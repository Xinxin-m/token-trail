"""Small deterministic inventory of instruction entry points, deduplicated by real path."""
import hashlib
from pathlib import Path

def audit(paths):
    found={};errors=[]
    for name in paths:
        p=Path(name).expanduser()
        candidates=sorted(p.glob('*/SKILL.md')) if p.is_dir() else [p]
        for candidate in candidates:
            try:
                real=candidate.resolve(strict=True)
                if real in found:
                    found[real]['aliases'].append(str(candidate));continue
                text=real.read_text(encoding='utf-8')
                found[real]=dict(path=str(real),aliases=[str(candidate)],characters=len(text),estimated_tokens=(len(text)+3)//4,
                                sha256=hashlib.sha256(text.encode()).hexdigest(),
                                sections=[line[3:].strip() for line in text.splitlines() if line.startswith('## ')],
                                vendor_managed=('/plugins/cache/' in str(real) or '/skills/.system/' in str(real)),
                                suggestion='Consider routing task-specific sections into references; retain invariant rules in the entry point.' if len(text)>6000 else 'Keep concise; no size-based rewrite needed.')
            except (OSError,UnicodeError) as e:errors.append(dict(path=str(candidate),error=str(e)))
    return dict(files=sorted(found.values(),key=lambda r:r['characters'],reverse=True),errors=errors,
                note='Characters/4 is a rough text estimate, not measured billing. Files are read once each by code. No model calls and no edits.')
