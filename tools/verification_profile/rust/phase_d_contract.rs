// SPDX-License-Identifier: Apache-2.0
//! Read-only replay of externally authenticated R11 projections in the R12 format.
use super::decision_replay::{audit_evaluate, execution_condition, resolve_boundary};
use super::runtime_bindings::ancestors;
use super::*;
use std::collections::BTreeMap;

const VERSION: &str = "ACLt/PhaseD/Candidate/1";
const SOURCE: &str = "ACLt/TEST/R11/PhaseDSource/1";
const INVALIDATING: &str = "VERIFICATION_INVALIDATING";
const RULES: [(&str, &str); 5] = [
    (INVALIDATING, "UNRESOLVED"),
    ("EXECUTION_FAILED", "FAILED"),
    ("BUDGET_EXHAUSTED", "FUNDING_EXHAUSTED"),
    ("DEADLINE_REACHED", "EXPIRED"),
    ("EVIDENCE_EXHAUSTED", "UNRESOLVED"),
];

fn digest(kind: &str, value: &V) -> R<V> {
    Ok(V::X(domain(&format!("{VERSION}/{kind}"), &encode(value)?)))
}

fn unsigned(value: &V, name: &str) -> R<i128> {
    let n = get(value, name)?;
    uint(n)?;
    integer(n)
}

fn bound_digest(value: &V, name: &str) -> R<V> {
    let value = get(value, name)?;
    need(bytes(value)?.len() == 32, "digest length")?;
    Ok(value.clone())
}

fn project(source: &V, deployment: Vec<u8>) -> R<V> {
    fields(source, &["genesis", "cutoff_seq", "cutoff_head", "pre_state_digest", "projection"])?;
    let evidence = get(source, "projection")?;
    let receipt = bound_digest(evidence, "receipt")?;
    let head = bound_digest(source, "cutoff_head")?;
    let cutoff = unsigned(source, "cutoff_seq")?;
    let instant = unsigned(evidence, "instant")?;
    let deadline = unsigned(evidence, "deadline")?;
    let cap = unsigned(evidence, "funding_cap")?;
    let minimum = unsigned(evidence, "minimum_accepted_results")?;
    need(minimum == 2, "audit candidate minimum")?;

    let frontier = get(evidence, "projected_frontier")?;
    let observations = get(evidence, "boundary")?;
    let boundary_keys: Vec<_> = ["funding_event_ref", "deadline_event_ref"].into_iter()
        .filter(|key| get(observations, key).is_ok()).collect();
    fields(observations, &boundary_keys)?;
    let deadline_ref = get(observations, "deadline_event_ref").ok();
    need(deadline_ref.is_some() == (instant >= deadline), "deadline presence")?;
    let method_input = get(evidence, "method_input")?;
    let (outcomes, aggregate) = audit_evaluate(method_input, deadline, cap, instant)?;
    need(encode(&aggregate)? == encode(get(evidence, "aggregate")?)? &&
         outcomes.len() == arr(get(method_input, "evidence")?)?.len(), "legacy aggregate mismatch")?;

    let records = arr(get(frontier, "event_records")?)?;
    need(records.len() as i128 == cutoff + i128::from(deadline_ref.is_some()) && cutoff > 0,
         "frontier length")?;
    let mut events = BTreeMap::new();
    let mut parent = None;
    for record in records {
        let parents = arr(get(record, "parent_refs")?)?;
        need(parents.len() == usize::from(parent.is_some()) && parents.first() == parent,
             "linear frontier")?;
        let reference = get(record, "event_ref")?;
        need(events.insert(encode(reference)?, record.clone()).is_none(), "duplicate frontier reference")?;
        parent = Some(reference);
    }
    let frontier_head = get(frontier, "frontier_event_ref")?;
    need(parent == Some(frontier_head) &&
         get(&records[usize::try_from(cutoff - 1).map_err(|_| "cutoff length")?], "event_ref")? == &head &&
         deadline_ref.is_none_or(|reference| reference == frontier_head), "frontier head binding")?;
    let visible = ancestors(&events, &encode(frontier_head)?)?;
    let boundary = resolve_boundary(observations, &events, &visible, &receipt)?;

    let causes = get(evidence, "causes")?;
    let cause_names = arr(causes)?.iter().map(txt).collect::<R<Vec<_>>>()?;
    let mut expected_causes = Vec::new();
    if cause_names.contains(&"TEST_SOURCE_REVOKED") {
        expected_causes.push("TEST_SOURCE_REVOKED");
    }
    if !arr(get(evidence, "unknown_starts")?)?.is_empty() {
        expected_causes.push("START_UNDETERMINED");
    }
    if boundary == Some(INVALIDATING) {
        expected_causes.push("BOUNDARY_UNRESOLVED");
    }
    need(cause_names == expected_causes, "invalidating causes")?;

    let context = map(vec![
        ("deployment_digest", V::X(deployment)),
        ("receipt_id", receipt.clone()),
        ("profile_digest", bound_digest(evidence, "profile")?),
        ("log_id", bound_digest(source, "genesis")?),
        ("cutoff_seq", V::N(cutoff)),
        ("cutoff_head", head),
        ("cutoff_state_digest", bound_digest(source, "pre_state_digest")?),
    ]);
    let mut input = vec![
        ("context", context.clone()),
        ("evaluated_at", V::N(instant)),
        ("deadline", V::N(deadline)),
        ("funding_cap", V::N(cap)),
        ("method_input", method_input.clone()),
        ("minimum_accepted_results", V::N(minimum)),
        ("invalidating_causes", causes.clone()),
    ];
    if let Ok(funding) = get(observations, "funding_event_ref") {
        input.push(("funding_event_ref", funding.clone()));
    }
    if deadline_ref.is_some() {
        input.push(("deadline_observation_ref", digest(
            "DeadlineObservation", &V::A(vec![context.clone(), V::N(deadline), V::N(instant)]),
        )?));
    }
    let observation = get(evidence, "execution_observation")?;
    let execution = execution_condition(observation, &receipt, &events, &visible, outcomes.len() as i128)?;
    if let Ok(closure) = get(evidence, "execution_closure") {
        let attempts = unsigned(closure, "attempts_observed")?;
        let valid = unsigned(closure, "valid_submission_count")?;
        let event = bound_digest(evidence, "closure_event")?;
        let record = get(observation, "record")?;
        need(unsigned(record, "attempts_observed")? == attempts &&
             unsigned(record, "valid_submission_count")? == valid &&
             get(record, "recovery_exhausted_event")? == &event, "legacy closure binding")?;
        let mut body = vec![
            ("context", context),
            ("source_contract", s("ACLt/PhaseD/Candidate/1/FM-S3Observer")),
            ("attempts_observed", V::N(attempts)),
            ("valid_submission_count", V::N(valid)),
            ("recovery_exhausted_event", event),
        ];
        body.push(("closure_digest", digest("ExecutionClosure", &map(body.clone()))?));
        input.push(("execution_closure", map(body)));
    } else {
        need(txt(get(observation, "tag")?)? == "NOT_APPLICABLE", "missing closure source")?;
    }

    let input = map(input);
    let input_digest = digest("EvaluationInput", &input)?;
    let legacy_conditions = get(evidence, "conditions")?;
    fields(legacy_conditions, &RULES.map(|(name, _)| name))?;
    let mut vector = Vec::new();
    let mut winner = None;
    for (condition, terminal) in RULES {
        let value = match condition {
            INVALIDATING => !cause_names.is_empty() || execution == Some(INVALIDATING),
            "EXECUTION_FAILED" => execution == Some(condition),
            "EVIDENCE_EXHAUSTED" => winner.is_none() && outcomes.len() as i128 >= minimum,
            _ => boundary == Some(condition),
        };
        need(get(legacy_conditions, condition)? == &V::B(value), "legacy condition mismatch")?;
        if value && winner.is_none() {
            winner = Some((condition, terminal));
        }
        let reason = digest("DecisionReason", &V::A(vec![input_digest.clone(), s(condition), V::B(value)]))?;
        vector.push(map(vec![("condition", s(condition)), ("value", V::B(value)), ("reason_digest", reason)]));
    }
    let (condition, terminal) = winner.ok_or("audit evidence still open")?;
    Ok(map(vec![
        ("version", s(VERSION)),
        ("evaluation_input", input),
        ("input_digest", input_digest),
        ("condition_vector", V::A(vector)),
        ("selected_condition", s(condition)),
        ("derived_terminal", s(terminal)),
    ]))
}

pub(super) fn run(input: &str, pins: &str) -> R<V> {
    let (deployment, source_pin) = pins.split_once(':').ok_or("two candidate pins required")?;
    let deployment = unhex(deployment)?;
    let source_pin = unhex(source_pin)?;
    need(deployment.len() == 32 && source_pin.len() == 32, "candidate pin length")?;
    let request = decode(&unhex(input)?)?;
    fields(&request, &["source", "candidate"])?;
    let source = bytes(get(&request, "source")?)?;
    need(domain(SOURCE, source) == source_pin, "legacy source pin mismatch")?;
    let raw = encode(&project(&decode(source)?, deployment)?)?;
    need(raw == bytes(get(&request, "candidate")?)?, "candidate bytes differ from authenticated replay")?;
    Ok(map(vec![("candidate_cbor_hex", s(&hex(&raw)))]))
}
