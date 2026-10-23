// SPDX-License-Identifier: Apache-2.0
// Independent decoder and executor for prevalidated, canonical stats-slice Wasm.
// Not an independent RIR/CBOR validator. No third-party crates or Python AST input.
use std::{env, fs, process};
#[derive(Clone)]
struct Node { op:u8, args:Vec<u64>, body:Vec<Node>, other:Vec<Node> }
struct Reader<'a> { b:&'a [u8], p:usize }
impl<'a> Reader<'a> {
    fn take(&mut self,n:usize)->Result<&'a [u8],String> {
        if n>self.b.len().saturating_sub(self.p) {return Err("truncated".into())}
        let out=&self.b[self.p..self.p+n]; self.p+=n; Ok(out)
    }
    fn byte(&mut self)->Result<u8,String>{Ok(self.take(1)?[0])}
    fn num(&mut self, signed:bool,bits:u32)->Result<u64,String>{
        let mut n=0u128;
        for i in 0..bits.div_ceil(7) {
            let b=self.byte()?;n|=((b&127) as u128)<<(7*i);
            if b<128 {
                let shift=7*(i+1);
                let value=if signed && b&64!=0 {(n as i128)-(1i128<<shift)}else{n as i128};
                if signed {if value< -(1i128<<(bits-1)) || value>=(1i128<<(bits-1)){return Err("signed LEB".into())}}
                else if n>=(1u128<<bits){return Err("unsigned LEB".into())}
                return Ok(value as u64)
            }
        } Err("LEB length".into())
    }
    fn u(&mut self)->Result<usize,String>{Ok(self.num(false,32)? as usize)}
    fn text(&mut self)->Result<String,String>{let n=self.u()?;String::from_utf8(self.take(n)?.to_vec()).map_err(|_|"UTF8".into())}
    fn done(&self)->Result<(),String>{if self.p==self.b.len(){Ok(())}else{Err("trailing bytes".into())}}
}
fn is_mem(op:u8)->bool {matches!(op,0x28|0x29|0x2d|0x36|0x37|0x3a)}
fn sequence(r:&mut Reader,depth:usize)->Result<(Vec<Node>,u8),String>{
    if depth>128{return Err("nesting".into())}
    let mut nodes=Vec::new();
    loop {
        let op=r.byte()?;if op==5||op==11{return Ok((nodes,op))}
        let mut n=Node{op,args:vec![],body:vec![],other:vec![]};
        match op {
            2..=4=>{if r.byte()?!=0x40{return Err("void block required".into())}
                let (body,mut end)=sequence(r,depth+1)?;n.body=body;
                if end==5 {if op!=4{return Err("unexpected else".into())}let(other,e)=sequence(r,depth+1)?;n.other=other;end=e;}
                if end!=11{return Err("block end".into())}
            },
            0x0c|0x0d|0x10|0x20..=0x24=>n.args.push(r.num(false,32)?),
            0x41|0x42=>n.args.push(r.num(true,if op==0x41{32}else{64})?),
            x if is_mem(x)=>{n.args.push(r.num(false,32)?);n.args.push(r.num(false,32)?);},
            0|1|15|0x1a|0x1b|0x45..=0x5a|0x67..=0x8a|0xa7|0xac|0xad=>{},
            _=>return Err(format!("unsupported opcode {op:x}"))
        }
        nodes.push(n);
    }
}
struct Module { types:Vec<(Vec<u8>,Vec<u8>)>,imports:Vec<(String,usize)>,functions:Vec<usize>,code:Vec<(usize,Vec<Node>)>,globals:Vec<u64>,run:usize }
fn decode(bytes:&[u8])->Result<Module,String>{
    if bytes.len()>4*1024*1024 || bytes.get(..8)!=Some(b"\0asm\x01\0\0\0"){return Err("header/size".into())}
    let mut r=Reader{b:&bytes[8..],p:0};let mut last=0;
    let mut m=Module{types:vec![],imports:vec![],functions:vec![],code:vec![],globals:vec![],run:usize::MAX};
    let mut sections=vec![];
    while r.p<r.b.len(){let id=r.byte()?;if id<=last{return Err("section order/custom".into())}last=id;sections.push(id);
        let len=r.u()?;let mut s=Reader{b:r.take(len)?,p:0};
        match id {
            1=>{let n=s.u()?;if n>64{return Err("type cap".into())}for _ in 0..n{if s.byte()?!=0x60{return Err("type".into())}let pn=s.u()?;if pn>16{return Err("parameter cap".into())}let p=s.take(pn)?.to_vec();let rn=s.u()?;if rn>1{return Err("result cap".into())}let result=s.take(rn)?.to_vec();if p.iter().chain(result.iter()).any(|t|!matches!(t,0x7e|0x7f)){return Err("integer type".into())}m.types.push((p,result));}},
            2=>{let n=s.u()?;if n!=5{return Err("five imports".into())}for _ in 0..n{if s.text()?!="aclt"{return Err("import module".into())}let name=s.text()?;if s.byte()?!=0{return Err("function import".into())}let t=s.u()?;m.imports.push((name,t));}},
            3=>{let n=s.u()?;if n>32{return Err("function cap".into())}for _ in 0..n{m.functions.push(s.u()?);}},
            5=>{if s.u()?!=1||s.byte()?!=1||s.u()?!=2||s.u()?!=2{return Err("memory".into())}},
            6=>{let n=s.u()?;if n>1024{return Err("global cap".into())}for _ in 0..n{let t=s.byte()?;let mutability=s.byte()?;let op=s.byte()?;if !matches!(t,0x7f|0x7e)||mutability>1||op!=if t==0x7f{0x41}else{0x42}{return Err("global".into())}m.globals.push(s.num(true,if t==0x7f{32}else{64})?&if t==0x7f{0xffffffff}else{u64::MAX});if s.byte()?!=11{return Err("global end".into())}}},
            7=>{let n=s.u()?;if n!=2{return Err("exports".into())}for _ in 0..n{let name=s.text()?;let kind=s.byte()?;let idx=s.u()?;match(name.as_str(),kind,idx){("run",0,i)=>m.run=i,("memory",2,0)=>{},_=>return Err("export".into())}}},
            10=>{let n=s.u()?;if n!=m.functions.len(){return Err("code count".into())}for _ in 0..n{let len=s.u()?;let mut b=Reader{b:s.take(len)?,p:0};let groups=b.u()?;if groups>4096{return Err("local groups".into())}let mut locals=0;for _ in 0..groups{locals+=b.u()?;if locals>4096||!matches!(b.byte()?,0x7f|0x7e){return Err("locals".into())}}let(nodes,end)=sequence(&mut b,0)?;if end!=11{return Err("function end".into())}b.done()?;m.code.push((locals,nodes));}},
            _=>return Err("section".into())
        }s.done()?;
    }
    if sections!=[1,2,3,5,6,7,10]||m.run<5||m.run>=5+m.functions.len(){return Err("module shape".into())}
    for (name,t) in &m.imports{
        let expected=match name.as_str(){"input_count"=>(vec![],vec![0x7f]),"input_len"=>(vec![0x7f],vec![0x7e]),"input_read"=>(vec![0x7f,0x7e,0x7f,0x7f],vec![]),"output_write"=>(vec![0x7f,0x7f],vec![]),"abort"=>(vec![0x7f],vec![]),_=>return Err("import".into())};
        if m.types.get(*t)!=Some(&expected){return Err("signature".into())}
    }
    for t in &m.functions {if m.types.get(*t).is_none_or(|s|!s.1.is_empty()){return Err("void function".into())}}
    Ok(m)
}
#[derive(Debug)]
enum Stop {Trap(&'static str,Option<u32>),Jump(u64),Return,Fault}
type Exec<T>=Result<T,Stop>;
fn pop(s:&mut Vec<u64>)->Exec<u64>{s.pop().ok_or(Stop::Fault)}
struct Machine<'a>{m:&'a Module,input:Vec<u8>,memory:Vec<u8>,output:Vec<u8>,globals:Vec<u64>,gas:u64,limit:u64,out_limit:u64,depth_limit:u64,steps:u64,step_limit:u64}
impl Machine<'_> {
    fn charge(&mut self,cost:u64)->Exec<()> {self.steps+=1;if self.steps>self.step_limit{return Err(Stop::Fault)}if cost>self.limit-self.gas{return Err(Stop::Trap("TRAP_GAS_EXHAUSTED",None))}self.gas+=cost;Ok(())}
    fn host(&mut self,name:&str,args:&[u64])->Exec<Option<u64>>{
        let cost=match name{"input_count"|"input_len"=>4,"abort"=>1,_=>16+args.last().ok_or(Stop::Fault)?.div_ceil(8)};self.charge(cost)?;
        let bad=||Stop::Trap("TRAP_HOST_ARGUMENT",None);
        match name {
            "input_count"=>Ok(Some(1)),
            "input_len"=>{if args[0]!=0{return Err(bad())}Ok(Some(self.input.len() as u64))},
            "abort"=>Err(Stop::Trap("ABORT",Some(args[0] as u32))),
            "input_read"=>{let(index,off,dst,n)=(args[0],args[1] as u128,args[2] as u128,args[3] as u128);if index!=0||off+n>self.input.len() as u128||dst+n>self.memory.len() as u128{return Err(bad())}self.memory[dst as usize..(dst+n) as usize].copy_from_slice(&self.input[off as usize..(off+n) as usize]);Ok(None)},
            "output_write"=>{let(src,n)=(args[0] as u128,args[1] as u128);if src+n>self.memory.len() as u128{return Err(bad())}if self.output.len() as u128+n>self.out_limit as u128{return Err(Stop::Trap("TRAP_OUTPUT_LIMIT",None))}self.output.extend_from_slice(&self.memory[src as usize..(src+n) as usize]);Ok(None)},
            _=>Err(Stop::Fault)
        }
    }
    fn invoke(&mut self,index:usize,args:Vec<u64>,depth:u64)->Exec<Option<u64>>{
        if index<5{let name=&self.m.imports[index].0;return self.host(name,&args)}
        if depth>self.depth_limit{return Err(Stop::Trap("TRAP_CALL_DEPTH",None))}
        if depth>128{return Err(Stop::Fault)}
        let(n,nodes)=&self.m.code[index-5];let mut locals=args;locals.resize(locals.len()+n,0);let mut stack=vec![];
        match self.seq(nodes,&mut stack,&mut locals,depth){Ok(())|Err(Stop::Return)|Err(Stop::Jump(0))=>Ok(None),Err(e)=>Err(e)}
    }
    fn seq(&mut self,nodes:&[Node],s:&mut Vec<u64>,locals:&mut Vec<u64>,depth:u64)->Exec<()> {
        for n in nodes {let op=n.op;let a=&n.args;
            if op==0x10 && a[0]<5 {let t=self.m.imports[a[0] as usize].1;let count=self.m.types[t].0.len();if count>s.len(){return Err(Stop::Fault)}let args=s.split_off(s.len()-count);if let Some(v)=self.invoke(a[0] as usize,args,depth)?{s.push(v)}continue}
            self.charge(if op==0x10{4}else if is_mem(op){2}else if matches!(op,0x6c|0x7e){3}else if matches!(op,0x6d..=0x70|0x7f..=0x82){8}else{1})?;
            match op {
                0=>return Err(Stop::Trap("TRAP_UNREACHABLE",None)),1=>{},
                2..=4=>{let selected=if op==4 && pop(s)?==0{&n.other}else{&n.body};let height=s.len();loop{match self.seq(selected,s,locals,depth){Ok(())=>break,Err(Stop::Jump(d))=>{s.truncate(height);if d>0{return Err(Stop::Jump(d-1))}if op!=3{break}self.charge(1)?},Err(e)=>return Err(e)}}},
                0x0c=>return Err(Stop::Jump(a[0])),0x0d=>{if pop(s)?!=0{return Err(Stop::Jump(a[0]))}},15=>return Err(Stop::Return),
                0x10=>{let idx=a[0] as usize;let count=self.m.types[self.m.functions[idx-5]].0.len();if count>s.len(){return Err(Stop::Fault)}let args=s.split_off(s.len()-count);if let Some(v)=self.invoke(idx,args,depth+1)?{s.push(v)}},
                0x20=>s.push(locals[a[0] as usize]),0x21=>locals[a[0] as usize]=pop(s)?,0x22=>locals[a[0] as usize]=*s.last().ok_or(Stop::Fault)?,
                0x23=>s.push(self.globals[a[0] as usize]),0x24=>self.globals[a[0] as usize]=pop(s)?,
                x if is_mem(x)=>{let store=matches!(x,0x36|0x37|0x3a);let width=if matches!(x,0x29|0x37){8}else if matches!(x,0x2d|0x3a){1}else{4};let value=if store{pop(s)?}else{0};let address=pop(s)? as u128+a[1] as u128;if address+width as u128>self.memory.len() as u128{return Err(Stop::Trap("TRAP_MEMORY_OOB",None))}let address=address as usize;if store{self.memory[address..address+width].copy_from_slice(&value.to_le_bytes()[..width]);}else{let mut b=[0;8];b[..width].copy_from_slice(&self.memory[address..address+width]);s.push(u64::from_le_bytes(b));}},
                0x41=>s.push(a[0]&0xffffffff),0x42=>s.push(a[0]),0x1a=>{pop(s)?;},
                0x1b=>{let c=pop(s)?;let right=pop(s)?;let left=pop(s)?;s.push(if c!=0{left}else{right});},
                0x45|0x50=>{let v=pop(s)?;s.push((v==0) as u64)},
                0x46..=0x4f|0x51..=0x5a|0x6a..=0x78|0x7c..=0x8a=>{let right=pop(s)?;let left=pop(s)?;s.push(binary(op,left,right)?);},
                0x67..=0x69|0x79..=0x7b=>{let v=pop(s)?;let bits=if op<0x79{32}else{64};let k=op-if bits==32{0x67}else{0x79};let answer=if bits==32{let v=v as u32;match k{0=>v.leading_zeros(),1=>v.trailing_zeros(),_=>v.count_ones()}}else{match k{0=>v.leading_zeros(),1=>v.trailing_zeros(),_=>v.count_ones()}};s.push(answer as u64);},
                0xa7|0xad=>{let v=pop(s)?;s.push(v&0xffffffff)},0xac=>{let v=pop(s)?;s.push(v as u32 as i32 as i64 as u64)},
                _=>return Err(Stop::Fault)
            }
        }Ok(())
    }
}
fn binary(op:u8,l:u64,r:u64)->Exec<u64>{
    let cmp=matches!(op,0x46..=0x4f|0x51..=0x5a);let bits=if op<0x50||matches!(op,0x6a..=0x78){32}else{64};
    let mask=if bits==32{0xffffffff}else{u64::MAX};let(l,r)=(l&mask,r&mask);
    let(sl,sr)=if bits==32{(l as u32 as i32 as i64,r as u32 as i32 as i64)}else{(l as i64,r as i64)};
    if cmp{let k=op-if bits==32{0x46}else{0x51};return Ok(match k{0=>l==r,1=>l!=r,2=>sl<sr,3=>l<r,4=>sl>sr,5=>l>r,6=>sl<=sr,7=>l<=r,8=>sl>=sr,_=>l>=r} as u64)}
    let k=op-if bits==32{0x6a}else{0x7c};let n=(r%bits) as u32;
    let value=match k{
        0=>l.wrapping_add(r),1=>l.wrapping_sub(r),2=>l.wrapping_mul(r),
        3..=6=>{if r==0{return Err(Stop::Trap("TRAP_INTEGER_DIVIDE_BY_ZERO",None))}let min=if bits==32{i32::MIN as i64}else{i64::MIN};if k==3&&sl==min&&sr==-1{return Err(Stop::Trap("TRAP_INTEGER_OVERFLOW",None))}match k{3=>sl.wrapping_div(sr) as u64,4=>l/r,5=>sl.wrapping_rem(sr) as u64,_=>l%r}},
        7=>l&r,8=>l|r,9=>l^r,10=>l.wrapping_shl(n),11=>(sl>>n) as u64,12=>l>>n,
        13=>if bits==32{(l as u32).rotate_left(n) as u64}else{l.rotate_left(n)},
        _=>if bits==32{(l as u32).rotate_right(n) as u64}else{l.rotate_right(n)}
    };Ok(value&mask)
}
fn run()->Result<(String,i32),String>{
    let args:Vec<String>=env::args().collect();if args.len()!=8{return Err("usage: executor WASM INPUT GAS OUTPUT_LIMIT CALL_DEPTH STEP_LIMIT MEMORY_PAGES".into())}
    let (wasm,input)=match (fs::read(&args[1]),fs::read(&args[2])) {
        (Ok(wasm),Ok(input))=>(wasm,input),
        _=>return Ok(("{\"kind\":\"HOST_FAULT\"}".into(),3))
    };
    if input.len()>2_000_000{return Err("input byte cap".into())}
    let num=|i:usize|args[i].parse::<u64>().map_err(|_|"invalid limit".to_string());
    let(gas,out_limit,depth,steps,pages)=(num(3)?,num(4)?,num(5)?,num(6)?,num(7)?);
    if gas<8192||gas>i64::MAX as u64||depth==0||depth>4096||pages!=2{return Ok(("{\"kind\":\"REJECTED\"}".into(),2))}
    let m=decode(&wasm)?;let mut machine=Machine{m:&m,input,memory:vec![0;131072],output:vec![],globals:m.globals.clone(),gas:0,limit:gas,out_limit,depth_limit:depth,steps:0,step_limit:steps};
    let result=machine.charge(8192).and_then(|_|machine.invoke(m.run,vec![],1));
    let (name,abort)=match result{Ok(_)=>("OK",None),Err(Stop::Trap(n,a))=>(n,a),_=>return Ok(("{\"kind\":\"HOST_FAULT\"}".into(),3))};
    let mut json=format!("{{\"outcome\":\"{name}\",\"gas_used\":{}",machine.gas);
    if name=="OK"{json.push_str(",\"output_hex\":\"");for b in &machine.output{json.push_str(&format!("{b:02x}"))}json.push('"');}
    if let Some(code)=abort{json.push_str(&format!(",\"abort_code\":{code}"));}json.push('}');Ok((json,0))
}
fn main(){
    match std::panic::catch_unwind(run){Ok(Ok((json,code)))=>{println!("{json}");process::exit(code)},Ok(Err(error))=>{eprintln!("REJECTED: {error}");println!("{{\"kind\":\"REJECTED\"}}");process::exit(2)},Err(_)=>{println!("{{\"kind\":\"HOST_FAULT\"}}");process::exit(3)}}
}
