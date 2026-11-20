#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay versioned Phase B/D test envelopes through the pinned FM-S3 registry."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import socket
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
R13 = runpy.run_path(str(ROOT / 'scripts/check-phase-d-crosscheck.py'))
R11 = R13['R12']['R11']
from tools.formal_migration import phase_d_envelope as envelope
from tools.verification_profile import codec as c

REGISTRY = ROOT / 'tests/formal_migration/phase-d-envelope-registry.cbor'
VECTORS = ROOT / 'tests/formal_migration/phase-d-envelope-vectors.json'


SHA_RECORD_CASES = frozenset({'external-registry-pin','external-registry-pin-omitted','configuration-under-test-pin',
                              'anchor-under-test-pin','source-contract-sha-record',
                              'phase_d-phase_b_digest','phase_d-source_digest'})


def fixture_registry(cases):
    """Reproduce the retained registry from the repository's pinned fixture index."""
    deployments = {}
    for _, config, snapshot, anchor, checkpoint, receipts in cases:
        report = R11['bridge'].verify(config, snapshot, anchor, checkpoint, receipts)
        profiles = [bytes.fromhex(row['profile']) for row in report['receipts']]
        genesis = checkpoint['genesis'].hex()
        c.need(genesis not in deployments, 'duplicate fixture deployment')
        deployments[genesis] = envelope.registry_entry(config, anchor, checkpoint, profiles)
    return c.encode(dict(version=envelope.VERSION, deployments=deployments))


def check_negatives(fixture, registry, pin):
    value, receipts = fixture
    checks = []

    def reject(name, message, *, wire=None, new_registry=registry, new_pin=pin, selected=receipts):
        try:
            envelope.verify(c.encode(value if wire is None else wire), new_registry, new_pin, selected)
        except c.CodecError as exc:
            c.need(message in str(exc), f'{name}: {exc}')
        else:
            raise c.CodecError(f'{name} accepted')
        checks.append(name)

    def accept_record(name, *, wire=None, new_registry=registry, new_pin=pin):
        c.need(name in SHA_RECORD_CASES, 'reviewed SHA record case')
        report = envelope.verify(c.encode(value if wire is None else wire), new_registry, new_pin, receipts)
        c.need(report['status'] == 'PASS', name + ': actual replay failed')

    accept_record('external-registry-pin', new_pin=b'x' * 32)
    accept_record('external-registry-pin-omitted', new_pin=None)
    reject('cross-version', 'envelope version', wire=dict(value, version='ACLt/1'))
    reject('missing-receipt', 'envelope receipt count', wire=dict(value, records=[]))
    reject('duplicate-receipt', 'duplicate receipt selection',
           wire=dict(value, records=value['records'] * 2), selected=receipts * 2)
    reject('foreign-receipt', 'one terminal', selected=[b'x' * 32])
    reject('unregistered-deployment', 'unregistered deployment',
           wire=dict(value, config=dict(value['config'], network=b'x' * 32)))
    snapshot = value['snapshot']
    reject('checkpoint-replacement', 'expected checkpoint mismatch',
           wire=dict(value, snapshot=dict(snapshot, checkpoint=dict(snapshot['checkpoint'], seq=0))))
    signature = snapshot['signature']
    reject('checkpoint-signature', 'signature',
           wire=dict(value, snapshot=dict(snapshot, signature=bytes([signature[0] ^ 1]) + signature[1:])))
    genesis = snapshot['checkpoint']['genesis'].hex()
    for name, message in (
        ('configuration', 'registered configuration pin'),
        ('anchor', 'anchor consistency'),
        ('source-contract', 'registered deployment or source contract'),
        ('profile', 'unregistered Profile'),
    ):
        changed = c.decode(registry)
        entry = changed['deployments'][genesis]
        if name == 'configuration':
            entry['config_sha256'] = b'x' * 32
        elif name == 'anchor':
            entry['anchor']['head'] = b'x' * 32
        elif name == 'source-contract':
            entry['deployment']['sources']['clock']['version'] = [2, 0, 0]
        else:
            entry['profiles'] = [b'x' * 32]
        raw = c.encode(changed)
        if name in ('configuration', 'anchor'):
            accept_record(name + '-under-test-pin', new_registry=raw,
                          new_pin=hashlib.sha256(raw).digest())
        else:
            reject(name + '-under-test-pin', message, new_registry=raw,
                   new_pin=hashlib.sha256(raw).digest())
    changed = c.decode(registry)
    changed['deployments'][genesis]['deployment']['sources']['clock']['digest'] = b'x' * 32
    raw = c.encode(changed)
    accept_record('source-contract-sha-record', new_registry=raw,
                  new_pin=hashlib.sha256(raw).digest())

    for phase, key, replacement in (
        ('phase_b', 'deployment_binding', {'deployment_ref': {'tag': 'MAINNET'}}),
        ('phase_b', 'funding_held', 0),
        ('phase_b', 'leases', []),
        ('phase_d', 'phase_b_digest', b'x' * 32),
        ('phase_d', 'source_digest', b'x' * 32),
        ('phase_d', 'candidate_record', b''),
    ):
        changed = copy.deepcopy(value)
        record = c.decode(changed['records'][0][phase])
        c.need(record[key] != replacement, 'mutation must change a field')
        record[key] = replacement
        changed['records'][0][phase] = c.encode(record)
        name = phase + '-' + key
        if name in SHA_RECORD_CASES:
            accept_record(name, wire=changed)
        else:
            reject(name, 'B/D envelope does not match', wire=changed)
    for name in ('short-source-digest', 'missing-source-digest'):
        changed = copy.deepcopy(value)
        phase_d = c.decode(changed['records'][0]['phase_d'])
        if name == 'short-source-digest':
            phase_d['source_digest'] = b'short'
        else:
            phase_d.pop('source_digest')
        changed['records'][0]['phase_d'] = c.encode(phase_d)
        reject(name, 'B/D envelope does not match', wire=changed)
    changed_registry = c.decode(registry)
    changed_registry['deployments'][genesis]['deployment']['sources']['clock']['id'] = 'acl.test.fm-s3.other'
    raw = c.encode(changed_registry)
    reject('source-contract-id', 'registered deployment or source contract',
           new_registry=raw, new_pin=hashlib.sha256(raw).digest())
    changed = copy.deepcopy(value)
    record = changed['records'][0]
    phase_b = c.decode(record['phase_b'])
    phase_d = c.decode(record['phase_d'])
    phase_b['deadline'] += 1
    phase_d['phase_b_digest'] = envelope.digest(envelope.VERSION + '/PhaseB', phase_b)
    record.update(phase_b=c.encode(phase_b), phase_d=c.encode(phase_d))
    reject('changed-phase-b-with-matching-link', 'B/D envelope does not match', wire=changed)
    return checks


def run(cases, registry, pin, *, binary=None):
    rows, rust_requests, rust_expected = [], [], []
    negative_fixture = None
    for name, config, snapshot, _, _, receipts in cases:
        records, expected = envelope.replay(registry, pin, config, snapshot, receipts)
        value = dict(version=envelope.VERSION, config=config, snapshot=snapshot, records=records)
        wire = c.encode(value)
        report = envelope.verify(wire, registry, pin, receipts)
        c.need(report == expected, 'authenticated replay changed')
        if name == 'FM-S3-EXECUTION-CLOSURE':
            negative_fixture = value, receipts
        entries = []
        for record, row in zip(records, report['receipts'], strict=True):
            phase_d = c.decode(record['phase_d'])
            candidate_raw = phase_d['candidate_record']
            candidate_pin = hashlib.sha256(candidate_raw).hexdigest()
            # Candidate SHA is retained as a record.
            entries.append(dict(receipt=row['receipt'], terminal=row['terminal'],
                                phase_b_sha256=hashlib.sha256(record['phase_b']).hexdigest(),
                                phase_d_sha256=hashlib.sha256(record['phase_d']).hexdigest(),
                                candidate_sha256=candidate_pin))
            payload = c.encode(dict(source=bytes.fromhex(row['phase_d_source_cbor_hex']), candidate=candidate_raw))
            deployment = hashlib.sha256(c.encode(config)).hexdigest()
            rust_requests.append(f'phase-d-candidate:{deployment}:{row["phase_d_source_digest"]}\t{payload.hex()}')
            rust_expected.append(dict(candidate_cbor_hex=candidate_raw.hex()))
        rows.append(dict(snapshot=name, envelope_sha256=hashlib.sha256(wire).hexdigest(), receipts=entries))
    c.need(negative_fixture is not None, 'execution closure fixture missing')
    if binary is not None:
        proc = subprocess.run([str(binary)], input='\n'.join(rust_requests) + '\n', text=True,
                              capture_output=True, check=True, timeout=90)
        c.need([json.loads(line) for line in proc.stdout.splitlines()] == rust_expected,
               'R13 Rust inner record differs from R14 envelope')
    return dict(version=envelope.VERSION, registry_sha256=pin.hex(), snapshots=rows,
                negatives=check_negatives(negative_fixture, registry, pin))


def source_names():
    return sorted(set(R13['source_names']()) | {
        REGISTRY.relative_to(ROOT).as_posix(), VECTORS.relative_to(ROOT).as_posix(),
        'scripts/check-phase-d-envelope.py', 'schemas/formal-migration/replay-envelope.md',
    })


def semantic_result(result):
    return dict(version=result['version'], snapshots=[dict(
        snapshot=row['snapshot'], receipts=[{key: receipt[key] for key in ('receipt', 'terminal')}
                                             for receipt in row['receipts']])
        for row in result['snapshots']])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    cases = list(R11['fixtures']())
    frozen = json.loads(VECTORS.read_text())
    registry = REGISTRY.read_bytes()
    pin = bytes.fromhex(frozen['registry_sha256'])
    c.need(c.encode(envelope.record_projection(c.decode(registry))) ==
           c.encode(envelope.record_projection(c.decode(fixture_registry(cases)))),
           'fixture registry semantic drift')
    compiler = os.environ.get('RUSTC', 'rustc')
    with tempfile.TemporaryDirectory(prefix='aclt-phase-d-r14-') as tmp:
        binary = Path(tmp) / 'codec'
        subprocess.run([compiler, '--edition=2021', '-D', 'warnings', str(R13['RUST'] / 'main.rs'),
                        '-o', str(binary)], check=True, timeout=120)
        result = run(cases, registry, pin, binary=binary)
    c.need(semantic_result(result) == semantic_result(frozen), 'R14 semantic vectors drift')
    raw = json.dumps(result, sort_keys=True, separators=(',', ':')).encode()
    summary = dict(status='PASS', sha_consistency='DISABLED',
                   disabled_sha_cases=sorted(SHA_RECORD_CASES), snapshots=len(result['snapshots']),
                   receipts=sum(len(row['receipts']) for row in result['snapshots']),
                   negatives=result['negatives'], registry_sha256=pin.hex(),
                   results_sha256=hashlib.sha256(raw).hexdigest())
    if args.report:
        host = dict(hostname=socket.gethostname(), python=platform.python_version(),
                    kernel=platform.release(), rustc=subprocess.check_output([compiler, '--version'], text=True).strip())
        pins = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_names()}
        with args.report.open('x') as stream:
            json.dump(dict(summary, host=host, source_sha256=pins), stream, indent=2)
            stream.write('\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
