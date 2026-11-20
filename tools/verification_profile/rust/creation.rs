// SPDX-License-Identifier: Apache-2.0
// Independent I/F binding and explicitly pinned fixed audit TEST replay.
use super::*;
use super::registration::{Imports,typed};
use std::collections::{BTreeMap,BTreeSet};
fn rows(v:&V)->R<&[(V,V)]>{if let V::M(a)=v{Ok(a)}else{Err("map".into())}}
fn same(a:&V,b:&V)->R<bool>{Ok(encode(a)?==encode(b)?)}
fn types()->R<V>{
 let base=parse_json(include_str!("audit_types.json"))?;
 let extra=parse_json(include_str!("creation_types.json"))?;
 let mut result=rows(&base)?.to_vec();
 for (k,v) in rows(&extra)? {need(get_key(&base,k).is_err(),"duplicate creation type")?;result.push((k.clone(),v.clone()));}Ok(V::M(result))
}
fn identity(v:&V)->R<V>{let h=get(v,"header")?;Ok(map(vec![("id",get(h,"id")?.clone()),("digest",get(h,"digest")?.clone())]))}
fn profile_ref(v:&V)->R<V>{Ok(map(vec![("id",get(v,"profile_id")?.clone()),("version",get(v,"profile_version")?.clone()),("digest",get(v,"profile_digest")?.clone())]))}
fn content(v:&V,kind:&str)->R<V>{
 if kind=="ReceiptIntent" {need(get(v,"profile_ref").is_ok()!=get(v,"selection_policy_ref").is_ok(),"RI-1")?;return Ok(v.clone());}
 let h=get(v,"header")?;let mut output=Vec::new();
 for key in ["schema_version","encoding_profile_id","id"] {output.push((s(key),get(h,key)?.clone()));}
 for (k,x) in rows(v)? {if txt(k)?!="header" {output.push((k.clone(),x.clone()));}}Ok(V::M(output))
}
fn object_hash(v:&V,kind:&str,types:&V,imports:&Imports)->R<Vec<u8>>{
 typed(v,&s(kind),types,imports)?;let projection=content(v,kind)?;
 need(integer(get(&projection,"schema_version")?)?==1,"creation schema version")?;
 let tag=if kind=="PhaseIRecord" {"PhaseIValidationRecord"}else{kind};
 let hash=domain(&format!("ACLt/P0-1/{tag}/1"),&encode(&projection)?);
 if kind!="ReceiptIntent" {need(digest_consistency(bytes(get(get(v,"header")?,"digest")?)?==hash),"creation object digest")?;}Ok(hash)
}
fn context(v:&V,bundle:&V,types:&V,imports:&Imports)->R<()>{
 object_hash(v,"CreationContext",types,imports)?;
 for key in ["evaluation_instant","registry_snapshot_ref"]{need(if key=="registry_snapshot_ref"{same_reference(get(v,key)?,get(get(bundle,"context")?,key)?)?}else{same(get(v,key)?,get(get(bundle,"context")?,key)?)?},"SV-101: CC-1")?;}Ok(())
}
fn replay(e:&V,contract:&V)->R<(V,V)>{
 let p=get(e,"profile")?;let slot=get(e,"slot")?;let intent=get(e,"intent")?;let reference=profile_ref(p)?;
 need(same(&reference,get(contract,"profile_ref")?)?&&same(get(p,"admission_predicate")?,get(contract,"admission_predicate")?)?,"test contract Profile/predicate")?;
 let implicit=map(vec![("index",V::N(0)),("profile_ref",reference.clone()),("kind",s("PRIMARY")),("enabling_triggers",V::A(vec![]))]);
 need(same(slot,&implicit)?,"fixed test implicit primary slot only")?;
 need(same(get(intent,"profile_ref")?,&reference)?&&get(intent,"degradation_authorized")?==&V::B(false),"fixed test direct selection only")?;
 need(get(p,"degradation").is_err(),"fixed test no degradation")?;
 for row in arr(get(p,"assumption_references")?)?{need(txt(get(row,"role")?)?=="INFORMATIONAL","test replay excludes safety/liveness scopes")?;}
 need(same(get(e,"assurance_profile")?,get(contract,"assurance_profile")?)?&&same(get(intent,"network_id")?,get(contract,"network_id")?)?&&same(get(intent,"assurance_profile_ref")?,get(contract,"assurance_profile_ref")?)?,"opaque test deployment binding")?;
 let mut found=false;
 for row in arr(get(get(get(e,"bundle")?,"registry_snapshot")?,"entries")?)?{
  if txt(get(row,"object_kind")?)?=="VERIFICATION_PROFILE" && ["id","version","digest"].iter().all(|k|get(row,k).ok()==get(&reference,k).ok())&&["REGISTERED","ACTIVE"].contains(&txt(get(row,"state")?)?){found=true;}
 }
 let mut reasons=vec![];
 if !found {reasons.push(V::X(b"PROFILE_UNAVAILABLE".to_vec()));}
 if !same(get(intent,"contract_tuple")?,get(contract,"contract_tuple")?)?{reasons.push(V::X(b"CONTRACT_MISMATCH".to_vec()));}
 Ok((s(if reasons.is_empty(){"SELECTED"}else{"REJECTED"}),V::A(reasons)))
}
fn ancestors(start:&[u8],events:&BTreeMap<Vec<u8>,&V>)->R<BTreeSet<Vec<u8>>>{
 let mut seen=BTreeSet::new();let mut todo=vec![start.to_vec()];
 while let Some(key)=todo.pop(){if !seen.insert(key.clone()){continue;}
  let event=events.get(&key).ok_or("unresolved event")?;
  for parent in arr(get(event,"parent_refs")?)? {todo.push(encode(parent)?);}
 }Ok(seen)
}
fn causal(record:&V,after:&V,frontier:&V)->R<()>{
 let mut events=BTreeMap::new();for row in arr(get(frontier,"event_records")?)?{events.insert(encode(get(row,"event_ref")?)?,row);}
 let before=encode(get(record,"produced_by_event")?)?;let after=encode(after)?;
 let i=events.get(&before).ok_or("SV-110: missing I event")?;let f=events.get(&after).ok_or("SV-110: missing F event")?;
 let subject=map(vec![("tag",s("PHASE_I_RECORD")),("id",get(get(record,"header")?,"id")?.clone())]);
 need(txt(get(i,"event_kind")?)?=="PHASE_I_VALIDATION"&&same(get(i,"subject_ref")?,&subject)?,"SV-110: I kind/subject")?;
 need(txt(get(f,"event_kind")?)?=="PHASE_F_VALIDATION","SV-110: F kind")?;
 need(before!=after&&ancestors(&after,&events)?.contains(&before),"SV-110: strict I-before-F ancestry")?;
 need(ancestors(&encode(get(frontier,"frontier_event_ref")?)?,&events)?.contains(&after),"test frontier includes F")
}
pub(super) fn run(input:&str,pins:&str,phase:&str)->R<V>{
 let (lock_pin,contract_pin)=pins.split_once(':').ok_or("two external pins required")?;
 let value=decode(&unhex(input)?)?;let key=if phase=="I"{"transcript"}else{"envelope"};
 fields(&value,&[key,"schema_lock","schema_documents","registry_objects","test_contract"])?;
 let contract=get(&value,"test_contract")?;let contract_hash=unhex(contract_pin)?;
 need(contract_hash.len()==32&&digest_consistency(sha256::hash(&encode(contract)?)==contract_hash),"test contract pin")?;
 let imports=Imports::new_mode(get(&value,"schema_lock")?,get(&value,"schema_documents")?,&unhex(lock_pin)?,true)?;
 let types=types()?;typed(contract,&s("FixedAuditTestContract"),&types,&imports)?;
 let (e,t)=if phase=="I" {let t=get(&value,key)?;typed(t,&s("PhaseITranscript"),&types,&imports)?;(get(t,"input")?,t)}
 else {let e=get(&value,key)?;typed(e,&s("PhaseFEnvelope"),&types,&imports)?;(e,get(e,"phase_i_transcript")?)};
 let original=get(t,"input")?;let record=get(t,"output")?;
 let envelopes=if phase=="I"{vec![original]}else{vec![original,e]};
 for env in envelopes {
  let shadow=map(vec![("envelope",map(vec![("phase",s("R")),("bundle",get(env,"bundle")?.clone()),("object",get(env,"profile")?.clone())])),
   ("schema_lock",get(&value,"schema_lock")?.clone()),("schema_documents",get(&value,"schema_documents")?.clone()),("registry_objects",get(&value,"registry_objects")?.clone())]);
  super::method_rules::run(&hex(&encode(&shadow)?),lock_pin,true)?;
  context(get(env,"creation_context")?,get(env,"bundle")?,&types,&imports)?;
  object_hash(get(env,"intent")?,"ReceiptIntent",&types,&imports)?;
 }
 object_hash(record,"PhaseIRecord",&types,&imports)?;
 need(same_reference(get(record,"creation_context_ref")?,&identity(get(original,"creation_context")?)?)?,"SV-96: CC-2I")?;
 need(digest_consistency(bytes(get(record,"intent_digest")?)?==object_hash(get(original,"intent")?,"ReceiptIntent",&types,&imports)?),"SV-102: intent digest")?;
 need(same(get(record,"slot_index")?,get(get(original,"slot")?,"index")?)?,"SV-102: slot index")?;
 let (outcome,reasons)=replay(original,contract)?;
 need(same(get(record,"outcome")?,&outcome)?&&same(get(record,"failure_reasons")?,&reasons)?,"SV-102: fixed TEST replay")?;
 if phase=="F" {
  need(same_reference(get(record,"creation_context_ref")?,&identity(get(e,"creation_context")?)?)?,"SV-96: CC-2F")?;
  need(same_reference(&profile_ref(get(original,"profile")?)?,&profile_ref(get(e,"profile")?)?)?,"SV-96: CC-3 Profile")?;
  need(same(&content(get(original,"intent")?,"ReceiptIntent")?,&content(get(e,"intent")?,"ReceiptIntent")?)?&&same(get(original,"slot")?,get(e,"selected_slot")?)?,"SV-96: CC-3 Intent/slot")?;
  let mut projection=rows(e)?.to_vec();projection.push((s("slot"),get(e,"selected_slot")?.clone()));
  let (fo,fr)=replay(&V::M(projection),contract)?;
  need(same(get(record,"outcome")?,&fo)?&&same(get(record,"failure_reasons")?,&fr)?,"SV-102: fixed TEST F replay")?;
  need(txt(get(record,"outcome")?)?=="SELECTED","SV-102: F requires SELECTED")?;
  causal(record,get(e,"phase_f_event_ref")?,get(get(e,"bundle")?,"event_frontier_snapshot")?)?;
 }
 let reasons_hex=V::A(arr(&reasons)?.iter().map(|x|Ok(s(&hex(bytes(x)?)))).collect::<R<_>>()?);
 Ok(map(vec![("phase",s(phase)),("outcome",outcome),("failure_reasons_hex",reasons_hex),
  ("context_digest_hex",s(&hex(bytes(get(get(get(e,"creation_context")?,"header")?,"digest")?)?))),
  ("intent_digest_hex",s(&hex(bytes(get(record,"intent_digest")?)?))),
  ("phase_i_record_digest_hex",s(&hex(bytes(get(get(record,"header")?,"digest")?)?))),
  ("schema_lock_sha256",s(lock_pin)),("test_contract_sha256",s(contract_pin)),
  ("full_schema_valid",V::B(false)),("full_phase_i_replay",V::B(false)),("source_authentication",V::B(false)),("production_admission",V::B(false)),("receipt_created",V::B(false))]))
}
