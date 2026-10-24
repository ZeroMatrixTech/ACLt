# Work 3 slice 1 — experimental funding policy and atomic reservation

This is a **prefunded integer test-asset** experiment, not real money, an issuance
mechanism, formal FundingPolicy/SettlementPolicy, payment/refund implementation,
verification verdict or production admission. Prior experiments stay byte-for-byte
unchanged. It uses existing Python/SQLite/fsync/OpenSSL and the old candidate
CBOR/signature adapter; no new dependencies, Rust compilation or guest execution.

## Frozen objects and authority

`aclt.exp.funding-policy@1` is a closed canonical CBOR object: task, requester,
payee, asset, decimal_places, source, authorized_cap, success_fee, settlement_rule,
refund_rule and pending_rule, plus schema_id. References are 32-byte opaque values;
task is the existing experimental_task_id and requester must match its commitment.
FREEZE also binds actual commitment/artifact/input bytes with the old binding
checker. Authentication is trusted test HMAC enrollment, not formal identity proof.

Only `aclt.exp.test-unit@1`, decimal_places=0 and prefunded-test-balance are allowed.
Amounts are exact integers 0..2^63-1; reservation cap is positive, success_fee<=cap,
and the sum of fixed genesis balances cannot exceed that bound. Floats, negatives,
bools, implicit credit and undeclared assets/sources are rejected. There is no
runtime mint/top-up/transfer endpoint. Genesis balances are explicit test fixtures.

The policy freezes fixed success fee and rule IDs:

- `aclt.exp.exact-evidence-fixed-fee@1`: a later eligible exact-comparison decision
  may pay the fixed fee and return the remainder;
- `aclt.exp.closed-no-pay-full-refund@1`: a later valid closed no-pay decision may
  return the full reservation;
- `aclt.exp.unknown-hold-reservation@1`: uncertainty retains the reservation.

These are experimental policy commitments, not implemented decision/payment/refund
transitions. No current ACCEPT, Task OK, timeout, silence or host failure is by
itself an eligible settlement decision. Formal outcome/fault matrices and evidence
validation remain later work; these rule IDs do not settle OQ-10.

Policy ID = SHA256(u8(taglen)||ASCII(tag)||canonical policy), with
`ACLt/Experiment/FundingPolicy/1`. One task has exactly one frozen policy per
funding deployment, even before reservation. Same bytes return DUPLICATE; changed
cap/fee/payee/rules conflict without replacing the original. The funding object is
an additional experiment object, not a mutation of ExperimentalTaskCommitment or
an invented ReceiptID. Repeated nonce/transport requests cannot make a new policy.

## Ledger transitions

A single trusted SQLite authority implements only FREEZE, RESERVE, STATUS and
BALANCE. Requester HMAC covers closed schema/deployment/requester/nonce/op/data.
Replies are signed with the existing RSA-2048/SHA-256 adapter and bind request
hash/nonce/op/deployment/event. Private keys stay on A; enrollment secrets stay in
private directories and never enter exports or collected B public files.

RESERVE takes only policy_id, never a caller-supplied amount. It derives the cap,
authenticates its payer and atomically moves available→reserved. A unique policy
row and deterministic reservation ID prevent extra locks across new nonces,
concurrent clients or service restarts. Reservation ID uses the domain
`ACLt/Experiment/FundingReservation/1` over `[authority_id,policy_id]`.
A signed `aclt.exp.funding-reservation@1` binds deployment, reservation/policy/task,
payer/payee, asset and amount. It is retained once; duplicates/STATUS return the
same stored bytes. Unknown policy or wrong payer is DENIED. Insufficiency leaves
balances unchanged; it is an experimental prefunding rejection, not a protocol
FUNDING_EXHAUSTED terminal or permission to execute with a partial budget.

Balances, reservations, original receipt and event commit in one
`BEGIN IMMEDIATE`/`synchronous=FULL` transaction. Event/signature failure before
commit rolls all changes back; failure after commit can lose the response while
retaining the reservation. Query the original policy/reservation before recovery;
this slice never automatically refunds or retries an external payment. It has no
PAY, REFUND, CANCEL, credit, grant or execution endpoint. All reserved funds remain
locked until a later explicitly implemented settlement transition.

For every state:

```
sum(available + reserved) = fixed genesis total
sum(account reserved) = sum(unique reservation amounts)
available >= 0; reserved >= 0
reservation amount = frozen authorized_cap
```

These checks are this slice's conservation contract. Do not add future Settled or
RefundReserved twice or equate this two-bucket projection with the full formal
funding invariant. Funding reservation is also distinct from Provider exposure or
execution-slot consumption. The old execution entries do not consult this ledger;
a future combined admission must enforce frozen policy+reservation before grant
and invocation. A reservation receipt itself is not a launch capability.

## Journal, offline verification and trust

Events contain schema/seq/prev/kind/data, canonical CBOR, hash domain
`ACLt/Experiment/FundingEvent/1`. GENESIS is first; authenticated operation events
retain request bytes and decision/receipt. Rejected malformed/unauthenticated
packets fail before state changes and are not advertised as committed events.

The separately saved signed checkpoint binds deployment/count/head/projection
hash. Projection uses sorted compact ASCII JSON; event/receipt objects use the
small existing canonical CBOR codec (16 KiB per object/frame). `audit.py` has its
own transition reducer and imports neither Ledger nor its transition functions.
It verifies task binding, policy immutability, conservation, unique reservation,
original signed receipts, decisions and signed head/projection. It shares byte/
crypto/schema helpers; offline HMAC authenticity relies on the signed authority
checkpoint, not possession or independent verification of enrollment secrets.

Offline audit requires independently retained issuer-key and checkpoint digests.
A valid historical checkpoint proves only its own as-of state. Hashes do not
establish freshness, production finality or prevent trusted-issuer rollback/forks.
Assumptions remain honest client/config/host/storage, private key/enrollment, and
one trusted non-rollback/non-forked A ledger. Plaintext LAN has no TLS/DoS or
production key lifecycle/attestation/failover. Process restart is not power-cut
verification. Two physical hosts are the bounded DUALHOST-SSH-1 assumption, not
statistical/Sybil independence. Formal objects, Gates and assurance are unchanged.

## Reproduce

```sh
make check-funding-reservation
python3 -B experiments/aclt-funding-reservation/dualhost.py \
  --peer USER@B_IP --a-host A_LAN_IP \
  --remote-root /absolute/new/B/run --output /absolute/new/A/evidence
python3 -B experiments/aclt-funding-reservation/audit.py \
  --bundle /saved/ledger-export.json --anchor /saved/checkpoint.cbor \
  --public /saved/A/issuer.pub --public-digest RETAINED_KEY_SHA256 \
  --anchor-digest RETAINED_CHECKPOINT_SHA256 --report /new/audit.json
```

Default checks run local regressions only, never network/integration. The opt-in
matrix source-locks both deployments, runs B regressions, and sends real B→A LAN
funding requests. SSH provisions/controls/collects with strict host-key checking;
only its new test directories/processes/ports are used. A runs the single funding
service/ledger; B is the authenticated requester, not a computing Provider in this
slice. No VM or OS service/firewall changes. Errors preserve evidence and fail;
there is no fallback to a second local ledger.

`client.py freeze|reserve|status|balance --config /private/payer.json --public
/issuer.pub --report /new/response.json` saves original request and signed reply
alongside its decoded view. Freeze additionally needs --policy/--commitment/
--artifact/--input; reserve/status need --policy-id HEX64. Config is private and
must include explicit host/port/deployment/payer/secret/key pin. `Ledger(...,
genesis=...)` is an explicit fresh-store test setup API, not a network operation;
opening an existing store never initializes or replaces it. Keys, configs,
databases and runtime directories are excluded from the source package.
