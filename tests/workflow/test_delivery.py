"""Regression checks for complete, non-mutating update delivery."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from repository_files import refresh, verify

class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        def ignore(directory, names):
            relative = Path(directory).relative_to(ROOT).as_posix()
            blocked = {'.git', 'target', '.toolchain', '__pycache__', 'dist'}
            if not relative.startswith('docs/workflow/example'):
                blocked.update({'build', 'artifacts'})
            if relative == '.aclt-flow':
                blocked.update({'runs', 'state.json', 'rules-status.json', 'lock'})
            return blocked.intersection(names)
        shutil.copytree(ROOT, self.root, ignore=ignore)
        refresh(self.root)

    def package(self):
        return subprocess.run([sys.executable, '-B', str(self.root / 'scripts/package-singlehost.py')],
                              capture_output=True, text=True)

    def test_archive_contains_registration_and_all_local_test_inputs(self):
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(self.root / 'dist/aclt-singlehost-update.zip') as bundle:
            for name in ['README.md', 'LICENSE', 'Makefile', 'docs/development.md',
                         'registries/verification-profile/mainnet_assurance.disabled.seed.json',
                         'experiments/aclt-multinode-admission/check.py',
                         'scripts/repository_files.py']:
                self.assertEqual(bundle.read(name), (self.root / name).read_bytes())

    def test_stale_source_refuses_package_without_rewriting_manifest(self):
        checksum = self.root / 'SINGLEHOST-SHA256SUMS'
        before = checksum.read_bytes()
        with (self.root / 'README.md').open('a') as out:
            out.write('\nChanged without refreshing checksums\n')
        self.assertNotEqual(self.package().returncode, 0)
        self.assertEqual(checksum.read_bytes(), before)
        self.assertFalse((self.root / 'dist/aclt-singlehost-update.zip').exists())

    def test_new_registration_file_invalidates_manifest(self):
        (self.root / 'registries/verification-profile/new.json').write_text('{}')
        self.assertIn('SINGLEHOST-SHA256SUMS', verify(self.root))

    def test_existing_archive_is_never_replaced(self):
        self.assertEqual(self.package().returncode, 0)
        archive = self.root / 'dist/aclt-singlehost-update.zip'
        before = archive.read_bytes()
        self.assertNotEqual(self.package().returncode, 0)
        self.assertEqual(archive.read_bytes(), before)

    def test_symlinked_input_is_not_bundled(self):
        secret = Path(self.temp.name) / 'external'
        secret.write_text('must not be delivered')
        (self.root / 'registries/linked.json').symlink_to(secret)
        self.assertNotEqual(self.package().returncode, 0)
        self.assertFalse((self.root / 'dist/aclt-singlehost-update.zip').exists())
