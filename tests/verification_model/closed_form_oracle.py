"""Independent closed-form and exhaustive oracle for ACLt verification tests."""

from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from math import comb
from typing import Iterable, Mapping


INFINITY = "POSITIVE_INFINITY"


def falling(value: int, count: int) -> int:
    result = 1
    for offset in range(count):
        result *= value - offset
    return result


def component_capital(
    population: int,
    wrong_bound: int,
    alternative: int,
    draws: int,
    successes: int,
) -> Fraction | str:
    """Closed-form ordered-path likelihood ratio.

    The explicit ordering of exceptional states avoids ambiguous ``0/0``.
    """
    failures = draws - successes
    if successes > wrong_bound:
        return INFINITY
    if failures > population - alternative:
        return Fraction(0)
    numerator = falling(alternative, successes) * falling(
        population - alternative, failures
    )
    denominator = falling(wrong_bound, successes) * falling(
        population - wrong_bound, failures
    )
    if denominator == 0:
        raise AssertionError("closed-form state classification left an undefined ratio")
    return Fraction(numerator, denominator)


def mixture_capital(
    population: int,
    wrong_bound: int,
    weights: Mapping[int, Fraction],
    draws: int,
    successes: int,
) -> Fraction | str:
    result = Fraction(0)
    for alternative, weight in weights.items():
        value = component_capital(
            population, wrong_bound, alternative, draws, successes
        )
        if value == INFINITY:
            return INFINITY
        result += weight * value
    return result


def accepts_path(
    population: int,
    wrong_bound: int,
    alternative: int,
    epsilon_f: Fraction,
    observations: Iterable[int],
) -> bool:
    threshold = Fraction(1) / epsilon_f
    successes = 0
    for draws, observation in enumerate(observations, start=1):
        successes += observation
        capital = component_capital(
            population, wrong_bound, alternative, draws, successes
        )
        if capital == INFINITY or capital >= threshold:
            return True
        if capital == 0:
            return False
    return False


def exact_capability_placement_rate(
    population: int,
    wrong_bound: int,
    alternative: int,
    epsilon_f: Fraction,
    capability_count: int,
    vote_budget: int,
) -> Fraction:
    """Enumerate uniformly random placements of a fixed capability set.

    Every capable unit supports until ``vote_budget`` has been consumed.  When
    ``capability_count > vote_budget`` the realized support positions depend on
    draw order, which supplies the counterexample to a mere realized-vote cap.
    """
    accepted = 0
    total = comb(population, capability_count)
    for positions in combinations(range(population), capability_count):
        capable = set(positions)
        budget = vote_budget
        path: list[int] = []
        for position in range(population):
            support = int(position in capable and budget > 0)
            path.append(support)
            budget -= support
        accepted += accepts_path(
            population, wrong_bound, alternative, epsilon_f, path
        )
    return Fraction(accepted, total)


def worst_adaptive_abstention_rate(
    population: int,
    wrong_bound: int,
    alternative: int,
    epsilon_f: Fraction,
    capability_count: int,
) -> Fraction:
    """Exact optimal policy for a fixed capability set.

    Membership is fixed before the uniform draw order.  When a capable unit is
    drawn, the adversary observes the complete history and chooses support or
    abstention to maximize eventual acceptance.
    """
    threshold = Fraction(1) / epsilon_f

    @lru_cache(maxsize=None)
    def value(draws: int, successes: int, capable_remaining: int) -> Fraction:
        capital = component_capital(
            population, wrong_bound, alternative, draws, successes
        )
        if capital == INFINITY or capital >= threshold:
            return Fraction(1)
        if capital == 0 or draws == population:
            return Fraction(0)
        remaining = population - draws
        incapable_probability = Fraction(remaining - capable_remaining, remaining)
        capable_probability = Fraction(capable_remaining, remaining)
        after_incapable = value(draws + 1, successes, capable_remaining)
        if capable_remaining == 0:
            return after_incapable
        after_abstain = value(draws + 1, successes, capable_remaining - 1)
        after_support = value(draws + 1, successes + 1, capable_remaining - 1)
        return (
            incapable_probability * after_incapable
            + capable_probability * max(after_abstain, after_support)
        )

    return value(0, 0, capability_count)


def liveness_curve(
    population: int,
    wrong_bound: int,
    true_support: int,
    weights: Mapping[int, Fraction],
    epsilon_f: Fraction,
    max_draws: int | None = None,
) -> list[Fraction]:
    """Exact absorption curve under a fixed true support total."""
    limit = population if max_draws is None else min(max_draws, population)
    threshold = Fraction(1) / epsilon_f
    live: dict[tuple[int, int], Fraction] = {(0, 0): Fraction(1)}
    absorbed = Fraction(0)
    curve: list[Fraction] = []
    for _ in range(limit):
        next_live: dict[tuple[int, int], Fraction] = {}
        for (draws, successes), probability in live.items():
            remaining = population - draws
            support_probability = Fraction(true_support - successes, remaining)
            for observation, branch_probability in (
                (1, support_probability),
                (0, 1 - support_probability),
            ):
                if branch_probability == 0:
                    continue
                key = (draws + 1, successes + observation)
                next_live[key] = (
                    next_live.get(key, Fraction(0))
                    + probability * branch_probability
                )
        live = {}
        for (draws, successes), probability in next_live.items():
            capital = mixture_capital(
                population, wrong_bound, weights, draws, successes
            )
            if capital == INFINITY or capital >= threshold:
                absorbed += probability
            elif capital != 0:
                live[(draws, successes)] = probability
        curve.append(absorbed)
    return curve


def exact_liveness_curve_by_placement(
    population: int,
    wrong_bound: int,
    true_support: int,
    weights: Mapping[int, Fraction],
    epsilon_f: Fraction,
) -> list[Fraction]:
    """Independent exhaustive oracle for the DP curve."""
    hit_counts = [0] * population
    total = comb(population, true_support)
    threshold = Fraction(1) / epsilon_f
    for positions in combinations(range(population), true_support):
        support_positions = set(positions)
        successes = 0
        hit: int | None = None
        for draws in range(1, population + 1):
            successes += int(draws - 1 in support_positions)
            capital = mixture_capital(
                population, wrong_bound, weights, draws, successes
            )
            if capital == INFINITY or capital >= threshold:
                hit = draws
                break
            if capital == 0:
                break
        if hit is not None:
            for index in range(hit - 1, population):
                hit_counts[index] += 1
    return [Fraction(count, total) for count in hit_counts]


def required_draws(curve: list[Fraction], delta_l: Fraction) -> int | None:
    target = Fraction(1) - delta_l
    for draws, probability in enumerate(curve, start=1):
        if probability >= target:
            return draws
    return None

