#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check Developer Certificate of Origin sign-offs (CONTRIBUTING section 11).

Two modes:

* ``pr``: commits on a pull request from a fork must each carry a
  ``Signed-off-by`` trailer whose e-mail matches the commit author.  Pull
  requests from branches of this repository are written by agents and the
  maintainer; the maintainer signs the squash merge commit instead, so they
  are skipped here.
* ``push``: every first-parent commit pushed to ``main`` must carry at least
  one ``Signed-off-by`` trailer, starting with the first commit whose parent
  already contains this script (the adoption point).  Earlier history is not
  rewritten and is out of scope.
"""
import argparse
import re
import subprocess
import sys

SCRIPT = "scripts/check-dco.py"
SIGNOFF = re.compile(r"^Signed-off-by:\s*(.+?)\s*<([^<>\s]+@[^<>\s]+)>\s*$", re.MULTILINE)
ZERO = "0" * 40


def git(*args, check=True):
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def signoffs(commit):
    message = git("show", "-s", "--format=%B", commit).stdout
    return [email.lower() for _, email in SIGNOFF.findall(message)]


def author_email(commit):
    return git("show", "-s", "--format=%ae", commit).stdout.strip().lower()


def adopted(commit):
    """True when the commit's first parent already contains this script."""
    parents = git("show", "-s", "--format=%P", commit).stdout.split()
    if not parents:
        return False
    return git("cat-file", "-e", f"{parents[0]}:{SCRIPT}", check=False).returncode == 0


def check_pr(base, head, fork):
    if not fork:
        print("PASS: same-repository pull request; the maintainer signs the squash merge commit")
        return 0
    commits = git("rev-list", "--no-merges", f"{base}..{head}").stdout.split()
    failures = []
    for commit in commits:
        emails = signoffs(commit)
        if author_email(commit) not in emails:
            failures.append(commit)
    for commit in failures:
        print(f"FAIL: {commit[:12]} lacks a Signed-off-by trailer matching its author (use git commit -s)")
    if failures:
        return 1
    print(f"PASS: {len(commits)} fork commit(s) signed off by their authors")
    return 0


def check_push(before, after):
    if before == ZERO:
        commits = [after]
    else:
        commits = git("rev-list", "--first-parent", f"{before}..{after}").stdout.split()
    checked = 0
    failures = []
    for commit in commits:
        if not adopted(commit):
            continue
        checked += 1
        if not signoffs(commit):
            failures.append(commit)
    for commit in failures:
        print(f"FAIL: {commit[:12]} on main has no Signed-off-by trailer; the maintainer signs squash merges")
    if failures:
        return 1
    print(f"PASS: {checked} commit(s) after the DCO adoption point carry a sign-off")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    pr = sub.add_parser("pr")
    pr.add_argument("--base", required=True)
    pr.add_argument("--head", required=True)
    pr.add_argument("--fork", choices=["true", "false"], required=True)
    push = sub.add_parser("push")
    push.add_argument("--before", required=True)
    push.add_argument("--after", required=True)
    args = parser.parse_args(argv)
    if args.mode == "pr":
        return check_pr(args.base, args.head, args.fork == "true")
    return check_push(args.before, args.after)


if __name__ == "__main__":
    sys.exit(main())
