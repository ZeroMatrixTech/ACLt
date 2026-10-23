// SPDX-License-Identifier: Apache-2.0
mod data { include!("unicode_data.rs"); }
fn ccc(c:u32)->u8 {data::CCC.binary_search_by_key(&c,|x|x.0).map(|i|data::CCC[i].1).unwrap_or(0)}
fn decompose(c:u32,out:&mut Vec<u32>) {
    if (0xac00..0xd7a4).contains(&c) {let s=c-0xac00;out.push(0x1100+s/588);out.push(0x1161+(s%588)/28);if s%28!=0 {out.push(0x11a7+s%28);} }
    else if let Ok(i)=data::DECOMP.binary_search_by_key(&c,|x|x.0) {for &v in data::DECOMP[i].1 {decompose(v,out);}}
    else {out.push(c);}
}
fn compose(a:u32,b:u32)->Option<u32>{
    if (0x1100..0x1113).contains(&a)&&(0x1161..0x1176).contains(&b){return Some(0xac00+(a-0x1100)*588+(b-0x1161)*28);}
    if (0xac00..0xd7a4).contains(&a)&&(a-0xac00)%28==0&&(0x11a8..0x11c3).contains(&b){return Some(a+b-0x11a7);}
    data::COMPOSE.binary_search_by_key(&(a,b),|x|(x.0,x.1)).ok().map(|i|data::COMPOSE[i].2)
}
pub fn is_nfc(s:&str)->bool {
    let mut d=Vec::new();for c in s.chars(){decompose(c as u32,&mut d);}
    // Stable canonical ordering within each starter segment, O(n log n).
    let mut start=0;for i in 0..d.len(){if ccc(d[i])==0 {d[start..i].sort_by_key(|c|ccc(*c));start=i+1;}}d[start..].sort_by_key(|c|ccc(*c));
    let mut out:Vec<u32>=Vec::new();let mut starter=None;let mut last=0;
    for c in d {let cls=ccc(c);if let Some(i)=starter {if last==0||last<cls {if let Some(combined)=compose(out[i],c){out[i]=combined;continue;}}}
        if cls==0 {starter=Some(out.len());}out.push(c);last=cls;
    }
    s.chars().map(|c|c as u32).eq(out)
}
