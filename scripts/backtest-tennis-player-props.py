#!/usr/bin/env python3
"""Stage-0 backtest for Slam aces and double-fault projections.

This is outcome-only validation. It does not need Bet365 odds and it must not be
used as ROI evidence. The goal is to check whether the count projections beat a
simple player surface-average baseline on held-out Slam matches.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from tennis_props_model import count_line_probabilities, project_player, resolve_count_dispersion  # noqa: E402


SACKMANN_DIR = ROOT / "data" / "sackmann"
OUT_DIR = ROOT / "data" / "tennis-props" / "backtest"
DEFAULT_OUT_TXT = OUT_DIR / "aces-dfs-stage0-report.txt"
DEFAULT_OUT_CSV = OUT_DIR / "aces-dfs-stage0-rows.csv"

SLAMS = {
    "australian open": "Australian Open",
    "roland garros": "Roland Garros",
    "french open": "Roland Garros",
    "wimbledon": "Wimbledon",
    "us open": "US Open",
    "u.s. open": "US Open",
}


@dataclass(frozen=True)
class SideEvent:
    tour: str
    match_date: date
    year: int
    tourney_id: str
    tournament: str
    slam: str | None
    surface: str
    player_id: str
    player_name: str
    opponent_id: str
    aces: int
    dfs: int
    breaks_for: int
    broken: int
    return_games: int
    service_games_break_sample: int
    svpt: int
    svgms: int
    first_in: int
    first_won: int
    second_won: int
    opp_svpt: int
    opp_first_in: int
    opp_first_won: int
    opp_second_won: int
    won: bool


@dataclass(frozen=True)
class EvalRow:
    tour: str
    year: int
    date: date
    tournament: str
    round: str
    surface: str
    player_id: str
    player: str
    opponent_id: str
    opponent: str
    actual_aces: int
    actual_dfs: int
    projected_aces: float
    projected_dfs: float
    naive_aces: float
    naive_dfs: float
    ace_confidence: str
    df_confidence: str
    notes: str
    actual_service_points: int
    expected_service_points: float
    candidate_expected_service_points: float
    candidate_projected_aces: float
    candidate_projected_dfs: float
    player_service_point_win: float
    opponent_service_point_win: float
    same_tournament_matches: int


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def parse_int(value: object) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return 0
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def norm_surface(value: object) -> str:
    lower = str(value or "").strip().lower()
    if "clay" in lower:
        return "Clay"
    if "grass" in lower:
        return "Grass"
    if "hard" in lower:
        return "Hard"
    if "carpet" in lower:
        return "Carpet"
    return str(value or "Unknown").strip().title() or "Unknown"


def slam_name(value: object) -> str | None:
    lower = str(value or "").strip().lower()
    for needle, label in SLAMS.items():
        if needle in lower:
            return label
    return None


def score_games(value: object) -> int | None:
    text = str(value or "").strip()
    if not text or re.search(r"\b(W/O|WO|DEF)\b", text, re.I):
        return None
    total = 0
    for a, b in re.findall(r"(\d+)-(\d+)", text):
        total += int(a) + int(b)
    return total or None


def empty_totals() -> dict[str, float]:
    return {
        "matches": 0,
        "wins": 0,
        "svpt": 0,
        "svgms": 0,
        "aces": 0,
        "dfs": 0,
        "breaks_for": 0,
        "broken": 0,
        "return_games": 0,
        "service_games_break_sample": 0,
        "first_in": 0,
        "first_won": 0,
        "second_won": 0,
        "second_attempts": 0,
        "ret_first_points": 0,
        "ret_first_won": 0,
        "ret_second_points": 0,
        "ret_second_won": 0,
    }


def add_event(totals: dict[str, float], event: SideEvent) -> None:
    if event.svpt <= 0 or event.opp_svpt <= 0:
        return
    second_attempts = max(0, event.svpt - event.first_in)
    opp_second_attempts = max(0, event.opp_svpt - event.opp_first_in)
    totals["matches"] += 1
    totals["wins"] += 1 if event.won else 0
    totals["svpt"] += event.svpt
    totals["svgms"] += event.svgms
    totals["aces"] += event.aces
    totals["dfs"] += event.dfs
    totals["breaks_for"] += event.breaks_for
    totals["broken"] += event.broken
    totals["return_games"] += event.return_games
    totals["service_games_break_sample"] += event.service_games_break_sample
    totals["first_in"] += event.first_in
    totals["first_won"] += event.first_won
    totals["second_won"] += event.second_won
    totals["second_attempts"] += second_attempts
    totals["ret_first_points"] += event.opp_first_in
    totals["ret_first_won"] += max(0, event.opp_first_in - event.opp_first_won)
    totals["ret_second_points"] += opp_second_attempts
    totals["ret_second_won"] += max(0, opp_second_attempts - event.opp_second_won)


def safe_div(num: float, den: float) -> float | None:
    return None if den <= 0 else num / den


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None or not math.isfinite(value) else f"{value:.{digits}f}"


def totals_row(tour: str, player_id: str, player_name: str, surface: str, window: str, totals: dict[str, float]) -> dict[str, str]:
    return {
        "tour": tour.upper(),
        "player_id": player_id,
        "player_name": player_name,
        "surface": surface,
        "window": window,
        "matches": str(int(totals["matches"])),
        "wins": str(int(totals["wins"])),
        "svpt": str(int(totals["svpt"])),
        "svgms": str(int(totals["svgms"])),
        "aces": str(int(totals["aces"])),
        "dfs": str(int(totals["dfs"])),
        "breaks_for": str(int(totals["breaks_for"])),
        "broken": str(int(totals["broken"])),
        "return_games": str(int(totals["return_games"])),
        "service_games_break_sample": str(int(totals["service_games_break_sample"])),
        "ace_rate": fmt(safe_div(totals["aces"], totals["svpt"])),
        "df_rate": fmt(safe_div(totals["dfs"], totals["svpt"])),
        "break_for_rate": fmt(safe_div(totals["breaks_for"], totals["return_games"])),
        "broken_rate": fmt(safe_div(totals["broken"], totals["service_games_break_sample"])),
        "first_serve_pct": fmt(safe_div(totals["first_in"], totals["svpt"])),
        "first_serve_win_pct": fmt(safe_div(totals["first_won"], totals["first_in"])),
        "second_serve_win_pct": fmt(safe_div(totals["second_won"], totals["second_attempts"])),
        "ret_first_points": str(int(totals["ret_first_points"])),
        "ret_first_win_pct": fmt(safe_div(totals["ret_first_won"], totals["ret_first_points"])),
        "ret_second_points": str(int(totals["ret_second_points"])),
        "ret_second_win_pct": fmt(safe_div(totals["ret_second_won"], totals["ret_second_points"])),
        "svpt_per_svgame": fmt(safe_div(totals["svpt"], totals["svgms"]), 4),
    }


def side_event(tour: str, row: dict[str, str], match_date: date, *, prefix: str, opp_prefix: str, won: bool) -> SideEvent | None:
    id_col = "winner_id" if won else "loser_id"
    name_col = "winner_name" if won else "loser_name"
    opp_id_col = "loser_id" if won else "winner_id"
    player_id = str(row.get(id_col) or "").strip()
    opponent_id = str(row.get(opp_id_col) or "").strip()
    player_name = str(row.get(name_col) or "").strip()
    if not player_id or not opponent_id or not player_name:
        return None
    svpt = parse_int(row.get(f"{prefix}_svpt"))
    opp_svpt = parse_int(row.get(f"{opp_prefix}_svpt"))
    if svpt <= 0 or opp_svpt <= 0:
        return None
    service_games = parse_int(row.get(f"{prefix}_SvGms"))
    opponent_service_games = parse_int(row.get(f"{opp_prefix}_SvGms"))
    bp_faced = parse_int(row.get(f"{prefix}_bpFaced"))
    bp_saved = parse_int(row.get(f"{prefix}_bpSaved"))
    opponent_bp_faced = parse_int(row.get(f"{opp_prefix}_bpFaced"))
    opponent_bp_saved = parse_int(row.get(f"{opp_prefix}_bpSaved"))
    if service_games <= 0 or opponent_service_games <= 0:
        return None
    return SideEvent(
        tour=tour,
        match_date=match_date,
        year=match_date.year,
        tourney_id=str(row.get("tourney_id") or ""),
        tournament=str(row.get("tourney_name") or "").strip(),
        slam=slam_name(row.get("tourney_name")),
        surface=norm_surface(row.get("surface")),
        player_id=player_id,
        player_name=player_name,
        opponent_id=opponent_id,
        aces=parse_int(row.get(f"{prefix}_ace")),
        dfs=parse_int(row.get(f"{prefix}_df")),
        breaks_for=max(0, opponent_bp_faced - opponent_bp_saved),
        broken=max(0, bp_faced - bp_saved),
        return_games=opponent_service_games,
        service_games_break_sample=service_games,
        svpt=svpt,
        svgms=service_games,
        first_in=parse_int(row.get(f"{prefix}_1stIn")),
        first_won=parse_int(row.get(f"{prefix}_1stWon")),
        second_won=parse_int(row.get(f"{prefix}_2ndWon")),
        opp_svpt=opp_svpt,
        opp_first_in=parse_int(row.get(f"{opp_prefix}_1stIn")),
        opp_first_won=parse_int(row.get(f"{opp_prefix}_1stWon")),
        opp_second_won=parse_int(row.get(f"{opp_prefix}_2ndWon")),
        won=won,
    )


def load_data(sackmann_dir: Path, years: Iterable[int]) -> tuple[list[dict[str, str]], list[SideEvent]]:
    matches: list[dict[str, str]] = []
    events: list[SideEvent] = []
    for tour in ("atp", "wta"):
        for year in years:
            path = sackmann_dir / f"{tour}_matches_{year}.csv"
            for row in read_csv(path):
                match_date = parse_date(row.get("tourney_date"))
                if match_date is None:
                    continue
                row = dict(row)
                row["_tour"] = tour
                row["_date_iso"] = match_date.isoformat()
                row["_surface_norm"] = norm_surface(row.get("surface"))
                row["_slam"] = slam_name(row.get("tourney_name")) or ""
                games = score_games(row.get("score"))
                row["_match_games"] = "" if games is None else str(games)
                matches.append(row)
                winner_event = side_event(tour, row, match_date, prefix="w", opp_prefix="l", won=True)
                loser_event = side_event(tour, row, match_date, prefix="l", opp_prefix="w", won=False)
                if winner_event:
                    events.append(winner_event)
                if loser_event:
                    events.append(loser_event)
    matches.sort(key=lambda item: item["_date_iso"])
    events.sort(key=lambda item: item.match_date)
    return matches, events


def build_window_rows(
    *,
    tour: str,
    player_id: str,
    player_name: str,
    surface: str,
    as_of: date,
    events_by_player: dict[tuple[str, str], list[SideEvent]],
) -> dict[str, dict[str, str]]:
    windows = {"L12M": 365, "L24M": 730, "career_4y": 1460}
    out: dict[str, dict[str, str]] = {}
    player_events = events_by_player.get((tour, player_id), [])
    for window, days in windows.items():
        totals = empty_totals()
        for event in player_events:
            age = (as_of - event.match_date).days
            if age <= 0 or age > days or event.surface != surface:
                continue
            add_event(totals, event)
        if totals["matches"] > 0:
            out[window] = totals_row(tour, player_id, player_name, surface, window, totals)
    return out


def build_same_tournament_row(
    *,
    tour: str,
    player_id: str,
    tourney_id: str,
    as_of: date,
    events_by_player: dict[tuple[str, str], list[SideEvent]],
) -> dict[str, str] | None:
    totals = empty_totals()
    for event in events_by_player.get((tour, player_id), []):
        if event.match_date >= as_of or event.tourney_id != tourney_id:
            continue
        add_event(totals, event)
    if totals["matches"] <= 0:
        return None
    return {
        "matches": str(int(totals["matches"])),
        "svpt": str(int(totals["svpt"])),
        "aces": str(int(totals["aces"])),
        "dfs": str(int(totals["dfs"])),
        "breaks_for": str(int(totals["breaks_for"])),
        "broken": str(int(totals["broken"])),
        "return_games": str(int(totals["return_games"])),
        "service_games_break_sample": str(int(totals["service_games_break_sample"])),
    }


def build_factor_row(
    *,
    tour: str,
    slam: str,
    surface: str,
    as_of: date,
    matches: list[dict[str, str]],
    events: list[SideEvent],
    fallback_best_of: int,
) -> dict[str, str]:
    slam_totals = empty_totals()
    base_totals = empty_totals()
    match_games_sum = 0
    match_games_n = 0
    for event in events:
        if event.tour != tour or event.surface != surface or event.match_date >= as_of:
            continue
        if event.slam == slam:
            add_event(slam_totals, event)
        elif event.slam is None:
            add_event(base_totals, event)
    for row in matches:
        row_date = parse_date(row.get("_date_iso"))
        if row_date is None or row_date >= as_of:
            continue
        if row.get("_tour") != tour or row.get("_surface_norm") != surface or row.get("_slam") != slam:
            continue
        games = parse_int(row.get("_match_games"))
        if games > 0:
            match_games_sum += games
            match_games_n += 1

    base_ace = safe_div(base_totals["aces"], base_totals["svpt"])
    base_df = safe_div(base_totals["dfs"], base_totals["svpt"])
    slam_ace = safe_div(slam_totals["aces"], slam_totals["svpt"])
    slam_df = safe_div(slam_totals["dfs"], slam_totals["svpt"])
    fallback_games = 38.5 if tour == "atp" and fallback_best_of == 5 else 21.5
    match_games = safe_div(match_games_sum, match_games_n) or fallback_games
    return {
        "tour": tour.upper(),
        "tournament": slam,
        "surface": surface,
        "year": "PAST_ONLY",
        "matches": str(int(slam_totals["matches"] / 2)),
        "ace_rate": fmt(slam_ace),
        "df_rate": fmt(slam_df),
        "svpt_per_svgame": fmt(safe_div(slam_totals["svpt"], slam_totals["svgms"]) or 6.35, 4),
        "match_games_per_match": fmt(match_games, 3),
        "tour_surface_baseline_ace": fmt(base_ace),
        "tour_surface_baseline_df": fmt(base_df),
        "ace_factor": fmt((slam_ace / base_ace) if slam_ace and base_ace else 1.0, 4),
        "df_factor": fmt((slam_df / base_df) if slam_df and base_df else 1.0, 4),
        "sample_flag": "OK" if slam_totals["matches"] >= 160 and base_totals["matches"] >= 400 else "LOW_SAMPLE",
    }


def slam_prior_matches(tour: str, player_id: str, slam: str, as_of: date, events_by_player: dict[tuple[str, str], list[SideEvent]]) -> int:
    return sum(
        1
        for event in events_by_player.get((tour, player_id), [])
        if event.match_date < as_of and event.slam == slam
    )


def naive_projection(player_rows: dict[str, dict[str, str]], factor_row: dict[str, str], expected_service_points: float, tour: str) -> tuple[float, float]:
    l12 = player_rows.get("L12M") or {}
    prior_ace = float(factor_row.get("tour_surface_baseline_ace") or (0.065 if tour == "atp" else 0.027))
    prior_df = float(factor_row.get("tour_surface_baseline_df") or (0.035 if tour == "atp" else 0.048))
    ace_rate = float(l12.get("ace_rate") or prior_ace)
    df_rate = float(l12.get("df_rate") or prior_df)
    return ace_rate * expected_service_points, df_rate * expected_service_points


def evaluate(sackmann_dir: Path, years: list[int], eval_years: set[int]) -> list[EvalRow]:
    matches, events = load_data(sackmann_dir, years)
    events_by_player: dict[tuple[str, str], list[SideEvent]] = defaultdict(list)
    for event in events:
        events_by_player[(event.tour, event.player_id)].append(event)

    rows: list[EvalRow] = []
    factor_cache: dict[tuple[str, str, str, date, int], dict[str, str]] = {}
    for row in matches:
        match_date = parse_date(row.get("_date_iso"))
        if match_date is None or match_date.year not in eval_years:
            continue
        tour = str(row.get("_tour") or "")
        slam = str(row.get("_slam") or "")
        if not slam:
            continue
        surface = str(row.get("_surface_norm") or "")
        best_of = parse_int(row.get("best_of")) or (5 if tour == "atp" else 3)
        factor_key = (tour, slam, surface, match_date, best_of)
        factor = factor_cache.get(factor_key)
        if factor is None:
            factor = build_factor_row(
                tour=tour,
                slam=slam,
                surface=surface,
                as_of=match_date,
                matches=matches,
                events=events,
                fallback_best_of=best_of,
            )
            factor_cache[factor_key] = factor
        expected_match_games = float(factor.get("match_games_per_match") or (38.5 if best_of == 5 else 21.5))
        sides = (
            ("winner_id", "winner_name", "loser_id", "loser_name", "w", True),
            ("loser_id", "loser_name", "winner_id", "winner_name", "l", False),
        )
        for id_col, name_col, opp_id_col, opp_name_col, prefix, _won in sides:
            player_id = str(row.get(id_col) or "").strip()
            opponent_id = str(row.get(opp_id_col) or "").strip()
            player = str(row.get(name_col) or "").strip()
            opponent = str(row.get(opp_name_col) or "").strip()
            if not player_id or not opponent_id:
                continue
            player_rows = build_window_rows(
                tour=tour,
                player_id=player_id,
                player_name=player,
                surface=surface,
                as_of=match_date,
                events_by_player=events_by_player,
            )
            opponent_rows = build_window_rows(
                tour=tour,
                player_id=opponent_id,
                player_name=opponent,
                surface=surface,
                as_of=match_date,
                events_by_player=events_by_player,
            )
            same = build_same_tournament_row(
                tour=tour,
                player_id=player_id,
                tourney_id=str(row.get("tourney_id") or ""),
                as_of=match_date,
                events_by_player=events_by_player,
            )
            projection = project_player(
                tour=tour,
                player_rows=player_rows,
                opponent_rows=opponent_rows,
                factor_row=factor,
                expected_match_games=expected_match_games,
                slam_matches=slam_prior_matches(tour, player_id, slam, match_date, events_by_player),
                same_tournament_row=same,
            )
            candidate = project_player(
                tour=tour,
                player_rows=player_rows,
                opponent_rows=opponent_rows,
                factor_row=factor,
                expected_match_games=expected_match_games,
                slam_matches=slam_prior_matches(tour, player_id, slam, match_date, events_by_player),
                same_tournament_row=same,
                service_points_mode="matchup_recursion",
            )
            naive_aces, naive_dfs = naive_projection(
                player_rows,
                factor,
                projection.expected_service_points,
                tour,
            )
            rows.append(
                EvalRow(
                    tour=tour.upper(),
                    year=match_date.year,
                    date=match_date,
                    tournament=slam,
                    round=str(row.get("round") or ""),
                    surface=surface,
                    player_id=player_id,
                    player=player,
                    opponent_id=opponent_id,
                    opponent=opponent,
                    actual_aces=parse_int(row.get(f"{prefix}_ace")),
                    actual_dfs=parse_int(row.get(f"{prefix}_df")),
                    projected_aces=projection.expected_aces,
                    projected_dfs=projection.expected_dfs,
                    naive_aces=naive_aces,
                    naive_dfs=naive_dfs,
                    ace_confidence=projection.ace_confidence,
                    df_confidence=projection.df_confidence,
                    notes=";".join(projection.notes),
                    actual_service_points=parse_int(row.get(f"{prefix}_svpt")),
                    expected_service_points=projection.expected_service_points,
                    candidate_expected_service_points=candidate.expected_service_points,
                    candidate_projected_aces=candidate.expected_aces,
                    candidate_projected_dfs=candidate.expected_dfs,
                    player_service_point_win=projection.player_service_point_win,
                    opponent_service_point_win=projection.opponent_service_point_win,
                    same_tournament_matches=projection.same_tournament_matches,
                )
            )
    return rows


def mae(values: list[float]) -> float:
    return mean(values) if values else float("nan")


def rmse(errors: list[float]) -> float:
    return math.sqrt(mean([err * err for err in errors])) if errors else float("nan")


def log_loss(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    total = 0.0
    for prob, outcome in zip(probs, outcomes, strict=True):
        p = max(1e-6, min(1.0 - 1e-6, prob))
        total += -outcome * math.log(p) - (1 - outcome) * math.log(1.0 - p)
    return total / len(probs)


def bucket_summary(rows: list[EvalRow]) -> dict[str, float]:
    ace_errors = [r.projected_aces - r.actual_aces for r in rows]
    df_errors = [r.projected_dfs - r.actual_dfs for r in rows]
    naive_ace_errors = [r.naive_aces - r.actual_aces for r in rows]
    naive_df_errors = [r.naive_dfs - r.actual_dfs for r in rows]

    ace_model_probs: list[float] = []
    ace_naive_probs: list[float] = []
    ace_outcomes: list[int] = []
    df_model_probs: list[float] = []
    df_naive_probs: list[float] = []
    df_outcomes: list[int] = []
    for r in rows:
        ace_line = math.floor(r.naive_aces) + 0.5
        df_line = math.floor(r.naive_dfs) + 0.5
        ace_alpha = resolve_count_dispersion(r.tour, "aces")
        df_alpha = resolve_count_dispersion(r.tour, "dfs")
        ace_model_probs.append(
            count_line_probabilities(
                ace_line,
                r.projected_aces,
                distribution="negative_binomial",
                alpha=ace_alpha,
                tour=r.tour,
                market="aces",
            )[0]
        )
        ace_naive_probs.append(
            count_line_probabilities(
                ace_line,
                r.naive_aces,
                distribution="negative_binomial",
                alpha=ace_alpha,
                tour=r.tour,
                market="aces",
            )[0]
        )
        ace_outcomes.append(1 if r.actual_aces > ace_line else 0)
        df_model_probs.append(
            count_line_probabilities(
                df_line,
                r.projected_dfs,
                distribution="negative_binomial",
                alpha=df_alpha,
                tour=r.tour,
                market="dfs",
            )[0]
        )
        df_naive_probs.append(
            count_line_probabilities(
                df_line,
                r.naive_dfs,
                distribution="negative_binomial",
                alpha=df_alpha,
                tour=r.tour,
                market="dfs",
            )[0]
        )
        df_outcomes.append(1 if r.actual_dfs > df_line else 0)

    return {
        "n": float(len(rows)),
        "aces_mae": mae([abs(err) for err in ace_errors]),
        "aces_naive_mae": mae([abs(err) for err in naive_ace_errors]),
        "aces_bias": mean(ace_errors) if ace_errors else float("nan"),
        "aces_rmse": rmse(ace_errors),
        "aces_synth_logloss": log_loss(ace_model_probs, ace_outcomes),
        "aces_naive_synth_logloss": log_loss(ace_naive_probs, ace_outcomes),
        "dfs_mae": mae([abs(err) for err in df_errors]),
        "dfs_naive_mae": mae([abs(err) for err in naive_df_errors]),
        "dfs_bias": mean(df_errors) if df_errors else float("nan"),
        "dfs_rmse": rmse(df_errors),
        "dfs_synth_logloss": log_loss(df_model_probs, df_outcomes),
        "dfs_naive_synth_logloss": log_loss(df_naive_probs, df_outcomes),
    }


def group_rows(rows: list[EvalRow], key_fn) -> list[tuple[str, dict[str, float]]]:
    grouped: dict[str, list[EvalRow]] = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(row)
    return [(key, bucket_summary(grouped[key])) for key in sorted(grouped)]


def fmt_num(value: float, digits: int = 3) -> str:
    return "n/a" if math.isnan(value) else f"{value:.{digits}f}"


def write_rows(path: Path, rows: list[EvalRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "tour",
        "year",
        "date",
        "tournament",
        "round",
        "surface",
        "player_id",
        "player",
        "opponent_id",
        "opponent",
        "actual_aces",
        "projected_aces",
        "naive_aces",
        "actual_dfs",
        "projected_dfs",
        "naive_dfs",
        "ace_confidence",
        "df_confidence",
        "expected_service_points",
        "candidate_expected_service_points",
        "candidate_projected_aces",
        "candidate_projected_dfs",
        "player_service_point_win",
        "opponent_service_point_win",
        "same_tournament_matches",
        "notes",
        "actual_service_points",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "tour": row.tour,
                    "year": row.year,
                    "date": row.date.isoformat(),
                    "tournament": row.tournament,
                    "round": row.round,
                    "surface": row.surface,
                    "player_id": row.player_id,
                    "player": row.player,
                    "opponent_id": row.opponent_id,
                    "opponent": row.opponent,
                    "actual_aces": row.actual_aces,
                    "projected_aces": f"{row.projected_aces:.3f}",
                    "naive_aces": f"{row.naive_aces:.3f}",
                    "actual_dfs": row.actual_dfs,
                    "projected_dfs": f"{row.projected_dfs:.3f}",
                    "naive_dfs": f"{row.naive_dfs:.3f}",
                    "ace_confidence": row.ace_confidence,
                    "df_confidence": row.df_confidence,
                    "expected_service_points": f"{row.expected_service_points:.3f}",
                    "candidate_expected_service_points": f"{row.candidate_expected_service_points:.3f}",
                    "candidate_projected_aces": f"{row.candidate_projected_aces:.3f}",
                    "candidate_projected_dfs": f"{row.candidate_projected_dfs:.3f}",
                    "player_service_point_win": f"{row.player_service_point_win:.6f}",
                    "opponent_service_point_win": f"{row.opponent_service_point_win:.6f}",
                    "same_tournament_matches": row.same_tournament_matches,
                    "notes": row.notes,
                    "actual_service_points": row.actual_service_points,
                }
            )


def write_report(path: Path, rows: list[EvalRow], *, years: list[int], sackmann_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("Tennis Slam Aces/DF Stage-0 Backtest")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Sackmann dir: {sackmann_dir}")
    lines.append(f"Evaluation years: {', '.join(map(str, years))}")
    lines.append("Outcome-only validation. No odds, no ROI, no CLV.")
    lines.append(
        "Synthetic O/U log-loss uses negative-binomial tails with alpha: "
        "ATP aces 0.35, WTA aces 0.50, ATP DFs 0.10, WTA DFs 0.20."
    )
    lines.append("")

    def section(title: str, items: list[tuple[str, dict[str, float]]]) -> None:
        lines.append(title)
        lines.append("Bucket                         N  AceMAE model/naive  AceLL model/naive  DfMAE model/naive  DfLL model/naive  AceBias  DfBias")
        for key, summary in items:
            lines.append(
                f"{key[:28]:28s} {int(summary['n']):4d}  "
                f"{fmt_num(summary['aces_mae'])}/{fmt_num(summary['aces_naive_mae'])}        "
                f"{fmt_num(summary['aces_synth_logloss'])}/{fmt_num(summary['aces_naive_synth_logloss'])}        "
                f"{fmt_num(summary['dfs_mae'])}/{fmt_num(summary['dfs_naive_mae'])}        "
                f"{fmt_num(summary['dfs_synth_logloss'])}/{fmt_num(summary['dfs_naive_synth_logloss'])}        "
                f"{summary['aces_bias']:+.3f}  {summary['dfs_bias']:+.3f}"
            )
        lines.append("")

    section("Overall", [("all", bucket_summary(rows))])
    section("By tour", group_rows(rows, lambda r: r.tour))
    section("By tournament", group_rows(rows, lambda r: f"{r.tour} {r.tournament}"))
    section("By year", group_rows(rows, lambda r: str(r.year)))
    section("By ace confidence", group_rows(rows, lambda r: f"aces {r.ace_confidence}"))
    section("By DF confidence", group_rows(rows, lambda r: f"dfs {r.df_confidence}"))

    high_ace = [r for r in rows if r.ace_confidence == "HIGH"]
    high_df = [r for r in rows if r.df_confidence == "HIGH"]
    overall = bucket_summary(rows)
    lines.append("Verdict")
    if overall["aces_mae"] < overall["aces_naive_mae"] and overall["aces_synth_logloss"] <= overall["aces_naive_synth_logloss"]:
        lines.append("- Aces beat the naive surface-average baseline on MAE and synthetic O/U log-loss. Worth keeping as a research board.")
    elif overall["aces_mae"] < overall["aces_naive_mae"]:
        lines.append("- Aces beat naive on count MAE but not synthetic O/U log-loss. Use projections only, not recommendations.")
    else:
        lines.append("- Aces do not beat the naive baseline overall. Do not use for betting recommendations yet.")
    if overall["dfs_mae"] < overall["dfs_naive_mae"] and overall["dfs_synth_logloss"] <= overall["dfs_naive_synth_logloss"]:
        lines.append("- DFs beat the naive baseline overall, but still require line capture because counts are low and noisy.")
    elif overall["dfs_mae"] < overall["dfs_naive_mae"]:
        lines.append("- DFs improve count MAE but not O/U classification. Keep projection-only.")
    else:
        lines.append("- DFs do not beat the naive baseline overall. Keep them display-only or remove recommendations.")
    lines.append(f"- HIGH-confidence aces sample: {len(high_ace)} rows. HIGH-confidence DF sample: {len(high_df)} rows.")
    lines.append("- No live staking without Bet365 line capture and settlement.")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest Slam aces/DF projections against Sackmann outcomes.")
    parser.add_argument("--sackmann-dir", type=Path, default=SACKMANN_DIR)
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--eval-years", nargs="+", type=int, default=[2024, 2025])
    parser.add_argument("--out-txt", type=Path, default=DEFAULT_OUT_TXT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    years = list(range(args.start_year, args.end_year + 1))
    rows = evaluate(args.sackmann_dir, years, set(args.eval_years))
    if not rows:
        raise SystemExit("No Slam prop backtest rows generated.")
    write_rows(args.out_csv, rows)
    write_report(args.out_txt, rows, years=args.eval_years, sackmann_dir=args.sackmann_dir)
    print(f"Wrote {args.out_txt}")
    print(f"Wrote {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
