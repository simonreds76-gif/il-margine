#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests

from settlement_utils import normalize_team_name


ROOT = Path(__file__).resolve().parents[1]
MATCHES_URL = "https://www.fotmob.com/api/data/matches"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fotmob.com/",
}

LEAGUE_CONFIGS = {
    "serie-a": {"league_id": 55, "label": "Serie A", "lineups": "data/goalscorer/confirmed-lineups.json"},
    "epl": {"league_id": 47, "label": "Premier League", "lineups": "data/goalscorer/epl-confirmed-lineups.json"},
    "la-liga": {"league_id": 87, "label": "La Liga", "lineups": "data/goalscorer/la-liga-confirmed-lineups.json"},
    "bundesliga": {"league_id": 54, "label": "Bundesliga", "lineups": "data/goalscorer/bundesliga-confirmed-lineups.json"},
    "ligue-1": {"league_id": 53, "label": "Ligue 1", "lineups": "data/goalscorer/ligue-1-confirmed-lineups.json"},
}
TRACKED_SIGNAL_GLOB = "data/goalscorer/fair-odds-lab-*-signals.csv"


@dataclass
class FixtureWindow:
    tier: str
    kickoff_utc: datetime
    minutes_to_kickoff: int
    home_team: str
    away_team: str
    match_id: int | None
    already_confirmed: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a lightweight official-lineup polling plan from FotMob fixtures."
    )
    parser.add_argument("--leagues", default=",".join(LEAGUE_CONFIGS.keys()), help="Comma-separated league keys")
    parser.add_argument(
        "--lookahead-hours",
        type=int,
        default=36,
        help="Fixture schedule horizon used only to discover lineup windows",
    )
    parser.add_argument(
        "--lineup-window-before-minutes",
        type=int,
        default=70,
        help="Start official-lineup checks this many minutes before kickoff",
    )
    parser.add_argument(
        "--lineup-grace-after-minutes",
        type=int,
        default=15,
        help="Keep retrying briefly after kickoff if confirmed teams are still missing",
    )
    parser.add_argument("--hot-cadence", type=int, default=10, help="Cadence in minutes while lineups are due")
    parser.add_argument(
        "--close-window-before-minutes",
        type=int,
        default=40,
        help="Continue price capture for tracked signals this many minutes before kickoff",
    )
    parser.add_argument(
        "--include-confirmed",
        action="store_true",
        help="Include already-confirmed fixtures in output for diagnostics; they are skipped by default",
    )
    parser.add_argument(
        "--include-distant-fixtures",
        action="store_true",
        help="Diagnostic mode only: include fixtures outside the official-lineup window as distant/off fixtures",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    return parser.parse_args()


def _fotmob_dates(now_utc: datetime, lookahead_hours: int) -> List[str]:
    today = now_utc.astimezone(timezone.utc).date()
    horizon = now_utc + timedelta(hours=max(lookahead_hours, 1))
    days = max((horizon.date() - today).days, 0) + 1
    return [(today + timedelta(days=offset)).strftime("%Y%m%d") for offset in range(days)]


def _parse_kickoff(match: dict[str, Any]) -> datetime | None:
    raw = (
        match.get("status", {}).get("utcTime")
        or match.get("timeUTCDate")
        or match.get("matchTimeUTCDate")
        or match.get("status", {}).get("timeStr")
    )
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _is_cancelled_or_finished(match: dict[str, Any]) -> bool:
    status = match.get("status", {}) or {}
    return bool(status.get("finished")) or bool(status.get("cancelled"))


def _classify_fixture(
    now_utc: datetime,
    kickoff_utc: datetime,
    lineup_window_before_minutes: int,
    lineup_grace_after_minutes: int,
    *,
    include_distant: bool,
) -> str | None:
    minutes_to_kickoff = int((kickoff_utc - now_utc).total_seconds() // 60)
    if minutes_to_kickoff > lineup_window_before_minutes:
        return "distant" if include_distant else None
    if minutes_to_kickoff >= 0:
        return "lineup"
    if minutes_to_kickoff >= -lineup_grace_after_minutes:
        return "grace"
    return None


def _fixture_key(match_date: str, home_team: str, away_team: str) -> tuple[str, str, str]:
    teams = sorted([normalize_team_name(home_team), normalize_team_name(away_team)])
    return str(match_date)[:10], teams[0], teams[1]


def _load_tracked_signal_fixtures() -> dict[str, set[tuple[str, str, str]]]:
    tracked: dict[str, set[tuple[str, str, str]]] = {league: set() for league in LEAGUE_CONFIGS}
    pattern = str(ROOT / TRACKED_SIGNAL_GLOB)
    for raw_path in sorted(glob.glob(pattern)):
        path = Path(raw_path)
        league = path.name.removeprefix("fair-odds-lab-").removesuffix("-signals.csv")
        if league not in tracked:
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                match_date = str(row.get("date") or "")[:10]
                home = str(row.get("home_team") or "")
                away = str(row.get("away_team") or "")
                if match_date and home and away:
                    tracked[league].add(_fixture_key(match_date, home, away))
    return tracked


def _effective_fixture_tier(
    now_utc: datetime,
    kickoff_utc: datetime,
    *,
    already_confirmed: bool,
    tracked_signal: bool,
    lineup_window_before_minutes: int,
    lineup_grace_after_minutes: int,
    close_window_before_minutes: int,
    include_distant: bool,
    include_confirmed: bool,
) -> str | None:
    minutes_to_kickoff = int((kickoff_utc - now_utc).total_seconds() // 60)
    if already_confirmed:
        if tracked_signal and 0 <= minutes_to_kickoff <= close_window_before_minutes:
            return "close"
        if not include_confirmed:
            return None
    return _classify_fixture(
        now_utc,
        kickoff_utc,
        lineup_window_before_minutes,
        lineup_grace_after_minutes,
        include_distant=include_distant,
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _confirmed_match_ids(lineups_path: Path) -> set[int]:
    payload = _read_json(lineups_path)
    fixtures = payload.get("fixtures", []) if isinstance(payload, dict) else []
    confirmed: set[int] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        if str(fixture.get("lineup_type") or "").strip().lower() != "standard":
            continue
        match_id = fixture.get("fotmob_match_id")
        try:
            confirmed.add(int(match_id))
        except (TypeError, ValueError):
            continue
    return confirmed


def fetch_daily_payload(date_str: str) -> dict[str, Any]:
    response = requests.get(
        MATCHES_URL,
        params={"date": date_str, "timezone": "Europe/London", "ccode3": "GBR"},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    args = parse_args()
    requested_leagues = [item.strip() for item in args.leagues.split(",") if item.strip()]
    league_ids = {LEAGUE_CONFIGS[key]["league_id"]: key for key in requested_leagues if key in LEAGUE_CONFIGS}
    now_utc = datetime.now(timezone.utc)
    lookahead_limit = now_utc + timedelta(hours=max(args.lookahead_hours, 1))
    confirmed_by_league = {
        league: _confirmed_match_ids(ROOT / str(LEAGUE_CONFIGS[league]["lineups"]))
        for league in requested_leagues
        if league in LEAGUE_CONFIGS
    }
    tracked_signals = _load_tracked_signal_fixtures()

    fixtures_by_league: Dict[str, List[FixtureWindow]] = {
        league: [] for league in requested_leagues if league in LEAGUE_CONFIGS
    }
    for date_str in _fotmob_dates(now_utc, args.lookahead_hours):
        payload = fetch_daily_payload(date_str)
        for league in payload.get("leagues", []):
            league_id = league.get("id")
            league_key = league_ids.get(league_id)
            if not league_key:
                continue
            for match in league.get("matches", []):
                if _is_cancelled_or_finished(match):
                    continue
                kickoff_utc = _parse_kickoff(match)
                if kickoff_utc is None or kickoff_utc > lookahead_limit:
                    continue
                match_id = int(match.get("id")) if match.get("id") else None
                already_confirmed = bool(match_id and match_id in confirmed_by_league.get(league_key, set()))
                home_name = str(match.get("home", {}).get("name") or "").strip()
                away_name = str(match.get("away", {}).get("name") or "").strip()
                tracked_signal = _fixture_key(kickoff_utc.date().isoformat(), home_name, away_name) in tracked_signals.get(league_key, set())
                tier = _effective_fixture_tier(
                    now_utc,
                    kickoff_utc,
                    already_confirmed=already_confirmed,
                    tracked_signal=tracked_signal,
                    lineup_window_before_minutes=args.lineup_window_before_minutes,
                    lineup_grace_after_minutes=args.lineup_grace_after_minutes,
                    close_window_before_minutes=args.close_window_before_minutes,
                    include_distant=args.include_distant_fixtures,
                    include_confirmed=args.include_confirmed,
                )
                if tier is None:
                    continue
                if already_confirmed and tier != "close" and not args.include_confirmed:
                    continue
                minutes_to_kickoff = int((kickoff_utc - now_utc).total_seconds() // 60)
                fixtures_by_league.setdefault(league_key, []).append(
                    FixtureWindow(
                        tier=tier,
                        kickoff_utc=kickoff_utc,
                        minutes_to_kickoff=minutes_to_kickoff,
                        home_team=home_name,
                        away_team=away_name,
                        match_id=match_id,
                        already_confirmed=already_confirmed,
                    )
                )

    tier_priority = {"close": 0, "lineup": 1, "grace": 2, "distant": 3}
    cadence_map = {"close": args.hot_cadence, "lineup": args.hot_cadence, "grace": args.hot_cadence, "distant": 0, "off": 0}
    payload = {
        "generated_at": now_utc.replace(microsecond=0).isoformat(),
        "mode": "official-lineup-window",
        "lookahead_hours": args.lookahead_hours,
        "lineup_window_before_minutes": args.lineup_window_before_minutes,
        "lineup_grace_after_minutes": args.lineup_grace_after_minutes,
        "close_window_before_minutes": args.close_window_before_minutes,
        "leagues": [],
    }

    for league_key in requested_leagues:
        config = LEAGUE_CONFIGS.get(league_key)
        if not config:
            continue
        fixtures = sorted(
            fixtures_by_league.get(league_key, []),
            key=lambda item: (tier_priority.get(item.tier, 99), item.kickoff_utc),
        )
        active_fixtures = [
            item
            for item in fixtures
            if (item.tier in {"lineup", "grace"} and not item.already_confirmed) or item.tier == "close"
        ]
        tier = active_fixtures[0].tier if active_fixtures else "off"
        next_kickoff_source = active_fixtures[0] if active_fixtures else (fixtures[0] if fixtures else None)
        next_kickoff = (
            next_kickoff_source.kickoff_utc.isoformat().replace("+00:00", "Z")
            if next_kickoff_source is not None
            else ""
        )
        payload["leagues"].append(
            {
                "league": league_key,
                "label": config["label"],
                "tier": tier,
                "cadence_minutes": cadence_map[tier],
                "active_fixture_count": len(active_fixtures),
                "lineup_count": sum(1 for item in active_fixtures if item.tier == "lineup"),
                "grace_count": sum(1 for item in active_fixtures if item.tier == "grace"),
                "close_count": sum(1 for item in active_fixtures if item.tier == "close"),
                "distant_count": sum(1 for item in fixtures if item.tier == "distant"),
                "stored_confirmed_count": len(confirmed_by_league.get(league_key, set())),
                "next_kickoff_utc": next_kickoff,
                "fixtures": [
                    {
                        "match_id": item.match_id,
                        "home_team": item.home_team,
                        "away_team": item.away_team,
                        "tier": item.tier,
                        "kickoff_utc": item.kickoff_utc.isoformat().replace("+00:00", "Z"),
                        "minutes_to_kickoff": item.minutes_to_kickoff,
                        "already_confirmed": item.already_confirmed,
                    }
                    for item in (active_fixtures or fixtures)[:6]
                ],
            }
        )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
