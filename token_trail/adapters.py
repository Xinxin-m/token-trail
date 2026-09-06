"""Portable sources: native Kimi CLI wire events and an explicit usage JSONL contract."""
import json, math, re
from pathlib import Path
from .collector import clean_title, digest, encoded, stamp, visible

NAME = re.compile(r'^[a-z][a-z0-9_-]{0,39}$')

def sources(config):
    if config.get('demo'):return [] # Never discover personal sources in a synthetic demo.
    if 'sources' in config:
        result=config['sources']
        if not isinstance(result,list):raise ValueError('sources must be a list')
    else:
        result=[dict(adapter=k,path=config.get(k+'_root',default)) for k,default in
                [('claude','~/.claude/projects'),('codex','~/.codex/sessions'),('kimi','~/.kimi/sessions')]]
    for source in result:
        if source.get('adapter') not in ('claude','codex','kimi','usage-jsonl'):raise ValueError('Unsupported adapter')
        if not isinstance(source.get('path'),str) or not source['path']:raise ValueError('Each source needs a path')
    return [s for s in result if s.get('enabled',True)]

def bundle(provider,sid,parent=''):
    return dict(session=dict(id=provider+':'+sid,provider=provider,native_id=sid,title='Untitled conversation',cwd='',start=0,end=0,
                             parent=parent,lineage='Explicit parent ID' if parent else '',origin='agent' if parent else 'unresolved',source=provider,
                             topic='Uncategorized',compactions=0,human_turns=0,warnings=[],forked_from='',window=0,rows=0),
                requests=[],tools=[],items=[],links=[])

def integer(u,key,default=0):
    n=u.get(key,default)
    if isinstance(n,bool) or not isinstance(n,int) or n<0:raise ValueError(f'{key} must be a nonnegative integer')
    return n

def request(s,key,ts,model,u,epoch=0,purpose='Conversation'):
    fresh=integer(u,'fresh');read=integer(u,'cache_read');write=integer(u,'cache_write');output=integer(u,'output');reason=integer(u,'reasoning')
    if reason>output:raise ValueError('reasoning must be a subset of output')
    return dict(id=key,session=s['id'],ts=ts,model=model or 'unknown',input=fresh+read+write,cache_read=read,cache_write=write,
                fresh=fresh,output=output,reasoning=reason,total=fresh+read+write+output,purpose=purpose,epoch=epoch,kind='response')

def touch(s,ts):
    if not math.isfinite(ts) or ts<=0:raise ValueError('A valid positive timestamp is required')
    s['start']=min(s['start'],ts) if s['start'] else ts;s['end']=max(s['end'],ts);s['rows']+=1

def lines(path):
    with Path(path).open('rb') as f:
        for number,line in enumerate(f,1):
            if not line.endswith(b'\n'):continue
            try:
                record=json.loads(line)
                if not isinstance(record,dict):raise ValueError('Record must be an object')
                yield number,record,None
            except (ValueError,UnicodeDecodeError) as e:yield number,{},str(e)

def generic(path):
    """One file can contain multiple sessions. No field guessing or cumulative counters."""
    bundles={};warnings=[];seen={}
    for number,r,error in lines(path):
        try:
            if error:raise ValueError(error)
            if r.get('schema')!='token-trail.usage.v1':raise ValueError('Expected schema token-trail.usage.v1')
            provider=r['provider'];sid=r['session_id'];rid=r['request_id']
            if not isinstance(provider,str) or not NAME.fullmatch(provider):raise ValueError('Invalid provider name')
            if not all(isinstance(x,str) and x for x in (sid,rid)):raise ValueError('session_id and request_id must be nonempty strings')
            key=provider+':'+sid;parent=r.get('parent_id','')
            if parent and (not isinstance(parent,str) or ':' not in parent or parent==key):raise ValueError('parent_id must be a distinct namespaced ID')
            b=bundles.setdefault(key,bundle(provider,sid,parent));s=b['session']
            if s['parent']!=parent:raise ValueError('Conflicting parent_id within session')
            ts=stamp(r['timestamp']);touch(s,ts)
            s['title']=clean_title(str(r.get('title') or s['title']));s['topic']=str(r.get('topic') or s['topic'])[:150]
            if r.get('origin') in ('human','agent','automation','unresolved') and not parent:s['origin']=r['origin']
            u=r['usage']
            if not isinstance(u,dict) or not all(k in u for k in ('fresh','cache_read','cache_write','output')):raise ValueError('usage needs fresh, cache_read, cache_write, output; use 0 only when known')
            row=request(s,provider+':response:'+rid,ts,str(r.get('model') or 'unknown'),u,purpose=str(r.get('purpose') or 'Conversation')[:80])
            old=seen.get(row['id'])
            if old:
                if old!=row:raise ValueError('Conflicting duplicate request_id')
                continue
            seen[row['id']]=row;b['requests'].append(row)
        except (ValueError,TypeError,KeyError) as e:warnings.append(f'Line {number}: {e}')
    if not bundles:bundles['empty']=bundle('usage-jsonl',digest(str(Path(path).resolve()))[:24])
    result=list(bundles.values());result[0]['session']['warnings']+=warnings[:20]
    return dict(bundles=result)

def kimi(path):
    """Python kimi-cli WireMessageRecord. No credentials or context.jsonl reads."""
    sid=Path(path).parent.name;root=bundle('kimi',sid);all_bundles={root['session']['id']:root};states={};seen={};warnings=[]
    def process(msg,ts,b,number,depth=0):
        if depth>16:raise ValueError('Subagent nesting exceeds 16')
        typ=msg.get('type');d=msg.get('payload') or {};s=b['session'];touch(s,ts)
        st=states.setdefault(s['id'],dict(turn=0,step=0,attempt=0,epoch=0))
        if typ=='SubagentEvent':
            child=d.get('agent_id') or d.get('parent_tool_call_id') or d.get('task_tool_call_id')
            if not child:raise ValueError('Subagent event lacks identity; skipped to avoid false attribution')
            native=s['native_id']+'/'+str(child);key='kimi:'+native
            cb=all_bundles.setdefault(key,bundle('kimi',native,s['id']))
            cb['session']['lineage']='Native Kimi SubagentEvent';process(d['event'],ts,cb,number,depth+1)
        elif typ in ('TurnBegin','SteerInput'):
            st['turn']+=1;st['step']=0;s['human_turns']+=int(not s['parent'])
            if s['title']=='Untitled conversation':s['title']=clean_title(visible(d.get('user_input','')))
            # A TurnBegin can also be headless automation; do not assert human origin.
        elif typ=='StepBegin':st['step']=d.get('n',st['step']+1);st['attempt']=0
        elif typ=='StepRetry':st['attempt']=d.get('next_attempt',st['attempt']+1)
        elif typ=='CompactionEnd':st['epoch']+=1;s['compactions']+=1
        elif typ=='StatusUpdate':
            s['window']=d.get('max_context_tokens') or s['window']
            usage=d.get('token_usage')
            if usage is None:return
            if not isinstance(usage,dict):raise ValueError('Invalid token_usage')
            required=('input_other','input_cache_read','input_cache_creation','output')
            if not all(k in usage for k in required):raise ValueError('Unsupported Kimi usage fields; expected Python wire snake_case counters')
            u=dict(fresh=usage['input_other'],cache_read=usage['input_cache_read'],cache_write=usage['input_cache_creation'],output=usage['output'])
            message=d.get('message_id')
            if not message and not st['step']:raise ValueError('Usage lacks message_id and StepBegin identity')
            key='kimi:response:'+str(message) if message else s['id']+f":turn:{st['turn']}:step:{st['step']}:attempt:{st['attempt']}"
            row=request(s,key,ts,d.get('model','unknown'),u,st['epoch'],'Delegation' if s['parent'] else 'Conversation')
            if key in seen:
                old=seen[key]
                if old['session']!=s['id']:return # Mirrored same provider response already accounted for.
                if row['total']>=old['total']:old.update({k:row[k] for k in ('input','fresh','cache_read','cache_write','output','total')})
            else:seen[key]=row;b['requests'].append(row)
    for number,r,error in lines(path):
        try:
            if error:raise ValueError(error)
            if r.get('type')=='metadata':continue
            if 'message' not in r:raise ValueError('Unsupported Kimi wire envelope')
            process(r['message'],stamp(r.get('timestamp')),root,number)
        except (ValueError,TypeError,KeyError,AttributeError) as e:warnings.append(f'Line {number}: {e}')
    root['session']['warnings']+=warnings[:20]
    root['session']['warnings'].append('Kimi wire adapter: model may be absent; tool payload attribution is not implemented. Headless vs human origin is unknown without explicit lineage.')
    return dict(bundles=list(all_bundles.values()))
