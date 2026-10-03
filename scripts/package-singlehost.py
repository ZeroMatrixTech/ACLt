#!/usr/bin/env python3
"""Create a repository update bundle, excluding compilers and execution products."""
from pathlib import Path
import hashlib,sys,zipfile,subprocess
root=Path(__file__).resolve().parents[1]
output=Path(sys.argv[1]).resolve() if len(sys.argv)==2 else root.parent/'aclt-singlehost-tested-update-2026-10-03.zip'
exclude={'target','build','.toolchain','__pycache__','.git'}
subprocess.run([sys.executable,str(root/'scripts/update-manifests.py')],check=True)
manifest=(root/'SINGLEHOST-SHA256SUMS').read_text()
files=[root/line.split('  ',1)[1] for line in manifest.splitlines()]
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,p.relative_to(root).as_posix())
 z.writestr('SINGLEHOST-SHA256SUMS',manifest)
with zipfile.ZipFile(output) as z:
 for line in z.read('SINGLEHOST-SHA256SUMS').decode().splitlines():
  digest,name=line.split('  ',1)
  assert hashlib.sha256(z.read(name)).hexdigest()==digest
  assert z.read(name)==(root/name).read_bytes()
 for name in z.namelist():
  blocked=exclude-{'build'} if name.startswith('docs/workflow/example/') else exclude
  assert not blocked & set(Path(name).parts)
 for name in z.namelist():assert not Path(name).is_absolute() and '..' not in Path(name).parts
(output.with_suffix(output.suffix+'.sha256')).write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
print(f'PASS: source equality, checksums, safe archive paths; {len(files)+1} files; {output.stat().st_size} bytes')
print(output)
