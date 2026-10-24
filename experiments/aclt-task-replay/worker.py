# SPDX-License-Identifier: Apache-2.0
"""Durable causal worker; replay reads a complete immutable package and never executes RIR."""
import argparse
import json
import secrets
from context import *
from journal import Journal,snapshot_check
from network import request,response,exchange

def grant_check(delivery,commitment,expected,artifact,inputs,cfg,public):
    obj,frozen=bind(commitment,expected,artifact,inputs);need(cfg['environment_digest']==environment_digest(),'worker environment changed')
    bundle=decode(delivery);need(set(bundle)=={'grant','issue_event','register_event'},'grant delivery fields')
    body=validate_grant(verify(bundle['grant'],public,cfg['public_digest']));tup,td=execution_tuple(commitment,cfg['provider_ref'],cfg['unit_ref'],cfg['environment_digest'])
    need(body['authority_id']==cfg['authority_id'] and body['execution_tuple_digest']==td and all(body[k]==tup[k] for k in ['experimental_task_id','provider_ref','unit_ref','environment_digest','scope_digest']),'grant tuple binding')
    return bundle,body,obj,frozen

def rpc(cfg,public,gid,op,data,transport=None):
    req=request(cfg,gid,op,data);reply=(transport or (lambda p:exchange(cfg,p)))(req);return req,reply,response(req,reply,cfg,public)

def dispatch(delivery,commitment,expected,artifact,inputs,cfg,public,state,transport=None):
    bundle,body,obj,frozen=grant_check(delivery,commitment,expected,artifact,inputs,cfg,public)
    directory=state_directory(state);sid=stream_id('worker',cfg['authority_id'],body['experimental_task_id'],body['unit_ref']);j=Journal(directory/'journal',sid,create=True)
    refs=[j.put(b) for b in [commitment,artifact,inputs[0],delivery]]
    payload={'task':body['experimental_task_id'],'grant_id':grant_id(body),'execution_tuple_digest':body['execution_tuple_digest'],
             'commitment_ref':refs[0],'artifact_ref':refs[1],'input_ref':refs[2],'delivery_ref':refs[3]}
    j.append('DISPATCH_REQUEST',payload,[bundle['issue_event']])
    req,reply,result=rpc(cfg,public,grant_id(body),'CHECK',j.snapshot(),transport)
    need(result['status']=='ALLOW','dispatch denied: '+result['reason'])
    j.append('DISPATCH_CHECKED',{'request_ref':j.put(req),'response_ref':j.put(reply)},[result['event_ref']])
    durable_new(directory/'bundle.cbor',encode({'delivery':delivery,'check_request':req,'check_response':reply}))
    return {'status':'DISPATCH_CHECKED','experimental_task_id':expected}

def launch(commitment,expected,artifact,inputs,cfg,public,state,transport=None,hook=None):
    directory=Path(state);saved=decode(regular(directory/'bundle.cbor'))
    bundle,body,obj,frozen=grant_check(saved['delivery'],commitment,expected,artifact,inputs,cfg,public)
    checked=response(saved['check_request'],saved['check_response'],cfg,public);need(checked['status']=='ALLOW','saved dispatch denial')
    sid=stream_id('worker',cfg['authority_id'],body['experimental_task_id'],body['unit_ref']);j=Journal(directory/'journal',sid)
    need(decode(j.events()[-1])['kind']=='DISPATCH_CHECKED','launch not resumable')
    intent={'task':body['experimental_task_id'],'grant_id':grant_id(body),'execution_tuple_digest':body['execution_tuple_digest']}
    durable_new(directory/'launch.used',encode(intent));j.append('INTENT',intent,[checked['event_ref']])
    if hook:hook('after-intent')
    req,reply,permit=rpc(cfg,public,grant_id(body),'CONSUME',j.snapshot(),transport)
    need(permit['status']=='ALLOW','consume denied: '+permit['reason'])
    durable_new(directory/'permit.cbor',encode({'request':req,'response':reply}));j.append('PERMIT',{'request_ref':j.put(req),'response_ref':j.put(reply)},[permit['event_ref']])
    if hook:hook('after-permit')
    j.append('INVOKE',{'grant_id':grant_id(body)})
    from rir_adapter import execute
    result=execute(artifact,frozen,obj['execution_limits']);record={k:v for k,v in result.items() if k not in ['outcome_digest','output_hex']}
    output_ref=ZERO
    if 'output_hex' in result:
        output=bytes.fromhex(result['output_hex']);output_ref=j.put(output);record['output']=sha(output)
    outcome={'result':record,'outcome_digest':bytes.fromhex(result['outcome_digest']),'grant_id':grant_id(body),'tuple':body['execution_tuple_digest']}
    oref=j.put(encode(outcome));j.append('OUTCOME',{'outcome_ref':oref,'output_ref':output_ref})
    if hook:hook('after-outcome')
    prepare(j,body,directory)
    if hook:hook('after-prepared')
    return replay(directory,expected,cfg,public,transport)

def prepare(j,body,directory):
    pack=j.snapshot();last=decode(pack['events'][-1]);need(last['kind']=='OUTCOME','complete outcome required')
    payload=decode(pack['objects'][last['payload_ref'].hex()]);head=event_id(pack['events'][-1])
    sb={'schema_id':'aclt.exp.submission@1','authority_id':body['authority_id'],'grant_id':grant_id(body),'task':body['experimental_task_id'],
        'unit':body['unit_ref'],'provider':body['provider_ref'],'tuple':body['execution_tuple_digest'],'worker_head':head,
        'outcome_ref':payload['outcome_ref'],'output_ref':payload['output_ref'],'submission_nonce':secrets.token_bytes(16)}
    raw=encode({'body':encode(sb),'worker':pack})
    durable_new(directory/'submission.cbor',raw)
    j.append('PREPARED',{'submission_digest':sha(raw),'body_digest':sha(encode(sb))})
    return raw

def _replay(state,expected,cfg,public,transport=None):
    directory=Path(state);raw=regular(directory/'submission.cbor');sub=decode(raw);sb=decode(sub['body'])
    need(sb['task'].hex()==expected and sb['provider']==cfg['provider_ref'] and sb['unit']==cfg['unit_ref'] and sb['authority_id']==cfg['authority_id'],'saved submission context')
    j=Journal(directory/'journal',sub['worker']['stream']);events=j.events();prepared=[r for r in events if decode(r)['kind']=='PREPARED'];need(len(prepared)==1,'one complete prepared event required')
    pe=decode(prepared[0]);pp=j.get(pe['payload_ref']);need(decode(pp)=={'submission_digest':sha(raw),'body_digest':sha(sub['body'])},'saved submission changed')
    snapshot_check(sub['worker'])
    nonce=secrets.token_bytes(16)
    send_payload={'submission_digest':sha(raw),'attempt_nonce':nonce}
    send_ref=j.append('SEND',send_payload,[event_id(prepared[0])]);send_raw=j.events()[-1]
    data={'submission':raw,'prepared_event':prepared[0],'prepared_payload':pp,'send_event':send_raw,'send_payload':encode(send_payload)}
    req=request(cfg,sb['grant_id'],'SUBMIT',data,nonce);j.put(req)
    reply=(transport or (lambda p:exchange(cfg,p)))(req);result=response(req,reply,cfg,public)
    reply_ref=j.put(reply)
    if result['status'] not in ['ACCEPTED','DUPLICATE']:
        j.append('SUBMIT_DENIED',{'response_ref':reply_ref,'request_ref':sha(req)},[result['event_ref']]);raise Rejected('submission denied: '+result['status'])
    receipt=verify(result['receipt'],public,cfg['public_digest'])
    need(receipt['schema_id']=='aclt.exp.acceptance-receipt@1' and receipt['submission_digest']==sha(raw) and receipt['grant_id']==sb['grant_id'] and receipt['task']==sb['task'] and receipt['unit']==sb['unit'] and receipt['execution_tuple_digest']==sb['tuple'],'receipt binding')
    rpath=directory/'receipt.cbor'
    if rpath.exists():need(regular(rpath)==result['receipt'],'stable receipt changed')
    else:durable_new(rpath,result['receipt'])
    j.append('ACK',{'response_ref':reply_ref,'request_ref':sha(req),'receipt_ref':j.put(result['receipt'])},[result['event_ref']])
    return {'status':result['status'],'experimental_task_id':expected,'submission_digest':sha(raw).hex(),'receipt_digest':sha(result['receipt']).hex()}

def replay(state,expected,cfg,public,transport=None):
    import fcntl,os
    directory=Path(state)
    fd=os.open(directory/'replay.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        return _replay(directory,expected,cfg,public,transport)
    finally:os.close(fd)

def export_worker(state):
    directory=Path(state);sid=regular(directory/'journal/stream')
    return {'journal':Journal(directory/'journal',sid).snapshot(),
            'files':{n:regular(directory/n) for n in ['submission.cbor','receipt.cbor','launch.used'] if (directory/n).exists()}}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['dispatch','launch','replay','export'])
    for name in ['config','public','commitment','artifact','input','delivery','state','report']:p.add_argument('--'+name,type=Path,required=name in ['config','public','state','report'])
    p.add_argument('--task-id',required=True);a=p.parse_args()
    if a.report.exists() or a.report.is_symlink():p.error('report exists')
    try:
        cfg=config(a.config)
        if a.stage=='replay':result=replay(a.state,a.task_id,cfg,a.public)
        elif a.stage=='export':
            sub=decode(regular(a.state/'submission.cbor')) if (a.state/'submission.cbor').exists() else None
            sid=regular(a.state/'journal/stream');result=export_worker(a.state)
            with a.report.open('xb') as f:f.write(encode(result))
            print('EXPORTED');raise SystemExit(0)
        else:
            need(a.commitment is not None and a.artifact is not None and a.input is not None,'task files required')
            args=(regular(a.commitment),a.task_id,regular(a.artifact),[regular(a.input)],cfg,a.public,a.state)
            result=dispatch(regular(a.delivery),*args) if a.stage=='dispatch' else launch(*args)
        code=0
    except Rejected as exc:result={'status':'REJECTED','reason':str(exc)};code=2
    except Exception as exc:result={'status':'HOST_FAULT','reason':type(exc).__name__+': '+str(exc)};code=3
    with a.report.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result));raise SystemExit(code)
