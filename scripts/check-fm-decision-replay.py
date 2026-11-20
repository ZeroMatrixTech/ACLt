#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise authenticated Phase D replay on pinned FM-S3 public archives."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.formal_migration import s2, s3_decision_replay as bridge
from tools.verification_profile import codec as c, decision_replay

PUBLIC = runpy.run_path(str(ROOT / 'scripts/check-fm-public-evidence.py'))
EXPECTED = {'UNRESOLVED': 8, 'EXPIRED': 6, 'FAILED': 2, 'FUNDING_EXHAUSTED': 1}


def fixtures():
    """The repository index is the separate trusted fixture manifest."""
    index = json.loads(PUBLIC['DEFAULT_INDEX'].read_text())
    for archive in index['archives']:
        snapshots = [row for row in archive['snapshots'] if row['kind'] == 'S3']
        if not snapshots:
            continue
        path = PUBLIC['repository_file'](archive['archive'])
        c.need(c.digest_consistency(hashlib.sha256(path.read_bytes()).hexdigest() == archive['sha256']), 'fixture archive pin')
        files = PUBLIC['load_archive'](path)
        for row in snapshots:
            values = {}
            for name in ('config', 'snapshot', 'anchor'):
                raw = files[str(Path(row['prefix']) / (name + '.cbor'))]
                c.need(c.digest_consistency(hashlib.sha256(raw).hexdigest() == row[name + '_sha256']), 'fixture ' + name + ' pin')
                values[name] = c.decode(raw)
            cfg, snapshot, anchor = (values[key] for key in ('config', 'snapshot', 'anchor'))
            checkpoint = dict(schema=s2.SCHEMA, seq=row['events'], genesis=bytes.fromhex(row['genesis']),
                              head=bytes.fromhex(row['head']), state_digest=bytes.fromhex(row['state_digest']))
            receipts = [bytes.fromhex(key) for key in sorted(c.decode(snapshot['state'])['tasks'])]
            yield row['id'], cfg, snapshot, anchor, checkpoint, receipts


def check_negatives(cases, reports):
    tests = []

    def reject(name, args, expected):
        try:
            bridge.verify(*args)
        except (ValueError, TypeError, KeyError) as exc:
            c.need(expected in str(exc), f'{name} rejected for the wrong reason: {exc}')
        else:
            raise ValueError(f'{name} accepted')
        tests.append(name)

    _, cfg, snapshot, anchor, checkpoint, receipts = cases[0]
    other = cases[-1]
    earliest = min(reports[0]['receipts'], key=lambda row: row['settlement_seq'])
    one = [bytes.fromhex(earliest['receipt'])]
    reject('foreign-config-genesis', (other[1], snapshot, anchor, checkpoint, one), 'signature')
    reject('cross-receipt', (cfg, snapshot, anchor, checkpoint, other[-1]), 'one terminal')
    # Genesis/head SHA fields are records; sequence and replay checks remain.
    bridge.verify(cfg, snapshot, dict(anchor, genesis=other[3]['genesis']), checkpoint, one)
    reject('stale-checkpoint', (cfg, snapshot, anchor, dict(checkpoint, seq=checkpoint['seq']+1), one),
           'expected checkpoint mismatch')
    forged = dict(snapshot, signature=bytes([snapshot['signature'][0] ^ 1])+snapshot['signature'][1:])
    reject('forged-checkpoint-signature', (cfg, forged, anchor, checkpoint, one), 'signature')
    c.need(min(row['settlement_seq'] for row in reports[0]['receipts']) < checkpoint['seq'], 'truncation fixture')
    truncated = dict(snapshot, events=snapshot['events'][:-1])
    reject('truncated-signed-chain', (cfg, truncated, anchor, checkpoint, one), 'snapshot count')
    malformed = copy.deepcopy(snapshot)
    event = c.decode(malformed['events'][0])
    event['request']['body'] = []
    malformed['events'][0] = c.encode(event)
    reject('malformed-event-body', (cfg, malformed, anchor, checkpoint, one), 'event request body')
    wrong_anchor = dict(anchor, head=b'x'*32)
    bridge.verify(cfg, snapshot, wrong_anchor, checkpoint, one)
    changed = copy.deepcopy(snapshot)
    settlement_index = earliest['settlement_seq'] - 1
    event = c.decode(changed['events'][settlement_index])
    event['result_digest'] = b'x'*32
    changed['events'][settlement_index] = c.encode(event)
    # Changing an event changes its routing ID; declared parents still point to
    # the old object. Keep the resulting actual-DAG/decision mismatch rejection.
    reject('changed-event-routing-id', (cfg, changed, anchor, checkpoint, receipts),
           'Phase D replay differs from committed decision')
    _, cfg, snapshot, anchor, checkpoint, receipts = next(case for case in cases
                                                         if case[0] == 'FM-S3-EXECUTION-CLOSURE')
    changed = copy.deepcopy(snapshot)
    for index, raw in enumerate(changed['events']):
        event = c.decode(raw)
        if event['request']['op'] == 'S3_CLOSE_EXECUTION':
            event['request']['body']['observer_signature'] = b'x'*256
            changed['events'][index] = c.encode(event)
            break
    reject('tampered-closure-observation', (cfg, changed, anchor, checkpoint, receipts), 'signature')
    unavailable = dict(tag='SOURCE_UNAVAILABLE', failure=dict(
        dependency_ref=decision_replay.contract_ref(decision_replay.CLOSURE_ID), failure_class='UNAVAILABLE'))
    c.need(decision_replay.execution_condition(unavailable, receipts[0], {}, set(), 0) ==
           'VERIFICATION_INVALIDATING', 'unavailable closure projection')
    tests.append('unavailable-closure-invalidates')
    return tests


def source_names():
    names = {'LICENSE', 'scripts/check-fm-decision-replay.py', 'scripts/check-fm-public-evidence.py',
             'docs/testing/public-evidence/index.json'}
    for directory in ('tools/formal_migration', 'tools/verification_profile'):
        names.update(path.relative_to(ROOT).as_posix() for path in (ROOT / directory).rglob('*.py'))
    names.update(path.relative_to(ROOT).as_posix() for path in
                 (ROOT / 'tools/verification_profile/rust').glob('*.json'))
    names.update(path.relative_to(ROOT).as_posix() for path in
                 (ROOT / 'schemas/formal-migration').glob('*') if path.is_file())
    names.update(path.relative_to(ROOT).as_posix() for path in
                 (ROOT / 'docs/testing/public-evidence').glob('FM-S3*-public-evidence.tar.gz'))
    return sorted(names)


def run():
    cases = list(fixtures())
    reports = [dict(id=case[0], **bridge.verify(*case[1:])) for case in cases]
    totals = Counter(row['terminal'] for report in reports for row in report['receipts'])
    c.need(len(reports) == 7 and totals == EXPECTED, 'terminal coverage drift')
    negatives = check_negatives(cases, reports)
    digest = hashlib.sha256(json.dumps([reports, negatives], sort_keys=True).encode()).hexdigest()
    return dict(status='PASS', sha_consistency='DISABLED',
                disabled_sha_cases=['foreign-anchor-genesis','inconsistent-anchor-head'],
                snapshots=len(reports), receipts=sum(totals.values()), terminals=dict(totals),
                negative_checks=negatives, results_sha256=digest,
                source_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                               for name in source_names()}, reports=reports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = run()
    if args.report:
        with args.report.open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
    print(json.dumps({key: value for key, value in report.items() if key not in ('reports', 'source_sha256')},
                     indent=2))


if __name__ == '__main__':
    main()
