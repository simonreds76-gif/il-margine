#!/usr/bin/env python3
"""Legacy ``(mean, r)`` compatibility wrapper for football count maths.

New code should import :mod:`football_counts` and use NB2 ``alpha`` directly.
"""

from __future__ import annotations

from typing import Iterable

import football_counts as counts


MIN_MEAN = counts.MIN_MEAN
MAX_MEAN = counts.MAX_MEAN
MIN_R = counts.MIN_R
MAX_R = counts.MAX_R


def _clip_prob(value: float) -> float:
    return counts.clip_probability(value)


def _alpha(r: float) -> float:
    bounded_r = max(MIN_R, min(MAX_R, float(r)))
    return counts.r_to_alpha(bounded_r)


def nb_pmf(k: int, mean: float, r: float) -> float:
    return counts.nb_pmf(k, max(MIN_MEAN, float(mean)), _alpha(r))


def nb_cdf(k: int, mean: float, r: float) -> float:
    return counts.nb_cdf(k, max(MIN_MEAN, float(mean)), _alpha(r))


def nb_total_probs(line: float, mean: float, r: float) -> tuple[float, float, float]:
    return counts.total_probs(
        line,
        max(MIN_MEAN, float(mean)),
        distribution="negative_binomial",
        alpha=_alpha(r),
    )


def nb_total_prob_over(line: float, mean: float, r: float) -> float:
    return nb_total_probs(line, mean, r)[0]


def fair_decimal(prob: float) -> float:
    return counts.fair_decimal(prob)


def fit_dispersion(values: Iterable[float], *, fallback: float = 80.0) -> float:
    alpha = counts.fit_dispersion_alpha(values, fallback=counts.r_to_alpha(fallback))
    return max(MIN_R, min(MAX_R, counts.alpha_to_r(alpha)))


def invert_mean_for_over_prob(line: float, target_over: float, r: float) -> float:
    return counts.invert_mean_for_over_prob(line, target_over, _alpha(r))
