"""Explicit local onboarding. Never rewrites an existing skill or configuration."""
import json, os, shutil, sys
from pathlib import Path
from .adapters import sources

def initialize(config,output,requested=None):
    path=Path(output).expanduser().resolve()
    detected=sources(config)
    if requested:
        detected=[]
        for item in requested:
            adapter,sep,root=item.partition('=')
            if not sep:raise ValueError('--source requires adapter=path')
            detected.append(dict(adapter=adapter,path=str(Path(root).expanduser().resolve())))
        sources({'sources':detected})
    else:detected=[dict(s,path=str(Path(s['path']).expanduser().resolve())) for s in detected if Path(s['path']).expanduser().exists()]
    value=dict(db=str(Path(config['db']).expanduser().resolve()),sources=detected,port=config.get('port',8765),interval=5,library='')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    try:os.chmod(path,0o600)
    except OSError:pass
    return dict(config=str(path),sources=detected,next=['python','-m','token_trail','--config',str(path),'serve'])

def install_skill(target=None,path=None):
    homes={'claude':Path.home()/'.claude/skills','codex':Path.home()/'.codex/skills'}
    dest=Path(path).expanduser().resolve() if path else homes[target]/'token-trail'
    if dest.exists():raise ValueError(f'{dest} already exists; review it before installing an update')
    template=Path(__file__).parent/'skill'
    shutil.copytree(template,dest)
    # The tiny runner preserves the installer interpreter and installed/check-out location.
    # Only this local copy contains machine paths. Public template remains portable.
    runtime=Path(__file__).resolve().parent.parent
    runner=dest/'scripts/trail.py';runner.parent.mkdir(exist_ok=True)
    runner.write_text('import os, sys\nos.environ["PYTHONPATH"] = '+repr(str(runtime))+'\nos.execv('+repr(sys.executable)+', ['+repr(sys.executable)+', "-m", "token_trail", *sys.argv[1:]])\n',encoding='utf-8')
    return dict(installed=str(dest),command=f'python "{runner}" doctor',model_calls=0)
