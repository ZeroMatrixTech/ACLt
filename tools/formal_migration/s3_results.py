# SPDX-License-Identifier: Apache-2.0
"""FM-S3a candidate signed results and pure audit replay; no admission or money.

The caller supplies an independently authenticated S2 checkpoint. Replay proves
facts at that checkpoint, not current wall-clock freshness or timely submission.
"""
import copy
from tools.formal_migration import policy as p, s2, s2_evidence
from tools.verification_profile import codec as c

SCHEMA = 'ACLt/FM/S3a/1'
EVENTS = ('POSITIVE', 'NEGATIVE', 'TIMEOUT', 'RESOURCE_EXHAUSTED',
          'MALFORMED_SUBMISSION', 'ENCODING_INVALID', 'VERIFIER_CRASH',
          'VERIFIER_NONDETERMINISM_DETECTED', 'OBJECT_UNAVAILABLE', 'EPOCH_STALE',
          'ASSUMPTION_REVOKED', 'EQUIVALENCE_UNDECIDED', 'EQUIVALENCE_RESOURCE_EXCEEDED')
RULES = ('VERIFICATION_INVALIDATING', 'EXECUTION_FAILED', 'BUDGET_EXHAUSTED',
         'DEADLINE_REACHED', 'EVIDENCE_EXHAUSTED')
RESULT_FIELDS = {'schema', 'genesis', 'receipt', 'profile', 'role', 'provider',
                 'assignment', 'epoch', 'intent', 'consume_event', 'outcome', 'signature'}


def digest(kind, value):
    return c.domain_hash(SCHEMA + '/' + kind, c.encode(value))


def profile():
    """Exactly one candidate contract; this is not an official Profile object."""
    outcomes = {e: 'INCONCLUSIVE' for e in EVENTS}
    outcomes.update(POSITIVE='CONCORDANT', NEGATIVE='DISCORDANT')
    for e in ('VERIFIER_NONDETERMINISM_DETECTED', 'OBJECT_UNAVAILABLE',
              'EPOCH_STALE', 'ASSUMPTION_REVOKED', 'EQUIVALENCE_RESOURCE_EXCEEDED'):
        outcomes[e] = 'VERIFICATION_INVALIDATING'
    return dict(schema=SCHEMA, scope='TEST_ONLY_NO_OFFICIAL_ADMISSION',
                method='REEXEC_AUDIT_ONLY', verified_claim_spec=dict(kind='NO_CLAIM'),
                safety_parameters=[], liveness_parameters=[], min_reexecutions=1,
                comparison='CANONICAL_OUTCOME_BITWISE',
                failure_mapping=[dict(event=e, outcome=outcomes[e], attribution='NO_ATTRIBUTION') for e in EVENTS],
                rules=list(RULES), default='UNRESOLVED',
                reachable_terminals=list(p.PROCESS_TERMINALS))


def check_profile(value):
    # Encoding validation excludes bool/int aliases, null, unknown fields and tags.
    c.need(c.encode(value) == c.encode(profile()), 'unsupported S3a audit contract')
    return digest('PROFILE', value)


def bind_bundle(bundle):
    """New commitment only; caller must re-sign and allowlist its new Receipt."""
    result = copy.deepcopy(bundle)
    for component in result['components']:
        if component['kind'] == 'AUDIT_CONTRACT':
            component['content'] = c.encode(profile())
    result['receipt']['component_refs'] = [p.ref(x['kind'], x) for x in result['components']]
    p.bundle(result)
    return result


def bundle_profile(bundle):
    p.bundle(bundle)
    contract = next(x for x in bundle['components'] if x['kind'] == 'AUDIT_CONTRACT')
    return check_profile(c.decode(contract['content']))


def outcome_check(raw, execution):
    c.need(type(raw) is bytes and 0 < len(raw) <= execution['output_bytes_limit'] + 128,
           'S3a outcome byte bound')
    obj = c.decode(raw)
    # Initial stats-int-v1 path only; semantic traps need a later explicit contract.
    s2.fields(obj, {'outcome', 'gas_used', 'output'})
    c.need(obj['outcome'] == 'OK', 'S3a supports OK task outcomes only')
    s2.uint(obj['gas_used'])
    c.need(obj['gas_used'] <= execution['fuel'], 'outcome fuel bound')
    c.need(type(obj['output']) is bytes and len(obj['output']) <= execution['output_bytes_limit'],
           'outcome output bound')
    c.need(c.encode(obj) == raw, 'canonical outcome encoding')
    return c.domain_hash('ACLt/RIR-0/ExecutionOutcome/1', raw)


def consumed_event(snapshot, assignment, intent):
    matches = []
    for raw in snapshot['events']:
        event = c.decode(raw)
        req = event['request']
        if req['op'] == 'CONSUME' and req['body']['assignment'] == assignment and req['body']['intent'] == intent:
            matches.append(s2.h(event))
    c.need(len(matches) == 1, 'one authenticated consume event required')
    return matches[0]


def context(cfg, snapshot, checkpoint, receipt):
    c.need(checkpoint is not None and c.encode(checkpoint) == c.encode(snapshot['checkpoint']),
           'explicit independently authenticated checkpoint required')
    s2_evidence.verify(cfg, snapshot, checkpoint)
    s2.pin(receipt)
    state = c.decode(snapshot['state'])
    task = state['tasks'].get(receipt.hex())
    c.need(task is not None and not task['fenced'], 'unknown/fenced S3a receipt')
    c.need(state['last_time'] < task['bundle']['receipt']['execution']['deadline'],
           'checkpoint past execution deadline')
    return task


def unsigned(cfg, task, snapshot, role, outcome):
    c.need(type(role) is str and role in s2.ROLES, 'S3a role')
    lease = task['leases'][role]
    c.need(lease['state'] == 'CONSUMED', 'result requires consumed lease')
    proposal = lease['proposal']
    outcome_check(outcome, task['bundle']['receipt']['execution'])
    return dict(schema=SCHEMA, genesis=s2.h(cfg), receipt=task['rid'],
                profile=bundle_profile(task['bundle']), role=role,
                provider=proposal['provider'], assignment=proposal['assignment'], epoch=1,
                intent=lease['intent'], consume_event=consumed_event(snapshot, proposal['assignment'], lease['intent']),
                outcome=outcome)


def sign_result(cfg, snapshot, checkpoint, receipt, role, outcome, private):
    task = context(cfg, snapshot, checkpoint, receipt)
    value = unsigned(cfg, task, snapshot, role, outcome)
    return dict(value, signature=s2.sign(private, SCHEMA + '/RESULT', value))


def verify_result(cfg, snapshot, checkpoint, receipt, raw):
    task = context(cfg, snapshot, checkpoint, receipt)
    value = c.decode(raw)
    s2.fields(value, RESULT_FIELDS)
    expected = unsigned(cfg, task, snapshot, value['role'], value['outcome'])
    body = {k: v for k, v in value.items() if k != 'signature'}
    c.need(c.encode(body) == c.encode(expected), 'S3a result binding')
    record = cfg['providers'][value['role']]
    s2.verify_signature(record['public_key_der'], SCHEMA + '/RESULT', body, value['signature'])
    return value


def replay_pair(cfg, snapshot, checkpoint, receipt, results):
    c.need(type(results) is list and len(results) == 2, 'one executor and one auditor result required')
    checked = [verify_result(cfg, snapshot, checkpoint, receipt, raw) for raw in results]
    c.need({v['role'] for v in checked} == set(s2.ROLES), 'duplicate/missing audit role')
    event = 'POSITIVE' if checked[0]['outcome'] == checked[1]['outcome'] else 'NEGATIVE'
    row = next(r for r in profile()['failure_mapping'] if r['event'] == event)
    # This observation is an input to future explicit assumption/decision evaluation.
    # It is never a Decision, a terminal authority, fulfillment or payment right.
    return dict(schema=SCHEMA, scope='PURE_REPLAY_NO_ADMISSION', receipt=receipt,
                profile=checked[0]['profile'], checkpoint=checkpoint,
                result_refs=sorted(digest('RESULT', v) for v in checked),
                event=event, outcome=row['outcome'], completed_reexecutions=1,
                coverage_target_met=True, correctness_claim=False,
                decision_committed=False, entitlement_created=False)
