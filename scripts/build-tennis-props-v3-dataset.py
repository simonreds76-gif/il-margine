#!/usr/bin/env python3
"""Build a causal all-main-tour feature matrix for tennis props v3.

Tournament start dates are the finest reliable Sackmann timestamps. Every
event sharing a start date is therefore featurised before any result from that
date is added to rolling state. This prevents later rounds or parallel events
from leaking into pre-match features.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SACKMANN_DIR = ROOT / "data" / "sackmann"
DEFAULT_OUT = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-v3-all-tour-features.csv"
ATP_LEVELS = {"A", "M", "G", "F"}
WTA_LEVELS = {"I", "P", "PM", "G", "F"}
WINDOWS = {"l12m": 365, "l24m": 730, "career4y": 1460}


@dataclass(frozen=True)
class Observation:
    match_date: date
    aces: float
    dfs: int
    svpt: int
    svgms: int
    first_in: int
    first_won: int
    second_won: int
    opponent_aces: float
    opponent_svpt: int
    opponent_first_in: int
    opponent_first_won: int
    opponent_second_won: int


@dataclass(frozen=True)
class ActivityObservation:
    match_date: date
    surface: str
    source: str
    rank: int


def parse_int(value: object, default: int = 0) -> int:
    try:
        text = str(value or "").strip()
        return int(float(text)) if text else default
    except (TypeError, ValueError):
        return default


def parse_float(value: object, default: float = 0.0) -> float:
    try:
        text = str(value or "").strip()
        parsed = float(text) if text else default
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def norm_surface(value: object) -> str:
    text = str(value or "").strip().lower()
    if "hard" in text:
        return "Hard"
    if "clay" in text:
        return "Clay"
    if "grass" in text:
        return "Grass"
    if "carpet" in text:
        return "Carpet"
    return "Unknown"


def norm_tournament(value: object) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def score_games(value: object) -> int:
    text = str(value or "")
    if re.search(r"\b(W/O|WO|DEF)\b", text, re.I):
        return 0
    return sum(int(a) + int(b) for a, b in re.findall(r"(\d+)-(\d+)", text))


def blank_stats() -> dict[str, float]:
    return defaultdict(float)


def add_observation(stats: dict[str, float], obs: Observation) -> None:
    stats["matches"] += 1
    stats["aces"] += obs.aces
    stats["dfs"] += obs.dfs
    stats["svpt"] += obs.svpt
    stats["svgms"] += obs.svgms
    stats["first_in"] += obs.first_in
    stats["first_won"] += obs.first_won
    stats["second_won"] += obs.second_won
    stats["second_attempts"] += max(0, obs.svpt - obs.first_in)
    stats["ret_first_points"] += obs.opponent_first_in
    stats["ret_first_won"] += max(0, obs.opponent_first_in - obs.opponent_first_won)
    stats["ret_second_points"] += max(0, obs.opponent_svpt - obs.opponent_first_in)
    stats["ret_second_won"] += max(
        0,
        obs.opponent_svpt - obs.opponent_first_in - obs.opponent_second_won,
    )
    stats["opponent_aces"] += obs.opponent_aces
    stats["opponent_svpt"] += obs.opponent_svpt


def add_side_aggregate(stats: dict[str, float], obs: Observation) -> None:
    add_observation(stats, obs)


def safe_rate(stats: dict[str, float], numerator: str, denominator: str, fallback: float) -> float:
    den = stats.get(denominator, 0.0)
    return stats.get(numerator, 0.0) / den if den > 0 else fallback


def rolling_stats(history: list[Observation], as_of: date, days: int) -> dict[str, float]:
    stats = blank_stats()
    for obs in reversed(history):
        age = (as_of - obs.match_date).days
        if age <= 0:
            continue
        if age > days:
            break
        add_observation(stats, obs)
    return stats


def activity_features(
    history: list[ActivityObservation],
    as_of: date,
    surface: str,
    current_rank: int,
) -> dict[str, float]:
    """Return lagged all-level activity and ranking features.

    The caller updates history only after every match on ``as_of`` has been
    featurised, so these values cannot contain same-day results.
    """
    prior = [obs for obs in history if obs.match_date < as_of]
    if prior:
        days_since_match = min(1460, (as_of - prior[-1].match_date).days)
    else:
        days_since_match = 1460
    prior_surface = [obs for obs in prior if obs.surface == surface]
    if prior_surface:
        days_since_surface_match = min(
            1460, (as_of - prior_surface[-1].match_date).days
        )
    else:
        days_since_surface_match = 1460

    recent_90 = [
        obs for obs in prior if 0 < (as_of - obs.match_date).days <= 90
    ]
    recent_365 = [
        obs for obs in prior if 0 < (as_of - obs.match_date).days <= 365
    ]
    lower_90 = sum(obs.source != "main" for obs in recent_90)
    lower_365 = sum(obs.source != "main" for obs in recent_365)

    def rank_at_lag(days: int) -> tuple[int, int]:
        cutoff = as_of - timedelta(days=days)
        for obs in reversed(prior):
            if obs.match_date <= cutoff and 0 < obs.rank < 999:
                return obs.rank, 1
        return current_rank, 0

    rank_90, rank_90_known = rank_at_lag(90)
    rank_365, rank_365_known = rank_at_lag(365)
    safe_current_rank = max(1, min(999, current_rank))
    return {
        "days_since_match_all": float(days_since_match),
        "days_since_surface_match": float(days_since_surface_match),
        "matches_l90d_all": float(len(recent_90)),
        "matches_l365d_all": float(len(recent_365)),
        "lower_matches_l90d": float(lower_90),
        "lower_matches_l365d": float(lower_365),
        "lower_share_l365d": (
            lower_365 / len(recent_365) if recent_365 else 0.0
        ),
        "inactive_30d": float(days_since_match > 30),
        "inactive_60d": float(days_since_match > 60),
        "inactive_90d": float(days_since_match > 90),
        "rank_90d_known": float(rank_90_known),
        "rank_365d_known": float(rank_365_known),
        "rank_log_change_90d": (
            math.log1p(safe_current_rank) - math.log1p(max(1, rank_90))
            if rank_90_known else 0.0
        ),
        "rank_log_change_365d": (
            math.log1p(safe_current_rank) - math.log1p(max(1, rank_365))
            if rank_365_known else 0.0
        ),
    }


def blend_rate(
    windows: dict[str, dict[str, float]],
    numerator: str,
    denominator: str,
    prior: float,
    prior_weight: float,
) -> float:
    weights = {"l12m": 1.0, "l24m": 0.55, "career4y": 0.25}
    total = prior * prior_weight
    weight_total = prior_weight
    for name, weight in weights.items():
        stats = windows[name]
        sample = stats.get(denominator, 0.0)
        if sample <= 0:
            continue
        total += safe_rate(stats, numerator, denominator, prior) * sample * weight
        weight_total += sample * weight
    return total / weight_total if weight_total > 0 else prior


def shrink_factor(raw: float, matches: float, prior_matches: float = 100.0) -> float:
    weight = matches / (matches + prior_matches) if matches > 0 else 0.0
    return 1.0 + (raw - 1.0) * weight


def main_levels(tour: str) -> set[str]:
    return ATP_LEVELS if tour == "ATP" else WTA_LEVELS


def load_level_factors(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    global_factor = float(payload.get("global", {}).get("ace_count_factor", 1.0))
    output = {"global": global_factor}
    for surface_name, row in payload.get("surfaces", {}).items():
        output[str(surface_name)] = float(row.get("ace_count_factor", global_factor))
    return output


def load_matches(
    start_year: int,
    end_year: int,
    *,
    include_qual_chall: bool = False,
    level_factors: dict[str, float] | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for tour in ("ATP", "WTA"):
        for year in range(start_year, end_year + 1):
            sources = [("main", SACKMANN_DIR / f"{tour.lower()}_matches_{year}.csv")]
            if include_qual_chall and tour == "ATP":
                sources.append((
                    "qual_chall",
                    SACKMANN_DIR / f"{tour.lower()}_matches_qual_chall_{year}.csv",
                ))
            for source, path in sources:
                if not path.exists():
                    continue
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    raw_rows = list(csv.DictReader(handle))
                for raw in raw_rows:
                    match_date = parse_date(raw.get("tourney_date"))
                    level = str(raw.get("tourney_level") or "").strip()
                    surface = norm_surface(raw.get("surface"))
                    if match_date is None or surface == "Unknown":
                        continue
                    if source == "main" and level not in main_levels(tour):
                        continue
                    if parse_int(raw.get("w_svpt")) <= 0 or parse_int(raw.get("l_svpt")) <= 0:
                        continue
                    identity = (
                        tour,
                        str(raw.get("tourney_id") or ""),
                        str(raw.get("tourney_date") or ""),
                        str(raw.get("match_num") or ""),
                        str(raw.get("winner_id") or ""),
                        str(raw.get("loser_id") or ""),
                    )
                    if identity in seen:
                        continue
                    seen.add(identity)
                    row = dict(raw)
                    row["_tour"] = tour
                    row["_date"] = match_date.isoformat()
                    row["_surface"] = surface
                    row["_source"] = source
                    row["_target"] = "yes" if source == "main" else "no"
                    row["_ace_factor"] = str(
                        1.0 if source == "main"
                        else (level_factors or {}).get(
                            surface, (level_factors or {}).get("global", 1.0)
                        )
                    )
                    rows.append(row)
    return sorted(rows, key=lambda row: (row["_date"], row["_tour"], str(row.get("tourney_id")), parse_int(row.get("match_num"))))


def observation(row: dict[str, str], prefix: str, opponent_prefix: str) -> Observation:
    ace_factor = parse_float(row.get("_ace_factor"), 1.0)
    return Observation(
        match_date=date.fromisoformat(row["_date"]),
        aces=parse_int(row.get(f"{prefix}_ace")) * ace_factor,
        dfs=parse_int(row.get(f"{prefix}_df")),
        svpt=parse_int(row.get(f"{prefix}_svpt")),
        svgms=parse_int(row.get(f"{prefix}_SvGms")),
        first_in=parse_int(row.get(f"{prefix}_1stIn")),
        first_won=parse_int(row.get(f"{prefix}_1stWon")),
        second_won=parse_int(row.get(f"{prefix}_2ndWon")),
        opponent_aces=parse_int(row.get(f"{opponent_prefix}_ace")) * ace_factor,
        opponent_svpt=parse_int(row.get(f"{opponent_prefix}_svpt")),
        opponent_first_in=parse_int(row.get(f"{opponent_prefix}_1stIn")),
        opponent_first_won=parse_int(row.get(f"{opponent_prefix}_1stWon")),
        opponent_second_won=parse_int(row.get(f"{opponent_prefix}_2ndWon")),
    )


def player_features(
    history: list[Observation],
    ace_history: list[Observation] | None,
    as_of: date,
    prior_ace: float,
    prior_df: float,
    prior_ret_first: float,
    prior_ret_second: float,
    tour: str,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    windows = {name: rolling_stats(history, as_of, days) for name, days in WINDOWS.items()}
    ace_windows = {
        name: rolling_stats(ace_history if ace_history is not None else history, as_of, days)
        for name, days in WINDOWS.items()
    }
    ace_weight = 400.0 if tour == "ATP" else 600.0
    df_weight = 600.0 if tour == "ATP" else 800.0
    features: dict[str, float] = {
        "ace_rate_blend": blend_rate(ace_windows, "aces", "svpt", prior_ace, ace_weight),
        "df_rate_blend": blend_rate(windows, "dfs", "svpt", prior_df, df_weight),
        "ret_first_blend": blend_rate(windows, "ret_first_won", "ret_first_points", prior_ret_first, 350.0),
        "ret_second_blend": blend_rate(windows, "ret_second_won", "ret_second_points", prior_ret_second, 350.0),
        "aces_allowed_blend": blend_rate(ace_windows, "opponent_aces", "opponent_svpt", prior_ace, 400.0),
        "svpt_per_svg_blend": blend_rate(windows, "svpt", "svgms", 6.35, 60.0),
    }
    for name, stats in windows.items():
        ace_stats = ace_windows[name]
        features[f"{name}_matches"] = ace_stats.get("matches", 0.0)
        features[f"{name}_svpt"] = ace_stats.get("svpt", 0.0)
        features[f"{name}_ace_rate"] = safe_rate(ace_stats, "aces", "svpt", prior_ace)
        features[f"{name}_df_rate"] = safe_rate(stats, "dfs", "svpt", prior_df)
        features[f"{name}_svpt_per_match"] = safe_rate(stats, "svpt", "matches", 65.0)
        features[f"{name}_first_serve_pct"] = safe_rate(stats, "first_in", "svpt", 0.61)
        features[f"{name}_first_win_pct"] = safe_rate(stats, "first_won", "first_in", 0.70)
        features[f"{name}_second_win_pct"] = safe_rate(stats, "second_won", "second_attempts", 0.52)
        features[f"{name}_aces_allowed_rate"] = safe_rate(
            ace_stats, "opponent_aces", "opponent_svpt", prior_ace
        )
    return features, windows


def side_row(
    row: dict[str, str],
    *,
    prefix: str,
    opponent_prefix: str,
    player_id_field: str,
    opponent_id_field: str,
    player_name_field: str,
    opponent_name_field: str,
    player_rank_field: str,
    opponent_rank_field: str,
    player_age_field: str,
    opponent_age_field: str,
    player_height_field: str,
    opponent_height_field: str,
    player_hand_field: str,
    opponent_hand_field: str,
    player_history: dict[tuple[str, str, str], list[Observation]],
    ace_history: dict[tuple[str, str, str], list[Observation]],
    activity_history: dict[tuple[str, str], list[ActivityObservation]],
    surface_stats: dict[tuple[str, str], dict[str, float]],
    venue_stats: dict[tuple[str, str, str], dict[str, float]],
    workload_stats: dict[tuple[str, str, str, int], dict[str, float]],
    include_a3_features: bool,
) -> dict[str, object]:
    tour = row["_tour"]
    surface = row["_surface"]
    as_of = date.fromisoformat(row["_date"])
    level = str(row.get("tourney_level") or "")
    best_of = parse_int(row.get("best_of"), 3)
    venue_key = (tour, norm_tournament(row.get("tourney_name")), surface)
    surface_key = (tour, surface)
    workload_key = (tour, surface, level, best_of)
    global_stats = surface_stats.get(surface_key, blank_stats())
    prior_ace = safe_rate(global_stats, "aces", "svpt", 0.065 if tour == "ATP" else 0.027)
    prior_df = safe_rate(global_stats, "dfs", "svpt", 0.035 if tour == "ATP" else 0.048)
    prior_ret_first = 0.315 if tour == "ATP" else 0.365
    prior_ret_second = 0.520 if tour == "ATP" else 0.550
    player_id = str(row.get(player_id_field) or "")
    opponent_id = str(row.get(opponent_id_field) or "")
    player, _ = player_features(
        player_history.get((tour, player_id, surface), []),
        ace_history.get((tour, player_id, surface), []),
        as_of, prior_ace, prior_df, prior_ret_first, prior_ret_second, tour,
    )
    opponent, _ = player_features(
        player_history.get((tour, opponent_id, surface), []),
        ace_history.get((tour, opponent_id, surface), []),
        as_of, prior_ace, prior_df, prior_ret_first, prior_ret_second, tour,
    )
    venue = venue_stats.get(venue_key, blank_stats())
    venue_matches = venue.get("match_count", 0.0)
    raw_ace_factor = safe_rate(venue, "aces", "svpt", prior_ace) / max(0.002, prior_ace)
    raw_df_factor = safe_rate(venue, "dfs", "svpt", prior_df) / max(0.002, prior_df)
    ace_venue_factor = shrink_factor(raw_ace_factor, venue_matches)
    df_venue_factor = shrink_factor(raw_df_factor, venue_matches)
    workload = workload_stats.get(workload_key, blank_stats())
    fallback_games = 38.5 if tour == "ATP" and best_of == 5 else 21.5
    expected_match_games = safe_rate(workload, "match_games", "match_count", fallback_games)
    expected_service_games = max(4.0, expected_match_games * 0.5)
    expected_service_points = expected_service_games * max(4.8, min(8.6, player["svpt_per_svg_blend"]))
    return_factor = max(0.76, min(1.22, (prior_ret_first / max(0.18, opponent["ret_first_blend"])) ** 0.6))
    incumbent_aces = max(0.002, min(0.28, player["ace_rate_blend"] * ace_venue_factor * return_factor)) * expected_service_points
    incumbent_dfs = max(0.002, min(0.16, player["df_rate_blend"] * df_venue_factor)) * expected_service_points
    player_rank = parse_int(row.get(player_rank_field), 999)
    opponent_rank = parse_int(row.get(opponent_rank_field), 999)
    player_activity = activity_features(
        activity_history.get((tour, player_id), []),
        as_of,
        surface,
        player_rank,
    )
    opponent_activity = activity_features(
        activity_history.get((tour, opponent_id), []),
        as_of,
        surface,
        opponent_rank,
    )

    features: dict[str, object] = {
        "date": row["_date"],
        "year": as_of.year,
        "tour": tour,
        "tournament": str(row.get("tourney_name") or ""),
        "surface": surface,
        "level": level,
        "round": str(row.get("round") or ""),
        "best_of": best_of,
        "draw_size": parse_int(row.get("draw_size")),
        "player_id": player_id,
        "player": str(row.get(player_name_field) or ""),
        "opponent_id": opponent_id,
        "opponent": str(row.get(opponent_name_field) or ""),
        "player_hand": str(row.get(player_hand_field) or "U"),
        "opponent_hand": str(row.get(opponent_hand_field) or "U"),
        "player_rank": player_rank,
        "opponent_rank": opponent_rank,
        "log_player_rank": math.log1p(max(1, player_rank)),
        "log_opponent_rank": math.log1p(max(1, opponent_rank)),
        "rank_log_gap": math.log1p(max(1, player_rank)) - math.log1p(max(1, opponent_rank)),
        "player_age": parse_float(row.get(player_age_field), 26.0),
        "opponent_age": parse_float(row.get(opponent_age_field), 26.0),
        "player_height": parse_float(row.get(player_height_field), 0.0),
        "opponent_height": parse_float(row.get(opponent_height_field), 0.0),
        "surface_prior_ace_rate": prior_ace,
        "surface_prior_df_rate": prior_df,
        "venue_history_matches": venue_matches,
        "venue_ace_factor": ace_venue_factor,
        "venue_df_factor": df_venue_factor,
        "expected_match_games": expected_match_games,
        "expected_service_points": expected_service_points,
        "opponent_return_factor": return_factor,
        "incumbent_aces": incumbent_aces,
        "incumbent_dfs": incumbent_dfs,
        "actual_aces": parse_int(row.get(f"{prefix}_ace")),
        "actual_dfs": parse_int(row.get(f"{prefix}_df")),
        "actual_service_points": parse_int(row.get(f"{prefix}_svpt")),
    }
    features.update({f"player_{key}": value for key, value in player.items()})
    features.update({f"opponent_{key}": value for key, value in opponent.items()})
    if include_a3_features:
        features.update({
            f"player_activity_{key}": value
            for key, value in player_activity.items()
        })
        features.update({
            f"opponent_activity_{key}": value
            for key, value in opponent_activity.items()
        })
    return features


def new_feature_state() -> dict[str, object]:
    """Create the causal rolling state shared by backtests and live scoring."""
    return {
        "player_history": defaultdict(list),
        "ace_history": defaultdict(list),
        "activity_history": defaultdict(list),
        "surface_stats": defaultdict(blank_stats),
        "venue_stats": defaultdict(blank_stats),
        "workload_stats": defaultdict(blank_stats),
    }


def update_feature_state(state: dict[str, object], row: dict[str, str]) -> None:
    """Append one completed match after its date has been featurised."""
    tour = row["_tour"]
    surface = row["_surface"]
    level = str(row.get("tourney_level") or "")
    best_of = parse_int(row.get("best_of"), 3)
    winner_obs = observation(row, "w", "l")
    loser_obs = observation(row, "l", "w")
    winner_key = (tour, str(row.get("winner_id") or ""), surface)
    loser_key = (tour, str(row.get("loser_id") or ""), surface)
    ace_history = state["ace_history"]
    activity_history = state["activity_history"]
    player_history = state["player_history"]
    surface_stats = state["surface_stats"]
    venue_stats = state["venue_stats"]
    workload_stats = state["workload_stats"]

    ace_history[winner_key].append(winner_obs)
    ace_history[loser_key].append(loser_obs)
    source = str(row.get("_source") or "main")
    activity_history[(tour, winner_key[1])].append(ActivityObservation(
        match_date=winner_obs.match_date,
        surface=surface,
        source=source,
        rank=parse_int(row.get("winner_rank"), 999),
    ))
    activity_history[(tour, loser_key[1])].append(ActivityObservation(
        match_date=loser_obs.match_date,
        surface=surface,
        source=source,
        rank=parse_int(row.get("loser_rank"), 999),
    ))
    if row.get("_target", "yes") != "yes":
        return

    player_history[winner_key].append(winner_obs)
    player_history[loser_key].append(loser_obs)
    surface_key = (tour, surface)
    venue_key = (tour, norm_tournament(row.get("tourney_name")), surface)
    for obs in (winner_obs, loser_obs):
        add_side_aggregate(surface_stats[surface_key], obs)
        add_side_aggregate(venue_stats[venue_key], obs)
    venue_stats[venue_key]["match_count"] += 1
    games = score_games(row.get("score"))
    if games > 0:
        workload_key = (tour, surface, level, best_of)
        workload_stats[workload_key]["match_games"] += games
        workload_stats[workload_key]["match_count"] += 1


def build_feature_state(
    rows: list[dict[str, str]],
    *,
    as_of: date,
) -> dict[str, object]:
    """Build state from matches strictly before ``as_of``."""
    state = new_feature_state()
    cutoff = as_of.isoformat()
    for row in rows:
        if str(row.get("_date") or "") >= cutoff:
            continue
        update_feature_state(state, row)
    return state


def build_dataset(
    rows: list[dict[str, str]],
    output_start_year: int,
    *,
    include_a3_features: bool = False,
) -> list[dict[str, object]]:
    state = new_feature_state()
    output: list[dict[str, object]] = []
    rows_by_date: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_date[row["_date"]].append(row)

    for date_key in sorted(rows_by_date):
        day_rows = rows_by_date[date_key]
        for row in day_rows:
            if (
                int(date_key[:4]) < output_start_year
                or row.get("_target", "yes") != "yes"
            ):
                continue
            common = {
                **state,
                "include_a3_features": include_a3_features,
            }
            output.append(side_row(
                row, prefix="w", opponent_prefix="l",
                player_id_field="winner_id", opponent_id_field="loser_id",
                player_name_field="winner_name", opponent_name_field="loser_name",
                player_rank_field="winner_rank", opponent_rank_field="loser_rank",
                player_age_field="winner_age", opponent_age_field="loser_age",
                player_height_field="winner_ht", opponent_height_field="loser_ht",
                player_hand_field="winner_hand", opponent_hand_field="loser_hand", **common,
            ))
            output.append(side_row(
                row, prefix="l", opponent_prefix="w",
                player_id_field="loser_id", opponent_id_field="winner_id",
                player_name_field="loser_name", opponent_name_field="winner_name",
                player_rank_field="loser_rank", opponent_rank_field="winner_rank",
                player_age_field="loser_age", opponent_age_field="winner_age",
                player_height_field="loser_ht", opponent_height_field="winner_ht",
                player_hand_field="loser_hand", opponent_hand_field="winner_hand", **common,
            ))

        # Update every state only after all same-date features have been frozen.
        for row in day_rows:
            update_feature_state(state, row)
    return output


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise SystemExit("No v3 feature rows generated")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--output-start-year", type=int, default=2023)
    parser.add_argument("--include-qual-chall", action="store_true")
    parser.add_argument("--include-a3-features", action="store_true")
    parser.add_argument("--level-factors", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    level_factors = load_level_factors(args.level_factors)
    if args.include_qual_chall and not level_factors:
        raise SystemExit("--include-qual-chall requires --level-factors")
    matches = load_matches(
        args.start_year,
        args.end_year,
        include_qual_chall=args.include_qual_chall,
        level_factors=level_factors,
    )
    rows = build_dataset(
        matches,
        args.output_start_year,
        include_a3_features=args.include_a3_features,
    )
    write_rows(args.out, rows)
    print(f"Wrote {args.out} ({len(rows)} side rows from {len(matches)} matches)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
