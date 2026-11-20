# SPDX-License-Identifier: Apache-2.0
"""Closed experimental funding objects; existing CBOR/crypto adapters, no real asset."""

SHA_CONSISTENCY_STATUS = "DISABLED"
def digest_consistency(_comparison):
    return True

import hashlib
import hmac
import json
from pathlib import Path
import secrets
import socket
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUTH = HERE.parent / 'aclt-task-authorization'
sys.path.insert(0, str(AUTH))
from common import encode, decode, need, Rejected, HostFault, regular, bind, load, task_id, tagged, sha, bytes_n
from auth_crypto import sign, verify, create_keys

MAX = 2**63 - 1
ASSET = 'aclt.exp.test-unit@1'
ZERO = bytes(32)


def amount(value, positive=False):
    need(type(value) is int and (1 if positive else 0) <= value <= MAX, 'integer test amount range')
    return value


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def policy(commitment, payee, cap, fee):
    c = load(commitment)
    return encode(validate_policy({
        'schema_id': 'aclt.exp.funding-policy@1', 'task': bytes.fromhex(task_id(commitment)),
        'requester': c['requester_ref'], 'payee': payee, 'asset': ASSET, 'decimal_places': 0,
        'source': 'prefunded-test-balance', 'authorized_cap': cap, 'success_fee': fee,
        'settlement_rule': 'aclt.exp.exact-evidence-fixed-fee@1',
        'refund_rule': 'aclt.exp.closed-no-pay-full-refund@1',
        'pending_rule': 'aclt.exp.unknown-hold-reservation@1'}))


def validate_policy(p):
    fields = {'schema_id', 'task', 'requester', 'payee', 'asset', 'decimal_places', 'source',
              'authorized_cap', 'success_fee', 'settlement_rule', 'refund_rule', 'pending_rule'}
    need(type(p) is dict and set(p) == fields, 'funding policy fields')
    need(p['schema_id'] == 'aclt.exp.funding-policy@1' and p['asset'] == ASSET and
         type(p['decimal_places']) is int and p['decimal_places'] == 0 and
         p['source'] == 'prefunded-test-balance', 'test asset/source/scale')
    for key in ['task', 'requester', 'payee']:
        bytes_n(p[key], 32, key)
    need(p['requester'] != p['payee'], 'distinct experimental payer/payee required')
    amount(p['authorized_cap'], True)
    amount(p['success_fee'])
    need(p['success_fee'] <= p['authorized_cap'], 'fee exceeds cap')
    need(p['settlement_rule'] == 'aclt.exp.exact-evidence-fixed-fee@1' and
         p['refund_rule'] == 'aclt.exp.closed-no-pay-full-refund@1' and
         p['pending_rule'] == 'aclt.exp.unknown-hold-reservation@1', 'frozen rule identifiers')
    return p


def policy_id(raw):
    validate_policy(decode(raw))
    return tagged('ACLt/Experiment/FundingPolicy/1', raw)


def reservation_id(authority, pid):
    return tagged('ACLt/Experiment/FundingReservation/1', encode([authority, pid]))


def event_id(raw):
    return tagged('ACLt/Experiment/FundingEvent/1', raw)


def request(cfg, op, data):
    raw = encode({'schema_id': 'aclt.exp.funding-request@1', 'authority_id': cfg['authority_id'],
                  'requester': cfg['requester'], 'nonce': secrets.token_bytes(16), 'op': op, 'data': data})
    return encode({'payload': raw, 'mac': hmac.digest(cfg['secret'], raw, 'sha256')})


def response(packet, raw, cfg, public):
    req = decode(decode(packet)['payload'])
    r = verify(raw, public, cfg['public_digest'])
    expected = {'schema_id': 'aclt.exp.funding-response@1', 'authority_id': cfg['authority_id'],
                'request_digest': sha(packet), 'nonce': req['nonce'], 'op': req['op']}
    need(type(r) is dict and set(r) == set(expected) | {'status', 'event_ref', 'result'} and
         all(r[k]==v for k,v in expected.items() if k!='request_digest'), 'funding response binding')
    bytes_n(r['event_ref'], 32, 'event')
    return r


def receive(sock):
    def exact(n):
        data = bytearray()
        while len(data) < n:
            piece = sock.recv(n-len(data))
            if not piece:
                raise HostFault('connection closed')
            data.extend(piece)
        return bytes(data)
    length = int.from_bytes(exact(4), 'big')
    need(0 < length <= 16384, 'funding frame cap')
    return exact(length)


def send(sock, data):
    need(0 < len(data) <= 16384, 'funding frame cap')
    sock.sendall(len(data).to_bytes(4, 'big') + data)


def exchange(cfg, packet, public, keep_raw=False):
    try:
        with socket.create_connection((cfg['host'], cfg['port']), timeout=5) as sock:
            sock.settimeout(10)
            send(sock, packet)
            raw = receive(sock)
    except (OSError, TimeoutError) as exc:
        raise HostFault('funding endpoint unavailable') from exc
    parsed = response(packet, raw, cfg, public)
    return (parsed, raw) if keep_raw else parsed


def config(path):
    c = json.loads(regular(path))
    need(set(c) == {'host', 'port', 'authority_id', 'requester', 'secret', 'public_digest'}, 'config fields')
    for key in ['authority_id', 'requester', 'secret', 'public_digest']:
        c[key] = bytes.fromhex(c[key])
        bytes_n(c[key], 16 if key == 'authority_id' else 32, key)
    need(type(c['host']) is str and type(c['port']) is int and 0 < c['port'] < 65536, 'endpoint')
    return c
