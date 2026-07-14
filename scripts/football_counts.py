#!/usr/bin/env python3
"""Shared count-distribution maths for football markets.

Negative Binomial functions use the NB2 ``(mean, alpha)`` parameterization::

    variance = mean + alpha * mean**2

The legacy corners code uses ``r = 1 / alpha``. Explicit converters are kept
here so callers cannot accidentally mix the two dispersion conventions.
"""

from __future__ import annotations

import math
from typing import Iterable, Literal


MIN_PROBABILITY = 1e-9
MIN_MEAN = 0.05
MAX_MEAN = 30.0
MIN_R = 1.25
MAX_R = 500.0
MIN_ALPHA = 1.0 / MAX_R
MAX_ALPHA = 1.0 / MIN_R


def clip_probability(value: float, *, epsilon: float = MIN_PROBABILITY) -> float:
    return max(epsilon, min(1.0 - epsilon, float(value)))


def r_to_alpha(r: float) -> float:
    """Convert legacy NB size/dispersion ``r`` to NB2 ``alpha``."""
    value = float(r)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("r must be a finite positive number")
    return 1.0 / value


def alpha_to_r(alpha: float) -> float:
    """Convert NB2 ``alpha`` to legacy ``r``; alpha=0 is Poisson."""
    value = float(alpha)
    if value < 0.0 or not math.isfinite(value):
        raise ValueError("alpha must be a finite non-negative number")
    return math.inf if value == 0.0 else 1.0 / value


def poisson_pmf(k: int, mean: float) -> float:
    if k < 0:
        return 0.0
    mu = float(mean)
    if mu <= 0.0:
        return 1.0 if k == 0 else 0.0
    return math.exp((k * math.log(mu)) - mu - math.lgamma(k + 1))


def poisson_cdf(k: int, mean: float) -> float:
    if k < 0:
        return 0.0
    mu = float(mean)
    if mu <= 0.0:
        return 1.0
    pmf = math.exp(-mu)
    total = pmf
    for value in range(1, k + 1):
        pmf *= mu / value
        total += pmf
    return max(0.0, min(1.0, total))


def nb_pmf(k: int, mean: float, alpha: float) -> float:
    """Return P(X=k) for an NB2 count with ``(mean, alpha)``."""
    if k < 0:
        return 0.0
    mu = float(mean)
    dispersion = float(alpha)
    if mu <= 0.0:
        return 1.0 if k == 0 else 0.0
    if dispersion <= 0.0:
        return poisson_pmf(k, mu)

    r = 1.0 / dispersion
    success = r / (r + mu)
    log_pmf = (
        math.lgamma(k + r)
        - math.lgamma(r)
        - math.lgamma(k + 1)
        + r * math.log(success)
        + k * math.log1p(-success)
    )
    return math.exp(log_pmf)


def nb_log_pmf(k: int, mean: float, alpha: float) -> float:
    """Return log P(X=k), using the Poisson limit when alpha is zero."""
    if k < 0:
        return -math.inf
    mu = max(MIN_MEAN, float(mean))
    dispersion = float(alpha)
    if dispersion <= 0.0:
        return (k * math.log(mu)) - mu - math.lgamma(k + 1)
    r = 1.0 / dispersion
    success = r / (r + mu)
    return (
        math.lgamma(k + r)
        - math.lgamma(r)
        - math.lgamma(k + 1)
        + (r * math.log(success))
        + (k * math.log1p(-success))
    )


def nb_cdf(k: int, mean: float, alpha: float) -> float:
    """Return P(X<=k) for an NB2 count with ``(mean, alpha)``."""
    if k < 0:
        return 0.0
    mu = float(mean)
    dispersion = float(alpha)
    if mu <= 0.0:
        return 1.0
    if dispersion <= 0.0:
        return poisson_cdf(k, mu)

    r = 1.0 / dispersion
    success = r / (r + mu)
    failure = 1.0 - success
    pmf = math.exp(r * math.log(success))
    total = pmf
    for value in range(k):
        pmf *= ((value + r) / (value + 1.0)) * failure
        total += pmf
    return max(0.0, min(1.0, total))


def total_probs(
    line: float,
    mean: float,
    *,
    distribution: Literal["poisson", "negative_binomial"] = "negative_binomial",
    alpha: float = 0.0,
) -> tuple[float, float, float]:
    """Return ``(p_over, p_under, p_push)`` for a count total line."""
    total_line = float(line)
    cdf = nb_cdf if distribution == "negative_binomial" else poisson_cdf

    if abs(total_line - round(total_line)) < 1e-9:
        exact = int(round(total_line))
        p_under = cdf(exact - 1, mean, alpha) if cdf is nb_cdf else cdf(exact - 1, mean)
        if distribution == "negative_binomial":
            p_push = nb_pmf(exact, mean, alpha)
        else:
            p_push = poisson_pmf(exact, mean)
        p_over = max(0.0, 1.0 - p_under - p_push)
        return p_over, p_under, p_push

    threshold = math.floor(total_line)
    p_under = cdf(threshold, mean, alpha) if cdf is nb_cdf else cdf(threshold, mean)
    return max(0.0, 1.0 - p_under), p_under, 0.0


def prob_over(
    line: float,
    mean: float,
    *,
    distribution: Literal["poisson", "negative_binomial"] = "poisson",
    alpha: float = 0.0,
) -> float:
    return total_probs(line, mean, distribution=distribution, alpha=alpha)[0]


def fair_decimal(probability: float, *, cap: float | None = None) -> float:
    probability = max(MIN_PROBABILITY, min(1.0, float(probability)))
    odds = round(1.0 / probability, 3)
    return min(cap, odds) if cap is not None else odds


def fit_dispersion_alpha(
    values: Iterable[float],
    *,
    fallback: float = 1.0 / 80.0,
    min_sample: int = 30,
) -> float:
    """Method-of-moments NB2 alpha, bounded to the legacy corners range."""
    observations = [float(value) for value in values if float(value) >= 0.0]
    if len(observations) < min_sample:
        return float(fallback)
    mean = sum(observations) / len(observations)
    if mean <= 0.0:
        return float(fallback)
    variance = sum((value - mean) ** 2 for value in observations) / max(1, len(observations) - 1)
    if variance <= mean + 1e-9:
        return MIN_ALPHA
    alpha = (variance - mean) / (mean * mean)
    return max(MIN_ALPHA, min(MAX_ALPHA, alpha))


def fit_dispersion_alpha_mle(
    observations: Iterable[tuple[float, float]],
    *,
    fallback: float = 1.0 / 80.0,
    min_sample: int = 30,
) -> float:
    """Fit NB2 alpha against frozen, observation-specific means."""
    rows = [
        (max(0, int(round(actual))), max(MIN_MEAN, float(mean)))
        for actual, mean in observations
        if math.isfinite(float(actual)) and math.isfinite(float(mean)) and float(actual) >= 0.0
    ]
    if len(rows) < min_sample:
        return float(fallback)

    def objective(log_alpha: float) -> float:
        alpha = math.exp(log_alpha)
        return -sum(nb_log_pmf(actual, mean, alpha) for actual, mean in rows)

    low = math.log(MIN_ALPHA)
    high = math.log(MAX_ALPHA)
    golden = (math.sqrt(5.0) - 1.0) / 2.0
    left = high - (golden * (high - low))
    right = low + (golden * (high - low))
    left_value = objective(left)
    right_value = objective(right)
    for _ in range(80):
        if left_value <= right_value:
            high = right
            right = left
            right_value = left_value
            left = high - (golden * (high - low))
            left_value = objective(left)
        else:
            low = left
            left = right
            left_value = right_value
            right = low + (golden * (high - low))
            right_value = objective(right)
    return max(MIN_ALPHA, min(MAX_ALPHA, math.exp((low + high) / 2.0)))


def invert_mean_for_over_prob(
    line: float,
    target_over: float,
    alpha: float,
    *,
    min_mean: float = MIN_MEAN,
    max_mean: float = MAX_MEAN,
) -> float:
    """Find the NB2 mean matching a target over probability at ``line``."""
    target = clip_probability(target_over)
    low = float(min_mean)
    high = float(max_mean)
    for _ in range(80):
        midpoint = (low + high) / 2.0
        probability = prob_over(
            line,
            midpoint,
            distribution="negative_binomial",
            alpha=alpha,
        )
        if probability < target:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2.0
