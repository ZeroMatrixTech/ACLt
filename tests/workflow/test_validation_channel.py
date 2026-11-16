# SPDX-License-Identifier: Apache-2.0
"""Black-box tests for the validation channel classifier in validate.yml.

The classifier decides whether a pull request may take the documentation fast
path.  Ordinary changes confined to whitelisted paths can take the fast path:
a deletion, a rename (which ``--no-renames`` splits into a deletion plus an
addition), an empty diff, or any path outside the whitelist must fall back to
the full validation channel.  These tests extract the inline classifier script
from the workflow and run it against a throwaway git repository.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/validate.yml'
STEP = '- name: Classify validation channel'


def classify_script():
    """Return the inline classifier script of the workflow."""
    lines = WORKFLOW.read_text(encoding='utf-8').splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == STEP:
            start = index
            break
    if start is None:
        raise AssertionError('classify step not found in validate.yml')
    run = None
    for index in range(start, len(lines)):
        if lines[index].strip() == 'run: |':
            run = index
            break
    if run is None:
        raise AssertionError('classify run block not found in validate.yml')
    indent = len(lines[run]) - len(lines[run].lstrip())
    block = []
    for line in lines[run + 1:]:
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        block.append(line[indent + 2:] if len(line) > indent + 2 else '')
    return '\n'.join(block) + '\n'


@unittest.skipUnless(shutil.which('bash') and shutil.which('git'),
                     'requires bash and git')
class ValidationChannelTests(unittest.TestCase):
    """Run the workflow classifier against controlled git repositories."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.env = os.environ.copy()
        self.env.update({
            'GIT_CONFIG_GLOBAL': str(self.root / 'gitconfig'),
            'GIT_CONFIG_NOSYSTEM': '1',
            'HOME': str(self.root),
        })
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'docs').mkdir()
        (self.repo / 'scripts').mkdir()
        (self.repo / 'docs/a.md').write_text('# a\n', encoding='utf-8')
        (self.repo / 'README.md').write_text('# readme\n', encoding='utf-8')
        (self.repo / 'Makefile').write_text('check:\n\t@true\n', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.script = self.root / 'classify.sh'
        self.script.write_text(classify_script(), encoding='utf-8')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, check=True,
                              env=self.env, capture_output=True, text=True).stdout

    def channel(self, event='pull_request'):
        """Commit the current tree and return the classifier channel."""
        self.git('add', '-A')
        self.git('commit', '-q', '--allow-empty', '-m', 'case')
        output = self.root / 'github_output'
        output.write_text('', encoding='utf-8')
        env = self.env.copy()
        env.update({
            'EVENT_NAME': event,
            'BASE_SHA': self.base,
            'BASE_REF': 'main',
            'GITHUB_OUTPUT': str(output),
        })
        proc = subprocess.run(
            ['bash', '--noprofile', '--norc', '-eo', 'pipefail', str(self.script)],
            cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        values = dict(line.split('=', 1)
                      for line in output.read_text(encoding='utf-8').splitlines()
                      if '=' in line)
        return values.get('channel')

    def test_modified_whitelisted_markdown_takes_fast_path(self):
        (self.repo / 'docs/a.md').write_text('# changed\n', encoding='utf-8')
        self.assertEqual(self.channel(), 'fast')

    def test_modified_root_whitelist_file_takes_fast_path(self):
        (self.repo / 'README.md').write_text('# changed\n', encoding='utf-8')
        self.assertEqual(self.channel(), 'fast')

    def test_deleted_whitelisted_markdown_falls_back_to_full(self):
        (self.repo / 'docs/a.md').unlink()
        self.assertEqual(self.channel(), 'full')

    def test_renamed_whitelisted_markdown_falls_back_to_full(self):
        self.git('mv', 'docs/a.md', 'docs/b.md')
        self.assertEqual(self.channel(), 'full')

    def test_empty_diff_falls_back_to_full(self):
        self.assertEqual(self.channel(), 'full')

    def test_outside_whitelist_path_falls_back_to_full(self):
        (self.repo / 'scripts/x.py').write_text('x = 1\n', encoding='utf-8')
        self.assertEqual(self.channel(), 'full')

    def test_symlink_falls_back_to_full(self):
        (self.repo / 'docs/link.md').symlink_to('a.md')
        self.assertEqual(self.channel(), 'full')

    def test_non_pull_request_falls_back_to_full(self):
        (self.repo / 'docs/a.md').write_text('# changed\n', encoding='utf-8')
        self.assertEqual(self.channel('push'), 'full')


if __name__ == '__main__':
    unittest.main()
