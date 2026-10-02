#!/usr/bin/env python3
"""Package only reviewed source/documentation paths, never local build tools."""
import hashlib
import pathlib
import sys
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
output = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else root.parent/'aclt-single-pc-2026-10-02.zip'
files = [root/name for name in ('.gitignore','Cargo.toml','Cargo.lock','README.md')]
for directory in ('src','cpp','scripts','examples','docs'):
    files += [p for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
files = sorted(files)
prefix = 'experiments/aclt-minimal-verifier/'
manifest = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}\n' for p in files)
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path,prefix+path.relative_to(root).as_posix())
    archive.writestr(prefix+'SHA256SUMS',manifest)
digest = hashlib.sha256(output.read_bytes()).hexdigest()
output.with_suffix(output.suffix+'.sha256').write_text(f'{digest}  {output.name}\n')
print(f'{output.name}: {len(files)+1} files, {output.stat().st_size} bytes')
print(f'SHA256 {digest}')
