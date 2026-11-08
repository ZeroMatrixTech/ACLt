# SPDX-License-Identifier: Apache-2.0
"""Selected registration rules, frozen assumption hash and audit integration."""
import copy
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tarfile
import tempfile
import unittest

from tools.verification_profile import codec as c, profile as p, registration_rules as r
from tools.verification_profile.validator import validate_registration_rules_cbor

ROOT=Path(__file__).resolve().parents[2]
DRIVER=runpy.run_path(str(ROOT/'scripts/check-registration-rules.py'))


class RegistrationRuleTests(unittest.TestCase):
    def setUp(self):
        self.value,self.pin=DRIVER['fixture']()

    def check(self,value=None):
        return r.inspect(c.encode(self.value if value is None else value),self.pin)

    def test_fixed_vectors(self):
        rows=json.loads((ROOT/'tests/verification_profile/codec/registration-rules-vectors.json').read_text())['vectors']
        self.assertEqual(len(rows),len({row['id'] for row in rows}))
        for row in rows:
            with self.subTest(id=row['id']):
                args=(row['mode'],bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']))
                if row['valid']:self.assertEqual(DRIVER['evaluate'](*args),row['expected'])
                else:
                    with self.assertRaises(c.CodecError):DRIVER['evaluate'](*args)

    def test_method_enum_and_removed_field_have_specific_owners(self):
        for method in p.METHODS:
            value,pin=DRIVER['fixture'](method)
            self.assertEqual(r.inspect(c.encode(value),pin)['verification_method'],method)
            value['profile']['post_execution_predicate']={}
            with self.assertRaisesRegex(c.CodecError,'SV-32:'):r.inspect(c.encode(value),pin)
        for invalid in ('ATTESTED',[],True,1):
            self.value['profile']['verification_method']=invalid
            with self.assertRaisesRegex(c.CodecError,'SV-03:'):self.check()

    def test_required_classes_and_roles_match_ar2_specification(self):
        spec=(ROOT/'docs/03-protocol/verification-profile-schema.md').read_text()
        section=spec.split('**AR-2**',1)[1].split('**AR-3**',1)[0]
        expected={method:set() for method in p.METHODS}
        for line in section.splitlines():
            if not line.startswith('| `'):continue
            fields=line.strip('|').split('|');method=re.findall(r'`([^`]+)`',fields[0])[0]
            classes=re.findall(r'`([^`]+)`',fields[1]);roles=re.findall(r'`([^`]+)`',fields[2])
            if classes:expected[method].update((name,roles[0]) for name in classes)
        self.assertEqual(r.REQUIRED,expected)
        self.assertEqual([len(r.REQUIRED[x]) for x in p.METHODS],[1,1,5,0])
        for method,pairs in expected.items():
            for kind,role in pairs:
                value,pin=DRIVER['fixture'](method)
                row=next(row for row in value['profile']['assumption_references'] if row['assumption_class']==kind)
                row['role']='INFORMATIONAL';DRIVER['seal'](value)
                with self.subTest(method=method,kind=kind),self.assertRaisesRegex(c.CodecError,'SV-38:'):
                    r.inspect(c.encode(value),pin)

    def test_revocation_all_three_stages_and_safety_values(self):
        row=self.value['profile']['assumption_references'][0]
        for key in r.REVOCATION_FIELDS:
            value=copy.deepcopy(self.value);value['profile']['assumption_references'][0]['revocation_mapping'].pop(key)
            DRIVER['seal'](value)
            with self.assertRaisesRegex(c.CodecError,'SV-33:'):self.check(value)
        row['role']='SAFETY_CRITICAL'
        DRIVER['seal'](self.value)
        with self.assertRaisesRegex(c.CodecError,'SV-37:'):self.check()
        row['revocation_mapping']=copy.deepcopy(r.SAFE_REVOCATION)
        DRIVER['seal'](self.value);self.check()

    def test_scope_requires_six_dimensions_but_not_nonempty_phase_i_sets(self):
        for key in r.SCOPE_FIELDS:
            value=copy.deepcopy(self.value);value['profile']['assumption_references'][0]['scope'].pop(key)
            DRIVER['seal'](value)
            with self.assertRaisesRegex(c.CodecError,'SV-59:'):self.check(value)
        self.value['profile']['assumption_references'][0]['scope'].update(fault_domains=[],geography=[])
        DRIVER['seal'](self.value);self.check()

    def test_degradation_trigger_subset_does_not_impose_extra_array_order(self):
        target=dict(id='acl.vp.old.audit',version=[1,0,0],digest=b'd'*32)
        for triggers in ([],list(r.TRIGGERS),['POPULATION_TOO_SMALL']*2):
            self.value['profile']['degradation']=dict(target=target,triggers=triggers)
            DRIVER['seal'](self.value);self.check()
        self.value['profile']['degradation']['triggers']=['ATTESTED']
        DRIVER['seal'](self.value)
        with self.assertRaisesRegex(c.CodecError,'SV-22:'):self.check()

    def test_supersedes_requires_complete_identity_in_profile_domain(self):
        ref=dict(id='acl.vp.old.audit',version=[1,0,0],digest=b'd'*32)
        self.value['profile']['supersedes']=copy.deepcopy(ref);DRIVER['seal'](self.value);self.check()
        for key,value in [('id','acl.vp.other.audit'),('version',[9,0,0]),('digest',b'x'*32)]:
            changed=copy.deepcopy(self.value);changed['profile']['supersedes'][key]=value;DRIVER['seal'](changed)
            with self.assertRaisesRegex(c.CodecError,'SV-84:'):self.check(changed)
        changed=copy.deepcopy(self.value)
        rows=changed['registry_snapshot']['entries']
        row=next(row for row in rows if row['object_kind']=='VERIFICATION_PROFILE')
        row.update(object_kind='CLAIM_TEMPLATE',id='acl.ct.some')
        rows.sort(key=lambda row:c.encode([row['object_kind'],row['id'],row['version']]))
        DRIVER['seal'](changed)
        with self.assertRaisesRegex(c.CodecError,'SV-84:'):self.check(changed)

    def test_static_assumption_digest_matches_independent_preimage(self):
        value,pin=DRIVER['fixture']('REEXEC_BOUNDED')
        assumptions=value['profile']['assumption_references']
        pairs=sorted([[row['assumption_id'],row['statement_digest']] for row in assumptions],key=c.encode)
        self.assertEqual(len(pairs),6)  # Five required pairs plus INFORMATIONAL.
        tag=b'ACLt/P0-1/AssumptionSet/1';raw=bytes([len(tag)])+tag+c.encode(pairs)
        self.assertEqual(r.assumption_set_digest(assumptions),hashlib.sha256(raw).digest())
        self.assertEqual(r.assumption_set_digest(assumptions),subprocess.check_output(['openssl','dgst','-sha256','-binary'],input=raw))
        self.assertEqual(r.assumption_set_digest([]),hashlib.sha256(bytes([len(tag)])+tag+b'\x80').digest())

    def test_set_digest_order_independent_and_not_evidence_version_digest(self):
        value,pin=DRIVER['fixture']('REEXEC_BOUNDED');old=value['assumption_set_digest'];old_profile=value['profile']['profile_digest']
        value['profile']['assumption_references'].reverse();DRIVER['seal'](value)
        self.assertEqual(old,value['assumption_set_digest']);self.assertNotEqual(old_profile,value['profile']['profile_digest'])
        row=value['profile']['assumption_references'][0];row['evidence_version']=[9,8,7]
        DRIVER['seal'](value);self.assertEqual(old,value['assumption_set_digest'])
        row['statement_digest']=b'x'*32;DRIVER['seal'](value)
        self.assertNotEqual(old,value['assumption_set_digest'])
        value['assumption_set_digest']=old
        with self.assertRaisesRegex(c.CodecError,'SV-73:'):r.inspect(c.encode(value),pin)

    def test_phase_r_does_not_evaluate_scope_or_window(self):
        row=self.value['profile']['assumption_references'][0]
        row['scope']['task_class']='acl.tt.other'
        row['validity_window']=[-20,-10]
        DRIVER['seal'](self.value);self.check()

    def test_fixed_audit_entry_adds_digest_without_enabling_other_methods(self):
        audit,pin=DRIVER['PREVIOUS']['fixture']()
        result=r.inspect_audit(c.encode(audit),pin)
        self.assertEqual(result['assumption_set_digest_hex'],r.assumption_set_digest(audit['envelope']['object']['assumption_references']).hex())
        self.assertNotIn('assumption_set_digest',audit['envelope']['object'])
        for method in p.METHODS[:-1]:
            value=copy.deepcopy(audit);value['envelope']['object']=DRIVER['fixture'](method)[0]['profile']
            DRIVER['PREVIOUS']['seal'](value)
            with self.assertRaisesRegex(c.CodecError,'audit-only'):r.inspect_audit(c.encode(value),pin)
        audit['envelope']['object']['degradation']=dict(target=dict(id='acl.vp.old.audit',version=[1,0,0],digest=b'd'*32),triggers=['POPULATION_TOO_SMALL'])
        DRIVER['PREVIOUS']['seal'](audit)
        with self.assertRaisesRegex(c.CodecError,'fixed audit'):r.inspect_audit(c.encode(audit),pin)

    def test_cli_modes_and_production_boundary(self):
        for audit in (False,True):
            value,pin=DRIVER['PREVIOUS']['fixture']() if audit else DRIVER['fixture']()
            self.assertEqual(validate_registration_rules_cbor(c.encode(value),pin,audit=audit),[])
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'rules.cbor';path.write_bytes(c.encode(value))
                flag='--registration-r4-cbor' if audit else '--registration-rules-cbor'
                cmd=[sys.executable,'-B','-m','tools.verification_profile.validator',str(path),flag,'--schema-lock-sha256',pin.hex()]
                result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout),[])
                result=subprocess.run(cmd+['--production'],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(result.returncode,1);self.assertEqual(json.loads(result.stdout)[0]['sv_id'],'COVERAGE')
                result=subprocess.run(cmd+['--registration-cbor'],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(result.returncode,2)
                for raw in (b'\xa0',b'\x80',b'\x01',b'\xf6'):
                    path.write_bytes(raw);result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
                    self.assertEqual(result.returncode,1);self.assertNotIn('Traceback',result.stderr)

    def test_failure_and_success_do_not_mutate_input(self):
        before=copy.deepcopy(self.value);self.check();self.assertEqual(self.value,before)
        with self.assertRaises(c.CodecError):r.inspect(c.encode(self.value),b'x'*32)
        self.assertEqual(self.value,before)

    def test_uncommitted_r3_evidence_keeps_its_exact_sources(self):
        summary=json.loads((ROOT/'docs/testing/PROFILE-REFERENCES-R3-20261108.summary.json').read_text())
        archive=ROOT/summary['source_archive']['path']
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),summary['source_archive']['sha256'])
        with tarfile.open(archive) as tar:
            for name,digest in summary['source_sha256'].items():
                self.assertEqual(hashlib.sha256(tar.extractfile(name).read()).hexdigest(),digest,name)


if __name__=='__main__':unittest.main()
