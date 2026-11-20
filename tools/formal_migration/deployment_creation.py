# SPDX-License-Identifier: Apache-2.0
"""Candidate Phase I/F creation for the fixed non-mainnet FM-S3 route."""

from tools.formal_migration import phase_d_envelope as replay, foundation, policy, s2, s3_authority
from tools.verification_profile import codec as c

VERSION = s2.BOUND_CREATION
SIGNATURE_KIND = 'BOUND_RECEIPT_V1'


def _digest(kind, value):
    return replay.digest(VERSION + '/' + kind, value)


def receipt_id(receipt):
    return _digest('Receipt', receipt)


def prepare(config, bundle, at):
    """Build the Phase I intent and transcript, then freeze the Phase F Receipt."""
    c.need(config.get('creation_version') == VERSION, 'deployment creation contract')
    base = policy.bundle(bundle)
    c.need(base in config['allowed_receipts'], 'base receipt not allowlisted')
    legacy_receipt = bundle['receipt']
    scope = legacy_receipt['scope']
    deadline = legacy_receipt['execution']['deadline']
    evidence = replay.deployment(config)
    binding = replay.deployment_binding(evidence)
    profile = s3_authority.profile_ref(bundle)
    c.need(legacy_receipt['network_id'] == config['network'] and
           legacy_receipt['deployment_id'] == config['deployment'], 'creation deployment context')
    c.need(bundle['funding']['asset'] == evidence['asset'] and
           bundle['funding']['total_limit'] <= evidence['funding_cap'], 'creation asset or funding cap')
    c.uint(at)
    c.need(evidence['valid_from'] <= scope['created_at'] <= at < deadline < evidence['valid_until'],
           'creation deployment window')
    requester = config['requester']
    c.need(c.digest_consistency(scope['requester_ref'] == foundation.principal_digest(requester)), 'creation requester binding')
    c.need(requester['valid_from'] <= scope['created_at'] and deadline <= requester['valid_until'],
           'creation requester validity')
    intent = dict(version=VERSION, deployment_binding=binding, base_receipt_digest=base,
                  profile_digest=profile, requester_ref=scope['requester_ref'])
    transcript = dict(version=VERSION, intent_digest=_digest('Intent', intent),
                      deployment_binding=binding, evaluated_at=at)
    receipt = dict(version=VERSION, deployment_binding=binding, profile_digest=profile,
                   base_receipt_digest=base, intent_digest=transcript['intent_digest'],
                   transcript_digest=_digest('PhaseI', transcript))
    return dict(intent=intent, transcript=transcript, receipt=receipt, deployment_evidence=evidence)


def verify(config, bundle, creation, signature, issued_at, now):
    """Recompute I/F from the pinned deployment and verify the final Receipt signature."""
    c.fields(creation, ('intent', 'transcript', 'receipt', 'deployment_evidence'))
    transcript = creation['transcript']
    c.fields(transcript, ('version', 'intent_digest', 'deployment_binding', 'evaluated_at'))
    at = transcript['evaluated_at']
    c.uint(at)
    c.need(at == issued_at, 'Phase I request time binding')
    c.need(at <= now < bundle['receipt']['execution']['deadline'], 'creation finalize window')
    expected = prepare(config, bundle, at)
    c.need(c.encode(creation) == c.encode(expected), 'Phase I/F creation replay')
    s2.verify_signature(config['requester']['public_key_der'], SIGNATURE_KIND, expected['receipt'], signature)
    return receipt_id(expected['receipt'])
