# SPDX-License-Identifier: Apache-2.0
"""The encoded positive-weight support must fit its finite population."""
import copy
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest

from test_validator import bounded_profile
from tools.verification_profile import codec, method_rules
from tools.verification_profile.validator import validate

ROOT = Path(__file__).resolve().parents[2]
DRIVER = runpy.run_path(str(ROOT / 'scripts/check-method-matrices.py'))


class MixtureSupportDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix='aclt-mixture-domain-')
        cls.addClassCleanup(temporary.cleanup)
        cls.binary = Path(temporary.name) / 'codec'
        subprocess.run([
            'rustc', '--edition=2021', '-D', 'warnings',
            str(ROOT / 'tools/verification_profile/rust/main.rs'), '-o', str(cls.binary),
        ], check=True, capture_output=True, timeout=120)

    def test_disabled_digest_policy_keeps_records_and_rejects_bad_shape(self):
        from test_codec import native
        from test_profile_digest import fixture
        from tools.verification_profile import profile
        for mode, value, inspect, field in (
            ('template', native('template'), lambda raw: codec.inspect('template', raw), 'header'),
            ('profile-digest', fixture(), lambda raw: profile.inspect('profile-digest', raw), None),
        ):
            key = 'digest' if field else 'profile_digest'
            holder = value[field] if field else value
            holder[key] = b'z' * 32
            before = copy.deepcopy(value)
            raw = codec.encode(value)
            process = subprocess.run([str(self.binary)], input=mode + '\t' + raw.hex() + '\n',
                                     text=True, capture_output=True, check=True, timeout=30)
            python = inspect(raw)
            self.assertEqual(json.loads(process.stdout), python)
            self.assertEqual(python['sha_consistency_policy'], 'DISABLED')
            self.assertEqual(value, before)
            holder[key] = b'short'
            raw = codec.encode(value)
            with self.assertRaises(codec.CodecError):
                inspect(raw)
            process = subprocess.run([str(self.binary)], input=mode + '\t' + raw.hex() + '\n',
                                     text=True, capture_output=True, check=True, timeout=30)
            self.assertIn('error', json.loads(process.stdout))

    def test_bootstrap_versions_share_the_population_bound(self):
        for version in ('1', '2'):
            for m, accepted in ((4, True), (5, True), (6, False), (2**64 - 1, False)):
                with self.subTest(version=version, m=m):
                    profile = bounded_profile()
                    profile['schema_version'] = version
                    profile['method_parameters']['mixture_weights'] = [
                        {'m': str(m), 'weight': ['1', '1']},
                    ]
                    issues = validate(profile)
                    self.assertEqual(not issues, accepted)
                    if not accepted:
                        self.assertIn('SV-11', {issue.sv_id for issue in issues})

    def test_zero_weight_rows_keep_the_existing_encoding_policy(self):
        profile = bounded_profile()
        profile['method_parameters']['mixture_weights'] = [
            {'m': '0', 'weight': ['0', '1']},
            {'m': '5', 'weight': ['1', '1']},
        ]
        original = copy.deepcopy(profile)
        self.assertEqual(validate(profile), [])
        self.assertEqual(profile, original)

    def test_v2_python_and_rust_agree_on_support_boundaries(self):
        for weights, accepted in (
            ([(3, [1, 1])], True),
            ([(5, [1, 1])], True),
            ([(6, [1, 1])], False),
            ([(3, [1, 2]), (6, [1, 2])], False),
            ([(0, [0, 1]), (5, [1, 1])], True),
        ):
            with self.subTest(weights=weights):
                value, pin = DRIVER['fixture']('REEXEC_BOUNDED')
                value['profile']['method_parameters']['mixture_weights'] = [
                    {'m': m, 'weight': weight} for m, weight in weights
                ]
                DRIVER['seal'](value)
                raw = codec.encode(value)
                request = 'method-matrix:' + pin.hex() + '\t' + raw.hex() + '\n'
                process = subprocess.run(
                    [str(self.binary)], input=request, text=True,
                    capture_output=True, check=True, timeout=30,
                )
                rust = json.loads(process.stdout)
                if accepted:
                    python = method_rules.inspect(raw, pin)
                    self.assertEqual(rust, python)
                    self.assertFalse(python['full_schema_valid'])
                else:
                    with self.assertRaisesRegex(codec.CodecError, 'SV-11:'):
                        method_rules.inspect(raw, pin)
                    self.assertIn('SV-11:', rust['error'])


if __name__ == '__main__':
    unittest.main()
