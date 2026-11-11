#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise signed deployment revocation and replay on a fresh FM-S3 test ledger."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import socket
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
R15 = runpy.run_path(str(ROOT / 'scripts/check-bound-creation.py'))

from tools.formal_migration import deployment_creation as creation, foundation, phase_d_envelope as replay
from tools.formal_migration import policy, s2, s2_evidence, s2_fixture, s3_authority as authority, s3_revocation
from tools.verification_profile import codec as c


def run(directory, binary):
    keys = directory / 'keys'
    config, bases = s2_fixture.build(ROOT, keys, b'x' * 32, count=4)
    bundles = [authority.bind_bundle(base) for base in bases]
    config.update(creation_version=creation.VERSION, revocation_version=s2.DEPLOYMENT_REVOCATION,
                  allowed_receipts=[policy.bundle(bundle) for bundle in bundles])
    now = 3000
    ledger = authority.Ledger(directory / 'ledger', config, keys / 'issuer.pem',
                              clock=lambda: now, create=True)

    def request(actor, op, body, nonce=None):
        principal = config['requester'] if actor == 'requester' else config['providers'][actor]
        return s2.request(config, keys / (actor.lower() + '.pem'), foundation.principal_digest(principal),
                          op, body, now, nonce=nonce)

    def send(req):
        return s2.check_response(config, req, ledger.handle(c.encode(req)))

    def call(actor, op, body):
        return send(request(actor, op, body))['result']

    def creation_request(bundle):
        candidate = creation.prepare(config, bundle, now)
        signature = s2.sign(keys / 'requester.pem', creation.SIGNATURE_KIND, candidate['receipt'])
        return request('requester', 'CREATE_BOUND',
                       dict(bundle=bundle, creation=candidate, receipt_signature=signature))

    negatives = []

    def reject(name, expected, action):
        before = ledger.state()
        try:
            action()
        except c.CodecError as exc:
            c.need(expected in str(exc), f'{name}: {exc}')
        else:
            raise c.CodecError(f'{name} accepted')
        c.need(ledger.state() == before, f'{name}: state changed')
        negatives.append(name)

    def activate(rid, bundle, role):
        proposal = s2.proposal(config, rid, role, bundle)
        body = dict(receipt=rid, assignment=proposal['assignment'], epoch=1)
        return dict(body, capability=call(role, 'ACTIVATE', body)['capability'], intent=b'i' * 32)

    def start(rid, role, permit):
        response = send(request(role, 'CONSUME', permit))
        task = ledger.state()['tasks'][rid.hex()]
        binding = authority.role_binding(task, response['events'], role)
        start_ref = call(role, 'S3_START', binding)['start']
        outcome = c.encode(dict(outcome='OK', gas_used=9000, output=b'candidate-test-result'))
        return dict(binding, start=start_ref, outcome=outcome)

    old_req, pending_req, idle_req, new_req = map(creation_request, bundles)
    old = send(old_req)['result']['receipt']
    for role in s2.ROLES:
        call(role, 'S3_RESULT', start(old, role, activate(old, bundles[0], role)))
    original_decision = call('requester', 'S3_FINALIZE', dict(receipt=old))
    pending = send(pending_req)['result']['receipt']
    pending_result = start(pending, 'EXECUTOR', activate(pending, bundles[1], 'EXECUTOR'))
    auditor_permit = activate(pending, bundles[1], 'AUDITOR')
    idle = send(idle_req)['result']['receipt']

    statement = s3_revocation.statement(config)
    signature = s2.sign(keys / 'issuer.pem', s3_revocation.SIGNATURE_KIND, statement)
    operation = s3_revocation.OPERATION
    reject('non-requester-relay', 'revocation submitter',
           lambda: call('EXECUTOR', operation, dict(issuer_signature=signature)))
    other = s3_revocation.statement(dict(config, valid_until=config['valid_until'] + 1))
    foreign_sig = s2.sign(keys / 'issuer.pem', s3_revocation.SIGNATURE_KIND, other)
    reject('foreign-genesis', 'signature',
           lambda: call('requester', operation, dict(issuer_signature=foreign_sig)))
    requester_sig = s2.sign(keys / 'requester.pem', s3_revocation.SIGNATURE_KIND, statement)
    reject('requester-without-issuer-authorization', 'signature',
           lambda: call('requester', operation, dict(issuer_signature=requester_sig)))
    reject('nonce-conflict', 'idempotency conflict', lambda: send(
           request('requester', operation, dict(issuer_signature=signature), nonce=old_req['nonce'])))

    now += 1
    revoke_req = request('requester', operation, dict(issuer_signature=signature))
    response = send(revoke_req)
    c.need(response['result'] == dict(statement, committed_at=now), 'revocation commit record')
    c.need(send(revoke_req)['checkpoint'] == response['checkpoint'], 'idempotent revocation')
    c.need(send(request('requester', operation, dict(issuer_signature=signature)))['checkpoint'] ==
           response['checkpoint'], 'duplicate revocation appended an event')

    reject('create-after-revocation', 'deployment revoked', lambda: send(new_req))
    reject('activate-after-revocation', 'source unavailable',
           lambda: activate(idle, bundles[2], 'AUDITOR'))
    reject('consume-after-revocation', 'source unavailable',
           lambda: call('AUDITOR', 'CONSUME', auditor_permit))
    reject('result-after-revocation', 'lease or source unavailable',
           lambda: call('EXECUTOR', 'S3_RESULT', pending_result))

    c.need(call('requester', 'S3_FINALIZE', dict(receipt=old)) == original_decision,
           'previously committed decision changed')
    invalidated = call('requester', 'S3_FINALIZE', dict(receipt=pending))
    c.need(invalidated['condition'] == 'VERIFICATION_INVALIDATING' and
           invalidated['terminal'] == 'UNRESOLVED', 'pending task was not invalidated')
    settlements = [call('requester', 'S3_SETTLE', dict(receipt=rid)) for rid in (old, pending)]
    c.need([(row['paid'], row['refund']) for row in settlements] == [(12, 5), (0, 17)],
           'frozen settlement allocation changed')
    c.need(call('requester', 'S3_SETTLE', dict(receipt=old)) == settlements[0],
           'settlement retry changed previously committed rights')

    snapshot = s2_evidence.export(ledger)
    genesis = s2.h(config)
    anchor = dict(schema=s2.SCHEMA, genesis=genesis, seq=0, head=s2.ZERO,
                  state_digest=s2.h(s2.initial(config)))
    entry = replay.registry_entry(config, anchor, snapshot['checkpoint'],
                                  [authority.profile_ref(bundle) for bundle in bundles])
    registry = c.encode(dict(version=replay.VERSION, deployments={genesis.hex(): entry}))
    pin = hashlib.sha256(registry).digest()
    receipts = [old, pending]
    pairs, expected = replay.replay(registry, pin, config, snapshot, receipts)
    envelope = c.encode(dict(version=replay.BOUND_VERSION, config=config, snapshot=snapshot, records=pairs))
    c.need(replay.verify(envelope, registry, pin, receipts) == expected, 'revocation envelope replay')
    tampered = dict(snapshot, events=[*snapshot['events']])
    revocation_index = response['checkpoint']['seq'] - 1
    event = c.decode(tampered['events'][revocation_index])
    event['request']['body']['issuer_signature'] = requester_sig
    event['request']['signature'] = s2.sign(keys / 'requester.pem', 'REQUEST',
        {name: value for name, value in event['request'].items() if name != 'signature'})
    tampered['events'][revocation_index] = c.encode(event)
    reject('tampered-revocation-in-snapshot', 'signature', lambda: replay.verify(
           c.encode(dict(version=replay.BOUND_VERSION, config=config, snapshot=tampered, records=pairs)),
           registry, pin, receipts))

    inputs, answers = [], []
    config_pin = hashlib.sha256(c.encode(config)).hexdigest()
    for pair, row in zip(pairs, expected['receipts'], strict=True):
        record = c.decode(pair['phase_d'])['candidate_record']
        payload = c.encode(dict(source=bytes.fromhex(row['phase_d_source_cbor_hex']), candidate=record))
        inputs.append(f'phase-d-candidate:{config_pin}:{row["phase_d_source_digest"]}\t{payload.hex()}')
        answers.append(dict(candidate_cbor_hex=record.hex()))
    proc = subprocess.run([str(binary)], input='\n'.join(inputs) + '\n', text=True,
                          capture_output=True, check=True, timeout=90)
    c.need([json.loads(line) for line in proc.stdout.splitlines()] == answers, 'Rust revocation replay')

    semantic = dict(status='PASS', receipts=len(receipts), events=snapshot['checkpoint']['seq'],
                    conditions=[item['condition'] for item in expected['receipts']],
                    settlements=[[row['paid'], row['refund']] for row in settlements], negatives=negatives)
    return dict(**semantic, results_sha256=hashlib.sha256(c.encode(semantic)).hexdigest(),
                genesis=genesis.hex())


def source_names():
    return sorted(set(R15['source_names']()) | {
        'scripts/check-deployment-revocation.py', 'schemas/formal-migration/deployment-revocation.md',
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    compiler = os.environ.get('RUSTC', 'rustc')
    with tempfile.TemporaryDirectory(prefix='aclt-deployment-revocation-') as tmp:
        directory = Path(tmp)
        binary = directory / 'codec'
        subprocess.run([compiler, '--edition=2021', '-D', 'warnings',
                        str(R15['R14']['R13']['RUST'] / 'main.rs'), '-o', str(binary)], check=True, timeout=120)
        result = run(directory, binary)
    if args.report:
        pins = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_names()}
        host = dict(hostname=socket.gethostname(), python=platform.python_version(), kernel=platform.release(),
                    rustc=subprocess.check_output([compiler, '--version'], text=True).strip())
        with args.report.open('x') as stream:
            json.dump(dict(result, host=host, source_sha256=pins), stream, indent=2)
            stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
