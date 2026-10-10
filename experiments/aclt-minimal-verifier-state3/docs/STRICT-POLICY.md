# Strict local admission contract

## Identity and scope

This experiment has no network voter authentication, aggregate voting or Sybil
protection. The trusted operator administers one persistent local registry and
controls the deployed binary. The default root is `/var/lib/aclt/local-unit`;
`ACLT_REGISTRY_ROOT` at **compile time** can pin another absolute canonical root.
A caller cannot choose another root through CLI arguments or runtime environment.
`init-registry` requires a new directory at that pinned root and never resets an
existing directory. Loss of the directory is not automatically repaired. An
administrator who deletes the registry or rebuilds the deployment can defeat
local history; divergent VM clones and storage rollback require external authority.

The key is SHA256 of UTF-8 `ACLT-LOCAL-CLAIM-1\nstats-int-v1\n` followed by the
ordered canonical signed decimal integer input, separated by single spaces with
no trailing newline. The parser accepts the existing i64 input grammar. Directory,
run UUID, boot, worker path/hash, chunk and budgets do not change qualification.
The first attempt binds chunk/worker in its reservation. This intentionally forbids
repeating identical input even for a new operator-labelled round. Future distinct
claims need an authority-issued contract; adding an arbitrary round ID is unsafe.

## Ordering and acceptance

The entire attempt holds the registry exclusive lock. A create-new `.claim` file
reserves eligibility; write and file fsync followed by directory fsync must succeed
before creating a run directory or starting any worker. Any existing claim object,
including a truncated file or symlink, refuses execution. Existing receipt/pending
objects also refuse before execution. Failure after reservation consumes eligibility.
Loss of an uncommitted reservation before any execution can permit a fresh attempt;
this is not continuation and did not consume a durable qualification.

Every block has at most one worker attempt. Only a whole completed verified result
may create a receipt. The immutable `.receipt.pending` file is written and synced,
then hard-linked to `.receipt` without overwriting, then the registry directory is
synced before returning success. Pending is retained. `.receipt` is the sole local
acceptance record; state DONE and published run results alone confer no contribution.

A crash or directory-sync error after receipt publication can leave a valid receipt
although the caller did not receive success. Audit resolves this as zero or one
complete contribution, never a retry or a second contribution. Successful acceptance
is acknowledged only after directory fsync. No universal physical durability claim
is made from QEMU/ext4 tests. Published receipts cannot be overwritten by this API.
Checksums detect accidental alteration, not adversarial forgery by the operator.

`resume` always refuses before task or registry writes, including same-boot process
failure, clean reboot and complete tasks. `audit REGISTRY INPUT` holds a shared lock,
validates receipt and reservation checksums/identity/binding and mathematically checks
rows without starting a worker, changing counters or modifying files. Repeated audit
returns the same one local contribution. Distributed re-transmission/deduplication
and malicious/conflicting network messages remain unimplemented.

## Commands and test binaries

```
cargo build --offline --locked --bins
# Administrator creates the parent, grants appropriate ownership, then initializes:
coordinator init-registry /var/lib/aclt/local-unit
coordinator INPUT 4 WORKER NEW_RUN normal 1000 1 /var/lib/aclt/local-unit
coordinator audit /var/lib/aclt/local-unit INPUT
```

Build-time pin example: `ACLT_REGISTRY_ROOT=/data/registry cargo build --offline
--locked --bins --no-default-features`. The round's VM deployment uses this pin.

The explicit `admission-test-registry` Cargo feature removes only the deployment
root constraint so separate regression fixtures can create separate trusted domains.
It must never be enabled for a deployed coordinator. Regression copies that binary
as `coordinator-test-registry`; `check-strict.py` and the collaboratively repaired
`check-strict-adversarial.py` exercise the same reservation/receipt logic. Production
root rejection and all whole-VM cuts use the feature-disabled pinned binary.

Old recovery/process/batch suites depend on the retired CLI and retry policy and
are historical, not silently counted as passing under this contract. New-policy
checks, mathematical/profile regressions and exact-language differential checks
are recorded in the round report.
