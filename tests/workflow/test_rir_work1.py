# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/rir-work1.py'
spec=importlib.util.spec_from_file_location('rir_work1',SCRIPT)
work=importlib.util.module_from_spec(spec)
spec.loader.exec_module(work)

class RIRWork1Checks(unittest.TestCase):
    def test_missing_source_pin_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'missing source pins'):
            work.source_check(ROOT,{'source_hashes':{}},{'build.py'})
    def test_current_source_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t);(path/'program.rs').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'differs from tested source'):
                work.source_check(path,{'source_hashes':{'program.rs':hashlib.sha256(b'original').hexdigest()}},{'program.rs'})
    def test_symlink_does_not_count_as_retained_file(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t);(path/'original').write_bytes(b'x');(path/'alias').symlink_to('original')
            with self.assertRaisesRegex(ValueError,'regular evidence/source file'):work.sha(path/'alias')
    def test_all_three_slice_pairs_required(self):
        with self.assertRaisesRegex(ValueError,'all three'):work.verify([])
    def test_existing_report_preserved_before_reading_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t);report=path/'result.json';report.write_text('keep previous result\n')
            argv=[sys.executable,'-B',str(SCRIPT),'verify','--report',str(report)]
            for i in range(1,4):argv+=['--slice'+str(i),str(path/'missing-A'),str(path/'missing-B')]
            p=subprocess.run(argv,capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0);self.assertIn('report must be new',p.stderr)
            self.assertEqual(report.read_text(),'keep previous result\n')
