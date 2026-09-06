#!/usr/bin/env python3
"""Additive local installation with backups. Never changes model selection or source logs."""
import argparse,json,os,plistlib,shlex,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def write_with_backup(path,content):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        backup=path.with_name(path.name+'.token-trail-backup-'+str(time.time_ns()));shutil.copy2(path,backup)
        print('Backup:',backup)
    tmp=path.with_name(path.name+'.token-trail-tmp');tmp.write_bytes(content);os.chmod(tmp,0o600);os.replace(tmp,path)

def install_hook(path,provider,config):
    d=json.loads(path.read_text()) if path.exists() else {}
    command=shlex.join([sys.executable,'-m','token_trail','--config',str(config),'hook','--provider',provider])
    command='cd '+shlex.quote(str(ROOT))+' && '+command
    hooks=d.setdefault('hooks',{}).setdefault('SessionStart',[])
    matcher='startup|resume|clear|compact'
    for group in hooks:
        for entry in group.get('hooks',[]):
            if 'token_trail' in entry.get('command','') and 'hook' in entry.get('command',''):
                if group.get('matcher')!=matcher or entry.get('command')!=command:
                    group['matcher']=matcher;entry['command']=command
                    write_with_backup(path,(json.dumps(d,indent=2)+'\n').encode())
                print(provider,'hook ready');return
    hooks.append(dict(matcher=matcher,hooks=[dict(type='command',command=command,timeout=5)]))
    write_with_backup(path,(json.dumps(d,indent=2)+'\n').encode());print('Installed identifier-only SessionStart hook:',path)

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--service',action='store_true');p.add_argument('--hooks',action='store_true');a=p.parse_args();config=Path(a.config).resolve()
    if not config.is_file():raise SystemExit('Configuration file is missing')
    if a.hooks:
        install_hook(Path.home()/'.claude/settings.json','claude',config);install_hook(Path.home()/'.codex/hooks.json','codex',config)
    if a.service:
        log=Path(json.loads(config.read_text())['db']).parent/'service.log';log.parent.mkdir(parents=True,exist_ok=True)
        if sys.platform=='darwin':
            dest=Path.home()/'Library/LaunchAgents/local.token-trail.plist'
            body=dict(Label='local.token-trail',ProgramArguments=[sys.executable,'-m','token_trail','--config',str(config),'serve'],WorkingDirectory=str(ROOT),RunAtLoad=True,KeepAlive=True,ThrottleInterval=10,StandardOutPath=str(log),StandardErrorPath=str(log),EnvironmentVariables={'PYTHONUNBUFFERED':'1'})
            write_with_backup(dest,plistlib.dumps(body));print('Service created:',dest);print('Start: launchctl bootstrap gui/'+str(os.getuid())+' '+shlex.quote(str(dest)))
        elif sys.platform.startswith('linux'):
            dest=Path.home()/'.config/systemd/user/token-trail.service'
            body='[Unit]\nDescription=Token Trail local collector\n[Service]\nWorkingDirectory='+str(ROOT)+'\nExecStart='+shlex.join([sys.executable,'-m','token_trail','--config',str(config),'serve'])+'\nRestart=on-failure\n[Install]\nWantedBy=default.target\n'
            write_with_backup(dest,body.encode());print('Service created:',dest);print('Start: systemctl --user daemon-reload && systemctl --user enable --now token-trail')
        else:raise SystemExit('Automatic service installation supports macOS and Linux; use the serve command on Windows.')
if __name__=='__main__':main()
