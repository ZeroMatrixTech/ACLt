# Public repository settings checklist

The maintainer applies and verifies these settings after the repository becomes public. Record the verification in the first public release checklist. [Release audit](https://github.com/ZeroMatrixTech/ACLt/pull/135) · [Stage decision](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6892853713)

- [ ] Protect `main` after the repository becomes public: require a pull request, a passing `local-validation` check, and an up-to-date branch before merging; block force pushes and deletion of `main`. Add DCO to the `main` branch protection rule or ruleset as a required check for the verification, under the exact name observed on a pull request. On a real external fork pull request with all other merge requirements satisfied, push a commit without a `Signed-off-by` trailer and confirm that merge is blocked because of the `dco` check (a failing workflow alone does not count); then add the trailer, push, and confirm that the latest head passes and merging is available again. Keep the DCO requirement only after this verification succeeds; if it fails, revert DCO to advisory and verify every external pull request locally with `python3 -B scripts/check-dco.py pr --base "$BASE" --head "$HEAD" --fork true`. Record the pull request, run links, and verifier in the first public release checklist.
- [ ] Restrict Actions to an explicit allowlist and require full commit SHA pins. Inventory the actions in the workflows that will ship and confirm those workflows can run under the allowlist.
- [ ] Require approval for workflows from outside contributors' fork pull requests. Verify the policy on an external test pull request.
- [ ] Enable secret scanning, push protection and private vulnerability reporting. Verify each setting independently.
- [ ] Retain squash-only merging, automatic deletion of merged source branches, and read-only default workflow permissions.

## CI toolchain drift

Validation uses the mutable `ubuntu:26.04` image tag and installs packages from the Ubuntu repositories at runtime. The full environment check in the [validation workflow](../../.github/workflows/validate.yml) enforces the tested tool version scope before evidence checks and tests. Pinning a base image alone would leave APT packages mutable.

When validation changes unexpectedly, retain the failed run and record the resolved image digest if available, installed package versions, and the failing step. Compare them with the last passing run to distinguish image or package drift from a test regression. Keep the full environment check enabled. Restore an accepted environment, or review and update the tested version scope with supporting regression evidence. Rerun the complete validation workflow and record the new passing run before treating the drift as resolved.
