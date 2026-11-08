#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent commitments, Claim/snapshot bindings and candidate admission input checks."""
import argparse,copy,hashlib,json,os,platform,runpy,socket,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verification_profile import codec as c,profile as p,registration as reg,references,registration_rules as common,creation,commitments as r
R5=runpy.run_path(str(ROOT/'scripts/check-method-matrices.py'))
R6=runpy.run_path(str(ROOT/'scripts/check-creation-bindings.py'))
R7=runpy.run_path(str(ROOT/'scripts/check-selection-assets.py'))
VECTOR=ROOT/'tests/verification_profile/codec/commitment-bindings-vectors.json'


def pin(v):return hashlib.sha256(c.encode(v)).digest()


def extend(base):
    aliases={'NativeValue'};visited=set()
    def walk(x):
        if isinstance(x,str) and x in r.TYPES and x not in visited:
            visited.add(x);walk(r.TYPES[x])
        if isinstance(x,dict):
            if 'import_' in x:aliases.add(x['import_'])
            for y in x.values():walk(y)
        elif isinstance(x,list):
            for y in x:walk(y)
    walk(r.EXTRA);walk(r.selection.EXTRA);walk(creation.EXTRA);existing={x['alias'] for x in base['schema_lock']['entries']}
    for alias in sorted(aliases-existing):
        identifier='acl.schema.'+r.ALIASES[alias]+'@1' if alias in r.ALIASES else reg.FIXED_IMPORTS.get(alias,'acl.schema.test-'+alias.lower()+'@1')
        if alias=='NativeValue':identifier='acl.schema.r8-native-value@1'
        raw=c.encode(dict(alias=alias,id=identifier,version=[1,0,0],representation='NATIVE_CBOR' if alias=='NativeValue' else 'OPAQUE_BSTR'))
        ref=dict(id=identifier,version=[1,0,0],digest=hashlib.sha256(raw).digest());base['schema_lock']['entries'].append(dict(alias=alias,ref=ref));base['schema_documents'].append(dict(ref=copy.deepcopy(ref),content=raw))
    base['schema_lock']['entries'].sort(key=lambda x:c.encode(x['alias']))


def wrap(base,value):
    reference=next(x['ref'] for x in base['schema_lock']['entries'] if x['alias']=='NativeValue');raw=c.encode(value)
    return dict(schema_ref=copy.deepcopy(reference),canonical_bytes=raw,object_digest=hashlib.sha256(raw).digest())


def fixture(operation='registration',method='DIRECT_VERIFIED'):
    base,_=R5['fixture'](method);extend(base);profile=base['profile'];registry=base['registry_snapshot'];ecr=copy.deepcopy(R5['audit_fixture']()[0]['registry_objects'][0]['object'])
    ecr['header']['id']='acl.ecr.r8-test';all_specific=set().union(*r.SPECIFIC.values())
    for identifier in sorted(all_specific):ecr['entries'].append(dict(exclusion_id=identifier,statement='Test copy of the frozen method exclusion identifier.',category='METHOD_SPECIFIC'))
    ecr['entries'].sort(key=lambda x:c.encode(x['exclusion_id']));ecr['header']['digest']=references.exclusion_registry_digest(ecr)
    profile['excluded_claims']=dict(registry_ref=r.identity(ecr),exclusion_ids=sorted(references.BASELINE|r.SPECIFIC[method],key=c.encode),digest=b'\0'*32);profile['excluded_claims']['digest']=references.excluded_digest(profile['excluded_claims'])
    h=lambda identifier,runtime=False:dict(schema_version=1,encoding_profile_id=c.ENCODING,id=identifier,**({} if runtime else dict(version=[1,0,0])),digest=b'\0'*32)
    template=None
    if method!='REEXEC_AUDIT_ONLY':
        static=r.static_values(profile);slots=[]
        for name,value in static.items():
            kind='VERSION' if name=='profile_version' else 'DIGEST' if name=='assumption_set_digest' else {'enum':['SOUND','SOUND_AND_COMPLETE']} if name=='soundness_class' else 'REF'
            slots.append(dict(slot=name,decl=dict(kind='STATIC',value_type=kind,source='PROFILE')))
        runtime={'DIRECT_VERIFIED':{'input_refs':'RECEIPT','output_ref':'EVIDENCE_CHAIN'},'PROOF_VERIFIED':{'output_ref':'EVIDENCE_CHAIN','proof_ref':'EVIDENCE_CHAIN'},'REEXEC_BOUNDED':{'rpr_profile_version':'RECEIPT','rir_digest':'RECEIPT','input_refs':'RECEIPT','result_digest':'EVIDENCE_CHAIN','snapshot_digest':'SNAPSHOT'}}[method]
        for name,source in runtime.items():slots.append(dict(slot=name,decl=dict(kind='RUNTIME',value_type='VERSION' if name=='rpr_profile_version' else 'DIGEST' if name.endswith('digest') else 'OBJECT_REF',source=source)))
        slots.sort(key=lambda x:c.encode(x['slot']))
        template=dict(header=h(r.TEMPLATES[method]),normative_text='Test-only conditional claim under frozen references.',slot_decls=slots,translations=[dict(lang='zh',text='非规范测试翻译')]);template['header']['digest']=r.object_digest(template,'ClaimTemplate')
        profile['verified_claim_spec']=dict(claim_spec_id='acl.cs.test',claim_template_ref=r.identity(template),binding_schema=copy.deepcopy(slots),static_bindings=sorted([dict(slot=k,value=wrap(base,v)) for k,v in static.items()],key=lambda x:c.encode(x['slot'])),binding_function_ref='acl.bind.r8-test@1.0.0')
    profile['profile_digest']=p.profile_digest(profile)
    registry['entries']=[x for x in registry['entries'] if x['object_kind'] not in ('EXCLUDED_CLAIMS_REGISTRY','CLAIM_TEMPLATE') and x['id']!=profile['profile_id']]
    registry['entries'].extend([dict(object_kind='EXCLUDED_CLAIMS_REGISTRY',**r.identity(ecr),state='REGISTERED'),dict(object_kind='VERIFICATION_PROFILE',**r.selection.profile_ref(profile),state='REGISTERED')])
    if template:registry['entries'].append(dict(object_kind='CLAIM_TEMPLATE',**r.identity(template),state='REGISTERED'))
    registry['entries'].sort(key=lambda x:c.encode([x['object_kind'],x['id'],x['version']]));registry['header']['digest']=reg.registry_digest(registry)
    external_ref=dict(id='acl.component.r8-test',version=[1,0,0],digest=b'e'*32)
    assurance=dict(header=h('acl.map.r8-test'),network_id=b'R8_TEST_ONLY',issuer_ref=b'test-maintenance',validity_window=[0,1000],profile_capabilities=[dict(profile_ref=r.selection.profile_ref(profile),disposition='DISABLED',required_assumption_ids=[],max_receipt_exposure_ref=external_ref)],allowed_rpr_refs=[external_ref],allowed_validator_refs=[external_ref],log_backend_ref=external_ref,execution_capability_contract_ref=external_ref,assumption_verdict_reducer_ref=r.default_reducer_ref(),correlation_policy_ref=external_ref,loss_budget_ref=external_ref,required_conformance_refs=[external_ref],outside_network_disposition='DISABLED',human_summary=b'test boundary; not enabled')
    assurance['header']['digest']=r.object_digest(assurance,'MainnetAssuranceProfile')
    rows=[dict(assumption_id=x['assumption_id'],evidence_ref=x['evidence_ref'],evidence_version=x['evidence_version'],cause_set=[],effective_verdict='VALID') for x in profile['assumption_references'] if x['role'] in ('SAFETY_CRITICAL','LIVENESS')];rows.sort(key=lambda x:c.encode(x['assumption_id']))
    snapshot=dict(header=h('acl.ass.'+'0'*26,True),receipt_id=b'r'*32,evaluation_instant=10,reducer_ref=r.default_reducer_ref(),assumption_states=rows);snapshot['header']['digest']=r.object_digest(snapshot,'AssumptionStateSnapshot')
    result=dict(tag='COMPLETE',snapshot=snapshot)
    value=dict(operation=operation,payload={},schema_lock=base['schema_lock'],schema_documents=base['schema_documents'])
    if operation=='registration':
        value['payload']=dict(profile=profile,registry_snapshot=registry,exclusion_registry=ecr)
        if template:value['payload']['template']=template
    elif operation=='state':value['payload']=dict(profile=profile,result=result,assumption_state_digest=r.state_digest(snapshot))
    elif operation=='claim-guard':
        value['payload']=dict(profile=profile,registry_snapshot=registry,receipt_id=b'r'*32,terminal_state='TRUSTED' if template else 'UNRESOLVED',assumption_result=result)
        if template:
            bindings=[dict(slot_id=x['slot'],value=copy.deepcopy(x['value'])) for x in profile['verified_claim_spec']['static_bindings']]
            for row in template['slot_decls']:
                if row['decl']['kind']=='RUNTIME':bindings.append(dict(slot_id=row['slot'],value=wrap(base,[1,0,0] if row['slot']=='rpr_profile_version' else [b'input'] if row['slot']=='input_refs' else b'o'*32)))
            bindings.sort(key=lambda x:c.encode(x['slot_id']))
            binding=dict(claim_spec_id='acl.cs.test',claim_template_ref=r.identity(template),profile_ref=r.selection.profile_ref(profile),network_id=assurance['network_id'],assurance_profile_ref=r.identity(assurance),assurance_boundary_digest=assurance['header']['digest'],verification_method=method,concrete_bindings=bindings,rendered_claim_digest=r.rendered_digest(r.identity(template),bindings),excluded_claims_registry_ref=profile['excluded_claims']['registry_ref'],excluded_claims_ids=profile['excluded_claims']['exclusion_ids'],excluded_claims_digest=profile['excluded_claims']['digest'],assumption_set_digest=common.assumption_set_digest(profile['assumption_references']),assumption_state_digest=r.state_digest(snapshot),assumption_state_snapshot_ref={k:snapshot['header'][k] for k in ('id','digest')})
            if method=='REEXEC_BOUNDED':binding.update(algorithm_id=profile['method_parameters']['algorithm_id'],snapshot_digest=b's'*32)
            value['payload'].update(template=template,claim_binding=binding,assurance_profile=assurance)
    elif operation=='template-digest':value['payload']=dict(object=template)
    elif operation=='assurance-digest':value['payload']=dict(object=assurance)
    elif operation=='rendered-digest':
        guard,_=fixture('claim-guard',method);binding=guard['payload']['claim_binding'];value['payload']=dict(template_ref=binding['claim_template_ref'],bindings=binding['concrete_bindings'],digest=binding['rendered_claim_digest'])
    elif operation=='decision-input-digest':
        input_=dict(receipt_binding=dict(receipt_id=b'r'*32,profile_ref=r.selection.profile_ref(profile),network_id=assurance['network_id'],assurance_profile_ref=r.identity(assurance)),profile_ref=r.selection.profile_ref(profile),assurance_profile=assurance,method_evaluation=dict(evaluator_ref=external_ref,canonical_input=wrap(base,dict(evidence=[b'complete test payload'])),claimed_outcome=wrap(base,b'CONCORDANT'),claimed_aggregate=wrap(base,dict(exhausted=True))),assumption_evaluation=result,boundary_observation={},execution_observation=dict(tag='NOT_APPLICABLE'))
        value['payload']=dict(evaluation_input=input_,input_digest=c.domain_hash('ACLt/P0-1/DecisionEvaluationInput/1',c.encode(input_)))
    elif operation=='candidate-input':
        contract=dict(protocol_version=[1,0,0],rir_version=[1,0,0],rpr_version=[1,0,0],allowed_effects=[b'integer'],resource_bounds=b'resources')
        intent=dict(schema_version=1,encoding_profile_id=c.ENCODING,network_id=b'R8_TEST_ONLY',assurance_profile_ref=r.identity(assurance),requester_ref=b'requester',contract_tuple=c.encode(contract),program_ref=b'stats-int',input_refs=[b'B',b'A',b'B'],output_spec=b'output',profile_ref=r.selection.profile_ref(profile),degradation_authorized=False)
        value['payload']=dict(candidate=dict(schema_version='R8_CANDIDATE_1',encoding_profile_id=c.ENCODING,base_intent=intent,task_type='acl.tt.stats',environment_class=b'host',fault_domains=[b'physical-A'],geography=[b'local'],contract_tuple=contract,n_max=5))
    else:raise ValueError(operation)
    return value,pin(value['schema_lock'])


def reseal(v):
    q=v['payload']
    for key,kind in [('object','ClaimTemplate' if v['operation']=='template-digest' else 'MainnetAssuranceProfile'),('template','ClaimTemplate'),('assurance_profile','MainnetAssuranceProfile')]:
        if key in q and isinstance(q[key],dict) and 'header' in q[key] and v['operation'] in ('template-digest','assurance-digest','registration','claim-guard'):
            q[key]['header']['digest']=r.object_digest(q[key],kind)
    result=q.get('result',q.get('assumption_result',{}))
    if result.get('tag')=='COMPLETE':result['snapshot']['header']['digest']=r.object_digest(result['snapshot'],'AssumptionStateSnapshot')
    if 'profile' in q:q['profile']['profile_digest']=p.profile_digest(q['profile'])
    return v


def rebind_registration(value):
    q=value['payload'];profile=q['profile']
    if 'template' in q:
        template=q['template'];template['header']['digest']=r.object_digest(template,'ClaimTemplate')
        profile['verified_claim_spec']['claim_template_ref']=r.identity(template)
        for row in q['registry_snapshot']['entries']:
            if row['object_kind']=='CLAIM_TEMPLATE':row.update(r.identity(template))
    profile['profile_digest']=p.profile_digest(profile)
    for row in q['registry_snapshot']['entries']:
        if row['object_kind']=='VERIFICATION_PROFILE' and row['id']==profile['profile_id']:row.update(r.selection.profile_ref(profile))
    q['registry_snapshot']['header']['digest']=reg.registry_digest(q['registry_snapshot'])
    return value


def vectors():
    rows=[]
    def add(name,v,valid=True,*,seal=False,lock=None):
        if seal:reseal(v)
        raw=c.encode(v);lock=lock or pin(v['schema_lock']);row=dict(id=name,mode='commitments',cbor_hex=raw.hex(),lock_pin=lock.hex(),valid=valid)
        if valid:row['expected']=r.inspect(raw,lock)
        rows.append(row)
    operations=('registration','claim-guard','state','template-digest','assurance-digest','rendered-digest','decision-input-digest','candidate-input')
    for op in operations:
        base,lock=fixture(op);add('valid-'+op,copy.deepcopy(base))
        add('wrong-pin-'+op,copy.deepcopy(base),False,lock=b'x'*32)
        for field in base['payload']:
            v=copy.deepcopy(base);v['payload'].pop(field);add('missing-'+op+'-'+field,v,False)
        for payload in ([],True,'bad'):
            v=copy.deepcopy(base);v['payload']=payload;add('malformed-'+op+'-'+str(payload),v,False)
        v=copy.deepcopy(base);v['payload']['unexpected']=1;add('unknown-'+op,v,False)
    for method in p.METHODS:
        for op in ('registration','claim-guard','state'):
            base,_=fixture(op,method);add('method-'+op+'-'+method,copy.deepcopy(base))
    for method in p.METHODS[:-1]:
        base,_=fixture('registration',method)
        for missing in sorted(r.SPECIFIC[method]):
            v=copy.deepcopy(base);profile=v['payload']['profile'];profile['excluded_claims']['exclusion_ids'].remove(missing);profile['excluded_claims']['digest']=references.excluded_digest(profile['excluded_claims']);add('missing-specific-'+method+'-'+missing,v,False,seal=True)
        v=copy.deepcopy(base);v['payload']['profile']['verified_claim_spec']['claim_template_ref']['id']='acl.ct.wrong';add('method-template-'+method,v,False,seal=True)
        for state in ('DEPRECATED','REVOKED'):
            v=copy.deepcopy(base);registry=v['payload']['registry_snapshot'];next(x for x in registry['entries'] if x['object_kind']=='CLAIM_TEMPLATE')['state']=state;registry['header']['digest']=reg.registry_digest(registry);add('template-state-'+method+'-'+state,v,False)
        for label,edit in [('missing-schema-slot',lambda x:x['binding_schema'].pop()),('runtime-static',lambda x:x['static_bindings'].append(dict(slot='output_ref',value=copy.deepcopy(x['static_bindings'][0]['value'])))),('missing-static',lambda x:x['static_bindings'].pop()),('duplicate-schema',lambda x:x['binding_schema'].append(copy.deepcopy(x['binding_schema'][0]))),('wrong-static',lambda x:x['static_bindings'][0].update(value=wrap(base,b'wrong')))]:
            v=copy.deepcopy(base);edit(v['payload']['profile']['verified_claim_spec']);add('spec-'+method+'-'+label,v,False,seal=True)
    base,_=fixture('registration','REEXEC_BOUNDED')
    v=copy.deepcopy(base)
    for container in (v['payload']['template']['slot_decls'],v['payload']['profile']['verified_claim_spec']['binding_schema']):
        next(x for x in container if x['slot']=='rpr_profile_version')['decl'].update(kind='STATIC',source='PROFILE')
    rebind_registration(v);add('range-cannot-be-static',v,False)
    for op in ('template-digest','assurance-digest'):
        base,_=fixture(op);kind='ClaimTemplate' if op=='template-digest' else 'MainnetAssuranceProfile'
        for field in r.EXTRA['TemplateR8' if op=='template-digest' else 'AssuranceR8']['fields']:
            v=copy.deepcopy(base);v['payload']['object'].pop(field);add('missing-object-'+op+'-'+field,v,False)
        v=copy.deepcopy(base);v['payload']['object']['header']['digest']=b'x'*32;add('bad-object-digest-'+op,v,False)
        v=copy.deepcopy(base);v['payload']['object']['header'].update(id='acl.ct.other' if op=='template-digest' else 'acl.map.other',version=[9,2,3]);add('identity-excluded-'+op,v)
        v=copy.deepcopy(base);v['payload']['object']['translations' if op=='template-digest' else 'human_summary']=[dict(lang='en',text='changed')] if op=='template-digest' else b'changed';add('advisory-excluded-'+op,v)
        for field in ('id','version','digest'):
            v=copy.deepcopy(base);v['payload']['object'][field]=v['payload']['object']['header'][field];add('duplicate-identity-'+op+'-'+field,v,False)
    base,_=fixture('claim-guard')
    binding=base['payload']['claim_binding']
    for field in binding:
        v=copy.deepcopy(base);v['payload']['claim_binding'].pop(field);add('missing-claim-binding-'+field,v,False)
    for label,edit in [('claim-missing',lambda q:q.pop('claim_binding')),('wrong-receipt',lambda q:q.update(receipt_id=b'x'*32)),('snapshot-ref',lambda q:q['claim_binding']['assumption_state_snapshot_ref'].update(digest=b'x'*32)),('snapshot-version',lambda q:q['claim_binding']['assumption_state_snapshot_ref'].update(version=[1,0,0])),('rendered-digest',lambda q:q['claim_binding'].update(rendered_claim_digest=b'x'*32)),('state-digest',lambda q:q['claim_binding'].update(assumption_state_digest=b'x'*32)),('profile-ref',lambda q:q['claim_binding']['profile_ref'].update(digest=b'x'*32)),('network',lambda q:q['claim_binding'].update(network_id=b'other')),('concrete-missing',lambda q:q['claim_binding']['concrete_bindings'].pop()),('concrete-static',lambda q:q['claim_binding']['concrete_bindings'][0].update(value=wrap(base,b'changed')))]:
        v=copy.deepcopy(base);edit(v['payload']);add('claim-'+label,v,False)
    base,_=fixture('state','REEXEC_BOUNDED')
    for label,edit in [('missing-row',lambda q:q['result']['snapshot']['assumption_states'].pop()),('duplicate-row',lambda q:q['result']['snapshot']['assumption_states'].append(copy.deepcopy(q['result']['snapshot']['assumption_states'][0]))),('unknown-verdict',lambda q:q['result']['snapshot']['assumption_states'][0].update(effective_verdict='UNKNOWN')),('evidence-version',lambda q:q['result']['snapshot']['assumption_states'][0].update(evidence_version=[2,0,0])),('wrong-reducer',lambda q:q['result']['snapshot']['reducer_ref'].update(digest=b'x'*32)),('state-digest',lambda q:q.update(assumption_state_digest=b'x'*32))]:
        v=copy.deepcopy(base);edit(v['payload']);add('state-'+label,v,False,seal=True)
    for mask in range(8):
        v=copy.deepcopy(base);snapshot=v['payload']['result']['snapshot'];codes=[x for n,x in enumerate(r.CAUSE_ORDER) if mask&(1<<n)];row=snapshot['assumption_states'][0];row['cause_set']=sorted([dict(cause_code=x,evidence_ref=b'cause',observed_event_ref=x.encode()) for x in codes],key=lambda x:c.encode(x['cause_code']));row['effective_verdict']=next((x for x in r.CAUSE_ORDER if x in codes),'VALID');snapshot['header']['digest']=r.object_digest(snapshot,'AssumptionStateSnapshot');v['payload']['assumption_state_digest']=r.state_digest(snapshot);add('cause-subset-'+str(mask),v)
        if mask:
            bad=copy.deepcopy(v);bad['payload']['result']['snapshot']['assumption_states'][0]['effective_verdict']='VALID';add('forged-verdict-'+str(mask),bad,False,seal=True)
    for failure in ('EVIDENCE_UNAVAILABLE','EVIDENCE_MALFORMED','REGISTRY_UNAVAILABLE','VERDICT_UNDETERMINED'):
        v=copy.deepcopy(base);v['payload'].pop('assumption_state_digest');v['payload']['result']=dict(tag='INVALIDATING',failure=dict(assumption_id='ACL-ASM-0002',failure_class=failure,observed_at=10));add('invalidating-'+failure,v)
        bad=copy.deepcopy(v);bad['payload']['result']['snapshot']=base['payload']['result']['snapshot'];add('invalidating-with-snapshot-'+failure,bad,False)
    base,_=fixture('claim-guard')
    for terminal in ('UNRESOLVED','FAILED','EXPIRED','FUNDING_EXHAUSTED'):
        v=copy.deepcopy(base);q=v['payload'];q['terminal_state']=terminal;q.pop('claim_binding');q.pop('template');q.pop('assurance_profile');q['assumption_result']=dict(tag='INVALIDATING',failure=dict(assumption_id='ACL-ASM-0002',failure_class='EVIDENCE_UNAVAILABLE',observed_at=10));add('constructible-no-snapshot-'+terminal,v)
    base,_=fixture('decision-input-digest')
    for field in base['payload']['evaluation_input']:
        v=copy.deepcopy(base);v['payload']['evaluation_input'].pop(field);add('missing-decision-input-'+field,v,False)
        v=copy.deepcopy(base);v['payload']['evaluation_input'][field]=b'changed';add('tampered-decision-input-'+field,v,False)
    v=copy.deepcopy(base);v['payload']['evaluation_input']['method_evaluation']['canonical_input']=b'reference-only';v['payload']['input_digest']=c.domain_hash('ACLt/P0-1/DecisionEvaluationInput/1',c.encode(v['payload']['evaluation_input']));add('input-reference-only-even-rehashed',v,False)
    base,_=fixture('candidate-input')
    for field in base['payload']['candidate']:
        v=copy.deepcopy(base);v['payload']['candidate'].pop(field);add('missing-candidate-'+field,v,False)
    for field in ('fault_domains','geography'):
        v=copy.deepcopy(base);v['payload']['candidate'][field]=[];add('empty-candidate-'+field,v,False)
    for label,edit in [('contract-drift',lambda x:x['contract_tuple'].update(rpr_version=[2,0,0])),('n-max-bool',lambda x:x.update(n_max=True)),('n-max-negative',lambda x:x.update(n_max=-1)),('scope-override',lambda x:x.update(declared_scope={})),('version',lambda x:x.update(schema_version='OFFICIAL_V2'))]:
        v=copy.deepcopy(base);edit(v['payload']['candidate']);add('candidate-'+label,v,False)
    for field in ('n_max','task_type','environment_class','fault_domains','geography'):
        v=copy.deepcopy(base);value=v['payload']['candidate'][field];v['payload']['candidate'][field]=value+1 if type(value) is int else 'acl.tt.other' if field=='task_type' else [b'other'] if isinstance(value,list) else b'other';add('candidate-committed-'+field,v)
    base,_=fixture('claim-guard')
    v=copy.deepcopy(base);q=v['payload'];s=q['assumption_result']['snapshot'];s['assumption_states'][0]['cause_set']=[dict(cause_code='REVOKED',evidence_ref=b'e',observed_event_ref=b'event')];s['assumption_states'][0]['effective_verdict']='REVOKED';s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot');q['claim_binding']['assumption_state_digest']=r.state_digest(s);q['claim_binding']['assumption_state_snapshot_ref']={k:s['header'][k] for k in ('id','digest')};add('trusted-revoked-with-consistent-hashes',v,False)
    v=copy.deepcopy(base);q=v['payload'];q['assumption_result']=dict(tag='INVALIDATING',failure=dict(assumption_id='ACL-ASM-0002',failure_class='EVIDENCE_UNAVAILABLE',observed_at=10));add('trusted-invalidating-no-snapshot',v,False)
    v=copy.deepcopy(base);q=v['payload'];s=q['assumption_result']['snapshot'];s['receipt_id']=b'x'*32;s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot');q['claim_binding']['assumption_state_snapshot_ref']={k:s['header'][k] for k in ('id','digest')};add('foreign-receipt-snapshot-rehashed',v,False)
    v=copy.deepcopy(base);q=v['payload'];binding=q['claim_binding'];next(x for x in binding['concrete_bindings'] if x['slot_id']=='predicate_ref')['value']=wrap(v,'acl.pred.other@1.0.0');binding['rendered_claim_digest']=r.rendered_digest(binding['claim_template_ref'],binding['concrete_bindings']);add('static-concrete-forgery-rehashed',v,False)
    base,_=fixture('state');v=copy.deepcopy(base);v['payload']['profile']['documentation']=b'unchanged-advisory';v['payload']['profile']['assumption_references'][0]['statement_digest']=b'x'*32;add('state-profile-commitment-required',v,False)
    base,_=fixture('candidate-input');v=copy.deepcopy(base);candidate=v['payload']['candidate'];candidate['contract_tuple']['rpr_version']=[2,0,0];candidate['base_intent']['contract_tuple']=c.encode(candidate['contract_tuple']);add('candidate-new-contract-new-commitment',v)
    v,_=fixture('registration');next(x for x in v['payload']['template']['slot_decls'] if x['slot']=='soundness_class')['decl']['value_type']=True;next(x for x in v['payload']['profile']['verified_claim_spec']['binding_schema'] if x['slot']=='soundness_class')['decl']['value_type']=1;rebind_registration(v);add('native-declaration-bool-is-not-integer',v,False)
    # Generic wire assertions cover every versioned family and four runtime kinds.
    wire_objects={}
    for kind,operation in [('ClaimTemplate','template-digest'),('MainnetAssuranceProfile','assurance-digest')]:wire_objects[kind]=fixture(operation)[0]['payload']['object']
    v,_=fixture('state');wire_objects['AssumptionStateSnapshot']=v['payload']['result']['snapshot']
    c6,_,_=R6['fixture']();wire_objects['CreationValidationContext']=c6['envelope']['creation_context'];wire_objects['PhaseIValidationRecord']=c6['envelope']['phase_i_transcript']['output'];wire_objects['EventFrontierSnapshot']=c6['envelope']['bundle']['event_frontier_snapshot']
    for kind,operation,key in [('ProfileSelectionPolicy','policy','policy'),('ConformanceManifest','manifest','manifest'),('WeakeningEdge','edge','edge')]:wire_objects[kind]=R7['fixture'](operation)[0]['payload'][key]
    regbase,_=fixture();wire_objects.update(VerificationProfile=regbase['payload']['profile'],RegistrySnapshot=regbase['payload']['registry_snapshot'],ExcludedClaimsRegistry=regbase['payload']['exclusion_registry'])
    root=fixture()[0]
    for kind,object_ in wire_objects.items():
        v=copy.deepcopy(root);v.update(operation='wire',payload=dict(kind=kind,object=object_));add('wire-'+kind,v)
        bad=copy.deepcopy(v)
        if kind=='VerificationProfile':bad['payload']['object']['header']={}
        else:bad['payload']['object']['id']=object_['header']['id']
        add('wire-duplicate-'+kind,bad,False)
        if kind in r.RUNTIME:
            bad=copy.deepcopy(v);bad['payload']['object']['header']['version']=[1,0,0];add('wire-pseudo-version-'+kind,bad,False)
            ref={k:object_['header'][k] for k in ('id','digest')};v.update(operation='runtime-ref',payload=dict(kind=kind,ref=ref));add('runtime-ref-'+kind,copy.deepcopy(v))
            for label,change in [('version',dict(version=[1,0,0])),('foreign',dict(id='acl.cctx.'+'1'*26 if kind!='CreationValidationContext' else 'acl.ass.'+'1'*26))]:bad=copy.deepcopy(v);bad['payload']['ref'].update(change);add('runtime-ref-'+label+'-'+kind,bad,False)
    return rows


def run(binary,rows):
    request=''.join('commitments:'+x['lock_pin']+'\t'+x['cbor_hex']+'\n' for x in rows);result=subprocess.run([str(binary)],input=request,text=True,capture_output=True,check=True,timeout=180);outputs=[json.loads(x) for x in result.stdout.splitlines()]
    if len(outputs)!=len(rows):raise ValueError('response count')
    for row,rust in zip(rows,outputs,strict=True):
        try:python=r.inspect(bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']))
        except c.CodecError:
            if row['valid'] or 'error' not in rust:raise ValueError('negative disagreement '+row['id']+' '+str(rust))
        else:
            if not row['valid'] or python!=rust or python!=row['expected']:raise ValueError('positive disagreement '+row['id']+' '+str(rust))
    return outputs


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze-vectors',action='store_true');parser.add_argument('--report',type=Path);args=parser.parse_args()
    if args.freeze_vectors:
        data=vectors()
        with VECTOR.open('x') as f:json.dump(dict(scope='commitment/binding components; candidate sum/ENUM/admission interfaces; no Decision emission',vectors=data),f,indent=2);f.write('\n')
    rows=json.loads(VECTOR.read_text())['vectors']
    with tempfile.TemporaryDirectory(prefix='aclt-commitments-') as tmp:
        binary=Path(tmp)/'codec';subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings',str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True,timeout=120);outputs=run(binary,rows)
    names=set(json.loads((ROOT/'scripts/creation-source-files.json').read_text()))|{'scripts/check-commitment-bindings.py','scripts/check-creation-bindings.py','scripts/check-selection-assets.py','tools/verification_profile/commitments.py','tools/verification_profile/creation.py','tools/verification_profile/selection.py','tools/verification_profile/rust/creation_types.json','tools/verification_profile/rust/selection_types.json','tools/verification_profile/rust/binding_types.json','tools/verification_profile/rust/runtime_types.json','tests/verification_profile/test_commitments.py','tests/verification_profile/codec/commitment-bindings-vectors.json'}
    names.update(x.relative_to(ROOT).as_posix() for x in (ROOT/'tools/verification_profile/rust').glob('*.rs'))
    report=dict(status='PASS',cases=len(rows),positive=sum(x['valid'] for x in rows),results_sha256=hashlib.sha256(json.dumps(outputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),hostname=socket.gethostname(),python=sys.version.split()[0],kernel=platform.release(),rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(names)},full_schema_valid=False,full_phase_i_replay=False,source_authentication=False,production_admission=False,protocol_decision_emitted=False)
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
