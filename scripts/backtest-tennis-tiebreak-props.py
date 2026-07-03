#!/usr/bin/env python3
"""Outcome-only calibration audit for tennis tie-break props.

This validates the research probabilities now shown on the tennis props board:
  - first-set tie-break
  - any tie-break in the match

It uses OnCourt main-tour history with past-only player windows, past-only venue
factors, and past-only same-event bumps. No odds, ROI, or CLV are inferred here.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from tennis_props_model import project_player, set_tiebreak_calibration_override  # noqa: E402


ONCOURT_DIR = ROOT / "data" / "oncourt"
OUT_DIR = ROOT / "data" / "tennis-props" / "backtest"
DEFAULT_OUT_TXT = OUT_DIR / "tiebreak-stage0-report.txt"
DEFAULT_OUT_CSV = OUT_DIR / "tiebreak-stage0-rows.csv"
DEFAULT_GATE_JSON = OUT_DIR / "tiebreak-gate.json"
DEFAULT_CALIBRATION_JSON = ROOT / "data" / "tennis-props" / "tiebreak-calibration.json"
MAIN_TOUR_RANKS = {"2", "3", "4"}
WINDOW_DAYS = {"L12M": 365, "L24M": 730, "career_4y": 1460}


@dataclass(frozen=True)
class SideEvent:
    tour: str
    match_date: date
    tour_id: str
    tournament: str
    surface: str
    player_id: str
    player_name: str
    opponent_id: str
    aces: int
    dfs: int
    svpt: int
    svgms: float
    first_in: int
    first_won: int
    second_won: int
    opp_svpt: int
    opp_first_in: int
    opp_first_won: int
    opp_second_won: int
    breaks_for: int
    broken: int
    won: bool


@dataclass(frozen=True)
class MatchEvent:
    tour: str
    match_date: date
    year: int
    tour_id: str
    tournament: str
    surface: str
    round_id: str
    winner_id: str
    winner_name: str
    loser_id: str
    loser_name: str
    score: str
    total_games: int
    best_of: int
    first_set_tb: int
    match_tb: int
    w: SideEvent
    l: SideEvent


@dataclass(frozen=True)
class EvalRow:
    tour: str
    year: int
    date: date
    tournament: str
    surface: str
    best_of: int
    match: str
    actual_first_set_tb: int
    actual_match_tb: int
    first_set_prob: float
    match_prob: float
    first_set_base_prob: float
    match_base_prob: float
    first_set_naive_prob: float
    match_naive_prob: float
    tiebreak_confidence: str
    venue_first_set_factor: float
    venue_match_factor: float
    current_first_set_factor: float
    current_match_factor: float
    venue_matches: int
    current_matches: int


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_int(value: object) -> int:
    try:
        text = str(value or "").strip()
        return int(float(text)) if text else 0
    except (TypeError, ValueError):
        return 0


def parse_float(value: object, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def oncourt_service_points(stat: dict[str, str], prefix: str) -> int:
    return parse_int(stat.get(f"{prefix}_fsof")) or parse_int(stat.get(f"{prefix}_svpt"))


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def norm_surface(value: object) -> str:
    lower = str(value or "").strip().lower()
    if "clay" in lower:
        return "Clay"
    if "grass" in lower:
        return "Grass"
    if "hard" in lower or "acrylic" in lower:
        return "Hard"
    if "carpet" in lower:
        return "Carpet"
    return str(value or "Unknown").strip().title() or "Unknown"


def canonical_tournament_name(value: object) -> str:
    raw = str(value or "").strip()
    lower = raw.lower()
    if "australian open" in lower:
        return "Australian Open"
    if "roland garros" in lower or "french open" in lower:
        return "Roland Garros"
    if "wimbledon" in lower:
        return "Wimbledon"
    if "us open" in lower or "u.s. open" in lower:
        return "US Open"
    if "hertogenbosch" in lower or "rosmalen" in lower or "libema open" in lower:
        return "Hertogenbosch"
    if "queen" in lower or "cinch championships" in lower or "stella artois" in lower or "lta london" in lower:
        return "Queen's Club"
    if "stuttgart" in lower or "boss open" in lower:
        return "Stuttgart"
    if "halle" in lower or "terra wortmann" in lower or "gerry weber" in lower:
        return "Halle"
    if "nottingham" in lower:
        return "Nottingham"
    if "berlin" in lower and ("open" in lower or "tennis" in lower or "bett1" in lower):
        return "Berlin"
    if "eastbourne" in lower:
        return "Eastbourne"
    if "bad homburg" in lower:
        return "Bad Homburg"
    if "mallorca" in lower:
        return "Mallorca"
    return raw.split(" - ")[0].strip() or raw


def score_games(score: object) -> int:
    text = str(score or "").strip()
    if not text or re.search(r"\b(W/O|WO|DEF|RET|ABD)\b", text, re.I):
        return 0
    return sum(int(a) + int(b) for a, b in re.findall(r"(\d+)-(\d+)", text))


def score_tiebreak_flags(score: object) -> tuple[int, int, int]:
    text = str(score or "").strip()
    if not text or re.search(r"\b(W/O|WO|DEF|RET|ABD)\b", text, re.I):
        return 0, 0, 0
    sets = re.findall(r"(\d+)\s*-\s*(\d+)(?:\s*\([^)]*\))?", text)
    if not sets:
        return 0, 0, 0
    tb_flags = [1 if {int(a), int(b)} == {6, 7} else 0 for a, b in sets]
    return len(sets), tb_flags[0], 1 if any(tb_flags) else 0


def safe_div(num: float, den: float) -> float | None:
    return None if den <= 0 else num / den


def fmt(value: float | None, digits: int = 6) -> str:
    if value is None or not math.isfinite(value):
        return ""
    return f"{value:.{digits}f}"


def empty_totals() -> dict[str, float]:
    return {
        "matches": 0.0,
        "aces": 0.0,
        "dfs": 0.0,
        "svpt": 0.0,
        "svgms": 0.0,
        "match_games": 0.0,
        "match_games_n": 0.0,
        "first_set_tiebreaks": 0.0,
        "match_tiebreaks": 0.0,
    }


def add_match_totals(totals: dict[str, float], match: MatchEvent) -> None:
    totals["matches"] += 1
    totals["aces"] += match.w.aces + match.l.aces
    totals["dfs"] += match.w.dfs + match.l.dfs
    totals["svpt"] += match.w.svpt + match.l.svpt
    totals["svgms"] += match.w.svgms + match.l.svgms
    totals["match_games"] += match.total_games
    totals["match_games_n"] += 1
    totals["first_set_tiebreaks"] += match.first_set_tb
    totals["match_tiebreaks"] += match.match_tb


def subtract_totals(total: dict[str, float], part: dict[str, float]) -> dict[str, float]:
    out = empty_totals()
    for key in out:
        out[key] = max(0.0, total.get(key, 0.0) - part.get(key, 0.0))
    return out


def ratio_factor(current_rate: float, baseline_rate: float | None, weight: float, low: float, high: float) -> float:
    if baseline_rate is None or baseline_rate <= 0 or current_rate <= 0 or weight <= 0:
        return 1.0
    raw = current_rate / baseline_rate
    return max(low, min(high, 1.0 + (raw - 1.0) * weight))


def factor_row_from_totals(tour: str, tournament: str, surface: str, event: dict[str, float], baseline: dict[str, float]) -> dict[str, str]:
    ace_rate = safe_div(event["aces"], event["svpt"])
    df_rate = safe_div(event["dfs"], event["svpt"])
    first_set_rate = safe_div(event["first_set_tiebreaks"], event["matches"])
    match_rate = safe_div(event["match_tiebreaks"], event["matches"])
    base_ace = safe_div(baseline["aces"], baseline["svpt"])
    base_df = safe_div(baseline["dfs"], baseline["svpt"])
    base_first = safe_div(baseline["first_set_tiebreaks"], baseline["matches"])
    base_match = safe_div(baseline["match_tiebreaks"], baseline["matches"])
    weight = event["matches"] / (event["matches"] + 100.0) if event["matches"] > 0 else 0.0
    return {
        "tour": tour.upper(),
        "tournament": tournament,
        "surface": surface,
        "year": "PAST_ONLY",
        "matches": str(int(event["matches"])),
        "ace_rate": fmt(ace_rate),
        "df_rate": fmt(df_rate),
        "first_set_tiebreak_rate": fmt(first_set_rate),
        "match_tiebreak_rate": fmt(match_rate),
        "svpt_per_svgame": fmt(safe_div(event["svpt"], event["svgms"]) or safe_div(baseline["svpt"], baseline["svgms"]) or 6.35, 4),
        "match_games_per_match": fmt(safe_div(event["match_games"], event["match_games_n"]) or safe_div(baseline["match_games"], baseline["match_games_n"]) or 22.5, 3),
        "tour_surface_baseline_ace": fmt(base_ace),
        "tour_surface_baseline_df": fmt(base_df),
        "tour_surface_baseline_first_set_tiebreak": fmt(base_first),
        "tour_surface_baseline_match_tiebreak": fmt(base_match),
        "ace_factor": fmt(ratio_factor(ace_rate or 0.0, base_ace, weight, 0.75, 1.35), 4),
        "df_factor": fmt(ratio_factor(df_rate or 0.0, base_df, weight, 0.75, 1.35), 4),
        "first_set_tiebreak_factor": fmt(ratio_factor(first_set_rate or 0.0, base_first, weight, 0.70, 1.45), 4),
        "match_tiebreak_factor": fmt(ratio_factor(match_rate or 0.0, base_match, weight, 0.70, 1.35), 4),
        "sample_flag": "OK" if event["matches"] >= 50 and baseline["matches"] >= 150 else "LOW_SAMPLE",
    }


def side_totals_row(tour: str, player_id: str, player_name: str, surface: str, window: str, totals: dict[str, float]) -> dict[str, str]:
    second_attempts = max(0.0, totals["svpt"] - totals["first_in"])
    return {
        "tour": tour.upper(),
        "player_id": player_id,
        "player_name": player_name,
        "surface": surface,
        "window": window,
        "matches": str(int(totals["matches"])),
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
        "second_serve_win_pct": fmt(safe_div(totals["second_won"], second_attempts)),
        "ret_first_points": str(int(totals["ret_first_points"])),
        "ret_first_win_pct": fmt(safe_div(totals["ret_first_won"], totals["ret_first_points"])),
        "ret_second_points": str(int(totals["ret_second_points"])),
        "ret_second_win_pct": fmt(safe_div(totals["ret_second_won"], totals["ret_second_points"])),
        "svpt_per_svgame": fmt(safe_div(totals["svpt"], totals["svgms"]), 4),
    }


def empty_side_totals() -> dict[str, float]:
    return {
        "matches": 0.0,
        "svpt": 0.0,
        "svgms": 0.0,
        "aces": 0.0,
        "dfs": 0.0,
        "breaks_for": 0.0,
        "broken": 0.0,
        "return_games": 0.0,
        "service_games_break_sample": 0.0,
        "first_in": 0.0,
        "first_won": 0.0,
        "second_won": 0.0,
        "ret_first_points": 0.0,
        "ret_first_won": 0.0,
        "ret_second_points": 0.0,
        "ret_second_won": 0.0,
    }


def add_side_totals(totals: dict[str, float], event: SideEvent) -> None:
    second_attempts = max(0, event.svpt - event.first_in)
    opp_second_attempts = max(0, event.opp_svpt - event.opp_first_in)
    totals["matches"] += 1
    totals["svpt"] += event.svpt
    totals["svgms"] += event.svgms
    totals["aces"] += event.aces
    totals["dfs"] += event.dfs
    totals["breaks_for"] += event.breaks_for
    totals["broken"] += event.broken
    totals["return_games"] += event.svgms
    totals["service_games_break_sample"] += event.svgms
    totals["first_in"] += event.first_in
    totals["first_won"] += event.first_won
    totals["second_won"] += event.second_won
    totals["ret_first_points"] += event.opp_first_in
    totals["ret_first_won"] += max(0, event.opp_first_in - event.opp_first_won)
    totals["ret_second_points"] += opp_second_attempts
    totals["ret_second_won"] += max(0, opp_second_attempts - event.opp_second_won)
    # Keep denominator coherent even when service games are approximated.
    if second_attempts <= 0:
        totals["second_won"] += 0


def load_players(tour: str) -> dict[str, str]:
    return {
        str(row.get("id") or "").strip(): str(row.get("name") or "").strip()
        for row in read_csv(ONCOURT_DIR / f"players_{tour}.csv")
        if str(row.get("id") or "").strip()
    }


def load_events(start_year: int, end_year: int) -> list[MatchEvent]:
    court_surface = {str(row.get("id") or "").strip(): norm_surface(row.get("name")) for row in read_csv(ONCOURT_DIR / "courts.csv")}
    all_matches: list[MatchEvent] = []
    for tour in ("atp", "wta"):
        players = load_players(tour)
        tours = {}
        for row in read_csv(ONCOURT_DIR / f"tours_{tour}.csv"):
            event_id = str(row.get("id") or "").strip()
            event_date = parse_date(row.get("date"))
            if not event_id or event_date is None or event_date.year < start_year or event_date.year > end_year:
                continue
            if str(row.get("rank") or "").strip() not in MAIN_TOUR_RANKS:
                continue
            tours[event_id] = {
                "name": canonical_tournament_name(row.get("name")),
                "surface": court_surface.get(str(row.get("court_id") or "").strip(), "Unknown"),
                "rank": str(row.get("rank") or "").strip(),
            }
        stat_map: dict[tuple[str, str, str, str], deque[dict[str, str]]] = defaultdict(deque)
        for row in read_csv(ONCOURT_DIR / f"stat_{tour}.csv"):
            key = (
                str(row.get("winner_id") or "").strip(),
                str(row.get("loser_id") or "").strip(),
                str(row.get("tour_id") or "").strip(),
                str(row.get("round_id") or "").strip(),
            )
            stat_map[key].append(row)
        for game in read_csv(ONCOURT_DIR / f"games_{tour}.csv"):
            tour_id = str(game.get("tour_id") or "").strip()
            meta = tours.get(tour_id)
            if not meta:
                continue
            match_date = parse_date(game.get("date"))
            if match_date is None or match_date.year < start_year or match_date.year > end_year:
                continue
            score = str(game.get("result") or "")
            total_games = score_games(score)
            sets_played, first_set_tb, match_tb = score_tiebreak_flags(score)
            if total_games <= 0 or sets_played <= 0:
                continue
            winner_id = str(game.get("winner_id") or "").strip()
            loser_id = str(game.get("loser_id") or "").strip()
            winner_name = players.get(winner_id, "")
            loser_name = players.get(loser_id, "")
            if not winner_name or not loser_name or "/" in winner_name or "/" in loser_name:
                continue
            key = (winner_id, loser_id, tour_id, str(game.get("round_id") or "").strip())
            dq = stat_map.get(key)
            if not dq:
                continue
            stat = dq.popleft()
            w_svpt = oncourt_service_points(stat, "w")
            l_svpt = oncourt_service_points(stat, "l")
            if w_svpt <= 0 or l_svpt <= 0:
                continue
            w_svgms = max(1.0, total_games / 2.0)
            l_svgms = max(1.0, total_games / 2.0)
            w_breaks_for = parse_int(stat.get("w_bpw"))
            l_breaks_for = parse_int(stat.get("l_bpw"))
            w = SideEvent(
                tour=tour,
                match_date=match_date,
                tour_id=tour_id,
                tournament=meta["name"],
                surface=meta["surface"],
                player_id=winner_id,
                player_name=winner_name,
                opponent_id=loser_id,
                aces=parse_int(stat.get("w_ace")),
                dfs=parse_int(stat.get("w_df")),
                svpt=w_svpt,
                svgms=w_svgms,
                first_in=parse_int(stat.get("w_fs")),
                first_won=parse_int(stat.get("w_w1s")),
                second_won=parse_int(stat.get("w_w2s")),
                opp_svpt=l_svpt,
                opp_first_in=parse_int(stat.get("l_fs")),
                opp_first_won=parse_int(stat.get("l_w1s")),
                opp_second_won=parse_int(stat.get("l_w2s")),
                breaks_for=w_breaks_for,
                broken=l_breaks_for,
                won=True,
            )
            l = SideEvent(
                tour=tour,
                match_date=match_date,
                tour_id=tour_id,
                tournament=meta["name"],
                surface=meta["surface"],
                player_id=loser_id,
                player_name=loser_name,
                opponent_id=winner_id,
                aces=parse_int(stat.get("l_ace")),
                dfs=parse_int(stat.get("l_df")),
                svpt=l_svpt,
                svgms=l_svgms,
                first_in=parse_int(stat.get("l_fs")),
                first_won=parse_int(stat.get("l_w1s")),
                second_won=parse_int(stat.get("l_w2s")),
                opp_svpt=w_svpt,
                opp_first_in=parse_int(stat.get("w_fs")),
                opp_first_won=parse_int(stat.get("w_w1s")),
                opp_second_won=parse_int(stat.get("w_w2s")),
                breaks_for=l_breaks_for,
                broken=w_breaks_for,
                won=False,
            )
            all_matches.append(
                MatchEvent(
                    tour=tour,
                    match_date=match_date,
                    year=match_date.year,
                    tour_id=tour_id,
                    tournament=meta["name"],
                    surface=meta["surface"],
                    round_id=str(game.get("round_id") or ""),
                    winner_id=winner_id,
                    winner_name=winner_name,
                    loser_id=loser_id,
                    loser_name=loser_name,
                    score=score,
                    total_games=total_games,
                    best_of=5 if tour == "atp" and meta["name"] in {"Australian Open", "Roland Garros", "Wimbledon", "US Open"} else 3,
                    first_set_tb=first_set_tb,
                    match_tb=match_tb,
                    w=w,
                    l=l,
                )
            )
    return sorted(all_matches, key=lambda m: (m.match_date, m.tour, m.tour_id, m.round_id, m.winner_id, m.loser_id))


def build_window_rows(player_events: list[SideEvent], as_of: date, surface: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for window, days in WINDOW_DAYS.items():
        totals = empty_side_totals()
        name = ""
        player_id = ""
        tour = ""
        for event in player_events:
            if event.match_date >= as_of or event.surface != surface:
                continue
            if (as_of - event.match_date).days > days:
                continue
            name = event.player_name
            player_id = event.player_id
            tour = event.tour
            add_side_totals(totals, event)
        if totals["matches"] > 0:
            rows[window] = side_totals_row(tour, player_id, name, surface, window, totals)
    return rows


def build_same_tournament_row(player_events: list[SideEvent], as_of: date, tour_id: str) -> dict[str, str]:
    totals = empty_side_totals()
    name = ""
    player_id = ""
    tour = ""
    surface = ""
    for event in player_events:
        if event.match_date >= as_of or event.tour_id != tour_id:
            continue
        name = event.player_name
        player_id = event.player_id
        tour = event.tour
        surface = event.surface
        add_side_totals(totals, event)
    if totals["matches"] <= 0:
        return {}
    return side_totals_row(tour, player_id, name, surface, "same_tournament", totals)


def build_factor_row(match: MatchEvent, prior_matches: list[MatchEvent]) -> dict[str, str]:
    event = empty_totals()
    surface = empty_totals()
    for prior in prior_matches:
        if prior.tour != match.tour or prior.surface != match.surface:
            continue
        add_match_totals(surface, prior)
        if prior.tournament == match.tournament:
            add_match_totals(event, prior)
    baseline = subtract_totals(surface, event)
    if event["matches"] <= 0:
        event = empty_totals()
        # Neutral low-sample event row, with match length inherited from surface.
        event["match_games"] = surface["match_games"]
        event["match_games_n"] = surface["match_games_n"]
        event["svpt"] = surface["svpt"]
        event["svgms"] = surface["svgms"]
    return factor_row_from_totals(match.tour, match.tournament, match.surface, event, baseline or surface)


def build_current_env_row(match: MatchEvent, prior_matches: list[MatchEvent], factor: dict[str, str]) -> dict[str, str]:
    current = [m for m in prior_matches if m.tour == match.tour and m.tour_id == match.tour_id]
    if not current:
        return {}
    totals = empty_totals()
    for prior in current:
        add_match_totals(totals, prior)
    matches = int(totals["matches"])
    svpt = totals["svpt"]
    if matches <= 0 or svpt <= 0:
        return {}
    weight = max(0.0, min(0.10, matches / 20.0 * 0.10))
    ace_rate = totals["aces"] / svpt
    df_rate = totals["dfs"] / svpt
    first_rate = totals["first_set_tiebreaks"] / matches
    match_rate = totals["match_tiebreaks"] / matches
    base_ace = parse_float(factor.get("ace_rate")) or parse_float(factor.get("tour_surface_baseline_ace"))
    base_df = parse_float(factor.get("df_rate")) or parse_float(factor.get("tour_surface_baseline_df"))
    base_first = parse_float(factor.get("first_set_tiebreak_rate")) or parse_float(factor.get("tour_surface_baseline_first_set_tiebreak"))
    base_match = parse_float(factor.get("match_tiebreak_rate")) or parse_float(factor.get("tour_surface_baseline_match_tiebreak"))
    return {
        "matches": str(matches),
        "svpt": str(int(svpt)),
        "weight": f"{weight:.3f}",
        "ace_factor": f"{ratio_factor(ace_rate, base_ace, weight, 0.94, 1.06):.4f}",
        "df_factor": f"{ratio_factor(df_rate, base_df, weight, 0.94, 1.06):.4f}",
        "break_factor": "1.0000",
        "first_set_tiebreak_factor": f"{ratio_factor(first_rate, base_first, weight, 0.90, 1.12):.4f}",
        "match_tiebreak_factor": f"{ratio_factor(match_rate, base_match, weight, 0.90, 1.12):.4f}",
    }


def naive_prob(factor: dict[str, str], field: str, fallback: float) -> float:
    value = parse_float(factor.get(field))
    if value is None:
        value = parse_float(factor.get(f"tour_surface_baseline_{field}"))
    return max(0.001, min(0.999, value if value is not None else fallback))


def evaluate(matches: list[MatchEvent], eval_years: set[int]) -> list[EvalRow]:
    events_by_player: dict[tuple[str, str], list[SideEvent]] = defaultdict(list)
    for match in matches:
        events_by_player[(match.tour, match.w.player_id)].append(match.w)
        events_by_player[(match.tour, match.l.player_id)].append(match.l)
    rows: list[EvalRow] = []
    prior_matches: list[MatchEvent] = []
    for match in matches:
        if match.year in eval_years:
            factor = build_factor_row(match, prior_matches)
            current_env = build_current_env_row(match, prior_matches, factor)
            expected_games = parse_float(factor.get("match_games_per_match"), 22.5) or 22.5
            w_proj = project_player(
                tour=match.tour,
                player_rows=build_window_rows(events_by_player[(match.tour, match.winner_id)], match.match_date, match.surface),
                opponent_rows=build_window_rows(events_by_player[(match.tour, match.loser_id)], match.match_date, match.surface),
                factor_row=factor,
                expected_match_games=expected_games,
                slam_matches=int(parse_float(factor.get("matches"), 0) or 0),
                same_tournament_row=build_same_tournament_row(events_by_player[(match.tour, match.winner_id)], match.match_date, match.tour_id),
                current_tournament_env_row=current_env,
            )
            l_proj = project_player(
                tour=match.tour,
                player_rows=build_window_rows(events_by_player[(match.tour, match.loser_id)], match.match_date, match.surface),
                opponent_rows=build_window_rows(events_by_player[(match.tour, match.winner_id)], match.match_date, match.surface),
                factor_row=factor,
                expected_match_games=expected_games,
                slam_matches=int(parse_float(factor.get("matches"), 0) or 0),
                same_tournament_row=build_same_tournament_row(events_by_player[(match.tour, match.loser_id)], match.match_date, match.tour_id),
                current_tournament_env_row=current_env,
            )
            confidence = "HIGH" if w_proj.tiebreak_confidence == "HIGH" and l_proj.tiebreak_confidence == "HIGH" else ("MED" if "MED" in {w_proj.tiebreak_confidence, l_proj.tiebreak_confidence} else "LOW")
            rows.append(
                EvalRow(
                    tour=match.tour.upper(),
                    year=match.year,
                    date=match.match_date,
                    tournament=match.tournament,
                    surface=match.surface,
                    best_of=match.best_of,
                    match=f"{match.winner_name} d. {match.loser_name}",
                    actual_first_set_tb=match.first_set_tb,
                    actual_match_tb=match.match_tb,
                    first_set_prob=(w_proj.first_set_tiebreak_prob + l_proj.first_set_tiebreak_prob) / 2.0,
                    match_prob=(w_proj.match_tiebreak_prob + l_proj.match_tiebreak_prob) / 2.0,
                    first_set_base_prob=(w_proj.first_set_tiebreak_base_prob + l_proj.first_set_tiebreak_base_prob) / 2.0,
                    match_base_prob=(w_proj.match_tiebreak_base_prob + l_proj.match_tiebreak_base_prob) / 2.0,
                    first_set_naive_prob=naive_prob(factor, "first_set_tiebreak_rate", 0.18),
                    match_naive_prob=naive_prob(factor, "match_tiebreak_rate", 0.36),
                    tiebreak_confidence=confidence,
                    venue_first_set_factor=parse_float(factor.get("first_set_tiebreak_factor"), 1.0) or 1.0,
                    venue_match_factor=parse_float(factor.get("match_tiebreak_factor"), 1.0) or 1.0,
                    current_first_set_factor=parse_float(current_env.get("first_set_tiebreak_factor"), 1.0) or 1.0,
                    current_match_factor=parse_float(current_env.get("match_tiebreak_factor"), 1.0) or 1.0,
                    venue_matches=parse_int(factor.get("matches")),
                    current_matches=parse_int(current_env.get("matches")),
                )
            )
        prior_matches.append(match)
    return rows


def brier(rows: list[EvalRow], prob_field: str, actual_field: str) -> float:
    if not rows:
        return float("nan")
    return mean((getattr(row, prob_field) - getattr(row, actual_field)) ** 2 for row in rows)


def logloss(rows: list[EvalRow], prob_field: str, actual_field: str) -> float:
    if not rows:
        return float("nan")
    total = 0.0
    for row in rows:
        p = max(1e-6, min(1.0 - 1e-6, getattr(row, prob_field)))
        y = getattr(row, actual_field)
        total += -y * math.log(p) - (1 - y) * math.log(1.0 - p)
    return total / len(rows)


def summary(rows: list[EvalRow]) -> dict[str, float]:
    return {
        "n": float(len(rows)),
        "first_actual": mean([r.actual_first_set_tb for r in rows]) if rows else float("nan"),
        "first_pred": mean([r.first_set_prob for r in rows]) if rows else float("nan"),
        "first_base": mean([r.first_set_base_prob for r in rows]) if rows else float("nan"),
        "first_naive": mean([r.first_set_naive_prob for r in rows]) if rows else float("nan"),
        "first_brier": brier(rows, "first_set_prob", "actual_first_set_tb"),
        "first_naive_brier": brier(rows, "first_set_naive_prob", "actual_first_set_tb"),
        "first_logloss": logloss(rows, "first_set_prob", "actual_first_set_tb"),
        "first_naive_logloss": logloss(rows, "first_set_naive_prob", "actual_first_set_tb"),
        "match_actual": mean([r.actual_match_tb for r in rows]) if rows else float("nan"),
        "match_pred": mean([r.match_prob for r in rows]) if rows else float("nan"),
        "match_base": mean([r.match_base_prob for r in rows]) if rows else float("nan"),
        "match_naive": mean([r.match_naive_prob for r in rows]) if rows else float("nan"),
        "match_brier": brier(rows, "match_prob", "actual_match_tb"),
        "match_naive_brier": brier(rows, "match_naive_prob", "actual_match_tb"),
        "match_logloss": logloss(rows, "match_prob", "actual_match_tb"),
        "match_naive_logloss": logloss(rows, "match_naive_prob", "actual_match_tb"),
    }


def reliability(rows: list[EvalRow], prob_field: str, actual_field: str, bins: int = 10) -> dict[str, object]:
    if not rows:
        return {"ece": float("nan"), "max_bin_gap": float("nan"), "bins": []}
    buckets: list[list[EvalRow]] = [[] for _ in range(bins)]
    for row in rows:
        prob = max(0.0, min(0.999999, getattr(row, prob_field)))
        buckets[min(bins - 1, int(prob * bins))].append(row)
    total = len(rows)
    ece = 0.0
    max_gap = 0.0
    out_bins = []
    for index, bucket in enumerate(buckets):
        if not bucket:
            continue
        pred = mean(getattr(row, prob_field) for row in bucket)
        actual = mean(getattr(row, actual_field) for row in bucket)
        gap = abs(pred - actual)
        ece += (len(bucket) / total) * gap
        max_gap = max(max_gap, gap)
        out_bins.append(
            {
                "bin": index,
                "low": index / bins,
                "high": (index + 1) / bins,
                "n": len(bucket),
                "pred": pred,
                "actual": actual,
                "gap": gap,
            }
        )
    return {"ece": ece, "max_bin_gap": max_gap, "bins": out_bins}


def tournament_drift(rows: list[EvalRow], prob_field: str, actual_field: str, min_n: int = 50) -> dict[str, object]:
    grouped: dict[tuple[str, str], list[EvalRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.tour, row.tournament)].append(row)
    items = []
    for (tour, tournament), bucket in sorted(grouped.items()):
        if len(bucket) < min_n:
            continue
        pred = mean(getattr(row, prob_field) for row in bucket)
        actual = mean(getattr(row, actual_field) for row in bucket)
        diff = pred - actual
        items.append(
            {
                "tour": tour,
                "tournament": tournament,
                "n": len(bucket),
                "pred": pred,
                "actual": actual,
                "diff": diff,
                "abs_diff": abs(diff),
            }
        )
    if not items:
        return {
            "n_tournaments": 0,
            "share_abs_gt_10pp": float("nan"),
            "mean_signed_error": float("nan"),
            "items": [],
        }
    return {
        "n_tournaments": len(items),
        "share_abs_gt_10pp": sum(1 for item in items if item["abs_diff"] > 0.10) / len(items),
        "mean_signed_error": mean(item["diff"] for item in items),
        "items": items,
    }


def tour_surface_sample_check(rows: list[EvalRow]) -> dict[str, object]:
    grouped: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        grouped[(row.tour, row.surface)] += 1
    cells = [
        {"tour": tour, "surface": surface, "n": n, "certifiable": n >= 300}
        for (tour, surface), n in sorted(grouped.items())
    ]
    return {"cells": cells, "all_cells_ge_300": all(cell["certifiable"] for cell in cells)}


def gate_market(rows: list[EvalRow], *, market: str) -> dict[str, object]:
    if market == "first_set":
        prob_field = "first_set_prob"
        naive_field = "first_set_naive_prob"
        actual_field = "actual_first_set_tb"
    elif market == "match":
        prob_field = "match_prob"
        naive_field = "match_naive_prob"
        actual_field = "actual_match_tb"
    else:
        raise ValueError(f"unknown market: {market}")

    n = len(rows)
    actual = mean(getattr(row, actual_field) for row in rows) if rows else float("nan")
    pred = mean(getattr(row, prob_field) for row in rows) if rows else float("nan")
    naive = mean(getattr(row, naive_field) for row in rows) if rows else float("nan")
    mean_error = pred - actual
    model_brier = brier(rows, prob_field, actual_field)
    naive_brier = brier(rows, naive_field, actual_field)
    model_logloss = logloss(rows, prob_field, actual_field)
    naive_logloss = logloss(rows, naive_field, actual_field)
    rel = reliability(rows, prob_field, actual_field)
    drift = tournament_drift(rows, prob_field, actual_field)
    samples = tour_surface_sample_check(rows)
    brier_skill = 1.0 - (model_brier / naive_brier) if naive_brier and math.isfinite(naive_brier) else float("nan")

    checks = {
        "overall_sample_ge_1000": n >= 1000,
        "mean_error_abs_le_1pp": abs(mean_error) <= 0.01,
        "ece_le_1_5pp": bool(rel["ece"] <= 0.015),
        "max_bin_gap_le_3pp": bool(rel["max_bin_gap"] <= 0.03),
        "brier_beats_naive_by_0_002": model_brier <= naive_brier - 0.002,
        "brier_skill_ge_1pct": brier_skill >= 0.01,
        "logloss_beats_naive_by_0_003": model_logloss <= naive_logloss - 0.003,
        "tournament_abs10_share_lt_20pct": bool(
            math.isfinite(drift["share_abs_gt_10pp"]) and drift["share_abs_gt_10pp"] < 0.20
        ),
        "tournament_signed_error_abs_le_2pp": bool(
            math.isfinite(drift["mean_signed_error"]) and abs(drift["mean_signed_error"]) <= 0.02
        ),
    }
    return {
        "market": market,
        "pass": all(checks.values()),
        "checks": checks,
        "metrics": {
            "n": n,
            "actual": actual,
            "pred": pred,
            "naive": naive,
            "mean_error": mean_error,
            "brier": model_brier,
            "naive_brier": naive_brier,
            "brier_skill": brier_skill,
            "logloss": model_logloss,
            "naive_logloss": naive_logloss,
            "ece": rel["ece"],
            "max_bin_gap": rel["max_bin_gap"],
        },
        "reliability": rel,
        "tournament_drift": drift,
        "tour_surface_samples": samples,
    }


def _jsonable(value: object) -> object:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _clip_prob(prob: float) -> float:
    return max(0.001, min(0.999, prob))


def _logit(prob: float) -> float:
    p = _clip_prob(prob)
    return math.log(p / (1.0 - p))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def fit_platt(rows: list[EvalRow], prob_field: str, actual_field: str) -> dict[str, object] | None:
    if len(rows) < 100:
        return None
    xs = [_logit(getattr(row, prob_field)) for row in rows]
    ys = [float(getattr(row, actual_field)) for row in rows]
    a = 1.0
    b = 0.0
    ridge = 0.01
    for _ in range(50):
        g_a = ridge * (a - 1.0)
        g_b = ridge * b
        h_aa = ridge
        h_ab = 0.0
        h_bb = ridge
        for x, y in zip(xs, ys):
            pred = _sigmoid(a * x + b)
            diff = pred - y
            w = pred * (1.0 - pred)
            g_a += diff * x
            g_b += diff
            h_aa += w * x * x
            h_ab += w * x
            h_bb += w
        det = h_aa * h_bb - h_ab * h_ab
        if abs(det) < 1e-9:
            break
        delta_a = (g_a * h_bb - g_b * h_ab) / det
        delta_b = (h_aa * g_b - h_ab * g_a) / det
        delta_a = max(-0.35, min(0.35, delta_a))
        delta_b = max(-0.35, min(0.35, delta_b))
        a -= delta_a
        b -= delta_b
        a = max(0.10, min(3.00, a))
        b = max(-4.00, min(4.00, b))
        if abs(delta_a) + abs(delta_b) < 1e-6:
            break
    raw_pred = mean(getattr(row, prob_field) for row in rows)
    cal_pred = mean(_sigmoid(a * _logit(getattr(row, prob_field)) + b) for row in rows)
    actual = mean(getattr(row, actual_field) for row in rows)
    return {
        "a": a,
        "b": b,
        "n": len(rows),
        "actual": actual,
        "raw_pred": raw_pred,
        "calibrated_pred": cal_pred,
    }


def _calibration_key(market: str, tour: str, surface: str, bo_key: str) -> str:
    return f"{market}|{tour}|{surface}|{bo_key}"


def fit_tiebreak_calibration(rows: list[EvalRow], fit_years: list[int]) -> dict[str, object]:
    keys: dict[str, dict[str, object]] = {}

    def add_key(key: str, subset: list[EvalRow], prob_field: str, actual_field: str, *, min_n: int) -> None:
        if len(subset) < min_n:
            return
        fitted = fit_platt(subset, prob_field, actual_field)
        if fitted:
            keys[key] = fitted

    for market, prob_field, actual_field in (
        ("first_set", "first_set_prob", "actual_first_set_tb"),
        ("match", "match_prob", "actual_match_tb"),
    ):
        add_key(_calibration_key(market, "ALL", "ALL", "ALL"), rows, prob_field, actual_field, min_n=300)
        tours = sorted({row.tour for row in rows})
        for tour in tours:
            tour_rows = [row for row in rows if row.tour == tour]
            add_key(_calibration_key(market, tour, "ALL", "ALL"), tour_rows, prob_field, actual_field, min_n=300)
            if market == "match":
                for best_of in sorted({row.best_of for row in tour_rows}):
                    bo_rows = [row for row in tour_rows if row.best_of == best_of]
                    add_key(_calibration_key(market, tour, "ALL", f"BO{best_of}"), bo_rows, prob_field, actual_field, min_n=300)
            for surface in sorted({row.surface for row in tour_rows}):
                surface_rows = [row for row in tour_rows if row.surface == surface]
                add_key(_calibration_key(market, tour, surface, "ALL"), surface_rows, prob_field, actual_field, min_n=300)
                if market == "match":
                    for best_of in sorted({row.best_of for row in surface_rows}):
                        bo_rows = [row for row in surface_rows if row.best_of == best_of]
                        add_key(_calibration_key(market, tour, surface, f"BO{best_of}"), bo_rows, prob_field, actual_field, min_n=300)

    return {
        "version": 1,
        "method": "platt_logit",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "fit_years": fit_years,
        "keys": keys,
    }


def write_calibration_json(path: Path, calibration: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(calibration), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_gate_json(path: Path, rows: list[EvalRow], eval_years: list[int]) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    first_gate = gate_market(rows, market="first_set")
    match_gate = gate_market(rows, market="match")
    probability_gate_pass = bool(first_gate["pass"] and match_gate["pass"])
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "eval_years": eval_years,
        "fit_years": f"<={min(eval_years) - 1}" if eval_years else "",
        "status": "FAIL",
        "probability_gate_pass": probability_gate_pass,
        "market_gate_pass": False,
        "recommendations_allowed": False,
        "reason": (
            "probability_gate_failed"
            if not probability_gate_pass
            else "market_gate_failed_no_automated_price_feed_or_clv"
        ),
        "constraints": {
            "no_manual_csv_workflow": True,
            "needs_automated_market_price": True,
            "needs_200_settled_shadow_clv_positive": True,
            "current_odds_feed_has_tiebreak_markets": False,
        },
        "gates": {
            "first_set": first_gate,
            "match": match_gate,
        },
    }
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def group_rows(rows: list[EvalRow], key_fn) -> list[tuple[str, dict[str, float]]]:
    grouped: dict[str, list[EvalRow]] = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(row)
    return [(key, summary(grouped[key])) for key in sorted(grouped)]


def fmt_num(value: float, digits: int = 3) -> str:
    return "n/a" if math.isnan(value) else f"{value:.{digits}f}"


def write_rows(path: Path, rows: list[EvalRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "tour",
        "year",
        "date",
        "tournament",
        "surface",
        "best_of",
        "match",
        "actual_first_set_tb",
        "actual_match_tb",
        "first_set_prob",
        "match_prob",
        "first_set_base_prob",
        "match_base_prob",
        "first_set_naive_prob",
        "match_naive_prob",
        "tiebreak_confidence",
        "venue_first_set_factor",
        "venue_match_factor",
        "current_first_set_factor",
        "current_match_factor",
        "venue_matches",
        "current_matches",
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
                    "surface": row.surface,
                    "best_of": row.best_of,
                    "match": row.match,
                    "actual_first_set_tb": row.actual_first_set_tb,
                    "actual_match_tb": row.actual_match_tb,
                    "first_set_prob": f"{row.first_set_prob:.6f}",
                    "match_prob": f"{row.match_prob:.6f}",
                    "first_set_base_prob": f"{row.first_set_base_prob:.6f}",
                    "match_base_prob": f"{row.match_base_prob:.6f}",
                    "first_set_naive_prob": f"{row.first_set_naive_prob:.6f}",
                    "match_naive_prob": f"{row.match_naive_prob:.6f}",
                    "tiebreak_confidence": row.tiebreak_confidence,
                    "venue_first_set_factor": f"{row.venue_first_set_factor:.4f}",
                    "venue_match_factor": f"{row.venue_match_factor:.4f}",
                    "current_first_set_factor": f"{row.current_first_set_factor:.4f}",
                    "current_match_factor": f"{row.current_match_factor:.4f}",
                    "venue_matches": row.venue_matches,
                    "current_matches": row.current_matches,
                }
            )


def write_report(path: Path, rows: list[EvalRow], eval_years: list[int], gate: dict[str, object] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("Tennis Tie-Break Stage-0 Calibration Audit")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Evaluation years: {', '.join(map(str, eval_years))}")
    lines.append("Outcome-only validation. No odds, no ROI, no CLV.")
    lines.append("Model probabilities use serve/return strength plus past-only venue factors and past-only same-event bumps.")
    lines.append("Naive benchmark = past tournament tie-break rate, falling back to tour-surface rate.")
    lines.append("")

    def section(title: str, items: list[tuple[str, dict[str, float]]], min_n: int = 1) -> None:
        lines.append(title)
        lines.append("Bucket                         N  1st actual/pred/naive  1st Brier m/n  Match actual/pred/naive  Match Brier m/n")
        for key, s in items:
            if int(s["n"]) < min_n:
                continue
            lines.append(
                f"{key[:28]:28s} {int(s['n']):4d}  "
                f"{fmt_num(s['first_actual'])}/{fmt_num(s['first_pred'])}/{fmt_num(s['first_naive'])}        "
                f"{fmt_num(s['first_brier'])}/{fmt_num(s['first_naive_brier'])}        "
                f"{fmt_num(s['match_actual'])}/{fmt_num(s['match_pred'])}/{fmt_num(s['match_naive'])}        "
                f"{fmt_num(s['match_brier'])}/{fmt_num(s['match_naive_brier'])}"
            )
        lines.append("")

    section("Overall", [("all", summary(rows))])
    section("By tour", group_rows(rows, lambda r: r.tour))
    section("By surface", group_rows(rows, lambda r: f"{r.tour} {r.surface}"))
    section("By year", group_rows(rows, lambda r: str(r.year)))
    section("By confidence", group_rows(rows, lambda r: r.tiebreak_confidence))
    section("By tournament (n>=25)", group_rows(rows, lambda r: f"{r.tour} {r.tournament}"), min_n=25)

    overall = summary(rows)
    lines.append("Verdict")
    first_ok = overall["first_brier"] <= overall["first_naive_brier"] and abs(overall["first_pred"] - overall["first_actual"]) <= 0.03
    match_ok = overall["match_brier"] <= overall["match_naive_brier"] and abs(overall["match_pred"] - overall["match_actual"]) <= 0.04
    lines.append(f"- First-set TB calibration: {'PASS research gate' if first_ok else 'FAIL/needs recalibration'}")
    lines.append(f"- Match TB calibration: {'PASS research gate' if match_ok else 'FAIL/needs recalibration'}")
    if gate:
        lines.append("")
        lines.append("Strict betting-readiness gate")
        lines.append(f"- Probability gate: {'PASS' if gate.get('probability_gate_pass') else 'FAIL'}")
        lines.append(f"- Market/CLV gate: {'PASS' if gate.get('market_gate_pass') else 'FAIL'}")
        lines.append(f"- Recommendations allowed: {'YES' if gate.get('recommendations_allowed') else 'NO'}")
        lines.append(f"- Gate reason: {gate.get('reason')}")
        for market_key in ("first_set", "match"):
            market_gate = ((gate.get("gates") or {}) if isinstance(gate.get("gates"), dict) else {}).get(market_key)
            if not isinstance(market_gate, dict):
                continue
            metrics = market_gate.get("metrics") if isinstance(market_gate.get("metrics"), dict) else {}
            checks = market_gate.get("checks") if isinstance(market_gate.get("checks"), dict) else {}
            failed = [key for key, ok in checks.items() if not ok]
            lines.append(
                f"- {market_key}: {'PASS' if market_gate.get('pass') else 'FAIL'}; "
                f"n={metrics.get('n')}; "
                f"mean_error={fmt_num(float(metrics.get('mean_error') or float('nan')), 4)}; "
                f"brier={fmt_num(float(metrics.get('brier') or float('nan')), 4)} vs naive {fmt_num(float(metrics.get('naive_brier') or float('nan')), 4)}; "
                f"logloss={fmt_num(float(metrics.get('logloss') or float('nan')), 4)} vs naive {fmt_num(float(metrics.get('naive_logloss') or float('nan')), 4)}; "
                f"ece={fmt_num(float(metrics.get('ece') or float('nan')), 4)}; "
                f"failed={','.join(failed) if failed else 'none'}"
            )
    lines.append("- Do not turn this into betting recommendations until Bet365 line capture exists and settled CLV/ROI are tracked.")
    lines.append("- If model Brier does not beat naive, venue/team/player factors are not adding useful signal yet.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest tennis tie-break probabilities on OnCourt history.")
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--eval-years", nargs="+", type=int, default=[2024, 2025, 2026])
    parser.add_argument("--out-txt", type=Path, default=DEFAULT_OUT_TXT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--gate-json", type=Path, default=DEFAULT_GATE_JSON)
    parser.add_argument("--calibration-json", type=Path, default=DEFAULT_CALIBRATION_JSON)
    parser.add_argument("--fit-years", nargs="+", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matches = load_events(args.start_year, args.end_year)
    fit_years = args.fit_years
    if fit_years is None:
        first_eval_year = min(args.eval_years)
        fit_years = [year for year in range(args.start_year, first_eval_year) if year <= args.end_year]
    if not fit_years:
        raise SystemExit("No calibration fit years available. Pass --fit-years or lower --start-year.")
    set_tiebreak_calibration_override({})
    fit_rows = evaluate(matches, set(fit_years))
    if not fit_rows:
        raise SystemExit("No tie-break calibration rows generated.")
    calibration = fit_tiebreak_calibration(fit_rows, fit_years)
    write_calibration_json(args.calibration_json, calibration)
    set_tiebreak_calibration_override(calibration)
    rows = evaluate(matches, set(args.eval_years))
    if not rows:
        raise SystemExit("No tie-break backtest rows generated.")
    write_rows(args.out_csv, rows)
    gate = write_gate_json(args.gate_json, rows, args.eval_years)
    write_report(args.out_txt, rows, args.eval_years, gate)
    print(f"Wrote {args.out_txt}")
    print(f"Wrote {args.out_csv}")
    print(f"Wrote {args.gate_json}")
    print(f"Wrote {args.calibration_json}")
    if not gate.get("recommendations_allowed"):
        print(f"TB recommendations blocked: {gate.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
