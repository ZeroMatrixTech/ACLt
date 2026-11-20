// SPDX-License-Identifier: Apache-2.0
// Independent FM-S1b validation; hypothetical amounts, no terminal/ledger writes.
use super::*;
const COMPONENTS:&[&str]=&["RIR","RUNTIME","PROVENANCE","EQUIVALENCE","EXPOSURE","AVAILABILITY","DEPLOYMENT_TEST","AUDIT_CONTRACT"];
const KINDS:&[&str]=&["LOGICAL","FUNDING","SETTLEMENT","RECEIPT","RIR","RUNTIME","PROVENANCE","EQUIVALENCE","EXPOSURE","AVAILABILITY","DEPLOYMENT_TEST","AUDIT_CONTRACT"];
const TERMINALS:&[&str]=&["UNRESOLVED","EXPIRED","FAILED","FUNDING_EXHAUSTED","REJECTED_AT_CREATE","FAILED_PLANNING","UNSUPPORTED"];
const STATUS:&[&str]=&["COMPLETE","MISSING","HOST_FAULT"];
const STAG:&str="ACLt/FM/S1b/ReceiptSignature/1";
fn base()->Vec<(&'static str,&'static str)>{vec![("schema_version","uint"),("encoding_profile_id","text"),("protocol_version","semver"),("network_id","digest"),("deployment_id","digest")]}
fn schema(k:&str)->Option<Vec<(&'static str,&'static str)>>{Some(match k{
 "scope"=>vec![("requester_ref","digest"),("nonce","digest"),("created_at","int"),("expires_at","int")],
 "ref"=>vec![("kind","ref-kind"),("version","semver"),("digest","digest")],
 "row"=>vec![("terminal","terminal"),("executor","fulfillment"),("auditor","fulfillment"),("storage","fulfillment"),("execution_fee","uint"),("verification_fee","uint"),("storage_fee","uint"),("refund_action","text")],
 "fm2-logical"=>{let mut x=base();x.extend([("object_type","text"),("object_version","semver"),("publisher_ref","digest"),("created_at","int"),("available_until","int"),("parents","refs"),("content","bytes")]);x},
 "fm2-funding"=>{let mut x=base();x.extend([("scope","scope"),("source","text"),("asset","text"),("execution_limit","uint"),("verification_limit","uint"),("storage_limit","uint"),("refund_reserve","uint"),("total_limit","uint")]);x},
 "fm2-settlement"=>{let mut x=base();x.extend([("scope","scope"),("method","text"),("rows","rows")]);x},
 "fm2-component"=>vec![("kind","component-kind"),("version","semver"),("content","bytes")],
 "execution"=>vec![("fuel","uint"),("memory_bytes","uint"),("input_bytes_limit","uint"),("output_bytes_limit","uint"),("max_assignments","uint"),("max_attempts","uint"),("message_retries","uint"),("recovery_queries","uint"),("deadline","int"),("capabilities","text-set"),("architecture","text"),("network","text"),("sandbox","text")],
 "fm2-receipt"=>{let mut x=base();x.extend([("scope","scope"),("task_family","text"),("entry","text"),("output_type","text"),("success","text"),("merge","text"),("failure","text"),("method","text"),("input_refs","refs"),("funding_ref","ref"),("settlement_ref","ref"),("component_refs","refs"),("execution","execution")]);x},
 "fm2-bundle"=>vec![("receipt","fm2-receipt"),("funding","fm2-funding"),("settlement","fm2-settlement"),("inputs","inputs"),("components","components")],
 "fm2-quote"=>vec![("bundle","fm2-bundle"),("terminal","terminal"),("executor","fulfillment"),("auditor","fulfillment"),("storage","fulfillment")],
 "fm2-verify"=>vec![("bundle","fm2-bundle"),("record","fm-principal"),("signature","bytes"),("expected_receipt","digest"),("expected_requester","digest"),("now","int")],
 _=>return None})}
fn proj(k:&str,v:&V,reverse:bool)->R<V>{
 if let Some(fs)=schema(k){fields(v,&fs.iter().map(|x|x.0).collect::<Vec<_>>())?;let mut a=Vec::new();for(n,t) in fs{a.push((n,proj(t,get(v,n)?,reverse)?));}return Ok(map(a));}
 let child=match k{"refs"=>Some("ref"),"rows"=>Some("row"),"inputs"=>Some("fm2-logical"),"components"=>Some("fm2-component"),_=>None};
 if let Some(t)=child{let a=arr(v)?;need(a.len()<=111,"array limit")?;return Ok(V::A(a.iter().map(|x|proj(t,x,reverse)).collect::<R<_>>()?));}
 let options=match k{"ref-kind"=>KINDS,"component-kind"=>COMPONENTS,"terminal"=>TERMINALS,"fulfillment"=>STATUS,_=>&[]};
 if !options.is_empty(){need(options.contains(&txt(v)?),"unknown ENUM")?;return Ok(v.clone());}
 fm::proj(k,v,reverse)
}
fn n(v:&V,k:&str)->R<i128>{integer(get(v,k)?)}
fn t<'a>(v:&'a V,k:&str)->R<&'a str>{txt(get(v,k)?)}
fn common(v:&V)->R<()>{need(n(v,"schema_version")?==1&&t(v,"encoding_profile_id")?==ENC&&get(v,"protocol_version")?==&V::A(vec![V::N(0),V::N(5),V::N(0)]),"header version")}
fn scope(v:&V)->R<()>{need(n(v,"created_at")?>=0&&n(v,"created_at")?<n(v,"expires_at")?,"scope interval")}
fn digest(k:&str,v:&V)->R<Vec<u8>>{Ok(domain(&format!("ACLt/FM/S1b/{k}/1"),&encode(v)?))}
fn reference(k:&str,v:&V)->R<V>{Ok(map(vec![("kind",s(k)),("version",V::A(vec![V::N(1),V::N(0),V::N(0)])),("digest",V::X(digest(k,v)?))]))}
fn check_ref(v:&V,k:&str)->R<()>{need(t(v,"kind")?==k&&get(v,"version")?==&V::A(vec![V::N(1),V::N(0),V::N(0)]),"reference kind/version")}
fn logical(v:&V)->R<()>{
 common(v)?;need(t(v,"object_type")?=="FM_STATS_I32_VECTOR"&&get(v,"object_version")?==&V::A(vec![V::N(1),V::N(0),V::N(0)]),"logical schema")?;
 need(arr(get(v,"parents")?)?.is_empty(),"initial input parents")?;need(n(v,"created_at")?>=0&&n(v,"created_at")?<n(v,"available_until")?,"availability interval")?;
 let raw=bytes(get(v,"content")?)?;let value=decode(raw)?;let a=arr(&value)?;need(!a.is_empty(),"input size")?;
 for x in a{need((i32::MIN as i128..=i32::MAX as i128).contains(&integer(x)?),"i32 input")?;}Ok(())
}
fn funding(v:&V)->R<()>{common(v)?;scope(get(v,"scope")?)?;need(t(v,"source")?=="REQUESTER_PREFUNDED"&&t(v,"asset")?=="FM_TEST_UNIT","source/asset")?;
 need(n(v,"execution_limit")?>0&&n(v,"verification_limit")?>0,"minimum process funding")?;
 let total=n(v,"execution_limit")?+n(v,"verification_limit")?+n(v,"storage_limit")?+n(v,"refund_reserve")?;need(total<=u64::MAX as i128&&total==n(v,"total_limit")?,"funding sum/overflow")}
fn row_key(v:&V)->R<V>{Ok(V::A(["terminal","executor","auditor","storage"].iter().map(|k|get(v,k).cloned()).collect::<R<_>>()?))}
fn matrix_keys()->R<Vec<Vec<u8>>>{let mut keys=Vec::new();for t in TERMINALS{if ["REJECTED_AT_CREATE","FAILED_PLANNING","UNSUPPORTED"].contains(t){keys.push(encode(&V::A(vec![s(t),s("MISSING"),s("MISSING"),s("MISSING")]))?);}else{for a in STATUS{for b in STATUS{for c in STATUS{keys.push(encode(&V::A(vec![s(t),s(a),s(b),s(c)]))?);}}}}}keys.sort();Ok(keys)}
fn settlement(v:&V)->R<()>{common(v)?;scope(get(v,"scope")?)?;need(t(v,"method")?=="REEXEC_AUDIT_ONLY","audit-only method")?;
 let rows=arr(get(v,"rows")?)?;let keys=rows.iter().map(|r|encode(&row_key(r)?)).collect::<R<Vec<_>>>()?;need(keys==matrix_keys()?,"missing/duplicate/unordered matrix cell")?;
 for r in rows{
  need(t(r,"refund_action")?=="RETURN_REMAINDER","refund rule")?;
  for (status,fee) in [("executor","execution_fee"),("auditor","verification_fee"),("storage","storage_fee")]{need(t(r,status)?=="COMPLETE"||n(r,fee)?==0,"missing/host fault is not fulfillment")?;}
  need(n(r,"execution_fee")?+n(r,"verification_fee")?+n(r,"storage_fee")?<=u64::MAX as i128,"fee sum overflow")?;
 }Ok(())
}
fn component(v:&V)->R<()>{let b=bytes(get(v,"content")?)?;need(get(v,"version")?==&V::A(vec![V::N(1),V::N(0),V::N(0)])&&!b.is_empty(),"component version/bytes")}
fn receipt(v:&V)->R<()>{common(v)?;scope(get(v,"scope")?)?;
 for(k,x) in [("task_family","stats-int-v1"),("entry","stats_int_v1"),("output_type","FM_STATS_INT_RESULT"),("success","EXACT_TASK_OUTCOME"),("merge","SINGLE_ASSIGNMENT"),("failure","FROZEN_AUDIT_MAPPING"),("method","REEXEC_AUDIT_ONLY")]{need(t(v,k)?==x,"unsupported receipt semantics")?;}
 let inputs=arr(get(v,"input_refs")?)?;need(inputs.len()==1,"one immutable input")?;check_ref(&inputs[0],"LOGICAL")?;check_ref(get(v,"funding_ref")?,"FUNDING")?;check_ref(get(v,"settlement_ref")?,"SETTLEMENT")?;
 let refs=arr(get(v,"component_refs")?)?;need(refs.len()==COMPONENTS.len(),"component imports count")?;for (r,k) in refs.iter().zip(COMPONENTS){check_ref(r,k)?;}
 let e=get(v,"execution")?;
 need(n(e,"fuel")?>0&&n(e,"memory_bytes")?>0&&n(e,"input_bytes_limit")?>0&&n(e,"output_bytes_limit")?>0,"resource limits")?;
 need(n(e,"max_assignments")?==2&&n(e,"max_attempts")?==1&&(1..=16).contains(&n(e,"message_retries")?)&&(1..=32).contains(&n(e,"recovery_queries")?),"finite execution/recovery")?;
 let sc=get(v,"scope")?;need(n(sc,"created_at")?<n(e,"deadline")?&&n(e,"deadline")?<=n(sc,"expires_at")?,"receipt deadline")?;
 need(arr(get(e,"capabilities")?)?.is_empty()&&t(e,"architecture")?=="wasm32"&&t(e,"network")?=="DENY"&&t(e,"sandbox")?=="REQUIRED","environment/effects")
}
fn validate(k:&str,v:&V)->R<()>{proj(k,v,false)?;match k{"fm2-logical"=>logical(v),"fm2-funding"=>funding(v),"fm2-settlement"=>settlement(v),"fm2-component"=>component(v),"fm2-receipt"=>receipt(v),_=>Ok(())}}
fn bundle(v:&V)->R<Vec<u8>>{
 validate("fm2-bundle",v)?;let r=get(v,"receipt")?;receipt(r)?;
 for (name,k) in [("funding","FUNDING"),("settlement","SETTLEMENT")]{let obj=get(v,name)?;validate(&format!("fm2-{name}"),obj)?;
  for (field,_) in base(){need(get(obj,field)?==get(r,field)?,"foreign policy header")?;}
  need(get(obj,"scope")?==get(r,"scope")?,"foreign policy scope")?;need(same_reference(get(r,&format!("{name}_ref"))?,&reference(k,obj)?)?,"stale policy reference")?;
 }
 let inputs=arr(get(v,"inputs")?)?;let comps=arr(get(v,"components")?)?;need(inputs.len()==1&&comps.len()==COMPONENTS.len(),"unavailable/extra object")?;
 let obj=&inputs[0];validate("fm2-logical",obj)?;
 for (field,_) in base(){need(get(obj,field)?==get(r,field)?,"input context")?;}
 need(get(obj,"publisher_ref")?==get(get(r,"scope")?,"requester_ref")?,"input owner")?;
 need(n(obj,"created_at")?<=n(get(r,"scope")?,"created_at")?&&n(obj,"available_until")?>=n(get(r,"execution")?,"deadline")?,"input unavailable interval")?;
 need(bytes(get(obj,"content")?)?.len() as i128<=n(get(r,"execution")?,"input_bytes_limit")?&&same_reference(&arr(get(r,"input_refs")?)?[0],&reference("LOGICAL",obj)?)?,"input content/reference")?;
 for ((obj,rr),kind) in comps.iter().zip(arr(get(r,"component_refs")?)?).zip(COMPONENTS){validate("fm2-component",obj)?;need(t(obj,"kind")?==*kind&&same_reference(rr,&reference(kind,obj)?)?,"unavailable/stale component")?;}
 let funding=get(v,"funding")?;
 for row in arr(get(get(v,"settlement")?,"rows")?)?{
  for(fee,limit) in [("execution_fee","execution_limit"),("verification_fee","verification_limit"),("storage_fee","storage_limit")]{need(n(row,fee)?<=n(funding,limit)?,"bucket over-budget")?;}
  need(n(row,"execution_fee")?+n(row,"verification_fee")?+n(row,"storage_fee")?+n(funding,"refund_reserve")?<=n(funding,"total_limit")?,"refund reserve over-budget")?;
 }digest("RECEIPT",r)
}
fn message(v:&V)->R<Vec<u8>>{bundle(v)?;let mut raw=vec![STAG.len()as u8];raw.extend(STAG.as_bytes());raw.extend(encode(get(v,"receipt")?)?);Ok(raw)}
fn quote(v:&V)->R<V>{let b=get(v,"bundle")?;let rid=bundle(b)?;let key=row_key(v)?;let mut row=None;
 for x in arr(get(get(b,"settlement")?,"rows")?)?{if row_key(x)?==key{row=Some(x);break;}}
 let r=row.ok_or("matrix cell")?;let a=n(r,"execution_fee")?;let bb=n(r,"verification_fee")?;let c=n(r,"storage_fee")?;let amounts=map(vec![("execution_fee",s(&a.to_string())),("verification_fee",s(&bb.to_string())),("storage_fee",s(&c.to_string()))]);
 Ok(map(vec![("receipt_digest_hex",s(&hex(&rid))),("amounts",amounts),("refund",s(&(n(get(b,"funding")?,"total_limit")?-a-bb-c).to_string())),("scope",s("HYPOTHETICAL_ONLY_NO_ENTITLEMENT"))]))
}
fn verify(v:&V)->R<V>{let b=get(v,"bundle")?;let rid=bundle(b)?;let r=get(b,"receipt")?;let record=get(v,"record")?;let pin=fm::principal_hash(record)?;
 need(digest_consistency(bytes(get(v,"expected_requester")?)?==pin)&&digest_consistency(bytes(get(get(r,"scope")?,"requester_ref")?)?==pin),"requester pin")?;need(digest_consistency(bytes(get(v,"expected_receipt")?)?==rid),"caller receipt commitment")?;
 need(t(record,"role")?=="REQUESTER","requester role")?;for k in ["protocol_version","network_id","deployment_id"]{need(get(record,k)?==get(r,k)?,"requester context")?;}
 let start=n(get(r,"scope")?,"created_at")?;need(n(record,"valid_from")?<=start&&start<=n(v,"now")?&&n(v,"now")?<n(get(r,"execution")?,"deadline")?&&n(get(r,"execution")?,"deadline")?<=n(record,"valid_until")?,"signature validity")?;
 let sig=bytes(get(v,"signature")?)?;need(sig.len()==256,"signature width")?;fm::crypto(bytes(get(record,"public_key_der")?)?,&message(b)?,sig)?;
 Ok(map(vec![("valid",V::B(true)),("receipt_digest_hex",s(&hex(&rid))),("requester_digest_hex",s(&hex(&pin)))]))
}
pub(super) fn run(mode:&str,input:&str)->R<V>{
 let k=mode.strip_prefix("view-").unwrap_or(mode);need(["fm2-logical","fm2-funding","fm2-settlement","fm2-component","fm2-receipt","fm2-bundle","fm2-quote","fm2-verify"].contains(&k),"unknown S1b kind")?;
 let raw=if mode.starts_with("view-"){encode(&proj(k,&parse_json(input)?,true)?)?}else{unhex(input)?};let v=decode(&raw)?;validate(k,&v)?;
 if k=="fm2-quote"{return quote(&v);}if k=="fm2-verify"{return verify(&v);}
 let mut result=vec![("cbor_hex",s(&hex(&encode(&v)?))),("schema_view",proj(k,&v,false)?)];
 let hash=if k=="fm2-bundle"{result.push(("signing_input_hex",s(&hex(&message(&v)?))));bundle(&v)?}else{let kind=match k{"fm2-logical"=>"LOGICAL","fm2-funding"=>"FUNDING","fm2-settlement"=>"SETTLEMENT","fm2-receipt"=>"RECEIPT",_=>t(&v,"kind")?};digest(kind,&v)?};
 result.push(("digest_hex",s(&hex(&hash))));Ok(map(result))
}
