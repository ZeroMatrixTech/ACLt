// SPDX-License-Identifier: Apache-2.0
// FM-S1a uses this independent Rust CBOR/NFC/SHA core; no Python subprocess.
use super::*;
use std::fs;
use std::os::unix::fs::DirBuilderExt;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
const SUITE:&str="fm.rsa2048-pkcs1v15-sha256@1";
const PTAG:&str="ACLt/FM/S1a/Principal/1";
const ITAG:&str="ACLt/FM/S1a/KeyIdentity/1";
const STAG:&str="ACLt/FM/S1a/SignatureInput/1";
const IID:&str="acl.fm.schema.value@1";
const ISOURCE:&[u8]=b"ACLt FM-S1a test value v1: closed map {operation:REQUEST|ACCEPT|RESULT,count:uint,offset:int,ratio:Rational,version:SemVer,enabled:bool,label:NFC text,members:Set<text>}.";
fn base()->Vec<(&'static str,&'static str)>{vec![("schema_version","uint"),("encoding_profile_id","text"),("protocol_version","semver"),("network_id","digest"),("deployment_id","digest")]}
fn unsigned_fields()->Vec<(&'static str,&'static str)>{let mut f=base();f.extend([("suite","text"),("principal_ref","digest"),("role","role"),("object_type","text"),("context","digest"),("nonce","digest"),("issued_at","int"),("expires_at","int"),("payload_ref","fm-import"),("payload","bytes")]);f}
fn schema(kind:&str)->Option<Vec<(&'static str,&'static str)>>{
 Some(match kind {
 "fm-value"=>vec![("operation","operation"),("count","uint"),("offset","int"),("ratio","rational"),("version","semver"),("enabled","bool"),("label","text"),("members","text-set")],
 "fm-principal"=>{let mut f=base();f.extend([("principal_id","digest"),("key_id","digest"),("public_key_der","bytes"),("role","role"),("suite","text"),("valid_from","int"),("valid_until","int"),("status","status")]);f},
 "fm-signing"=>unsigned_fields(),
 "fm-envelope"=>{let mut f=unsigned_fields();f.push(("signature","bytes"));f},
 "fm-import"=>vec![("id","text"),("version","semver"),("digest","digest")],
 "fm-expected"=>vec![("protocol_version","semver"),("network_id","digest"),("deployment_id","digest"),("role","role"),("object_type","text"),("context","digest"),("nonce","digest"),("record_digest","digest")],
 "fm-verify"=>vec![("record","fm-principal"),("envelope","fm-envelope"),("expected","fm-expected"),("now","int")],
 _=>return None})
}
fn proj(kind:&str,v:&V,reverse:bool)->R<V>{
 if let Some(fs)=schema(kind){fields(v,&fs.iter().map(|x|x.0).collect::<Vec<_>>())?;let mut out=Vec::new();for(k,t) in fs{out.push((k,proj(t,get(v,k)?,reverse)?));}return Ok(map(out));}
 let values:&[&str]=match kind{"fm-role"|"role"=>&["REQUESTER","PROVIDER"],"operation"=>&["REQUEST","ACCEPT","RESULT"],"status"=>&["ACTIVE"],_=>&[]};
 if !values.is_empty(){need(values.contains(&txt(v)?),"unknown ENUM")?;return Ok(v.clone());}
 let result=project(kind,v,reverse)?;
 if kind=="text-set"{let a=arr(if reverse{&result}else{v})?;for w in a.windows(2){need(encode(&w[0])?<encode(&w[1])?,"set order/duplicate")?;}}
 Ok(result)
}
fn common(v:&V)->R<()>{need(integer(get(v,"schema_version")?)?==1&&txt(get(v,"encoding_profile_id")?)?==ENC,"schema/encoding version")?;need(get(v,"protocol_version")?==&V::A(vec![V::N(0),V::N(5),V::N(0)]),"protocol version")}
fn principal(v:&V)->R<()>{
 proj("fm-principal",v,false)?;common(v)?;
 let der=bytes(get(v,"public_key_der")?)?;let prefix=unhex("30820122300d06092a864886f70d01010105000382010f003082010a0282010100")?;let suffix=unhex("0203010001")?;
 need(der.len()==294&&der.starts_with(&prefix)&&der.ends_with(&suffix),"RSA SPKI encoding")?;
 let modulus=&der[prefix.len()..der.len()-suffix.len()];need(modulus.len()==256&&modulus[0]&128!=0&&modulus[255]&1!=0,"RSA modulus")?;
 need(txt(get(v,"suite")?)?==SUITE&&bytes(get(v,"key_id")?)?==sha256::hash(der),"key/suite")?;
 need(bytes(get(v,"principal_id")?)?==domain(ITAG,der),"principal identity")?;
 let start=integer(get(v,"valid_from")?)?;need(start>=0&&start<integer(get(v,"valid_until")?)?,"validity interval")
}
fn principal_hash(v:&V)->R<Vec<u8>>{principal(v)?;Ok(domain(PTAG,&encode(v)?))}
fn unsigned(v:&V)->R<()>{
 proj("fm-signing",v,false)?;common(v)?;
 need(txt(get(v,"suite")?)?==SUITE&&txt(get(v,"object_type")?)?=="FM_TEST_VALUE","suite/object type")?;
 let start=integer(get(v,"issued_at")?)?;need(start>=0&&start<integer(get(v,"expires_at")?)?,"message interval")?;
 let import=get(v,"payload_ref")?;need(txt(get(import,"id")?)?==IID&&get(import,"version")?==&V::A(vec![V::N(1),V::N(0),V::N(0)])&&bytes(get(import,"digest")?)?==sha256::hash(ISOURCE),"unlocked import")?;
 let raw=bytes(get(v,"payload")?)?;need(raw.len()<=4096,"payload byte limit")?;let payload=decode(raw)?;proj("fm-value",&payload,false)?;
 let op=txt(get(&payload,"operation")?)?;let role=txt(get(v,"role")?)?;
 need(if role=="REQUESTER"{op=="REQUEST"}else{["ACCEPT","RESULT"].contains(&op)},"role responsibility")
}
fn content(v:&V)->R<V>{let mut out=Vec::new();for (k,_) in unsigned_fields(){out.push((k,get(v,k)?.clone()));}Ok(map(out))}
fn message(v:&V)->R<Vec<u8>>{unsigned(v)?;let mut raw=vec![STAG.len() as u8];raw.extend(STAG.as_bytes());raw.extend(encode(v)?);Ok(raw)}
fn envelope(v:&V)->R<()>{proj("fm-envelope",v,false)?;unsigned(&content(v)?)?;need(bytes(get(v,"signature")?)?.len()==256,"signature width")}
// Temporary names are process-local implementation detail, never protocol time.
struct Temp(std::path::PathBuf);
impl Drop for Temp{fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}
fn crypto(der:&[u8],raw:&[u8],signature:&[u8])->R<()>{
 static SERIAL:AtomicU64=AtomicU64::new(0);
 let mut temp=None;
 for _ in 0..100{
  let name=format!("aclt-fm-{}-{}",std::process::id(),SERIAL.fetch_add(1,Ordering::Relaxed));let path=std::env::temp_dir().join(name);
  match fs::DirBuilder::new().mode(0o700).create(&path){Ok(())=>{temp=Some(Temp(path));break;},Err(e) if e.kind()==std::io::ErrorKind::AlreadyExists=>continue,Err(_)=>return Err("temporary directory".into())}
 }
 let tmp=temp.ok_or("temporary directory collisions")?;
 for (n,b) in [("key.der",der),("input.bin",raw),("sig.bin",signature)]{fs::write(tmp.0.join(n),b).map_err(|_|"temporary write")?;}
 let mut child=Command::new("openssl").args(["dgst","-sha256","-keyform","DER","-verify"]).arg(tmp.0.join("key.der")).args(["-sigopt","rsa_padding_mode:pkcs1","-signature"]).arg(tmp.0.join("sig.bin")).arg(tmp.0.join("input.bin")).stdout(Stdio::null()).stderr(Stdio::null()).spawn().map_err(|_|"crypto adapter unavailable")?;
 let deadline=std::time::Instant::now()+std::time::Duration::from_secs(10);
 loop{
  match child.try_wait(){Ok(Some(status))=>return need(status.success(),"signature verification"),Ok(None)=>{},Err(_)=>{let _=child.kill();let _=child.wait();return Err("crypto wait".into());}}
  if std::time::Instant::now()>=deadline{let _=child.kill();let _=child.wait();return Err("crypto timeout".into());}
  std::thread::sleep(std::time::Duration::from_millis(5));
 }
}
fn verify(v:&V)->R<V>{
 proj("fm-verify",v,false)?;let record=get(v,"record")?;let env=get(v,"envelope")?;let expected=get(v,"expected")?;let now=integer(get(v,"now")?)?;
 principal(record)?;envelope(env)?;let digest=principal_hash(record)?;
 need(bytes(get(expected,"record_digest")?)?==digest&&bytes(get(env,"principal_ref")?)?==digest,"untrusted principal pin")?;
 for k in ["protocol_version","network_id","deployment_id","role"]{need(get(record,k)?==get(env,k)?&&get(env,k)?==get(expected,k)?,"principal context")?;}
 for k in ["object_type","context","nonce"]{need(get(env,k)?==get(expected,k)?,"message context")?;}
 let start=integer(get(env,"issued_at")?)?;let end=integer(get(env,"expires_at")?)?;
 need(integer(get(record,"valid_from")?)?<=start&&start<=now&&now<end&&end<=integer(get(record,"valid_until")?)?,"expired/not-yet-valid")?;
 let raw=message(&content(env)?)?;crypto(bytes(get(record,"public_key_der")?)?,&raw,bytes(get(env,"signature")?)?)?;
 Ok(map(vec![("valid",V::B(true)),("record_digest_hex",s(&hex(&digest))),("signing_digest_hex",s(&hex(&sha256::hash(&raw))))]))
}
pub(super) fn run(mode:&str,input:&str)->R<V>{
 let kind=mode.strip_prefix("view-").unwrap_or(mode);
 need(["fm-value","fm-principal","fm-signing","fm-envelope","fm-verify","fm-role"].contains(&kind),"unknown FM kind")?;
 let raw=if mode.starts_with("view-"){encode(&proj(kind,&parse_json(input)?,true)?)?}else{unhex(input)?};let v=decode(&raw)?;proj(kind,&v,false)?;
 if kind=="fm-verify"{return verify(&v);}
 let mut out=vec![("cbor_hex",s(&hex(&encode(&v)?))),("schema_view",proj(kind,&v,false)?)];
 if kind=="fm-principal"{out.push(("digest_hex",s(&hex(&principal_hash(&v)?))));}
 if ["fm-signing","fm-envelope"].contains(&kind){if kind=="fm-envelope"{envelope(&v)?;}let raw=message(&content(&v)?)?;out.push(("signing_input_hex",s(&hex(&raw))));out.push(("digest_hex",s(&hex(&sha256::hash(&raw)))));}
 Ok(map(out))
}
