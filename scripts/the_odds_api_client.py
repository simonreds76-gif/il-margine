#!/usr/bin/env python3
"""
Shared client for The Odds API (the-odds-api.com).

Handles:
  - Auth via THE_ODDS_API_KEY from .env.local
  - Rate limiting (0.35s between requests)
  - Caching recent responses to disk
  - Market-specific helpers for corners, cards, goals, shots

Usage:
  from the_odds_api_client import OddsApiClient

  client = OddsApiClient()
  events = client.get_upcoming_events("soccer_epl")
  odds = client.get_event_corner_odds(event_id, sport_key="soccer_epl")
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://api.the-odds-api.com/v4"
CACHE_DIR = ROOT / "data" / ".odds-api-cache"
REQUEST_DELAY = 0.35
DEFAULT_REGIONS = "uk,eu"

SPORT_KEYS = {
    "epl": "soccer_epl",
    "serie-a": "soccer_italy_serie_a",
    "la-liga": "soccer_spain_la_liga",
    "bundesliga": "soccer_germany_bundesliga",
    "ligue-1": "soccer_france_ligue_one",
}

CORNER_MARKET = "alternate_totals_corners"
CORNER_HANDICAP_MARKET = "alternate_spreads_corners"
CARDS_MARKET = "alternate_totals_cards"
PLAYER_SHOTS_MARKET = "player_shots"
PLAYER_SOT_MARKET = "player_shots_on_target"

ALL_SOCCER_EXTRA_MARKETS = [
    CORNER_MARKET,
    CORNER_HANDICAP_MARKET,
    PLAYER_SHOTS_MARKET,
    PLAYER_SOT_MARKET,
]


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


def _get_api_key() -> str:
    load_env()
    key = os.environ.get("THE_ODDS_API_KEY") or os.environ.get("THEODDS_API_KEY")
    if not key:
        raise RuntimeError(
            "THE_ODDS_API_KEY not found. "
            "Sign up free at https://the-odds-api.com and add your key to .env.local"
        )
    return key


class OddsApiClient:
    def __init__(self, api_key: Optional[str] = None, cache_ttl_minutes: int = 30):
        self.api_key = api_key or _get_api_key()
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._last_request_time = 0.0
        self.remaining_credits: Optional[int] = None
        self.used_credits: Optional[int] = None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

    def _cache_key(self, url: str, params: Dict[str, Any]) -> str:
        raw = f"{url}|{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_cached(self, cache_key: str) -> Optional[Any]:
        path = CACHE_DIR / f"{cache_key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(data["_cached_at"])
            if datetime.now(timezone.utc) - ts > self.cache_ttl:
                return None
            return data["payload"]
        except (json.JSONDecodeError, KeyError):
            return None

    def _set_cache(self, cache_key: str, payload: Any) -> None:
        path = CACHE_DIR / f"{cache_key}.json"
        data = {
            "_cached_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _request(self, url: str, params: Optional[Dict[str, Any]] = None, use_cache: bool = True) -> Any:
        params = params or {}
        params["apiKey"] = self.api_key

        if use_cache:
            ck = self._cache_key(url, {k: v for k, v in params.items() if k != "apiKey"})
            cached = self._get_cached(ck)
            if cached is not None:
                return cached

        self._rate_limit()
        resp = requests.get(url, params=params, timeout=30)
        self._last_request_time = time.time()

        self.remaining_credits = resp.headers.get("x-requests-remaining")
        self.used_credits = resp.headers.get("x-requests-used")

        if resp.status_code == 401:
            raise RuntimeError("Invalid API key. Check THE_ODDS_API_KEY in .env.local")
        if resp.status_code == 429:
            raise RuntimeError(
                f"Rate limited / quota exceeded. "
                f"Remaining: {self.remaining_credits}, Used: {self.used_credits}"
            )
        resp.raise_for_status()

        data = resp.json()
        if use_cache:
            self._set_cache(ck, data)
        return data

    def get_credits_remaining(self) -> Optional[int]:
        return int(self.remaining_credits) if self.remaining_credits else None

    # ── Events ─────────────────────────────────────────────────────

    def get_upcoming_events(self, sport_key: str) -> List[dict]:
        url = f"{BASE_URL}/sports/{sport_key}/events"
        return self._request(url)

    def get_upcoming_events_for_league(self, league: str) -> List[dict]:
        sport_key = SPORT_KEYS.get(league)
        if not sport_key:
            raise ValueError(f"Unknown league: {league}. Valid: {list(SPORT_KEYS)}")
        return self.get_upcoming_events(sport_key)

    # ── Standard odds (h2h, totals, spreads) ───────────────────────

    def get_odds(
        self, sport_key: str, markets: str = "h2h",
        regions: str = DEFAULT_REGIONS,
    ) -> List[dict]:
        url = f"{BASE_URL}/sports/{sport_key}/odds"
        return self._request(url, {"regions": regions, "markets": markets, "oddsFormat": "decimal"})

    # ── Event-level odds (corners, cards, etc.) ────────────────────

    def get_event_odds(
        self, event_id: str, sport_key: str,
        markets: str = CORNER_MARKET,
        regions: str = DEFAULT_REGIONS,
    ) -> dict:
        url = f"{BASE_URL}/sports/{sport_key}/events/{event_id}/odds"
        return self._request(url, {
            "regions": regions, "markets": markets, "oddsFormat": "decimal",
        })

    def get_event_corner_odds(
        self, event_id: str, sport_key: str,
        regions: str = DEFAULT_REGIONS,
    ) -> dict:
        return self.get_event_odds(event_id, sport_key, markets=CORNER_MARKET, regions=regions)

    def get_event_cards_odds(
        self, event_id: str, sport_key: str,
        regions: str = DEFAULT_REGIONS,
    ) -> dict:
        return self.get_event_odds(event_id, sport_key, markets=CARDS_MARKET, regions=regions)

    def get_event_player_shots_odds(
        self, event_id: str, sport_key: str,
        regions: str = "us,eu,uk",
    ) -> dict:
        return self.get_event_odds(
            event_id, sport_key,
            markets=f"{PLAYER_SHOTS_MARKET},{PLAYER_SOT_MARKET}",
            regions=regions,
        )

    # ── Convenience: all corner O/U for a league ──────────────────

    def get_all_corner_odds(self, league: str, regions: str = DEFAULT_REGIONS) -> List[dict]:
        """
        Fetch corner O/U odds for all upcoming events in a league.
        Cost: 1 credit per event.
        """
        sport_key = SPORT_KEYS.get(league)
        if not sport_key:
            raise ValueError(f"Unknown league: {league}. Valid: {list(SPORT_KEYS)}")

        events = self.get_upcoming_events(sport_key)
        results = []
        for event in events:
            try:
                odds_data = self.get_event_corner_odds(event["id"], sport_key, regions=regions)
                results.append(odds_data)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    continue
                raise
        return results

    # ── Parse helpers ──────────────────────────────────────────────

    @staticmethod
    def extract_corner_lines(event_odds: dict) -> List[dict]:
        """
        Extract corner O/U lines from event odds response.

        Returns list of dicts: {bookmaker, line, over_odds, under_odds}
        """
        lines = []
        for bm in event_odds.get("bookmakers", []):
            bm_key = bm.get("key", "")
            bm_title = bm.get("title", "")
            for market in bm.get("markets", []):
                if market.get("key") != CORNER_MARKET:
                    continue
                outcomes = market.get("outcomes", [])
                over_by_line: Dict[float, float] = {}
                under_by_line: Dict[float, float] = {}
                for o in outcomes:
                    name = (o.get("name") or "").lower()
                    point = o.get("point")
                    price = o.get("price")
                    if point is None or price is None:
                        continue
                    if name == "over":
                        over_by_line[float(point)] = float(price)
                    elif name == "under":
                        under_by_line[float(point)] = float(price)
                for line_val in sorted(set(over_by_line) & set(under_by_line)):
                    lines.append({
                        "bookmaker": bm_title,
                        "bookmaker_key": bm_key,
                        "line": line_val,
                        "over_odds": over_by_line[line_val],
                        "under_odds": under_by_line[line_val],
                    })
        return lines


    @staticmethod
    def extract_player_shots(event_odds: dict) -> List[dict]:
        """
        Extract player shots O/U from event odds response.

        Returns list of dicts:
          {bookmaker, market, player, team, line, side, odds, description}
        """
        rows: List[dict] = []
        home = event_odds.get("home_team", "")
        away = event_odds.get("away_team", "")

        for bm in event_odds.get("bookmakers", []):
            bm_key = bm.get("key", "")
            bm_title = bm.get("title", "")
            for market in bm.get("markets", []):
                mkey = market.get("key", "")
                if mkey not in (PLAYER_SHOTS_MARKET, PLAYER_SOT_MARKET):
                    continue
                for o in market.get("outcomes", []):
                    name = (o.get("name") or "").strip()
                    point = o.get("point")
                    price = o.get("price")
                    desc = (o.get("description") or "").strip()
                    if point is None or price is None or not desc:
                        continue
                    side = name.lower()
                    if side not in ("over", "under"):
                        continue
                    rows.append({
                        "bookmaker": bm_title,
                        "bookmaker_key": bm_key,
                        "market": mkey,
                        "player": desc,
                        "home_team": home,
                        "away_team": away,
                        "line": float(point),
                        "side": side,
                        "odds": float(price),
                    })
        return rows


if __name__ == "__main__":
    client = OddsApiClient()
    print("Testing The Odds API connection...")
    for league, sport_key in SPORT_KEYS.items():
        try:
            events = client.get_upcoming_events(sport_key)
            print(f"  {league}: {len(events)} upcoming events")
            if events:
                ev = events[0]
                print(f"    First: {ev.get('home_team')} vs {ev.get('away_team')} @ {ev.get('commence_time')}")
        except Exception as e:
            print(f"  {league}: ERROR - {e}")
    credits = client.get_credits_remaining()
    if credits is not None:
        print(f"\nCredits remaining: {credits}")
