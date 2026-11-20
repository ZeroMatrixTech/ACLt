"""Delivery membership checks with SHA consistency disabled."""
from pathlib import Path
import importlib.util
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from repository_files import (DIGEST, classify, delivery_files, policy,
                              refresh, tracked_coverage, verify)

MANIFEST = 'SINGLEHOST-SHA256SUMS'


def copy_ignore(directory, names):
    """Recreate a clean delivery tree without local build output or VCS data."""
    relative = Path(directory).relative_to(ROOT).as_posix()
    blocked = {'.git', 'target', '.toolchain', '__pycache__', 'dist'}
    if not relative.startswith('docs/workflow/example'):
        blocked.update({'build', 'artifacts'})
    if relative == '.aclt-flow':
        blocked.update({'runs', 'state.json', 'rules-status.json', 'lock'})
    return blocked.intersection(names)


def load_packager():
    spec = importlib.util.spec_from_file_location('package_singlehost',
                                                  ROOT / 'scripts/package-singlehost.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PACKAGER = load_packager()


def entry(name, data):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_STORED
    return info, data


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        shutil.copytree(ROOT, self.root, ignore=copy_ignore)
        refresh(self.root)
        self.archive = self.root / 'dist/aclt-singlehost-update.zip'

    def package(self, output=None):
        command = [sys.executable, '-B', str(self.root / 'scripts/package-singlehost.py')]
        if output is not None:
            command.append(str(output))
        return subprocess.run(command, capture_output=True, text=True)

    def expected_paths(self):
        return {path.relative_to(self.root).as_posix() for path in delivery_files(self.root)} | {MANIFEST}

    def digest_names(self):
        config = policy(self.root)
        return {path.relative_to(self.root).as_posix()
                for path in delivery_files(self.root)
                if classify(path.relative_to(self.root), config) == DIGEST}

    def markdown_names(self):
        return {path.relative_to(self.root).as_posix()
                for path in delivery_files(self.root) if path.suffix == '.md'}

    def rewritten(self, replace=None, drop=(), add=None):
        replace, add = replace or {}, add or {}
        target = self.root / 'dist/rewritten.zip'
        with zipfile.ZipFile(self.archive) as source, \
                zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED) as bundle:
            for info in source.infolist():
                if info.filename in drop:
                    continue
                bundle.writestr(info, replace.get(info.filename, source.read(info.filename)))
            for name, data in add.items():
                bundle.writestr(*entry(name, data))
        return target

    def test_archive_contains_every_delivery_file_and_the_manifest(self):
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(self.archive) as bundle:
            self.assertEqual(set(bundle.namelist()), self.expected_paths())
            for name in ['README.md', 'LICENSE', 'Makefile', 'docs/development.md',
                         'registries/verification-profile/mainnet_assurance.disabled.seed.json',
                         'experiments/aclt-multinode-admission/check.py',
                         'experiments/aclt-authority-admission/authority.py',
                         'experiments/aclt-authority-admission/run_vms.py',
                         'scripts/repository_files.py']:
                self.assertEqual(bundle.read(name), (self.root / name).read_bytes())

    def test_root_manifests_pin_no_markdown_but_markdown_is_delivered(self):
        self.assertEqual(self.package().returncode, 0)
        self.assertTrue(self.markdown_names())
        with zipfile.ZipFile(self.archive) as bundle:
            self.assertTrue(self.markdown_names() <= set(bundle.namelist()))
        self.assertEqual(refresh(self.root)['status'], 'DISABLED')
        for name in (MANIFEST, 'WORKFLOW-SHA256SUMS'):
            for line in (self.root / name).read_text().splitlines():
                self.assertFalse(line.split('  ', 1)[1].endswith('.md'), line)

    def test_markdown_edit_does_not_invalidate_manifest(self):
        for name in ('README.md', 'docs/development.md', 'CONTRIBUTING.md'):
            with (self.root / name).open('a', encoding='utf-8') as out:
                out.write('\nChanged without refreshing manifests\n')
        self.assertEqual(verify(self.root), [])
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_experiment_markdown_does_not_invalidate_any_manifest(self):
        for path in ('experiments/aclt-minimal-verifier-state3/README.md',
                     'experiments/aclt-multinode-admission/README.md',
                     'experiments/aclt-authority-admission/README.md'):
            with (self.root / path).open('a', encoding='utf-8') as out:
                out.write('\nChanged without refreshing any manifest\n')
        self.assertEqual(verify(self.root), [])
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_experiment_changes_leave_manifest_checks_disabled(self):
        cases = (
            ('experiments/aclt-minimal-verifier-state3/Cargo.toml',
             'experiments/aclt-minimal-verifier-state3/SHA256SUMS'),
            ('experiments/aclt-multinode-admission/check.py',
             'experiments/aclt-multinode-admission/SHA256SUMS'),
            ('experiments/aclt-authority-admission/authority.py',
             'experiments/aclt-authority-admission/SHA256SUMS'),
        )
        for relative, manifest in cases:
            path = self.root / relative
            before = path.read_bytes()
            try:
                path.write_bytes(before + b'\n')
                # The experiment manifest and the root manifest both pin this
                # file, so both must become stale together.
                self.assertEqual(verify(self.root), [])
            finally:
                path.write_bytes(before)

    def test_added_and_deleted_markdown_do_not_invalidate_manifest(self):
        (self.root / 'docs/new-note.md').write_text('# new\n', encoding='utf-8')
        (self.root / 'docs/workflow/README.md').unlink()
        self.assertEqual(verify(self.root), [])
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_change_packages_without_refreshing_sha_records(self):
        before = (self.root / MANIFEST).read_bytes()
        with (self.root / 'scripts/repository_files.py').open('a', encoding='utf-8') as out:
            out.write('\n# edited\n')
        self.assertEqual(verify(self.root), [])
        self.assertEqual(self.package().returncode, 0)
        self.assertEqual((self.root / MANIFEST).read_bytes(), before)
        self.assertTrue(self.archive.exists())

    def test_evidence_change_leaves_sha_checks_disabled(self):
        evidence = sorted((self.root / 'docs/testing').rglob('*.json'))[0]
        evidence.write_bytes(evidence.read_bytes() + b'\n')
        self.assertEqual(verify(self.root), [])

    def test_code_read_roadmap_input_is_pinned(self):
        # tools/migration_evidence.py reads this plan and its recorded hashes
        # decide check-migration-evidence, so it must never be delivery-only.
        relative = Path('docs/07-roadmap/fm-s3-audit-dependencies.json')
        self.assertEqual(classify(relative, policy(self.root)), DIGEST)
        self.assertIn(relative.as_posix(), self.digest_names())
        target = self.root / relative
        target.write_bytes(target.read_bytes() + b'\n')
        self.assertEqual(verify(self.root), [])

    def test_new_registration_leaves_sha_checks_disabled(self):
        (self.root / 'registries/verification-profile/new.json').write_text('{}')
        self.assertEqual(verify(self.root), [])

    def test_archive_source_bytes_are_not_sha_checked(self):
        self.assertEqual(self.package().returncode, 0)
        tampered = self.rewritten(replace={'scripts/repository_files.py': b'# tampered\n'})
        PACKAGER.verify_archive(tampered, self.root)

    def test_archive_markdown_bytes_are_not_consistency_checked(self):
        self.assertEqual(self.package().returncode, 0)
        tampered = self.rewritten(replace={'README.md': b'# different\n'})
        PACKAGER.verify_archive(tampered, self.root)

    def test_archive_extra_file_fails_verification(self):
        self.assertEqual(self.package().returncode, 0)
        tampered = self.rewritten(add={'notes.txt': b'extra\n'})
        with self.assertRaisesRegex(ValueError, 'outside delivery scope'):
            PACKAGER.verify_archive(tampered, self.root)

    def test_archive_missing_markdown_fails_verification(self):
        self.assertEqual(self.package().returncode, 0)
        tampered = self.rewritten(drop={'docs/development.md'})
        with self.assertRaisesRegex(ValueError, 'missing delivery files'):
            PACKAGER.verify_archive(tampered, self.root)

    def test_archive_missing_digest_file_fails_verification(self):
        self.assertEqual(self.package().returncode, 0)
        tampered = self.rewritten(drop={'scripts/repository_files.py'})
        with self.assertRaisesRegex(ValueError, 'missing delivery files'):
            PACKAGER.verify_archive(tampered, self.root)

    def test_archive_sha_record_bytes_are_not_checked(self):
        self.assertEqual(self.package().returncode, 0)
        tampered = self.rewritten(replace={MANIFEST: b''})
        PACKAGER.verify_archive(tampered, self.root)

    def test_archive_bytes_ignore_wall_clock_and_file_mtimes(self):
        first = self.package(); self.assertEqual(first.returncode, 0, first.stderr)
        expected = self.archive.read_bytes()
        import os
        for path in (self.root / 'tools').rglob('*.py'):
            os.utime(path, (1000000000, 1000000000))
        other = self.root / 'dist/second.zip'
        result = subprocess.run([sys.executable, '-B', str(self.root / 'scripts/package-singlehost.py'), str(other)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(other.read_bytes(), expected)
        with zipfile.ZipFile(other) as bundle:
            self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0)
                                and info.compress_type == zipfile.ZIP_STORED
                                for info in bundle.infolist()))
            self.assertNotIn('AGENTS.md', bundle.namelist())
            self.assertFalse(any(name.startswith('.claude/') for name in bundle.namelist()))
            self.assertTrue(any(name.startswith('docs/codocs/') for name in bundle.namelist()))
            self.assertIn('.github/workflows/validate.yml', bundle.namelist())

    def test_existing_archive_is_never_replaced(self):
        self.assertEqual(self.package().returncode, 0)
        before = self.archive.read_bytes()
        self.assertNotEqual(self.package().returncode, 0)
        self.assertEqual(self.archive.read_bytes(), before)

    def test_symlinked_input_is_not_bundled(self):
        secret = Path(self.temp.name) / 'external'
        secret.write_text('must not be delivered')
        (self.root / 'registries/linked.json').symlink_to(secret)
        self.assertNotEqual(self.package().returncode, 0)
        self.assertFalse(self.archive.exists())


class GitCheckoutDeliveryTests(unittest.TestCase):
    """A Git checkout must not package an incomplete delivery set."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        shutil.copytree(ROOT, self.root, ignore=copy_ignore)
        refresh(self.root)
        self.archive = self.root / 'dist/aclt-singlehost-update.zip'
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'base')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args],
                              capture_output=True, text=True)

    def package(self):
        return subprocess.run([sys.executable, '-B', str(self.root / 'scripts/package-singlehost.py')],
                              capture_output=True, text=True)

    def test_missing_tracked_delivery_file_fails_package(self):
        (self.root / 'docs/workflow/README.md').unlink()
        result = self.package()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing from the working tree', result.stderr)
        self.assertFalse(self.archive.exists())

    def test_manifest_command_reports_disabled_even_with_missing_file(self):
        (self.root / 'docs/development.md').unlink()
        result = subprocess.run([sys.executable, '-B', str(self.root / 'scripts/update-manifests.py'),
                                 '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('DISABLED', result.stdout)

    def test_git_removed_delivery_file_is_not_required(self):
        # Assert against the delivery set at test start, never a fixed count:
        # a legitimate Markdown addition or removal must not fail this case.
        removed_path = 'docs/workflow/README.md'
        expected = {path.relative_to(self.root).as_posix() for path in delivery_files(self.root)}
        removed = self.git('rm', '-q', removed_path)
        self.assertEqual(removed.returncode, 0, removed.stderr)
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(self.archive) as bundle:
            names = set(bundle.namelist())
        self.assertNotIn(removed_path, names)
        self.assertEqual(names, (expected - {removed_path}) | {MANIFEST})


class ClassificationTests(unittest.TestCase):
    """Rule-driven classification must fail closed outside the policy."""

    def repo(self, top_level):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        subprocess.run(['git', 'init', '-q', str(directory)], check=True)
        (directory / 'DELIVERY-SCOPE.json').write_text(json.dumps({
            'schema': 'aclt.delivery-scope@2',
            'source_directories': [],
            'top_level_files': top_level,
            'classification_order': ['tracked_exceptions', 'never_digest_patterns',
                                     'digest_patterns', 'delivery_only_patterns'],
            'tracked_exceptions': {},
            'never_digest_patterns': ['**/*.md'],
            'digest_patterns': ['DELIVERY-SCOPE.json'],
            'delivery_only_patterns': ['docs/**'],
        }))
        return directory

    def add(self, directory, *names):
        for name in names:
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('x\n')
        subprocess.run(['git', '-C', str(directory), 'add', 'DELIVERY-SCOPE.json', *names],
                       check=True)

    def test_tracked_path_outside_delivery_scope_fails(self):
        directory = self.repo(['DELIVERY-SCOPE.json'])
        self.add(directory, 'notes.txt')
        with self.assertRaisesRegex(ValueError, 'outside delivery scope'):
            tracked_coverage(directory)

    def test_delivery_path_outside_rules_fails_closed(self):
        directory = self.repo(['DELIVERY-SCOPE.json', 'extra.txt'])
        self.add(directory, 'extra.txt')
        with self.assertRaisesRegex(ValueError, 'Unclassified tracked delivery paths: extra.txt'):
            tracked_coverage(directory)


if __name__ == '__main__':
    unittest.main()
