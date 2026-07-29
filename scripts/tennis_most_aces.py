#!/usr/bin/env python3
"""Probability helpers for the ATP Most Aces 1X2 shadow lane."""

from __future__ import annotations

import math
import re
import unicodedata
from functools import lru_cache
from typing import Iterable

import numpy as np
from scipy.stats import nbinom, norm, qmc


DEFAULT_RHO = 0.22
DEFAULT_SIMULATIONS = 16384
MIN_RECENT_MATCHES = 4
MIN_RECENT_SERVICE_POINTS = 250
MIN_HISTORICAL_L24M_MATCHES = 12
MIN_HISTORICAL_L24M_SERVICE_POINTS = 800
MIN_HISTORICAL_CAREER_MATCHES = 20
MIN_HISTORICAL_CAREER_SERVICE_POINTS = 1500


def sample_evidence_tier(
    *,
    l12m_matches: int,
    l12m_service_points: int,
    l24m_matches: int,
    l24m_service_points: int,
    career_matches: int,
    career_service_points: int,
) -> str:
    """Classify whether an ace estimate measures current or historical form."""
    if (
        l12m_matches >= MIN_RECENT_MATCHES
        and l12m_service_points >= MIN_RECENT_SERVICE_POINTS
    ):
        return "RECENT"
    if (
        l24m_matches >= MIN_HISTORICAL_L24M_MATCHES
        and l24m_service_points >= MIN_HISTORICAL_L24M_SERVICE_POINTS
    ) or (
        career_matches >= MIN_HISTORICAL_CAREER_MATCHES
        and career_service_points >= MIN_HISTORICAL_CAREER_SERVICE_POINTS
    ):
        return "HISTORICAL"
    return "INSUFFICIENT"


def recent_activity(matches: int, service_points: int) -> bool:
    return (
        matches >= MIN_RECENT_MATCHES
        and service_points >= MIN_RECENT_SERVICE_POINTS
    )


def norm_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def pair_key(player1: object, player2: object) -> tuple[str, str]:
    return tuple(sorted((norm_name(player1), norm_name(player2))))  # type: ignore[return-value]


def nb2_parameters(mean: float, alpha: float) -> tuple[float, float]:
    if mean <= 0:
        raise ValueError("mean must be positive")
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    size = 1.0 / alpha
    probability = size / (size + mean)
    return size, probability


@lru_cache(maxsize=8)
def _sobol_normals(simulations: int) -> tuple[np.ndarray, np.ndarray]:
    if simulations < 256 or simulations & (simulations - 1):
        raise ValueError("simulations must be a power of two and at least 256")
    sample = qmc.Sobol(d=2, scramble=False).random_base2(int(math.log2(simulations)))
    sample = np.clip(sample, 1e-10, 1.0 - 1e-10)
    return norm.ppf(sample[:, 0]), norm.ppf(sample[:, 1])


def most_aces_probabilities(
    mean1: float,
    mean2: float,
    *,
    alpha1: float,
    alpha2: float,
    rho: float = DEFAULT_RHO,
    simulations: int = DEFAULT_SIMULATIONS,
) -> tuple[float, float, float]:
    """Return P1 / Draw / P2 using correlated NB2 marginal counts.

    A Gaussian copula preserves each player's fitted NB2 count distribution
    while adding the empirically measured shared match-workload dependence.
    Sobol draws keep the result deterministic across daily runs.
    """
    if not -0.95 < rho < 0.95:
        raise ValueError("rho must be between -0.95 and 0.95")
    z1, independent = _sobol_normals(simulations)
    z2 = rho * z1 + math.sqrt(1.0 - rho * rho) * independent
    u1 = np.clip(norm.cdf(z1), 1e-10, 1.0 - 1e-10)
    u2 = np.clip(norm.cdf(z2), 1e-10, 1.0 - 1e-10)
    size1, probability1 = nb2_parameters(mean1, alpha1)
    size2, probability2 = nb2_parameters(mean2, alpha2)
    count1 = nbinom.ppf(u1, size1, probability1)
    count2 = nbinom.ppf(u2, size2, probability2)
    p1 = float(np.mean(count1 > count2))
    draw = float(np.mean(count1 == count2))
    p2 = max(0.0, 1.0 - p1 - draw)
    return p1, draw, p2


def independent_most_aces_probabilities(
    mean1: float,
    mean2: float,
    *,
    alpha1: float,
    alpha2: float,
) -> tuple[float, float, float]:
    """Exact independence control for the correlated shadow model."""
    size1, probability1 = nb2_parameters(mean1, alpha1)
    size2, probability2 = nb2_parameters(mean2, alpha2)
    maximum = int(max(
        nbinom.ppf(1.0 - 1e-10, size1, probability1),
        nbinom.ppf(1.0 - 1e-10, size2, probability2),
    ))
    counts = np.arange(maximum + 1)
    pmf1 = nbinom.pmf(counts, size1, probability1)
    pmf2 = nbinom.pmf(counts, size2, probability2)
    cdf2_below = nbinom.cdf(counts - 1, size2, probability2)
    p1 = float(np.sum(pmf1 * cdf2_below))
    draw = float(np.sum(pmf1 * pmf2))
    p2 = max(0.0, 1.0 - p1 - draw)
    return p1, draw, p2


def fair_odds(probability: float) -> float | None:
    return 1.0 / probability if probability > 0 else None


def devig_three_way(odds: Iterable[float]) -> tuple[float, float, float, float]:
    prices = tuple(float(value) for value in odds)
    if len(prices) != 3 or any(value <= 1.0 for value in prices):
        raise ValueError("three decimal prices above 1.0 are required")
    raw = tuple(1.0 / value for value in prices)
    overround = sum(raw)
    return raw[0] / overround, raw[1] / overround, raw[2] / overround, overround


def value_pct(probability: float, decimal_odds: float) -> float:
    return (probability * decimal_odds - 1.0) * 100.0


def result_from_counts(player1_aces: int, player2_aces: int) -> str:
    if player1_aces > player2_aces:
        return "P1"
    if player2_aces > player1_aces:
        return "P2"
    return "DRAW"
