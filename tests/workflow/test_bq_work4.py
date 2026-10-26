# SPDX-License-Identifier: Apache-2.0
"""Retained mathematical research must fail closed on source/evidence drift."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('bq_work4',ROOT/'scripts/bq-work4.py')
suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)


class BQWork4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.base=Path(cls.temp.name)/'original'
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts/bq-work4.py'),'run','--output',str(cls.base)],check=True,stdout=subprocess.DEVNULL)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.work=tempfile.TemporaryDirectory();self.addCleanup(self.work.cleanup)
        self.root=Path(self.work.name)/'copy';shutil.copytree(self.base,self.root)
    def test_source_drift_rejected_before_replay(self):
        p=self.root/'source-lock.json';d=json.loads(p.read_text());d['scripts/bq-work4.py']='0'*64;p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'source drift'):suite.verify(self.root)
    def test_forged_report_with_rehashed_inventory_rejected(self):
        p=self.root/'boundaries.json';d=json.loads(p.read_text());d['parameters']['B']=4;p.write_text(json.dumps(d))
        (self.root/'inventory.json').write_text(json.dumps(suite.inventory(self.root)))
        with self.assertRaisesRegex(ValueError,'slice report drift'):suite.verify(self.root)
    def test_symlinks_and_traversal_cannot_supply_evidence(self):
        p=self.root/'source-lock.json';p.unlink();p.symlink_to(self.base/'source-lock.json')
        with self.assertRaises(ValueError):suite.verify(self.root)
        for name in ['../source-lock.json','/tmp/source-lock.json','a/../source-lock.json']:
            with self.assertRaises(ValueError):suite.retained(self.root,name)
    def test_forged_suite_summary_rejected(self):
        p=self.root/'suite.json';d=json.loads(p.read_text());d['continuity']['real_BQ_established']=True;p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'summary drift'):suite.verify(self.root)
    def test_offline_verify_preserves_evidence_and_existing_report(self):
        before={p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        result=suite.verify(self.root);self.assertEqual(result['slices_recomputed'],3);self.assertFalse(result['continuity']['capability_changed'])
        after={p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()};self.assertEqual(before,after)
        dest=Path(self.work.name)/'old.json';dest.write_text('retained')
        p=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/bq-work4.py'),'verify','--evidence',str(self.root),'--report',str(dest)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.assertNotEqual(p.returncode,0);self.assertEqual(dest.read_text(),'retained')


if __name__=='__main__':unittest.main()
