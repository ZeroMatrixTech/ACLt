// SPDX-License-Identifier: Apache-2.0
// Independent explicit Phase B components; pinned TEST imports, no state writes.
use super::*;
use super::registration::{typed,Imports};
use std::collections::{BTreeMap,BTreeSet};
const STAGES:[&str;4]=["PRE_FREEZE","FROZEN_PRE_DRAW","RUNNING","TERMINAL"];
fn same(a:&V,b:&V)->R<bool>{Ok(encode(a)?==encode(b)?)}
fn same_optional(a:Option<&V>,b:Option<&V>)->R<bool>{match(a,b){(Some(x),Some(y))=>same(x,y),(None,None)=>Ok(true),_=>Ok(false)}}
fn types()->R<V>{let mut all=match commitments::types()?{V::M(v)=>v,_=>return Err("types".into())};let extra=parse_json(include_str!("runtime_types.json"))?;if let V::M(v)=extra{for (k,v) in v{need(!all.iter().any(|(a,_)|a==&k),"duplicate runtime type")?;all.push((k,v));}}Ok(V::M(all))}
pub(super) fn ancestors(events:&BTreeMap<Vec<u8>,V>,root:&[u8])->R<BTreeSet<Vec<u8>>>{let mut seen=BTreeSet::new();let mut pending=vec![root.to_vec()];while let Some(k)=pending.pop(){if seen.insert(k.clone()){let event=events.get(&k).ok_or("missing event")?;for p in arr(get(event,"parent_refs")?)?{pending.push(encode(p)?);}}}Ok(seen)}
pub(super) fn event_is(events:&BTreeMap<Vec<u8>,V>,visible:&BTreeSet<Vec<u8>>,reference:&V,kind:&str,tag:&str,id:&V)->R<bool>{let code=encode(reference)?;let Some(row)=events.get(&code)else{return Ok(false);};Ok(visible.contains(&code)&&txt(get(row,"event_kind")?)?==kind&&same(get(row,"subject_ref")?,&map(vec![("tag",s(tag)),("id",id.clone())]))?)}
fn shape<'a>(e:&'a V,t:&V,i:&Imports)->R<Option<V>>{
 typed(e,&s("RuntimeEnvelopeR9"),t,i)?;let payload=get(e,"payload")?;let tag=txt(get(payload,"tag")?)?;
 let keys:Vec<&str>=match tag{
 "LEASE_ACTIVATION_PRE_FREEZE"=>vec!["tag","transition","actual_bound_scope"],
 "LEASE_ACTIVATION_POST_FREEZE"|"SNAPSHOT_FREEZE"=>vec!["tag","transition","actual_bound_scope","eligibility_snapshot"],
 "CLUSTER_MAPPING_FIX"=>vec!["tag","transition","cluster_mapping_fixed_event"],
 "ROUND_TRANSITION_PRE_FREEZE"=>vec!["tag","transition"],
 "ROUND_TRANSITION_POST_FREEZE"=>vec!["tag","transition","eligibility_snapshot"],
 "ROUND_TRANSITION_NO_SNAPSHOT"=>if get(payload,"transition_event_ref").is_ok(){vec!["tag","transition","transition_event_ref"]}else{vec!["tag","transition"]},
 _=>return Err("SV-93: payload tag".into()),
 };fields(payload,&keys)?;typed(get(payload,"transition")?,&s(if tag=="SNAPSHOT_FREEZE"{"FreezeTransitionR9"}else{"TransitionR9"}),t,i)?;
 if let Ok(scope)=get(payload,"actual_bound_scope"){typed(scope,&s("DeclaredScopeR7"),t,i)?;for key in ["fault_domains","geography"]{need(!arr(get(scope,key)?)?.is_empty(),"SV-77: empty actual dimension")?;}}
 for key in ["cluster_mapping_fixed_event","transition_event_ref"]{if let Ok(event)=get(payload,key){i.check("EventRef",event)?;}}
 if let Ok(raw)=get(payload,"eligibility_snapshot"){
  i.external_object(raw)?;let snapshot=decode(bytes(get(raw,"canonical_bytes")?)?)?;typed(&snapshot,&s("SnapshotAdapterR9"),t,i)?;need(!txt(get(&snapshot,"id")?)?.is_empty(),"empty snapshot ID")?;
  for row in arr(get(&snapshot,"sampling_units")?)?{need(!bytes(get(row,"id")?)?.is_empty(),"empty unit ID")?;for key in ["fault_domains","geography"]{need(!arr(get(get(row,"scope")?,key)?)?.is_empty(),"empty unit scope")?;}}Ok(Some(snapshot))
 }else{Ok(None)}
}
fn frozen(p:&V)->R<V>{let safety=get(p,"safety_parameters")?;Ok(map(vec![("G",get(safety,"G")?.clone()),("B",get(safety,"B")?.clone()),("Q",get(get(p,"liveness_parameters")?,"Q")?.clone()),("delta_min",get(safety,"delta_min")?.clone()),("mixture_weights",get(get(p,"method_parameters")?,"mixture_weights")?.clone())]))}
fn bundle(b:&V,t:&V,i:&Imports)->R<()>{typed(b,&s("ReferencesBundle"),t,i)?;let reg=get(b,"registry_snapshot")?;registration::check_registry(reg)?;let context=get(b,"context")?;need(same(get(context,"registry_snapshot_ref")?,&commitments::identity(reg)?)?,"registry context")?;let f=get(b,"event_frontier_snapshot")?;registration::check_frontier(f,i)?;let h=get(f,"header")?;need(same(get(context,"event_frontier_ref")?,&map(vec![("id",get(h,"id")?.clone()),("digest",get(h,"digest")?.clone())]))?,"frontier context")}
fn unit_set(v:&V)->R<BTreeSet<Vec<u8>>>{arr(v)?.iter().map(encode).collect()}
fn no_snapshot(method:&str,receipt:&V,reference:&V,payload:&V,events:&BTreeMap<Vec<u8>,V>,visible:&BTreeSet<Vec<u8>>)->R<()>{
 need(["DIRECT_VERIFIED","PROOF_VERIFIED","REEXEC_AUDIT_ONLY"].contains(&method),"SV-94")?;let tr=get(payload,"transition")?;let before=get(tr,"prior_round_state")?;let after=get(tr,"proposed_round_state")?;let a=txt(get(before,"round_stage")?)?;let z=txt(get(after,"round_stage")?)?;
 need([("PRE_FREEZE","RUNNING"),("RUNNING","RUNNING"),("RUNNING","TERMINAL"),("PRE_FREEZE","TERMINAL")].contains(&(a,z)),"SV-94")?;
 for state in [before,after]{need(same(get(state,"bound_profile_ref")?,reference)?,"SV-94")?;}
 need(get(payload,"transition_event_ref").is_ok()==(a!=z),"SV-94")?;
 let mut starts=vec![];let mut terminals=vec![];
 for key in visible{let row=events.get(key).ok_or("event missing")?;if same(get(row,"subject_ref")?,&map(vec![("tag",s("RECEIPT")),("id",receipt.clone())]))?{match txt(get(row,"event_kind")?)?{"VERIFICATION_STARTED"=>starts.push(key.clone()),"VERIFICATION_TERMINAL_COMMITTED"=>terminals.push(key.clone()),_=>()}}}
 if z=="RUNNING"{need(starts.len()==1&&terminals.is_empty(),"SV-94")?;if a!=z{need(encode(get(payload,"transition_event_ref")?)?==starts[0],"SV-94")?;}}
 else{let reference=encode(get(payload,"transition_event_ref")?)?;need(terminals==vec![reference.clone()],"SV-94")?;if a=="RUNNING"{need(starts.len()==1&&starts[0]!=reference&&ancestors(events,&reference)?.contains(&starts[0]),"SV-94")?;}else{need(starts.is_empty(),"SV-94")?;}}Ok(())
}
fn guard(e:&V,snapshot:Option<&V>,contract:&V,t:&V,i:&Imports)->R<()>{
 let p=get(e,"profile")?;let method=txt(get(p,"verification_method")?)?;let bounded=method=="REEXEC_BOUNDED";let payload=get(e,"payload")?;let tag=txt(get(payload,"tag")?)?;let tr=get(payload,"transition")?;let prior=get(tr,"prior_round_state")?;let after=get(tr,"proposed_round_state")?;let a=txt(get(prior,"round_stage")?)?;let z=txt(get(after,"round_stage")?)?;
 let binding=get(e,"receipt_binding")?;let reference=commitments::pref(p)?;let assurance=get(e,"assurance_profile")?;
 for actual in [get(binding,"profile_ref")?,get(e,"bound_profile_ref")?,get(prior,"bound_profile_ref")?,get(after,"bound_profile_ref")?]{need(same(&reference,actual)?,"SV-92")?;}
 need(same(&commitments::identity(assurance)?,get(binding,"assurance_profile_ref")?)?&&same(get(assurance,"network_id")?,get(binding,"network_id")?)?,"SV-92")?;
 if let Some(snap)=snapshot{need(same(get(snap,"receipt_id")?,get(binding,"receipt_id")?)?,"SV-92")?;}
 need(STAGES.iter().position(|x|*x==a)<=STAGES.iter().position(|x|*x==z),"SV-105")?;
 let frontier=get(get(e,"bundle")?,"event_frontier_snapshot")?;let mut events=BTreeMap::new();for row in arr(get(frontier,"event_records")?)?{events.insert(encode(get(row,"event_ref")?)?,row.clone());}let visible=ancestors(&events,&encode(get(frontier,"frontier_event_ref")?)?)?;
 if bounded{
  let valid=match tag{"LEASE_ACTIVATION_PRE_FREEZE"|"CLUSTER_MAPPING_FIX"|"ROUND_TRANSITION_PRE_FREEZE"=>a=="PRE_FREEZE"&&z==a,"LEASE_ACTIVATION_POST_FREEZE"=>a==z&&STAGES[1..].contains(&a),"SNAPSHOT_FREEZE"=>a=="PRE_FREEZE"&&z=="FROZEN_PRE_DRAW","ROUND_TRANSITION_POST_FREEZE"=>[("FROZEN_PRE_DRAW","RUNNING"),("RUNNING","RUNNING"),("RUNNING","TERMINAL")].contains(&(a,z)),_=>false};need(valid,"SV-105")?;
  let expected=frozen(p)?;
  for state in [prior,after]{need(get(state,"frozen_parameters").is_ok_and(|x|same(x,&expected).unwrap_or(false)),"SV-94")?;if txt(get(state,"round_stage")?)?!="PRE_FREEZE"{need(get(state,"population_size").is_ok_and(|x|same(x,get(&expected,"G").unwrap()).unwrap_or(false))&&get(state,"cluster_mapping_ref").is_ok(),"SV-94")?;}else if let Ok(size)=get(state,"population_size"){need(same(size,get(&expected,"G")?)?,"SV-94")?;}}
  let old=get(prior,"cluster_mapping_ref").ok();let new=get(after,"cluster_mapping_ref").ok();
  if tag=="CLUSTER_MAPPING_FIX"{need(old.is_none()&&new.is_some(),"SV-106")?;}else{need(same_optional(old,new)?,"SV-106")?;}
  if tag=="SNAPSHOT_FREEZE"{need(old.is_some(),"SV-106")?;}
 }else{
  need(["LEASE_ACTIVATION_PRE_FREEZE","ROUND_TRANSITION_NO_SNAPSHOT"].contains(&tag),"SV-105")?;
  for state in [prior,after]{need(["frozen_parameters","population_size","cluster_mapping_ref"].iter().all(|k|get(state,k).is_err())&&txt(get(state,"round_stage")?)?!="FROZEN_PRE_DRAW","SV-94")?;}
  if tag=="LEASE_ACTIVATION_PRE_FREEZE"{need(a=="PRE_FREEZE"&&z==a,"SV-105")?;}else{no_snapshot(method,get(binding,"receipt_id")?,&reference,payload,&events,&visible)?;}
 }
 let assumptions=arr(get(p,"assumption_references")?)?.iter().filter(|x|["SAFETY_CRITICAL","LIVENESS"].contains(&txt(get(x,"role").unwrap()).unwrap())).collect::<Vec<_>>();
 if let Ok(actual)=get(payload,"actual_bound_scope"){for row in &assumptions{need(selection::scope(get(row,"scope")?,actual,t,i)?,"SV-68")?;}}
 if tag=="CLUSTER_MAPPING_FIX"{need(event_is(&events,&visible,get(payload,"cluster_mapping_fixed_event")?,"CLUSTER_MAPPING_FIXED","CLUSTER_MAPPING",get(get(after,"cluster_mapping_ref")?,"id")?)?,"SV-106")?;}
 if let Some(snap)=snapshot{
  let units=arr(get(snap,"sampling_units")?)?;let ids=units.iter().map(|u|encode(get(u,"id")?)).collect::<R<BTreeSet<_>>>()?;need(ids.len()==units.len(),"SV-82")?;
  for unit in units{for a in &assumptions{need(selection::scope(get(a,"scope")?,get(unit,"scope")?,t,i)?,"SV-69")?;}}
  for state in [prior,after]{need(get(state,"cluster_mapping_ref").is_ok_and(|x|same(get(snap,"cluster_mapping_ref").unwrap(),x).unwrap_or(false)),"SV-99")?;}
  let params=get(p,"method_parameters")?;let g=integer(get(get(p,"safety_parameters")?,"G")?)?;
  need(same(get(snap,"population_definition_ref")?,get(params,"population_definition")?)?&&same(get(snap,"snapshot_schema_ref")?,get(params,"snapshot_schema_ref")?)?&&ids.len() as i128==g,"SV-81")?;
  for (source,target) in [("population_definition","population_definition_ref"),("snapshot_schema_ref","snapshot_schema_ref"),("randomness_commitment","randomness_rule_ref")]{need(same(get(params,source)?,get(contract,target)?)?,"SV-81")?;}
  let random=get(snap,"randomness_commitment")?;need(same(get(random,"scheme_id")?,get(contract,"scheme_id")?)?&&arr(get(contract,"allowed_randomness_parameters")?)?.iter().any(|x|same(x,get(random,"parameters").unwrap()).unwrap_or(false)),"SV-81")?;
 }
 if tag=="SNAPSHOT_FREEZE"{
  let snap=snapshot.ok_or("snapshot required")?;let record=get(tr,"snapshot_freeze_record")?;let mapping=get(record,"cluster_mapping_ref")?;need(same(mapping,get(snap,"cluster_mapping_ref")?)?,"SV-99")?;
  let candidate=unit_set(get(record,"candidate_units_pre_scope_filter")?)?;let excluded=unit_set(get(record,"excluded_by_scope")?)?;let kept=unit_set(get(record,"frozen_units")?)?;let actual=arr(get(snap,"sampling_units")?)?.iter().map(|x|encode(get(x,"id")?)).collect::<R<BTreeSet<_>>>()?;
  need(excluded.is_subset(&candidate)&&kept==candidate.difference(&excluded).cloned().collect()&&kept==actual&&kept.len() as i128==integer(get(get(p,"safety_parameters")?,"G")?)?,"SV-94")?;
  let first=get(record,"cluster_mapping_fixed_event")?;let last=get(record,"freeze_event")?;
  need(event_is(&events,&visible,first,"CLUSTER_MAPPING_FIXED","CLUSTER_MAPPING",get(mapping,"id")?)?&&event_is(&events,&visible,last,"SNAPSHOT_FROZEN","ELIGIBILITY_SNAPSHOT",get(snap,"id")?)?&&!same(first,last)?&&ancestors(&events,&encode(last)?)?.contains(&encode(first)?),"SV-107")?;
 }Ok(())
}
pub(super) fn run(input:&str,lock:&str,contract_pin:&str)->R<V>{
 let v=decode(&unhex(input)?)?;fields(&v,&["envelope","schema_lock","schema_documents","runtime_contract"])?;let i=Imports::new_bindings(get(&v,"schema_lock")?,get(&v,"schema_documents")?,&unhex(lock)?)?;let t=types()?;let contract=get(&v,"runtime_contract")?;typed(contract,&s("RuntimeContractR9"),&t,&i)?;need(sha256::hash(&encode(contract)?)==unhex(contract_pin)?,"runtime contract pin")?;need(!txt(get(contract,"scheme_id")?)?.is_empty()&&!arr(get(contract,"allowed_randomness_parameters")?)?.is_empty(),"empty runtime contract")?;
 let e=get(&v,"envelope")?;let snapshot=shape(e,&t,&i)?;let p=get(e,"profile")?;profile::run("profile-digest",&hex(&encode(p)?))?;let method=txt(get(p,"verification_method")?)?;need(["DIRECT_VERIFIED","PROOF_VERIFIED","REEXEC_BOUNDED","REEXEC_AUDIT_ONLY"].contains(&method),"method")?;registration::rule_assumptions(get(p,"assumption_references")?,&t,&i)?;method_rules::asset_input(p,&i)?;selection::parameter_refs(p)?;bundle(get(e,"bundle")?,&t,&i)?;commitments::digest_object(get(e,"assurance_profile")?,"MainnetAssuranceProfile",&t,&i)?;
 let before=txt(get(get(get(e,"payload")?,"transition")?,"prior_round_state").and_then(|x|get(x,"round_stage"))?)?;
 let failure=guard(e,snapshot.as_ref(),contract,&t,&i).err();let accepted=failure.is_none();let consequence=if accepted{"VALIDATED"}else{match before{"PRE_FREEZE"=>"REJECT_OPERATION","FROZEN_PRE_DRAW"=>"INVALIDATE_SNAPSHOT_NO_REFREEZE","RUNNING"=>"VERIFICATION_INVALIDATING","TERMINAL"=>"QUALIFICATION_ONLY",_=>return Err("stage".into())}};
 Ok(map(vec![("accepted",V::B(accepted)),("failure_rule",s(failure.as_deref().unwrap_or(""))),("consequence",s(consequence)),("prior_stage",s(before)),("payload_tag",get(get(e,"payload")?,"tag")?.clone()),("schema_lock_sha256",s(lock)),("runtime_contract_sha256",s(contract_pin)),("full_schema_valid",V::B(false)),("formal_phase_b_conformance",V::B(false)),("source_authentication",V::B(false)),("production_admission",V::B(false)),("protocol_decision_emitted",V::B(false)),("state_committed",V::B(false))]))
}
