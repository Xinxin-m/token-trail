"""Opt-in launch trace. Stores identifiers only; never captures stdin/stdout/prompts."""
import json,os,subprocess,sys,time,uuid,shlex
from .collector import connect,UUID

def event(config,value):
    db=connect(config['db']);db.execute('INSERT OR IGNORE INTO trace_events VALUES(?,?)',(str(uuid.uuid4()),json.dumps(value)));db.commit();db.close()

def hook(config,provider):
    try:
        d=json.load(sys.stdin);sid=d.get('session_id') or d.get('sessionId') or d.get('thread_id')
        if not sid:return
        parent=os.environ.get('TOKEN_TRAIL_PARENT','')
        if not parent:
            other='codex' if provider=='claude' else 'claude'
            keys=('CODEX_THREAD_ID','CODEX_SESSION_ID') if other=='codex' else ('CLAUDE_SESSION_ID','CLAUDE_CODE_SESSION_ID')
            inherited=next((os.environ[k] for k in keys if os.environ.get(k)),None)
            if inherited and inherited!=sid:parent=other+':'+inherited
        if not parent:
            current=os.environ.get('TOKEN_TRAIL_CURRENT','')
            if current and current!=provider+':'+sid:parent=current
        event(config,dict(kind='session_start',session=provider+':'+sid,parent=parent,run_id=os.environ.get('TOKEN_TRAIL_RUN_ID',''),ts=time.time()))
        # Claude's documented environment-file hook makes subsequent shell launches
        # inherit the current session automatically, without a prompt or model call.
        if provider=='claude' and os.environ.get('CLAUDE_ENV_FILE'):
            with open(os.environ['CLAUDE_ENV_FILE'],'a') as f:
                f.write('\nexport TOKEN_TRAIL_CURRENT='+shlex.quote('claude:'+sid)+'\nunset TOKEN_TRAIL_PARENT TOKEN_TRAIL_RUN_ID\n')
    except Exception:pass # A telemetry hook must never block the user's work.

def run(config,parent,argv):
    if argv and argv[0]=='--':argv=argv[1:]
    if not argv:raise SystemExit('Provide a command after --')
    if not parent.startswith(('claude:','codex:')):raise SystemExit('--parent must be claude:<session-id> or codex:<thread-id>')
    run_id=str(uuid.uuid4());env=os.environ.copy();env['TOKEN_TRAIL_PARENT']=parent;env['TOKEN_TRAIL_RUN_ID']=run_id
    event(config,dict(kind='launch',run_id=run_id,parent=parent,executable=os.path.basename(argv[0]),ts=time.time()))
    # No shell, no output capture, no model override. Preserve normal terminal IO.
    child=subprocess.Popen(argv,env=env)
    event(config,dict(kind='process',run_id=run_id,pid=child.pid,ts=time.time()))
    try:code=child.wait()
    except KeyboardInterrupt:
        child.send_signal(2);code=child.wait()
    event(config,dict(kind='exit',run_id=run_id,code=code,ts=time.time()))
    raise SystemExit(code)
