#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""FM-S1b independent content-DAG, quote matrix, binding and signing cross-check."""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.formal_migration import policy as p
from tools.formal_migration import foundation as f
from tools.verification_profile import codec as c
spec=importlib.util.spec_from_file_location('fm1driver',ROOT/'scripts/check-fm-s1a.py');fm1=importlib.util.module_from_spec(spec);spec.loader.exec_module(fm1)
VECTOR=ROOT/'tests/formal_migration/policy-vectors.json'

def fixture(requester=b'r'*32):
    header=dict(schema_version=1,encoding_profile_id=c.ENCODING,protocol_version=[0,5,0],network_id=b'n'*32,deployment_id=b'd'*32)
    scope=dict(requester_ref=requester,nonce=b'x'*32,created_at=2000,expires_at=6000)
    logical=dict(header,object_type='FM_STATS_I32_VECTOR',object_version=[1,0,0],publisher_ref=requester,created_at=1000,available_until=7000,parents=[],content=c.encode([3,-2,7]))
    funding=dict(header,scope=copy.deepcopy(scope),source='REQUESTER_PREFUNDED',asset='FM_TEST_UNIT',execution_limit=7,verification_limit=5,storage_limit=3,refund_reserve=2,total_limit=17)
    rows=[]
    for terminal,executor,auditor,storage in p.matrix_keys():
        rows.append(dict(terminal=terminal,executor=executor,auditor=auditor,storage=storage,execution_fee=7 if executor=='COMPLETE' else 0,verification_fee=5 if auditor=='COMPLETE' else 0,storage_fee=3 if storage=='COMPLETE' else 0,refund_action='RETURN_REMAINDER'))
    settlement=dict(header,scope=copy.deepcopy(scope),method='REEXEC_AUDIT_ONLY',rows=rows)
    components=[dict(kind=k,version=[1,0,0],content=('FM-S1b fixture '+k+'; bytes-only reference, no conformance claim').encode()) for k in p.COMPONENTS]
    execution=dict(fuel=10000,memory_bytes=65536,input_bytes_limit=4096,output_bytes_limit=4096,max_assignments=2,max_attempts=1,message_retries=3,recovery_queries=8,deadline=5000,capabilities=[],architecture='wasm32',network='DENY',sandbox='REQUIRED')
    receipt=dict(header,scope=scope,task_family='stats-int-v1',entry='stats_int_v1',output_type='FM_STATS_INT_RESULT',success='EXACT_TASK_OUTCOME',merge='SINGLE_ASSIGNMENT',failure='FROZEN_AUDIT_MAPPING',method='REEXEC_AUDIT_ONLY',input_refs=[],funding_ref={},settlement_ref={},component_refs=[],execution=execution)
    return rebind(dict(receipt=receipt,funding=funding,settlement=settlement,inputs=[logical],components=components))

def rebind(b):
    r=b['receipt'];r['funding_ref']=p.ref('FUNDING',b['funding']);r['settlement_ref']=p.ref('SETTLEMENT',b['settlement']);r['input_refs']=[p.ref('LOGICAL',x) for x in b['inputs']];r['component_refs']=[p.ref(x['kind'],x) for x in b['components']];return b

def signing_request(b,record,key):
    sig=fm1.openssl('dgst','-sha256','-sign',key,'-sigopt','rsa_padding_mode:pkcs1',input=p.signing_input(b))
    return dict(bundle=b,record=record,signature=sig,expected_receipt=p.bundle(b),expected_requester=f.principal_digest(record),now=3000)

def freeze(tmp):
    b=fixture();rows=[]
    def add(label,kind,v,valid=True):
        raw=v if isinstance(v,bytes) else c.encode(v);r=dict(id=label,kind=kind,cbor_hex=raw.hex(),valid=valid)
        try:got=p.inspect(kind,raw)
        except c.CodecError:
            if valid:raise
        else:
            assert valid,label;r['expected']=got
        rows.append(r)
    for label,kind,v in [('logical','fm2-logical',b['inputs'][0]),('funding','fm2-funding',b['funding']),('settlement','fm2-settlement',b['settlement']),('rir','fm2-component',b['components'][0]),('receipt','fm2-receipt',b['receipt']),('bundle','fm2-bundle',b)]:add(label,kind,v)
    for field,value in [('source','ISSUANCE'),('asset','USD'),('execution_limit',True),('refund_reserve',2**64-1),('total_limit',16)]:
        v=copy.deepcopy(b['funding']);v[field]=value;add('funding-'+field,'fm2-funding',v,False)
    for label,edit in [('missing-cell',lambda x:x['rows'].pop()),('duplicate-cell',lambda x:x['rows'].__setitem__(1,copy.deepcopy(x['rows'][0]))),('reordered-cell',lambda x:x['rows'].reverse()),('hostfault-fee',lambda x:next(r for r in x['rows'] if r['executor']=='HOST_FAULT').update(execution_fee=1)),('refund-rule',lambda x:x['rows'][0].update(refund_action='KEEP'))]:
        v=copy.deepcopy(b['settlement']);edit(v);add(label,'fm2-settlement',v,False)
    for label,edit in [('cycle-policy',lambda x:x.update(receipt_ref=p.ref('RECEIPT',b['receipt']))),('cycle-scope',lambda x:x['scope'].update(receipt_id=b'\0'*32))]:
        v=copy.deepcopy(b['funding']);edit(v);add(label,'fm2-funding',v,False)
    for label,edit in [('bounded',lambda x:x.update(method='REEXEC_BOUNDED')),('snapshot',lambda x:x.update(eligibility_snapshot=b'\0'*32)),('attempts',lambda x:x['execution'].update(max_attempts=2)),('no-deadline',lambda x:x['execution'].update(deadline=0)),('wrong-ref-kind',lambda x:x['funding_ref'].update(kind='RECEIPT'))]:
        v=copy.deepcopy(b['receipt']);edit(v);add(label,'fm2-receipt',v,False)
    key=tmp/'requester.pem';record=fm1.record(fm1.keypair(key));signed=signing_request(fixture(f.principal_digest(record)),record,key);add('signed-receipt','fm2-verify',signed)
    for label,edit in [('old-receipt-pin',lambda x:x.update(expected_receipt=b'z'*32)),('old-requester-pin',lambda x:x.update(expected_requester=b'z'*32)),('bad-signature',lambda x:x.update(signature=b'\0'*256)),('expired',lambda x:x.update(now=5000))]:
        v=copy.deepcopy(signed);edit(v);add(label,'fm2-verify',v,False)
    return rows

def compare(rows,binary,tmp):
    cases=[]
    def add(label,kind,v,valid):
        raw=v if isinstance(v,bytes) else c.encode(v)
        try:got=p.inspect(kind,raw)
        except c.CodecError:
            assert not valid,label;got=None
        else:assert valid,label
        cases.append((label,kind,raw.hex(),got))
        return got
    for row in rows:
        result=add(row['id'],row['kind'],bytes.fromhex(row['cbor_hex']),row['valid']);assert result==row.get('expected'),row['id']
        if row['valid'] and row['kind'] not in ('fm2-quote','fm2-verify'):
            view=json.dumps(result['schema_view']);assert p.from_view_json(row['kind'],view).hex()==row['cbor_hex'];cases.append(('view-'+row['id'],'view-'+row['kind'],view,result))
    b=c.decode(bytes.fromhex(next(r['cbor_hex'] for r in rows if r['id']=='bundle')));base=p.bundle(b)
    for cell in p.matrix_keys():
        q=dict(bundle=b,**dict(zip(('terminal','executor','auditor','storage'),cell)));expected=add('matrix-'+str(cell),'fm2-quote',q,True)
        a=expected['amounts'];paid=sum(int(x) for x in a.values());assert paid+int(expected['refund'])==17 and int(expected['refund'])>=2
        for state,fee in zip(cell[1:],['execution_fee','verification_fee','storage_fee']):assert int(a[fee])==(dict(execution_fee=7,verification_fee=5,storage_fee=3)[fee] if state=='COMPLETE' else 0)
    # Each immutable semantic group changes the commitment after legal rebinding.
    mutations=[('funding',lambda b:b['funding'].update(refund_reserve=3,total_limit=18)),('settlement',lambda b:next(r for r in b['settlement']['rows'] if r['executor']=='COMPLETE').update(execution_fee=6)),('input',lambda b:b['inputs'][0].update(content=c.encode([3,-2,8]))),('resource',lambda b:b['receipt']['execution'].update(fuel=10001))]
    mutations +=[(k,lambda b,i=i:b['components'][i].update(content=b'changed explicit '+p.COMPONENTS[i].encode())) for i,k in enumerate(p.COMPONENTS)]
    for label,edit in mutations:
        changed=copy.deepcopy(b);edit(changed)
        if label!='resource':add(label+'-stale','fm2-bundle',changed,False)
        rebind(changed);got=add(label+'-rebound','fm2-bundle',changed,True);assert got['digest_hex']!=base.hex(),label
        if label in ('funding','settlement','input','resource'):assert changed['receipt']['component_refs'][0]==b['receipt']['component_refs'][0]
    bads=[('missing-input',lambda x:x.update(inputs=[])),('missing-component',lambda x:x['components'].pop()),('extra-component',lambda x:x['components'].append(x['components'][0])),('wrong-component-kind',lambda x:x['components'][0].update(kind='RUNTIME')),('short-availability',lambda x:x['inputs'][0].update(available_until=4999)),('foreign-scope',lambda x:x['funding']['scope'].update(nonce=b'z'*32)),('foreign-network',lambda x:x['funding'].update(network_id=b'z'*32)),('over-bucket',lambda x:next(r for r in x['settlement']['rows'] if r['executor']=='COMPLETE').update(execution_fee=8)),('i32-overflow',lambda x:x['inputs'][0].update(content=c.encode([2**31]))),('input-missing',lambda x:x['inputs'][0].update(content=c.encode([]))),('input-budget',lambda x:x['receipt']['execution'].update(input_bytes_limit=1)),('unknown-schema',lambda x:x['inputs'][0].update(object_version=[2,0,0])),('logical-parent-cycle',lambda x:x['inputs'][0].update(parents=[p.ref('RECEIPT',x['receipt'])])),('effect',lambda x:x['receipt']['execution'].update(capabilities=['network'])),('zero-recovery',lambda x:x['receipt']['execution'].update(recovery_queries=0)),('fee-overflow',lambda x:next(r for r in x['settlement']['rows'] if r['executor']==r['auditor']=='COMPLETE').update(execution_fee=2**64-1,verification_fee=1))]
    for label,edit in bads:
        changed=copy.deepcopy(b);edit(changed);rebind(changed);add(label,'fm2-bundle',changed,False)
    for terminal in ['TRUSTED','UNKNOWN']:
        add('unsupported-quote-'+terminal,'fm2-quote',dict(bundle=b,terminal=terminal,executor='MISSING',auditor='MISSING',storage='MISSING'),False)
    for terminal in p.PRESTART_TERMINALS:
        add('prestart-invalid-fulfillment-'+terminal,'fm2-quote',dict(bundle=b,terminal=terminal,executor='COMPLETE',auditor='MISSING',storage='MISSING'),False)
    # Re-sign changed policies from a new temporary key, compare independently built inputs.
    key=tmp/'fresh.pem';record=fm1.record(fm1.keypair(key));bb=fixture(f.principal_digest(record));initial=signing_request(bb,record,key);add('fresh-signed','fm2-verify',initial,True)
    bb2=copy.deepcopy(bb);bb2['funding'].update(refund_reserve=3,total_limit=18);rebind(bb2)
    rebound=signing_request(bb2,record,key);add('new-policy-resigned','fm2-verify',rebound,True)
    stale=copy.deepcopy(rebound);stale['expected_receipt']=initial['expected_receipt'];add('new-policy-old-pin','fm2-verify',stale,False)
    stale=copy.deepcopy(rebound);stale['signature']=initial['signature'];add('new-policy-old-signature','fm2-verify',stale,False)
    rust=json.loads(subprocess.run([str(binary)],input='fm2-bundle\t'+c.encode(bb2).hex()+'\n',text=True,capture_output=True,check=True,timeout=30).stdout)
    rust_input=bytes.fromhex(rust['signing_input_hex']);assert rust_input==p.signing_input(bb2)
    rust_sig=fm1.openssl('dgst','-sha256','-sign',key,'-sigopt','rsa_padding_mode:pkcs1',input=rust_input);assert rust_sig==rebound['signature']
    for mode,source in [('view-fm2-funding','{"source":"REQUESTER_PREFUNDED","source":"ISSUANCE"}'),('view-fm2-receipt','null'),('view-fm2-bundle','NaN')]:
        try:p.from_view_json(mode[5:],source)
        except c.CodecError:pass
        else:raise AssertionError(source)
        cases.append(('invalid-json',mode,source,None))
    result=subprocess.run([str(binary)],input=''.join(mode+'\t'+wire+'\n' for _,mode,wire,_ in cases),capture_output=True,text=True,check=True,timeout=120)
    lines=result.stdout.splitlines();assert len(lines)==len(cases),(len(lines),len(cases))
    for (label,mode,wire,want),line in zip(cases,lines):
        got=json.loads(line)
        if want is None:assert set(got)=={'error'},('Rust accepted',label,got)
        else:assert got==want,('Rust mismatch',label,got.keys(),want.keys())
    return dict(cases=len(cases),matrix_cells=111,fixed_vectors=len(rows),fixed_positive=sum(x['valid'] for x in rows),negative_cases=sum(x[3] is None for x in cases),fresh_policy_resigning=True)

def main():
    arg=argparse.ArgumentParser(description=__doc__);arg.add_argument('--report',type=Path);arg.add_argument('--freeze-vectors',action='store_true');a=arg.parse_args()
    if a.report and a.report.exists():arg.error('report exists')
    with tempfile.TemporaryDirectory(prefix='aclt-fm-s1b-') as name:
        tmp=Path(name);binary=tmp/'codec';subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings','-C','overflow-checks=yes','-O',str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True,timeout=90)
        if a.freeze_vectors:
            if VECTOR.exists():arg.error('vectors exist')
            rows=freeze(tmp);VECTOR.write_text(json.dumps(dict(status='CANDIDATE_TEST_ONLY',vectors=rows),ensure_ascii=False,indent=2)+'\n')
        else:rows=json.loads(VECTOR.read_text())['vectors']
        result=compare(rows,binary,tmp);result.update(status='PASS',scope='FM-S1b candidate content/signature contract; hypothetical quotes, no settlement or terminal authority',python=subprocess.check_output([sys.executable,'--version'],text=True).strip(),rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),openssl=fm1.openssl('version').decode().strip(),source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['tools/formal_migration/policy.py','tools/formal_migration/foundation.py','tools/verification_profile/codec.py','tools/verification_profile/rust/main.rs','tools/verification_profile/rust/profile.rs','tools/verification_profile/rust/registration.rs','tools/verification_profile/rust/audit_types.json','tools/verification_profile/rust/method_types.json','tools/verification_profile/rust/method_rules.rs','tools/verification_profile/rust/creation.rs','tools/verification_profile/rust/creation_types.json','tools/verification_profile/rust/selection.rs','tools/verification_profile/rust/selection_types.json','tools/verification_profile/rust/commitments.rs','tools/verification_profile/rust/runtime_bindings.rs','tools/verification_profile/rust/binding_types.json','tools/verification_profile/rust/runtime_types.json','tools/verification_profile/rust/fm.rs','tools/verification_profile/rust/fm_policy.rs','tools/verification_profile/rust/sha256.rs','tools/verification_profile/rust/nfc.rs','tools/verification_profile/rust/unicode_data.rs','scripts/check-fm-s1a.py','scripts/check-fm-s1b.py','tests/formal_migration/policy-vectors.json']})
    if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'},indent=2))
if __name__=='__main__':main()
