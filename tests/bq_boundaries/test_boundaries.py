# SPDX-License-Identifier: Apache-2.0
"""Compare countermodels to the retained independent closed-form oracle."""
import json
from fractions import Fraction
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.bq_boundaries.model import (
    accepts, placements, q_tail_witness, report, twin_capability_worlds,
    twin_liveness_worlds, liveness_curve, worst_adaptive_abstention_rate,
)


class BoundaryTests(unittest.TestCase):
    def test_valid_uniform_null_grid(self):
        checked = 0
        for g in range(3, 8):
            for b in range(g - 1):
                for c in range(b + 1):
                    self.assertLessEqual(placements(g, b, b + 1, c)[-1], Fraction(1, 5))
                    checked += 1
        self.assertEqual(checked, 55)

    def test_capacity_bound_is_not_realized_vote_cap(self):
        expected = {3: '1/12', 4: '4/21', 5: '43/126', 6: '11/21', 8: '8/9', 10: '1'}
        for c, rate in expected.items():
            self.assertEqual(placements(10, 3, 8, c, vote_cap=3)[-1], Fraction(rate))
        self.assertGreater(Fraction(expected[5]), Fraction(1, 5))
        self.assertLess(Fraction(expected[4]), Fraction(1, 5))

    def test_response_selection_breaks_even_valid_capacity_bound(self):
        self.assertEqual(placements(10, 3, 8, 3)[-1], Fraction(1, 12))
        self.assertEqual(placements(10, 3, 8, 3, sampler='responses_only')[-1], 1)

    def test_capability_dependent_order_breaks_uniform_draw(self):
        self.assertEqual(placements(10, 3, 8, 3, sampler='support_first')[-1], 1)
        self.assertTrue(accepts([1, 1]))

    def test_adaptive_abstention_with_fixed_valid_set_remains_bounded(self):
        for c in range(4):
            self.assertLessEqual(worst_adaptive_abstention_rate(10, 3, 8, Fraction(1, 5), c), Fraction(1, 5))

    def test_liveness_curves_match_independent_DP_and_budget_failure(self):
        for c in range(11):
            self.assertEqual(placements(10, 3, 8, c), liveness_curve(10, 3, c, {8: Fraction(1)}, Fraction(1, 5)))
        self.assertEqual(placements(10, 3, 8, 8)[5], 1)
        self.assertEqual(placements(10, 3, 8, 7)[5], Fraction(53, 60))
        self.assertLess(Fraction(53, 60), Fraction(19, 20))

    def test_same_full_transcript_does_not_reveal_unused_capabilities(self):
        worlds = twin_capability_worlds()
        self.assertEqual(worlds[0]['public'], worlds[1]['public'])
        self.assertNotEqual(worlds[0]['actual_C'], worlds[1]['actual_C'])
        for w in worlds:
            supports = {i for i, x in enumerate(w['public']['observations']) if x}
            self.assertTrue(supports <= set(w['capable_units']))
            self.assertEqual(len(w['capable_units']), w['actual_C'])

    def test_mean_support_is_not_lower_tail_coverage(self):
        w = q_tail_witness();mass = [(x['support'], Fraction(x['mass'])) for x in w['distribution']]
        self.assertEqual(sum(p for _, p in mass), 1)
        self.assertEqual(sum(m * p for m, p in mass), 8)
        self.assertEqual(sum(p for m, p in mass if m >= 8), Fraction(4, 5))
        self.assertLess(Fraction(w['actual_coverage']), Fraction(w['target_coverage']))

    def test_finite_history_does_not_restrict_unmodeled_target_shift(self):
        a, b = twin_liveness_worlds()
        self.assertEqual(a['public_history'], b['public_history'])
        self.assertEqual(placements(10, 3, 8, a['target_correct_support'])[-1], 1)
        self.assertEqual(placements(10, 3, 8, b['target_correct_support'])[-1], 0)

    def test_invalid_parameters_rejected(self):
        for args in [(10, 3, 3, 3), (13, 3, 8, 3), (10, 3, 8, 11), (10, 3, 8, True)]:
            with self.assertRaises(ValueError): placements(*args)
        for kwargs in [{'sampler':'unrecognized'}, {'vote_cap':-1}, {'budget':11}]:
            with self.assertRaises(ValueError): placements(10, 3, 8, 3, **kwargs)

    def test_cli_reproduces_report_and_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            cmd = [sys.executable, '-B', str(ROOT/'scripts/check-bq-boundaries.py'), '--report', str(path)]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
            raw = path.read_bytes();data = json.loads(raw);source = data.pop('source_sha256')
            self.assertEqual(data, report());self.assertEqual(len(source), 6)
            self.assertNotEqual(subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode, 0)
            self.assertEqual(path.read_bytes(), raw)


if __name__ == '__main__': unittest.main()
