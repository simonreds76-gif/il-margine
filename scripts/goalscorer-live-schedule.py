#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import requests


MATCHES_URL = "https://www.fotmob.com/api/data/matches"
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


@dataclass
class FixtureWindow:
    tier: str
    kickoff_utc: datetime
    minutes_to_kickoff: int
    home_team: str
    away_team: str
    match_id: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a lightweight goalscorer cadence plan from FotMob fixtures.")
    parser.add_argument("--leagues", default=",".join(LEAGUE_CONFIGS.keys()), help="Comma-separated league keys")
    parser.add_argument("--lookahead-hours", type=int, default=12, help="Only consider fixtures within this window")
    parser.add_argument("--cold-minutes", type=int, default=180, help="Cold tier starts above this many minutes")
    parser.add_argument("--warm-minutes", type=int, default=60, help="Warm tier starts above this many minutes")
    parser.add_argument("--hot-cadence", type=int, default=10, help="Cadence in minutes for hot fixtures")
    parser.add_argument("--warm-cadence", type=int, default=30, help="Cadence in minutes for warm fixtures")
    parser.add_argument("--cold-cadence", type=int, default=120, help="Cadence in minutes for cold fixtures")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    return parser.parse_args()


def _fotmob_dates(now_utc: datetime) -> List[str]:
    today = now_utc.astimezone(timezone.utc).date()
    return [(today + timedelta(days=offset)).strftime("%Y%m%d") for offset in range(2)]


def _parse_kickoff(match: dict) -> datetime | None:
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


def _is_live_or_finished(match: dict) -> bool:
    status = match.get("status", {}) or {}
    if bool(status.get("finished")) or bool(status.get("cancelled")):
        return True
    if bool(status.get("started")):
        return True
    return False


def _classify_fixture(now_utc: datetime, kickoff_utc: datetime, warm_minutes: int, cold_minutes: int) -> str | None:
    delta_minutes = int((kickoff_utc - now_utc).total_seconds() // 60)
    if delta_minutes < 0:
        return None
    if delta_minutes <= warm_minutes:
        return "hot"
    if delta_minutes <= cold_minutes:
        return "warm"
    return "cold"


def fetch_daily_payload(date_str: str) -> dict:
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

    fixtures_by_league: Dict[str, List[FixtureWindow]] = {league: [] for league in requested_leagues if league in LEAGUE_CONFIGS}
    for date_str in _fotmob_dates(now_utc):
        payload = fetch_daily_payload(date_str)
        for league in payload.get("leagues", []):
            league_id = league.get("id")
            league_key = league_ids.get(league_id)
            if not league_key:
                continue
            for match in league.get("matches", []):
                if _is_live_or_finished(match):
                    continue
                kickoff_utc = _parse_kickoff(match)
                if kickoff_utc is None or kickoff_utc > lookahead_limit:
                    continue
                tier = _classify_fixture(now_utc, kickoff_utc, args.warm_minutes, args.cold_minutes)
                if tier is None:
                    continue
                minutes_to_kickoff = int((kickoff_utc - now_utc).total_seconds() // 60)
                fixtures_by_league.setdefault(league_key, []).append(
                    FixtureWindow(
                        tier=tier,
                        kickoff_utc=kickoff_utc,
                        minutes_to_kickoff=minutes_to_kickoff,
                        home_team=str(match.get("home", {}).get("name") or "").strip(),
                        away_team=str(match.get("away", {}).get("name") or "").strip(),
                        match_id=int(match.get("id")) if match.get("id") else None,
                    )
                )

    tier_priority = {"hot": 0, "warm": 1, "cold": 2}
    cadence_map = {"hot": args.hot_cadence, "warm": args.warm_cadence, "cold": args.cold_cadence, "off": 0}
    payload = {
        "generated_at": now_utc.replace(microsecond=0).isoformat(),
        "lookahead_hours": args.lookahead_hours,
        "cold_minutes": args.cold_minutes,
        "warm_minutes": args.warm_minutes,
        "leagues": [],
    }

    for league_key in requested_leagues:
        config = LEAGUE_CONFIGS.get(league_key)
        if not config:
            continue
        fixtures = sorted(
            fixtures_by_league.get(league_key, []),
            key=lambda item: (tier_priority[item.tier], item.kickoff_utc),
        )
        tier = fixtures[0].tier if fixtures else "off"
        next_kickoff = fixtures[0].kickoff_utc.isoformat().replace("+00:00", "Z") if fixtures else ""
        payload["leagues"].append(
            {
                "league": league_key,
                "label": config["label"],
                "tier": tier,
                "cadence_minutes": cadence_map[tier],
                "active_fixture_count": len(fixtures),
                "hot_count": sum(1 for item in fixtures if item.tier == "hot"),
                "warm_count": sum(1 for item in fixtures if item.tier == "warm"),
                "cold_count": sum(1 for item in fixtures if item.tier == "cold"),
                "next_kickoff_utc": next_kickoff,
                "fixtures": [
                    {
                        "match_id": item.match_id,
                        "home_team": item.home_team,
                        "away_team": item.away_team,
                        "tier": item.tier,
                        "kickoff_utc": item.kickoff_utc.isoformat().replace("+00:00", "Z"),
                        "minutes_to_kickoff": item.minutes_to_kickoff,
                    }
                    for item in fixtures[:6]
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
