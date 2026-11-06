# SPDX-License-Identifier: Apache-2.0
"""Bounded S3b test authority over the S2 transaction and event chain."""
import copy

from tools.formal_migration import foundation as f, policy as p, s2, s2_evidence, s3_results, s3_settlement
from tools.verification_profile import admission, codec as c

SCHEMA = 'ACLt/FM/S3b/1'
ROLE_BINDING = {'receipt', 'profile', 'role', 'assignment', 'epoch', 'intent', 'consume_event'}
ACTIONS = {
    'S3_START': ROLE_BINDING,
    'S3_RESULT': ROLE_BINDING | {'start', 'outcome'},
    'S3_HOST_FAULT': ROLE_BINDING | {'start', 'reason'},
    'S3_REVOKE': {'receipt'},
    'S3_FINALIZE': {'receipt'},
    'S3_SETTLE': {'receipt'},
    'S3_SETTLEMENT_STATUS': {'receipt'},
}
BUCKET = {'EXECUTOR': 'execution_limit', 'AUDITOR': 'verification_limit'}


def profile(*, task_traps=False):
    value = s3_results.profile()
    for key in ('verified_claim_spec', 'safety_parameters', 'liveness_parameters'):
        del value[key]
    value.update(schema=SCHEMA, start_source='PINNED_PROVIDER_TEST_ENTRY_ATTESTATION',
                 conflict_limit_per_role=1, acceptance_cost='RESERVE_ROLE_BUCKET',
                 clock='PINNED_MONOTONIC_TEST_TIME')
    if task_traps:
        value['task_outcomes'] = 'RIR_OK_ABORT_AND_TRAPS_V1'
    return value


def profile_ref(*, task_traps=False):
    return c.domain_hash(SCHEMA + '/PROFILE', c.encode(profile(task_traps=task_traps)))


def bind_bundle(bundle, *, task_traps=False):
    value = copy.deepcopy(bundle)
    for component in value['components']:
        if component['kind'] == 'AUDIT_CONTRACT':
            component['content'] = c.encode(profile(task_traps=task_traps))
    value['receipt']['component_refs'] = [p.ref(x['kind'], x) for x in value['components']]
    p.bundle(value)
    return value


def check_bundle(bundle):
    component = next(x for x in bundle['components'] if x['kind'] == 'AUDIT_CONTRACT')
    content = component['content']
    if content == c.encode(profile()):
        return False
    c.need(content == c.encode(profile(task_traps=True)), 'S3b profile required')
    return True


def initial_audit():
    return dict(phase='BEFORE_VERIFICATION', starts={}, slots={}, conflicts={},
                accepted_cost=0, revoked=False, decision={})


def role_binding(task, events, role):
    lease = task['leases'][role]
    prop = lease['proposal']
    return dict(receipt=task['rid'], profile=profile_ref(task_traps=check_bundle(task['bundle'])), role=role,
                assignment=prop['assignment'], epoch=prop['epoch'], intent=lease['intent'],
                consume_event=s3_results.consumed_event({'events': events}, prop['assignment'], lease['intent']))


def evaluate(task, now):
    audit = task['audit']
    executor = audit['slots'].get('EXECUTOR', {})
    auditor = audit['slots'].get('AUDITOR', {})
    pair = executor.get('kind') == auditor.get('kind') == 'S3_RESULT'
    deadline = now >= task['bundle']['receipt']['execution']['deadline']
    unknown = [role for role in s2.ROLES if task['leases'][role]['state'] == 'CONSUMED'
               and role not in audit['starts']]
    causes = (['TEST_SOURCE_REVOKED'] if audit['revoked'] else [])
    if unknown:
        causes.append('START_UNDETERMINED')
    c.need(pair or deadline or audit['revoked'], 'decision evidence still open')
    conditions = dict(VERIFICATION_INVALIDATING=bool(causes), EXECUTION_FAILED=False,
                      BUDGET_EXHAUSTED=False, DEADLINE_REACHED=deadline, EVIDENCE_EXHAUSTED=pair)
    condition = next(rule for rule in s3_results.RULES if conditions[rule])
    comparison = 'NO_PAIR'
    if pair:
        comparison = 'CONCORDANT' if executor['outcome'] == auditor['outcome'] else 'DISCORDANT'
    return dict(receipt=task['rid'], profile=profile_ref(task_traps=check_bundle(task['bundle'])), evaluated_at=now,
                assumption_evaluation=dict(status='INVALIDATING' if causes else 'COMPLETE',
                                           causes=causes, unknown_starts=unknown),
                conditions=[[rule, conditions[rule]] for rule in s3_results.RULES],
                method_observation=comparison, condition=condition,
                terminal='EXPIRED' if condition == 'DEADLINE_REACHED' else 'UNRESOLVED')


class Ledger(s2.Ledger):
    def __init__(self, path, cfg, private, clock, create=False, hook=None):
        c.need(callable(clock), 'S3b requires a pinned test clock')
        super().__init__(path, cfg, private, clock=clock, create=create, hook=hook)

    @staticmethod
    def transition(cfg, state, req, now, events, clock=None):
        s2.fields(req, s2.REQUEST)
        op = req['op']
        c.need(type(op) is str, 'S3b operation')
        if op not in ACTIONS:
            c.need(op != 'FENCE', 'use S3_FINALIZE for S3b')
            if op in ('ACTIVATE', 'CONSUME'):
                body = req['body']
                s2.fields(body, s2.ACTIONS[op])
                s2.pin(body['receipt'])
                task = state['tasks'].get(body['receipt'].hex())
                c.need(task is not None and not task['audit']['revoked'], 'S3b source unavailable')
            nxt, result = s2.reduce(cfg, state, req, now)
            if op == 'CREATE' and nxt is not state:
                check_bundle(req['body']['bundle'])
                nxt['tasks'][result['receipt'].hex()]['audit'] = initial_audit()
            if op == 'QUERY':
                audit = nxt['tasks'][req['body']['receipt'].hex()]['audit']
                result['audit'] = copy.deepcopy(audit)
                result['task']['terminal'] = audit['decision'].get('terminal', 'PENDING')
                settled = nxt['tasks'][req['body']['receipt'].hex()].get('settlement')
                if settled is not None:
                    result['task']['settlement'] = 'COMMITTED'
                    result['settlement'] = copy.deepcopy(settled)
            return nxt, result, now

        record = s2.verify_request(cfg, req, now, ACTIONS)
        body = req['body']
        s2.pin(body['receipt'])
        task = state['tasks'].get(body['receipt'].hex())
        c.need(task is not None and 'audit' in task, 'unknown S3b receipt')
        audit = task['audit']
        actor = req['actor']
        nonce = actor.hex() + ':' + req['nonce'].hex()
        previous = state['nonces'].get(nonce)
        if previous is not None:
            c.need(previous['request'] == s2.h(req), 'idempotency conflict')

        role = None
        if op in ('S3_FINALIZE', 'S3_REVOKE', 'S3_SETTLE', 'S3_SETTLEMENT_STATUS'):
            c.need(actor == f.principal_digest(cfg['requester']), 'S3b requester role')
        else:
            role = body['role']
            c.need(type(role) is str and role in s2.ROLES, 'S3b provider role')
            expected = role_binding(task, events, role)
            c.need(actor == task['leases'][role]['proposal']['provider'], 'S3b signer binding')
            c.need(c.encode({key: body[key] for key in ROLE_BINDING}) == c.encode(expected),
                   'S3b submission binding')
            if op != 'S3_START':
                c.need(body['start'] == audit['starts'].get(role), 'S3b start reference')
                if op == 'S3_RESULT':
                    s3_results.outcome_check(body['outcome'], task['bundle']['receipt']['execution'],
                                             allow_traps=check_bundle(task['bundle']))
                else:
                    c.need(body['reason'] in ('IO', 'RESOURCE', 'INTERRUPTED'), 'S3b fault reason')

        received_at = clock() if clock else now
        s2.uint(received_at)
        c.need(received_at >= max(now, state['last_time']), 'authority clock rollback')
        s2.check_request_time(cfg, req, record, received_at)
        if previous is not None:
            return state, previous['result'], received_at

        if op == 'S3_SETTLEMENT_STATUS':
            if 'settlement' in task:
                return state, dict(status='COMMITTED', settlement=task['settlement']), received_at
            status = 'READY' if audit['decision'] else 'AWAITING_TERMINAL'
            return state, dict(status=status), received_at
        if op == 'S3_SETTLE':
            if 'settlement' in task:
                return state, task['settlement'], received_at
            nxt, result = s3_settlement.settle(cfg, state, task, events, actor)
            nxt['last_time'] = received_at
            nxt['nonces'][nonce] = dict(request=s2.h(req), result=result)
            c.decode(c.encode(nxt))
            return nxt, result, received_at

        identity = s2.h([SCHEMA, op, body])
        if op == 'S3_FINALIZE' and audit['decision']:
            return state, audit['decision'], received_at
        if op == 'S3_REVOKE' and audit['revoked']:
            return state, dict(revoked=True), received_at
        if op == 'S3_START' and audit['starts'].get(role) == identity:
            return state, dict(start=identity), received_at
        slot = audit['slots'].get(role)
        if slot and slot['identity'] == identity:
            return state, slot, received_at

        c.need(not audit['decision'], 'S3b terminal already committed')
        nxt = copy.deepcopy(state)
        updated = nxt['tasks'][body['receipt'].hex()]
        view = updated['audit']
        if op == 'S3_FINALIZE':
            result = evaluate(task, received_at)
            view.update(phase='TERMINAL', decision=result)
            updated['fenced'] = True
            for lease in updated['leases'].values():
                lease['state'] = 'FENCED'
        elif op == 'S3_REVOKE':
            view['revoked'] = True
            result = dict(revoked=True)
        else:
            c.need(received_at < task['bundle']['receipt']['execution']['deadline'], 'S3b deadline')
            c.need(task['leases'][role]['state'] == 'CONSUMED' and not audit['revoked'],
                   'S3b lease or source unavailable')
            if op == 'S3_START':
                c.need(role not in view['starts'], 'S3b start already recorded')
                view['starts'][role] = identity
                if role == 'AUDITOR':
                    view['phase'] = 'RUNNING'
                result = dict(start=identity)
            elif slot:
                result = dict(conflict=True, accepted=slot['identity'])
                if role in view['conflicts']:
                    return state, result, received_at
                view['conflicts'][role] = identity
            else:
                cost = task['bundle']['funding'][BUCKET[role]] if op == 'S3_RESULT' else 0
                c.need(admission.within_funding_cap(view['accepted_cost'], cost, task['funding_held']),
                       'S3b admission budget')
                result = dict(identity=identity, kind=op, received_at=received_at, cost=cost)
                if op == 'S3_RESULT':
                    result['outcome'] = body['outcome']
                view['slots'][role] = result
                view['accepted_cost'] += cost

        nxt['last_time'] = received_at
        nxt['nonces'][nonce] = dict(request=s2.h(req), result=result)
        c.decode(c.encode(nxt))
        return nxt, result, received_at


def verify_snapshot(cfg, snapshot, anchor):
    c.need(anchor is not None, 'S3b independently saved checkpoint required')
    return s2_evidence.verify(cfg, snapshot, anchor, transition=Ledger.transition)
