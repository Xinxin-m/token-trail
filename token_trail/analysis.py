"""An auditable read model: measured usage, observed activity, estimated text sizes."""
from __future__ import annotations
import json, time, bisect
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
from .collector import load

FIELDS=('input','cache_read','cache_write','fresh','output','reasoning','total')
def zero():return dict.fromkeys(FIELDS,0)|{'requests':0}
def add(a,r):
    for k in FIELDS:a[k]+=r.get(k,0)
    a['requests']+=r.get('requests',1)
    return a

def read_json(p,default):
    try:return json.loads(Path(p).read_text())
    except (OSError,ValueError):return default

class Ledger:
    def __init__(self,db,library=None):
        self.sessions={}; self.requests=[];self.tools=[];self.items=[];self.links=[];self.duplicates=0
        seen={};seen_tools=set();seen_items=set()
        for bundle in load(db):
            s=bundle['session'];sid=s['id']
            if sid in self.sessions:
                old=self.sessions[sid]
                s['start']=min(old['start'],s['start']);s['end']=max(old['end'],s['end'])
            self.sessions[sid]=s
            for r in bundle['requests']:
                if r['id'] in seen:
                    self.duplicates+=1
                    original=seen[r['id']]
                    if r['total']>original['total']:
                        for field in FIELDS:original[field]=r[field]
                    continue
                seen[r['id']]=r;r['session']=sid;self.requests.append(r)
            for r in bundle['tools']:
                k=(sid,r['id'])
                if k in seen_tools:continue
                seen_tools.add(k);self.tools.append(dict(r,session=sid))
            for r in bundle['items']:
                k=(sid,r['id'])
                if k in seen_items:continue
                seen_items.add(k);self.items.append(dict(r,session=sid))
            self.links.extend(bundle['links'])
        # IDs emitted by a launch are stronger evidence than cwd/time proximity.
        candidates=defaultdict(set)
        for edge in self.links:
            child=self.sessions.get(edge['child']);parent=self.sessions.get(edge['parent'])
            if not child or not parent or child['id']==parent['id']:continue
            if child.get('parent') or child['origin'] in ('human','likely human'):continue
            if parent['start']<=child['start']<=edge['ts']+120 and abs(edge['ts']-child['start'])<24*3600:
                candidates[child['id']].add(parent['id'])
        for child,parents in candidates.items():
            if len(parents)==1:self.sessions[child].update(parent=next(iter(parents)),origin='agent',lineage='Session ID in agent-launch tool result')
        # Some headless Claude processes inherit the VS Code entrypoint. Repeated
        # long prompt templates are an automation signal, not proof of a parent.
        templates=Counter(s['title'][:110] for s in self.sessions.values() if len(s['title'])>=110 and not s['parent'])
        for s in self.sessions.values():
            if s['origin']!='human' and not s['parent'] and templates[s['title'][:110]]>=4:
                s.update(origin='likely automation',lineage='Repeated prompt template (inferred)')
        for child,parent,reason,_ in db.execute('SELECT * FROM overrides'):
            if child in self.sessions:
                self.sessions[child].update(parent=parent or '',origin='agent' if parent else 'human',lineage=reason)
        # The optional wrapper/hook writes only IDs and PID ancestry, never prompts.
        events=[json.loads(r[0]) for r in db.execute('SELECT payload FROM trace_events')]
        runs={e.get('run_id'):e for e in events if e.get('kind')=='launch'}
        for e in events:
            if e.get('kind')!='session_start':continue
            sid=e.get('session');run=runs.get(e.get('run_id'));parent=e.get('parent') or (run or {}).get('parent')
            if sid in self.sessions and parent in self.sessions and sid!=parent:
                self.sessions[sid].update(parent=parent,origin='agent',lineage='Instrumented launch trace')
        # Read-only integration with the user's optional chat library.
        if library:
            p=Path(library).expanduser();index=read_json(p/'index.json',{});enrich=read_json(p/'enrich.json',{});projects=read_json(p/'projects.json',{})
            names={r['id']:r['name'] for r in projects.get('projects',[])}
            for s in self.sessions.values():
                key=s['id'].replace(':','-',1);m=index.get(key,{});e=enrich.get(key,{})
                s['title']=e.get('title') or m.get('title_seed') or s['title']
                assignment=projects.get('assignments',{}).get(key)
                if assignment:s['topic']=names.get(assignment,assignment);s['topic_source']='Chat library'
                else:s['topic_source']='Unassigned'
        self.cycles=[]
        for sid,s in self.sessions.items():
            root=sid;visited=set()
            while self.sessions.get(root,{}).get('parent'):
                if root in visited:
                    self.cycles.append(sid);root=sid;break
                visited.add(root);parent=self.sessions[root]['parent']
                if parent not in self.sessions:break
                root=parent
            s['root']=root
        for s in self.sessions.values():
            root=self.sessions.get(s['root'],s)
            s['root_origin']=root['origin'];s['root_title']=root['title'];s['root_topic']=root.get('topic','Uncategorized')
        self.requests.sort(key=lambda r:r['ts']);self.tools.sort(key=lambda r:r['ts']);self.items.sort(key=lambda r:r['ts'])
        self.session_requests=defaultdict(list);self.session_tools=defaultdict(list)
        for r in self.requests:
            s=self.sessions[r['session']];r['root']=s['root'];r['provider']=s['provider'];r['topic']=s['root_topic'];self.session_requests[r['session']].append(r)
        for r in self.tools:
            s=self.sessions[r['session']];r['root']=s['root'];r['provider']=s['provider'];r['topic']=s['root_topic'];self.session_tools[r['session']].append(r)
        for r in self.items:
            s=self.sessions[r['session']];r['root']=s['root'];r['provider']=s['provider'];r['topic']=s['root_topic']
        self.created=time.time()

    def scope(self,hours=None,provider='all',topic='all',now=None,root=None):
        now=now or time.time();start=now-float(hours)*3600 if hours is not None else 0
        def ok(r):return start<=r['ts']<=now and (provider=='all' or r['provider']==provider) and (topic=='all' or r['topic']==topic) and (not root or r['root']==root)
        return [r for r in self.requests if ok(r)],[r for r in self.tools if ok(r)],[r for r in self.items if ok(r)]

    def summary(self,hours=None,provider='all',topic='all',now=None,root=None):
        now=now or time.time();requests,tools,items=self.scope(hours,provider,topic,now,root)
        total=zero();groups=defaultdict(zero);providers=defaultdict(zero);models=defaultdict(zero);purposes=defaultdict(zero);topics=defaultdict(zero);days=defaultdict(zero);hourly=defaultdict(zero)
        byroot=defaultdict(list)
        for r in requests:
            add(total,r);add(groups[r['root']],r);add(providers[r['provider']],r);add(models[r['model']],r);add(purposes[r['purpose']],r);add(topics[r['topic']],r)
            add(days[datetime.fromtimestamp(r['ts']).strftime('%Y-%m-%d')],r)
            add(hourly[datetime.fromtimestamp(r['ts']).strftime('%Y-%m-%d %H:00')],r);byroot[r['root']].append(r)
        roots=[];active_sids={r['session'] for r in requests};native_children=sum(bool(self.sessions[s]['parent']) for s in active_sids)
        for sid,usage in groups.items():
            s=self.sessions.get(sid);rs=byroot[sid];members={r['session'] for r in rs}
            roots.append(dict(id=sid,title=s['title'],topic=s.get('topic','Uncategorized'),origin=s['origin'],start=s['start'],end=max(r['ts'] for r in rs),
                              child_count=len(members-{sid}),providers=sorted({r['provider'] for r in rs}),
                              child_tokens=sum(r['total'] for r in rs if r['session']!=sid),**usage))
        roots.sort(key=lambda s:s['total'],reverse=True)
        # Repeat result hashes must match within one native session. A re-read can be
        # justified; the estimate is payload size, never a promised saving or invoice.
        repeats=Counter();repeated_tokens=0;repeat_calls=0;failures=0;tool_groups={};skill_groups={};duplicate_rows=[]
        for t in tools:
            k=t['name'];g=tool_groups.setdefault(k,dict(name=k,calls=0,failures=0,result_tokens=0,repeat_tokens=0,nested=Counter()))
            g['calls']+=1;g['result_tokens']+=t['result_tokens'];g['failures']+=int(t['error']);g['nested'].update(t['nested']);failures+=int(t['error'])
            fp=t.get('result_fingerprint');key=(t['session'],fp)
            if fp and t['result_tokens']>=100:
                if repeats[key]:
                    repeated_tokens+=t['result_tokens'];repeat_calls+=1;g['repeat_tokens']+=t['result_tokens']
                    duplicate_rows.append(dict(session=t['session'],root=t['root'],label=t['label'],tokens=t['result_tokens'],ts=t['ts'],tool=t['name']))
                repeats[key]+=1
            if t['category']=='Skills':
                sg=skill_groups.setdefault(t['label'],dict(name=t['label'],calls=0,result_tokens=0,sessions=set()))
                sg['calls']+=1;sg['result_tokens']+=t['result_tokens'];sg['sessions'].add(t['session'])
        for g in tool_groups.values():g['nested']=dict(g['nested'])
        for g in skill_groups.values():g['sessions']=len(g['sessions'])
        resources={};resource_seen=Counter()
        for t in tools:
            if t['category'] not in ('Skills','Files','Images') or t['label']==t['name']:continue
            k=(t['session'],t['label']);resource_seen[k]+=1
            row=resources.setdefault(t['label'],dict(name=t['label'],calls=0,result_tokens=0,rereads=0,repeat_result_tokens=0,category=t['category']))
            row['calls']+=1;row['result_tokens']+=t['result_tokens']
            if resource_seen[k]>1:row['rereads']+=1;row['repeat_result_tokens']+=t['result_tokens']
        image_seen=Counter();repeated_images=0
        for i in items:
            for fp in i.get('image_fingerprints',[]):
                k=(i['session'],fp)
                if image_seen[k]:repeated_images+=1
                image_seen[k]+=1
        content=defaultdict(lambda:dict(tokens=0,items=0,images=0))
        for i in items:g=content[i['category']];g['tokens']+=i['tokens'];g['items']+=1;g['images']+=i['images']
        measured_children=sum(r['total'] for r in requests if r['session']!=r['root'])
        unresolved=sum(s['total'] for s in roots if s['origin'] not in ('human','likely human'))
        warning_count=sum(bool(s.get('warnings')) for s in self.sessions.values())
        limits=[0,16000,32000,64000,128000,256000,512000,float('inf')]
        labels=['<16k','16–32k','32–64k','64–128k','128–256k','256–512k','512k+']
        histogram=[dict(label=label,claude=0,codex=0,count=0,total=0) for label in labels]
        for r in requests:
            idx=min(6,bisect.bisect_right(limits,r['input'])-1);b=histogram[idx];b[r['provider']]=b.get(r['provider'],0)+1;b['count']+=1;b['total']+=r['total']
        ordered=sorted(r['input'] for r in requests)
        quantiles={k:(ordered[min(len(ordered)-1,int((len(ordered)-1)*p))] if ordered else 0) for k,p in [('median',.5),('p90',.9),('max',1)]}
        # Uniform deterministic sample plus largest-context outliers; the histogram
        # above always uses every request. Keep the full ledger off the wire.
        selected={r['id']:r for r in requests[::max(1,len(requests)//700)]}
        selected.update({r['id']:r for r in sorted(requests,key=lambda r:r['input'],reverse=True)[:30]})
        points=[dict(input=r['input'],cache=r['cache_read']/max(1,r['input']),output=r['output'],provider=r['provider'],root=r['root'],title=self.sessions[r['root']]['title'],ts=r['ts']) for r in selected.values()]
        def ranked(d):return sorted([dict(name=k,**v) for k,v in d.items()],key=lambda r:r['total'],reverse=True)
        flags=[]
        if repeated_tokens:flags.append(dict(title='Repeated tool payloads',evidence=f'{repeat_calls:,} repeated results within native sessions; about {repeated_tokens:,} text tokens returned again.',action='Reuse the existing result or cache a compact artifact when the content is unchanged. Repetition is a review candidate, not proof of waste.',metric=repeated_tokens,kind='estimate'))
        if failures:flags.append(dict(title='Tool failures',evidence=f'{failures:,} of {len(tools):,} recorded tool calls report an explicit error or nonzero exit.',action='After two failures with the same cause, inspect the cause and change approach. Preserve necessary retries.',metric=failures,kind='observed'))
        if measured_children:flags.append(dict(title='Delegated work',evidence=f'{measured_children:,} measured tokens belong to linked child sessions ({100*measured_children/max(1,total["total"]):.1f}% of usage).',action='Review the largest trees. Give each child a bounded question and reuse it for follow-ups; keep critical decisions with a capable reviewer.',metric=measured_children,kind='measured'))
        if unresolved:flags.append(dict(title='Unattributed launches',evidence=f'{unresolved:,} tokens remain in roots whose human origin is unconfirmed.',action='Attach an unresolved run to its parent in Lineage, or use the launch wrapper for future cross-provider calls.',metric=unresolved,kind='measured'))
        return dict(generated_at=self.created,as_of=now,hours=hours,totals=total,roots=roots,providers=ranked(providers),models=ranked(models),purposes=ranked(purposes),topics=ranked(topics),
                    visuals=dict(histogram=histogram,quantiles=quantiles,points=points,point_population=len(requests)),
                    daily=[dict(date=k,**v) for k,v in sorted(days.items())],hourly=[dict(date=k,**v) for k,v in sorted(hourly.items())],
                    tools=sorted(tool_groups.values(),key=lambda x:x['result_tokens'],reverse=True),skills=sorted(skill_groups.values(),key=lambda x:x['result_tokens'],reverse=True),
                    resources=sorted(resources.values(),key=lambda x:x['repeat_result_tokens'],reverse=True),
                    content=[dict(name=k,**v) for k,v in sorted(content.items(),key=lambda kv:kv[1]['tokens'],reverse=True)],
                    repeats=sorted(duplicate_rows,key=lambda x:x['tokens'],reverse=True)[:60],insights=flags,
                    coverage=dict(native_sessions=len(active_sids),human_roots=sum(r['origin']=='human' for r in roots),likely_human_roots=sum(r['origin']=='likely human' for r in roots),
                                  unresolved_roots=sum(r['origin'] not in ('human','likely human') for r in roots),linked_children=native_children,child_tokens=measured_children,
                                  unresolved_tokens=unresolved,deduplicated_records=self.duplicates,warning_sessions=warning_count,cycles=len(self.cycles)),
                    observed=dict(tool_calls=len(tools),tool_failures=failures,repeated_results=repeat_calls,repeated_result_tokens_estimate=repeated_tokens,images=sum(i['images'] for i in items),repeated_images=repeated_images,resource_rereads=sum(r['rereads'] for r in resources.values())),
                    all_providers=sorted({s['provider'] for s in self.sessions.values()}),
                    all_topics=sorted({s['root_topic'] for s in self.sessions.values()}),
                    rate_limits=[dict(session=s['id'],provider=s['provider'],**s['rate_limits']) for s in self.sessions.values() if s.get('rate_limits') and now-s['rate_limits']['timestamp']<86400][-10:])

    def detail(self,sid,hours=None,provider='all',topic='all'):
        if sid not in self.sessions:return None
        root=self.sessions[sid]['root'];summary=self.summary(hours,provider,topic,root=root)
        members=[]
        for s in self.sessions.values():
            if s['root']!=root:continue
            usage=zero()
            for r in self.session_requests[s['id']]:add(usage,r)
            members.append(dict(s,usage=usage))
        scoped,scoped_tools,_=self.scope(hours,provider,topic,root=root)
        summary['members']=sorted(members,key=lambda s:s['start'])
        summary['requests']=scoped[-500:];summary['request_rows_total']=len(scoped)
        summary['tool_events']=sorted(scoped_tools,key=lambda t:t['result_tokens'],reverse=True)[:100]
        summary['root']=self.sessions[root]
        return summary

    def lineage(self):
        rows=[]
        for s in self.sessions.values():
            usage=zero()
            for r in self.session_requests[s['id']]:add(usage,r)
            if not usage['total']:continue
            rows.append(dict(id=s['id'],title=s['title'],provider=s['provider'],parent=s['parent'],root=s['root'],origin=s['origin'],lineage=s['lineage'],start=s['start'],end=s['end'],total=usage['total'],source=s['source']))
        return sorted(rows,key=lambda r:r['total'],reverse=True)
