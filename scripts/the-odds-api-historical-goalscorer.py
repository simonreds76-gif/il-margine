#!/usr/bin/env python3
"""
Fetch historical Serie A anytime-goalscorer odds from The Odds API.

This script is designed for backfilling historical ATGS snapshots into the same
canonical CSV shape used by the live goalscorer archive/import flow.

Workflow:
  1. Load historical Serie A fixtures from our player-log CSVs.
  2. Discover matching The Odds API event ids for those dates/fixtures.
  3. Fetch one historical odds snapshot per event at one or more offsets before kickoff.
  4. Write canonical odds CSV rows ready for `goalscorer-odds-archive.py`.

Notes:
  - The Odds API historical player props require a paid key.
  - Soccer player props are currently limited to supported regions/bookmakers.
  - This script uses the event-specific historical endpoint because player props
    are event-level markets.
"""

from __future__ import annotations

import argparse
import csv
import glob
import html
import os
import re
import time
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests


ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "soccer_italy_serie_a"
MARKET_KEY = "player_goal_scorer_anytime"
DEFAULT_DATA_GLOB = "data/goalscorer/serie-a-player-match-logs-*.csv"
DEFAULT_OUT_DIR = "data/goalscorer/inbox"
DEFAULT_REGIONS = "us"
DEFAULT_OFFSETS = "60"
DEFAULT_EVENT_SCAN_HOURS = "06,12,18"
REQUEST_DELAY = 0.35


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _norm_text(value: str) -> str:
    normalized = html.unescape((value or "").strip().lower())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", cleaned).strip()


TEAM_ALIASES = {
    "ac milan": "milan",
    "milan": "milan",
    "inter": "inter",
    "inter milan": "inter",
    "internazionale": "inter",
    "as roma": "roma",
    "roma": "roma",
    "lazio": "lazio",
    "lazio rome": "lazio",
    "ss lazio": "lazio",
    "hellas verona": "verona",
    "verona": "verona",
    "juventus": "juventus",
    "juventus fc": "juventus",
    "como 1907": "como",
    "como": "como",
    "us cremonese": "cremonese",
    "cremonese": "cremonese",
    "acf fiorentina": "fiorentina",
    "fiorentina": "fiorentina",
    "cagliari calcio": "cagliari",
    "cagliari": "cagliari",
    "pisa sc": "pisa",
    "pisa": "pisa",
    "sassuolo calcio": "sassuolo",
    "sassuolo": "sassuolo",
    "bologna fc": "bologna",
    "bologna fc 1909": "bologna",
    "bologna": "bologna",
    "atalanta bc": "atalanta",
    "atalanta": "atalanta",
    "empoli fc": "empoli",
    "empoli": "empoli",
    "genoa cfc": "genoa",
    "genoa": "genoa",
    "us lecce": "lecce",
    "lecce": "lecce",
    "ac monza": "monza",
    "monza": "monza",
    "ssc napoli": "napoli",
    "napoli": "napoli",
    "parma calcio 1913": "parma",
    "parma": "parma",
    "torino fc": "torino",
    "torino": "torino",
    "udinese calcio": "udinese",
    "udinese": "udinese",
    "venezia fc": "venezia",
    "venezia": "venezia",
}


def _team_key(name: str) -> str:
    return TEAM_ALIASES.get(_norm_text(name), _norm_text(name))


def _expand_paths(paths: Iterable[str]) -> List[str]:
    expanded: List[str] = []
    for path in paths:
        if "*" in path or "?" in path:
            expanded.extend(glob.glob(path))
        else:
            expanded.append(path)
    return [path for path in expanded if os.path.exists(path)]


def _parse_date(value: str) -> Optional[date]:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _parse_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "y", "yes"}


def _parse_float(value, default: Optional[float] = None) -> Optional[float]:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _match_key(match_date: str, home_team: str, away_team: str) -> tuple[str, str]:
    teams = sorted([_team_key(home_team), _team_key(away_team)])
    return match_date, " | ".join(teams)


def _parse_iso_dt(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_fixture_targets(paths: List[str], date_from: Optional[date], date_to: Optional[date]) -> List[dict]:
    fixtures: Dict[tuple[str, str], dict] = {}
    for path in _expand_paths(paths):
        with open(path, "r", encoding="utf-8-sig") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = list(csv.DictReader(handle, dialect=dialect))
        print(f"  Loaded {len(rows):,} rows from {os.path.basename(path)}")

        for row in rows:
            match_date = _parse_date(row.get("match_date") or row.get("date") or "")
            if match_date is None:
                continue
            if date_from and match_date < date_from:
                continue
            if date_to and match_date > date_to:
                continue

            team = (row.get("team") or "").strip()
            opponent = (row.get("opponent") or "").strip()
            if not team or not opponent:
                continue
            is_home = _parse_bool(row.get("is_home") or "")
            home_team = team if is_home else opponent
            away_team = opponent if is_home else team
            key = _match_key(match_date.isoformat(), home_team, away_team)
            existing = fixtures.get(key)
            if existing is None:
                fixtures[key] = {
                    "match_date": match_date.isoformat(),
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_key": key,
                }
    return sorted(fixtures.values(), key=lambda row: (row["match_date"], row["home_team"], row["away_team"]))


def fetch_json(path: str, params: dict, allow_not_found: bool = False) -> dict | list | None:
    response = requests.get(f"{BASE_URL}/{path.lstrip('/')}", params=params, timeout=40)
    if allow_not_found and response.status_code == 404:
        if REQUEST_DELAY > 0:
            time.sleep(REQUEST_DELAY)
        return None
    response.raise_for_status()
    if REQUEST_DELAY > 0:
        time.sleep(REQUEST_DELAY)
    return response.json()


def _unwrap_data(payload: dict | list) -> dict | list:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def discover_events(
    api_key: str,
    fixtures: List[dict],
    event_scan_hours: List[int],
) -> tuple[List[dict], dict]:
    fixtures_by_key = {fixture["match_key"]: fixture for fixture in fixtures}
    fixture_dates = sorted({fixture["match_date"] for fixture in fixtures})
    found_by_key: Dict[tuple[str, str], dict] = {}
    stats = {
        "target_fixtures": len(fixtures),
        "matched_events": 0,
        "unmatched_fixtures": 0,
        "event_queries": 0,
    }

    for match_date in fixture_dates:
        for hour in event_scan_hours:
            snapshot_at = f"{match_date}T{hour:02d}:00:00Z"
            payload = fetch_json(
                f"historical/sports/{SPORT_KEY}/events",
                {"apiKey": api_key, "date": snapshot_at},
            )
            stats["event_queries"] += 1
            events = _unwrap_data(payload)
            if not isinstance(events, list):
                continue

            for event in events:
                commence_time = str(event.get("commence_time") or "")
                commence_date = commence_time[:10]
                home_team = str(event.get("home_team") or "")
                away_team = str(event.get("away_team") or "")
                key = _match_key(commence_date, home_team, away_team)
                if key not in fixtures_by_key:
                    continue
                current = found_by_key.get(key)
                if current is None:
                    found_by_key[key] = {
                        "event_id": str(event.get("id") or ""),
                        "match_date": commence_date,
                        "kickoff_at": commence_time,
                        "home_team": home_team,
                        "away_team": away_team,
                        "sport_title": str(event.get("sport_title") or "Serie A"),
                    }

    stats["matched_events"] = len(found_by_key)
    stats["unmatched_fixtures"] = len(fixtures) - len(found_by_key)
    return sorted(found_by_key.values(), key=lambda row: (row["match_date"], row["home_team"])), stats


def _market_is_atgs(key: str, name: str) -> bool:
    if (key or "").strip().lower() == MARKET_KEY:
        return True
    text = (name or "").strip().lower()
    return "anytime" in text and "goal" in text


def _extract_player_name(outcome: dict) -> str:
    name = str(outcome.get("name") or outcome.get("label") or "").strip()
    description = str(outcome.get("description") or "").strip()
    if description and name.lower() in {"yes", "to score", "over"}:
        return description
    if name and name.lower() not in {"yes", "no"}:
        return name
    if description:
        return description
    return name


def extract_canonical_rows(
    payload: dict,
    event_meta: dict,
    bookmaker_filter: set[str],
    requested_at: datetime,
    offset_minutes: int,
) -> List[dict]:
    event = _unwrap_data(payload)
    if not isinstance(event, dict):
        return []

    actual_timestamp = _parse_iso_dt(str(payload.get("timestamp") or "")) or requested_at
    kickoff_dt = _parse_iso_dt(event_meta["kickoff_at"])
    minutes_to_kickoff = (kickoff_dt - actual_timestamp).total_seconds() / 60.0 if kickoff_dt else offset_minutes

    rows: List[dict] = []
    for bookmaker in event.get("bookmakers") or []:
        bookmaker_name = str(bookmaker.get("title") or bookmaker.get("name") or bookmaker.get("key") or "").strip()
        bookmaker_key = _norm_text(bookmaker_name or str(bookmaker.get("key") or ""))
        if bookmaker_filter and bookmaker_key not in bookmaker_filter:
            continue

        for market in bookmaker.get("markets") or []:
            market_key = str(market.get("key") or "")
            market_name = str(market.get("name") or market_key)
            if not _market_is_atgs(market_key, market_name):
                continue

            for outcome in market.get("outcomes") or []:
                player_name = _extract_player_name(outcome)
                odds_decimal = _parse_float(outcome.get("price") or outcome.get("odds") or outcome.get("decimal"))
                if not player_name or odds_decimal is None or odds_decimal <= 1.0:
                    continue
                rows.append(
                    {
                        "captured_at": _iso_z(actual_timestamp),
                        "match_date": event_meta["match_date"],
                        "event_id": event_meta["event_id"],
                        "kickoff_at": event_meta["kickoff_at"],
                        "minutes_to_kickoff": f"{minutes_to_kickoff:.1f}",
                        "snapshot_kind": f"historical_{offset_minutes}m",
                        "bookmaker": bookmaker_name or str(bookmaker.get("key") or "Unknown"),
                        "competition": str(event.get("sport_title") or event_meta["sport_title"] or "Serie A"),
                        "market": "ATGS",
                        "home_team": str(event.get("home_team") or event_meta["home_team"]),
                        "away_team": str(event.get("away_team") or event_meta["away_team"]),
                        "player_name": player_name,
                        "player_team": "",
                        "odds_decimal": f"{odds_decimal:.4f}",
                        "source": "the_odds_api_historical",
                        "notes": f"requested_at={_iso_z(requested_at)};market={market_key or market_name}",
                    }
                )
    return rows


def write_rows(rows: List[dict], out_dir: str, out_file: str = "", dry_run: bool = False) -> Optional[str]:
    fieldnames = [
        "captured_at",
        "match_date",
        "event_id",
        "kickoff_at",
        "minutes_to_kickoff",
        "snapshot_kind",
        "bookmaker",
        "competition",
        "market",
        "home_team",
        "away_team",
        "player_name",
        "player_team",
        "odds_decimal",
        "source",
        "notes",
    ]
    if dry_run:
        return None
    os.makedirs(out_dir, exist_ok=True)
    target = out_file or os.path.join(
        out_dir,
        f"the-odds-api-historical-atgs-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv",
    )
    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch historical Serie A ATGS odds from The Odds API")
    parser.add_argument("--data", nargs="+", default=[DEFAULT_DATA_GLOB], help="Historical player-log CSVs or globs")
    parser.add_argument("--date-from", default="", help="Optional lower match-date bound (YYYY-MM-DD)")
    parser.add_argument("--date-to", default="", help="Optional upper match-date bound (YYYY-MM-DD)")
    parser.add_argument("--regions", default=DEFAULT_REGIONS, help="The Odds API regions parameter")
    parser.add_argument("--bookmakers", default="", help="Optional comma-separated bookmaker titles/keys to keep")
    parser.add_argument("--offset-minutes", default=DEFAULT_OFFSETS, help="Comma-separated kickoff offsets in minutes")
    parser.add_argument("--event-scan-hours", default=DEFAULT_EVENT_SCAN_HOURS, help="Comma-separated UTC hours for event discovery")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-file", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env()
    api_key = (
        os.environ.get("THE_ODDS_API_KEY")
        or os.environ.get("THEODDS_API_KEY")
        or os.environ.get("ODDS_API_V4_KEY")
    )
    if not api_key:
        raise SystemExit("Set THE_ODDS_API_KEY (or ODDS_API_V4_KEY) in .env.local for historical backfill.")

    date_from = _parse_date(args.date_from) if args.date_from else None
    date_to = _parse_date(args.date_to) if args.date_to else None
    offsets = [int(part.strip()) for part in args.offset_minutes.split(",") if part.strip()]
    event_scan_hours = [int(part.strip()) for part in args.event_scan_hours.split(",") if part.strip()]
    bookmaker_filter = {_norm_text(part) for part in args.bookmakers.split(",") if part.strip()}

    print("\n" + "=" * 64)
    print("  IL MARGINE - The Odds API Historical Goalscorer Fetch")
    print("=" * 64)

    fixtures = load_fixture_targets(args.data, date_from, date_to)
    print(f"  Target fixtures:     {len(fixtures):,}")
    if not fixtures:
        print("  No fixtures found for the requested range.")
        return

    events, event_stats = discover_events(api_key, fixtures, event_scan_hours)
    print(f"  Event queries:       {event_stats['event_queries']:,}")
    print(f"  Matched events:      {event_stats['matched_events']:,}")
    print(f"  Unmatched fixtures:  {event_stats['unmatched_fixtures']:,}")
    if not events:
        print("  No historical events discovered. Nothing to fetch.")
        return

    all_rows: List[dict] = []
    missing_event_odds = 0
    for event_meta in events:
        kickoff_dt = _parse_iso_dt(event_meta["kickoff_at"])
        if kickoff_dt is None:
            continue
        for offset_minutes in offsets:
            requested_at = kickoff_dt - timedelta(minutes=offset_minutes)
            payload = fetch_json(
                f"historical/sports/{SPORT_KEY}/events/{event_meta['event_id']}/odds",
                {
                    "apiKey": api_key,
                    "regions": args.regions,
                    "markets": MARKET_KEY,
                    "date": _iso_z(requested_at),
                    "oddsFormat": "decimal",
                },
                allow_not_found=True,
            )
            if payload is None:
                missing_event_odds += 1
                continue
            all_rows.extend(extract_canonical_rows(payload, event_meta, bookmaker_filter, requested_at, offset_minutes))

    print(f"  Missing event odds:  {missing_event_odds:,}")
    print(f"  Canonical rows:      {len(all_rows):,}")
    if all_rows:
        sample = all_rows[0]
        print(
            "  Sample: "
            f"{sample['home_team']} vs {sample['away_team']} | "
            f"{sample['player_name']} @ {sample['odds_decimal']} ({sample['bookmaker']})"
        )

    if args.dry_run:
        print("  Dry run only; no file written.")
        print("\n  Done.\n")
        return

    output = write_rows(all_rows, args.out_dir, out_file=args.out_file, dry_run=False)
    print(f"  Saved: {output}")
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
