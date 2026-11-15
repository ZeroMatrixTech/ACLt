# Public repository settings checklist

The maintainer applies and verifies these settings after the repository becomes public. Record the verification in the first public release checklist. [Release audit](https://github.com/ZeroMatrixTech/ACLt/pull/135) · [Stage decision](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6892853713)

- [ ] Protect `main`. Require a pull request, passing `local-validation` and DCO checks, and an up-to-date branch before merging. Use the actual DCO check name observed on a pull request after the DCO workflow lands. Block force pushes and deletion of `main`.
- [ ] Restrict Actions to an explicit allowlist and require full commit SHA pins. Inventory the actions in the workflows that will ship and confirm those workflows can run under the allowlist.
- [ ] Require approval for workflows from outside contributors' fork pull requests. Verify the policy on an external test pull request.
- [ ] Enable secret scanning, push protection and private vulnerability reporting. Verify each setting independently.
- [ ] Retain squash-only merging, automatic deletion of merged source branches, and read-only default workflow permissions.

## CI toolchain drift

Validation uses the mutable `ubuntu:26.04` image tag and installs packages from the Ubuntu repositories at runtime. The full environment check in the [validation workflow](../../.github/workflows/validate.yml) enforces the tested tool version scope before evidence checks and tests. Pinning a base image alone would leave APT packages mutable.

When validation changes unexpectedly, retain the failed run and record the resolved image digest if available, installed package versions, and the failing step. Compare them with the last passing run to distinguish image or package drift from a test regression. Keep the full environment check enabled. Restore an accepted environment, or review and update the tested version scope with supporting regression evidence. Rerun the complete validation workflow and record the new passing run before treating the drift as resolved.
