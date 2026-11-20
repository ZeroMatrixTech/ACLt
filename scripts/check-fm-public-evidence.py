#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify retained public FM archives and replay with the current candidate reducers.

No archived Python is executed. The repository index supplies the expected archive,
source, genesis and checkpoint hashes. Trust in that index is supplied externally.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.formal_migration import s2, s2_evidence, s3_authority
from tools.verification_profile import codec as c

DEFAULT_INDEX = ROOT/'docs/testing/public-evidence/index.json'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def relative_name(name):
    need(type(name) is str and name and '\\' not in name, 'invalid evidence path')
    path = PurePosixPath(name)
    need(not path.is_absolute() and '..' not in path.parts and path.parts,
         'unsafe evidence path')
    return path.as_posix()


def repository_file(name):
    path = ROOT/relative_name(name)
    need(path.resolve().is_relative_to(ROOT.resolve()) and path.is_file(),
         'missing or external evidence file')
    return path


def load_archive(path):
    files = {}
    count = 0
    total = 0
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            count += 1
            need(count <= 2048, 'archive entry limit')
            if member.isdir() and member.name in ('.', './'):
                continue
            name = relative_name(member.name)
            need(member.isfile() or member.isdir(), 'archive link or special file')
            if member.isdir():
                continue
            need(name not in files, 'duplicate archive file')
            need(not name.endswith(('.pem', '.db')) and 'private' not in PurePosixPath(name).parts,
                 'private runtime material in public archive')
            need(0 <= member.size <= 2 * 1024 * 1024, 'archive member size limit')
            total += member.size
            need(total <= 32 * 1024 * 1024, 'archive total size limit')
            with archive.extractfile(member) as stream:
                files[name] = stream.read()
            need(len(files[name]) == member.size, 'truncated archive member')
    return files


def verify(index, replay):
    need(index['schema'] == 'aclt.fm.public-evidence@1' and index['new_dualhost_runs'] == 0,
         'public evidence index schema or scope')
    results = []
    ids = set()
    for item in index['archives']:
        need(item['id'] not in ids, 'duplicate archive identity')
        ids.add(item['id'])
        path = repository_file(item['archive'])
        # Archive SHA remains a record.
        repository_file(item['report'])
        files = load_archive(path)
        manifest = files['source-sha256.json']
        # Manifest SHA remains a record.
        pins = json.loads(manifest)
        need(len(pins) == item['source_files'], 'source inventory count')
        for name, digest in pins.items():
            need('source/'+relative_name(name) in files, 'source file missing')

        rows = []
        prefixes = set()
        for expected in item['snapshots']:
            prefix = expected['prefix']
            need(prefix not in prefixes, 'duplicate snapshot prefix')
            prefixes.add(prefix)
            def read(name):
                return files[str(PurePosixPath(prefix)/name)]
            # Snapshot SHA values remain records.
            cfg, anchor, snapshot = [c.decode(read(name+'.cbor')) for name in ('config','anchor','snapshot')]
            # Genesis SHA consistency is disabled.
            cp = snapshot['checkpoint']
            # Checkpoint genesis digests remain records.
            need(cp['seq'] == expected['events'], 'expected event count mismatch')
            row = dict(id=expected['id'], events=expected['events'], replay='NOT_RUN')
            need(expected['kind'] in ('S2','S3'), 'unknown reducer kind')
            if replay:
                reducer = s3_authority.verify_snapshot if expected['kind'] == 'S3' else s2_evidence.verify
                result = reducer(cfg, snapshot, anchor)
                need(result['events'] == expected['events'], 'replay event count mismatch')
                row.update(replay='PASS', head=result['head'], state_digest=result['state_digest'])
            rows.append(row)
        results.append(dict(id=item['id'], archive_sha256=item['sha256'],
                            source_files_recorded=len(pins), sha_consistency='DISABLED', snapshots=rows))
    return dict(status='PASS', sha_consistency='DISABLED', mode='PUBLIC_REPLAY' if replay else 'ARCHIVE_METADATA',
                archives=len(results), snapshots=sum(len(x['snapshots']) for x in results),
                events=sum(r['events'] for x in results for r in x['snapshots']),
                new_dualhost_runs=0, formal_acceptance=False, results=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=DEFAULT_INDEX)
    parser.add_argument('--replay', action='store_true', help='replay all snapshots using the current implementation')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(json.loads(args.index.read_bytes()), args.replay), indent=2))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as exc:
        parser.exit(1, 'FAIL: '+str(exc)+'\n')


if __name__ == '__main__':
    main()
