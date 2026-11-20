#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cross-check the R10 Phase D TEST replay on canonical CBOR."""
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
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.verification_profile import codec as c, commitments as b, decision_replay as d
from tools.verification_profile import registration as reg

R9 = runpy.run_path(str(ROOT / 'scripts/check-runtime-bindings.py'))
R8 = R9['PREVIOUS']
VECTORS = ROOT / 'tests/verification_profile/codec/decision-replay-vectors.json'

# Each row mutates only the named SHA field or externally supplied SHA pin.
SHA_ONLY_ROWS = frozenset({'forged-reason', 'forged-input-digest', 'foreign-profile',
                          'stale-frontier-context', 'wrong-schema-pin', 'wrong-contract-pin'})


def semantic_result(result):
    return {k: v for k, v in result.items() if k != 'record_sha256'}


def current_frozen_vectors():
    """Adapt declared SHA cases in memory and preserve the frozen JSON bytes."""
    rows = copy.deepcopy(json.loads(VECTORS.read_text())['vectors'])
    by_id = {row['id']: row for row in rows}
    funding = semantic_result(by_id['funding-empty']['expected'])
    failed = semantic_result(by_id['closure']['expected'])
    for item in rows:
        if item['id'] in SHA_ONLY_ROWS:
            item['expected'] = copy.deepcopy(funding)
        elif item['id'] == 'closure-wrong-digest':
            request = c.decode(bytes.fromhex(item['cbor_hex']))
            # The closure still has zero valid submissions and an authorized exhaustion event.
            # Its retired digest mismatch is no longer an invalidating cause.
            winner = stamp(request)
            c.need(winner == 'EXECUTION_FAILED', 'SHA-only closure must retain actual exhaustion semantics')
            item['cbor_hex'] = c.encode(request).hex()
            item['expected'] = copy.deepcopy(failed)
        else:
            item['expected'] = semantic_result(item['expected'])
    return rows



def data(request):
    return request['envelope']['evaluation_input']


def fixture():
    value, _, _ = R9['fixture']('ROUND_TRANSITION_NO_SNAPSHOT', 'REEXEC_AUDIT_ONLY',
                               ('PRE_FREEZE', 'TERMINAL'))
    assurance = value['envelope'].pop('assurance_profile')
    assurance['allowed_validator_refs'] = [d.contract_ref(d.EVALUATOR_ID)]
    assurance['header']['digest'] = b.object_digest(assurance, 'MainnetAssuranceProfile')
    receipt = value['envelope'].pop('receipt_binding')
    receipt['assurance_profile_ref'] = b.identity(assurance)
    profile = value['envelope']['profile']
    bundle = value['envelope']['bundle']
    state = R8['fixture']('state', 'REEXEC_AUDIT_ONLY')[0]['payload']['result']
    state['snapshot']['evaluation_instant'] = bundle['context']['evaluation_instant']
    state['snapshot']['header']['digest'] = b.object_digest(state['snapshot'], 'AssumptionStateSnapshot')
    request = dict(
        schema_lock=value['schema_lock'], schema_documents=value['schema_documents'],
        decision_contract=dict(name='r10-audit-decision-test@1', receipt_binding=copy.deepcopy(receipt),
                               deadline=20, funding_cap=10),
        envelope=dict(phase='D', bundle=bundle, profile=profile,
                      evaluation_input=dict(receipt_binding=receipt, profile_ref=copy.deepcopy(receipt['profile_ref']),
                                            assurance_profile=assurance, method_evaluation={},
                                            assumption_evaluation=state, boundary_observation={},
                                            execution_observation=dict(tag='NOT_APPLICABLE'))))
    set_evidence(request, [], [], 0)
    graph(request, 'none')
    return request


def set_evidence(request, evidence, outcomes, cost):
    data(request)['method_evaluation'] = dict(
        evaluator_ref=d.contract_ref(d.EVALUATOR_ID),
        canonical_input=R8['wrap'](request, dict(expected_result=c.encode(1), evidence=evidence)),
        claimed_outcome=R8['wrap'](request, outcomes),
        claimed_aggregate=R8['wrap'](request, dict(admitted=len(outcomes),
            concordant=outcomes.count('CONCORDANT'), discordant=outcomes.count('DISCORDANT'),
            committed_cost=cost)))


def row(key, received=10, cost=1, passed=True, result=1):
    return dict(attempt_id=key.encode(), received_at=received, cost=cost,
                validation_passed=passed, result=c.encode(result))


def graph(request, mode):
    frontier = request['envelope']['bundle']['event_frontier_snapshot']
    root = next(copy.deepcopy(x) for x in frontier['event_records'] if x['event_ref'] == b'root')
    receipt = data(request)['receipt_binding']['receipt_id']
    subject = dict(tag='RECEIPT', id=receipt)

    def event(ref, kind, parents):
        return dict(event_ref=ref, event_kind=kind, parent_refs=parents, subject_ref=copy.deepcopy(subject))

    rows = [root]
    observation = {}
    head = b'root'
    if mode in ('funding', 'funding-first', 'deadline-first', 'concurrent', 'hidden', 'cycle', 'missing-parent'):
        parents = [b'deadline'] if mode == 'deadline-first' else [b'root']
        if mode == 'cycle':
            parents = [b'funding']
        if mode == 'missing-parent':
            parents = [b'unknown']
        rows.append(event(b'funding', 'FUNDING_EXHAUSTED', parents))
        observation['funding_event_ref'] = head = b'funding'
    if mode in ('deadline', 'funding-first', 'deadline-first', 'concurrent'):
        parents = [b'funding'] if mode == 'funding-first' else [b'root']
        rows.append(event(b'deadline', 'DEADLINE_REACHED', parents))
        observation['deadline_event_ref'] = b'deadline'
        if mode != 'deadline-first':
            head = b'deadline'
    if mode == 'concurrent':
        root_join = copy.deepcopy(root)
        root_join.update(event_ref=b'join', parent_refs=sorted([b'deadline', b'funding'], key=c.encode))
        rows.append(root_join)
        head = b'join'
    if mode == 'hidden':
        head = b'root'
    if mode in ('closure', 'closure-started', 'closure-funding'):
        if mode == 'closure-started':
            rows.append(event(b'start', 'VERIFICATION_STARTED', [head]))
            head = b'start'
        if mode == 'closure-funding':
            rows.append(event(b'funding', 'FUNDING_EXHAUSTED', [head]))
            observation['funding_event_ref'] = head = b'funding'
        rows.append(event(b'closure', 'EXECUTION_EXHAUSTED', [head]))
        head = b'closure'
    frontier.update(frontier_event_ref=head, event_records=rows)
    data(request)['boundary_observation'] = observation
    R9['seal'](request)


def closure(request, valid=0, attempts=2):
    record = dict(receipt_id=data(request)['receipt_binding']['receipt_id'],
                  execution_contract_ref=d.contract_ref(d.CLOSURE_ID), attempts_observed=attempts,
                  valid_submission_count=valid, recovery_exhausted_event=b'closure')
    record['closure_digest'] = d.closure_digest(record)
    data(request)['execution_observation'] = dict(tag='CLOSURE', record=record)
    return record


def pins(request):
    return tuple(hashlib.sha256(c.encode(request[key])).digest()
                 for key in ('schema_lock', 'decision_contract'))


def stamp(request):
    clean = {key: value for key, value in request.items() if key != 'decision'}
    record = d.replay(clean, *pins(request))
    request['decision'] = dict(evaluation_record=record, terminal_state=record['derived_terminal'])
    return record.get('selected_condition', '')


def vectors():
    rows = []

    def add(name, request, winner=None, override=None):
        if winner is not None:
            observed = stamp(request)
            if observed != winner:
                raise ValueError((name, winner, observed))
        schema_pin, contract_pin = override or pins(request)
        raw = c.encode(request)
        item = dict(id=name, cbor_hex=raw.hex(), schema_pin=schema_pin.hex(), contract_pin=contract_pin.hex())
        try:
            outcome = d.inspect(raw, schema_pin, contract_pin)
        except c.CodecError:
            if winner is not None:
                raise
            outcome = dict(error=True)
        if winner is None and outcome != dict(error=True):
            raise ValueError('negative accepted: ' + name)
        item['expected'] = outcome
        rows.append(item)

    boundary_cases = {'none': '', 'funding': 'BUDGET_EXHAUSTED', 'deadline': 'DEADLINE_REACHED',
                      'funding-first': 'BUDGET_EXHAUSTED', 'deadline-first': 'DEADLINE_REACHED',
                      'concurrent': 'BUDGET_EXHAUSTED', 'hidden': d.admission.INVALIDATING,
                      'cycle': d.admission.INVALIDATING, 'missing-parent': d.admission.INVALIDATING}
    for mode, winner in boundary_cases.items():
        for with_evidence in (False, True):
            request = fixture()
            graph(request, mode)
            if with_evidence:
                minimum = request['envelope']['profile']['method_parameters']['min_reexecutions']
                set_evidence(request, [row(str(i)) for i in range(minimum)], ['CONCORDANT'] * minimum, minimum)
            add(mode + ('-covered' if with_evidence else '-empty'), request,
                winner or ('EVIDENCE_EXHAUSTED' if with_evidence else ''))
    for key, kind in [('funding_event_ref', 'funding'), ('deadline_event_ref', 'deadline')]:
        for problem in ('missing', 'wrong-kind', 'foreign-receipt'):
            request = fixture()
            graph(request, kind)
            frontier = request['envelope']['bundle']['event_frontier_snapshot']
            target = next(row for row in frontier['event_records'] if row['event_ref'] == kind.encode())
            if problem == 'missing':
                data(request)['boundary_observation'][key] = b'absent'
            elif problem == 'wrong-kind':
                target['event_kind'] = 'EXECUTION_EXHAUSTED'
            else:
                target['subject_ref']['id'] = b'q' * 32
            R9['seal'](request)
            add(kind + '-' + problem, request, d.admission.INVALIDATING)
    for mode, expected in [('closure', 'EXECUTION_FAILED'), ('closure-started', d.admission.INVALIDATING),
                           ('closure-funding', 'EXECUTION_FAILED')]:
        request = fixture()
        graph(request, mode)
        closure(request)
        add(mode, request, expected)
    for name, update, reseal in [
        ('valid-result', {'valid_submission_count': 1}, True),
        ('negative-attempts', {'attempts_observed': -1}, True),
        ('over-count', {'valid_submission_count': 3}, True),
        ('wrong-receipt', {'receipt_id': b'q' * 32}, True),
        ('wrong-source', {'execution_contract_ref': d.contract_ref('acl.other')}, True),
        ('wrong-event', {'recovery_exhausted_event': b'root'}, True),
        ('wrong-digest', {'closure_digest': b'x' * 32}, False),
    ]:
        request = fixture()
        graph(request, 'closure')
        record = closure(request)
        record.update(update)
        if reseal:
            record['closure_digest'] = d.closure_digest(record)
        add('closure-' + name, request, '' if name == 'valid-result' else 'EXECUTION_FAILED' if name == 'wrong-digest' else d.admission.INVALIDATING)
    for failure_class in ('UNAVAILABLE', 'MALFORMED', 'UNTRUSTED_SOURCE'):
        request = fixture()
        graph(request, 'closure-funding')
        data(request)['execution_observation'] = dict(tag='SOURCE_UNAVAILABLE',
            failure=dict(dependency_ref=d.contract_ref(d.CLOSURE_ID), failure_class=failure_class))
        add('execution-source-' + failure_class, request, d.admission.INVALIDATING)
    evidence_cases = [
        ('one-match', [row('a')], ['CONCORDANT'], 1),
        ('different-byte', [row('a', result=True)], ['DISCORDANT'], 1),
        ('strict-deadline', [row('a', received=20)], [], 0),
        ('budget-equality-and-overflow', [row('a', cost=10), row('b', cost=2**64 - 1)], ['CONCORDANT'], 10),
        ('invalid-validation', [row('a', passed=False)], [], 0),
        ('skip-unaffordable', [row('a', cost=11), row('b', cost=10)], ['CONCORDANT'], 10),
        ('duplicate-attempt', [row('a'), row('a')], [], 0),
        ('future-attempt', [row('a', received=101)], [], 0),
        ('decreasing-time', [row('a', received=11), row('b')], [], 0),
        ('invalid-cost', [row('a', cost=-1)], [], 0),
    ]
    for name, evidence, outcomes, cost in evidence_cases:
        request = fixture()
        set_evidence(request, evidence, outcomes, cost)
        minimum = request['envelope']['profile']['method_parameters']['min_reexecutions']
        winner = ('EVIDENCE_EXHAUSTED' if len(outcomes) >= minimum else '')
        if name in ('duplicate-attempt', 'future-attempt', 'decreasing-time', 'invalid-cost'):
            winner = d.admission.INVALIDATING
        add('evidence-' + name, request, winner)
    request = fixture()
    graph(request, 'closure')
    closure(request)
    set_evidence(request, [row('a')], ['CONCORDANT'], 1)
    add('closure-contradicts-admitted-evidence', request, d.admission.INVALIDATING)
    for label in ('unknown-evaluator', 'not-allowed', 'invalidating-assumption', 'invalid-safety-state'):
        request = fixture()
        graph(request, 'funding')
        info = data(request)
        if label == 'unknown-evaluator':
            info['method_evaluation']['evaluator_ref'] = d.contract_ref('acl.other')
        elif label == 'not-allowed':
            assurance = info['assurance_profile']
            assurance['allowed_validator_refs'] = []
            assurance['header']['digest'] = b.object_digest(assurance, 'MainnetAssuranceProfile')
            info['receipt_binding']['assurance_profile_ref'] = b.identity(assurance)
            request['decision_contract']['receipt_binding'] = copy.deepcopy(info['receipt_binding'])
        elif label == 'invalidating-assumption':
            info['assumption_evaluation'] = dict(tag='INVALIDATING',
                failure=dict(assumption_id='ACL-ASM-0002', failure_class='EVIDENCE_UNAVAILABLE', observed_at=10))
        else:
            snapshot = info['assumption_evaluation']['snapshot']
            profile = request['envelope']['profile']
            safety = profile['assumption_references'][0]
            safety.update(role='SAFETY_CRITICAL', revocation_mapping=copy.deepcopy(b.common.SAFE_REVOCATION))
            profile['profile_digest'] = b.p.profile_digest(profile)
            reference = b.selection.profile_ref(profile)
            info['profile_ref'] = copy.deepcopy(reference)
            info['receipt_binding']['profile_ref'] = copy.deepcopy(reference)
            assurance = info['assurance_profile']
            assurance['profile_capabilities'][0]['profile_ref'] = copy.deepcopy(reference)
            assurance['header']['digest'] = b.object_digest(assurance, 'MainnetAssuranceProfile')
            info['receipt_binding']['assurance_profile_ref'] = b.identity(assurance)
            request['decision_contract']['receipt_binding'] = copy.deepcopy(info['receipt_binding'])
            registry = request['envelope']['bundle']['registry_snapshot']
            for entry in registry['entries']:
                if entry['id'] == reference['id']:
                    entry['digest'] = reference['digest']
            registry['header']['digest'] = reg.registry_digest(registry)
            R9['seal'](request)
            snapshot['assumption_states'] = [dict(
                assumption_id=safety['assumption_id'], evidence_ref=safety['evidence_ref'],
                evidence_version=safety['evidence_version'], effective_verdict='REVOKED',
                cause_set=[dict(cause_code='REVOKED', evidence_ref=b'cause', observed_event_ref=b'root')])]
            snapshot['header']['digest'] = b.object_digest(snapshot, 'AssumptionStateSnapshot')
        add(label, request, d.admission.INVALIDATING)
    base = fixture()
    graph(base, 'funding')
    stamp(base)
    for name, mutate in [
        ('claimed-outcome', lambda v: data(v)['method_evaluation'].update(claimed_outcome=R8['wrap'](v, ['CONCORDANT']))),
        ('claimed-aggregate', lambda v: data(v)['method_evaluation'].update(claimed_aggregate=R8['wrap'](v, dict(admitted=20)))),
        ('swapped-vector', lambda v: v['decision']['evaluation_record']['condition_vector'].reverse()),
        ('missing-condition', lambda v: v['decision']['evaluation_record']['condition_vector'].pop()),
        ('forged-reason', lambda v: v['decision']['evaluation_record']['condition_vector'][0].update(reason_digest=b'x'*32)),
        ('forged-input-digest', lambda v: v['decision']['evaluation_record'].update(input_digest=b'x'*32)),
        ('forged-selected', lambda v: v['decision']['evaluation_record'].update(selected_condition='EXECUTION_FAILED')),
        ('forged-derived', lambda v: v['decision']['evaluation_record'].update(derived_terminal='FAILED')),
        ('forged-terminal', lambda v: v['decision'].update(terminal_state='TRUSTED')),
        ('foreign-receipt', lambda v: data(v)['receipt_binding'].update(receipt_id=b'q'*32)),
        ('foreign-profile', lambda v: data(v)['profile_ref'].update(digest=b'q'*32)),
        ('stale-frontier-context', lambda v: v['envelope']['bundle']['context']['event_frontier_ref'].update(digest=b'q'*32)),
        ('wrong-phase', lambda v: v['envelope'].update(phase='B')),
    ]:
        request = copy.deepcopy(base)
        mutate(request)
        add(name, request, 'BUDGET_EXHAUSTED' if name in SHA_ONLY_ROWS else None)
    schema_pin, contract_pin = pins(base)
    add('wrong-schema-pin', base, 'BUDGET_EXHAUSTED', override=(b'q'*32, contract_pin))
    add('wrong-contract-pin', base, 'BUDGET_EXHAUSTED', override=(schema_pin, b'q'*32))
    return rows


def run(binary, rows):
    lines = ''.join(f"decision-replay:{row['schema_pin']}:{row['contract_pin']}\t{row['cbor_hex']}\n"
                    for row in rows)
    result = subprocess.run([str(binary)], input=lines, capture_output=True, text=True,
                            timeout=120, check=True)
    normalized = []
    for row, line in zip(rows, result.stdout.splitlines(), strict=True):
        answer = json.loads(line)
        if 'error' in answer:
            answer = dict(error=True)
        try:
            python = d.inspect(bytes.fromhex(row['cbor_hex']), bytes.fromhex(row['schema_pin']),
                               bytes.fromhex(row['contract_pin']))
        except c.CodecError:
            python = dict(error=True)
        if semantic_result(answer) != semantic_result(python) or semantic_result(answer) != semantic_result(row['expected']):
            raise ValueError(f"{row['id']}: Rust {answer!r}, Python {python!r}, expected {row['expected']!r}")
        normalized.append(answer)
    return normalized


def source_names():
    return sorted(set(R9['source_names']()) | {
        'scripts/check-decision-replay.py', 'tests/verification_profile/codec/decision-replay-vectors.json',
        'tests/verification_profile/test_decision_replay.py',
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-vectors', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.freeze_vectors:
        rows = vectors()
        with VECTORS.open('x') as out:
            json.dump(dict(scope='Phase D audit TEST replay', vectors=rows), out, indent=2)
            out.write('\n')
    rows = current_frozen_vectors()
    with tempfile.TemporaryDirectory(prefix='aclt-decision-replay-') as tmp:
        binary = Path(tmp) / 'codec'
        subprocess.run([os.environ.get('RUSTC', 'rustc'), '--edition=2021', '-D', 'warnings',
                        str(ROOT / 'tools/verification_profile/rust/main.rs'), '-o', str(binary)],
                       timeout=120, check=True)
        answers = run(binary, rows)
    report = dict(sha_consistency='DISABLED',status='PASS', cases=len(rows), structural_rejects=sum('error' in x for x in answers),
                  results_sha256=hashlib.sha256(json.dumps(answers, sort_keys=True).encode()).hexdigest(),
                  hostname=socket.gethostname(), kernel=platform.release(), python=platform.python_version(),
                  rustc=subprocess.check_output([os.environ.get('RUSTC', 'rustc'), '--version'], text=True).strip(),
                  source_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                 for name in source_names()},
                  formal_phase_d_conformance=False, production_admission=False, state_committed=False)
    if args.report:
        with args.report.open('x') as out:
            json.dump(report, out, indent=2)
            out.write('\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'source_sha256'}, indent=2))


if __name__ == '__main__':
    main()
