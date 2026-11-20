#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare independent Phase D replay and candidate encoding against R12 vectors."""
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
R12 = runpy.run_path(str(ROOT / 'scripts/check-phase-d-contract.py'))
c = R12['c']
RUST = ROOT / 'tools/verification_profile/rust'


def crosscheck(binary, fixtures, frozen):
    requests = []
    expected = []
    names = []

    def add(name, deployment, source_pin, source, candidate, result):
        raw = c.encode(dict(source=source, candidate=candidate))
        requests.append(f'phase-d-candidate:{deployment.hex()}:{source_pin.hex()}\t{raw.hex()}')
        expected.append(result)
        names.append(name)

    def old_source(row):
        return bytes.fromhex(row['phase_d_source_cbor_hex']), bytes.fromhex(row['phase_d_source_digest'])

    def reject(name, fixture, message, *, deployment=None, source=None, source_pin=None, candidate=None):
        _, pin, row, result = fixture
        raw, legacy_pin = old_source(row)
        add(name, deployment if deployment is not None else pin,
            source_pin if source_pin is not None else legacy_pin,
            source if source is not None else raw,
            candidate if candidate is not None else c.encode(result), {'error': message})

    c.need(len(fixtures) == len(frozen['vectors']), 'frozen receipt count')
    for (snapshot, pin, row, result), vector in zip(fixtures, frozen['vectors'], strict=True):
        raw = c.encode(result)
        source, source_pin = old_source(row)
        c.need((snapshot, row['receipt']) == (vector['snapshot'], vector['receipt']) and
               c.digest_consistency((source_pin.hex(), hashlib.sha256(raw).hexdigest()) ==
                                    (vector['legacy_source_digest'], vector['candidate_sha256'])),
               'R12 frozen encoding drift')
        add(row['receipt'], pin, source_pin, source, raw, {'candidate_cbor_hex': raw.hex()})

    mutations = list(R12['mutation_cases']([row[1:] for row in fixtures]))
    c.need([item[0] for item in mutations] == frozen['negatives'], 'R12 frozen mutations drift')
    for name, pin, row, candidate in mutations:
        if name in R12['SHA_RECORD_CASES']:
            source, source_pin = old_source(row)
            add(name, pin, source_pin, source, candidate, {'candidate_cbor_hex': candidate.hex()})
        else:
            reject(name, ('', pin, row, R12['contract'].project(pin, row)),
                   'candidate bytes differ from authenticated replay', candidate=candidate)

    first = fixtures[0]
    at_deadline = next(item for item in fixtures if 'deadline_observation_ref' in item[-1]['evaluation_input'])
    with_closure = next(item for item in fixtures if 'execution_closure' in item[-1]['evaluation_input'])
    with_cost = next(item for item in fixtures
                     if any(row['cost'] > 0 for row in item[-1]['evaluation_input']['method_input']['evidence']))
    mismatch = 'candidate bytes differ from authenticated replay'
    source, source_pin = old_source(first[2])
    candidate = c.encode(first[-1])
    add('deployment-pin-record', b'x' * 32, source_pin, source, candidate,
        {'candidate_cbor_hex': candidate.hex()})
    add('source-pin-record', first[1], b'x' * 32, source, candidate,
        {'candidate_cbor_hex': candidate.hex()})
    reject('truncated-candidate', first, mismatch, candidate=c.encode(first[-1])[:-1])
    reject('candidate-trailing-byte', first, mismatch, candidate=c.encode(first[-1]) + b'\x00')
    # Record-only SHA fields still retain their schema and value types.
    for name in ('short-input-digest', 'missing-reason-digest', 'condition-integer'):
        changed = copy.deepcopy(first[-1])
        if name == 'short-input-digest':
            changed['input_digest'] = b'short'
        elif name == 'missing-reason-digest':
            changed['condition_vector'][0].pop('reason_digest')
        else:
            changed['condition_vector'][0]['value'] = 1
        raw = c.encode(changed)
        try:
            R12['contract'].verify(raw, first[1], first[2])
        except c.CodecError as exc:
            c.need(str(exc) == mismatch, name)
        else:
            raise ValueError(name + ' accepted by Python')
        reject(name, first, mismatch, candidate=raw)

    def edited_source(fixture, path, change):
        raw, _ = old_source(fixture[2])
        source = c.decode(raw)
        target = source
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = change(target[path[-1]])
        return c.encode(source)

    edits = [
        ('forged-aggregate', first, ('projection', 'aggregate', 'admitted'), lambda n: n + 1,
         'legacy aggregate mismatch'),
        ('forged-condition', first, ('projection', 'conditions', 'VERIFICATION_INVALIDATING'),
         lambda v: not v, 'legacy condition mismatch'),
        ('wrong-cutoff-head', first, ('cutoff_head',), lambda _: b'x' * 32, 'frontier head binding'),
        ('wrong-cutoff-sequence', first, ('cutoff_seq',), lambda n: n + 1, 'frontier length'),
        ('deadline-before-frozen-time', at_deadline, ('projection', 'instant'),
         lambda _: at_deadline[-1]['evaluation_input']['deadline'] - 1, 'deadline presence'),
        ('budget-below-accepted-cost', with_cost, ('projection', 'funding_cap'), lambda _: 0,
         'legacy aggregate mismatch'),
        ('wrong-closure-event', with_closure, ('projection', 'closure_event'), lambda _: b'x' * 32,
         'legacy closure binding'),
    ]
    for name, fixture, path, change, reason in edits:
        raw = edited_source(fixture, path, change)
        reject(name + '-under-test-pin', fixture, reason, source=raw,
               source_pin=c.domain_hash('ACLt/TEST/R11/PhaseDSource/1', raw))

    proc = subprocess.run([str(binary)], input='\n'.join(requests)+'\n', text=True,
                          capture_output=True, check=True, timeout=90)
    answers = [json.loads(line) for line in proc.stdout.splitlines()]
    c.need(len(answers) == len(expected), 'Rust answer count')
    for name, actual, wanted in zip(names, answers, expected, strict=True):
        c.need(actual == wanted, f'{name}: {actual.get("error", "unexpected candidate bytes")}')
    negatives = {name: row['error'] for name, row in zip(names, answers) if 'error' in row}
    result_bytes = json.dumps(list(zip(names, answers)), sort_keys=True, separators=(',', ':')).encode()
    return negatives, hashlib.sha256(result_bytes).hexdigest()


def source_names():
    return sorted(set(R12['source_names']()) | {
        'scripts/check-phase-d-crosscheck.py',
        *(path.relative_to(ROOT).as_posix() for path in RUST.iterdir()
          if path.suffix in {'.rs', '.json'} or path.name == 'UNICODE-LICENSE.txt'),
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    legacy_digest, fixtures = R12['replayed_fixtures']()
    frozen = json.loads(R12['VECTORS'].read_text())
    c.need(c.digest_consistency(legacy_digest == frozen['legacy_results_sha256']), 'R12 legacy result pin')
    compiler = os.environ.get('RUSTC', 'rustc')
    with tempfile.TemporaryDirectory(prefix='aclt-phase-d-r13-') as tmp:
        binary = Path(tmp)/'codec'
        subprocess.run([compiler, '--edition=2021', '-D', 'warnings', str(RUST/'main.rs'),
                        '-o', str(binary)], check=True, timeout=120)
        negatives, digest = crosscheck(binary, fixtures, frozen)
    summary = dict(status='PASS', sha_consistency='DISABLED',
                   disabled_sha_cases=sorted(R12['SHA_RECORD_CASES'] | {'wrong-deployment-pin','wrong-source-pin'}), receipts=len(fixtures), negative_checks=negatives,
                   legacy_results_sha256=legacy_digest, results_sha256=digest)
    if args.report:
        host = dict(hostname=socket.gethostname(), python=platform.python_version(),
                    kernel=platform.release(), rustc=subprocess.check_output([compiler, '--version'], text=True).strip())
        pins = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_names()}
        with args.report.open('x') as stream:
            json.dump(dict(summary, host=host, source_sha256=pins), stream, indent=2)
            stream.write('\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
