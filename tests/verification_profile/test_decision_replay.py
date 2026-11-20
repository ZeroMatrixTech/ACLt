# SPDX-License-Identifier: Apache-2.0
"""Phase D cross-check vectors also exercise the default Python gate."""
import json
import runpy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.verification_profile import codec, decision_replay

ROOT = Path(__file__).resolve().parents[2]
VECTORS = ROOT / 'tests/verification_profile/codec/decision-replay-vectors.json'
D = runpy.run_path(str(ROOT / 'scripts/check-decision-replay.py'))


class DecisionReplayTests(unittest.TestCase):
    def test_vectors(self):
        rows = D['current_frozen_vectors']()
        for row in rows:
            with self.subTest(row=row['id']):
                args = [bytes.fromhex(row[key]) for key in ('cbor_hex', 'schema_pin', 'contract_pin')]
                if 'error' in row['expected']:
                    with self.assertRaises(codec.CodecError):
                        decision_replay.inspect(*args)
                else:
                    self.assertEqual(D['semantic_result'](decision_replay.inspect(*args)), row['expected'])

    def test_cli_optional_pin_records_and_compatibility_flag(self):
        row = json.loads(VECTORS.read_text())['vectors'][0]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'decision.cbor'
            path.write_bytes(bytes.fromhex(row['cbor_hex']))
            cmd = [sys.executable, '-B', '-m', 'tools.verification_profile.validator',
                   str(path), '--decision-replay-cbor', '--schema-lock-sha256', row['schema_pin'],
                   '--decision-contract-sha256', row['contract_pin']]
            self.assertEqual(subprocess.run(cmd, cwd=ROOT, capture_output=True).returncode, 0)
            blocked = subprocess.run(cmd + ['--production'], cwd=ROOT, capture_output=True)
            self.assertEqual(blocked.returncode, 0)
            self.assertNotIn(b'COVERAGE', blocked.stdout)
