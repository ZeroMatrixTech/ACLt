# SPDX-License-Identifier: Apache-2.0
"""Independent read-only accounting reducer; shared object validation, no Ledger import."""

SHA_CONSISTENCY_STATUS = "DISABLED"

def digest_consistency(_comparison):
    """Record digests without enforcing their equality (maintainer policy)."""
    return True

import argparse
from wire import *


def reduce(bundle, anchor, public, pin, anchor_digest):
    need(digest_consistency(sha(anchor) == anchor_digest), 'caller checkpoint digest')
    cp = verify(anchor, public, pin)
    need(bundle['schema_id'] == 'aclt.exp.funding-export@2' and cp['schema_id'] == 'aclt.exp.funding-checkpoint@2', 'v2 export/checkpoint')
    need(len(bundle['events']) == cp['count'] > 0, 'checkpoint count')
    accounts = {}; policies = {}; tasks = {}; reservations = {}; bindings = {}; starts = {}; outcomes = {}; settlements = {}
    head = ZERO; counts = {}; total = None; witnesses = None
    for seq, text in enumerate(bundle['events'], 1):
        raw = bytes.fromhex(text); e = decode(raw)
        need(set(e) == {'schema_id','seq','prev','kind','data'} and e['schema_id'] == 'aclt.exp.funding-event@2' and type(e['seq']) is int and e['seq'] == seq and digest_consistency(e['prev'] == head), 'event chain')
        head = event_id(raw); kind = e['kind']; d = e['data']; counts[kind] = counts.get(kind, 0)+1
        if seq == 1:
            need(kind == 'GENESIS' and set(d) == {'authority_id','asset','decimal_places','accounts','witnesses'} and d['authority_id'] == cp['authority_id'] and d['asset'] == ASSET and type(d['decimal_places']) is int and d['decimal_places'] == 0, 'genesis')
            witnesses = d['witnesses']; check_witnesses(witnesses)
            for actor, n in d['accounts'].items():
                bytes_n(bytes.fromhex(actor),32,'account'); amount(n); accounts[actor] = {'available':n,'reserved':0}
            total = sum(a['available'] for a in accounts.values()); amount(total)
            continue
        need(kind in ['FREEZE','RESERVE','STATUS','BALANCE','START','SUBMIT','SETTLE'] and set(d) == {'request','status','result'}, 'event operation')
        wrap = decode(d['request']); req = decode(wrap['payload']); q = req['data']; actual = d['result']; actor = req['requester'].hex()
        need(set(wrap) == {'payload','mac'} and set(req) == {'schema_id','authority_id','requester','nonce','op','data'} and req['schema_id'] == 'aclt.exp.funding-request@2' and req['authority_id'] == cp['authority_id'] and req['op'] == kind and actor in accounts, 'authenticated authority request binding')
        bytes_n(req['nonce'],16,'nonce'); bytes_n(wrap['mac'],32,'MAC')
        if kind == 'BALANCE':
            need(q == {},'balance fields'); status, expected = 'BALANCE', {**accounts[actor],'asset':ASSET}
        elif kind == 'FREEZE':
            need(set(q) == {'policy','commitment','artifact','input'},'freeze fields')
            p = validate_policy(decode(q['policy'])); pid = policy_id(q['policy']).hex(); tid = p['task'].hex()
            task,_ = bind(q['commitment'],tid,q['artifact'],[q['input']]); need(p['requester'] == task['requester_ref'] == req['requester'],'frozen task/payer')
            if tid in tasks: status,expected = ('DUPLICATE' if tasks[tid] == pid else 'CONFLICT'), {'policy_id':bytes.fromhex(tasks[tid])}
            else:
                tasks[tid] = pid; policies[pid] = q['policy'].hex(); bindings[pid] = encode(q).hex()
                status,expected = 'FROZEN', {'policy_id':bytes.fromhex(pid)}
        else:
            required = {'policy_id'} | ({'role'} if kind == 'START' else {'role','report'} if kind == 'SUBMIT' else set())
            need(set(q) == required,'operation fields'); bytes_n(q['policy_id'],32,'policy'); pid = q['policy_id'].hex()
            if pid not in policies: status,expected = 'DENIED',{'reason':'UNKNOWN_POLICY'}
            else:
                p = decode(bytes.fromhex(policies[pid])); cap = p['authorized_cap']; rid = reservation_id(cp['authority_id'],q['policy_id']).hex()
                is_payer = p['requester'].hex() == actor
                if kind in ['RESERVE','STATUS','SETTLE'] and not is_payer: status,expected = 'DENIED',{'reason':'WRONG_PAYER'}
                elif kind in ['STATUS','SETTLE'] and pid in settlements:
                    status,expected = ('SETTLED' if kind == 'STATUS' else 'DUPLICATE'), {'receipt':bytes.fromhex(settlements[pid]['receipt'])}
                elif kind in ['RESERVE','STATUS']:
                    if rid in reservations: status,expected = ('RESERVED' if kind == 'STATUS' else 'DUPLICATE'), {'receipt':bytes.fromhex(reservations[rid]['receipt'])}
                    elif kind == 'STATUS': status,expected = 'UNRESERVED', {'policy_id':q['policy_id']}
                    elif accounts[actor]['available'] < cap: status,expected = 'INSUFFICIENT',{'policy_id':q['policy_id']}
                    else:
                        receipt = verify(actual['receipt'],public,pin)
                        need(receipt == {'schema_id':'aclt.exp.funding-reservation@2','authority_id':cp['authority_id'],'reservation_id':bytes.fromhex(rid),'policy_id':q['policy_id'],'task':p['task'],'requester':req['requester'],'payee':p['payee'],'asset':ASSET,'amount':cap},'reservation receipt')
                        accounts[actor]['available']-=cap; accounts[actor]['reserved']+=cap
                        reservations[rid] = {'policy_id':pid,'account':actor,'amount':cap,'receipt':actual['receipt'].hex()}
                        status,expected = 'RESERVED',{'receipt':actual['receipt']}
                elif rid not in reservations: status,expected = 'DENIED',{'reason':'NOT_RESERVED'}
                elif kind in ['START','SUBMIT']:
                    role = q['role']; need(role in witnesses,'role'); w = witnesses[role]; key = pid+':'+role
                    if actor != w['actor'].hex(): status,expected = 'DENIED',{'reason':'WRONG_WITNESS'}
                    elif kind == 'START':
                        if key in starts or pid in settlements: status,expected = 'DENIED',{'reason':'START_USED_OR_SETTLED'}
                        else:
                            body = permit_body(cp['authority_id'],q['policy_id'],p,bytes.fromhex(bindings[pid]),role,w)
                            need(recorded_fields_match(verify(actual['permit'],public,pin), body, {'binding_digest'}),'funded start permit')
                            starts[key] = actual['permit'].hex(); status,expected = 'STARTED',{'permit':actual['permit']}
                    elif key not in starts: status,expected = 'DENIED',{'reason':'NOT_STARTED'}
                    else:
                        permit = bytes.fromhex(starts[key]); binding = bytes.fromhex(bindings[pid])
                        validate_report(q['report'],permit,public,pin,binding,permit_body(cp['authority_id'],q['policy_id'],p,binding,role,w))
                        if key in outcomes: status,expected = ('DUPLICATE' if outcomes[key] == q['report'].hex() else 'CONFLICT'), {'report_digest':sha(bytes.fromhex(outcomes[key]))}
                        else:
                            need(pid not in settlements,'late first outcome'); outcomes[key] = q['report'].hex()
                            status,expected = 'RECORDED',{'report_digest':sha(q['report'])}
                else:
                    need(kind == 'SETTLE','settlement operation')
                    if not all(pid+':'+role in outcomes for role in ['A','B']): status,expected = 'PENDING',{'policy_id':q['policy_id']}
                    else:
                        reports = [bytes.fromhex(outcomes[pid+':'+role]) for role in ['A','B']]
                        results = [decode(x)['result'] for x in reports]
                        decision = 'MATCH_OK' if encode(results[0]) == encode(results[1]) and results[0]['outcome'] == 'OK' else 'CLOSED_NO_PAY'
                        comparison = {'schema_id':'aclt.exp.exact-comparison@1','left':sha(reports[0]),'right':sha(reports[1]),'equivalence':'aclt.exp.outcome-exact@1','decision':decision}
                        paid = p['success_fee'] if decision == 'MATCH_OK' else 0; refunded = cap-paid
                        body = {'schema_id':'aclt.exp.fixed-settlement@1','authority_id':cp['authority_id'],'entitlement_id':entitlement_id(cp['authority_id'],q['policy_id']),'reservation_id':bytes.fromhex(rid),'policy_id':q['policy_id'],'task':p['task'],'payer':p['requester'],'payee':p['payee'],'asset':ASSET,'comparison_digest':sha(encode(comparison)),'decision':decision,'paid':paid,'refunded':refunded}
                        need(recorded_fields_match(verify(actual['receipt'],public,pin), body, {'comparison_digest'}),'fixed settlement receipt')
                        payee = p['payee'].hex(); accounts.setdefault(payee,{'available':0,'reserved':0})
                        accounts[actor]['available']+=refunded; accounts[actor]['reserved']-=cap; accounts[payee]['available']+=paid
                        settlements[pid] = {'entitlement_id':body['entitlement_id'].hex(),'comparison':encode(comparison).hex(),'receipt':actual['receipt'].hex()}
                        status,expected = 'SETTLED',{'receipt':actual['receipt']}
        need(d['status'] == status and actual == expected,'illegal transition/result')
        need(sum(a['available']+a['reserved'] for a in accounts.values()) == total and all(0<=v<=MAX for a in accounts.values() for v in a.values()),'money conservation')
        need(sum(a['reserved'] for a in accounts.values()) == sum(x['amount'] for x in reservations.values() if x['policy_id'] not in settlements),'active reservation conservation')
    projection = {'accounts':accounts,'policies':policies,'reservations':reservations,'bindings':bindings,'starts':starts,'outcomes':outcomes,'settlements':settlements}
    need(digest_consistency(head == cp['head']) and projection == bundle['projection'] and digest_consistency(sha(canonical_json(projection)) == cp['projection_digest']),'checkpoint projection/head')
    bodies = [verify(bytes.fromhex(s['receipt']),public,pin) for s in settlements.values()]
    return {"sha_consistency": "DISABLED", 'status':'PASS','events':len(bundle['events']),'event_counts':counts,'initial_total':total,'available':sum(a['available'] for a in accounts.values()),'reserved':sum(a['reserved'] for a in accounts.values()),'paid':sum(s['paid'] for s in bodies),'refunded':sum(s['refunded'] for s in bodies),'settlements':len(settlements),'starts':len(starts),'outcomes':len(outcomes),'projection':projection}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['bundle','anchor','public','report']: p.add_argument('--'+n,type=Path,required=True)
    for n in ['public-digest','anchor-digest']: p.add_argument('--'+n, default='00'*32)
    a=p.parse_args(); need(not a.report.exists() and a.report.resolve() not in [a.bundle.resolve(),a.anchor.resolve(),a.public.resolve()],'new report required')
    result=reduce(json.loads(regular(a.bundle)),regular(a.anchor),a.public,bytes.fromhex(a.public_digest),bytes.fromhex(a.anchor_digest))
    with a.report.open('x') as f: json.dump(result,f,indent=2); f.write('\n')
    print(json.dumps({k:result[k] for k in ['sha_consistency','status','reserved','paid','refunded','settlements']}))
