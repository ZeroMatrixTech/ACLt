# SPDX-License-Identifier: Apache-2.0
"""Exact small-population witnesses for failed B/Q premises.

The sequential evaluator and old closed-form oracle are retained unchanged.
Here all capability placements have equal mass; optional response filtering
and sorting deliberately implement INVALID samplers to expose their effects.
ACCEPT is the mathematical kernel's output, never an authorized TRUSTED.
"""
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/verification_model'))
from recursive_model import ACCEPT, Parameters, VerificationRound
from closed_form_oracle import (
    exact_capability_placement_rate, liveness_curve, required_draws,
    worst_adaptive_abstention_rate,
)


def accepts(path, g=10, b=3, q=8, epsilon=Fraction(1, 5)):
    round_ = VerificationRound(Parameters(g, b, q, epsilon))
    for value in path:
        result = round_.step(value)
        if result.decision is not None:
            return result.decision == ACCEPT
    return False


def placements(g, b, q, capability_count, *, vote_cap=None, sampler='uniform', budget=None):
    """Exhaustive recursive-kernel absorption curve; bounded at G<=12.

    A fixed capable set is permuted uniformly. Each capable unit supports until
    vote_cap is exhausted. Time in the curve counts consumed observations;
    responses_only discards zeros and therefore corrupts that clock on purpose.
    """
    Parameters(g, b, q, Fraction(1, 5))
    if any(type(v) is not int for v in (g, b, q, capability_count)) or not 1 <= g <= 12 or not 0 <= capability_count <= g:
        raise ValueError('integer toy population/ability count required, G<=12')
    vote_cap = capability_count if vote_cap is None else vote_cap
    budget = g if budget is None else budget
    if type(vote_cap) is not int or not 0 <= vote_cap <= g or type(budget) is not int or not 1 <= budget <= g:
        raise ValueError('bounded integer vote cap/budget required')
    if sampler not in {'uniform', 'responses_only', 'support_first'}:
        raise ValueError('unknown toy sampler')
    hits = [0] * budget
    total = comb(g, capability_count)
    for positions in combinations(range(g), capability_count):
        capable = set(positions); left = vote_cap; path = []
        for i in range(g):
            vote = int(i in capable and left > 0)
            left -= vote
            path.append(vote)
        if sampler == 'responses_only':
            path = [x for x in path if x]
        elif sampler == 'support_first':
            path.sort(reverse=True)
        round_ = VerificationRound(Parameters(g, b, q, Fraction(1, 5)))
        for draw, vote in enumerate(path[:budget], 1):
            result = round_.step(vote)
            if result.decision == ACCEPT:
                for index in range(draw - 1, budget):
                    hits[index] += 1
                break
            if result.decision is not None:
                break
    return [Fraction(n, total) for n in hits]


def twin_capability_worlds():
    """Same full public transcript; hidden unused capabilities differ."""
    path = [0] * 7 + [1] * 3
    public = {'claimed_units': list(range(10)), 'draw_order': list(range(10)),
              'observations': path, 'declared_B': 3}
    return [
        {'name': 'fixed-three', 'public': public, 'capable_units': [7, 8, 9], 'actual_C': 3},
        {'name': 'all-capable-selective-abstention', 'public': dict(public),
         'capable_units': list(range(10)), 'actual_C': 10},
    ]


def twin_liveness_worlds():
    """Identical finite history, unrestricted target-task domain shift."""
    history = {'truth_labeled_training_tasks': ['fixture-1', 'fixture-2', 'fixture-3'],
               'correct_support_counts': [10, 10, 10], 'G': 10}
    return [
        {'name': 'same-scope-support', 'public_history': history, 'target_correct_support': 8},
        {'name': 'unobserved-trigger-or-outage', 'public_history': dict(history), 'target_correct_support': 0},
    ]


def q_tail_witness():
    """Mean support=8, but P(M>=8)=4/5, not 19/20.

    This is a stipulated two-point task-level distribution, not a fitted
    distribution, independence assertion, or empirical calibration result.
    """
    mass = [(0, Fraction(1, 5)), (10, Fraction(4, 5))]
    return {'distribution': [{'support': m, 'mass': str(p)} for m, p in mass],
            'mean_support': str(sum((m * p for m, p in mass), Fraction())),
            'Q': 8, 'actual_coverage': str(sum((p for m, p in mass if m >= 8), Fraction())),
            'claimed_delta_Q': '1/20', 'target_coverage': '19/20'}


def report():
    rows = []
    for c in [3, 4, 5, 6, 8, 10]:
        rate = placements(10, 3, 8, c, vote_cap=3)[-1]
        oracle = exact_capability_placement_rate(10, 3, 8, Fraction(1, 5), c, 3)
        if rate != oracle:
            raise AssertionError('recursive/closed-form placement disagreement')
        rows.append({'actual_C': c, 'vote_cap': 3, 'false_acceptance': str(rate),
                     'exceeds_epsilon': rate > Fraction(1, 5), 'placements': comb(10, c)})
    nominal = placements(10, 3, 8, 8)
    n = required_draws(nominal, Fraction(1, 20))
    shifted = placements(10, 3, 8, 7)
    for c in range(11):
        curve = placements(10, 3, 8, c)
        if curve != liveness_curve(10, 3, c, {8: Fraction(1)}, Fraction(1, 5)):
            raise AssertionError('recursive enumeration/closed-form DP disagreement')
    cases = [
        {'id': 'BQ1-CAPACITY', 'failed_premise': 'actual votes <= B is not capacity C <= B', 'rates': rows},
        {'id': 'BQ1-SYBIL', 'failed_premise': 'observed IDs/transcript do not identify unused capability or control', 'worlds': twin_capability_worlds()},
        {'id': 'BQ1-COMMON-MODE', 'failed_premise': 'all named units may share a wrong-support trigger',
         'assumed_G': 10, 'assumed_B': 3, 'actual_C': 10,
         'false_acceptance_with_three_vote_cap': str(placements(10, 3, 8, 10, vote_cap=3)[-1]),
         'conservative_single_cluster': {'G': 1, 'B_needed': 1, 'B_less_than_G': False}},
        {'id': 'BQ1-RESPONSE-FILTER', 'failed_premise': 'response-conditioned order is not the frozen uniform draw',
         'actual_C': 3, 'uniform_fixed_slots_rate': str(rows[0]['false_acceptance']),
         'discard_nonsupport_rate': str(placements(10, 3, 8, 3, sampler='responses_only')[-1])},
        {'id': 'BQ1-ORDER', 'failed_premise': 'support-first order depends on capability', 'actual_C': 3,
         'support_first_rate': str(placements(10, 3, 8, 3, sampler='support_first')[-1])},
        {'id': 'BQ1-Q-MEAN', 'failed_premise': 'mean is not task-level lower-tail coverage', **q_tail_witness()},
        {'id': 'BQ1-Q-SHIFT', 'failed_premise': 'finite observed history alone does not restrict unseen task distribution',
         'worlds': twin_liveness_worlds()},
        {'id': 'BQ1-Q-BUDGET', 'failed_premise': 'actual correct-support count below frozen Q',
         'declared_Q': 8, 'actual_support': 7, 'delta_L': '1/20', 'required_draws_under_Q': n,
         'nominal_probability_at_budget': str(nominal[n - 1]),
         'actual_probability_at_budget': str(shifted[n - 1]), 'target_probability': '19/20'},
    ]
    return {'status': 'PASS', 'kind': 'exact-toy-countermodels-not-deployment-calibration',
            'algorithm_id': 'finite-population-boundary-lr-v1',
            'parameters': {'G': 10, 'B': 3, 'Q': 8, 'epsilon_F': '1/5'},
            'cases': cases, 'case_count': len(cases),
            'controls': {'valid_uniform_null_rate': rows[0]['false_acceptance'],
                         'worst_fixed_set_adaptive_abstention_rate': str(worst_adaptive_abstention_rate(10, 3, 8, Fraction(1, 5), 3)),
                         'recursive_vs_closed_form_capacity_rows': len(rows),
                         'recursive_enumeration_vs_DP_curves': 11},
            'limits': ['small finite binary single-candidate toy model, not production probability',
                       'models stipulate latent truth/capability; no live identity inference or empirical B/Q estimate',
                       'ACCEPT denotes kernel output under supplied parameters; no TRUSTED authorization',
                       'B/Q are not established, no Gate/OQ/assurance change, no dualhost run']}
