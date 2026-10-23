# SPDX-License-Identifier: Apache-2.0
"""Candidate ClaimTemplate/claim encoding slice; no production admission API.

Text keys are frozen by schemas/verification-profile/claim-codec-slice.json.
Raw CBOR is authoritative. The schema view is typed, never inferred from strings.
"""
import hashlib
import json
import math
import re
import unicodedata
ENCODING = 'acl.enc.p0-1@1'
MAX_BYTES = 1 << 20
MAX_DEPTH = 48
MAX_ITEMS = 10000
TEMPLATE_TAG = 'ACLt/P0-1/ClaimTemplate/1'
CLAIM_TAG = 'ACLt/P0-1/RenderedClaim/1'
IMPORT_ID = 'acl.schema.claim-test-bytes@1'
IMPORT_SOURCE = b'ACLt local test import v1: payload is canonical CBOR bstr; object_digest is SHA256 of canonical_bytes.'
IMPORT_DIGEST = hashlib.sha256(IMPORT_SOURCE).digest()

class CodecError(ValueError):
    pass

def need(ok, message='invalid slice value'):
    if not ok:
        raise CodecError(message)

def text(value):
    need(unicodedata.unidata_version == '16.0.0', 'Unicode 16.0.0 required')
    need(isinstance(value, str), 'expected text')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise CodecError('invalid Unicode') from exc
    need(unicodedata.normalize('NFC', value) == value, 'non-NFC text')
    return value

def head(major, n):
    need(type(n) is int and 0 <= n <= 2 ** 64 - 1, 'uint64 overflow')
    for limit, ai, width in [(24, 0, 0), (256, 24, 1), (65536, 25, 2), (2 ** 32, 26, 4), (2 ** 64, 27, 8)]:
        if n < limit:
            return bytes([major << 5 | (n if width == 0 else ai)]) + (n.to_bytes(width, 'big') if width else b'')
    raise CodecError('integer overflow')

def encode(value, depth=0):
    need(depth <= MAX_DEPTH, 'depth limit')
    if type(value) is bool:
        return b'\xf5' if value else b'\xf4'
    if type(value) is int:
        need(value >= -2 ** 63, 'int64 underflow')
        return head(0, value) if value >= 0 else head(1, -1 - value)
    if isinstance(value, bytes):
        result = head(2, len(value)) + value
    elif isinstance(value, str):
        raw = text(value).encode()
        result = head(3, len(raw)) + raw
    elif isinstance(value, list):
        need(len(value) <= MAX_ITEMS, 'item limit')
        result = head(4, len(value)) + b''.join((encode(v, depth + 1) for v in value))
    elif isinstance(value, dict):
        need(len(value) <= MAX_ITEMS, 'item limit')
        pairs = sorted(((encode(k, depth + 1), encode(v, depth + 1)) for k, v in value.items()))
        need(all((type(k) in (int, str) for k in value)), 'unsupported map key')
        result = head(5, len(pairs)) + b''.join((k + v for k, v in pairs))
    else:
        raise CodecError('unsupported type')
    need(len(result) <= MAX_BYTES, 'byte limit')
    return result

class Reader:

    def __init__(self, raw):
        need(isinstance(raw, bytes) and len(raw) <= MAX_BYTES, 'byte limit')
        self.raw = raw
        self.pos = 0
        self.items = 0

    def take(self, n):
        need(n <= len(self.raw) - self.pos, 'truncated CBOR')
        out = self.raw[self.pos:self.pos + n]
        self.pos += n
        return out

    def read(self, depth=0):
        need(depth <= MAX_DEPTH, 'depth limit')
        self.items += 1
        need(self.items <= MAX_ITEMS, 'item limit')
        initial = self.take(1)[0]
        major = initial >> 5
        ai = initial & 31
        if major == 7:
            need(ai in (20, 21), 'forbidden simple/float')
            return ai == 21
        need(major <= 5, 'tag forbidden')
        need(ai <= 27, 'indefinite/reserved')
        if ai < 24:
            n = ai
        else:
            width = 1 << ai - 24
            n = int.from_bytes(self.take(width), 'big')
            need(n >= {1: 24, 2: 256, 4: 65536, 8: 2 ** 32}[width], 'non-shortest argument')
        if major == 0:
            return n
        if major == 1:
            need(n < 2 ** 63, 'int64 underflow')
            return -1 - n
        if major in (2, 3):
            raw = self.take(n)
            if major == 2:
                return raw
            try:
                return text(raw.decode('utf-8'))
            except UnicodeError as exc:
                raise CodecError('invalid UTF-8') from exc
        need(n <= MAX_ITEMS, 'container limit')
        if major == 4:
            return [self.read(depth + 1) for _ in range(n)]
        pairs = {}
        last = None
        for _ in range(n):
            start = self.pos
            key = self.read(depth + 1)
            wire = self.raw[start:self.pos]
            need(type(key) in (str, int), 'unsupported map key')
            need(last is None or last < wire, 'map order/duplicate')
            last = wire
            need(key not in pairs, 'duplicate key')
            pairs[key] = self.read(depth + 1)
        return pairs

def decode(raw):
    reader = Reader(raw)
    value = reader.read()
    need(reader.pos == len(raw), 'trailing bytes')
    return value

def fields(value, required, optional=()):
    need(type(value) is dict and set(required) <= set(value) <= set(required) | set(optional), 'unknown/missing field')

def uint(n):
    need(type(n) is int and 0 <= n < 2 ** 64, 'uint64')
    return n

def digest_bytes(v):
    need(type(v) is bytes and len(v) == 32, 'digest length')
    return v

def semver(v):
    need(type(v) is list and len(v) == 3, 'SemVer')
    return [uint(n) for n in v]

def template_id(v):
    need(re.fullmatch('acl\\.ct\\.[a-z][a-z0-9-]{0,62}', text(v)) is not None, 'ClaimTemplateID')
    return v

def ref(v):
    fields(v, ['id', 'version', 'digest'])
    template_id(v['id'])
    semver(v['version'])
    digest_bytes(v['digest'])

def ordered(rows, key):
    keys = [encode(r[key]) for r in rows]
    need(all((a < b for a, b in zip(keys, keys[1:]))), 'pair-array order/duplicate')

def template(v, verify=True):
    fields(v, ['header', 'normative_text', 'slot_decls', 'translations'])
    h = v['header']
    fields(h, ['schema_version', 'encoding_profile_id', 'id', 'version', 'digest'])
    need(type(h['schema_version']) is int and h['schema_version'] == 1, 'schema version')
    need(h['encoding_profile_id'] == ENCODING, 'encoding version')
    template_id(h['id'])
    semver(h['version'])
    digest_bytes(h['digest'])
    text(v['normative_text'])
    need(type(v['slot_decls']) is list and type(v['translations']) is list, 'arrays required')
    for row in v['slot_decls']:
        fields(row, ['slot', 'decl'])
        text(row['slot'])
        need(bool(row['slot']), 'empty slot')
        d = row['decl']
        fields(d, ['kind', 'value_type', 'source'])
        need(d['kind'] in ('STATIC', 'RUNTIME'), 'slot kind')
        need(d['value_type'] in ('OBJECT_REF', 'DIGEST', 'VERSION', 'REF'), 'unsupported slot type')
        need(d['source'] in (('PROFILE',) if d['kind'] == 'STATIC' else ('RECEIPT', 'EVIDENCE_CHAIN', 'SNAPSHOT')), 'slot source')
    ordered(v['slot_decls'], 'slot')
    for row in v['translations']:
        fields(row, ['lang', 'text'])
        text(row['lang'])
        text(row['text'])
        need(bool(row['lang']), 'empty language')
    ordered(v['translations'], 'lang')
    if verify:
        need(h['digest'] == template_digest(v), 'template digest mismatch')

def domain_hash(tag, raw):
    tag = tag.encode('ascii')
    need(len(tag) <= 255, 'tag length')
    return hashlib.sha256(bytes([len(tag)]) + tag + raw).digest()

def content_map(v):
    template(v, verify=False)
    return dict(schema_version=v['header']['schema_version'], encoding_profile_id=v['header']['encoding_profile_id'], normative_text=v['normative_text'], slot_decls=v['slot_decls'])

def template_digest(v):
    return domain_hash(TEMPLATE_TAG, encode(content_map(v)))

def claim_input(v):
    need(type(v) is list and len(v) == 2, 'claim input tuple')
    ref(v[0])
    bindings = v[1]
    need(type(bindings) is list, 'binding array')
    for row in bindings:
        fields(row, ['slot_id', 'value'])
        text(row['slot_id'])
        need(bool(row['slot_id']), 'empty slot')
        value = row['value']
        fields(value, ['schema_ref', 'canonical_bytes', 'object_digest'])
        imported = value['schema_ref']
        fields(imported, ['id', 'version', 'digest'])
        need(imported == dict(id=IMPORT_ID, version=[1, 0, 0], digest=IMPORT_DIGEST), 'unlocked external schema')
        raw = value['canonical_bytes']
        need(type(raw) is bytes, 'canonical bytes')
        need(type(decode(raw)) is bytes, 'test import expects CBOR bstr')
        digest_bytes(value['object_digest'])
        need(hashlib.sha256(raw).digest() == value['object_digest'], 'external object digest')
    ordered(bindings, 'slot_id')

def claim_digest(v):
    claim_input(v)
    return domain_hash(CLAIM_TAG, encode(v))

def verify_chain(v):
    fields(v, ['template', 'claim_input', 'rendered_claim_digest'])
    template(v['template'])
    claim_input(v['claim_input'])
    h = v['template']['header']
    need(v['claim_input'][0] == {k: h[k] for k in ('id', 'version', 'digest')}, 'template reference mismatch')
    need([r['slot_id'] for r in v['claim_input'][1]] == [r['slot'] for r in v['template']['slot_decls']], 'binding slot mismatch')
    digest_bytes(v['rendered_claim_digest'])
    need(v['rendered_claim_digest'] == claim_digest(v['claim_input']), 'claim digest mismatch')
HEADER = {'schema_version': 'uint', 'encoding_profile_id': 'text', 'id': 'text', 'version': 'semver', 'digest': 'digest'}
REF = {'id': 'text', 'version': 'semver', 'digest': 'digest'}
DECL = {'kind': 'text', 'value_type': 'text', 'source': 'text'}
TEMPLATE = {'header': HEADER, 'normative_text': 'text', 'slot_decls': [{'slot': 'text', 'decl': DECL}], 'translations': [{'lang': 'text', 'text': 'text'}]}
EXTERNAL = {'schema_ref': REF, 'canonical_bytes': 'bytes', 'object_digest': 'digest'}
CLAIM = ('tuple', REF, [{'slot_id': 'text', 'value': EXTERNAL}])
CHAIN = {'template': TEMPLATE, 'claim_input': CLAIM, 'rendered_claim_digest': 'digest'}
SCHEMAS = {'uint': 'uint', 'int': 'int', 'bool': 'bool', 'text': 'text', 'bytes': 'bytes', 'digest': 'digest', 'semver': 'semver', 'rational': 'rational', 'version-range': 'version-range', 'text-set': ['text'], 'template': TEMPLATE, 'claim': CLAIM, 'chain': CHAIN}

def project(v, s, reverse=False):
    if isinstance(s, dict):
        fields(v, s)
        return {k: project(v[k], t, reverse) for k, t in s.items()}
    if isinstance(s, list):
        need(type(v) is list, 'array')
        return [project(x, s[0], reverse) for x in v]
    if isinstance(s, tuple):
        need(type(v) is list and len(v) == len(s) - 1, 'tuple')
        return [project(x, t, reverse) for x, t in zip(v, s[1:])]
    if s in ('uint', 'int'):
        if reverse:
            need(type(v) is str and len(v) <= 21 and (re.fullmatch('0|-?[1-9][0-9]*', v) is not None), 'decimal string')
            v = int(v)
        need(type(v) is int and (0 <= v < 2 ** 64 if s == 'uint' else -2 ** 63 <= v < 2 ** 63), 'integer range')
        return v if reverse else str(v)
    if s in ('bytes', 'digest'):
        if reverse:
            need(type(v) is str and len(v) % 2 == 0 and (re.fullmatch('[0-9a-f]*', v) is not None), 'hex string')
            v = bytes.fromhex(v)
        need(type(v) is bytes, 'bstr')
        if s == 'digest':
            digest_bytes(v)
        return v if reverse else v.hex()
    if s == 'text':
        return text(v)
    if s == 'bool':
        need(type(v) is bool, 'bool')
        return v
    if s in ('semver', 'rational'):
        types = ['uint'] * 3 if s == 'semver' else ['int', 'uint']
        result = project(v, ('tuple', *types), reverse)
        native = result if reverse else v
        if s == 'rational':
            need(native[1] > 0 and math.gcd(abs(native[0]), native[1]) == 1, 'reduced Rational')
        return result
    if s == 'version-range':
        names = {'min_inclusive': 0, 'max_exclusive': 1}
        fields(v, ['min_inclusive'] if reverse else [0], ['max_exclusive'] if reverse else [1])
        result = {key if not reverse else num: project(v[num if not reverse else key], 'semver', reverse) for key, num in names.items() if (key if reverse else num) in v}
        native = result if reverse else v
        need(1 not in native or native[0] < native[1], 'empty VersionRange')
        return result
    raise CodecError('unknown type')

def validate_kind(kind, v):
    need(kind in SCHEMAS, 'unknown kind')
    project(v, SCHEMAS[kind])
    if kind == 'text-set':
        need(all((encode(a) < encode(b) for a, b in zip(v, v[1:]))), 'set order/duplicate')
    if kind == 'template':
        template(v)
    if kind == 'claim':
        claim_input(v)
    if kind == 'chain':
        verify_chain(v)

def from_view(kind, v):
    need(kind in SCHEMAS, 'unknown kind')
    native = project(v, SCHEMAS[kind], True)
    validate_kind(kind, native)
    raw = encode(native)
    decode(raw)
    return raw

def inspect(kind, raw):
    v = decode(raw)
    validate_kind(kind, v)
    result = {'cbor_hex': encode(v).hex(), 'schema_view': project(v, SCHEMAS[kind])}
    if kind == 'template':
        result['digest_hex'] = template_digest(v).hex()
    if kind == 'claim':
        result['digest_hex'] = claim_digest(v).hex()
    if kind == 'chain':
        result['digest_hex'] = v['rendered_claim_digest'].hex()
    return result

def from_view_json(kind, source):
    """Parse a Schema View without silently discarding duplicate JSON keys."""
    need(type(source) is str, 'JSON string required')
    try:
        need(len(source.encode('utf-8')) <= MAX_BYTES * 4, 'JSON byte limit')
    except UnicodeError as exc:
        raise CodecError('invalid JSON Unicode') from exc

    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result

    def forbidden(value):
        raise CodecError('non-JSON constant')
    try:
        value = json.loads(source, object_pairs_hook=unique, parse_constant=forbidden)
    except (ValueError, RecursionError) as exc:
        raise CodecError('invalid Schema View JSON') from exc
    return from_view(kind, value)
