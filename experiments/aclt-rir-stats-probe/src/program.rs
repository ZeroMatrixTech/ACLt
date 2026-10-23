// SPDX-License-Identifier: Apache-2.0
#![no_std]
#![forbid(unsafe_code)]
extern crate aclt_sdk as sdk;

// Experimental wire: LE u64 chunk, LE u64 count, followed by count LE i64.
fn read(offset: u64) -> u64 {
    let mut b = [0u8; 8];
    sdk::input_read(0, offset, &mut b);
    u64::from_le_bytes(b)
}
fn write(value: u64) { sdk::output_write(&value.to_le_bytes()); }

pub fn entry() {
    if sdk::input_count() != 1 { sdk::abort(1); }
    let length = sdk::input_len(0);
    if length < 16 { sdk::abort(2); }
    let chunk = read(0);
    let count = read(8);
    if chunk == 0 || chunk > 100000 { sdk::abort(3); }
    if count == 0 || count > 100000 { sdk::abort(4); }
    if length != 16 + count * 8 { sdk::abort(2); }
    // Validate all values before emitting any rows.
    let mut i = 0;
    while i < count {
        let v = read(16 + i * 8) as i64;
        if v < -1000000000 || v > 1000000000 { sdk::abort(5); }
        i += 1;
    }
    let mut start = 0;
    let mut id = 0;
    while start < count {
        let size = core::cmp::min(chunk, count - start);
        let mut sum = 0i64;
        let mut lo = 1000000000i64;
        let mut hi = -1000000000i64;
        let mut j = 0;
        while j < size {
            let v = read(16 + (start + j) * 8) as i64;
            sum += v;
            lo = core::cmp::min(lo, v);
            hi = core::cmp::max(hi, v);
            j += 1;
        }
        // Each row: LE u64 id/start/size; LE i64 sum/min/max (48 bytes).
        write(id); write(start); write(size);
        write(sum as u64); write(lo as u64); write(hi as u64);
        start += size;
        id += 1;
    }
}
