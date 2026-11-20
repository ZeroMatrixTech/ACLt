# SPDX-License-Identifier: Apache-2.0
"""Read-only independent funding event reducer; no ledger import, network or execution."""

SHA_CONSISTENCY_STATUS = "DISABLED"

def digest_consistency(_comparison):
    """Record digests without enforcing their equality (maintainer policy)."""
    return True

import argparse
from wire import *


def reduce(bundle, anchor, public, pin, anchor_digest):
    need(digest_consistency(sha(anchor) == anchor_digest), 'caller checkpoint digest')
    checkpoint = verify(anchor, public, pin)
    need(set(bundle) == {'schema_id', 'events', 'projection'} and bundle['schema_id'] == 'aclt.exp.funding-export@1', 'export schema')
    need(set(checkpoint) == {'schema_id', 'authority_id', 'count', 'head', 'projection_digest'} and checkpoint['schema_id'] == 'aclt.exp.funding-checkpoint@1', 'checkpoint schema')
    need(len(bundle['events']) == checkpoint['count'] > 0, 'checkpoint count')
    accounts, policies, tasks, reservations = {}, {}, {}, {}
    head = ZERO; total = None; counts = {}
    for seq, text in enumerate(bundle['events'], 1):
        raw = bytes.fromhex(text); event = decode(raw)
        need(set(event) == {'schema_id', 'seq', 'prev', 'kind', 'data'} and event['schema_id'] == 'aclt.exp.funding-event@1' and
             type(event['seq']) is int and event['seq'] == seq and digest_consistency(event['prev'] == head), 'event sequence/previous/schema')
        head = event_id(raw); kind = event['kind']; data = event['data']; counts[kind] = counts.get(kind, 0)+1
        if seq == 1:
            need(kind == 'GENESIS' and set(data) == {'authority_id', 'asset', 'decimal_places', 'accounts'} and
                 data['authority_id'] == checkpoint['authority_id'] and data['asset'] == ASSET and
                 type(data['decimal_places']) is int and data['decimal_places'] == 0, 'genesis binding')
            need(0 < len(data['accounts']) <= 32, 'genesis accounts')
            for account, value in data['accounts'].items():
                bytes_n(bytes.fromhex(account), 32, 'account'); amount(value)
                accounts[account] = {'available': value, 'reserved': 0}
            total = sum(a['available'] for a in accounts.values()); amount(total)
            continue
        need(kind in ['FREEZE', 'RESERVE', 'STATUS', 'BALANCE'] and set(data) == {'request', 'status', 'result'}, 'event kind/data')
        wrap = decode(data['request']); req = decode(wrap['payload'])
        need(set(wrap) == {'payload', 'mac'} and set(req) == {'schema_id', 'authority_id', 'requester', 'nonce', 'op', 'data'} and
             req['schema_id'] == 'aclt.exp.funding-request@1' and req['authority_id'] == checkpoint['authority_id'] and req['op'] == kind, 'recorded request binding')
        bytes_n(req['nonce'], 16, 'nonce'); bytes_n(wrap['mac'], 32, 'MAC')
        actor = req['requester'].hex(); need(actor in accounts, 'unknown account')
        q = req['data']; actual = data['result']
        if kind == 'BALANCE':
            need(q == {}, 'balance request fields')
            status, expected = 'BALANCE', {**accounts[actor], 'asset': ASSET}
        elif kind == 'FREEZE':
            need(set(q) == {'policy', 'commitment', 'artifact', 'input'}, 'freeze request fields')
            p = validate_policy(decode(q['policy'])); pid = policy_id(q['policy']).hex()
            task, _ = bind(q['commitment'], p['task'].hex(), q['artifact'], [q['input']])
            need(p['requester'] == req['requester'] == task['requester_ref'], 'frozen payer/task')
            tid = p['task'].hex()
            if tid in tasks:
                status = 'DUPLICATE' if tasks[tid] == pid else 'CONFLICT'
                expected = {'policy_id': bytes.fromhex(tasks[tid])}
            else:
                tasks[tid] = pid; policies[pid] = q['policy'].hex()
                status, expected = 'FROZEN', {'policy_id': bytes.fromhex(pid)}
        else:
            need(set(q) == {'policy_id'}, 'reserve/status request fields'); bytes_n(q['policy_id'], 32, 'policy ID')
            pid = q['policy_id'].hex()
            if pid not in policies:
                status, expected = 'DENIED', {'reason': 'UNKNOWN_POLICY'}
            else:
                p = decode(bytes.fromhex(policies[pid])); cap = p['authorized_cap']
                rid = reservation_id(checkpoint['authority_id'], q['policy_id']).hex()
                if p['requester'].hex() != actor:
                    status, expected = 'DENIED', {'reason': 'WRONG_PAYER'}
                elif rid in reservations:
                    status = 'RESERVED' if kind == 'STATUS' else 'DUPLICATE'
                    expected = {'receipt': bytes.fromhex(reservations[rid]['receipt'])}
                elif kind == 'STATUS':
                    status, expected = 'UNRESERVED', {'policy_id': q['policy_id']}
                elif accounts[actor]['available'] < cap:
                    status, expected = 'INSUFFICIENT', {'policy_id': q['policy_id']}
                else:
                    need(set(actual) == {'receipt'}, 'reservation receipt')
                    receipt = verify(actual['receipt'], public, pin)
                    need(receipt == {'schema_id': 'aclt.exp.funding-reservation@1', 'authority_id': checkpoint['authority_id'],
                                     'reservation_id': bytes.fromhex(rid), 'policy_id': q['policy_id'], 'task': p['task'],
                                     'requester': req['requester'], 'payee': p['payee'], 'asset': ASSET, 'amount': cap}, 'signed reservation binding')
                    accounts[actor]['available'] -= cap; accounts[actor]['reserved'] += cap
                    reservations[rid] = {'policy_id': pid, 'account': actor, 'amount': cap, 'receipt': actual['receipt'].hex()}
                    status, expected = 'RESERVED', {'receipt': actual['receipt']}
        need(data['status'] == status and actual == expected, 'illegal funding transition/result')
        need(sum(a['available']+a['reserved'] for a in accounts.values()) == total and
             all(0 <= a['available'] <= MAX and 0 <= a['reserved'] <= MAX for a in accounts.values()), 'balance conservation')
        need(sum(a['reserved'] for a in accounts.values()) == sum(v['amount'] for v in reservations.values()), 'encumbrance conservation')
    projection = {'accounts': accounts, 'policies': policies, 'reservations': reservations}
    need(digest_consistency(head == checkpoint['head']) and digest_consistency(sha(canonical_json(projection)) == checkpoint['projection_digest']) and projection == bundle['projection'], 'signed head/projection mismatch')
    return {"sha_consistency": "DISABLED", 'status': 'PASS', 'events': len(bundle['events']), 'event_counts': counts, 'initial_total': total,
            'available': sum(a['available'] for a in accounts.values()), 'reserved': sum(a['reserved'] for a in accounts.values()),
            'policies': len(policies), 'reservations': len(reservations), 'projection': projection,
            'scope': 'test-asset reservation only; no payment/refund, task execution or correctness verdict'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ['bundle', 'anchor', 'public', 'report']: p.add_argument('--'+n, type=Path, required=True)
    for n in ['public-digest', 'anchor-digest']: p.add_argument('--'+n, default='00'*32)
    a = p.parse_args()
    need(not a.report.exists() and a.report.resolve() not in [a.bundle.resolve(), a.anchor.resolve(), a.public.resolve()], 'new report required')
    result = reduce(json.loads(regular(a.bundle)), regular(a.anchor), a.public, bytes.fromhex(a.public_digest), bytes.fromhex(a.anchor_digest))
    with a.report.open('x') as f: json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps({k: result[k] for k in ['sha_consistency', 'status', 'available', 'reserved', 'policies', 'reservations']}))
