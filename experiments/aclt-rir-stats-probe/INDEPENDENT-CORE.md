# RIR independent stats-core entry

Scope `RIR_STATS_INDEPENDENT_CORE_1` is a candidate implementation/evidence slice.
It is **not** complete RIR-0, RPR conformance, ADR-0006 acceptance or production
admission. `independent-contract.json` declares the restricted support and open
work. The historical executor.rs, Wasm/Python oracle, lowering sources and prior
evidence remain unchanged. A new `src/independent_executor.rs` entry forks the
existing Rust interpreter and adds `src/core.rs`; it has no raw-body bypass.

## What is independent now

The Rust process receives raw RIRArtifact CBOR, not Python's Wasm AST or a
prevalidated body. It independently performs:

1. Canonical CBOR read/re-encode and exact closed envelope/type/version checks.
2. Supported Wasm instruction parsing and canonical rewriting: shortest LEB128,
   section order, local declaration merging, empty-else omission and no custom
   sections. Full table/element/data module grammar is not claimed.
3. Conservative stats-subset checks and independent operand/control type checking,
   import ABI/uniqueness, local/global/call/branch bounds, mutability and alignment.
4. Restricted static and declared RPR limits, one supplied input matching arity,
   and revalidation against the caller-retained expected artifact digest.
5. Execution, Task outcome CBOR encoding and domain-separated SHA-256, including
   exact output bytes, gas and abort code. Python never supplies a result digest.

Rust reuses the already independent Rust primitive CBOR/NFC/SHA implementation via
crate-internal functions. Python uses its existing decoder, normalizer, validator
and interpreter; it shares no executable codec/hash with Rust. Shared rules,
Unicode data version and vectors do not by themselves prove correctness.

The Python oracle wrapper classifies the existing restricted parser's diagnostics.
Neither it nor Rust is a general seven-stage Wasm validator. Resource guards,
unsupported module sections and combined out-of-core errors still need the full
ADR-0006 rejection-order suite. The four A codes in the fixed vectors are scoped
to this core; do not claim full phase conformance from them.

## Explicit entry and support

Build from repository root:

```sh
rustc --edition=2021 -D warnings -C overflow-checks=yes -O \
  experiments/aclt-rir-stats-probe/src/independent_executor.rs -o /tmp/rir-core
/tmp/rir-core --support
/tmp/rir-core --artifact ARTIFACT.cbor INPUT.bin GAS OUTPUT_BYTES \
  CALL_DEPTH LOCAL_STEP_LIMIT MEMORY_PAGES EXPECTED_RIR_DIGEST
```

Expected digest must be retained by the trusted consumer, not obtained by copying
an untrusted submission. It is an artifact pin, not a formal ReceiptID or execution
capability. `--support` declares no production admission and no full ADR conformance.
Current core: artifact ≤1 MiB, exactly one input ≤2,000,000 bytes, five `aclt` ABI
imports, integer/void-control stats subset, required sections 1/2/3/5/6/7/10, two
memory pages, ≤64 types/32 defined functions/16 parameters/4096 locals/1024 globals,
≤128 control depth, ≤512 KiB function bodies, gas 8192..50,000,000, output
0..4,800,000 bytes, call depth 1..64. Other valid RIR programs may be conservatively
unsupported by this implementation; its limits are smaller than full ADR-0006.

Limits are explicit inputs. Unsupported bounds reject before execution. The local
step ceiling is a host resource guard, never a Task gas result. Input too large
for declared support rejects with LIMITS; I/O loss is HOST_FAULT. Expected artifact
mismatch yields RPR_REVALIDATION_MISMATCH with no Task result. A named
`test-memory-fault` final argument injects only a host-allocation failure path;
it is off by default and is not evidence of real physical OOM containment.
Initial linear memory and output growth use fallible reservation. All-process
OOM/kill handling and every allocation site remain wider RPR work.

## Result wire and faults

Task output is `{status:TASK_OUTCOME, rir_digest, result,
canonical_outcome_hex, outcome_digest}`. Result CBOR contains `outcome`, `gas_used`,
`output` as raw bstr for OK, or `abort_code` when ABORT; trap results discard partial
output. The digest tag is `ACLt/RIR-0/ExecutionOutcome/1`. Artifact tag is
`ACLt/RIR-0/Artifact/1`. This is the candidate RIR outcome contract, not protocol
VerificationEvidence or TRUSTED.

A codes produce only `REJECTED` and `code`, exit 2. C produces only `HOST_FAULT`
and `code`, exit 3. A/C never emit a Task result, CBOR or outcome digest. Success
and deterministic Task traps use exit 0. No wall-clock/network/hidden I/O enters
Task semantics. This core does not consume a nonce, create a Lease, authorize
funding or generate a verification verdict.

## Reproducible evidence

`make test-rir-independent RIR_INDEPENDENT_REPORT=/new/report.json` compiles the
Rust binary, compares 38 fixed vectors, 39 stats datasets, 80 seeded programs,
standalone execution without Python/source/OpenSSL in PATH, caller-pin mismatch,
real missing input and an output >1 MiB. Seeded arithmetic values are written to
memory and emitted, so numeric differences cannot hide behind dropped values.
Each Task outcome's raw CBOR and digest is compared with Python's result; Rust's
stdout is never supplemented with Python hashing. Reports retain source pins,
RPR support and deterministic results SHA-256.

`python3 -B scripts/rir-independent-dualhost.py --peer USER@B_IP --remote-root
/new/B/directory --output /new/A/directory` deploys a fixed source snapshot over
strict SSH into a new directory, builds/runs independently on the two accepted
physical hosts and checks equal result-summary hashes. Hostnames alone do not
prove independence. This is raw-artifact execution/encoding evidence, not task
TCP, Lease/ledger integration or network-fault admission.

## Remaining gate before formal execution

- Complete Wasm/RIR grammar, full allowed instructions and quantitative space.
- Complete seven-stage rejection priority, general import/section and combined
  invalidity vectors, including table/element/data and typed control.
- All ADR-0006 §13 gas/depth/memory.grow/call_indirect/HostFault conformance.
- Formal Receipt binding and actual ReceiptID/version/limit identity tests.
- ADR-0006 §11 normative synchronization, human acceptance and deployment evidence.

FM-S2's authorization/atomic-reservation/event code can progress against a bounded
candidate interface, but this core success does not admit the formal end-to-end
execution path or close MG-01/MG-02, P0-1B or G2.
