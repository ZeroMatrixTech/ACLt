# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from normalize import normalize, artifact, tagged, section, name, SliceError
from build import build
from compare import compare
FIXTURE = json.loads((ROOT / 'tests/fixture.json').read_text())
RAW = bytes.fromhex(FIXTURE['raw_hex'])
NORMAL = bytes.fromhex(FIXTURE['normalized_hex'])


class ProbeTests(unittest.TestCase):
    def test_compiler_fixture_and_idempotence(self):
        lowered, detail = normalize(RAW)
        self.assertEqual(lowered, NORMAL)
        self.assertEqual(normalize(lowered)[0], lowered)
        self.assertEqual(detail['removed_exports'], ['__data_end', '__heap_base'])
        self.assertEqual({e['name'] for e in detail['exports']}, {'run', 'memory'})

    def test_truncated_required_sections_rejected(self):
        for i in range(len(NORMAL)):
            with self.subTest(prefix=i), self.assertRaises(SliceError):
                normalize(NORMAL[:i])

    def test_unapproved_metadata_and_export_rejected(self):
        for raw in [NORMAL + section(0, name('unapproved')), RAW.replace(b'__heap_base', b'__heap_bass')]:
            with self.assertRaises(SliceError):
                normalize(raw)

    def test_valid_nonempty_body_is_outside_slice(self):
        self.assertEqual(NORMAL[-6:], b'\x0a\x04\x01\x02\x00\x0b')
        # A well-formed unreachable body must not be silently treated as empty.
        with self.assertRaises(SliceError):
            normalize(NORMAL[:-6] + b'\x0a\x05\x01\x03\x00\x00\x0b')

    def test_nonminimal_section_length_rejected(self):
        with self.assertRaises(SliceError):
            normalize(NORMAL[:9] + b'\x84\x00' + NORMAL[10:])

    def test_fixed_candidate_digest(self):
        self.assertEqual(tagged(artifact(NORMAL)), FIXTURE['candidate_rir_digest'])

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)
            (path / 'keep').write_text('retain')
            with self.assertRaises(FileExistsError):
                build(path / 'missing-toolchain', path)
            self.assertEqual((path / 'keep').read_text(), 'retain')
            self.assertFalse((path / 'report.json').exists())

    def test_preflight_failure_retains_failed_report(self):
        with tempfile.TemporaryDirectory() as t:
            output = Path(t) / 'new-run'
            with self.assertRaises(FileNotFoundError):
                build(Path(t) / 'missing-toolchain', output)
            self.assertEqual(json.loads((output / 'report.json').read_text())['status'], 'FAIL')

    def retained_pair(self, root):
        paths = [root / 'A', root / 'B']
        for host, path in zip(['host-a', 'host-b'], paths):
            path.mkdir()
            report = {'status': 'PASS', 'hostname': host, 'source_hashes': {'fixture': 'same'},
                      'rustc_verbose': 'same compiler', 'toolchain_lock_sha256': 'same lock', 'builds': []}
            for location in ['first-location', 'second-location']:
                directory = path / location
                directory.mkdir()
                row = {'name': location, 'candidate_rir_digest': tagged(artifact(NORMAL))}
                for file, data, key in [('raw.wasm', RAW, 'raw_sha256'), ('normalized.wasm', NORMAL, 'normalized_sha256'),
                                        ('candidate-artifact.cbor', artifact(NORMAL), 'artifact_sha256')]:
                    (directory / file).write_bytes(data)
                    row[key] = hashlib.sha256(data).hexdigest()
                report['builds'].append(row)
            (path / 'report.json').write_text(json.dumps(report))
        return paths

    def test_comparison_checks_retained_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            left, right = self.retained_pair(Path(t))
            self.assertEqual(compare(left, right)['status'], 'PASS')
            (right / 'first-location/normalized.wasm').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                compare(left, right)

    def test_same_host_and_source_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            left, right = self.retained_pair(Path(t))
            original = json.loads((right / 'report.json').read_text())
            for key, value in [('hostname', 'host-a'), ('source_hashes', {'different': 'source'})]:
                modified = copy.deepcopy(original)
                modified[key] = value
                (right / 'report.json').write_text(json.dumps(modified))
                with self.assertRaises(ValueError):
                    compare(left, right)


if __name__ == '__main__':
    unittest.main()
