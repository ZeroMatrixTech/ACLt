// SPDX-License-Identifier: Apache-2.0
// Independent registration assets and explicit-input selection rule components.
use super::*;
use super::registration::{Imports,typed};
use std::collections::BTreeSet;
fn rows(v:&V)->R<&[(V,V)]>{if let V::M(a)=v{Ok(a)}else{Err("map".into())}}
fn same(a:&V,b:&V)->R<bool>{Ok(encode(a)?==encode(b)?)}
fn boolean(v:&V)->R<bool>{if let V::B(b)=v{Ok(*b)}else{Err("bool".into())}}
fn types()->R<V>{
 let base=parse_json(include_str!("audit_types.json"))?;let extra=parse_json(include_str!("selection_types.json"))?;let mut result=rows(&base)?.to_vec();
 for (k,v) in rows(&extra)?{need(get_key(&base,k).is_err(),"duplicate selection type")?;result.push((k.clone(),v.clone()));}Ok(V::M(result))
}
fn pref(p:&V)->R<V>{Ok(map(vec![("id",get(p,"profile_id")?.clone()),("version",get(p,"profile_version")?.clone()),("digest",get(p,"profile_digest")?.clone())]))}
fn verify(p:&V)->R<()>{super::profile::run("profile-digest",&hex(&encode(p)?))?;Ok(())}
fn snapshot(v:&V,t:&V,i:&Imports)->R<()>{typed(v,&s("Registry"),t,i)?;super::registration::check_registry(v)}
fn present(row:&V,reference:&V)->R<bool>{Ok(txt(get(row,"object_kind")?)?=="VERIFICATION_PROFILE"&&["id","version","digest"].iter().all(|k|get(row,k).ok()==get(reference,k).ok()))}
fn resolve<'a>(reference:&V,profiles:&'a V,snapshot:&V,t:&V,i:&Imports)->R<&'a V>{
 typed(reference,&s("ProfileRef"),t,i)?;let mut found=None;
 for p in arr(profiles)?{if same(&pref(p)?,reference)?{need(found.is_none(),"duplicate Profile asset")?;verify(p)?;found=Some(p);}}
 let p=found.ok_or("missing actual Profile")?;let mut registered=false;
 for row in arr(get(snapshot,"entries")?)?{if present(row,reference)?{registered=true;}}
 need(registered,"Profile absent from snapshot")?;Ok(p)
}
fn assets(profiles:&V,snap:&V,t:&V,i:&Imports)->R<()>{
 snapshot(snap,t,i)?;let mut identities=BTreeSet::new();
 for p in arr(profiles)?{verify(p)?;let reference=pref(p)?;need(identities.insert(encode(&reference)?),"duplicate Profile asset")?;resolve(&reference,profiles,snap,t,i)?;}Ok(())
}
fn parameter_refs(p:&V)->R<()>{
 if txt(get(p,"verification_method")?)?!="REEXEC_BOUNDED"{return Ok(());}
 for (block,key,class,role) in [("safety_parameters","support_capability_bound_ref","SUPPORT_CAPABILITY_BOUND","SAFETY_CRITICAL"),("liveness_parameters","calibration_ref","CALIBRATION","LIVENESS")]{
  let reference=get(get(p,block)?,key)?;let mut matches=vec![];
  for row in arr(get(p,"assumption_references")?)?{if same(get(row,"assumption_id")?,reference)?{matches.push(row);}}
  need(matches.len()==1&&txt(get(matches[0],"assumption_class")?)?==class&&txt(get(matches[0],"role")?)?==role,"SV-12R/47: assumption reference class/role")?;
 }Ok(())
}
fn admissible(p:&V,snap:&V)->R<bool>{
 verify(p)?;let reference=pref(p)?;
 for row in arr(get(snap,"entries")?)?{if present(row,&reference)?&&["REGISTERED","ACTIVE"].contains(&txt(get(row,"state")?)?){return Ok(true);}}Ok(false)
}
fn selected(slot:&V,p:&V,snap:&V)->R<()>{
 verify(p)?;let reference=pref(p)?;need(same(get(slot,"profile_ref")?,&reference)?,"SV-45: slot/actual Profile")?;
 for row in arr(get(snap,"entries")?)?{if present(row,&reference)?{return Ok(());}}Err("SV-45: Profile absent from snapshot".into())
}
fn projection(v:&V)->R<V>{
 let h=get(v,"header")?;fields(h,&["schema_version","encoding_profile_id","id","version","digest"])?;
 let mut result=vec![(s("schema_version"),get(h,"schema_version")?.clone()),(s("encoding_profile_id"),get(h,"encoding_profile_id")?.clone())];
 for (k,x) in rows(v)?{if txt(k)?!="header"{result.push((k.clone(),x.clone()));}}Ok(V::M(result))
}
fn asset_hash(v:&V,kind:&str,t:&V,i:&Imports)->R<()>{
 typed(v,&s(kind),t,i)?;let h=get(v,"header")?;need(integer(get(h,"schema_version")?)?==1,"asset schema version")?;
 let tag=match kind{"PolicyR7"=>"SelectionPolicy","EdgeR7"=>"WeakeningEdge","ManifestR7"=>"Manifest",_=>return Err("asset kind".into())};
 let hash=domain(&format!("ACLt/P0-1/{tag}/1"),&encode(&projection(v)?)?);
 need(bytes(get(h,"digest")?)?==hash,"asset digest mismatch")
}
fn edge(v:&V,profiles:&V,snap:&V,t:&V,i:&Imports)->R<()>{
 asset_hash(v,"EdgeR7",t,i)?;need(txt(get(v,"edge_class")?)?=="AUTO_DECIDABLE","SV-21: AUTO_DECIDABLE only")?;
 let a=resolve(get(v,"source")?,profiles,snap,t,i)?;let b=resolve(get(v,"target")?,profiles,snap,t,i)?;
 need(txt(get(a,"verification_method")?)?=="REEXEC_BOUNDED"&&txt(get(b,"verification_method")?)?=="REEXEC_AUDIT_ONLY","SV-21: bounded to audit only")?;
 need(get(b,"verified_claim_spec").is_err(),"SV-21: no target claim")?;
 let source=arr(get(get(a,"excluded_claims")?,"exclusion_ids")?)?;let target=arr(get(get(b,"excluded_claims")?,"exclusion_ids")?)?;
 need(source.iter().all(|x|target.contains(x)),"SV-21: exclusions")?;
 for key in ["task_type","contract_tuple_constraints","result_equivalence"]{need(same(get(a,key)?,get(b,key)?)?,"SV-21: task/constraints/equivalence")?;}Ok(())
}
fn expand(candidates:&V,profiles:&V,snap:&V,t:&V,i:&Imports)->R<V>{
 let mut slots=vec![];
 for candidate in arr(candidates)?{
  let p=resolve(get(candidate,"profile_ref")?,profiles,snap,t,i)?;let n=slots.len();
  let mut primary=vec![("index",V::N(n as i128)),("profile_ref",get(candidate,"profile_ref")?.clone()),("kind",s("PRIMARY")),("enabling_triggers",V::A(vec![]))];
  if let Ok(gate)=get(candidate,"gate"){primary.push(("gate",gate.clone()));}slots.push(map(primary));
  if let Ok(d)=get(p,"degradation"){
   typed(d,&s("Degradation"),t,i)?;
   slots.push(map(vec![("index",V::N(slots.len() as i128)),("profile_ref",get(d,"target")?.clone()),("kind",s("DEGRADED")),("degraded_from",V::N(n as i128)),("enabling_triggers",get(d,"triggers")?.clone())]));
  }
 }Ok(V::A(slots))
}
fn policy(v:&V,profiles:&V,snap:&V,edges:&V,t:&V,i:&Imports)->R<()>{
 asset_hash(v,"PolicyR7",t,i)?;let mut indices=BTreeSet::new();
 for slot in arr(get(v,"expanded_slots")?)?{need(indices.insert(integer(get(slot,"index")?)?),"SV-41: duplicate index")?;}
 need(same(get(v,"expanded_slots")?,&expand(get(v,"ordered_candidates")?,profiles,snap,t,i)?)?,"SV-53a: expansion/per-slot gate")?;
 for candidate in arr(get(v,"ordered_candidates")?)?{
  let reference=get(candidate,"profile_ref")?;let p=resolve(reference,profiles,snap,t,i)?;
  if let Ok(d)=get(p,"degradation"){
   let target=get(d,"target")?;resolve(target,profiles,snap,t,i)?;let mut matches=vec![];
   for e in arr(edges)?{if same(get(e,"source")?,reference)?&&same(get(e,"target")?,target)?{matches.push(e);}}
   need(matches.len()==1,"one explicit weakening edge required")?;edge(matches[0],profiles,snap,t,i)?;
  }
 }for e in arr(edges)?{edge(e,profiles,snap,t,i)?;}Ok(())
}
fn manifest(v:&V,t:&V,i:&Imports)->R<()>{
 asset_hash(v,"ManifestR7",t,i)?;let mut previous:Option<&str>=None;
 for row in arr(get(v,"file_digests")?)?{
  let path=txt(get(row,"path")?)?;let drive=path.as_bytes().get(1)==Some(&b':')&&path.as_bytes()[0].is_ascii_alphabetic();
  need(!path.is_empty()&&!path.contains('\0')&&!path.starts_with('/')&&!path.contains('\\')&&!drive,"SV-85: relative POSIX path")?;
  if let Some(last)=previous{need(last<path,"SV-85: file path order/duplicate")?;}previous=Some(path);
 }Ok(())
}
fn event_subject(v:&V,t:&V,i:&Imports)->R<()>{
 typed(v,&s("Event"),t,i)?;let kind=txt(get(v,"event_kind")?)?;let sub=get(v,"subject_ref")?;
 let tag=match kind{"PHASE_I_VALIDATION"=>"PHASE_I_RECORD","PHASE_F_VALIDATION"=>"PHASE_F_CALL","CLUSTER_MAPPING_FIXED"=>"CLUSTER_MAPPING","SNAPSHOT_FROZEN"=>"ELIGIBILITY_SNAPSHOT","FUNDING_EXHAUSTED"|"DEADLINE_REACHED"|"EXECUTION_EXHAUSTED"|"VERIFICATION_STARTED"|"VERIFICATION_TERMINAL_COMMITTED"=>"RECEIPT","OTHER"=>"OPAQUE_IMPORTED",_=>return Err("SV-120: unknown kind".into())};
 need(txt(get(sub,"tag")?)?==tag,"SV-120: subject tag")?;need(get(sub,"schema_ref").is_ok()==(kind=="OTHER"),"SV-120: subject fields")?;
 let id=get(sub,"id")?;
 match tag{
  "PHASE_I_RECORD"=>typed(id,&map(vec![("identifier",s("PHASE_I_RECORD"))]),t,i)?,
  "CLUSTER_MAPPING"=>{let tail=txt(id)?.strip_prefix("acl.cmap.").ok_or("cluster ID")?;need(tail.len()==26&&tail.bytes().all(|c|b"0123456789ABCDEFGHJKMNPQRSTVWXYZ".contains(&c)),"cluster ID")?;},
  "PHASE_F_CALL"=>i.check("EventRef",id)?,"RECEIPT"=>dig(id)?,_=>{txt(id)?;},
 }Ok(())
}
fn authorized(slot:&V,auth:&V)->R<bool>{let auth=boolean(auth)?;let kind=txt(get(slot,"kind")?)?;need(["PRIMARY","DEGRADED"].contains(&kind),"slot kind")?;Ok(kind=="PRIMARY"||auth)}
fn semver_cmp(a:&V,b:&V)->R<std::cmp::Ordering>{let a=arr(a)?.iter().map(integer).collect::<R<Vec<_>>>()?;let b=arr(b)?.iter().map(integer).collect::<R<Vec<_>>>()?;Ok(a.cmp(&b))}
fn in_range(v:&V,range:&V)->R<bool>{
 if semver_cmp(v,get_key(range,&V::N(0))?)?.is_lt(){return Ok(false);}
 if let Ok(end)=get_key(range,&V::N(1)){if !semver_cmp(v,end)?.is_lt(){return Ok(false);}}Ok(true)
}
fn scope(scope:&V,declared:&V,t:&V,i:&Imports)->R<bool>{
 typed(scope,&s("Scope"),t,i)?;typed(declared,&s("DeclaredScopeR7"),t,i)?;
 for key in ["fault_domains","geography"]{need(!arr(get(declared,key)?)?.is_empty(),"SV-58: empty declared dimension")?;}
 let mut covered=same(get(scope,"task_class")?,get(declared,"task_class")?)?&&same(get(scope,"environment_class")?,get(declared,"environment_class")?)?;
 covered&=in_range(get(declared,"rir_version")?,get(scope,"rir_profile_range")?)?&&in_range(get(declared,"rpr_version")?,get(scope,"rpr_version_range")?)?;
 for key in ["fault_domains","geography"]{let a=arr(get(scope,key)?)?;covered&=arr(get(declared,key)?)?.iter().all(|x|a.contains(x));}Ok(covered)
}
fn applicability(v:&V,t:&V,i:&Imports)->R<V>{
 fields(v,&["profile","declared_scope","evaluation_instant","n_max","intent_effects","slot","degradation_authorized","source_failure_reasons"])?;
 let p=get(v,"profile")?;verify(p)?;super::method_rules::asset_input(p,i)?;parameter_refs(p)?;
 uint(get(v,"n_max")?)?;typed(get(v,"evaluation_instant")?,&s("int"),t,i)?;
 let declared=get(v,"declared_scope")?;typed(declared,&s("DeclaredScopeR7"),t,i)?;
 for key in ["fault_domains","geography"]{need(!arr(get(declared,key)?)?.is_empty(),"SV-58: empty declared dimension")?;}
 let slot=get(v,"slot")?;typed(slot,&s("SlotR7"),t,i)?;
 let effects=get(v,"intent_effects")?;let mut seen=vec![];
 for e in arr(effects)?{i.check("EffectID",e)?;let code=encode(e)?;if let Some(last)=seen.last(){need(last<&code,"effects order/duplicate")?;}seen.push(code);}
 let reasons=get(v,"source_failure_reasons")?;for x in arr(reasons)?{txt(x)?;}
 let allowed=authorized(slot,get(v,"degradation_authorized")?)?;let triggers=arr(get(slot,"enabling_triggers")?)?;
 let enabled=allowed&&(txt(get(slot,"kind")?)?=="PRIMARY"||(!arr(reasons)?.is_empty()&&arr(reasons)?.iter().all(|x|triggers.contains(x))));
 let mut covered=true;
 for row in arr(get(p,"assumption_references")?)?{if ["SAFETY_CRITICAL","LIVENESS"].contains(&txt(get(row,"role")?)?){covered&=scope(get(row,"scope")?,declared,t,i)?;}}
 let allowed_effects=arr(get(get(p,"contract_tuple_constraints")?,"allowed_effects")?)?;
 let mut output=vec![("degradation_authorized",V::B(allowed)),("test_slot_enabled",V::B(enabled)),("scope_covered",V::B(covered)),("effects_covered",V::B(arr(effects)?.iter().all(|x|allowed_effects.contains(x))))];
 if txt(get(p,"verification_method")?)?=="REEXEC_BOUNDED"{
  let reference=get(get(p,"safety_parameters")?,"support_capability_bound_ref")?;
  let a=arr(get(p,"assumption_references")?)?.iter().find(|x|get(x,"assumption_id").ok()==Some(reference)).ok_or("bound assumption")?;
  let window=get(a,"validity_window")?;typed(window,&s("wire-time-range"),t,i)?;let w=arr(window)?;let instant=integer(get(v,"evaluation_instant")?)?;
  output.push(("bound_scope_window_ok",V::B(scope(get(a,"scope")?,declared,t,i)?&&integer(&w[0])?<=instant&&instant<integer(&w[1])?)));
  output.push(("required_draws_within_limit",V::B(integer(get(get(p,"liveness_parameters")?,"n_required")?)?<=integer(get(v,"n_max")?)?)));
  output.push(("invalid_sample_limit_ok",V::B(integer(get(get(p,"failure_mapping")?,"max_invalid_samples")?)?<=integer(get(v,"n_max")?)?)));
 }Ok(map(output))
}
pub(super) fn run(input:&str,pin:&str)->R<V>{
 let value=decode(&unhex(input)?)?;fields(&value,&["operation","payload","schema_lock","schema_documents"])?;
 let i=Imports::new_mode(get(&value,"schema_lock")?,get(&value,"schema_documents")?,&unhex(pin)?,true)?;let t=types()?;
 let op=txt(get(&value,"operation")?)?;let v=get(&value,"payload")?;let mut out=vec![];
 match op{
  "policy"|"edge"=>{
   fields(v,if op=="policy"{&["policy","profiles","registry_snapshot","edges"]}else{&["edge","profiles","registry_snapshot"]})?;
   let profiles=get(v,"profiles")?;let snap=get(v,"registry_snapshot")?;assets(profiles,snap,&t,&i)?;
   if op=="policy"{policy(get(v,op)?,profiles,snap,get(v,"edges")?,&t,&i)?;}else{edge(get(v,op)?,profiles,snap,&t,&i)?;}
   out.push(("digest_hex",s(&hex(bytes(get(get(get(v,op)?,"header")?,"digest")?)?))));
  },
  "manifest"=>{fields(v,&["manifest"])?;manifest(get(v,"manifest")?,&t,&i)?;out.push(("digest_hex",s(&hex(bytes(get(get(get(v,"manifest")?,"header")?,"digest")?)?))));},
  "profile-refs"=>{fields(v,&["profile","registry_snapshot"])?;let p=get(v,"profile")?;super::method_rules::asset_rules(p,get(v,"registry_snapshot")?,&i)?;parameter_refs(p)?;},
  "profile-lookup"=>{fields(v,&["profile","registry_snapshot","slot"])?;typed(get(v,"slot")?,&s("SlotR7"),&t,&i)?;snapshot(get(v,"registry_snapshot")?,&t,&i)?;selected(get(v,"slot")?,get(v,"profile")?,get(v,"registry_snapshot")?)?;out.push(("admissible",V::B(admissible(get(v,"profile")?,get(v,"registry_snapshot")?)?)));},
  "events"=>{fields(v,&["events"])?;let events=arr(get(v,"events")?)?;for e in events{event_subject(e,&t,&i)?;}out.push(("events",V::N(events.len() as i128)));},
  "applicability-test"=>{let a=applicability(v,&t,&i)?;for key in ["degradation_authorized","test_slot_enabled","scope_covered","effects_covered","bound_scope_window_ok","required_draws_within_limit","invalid_sample_limit_ok"]{if let Ok(x)=get(&a,key){out.push((key,x.clone()));}}},
  _=>return Err("unknown registration asset operation".into()),
 }
 out.extend(vec![("operation",s(op)),("schema_lock_sha256",s(pin)),("full_schema_valid",V::B(false)),("full_phase_i_replay",V::B(false)),("source_authentication",V::B(false)),("production_admission",V::B(false))]);Ok(map(out))
}
