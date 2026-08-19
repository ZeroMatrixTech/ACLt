"""ACLt finite-population verification model: sequential reference implementation.

Only Python's standard library is used.  All protocol arithmetic is exact
``fractions.Fraction`` arithmetic; floating point is deliberately absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Mapping


CONTINUE = "CONTINUE"
ACCEPT = "ACCEPT"
UNRESOLVED = "UNRESOLVED"
ASSUMPTION_INVALID = "ASSUMPTION_INVALID"
NULL_BOUND_EXACTLY_EXCEEDED = "NULL_BOUND_EXACTLY_EXCEEDED"
COMPONENT_LIVENESS_INVALIDATED = "COMPONENT_LIVENESS_INVALIDATED"


@dataclass(frozen=True)
class Parameters:
    population: int
    wrong_capability_bound: int
    minimum_correct_support: int
    epsilon_f: Fraction

    def __post_init__(self) -> None:
        g = self.population
        b = self.wrong_capability_bound
        q = self.minimum_correct_support
        if not (0 <= b < q <= g):
            raise ValueError("parameters must satisfy 0 <= B < Q <= G")
        if not (Fraction(0) < self.epsilon_f < Fraction(1)):
            raise ValueError("epsilon_f must lie strictly between zero and one")

    @property
    def threshold(self) -> Fraction:
        return Fraction(1, 1) / self.epsilon_f


@dataclass(frozen=True)
class StepResult:
    t: int
    successes: int
    component_capitals: Mapping[int, Fraction]
    mixture_capital: Fraction | None
    component_events: tuple[tuple[int, str], ...]
    aggregate_state: str
    decision: str | None


@dataclass
class VerificationRound:
    """Sequential likelihood-ratio implementation.

    ``weights`` is a frozen convex mixture over alternative finite-population
    support totals.  A zero component remains zero and its mass is never
    redistributed after observations.
    """

    parameters: Parameters
    weights: Mapping[int, Fraction] | None = None
    t: int = 0
    successes: int = 0
    component_capitals: dict[int, Fraction] = field(init=False)
    aggregate_state: str = field(default=CONTINUE, init=False)
    decision: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.weights is None:
            self.weights = {self.parameters.minimum_correct_support: Fraction(1)}
        else:
            self.weights = dict(self.weights)
        if not self.weights:
            raise ValueError("at least one mixture component is required")
        if any(weight <= 0 for weight in self.weights.values()):
            raise ValueError("mixture weights must be positive")
        if sum(self.weights.values(), Fraction(0)) != Fraction(1):
            raise ValueError("mixture weights must sum exactly to one")
        g = self.parameters.population
        q = self.parameters.minimum_correct_support
        if any(not (q <= alternative <= g) for alternative in self.weights):
            raise ValueError("every alternative component must satisfy Q <= m <= G")
        self.component_capitals = {m: Fraction(1) for m in self.weights}

    def _mixture_capital(self) -> Fraction:
        return sum(
            (self.weights[m] * capital for m, capital in self.component_capitals.items()),
            Fraction(0),
        )

    def invalidate_assumptions(self) -> StepResult:
        """Fail closed after independent evidence revokes a frozen premise."""
        if self.decision is not None:
            raise RuntimeError("a terminal verification round cannot be changed")
        self.aggregate_state = ASSUMPTION_INVALID
        self.decision = UNRESOLVED
        return self.snapshot()

    def snapshot(
        self, component_events: tuple[tuple[int, str], ...] = ()
    ) -> StepResult:
        exact_exceeded = self.aggregate_state == NULL_BOUND_EXACTLY_EXCEEDED
        return StepResult(
            t=self.t,
            successes=self.successes,
            component_capitals=dict(self.component_capitals),
            mixture_capital=None if exact_exceeded else self._mixture_capital(),
            component_events=component_events,
            aggregate_state=self.aggregate_state,
            decision=self.decision,
        )

    def step(self, observation: int) -> StepResult:
        if observation not in (0, 1):
            raise ValueError("observation must be zero or one")
        if self.decision is not None:
            raise RuntimeError("a terminal verification round cannot consume evidence")
        g = self.parameters.population
        b = self.parameters.wrong_capability_bound
        if self.t >= g:
            self.aggregate_state = UNRESOLVED
            self.decision = UNRESOLVED
            return self.snapshot()

        remaining = g - self.t
        null_successes_remaining = b - self.successes

        # This branch is a symbolic protocol state, not floating-point infinity.
        if observation == 1 and null_successes_remaining == 0:
            self.t += 1
            self.successes += 1
            self.aggregate_state = NULL_BOUND_EXACTLY_EXCEEDED
            self.decision = ACCEPT
            return self.snapshot()

        component_events: list[tuple[int, str]] = []
        for alternative, capital in tuple(self.component_capitals.items()):
            if capital == 0:
                continue
            alternative_successes_remaining = alternative - self.successes
            if not (0 <= alternative_successes_remaining <= remaining):
                raise AssertionError("live component is inconsistent with observed history")

            if observation == 1:
                if null_successes_remaining <= 0:
                    raise AssertionError("exact null-bound branch should have handled this step")
                factor = Fraction(
                    alternative_successes_remaining, null_successes_remaining
                )
            else:
                alternative_failures_remaining = remaining - alternative_successes_remaining
                null_failures_remaining = remaining - null_successes_remaining
                if alternative_failures_remaining == 0:
                    self.component_capitals[alternative] = Fraction(0)
                    component_events.append(
                        (alternative, COMPONENT_LIVENESS_INVALIDATED)
                    )
                    continue
                if null_failures_remaining <= 0:
                    raise AssertionError(
                        "a live m>B component cannot outlive exhaustion of null failures"
                    )
                factor = Fraction(
                    alternative_failures_remaining, null_failures_remaining
                )
            self.component_capitals[alternative] = capital * factor

        self.t += 1
        self.successes += observation
        mixture = self._mixture_capital()
        if mixture >= self.parameters.threshold:
            self.aggregate_state = ACCEPT
            self.decision = ACCEPT
        elif all(capital == 0 for capital in self.component_capitals.values()):
            self.aggregate_state = UNRESOLVED
            self.decision = UNRESOLVED
        else:
            self.aggregate_state = CONTINUE
        return self.snapshot(tuple(component_events))
