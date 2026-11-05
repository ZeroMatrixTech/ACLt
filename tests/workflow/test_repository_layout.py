"""The installed repository must expose the tested generation and its workflow."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = 'experiments/aclt-minimal-verifier-state3'

class RepositoryLayoutTests(unittest.TestCase):
    def test_entrypoints_select_current_generation(self):
        config = json.loads((ROOT / '.aclt-flow/template.json').read_text())
        job = next(j for j in config['jobs'] if j['id'] == 'singlehost')
        self.assertEqual(job['command'], ['bash', EXPERIMENT + '/scripts/run-ubuntu.sh'])
        self.assertIn('bash ' + job['command'][1], (ROOT / 'scripts/run-singlehost.sh').read_text())
        for pattern in job['inputs']:
            self.assertTrue(list(ROOT.glob(pattern)), pattern)
        runner = (ROOT / job['command'][1]).read_text()
        for name in ['check-strict.py', 'check-strict-adversarial.py', 'check-differential.py']:
            self.assertIn('python3 scripts/' + name, runner)
            self.assertTrue((ROOT / EXPERIMENT / 'scripts' / name).is_file())
        for script in ['repository_files.py', 'aclt-flow.py']:
            text = (ROOT / 'scripts' / script).read_text()
            self.assertIn(EXPERIMENT, text)

    def test_workflow_is_installed_at_documented_paths(self):
        for name in ['.aclt-flow/.gitignore', 'docs/workflow/README.md', 'tests/workflow/test_flow.py']:
            self.assertTrue((ROOT / name).is_file(), name)
        self.assertFalse((ROOT / 'workflow').exists())

    def test_delivery_manifests_match_installed_files(self):
        for root, name in [(ROOT, 'SINGLEHOST-SHA256SUMS'), (ROOT, 'WORKFLOW-SHA256SUMS'),
                           (ROOT / EXPERIMENT, 'SHA256SUMS'),
                           (ROOT / 'experiments/aclt-multinode-admission', 'SHA256SUMS')]:
            for line in (root / name).read_text().splitlines():
                digest, relative = line.split('  ', 1)
                with self.subTest(manifest=name, path=relative):
                    self.assertEqual(hashlib.sha256((root / relative).read_bytes()).hexdigest(), digest)
