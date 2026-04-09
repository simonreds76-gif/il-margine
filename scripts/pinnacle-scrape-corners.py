#!/usr/bin/env python3
"""
Scrape Pinnacle corners O/U odds for Big 5 leagues.

Uses the same Pinnacle guest API as pinnacle-scrape-odds.py (tennis).
Appends new snapshots to data/corners-ou/pinnacle-corners-odds.csv.

Market detection: 'total' markets at period=0 with line >= 7.0 are corners.
Goals totals sit at lines 1.5-5.5 - no ambiguity.

Run this before/after placing corners bets to build a CLV log.
One snapshot per (match, line, side) per calendar day is stored.

Usage:
  python scripts/pinnacle-scrape-corners.py
  python scripts/pinnacle-scrape-corners.py --dry-run
  python scripts/pinnacle-scrape-corners.py --verbose
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "corners-ou" / "pinnacle-corners-odds.csv"

PINNACLE_API_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PINNACLE_API_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"

_HEADERS = {
    "X-API-Key": PINNACLE_API_KEY,
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
}

# Big 5 league IDs - verified against live API 2026-04-09
LEAGUES: Dict[str, int] = {
    "epl":        1980,   # England - Premier League
    "la-liga":    2196,   # Spain - La Liga
    "serie-a":    2436,   # Italy - Serie A
    "bundesliga": 1842,   # Germany - Bundesliga
    "ligue-1":    2036,   # France - Ligue 1
}

# Corners lines only: goals totals are always <= 6.5, corners >= 7.0
CORNERS_LINE_MIN = 7.0

OUTPUT_FIELDS = [
    "captured_at", "league", "match_date", "kickoff_iso",
    "home_team", "away_team",
    "line", "side", "odds_decimal", "odds_american",
]


def _get(path: str, retries: int = 3) -> list | dict:
    url = f"{PINNACLE_API_BASE}/{path.lstrip('/')}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt
                print(f"    [rate-limit] sleeping {wait}s")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {retries} retries: {url}")


def _american_to_decimal(american: float) -> float:
    if american > 0:
        return round(american / 100 + 1, 4)
    return round(100 / abs(american) + 1, 4)


def _scrape_league(
    league_key: str,
    league_id: int,
    captured_at: str,
    verbose: bool,
) -> List[Dict]:
    rows: List[Dict] = []
    try:
        matchups = _get(f"leagues/{league_id}/matchups?withSpecials=false&brandId=0")
    except Exception as e:
        print(f"  [{league_key}] WARN: could not fetch matchups: {e}")
        return rows

    regular = [m for m in matchups if m.get("type") != "special"]
    print(f"  {league_key}: {len(regular)} matches")

    for match in regular:
        participants = match.get("participants", [])
        home = next((p["name"] for p in participants if p.get("alignment") == "home"), "")
        away = next((p["name"] for p in participants if p.get("alignment") == "away"), "")
        if not home or not away:
            continue

        kickoff_iso = match.get("startTime", "")
        match_date = kickoff_iso[:10] if kickoff_iso else ""
        matchup_id = match.get("id")

        try:
            markets = _get(f"matchups/{matchup_id}/markets/related/straight")
        except Exception as e:
            if verbose:
                print(f"    [{home} v {away}] WARN: {e}")
            continue

        for mkt in markets:
            if mkt.get("type") != "total":
                continue
            if mkt.get("period") != 0:
                continue
            if mkt.get("status") != "open":
                continue

            # Key format: s;0;ou;{line}
            parts = mkt.get("key", "").split(";")
            if len(parts) < 4:
                continue
            try:
                line = float(parts[3])
            except ValueError:
                continue

            if line < CORNERS_LINE_MIN:
                continue

            for price in mkt.get("prices", []):
                side = price.get("designation", "")  # "over" or "under"
                american = price.get("price")
                if not side or american is None:
                    continue

                rows.append({
                    "captured_at": captured_at,
                    "league": league_key,
                    "match_date": match_date,
                    "kickoff_iso": kickoff_iso,
                    "home_team": home,
                    "away_team": away,
                    "line": line,
                    "side": side,
                    "odds_decimal": _american_to_decimal(float(american)),
                    "odds_american": int(american),
                })

        time.sleep(0.1)  # be gentle between matchup requests

    return rows


def _load_existing_keys(path: Path) -> set:
    """Return set of (match_date, home, away, line, side, capture_day) already stored."""
    keys: set = set()
    if not path.exists():
        return keys
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            keys.add((
                row.get("match_date", ""),
                (row.get("home_team") or "").lower(),
                (row.get("away_team") or "").lower(),
                str(row.get("line", "")),
                (row.get("side") or "").lower(),
                (row.get("captured_at") or "")[:10],
            ))
    return keys


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Pinnacle corners O/U odds (Big 5)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not write")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("=" * 50)
    print("  Pinnacle Corners Odds Scraper")
    print("=" * 50)

    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = captured_at[:10]

    existing_keys = _load_existing_keys(args.output)
    print(f"  Existing snapshots: {len(existing_keys)}")
    print(f"  Capture time:       {captured_at}\n")

    all_new: List[Dict] = []
    for league_key, league_id in LEAGUES.items():
        rows = _scrape_league(league_key, league_id, captured_at, args.verbose)
        for row in rows:
            k = (
                row["match_date"],
                row["home_team"].lower(),
                row["away_team"].lower(),
                str(row["line"]),
                row["side"].lower(),
                today,
            )
            if k not in existing_keys:
                all_new.append(row)
                existing_keys.add(k)
        time.sleep(0.3)

    print(f"\n  New rows: {len(all_new)}")

    if not all_new:
        print("  Nothing new to write.")
        return

    if args.dry_run:
        print("  [dry-run] sample:")
        for row in all_new[:4]:
            print(f"    {row['match_date']}  {row['home_team']} v {row['away_team']}"
                  f"  {row['side']:5s} {row['line']}  {row['odds_decimal']}")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_header = not args.output.exists()
    with open(args.output, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(all_new)

    print(f"  Written -> {args.output}")
    print("=" * 50)


if __name__ == "__main__":
    main()
