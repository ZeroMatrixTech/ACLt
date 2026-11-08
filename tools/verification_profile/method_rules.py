# SPDX-License-Identifier: Apache-2.0
"""Frozen method/failure/decision matrices; test imports are not deployment approval."""
import json
from pathlib import Path
from tools.verification_profile import codec as c, profile as p, registration as reg, references, registration_rules as common

METHOD_TYPES=json.loads((Path(__file__).parent/'rust/method_types.json').read_text())
if reg.TYPES.keys() & METHOD_TYPES.keys():
    raise c.CodecError('duplicate method type name')
TYPES=reg.TYPES|METHOD_TYPES
PARAM_TYPES=dict(zip(p.METHODS,('DirectParamsR5','ProofParamsR5','BoundedParamsR5','AuditParams')))
OUTCOMES={
 'DIRECT_VERIFIED':('ACCEPT','REJECT','INCONCLUSIVE','VERIFICATION_INVALIDATING'),
 'PROOF_VERIFIED':('PROOF_ACCEPTED','PROOF_REJECTED','INCONCLUSIVE','VERIFICATION_INVALIDATING'),
 'REEXEC_BOUNDED':('SUPPORT','NON_SUPPORT','INVALID_SAMPLE','VERIFICATION_INVALIDATING'),
 'REEXEC_AUDIT_ONLY':p.AUDIT_OUTCOMES,
}
BASE_EVENTS=tuple(x for x in p.AUDIT_EVENTS if not x.startswith('EQUIVALENCE_'))


def check_parameters(profile,imports):
    method=common.check_method(profile)
    c.need(profile['schema_version']==2,'R5 requires Profile v2')
    params=profile['method_parameters']
    c.need(type(params) is dict,'SV-04: method parameter object')
    if method=='REEXEC_BOUNDED':
        c.need(all(type(profile.get(key)) is dict and profile[key] for key in ('safety_parameters','liveness_parameters')),
               'SV-31: bounded requires both parameter blocks')
        c.need(profile['liveness_parameters'].get('q_source') in ('ANCHORED_IN_CLASS','FAULT_INJECTED_IN_CLASS'),
               'SV-13: q_source')
        reg.typed(profile['safety_parameters'],'SafetyR5',imports,TYPES)
        reg.typed(profile['liveness_parameters'],'LivenessR5',imports,TYPES)
    else:
        c.need('safety_parameters' not in profile and 'liveness_parameters' not in profile,
               'SV-31: method forbids safety/liveness blocks')
    if method=='DIRECT_VERIFIED':
        c.need(params.get('determinism')=='DETERMINISTIC' and params.get('effects')==[],
               'SV-16: direct deterministic and no effects')
    reg.typed(params,PARAM_TYPES[method],imports,TYPES)
    if method=='DIRECT_VERIFIED':
        c.need(params['verifier_replication_min']>=1,'direct verifier replication minimum')
        c.need(params['soundness_class']!='SOUND' or params['reject_attribution']=='NO_ATTRIBUTION',
               'SV-09: sound-only reject has no attribution')
    if method=='REEXEC_BOUNDED':
        ms=[row['m'] for row in params['mixture_weights']]
        c.need(ms==sorted(set(ms)),'mixture m order or duplicate')
    return method


def expected_events(profile):
    method=profile['verification_method'];events=set(BASE_EVENTS)
    if method=='DIRECT_VERIFIED':
        events.add('PREDICATE_UNDECIDED')
        if profile['method_parameters']['certificate_required']:events.add('CERTIFICATE_ABSENT')
    elif method=='PROOF_VERIFIED':events.add('PROOF_ABSENT')
    else:
        events.update(('EQUIVALENCE_UNDECIDED','EQUIVALENCE_RESOURCE_EXCEEDED'))
        if method=='REEXEC_BOUNDED':events.update(('SNAPSHOT_DIGEST_MISMATCH','RANDOMNESS_COMMITMENT_INVALID'))
    return sorted(events,key=c.encode)


def check_failure(profile):
    method=profile['verification_method'];mapping=profile['failure_mapping']
    c.need(type(mapping) is dict,'SV-19: failure mapping object')
    bounded=method=='REEXEC_BOUNDED'
    if bounded:
        c.need('max_invalid_samples' in mapping,'SV-29R: max_invalid_samples required')
        c.uint(mapping['max_invalid_samples'])
    c.fields(mapping,('entries','max_invalid_samples') if bounded else ('entries',))
    c.need(type(mapping['entries']) is list,'SV-19: failure entries array')
    keys=[];field='evidence_class' if bounded else 'outcome'
    for row in mapping['entries']:
        c.fields(row,('key','value'));c.text(row['key']);keys.append(row['key'])
        value=row['value'];c.fields(value,(field,'attribution'))
        c.need(type(value[field]) is str and value[field] in OUTCOMES[method],'SV-19: wrong outcome variant')
        c.need(type(value['attribution']) is str and value['attribution'] in p.ATTRIBUTIONS,'SV-19: attribution')
        if method=='DIRECT_VERIFIED' and row['key']=='PREDICATE_UNDECIDED':
            c.need(value[field]=='INCONCLUSIVE','direct UNDECIDED maps to INCONCLUSIVE')
    c.need(keys==expected_events(profile),'SV-18: exact applicable events/order/uniqueness')


def expected_conditions(profile):
    method=profile['verification_method'];allowed=set(p.AUDIT_CONDITIONS)
    if method!='REEXEC_AUDIT_ONLY':allowed.add('ACCEPT')
    if method=='DIRECT_VERIFIED':
        allowed.add('REJECT_COMPLETE' if profile['method_parameters']['soundness_class']=='SOUND_AND_COMPLETE' else 'REJECT_SOUND_ONLY')
    elif method=='PROOF_VERIFIED':allowed.add('REJECT_SOUND_ONLY')
    return [name for name in p.CONDITIONS if name in allowed]


def check_decision(profile,claimed_reachable=None):
    p.decision_fields(profile)
    rules=profile['decision_mapping']['rules']
    c.need('EXECUTION_FAILED' in rules,'SV-51: EXECUTION_FAILED required')
    c.need(rules==expected_conditions(profile),'SV-20: exact method condition set')
    reachable=sorted({p.TERMINALS[name] for name in rules}|{'UNRESOLVED'},key=c.encode)
    if profile['verification_method']=='REEXEC_AUDIT_ONLY':
        c.need(profile['method_parameters']['reachable_terminals']==reachable,'SV-64: audit reachable terminals')
    if claimed_reachable is not None:
        c.need(claimed_reachable==reachable,'SV-64: adapter expected reachable terminals')
    return reachable


def check_matrix(profile,imports,claimed_reachable=None):
    method=check_parameters(profile,imports)
    check_failure(profile)
    reachable=check_decision(profile,claimed_reachable)
    return dict(verification_method=method,events=len(expected_events(profile)),conditions=expected_conditions(profile),
                reachable_terminals=reachable,full_schema_valid=False,source_authentication=False)


def inspect(raw,pin):
    value=c.decode(raw)
    c.fields(value,('profile','registry_snapshot','schema_lock','schema_documents','assumption_set_digest','reachable_terminals'))
    imports=references.Imports(value['schema_lock'],value['schema_documents'],pin)
    result=common.check_rules(value['profile'],value['registry_snapshot'],imports)
    c.digest_bytes(value['assumption_set_digest'])
    c.need(value['assumption_set_digest'].hex()==result['assumption_set_digest_hex'],'SV-73: assumption set digest')
    result.update(check_matrix(value['profile'],imports,value['reachable_terminals']))
    return result


def inspect_audit(raw,pin):
    value=c.decode(raw);c.fields(value,('envelope','schema_lock','schema_documents','registry_objects'))
    envelope=value['envelope'];c.fields(envelope,('phase','bundle','object'))
    profile=envelope['object'];c.need(common.check_method(profile)=='REEXEC_AUDIT_ONLY','fixed audit R5 integration scope')
    p.verify_digest(profile)
    imports=references.Imports(value['schema_lock'],value['schema_documents'],pin)
    matrix=check_matrix(profile,imports)
    result=common.inspect_audit(raw,pin);result.update(matrix)
    return result


def project(value):
    """Method-outcome rows of frozen Pi; aggregate flags are explicit test inputs."""
    c.need(type(value) is dict,'projection adapter map')
    method=value.get('verification_method');c.need(type(method) is str and method in p.METHODS,'method')
    keys=['verification_method','outcome','aggregate_exhausted']
    if method=='DIRECT_VERIFIED':keys.append('soundness_class')
    if method=='REEXEC_BOUNDED':keys+=['threshold_met','null_bound_exactly_exceeded']
    c.fields(value,keys)
    c.need(type(value['aggregate_exhausted']) is bool,'aggregate flag must be bool')
    outcome=value['outcome'];allowed=OUTCOMES[method]+(('NULL_BOUND_EXACTLY_EXCEEDED',) if method=='REEXEC_BOUNDED' else ())
    c.need(type(outcome) is str and outcome in allowed,'method outcome')
    if method=='DIRECT_VERIFIED':c.need(value['soundness_class'] in ('SOUND','SOUND_AND_COMPLETE'),'soundness')
    if method=='REEXEC_BOUNDED':
        c.need(all(type(value[name]) is bool for name in ('threshold_met','null_bound_exactly_exceeded')),'aggregate flags must be bool')
    condition=None
    if outcome=='VERIFICATION_INVALIDATING':condition='VERIFICATION_INVALIDATING'
    elif method=='DIRECT_VERIFIED':
        if outcome=='ACCEPT':condition='ACCEPT'
        elif outcome=='REJECT':condition='REJECT_COMPLETE' if value['soundness_class']=='SOUND_AND_COMPLETE' else 'REJECT_SOUND_ONLY'
    elif method=='PROOF_VERIFIED':
        if outcome=='PROOF_ACCEPTED':condition='ACCEPT'
        elif outcome=='PROOF_REJECTED':condition='REJECT_SOUND_ONLY'
    elif method=='REEXEC_BOUNDED' and (value['threshold_met'] or value['null_bound_exactly_exceeded'] or outcome=='NULL_BOUND_EXACTLY_EXCEEDED'):
        condition='ACCEPT'
    if condition is None and value['aggregate_exhausted']:condition='EVIDENCE_EXHAUSTED'
    return dict(condition_present=False) if condition is None else dict(condition_present=True,condition=condition)
