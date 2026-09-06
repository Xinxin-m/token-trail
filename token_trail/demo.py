"""Generate fictional sessions into a fresh demo directory; never read user logs."""
import json,time,uuid,zlib
from pathlib import Path
from datetime import datetime,timezone
from .collector import connect,encoded

def seed(config):
    target=Path(config['db']).parent/'demo'
    target.mkdir(parents=True,exist_ok=True)
    dbpath=target/'ledger.sqlite'
    if dbpath.exists():raise SystemExit('Demo already exists. Use its printed config, or choose a fresh TOKEN_TRAIL_DATA directory.')
    db=connect(dbpath);now=time.time();roots=[]
    tasks=[('Ship the analytics workspace','Product'),('Research a new market','Research'),('Fix the import pipeline','Engineering'),('Review authentication design','Engineering'),('Write the release notes','Product')]
    for i,(title,topic) in enumerate(tasks):
        sid=('claude' if i%2==0 else 'codex')+':'+str(uuid.uuid4());roots.append(sid)
        for child in range(1+(i in (0,1))*3):
            native=sid if child==0 else ('codex' if child%2 else 'claude')+':'+str(uuid.uuid4());provider=native.split(':')[0];start=now-(6-i)*86400
            s=dict(id=native,provider=provider,native_id=native.split(':')[1],title=title if child==0 else ['','Validate API contracts','Collect source evidence','Review the implementation'][child],cwd='demo',start=start,end=start+3600,parent='' if child==0 else sid,lineage='' if child==0 else 'Synthetic native parent',origin='human' if child==0 else 'agent',source='demo',topic=topic,compactions=0,human_turns=4,warnings=[],forked_from='',window=200000)
            requests=[];tools=[];items=[]
            for j in range(40):
                inp=14000+j*900+child*2500;cache=int(inp*.88);output=600+j*12;ts=start+j*80
                r=dict(id=native+':r'+str(j),session=native,ts=ts,model='Demo capable model',input=inp,cache_read=cache,cache_write=0,fresh=inp-cache,output=output,reasoning=output//3,total=inp+output,purpose=['Files','Web & browser','Editing','Skills'][j%4],epoch=0,kind='response');requests.append(r)
                t=dict(id=native+':t'+str(j),ts=ts,epoch=0,name=['Read','WebFetch','Edit','Read'][j%4],category=r['purpose'],label='sample/SKILL.md' if j%4==3 else 'Sample artifact',fingerprint=str(j),arg_tokens=40,result_tokens=800+j*5,result_chars=3200+j*20,result_fingerprint=str(j//2),images=0,error=j==10,status='error' if j==10 else 'complete',nested=[],launch_target='');tools.append(t)
                items.append(dict(id=t['id'],ts=ts,epoch=0,category=t['category'],label=t['label'],chars=t['result_chars'],tokens=t['result_tokens'],fingerprint=t['result_fingerprint'],images=0))
            bundle=dict(session=s,requests=requests,tools=tools,items=items,links=[])
            db.execute('INSERT INTO files VALUES(?,?,?,?,?,?)',(native,0,0,2,now,zlib.compress(encoded(bundle).encode())))
    db.commit();db.close()
    (target/'claude').mkdir(exist_ok=True);(target/'codex').mkdir(exist_ok=True)
    cfg=dict(sources=[],db=str(dbpath.resolve()),claude_root=str((target/'claude').resolve()),codex_root=str((target/'codex').resolve()),port=8766,interval=5,library='',demo=True)
    path=target/'config.json';path.write_text(json.dumps(cfg,indent=2));print('Synthetic demo created. Run:\npython3 -m token_trail --config '+str(path)+' serve')
