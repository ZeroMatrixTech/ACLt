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
SIGNOFF_ANKAR = "Signed-off-by: Ankar <ankarnassia@lingmatrix.cn>"
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
        self.assertIn("not a sign-off identity", result.stdout)

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
        trusted = self.trusted_checkout("signoff attacker <attacker@example.invalid>\n")
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
        self.assertIn("cannot read the sign-off list", result.stderr)

    def test_list_without_a_signoff_identity_fails_closed(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent", author=AGENT)
        trusted = self.trusted_checkout("# no identities yet\n")
        result = self.pr(base, head, "false", "Change: x\n\n" + SIGNOFF, script=trusted)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no signoff identity", result.stderr)

    def test_author_role_is_unknown(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=AGENT)
        trusted = self.trusted_checkout("signoff inpac <inpac@lingmatrix.cn>\n"
                                        "author inPac <tenneidp@gmail.com>\n")
        result = self.pr(base, head, "false", "Change: x\n\n" + SIGNOFF, script=trusted)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown role 'author'; expected signoff", result.stderr)

    def test_repository_list_keeps_the_initial_identities(self):
        text = MAINTAINERS.read_text()
        self.assertIn("signoff inpac <inpac@lingmatrix.cn>", text)

    def test_repository_list_carries_the_authorised_collaborator(self):
        text = MAINTAINERS.read_text()
        self.assertIn("signoff Ankar <ankarnassia@lingmatrix.cn>", text)

    def test_repository_list_registers_signers_only(self):
        entries = [line for line in MAINTAINERS.read_text().splitlines()
                   if line.strip() and not line.strip().startswith("#")]
        self.assertEqual(len(entries), 2)
        for line in entries:
            self.assertTrue(line.startswith("signoff "), line)

    def test_two_signoff_identities_either_may_sign_the_body(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=AGENT)
        trusted = self.trusted_checkout(
            "signoff inpac <inpac@lingmatrix.cn>\n"
            "signoff Ankar <ankarnassia@lingmatrix.cn>\n")
        for signoff, signer in ((SIGNOFF, "inpac <inpac@lingmatrix.cn>"),
                                (SIGNOFF_ANKAR, "Ankar <ankarnassia@lingmatrix.cn>")):
            with self.subTest(signer=signer):
                result = self.pr(base, head, "false", "Change: x\n\n" + signoff, script=trusted)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn("signed off by " + signer, result.stdout)


class SameRepositoryCommitTests(DcoTestCase):
    """A branch pull request is confirmed by the body sign-off; commits are not
    inspected, whatever their authors are."""

    def body(self, signoff=SIGNOFF):
        return "Change: x\n\n" + signoff

    def test_commits_of_any_author_need_no_per_commit_signoff(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=("dsh", "dsh@localhost"))
        for signoff in (SIGNOFF, SIGNOFF_ANKAR):
            with self.subTest(signoff=signoff):
                result = self.pr(base, head, "false", self.body(signoff))
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn("same-repository pull request", result.stdout)

    def test_commit_by_an_outside_author_passes(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "outside work", author=AUTHOR)
        self.assertEqual(self.pr(base, head, "false", self.body()).returncode, 0)

    def test_merge_commit_by_an_outside_author_passes(self):
        base = self.commit("a", "base", author=AGENT)
        self.git("checkout", "-q", "-b", "side")
        self.commit("s", "side", author=("dsh", "dsh@localhost"))
        self.git("checkout", "-q", "main")
        self.commit("m", "main", author=AGENT)
        self.git("merge", "-q", "--no-ff", "-m", "merge without sign-off", "side", author=AUTHOR)
        merge = self.git("rev-parse", "HEAD")
        self.assertEqual(self.pr(base, merge, "false", self.body()).returncode, 0)

    def test_an_unsigned_body_still_fails(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=("dsh", "dsh@localhost"))
        self.assertEqual(self.pr(base, head, "false", "Change: x").returncode, 1)


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
        # Only the parsing is shared: the body must also be signed by a listed
        # sign-off identity, while the push fallback accepts any sign-off.
        cases = {
            "signed": "Change: x\n\n" + SIGNOFF,
            "unsigned": "Change: x",
            "separator": "Change: x\n\n---\n\n" + SIGNOFF,
            "middle": "Change: x\n\n" + SIGNOFF + "\n\nmore prose",
            "crlf": "Change: x\r\n\r\n" + SIGNOFF + "\r\n",
            "coauthor suffix": "Change: x\n\n" + SIGNOFF + "\n\n---------\n\n"
                               "Co-authored-by: dsh <dsh@localhost>",
            "coauthor suffix, two authors": "Change: x\n\n" + SIGNOFF + "\n\n---------\n\n"
                                            "Co-authored-by: dsh <dsh@localhost>\n"
                                            "Co-authored-by: R <r@example.invalid>",
            "coauthor suffix, eight dashes": "Change: x\n\n" + SIGNOFF + "\n\n--------\n\n"
                                             "Co-authored-by: dsh <dsh@localhost>",
            "coauthor suffix, extra trailer": "Change: x\n\n" + SIGNOFF + "\n\n---------\n\n"
                                              "Reviewed-by: R <r@example.invalid>\n"
                                              "Co-authored-by: dsh <dsh@localhost>",
            "coauthor suffix, unsigned above": "Change: x\n\n---------\n\n"
                                               "Co-authored-by: dsh <dsh@localhost>",
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


# The squash message of ece86b5 on main, copied verbatim from
# "git log -1 --format=%B ece86b5" on 2026-11-18.  GitHub appended that
# separator and Co-authored-by block after the maintainer's sign-off, so the
# push check read only the appended block and reported
# "FAIL: ece86b536bef on main has no Signed-off-by trailer".  Keep the text
# byte-for-byte identical: it is the fixture for that failure.
ECE86B5_MESSAGE = """docs: archive the post-release closure recheck (AUD-20261118-01) (#201)

<!-- PARALLEL-1：docs/08-governance/parallel-workflow.md。不要写入凭据、真实
IP、用户名或本地路径。 -->

Closes #200

Refs #128

## 条目与基线

- Issue：#200（归档 AUD-20261118-01，阶段 #128 关闭前的最后一项收尾）
- 分支：`docs/archive-aud-20261118-01`
- 基线：`5b3bc9a065b8c78561d67a76ee6694b2f2de5079`（开分支时）；已按 PARALLEL-1 §5.4
合并 `origin/main` `203249dee46336181d682fd0fb894194669afdd3`（P1-p #203）
- 实现代理：dsh；审计按计划卡不再另开一轮，只归档原报告
- 提交：`0cd1542`（归档与索引）、`69deb44`（同步 main）、`d54392c`（PRA-201-02 修复）
- 同步只解一处冲突：`docs/07-roadmap/current-status.md` §9 表头下两行并存，P1-p
在上、AUD-20261118-01 在下

## Change

### 归档与索引（`0cd1542`）

- 新增
`docs/08-governance/audits/audit-20261118-01-post-release-closure.md`：Codex
交付件逐字节复制，33,272 字节，SHA-256
`9829ff904f71e262fcb004d839dc5f5a9995a437a61fbf9b0da7d627d21cf194`，`cmp`
退出 0；内容、结论与失败证据保持原文。报告里没有指向仓库外本机路径的链接（本地路径只以纯文本出现在 §1 与
§10），未触发计划卡允许的唯一改写。
- `docs/08-governance/audits/README.md`：接 AUD-20261116-02/03 那一段之后新增一段：

> 2026-11-18 的阶段 #128 发布后收尾回验见
[AUD-20261118-01](audit-20261118-01-post-release-closure.md)。报告按原字节归档，保留原结论、发现与失败证据；它不是
PR 审计，也不是 Gate 退出审计。本轮新增 0 BLOCKER、1 MAJOR（现为
`ACCEPTED_BY_MAINTAINER`）、0 MINOR，未处理 OPEN 为
0；报告结论为已无未处理的关闭阻断，本报告归档并加入索引后 #128 可由维护者关闭。

- `docs/README.md`：接 :295（AUD-20261116-03）之后新增一条：

> [2026-11-18 阶段 #128
发布后收尾回验（AUD-20261118-01）](08-governance/audits/audit-20261118-01-post-release-closure.md)：新增
0 BLOCKER、1 MAJOR（现为 `ACCEPTED_BY_MAINTAINER`）、0 MINOR，未处理 OPEN 为
0；已无未处理的关闭阻断，本报告归档并加入索引后 #128 可由维护者关闭。

- `docs/07-roadmap/current-status.md`（热点文件）：§9 新增一行，只转述归档事实、结论与计数，Gate
栏“不变”。

### 归档字节与文档门禁的兼容（`d54392c`，PRA-201-02）

- 新增 `docs/08-governance/audits/.gitattributes`：对 `audit-*.md` 声明
`whitespace=-blank-at-eol`。归档报告是原字节记录，P1-k 之后文档通道无条件运行 `git diff
--check`，保留交付件的 Markdown 硬换行会确定性地让 `local-validation`
失败；这条仓库规则只豁免归档副本，同目录的索引与后续人工撰写的文件仍按默认检查。
- `scripts/check-license-coverage.py`：把 `.gitattributes` 加入
`CONFIG_NAMES`（与 `.gitignore` 同类），文件头的类别列表同步。该文件带 SPDX 头，按配置类受检查。
- `tests/workflow/test_license_coverage.py`：新增
`test_gitattributes_is_covered_and_declarable`，与 `.gitignore` 的既有用例同构。
- `docs/07-roadmap/open-questions.md`：OQ-01“关闭证据”补一句，记录 `.gitattributes`
纳入配置类及其用途。
- `SINGLEHOST-SHA256SUMS`、`WORKFLOW-SHA256SUMS`：脚本与测试是钉住文件，按
`update-manifests.py` 刷新。

## Problem / counterexample

- 阶段 #128 的发布后收尾回验只存在于代理目录，仓库内没有可引用的归档；审计索引停在
AUD-20261116-03，`docs/README.md` 的 AUD-20261115 条目仍写“发布后收尾回验另行归档”。
- **PRA-201-02：** 归档报告第 3–7 行是交付件的 Markdown
硬换行；`.github/workflows/validate.yml` 的文档通道在 `make check-docs` 后无条件执行
`git diff --check "${BASE}...HEAD"`。按原字节归档会让必需检查 `local-validation`
必然失败，而删掉空格就不再是逐字节副本。
- `.gitattributes` 是唯一既能保留字节、又能让该检查放行的已跟踪机制；但许可覆盖检查器此前只把 `.gitignore`
列为配置类，`.gitattributes` 会被判为 `unclassified tracked file` 而失败。
- **PRA-201-01（已解除）：** 提交 `0cd1542` 的作者不是受信任身份。P1-p（#203）之后 `dco` 只检查 PR
正文的签名者，该头部已由维护者签署，此问题随同步解除；未改写已推送历史。

## Status before → after

| 位置 | 之前 | 之后 |
|---|---|---|
| 回验报告 | 只在本机代理目录 | 已入库，逐字节等于交付件 |
| 审计索引 | 最后一条为 AUD-20261116-03 | 新增 AUD-20261118-01 一段 |
| `docs/README.md` | 最后一条为 AUD-20261116-03 | 新增 AUD-20261118-01 一条 |
| 状态日志 §9 | 无归档记录 | 新增一行，Gate 不变（同步后与 P1-p 行并存） |
| `git diff --check`（文档通道） | 命中报告 5 行硬换行，退出 2 | 退出 0；归档字节不变 |
| `.gitattributes` | 不能引入（许可覆盖判为未分类） | 按配置类受检查，`covered=352 headers=257
declared=95 excluded=457 missing=0` |
| DCO | `0cd1542` 作者非受信任身份而失败 | P1-p 后只检查 PR 正文签名者，正文已由维护者签署 |

## Tests or proofs（本次执行）

分支头 `d54392c`（基线 `203249d`），2026-11-18：

| 命令 | 基线 SHA | 退出码 |
|---|---|---|
| `python3 -B -m unittest tests.workflow.test_license_coverage` |
`203249d` | 0（49 项通过） |
| `python3 -B scripts/check-license-coverage.py --require-git` |
`203249d` | 0（PASS：covered=352 headers=257 declared=95 excluded=457
missing=0） |
| `python3 -B scripts/update-manifests.py` | `203249d` | 0（刷新两份清单） |
| `python3 -B scripts/update-manifests.py --check` | `203249d` | 0（PASS）
|
| `python3 -B scripts/check-repository-evidence.py --repository .` |
`203249d` | 0（PASS，1008 个本地 prose 链接） |
| `cmp <交付件>
docs/08-governance/audits/audit-20261118-01-post-release-closure.md` |
`203249d` | 0（无输出，逐字节相同） |
| `git diff --check origin/main...HEAD` | `203249d` | 0（加
`.gitattributes` 后不再命中归档硬换行） |
| `make -j"$(nproc)" -O check` | `203249d` | 0（PASS） |

本次改到检查器与测试，按效率规则跑一次 `make check`；未跑 `make test` 全量回归。CI 因含非 Markdown
文件会走全量通道，结果以 GitHub 为准，不轮询。

## Evidence tags

无。本条目不新增证据提交。

## 理论缺口

无。本条目不依赖任何未建模性质，也不据此关闭 TG-6（#123）或 SV-62/SV-118 的 partial 缺口。

## Residual risk

- 报告结论原样保留：#196 的历史 DCO 漏签按维护者接受的 PR 正文补签作为补救，原 push DCO 失败仍在；本 PR
不把历史运行写成通过。
- 报告列出的残余事项（外部贡献者 fork 端到端实测免做、P1-n 合并后线上实测免做、“只有维护者合并”为流程约定、#186 的 DCO
补救）按原记录保留。
- `.gitattributes` 规则按模式 `audit-*.md` 豁免该目录下所有归档报告，不限于本条目这一份；索引
`README.md` 与其他文件不受影响。该规则只影响 whitespace 诊断，不改变任何文件字节。
- 本条目的 PR 正文在维护者签署后被更新（新增归档字节与门禁一节），签名行原样保留在最末尾；若维护者认为需要重新确认，可在正文或评论中说明。
- #128 是否关闭由维护者决定；本 PR 只把归档与索引这一前置条件落地。

## Documents updated


`docs/08-governance/audits/audit-20261118-01-post-release-closure.md`、`docs/08-governance/audits/README.md`、`docs/README.md`、`docs/07-roadmap/current-status.md`、`docs/08-governance/audits/.gitattributes`、`scripts/check-license-coverage.py`、`tests/workflow/test_license_coverage.py`、`docs/07-roadmap/open-questions.md`、`SINGLEHOST-SHA256SUMS`、`WORKFLOW-SHA256SUMS`

## 合并检查

- [x] 改动文件都在计划卡的文件集内（#200 已按维护者 2026-11-18 决定同步文件集与目标）
- [x] PARALLEL-1 审计：首轮 0 BLOCKER、1 MAJOR、1 MINOR；PRA-201-01 随 P1-p
解除，PRA-201-02 本 PR 修复，待增量复核
- [x] 已按 §5.4 合并 `origin/main` `203249d`，重跑通过
- [x] CI 通过：以 GitHub 为准（本次走全量通道），未轮询
- [x] DCO：维护者已在本正文最末尾签署 `Signed-off-by`；P1-p 后 `dco` 只检查签名者，提交作者不再单独要求


[![](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)

<!-- DCO（CONTRIBUTING §11）：维护者合并前在本行下方另起一段加上签名行 `Signed-off-by: 姓名
<邮箱>`。只有正文最末尾的 trailer 区才算数；正文中只含 `---` 的行会把之后的内容当成补丁区。代理不填写本段。 -->

Signed-off-by: inpac <inpac@lingmatrix.cn>

---------

Co-authored-by: dsh <dsh@localhost>
"""


class CoauthorSuffixTests(DcoTestCase):
    """GitHub appends the co-author suffix after the body sign-off at merge time.

    The body check and the push check must both read the sign-off through that
    suffix, and every other use of a dash line must keep its earlier verdict.
    """

    SIGNED = "Change: x\n\n" + SIGNOFF
    SUFFIX = "\n\n---------\n\nCo-authored-by: dsh <dsh@localhost>"

    def commit_verbatim(self, name, message, author=AGENT):
        """A commit whose message is stored byte for byte, as GitHub writes it."""
        (self.dir / name).write_text(name + "\n")
        (self.dir / "message.txt").write_text(message)
        self.git("add", name)
        self.git("commit", "-q", "--cleanup=verbatim", "-F", "message.txt", author=author)
        return self.git("rev-parse", "HEAD")

    def push_verdict(self, message):
        adopt = self.commit("b", "adopt DCO check", with_script=True, author=AGENT)
        head = self.commit_verbatim("c", message)
        return self.push(adopt, head)

    def test_the_real_squash_message_passes_the_push_check(self):
        result = self.push_verdict(ECE86B5_MESSAGE)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("PASS: 1 commit(s)", result.stdout)

    def test_the_real_message_is_the_one_the_trailer_parser_misses(self):
        parsed = subprocess.run(["git", "interpret-trailers", "--parse"],
                                input=ECE86B5_MESSAGE, capture_output=True, text=True)
        self.assertEqual(parsed.returncode, 0, parsed.stderr)
        self.assertEqual(parsed.stdout.strip(), "Co-authored-by: dsh <dsh@localhost>")

    def test_the_real_squash_message_passes_the_body_check(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=AGENT)
        result = self.pr(base, head, "false", ECE86B5_MESSAGE)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("signed off by inpac <inpac@lingmatrix.cn>", result.stdout)

    def test_the_committed_fixture_is_kept_verbatim(self):
        # "git commit -m" would strip and collapse blank lines, which would hide
        # the very shape under test; this helper commits the bytes as they are.
        head = self.commit_verbatim("c", ECE86B5_MESSAGE)
        self.assertEqual(self.git("show", "-s", "--format=%B", head), ECE86B5_MESSAGE.rstrip("\n"))

    def test_several_coauthors_pass(self):
        message = self.SIGNED + self.SUFFIX + "\nCo-authored-by: Example Author <author@example.invalid>"
        result = self.push_verdict(message)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_missing_signoff_above_the_suffix_fails(self):
        result = self.push_verdict("Change: x" + self.SUFFIX)
        self.assertEqual(result.returncode, 1)
        self.assertIn("no Signed-off-by trailer", result.stdout)

    def test_a_separator_that_is_not_nine_dashes_keeps_the_earlier_verdict(self):
        for separator in ("--------", "----------", "--------- "):
            with self.subTest(separator=separator):
                self.tearDown()
                self.setUp()
                suffix = "\n\n" + separator + "\n\nCo-authored-by: dsh <dsh@localhost>"
                result = self.push_verdict(self.SIGNED + suffix)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("no Signed-off-by trailer", result.stdout)

    def test_a_suffix_with_another_trailer_is_not_stripped(self):
        suffix = ("\n\n---------\n\nReviewed-by: R <r@example.invalid>\n"
                  "Co-authored-by: dsh <dsh@localhost>")
        result = self.push_verdict(self.SIGNED + suffix)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no Signed-off-by trailer", result.stdout)

    def test_the_separator_must_open_its_own_paragraph(self):
        # GitHub writes the separator as its own paragraph; glued to the line
        # above it, the block is ordinary body text and the earlier verdict stands.
        message = ("Change: x\n\n" + SIGNOFF + "\n---------\n\n"
                   "Co-authored-by: dsh <dsh@localhost>")
        result = self.push_verdict(message)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no Signed-off-by trailer", result.stdout)

    def test_the_coauthor_lines_must_end_the_message(self):
        result = self.push_verdict(self.SIGNED + self.SUFFIX + "\nmore prose")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no Signed-off-by trailer", result.stdout)

    def test_the_signer_must_still_be_on_the_list(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=AGENT)
        body = "Change: x\n\n" + UNKNOWN_SIGNOFF + self.SUFFIX
        result = self.pr(base, head, "false", body)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a sign-off identity", result.stdout)

    def test_a_listed_signer_passes_the_body_check_through_the_suffix(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=AGENT)
        body = "Change: x\n\n" + SIGNOFF + self.SUFFIX
        result = self.pr(base, head, "false", body)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("signed off by inpac <inpac@lingmatrix.cn>", result.stdout)

    def test_crlf_and_lf_are_judged_identically_through_the_suffix(self):
        base = self.commit("a", "base", author=AGENT)
        head = self.commit("b", "agent work", author=AGENT)
        text = "Change: x\n\n" + SIGNOFF + self.SUFFIX
        lf = self.pr(base, head, "false", text)
        crlf = self.pr(base, head, "false", text.replace("\n", "\r\n"))
        self.assertEqual(lf.returncode, 0, lf.stdout)
        self.assertEqual(lf.stdout, crlf.stdout)


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
        self.assertEqual(len(commands), 3)
        for command in commands[1:]:
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

    def test_organization_policy_precedes_checkout(self):
        policy = self.step('Apply organization contribution policy')
        self.assertLess(self.workflow.index('Apply organization contribution policy'),
                        self.workflow.index('Checkout the trusted checker'))
        self.assertIn("if: github.event_name == 'pull_request_target'", policy)
        self.assertIn("('OWNER', 'MEMBER')", policy)
        self.assertIn("HEAD_OWNER", policy)
        self.assertIn("BASE_OWNER", policy)
        self.assertNotIn('${{', self.run_blocks()[0])


    def test_organization_policy_accepts_members_and_rejects_external_sources(self):
        step = self.step('Apply organization contribution policy')
        body = step.split("run: |", 1)[1].splitlines()
        script = "\n".join(line[10:] for line in body if line.strip())
        for association, head_owner, expected in [
            ('MEMBER', 'zeromatrixtech', 0), ('OWNER', 'ZeroMatrixTech', 0),
            ('COLLABORATOR', 'ZeroMatrixTech', 1), ('MEMBER', 'external', 1),
            ('FIRST_TIMER', 'ZeroMatrixTech', 1),
        ]:
            with self.subTest(association=association, head_owner=head_owner):
                env = dict(os.environ, AUTHOR_ASSOCIATION=association,
                           HEAD_OWNER=head_owner, BASE_OWNER='ZeroMatrixTech')
                result = subprocess.run(['bash', '-c', script], env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)


class DocumentationConsistencyTests(unittest.TestCase):
    def test_local_verification_command_carries_the_body_environment(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text()
        self.assertIn("--body-env PR_BODY", contributing)
        self.assertIn('PR_BODY="$(cat', contributing)


if __name__ == "__main__":
    unittest.main()
