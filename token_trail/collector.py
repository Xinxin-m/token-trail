"""Read-only transcript adapters. No provider calls, no raw message bodies in storage."""
from __future__ import annotations
import hashlib, json, re, sqlite3, time, os
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

VERSION = 5
UUID = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.I)

def stamp(s):
    if isinstance(s,(int,float)) and not isinstance(s,bool):return float(s)
    try: return datetime.fromisoformat(str(s).replace('Z','+00:00')).timestamp()
    except (ValueError, TypeError): return 0.0

def digest(s): return hashlib.sha256(s.encode('utf-8',errors='replace')).hexdigest()
def encoded(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',',':'))

def visible(x):
    """Exclude base64, image URLs, encrypted reasoning and transport metadata."""
    if isinstance(x,str): return x
    if isinstance(x,list): return '\n'.join(filter(None,(visible(b) for b in x)))
    if isinstance(x,dict):
        if x.get('type') in ('image','input_image','image_url'): return ''
        if x.get('type') in ('text','input_text','output_text'): return x.get('text','')
        for key in ('content','output','text'):
            if key in x:return visible(x[key])
    return ''

def image_count(x):
    if isinstance(x,list): return sum(image_count(v) for v in x)
    if isinstance(x,dict):
        if x.get('type') in ('image','input_image','image_url'): return 1
        return sum(image_count(v) for k,v in x.items() if k not in ('source','data'))
    return 0

def image_keys(x):
    if isinstance(x,list):return [k for v in x for k in image_keys(v)]
    if isinstance(x,dict):
        if x.get('type') in ('image','input_image','image_url'):
            return [digest(encoded(x.get('source') or x.get('image_url') or x.get('data') or x))]
        return [k for key,v in x.items() if key not in ('source','data') for k in image_keys(v)]
    return []

def category(name, args=''):
    s=(name+' '+args).lower()
    if re.search(r'skill\.md|/skills/|\bskill\b',s):return 'Skills'
    if re.search(r'spawn_agent|subagent|\bagent\b|\btask\b|codex (exec|resume)|claude .*?-p|mcp__codex',s):return 'Delegation'
    if re.search(r'web__|websearch|webfetch|web_search|search_query|browse|browser|playwright|https?://',s):return 'Web & browser'
    if re.search(r'view_image|screenshot|imagegen|image_gen|\.png\b|\.jpe?g\b',s):return 'Images'
    if re.search(r'apply_patch|\bedit\b|\bwrite\b',name.lower()):return 'Editing'
    if re.search(r'\bread\b|read_file|\bcat\b|\bsed\b|\.pdf\b|\.docx\b',s):return 'Files'
    if re.search(r'\brg\b|\bglob\b|\bgrep\b|search',s):return 'Search'
    if re.search(r'exec|bash|shell|terminal|stdin',s):return 'Shell & code'
    return 'Other tools'

def label_for(name,args):
    if isinstance(args,dict):
        for k in ('file_path','path','skill','url'):
            if isinstance(args.get(k),str):return args[k][:240]
    s=args if isinstance(args,str) else encoded(args)
    m=re.search(r'[^\s\"\'<>;,{}()]+/SKILL\.md',s)
    if m:return m.group(0)[-240:]
    return name

def clean_title(s):
    s=re.sub(r'<[^>]+>.*?</[^>]+>','',s,flags=re.S)
    if '## My request:' in s:s=s.split('## My request:',1)[1]
    s=re.sub(r'\s+',' ',s).strip(' #\n')
    return s[:150] or 'Untitled conversation'

def parse_file(path, provider):
    if provider in ('kimi','usage-jsonl'):
        from .adapters import kimi,generic
        return kimi(path) if provider=='kimi' else generic(path)
    path=Path(path); sid=path.stem; sub=provider=='claude' and 'subagents' in path.parts
    if sub:sid=path.parent.parent.name+'/'+path.stem
    elif provider=='codex':
        m=UUID.findall(path.stem);sid=m[-1] if m else path.stem
    session=dict(id=provider+':'+sid,provider=provider,native_id=sid,title='',cwd='',start=0,end=0,
                 parent='',lineage='',origin='unresolved',source='',topic='Uncategorized',compactions=0,
                 human_turns=0,warnings=[],forked_from='',window=0)
    if sub:session.update(parent='claude:'+path.parent.parent.name,lineage='Native subagent path',origin='agent')
    reqs={}; tools={}; items={}; links=[]; pending=[]; epoch=0; model='unknown'; previous=None
    malformed=0; rows=0; inherited=False; meta_start=0; meta_seen=False; copied_turn=False; counter_generation=0; last_purpose='Conversation'; detailed=False
    def add_item(key,ts,kind,body,label='',images=0,image_fingerprints=None):
        if not body and not images:return
        items[key]=dict(id=key,ts=ts,epoch=epoch,category=kind,label=label or kind,
                        chars=len(body),tokens=(len(body)+3)//4,fingerprint=digest(body) if body else '',images=images,image_fingerprints=image_fingerprints or [])
    def call(cid,ts,name,args):
        nonlocal last_purpose
        argstr=args if isinstance(args,str) else encoded(args)
        try:a=json.loads(argstr)
        except (ValueError,TypeError):a=args
        cat=category(name,argstr);last_purpose=cat;pending.append(cat)
        # A wrapper may contain several calls; retain names without inventing per-call billing.
        nested=sorted(set(re.findall(r'tools\.([A-Za-z_][\w]*)\s*\(',argstr)))
        tools[cid]=dict(id=cid,ts=ts,epoch=epoch,name=name,category=cat,label=label_for(name,a),
                        fingerprint=digest(name+' '+argstr),arg_tokens=(len(argstr)+3)//4,
                        result_tokens=0,result_chars=0,result_fingerprint='',images=0,error=False,
                        status='pending',nested=nested,launch_target='')
        if re.search(r'\bcodex\b',argstr) and re.search(r'\bexec\b|\bresume\b|mcp__codex',argstr):tools[cid]['launch_target']='codex'
        elif re.search(r'\bclaude\b',argstr) and re.search(r'(?:\s-p\b|--print\b|mcp__claude)',argstr):tools[cid]['launch_target']='claude'
        add_item('call:'+cid,ts,'Tool instructions',argstr,name)
    def result(cid,ts,out,error=False):
        t=tools.get(cid)
        if not t:
            call(cid,ts,'Unknown tool',{});t=tools[cid]
        body=visible(out);images=image_count(out)
        if not body and isinstance(out,dict):body=encoded({k:v for k,v in out.items() if k not in ('data','source')})
        # Explicit nonzero exits and tool protocol flags, not arbitrary occurrences of "error".
        failure=bool(error or re.search(r'(?:Process exited with code|exit_code[\"\s:]+|Exit code:)\s*[1-9]\d*',body))
        t.update(result_tokens=(len(body)+3)//4,result_chars=len(body),result_fingerprint=digest(body),
                 images=images,error=failure,status='error' if failure else 'complete')
        add_item('result:'+cid,ts,t['category'],body,t['label'],images,image_keys(out))
        if t['launch_target']:
            for uid in set(UUID.findall(body)):
                links.append(dict(parent=session['id'],child=t['launch_target']+':'+uid,evidence='Session ID in agent-launch tool result',ts=ts))
    def request(key,ts,u,purpose,kind):
        if provider=='claude':
            fresh=int(u.get('input_tokens',0));read=int(u.get('cache_read_input_tokens',0));write=int(u.get('cache_creation_input_tokens',0));inp=fresh+read+write
            reason=int((u.get('output_tokens_details') or {}).get('thinking_tokens',0))
        else:
            inp=int(u.get('input_tokens',0));read=int(u.get('cached_input_tokens',0));write=int(u.get('cache_write_input_tokens',0));fresh=max(0,inp-read-write);reason=int(u.get('reasoning_output_tokens',0))
        output=int(u.get('output_tokens',0))
        if not inp and not output:return
        r=dict(id=key,session=session['id'],ts=ts,model=model,input=inp,cache_read=read,cache_write=write,
               fresh=fresh,output=output,reasoning=reason,total=inp+output,purpose=purpose,epoch=epoch,kind=kind)
        if key in reqs:
            old=reqs[key]
            for field in ('input','cache_read','cache_write','fresh','output','reasoning','total'):r[field]=max(old[field],r[field])
        reqs[key]=r
    with path.open('rb') as f:
        for lineno,line in enumerate(f,1):
            if not line.endswith(b'\n'):continue # A writer may be mid-record.
            try:r=json.loads(line)
            except (ValueError,UnicodeDecodeError):malformed+=1;continue
            rows+=1;ts=stamp(r.get('timestamp'));typ=r.get('type');d=r.get('payload') or {}
            if provider=='codex' and typ=='session_meta':
                if meta_seen:continue # Older fork files also embed the ancestor's metadata.
                meta_seen=True
                sid=d.get('id',sid);session['id']='codex:'+sid;session['native_id']=sid
                meta_start=stamp(d.get('timestamp') or r.get('timestamp'))
                session['start']=meta_start;session['cwd']=d.get('cwd','');src=d.get('source','');session['source']=encoded(src) if isinstance(src,dict) else src
                parent=d.get('parent_thread_id') or ((src.get('subagent') or {}).get('thread_spawn') or {}).get('parent_thread_id') if isinstance(src,dict) else d.get('parent_thread_id')
                if parent:session.update(parent='codex:'+parent,origin='agent',lineage='Native parent_thread_id')
                elif src in ('vscode','cli','app'):session['origin']='likely human'
                session['forked_from']=d.get('forked_from_id','') or ''
                inherited=bool(parent or session['forked_from']);session['window']=d.get('context_window',0) or 0
                add_item('base',meta_start,'Instructions',visible(d.get('base_instructions',{})),'Base instructions')
                continue
            if ts:
                if not session['start']:session['start']=ts
                session['end']=max(session['end'],ts)
            if provider=='codex':
                if inherited and typ=='event_msg' and d.get('type')=='task_started':
                    started=d.get('started_at')
                    if isinstance(started,(int,float)):copied_turn=started<int(meta_start)
                    else:copied_turn=bool(ts and ts<meta_start)
                # Forks carry ancestor history. Do not bill it to the child again.
                if inherited and (copied_turn or (ts and ts<meta_start)):
                    if typ=='event_msg' and d.get('type')=='token_count' and d.get('info'):previous=d['info'].get('total_token_usage')
                    continue
                if typ=='turn_context':model=d.get('model',model);continue
                if typ=='compacted':epoch+=1;session['compactions']+=1;continue
                if typ=='token_usage_record':
                    u=d.get('usage') or {};detailed=True
                    owner=d.get('thread_id')
                    if owner and owner!=sid:continue
                    request('codex:response:'+str(d.get('response_id') or digest(encoded(d))),ts,u,last_purpose,'response')
                elif typ=='event_msg' and d.get('type')=='token_count':
                    info=d.get('info') or {};total=info.get('total_token_usage')
                    if not total:continue
                    if d.get('rate_limits'):session['rate_limits']=dict(timestamp=ts,**d['rate_limits'])
                    session['window']=info.get('model_context_window') or session['window']
                    if previous==total:continue
                    if previous is None:
                        delta=info.get('last_token_usage',total) if inherited else total
                        if inherited:session['warnings'].append('Initial inherited cumulative baseline uses last_token_usage')
                    elif total.get('total_tokens',0)>=previous.get('total_tokens',0):delta={k:max(0,v-previous.get(k,0)) for k,v in total.items() if isinstance(v,(int,float))}
                    else:
                        counter_generation+=1
                        delta=info.get('last_token_usage') or total
                        session['warnings'].append('Cumulative counter reset; used last_token_usage')
                    previous=total
                    request('codex:cumulative:'+sid+':'+str(counter_generation)+':'+digest(encoded(total)),ts,delta,last_purpose,'cumulative')
                elif typ=='response_item':
                    kind=d.get('type');cid=d.get('call_id') or d.get('id') or str(lineno)
                    if kind in ('function_call','custom_tool_call'):call(cid,ts,d.get('name','Unknown'),d.get('arguments',d.get('input','')))
                    elif kind in ('function_call_output','custom_tool_call_output'):result(cid,ts,d.get('output',''))
                    elif kind=='message':
                        role=d.get('role','');body=visible(d.get('content'));key=d.get('id') or digest(role+str(ts)+body)
                        if role=='user':
                            session['human_turns']+=1
                            if not session['title']:session['title']=clean_title(body)
                            last_purpose='Conversation'
                        add_item('msg:'+key,ts,{'user':'User prompts','developer':'Instructions','system':'Instructions'}.get(role,'Assistant text'),body,role,image_count(d.get('content')),image_keys(d.get('content')))
            else:
                session['cwd']=r.get('cwd') or session['cwd'];session['source']=r.get('entrypoint') or session['source']
                if not sub and r.get('origin',{}).get('kind')=='human':session['origin']='human'
                elif not sub and session['origin']=='unresolved' and session['source'] in ('claude-vscode','cli'):session['origin']='likely human'
                if typ=='system' and r.get('subtype')=='compact_boundary':epoch+=1;session['compactions']+=1;continue
                if typ in ('custom-title','ai-title'):
                    session['title']=r.get('customTitle') or r.get('title') or session['title'];continue
                msg=r.get('message') or {};content=msg.get('content',[]);blocks=content if isinstance(content,list) else [{'type':'text','text':content}]
                if typ=='assistant':
                    model=msg.get('model',model)
                    cats=[category(b.get('name',''),encoded(b.get('input',{}))) for b in blocks if isinstance(b,dict) and b.get('type')=='tool_use']
                    purpose=cats[0] if len(set(cats))==1 else 'Mixed tools' if cats else last_purpose
                    if msg.get('usage'):
                        request('claude:'+str(msg.get('id') or r.get('requestId') or r.get('uuid')),ts,msg['usage'],purpose,'response')
                    for i,b in enumerate(blocks):
                        if not isinstance(b,dict):continue
                        if b.get('type')=='tool_use':call(b['id'],ts,b.get('name','Unknown'),b.get('input',{}))
                        elif b.get('type')=='text':add_item('text:'+str(r.get('uuid',lineno))+':'+str(i),ts,'Assistant text',b.get('text',''),'assistant')
                elif typ=='user':
                    actual=False
                    for i,b in enumerate(blocks):
                        if not isinstance(b,dict):continue
                        if b.get('type')=='tool_result':result(b.get('tool_use_id',str(lineno)),ts,b.get('content',''),b.get('is_error',False))
                        else:
                            body=visible(b);add_item('user:'+str(r.get('uuid',lineno))+':'+str(i),ts,'User prompts',body,'user',image_count(b),image_keys(b));actual=actual or bool(body)
                            if body and not session['title']:session['title']=clean_title(body)
                    if actual:session['human_turns']+=1;last_purpose='Conversation'
    # New Codex records have stable response IDs and per-request usage. Prefer them for
    # their covered period; retain legacy counter deltas before the first detailed record.
    if detailed:
        detailed_rows=[r for r in reqs.values() if r['kind']=='response']
        start=min((r['ts'] for r in detailed_rows),default=float('inf'))
        reqs={k:r for k,r in reqs.items() if r['kind']=='response' or r['ts']<start-2}
    session['title']=session['title'] or 'Untitled conversation';session['warnings']=sorted(set(session['warnings']))
    if malformed:session['warnings'].append(f'{malformed} malformed JSON lines skipped')
    session['rows']=rows
    return dict(session=session,requests=list(reqs.values()),tools=list(tools.values()),items=list(items.values()),links=links)

SCHEMA='''
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,mtime INTEGER,size INTEGER,version INTEGER,parsed_at REAL,payload BLOB);
CREATE TABLE IF NOT EXISTS overrides(child TEXT PRIMARY KEY,parent TEXT,reason TEXT,updated_at REAL);
CREATE TABLE IF NOT EXISTS trace_events(id TEXT PRIMARY KEY,payload TEXT);
'''

def connect(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=30);db.execute('PRAGMA journal_mode=WAL');db.executescript(SCHEMA)
    try:os.chmod(path,0o600)
    except OSError:pass
    return db

def scan(db,claude_root=None,codex_root=None,progress=None,config=None):
    import zlib
    known={r[0]:r[1:] for r in db.execute('SELECT path,mtime,size,version FROM files')};changed=0;errors=[];found=[]
    from .adapters import sources
    config=config if config is not None else dict(sources=[dict(adapter=k,path=str(v)) for k,v in [('claude',claude_root),('codex',codex_root)] if v])
    available=[]
    for source in sources(config):
        provider=source['adapter'];root=Path(source['path']).expanduser()
        if not root.exists():continue # A single-provider installation is normal.
        available.append(provider)
        paths=[root] if root.is_file() else sorted(root.rglob('wire.jsonl' if provider=='kimi' else '*.jsonl'))
        for p in paths:
            try:
                st=p.stat();key=str(p);found.append(key)
                if known.get(key)==(st.st_mtime_ns,st.st_size,VERSION):continue
                parsed=parse_file(p,provider)
                payload=zlib.compress(encoded(parsed).encode(),3)
                db.execute('INSERT INTO files VALUES(?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime,size=excluded.size,version=excluded.version,parsed_at=excluded.parsed_at,payload=excluded.payload',
                           (key,st.st_mtime_ns,st.st_size,VERSION,time.time(),payload))
                changed+=1
                if changed%100==0:
                    db.commit()
                    if progress:progress(changed)
            except (OSError,ValueError,TypeError,KeyError) as e:errors.append(f'{p.name}: {type(e).__name__}: {e}')
    db.commit()
    return dict(changed=changed,files=len(found),errors=errors,available_adapters=sorted(set(available)),scanned_at=time.time())

def load(db):
    import zlib
    result=[]
    for row in db.execute('SELECT payload FROM files'):
        b=json.loads(zlib.decompress(row[0]));result.extend(b['bundles'] if 'bundles' in b else [b])
    return result
