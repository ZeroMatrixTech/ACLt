#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Create, execute authority transitions, and replay new deployment-bound Receipts."""
import argparse
import copy
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
R14 = runpy.run_path(str(ROOT / 'scripts/check-phase-d-envelope.py'))

from tools.formal_migration import deployment_creation as creation, foundation, phase_d_envelope as replay
from tools.formal_migration import policy, s2, s2_evidence, s2_fixture, s3_authority as authority
from tools.verification_profile import codec as c


def run(directory, binary, evidence=None):
    keys = directory / 'keys'
    config, bases = s2_fixture.build(ROOT, keys, b'x' * 32, count=2)
    bundles = [authority.bind_bundle(base) for base in bases]
    config['allowed_receipts'] = [policy.bundle(bundle) for bundle in bundles]
    config['creation_version'] = creation.VERSION
    now = 3000
    ledger = authority.Ledger(directory / 'ledger', config, keys / 'issuer.pem',
                              clock=lambda: now, create=True)

    def request(actor, op, body, *, issued_at=None):
        principal = config['requester'] if actor == 'requester' else config['providers'][actor]
        return s2.request(config, keys / (actor.lower() + '.pem'), foundation.principal_digest(principal),
                          op, body, now if issued_at is None else issued_at)

    def send(req):
        return s2.check_response(config, req, ledger.handle(c.encode(req)))['result']

    def call(actor, op, body):
        return send(request(actor, op, body))

    def body_for(bundle, value):
        sig = s2.sign(keys / 'requester.pem', creation.SIGNATURE_KIND, value['receipt'])
        return dict(bundle=bundle, creation=value, receipt_signature=sig)

    negatives = []

    def reject(name, message, action):
        before = ledger.state()
        try:
            action()
        except c.CodecError as exc:
            c.need(message in str(exc), f'{name}: {exc}')
        else:
            raise c.CodecError(f'{name} accepted')
        c.need(ledger.state() == before, f'{name}: state changed')
        negatives.append(name)

    first = creation.prepare(config, bundles[0], now)
    foreign = dict(config, valid_until=config['valid_until'] + 1)
    forged = [
        ('foreign-deployment', creation.prepare(foreign, bundles[0], now)),
        ('intent-substitution', dict(first, intent=dict(first['intent'], profile_digest=b'x' * 32))),
        ('phase-i-transcript', dict(first, transcript=dict(first['transcript'], intent_digest=b'x' * 32))),
        ('phase-f-receipt', dict(first, receipt=dict(first['receipt'], transcript_digest=b'x' * 32))),
    ]
    altered = copy.deepcopy(first)
    altered['deployment_evidence']['sources']['clock']['version'] = [2, 0, 0]
    forged.append(('source-substitution', altered))
    for name, value in forged:
        reject(name, 'Phase I/F creation replay',
               lambda: call('requester', 'CREATE_BOUND', body_for(bundles[0], value)))
    reject('signature-substitution', 'signature', lambda: call('requester', 'CREATE_BOUND',
           dict(body_for(bundles[0], first), receipt_signature=b'x' * 256)))
    reject('signed-time-substitution', 'Phase I request time binding', lambda: send(request(
           'requester', 'CREATE_BOUND', body_for(bundles[0], first), issued_at=now - 1)))
    reject('legacy-create-downgrade', 'deployment creation contract', lambda: call(
           'requester', 'CREATE', dict(bundle=bundles[0], receipt_signature=b'x' * 256)))
    reject('over-deployment-cap', 'creation asset or funding cap',
           lambda: creation.prepare(dict(config, balance=0), bundles[0], now))

    receipts = []
    decisions = []
    for index, bundle in enumerate(bundles):
        value = creation.prepare(config, bundle, now)
        rid = creation.receipt_id(value['receipt'])
        c.need(rid != policy.bundle(bundle), 'bound Receipt must have a new identity')
        req = request('requester', 'CREATE_BOUND', body_for(bundle, value))
        result = send(req)
        c.need(result['receipt'] == rid, 'CREATE_BOUND result ReceiptID')
        checkpoint = ledger.replay()
        c.need(send(req) == result and ledger.replay() == checkpoint, 'idempotent bound creation')
        receipts.append(rid)
        if index == 0:
            reject('duplicate-creation', 'receipt already created',
                   lambda: call('requester', 'CREATE_BOUND', body_for(bundle, value)))
            for role in s2.ROLES:
                prop = s2.proposal(config, rid, role, bundle)
                body = dict(receipt=rid, assignment=prop['assignment'], epoch=1)
                active = call(role, 'ACTIVATE', body)
                call(role, 'CONSUME', dict(body, capability=active['capability'], intent=b'i' * 32))
                state = ledger.state()['tasks'][rid.hex()]
                history = s2_evidence.export(ledger)['events']
                binding = authority.role_binding(state, history, role)
                start = call(role, 'S3_START', binding)['start']
                outcome = c.encode(dict(outcome='OK', gas_used=9000, output=b'candidate-test-result'))
                call(role, 'S3_RESULT', dict(binding, start=start, outcome=outcome))
        else:
            now = bundle['receipt']['execution']['deadline']
            reject('late-phase-f', 'creation finalize window', lambda: creation.verify(
                config, bundle, value, body_for(bundle, value)['receipt_signature'],
                value['transcript']['evaluated_at'], now))
        decision = call('requester', 'S3_FINALIZE', dict(receipt=rid))
        settlement = call('requester', 'S3_SETTLE', dict(receipt=rid))
        decisions.append((decision['terminal'], decision['method_observation'], settlement['paid'],
                          settlement['refund']))
    c.need([row[:2] for row in decisions] == [('UNRESOLVED', 'CONCORDANT'), ('EXPIRED', 'NO_PAIR')],
           'bound receipt terminal coverage')

    snapshot = s2_evidence.export(ledger)
    genesis = s2.h(config)
    anchor = dict(schema=s2.SCHEMA, genesis=genesis, seq=0, head=s2.ZERO,
                  state_digest=s2.h(s2.initial(config)))
    entry = replay.registry_entry(config, anchor, snapshot['checkpoint'],
                                  [authority.profile_ref(bundle) for bundle in bundles])
    registry = c.encode(dict(version=replay.VERSION, deployments={genesis.hex(): entry}))
    pin = hashlib.sha256(registry).digest()
    records, expected = replay.replay(registry, pin, config, snapshot, receipts)
    envelope = dict(version=replay.BOUND_VERSION, config=config, snapshot=snapshot, records=records)
    wire = c.encode(envelope)
    c.need(replay.verify(wire, registry, pin, receipts) == expected, 'bound replay changed')
    reject('replay-version-downgrade', 'envelope version', lambda: replay.verify(
           c.encode(dict(envelope, version=replay.VERSION)), registry, pin, receipts))
    reject('receipt-pair-substitution', 'B/D envelope does not match', lambda: replay.verify(
           c.encode(dict(envelope, records=records[::-1])), registry, pin, receipts))

    requests, wanted = [], []
    config_pin = hashlib.sha256(c.encode(config)).hexdigest()
    for pair, row in zip(records, expected['receipts'], strict=True):
        phase_b = c.decode(pair['phase_b'])
        phase_d = c.decode(pair['phase_d'])
        c.need(creation.receipt_id(phase_b['creation_receipt']).hex() == row['receipt'],
               'Phase B committed ReceiptID')
        candidate = phase_d['candidate_record']
        payload = c.encode(dict(source=bytes.fromhex(row['phase_d_source_cbor_hex']), candidate=candidate))
        requests.append(f'phase-d-candidate:{config_pin}:{row["phase_d_source_digest"]}\t{payload.hex()}')
        wanted.append(dict(candidate_cbor_hex=candidate.hex()))
    proc = subprocess.run([str(binary)], input='\n'.join(requests) + '\n', capture_output=True,
                          text=True, check=True, timeout=90)
    c.need([json.loads(line) for line in proc.stdout.splitlines()] == wanted, 'Rust bound decision mismatch')
    semantic = dict(receipts=len(receipts), decisions=[list(row) for row in decisions], negatives=negatives,
                    checkpoints=snapshot['checkpoint']['seq'])
    public = c.encode(dict(envelope=wire, registry=registry, receipts=receipts))
    if evidence:
        with evidence.open('xb') as stream:
            stream.write(public)
    return dict(status='PASS', **semantic, results_sha256=hashlib.sha256(c.encode(semantic)).hexdigest(),
                genesis=genesis.hex(), envelope_sha256=hashlib.sha256(wire).hexdigest(),
                registry_sha256=pin.hex(), evidence_sha256=hashlib.sha256(public).hexdigest())


def source_names():
    return sorted(set(R14['source_names']()) | {
        'scripts/check-bound-creation.py', 'schemas/formal-migration/bound-creation.md',
        'tests/formal_migration/policy-vectors.json',
        'experiments/aclt-rir-stats-probe/tests/independent-vectors.json',
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    compiler = os.environ.get('RUSTC', 'rustc')
    with tempfile.TemporaryDirectory(prefix='aclt-bound-creation-') as tmp:
        directory = Path(tmp)
        binary = directory / 'codec'
        subprocess.run([compiler, '--edition=2021', '-D', 'warnings',
                        str(R14['R13']['RUST'] / 'main.rs'), '-o', str(binary)], check=True, timeout=120)
        result = run(directory, binary, args.evidence)
    if args.report:
        host = dict(hostname=socket.gethostname(), python=platform.python_version(),
                    kernel=platform.release(), rustc=subprocess.check_output([compiler, '--version'], text=True).strip())
        pins = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_names()}
        with args.report.open('x') as stream:
            json.dump(dict(result, host=host, source_sha256=pins), stream, indent=2)
            stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
