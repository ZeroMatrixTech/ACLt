# Work 3 slice 2 — frozen exact comparison and fixed test settlement

This independent **v2 experimental deployment** extends slice 1's bounded idea
without modifying its sources or migrating its stores. Only prefunded integer
`aclt.exp.test-unit@1` is used. There is no real asset, external payment adapter,
production issuance, formal EntitlementKey/ComputeReceipt/Lease/EventRecord,
TRUSTED verdict, B/Q evidence or Gate change. Existing Python/SQLite/OpenSSL and
saved Rust/Wasm fixture are reused; no new dependency or Rust compilation.

## Frozen settlement rule and evidence scope

Policy schema/domain are `aclt.exp.funding-policy@2` and
`ACLt/Experiment/FundingPolicy/2`. It retains the closed slice-1 fields and adds
`comparison_rule=aclt.exp.two-complete-match-OK-else-no-pay@1`. The comparison and
money rule are committed before RESERVE and START; changing fee, recipient or
comparison rule conflicts with the original policy for the task.

| Saved evidence | Experimental decision | Paid | Refund | Active reservation |
|---|---|---|---|---|
| Both complete results match exactly and are OK | MATCH_OK | fixed success_fee | cap-fee | cleared |
| Both complete, mismatch or matching non-OK Task outcomes | CLOSED_NO_PAY | 0 | cap | cleared |
| Missing/invalid/incomplete/HostFault/unknown side | PENDING | 0 | 0 | retained |

Comparison covers outcome kind, gas_used, exact output bytes for OK and abort_code
for ABORT. Output bytes and outcome hash are checked, as are task/Profile/limits
via the original commitment and the exact frozen artifact/input. The comparison
object references both original report hashes and the frozen equivalence rule.
The mismatch/no-pay policy is a deliberately limited mechanical test policy, not
fault attribution, punishment, a formal UNRESOLVED/FAILED terminal, or the full
OQ-10 settlement matrix. ACCEPT, Task OK on one host, silence and timeout cannot
select a payment/refund branch. Clients cannot submit arbitrary branch/amounts.

## Distinct authenticated roles and funded execution

Genesis freezes distinct A/B actor references and source/boot/Profile environment
digests. Each actor has separate test HMAC enrollment; B receives only its own
role secret and Requester secret. A's role secret and issuer RSA key stay on A.
A ledger/service and A reference worker share a fault domain; B independently
runs the same Python reference implementation. Two hosts do not make independent
implementations or establish statistical/Sybil independence. HMAC role enrollment
and source binding are honest-host deployment assumptions, not remote attestation
or cryptographic proof that a hostile worker ran a program.

The new `executor.py` is funding-gated: it checks caller-retained expected task ID,
actual artifact/input/policy binding and its current enrolled environment; fsyncs
an O_EXCL local intent; then calls START over TCP. A requires a reservation and
atomically consumes the `(policy,role)` start slot before returning a signed
`aclt.exp.funded-start@1` permit. Permit binds deployment/reservation/policy/task,
actor/role/environment and the frozen binding digest. The worker verifies and
fsyncs the permit and invocation intent before calling the old RIR reference.

A new state directory or nonce cannot reopen a consumed slot. Lost START reply,
HostFault or interrupted/incomplete state can sacrifice liveness; there is no
resume/recompute or automatic refund. This is a dedicated experimental permit,
not formal active Lease/ExecutionCapability; old execution entries remain outside
this funding gate. No claim is made that a hostile host cannot bypass Python.

Complete outcome bytes bind task/role/environment and the exact permit hash.
They are fsynced once and submitted under that role's HMAC. A validates the
structural/resource/outcome hash and funded start, then seals one outcome per
role. Same bytes are idempotent; conflicting bytes cannot overwrite the first.
The authority does not rerun the guest to prove an outcome's arithmetic truth.
Only the separately authenticated role can submit that role's result.
`executor.py submit` retransmits saved bytes without invoking the guest or doing
current-boot startup authorization again; caller policy/role/deployment bindings
still apply. Large outputs beyond the existing 16 KiB object/frame cap fail
conservatively as host/transport limits, not invented Task traps.

## One entitlement, atomic internal payment and refund

SETTLE accepts only policy_id and requires its authenticated payer. It derives its
comparison from the two sealed reports, never a client-provided success decision.
One entitlement ID covers the **whole allocation**, using domain
`ACLt/Experiment/FixedEntitlement/1` over `[authority_id,reservation_id,policy_id]`.
Separate payment/refund requests cannot compete for the same reservation because
there are no independent PAY/REFUND/CANCEL/credit endpoints.

In one `BEGIN IMMEDIATE`/`synchronous=FULL` transaction the ledger creates the
comparison, signed fixed-settlement receipt and unique entitlement, clears active
reserved cap, credits payee paid amount and payer refund, and appends the event.
Signature/event failure before commit rolls everything back. Reply failure after
commit retains the original allocation; STATUS and repeated SETTLE return the
same original receipt. Later RESERVE returns the old reservation proof without
locking funds again; it does not create a second entitlement.

The receipt binds deployment/reservation/policy/task, payer/payee/asset,
entitlement ID, comparison digest, decision and exact paid/refunded amounts.
Amounts are exact integers <=2^63-1 and paid+refunded=cap. There are no rounding
or partial external transfers. Invariants are:

```
sum(account available + account active reserved) = fixed genesis total
sum(active reserved) = sum(reservation cap for policies not yet settled)
for each settlement: paid + refunded = original cap
one immutable settlement allocation per reservation/policy
```

Historical paid/refunded totals are flows already present in current available
balances; do not add them to supply again. This is not the full formal funding
invariant or a general economic model.

## Journal, audit and trust

Funding request/response/event/reservation/export/checkpoint schemas and funding
hash domains are v2; new outcome/start/comparison/settlement schemas are explicitly
experimental @1. The old small canonical CBOR/signature adapters are unchanged.
Checkpoints bind deployment/count/head and compact sorted JSON projection digest.
The projection includes original frozen binding, permits, reports, comparisons
and settlement receipts; immutable reservations remain as proofs after settlement.

`audit.py` has its own state/account reducer and does not import Ledger or execute
a program. It reconstructs funding-before-start-before-outcome ordering, both
original reports, exact comparison, unique allocation, balances and receipts,
and checks the signed checkpoint. It shares schema/byte/crypto helpers; HMAC
request authenticity is accepted from the signed authority journal, not verified
with leaked enrollment secrets. Separately retained key/checkpoint digests are
mandatory. Historical anchors prove as-of state only; hashes do not establish
freshness or solve authority rollback/equivocation.

Assumptions remain honest pinned workers/config/filesystems, private enrollment/
issuer keys and a single non-rollback/non-forked A authority. Plaintext LAN has no
TLS/DoS, production identity/key lifecycle, failover, physical power-cut proof or
malicious-host enforcement. Progress depends on both sides completing; unresolved
reservations may remain locked. Full terminal/fault/source matrices, real payment
adapter idempotency, performance economics and production conformance remain open.

## Reproduce

```sh
make check-fixed-settlement
python3 -B experiments/aclt-fixed-settlement/dualhost.py \
  --peer USER@B_IP --a-host A_LAN_IP \
  --remote-root /absolute/new/B/run --output /absolute/new/A/evidence
python3 -B experiments/aclt-fixed-settlement/audit.py \
  --bundle /saved/ledger-export.json --anchor /saved/checkpoint.cbor \
  --public /saved/A/issuer.pub --public-digest RETAINED_KEY_SHA256 \
  --anchor-digest RETAINED_CHECKPOINT_SHA256 --report /new/audit.json
```

Local checks never contact B. The opt-in matrix uses fresh source-locked physical
host directories, actual TCP FREEZE/RESERVE/START/SUBMIT/SETTLE/STATUS, and separate
A/B local execution state. SSH provisions/controls/collects with strict host-key
checking; it does not substitute for the task protocol. It changes no firewall/
OS service and stops only the temporary service/test processes. Private keys and
configs stay in private directories outside public worker evidence/source packs.

`client.py freeze|reserve|status|balance|settle` retains original request and signed
reply and needs --config/--public/--report; freeze also needs --policy/--commitment/
--artifact/--input, reserve/status/settle need --policy-id. `executor.py execute`
needs --config/--public/--state/--binding/--task-id/--report; `submit` needs saved
--state and --policy-id instead of a new execution. Binding is canonical CBOR of
policy/commitment/artifact/input. Config includes the old funding fields plus
role and environment. `executor.py environment` describes the pinned current
execution environment. Explicit `Ledger(..., genesis=..., witnesses=...)` creates
a new test store; no network initialization or automatic old-store migration.
All reports/directories must be new; existing markers/evidence are preserved.
