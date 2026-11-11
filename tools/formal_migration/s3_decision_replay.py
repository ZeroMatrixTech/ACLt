# SPDX-License-Identifier: Apache-2.0
"""Read-only bridge from authenticated FM-S3 evidence to audit Phase D."""
import argparse
import json
from pathlib import Path

from tools.formal_migration import s2, s2_evidence, s3_authority, s3_closure, s3_terminals
from tools.verification_profile import admission, codec as c, decision_replay, profile


def event_positions(events, operation, receipt):
    return [i for i, event in enumerate(events, 1)
            if event['request']['op'] == operation and event['request']['body'].get('receipt') == receipt]


def accepted_evidence(task, events, instant):
    """Preserve first accepted results and replay them in committed event order."""
    rows = []
    outcomes = {}
    for role, slot in task['audit']['slots'].items():
        if slot['kind'] != 'S3_RESULT':
            continue
        matches = [
            event['seq'] for event in events
            if event['request']['op'] == 'S3_RESULT'
            and event['request']['body']['receipt'] == task['rid']
            and event['request']['body']['role'] == role
            and event['result_digest'] == s2.h(slot)
        ]
        c.need(len(matches) == 1 and events[matches[0] - 1]['now'] == slot['received_at'],
               'accepted result event binding')
        assignment = task['leases'][role]['proposal']['assignment']
        outcomes[role] = c.encode(slot['outcome'])
        rows.append((matches[0], dict(attempt_id=assignment, received_at=slot['received_at'],
                                     cost=slot['cost'], validation_passed=True, result=outcomes[role])))
    evidence = [row for _, row in sorted(rows)]
    expected = outcomes.get('EXECUTOR') or outcomes.get('AUDITOR') or c.encode([])
    method_input = dict(expected_result=expected, evidence=evidence)
    _, aggregate = decision_replay.audit_evaluate(
        method_input,
        task['bundle']['receipt']['execution']['deadline'], task['funding_held'], instant)
    c.need(aggregate['admitted'] == len(evidence) and
           aggregate['committed_cost'] == task['audit']['accepted_cost'], 'accepted evidence accounting')
    comparison = 'NO_PAIR'
    if set(outcomes) == set(s2.ROLES):
        comparison = 'CONCORDANT' if outcomes['EXECUTOR'] == outcomes['AUDITOR'] else 'DISCORDANT'
    return method_input, [seq for seq, _ in sorted(rows)], aggregate, comparison


def project_decision(task, raw_prefix, events, instant):
    """Adapt the frozen S3 contract using only pre-finalize state and events."""
    contract = s3_authority.check_bundle(task['bundle'])
    c.need(contract['method'] == 'REEXEC_AUDIT_ONLY' and contract['min_reexecutions'] == 1 and
           contract['rules'] == list(profile.AUDIT_CONDITIONS), 'unsupported audit contract')
    method_input, result_positions, aggregate, comparison = accepted_evidence(task, events, instant)
    audit = task['audit']
    receipt = task['rid']
    deadline = task['bundle']['receipt']['execution']['deadline']
    # Historical S3 observes the deadline at evaluation. This child is derived
    # from the verified prefix and time, and is never counted as a ledger entry.
    frontier, refs = s3_terminals.frontier_view(task, raw_prefix, instant if instant >= deadline else None)
    boundary_observation = {}
    if 'funding_boundary' in audit:
        c.need('funding_boundary' in contract, 'funding contract')
        boundary_observation['funding_event_ref'] = refs.get('FUNDING_EXHAUSTED', s2.ZERO)
    if 'DEADLINE_REACHED' in refs:
        boundary_observation['deadline_event_ref'] = refs['DEADLINE_REACHED']
    boundary = admission.resolve_boundary(boundary_observation, frontier, receipt)
    causes = ['TEST_SOURCE_REVOKED'] if audit['revoked'] else []
    unknown = [role for role in s2.ROLES if task['leases'][role]['state'] == 'CONSUMED'
               and role not in audit['starts']]
    if unknown:
        causes.append('START_UNDETERMINED')
    if boundary == admission.INVALIDATING:
        causes.append('BOUNDARY_UNRESOLVED')

    closure_ref = None
    execution = None
    execution_observation = dict(tag='NOT_APPLICABLE')
    if 'execution_closure' in audit:
        source = audit['execution_closure']
        closure_ref = s3_closure.exhaustion_event(raw_prefix, source)
        # The source signature and request binding were checked by S3 replay.
        # Adapt just the fields consumed by R10 and keep the source ref separately.
        record = dict(receipt_id=receipt,
                      execution_contract_ref=decision_replay.contract_ref(decision_replay.CLOSURE_ID),
                      attempts_observed=source['attempts_observed'],
                      valid_submission_count=source['valid_submission_count'],
                      recovery_exhausted_event=closure_ref)
        record['closure_digest'] = decision_replay.closure_digest(record)
        events_by_ref = {c.encode(row['event_ref']): row for row in frontier['event_records']}
        events_by_ref[c.encode(closure_ref)].update(
            event_kind='EXECUTION_EXHAUSTED', subject_ref=dict(tag='RECEIPT', id=receipt))
        execution_observation = dict(tag='CLOSURE', record=record)
        # S3's verified linear prefix includes the closure event and proves the
        # auditor had not started, as required by the closure transition.
        execution = decision_replay.execution_condition(
            execution_observation, receipt, events_by_ref,
            events_by_ref.keys(), aggregate['admitted'])
    conditions = decision_replay.audit_conditions(bool(causes), execution, boundary,
                                                  aggregate['admitted'], 2)
    winner = next((rule for rule in profile.AUDIT_CONDITIONS if conditions[rule]), None)
    c.need(winner is not None, 'audit evidence still open')
    evidence = dict(receipt=receipt, profile=s3_authority.profile_ref(task['bundle']),
                    instant=instant, deadline=deadline, funding_cap=task['funding_held'],
                    method_input=method_input, result_positions=result_positions,
                    aggregate=aggregate, method_observation=comparison, minimum_accepted_results=2,
                    causes=causes, unknown_starts=unknown, boundary=boundary_observation,
                    projected_frontier=frontier, execution_observation=execution_observation,
                    conditions=conditions)
    if closure_ref is not None:
        evidence['execution_closure'] = audit['execution_closure']
        evidence['closure_event'] = closure_ref
    return evidence, winner, profile.TERMINALS[winner]


def verify(cfg, pack, anchor, checkpoint, receipts, *, observe=None):
    """Verify an exact checkpoint and replay requested settled decisions.

    Config, anchor and expected checkpoint must be supplied from outside the
    package. The expected checkpoint is an exact pin, not a freshness oracle.
    An optional observer receives each checked row and its pre-decision task.
    """
    c.need(type(receipts) is list and 1 <= len(receipts) <= 16, 'receipt selection')
    for receipt in receipts:
        s2.pin(receipt)
    c.need(len(set(receipts)) == len(receipts), 'duplicate receipt selection')
    for pin in (anchor, checkpoint):
        s2.fields(pin, {'schema', 'genesis', 'seq', 'head', 'state_digest'})
        s2.uint(pin['seq'])
        for key in ('genesis', 'head', 'state_digest'):
            s2.pin(pin[key])
    s2.fields(pack, {'schema', 'checkpoint', 'signature', 'state', 'events'})
    c.need(c.encode(pack['checkpoint']) == c.encode(checkpoint), 'expected checkpoint mismatch')
    c.need(type(pack['events']) is list and len(pack['events']) <= 256, 'snapshot count')
    events = []
    for raw in pack['events']:
        event = c.decode(raw)
        s2.fields(event, {'schema', 'genesis', 'seq', 'prev', 'parents', 'now', 'request',
                          'state_digest', 'result_digest'})
        s2.fields(event['request'], s2.REQUEST)
        c.need(type(event['request']['body']) is dict, 'event request body')
        events.append(event)
    positions = {}
    for receipt in receipts:
        finalized = event_positions(events, 'S3_FINALIZE', receipt)
        settled = event_positions(events, 'S3_SETTLE', receipt)
        c.need(len(finalized) == len(settled) == 1 and finalized[0] < settled[0],
               'one terminal and later settlement required for receipt')
        positions[receipt] = finalized[0], settled[0]
    capture = {seq for pair in positions.values() for seq in pair}
    verified = s2_evidence.verify(cfg, pack, anchor, transition=s3_authority.Ledger.transition,
                                  capture=capture)
    final = c.decode(pack['state'])
    rows = []
    for receipt, (decision_seq, settlement_seq) in positions.items():
        before, decision = map(c.decode, verified['captures'][decision_seq])
        task = before['tasks'][receipt.hex()]
        decision_event = events[decision_seq - 1]
        decision_ref = s2.h(decision_event)
        prefix = pack['events'][:decision_seq - 1]
        evidence, condition, terminal = project_decision(
            task, prefix, events[:decision_seq - 1], decision_event['now'])
        c.need(decision['receipt'] == receipt and decision['profile'] == evidence['profile'] and
               decision['evaluated_at'] == evidence['instant'] and decision['condition'] == condition and
               decision['terminal'] == terminal and decision['method_observation'] == evidence['method_observation'],
               'Phase D replay differs from committed decision')
        settled_before, settlement = map(c.decode, verified['captures'][settlement_seq])
        committed = final['tasks'][receipt.hex()]
        c.need(c.encode(committed['audit']['decision']) == c.encode(decision) and
               c.encode(committed['settlement']) == c.encode(settlement) and
               settlement['receipt'] == receipt and settlement['terminal'] == terminal and
               settlement['decision_event'] == decision_ref and settlement['decision_digest'] == s2.h(decision) and
               settlement['paid'] + settlement['refund'] == settled_before['tasks'][receipt.hex()]['funding_held'],
               'settlement linkage or allocation')
        source = c.encode(dict(genesis=checkpoint['genesis'], cutoff_seq=decision_seq - 1,
                               cutoff_head=decision_event['prev'], pre_state_digest=s2.h(before),
                               projection=evidence))
        digest = c.domain_hash('ACLt/TEST/R11/PhaseDSource/1', source)
        rows.append(dict(receipt=receipt.hex(), profile=evidence['profile'].hex(),
                         cutoff_seq=decision_seq - 1, cutoff_head=decision_event['prev'].hex(),
                         decision_seq=decision_seq, decision_event=decision_ref.hex(),
                         decision_digest=s2.h(decision).hex(), settlement_seq=settlement_seq,
                         settlement_event=s2.h(events[settlement_seq - 1]).hex(),
                         settlement_digest=s2.h(settlement).hex(), phase_d_source_digest=digest.hex(),
                         phase_d_source_cbor_hex=source.hex(),
                         condition=condition, terminal=terminal, method_observation=evidence['method_observation'],
                         admitted=evidence['aggregate']['admitted'], accepted_cost=evidence['aggregate']['committed_cost'],
                         paid=settlement['paid'], refund=settlement['refund'],
                         entitlements=len(settlement['entitlements'])))
        if observe is not None:
            observe(rows[-1], task, prefix)
    return dict(status='PASS', genesis=checkpoint['genesis'].hex(), checkpoint_seq=checkpoint['seq'],
                checkpoint_head=verified['head'], official_admission=False, receipts=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--anchor', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--receipt', action='append', required=True)
    args = parser.parse_args()
    try:
        report = verify(c.decode(args.config.read_bytes()), c.decode(args.snapshot.read_bytes()),
                        c.decode(args.anchor.read_bytes()), c.decode(args.checkpoint.read_bytes()),
                        [bytes.fromhex(receipt) for receipt in args.receipt])
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(1, f'REJECT: {exc}\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
