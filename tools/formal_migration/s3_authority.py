# SPDX-License-Identifier: Apache-2.0
"""Bounded S3b test authority over the S2 transaction and event chain."""
import copy

from tools.formal_migration import foundation as f, policy as p, s2, s2_evidence, s3_closure, s3_results, s3_settlement
from tools.formal_migration import s3_revocation, s3_terminals
from tools.verification_profile import admission, codec as c

SCHEMA = 'ACLt/FM/S3b/1'
ROLE_BINDING = {'receipt', 'profile', 'role', 'assignment', 'epoch', 'intent', 'consume_event'}
ACTIONS = {
    'S3_START': ROLE_BINDING,
    'S3_ENTRY': ROLE_BINDING | {'entry'},
    'S3_RESULT': ROLE_BINDING | {'start', 'outcome'},
    'S3_HOST_FAULT': ROLE_BINDING | {'start', 'reason'},
    'S3_REVOKE': {'receipt'},
    'S3_FINALIZE': {'receipt'},
    'S3_CLOSE_EXECUTION': {'receipt', 'observation', 'observer_signature'},
    'S3_SETTLE': {'receipt'},
    'S3_SETTLEMENT_STATUS': {'receipt'},
}
BUCKET = {'EXECUTOR': 'execution_limit', 'AUDITOR': 'verification_limit'}
TERMINAL = {'VERIFICATION_INVALIDATING': 'UNRESOLVED', 'EXECUTION_FAILED': 'FAILED',
            'BUDGET_EXHAUSTED': 'FUNDING_EXHAUSTED', 'DEADLINE_REACHED': 'EXPIRED',
            'EVIDENCE_EXHAUSTED': 'UNRESOLVED'}


def profile(*, task_traps=False, closure_observer_der=None, rpr_entry=False, funding_boundary=False):
    value = s3_results.profile()
    for key in ('verified_claim_spec', 'safety_parameters', 'liveness_parameters'):
        del value[key]
    value.update(schema=SCHEMA, start_source='PINNED_PROVIDER_TEST_ENTRY_ATTESTATION',
                 conflict_limit_per_role=1, acceptance_cost='RESERVE_ROLE_BUCKET',
                 clock='PINNED_MONOTONIC_TEST_TIME')
    if task_traps:
        value['task_outcomes'] = 'RIR_OK_ABORT_AND_TRAPS_V1'
    if closure_observer_der is not None:
        value.update(execution_closure=s3_closure.CONTRACT, closure_observer_der=closure_observer_der)
    if rpr_entry:
        value.update(start_source=s3_terminals.ENTRY_SOURCE, rpr_entry=s3_terminals.ENTRY_CONTRACT)
    if funding_boundary:
        value.update(funding_boundary=s3_terminals.FUNDING_CONTRACT,
                     boundary_resolution=s3_terminals.BOUNDARY_RESOLUTION)
    return value


def profile_ref(bundle):
    return c.domain_hash(SCHEMA + '/PROFILE', c.encode(check_bundle(bundle)))


def bind_bundle(bundle, *, task_traps=False, closure_observer_der=None, rpr_entry=False,
                funding_boundary=False):
    value = copy.deepcopy(bundle)
    for component in value['components']:
        if component['kind'] == 'AUDIT_CONTRACT':
            component['content'] = c.encode(profile(task_traps=task_traps, closure_observer_der=closure_observer_der,
                                                    rpr_entry=rpr_entry, funding_boundary=funding_boundary))
    value['receipt']['component_refs'] = [p.ref(x['kind'], x) for x in value['components']]
    p.bundle(value)
    return value


def check_bundle(bundle):
    component = next(x for x in bundle['components'] if x['kind'] == 'AUDIT_CONTRACT')
    value = c.decode(component['content'])
    c.need(type(value) is dict, 'S3b profile object required')
    expected = profile(task_traps='task_outcomes' in value,
                       closure_observer_der=value.get('closure_observer_der'),
                       rpr_entry='rpr_entry' in value, funding_boundary='funding_boundary' in value)
    c.need(component['content'] == c.encode(expected), 'S3b profile required')
    return value


def uses(bundle, field):
    return field in check_bundle(bundle)


def initial_audit():
    return dict(phase='BEFORE_VERIFICATION', starts={}, slots={}, conflicts={},
                accepted_cost=0, revoked=False, decision={})


def role_binding(task, events, role):
    lease = task['leases'][role]
    prop = lease['proposal']
    return dict(receipt=task['rid'], profile=profile_ref(task['bundle']), role=role,
                assignment=prop['assignment'], epoch=prop['epoch'], intent=lease['intent'],
                consume_event=s3_results.consumed_event({'events': events}, prop['assignment'], lease['intent']))


def evaluate(task, now, events):
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
    closure = audit.get('execution_closure')
    event = s3_closure.exhaustion_event(events, closure) if closure else None
    funding = audit.get('funding_boundary')
    c.need(pair or deadline or audit['revoked'] or event is not None or funding is not None,
           'decision evidence still open')
    budget, deadline_condition, boundary = False, deadline, None
    if uses(task['bundle'], 'funding_boundary'):
        resolved, observation, frontier = s3_terminals.resolve(task, events, now)
        if resolved == admission.INVALIDATING:
            causes.append('BOUNDARY_UNRESOLVED')
        budget = resolved == admission.FUNDING
        deadline_condition = resolved == admission.DEADLINE
        boundary = dict(observation=observation, resolved=resolved or 'NONE', frontier=frontier)
    conditions = dict(VERIFICATION_INVALIDATING=bool(causes), EXECUTION_FAILED=event is not None,
                      BUDGET_EXHAUSTED=budget, DEADLINE_REACHED=deadline_condition, EVIDENCE_EXHAUSTED=pair)
    condition = next(rule for rule in s3_results.RULES if conditions[rule])
    comparison = 'NO_PAIR'
    if pair:
        comparison = 'CONCORDANT' if executor['outcome'] == auditor['outcome'] else 'DISCORDANT'
    result = dict(receipt=task['rid'], profile=profile_ref(task['bundle']), evaluated_at=now,
                assumption_evaluation=dict(status='INVALIDATING' if causes else 'COMPLETE',
                                           causes=causes, unknown_starts=unknown),
                conditions=[[rule, conditions[rule]] for rule in s3_results.RULES],
                method_observation=comparison, condition=condition,
                terminal=TERMINAL[condition])
    if event is not None:
        result['execution_observation'] = dict(record=closure, recovery_exhausted_event=event)
    if uses(task['bundle'], 'rpr_entry'):
        result['start_states'] = s3_terminals.start_states(task, final=True)
    if boundary is not None:
        result['boundary'] = boundary
    return result


class Ledger(s2.Ledger):
    def __init__(self, path, cfg, private, clock, create=False, hook=None):
        c.need(callable(clock), 'S3b requires a pinned test clock')
        super().__init__(path, cfg, private, clock=clock, create=create, hook=hook)

    @staticmethod
    def transition(cfg, state, req, now, events, clock=None):
        s2.fields(req, s2.REQUEST)
        op = req['op']
        c.need(type(op) is str, 'S3b operation')
        if op == s3_revocation.OPERATION:
            return s3_revocation.transition(cfg, state, req, now, clock)
        if op not in ACTIONS:
            c.need(op != 'FENCE', 'use S3_FINALIZE for S3b')
            if op in ('ACTIVATE', 'CONSUME'):
                body = req['body']
                s2.fields(body, s2.ACTIONS[op])
                s2.pin(body['receipt'])
                task = state['tasks'].get(body['receipt'].hex())
                c.need(task is not None and not task['audit']['revoked'] and
                       'execution_closure' not in task['audit'], 'S3b source unavailable')
                if uses(task['bundle'], 'funding_boundary'):
                    if op == 'ACTIVATE':
                        handled = s3_terminals.activation(cfg, state, req, now, task, events)
                        if handled is not None:
                            return handled
                    c.need('funding_boundary' not in task['audit'], 'S3 funding boundary recorded')
            if op == 'CREATE_BOUND':
                from tools.formal_migration import deployment_creation
                nxt, result = s2.reduce(cfg, state, req, now, create_bound=deployment_creation.verify)
            else:
                nxt, result = s2.reduce(cfg, state, req, now)
            if op in ('CREATE', 'CREATE_BOUND') and nxt is not state:
                contract = check_bundle(req['body']['bundle'])
                if 'closure_observer_der' in contract:
                    s3_closure.check_observer_key(cfg, contract['closure_observer_der'])
                nxt['tasks'][result['receipt'].hex()]['audit'] = initial_audit()
            if op == 'QUERY':
                queried = nxt['tasks'][req['body']['receipt'].hex()]
                audit = queried['audit']
                result['audit'] = copy.deepcopy(audit)
                if uses(queried['bundle'], 'rpr_entry'):
                    result['start_states'] = (audit['decision']['start_states'] if audit['decision']
                                              else s3_terminals.start_states(queried))
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
        closure_record = None
        if op in ('S3_FINALIZE', 'S3_REVOKE', 'S3_SETTLE', 'S3_SETTLEMENT_STATUS', 'S3_CLOSE_EXECUTION'):
            c.need(actor == f.principal_digest(cfg['requester']), 'S3b requester role')
            if op == 'S3_CLOSE_EXECUTION' and 'execution_closure' not in audit:
                contract = check_bundle(task['bundle'])
                c.need('closure_observer_der' in contract, 'closure source unavailable')
                closure_record = s3_closure.validate(cfg, task, contract,
                    role_binding(task, events, 'EXECUTOR'), body)
        else:
            role = body['role']
            c.need(type(role) is str and role in s2.ROLES, 'S3b provider role')
            expected = role_binding(task, events, role)
            c.need(actor == task['leases'][role]['proposal']['provider'], 'S3b signer binding')
            c.need(c.encode({key: body[key] for key in ROLE_BINDING}) == c.encode(expected),
                   'S3b submission binding')
            entry_contract = uses(task['bundle'], 'rpr_entry')
            if op == 'S3_START':
                c.need(not entry_contract, 'S3 entry contract requires a verified RPR entry')
            elif op == 'S3_ENTRY':
                c.need(entry_contract, 'S3 RPR entry requires the entry contract')
                descriptor = s3_terminals.entry_descriptor(cfg, task['bundle'], task['rid'], role)
                c.need(c.encode(body['entry']) == c.encode(descriptor), 'S3 RPR entry binding')
            else:
                c.need(body['start'] == audit['starts'].get(role), 'S3b start reference')
                if op == 'S3_RESULT':
                    s3_results.outcome_check(body['outcome'], task['bundle']['receipt']['execution'],
                                             allow_traps='task_outcomes' in check_bundle(task['bundle']))
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

        if op == 'S3_CLOSE_EXECUTION' and 'execution_closure' in audit:
            recorded = audit['execution_closure']
            c.need(recorded['request_identity'] == s2.h(body), 'conflicting execution closure')
            return state, recorded, received_at

        identity = s2.h([SCHEMA, op, body])
        if op == 'S3_FINALIZE' and audit['decision']:
            return state, audit['decision'], received_at
        if op == 'S3_REVOKE' and audit['revoked']:
            return state, dict(revoked=True), received_at
        if op in ('S3_START', 'S3_ENTRY') and audit['starts'].get(role) == identity:
            return state, dict(start=identity), received_at
        slot = audit['slots'].get(role)
        if slot and slot['identity'] == identity:
            return state, slot, received_at

        c.need(not audit['decision'], 'S3b terminal already committed')
        nxt = copy.deepcopy(state)
        updated = nxt['tasks'][body['receipt'].hex()]
        view = updated['audit']
        if op == 'S3_FINALIZE':
            result = evaluate(task, received_at, events)
            view.update(phase='TERMINAL', decision=result)
            updated['fenced'] = True
            for lease in updated['leases'].values():
                lease['state'] = 'FENCED'
        elif op == 'S3_REVOKE':
            view['revoked'] = True
            result = dict(revoked=True)
        elif op == 'S3_CLOSE_EXECUTION':
            c.need(received_at < task['bundle']['receipt']['execution']['deadline'] and
                   not audit['revoked'], 'closure source or deadline')
            result = closure_record
            view['execution_closure'] = result
        else:
            c.need('execution_closure' not in audit, 'execution already closed')
            c.need(received_at < task['bundle']['receipt']['execution']['deadline'], 'S3b deadline')
            c.need(task['leases'][role]['state'] == 'CONSUMED' and not audit['revoked'],
                   'S3b lease or source unavailable')
            if op in ('S3_START', 'S3_ENTRY'):
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
