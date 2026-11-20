// SPDX-License-Identifier: Apache-2.0
// Independent Profile v2 projection and selected Phase R checks.
// Nested schema/import and registry validation remain separate obligations.
use super::*;


const CONTENT: &[&str] = &[
    "schema_version", "encoding_profile_id", "supersedes", "task_type",
    "contract_tuple_constraints", "admission_predicate", "verified_claim_spec",
    "excluded_claims", "verification_method", "method_parameters", "result_equivalence",
    "safety_parameters", "liveness_parameters", "assumption_references",
    "failure_mapping", "decision_mapping", "degradation",
];
const OPTIONAL: &[&str] = &[
    "supersedes", "verified_claim_spec", "safety_parameters", "liveness_parameters", "degradation",
];
const IDENTITY_ADVISORY: &[&str] = &[
    "profile_id", "profile_version", "profile_digest", "cost_parameters", "documentation",
];
const METHODS: &[&str] = &["DIRECT_VERIFIED", "PROOF_VERIFIED", "REEXEC_BOUNDED", "REEXEC_AUDIT_ONLY"];
const CONDITIONS: &[&str] = &[
    "VERIFICATION_INVALIDATING", "ACCEPT", "REJECT_COMPLETE", "REJECT_SOUND_ONLY",
    "EXECUTION_FAILED", "BUDGET_EXHAUSTED", "DEADLINE_REACHED", "EVIDENCE_EXHAUSTED",
];
const AUDIT_CONDITIONS: &[&str] = &[
    "VERIFICATION_INVALIDATING", "EXECUTION_FAILED", "BUDGET_EXHAUSTED",
    "DEADLINE_REACHED", "EVIDENCE_EXHAUSTED",
];
const AUDIT_EVENTS: &[&str] = &[
    "POSITIVE", "NEGATIVE", "TIMEOUT", "RESOURCE_EXHAUSTED", "MALFORMED_SUBMISSION",
    "ENCODING_INVALID", "VERIFIER_CRASH", "VERIFIER_NONDETERMINISM_DETECTED",
    "OBJECT_UNAVAILABLE", "EPOCH_STALE", "ASSUMPTION_REVOKED", "EQUIVALENCE_UNDECIDED",
    "EQUIVALENCE_RESOURCE_EXCEEDED",
];

fn content(value: &V) -> R<V> {
    let rows = match value {
        V::M(rows) => rows,
        _ => return Err("Profile map".into()),
    };
    for (key, _) in rows {
        let key = txt(key)?;
        need(CONTENT.contains(&key) || IDENTITY_ADVISORY.contains(&key), "unknown Profile field")?;
    }
    for key in CONTENT.iter().filter(|key| !OPTIONAL.contains(key)).chain(IDENTITY_ADVISORY) {
        get(value, key)?;
    }
    need([1, 2].contains(&integer(get(value, "schema_version")?)?), "Profile schema version")?;
    need(txt(get(value, "encoding_profile_id")?)? == ENC, "encoding profile")?;
    txt(get(value, "profile_id")?)?;
    semver(get(value, "profile_version")?)?;
    dig(get(value, "profile_digest")?)?;
    need(METHODS.contains(&txt(get(value, "verification_method")?)?), "verification method")?;
    let mut selected = Vec::new();
    for key in CONTENT {
        if let Ok(field) = get(value, key) {
            selected.push((*key, field.clone()));
        }
    }
    Ok(map(selected))
}

fn strings(value: &V) -> R<Vec<&str>> {
    arr(value)?.iter().map(txt).collect()
}

pub(super) fn decision_fields(value: &V) -> R<()> {
    let decision = get(value, "decision_mapping")?;
    fields(decision, &["rules", "default"])?;
    let rules = strings(get(decision, "rules")?)?;
    need(rules.iter().all(|key| CONDITIONS.contains(key)), "DecisionCondition")?;
    need(txt(get(decision, "default")?)? == "UNRESOLVED", "decision default")?;
    let ordered: Vec<&str> = CONDITIONS.iter().copied().filter(|key| rules.contains(key)).collect();
    need(rules == ordered, "decision order or duplicate")?;
    if txt(get(value, "verification_method")?)? == "REEXEC_AUDIT_ONLY" {
        need(!rules.contains(&"ACCEPT"), "audit ACCEPT")?;
    }
    Ok(())
}

pub(super) fn audit_fields(value: &V) -> R<()> {
    need(integer(get(value, "schema_version")?)? == 2, "new audit requires schema v2")?;
    need(txt(get(value, "verification_method")?)? == "REEXEC_AUDIT_ONLY", "audit method")?;
    for key in ["verified_claim_spec", "safety_parameters", "liveness_parameters"] {
        need(get(value, key).is_err(), "audit forbidden block")?;
    }
    decision_fields(value)?;
    need(strings(get(get(value, "decision_mapping")?, "rules")?)? == AUDIT_CONDITIONS,
         "audit condition set")?;
    let params = get(value, "method_parameters")?;
    let keys = ["min_reexecutions", "evidence_retention", "reachable_terminals"];
    for key in keys {
        get(params, key)?;
    }
    let param_rows = match params {
        V::M(rows) => rows,
        _ => return Err("audit parameters".into()),
    };
    for (key, _) in param_rows {
        need(keys.contains(&txt(key)?) || txt(key)? == "audit_coverage_target", "audit parameter field")?;
    }
    uint(get(params, "min_reexecutions")?)?;
    if let Ok(target) = get(params, "audit_coverage_target") {
        project("rational", target, false)?;
    }
    let mut terminals = vec![s("UNRESOLVED"), s("FAILED"), s("EXPIRED"), s("FUNDING_EXHAUSTED")];
    let mut encoded: Vec<(Vec<u8>, V)> = terminals.drain(..)
        .map(|value| Ok((encode(&value)?, value))).collect::<R<_>>()?;
    encoded.sort_by(|a, b| a.0.cmp(&b.0));
    let terminals = V::A(encoded.into_iter().map(|(_, value)| value).collect());
    need(get(params, "reachable_terminals")? == &terminals, "reachable terminals")?;

    let mapping = get(value, "failure_mapping")?;
    fields(mapping, &["entries"])?;
    let mut events = Vec::new();
    for row in arr(get(mapping, "entries")?)? {
        fields(row, &["key", "value"])?;
        let event = txt(get(row, "key")?)?;
        need(AUDIT_EVENTS.contains(&event), "audit event")?;
        let outcome = get(row, "value")?;
        fields(outcome, &["outcome", "attribution"])?;
        need(["CONCORDANT", "DISCORDANT", "INCONCLUSIVE", "VERIFICATION_INVALIDATING"]
            .contains(&txt(get(outcome, "outcome")?)?), "audit outcome")?;
        need(["PROVIDER_FAULT", "VERIFIER_FAULT", "PLATFORM_FAULT", "REQUESTER_FAULT", "NO_ATTRIBUTION"]
            .contains(&txt(get(outcome, "attribution")?)?), "attribution")?;
        events.push(encode(&s(event))?);
    }
    let mut expected = AUDIT_EVENTS.iter().map(|key| encode(&s(key))).collect::<R<Vec<_>>>()?;
    expected.sort();
    need(events == expected, "audit events coverage, order or duplicate")
}

pub(super) fn run(mode: &str, input: &str) -> R<V> {
    let raw = unhex(input)?;
    let value = decode(&raw)?;
    let selected = content(&value)?;
    let content_raw = encode(&selected)?;
    let tag = if integer(get(&value, "schema_version")?)? == 1 {
        "ACLt/P0-1/Profile/1"
    } else {
        "ACLt/P0-1/Profile/2"
    };
    let digest = domain(tag, &content_raw);
    need(digest_consistency(bytes(get(&value, "profile_digest")?)? == digest), "DISABLED: profile digest consistency")?;
    match mode {
        "profile-decision" => decision_fields(&value)?,
        "audit-profile" => audit_fields(&value)?,
        _ => {}
    }
    Ok(map(vec![
        ("cbor_hex", s(&hex(&raw))),
        ("content_cbor_hex", s(&hex(&content_raw))),
        ("digest_hex", s(&hex(&digest))),
        ("sha_consistency_policy", s(SHA_CONSISTENCY_STATUS)),
    ]))
}
