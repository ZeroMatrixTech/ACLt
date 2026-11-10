#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay pinned FM-S3 evidence and compare R12 candidate Phase D vectors."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.verification_profile import codec as c, phase_d_contract as contract

R11 = runpy.run_path(str(ROOT / 'scripts/check-fm-decision-replay.py'))
LEGACY = ROOT / 'docs/testing/PROFILE-AUTHORITY-R11-20261109.summary.json'
VECTORS = ROOT / 'tests/verification_profile/codec/phase-d-contract-vectors.json'


def mutation_cases(fixtures):
    deadline = next(item for item in fixtures if 'deadline_observation_ref' in item[2]['evaluation_input'])
    closure = next(item for item in fixtures if 'execution_closure' in item[2]['evaluation_input'])
    before = next(item for item in fixtures if 'deadline_observation_ref' not in item[2]['evaluation_input'])
    cases = [
        ('foreign-deployment', deadline, ('evaluation_input', 'context', 'deployment_digest'), b'x' * 32),
        ('foreign-receipt', deadline, ('evaluation_input', 'context', 'receipt_id'), b'x' * 32),
        ('foreign-profile', deadline, ('evaluation_input', 'context', 'profile_digest'), b'x' * 32),
        ('changed-cutoff', deadline, ('evaluation_input', 'context', 'cutoff_head'), b'x' * 32),
        ('changed-clock', deadline, ('evaluation_input', 'evaluated_at'), 0),
        ('changed-deadline-ref', deadline, ('evaluation_input', 'deadline_observation_ref'), b'x' * 32),
        ('premature-deadline-ref', before, ('evaluation_input', 'deadline_observation_ref'), b'x' * 32),
        ('changed-closure-event', closure, ('evaluation_input', 'execution_closure',
                                          'recovery_exhausted_event'), b'x' * 32),
        ('changed-reason', closure, ('condition_vector', 0, 'reason_digest'), b'x' * 32),
        ('changed-terminal', closure, ('derived_terminal',), 'TRUSTED'),
    ]
    for name, (pin, row, result), path, value in cases:
        changed = copy.deepcopy(result)
        parent = changed
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
        yield name, pin, row, c.encode(changed)


def check_mutations(fixtures):
    checked = []
    for name, pin, row, changed in mutation_cases(fixtures):
        try:
            contract.verify(changed, pin, row)
        except c.CodecError as exc:
            c.need(str(exc) == 'candidate bytes differ from authenticated replay', name)
        else:
            raise ValueError(f'{name} accepted')
        checked.append(name)
    return checked


def replayed_fixtures():
    legacy = R11['run']()
    expected = json.loads(LEGACY.read_text())
    c.need(legacy['results_sha256'] == expected['results_sha256'], 'R11 historical replay drift')
    configs = {ident: hashlib.sha256(c.encode(config)).digest()
               for ident, config, *_ in R11['fixtures']()}
    fixtures = [
        (report['id'], configs[report['id']], row, contract.project(configs[report['id']], row))
        for report in legacy['reports'] for row in report['receipts']
    ]
    return legacy['results_sha256'], fixtures


def run():
    legacy_digest, fixtures = replayed_fixtures()
    vectors = []
    for snapshot, pin, row, result in fixtures:
        raw = c.encode(result)
        contract.verify(raw, pin, row)
        data = result['evaluation_input']
        vectors.append(dict(
            snapshot=snapshot, receipt=row['receipt'],
            legacy_source_digest=row['phase_d_source_digest'],
            candidate_sha256=hashlib.sha256(raw).hexdigest(),
            input_digest=result['input_digest'].hex(),
            deadline_observation_ref=data.get('deadline_observation_ref', b'').hex() or None,
            closure_digest=data.get('execution_closure', {}).get('closure_digest', b'').hex() or None,
            selected_reason_digest=next(item['reason_digest'].hex() for item in result['condition_vector']
                                        if item['condition'] == result['selected_condition']),
            condition=result['selected_condition'], terminal=result['derived_terminal'],
        ))
    return dict(schema='aclt.phase-d-contract-vectors@1', legacy_results_sha256=legacy_digest,
                negatives=check_mutations([row[1:] for row in fixtures]), vectors=vectors)


def source_names():
    return sorted(set(R11['source_names']()) | {
        LEGACY.relative_to(ROOT).as_posix(), VECTORS.relative_to(ROOT).as_posix(),
        'scripts/check-phase-d-contract.py', 'docs/03-protocol/verification-profile-schema.md',
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = run()
    expected = json.loads(VECTORS.read_text())
    c.need(report == expected, 'Phase D candidate vector drift')
    result_bytes = json.dumps(report, sort_keys=True, separators=(',', ':')).encode('utf-8')
    summary = dict(status='PASS', receipts=len(report['vectors']), negative_checks=len(report['negatives']),
                   legacy_results_sha256=report['legacy_results_sha256'],
                   results_sha256=hashlib.sha256(result_bytes).hexdigest())
    if args.report:
        with args.report.open('x') as stream:
            json.dump(dict(summary, source_sha256={
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_names()
            }), stream, indent=2)
            stream.write('\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
