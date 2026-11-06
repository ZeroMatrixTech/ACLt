# SPDX-License-Identifier: Apache-2.0
"""Candidate execution exhaustion facts for a single, non-retryable attempt."""
from tools.formal_migration import foundation as f, s2
from tools.verification_profile import codec as c

CONTRACT = 'RIR_TEST_NO_RETRY_CLOSURE_V1'
SIGNATURE_DOMAIN = 'ACLt/FM/S3/ExecutionClosureObservation/1'
FAULT = 'HOST_RESOURCE_EXHAUSTED'


def check_observer_key(cfg, der):
    c.need(type(der) is bytes and len(der) == 294 and der.startswith(f.SPKI_PREFIX)
           and der.endswith(f.SPKI_SUFFIX), 'closure observer key shape')
    role_keys = [cfg['issuer_der'], cfg['requester']['public_key_der'],
                 *(role['public_key_der'] for role in cfg['providers'].values())]
    c.need(der not in role_keys, 'closure observer must have a separate key')


def observation(cfg, binding, start):
    return dict(contract=CONTRACT, genesis=s2.h(cfg), binding=binding, start=start,
                runtime=cfg['runtime_sha256'], status='HOST_FAULT', code=FAULT)


def validate(cfg, task, profile, binding, body):
    der = profile.get('closure_observer_der')
    check_observer_key(cfg, der)
    audit = task['audit']
    c.need(task['leases']['EXECUTOR']['state'] == 'CONSUMED' and
           task['leases']['AUDITOR']['state'] != 'CONSUMED' and
           audit['phase'] == 'BEFORE_VERIFICATION' and 'AUDITOR' not in audit['starts'],
           'closure requires spent executor attempt before verification')
    c.need('EXECUTOR' in audit['starts'], 'closure requires executor entry binding')
    valid = sum(slot['kind'] == 'S3_RESULT' for slot in audit['slots'].values())
    c.need(valid == 0, 'closure requires zero valid submissions')
    expected = observation(cfg, binding, audit['starts']['EXECUTOR'])
    c.need(c.encode(body['observation']) == c.encode(expected), 'closure observation binding')
    s2.verify_signature(der, SIGNATURE_DOMAIN, expected, body['observer_signature'])
    return dict(kind='EXECUTION_EXHAUSTED', receipt_id=task['rid'],
                execution_contract_ref=CONTRACT, attempts_observed=1,
                valid_submission_count=valid, observation_digest=s2.h(expected),
                request_identity=s2.h(body))


def exhaustion_event(events, record):
    matches = []
    for raw in events:
        event = c.decode(raw)
        req = event['request']
        if req['op'] == 'S3_CLOSE_EXECUTION' and req['body']['receipt'] == record['receipt_id']:
            c.need(event['result_digest'] == s2.h(record), 'closure result digest')
            matches.append(s2.h(event))
    c.need(len(matches) == 1, 'closure requires one exhaustion event')
    return matches[0]
