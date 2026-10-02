use aclt_minimal_verifier::{input, chunk_size, read, verify, summary, RESULT_LIMIT};
use std::{env, process};
fn run() -> Result<(), String> {
    let args: Vec<_> = env::args().collect();
    if args.len() != 4 { return Err("usage: verifier INPUT CHUNK_SIZE RESULTS".into()); }
    let chunk = chunk_size(&args[2])?;
    let values = input(&args[1])?;
    verify(&values, chunk, &read(&args[3], RESULT_LIMIT)?)?;
    println!("{}", summary(&values, chunk));
    Ok(())
}
fn main() {
    if let Err(e) = run() { eprintln!("REJECT: {e}"); process::exit(1); }
}
