# SPDX-License-Identifier: Apache-2.0
"""Negative controls for the public evidence boundary."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('fm_public_evidence', ROOT/'scripts/check-fm-public-evidence.py')
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class PublicArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.index = json.loads(evidence.DEFAULT_INDEX.read_bytes())
        self.index['archives'] = [copy.deepcopy(self.index['archives'][0])]
        self.item = self.index['archives'][0]
        self.archive = self.root/self.item['archive']
        self.archive.parent.mkdir(parents=True)
        self.archive.write_bytes((ROOT/self.item['archive']).read_bytes())
        report = self.root/self.item['report']
        report.parent.mkdir(parents=True, exist_ok=True)
        report.touch()

    def replace_files(self, files):
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, raw in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))
        self.item['sha256'] = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def verify(self):
        with patch.object(evidence, 'ROOT', self.root):
            return evidence.verify(self.index, replay=False)

    def test_changed_archive_is_rejected_before_loading(self):
        self.archive.write_bytes(self.archive.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError, 'archive hash mismatch'):
            self.verify()

    def test_source_corruption_is_detected_after_archive_hash_refresh(self):
        files = evidence.load_archive(self.archive)
        name = next(iter(json.loads(files['source-sha256.json'])))
        files['source/'+name] += b'changed'
        self.replace_files(files)
        with self.assertRaisesRegex(ValueError, 'source file hash mismatch'):
            self.verify()

    def test_changed_snapshot_is_detected_after_archive_hash_refresh(self):
        files = evidence.load_archive(self.archive)
        prefix = self.item['snapshots'][0]['prefix']
        name = prefix+'/snapshot.cbor'
        files[name] += b'changed'
        self.replace_files(files)
        with self.assertRaisesRegex(ValueError, 'snapshot hash mismatch'):
            self.verify()

    def test_wrong_independent_genesis_is_rejected(self):
        self.item['snapshots'][0]['genesis'] = '00'*32
        with self.assertRaisesRegex(ValueError, 'independent genesis mismatch'):
            self.verify()

    def test_unsafe_members_links_and_duplicates_are_rejected(self):
        for name, kind, repeats, message in [
            ('../escape', tarfile.REGTYPE, 1, 'unsafe evidence path'),
            ('/absolute', tarfile.REGTYPE, 1, 'unsafe evidence path'),
            ('link', tarfile.SYMTYPE, 1, 'archive link or special file'),
            ('same', tarfile.REGTYPE, 2, 'duplicate archive file'),
            ('private/config.cbor', tarfile.REGTYPE, 1, 'private runtime material'),
            ('executor.pem', tarfile.REGTYPE, 1, 'private runtime material'),
        ]:
            with self.subTest(name=name):
                with tarfile.open(self.archive, 'w:gz') as archive:
                    for _ in range(repeats):
                        info = tarfile.TarInfo(name)
                        info.type = kind
                        info.linkname = 'elsewhere' if kind == tarfile.SYMTYPE else ''
                        info.size = 0
                        archive.addfile(info, io.BytesIO())
                with self.assertRaisesRegex(ValueError, message):
                    evidence.load_archive(self.archive)


if __name__ == '__main__':
    unittest.main()
