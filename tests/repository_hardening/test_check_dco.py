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

    def test_fork_merge_commits_and_body_lines_do_not_count(self):
        base = self.commit("a", "base")
        self.git("checkout", "-q", "-b", "side")
        side = self.commit("s", f"side\n\nSigned-off-by: {AUTHOR[0]} <{AUTHOR[1]}>")
        self.git("checkout", "-q", "main")
        self.commit("m", f"main\n\nSigned-off-by: {AUTHOR[0]} <{AUTHOR[1]}>")
        self.git("merge", "-q", "--no-ff", "-m", "merge without sign-off", side)
        merge = self.git("rev-parse", "HEAD")
        result = self.run_check("pr", "--base", base, "--head", merge, "--fork", "true")
        self.assertEqual(result.returncode, 1)
        self.assertIn(merge[:12], result.stdout)
        body = self.commit("b", f"subject\n\nSigned-off-by: {AUTHOR[0]} <{AUTHOR[1]}> appears in prose\n\nnot a trailer block line")
        result = self.run_check("pr", "--base", merge, "--head", body, "--fork", "true")
        self.assertEqual(result.returncode, 1)
        self.assertIn(body[:12], result.stdout)

    def test_checker_reads_commits_from_a_separate_repository(self):
        base = self.commit("a", "base")
        head = self.commit("b", "unsigned")
        outside = tempfile.mkdtemp()
        try:
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo", str(self.dir), "pr",
                                     "--base", base, "--head", head, "--fork", "true"],
                                    cwd=outside, env=self.env, capture_output=True, text=True)
        finally:
            shutil.rmtree(outside)
        self.assertEqual(result.returncode, 1)
        self.assertIn(head[:12], result.stdout)

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


WORKFLOW = ROOT / ".github" / "workflows" / "dco.yml"


class DcoWorkflowTrustTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text()

    def step(self, name):
        lines = self.workflow.splitlines()
        start = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {name}")
        block = []
        for line in lines[start:]:
            if block and line.startswith("      - "):
                break
            block.append(line)
        return "\n".join(block)

    def run_commands(self):
        lines = self.workflow.splitlines()
        commands = []
        for i, line in enumerate(lines):
            if not line.lstrip().startswith("run:"):
                continue
            value = line.split("run:", 1)[1].strip()
            if value in ("|", ">"):
                indent = len(line) - len(line.lstrip())
                block = []
                for following in lines[i + 1:]:
                    if following.strip() and len(following) - len(following.lstrip()) <= indent:
                        break
                    block.append(following.strip())
                value = "\n".join(block).strip()
            commands.append(value)
        return commands

    def test_trusted_checkout_uses_the_target_commit(self):
        step = self.step("Checkout the trusted checker")
        refs = [line.strip() for line in step.splitlines() if line.strip().startswith("ref:")]
        self.assertEqual(refs, ["ref: ${{ github.sha }}"])
        self.assertIn("path: trusted", step)
        self.assertIn("persist-credentials: false", step)
        self.assertNotIn("if:", step)
        self.assertNotRegex(step, r"\$\{\{\s*github\.event")

    def test_pull_request_is_checked_out_as_data_only(self):
        self.assertEqual(self.workflow.count("uses: actions/checkout@"), 2)
        step = self.step("Checkout pull request commits as data")
        self.assertIn("if: github.event_name == 'pull_request_target'", step)
        self.assertIn("ref: refs/pull/${{ github.event.pull_request.number }}/head", step)
        self.assertIn("path: pr", step)
        self.assertIn("persist-credentials: false", step)
        self.assertNotIn("path: trusted", step)

        commands = self.run_commands()
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertRegex(command, r"^python3 -B trusted/scripts/check-dco\.py(?:\s|$)")
        self.assertNotIn("pr/", "\n".join(commands))
        self.assertNotIn("working-directory: pr", self.workflow)

    def test_header_explains_why_the_target_commit_is_trusted(self):
        header = self.workflow.split("on:", 1)[0]
        self.assertIn("github.sha", header)
        self.assertIn("not use github.event.pull_request.base.sha", header)


if __name__ == "__main__":
    unittest.main()
