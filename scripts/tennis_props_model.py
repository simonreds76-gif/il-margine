#!/usr/bin/env python3
"""Small projection helpers for tennis aces/double-fault research boards."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.lib.tennis_prob import expected_match_service_points

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

DEFAULT_TIEBREAK_CALIBRATION_PATH = ROOT / "data" / "tennis-props" / "tiebreak-calibration.json"
DEFAULT_BREAK_GATE_PATH = ROOT / "data" / "tennis-props" / "backtest" / "breaks-stage0-gate.json"
_TIEBREAK_CALIBRATION_OVERRIDE: dict[str, object] | None = None


@dataclass(frozen=True)
class Projection:
    expected_aces: float
    expected_dfs: float
    expected_breaks_for: float
    expected_broken: float
    expected_total_breaks: float
    first_set_tiebreak_prob: float
    match_tiebreak_prob: float
    first_set_tiebreak_base_prob: float
    match_tiebreak_base_prob: float
    first_set_tiebreak_fair_yes: float
    match_tiebreak_fair_yes: float
    expected_service_points: float
    expected_service_games: float
    ace_rate: float
    df_rate: float
    ace_rate_pre_opponent: float
    opponent_return_ratio: float
    opponent_return_factor: float
    ace_count_correction: float
    break_rate: float
    broken_rate: float
    player_service_point_win: float
    opponent_service_point_win: float
    same_tournament_matches: int
    same_tournament_svpt: int
    same_tournament_ace_weight: float
    same_tournament_df_weight: float
    same_tournament_breaks_for: int
    same_tournament_broken: int
    same_tournament_total_breaks: int
    current_env_matches: int
    current_env_svpt: int
    current_env_weight: float
    current_env_ace_factor: float
    current_env_df_factor: float
    current_env_break_factor: float
    player_tiebreak_factor: float
    player_tiebreak_sample: int
    player_match_tiebreak_rate: float
    opponent_match_tiebreak_rate: float
    venue_first_set_tiebreak_factor: float
    venue_match_tiebreak_factor: float
    current_env_first_set_tiebreak_factor: float
    current_env_match_tiebreak_factor: float
    ace_confidence: str
    df_confidence: str
    break_confidence: str
    tiebreak_confidence: str
    break_notes: tuple[str, ...]
    tiebreak_notes: tuple[str, ...]
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


def _blend_tiebreak_rate(
    rows_by_window: dict[str, dict[str, str]],
    rate_field: str,
    sample_field: str,
    prior_rate: float,
    prior_weight: float,
) -> tuple[float, int]:
    return _blend_rate(rows_by_window, rate_field, sample_field, prior_rate, prior_weight)


def _player_tiebreak_factor(
    player_rows: dict[str, dict[str, str]],
    opponent_rows: dict[str, dict[str, str]],
    *,
    prior_set_rate: float,
    prior_first_set_rate: float,
    prior_match_rate: float,
    player_all_rows: dict[str, dict[str, str]] | None = None,
    opponent_all_rows: dict[str, dict[str, str]] | None = None,
) -> tuple[float, int, float, float]:
    def blended_with_all(
        surface_rows: dict[str, dict[str, str]],
        all_rows: dict[str, dict[str, str]] | None,
        rate_field: str,
        sample_field: str,
        prior_rate: float,
        surface_prior_weight: float,
        all_prior_weight: float,
    ) -> tuple[float, int]:
        surface_rate, surface_sample = _blend_tiebreak_rate(
            surface_rows,
            rate_field,
            sample_field,
            prior_rate,
            surface_prior_weight,
        )
        all_rate, all_sample = _blend_tiebreak_rate(
            all_rows or {},
            rate_field,
            sample_field,
            prior_rate,
            all_prior_weight,
        )
        if all_sample <= 0:
            return surface_rate, surface_sample

        # Surface is still king, but tiny grass samples should not erase a
        # repeatable player style. The all-surface term carries big-server /
        # grinder tendency until the surface sample becomes meaningful.
        surface_weight = _clip(surface_sample / 80.0, 0.0, 1.0)
        all_weight = _clip(all_sample / 180.0, 0.0, 1.0) * (1.0 - 0.45 * surface_weight)
        prior_weight = 0.25
        denominator = prior_weight + surface_weight + all_weight
        rate = (
            prior_rate * prior_weight
            + surface_rate * surface_weight
            + all_rate * all_weight
        ) / denominator
        effective_sample = int(max(surface_sample, min(all_sample, 180)))
        return rate, effective_sample

    player_set_rate, player_set_sample = blended_with_all(
        player_rows,
        player_all_rows,
        "tiebreak_set_rate",
        "sets_played",
        prior_set_rate,
        28.0,
        60.0,
    )
    opponent_set_rate, opponent_set_sample = blended_with_all(
        opponent_rows,
        opponent_all_rows,
        "tiebreak_set_rate",
        "sets_played",
        prior_set_rate,
        28.0,
        60.0,
    )
    player_first_set_rate, player_first_set_sample = blended_with_all(
        player_rows,
        player_all_rows,
        "first_set_tiebreak_rate",
        "matches",
        prior_first_set_rate,
        16.0,
        36.0,
    )
    opponent_first_set_rate, opponent_first_set_sample = blended_with_all(
        opponent_rows,
        opponent_all_rows,
        "first_set_tiebreak_rate",
        "matches",
        prior_first_set_rate,
        16.0,
        36.0,
    )
    player_match_rate, player_match_sample = blended_with_all(
        player_rows,
        player_all_rows,
        "match_tiebreak_rate",
        "matches",
        prior_match_rate,
        16.0,
        36.0,
    )
    opponent_match_rate, opponent_match_sample = blended_with_all(
        opponent_rows,
        opponent_all_rows,
        "match_tiebreak_rate",
        "matches",
        prior_match_rate,
        16.0,
        36.0,
    )
    sample = int(
        (
            player_set_sample
            + opponent_set_sample
            + player_first_set_sample
            + opponent_first_set_sample
            + player_match_sample
            + opponent_match_sample
        )
        / 6
    )
    if sample <= 0 or prior_set_rate <= 0 or prior_match_rate <= 0:
        return 1.0, sample, player_match_rate, opponent_match_rate

    def pair_style_ratio(player_rate: float, opponent_rate: float, prior_rate: float) -> float:
        if prior_rate <= 0:
            return 1.0
        player_ratio = max(0.20, player_rate / prior_rate)
        opponent_ratio = max(0.20, opponent_rate / prior_rate)
        max_ratio = max(player_ratio, opponent_ratio)
        mean_ratio = (player_ratio + opponent_ratio) * 0.5
        geom_ratio = math.sqrt(player_ratio * opponent_ratio)
        # A tiebreak-prone server can drag a match into breakers even if the
        # opponent is more ordinary, so do not let geometric averaging fully
        # cancel a strong single-player signal.
        return 0.45 * max_ratio + 0.35 * geom_ratio + 0.20 * mean_ratio

    set_ratio = pair_style_ratio(player_set_rate, opponent_set_rate, prior_set_rate)
    first_ratio = pair_style_ratio(player_first_set_rate, opponent_first_set_rate, prior_first_set_rate)
    match_ratio = pair_style_ratio(player_match_rate, opponent_match_rate, prior_match_rate)
    raw = (max(0.25, set_ratio) ** 0.40) * (max(0.25, first_ratio) ** 0.25) * (max(0.25, match_ratio) ** 0.35)
    sample_weight = _clip(sample / 55.0, 0.0, 1.0)
    # Historical player tendency is useful for monster-server profiles, but it
    # is a correction to serve/return math, not a replacement for it.
    adjusted = math.exp(math.log(max(0.35, min(2.85, raw))) * 0.55 * sample_weight)
    return _clip(adjusted, 0.82, 1.24), sample, player_match_rate, opponent_match_rate


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _service_point_win_from_row(row: dict[str, str], default: float) -> float | None:
    first_pct = _float(row.get("first_serve_pct"))
    first_win = _float(row.get("first_serve_win_pct"))
    second_win = _float(row.get("second_serve_win_pct"))
    if first_pct is None or first_win is None or second_win is None:
        return None
    return _clip(first_pct * first_win + (1.0 - first_pct) * second_win, 0.42, 0.76)


def _blend_service_point_win(
    rows_by_window: dict[str, dict[str, str]],
    *,
    prior_value: float,
    prior_weight: float,
) -> tuple[float, int]:
    weights = {
        "L12M": 1.0,
        "L24M": 0.55,
        "career_4y": 0.25,
    }
    numerator = prior_value * prior_weight
    denominator = prior_weight
    max_sample = 0
    for window, weight in weights.items():
        row = rows_by_window.get(window) or {}
        sample = _int(row.get("svpt"))
        value = _service_point_win_from_row(row, prior_value)
        if sample <= 0 or value is None:
            continue
        numerator += value * sample * weight
        denominator += sample * weight
        max_sample = max(max_sample, sample)
    return numerator / denominator if denominator > 0 else prior_value, max_sample


def _return_point_win_vs_server_mix(
    rows_by_window: dict[str, dict[str, str]],
    *,
    server_first_serve_pct: float,
    prior_ret_first: float,
    prior_ret_second: float,
) -> tuple[float, int]:
    ret_first, ret_first_sample = _blend_rate(
        rows_by_window,
        "ret_first_win_pct",
        "ret_first_points",
        prior_ret_first,
        350.0,
    )
    ret_second, ret_second_sample = _blend_rate(
        rows_by_window,
        "ret_second_win_pct",
        "ret_second_points",
        prior_ret_second,
        350.0,
    )
    return (
        _clip(server_first_serve_pct * ret_first + (1.0 - server_first_serve_pct) * ret_second, 0.20, 0.56),
        min(ret_first_sample, ret_second_sample),
    )


def _prob_game_from_point(p: float) -> float:
    p = _clip(p, 0.01, 0.99)
    d = (p * p) / (1.0 - 2.0 * p * (1.0 - p))
    return p**4 + 4 * p**4 * (1 - p) + 10 * p**4 * (1 - p) ** 2 + 20 * p**3 * (1 - p) ** 3 * d


@lru_cache(maxsize=8192)
def _set_no_tb_outcomes(pa_int: int, pb_int: int, a_serves_first: bool) -> tuple[float, float, float]:
    """Return (A wins set without TB, B wins set without TB, set reaches TB)."""
    p_a = _clip(pa_int / 10000.0, 0.01, 0.99)
    p_b = _clip(pb_int / 10000.0, 0.01, 0.99)
    pg_a = _prob_game_from_point(p_a)
    pg_b = _prob_game_from_point(p_b)
    reach: dict[tuple[int, int, bool], float] = {(0, 0, a_serves_first): 1.0}
    a_no_tb = 0.0
    b_no_tb = 0.0
    reaches_tb = 0.0

    for total_games in range(13):
        current = [(state, prob) for state, prob in reach.items() if state[0] + state[1] == total_games and prob > 0]
        for (a_games, b_games, a_serves), state_prob in current:
            if a_games >= 6 and a_games - b_games >= 2:
                a_no_tb += state_prob
                continue
            if b_games >= 6 and b_games - a_games >= 2:
                b_no_tb += state_prob
                continue
            if a_games == 6 and b_games == 6:
                reaches_tb += state_prob
                continue
            p_win_game = pg_a if a_serves else (1.0 - pg_b)
            reach[(a_games + 1, b_games, not a_serves)] = reach.get((a_games + 1, b_games, not a_serves), 0.0) + state_prob * p_win_game
            reach[(a_games, b_games + 1, not a_serves)] = reach.get((a_games, b_games + 1, not a_serves), 0.0) + state_prob * (1.0 - p_win_game)

    return _clip(a_no_tb, 0.0, 1.0), _clip(b_no_tb, 0.0, 1.0), _clip(reaches_tb, 0.0, 1.0)


def _set_tiebreak_prob(p_a: float, p_b: float, a_serves_first: bool) -> float:
    pa_int = int(round(_clip(p_a, 0.01, 0.99) * 10000))
    pb_int = int(round(_clip(p_b, 0.01, 0.99) * 10000))
    return _set_no_tb_outcomes(pa_int, pb_int, a_serves_first)[2]


def _match_tiebreak_prob(p_a: float, p_b: float, *, best_of: int) -> float:
    pa_int = int(round(_clip(p_a, 0.01, 0.99) * 10000))
    pb_int = int(round(_clip(p_b, 0.01, 0.99) * 10000))
    sets_needed = 3 if best_of >= 5 else 2
    serve_order = [True, False, True, False, True]

    @lru_cache(maxsize=256)
    def no_tb_from(set_index: int, a_wins: int, b_wins: int) -> float:
        if a_wins >= sets_needed or b_wins >= sets_needed:
            return 1.0
        if set_index >= best_of:
            return 0.0
        a_no_tb, b_no_tb, _ = _set_no_tb_outcomes(pa_int, pb_int, serve_order[set_index])
        return (
            a_no_tb * no_tb_from(set_index + 1, a_wins + 1, b_wins)
            + b_no_tb * no_tb_from(set_index + 1, a_wins, b_wins + 1)
        )

    return _clip(1.0 - no_tb_from(0, 0, 0), 0.0, 1.0)


def _prob_fair_yes(prob: float) -> float:
    return 999.0 if prob <= 0 else 1.0 / _clip(prob, 0.001, 0.999)


def _apply_probability_factors(
    base_prob: float,
    *,
    venue_factor: float,
    current_factor: float,
    low: float,
    high: float,
) -> float:
    # Multiplicative probability nudges are deliberately conservative because
    # the exact serve/return model is still the primary signal.
    return _clip(base_prob * venue_factor * current_factor, low, high)


def _logit(prob: float) -> float:
    p = _clip(prob, 0.001, 0.999)
    return math.log(p / (1.0 - p))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _apply_tiebreak_probability_factors(
    base_prob: float,
    *,
    venue_factor: float,
    current_factor: float,
    low: float,
    high: float,
) -> float:
    # Tie-break venue/live adjustments behave better in logit space. A venue
    # at 1.10 becomes a small odds-ratio nudge, not a raw +10% probability jump.
    delta = _clip(math.log(max(0.50, venue_factor)), math.log(0.82), math.log(1.22))
    delta += _clip(math.log(max(0.50, current_factor)), math.log(0.90), math.log(1.12))
    return _clip(_sigmoid(_logit(base_prob) + delta), low, high)


def set_tiebreak_calibration_override(calibration: dict[str, object] | None) -> None:
    global _TIEBREAK_CALIBRATION_OVERRIDE
    _TIEBREAK_CALIBRATION_OVERRIDE = calibration
    _load_tiebreak_calibration.cache_clear()


@lru_cache(maxsize=1)
def _load_tiebreak_calibration() -> dict[str, object]:
    if _TIEBREAK_CALIBRATION_OVERRIDE is not None:
        return _TIEBREAK_CALIBRATION_OVERRIDE
    path = DEFAULT_TIEBREAK_CALIBRATION_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _calibration_keys(*, market: str, tour: str, surface: str, best_of: int) -> list[str]:
    tour_key = (tour or "").strip().upper() or "ALL"
    surface_key = (surface or "").strip().title() or "ALL"
    bo_key = f"BO{best_of}" if market == "match" else "ALL"
    return [
        f"{market}|{tour_key}|{surface_key}|{bo_key}",
        f"{market}|{tour_key}|{surface_key}|ALL",
        f"{market}|{tour_key}|ALL|{bo_key}",
        f"{market}|{tour_key}|ALL|ALL",
        f"{market}|ALL|ALL|ALL",
    ]


def _calibrate_tiebreak_prob(
    prob: float,
    *,
    market: str,
    tour: str,
    surface: str,
    best_of: int,
) -> tuple[float, str | None]:
    payload = _load_tiebreak_calibration()
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, dict):
        return prob, None
    for key in _calibration_keys(market=market, tour=tour, surface=surface, best_of=best_of):
        params = keys.get(key)
        if not isinstance(params, dict):
            continue
        a = _float(params.get("a"))
        b = _float(params.get("b"))
        if a is None or b is None:
            continue
        calibrated = _sigmoid(a * _logit(prob) + b)
        return _clip(calibrated, 0.001, 0.999), key
    return prob, None


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
    player_all_rows: dict[str, dict[str, str]] | None = None,
    opponent_all_rows: dict[str, dict[str, str]] | None = None,
    factor_row: dict[str, str],
    expected_match_games: float,
    slam_matches: int,
    same_tournament_row: dict[str, str] | None = None,
    current_tournament_env_row: dict[str, str] | None = None,
    service_points_mode: str = "incumbent",
    ace_return_exponent: float = 0.6,
    apply_slam_bias_correction: bool = True,
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
    prior_ret_second = 0.520 if tour_norm == "atp" else 0.550
    prior_service_point_win = 0.635 if tour_norm == "atp" else 0.585
    prior_break_rate = 0.235 if tour_norm == "atp" else 0.285
    prior_broken_rate = 0.235 if tour_norm == "atp" else 0.285

    ace_rate, surface_svpt = _blend_rate(
        player_rows, "ace_rate", "svpt", prior_ace, ace_prior_weight
    )
    df_rate, _ = _blend_rate(player_rows, "df_rate", "svpt", prior_df, df_prior_weight)
    break_for_rate, return_games_sample = _blend_rate(
        player_rows, "break_for_rate", "return_games", prior_break_rate, 80.0
    )
    broken_rate, service_games_sample = _blend_rate(
        player_rows, "broken_rate", "service_games_break_sample", prior_broken_rate, 80.0
    )
    opp_break_for_rate, opp_return_games_sample = _blend_rate(
        opponent_rows, "break_for_rate", "return_games", prior_break_rate, 80.0
    )
    opp_broken_rate, opp_service_games_sample = _blend_rate(
        opponent_rows, "broken_rate", "service_games_break_sample", prior_broken_rate, 80.0
    )
    player_first_serve_pct = _blend_value(
        player_rows,
        "first_serve_pct",
        "svpt",
        0.62 if tour_norm == "atp" else 0.60,
        400.0,
    )
    opponent_first_serve_pct = _blend_value(
        opponent_rows,
        "first_serve_pct",
        "svpt",
        0.62 if tour_norm == "atp" else 0.60,
        400.0,
    )
    player_service_baseline, service_point_sample = _blend_service_point_win(
        player_rows,
        prior_value=prior_service_point_win,
        prior_weight=400.0 if tour_norm == "atp" else 600.0,
    )
    opponent_service_baseline, opponent_service_point_sample = _blend_service_point_win(
        opponent_rows,
        prior_value=prior_service_point_win,
        prior_weight=400.0 if tour_norm == "atp" else 600.0,
    )
    opp_return_vs_player, opp_return_mix_sample = _return_point_win_vs_server_mix(
        opponent_rows,
        server_first_serve_pct=player_first_serve_pct,
        prior_ret_first=prior_ret_first,
        prior_ret_second=prior_ret_second,
    )
    player_return_vs_opp, player_return_mix_sample = _return_point_win_vs_server_mix(
        player_rows,
        server_first_serve_pct=opponent_first_serve_pct,
        prior_ret_first=prior_ret_first,
        prior_ret_second=prior_ret_second,
    )
    player_service_point_win = _clip(math.sqrt(player_service_baseline * (1.0 - opp_return_vs_player)), 0.45, 0.76)
    opponent_service_point_win = _clip(math.sqrt(opponent_service_baseline * (1.0 - player_return_vs_opp)), 0.45, 0.76)

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
        notes.append("TOURNAMENT_DEBUT")
    if same_matches > 0:
        notes.append(f"SAME_TOURNAMENT_N{same_matches}")

    slam_ace_factor = _float(factor_row.get("ace_factor"), 1.0) or 1.0
    slam_df_factor = _float(factor_row.get("df_factor"), 1.0) or 1.0
    current_env_row = current_tournament_env_row or {}
    current_env_matches = _int(current_env_row.get("matches"))
    current_env_svpt = _int(current_env_row.get("svpt"))
    current_env_weight = _float(current_env_row.get("weight"), 0.0) or 0.0
    current_env_ace_factor = _float(current_env_row.get("ace_factor"), 1.0) or 1.0
    current_env_df_factor = _float(current_env_row.get("df_factor"), 1.0) or 1.0
    current_env_break_factor = _float(current_env_row.get("break_factor"), 1.0) or 1.0
    current_env_first_set_tiebreak_factor = _float(current_env_row.get("first_set_tiebreak_factor"), 1.0) or 1.0
    current_env_match_tiebreak_factor = _float(current_env_row.get("match_tiebreak_factor"), 1.0) or 1.0
    if current_env_weight > 0 and current_env_matches > 0:
        notes.append(f"EVENT_ENV_N{current_env_matches}")
    opponent_return_ratio = prior_ret_first / max(0.18, opp_ret_first)
    ret_factor = _clip(opponent_return_ratio ** ace_return_exponent, 0.76, 1.22)

    ace_rate_pre_opponent = ace_rate * slam_ace_factor * current_env_ace_factor
    ace_rate_adj = _clip(ace_rate_pre_opponent * ret_factor, 0.002, 0.28)
    df_rate_adj = _clip(df_rate * slam_df_factor * current_env_df_factor, 0.002, 0.16)
    best_of = 5 if str(factor_row.get("tournament") or "").strip() in {"Australian Open", "Roland Garros", "Wimbledon", "US Open"} and tour.upper() == "ATP" else 3
    expected_service_games = max(4.0, expected_match_games * 0.5)
    expected_service_points = expected_service_games * _clip(svpt_per_svg, 4.8, 8.6)
    if service_points_mode == "matchup_recursion":
        workload = expected_match_service_points(
            player_service_point_win,
            opponent_service_point_win,
            best_of=best_of,
        )
        expected_service_games = max(4.0, workload.player_a_games)
        expected_service_points = max(20.0, workload.player_a_points)
        notes.append("SERVICE_POINTS_RECURSION_SHADOW")
    elif service_points_mode != "incumbent":
        raise ValueError(f"Unsupported service_points_mode: {service_points_mode}")

    # Breaks are game-count props, so estimate them from both sides: a player's
    # return break rate and the opponent's broken rate. Keep it market-research
    # only until we have real Bet365 line history.
    break_rate_adj = math.sqrt(max(0.0001, break_for_rate) * max(0.0001, opp_broken_rate))
    broken_rate_adj = math.sqrt(max(0.0001, broken_rate) * max(0.0001, opp_break_for_rate))
    break_rate_adj = _clip(break_rate_adj * current_env_break_factor, 0.06, 0.48)
    broken_rate_adj = _clip(broken_rate_adj * current_env_break_factor, 0.06, 0.48)
    same_breaks_for = _int((same_tournament_row or {}).get("breaks_for"))
    same_broken = _int((same_tournament_row or {}).get("broken"))
    same_total_breaks = same_breaks_for + same_broken
    if same_matches > 0 and expected_service_games > 0:
        same_break_weight = _clip(same_matches / 8.0, 0.0, 0.25)
        same_break_rate = _clip(same_breaks_for / max(1.0, same_matches * expected_service_games), 0.02, 0.55)
        same_broken_rate = _clip(same_broken / max(1.0, same_matches * expected_service_games), 0.02, 0.55)
        break_rate_adj = (1.0 - same_break_weight) * break_rate_adj + same_break_weight * same_break_rate
        broken_rate_adj = (1.0 - same_break_weight) * broken_rate_adj + same_break_weight * same_broken_rate

    expected_aces = ace_rate_adj * expected_service_points
    expected_dfs = df_rate_adj * expected_service_points
    expected_breaks_for = break_rate_adj * expected_service_games
    expected_broken = broken_rate_adj * expected_service_games
    expected_total_breaks = expected_breaks_for + expected_broken
    first_set_tiebreak_base_prob = _set_tiebreak_prob(player_service_point_win, opponent_service_point_win, True)
    venue_first_set_tiebreak_factor = _float(factor_row.get("first_set_tiebreak_factor"), 1.0) or 1.0
    venue_match_tiebreak_factor = _float(factor_row.get("match_tiebreak_factor"), 1.0) or 1.0
    prior_tiebreak_set = _float(factor_row.get("tiebreak_set_rate"), None)
    if prior_tiebreak_set is None:
        prior_tiebreak_set = _float(factor_row.get("tour_surface_baseline_tiebreak_set"), 0.18) or 0.18
    prior_first_set_tiebreak = _float(factor_row.get("first_set_tiebreak_rate"), None)
    if prior_first_set_tiebreak is None:
        prior_first_set_tiebreak = _float(factor_row.get("tour_surface_baseline_first_set_tiebreak"), prior_tiebreak_set) or prior_tiebreak_set
    prior_match_tiebreak = _float(factor_row.get("match_tiebreak_rate"), None)
    if prior_match_tiebreak is None:
        prior_match_tiebreak = _float(factor_row.get("tour_surface_baseline_match_tiebreak"), 0.36 if best_of >= 5 else 0.28) or (0.36 if best_of >= 5 else 0.28)
    player_tiebreak_factor, player_tiebreak_sample, player_match_tiebreak_rate, opponent_match_tiebreak_rate = _player_tiebreak_factor(
        player_rows,
        opponent_rows,
        prior_set_rate=prior_tiebreak_set,
        prior_first_set_rate=prior_first_set_tiebreak,
        prior_match_rate=prior_match_tiebreak,
        player_all_rows=player_all_rows,
        opponent_all_rows=opponent_all_rows,
    )
    first_set_tiebreak_prob = _apply_tiebreak_probability_factors(
        first_set_tiebreak_base_prob,
        venue_factor=venue_first_set_tiebreak_factor * player_tiebreak_factor,
        current_factor=current_env_first_set_tiebreak_factor,
        low=0.015,
        high=0.58 if best_of == 3 else 0.62,
    )
    match_tiebreak_base_prob = _clip(
        _match_tiebreak_prob(player_service_point_win, opponent_service_point_win, best_of=best_of),
        0.015,
        0.92 if best_of >= 5 else 0.86,
    )
    match_tiebreak_note = "MATCH_TB_RECURSION"
    match_tiebreak_prob = _apply_tiebreak_probability_factors(
        match_tiebreak_base_prob,
        venue_factor=venue_match_tiebreak_factor * player_tiebreak_factor,
        current_factor=current_env_match_tiebreak_factor,
        low=0.025,
        high=0.94 if best_of >= 5 else 0.86,
    )
    surface = str(factor_row.get("surface") or "")
    first_set_tiebreak_prob, first_cal_key = _calibrate_tiebreak_prob(
        first_set_tiebreak_prob,
        market="first_set",
        tour=tour,
        surface=surface,
        best_of=best_of,
    )
    match_tiebreak_prob, match_cal_key = _calibrate_tiebreak_prob(
        match_tiebreak_prob,
        market="match",
        tour=tour,
        surface=surface,
        best_of=best_of,
    )
    tournament = str(factor_row.get("tournament") or "").strip()
    correction = SLAM_COUNT_BIAS_CORRECTION.get((tour.upper(), tournament))
    ace_count_correction = 0.0
    if correction and apply_slam_bias_correction:
        ace_count_correction = _clip(correction.get("aces", 0.0), -0.90, 0.90)
        expected_aces = max(0.0, expected_aces + ace_count_correction)
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

    break_sample = min(return_games_sample, service_games_sample, opp_return_games_sample, opp_service_games_sample)
    break_notes = ["BREAK_RESEARCH_ONLY", "TOTAL_GAMES_DEPENDENT"]
    if break_sample >= 180 and surface_svpt >= 1500:
        break_confidence = "HIGH"
    elif break_sample >= 60 or surface_svpt >= 500:
        break_confidence = "MED"
    else:
        break_confidence = "LOW"
        break_notes.append("BREAK_LOW_SAMPLE")
    tiebreak_notes = ["TIEBREAK_RESEARCH_ONLY", "SERVE_RETURN_DEPENDENT", match_tiebreak_note]
    if abs(player_tiebreak_factor - 1.0) >= 0.025:
        tiebreak_notes.append("PLAYER_TB_TENDENCY")
    if first_cal_key or match_cal_key:
        tiebreak_notes.append("TIEBREAK_PLATT_CALIBRATED")
    venue_matches = _int(factor_row.get("matches"))
    tiebreak_sample = min(service_point_sample, opponent_service_point_sample, opp_return_mix_sample, player_return_mix_sample)
    if tiebreak_sample >= 1200 and venue_matches >= 50:
        tiebreak_confidence = "HIGH"
    elif tiebreak_sample >= 500 or venue_matches >= 30:
        tiebreak_confidence = "MED"
    else:
        tiebreak_confidence = "LOW"
        tiebreak_notes.append("TIEBREAK_LOW_SAMPLE")

    return Projection(
        expected_aces=expected_aces,
        expected_dfs=expected_dfs,
        expected_breaks_for=expected_breaks_for,
        expected_broken=expected_broken,
        expected_total_breaks=expected_total_breaks,
        first_set_tiebreak_prob=first_set_tiebreak_prob,
        match_tiebreak_prob=match_tiebreak_prob,
        first_set_tiebreak_base_prob=first_set_tiebreak_base_prob,
        match_tiebreak_base_prob=match_tiebreak_base_prob,
        first_set_tiebreak_fair_yes=_prob_fair_yes(first_set_tiebreak_prob),
        match_tiebreak_fair_yes=_prob_fair_yes(match_tiebreak_prob),
        expected_service_points=expected_service_points,
        expected_service_games=expected_service_games,
        ace_rate=ace_rate_adj,
        df_rate=df_rate_adj,
        ace_rate_pre_opponent=ace_rate_pre_opponent,
        opponent_return_ratio=opponent_return_ratio,
        opponent_return_factor=ret_factor,
        ace_count_correction=ace_count_correction,
        break_rate=break_rate_adj,
        broken_rate=broken_rate_adj,
        player_service_point_win=player_service_point_win,
        opponent_service_point_win=opponent_service_point_win,
        same_tournament_matches=same_matches,
        same_tournament_svpt=same_svpt,
        same_tournament_ace_weight=same_ace_weight,
        same_tournament_df_weight=same_df_weight,
        same_tournament_breaks_for=same_breaks_for,
        same_tournament_broken=same_broken,
        same_tournament_total_breaks=same_total_breaks,
        current_env_matches=current_env_matches,
        current_env_svpt=current_env_svpt,
        current_env_weight=current_env_weight,
        current_env_ace_factor=current_env_ace_factor,
        current_env_df_factor=current_env_df_factor,
        current_env_break_factor=current_env_break_factor,
        player_tiebreak_factor=player_tiebreak_factor,
        player_tiebreak_sample=player_tiebreak_sample,
        player_match_tiebreak_rate=player_match_tiebreak_rate,
        opponent_match_tiebreak_rate=opponent_match_tiebreak_rate,
        venue_first_set_tiebreak_factor=venue_first_set_tiebreak_factor,
        venue_match_tiebreak_factor=venue_match_tiebreak_factor,
        current_env_first_set_tiebreak_factor=current_env_first_set_tiebreak_factor,
        current_env_match_tiebreak_factor=current_env_match_tiebreak_factor,
        ace_confidence=ace_confidence,
        df_confidence=df_confidence,
        break_confidence=break_confidence,
        tiebreak_confidence=tiebreak_confidence,
        break_notes=tuple(break_notes),
        tiebreak_notes=tuple(tiebreak_notes),
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
    market_key = "dfs" if str(market or "").lower().replace(" ", "_") in {"double_faults", "double_fault", "df", "dfs", "match_double_faults"} else "aces"
    return DEFAULT_COUNT_DISPERSION_ALPHA.get((tour_key, market_key), 0.25 if market_key == "aces" else 0.12)


@lru_cache(maxsize=4)
def load_break_gate(path: str = str(DEFAULT_BREAK_GATE_PATH)) -> dict[str, object]:
    gate_path = Path(path)
    if not gate_path.exists():
        return {}
    try:
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_break_distribution(
    tour: str,
    scope: str,
    *,
    gate_path: Path | str = DEFAULT_BREAK_GATE_PATH,
) -> tuple[str, float | None, bool]:
    """Return the training-selected count family and outcome-only gate state."""
    gate = load_break_gate(str(gate_path))
    scopes = gate.get("scopes")
    scope_row = scopes.get(scope) if isinstance(scopes, dict) else None
    tours = scope_row.get("tours") if isinstance(scope_row, dict) else None
    row = tours.get(str(tour or "").upper()) if isinstance(tours, dict) else None
    if not isinstance(row, dict):
        return "poisson", None, False
    distribution = str(row.get("distribution") or "poisson")
    alpha_raw = row.get("model_alpha")
    try:
        alpha = float(alpha_raw) if alpha_raw is not None else None
    except (TypeError, ValueError):
        alpha = None
    passed = bool(scope_row.get("passed")) and bool(row.get("passed"))
    return distribution, alpha, passed


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
