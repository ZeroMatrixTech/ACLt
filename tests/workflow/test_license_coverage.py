#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the SPDX/REUSE source coverage check."""
import importlib.util
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
        (self.root / "REUSE.toml").write_text(text, encoding="utf-8")

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

    def test_repository_tree_is_covered(self):
        result = CHECKER.check_coverage(ROOT)
        self.assertEqual(result.missing, 0)
        self.assertEqual(result.declared, 79)
        self.assertEqual(result.external, 2)
        self.assertEqual(result.source, result.headers + result.declared)

    def test_git_inventory_unavailable_falls_back_to_walk(self):
        self.write("example.py", "# SPDX-License-Identifier: Apache-2.0\nprint(1)\n")
        (self.root / ".git").mkdir()
        result = CHECKER.check_coverage(self.root)
        self.assertEqual(
            (result.source, result.headers, result.declared, result.external, result.missing),
            (1, 1, 0, 0, 0),
        )

    def test_require_git_rejects_unusable_git(self):
        self.write("example.py", "# SPDX-License-Identifier: Apache-2.0\n")
        (self.root / ".git").mkdir()
        with self.assertRaises(CHECKER.CoverageError) as context:
            CHECKER.check_coverage(self.root, require_git=True)
        self.assertIn("cannot read git inventory", str(context.exception))

    def test_walk_includes_build_source_without_git(self):
        self.write("build/probe.py", "# SPDX-License-Identifier: Apache-2.0\n")
        result = CHECKER.check_coverage(self.root)
        self.assertEqual(
            (result.source, result.headers, result.declared, result.external, result.missing),
            (1, 1, 0, 0, 0),
        )

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
        result = CHECKER.check_coverage(self.root)
        self.assertEqual(
            (result.source, result.headers, result.declared, result.external, result.missing),
            (1, 1, 0, 0, 0),
        )

    def test_explicit_declaration_covers_source(self):
        self.write("example.py", "print(1)\n")
        self.write_reuse("version = 1\n" + self.declaration("example.py"))
        result = CHECKER.check_coverage(self.root)
        self.assertEqual(
            (result.source, result.headers, result.declared, result.external, result.missing),
            (1, 0, 1, 0, 0),
        )

    def test_cargo_manifest_may_be_declared_externally(self):
        self.write("Cargo.toml", '[package]\nname = "example"\n')
        self.write_reuse("version = 1\n" + self.declaration("Cargo.toml"))
        result = CHECKER.check_coverage(self.root)
        self.assertEqual(
            (result.source, result.headers, result.declared, result.external, result.missing),
            (0, 0, 0, 1, 0),
        )

    def test_non_cargo_toml_declaration_is_rejected(self):
        self.write("settings.toml", "value = 1\n")
        self.write_reuse("version = 1\n" + self.declaration("settings.toml"))
        self.assert_rejected("not a source file or Cargo manifest")

    def test_js_and_html_are_outside_source_boundary(self):
        self.write("tool.js", "// SPDX-License-Identifier: Apache-2.0\n")
        self.write("page.html", "<!-- SPDX-License-Identifier: Apache-2.0 -->\n")
        self.write("Makefile", "# SPDX-License-Identifier: Apache-2.0\n")
        result = CHECKER.check_coverage(self.root)
        self.assertEqual(
            (result.source, result.headers, result.declared, result.external, result.missing),
            (0, 0, 0, 0, 0),
        )

    def test_undeclared_source_is_rejected(self):
        self.write("example.py", "print(1)\n")
        self.assert_rejected("missing source licenses")

    def test_string_literal_is_not_a_header(self):
        self.write("example.py", 'value = "# SPDX-License-Identifier: Apache-2.0"\n')
        self.assert_rejected("missing source licenses")

    def test_missing_declared_path_is_rejected(self):
        self.write_reuse("version = 1\n" + self.declaration("missing.py"))
        self.assert_rejected("declared path does not exist")

    def test_non_source_declaration_is_rejected(self):
        self.write("README.md", "text\n")
        self.write_reuse("version = 1\n" + self.declaration("README.md"))
        self.assert_rejected("not a source file or Cargo manifest")

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
        self.assert_rejected("missing source licenses")


if __name__ == "__main__":
    unittest.main()
