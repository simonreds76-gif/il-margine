#!/usr/bin/env python3
"""
Fetch FotMob league lineups and write them in the JSON shape expected by the
goalscorer pipeline and monitor.

Lineups are read from the match page's embedded Next.js payload:
  props.pageProps.content.lineup

Important detail:
  - lineupType == "predicted"   -> expected / probable XI
  - lineupType == "standard"    -> confirmed XI

Both are saved for display. Only confirmed XIs should affect starter-state
logic in the pricing pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import runpy
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "goalscorer" / "confirmed-lineups.json"
DEFAULT_PLAYER_LOG = ROOT / "data" / "goalscorer" / "serie-a-player-match-logs-2025-2026.csv"
SERIE_A_LEAGUE_ID = 55
LEAGUE_LABELS = {
    47: "Premier League",
    53: "Ligue 1",
    54: "Bundesliga",
    55: "Serie A",
    87: "La Liga",
}
MATCHES_URL = "https://www.fotmob.com/api/data/matches"
MATCH_URL = "https://www.fotmob.com/api/data/match"
WEB_BASE = "https://www.fotmob.com"
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fotmob.com/",
}

ROLE_GROUPS = {
    0: "GK",
    1: "DEF",
    2: "DMC",
    3: "MID",
    4: "AM",
    5: "FW",
}


def _today_fotmob_date() -> str:
    return datetime.now(ZoneInfo("Europe/London")).strftime("%Y%m%d")


def _fotmob_date_window(start_date: str, days_ahead: int) -> List[str]:
    base = datetime.strptime(start_date, "%Y%m%d").replace(tzinfo=ZoneInfo("Europe/London"))
    return [
        (base + timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(max(days_ahead, 0) + 1)
    ]


def _team_key_func():
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    return model_mod["_team_key"]


def _load_understat_rosters(csv_path: Path, team_key_func) -> Dict[str, List[str]]:
    roster_by_team: Dict[str, List[str]] = defaultdict(list)
    seen = set()
    with csv_path.open("r", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            team = (row.get("team") or "").strip()
            player_name = (row.get("player_name") or "").strip()
            if not team or not player_name:
                continue
            key = (team_key_func(team), player_name)
            if key in seen:
                continue
            seen.add(key)
            roster_by_team[key[0]].append(player_name)
    return roster_by_team


def _fetch_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def _fetch_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def _extract_next_payload(html_text: str) -> dict:
    match = NEXT_DATA_RE.search(html_text)
    if not match:
        raise ValueError("Could not find __NEXT_DATA__ payload on FotMob page")
    return json.loads(match.group(1))


def _resolve_player_name(raw_name: str, team_name: str, roster_by_team: Dict[str, List[str]], team_key_func) -> str:
    return str(raw_name or "").strip()


def _resolve_player_names(players: List[dict], team_name: str, roster_by_team: Dict[str, List[str]], team_key_func) -> List[str]:
    resolved: List[str] = []
    for player in players:
        raw_name = str(player.get("name") or "").strip()
        if not raw_name:
            continue
        resolved.append(_resolve_player_name(raw_name, team_name, roster_by_team, team_key_func))
    return resolved


def _parse_formation_lines(formation: str, starter_count: int) -> List[int]:
    if not formation:
        return []
    try:
        line_sizes = [int(part) for part in str(formation).split("-") if part.strip()]
    except ValueError:
        return []
    if sum(line_sizes) != max(starter_count - 1, 0):
        return []
    return line_sizes


def _line_role_score(line_sizes: List[int], line_index: int) -> int:
    total_lines = len(line_sizes)
    if total_lines <= 0:
        return 0
    if line_index == 0:
        return 1
    if line_index == total_lines - 1:
        return 5
    if total_lines == 4:
        if line_index == 1:
            return 2 if line_sizes[line_index] <= 2 else 3
        return 4
    if total_lines >= 5:
        if line_index == 1:
            return 2
        if line_index >= total_lines - 2:
            return 4
        return 3
    return 3


def _build_starter_entries(players: List[dict], team_name: str, roster_by_team: Dict[str, List[str]], team_key_func, formation: str) -> List[dict]:
    entries: List[dict] = []
    if not players:
        return entries

    resolved_names = [
        _resolve_player_name(str(player.get("name") or "").strip(), team_name, roster_by_team, team_key_func)
        for player in players
        if str(player.get("name") or "").strip()
    ]
    if not resolved_names:
        return entries

    entries.append(
        {
            "name": resolved_names[0],
            "line_index": -1,
            "line_size": 1,
            "role_score": 0,
            "role_group": ROLE_GROUPS[0],
            "formation": formation,
            "position_id": players[0].get("positionId", ""),
        }
    )

    outfield_players = players[1:]
    outfield_names = resolved_names[1:]
    line_sizes = _parse_formation_lines(formation, len(players))
    if not line_sizes:
        for raw_player, resolved_name in zip(outfield_players, outfield_names):
            entries.append(
                {
                    "name": resolved_name,
                    "line_index": -1,
                    "line_size": 0,
                    "role_score": 0,
                    "role_group": "",
                    "formation": formation,
                    "position_id": raw_player.get("positionId", ""),
                }
            )
        return entries

    cursor = 0
    for line_index, line_size in enumerate(line_sizes):
        role_score = _line_role_score(line_sizes, line_index)
        role_group = ROLE_GROUPS.get(role_score, "")
        for _ in range(line_size):
            if cursor >= len(outfield_players):
                break
            raw_player = outfield_players[cursor]
            resolved_name = outfield_names[cursor]
            entries.append(
                {
                    "name": resolved_name,
                    "line_index": line_index,
                    "line_size": line_size,
                    "role_score": role_score,
                    "role_group": role_group,
                    "formation": formation,
                    "position_id": raw_player.get("positionId", ""),
                }
            )
            cursor += 1

    return entries


def fetch_confirmed_lineups(date_str: str, league_id: int, roster_by_team: Dict[str, List[str]], team_key_func) -> tuple[List[dict], dict]:
    matches_payload = _fetch_json(
        MATCHES_URL,
        {"date": date_str, "timezone": "Europe/London", "ccode3": "GBR"},
    )
    leagues = matches_payload.get("leagues", [])
    serie_matches = [match for league in leagues if league.get("id") == league_id for match in league.get("matches", [])]

    fixtures: List[dict] = []
    stats = {
        "league_matches": len(serie_matches),
        "page_fetches": 0,
        "confirmed_fixtures": 0,
        "predicted_fixtures": 0,
        "missing_lineup_payload": 0,
    }

    for match in serie_matches:
        match_id = match.get("id")
        if not match_id:
            continue

        match_payload = _fetch_json(MATCH_URL, {"id": match_id})
        page_url = str(match_payload.get("pageUrl") or "").strip()
        if not page_url:
            continue

        page_payload = _extract_next_payload(_fetch_text(f"{WEB_BASE}{page_url}"))
        stats["page_fetches"] += 1
        page_props = page_payload.get("props", {}).get("pageProps", {})
        lineup = page_props.get("content", {}).get("lineup")
        general = page_props.get("general", {})
        if not isinstance(lineup, dict):
            stats["missing_lineup_payload"] += 1
            continue

        lineup_type = str(lineup.get("lineupType") or "").strip().lower()
        if lineup_type not in {"standard", "predicted"}:
            continue

        home_team = str(general.get("homeTeam", {}).get("name") or lineup.get("homeTeam", {}).get("name") or match.get("home", {}).get("name") or "").strip()
        away_team = str(general.get("awayTeam", {}).get("name") or lineup.get("awayTeam", {}).get("name") or match.get("away", {}).get("name") or "").strip()
        match_date = str(general.get("matchTimeUTCDate") or match.get("status", {}).get("utcTime") or "").strip()[:10]
        home_formation = str(lineup.get("homeTeam", {}).get("formation") or lineup.get("formation") or "").strip()
        away_formation = str(lineup.get("awayTeam", {}).get("formation") or lineup.get("formation") or "").strip()
        home_starter_entries = _build_starter_entries(
            lineup.get("homeTeam", {}).get("starters", []),
            home_team,
            roster_by_team,
            team_key_func,
            home_formation,
        )
        away_starter_entries = _build_starter_entries(
            lineup.get("awayTeam", {}).get("starters", []),
            away_team,
            roster_by_team,
            team_key_func,
            away_formation,
        )
        home_players = [entry["name"] for entry in home_starter_entries]
        away_players = [entry["name"] for entry in away_starter_entries]
        home_subs = _resolve_player_names(lineup.get("homeTeam", {}).get("subs", []), home_team, roster_by_team, team_key_func)
        away_subs = _resolve_player_names(lineup.get("awayTeam", {}).get("subs", []), away_team, roster_by_team, team_key_func)
        home_unavailable = _resolve_player_names(lineup.get("homeTeam", {}).get("unavailable", []), home_team, roster_by_team, team_key_func)
        away_unavailable = _resolve_player_names(lineup.get("awayTeam", {}).get("unavailable", []), away_team, roster_by_team, team_key_func)
        if len(home_players) != 11 or len(away_players) != 11:
            stats["missing_lineup_payload"] += 1
            continue

        fixtures.append(
            {
                "match_date": match_date,
                "home_team": home_team,
                "away_team": away_team,
                "home_status": "Confirmed Lineup" if lineup_type == "standard" else "FotMob Expected XI",
                "away_status": "Confirmed Lineup" if lineup_type == "standard" else "FotMob Expected XI",
                "lineup_type": lineup_type,
                "home_formation": home_formation,
                "away_formation": away_formation,
                "home_players": home_players,
                "away_players": away_players,
                "home_starters": home_starter_entries,
                "away_starters": away_starter_entries,
                "home_subs": home_subs,
                "away_subs": away_subs,
                "home_unavailable": home_unavailable,
                "away_unavailable": away_unavailable,
            }
        )
        if lineup_type == "standard":
            stats["confirmed_fixtures"] += 1
        else:
            stats["predicted_fixtures"] += 1

    fixtures.sort(key=lambda item: (item["match_date"], item["home_team"], item["away_team"]))
    return fixtures, stats


def write_output(path: Path, fixtures: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"fixtures": fixtures}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch FotMob league lineups")
    parser.add_argument("--date", default=_today_fotmob_date(), help="FotMob date in YYYYMMDD format")
    parser.add_argument("--days-ahead", type=int, default=0, help="Also fetch subsequent FotMob dates up to this many days ahead")
    parser.add_argument("--league-id", type=int, default=SERIE_A_LEAGUE_ID, help="FotMob league id")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    parser.add_argument("--player-log", default=str(DEFAULT_PLAYER_LOG), help="Current Understat-style player log for name matching")
    args = parser.parse_args()

    team_key_func = _team_key_func()
    roster_by_team = _load_understat_rosters(Path(args.player_log), team_key_func)

    print("\n" + "=" * 64)
    print("  IL MARGINE - FotMob Confirmed Lineups")
    print("=" * 64)
    date_window = _fotmob_date_window(args.date, args.days_ahead)
    print(
        "  Date Window:          "
        f"{date_window[0]}{' -> ' + date_window[-1] if len(date_window) > 1 else ''}"
    )
    print(f"  League:               {LEAGUE_LABELS.get(args.league_id, 'League ' + str(args.league_id))}")
    print(f"  League ID:            {args.league_id}")

    fixtures: List[dict] = []
    stats = {
        "league_matches": 0,
        "page_fetches": 0,
        "confirmed_fixtures": 0,
        "predicted_fixtures": 0,
        "missing_lineup_payload": 0,
    }
    seen_keys = set()
    for date_str in date_window:
        daily_fixtures, daily_stats = fetch_confirmed_lineups(date_str, args.league_id, roster_by_team, team_key_func)
        stats = {key: stats[key] + daily_stats.get(key, 0) for key in stats}
        for fixture in daily_fixtures:
            key = (fixture.get("match_date", ""), fixture.get("home_team", ""), fixture.get("away_team", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            fixtures.append(fixture)

    fixtures.sort(key=lambda item: (item["match_date"], item["home_team"], item["away_team"]))
    write_output(Path(args.out), fixtures)

    print(f"  League fixtures:      {stats['league_matches']:,}")
    print(f"  Page fetches:         {stats['page_fetches']:,}")
    print(f"  Confirmed lineups:    {stats['confirmed_fixtures']:,}")
    print(f"  Expected XIs:         {stats['predicted_fixtures']:,}")
    print(f"  Missing payload:      {stats['missing_lineup_payload']:,}")
    print(f"  Saved:                {args.out}")
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
