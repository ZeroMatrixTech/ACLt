# SPDX-License-Identifier: Apache-2.0
"""Regression tests for scripts/check-dco.py on a throwaway Git repository.

The pull request check receives its untrusted input the way the workflow does:
in the PR_BODY environment variable named by --body-env.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-dco.py"
MAINTAINERS = ROOT / ".github" / "dco-maintainers.txt"
AUTHOR = ("Example Author", "author@example.invalid")
AGENT = ("inPac", "tenneidp@gmail.com")
SIGNOFF = "Signed-off-by: inpac <inpac@lingmatrix.cn>"
UNKNOWN_SIGNOFF = "Signed-off-by: Someone Else <other@example.invalid>"


class DcoTestCase(unittest.TestCase):
    """A throwaway repository plus the checker under test."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.temporary = []
        self.env = dict(os.environ, GIT_AUTHOR_NAME=AUTHOR[0], GIT_AUTHOR_EMAIL=AUTHOR[1],
                        GIT_COMMITTER_NAME=AUTHOR[0], GIT_COMMITTER_EMAIL=AUTHOR[1],
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        self.env.pop("PR_BODY", None)
        self.git("init", "-q", "-b", "main")

    def tearDown(self):
        shutil.rmtree(self.dir)
        for path in self.temporary:
            shutil.rmtree(path, ignore_errors=True)
        self.temporary = []

    def git(self, *args, author=AUTHOR):
        env = dict(self.env, GIT_AUTHOR_NAME=author[0], GIT_AUTHOR_EMAIL=author[1],
                   GIT_COMMITTER_NAME=author[0], GIT_COMMITTER_EMAIL=author[1])
        return subprocess.run(["git", *args], cwd=self.dir, env=env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, name, message, with_script=False, author=AUTHOR):
        (self.dir / name).write_text(name + "\n")
        self.git("add", name)
        if with_script:
            target = self.dir / "scripts" / "check-dco.py"
            target.parent.mkdir(exist_ok=True)
            target.write_text(SCRIPT.read_text())
            self.git("add", "scripts/check-dco.py")
        self.git("commit", "-q", "-m", message, author=author)
        return self.git("rev-parse", "HEAD")

    def trusted_checkout(self, maintainers=None, with_list=True):
        """A trusted checkout holding the script and a maintainer list."""
        root = Path(tempfile.mkdtemp())
        self.temporary.append(root)
        (root / "scripts").mkdir()
        (root / "scripts" / "check-dco.py").write_text(SCRIPT.read_text())
        if with_list:
            (root / ".github").mkdir()
            (root / ".github" / "dco-maintainers.txt").write_text(
                MAINTAINERS.read_text() if maintainers is None else maintainers)
        return root / "scripts" / "check-dco.py"

    def pr(self, base, head, fork, body=None, script=None):
        environment = dict(self.env)
        if body is None:
            environment.pop("PR_BODY", None)
        else:
            environment["PR_BODY"] = body
        return subprocess.run(
            [sys.executable, "-B", str(script or SCRIPT), "--repo", str(self.dir), "pr",
             "--base", base, "--head", head, "--fork", fork, "--body-env", "PR_BODY"],
            cwd=self.dir, env=environment, capture_output=True, text=True)

    def push(self, before, after):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--repo", str(self.dir), "push",
             "--before", before, "--after", after],
            cwd=self.dir, env=self.env, capture_output=True, text=True)


class PullRequestBodyTests(DcoTestCase):
    def agent_pr(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=AGENT)
        return base, head

    def test_signed_final_paragraph_passes(self):
        base, head = self.agent_pr()
        result = self.pr(base, head, "false", "Change: x\n\n" + SIGNOFF)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("signed off by inpac <inpac@lingmatrix.cn>", result.stdout)

    def test_missing_signoff_fails(self):
        base, head = self.agent_pr()
        result = self.pr(base, head, "false", "Change: x")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no Signed-off-by trailer in its last paragraph", result.stdout)

    def test_signoff_in_the_middle_of_the_body_fails(self):
        base, head = self.agent_pr()
        body = "Change: x\n\n" + SIGNOFF + "\n\nmore prose after the trailer block"
        result = self.pr(base, head, "false", body)
        self.assertEqual(result.returncode, 1)
        self.assertIn("no Signed-off-by trailer", result.stdout)

    def test_patch_separator_before_the_signoff_fails_and_says_why(self):
        base, head = self.agent_pr()
        body = "Change: x\n\n---\n\n" + SIGNOFF
        result = self.pr(base, head, "false", body)
        self.assertEqual(result.returncode, 1)
        self.assertIn("---", result.stdout)
        self.assertIn("patch", result.stdout)

    def test_signoff_before_the_patch_separator_still_passes(self):
        base, head = self.agent_pr()
        body = "Change: x\n\n" + SIGNOFF + "\n\n---\n\ndiff --git a/x b/x\n"
        result = self.pr(base, head, "false", body)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_crlf_and_lf_are_judged_identically(self):
        base, head = self.agent_pr()
        for text in ("Change: x\n\n" + SIGNOFF, "Change: x"):
            with self.subTest(text=text):
                lf = self.pr(base, head, "false", text)
                crlf = self.pr(base, head, "false", text.replace("\n", "\r\n"))
                self.assertEqual(lf.returncode, crlf.returncode)
                self.assertEqual(lf.stdout, crlf.stdout)

    def test_the_last_trailer_paragraph_is_the_one_that_counts(self):
        base, head = self.agent_pr()
        signed_then_reviewed = "Change: x\n\n" + SIGNOFF + "\n\nReviewed-by: R <r@example.invalid>"
        self.assertEqual(self.pr(base, head, "false", signed_then_reviewed).returncode, 1)
        reviewed_then_signed = "Change: x\n\nReviewed-by: R <r@example.invalid>\n\n" + SIGNOFF
        self.assertEqual(self.pr(base, head, "false", reviewed_then_signed).returncode, 0)

    def test_signed_body_without_a_trailing_newline_passes(self):
        base, head = self.agent_pr()
        result = self.pr(base, head, "false", "Change: x\n\n" + SIGNOFF)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.pr(base, head, "false", "Change: x\n\n" + SIGNOFF + "\n").returncode, 0)

    def test_signer_outside_the_list_fails(self):
        base, head = self.agent_pr()
        result = self.pr(base, head, "false", "Change: x\n\n" + UNKNOWN_SIGNOFF)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a maintainer sign-off identity", result.stdout)

    def test_empty_body_fails(self):
        base, head = self.agent_pr()
        result = self.pr(base, head, "false", "")
        self.assertEqual(result.returncode, 1)
        self.assertIn("body is empty", result.stdout)

    def test_missing_environment_variable_fails_closed(self):
        base, head = self.agent_pr()
        result = self.pr(base, head, "false", None)
        self.assertEqual(result.returncode, 1)
        self.assertIn("body is empty", result.stdout)

    def test_body_characters_are_text_and_never_execute(self):
        base, head = self.agent_pr()
        marker = self.dir / "injected"
        body = ("Change: x\n\n$(touch {m})\n`touch {m}`\n${{{B}}} github.token {{{B}}}\n\n"
                .format(m=marker, B="{") + SIGNOFF)
        result = self.pr(base, head, "false", body)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(marker.exists(), "the body was executed")

    def test_trusted_list_judges_the_pull_request(self):
        base, head = self.agent_pr()
        pr_list = self.dir / ".github" / "dco-maintainers.txt"
        pr_list.parent.mkdir(exist_ok=True)
        pr_list.write_text("signoff attacker <attacker@example.invalid>\n")
        body = "Change: x\n\nSigned-off-by: attacker <attacker@example.invalid>"
        with_real_list = self.pr(base, head, "false", body)
        self.assertEqual(with_real_list.returncode, 1)
        # The same body passes once the trusted checkout lists the signer, which
        # proves the verdict follows the trusted list rather than the PR copy.
        trusted = self.trusted_checkout("signoff attacker <attacker@example.invalid>\n"
                                        "author inPac <tenneidp@gmail.com>\n")
        with_pr_list = self.pr(base, head, "false", body, script=trusted)
        self.assertEqual(with_pr_list.returncode, 0, with_pr_list.stdout)


class PullRequestTemplateTests(DcoTestCase):
    def test_template_alone_fails_and_with_the_maintainer_signoff_passes(self):
        template = (ROOT / ".github" / "pull_request_template.md").read_text()
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent", author=AGENT)
        alone = self.pr(base, head, "false", template)
        self.assertEqual(alone.returncode, 1, alone.stdout)
        signed = self.pr(base, head, "false", template + "\n\n" + SIGNOFF)
        self.assertEqual(signed.returncode, 0, signed.stdout)


class MaintainerListTests(DcoTestCase):
    def test_malformed_entry_fails_closed(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent", author=AGENT)
        trusted = self.trusted_checkout("signoff no-address-here\n")
        result = self.pr(base, head, "false", "Change: x\n\n" + SIGNOFF, script=trusted)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected 'name <e-mail>'", result.stderr)

    def test_missing_list_fails_closed(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent", author=AGENT)
        trusted = self.trusted_checkout(with_list=False)
        result = self.pr(base, head, "false", "Change: x\n\n" + SIGNOFF, script=trusted)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot read the maintainer list", result.stderr)

    def test_list_without_a_signoff_identity_fails_closed(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent", author=AGENT)
        trusted = self.trusted_checkout("author inPac <tenneidp@gmail.com>\n")
        result = self.pr(base, head, "false", "Change: x\n\n" + SIGNOFF, script=trusted)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no signoff identity", result.stderr)

    def test_repository_list_keeps_the_initial_identities(self):
        text = MAINTAINERS.read_text()
        self.assertIn("signoff inpac <inpac@lingmatrix.cn>", text)
        self.assertIn("author inPac <tenneidp@gmail.com>", text)


class SameRepositoryCommitTests(DcoTestCase):
    def body(self):
        return "Change: x\n\n" + SIGNOFF

    def test_maintainer_identity_commits_need_no_signoff(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=AGENT)
        result = self.pr(base, head, "false", self.body())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("authored by a maintainer identity", result.stdout)

    def test_author_match_is_case_insensitive(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=("InPac", "Tenneidp@Gmail.com"))
        self.assertEqual(self.pr(base, head, "false", self.body()).returncode, 0)

    def test_other_author_commit_needs_a_matching_signoff(self):
        base = self.commit("a", "base", author=AGENT)
        unsigned = self.commit("b", "outside work", author=AUTHOR)
        result = self.pr(base, unsigned, "false", self.body())
        self.assertEqual(result.returncode, 1)
        self.assertIn(AUTHOR[1], result.stdout)
        signed = self.commit("c", "outside work signed\n\nSigned-off-by: {0} <{1}>".format(*AUTHOR),
                             author=AUTHOR)
        result = self.pr(unsigned, signed, "false", self.body())
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_merge_commit_by_a_non_maintainer_author_needs_a_signoff(self):
        base = self.commit("a", "base", author=AGENT)
        self.git("checkout", "-q", "-b", "side")
        self.commit("s", "side", author=AUTHOR)
        self.git("checkout", "-q", "main")
        self.commit("m", "main", author=AGENT)
        self.git("merge", "-q", "--no-ff", "-m", "merge without sign-off", "side", author=AUTHOR)
        merge = self.git("rev-parse", "HEAD")
        result = self.pr(base, merge, "false", self.body())
        self.assertEqual(result.returncode, 1)
        self.assertIn(merge[:12], result.stdout)


class ForkCommitTests(DcoTestCase):
    def body(self):
        return "Change: x\n\n" + SIGNOFF

    def test_fork_pull_request_requires_matching_signoff(self):
        base = self.commit("a", "base")
        good = self.commit("b", "good\n\nSigned-off-by: {0} <{1}>".format(*AUTHOR))
        self.assertEqual(self.pr(base, good, "true", self.body()).returncode, 0)
        other = self.commit("c", "other\n\nSigned-off-by: Someone Else <other@example.invalid>")
        result = self.pr(base, other, "true", self.body())
        self.assertEqual(result.returncode, 1)
        self.assertIn(other[:12], result.stdout)
        unsigned = self.commit("d", "unsigned")
        self.assertEqual(self.pr(base, unsigned, "true", self.body()).returncode, 1)

    def test_fork_merge_commits_and_body_lines_do_not_count(self):
        base = self.commit("a", "base")
        self.git("checkout", "-q", "-b", "side")
        side = self.commit("s", "side\n\nSigned-off-by: {0} <{1}>".format(*AUTHOR))
        self.git("checkout", "-q", "main")
        self.commit("m", "main\n\nSigned-off-by: {0} <{1}>".format(*AUTHOR))
        self.git("merge", "-q", "--no-ff", "-m", "merge without sign-off", side)
        merge = self.git("rev-parse", "HEAD")
        result = self.pr(base, merge, "true", self.body())
        self.assertEqual(result.returncode, 1)
        self.assertIn(merge[:12], result.stdout)
        text = "subject\n\nSigned-off-by: {0} <{1}> appears in prose\n\nnot a trailer block line"
        body = self.commit("b", text.format(*AUTHOR))
        result = self.pr(base, body, "true", self.body())
        self.assertEqual(result.returncode, 1)
        self.assertIn(body[:12], result.stdout)

    def test_fork_commits_by_a_maintainer_identity_still_need_a_signoff(self):
        base = self.commit("a", "base", author=AGENT)
        unsigned = self.commit("b", "agent fork work", author=AGENT)
        self.assertEqual(self.pr(base, unsigned, "true", self.body()).returncode, 1)
        signed = self.commit("c", "agent fork work\n\nSigned-off-by: {0} <{1}>".format(*AGENT),
                             author=AGENT)
        self.assertEqual(self.pr(unsigned, signed, "true", self.body()).returncode, 0)

    def test_checker_reads_commits_from_a_separate_repository(self):
        base = self.commit("a", "base")
        head = self.commit("b", "unsigned")
        outside = tempfile.mkdtemp()
        self.temporary.append(Path(outside))
        environment = dict(self.env, PR_BODY=self.body())
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--repo", str(self.dir), "pr",
                                 "--base", base, "--head", head, "--fork", "true",
                                 "--body-env", "PR_BODY"],
                                cwd=outside, env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(head[:12], result.stdout)


class PushTests(DcoTestCase):
    def test_push_checks_only_commits_after_adoption(self):
        old = self.commit("a", "history before DCO")
        adopt = self.commit("b", "adopt DCO check", with_script=True)
        # The adoption commit's parent lacks the script, so it is not checked.
        self.assertEqual(self.push(old, adopt).returncode, 0)
        signed = self.commit("c", "merge\n\n" + SIGNOFF)
        self.assertEqual(self.push(adopt, signed).returncode, 0)
        unsigned = self.commit("d", "merge without sign-off")
        result = self.push(signed, unsigned)
        self.assertEqual(result.returncode, 1)
        self.assertIn(unsigned[:12], result.stdout)

    def test_body_check_and_push_check_parse_the_same_text(self):
        # Only the parsing is shared: the body must also be signed by a
        # maintainer identity, while the push fallback accepts any sign-off.
        cases = {
            "signed": "Change: x\n\n" + SIGNOFF,
            "unsigned": "Change: x",
            "separator": "Change: x\n\n---\n\n" + SIGNOFF,
            "middle": "Change: x\n\n" + SIGNOFF + "\n\nmore prose",
            "crlf": "Change: x\r\n\r\n" + SIGNOFF + "\r\n",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.tearDown()
                self.setUp()
                base = self.commit("a", "base", author=AGENT)
                head = self.commit("b", "agent", author=AGENT)
                body_verdict = self.pr(base, head, "false", text).returncode
                adopt = self.commit("c", "adopt DCO check", with_script=True, author=AGENT)
                target = self.commit("d", text, author=AGENT)
                push_verdict = self.push(adopt, target).returncode
                self.assertEqual(body_verdict, push_verdict, name)


class DcoWorkflowTrustTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github" / "workflows" / "dco.yml").read_text()

    def step(self, name):
        lines = self.workflow.splitlines()
        start = next(i for i, line in enumerate(lines) if line.strip() == "- name: " + name)
        block = []
        for line in lines[start:]:
            if block and line.startswith("      - "):
                break
            block.append(line)
        return "\n".join(block)

    def run_blocks(self):
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

        commands = self.run_blocks()
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertRegex(command, r"^python3 -B trusted/scripts/check-dco\.py(?:\s|$)")
        self.assertNotIn("pr/", "\n".join(commands))
        self.assertNotIn("working-directory: pr", self.workflow)

    def test_body_arrives_through_an_environment_variable_only(self):
        step = self.step("Check pull request sign-offs")
        self.assertIn("PR_BODY: ${{ github.event.pull_request.body }}", step)
        self.assertIn("--body-env PR_BODY", step)
        self.assertNotRegex(self.workflow, r"pull_request\.(title|head\.ref)")
        self.assertNotIn("$GITHUB_ENV", self.workflow)
        self.assertNotIn("$GITHUB_OUTPUT", self.workflow)
        for command in self.run_blocks():
            self.assertNotIn("${{", command, command)
            self.assertNotIn("PR_BODY", command.replace("--body-env PR_BODY", ""), command)

    def test_an_edited_body_reruns_the_check(self):
        self.assertRegex(self.workflow,
                         r"pull_request_target:\n    types: \[[^\]]*\bedited\b[^\]]*\]")
        self.assertIn("group: dco-${{ github.event.pull_request.number || github.ref }}",
                      self.workflow)
        self.assertIn("cancel-in-progress: true", self.workflow)

    def test_header_explains_the_trust_boundary(self):
        header = self.workflow.split("on:", 1)[0]
        self.assertIn("github.sha", header)
        self.assertIn("not use github.event.pull_request.base.sha", header)
        self.assertIn("dco-maintainers.txt", header)
        self.assertIn("GITHUB_ENV", header)


if __name__ == "__main__":
    unittest.main()
