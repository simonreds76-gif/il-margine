from __future__ import annotations

import math


def poisson_cdf(k: int, mu: float) -> float:
    if k < 0:
        return 0.0
    if mu <= 0:
        return 1.0
    pmf = math.exp(-mu)
    total = pmf
    for x in range(1, k + 1):
        pmf *= mu / x
        total += pmf
    return min(max(total, 0.0), 1.0)


def negbin_cdf(k: int, mu: float, alpha: float) -> float:
    if k < 0:
        return 0.0
    if mu <= 0:
        return 1.0
    if alpha <= 0:
        return poisson_cdf(k, mu)
    r = 1.0 / alpha
    p = r / (r + mu)
    log_p = math.log(p)
    log_1mp = math.log1p(-p)
    total = 0.0
    for x in range(k + 1):
        log_pmf = math.lgamma(x + r) - math.lgamma(r) - math.lgamma(x + 1) + r * log_p + x * log_1mp
        total += math.exp(log_pmf)
    return min(max(total, 0.0), 1.0)


def prob_over(line: float, mu: float, *, distribution: str = "poisson", alpha: float = 0.0) -> float:
    """P(shots > line). For line=10.5 this is P(shots >= 11)."""
    k = math.floor(line)
    if distribution == "negative_binomial":
        return 1.0 - negbin_cdf(k, mu, alpha)
    return 1.0 - poisson_cdf(k, mu)


def fair_odds(prob: float) -> float:
    if prob <= 0:
        return 999.0
    if prob >= 1:
        return 1.001
    return round(1.0 / prob, 3)
