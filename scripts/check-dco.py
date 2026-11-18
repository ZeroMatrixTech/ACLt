#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check Developer Certificate of Origin sign-offs (CONTRIBUTING section 11).

Only the signer is checked; commit authors on a branch of this repository are
not.  Pull requests (`pr` mode) are checked in two parts:

* The pull request body must end with a trailer block carrying a
  `Signed-off-by` whose e-mail is a sign-off identity in the list.  The
  squash merge takes its commit message from the body
  (`squash_merge_commit_message = PR_BODY`), so this is the pre-merge gate
  for the commit that lands on `main`, and it confirms the whole pull
  request.  The body is untrusted data: the workflow hands it over in an
  environment variable, and this script only ever parses it as text.
* Commits on a pull request from a fork, merge commits included, must carry a
  `Signed-off-by` trailer whose e-mail matches the commit author.  That is
  the outside contributor's own DCO confirmation.  Commits on a branch of this
  repository (agents and the maintainer) are not inspected per commit: the
  body sign-off covers them whatever their authors are.

`push` mode keeps the fallback check: every first-parent commit pushed to
`main` must carry at least one `Signed-off-by` trailer, starting with the
first commit whose parent already contains this script (the adoption point).
Earlier history is not rewritten and is out of scope.

Both the body and commit messages go through the same
`git interpret-trailers --parse`: a line containing only `---` starts the
patch section, so anything after it is not a trailer, and CRLF is normalised to
LF first so the same text is judged the same way.  When a merged pull request
had several authors, GitHub appends a `---------` separator and one
`Co-authored-by` line per author to the squash message; that exact suffix is
stripped before parsing, so the sign-off written above it is read as the last
trailer paragraph again.

The sign-off identities live in `.github/dco-maintainers.txt` next to the
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
SEPARATOR = "-" * 9
COAUTHOR = re.compile(r"^Co-authored-by:\s*(?P<name>.+?)\s*<(?P<email>[^<>\s]+@[^<>\s]+)>$")
ROLES = {"signoff"}
REPO = "."
ZERO = "0" * 40


def git(*args, check=True, stdin=None):
    result = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, input=stdin)
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def without_coauthor_suffix(text):
    """The text minus the co-author block GitHub appends to a squash message.

    A pull request whose commits have more than one author gets a fixed suffix
    added to the message GitHub builds from its body: a line of exactly nine
    dashes, a blank line, then one `Co-authored-by: name <e-mail>` line per
    co-author.  That moves the body sign-off into the second-to-last
    paragraph, which `git interpret-trailers --parse` does not read.

    Only that shape is stripped.  A separator of any other length, a missing
    blank line on either side of the separator, or a line inside the suffix
    that is not a `Co-authored-by` trailer all leave the text unchanged, so
    every other use of a dash line keeps the verdict it had before.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    end = len(lines)
    while end and not lines[end - 1].strip():
        end -= 1
    first = end
    while first and COAUTHOR.match(lines[first - 1]):
        first -= 1
    if first == end:
        return text
    if first < 3 or lines[first - 1].strip() or lines[first - 2] != SEPARATOR:
        return text
    if lines[first - 3].strip():
        # GitHub writes the separator as its own paragraph; anywhere else the
        # line is ordinary body text and keeps its current meaning.
        return text
    body = "\n".join(lines[:first - 2])
    return body if body.strip() else text


def trailers(text):
    """Signed-off-by identities in the text's trailer block, as (name, e-mail)."""
    # Trailer parsing does not read a repository, so this never consults the
    # pull request's Git configuration; CRLF becomes LF so both line endings
    # reach git as the same bytes, and the co-author suffix is dropped first so
    # the sign-off above it is still the last trailer paragraph.  The body and
    # the commit checks both call this function, so they judge a text alike.
    result = subprocess.run(["git", "interpret-trailers", "--parse"],
                            capture_output=True, text=True,
                            input=without_coauthor_suffix(text.replace("\r\n", "\n")))
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
    """The sign-off identities that may sign a pull request body."""

    def __init__(self, signoff):
        self.signoff = signoff


def load_maintainers():
    """Read the list from the checkout that holds this script, never from --repo."""
    path = Path(__file__).resolve().parent.parent / MAINTAINERS
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SystemExit(f"cannot read the sign-off list {MAINTAINERS}: {error.strerror}")
    signoff = {}
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        role, _, rest = line.partition(" ")
        if role not in ROLES:
            raise SystemExit(f"{MAINTAINERS}:{number}: unknown role {role!r}; expected signoff")
        match = IDENTITY.match(rest.strip())
        if not match:
            raise SystemExit(f"{MAINTAINERS}:{number}: expected 'name <e-mail>' after the role")
        email = match.group("email").lower()
        signoff[email] = f"{match.group('name')} <{match.group('email')}>"
    if not signoff:
        raise SystemExit(f"{MAINTAINERS}: no signoff identity, so no merge could be signed")
    return Maintainers(signoff)


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
        print(f"FAIL: the pull request body is signed off by {signed}, which is not a sign-off "
              f"identity in {MAINTAINERS}")
        return False
    name, email = matched[-1]
    print(f"PASS: the pull request body is signed off by {name} <{email}>")
    return True


def check_commits(base, head, fork):
    """Fork pull requests sign every commit; repository branches do not.

    The body sign-off is the DCO confirmation for the whole pull request, so a
    branch of this repository needs no per-commit trailer from any author.  A
    fork commit is the outside contributor's own confirmation and keeps the
    per-commit rule, merge commits included.
    """
    if not fork:
        print("PASS: same-repository pull request; the body sign-off covers its commits")
        return True
    commits = git("rev-list", f"{base}..{head}").stdout.split()
    failures = []
    for commit in commits:
        author = author_email(commit)
        if author not in signoffs(commit):
            failures.append((commit, author))
    for commit, author in failures:
        print(f"FAIL: {commit[:12]} is authored by {author} and has no Signed-off-by trailer "
              "matching that author (use git commit -s)")
    if failures:
        return False
    print(f"PASS: {len(commits)} fork commit(s) signed off by their authors")
    return True


def check_pr(base, head, fork, body, maintainers):
    body_ok = check_body(body, maintainers)
    commits_ok = check_commits(base, head, fork)
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
        print(f"FAIL: {commit[:12]} on main has no Signed-off-by trailer; the signer adds it to "
              "the pull request body (CONTRIBUTING section 11)")
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
