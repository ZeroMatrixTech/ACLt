# CI Git source verification follow-up (2026-11-05)

This fix makes Git source verification work in a clean clone with absent or foreign-owned checkouts. The seven new regression tests, all 95 retained source pins and the full local test suite pass; two independently generated packages are byte-identical. Scope is repository tooling only; protocol, runtime, deployment and Gate state are unchanged.

## Failure and diagnosis

[PR #65 job](https://github.com/ZeroMatrixTech/ACLt/actions/runs/42009685044/job/127185225939?pr=65) failed at the first retained source read. The previous script suppressed Git stderr and reported every Git failure as unavailable source. Checkout logs show full-history fetching and safe.directory configuration under a temporary HOME. The retained revision `802cd74389d8b338b7fd5b03c985eab769b7c19b` is an ancestor of branch baseline `58ae7b09e85c7e44b2d6517216e2687448c40643` and is present in a fresh no-local clone.

Container ownership rejection is reproducible locally: with `GIT_TEST_ASSUME_DIFFERENT_OWNER=1` and no inherited Git configuration, an ordinary Git read fails with dubious ownership. This supports the temporary-HOME/ownership diagnosis; the failed online job did not retain the underlying stderr, so its precise Git error remains unconfirmed.

## Change

Shared Git access explicitly trusts only the resolved repository passed by the caller, for each command. It writes no global configuration and uses no wildcard trust. Source readers, retained snapshot archiving and tracked delivery coverage use this helper. Git failures retain exit status, operation and stderr. Only directories without their own checkout receive NOT_RUN_NO_CHECKOUT; a broken checkout fails.

No source pin, expected checksum, original SOURCE-BASELINE record or historical result is relaxed or replaced. Missing revisions and files remain failures.

## Verification

- Seven new regression tests cover container ownership, absent revision/path, unchanged global configuration, archive/nested-directory classification, broken checkout and tracked coverage.
- Clean clone made with `git clone --no-local --single-branch` from baseline: all 95 retained source pins pass with simulated foreign ownership and empty global/system Git configuration; all three migration summaries also pass source verification.
- Full local `make test`: PASS, including 398 default unittest methods and all existing native/cross-language/sanitizer checks. Final manifests pass; two independently generated packages are byte-identical (536 entries). The initial restricted run failed to create a local socket; the full rerun with local socket access passed. Machine-readable results are in [the companion summary](CI-GIT-SOURCE-FIX-20261105.summary.json).
- Online rerun: NOT_RUN for this fix; the user reviews and pushes the follow-up commit. This repository tooling change requires no new dualhost experiment and adds no new dualhost result.
