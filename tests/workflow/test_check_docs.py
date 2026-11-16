# SPDX-License-Identifier: Apache-2.0
"""Guard tests for the check-docs Markdown fast path in the Makefile.

``make check-docs`` runs the local ``check`` target plus the documentary
checks that read Markdown files.  A check appended to the ``make test``
closure but omitted from ``check-docs`` would silently drop out of the fast
CI lane, so this test walks both closures and fails when a test-closure
target reads a Markdown file while no check-docs-closure target runs it.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / 'Makefile'

_ASSIGNMENT = re.compile(r'^[A-Za-z_.][A-Za-z0-9_.-]*\s*(?:\?|\+|:|!)?=')
_RULE = re.compile(r'^([^#\s][^:=]*?)\s*:(?!=)\s*(.*)$')
_TARGET = re.compile(r'^[A-Za-z0-9_.-]+$')
_SCRIPT = re.compile(r'scripts/[\w./-]+\.py')
_DISCOVER = re.compile(r'\bunittest\s+discover\b')
_DISCOVER_DIR = re.compile(r'(?:^|\s)-s\s+([A-Za-z0-9_./-]+)')
_TESTS_DIR = re.compile(r'(?<![\w./-])(tests/[\w/]+)')
_MD_LITERAL = re.compile(r'''['"]([A-Za-z0-9_./-]+\.md)['"]''')


def logical_lines(text):
    """Join Makefile lines that continue with a trailing backslash."""
    lines = []
    current = None
    for raw in text.splitlines():
        if current is None:
            current = raw
        else:
            current = current + ' ' + raw.strip()
        if current.rstrip().endswith('\\'):
            current = current.rstrip()[:-1]
            continue
        lines.append(current)
        current = None
    if current is not None:
        lines.append(current)
    return lines


def parse_rules(text):
    """Parse rules, merging duplicate targets and continued prerequisites.

    Returns a mapping of target name to ``{'deps': set, 'recipe': list}``.
    Variable assignments, comments, and directives are not rules; a recipe
    line is any line starting with a tab directly after a rule.
    """
    rules = {}
    current = []
    for line in logical_lines(text):
        if line.startswith('\t'):
            for target in current:
                rules[target]['recipe'].append(line.strip())
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or _ASSIGNMENT.match(line):
            current = []
            continue
        match = _RULE.match(line)
        if not match:
            current = []
            continue
        targets = [part for part in match.group(1).split() if _TARGET.match(part)]
        deps = {part for part in match.group(2).split() if _TARGET.match(part)}
        for target in targets:
            rule = rules.setdefault(target, {'deps': set(), 'recipe': []})
            rule['deps'].update(deps)
        current = targets
    return rules


def closure(rules, roots):
    """Return the roots and every target reachable through prerequisites."""
    seen = set()
    pending = list(roots)
    while pending:
        target = pending.pop()
        if target in seen:
            continue
        seen.add(target)
        pending.extend(rules.get(target, {}).get('deps', ()))
    return seen


def target_scripts(recipe):
    """Return the repository-relative scripts/*.py paths a recipe invokes."""
    scripts = set()
    for line in recipe:
        scripts.update(_SCRIPT.findall(line))
    return scripts


def discover_dirs(recipe):
    """Return the unittest discovery directories a recipe names with ``-s``."""
    directories = set()
    for line in recipe:
        if not _DISCOVER.search(line):
            continue
        literal = {part for part in _DISCOVER_DIR.findall(line)
                   if not part.startswith('$')}
        if literal:
            directories.update(literal)
        else:
            # The directory is hidden behind a variable; fall back to a
            # literal tests/ path on the same line, when one is present.
            directories.update(_TESTS_DIR.findall(line))
    return directories


def md_literals(path):
    """Return the Markdown path literals quoted by a Python source file.

    A glob pattern and the bare suffix ``.md`` are not paths, so they are
    ignored; a path built from string parts is invisible to this heuristic.
    """
    try:
        text = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return set()
    literals = set()
    for literal in _MD_LITERAL.findall(text):
        if '*' in literal or literal.rsplit('/', 1)[-1] == '.md':
            continue
        literals.add(literal)
    return literals


def directory_reads_markdown(directory):
    """Whether a discovery directory contains a Python file reading Markdown."""
    root = ROOT / directory
    if not root.is_dir():
        return False
    return any(md_literals(source) for source in root.rglob('*.py'))


def find_uncovered(makefile_text):
    """Return test-closure targets whose Markdown readers check-docs skips.

    A script or discovery directory counts as covered when any target in the
    check-docs closure references it.  A test-closure target is reported when
    it references an uncovered Markdown reader, unless another check-docs
    target covers the same script or directory.
    """
    rules = parse_rules(makefile_text)
    fast_targets = closure(rules, ['check-docs'])
    covered_scripts = set()
    covered_dirs = set()
    for target in fast_targets:
        recipe = rules.get(target, {}).get('recipe', ())
        covered_scripts.update(target_scripts(recipe))
        covered_dirs.update(discover_dirs(recipe))
    uncovered = set()
    for target in closure(rules, ['test']):
        recipe = rules.get(target, {}).get('recipe', ())
        if any(md_literals(script)
               for script in target_scripts(recipe) - covered_scripts):
            uncovered.add(target)
        if any(directory_reads_markdown(directory)
               for directory in discover_dirs(recipe) - covered_dirs):
            uncovered.add(target)
    return uncovered


class CheckDocsGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.makefile = MAKEFILE.read_text(encoding='utf-8')
        cls.rules = parse_rules(cls.makefile)

    def test_check_docs_covers_all_markdown_readers(self):
        self.assertEqual(find_uncovered(self.makefile), set())

    def test_check_docs_includes_check(self):
        self.assertIn('check', closure(self.rules, ['check-docs']))

    def test_check_docs_excludes_heavy_targets(self):
        fast = closure(self.rules, ['check-docs'])
        for target in ('test-singlehost', 'test-multinode',
                       'test-authority', 'test-claim-codec'):
            with self.subTest(target=target):
                self.assertNotIn(target, fast)

    def test_missing_dependency_is_detected(self):
        needle = '  test-profile-digest \\\n'
        self.assertEqual(self.makefile.count(needle), 1,
                         'the counterexample must remove exactly one line')
        patched = self.makefile.replace(needle, '')
        self.assertNotEqual(patched, self.makefile)
        self.assertIn('test-profile-digest', find_uncovered(patched))

    def test_markdown_literal_detection(self):
        found = md_literals(ROOT / 'scripts/check-profile-digest.py')
        self.assertIn('docs/03-protocol/verification-profile-schema.md', found)

    def test_license_suffix_not_a_path(self):
        found = md_literals(ROOT / 'scripts/check-license-coverage.py')
        self.assertEqual(found, set())

    def test_parser_merges_continued_and_appended_rules(self):
        self.assertIn('test-profile-digest', self.rules['check-docs']['deps'])
        self.assertIn('test-profile-digest', self.rules['test']['deps'])
        self.assertIn('tests/workflow', discover_dirs(self.rules['test-python']['recipe']))

    def test_recipe_script_extraction(self):
        recipe = ['\t$(PYTHON) -B scripts/check-profile-digest.py --report x']
        self.assertEqual(target_scripts(recipe), {'scripts/check-profile-digest.py'})


if __name__ == '__main__':
    unittest.main()
