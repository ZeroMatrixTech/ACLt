// SPDX-License-Identifier: Apache-2.0
// Independent frozen commitments, Claim binding components and candidate inputs.
use super::*;
use super::registration::{Imports,typed};
use std::collections::BTreeSet;
const REDUCER_SOURCE:&[u8]=b"ACLt R8 reference: REVOKED > OUT_OF_SCOPE > WINDOW_EXPIRED > VALID; full cause set retained.";
fn rows(v:&V)->R<&[(V,V)]>{if let V::M(a)=v{Ok(a)}else{Err("map".into())}}
fn same(a:&V,b:&V)->R<bool>{Ok(encode(a)?==encode(b)?)}
fn types()->R<V>{
 let mut result=vec![];
 for data in [include_str!("audit_types.json"),include_str!("creation_types.json"),include_str!("selection_types.json"),include_str!("method_types.json"),include_str!("binding_types.json")]{
  let next=parse_json(data)?;for (k,v) in rows(&next)?{need(!result.iter().any(|(x,_)|x==k),"duplicate binding type")?;result.push((k.clone(),v.clone()));}
 }Ok(V::M(result))
}
fn verify(p:&V)->R<()>{profile::run("profile-digest",&hex(&encode(p)?))?;Ok(())}
fn pref(p:&V)->R<V>{Ok(map(vec![("id",get(p,"profile_id")?.clone()),("version",get(p,"profile_version")?.clone()),("digest",get(p,"profile_digest")?.clone())]))}
fn identity(v:&V)->R<V>{let h=get(v,"header")?;Ok(map(["id","version","digest"].iter().map(|k|Ok((*k,get(h,k)?.clone()))).collect::<R<_>>()?))}
fn runtime_identity(v:&V)->R<V>{let h=get(v,"header")?;Ok(map(vec![("id",get(h,"id")?.clone()),("digest",get(h,"digest")?.clone())]))}
fn sorted_rows(v:&V,key:&str)->R<()>{let mut prior=None;for row in arr(v)?{let code=encode(get(row,key)?)?;if let Some(last)=prior{need(last<code,"pair-array order/duplicate")?;}prior=Some(code);}Ok(())}
fn keyset(v:&V,key:&str)->R<BTreeSet<Vec<u8>>>{arr(v)?.iter().map(|x|encode(get(x,key)?)).collect()}
fn external(v:&V,i:&Imports)->R<V>{i.external_object(v)?;decode(bytes(get(v,"canonical_bytes")?)?)}
fn reducer()->V{map(vec![("id",s("acl.reducer.r8-default")),("version",V::A(vec![V::N(1),V::N(0),V::N(0)])),("digest",V::X(sha256::hash(REDUCER_SOURCE)))])}
fn projection(v:&V,kind:&str)->R<V>{
 let h=get(v,"header")?;let runtime=runtime_type(kind).is_ok();
 fields(h,if runtime{&["schema_version","encoding_profile_id","id","digest"]}else{&["schema_version","encoding_profile_id","id","version","digest"]})?;
 let mut out=vec![(s("schema_version"),get(h,"schema_version")?.clone()),(s("encoding_profile_id"),get(h,"encoding_profile_id")?.clone())];
 if runtime{out.push((s("id"),get(h,"id")?.clone()));}
 for (k,x) in rows(v)?{if !["header","translations","human_summary"].contains(&txt(k)?){out.push((k.clone(),x.clone()));}}Ok(V::M(out))
}
fn digest_object(v:&V,kind:&str,t:&V,i:&Imports)->R<()>{
 let schema=match kind{"ClaimTemplate"=>"TemplateR8","AssumptionStateSnapshot"=>"StateSnapshotR8","MainnetAssuranceProfile"=>"AssuranceR8",_=>return Err("object kind".into())};
 typed(v,&s(schema),t,i)?;let h=get(v,"header")?;need(integer(get(h,"schema_version")?)?==1,"object schema version")?;
 need(bytes(get(h,"digest")?)?==domain(&format!("ACLt/P0-1/{kind}/1"),&encode(&projection(v,kind)?)?),"object digest mismatch")
}
fn state_hash(v:&V)->R<Vec<u8>>{
 let mut keyed=arr(get(v,"assumption_states")?)?.iter().map(|x|Ok((encode(get(x,"assumption_id")?)?,x.clone()))).collect::<R<Vec<_>>>()?;keyed.sort_by(|a,b|a.0.cmp(&b.0));let rows=keyed.into_iter().map(|(_,v)|v).collect();
 Ok(domain("ACLt/P0-1/AssumptionState/1",&encode(&V::A(vec![get(v,"reducer_ref")?.clone(),V::A(rows)]))?))
}
fn claim_hash(reference:&V,bindings:&V)->R<Vec<u8>>{Ok(domain("ACLt/P0-1/RenderedClaim/1",&encode(&V::A(vec![reference.clone(),bindings.clone()]))?))}
fn decision_hash(v:&V,t:&V,i:&Imports)->R<Vec<u8>>{typed(v,&s("DecisionInputR8"),t,i)?;Ok(domain("ACLt/P0-1/DecisionEvaluationInput/1",&encode(v)?))}
fn method_exclusions(p:&V)->R<()>{
 let method=txt(get(p,"verification_method")?)?;let ids=arr(get(get(p,"excluded_claims")?,"exclusion_ids")?)?;
 let required:&[&str]=match method{"DIRECT_VERIFIED"=>&["EXC-SPEC-PREDICATE-FIT","EXC-IMPL-VALIDATOR"],"PROOF_VERIFIED"=>&["EXC-IMPL-VALIDATOR","EXC-PROOF-SYSTEM","EXC-PROOF-STATEMENT-FIT"],"REEXEC_BOUNDED"=>&["EXC-STAT-BOUND-SOURCE","EXC-STAT-CALIBRATION"],"REEXEC_AUDIT_ONLY"=>&[],_=>return Err("method".into())};
 need(required.iter().all(|x|ids.contains(&s(x))),"SV-09: method exclusions")?;
 if method=="DIRECT_VERIFIED"{let params=get(p,"method_parameters")?;if txt(get(params,"soundness_class")?)?=="SOUND"{need(txt(get(params,"reject_attribution")?)?=="NO_ATTRIBUTION","SV-09: SOUND attribution")?;}}Ok(())
}
fn static_values(p:&V)->R<V>{
 let params=get(p,"method_parameters")?;
 Ok(match txt(get(p,"verification_method")?)?{
  "DIRECT_VERIFIED"=>map(["predicate_ref","soundness_class","validator_ref"].iter().map(|k|Ok((*k,get(params,k)?.clone()))).collect::<R<_>>()?),
  "PROOF_VERIFIED"=>map(vec![("proof_system_ref",get(params,"proof_system_ref")?.clone()),("params_ref",get(params,"public_params_ref")?.clone()),("statement_binding_rule",get(params,"statement_binding_rule")?.clone()),("verifier_ref",get(params,"verifier_ref")?.clone())]),
  "REEXEC_BOUNDED"=>map(vec![("equivalence_id",get(get(p,"result_equivalence")?,"equivalence_id")?.clone()),("algorithm_id",get(params,"algorithm_id")?.clone()),("profile_id",get(p,"profile_id")?.clone()),("profile_version",get(p,"profile_version")?.clone()),("assumption_set_digest",V::X(registration::assumption_set_digest(get(p,"assumption_references")?)?))]),
  _=>map(vec![]),
 })
}
fn range_slots(p:&V)->R<BTreeSet<String>>{
 let mut out=BTreeSet::new();let constraints=get(p,"contract_tuple_constraints")?;
 for (field,slot) in [("protocol_version_range","protocol_version"),("rir_version_range","rir_version"),("runtime_profile_version_range","rpr_profile_version"),("frontend_profile_version_range","frontend_profile_version")]{if get(constraints,field).is_ok(){out.insert(slot.into());}}
 if let Ok(live)=get(p,"liveness_parameters"){for field in ["calibration_rir_profile","calibration_rpr_version"]{if get(live,field).is_ok(){out.insert(field.into());}}}
 if !arr(get(p,"assumption_references")?)?.is_empty(){out.insert("rir_version".into());out.insert("rpr_profile_version".into());}Ok(out)
}
fn spec(p:&V,template:Option<&V>,snapshot:&V,t:&V,i:&Imports)->R<()>{
 verify(p)?;let method=txt(get(p,"verification_method")?)?;
 if method=="REEXEC_AUDIT_ONLY"{return need(get(p,"verified_claim_spec").is_err(),"SV-30: audit omit claim");}
 let v=get(p,"verified_claim_spec")?;typed(v,&s("ClaimSpecR8"),t,i)?;let reference=get(v,"claim_template_ref")?;
 let expected=match method{"DIRECT_VERIFIED"=>"acl.ct.direct-predicate","PROOF_VERIFIED"=>"acl.ct.proof-statement","REEXEC_BOUNDED"=>"acl.ct.reexec-canonical",_=>return Err("method".into())};
 need(txt(get(reference,"id")?)?==expected,"SV-05: method/template ID")?;
 let template=template.ok_or("template object required")?;digest_object(template,"ClaimTemplate",t,i)?;
 typed(snapshot,&s("Registry"),t,i)?;registration::check_registry(snapshot)?;let actual=identity(template)?;let mut found=false;
 for row in arr(get(snapshot,"entries")?)?{if txt(get(row,"object_kind")?)?=="CLAIM_TEMPLATE"&&["id","version","digest"].iter().all(|k|get(row,k).ok()==get(&actual,k).ok())&&["REGISTERED","ACTIVE"].contains(&txt(get(row,"state")?)?){found=true;}}
 need(same(reference,&actual)?&&found,"SV-48: template binding/state")?;
 sorted_rows(get(template,"slot_decls")?,"slot")?;sorted_rows(get(template,"translations")?,"lang")?;sorted_rows(get(v,"binding_schema")?,"slot")?;sorted_rows(get(v,"static_bindings")?,"slot")?;
 let declared=get(template,"slot_decls")?;let schema=get(v,"binding_schema")?;
 need(same(declared,schema)?,"SV-06: template/schema declarations")?;let ranges=range_slots(p)?;let mut static_keys=BTreeSet::new();
 for row in arr(schema)?{
  let name=txt(get(row,"slot")?)?;let decl=get(row,"decl")?;let kind=txt(get(decl,"kind")?)?;let source=txt(get(decl,"source")?)?;
  need(!name.is_empty()&&((kind=="STATIC"&&source=="PROFILE")||(kind=="RUNTIME"&&["RECEIPT","EVIDENCE_CHAIN","SNAPSHOT"].contains(&source))),"slot source/kind")?;
  if ranges.contains(name){need(kind=="RUNTIME","SV-49: version range slot")?;}if kind=="STATIC"{static_keys.insert(encode(get(row,"slot")?)?);}
 }
 let bindings=get(v,"static_bindings")?;need(keyset(bindings,"slot")?==static_keys,"SV-06: static keys")?;let expected=static_values(p)?;
 for row in arr(bindings)?{
  let name=txt(get(row,"slot")?)?;let source=get(&expected,name).map_err(|_|"SV-44: unknown frozen field")?;
  need(same(&external(get(row,"value")?,i)?,source)?,"SV-44: STATIC field value")?;
 }Ok(())
}
fn concrete(p:&V,template:&V,registry:&V,bindings:&V,t:&V,i:&Imports)->R<()>{
 spec(p,Some(template),registry,t,i)?;for row in arr(bindings)?{typed(row,&s("ConcreteRowR8"),t,i)?;}sorted_rows(bindings,"slot_id")?;
 let v=get(p,"verified_claim_spec")?;need(keyset(bindings,"slot_id")?==keyset(get(v,"binding_schema")?,"slot")?,"SV-35: concrete keys")?;
 for row in arr(get(v,"static_bindings")?)?{
  let actual=arr(bindings)?.iter().find(|x|get(x,"slot_id").ok()==get(row,"slot").ok()).ok_or("missing concrete STATIC")?;
  need(same(get(actual,"value")?,get(row,"value")?)?,"SV-35: STATIC concrete changed")?;
 }Ok(())
}
fn states<'a>(p:&V,result:&'a V,t:&V,i:&Imports)->R<Option<&'a V>>{
 verify(p)?;let tag=txt(get(result,"tag")?)?;
 if tag=="INVALIDATING"{fields(result,&["tag","failure"])?;typed(get(result,"failure")?,&s("AssumptionFailureR8"),t,i)?;return Ok(None);}
 need(tag=="COMPLETE","SV-116: result tag")?;fields(result,&["tag","snapshot"])?;let snapshot=get(result,"snapshot")?;digest_object(snapshot,"AssumptionStateSnapshot",t,i)?;
 need(same(get(snapshot,"reducer_ref")?,&reducer())?,"unsupported assumption reducer contract")?;
 let assumptions=get(p,"assumption_references")?;registration::rule_assumptions(assumptions,t,i)?;let mut required=BTreeSet::new();
 for row in arr(assumptions)?{if ["SAFETY_CRITICAL","LIVENESS"].contains(&txt(get(row,"role")?)?){required.insert(encode(get(row,"assumption_id")?)?);}}
 let data=get(snapshot,"assumption_states")?;sorted_rows(data,"assumption_id")?;need(keyset(data,"assumption_id")?==required,"SV-54a: coverage")?;
 for row in arr(data)?{
  let source=arr(assumptions)?.iter().find(|x|get(x,"assumption_id").ok()==get(row,"assumption_id").ok()).ok_or("missing assumption")?;
  need(same(get(row,"evidence_ref")?,get(source,"evidence_ref")?)?&&same(get(row,"evidence_version")?,get(source,"evidence_version")?)?,"state evidence binding")?;
  let causes=get(row,"cause_set")?;sorted_rows(causes,"cause_code")?;
  let mut verdict="VALID";for code in ["REVOKED","OUT_OF_SCOPE","WINDOW_EXPIRED"]{if arr(causes)?.iter().any(|x|get(x,"cause_code").ok()==Some(&s(code))){verdict=code;break;}}
  need(txt(get(row,"effective_verdict")?)?==verdict,"SV-54a: reducer")?;
 }Ok(Some(snapshot))
}
fn claim_guard(v:&V,t:&V,i:&Imports)->R<()>{
 typed(v,&map(vec![("fields",map(vec![("profile",s("native")),("registry_snapshot",s("Registry")),("receipt_id",s("digest")),("terminal_state",s("text")),("assumption_result",s("native"))])),("optional",map(vec![("template",s("TemplateR8")),("claim_binding",s("ClaimBindingR8")),("assurance_profile",s("AssuranceR8"))]))]),t,i)?;
 let p=get(v,"profile")?;verify(p)?;let terminal=txt(get(v,"terminal_state")?)?;need(["TRUSTED","UNRESOLVED","FAILED","EXPIRED","FUNDING_EXHAUSTED"].contains(&terminal),"terminal enum")?;
 let snapshot=states(p,get(v,"assumption_result")?,t,i)?;let binding=get(v,"claim_binding").ok();
 if terminal=="TRUSTED"{
  need(txt(get(p,"verification_method")?)?!="REEXEC_AUDIT_ONLY"&&binding.is_some(),"SV-36: complete non-audit binding required")?;
  let snap=snapshot.ok_or("SV-57: COMPLETE required")?;let data=arr(get(snap,"assumption_states")?)?;
  for a in arr(get(p,"assumption_references")?)?{if txt(get(a,"role")?)?=="SAFETY_CRITICAL"{let state=data.iter().find(|x|get(x,"assumption_id").ok()==get(a,"assumption_id").ok()).ok_or("missing safety state")?;need(txt(get(state,"effective_verdict")?)?=="VALID","SV-57: safety verdict")?;}}
 }
 let Some(b)=binding else{return Ok(());};need(txt(get(p,"verification_method")?)?!="REEXEC_AUDIT_ONLY","audit has no ClaimBinding")?;typed(b,&s("ClaimBindingR8"),t,i)?;
 concrete(p,get(v,"template")?,get(v,"registry_snapshot")?,get(b,"concrete_bindings")?,t,i)?;let cs=get(p,"verified_claim_spec")?;
 need(same(get(b,"claim_spec_id")?,get(cs,"claim_spec_id")?)?&&same(get(b,"claim_template_ref")?,get(cs,"claim_template_ref")?)?&&same(get(b,"profile_ref")?,&pref(p)?)?&&same(get(b,"verification_method")?,get(p,"verification_method")?)?,"Claim/Profile identity")?;
 need(bytes(get(b,"rendered_claim_digest")?)?==claim_hash(get(b,"claim_template_ref")?,get(b,"concrete_bindings")?)?,"SV-46: rendered claim digest")?;
 let snapshot=snapshot.ok_or("SV-78: snapshot required")?;
 need(same(get(snapshot,"receipt_id")?,get(v,"receipt_id")?)?&&same(get(b,"assumption_state_snapshot_ref")?,&runtime_identity(snapshot)?)?,"SV-78: Receipt/snapshot binding")?;
 need(bytes(get(b,"assumption_state_digest")?)?==state_hash(snapshot)?,"SV-54b: state digest")?;need(bytes(get(b,"assumption_set_digest")?)?==registration::assumption_set_digest(get(p,"assumption_references")?)?,"assumption set digest")?;
 let exclusions=get(p,"excluded_claims")?;
 for (key,source) in [("excluded_claims_registry_ref","registry_ref"),("excluded_claims_ids","exclusion_ids"),("excluded_claims_digest","digest")]{need(same(get(b,key)?,get(exclusions,source)?)?,"claim exclusion binding")?;}
 let assurance=get(v,"assurance_profile")?;digest_object(assurance,"MainnetAssuranceProfile",t,i)?;
 need(same(get(b,"network_id")?,get(assurance,"network_id")?)?&&same(get(b,"assurance_profile_ref")?,&identity(assurance)?)?&&same(get(b,"assurance_boundary_digest")?,get(get(assurance,"header")?,"digest")?)?&&same(get(snapshot,"reducer_ref")?,get(assurance,"assumption_verdict_reducer_ref")?)?,"assurance boundary binding")?;
 let bounded=txt(get(p,"verification_method")?)?=="REEXEC_BOUNDED";need(get(b,"algorithm_id").is_ok()==bounded&&get(b,"snapshot_digest").is_ok()==bounded,"method claim fields")?;
 if bounded{need(same(get(b,"algorithm_id")?,get(get(p,"method_parameters")?,"algorithm_id")?)?,"claim algorithm")?;}Ok(())
}
fn runtime_type(kind:&str)->R<(&'static str,&'static str)>{Ok(match kind{"AssumptionStateSnapshot"=>("StateSnapshotR8","ASSUMPTION_SNAPSHOT"),"CreationValidationContext"=>("CreationContext","CREATION_CONTEXT"),"PhaseIValidationRecord"=>("PhaseIRecord","PHASE_I_RECORD"),"EventFrontierSnapshot"=>("ReferencesFrontier","FRONTIER"),_=>return Err("runtime kind".into())})}
fn wire(kind:&str,v:&V,t:&V,i:&Imports)->R<()>{
 if kind=="VerificationProfile"{return verify(v);}
 let schema=match kind{"ClaimTemplate"=>"TemplateR8","ProfileSelectionPolicy"=>"PolicyR7","ConformanceManifest"=>"ManifestR7","RegistrySnapshot"=>"Registry","WeakeningEdge"=>"EdgeR7","ExcludedClaimsRegistry"=>"ExclusionRegistry","MainnetAssuranceProfile"=>"AssuranceR8",_=>runtime_type(kind)?.0};
 typed(v,&s(schema),t,i)?;let h=get(v,"header")?;let runtime=runtime_type(kind).is_ok();fields(h,if runtime{&["schema_version","encoding_profile_id","id","digest"]}else{&["schema_version","encoding_profile_id","id","version","digest"]})?;
 for key in ["id","version","digest"]{need(get(v,key).is_err(),"SV-86c: duplicate identity")?;}
 if runtime{let content=projection(v,kind)?;need(same(get(&content,"id")?,get(h,"id")?)?,"SV-86b: runtime ID")?;}Ok(())
}
fn runtime_ref(kind:&str,v:&V,t:&V,i:&Imports)->R<()>{let (_,id)=runtime_type(kind)?;fields(v,&["id","digest"])?;typed(get(v,"id")?,&map(vec![("identifier",s(id))]),t,i)?;dig(get(v,"digest")?)}
fn candidate(v:&V,t:&V,i:&Imports)->R<V>{
 typed(v,&s("CandidateIntentR8"),t,i)?;let base=get(v,"base_intent")?;need(integer(get(base,"schema_version")?)?==1,"candidate wraps Intent v1")?;
 need(get(base,"profile_ref").is_ok()!=get(base,"selection_policy_ref").is_ok(),"RI-1 selector")?;
 for key in ["fault_domains","geography"]{need(!arr(get(v,key)?)?.is_empty(),"candidate empty scope")?;}
 let contract=get(v,"contract_tuple")?;need(bytes(get(base,"contract_tuple")?)?==encode(contract)?,"candidate/base contract bytes mismatch")?;
 let scope=map(vec![("task_class",get(v,"task_type")?.clone()),("rir_version",get(contract,"rir_version")?.clone()),("rpr_version",get(contract,"rpr_version")?.clone()),("environment_class",get(v,"environment_class")?.clone()),("fault_domains",get(v,"fault_domains")?.clone()),("geography",get(v,"geography")?.clone())]);
 Ok(map(vec![("candidate_digest_hex",s(&hex(&domain("ACLt/TEST/R8/AdmissionInput/1",&encode(v)?)))),("base_intent_digest_hex",s(&hex(&domain("ACLt/P0-1/ReceiptIntent/1",&encode(base)?)))),("declared_scope_cbor_hex",s(&hex(&encode(&scope)?))),("effects_cbor_hex",s(&hex(&encode(get(contract,"allowed_effects")?)?))),("n_max_decimal",s(&integer(get(v,"n_max")?)?.to_string())),("normative_intent_upgrade",V::B(false))]))
}
pub(super) fn run(input:&str,pin:&str)->R<V>{
 let value=decode(&unhex(input)?)?;fields(&value,&["operation","payload","schema_lock","schema_documents"])?;let i=Imports::new_bindings(get(&value,"schema_lock")?,get(&value,"schema_documents")?,&unhex(pin)?)?;let t=types()?;let op=txt(get(&value,"operation")?)?;let v=get(&value,"payload")?;let mut out=vec![];
 match op{
  "registration"=>{
   let allowed=map(vec![("fields",map(vec![("profile",s("native")),("registry_snapshot",s("Registry")),("exclusion_registry",s("ExclusionRegistry"))])),("optional",map(vec![("template",s("TemplateR8"))]))]);typed(v,&allowed,&t,&i)?;
   let p=get(v,"profile")?;registration::common_rules(p,get(v,"registry_snapshot")?,&t,&i)?;method_rules::asset_input(p,&i)?;
   super::selection::parameter_refs(p)?;let excluded=map(vec![("selection",get(p,"excluded_claims")?.clone()),("registry",get(v,"exclusion_registry")?.clone()),("registry_snapshot",get(v,"registry_snapshot")?.clone())]);registration::run_excluded(&hex(&encode(&excluded)?))?;method_exclusions(p)?;spec(p,get(v,"template").ok(),get(v,"registry_snapshot")?,&t,&i)?;
  },
  "claim-guard"=>claim_guard(v,&t,&i)?,
  "state"=>{typed(v,&map(vec![("fields",map(vec![("profile",s("native")),("result",s("native"))])),("optional",map(vec![("assumption_state_digest",s("digest"))]))]),&t,&i)?;if let Some(snap)=states(get(v,"profile")?,get(v,"result")?,&t,&i)?{need(bytes(get(v,"assumption_state_digest")?)?==state_hash(snap)?,"SV-54b: state digest")?;out.push(("snapshot_digest_hex",s(&hex(bytes(get(get(snap,"header")?,"digest")?)?))));}else{need(get(v,"assumption_state_digest").is_err(),"INVALIDATING must not fabricate state digest")?;}},
  "template-digest"|"assurance-digest"=>{fields(v,&["object"])?;let kind=if op=="template-digest"{"ClaimTemplate"}else{"MainnetAssuranceProfile"};digest_object(get(v,"object")?,kind,&t,&i)?;out.push(("digest_hex",s(&hex(bytes(get(get(get(v,"object")?,"header")?,"digest")?)?))));},
  "rendered-digest"=>{fields(v,&["template_ref","bindings","digest"])?;typed(get(v,"template_ref")?,&s("TemplateRefR8"),&t,&i)?;for row in arr(get(v,"bindings")?)?{typed(row,&s("ConcreteRowR8"),&t,&i)?;}sorted_rows(get(v,"bindings")?,"slot_id")?;need(bytes(get(v,"digest")?)?==claim_hash(get(v,"template_ref")?,get(v,"bindings")?)?,"SV-46: rendered digest")?;out.push(("digest_hex",s(&hex(bytes(get(v,"digest")?)?))));},
  "decision-input-digest"=>{fields(v,&["evaluation_input","input_digest"])?;need(bytes(get(v,"input_digest")?)?==decision_hash(get(v,"evaluation_input")?,&t,&i)?,"SV-114: complete input digest")?;out.push(("digest_hex",s(&hex(bytes(get(v,"input_digest")?)?))));},
  "wire"=>{fields(v,&["kind","object"])?;wire(txt(get(v,"kind")?)?,get(v,"object")?,&t,&i)?;},
  "runtime-ref"=>{fields(v,&["kind","ref"])?;runtime_ref(txt(get(v,"kind")?)?,get(v,"ref")?,&t,&i)?;},
  "candidate-input"=>{fields(v,&["candidate"])?;let result=candidate(get(v,"candidate")?,&t,&i)?;for key in ["candidate_digest_hex","base_intent_digest_hex","declared_scope_cbor_hex","effects_cbor_hex","n_max_decimal","normative_intent_upgrade"]{out.push((key,get(&result,key)?.clone()));}},
  _=>return Err("unknown binding operation".into()),
 }
 out.extend(vec![("operation",s(op)),("schema_lock_sha256",s(pin)),("full_schema_valid",V::B(false)),("full_phase_i_replay",V::B(false)),("source_authentication",V::B(false)),("production_admission",V::B(false)),("protocol_decision_emitted",V::B(false))]);Ok(map(out))
}
