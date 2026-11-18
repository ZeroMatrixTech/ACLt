#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check Developer Certificate of Origin sign-offs (CONTRIBUTING section 11).

Pull requests (`pr` mode) are checked twice:

* The pull request body must end with a trailer block carrying a
  `Signed-off-by` whose e-mail is a maintainer sign-off identity.  The
  squash merge takes its commit message from the body
  (`squash_merge_commit_message = PR_BODY`), so this is the pre-merge gate
  for the commit that lands on `main`.  The body is untrusted data: the
  workflow hands it over in an environment variable, and this script only ever
  parses it as text.
* Commits on a pull request from a fork, merge commits included, must carry a
  `Signed-off-by` trailer whose e-mail matches the commit author.  Commits on
  a pull request from a branch of this repository are written by agents and
  the maintainer; a commit whose author is a maintainer identity needs no
  per-commit sign-off, and any other author (for example an outside
  contributor pushing to a branch of this repository) is checked like a fork
  commit.

`push` mode keeps the fallback check: every first-parent commit pushed to
`main` must carry at least one `Signed-off-by` trailer, starting with the
first commit whose parent already contains this script (the adoption point).
Earlier history is not rewritten and is out of scope.

Both the body and commit messages go through the same
`git interpret-trailers --parse`: a line containing only `---` starts the
patch section, so anything after it is not a trailer, and CRLF is normalised to
LF first so the same text is judged the same way.

The maintainer identities live in `.github/dco-maintainers.txt` next to the
checkout that holds this script.  The workflow runs the script from the trusted
checkout of the target branch, so a pull request cannot change the list that
judges it.  Nothing from the pull request is executed.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

SCRIPT = "scripts/check-dco.py"
MAINTAINERS = ".github/dco-maintainers.txt"
SIGNOFF = re.compile(r"^Signed-off-by:\s*(.+?)\s*<([^<>\s]+@[^<>\s]+)>\s*$", re.MULTILINE)
IDENTITY = re.compile(r"^(?P<name>.+?)\s*<(?P<email>[^<>\s]+@[^<>\s]+)>$")
ROLES = {"signoff", "author"}
REPO = "."
ZERO = "0" * 40


def git(*args, check=True, stdin=None):
    result = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, input=stdin)
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def trailers(text):
    """Signed-off-by identities in the text's trailer block, as (name, e-mail)."""
    # Trailer parsing does not read a repository, so this never consults the
    # pull request's Git configuration; CRLF becomes LF so both line endings
    # reach git as the same bytes.
    result = subprocess.run(["git", "interpret-trailers", "--parse"],
                            capture_output=True, text=True, input=text.replace("\r\n", "\n"))
    if result.returncode != 0:
        raise SystemExit(f"git interpret-trailers --parse failed: {result.stderr.strip()}")
    return [(name, email.lower()) for name, email in SIGNOFF.findall(result.stdout)]


def signoffs(commit):
    """E-mails in Signed-off-by trailers; lines elsewhere in the body are ignored."""
    return [email for _, email in trailers(git("show", "-s", "--format=%B", commit).stdout)]


def author_email(commit):
    return git("show", "-s", "--format=%ae", commit).stdout.strip().lower()


def adopted(commit):
    """True when the commit's first parent already contains this script."""
    parents = git("show", "-s", "--format=%P", commit).stdout.split()
    if not parents:
        return False
    return git("cat-file", "-e", f"{parents[0]}:{SCRIPT}", check=False).returncode == 0


class Maintainers:
    """Sign-off identities and the maintainer-owned commit identities."""

    def __init__(self, signoff, authors):
        self.signoff = signoff
        self.authors = authors


def load_maintainers():
    """Read the list from the checkout that holds this script, never from --repo."""
    path = Path(__file__).resolve().parent.parent / MAINTAINERS
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SystemExit(f"cannot read the maintainer list {MAINTAINERS}: {error.strerror}")
    signoff = {}
    authors = set()
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        role, _, rest = line.partition(" ")
        if role not in ROLES:
            raise SystemExit(f"{MAINTAINERS}:{number}: unknown role {role!r}; expected signoff or author")
        match = IDENTITY.match(rest.strip())
        if not match:
            raise SystemExit(f"{MAINTAINERS}:{number}: expected 'name <e-mail>' after the role")
        email = match.group("email").lower()
        authors.add(email)
        if role == "signoff":
            signoff[email] = f"{match.group('name')} <{match.group('email')}>"
    if not signoff:
        raise SystemExit(f"{MAINTAINERS}: no signoff identity, so no merge could be signed")
    return Maintainers(signoff, authors)


def check_body(body, maintainers):
    if not body.strip():
        print('FAIL: the pull request body is empty; the maintainer adds '
              '"Signed-off-by: <name> <e-mail>" as its last paragraph (CONTRIBUTING section 11)')
        return False
    identities = trailers(body)
    if not identities:
        hint = ""
        if any(line.strip() == "---" for line in body.replace("\r\n", "\n").splitlines()):
            hint = ('; a line containing only "---" starts the patch section, so a sign-off '
                    "below it is read as patch and ignored")
        print("FAIL: the pull request body has no Signed-off-by trailer in its last paragraph; "
              'add "Signed-off-by: <name> <e-mail>" as a standalone final paragraph '
              "(CONTRIBUTING section 11)" + hint)
        return False
    matched = [(name, email) for name, email in identities if email in maintainers.signoff]
    if not matched:
        signed = ", ".join(f"{name} <{email}>" for name, email in identities)
        print(f"FAIL: the pull request body is signed off by {signed}, which is not a maintainer "
              f"sign-off identity in {MAINTAINERS}")
        return False
    name, email = matched[-1]
    print(f"PASS: the pull request body is signed off by {name} <{email}>")
    return True


def check_commits(base, head, fork, maintainers):
    commits = git("rev-list", f"{base}..{head}").stdout.split()
    checked = 0
    failures = []
    for commit in commits:
        author = author_email(commit)
        if not fork and author in maintainers.authors:
            continue
        checked += 1
        if author not in signoffs(commit):
            failures.append((commit, author))
    for commit, author in failures:
        if fork:
            print(f"FAIL: {commit[:12]} is authored by {author} and has no Signed-off-by trailer "
                  "matching that author (use git commit -s)")
        else:
            print(f"FAIL: {commit[:12]} is authored by {author}, which is not a maintainer identity, "
                  "and has no Signed-off-by trailer matching that author (use git commit -s)")
    if failures:
        return False
    if fork:
        print(f"PASS: {checked} fork commit(s) signed off by their authors")
    elif checked:
        print(f"PASS: {checked} commit(s) by authors outside the maintainer identities are signed "
              "off by their authors")
    else:
        print("PASS: every commit is authored by a maintainer identity; no per-commit sign-off is required")
    return True


def check_pr(base, head, fork, body, maintainers):
    body_ok = check_body(body, maintainers)
    commits_ok = check_commits(base, head, fork, maintainers)
    return 0 if body_ok and commits_ok else 1


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
    global REPO
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="Git repository holding the commits to check")
    sub = parser.add_subparsers(dest="mode", required=True)
    pr = sub.add_parser("pr")
    pr.add_argument("--base", required=True)
    pr.add_argument("--head", required=True)
    pr.add_argument("--fork", choices=["true", "false"], required=True)
    pr.add_argument("--body-env", required=True, metavar="NAME",
                    help="environment variable that carries the untrusted pull request body")
    push = sub.add_parser("push")
    push.add_argument("--before", required=True)
    push.add_argument("--after", required=True)
    args = parser.parse_args(argv)
    REPO = args.repo
    if args.mode == "pr":
        # A missing variable is an empty body, which fails closed.
        body = os.environ.get(args.body_env, "")
        return check_pr(args.base, args.head, args.fork == "true", body, load_maintainers())
    return check_push(args.before, args.after)


if __name__ == "__main__":
    sys.exit(main())
