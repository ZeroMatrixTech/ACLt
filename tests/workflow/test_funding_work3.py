# SPDX-License-Identifier: Apache-2.0
import copy
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
    def test_source_drift_rejected_before_retained_matrix_checks(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            work.dump(root / 'source-lock.json', {'scripts/funding-work3.py': '00' * 32})
            with self.assertRaisesRegex(ValueError, 'source drift'):
                work.source_check(root)

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

    def test_changed_public_evidence_rejected_before_audit(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'evidence').write_bytes(b'original')
            work.dump(root / 'public-inventory.json', work.inventory(root))
            (root / 'evidence').write_bytes(b'changed')
            with patch.object(work, 'source_check', return_value={}):
                with self.assertRaisesRegex(ValueError, 'changed or missing'):
                    work.verify(root, root / 'no-pins')

    def test_all_independently_retained_checkpoint_pins_are_required(self):
        pins = {name: {'public_digest': '11' * 32, 'checkpoints': {
            label: '22' * 32 for label in (work.RECOVERY_LABELS if name == 'recovery' else ['final'])}}
            for name in work.COMPONENTS}
        work.check_pins(pins)
        for change in ['missing_component', 'missing_checkpoint', 'extra_checkpoint', 'malformed_digest']:
            bad = copy.deepcopy(pins)
            if change == 'missing_component': del bad['reservation']
            elif change == 'missing_checkpoint': del bad['recovery']['checkpoints']['before-commit-rolled-back']
            elif change == 'extra_checkpoint': bad['fixed']['checkpoints']['unrequested'] = '33' * 32
            else: bad['fixed']['public_digest'] = 'not-a-pin'
            with self.assertRaises(ValueError): work.check_pins(bad)

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
