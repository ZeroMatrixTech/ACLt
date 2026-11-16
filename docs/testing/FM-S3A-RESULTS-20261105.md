# FM-S3a signed result replay (2026-11-05)

Baseline: `d648512893fc039e3c4c8c133d25c79941e42e11` (PR #65 merged).
This report records the first local implementation slice on returning to FM-S3: the closed candidate audit contract and both role-signed ResultSubmission candidates were implemented, a public S2 snapshot replay with a separately authenticated checkpoint establishes the provenance prefix, and local verification passes with 416 default unittest methods plus the existing native, cross-language and sanitizer checks and all 95 Git source pins.
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

These results cover local cryptographic and reducer tests over synthetic outcome
bytes. A new runtime execution or physical A/B run is outside this slice; correct
stats output and timely result admission remain open. Exact checkpoint binding
establishes an as-of prefix; freshness is a separate property. SV rules and global
conformance claims remain as registered before this slice. The four interface
reviews, P0-1B 3/19/97, ADR-0006 PROPOSED, OQ/Gates and official admission keep
their existing status.

## Next concrete slice

Add result acceptance/idempotency and authenticated received-at events to the
single authority; then explicit assumption evaluation and condition/terminal
replay. Process fees/refunds must follow a unique committed terminal and the
frozen policy, never comparison equality alone. Run new physical A/B result,
conflict/retransmission/deadline/fault/recovery cases for the integrated path.
