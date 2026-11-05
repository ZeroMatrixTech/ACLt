# FM-S3a candidate audit contract and signed result replay

Namespace: `ACLt/FM/S3a/1`. This is a **local pure result-validation slice**, not
formal Profile registration, Decision admission or the FM-S3 integration gate.
The [four interface reviews](../../docs/07-roadmap/fm-s3-audit-dependencies.md)
remain OPEN. Global P0-1B coverage and normative 00–03 documents are unchanged.

## Frozen candidate contract

`tools/formal_migration/s3_results.py:profile()` defines exactly one closed test
contract: REEXEC_AUDIT_ONLY, one reexecution by the enrolled AUDITOR, canonical
outcome byte comparison, empty safety/liveness parameters, all 13 applicable
failure events, five ordered decision-condition names and four reachable process
terminals. No B/Q, ClaimTemplate, EligibilitySnapshot, selection or degradation
fields are accepted. The exact profile wire bytes and digest are retained in
`tests/formal_migration/audit-result-vectors.json`.

The candidate `verified_claim_spec={kind:NO_CLAIM}` is an explicit tagged local
representation, **not** resolution of AUDIT-WIRE-BOTTOM or a registered formal
Schema View. Event mappings are fixed local choices: positive/negative map to
CONCORDANT/DISCORDANT; nondeterminism, unavailable objects, stale epoch, revoked
assumptions and equivalence-resource exhaustion map to VERIFICATION_INVALIDATING;
other applicable events map to INCONCLUSIVE. Attribution is NO_ATTRIBUTION in all
rows, with no payment effect. This does not implement all event observation paths.

The profile is stored as canonical CBOR content of the existing AUDIT_CONTRACT
component. `bind_bundle` returns a new bundle and recomputes component references;
policy validation derives a new Receipt digest. A caller must obtain a new
Requester signature and create a new allowlisted test genesis. Existing S2
Receipts and ledgers are not silently migrated. Rebinding does not change input
objects, RIR bytes or fee policies.

## Result and provenance

Every ResultSubmission candidate has exactly:
`schema,genesis,receipt,profile,role,provider,assignment,epoch,intent,consume_event,
outcome,signature`. Digests are byte strings. `profile` is the S3a typed digest;
Receipt additionally binds the full AUDIT_CONTRACT component with S1b hashing.
Signature uses the existing FM-S2 RSA suite and signature input
`CBOR([ACLt/FM/S2/1, ACLt/FM/S3a/1/RESULT, unsigned_result])`.
The assigned Provider must sign its own role; issuer/Requester/other-role keys
cannot substitute. Candidate result references hash the full signed object under
`ACLt/FM/S3a/1/RESULT`, using the shared length-prefixed domain hash.

Validation requires a pinned S2 genesis, a public signed snapshot, and a checkpoint
independently authenticated by the caller. The checkpoint must exactly equal the
snapshot checkpoint. Full S2 replay checks actor signatures, event inclusion and
state/result digests. Results must match the enrolled role's consumed Lease,
epoch, Assignment, intent and unique CONSUME event hash. Proposed, active, fenced,
foreign or altered bindings reject. Snapshots whose replayed authority time has
already reached the Receipt execution deadline reject this entry.

The checkpoint proves facts **as of that authenticated prefix**, not latest-state
or wall-clock freshness. Worker result signatures contain no authoritative
received-at event. Timely result admission and deadline/budget causal ordering
remain required in the subsequent authority integration; supplying an old signed
snapshot cannot by itself prove that a result was received before a boundary.

Only canonical `OK` outcome maps `{outcome,gas_used,output}` are supported initially,
with strict uint/fuel and byte/output limits. Host faults, rejected artifacts and
semantic traps fail closed here. This validates encoding/provenance, not whether
arbitrary output bytes correctly implement stats. The honest pinned-host and
incomplete RPR/sandbox limitations of FM-S2 remain in force.

## Pure replay and remaining work

`replay_pair` requires one signed EXECUTOR and one signed AUDITOR result. It
compares the full canonical outcome bytes, including gas, and returns deterministic
CONCORDANT/DISCORDANT observations and ordered result references. Identical replay
is stable and has no ledger writes, guest calls, receipt changes or fund effects.
It reports no correctness claim, committed Decision or entitlement.

This slice does not accept results into the authority log or resolve conflicting
submissions. Next integration must freeze result identity/idempotency, authenticated
received-at facts, explicit AssumptionEvaluation (including INVALIDATING), method
and condition replay, unique terminal commitment, policy-derived rights/refunds
and read-only recovery. Those transitions require new physical A/B integration
and fault evidence; local pure replay is not a substitute.
