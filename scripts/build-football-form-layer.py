#!/usr/bin/env python3
"""Build canonical football team-match and rolling-form tables.

This is an input layer only. It does not change bet selection or model formulas.

Outputs:
- data/football-form/team-match-base.csv
- data/football-form/team-rolling-form.csv
- data/football-form/team-match-base-YYYY-MM-DD.csv
- data/football-form/team-rolling-form-YYYY-MM-DD.csv
- data/football-form/team-form-manifest.json
- data/football-form/team-form-report.md
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from settlement_utils import normalize_team_name  # noqa: E402


DEFAULT_MATCH_BASE = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_CURRENT_MATCH_BASE = ROOT / "data" / "team-shots" / "historical" / "all-historical-matches.csv"
DEFAULT_XG_SOURCE = ROOT / "data" / "team-shots" / "understat" / "all-understat-matches.csv"
LEGACY_XG_SOURCE = ROOT / "data" / "team-shots" / "fbref" / "all-fbref-matches.csv"
DEFAULT_SUPPLEMENTAL_MATCH_BASES = (DEFAULT_CURRENT_MATCH_BASE, DEFAULT_XG_SOURCE)
DEFAULT_OUTPUT_DIR = ROOT / "data" / "football-form"

WINDOWS = (5, 10)
EMA_WINDOW = 20
EMA_DECAY = 0.93


TEAM_MATCH_FIELDS = [
    "date",
    "league",
    "season",
    "team",
    "team_key",
    "opponent",
    "opponent_key",
    "venue",
    "home_team",
    "away_team",
    "goals_for",
    "goals_against",
    "xg_for",
    "xg_against",
    "shots_for",
    "shots_against",
    "sot_for",
    "sot_against",
    "corners_for",
    "corners_against",
    "b365h",
    "b365d",
    "b365a",
    "market_team_win_prob",
    "market_opp_win_prob",
    "match_source",
    "xg_source",
]


ROLLING_BASE_FIELDS = [
    "date",
    "league",
    "season",
    "team",
    "team_key",
    "opponent",
    "opponent_key",
    "venue",
    "home_team",
    "away_team",
    "current_goals_for",
    "current_goals_against",
    "current_xg_for",
    "current_xg_against",
    "current_shots_for",
    "current_shots_against",
    "current_sot_for",
    "current_sot_against",
    "current_corners_for",
    "current_corners_against",
    "market_team_win_prob",
    "market_opp_win_prob",
    "league_prior_rows",
    "league_prior_shots_for_avg",
    "league_prior_shots_against_avg",
    "league_prior_corners_for_avg",
    "league_prior_corners_against_avg",
    "league_prior_xg_for_avg",
    "league_prior_xg_against_avg",
    "league_t12_rows",
    "league_t12_shots_for_avg",
    "league_t12_shots_against_avg",
    "league_t12_corners_for_avg",
    "league_t12_corners_against_avg",
    "league_t12_xg_for_avg",
    "league_t12_xg_against_avg",
]


ROLLING_METRICS = [
    "matches",
    "home_matches",
    "away_matches",
    "goals_for_avg",
    "goals_against_avg",
    "xg_for_avg",
    "xg_against_avg",
    "xg_for_home_avg",
    "xg_for_away_avg",
    "shots_for_avg",
    "shots_against_avg",
    "shots_for_home_avg",
    "shots_for_away_avg",
    "shots_against_home_avg",
    "shots_against_away_avg",
    "sot_for_avg",
    "sot_against_avg",
    "sot_for_home_avg",
    "sot_for_away_avg",
    "sot_against_home_avg",
    "sot_against_away_avg",
    "corners_for_avg",
    "corners_against_avg",
    "corners_for_home_avg",
    "corners_for_away_avg",
    "corners_against_home_avg",
    "corners_against_away_avg",
    "xg_per_shot_for",
    "xg_per_shot_against",
    "opponent_market_strength_avg",
]


RELATIVE_METRICS = [
    "shots_for_avg_rel",
    "shots_against_avg_rel",
    "corners_for_avg_rel",
    "corners_against_avg_rel",
    "xg_for_avg_rel",
    "xg_against_avg_rel",
    "shots_for_avg_t12_rel",
    "shots_against_avg_t12_rel",
    "corners_for_avg_t12_rel",
    "corners_against_avg_t12_rel",
    "xg_for_avg_t12_rel",
    "xg_against_avg_t12_rel",
]


def rolling_fields() -> list[str]:
    fields = list(ROLLING_BASE_FIELDS)
    for window in WINDOWS:
        for metric in ROLLING_METRICS:
            fields.append(f"r{window}_{metric}")
        for metric in RELATIVE_METRICS:
            fields.append(f"r{window}_{metric}")
    for metric in ROLLING_METRICS:
        fields.append(f"ema{EMA_WINDOW}_{metric}")
    return fields


def parse_float(value: Any, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    return int(round(parse_float(value, float(default))))


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for candidate in (text, text[:10]):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    return None


def clean_name(value: Any) -> str:
    return str(value or "").strip()


def team_key(value: str) -> str:
    return normalize_team_name(value or "")


def match_key(match_date: date, league: str, home_team: str, away_team: str) -> tuple[str, str, str, str]:
    return (
        match_date.isoformat(),
        str(league or "").strip().lower(),
        team_key(home_team),
        team_key(away_team),
    )


def no_vig_probs(home_odds: float, draw_odds: float, away_odds: float) -> tuple[float, float, float] | None:
    if home_odds <= 1.0 or draw_odds <= 1.0 or away_odds <= 1.0:
        return None
    inv_home = 1.0 / home_odds
    inv_draw = 1.0 / draw_odds
    inv_away = 1.0 / away_odds
    overround = inv_home + inv_draw + inv_away
    if overround <= 0:
        return None
    return inv_home / overround, inv_draw / overround, inv_away / overround


@dataclass
class Match:
    match_date: date
    league: str
    season: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_shots: int
    away_shots: int
    home_sot: int
    away_sot: int
    home_corners: int
    away_corners: int
    b365h: float
    b365d: float
    b365a: float
    home_xg: float = 0.0
    away_xg: float = 0.0
    xg_source: str = ""


def load_match_base(path: Path) -> dict[tuple[str, str, str, str], Match]:
    matches: dict[tuple[str, str, str, str], Match] = {}
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            match_date = parse_date(row.get("Date") or row.get("date"))
            if not match_date:
                continue
            home = clean_name(row.get("HomeTeam") or row.get("home_team"))
            away = clean_name(row.get("AwayTeam") or row.get("away_team"))
            if not home or not away:
                continue
            league = clean_name(row.get("league"))
            match = Match(
                match_date=match_date,
                league=league,
                season=clean_name(row.get("season")),
                home_team=home,
                away_team=away,
                home_goals=parse_int(row.get("FTHG") or row.get("home_goals")),
                away_goals=parse_int(row.get("FTAG") or row.get("away_goals")),
                home_shots=parse_int(row.get("HS") or row.get("home_shots")),
                away_shots=parse_int(row.get("AS") or row.get("away_shots")),
                home_sot=parse_int(row.get("HST") or row.get("home_sot")),
                away_sot=parse_int(row.get("AST") or row.get("away_sot")),
                home_corners=parse_int(row.get("HC") or row.get("home_corners")),
                away_corners=parse_int(row.get("AC") or row.get("away_corners")),
                b365h=parse_float(row.get("B365H")),
                b365d=parse_float(row.get("B365D")),
                b365a=parse_float(row.get("B365A")),
            )
            matches[match_key(match_date, league, home, away)] = match
    return matches


def load_match_bases(primary: Path, supplemental: Iterable[Path]) -> dict[tuple[str, str, str, str], Match]:
    """Load the durable archive, then upsert fresher current-season sources."""
    matches = load_match_base(primary)
    for path in supplemental:
        if not path.exists() or path.resolve() == primary.resolve():
            continue
        matches.update(load_match_base(path))
    return matches


def overlay_xg(matches: dict[tuple[str, str, str, str], Match], path: Path) -> dict[str, int]:
    stats = {"rows": 0, "matched": 0, "unmatched": 0, "with_xg": 0}
    if not path.exists():
        return stats
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            stats["rows"] += 1
            match_date = parse_date(row.get("date") or row.get("Date"))
            if not match_date:
                stats["unmatched"] += 1
                continue
            home = clean_name(row.get("home_team") or row.get("HomeTeam"))
            away = clean_name(row.get("away_team") or row.get("AwayTeam"))
            league = clean_name(row.get("league"))
            key = match_key(match_date, league, home, away)
            match = matches.get(key)
            if not match:
                stats["unmatched"] += 1
                continue
            stats["matched"] += 1
            home_xg = parse_float(row.get("home_xg"))
            away_xg = parse_float(row.get("away_xg"))
            if home_xg > 0 or away_xg > 0:
                stats["with_xg"] += 1
                match.home_xg = home_xg
                match.away_xg = away_xg
                match.xg_source = "understat"
    return stats


def team_rows_from_match(match: Match) -> list[dict[str, Any]]:
    probs = no_vig_probs(match.b365h, match.b365d, match.b365a)
    if probs:
        p_home, _p_draw, p_away = probs
    else:
        p_home, p_away = 0.0, 0.0
    base = {
        "date": match.match_date.isoformat(),
        "league": match.league,
        "season": match.season,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "b365h": value_or_blank(match.b365h),
        "b365d": value_or_blank(match.b365d),
        "b365a": value_or_blank(match.b365a),
        "match_source": "football-data",
        "xg_source": match.xg_source,
    }
    return [
        {
            **base,
            "team": match.home_team,
            "team_key": team_key(match.home_team),
            "opponent": match.away_team,
            "opponent_key": team_key(match.away_team),
            "venue": "home",
            "goals_for": match.home_goals,
            "goals_against": match.away_goals,
            "xg_for": value_or_blank(match.home_xg),
            "xg_against": value_or_blank(match.away_xg),
            "shots_for": match.home_shots,
            "shots_against": match.away_shots,
            "sot_for": match.home_sot,
            "sot_against": match.away_sot,
            "corners_for": match.home_corners,
            "corners_against": match.away_corners,
            "market_team_win_prob": value_or_blank(p_home),
            "market_opp_win_prob": value_or_blank(p_away),
        },
        {
            **base,
            "team": match.away_team,
            "team_key": team_key(match.away_team),
            "opponent": match.home_team,
            "opponent_key": team_key(match.home_team),
            "venue": "away",
            "goals_for": match.away_goals,
            "goals_against": match.home_goals,
            "xg_for": value_or_blank(match.away_xg),
            "xg_against": value_or_blank(match.home_xg),
            "shots_for": match.away_shots,
            "shots_against": match.home_shots,
            "sot_for": match.away_sot,
            "sot_against": match.home_sot,
            "corners_for": match.away_corners,
            "corners_against": match.home_corners,
            "market_team_win_prob": value_or_blank(p_away),
            "market_opp_win_prob": value_or_blank(p_home),
        },
    ]


def value_or_blank(value: float, digits: int = 4) -> str:
    if value is None or value <= 0:
        return ""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def numeric(row: dict[str, Any], key: str) -> float | None:
    value = parse_float(row.get(key), default=float("nan"))
    if value != value:
        return None
    return value


def avg(values: Iterable[float | None]) -> str:
    present = [value for value in values if value is not None]
    if not present:
        return ""
    return f"{sum(present) / len(present):.4f}".rstrip("0").rstrip(".")


def weighted_avg(values: Iterable[tuple[float | None, float]]) -> str:
    present = [(value, weight) for value, weight in values if value is not None and weight > 0]
    weight_sum = sum(weight for _, weight in present)
    if not present or weight_sum <= 0:
        return ""
    return f"{sum(value * weight for value, weight in present) / weight_sum:.4f}".rstrip("0").rstrip(".")


def ratio(num: float | None, den: float | None) -> str:
    if num is None or den is None or den <= 0:
        return ""
    return f"{num / den:.4f}".rstrip("0").rstrip(".")


def summarize_window(history: list[dict[str, Any]], window: int) -> dict[str, Any]:
    recent = history[-window:]
    home_rows = [row for row in recent if row.get("venue") == "home"]
    away_rows = [row for row in recent if row.get("venue") == "away"]
    xg_for_sum = sum((numeric(row, "xg_for") or 0.0) for row in recent)
    xg_against_sum = sum((numeric(row, "xg_against") or 0.0) for row in recent)
    shots_for_sum = sum((numeric(row, "shots_for") or 0.0) for row in recent)
    shots_against_sum = sum((numeric(row, "shots_against") or 0.0) for row in recent)
    return {
        f"r{window}_matches": len(recent),
        f"r{window}_home_matches": len(home_rows),
        f"r{window}_away_matches": len(away_rows),
        f"r{window}_goals_for_avg": avg(numeric(row, "goals_for") for row in recent),
        f"r{window}_goals_against_avg": avg(numeric(row, "goals_against") for row in recent),
        f"r{window}_xg_for_avg": avg(numeric(row, "xg_for") for row in recent if numeric(row, "xg_for") is not None),
        f"r{window}_xg_against_avg": avg(numeric(row, "xg_against") for row in recent if numeric(row, "xg_against") is not None),
        f"r{window}_xg_for_home_avg": avg(numeric(row, "xg_for") for row in home_rows if numeric(row, "xg_for") is not None),
        f"r{window}_xg_for_away_avg": avg(numeric(row, "xg_for") for row in away_rows if numeric(row, "xg_for") is not None),
        f"r{window}_shots_for_avg": avg(numeric(row, "shots_for") for row in recent),
        f"r{window}_shots_against_avg": avg(numeric(row, "shots_against") for row in recent),
        f"r{window}_shots_for_home_avg": avg(numeric(row, "shots_for") for row in home_rows),
        f"r{window}_shots_for_away_avg": avg(numeric(row, "shots_for") for row in away_rows),
        f"r{window}_shots_against_home_avg": avg(numeric(row, "shots_against") for row in home_rows),
        f"r{window}_shots_against_away_avg": avg(numeric(row, "shots_against") for row in away_rows),
        f"r{window}_sot_for_avg": avg(numeric(row, "sot_for") for row in recent),
        f"r{window}_sot_against_avg": avg(numeric(row, "sot_against") for row in recent),
        f"r{window}_sot_for_home_avg": avg(numeric(row, "sot_for") for row in home_rows),
        f"r{window}_sot_for_away_avg": avg(numeric(row, "sot_for") for row in away_rows),
        f"r{window}_sot_against_home_avg": avg(numeric(row, "sot_against") for row in home_rows),
        f"r{window}_sot_against_away_avg": avg(numeric(row, "sot_against") for row in away_rows),
        f"r{window}_corners_for_avg": avg(numeric(row, "corners_for") for row in recent),
        f"r{window}_corners_against_avg": avg(numeric(row, "corners_against") for row in recent),
        f"r{window}_corners_for_home_avg": avg(numeric(row, "corners_for") for row in home_rows),
        f"r{window}_corners_for_away_avg": avg(numeric(row, "corners_for") for row in away_rows),
        f"r{window}_corners_against_home_avg": avg(numeric(row, "corners_against") for row in home_rows),
        f"r{window}_corners_against_away_avg": avg(numeric(row, "corners_against") for row in away_rows),
        f"r{window}_xg_per_shot_for": ratio(xg_for_sum, shots_for_sum),
        f"r{window}_xg_per_shot_against": ratio(xg_against_sum, shots_against_sum),
        f"r{window}_opponent_market_strength_avg": avg(numeric(row, "market_opp_win_prob") for row in recent),
    }


def summarize_ema_window(history: list[dict[str, Any]]) -> dict[str, Any]:
    recent = history[-EMA_WINDOW:]
    prefix = f"ema{EMA_WINDOW}"
    weighted_rows = [
        (row, EMA_DECAY ** (len(recent) - 1 - index))
        for index, row in enumerate(recent)
    ]
    home_rows = [(row, weight) for row, weight in weighted_rows if row.get("venue") == "home"]
    away_rows = [(row, weight) for row, weight in weighted_rows if row.get("venue") == "away"]

    xg_for_sum = sum((numeric(row, "xg_for") or 0.0) * weight for row, weight in weighted_rows)
    xg_against_sum = sum((numeric(row, "xg_against") or 0.0) * weight for row, weight in weighted_rows)
    shots_for_sum = sum((numeric(row, "shots_for") or 0.0) * weight for row, weight in weighted_rows)
    shots_against_sum = sum((numeric(row, "shots_against") or 0.0) * weight for row, weight in weighted_rows)

    return {
        f"{prefix}_matches": len(recent),
        f"{prefix}_home_matches": len(home_rows),
        f"{prefix}_away_matches": len(away_rows),
        f"{prefix}_goals_for_avg": weighted_avg((numeric(row, "goals_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_goals_against_avg": weighted_avg((numeric(row, "goals_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_xg_for_avg": weighted_avg((numeric(row, "xg_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_xg_against_avg": weighted_avg((numeric(row, "xg_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_xg_for_home_avg": weighted_avg((numeric(row, "xg_for"), weight) for row, weight in home_rows),
        f"{prefix}_xg_for_away_avg": weighted_avg((numeric(row, "xg_for"), weight) for row, weight in away_rows),
        f"{prefix}_shots_for_avg": weighted_avg((numeric(row, "shots_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_shots_against_avg": weighted_avg((numeric(row, "shots_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_shots_for_home_avg": weighted_avg((numeric(row, "shots_for"), weight) for row, weight in home_rows),
        f"{prefix}_shots_for_away_avg": weighted_avg((numeric(row, "shots_for"), weight) for row, weight in away_rows),
        f"{prefix}_shots_against_home_avg": weighted_avg((numeric(row, "shots_against"), weight) for row, weight in home_rows),
        f"{prefix}_shots_against_away_avg": weighted_avg((numeric(row, "shots_against"), weight) for row, weight in away_rows),
        f"{prefix}_sot_for_avg": weighted_avg((numeric(row, "sot_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_sot_against_avg": weighted_avg((numeric(row, "sot_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_sot_for_home_avg": weighted_avg((numeric(row, "sot_for"), weight) for row, weight in home_rows),
        f"{prefix}_sot_for_away_avg": weighted_avg((numeric(row, "sot_for"), weight) for row, weight in away_rows),
        f"{prefix}_sot_against_home_avg": weighted_avg((numeric(row, "sot_against"), weight) for row, weight in home_rows),
        f"{prefix}_sot_against_away_avg": weighted_avg((numeric(row, "sot_against"), weight) for row, weight in away_rows),
        f"{prefix}_corners_for_avg": weighted_avg((numeric(row, "corners_for"), weight) for row, weight in weighted_rows),
        f"{prefix}_corners_against_avg": weighted_avg((numeric(row, "corners_against"), weight) for row, weight in weighted_rows),
        f"{prefix}_corners_for_home_avg": weighted_avg((numeric(row, "corners_for"), weight) for row, weight in home_rows),
        f"{prefix}_corners_for_away_avg": weighted_avg((numeric(row, "corners_for"), weight) for row, weight in away_rows),
        f"{prefix}_corners_against_home_avg": weighted_avg((numeric(row, "corners_against"), weight) for row, weight in home_rows),
        f"{prefix}_corners_against_away_avg": weighted_avg((numeric(row, "corners_against"), weight) for row, weight in away_rows),
        f"{prefix}_xg_per_shot_for": ratio(xg_for_sum, shots_for_sum),
        f"{prefix}_xg_per_shot_against": ratio(xg_against_sum, shots_against_sum),
        f"{prefix}_opponent_market_strength_avg": weighted_avg(
            (numeric(row, "market_opp_win_prob"), weight) for row, weight in weighted_rows
        ),
    }


LEAGUE_BASELINE_SOURCES = {
    "shots_for": "league_prior_shots_for_avg",
    "shots_against": "league_prior_shots_against_avg",
    "corners_for": "league_prior_corners_for_avg",
    "corners_against": "league_prior_corners_against_avg",
    "xg_for": "league_prior_xg_for_avg",
    "xg_against": "league_prior_xg_against_avg",
}


def adjust_league_stats(stats: dict[str, float], row: dict[str, Any], delta: float) -> None:
    stats["rows"] = stats.get("rows", 0.0) + delta
    for source_field in LEAGUE_BASELINE_SOURCES:
        value = numeric(row, source_field)
        if value is None:
            continue
        stats[f"{source_field}_sum"] = stats.get(f"{source_field}_sum", 0.0) + (value * delta)
        stats[f"{source_field}_count"] = stats.get(f"{source_field}_count", 0.0) + delta


def update_league_stats(stats: dict[str, float], row: dict[str, Any]) -> None:
    adjust_league_stats(stats, row, 1.0)


def remove_league_stats(stats: dict[str, float], row: dict[str, Any]) -> None:
    adjust_league_stats(stats, row, -1.0)


def summarize_league_baseline(stats: dict[str, float]) -> dict[str, Any]:
    """Causal league baseline using only rows from dates before this matchday."""
    out: dict[str, Any] = {"league_prior_rows": int(stats.get("rows", 0.0))}
    for source_field, output_field in LEAGUE_BASELINE_SOURCES.items():
        count = stats.get(f"{source_field}_count", 0.0)
        total = stats.get(f"{source_field}_sum", 0.0)
        out[output_field] = f"{total / count:.4f}".rstrip("0").rstrip(".") if count else ""
    return {
        "league_prior_rows": out["league_prior_rows"],
        "league_prior_shots_for_avg": out["league_prior_shots_for_avg"],
        "league_prior_shots_against_avg": out["league_prior_shots_against_avg"],
        "league_prior_corners_for_avg": out["league_prior_corners_for_avg"],
        "league_prior_corners_against_avg": out["league_prior_corners_against_avg"],
        "league_prior_xg_for_avg": out["league_prior_xg_for_avg"],
        "league_prior_xg_against_avg": out["league_prior_xg_against_avg"],
    }


def summarize_league_t12_baseline(stats: dict[str, float]) -> dict[str, Any]:
    """Causal trailing-12-month league baseline using only prior matchdays."""
    out: dict[str, Any] = {"league_t12_rows": int(stats.get("rows", 0.0))}
    for source_field in LEAGUE_BASELINE_SOURCES:
        count = stats.get(f"{source_field}_count", 0.0)
        total = stats.get(f"{source_field}_sum", 0.0)
        out[f"league_t12_{source_field}_avg"] = f"{total / count:.4f}".rstrip("0").rstrip(".") if count else ""
    return out


def relative_window_fields(row: dict[str, Any], window: int) -> dict[str, Any]:
    pairs = {
        "shots_for_avg_rel": (f"r{window}_shots_for_avg", "league_prior_shots_for_avg"),
        "shots_against_avg_rel": (f"r{window}_shots_against_avg", "league_prior_shots_against_avg"),
        "corners_for_avg_rel": (f"r{window}_corners_for_avg", "league_prior_corners_for_avg"),
        "corners_against_avg_rel": (f"r{window}_corners_against_avg", "league_prior_corners_against_avg"),
        "xg_for_avg_rel": (f"r{window}_xg_for_avg", "league_prior_xg_for_avg"),
        "xg_against_avg_rel": (f"r{window}_xg_against_avg", "league_prior_xg_against_avg"),
        "shots_for_avg_t12_rel": (f"r{window}_shots_for_avg", "league_t12_shots_for_avg"),
        "shots_against_avg_t12_rel": (f"r{window}_shots_against_avg", "league_t12_shots_against_avg"),
        "corners_for_avg_t12_rel": (f"r{window}_corners_for_avg", "league_t12_corners_for_avg"),
        "corners_against_avg_t12_rel": (f"r{window}_corners_against_avg", "league_t12_corners_against_avg"),
        "xg_for_avg_t12_rel": (f"r{window}_xg_for_avg", "league_t12_xg_for_avg"),
        "xg_against_avg_t12_rel": (f"r{window}_xg_against_avg", "league_t12_xg_against_avg"),
    }
    return {
        f"r{window}_{name}": ratio(numeric(row, value_field), numeric(row, baseline_field))
        for name, (value_field, baseline_field) in pairs.items()
    }


def build_rolling_rows(team_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    histories: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=max(max(WINDOWS), EMA_WINDOW)))
    league_stats: dict[str, dict[str, float]] = defaultdict(dict)
    league_t12_rows: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    league_t12_stats: dict[str, dict[str, float]] = defaultdict(dict)
    pending_league_rows: list[dict[str, Any]] = []
    current_date: str | None = None
    rolling_rows: list[dict[str, Any]] = []
    sorted_rows = sorted(
        team_rows,
        key=lambda row: (
            row["date"],
            row.get("league", ""),
            row.get("home_team", ""),
            row.get("away_team", ""),
            row.get("venue", ""),
        ),
    )
    for row in sorted_rows:
        if current_date is None:
            current_date = row["date"]
        elif row["date"] != current_date:
            for pending_row in pending_league_rows:
                update_league_stats(league_stats[pending_row["league"]], pending_row)
                league_t12_rows[pending_row["league"]].append(pending_row)
                update_league_stats(league_t12_stats[pending_row["league"]], pending_row)
            pending_league_rows = []
            current_date = row["date"]

        row_date = parse_date(row["date"])
        if row_date is not None:
            cutoff = row_date - timedelta(days=365)
            league_window = league_t12_rows[row["league"]]
            while league_window and (parsed := parse_date(league_window[0]["date"])) is not None and parsed < cutoff:
                expired = league_window.popleft()
                remove_league_stats(league_t12_stats[row["league"]], expired)

        history = list(histories[row["team_key"]])
        out = {
            "date": row["date"],
            "league": row["league"],
            "season": row["season"],
            "team": row["team"],
            "team_key": row["team_key"],
            "opponent": row["opponent"],
            "opponent_key": row["opponent_key"],
            "venue": row["venue"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "current_goals_for": row["goals_for"],
            "current_goals_against": row["goals_against"],
            "current_xg_for": row["xg_for"],
            "current_xg_against": row["xg_against"],
            "current_shots_for": row["shots_for"],
            "current_shots_against": row["shots_against"],
            "current_sot_for": row["sot_for"],
            "current_sot_against": row["sot_against"],
            "current_corners_for": row["corners_for"],
            "current_corners_against": row["corners_against"],
            "market_team_win_prob": row["market_team_win_prob"],
            "market_opp_win_prob": row["market_opp_win_prob"],
        }
        out.update(summarize_league_baseline(league_stats[row["league"]]))
        out.update(summarize_league_t12_baseline(league_t12_stats[row["league"]]))
        for window in WINDOWS:
            out.update(summarize_window(history, window))
            out.update(relative_window_fields(out, window))
        out.update(summarize_ema_window(history))
        rolling_rows.append(out)
        histories[row["team_key"]].append(row)
        pending_league_rows.append(row)
    return rolling_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def default_version_label() -> str:
    return datetime.now(UTC).date().isoformat()


def write_manifest(
    *,
    output_dir: Path,
    version_label: str,
    match_rows: list[dict[str, Any]],
    rolling_rows: list[dict[str, Any]],
    xg_overlay_stats: dict[str, int],
) -> None:
    dates = [parse_date(row["date"]) for row in match_rows]
    dates = [item for item in dates if item is not None]
    manifest = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "version": version_label,
        "outputs": {
            "team_match_base": rel(output_dir / "team-match-base.csv"),
            "team_match_base_versioned": rel(output_dir / f"team-match-base-{version_label}.csv"),
            "team_rolling_form": rel(output_dir / "team-rolling-form.csv"),
            "team_rolling_form_versioned": rel(output_dir / f"team-rolling-form-{version_label}.csv"),
            "report": rel(output_dir / "team-form-report.md"),
            "validation_json": rel(output_dir / "team-form-validation.json"),
            "validation_report": rel(output_dir / "team-form-validation.md"),
        },
        "row_counts": {
            "team_match_base": len(match_rows),
            "team_rolling_form": len(rolling_rows),
        },
        "date_range": {
            "min": min(dates).isoformat() if dates else None,
            "max": max(dates).isoformat() if dates else None,
        },
        "fields": {
            "team_match_base": TEAM_MATCH_FIELDS,
            "team_rolling_form": rolling_fields(),
        },
        "xg_overlay": xg_overlay_stats,
        "notes": [
            "Versioned CSVs are date-tagged generated artifacts.",
            "Models should record the version value when training or producing research reports.",
            "Validation must pass before a canonical table is trusted for model comparison.",
        ],
    }
    (output_dir / "team-form-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_report(
    *,
    match_count: int,
    team_row_count: int,
    rolling_row_count: int,
    xg_overlay_stats: dict[str, int],
    team_rows: list[dict[str, Any]],
    output_dir: Path,
) -> str:
    dates = [parse_date(row["date"]) for row in team_rows]
    dates = [d for d in dates if d is not None]
    leagues = sorted({row["league"] for row in team_rows if row.get("league")})
    rows_with_xg = sum(1 for row in team_rows if parse_float(row.get("xg_for")) > 0)
    rows_with_odds = sum(1 for row in team_rows if parse_float(row.get("market_team_win_prob")) > 0)
    league_counts: dict[str, int] = defaultdict(int)
    league_xg_counts: dict[str, int] = defaultdict(int)
    for row in team_rows:
        league = row.get("league") or "unknown"
        league_counts[league] += 1
        if parse_float(row.get("xg_for")) > 0:
            league_xg_counts[league] += 1

    lines = [
        "# Football Team Form Layer Report",
        "",
        f"Generated: {datetime.now(UTC).replace(microsecond=0).isoformat()}",
        "",
        "## Outputs",
        "",
        f"- `{rel(output_dir / 'team-match-base.csv')}`",
        f"- `{rel(output_dir / 'team-rolling-form.csv')}`",
        "",
        "## Summary",
        "",
        f"- Match rows: {match_count}",
        f"- Team-match rows: {team_row_count}",
        f"- Rolling-form rows: {rolling_row_count}",
        f"- Date range: {min(dates).isoformat() if dates else '-'} to {max(dates).isoformat() if dates else '-'}",
        f"- Leagues: {', '.join(leagues)}",
        f"- Team rows with xG: {rows_with_xg} ({rows_with_xg / max(team_row_count, 1) * 100:.1f}%)",
        f"- Team rows with market 1X2 strength: {rows_with_odds} ({rows_with_odds / max(team_row_count, 1) * 100:.1f}%)",
        "",
        "## xG Overlay",
        "",
        "```json",
        json.dumps(xg_overlay_stats, indent=2, sort_keys=True),
        "```",
        "",
        "## League Coverage",
        "",
        "| League | Team rows | Rows with xG | xG coverage |",
        "| --- | ---: | ---: | ---: |",
    ]
    for league in sorted(league_counts):
        rows = league_counts[league]
        xg_rows = league_xg_counts.get(league, 0)
        lines.append(f"| {league} | {rows} | {xg_rows} | {xg_rows / max(rows, 1) * 100:.1f}% |")
    lines.extend([
        "",
        "## Notes",
        "",
        "- Rolling features are causal: each row uses only prior matches for that team.",
        f"- EMA{EMA_WINDOW} fields are causal with decay {EMA_DECAY}; newest prior match receives weight 1.0.",
        "- League-relative fields include all-prior and trailing-12-month causal baselines; both exclude the current matchday.",
        "- Current-match raw stats are included for backtests; model training must avoid using current_* as predictors for pre-match bets.",
        "- Venue-split rolling shots, SOT, and corners are included so live models do not have to rebuild those histories separately.",
        "- Opponent strength is currently a bookmaker 1X2 proxy from previous matches, not an Elo system.",
        "- Understat xG is overlaid where it matches the Football-Data fixture key; older historical rows remain shots/corners only.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build canonical football team form tables.")
    parser.add_argument("--match-base", type=Path, default=DEFAULT_MATCH_BASE)
    parser.add_argument(
        "--supplemental-match-base",
        type=Path,
        nargs="*",
        default=list(DEFAULT_SUPPLEMENTAL_MATCH_BASES),
        help="Fresher match archives to upsert over the durable historical base",
    )
    parser.add_argument("--xg-source", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--version-label", default=default_version_label())
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--fail-on-validation-error", action="store_true")
    args = parser.parse_args()

    matches = load_match_bases(args.match_base, args.supplemental_match_base)
    xg_source = args.xg_source or DEFAULT_XG_SOURCE
    if args.xg_source is None and not xg_source.exists() and LEGACY_XG_SOURCE.exists():
        print(f"WARNING: using deprecated xG artifact {LEGACY_XG_SOURCE}")
        xg_source = LEGACY_XG_SOURCE
    xg_overlay_stats = overlay_xg(matches, xg_source)
    match_rows = sorted(matches.values(), key=lambda match: (match.match_date, match.league, match.home_team, match.away_team))
    team_rows = [team_row for match in match_rows for team_row in team_rows_from_match(match)]
    rolling_rows = build_rolling_rows(team_rows)

    write_csv(args.output_dir / "team-match-base.csv", team_rows, TEAM_MATCH_FIELDS)
    write_csv(args.output_dir / "team-rolling-form.csv", rolling_rows, rolling_fields())
    write_csv(args.output_dir / f"team-match-base-{args.version_label}.csv", team_rows, TEAM_MATCH_FIELDS)
    write_csv(args.output_dir / f"team-rolling-form-{args.version_label}.csv", rolling_rows, rolling_fields())
    report = render_report(
        match_count=len(match_rows),
        team_row_count=len(team_rows),
        rolling_row_count=len(rolling_rows),
        xg_overlay_stats=xg_overlay_stats,
        team_rows=team_rows,
        output_dir=args.output_dir,
    )
    (args.output_dir / "team-form-report.md").write_text(report, encoding="utf-8")
    write_manifest(
        output_dir=args.output_dir,
        version_label=args.version_label,
        match_rows=team_rows,
        rolling_rows=rolling_rows,
        xg_overlay_stats=xg_overlay_stats,
    )

    if not args.skip_validation:
        validation_cmd = [
            sys.executable,
            str(ROOT / "scripts" / "validate-football-form-layer.py"),
            "--output-dir",
            str(args.output_dir),
        ]
        if args.fail_on_validation_error:
            validation_cmd.append("--fail-on-error")
        subprocess.run(validation_cmd, check=args.fail_on_validation_error)

    print(f"Wrote {rel(args.output_dir / 'team-match-base.csv')}")
    print(f"Wrote {rel(args.output_dir / 'team-rolling-form.csv')}")
    print(f"Wrote {rel(args.output_dir / f'team-match-base-{args.version_label}.csv')}")
    print(f"Wrote {rel(args.output_dir / f'team-rolling-form-{args.version_label}.csv')}")
    print(f"Wrote {rel(args.output_dir / 'team-form-manifest.json')}")
    print(f"Wrote {rel(args.output_dir / 'team-form-report.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
