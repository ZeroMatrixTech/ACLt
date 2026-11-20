# SPDX-License-Identifier: Apache-2.0
"""Frozen binary adapters, independent math/C++ oracle, and runtime differential."""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import copy
import hashlib
import json
import random
import struct
import subprocess
from pathlib import Path
from wasm import Module, artifact, cbor
from runtime import load_candidate, Runner, Reject, HostFault

LIMITS=dict(gas_limit=50000000,output_limit=4800000,memory_pages_limit=2,call_depth_limit=8,max_steps=20000000)

def encode(chunk,values):return struct.pack('<QQ',chunk,len(values))+b''.join(struct.pack('<q',v) for v in values)
def rows(values,chunk):
    return [(i,start,len(v),sum(v),min(v),max(v)) for i,start in enumerate(range(0,len(values),chunk)) for v in [values[start:start+chunk]]]
def binary_rows(rs):return b''.join(struct.pack('<QQQqqq',*r) for r in rs)
def text_rows(rs):return ''.join(' '.join(map(str,r))+'\n' for r in rs).encode()
def decode_output(blob):
    if len(blob)%48:raise ValueError('incomplete result row')
    return [struct.unpack('<QQQqqq',blob[i:i+48]) for i in range(0,len(blob),48)]

def corpus():
    valid=[('singleton-zero',1,[0]),('negative',1,[-1]),('extremes',2,[-10**9,10**9,0,-10**9,10**9]),
           ('partial-last',3,[7,-9,12,0,5,-1,8]),('chunk-over-count',100000,[1,-2,3]),
           ('sum-positive',1000,[10**9]*1000),('sum-negative',1000,[-10**9]*1000)]
    rng=random.Random(20261023)
    for i in range(32):
        n=rng.randrange(1,80);valid.append((f'seeded-{i:02}',rng.choice([1,2,3,7,n,n+1,100000]),[rng.randint(-10**9,10**9) for _ in range(n)]))
    valid.append(('maximum-count',100000,[10**9 if i%2 else -10**9 for i in range(100000)]))
    return valid

def outcome_digest(result):
    value={k:v for k,v in result.items() if k!='outcome_digest'}
    if 'output_hex' in value:value['output']=bytes.fromhex(value.pop('output_hex'))
    tag=b'ACLt/RIR-0/ExecutionOutcome/1'
    return hashlib.sha256(bytes([len(tag)])+tag+cbor(value)).hexdigest()

def python_run(body,data,limits):
    try:return load_candidate(artifact(body),[data],**limits).run()
    except Reject:return {'kind':'REJECTED'}
    except HostFault:return {'kind':'HOST_FAULT'}

def native_run(executor,module,input_path,limits,log):
    p=subprocess.run([str(executor),str(module),str(input_path),str(limits['gas_limit']),str(limits['output_limit']),str(limits['call_depth_limit']),str(limits['max_steps']),str(limits['memory_pages_limit'])],capture_output=True,text=True,timeout=90)
    log.write_text(p.stdout+p.stderr)
    result=json.loads(p.stdout)
    expected=3 if result.get('kind')=='HOST_FAULT' else 2 if result.get('kind')=='REJECTED' else 0
    if p.returncode!=expected:raise AssertionError(('native exit status',p.returncode,result))
    if 'outcome' in result:result['outcome_digest']=outcome_digest(result)
    return result

def run(body,directory,executor,worker):
    directory=Path(directory);case_root=directory/'cases';case_root.mkdir()
    module_path=directory/'normalized.wasm';records=[]
    def check(name,data,expected=None,limits=None,module=body):
        idx=len(records);folder=case_root/f'{idx:03}-{name}';folder.mkdir()
        inp=folder/'input.bin';inp.write_bytes(data);lim={**LIMITS,**(limits or {})}
        mp=module_path
        if module!=body:mp=folder/'fixture.wasm';mp.write_bytes(module)
        py=python_run(module,data,lim);native=native_run(executor,mp,inp,lim,folder/'native.log')
        if {k:v for k,v in py.items() if k!='outcome_digest'}!={k:v for k,v in native.items() if k!='outcome_digest'}:raise AssertionError((name,'runtime mismatch',py,native))
        if expected:
            for k,v in expected.items():
                if py.get(k)!=v:raise AssertionError((name,k,py,v))
        record={'name':name,'input_sha256':hashlib.sha256(data).hexdigest(),'limits':lim,'actual':py}
        records.append(record);return py,folder,record
    for name,chunk,values in corpus():
        reference=rows(values,chunk);expected=binary_rows(reference)
        result,folder,record=check(name,encode(chunk,values),{'outcome':'OK','output_hex':expected.hex()})
        assert decode_output(bytes.fromhex(result['output_hex']))==reference
        text_input=folder/'reference.txt';text_input.write_text(' '.join(map(str,values))+'\n')
        p=subprocess.run([str(worker),str(text_input),str(chunk)],capture_output=True,timeout=90)
        (folder/'cpp-output.txt').write_bytes(p.stdout);(folder/'cpp-stderr.txt').write_bytes(p.stderr)
        if p.returncode or p.stdout!=text_rows(reference):raise AssertionError((name,'C++ oracle',p.returncode))
        record['cpp_stdout_sha256']=hashlib.sha256(p.stdout).hexdigest()
    for name,data,code in [
        ('short-header',b'',2),('trailing-byte',encode(1,[3])+b'\0',2),('truncated-values',encode(1,[3])[:-1],2),
        ('zero-chunk',encode(0,[3]),3),('huge-chunk',encode(100001,[3]),3),('zero-count',encode(1,[]),4),
        ('huge-count',struct.pack('<QQ',1,100001),4),('minimum-i64',encode(1,[-2**63]),5),('maximum-i64',encode(1,[2**63-1]),5),
        ('below-value-bound',encode(1,[-1000000001]),5),('above-value-bound',encode(1,[1000000001]),5),
        ('late-invalid-value',encode(1,[1,2,3,1000000001]),5)]:
        check(name,data,{'outcome':'ABORT','abort_code':code})
    sample=encode(2,[3,-1,5,8]);normal=python_run(body,sample,LIMITS);gas=normal['gas_used'];out=normal['output_hex']
    check('exact-gas',sample,{'outcome':'OK','gas_used':gas,'output_hex':out},{'gas_limit':gas})
    check('gas-short',sample,{'outcome':'TRAP_GAS_EXHAUSTED'},{'gas_limit':gas-1})
    check('zero-output',sample,{'outcome':'TRAP_OUTPUT_LIMIT'},{'output_limit':0})
    check('partial-output-discard',sample,{'outcome':'TRAP_OUTPUT_LIMIT'},{'output_limit':95})
    check('exact-output',sample,{'outcome':'OK','output_hex':out},{'output_limit':96})
    check('depth-abort',b'',{'outcome':'TRAP_CALL_DEPTH'},{'call_depth_limit':1})
    check('depth-normal',sample,{'outcome':'OK'},{'call_depth_limit':1})
    check('instantiation-gas',sample,{'kind':'REJECTED'},{'gas_limit':8191})
    check('instantiation-memory',sample,{'kind':'REJECTED'},{'memory_pages_limit':1})
    check('local-ceiling',sample,{'kind':'HOST_FAULT'},{'max_steps':1})
    # Hand-authored golden instruction sequences, independent of Rust compiler output.
    def node(op,*args,**kw):return dict(op=op,args=list(args),**kw)
    def fixture(nodes):
        m=Module(body);m.code[0]=([],nodes);return m.canonical()
    golden=[
        ('golden-empty',[],{'outcome':'OK','gas_used':8192,'output_hex':''}),
        ('golden-mul',[node(0x42,7),node(0x42,-3),node(0x7e),node(0x1a)],{'outcome':'OK','gas_used':8198,'output_hex':''}),
        ('golden-divzero',[node(0x42,7),node(0x42,0),node(0x7f),node(0x1a)],{'outcome':'TRAP_INTEGER_DIVIDE_BY_ZERO','gas_used':8202}),
        ('golden-divoverflow',[node(0x42,-2**63),node(0x42,-1),node(0x7f),node(0x1a)],{'outcome':'TRAP_INTEGER_OVERFLOW','gas_used':8202}),
        ('golden-memory',[node(0x41,131072),node(0x29,3,0),node(0x1a)],{'outcome':'TRAP_MEMORY_OOB','gas_used':8195}),
        ('golden-unreachable',[node(0)],{'outcome':'TRAP_UNREACHABLE','gas_used':8193}),
        ('golden-host-gas-first',[node(0x41,131072),node(0x41,1),node(0x10,3)],{'outcome':'TRAP_GAS_EXHAUSTED','gas_used':8194}),
    ]
    for name,nodes,expected in golden:check(name,sample,expected,{'gas_limit':8194} if name.endswith('gas-first') else None,fixture(nodes))
    return {'count':len(records),'valid_cpp_cases':len(corpus()),'runtimes':['Python reference','independent Rust Wasm decoder/executor'],
            'scope':'candidate stats wire adapter; exact arithmetic rows with C++/Python; not protocol conformance','cases':records}
