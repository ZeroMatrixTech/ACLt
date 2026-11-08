# SPDX-License-Identifier: Apache-2.0
"""Selected common Phase R rules, independently callable for all four methods.

Passing these rules does not validate unexamined method parameters/claims,
register a Profile or establish the truth of an assumption.
"""
from tools.verification_profile import codec as c, profile as p, registration as r, references

SCOPE_FIELDS=frozenset(('task_class','rir_profile_range','rpr_version_range','environment_class','fault_domains','geography'))
REVOCATION_FIELDS=frozenset(('before_verification','during_verification','after_terminal'))
SAFE_REVOCATION=dict(before_verification='BLOCK_ADMISSION',during_verification='VERIFICATION_INVALIDATING',after_terminal='QUALIFY_REVOKED')
TRIGGERS=frozenset(('SUPPORT_CAPABILITY_BOUND_UNAVAILABLE','POPULATION_TOO_SMALL','CALIBRATION_OUT_OF_SCOPE'))
REQUIRED={
    'DIRECT_VERIFIED':frozenset({('PREDICATE_SOUNDNESS','SAFETY_CRITICAL')}),
    'PROOF_VERIFIED':frozenset({('PROOF_SYSTEM','SAFETY_CRITICAL')}),
    'REEXEC_BOUNDED':frozenset({(name,'SAFETY_CRITICAL') for name in (
        'SUPPORT_CAPABILITY_BOUND','RANDOMNESS','SNAPSHOT','CORRECTNESS_BRIDGE')}|{('CALIBRATION','LIVENESS')}),
    'REEXEC_AUDIT_ONLY':frozenset(),
}


def check_method(profile):
    c.need(type(profile) is dict,'Profile map')
    c.need('post_execution_predicate' not in profile,'SV-32: removed post_execution_predicate')
    method=profile.get('verification_method')
    c.need(type(method) is str and method in p.METHODS,'SV-03: verification method')
    return method


def check_assumptions(assumptions,imports):
    c.need(type(assumptions) is list,'assumption array')
    ids=[]
    for row in assumptions:
        c.need(type(row) is dict,'assumption object')
        mapping=row.get('revocation_mapping')
        c.need(type(mapping) is dict and set(mapping)==REVOCATION_FIELDS,'SV-33: three closed revocation stages required')
        scope=row.get('scope')
        c.need(type(scope) is dict and set(scope)==SCOPE_FIELDS,'SV-59: six closed scope dimensions required')
        if row.get('role')=='SAFETY_CRITICAL':
            c.need(mapping==SAFE_REVOCATION,'SV-37: safety-critical revocation mapping')
        r.typed(row,'ReferencesAssumption',imports)
        ids.append(row['assumption_id'])
    c.need(len(ids)==len(set(ids)),'SV-76: duplicate assumption ID')


def check_required(method,assumptions):
    present={(row['assumption_class'],row['role']) for row in assumptions}
    c.need(REQUIRED[method]<=present,'SV-38: required assumption class/role missing')


def check_degradation(declaration):
    c.fields(declaration,('target','triggers'))
    r.typed(declaration['target'],'ProfileRef',None)
    triggers=declaration['triggers']
    c.need(type(triggers) is list and all(type(x) is str and x in TRIGGERS for x in triggers),
           'SV-22: unknown degradation trigger')


def assumption_set_digest(assumptions):
    c.need(type(assumptions) is list,'assumption array')
    pairs=[]
    for row in assumptions:
        c.need(type(row) is dict and {'assumption_id','statement_digest'}<=row.keys(),'assumption digest fields')
        r.identifier(row['assumption_id'],'ASSUMPTION')
        c.digest_bytes(row['statement_digest'])
        pairs.append([row['assumption_id'],row['statement_digest']])
    return c.domain_hash('ACLt/P0-1/AssumptionSet/1',c.encode(sorted(pairs,key=c.encode)))


def check_rules(profile,snapshot,imports):
    method=check_method(profile)
    p.verify_digest(profile)
    assumptions=profile['assumption_references']
    check_assumptions(assumptions,imports)
    check_required(method,assumptions)
    r.typed(snapshot,'Registry',None)
    r.check_registry(snapshot)
    if 'supersedes' in profile:
        r.typed(profile['supersedes'],'ProfileRef',None)
        r.check_supersedes(profile,snapshot)
    if 'degradation' in profile:check_degradation(profile['degradation'])
    return dict(verification_method=method,assumptions=len(assumptions),
                assumption_set_digest_hex=assumption_set_digest(assumptions).hex(),
                full_schema_valid=False,source_authentication=False)


def inspect(raw,lock_pin):
    """Rule-only adapter; non-audit inputs do not enable other method paths."""
    value=c.decode(raw)
    c.fields(value,('profile','registry_snapshot','schema_lock','schema_documents','assumption_set_digest'))
    imports=references.Imports(value['schema_lock'],value['schema_documents'],lock_pin)
    output=check_rules(value['profile'],value['registry_snapshot'],imports)
    c.digest_bytes(value['assumption_set_digest'])
    c.need(value['assumption_set_digest'].hex()==output['assumption_set_digest_hex'],'SV-73: assumption set digest mismatch')
    return output


def inspect_audit(raw,lock_pin):
    value=c.decode(raw)
    c.fields(value,('envelope','schema_lock','schema_documents','registry_objects'))
    envelope=value['envelope']
    c.fields(envelope,('phase','bundle','object'))
    c.need(envelope['phase']=='R','Phase R envelope')
    c.fields(envelope['bundle'],('context','registry_snapshot','event_frontier_snapshot'))
    profile=envelope['object']
    check_method(profile)
    c.need(profile['verification_method']=='REEXEC_AUDIT_ONLY','audit-only integration scope')
    imports=references.Imports(value['schema_lock'],value['schema_documents'],lock_pin)
    common=check_rules(profile,value['envelope']['bundle']['registry_snapshot'],imports)
    c.need('degradation' not in profile,'fixed audit integration excludes degradation; use rule-only checks')
    output=references.inspect(raw,lock_pin)
    output.update(assumption_set_digest_hex=common['assumption_set_digest_hex'])
    return output
