// SPDX-License-Identifier: Apache-2.0
// Independent frozen method matrices and scoped audit R5 integration.
use super::*;
use super::registration::{Imports, typed, common_rules};
use std::collections::BTreeSet;

const METHODS: &[&str] = &["DIRECT_VERIFIED", "PROOF_VERIFIED", "REEXEC_BOUNDED", "REEXEC_AUDIT_ONLY"];
const CONDITIONS: &[&str] = &["VERIFICATION_INVALIDATING", "ACCEPT", "REJECT_COMPLETE", "REJECT_SOUND_ONLY",
    "EXECUTION_FAILED", "BUDGET_EXHAUSTED", "DEADLINE_REACHED", "EVIDENCE_EXHAUSTED"];
const ATTRIBUTIONS: &[&str] = &["PROVIDER_FAULT", "VERIFIER_FAULT", "PLATFORM_FAULT", "REQUESTER_FAULT", "NO_ATTRIBUTION"];
fn rows(value: &V) -> R<&[(V,V)]> { if let V::M(v)=value { Ok(v) } else { Err("map".into()) } }
fn boolean(value: &V) -> R<bool> { if let V::B(v)=value { Ok(*v) } else { Err("bool".into()) } }
fn catalogue() -> R<V> {
    let base=parse_json(include_str!("audit_types.json"))?;
    let extra=parse_json(include_str!("method_types.json"))?;
    let mut result=rows(&base)?.to_vec();
    for (key,value) in rows(&extra)? {
        need(get_key(&base,key).is_err(),"duplicate type name")?;
        result.push((key.clone(),value.clone()));
    }
    Ok(V::M(result))
}
fn method(value: &V) -> R<&str> {
    let name=txt(get(value,"verification_method")?)?;
    need(METHODS.contains(&name),"method")?;Ok(name)
}
fn outcomes(name: &str) -> &'static [&'static str] {
    match name {
        "DIRECT_VERIFIED" => &["ACCEPT","REJECT","INCONCLUSIVE","VERIFICATION_INVALIDATING"],
        "PROOF_VERIFIED" => &["PROOF_ACCEPTED","PROOF_REJECTED","INCONCLUSIVE","VERIFICATION_INVALIDATING"],
        "REEXEC_BOUNDED" => &["SUPPORT","NON_SUPPORT","INVALID_SAMPLE","VERIFICATION_INVALIDATING"],
        _ => &["CONCORDANT","DISCORDANT","INCONCLUSIVE","VERIFICATION_INVALIDATING"],
    }
}
fn check_parameters(profile: &V, imports: &Imports, types: &V) -> R<()> {
    let name=method(profile)?;need(integer(get(profile,"schema_version")?)?==2,"R5 requires Profile v2")?;
    let params=get(profile,"method_parameters")?;rows(params)?;
    if name=="REEXEC_BOUNDED" {
        for key in ["safety_parameters","liveness_parameters"] {
            let block=get(profile,key).map_err(|_| "SV-31: bounded parameter block required")?;
            need(!rows(block)?.is_empty(),"SV-31: nonempty bounded parameter block required")?;
        }
        let q=txt(get(get(profile,"liveness_parameters")?,"q_source")?)?;
        need(["ANCHORED_IN_CLASS","FAULT_INJECTED_IN_CLASS"].contains(&q),"SV-13: q_source")?;
        typed(get(profile,"safety_parameters")?,&s("SafetyR5"),types,imports)?;
        typed(get(profile,"liveness_parameters")?,&s("LivenessR5"),types,imports)?;
    } else {
        need(get(profile,"safety_parameters").is_err() && get(profile,"liveness_parameters").is_err(),"SV-31: forbidden blocks")?;
    }
    if name=="DIRECT_VERIFIED" {
        need(txt(get(params,"determinism")?)?=="DETERMINISTIC" && arr(get(params,"effects")?)?.is_empty(),"SV-16: deterministic no-effects")?;
    }
    let kind=match name { "DIRECT_VERIFIED"=>"DirectParamsR5", "PROOF_VERIFIED"=>"ProofParamsR5", "REEXEC_BOUNDED"=>"BoundedParamsR5", _=>"AuditParams" };
    typed(params,&s(kind),types,imports)?;
    if name=="DIRECT_VERIFIED" {
        need(integer(get(params,"verifier_replication_min")?)?>=1,"direct verifier replication minimum")?;
        need(txt(get(params,"soundness_class")?)?!="SOUND" || txt(get(params,"reject_attribution")?)?=="NO_ATTRIBUTION","SV-09: sound-only rejection attribution")?;
    }
    if name=="REEXEC_BOUNDED" {
        let mut previous=None;
        for row in arr(get(params,"mixture_weights")?)? {
            let m=integer(get(row,"m")?)?;
            let weight=arr(get(row,"weight")?)?;
            if integer(&weight[0])?>0 {
                let q=integer(get(get(profile,"liveness_parameters")?,"Q")?)?;
                let g=integer(get(get(profile,"safety_parameters")?,"G")?)?;
                need(q<=m&&m<=g,"SV-11: supported m outside Q..G")?;
            }
            if let Some(last)=previous { need(last<m,"mixture m order or duplicate")?; }
            previous=Some(m);
        }
    }
    Ok(())
}
fn events(profile: &V) -> R<Vec<&'static str>> {
    let name=method(profile)?;
    let mut result=vec!["POSITIVE","NEGATIVE","TIMEOUT","RESOURCE_EXHAUSTED","MALFORMED_SUBMISSION","ENCODING_INVALID",
        "VERIFIER_CRASH","VERIFIER_NONDETERMINISM_DETECTED","OBJECT_UNAVAILABLE","EPOCH_STALE","ASSUMPTION_REVOKED"];
    match name {
        "DIRECT_VERIFIED" => {
            result.push("PREDICATE_UNDECIDED");
            if boolean(get(get(profile,"method_parameters")?,"certificate_required")?)? {result.push("CERTIFICATE_ABSENT");}
        },
        "PROOF_VERIFIED" => result.push("PROOF_ABSENT"),
        _ => {result.extend(["EQUIVALENCE_UNDECIDED","EQUIVALENCE_RESOURCE_EXCEEDED"]);
            if name=="REEXEC_BOUNDED" {result.extend(["SNAPSHOT_DIGEST_MISMATCH","RANDOMNESS_COMMITMENT_INVALID"]);}}
    }
    let mut encoded=result.into_iter().map(|key|Ok((encode(&s(key))?,key))).collect::<R<Vec<_>>>()?;
    encoded.sort_by(|a,b|a.0.cmp(&b.0));Ok(encoded.into_iter().map(|(_,key)|key).collect())
}
fn check_failure(profile: &V) -> R<()> {
    let name=method(profile)?;let mapping=get(profile,"failure_mapping")?;let bounded=name=="REEXEC_BOUNDED";
    if bounded { uint(get(mapping,"max_invalid_samples").map_err(|_| "SV-29R: max_invalid_samples required")?)?; }
    fields(mapping,if bounded {&["entries","max_invalid_samples"]}else{&["entries"]})?;
    let field=if bounded {"evidence_class"}else{"outcome"};let mut keys=vec![];
    for row in arr(get(mapping,"entries")?)? {
        fields(row,&["key","value"])?;let event=txt(get(row,"key")?)?;keys.push(event);
        let value=get(row,"value")?;fields(value,&[field,"attribution"])?;
        let outcome=txt(get(value,field)?)?;
        need(outcomes(name).contains(&outcome),"SV-19: wrong outcome variant")?;
        need(ATTRIBUTIONS.contains(&txt(get(value,"attribution")?)?),"SV-19: attribution")?;
        if name=="DIRECT_VERIFIED" && event=="PREDICATE_UNDECIDED" {need(outcome=="INCONCLUSIVE","direct UNDECIDED maps to INCONCLUSIVE")?;}
    }
    need(keys==events(profile)?,"SV-18: exact method event set/order")
}
fn conditions(profile: &V) -> R<Vec<&'static str>> {
    let name=method(profile)?;
    let reject=if name=="DIRECT_VERIFIED" {
        if txt(get(get(profile,"method_parameters")?,"soundness_class")?)?=="SOUND_AND_COMPLETE" {"REJECT_COMPLETE"}else{"REJECT_SOUND_ONLY"}
    }else if name=="PROOF_VERIFIED" {"REJECT_SOUND_ONLY"}else{""};
    Ok(CONDITIONS.iter().copied().filter(|key|match *key {"ACCEPT"=>name!="REEXEC_AUDIT_ONLY", "REJECT_COMPLETE"|"REJECT_SOUND_ONLY"=>*key==reject, _=>true}).collect())
}
fn terminal(condition: &str) -> &'static str {
    match condition {"ACCEPT"=>"TRUSTED","EXECUTION_FAILED"=>"FAILED","BUDGET_EXHAUSTED"=>"FUNDING_EXHAUSTED","DEADLINE_REACHED"=>"EXPIRED",_=>"UNRESOLVED"}
}
fn check_matrix(profile: &V,imports: &Imports,types: &V,claimed: Option<&V>) -> R<V> {
    check_parameters(profile,imports,types)?;check_failure(profile)?;profile::decision_fields(profile)?;
    let actual=arr(get(get(profile,"decision_mapping")?,"rules")?)?.iter().map(txt).collect::<R<Vec<_>>>()?;
    need(actual.contains(&"EXECUTION_FAILED"),"SV-51: EXECUTION_FAILED required")?;
    let expected=conditions(profile)?;need(actual==expected,"SV-20: exact method condition set")?;
    let mut set=BTreeSet::new();set.insert("UNRESOLVED");for key in &actual {set.insert(terminal(key));}
    let mut encoded=set.into_iter().map(|key|Ok((encode(&s(key))?,s(key)))).collect::<R<Vec<_>>>()?;
    encoded.sort_by(|a,b|a.0.cmp(&b.0));let reachable=V::A(encoded.into_iter().map(|(_,value)|value).collect());
    if method(profile)?=="REEXEC_AUDIT_ONLY" {need(encode(get(get(profile,"method_parameters")?,"reachable_terminals")?)?==encode(&reachable)?,"SV-64: audit reachable terminals")?;}
    if let Some(claimed)=claimed {need(encode(claimed)?==encode(&reachable)?,"SV-64: adapter reachable terminals")?;}
    Ok(map(vec![("verification_method",s(method(profile)?)),("events",V::N(events(profile)?.len()as i128)),
        ("conditions",V::A(expected.into_iter().map(s).collect())),("reachable_terminals",reachable),
        ("full_schema_valid",V::B(false)),("source_authentication",V::B(false))]))
}
pub(super) fn run(input: &str,pin: &str,audit: bool) -> R<V> {
    let value=decode(&unhex(input)?)?;let types=catalogue()?;
    let imports=Imports::new_mode(get(&value,"schema_lock")?,get(&value,"schema_documents")?,&unhex(pin)?,true)?;
    if audit {
        fields(&value,&["envelope","schema_lock","schema_documents","registry_objects"])?;
        let envelope=get(&value,"envelope")?;fields(envelope,&["phase","bundle","object"])?;
        let profile=get(envelope,"object")?;need(method(profile)?=="REEXEC_AUDIT_ONLY","fixed audit R5 scope")?;
        profile::run("profile-digest",&hex(&encode(profile)?))?;
        let matrix=check_matrix(profile,&imports,&types,None)?;
        let common=registration::run_rules(input,pin,true)?;
        merge(&common,&matrix)
    } else {
        fields(&value,&["profile","registry_snapshot","schema_lock","schema_documents","assumption_set_digest","reachable_terminals"])?;
        let profile=get(&value,"profile")?;
        let common=common_rules(profile,get(&value,"registry_snapshot")?,&types,&imports)?;
        dig(get(&value,"assumption_set_digest")?)?;
        need(digest_consistency(txt(get(&common,"assumption_set_digest_hex")?)?==hex(bytes(get(&value,"assumption_set_digest")?)?)),"SV-73: assumption set digest")?;
        let matrix=check_matrix(profile,&imports,&types,Some(get(&value,"reachable_terminals")?))?;
        merge(&common,&matrix)
    }
}
fn merge(a: &V,b: &V) -> R<V> {
    let mut output=rows(a)?.iter().filter(|(key,_)|get_key(b,key).is_err()).cloned().collect::<Vec<_>>();
    output.extend_from_slice(rows(b)?);Ok(V::M(output))
}
pub(super) fn project(input: &str) -> R<V> {
    let value=decode(&unhex(input)?)?;let name=method(&value)?;
    let mut keys=vec!["verification_method","outcome","aggregate_exhausted"];
    if name=="DIRECT_VERIFIED" {keys.push("soundness_class");}
    if name=="REEXEC_BOUNDED" {keys.extend(["threshold_met","null_bound_exactly_exceeded"]);}
    fields(&value,&keys)?;let exhausted=boolean(get(&value,"aggregate_exhausted")?)?;
    let outcome=txt(get(&value,"outcome")?)?;
    need(outcomes(name).contains(&outcome)||(name=="REEXEC_BOUNDED"&&outcome=="NULL_BOUND_EXACTLY_EXCEEDED"),"method outcome")?;
    let sound=if name=="DIRECT_VERIFIED" {let s=txt(get(&value,"soundness_class")?)?;need(["SOUND","SOUND_AND_COMPLETE"].contains(&s),"soundness")?;s}else{""};
    let threshold=if name=="REEXEC_BOUNDED" {boolean(get(&value,"threshold_met")?)?}else{false};
    let null_bound=if name=="REEXEC_BOUNDED" {boolean(get(&value,"null_bound_exactly_exceeded")?)?}else{false};
    let condition=if outcome=="VERIFICATION_INVALIDATING" {Some("VERIFICATION_INVALIDATING")}
    else if name=="DIRECT_VERIFIED"&&outcome=="ACCEPT" {Some("ACCEPT")}
    else if name=="DIRECT_VERIFIED"&&outcome=="REJECT" {Some(if sound=="SOUND_AND_COMPLETE"{"REJECT_COMPLETE"}else{"REJECT_SOUND_ONLY"})}
    else if name=="PROOF_VERIFIED"&&outcome=="PROOF_ACCEPTED" {Some("ACCEPT")}
    else if name=="PROOF_VERIFIED"&&outcome=="PROOF_REJECTED" {Some("REJECT_SOUND_ONLY")}
    else if name=="REEXEC_BOUNDED"&&(threshold||null_bound||outcome=="NULL_BOUND_EXACTLY_EXCEEDED") {Some("ACCEPT")}
    else if exhausted {Some("EVIDENCE_EXHAUSTED")}else{None};
    Ok(if let Some(condition)=condition {map(vec![("condition_present",V::B(true)),("condition",s(condition))])}else{map(vec![("condition_present",V::B(false))])})
}

pub(super) fn asset_rules(profile:&V,snapshot:&V,imports:&Imports)->R<()> {
 let types=catalogue()?;common_rules(profile,snapshot,&types,imports)?;check_matrix(profile,imports,&types,None)?;Ok(())
}

pub(super) fn asset_input(profile:&V,imports:&Imports)->R<()> {
 let types=catalogue()?;super::registration::rule_assumptions(get(profile,"assumption_references")?,&types,imports)?;
 check_matrix(profile,imports,&types,None)?;Ok(())
}
