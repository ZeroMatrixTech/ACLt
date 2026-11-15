#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check that every source file has an SPDX license or a REUSE declaration.

Source files are Python, Rust, shell, C++, and Node scripts. A source file is
covered by an SPDX-License-Identifier in its first ten lines or, for
Apache-2.0 only, by an explicit path in REUSE.toml. Tracked files are read
through git when the directory is a checkout; an unpacked source tree is walked.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SOURCE_SUFFIXES = frozenset({".py", ".rs", ".sh", ".cpp", ".cjs"})
HEADER_LICENSES = frozenset({"Apache-2.0", "Unicode-3.0"})
EXTERNAL_LICENSE = "Apache-2.0"
HEADER_LINES = 10
EXCLUDED_DIRS = frozenset({".git", "__pycache__", "target", "build", ".toolchain", "artifacts", "dist"})


class CoverageError(Exception):
    """The source tree is not fully covered by file headers or declarations."""


@dataclass(frozen=True)
class Coverage:
    source: int
    headers: int
    declared: int
    missing: int


def _run_git(root, *arguments):
    try:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"") or b""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace").strip()
        raise CoverageError(f"cannot read git inventory: {detail or exc}") from exc


def _tracked_source_files(root):
    names = _run_git(root, "ls-files", "-z").stdout.split(b"\0")
    files = []
    for raw in names:
        if not raw:
            continue
        relative = raw.decode("utf-8")
        path = root / relative
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        if path.is_symlink():
            raise CoverageError(f"unsafe symlink source: {relative}")
        if path.is_file():
            files.append(relative)
    return sorted(files)


def _walk_source_files(root):
    files = []
    for directory, dirnames, filenames in os.walk(root):
        directory_path = Path(directory)
        # Prune excluded directories before descending. A tracked checkout can
        # carry a large .git or target tree even though none of it is source.
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
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                files.append(relative.as_posix())
    return sorted(files)


def _source_files(root):
    if (root / ".git").exists():
        try:
            top = _run_git(root, "rev-parse", "--show-toplevel").stdout.decode("utf-8").strip()
        except CoverageError:
            top = None
        if top is not None:
            if Path(top).resolve() != root.resolve():
                raise CoverageError(f"not a git checkout root: {root}")
            try:
                return _tracked_source_files(root)
            except CoverageError:
                # Git metadata can be present but unusable, for example a
                # container checkout rejected by Git's dubious-ownership check.
                pass
    return _walk_source_files(root)


def _header_license(path, relative):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:HEADER_LINES]
    except (OSError, UnicodeDecodeError) as exc:
        raise CoverageError(f"cannot read source {relative}: {exc}") from exc

    found = []
    for line in lines:
        marker = "SPDX-License-Identifier:"
        if marker not in line:
            continue
        value = line.split(marker, 1)[1].strip()
        value = value.removesuffix("*/").strip().removesuffix("-->").strip()
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
        if license_value != EXTERNAL_LICENSE:
            raise CoverageError(
                f"REUSE.toml annotation {index} uses unsupported external license "
                f"{license_value!r}; only {EXTERNAL_LICENSE} is allowed"
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


def check_coverage(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise CoverageError(f"not a directory: {root}")

    declarations = _load_declarations(root)
    source = _source_files(root)
    headers = {}
    errors = []
    for relative in source:
        try:
            headers[relative] = _header_license(root / relative, relative)
        except CoverageError as exc:
            errors.append(str(exc))

    for relative in declarations:
        path = root / relative
        if path.is_symlink():
            errors.append(f"unsafe symlink declared path: {relative}")
        elif not path.exists():
            errors.append(f"declared path does not exist: {relative}")
        elif not path.is_file():
            errors.append(f"declared path is not a file: {relative}")
        elif path.suffix not in SOURCE_SUFFIXES:
            errors.append(f"declared path is not a source file: {relative}")
        elif relative not in headers:
            errors.append(f"declared path is not an included source file: {relative}")
        elif headers[relative] is not None:
            errors.append(f"declared path already has an SPDX header: {relative}")

    missing = []
    for relative in source:
        license_value = headers.get(relative)
        if license_value is None:
            if relative not in declarations:
                missing.append(relative)
        elif license_value not in HEADER_LICENSES:
            errors.append(f"{relative}: unsupported SPDX license {license_value!r}")

    if errors:
        raise CoverageError("\n".join(errors))
    if missing:
        raise CoverageError(
            "missing source licenses (add an SPDX header or an explicit REUSE.toml path):\n"
            + "\n".join(missing)
        )

    header_count = sum(value is not None for value in headers.values())
    declared_count = sum(
        headers.get(relative) is None and relative in declarations for relative in source
    )
    return Coverage(
        source=len(source),
        headers=header_count,
        declared=declared_count,
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
    args = parser.parse_args(argv)
    try:
        result = check_coverage(args.root)
    except CoverageError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"PASS: source={result.source} headers={result.headers} "
        f"declared={result.declared} missing={result.missing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
