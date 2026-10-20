# External authority admission experiment

Experimental v2, separate from the normative ACLt protocol. This generation
protects qualification and contributions against **gateway** disk rollback and
gateway cloning. One trusted external authority owns all `(claim, enrolled unit)`
slots and receipts. Gateways are stateless relays, carry no worker credentials or
authority private key, and cannot create a response accepted by a v2 worker.

The authority's own undetected rollback/cloning, malicious workers, worker
memory/disk rollback and physical identity independence remain outside scope.
An internally valid old authority database cannot be detected without another
trusted source. There is one authority, no replication or consensus claim.

## Local verification

From the repository root on Linux, with Python 3, G++ and OpenSSL on PATH:

```sh
make test-authority
```

The 25 local scenarios cover the R01-R12 families, use real loopback TCP and the
existing C++ worker, generate temporary RSA-2048 fixture keys, and write
`artifacts/authority/local-tests.json`. No dependency is downloaded. The RSA/SHA-256
CLI adapter is an experimental authentication choice; it is not ACLt's canonical
encoding/signature profile. Requests use newly enrolled, test-only HMAC secrets;
only the authority holds the RSA private key. Each worker pins the authority
identity, frozen manifest digest and public key independently of the gateway.

`make test` includes this suite. `make workflow` records its source and evidence
fingerprints. These commands require local network permission; a restricted
sandbox denying sockets is an environment failure, not a test pass.

## Invariants

- A durable local `.used` marker precedes requesting qualification. No resume or
  computation retry API exists. An interrupted or unsuccessful attempt can lose
  availability permanently.
- Only a committed authority reservation can grant execution. Every later reserve
  returns `consumed`, including after lost replies; lookup does not reissue tickets.
- The authority, not the gateway, independently recomputes this integer task's
  exact rows before accepting. First invalid result is permanent; exact duplicates
  preserve the original receipt; conflicts preserve the original contribution.
- Only a complete saved submission can be replayed. A reboot may replay that
  immutable packet but cannot start computation again from the same worker store.
- Responses bind v2, authority/config identity, request digest and nonce, task,
  claim/unit, boot and the operation; the request digest also binds ticket/results.
  Workers verify the authority signature before using a grant or receipt.
- The authority opens an existing database in `mode=rw`; loss, corruption, identity
  changes and symlinks fail closed. Initialization is explicit and exclusive.
- Gateway cache recovery is unnecessary: no durable qualification exists there.
  Disconnection never authorizes offline work or offline successful acceptance.

## Services and VM reproduction

`server.py authority --config authority.json` requires a manifest, existing
database and signing/public key paths. Only a deliberate first initialization may
add `--initialize`. `server.py gateway --config gateway.json` needs only upstream
host/port. Both bind localhost by default. `Authority`/`Worker` Python interfaces
are exercised by `check.py`; generated VM fixture configuration is a concrete
deployment example. Never reuse v1 credentials or pretend old receipts migrated.

VM reproduction additionally requires QEMU, cpio, ext4 tools, a compatible kernel,
and a minimal Linux/Python runtime with that kernel's e1000 module. The original
runtime/template and raw evidence are external project artifacts, not included in
the source update archive. Supply them explicitly:

```sh
python3 -B experiments/aclt-authority-admission/run_vms.py \
  --runtime-root /absolute/path/to/compatible/minimal-runtime \
  --kernel /absolute/path/to/compatible/vmlinuz \
  --output /absolute/path/to/new-evidence-directory \
  --accel tcg --random-cuts 20 --seed 20261020
```

Five VMs separate the authority disk, two gateway copies and two worker disks.
Gateway rollback never rolls back the authority or worker volumes. All guest
services run as uid/gid 1000. `--test-admin-port` and `vm_node.py` expose controlled
fault injection only when explicitly enabled; no production API security claim
is made. Do not expose these test endpoints to untrusted networks.

Keep raw images untouched; offline verification must recover filesystem journals
on copies. Count execution intentions (`.started`), completed worker invocations
(`.execution.json`), authoritative grants and contributions separately. A start
marker by itself cannot prove a process actually began.

## Baseline counterexamples and offline verification

The old v1 prototype is deliberately retained with its historical scope. To
reproduce its authenticated rollback/clone counterexamples without computing:

```sh
mkdir -p artifacts/authority
python3 -B experiments/aclt-authority-admission/reproduce_baseline.py \
  --source . --report artifacts/authority/baseline-counterexamples.json
```

After stopping the new VM matrix, recover and check copies of the evidence:

```sh
python3 -B experiments/aclt-authority-admission/check_offline.py \
  --evidence /absolute/path/to/VM-evidence \
  --output /absolute/path/to/new-offline-check-directory
```

The verifier imports no implementation modules. It independently checks SQLite
state/events, input arithmetic, saved packet HMACs, authority signatures and request
bindings, receipt hashes, actual invocation records, source provenance and raw
disk preservation. See the [2026-10-20 engineering record](../../docs/testing/AUTHORITY-ADMISSION-20261020.md)
for this round's results and limits.
