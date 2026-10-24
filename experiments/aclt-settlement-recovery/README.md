# Work 3 slice 3 — actual settlement reply loss and process recovery

This is an independent recovery harness over **unchanged**
`aclt-fixed-settlement` v2 transitions, evidence objects and independent auditor.
It does not migrate old stores, change prices/policies, introduce a new protocol
terminal, or use real money/external payment adapters. Only existing Python,
SQLite/fsync/OpenSSL and the saved Wasm fixture are used. No dependency download,
Rust compilation, VM or OS service/firewall change is needed.

## Normal and test-only paths

`RecoveryLedger` inherits the original transitions/projection and preserves their
one-transaction allocation and stable receipts. Its handle wrapper brackets the
actual SQL COMMIT with optional callbacks. Normal `service.py` has no callback;
only explicit `--test-control /private/control.json` enables fault injection.
The local control file binds op/policy/point/mode/token/ready path. It is never a
network request, funding-policy field or production administrative API.

A test gate can:

- drop the TCP reply **after COMMIT**, closing the real connection without a
  response; this does not roll back the allocation;
- fsync a ready marker after appending the uncommitted event but before COMMIT,
  then pause until the harness SIGKILLs its own service process;
- fsync a marker after COMMIT but before response and pause for the same owned
  process kill;
- pause B's execution wrapper after fsynced permit or after complete fsynced
  outcome. The explicit fault driver checks its own script path, pause/race mode
  and `/proc` process start ticks before killing the recorded worker PID.

Service kills target only the `Popen` process owned by the harness, with matching
ready PID/token. Marker point/request/event/receipt digests preserve which boundary
was reached. They are test instrumentation, not independent cryptographic proof
of host behavior. SIGKILL and SQLite hot-journal recovery are process-failure
evidence, not physical power-cut or storage-controller failure guarantees.

The first-settlement race uses two B processes: both fsync ready markers while
the policy is still unsettled, then one common release lets both send their first
SETTLE. Exactly one SETTLED and one DUPLICATE must return identical receipt bytes.

## Read-first recovery

`client.py recover` sends exactly one STATUS request. It validates the signed
raw response and its request/nonce/deployment binding, then checks any returned
settlement receipt's policy/reservation/entitlement/payer/deployment/asset binding.
It never trusts an unsigned decoded view instead of signed bytes.

| Authoritative response | Client diagnostic | Action |
|---|---|---|
| SETTLED with bound original receipt | RECOVERED | retain original allocation; no SETTLE |
| RESERVED | HELD | retain funds; no automatic SETTLE/refund/guest |
| UNRESERVED for a known frozen policy | UNFUNDED | no automatic reservation or payment |
| unavailable, denied or invalid | error | preserve uncertainty; no guessed funding action |

After a known uncommitted request rolls back, the operator/harness can explicitly
issue SETTLE following the query. It still derives the original comparison and
uses the same deterministic entitlement. After a committed lost reply, recovery
only obtains the already saved receipt; retransmissions cannot create new payment
or refund. Client diagnostics are not new ledger/protocol states.

## Execution recovery and immutable evidence

The dedicated executor is a small wrapper of the original funded once-only entry.
Normal calls have no hooks. Its environment digest additionally binds every new
wrapper source plus the original environment/Profile/boot digest; both hosts are
pinned independently before genesis. All original v2 policy/permit/outcome/
settlement/entitlement schemas and hash domains remain unchanged.

If B is killed after complete outcome fsync, `executor.py submit` can transmit the
saved bytes without executing a guest. If B only has the permit, there is no
outcome to send, the slot remains consumed and a clone cannot recompute. Missing
one side cannot manufacture a no-pay terminal or release its reservation. The
precommitted fixed rule still requires two complete role-authenticated outcomes;
HostFault/silence/timeout are not substitute evidence.

A hosts the one trusted ledger/service and A worker, sharing a fault domain; B
hosts requester and B worker. START/SUBMIT/funding/settlement queries use actual
TCP, B→A over LAN, while SSH provisions/controls/collects under strict host-key
checking. Workers use separate persistent directories and HMAC roles. This uses
the same reference implementation on two physical hosts under DUALHOST-SSH-1;
it does not establish statistical/identity or implementation independence.

## Checkpoints and offline verification

The harness saves separate export/checkpoint/reduced files at lost-reply,
rollback, postcommit, pre-race and incomplete-evidence boundaries. Before-COMMIT
kill must recover exactly the prior event/projection/checkpoint; the provisional
event must be absent. Post-COMMIT kill must retain the observed committed event
and original receipt digest. Final offline reconstruction uses the unchanged
independent v2 `audit.py`, never the live transitions or a guest.

Separately retained key/checkpoint digests are required. The auditor shares byte/
crypto/schema helpers and accepts HMAC authentication from the signed authority
journal. Valid historical checkpoints are as-of evidence, not freshness/rollback/
equivocation protection. Honest pinned hosts/config/filesystems, private role/
issuer keys and one non-rollback/non-forked authority remain assumptions. No TLS/
DoS, attestation, production identity/key lifecycle, failover, arbitrary malicious
worker enforcement, formal objects/TRUSTED/settlement assurance or Gate change is
claimed. Unknown reservations can remain locked; this harness adds no emergency
refund or administrative override.

## Reproduce

```sh
make check-settlement-recovery
python3 -B experiments/aclt-settlement-recovery/dualhost.py \
  --peer USER@B_IP --a-host A_LAN_IP \
  --remote-root /absolute/new/B/run --output /absolute/new/A/evidence
python3 -B experiments/aclt-fixed-settlement/audit.py \
  --bundle /saved/final-export.json --anchor /saved/final-anchor.cbor \
  --public /saved/A/issuer.pub --public-digest RETAINED_KEY_SHA256 \
  --anchor-digest RETAINED_FINAL_CHECKPOINT_SHA256 --report /new/audit.json
```

`client.py freeze|reserve|status|balance|settle|recover` uses explicit --config,
--public and new --report; policy-file options match the prior v2 client, and
reserve/status/settle/recover need --policy-id. Reports save original request and
signed response, with an additional recovery_status diagnostic only for recover.
`executor.py execute|submit|environment` retains the prior explicit bindings and
once-only intent/permit/invoke/outcome ordering. `fault_driver.py` is test-only.

Default checks are local regression/model checks and do not run the remote matrix.
The opt-in suite needs fresh local/remote roots, preserves failures, cleans only
its owned processes and retains signed B replies and public worker state. Private
issuer keys/HMAC configs stay in private directories outside collected B public
files and source archives. Operational paths/host identifiers remain local;
public repository summaries use placeholders and source/evidence hashes.
