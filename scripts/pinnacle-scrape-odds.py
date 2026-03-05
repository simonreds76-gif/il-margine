#!/usr/bin/env python3
"""
Pinnacle tennis odds scraper — API edition.

Uses Pinnacle's public guest API (guest.api.arcadia.pinnacle.com) to fetch
structured JSON for all tennis leagues, matchups, and markets. No more HTML
parsing or Playwright browser automation.

Scope: MEN'S SINGLES ONLY.
  - Include: ATP (main draw + qualifiers), Challenger.
  - Exclude: doubles, ITF, WTA, Futures / anything below Challenger (e.g. M15, M25).

Usage:
  python scripts/pinnacle-scrape-odds.py
  python scripts/pinnacle-scrape-odds.py --dry-run --verbose
  python scripts/pinnacle-scrape-odds.py --include-wta
  python scripts/pinnacle-scrape-odds.py --list-leagues   # debug: print all tennis leagues (Indian Wells etc.)
  python scripts/pinnacle-scrape-odds.py --active-leagues-only   # only leagues with all=false (default)
  python scripts/pinnacle-scrape-odds.py --all-leagues           # use all=true (slower; debug/fallback)
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
LIST_LEAGUES_ONLY = "--list-leagues" in sys.argv
PINNACLE_LEAGUES_ALL = "--all-leagues" in sys.argv
# Keep daily jobs fast and predictable: use active leagues by default.
PINNACLE_LEAGUES_ACTIVE_ONLY = "--active-leagues-only" in sys.argv or not PINNACLE_LEAGUES_ALL

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
    """
    Include men's singles tour-level leagues (ATP/challenger/qualifiers where Pinnacle
    may omit explicit 'ATP' in league name). Exclude women, ITF/Futures, and low-level Mxx.
    """
    upper = (name or "").upper()
    if "WTA" in upper or "WOMEN" in upper:
        return bool(INCLUDE_WTA)
    if "DOUBLES" in upper:
        return False
    if "ITF" in upper or "FUTURES" in upper or "JUNIOR" in upper or "BOYS" in upper or "GIRLS" in upper:
        return False
    if re.search(r"\bM\d{2}\b", upper):  # M15, M25, M50 etc.
        return False
    # Keep explicit ATP/Challenger; also include remaining men's leagues so
    # qualifiers like Indian Wells are not missed when naming differs.
    return True


def _extract_best_game_total(markets: list[dict] | None) -> dict | None:
    """
    Pick one full-match games total market (prefer non-alternate). Skip set totals.
    """
    best = None
    for mkt in markets or []:
        if mkt.get("type") != "total":
            continue
        if mkt.get("period") != 0:
            continue
        prices = mkt.get("prices", []) or []
        if not prices:
            continue
        points = prices[0].get("points")
        try:
            points_f = float(points)
        except (TypeError, ValueError):
            continue
        units = str(mkt.get("units") or "").lower()
        special = str(mkt.get("special") or "").lower()
        if "set" in units or "set" in special:
            continue
        if points_f < 10:
            continue  # set totals are typically <10
        over_p = next((p["price"] for p in prices if p.get("designation") == "over"), None)
        under_p = next((p["price"] for p in prices if p.get("designation") == "under"), None)
        if over_p is None or under_p is None:
            continue
        cand = {
            "line": points_f,
            "over": american_to_decimal(over_p),
            "under": american_to_decimal(under_p),
            "is_alt": bool(mkt.get("isAlternate", False)),
        }
        if best is None or (best.get("is_alt") and not cand.get("is_alt")):
            best = cand
    return best


# ─── Core scraper ───────────────────────────────────────────────────

def scrape_pinnacle() -> list[dict]:
    """
    Scrape men's singles only: ATP (main + qualifiers) + Challenger.
    No doubles, ITF, WTA, or below Challenger.

    Flow:
      1. GET /sports/33/leagues — list tennis leagues
      2. Filter for ATP/Challenger only (optionally WTA with --include-wta)
      3. For each league:
         a. GET /leagues/{id}/matchups — get matches + player names
         b. GET /leagues/{id}/markets/straight — get all odds
         c. Join moneyline + game-total markets to matchups
      4. Return list of match dicts
    """
    results = []

    # ── Step 1: Get tennis leagues ──
    # default: active only (all=false); fallback/debug: --all-leagues (all=true)
    all_param = "false" if PINNACLE_LEAGUES_ACTIVE_ONLY else "true"
    if VERBOSE:
        print(f"  Fetching tennis leagues (all={all_param})...")
    leagues = _api_get(f"sports/{PINNACLE_SPORT_ID_TENNIS}/leagues?all={all_param}")
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
                cand = _extract_best_game_total([mkt])
                if cand is None:
                    continue
                existing = game_totals.get(mid)
                if existing is None or (existing.get("is_alt") and not cand.get("is_alt")):
                    game_totals[mid] = cand

        if VERBOSE:
            print(f"    {len(regular_matchups)} regular matchups, {len(games_matchups)} (Games) variants")
            print(f"    {len(moneylines)} moneylines, {len(game_totals)} game-total lines")

        # ── Merge: for each regular matchup, combine ML + game total (singles only) ──
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

            # Men's singles only: skip doubles (e.g. "Smith / Jones" or "A & B")
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
            if not gt:
                # Fallback: query matchup-level markets (same as opening the match page)
                fallback_ids = []
                if games_mid:
                    fallback_ids.append(games_mid)
                fallback_ids.append(mid)
                if m.get("parentId"):
                    fallback_ids.append(m["parentId"])
                for fb_mid in dict.fromkeys(fallback_ids):
                    related = _api_get(f"matchups/{fb_mid}/markets/related/straight", retries=1)
                    if isinstance(related, list):
                        gt = _extract_best_game_total(related)
                    if gt is None:
                        straight = _api_get(f"matchups/{fb_mid}/markets/straight", retries=1)
                        if isinstance(straight, list):
                            gt = _extract_best_game_total(straight)
                    if gt is not None:
                        break

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
            print(f"    -> {league_count} singles matches ({ou_c} with O/U)")

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


# ─── Outright (tournament winner) scraper ───────────────────────────

def _normalise_tournament_name(league_name: str) -> str:
    """Map Pinnacle league name to canonical tournament name."""
    upper = (league_name or "").upper()
    if "INDIAN WELLS" in upper and "CHALLENGER" not in upper and "QUALIF" not in upper:
        return "Indian Wells"
    if "MIAMI" in upper and "ITF" not in upper and "CHALLENGER" not in upper:
        return "Miami"
    if "MONTE CARLO" in upper or "MONTE-CARLO" in upper:
        return "Monte Carlo"
    if "MADRID" in upper and "MUTUA" in upper:
        return "Madrid"
    if "ROME" in upper or "INTERNAZIONALI" in upper and "ITAL" in upper:
        return "Rome"
    if "CANADA" in upper or "MONTREAL" in upper or "TORONTO" in upper:
        return "Canada"
    if "CINCINNATI" in upper or "WESTERN" in upper:
        return "Cincinnati"
    if "SHANGHAI" in upper:
        return "Shanghai"
    if "PARIS" in upper and "MASTERS" in upper:
        return "Paris"
    if "AUSTRALIAN OPEN" in upper:
        return "Australian Open"
    if "FRENCH OPEN" in upper or "ROLAND" in upper:
        return "French Open"
    if "WIMBLEDON" in upper:
        return "Wimbledon"
    if "US OPEN" in upper or "U.S. OPEN" in upper:
        return "US Open"
    # Fallback: strip qualifiers, challenger, round suffixes
    name = re.sub(r"\s*-\s*(Qualifiers?|R\d+|QF|SF|Final|CHALLENGER).*", "", upper, flags=re.I)
    return name.strip() or league_name


def scrape_outrights() -> list[dict]:
    """
    Scrape tournament winner (outright) odds from Pinnacle.
    Returns list of {tournament_name, league_name, player_name, odds, rank_in_market}.
    """
    results = []
    leagues = _api_get(f"sports/{PINNACLE_SPORT_ID_TENNIS}/leagues?all={'false' if PINNACLE_LEAGUES_ACTIVE_ONLY else 'true'}")
    if not leagues:
        return []

    for lg in leagues:
        name = lg.get("name", "")
        if not _should_include_league(name) or "DOUBLES" in name.upper():
            continue
        lid = lg.get("id")
        matchups = _api_get(f"leagues/{lid}/matchups")
        if not matchups:
            continue

        outright = next((m for m in matchups if len(m.get("participants", [])) > 2), None)
        if not outright:
            continue

        markets = _api_get(f"leagues/{lid}/markets/straight")
        mkt = next((m for m in markets or [] if m.get("matchupId") == outright["id"] and m.get("type") == "moneyline"), None)
        if not mkt or not mkt.get("prices"):
            continue

        pid_to_name = {p.get("id"): _clean_name(p.get("name", "")) for p in outright.get("participants", [])}
        prices = mkt.get("prices", [])
        rows = []
        for rank, p in enumerate(prices, 1):
            pid = p.get("participantId")
            player = pid_to_name.get(pid, "")
            if not player or player == "The Field":
                continue
            try:
                american = int(p.get("price", 0))
                odds = american_to_decimal(american)
            except (TypeError, ValueError):
                continue
            rows.append({
                "tournament_name": _normalise_tournament_name(name),
                "league_name": name,
                "player_name": player,
                "odds": odds,
                "rank_in_market": rank,
            })
        results.extend(rows)
        if VERBOSE:
            print(f"    Outright: {name} -> {len(rows)} players")

    return results


def upsert_outrights_to_supabase(results: list[dict]):
    """Batch upsert to tournament_outright_snapshot."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("  WARNING: No Supabase credentials — skipping outright upsert.")
        return

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    rows = []
    for r in results:
        rows.append({
            "capture_date": today,
            "tournament_name": r["tournament_name"],
            "league_name": r["league_name"],
            "player_name": r["player_name"],
            "odds": r["odds"],
            "rank_in_market": r["rank_in_market"],
            "captured_at": now.isoformat(),
        })

    if not rows:
        return

    delete_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/tournament_outright_snapshot?capture_date=eq.{today}"
    delete_headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        requests.delete(delete_url, headers=delete_headers, timeout=30)
    except requests.RequestException:
        pass

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/tournament_outright_snapshot"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    try:
        resp = requests.post(url, json=rows, headers=headers, timeout=60)
        if resp.ok:
            by_tour = {}
            for r in rows:
                t = r["tournament_name"]
                by_tour[t] = by_tour.get(t, 0) + 1
            print(f"  Outrights: {len(rows)} rows for {len(by_tour)} tournaments")
        else:
            print(f"  WARNING: Outright upsert failed: {resp.status_code} {resp.text[:120]}")
    except requests.RequestException as e:
        print(f"  WARNING: Outright upsert error: {e}")


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
        rows.append({
            "capture_date": today,
            "captured_at": now.isoformat(),
            "bookmaker": "Pinnacle",
            "league": r.get("league", "ATP"),
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

    # Keep snapshot coherent per day: clear today's Pinnacle rows first, then write fresh set.
    delete_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/bookmaker_odds_snapshot?capture_date=eq.{today}&bookmaker=eq.Pinnacle"
    delete_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    try:
        dresp = requests.delete(delete_url, headers=delete_headers, timeout=30)
        if not dresp.ok:
            print(f"  WARNING: pre-clear failed ({dresp.status_code}): {dresp.text[:160]}")
    except requests.RequestException as e:
        print(f"  WARNING: pre-clear network error: {e}")

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
                chall_c = sum(1 for r in rows if r["league"] == "Challenger")
                wta_c = sum(1 for r in rows if r["league"] == "WTA")
                print(f"  Upserted {len(rows)} rows ({atp_c} ATP, {chall_c} Challenger, {wta_c} WTA)")
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

def list_leagues_and_exit():
    """Fetch and print all tennis leagues (all=false and all=true) for debugging Indian Wells etc."""
    print("  Fetching tennis leagues (all=false)...")
    active = _api_get(f"sports/{PINNACLE_SPORT_ID_TENNIS}/leagues?all=false")
    print("  Fetching tennis leagues (all=true)...")
    all_leagues = _api_get(f"sports/{PINNACLE_SPORT_ID_TENNIS}/leagues?all=true")
    print()
    for label, leagues in [("all=false (active)", active or []), ("all=true (all)", all_leagues or [])]:
        print(f"  --- {label}: {len(leagues or [])} leagues ---")
        if not leagues:
            continue
        for lg in leagues:
            name = lg.get("name") or ""
            lid = lg.get("id", "")
            inc = "YES" if _should_include_league(name) else "no"
            tag = _classify_league(name)
            print(f"    {lid}: {name!r}  -> include={inc}  tag={tag}")
        print()
    # Highlight Indian Wells
    combined = list({lg.get("name"): lg for lg in ((active or []) + (all_leagues or [])) if lg.get("name")}.values())
    indian = [lg for lg in combined if "indian" in (lg.get("name") or "").lower() or "wells" in (lg.get("name") or "").lower()]
    if indian:
        print("  Indian Wells–related leagues:", [lg.get("name") for lg in indian])
    else:
        print("  No league name containing 'Indian' or 'Wells' found.")
    sys.exit(0)


def main():
    now = datetime.now(timezone.utc)
    print(f"{'=' * 60}")
    print(f"  Pinnacle Tennis Odds Scraper (API edition)")
    print(f"  {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE'} | WTA: {'included' if INCLUDE_WTA else 'excluded'}")
    print(f"{'=' * 60}")

    if LIST_LEAGUES_ONLY:
        list_leagues_and_exit()

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

    # ── Outright (tournament winner) odds ──
    outrights = scrape_outrights()
    if outrights:
        if VERBOSE:
            by_t = {}
            for o in outrights:
                t = o["tournament_name"]
                by_t[t] = by_t.get(t, 0) + 1
            print(f"\n  Outrights: {len(outrights)} players across {len(by_t)} tournaments")
        if not DRY_RUN:
            upsert_outrights_to_supabase(outrights)

    print(f"\n  Done.")


if __name__ == "__main__":
    main()
