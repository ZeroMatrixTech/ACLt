# SPDX-License-Identifier: Apache-2.0
"""Bounded Python reference runner for the I/O slice; not a production RPR."""
from wasm import Module, MEM, ABI, need, Reject, cbor, decode_artifact
import hashlib

class Trap(Exception):
    def __init__(self,code,abort_code=None):self.code=code;self.abort_code=abort_code
class HostFault(Exception):pass
class Jump(Exception):
    def __init__(self,depth):self.depth=depth
class Return(Exception):pass

class Host:
    def __init__(self,inputs,memory_bytes,gas_limit,output_limit,max_steps=100000):
        need(1<=gas_limit<=2**63-1 and 0<=output_limit<2**64,'limits')
        need(len(inputs)<2**32,'input arity')
        self.inputs=tuple(bytes(x) for x in inputs)
        self.memory=bytearray(memory_bytes);self.gas_limit=gas_limit;self.gas_used=0
        self.output_limit=output_limit;self.output=bytearray();self.trace=[];self.steps=0;self.max_steps=max_steps
    def charge(self,cost):
        self.steps+=1
        if self.steps>self.max_steps:raise HostFault('HOST_RESOURCE_EXHAUSTED: local step ceiling')
        if self.gas_limit-self.gas_used<cost:raise Trap('TRAP_GAS_EXHAUSTED')
        self.gas_used+=cost
    def call(self,name,args):
        if name not in ABI or len(args)!=len(ABI[name][0]) or any(type(v) is not int or not 0<=v<2**(32 if t==0x7f else 64) for v,t in zip(args,ABI[name][0])):
            raise HostFault('RPR_INTERNAL_ERROR: malformed typed ABI values')
        cost=4 if name in ('input_count','input_len') else 1 if name=='abort' else 16+(args[-1]+7)//8
        self.charge(cost)
        self.trace.append({'name':name,'args':list(args),'gas_used':self.gas_used})
        if name=='input_count':return len(self.inputs)
        if name=='abort':raise Trap('ABORT',args[0]&0xffffffff)
        if name=='input_len':
            if args[0]>=len(self.inputs):raise Trap('TRAP_HOST_ARGUMENT')
            return len(self.inputs[args[0]])
        if name=='input_read':
            index,offset,dst,length=args
            if index>=len(self.inputs) or offset+length>len(self.inputs[index]) or dst+length>len(self.memory):raise Trap('TRAP_HOST_ARGUMENT')
            self.memory[dst:dst+length]=self.inputs[index][offset:offset+length];return
        if name=='output_write':
            src,length=args
            if src+length>len(self.memory):raise Trap('TRAP_HOST_ARGUMENT')
            if len(self.output)+length>self.output_limit:raise Trap('TRAP_OUTPUT_LIMIT')
            self.output.extend(self.memory[src:src+length]);return
        raise HostFault('RPR_INTERNAL_ERROR: unknown host import')

class Runner:
    def __init__(self,module,inputs,gas_limit=100000,output_limit=16,memory_pages_limit=2,call_depth_limit=8,max_steps=100000,input_arity=1):
        need(module.canonical()==module.raw,'RIR_REJECT_ENCODING: canonical Wasm required')
        if input_arity is not None:need(len(inputs)==input_arity,'RIR_REJECT_INVALID: input count binding')
        need(module.initial<=memory_pages_limit<=module.maximum and 1<=call_depth_limit<=4096,'RIR_REJECT_LIMITS')
        self.instantiation_cost=4096*module.initial
        need(gas_limit>=self.instantiation_cost,'RIR_REJECT_LIMITS: instantiation gas')
        self.module=module;self.host=Host(inputs,module.initial*65536,gas_limit,output_limit,max_steps)
        self.depth_limit=call_depth_limit
        self.globals=[v%(2**(32 if t==0x7f else 64)) for t,_,v in module.globals]
    def invoke(self,index,args,depth):
        m=self.module
        if index<len(m.imports):return self.host.call(m.imports[index][0],args)
        if depth>self.depth_limit:raise Trap('TRAP_CALL_DEPTH')
        locals_types,nodes=m.code[index-len(m.imports)]
        locals_=list(args)+[0]*len(locals_types);stack=[]
        try:self.seq(nodes,stack,locals_,depth)
        except Return:pass
        except Jump as j:
            if j.depth!=0:raise HostFault('RPR_INTERNAL_ERROR: escaped branch')
        return None
    def block(self,node,stack,locals_,depth):
        op=node['op'];height=len(stack)
        selected=node['body']
        if op==4:selected=selected if stack.pop()!=0 else node.get('else',[]);height=len(stack)
        while True:
            try:self.seq(selected,stack,locals_,depth);return
            except Jump as j:
                stack[height:]=[]
                if j.depth:
                    j.depth-=1;raise
                if op!=3:return
                # Branch to a loop re-enters the loop instruction, charged again.
                self.host.charge(1)
    def seq(self,nodes,stack,locals_,depth):
        for node in nodes:
            op=node['op'];a=node['args'];h=self.host;m=self.module
            # Imported calls use exactly the ABI cost, not an extra call cost.
            if op==0x10 and a[0]<len(m.imports):
                ps,rs=m.signature(a[0]);args=[stack.pop() for _ in ps][::-1]
                result=self.invoke(a[0],args,depth)
                if rs:stack.append(result)
                continue
            h.charge(4 if op==0x10 else 2 if op in MEM else 1)
            if op==0:raise Trap('TRAP_UNREACHABLE')
            if op==1:continue
            if op in (2,3,4):self.block(node,stack,locals_,depth)
            elif op==0x0c:raise Jump(a[0])
            elif op==0x0d:
                if stack.pop()!=0:raise Jump(a[0])
            elif op==0x0f:raise Return()
            elif op==0x10:
                ps,rs=m.signature(a[0]);args=[stack.pop() for _ in ps][::-1]
                result=self.invoke(a[0],args,depth+1)
                if rs:stack.append(result)
            elif op==0x20:stack.append(locals_[a[0]])
            elif op==0x21:locals_[a[0]]=stack.pop()
            elif op==0x22:locals_[a[0]]=stack[-1]
            elif op==0x23:stack.append(self.globals[a[0]])
            elif op==0x24:self.globals[a[0]]=stack.pop()
            elif op in MEM:
                typ,width,store=MEM[op];val=stack.pop() if store else None;address=stack.pop()+a[1]
                if address+width>len(h.memory):raise Trap('TRAP_MEMORY_OOB')
                if store:h.memory[address:address+width]=(val%(2**(8*width))).to_bytes(width,'little')
                else:stack.append(int.from_bytes(h.memory[address:address+width],'little'))
            elif op in (0x41,0x42):stack.append(a[0]%(2**(32 if op==0x41 else 64)))
            elif op==0x1a:stack.pop()
            elif op==0x1b:
                cond=stack.pop();right=stack.pop();left=stack.pop();stack.append(left if cond else right)
            elif op in (0x45,0x50):stack.append(int(stack.pop()==0))
            elif op in (0x46,0x47,0x51,0x52,0x6a,0x6b,0x7c,0x7d):
                right=stack.pop();left=stack.pop()
                if op in (0x46,0x51):stack.append(int(left==right))
                elif op in (0x47,0x52):stack.append(int(left!=right))
                else:stack.append((left+right if op in (0x6a,0x7c) else left-right)%(2**(32 if op in (0x6a,0x6b) else 64)))
            elif op==0xa7:stack.append(stack.pop()&0xffffffff)
            elif op==0xad:stack.append(stack.pop()&0xffffffff)
            else:raise HostFault('RPR_INTERNAL_ERROR: instruction')
    def run(self):
        try:
            self.host.charge(self.instantiation_cost);self.invoke(self.module.run,[],1)
            result={'outcome':'OK','gas_used':self.host.gas_used,'output':bytes(self.host.output)}
        except Trap as trap:
            result={'outcome':trap.code,'gas_used':self.host.gas_used}
            if trap.code=='ABORT':result['abort_code']=trap.abort_code
        except (MemoryError,RecursionError) as exc:raise HostFault('HOST_RESOURCE_EXHAUSTED: Python memory/call stack') from exc
        encoded=cbor(result);tag=b'ACLt/RIR-0/ExecutionOutcome/1'
        view={**result,'outcome_digest':hashlib.sha256(bytes([len(tag)])+tag+encoded).hexdigest()}
        if 'output' in view:view['output_hex']=view.pop('output').hex()
        return view


def load_candidate(blob,inputs,**limits):
    if 'input_arity' in limits:raise Reject('input binding cannot be overridden')
    return Runner(decode_artifact(blob),inputs,input_arity=1,**limits)
