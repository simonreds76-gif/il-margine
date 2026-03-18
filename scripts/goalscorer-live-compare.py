#!/usr/bin/env python3
"""
Compare live or future ATGS odds against a pre-match goalscorer model projection.

Unlike `goalscorer-compare-odds.py`, this does not rely on settled historical
model rows. It rebuilds player/team histories from the historical logs, then
prices each odds row using only data available before that match date.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import runpy
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Dict, Iterable, List

import requests

from goalscorer_penalty_utils import best_name_match, load_penalty_hierarchy, penalty_transfer_info


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ["data/goalscorer/serie-a-player-match-logs-*.csv"]
DEFAULT_ODDS = "data/goalscorer/goalscorer-odds-history.csv"
DEFAULT_OUT_DIR = "data/goalscorer"
DEFAULT_PENALTY_HIERARCHY = "data/goalscorer/serie-a-penalty-takers.json"
UNDERSTAT_LEAGUE_URL = "https://understat.com/getLeagueData/{league_slug}/{season_start}"
UNDERSTAT_LEAGUE_SLUGS = {
    "serie-a": "Serie_A",
    "epl": "EPL",
    "la-liga": "La_liga",
    "bundesliga": "Bundesliga",
    "ligue-1": "Ligue_1",
}

LEAGUE_COMPETITION_VARIANTS = {
    "serie-a": {"italy serie a", "serie a"},
    "epl": {"england premier league", "premier league"},
    "la-liga": {"spain la liga", "la liga"},
    "bundesliga": {"germany bundesliga", "bundesliga"},
    "ligue-1": {"france ligue 1", "ligue 1", "ligue 1 mcdonalds"},
}
MIN_PUBLIC_HISTORY_MINUTES = 500.0
CONFIRMED_STARTER_MINUTES = 85.0
CONFIRMED_BENCH_MINUTES = 14.0
STACKED_RECENT_WINDOW = 8
STACKED_FIXTURE_WINDOW = 3
USUAL_POSITION_WINDOW = 10
USUAL_POSITION_SHARE_MIN = 0.80
PUBLIC_ATTACKING_POSITIONS = {"FW", "FWR", "FWL", "AMC", "AMR", "AML"}
PUBLIC_MIDFIELD_EXCEPTIONS = {"MC", "ML", "MR", "DMC"}
PUBLIC_MAX_FAIR_ODDS = 10.0
PUBLIC_EXCEPTION_MAX_FAIR_ODDS = 14.0
PUBLIC_MIN_EXPECTED_MINUTES = 65.0
PUBLIC_MIN_NPXG90_ATTACK = 0.12
PUBLIC_MIN_NPXG90_EXCEPTION = 0.20

POSITION_SCORES = {
    "GK": 0,
    "DC": 1,
    "DL": 1,
    "DR": 1,
    "DML": 2,
    "DMR": 2,
    "DMC": 2,
    "MC": 3,
    "ML": 3,
    "MR": 3,
    "AMC": 4,
    "AML": 4,
    "AMR": 4,
    "FW": 5,
    "FWL": 5,
    "FWR": 5,
}

POSITION_GROUP_LABELS = {
    0: "GK",
    1: "DEF",
    2: "DMC",
    3: "MID",
    4: "AM",
    5: "FW",
}

# Fallback defaults before the live compare syncs the full model config in main().
LEAGUE_AVG = {
    "team_xga_per_match": 1.30,
    "penalty_conversion": 0.77,
}


def _norm_text(value: str) -> str:
    normalized = html.unescape((value or "").strip().lower())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_float(value: str, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _coarse_position_text(position: str) -> str:
    return (position or "").split(",")[0].strip()


def _np_goals(goals: int, penalties_scored: int) -> int:
    return max(int(goals or 0) - int(penalties_scored or 0), 0)


def _player_match_score(query_key: str, candidate_key: str) -> int:
    if not query_key or not candidate_key:
        return 0
    if query_key == candidate_key:
        return 100

    q_tokens = query_key.split()
    c_tokens = candidate_key.split()
    if not q_tokens or not c_tokens:
        return 0

    q_first = q_tokens[0]
    q_last = q_tokens[-1]
    c_first = c_tokens[0]
    c_last = c_tokens[-1]

    if q_last == c_last:
        if q_first == c_first:
            return 95
        if q_first.startswith(c_first) or c_first.startswith(q_first):
            return 90
        return 80

    if len(c_tokens) == 1 and c_tokens[0] in q_tokens:
        return 72
    if len(q_tokens) == 1 and q_tokens[0] in c_tokens:
        return 72
    if candidate_key in query_key or query_key in candidate_key:
        return 74

    overlap = len(set(q_tokens) & set(c_tokens))
    if overlap >= 2:
        return 65
    return 0


def _fixture_season_start(match_date_str: str) -> str:
    match_date = datetime.strptime(match_date_str[:10], "%Y-%m-%d").date()
    return str(match_date.year if match_date.month >= 7 else match_date.year - 1)


def _load_understat_rosters(
    season_starts: Iterable[str],
    team_key_func,
    league_slug: str,
) -> tuple[Dict[str, List[dict]], Dict[str, List[dict]]]:
    roster_by_player_key: Dict[str, List[dict]] = defaultdict(list)
    roster_by_team_key: Dict[str, List[dict]] = defaultdict(list)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
    }

    for season_start in sorted(set(season_starts)):
        if not season_start:
            continue
        try:
            response = requests.get(
                UNDERSTAT_LEAGUE_URL.format(league_slug=league_slug, season_start=season_start),
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            print(f"  Warning: failed to load Understat roster for {season_start}: {exc}")
            continue

        for player in payload.get("players", []):
            player_name = str(player.get("player_name") or "").strip()
            player_key = _norm_text(player_name)
            if not player_key:
                continue

            team_keys: List[str] = []
            for team_name in str(player.get("team_title") or "").split(","):
                team_key = team_key_func(team_name.strip())
                if team_key and team_key not in team_keys:
                    team_keys.append(team_key)
            if not team_keys:
                continue

            entry = {
                "player_id": str(player.get("id") or ""),
                "player_name": player_name,
                "player_key": player_key,
                "team": str(player.get("team_title") or "").strip(),
                "team_key": team_keys[-1],
                "team_keys": team_keys,
                "position": str(player.get("position") or "").strip(),
                "match_date": f"{season_start}-07-01",
                "games": _parse_float(player.get("games"), 0.0),
                "minutes": _parse_float(player.get("time"), 0.0),
                "source": "live_roster",
            }
            roster_by_player_key[player_key].append(entry)
            for team_key in team_keys:
                roster_by_team_key[team_key].append(entry)

    return roster_by_player_key, roster_by_team_key


def _resolve_player_meta(
    odds_player_name: str,
    home_key: str,
    away_key: str,
    latest_player_meta: Dict[str, dict],
    players_by_team_key: Dict[str, List[dict]],
    roster_by_player_key: Dict[str, List[dict]],
    roster_by_team_key: Dict[str, List[dict]],
) -> dict | None:
    query_key = _norm_text(odds_player_name)
    exact = latest_player_meta.get(query_key)
    if exact is not None and exact["team_key"] in {home_key, away_key}:
        return exact

    def best_candidate(candidates: List[dict], sort_field: str) -> dict | None:
        scored = []
        for candidate in candidates:
            score = _player_match_score(query_key, candidate["player_key"])
            if score > 0:
                scored.append((score, candidate.get(sort_field, ""), candidate))

        if not scored:
            return None

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, _, best_candidate = scored[0]
        if len(scored) > 1 and scored[1][0] == best_score and scored[1][2]["player_key"] != best_candidate["player_key"]:
            return None
        if best_score >= 68:
            return best_candidate
        return None

    history_candidates = players_by_team_key.get(home_key, []) + players_by_team_key.get(away_key, [])
    best_history = best_candidate(history_candidates, "match_date")
    if best_history is not None:
        return best_history

    roster_exact = [
        candidate
        for candidate in roster_by_player_key.get(query_key, [])
        if home_key in candidate["team_keys"] or away_key in candidate["team_keys"]
    ]
    if len(roster_exact) == 1:
        return roster_exact[0]

    roster_candidates = roster_by_team_key.get(home_key, []) + roster_by_team_key.get(away_key, [])
    best_roster = best_candidate(roster_candidates, "minutes")
    if best_roster is not None:
        return best_roster

    return exact


def _load_csv(path: str) -> List[dict]:
    if not os.path.exists(path):
        raise SystemExit(f"File not found: {path}")
    with open(path, "r", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_odds_rows(path: str, bookmaker_filter: str = "", league: str = "serie-a") -> List[dict]:
    rows = _load_csv(path)
    bookmaker_norm = _norm_text(bookmaker_filter) if bookmaker_filter else ""
    league_variants = LEAGUE_COMPETITION_VARIANTS.get(league, set())
    loaded: List[dict] = []
    for row in rows:
        bookmaker = (row.get("bookmaker") or "").strip()
        if bookmaker_norm and _norm_text(bookmaker) != bookmaker_norm:
            continue
        market = (row.get("market") or "").strip().upper()
        if market and market != "ATGS":
            continue
        match_date = (row.get("match_date") or "").strip()
        home_team = (row.get("home_team") or "").strip()
        away_team = (row.get("away_team") or "").strip()
        player_name = (row.get("player_name") or "").strip()
        competition = (row.get("competition") or "").strip()
        if league_variants and _norm_text(competition) not in league_variants:
            continue
        if not match_date or not home_team or not away_team or not player_name:
            continue
        loaded.append(
            {
                "captured_at": (row.get("captured_at") or "").strip(),
                "match_date": match_date,
                "bookmaker": bookmaker,
                "competition": competition,
                "home_team": home_team,
                "away_team": away_team,
                "player_name": player_name,
                "player_key": _norm_text(player_name),
                "player_team": (row.get("player_team") or "").strip(),
                "odds_decimal": _parse_float(row.get("odds_decimal")),
                "implied_prob": _parse_float(row.get("implied_prob")),
                "source": (row.get("source") or "").strip(),
                "notes": (row.get("notes") or "").strip(),
            }
        )
    loaded.sort(key=lambda row: (row["match_date"], row["captured_at"], row["bookmaker"], row["player_name"]))
    return loaded


def latest_rows_per_market(rows: List[dict]) -> List[dict]:
    latest: Dict[tuple[str, str, str, str, str], dict] = {}
    for row in rows:
        key = (
            row["match_date"],
            row["bookmaker"],
            row["player_key"],
            _norm_text(row["home_team"]),
            _norm_text(row["away_team"]),
        )
        current = latest.get(key)
        if current is None or row["captured_at"] > current["captured_at"]:
            latest[key] = row
    return sorted(latest.values(), key=lambda row: (row["match_date"], row["bookmaker"], row["player_name"]))


def _classify_confidence(
    resolver_source: str,
    method: str,
    history_minutes: float,
    ev: float,
    min_ev: float,
    lineup_state: str,
) -> tuple[str, str, str]:
    reasons: List[str] = []

    if lineup_state == "not_in_squad":
        reasons.append("not_in_squad")
        return "low", "suppress", ",".join(reasons)

    if lineup_state == "bench":
        reasons.append("confirmed_bench")
        return "low", "suppress", ",".join(reasons)

    if method != "model":
        reasons.append("fallback_method")
        return "low", "suppress", ",".join(reasons)

    if history_minutes < MIN_PUBLIC_HISTORY_MINUTES:
        reasons.append("history_lt_500")
        return "low", "suppress", ",".join(reasons)

    if resolver_source == "live_roster":
        reasons.append("live_roster_resolver")
        action = "surface_with_caveat" if ev >= min_ev else "monitor"
        if lineup_state == "starter":
            reasons.append("confirmed_starter")
        return "medium", action, ",".join(reasons)

    reasons.append("history_resolver")
    if lineup_state == "starter":
        reasons.append("confirmed_starter")
    action = "surface" if ev >= min_ev else "monitor"
    return "high", action, ",".join(reasons)


def _public_publish_gate(
    position: str,
    fair_odds: float,
    expected_minutes: float,
    recent_npxg_per90: float,
    penalty_transfer: bool,
    penalty_share: float,
    position_upgrade: bool,
) -> str:
    coarse_position = _coarse_position_text(position)

    if expected_minutes < PUBLIC_MIN_EXPECTED_MINUTES:
        return "minutes_lt_65"

    if coarse_position in PUBLIC_ATTACKING_POSITIONS:
        if fair_odds <= PUBLIC_MAX_FAIR_ODDS and recent_npxg_per90 >= PUBLIC_MIN_NPXG90_ATTACK:
            return ""
        if (
            fair_odds <= PUBLIC_EXCEPTION_MAX_FAIR_ODDS
            and (penalty_transfer or position_upgrade or recent_npxg_per90 >= PUBLIC_MIN_NPXG90_EXCEPTION)
        ):
            return ""
        return "attacker_profile_too_thin"

    if coarse_position in PUBLIC_MIDFIELD_EXCEPTIONS:
        if penalty_transfer or penalty_share >= 0.18 or position_upgrade:
            if fair_odds <= PUBLIC_EXCEPTION_MAX_FAIR_ODDS and recent_npxg_per90 >= PUBLIC_MIN_NPXG90_EXCEPTION:
                return ""
            return "midfielder_profile_too_thin"
        return "non_attacking_role"

    return "defensive_role"


def _stacked_signal_features(player_history, opponent_summary: dict | None) -> dict:
    history_rows = list(player_history.matches)
    recent = history_rows[-STACKED_RECENT_WINDOW:]
    recent_minutes = float(sum(match.get("minutes", 0.0) or 0.0 for match in recent))
    recent_npxg = float(sum(match.get("npxg", 0.0) or 0.0 for match in recent))
    recent_np_goals = float(sum(match.get("np_goals", 0.0) or 0.0 for match in recent))
    recent_npxg_per90 = (recent_npxg / (recent_minutes / 90.0)) if recent_minutes > 0 else 0.0
    finishing_luck = recent_np_goals - recent_npxg

    last_fixture_block = history_rows[-STACKED_FIXTURE_WINDOW:]
    last_fixture_xga = [match.get("opp_xga_pre") for match in last_fixture_block if match.get("opp_xga_pre") is not None]
    last_fixture_avg_xga = (sum(last_fixture_xga) / len(last_fixture_xga)) if last_fixture_xga else None
    next_opponent_xga = (
        opponent_summary["xga_per_match"]
        if opponent_summary is not None
        else LEAGUE_AVG["team_xga_per_match"]
    )
    fixture_swing = (
        next_opponent_xga / last_fixture_avg_xga
        if last_fixture_avg_xga and last_fixture_avg_xga > 0
        else None
    )

    return {
        "recent_matches_8": len(recent),
        "recent_npxg_8": recent_npxg,
        "recent_np_goals_8": recent_np_goals,
        "recent_npxg_per90_8": recent_npxg_per90,
        "finishing_luck_8": finishing_luck,
        "last_fixture_avg_xga_3": last_fixture_avg_xga,
        "next_opponent_xga": next_opponent_xga,
        "fixture_swing_3": fixture_swing,
    }


def _write_csv(path: str, rows: List[dict]) -> None:
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["no_rows"])


def _coerce_lineup_names(values) -> List[str]:
    if not isinstance(values, list):
        return []

    names: List[str] = []
    for item in values:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(
                item.get("name")
                or item.get("player_name")
                or item.get("player")
                or item.get("title")
                or ""
            ).strip()
        else:
            name = ""
        if name:
            names.append(name)
    return names


def _coerce_starter_entries(values) -> List[dict]:
    if not isinstance(values, list):
        return []

    entries: List[dict] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("player_name") or item.get("player") or "").strip()
        if not name:
            continue
        entries.append(
            {
                "name": name,
                "line_index": int(item.get("line_index", -1) or -1),
                "line_size": int(item.get("line_size", 0) or 0),
                "role_score": int(item.get("role_score", 0) or 0),
                "role_group": str(item.get("role_group") or "").strip(),
                "formation": str(item.get("formation") or "").strip(),
                "position_id": item.get("position_id", ""),
            }
        )
    return entries


def load_confirmed_lineup_map(path: str, team_key_func) -> Dict[tuple[str, str, str], dict]:
    if not path:
        return {}
    if not os.path.exists(path):
        raise SystemExit(f"Lineup file not found: {path}")

    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    fixtures = payload if isinstance(payload, list) else payload.get("fixtures", [])
    loaded: Dict[tuple[str, str, str], dict] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue

        home_team = str(fixture.get("home_team") or fixture.get("homeTeam") or "").strip()
        away_team = str(fixture.get("away_team") or fixture.get("awayTeam") or "").strip()
        if not home_team or not away_team:
            continue

        match_date = str(fixture.get("match_date") or fixture.get("matchDate") or "").strip()
        home_players = _coerce_lineup_names(
            fixture.get("home_players")
            or fixture.get("home_lineup")
            or fixture.get("confirmed_home")
            or fixture.get("home")
            or []
        )
        away_players = _coerce_lineup_names(
            fixture.get("away_players")
            or fixture.get("away_lineup")
            or fixture.get("confirmed_away")
            or fixture.get("away")
            or []
        )
        if not home_players and not away_players:
            continue

        key = (match_date, team_key_func(home_team), team_key_func(away_team))
        loaded[key] = {
            "match_date": match_date,
            "home_team": home_team,
            "away_team": away_team,
            "lineup_type": str(fixture.get("lineup_type") or fixture.get("lineupType") or "").strip(),
            "home_formation": str(fixture.get("home_formation") or fixture.get("homeFormation") or "").strip(),
            "away_formation": str(fixture.get("away_formation") or fixture.get("awayFormation") or "").strip(),
            "home_players": home_players,
            "away_players": away_players,
            "home_starters": _coerce_starter_entries(fixture.get("home_starters") or fixture.get("homeStarters") or []),
            "away_starters": _coerce_starter_entries(fixture.get("away_starters") or fixture.get("awayStarters") or []),
            "home_subs": _coerce_lineup_names(fixture.get("home_subs") or fixture.get("homeSubs") or []),
            "away_subs": _coerce_lineup_names(fixture.get("away_subs") or fixture.get("awaySubs") or []),
            "home_unavailable": _coerce_lineup_names(fixture.get("home_unavailable") or fixture.get("homeUnavailable") or []),
            "away_unavailable": _coerce_lineup_names(fixture.get("away_unavailable") or fixture.get("awayUnavailable") or []),
            "home_status": str(fixture.get("home_status") or fixture.get("status") or "Confirmed Lineup").strip(),
            "away_status": str(fixture.get("away_status") or fixture.get("status") or "Confirmed Lineup").strip(),
        }
        if match_date:
            loaded.setdefault(("", team_key_func(home_team), team_key_func(away_team)), loaded[key])
    return loaded


def _lineup_match_name(player_name: str, names: List[str]) -> str:
    return best_name_match(player_name, names) or ""


def _resolve_lineup_state(player_name: str, fixture_lineup: dict | None, is_home: bool) -> tuple[str, str]:
    if fixture_lineup is None:
        return "unknown", ""

    starter_names = fixture_lineup.get("home_players" if is_home else "away_players", [])
    bench_names = fixture_lineup.get("home_subs" if is_home else "away_subs", [])
    unavailable_names = fixture_lineup.get("home_unavailable" if is_home else "away_unavailable", [])

    starter_match = _lineup_match_name(player_name, starter_names)
    if starter_match:
        return "starter", starter_match

    bench_match = _lineup_match_name(player_name, bench_names)
    if bench_match:
        return "bench", bench_match

    unavailable_match = _lineup_match_name(player_name, unavailable_names)
    if unavailable_match:
        return "not_in_squad", unavailable_match

    return "not_in_squad", ""


def _resolve_starter_entry(player_name: str, fixture_lineup: dict | None, is_home: bool) -> dict | None:
    if fixture_lineup is None:
        return None
    starter_entries = fixture_lineup.get("home_starters" if is_home else "away_starters", [])
    if not starter_entries:
        return None
    matched_name = _lineup_match_name(player_name, [entry.get("name", "") for entry in starter_entries])
    if not matched_name:
        return None
    for entry in starter_entries:
        if entry.get("name") == matched_name:
            return entry
    return None


def _usual_position_summary(player_history) -> dict:
    recent = list(player_history.matches)[-USUAL_POSITION_WINDOW:]
    valid_positions = []
    for match in recent:
        position = _coarse_position_text(match.get("position", ""))
        score = POSITION_SCORES.get(position)
        if score is None:
            continue
        valid_positions.append((position, score))

    if not valid_positions:
        return {
            "usual_position": "",
            "usual_position_score": None,
            "usual_position_share": 0.0,
            "usual_position_matches": 0,
        }

    counts: Dict[str, int] = defaultdict(int)
    for position, _ in valid_positions:
        counts[position] += 1

    usual_position = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]
    return {
        "usual_position": usual_position,
        "usual_position_score": POSITION_SCORES.get(usual_position),
        "usual_position_share": counts[usual_position] / len(valid_positions),
        "usual_position_matches": len(valid_positions),
    }


def _position_upgrade_summary(player_name: str, player_history, fixture_lineup: dict | None, is_home: bool) -> dict:
    starter_entry = _resolve_starter_entry(player_name, fixture_lineup, is_home)
    usual = _usual_position_summary(player_history)
    today_score = starter_entry.get("role_score") if starter_entry is not None else None
    today_group = starter_entry.get("role_group", "") if starter_entry is not None else ""
    formation = starter_entry.get("formation", "") if starter_entry is not None else ""
    usual_score = usual["usual_position_score"]
    upgrade_score = (
        int(today_score) - int(usual_score)
        if today_score is not None and usual_score is not None
        else None
    )
    position_upgrade = bool(
        starter_entry is not None
        and upgrade_score is not None
        and upgrade_score >= 2
        and usual["usual_position_share"] >= USUAL_POSITION_SHARE_MIN
    )
    return {
        "usual_position": usual["usual_position"],
        "usual_position_score": usual_score if usual_score is not None else "",
        "usual_position_share": usual["usual_position_share"],
        "usual_position_matches": usual["usual_position_matches"],
        "today_position_group": today_group,
        "today_position_score": today_score if today_score is not None else "",
        "today_formation": formation,
        "position_change_score": upgrade_score if upgrade_score is not None else "",
        "position_upgrade": int(position_upgrade),
    }


def write_outputs(rows: List[dict], stats: dict, out_dir: str, compared_at: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "goalscorer-live-comparison.csv")
    txt_path = os.path.join(out_dir, "goalscorer-live-comparison.txt")
    snapshot_dir = os.path.join(out_dir, "live-history")
    stamp = compared_at.replace("-", "").replace(":", "").replace("T", "-").replace("Z", "")
    snapshot_csv_path = os.path.join(snapshot_dir, f"goalscorer-live-comparison-{stamp}.csv")
    snapshot_txt_path = os.path.join(snapshot_dir, f"goalscorer-live-comparison-{stamp}.txt")

    _write_csv(csv_path, rows)
    os.makedirs(snapshot_dir, exist_ok=True)
    _write_csv(snapshot_csv_path, rows)

    with open(txt_path, "w", encoding="utf-8") as handle:
        handle.write("Goalscorer Live Comparison\n")
        handle.write("==========================\n\n")
        handle.write(f"Compared At             {compared_at}\n\n")
        for key in (
            "historical_rows",
            "odds_rows",
            "matched_rows",
            "missing_player_history",
            "missing_team_mapping",
            "fallback_rows",
            "qualified_rows",
            "roster_resolved_rows",
            "high_confidence_rows",
            "medium_confidence_rows",
            "low_confidence_rows",
            "public_high_signals",
            "public_caveat_signals",
            "penalty_transfer_rows",
            "position_upgrade_rows",
            "fixtures_with_confirmed_lineups",
            "confirmed_starter_rows",
            "confirmed_bench_rows",
            "not_in_squad_rows",
        ):
            handle.write(f"{key.replace('_', ' ').title():<24} {stats.get(key, 0):,}\n")
        handle.write(f"\nAverage EV               {stats.get('avg_ev', 0.0):.4f}\n")
    with open(snapshot_txt_path, "w", encoding="utf-8") as handle:
        handle.write(Path(txt_path).read_text(encoding="utf-8"))
    print(f"  Saved: {csv_path}")
    print(f"  Saved: {txt_path}")
    print(f"  Saved: {snapshot_csv_path}")
    print(f"  Saved: {snapshot_txt_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Live pre-match comparison for ATGS odds")
    parser.add_argument("--data", nargs="+", default=DEFAULT_DATA, help="Historical player-log CSVs or globs")
    parser.add_argument("--league", choices=sorted(UNDERSTAT_LEAGUE_SLUGS), default="serie-a", help="League for Understat live-roster resolution")
    parser.add_argument("--odds", default=DEFAULT_ODDS, help="Canonical ATGS odds history CSV")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--bookmaker", default="")
    parser.add_argument("--min-ev", type=float, default=0.05)
    parser.add_argument("--all-captures", action="store_true")
    parser.add_argument("--lineups", default="", help="Optional confirmed-lineup JSON for penalty-transfer detection")
    parser.add_argument("--penalty-hierarchy", default=DEFAULT_PENALTY_HIERARCHY, help="Penalty taker hierarchy JSON")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer Live Comparison")
    print("=" * 64)

    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    load_match_logs = model_mod["load_match_logs"]
    PlayerHistory = model_mod["PlayerHistory"]
    TeamHistory = model_mod["TeamHistory"]
    RECENT_WINDOW = model_mod["RECENT_WINDOW"]
    LONG_WINDOW = model_mod["LONG_WINDOW"]
    MIN_PLAYER_MATCHES = model_mod["MIN_PLAYER_MATCHES"]
    globals()["LEAGUE_AVG"] = model_mod["LEAGUE_AVG"]
    expected_minutes_from_summary = model_mod["expected_minutes_from_summary"]
    build_player_propensity = model_mod["build_player_propensity"]
    build_team_expected_npxg = model_mod["build_team_expected_npxg"]
    build_penalty_component = model_mod["build_penalty_component"]
    prob_at_least_one = model_mod["prob_at_least_one"]
    team_key_func = model_mod["_team_key"]
    coarse_position = model_mod["coarse_position"]
    penalty_hierarchy = load_penalty_hierarchy(ROOT / args.penalty_hierarchy, team_key_func=team_key_func)

    historical_rows = load_match_logs(args.data)
    odds_rows = load_odds_rows(args.odds, bookmaker_filter=args.bookmaker, league=args.league)
    if not args.all_captures:
        odds_rows = latest_rows_per_market(odds_rows)
    compared_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lineup_map = load_confirmed_lineup_map(args.lineups, team_key_func)

    latest_player_meta: Dict[str, dict] = {}
    players_by_team_key: Dict[str, List[dict]] = defaultdict(list)
    for row in historical_rows:
        key = _norm_text(row.player_name)
        current = latest_player_meta.get(key)
        if current is None or row.match_date_str > current["match_date"]:
            latest_player_meta[key] = {
                "player_id": row.player_id,
                "team": row.team,
                "team_key": row.team_key,
                "position": row.position,
                "player_key": key,
                "match_date": row.match_date_str,
                "games": 0.0,
                "minutes": 0.0,
                "source": "history",
            }
    for meta in latest_player_meta.values():
        players_by_team_key[meta["team_key"]].append(meta)

    roster_seasons = {_fixture_season_start(row["match_date"]) for row in odds_rows if row.get("match_date")}
    roster_by_player_key, roster_by_team_key = _load_understat_rosters(
        roster_seasons,
        team_key_func,
        UNDERSTAT_LEAGUE_SLUGS[args.league],
    )

    player_histories: Dict[str, object] = defaultdict(PlayerHistory)
    team_histories: Dict[str, object] = defaultdict(TeamHistory)

    def apply_history_batch(batch: List[object]) -> None:
        team_match_summaries: Dict[tuple[str, str, bool], dict] = {}
        for row in batch:
            team_match_key = (row.team_key, row.opponent_key, row.is_home)
            summary = team_match_summaries.setdefault(
                team_match_key,
                {"team_npxg": None, "team_xg": None, "team_xga": None, "team_penalties_attempted": 0},
            )
            if row.team_xg is not None and summary["team_xg"] is None:
                summary["team_xg"] = row.team_xg
            if row.team_xga is not None and summary["team_xga"] is None:
                summary["team_xga"] = row.team_xga
            summary["team_penalties_attempted"] += row.penalties_attempted

        for summary in team_match_summaries.values():
            if summary["team_xg"] is not None:
                summary["team_npxg"] = max(
                    0.0,
                    summary["team_xg"] - (summary["team_penalties_attempted"] * LEAGUE_AVG["penalty_conversion"]),
                )

        for row in batch:
            opponent_summary = team_histories[row.opponent_key].summary()
            opponent_xga_pre = (
                opponent_summary["xga_per_match"]
                if opponent_summary is not None
                else LEAGUE_AVG["team_xga_per_match"]
            )
            team_match = team_match_summaries[(row.team_key, row.opponent_key, row.is_home)]
            player_histories[row.player_id].add_match(
                {
                    "minutes": row.minutes,
                    "started": row.started,
                    "position": row.position,
                    "goals": row.goals,
                    "shots": row.shots,
                    "xg": row.xg,
                    "npxg": row.npxg,
                    "np_goals": _np_goals(row.goals, row.penalties_scored),
                    "penalties_scored": row.penalties_scored,
                    "penalties_attempted": row.penalties_attempted,
                    "team_penalties_attempted": team_match["team_penalties_attempted"],
                    "opp_xga_pre": opponent_xga_pre,
                }
            )

        for (team_key, _, _), summary in team_match_summaries.items():
            team_histories[team_key].add_match(summary)

    history_index = 0
    results: List[dict] = []
    stats = {
        "historical_rows": len(historical_rows),
        "odds_rows": len(odds_rows),
        "matched_rows": 0,
        "missing_player_history": 0,
        "missing_team_mapping": 0,
        "fallback_rows": 0,
        "qualified_rows": 0,
        "roster_resolved_rows": 0,
        "high_confidence_rows": 0,
        "medium_confidence_rows": 0,
        "low_confidence_rows": 0,
        "public_high_signals": 0,
        "public_caveat_signals": 0,
        "penalty_transfer_rows": 0,
        "position_upgrade_rows": 0,
        "fixtures_with_confirmed_lineups": 0,
        "confirmed_starter_rows": 0,
        "confirmed_bench_rows": 0,
        "not_in_squad_rows": 0,
        "avg_ev": 0.0,
    }

    def resolve_candidate(odds_row: dict) -> Optional[dict]:
        home_team = odds_row["home_team"]
        away_team = odds_row["away_team"]
        home_key = team_key_func(home_team)
        away_key = team_key_func(away_team)
        player_meta = _resolve_player_meta(
            odds_row["player_name"],
            home_key,
            away_key,
            latest_player_meta,
            players_by_team_key,
            roster_by_player_key,
            roster_by_team_key,
        )
        if player_meta is None:
            stats["missing_player_history"] += 1
            return None

        if player_meta.get("source") == "live_roster":
            stats["roster_resolved_rows"] += 1

        player_team = odds_row["player_team"] or player_meta.get("team") or ""
        player_team_key = team_key_func(player_team)
        if player_team_key not in {home_key, away_key}:
            roster_team_keys = [team_key for team_key in player_meta.get("team_keys", []) if team_key in {home_key, away_key}]
            if len(roster_team_keys) == 1:
                player_team_key = roster_team_keys[0]
                player_team = home_team if player_team_key == home_key else away_team
        if player_team_key == home_key:
            opponent = away_team
            opponent_key = away_key
            is_home = True
        elif player_team_key == away_key:
            opponent = home_team
            opponent_key = home_key
            is_home = False
        else:
            stats["missing_team_mapping"] += 1
            return None

        player_id = player_meta["player_id"]
        position = player_meta.get("position", "")
        player_recent = player_histories[player_id].summary(RECENT_WINDOW)
        player_long = player_histories[player_id].summary(LONG_WINDOW)
        opponent_summary = team_histories[opponent_key].summary()
        stacked_features = _stacked_signal_features(player_histories[player_id], opponent_summary)
        roster_games = player_meta.get("games", 0.0) or 0.0
        roster_minutes = player_meta.get("minutes", 0.0) or 0.0
        roster_avg_minutes = (roster_minutes / roster_games) if roster_games > 0 else None
        history_minutes = float(sum(match["minutes"] for match in player_histories[player_id].matches))
        expected_minutes = expected_minutes_from_summary(player_recent, None)
        if player_recent is None and roster_avg_minutes is not None:
            expected_minutes = max(5.0, min(80.0, roster_avg_minutes))

        return {
            "odds_row": odds_row,
            "player_meta": player_meta,
            "player_id": player_id,
            "player_team": player_team,
            "player_team_key": player_team_key,
            "opponent": opponent,
            "opponent_key": opponent_key,
            "is_home": is_home,
            "position": position,
            "player_recent": player_recent,
            "player_long": player_long,
            "roster_avg_minutes": roster_avg_minutes,
            "history_minutes": history_minutes,
            "expected_minutes": expected_minutes,
            "stacked_features": stacked_features,
        }

    def evaluate_fixture_rows(fixture_rows: List[dict]) -> None:
        resolved_rows = []
        for odds_row in fixture_rows:
            candidate = resolve_candidate(odds_row)
            if candidate is not None:
                resolved_rows.append(candidate)

        if not resolved_rows:
            return

        fixture_sample = fixture_rows[0]
        fixture_home_key = team_key_func(fixture_sample["home_team"])
        fixture_away_key = team_key_func(fixture_sample["away_team"])
        fixture_lineup = (
            lineup_map.get((fixture_sample["match_date"], fixture_home_key, fixture_away_key))
            or lineup_map.get(("", fixture_home_key, fixture_away_key))
        )
        if fixture_lineup is not None:
            stats["fixtures_with_confirmed_lineups"] += 1

        team_penalty_events: Dict[str, dict] = {}
        if fixture_lineup is not None:
            team_penalty_events[fixture_home_key] = {
                **penalty_transfer_info(
                    penalty_hierarchy.get(fixture_home_key),
                    fixture_lineup.get("home_players", []),
                ),
                "lineup_status": fixture_lineup.get("home_status", ""),
            }
            team_penalty_events[fixture_away_key] = {
                **penalty_transfer_info(
                    penalty_hierarchy.get(fixture_away_key),
                    fixture_lineup.get("away_players", []),
                ),
                "lineup_status": fixture_lineup.get("away_status", ""),
            }

        for candidate in resolved_rows:
            player_display_name = candidate["player_meta"].get("player_name", candidate["odds_row"]["player_name"])
            lineup_state, lineup_match_name = _resolve_lineup_state(player_display_name, fixture_lineup, candidate["is_home"])
            candidate["lineup_state"] = lineup_state
            candidate["lineup_match_name"] = lineup_match_name

            if lineup_state == "starter":
                candidate["expected_minutes"] = CONFIRMED_STARTER_MINUTES
                stats["confirmed_starter_rows"] += 1
            elif lineup_state == "bench":
                candidate["expected_minutes"] = CONFIRMED_BENCH_MINUTES
                stats["confirmed_bench_rows"] += 1
            elif lineup_state == "not_in_squad":
                candidate["expected_minutes"] = 0.0
                stats["not_in_squad_rows"] += 1

        team_buckets: Dict[str, List[dict]] = defaultdict(list)
        unique_predictions: Dict[tuple[str, str], dict] = {}
        for candidate in resolved_rows:
            unique_key = (candidate["player_id"], candidate["player_team_key"])
            if unique_key not in unique_predictions:
                unique_predictions[unique_key] = candidate
                team_buckets[candidate["player_team_key"]].append(candidate)

        computed_predictions: Dict[tuple[str, str], dict] = {}
        for team_key, team_candidates in team_buckets.items():
            sample = team_candidates[0]
            team_summary = team_histories[team_key].summary()
            opponent_summary = team_histories[sample["opponent_key"]].summary()
            (
                team_expected_npxg,
                attack_factor,
                opp_factor,
                _attack_fallback,
                _defense_fallback,
            ) = build_team_expected_npxg(team_summary, opponent_summary, sample["is_home"])

            team_propensity_total = 0.0
            for candidate in team_candidates:
                if candidate.get("lineup_state") == "not_in_squad":
                    propensity = 0.0
                    base_rate = 0.0
                    method = "model"
                    penalty_lambda = 0.0
                    penalty_share = 0.0
                else:
                    propensity, base_rate, method = build_player_propensity(
                        candidate["player_recent"],
                        candidate["player_long"],
                        candidate["position"],
                        candidate["expected_minutes"],
                    )
                    penalty_lambda = 0.0
                    penalty_share = 0.0
                    if method == "model":
                        penalty_lambda, penalty_share = build_penalty_component(
                            candidate["player_recent"],
                            candidate["player_long"],
                            team_summary,
                            candidate["expected_minutes"],
                        )
                computed_predictions[(candidate["player_id"], candidate["player_team_key"])] = {
                    "base_rate": base_rate,
                    "method": method,
                    "propensity": propensity,
                    "penalty_lambda": penalty_lambda,
                    "penalty_share": penalty_share,
                    "team_expected_npxg": team_expected_npxg,
                    "attack_factor": attack_factor,
                    "opp_factor": opp_factor,
                }
                team_propensity_total += propensity

            if team_propensity_total <= 0:
                team_propensity_total = float(len(team_candidates)) or 1.0
                for candidate in team_candidates:
                    computed_predictions[(candidate["player_id"], candidate["player_team_key"])]["propensity"] = 1.0

            for candidate in team_candidates:
                key = (candidate["player_id"], candidate["player_team_key"])
                prediction = computed_predictions[key]
                if candidate.get("lineup_state") == "not_in_squad":
                    team_share = 0.0
                    non_pen_lambda = 0.0
                    penalty_lambda = 0.0
                    total_lambda = 0.0
                else:
                    team_share = prediction["propensity"] / team_propensity_total
                    non_pen_lambda = prediction["team_expected_npxg"] * team_share
                    penalty_lambda = prediction["penalty_lambda"]
                    total_lambda = max(0.001, non_pen_lambda + penalty_lambda)
                prediction["team_share"] = team_share
                prediction["non_pen_lambda"] = non_pen_lambda
                prediction["total_lambda"] = total_lambda

        for candidate in resolved_rows:
            odds_row = candidate["odds_row"]
            prediction = computed_predictions[(candidate["player_id"], candidate["player_team_key"])]
            method = prediction["method"]
            stacked_features = candidate["stacked_features"]
            if method == "fallback":
                stats["fallback_rows"] += 1

            model_prob = prob_at_least_one(prediction["total_lambda"]) if prediction["total_lambda"] > 0 else 0.0
            fair_odds = (1.0 / model_prob) if model_prob > 0.01 else 99.0
            odds_decimal = odds_row["odds_decimal"]
            implied_prob = odds_row["implied_prob"] or (1.0 / odds_decimal if odds_decimal > 1.0 else 0.0)
            ev = (model_prob * odds_decimal) - 1.0 if odds_decimal > 1.0 else 0.0
            signal_confidence, public_action, confidence_reason = _classify_confidence(
                candidate["player_meta"].get("source", "history"),
                method,
                candidate["history_minutes"],
                ev,
                args.min_ev,
                candidate.get("lineup_state", "unknown"),
            )
            team_penalty_event = team_penalty_events.get(candidate["player_team_key"], {})
            penalty_transfer = bool(team_penalty_event.get("penalty_transfer")) and (
                best_name_match(
                    candidate["player_meta"].get("player_name", odds_row["player_name"]),
                    [team_penalty_event.get("active_taker", "")],
                ) is not None
            )
            position_signal = _position_upgrade_summary(
                candidate["player_meta"].get("player_name", odds_row["player_name"]),
                player_histories[candidate["player_id"]],
                fixture_lineup,
                candidate["is_home"],
            )
            public_gate_reason = ""
            if public_action in {"surface", "surface_with_caveat"}:
                public_gate_reason = _public_publish_gate(
                    candidate["position"],
                    fair_odds,
                    candidate["expected_minutes"],
                    stacked_features["recent_npxg_per90_8"],
                    penalty_transfer,
                    prediction["penalty_share"],
                    bool(position_signal["position_upgrade"]),
                )
                if public_gate_reason:
                    public_action = "monitor"
                    confidence_reason = f"{confidence_reason},{public_gate_reason}" if confidence_reason else public_gate_reason
            signal_eligible = candidate.get("lineup_state", "unknown") not in {"bench", "not_in_squad"}
            if ev >= args.min_ev and signal_eligible:
                stats["qualified_rows"] += 1
            if signal_confidence == "high":
                stats["high_confidence_rows"] += 1
            elif signal_confidence == "medium":
                stats["medium_confidence_rows"] += 1
            else:
                stats["low_confidence_rows"] += 1
            if ev >= args.min_ev and signal_eligible and public_action == "surface":
                stats["public_high_signals"] += 1
            elif ev >= args.min_ev and signal_eligible and public_action == "surface_with_caveat":
                stats["public_caveat_signals"] += 1
            if penalty_transfer:
                stats["penalty_transfer_rows"] += 1
            if position_signal["position_upgrade"]:
                stats["position_upgrade_rows"] += 1

            results.append(
                {
                    "compared_at": compared_at,
                    "captured_at": odds_row["captured_at"],
                    "match_date": odds_row["match_date"],
                    "bookmaker": odds_row["bookmaker"],
                    "competition": odds_row["competition"],
                    "home_team": odds_row["home_team"],
                    "away_team": odds_row["away_team"],
                    "is_home": int(candidate["is_home"]),
                    "player_id": candidate["player_id"],
                    "player_name": odds_row["player_name"],
                    "canonical_player_name": candidate["player_meta"].get("player_name", odds_row["player_name"]),
                    "player_team": candidate["player_team"],
                    "opponent": candidate["opponent"],
                    "position": candidate["position"],
                    "position_group": coarse_position(candidate["position"]),
                    "odds_decimal": round(odds_decimal, 4),
                    "implied_prob": round(implied_prob, 6),
                    "model_p_atgs": round(model_prob, 6),
                    "model_fair_odds_atgs": round(fair_odds, 4),
                    "model_lambda": round(prediction["total_lambda"], 4),
                    "team_expected_npxg": round(prediction["team_expected_npxg"], 4),
                    "team_share": round(prediction["team_share"], 4),
                    "non_pen_lambda": round(prediction["non_pen_lambda"], 4),
                    "penalty_lambda": round(prediction["penalty_lambda"], 4),
                    "penalty_share": round(prediction["penalty_share"], 4),
                    "penalty_transfer": int(penalty_transfer),
                    "penalty_transfer_from": team_penalty_event.get("inherited_from", "") if penalty_transfer else "",
                    "penalty_transfer_level": team_penalty_event.get("transfer_level", "") if penalty_transfer else "",
                    "penalty_transfer_boost_xg": 0.07 if penalty_transfer else 0.0,
                    "lineup_state": candidate.get("lineup_state", "unknown"),
                    "lineup_match_name": candidate.get("lineup_match_name", ""),
                    "usual_position": position_signal["usual_position"],
                    "usual_position_score": position_signal["usual_position_score"],
                    "usual_position_share_10": round(position_signal["usual_position_share"], 4),
                    "usual_position_matches_10": int(position_signal["usual_position_matches"]),
                    "today_position_group": position_signal["today_position_group"],
                    "today_position_score": position_signal["today_position_score"],
                    "today_formation": position_signal["today_formation"],
                    "position_change_score": position_signal["position_change_score"],
                    "position_upgrade": int(position_signal["position_upgrade"]),
                    "expected_minutes": round(candidate["expected_minutes"], 1),
                    "recent_matches_8": int(stacked_features["recent_matches_8"]),
                    "recent_npxg_8": round(stacked_features["recent_npxg_8"], 4),
                    "recent_np_goals_8": round(stacked_features["recent_np_goals_8"], 4),
                    "recent_npxg_per90_8": round(stacked_features["recent_npxg_per90_8"], 4),
                    "finishing_luck_8": round(stacked_features["finishing_luck_8"], 4),
                    "last_fixture_avg_xga_3": round(stacked_features["last_fixture_avg_xga_3"], 4) if stacked_features["last_fixture_avg_xga_3"] is not None else "",
                    "next_opponent_xga": round(stacked_features["next_opponent_xga"], 4),
                    "fixture_swing_3": round(stacked_features["fixture_swing_3"], 4) if stacked_features["fixture_swing_3"] is not None else "",
                    "attack_factor": round(prediction["attack_factor"], 4),
                    "opp_factor": round(prediction["opp_factor"], 4),
                    "ev": round(ev, 6),
                    "edge_pct": round(((model_prob - implied_prob) / implied_prob) * 100.0, 3) if implied_prob > 0 else 0.0,
                    "method": method,
                    "resolver_source": candidate["player_meta"].get("source", "history"),
                    "historical_minutes": round(candidate["history_minutes"], 1),
                    "signal_confidence": signal_confidence,
                    "public_action": public_action,
                    "confidence_reason": confidence_reason,
                    "lineup_status": team_penalty_event.get("lineup_status", ""),
                    "source": odds_row["source"],
                    "notes": odds_row["notes"],
                }
            )
            stats["matched_rows"] += 1

    for match_date, group_rows in groupby(odds_rows, key=lambda row: row["match_date"]):
        while history_index < len(historical_rows) and historical_rows[history_index].match_date_str < match_date:
            batch_date = historical_rows[history_index].match_date
            batch: List[object] = []
            while history_index < len(historical_rows) and historical_rows[history_index].match_date == batch_date:
                batch.append(historical_rows[history_index])
                history_index += 1
            apply_history_batch(batch)
        match_rows = list(group_rows)
        fixture_groups: Dict[tuple[str, str], List[dict]] = defaultdict(list)
        for odds_row in match_rows:
            fixture_groups[(odds_row["home_team"], odds_row["away_team"])].append(odds_row)
        for fixture_rows in fixture_groups.values():
            evaluate_fixture_rows(fixture_rows)

    if results:
        stats["avg_ev"] = sum(row["ev"] for row in results) / len(results)
        results.sort(key=lambda row: (row["match_date"], row["bookmaker"], -row["ev"], row["player_name"]))

    print(f"  Historical rows:      {stats['historical_rows']:,}")
    print(f"  Odds rows:            {stats['odds_rows']:,}")
    print(f"  Matched rows:         {stats['matched_rows']:,}")
    print(f"  Missing player hist:  {stats['missing_player_history']:,}")
    print(f"  Missing team mapping: {stats['missing_team_mapping']:,}")
    print(f"  Fallback rows:        {stats['fallback_rows']:,}")
    print(f"  Qualified rows:       {stats['qualified_rows']:,}")
    print(f"  High-confidence:      {stats['high_confidence_rows']:,}")
    print(f"  Medium-confidence:    {stats['medium_confidence_rows']:,}")
    print(f"  Low-confidence:       {stats['low_confidence_rows']:,}")
    print(f"  Public high signals:  {stats['public_high_signals']:,}")
    print(f"  Public caveats:       {stats['public_caveat_signals']:,}")
    print(f"  Penalty transfers:    {stats['penalty_transfer_rows']:,}")
    print(f"  Position upgrades:    {stats['position_upgrade_rows']:,}")
    print(f"  Fixtures w/ lineups:  {stats['fixtures_with_confirmed_lineups']:,}")
    print(f"  Confirmed starters:   {stats['confirmed_starter_rows']:,}")
    print(f"  Confirmed bench:      {stats['confirmed_bench_rows']:,}")
    print(f"  Not in squad:         {stats['not_in_squad_rows']:,}")
    print(f"  Average EV:           {stats['avg_ev']:.4f}")

    write_outputs(results, stats, args.out_dir, compared_at)
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
