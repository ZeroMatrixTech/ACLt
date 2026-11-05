# SPDX-License-Identifier: Apache-2.0
"""Python oracle for the restricted independent stats-core entry, not full RIR.

Uses the existing Python grammar/type validator and interpreter. Rust does not
import or invoke this file. The complete ADR-0006 grammar/priority suite is open.
"""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import hashlib
from tools.verification_profile import codec as c
from wasm import Module,Reject,cbor
from runtime import Runner,HostFault

ENC='RIR_REJECT_ENCODING';UNS='RIR_REJECT_UNSUPPORTED';INV='RIR_REJECT_INVALID';LIM='RIR_REJECT_LIMITS'
class CoreReject(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)
class GrammarModule(Module):
    def validate_function(self,i):pass

def classified(error):
    message=str(error)
    if any(x in message for x in ('truncated','LEB','UTF8','section order','block end','function end','trailing')):return ENC
    if 'outside stats slice:' in message:
        op=int(message.rsplit(' ',1)[1],16)
        return UNS if op in [0x0e,0x11,0x3f,0x40,0x43,0x44] or 0x28<=op<=0xbf else ENC
    if any(x in message for x in ('cap','limit','two-page','nesting')):return LIM
    if any(x in message for x in ('underflow','operand type','leftover','index','branch depth','alignment','immutable global')):return INV
    return UNS

def validate(raw,limits):
    try:v=c.decode(raw);c.need(c.encode(v)==raw)
    except c.CodecError as e:raise CoreReject(ENC) from e
    try:
        c.fields(v,['schema_version','encoding_profile_id','rir_version','entry','input_arity','body'])
        c.need(type(v['schema_version']) is int and v['schema_version']==1 and v['encoding_profile_id']=='acl.enc.rir-0@1' and v['rir_version']==[0,1,0] and all(type(n) is int for n in v['rir_version']) and v['entry']=='run' and type(v['body']) is bytes)
        c.uint(v['input_arity'])
    except (c.CodecError,TypeError) as e:raise CoreReject(UNS) from e
    try:
        grammar=GrammarModule(v['body'])
        if grammar.canonical()!=v['body']:raise CoreReject(ENC)
        module=Module(v['body'])
    except Reject as e:raise CoreReject(classified(e)) from e
    if v['input_arity']>2**32-1:raise CoreReject(LIM)
    if v['input_arity']!=1:raise CoreReject(INV)
    g,o,d,p=limits['gas_limit'],limits['output_limit'],limits['call_depth_limit'],limits['memory_pages_limit']
    if not (8192<=g<=50000000 and 0<=o<=4800000 and 1<=d<=64 and p==2):raise CoreReject(LIM)
    return module

def execute(raw,data,limits,expected=None,hook=''):
    try:module=validate(raw,limits)
    except CoreReject as e:return dict(status='REJECTED',code=e.code)
    digest=c.domain_hash('ACLt/RIR-0/Artifact/1',raw).hex()
    if expected is not None and expected!=digest:return dict(status='HOST_FAULT',code='RPR_REVALIDATION_MISMATCH')
    if hook=='test-memory-fault':return dict(status='HOST_FAULT',code='HOST_RESOURCE_EXHAUSTED')
    try:result=Runner(module,[data],**limits).run()
    except HostFault:return dict(status='HOST_FAULT',code='HOST_RESOURCE_OR_INTERNAL_FAILURE')
    given=result.pop('outcome_digest')
    value=dict(result)
    if 'output_hex' in value:value['output']=bytes.fromhex(value.pop('output_hex'))
    encoded=cbor(value);digest_out=c.domain_hash('ACLt/RIR-0/ExecutionOutcome/1',encoded).hex();assert given==digest_out
    return dict(status='TASK_OUTCOME',rir_digest=digest,canonical_outcome_hex=encoded.hex(),outcome_digest=digest_out,result=result)
