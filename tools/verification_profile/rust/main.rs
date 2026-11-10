// SPDX-License-Identifier: Apache-2.0
// Independent candidate slice implementation. No Python subprocess or shared codec.
mod sha256;
mod nfc;
mod fm;
mod fm_policy;
mod profile;
mod registration;
mod method_rules;
mod creation;
mod selection;
mod commitments;
mod runtime_bindings;
mod decision_replay;
mod phase_d_contract;
use std::io::{self,BufRead};
pub(crate) type R<T> = Result<T,String>;
const MAX:usize=1<<20;
const ENC:&str="acl.enc.p0-1@1";
const IMPORT_ID:&str="acl.schema.claim-test-bytes@1";
const IMPORT_SOURCE:&[u8]=b"ACLt local test import v1: payload is canonical CBOR bstr; object_digest is SHA256 of canonical_bytes.";
#[derive(Clone,Debug,PartialEq)]
pub(crate) enum V { N(i128), B(bool), S(String), X(Vec<u8>), A(Vec<V>), M(Vec<(V,V)>) }
pub(crate) fn need(ok:bool,msg:&str)->R<()> {if ok {Ok(())}else{Err(msg.into())}}
pub(crate) fn s(v:&str)->V {V::S(v.into())}
pub(crate) fn map(items:Vec<(&str,V)>)->V {V::M(items.into_iter().map(|(k,v)|(s(k),v)).collect())}
pub(crate) fn txt(v:&V)->R<&str>{if let V::S(x)=v {need(nfc::is_nfc(x),"NFC")?;Ok(x)}else{Err("text".into())}}
pub(crate) fn arr(v:&V)->R<&[V]>{if let V::A(a)=v {Ok(a)}else{Err("array".into())}}
pub(crate) fn bytes(v:&V)->R<&[u8]>{if let V::X(x)=v {Ok(x)}else{Err("bstr".into())}}
pub(crate) fn integer(v:&V)->R<i128>{if let V::N(n)=v {Ok(*n)}else{Err("integer".into())}}
pub(crate) fn get<'a>(v:&'a V,key:&str)->R<&'a V>{get_key(v,&s(key))}
fn get_key<'a>(v:&'a V,key:&V)->R<&'a V>{if let V::M(m)=v {m.iter().find(|(k,_)|k==key).map(|(_,v)|v).ok_or("missing key".into())}else{Err("map".into())}}
pub(crate) fn fields(v:&V,keys:&[&str])->R<()> {if let V::M(m)=v {need(m.len()==keys.len(),"field count")?;for k in keys {get(v,k)?;}Ok(())}else{Err("fields".into())}}
fn uint(v:&V)->R<()> {need((0..=u64::MAX as i128).contains(&integer(v)?),"uint64")}
fn dig(v:&V)->R<()> {need(bytes(v)?.len()==32,"digest length")}
fn semver(v:&V)->R<()> {let a=arr(v)?;need(a.len()==3,"SemVer")?;for x in a {uint(x)?;}Ok(())}
fn tid(v:&V)->R<()> {let id=txt(v)?.strip_prefix("acl.ct.").ok_or("template id")?;need(!id.is_empty()&&id.len()<=63&&id.as_bytes()[0].is_ascii_lowercase()&&id.bytes().all(|b|b.is_ascii_lowercase()||b.is_ascii_digit()||b==b'-'),"template id")}
fn argument(out:&mut Vec<u8>,major:u8,n:u64){
    if n<24 {out.push(major*32+n as u8);}else{let width=if n<256{1}else if n<65536{2}else if n<1<<32{4}else{8};out.push(major*32+match width{1=>24,2=>25,4=>26,_=>27});out.extend_from_slice(&n.to_be_bytes()[8-width..]);}
}
pub(crate) fn encode(v:&V)->R<Vec<u8>> {fn go(v:&V,d:usize)->R<Vec<u8>>{
    need(d<=48,"depth")?;let mut out=Vec::new();match v {
        V::N(n)=>{need(*n>=i64::MIN as i128&&*n<=u64::MAX as i128,"integer range")?;if *n>=0{argument(&mut out,0,*n as u64)}else{argument(&mut out,1,(-1-*n)as u64)}},
        V::B(b)=>out.push(if *b{245}else{244}),
        V::X(x)=>{argument(&mut out,2,x.len()as u64);out.extend(x);},
        V::S(t)=>{need(nfc::is_nfc(t),"NFC")?;argument(&mut out,3,t.len()as u64);out.extend(t.as_bytes());},
        V::A(a)=>{need(a.len()<=10000,"items")?;argument(&mut out,4,a.len()as u64);for x in a {out.extend(go(x,d+1)?);}},
        V::M(m)=>{need(m.len()<=10000,"items")?;let mut p=Vec::new();for(k,v)in m {need(matches!(k,V::S(_)|V::N(_)),"key")?;p.push((go(k,d+1)?,go(v,d+1)?));}p.sort_by(|a,b|a.0.cmp(&b.0));need(p.windows(2).all(|w|w[0].0<w[1].0),"duplicate key")?;argument(&mut out,5,p.len()as u64);for(k,v)in p{out.extend(k);out.extend(v);}}
    }need(out.len()<=MAX,"size")?;Ok(out)
}go(v,0)}
struct Reader<'a>{raw:&'a[u8],pos:usize,items:usize}
impl<'a> Reader<'a>{
 fn take(&mut self,n:usize)->R<&'a[u8]>{need(n<=self.raw.len()-self.pos,"truncated")?;let r=&self.raw[self.pos..self.pos+n];self.pos+=n;Ok(r)}
 fn read(&mut self,depth:usize)->R<V>{need(depth<=48,"depth")?;self.items+=1;need(self.items<=10000,"items")?;let first=self.take(1)?[0];let major=first>>5;let ai=first&31;
    if major==7 {need(ai==20||ai==21,"simple/float")?;return Ok(V::B(ai==21));}
    need(major<=5&&ai<=27,"tag/indefinite")?;
    let n=if ai<24 {ai as u64}else{let width=1usize<<(ai-24);let mut v=0u64;for b in self.take(width)? {v=(v<<8)|*b as u64;}let min=match width{1=>24,2=>256,4=>65536,_=>1u64<<32};need(v>=min,"shortest")?;v};
    match major {
      0=>Ok(V::N(n as i128)),1=>{need(n<=i64::MAX as u64,"int64")?;Ok(V::N(-1-n as i128))},
      2|3=>{need(n<=MAX as u64,"size")?;let raw=self.take(n as usize)?;if major==2{Ok(V::X(raw.to_vec()))}else{let t=std::str::from_utf8(raw).map_err(|_|"UTF-8")?;need(nfc::is_nfc(t),"NFC")?;Ok(s(t))}},
      4=>{need(n<=10000,"items")?;let mut a=Vec::new();for _ in 0..n {a.push(self.read(depth+1)?);}Ok(V::A(a))},
      5=>{need(n<=10000,"items")?;let mut m=Vec::new();let mut last:Option<Vec<u8>>=None;for _ in 0..n{let start=self.pos;let key=self.read(depth+1)?;need(matches!(key,V::S(_)|V::N(_)),"key")?;let wire=self.raw[start..self.pos].to_vec();if let Some(l)=last{need(l<wire,"map order/duplicate")?;}last=Some(wire);m.push((key,self.read(depth+1)?));}Ok(V::M(m))},_=>Err("major".into())
    }
 }
}
pub(crate) fn decode(raw:&[u8])->R<V>{need(raw.len()<=MAX,"size")?;let mut r=Reader{raw,pos:0,items:0};let v=r.read(0)?;need(r.pos==raw.len(),"trailing")?;Ok(v)}
pub(crate) fn hex(raw:&[u8])->String{raw.iter().map(|b|format!("{b:02x}")).collect()}
fn unhex(t:&str)->R<Vec<u8>>{need(t.len()%2==0&&t.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b)),"hex")?;(0..t.len()).step_by(2).map(|i|u8::from_str_radix(&t[i..i+2],16).map_err(|_|"hex".into())).collect()}
fn ordered(v:&V,key:&str)->R<()> {let mut last=None;for row in arr(v)? {let cur=encode(get(row,key)?)?;if let Some(prior)=last {need(prior<cur,"pair order")?;}last=Some(cur);}Ok(())}
fn reference(v:&V)->R<()> {fields(v,&["id","version","digest"])?;tid(get(v,"id")?)?;semver(get(v,"version")?)?;dig(get(v,"digest")?)}
pub(crate) fn domain(tag:&str,raw:&[u8])->Vec<u8>{let mut x=vec![tag.len()as u8];x.extend(tag.as_bytes());x.extend(raw);sha256::hash(&x)}
fn content(v:&V)->R<V>{let h=get(v,"header")?;Ok(map(vec![("schema_version",get(h,"schema_version")?.clone()),("encoding_profile_id",get(h,"encoding_profile_id")?.clone()),("normative_text",get(v,"normative_text")?.clone()),("slot_decls",get(v,"slot_decls")?.clone())]))}
fn template_hash(v:&V)->R<Vec<u8>>{Ok(domain("ACLt/P0-1/ClaimTemplate/1",&encode(&content(v)?)?))}
fn template(v:&V)->R<()> {
 fields(v,&["header","normative_text","slot_decls","translations"])?;let h=get(v,"header")?;
 fields(h,&["schema_version","encoding_profile_id","id","version","digest"])?;
 need(integer(get(h,"schema_version")?)?==1,"schema version")?;need(txt(get(h,"encoding_profile_id")?)?==ENC,"encoding version")?;tid(get(h,"id")?)?;semver(get(h,"version")?)?;dig(get(h,"digest")?)?;txt(get(v,"normative_text")?)?;
 for row in arr(get(v,"slot_decls")?)? {fields(row,&["slot","decl"])?;need(!txt(get(row,"slot")?)?.is_empty(),"empty slot")?;let d=get(row,"decl")?;fields(d,&["kind","value_type","source"])?;
 let k=txt(get(d,"kind")?)?;let t=txt(get(d,"value_type")?)?;let src=txt(get(d,"source")?)?;
 need(["OBJECT_REF","DIGEST","VERSION","REF"].contains(&t),"slot type")?;
 need((k=="STATIC"&&src=="PROFILE")||(k=="RUNTIME"&&["RECEIPT","EVIDENCE_CHAIN","SNAPSHOT"].contains(&src)),"slot kind/source")?;}
 ordered(get(v,"slot_decls")?,"slot")?;
 for row in arr(get(v,"translations")?)? {fields(row,&["lang","text"])?;need(!txt(get(row,"lang")?)?.is_empty(),"lang")?;txt(get(row,"text")?)?;}
 ordered(get(v,"translations")?,"lang")?;need(bytes(get(h,"digest")?)?==template_hash(v)?,"template digest")
}
fn claim(v:&V)->R<()> {
 let a=arr(v)?;need(a.len()==2,"claim tuple")?;reference(&a[0])?;
 for row in arr(&a[1])? {fields(row,&["slot_id","value"])?;need(!txt(get(row,"slot_id")?)?.is_empty(),"slot")?;let e=get(row,"value")?;fields(e,&["schema_ref","canonical_bytes","object_digest"])?;let r=get(e,"schema_ref")?;
 fields(r,&["id","version","digest"])?;need(txt(get(r,"id")?)?==IMPORT_ID,"import id")?;need(get(r,"version")?==&V::A(vec![V::N(1),V::N(0),V::N(0)]),"import version")?;need(bytes(get(r,"digest")?)?==sha256::hash(IMPORT_SOURCE),"import digest")?;
 let raw=bytes(get(e,"canonical_bytes")?)?;need(matches!(decode(raw)?,V::X(_)),"import payload")?;dig(get(e,"object_digest")?)?;need(bytes(get(e,"object_digest")?)?==sha256::hash(raw),"object digest")?;}
 ordered(&a[1],"slot_id")
}
fn claim_hash(v:&V)->R<Vec<u8>>{Ok(domain("ACLt/P0-1/RenderedClaim/1",&encode(v)?))}
fn chain(v:&V)->R<()> {
 fields(v,&["template","claim_input","rendered_claim_digest"])?;let t=get(v,"template")?;let c=get(v,"claim_input")?;template(t)?;claim(c)?;
 let h=get(t,"header")?;let ca=arr(c)?;for key in ["id","version","digest"] {need(get(&ca[0],key)?==get(h,key)?,"reference mismatch")?;}
 let a=arr(get(t,"slot_decls")?)?;let b=arr(&ca[1])?;need(a.len()==b.len(),"slots")?;for (x,y) in a.iter().zip(b) {need(get(x,"slot")?==get(y,"slot_id")?,"slot mismatch")?;}
 dig(get(v,"rendered_claim_digest")?)?;need(bytes(get(v,"rendered_claim_digest")?)?==claim_hash(c)?,"claim digest")
}
fn schema_fields(kind:&str)->Option<Vec<(&str,&str)>> {Some(match kind {
 "template"=>vec![("header","header"),("normative_text","text"),("slot_decls","slots"),("translations","translations")],
 "header"=>vec![("schema_version","uint"),("encoding_profile_id","text"),("id","text"),("version","semver"),("digest","digest")],
 "reference"=>vec![("id","text"),("version","semver"),("digest","digest")],
 "slot"=>vec![("slot","text"),("decl","decl")],
 "decl"=>vec![("kind","text"),("value_type","text"),("source","text")],
 "translation"=>vec![("lang","text"),("text","text")],
 "binding"=>vec![("slot_id","text"),("value","external")],
 "external"=>vec![("schema_ref","reference"),("canonical_bytes","bytes"),("object_digest","digest")],
 "chain"=>vec![("template","template"),("claim_input","claim"),("rendered_claim_digest","digest")],
 _=>return None})}
fn gcd(mut a:u128,mut b:u128)->u128{while b!=0 {let r=a%b;a=b;b=r;}a}
fn project(kind:&str,v:&V,reverse:bool)->R<V>{
 if let Some(fs)=schema_fields(kind) {fields(v,&fs.iter().map(|x|x.0).collect::<Vec<_>>())?;let mut out=Vec::new();for(k,t) in fs{out.push((k,project(t,get(v,k)?,reverse)?));}return Ok(map(out));}
 match kind {
 "text"=>Ok(s(txt(v)?)),
 "bool"=>{need(matches!(v,V::B(_)),"bool")?;Ok(v.clone())},
 "uint"|"int"=>{let n=if reverse {let st=txt(v)?;need(st.len()<=21,"decimal length")?;let n=st.parse::<i128>().map_err(|_|"decimal")?;need(n.to_string()==st,"decimal canonical")?;n}else{integer(v)?};need(if kind=="uint"{n>=0&&n<=u64::MAX as i128}else{n>=i64::MIN as i128&&n<=i64::MAX as i128},"integer range")?;Ok(if reverse{V::N(n)}else{s(&n.to_string())})},
 "bytes"|"digest"=>{let b=if reverse {unhex(txt(v)?)?}else{bytes(v)?.to_vec()};if kind=="digest"{need(b.len()==32,"digest length")?;}Ok(if reverse{V::X(b)}else{s(&hex(&b))})},
 "slots"|"translations"|"bindings"|"text-set"=>{let child=match kind{"slots"=>"slot","translations"=>"translation","bindings"=>"binding",_=>"text"};Ok(V::A(arr(v)?.iter().map(|x|project(child,x,reverse)).collect::<R<_>>()?))},
 "semver"|"rational"|"claim"=>{let types=match kind{"semver"=>vec!["uint","uint","uint"],"rational"=>vec!["int","uint"],_=>vec!["reference","bindings"]};let a=arr(v)?;need(a.len()==types.len(),"tuple length")?;let out=V::A(a.iter().zip(types).map(|(x,t)|project(t,x,reverse)).collect::<R<_>>()?);
 if kind=="rational"{let n=arr(if reverse{&out}else{v})?;let a=integer(&n[0])?;let b=integer(&n[1])?;need(b>0&&gcd(a.unsigned_abs(),b as u128)==1,"reduced Rational")?;}Ok(out)},
 "version-range"=>{let m=if let V::M(m)=v {m}else{return Err("map".into())};need(m.len()==1||m.len()==2,"range fields")?;let mut out=Vec::new();for (i,key) in [(0,"min_inclusive"),(1,"max_exclusive")] {let source=if reverse{s(key)}else{V::N(i)};match get_key(v,&source){Ok(x)=>out.push((if reverse{V::N(i)}else{s(key)},project("semver",x,reverse)?)),Err(_)=>need(i==1,"min bound")?,}}
 need(out.len()==m.len(),"unknown range key")?;let result=V::M(out);let native=if reverse{&result}else{v};if let Ok(max)=get_key(native,&V::N(1)){let numbers=|x:&V|->R<Vec<i128>>{arr(x)?.iter().map(integer).collect()};need(numbers(get_key(native,&V::N(0))?)?<numbers(max)?,"range order")?;}Ok(result)},
 _=>Err("unknown kind".into())
 }
}
fn validate(kind:&str,v:&V)->R<()> {
 project(kind,v,false)?;match kind{"template"=>template(v),"claim"=>claim(v),"chain"=>chain(v),"text-set"=>{let a=arr(v)?;for w in a.windows(2){need(encode(&w[0])?<encode(&w[1])?,"set order")?;}Ok(())},_=>Ok(())}
}
fn quote(s:&str)->String {let mut out=String::from("\"");for c in s.chars(){match c{'"'=>out.push_str("\\\""),'\\'=>out.push_str("\\\\"),'\n'=>out.push_str("\\n"),'\r'=>out.push_str("\\r"),'\t'=>out.push_str("\\t"),c if c<' '=>out.push_str(&format!("\\u{:04x}",c as u32)),c=>out.push(c)}}out.push('"');out}
fn json(v:&V)->String{match v{V::S(t)=>quote(t),V::B(b)=>b.to_string(),V::N(n)=>n.to_string(),V::X(b)=>quote(&hex(b)),V::A(a)=>format!("[{}]",a.iter().map(json).collect::<Vec<_>>().join(",")),V::M(m)=>format!("{{{}}}",m.iter().map(|(k,v)|format!("{}:{}",json(k),json(v))).collect::<Vec<_>>().join(","))}}
// Schema View JSON parser accepts only strings, booleans, arrays, and string-key maps.
// Integers must be strings. Duplicate fields, invalid Unicode and null are rejected.
struct J<'a>{b:&'a[u8],p:usize,n:usize}
impl J<'_>{
 fn ws(&mut self){while self.p<self.b.len()&&matches!(self.b[self.p],b' '|b'\n'|b'\r'|b'\t'){self.p+=1;}}
 fn next(&mut self)->R<u8>{need(self.p<self.b.len(),"JSON EOF")?;let c=self.b[self.p];self.p+=1;Ok(c)}
 fn u16(&mut self)->R<u32>{let mut n=0;for _ in 0..4 {let c=self.next()? as char;n=n*16+c.to_digit(16).ok_or("JSON hex")?;}Ok(n)}
 fn string(&mut self)->R<String>{need(self.next()?==b'"',"JSON string")?;let mut out=Vec::new();loop{match self.next()?{
 b'"'=>break,b'\\'=>{let c=self.next()?;match c{b'"'|b'\\'|b'/'=>out.push(c),b'b'=>out.push(8),b'f'=>out.push(12),b'n'=>out.push(10),b'r'=>out.push(13),b't'=>out.push(9),b'u'=>{let mut n=self.u16()?;if (0xd800..=0xdbff).contains(&n){need(self.next()?==b'\\'&&self.next()?==b'u',"surrogate pair")?;let low=self.u16()?;need((0xdc00..=0xdfff).contains(&low),"surrogate")?;n=0x10000+(n-0xd800)*1024+low-0xdc00;}let ch=char::from_u32(n).ok_or("Unicode")?;let mut bytes=[0u8;4];out.extend(ch.encode_utf8(&mut bytes).as_bytes());},_=>return Err("escape".into())}},c=>{need(c>=32,"control")?;out.push(c);}}}String::from_utf8(out).map_err(|_|"UTF-8".into())}
 fn value(&mut self,d:usize)->R<V>{need(d<=48,"JSON depth")?;self.n+=1;need(self.n<=10000,"JSON items")?;self.ws();need(self.p<self.b.len(),"JSON EOF")?;match self.b[self.p]{
 b'"'=>Ok(s(&self.string()?)),b't'|b'f'=>{let word=if self.b[self.p]==b't'{"true"}else{"false"};need(self.b[self.p..].starts_with(word.as_bytes()),"boolean")?;self.p+=word.len();Ok(V::B(word=="true"))},
 b'['|b'{'=>{let is_map=self.next()?==b'{';let end=if is_map{b'}'}else{b']'};self.ws();let mut a=Vec::new();let mut m=Vec::new();if self.p<self.b.len()&&self.b[self.p]==end{self.p+=1;return Ok(if is_map{V::M(m)}else{V::A(a)});}loop{if is_map{self.ws();let key=s(&self.string()?);need(!m.iter().any(|(k,_)|k==&key),"duplicate JSON key")?;self.ws();need(self.next()?==b':',"colon")?;m.push((key,self.value(d+1)?));}else{a.push(self.value(d+1)?);}self.ws();let sep=self.next()?;if sep==end{break;}need(sep==b',',"comma")?;}Ok(if is_map{V::M(m)}else{V::A(a)})},_=>Err("JSON value".into())}}
}
fn parse_json(input:&str)->R<V>{need(input.len()<=MAX*4,"JSON size")?;let mut j=J{b:input.as_bytes(),p:0,n:0};let v=j.value(0)?;j.ws();need(j.p==j.b.len(),"JSON trailing")?;Ok(v)}
fn run(line:&str)->R<V>{
 let (mode,input)=line.split_once('\t').ok_or("mode TAB input")?;
 if let Some(pins)=mode.strip_prefix("phase-i6:"){return creation::run(input,pins,"I");}
 if let Some(pins)=mode.strip_prefix("phase-f6:"){return creation::run(input,pins,"F");}
 if let Some(pin)=mode.strip_prefix("registration-assets:"){return selection::run(input,pin);}
 if let Some(pins)=mode.strip_prefix("phase-d-candidate:"){return phase_d_contract::run(input,pins);}
 if let Some(pins)=mode.strip_prefix("decision-replay:"){let (lock,contract)=pins.split_once(':').ok_or("two decision pins required")?;return decision_replay::run(input,lock,contract);}
 if let Some(pins)=mode.strip_prefix("runtime-bindings:"){let (lock,contract)=pins.split_once(':').ok_or("two runtime pins required")?;return runtime_bindings::run(input,lock,contract);}
 if let Some(pin)=mode.strip_prefix("commitments:"){return commitments::run(input,pin);}
 if mode=="frozen-projection"{return method_rules::project(input);}
 if let Some(pin)=mode.strip_prefix("method-matrix:"){return method_rules::run(input,pin,false);}
 if let Some(pin)=mode.strip_prefix("phase-r5:"){return method_rules::run(input,pin,true);}
 if let Some(pin)=mode.strip_prefix("registration-rules:"){return registration::run_rules(input,pin,false);}
 if let Some(pin)=mode.strip_prefix("phase-r4:"){return registration::run_rules(input,pin,true);}
 if mode=="excluded-selection"{return registration::run_excluded(input);}
 if let Some(pin)=mode.strip_prefix("phase-r3:"){return registration::run_references(input,pin);}
 if let Some(pin)=mode.strip_prefix("phase-r:"){return registration::run(input,pin);}
 if ["profile-digest","profile-decision","audit-profile"].contains(&mode){return profile::run(mode,input);}
 if mode=="sha256"{return Ok(s(&hex(&sha256::hash(&unhex(input)?))));}
 if mode.strip_prefix("view-").unwrap_or(mode).starts_with("fm2-"){return fm_policy::run(mode,input);}
 if mode.strip_prefix("view-").unwrap_or(mode).starts_with("fm-"){return fm::run(mode,input);}
 let public_kind=mode.strip_prefix("view-").unwrap_or(mode);
 need(["uint","int","bool","text","bytes","digest","semver","rational","version-range","text-set","template","claim","chain"].contains(&public_kind),"unknown kind")?;
 let (kind,raw)=if let Some(kind)=mode.strip_prefix("view-"){let view=parse_json(input)?;let v=project(kind,&view,true)?;validate(kind,&v)?;(kind,encode(&v)?)}else{(mode,unhex(input)?)};
 let v=decode(&raw)?;validate(kind,&v)?;
 let mut out=vec![("cbor_hex",s(&hex(&encode(&v)?))),("schema_view",project(kind,&v,false)?)];
 let digest=match kind{"template"=>Some(template_hash(&v)?),"claim"=>Some(claim_hash(&v)?),"chain"=>Some(bytes(get(&v,"rendered_claim_digest")?)?.to_vec()),_=>None};if let Some(d)=digest{out.push(("digest_hex",s(&hex(&d))));}Ok(map(out))
}
fn main(){
 let stdin=io::stdin();let mut locked=stdin.lock();loop{let mut line=String::new();let read=std::io::Read::take(&mut locked,(MAX*4+2)as u64).read_line(&mut line);match read {Ok(0)=>break,Ok(_)=>{if line.len()>MAX*4 {println!("{{\"error\":\"line limit\"}}");break;}let result=run(line.trim_end_matches(['\n','\r']));println!("{}",match result{Ok(v)=>json(&v),Err(e)=>json(&map(vec![("error",s(&e))]))});},Err(_)=>{println!("{{\"error\":\"input\"}}");break;}}}
}
