#!/usr/bin/env python3
"""Shared two-way market calibration helpers for football count markets.

The shading parameter is the share of quoted overround removed from the Over
side. A value of 0.5 is an equal split; proportional de-vig remains available
only as a benchmark.
"""

from __future__ import annotations

import math
from collections.abc import Iterable


EPSILON = 1e-9


def clip_probability(value: float) -> float:
    return max(EPSILON, min(1.0 - EPSILON, float(value)))


def logit(probability: float) -> float:
    p = clip_probability(probability)
    return math.log(p / (1.0 - p))


def sigmoid(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def proportional_devig(over_odds: float, under_odds: float) -> tuple[float, float, float]:
    if min(over_odds, under_odds) <= 1.0:
        raise ValueError("two-way decimal odds must both exceed 1.0")
    imp_over = 1.0 / float(over_odds)
    imp_under = 1.0 / float(under_odds)
    total = imp_over + imp_under
    return imp_over / total, imp_under / total, max(0.0, total - 1.0)


def shading_aware_devig(
    over_odds: float,
    under_odds: float,
    *,
    over_vig_share: float,
) -> tuple[float, float, float]:
    """Remove the quoted overround using a fitted side allocation."""
    if min(over_odds, under_odds) <= 1.0:
        raise ValueError("two-way decimal odds must both exceed 1.0")
    imp_over = 1.0 / float(over_odds)
    imp_under = 1.0 / float(under_odds)
    overround = max(0.0, imp_over + imp_under - 1.0)
    share = max(0.0, min(1.0, float(over_vig_share)))
    fair_over = clip_probability(imp_over - (share * overround))
    fair_under = clip_probability(imp_under - ((1.0 - share) * overround))
    total = fair_over + fair_under
    return fair_over / total, fair_under / total, overround


def fit_over_vig_share(
    rows: Iterable[tuple[float, float, bool]],
    *,
    fallback: float = 0.5,
    min_sample: int = 20,
) -> float:
    """Fit the vig allocation by minimizing Over-side Brier score."""
    numerator = 0.0
    denominator = 0.0
    count = 0
    for over_odds, under_odds, actual_over in rows:
        if min(over_odds, under_odds) <= 1.0:
            continue
        imp_over = 1.0 / float(over_odds)
        overround = max(0.0, imp_over + (1.0 / float(under_odds)) - 1.0)
        if overround <= EPSILON:
            continue
        target = 1.0 if actual_over else 0.0
        numerator += overround * (imp_over - target)
        denominator += overround * overround
        count += 1
    if count < min_sample or denominator <= EPSILON:
        return max(0.0, min(1.0, float(fallback)))
    return max(0.0, min(1.0, numerator / denominator))


def blend_logit(model_probability: float, market_probability: float, model_weight: float) -> float:
    weight = max(0.0, min(1.0, float(model_weight)))
    return clip_probability(
        sigmoid((weight * logit(model_probability)) + ((1.0 - weight) * logit(market_probability)))
    )


def brier(probability: float, actual: bool) -> float:
    target = 1.0 if actual else 0.0
    return (clip_probability(probability) - target) ** 2


def log_loss(probability: float, actual: bool) -> float:
    p = clip_probability(probability)
    return -math.log(p if actual else 1.0 - p)


def fit_blend_weight(
    rows: Iterable[tuple[float, float, bool]],
    *,
    step: float = 0.01,
) -> float:
    """Fit one model-vs-market logit weight on a declared training sample."""
    observations = list(rows)
    if not observations:
        return 0.0
    steps = max(1, int(round(1.0 / step)))
    best_weight = 0.0
    best_loss = math.inf
    for index in range(steps + 1):
        weight = index / steps
        loss = sum(
            log_loss(blend_logit(model_probability, market_probability, weight), actual)
            for model_probability, market_probability, actual in observations
        ) / len(observations)
        if loss < best_loss - 1e-12:
            best_loss = loss
            best_weight = weight
    return best_weight
