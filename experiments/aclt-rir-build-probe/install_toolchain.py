# SPDX-License-Identifier: Apache-2.0
"""Offline installation of the three SHA-pinned official component archives."""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--downloads', type=Path, required=True)
    p.add_argument('--prefix', type=Path, required=True)
    a = p.parse_args()
    prefix = a.prefix.resolve()
    scratch = prefix.with_name(prefix.name + '.unpacked')
    if prefix.exists() or scratch.exists():
        p.error('prefix and adjacent .unpacked directory must both be new')
    lock = json.loads(Path(__file__).with_name('toolchain-lock.json').read_text())
    for component in lock['components']:
        archive = a.downloads / component['file']
        if hashlib.sha256(archive.read_bytes()).hexdigest() != component['sha256']:
            raise ValueError('archive pin mismatch: ' + str(archive))
    prefix.parent.mkdir(parents=True, exist_ok=True)
    scratch.mkdir()
    for component in lock['components']:
        archive = a.downloads / component['file']
        with tarfile.open(archive) as tar:
            tar.extractall(scratch, filter='data')
        installer = scratch / component['file'].removesuffix('.tar.xz') / 'install.sh'
        result = subprocess.run(['bash', str(installer), '--prefix=' + str(prefix), '--disable-ldconfig'], capture_output=True, text=True)
        (scratch / (component['file'] + '.install.log')).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('installation failed; retained logs in ' + str(scratch))
    for name, expected in {**lock['binaries'], **lock['target_libraries']}.items():
        if hashlib.sha256((prefix / name).read_bytes()).hexdigest() != expected:
            raise ValueError('installed toolchain mismatch: ' + name)
    print('PASS: offline pinned toolchain installed; system Rust unchanged')


if __name__ == '__main__':
    main()
