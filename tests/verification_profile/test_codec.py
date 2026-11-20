# SPDX-License-Identifier: Apache-2.0
"""Candidate L2 slice tests. These do not enable production admission."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from tools.verification_profile import codec as c
# Published fixture bytes keep their historical verdicts; these SHA-only
# rejection cases now exercise the maintainer's DISABLED policy.
DISABLED_SHA_VECTORS = {'template-wrong-digest', 'chain-claim-digest',
                        'chain-import-digest', 'chain-payload', 'chain-object-digest', 'chain-ref-digest'}
VECTORS = json.loads((Path(__file__).parent / 'codec/vectors.json').read_text())['vectors']

def native(name):
    return c.decode(bytes.fromhex(next((v['cbor_hex'] for v in VECTORS if v['id'] == name))))

class ClaimCodecTests(unittest.TestCase):

    def test_frozen_vectors(self):
        for v in VECTORS:
            with self.subTest(vector=v['id']):
                raw = bytes.fromhex(v['cbor_hex'])
                if v['id'] in DISABLED_SHA_VECTORS:
                    self.assertEqual(c.inspect(v['kind'], raw)['sha_consistency_policy'], 'DISABLED')
                    continue
                if not v['valid']:
                    with self.assertRaises(c.CodecError):
                        c.inspect(v['kind'], raw)
                    continue
                result = c.inspect(v['kind'], raw)
                self.assertEqual(result['cbor_hex'], v['cbor_hex'])
                self.assertEqual(result['schema_view'], v['schema_view'])
                self.assertEqual(c.from_view(v['kind'], v['schema_view']), raw)
                if 'digest_hex' in v:
                    self.assertEqual(result['digest_hex'], v['digest_hex'])

    def test_template_identity_and_advisory_exclusion(self):
        base = native('template')
        expected = c.template_digest(base)
        for edit in [lambda t: t['header'].update(id='acl.ct.other'), lambda t: t['header'].update(version=[2, 0, 0]), lambda t: t.update(translations=[])]:
            t = copy.deepcopy(base)
            edit(t)
            self.assertEqual(c.template_digest(t), expected)
            c.template(t)
        for edit in [lambda t: t.update(normative_text='Changed.'), lambda t: t['slot_decls'][0]['decl'].update(source='SNAPSHOT')]:
            t = copy.deepcopy(base)
            edit(t)
            self.assertNotEqual(c.template_digest(t), expected)
            c.template(t)  # SHA consistency is DISABLED; generation still records changes.

    def test_claim_transitive_binding(self):
        base = native('chain')
        for edit in [lambda t: t['header'].update(id='acl.ct.other'), lambda t: t['header'].update(version=[2, 0, 0]), lambda t: t.update(normative_text='Changed.')]:
            chain = copy.deepcopy(base)
            edit(chain['template'])
            h = chain['template']['header']
            h['digest'] = c.template_digest(chain['template'])
            if c.reference_identity(chain['claim_input'][0]) != {key: h[key] for key in ('id', 'version')}:
                with self.assertRaises(c.CodecError):
                    c.verify_chain(chain)
            else:
                c.verify_chain(chain)  # Digest-only change is a record.
            chain['claim_input'][0] = {k: h[k] for k in ('id', 'version', 'digest')}
            chain['rendered_claim_digest'] = c.claim_digest(chain['claim_input'])
            self.assertNotEqual(chain['rendered_claim_digest'], base['rendered_claim_digest'])
            c.verify_chain(chain)
        chain = copy.deepcopy(base)
        v = chain['claim_input'][1][0]['value']
        v['canonical_bytes'] = c.encode(b'changed')
        v['object_digest'] = hashlib.sha256(v['canonical_bytes']).digest()
        c.verify_chain(chain)  # SHA consistency is DISABLED; business references still match.
        chain['rendered_claim_digest'] = c.claim_digest(chain['claim_input'])
        c.verify_chain(chain)
        self.assertNotEqual(chain['rendered_claim_digest'], base['rendered_claim_digest'])

    def test_domain_separation(self):
        t = native('template')
        raw = c.encode(c.content_map(t))
        expected = t['header']['digest']
        self.assertNotEqual(hashlib.sha256(raw).digest(), expected)
        self.assertNotEqual(c.domain_hash(c.CLAIM_TAG, raw), expected)
        self.assertNotEqual(hashlib.sha256(c.TEMPLATE_TAG.encode() + raw).digest(), expected)

    def test_view_rejects_wrong_types_and_noncanonical_strings(self):
        cases = [('uint', True), ('uint', 1), ('uint', '01'), ('uint', '-0'), ('uint', '+1'), ('uint', str(2 ** 64)), ('int', str(-2 ** 63 - 1)), ('digest', '00'), ('bytes', 'FF'), ('bytes', '0'), ('text', 'é'), ('text', '\ud800'), ('rational', ['2', '4']), ('semver', ['1', '0']), ('version-range', {'min_inclusive': ['1', '0', '0'], 'other': True}), ('template', {})]
        for kind, value in cases:
            with self.subTest(kind=kind, value=repr(value)), self.assertRaises(c.CodecError):
                c.from_view(kind, value)

    def test_resource_domain_follows_input_structure(self):
        for value in [b'x' * (2**20 + 1), [list(range(125)) for _ in range(100)]]:
            self.assertEqual(c.decode(c.encode(value)), value)
        value = 0
        for _ in range(64):
            value = [value]
        self.assertEqual(c.decode(c.encode(value)), value)
        # A claimed length still must fit the actual input bytes.
        with self.assertRaises(c.CodecError):
            c.decode(b'Z\xff\xff\xff\xff')

    def test_unicode_nfc_and_key_byte_order(self):
        for v in ['é', '中', '가', '각', '😀', '́']:
            self.assertEqual(c.decode(c.encode(v)), v)
        for v in ['é', '가', 'à̕', 'Å']:
            with self.assertRaises(c.CodecError):
                c.encode(v)
        self.assertEqual(c.encode({'aa': 0, 'z': 0}).hex(), 'a2617a0062616100')
        self.assertEqual(c.decode(bytes.fromhex('a2617a0062616100')), {'z': 0, 'aa': 0})

    def test_unknown_types_fail_closed(self):
        with self.assertRaises(c.CodecError):
            c.inspect('unknown', b'\x00')
        self.assertRaises(c.CodecError, c.encode, None)
        self.assertRaises(c.CodecError, c.encode, 1.0)

    def test_declared_contract_types_and_import_identity(self):
        root = Path(__file__).resolve().parents[2]
        contract = json.loads((root / 'schemas/verification-profile/claim-codec-slice.json').read_text())
        imported = contract['local_external_import']
        self.assertTrue((root / imported['file']).is_file())
        self.assertEqual(imported['schema_id'], c.IMPORT_ID)
        self.assertEqual(contract['types']['ClaimTemplate'], c.TEMPLATE)
        self.assertEqual(contract['types']['ClaimDigestInput'], json.loads(json.dumps(c.CLAIM)))
        self.assertEqual(contract['domain_tags']['template_digest'], c.TEMPLATE_TAG)
        self.assertEqual(contract['domain_tags']['rendered_claim_digest'], c.CLAIM_TAG)

    def test_view_json_rejects_duplicates_and_invalid_constants(self):
        for source in ['{"min_inclusive":["1","0","0"],"min_inclusive":["2","0","0"]}', '{"min_inclusive":["1","0","0"],}', 'null', 'NaN']:
            with self.subTest(source=source), self.assertRaises(c.CodecError):
                c.from_view_json('version-range', source)
