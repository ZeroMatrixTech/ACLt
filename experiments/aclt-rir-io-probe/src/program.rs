#![no_std]
#![forbid(unsafe_code)]
extern crate aclt_sdk as sdk;

pub fn entry() {
    if sdk::input_count() != 1 { sdk::abort(1); }
    if sdk::input_len(0) != 16 { sdk::abort(2); }
    let mut bytes = [0u8; 16];
    sdk::input_read(0, 0, &mut bytes);
    sdk::output_write(&bytes);
}
