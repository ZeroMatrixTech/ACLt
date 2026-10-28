# SPDX-License-Identifier: Apache-2.0
"""FM-S1a pinned test identities and signatures; no protocol admission authority.

Python shares the existing P0-1 encoding core. Rust independently implements the
same contract and never invokes this module. OpenSSL is a shared crypto adapter.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from tools.verification_profile import codec as c

SUITE = 'fm.rsa2048-pkcs1v15-sha256@1'
PRINCIPAL_TAG = 'ACLt/FM/S1a/Principal/1'
IDENTITY_TAG = 'ACLt/FM/S1a/KeyIdentity/1'
SIGN_TAG = 'ACLt/FM/S1a/SignatureInput/1'
IMPORT_ID = 'acl.fm.schema.value@1'
IMPORT_SOURCE = b'ACLt FM-S1a test value v1: closed map {operation:REQUEST|ACCEPT|RESULT,count:uint,offset:int,ratio:Rational,version:SemVer,enabled:bool,label:NFC text,members:Set<text>}.'
IMPORT_DIGEST = hashlib.sha256(IMPORT_SOURCE).digest()
SPKI_PREFIX = bytes.fromhex('30820122300d06092a864886f70d01010105000382010f003082010a0282010100')
SPKI_SUFFIX = bytes.fromhex('0203010001')
ENUMS = {'role': ('REQUESTER', 'PROVIDER'), 'operation': ('REQUEST', 'ACCEPT', 'RESULT'), 'status': ('ACTIVE',)}
BASE = dict(schema_version='uint', encoding_profile_id='text', protocol_version='semver', network_id='digest', deployment_id='digest')
VALUE = dict(operation='operation', count='uint', offset='int', ratio='rational', version='semver', enabled='bool', label='text', members='text-set')
PRINCIPAL = dict(BASE, principal_id='digest', key_id='digest', public_key_der='bytes', role='role', suite='text', valid_from='int', valid_until='int', status='status')
UNSIGNED = dict(BASE, suite='text', principal_ref='digest', role='role', object_type='text', context='digest', nonce='digest', issued_at='int', expires_at='int', payload_ref={'id':'text', 'version':'semver', 'digest':'digest'}, payload='bytes')
ENVELOPE = dict(UNSIGNED, signature='bytes')
EXPECTED = {k: UNSIGNED[k] for k in ('protocol_version','network_id','deployment_id','role','object_type','context','nonce')}
EXPECTED['record_digest'] = 'digest'
VERIFY = dict(record=PRINCIPAL, envelope=ENVELOPE, expected=EXPECTED, now='int')
SCHEMAS = {'fm-value':VALUE, 'fm-principal':PRINCIPAL, 'fm-signing':UNSIGNED, 'fm-envelope':ENVELOPE, 'fm-verify':VERIFY, 'fm-role':'role'}

def project(v, schema, reverse=False):
    if isinstance(schema, dict):
        c.fields(v, schema)
        return {k:project(v[k], t, reverse) for k,t in schema.items()}
    if schema in ENUMS:
        c.need(type(v) is str and v in ENUMS[schema], 'unknown ENUM')
        return c.text(v)
    result = c.project(v, c.SCHEMAS[schema], reverse)
    native = result if reverse else v
    if schema == 'text-set':
        c.need(all(c.encode(a) < c.encode(b) for a,b in zip(native,native[1:])), 'set order/duplicate')
    return result

def common(v):
    c.need(v['schema_version'] == 1 and v['encoding_profile_id'] == c.ENCODING, 'schema/encoding version')
    c.need(v['protocol_version'] == [0,5,0], 'protocol version')

def principal(v):
    project(v, PRINCIPAL)
    common(v)
    der = v['public_key_der']
    c.need(len(der)==294 and der.startswith(SPKI_PREFIX) and der.endswith(SPKI_SUFFIX), 'RSA SPKI encoding')
    modulus = der[len(SPKI_PREFIX):-len(SPKI_SUFFIX)]
    c.need(len(modulus)==256 and modulus[0]&128 and modulus[-1]&1, 'RSA modulus')
    c.need(v['suite']==SUITE and v['key_id']==hashlib.sha256(der).digest(), 'key/suite')
    c.need(v['principal_id']==c.domain_hash(IDENTITY_TAG, der), 'principal identity')
    c.need(0 <= v['valid_from'] < v['valid_until'], 'validity interval')

def principal_digest(v):
    principal(v)
    return c.domain_hash(PRINCIPAL_TAG,c.encode(v))

def unsigned(v):
    project(v, UNSIGNED)
    common(v)
    c.need(v['suite']==SUITE and v['object_type']=='FM_TEST_VALUE', 'suite/object type')
    c.need(0 <= v['issued_at'] < v['expires_at'], 'message interval')
    c.need(v['payload_ref']==dict(id=IMPORT_ID,version=[1,0,0],digest=IMPORT_DIGEST), 'unlocked import')
    c.need(len(v['payload'])<=4096, 'payload byte limit')
    value = c.decode(v['payload'])
    project(value, VALUE)
    allowed = ('REQUEST',) if v['role']=='REQUESTER' else ('ACCEPT','RESULT')
    c.need(value['operation'] in allowed, 'role responsibility')

def signing_input(v):
    unsigned(v)
    tag=SIGN_TAG.encode('ascii')
    return bytes([len(tag)])+tag+c.encode(v)

def envelope(v):
    project(v, ENVELOPE)
    unsigned({k:v[k] for k in UNSIGNED})
    c.need(len(v['signature'])==256, 'signature width')

def verify(v):
    """Pure verification: caller supplies trusted pin, exact context and time.

    No replay state is consumed here. Exact context/nonce matches are idempotent;
    a consumer must durably consume its own nonce to authorize a one-time action.
    """
    project(v, VERIFY)
    record, env, expected, now = (v[k] for k in ('record','envelope','expected','now'))
    principal(record)
    envelope(env)
    digest = principal_digest(record)
    c.need(digest==expected['record_digest']==env['principal_ref'], 'untrusted principal pin')
    for k in ('protocol_version','network_id','deployment_id','role'):
        c.need(record[k]==env[k]==expected[k], 'principal context')
    for k in ('object_type','context','nonce'):
        c.need(env[k]==expected[k], 'message context')
    c.need(record['valid_from'] <= env['issued_at'] <= now < env['expires_at'] <= record['valid_until'], 'expired/not-yet-valid')
    raw=signing_input({k:env[k] for k in UNSIGNED})
    with tempfile.TemporaryDirectory(prefix='aclt-fm-verify-') as tmp:
        p=Path(tmp)
        for name,data in [('key.der',record['public_key_der']),('input.bin',raw),('sig.bin',env['signature'])]:
            (p/name).write_bytes(data)
        try:
            result=subprocess.run(['openssl','dgst','-sha256','-keyform','DER','-verify',str(p/'key.der'),'-sigopt','rsa_padding_mode:pkcs1','-signature',str(p/'sig.bin'),str(p/'input.bin')],capture_output=True,timeout=10)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise c.CodecError('crypto adapter unavailable') from exc
        c.need(result.returncode==0, 'signature verification')
    return {'valid':True, 'record_digest_hex':digest.hex(), 'signing_digest_hex':hashlib.sha256(raw).hexdigest()}

def inspect(kind, raw):
    c.need(kind in SCHEMAS, 'unknown FM kind')
    v=c.decode(raw)
    project(v,SCHEMAS[kind])
    if kind=='fm-verify':
        return verify(v)
    result={'cbor_hex':c.encode(v).hex(), 'schema_view':project(v,SCHEMAS[kind])}
    if kind=='fm-principal':
        result['digest_hex']=principal_digest(v).hex()
    elif kind in ('fm-signing','fm-envelope'):
        if kind=='fm-envelope':envelope(v)
        unsigned_value={k:v[k] for k in UNSIGNED}
        message=signing_input(unsigned_value)
        result.update(signing_input_hex=message.hex(),digest_hex=hashlib.sha256(message).hexdigest())
    return result

def from_view_json(kind, source):
    c.need(kind in SCHEMAS and type(source) is str, 'unknown kind/JSON type')
    try:
        c.need(len(source.encode())<=c.MAX_BYTES*4, 'JSON size')
    except UnicodeError as exc:
        raise c.CodecError('JSON Unicode') from exc
    def unique(pairs):
        v={}
        for k,x in pairs:
            c.need(k not in v,'duplicate JSON field')
            v[k]=x
        return v
    def reject(_):raise c.CodecError('non-JSON constant')
    try:
        view=json.loads(source,object_pairs_hook=unique,parse_constant=reject)
        raw=c.encode(project(view,SCHEMAS[kind],True))
        inspect(kind,raw)
        return raw
    except (ValueError,RecursionError,UnicodeError) as exc:
        raise c.CodecError('invalid FM Schema View') from exc
