# Candidate RIR stats-int slice

This experiment extends the slice-2 safe Rust SDK to integer statistics. It is
an experiment, not a normative RIR validator, production RPR, Receipt, verification
method, or settlement implementation. ADR-0006 remains PROPOSED/CANDIDATE.

## Frozen experiment wire: `aclt.rir.stats-wire@1`

One input: little-endian u64 chunk size, little-endian u64 count, then count
little-endian i64 values. Chunk/count are 1..100000, values -1000000000..1000000000;
length must be exactly 16+8*count. All values are checked before output. Abort
codes: 1 input count (unreachable under bound envelope), 2 length, 3 chunk,
4 count, 5 value. Count is bounded before multiplying. No decimal text parsing
is performed by this program.

Each output row is 48 bytes: LE u64 id/start/length followed by LE i64
sum/min/max. Signed integers use two's-complement bytes. Rows follow increasing
input offsets and retain the final partial chunk. `cases.py` explicitly adapts
these rows to the original C++ worker's canonical decimal text. It compares
arithmetic rows and exact candidate binary bytes; it does **not** claim the two
programs consume or emit identical wire bytes. These are candidate experiment
adapters, not settled protocol Logical Objects or frontend contracts.

The user crate forbids unsafe code. Only the SDK FFI boundary and export shim
contain trusted unsafe declarations. There is no allocator, clock, network,
filesystem, native execution fallback, floating point or newly downloaded package.
The normalized Wasm retains a fixed two-page memory and void blocks/functions.
The decoder rejects unsupported sections/opcodes/types rather than executing
unknown extensions. Broader integer instructions are exercised by local rules;
this remains a restricted decoder, not the whole Wasm/RIR validation surface.

## Reproduce

Use the **same** explicit official 1.93.1 prefix prepared in slice 1, including
its wasm32v1-none standard library and rust-lld. `toolchain-lock.json` is unchanged.
Build commands pin executable and target rlib hashes, metadata and compiler flags.
Native Rust uses that compiler and its host std; C++ uses the recorded system g++.
No Cargo downloads or third-party crates/Python packages are required.

```sh
make check-rir-stats-probe
make test-rir-stats-probe RIR_TOOLCHAIN=/pinned/prefix RIR_STATS_OUTPUT=/new/A
# On physical B, deploy the same sources to a fresh independent directory:
make test-rir-stats-probe RIR_TOOLCHAIN=/pinned/prefix RIR_STATS_OUTPUT=/new/B
python3 -B experiments/aclt-rir-stats-probe/compare.py /new/A /retrieved/B --report /new/comparison.json
# Optional existing Node, on A only:
node experiments/aclt-rir-stats-probe/oracle.cjs /new/A /retrieved/B /new/oracle.json
```

Each build invocation compiles Wasm, native Rust executor and C++ baseline twice
in different directories; it saves source hashes, compiler commands/logs,
raw/normalized Wasm, candidate envelope, raw inputs, C++ output, Rust logs and
execution records. It refuses existing output directories. Comparison rehashes
retained files and requires identical sources/toolchain, four matching Wasm/
artifact/corpus hashes, and different observed hostnames. Hostnames alone do not
prove physical, identity or statistical independence; DUALHOST-SSH-1 is assumed.
SSH is deployment/control here: this experiment does not test a LAN task protocol.

## Independent checks and boundaries

`runtime.py` interprets the validated envelope through the Python decoder.
`src/executor.rs` independently decodes canonical **Wasm bytes**, constructs its own
instruction tree, runs its own machine/ABI/gas logic, and emits outcome/gas/output.
It does not consume Python ASTs or call a native stats shortcut. Its entry contract
is a prevalidated module: it is **not** a second full type/canonical/envelope
validator. Candidate outcome CBOR/digest is shared Python post-processing, so
independence is claimed for decoding/execution/gas, not envelope/digest validation.
Both use the same candidate schedule and specification; correlated bugs remain.
Native process timeout/crash and interpreter resource exhaustion cannot count as
Task outcomes. Explicit local step exhaustion is HOST_FAULT (exit 3); rejections
exit 2; Task outcomes exit 0. Task traps discard already written output.

The corpus includes signed extrema, partial blocks, deterministic random inputs,
maximum count (100000), length/chunk/count/value aborts, gas/output boundaries,
call depth, local faults, and hand-written empty/multiply/division/memory/gas
priority golden modules. C++ and independent Python math check valid rows.
Optional Node validates all eight actual compiler modules and checks output,
abort and output-limit semantics, excluding gas/depth/envelope validation.
Default `make check` runs only small local regressions, with no compiler/network
or dual-host success claim. Full compiler/runtime/corpus checks are opt-in above.

The C++ `src/reference.cpp` is an exact snapshot of
`../aclt-minimal-verifier-state3/cpp/worker.cpp`, retained for reproducible builds.
The next slice must bind frozen input/limits/outcome to a Receipt and verification
record. No Gate, P0-1B, production TRUSTED, B/Q assumption or settlement is closed.
