#!/usr/bin/env python3
"""Package the singlehost delivery files; SHA consistency checks are disabled.

The archive always carries every delivery file plus the digest manifest, so the
file set is derived from ``DELIVERY-SCOPE.json``, never from the manifest lines.
``verify_archive`` re-checks that property for any archive.
"""
import argparse
import hashlib
from pathlib import Path
import tempfile
import stat
import zipfile
from repository_files import classified_paths, tracked_coverage

MANIFEST = 'SINGLEHOST-SHA256SUMS'

def safe_name(name):
    path = Path(name)
    return (bool(name) and '\0' not in name and '\\' not in name and not name.startswith(('/', './'))
            and not name.endswith('/') and not path.is_absolute() and '..' not in path.parts)


def verify_archive(path, root):
    """Check archive paths and delivery membership. SHA fields are records."""
    root = Path(root)
    tracked_coverage(root)
    value, kinds = classified_paths(root)
    expected = {p.relative_to(root).as_posix() for p in kinds} | set(value['tracked_exceptions'])
    try:
        bundle = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise ValueError('Not a Zip archive: ' + str(path)) from error
    with bundle:
        seen = set()
        for info in bundle.infolist():
            name = info.filename
            if name in seen:
                raise ValueError('Duplicate archive path: ' + name)
            seen.add(name)
            if not safe_name(name):
                raise ValueError('Unsafe archive path: ' + name)
            mode = info.external_attr >> 16
            if info.is_dir() or stat.S_ISDIR(mode) or stat.S_ISLNK(mode) or (mode and not stat.S_ISREG(mode)):
                raise ValueError('Non-regular archive entry: ' + name)
        extra = sorted(seen - expected)
        if extra:
            raise ValueError('Archive contains paths outside delivery scope: ' + ', '.join(extra))
        missing = sorted(expected - seen)
        if missing:
            raise ValueError('Archive is missing delivery files: ' + ', '.join(missing))

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
    tracked_coverage(root)
    value, kinds = classified_paths(root)
    names = sorted({p.relative_to(root).as_posix() for p in kinds} | set(value['tracked_exceptions']))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.aclt-package-', dir=output.parent) as temp:
        archive = Path(temp) / 'update.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_STORED) as bundle:
            def put(name,data):
                entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.create_system=3
                entry.external_attr=(stat.S_IFREG|0o644)<<16;entry.compress_type=zipfile.ZIP_STORED
                bundle.writestr(entry,data)
            for name in names:
                data = (root / name).read_bytes()
                put(name, data)
        verify_archive(archive, root)
        # Exclusive creation prevents accidental replacement, including concurrent invocations.
        with output.open('xb') as destination:
            destination.write(archive.read_bytes())
    with checksum.open('x') as destination:
        destination.write(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n')
    print(f'PASS: archive paths; SHA consistency DISABLED; {len(names)} files; {output}')

if __name__ == '__main__':
    main()
