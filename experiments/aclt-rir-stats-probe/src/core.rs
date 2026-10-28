// SPDX-License-Identifier: Apache-2.0
// Independent, fail-closed stats-core entry; not complete ADR-0006 conformance.
use super::*;
use std::collections::{BTreeMap, BTreeSet};
use wire::V;
type Check<T> = Result<T,&'static str>;
const ENC:&str="RIR_REJECT_ENCODING";
const UNS:&str="RIR_REJECT_UNSUPPORTED";
const INV:&str="RIR_REJECT_INVALID";
const LIM:&str="RIR_REJECT_LIMITS";
fn check(ok:bool,code:&'static str)->Check<()>{if ok{Ok(())}else{Err(code)}}
fn parse<T>(v:Result<T,String>)->Check<T>{v.map_err(|_|ENC)}
fn u(mut n:u64)->Vec<u8>{let mut b=Vec::new();loop{let x=(n&127)as u8;n>>=7;b.push(x|if n>0{128}else{0});if n==0{return b;}}}
fn signed(mut n:i64)->Vec<u8>{let mut b=Vec::new();loop{let x=(n&127)as u8;n>>=7;let end=(n==0&&x&64==0)||(n== -1&&x&64!=0);b.push(x|if end{0}else{128});if end{return b;}}}
fn name(t:&str)->Vec<u8>{let mut b=u(t.len()as u64);b.extend(t.as_bytes());b}
fn sec(id:u8,b:&[u8])->Vec<u8>{let mut x=vec![id];x.extend(u(b.len()as u64));x.extend(b);x}
fn instruction_seq(r:&mut Reader,depth:usize)->Check<(Vec<Node>,u8)>{
 check(depth<=128,LIM)?;let mut seq=Vec::new();loop{let op=parse(r.byte())?;if op==5||op==11{return Ok((seq,op));}let mut n=Node{op,args:vec![],body:vec![],other:vec![]};match op{
  2..=4=>{let ty=parse(r.byte())?;check(ty==0x40||matches!(ty,0x7c..=0x7f),ENC)?;n.args.push(ty as u64);let(body,mut end)=instruction_seq(r,depth+1)?;n.body=body;if end==5{check(op==4,ENC)?;let(other,e)=instruction_seq(r,depth+1)?;n.other=other;end=e;}check(end==11,ENC)?;},
  0x0c|0x0d|0x10|0x20..=0x24=>n.args.push(parse(r.num(false,32))?),
  0x0e=>{let count=parse(r.u())?;check(count<=r.b.len().saturating_sub(r.p),ENC)?;n.args.push(count as u64);for _ in 0..=count{n.args.push(parse(r.num(false,32))?);}},
  0x11=>{n.args.push(parse(r.num(false,32))?);check(parse(r.byte())?==0,ENC)?;},
  0x28..=0x3e=>{n.args.push(parse(r.num(false,32))?);n.args.push(parse(r.num(false,32))?);},
  0x3f|0x40=>{check(parse(r.byte())?==0,ENC)?;},
  0x41|0x42=>n.args.push(parse(r.num(true,if op==0x41{32}else{64}))?),
  0x43|0x44=>{let mut bits=[0u8;8];let w=if op==0x43{4}else{8};bits[..w].copy_from_slice(parse(r.take(w))?);n.args.push(u64::from_le_bytes(bits));},
  0|1|15|0x1a|0x1b|0x45..=0xbf=>{},_=>return Err(ENC)
 }seq.push(n);}
}
fn nodes(ns:&[Node])->Vec<u8>{let mut b=Vec::new();for n in ns{b.push(n.op);match n.op{
 2..=4=>{b.push(n.args[0]as u8);b.extend(nodes(&n.body));if !n.other.is_empty(){b.push(5);b.extend(nodes(&n.other));}b.push(11);},
 0x41|0x42=>b.extend(signed(n.args[0]as i64)),0x43|0x44=>b.extend(&n.args[0].to_le_bytes()[..if n.op==0x43{4}else{8}]),
 0x0c|0x0d|0x10|0x20..=0x24|0x0e=>{for a in &n.args{b.extend(u(*a));}},
 0x11=>{b.extend(u(n.args[0]));b.push(0);},0x28..=0x3e=>{b.extend(u(n.args[0]));b.extend(u(n.args[1]));},0x3f|0x40=>b.push(0),_=>{}}}b}
fn supported_nodes(ns:&[Node])->bool{ns.iter().all(|n|match n.op{2..=4=>n.args==[0x40]&&supported_nodes(&n.body)&&supported_nodes(&n.other),0x28|0x29|0x2d|0x36|0x37|0x3a=>true,0|1|15|0x0c|0x0d|0x10|0x1a|0x1b|0x20..=0x24|0x41|0x42|0x45..=0x5a|0x67..=0x8a|0xa7|0xac|0xad=>true,_=>false})}

struct Shape { types:Vec<(Vec<u8>,Vec<u8>)>,imports:Vec<(String,String,u8,usize)>,functions:Vec<usize>,locals:Vec<Vec<u8>>,globals:Vec<(u8,u8)>,exports:Vec<(String,u8,usize)>,code:Vec<Vec<Node>>,pages:Vec<(u8,u32,u32)>,unsupported:bool }
fn count(r:&mut Reader)->Check<usize>{let n=parse(r.u())?;check(n<=r.b.len().saturating_sub(r.p),ENC)?;Ok(n)}
fn canonical(raw:&[u8])->Check<Shape>{
 check(raw.get(..8)==Some(b"\0asm\x01\0\0\0"),ENC)?;
 let mut r=Reader{b:&raw[8..],p:0};let mut parts=BTreeMap::new();let mut last=0;let mut custom=false;
 while r.p<r.b.len(){let id=parse(r.byte())?;let len=parse(r.u())?;let b=parse(r.take(len))?;if id==0{custom=true;continue;}check((1..=11).contains(&id)&&id>last,ENC)?;last=id;parts.insert(id,b);}
 // No general Wasm 1.0 grammar claim for table/element/data/typed blocks here.
 let mut shape=Shape{types:vec![],imports:vec![],functions:vec![],locals:vec![],globals:vec![],exports:vec![],code:vec![],pages:vec![],unsupported:false};
 let mut rebuilt=b"\0asm\x01\0\0\0".to_vec();
 for (&id,payload) in &parts {
  let mut s=Reader{b:payload,p:0};let mut b=Vec::new();let n=count(&mut s)?;b.extend(u(n as u64));
  match id {
   1=>{for _ in 0..n{check(parse(s.byte())?==0x60,ENC)?;let pn=parse(s.u())?;let params=parse(s.take(pn))?.to_vec();let rn=parse(s.u())?;let result=parse(s.take(rn))?.to_vec();check(params.iter().chain(result.iter()).all(|t|matches!(t,0x7c..=0x7f)),ENC)?;b.push(0x60);b.extend(u(pn as u64));b.extend(&params);b.extend(u(rn as u64));b.extend(&result);shape.types.push((params,result));}},
   2=>{for _ in 0..n{let module=parse(s.text())?;let field=parse(s.text())?;let kind=parse(s.byte())?;if kind!=0{return Err(UNS);}let ty=parse(s.u())?;b.extend(name(&module));b.extend(name(&field));b.push(kind);b.extend(u(ty as u64));shape.imports.push((module,field,kind,ty));}},
   3=>{for _ in 0..n{let ty=parse(s.u())?;b.extend(u(ty as u64));shape.functions.push(ty);}},
   5=>{for _ in 0..n{let flags=parse(s.byte())?;check(flags<=1,ENC)?;let min=parse(s.num(false,32))? as u32;let max=if flags==1{parse(s.num(false,32))? as u32}else{min};b.push(flags);b.extend(u(min as u64));if flags==1{b.extend(u(max as u64));}shape.pages.push((flags,min,max));}},
   6=>{for _ in 0..n{let t=parse(s.byte())?;let m=parse(s.byte())?;let op=parse(s.byte())?;b.extend([t,m,op]);match op{0x41|0x42=>{let val=parse(s.num(true,if op==0x41{32}else{64}))?;b.extend(signed(val as i64));},0x43|0x44=>{b.extend(parse(s.take(if op==0x43{4}else{8}))?);shape.unsupported=true;},_=>return Err(UNS)}check(parse(s.byte())?==11,ENC)?;b.push(11);shape.globals.push((t,m));}},
   7=>{for _ in 0..n{let nm=parse(s.text())?;let kind=parse(s.byte())?;let index=parse(s.u())?;check(kind<=3,ENC)?;b.extend(name(&nm));b.push(kind);b.extend(u(index as u64));shape.exports.push((nm,kind,index));}},
   10=>{for _ in 0..n{let len=parse(s.u())?;check(len<=512*1024,LIM)?;let mut f=Reader{b:parse(s.take(len))?,p:0};let groups=count(&mut f)?;let mut local_types=Vec::new();let mut compressed:Vec<(u64,u8)>=Vec::new();for _ in 0..groups{let cnt=parse(f.u())?;let t=parse(f.byte())?;check(matches!(t,0x7c..=0x7f),ENC)?;check(cnt<=4096&&local_types.len()+cnt<=4096,LIM)?;local_types.extend(std::iter::repeat_n(t,cnt));if cnt>0{if let Some((c,ty))=compressed.last_mut(){if *ty==t{*c+=cnt as u64;}else{compressed.push((cnt as u64,t));}}else{compressed.push((cnt as u64,t));}}}
    let (seq,end)=instruction_seq(&mut f,0)?;check(end==11,ENC)?;parse(f.done())?;
    let mut body=u(compressed.len()as u64);for(c,t)in compressed{body.extend(u(c));body.push(t);}body.extend(nodes(&seq));body.push(11);b.extend(u(body.len()as u64));b.extend(body);shape.locals.push(local_types);shape.code.push(seq);
   }},
   _=>return Err(UNS)
  }parse(s.done())?;
  if n>0{rebuilt.extend(sec(id,&b));}
 }
 check(!custom&&rebuilt==raw,ENC)?;
 check(parts.keys().copied().collect::<Vec<_>>()==[1,2,3,5,6,7,10],UNS)?;
 Ok(shape)
}
fn subset(s:&Shape)->Check<()> {
 check(!s.unsupported&&s.code.iter().all(|seq|supported_nodes(seq))&&s.types.iter().all(|(p,r)|p.iter().chain(r.iter()).all(|t|matches!(t,0x7e|0x7f))&&r.len()<=1),UNS)?;
 check(s.imports.len()==5,UNS)?;let mut seen=BTreeSet::new();
 for (module,nm,kind,ty) in &s.imports{check(module=="aclt"&&*kind==0&&seen.insert(nm),UNS)?;let expected=match nm.as_str(){"input_count"=>(vec![],vec![0x7f]),"input_len"=>(vec![0x7f],vec![0x7e]),"input_read"=>(vec![0x7f,0x7e,0x7f,0x7f],vec![]),"output_write"=>(vec![0x7f,0x7f],vec![]),"abort"=>(vec![0x7f],vec![]),_=>return Err(UNS)};check(s.types.get(*ty)==Some(&expected),UNS)?;}
 check(s.pages.len()==1&&s.pages[0].0==1,UNS)?;
 check(s.locals.iter().flatten().all(|t|matches!(t,0x7e|0x7f))&&s.globals.iter().all(|(t,m)|matches!(t,0x7e|0x7f)&&*m<=1),UNS)?;
 check(s.exports.len()==2&&s.exports.iter().all(|(n,k,_)|(n=="run"&&*k==0)||(n=="memory"&&*k==2)),UNS)?;
 Ok(())
}
fn signature(s:&Shape,index:usize)->Check<&(Vec<u8>,Vec<u8>)>{let ty=if index<s.imports.len(){s.imports[index].3}else{*s.functions.get(index-s.imports.len()).ok_or(INV)?};s.types.get(ty).ok_or(INV)}
fn pop(stack:&mut Vec<Option<u8>>,height:usize,dead:bool,t:Option<u8>)->Check<Option<u8>>{
 if stack.len()==height&&dead{return Ok(t);}check(stack.len()>height,INV)?;let actual=stack.pop().ok_or(INV)?;check(t.is_none()||actual.is_none()||t==actual,INV)?;Ok(actual.or(t))
}
fn typed(ns:&[Node],s:&Shape,locals:&[u8],mut stack:Vec<Option<u8>>,height:usize,labels:usize)->Check<()> {
 let mut dead=false;
 for n in ns{let op=n.op;let a=&n.args;
  match op{
   2..=4=>{if op==4{pop(&mut stack,height,dead,Some(0x7f))?;}typed(&n.body,s,locals,stack.clone(),stack.len(),labels+1)?;if op==4{typed(&n.other,s,locals,stack.clone(),stack.len(),labels+1)?;}},
   0|0x0c|15=>{if op==0x0c{check((a[0]as usize)<labels,INV)?;}stack.truncate(height);dead=true;},
   0x0d=>{check((a[0]as usize)<labels,INV)?;pop(&mut stack,height,dead,Some(0x7f))?;},
   0x10=>{let(ps,rs)=signature(s,a[0]as usize)?;for t in ps.iter().rev(){pop(&mut stack,height,dead,Some(*t))?;}stack.extend(rs.iter().map(|t|Some(*t)));},
   0x20..=0x22=>{let t=*locals.get(a[0]as usize).ok_or(INV)?;if op!=0x20{pop(&mut stack,height,dead,Some(t))?;}if op!=0x21{stack.push(Some(t));}},
   0x23|0x24=>{let(t,m)=s.globals.get(a[0]as usize).ok_or(INV)?;if op==0x24{check(*m==1,INV)?;pop(&mut stack,height,dead,Some(*t))?;}else{stack.push(Some(*t));}},
   x if is_mem(x)=>{let t=if matches!(x,0x29|0x37){0x7e}else{0x7f};let width=if matches!(x,0x29|0x37){8}else if matches!(x,0x2d|0x3a){1}else{4};check(a[0]<32&&(1u64<<a[0])<=width,INV)?;let store=matches!(x,0x36|0x37|0x3a);if store{pop(&mut stack,height,dead,Some(t))?;}pop(&mut stack,height,dead,Some(0x7f))?;if !store{stack.push(Some(t));}},
   0x41|0x42=>stack.push(Some(if op==0x41{0x7f}else{0x7e})),
   0x1a=>{pop(&mut stack,height,dead,None)?;},
   0x1b=>{pop(&mut stack,height,dead,Some(0x7f))?;let t=pop(&mut stack,height,dead,None)?;let other=pop(&mut stack,height,dead,t)?;stack.push(t.or(other));},
   0x45|0x50=>{pop(&mut stack,height,dead,Some(if op==0x45{0x7f}else{0x7e}))?;stack.push(Some(0x7f));},
   0x46..=0x4f|0x51..=0x5a|0x6a..=0x78|0x7c..=0x8a=>{let t=if op<0x50||(0x6a..=0x78).contains(&op){0x7f}else{0x7e};pop(&mut stack,height,dead,Some(t))?;pop(&mut stack,height,dead,Some(t))?;stack.push(Some(if op<0x5b{0x7f}else{t}));},
   0x67..=0x69|0x79..=0x7b=>{let t=if op<0x79{0x7f}else{0x7e};pop(&mut stack,height,dead,Some(t))?;stack.push(Some(t));},
   0xa7|0xac|0xad=>{pop(&mut stack,height,dead,Some(if op==0xa7{0x7e}else{0x7f}))?;stack.push(Some(if op==0xa7{0x7f}else{0x7e}));},
   1=>{},_=>return Err(UNS)
  }check(stack.len()<=4096,LIM)?;
 }check(stack.len()==height,INV)
}
fn validity(s:&Shape)->Check<()> {
 check(!s.functions.is_empty()&&s.functions.len()==s.code.len(),INV)?;let mut names=BTreeSet::new();
 for(n,k,i)in &s.exports{check(names.insert(n),INV)?;if *k==0{check(*i>=5&&signature(s,*i)?==&(vec![],vec![]),INV)?;}else{check(*i==0,INV)?;}}
 for(i,ty)in s.functions.iter().enumerate(){let(params,results)=s.types.get(*ty).ok_or(INV)?;check(results.is_empty(),UNS)?;let mut locals=params.clone();locals.extend(&s.locals[i]);typed(&s.code[i],s,&locals,vec![],0,1)?;}
 Ok(())
}
fn limits(s:&Shape)->Check<()> {check(s.types.len()<=64&&s.types.iter().all(|(p,_)|p.len()<=16)&&s.functions.len()<=32&&s.globals.len()<=1024&&s.pages==[(1,2,2)],LIM)}
fn artifact(raw:&[u8])->Check<(Module,String)> {
 let v=wire::decode(raw).map_err(|_|ENC)?;let encoded=wire::encode(&v).map_err(|_|ENC)?;check(encoded==raw,ENC)?;
 let keys=["schema_version","encoding_profile_id","rir_version","entry","input_arity","body"];
 wire::fields(&v,&keys).map_err(|_|UNS)?;
 let get=|k|wire::get(&v,k).map_err(|_|UNS);
 check(matches!(get("schema_version")?,V::N(1))&&get("encoding_profile_id")?==&V::S("acl.enc.rir-0@1".into())&&get("rir_version")?==&V::A(vec![V::N(0),V::N(1),V::N(0)])&&get("entry")?==&V::S("run".into()),UNS)?;
 let arity=match get("input_arity")?{V::N(n)if *n>=0=>*n,_=>return Err(UNS)};
 let body=wire::bytes(get("body")?).map_err(|_|UNS)?;let shape=canonical(body)?;subset(&shape)?;validity(&shape)?;limits(&shape)?;check(arity<=u32::MAX as i128,LIM)?;check(arity==1,INV)?;
 let m=decode(body).map_err(|_|INV)?;Ok((m,wire::hex(&wire::domain("ACLt/RIR-0/Artifact/1",raw))))
}
fn cbor_head(major:u8,n:u64)->Vec<u8>{if n<24{return vec![major*32+n as u8];}let width=if n<256{1}else if n<65536{2}else if n<1u64<<32{4}else{8};let mut b=vec![major*32+match width{1=>24,2=>25,4=>26,_=>27}];b.extend(&n.to_be_bytes()[8-width..]);b}
fn encode_outcome(name:&str,gas:u64,output:&[u8],abort:Option<u32>)->Result<Vec<u8>,String>{
 let mut pairs=vec![(wire::encode(&V::S("outcome".into()))?,wire::encode(&V::S(name.into()))?),(wire::encode(&V::S("gas_used".into()))?,wire::encode(&V::N(gas as i128))?)];
 if name=="OK"{let mut b=cbor_head(2,output.len()as u64);b.try_reserve(output.len()).map_err(|_|"allocation")?;b.extend(output);pairs.push((wire::encode(&V::S("output".into()))?,b));}
 if let Some(n)=abort{pairs.push((wire::encode(&V::S("abort_code".into()))?,wire::encode(&V::N(n as i128))?));}
 pairs.sort_by(|a,b|a.0.cmp(&b.0));let mut result=cbor_head(5,pairs.len()as u64);let len=pairs.iter().map(|(k,v)|k.len()+v.len()).sum();result.try_reserve(len).map_err(|_|"allocation")?;for(k,v)in pairs{result.extend(k);result.extend(v);}Ok(result)
}
fn rejected(code:&str)->(String,i32){(format!("{{\"status\":\"REJECTED\",\"code\":\"{code}\"}}"),2)}
fn fault(code:&str)->(String,i32){(format!("{{\"status\":\"HOST_FAULT\",\"code\":\"{code}\"}}"),3)}
fn run()->Result<(String,i32),String>{
 let a:Vec<String>=env::args().collect();if a.get(1).is_some_and(|x|x=="--support"){return Ok(("{\"scope\":\"RIR_STATS_INDEPENDENT_CORE_1\",\"production_admission\":false,\"artifact_bytes_max\":1048576,\"input_arity\":1,\"input_bytes_max\":2000000,\"memory_pages\":2,\"gas_min\":8192,\"gas_max\":50000000,\"output_bytes_max\":4800000,\"call_depth_min\":1,\"call_depth_max\":64,\"full_ADR_0006_conformance\":false}".into(),0));}
 if a.len()!=10&&a.len()!=11{return Ok(rejected(UNS));}if a[1]!="--artifact"{return Ok(rejected(UNS));}
 let read=|path:&str,max:u64|->Result<Vec<u8>,std::io::Error>{use std::io::Read;let file=fs::File::open(path)?;let mut b=Vec::new();file.take(max+1).read_to_end(&mut b)?;Ok(b)};
 let raw=match read(&a[2],1<<20){Ok(b)=>b,Err(_)=>return Ok(fault("HOST_IO_FAILURE"))};let(m,digest)=match artifact(&raw){Ok(m)=>m,Err(c)=>return Ok(rejected(c))};
 let num=|i:usize|a[i].parse::<u64>().map_err(|_|"invalid limit".to_string());let(gas,out,depth,steps,pages)=match(num(4),num(5),num(6),num(7),num(8)){(Ok(g),Ok(o),Ok(d),Ok(s),Ok(p))=>(g,o,d,s,p),_=>return Ok(rejected(LIM))};
 if !(8192..=50000000).contains(&gas)||out>4800000||!(1..=64).contains(&depth)||pages!=2{return Ok(rejected(LIM));}
 if a[9]!=digest{return Ok(fault("RPR_REVALIDATION_MISMATCH"));}
 let input=match read(&a[3],2000000){Ok(b)if b.len()<=2000000=>b,Ok(_)=>return Ok(rejected(LIM)),Err(_)=>return Ok(fault("HOST_IO_OR_RESOURCE_FAILURE"))};
 let hook=a.get(10).map(String::as_str).unwrap_or("");if hook=="test-memory-fault"{return Ok(fault("HOST_RESOURCE_EXHAUSTED"));}if !hook.is_empty(){return Ok(rejected(UNS));}
 let mut memory=Vec::new();if memory.try_reserve_exact(131072).is_err(){return Ok(fault("HOST_RESOURCE_EXHAUSTED"));}memory.resize(131072,0);
 let mut machine=Machine{m:&m,input,memory,output:vec![],globals:m.globals.clone(),gas:0,limit:gas,out_limit:out,depth_limit:depth,steps:0,step_limit:steps};
 let outcome=machine.charge(8192).and_then(|_|machine.invoke(m.run,vec![],1));let(name,abort)=match outcome{Ok(_)=>("OK",None),Err(Stop::Trap(n,a))=>(n,a),_=>return Ok(fault("HOST_RESOURCE_OR_INTERNAL_FAILURE"))};
 let mut json=format!("{{\"outcome\":\"{name}\",\"gas_used\":{}",machine.gas);
 if name=="OK"{json.push_str(&format!(",\"output_hex\":\"{}\"",wire::hex(&machine.output)));}
 if let Some(n)=abort{json.push_str(&format!(",\"abort_code\":{n}"));}json.push('}');let encoded=encode_outcome(name,machine.gas,&machine.output,abort)?;
 Ok((format!("{{\"status\":\"TASK_OUTCOME\",\"rir_digest\":\"{digest}\",\"canonical_outcome_hex\":\"{}\",\"outcome_digest\":\"{}\",\"result\":{json}}}",wire::hex(&encoded),wire::hex(&wire::domain("ACLt/RIR-0/ExecutionOutcome/1",&encoded))),0))
}
pub(super) fn main(){match std::panic::catch_unwind(run){Ok(Ok((v,c)))=>{println!("{v}");process::exit(c)},Ok(Err(_))|Err(_)=>{println!("{{\"status\":\"HOST_FAULT\",\"code\":\"RPR_INTERNAL_ERROR\"}}");process::exit(3)}}}
