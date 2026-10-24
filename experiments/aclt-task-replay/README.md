# Work 2 slice 3 — experimental causal journals and immutable submission replay

This experiment adds the complete **bounded experimental** record path:
registered task → issued grant → dispatch/check → durable intent/consume permit
→ invocation intent → outcome → sealed submission → acceptance → worker ACK.
It keeps all prior experiments unchanged. It does not implement formal
ComputeReceipt/Lease/ExecutionCapability/EventRecord, verification TRUSTED or
settlement. Acceptance means structurally bound evidence was retained, not a
proof that the result is correct or that a hostile host executed the program.

## Canonical objects, streams and anchors

The envelope codec is a separate copy of the small candidate CBOR codec, with a
16 MiB cap for snapshots/attachments. It accepts uint/ASCII/bstr/list/text-key map,
shortest encoding and deterministic unique sorted keys. The original commitment
codec, RIR artifact/profile and gas rules are unchanged. Large snapshots beyond
this transport cap fail as host/transport limits, never as guest gas traps.
No new package or software installation is required; stdlib SQLite/fsync and the
existing OpenSSL adapter are used.

`aclt.exp.causal-event@1` has exactly schema_id, stream, seq, prev, kind,
payload_ref and sorted unique parents. Object references are SHA256(raw bytes).
Event IDs use SHA256(u8(taglen)||ASCII(tag)||canonical event CBOR), tag
`ACLt/Experiment/CausalEvent/1`. Stream IDs similarly use
`ACLt/Experiment/CausalStream/1` over `[role,authority_id,task,unit]`, with zero
32-byte task/unit for the authority stream. Sequences start at 1, prev starts at
zero, and cross-stream parents establish the causal DAG.

Worker payloads/attachments are content addressed and fsynced before an exclusive
sequence file. Existing, partial, missing or unexpected event files are rejected;
there is no silent tail truncation/repair. Events use a filesystem lock for
sequence allocation; a separate exclusive launch marker still fences execution.
Authority objects, hash-linked event and materialized projection change inside
one `BEGIN IMMEDIATE`/`synchronous=FULL` transaction. Those projection tables are
caches checked by replay, not a second authority allowed to override events.

A signed `aclt.exp.journal-checkpoint@1` binds authority/deployment, stream,
count/head and canonical projection digest. Offline checking requires both an
independently pinned public-key digest and a **caller-retained checkpoint digest**.
The checkpoint is supplied separately from the export. Hashes alone do not
provide authenticity; valid historical checkpoint/export pairs remain valid
as-of their own anchors. Offline checking cannot discover a newer checkpoint or
solve issuer equivocation/ledger rollback without an external witness.

## Execution and immutable submission

Dispatch and startup keep the previous single-issuer model: actual task/input/RIR,
provider/unit/environment and scope are checked twice, and fresh LAN CONSUME is
committed before guest execution. A new replay environment digest additionally
binds the new wrapper sources. This is deployment binding, not remote attestation.
New deployments/keys/ledgers are explicit; old slice-2 stores are not migrated.

Worker event kinds are DISPATCH_REQUEST, DISPATCH_CHECKED, INTENT, PERMIT, INVOKE,
OUTCOME, PREPARED, SEND, ACK and SUBMIT_DENIED. Authority kinds are REGISTER,
ISSUE, CHECK, CONSUME, ACCEPT, SUBMIT_DUPLICATE, SUBMIT_CONFLICT and
SUBMIT_REJECTED. INVOKE is intent, not proof of physical execution. A crash after
permit or outcome can sacrifice liveness; incomplete work is never recomputed.

The sealed `aclt.exp.submission@1` body binds task/unit/provider/grant/tuple,
worker outcome head, outcome/output references and a one-time submission nonce.
Its immutable package contains the exact worker prefix through OUTCOME and all
necessary byte attachments. The package is fsynced before PREPARED records its
digest. A missing PREPARED record, incomplete/corrupt package or caller-expected
task mismatch prevents replay. No public recovery command assembles an unfinished
submission or resumes computation after a crash.

SEND records a fresh transport nonce and the sealed package digest. The request
includes that event, the saved PREPARED proof and the complete package, all covered
by provider HMAC. A validates structural/causal/outcome-digest/resource bindings;
it **does not reexecute RIR or assert arithmetic correctness**. The first valid
bound package is retained with a pre-signed acceptance receipt and ACCEPT event
in one transaction. Signature/commit/response failures preserve conservative
uncertainty; no consumed execution entitlement is refunded.

The `aclt.exp.acceptance-receipt@1` binds deployment, task/unit/grant/tuple,
submission digest and outcome digest. It is a result-acceptance acknowledgement,
never ReceiptID or a formal verification decision. Exact retransmission returns
the originally stored **same receipt bytes**, independent of transport nonce,
time, expiry after execution or service process restart. An authenticated different
packet after acceptance records conflict and preserves the first receipt; an
invalid first packet records rejection and cannot create acceptance. Replaying the
original complete sealed package remains possible without another CONSUME.

`replay` reads only the saved packet/journal and uses no RIR execution function or
current-boot execution check; thus completed packets may be retransmitted after a
worker reboot/configured environment change. Trusted issuer/provider enrollment
and caller's expected task ID still apply. Local retransmissions serialize on a
filesystem lock. Receipt loss is represented as accepted at A, unacknowledged at
B; a later duplicate response appends ACK without modifying the submission.

## Independent offline reducer

`offline.py` imports neither Ledger, Journal nor worker transition functions. It
uses shared byte/crypto primitives, but has its own phase/state reducer. It reads
only exported bytes plus the separate pinned checkpoint/key, rebuilds task/grant/
consume/acceptance projections, verifies signed permissions/receipts and original
RIR outcome hashes, worker phase order, complete attachments, sequence/prev links,
worker-prefix references, missing parents/forks and the closed causal DAG. It
compares the rebuilt state with the signed checkpoint and live-export projection.
It never invokes a guest, parses a program for execution, or computes stats rows.
This is state-reducer independence, not a second cryptographic/CBOR implementation
or proof of all protocol recovery behavior.

## Reproduce

```sh
make check-task-replay
python3 -B experiments/aclt-task-replay/dualhost.py \
  --peer USER@B_IP --a-host A_LAN_IP \
  --remote-root /absolute/new/B/run --output /absolute/new/A/evidence
python3 -B experiments/aclt-task-replay/offline.py \
  --bundle /saved/final-bundle.cbor --anchor /saved/final-anchor.cbor \
  --public /saved/issuer.pub --public-digest RETAINED_KEY_SHA256 \
  --expected-anchor-digest RETAINED_ANCHOR_SHA256 --report /new/reduced.json
```

The opt-in matrix deploys fixed sources into new independent physical-host paths.
A hosts the trusted journal/acceptance service; B runs the reference guest and
sends CHECK/CONSUME/SUBMIT over real LAN TCP. SSH only controls/provisions/collects.
Strict host-key checking remains on, no firewall/system service changes or VMs.
Private keys remain on A; B enrollment secrets stay outside collected public B
state/source packages. The temporary service is stopped afterward.

Matrix coverage includes identical/concurrent retransmission, authority restart,
conflict, ACCEPT-reply loss with pending ACK, complete PREPARED-package recovery,
actual service unavailability, controlled SIGKILL after INTENT/OUTCOME/PREPARED,
rejection of incomplete replay/relaunch, and corrupt-copy rejection followed by
original-package replay. Separate negative controls alter only copies of retained
exports (truncation, missing proof, object/projection/fork/pin/anchor changes).
The CLI fault_driver process gates/response-drop selector are test-only, not the
normal entry. Process kills/restarts are not physical power-cut evidence.

Trust assumptions remain an honest pinned worker/config/filesystem, A key/clock,
HMAC enrollment and single non-rollback/non-forked authority. This plaintext LAN
experiment has no TLS/DoS protection, production key lifecycle, failover, secure
attestation, arbitrary malicious-host enforcement or independent native Rust
authorization/replay entry. A task/unit launch slot is not statistical eligibility
or an independent sample, and no B/Q/production/Gate conclusion follows.
