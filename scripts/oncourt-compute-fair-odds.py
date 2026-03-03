"""
Phase 4: Compute fair odds for today's matches (hold%/return% + Elo hybrid).
Reads today's fixtures from Supabase, fetches player_surface_stats and player_elo,
computes p_A/p_B -> P(serve/return) -> blend with P(Elo) -> fair odds.
Create table first: run docs/supabase-phase4-daily-fair-odds.sql in Supabase.
Run: python scripts/oncourt-compute-fair-odds.py [--dry-run] [--debug [name1,name2]]
  --debug [names]  Print Elo, stats, ATP rank and fair odds for fixtures matching names (default: Cerundolo). E.g. --debug Cerundolo,Rublev.
  WARNING: If two players share a surname (e.g. F. and J.M. Cerundolo), OnCourt today_atp must use the correct ID per match; otherwise we show wrong odds.
"""

import math
import os
import re
import sys
from datetime import date

# Project root for tennis_prob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.lib.tennis_prob import prob_match_best_of_3, expected_total_games_best_of_3, prob_over_games

def load_env():
    base = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(base)
    for name in ["env.local", ".env.local"]:
        path = os.path.join(root, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip().replace("\r", "")
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        os.environ[k.strip()] = v

load_env()

# ─── CALIBRATION CONSTANTS (2026-03-02 tuning) ─────────────────────
#
# P = w*P_elo + (1-w)*P_serve_return.
# Default 55% Elo / 45% serve-return; adaptive by sample size (see below).
# Rationale: serve/return stats are noisy game-level proxies for point probs.
# At Challenger level with <20 matches, Elo+rank is more reliable.
HYBRID_ELO_WEIGHT_DEFAULT = 0.55   # was 0.40; Elo is more stable than noisy serve/return
HYBRID_ELO_WEIGHT_MIN_MATCHES = 30  # was 20; only trust serve/return more when well-sampled
POINT_CLAMP = (0.48, 0.82)   # realistic SPW range (0.01/0.99 was too wide, let junk through K-M)
DEFAULT_ELO = 1500
# Standard bookie O/U lines for ATP bo3 — we price at these instead of centring on mean E[G]
STANDARD_OU_LINES = [19.5, 20.5, 21.5, 22.5, 23.5, 24.5, 25.5]
# Vs leftie: adjustment from win_pct_vs_leftie (default 0.5)
VS_LEFTIE_WEIGHT = 0.03
VS_LEFTIE_CAP = 0.015
# Vs big server (hold_pct >= 0.68 on surface): adjustment from win_pct_vs_big_server
VS_BIG_SERVER_WEIGHT = 0.03
VS_BIG_SERVER_CAP = 0.015
BIG_SERVER_HOLD_PCT = 0.68
# Long-window: base blend 12m vs 36m; overridden by adaptive blend when match_count available
BLEND_RECENT_WEIGHT = 0.5
# Venue (same-event): lifetime win rate at this tournament
VENUE_WEIGHT = 0.025
VENUE_CAP = 0.015
# Altitude: at high altitude serve is more effective
ALTITUDE_WEIGHT = 0.03
ALTITUDE_CAP = 0.02
ALTITUDE_THRESHOLD_M = 200   # only adjust when venue altitude >= this (metres)
# Age: small modifier (prime 22-30, decline after 30)
AGE_CAP = 0.01
# Rank: blend with Elo.
# 0.30 so rank is a significant input (especially for Challengers where Elo may be default 1500).
# Was 0.15 which made rank a tiebreaker with only 6% total influence — far too low.
RANK_ELO_BLEND = 0.30   # was 0.15
# Log-rank scale for ATP ranking → win probability.
# Old value 1.1 was catastrophically wrong: rank 100 vs 300 → 91% (absurd).
# New value 3.5: rank 100 vs 300 → 67%, rank 50 vs 200 → 71% (realistic).
LOG_RANK_SCALE = 3.5   # was 1.1
# Shrinkage toward surface average when match count is low (hold/return noisy).
# With N=40: 10 matches → alpha=0.20 (20% raw stats), 20 → 0.33, 40 → 0.50.
# Was N=15 which gave 40% weight to 10-match stats (way too trusting of noise).
SHRINKAGE_N = 40   # was 15
# League avg serve point win % by surface (for ratio-based p_a/p_b; Barnett-Clarke). Replace with DB-computed if available.
SURFACE_LEAGUE_AVG = {"Hard": 0.64, "Clay": 0.62, "Grass": 0.67, "I.hard": 0.64, "N/A": 0.64}
# Surface averages for shrinkage (hold, return) when match_count is low
SURFACE_AVG_HOLD = {"Hard": 0.64, "Clay": 0.62, "Grass": 0.67, "I.hard": 0.64, "N/A": 0.64}
SURFACE_AVG_RETURN = {"Hard": 0.36, "Clay": 0.38, "Grass": 0.33, "I.hard": 0.36, "N/A": 0.36}
# Tournament totals: residual shift after venue-SPW adjustment (Claude: reduce from 0.5 to 0.2, cap ±1.5)
TOURNAMENT_TOTAL_WEIGHT = 0.20
TOURNAMENT_TOTAL_SHIFT_CAP = 1.5
# Only use a tour's shift when it has at least this many matches (noisy otherwise)
MIN_TOUR_MATCHES_FOR_SHIFT = 30
# Venue SPW: min matches to use tournament_serve_profile (Claude: 50)
MIN_VENUE_SPW_MATCHES = 50
SPEED_RATIO_CLAMP = (0.92, 1.08)
# Form/fatigue (player_recent_activity): three factors combined, then net delta cap
FORM_WEIGHT = 0.06
FORM_CAP = 0.02
FORM_MIN_MATCHES = 3   # need 3+ matches in 21d to apply form signal
FATIGUE_PLAYED_YESTERDAY = 0.008   # penalty (we apply as negative)
FATIGUE_DENSE_5D = 0.007           # 3+ matches in 5 days
FATIGUE_MODERATE_COMPOUND = 0.004  # 2 in 5d AND played yesterday
FATIGUE_CAP = 0.015
RUST_THRESHOLD_MODERATE = 28       # days without match → moderate rust
RUST_THRESHOLD_SEVERE = 42         # days → significant rust
RUST_PENALTY_MODERATE = 0.008
RUST_PENALTY_SEVERE = 0.015
RUST_CAP = 0.015
FORM_TOTAL_CAP = 0.025


def _float(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _age_factor(birthdate_str):
    """Return small modifier for age: prime 22-30 ~ 0, decline after 30 negative, young positive. Cap in caller."""
    if not birthdate_str:
        return 0.0
    try:
        bd = date.fromisoformat(birthdate_str.strip()[:10])
        age = (date.today() - bd).days / 365.25
    except (ValueError, TypeError, IndexError):
        return 0.0
    if age >= 30:
        return -0.004 * (age - 30)  # e.g. 35 -> -0.02
    if age < 22:
        return 0.002 * (22 - age)  # e.g. 20 -> 0.004
    return 0.0  # prime 22-30


def _solve_spw_for_match_prob(p1_win, avg_spw, clamp_lo=0.48, clamp_hi=0.82, tol=5e-4, max_iter=60):
    """Binary-search for (p_a, p_b) such that prob_match_best_of_3(p_a, p_b) ≈ p1_win.

    Assumes symmetric offset from avg_spw: p_a = avg + delta, p_b = avg - delta.
    This preserves the surface's average serve point win % while producing the
    correct match win probability.

    Returns (p_a, p_b) clamped to [clamp_lo, clamp_hi].
    """
    p1_win = max(0.02, min(0.98, p1_win))
    avg_spw = max(clamp_lo + 0.01, min(clamp_hi - 0.01, avg_spw))
    max_delta = min(avg_spw - clamp_lo, clamp_hi - avg_spw)
    lo, hi = -max_delta, max_delta
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        pa = max(clamp_lo, min(clamp_hi, avg_spw + mid))
        pb = max(clamp_lo, min(clamp_hi, avg_spw - mid))
        prob = prob_match_best_of_3(pa, pb)
        if abs(prob - p1_win) < tol:
            return (pa, pb)
        if prob < p1_win:
            lo = mid
        else:
            hi = mid
    mid = (lo + hi) / 2.0
    return (max(clamp_lo, min(clamp_hi, avg_spw + mid)),
            max(clamp_lo, min(clamp_hi, avg_spw - mid)))


def main():
    import requests
    do_dry_run = "--dry-run" in sys.argv
    if do_dry_run:
        print("Dry run: will not write to Supabase\n")

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local")
        sys.exit(1)

    base = url.rstrip("/") + "/rest/v1"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    REQ_TIMEOUT = 45  # avoid hanging on slow Supabase

    # 1) Today's fixtures (dedupe by match key so same match isn't listed twice)
    r = requests.get(f"{base}/oncourt_today", headers=headers, params={"select": "*", "limit": 1000}, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    raw_fixtures = r.json()
    if not raw_fixtures:
        print("No rows in oncourt_today. Run sync first.")
        return
    seen = set()
    fixtures = []
    for f in raw_fixtures:
        key = (f.get("tour_id"), f.get("player1_id"), f.get("player2_id"), f.get("round_id"))
        if key in seen:
            continue
        seen.add(key)
        fixtures.append(f)
    if len(fixtures) < len(raw_fixtures):
        print(f"Fixtures: {len(fixtures)} (deduped from {len(raw_fixtures)})")
    else:
        print(f"Fixtures: {len(fixtures)}")

    # Only include fixtures that are not yet played (no result from OnCourt)
    fixtures = [f for f in fixtures if not (f.get("result") or "").strip()]
    print(f"  Fixtures with no result (unplayed): {len(fixtures)}")

    # 2) Tour -> surface; restrict to ATP + Challenger only (exclude ITF, Futures, etc.)
    tour_select = "id,court_id,name,rank,altitude"
    r0 = requests.get(f"{base}/oncourt_tours", headers=headers, params={"select": tour_select, "limit": 1}, timeout=REQ_TIMEOUT)
    if r0.status_code == 400:
        tour_select = "id,court_id,name,rank"
    tours_list = []
    off = 0
    while True:
        r = requests.get(f"{base}/oncourt_tours", headers=headers, params={"select": tour_select, "offset": off, "limit": 1000}, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        tours_list.extend(data)
        off += len(data)
        if len(data) < 1000:
            break
    # ITF/Futures: M15, M25, M5, W15, W25, W5 etc. – exclude these
    itf_pattern = re.compile(r"\b[MW]\d{1,2}\b", re.IGNORECASE)

    tours = {}
    tour_to_altitude = {}
    atp_challenger_tour_ids = set()
    for t in tours_list:
        if t.get("id") is None:
            continue
        tid = int(t["id"])
        tours[tid] = t.get("court_id")
        alt = t.get("altitude")
        if alt is not None:
            try:
                tour_to_altitude[tid] = float(alt)
            except (TypeError, ValueError):
                pass
        name = (t.get("name") or "").upper()
        raw_name = t.get("name") or ""
        rank = t.get("rank")
        if itf_pattern.search(raw_name):
            continue
        if "ITF" in name or "FUTURES" in name:
            continue
        # Include: rank 1 (ATP) or 2 (Challenger), or name contains Challenger, or ATP
        if rank is not None and rank <= 2:
            atp_challenger_tour_ids.add(tid)
        elif "CHALLENGER" in name:
            atp_challenger_tour_ids.add(tid)
        elif "ATP" in name:
            atp_challenger_tour_ids.add(tid)
    fixtures = [f for f in fixtures if f.get("tour_id") in atp_challenger_tour_ids]
    print(f"  Fixtures after ATP/Challenger only (excl. M15/M25/ITF): {len(fixtures)}")

    r = requests.get(f"{base}/oncourt_courts", headers=headers, params={"select": "id,name", "limit": 100}, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    courts = {int(c["id"]): (c.get("name") or "N/A").strip() for c in r.json() if c.get("id") is not None}

    def _court_to_surface(court_name):
        """Map OnCourt court name to canonical surface (Hard, Clay, Grass, I.hard) for stats lookup."""
        if not court_name:
            return "N/A"
        c = court_name.upper()
        if "CLAY" in c or "TERRE" in c:
            return "Clay"
        if "GRASS" in c:
            return "Grass"
        if "INDOOR" in c and "HARD" in c:
            return "I.hard"
        if "HARD" in c or "DECOTURF" in c or "ACRYLIC" in c:
            return "Hard"
        return court_name  # keep as-is if no match (e.g. "Carpet" -> N/A later)

    tour_to_surface = {}
    for tid, cid in tours.items():
        if cid is not None:
            raw = courts.get(int(cid), "N/A")
            tour_to_surface[tid] = _court_to_surface(raw) if raw != "N/A" else raw
    print(f"  Loaded {len(tour_to_surface):,} tours -> surface" + (f", {len(tour_to_altitude):,} with altitude (run oncourt-derive-altitude.py + migration if 0)" if tour_to_altitude else ""))

    # 3) All player_surface_stats (with long-window columns for blend if table has them) and player_elo
    stats_select_full = "player_id,surface,hold_pct,return_pct,hold_pct_long,return_pct_long,match_count,service_pts"
    stats_select_base = "player_id,surface,hold_pct,return_pct,match_count,service_pts"
    r = requests.get(
        f"{base}/player_surface_stats",
        headers={**headers, "Prefer": "count=exact"},
        params={"select": stats_select_full, "limit": 1},
        timeout=REQ_TIMEOUT,
    )
    stats_select = stats_select_full
    if r.status_code in (400, 404):
        r = requests.get(
            f"{base}/player_surface_stats",
            headers={**headers, "Prefer": "count=exact"},
            params={"select": stats_select_base, "limit": 1},
            timeout=REQ_TIMEOUT,
        )
        stats_select = stats_select_base
    if r.status_code not in (200, 206):
        print("player_surface_stats fetch failed:", r.status_code)
        sys.exit(1)
    stats_rows = []
    off = 0
    while True:
        r = requests.get(
            f"{base}/player_surface_stats",
            headers=headers,
            params={"select": stats_select, "offset": off, "limit": 1000},
            timeout=REQ_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        stats_rows.extend(data)
        off += len(data)
        if len(data) < 1000:
            break
    stats = {(int(r["player_id"]), (r.get("surface") or "N/A").strip()): r for r in stats_rows}

    elo_rows = []
    off = 0
    while True:
        r = requests.get(
            f"{base}/player_elo",
            headers=headers,
            params={"select": "player_id,surface,elo", "offset": off, "limit": 1000},
            timeout=REQ_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        elo_rows.extend(data)
        off += len(data)
        if len(data) < 1000:
            break
    elo_lookup = {(int(r["player_id"]), (r.get("surface") or "N/A").strip()): _float(r.get("elo"), DEFAULT_ELO) for r in elo_rows}
    has_overall_elo = any(s == "Overall" for (_, s) in elo_lookup)
    print(f"  Elo: {len(elo_lookup):,} rows" + (" (surface + Overall 50/50 blend)" if has_overall_elo else " (surface only)"))

    # 4) Lefties: prefer player_hand_reference (hand=L), then fallback to player_extra + categories
    leftie_ids = set()
    try:
        r = requests.get(
            f"{base}/player_hand_reference",
            headers=headers,
            params={"select": "player_id", "hand": "eq.L", "limit": 10000},
            timeout=REQ_TIMEOUT,
        )
        if r.status_code == 200 and r.json():
            for row in r.json():
                pid = row.get("player_id")
                if pid is not None:
                    leftie_ids.add(int(pid))
        if leftie_ids:
            pass  # use player_hand_reference
        else:
            for tbl, col in [("oncourt_player_extra", "plays"), ("oncourt_categories", "cat1")]:
                off = 0
                while True:
                    sel = f"player_id,{col}" if tbl == "oncourt_player_extra" else "player_id,cat1"
                    r = requests.get(f"{base}/{tbl}", headers=headers, params={"select": sel, "offset": off, "limit": 1000}, timeout=REQ_TIMEOUT)
                    if r.status_code != 200:
                        break
                    data = r.json()
                    if not data:
                        break
                    for row in data:
                        if row.get("player_id") is None:
                            continue
                        if tbl == "oncourt_player_extra" and "Left-Handed" in (row.get("plays") or ""):
                            leftie_ids.add(int(row["player_id"]))
                        if tbl == "oncourt_categories" and row.get("cat1") is True:
                            leftie_ids.add(int(row["player_id"]))
                    off += len(data)
                    if len(data) < 1000:
                        break
    except Exception:
        pass
    vs_leftie_rows = []
    try:
        off = 0
        while True:
            r = requests.get(
                f"{base}/player_vs_leftie_stats",
                headers=headers,
                params={"select": "player_id,surface,win_pct_vs_leftie,match_count_vs_leftie", "offset": off, "limit": 1000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            vs_leftie_rows.extend(data)
            off += len(data)
            if len(data) < 1000:
                break
    except Exception:
        pass
    vs_leftie_lookup = {}
    for r in vs_leftie_rows:
        pid = r.get("player_id")
        surf = (r.get("surface") or "N/A").strip()
        if pid is not None and surf:
            vs_leftie_lookup[(int(pid), surf)] = _float(r.get("win_pct_vs_leftie"), 0.5)
    print(f"  Lefties: {len(leftie_ids)}, vs-leftie stats: {len(vs_leftie_lookup):,} rows")

    # 4b) Big servers (hold_pct >= threshold on surface) and vs-big-server stats
    big_server_set = set()
    try:
        off = 0
        while True:
            r = requests.get(
                f"{base}/player_surface_stats",
                headers=headers,
                params={"select": "player_id,surface,hold_pct", "hold_pct": f"gte.{BIG_SERVER_HOLD_PCT}", "offset": off, "limit": 1000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            for row in data:
                pid = row.get("player_id")
                surf = (row.get("surface") or "N/A").strip()
                if pid is not None and surf:
                    big_server_set.add((int(pid), surf))
            off += len(data)
            if len(data) < 1000:
                break
    except Exception:
        pass
    vs_big_server_rows = []
    try:
        off = 0
        while True:
            r = requests.get(
                f"{base}/player_vs_big_server_stats",
                headers=headers,
                params={"select": "player_id,surface,win_pct_vs_big_server", "offset": off, "limit": 1000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            vs_big_server_rows.extend(data)
            off += len(data)
            if len(data) < 1000:
                break
    except Exception:
        pass
    vs_big_server_lookup = {}
    for r in vs_big_server_rows:
        pid = r.get("player_id")
        surf = (r.get("surface") or "N/A").strip()
        if pid is not None and surf:
            vs_big_server_lookup[(int(pid), surf)] = _float(r.get("win_pct_vs_big_server"), 0.5)
    print(f"  Big servers: {len(big_server_set)} (player,surface), vs-big-server stats: {len(vs_big_server_lookup):,} rows")

    # 5) Venue stats (player_id, tour_id) -> win_pct at this event (lifetime). Load only for players/tours in today's fixtures (avoids pulling ~1.2M rows).
    venue_player_ids = set()
    venue_tour_ids = set()
    for f in fixtures:
        a, b = f.get("player1_id"), f.get("player2_id")
        if a is not None:
            venue_player_ids.add(int(a))
        if b is not None:
            venue_player_ids.add(int(b))
        t = f.get("tour_id")
        if t is not None:
            try:
                venue_tour_ids.add(int(t))
            except (TypeError, ValueError):
                pass
    venue_rows = []
    if venue_player_ids and venue_tour_ids:
        ids_list = list(venue_player_ids)
        tours_list = list(venue_tour_ids)
        try:
            r = requests.get(
                f"{base}/player_venue_stats",
                headers=headers,
                params={
                    "select": "player_id,tour_id,win_count,match_count",
                    "player_id": "in.(" + ",".join(str(x) for x in ids_list) + ")",
                    "tour_id": "in.(" + ",".join(str(x) for x in tours_list) + ")",
                    "limit": 10000,
                },
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 200:
                venue_rows = r.json() or []
        except Exception:
            pass
    print(f"  Venue: loaded {len(venue_rows):,} rows (fixture players/tours only)")
    venue_lookup = {}
    for r in venue_rows:
        pid = r.get("player_id")
        tid = r.get("tour_id")
        m = _float(r.get("match_count"), 0) or 0
        if pid is not None and tid is not None and m > 0:
            w = _float(r.get("win_count"), 0) or 0
            venue_lookup[(int(pid), int(tid))] = w / m
    print(f"  Venue stats: {len(venue_lookup):,} rows" + (" (venue adjustment active)" if venue_lookup else " (none – run venue pipeline or create table)"))

    # 5b) Player record at altitude (win % at high-altitude venues by surface) – used when match is at altitude
    altitude_rows = []
    if venue_player_ids:
        try:
            r = requests.get(
                f"{base}/player_altitude_stats",
                headers=headers,
                params={"player_id": "in.(" + ",".join(str(x) for x in list(venue_player_ids)) + ")", "limit": 5000},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 200:
                altitude_rows = r.json() or []
        except Exception:
            pass
    altitude_lookup = {}
    for r in altitude_rows:
        pid = r.get("player_id")
        surf = (r.get("surface") or "N/A").strip()
        if pid is not None and surf:
            w = _float(r.get("win_pct_at_altitude"), 0.5)
            altitude_lookup[(int(pid), surf)] = w
    print(f"  Altitude stats: {len(altitude_lookup):,} rows" + (" (player record at altitude active)" if altitude_lookup else " (run oncourt-compute-altitude-stats.py after derive-altitude)"))

    # 5c) League avg serve point win % per surface (for ratio p_a/p_b). Fallback to constants if missing.
    league_avg_by_surface = dict(SURFACE_LEAGUE_AVG)
    league_avg_from_db = 0
    try:
        r = requests.get(f"{base}/surface_league_averages", headers=headers, params={"select": "surface,serve_point_win_pct", "limit": 20}, timeout=REQ_TIMEOUT)
        if r.status_code == 200 and r.json():
            for row in r.json():
                surf = (row.get("surface") or "N/A").strip()
                pct = _float(row.get("serve_point_win_pct"))
                if surf and pct is not None:
                    league_avg_by_surface[surf] = pct
                    league_avg_from_db += 1
    except Exception:
        pass
    print(f"  League avg (surface): {league_avg_from_db} from DB" + (", rest constants" if league_avg_from_db < len(SURFACE_LEAGUE_AVG) else ""))

    # 5d) Tournament avg total games (shift_from_surface for expected_total_games adjustment)
    tour_shift_lookup = {}
    if venue_tour_ids:
        try:
            r = requests.get(
                f"{base}/tournament_game_averages",
                headers=headers,
                params={"tour_id": "in.(" + ",".join(str(x) for x in list(venue_tour_ids)) + ")", "select": "tour_id,surface,shift_from_surface,match_count", "limit": 500},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 200 and r.json():
                for row in r.json():
                    tid, surf = row.get("tour_id"), (row.get("surface") or "N/A").strip()
                    shift = row.get("shift_from_surface")
                    n = int(row.get("match_count") or 0)
                    if tid is not None and surf and shift is not None and n >= MIN_TOUR_MATCHES_FOR_SHIFT:
                        tour_shift_lookup[(int(tid), surf)] = float(shift)
        except Exception:
            pass
    print(f"  Tournament totals shift: {len(tour_shift_lookup):,} rows" + (" (active)" if tour_shift_lookup else " (run oncourt-compute-tournament-avg-games.py)"))

    # 5d2) Tournament serve profile (venue_avg_spw) for expected-total-games: adjust p_a/p_b before K-M
    venue_serve_lookup = {}
    if venue_tour_ids:
        try:
            r_venue = requests.get(
                f"{base}/tournament_serve_profile",
                headers=headers,
                params={"tour_id": "in.(" + ",".join(str(x) for x in list(venue_tour_ids)) + ")", "select": "tour_id,surface,venue_avg_spw,match_count", "limit": 500},
                timeout=REQ_TIMEOUT,
            )
            if r_venue.status_code == 200 and r_venue.json():
                for row in r_venue.json():
                    tid, surf = row.get("tour_id"), (row.get("surface") or "N/A").strip()
                    spw = row.get("venue_avg_spw")
                    n = int(row.get("match_count") or 0)
                    if tid is not None and surf and spw is not None and n >= MIN_VENUE_SPW_MATCHES:
                        venue_serve_lookup[(int(tid), surf)] = float(spw)
        except Exception:
            pass
    if venue_serve_lookup:
        print(f"  Tournament serve profile: {len(venue_serve_lookup):,} rows (venue SPW adjustment active)")

    # 5e) Recent form / fatigue (player_recent_activity)
    recent_activity_by_player = {}
    fixture_player_ids = set()
    for f in fixtures:
        a, b = f.get("player1_id"), f.get("player2_id")
        if a is not None:
            fixture_player_ids.add(int(a))
        if b is not None:
            fixture_player_ids.add(int(b))
    if fixture_player_ids:
        try:
            r = requests.get(
                f"{base}/player_recent_activity",
                headers=headers,
                params={"player_id": "in.(" + ",".join(str(x) for x in list(fixture_player_ids)) + ")", "select": "player_id,matches_last_21d,wins_last_21d,win_rate_21d,matches_last_5d,played_yesterday,last_match_date,avg_opponent_elo", "limit": 500},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 200 and r.json():
                for row in r.json():
                    pid = row.get("player_id")
                    if pid is not None:
                        recent_activity_by_player[int(pid)] = row
        except Exception:
            pass
    print(f"  Recent activity: {len(recent_activity_by_player):,} rows" + (" (form/fatigue active)" if recent_activity_by_player else " (run oncourt-compute-recent-activity.py)"))
    birthdate_by_player = {}
    atp_rank_by_player = {}
    surface_points_by_player = {}  # pid -> {"Hard": x, "Clay": y, "Grass": z} from OnCourt
    name_by_player = {}
    player_select = "id,name,birthdate,atp_rank,hard_points,clay_points,grass_points"
    if fixture_player_ids:
        ids_list = list(fixture_player_ids)
        for i in range(0, len(ids_list), 100):
            chunk = ids_list[i : i + 100]
            r = requests.get(
                f"{base}/oncourt_players",
                headers=headers,
                params={"id": "in.(" + ",".join(str(x) for x in chunk) + ")", "select": player_select},
                timeout=REQ_TIMEOUT,
            )
            if r.status_code == 400:
                r = requests.get(
                    f"{base}/oncourt_players",
                    headers=headers,
                    params={"id": "in.(" + ",".join(str(x) for x in chunk) + ")", "select": "id,name,birthdate,atp_rank"},
                    timeout=REQ_TIMEOUT,
                )
            if r.status_code == 200:
                for row in r.json():
                    if row.get("id") is not None:
                        pid = int(row["id"])
                        name_by_player[pid] = (row.get("name") or "").strip()
                        birthdate_by_player[pid] = row.get("birthdate")
                        rk = row.get("atp_rank")
                        if rk is not None and str(rk).strip() != "":
                            try:
                                atp_rank_by_player[pid] = int(float(rk))
                            except (ValueError, TypeError):
                                pass
                        hp = _float(row.get("hard_points")); cp = _float(row.get("clay_points")); gp = _float(row.get("grass_points"))
                        if hp is not None or cp is not None or gp is not None:
                            surface_points_by_player[pid] = {"Hard": hp, "Clay": cp, "Grass": gp, "I.hard": hp}
    print(f"  Players (birthdate + atp_rank): {len(birthdate_by_player)} with birthdate, {len(atp_rank_by_player)} with rank, {len(surface_points_by_player)} with surface points")
    # Warn if same surname appears for multiple players in today's fixtures (e.g. two Cerundolos) – wrong ID in OnCourt today_atp can cause wrong odds
    surname_to_players = {}
    skip_surnames = {"player", "unknown", "tbd", "tba"}  # ignore placeholders
    for pid in fixture_player_ids:
        name = name_by_player.get(pid, "")
        parts = (name or "").strip().split()
        sn = (parts[-1] if parts else "").strip().lower()
        if sn and sn not in skip_surnames:
            surname_to_players.setdefault(sn, []).append((pid, name))
    for sn, plist in surname_to_players.items():
        if len(plist) > 1:
            print(f"  WARNING: Same surname '{sn}' for multiple players in today's fixtures: {plist}. If odds look wrong, check OnCourt today_atp has the correct player ID for each match (e.g. F. vs J.M. Cerundolo).")
    do_debug = "--debug" in sys.argv
    debug_names = []
    for i, arg in enumerate(sys.argv):
        if arg == "--debug" and i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
            debug_names = [s.strip().lower() for s in sys.argv[i + 1].split(",") if s.strip()]
            break
    if "--debug" in sys.argv and not debug_names:
        debug_names = ["cerundolo"]  # default

    out = []
    skip_no_players = 0
    skip_missing_both = 0
    skip_missing_p1 = 0
    skip_missing_p2 = 0
    surface_counts = {}
    for f in fixtures:
        tour_id = f.get("tour_id")
        p1 = f.get("player1_id")
        p2 = f.get("player2_id")
        round_id = f.get("round_id")
        draw = f.get("draw")
        if p1 is None or p2 is None:
            skip_no_players += 1
            continue
        p1, p2 = int(p1), int(p2)
        try:
            tid = int(tour_id) if tour_id is not None else None
        except (TypeError, ValueError):
            tid = None
        surface = (tour_to_surface.get(tid) or "N/A") if tid is not None else "N/A"
        surface_counts[surface] = surface_counts.get(surface, 0) + 1

        s1 = stats.get((p1, surface))
        s2 = stats.get((p2, surface))
        e1_s = elo_lookup.get((p1, surface), DEFAULT_ELO)
        e2_s = elo_lookup.get((p2, surface), DEFAULT_ELO)
        e1_o = elo_lookup.get((p1, "Overall"))
        e2_o = elo_lookup.get((p2, "Overall"))

        # Track whether player has real Elo (not default 1500)
        e1_is_real = (p1, surface) in elo_lookup or (p1, "Overall") in elo_lookup
        e2_is_real = (p2, surface) in elo_lookup or (p2, "Overall") in elo_lookup

        # Determine confidence and whether we have stats
        has_s1 = s1 is not None
        has_s2 = s2 is not None
        if not has_s1 and not has_s2:
            skip_missing_both += 1
        elif not has_s1:
            skip_missing_p1 += 1
        elif not has_s2:
            skip_missing_p2 += 1

        surf_hold = SURFACE_AVG_HOLD.get(surface, 0.64)
        surf_ret = SURFACE_AVG_RETURN.get(surface, 0.36)

        # Blend 12m with long-window (36m); use surface averages as fallback when stats missing
        h1_12 = _float((s1 or {}).get("hold_pct"), surf_hold)
        r1_12 = _float((s1 or {}).get("return_pct"), surf_ret)
        h2_12 = _float((s2 or {}).get("hold_pct"), surf_hold)
        r2_12 = _float((s2 or {}).get("return_pct"), surf_ret)
        h1_long = _float((s1 or {}).get("hold_pct_long"), h1_12)
        r1_long = _float((s1 or {}).get("return_pct_long"), r1_12)
        h2_long = _float((s2 or {}).get("hold_pct_long"), h2_12)
        r2_long = _float((s2 or {}).get("return_pct_long"), r2_12)
        mc1_12 = int((s1 or {}).get("match_count") or 0) if has_s1 else 0
        mc2_12 = int((s2 or {}).get("match_count") or 0) if has_s2 else 0
        min_matches_12 = min(mc1_12, mc2_12)
        if min_matches_12 >= 25:
            recent_weight = 0.75
        elif min_matches_12 >= 15:
            recent_weight = 0.6
        elif min_matches_12 >= 8:
            recent_weight = 0.5
        else:
            recent_weight = 0.3
        if surface == "Clay":
            recent_weight = min(recent_weight, 0.6)   # clay: more weight to long window
        elif surface == "Grass":
            recent_weight = max(recent_weight, 0.55)   # grass: favour 12m (stale faster)
        hold1_raw = recent_weight * h1_12 + (1.0 - recent_weight) * h1_long
        ret1_raw = recent_weight * r1_12 + (1.0 - recent_weight) * r1_long
        hold2_raw = recent_weight * h2_12 + (1.0 - recent_weight) * h2_long
        ret2_raw = recent_weight * r2_12 + (1.0 - recent_weight) * r2_long
        # Shrinkage toward surface average when match count is low
        alpha1 = mc1_12 / (mc1_12 + SHRINKAGE_N) if mc1_12 else 0.0
        alpha2 = mc2_12 / (mc2_12 + SHRINKAGE_N) if mc2_12 else 0.0
        hold1 = alpha1 * hold1_raw + (1.0 - alpha1) * surf_hold if alpha1 > 0 else surf_hold
        ret1 = alpha1 * ret1_raw + (1.0 - alpha1) * surf_ret if alpha1 > 0 else surf_ret
        hold2 = alpha2 * hold2_raw + (1.0 - alpha2) * surf_hold if alpha2 > 0 else surf_hold
        ret2 = alpha2 * ret2_raw + (1.0 - alpha2) * surf_ret if alpha2 > 0 else surf_ret

        # p_A, p_B: ratio-based (Barnett-Clarke) relative to league avg serve point win % on surface (from DB or constants)
        league_avg = league_avg_by_surface.get(surface, 0.64)
        if league_avg <= 0 or league_avg >= 1:
            league_avg = 0.64
        p_a = (hold1 * (1.0 - ret2)) / league_avg
        p_b = (hold2 * (1.0 - ret1)) / league_avg
        p_a = max(POINT_CLAMP[0], min(POINT_CLAMP[1], p_a))
        p_b = max(POINT_CLAMP[0], min(POINT_CLAMP[1], p_b))

        p_serve_return = prob_match_best_of_3(p_a, p_b)

        # NOTE: p_a_eg / p_b_eg for E[G] and O/U are now computed AFTER p1_win
        # is finalised (see "Solve SPW" block below). The old approach computed
        # them here from the raw Barnett-Clarke ratio, which was inconsistent
        # with the final match-win probability after Elo/rank blending.
        # ─── Elo + Rank ────────────────────────────────────────────
        # Sackmann: 50/50 blend of single-surface and overall Elo predicts best
        p_elo_surface = 1.0 / (1.0 + 10.0 ** ((e2_s - e1_s) / 400.0))
        if e1_o is not None and e2_o is not None:
            p_elo_overall = 1.0 / (1.0 + 10.0 ** ((float(e2_o) - float(e1_o)) / 400.0))
            p_elo = 0.5 * p_elo_surface + 0.5 * p_elo_overall
        else:
            p_elo = p_elo_surface

        # General ability: surface points primary when available; else log-rank (ATP).
        # LOG_RANK_SCALE = 3.5 so rank 100 vs 300 → ~67% (was 1.1 → 91%, catastrophically extreme).
        r1, r2 = atp_rank_by_player.get(p1), atp_rank_by_player.get(p2)
        pts1 = surface_points_by_player.get(p1, {}).get(surface) if surface in ("Hard", "Clay", "Grass", "I.hard") else None
        pts2 = surface_points_by_player.get(p2, {}).get(surface) if surface in ("Hard", "Clay", "Grass", "I.hard") else None
        p_rank = None
        if pts1 is not None and pts2 is not None and (pts1 > 0 or pts2 > 0):
            # Surface points ratio (with floor to avoid division by zero)
            p_rank = (pts1 + 1) / (pts1 + pts2 + 2)
        elif r1 is not None and r2 is not None and r1 > 0 and r2 > 0:
            log_scale = LOG_RANK_SCALE
            p_rank = 1.0 / (1.0 + 10.0 ** ((math.log(max(1, r1)) - math.log(max(1, r2))) / log_scale))

        # When both players have default Elo (1500/1500) AND we have rank,
        # rank should be the primary signal — not blended 30% into useless Elo.
        both_elo_default = not e1_is_real and not e2_is_real
        if both_elo_default and p_rank is not None:
            # Rank IS the Elo signal when Elo is uninformative
            p_elo = p_rank
        elif p_rank is not None:
            # Normal blend: rank is 30% of the Elo component
            p_elo = (1.0 - RANK_ELO_BLEND) * p_elo + RANK_ELO_BLEND * p_rank
        # Confidence level based on data availability
        if both_elo_default and p_rank is None and not has_s1 and not has_s2:
            # Truly zero data: no stats, no real Elo, no rank.
            # Model output is meaningless (50/50 by construction).
            confidence = "none"
        elif not has_s1 and not has_s2:
            confidence = "low"
        elif not has_s1 or not has_s2:
            confidence = "low" if min(mc1_12, mc2_12) < 5 else "medium"
        elif min(mc1_12, mc2_12) < 5:
            confidence = "medium"
        elif min(mc1_12, mc2_12) >= 10:
            confidence = "high"
        else:
            confidence = "medium"

        # ─── Hybrid blend: Elo vs serve/return ──────────────────────
        # Default 55% Elo / 45% serve-return (was 40/60).
        # Lean more on Elo when stats are thin or missing.
        if not has_s1 or not has_s2:
            elo_weight = 0.80
        else:
            # Adaptive: ranges from 0.55 (30+ matches) up to 0.85 (0 matches)
            elo_weight = HYBRID_ELO_WEIGHT_DEFAULT + 0.30 * max(0.0, 1.0 - min(min_matches_12, HYBRID_ELO_WEIGHT_MIN_MATCHES) / float(HYBRID_ELO_WEIGHT_MIN_MATCHES))
            elo_weight = max(0.40, min(0.85, elo_weight))

        # When serve/return is uninformative (near 50/50) but Elo/rank strongly favour one player, trust Elo+rank more.
        # Threshold widened from 0.04 to 0.08 to catch more cases where heavy shrinkage washes out real differences.
        if abs(p_serve_return - 0.5) < 0.08 and p_rank is not None:
            # Serve/return is uninformative — rely on rank + Elo
            p_elo_effective = 0.4 * p_elo + 0.6 * p_rank
            elo_weight = 0.90
            p1_win = elo_weight * p_elo_effective + (1.0 - elo_weight) * p_serve_return
        else:
            p1_win = elo_weight * p_elo + (1.0 - elo_weight) * p_serve_return
        p2_win = 1.0 - p1_win

        # Factor adjustments (small weights, capped so we don't flip favourites)
        delta_p1 = 0.0
        # Vs leftie
        if p2 in leftie_ids:
            w1_vs_leftie = vs_leftie_lookup.get((p1, surface), 0.5)
            delta_p1 += (w1_vs_leftie - 0.5) * VS_LEFTIE_WEIGHT
        if p1 in leftie_ids:
            w2_vs_leftie = vs_leftie_lookup.get((p2, surface), 0.5)
            delta_p1 -= (w2_vs_leftie - 0.5) * VS_LEFTIE_WEIGHT
        # Vs big server: when opponent is big server, use win_pct_vs_big_server (continuous: weight by how much over surface avg)
        if (p2, surface) in big_server_set:
            w1_vs_bs = vs_big_server_lookup.get((p1, surface), 0.5)
            server_strength = max(0.0, (hold2 - surf_hold) / 0.13) if surf_hold < 0.75 else 1.0  # 0.75 - 0.62 ≈ 0.13 for clay
            server_strength = min(1.0, server_strength)
            d_bs = (w1_vs_bs - 0.5) * VS_BIG_SERVER_WEIGHT * server_strength
            delta_p1 += max(-VS_BIG_SERVER_CAP, min(VS_BIG_SERVER_CAP, d_bs))
        if (p1, surface) in big_server_set:
            w2_vs_bs = vs_big_server_lookup.get((p2, surface), 0.5)
            server_strength = max(0.0, (hold1 - surf_hold) / 0.13) if surf_hold < 0.75 else 1.0
            server_strength = min(1.0, server_strength)
            d_bs = (w2_vs_bs - 0.5) * VS_BIG_SERVER_WEIGHT * server_strength
            delta_p1 -= max(-VS_BIG_SERVER_CAP, min(VS_BIG_SERVER_CAP, d_bs))
        # Venue (same-event): better record at this tour gets a small boost
        if tid is not None:
            v1 = venue_lookup.get((p1, tid), 0.5)
            v2 = venue_lookup.get((p2, tid), 0.5)
            delta_p1 += (v1 - 0.5) * VENUE_WEIGHT - (v2 - 0.5) * VENUE_WEIGHT
        # Altitude: use player record at high-altitude venues (win_pct_at_altitude by surface); fallback to hold% proxy if no stats
        alt = tour_to_altitude.get(tid) if tid is not None else None
        if alt is not None and alt >= ALTITUDE_THRESHOLD_M:
            a1 = altitude_lookup.get((p1, surface), 0.5)
            a2 = altitude_lookup.get((p2, surface), 0.5)
            if a1 != 0.5 or a2 != 0.5:
                d_alt = (a1 - 0.5) * ALTITUDE_WEIGHT - (a2 - 0.5) * ALTITUDE_WEIGHT
            else:
                d_alt = (hold1 - hold2) * ALTITUDE_WEIGHT
            d_alt = max(-ALTITUDE_CAP, min(ALTITUDE_CAP, d_alt))
            delta_p1 += d_alt
        # Age: prime vs decline (scale so max effect ~ ±0.01)
        a1 = _age_factor(birthdate_by_player.get(p1))
        a2 = _age_factor(birthdate_by_player.get(p2))
        delta_p1 += 0.5 * (a1 - a2)
        # Form/fatigue/rust (player_recent_activity): three factors, then net delta
        today_d = date.today()
        def _form_fatigue_rust(pid, player_elo_surface):
            act = recent_activity_by_player.get(pid)
            if not act:
                return 0.0
            m21 = int(act.get("matches_last_21d") or 0)
            wr = _float(act.get("win_rate_21d"))
            avg_opp = _float(act.get("avg_opponent_elo"), 1500)
            # Factor A: form (outperform vs expected given opponent quality)
            delta_form = 0.0
            if m21 >= FORM_MIN_MATCHES and wr is not None and avg_opp is not None:
                expected_wr = 1.0 / (1.0 + 10.0 ** ((avg_opp - player_elo_surface) / 400.0))
                delta_form = (wr - expected_wr) * FORM_WEIGHT
                delta_form = max(-FORM_CAP, min(FORM_CAP, delta_form))
            # Factor B: fatigue (scheduling density)
            delta_fatigue = 0.0
            if act.get("played_yesterday"):
                delta_fatigue -= FATIGUE_PLAYED_YESTERDAY
            m5 = int(act.get("matches_last_5d") or 0)
            if m5 >= 3:
                delta_fatigue -= FATIGUE_DENSE_5D
            elif m5 >= 2 and act.get("played_yesterday"):
                delta_fatigue -= FATIGUE_MODERATE_COMPOUND
            delta_fatigue = max(-FATIGUE_CAP, delta_fatigue)
            # Factor C: inactivity / ring rust
            delta_rust = 0.0
            last_d = act.get("last_match_date")
            if last_d:
                try:
                    if isinstance(last_d, str):
                        last_d = date.fromisoformat(last_d[:10])
                    days = (today_d - last_d).days
                    if days >= RUST_THRESHOLD_SEVERE:
                        delta_rust = -RUST_PENALTY_SEVERE
                    elif days >= RUST_THRESHOLD_MODERATE:
                        delta_rust = -RUST_PENALTY_MODERATE
                    delta_rust = max(-RUST_CAP, delta_rust)
                except (ValueError, TypeError):
                    pass
            return delta_form + delta_fatigue + delta_rust
        p1_form = _form_fatigue_rust(p1, e1_s)
        p2_form = _form_fatigue_rust(p2, e2_s)
        delta_p1_form = 0.5 * (p1_form - p2_form)
        delta_p1_form = max(-FORM_TOTAL_CAP, min(FORM_TOTAL_CAP, delta_p1_form))
        delta_p1 += delta_p1_form
        # Cap total adjustment
        delta_p1 = max(-max(VS_LEFTIE_CAP, VS_BIG_SERVER_CAP, VENUE_CAP, ALTITUDE_CAP, AGE_CAP, FORM_TOTAL_CAP), min(max(VS_LEFTIE_CAP, VS_BIG_SERVER_CAP, VENUE_CAP, ALTITUDE_CAP, AGE_CAP, FORM_TOTAL_CAP), delta_p1))
        delta_p1 = max(-0.04, min(0.04, delta_p1))  # overall cap ±0.04
        p1_win += delta_p1
        p2_win -= delta_p1

        # Normalize
        tot = p1_win + p2_win
        if tot > 0:
            p1_win, p2_win = p1_win / tot, p2_win / tot
        odds1 = 1.0 / p1_win if p1_win > 0 else 100.0
        odds2 = 1.0 / p2_win if p2_win > 0 else 100.0

        # ─── Solve SPW from final p1_win, then compute E[G] and O/U ──────
        # avg_spw for this surface (used as centre point for the solve)
        avg_spw_surface = league_avg_by_surface.get(surface, 0.64)
        # Venue SPW adjustment: shift the centre point if we have tournament serve profile
        if tid is not None:
            venue_spw = venue_serve_lookup.get((tid, surface))
            if venue_spw is not None:
                avg_spw_surface = venue_spw  # use venue-specific SPW as centre
        p_a_eg, p_b_eg = _solve_spw_for_match_prob(
            p1_win, avg_spw_surface,
            clamp_lo=POINT_CLAMP[0], clamp_hi=POINT_CLAMP[1]
        )
        exp_games = expected_total_games_best_of_3(p_a_eg, p_b_eg)

        # Tournament residual shift (e.g. court speed effects not captured by venue SPW)
        tour_shift = tour_shift_lookup.get((tid, surface)) if tid is not None else None
        if tour_shift is not None:
            raw_add = TOURNAMENT_TOTAL_WEIGHT * tour_shift
            exp_games += max(-TOURNAMENT_TOTAL_SHIFT_CAP, min(TOURNAMENT_TOTAL_SHIFT_CAP, raw_add))
        exp_games = max(12.0, min(48.0, exp_games))

        # O/U: use STANDARD bookie lines (not centred on mean E[G]).
        # Find the line where P(over) crosses 50% (median), then show that line ± 1 — like Pinnacle.
        ou_data = {}
        if confidence != "none":
            line_probs = []
            for line in STANDARD_OU_LINES:
                p_over = prob_over_games(p_a_eg, p_b_eg, line)
                p_over = max(0.01, min(0.99, p_over))
                line_probs.append((line, p_over))
            median_idx = min(range(len(line_probs)), key=lambda i: abs(line_probs[i][1] - 0.50))
            median_idx = max(1, min(len(line_probs) - 2, median_idx))
            for idx_offset, display_idx in enumerate(range(median_idx - 1, median_idx + 2)):
                line, p_over = line_probs[display_idx]
                fair_over = round(1.0 / p_over, 3)
                fair_under = round(1.0 / (1.0 - p_over), 3)
                ou_data[f"ou_line_{idx_offset + 1}"] = round(line, 1)
                ou_data[f"ou_over_{idx_offset + 1}"] = fair_over
                ou_data[f"ou_under_{idx_offset + 1}"] = fair_under

        if do_debug:
            n1, n2 = name_by_player.get(p1, ""), name_by_player.get(p2, "")
            n1_l, n2_l = n1.lower(), n2.lower()
            if any(d in n1_l or d in n2_l for d in debug_names):
                print(f"\n  [DEBUG] {n1} (P1 id={p1}) vs {n2} (P2 id={p2}) surface={surface}")
                print(f"    Elo surface: P1={e1_s:.0f} P2={e2_s:.0f}  Overall: P1={e1_o} P2={e2_o}  real_elo: P1={e1_is_real} P2={e2_is_real}  confidence={confidence}")
                mc1 = (s1 or {}).get("match_count"); sp1 = (s1 or {}).get("service_pts"); mc2 = (s2 or {}).get("match_count"); sp2 = (s2 or {}).get("service_pts")
                print(f"    Hold/return 12m: P1 hold={hold1:.3f} ret={ret1:.3f}  P2 hold={hold2:.3f} ret={ret2:.3f}  (P1 matches={mc1} svc_pts={sp1}  P2 matches={mc2} svc_pts={sp2})")
                print(f"    Shrinkage: alpha1={alpha1:.3f} alpha2={alpha2:.3f}  (SHRINKAGE_N={SHRINKAGE_N})")
                print(f"    ATP rank: P1={atp_rank_by_player.get(p1)} P2={atp_rank_by_player.get(p2)}  p_rank={p_rank}  both_elo_default={both_elo_default}")
                print(f"    p_elo={p_elo:.4f} p_serve_return={p_serve_return:.4f} elo_weight={elo_weight:.2f} -> p1_win={p1_win:.4f} (after adj)")
                o1 = 1.0 / p1_win if p1_win > 0 else 0
                o2 = 1.0 / p2_win if p2_win > 0 else 0
                print(f"    Our fair odds: P1={o1:.2f} P2={o2:.2f}  (if P1 favoured, P1 odds should be lower e.g. ~1.2)")
                print(f"    Expected total games: {exp_games:.1f}")
                print(f"    p_a_eg={p_a_eg:.4f} p_b_eg={p_b_eg:.4f}  (solved from p1_win={p1_win:.4f}, avg_spw={avg_spw_surface:.3f})")
                if (mc1 is not None and int(mc1 or 0) < 10) or (mc2 is not None and int(mc2 or 0) < 10):
                    print(f"    ^ Low match_count -> hold/return may be noisy. Re-run oncourt-compute-player-stats after fresh extract, or add prior when sample small.")

        out.append({
            "tour_id": tour_id,
            "player1_id": p1,
            "player2_id": p2,
            "surface": surface,
            "round_id": round_id,
            "draw": draw,
            "p1_win_prob": round(p1_win, 4),
            "p2_win_prob": round(p2_win, 4),
            "p_serve_return": round(p_serve_return, 4),
            "p_elo": round(p_elo, 4),
            "odds1": round(odds1, 2),
            "odds2": round(odds2, 2),
            "expected_total_games": round(exp_games, 1),
            "confidence": confidence,
            **ou_data,
        })

    print(f"Computed {len(out)} fair odds rows")
    print(f"  Fixture surfaces (from tour_id): {dict(surface_counts)}")
    print(f"  Skipped: no player1/player2 = {skip_no_players}")
    print(f"  Elo/rank fallback (missing stats): both = {skip_missing_both}, P1 only = {skip_missing_p1}, P2 only = {skip_missing_p2}")
    conf_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for row in out:
        c = row.get("confidence", "high")
        conf_counts[c] = conf_counts.get(c, 0) + 1
    print(f"  Confidence: high={conf_counts['high']}, medium={conf_counts['medium']}, low={conf_counts['low']}, none={conf_counts['none']}")
    if out:
        for row in out[:3]:
            print(f"  P1={row['player1_id']} P2={row['player2_id']} surface={row['surface']} P1={row['p1_win_prob']} odds1={row['odds1']} odds2={row['odds2']}")

    if do_dry_run:
        print("\nDry run done. Run without --dry-run to upsert to daily_fair_odds.")
        return

    # Replace daily_fair_odds with this run only (clear old so we don't show stale/duplicate days)
    try:
        r = requests.delete(
            f"{base}/daily_fair_odds",
            headers={k: v for k, v in headers.items() if k != "Content-Type"},
            params={"id": "gte.0"},
            timeout=30,
        )
        r.raise_for_status()
        print("  Cleared existing daily_fair_odds rows.")
    except Exception as e:
        print(f"  Warning: could not clear daily_fair_odds ({e}). Old rows may remain.")

    # Insert current run's rows only
    headers_post = {**headers, "Content-Type": "application/json", "Prefer": "return=minimal"}
    for row in out:
        r = requests.post(f"{base}/daily_fair_odds", headers=headers_post, json=row, timeout=30)
        r.raise_for_status()
    print("Done.")


if __name__ == "__main__":
    if "--test-solver" in sys.argv:
        # Quick local check: 85% favourite -> E[G] ~22.5 (no Supabase needed)
        p_a, p_b = _solve_spw_for_match_prob(0.85, 0.64, clamp_lo=POINT_CLAMP[0], clamp_hi=POINT_CLAMP[1])
        eg = expected_total_games_best_of_3(p_a, p_b)
        print(f"[--test-solver] p1_win=0.85 avg_spw=0.64 -> p_a={p_a:.3f} p_b={p_b:.3f} E[G]={eg:.1f} (expect ~22.5)")
        sys.exit(0)
    main()
