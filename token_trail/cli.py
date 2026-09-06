import argparse,json,os,sys,time
from pathlib import Path
from .collector import connect,scan
from .analysis import Ledger

def defaults(args):
    cfg={}
    if args.config:
        cfg=json.loads(Path(args.config).expanduser().read_text())
    base=Path(os.environ.get('TOKEN_TRAIL_DATA',str(Path.home()/'.local/share/token-trail'))).expanduser()
    return dict(db=str(base/'ledger.sqlite'),claude_root='~/.claude/projects',codex_root='~/.codex/sessions',library='',port=8765,interval=5) | cfg

def main():
    p=argparse.ArgumentParser(description='Token Trail: local, zero-LLM token observability for Claude Code and Codex.')
    p.add_argument('--config',help='Local JSON configuration file')
    sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('serve');s.add_argument('--port',type=int)
    sub.add_parser('scan')
    r=sub.add_parser('report');r.add_argument('--hours',type=float);r.add_argument('--json',action='store_true')
    sub.add_parser('doctor')
    a=sub.add_parser('advise');a.add_argument('--session',required=True)
    hook=sub.add_parser('hook');hook.add_argument('--provider',choices=['claude','codex'],required=True)
    run=sub.add_parser('run',help='Trace a cross-provider launch without changing its model');run.add_argument('--parent',required=True);run.add_argument('argv',nargs=argparse.REMAINDER)
    sub.add_parser('demo')
    args=p.parse_args();config=defaults(args)
    if args.command=='serve':
        from .server import serve
        if args.port:config['port']=args.port
        serve(config);return
    if args.command in ('hook','run'):
        from .trace import hook,run
        return hook(config,args.provider) if args.command=='hook' else run(config,args.parent,args.argv)
    if args.command=='advise':
        from .guard import advise
        print(json.dumps(advise(config,args.session),indent=2));return
    if args.command=='demo':
        from .demo import seed
        seed(config);return
    db=connect(config['db'])
    if args.command=='scan':print(json.dumps(scan(db,config['claude_root'],config['codex_root']),indent=2));return
    if args.command=='doctor':
        result=dict(python=sys.version.split()[0],database=config['db'],cached_files=db.execute('SELECT count(*) FROM files').fetchone()[0],
                    sources={k:str(Path(config[k]).expanduser()) for k in ('claude_root','codex_root')},
                    source_exists={k:Path(config[k]).expanduser().exists() for k in ('claude_root','codex_root')},
                    library_available=bool(config['library'] and Path(config['library']).expanduser().exists()),network='loopback only',model_calls=0)
        print(json.dumps(result,indent=2));return
    ledger=Ledger(db,config.get('library'));summary=ledger.summary(hours=args.hours)
    if args.json:print(json.dumps(summary,indent=2));return
    from .report import markdown
    print(markdown(ledger,summary))
