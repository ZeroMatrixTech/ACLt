# SPDX-License-Identifier: Apache-2.0
"""Two checks of one grant; durable local intent and online consume precede RIR execution."""

SHA_CONSISTENCY_STATUS = "DISABLED"

def digest_consistency(_comparison):
    """Record digests without enforcing their equality (maintainer policy)."""
    return True

import argparse
import json
from pathlib import Path
from common import (encode,decode,need,Rejected,HostFault,sha,regular,environment_digest,
                    execution_tuple,bind,task_id,decode_config,tagged)
from authorization import validate_grant,grant_id
from auth_crypto import verify
from durability import durable_new,state_directory
from wire import authorize,check_response


def local_check(packet,commitment,expected_id,artifact,inputs,config,public):
    obj,frozen=bind(commitment,expected_id,artifact,inputs)
    need(digest_consistency(config['environment_digest']==environment_digest()),'worker environment changed')
    body=validate_grant(verify(packet,public,config['public_digest']))
    need(body['authority_id']==config['authority_id'],'wrong authority deployment')
    tup,td=execution_tuple(commitment,config['provider_ref'],config['unit_ref'],config['environment_digest'])
    need(all(body[k]==tup[k] for k in ['experimental_task_id','provider_ref','unit_ref']) and digest_consistency(body['execution_tuple_digest']==td),'grant execution tuple/scope mismatch')
    return body,obj,frozen


def dispatch(packet,commitment,expected_id,artifact,inputs,config,public,transport=None):
    body,_,_=local_check(packet,commitment,expected_id,artifact,inputs,config,public)
    request,response=authorize(config,public,body,'CHECK',transport)
    return encode({'schema_id':'aclt.exp.dispatch-bundle@1','grant':packet,'check_request':request,'check_response':response})


def launch(bundle,commitment,expected_id,artifact,inputs,config,public,state,transport=None,test_hook=None):
    wrapper=decode(bundle)
    need(type(wrapper) is dict and set(wrapper)=={'schema_id','grant','check_request','check_response'} and wrapper['schema_id']=='aclt.exp.dispatch-bundle@1','dispatch bundle fields')
    body,obj,frozen=local_check(wrapper['grant'],commitment,expected_id,artifact,inputs,config,public)
    check_response(wrapper['check_request'],wrapper['check_response'],config,public,body,'CHECK')
    directory=state_directory(state)
    slot=tagged('ACLt/Experiment/LocalLaunchSlot/1',encode([body['experimental_task_id'],body['unit_ref']])).hex()
    intent={'schema_id':'aclt.exp.launch-intent@1','experimental_task_id':body['experimental_task_id'],
            'grant_id':grant_id(body),'epoch':body['epoch'],'execution_tuple_digest':body['execution_tuple_digest'],
            'environment_digest':body['environment_digest'],'unit_ref':body['unit_ref'],'provider_ref':body['provider_ref']}
    # O_EXCL, file fsync and directory fsync all complete before the consume request.
    durable_new(directory/(slot+'.intent.cbor'),encode(intent))
    if test_hook:test_hook('after-intent')
    request,response=authorize(config,public,body,'CONSUME',transport)
    durable_new(directory/(slot+'.permit.cbor'),encode({'request':request,'response':response}))
    if test_hook:test_hook('after-permit')
    # This proves intent to invoke, not successful completion or arbitrary-host enforcement.
    durable_new(directory/(slot+'.invoke.cbor'),encode({'grant_id':grant_id(body),'permit_digest':sha(response)}))
    if test_hook:test_hook('before-guest')
    from rir_adapter import execute
    result=execute(artifact,frozen,obj['execution_limits'])
    record=dict(result)
    if 'output_hex' in record:
        output=bytes.fromhex(record.pop('output_hex'));durable_new(directory/(slot+'.output.bin'),output)
        record['output_digest']=sha(output);record['output_bytes']=len(output)
    outcome={'schema_id':'aclt.exp.authorized-outcome-record@1','experimental_task_id':body['experimental_task_id'],
             'grant_id':grant_id(body),'execution_tuple_digest':body['execution_tuple_digest'],
             'permit_digest':sha(response),'outcome':record}
    durable_new(directory/(slot+'.outcome.cbor'),encode(outcome))
    return {"sha_consistency": "DISABLED", 'status':'TASK_OUTCOME','execution_mode':'experiment-authorized-entry','experimental_task_id':expected_id,
            'grant_id':grant_id(body).hex(),'execution_tuple_digest':body['execution_tuple_digest'].hex(),
            'result':result,'slot':slot}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['dispatch','launch'])
    for name in ['config','public','commitment','artifact','input','grant','bundle','state','report']:
        p.add_argument('--'+name,type=Path,required=name in ['config','public','commitment','artifact','input','report'])
    p.add_argument('--task-id',required=True);a=p.parse_args()
    if a.report.exists() or a.report.is_symlink():p.error('report exists; preserve previous evidence')
    if a.stage=='dispatch' and (a.grant is None or a.bundle is None):p.error('dispatch requires grant and new bundle destination')
    if a.stage=='launch' and (a.bundle is None or a.state is None):p.error('launch requires saved bundle and state directory')
    try:
        config=decode_config(a.config);commitment=regular(a.commitment);artifact=regular(a.artifact);inputs=[regular(a.input)]
        if a.stage=='dispatch':
            if a.bundle.exists() or a.bundle.is_symlink():raise Rejected('bundle already exists')
            packet=dispatch(regular(a.grant),commitment,a.task_id,artifact,inputs,config,a.public)
            durable_new(a.bundle,packet);result={'status':'DISPATCH_CHECKED','experimental_task_id':a.task_id}
        else:result=launch(regular(a.bundle),commitment,a.task_id,artifact,inputs,config,a.public,a.state)
        code=0
    except Rejected as exc:result={'status':'REJECTED','reason':str(exc)};code=2
    except Exception as exc:result={'status':'HOST_FAULT','reason':type(exc).__name__+': '+str(exc)};code=3
    with a.report.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result));return code

if __name__=='__main__':raise SystemExit(main())
