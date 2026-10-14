#!/usr/bin/env python3
"""Package the singlehost update only after its manifests have been reviewed."""
import argparse
import hashlib
from pathlib import Path
import tempfile
import zipfile
from repository_files import verify

def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path,
                        default=root / 'dist/aclt-singlehost-update.zip')
    args = parser.parse_args()
    output = args.output.resolve()
    checksum = output.with_suffix(output.suffix + '.sha256')
    if output.exists() or checksum.exists():
        parser.error('Output already exists; choose a new filename')
    errors = verify(root)
    if errors:
        parser.error('Stale manifests: ' + ', '.join(errors) + '; review and run make manifests')
    source = (root / 'SINGLEHOST-SHA256SUMS').read_text()
    entries = [line.split('  ', 1) for line in source.splitlines()]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.aclt-package-', dir=output.parent) as temp:
        archive = Path(temp) / 'update.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for digest, name in entries:
                path = Path(name)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unsafe archive path: ' + name)
                data = (root / path).read_bytes()
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError('Source changed while packaging: ' + name)
                bundle.writestr(name, data)
            bundle.writestr('SINGLEHOST-SHA256SUMS', source)
        with zipfile.ZipFile(archive) as bundle:
            for digest, name in entries:
                if hashlib.sha256(bundle.read(name)).hexdigest() != digest:
                    raise ValueError('Archive checksum mismatch: ' + name)
        # Exclusive creation prevents accidental replacement, including concurrent invocations.
        with output.open('xb') as destination:
            destination.write(archive.read_bytes())
    with checksum.open('x') as destination:
        destination.write(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n')
    print(f'PASS: verified archive; {len(entries) + 1} files; {output}')

if __name__ == '__main__':
    main()
