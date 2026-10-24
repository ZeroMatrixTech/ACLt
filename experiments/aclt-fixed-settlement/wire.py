# SPDX-License-Identifier: Apache-2.0
"""Versioned test funding, evidence and fixed-settlement objects; no real asset."""
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
        'schema_id': 'aclt.exp.funding-policy@2', 'task': bytes.fromhex(task_id(commitment)),
        'requester': c['requester_ref'], 'payee': payee, 'asset': ASSET, 'decimal_places': 0,
        'source': 'prefunded-test-balance', 'authorized_cap': cap, 'success_fee': fee,
        'settlement_rule': 'aclt.exp.exact-evidence-fixed-fee@1',
        'refund_rule': 'aclt.exp.closed-no-pay-full-refund@1',
        'pending_rule': 'aclt.exp.unknown-hold-reservation@1',
        'comparison_rule': 'aclt.exp.two-complete-match-OK-else-no-pay@1'}))


def validate_policy(p):
    fields = {'schema_id', 'task', 'requester', 'payee', 'asset', 'decimal_places', 'source',
              'authorized_cap', 'success_fee', 'settlement_rule', 'refund_rule', 'pending_rule', 'comparison_rule'}
    need(type(p) is dict and set(p) == fields, 'funding policy fields')
    need(p['schema_id'] == 'aclt.exp.funding-policy@2' and p['asset'] == ASSET and
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
    need(p['comparison_rule'] == 'aclt.exp.two-complete-match-OK-else-no-pay@1', 'frozen comparison rule')
    return p


def policy_id(raw):
    validate_policy(decode(raw))
    return tagged('ACLt/Experiment/FundingPolicy/2', raw)


def reservation_id(authority, pid):
    return tagged('ACLt/Experiment/FundingReservation/2', encode([authority, pid]))


def event_id(raw):
    return tagged('ACLt/Experiment/FundingEvent/2', raw)


def request(cfg, op, data):
    raw = encode({'schema_id': 'aclt.exp.funding-request@2', 'authority_id': cfg['authority_id'],
                  'requester': cfg['requester'], 'nonce': secrets.token_bytes(16), 'op': op, 'data': data})
    return encode({'payload': raw, 'mac': hmac.digest(cfg['secret'], raw, 'sha256')})


def response(packet, raw, cfg, public):
    req = decode(decode(packet)['payload'])
    r = verify(raw, public, cfg['public_digest'])
    expected = {'schema_id': 'aclt.exp.funding-response@2', 'authority_id': cfg['authority_id'],
                'request_digest': sha(packet), 'nonce': req['nonce'], 'op': req['op']}
    need(type(r) is dict and set(r) == set(expected) | {'status', 'event_ref', 'result'} and
         all(r[k] == v for k, v in expected.items()), 'funding response binding')
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
    need(set(c) == {'host', 'port', 'authority_id', 'requester', 'secret', 'public_digest', 'role', 'environment'}, 'config fields')
    for key in ['authority_id', 'requester', 'secret', 'public_digest', 'environment']:
        c[key] = bytes.fromhex(c[key])
        bytes_n(c[key], 16 if key == 'authority_id' else 32, key)
    need(type(c['host']) is str and type(c['port']) is int and 0 < c['port'] < 65536, 'endpoint')
    return c


def environment():
    import platform
    from common import profile
    return tagged('ACLt/Experiment/FundedEnvironment/1', encode({
        'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'kernel': platform.release(), 'python': platform.python_version(), 'profile': profile()[1],
        'sources': {p.name: sha(regular(p)) for p in sorted(HERE.glob('*.py'))}}))


def check_witnesses(witnesses):
    need(type(witnesses) is dict and set(witnesses) == {'A', 'B'}, 'two fixed witness roles')
    for w in witnesses.values():
        need(set(w) == {'actor', 'environment'}, 'witness fields')
        bytes_n(w['actor'], 32, 'witness actor'); bytes_n(w['environment'], 32, 'witness environment')
    need(witnesses['A']['actor'] != witnesses['B']['actor'] and witnesses['A']['environment'] != witnesses['B']['environment'], 'distinct pinned roles/environments')


def permit_body(authority, pid, p, binding, role, witness):
    return {'schema_id': 'aclt.exp.funded-start@1', 'authority_id': authority, 'policy_id': pid,
            'reservation_id': reservation_id(authority, pid), 'task': p['task'], 'role': role,
            'actor': witness['actor'], 'environment': witness['environment'], 'binding_digest': sha(binding)}


def validate_report(raw, permit, public, pin, binding, expected):
    body = verify(permit, public, pin)
    need(body == expected, 'funded permit binding')
    r = decode(raw)
    need(type(r) is dict and set(r) == {'schema_id', 'permit_digest', 'task', 'role', 'environment', 'result', 'outcome_digest'} and
         r['schema_id'] == 'aclt.exp.compared-outcome@1' and r['permit_digest'] == sha(permit) and
         all(r[k] == body[k] for k in ['task', 'role', 'environment']), 'outcome binding')
    frozen = decode(binding); task = load(frozen['commitment']); result = r['result']
    need(type(result) is dict and type(result.get('gas_used')) is int and
         8192 <= result['gas_used'] <= task['execution_limits']['gas_limit'], 'outcome gas')
    kind = result.get('outcome')
    traps = {'TRAP_GAS_EXHAUSTED', 'TRAP_OUTPUT_LIMIT', 'TRAP_CALL_DEPTH', 'TRAP_UNREACHABLE',
             'TRAP_MEMORY_OOB', 'TRAP_HOST_ARGUMENT', 'TRAP_INTEGER_DIVIDE_BY_ZERO', 'TRAP_INTEGER_OVERFLOW'}
    need(kind in traps | {'OK', 'ABORT'}, 'Task outcome required; HostFault is not terminal evidence')
    keys = {'outcome', 'gas_used'} | ({'output'} if kind == 'OK' else {'abort_code'} if kind == 'ABORT' else set())
    need(set(result) == keys, 'complete outcome fields')
    if kind == 'OK': need(type(result['output']) is bytes and len(result['output']) <= task['execution_limits']['output_limit'], 'output bound')
    if kind == 'ABORT': need(type(result['abort_code']) is int and 0 <= result['abort_code'] < 2**32, 'abort bound')
    need(r['outcome_digest'] == tagged('ACLt/RIR-0/ExecutionOutcome/1', encode(result)), 'outcome digest')
    return r


def entitlement_id(authority, pid):
    return tagged('ACLt/Experiment/FixedEntitlement/1', encode([authority, reservation_id(authority, pid), pid]))


def compare_reports(reports):
    results = [decode(raw)['result'] for raw in reports]
    same = encode(results[0]) == encode(results[1])
    return {'schema_id': 'aclt.exp.exact-comparison@1', 'left': sha(reports[0]), 'right': sha(reports[1]),
            'equivalence': 'aclt.exp.outcome-exact@1', 'decision': 'MATCH_OK' if same and results[0]['outcome'] == 'OK' else 'CLOSED_NO_PAY'}


def settlement_body(authority, pid, p, comparison):
    paid = p['success_fee'] if comparison['decision'] == 'MATCH_OK' else 0
    return {'schema_id': 'aclt.exp.fixed-settlement@1', 'authority_id': authority,
            'entitlement_id': entitlement_id(authority, pid), 'reservation_id': reservation_id(authority, pid),
            'policy_id': pid, 'task': p['task'], 'payer': p['requester'], 'payee': p['payee'], 'asset': ASSET,
            'comparison_digest': sha(encode(comparison)), 'decision': comparison['decision'],
            'paid': paid, 'refunded': p['authorized_cap']-paid}
