# Experimental task commitment — work 2, slice 1

This slice binds an existing candidate RIR artifact, explicit input bytes and
execution limits to **ExperimentalTaskCommitment** (`aclt.exp.task-commitment@1`).
Its identity is `experimental_task_id`, never `ReceiptID`. It does not implement
ComputeReceipt, Principal authentication, signatures, active Lease, authorization,
registration, durable event replay, verification verdict or settlement.
The existing authority experiment's result receipt is a separate experimental
acceptance acknowledgement; it must not be reused as this pre-execution identity.

## Authoritative bytes and identity

`schema.json` describes the typed JSON view. Only explicitly marked bstr fields
are rendered as lowercase hex; the CBOR bytes are authoritative. No strings are
guessed as bytes. This candidate encoding supports uint, printable ASCII text,
bstr, array and text-key map only. It requires shortest heads, deterministic map
ordering by encoded key bytes, unique keys, no trailing data and fixed resource
caps; bool, negative integers, floats, tags and indefinite forms are rejected.
This small codec is not the general protocol object codec.

The exact fields are closed: schema/encoding/context IDs, task family, opaque
32-byte requester reference, 16-byte nonce, RIR version/digest/entry, one ordered
input reference (experimental bytes type + raw SHA-256 + byte length), execution
Profile ID/digest, explicit execution limits, and result equivalence rule.
The requester reference is an opaque binding, not proof of identity/control.
The nonce is caller-selected, not evidence of uniqueness or an enrollment grant.

```
experimental_task_id = SHA256(u8(len(tag)) || ASCII(tag) || canonical_commitment_cbor)
tag = "ACLt/Experiment/TaskCommitment/1"
```

The input object digest is SHA256(raw input bytes), not a formal LogicalObject
identity. The RIR digest retains the first work's `ACLt/RIR-0/Artifact/1` domain.
Profile digest uses the separate `ACLt/Experiment/ExecutionProfile/1` domain over
the canonical CBOR representation of `execution-profile.json`.

The profile file is pinned in code and pins the unchanged slice-3 decoder,
interpreter, native Rust interpreter source and SDK. It fixes the limited machine,
ABI/effects and exact-outcome rule. A profile semantic/pin change requires an
explicit profile revision and new golden vectors, never an in-place silent update.
Profile source pins provide consistency checks under trusted deployment; they do
not authenticate a hostile machine, make an engine normative, or prove all RIR
conformance. This binding slice executes the Python reference; it does not add an
independent Rust commitment codec or re-certify the native interpreter.

All four limits are explicit and identity-bound. This experiment supports gas
8192..50000000, output 0..4800000 bytes, exactly two memory pages and call depth
1..64. These are local profile support bounds, not new protocol-wide defaults.
Local interpreter step exhaustion remains HostFault; its diagnostic ceiling is
not moved into Task semantic gas. Input references are opaque bytes: malformed
stats data can still produce the existing program's ABORT after successful binding.

## Freeze and check execution

`freeze()` returns immutable bytes, independent of later caller list/map changes.
Input/limit/requester/nonce changes produce a new experimental task identity;
input/limit changes retain the original rir_digest. Changing the artifact changes
both identities. CBOR map insertion order does not change either identity.

`bind()` requires the caller's **previously retained expected task ID**. A
self-recomputed ID from a replacement object cannot substitute for it. The caller
must retain that ID independently of untrusted transfers; this slice provides no
signed registry or persistence guarantee. Binding rejects unsupported versions,
unknown fields/Profile/equivalence, wrong artifact, missing/extra/changed input,
and incompatible limits before any guest instruction executes. The execution
probe has no CLI overrides for frozen limits. Reference source pins are checked
before loading/executing reference modules. Use a dedicated probe process; another
experiment already loaded under the generic wasm/runtime names is rejected.

```sh
make check-task-commitment
make test-task-commitment TASK_COMMITMENT_OUTPUT=/new/A
# Run the same source independently on physical B, then retrieve its evidence.
python3 -B experiments/aclt-task-commitment/compare.py /new/A /retrieved/B --report /new/comparison.json
```

The self-contained probe reuses the checked-in slice-3 raw Wasm fixture, validates
and normalizes it, creates candidate envelopes and runs binding/identity cases.
It does not invoke rustc or claim a fresh Rust compilation. It saves source pins,
CBOR/input/artifact bytes, typed view, identities, outcomes and rejection reasons;
existing output directories/reports are refused. A fixture is test data, not a
network registry or trusted execution grant. Hostname difference is an auxiliary
check under DUALHOST-SSH-1; hashes are not authenticated provenance.

For a caller-supplied saved artifact/input, with explicit non-secret references:

```sh
python3 -B experiments/aclt-task-commitment/cli.py freeze \
  --artifact /saved/artifact.cbor --input /saved/input.bin \
  --requester-ref HEX64 --nonce HEX32 \
  --gas-limit 50000000 --output-limit 4800000 \
  --memory-pages-limit 2 --call-depth-limit 8 --output /new/frozen-task
python3 -B experiments/aclt-task-commitment/cli.py execute-probe \
  --commitment /new/frozen-task/commitment.cbor --task-id RETAINED_HEX64 \
  --artifact /saved/artifact.cbor --input /saved/input.bin --report /new/result.json
```

`execute-probe` explicitly labels its mode `without-authorization`. This is an
intentional binding test entry, not a deployed worker/production admission path.
Exit 0 is Task outcome (including Task traps/ABORT), 2 is rejection and 3 is host
failure. Non-OK outcomes discard partial output. No signed authorization or
once-only execution is claimed; those belong to the next slice.

`tests/golden.json` is a frozen regression vector from this experiment, not an
independent conformance proof. Default `make check` includes 19 local regressions;
it does not contact B or turn historical runs into current success evidence.
No new third-party dependencies or software installation is required.
