# SPDX-License-Identifier: Apache-2.0
"""Frozen exclusion objects, schema resolution and formal wire regressions."""
import copy
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import unittest

from tools.verification_profile import codec as c, references as r
from tools.verification_profile.validator import validate_registration_references_cbor

ROOT=Path(__file__).resolve().parents[2]
DRIVER=runpy.run_path(str(ROOT/'scripts/check-profile-references.py'))


class ReferencesTests(unittest.TestCase):
    def setUp(self):
        self.value,self.pin=DRIVER['fixture']()

    def check(self,value=None):
        return r.inspect(c.encode(self.value if value is None else value),self.pin)

    def check_selection(self,value=None):
        return r.inspect_excluded(c.encode(DRIVER['selection_input'](self.value if value is None else value)))

    def test_frozen_vectors(self):
        vectors=json.loads((ROOT/'tests/verification_profile/codec/profile-references-vectors.json').read_text())['vectors']
        for row in vectors:
            with self.subTest(id=row['id']):
                args=(row['mode'],bytes.fromhex(row['cbor_hex']),bytes.fromhex(row.get('lock_pin','')))
                if row['valid']:self.assertEqual(DRIVER['evaluate'](*args),row['expected'])
                else:
                    with self.assertRaises(c.CodecError):DRIVER['evaluate'](*args)

    def test_all_fourteen_baseline_ids_match_specification(self):
        spec=(ROOT/'docs/03-protocol/verification-profile-schema.md').read_text()
        table=spec.split('### 6.3 基线注册表 v1',1)[1].split('方法特定项：',1)[0]
        expected=set(re.findall(r'\| `(EXC-BASE-[A-Z-]+)`',table))
        self.assertEqual(len(expected),14)
        self.assertEqual(r.BASELINE,expected)
        for id in expected:
            value=copy.deepcopy(self.value)
            value['envelope']['object']['excluded_claims']['exclusion_ids'].remove(id)
            DRIVER['seal'](value)
            with self.subTest(id=id),self.assertRaisesRegex(c.CodecError,'SV-07:'):self.check_selection(value)

    def test_digest_preimages_match_frozen_tags_with_openssl(self):
        value=DRIVER['selection_input'](self.value);registry=value['registry'];h=registry['header']
        registry_content=dict(schema_version=h['schema_version'],encoding_profile_id=h['encoding_profile_id'],entries=registry['entries'])
        selection=value['selection']
        for tag,content,expected in [
            (b'ACLt/P0-1/ExcludedClaimsRegistry/1',registry_content,h['digest']),
            (b'ACLt/P0-1/ExcludedClaims/1',[selection['registry_ref'],sorted(selection['exclusion_ids'],key=c.encode)],selection['digest'])]:
            raw=bytes([len(tag)])+tag+c.encode(content)
            self.assertEqual(hashlib.sha256(raw).digest(),expected)
            self.assertEqual(subprocess.check_output(['openssl','dgst','-sha256','-binary'],input=raw),expected)

    def test_registry_identity_excluded_but_reference_chain_binds_it(self):
        asset=self.value['registry_objects'][0]['object']
        old=r.exclusion_registry_digest(asset)
        asset['header'].update(id='acl.ecr.other',version=[2,0,0])
        self.assertEqual(r.exclusion_registry_digest(asset),old)
        with self.assertRaisesRegex(c.CodecError,'SV-08:'):self.check_selection()
        DRIVER['seal'](self.value);self.check()
        self.assertEqual(r.exclusion_registry_digest(asset),old)

    def test_registry_statement_tamper_rejected_until_fully_rebound(self):
        asset=self.value['registry_objects'][0]['object'];old=asset['header']['digest']
        asset['entries'][0]['statement']='new normative statement'
        self.assertNotEqual(r.exclusion_registry_digest(asset),old)
        with self.assertRaisesRegex(c.CodecError,'SV-89:'):self.check_selection()
        DRIVER['seal'](self.value);self.check()

    def test_digest_sorts_selection_but_does_not_accept_unsorted_wire(self):
        selection=self.value['envelope']['object']['excluded_claims'];original=r.excluded_digest(selection)
        selection['exclusion_ids'].reverse()
        self.assertEqual(r.excluded_digest(selection),original)
        with self.assertRaises(c.CodecError):self.check_selection()
        self.value,self.pin=DRIVER['fixture']()
        registry=self.value['registry_objects'][0]['object'];original=r.exclusion_registry_digest(registry)
        registry['entries'].reverse()
        self.assertNotEqual(r.exclusion_registry_digest(registry),original)
        DRIVER['seal'](self.value);self.check()

    def test_membership_uses_explicit_registry_content(self):
        asset=self.value['registry_objects'][0]['object'];asset['entries'].pop()
        DRIVER['seal'](self.value)
        with self.assertRaisesRegex(c.CodecError,'SV-08:'):self.check_selection()
        self.value,self.pin=DRIVER['fixture']()
        rows=self.value['envelope']['bundle']['registry_snapshot']['entries']
        row=next(row for row in rows if row['object_kind']=='EXCLUDED_CLAIMS_REGISTRY')
        row['version']=[9,0,0]
        DRIVER['PREVIOUS']['seal'](self.value)
        with self.assertRaisesRegex(c.CodecError,'SV-08:'):self.check_selection()

    def test_selection_digest_owner_after_other_bindings_are_valid(self):
        self.value['envelope']['object']['excluded_claims']['digest']=b'x'*32
        DRIVER['PREVIOUS']['seal'](self.value)
        with self.assertRaisesRegex(c.CodecError,'SV-72:'):self.check()

    def test_wire_time_range_has_one_encoding(self):
        assumption=self.value['envelope']['object']['assumption_references'][0]
        self.assertEqual(assumption['validity_window'],[1,2])
        original=self.check()
        self.value['envelope']['bundle']['context']['evaluation_instant']=-(2**63)
        self.assertEqual(self.check(),original)
        assumption['validity_window']=dict(start=1,end=2)
        DRIVER['seal'](self.value)
        with self.assertRaisesRegex(c.CodecError,'wire TimeRange'):self.check()

    def test_external_payload_schema_and_hash_are_both_bound(self):
        binding=self.value['envelope']['bundle']['event_frontier_snapshot']['log_binding']
        obj=binding['finalized_checkpoint']
        self.assertEqual(set(obj),{'schema_ref','canonical_bytes','object_digest'})
        self.assertEqual(c.decode(obj['canonical_bytes']),b'checkpoint')
        obj['schema_ref']['digest']=b'x'*32;DRIVER['seal'](self.value)
        with self.assertRaisesRegex(c.CodecError,'trusted lock'):self.check()
        self.value,self.pin=DRIVER['fixture']()
        binding=self.value['envelope']['bundle']['event_frontier_snapshot']['log_binding']
        binding['finalized_checkpoint']['object_digest']=b'x'*32;DRIVER['seal'](self.value)
        with self.assertRaisesRegex(c.CodecError,'payload digest'):self.check()

    def test_external_canonical_bytes_and_schema_type_checked(self):
        obj=self.value['envelope']['bundle']['event_frontier_snapshot']['log_binding']['finalized_checkpoint']
        for raw in (b'\x58\x01a',c.encode(42)):
            obj.update(canonical_bytes=raw,object_digest=hashlib.sha256(raw).digest())
            DRIVER['seal'](self.value)
            with self.assertRaises(c.CodecError):self.check()

    def test_import_hash_pin_is_separate_and_no_official_registration_claim(self):
        imports=r.Imports(self.value['schema_lock'],self.value['schema_documents'],self.pin)
        self.assertNotIn('ExternalTypedObject',imports.refs)
        self.assertIn('ExternalVersionedObjectRef',imports.refs)
        with self.assertRaises(c.CodecError):r.inspect(c.encode(self.value),b'x'*32)
        output=self.check()
        self.assertFalse(output['full_schema_valid']);self.assertFalse(output['source_authentication'])

    def test_old_limited_route_and_historical_source_pins_preserved(self):
        from tools.verification_profile import registration
        old,old_pin=DRIVER['PREVIOUS']['fixture']()
        self.assertEqual(registration.inspect(c.encode(old),old_pin)['schema_lock_sha256'],old_pin.hex())
        self.assertEqual(old['envelope']['object']['assumption_references'][0]['validity_window'],dict(start=1,end=2))
        legacy=json.loads((ROOT/'tests/verification_profile/codec/profile-registration-vectors.json').read_text())['vectors']
        first=next(row for row in legacy if row['valid'])
        self.assertEqual(registration.inspect(bytes.fromhex(first['cbor_hex']),bytes.fromhex(first['lock_pin'])),first['expected'])

    def test_assets_explicit_and_no_mutation(self):
        before=copy.deepcopy(self.value);self.check();self.assertEqual(self.value,before)
        for assets in ([],self.value['registry_objects']*2):
            value=copy.deepcopy(self.value);value['registry_objects']=assets
            with self.assertRaises(c.CodecError):self.check(value)
            self.assertEqual(self.value,before)

    def test_cli_production_and_malformed_inputs_fail_closed(self):
        self.assertEqual(validate_registration_references_cbor(c.encode(self.value),self.pin),[])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'refs.cbor';path.write_bytes(c.encode(self.value))
            cmd=[sys.executable,'-B','-m','tools.verification_profile.validator',str(path),
                 '--registration-references-cbor','--schema-lock-sha256',self.pin.hex()]
            output=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(output.returncode,0,output.stderr);self.assertEqual(json.loads(output.stdout),[])
            output=subprocess.run(cmd+['--production'],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(output.returncode,1);self.assertEqual(json.loads(output.stdout)[0]['sv_id'],'COVERAGE')
            output=subprocess.run(cmd+['--registration-cbor'],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(output.returncode,2)
            for raw in (b'\xa0',b'\x80',b'\x01',b'\xf6'):
                path.write_bytes(raw);output=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(output.returncode,1);self.assertNotIn('Traceback',output.stderr)


if __name__=='__main__':unittest.main()
