# SPDX-License-Identifier: Apache-2.0
"""Independent byte-driven reducer. No Ledger/Journal/worker import and no guest execution."""
import argparse
import json
from context import encode,decode,sha,tagged,verify,need,Rejected,ZERO,regular

EVENT_KEYS={'schema_id','stream','seq','prev','kind','payload_ref','parents'}

def eid(raw):return tagged('ACLt/Experiment/CausalEvent/1',raw)
def object_map(values):
    need(type(values) is dict,'object map')
    for key,data in values.items():need(type(data) is bytes and sha(data).hex()==key,'object hash mismatch')
    return dict(values)

def chain(events,stream,objects):
    need(type(events) is list,'events array');head=ZERO;nodes={}
    for seq,raw in enumerate(events,1):
        obj=decode(raw)
        need(type(obj) is dict and set(obj)==EVENT_KEYS and obj['schema_id']=='aclt.exp.causal-event@1','event schema')
        need(obj['stream']==stream and type(obj['seq']) is int and obj['seq']==seq and obj['prev']==head,'event gap/order/previous')
        need(type(obj['parents']) is list and all(type(x) is bytes and len(x)==32 for x in obj['parents']) and obj['parents']==sorted(set(obj['parents'])),'event causal parents')
        need(type(obj['payload_ref']) is bytes and len(obj['payload_ref'])==32 and obj['payload_ref'].hex() in objects,'missing event payload')
        head=eid(raw);nodes[head]=obj
    return head,nodes

def reduce(bundle,anchor,public,public_digest,expected_anchor_digest):
    need(sha(anchor)==expected_anchor_digest,'caller-retained checkpoint digest mismatch')
    checkpoint=verify(anchor,public,public_digest)
    need(checkpoint['schema_id']=='aclt.exp.journal-checkpoint@1','checkpoint schema')
    authority=bundle['authority'];objects=object_map(authority['objects']);authid=authority['authority_id']
    stream=tagged('ACLt/Experiment/CausalStream/1',encode(['authority',authid,ZERO,ZERO]))
    need(authority['stream']==checkpoint['stream']==stream and checkpoint['authority_id']==authid,'checkpoint deployment/stream')
    head,anodes=chain(authority['events'],stream,objects)
    need(checkpoint['count']==len(anodes) and checkpoint['head']==head,'truncated/extended checkpoint log')
    nodes=dict(anodes);workers=[];stream_positions={}
    for item in bundle['workers']:
        pack=item['journal'];wobjects=object_map(pack['objects'])
        for key,value in wobjects.items():
            need(key not in objects or objects[key]==value,'conflicting object bytes');objects[key]=value
        for value in item['files'].values():objects[sha(value).hex()]=value
        _,wnodes=chain(pack['events'],pack['stream'],objects)
        for key,event in wnodes.items():
            position=(event['stream'],event['seq'])
            need(position not in stream_positions or stream_positions[position]==key,'worker journal fork')
            stream_positions[position]=key;need(key not in nodes or nodes[key]==event,'event collision');nodes[key]=event
        workers.append((item,wnodes))
    def blob(ref):
        need(type(ref) is bytes and len(ref)==32 and ref.hex() in objects,'missing object reference');return objects[ref.hex()]
    def payload(event):return decode(blob(event['payload_ref']))
    def request(raw):
        wrap=decode(raw);req=decode(wrap['payload'])
        need(req['schema_id']=='aclt.exp.causal-request@1' and req['authority_id']==authid,'request deployment')
        return req
    def reply(reqraw,raw):
        req=request(reqraw);r=verify(raw,public,public_digest)
        need(r['schema_id']=='aclt.exp.causal-response@1' and r['authority_id']==authid and r['request_digest']==sha(reqraw) and r['nonce']==req['nonce'] and r['op']==req['op'] and r['grant_id']==req['grant_id'],'signed response/request binding')
        need(r['event_ref'] in anodes,'response missing authority event')
        ap=payload(anodes[r['event_ref']]);need(ap['request_ref']==sha(reqraw) and ap['status']==r['status'],'response authority decision mismatch')
        return r
    def worker_snapshot(pack):
        local=object_map(pack['objects']);wh,wn=chain(pack['events'],pack['stream'],local)
        need(all(k in nodes and nodes[k]==v for k,v in wn.items()),'referenced worker prefix missing/forked')
        return wh
    def outcome_check(oref,outref,g,task):
        o=decode(blob(oref));r=o['result'];output=blob(outref) if outref!=ZERO else None
        need(set(o)=={'result','outcome_digest','grant_id','tuple'} and o['grant_id']==g['gid'] and o['tuple']==g['body']['execution_tuple_digest'],'outcome grant/tuple')
        need(type(r) is dict and type(r.get('gas_used')) is int and 8192<=r['gas_used']<=task['limits']['gas_limit'],'outcome gas binding')
        kind=r.get('outcome');allowed={'OK','ABORT','TRAP_GAS_EXHAUSTED','TRAP_OUTPUT_LIMIT','TRAP_CALL_DEPTH','TRAP_UNREACHABLE','TRAP_MEMORY_OOB','TRAP_HOST_ARGUMENT','TRAP_INTEGER_DIVIDE_BY_ZERO','TRAP_INTEGER_OVERFLOW'}
        need(kind in allowed,'unknown Task outcome')
        expected={'outcome','gas_used'}|({'output'} if kind=='OK' else {'abort_code'} if kind=='ABORT' else set());need(set(r)==expected,'outcome fields/partial output')
        original=dict(r)
        if kind=='OK':need(output is not None and sha(output)==r['output'] and len(output)<=task['limits']['output_limit'],'output bytes/digest');original['output']=output
        else:need(output is None,'non-OK output attachment')
        if kind=='ABORT':need(type(r['abort_code']) is int and 0<=r['abort_code']<2**32,'abort code')
        need(tagged('ACLt/RIR-0/ExecutionOutcome/1',encode(original))==o['outcome_digest'],'outcome digest')
        return o
    tasks={};grants={};active={};accepted={};counts={}
    for raw in authority['events']:
        ref=eid(raw);event=anodes[ref];p=payload(event);kind=event['kind'];counts[kind]=counts.get(kind,0)+1
        if kind=='REGISTER':
            need(p['task'] not in tasks,'duplicate task registration');craw=blob(p['commitment_ref']);commit=decode(craw)
            need(tagged('ACLt/Experiment/TaskCommitment/1',craw)==p['task'] and commit['schema_id']=='aclt.exp.task-commitment@1','task identity')
            need(tagged('ACLt/RIR-0/Artifact/1',blob(p['artifact_ref']))==commit['rir_digest'],'registered artifact binding')
            data=blob(p['input_ref']);need(len(commit['inputs'])==1 and sha(data)==commit['inputs'][0]['object_digest'] and len(data)==commit['inputs'][0]['byte_length'],'registered input binding')
            tasks[p['task']]={'raw':commit,'event':ref,'limits':commit['execution_limits'],'refs':[p['commitment_ref'],p['artifact_ref'],p['input_ref']]}
        elif kind=='ISSUE':
            body=verify(blob(p['grant_ref']),public,public_digest);tid=body['experimental_task_id'];need(tid in tasks and body['authority_id']==authid,'issued task/deployment')
            gid=tagged('ACLt/Experiment/ExecutionGrant/1',encode(body));key=(tid,body['unit_ref']);task=tasks[tid]['raw']
            scope={'schema_id':'aclt.exp.execution-scope@1','experimental_task_id':tid,'rir_digest':task['rir_digest'],'inputs':task['inputs'],'execution_profile_digest':task['execution_profile_digest'],'execution_limits':task['execution_limits'],'result_equivalence':task['result_equivalence']}
            sd=tagged('ACLt/Experiment/ExecutionScope/1',encode(scope));tup={'schema_id':'aclt.exp.execution-tuple@1','experimental_task_id':tid,'provider_ref':body['provider_ref'],'unit_ref':body['unit_ref'],'environment_digest':body['environment_digest'],'scope_digest':sd}
            need(body['scope_digest']==sd and body['execution_tuple_digest']==tagged('ACLt/Experiment/ExecutionTuple/1',encode(tup)),'issued tuple/scope')
            if key in active:
                old=grants[active[key]];need(not old['consumed'] and body['epoch']>old['body']['epoch'],'renewal after consume or stale epoch')
            need(tasks[tid]['event'] in event['parents'],'missing registration parent')
            grants[gid]={'gid':gid,'body':body,'event':ref,'consumed':b'','accepted':b''};active[key]=gid
        elif kind in ['CHECK','CONSUME']:
            req=request(blob(p['request_ref']));need(req['op']==kind and req['grant_id']==p['grant_id'],'authorization request mismatch')
            if p['status']=='ALLOW':
                need(p['grant_id'] in grants,'unknown allowed grant');g=grants[p['grant_id']];b=g['body'];key=(b['experimental_task_id'],b['unit_ref'])
                need(active[key]==g['gid'] and not g['consumed'] and b['provider_ref']==req['provider_ref'] and b['not_before']<=p['time']<b['expires_at'],'illegal grant/time/consume transition')
                wh=worker_snapshot(req['data']);wp=payload(nodes[wh]);need(nodes[wh]['kind']==('DISPATCH_REQUEST' if kind=='CHECK' else 'INTENT') and wp['grant_id']==g['gid'] and wp['execution_tuple_digest']==b['execution_tuple_digest'],'authorization worker causal head')
                need(g['event'] in event['parents'] and wh in event['parents'],'missing authorization parent')
                if kind=='CONSUME':g['consumed']=ref
            else:need(p['status']=='DENY','authorization status')
        elif kind in ['ACCEPT','SUBMIT_DUPLICATE','SUBMIT_CONFLICT','SUBMIT_REJECTED']:
            reqraw=blob(p['request_ref']);req=request(reqraw);need(req['op']=='SUBMIT' and req['grant_id']==p['grant_id'],'submission request mismatch')
            if kind=='SUBMIT_REJECTED':need(p['status']=='REJECTED','rejection status');continue
            need(p['grant_id'] in grants,'unknown submission grant');g=grants[p['grant_id']];b=g['body'];need(bool(g['consumed']),'submission before consume')
            rawsub=req['data']['submission'];digest=sha(rawsub)
            if kind=='SUBMIT_CONFLICT':need(g['gid'] in accepted and digest!=g['accepted'] and p['status']=='CONFLICT','invalid conflict transition');continue
            send_raw=req['data']['send_event'];send=eid(send_raw);sp=decode(req['data']['send_payload'])
            need(send in nodes and nodes[send]['kind']=='SEND' and nodes[send]['payload_ref']==sha(req['data']['send_payload']) and sp=={'submission_digest':digest,'attempt_nonce':req['nonce']} and send in event['parents'],'submission SEND causality')
            receipt_raw=blob(p['receipt_ref']);receipt=verify(receipt_raw,public,public_digest)
            if kind=='SUBMIT_DUPLICATE':
                need(g['gid'] in accepted and g['accepted']==digest and receipt_raw==accepted[g['gid']]['receipt'] and p['status']=='DUPLICATE','duplicate changed stable receipt');continue
            need(g['gid'] not in accepted and p['status']=='ACCEPTED','second acceptance')
            sub=decode(rawsub);sb=decode(sub['body']);wh=worker_snapshot(sub['worker']);pe_raw=req['data']['prepared_event'];pe=eid(pe_raw)
            need(pe in nodes and nodes[pe]['kind']=='PREPARED' and nodes[pe]['prev']==wh and nodes[pe]['payload_ref']==sha(req['data']['prepared_payload']),'prepared prefix missing')
            need(decode(req['data']['prepared_payload'])=={'submission_digest':digest,'body_digest':sha(sub['body'])},'prepared bytes mismatch')
            need(sb['authority_id']==authid and sb['grant_id']==g['gid'] and sb['task']==b['experimental_task_id'] and sb['unit']==b['unit_ref'] and sb['provider']==b['provider_ref'] and sb['tuple']==b['execution_tuple_digest'] and sb['worker_head']==wh,'submission binding')
            op=payload(nodes[wh]);need(nodes[wh]['kind']=='OUTCOME' and op=={'outcome_ref':sb['outcome_ref'],'output_ref':sb['output_ref']},'submission not complete outcome')
            outcome=outcome_check(sb['outcome_ref'],sb['output_ref'],g,tasks[b['experimental_task_id']])
            expected={'schema_id':'aclt.exp.acceptance-receipt@1','authority_id':authid,'task':sb['task'],'unit':sb['unit'],'grant_id':g['gid'],'execution_tuple_digest':sb['tuple'],'submission_digest':digest,'outcome_digest':outcome['outcome_digest']}
            need(receipt==expected and g['consumed'] in event['parents'] and pe in event['parents'],'acceptance receipt/parents')
            g['accepted']=digest;accepted[g['gid']]={'receipt':receipt_raw,'event':ref}
        else:raise Rejected('unknown authority transition: '+kind)
    # Independently check the worker phase machine, not just its hash chain.
    wstates=[]
    for item,wnodes in workers:
        phase='NEW';gid=None;prepared=None;acked=False
        for ref,event in wnodes.items():
            p=payload(event);kind=event['kind']
            if kind=='DISPATCH_REQUEST':
                need(phase=='NEW' and p['grant_id'] in grants,'worker dispatch phase');gid=p['grant_id'];g=grants[gid];b=g['body']
                need([p[n] for n in ['commitment_ref','artifact_ref','input_ref']]==tasks[b['experimental_task_id']]['refs'] and p['task']==b['experimental_task_id'] and p['execution_tuple_digest']==b['execution_tuple_digest'],'worker registered objects/tuple')
                need(g['event'] in event['parents'] and event['stream']==tagged('ACLt/Experiment/CausalStream/1',encode(['worker',authid,b['experimental_task_id'],b['unit_ref']])),'worker issue/stream binding');phase='REQUESTED'
            elif kind in ['DISPATCH_CHECKED','PERMIT']:
                need(phase==('REQUESTED' if kind=='DISPATCH_CHECKED' else 'INTENT'),'worker authorization phase')
                r=reply(blob(p['request_ref']),blob(p['response_ref']));need(r['status']=='ALLOW' and r['grant_id']==gid and r['op']==('CHECK' if kind=='DISPATCH_CHECKED' else 'CONSUME') and r['event_ref'] in event['parents'],'worker signed permission')
                phase='CHECKED' if kind=='DISPATCH_CHECKED' else 'PERMITTED'
            elif kind=='INTENT':need(phase=='CHECKED' and p['grant_id']==gid and p['execution_tuple_digest']==grants[gid]['body']['execution_tuple_digest'],'worker intent phase/binding');phase='INTENT'
            elif kind=='INVOKE':need(phase=='PERMITTED' and p['grant_id']==gid,'worker invocation without permit');phase='INVOKED'
            elif kind=='OUTCOME':need(phase=='INVOKED','worker outcome without invoke');outcome_check(p['outcome_ref'],p['output_ref'],grants[gid],tasks[grants[gid]['body']['experimental_task_id']]);phase='OUTCOME'
            elif kind=='PREPARED':
                need(phase=='OUTCOME','worker prepare without outcome');rawsub=blob(p['submission_digest']);sub=decode(rawsub)
                need(sha(sub['body'])==p['body_digest'] and sub['worker']['events']==item['journal']['events'][:event['seq']-1],'prepared exact prefix');prepared=p['submission_digest'];phase='PREPARED'
            elif kind=='SEND':need(phase in ['PREPARED','SENDING','ACKED','DENIED'] and p['submission_digest']==prepared,'worker send without complete immutable packet');phase='SENDING'
            elif kind in ['ACK','SUBMIT_DENIED']:
                need(phase=='SENDING','worker reply without send');r=reply(blob(p['request_ref']),blob(p['response_ref']));need(r['event_ref'] in event['parents'],'worker response parent')
                if kind=='ACK':need(r['status'] in ['ACCEPTED','DUPLICATE'] and blob(p['receipt_ref'])==r['receipt'] and gid in accepted and r['receipt']==accepted[gid]['receipt'],'worker stable receipt');acked=True;phase='ACKED'
                else:need(r['status'] in ['REJECTED','CONFLICT'],'worker denial status');phase='DENIED'
            else:raise Rejected('unknown worker phase: '+kind)
        wstates.append({'stream':item['journal']['stream'].hex(),'phase':phase,'accepted':bool(gid in accepted),'acknowledged':acked})
    # Causal references must form one closed DAG; reject missing cross-stream parents.
    done=set();visiting=set()
    def visit(ref):
        need(ref in nodes,'missing causal parent')
        if ref in done:return
        need(ref not in visiting,'causal cycle');visiting.add(ref)
        event=nodes[ref]
        for parent in ([event['prev']] if event['prev']!=ZERO else [])+event['parents']:visit(parent)
        visiting.remove(ref);done.add(ref)
    for ref in nodes:visit(ref)
    projection={'tasks':sorted(t.hex() for t in tasks),'slots':{gid.hex():{'task':grants[gid]['body']['experimental_task_id'].hex(),'unit':grants[gid]['body']['unit_ref'].hex(),'epoch':grants[gid]['body']['epoch'],'consumed':grants[gid]['consumed'].hex() if grants[gid]['consumed'] else '', 'accepted':grants[gid]['accepted'].hex() if grants[gid]['accepted'] else ''} for gid in active.values()}}
    need(projection==authority['projection'] and sha(encode(projection))==checkpoint['projection_digest'],'replayed state differs from signed/materialized projection')
    return {'status':'PASS','authority_events':len(anodes),'worker_events':sum(len(n) for _,n in workers),'accepted':len(accepted),'consumed':sum(bool(grants[g]['consumed']) for g in active.values()),'authority_counts':counts,'workers':wstates,'projection':projection,'guest_executions_during_replay':0}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['bundle','anchor','public','report']:p.add_argument('--'+name,required=True)
    p.add_argument('--public-digest',required=True);p.add_argument('--expected-anchor-digest',required=True);a=p.parse_args()
    from pathlib import Path
    if Path(a.report).exists():p.error('report exists')
    result=reduce(decode(regular(a.bundle)),regular(a.anchor),a.public,bytes.fromhex(a.public_digest),bytes.fromhex(a.expected_anchor_digest))
    with open(a.report,'x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ['status','authority_events','worker_events','accepted','consumed']}))
