# SPDX-License-Identifier: Apache-2.0
"""Frozen registration assets and selection/binding rule components.

Explicit snapshots/import pins are input. This is not a registration authority,
full ReplayPhaseI, CreateReceipt or source authentication. Applicability helpers
consume declared test-adapter values; they never infer fields of opaque imports.
"""
import json,re
from pathlib import Path
from tools.verification_profile import codec as c,profile as p,registration as r,references,registration_rules as common,method_rules
EXTRA=json.loads((Path(__file__).parent/'rust/selection_types.json').read_text())
if r.TYPES.keys()&EXTRA.keys():raise c.CodecError('duplicate selection type')
TYPES=r.TYPES|EXTRA


def typed(value,kind,imports):r.typed(value,kind,imports,TYPES)


def profile_ref(profile):return dict(id=profile['profile_id'],version=profile['profile_version'],digest=profile['profile_digest'])


def check_snapshot(snapshot):
    r.typed(snapshot,'Registry',None);r.check_registry(snapshot)


def resolve_profile(reference,profiles,snapshot):
    """Resolve complete identity with one explicit actual object; no remote lookup."""
    r.typed(reference,'ProfileRef',None)
    matches=[x for x in profiles if c.reference_identity(profile_ref(x))==c.reference_identity(reference)]
    c.need(len(matches)==1,'one explicit Profile for complete reference required')
    profile=matches[0];p.verify_digest(profile)
    c.need(any(row['object_kind']=='VERIFICATION_PROFILE' and all(row[k]==reference[k] for k in reference if k!='digest')
               for row in snapshot['entries']),'Profile identity absent from snapshot')
    return profile


def check_profile_assets(profiles,snapshot):
    check_snapshot(snapshot);c.need(type(profiles) is list,'Profile asset array')
    identities=[]
    for profile in profiles:
        common.check_method(profile);p.verify_digest(profile)
        reference=profile_ref(profile);r.typed(reference,'ProfileRef',None);identities.append(c.encode(reference))
        resolve_profile(reference,profiles,snapshot)
    c.need(len(set(identities))==len(identities),'duplicate Profile asset')


def check_parameter_refs(profile):
    """SV-12R/47 reference roles, independent of assumption truth or method enablement."""
    if common.check_method(profile)!='REEXEC_BOUNDED':return
    assumptions=profile['assumption_references']
    for owner,block,key,kind,role in [
        ('SV-12R','safety_parameters','support_capability_bound_ref','SUPPORT_CAPABILITY_BOUND','SAFETY_CRITICAL'),
        ('SV-47','liveness_parameters','calibration_ref','CALIBRATION','LIVENESS')]:
        reference=profile[block][key];r.identifier(reference,'ASSUMPTION')
        matches=[x for x in assumptions if x['assumption_id']==reference]
        c.need(len(matches)==1 and matches[0]['assumption_class']==kind and matches[0]['role']==role,
               owner+': missing, ambiguous or wrong assumption class/role')


def profile_admissible(profile,snapshot):
    check_snapshot(snapshot);p.verify_digest(profile);reference=profile_ref(profile)
    return any(row['object_kind']=='VERIFICATION_PROFILE' and all(row[k]==reference[k] for k in reference if k!='digest')
               and row['state'] in ('REGISTERED','ACTIVE') for row in snapshot['entries'])


def check_selected(slot,profile,snapshot):
    """SV-45: full slot/actual-object/snapshot identity, never a digest-only lookup."""
    check_snapshot(snapshot);p.verify_digest(profile);reference=profile_ref(profile)
    r.typed(slot['profile_ref'],'ProfileRef',None)
    c.need(c.reference_identity(slot['profile_ref'])==c.reference_identity(reference) and any(row['object_kind']=='VERIFICATION_PROFILE' and
        all(row[k]==reference[k] for k in reference if k!='digest') for row in snapshot['entries']),
        'SV-45: selected slot/actual Profile/snapshot mismatch')


def content_map(value,kind):
    c.need(kind in ('PolicyR7','EdgeR7','ManifestR7'),'asset kind')
    schema=EXTRA[kind];c.fields(value,schema['fields'],schema['optional']);h=value['header']
    c.fields(h,('schema_version','encoding_profile_id','id','version','digest'))
    return {k:h[k] for k in ('schema_version','encoding_profile_id')}|{k:v for k,v in value.items() if k!='header'}


def asset_digest(value,kind):
    tag={'PolicyR7':'SelectionPolicy','EdgeR7':'WeakeningEdge','ManifestR7':'Manifest'}[kind]
    return c.domain_hash('ACLt/P0-1/'+tag+'/1',c.encode(content_map(value,kind)))


def check_asset(value,kind,imports):
    typed(value,kind,imports);h=value['header'];c.need(h['schema_version']==1,'asset schema version')
    owner={'PolicyR7':'SV-53b','EdgeR7':'SV-88','ManifestR7':'SV-74'}[kind]
    c.need(c.digest_consistency(h['digest']==asset_digest(value,kind)),owner+': asset digest mismatch')


def check_edge(edge,profiles,snapshot,imports):
    check_asset(edge,'EdgeR7',imports)
    c.need(edge['edge_class']=='AUTO_DECIDABLE','SV-21: only AUTO_DECIDABLE edge accepted')
    source=resolve_profile(edge['source'],profiles,snapshot);target=resolve_profile(edge['target'],profiles,snapshot)
    c.need(source['verification_method']=='REEXEC_BOUNDED' and target['verification_method']=='REEXEC_AUDIT_ONLY',
           'SV-21: only bounded to audit automatic weakening')
    c.need('verified_claim_spec' not in target,'SV-21: target must omit claim in v2')
    c.need(set(source['excluded_claims']['exclusion_ids'])<=set(target['excluded_claims']['exclusion_ids']),
           'SV-21: target exclusions must contain source exclusions')
    for field in ('task_type','contract_tuple_constraints','result_equivalence'):
        c.need(c.encode(source[field])==c.encode(target[field]),'SV-21: different '+field)


def expand(candidates,profiles,snapshot):
    """D-06 position-indexed expansion; gate is copied per slot, never keyed by ID."""
    slots=[]
    for candidate in candidates:
        profile=resolve_profile(candidate['profile_ref'],profiles,snapshot)
        primary=dict(index=len(slots),profile_ref=candidate['profile_ref'],kind='PRIMARY',enabling_triggers=[])
        if 'gate' in candidate:primary['gate']=candidate['gate']
        slots.append(primary)
        if 'degradation' in profile:
            declaration=profile['degradation'];common.check_degradation(declaration)
            slots.append(dict(index=len(slots),profile_ref=declaration['target'],kind='DEGRADED',
                              degraded_from=primary['index'],enabling_triggers=declaration['triggers']))
    return slots


def check_policy(policy,profiles,snapshot,edges,imports):
    check_asset(policy,'PolicyR7',imports)
    slots=policy['expanded_slots'];indices=[x['index'] for x in slots]
    c.need(len(indices)==len(set(indices)),'SV-41: duplicate slot index')
    expected=expand(policy['ordered_candidates'],profiles,snapshot)
    c.need(c.encode(slots)==c.encode(expected),'SV-53a: expansion or per-slot gate mismatch')
    for edge in edges:check_edge(edge,profiles,snapshot,imports)
    # A declared degradation needs its actual target and the valid explicit edge.
    for candidate in policy['ordered_candidates']:
        source=resolve_profile(candidate['profile_ref'],profiles,snapshot)
        if 'degradation' not in source:continue
        target=source['degradation']['target'];resolve_profile(target,profiles,snapshot)
        matches=[e for e in edges if c.reference_identity(e['source'])==c.reference_identity(candidate['profile_ref']) and c.reference_identity(e['target'])==c.reference_identity(target)]
        c.need(len(matches)==1,'one explicit weakening edge required')
        check_edge(matches[0],profiles,snapshot,imports)


def check_manifest(manifest,imports):
    check_asset(manifest,'ManifestR7',imports)
    paths=[]
    for row in manifest['file_digests']:
        path=row['path']
        c.need(path and '\0' not in path and not path.startswith('/') and '\\' not in path and not re.match(r'^[A-Za-z]:',path),
               'SV-85: canonical relative POSIX path required')
        paths.append(path)
    c.need(paths==sorted(set(paths)),'SV-85: file paths order or duplicate')


def check_event_subject(event,imports):
    r.typed(event,'Event',imports);kind=event['event_kind'];subject=event['subject_ref']
    c.need(kind in r.SUBJECTS and subject['tag']==r.SUBJECTS[kind],'SV-120: event kind/subject tag')
    c.need(('schema_ref' in subject)==(kind=='OTHER'),'SV-120: subject fields')
    value=subject['id'];tag=subject['tag']
    if tag=='PHASE_I_RECORD':r.identifier(value,'PHASE_I_RECORD')
    elif tag=='CLUSTER_MAPPING':
        c.need(re.fullmatch(r'acl\.cmap\.'+r.ULID,c.text(value)) is not None,'SV-120: cluster ID')
    elif tag=='PHASE_F_CALL':imports.check('EventRef',value)
    elif tag=='RECEIPT':c.digest_bytes(value)
    else:c.text(value)


def authorized_slot(slot,authorized):
    """SV-23: considering a DEGRADED slot always requires explicit bool authorization."""
    c.need(type(authorized) is bool,'degradation authorization bool')
    c.need(type(slot) is dict and slot.get('kind') in ('PRIMARY','DEGRADED'),'slot kind')
    return slot['kind']=='PRIMARY' or authorized


def scope_contains(scope,declared,imports):
    """Frozen SC-1 comparator; declared is explicit adapter input, not normalized Intent."""
    r.typed(scope,'Scope',imports);typed(declared,'DeclaredScopeR7',imports)
    c.need(bool(declared['fault_domains']) and bool(declared['geography']),'SV-58: empty declared scope dimension')
    def in_range(point,interval):return interval[0]<=point and (1 not in interval or point<interval[1])
    return scope['task_class']==declared['task_class'] and scope['environment_class']==declared['environment_class'] and \
        in_range(declared['rir_version'],scope['rir_profile_range']) and in_range(declared['rpr_version'],scope['rpr_version_range']) and \
        set(declared['fault_domains'])<=set(scope['fault_domains']) and set(declared['geography'])<=set(scope['geography'])


def applicability(payload,imports):
    """Components with explicit TEST adapter facts; never infer fields of ReceiptIntent."""
    c.fields(payload,('profile','declared_scope','evaluation_instant','n_max','intent_effects','slot','degradation_authorized','source_failure_reasons'))
    profile=payload['profile'];method=common.check_method(profile);p.verify_digest(profile)
    common.check_assumptions(profile['assumption_references'],imports);method_rules.check_matrix(profile,imports);check_parameter_refs(profile)
    c.uint(payload['n_max']);r.typed(payload['evaluation_instant'],'int',imports)
    typed(payload['declared_scope'],'DeclaredScopeR7',imports)
    c.need(payload['declared_scope']['fault_domains'] and payload['declared_scope']['geography'],'SV-58: empty declared dimension')
    typed(payload['slot'],'SlotR7',imports)
    effects=payload['intent_effects'];c.need(type(effects) is list,'effects array')
    for effect in effects:imports.check('EffectID',effect)
    encoded=[c.encode(x) for x in effects];c.need(encoded==sorted(set(encoded)),'effects set order or duplicate')
    reasons=payload['source_failure_reasons'];c.need(type(reasons) is list and all(type(x) is str for x in reasons),'TEST failure reason labels')
    allowed=authorized_slot(payload['slot'],payload['degradation_authorized'])
    trigger_set=set(payload['slot']['enabling_triggers'])
    enabled=allowed and (payload['slot']['kind']=='PRIMARY' or (bool(reasons) and set(reasons)<=trigger_set))
    scopes=[]
    for assumption in profile['assumption_references']:
        if assumption['role'] in ('SAFETY_CRITICAL','LIVENESS'):
            scopes.append(scope_contains(assumption['scope'],payload['declared_scope'],imports))
    result=dict(degradation_authorized=allowed,test_slot_enabled=enabled,scope_covered=all(scopes),
                effects_covered=set(effects)<=set(profile['contract_tuple_constraints']['allowed_effects']))
    if method=='REEXEC_BOUNDED':
        reference=profile['safety_parameters']['support_capability_bound_ref']
        assumption=next(x for x in profile['assumption_references'] if x['assumption_id']==reference)
        window=assumption['validity_window'];r.typed(window,'wire-time-range',imports)
        result.update(bound_scope_window_ok=scope_contains(assumption['scope'],payload['declared_scope'],imports) and window[0]<=payload['evaluation_instant']<window[1],
                      required_draws_within_limit=profile['liveness_parameters']['n_required']<=payload['n_max'],
                      invalid_sample_limit_ok=profile['failure_mapping']['max_invalid_samples']<=payload['n_max'])
    return result


def inspect_components(raw,lock_pin):
    value=c.decode(raw);c.fields(value,('operation','payload','schema_lock','schema_documents'))
    imports=references.Imports(value['schema_lock'],value['schema_documents'],lock_pin)
    operation=value['operation'];payload=value['payload'];result={}
    if operation in ('policy','edge'):
        key=operation;c.fields(payload,(key,'profiles','registry_snapshot','edges') if key=='policy' else (key,'profiles','registry_snapshot'))
        check_profile_assets(payload['profiles'],payload['registry_snapshot'])
        if key=='policy':
            c.need(type(payload['edges']) is list,'edge assets array');check_policy(payload[key],payload['profiles'],payload['registry_snapshot'],payload['edges'],imports)
        else:check_edge(payload[key],payload['profiles'],payload['registry_snapshot'],imports)
        result['digest_hex']=payload[key]['header']['digest'].hex()
    elif operation=='manifest':
        c.fields(payload,('manifest',));check_manifest(payload['manifest'],imports);result['digest_hex']=payload['manifest']['header']['digest'].hex()
    elif operation=='profile-refs':
        c.fields(payload,('profile','registry_snapshot'));profile=payload['profile']
        common.check_rules(profile,payload['registry_snapshot'],imports);method_rules.check_matrix(profile,imports);check_parameter_refs(profile)
    elif operation=='profile-lookup':
        c.fields(payload,('profile','registry_snapshot','slot'));typed(payload['slot'],'SlotR7',imports)
        check_selected(payload['slot'],payload['profile'],payload['registry_snapshot'])
        result['admissible']=profile_admissible(payload['profile'],payload['registry_snapshot'])
    elif operation=='events':
        c.fields(payload,('events',));c.need(type(payload['events']) is list,'event array')
        for event in payload['events']:check_event_subject(event,imports)
        result['events']=len(payload['events'])
    elif operation=='applicability-test':result.update(applicability(payload,imports))
    else:raise c.CodecError('unknown registration asset operation')
    result.update(operation=operation,schema_lock_sha256=c.digest_record_hex(lock_pin),full_schema_valid=False,full_phase_i_replay=False,
                  source_authentication=False,production_admission=False)
    return result


def inspect(raw,lock_pin):
    try:
        return inspect_components(raw,lock_pin)
    except (KeyError,TypeError,IndexError,RecursionError) as exc:
        raise c.CodecError('malformed registration asset input') from exc
