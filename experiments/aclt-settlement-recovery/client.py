# SPDX-License-Identifier: Apache-2.0
"""Read-first recovery; uncertainty never automatically submits a new settlement."""
import argparse
from context import *


def checked_settlement(raw,cfg,public,pid):
    s=verify(raw,public,cfg['public_digest'])
    keys={'schema_id','authority_id','entitlement_id','reservation_id','policy_id','task','payer','payee','asset','comparison_digest','decision','paid','refunded'}
    need(set(s)==keys and s['schema_id']=='aclt.exp.fixed-settlement@1' and s['authority_id']==cfg['authority_id'] and s['policy_id']==pid and s['payer']==cfg['requester'] and s['asset']==ASSET and s['entitlement_id']==entitlement_id(cfg['authority_id'],pid) and s['reservation_id']==reservation_id(cfg['authority_id'],pid),'recovered entitlement binding')
    for key in ['task','payee','comparison_digest']: bytes_n(s[key],32,key)
    amount(s['paid']); amount(s['refunded']); need(s['paid']<=MAX-s['refunded'],'allocation overflow')
    need(s['decision'] in ['MATCH_OK','CLOSED_NO_PAY'] and (s['decision']!='CLOSED_NO_PAY' or s['paid']==0),'recovered decision')
    return s


def recover(cfg,public,pid,transport=None):
    bytes_n(pid,32,'policy ID'); packet=request(cfg,'STATUS',{'policy_id':pid})
    result,raw=transport(packet) if transport else exchange(cfg,packet,public,keep_raw=True)
    # Never trust a transport's decoded view in place of the signed raw response.
    result=response(packet,raw,cfg,public)
    need(result['status'] in ['SETTLED','RESERVED','UNRESERVED'],'recovery query denied/unknown')
    if result['status']=='SETTLED':
        checked_settlement(result['result']['receipt'],cfg,public,pid); status='RECOVERED'
    else: status='HELD' if result['status']=='RESERVED' else 'UNFUNDED'
    return {'request':packet,'signed_response':raw,'response':result,'recovery_status':status}


def view(value):
    if type(value) is bytes: return value.hex()
    if type(value) is dict: return {k:view(v) for k,v in value.items()}
    if type(value) is list: return [view(v) for v in value]
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['freeze','reserve','status','balance','settle','recover'])
    for n in ['config','public','report']: p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--policy-id')
    for n in ['policy','commitment','artifact','input']: p.add_argument('--'+n,type=Path)
    a=p.parse_args(); need(not a.report.exists(),'new report required'); cfg=config(a.config)
    if a.operation=='recover': result=recover(cfg,a.public,bytes.fromhex(a.policy_id))
    else:
        if a.operation=='freeze': data={n:regular(getattr(a,n)) for n in ['policy','commitment','artifact','input']}
        elif a.operation in ['reserve','status','settle']: data={'policy_id':bytes.fromhex(a.policy_id)}
        else: data={}
        packet=request(cfg,a.operation.upper(),data); parsed,raw=exchange(cfg,packet,a.public,keep_raw=True)
        result={'request':packet,'signed_response':raw,'response':parsed}
    with a.report.open('x') as f: json.dump(view(result),f,indent=2); f.write('\n')
    print(json.dumps({'status':result.get('recovery_status',result['response']['status'])}))
