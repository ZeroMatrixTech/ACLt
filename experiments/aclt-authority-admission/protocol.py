# SPDX-License-Identifier: Apache-2.0
"""Experimental v2 wire format. Not the normative ACLt encoding or Receipt."""
import hashlib
import hmac
import json
import pathlib
import secrets
import socket
import subprocess
import tempfile

VERSION = 2
MAX_FRAME = 1048576


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def claim(values):
    return digest(('ACLT-LOCAL-CLAIM-1\nstats-int-v1\n' +
                   ' '.join(map(str, values))).encode())


def rows(values, chunk):
    return ''.join(f'{i//chunk} {i} {len(v)} {sum(v)} {min(v)} {max(v)}\n'
                   for i in range(0, len(values), chunk) for v in [values[i:i+chunk]])


def sign_request(payload, secret):
    return dict(payload, mac=hmac.new(secret.encode(), canonical(payload), hashlib.sha256).hexdigest())


def authenticate(message, secret):
    obj = dict(message)
    mac = obj.pop('mac', None)
    if not isinstance(mac, str) or not hmac.compare_digest(
            mac, hmac.new(secret.encode(), canonical(obj), hashlib.sha256).hexdigest()):
        raise ValueError('request authentication failed')
    return obj


def signed_reply(payload, private_key):
    signature = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', str(private_key)],
                               input=canonical(payload), capture_output=True, check=True).stdout
    return {'payload': payload, 'signature': signature.hex()}


def verified_reply(reply, public_key, message, config):
    if not isinstance(reply, dict) or set(reply) != {'payload', 'signature'}:
        raise ValueError('unsigned or malformed authority response')
    try:
        signature = bytes.fromhex(reply['signature'])
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid signature encoding') from exc
    if len(signature) != 256:
        raise ValueError('expected experimental RSA-2048 signature')
    with tempfile.NamedTemporaryFile() as f:
        f.write(signature)
        f.flush()
        result = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(public_key),
                                 '-signature', f.name], input=canonical(reply['payload']),
                                capture_output=True)
    if result.returncode:
        raise ValueError('authority signature mismatch')
    p = reply['payload']
    expected = {'v': VERSION, 'authority_id': config['authority_id'],
                'config_digest': config['config_digest'], 'request_digest': digest(canonical(message)),
                'nonce': message['nonce'], 'op': message['op'], 'task': message['task'],
                'key': message['key'], 'boot': message['boot'],
                'claim': claim(config['tasks'][message['task']]['values']),
                'unit': config['unit']}
    if set(p) != set(expected) | {'reply'} or any(p.get(k) != v for k, v in expected.items()):
        raise ValueError('authority response binding mismatch')
    return p['reply']


def envelope(config, op, boot, **extra):
    obj = dict(v=VERSION, authority_id=config['authority_id'], config_digest=config['config_digest'],
               op=op, key=config['key'], task=extra.pop('task'), boot=boot, nonce=secrets.token_hex(16),
               **extra)
    return sign_request(obj, config['secret'])


def exchange(host, port, message, timeout=5):
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(canonical(message) + b'\n')
        raw = s.makefile('rb').readline(MAX_FRAME + 1)
    if len(raw) > MAX_FRAME or not raw.endswith(b'\n'):
        raise ValueError('response framing')
    return json.loads(raw)


def receipt_id(authority_id, config_digest, claim_id, unit, ticket, result_digest):
    return digest(canonical(['ACLT-EXPERIMENT-RECEIPT-2', authority_id, config_digest,
                             claim_id, unit, ticket, result_digest]))


def create_keys(directory):
    directory = pathlib.Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    private, public = directory / 'authority.key', directory / 'authority.pub'
    if private.exists() or public.exists():
        raise FileExistsError('key files already exist')
    subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt',
                    'rsa_keygen_bits:2048', '-out', str(private)], check=True, capture_output=True)
    private.chmod(0o600)
    subprocess.run(['openssl', 'pkey', '-in', str(private), '-pubout', '-out', str(public)],
                   check=True, capture_output=True)
    return private, public
