// SPDX-License-Identifier: Apache-2.0
//! Independent Phase D replay for the explicitly pinned audit TEST contract.
use super::commitments::same;
use super::registration::{typed, Imports};
use super::runtime_bindings::{ancestors, event_is};
use super::*;
use std::collections::{BTreeMap, BTreeSet};

const INVALIDATING: &str = "VERIFICATION_INVALIDATING";
const EVALUATOR_ID: &str = "acl.evaluator.r10-audit-test";
const CLOSURE_ID: &str = "acl.closure.r10-execution-test";
const CLOSURE_DOMAIN: &str = "ACLt/TEST/R10/ExecutionClosure/1";
const REASON_DOMAIN: &str = "ACLt/TEST/R10/DecisionReason/1";

type Events = BTreeMap<Vec<u8>, V>;

fn contract_ref(identifier: &str) -> V {
    map(vec![
        ("id", s(identifier)),
        ("version", V::A(vec![V::N(1), V::N(0), V::N(0)])),
        ("digest", V::X(sha256::hash(identifier.as_bytes()))),
    ])
}

pub(super) fn resolve_boundary(observation: &V, events: &Events, visible: &BTreeSet<Vec<u8>>, receipt: &V)
    -> R<Option<&'static str>>
{
    let funding = get(observation, "funding_event_ref").ok();
    let deadline = get(observation, "deadline_event_ref").ok();
    for (reference, kind) in [(funding, "FUNDING_EXHAUSTED"), (deadline, "DEADLINE_REACHED")] {
        if let Some(reference) = reference {
            if !event_is(events, visible, reference, kind, "RECEIPT", receipt)? {
                return Ok(Some(INVALIDATING));
            }
        }
    }
    match (funding, deadline) {
        (None, None) => Ok(None),
        (None, Some(_)) => Ok(Some("DEADLINE_REACHED")),
        (Some(funding), Some(deadline))
            if ancestors(events, &encode(funding)?)?.contains(&encode(deadline)?) =>
        {
            Ok(Some("DEADLINE_REACHED"))
        }
        _ => Ok(Some("BUDGET_EXHAUSTED")),
    }
}

pub(super) fn execution_condition(observation: &V, receipt: &V, events: &Events,
                       visible: &BTreeSet<Vec<u8>>, admitted: i128) -> R<Option<&'static str>> {
    match txt(get(observation, "tag")?)? {
        "NOT_APPLICABLE" => {
            fields(observation, &["tag"])?;
            return Ok(None);
        }
        "SOURCE_UNAVAILABLE" => return Ok(Some(INVALIDATING)),
        "CLOSURE" => fields(observation, &["tag", "record"])?,
        _ => return Err("execution tag".into()),
    }
    let record = get(observation, "record")?;
    let committed = ["receipt_id", "execution_contract_ref", "attempts_observed",
                     "valid_submission_count", "recovery_exhausted_event"];
    fields(record, &["receipt_id", "execution_contract_ref", "attempts_observed",
                     "valid_submission_count", "recovery_exhausted_event", "closure_digest"])?;
    let attempts = get(record, "attempts_observed")?;
    let valid = get(record, "valid_submission_count")?;
    uint(attempts)?;
    uint(valid)?;
    need(integer(valid)? <= integer(attempts)?, "closure counts")?;
    need(get(record, "receipt_id")? == receipt &&
         same(get(record, "execution_contract_ref")?, &contract_ref(CLOSURE_ID))?, "closure binding")?;
    let mut projection = Vec::new();
    for key in committed {
        projection.push((key, get(record, key)?.clone()));
    }
    need(digest_consistency(bytes(get(record, "closure_digest")?)? == domain(CLOSURE_DOMAIN, &encode(&map(projection))?)),
         "closure digest")?;
    need(event_is(events, visible, get(record, "recovery_exhausted_event")?,
                  "EXECUTION_EXHAUSTED", "RECEIPT", receipt)?, "closure event")?;
    if integer(valid)? > 0 {
        return Ok(None);
    }
    need(admitted == 0, "contradictory closure")?;
    for key in visible {
        let row = events.get(key).ok_or("visible event missing")?;
        need(!event_is(events, visible, get(row, "event_ref")?,
                       "VERIFICATION_STARTED", "RECEIPT", receipt)?, "contradictory closure")?;
    }
    Ok(Some("EXECUTION_FAILED"))
}

fn aggregate(outcomes: &[V], concordant: i128, cost: i128) -> V {
    let admitted = outcomes.len() as i128;
    map(vec![
        ("admitted", V::N(admitted)),
        ("concordant", V::N(concordant)),
        ("discordant", V::N(admitted - concordant)),
        ("committed_cost", V::N(cost)),
    ])
}

pub(super) fn audit_evaluate(input: &V, deadline: i128, cap: i128, instant: i128) -> R<(Vec<V>, V)> {
    fields(input, &["expected_result", "evidence"])?;
    let expected = bytes(get(input, "expected_result")?)?;
    decode(expected)?;
    let mut attempts = BTreeSet::new();
    let mut outcomes = Vec::new();
    let mut concordant = 0;
    let mut committed = 0;
    let mut previous = i64::MIN as i128;
    for row in arr(get(input, "evidence")?)? {
        fields(row, &["attempt_id", "received_at", "cost", "validation_passed", "result"])?;
        let attempt = bytes(get(row, "attempt_id")?)?;
        need(!attempt.is_empty() && attempts.insert(attempt), "duplicate or invalid attempt")?;
        let received_at = integer(get(row, "received_at")?)?;
        need(received_at >= previous && received_at <= instant, "evidence instant order")?;
        previous = received_at;
        let cost = get(row, "cost")?;
        uint(cost)?;
        let cost = integer(cost)?;
        let V::B(validation_passed) = get(row, "validation_passed")? else {
            return Err("explicit validation result required".into());
        };
        let result = bytes(get(row, "result")?)?;
        if *validation_passed && received_at < deadline && cost <= cap - committed {
            decode(result)?;
            committed += cost;
            if result == expected {
                concordant += 1;
                outcomes.push(s("CONCORDANT"));
            } else {
                outcomes.push(s("DISCORDANT"));
            }
        }
    }
    let summary = aggregate(&outcomes, concordant, committed);
    Ok((outcomes, summary))
}

fn method_evaluation(method: &V, assurance: &V, imports: &Imports, deadline: i128,
                     cap: i128, instant: i128) -> R<(bool, i128)> {
    let reference = contract_ref(EVALUATOR_ID);
    let mut allowed = false;
    for candidate in arr(get(assurance, "allowed_validator_refs")?)? {
        allowed |= same(candidate, &reference)?;
    }
    if !same(get(method, "evaluator_ref")?, &reference)? || !allowed {
        return Ok((true, 0));
    }
    let schema = imports.native_schema().ok_or("audit TEST native schema")?;
    for name in ["canonical_input", "claimed_outcome", "claimed_aggregate"] {
        need(same_reference(get(get(method, name)?, "schema_ref")?,schema)?, "audit TEST native schema")?;
    }
    let payload = decode(bytes(get(get(method, "canonical_input")?, "canonical_bytes")?)?)?;
    let Ok((outcomes, aggregate)) = audit_evaluate(&payload, deadline, cap, instant) else {
        return Ok((true, 0));
    };
    let admitted = outcomes.len() as i128;
    need(bytes(get(get(method, "claimed_outcome")?, "canonical_bytes")?)? ==
             encode(&V::A(outcomes))? &&
         bytes(get(get(method, "claimed_aggregate")?, "canonical_bytes")?)? ==
             encode(&aggregate)?, "method replay mismatch")?;
    Ok((false, admitted))
}

fn assumption_invalid(profile: &V, state: &V, receipt: &V, assurance: &V, instant: &V,
                      types: &V, imports: &Imports) -> R<bool> {
    let Some(snapshot) = commitments::states(profile, state, types, imports)? else {
        return Ok(true);
    };
    need(get(snapshot, "receipt_id")? == receipt && get(snapshot, "evaluation_instant")? == instant &&
         get(snapshot, "reducer_ref")? == get(assurance, "assumption_verdict_reducer_ref")?,
         "assumption binding")?;
    let mut safety = BTreeSet::new();
    for row in arr(get(profile, "assumption_references")?)? {
        if txt(get(row, "role")?)? == "SAFETY_CRITICAL" {
            safety.insert(txt(get(row, "assumption_id")?)?);
        }
    }
    for row in arr(get(snapshot, "assumption_states")?)? {
        if safety.contains(txt(get(row, "assumption_id")?)?) &&
           txt(get(row, "effective_verdict")?)? != "VALID" {
            return Ok(true);
        }
    }
    Ok(false)
}

fn decision_record_projection(record:&V)->R<V>{
 let selected=get(record,"selected_condition").is_ok();
 fields(record,if selected{&["input_digest","condition_vector","derived_terminal","selected_condition"]}else{&["input_digest","condition_vector","derived_terminal"]})?;
 dig(get(record,"input_digest")?)?;
 let mut rows=Vec::new();
 for row in arr(get(record,"condition_vector")?)?{
  fields(row,&["condition","value","reason_digest"])?;dig(get(row,"reason_digest")?)?;txt(get(row,"condition")?)?;need(matches!(get(row,"value")?,V::B(_)),"condition boolean")?;
  rows.push(map(vec![("condition",get(row,"condition")?.clone()),("value",get(row,"value")?.clone())]));
 }
 let mut projected=vec![("condition_vector",V::A(rows)),("derived_terminal",get(record,"derived_terminal")?.clone())];
 if selected{projected.push(("selected_condition",get(record,"selected_condition")?.clone()));}
 Ok(map(projected))
}

pub(super) fn run(input: &str, lock: &str, contract_pin: &str) -> R<V> {
    let request = decode(&unhex(input)?)?;
    fields(&request, &["envelope", "schema_lock", "schema_documents", "decision_contract", "decision"])?;
    let imports = Imports::new_bindings(get(&request, "schema_lock")?,
                                       get(&request, "schema_documents")?, &unhex(lock)?)?;
    let types = commitments::types()?;
    let contract = get(&request, "decision_contract")?;
    let pin = unhex(contract_pin)?;
    fields(contract, &["name", "receipt_binding", "deadline", "funding_cap"])?;
    need(txt(get(contract, "name")?)? == "r10-audit-decision-test@1" &&
         digest_consistency(sha256::hash(&encode(contract)?) == pin), "decision contract pin")?;
    typed(get(contract, "deadline")?, &s("int"), &types, &imports)?;
    let cap = get(contract, "funding_cap")?;
    uint(cap)?;

    let envelope = get(&request, "envelope")?;
    fields(envelope, &["phase", "bundle", "profile", "evaluation_input"])?;
    need(txt(get(envelope, "phase")?)? == "D", "Phase D required")?;
    let profile = get(envelope, "profile")?;
    super::profile::run("profile-digest", &hex(&encode(profile)?))?;
    super::profile::audit_fields(profile)?;
    let equivalence = get(profile, "result_equivalence")?;
    need(txt(get(equivalence, "equivalence_id")?)? == "acl.eq.exact@1" &&
         txt(get(equivalence, "canonical_encoding_id")?)? == ENC &&
         txt(get(equivalence, "relation_kind")?)? == "CANONICAL_BITWISE" &&
         txt(get(equivalence, "totality")?)? == "TOTAL", "audit TEST exact equivalence")?;
    registration::rule_assumptions(get(profile, "assumption_references")?, &types, &imports)?;
    let data = get(envelope, "evaluation_input")?;
    let digest = commitments::decision_hash(data, &types, &imports)?;
    let assurance = get(data, "assurance_profile")?;
    commitments::digest_object(assurance, "MainnetAssuranceProfile", &types, &imports)?;
    let receipt = get(data, "receipt_binding")?;
    let receipt_id = get(receipt, "receipt_id")?;
    need(encode(receipt)? == encode(get(contract, "receipt_binding")?)? &&
         same_reference(get(receipt, "profile_ref")?,get(data, "profile_ref")?)? &&
         same_reference(get(data, "profile_ref")?, &commitments::pref(profile)?)? &&
         get(receipt, "network_id")? == get(assurance, "network_id")? &&
         same_reference(get(receipt, "assurance_profile_ref")?, &commitments::identity(assurance)?)?,
         "Receipt binding")?;

    let bundle = get(envelope, "bundle")?;
    typed(bundle, &s("ReferencesBundle"), &types, &imports)?;
    let registry = get(bundle, "registry_snapshot")?;
    registration::check_registry(registry)?;
    let context = get(bundle, "context")?;
    need(same_reference(get(context, "registry_snapshot_ref")?, &commitments::identity(registry)?)?, "registry context")?;
    let frontier = get(bundle, "event_frontier_snapshot")?;
    let header = get(frontier, "header")?;
    let frontier_hash = get(header, "digest")?;
    let frontier_ref = map(vec![("id", get(header, "id")?.clone()), ("digest", frontier_hash.clone())]);
    need(digest_consistency(bytes(frontier_hash)? == registration::frontier_digest(frontier)?) &&
         same_reference(get(context, "event_frontier_ref")?, &frontier_ref)?, "frontier commitment")?;

    let instant = get(context, "evaluation_instant")?;
    let (method_invalid, admitted) = method_evaluation(
        get(data, "method_evaluation")?, assurance, &imports,
        integer(get(contract, "deadline")?)?, integer(cap)?, integer(instant)?)?;
    let assumption_invalid = assumption_invalid(profile, get(data, "assumption_evaluation")?,
                                                receipt_id, assurance, instant, &types, &imports)?;
    let mut boundary = Some(INVALIDATING);
    let mut execution = None;
    if registration::check_frontier(frontier, &imports).is_ok() {
        let mut events = Events::new();
        for row in arr(get(frontier, "event_records")?)? {
            events.insert(encode(get(row, "event_ref")?)?, row.clone());
        }
        let visible = ancestors(&events, &encode(get(frontier, "frontier_event_ref")?)?)?;
        boundary = resolve_boundary(get(data, "boundary_observation")?, &events, &visible, receipt_id)?;
        execution = execution_condition(get(data, "execution_observation")?, receipt_id,
                                        &events, &visible, admitted).unwrap_or(Some(INVALIDATING));
    }
    let invalidating = method_invalid || assumption_invalid ||
                       boundary == Some(INVALIDATING) || execution == Some(INVALIDATING);
    let minimum = integer(get(get(profile, "method_parameters")?, "min_reexecutions")?)?;
    need(minimum > 0, "audit TEST minimum must be positive")?;
    let mapping = get(profile, "decision_mapping")?;
    let mut vector = Vec::new();
    let mut winner = None;
    for rule in arr(get(mapping, "rules")?)? {
        let condition = txt(rule)?;
        let value = match condition {
            INVALIDATING => invalidating,
            "EXECUTION_FAILED" => execution == Some(condition),
            "BUDGET_EXHAUSTED" | "DEADLINE_REACHED" => boundary == Some(condition),
            "EVIDENCE_EXHAUSTED" => winner.is_none() && admitted >= minimum,
            _ => return Err("unexpected audit condition".into()),
        };
        if value && winner.is_none() {
            winner = Some(condition);
        }
        let reason = domain(REASON_DOMAIN, &encode(&V::A(vec![
            V::X(digest.clone()), frontier_hash.clone(), V::X(pin.clone()), instant.clone(),
            rule.clone(), V::B(value),
        ]))?);
        vector.push(map(vec![("condition", rule.clone()), ("value", V::B(value)), ("reason_digest", V::X(reason))]));
    }
    let terminal = match winner {
        Some("EXECUTION_FAILED") => "FAILED",
        Some("BUDGET_EXHAUSTED") => "FUNDING_EXHAUSTED",
        Some("DEADLINE_REACHED") => "EXPIRED",
        Some(_) => "UNRESOLVED",
        None => txt(get(mapping, "default")?)?,
    };
    let mut record = vec![("input_digest", V::X(digest)),
                          ("condition_vector", V::A(vector)), ("derived_terminal", s(terminal))];
    if let Some(condition) = winner {
        record.push(("selected_condition", s(condition)));
    }
    let expected_record = map(record);
    let expected = encode(&expected_record)?;
    let decision = get(&request, "decision")?;
    fields(decision, &["evaluation_record", "terminal_state"])?;
    need(encode(&decision_record_projection(get(decision, "evaluation_record")?)?)? == encode(&decision_record_projection(&expected_record)?)? &&
         txt(get(decision, "terminal_state")?)? == terminal, "decision replay mismatch")?;
    Ok(map(vec![
        ("record_sha256", s(&hex(&sha256::hash(&expected)))),
        ("terminal", s(terminal)),
        ("selected_condition", s(winner.unwrap_or(""))),
        ("production_admission", V::B(false)),
        ("state_committed", V::B(false)),
    ]))
}
