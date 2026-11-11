# Deployment-bound creation for the non-mainnet test route

The FM-S3 authority recognizes `CREATE_BOUND` for deployments whose pinned
configuration sets `creation_version` to `ACLt/TEST/FM-S3/BoundCreation/1`.
The existing allowlist approves the underlying Receipt digest, which commits
the task, inputs, audit Profile and policies before the deployment hash is
computed. The new ReceiptID commits that digest and the deployment binding.
This ordering avoids a circular dependency between the genesis commitment and
ReceiptID.

The signed authority request carries `{bundle, creation, receipt_signature}`.
The creation object contains four exact canonical CBOR maps:

```text
creation = {intent, transcript, receipt, deployment_evidence}
intent = {version, deployment_binding, base_receipt_digest, profile_digest, requester_ref}
transcript = {version, intent_digest, deployment_binding, evaluated_at}
receipt = {version, deployment_binding, profile_digest, base_receipt_digest,
           intent_digest, transcript_digest}
```

The deployment evidence and binding use the declaration and source references
from the non-mainnet replay registry. The authority derives these from its
pinned configuration. The transcript instant equals the signed request issue
time and is at or before commit. The authority checks the deployment, requester
and deadline windows, test asset and deployment cap. It reconstructs all four
maps and verifies the requester signature using the FM-S2 signing format with
kind `BOUND_RECEIPT_V1`. The digest domains append `/Intent`, `/PhaseI` and
`/Receipt` to the creation version. Digest framing follows the existing
canonical CBOR domain hashing convention.

The state commits the new ReceiptID and the exact signed creation Receipt.
Assignment, Lease, capability, decision and settlement use that ReceiptID.
Settlement checks the underlying policy quote against the base commitment and
uses the bound ReceiptID for entitlements. Bound deployments accept the new
create operation only. Retrying the identical signed create recovers the
original result.

ReplayEnvelope/2 is selected by the pinned creation version. Phase B adds
`creation_receipt` and verifies it against the committed creation event, state,
Profile and deployment. Phase D binds this Phase B under the version 2 digest
domain and includes the R12 candidate decision. Legacy configurations use
ReplayEnvelope/1 with their existing wire and digest domains.

The evidence is scoped to the finite test deployment, signed local authority
time and the fixed audit Profile. Formal approval of Profile, source
authorization, deployment revocation and official conformance has its own
acceptance criteria.
