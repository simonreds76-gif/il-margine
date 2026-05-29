#!/usr/bin/env python3
"""Small projection helpers for tennis aces/double-fault research boards."""

from __future__ import annotations

from dataclasses import dataclass
import math

DEFAULT_COUNT_DISPERSION_ALPHA = {
    ("ATP", "aces"): 0.35,
    ("WTA", "aces"): 0.50,
    ("ATP", "dfs"): 0.10,
    ("WTA", "dfs"): 0.20,
}

# Additive correction = actual minus projected from the 2024-2025 Slam
# Stage-0 holdout report. Keep this small and transparent; same-tournament
# current-round data still carries the live within-event adjustment.
SLAM_COUNT_BIAS_CORRECTION = {
    ("ATP", "Australian Open"): {"aces": -0.180, "dfs": 0.252},
    ("ATP", "Roland Garros"): {"aces": 0.076, "dfs": -0.327},
    ("ATP", "US Open"): {"aces": -0.850, "dfs": 0.630},
    ("ATP", "Wimbledon"): {"aces": 0.589, "dfs": -0.010},
    ("WTA", "Australian Open"): {"aces": -0.092, "dfs": -0.033},
    ("WTA", "Roland Garros"): {"aces": 0.073, "dfs": -0.164},
    ("WTA", "US Open"): {"aces": -0.225, "dfs": 0.078},
    ("WTA", "Wimbledon"): {"aces": 0.000, "dfs": 0.231},
}


@dataclass(frozen=True)
class Projection:
    expected_aces: float
    expected_dfs: float
    expected_service_points: float
    expected_service_games: float
    ace_rate: float
    df_rate: float
    same_tournament_matches: int
    same_tournament_svpt: int
    same_tournament_ace_weight: float
    same_tournament_df_weight: float
    ace_confidence: str
    df_confidence: str
    notes: tuple[str, ...]


def _float(value: object, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def _int(value: object, default: int = 0) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _blend_rate(
    rows_by_window: dict[str, dict[str, str]],
    rate_field: str,
    sample_field: str,
    prior_rate: float,
    prior_weight: float,
) -> tuple[float, int]:
    weights = {
        "L12M": 1.0,
        "L24M": 0.55,
        "career_4y": 0.25,
    }
    numerator = prior_rate * prior_weight
    denominator = prior_weight
    max_sample = 0
    for window, weight in weights.items():
        row = rows_by_window.get(window) or {}
        sample = _int(row.get(sample_field))
        rate = _float(row.get(rate_field))
        if sample <= 0 or rate is None:
            continue
        numerator += rate * sample * weight
        denominator += sample * weight
        max_sample = max(max_sample, sample)
    return numerator / denominator if denominator > 0 else prior_rate, max_sample


def _blend_value(
    rows_by_window: dict[str, dict[str, str]],
    value_field: str,
    sample_field: str,
    prior_value: float,
    prior_weight: float,
) -> float:
    weights = {
        "L12M": 1.0,
        "L24M": 0.55,
        "career_4y": 0.25,
    }
    numerator = prior_value * prior_weight
    denominator = prior_weight
    for window, weight in weights.items():
        row = rows_by_window.get(window) or {}
        sample = _int(row.get(sample_field))
        value = _float(row.get(value_field))
        if sample <= 0 or value is None:
            continue
        numerator += value * sample * weight
        denominator += sample * weight
    return numerator / denominator if denominator > 0 else prior_value


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _same_tournament_rate(
    row: dict[str, str] | None,
    numerator_field: str,
    *,
    max_weight: float,
    sample_full: float,
) -> tuple[float | None, float, int, int]:
    if not row:
        return None, 0.0, 0, 0
    svpt = _int(row.get("svpt"))
    matches = _int(row.get("matches"))
    numerator = _int(row.get(numerator_field))
    if svpt <= 0 or matches <= 0:
        return None, 0.0, matches, svpt
    rate = numerator / svpt
    weight = _clip((svpt / sample_full) * max_weight, 0.0, max_weight)
    return rate, weight, matches, svpt


def project_player(
    *,
    tour: str,
    player_rows: dict[str, dict[str, str]],
    opponent_rows: dict[str, dict[str, str]],
    factor_row: dict[str, str],
    expected_match_games: float,
    slam_matches: int,
    same_tournament_row: dict[str, str] | None = None,
) -> Projection:
    tour_norm = tour.lower()
    ace_prior_weight = 400.0 if tour_norm == "atp" else 600.0
    df_prior_weight = 600.0 if tour_norm == "atp" else 800.0
    default_ace_prior = 0.065 if tour_norm == "atp" else 0.027
    default_df_prior = 0.035 if tour_norm == "atp" else 0.048

    prior_ace = _float(factor_row.get("tour_surface_baseline_ace"), default_ace_prior) or default_ace_prior
    prior_df = _float(factor_row.get("tour_surface_baseline_df"), default_df_prior) or default_df_prior
    prior_svpt_per_svg = _float(factor_row.get("svpt_per_svgame"), 6.35) or 6.35
    prior_ret_first = 0.315 if tour_norm == "atp" else 0.365

    ace_rate, surface_svpt = _blend_rate(
        player_rows, "ace_rate", "svpt", prior_ace, ace_prior_weight
    )
    df_rate, _ = _blend_rate(player_rows, "df_rate", "svpt", prior_df, df_prior_weight)

    same_ace_rate, same_ace_weight, same_matches, same_svpt = _same_tournament_rate(
        same_tournament_row,
        "aces",
        max_weight=0.34 if tour_norm == "atp" else 0.24,
        sample_full=320.0 if tour_norm == "atp" else 280.0,
    )
    same_df_rate, same_df_weight, _, _ = _same_tournament_rate(
        same_tournament_row,
        "dfs",
        max_weight=0.24 if tour_norm == "atp" else 0.18,
        sample_full=360.0 if tour_norm == "atp" else 320.0,
    )
    if same_ace_rate is not None and same_ace_weight > 0:
        ace_rate = (1.0 - same_ace_weight) * ace_rate + same_ace_weight * same_ace_rate
    if same_df_rate is not None and same_df_weight > 0:
        df_rate = (1.0 - same_df_weight) * df_rate + same_df_weight * same_df_rate

    svpt_per_svg = _blend_value(
        player_rows, "svpt_per_svgame", "svgms", prior_svpt_per_svg, 60.0
    )
    opp_ret_first, opp_return_sample = _blend_rate(
        opponent_rows,
        "ret_first_win_pct",
        "ret_first_points",
        prior_ret_first,
        350.0,
    )

    notes: list[str] = []
    if surface_svpt < 500:
        notes.append("LOW_SAMPLE")
    if opp_return_sample < 250:
        notes.append("NO_OPP_DATA")
    if slam_matches <= 0:
        notes.append("SLAM_DEBUT")
    if same_matches > 0:
        notes.append(f"SAME_TOURNAMENT_N{same_matches}")

    slam_ace_factor = _float(factor_row.get("ace_factor"), 1.0) or 1.0
    slam_df_factor = _float(factor_row.get("df_factor"), 1.0) or 1.0
    ret_factor = _clip((prior_ret_first / max(0.18, opp_ret_first)) ** 0.6, 0.76, 1.22)

    ace_rate_adj = _clip(ace_rate * slam_ace_factor * ret_factor, 0.002, 0.28)
    df_rate_adj = _clip(df_rate * slam_df_factor, 0.002, 0.16)
    expected_service_games = max(4.0, expected_match_games * 0.5)
    expected_service_points = expected_service_games * _clip(svpt_per_svg, 4.8, 8.6)

    expected_aces = ace_rate_adj * expected_service_points
    expected_dfs = df_rate_adj * expected_service_points
    tournament = str(factor_row.get("tournament") or "").strip()
    correction = SLAM_COUNT_BIAS_CORRECTION.get((tour.upper(), tournament))
    if correction:
        expected_aces = max(0.0, expected_aces + _clip(correction.get("aces", 0.0), -0.90, 0.90))
        expected_dfs = max(0.0, expected_dfs + _clip(correction.get("dfs", 0.0), -0.70, 0.70))

    l12 = player_rows.get("L12M") or {}
    l12_matches = _int(l12.get("matches"))
    if surface_svpt >= 1500 and slam_matches >= 8 and opp_return_sample >= 800:
        ace_confidence = "HIGH"
    elif surface_svpt >= 500:
        ace_confidence = "MED"
    else:
        ace_confidence = "LOW"

    if surface_svpt >= 2000 and l12_matches >= 30 and expected_dfs >= 2.0:
        df_confidence = "HIGH"
    elif surface_svpt >= 500 and expected_dfs >= 1.5:
        df_confidence = "MED"
    else:
        df_confidence = "LOW"

    return Projection(
        expected_aces=expected_aces,
        expected_dfs=expected_dfs,
        expected_service_points=expected_service_points,
        expected_service_games=expected_service_games,
        ace_rate=ace_rate_adj,
        df_rate=df_rate_adj,
        same_tournament_matches=same_matches,
        same_tournament_svpt=same_svpt,
        same_tournament_ace_weight=same_ace_weight,
        same_tournament_df_weight=same_df_weight,
        ace_confidence=ace_confidence,
        df_confidence=df_confidence,
        notes=tuple(notes),
    )


def poisson_pmf(k: int, mean: float) -> float:
    if k < 0 or mean <= 0:
        return 0.0
    term = math.exp(-mean)
    for i in range(1, k + 1):
        term *= mean / i
    return _clip(term, 0.0, 1.0)


def negative_binomial_pmf(k: int, mean: float, alpha: float) -> float:
    if k < 0:
        return 0.0
    if mean <= 0:
        return 1.0 if k == 0 else 0.0
    if alpha <= 1e-9:
        return poisson_pmf(k, mean)
    # Var = mean + alpha * mean^2. This is the standard NB2 parameterisation.
    size = 1.0 / alpha
    prob = size / (size + mean)
    log_pmf = (
        math.lgamma(k + size)
        - math.lgamma(size)
        - math.lgamma(k + 1)
        + size * math.log(prob)
        + k * math.log1p(-prob)
    )
    return _clip(math.exp(log_pmf), 0.0, 1.0)


def _negative_binomial_cdf(cutoff: int, mean: float, alpha: float) -> float:
    if cutoff < 0:
        return 0.0
    if mean <= 0:
        return 1.0
    return _clip(sum(negative_binomial_pmf(k, mean, alpha) for k in range(cutoff + 1)), 0.0, 1.0)


def _poisson_cdf(cutoff: int, mean: float) -> float:
    if cutoff < 0:
        return 0.0
    if mean <= 0:
        return 1.0
    cdf = 0.0
    term = math.exp(-mean)
    cdf += term
    for k in range(1, cutoff + 1):
        term *= mean / k
        cdf += term
    return _clip(cdf, 0.0, 1.0)


def _is_integer_line(line: float) -> bool:
    return abs(float(line) - round(float(line))) < 1e-9


def poisson_p_push(line: float, mean: float) -> float:
    if not _is_integer_line(line):
        return 0.0
    return poisson_pmf(int(round(line)), mean)


def poisson_line_probabilities(line: float, mean: float) -> tuple[float, float, float]:
    """Return raw (over win, under win, push) probabilities for an O/U line."""
    if mean <= 0:
        if _is_integer_line(line) and int(round(line)) == 0:
            return 0.0, 0.0, 1.0
        return 0.0, 1.0, 0.0
    cutoff = math.floor(line)
    if _is_integer_line(line):
        push = poisson_pmf(cutoff, mean)
        under = _poisson_cdf(cutoff - 1, mean)
        over = 1.0 - under - push
        return _clip(over, 0.0, 1.0), _clip(under, 0.0, 1.0), _clip(push, 0.0, 1.0)
    under = _poisson_cdf(cutoff, mean)
    return _clip(1.0 - under, 0.0, 1.0), under, 0.0


def negative_binomial_line_probabilities(line: float, mean: float, alpha: float) -> tuple[float, float, float]:
    if mean <= 0:
        if _is_integer_line(line) and int(round(line)) == 0:
            return 0.0, 0.0, 1.0
        return 0.0, 1.0, 0.0
    cutoff = math.floor(line)
    if _is_integer_line(line):
        push = negative_binomial_pmf(cutoff, mean, alpha)
        under = _negative_binomial_cdf(cutoff - 1, mean, alpha)
        over = 1.0 - under - push
        return _clip(over, 0.0, 1.0), _clip(under, 0.0, 1.0), _clip(push, 0.0, 1.0)
    under = _negative_binomial_cdf(cutoff, mean, alpha)
    return _clip(1.0 - under, 0.0, 1.0), under, 0.0


def resolve_count_dispersion(tour: str, market: str) -> float:
    tour_key = str(tour or "").upper()
    market_key = "dfs" if str(market or "").lower().replace(" ", "_") in {"double_faults", "double_fault", "df", "dfs"} else "aces"
    return DEFAULT_COUNT_DISPERSION_ALPHA.get((tour_key, market_key), 0.25 if market_key == "aces" else 0.12)


def count_line_probabilities(
    line: float,
    mean: float,
    *,
    distribution: str = "negative_binomial",
    alpha: float | None = None,
    tour: str = "",
    market: str = "aces",
) -> tuple[float, float, float]:
    if distribution in {"nb", "negative_binomial"}:
        resolved_alpha = resolve_count_dispersion(tour, market) if alpha is None else alpha
        return negative_binomial_line_probabilities(line, mean, resolved_alpha)
    return poisson_line_probabilities(line, mean)


def push_adjusted_fair_odds(win_prob: float, push_prob: float = 0.0) -> float | None:
    if win_prob <= 0:
        return None
    return max(1e-6, 1.0 - push_prob) / win_prob


def push_adjusted_value_pct(win_prob: float, push_prob: float, odds: float | None) -> float | None:
    if odds is None or odds <= 1:
        return None
    # EV per 1u stake with push returning stake: win*(odds-1) - loss.
    return (win_prob * odds + push_prob - 1.0) * 100.0


def poisson_p_over(line: float, mean: float) -> float:
    return poisson_line_probabilities(line, mean)[0]


def poisson_p_under(line: float, mean: float) -> float:
    return poisson_line_probabilities(line, mean)[1]
