// SPDX-License-Identifier: Apache-2.0
// Local conformance fixture, not a complete protocol validator.
fn main() {
    let mut present=[false;3];
    for code in std::env::args().skip(1) {
        let index=match code.as_str() {"WINDOW_EXPIRED"=>0,"OUT_OF_SCOPE"=>1,"REVOKED"=>2,_=>std::process::exit(1)};
        if present[index] {std::process::exit(1);}
        present[index]=true;
    }
    println!("{}",match present { [_,_,true]=>"REVOKED",[_,true,_]=>"OUT_OF_SCOPE",[true,_,_]=>"WINDOW_EXPIRED",_=>"VALID" });
}
