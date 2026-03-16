#!/usr/bin/env python3
"""
Download league logos from FotMob and store them locally for the penalty page.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "league-logos"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.fotmob.com/",
}

LEAGUES = {
    "serie-a": 55,
    "epl": 47,
    "la-liga": 87,
    "bundesliga": 54,
    "ligue-1": 53,
}


def cache_league_logos(force: bool) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        for slug, league_id in LEAGUES.items():
            out_path = OUT_DIR / f"{slug}.png"
            if out_path.exists() and not force:
                continue
            url = f"https://images.fotmob.com/image_resources/logo/leaguelogo/{league_id}.png"
            response = session.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            out_path.write_bytes(response.content)
            print(f"cached {slug} -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache FotMob league logos locally")
    parser.add_argument("--force", action="store_true", help="Redownload logos even if they already exist")
    args = parser.parse_args()
    cache_league_logos(force=args.force)


if __name__ == "__main__":
    main()
