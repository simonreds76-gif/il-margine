#!/usr/bin/env python3
"""
Fetch recent FotMob post-match detail payloads for goalscorer settlement.

This script creates a lightweight, per-fixture result layer that is safer for
settlement than relying on Understat participation rows:
  - who appeared
  - who stayed unused
  - who scored non-own goals

Output files are written to:
  data/goalscorer/match-results/<league>/fotmob-<match_date>-<match_id>.json
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "data" / "goalscorer" / "match-results"
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

LEAGUE_CONFIGS = {
    "serie-a": {"league_id": 55, "label": "Serie A"},
    "epl": {"league_id": 47, "label": "Premier League"},
    "la-liga": {"league_id": 87, "label": "La Liga"},
    "bundesliga": {"league_id": 54, "label": "Bundesliga"},
    "ligue-1": {"league_id": 53, "label": "Ligue 1"},
}


def _today_fotmob_date() -> str:
    return datetime.now(ZoneInfo("Europe/London")).strftime("%Y%m%d")


def _date_window(end_date: str, days_back: int) -> List[str]:
    base = datetime.strptime(end_date, "%Y%m%d").replace(tzinfo=ZoneInfo("Europe/London"))
    return [
        (base - timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(max(days_back, 0), -1, -1)
    ]


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


def _fetch_match_payload(match_id: int) -> dict:
    match_payload = _fetch_json(MATCH_URL, {"id": match_id})
    page_url = str(match_payload.get("pageUrl") or "").strip()
    if not page_url:
        raise ValueError(f"Missing pageUrl for match {match_id}")
    return _extract_next_payload(_fetch_text(f"{WEB_BASE}{page_url}"))


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _event_counts(events: Iterable[dict]) -> tuple[int, int]:
    goals = 0
    own_goals = 0
    for event in events:
        event_type = str((event or {}).get("type") or "").strip().lower()
        if event_type in {"goal", "penaltygoal"}:
            goals += 1
        elif event_type == "owngoal":
            own_goals += 1
    return goals, own_goals


def _substitution_times(sub_events: Iterable[dict]) -> tuple[int | None, int | None]:
    sub_in = None
    sub_out = None
    for event in sub_events:
        if not isinstance(event, dict):
            continue
        minute = _safe_int(event.get("time"))
        event_type = str(event.get("type") or "").strip().lower()
        if event_type == "subin":
            sub_in = minute
        elif event_type == "subout":
            sub_out = minute
    return sub_in, sub_out


def _estimate_minutes(*, started: bool, sub_in: int | None, sub_out: int | None) -> int:
    if started:
        if sub_out is not None and sub_out > 0:
            return sub_out
        return 90
    if sub_in is not None and sub_in > 0:
        return max(1, 90 - sub_in)
    return 0


def _parse_team_players(team_payload: dict, team_name: str, team_id: int) -> List[dict]:
    players: List[dict] = []
    for bucket, started in (("starters", True), ("subs", False), ("unavailable", False)):
        for player in team_payload.get(bucket, []) or []:
            if not isinstance(player, dict):
                continue
            performance = player.get("performance") or {}
            perf_events = performance.get("events") or []
            sub_events = performance.get("substitutionEvents") or []
            goals, own_goals = _event_counts(perf_events)
            sub_in, sub_out = _substitution_times(sub_events)
            players.append(
                {
                    "name": str(player.get("name") or "").strip(),
                    "fotmob_id": _safe_int(player.get("id")),
                    "team": team_name,
                    "team_id": team_id,
                    "started": started,
                    "squad_status": bucket[:-1] if bucket.endswith("s") else bucket,
                    "minutes_played": _estimate_minutes(started=started, sub_in=sub_in, sub_out=sub_out),
                    "goals": goals,
                    "own_goals": own_goals,
                    "subbed_on": sub_in is not None,
                    "subbed_off": sub_out is not None,
                    "sub_in_minute": sub_in or 0,
                    "sub_out_minute": sub_out or 0,
                }
            )
    return players


def _extract_goal_events(shots: Iterable[dict], home_team: str, away_team: str, home_id: int, away_id: int) -> List[dict]:
    goal_events: List[dict] = []
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        event_type = str(shot.get("eventType") or "").strip().lower()
        if event_type != "goal":
            continue
        if str(shot.get("period") or "").strip().lower() == "penaltyshootout":
            continue
        team_id = _safe_int(shot.get("teamId"))
        if team_id == home_id:
            team_name = home_team
        elif team_id == away_id:
            team_name = away_team
        else:
            team_name = str(shot.get("teamName") or "").strip()
        goal_events.append(
            {
                "minute": _safe_int(shot.get("min")),
                "scorer": str(shot.get("fullName") or shot.get("playerName") or "").strip(),
                "fotmob_id": _safe_int(shot.get("playerId")),
                "team": team_name,
                "is_own_goal": False,
            }
        )
    return goal_events


def _build_substitution_groups(players: Iterable[dict]) -> List[dict]:
    groups: Dict[tuple[int, int], dict] = {}
    for player in players:
        if not isinstance(player, dict):
            continue
        team_id = _safe_int(player.get("team_id"))
        team_name = str(player.get("team") or "").strip()
        player_payload = {
            "name": str(player.get("name") or "").strip(),
            "fotmob_id": _safe_int(player.get("fotmob_id")),
        }
        sub_in = _safe_int(player.get("sub_in_minute"))
        sub_out = _safe_int(player.get("sub_out_minute"))
        if bool(player.get("subbed_on")) and sub_in > 0:
            group = groups.setdefault(
                (team_id, sub_in),
                {"team": team_name, "team_id": team_id, "minute": sub_in, "on": [], "off": []},
            )
            group["on"].append(player_payload)
        if bool(player.get("subbed_off")) and sub_out > 0:
            group = groups.setdefault(
                (team_id, sub_out),
                {"team": team_name, "team_id": team_id, "minute": sub_out, "on": [], "off": []},
            )
            group["off"].append(player_payload)

    output: List[dict] = []
    for group in groups.values():
        group["direct_replacement_verified"] = len(group["on"]) == 1 and len(group["off"]) == 1
        output.append(group)
    return sorted(output, key=lambda group: (str(group.get("team") or ""), _safe_int(group.get("minute"))))


def _build_match_result(league_key: str, match: dict, payload: dict) -> dict | None:
    page_props = payload.get("props", {}).get("pageProps", {})
    general = page_props.get("general", {}) or {}
    content = page_props.get("content", {}) or {}
    lineup = content.get("lineup") or {}
    shotmap = content.get("shotmap") or {}
    shots = shotmap.get("shots") or []
    if not isinstance(lineup, dict):
        lineup = {}
    if not isinstance(shots, list):
        shots = []

    home_team = str(
        general.get("homeTeam", {}).get("name")
        or match.get("home", {}).get("longName")
        or match.get("home", {}).get("name")
        or ""
    ).strip()
    away_team = str(
        general.get("awayTeam", {}).get("name")
        or match.get("away", {}).get("longName")
        or match.get("away", {}).get("name")
        or ""
    ).strip()
    match_date = str(general.get("matchTimeUTCDate") or match.get("status", {}).get("utcTime") or "").strip()[:10]
    if not home_team or not away_team or not match_date:
        return None

    home_id = _safe_int(general.get("homeTeam", {}).get("id") or match.get("home", {}).get("id"))
    away_id = _safe_int(general.get("awayTeam", {}).get("id") or match.get("away", {}).get("id"))
    status = match.get("status", {}) or {}

    home_lineup = lineup.get("homeTeam", {}) or {}
    away_lineup = lineup.get("awayTeam", {}) or {}
    home_players = _parse_team_players(home_lineup, home_team, home_id)
    away_players = _parse_team_players(away_lineup, away_team, away_id)
    goal_events = _extract_goal_events(shots, home_team, away_team, home_id, away_id)

    goal_counts: Dict[tuple[int, str], int] = {}
    for event in goal_events:
        key = (_safe_int(event.get("fotmob_id")), str(event.get("scorer") or "").strip())
        goal_counts[key] = goal_counts.get(key, 0) + 1

    merged_players: List[dict] = []
    for player in [*home_players, *away_players]:
        key = (_safe_int(player.get("fotmob_id")), str(player.get("name") or "").strip())
        player["goals"] = max(_safe_int(player.get("goals")), goal_counts.get(key, 0))
        merged_players.append(player)

    return {
        "league": league_key,
        "match_id": _safe_int(match.get("id")),
        "match_date": match_date,
        "status": "finished" if status.get("finished") else ("started" if status.get("started") else "scheduled"),
        "status_started": bool(status.get("started")),
        "status_finished": bool(status.get("finished")),
        "status_cancelled": bool(status.get("cancelled")),
        "status_reason": str(status.get("reason", {}).get("long") or status.get("reason", {}).get("short") or "").strip(),
        "home_team": home_team,
        "away_team": away_team,
        "home_fotmob_team_id": home_id,
        "away_fotmob_team_id": away_id,
        "home_score": _safe_int(status.get("scoreStr", "0-0").split("-")[0] if "-" in str(status.get("scoreStr") or "") else 0),
        "away_score": _safe_int(status.get("scoreStr", "0-0").split("-")[1] if "-" in str(status.get("scoreStr") or "") else 0),
        "players": merged_players,
        "goal_events": goal_events,
        "substitution_groups": _build_substitution_groups(merged_players),
        "fetched_at": datetime.now(ZoneInfo("UTC")).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def _save_result(out_dir: Path, league_key: str, payload: dict) -> None:
    league_dir = out_dir / league_key
    league_dir.mkdir(parents=True, exist_ok=True)
    target = league_dir / f"fotmob-{payload['match_date']}-{payload['match_id']}.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent FotMob post-match detail for goalscorer settlement")
    parser.add_argument("--league", nargs="*", choices=sorted(LEAGUE_CONFIGS), default=sorted(LEAGUE_CONFIGS), help="League keys to fetch")
    parser.add_argument("--date", default=_today_fotmob_date(), help="End FotMob date in YYYYMMDD format")
    parser.add_argument("--days-back", type=int, default=3, help="Fetch this many days back inclusive")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory for match result JSONs")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    dates = _date_window(args.date, args.days_back)
    saved = 0
    warnings = 0

    print("\n" + "=" * 64)
    print("  IL MARGINE - FotMob Match Detail Fetch")
    print("=" * 64)
    print(f"  Dates:                {dates[0]} -> {dates[-1]}")
    print(f"  Leagues:              {', '.join(args.league)}")

    for fotmob_date in dates:
        try:
            matches_payload = _fetch_json(
                MATCHES_URL,
                {"date": fotmob_date, "timezone": "Europe/London", "ccode3": "GBR"},
            )
        except Exception as exc:
            warnings += 1
            print(f"WARNING: failed to fetch FotMob matches for {fotmob_date}: {exc}")
            continue

        leagues = matches_payload.get("leagues", [])
        for league_key in args.league:
            league_id = LEAGUE_CONFIGS[league_key]["league_id"]
            league_matches = [
                match
                for league in leagues
                if league.get("id") == league_id
                for match in league.get("matches", [])
            ]
            for match in league_matches:
                status = match.get("status", {}) or {}
                if not status.get("started") and not status.get("finished"):
                    continue
                match_id = _safe_int(match.get("id"))
                if not match_id:
                    continue
                try:
                    payload = _fetch_match_payload(match_id)
                    result = _build_match_result(league_key, match, payload)
                except Exception as exc:
                    warnings += 1
                    print(f"WARNING: failed to fetch FotMob match {match_id}: {exc}")
                    continue
                if result is None:
                    continue
                _save_result(out_dir, league_key, result)
                saved += 1

    print(f"  Saved results:        {saved:,}")
    print(f"  Warnings:             {warnings:,}")
    print(f"  Output dir:           {out_dir}")
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
