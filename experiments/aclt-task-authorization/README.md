# Work 2 slice 2 — experimental authorization and durable launch intent

This experiment connects the unchanged ExperimentalTaskCommitment to a signed
**ExperimentalExecutionGrant**, two checks of that same grant, a trusted online
consume ledger, and persistent worker launch markers. It is not ComputeReceipt,
active Lease/ExecutionCapability conformance, a production scheduler, EventRecord
replay, verification verdict or settlement. The existing unsigned execute-probe
remains an explicitly separate diagnostic; it is never used as this launch path.
Only this trusted Python reference entry is covered, not arbitrary hostile hosts,
OS sandbox enforcement or the independent native Rust executor entry.

## One authority, two checks

A is an explicitly trusted experimental issuer and SQLite consume ledger; B holds
an enrolled provider credential and a separately provisioned public-key pin.
The test issuer is an implementation trust assumption, not a new protocol
Principal or statistical verifier authority. Physical host independence is the
finite DUALHOST-SSH-1 assumption; no Sybil or statistical independence is inferred.

A grant contains exactly: schema_id, authority_id, grant_nonce,
experimental_task_id, provider_ref, unit_ref, environment_digest, scope_digest,
execution_tuple_digest, epoch, not_before, expires_at. Fixed bytes are 16 for the
authority/nonce and 32 for other references; times/epoch are uint below 2^63,
epoch>=1 and not_before<expires_at. Schema is `aclt.exp.execution-grant@1`.
The closed scope binds task/RIR/input references, execution Profile/limits and
result-equivalence rule. The execution tuple binds task, provider, unit,
environment and scope. All use explicit `ACLt/Experiment/.../1` domains (see
common.py). A grant_id hashes canonical grant-body CBOR using
`ACLt/Experiment/ExecutionGrant/1`. It is never called LeaseID or ReceiptID.

The signed envelope is canonical CBOR `{payload: bstr(canonical body),
signature: bstr256}`. Existing OpenSSL RSA-2048/SHA-256 signs
`ASCII("ACLt/Experiment/SignedAuthorization/1") || 0x00 || payload`.
Grant/response schema IDs distinguish their uses; a response cannot replace a
grant. No external cryptographic package or new software installation is needed.
Test private keys and HMAC secrets stay in private runtime directories and are
excluded from source packages/public evidence. HMAC is provider enrollment under
this experiment, not a formal Principal signature or identity-independent unit.

1. Dispatch checks the saved expected task ID, all artifact/input bindings, pinned
   issuer, local provider/unit/environment, and tuple/scope. It sends CHECK to A.
   The signed response is bound to the exact HMAC request digest, nonce, operation,
   deployment and grant. CHECK allocates no execution permission by itself.
2. Startup independently verifies the same grant and bundle against actual bytes
   and current trusted environment. It cannot override scope from a dispatch field.
   It durably writes an exclusive intent, then sends a fresh CONSUME to A.
3. A uses BEGIN IMMEDIATE and synchronous=FULL to atomically check the current
   epoch/grant/time/provider/tuple and change ISSUED to CONSUMED. Each task/unit
   slot can be consumed once. It signs only after COMMIT. Expiry uses A's clock,
   including at startup; B cannot extend expiry via its own clock.
4. B verifies the fresh response and durably saves it before an invocation-intent
   marker and before guest execution. Only then does the existing RIR reference
   execute the bound artifact/input/limits. Successful output and outcome are
   retained with digest/tuple/grant/permit linkage.

A new epoch can supersede an **unconsumed** issued grant; old grant IDs cease to
be active. A consumed slot cannot be renewed by increasing epoch, changing state
directory or restarting the service. This is one experimental launch entitlement
per frozen task/unit, **not** sampling eligibility, an independent contribution,
or prevention of repeated equivalent claims across different task IDs/nonces.
No statistical truth weight follows from these records.

## Persistence and failure boundaries

The local slot filename derives from task/unit, not grant/epoch. O_EXCL + file
fsync + directory fsync precede CONSUME; the accepted permit is fsynced before any
guest instruction. Existing, partial or uncertain markers are not resumed or
removed. A lost permit response, signing failure or disk error after consume can
burn the slot without computing. There is no automatic refund/reissue.
The .invoke marker is intent, not proof that a physical instruction ran. Host
failure never becomes a Task trap. Task outcomes retain the existing RIR semantics.
Large outputs are stored separately, avoiding the small CBOR envelope size cap.

Trust assumptions include honest pinned worker code/config, protected local state,
A's signing/enrollment keys, reliable fsync/SQLite storage, A's clock and A's ledger
not rolling back or being forked. Local state clones are rejected after a consume
by that same live ledger, but authority rollback/fork, malicious providers,
failover, key rotation/revocation, cross-machine attestation and power-cut recovery
remain unsolved. The environment digest includes boot, kernel/Python and wrapper
sources; it is a deployment binding, not remote attestation.

Length-prefixed CBOR requests use existing TCP sockets and per-provider HMAC;
responses are signed. LAN traffic is not encrypted, and the endpoint has no DoS
protection/TLS/production enrollment. SSH is deployment/control only: the actual
CHECK and CONSUME travel over LAN TCP from B to A. A server/network outage denies
startup. This availability requirement is deliberate for this bounded slice.

## Reproduce

```sh
make check-task-authorization                 # local stdlib/OpenSSL regressions
python3 -B experiments/aclt-task-authorization/dualhost.py \
  --peer USER@B_IP --a-host A_LAN_IP \
  --remote-root /absolute/new/B/run --output /absolute/new/A/evidence
```

The opt-in matrix creates fresh local/remote paths, pins/deploys sources, runs B's
local tests, starts a fresh A service on an ephemeral port, provisions **test**
credentials over SSH, and drives real LAN authorization plus B dispatch/startup.
No firewall, SSH host-key, system service or global software settings are changed.
Strict host-key checking stays enabled. Keep the TCP port reachable on the LAN.
Default make check never runs this network matrix or starts VMs.

The matrix covers normal execution, local duplicate, fresh-state clone, authority
process restart, forged signature, wrong input/unit/environment, expiry before
and after dispatch, epoch replacement, two concurrent launches, lost consume
reply, controlled SIGKILL after fsynced intent and after fsynced permit, and actual
service unavailability. It kills only owned test processes identified by fresh
readiness/PID records and verified command lines. Process kill is not physical
power failure. Private signing keys never go to B. A private enrollment secret is
provisioned only to the enrolled worker config. Runtime private directories are
not included in collected B/public evidence or source archives.

Normal runner CLI stages are dispatch and launch (use --help). The explicit
fault_driver.py process gates and service.py --test-drop-consume-file are only
harness faults; default execution has no such fault selector. Exit 0 is dispatch
success or Task outcome, 2 is rejection and 3 is host failure. All output reports,
bundles and state markers refuse overwrites. First-work source/profile and the
previous commitment slice are unchanged; the saved Wasm fixture is reused, with
no new Rust compilation or independent authorization implementation claim.

The next slice is the complete causal event chain, saved submission/replay and
independent offline state reconstruction. These per-attempt files and SQLite
operation rows are supporting evidence, not that completed event contract.
