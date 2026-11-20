# SPDX-License-Identifier: Apache-2.0
"""FM-S1b candidate content DAG, audit fee table and pinned Receipt signature.

Pure checks and hypothetical quote only. No terminal resolver, authorized balance,
nonce consumption, entitlement creation or ledger writes exist in this module.
"""
import hashlib
import itertools
import json
from tools.formal_migration import foundation as f
from tools.verification_profile import codec as c
BASE=f.BASE
SCOPE=dict(requester_ref='digest',nonce='digest',created_at='int',expires_at='int')
REF=dict(kind='ref-kind',version='semver',digest='digest')
KINDS=('LOGICAL','FUNDING','SETTLEMENT','RECEIPT','RIR','RUNTIME','PROVENANCE','EQUIVALENCE','EXPOSURE','AVAILABILITY','DEPLOYMENT_TEST','AUDIT_CONTRACT')
COMPONENTS=('RIR','RUNTIME','PROVENANCE','EQUIVALENCE','EXPOSURE','AVAILABILITY','DEPLOYMENT_TEST','AUDIT_CONTRACT')
PROCESS_TERMINALS=('UNRESOLVED','EXPIRED','FAILED','FUNDING_EXHAUSTED')
PRESTART_TERMINALS=('REJECTED_AT_CREATE','FAILED_PLANNING','UNSUPPORTED')
TERMINALS=PROCESS_TERMINALS+PRESTART_TERMINALS
FULFILLMENT=('COMPLETE','MISSING','HOST_FAULT')
ENUMS={'ref-kind':KINDS,'component-kind':COMPONENTS,'terminal':TERMINALS,'fulfillment':FULFILLMENT}
ROW=dict(terminal='terminal',executor='fulfillment',auditor='fulfillment',storage='fulfillment',execution_fee='uint',verification_fee='uint',storage_fee='uint',refund_action='text')
LOGICAL=dict(BASE,object_type='text',object_version='semver',publisher_ref='digest',created_at='int',available_until='int',parents=[REF],content='bytes')
FUNDING=dict(BASE,scope=SCOPE,source='text',asset='text',execution_limit='uint',verification_limit='uint',storage_limit='uint',refund_reserve='uint',total_limit='uint')
SETTLEMENT=dict(BASE,scope=SCOPE,method='text',rows=[ROW])
COMPONENT=dict(kind='component-kind',version='semver',content='bytes')
EXECUTION=dict(fuel='uint',memory_bytes='uint',input_bytes_limit='uint',output_bytes_limit='uint',max_assignments='uint',max_attempts='uint',message_retries='uint',recovery_queries='uint',deadline='int',capabilities='text-set',architecture='text',network='text',sandbox='text')
RECEIPT=dict(BASE,scope=SCOPE,task_family='text',entry='text',output_type='text',success='text',merge='text',failure='text',method='text',input_refs=[REF],funding_ref=REF,settlement_ref=REF,component_refs=[REF],execution=EXECUTION)
BUNDLE=dict(receipt=RECEIPT,funding=FUNDING,settlement=SETTLEMENT,inputs=[LOGICAL],components=[COMPONENT])
QUOTE=dict(bundle=BUNDLE,terminal='terminal',executor='fulfillment',auditor='fulfillment',storage='fulfillment')
VERIFY=dict(bundle=BUNDLE,record=f.PRINCIPAL,signature='bytes',expected_receipt='digest',expected_requester='digest',now='int')
SCHEMAS={'fm2-logical':LOGICAL,'fm2-funding':FUNDING,'fm2-settlement':SETTLEMENT,'fm2-component':COMPONENT,'fm2-receipt':RECEIPT,'fm2-bundle':BUNDLE,'fm2-quote':QUOTE,'fm2-verify':VERIFY}
TAGS={k:'ACLt/FM/S1b/'+k+'/1' for k in KINDS}
SIGN_TAG='ACLt/FM/S1b/ReceiptSignature/1'
U64=2**64-1

def project(v,s,reverse=False):
    if isinstance(s,dict):
        c.fields(v,s)
        return {k:project(v[k],t,reverse) for k,t in s.items()}
    if isinstance(s,list):
        c.need(type(v) is list and len(v)<=111,'array limit')
        return [project(x,s[0],reverse) for x in v]
    if s in ENUMS:
        c.need(type(v) is str and v in ENUMS[s],'unknown ENUM')
        return v
    return f.project(v,s,reverse)

def common(v):f.common(v)
def scope(v):c.need(0 <= v['created_at'] < v['expires_at'],'scope interval')
def reference(kind,digest):return dict(kind=kind,version=[1,0,0],digest=digest)
def digest(kind,v):return c.domain_hash(TAGS[kind],c.encode(v))
def ref(kind,v):return reference(kind,digest(kind,v))
def check_ref(v,kind):c.need(v['kind']==kind and v['version']==[1,0,0],'reference kind/version')

def logical(v):
    common(v)
    c.need(v['object_type']=='FM_STATS_I32_VECTOR' and v['object_version']==[1,0,0],'logical schema')
    c.need(v['parents']==[],'initial immutable input has no parents')
    c.need(0<=v['created_at']<v['available_until'],'availability interval')
    a=c.decode(v['content']);c.need(type(a) is list and bool(a),'input vector size')
    c.need(all(type(n) is int and -2**31<=n<2**31 for n in a),'i32 input')

def funding(v):
    common(v);scope(v['scope'])
    c.need(v['source']=='REQUESTER_PREFUNDED' and v['asset']=='FM_TEST_UNIT','funding source/asset')
    limits=[v[k] for k in ('execution_limit','verification_limit','storage_limit','refund_reserve')]
    c.need(v['execution_limit']>0 and v['verification_limit']>0,'minimum process funding')
    c.need(sum(limits)<=U64 and sum(limits)==v['total_limit'],'funding sum/overflow')

def key(row):return tuple(row[k] for k in ('terminal','executor','auditor','storage'))
def matrix_keys():
    keys=list(itertools.product(PROCESS_TERMINALS,FULFILLMENT,FULFILLMENT,FULFILLMENT))
    keys += [(t,'MISSING','MISSING','MISSING') for t in PRESTART_TERMINALS]
    return sorted(keys,key=lambda x:c.encode(list(x)))
def settlement(v):
    common(v);scope(v['scope']);c.need(v['method']=='REEXEC_AUDIT_ONLY','audit-only method')
    c.need([key(r) for r in v['rows']]==matrix_keys(),'missing/duplicate/unordered matrix cell')
    for r in v['rows']:
        c.need(r['refund_action']=='RETURN_REMAINDER','refund rule')
        for status,fee in [('executor','execution_fee'),('auditor','verification_fee'),('storage','storage_fee')]:
            c.need(r[status]=='COMPLETE' or r[fee]==0,'missing/host fault is not fulfillment')
        c.need(sum(r[k] for k in ('execution_fee','verification_fee','storage_fee'))<=U64,'fee sum overflow')

def component(v):
    c.need(v['version']==[1,0,0] and len(v['content'])>0,'component version/bytes')
    # Component bytes are pinned imports; RIR/runtime conformance is not inferred.

def receipt(v):
    common(v);scope(v['scope'])
    for k,x in dict(task_family='stats-int-v1',entry='stats_int_v1',output_type='FM_STATS_INT_RESULT',success='EXACT_TASK_OUTCOME',merge='SINGLE_ASSIGNMENT',failure='FROZEN_AUDIT_MAPPING',method='REEXEC_AUDIT_ONLY').items():c.need(v[k]==x,'unsupported receipt semantics')
    c.need(len(v['input_refs'])==1,'one immutable input')
    check_ref(v['input_refs'][0],'LOGICAL');check_ref(v['funding_ref'],'FUNDING');check_ref(v['settlement_ref'],'SETTLEMENT')
    c.need([x['kind'] for x in v['component_refs']]==list(COMPONENTS),'component imports/order')
    for x in v['component_refs']:check_ref(x,x['kind'])
    e=v['execution']
    c.need(0<e['fuel'] and 0<e['memory_bytes'] and 0<e['input_bytes_limit'] and 0<e['output_bytes_limit'],'resource limits')
    c.need(e['max_assignments']==2 and e['max_attempts']==1 and 1<=e['message_retries']<=16 and 1<=e['recovery_queries']<=32,'finite execution/recovery')
    c.need(v['scope']['created_at']<e['deadline']<=v['scope']['expires_at'],'receipt deadline')
    c.need(e['capabilities']==[] and e['architecture']=='wasm32' and e['network']=='DENY' and e['sandbox']=='REQUIRED','environment/effects')

def validate(kind,v):
    project(v,SCHEMAS[kind])
    {'fm2-logical':logical,'fm2-funding':funding,'fm2-settlement':settlement,'fm2-component':component,'fm2-receipt':receipt}.get(kind,lambda _:None)(v)

def bundle(v):
    validate('fm2-bundle',v)
    r=v['receipt'];validate('fm2-receipt',r)
    for name,kind in [('funding','FUNDING'),('settlement','SETTLEMENT')]:
        obj=v[name];validate('fm2-'+name,obj)
        c.need(all(obj[k]==r[k] for k in BASE) and obj['scope']==r['scope'],'foreign policy/scope')
        c.need(c.reference_identity(r[name+'_ref'])==c.reference_identity(ref(kind,obj)),'stale policy reference')
    c.need(len(v['inputs'])==1 and len(v['components'])==len(COMPONENTS),'unavailable/extra object')
    obj=v['inputs'][0];validate('fm2-logical',obj)
    c.need(all(obj[k]==r[k] for k in BASE) and obj['publisher_ref']==r['scope']['requester_ref'],'input owner/context')
    c.need(obj['created_at']<=r['scope']['created_at'] and obj['available_until']>=r['execution']['deadline'],'input unavailable in interval')
    c.need(len(obj['content'])<=r['execution']['input_bytes_limit'] and c.reference_identity(r['input_refs'][0])==c.reference_identity(ref('LOGICAL',obj)),'input content/reference')
    c.need([x['kind'] for x in v['components']]==list(COMPONENTS),'unavailable/extra component kind')
    for obj,rr in zip(v['components'],r['component_refs']):
        validate('fm2-component',obj);c.need(c.reference_identity(rr)==c.reference_identity(ref(obj['kind'],obj)),'stale component reference')
    limits=v['funding']
    for row in v['settlement']['rows']:
        for fee,limit in [('execution_fee','execution_limit'),('verification_fee','verification_limit'),('storage_fee','storage_limit')]:c.need(row[fee]<=limits[limit],'bucket over-budget')
        paid=sum(row[k] for k in ('execution_fee','verification_fee','storage_fee'))
        c.need(paid+limits['refund_reserve']<=limits['total_limit'],'refund reserve over-budget')
    # All reference edges: Receipt -> immutable leaves. No content has ReceiptID.
    return digest('RECEIPT',r)

def quote(v):
    project(v,QUOTE)
    rid=bundle(v['bundle']);row=next((r for r in v['bundle']['settlement']['rows'] if key(r)==key(v)),None)
    c.need(row is not None,'prestart terminal cannot claim fulfillment')
    amounts={k:row[k] for k in ('execution_fee','verification_fee','storage_fee')}
    return dict(receipt_digest_hex=rid.hex(),amounts={k:str(x) for k,x in amounts.items()},refund=str(v['bundle']['funding']['total_limit']-sum(amounts.values())),scope='HYPOTHETICAL_ONLY_NO_ENTITLEMENT')

def signing_input(v):
    rid=bundle(v);tag=SIGN_TAG.encode();return bytes([len(tag)])+tag+c.encode(v['receipt'])

def verify(v):
    project(v,VERIFY)
    rid=bundle(v['bundle']);r=v['bundle']['receipt'];record=v['record'];pin=f.principal_digest(record)
    c.need(c.digest_consistency(pin==v['expected_requester']==r['scope']['requester_ref']),'requester pin')
    c.need(c.digest_consistency(rid==v['expected_receipt']),'caller receipt commitment')
    c.need(record['role']=='REQUESTER' and all(record[k]==r[k] for k in ('protocol_version','network_id','deployment_id')),'requester role/context')
    c.need(record['valid_from']<=r['scope']['created_at']<=v['now']<r['execution']['deadline']<=record['valid_until'],'signature validity')
    c.need(len(v['signature'])==256,'signature width')
    f.crypto_verify(record['public_key_der'],signing_input(v['bundle']),v['signature'])
    return dict(valid=True,receipt_digest_hex=rid.hex(),requester_digest_hex=pin.hex())

def inspect(kind,raw):
    c.need(kind in SCHEMAS,'unknown S1b kind');v=c.decode(raw);validate(kind,v)
    if kind=='fm2-quote':return quote(v)
    if kind=='fm2-verify':return verify(v)
    result=dict(cbor_hex=c.encode(v).hex(),schema_view=project(v,SCHEMAS[kind]))
    if kind=='fm2-bundle':
        result.update(digest_hex=bundle(v).hex(),signing_input_hex=signing_input(v).hex())
    else:
        k={'fm2-logical':'LOGICAL','fm2-funding':'FUNDING','fm2-settlement':'SETTLEMENT','fm2-receipt':'RECEIPT'}.get(kind,v.get('kind'))
        result['digest_hex']=digest(k,v).hex()
    return result

def from_view_json(kind,source):
    c.need(kind in SCHEMAS and type(source) is str,'kind/JSON type')
    def unique(pairs):
        d={}
        for k,v in pairs:c.need(k not in d,'duplicate JSON key');d[k]=v
        return d
    def reject(_):raise c.CodecError('non-JSON constant')
    try:
        source.encode()
        v=project(json.loads(source,object_pairs_hook=unique,parse_constant=reject),SCHEMAS[kind],True);raw=c.encode(v);inspect(kind,raw);return raw
    except (ValueError,RecursionError,UnicodeError) as exc:raise c.CodecError('invalid S1b Schema View') from exc
