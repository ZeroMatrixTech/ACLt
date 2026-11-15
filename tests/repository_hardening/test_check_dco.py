# SPDX-License-Identifier: Apache-2.0
"""Regression tests for scripts/check-dco.py on a throwaway Git repository."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-dco.py"
AUTHOR = ("Example Author", "author@example.invalid")


class CheckDcoTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.env = dict(os.environ, GIT_AUTHOR_NAME=AUTHOR[0], GIT_AUTHOR_EMAIL=AUTHOR[1],
                        GIT_COMMITTER_NAME=AUTHOR[0], GIT_COMMITTER_EMAIL=AUTHOR[1],
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        self.git("init", "-q", "-b", "main")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, name, message, with_script=False):
        (self.dir / name).write_text(name + "\n")
        self.git("add", name)
        if with_script:
            target = self.dir / "scripts" / "check-dco.py"
            target.parent.mkdir(exist_ok=True)
            target.write_text(SCRIPT.read_text())
            self.git("add", "scripts/check-dco.py")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_check(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=self.dir,
                              env=self.env, capture_output=True, text=True)

    def test_fork_pull_request_requires_matching_signoff(self):
        base = self.commit("a", "base")
        good = self.commit("b", f"good\n\nSigned-off-by: {AUTHOR[0]} <{AUTHOR[1]}>")
        self.assertEqual(self.run_check("pr", "--base", base, "--head", good, "--fork", "true").returncode, 0)
        other = self.commit("c", "other\n\nSigned-off-by: Someone Else <other@example.invalid>")
        result = self.run_check("pr", "--base", base, "--head", other, "--fork", "true")
        self.assertEqual(result.returncode, 1)
        self.assertIn(other[:12], result.stdout)
        unsigned = self.commit("d", "unsigned")
        self.assertEqual(self.run_check("pr", "--base", good, "--head", unsigned, "--fork", "true").returncode, 1)

    def test_same_repository_pull_request_is_signed_at_merge(self):
        base = self.commit("a", "base")
        head = self.commit("b", "agent commit without sign-off")
        result = self.run_check("pr", "--base", base, "--head", head, "--fork", "false")
        self.assertEqual(result.returncode, 0)
        self.assertIn("maintainer signs", result.stdout)

    def test_push_checks_only_commits_after_adoption(self):
        old = self.commit("a", "history before DCO")
        adopt = self.commit("b", "adopt DCO check", with_script=True)
        # The adoption commit's parent lacks the script, so it is not checked.
        self.assertEqual(self.run_check("push", "--before", old, "--after", adopt).returncode, 0)
        signed = self.commit("c", f"merge\n\nSigned-off-by: {AUTHOR[0]} <{AUTHOR[1]}>")
        self.assertEqual(self.run_check("push", "--before", adopt, "--after", signed).returncode, 0)
        unsigned = self.commit("d", "merge without sign-off")
        result = self.run_check("push", "--before", signed, "--after", unsigned)
        self.assertEqual(result.returncode, 1)
        self.assertIn(unsigned[:12], result.stdout)


if __name__ == "__main__":
    unittest.main()
