# SPDX-License-Identifier: Apache-2.0
"""Candidate Phase D encoding and read-only projection of verified R11 rows."""

import copy
from tools.verification_profile import codec as c, profile

VERSION = 'ACLt/PhaseD/Candidate/1'


def digest(kind, value):
    return c.domain_hash(f'{VERSION}/{kind}', c.encode(value))


def project(config_pin, row):
    """Encode an R11 row returned by the authenticated bridge, never a peer claim."""
    legacy = bytes.fromhex(row['phase_d_source_cbor_hex'])
    legacy_digest = c.domain_hash('ACLt/TEST/R11/PhaseDSource/1', legacy)
    c.need(c.digest_consistency(legacy_digest.hex() == row['phase_d_source_digest']), 'legacy source digest')
    source = c.decode(legacy)
    evidence = source['projection']
    context = dict(
        deployment_digest=c.digest_bytes(config_pin), receipt_id=evidence['receipt'],
        profile_digest=evidence['profile'], log_id=source['genesis'],
        cutoff_seq=source['cutoff_seq'], cutoff_head=source['cutoff_head'],
        cutoff_state_digest=source['pre_state_digest'],
    )
    data = dict(
        context=context, evaluated_at=evidence['instant'], deadline=evidence['deadline'],
        funding_cap=evidence['funding_cap'], method_input=evidence['method_input'],
        minimum_accepted_results=evidence['minimum_accepted_results'],
        invalidating_causes=evidence['causes'],
    )
    if 'funding_event_ref' in evidence['boundary']:
        data['funding_event_ref'] = evidence['boundary']['funding_event_ref']
    if evidence['instant'] >= evidence['deadline']:
        c.need('deadline_event_ref' in evidence['boundary'], 'missing legacy deadline observation')
        data['deadline_observation_ref'] = digest(
            'DeadlineObservation', [context, evidence['deadline'], evidence['instant']])
    else:
        c.need('deadline_event_ref' not in evidence['boundary'], 'premature legacy deadline observation')
    if 'execution_closure' in evidence:
        observed = evidence['execution_closure']
        body = dict(
            context=context,
            source_contract='ACLt/PhaseD/Candidate/1/FM-S3Observer',
            attempts_observed=observed['attempts_observed'],
            valid_submission_count=observed['valid_submission_count'],
            recovery_exhausted_event=evidence['closure_event'],
        )
        data['execution_closure'] = dict(body, closure_digest=digest('ExecutionClosure', body))

    input_digest = digest('EvaluationInput', data)
    conditions = evidence['conditions']
    c.need(set(conditions) == set(profile.AUDIT_CONDITIONS), 'audit condition coverage')
    vector = [
        dict(condition=name, value=conditions[name],
             reason_digest=digest('DecisionReason', [input_digest, name, conditions[name]]))
        for name in profile.AUDIT_CONDITIONS
    ]
    winner = next((item['condition'] for item in vector if item['value']), None)
    c.need(winner is not None and winner == row['condition']
           and profile.TERMINALS[winner] == row['terminal'], 'legacy decision mismatch')
    return dict(version=VERSION, evaluation_input=data, input_digest=input_digest,
                condition_vector=vector, selected_condition=winner,
                derived_terminal=profile.TERMINALS[winner])


def comparison_projection(value):
    """Retain actual inputs and decisions while treating generated SHA fields as records."""
    result = copy.deepcopy(value)
    def record(mapping, key):
        c.digest_bytes(mapping[key])
        mapping[key] = bytes(32)
    def context(value):
        for key in ('deployment_digest', 'profile_digest', 'log_id',
                    'cutoff_head', 'cutoff_state_digest'):
            record(value, key)
    record(result, 'input_digest')
    data = result['evaluation_input']
    context(data['context'])
    if 'deadline_observation_ref' in data:
        record(data, 'deadline_observation_ref')
    if 'execution_closure' in data:
        closure = data['execution_closure']
        context(closure['context'])
        record(closure, 'closure_digest')
    c.need(type(result['condition_vector']) is list, 'condition vector array')
    for row in result['condition_vector']:
        record(row, 'reason_digest')
    return result


def verify(projected_bytes, config_pin, verified_row):
    """Compare actual values, field sets and decisions against replayed evidence."""
    message = 'candidate bytes differ from authenticated replay'
    try:
        candidate = comparison_projection(c.decode(projected_bytes))
        expected = comparison_projection(project(config_pin, verified_row))
        matches = c.encode(candidate) == c.encode(expected)
    except (KeyError, TypeError, ValueError) as exc:
        raise c.CodecError(message) from exc
    c.need(matches, message)
