# SPDX-License-Identifier: Apache-2.0
"""Fixed I/O and boundary cases; gas expectations hand-counted for this fixture."""
import random
from wasm import Module,Reject,artifact
from runtime import Runner,HostFault,load_candidate

def vectors():
    data=bytes(range(16));out=[]
    def add(name,inputs,expected,limits=None,oracle=True,scope='bound-candidate-input'):
        out.append({'name':name,'inputs_hex':[x.hex() for x in inputs],'limits':limits or {},'expected':expected,'oracle':oracle,'scope':scope})
    for name,b in [('range',data),('zero',bytes(16)),('ff',b'\xff'*16),('high-bits',bytes([0,255,128,127])*4)]:
        add(name,[b],{'outcome':'OK','gas_used':8271,'output_hex':b.hex()})
    rng=random.Random(20261023)
    for i in range(32):
        b=bytes(rng.randrange(256) for _ in range(16));add('random-'+str(i),[b],{'outcome':'OK','gas_used':8271,'output_hex':b.hex()})
    for size in [0,1,15,17,64]:add('wrong-length-'+str(size),[b'x'*size],{'outcome':'ABORT','abort_code':2,'gas_used':8221})
    for name,inputs in [('no-input',[]),('two-inputs',[data,data])]:
        add('binding-'+name,inputs,{'rejected':True})
        add('module-only-'+name,inputs,{'outcome':'ABORT','abort_code':1,'gas_used':8213},{'input_arity':None},True,'unbound-module-ABI-probe')
    add('gas-exact',[data],{'outcome':'OK','gas_used':8271,'output_hex':data.hex()},{'gas_limit':8271},False)
    add('gas-minus-one',[data],{'outcome':'TRAP_GAS_EXHAUSTED','gas_used':8270},{'gas_limit':8270},False)
    add('gas-before-output',[data],{'outcome':'TRAP_GAS_EXHAUSTED','gas_used':8248},{'gas_limit':8265},False)
    add('instantiation-gas-reject',[data],{'rejected':True},{'gas_limit':8191},False)
    add('memory-limit-reject',[data],{'rejected':True},{'memory_pages_limit':1},False)
    for n in [0,15]:add('output-limit-'+str(n),[data],{'outcome':'TRAP_OUTPUT_LIMIT','gas_used':8266},{'output_limit':n})
    add('host-calls-do-not-add-depth',[data],{'outcome':'OK','gas_used':8271,'output_hex':data.hex()},{'call_depth_limit':1},False)
    add('internal-abort-wrapper-depth',[b'bad'],{'outcome':'TRAP_CALL_DEPTH','gas_used':8219},{'call_depth_limit':1},False)
    add('local-resource-ceiling-is-host-fault',[data],{'host_fault':True},{'max_steps':1},False)
    return out

def run(raw):
    results=[]
    for case in vectors():
        inputs=[bytes.fromhex(h) for h in case['inputs_hex']]
        try:
            runner=(Runner(Module(raw),inputs,**case['limits']) if case['scope']=='unbound-module-ABI-probe' else load_candidate(artifact(raw),inputs,**case['limits']))
            actual=runner.run();trace=runner.host.trace
        except Reject as exc:actual={'rejected':True,'reason':str(exc)};trace=[]
        except HostFault as exc:actual={'host_fault':True,'reason':str(exc)};trace=[]
        for key,value in case['expected'].items():
            if actual.get(key)!=value:raise AssertionError((case['name'],key,actual,value))
        if actual.get('outcome')!='OK' and 'output_hex' in actual:raise AssertionError('partial output escaped')
        results.append({**case,'actual':actual,'host_trace':trace})
    return {'status':'PASS','fixture':'io16@1','seed':20261023,'cases':results,'count':len(results),'scope':'Python candidate subset; gas independently hand-counted for this fixture, no general proof'}
