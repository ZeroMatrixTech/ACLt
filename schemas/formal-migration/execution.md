# FM-S2 limited test integration contract

Candidate namespace `ACLt/FM/S2/1`; **official/production admission is disabled**.
This is the ADR-0007 D-3/D-5/D-6 test route, not official WorkPlan, Assignment,
Lease, EventRecord, assurance, Dispatch or RPR schema registration. Normative
00–03 documents/registries and their OPEN states remain unchanged. The four
[interface review records](../../docs/07-roadmap/fm-s3-audit-dependencies.md)
remain open. No field is silently omitted from a purported official object.

## Deployment and source of authority

A private offline genesis binds a new network/deployment, fixed Requester and
Executor/Auditor PrincipalRecords, a distinct issuer SPKI, finite exact candidate
Receipt allowlist, artifact bytes, native runtime SHA-256, prefunded test balance,
fixed exposure policy, validity and TEST_ONLY scope. Principal suite is FM-S1a's
RSA-2048/PKCS#1 v1.5/SHA-256/DER-SPKI. Only the Requester and Providers are
Principals; the issuer is an implementation signing key. Its signature is not a
Provider acceptance or a verdict. Changing a pin/policy creates another isolated
genesis; it cannot discharge any old obligation. Genesis trust is an operator
out-of-band pin, not a self-authenticated key enrollment or MainnetAssuranceProfile.

Both Assignments are deterministic: `H([genesis, Receipt, role, ASSIGNMENT])`.
A proposal fixes Provider, epoch 1, deadline, all Receipt execution fields,
Logical input reference, raw RIR digest and native runtime digest. A Provider
signs ACTIVATE over genesis/Receipt/Assignment/epoch, transitively binding that
exact proposal. A proposal alone reserves nothing. The first activation atomically
reserves the whole Receipt funding budget and that Assignment's exposure; the
second activation reuses the same funding reservation and reserves its own
exposure. There is one balance/held bucket pair, one Lease projection, one event
stream and one SQLite COMMIT point. There is no CHECK, funded-start or legacy
import API in this deployment. Historical experimental code remains unchanged.

One fixed deployment window is used, with separately checked concurrency/value/
attempt caps for Provider, unknown shared cluster, Receipt, window and global.
Unknown actors have no enrollment; the two enrolled Providers still share one
conservative correlation pool. This is a conservative test cap, not learned
correlation, B/Q, identity independence or monetary loss calibration. Value is the
corresponding execution/verification budget; whole funding is a separate bucket.

## Wire, signatures and atomic effects

Canonical CBOR is parsed using the bounded P0-1 codec; no JSON Schema View is
accepted over TCP. Every closed request has exactly:
`schema, genesis, actor, nonce, issued_at, expires_at, op, body, signature`.
Signature input is canonical CBOR `[ACLt/FM/S2/1, REQUEST, unsigned_request]`.
Typed digests are 32-byte bstr, integers are uint64, epoch is exactly 1. Unknown
fields, old schema/op, context, role, signature, nonce conflict and stale requests
reject. Caller time is never authoritative: the server supplies time. Requests
last at most 120 logical seconds and respect Principal and genesis validity.

| Operation | Exact body | Effect |
|---|---|---|
| CREATE | bundle, receipt_signature | Requester signature over full request plus FM-S1b Receipt signature; validate full DAG/policies and finite allowlist; freeze two proposals; consume scoped Receipt nonce |
| ACTIVATE | receipt, assignment, epoch | Provider accepts exact proposal; funds + all five exposure dimensions + Lease + nonce + event commit together |
| CONSUME | receipt, assignment, epoch, capability, intent | Same Provider, active Lease and deadline; persist sole consumed Attempt and worker intent; no second epoch or replacement Attempt |
| QUERY | receipt | Authenticated projection and proof; finite fresh-query budget per actor/Receipt; no execution permission by itself |
| FENCE | receipt | Requester after authority deadline; disable future activation/consume and release exposure; **funding remains held pending FM-S3** |

Capability is `H([CAPABILITY, genesis, exact_proposal])`; it is a reference to
current authority state, not a bearer token permitting offline execution. Same
nonce + identical mutation returns its original result; different content fails.
Old activation/consume duplicates past the deadline do not reauthorize execution.
QUERY duplicates return the current authenticated view without another budget
charge. No client-selected time, fee, terminal or fulfillment is admitted.

H is the existing length-prefixed domain hash with tag `ACLt/FM/S2/1` over CBOR.
Event fields are `schema,genesis,seq,prev,parents,now,request,state_digest,
result_digest`; genesis is implicit parent of event 1, later parents are exactly
the preceding event hash. Request signature facts, reducer projection, nonce
consumption and event are committed together (`BEGIN IMMEDIATE`, FULL SQLite
synchronous mode). Signing happens before COMMIT; failure rolls back. Success
response is released only after COMMIT. Rejections change no business/event
state; unsigned transport errors are diagnostics, never authenticated state.

Signed response payload has `schema,genesis,request,now,result,checkpoint,events`.
It binds the exact request hash/challenge. Checkpoint has schema/genesis, sequence,
head and state digest; the retained issuer signature covers it with the RESPONSE
domain. Clients verify the complete bounded prefix against genesis and any
independently saved anchor, checking inclusion and extension consistency. Offline
replay additionally verifies the original actor signatures and recomputes every
state/result digest, then compares the stored projection. No rollback/fork
protection is claimed beyond a saved anchor; a malicious issuer can equivocate
between clients. Fixed test bounds: 256 committed events, 900000-byte frame,
shared codec byte/item/depth limits. Exhaustion refuses atomically.

## Worker and restricted runtime

B's executor and A's auditor use separate private role keys and durable directories.
The adapter checks the runtime SHA, approved Receipt/bundle and exact proposal,
queries the same authority (Dispatch check), fsyncs intent, then calls CONSUME
against that authority (RPR entry check). No permission response means no guest.
Each worker invocation performs at most one query and one consume, with no hidden
transport/guest retry. Missing/unknown outcomes remain unknown. A restart with an
intent never invokes guest again, including the conservative crash-before-start
case. Explicit query/retransmission uses frozen budgets; no automatic new attempt.

Only the pinned raw stats artifact is executable. Logical i32 vector is lowered
to the stats binary input ABI as little-endian `(chunk_size=2, count, i64 values)`.
The raw-artifact Rust entry independently validates and executes with Receipt
fuel=50000000, memory=131072 bytes, output=4096, and fixed additional bounds
call depth=8/host steps=20000000. All limits and the mapping are part of this test
contract/proposal/runtime pin, not newly accepted ADR-0006 rules. Host faults
never get semantic outcome bytes/digests; a saved local outcome is only an
observation, **not a signed ResultSubmission, fulfillment or payment right**.

This adapter assumes an honest pinned native host. It is **not** a completed OS
sandbox, full RPR contract or hostile-worker boundary. The candidate Receipt's
sandbox declaration remains an unmet formal admission requirement; the explicit
test runtime component records this discrepancy. No official entry can be enabled
from these tests. Full validator conformance, hostile native behavior, power loss,
authority rollback/failover, official Phase B/non-mainnet assurance, Profile,
AssumptionEvaluation, ResultSubmission, terminal and settlement belong to later
work. No TRUSTED/ACCEPT/quote-based payment is implemented.
