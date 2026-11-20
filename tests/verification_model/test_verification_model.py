from __future__ import annotations

import hashlib
import json
import unittest
from fractions import Fraction
from itertools import product
from pathlib import Path

from closed_form_oracle import (
    INFINITY,
    component_capital,
    exact_capability_placement_rate,
    exact_liveness_curve_by_placement,
    liveness_curve,
    required_draws,
    worst_adaptive_abstention_rate,
)
from recursive_model import (
    ACCEPT,
    ASSUMPTION_INVALID,
    COMPONENT_LIVENESS_INVALIDATED,
    CONTINUE,
    NULL_BOUND_EXACTLY_EXCEEDED,
    UNRESOLVED,
    Parameters,
    VerificationRound,
)


HERE = Path(__file__).resolve().parent


class DifferentialModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parameters = Parameters(10, 3, 8, Fraction(1, 5))

    def test_recursive_and_closed_form_match_on_every_binary_path(self) -> None:
        weights = {8: Fraction(1, 2), 9: Fraction(1, 3), 10: Fraction(1, 6)}
        compared = 0
        for path in product((0, 1), repeat=self.parameters.population):
            round_ = VerificationRound(self.parameters, weights)
            for observation in path:
                result = round_.step(observation)
                if result.aggregate_state == NULL_BOUND_EXACTLY_EXCEEDED:
                    self.assertGreater(result.successes, self.parameters.wrong_capability_bound)
                    break
                for alternative, actual in result.component_capitals.items():
                    expected = component_capital(
                        self.parameters.population,
                        self.parameters.wrong_capability_bound,
                        alternative,
                        result.t,
                        result.successes,
                    )
                    self.assertNotEqual(expected, INFINITY)
                    self.assertEqual(actual, expected)
                    compared += 1
                if result.decision is not None:
                    break
        self.assertGreater(compared, 1000)

    def test_recursive_closed_form_grid(self) -> None:
        compared = 0
        for population in range(4, 8):
            for wrong_bound in range(population - 1):
                for minimum_support in range(wrong_bound + 1, population + 1):
                    parameters = Parameters(
                        population, wrong_bound, minimum_support, Fraction(1, 5)
                    )
                    for path in product((0, 1), repeat=population):
                        round_ = VerificationRound(parameters)
                        for observation in path:
                            result = round_.step(observation)
                            if result.aggregate_state == NULL_BOUND_EXACTLY_EXCEEDED:
                                break
                            expected = component_capital(
                                population,
                                wrong_bound,
                                minimum_support,
                                result.t,
                                result.successes,
                            )
                            self.assertNotEqual(expected, INFINITY)
                            self.assertEqual(
                                result.component_capitals[minimum_support], expected
                            )
                            compared += 1
                            if result.decision is not None:
                                break
        self.assertGreater(compared, 5000)

    def test_fixed_capability_counterexample_rates_are_exact(self) -> None:
        expected = {
            3: Fraction(1, 12),
            4: Fraction(4, 21),
            5: Fraction(43, 126),
            6: Fraction(11, 21),
            8: Fraction(8, 9),
            10: Fraction(1),
        }
        for capability_count, rate in expected.items():
            with self.subTest(capability_count=capability_count):
                self.assertEqual(
                    exact_capability_placement_rate(
                        10,
                        3,
                        8,
                        Fraction(1, 5),
                        capability_count,
                        vote_budget=3,
                    ),
                    rate,
                )

    def test_worst_adaptive_abstention_with_fixed_capability_set_is_safe(self) -> None:
        rate = worst_adaptive_abstention_rate(
            10, 3, 8, Fraction(1, 5), capability_count=3
        )
        self.assertEqual(rate, Fraction(1, 12))
        self.assertLessEqual(rate, Fraction(1, 5))

    def test_fixed_capability_adaptive_grid_respects_type_one_bound(self) -> None:
        epsilon_f = Fraction(1, 5)
        checked = 0
        for population in range(4, 10):
            for wrong_bound in range(population - 1):
                for alternative in range(wrong_bound + 1, population + 1):
                    rate = worst_adaptive_abstention_rate(
                        population,
                        wrong_bound,
                        alternative,
                        epsilon_f,
                        capability_count=wrong_bound,
                    )
                    self.assertLessEqual(rate, epsilon_f)
                    checked += 1
        self.assertGreater(checked, 100)

    def test_component_death_is_local_and_weights_are_not_renormalized(self) -> None:
        parameters = Parameters(10, 3, 8, Fraction(1, 1000))
        weights = {8: Fraction(1, 2), 9: Fraction(1, 2)}
        round_ = VerificationRound(parameters, weights)
        round_.step(0)
        result = round_.step(0)
        self.assertEqual(result.aggregate_state, CONTINUE)
        self.assertIsNone(result.decision)
        self.assertEqual(result.component_capitals[8], Fraction(1, 21))
        self.assertEqual(result.component_capitals[9], Fraction(0))
        self.assertEqual(result.mixture_capital, Fraction(1, 42))
        self.assertIn((9, COMPONENT_LIVENESS_INVALIDATED), result.component_events)
        self.assertEqual(round_.weights, weights)

    def test_p_zero_failure_is_regular_arithmetic(self) -> None:
        parameters = Parameters(10, 3, 8, Fraction(1, 1000))
        round_ = VerificationRound(parameters)
        for observation in (1, 1, 1, 0):
            result = round_.step(observation)
        self.assertEqual(result.aggregate_state, CONTINUE)
        self.assertEqual(result.component_capitals[8], Fraction(16))
        self.assertEqual(result.mixture_capital, Fraction(16))

    def test_p_zero_success_is_symbolic_exact_rejection(self) -> None:
        parameters = Parameters(10, 3, 8, Fraction(1, 1000))
        round_ = VerificationRound(parameters)
        for observation in (1, 1, 1, 1):
            result = round_.step(observation)
        self.assertEqual(result.aggregate_state, NULL_BOUND_EXACTLY_EXCEEDED)
        self.assertEqual(result.decision, ACCEPT)
        self.assertIsNone(result.mixture_capital)

    def test_independent_assumption_revocation_fails_closed(self) -> None:
        round_ = VerificationRound(self.parameters)
        result = round_.invalidate_assumptions()
        self.assertEqual(result.aggregate_state, ASSUMPTION_INVALID)
        self.assertEqual(result.decision, UNRESOLVED)

    def test_dp_matches_full_placement_enumeration(self) -> None:
        weights = {8: Fraction(1)}
        dp = liveness_curve(10, 3, 8, weights, Fraction(1, 5))
        exhaustive = exact_liveness_curve_by_placement(
            10, 3, 8, weights, Fraction(1, 5)
        )
        self.assertEqual(dp, exhaustive)
        self.assertEqual(
            dp[:6],
            [
                Fraction(0),
                Fraction(28, 45),
                Fraction(28, 45),
                Fraction(8, 9),
                Fraction(8, 9),
                Fraction(1),
            ],
        )
        self.assertEqual(required_draws(dp, Fraction(1, 10)), 6)
        self.assertEqual(required_draws(dp, Fraction(1, 100)), 6)

    def test_dp_quantile_minimality_and_platforms(self) -> None:
        curve = liveness_curve(
            20, 5, 16, {16: Fraction(1)}, Fraction(1, 20)
        )
        self.assertEqual(curve[2], Fraction(28, 57))
        self.assertEqual(curve[3], curve[2])
        self.assertEqual(required_draws(curve, Fraction(1, 100)), 10)
        self.assertLess(curve[8], Fraction(99, 100))
        self.assertGreaterEqual(curve[9], Fraction(99, 100))

    def test_static_json_vectors_match_reference_implementation(self) -> None:
        data = json.loads((HERE / "conformance_vectors.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        for vector in data["vectors"]:
            params = vector["parameters"]
            epsilon_n, epsilon_d = map(int, params["epsilon_f"].split("/"))
            parameters = Parameters(
                params["G"], params["B"], params["Q"], Fraction(epsilon_n, epsilon_d)
            )
            weights = {
                int(component): Fraction(*weight)
                for component, weight in vector["weights"].items()
            }
            round_ = VerificationRound(parameters, weights)
            result = round_.snapshot()
            for observation in vector["path"]:
                result = round_.step(observation)
                if result.decision is not None:
                    break
            self.assertEqual(result.aggregate_state, vector["expected"]["aggregate_state"])
            self.assertEqual(result.decision, vector["expected"]["decision"])
            expected_capital = vector["expected"].get("mixture_capital")
            if expected_capital is not None:
                numerator, denominator = map(int, expected_capital.split("/"))
                self.assertEqual(result.mixture_capital, Fraction(numerator, denominator))

    def test_manifest_records_algorithm_and_assets(self) -> None:
        manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["algorithm_id"], "finite-population-boundary-lr-v1")
        self.assertEqual(manifest["arithmetic"], "exact-rational")
        for filename in manifest["files"]:
            self.assertTrue((HERE / filename).is_file())


if __name__ == "__main__":
    unittest.main()
