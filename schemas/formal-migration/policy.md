# FM-S1b candidate policy and Receipt contract

This is a test-only candidate, fixed by `policy.json` and
`tests/formal_migration/policy-vectors.json`. It is not official ComputeReceipt,
ReceiptID, LogicalObject, FundingPolicy, SettlementPolicy or imported-schema
registration. Production/official admission stays disabled. All original
normative OPEN states and P0-1B coverage remain unchanged.

## Content and references

Python `tools/formal_migration/policy.py` and independent Rust
`tools/verification_profile/rust/fm_policy.rs` share the existing language-local
canonical CBOR/NFC/SHA core. Each parses, projects typed Schema View, checks types
and constraints, encodes and hashes independently. Rust never invokes Python.
There is no new dependency; OpenSSL remains a shared RSA adapter.

All maps are closed, required UTF-8 text keys. Integers/bytes/SemVer/arrays in
Schema View follow FM-S1a. Fixed enums, wire fields, domain tags, byte/item/depth
limits and version `[1,0,0]` are enumerated in policy.json. Unknown fields,
versions, source/asset, effect, method or reference kind fail closed; no fallback
parsing, empty ID or default policy exists.

`digest(kind, content) = SHA256(u8(tag length) || ASCII tag || CBOR(content))`.
Tags are `ACLt/FM/S1b/<KIND>/1`. They are candidate-domain tags only. Every
reference is `{kind, version:[1,0,0], digest:32-byte bstr}`, never an untyped digest.
A component digest covers its full kind/version/content envelope, not an official
RIR artifact ID. Matching bytes alone do not prove RIR/runtime conformance.

The only declared semantic reference edges are:

```text
Receipt content -> Funding policy content
                -> Settlement policy content
                -> parentless immutable Logical input
                -> RIR/runtime/provenance/equivalence/exposure/availability/
                   deployment-test/audit-contract component bytes
```

Policies carry protocol/schema/encoding/network/deployment and
`{requester_ref,nonce,created_at,expires_at}` scope, no ReceiptID or future
receipt digest. Scope must match Receipt exactly. Leaf maps have no Receipt back
reference or arbitrary reference fields; first-slice input parents must be empty.
Thus all accepted declared edges have depth one. Potential cycles are rejected
by the closed schema before hashing; opaque component bytes are data, not hidden
reference edges or authority instructions. Reusing policy content across
candidate Receipts is not permission to reserve funds twice: instance identity,
nonce uniqueness and authorized balances belong to FM-S2.

Policies are built/hashed first. Receipt then binds their references and every
semantic group. Mutating funding caps, a fee row, input content, execution bounds
or component bytes rejects the stale reference. Legal rebinding yields a new
candidate Receipt digest; changing input/policy/resources leaves the RIR reference
unchanged. The bundle resolves exactly one input and eight ordered components;
missing/extra objects, wrong type/version/context/hash or insufficient input
availability are rejected. Declared retention is not proof of actual persistence.

## Logical input and execution references

Initial input type is FM_STATS_I32_VECTOR, version 1.0.0: canonical CBOR array of
1..256 signed i32 integers, at most 4096 bytes; publisher pin/network/deployment
match Requester/Receipt, creation precedes Receipt, retention covers its deadline.
Output type is a declaration only; output construction and ResultSubmission are
FM-S3 work. No general LogicalObject graph or official schema import is claimed.

Receipt fixes stats-int-v1 test task semantics, entry/output, single-assignment
merge, audit-only method, scope, input/policy references, and eight explicit
component references. RIR/runtime/provenance/equivalence/exposure/availability/
audit/deployment component content is opaque, nonempty, bounded and hash-pinned;
semantic validators and official references are still required before admission.
Fixture component bytes explicitly identify themselves as fixtures.

Bounds include positive fuel/memory/input/output limits, exactly two total
assignments (one execution plus one audit), one guest attempt each, bounded
message retries/recovery queries, explicit deadline, no host capabilities,
wasm32, denied networking and required sandbox. The deployment-test component is
not MainnetAssuranceProfile, and it does not resolve protocol §5's non-mainnet
interface. Full VerificationProfile/DecisionMapping, real assurance and exposure
admission remain pending; a valid candidate bundle is not a runnable task permit.

## Funding and complete finite fee table

Only REQUESTER_PREFUNDED integer FM_TEST_UNIT is supported. Funding declares
separate execution, verification, storage caps and refund reserve; their sum must
fit uint64 and equal total_limit. Execution/verification caps are positive.
Every row must fit each bucket and leave the declared refund reserve unspent.
No source borrowing, subsidy, issuance, partial source mix or implicit top-up.
The cap is a budget, not proof that any balance is available or reserved.

There are exactly **111 explicit rows**, sorted by canonical CBOR of
`[terminal,executor,auditor,storage]`:

- UNRESOLVED, EXPIRED, FAILED, FUNDING_EXHAUSTED each have the 27 combinations of
  COMPLETE/MISSING/HOST_FAULT for execution, audit and storage: 108 rows.
- REJECTED_AT_CREATE, FAILED_PLANNING, UNSUPPORTED each have one all-MISSING row,
  zero fees and full unused-budget return: three prestart exit rows. A claim of
  completed fulfillment in these rows is rejected. This models rejection before
  the supported execution path; proving no reservation bypass is FM-S2 work.
- TRUSTED is absent because audit-only has no ACCEPT. Unknown terminals reject.

All 108 process combinations are conservatively covered; the table does not prove
that every combination or FUNDING_EXHAUSTED is reachable in a fully funded run.
It prevents a possible failure combination from lacking a predeclared outcome.
MISSING/HOST_FAULT in a role implies zero fee for that role. COMPLETE means a
canonical, accepted, current-epoch fulfillment item (including a well-formed Task
trap); it is not a claim that the task answer is correct. A bare caller label is
not such evidence. Fees for COMPLETE are frozen per cell and bounded, not selected
by the requester at settlement or rewarded for matching results.

`fm2-quote` only evaluates hypothetical facts:
`refund = total_limit - execution_fee - verification_fee - storage_fee`.
Refund reserve is returned unused in this no-payment-adapter contract. No client
amount, payer balance, terminal commit, fulfillment authentication, fault
attribution, EntitlementKey, transfer, refund transaction or exposure reservation
is created. Actual settlement must satisfy all five INV-07 premises, current
Lease/epoch and exactly-once ledger rules in FM-S2/S3. Refund output must never be
credited without an existing authorized reservation and terminal-driven rights.
The pure function is idempotent and leaves its inputs unchanged.

## Requester signature

Receipt content digest excludes attached signatures. A Requester signs
`u8(len(tag)) || tag || CBOR(complete Receipt content)` where tag is
`ACLt/FM/S1b/ReceiptSignature/1`. The suite is exactly FM-S1a's pinned
RSA-2048/e65537/PKCS1-v1_5/SHA256, DER SPKI and raw 256-byte signature. Suite
selection is unambiguous through the pinned Requester record; no new algorithm
field or negotiation default exists. The content includes policy digests, so a
changed policy requires a new Receipt digest and signature without a hash cycle.

`fm2-verify` takes a fully resolved bundle, a record/signature and independently
retained expected Receipt/Requester digests plus explicit now. It checks all
bindings, Requester role/network/deployment and validity before RSA. Pins must
come from the consumer, not be copied from an untrusted incoming bundle. New
policy + rebind + new signature + new trusted commitment succeeds; an old pin or
signature fails. Verification is pure, not nonce consumption or registration.
Admission validity is checked before deadline; historical committed Receipt audit
must use retained commit-time facts, not reinterpret a receipt using wall clock.

## Rule map and reproducibility

| Owner | Python / Rust locations | Evidence / limit |
|---|---|---|
| SV-25/42/52/118 | existing core, policy.project/inspect / fm_policy::proj/run | canonical primitive/container/integer/view; not full five-phase Profile |
| INV-01/02/12, FM-A03/04 partial | bundle/digest/receipt / independent counterparts | scope, policy-before-Receipt, closed acyclic references, stale vs rebound vectors |
| INV-06/09, FM-A09/10 partial | funding/settlement/quote | exact 111 cells, uint64/bucket/reserve bounds; no balance or terminal authority |
| ADR-0007 D-1/D-2/D-4/D-6 | scope/references/bounds/signature | fixed test contracts; lifecycle/admission remains pending |

Run `make check-fm-s1b` for 12 default Python regression methods;
`make test-fm-s1b FM_S1B_REPORT=/new/report.json` builds independent Rust, verifies
fixed vectors, all fee cells, negative scope/budget/DAG cases and fresh Receipt
policy re-signing. `make test` also reruns FM-S1a and old Claim vectors.
`python3 -B scripts/fm-s1b-dualhost.py --peer USER@B_IP --remote-root
/new/B/directory --output /new/A/directory` repeats build/byte/quote/signature
checks on the accepted two physical hosts. Strict host key checking and new
independent directories are required. SSH source/vector transfer is not task TCP
or ledger/fault validation. Keys are temporary, not part of vectors or archives.

Changing fields, tags, schema imports, matrix rules or signature suite after
release requires an explicit new candidate version and vectors; do not reinterpret
old digests. Existing experiment evidence and databases are not migrated.
