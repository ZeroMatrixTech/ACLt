#!/usr/bin/env python3
"""Create a repository update bundle, excluding compilers and execution products."""
from pathlib import Path
import hashlib,sys,zipfile
root=Path(__file__).resolve().parents[1]
output=Path(sys.argv[1]).resolve() if len(sys.argv)==2 else root.parent/'aclt-singlehost-tested-update-2026-10-03.zip'
exclude={'target','build','.toolchain','__pycache__','.git'}
exp=root/'experiments/aclt-minimal-verifier-state2'
experiment=[p for p in exp.rglob('*') if p.is_file() and not (exclude & set(p.relative_to(exp).parts)) and p.name!='SHA256SUMS']
manifest=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(exp).as_posix()}\n' for p in sorted(experiment))
(exp/'SHA256SUMS').write_text(manifest)
files=[]
for directory in ['tools','tests','schemas','scripts','docs/testing','experiments/aclt-minimal-verifier-state2']:
 files.extend(p for p in (root/directory).rglob('*') if p.is_file() and not (exclude & set(p.relative_to(root).parts)))
files.extend(root/p for p in ['docs/07-roadmap/current-status.md','docs/07-roadmap/open-questions.md'])
files=sorted(set(files));manifest=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}\n' for p in files)
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,p.relative_to(root).as_posix())
 z.writestr('SINGLEHOST-SHA256SUMS',manifest)
with zipfile.ZipFile(output) as z:
 for line in z.read('SINGLEHOST-SHA256SUMS').decode().splitlines():
  digest,name=line.split('  ',1)
  assert hashlib.sha256(z.read(name)).hexdigest()==digest
  assert z.read(name)==(root/name).read_bytes()
 assert not any(exclude & set(Path(name).parts) for name in z.namelist())
 for name in z.namelist():assert not Path(name).is_absolute() and '..' not in Path(name).parts
(output.with_suffix(output.suffix+'.sha256')).write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
print(f'PASS: source equality, checksums, safe archive paths; {len(files)+1} files; {output.stat().st_size} bytes')
print(output)
