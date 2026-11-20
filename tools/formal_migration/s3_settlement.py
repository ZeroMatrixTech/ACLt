# SPDX-License-Identifier: Apache-2.0
"""S3c settlement projection for the prefunded candidate test ledger."""
import copy

from tools.formal_migration import policy as p, s2
from tools.verification_profile import codec as c

SCHEMA = 'ACLt/FM/S3c/1'
FEE_ITEMS = (('EXECUTOR', 'execution_fee'), ('AUDITOR', 'verification_fee'))


def decision_event(task, events):
    decision = task['audit']['decision']
    c.need(task['fenced'] and task['audit']['phase'] == 'TERMINAL' and decision,
           'S3c requires a committed terminal')
    c.need(decision['receipt'] == task['rid'], 'S3c decision receipt')
    matches = []
    for raw in events:
        event = c.decode(raw)
        request = event['request']
        if request['op'] == 'S3_FINALIZE' and request['body']['receipt'] == task['rid']:
            c.need(c.digest_consistency(event['result_digest'] == s2.h(decision)), 'S3c decision event digest')
            matches.append(s2.h(event))
    c.need(len(matches) == 1, 'S3c requires exactly one terminal event')
    return matches[0]


def entitlement(cfg, receipt, kind, beneficiary, amount):
    # The business key identifies the obligation even if a proposed amount differs.
    key = c.domain_hash(SCHEMA + '/EntitlementKey',
                        c.encode([s2.h(cfg), receipt, kind, beneficiary]))
    return dict(key=key, kind=kind, beneficiary=beneficiary, amount=amount)


def settle(cfg, state, task, events, requester):
    """Derive the only settlement allowed for the task's frozen policy and facts."""
    event = decision_event(task, events)
    decision = task['audit']['decision']
    bundle = task['bundle']
    slots = task['audit']['slots']
    fulfillment = {'S3_RESULT': 'COMPLETE', 'S3_HOST_FAULT': 'HOST_FAULT'}
    statuses = {role: fulfillment[slots[role]['kind']] if role in slots else 'MISSING'
                for role in s2.ROLES}
    quote = p.quote(dict(bundle=bundle, terminal=decision['terminal'],
                         executor=statuses['EXECUTOR'], auditor=statuses['AUDITOR'],
                         storage='MISSING'))
    policy_receipt = task['rid']
    if 'creation_receipt' in task:
        from tools.formal_migration import deployment_creation
        bound = task['creation_receipt']
        c.need(c.digest_consistency(deployment_creation.receipt_id(bound) == task['rid']), 'S3c bound ReceiptID')
        policy_receipt = bound['base_receipt_digest']
    c.need(c.digest_consistency(quote['receipt_digest_hex'] == policy_receipt.hex()), 'S3c frozen receipt')
    held = task['funding_held']
    fees = {kind: int(value) for kind, value in quote['amounts'].items()}
    c.need(fees['storage_fee'] == 0, 'S3c storage disabled')
    paid = sum(fees.values())
    c.need(held == bundle['funding']['total_limit'] or (held == 0 and not slots),
           'S3c receipt funding reservation')
    c.need(paid <= held <= state['held'], 'S3c insufficient reserved funds')
    refund = int(quote['refund']) if held else 0
    c.need(paid + refund == held, 'S3c allocation conservation')

    rights = []
    for role, kind in FEE_ITEMS:
        amount = fees[kind]
        if amount:
            slot = slots.get(role, {})
            c.need(slot.get('kind') == 'S3_RESULT' and amount <= slot['cost'],
                   'S3c fee requires reserved role fulfillment')
            beneficiary = task['leases'][role]['proposal']['provider']
            rights.append(entitlement(cfg, task['rid'], kind, beneficiary, amount))
    if refund:
        rights.append(entitlement(cfg, task['rid'], 'refund', requester, refund))
    keys = {right['key'] for right in rights}
    allocated = {right['key'] for entry in state['tasks'].values()
                 for right in entry.get('settlement', {}).get('entitlements', [])}
    c.need(len(keys) == len(rights) and keys.isdisjoint(allocated), 'S3c duplicate entitlement')

    result = dict(schema=SCHEMA, receipt=task['rid'], asset=bundle['funding']['asset'],
                  terminal=decision['terminal'], decision_event=event,
                  decision_digest=s2.h(decision),
                  policy=bundle['receipt']['settlement_ref'],
                  fulfillment=dict(executor=statuses['EXECUTOR'], auditor=statuses['AUDITOR'],
                                   storage='MISSING'),
                  paid=paid, refund=refund, entitlements=rights)
    nxt = copy.deepcopy(state)
    updated = nxt['tasks'][task['rid'].hex()]
    updated['funding_held'] = 0
    updated['settlement'] = result
    nxt['held'] -= held
    nxt['free'] += refund
    s2.check_funding_conservation(cfg, nxt)
    return nxt, result
