#!/usr/bin/env python3
"""
Scrape Pinnacle anytime-goalscorer markets from the guest API.

Current default scope:
  - sport: Soccer
  - league: Italy - Serie A
  - market: Player Props / "<Player> To Score"

The output is already in the canonical format expected by
`goalscorer-odds-archive.py`, so it can be dropped straight into the inbox or
fed directly into the archive step.
"""

from __future__ import annotations

import argparse
import csv
import glob
import html
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests


PINNACLE_API_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PINNACLE_API_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
SOCCER_SPORT_ID = 29
DEFAULT_LEAGUE_NAME = "Italy - Serie A"
DEFAULT_OUT_DIR = "data/goalscorer/inbox"

API_HEADERS = {
    "X-API-Key": PINNACLE_API_KEY,
    "Referer": "https://www.pinnacle.com/",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def american_to_decimal(american: int | float) -> float:
    american = int(american)
    if american >= 100:
        return round(1 + american / 100.0, 4)
    if american <= -100:
        return round(1 + 100.0 / abs(american), 4)
    return 0.0


def _norm_text(value: str) -> str:
    normalized = html.unescape((value or "").strip().lower())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", cleaned).strip()


def _api_get(path: str) -> list | dict | None:
    url = f"{PINNACLE_API_BASE}/{path.lstrip('/')}"
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=20)
    except requests.RequestException as exc:
        print(f"  Network error for {path}: {exc}")
        return None
    if not response.ok:
        print(f"  API error for {path}: {response.status_code}")
        return None
    return response.json()


def _expand_paths(paths: Iterable[str]) -> List[str]:
    expanded: List[str] = []
    for path in paths:
        if "*" in path or "?" in path:
            expanded.extend(glob.glob(path))
        else:
            expanded.append(path)
    return [path for path in expanded if os.path.exists(path)]


def _load_player_team_map(paths: Iterable[str]) -> Dict[str, tuple[str, str]]:
    latest_by_player: Dict[str, tuple[str, str]] = {}
    for path in _expand_paths(paths):
        with open(path, "r", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                player = (row.get("player_name") or "").strip()
                team = (row.get("team") or "").strip()
                match_date = (row.get("match_date") or "").strip()
                if not player or not team or not match_date:
                    continue
                key = _norm_text(player)
                current = latest_by_player.get(key)
                if current is None or match_date > current[1]:
                    latest_by_player[key] = (team, match_date)
    return latest_by_player


def _extract_player_name(description: str) -> str:
    text = (description or "").strip()
    return re.sub(r"\s+To Score$", "", text, flags=re.I).strip()


def scrape_pinnacle_goalscorer(
    league_name: str,
    player_team_map: Dict[str, tuple[str, str]],
) -> List[dict]:
    leagues = _api_get(f"sports/{SOCCER_SPORT_ID}/leagues?all=false")
    if not leagues:
        return []

    target = next((league for league in leagues if (league.get("name") or "").strip() == league_name), None)
    if target is None:
        print(f"  League not found on Pinnacle: {league_name}")
        return []

    league_id = target["id"]
    matchups = _api_get(f"leagues/{league_id}/matchups")
    markets = _api_get(f"leagues/{league_id}/markets/straight")
    if not matchups or not markets:
        return []

    parent_matches: Dict[int, dict] = {}
    for matchup in matchups:
        parts = matchup.get("participants", [])
        if len(parts) != 2:
            continue
        if matchup.get("type") != "matchup":
            continue
        if matchup.get("special"):
            continue
        home = next((p for p in parts if p.get("alignment") == "home"), None)
        away = next((p for p in parts if p.get("alignment") == "away"), None)
        if not home or not away:
            continue
        parent_matches[matchup["id"]] = {
            "match_date": str(matchup.get("startTime") or "")[:10],
            "home_team": home.get("name", ""),
            "away_team": away.get("name", ""),
        }

    moneylines_by_matchup: Dict[int, dict] = {}
    for market in markets:
        if market.get("type") != "moneyline" or market.get("period") != 0:
            continue
        prices = market.get("prices", []) or []
        if not prices:
            continue
        moneylines_by_matchup[market["matchupId"]] = market

    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows: List[dict] = []

    for matchup in matchups:
        special = matchup.get("special") or {}
        if special.get("category") != "Player Props":
            continue
        description = special.get("description") or ""
        if not re.search(r"\bTo Score$", description, flags=re.I):
            continue

        parent_id = matchup.get("parentId")
        parent = parent_matches.get(parent_id)
        market = moneylines_by_matchup.get(matchup["id"])
        if not parent or not market:
            continue

        yes_participant = next((p for p in matchup.get("participants", []) if p.get("name") == "Yes"), None)
        if yes_participant is None:
            continue
        yes_price = next(
            (price.get("price") for price in market.get("prices", []) if price.get("participantId") == yes_participant.get("id")),
            None,
        )
        if yes_price is None:
            continue

        player_name = _extract_player_name(description)
        player_team = player_team_map.get(_norm_text(player_name), ("", ""))[0]
        no_price = next(
            (price.get("price") for price in market.get("prices", []) if price.get("participantId") != yes_participant.get("id")),
            None,
        )
        odds_decimal = american_to_decimal(yes_price)
        if odds_decimal <= 1.0:
            continue

        rows.append(
            {
                "captured_at": captured_at,
                "match_date": parent["match_date"],
                "bookmaker": "Pinnacle",
                "competition": "Serie A",
                "market": "ATGS",
                "home_team": parent["home_team"],
                "away_team": parent["away_team"],
                "player_name": player_name,
                "player_team": player_team,
                "odds_decimal": f"{odds_decimal:.4f}",
                "source": "pinnacle_guest_api",
                "notes": f"matchup_id={matchup['id']};no_american={no_price}",
            }
        )

    return rows


def write_rows(rows: List[dict], out_dir: str, out_file: str = "", dry_run: bool = False) -> Optional[str]:
    fieldnames = [
        "captured_at",
        "match_date",
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
        f"pinnacle-atgs-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv",
    )
    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Pinnacle Serie A anytime-goalscorer prices")
    parser.add_argument("--league-name", default=DEFAULT_LEAGUE_NAME)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-file", default="")
    parser.add_argument(
        "--team-map",
        nargs="+",
        default=["data/goalscorer/serie-a-player-match-logs-*.csv"],
        help="Historical player-log CSVs used to infer player_team",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Pinnacle Goalscorer Scraper")
    print("=" * 64)

    player_team_map = _load_player_team_map(args.team_map)
    rows = scrape_pinnacle_goalscorer(args.league_name, player_team_map)
    print(f"  Rows scraped: {len(rows):,}")
    if rows:
        sample = rows[0]
        print(
            "  Sample: "
            f"{sample['home_team']} vs {sample['away_team']} | "
            f"{sample['player_name']} @ {sample['odds_decimal']}"
        )
    if args.dry_run:
        print("  Dry run only; no file written.")
        print("\n  Done.\n")
        return

    output = write_rows(rows, args.out_dir, out_file=args.out_file, dry_run=False)
    print(f"  Saved: {output}")
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
