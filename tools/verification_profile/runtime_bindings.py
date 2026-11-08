# SPDX-License-Identifier: Apache-2.0
"""Explicit Phase B guards with pinned TEST snapshot/randomness adapters.

No state is committed, no capability or protocol Decision is emitted. These
checks do not authenticate imported populations, events or deployment sources.
"""
import hashlib,json
from pathlib import Path
from tools.verification_profile import codec as c,registration as reg,profile as p,commitments as b,selection,phase_b
from tools.verification_profile.event_frontier import ancestors
EXTRA=json.loads((Path(__file__).parent/'rust/runtime_types.json').read_text())
c.need(not EXTRA.keys()&b.TYPES.keys(),'duplicate runtime type')
TYPES=b.TYPES|EXTRA
STAGES=('PRE_FREEZE','FROZEN_PRE_DRAW','RUNNING','TERMINAL')
SHAPES={
 'LEASE_ACTIVATION_PRE_FREEZE':('actual_bound_scope',),
 'LEASE_ACTIVATION_POST_FREEZE':('actual_bound_scope','eligibility_snapshot'),
 'CLUSTER_MAPPING_FIX':('cluster_mapping_fixed_event',),
 'SNAPSHOT_FREEZE':('actual_bound_scope','eligibility_snapshot'),
 'ROUND_TRANSITION_PRE_FREEZE':(),
 'ROUND_TRANSITION_POST_FREEZE':('eligibility_snapshot',),
 'ROUND_TRANSITION_NO_SNAPSHOT':(),
}
CONSEQUENCES=dict(PRE_FREEZE='REJECT_OPERATION',FROZEN_PRE_DRAW='INVALIDATE_SNAPSHOT_NO_REFREEZE',RUNNING='VERIFICATION_INVALIDATING',TERMINAL='QUALIFICATION_ONLY')


def typed(v,kind,i):reg.typed(v,kind,i,TYPES)
def same(a,b):return (a is b) if a is None or b is None else c.encode(a)==c.encode(b)
def frozen(profile):
    s=profile['safety_parameters'];l=profile['liveness_parameters']
    return dict(G=s['G'],B=s['B'],Q=l['Q'],delta_min=s['delta_min'],mixture_weights=profile['method_parameters']['mixture_weights'])


def shape(envelope,imports):
    typed(envelope,'RuntimeEnvelopeR9',imports);payload=envelope['payload'];c.need(type(payload) is dict,'payload object')
    tag=payload.get('tag');c.need(type(tag) is str and tag in SHAPES,'SV-93: payload tag')
    c.fields(payload,('tag','transition')+SHAPES[tag],('transition_event_ref',) if tag=='ROUND_TRANSITION_NO_SNAPSHOT' else ())
    typed(payload['transition'],'FreezeTransitionR9' if tag=='SNAPSHOT_FREEZE' else 'TransitionR9',imports)
    if 'actual_bound_scope' in payload:
        typed(payload['actual_bound_scope'],'DeclaredScopeR7',imports)
        c.need(payload['actual_bound_scope']['fault_domains'] and payload['actual_bound_scope']['geography'],'SV-77: empty actual dimension')
    if 'cluster_mapping_fixed_event' in payload:imports.check('EventRef',payload['cluster_mapping_fixed_event'])
    if 'transition_event_ref' in payload:imports.check('EventRef',payload['transition_event_ref'])
    if 'eligibility_snapshot' in payload:
        snapshot=b.external_value(payload['eligibility_snapshot'],imports);typed(snapshot,'SnapshotAdapterR9',imports)
        c.need(bool(snapshot['id']),'empty snapshot ID')
        for row in snapshot['sampling_units']:
            c.need(bool(row['id']) and row['scope']['fault_domains'] and row['scope']['geography'],'snapshot unit shape')
        return snapshot
    return None


def visible_events(frontier):
    events={c.encode(x['event_ref']):x for x in frontier['event_records']}
    return events,ancestors(events,c.encode(frontier['frontier_event_ref']))


def event_is(events,visible,ref,kind,tag,identifier):
    row=events.get(c.encode(ref))
    return c.encode(ref) in visible and row is not None and row['event_kind']==kind and same(row['subject_ref'],dict(tag=tag,id=identifier))


def guard(e,snapshot,contract,i):
    profile=e['profile'];method=profile['verification_method'];payload=e['payload'];tag=payload['tag'];tr=payload['transition'];prior=tr['prior_round_state'];after=tr['proposed_round_state'];a=prior['round_stage'];z=after['round_stage'];bounded=method=='REEXEC_BOUNDED'
    binding=e['receipt_binding'];reference=selection.profile_ref(profile);assurance=e['assurance_profile']
    c.need(all(same(reference,x) for x in (binding['profile_ref'],e['bound_profile_ref'],prior['bound_profile_ref'],after['bound_profile_ref'])) and same(b.identity(assurance),binding['assurance_profile_ref']) and same(assurance['network_id'],binding['network_id']),'SV-92')
    if snapshot is not None:c.need(same(snapshot['receipt_id'],binding['receipt_id']),'SV-92')
    c.need(STAGES.index(a)<=STAGES.index(z),'SV-105')
    if bounded:
        edges={'LEASE_ACTIVATION_PRE_FREEZE':a==z=='PRE_FREEZE','LEASE_ACTIVATION_POST_FREEZE':a==z and a in STAGES[1:],'CLUSTER_MAPPING_FIX':a==z=='PRE_FREEZE','SNAPSHOT_FREEZE':(a,z)==('PRE_FREEZE','FROZEN_PRE_DRAW'),'ROUND_TRANSITION_PRE_FREEZE':a==z=='PRE_FREEZE','ROUND_TRANSITION_POST_FREEZE':(a,z) in (('FROZEN_PRE_DRAW','RUNNING'),('RUNNING','RUNNING'),('RUNNING','TERMINAL'))}
        c.need(edges.get(tag,False),'SV-105')
        expected=frozen(profile)
        for state in (prior,after):
            c.need('frozen_parameters' in state and same(state['frozen_parameters'],expected),'SV-94')
            if state['round_stage']!='PRE_FREEZE':c.need('population_size' in state and state['population_size']==expected['G'] and 'cluster_mapping_ref' in state,'SV-94')
            elif 'population_size' in state:c.need(state['population_size']==expected['G'],'SV-94')
        old=prior.get('cluster_mapping_ref');new=after.get('cluster_mapping_ref')
        if tag=='CLUSTER_MAPPING_FIX':c.need(old is None and new is not None,'SV-106')
        else:c.need(same(old,new) if old is not None and new is not None else old is new,'SV-106')
        if tag=='SNAPSHOT_FREEZE':c.need(old is not None,'SV-106')
    else:
        c.need(tag in ('LEASE_ACTIVATION_PRE_FREEZE','ROUND_TRANSITION_NO_SNAPSHOT'),'SV-105')
        for state in (prior,after):
            c.need(not ({'frozen_parameters','population_size','cluster_mapping_ref'}&state.keys()) and state['round_stage']!='FROZEN_PRE_DRAW','SV-94')
        if tag=='LEASE_ACTIVATION_PRE_FREEZE':c.need(a==z=='PRE_FREEZE','SV-105')
        else:
            try:phase_b.validate_no_snapshot_round(method,binding['receipt_id'],reference,payload,e['bundle']['event_frontier_snapshot'])
            except c.CodecError:raise c.CodecError('SV-94')
    assumptions=[x for x in profile['assumption_references'] if x['role'] in ('SAFETY_CRITICAL','LIVENESS')]
    if 'actual_bound_scope' in payload:
        c.need(all(selection.scope_contains(x['scope'],payload['actual_bound_scope'],i) for x in assumptions),'SV-68')
    events,visible=visible_events(e['bundle']['event_frontier_snapshot'])
    if tag=='CLUSTER_MAPPING_FIX':
        c.need(event_is(events,visible,payload['cluster_mapping_fixed_event'],'CLUSTER_MAPPING_FIXED','CLUSTER_MAPPING',after['cluster_mapping_ref']['id']),'SV-106')
    if snapshot is not None:
        units=snapshot['sampling_units'];ids=[c.encode(x['id']) for x in units]
        c.need(len(ids)==len(set(ids)) and bool(snapshot['cluster_mapping_ref']),'SV-82')
        c.need(all(selection.scope_contains(x['scope'],unit['scope'],i) for x in assumptions for unit in units),'SV-69')
        c.need(all(same(snapshot['cluster_mapping_ref'],state.get('cluster_mapping_ref')) for state in (prior,after)),'SV-99')
        params=profile['method_parameters'];G=profile['safety_parameters']['G']
        c.need(same(snapshot['population_definition_ref'],params['population_definition']) and same(snapshot['snapshot_schema_ref'],params['snapshot_schema_ref']) and len(ids)==G,'SV-81')
        c.need(same(params['population_definition'],contract['population_definition_ref']) and same(params['snapshot_schema_ref'],contract['snapshot_schema_ref']) and same(params['randomness_commitment'],contract['randomness_rule_ref']),'SV-81')
        random=snapshot['randomness_commitment']
        c.need(random['scheme_id']==contract['scheme_id'] and any(same(random['parameters'],x) for x in contract['allowed_randomness_parameters']),'SV-81')
    if tag=='SNAPSHOT_FREEZE':
        record=tr['snapshot_freeze_record'];mapping=record['cluster_mapping_ref']
        c.need(same(mapping,snapshot['cluster_mapping_ref']),'SV-99')
        candidate={c.encode(x) for x in record['candidate_units_pre_scope_filter']};excluded={c.encode(x) for x in record['excluded_by_scope']};kept={c.encode(x) for x in record['frozen_units']}
        c.need(excluded<=candidate and kept==candidate-excluded and kept=={c.encode(x['id']) for x in snapshot['sampling_units']} and len(kept)==profile['safety_parameters']['G'],'SV-94')
        first,last=record['cluster_mapping_fixed_event'],record['freeze_event']
        c.need(event_is(events,visible,first,'CLUSTER_MAPPING_FIXED','CLUSTER_MAPPING',mapping['id']) and event_is(events,visible,last,'SNAPSHOT_FROZEN','ELIGIBILITY_SNAPSHOT',snapshot['id']) and c.encode(first)!=c.encode(last) and c.encode(first) in ancestors(events,c.encode(last)),'SV-107')


def inspect(raw,lock_pin,contract_pin):
    try:
        v=c.decode(raw);c.fields(v,('envelope','schema_lock','schema_documents','runtime_contract'))
        i=b.Imports(v['schema_lock'],v['schema_documents'],lock_pin);contract=v['runtime_contract'];typed(contract,'RuntimeContractR9',i)
        c.need(hashlib.sha256(c.encode(contract)).digest()==contract_pin,'runtime contract pin')
        c.need(bool(contract['scheme_id']) and bool(contract['allowed_randomness_parameters']),'empty runtime contract')
        e=v['envelope'];snapshot=shape(e,i);profile=e['profile'];p.verify_digest(profile)
        b.common.check_method(profile);b.common.check_assumptions(profile['assumption_references'],i);b.method_rules.check_matrix(profile,i);selection.check_parameter_refs(profile)
        reg.check_bundle(e['bundle'],i,'ReferencesBundle');b.check_digest(e['assurance_profile'],'MainnetAssuranceProfile',i)
        before=e['payload']['transition']['prior_round_state']['round_stage'];failure=None
        try:guard(e,snapshot,contract,i)
        except c.CodecError as ex:failure=str(ex)
        return dict(accepted=failure is None,failure_rule=failure or '',consequence=CONSEQUENCES[before] if failure else 'VALIDATED',prior_stage=before,payload_tag=e['payload']['tag'],schema_lock_sha256=lock_pin.hex(),runtime_contract_sha256=contract_pin.hex(),full_schema_valid=False,formal_phase_b_conformance=False,source_authentication=False,production_admission=False,protocol_decision_emitted=False,state_committed=False)
    except (KeyError,TypeError,ValueError,IndexError,RecursionError) as ex:raise c.CodecError('malformed runtime input') from ex
