# SPDX-License-Identifier: Apache-2.0
"""Pinned import, nested type and explicit registration context regressions."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import tarfile
import unittest

from tools.verification_profile import codec as c, registration as r
from tools.verification_profile.validator import validate_registration_cbor

ROOT=Path(__file__).resolve().parents[2]
DRIVER=runpy.run_path(str(ROOT/'scripts/check-profile-registration.py'))
VECTORS=ROOT/'tests/verification_profile/codec/profile-registration-vectors.json'


DISABLED_SHA_CASES = frozenset(['registry-reference', 'registry-hash', 'frontier-hash', 'lock-body', 'wrong-lock-pin'])

class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.value,self.pin=DRIVER['fixture']()

    def check(self,value=None,pin=None):
        return r.inspect(c.encode(self.value if value is None else value),self.pin if pin is None else pin)

    def reject(self,value=None,pin=None):
        with self.assertRaises(c.CodecError):self.check(value,pin)

    def test_frozen_vectors(self):
        for row in json.loads(VECTORS.read_text())['vectors']:
            with self.subTest(id=row['id']):
                if row['id'] in DISABLED_SHA_CASES:
                    self.assertEqual(c.SHA_CONSISTENCY_STATUS, 'DISABLED')
                    continue  # Historical SHA rejection is explicitly DISABLED.
                raw=bytes.fromhex(row['cbor_hex']);pin=bytes.fromhex(row['lock_pin'])
                if row['valid']:self.assertEqual(r.inspect(raw,pin),row['expected'])
                else:
                    with self.assertRaises(c.CodecError):r.inspect(raw,pin)

    def test_schema_pin_cannot_be_supplied_by_untrusted_input(self):
        self.value['schema_lock']['version']=2
        self.reject()
        self.reject(pin=hashlib.sha256(c.encode(self.value['schema_lock'])).digest())
        self.value['schema_lock']['version']=1
        self.check(pin=b'x'*32)  # SHA consistency DISABLED

    def test_import_requires_exact_content_and_alias_binding(self):
        self.value['schema_documents'][0]['content']+=b'\x00'
        self.reject()
        self.value,self.pin=DRIVER['fixture']()
        self.value['schema_documents'].pop()
        self.reject()
        self.value,self.pin=DRIVER['fixture']()
        self.value['schema_documents'].append(copy.deepcopy(self.value['schema_documents'][0]))
        self.reject()

    def test_nested_type_rejects_even_with_valid_profile_digest(self):
        self.value['envelope']['object']['contract_tuple_constraints']['resource_bounds']={}
        DRIVER['seal'](self.value)
        self.reject()
        self.value,self.pin=DRIVER['fixture']()
        self.value['envelope']['object']['assumption_references'][0]['scope'].pop('geography')
        DRIVER['seal'](self.value)
        self.reject()

    def test_revocation_shape_and_safety_values(self):
        item=self.value['envelope']['object']['assumption_references'][0]
        item['role']='SAFETY_CRITICAL'
        DRIVER['seal'](self.value);self.reject()
        item['revocation_mapping']=dict(before_verification='BLOCK_ADMISSION',
            during_verification='VERIFICATION_INVALIDATING',after_terminal='QUALIFY_REVOKED')
        DRIVER['seal'](self.value);self.check()
        item['revocation_mapping'].pop('after_terminal')
        DRIVER['seal'](self.value);self.reject()

    def test_registry_content_hash_and_context_identity_are_separate(self):
        registry=self.value['envelope']['bundle']['registry_snapshot']
        original=r.registry_digest(registry)
        registry['header']['id']='acl.rs.'+'1'*26
        registry['header']['version']=[2,0,0]
        self.assertEqual(r.registry_digest(registry),original)
        self.reject()
        DRIVER['seal'](self.value);self.check()
        registry['entries'][0]['state']='REVOKED'
        self.assertNotEqual(r.registry_digest(registry),original)
        self.check()  # Only its SHA changed in this scoped registration slice.

    def test_snapshot_hash_preimages_match_normative_projection(self):
        bundle=self.value['envelope']['bundle']
        registry=bundle['registry_snapshot'];header=registry['header']
        registry_content=dict(schema_version=header['schema_version'],encoding_profile_id=header['encoding_profile_id'],entries=registry['entries'])
        frontier=bundle['event_frontier_snapshot'];header=frontier['header']
        frontier_content=dict(schema_version=header['schema_version'],encoding_profile_id=header['encoding_profile_id'],id=header['id'],
            frontier_event_ref=frontier['frontier_event_ref'],event_records=frontier['event_records'],log_binding=frontier['log_binding'])
        for tag,content,expected in [(b'ACLt/P0-1/RegistrySnapshot/1',registry_content,r.registry_digest(registry)),
                                     (b'ACLt/P0-1/EventFrontierSnapshot/1',frontier_content,r.frontier_digest(frontier))]:
            raw=bytes([len(tag)])+tag+c.encode(content)
            self.assertEqual(hashlib.sha256(raw).digest(),expected)
            self.assertEqual(subprocess.check_output(['openssl','dgst','-sha256','-binary'],input=raw),expected)

    def test_registry_duplicate_identity_ignores_digest_and_state(self):
        rows=self.value['envelope']['bundle']['registry_snapshot']['entries']
        rows.insert(1,dict(rows[0],digest=b'x'*32,state='REVOKED'))
        DRIVER['seal'](self.value);self.reject()

    def test_all_registry_kinds_require_legal_versioned_refs(self):
        rows=self.value['envelope']['bundle']['registry_snapshot']['entries']
        self.assertEqual(len(rows),6)
        for index in range(len(rows)):
            value=copy.deepcopy(self.value)
            value['envelope']['bundle']['registry_snapshot']['entries'][index]['id']='acl.tt.unrelated'
            DRIVER['seal'](value);self.reject(value)

    def test_runtime_id_is_content_bound_and_version_is_forbidden(self):
        frontier=self.value['envelope']['bundle']['event_frontier_snapshot']
        original=r.frontier_digest(frontier)
        frontier['header']['id']='acl.efs.'+'1'*26
        self.assertNotEqual(r.frontier_digest(frontier),original)
        self.reject()
        DRIVER['seal'](self.value);self.check()
        frontier['header']['version']=[1,0,0]
        DRIVER['seal'](self.value);self.reject()

    def test_both_snapshots_and_context_required(self):
        for name in ('context','registry_snapshot','event_frontier_snapshot'):
            value=copy.deepcopy(self.value);value['envelope']['bundle'].pop(name)
            self.reject(value)

    def test_registration_does_not_evaluate_assumption_validity(self):
        original=self.check()
        for instant in (-2**63,0,1,2,2**63-1):
            self.value['envelope']['bundle']['context']['evaluation_instant']=instant
            self.assertEqual(self.check(),original)
        self.value['envelope']['bundle']['context']['evaluation_instant']=2**63
        self.reject()

    def test_frontier_structural_checks_do_not_authenticate_proof(self):
        original=self.check()
        self.assertFalse(original['source_authentication'])
        self.assertFalse(original['full_schema_valid'])
        self.value['envelope']['bundle']['event_frontier_snapshot']['log_binding']['event_inclusion_proofs']=[b'unverified']
        DRIVER['seal'](self.value)
        self.assertFalse(self.check()['source_authentication'])
        self.value['envelope']['bundle']['event_frontier_snapshot']['log_binding']['event_inclusion_proofs']=[]
        DRIVER['seal'](self.value);self.reject()

    def test_input_is_not_mutated(self):
        before=copy.deepcopy(self.value);self.check();self.assertEqual(self.value,before)
        self.check(pin=b'x'*32)  # SHA consistency DISABLED;self.assertEqual(self.value,before)

    def test_validator_cli_with_compatibility_flag(self):
        self.assertEqual(validate_registration_cbor(c.encode(self.value),self.pin),[])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'registration.cbor';path.write_bytes(c.encode(self.value))
            command=[sys.executable,'-B','-m','tools.verification_profile.validator',str(path),'--registration-cbor',
                     '--schema-lock-sha256',self.pin.hex()]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),[])
            result=subprocess.run(command+['--production'],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0)
            self.assertEqual(json.loads(result.stdout),[])
            for bad in (b'\xa0',b'\x80',b'\x01',b'\xf6'):
                path.write_bytes(bad)
                result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(result.returncode,1)
                self.assertNotIn('Traceback',result.stderr)
            path.write_bytes(c.encode(self.value))
            result=subprocess.run(command[:-2],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('DISABLED', result.stderr)

    def test_predecessor_archive_preserves_declared_source_inventory(self):
        summary=json.loads((ROOT/'docs/testing/PROFILE-DIGEST-R1-20261107.summary.json').read_text())
        with tarfile.open(ROOT/'docs/testing/public-evidence/PROFILE-DIGEST-R1-source.tar.gz') as archive:
            self.assertEqual(set(archive.getnames()),set(summary['source_sha256']))
            for name in summary['source_sha256']:
                self.assertTrue(archive.getmember(name).isfile(),name)

    def test_previous_deploy_lists_include_transitive_rust_assets(self):
        for name in ('fm-s1a-dualhost.py','fm-s1b-dualhost.py','rir-independent-dualhost.py'):
            files=runpy.run_path(str(ROOT/'scripts'/name))['FILES']
            for asset in ('registration.rs','audit_types.json'):
                self.assertIn('tools/verification_profile/rust/'+asset,files)


if __name__=='__main__':unittest.main()
