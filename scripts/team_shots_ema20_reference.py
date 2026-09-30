"""Frozen EMA20 v3 inference recovered from commit 5b6fc5331 (26 April 2026).

Functions below are verbatim historical source, not a refit. Live April/May
publication left match-win probabilities blank, hence neutral game-state.
Only the new comparison collector uses this module. No real staking route.
"""
from __future__ import annotations
import math
from typing import Any, Iterable

def pf(value: Any, default: float | None = 0.0) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def poisson_prob_over(line: float, lam: float) -> float:
    """P(X > line) for half-goal/half-shot lines."""
    if lam <= 0:
        return 0.0
    cutoff = int(math.floor(line))
    cdf = 0.0
    for k in range(cutoff + 1):
        cdf += math.exp((k * math.log(lam)) - lam - math.lgamma(k + 1))
    return clamp(1.0 - cdf, 1e-6, 1.0 - 1e-6)


def negative_binomial_prob_over(line: float, mean_count: float, alpha: float) -> float:
    """P(X > line) for NB2 variance = mean + alpha * mean^2."""
    if mean_count <= 0:
        return 0.0
    if alpha <= 1e-6:
        return poisson_prob_over(line, mean_count)

    cutoff = int(math.floor(line))
    size = 1.0 / alpha
    success_prob = size / (size + mean_count)
    success_prob = clamp(success_prob, 1e-9, 1.0 - 1e-9)

    pmf = math.exp(size * math.log(success_prob))
    cdf = pmf
    fail_prob = 1.0 - success_prob
    for k in range(cutoff):
        pmf *= ((k + size) / (k + 1.0)) * fail_prob
        cdf += pmf
    return clamp(1.0 - cdf, 1e-6, 1.0 - 1e-6)


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def enough_ema_history(row: dict[str, Any], minimum: int = 6) -> bool:
    return int(pf(row.get("ema20_matches"), 0) or 0) >= minimum


def ema20(row: dict[str, Any], field: str) -> float | None:
    return pf(row.get(f"ema20_{field}"), None)


def ema20_prefer(row: dict[str, Any], preferred: str, fallback: str) -> float | None:
    value = ema20(row, preferred)
    if value is not None:
        return value
    return ema20(row, fallback)


def venue_field(base: str, venue: str) -> str:
    suffix = "home" if venue == "home" else "away"
    return f"{base}_{suffix}_avg"


def quality_adjustment(team: dict[str, Any], opp: dict[str, Any]) -> float:
    """
    Small xG-per-shot adjustment when both sides have usable xG history.

    This is deliberately capped. We are testing whether xG adds signal, not
    letting sparse xG rows dominate the count forecast.
    """
    team_q = pf(team.get("r10_xg_per_shot_for"), None)
    opp_q = pf(opp.get("r10_xg_per_shot_against"), None)
    if team_q is None or opp_q is None or team_q <= 0 or opp_q <= 0:
        return 1.0
    quality = (team_q + opp_q) / 2.0
    neutral = 0.10
    return clamp(1.0 + ((quality - neutral) * 1.5), 0.88, 1.12)


def market_game_state_adjustment(team: dict[str, Any]) -> float:
    """
    Pre-match market strength proxy for expected game-state asymmetry.

    Heavy favourites tend to take/produce more shots; heavy underdogs often spend
    more time defending. The cap keeps this as a modest contextual nudge rather
    than letting 1X2 odds dominate the shot model.
    """
    team_prob = pf(team.get("market_team_win_prob"), None)
    opp_prob = pf(team.get("market_opp_win_prob"), None)
    if team_prob is None or opp_prob is None:
        return 1.0
    gap = team_prob - opp_prob
    return clamp(1.0 + (gap * 0.22), 0.88, 1.12)


def canonical_team_shots_ema20_lambda(
    team: dict[str, Any],
    opp: dict[str, Any],
    *,
    use_market: bool = True,
) -> float | None:
    """Team-shots v3 replay: v2 pooled opponent defence with EMA20 histories."""
    team_venue = str(team.get("venue", "")).strip()
    attack = ema20_prefer(team, venue_field("shots_for", team_venue), "shots_for_avg")
    opp_defence = ema20(opp, "shots_against_avg")
    if attack is None or opp_defence is None or not enough_ema_history(team) or not enough_ema_history(opp):
        return None
    lam = (0.55 * attack) + (0.45 * opp_defence)
    lam *= quality_adjustment(team, opp)
    if use_market:
        lam *= market_game_state_adjustment(team)
    return clamp(lam, 3.0, 30.0)


def estimate_alpha(values: list[float]) -> float:
    if len(values) < 100:
        return 0.0
    avg = mean(values)
    if avg <= 0:
        return 0.0
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return clamp((variance - avg) / (avg * avg), 0.0, 2.0)
