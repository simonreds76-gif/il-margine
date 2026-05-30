#!/usr/bin/env python3
"""Negative-binomial helpers for corners total models.

Pure math only. The NB parameterization uses mean ``mu`` and dispersion ``r``:
variance = mu + mu^2 / r. Larger r tends toward Poisson.
"""

from __future__ import annotations

import math
from typing import Iterable


MIN_MEAN = 0.05
MAX_MEAN = 30.0
MIN_R = 1.25
MAX_R = 500.0


def _clip_prob(value: float) -> float:
    return max(1e-9, min(1.0 - 1e-9, value))


def nb_pmf(k: int, mean: float, r: float) -> float:
    """P(X=k) for NB(mean, r)."""
    if k < 0:
        return 0.0
    mean = max(MIN_MEAN, float(mean))
    r = max(MIN_R, min(MAX_R, float(r)))
    p = r / (r + mean)
    log_pmf = (
        math.lgamma(k + r)
        - math.lgamma(r)
        - math.lgamma(k + 1)
        + r * math.log(p)
        + k * math.log(1.0 - p)
    )
    return math.exp(log_pmf)


def nb_cdf(k: int, mean: float, r: float) -> float:
    """P(X<=k) for NB(mean, r)."""
    if k < 0:
        return 0.0
    total = 0.0
    # 80 is well above realistic corner totals; break once the tail is exhausted.
    for i in range(0, min(k, 80) + 1):
        total += nb_pmf(i, mean, r)
    return max(0.0, min(1.0, total))


def nb_total_probs(line: float, mean: float, r: float) -> tuple[float, float, float]:
    """Return (p_over, p_under, p_push) for a total-corners line."""
    line = float(line)
    threshold = math.floor(line)
    if abs(line - round(line)) < 1e-9:
        exact = int(round(line))
        p_push = nb_pmf(exact, mean, r)
        p_under = nb_cdf(exact - 1, mean, r)
        p_over = max(0.0, 1.0 - p_under - p_push)
        return p_over, p_under, p_push
    p_under_or_eq = nb_cdf(threshold, mean, r)
    p_over = 1.0 - p_under_or_eq
    return max(0.0, p_over), p_under_or_eq, 0.0


def nb_total_prob_over(line: float, mean: float, r: float) -> float:
    return nb_total_probs(line, mean, r)[0]


def fair_decimal(prob: float) -> float:
    prob = max(1e-9, min(1.0, prob))
    return round(1.0 / prob, 3)


def fit_dispersion(values: Iterable[float], *, fallback: float = 80.0) -> float:
    vals = [float(v) for v in values if float(v) >= 0.0]
    if len(vals) < 30:
        return fallback
    mean = sum(vals) / len(vals)
    if mean <= 0.0:
        return fallback
    var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
    if var <= mean + 1e-9:
        return MAX_R
    r = (mean * mean) / (var - mean)
    return max(MIN_R, min(MAX_R, r))


def invert_mean_for_over_prob(line: float, target_over: float, r: float) -> float:
    """Find mean whose NB over probability at ``line`` matches target_over."""
    target = _clip_prob(target_over)
    lo = MIN_MEAN
    hi = MAX_MEAN
    for _ in range(80):
        mid = (lo + hi) / 2.0
        p_mid = nb_total_prob_over(line, mid, r)
        if p_mid < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0
