# SPDX-License-Identifier: Apache-2.0
"""Frozen object commitments, Claim bindings and assumption-state components.

Native payloads require an explicit pinned import schema. ENUM wire, sum-union
adapters and admission input capsules are candidate interfaces, not normative
wire upgrades. No operation executes a verifier or emits a protocol Decision.
"""
import hashlib,json
from pathlib import Path
from tools.verification_profile import codec as c,profile as p,registration as r,references,registration_rules as common,method_rules,creation,selection
EXTRA=json.loads((Path(__file__).parent/'rust/binding_types.json').read_text())
TYPES=r.TYPES|creation.EXTRA|selection.EXTRA|method_rules.METHOD_TYPES
if TYPES.keys()&EXTRA.keys():raise c.CodecError('duplicate binding type')
TYPES|=EXTRA
TEMPLATES=dict(DIRECT_VERIFIED='acl.ct.direct-predicate',PROOF_VERIFIED='acl.ct.proof-statement',REEXEC_BOUNDED='acl.ct.reexec-canonical')
SPECIFIC=dict(DIRECT_VERIFIED={'EXC-SPEC-PREDICATE-FIT','EXC-IMPL-VALIDATOR'},PROOF_VERIFIED={'EXC-IMPL-VALIDATOR','EXC-PROOF-SYSTEM','EXC-PROOF-STATEMENT-FIT'},REEXEC_BOUNDED={'EXC-STAT-BOUND-SOURCE','EXC-STAT-CALIBRATION'},REEXEC_AUDIT_ONLY=set())
REDUCER_SOURCE=b'ACLt R8 reference: REVOKED > OUT_OF_SCOPE > WINDOW_EXPIRED > VALID; full cause set retained.'
def default_reducer_ref():
    return dict(id='acl.reducer.r8-default',version=[1,0,0],digest=hashlib.sha256(REDUCER_SOURCE).digest())
CAUSE_ORDER=('REVOKED','OUT_OF_SCOPE','WINDOW_EXPIRED')
VERSIONED={'VerificationProfile':None,'ClaimTemplate':'TemplateR8','ProfileSelectionPolicy':'PolicyR7','ConformanceManifest':'ManifestR7','RegistrySnapshot':'Registry','WeakeningEdge':'EdgeR7','ExcludedClaimsRegistry':'ExclusionRegistry','MainnetAssuranceProfile':'AssuranceR8'}
RUNTIME={'AssumptionStateSnapshot':('StateSnapshotR8','ASSUMPTION_SNAPSHOT'),'CreationValidationContext':('CreationContext','CREATION_CONTEXT'),'PhaseIValidationRecord':('PhaseIRecord','PHASE_I_RECORD'),'EventFrontierSnapshot':('ReferencesFrontier','FRONTIER')}
ALIASES={'NetworkID':'network-id','MaintenanceAuthorityRef':'maintenance-authority-ref','PrincipalRef':'principal-ref','LogicalObjectRef':'logical-object-ref'}


class Imports(references.Imports):
    representations=frozenset({'OPAQUE_BSTR','VERSIONED_REF','NATIVE_CBOR'})

    def __init__(self,lock,documents,pin):
        super().__init__(lock,documents,pin)
        for alias,ref in self.refs.items():
            doc=self.documents[c.encode(c.reference_identity(ref))]
            if doc['representation']=='NATIVE_CBOR':
                c.need(alias=='NativeValue' and ref['id']=='acl.schema.r8-native-value@1','native schema namespace')
            if alias in ALIASES:
                c.need(ref['id']=='acl.schema.'+ALIASES[alias]+'@1' and doc['representation']=='OPAQUE_BSTR','fixed imported alias')

    @staticmethod
    def payload(value,representation):
        if representation=='NATIVE_CBOR':c.encode(value)
        else:references.Imports.payload(value,representation)


def typed(value,kind,imports):r.typed(value,kind,imports,TYPES)


def external_value(value,imports):
    imports.external_object(value)
    return c.decode(value['canonical_bytes'])


def identity(value):return {k:value['header'][k] for k in ('id','version','digest')}


def ordered(rows,key):
    codes=[c.encode(x[key]) for x in rows];c.need(codes==sorted(set(codes)),'canonical pair-array order/duplicate')


def projection(value,kind):
    """Top-level frozen ContentMaps; nested opaque/ENUM data is not guessed."""
    schema={'ClaimTemplate':'TemplateR8','AssumptionStateSnapshot':'StateSnapshotR8','MainnetAssuranceProfile':'AssuranceR8'}[kind]
    definition=EXTRA[schema];c.fields(value,definition['fields'],definition['optional'])
    h=value['header'];c.fields(h,('schema_version','encoding_profile_id','id','digest') if kind=='AssumptionStateSnapshot' else ('schema_version','encoding_profile_id','id','version','digest'))
    fields=('schema_version','encoding_profile_id','id') if kind=='AssumptionStateSnapshot' else ('schema_version','encoding_profile_id')
    excluded={'header','translations','human_summary'}
    return {k:h[k] for k in fields}|{k:v for k,v in value.items() if k not in excluded}


def object_digest(value,kind):
    return c.domain_hash('ACLt/P0-1/'+kind+'/1',c.encode(projection(value,kind)))


def check_digest(value,kind,imports):
    schema={'ClaimTemplate':'TemplateR8','AssumptionStateSnapshot':'StateSnapshotR8','MainnetAssuranceProfile':'AssuranceR8'}[kind]
    typed(value,schema,imports);c.need(value['header']['schema_version']==1,'object schema version')
    owner={'ClaimTemplate':'SV-70','AssumptionStateSnapshot':'SV-71','MainnetAssuranceProfile':'SV-113'}[kind]
    c.need(c.digest_consistency(value['header']['digest']==object_digest(value,kind)),owner+': object digest mismatch')


def state_digest(snapshot):
    rows=sorted(snapshot['assumption_states'],key=lambda x:c.encode(x['assumption_id']))
    return c.domain_hash('ACLt/P0-1/AssumptionState/1',c.encode([snapshot['reducer_ref'],rows]))


def rendered_digest(template_ref,bindings):
    return c.domain_hash('ACLt/P0-1/RenderedClaim/1',c.encode([template_ref,bindings]))


def decision_input_digest(value,imports):
    typed(value,'DecisionInputR8',imports)
    return c.domain_hash('ACLt/P0-1/DecisionEvaluationInput/1',c.encode(value))


def check_method_exclusions(profile):
    method=common.check_method(profile);ids=set(profile['excluded_claims']['exclusion_ids'])
    c.need(SPECIFIC[method]<=ids,'SV-09: method-specific exclusions missing')
    if method=='DIRECT_VERIFIED' and profile['method_parameters']['soundness_class']=='SOUND':
        c.need(profile['method_parameters']['reject_attribution']=='NO_ATTRIBUTION','SV-09: SOUND reject attribution')


def static_values(profile):
    method=profile['verification_method'];params=profile['method_parameters']
    if method=='DIRECT_VERIFIED':return {k:params[k] for k in ('predicate_ref','soundness_class','validator_ref')}
    if method=='PROOF_VERIFIED':return dict(proof_system_ref=params['proof_system_ref'],params_ref=params['public_params_ref'],statement_binding_rule=params['statement_binding_rule'],verifier_ref=params['verifier_ref'])
    if method=='REEXEC_BOUNDED':return dict(equivalence_id=profile['result_equivalence']['equivalence_id'],algorithm_id=params['algorithm_id'],profile_id=profile['profile_id'],profile_version=profile['profile_version'],assumption_set_digest=common.assumption_set_digest(profile['assumption_references']))
    return {}


def range_slots(profile):
    result=set()
    mapping={'protocol_version_range':'protocol_version','rir_version_range':'rir_version','runtime_profile_version_range':'rpr_profile_version','frontend_profile_version_range':'frontend_profile_version'}
    result.update(slot for field,slot in mapping.items() if field in profile['contract_tuple_constraints'])
    live=profile.get('liveness_parameters',{})
    result.update(k for k in ('calibration_rir_profile','calibration_rpr_version') if k in live)
    if profile['assumption_references']:result.update(('rir_version','rpr_profile_version'))
    return result


def check_spec(profile,template,snapshot,imports):
    p.verify_digest(profile);method=common.check_method(profile)
    if method=='REEXEC_AUDIT_ONLY':
        c.need('verified_claim_spec' not in profile,'SV-30: audit must omit claim')
        return
    spec=profile['verified_claim_spec'];typed(spec,'ClaimSpecR8',imports)
    c.need(spec['claim_template_ref']['id']==TEMPLATES[method],'SV-05: method/template ID')
    check_digest(template,'ClaimTemplate',imports)
    selection.check_snapshot(snapshot);reference=identity(template)
    c.need(c.reference_identity(spec['claim_template_ref'])==c.reference_identity(reference) and any(x['object_kind']=='CLAIM_TEMPLATE' and all(x[k]==reference[k] for k in reference if k!='digest') and x['state'] in ('REGISTERED','ACTIVE') for x in snapshot['entries']),'SV-48: template identity/state/snapshot')
    ordered(template['slot_decls'],'slot');ordered(template['translations'],'lang');ordered(spec['binding_schema'],'slot');ordered(spec['static_bindings'],'slot')
    declared={x['slot']:x['decl'] for x in template['slot_decls']};schema={x['slot']:x['decl'] for x in spec['binding_schema']}
    c.need(c.encode(declared)==c.encode(schema),'SV-06: template and binding schema differ')
    for name,decl in schema.items():
        c.need(name and ((decl['kind']=='STATIC' and decl['source']=='PROFILE') or (decl['kind']=='RUNTIME' and decl['source'] in ('RECEIPT','EVIDENCE_CHAIN','SNAPSHOT'))),'slot source/kind')
        if name in range_slots(profile):c.need(decl['kind']=='RUNTIME','SV-49: version range requires RUNTIME slot')
    static={x['slot']:x['value'] for x in spec['static_bindings']}
    c.need(set(static)=={k for k,v in schema.items() if v['kind']=='STATIC'},'SV-06: static keys, missing value or runtime static binding')
    expected=static_values(profile)
    for name,value in static.items():
        c.need(name in expected and c.encode(external_value(value,imports))==c.encode(expected[name]),'SV-44: STATIC binding differs from frozen field')


def check_concrete(profile,template,registry,bindings,imports):
    check_spec(profile,template,registry,imports)
    for value in bindings:typed(value,'ConcreteRowR8',imports)
    ordered(bindings,'slot_id');spec=profile['verified_claim_spec']
    c.need({x['slot_id'] for x in bindings}=={x['slot'] for x in spec['binding_schema']},'SV-35: concrete key set')
    actual={x['slot_id']:x['value'] for x in bindings}
    for row in spec['static_bindings']:
        c.need(c.encode(actual[row['slot']])==c.encode(row['value']),'SV-35: STATIC concrete binding changed')


def check_states(profile,result,imports):
    """Candidate sum envelope; frozen state rows and AS-2 default reducer semantics."""
    p.verify_digest(profile)
    c.need(type(result) is dict and result.get('tag') in ('COMPLETE','INVALIDATING'),'SV-116: assumption result tag')
    if result['tag']=='INVALIDATING':
        c.fields(result,('tag','failure'));typed(result['failure'],'AssumptionFailureR8',imports);return None
    c.fields(result,('tag','snapshot'));snapshot=result['snapshot'];check_digest(snapshot,'AssumptionStateSnapshot',imports)
    c.need(c.reference_identity(snapshot['reducer_ref'])==c.reference_identity(default_reducer_ref()),'unsupported assumption reducer contract')
    refs=profile['assumption_references'];common.check_assumptions(refs,imports)
    expected={x['assumption_id']:x for x in refs if x['role'] in ('SAFETY_CRITICAL','LIVENESS')}
    rows=snapshot['assumption_states'];ordered(rows,'assumption_id')
    c.need({x['assumption_id'] for x in rows}==set(expected),'SV-54a: exact non-informational coverage')
    for row in rows:
        source=expected[row['assumption_id']]
        c.need(row['evidence_ref']==source['evidence_ref'] and row['evidence_version']==source['evidence_version'],'state evidence reference/version binding')
        ordered(row['cause_set'],'cause_code');codes={x['cause_code'] for x in row['cause_set']}
        verdict=next((x for x in CAUSE_ORDER if x in codes),'VALID')
        c.need(row['effective_verdict']==verdict,'SV-54a: frozen reducer mismatch')
    return snapshot


def check_claim_guard(payload,imports):
    c.fields(payload,('profile','registry_snapshot','receipt_id','terminal_state','assumption_result'),('template','claim_binding','assurance_profile'))
    profile=payload['profile'];p.verify_digest(profile);c.digest_bytes(payload['receipt_id'])
    terminal=payload['terminal_state'];c.need(terminal in ('TRUSTED','UNRESOLVED','FAILED','EXPIRED','FUNDING_EXHAUSTED'),'terminal enum')
    snapshot=check_states(profile,payload['assumption_result'],imports)
    binding=payload.get('claim_binding')
    if terminal=='TRUSTED':
        c.need(profile['verification_method']!='REEXEC_AUDIT_ONLY' and binding is not None,'SV-36: TRUSTED requires non-audit complete binding')
        c.need(snapshot is not None,'SV-57: TRUSTED requires COMPLETE')
        states={x['assumption_id']:x for x in snapshot['assumption_states']}
        c.need(all(states[x['assumption_id']]['effective_verdict']=='VALID' for x in profile['assumption_references'] if x['role']=='SAFETY_CRITICAL'),'SV-57: safety-critical verdict')
    if binding is None:return
    c.need(profile['verification_method']!='REEXEC_AUDIT_ONLY','audit has no ClaimBinding')
    typed(binding,'ClaimBindingR8',imports)
    check_concrete(profile,payload['template'],payload['registry_snapshot'],binding['concrete_bindings'],imports)
    spec=profile['verified_claim_spec']
    c.need(binding['claim_spec_id']==spec['claim_spec_id'] and c.reference_identity(binding['claim_template_ref'])==c.reference_identity(spec['claim_template_ref']) and c.reference_identity(binding['profile_ref'])==c.reference_identity(selection.profile_ref(profile)) and binding['verification_method']==profile['verification_method'],'Claim/Profile identity binding')
    c.need(c.digest_consistency(binding['rendered_claim_digest']==rendered_digest(binding['claim_template_ref'],binding['concrete_bindings'])),'SV-46: rendered claim digest')
    c.need(snapshot is not None and snapshot['receipt_id']==payload['receipt_id'] and c.reference_identity(binding['assumption_state_snapshot_ref'])=={k:snapshot['header'][k] for k in ('id',)},'SV-78: Receipt/snapshot identity')
    c.need(c.digest_consistency(binding['assumption_state_digest']==state_digest(snapshot)),'SV-54b: assumption state digest')
    c.need(c.digest_consistency(binding['assumption_set_digest']==common.assumption_set_digest(profile['assumption_references'])),'static assumption set digest')
    excluded=profile['excluded_claims'];c.need(c.reference_identity(binding['excluded_claims_registry_ref'])==c.reference_identity(excluded['registry_ref']) and binding['excluded_claims_ids']==excluded['exclusion_ids'] and c.digest_consistency(binding['excluded_claims_digest']==excluded['digest']),'Claim exclusions binding')
    assurance=payload['assurance_profile'];check_digest(assurance,'MainnetAssuranceProfile',imports)
    c.need(binding['network_id']==assurance['network_id'] and c.reference_identity(binding['assurance_profile_ref'])==c.reference_identity(identity(assurance)) and c.digest_consistency(binding['assurance_boundary_digest']==assurance['header']['digest']) and c.reference_identity(snapshot['reducer_ref'])==c.reference_identity(assurance['assumption_verdict_reducer_ref']),'assurance boundary binding')
    bounded=profile['verification_method']=='REEXEC_BOUNDED'
    c.need(('algorithm_id' in binding)==bounded and ('snapshot_digest' in binding)==bounded,'method-specific claim fields')
    if bounded:c.need(binding['algorithm_id']==profile['method_parameters']['algorithm_id'],'claim algorithm binding')


def wire_check(kind,value,imports):
    if kind=='VerificationProfile':p.verify_digest(value);return
    if kind in VERSIONED:
        schema=VERSIONED[kind];typed(value,schema,imports)
    else:
        c.need(kind in RUNTIME,'unknown wire object kind');typed(value,RUNTIME[kind][0],imports)
    h=value['header'];runtime=kind in RUNTIME
    c.fields(h,('schema_version','encoding_profile_id','id','digest') if runtime else ('schema_version','encoding_profile_id','id','version','digest'))
    c.need(not ({'id','version','digest'}&value.keys()),'SV-86c: duplicate identity outside header')
    if runtime:
        if kind=='AssumptionStateSnapshot':content=projection(value,kind)
        elif kind=='CreationValidationContext':content=creation.content_map(value,'CreationContext')
        elif kind=='PhaseIValidationRecord':content=creation.content_map(value,'PhaseIRecord')
        else:content={k:h[k] for k in ('schema_version','encoding_profile_id','id')}|{k:v for k,v in value.items() if k!='header'}
        c.need(content['id']==h['id'],'SV-86b: runtime ID projection')


def runtime_ref(kind,value,imports):
    c.need(kind in RUNTIME,'runtime reference kind')
    c.fields(value,('id','digest'));r.identifier(value['id'],RUNTIME[kind][1]);c.digest_bytes(value['digest'])


def candidate_input(value,imports):
    """PROPOSED capsule, dedicated TEST tag. Never changes ReceiptIntent/1."""
    typed(value,'CandidateIntentR8',imports);base=value['base_intent'];creation.content_map(base,'ReceiptIntent')
    c.need(base['schema_version']==1,'candidate wraps existing Intent v1')
    c.need(value['fault_domains'] and value['geography'],'candidate scope dimensions nonempty')
    contract=value['contract_tuple'];raw=c.encode(contract)
    c.need(base['contract_tuple']==raw,'candidate ContractTuple bytes must match base Intent')
    scope=dict(task_class=value['task_type'],rir_version=contract['rir_version'],rpr_version=contract['rpr_version'],environment_class=value['environment_class'],fault_domains=value['fault_domains'],geography=value['geography'])
    return dict(candidate_digest_hex=c.domain_hash('ACLt/TEST/R8/AdmissionInput/1',c.encode(value)).hex(),base_intent_digest_hex=creation.object_digest(base,'ReceiptIntent').hex(),declared_scope_cbor_hex=c.encode(scope).hex(),effects_cbor_hex=c.encode(contract['allowed_effects']).hex(),n_max_decimal=str(value['n_max']),normative_intent_upgrade=False)


def inspect_components(raw,pin):
    value=c.decode(raw);c.fields(value,('operation','payload','schema_lock','schema_documents'))
    imports=Imports(value['schema_lock'],value['schema_documents'],pin);op=value['operation'];v=value['payload'];out={}
    if op=='registration':
        c.fields(v,('profile','registry_snapshot','exclusion_registry'),('template',));profile=v['profile']
        common.check_rules(profile,v['registry_snapshot'],imports);method_rules.check_matrix(profile,imports);selection.check_parameter_refs(profile)
        references.check_excluded(profile['excluded_claims'],v['exclusion_registry'],v['registry_snapshot']);check_method_exclusions(profile)
        check_spec(profile,v.get('template'),v['registry_snapshot'],imports)
    elif op=='claim-guard':check_claim_guard(v,imports)
    elif op=='state':
        c.fields(v,('profile','result'),('assumption_state_digest',));snapshot=check_states(v['profile'],v['result'],imports)
        if snapshot is not None:
            c.need(c.digest_consistency(v['assumption_state_digest']==state_digest(snapshot)),'SV-54b: assumption state digest');out['snapshot_digest_hex']=snapshot['header']['digest'].hex()
        else:c.need('assumption_state_digest' not in v,'INVALIDATING must not fabricate a state digest')
    elif op in ('template-digest','assurance-digest'):
        c.fields(v,('object',));kind='ClaimTemplate' if op=='template-digest' else 'MainnetAssuranceProfile';check_digest(v['object'],kind,imports);out['digest_hex']=v['object']['header']['digest'].hex()
    elif op=='rendered-digest':
        c.fields(v,('template_ref','bindings','digest'));typed(v['template_ref'],'TemplateRefR8',imports)
        for row in v['bindings']:typed(row,'ConcreteRowR8',imports)
        ordered(v['bindings'],'slot_id');c.need(c.digest_consistency(v['digest']==rendered_digest(v['template_ref'],v['bindings'])),'SV-46: rendered claim digest');out['digest_hex']=v['digest'].hex()
    elif op=='decision-input-digest':
        c.fields(v,('evaluation_input','input_digest'));c.need(c.digest_consistency(v['input_digest']==decision_input_digest(v['evaluation_input'],imports)),'SV-114: complete input digest');out['digest_hex']=v['input_digest'].hex()
    elif op=='wire':c.fields(v,('kind','object'));wire_check(v['kind'],v['object'],imports)
    elif op=='runtime-ref':c.fields(v,('kind','ref'));runtime_ref(v['kind'],v['ref'],imports)
    elif op=='candidate-input':c.fields(v,('candidate',));out.update(candidate_input(v['candidate'],imports))
    else:raise c.CodecError('unknown binding operation')
    out.update(operation=op,schema_lock_sha256=c.digest_record_hex(pin),full_schema_valid=False,full_phase_i_replay=False,source_authentication=False,production_admission=False,protocol_decision_emitted=False)
    return out


def inspect(raw,pin):
    try:return inspect_components(raw,pin)
    except (KeyError,TypeError,IndexError,RecursionError) as exc:raise c.CodecError('malformed binding input') from exc
