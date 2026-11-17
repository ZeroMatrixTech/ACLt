# SPDX-License-Identifier: Apache-2.0
import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from tools.git_sources import git, read_blob
from repository_files import tracked_coverage


class GitSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'sample').write_bytes(b'exact source\n')
        subprocess.run(['git', '-C', str(self.repo), 'add', 'sample'], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'test'], check=True)
        self.env = dict(os.environ, GIT_TEST_ASSUME_DIFFERENT_OWNER='1',
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_COUNT='0')

    def test_explicit_repository_survives_container_ownership(self):
        with patch.dict(os.environ, self.env, clear=True):
            rejected = subprocess.run(['git', '-C', str(self.repo), 'show', 'HEAD:sample'], capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn(b'dubious ownership', rejected.stderr)
            self.assertEqual(read_blob(self.repo, 'HEAD', 'sample'), b'exact source\n')
            self.assertEqual(git(self.repo, 'config', '--global', '--list').stdout, b'')

    def test_missing_revision_keeps_git_diagnostic(self):
        with self.assertRaisesRegex(ValueError, 'Git failed.*show absent:sample'):
            read_blob(self.repo, 'absent', 'sample')

    def test_missing_path_is_not_ignored(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            read_blob(self.repo, 'HEAD', 'absent')

    def test_export_without_git_is_not_run(self):
        export = Path(self.temp.name) / 'export'
        export.mkdir()
        self.assertEqual(tracked_coverage(export, []), 'NOT_RUN_NO_CHECKOUT')

    def test_broken_checkout_is_error(self):
        (self.repo / '.git' / 'HEAD').unlink()
        with self.assertRaisesRegex(ValueError, 'Git failed'):
            tracked_coverage(self.repo, [])

    def test_nested_export_does_not_use_parent_checkout(self):
        export = self.repo / 'export'
        export.mkdir()
        self.assertEqual(tracked_coverage(export, []), 'NOT_RUN_NO_CHECKOUT')

    def test_tracked_coverage_under_container_ownership(self):
        (self.repo / 'DELIVERY-SCOPE.json').write_text(json.dumps({
            'schema': 'aclt.delivery-scope@2',
            'source_directories': [], 'top_level_files': ['sample'],
            'classification_order': ['tracked_exceptions', 'never_digest_patterns',
                                     'digest_patterns', 'delivery_only_patterns'],
            'tracked_exceptions': {}, 'never_digest_patterns': ['**/*.md'],
            'digest_patterns': ['sample'], 'delivery_only_patterns': ['docs/**']}))
        with patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(tracked_coverage(self.repo, [self.repo / 'sample']), 'PASS')
            with self.assertRaisesRegex(ValueError, 'outside delivery scope'):
                tracked_coverage(self.repo, [])
