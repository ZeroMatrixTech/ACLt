# Deployment revocation for the non-mainnet FM-S3 test route

A bound test deployment enables this operation by pinning
`revocation_version = ACLt/TEST/FM-S3/DeploymentRevocation/1` in its genesis
configuration. The issuer signs the canonical statement `{version, genesis}`
using the FM-S2 signature format with kind `DEPLOYMENT_REVOCATION_V1`.
The Requester submits the issuer signature in a signed
`S3_REVOKE_DEPLOYMENT` request. The ledger checks both signatures, exact
genesis, request validity, monotonic time and nonce conflicts.

Revocation takes effect at the event commit. The ledger records the genesis
and commit time, invalidates unsettled verification for Receipts with no
committed decision, and blocks fresh creation, activation, capability
consumption and result admission. An authenticated retry of the revocation
returns the recorded result. A replayed response to a previously accepted
request is governed by the existing idempotency rules.

Receipts with a committed decision use that decision and the original
settlement policy. For a revoked Receipt awaiting a decision, Phase D uses
the existing `VERIFICATION_INVALIDATING` condition. The signed event and
its position are included in the authenticated ReplayEnvelope/2 history.
A verifier relies on an independently selected checkpoint for that history.
A checkpoint proves the state at the pinned point in the log.

The trust boundary is the fixed test issuer, Requester relay, authority
clock and single committed log. Formal source and Profile approval,
revocation dissemination, freshness and official deployment remain
separate acceptance criteria.
