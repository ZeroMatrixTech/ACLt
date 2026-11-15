#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check that every tracked code and configuration file has an SPDX license.

The covered boundary is every tracked file whose contents carry code or
configuration: the code suffixes (.py, .rs, .sh, .cpp, .cjs, .js, .mjs, .html,
.htm), the configuration suffixes (.yml, .yaml, .toml), the build and VCS files
named Makefile, GNUmakefile, makefile or .gitignore, and the explicit strict
JSON configuration paths in CONFIG_PATHS. JSON has no comment syntax and strict
parsers reject comments, so those two files can only be declared externally.
`.js`, `.mjs` and `.cjs` are treated the same.

Markdown, data JSON, plain-text logs and captured outputs, lock files, archives
and the root LICENSE are outside the boundary. The repository-wide statement in
README ("开源与许可") and the root LICENSE cover them; most are historical
evidence kept byte-for-byte. OQ-01 in docs/07-roadmap/open-questions.md carries
the exclusion table with a reason per class.

An SPDX identifier must stand alone in a leading comment line; the same text
inside a string or code line is not a file header. A covered file is covered by
a header in its first ten lines or by an explicit REUSE.toml path declaring
Apache-2.0. A declaration for a path outside the boundary, for a missing path,
or for a file that already carries a header is an error. Unicode-3.0 headers are
accepted only on UNICODE_DATA_PATHS; every other file must be Apache-2.0.
Tracked files are read through git when the directory is a checkout; an
unpacked tree is walked.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

CODE_SUFFIXES = frozenset({".py", ".rs", ".sh", ".cpp", ".cjs", ".js", ".mjs", ".html", ".htm"})
CONFIG_SUFFIXES = frozenset({".yml", ".yaml", ".toml"})
CONFIG_NAMES = frozenset({"Makefile", "GNUmakefile", "makefile", ".gitignore"})
CONFIG_PATHS = frozenset({"DELIVERY-SCOPE.json", ".aclt-flow/template.json"})
DEFAULT_LICENSE = "Apache-2.0"
UNICODE_LICENSE = "Unicode-3.0"
UNICODE_DATA_PATHS = frozenset({"tools/verification_profile/rust/unicode_data.rs"})
HEADER_LINES = 10
COMMENT_PREFIXES = ("#", "//", "/*", "*", "<!--")
# Only VCS metadata is skipped during a fallback walk. Other directories can
# contain tracked source (for example build/probe.py), so they must be visited.
EXCLUDED_DIRS = frozenset({".git"})


class CoverageError(Exception):
    """The tree is not fully covered by file headers or declarations."""


@dataclass(frozen=True)
class Coverage:
    covered: int
    headers: int
    declared: int
    missing: int


def _is_covered(relative):
    path = PurePosixPath(relative)
    return (
        path.suffix in CODE_SUFFIXES
        or path.suffix in CONFIG_SUFFIXES
        or path.name in CONFIG_NAMES
        or relative in CONFIG_PATHS
    )


def _run_git(root, *arguments):
    try:
        return subprocess.run(
            ["git", "-c", f"safe.directory={root}", "-C", str(root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"") or b""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace").strip()
        raise CoverageError(f"cannot read git inventory: {detail or exc}") from exc


def _tracked_covered_files(root):
    names = _run_git(root, "ls-files", "-z").stdout.split(b"\0")
    files = []
    for raw in names:
        if not raw:
            continue
        relative = raw.decode("utf-8")
        if not _is_covered(relative):
            continue
        path = root / relative
        if path.is_symlink():
            raise CoverageError(f"unsafe symlink source: {relative}")
        if path.is_file():
            files.append(relative)
    return sorted(files)


def _walk_covered_files(root):
    files = []
    for directory, dirnames, filenames in os.walk(root):
        directory_path = Path(directory)
        # Prune only VCS metadata before descending. Do not prune source-like
        # directories such as build/: a tracked source there must not vanish
        # just because git metadata is unusable.
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS)
        for name in dirnames:
            path = directory_path / name
            if path.is_symlink():
                relative = path.relative_to(root)
                raise CoverageError(f"unsafe symlink source: {relative.as_posix()}")
        for name in sorted(filenames):
            path = directory_path / name
            relative = path.relative_to(root)
            if path.is_symlink():
                raise CoverageError(f"unsafe symlink source: {relative.as_posix()}")
            if path.is_file() and _is_covered(relative.as_posix()):
                files.append(relative.as_posix())
    return sorted(files)


def _covered_files(root, require_git=False):
    if (root / ".git").exists():
        try:
            top = _run_git(root, "rev-parse", "--show-toplevel").stdout.decode("utf-8").strip()
        except CoverageError:
            if require_git:
                raise
        else:
            if Path(top).resolve() != root.resolve():
                raise CoverageError(f"not a git checkout root: {root}")
            try:
                return _tracked_covered_files(root)
            except CoverageError:
                # Git metadata can be present but unusable, for example a
                # container checkout rejected by Git's dubious-ownership check.
                if require_git:
                    raise
    return _walk_covered_files(root)


def _comment_body(line):
    stripped = line.strip()
    for prefix in COMMENT_PREFIXES:
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def _header_license(path, relative):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:HEADER_LINES]
    except (OSError, UnicodeDecodeError) as exc:
        raise CoverageError(f"cannot read source {relative}: {exc}") from exc

    found = []
    for line in lines:
        if not line.strip():
            continue
        body = _comment_body(line)
        if body is None:
            # Stop at the first non-comment line. A comment-looking line inside
            # a string or a later comment after code is not a file header.
            break
        if not body.startswith("SPDX-License-Identifier:"):
            continue
        value = body.split(":", 1)[1].strip()
        value = value.removesuffix("*/").strip().removesuffix("-->").strip()
        if not value or any(character.isspace() for character in value):
            raise CoverageError(f"{relative}: malformed SPDX-License-Identifier")
        found.append(value)
    if not found:
        return None
    if len(set(found)) != 1:
        raise CoverageError(f"{relative}: multiple SPDX license identifiers: {found}")
    return found[0]


def _declared_path(raw):
    if not isinstance(raw, str) or not raw:
        raise CoverageError("REUSE.toml contains an empty path")
    if "\x00" in raw:
        raise CoverageError(f"unsafe declared path: {raw!r}")
    if raw.startswith(("/", "\\")):
        raise CoverageError(f"unsafe declared path: {raw}")
    if any(character in raw for character in "*?[]"):
        raise CoverageError(f"declared path must be explicit, not a glob: {raw}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise CoverageError(f"unsafe declared path: {raw}")
    return path.as_posix()


def _load_declarations(root):
    path = root / "REUSE.toml"
    if not path.is_file():
        raise CoverageError("REUSE.toml is missing")
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CoverageError(f"cannot read REUSE.toml: {exc}") from exc

    if data.get("version") != 1:
        raise CoverageError("REUSE.toml must declare version = 1")
    annotations = data.get("annotations", [])
    if not isinstance(annotations, list):
        raise CoverageError("REUSE.toml annotations must be an array of tables")

    declarations = {}
    for index, annotation in enumerate(annotations, start=1):
        if not isinstance(annotation, dict):
            raise CoverageError(f"REUSE.toml annotation {index} is not a table")
        license_value = annotation.get("SPDX-License-Identifier")
        if not isinstance(license_value, str) or not license_value:
            raise CoverageError(f"REUSE.toml annotation {index} has no SPDX license")
        if license_value != DEFAULT_LICENSE:
            raise CoverageError(
                f"REUSE.toml annotation {index} uses unsupported external license "
                f"{license_value!r}; only {DEFAULT_LICENSE} is allowed"
            )
        copyright_value = annotation.get("SPDX-FileCopyrightText")
        copyright_values = copyright_value if isinstance(copyright_value, list) else [copyright_value]
        if not copyright_values or any(
            not isinstance(value, str) or not value.strip() for value in copyright_values
        ):
            raise CoverageError(f"REUSE.toml annotation {index} has no copyright text")

        paths = annotation.get("path")
        if isinstance(paths, str):
            paths = [paths]
        if not isinstance(paths, list) or not paths:
            raise CoverageError(f"REUSE.toml annotation {index} has no paths")
        for raw in paths:
            relative = _declared_path(raw)
            if relative in declarations:
                raise CoverageError(f"duplicate declared path: {relative}")
            declarations[relative] = license_value
    return declarations


def check_coverage(root, require_git=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise CoverageError(f"not a directory: {root}")

    declarations = _load_declarations(root)
    covered = _covered_files(root, require_git=require_git)
    headers = {}
    errors = []
    for relative in covered:
        try:
            headers[relative] = _header_license(root / relative, relative)
        except CoverageError as exc:
            errors.append(str(exc))

    declared = {}
    for relative in declarations:
        path = root / relative
        if path.is_symlink():
            errors.append(f"unsafe symlink declared path: {relative}")
            continue
        if not path.exists():
            errors.append(f"declared path does not exist: {relative}")
            continue
        if not path.is_file():
            errors.append(f"declared path is not a file: {relative}")
            continue
        if not _is_covered(relative):
            errors.append(f"declared path is not a code or configuration file: {relative}")
            continue
        license_value = headers.get(relative)
        if license_value is not None:
            errors.append(f"declared path already has an SPDX header: {relative}")
            continue
        declared[relative] = declarations[relative]

    missing = []
    for relative in covered:
        license_value = headers.get(relative)
        if license_value is None:
            if relative not in declared:
                missing.append(relative)
            continue
        if license_value == DEFAULT_LICENSE:
            continue
        if license_value == UNICODE_LICENSE:
            if relative in UNICODE_DATA_PATHS:
                continue
            errors.append(
                f"{relative}: {UNICODE_LICENSE} is only allowed for "
                + ", ".join(sorted(UNICODE_DATA_PATHS))
            )
            continue
        errors.append(f"{relative}: unsupported SPDX license {license_value!r}")

    if errors:
        raise CoverageError("\n".join(errors))
    if missing:
        raise CoverageError(
            "missing licenses (add an SPDX header or an explicit REUSE.toml path):\n"
            + "\n".join(missing)
        )

    header_count = sum(value is not None for value in headers.values())
    return Coverage(
        covered=len(covered),
        headers=header_count,
        declared=len(declared),
        missing=0,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="source tree root (default: the repository containing this script)",
    )
    parser.add_argument(
        "--require-git",
        action="store_true",
        help="fail instead of walking if a checkout's git inventory is unusable",
    )
    args = parser.parse_args(argv)
    try:
        result = check_coverage(args.root, require_git=args.require_git)
    except CoverageError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"PASS: covered={result.covered} headers={result.headers} "
        f"declared={result.declared} missing={result.missing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
