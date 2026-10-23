# SPDX-License-Identifier: Apache-2.0
"""Generate inspectable commitment/binding evidence using the unchanged stats fixture."""
import argparse
import copy
import hashlib
import json
import platform
from pathlib import Path
from commitment import freeze,bind,task_id,load,view,execute_probe,Rejected,profile,ROOT,HERE
from cbor_codec import encode,decode
from rir_adapter import modules

LIMITS={'gas_limit':50000000,'output_limit':4800000,'memory_pages_limit':2,'call_depth_limit':8}

def fixture():
    wasm,_=modules()
    data=json.loads((ROOT/'experiments/aclt-rir-stats-probe/tests/fixture.json').read_text())
    body=wasm.normalize(bytes.fromhex(data['raw_hex']))[0]
    import struct
    return wasm.artifact(body),struct.pack('<QQ4q',2,4,3,-1,5,8)


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    report={'status':'RUNNING','hostname':platform.node(),'python':platform.python_version(),'scope':'candidate task identity/binding only; no authorization or Receipt'}
    try:
        profile() # Pin reference sources before importing their code.
        artifact,inp=fixture()
        raw,identity=freeze(artifact,[inp],bytes(32),bytes(range(16)),LIMITS)
        obj=load(raw)
        (output/'commitment.cbor').write_bytes(raw);(output/'artifact.cbor').write_bytes(artifact);(output/'input.bin').write_bytes(inp)
        (output/'view.json').write_text(json.dumps(view(obj),indent=2)+'\n')
        records=[]
        def reject(name,fn):
            try:fn()
            except Rejected as exc:records.append({'name':name,'status':'REJECTED','reason':str(exc)})
            else:raise AssertionError('invalid binding accepted: '+name)
        result=execute_probe(raw,identity,artifact,[inp])
        expected_rows=bytes.fromhex('0000000000000000000000000000000002000000000000000200000000000000ffffffffffffffff03000000000000000100000000000000020000000000000002000000000000000d0000000000000005000000000000000800000000000000')
        assert result['result']['output_hex']==expected_rows.hex() and result['result']['gas_used']==9126
        records.append({'name':'bound-execution','status':'TASK_OUTCOME',**result})
        assert freeze(artifact,[inp],bytes(32),bytes(range(16)),dict(reversed(list(LIMITS.items()))))==(raw,identity)
        records.append({'name':'map-order-invariance','status':'PASS','experimental_task_id':identity})
        variants=[]
        for name,new_input,changes in [('input-change',inp[:-1]+b'\x01',{}),('gas-change',inp,{'gas_limit':9125}),('output-limit-change',inp,{'output_limit':95}),('depth-change',inp,{'call_depth_limit':1})]:
            other,other_id=freeze(artifact,[new_input],bytes(32),bytes(range(16)),{**LIMITS,**changes})
            assert other_id!=identity and load(other)['rir_digest']==obj['rir_digest']
            variants.append({'name':name,'experimental_task_id':other_id,'rir_digest':obj['rir_digest'].hex()})
            reject('old-id-'+name,lambda other=other:bind(other,identity,artifact,[inp]))
            if name!='input-change':
                outcome=execute_probe(other,other_id,artifact,[inp])
                expected='TRAP_GAS_EXHAUSTED' if name=='gas-change' else 'TRAP_OUTPUT_LIMIT' if name=='output-limit-change' else 'OK'
                assert outcome['result']['outcome']==expected
                records.append({'name':'bound-'+name,'status':'TASK_OUTCOME',**outcome})
        wasm,_=modules()
        module=wasm.decode_artifact(artifact);module.code[0]=([],[{'op':0,'args':[]}])
        other_artifact=wasm.artifact(module.canonical())
        other,other_id=freeze(other_artifact,[inp],bytes(32),bytes(range(16)),LIMITS)
        assert load(other)['rir_digest']!=obj['rir_digest'] and other_id!=identity
        variants.append({'name':'artifact-change','experimental_task_id':other_id,'rir_digest':load(other)['rir_digest'].hex()})
        reject('old-artifact-new-task',lambda:bind(other,other_id,artifact,[inp]))
        changed_result=execute_probe(other,other_id,other_artifact,[inp])
        assert changed_result['result']['outcome']=='TRAP_UNREACHABLE'
        records.append({'name':'bound-artifact-change','status':'TASK_OUTCOME',**changed_result})
        reject('wrong-input-bytes',lambda:bind(raw,identity,artifact,[inp[:-1]+b'\x01']))
        reject('missing-input',lambda:bind(raw,identity,artifact,[]))
        reject('extra-input',lambda:bind(raw,identity,artifact,[inp,inp]))
        reject('wrong-artifact',lambda:bind(raw,identity,artifact+b'\0',[inp]))
        reject('wrong-task-id',lambda:bind(raw,'0'*64,artifact,[inp]))
        for name,key,value in [('profile-digest','execution_profile_digest',bytes(32)),('profile-id','execution_profile_id','unknown'),('equivalence','result_equivalence','unknown'),('version','rir_version',[0,2,0]),('requester-width','requester_ref',bytes(31))]:
            changed=copy.deepcopy(obj);changed[key]=value
            reject(name,lambda changed=changed:load(encode(changed)))
        extra={**obj,'ReceiptID':'not-a-receipt'}
        reject('unknown-field',lambda:load(encode(extra)))
        reject('trailing-cbor',lambda:load(raw+b'\0'))
        # A nonminimal uint8 map length represents the same object but is forbidden.
        assert len(obj)<24 and raw[0]==0xa0+len(obj)
        reject('padded-cbor-length',lambda:load(bytes([0xb8,len(obj)])+raw[1:]))
        evidence={'count':len(records),'cases':records,'identity_variants':variants}
        (output/'cases.json').write_text(json.dumps(evidence,indent=2)+'\n')
        (output/'identity.json').write_text(json.dumps({'experimental_task_id':identity,'authorization':'NOT_IMPLEMENTED'},indent=2)+'\n')
        local=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
        dependencies=[ROOT/n for n in profile()[0]['implementation_pins']]
        dependencies.append(ROOT/'experiments/aclt-rir-stats-probe/tests/fixture.json')
        report.update(status='PASS',cases=len(records),identity_variants=len(variants),experimental_task_id=identity,
                      rir_digest=obj['rir_digest'].hex(),execution_profile_digest=obj['execution_profile_digest'].hex(),
                      source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(local+dependencies)},
                      artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()})
    except BaseException as exc:
        report.update(status='FAIL',error=type(exc).__name__+': '+str(exc));raise
    finally:(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=run(a.output.resolve());print(json.dumps({'status':result['status'],'cases':result['cases'],'experimental_task_id':result['experimental_task_id']}))
