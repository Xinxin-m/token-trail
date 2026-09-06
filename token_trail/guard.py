"""Small evidence-based advisory. Does not compact, reroute, block or call a model."""
import json,zlib,time
from .collector import connect

def advise(config,sid):
    db=connect(config['db']);native=sid.split(':',1)[-1];latest=None
    for (blob,) in db.execute('SELECT payload FROM files WHERE path LIKE ?',('%'+native.split('/')[-1]+'%',)):
        d=json.loads(zlib.decompress(blob))
        if d['session']['id']==sid and d['requests']:latest=d
    db.close()
    if not latest:return {'session':sid,'status':'unknown','reason':'No measured usage for this session yet'}
    request=max(latest['requests'],key=lambda r:r['ts']);s=latest['session'];tools=latest['tools'];threshold=150000
    signals=[]
    if request['input']>=threshold:signals.append('Large input context: checkpoint completed work and use targeted retrieval before adding more large results.')
    failures=sum(t['error'] for t in tools[-6:])
    if failures>=2:signals.append('At least two recent tool error signals: inspect the cause before retrying the same approach.')
    return dict(session=sid,status='review' if signals else 'healthy',measured_at=request['ts'],input_tokens=request['input'],cache_read=request['cache_read'],signals=signals,
                rule='Preserve required evidence and capable final review; no automatic model downgrade or compaction.')
