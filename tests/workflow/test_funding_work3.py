# SPDX-License-Identifier: Apache-2.0
import copy
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/funding-work3.py'
spec = importlib.util.spec_from_file_location('funding_work3', SCRIPT)
work = importlib.util.module_from_spec(spec)
spec.loader.exec_module(work)


class FundingWork3Checks(unittest.TestCase):
    def test_source_pins_are_optional_records(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self.assertEqual(work.source_check(root), {})
            record = {'scripts/funding-work3.py': '0' * 64}
            work.dump(root / 'source-lock.json', record)
            self.assertEqual(work.source_check(root), record)
            self.assertEqual(work.SHA_CONSISTENCY_STATUS, 'DISABLED')

    def test_symlink_and_path_escape_cannot_substitute_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'real').write_bytes(b'original')
            (root / 'alias').symlink_to(root / 'real')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                work.retained(root, 'alias')
            for name in ['../outside', '/absolute', 'nested/../outside']:
                with self.assertRaisesRegex(ValueError, 'relative path'):
                    work.retained(root, name)

    def test_hash_drift_reaches_actual_matrix_checks(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'evidence').write_bytes(b'original')
            work.dump(root / 'public-inventory.json', work.inventory(root))
            (root / 'evidence').write_bytes(b'changed')
            (root / 'reservation').mkdir()
            work.dump(root / 'reservation/report.json', {'status': 'FAIL'})
            with patch.object(work, 'source_check', return_value={}):
                with self.assertRaisesRegex(ValueError, 'matrix incomplete'):
                    work.verify(root, None)

    def test_pins_are_records_without_acceptance_requirement(self):
        for pins in [{}, None, {'fixed': {'public_digest': 'not-a-pin'}}]:
            self.assertEqual(work.check_pins(pins), 'DISABLED')

    def test_existing_report_preserved_before_evidence_read(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            report = root / 'existing.json'
            report.write_text('preserve previous result\n')
            r = subprocess.run([sys.executable, '-B', str(SCRIPT), 'verify', '--evidence',
                                str(root / 'missing'), '--pins', str(root / 'no-pins'),
                                '--report', str(report)], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('new report outside', r.stderr)
            self.assertEqual(report.read_text(), 'preserve previous result\n')
