# SPDX-License-Identifier: Apache-2.0
"""Phase D replay over explicitly projected audit TEST evidence."""
import hashlib

from tools.verification_profile import admission, codec as c, commitments as binding
from tools.verification_profile import profile as profiles, registration as registration
from tools.verification_profile import selection
from tools.verification_profile.event_frontier import ancestors

EVALUATOR_ID = 'acl.evaluator.r10-audit-test'
CLOSURE_ID = 'acl.closure.r10-execution-test'
CLOSURE_DOMAIN = 'ACLt/TEST/R10/ExecutionClosure/1'
REASON_DOMAIN = 'ACLt/TEST/R10/DecisionReason/1'


def contract_ref(identifier):
    return dict(id=identifier, version=[1, 0, 0],
                digest=hashlib.sha256(identifier.encode()).digest())


def closure_digest(record):
    return c.domain_hash(CLOSURE_DOMAIN, c.encode(
        {name: value for name, value in record.items() if name != 'closure_digest'}))


def execution_condition(observation, receipt_id, events, visible, admitted):
    """Interpret a TEST closure at the supplied frontier."""
    try:
        tag = observation['tag']
        if tag == 'NOT_APPLICABLE':
            c.fields(observation, ('tag',))
            return None
        if tag == 'SOURCE_UNAVAILABLE':
            c.fields(observation, ('tag', 'failure'))
            failure = observation['failure']
            c.fields(failure, ('dependency_ref', 'failure_class'))
            c.fields(failure['dependency_ref'], ('id', 'version', 'digest'))
            c.text(failure['dependency_ref']['id'])
            c.semver(failure['dependency_ref']['version'])
            c.digest_bytes(failure['dependency_ref']['digest'])
            c.need(failure['failure_class'] in ('UNAVAILABLE', 'MALFORMED', 'UNTRUSTED_SOURCE'),
                   'execution failure class')
            return admission.INVALIDATING
        c.need(tag == 'CLOSURE', 'execution tag')
        c.fields(observation, ('tag', 'record'))
        record = observation['record']
        c.fields(record, ('receipt_id', 'execution_contract_ref', 'attempts_observed',
                          'valid_submission_count', 'recovery_exhausted_event', 'closure_digest'))
        c.uint(record['attempts_observed'])
        c.uint(record['valid_submission_count'])
        c.need(record['valid_submission_count'] <= record['attempts_observed'], 'closure counts')
        c.need(record['receipt_id'] == receipt_id and
               c.encode(record['execution_contract_ref']) == c.encode(contract_ref(CLOSURE_ID)) and
               record['closure_digest'] == closure_digest(record), 'closure binding')
        key = c.encode(record['recovery_exhausted_event'])
        subject = dict(tag='RECEIPT', id=receipt_id)
        c.need(key in visible and events[key]['event_kind'] == 'EXECUTION_EXHAUSTED' and
               events[key]['subject_ref'] == subject, 'closure event')
        if record['valid_submission_count'] > 0:
            return None
        c.need(not admitted and not any(
            events[ref]['event_kind'] == 'VERIFICATION_STARTED' and
            events[ref]['subject_ref'] == subject for ref in visible), 'contradictory closure')
        return 'EXECUTION_FAILED'
    except (c.CodecError, KeyError, TypeError):
        return admission.INVALIDATING


def audit_evaluate(canonical_input, deadline, cap, instant):
    """Recompute admission, byte equality and aggregate from ordered TEST rows."""
    c.fields(canonical_input, ('expected_result', 'evidence'))
    expected = canonical_input['expected_result']
    c.decode(expected)
    evidence = canonical_input['evidence']
    c.need(type(evidence) is list, 'evidence array')
    seen = set()
    outcomes = []
    committed = 0
    previous = -(2**63)
    for row in evidence:
        c.fields(row, ('attempt_id', 'received_at', 'cost', 'validation_passed', 'result'))
        attempt = row['attempt_id']
        c.need(type(attempt) is bytes and attempt and attempt not in seen, 'duplicate or invalid attempt')
        seen.add(attempt)
        instant_at = row['received_at']
        eligible = admission.evidence_admissible(
            instant_at, deadline, committed, row['cost'], cap, row['validation_passed'])
        c.need(previous <= instant_at <= instant, 'evidence instant order')
        previous = instant_at
        c.need(type(row['result']) is bytes, 'result bytes')
        if eligible:
            c.decode(row['result'])
            committed += row['cost']
            outcomes.append('CONCORDANT' if row['result'] == expected else 'DISCORDANT')
    return outcomes, dict(admitted=len(outcomes), concordant=outcomes.count('CONCORDANT'),
                          discordant=outcomes.count('DISCORDANT'), committed_cost=committed)


def replay(value, schema_pin, contract_pin):
    c.fields(value, ('envelope', 'schema_lock', 'schema_documents', 'decision_contract'))
    imports = binding.Imports(value['schema_lock'], value['schema_documents'], schema_pin)
    contract = value['decision_contract']
    c.fields(contract, ('name', 'receipt_binding', 'deadline', 'funding_cap'))
    c.need(contract['name'] == 'r10-audit-decision-test@1' and
           hashlib.sha256(c.encode(contract)).digest() == contract_pin, 'decision contract pin')
    registration.typed(contract['deadline'], 'int', imports)
    c.uint(contract['funding_cap'])
    envelope = value['envelope']
    c.fields(envelope, ('phase', 'bundle', 'profile', 'evaluation_input'))
    c.need(envelope['phase'] == 'D', 'Phase D required')
    profile = envelope['profile']
    profiles.verify_digest(profile)
    profiles.audit_fields(profile)
    equivalence = profile['result_equivalence']
    c.need(equivalence['equivalence_id'] == 'acl.eq.exact@1' and
           equivalence['canonical_encoding_id'] == c.ENCODING and
           equivalence['relation_kind'] == 'CANONICAL_BITWISE' and
           equivalence['totality'] == 'TOTAL', 'audit TEST exact equivalence')
    binding.common.check_assumptions(profile['assumption_references'], imports)
    data = envelope['evaluation_input']
    input_digest = binding.decision_input_digest(data, imports)
    assurance = data['assurance_profile']
    binding.check_digest(assurance, 'MainnetAssuranceProfile', imports)
    receipt = data['receipt_binding']
    c.need(c.encode(receipt) == c.encode(contract['receipt_binding']) and
           receipt['profile_ref'] == data['profile_ref'] == selection.profile_ref(profile) and
           receipt['network_id'] == assurance['network_id'] and
           receipt['assurance_profile_ref'] == binding.identity(assurance), 'Receipt binding')
    receipt_id = receipt['receipt_id']
    bundle = envelope['bundle']
    registration.typed(bundle, 'ReferencesBundle', imports)
    registration.check_registry(bundle['registry_snapshot'])
    context = bundle['context']
    c.need(context['registry_snapshot_ref'] == binding.identity(bundle['registry_snapshot']),
           'registry context')
    frontier = bundle['event_frontier_snapshot']
    header = frontier['header']
    c.need(header['digest'] == registration.frontier_digest(frontier) and
           context['event_frontier_ref'] == {name: header[name] for name in ('id', 'digest')},
           'frontier commitment')
    frontier_valid = True
    try:
        registration.check_frontier(frontier, imports)
        boundary = admission.resolve_boundary(data['boundary_observation'], frontier, receipt_id)
    except c.CodecError:
        frontier_valid = False
        boundary = admission.INVALIDATING
    invalidating = boundary == admission.INVALIDATING
    instant = context['evaluation_instant']
    assumption = binding.check_states(profile, data['assumption_evaluation'], imports)
    if assumption is None:
        invalidating = True
    else:
        c.need(assumption['receipt_id'] == receipt_id and assumption['evaluation_instant'] == instant and
               assumption['reducer_ref'] == assurance['assumption_verdict_reducer_ref'],
               'assumption binding')
        safety = {row['assumption_id'] for row in profile['assumption_references']
                  if row['role'] == 'SAFETY_CRITICAL'}
        invalidating |= any(row['assumption_id'] in safety and row['effective_verdict'] != 'VALID'
                            for row in assumption['assumption_states'])

    method = data['method_evaluation']
    reference = contract_ref(EVALUATOR_ID)
    outcomes, aggregate = [], dict(admitted=0, concordant=0, discordant=0, committed_cost=0)
    if method['evaluator_ref'] != reference or reference not in assurance['allowed_validator_refs']:
        invalidating = True
    else:
        schema = imports.refs.get('NativeValue')
        c.need(schema is not None and all(method[name]['schema_ref'] == schema for name in
               ('canonical_input', 'claimed_outcome', 'claimed_aggregate')), 'audit TEST native schema')
        try:
            outcomes, aggregate = audit_evaluate(binding.external_value(method['canonical_input'], imports),
                                                 contract['deadline'], contract['funding_cap'], instant)
        except (c.CodecError, TypeError):
            invalidating = True
        else:
            c.need(method['claimed_outcome']['canonical_bytes'] == c.encode(outcomes) and
                   method['claimed_aggregate']['canonical_bytes'] == c.encode(aggregate), 'method replay mismatch')

    execution = None
    if frontier_valid:
        events = {c.encode(row['event_ref']): row for row in frontier['event_records']}
        visible = ancestors(events, c.encode(frontier['frontier_event_ref']))
        execution = execution_condition(data['execution_observation'], receipt_id, events,
                                        visible, aggregate['admitted'])
    invalidating |= execution == admission.INVALIDATING
    minimum = profile['method_parameters']['min_reexecutions']
    c.need(minimum > 0, 'audit TEST minimum must be positive')
    conditions = {
        admission.INVALIDATING: invalidating,
        'EXECUTION_FAILED': execution == 'EXECUTION_FAILED',
        admission.FUNDING: boundary == admission.FUNDING,
        admission.DEADLINE: boundary == admission.DEADLINE,
    }
    conditions['EVIDENCE_EXHAUSTED'] = not any(conditions.values()) and aggregate['admitted'] >= minimum
    vector = []
    for condition in profile['decision_mapping']['rules']:
        active = conditions[condition]
        reason = c.domain_hash(REASON_DOMAIN, c.encode(
            [input_digest, header['digest'], contract_pin, instant, condition, active]))
        vector.append(dict(condition=condition, value=active, reason_digest=reason))
    winner = next((row['condition'] for row in vector if row['value']), None)
    terminal = profiles.TERMINALS[winner] if winner else profile['decision_mapping']['default']
    result = dict(input_digest=input_digest, condition_vector=vector, derived_terminal=terminal)
    if winner is not None:
        result['selected_condition'] = winner
    return result


def inspect(raw, schema_pin, contract_pin):
    try:
        request = c.decode(raw)
        c.fields(request, ('envelope', 'schema_lock', 'schema_documents', 'decision_contract', 'decision'))
        result = replay({key: value for key, value in request.items() if key != 'decision'},
                        schema_pin, contract_pin)
        claim = request['decision']
        c.fields(claim, ('evaluation_record', 'terminal_state'))
        c.need(c.encode(claim['evaluation_record']) == c.encode(result) and
               claim['terminal_state'] == result['derived_terminal'], 'decision replay mismatch')
        return dict(record_sha256=hashlib.sha256(c.encode(result)).hexdigest(),
                    terminal=result['derived_terminal'],
                    selected_condition=result.get('selected_condition', ''),
                    production_admission=False, state_committed=False)
    except (KeyError, TypeError, RecursionError) as error:
        raise c.CodecError('malformed Phase D input') from error
