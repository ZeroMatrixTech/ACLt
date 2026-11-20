# SPDX-License-Identifier: Apache-2.0
"""Profile v2 L2 digest and selected audit registration checks.

Digest inputs are already typed canonical CBOR. Nested schema/import validity,
registry authorization and the remaining Phase R checks are separate obligations.
"""
from tools.verification_profile import codec as c

TAGS = {1: 'ACLt/P0-1/Profile/1', 2: 'ACLt/P0-1/Profile/2'}
METHODS = ('DIRECT_VERIFIED', 'PROOF_VERIFIED', 'REEXEC_BOUNDED', 'REEXEC_AUDIT_ONLY')
CONTENT_FIELDS = (
    'schema_version', 'encoding_profile_id', 'supersedes', 'task_type',
    'contract_tuple_constraints', 'admission_predicate', 'verified_claim_spec',
    'excluded_claims', 'verification_method', 'method_parameters', 'result_equivalence',
    'safety_parameters', 'liveness_parameters', 'assumption_references',
    'failure_mapping', 'decision_mapping', 'degradation',
)
OPTIONAL_FIELDS = {'supersedes', 'verified_claim_spec', 'safety_parameters',
                   'liveness_parameters', 'degradation'}
REQUIRED_FIELDS = (set(CONTENT_FIELDS) - OPTIONAL_FIELDS) | {
    'profile_id', 'profile_version', 'profile_digest', 'cost_parameters', 'documentation',
}
CONDITIONS = (
    'VERIFICATION_INVALIDATING', 'ACCEPT', 'REJECT_COMPLETE', 'REJECT_SOUND_ONLY',
    'EXECUTION_FAILED', 'BUDGET_EXHAUSTED', 'DEADLINE_REACHED', 'EVIDENCE_EXHAUSTED',
)
TERMINALS = dict(zip(CONDITIONS, (
    'UNRESOLVED', 'TRUSTED', 'UNRESOLVED', 'UNRESOLVED',
    'FAILED', 'FUNDING_EXHAUSTED', 'EXPIRED', 'UNRESOLVED',
)))
AUDIT_CONDITIONS = tuple(x for x in CONDITIONS if x not in ('ACCEPT', 'REJECT_COMPLETE', 'REJECT_SOUND_ONLY'))
AUDIT_EVENTS = (
    'POSITIVE', 'NEGATIVE', 'TIMEOUT', 'RESOURCE_EXHAUSTED', 'MALFORMED_SUBMISSION',
    'ENCODING_INVALID', 'VERIFIER_CRASH', 'VERIFIER_NONDETERMINISM_DETECTED',
    'OBJECT_UNAVAILABLE', 'EPOCH_STALE', 'ASSUMPTION_REVOKED', 'EQUIVALENCE_UNDECIDED',
    'EQUIVALENCE_RESOURCE_EXCEEDED',
)
AUDIT_OUTCOMES = ('CONCORDANT', 'DISCORDANT', 'INCONCLUSIVE', 'VERIFICATION_INVALIDATING')
ATTRIBUTIONS = ('PROVIDER_FAULT', 'VERIFIER_FAULT', 'PLATFORM_FAULT', 'REQUESTER_FAULT', 'NO_ATTRIBUTION')


def content_map(profile):
    """UVP-1V projection for every Profile v2 method, independent of nested semantics."""
    c.fields(profile, REQUIRED_FIELDS, OPTIONAL_FIELDS)
    c.need(type(profile['schema_version']) is int and profile['schema_version'] in TAGS,
           'SV-01: unsupported Profile schema')
    c.need(profile['encoding_profile_id'] == c.ENCODING, 'SV-25: encoding profile')
    c.need(type(profile['profile_id']) is str, 'SV-01: profile identity')
    c.semver(profile['profile_version'])
    c.digest_bytes(profile['profile_digest'])
    c.need(profile['verification_method'] in METHODS, 'SV-03: verification method')
    # Values retain their native CBOR types. Identity/advisory fields are excluded
    # by the closed projection table, and optional absent fields stay absent.
    return {key: profile[key] for key in CONTENT_FIELDS if key in profile}


def profile_digest(profile):
    content = content_map(profile)
    return c.domain_hash(TAGS[profile['schema_version']], c.encode(content))


def verify_digest(profile):
    expected = profile_digest(profile)
    c.need(c.digest_consistency(profile['profile_digest'] == expected), 'DISABLED: SV-02 profile digest consistency')


def decision_fields(profile):
    """SV-63 and SV-39 for all four methods, plus the conditional SV-17."""
    decision = profile['decision_mapping']
    c.fields(decision, ('rules', 'default'))
    rules = decision['rules']
    c.need(type(rules) is list and all(type(x) is str and x in CONDITIONS for x in rules),
           'SV-63: DecisionCondition array')
    c.need(decision['default'] == 'UNRESOLVED', 'SV-39: default')
    c.need(rules == [x for x in CONDITIONS if x in rules], 'SV-39: order or duplicate')
    if profile['verification_method'] == 'REEXEC_AUDIT_ONLY':
        c.need('ACCEPT' not in rules, 'SV-17: audit ACCEPT condition')


def audit_fields(profile):
    """Selected audit R checks; opaque imported fields are not dereferenced."""
    c.need(profile['schema_version'] == 2, 'SV-01: new audit checks require schema v2')
    c.need(profile['verification_method'] == 'REEXEC_AUDIT_ONLY', 'audit method required')
    c.need('verified_claim_spec' not in profile, 'SV-30: audit claim must be absent')
    c.need('safety_parameters' not in profile and 'liveness_parameters' not in profile,
           'SV-31: audit parameter blocks must be absent')
    decision_fields(profile)
    c.need(profile['decision_mapping']['rules'] == list(AUDIT_CONDITIONS),
           'SV-20: audit condition set')
    params = profile['method_parameters']
    c.fields(params, ('min_reexecutions', 'evidence_retention', 'reachable_terminals'),
             ('audit_coverage_target',))
    c.uint(params['min_reexecutions'])
    if 'audit_coverage_target' in params:
        c.project(params['audit_coverage_target'], c.SCHEMAS['rational'])
    reachable = sorted({TERMINALS[x] for x in AUDIT_CONDITIONS}, key=c.encode)
    c.need(params['reachable_terminals'] == reachable, 'SV-64: reachable terminals')
    mapping = profile['failure_mapping']
    c.fields(mapping, ('entries',))
    rows = mapping['entries']
    c.need(type(rows) is list, 'SV-19: failure entries')
    for row in rows:
        c.fields(row, ('key', 'value'))
        c.need(type(row['key']) is str and row['key'] in AUDIT_EVENTS, 'SV-18: audit event')
        c.fields(row['value'], ('outcome', 'attribution'))
        c.need(row['value']['outcome'] in AUDIT_OUTCOMES, 'SV-19: audit outcome')
        c.need(row['value']['attribution'] in ATTRIBUTIONS, 'SV-19: attribution')
    c.need([row['key'] for row in rows] == sorted(AUDIT_EVENTS, key=c.encode),
           'SV-18: event coverage, order or duplicate')


def inspect(kind, raw):
    c.need(kind in ('profile-digest', 'profile-decision', 'audit-profile'), 'profile check kind')
    profile = c.decode(raw)
    content = content_map(profile)
    verify_digest(profile)
    if kind == 'profile-decision':
        decision_fields(profile)
    elif kind == 'audit-profile':
        audit_fields(profile)
    return dict(cbor_hex=raw.hex(), content_cbor_hex=c.encode(content).hex(),
                digest_hex=profile_digest(profile).hex(), sha_consistency_policy=c.SHA_CONSISTENCY_STATUS)
