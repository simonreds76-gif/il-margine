"""Compatibility API for team-shots count probabilities.

The authoritative Negative Binomial implementation lives in
``football_counts.py`` and uses NB2 ``alpha`` throughout.
"""

from __future__ import annotations

import football_counts as counts


poisson_cdf = counts.poisson_cdf
negbin_cdf = counts.nb_cdf


def prob_over(line: float, mu: float, *, distribution: str = "poisson", alpha: float = 0.0) -> float:
    if distribution not in {"poisson", "negative_binomial"}:
        raise ValueError(f"unsupported distribution: {distribution}")
    return counts.prob_over(line, mu, distribution=distribution, alpha=alpha)


def fair_odds(prob: float) -> float:
    if prob <= 0:
        return 999.0
    if prob >= 1:
        return 1.001
    return counts.fair_decimal(prob)
