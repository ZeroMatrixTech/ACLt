#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the SPDX/REUSE code and configuration coverage check."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check-license-coverage.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_license_coverage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


class LicenseCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.write_reuse("version = 1\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_reuse(self, text):
        # The fixture REUSE.toml is itself a covered .toml file, so it carries
        # a header and shows up in the counts below.
        (self.root / "REUSE.toml").write_text(
            "# SPDX-License-Identifier: Apache-2.0\n" + text, encoding="utf-8"
        )

    def declaration(self, path, license="Apache-2.0"):
        return (
            "[[annotations]]\n"
            f'path = "{path}"\n'
            'SPDX-FileCopyrightText = "2026 Example"\n'
            f'SPDX-License-Identifier = "{license}"\n'
        )

    def assert_rejected(self, fragment):
        with self.assertRaises(CHECKER.CoverageError) as context:
            CHECKER.check_coverage(self.root)
        self.assertIn(fragment, str(context.exception))

    def result(self):
        return CHECKER.check_coverage(self.root)

    def init_git(self):
        subprocess.run(
            ["git", "init", "-q", str(self.root)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def git_add(self, *paths):
        subprocess.run(
            ["git", "-C", str(self.root), "add", "--", *paths],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def test_repository_tree_is_classified(self):
        # The live tree may legitimately gain headed files, so this checks the
        # classification invariants rather than a frozen total.
        inventory = CHECKER._inventory(ROOT, require_git=True)
        result = CHECKER.check_coverage(ROOT)
        self.assertEqual(result.missing, 0)
        self.assertEqual(result.covered, result.headers + result.declared)
        self.assertEqual(result.covered + result.excluded, len(inventory))
        unclassified = [
            relative
            for relative in inventory
            if not CHECKER._is_covered(relative) and not CHECKER._is_excluded(relative)
        ]
        self.assertEqual(unclassified, [])

    def test_closed_classification_snapshot(self):
        # Fixed snapshot: covered/declared/excluded counts on a known tree.
        self.write("src/a.py", "# SPDX-License-Identifier: Apache-2.0\n")
        self.write("src/b.py", "print(1)\n")
        self.write("notes.md", "text\n")
        self.write("Cargo.lock", "lock\n")
        self.write("SINGLEHOST-SHA256SUMS", "digest\n")
        self.write("LICENSE", "license\n")
        self.write_reuse("version = 1\n" + self.declaration("src/b.py"))
        result = self.result()
        self.assertEqual(
            (result.covered, result.headers, result.declared, result.excluded, result.missing),
            (3, 2, 1, 4, 0),
        )

    def test_git_inventory_unavailable_falls_back_to_walk(self):
        self.write("example.py", "# SPDX-License-Identifier: Apache-2.0\nprint(1)\n")
        (self.root / ".git").mkdir()
        result = self.result()
        self.assertEqual((result.covered, result.headers, result.declared), (2, 2, 0))

    def test_require_git_rejects_unusable_git(self):
        self.write("example.py", "# SPDX-License-Identifier: Apache-2.0\n")
        (self.root / ".git").mkdir()
        with self.assertRaises(CHECKER.CoverageError) as context:
            CHECKER.check_coverage(self.root, require_git=True)
        self.assertIn("cannot read git inventory", str(context.exception))

    def test_walk_includes_build_source_without_git(self):
        self.write("build/probe.py", "# SPDX-License-Identifier: Apache-2.0\n")
        self.assertEqual(self.result().covered, 2)

    def test_walk_reports_build_source_without_header(self):
        self.write("build/probe.py", "print(1)\n")
        (self.root / ".git").mkdir()
        self.assert_rejected("build/probe.py")

    def test_symlinked_directory_is_rejected(self):
        self.write("real/example.py", "# SPDX-License-Identifier: Apache-2.0\nprint(1)\n")
        (self.root / "link").symlink_to(self.root / "real", target_is_directory=True)
        self.assert_rejected("unsafe symlink source: link")

    def test_header_covers_source(self):
        self.write("example.py", "# SPDX-License-Identifier: Apache-2.0\nprint(1)\n")
        self.assertEqual(self.result().headers, 2)

    def test_explicit_declaration_covers_source(self):
        self.write("example.py", "print(1)\n")
        self.write_reuse("version = 1\n" + self.declaration("example.py"))
        result = self.result()
        self.assertEqual((result.covered, result.headers, result.declared), (2, 1, 1))

    def test_cargo_manifest_is_covered_and_declarable(self):
        self.write("Cargo.toml", '[package]\nname = "example"\n')
        self.assert_rejected("Cargo.toml")
        self.write_reuse("version = 1\n" + self.declaration("Cargo.toml"))
        self.assertEqual((self.result().covered, self.result().declared), (2, 1))

    def test_javascript_mjs_and_cjs_are_covered_alike(self):
        for suffix in (".cjs", ".js", ".mjs"):
            with self.subTest(suffix=suffix):
                self.write("tool" + suffix, "console.log(1)\n")
                self.assert_rejected("tool" + suffix)
                (self.root / ("tool" + suffix)).unlink()

    def test_html_is_covered(self):
        self.write("page.html", "<!doctype html>\n<p>hi</p>\n")
        self.assert_rejected("page.html")
        self.write("page.html", "<!-- SPDX-License-Identifier: Apache-2.0 -->\n<!doctype html>\n")
        self.assertEqual(self.result().headers, 2)

    def test_makefile_is_covered(self):
        self.write("Makefile", "all:\n\t@true\n")
        self.assert_rejected("Makefile")
        self.write("Makefile", "# SPDX-License-Identifier: Apache-2.0\nall:\n\t@true\n")
        self.assertEqual(self.result().headers, 2)

    def test_yaml_is_covered_and_declarable(self):
        self.write("ci.yml", "name: example\n")
        self.assert_rejected("ci.yml")
        self.write_reuse("version = 1\n" + self.declaration("ci.yml"))
        self.assertEqual((self.result().covered, self.result().declared), (2, 1))

    def test_gitignore_is_covered_and_declarable(self):
        self.write(".gitignore", "build/\n")
        self.assert_rejected(".gitignore")
        self.write_reuse("version = 1\n" + self.declaration(".gitignore"))
        self.assertEqual((self.result().covered, self.result().declared), (2, 1))

    def test_config_json_requires_declaration(self):
        self.write("DELIVERY-SCOPE.json", '{"source_directories": []}\n')
        self.assert_rejected("DELIVERY-SCOPE.json")
        self.write_reuse("version = 1\n" + self.declaration("DELIVERY-SCOPE.json"))
        self.assertEqual((self.result().covered, self.result().declared), (2, 1))

    def test_data_json_stays_outside_boundary(self):
        self.write("results.json", '{"value": 1}\n')
        self.write("README.md", "text\n")
        self.assertEqual(self.result().covered, 1)

    def test_toml_is_covered(self):
        self.write("settings.toml", "value = 1\n")
        self.assert_rejected("settings.toml")

    def test_declaring_covered_file_with_header_is_rejected(self):
        self.write("example.py", "# SPDX-License-Identifier: Apache-2.0\n")
        self.write_reuse("version = 1\n" + self.declaration("example.py"))
        self.assert_rejected("already has an SPDX header")

    def test_non_covered_declaration_is_rejected(self):
        self.write("README.md", "text\n")
        self.write_reuse("version = 1\n" + self.declaration("README.md"))
        self.assert_rejected("not a code or configuration file")

    def test_unicode_license_is_limited_to_generated_data(self):
        self.write(
            "tools/verification_profile/rust/unicode_data.rs",
            "// SPDX-License-Identifier: Unicode-3.0\npub const DATA: u32 = 0;\n",
        )
        self.assertEqual(self.result().headers, 2)
        self.write("tools/probe_uni.py", "# SPDX-License-Identifier: Unicode-3.0\n")
        self.assert_rejected("only allowed for tools/verification_profile/rust/unicode_data.rs")

    def test_unicode_header_cannot_be_replaced_by_declaration(self):
        self.write(
            "tools/verification_profile/rust/unicode_data.rs",
            "// SPDX-License-Identifier: Unicode-3.0\npub const DATA: u32 = 0;\n",
        )
        self.write_reuse(
            "version = 1\n"
            + self.declaration("tools/verification_profile/rust/unicode_data.rs")
        )
        self.assert_rejected("already has an SPDX header")

    def test_unicode_external_declaration_is_rejected(self):
        self.write("example.py", "print(1)\n")
        self.write_reuse("version = 1\n" + self.declaration("example.py", "Unicode-3.0"))
        self.assert_rejected("unsupported external license")

    def test_undeclared_covered_file_is_rejected(self):
        self.write("example.py", "print(1)\n")
        self.assert_rejected("missing licenses")

    def test_string_literal_is_not_a_header(self):
        self.write("example.py", 'value = "# SPDX-License-Identifier: Apache-2.0"\n')
        self.assert_rejected("missing licenses")

    def test_missing_declared_path_is_rejected(self):
        self.write_reuse("version = 1\n" + self.declaration("missing.py"))
        self.assert_rejected("declared path does not exist")

    def test_parent_escape_is_rejected(self):
        self.write_reuse("version = 1\n" + self.declaration("../outside.py"))
        self.assert_rejected("unsafe declared path")

    def test_duplicate_declaration_is_rejected(self):
        self.write("example.py", "print(1)\n")
        self.write_reuse(
            "version = 1\n"
            + self.declaration("example.py")
            + self.declaration("example.py")
        )
        self.assert_rejected("duplicate declared path")

    def test_unknown_header_license_is_rejected(self):
        self.write("example.py", "# SPDX-License-Identifier: MIT\n")
        self.assert_rejected("unsupported SPDX license")

    def test_too_late_header_is_rejected(self):
        self.write("example.py", "\n" * 10 + "# SPDX-License-Identifier: Apache-2.0\n")
        self.assert_rejected("missing licenses")

    def test_uppercase_suffix_is_covered(self):
        self.write("PAGE.HTML", "<!doctype html>\n<p>hi</p>\n")
        self.assert_rejected("missing licenses")
        self.write("PAGE.HTML", "<!-- SPDX-License-Identifier: Apache-2.0 -->\n<p>hi</p>\n")
        self.assertEqual(self.result().headers, 2)

    def test_unclassified_tracked_file_is_rejected(self):
        for relative in (
            "tool.ts",
            "Dockerfile",
            "run",
            "other.lock",
            "audit/package.lock",
            "audit/tool.pySHA256SUMS",
            "audit/LICENSE",
        ):
            with self.subTest(relative=relative):
                self.write(relative, "text\n")
                self.assert_rejected(f"unclassified tracked file: {relative}")
                (self.root / relative).unlink()

    def test_excluded_classes_do_not_need_headers(self):
        for relative in (
            "notes.md",
            "data.json",
            "output.txt",
            "table.tsv",
            "run.log",
            "Cargo.lock",
            "bundle.tar.gz",
            "artifact.cbor",
            "report.docx",
            "SHA256SUMS",
            "LICENSE",
        ):
            self.write(relative, "text\n")
        result = self.result()
        self.assertEqual((result.covered, result.excluded, result.missing), (1, 11, 0))

    def test_untracked_declared_file_is_rejected(self):
        self.write("scratch.py", "print(1)\n")
        self.write_reuse("version = 1\n" + self.declaration("scratch.py"))
        self.init_git()
        with self.assertRaises(CHECKER.CoverageError) as context:
            CHECKER.check_coverage(self.root, require_git=True)
        self.assertIn(
            "declared path is not an included code or configuration file: scratch.py",
            str(context.exception),
        )

    def test_untracked_declared_file_with_header_is_rejected(self):
        self.write("scratch.py", "# SPDX-License-Identifier: Apache-2.0\nprint(1)\n")
        self.write_reuse("version = 1\n" + self.declaration("scratch.py"))
        self.init_git()
        with self.assertRaises(CHECKER.CoverageError) as context:
            CHECKER.check_coverage(self.root, require_git=True)
        self.assertIn("not an included code or configuration file", str(context.exception))
        self.assertNotIn("already has an SPDX header", str(context.exception))

    def test_tracked_file_missing_from_working_tree_is_rejected(self):
        self.write("notes.md", "text\n")
        self.write("example.py", "# SPDX-License-Identifier: Apache-2.0\n")
        self.init_git()
        self.git_add("notes.md", "example.py")
        (self.root / "notes.md").unlink()
        with self.assertRaises(CHECKER.CoverageError) as context:
            CHECKER.check_coverage(self.root, require_git=True)
        self.assertIn(
            "tracked file is missing from the working tree:",
            str(context.exception),
        )
        self.assertIn("notes.md", str(context.exception))

    def test_tracked_declared_file_passes(self):
        self.write("scratch.py", "print(1)\n")
        self.write_reuse("version = 1\n" + self.declaration("scratch.py"))
        self.init_git()
        self.git_add("scratch.py")
        result = CHECKER.check_coverage(self.root, require_git=True)
        self.assertEqual((result.covered, result.headers, result.declared), (1, 0, 1))


if __name__ == "__main__":
    unittest.main()
