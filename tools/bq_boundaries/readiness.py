# SPDX-License-Identifier: Apache-2.0
"""Non-authoritative B/Q evidence review and bounded lifecycle projections.

Only supplied research facts are consumed. No signatures, registry, finalized
log, external source, live clock or runtime capability is verified or changed.
A complete stipulated inventory yields a REVIEW candidate, never ENABLED.
"""
import copy
from fractions import Fraction
import json

from .calibration import fields, integer, ratio, digest
from .model import liveness_curve, required_draws

# Primary evidence layer, needed for audit execution review?, normative owner.
REQUIREMENTS={
 'contract_schema_registry':('A',True,'protocol-spec §3; Profile §13'),
 'runtime_conformance':('C',True,'ADR-0005 §3; MAP-5'),
 'lease_scope_binding':('C',True,'ADR-0005 §2.7; SV-117'),
 'log_and_status_sources':('C',True,'MAP-6; AS-3; EF-6/7'),
 'bounded_consumption_and_loss':('D',True,'INV-09/10; ADR-0005 §3'),
 'frozen_policy':('A',True,'D-04; INV-01/12'),
 'support_capability_bound':('C',False,'AR-2/3/5; SC-2'),
 'correctness_bridge':('C',False,'AR-2; MAP-5'),
 'population_binding':('A',False,'PB-1..9; SV-81/94'),
 'randomness_slot_accounting':('C',False,'AR-2; result-validation §6'),
 'q_truth_calibration':('C',False,'LP-1/4/5'),
 'calibration_confidence_accounting':('B',False,'BQ-W4-S2 finite-sample route only'),
 'assurance_components_revocation':('D',True,'MAP-1/2/3/8; AR-1; AS-3'),
 'exact_dp_budget':('B',False,'LP-2/3; SV-10/11'),
}
STAGES={'CREATE','PRE_FREEZE','FROZEN_PRE_DRAW','RUNNING','TERMINAL'}
TRIGGERS={'SUPPORT_CAPABILITY_BOUND_UNAVAILABLE','POPULATION_TOO_SMALL','CALIBRATION_OUT_OF_SCOPE'}
FAILURES=TRIGGERS|{'CONTRACT_MISMATCH','REQUIRED_EVIDENCE_MISSING','SOURCE_UNAVAILABLE','MAP_NOT_ENABLED'}
STATES={'STIPULATED_VALID','NOT_ESTABLISHED','REVOKED','SOURCE_UNAVAILABLE','INVALID','EXPIRED'}
KINDS={'EXTERNAL_REVIEW_STIPULATED','EXPERIMENT_ONLY','SYNTHETIC_ONLY','MISSING'}
TERMINALS={'TRUSTED','UNRESOLVED','FAILED','EXPIRED','FUNDING_EXHAUSTED'}


def strict_json(raw):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result: raise ValueError('duplicate research JSON key')
            result[k]=v
        return result
    def reject(x):raise ValueError('float/constant forbidden: '+x)
    return json.loads(raw,object_pairs_hook=pairs,parse_float=reject,parse_constant=reject)


def boolean(x):
    if type(x) is not bool:raise ValueError('explicit research bool required')


def assess_inventory(data):
    fields(data,{'schema_id','data_kind','context','parameters','records'})
    if data['schema_id']!='aclt.research.bq-readiness@1' or data['data_kind'] not in {'synthetic-review','project-gap-inventory'}:
        raise ValueError('research inventory required; not a protocol object')
    c=data['context'];fields(c,{'evaluation_tick','target_scope_digest','network_digest','assurance_network_digest','network_is_official','reuses_official_assurance'})
    integer(c['evaluation_tick'],0,None,'supplied tick')
    for key in ['target_scope_digest','network_digest','assurance_network_digest']:digest(c[key])
    for key in ['network_is_official','reuses_official_assurance']:boolean(c[key])
    p=data['parameters'];fields(p,{'G','B','Q','epsilon_F','delta_Q','delta_L','alpha_calibration','delta_min','n_budget','n_policy','n_required_claimed'})
    g=integer(p['G'],1,None,'G');b=integer(p['B'],0,g,'B');q=integer(p['Q'],0,g,'Q')
    for key in ['epsilon_F','delta_Q','delta_L','alpha_calibration','delta_min']:ratio(p[key])
    for key in ['n_budget','n_policy','n_required_claimed']:integer(p[key],1,g,key)
    if type(data['records']) is not list:raise ValueError('explicit records required')
    known={};issues=[];core=[]
    for row in data['records']:
        fields(row,{'requirement_id','state','evidence_kind','evidence_digest','scope_digest','validity'})
        rid=row['requirement_id']
        if rid not in REQUIREMENTS or rid in known:raise ValueError('unknown or duplicate research requirement')
        if row['state'] not in STATES or row['evidence_kind'] not in KINDS:raise ValueError('unknown research evidence state')
        if data['data_kind']=='project-gap-inventory' and row['state']=='STIPULATED_VALID':
            raise ValueError('project gap inventory cannot invent stipulated approval')
        if row['evidence_digest'] is not None:digest(row['evidence_digest'])
        if row['scope_digest'] is not None:digest(row['scope_digest'])
        window=row['validity']
        if window is not None:
            if type(window) is not list or len(window)!=2:raise ValueError('explicit time range required')
            integer(window[0],0,None,'start');integer(window[1],0,None,'end')
            if window[0]>=window[1]:raise ValueError('nonempty half-open range required')
        if row['state']=='STIPULATED_VALID' and (row['evidence_digest'] is None or row['scope_digest'] is None or window is None):
            raise ValueError('stipulated evidence needs explicit binding and window')
        known[rid]=row
    for rid,(_,is_core,_) in REQUIREMENTS.items():
        row=known.get(rid);reasons=[]
        if row is None:reasons=['MISSING_RECORD']
        else:
            if row['state']!='STIPULATED_VALID':reasons.append('STATE_'+row['state'])
            if row['evidence_kind']!='EXTERNAL_REVIEW_STIPULATED':reasons.append('BASIS_'+row['evidence_kind'])
            # SHA scope equality is disabled; fields remain records.
            window=row['validity']
            if window is None:reasons.append('NO_WINDOW')
            elif not window[0]<=c['evaluation_tick']<window[1]:reasons.append('OUTSIDE_WINDOW')
        for reason in reasons:
            item=rid+':'+reason;issues.append(item)
            if is_core:core.append(item)
    required=None;nmax=min(g,p['n_budget'],p['n_policy'])
    if not 0<=b<q<=g or Fraction(q-b,g)<ratio(p['delta_min']):
        issues.append('NUMERIC_PROFILE_NOT_ADMISSIBLE')
    else:
        required=required_draws(liveness_curve(g,b,q,{q:Fraction(1)},ratio(p['epsilon_F'])),ratio(p['delta_L']))
        if required is None or required!=p['n_required_claimed']:issues.append('DP_REQUIREMENT_NOT_BOUND')
        if required is None or required>nmax:issues.append('DP_BUDGET_TOO_SMALL')
    if c['reuses_official_assurance'] and not c['network_is_official']:
        issues.append('OFFICIAL_ASSURANCE_REUSED_OUTSIDE_BOUNDARY');core.append('OFFICIAL_ASSURANCE_REUSED_OUTSIDE_BOUNDARY')
    if not c['network_is_official'] or not c['reuses_official_assurance']:
        issues.append('NO_OFFICIAL_BOUNDED_ASSURANCE')
    ceiling='NO_REEXEC_REVIEW_CANDIDATE' if core else ('AUDIT_ONLY_REVIEW_CANDIDATE' if issues else 'BOUNDED_REVIEW_CANDIDATE')
    return {'research_ceiling':ceiling,'data_kind':data['data_kind'],'causes':sorted(set(issues)),
            'audit_core_causes':sorted(set(core)), 'computed_n_required':required,'n_max':nmax,
            'automatic_deployment_eligibility':False,'writes_runtime_state':False,
            'formal_phase_validator_implemented':False,'causes_are_not_formal_CauseSet':True}


def precreate_selection(case):
    fields(case,{'stage','failure_reasons','enabling_triggers','requester_authorized','edge_class',
                 'source_digest','edge_source_digest','target_digest','edge_target_digest','target_applicable','target_gate_ok'})
    if case['stage'] not in STAGES:raise ValueError('unknown research stage')
    for key in ['requester_authorized','target_applicable','target_gate_ok']:boolean(case[key])
    for key in ['source_digest','edge_source_digest','target_digest','edge_target_digest']:digest(case[key])
    for key,allowed in [('failure_reasons',FAILURES),('enabling_triggers',TRIGGERS)]:
        v=case[key]
        if type(v) is not list or len(v)!=len(set(v)) or not set(v)<=allowed:raise ValueError('closed unique trigger list required')
    if case['edge_class'] not in {'AUTO_DECIDABLE','ATTESTED'}:raise ValueError('unknown edge class')
    reasons=[]
    if case['stage']!='CREATE':reasons.append('EXISTING_RECEIPT_PROFILE_IMMUTABLE')
    if not case['requester_authorized']:reasons.append('REQUESTER_DID_NOT_AUTHORIZE')
    if case['edge_class']!='AUTO_DECIDABLE':reasons.append('EDGE_NOT_AUTO_DECIDABLE')
    # SHA edge equality is disabled; authorization and phase checks remain.
    if not case['failure_reasons'] or not set(case['failure_reasons'])<=set(case['enabling_triggers']):reasons.append('FAILURES_NOT_COVERED')
    if not case['target_applicable'] or not case['target_gate_ok']:reasons.append('TARGET_NOT_APPLICABLE_OR_GATED')
    return {'projection':'AUDIT_SLOT_REVIEW_CANDIDATE' if not reasons else 'NO_AUTOMATIC_FALLBACK',
            'causes':sorted(reasons),'changes_existing_receipt':False,'authorizes_runtime':False,
            'boundary':'only bounded-to-audit edge; not full D-06 ordered slot selection'}


def lifecycle_projection(stage,event,terminal=None,liveness_mapping=None):
    if stage not in STAGES or stage=='CREATE':raise ValueError('existing Receipt stage required')
    if event not in {'POPULATION_BINDING_FAILURE','SAFETY_REVOKED','SOURCE_UNAVAILABLE','CALIBRATION_REVOKED','VALIDITY_WINDOW_ENDED'}:raise ValueError('unknown research event')
    if (stage=='TERMINAL' and terminal not in TERMINALS) or (stage!='TERMINAL' and terminal is not None):raise ValueError('explicit compatible terminal required')
    action='';hint=None;qualification=None
    if event=='POPULATION_BINDING_FAILURE':
        action={'PRE_FREEZE':'REJECT_CURRENT_PHASE_B_OPERATION','FROZEN_PRE_DRAW':'INVALIDATE_SNAPSHOT_BLOCK_FIRST_DRAW_AND_REFREEZE',
                'RUNNING':'VERIFICATION_INVALIDATING','TERMINAL':'APPEND_QUALIFICATION_REVIEW_ONLY'}[stage]
        if stage in {'FROZEN_PRE_DRAW','RUNNING'}:hint='UNRESOLVED'
    elif event=='SAFETY_REVOKED':
        if stage=='TERMINAL':action='APPEND_QUALIFICATION_ONLY';qualification='DEPENDENCY_REVOKED'
        elif stage=='RUNNING':action='VERIFICATION_INVALIDATING';hint='UNRESOLVED'
        else:action='BLOCK_ADMISSION_BEFORE_VERIFICATION'
    elif event=='VALIDITY_WINDOW_ENDED':
        if stage=='TERMINAL':action='PRESERVE_TERMINAL_NO_RETROACTIVE_EXPIRY'
        elif stage=='RUNNING':action='VERIFICATION_INVALIDATING';hint='UNRESOLVED'
        else:action='BLOCK_ADMISSION_BEFORE_VERIFICATION'
    elif event=='SOURCE_UNAVAILABLE':
        action='NO_VERDICT_FAIL_CLOSED' if stage!='TERMINAL' else 'PRESERVE_TERMINAL_AND_RECORD_SOURCE_FAILURE'
        if stage!='TERMINAL':hint='UNRESOLVED_IF_PHASE_D_CAN_COMMIT'
    else:
        fields(liveness_mapping,{'before_verification','during_verification','after_terminal'})
        allowed={'before_verification':{'BLOCK_ADMISSION','PROCEED'},'during_verification':{'VERIFICATION_INVALIDATING','PROCEED'},
                 'after_terminal':{'QUALIFY_REVOKED','QUALIFY_WEAKENED','NO_EFFECT'}}
        if any(liveness_mapping[k] not in allowed[k] for k in allowed):raise ValueError('invalid frozen LIVENESS mapping')
        action=liveness_mapping['after_terminal' if stage=='TERMINAL' else 'during_verification' if stage=='RUNNING' else 'before_verification']
        if action=='VERIFICATION_INVALIDATING':hint='UNRESOLVED'
        qualification={'QUALIFY_REVOKED':'DEPENDENCY_REVOKED','QUALIFY_WEAKENED':'WEAKENED'}.get(action)
    return {'stage':stage,'event':event,'action':action,'terminal_hint_not_commit':hint,
            'terminal_preserved':terminal,'qualification_hint':qualification,
            'liveness_claim_requires_review':event=='CALIBRATION_REVOKED',
            'profile_switch_authorized':False,'parameter_change_authorized':False,
            'guest_retry_authorized':False,'new_TRUSTED_authorized':False,
            'writes_runtime_state':False,'boundary':'limited rule projection, not P0-5 or finalized event/qualification implementation'}


def matrix_report(hypothetical,current):
    inventories=[]
    def add(name,mutate):
        d=copy.deepcopy(hypothetical);mutate(d);inventories.append({'case':name,'result':assess_inventory(d)})
    def record(d,rid):return next(x for x in d['records'] if x['requirement_id']==rid)
    add('all_stipulated_inputs',lambda d:None)
    add('B_not_established',lambda d:record(d,'support_capability_bound').update(state='NOT_ESTABLISHED'))
    add('synthetic_Q_not_deployment',lambda d:record(d,'q_truth_calibration').update(evidence_kind='SYNTHETIC_ONLY'))
    add('expired_B',lambda d:record(d,'support_capability_bound').update(validity=[0,100]))
    add('wrong_Q_scope',lambda d:record(d,'q_truth_calibration').update(scope_digest='0'*64))
    add('revocation_source_unavailable',lambda d:record(d,'assurance_components_revocation').update(state='SOURCE_UNAVAILABLE'))
    add('log_source_unavailable',lambda d:record(d,'log_and_status_sources').update(state='SOURCE_UNAVAILABLE'))
    add('budget_too_small',lambda d:d['parameters'].update(n_budget=5))
    add('no_positive_gap',lambda d:d['parameters'].update(B=8,Q=8))
    add('wrong_claimed_DP',lambda d:d['parameters'].update(n_required_claimed=5))
    add('private_reuses_mainnet',lambda d:d['context'].update(network_is_official=False))
    add('simultaneous_B_and_Q_failure',lambda d:(record(d,'support_capability_bound').update(state='REVOKED'),record(d,'q_truth_calibration').update(scope_digest='0'*64)))
    e={'stage':'CREATE','failure_reasons':['SUPPORT_CAPABILITY_BOUND_UNAVAILABLE'],
       'enabling_triggers':['SUPPORT_CAPABILITY_BOUND_UNAVAILABLE'],'requester_authorized':True,
       'edge_class':'AUTO_DECIDABLE','source_digest':'1'*64,'edge_source_digest':'1'*64,
       'target_digest':'2'*64,'edge_target_digest':'2'*64,'target_applicable':True,'target_gate_ok':True}
    selections=[]
    for name,patch in [('authorized_precreate',{}),('no_authorization',{'requester_authorized':False}),
                       ('attested_edge',{'edge_class':'ATTESTED'}),('digest_mismatch',{'edge_target_digest':'3'*64}),
                       ('unrelated_failure',{'failure_reasons':['SUPPORT_CAPABILITY_BOUND_UNAVAILABLE','CONTRACT_MISMATCH']}),
                       ('target_disabled',{'target_gate_ok':False}),('receipt_already_frozen',{'stage':'PRE_FREEZE'}),
                       ('already_running',{'stage':'RUNNING'})]:
        d=copy.deepcopy(e);d.update(patch);selections.append({'case':name,'result':precreate_selection(d)})
    transitions=[]
    for event in ['POPULATION_BINDING_FAILURE','SAFETY_REVOKED','SOURCE_UNAVAILABLE','VALIDITY_WINDOW_ENDED']:
        for stage in ['PRE_FREEZE','FROZEN_PRE_DRAW','RUNNING','TERMINAL']:
            transitions.append(lifecycle_projection(stage,event,'TRUSTED' if stage=='TERMINAL' else None))
    mapping={'before_verification':'PROCEED','during_verification':'PROCEED','after_terminal':'QUALIFY_WEAKENED'}
    for stage in ['PRE_FREEZE','RUNNING','TERMINAL']:
        transitions.append(lifecycle_projection(stage,'CALIBRATION_REVOKED','TRUSTED' if stage=='TERMINAL' else None,mapping))
    return {'status':'PASS','kind':'research-evidence-review-not-capability-enablement',
            'requirements':{k:{'primary_evidence_layer':v[0],'audit_core':v[1],'owner':v[2]} for k,v in REQUIREMENTS.items()},
            'inventory_assessment':assess_inventory(current),'stipulated_inventory_cases':inventories,
            'precreate_selection_cases':selections,'lifecycle_projections':transitions,
            'case_counts':{'requirements':len(REQUIREMENTS),'inventories':len(inventories),'precreate':len(selections),'lifecycle':len(transitions)},
            'automatic_deployment_eligibility':False,'changes_runtime_capability':False,
            'limits':['all positive inputs are stipulated synthetic review facts, not evidence authentication',
                      'Q sample confidence accounting is the slice-2 research route, not a new protocol field',
                      'no full Phase R/I/F/B/D, source verifier, finalized ledger or P0-5 implementation',
                      'existing Receipts never change Profile; terminal hints do not commit or rewrite terminal states']}
