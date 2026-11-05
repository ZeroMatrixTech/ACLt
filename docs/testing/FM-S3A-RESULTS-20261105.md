# FM-S3a signed result replay (2026-11-05)

Baseline: `d648512893fc039e3c4c8c133d25c79941e42e11` (PR #65 merged).
This is the first local implementation slice on returning to FM-S3.
[Contract](../../schemas/formal-migration/audit-results.md) ·
[Machine summary](FM-S3A-RESULTS-20261105.summary.json).

## Delivered

- One closed candidate audit contract, all 13 failure-event keys and five ordered
  condition names, with frozen canonical bytes/digest. No new official registry.
- One-way binding through AUDIT_CONTRACT component content to a new Receipt;
  old Requester signatures/placeholder contracts are rejected on the new path.
- Both role-signed ResultSubmission candidates bind genesis/Receipt/profile,
  Provider/Assignment/epoch/intent and the actual authenticated CONSUME event.
- Public S2 snapshot replay and an explicit independently authenticated checkpoint
  establish the provenance prefix. Pair replay independently derives concordance
  or discordance from full canonical outcome bytes, including gas.
- No terminal, money, new attempt or live-authority API is introduced. Existing S2
  paths and historical evidence stay unchanged.

## Verification and boundaries

Run `make check-fm-s3-results` (also part of default `make check`). Eighteen local
regression methods cover positive freshly signed results, legitimate re-signing of
disagreement, byte/gas comparison, profile vectors and malformed profiles, every
binding mutation even after re-signing, bad signatures/role substitution, missing
and unknown fields, malformed CBOR, output/fuel limits, host faults/traps, active
or fenced Leases, stale/wrong/missing checkpoints, snapshot truncation/tampering,
old Receipt signature rejection, repeat replay and unchanged business state.
Full local `make test` passes, including 416 default unittest methods and the existing native/cross-language/sanitizer checks. Historical Git source verification passes all 95 pins. Final manifest and source-delivery checks pass. The machine summary pins the slice sources and full test-log hash.

These are local cryptographic/reducer tests using synthetic outcome bytes, not a
new runtime execution or physical A/B run. They establish neither correct stats
output nor timely result admission. Exact checkpoint binding proves an as-of
prefix; it is not a freshness oracle. No new SV rule or global conformance claim
is registered. The four interface reviews, P0-1B 3/19/97, ADR-0006 PROPOSED,
OQ/Gates and official admission remain unchanged.

## Next concrete slice

Add result acceptance/idempotency and authenticated received-at events to the
single authority; then explicit assumption evaluation and condition/terminal
replay. Process fees/refunds must follow a unique committed terminal and the
frozen policy, never comparison equality alone. Run new physical A/B result,
conflict/retransmission/deadline/fault/recovery cases for the integrated path.
