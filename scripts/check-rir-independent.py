#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Standalone raw-artifact Rust entry vs Python: validation, execution, bytes/hash.

Explicit restricted stats-core independence evidence; not full ADR acceptance.
"""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];PROBE=ROOT/'experiments/aclt-rir-stats-probe';sys.path[:0]=[str(ROOT),str(PROBE)]
from tools.verification_profile import codec as c
from wasm import Module,Reader,artifact,normalize,section,u,s
from cases import LIMITS,encode,corpus
from independent import execute,validate,CoreReject
VECTOR=PROBE/'tests/independent-vectors.json'

def body():return normalize(bytes.fromhex(json.loads((PROBE/'tests/fixture.json').read_text())['raw_hex']))[0]
def node(op,*args,**kw):return dict(op=op,args=list(args),**kw)
def fixture(nodes):
    m=Module(body());m.code[0]=([],nodes);return m.canonical()
def envelope(b,**fields):return c.encode(dict(schema_version=1,encoding_profile_id='acl.enc.rir-0@1',rir_version=[0,1,0],entry='run',input_arity=1,body=b,**fields)) if fields else artifact(b)

def freeze():
    rows=[];sample=encode(2,[3,-1,5,8]);default=dict(LIMITS)
    def add(name,blob,data=sample,limits=None,expected=None,code=None,hook=''):
        lim=dict(default,**(limits or {}));pin=c.domain_hash('ACLt/RIR-0/Artifact/1',blob).hex();got=execute(blob,data,lim,pin,hook)
        if code:assert got==dict(status='REJECTED',code=code),(name,got,code)
        if expected:
            for k,v in expected.items():assert got.get('result',got).get(k)==v,(name,got,expected)
        rows.append(dict(id=name,artifact_hex=blob.hex(),input_hex=data.hex(),limits=lim,expected_rir=pin,hook=hook,expected=got))
    blob=artifact(body());add('stats',blob,expected=dict(outcome='OK',gas_used=9126));add('gas-exact',blob,limits={'gas_limit':9126});add('gas-short',blob,limits={'gas_limit':9125},expected=dict(outcome='TRAP_GAS_EXHAUSTED'))
    add('output-partial-discard',blob,limits={'output_limit':49},expected=dict(outcome='TRAP_OUTPUT_LIMIT'));add('depth-trap',blob,b'',{'call_depth_limit':1},dict(outcome='TRAP_CALL_DEPTH'))
    for name,ns,expected in [('empty',[],dict(outcome='OK',gas_used=8192)),('multiply',[node(0x42,7),node(0x42,-3),node(0x7e),node(0x1a)],dict(outcome='OK',gas_used=8198)),('divzero',[node(0x42,7),node(0x42,0),node(0x7f),node(0x1a)],dict(outcome='TRAP_INTEGER_DIVIDE_BY_ZERO',gas_used=8202)),('divoverflow',[node(0x42,-2**63),node(0x42,-1),node(0x7f),node(0x1a)],dict(outcome='TRAP_INTEGER_OVERFLOW',gas_used=8202)),('remainder-min',[node(0x42,-2**63),node(0x42,-1),node(0x81),node(0x1a)],dict(outcome='OK',gas_used=8203)),('memory-oob',[node(0x41,131072),node(0x29,3,0),node(0x1a)],dict(outcome='TRAP_MEMORY_OOB')),('unreachable',[node(0)],dict(outcome='TRAP_UNREACHABLE'))]:add(name,artifact(fixture(ns)),expected=expected)
    # All four A codes plus typed-input negatives. Explicit expectations are not inferred from Rust.
    for name,bad in [('trailing',blob+b'\0'),('nonminimal-envelope',b'\xb8\x06'+blob[1:]),('duplicate-key',b'\xa2\x61a\x00\x61a\x00'),('invalid-utf8',b'\xa1\x61\xff\x00'),('float-envelope',bytes.fromhex('fa3f800000'))]:add(name,bad,code='RIR_REJECT_ENCODING')
    base=c.decode(blob)
    for field,val in [('schema_version',2),('entry','other'),('rir_version',[0,2,0]),('input_arity',True),('body','wasm')]:
        obj=copy.deepcopy(base);obj[field]=val;add('field-'+field,c.encode(obj),code='RIR_REJECT_UNSUPPORTED')
    obj=copy.deepcopy(base);obj['extra']=1;add('unknown-field',c.encode(obj),code='RIR_REJECT_UNSUPPORTED')
    for name,ns in [('local-index',[node(0x20,4096)]),('wrong-type',[node(0x42,1)]),('operand-underflow',[node(0x54)]),('branch-depth',[node(0x0c,99)]),('memory-alignment',[node(0x41,0),node(0x29,4,0),node(0x1a)])]:
        add(name,artifact(fixture(ns)),code='RIR_REJECT_INVALID')
    for arity,code in [(0,'RIR_REJECT_INVALID'),(2,'RIR_REJECT_INVALID'),(2**32,'RIR_REJECT_LIMITS')]:
        obj=copy.deepcopy(base);obj['input_arity']=arity;add('arity-'+str(arity),c.encode(obj),code=code)
    add('gas-below-instantiate',blob,limits={'gas_limit':8191},code='RIR_REJECT_LIMITS');add('support-gas-max',blob,limits={'gas_limit':50000001},code='RIR_REJECT_LIMITS');add('support-depth',blob,limits={'call_depth_limit':65},code='RIR_REJECT_LIMITS');add('support-memory',blob,limits={'memory_pages_limit':3},code='RIR_REJECT_LIMITS')
    add('local-step-host-fault',blob,limits={'max_steps':1},expected=dict(status='HOST_FAULT'));add('memory-fault-injection',blob,hook='test-memory-fault',expected=dict(status='HOST_FAULT'))
    # A canonical body's nonminimal section-length LEB must fail before execution.
    b=body();r=Reader(b[9:]);length=r.num();width=r.pos;bad=b[:9]+bytes([length|128,0])+b[9+width:] if length<128 else None
    if bad is not None:add('nonminimal-section-length',artifact(bad),code='RIR_REJECT_ENCODING')
    return rows

def run_native(exe,row,tmp,env=None):
    a=tmp/'artifact.cbor';i=tmp/'input.bin';a.write_bytes(bytes.fromhex(row['artifact_hex']));i.write_bytes(bytes.fromhex(row['input_hex']));lim=row['limits']
    cmd=[str(exe),'--artifact',str(a),str(i),str(lim['gas_limit']),str(lim['output_limit']),str(lim['call_depth_limit']),str(lim['max_steps']),str(lim['memory_pages_limit']),row['expected_rir']]
    if row.get('hook'):cmd.append(row['hook'])
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60,env=env);result=json.loads(r.stdout);expected_exit={'TASK_OUTCOME':0,'REJECTED':2,'HOST_FAULT':3}[result['status']];assert r.returncode==expected_exit,(row['id'],r.returncode,r.stdout,r.stderr)
    if result['status']!='TASK_OUTCOME':assert not any(k in result for k in ('result','canonical_outcome_hex','outcome_digest')),row['id']
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path);p.add_argument('--freeze-vectors',action='store_true');args=p.parse_args()
    if args.report and args.report.exists():p.error('report exists')
    if args.freeze_vectors:
        if VECTOR.exists():p.error('vectors exist')
        VECTOR.write_text(json.dumps(dict(scope='RIR_STATS_INDEPENDENT_CORE_1',vectors=freeze()),indent=2)+'\n')
    rows=json.loads(VECTOR.read_text())['vectors'];records=[]
    with tempfile.TemporaryDirectory(prefix='rir-independent-check-') as name:
        tmp=Path(name);exe=tmp/'executor';subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings','-C','overflow-checks=yes','-O',str(PROBE/'src/independent_executor.rs'),'-o',str(exe)],check=True,timeout=90)
        support=json.loads(subprocess.check_output([str(exe),'--support'],text=True));assert support['full_ADR_0006_conformance'] is False
        contract=json.loads((PROBE/'independent-contract.json').read_text())
        for k,v in contract['support'].items():
            if k in support:assert support[k]==v,k
        for row in rows:
            py=execute(bytes.fromhex(row['artifact_hex']),bytes.fromhex(row['input_hex']),row['limits'],row['expected_rir'],row.get('hook',''));assert py==row['expected'],row['id'];rust=run_native(exe,row,tmp);assert rust==py,(row['id'],rust,py);records.append(dict(id=row['id'],result=rust))
        # Run a copied binary with no Python or OpenSSL in PATH and no source files.
        isolated=tmp/'isolated';isolated.mkdir();standalone=isolated/'executor';shutil.copyfile(exe,standalone);standalone.chmod(0o700);env=dict(os.environ,PATH=str(isolated));assert run_native(standalone,rows[0],isolated,env)==rows[0]['expected'];records.append(dict(id='no-python-no-sources',result=rows[0]['expected']))
        wrong=copy.deepcopy(rows[0]);wrong['expected_rir']='00'*32;got=run_native(exe,wrong,tmp);assert got==dict(status='HOST_FAULT',code='RPR_REVALIDATION_MISMATCH');records.append(dict(id='wrong-caller-rir-pin',result=got))
        # Real stats workload and seeded valid programs, no Python prevalidation fed to Rust.
        workload=corpus()[:-1] # max-count corpus retained in old suite; avoid repeating a costly case here.
        for label,chunk,values in workload:
            row=dict(rows[0],id=label,input_hex=encode(chunk,values).hex());py=execute(bytes.fromhex(row['artifact_hex']),bytes.fromhex(row['input_hex']),row['limits'],row['expected_rir']);got=run_native(exe,row,tmp);assert got==py,label;records.append(dict(id='stats-'+label,result=got))
        rng=random.Random(20261028)
        for index in range(80):
            op=rng.choice([0x7c,0x7d,0x7e,0x83,0x84,0x85,0x86,0x87,0x88,0x89,0x8a]);ns=[node(0x41,0),node(0x42,rng.randrange(-2**63,2**63)),node(0x42,rng.randrange(-2**63,2**63)),node(op),node(0x37,3,0),node(0x41,0),node(0x41,8),node(0x10,3)];raw=artifact(fixture(ns));row=dict(rows[0],id='seeded-program-'+str(index),artifact_hex=raw.hex(),expected_rir=c.domain_hash('ACLt/RIR-0/Artifact/1',raw).hex());py=execute(raw,bytes.fromhex(row['input_hex']),row['limits'],row['expected_rir']);got=run_native(exe,row,tmp);assert got==py,row['id'];records.append(dict(id=row['id'],result=got))
        # Declared output range exceeds the input-envelope CBOR resource cap.
        ns=[node(0x41,0),node(0x41,131072),node(0x10,3)]*9;raw=artifact(fixture(ns));row=dict(rows[0],id='output-over-one-MiB',artifact_hex=raw.hex(),expected_rir=c.domain_hash('ACLt/RIR-0/Artifact/1',raw).hex());py=execute(raw,bytes.fromhex(row['input_hex']),row['limits'],row['expected_rir']);got=run_native(exe,row,tmp);assert got==py and len(bytes.fromhex(got['result']['output_hex']))==9*131072;records.append(dict(id=row['id'],result=got))
        # Input I/O loss cannot become a semantic Task trap.
        missing=copy.deepcopy(rows[0]);a=tmp/'lost-artifact';a.write_bytes(bytes.fromhex(missing['artifact_hex']));lim=missing['limits'];r=subprocess.run([str(exe),'--artifact',str(a),str(tmp/'does-not-exist'),str(lim['gas_limit']),str(lim['output_limit']),str(lim['call_depth_limit']),str(lim['max_steps']),'2',missing['expected_rir']],capture_output=True,text=True,timeout=30);got=json.loads(r.stdout);assert r.returncode==3 and got['status']=='HOST_FAULT' and 'outcome_digest' not in got;records.append(dict(id='actual-missing-input',result=got))
        # Artifact digest must not depend on execution limits; candidate Receipt linkage remains separate.
        first=rows[0]['expected'];other=next(r['expected'] for r in rows if r['id']=='gas-exact');assert first['rir_digest']==other['rir_digest'] and first['outcome_digest']==other['outcome_digest']
    files=['experiments/aclt-rir-stats-probe/src/independent_executor.rs','experiments/aclt-rir-stats-probe/src/core.rs','experiments/aclt-rir-stats-probe/independent.py','experiments/aclt-rir-stats-probe/wasm.py','experiments/aclt-rir-stats-probe/runtime.py','experiments/aclt-rir-stats-probe/cases.py','experiments/aclt-rir-stats-probe/tests/fixture.json','experiments/aclt-rir-stats-probe/tests/independent-vectors.json','tools/verification_profile/codec.py','tools/verification_profile/rust/main.rs','tools/verification_profile/rust/profile.rs','tools/verification_profile/rust/registration.rs','tools/verification_profile/rust/audit_types.json','tools/verification_profile/rust/method_types.json','tools/verification_profile/rust/method_rules.rs','tools/verification_profile/rust/creation.rs','tools/verification_profile/rust/creation_types.json','tools/verification_profile/rust/selection.rs','tools/verification_profile/rust/selection_types.json','tools/verification_profile/rust/commitments.rs','tools/verification_profile/rust/runtime_bindings.rs','tools/verification_profile/rust/decision_replay.rs','tools/verification_profile/rust/binding_types.json','tools/verification_profile/rust/runtime_types.json','tools/verification_profile/rust/fm.rs','tools/verification_profile/rust/fm_policy.rs','experiments/aclt-rir-stats-probe/independent-contract.json','tools/verification_profile/rust/sha256.rs','tools/verification_profile/rust/nfc.rs','tools/verification_profile/rust/unicode_data.rs','scripts/check-rir-independent.py']
    report=dict(status='PASS',scope='restricted independent stats-core; not complete ADR-0006 acceptance',fixed_vectors=len(rows),cases=len(records),source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in files},support=support,python_version=sys.version.split()[0],rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),results_sha256=hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest(),cases_detail=records)
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases_detail','source_sha256')},indent=2))
if __name__=='__main__':main()
