"""Loopback-only HTTP app. Source logs are read-only; no remote services are contacted."""
import csv, io, json, mimetypes, threading, time, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from .collector import connect,scan
from .analysis import Ledger

WEB=Path(__file__).parent/'web'
class State:
    def __init__(self,config):
        self.config=config;self.ledger=None;self.status={'state':'indexing','scanned_at':0,'errors':[]};self.revision=0;self.lock=threading.Lock();self.refresh=threading.Event();self.stop=threading.Event();self.cache={}
    def watch(self):
        db=connect(self.config['db']);previous_library=None
        while not self.stop.is_set():
            try:
                report=scan(db,config=self.config)
                library=Path(self.config['library']) if self.config.get('library') else None
                signature=tuple((p.name,p.stat().st_mtime_ns) for p in library.glob('*.json')) if library and library.exists() else ()
                if report['changed'] or self.ledger is None or self.refresh.is_set() or signature!=previous_library:
                    ledger=Ledger(db,library)
                    with self.lock:self.ledger=ledger;self.revision+=1;self.cache={}
                    previous_library=signature
                self.status=dict(report,state='ready',revision=self.revision)
            except Exception as e:
                self.status=dict(self.status,state='error',errors=[str(e)])
                traceback.print_exc()
            self.refresh.clear();self.refresh.wait(self.config.get('interval',5))
        db.close()
    def snapshot(self,filters):
        # Cache only within a short interval: rolling windows must expire while idle.
        key=(tuple(sorted(filters.items())),int(time.time()//5),self.revision)
        with self.lock:
            ledger=self.ledger
            if key in self.cache:return self.cache[key]
        if ledger is None:return None
        result=ledger.summary(**filters)
        from .coaching import playbook
        result['coaching']=playbook(result)
        with self.lock:
            if len(self.cache)>30:self.cache={}
            self.cache[key]=result
        return result

def filters(query):
    hours=query.get('hours',['168'])[0]
    if hours=='today':
        from datetime import datetime
        now=datetime.now();hours=(now-now.replace(hour=0,minute=0,second=0,microsecond=0)).total_seconds()/3600
    elif hours in ('all',''):hours=None
    else:hours=max(0,min(float(hours),24*365*20))
    provider=query.get('provider',['all'])[0]
    from .adapters import NAME
    if not NAME.fullmatch(provider):raise ValueError('Invalid provider')
    return dict(hours=hours,provider=provider,topic=query.get('topic',['all'])[0])

def handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):pass
        def headers_common(self):
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Cache-Control','no-store');self.send_header('Cross-Origin-Resource-Policy','same-origin')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        def valid_host(self):
            return self.headers.get('Host','') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        def send(self,value,status=200,ctype='application/json; charset=utf-8',filename=None):
            data=json.dumps(value,ensure_ascii=False).encode() if ctype.startswith('application/json') else value.encode() if isinstance(value,str) else value
            self.send_response(status);self.headers_common();self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
            if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            if not self.valid_host():return self.send({'error':'Loopback Host required'},403)
            p=urlparse(self.path);q=parse_qs(p.query)
            try:
                if p.path=='/api/status':return self.send(dict(state.status,library_enabled=bool(state.config.get('library')),demo=bool(state.config.get('demo'))))
                if p.path.startswith('/api/'):
                    l=state.ledger
                    if l is None:return self.send({'error':'Initial indexing in progress'},503)
                    if p.path=='/api/summary':return self.send(state.snapshot(filters(q)))
                    if p.path=='/api/session':
                        result=l.detail(q.get('id',[''])[0],**filters(q))
                        return self.send(result if result else {'error':'Unknown session'},200 if result else 404)
                    if p.path=='/api/lineage':return self.send(l.lineage())
                    if p.path=='/api/playbook':
                        from .coaching import markdown
                        kind=q.get('format',['memory'])[0]
                        if kind not in ('memory','skill'):raise ValueError('format must be memory or skill')
                        return self.send(markdown(state.snapshot(filters(q)),kind),ctype='text/markdown; charset=utf-8',filename='SKILL.md' if kind=='skill' else 'token-efficiency-feedback.md')
                    if p.path in ('/api/report','/api/diagnosis'):
                        personal=Path(state.config['db']).parent/'diagnosis.md'
                        if p.path=='/api/diagnosis' and personal.is_file():body=personal.read_text()
                        else:
                            from .report import markdown
                            body=markdown(l,state.snapshot(filters(q)))
                        return self.send(body,ctype='text/markdown; charset=utf-8',filename='token-trail-diagnosis.md')
                    if p.path=='/api/export':
                        s=state.snapshot(filters(q));out=io.StringIO();writer=csv.writer(out)
                        writer.writerow(['date','input','cache_read','cache_write','fresh','output','reasoning_subset','total','requests'])
                        for row in s['daily']:writer.writerow([row['date']]+[row[k] for k in ('input','cache_read','cache_write','fresh','output','reasoning','total','requests')])
                        return self.send(out.getvalue(),ctype='text/csv; charset=utf-8',filename='token-trail-daily.csv')
                    if p.path=='/api/share':
                        s=state.snapshot(filters(q))
                        # Explicit allowlist: no IDs, titles, paths, topics, tool arguments or prompts.
                        return self.send(dict(product='Token Trail',period_hours=s['hours'],totals=s['totals'],providers=s['providers'],
                                              linked_child_share=s['coverage']['child_tokens']/max(1,s['totals']['total']),
                                              note='Provider-reported token volume, not an invoice or measured waste.'),filename='token-trail-share.json')
                    return self.send({'error':'Unknown API route'},404)
                name=p.path.lstrip('/') or 'index.html';target=(WEB/unquote(name)).resolve()
                if WEB.resolve() not in target.parents or not target.is_file():return self.send({'error':'Not found'},404)
                return self.send(target.read_bytes(),ctype=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
            except (ValueError,TypeError) as e:return self.send({'error':str(e)},400)
        def do_POST(self):
            if not self.valid_host():return self.send({'error':'Loopback Host required'},403)
            expected=f'http://{self.headers.get("Host","")}'
            if self.headers.get('Origin')!=expected or self.headers.get('X-Token-Trail')!='local':return self.send({'error':'Same-origin dashboard request required'},403)
            if self.headers.get_content_type()!='application/json':return self.send({'error':'JSON required'},415)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length>8192:return self.send({'error':'Request too large'},413)
                body=json.loads(self.rfile.read(length) or b'{}')
                if self.path=='/api/link':
                    child=body.get('child');parent=body.get('parent') or '';l=state.ledger
                    if child not in l.sessions or (parent and parent not in l.sessions):raise ValueError('Unknown session')
                    node=parent;visited={child}
                    while node:
                        if node in visited:raise ValueError('This relationship would create a cycle')
                        visited.add(node);node=l.sessions.get(node,{}).get('parent','')
                    db=connect(state.config['db'])
                    db.execute('INSERT INTO overrides VALUES(?,?,?,?) ON CONFLICT(child) DO UPDATE SET parent=excluded.parent,reason=excluded.reason,updated_at=excluded.updated_at',
                               (child,parent,'User-confirmed parent' if parent else 'User-confirmed human root',time.time()));db.commit();db.close();state.refresh.set()
                    return self.send({'ok':True})
                if self.path=='/api/refresh':state.refresh.set();return self.send({'ok':True})
                return self.send({'error':'Unknown API route'},404)
            except (ValueError,TypeError,AttributeError) as e:return self.send({'error':str(e)},400)
    return Handler

def serve(config):
    state=State(config);server=ThreadingHTTPServer(('127.0.0.1',config.get('port',8765)),handler(state));server.daemon_threads=True
    thread=threading.Thread(target=state.watch,daemon=True);thread.start()
    print(f'Token Trail: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:state.stop.set();state.refresh.set();server.server_close();thread.join(timeout=15)
