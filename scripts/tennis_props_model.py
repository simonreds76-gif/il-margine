#!/usr/bin/env python3
"""Small projection helpers for tennis aces/double-fault research boards."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Projection:
    expected_aces: float
    expected_dfs: float
    expected_service_points: float
    expected_service_games: float
    ace_rate: float
    df_rate: float
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


def project_player(
    *,
    tour: str,
    player_rows: dict[str, dict[str, str]],
    opponent_rows: dict[str, dict[str, str]],
    factor_row: dict[str, str],
    expected_match_games: float,
    slam_matches: int,
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

    slam_ace_factor = _float(factor_row.get("ace_factor"), 1.0) or 1.0
    slam_df_factor = _float(factor_row.get("df_factor"), 1.0) or 1.0
    ret_factor = _clip((prior_ret_first / max(0.18, opp_ret_first)) ** 0.6, 0.76, 1.22)

    ace_rate_adj = _clip(ace_rate * slam_ace_factor * ret_factor, 0.002, 0.28)
    df_rate_adj = _clip(df_rate * slam_df_factor, 0.002, 0.16)
    expected_service_games = max(4.0, expected_match_games * 0.5)
    expected_service_points = expected_service_games * _clip(svpt_per_svg, 4.8, 8.6)

    expected_aces = ace_rate_adj * expected_service_points
    expected_dfs = df_rate_adj * expected_service_points

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
        ace_confidence=ace_confidence,
        df_confidence=df_confidence,
        notes=tuple(notes),
    )


def poisson_p_over(line: float, mean: float) -> float:
    if mean <= 0:
        return 0.0
    cutoff = math.floor(line)
    cdf = 0.0
    term = math.exp(-mean)
    cdf += term
    for k in range(1, cutoff + 1):
        term *= mean / k
        cdf += term
    return _clip(1.0 - cdf, 0.0, 1.0)


def poisson_p_under(line: float, mean: float) -> float:
    if mean <= 0:
        return 1.0
    # For common half-point lines, under is simply count <= floor(line).
    cutoff = math.floor(line)
    cdf = 0.0
    term = math.exp(-mean)
    cdf += term
    for k in range(1, cutoff + 1):
        term *= mean / k
        cdf += term
    return _clip(cdf, 0.0, 1.0)
