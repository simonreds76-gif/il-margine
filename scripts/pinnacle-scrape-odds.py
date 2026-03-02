#!/usr/bin/env python3
"""
Pinnacle tennis odds scraper — API edition.

Uses Pinnacle's public guest API (guest.api.arcadia.pinnacle.com) to fetch
structured JSON for all tennis leagues, matchups, and markets. No more HTML
parsing or Playwright browser automation.

Returns match-winner odds + total-games O/U for ATP & Challenger leagues.

Usage:
  python scripts/pinnacle-scrape-odds.py
  python scripts/pinnacle-scrape-odds.py --dry-run --verbose
  python scripts/pinnacle-scrape-odds.py --include-wta
"""

import csv
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from time import sleep as _sleep

import requests

# ─── Environment ────────────────────────────────────────────────────

def _load_env():
    """Load .env.local from project root."""
    root = Path(__file__).resolve().parent.parent
    for name in [".env.local", "env.local"]:
        path = root / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

_load_env()

# ─── Config ─────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

DRY_RUN = "--dry-run" in sys.argv
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
INCLUDE_WTA = "--include-wta" in sys.argv

# ─── Pinnacle Guest API ────────────────────────────────────────────
#
# This is the same API that Pinnacle's own frontend uses. It's public,
# requires no authentication beyond a static API key, and returns clean
# structured JSON. The key below is extracted from Pinnacle's frontend
# JS bundle and is the same one used by multiple open-source projects.
#
# If it stops working:
#   1. Go to pinnacle.com, open DevTools Network tab
#   2. Look for requests to guest.api.arcadia.pinnacle.com
#   3. Copy the X-API-Key header value
#   4. Update the constant below

PINNACLE_API_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PINNACLE_API_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
PINNACLE_SPORT_ID_TENNIS = 33

API_HEADERS = {
    "X-API-Key": PINNACLE_API_KEY,
    "Referer": "https://www.pinnacle.com/",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

API_TIMEOUT = 15  # seconds


# ─── Helpers ────────────────────────────────────────────────────────

def american_to_decimal(american: int | float) -> float:
    """Convert American odds (+150, -180) to decimal (2.50, 1.556)."""
    american = int(american)
    if american >= 100:
        return round(1 + american / 100, 3)
    elif american <= -100:
        return round(1 + 100 / abs(american), 3)
    return 0.0


def compute_margin(odds1: float, odds2: float) -> float:
    """Pinnacle margin as percentage."""
    if not odds1 or not odds2 or odds1 <= 1 or odds2 <= 1:
        return 0.0
    return round((1 / odds1 + 1 / odds2 - 1) * 100, 2)


def _clean_name(name: str) -> str:
    """
    Clean player name from the API.
    Strips '(Games)', '(Sets)', seeding numbers in parens, trailing junk.
    """
    n = (name or "").strip()
    n = re.sub(r"\s*\(Games\)", "", n)
    n = re.sub(r"\s*\(Sets\)", "", n)
    n = re.sub(r"\s*\([^)]*\)", "", n)  # strip (8), (WC), etc.
    return n.strip()


def _is_doubles(name: str) -> bool:
    return "/" in (name or "") or " & " in (name or "")


def _norm_name(name: str) -> str:
    """Normalise name for dedup/matching: lowercase, strip accents."""
    n = (name or "").strip().lower()
    n = unicodedata.normalize("NFD", n)
    n = re.sub(r"[\u0300-\u036f]", "", n)
    n = re.sub(r"[-']", "", n)
    return " ".join(n.split())


def _api_get(path: str, retries: int = 3) -> list | dict | None:
    """GET from Pinnacle API with retries."""
    url = f"{PINNACLE_API_BASE}/{path.lstrip('/')}"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=API_TIMEOUT)
            if resp.ok:
                return resp.json()
            if resp.status_code == 403:
                print(f"  ERROR: 403 Forbidden — API key may have changed.")
                print(f"  See instructions in the script header to update PINNACLE_API_KEY.")
                return None
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"  Rate limited (429), waiting {wait}s...")
                _sleep(wait)
                continue
            print(f"  WARNING: API returned {resp.status_code} for {path} (attempt {attempt})")
        except requests.exceptions.RequestException as e:
            print(f"  WARNING: Network error for {path} (attempt {attempt}): {e}")
        if attempt < retries:
            _sleep(1)
    return None


# ─── League detection ───────────────────────────────────────────────

def _classify_league(name: str) -> str:
    """
    Classify a Pinnacle league name into our internal league tags.
    Returns 'ATP', 'Challenger', or 'WTA'.
    """
    upper = (name or "").upper()
    if "CHALLENGER" in upper:
        return "Challenger"
    if "WTA" in upper or "WOMEN" in upper:
        return "WTA"
    return "ATP"


def _should_include_league(name: str) -> bool:
    """Filter leagues based on CLI flags."""
    upper = (name or "").upper()
    if "ITF" in upper:
        return False
    if "ATP" in upper or "CHALLENGER" in upper:
        return True
    if "WTA" in upper or "WOMEN" in upper:
        return INCLUDE_WTA
    return True


# ─── Core scraper ───────────────────────────────────────────────────

def scrape_pinnacle() -> list[dict]:
    """
    Scrape all ATP/Challenger tennis odds from Pinnacle's guest API.

    Flow:
      1. GET /sports/33/leagues — list active tennis leagues
      2. Filter for ATP/Challenger (optionally WTA)
      3. For each league:
         a. GET /leagues/{id}/matchups — get matches + player names
         b. GET /leagues/{id}/markets/straight — get all odds
         c. Join moneyline + game-total markets to matchups
      4. Return list of match dicts
    """
    results = []

    # ── Step 1: Get active tennis leagues ──
    if VERBOSE:
        print("  Fetching tennis leagues...")
    leagues = _api_get(f"sports/{PINNACLE_SPORT_ID_TENNIS}/leagues?all=false")
    if not leagues:
        print("ERROR: Failed to fetch tennis leagues from API.")
        return []

    target_leagues = [(lg["id"], lg["name"]) for lg in leagues if _should_include_league(lg.get("name", ""))]
    if VERBOSE:
        print(f"  {len(leagues)} total leagues, {len(target_leagues)} targeted:")
        for lid, lname in target_leagues:
            print(f"    {lid}: {lname}")

    if not target_leagues:
        print("  No ATP/Challenger leagues currently active on Pinnacle.")
        return []

    # ── Step 2: Scrape each league ──
    for league_id, league_name in target_leagues:
        league_tag = _classify_league(league_name)
        if VERBOSE:
            print(f"\n  Scraping: {league_name} ({league_tag})")

        matchups = _api_get(f"leagues/{league_id}/matchups")
        if not matchups:
            if VERBOSE:
                print(f"    No matchups for {league_name}")
            continue

        markets = _api_get(f"leagues/{league_id}/markets/straight")
        if not markets:
            if VERBOSE:
                print(f"    No markets for {league_name}")
            continue

        # ── Separate regular vs (Games) matchups ──
        regular_matchups = []
        games_matchups = []
        for m in matchups:
            parts = m.get("participants", [])
            if len(parts) < 2:
                continue
            p1_name = parts[0].get("name", "")
            if "(Games)" in p1_name:
                games_matchups.append(m)
            else:
                regular_matchups.append(m)

        # ── Build (Games) matchup lookup by parentId ──
        games_by_parent = {}
        for gm in games_matchups:
            pid = gm.get("parentId")
            if pid:
                games_by_parent[pid] = gm["id"]

        # ── Index markets by matchupId ──
        moneylines = {}
        game_totals = {}

        for mkt in markets:
            mid = mkt.get("matchupId")
            mtype = mkt.get("type")
            period = mkt.get("period")
            prices = mkt.get("prices", [])
            if period != 0 or not prices:
                continue

            if mtype == "moneyline":
                home = next((p["price"] for p in prices if p.get("designation") == "home"), None)
                away = next((p["price"] for p in prices if p.get("designation") == "away"), None)
                if home is not None and away is not None:
                    moneylines[mid] = {
                        "odds1": american_to_decimal(home),
                        "odds2": american_to_decimal(away),
                    }

            elif mtype == "total":
                points = prices[0].get("points", 0)
                is_alt = mkt.get("isAlternate", False)
                if points < 10:
                    continue  # skip set totals
                over_p = next((p["price"] for p in prices if p.get("designation") == "over"), None)
                under_p = next((p["price"] for p in prices if p.get("designation") == "under"), None)
                if over_p is None or under_p is None:
                    continue
                existing = game_totals.get(mid)
                if existing is None or (existing.get("is_alt") and not is_alt):
                    game_totals[mid] = {
                        "line": points,
                        "over": american_to_decimal(over_p),
                        "under": american_to_decimal(under_p),
                        "is_alt": is_alt,
                    }

        if VERBOSE:
            print(f"    {len(regular_matchups)} regular matchups, {len(games_matchups)} (Games) variants")
            print(f"    {len(moneylines)} moneylines, {len(game_totals)} game-total lines")

        # ── Merge: for each regular matchup, combine ML + game total ──
        league_count = 0
        for m in regular_matchups:
            mid = m["id"]
            parts = m.get("participants", [])
            if len(parts) < 2:
                continue

            p1_raw = parts[0].get("name", "")
            p2_raw = parts[1].get("name", "")
            p1 = _clean_name(p1_raw)
            p2 = _clean_name(p2_raw)

            if _is_doubles(p1) or _is_doubles(p2):
                continue
            if m.get("isLive"):
                continue

            ml = moneylines.get(mid)
            if not ml:
                continue

            gt = None
            games_mid = games_by_parent.get(mid)
            if games_mid:
                gt = game_totals.get(games_mid)
            if not gt and m.get("parentId"):
                games_mid = games_by_parent.get(m["parentId"])
                if games_mid:
                    gt = game_totals.get(games_mid)
            if not gt:
                gt = game_totals.get(mid)

            margin = compute_margin(ml["odds1"], ml["odds2"])

            row = {
                "player1_name": p1,
                "player2_name": p2,
                "odds1": ml["odds1"],
                "odds2": ml["odds2"],
                "pinnacle_margin": margin,
                "ou_line": gt["line"] if gt else None,
                "ou_over": gt["over"] if gt else None,
                "ou_under": gt["under"] if gt else None,
                "league": league_tag,
                "league_name": league_name,
            }
            results.append(row)
            league_count += 1

        if VERBOSE:
            ou_c = sum(1 for r in results[-league_count:] if r.get("ou_line"))
            print(f"    → {league_count} singles matches ({ou_c} with O/U)")

    # ── Dedup by player pair (keep lowest margin) ──
    seen = {}
    for r in results:
        key = (_norm_name(r["player1_name"]), _norm_name(r["player2_name"]))
        if key in seen:
            if r["pinnacle_margin"] < seen[key]["pinnacle_margin"]:
                seen[key] = r
        else:
            seen[key] = r
    results = list(seen.values())

    return results


# ─── Supabase upsert ────────────────────────────────────────────────

def upsert_to_supabase(results: list[dict]):
    """Batch upsert to bookmaker_odds_snapshot via PostgREST."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("  WARNING: No Supabase credentials — skipping upsert.")
        return

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    rows = []
    for r in results:
        league_db = r.get("league", "ATP")
        if league_db == "Challenger":
            league_db = "ATP"

        rows.append({
            "capture_date": today,
            "captured_at": now.isoformat(),
            "bookmaker": "Pinnacle",
            "league": league_db,
            "player1_name": r["player1_name"],
            "player2_name": r["player2_name"],
            "odds1": r["odds1"],
            "odds2": r["odds2"],
            "pinnacle_margin": r["pinnacle_margin"],
            "ou_line": r.get("ou_line"),
            "ou_over": r.get("ou_over"),
            "ou_under": r.get("ou_under"),
        })

    if not rows:
        print("  No rows to upsert.")
        return

    conflict_cols = "capture_date,bookmaker,league,player1_name,player2_name"
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/bookmaker_odds_snapshot?on_conflict={conflict_cols}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=rows, headers=headers, timeout=30)
            if resp.ok:
                atp_c = sum(1 for r in rows if r["league"] == "ATP")
                wta_c = sum(1 for r in rows if r["league"] == "WTA")
                print(f"  Upserted {len(rows)} rows ({atp_c} ATP, {wta_c} WTA)")
                return
            elif resp.status_code == 409:
                print("  ERROR: 409 Conflict — missing UNIQUE constraint.")
                print("  Run in Supabase SQL Editor:")
                print("    ALTER TABLE bookmaker_odds_snapshot")
                print("      ADD CONSTRAINT bookmaker_odds_snapshot_upsert_key")
                print(f"      UNIQUE ({conflict_cols});")
                return
            else:
                print(f"  WARNING: Upsert failed (attempt {attempt}/{max_retries}): {resp.status_code} {resp.text[:200]}")
        except requests.exceptions.RequestException as e:
            print(f"  WARNING: Network error (attempt {attempt}/{max_retries}): {e}")

        if attempt < max_retries:
            wait = 2 ** attempt
            print(f"  Retrying in {wait}s...")
            _sleep(wait)

    print(f"  ERROR: All {max_retries} upsert attempts failed.")


# ─── CSV backup ──────────────────────────────────────────────────────

def save_csv(results: list[dict]):
    """Write CSV backup to data/."""
    csv_path = Path(f"data/pinnacle-odds-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "player1_name", "player2_name", "odds1", "odds2",
        "pinnacle_margin", "ou_line", "ou_over", "ou_under",
        "league", "league_name",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"  CSV: {csv_path}")


# ─── JSON dump (debug) ──────────────────────────────────────────────

def save_debug_json(results: list[dict]):
    """Write raw results as JSON for debugging."""
    json_path = Path(f"data/pinnacle-debug-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"  Debug JSON: {json_path}")


# ─── Entry point ────────────────────────────────────────────────────

def main():
    now = datetime.now(timezone.utc)
    print(f"{'=' * 60}")
    print(f"  Pinnacle Tennis Odds Scraper (API edition)")
    print(f"  {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE'} | WTA: {'included' if INCLUDE_WTA else 'excluded'}")
    print(f"{'=' * 60}")

    if not DRY_RUN and (not SUPABASE_URL or not SUPABASE_KEY):
        print("\n  WARNING: Missing Supabase credentials.")
        print("  Ensure .env.local has NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        print("  Use --dry-run to scrape without DB, or add credentials.")
        sys.exit(1)

    results = scrape_pinnacle()

    if not results:
        print("\n  No matches scraped. Possible causes:")
        print("  1. No tennis scheduled right now on Pinnacle")
        print("  2. API key may have changed (check PINNACLE_API_KEY)")
        print("  3. Network/geo-blocking (try VPN)")
        sys.exit(0)

    ou_count = sum(1 for r in results if r.get("ou_line") is not None)
    atp = sum(1 for r in results if r["league"] in ("ATP", "Challenger"))
    wta = sum(1 for r in results if r["league"] == "WTA")
    chall = sum(1 for r in results if r["league"] == "Challenger")

    print(f"\n  Summary: {len(results)} matches ({atp} ATP/Challenger, {wta} WTA), {ou_count} with O/U")
    if chall:
        print(f"    ({chall} of which are Challenger)")

    if VERBOSE:
        print()
        for r in results:
            ou_str = f"O/U {r['ou_line']} ({r['ou_over']:.3f}/{r['ou_under']:.3f})" if r.get("ou_line") else "no O/U"
            print(f"    {r['player1_name']:>25s}  {r['odds1']:.3f}  vs  {r['odds2']:.3f}  {r['player2_name']:<25s}  m={r['pinnacle_margin']:.1f}%  {ou_str}  [{r['league']}]")

    save_csv(results)

    if VERBOSE:
        save_debug_json(results)

    if not DRY_RUN:
        upsert_to_supabase(results)

    print(f"\n  Done.")


if __name__ == "__main__":
    main()
