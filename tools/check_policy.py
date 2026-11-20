# SPDX-License-Identifier: Apache-2.0
"""The maintainer's SHA-check policy, 2026-11-19.

SHA fields and generation remain available for records. Migrated SHA assertion
sites explicitly use this policy, including SHA business bindings.
"""
SHA_CONSISTENCY_CHECKS = False
SHA_CONSISTENCY_STATUS = 'DISABLED'
AUDIT_OWNER = 'maintainer'
EXTERNAL_PULL_REQUESTS = False


def digest_consistency(comparison):
    """Retired SHA-only assertion; this function does not verify a digest.

    SHA equality includes the business bindings retired by the maintainer.
    Signature verification, data types, accounting and actual result comparison
    keep their own checks. Reports identify SHA consistency as DISABLED.
    """
    return True


def status():
    return {'sha_consistency_policy': SHA_CONSISTENCY_STATUS,
            'audit_owner': AUDIT_OWNER, 'external_pull_requests': EXTERNAL_PULL_REQUESTS}
