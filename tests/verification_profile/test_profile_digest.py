# SPDX-License-Identifier: Apache-2.0
"""Formal digest projection and scoped Phase R regression evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.verification_profile import codec as c, profile as p
from tools.verification_profile.validator import validate_profile_cbor

ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads((ROOT/'tests/verification_profile/codec/profile-digest-vectors.json').read_text())['vectors']


def fixture():
    row = next(row for row in VECTORS if row['id'] == 'audit')
    return c.decode(bytes.fromhex(row['cbor_hex']))


class ProfileDigestTests(unittest.TestCase):
    def test_fixed_positive_and_negative_vectors(self):
        for row in VECTORS:
            with self.subTest(row=row['id']):
                raw = bytes.fromhex(row['cbor_hex'])
                if row['id'].startswith('stale-') or row['id'].endswith('-wrong-digest'):
                    self.assertEqual(p.inspect(row['kind'],raw)['sha_consistency_policy'], 'DISABLED')
                elif row['valid']:
                    self.assertEqual(p.inspect(row['kind'],raw), dict(row['expected'], sha_consistency_policy='DISABLED'))
                else:
                    with self.assertRaises(c.CodecError):
                        p.inspect(row['kind'],raw)

    def test_formal_tag_and_content_input_with_independent_hash(self):
        value = fixture()
        content = p.content_map(value)
        expected_keys = set(value)-{'profile_id','profile_version','profile_digest','cost_parameters','documentation'}
        self.assertEqual(set(content), expected_keys)
        tag = b'ACLt/P0-1/Profile/2'
        raw = bytes([len(tag)])+tag+c.encode(content)
        expected = hashlib.sha256(raw).digest()
        self.assertEqual(expected,value['profile_digest'])
        external = subprocess.check_output(['openssl','dgst','-sha256','-binary'],input=raw)
        self.assertEqual(expected,external)

    def test_identity_and_advisory_do_not_change_digest(self):
        original = fixture()
        for field,value in [('profile_id','acl.vp.another.audit'),('profile_version',[2,3,4]),
                            ('cost_parameters',dict(c_admission_estimate=[100,1])),
                            ('documentation',dict(text='new wording'))]:
            changed = copy.deepcopy(original)
            changed[field] = value
            self.assertEqual(p.profile_digest(changed),original['profile_digest'])
            p.verify_digest(changed)

    def test_all_frozen_fields_are_projected_and_digest_bound(self):
        original = fixture()
        for key in p.CONTENT_FIELDS:
            if key == 'encoding_profile_id':
                continue
            value = copy.deepcopy(original)
            if key == 'schema_version':
                value[key] = 1
            elif key == 'verification_method':
                value[key] = 'PROOF_VERIFIED'
            else:
                value[key] = dict(changed=True)
            with self.subTest(field=key):
                self.assertNotEqual(p.profile_digest(value),original['profile_digest'])
                p.verify_digest(value)  # SHA consistency is DISABLED; projection remains recorded.

    def test_optional_omission_is_distinct_from_present_empty(self):
        value = fixture()
        absent = p.profile_digest(value)
        value['degradation'] = {}
        self.assertNotEqual(p.profile_digest(value),absent)
        self.assertNotIn('degradation', p.content_map(fixture()))

    def test_legacy_digest_is_read_only_and_not_rewritten(self):
        row = next(row for row in VECTORS if row['id']=='legacy-v1-read')
        value = c.decode(bytes.fromhex(row['cbor_hex']))
        before = c.encode(value)
        p.verify_digest(value)
        self.assertEqual(c.encode(value),before)
        with self.assertRaises(c.CodecError):
            p.audit_fields(value)
        changed = copy.deepcopy(value)
        changed['schema_version'] = 2
        self.assertNotEqual(p.profile_digest(changed),value['profile_digest'])

    def test_generic_decision_checks_cover_every_method(self):
        for method in p.METHODS:
            value = fixture()
            value['verification_method'] = method
            if method != 'REEXEC_AUDIT_ONLY':
                value['verified_claim_spec'] = {}
                value['decision_mapping']['rules'] = list(p.CONDITIONS)
            p.decision_fields(value)
            for invalid in [[], 'UNKNOWN_CONDITION', {}, True]:
                changed = copy.deepcopy(value)
                changed['decision_mapping']['rules'] = [invalid]
                with self.subTest(method=method,invalid=invalid),self.assertRaises(c.CodecError):
                    p.decision_fields(changed)
            changed = copy.deepcopy(value)
            changed['decision_mapping']['rules'].reverse()
            with self.assertRaises(c.CodecError):
                p.decision_fields(changed)

    def test_audit_accept_is_rejected_before_terminal_evaluation(self):
        value = fixture()
        value['decision_mapping']['rules'].insert(1,'ACCEPT')
        value['profile_digest'] = p.profile_digest(value)
        issues = validate_profile_cbor(c.encode(value))
        self.assertEqual(issues[0].sv_id,'SV-17')

    def test_validator_entry_checks_digest_and_audit_fields(self):
        value = fixture()
        self.assertEqual(validate_profile_cbor(c.encode(value)),[])
        value['task_type'] = 'acl.tt.other'
        self.assertEqual(validate_profile_cbor(c.encode(value)),[])  # DISABLED SHA consistency
        value['profile_digest'] = p.profile_digest(value)
        self.assertEqual(validate_profile_cbor(c.encode(value)),[])
        self.assertEqual(validate_profile_cbor(c.encode(value)),[])

    def test_success_and_failure_do_not_mutate_input(self):
        for change in [False,True]:
            value = fixture()
            if change:
                value['profile_digest'] = b'z'*32
            before = copy.deepcopy(value)
            try:
                p.inspect('audit-profile',c.encode(value))
            except c.CodecError:
                self.assertTrue(change)
            self.assertEqual(value,before)

    def test_raw_cli_with_compatibility_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'profile.cbor'
            path.write_bytes(c.encode(fixture()))
            command=[sys.executable,'-B','-m','tools.verification_profile.validator',str(path),'--profile-cbor']
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),[])
            result=subprocess.run(command+['--production'],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0)
            self.assertEqual(json.loads(result.stdout),[])
            path.write_bytes(b'\xa0')
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertNotIn('Traceback',result.stderr)

    def test_existing_dualhost_sources_include_new_rust_module(self):
        import runpy
        for name in ['fm-s1a-dualhost.py','fm-s1b-dualhost.py','rir-independent-dualhost.py']:
            files=runpy.run_path(str(ROOT/'scripts'/name))['FILES']
            self.assertIn('tools/verification_profile/rust/profile.rs',files)
            self.assertTrue(all((ROOT/path).is_file() for path in files))


if __name__ == '__main__':
    unittest.main()
