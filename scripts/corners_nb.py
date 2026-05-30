#!/usr/bin/env python3
"""
Negative Binomial helpers for corners v2.

This module is pure maths only. It is intended to sit beside
corners_poisson.py while the v2 real-odds validation work is built.

Parameterisation:
  total_corners ~ NB(mean=mu, dispersion=r)
  variance = mu + mu^2 / r

Large r approaches Poisson. Smaller r gives heavier tails.
"""

from __future__ import annotations

import math
from statistics import mean
from typing import Iterable, Sequence, Tuple

POISSON_LIKE_R = 1_000_000.0
MIN_DISPERSION_R = 0.25
MAX_DISPERSION_R = POISSON_LIKE_R


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def nb_pmf(k: int, mu: float, r: float) -> float:
    """Return P(X=k) for NB(mean=mu, dispersion=r)."""
    if k < 0:
        return 0.0
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    if r <= 0:
        raise ValueError("dispersion r must be positive")

    p = r / (r + mu)
    log_prob = (
        math.lgamma(k + r)
        - math.lgamma(r)
        - math.lgamma(k + 1)
        + r * math.log(p)
        + k * math.log1p(-p)
    )
    return math.exp(log_prob)


def nb_cdf(k: int, mu: float, r: float) -> float:
    """Return P(X<=k)."""
    if k < 0:
        return 0.0
    # Corner totals above 40 are extremely rare; continue further only when needed.
    return _clip(sum(nb_pmf(i, mu, r) for i in range(k + 1)))


def nb_line_probabilities(line: float, mu: float, r: float) -> Tuple[float, float, float]:
    """
    Return (p_over, p_under, p_push) for an O/U line.

    Half-point lines have p_push=0. Integer lines treat exact total==line as push.
    """
    if mu < 0:
        raise ValueError("mean mu must be non-negative")
    if r <= 0:
        raise ValueError("dispersion r must be positive")

    cutoff = math.floor(line)
    if abs(line - round(line)) < 1e-9:
        exact = int(round(line))
        p_push = nb_pmf(exact, mu, r)
        p_under = nb_cdf(exact - 1, mu, r)
        p_over = 1.0 - p_under - p_push
        return (_clip(p_over), _clip(p_under), _clip(p_push))

    p_under = nb_cdf(cutoff, mu, r)
    p_over = 1.0 - p_under
    return (_clip(p_over), _clip(p_under), 0.0)


def nb_total_prob_over(line: float, mu: float, r: float) -> float:
    """Compatibility helper: P(total corners > line)."""
    return nb_line_probabilities(line, mu, r)[0]


def fit_dispersion(totals: Iterable[float]) -> float:
    """
    Estimate NB dispersion r from realised total-corners counts.

    Method-of-moments: var = mu + mu^2/r, so r = mu^2/(var-mu).
    If variance is not above mean, return a Poisson-like large r.
    """
    values = [float(x) for x in totals if x is not None]
    if len(values) < 2:
        return POISSON_LIKE_R

    mu = mean(values)
    if mu <= 0:
        return POISSON_LIKE_R

    var = sum((x - mu) ** 2 for x in values) / (len(values) - 1)
    if var <= mu:
        return POISSON_LIKE_R

    r = (mu * mu) / (var - mu)
    return max(MIN_DISPERSION_R, min(MAX_DISPERSION_R, r))


def shrink_dispersion(raw_r: float, pooled_r: float, n: int, prior_n: int = 200) -> float:
    """Shrink a league-level dispersion estimate toward the pooled value."""
    if n <= 0:
        return pooled_r
    weight = n / (n + max(1, prior_n))
    return weight * raw_r + (1.0 - weight) * pooled_r


def fit_pooled_and_group_dispersion(
    rows: Sequence[tuple[str, float]],
    prior_n: int = 200,
) -> tuple[float, dict[str, float]]:
    """
    Fit pooled and shrunk group dispersions from (group, total) rows.

    Returns (pooled_r, {group: shrunk_r}).
    """
    pooled_r = fit_dispersion(total for _, total in rows)
    grouped: dict[str, list[float]] = {}
    for group, total in rows:
        grouped.setdefault(group or "unknown", []).append(float(total))

    shrunk = {
        group: shrink_dispersion(fit_dispersion(values), pooled_r, len(values), prior_n=prior_n)
        for group, values in grouped.items()
    }
    return pooled_r, shrunk


def push_adjusted_fair_decimal(win_prob: float, push_prob: float = 0.0) -> float | None:
    """Fair decimal odds when exact-line pushes return stake."""
    win_prob = _clip(win_prob)
    push_prob = _clip(push_prob)
    if win_prob <= 0:
        return None
    return (1.0 - push_prob) / win_prob
