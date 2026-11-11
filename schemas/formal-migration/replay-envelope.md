# Non-mainnet FM-S3 Phase B/D replay envelope

`ACLt/TEST/FM-S3/ReplayEnvelope/1` is the version of the historical replay
adapter for the first `REEXEC_AUDIT_ONLY` route under ADR-0008. It uses
deterministic CBOR with closed text-key maps. Hash inputs include the length
and ASCII bytes of the domain tag as specified in Verification Profile §17.4.

## Registry and trust

The verifier takes registry bytes, their SHA-256 pin, and an ordered list of
Receipt IDs from its caller. Registry v1 is `{version, deployments}` with
entries keyed by lowercase genesis hex. Each entry is
`{deployment, config_sha256, profiles, anchor, checkpoint}`.
`profiles` is a sorted unique list of FM-S3 audit Profile digests.
The declaration follows the field layout of Verification Profile §9.2.2.
For this adapter, genesis is the FM-S2 config commitment, the trust root
is SHA-256 of the issuer SPKI DER, the funding cap is the configured
test balance, and the asset is `FM_TEST_UNIT`. The seven approved test source
contracts are defined in `phase_d_envelope.SOURCE_CONTRACTS`. Each reference
has version `[1,0,0]` and a domain-separated digest over `{role, contract}`.
The frozen audit Profile commits the applicable start, result and closure rules.

The verifier requires the config and declaration to match the registry entry.
It then verifies the signed snapshot, anchor, exact expected checkpoint,
state transitions, and existing settlement. The test clock, revocation and
closure facts come from authenticated replay. The checkpoint is an exact
historical pin. Deployment funding checks constrain held funds. A failed
activation may still produce a funding-exhausted decision for a Receipt
whose requested funding exceeds available funds.

## Wire

```text
Envelope = {version, config, snapshot, records}
RecordPair = {phase_b: bstr, phase_d: bstr}
DeploymentBinding = {network_id, genesis, deployment_ref: {tag: NONMAINNET_TEST, ref}}
PhaseB = {version, phase: B, deployment_binding, receipt_id, profile_digest,
          create_event, deadline, funding_ref, funding_limit, funding_held, leases}
Lease = {role, assignment, epoch, provider, state, capability?, activate_event?, consume_event?}
PhaseD = {version, phase: D, deployment_binding, phase_b_digest, source_digest, candidate_record}
```

The order of pairs matches the caller's Receipt selection. Each Phase B
record binds the frozen Receipt and its committed CREATE event. It records
the two leases in the fixed FM-S2 role order using their state before
finalize. ACTIVE and CONSUMED include the capability and ACTIVATE event.
CONSUMED additionally includes the committed consume event. Optional keys
are omitted. The Phase D link uses
`H("ACLt/TEST/FM-S3/ReplayEnvelope/1/PhaseB", PhaseB)`.
`source_digest` is the existing R11 Phase D source commitment.
`candidate_record` contains the R12 CBOR bytes. Each pair must match
authenticated replay byte for byte.

The replay preserves the historical Receipt ID, state, signatures, decisions
and settlement. Formal receipt creation and formal Phase B/D activation
require approval and verification of the deployment, source and wire contracts.
