#![no_std]
#![no_main]
// Trusted entry shim: the exported symbol attribute belongs to lowering support.
extern crate user_program;

#[unsafe(no_mangle)]
pub extern "C" fn run() {
    user_program::entry();
}

#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    loop {}
}
