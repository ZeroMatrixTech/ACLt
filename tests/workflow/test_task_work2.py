# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/task-work2.py'
spec = importlib.util.spec_from_file_location('task_work2', SCRIPT)
work = importlib.util.module_from_spec(spec)
spec.loader.exec_module(work)


class TaskWork2Checks(unittest.TestCase):
    def test_symlink_cannot_substitute_source_or_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'file').write_bytes(b'original')
            (root / 'alias').symlink_to(root / 'file')
            with self.assertRaisesRegex(ValueError, 'regular'):
                work.sha(root / 'alias')

    def test_retained_path_cannot_escape_evidence(self):
        for name in ['../outside', '/absolute/file', 'nested/../outside']:
            with self.assertRaisesRegex(ValueError, 'relative path'):
                work.retained(Path('/missing'), name)

    def test_changed_public_evidence_is_rejected_before_reduction(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'evidence').write_bytes(b'original')
            work.dump(root / 'public-inventory.json', work.inventory(root))
            (root / 'evidence').write_bytes(b'changed')
            with patch.object(work, 'source_check', return_value={}):
                with self.assertRaisesRegex(ValueError, 'changed or missing'):
                    work.verify(root, root / 'no-pins')

    def test_current_source_drift_rejected_before_retained_matrices(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            work.dump(root / 'source-lock.json', {'scripts/task-work2.py': '0' * 64})
            with self.assertRaisesRegex(ValueError, 'source drift'):
                work.source_check(root)

    def test_existing_report_preserved_before_evidence_read(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            report = root / 'existing.json'
            report.write_text('preserve\n')
            p = subprocess.run([sys.executable, '-B', str(SCRIPT), 'verify', '--evidence',
                                str(root / 'missing'), '--pins', str(root / 'no-pins'),
                                '--report', str(report)], capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('new report outside', p.stderr)
            self.assertEqual(report.read_text(), 'preserve\n')
