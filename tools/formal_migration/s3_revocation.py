# SPDX-License-Identifier: Apache-2.0
"""One-way deployment revocation in the fixed non-mainnet test ledger."""
import copy

from tools.formal_migration import foundation, s2
from tools.verification_profile import codec as c

OPERATION = 'S3_REVOKE_DEPLOYMENT'
SIGNATURE_KIND = 'DEPLOYMENT_REVOCATION_V1'
ACTIONS = {OPERATION: {'issuer_signature'}}


def statement(config):
    return dict(version=s2.DEPLOYMENT_REVOCATION, genesis=s2.h(config))


def transition(config, state, request, now, clock):
    c.need(config.get('revocation_version') == s2.DEPLOYMENT_REVOCATION,
           'deployment revocation contract disabled')
    principal = s2.verify_request(config, request, now, ACTIONS)
    c.need(request['actor'] == foundation.principal_digest(config['requester']),
           'deployment revocation submitter')
    expected = statement(config)
    s2.verify_signature(config['issuer_der'], SIGNATURE_KIND, expected,
                        request['body']['issuer_signature'])

    committed_at = clock() if clock else now
    s2.uint(committed_at)
    c.need(committed_at >= max(now, state['last_time']), 'authority clock rollback')
    s2.check_request_time(config, request, principal, committed_at)
    nonce = request['actor'].hex() + ':' + request['nonce'].hex()
    if nonce in state['nonces']:
        c.need(state['nonces'][nonce]['request'] == s2.h(request), 'idempotency conflict')
    if 'deployment_revocation' in state:
        return state, state['deployment_revocation'], committed_at

    updated = copy.deepcopy(state)
    result = dict(expected, committed_at=committed_at)
    updated['deployment_revocation'] = result
    for task in updated['tasks'].values():
        if not task['audit']['decision']:
            task['audit']['revoked'] = True
    updated['last_time'] = committed_at
    updated['nonces'][nonce] = dict(request=s2.h(request), result=result)
    c.encode(updated)
    return updated, result, committed_at
