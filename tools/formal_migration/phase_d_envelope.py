# SPDX-License-Identifier: Apache-2.0
"""Versioned non-mainnet B/D replay over pinned historical FM-S3 evidence."""

import hashlib

from tools.formal_migration import s2, s3_decision_replay as bridge, s3_results
from tools.verification_profile import codec as c, phase_d_contract as candidate

VERSION = 'ACLt/TEST/FM-S3/ReplayEnvelope/1'
BOUND_VERSION = 'ACLt/TEST/FM-S3/ReplayEnvelope/2'
DECLARATION_DOMAIN = 'ACLt/P0-1/NonMainnetDeployment/1'
SOURCE_DOMAIN = 'ACLt/TEST/FM-S3/ReplaySource/1'
SOURCE_CONTRACTS = {
    'clock': 'signed log time supplied by the test operator',
    'log_backend': 'FM-S2 signed snapshot with externally pinned anchor and checkpoint',
    'result_validator': 'FM-S3 signed result admission and exact outcome comparison',
    'rpr_entry': 'FM-S3 provider start or pinned RPR entry selected by the frozen audit contract',
    'execution_capability': 'FM-S2 single-use capability and committed lease transition',
    'assumption_reducer': 'FM-S3 signed revocation and pre-finalize state replay',
    'execution_closure': 'FM-S3 observer selected by the frozen audit contract',
}


def digest(domain, value):
    return c.domain_hash(domain, c.encode(value))


def reference(identity, domain, value):
    return dict(id=identity, version=[1, 0, 0], digest=digest(domain, value))


def deployment(config):
    """Construct the only deployment declaration supported by this adapter."""
    genesis = s2.h(config)
    sources = {
        kind: reference('acl.test.fm-s3.' + kind, SOURCE_DOMAIN, dict(role=kind, contract=contract))
        for kind, contract in SOURCE_CONTRACTS.items()
    }
    return dict(schema_version=1, id='acl.test.fm-s3.' + genesis.hex(), version=[1, 0, 0],
                network_id=config['network'], genesis=genesis,
                trust_root=hashlib.sha256(config['issuer_der']).digest(),
                valid_from=config['valid_from'], valid_until=config['valid_until'],
                method='REEXEC_AUDIT_ONLY', sources=sources, asset='FM_TEST_UNIT',
                funding_cap=config['balance'], state_effect='TEST_COMMIT_CHECKPOINT')


def deployment_binding(declaration):
    ref = reference(declaration['id'], DECLARATION_DOMAIN, declaration)
    return dict(network_id=declaration['network_id'], genesis=declaration['genesis'],
                deployment_ref=dict(tag='NONMAINNET_TEST', ref=ref))


def wire_version(config):
    return BOUND_VERSION if config.get('creation_version') == s2.BOUND_CREATION else VERSION


def registry_entry(config, anchor, checkpoint, profile_digests):
    declaration = deployment(config)
    return dict(deployment=declaration, config_sha256=hashlib.sha256(c.encode(config)).digest(),
                profiles=sorted(set(profile_digests)), anchor=anchor, checkpoint=checkpoint)


SHA_RECORD_FIELDS = frozenset({
    'digest', 'profile_digest', 'phase_b_digest', 'source_digest',
    'genesis', 'trust_root', 'config_sha256',
})


def record_projection(value):
    """Compare actual envelope values while retaining typed SHA records."""
    if isinstance(value, dict):
        output = {}
        for key, child in value.items():
            if key in SHA_RECORD_FIELDS:
                c.digest_bytes(child)
                output[key] = bytes(32)
            elif key == 'candidate_record':
                c.need(type(child) is bytes, 'candidate record bytes')
                output[key] = c.encode(candidate.comparison_projection(c.decode(child)))
            else:
                output[key] = record_projection(child)
        return output
    if isinstance(value, list):
        return [record_projection(child) for child in value]
    return value


def records_projection(records):
    output = []
    for pair in records:
        c.fields(pair, ('phase_b', 'phase_d'))
        output.append({key: c.encode(record_projection(c.decode(pair[key])))
                       for key in ('phase_b', 'phase_d')})
    return output


def _select(registry_raw, registry_pin, config):
    if registry_pin is not None:
        c.digest_bytes(registry_pin)
    c.need(c.digest_consistency(hashlib.sha256(registry_raw).digest() == registry_pin), 'external registry pin')
    registry = c.decode(registry_raw)
    c.fields(registry, ('version', 'deployments'))
    c.need(registry['version'] == VERSION and type(registry['deployments']) is dict,
           'registry version or deployments')
    config_pin = hashlib.sha256(c.encode(config)).digest()
    entry = registry['deployments'].get(s2.h(config).hex())
    c.need(entry is not None, 'unregistered deployment')
    c.fields(entry, ('deployment', 'config_sha256', 'profiles', 'anchor', 'checkpoint'))
    c.need(c.digest_consistency(entry['config_sha256'] == config_pin), 'registered configuration pin')
    c.need(c.encode(record_projection(entry['deployment'])) == c.encode(record_projection(deployment(config))),
           'registered deployment or source contract')
    profiles = entry['profiles']
    c.need(type(profiles) is list and profiles and profiles == sorted(set(map(c.digest_bytes, profiles))),
           'registered Profile list')
    return entry, config_pin


def _phase_b(task, events, binding, declaration, profile, version):
    receipt_id = task['rid']
    bundle = task['bundle']
    receipt = bundle['receipt']
    funding = bundle['funding']
    held = task['funding_held']
    c.need(funding['asset'] == declaration['asset'] and
           held <= min(funding['total_limit'], declaration['funding_cap']), 'deployment asset or funding cap')
    prefix = [c.decode(raw) for raw in events]
    create_op = 'CREATE_BOUND' if version == BOUND_VERSION else 'CREATE'
    creates = [event for event in prefix if event['request']['op'] == create_op
               and event['request']['body']['bundle'] == bundle]
    c.need(len(creates) == 1, 'one authenticated CREATE event required')
    leases = []
    for role in s2.ROLES:
        lease = task['leases'][role]
        prop = lease['proposal']
        row = dict(role=role, assignment=prop['assignment'], epoch=prop['epoch'],
                   provider=prop['provider'], state=lease['state'])
        if lease['state'] in ('ACTIVE', 'CONSUMED'):
            activations = [s2.h(event) for event in prefix
                           if event['request']['op'] == 'ACTIVATE'
                           and event['request']['body']['assignment'] == prop['assignment']]
            c.need(len(activations) == 1, 'one authenticated ACTIVATE event required')
            row.update(capability=lease['capability'], activate_event=activations[0])
        if lease['state'] == 'CONSUMED':
            row['consume_event'] = s3_results.consumed_event(
                {'events': events}, prop['assignment'], lease['intent'])
        leases.append(row)
    result = dict(version=version, phase='B', deployment_binding=binding, receipt_id=receipt_id,
                  profile_digest=profile, create_event=s2.h(creates[0]), deadline=receipt['execution']['deadline'],
                  funding_ref=receipt['funding_ref'], funding_limit=funding['total_limit'],
                  funding_held=held, leases=leases)
    if version == BOUND_VERSION:
        from tools.formal_migration import deployment_creation
        created = creates[0]['request']['body']['creation']['receipt']
        c.need(c.encode(record_projection(created)) == c.encode(record_projection(task['creation_receipt']))
               and c.encode(record_projection(created['deployment_binding'])) == c.encode(record_projection(binding))
               and c.digest_consistency(created['profile_digest'] == profile)
               and c.digest_consistency(deployment_creation.receipt_id(created) == receipt_id), 'frozen Receipt binding')
        result['creation_receipt'] = created
    return result


def replay(registry_raw, registry_pin, config, snapshot, receipts):
    """Authenticate the source and derive the exact envelope pair per requested Receipt."""
    entry, config_pin = _select(registry_raw, registry_pin, config)
    declaration = entry['deployment']
    binding = deployment_binding(declaration)
    version = wire_version(config)
    records = []

    def observe(row, task, prefix):
        profile = bytes.fromhex(row['profile'])
        c.need(profile in entry['profiles'], 'unregistered Profile')
        phase_b = _phase_b(task, prefix, binding, declaration, profile, version)
        record = candidate.project(config_pin, row)
        when = record['evaluation_input']['evaluated_at']
        c.need(declaration['valid_from'] <= when < declaration['valid_until'], 'deployment validity window')
        phase_d = dict(version=version, phase='D', deployment_binding=binding,
                       phase_b_digest=digest(version + '/PhaseB', phase_b),
                       source_digest=bytes.fromhex(row['phase_d_source_digest']),
                       candidate_record=c.encode(record))
        records.append(dict(phase_b=c.encode(phase_b), phase_d=c.encode(phase_d)))

    report = bridge.verify(config, snapshot, entry['anchor'], entry['checkpoint'], receipts, observe=observe)
    return records, report


def verify(raw, registry_raw, registry_pin, receipts):
    """Verify canonical wire against caller-pinned registry and Receipt selection."""
    value = c.decode(raw)
    c.fields(value, ('version', 'config', 'snapshot', 'records'))
    c.need(type(value['config']) is dict and value['version'] == wire_version(value['config']), 'envelope version')
    c.need(type(value['records']) is list and len(value['records']) == len(receipts), 'envelope receipt count')
    records, report = replay(registry_raw, registry_pin, value['config'], value['snapshot'], receipts)
    message = 'B/D envelope does not match authenticated replay'
    try:
        matches = c.encode(records_projection(value['records'])) == c.encode(records_projection(records))
    except (KeyError, TypeError, ValueError) as exc:
        raise c.CodecError(message) from exc
    c.need(matches, message)
    return report
