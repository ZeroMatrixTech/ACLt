#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Simulate pull_request_target event fields against scripts/check-dco.py locally.

The pull_request_target workflow always runs the workflow and the checker from
the target branch, so a pull request that changes them cannot observe the new
behaviour before it merges.  This script reproduces the workflow step instead:
it builds a throwaway Git repository and hands the event fields to the checker
as environment variables (BASE, HEAD, FORK, PR_BODY), exactly the way the
workflow does, and reports one line per scenario.

Run it with:

    python3 -B tests/repository_hardening/dco_pr_simulation.py

Exit status 0 means every scenario produced its expected verdict.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-dco.py"
AGENT = ("inPac", "tenneidp@gmail.com")
AUTHOR = ("Example Author", "author@example.invalid")
SIGNOFF = "Signed-off-by: inpac <inpac@lingmatrix.cn>"
UNKNOWN = "Signed-off-by: Someone Else <other@example.invalid>"


def run(command, cwd, env, check=True):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit("command failed: {0}\n{1}".format(" ".join(command), result.stderr))
    return result


def git(repo, *args, author=AGENT):
    env = dict(os.environ, GIT_AUTHOR_NAME=author[0], GIT_AUTHOR_EMAIL=author[1],
               GIT_COMMITTER_NAME=author[0], GIT_COMMITTER_EMAIL=author[1],
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    return run(["git", *args], repo, env).stdout.strip()


def commit(repo, name, message, author):
    (Path(repo) / name).write_text(name + "\n")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message, author=author)
    return git(repo, "rev-parse", "HEAD")


def repository(root):
    """A base commit and one head commit per identity."""
    Path(root).mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    base = commit(root, "base", "base", AGENT)
    agent_head = commit(root, "agent", "agent work", AGENT)
    outside_head = commit(root, "outside", "outside work", AUTHOR)
    return base, agent_head, outside_head


def scenarios(agent_head, outside_head):
    signed = "Change: x\n\n" + SIGNOFF
    yield ("unsigned body", "Change: x", "false", agent_head, 1, "no Signed-off-by trailer")
    yield ("signed body", signed, "false", agent_head, 0, "signed off by inpac <inpac@lingmatrix.cn>")
    yield ("sign-off in the middle", "Change: x\n\n" + SIGNOFF + "\n\nmore prose",
           "false", agent_head, 1, "no Signed-off-by trailer")
    yield ("patch separator before the sign-off", "Change: x\n\n---\n\n" + SIGNOFF,
           "false", agent_head, 1, "patch section")
    yield ("CRLF body", "Change: x\r\n\r\n" + SIGNOFF + "\r\n", "false", agent_head, 0, "signed off by")
    yield ("signer outside the list", "Change: x\n\n" + UNKNOWN, "false", agent_head, 1,
           "not a maintainer sign-off identity")
    yield ("empty body", "", "false", agent_head, 1, "body is empty")
    yield ("non-maintainer commit unsigned", signed, "false", outside_head, 1, AUTHOR[1])
    yield ("fork commit unsigned", signed, "true", agent_head, 1, "Signed-off-by trailer matching")


def main():
    root = tempfile.mkdtemp()
    failures = 0
    try:
        repo = Path(root) / "pr"
        base, agent_head, outside_head = repository(repo)
        marker = Path(root) / "injected"
        injection = ("Change: x\n\n$(touch {0})\n`touch {0}`\n${{{B}}} github.token {{{B}}}\n\n"
                     .format(marker, B="{") + SIGNOFF)
        cases = list(scenarios(agent_head, outside_head))
        cases.append(("body characters are text", injection, "false", agent_head, 0, "signed off by"))
        print("command shape: PR_BODY=... python3 -B scripts/check-dco.py --repo <pr> pr "
              "--base <base> --head <head> --fork <true|false> --body-env PR_BODY")
        for name, body, fork, head, expected, needle in cases:
            env = dict(os.environ, BASE=base, HEAD=head, FORK=fork, PR_BODY=body)
            result = run([sys.executable, "-B", str(SCRIPT), "--repo", str(repo), "pr",
                          "--base", base, "--head", head, "--fork", fork,
                          "--body-env", "PR_BODY"], repo, env, check=False)
            ok = result.returncode == expected and needle in result.stdout + result.stderr
            failures += 0 if ok else 1
            print("{0}  {1:38s} expected exit {2}, got {3}".format(
                "PASS" if ok else "FAIL", name, expected, result.returncode))
            if not ok:
                print("      expected text: " + needle)
                print("      stdout: " + result.stdout.strip().replace("\n", "\n      "))
                print("      stderr: " + result.stderr.strip().replace("\n", "\n      "))
        if marker.exists():
            failures += 1
            print("FAIL  body characters created {0}".format(marker))
        else:
            print("PASS  body characters were never executed")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("{0} scenario(s) failed".format(failures) if failures else "PASS: all scenarios")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
