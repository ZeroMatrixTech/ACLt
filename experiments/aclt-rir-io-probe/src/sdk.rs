#![no_std]
// Trusted FFI boundary. User crates depend only on the safe functions below.
#[link(wasm_import_module = "aclt")]
unsafe extern "C" {
    #[link_name = "input_count"] fn raw_count() -> u32;
    #[link_name = "input_len"] fn raw_len(index: u32) -> u64;
    #[link_name = "input_read"] fn raw_read(index: u32, offset: u64, dst: u32, len: u32);
    #[link_name = "output_write"] fn raw_write(src: u32, len: u32);
    #[link_name = "abort"] fn raw_abort(code: u32) -> !;
}

pub fn input_count() -> u32 { unsafe { raw_count() } }
pub fn input_len(index: u32) -> u64 { unsafe { raw_len(index) } }
pub fn input_read(index: u32, offset: u64, dst: &mut [u8]) {
    // wasm32 pointers/lengths fit u32; the borrow keeps this writable slice live.
    unsafe { raw_read(index, offset, dst.as_mut_ptr() as u32, dst.len() as u32) }
}
pub fn output_write(src: &[u8]) {
    // The host contract reads exactly this live immutable slice.
    unsafe { raw_write(src.as_ptr() as u32, src.len() as u32) }
}
pub fn abort(code: u32) -> ! { unsafe { raw_abort(code) } }
