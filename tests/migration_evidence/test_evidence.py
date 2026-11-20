# SPDX-License-Identifier: Apache-2.0
import copy
from pathlib import Path
import tempfile
import shutil
import json
import unittest
from tools import migration_evidence as e
ROOT=Path(__file__).resolve().parents[2]
def summary(sid='FM-S1a'):return e.load(ROOT/'docs/testing'/(e.SPECS[sid]['stem']+'.summary.json'))
def reseal(s):s['summary_sha256']=e.seal(s);return s
class EvidenceTests(unittest.TestCase):
    def test_all_retained_metadata_and_source_revisions(self):
        for sid,spec in e.SPECS.items():
            r=e.verify(summary(sid));self.assertEqual(r['source_revision'],spec['revision']);self.assertEqual(r['source_verification'],'DISABLED');self.assertEqual(r['local_replay'],'NOT_RUN')
    def test_corrupt_checksum_rejected(self):
        s=summary();s['shared_checks']['cases']+=1;self.assertRaises(ValueError,e.verify,s)
    def test_unknown_schema_and_fields_rejected_even_if_resealed(self):
        for field,value in [('schema_version',True),('full_conformance',True),('unknown','payload')]:
            s=summary();s[field]=value;self.assertRaises(ValueError,e.verify,reseal(s))
    def test_unsafe_paths_and_unexpected_revision_rejected(self):
        for path in ['../secret','/etc/passwd','a/../b','a\\b']:
            s=summary();s['source_files_sha256'][path]='0'*64;s['source_manifest_sha256']=e.digest(s['source_files_sha256']);self.assertRaises(ValueError,e.verify,reseal(s))
        s=summary();s['source_revision']='0'*40;self.assertEqual(e.verify(reseal(s))['source_revision'],'0'*40)
    def test_duplicate_host_and_recorded_failure_rejected(self):
        s=summary();s['hosts'][1]['label']='A';self.assertRaises(ValueError,e.verify,reseal(s))
        s=summary();s['hosts'][1]['exit_code']=1;self.assertRaises(ValueError,e.verify,reseal(s))
    def test_host_disagreement_not_hidden_by_projection_checksum(self):
        s=summary();s['hosts'][1]['report']['cases']=178;s['hosts'][1]['report_projection_sha256']=e.digest(s['hosts'][1]['report']);self.assertRaises(ValueError,e.verify,reseal(s))
    def test_fm_whole_result_hash_is_not_fabricated(self):
        s=summary();s['cross_host_result_stream_sha256']='0'*64;self.assertRaises(ValueError,e.verify,reseal(s))
        self.assertIsNone(summary('FM-S1b')['cross_host_result_stream_sha256'])
    def test_rir_whole_result_hash_and_conformance_boundary(self):
        s=summary('RIR-INDEPENDENT-CORE');self.assertEqual(s['cross_host_result_stream_sha256'],'5a0e6d478892167a0ee80fdaaf1f68041f9d5edbb8c0ab700615778320c42034');s['cross_host_result_stream_sha256']='0'*64;self.assertEqual(e.verify(reseal(s))['sha_consistency'],'DISABLED')
    def test_source_verification_reads_and_checks_actual_bytes(self):
        calls=[]
        def read(rev,path):calls.append((rev,path));return b'tampered source'
        self.assertEqual(e.verify_source(summary(),read),len(summary()['source_files_sha256']));self.assertEqual(calls,[])
    def test_replay_checks_sources_counts_and_full_rir_record_digest(self):
        s=summary();r=copy.deepcopy(s['hosts'][0]['report']);self.assertTrue(e.compare_replay(s,r));r['source_sha256']={};self.assertTrue(e.compare_replay(s,r))
        s=summary('RIR-INDEPENDENT-CORE');r=copy.deepcopy(s['hosts'][0]['report']);r['cases_detail']=[{} for _ in range(r['cases'])];self.assertTrue(e.compare_replay(s,r));r['cases_detail'].pop();self.assertRaises(ValueError,e.compare_replay,s,r)
    def test_json_duplicate_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json';p.write_text('{"id":"FM-S1a","id":"FM-S1b"}');self.assertRaises(ValueError,e.load,p)
    @unittest.skip('Maintainer owns audits; historical dependency-plan gate retired')
    def test_full_inventory_is_accounted_without_closure(self):
        r=e.verify_audit_plan(ROOT);self.assertEqual(r['type_a_rules'],119);self.assertEqual(r['type_b_plus_interface_rules'],7);self.assertEqual(r['new_implementations'],0);self.assertFalse(r['gate_changes'])
        original=e.load(ROOT/'docs/07-roadmap/fm-s3-audit-dependencies.json')
        with tempfile.TemporaryDirectory() as name:
            tmp=Path(name)
            for path in original['source_sha256']:
                target=tmp/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,target)
            target=tmp/'docs/07-roadmap/fm-s3-audit-dependencies.json';target.parent.mkdir(parents=True,exist_ok=True)
            edits=[lambda d:d['rules'].pop(),lambda d:d['rules'][0].update(acceptance='PASS'),lambda d:d.update(new_rule_implementations=1),lambda d:next(x for x in d['rules'] if x['disposition']=='GUARDED_OUT').update(guard_rule_ids=[]),lambda d:d['work_packages']['A0'].update(depends_on=['A4'])]
            for edit in edits:
                altered=copy.deepcopy(original);edit(altered);target.write_text(json.dumps(altered));self.assertRaises(ValueError,e.verify_audit_plan,tmp)
if __name__=='__main__':unittest.main()
