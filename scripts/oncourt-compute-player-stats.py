"""
Phase 2.1 / 2.4: Compute hold% and return% by player and surface (last 12 months),
then upsert into Supabase player_surface_stats.

Formulas (from fair-odds-plan):
  hold_pct  = (W1S + W2S) / (FSOF + W2SOF)  -> (w_w1s + w_w2s) / (w_fsof + w_w2sof)
  return_pct = RPW / RPWOF                   -> w_rpw / w_rpwof

Reads from local CSVs (run after extract/sync so data is present).
Requires: .env.local with NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Create table first: run docs/supabase-phase2-player-stats.sql in Supabase SQL Editor.

Run: python scripts/oncourt-compute-player-stats.py [--dry-run]
  --dry-run  Compute and print summary only; do not write to Supabase
"""

import os
import sys
import csv
from datetime import datetime, timedelta
from collections import defaultdict

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

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "oncourt")
ROLLING_DAYS = 365
ROLLING_DAYS_LONG = 1095  # 36 months for blend (general ability, not just recent form)
BLEND_RECENT_WEIGHT = 0.7  # hold_blend = BLEND_RECENT_WEIGHT * hold_12m + (1 - BLEND_RECENT_WEIGHT) * hold_long
BATCH = 500


def load_csv(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({k: (v if v else None) for k, v in row.items()})
    return rows


def parse_date(s):
    if not s or not s.strip():
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _int(r, key, default=0):
    v = r.get(key)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


def main():
    do_dry_run = "--dry-run" in sys.argv
    if do_dry_run:
        print("Dry run: will not write to Supabase\n")

    cutoff = (datetime.now() - timedelta(days=ROLLING_DAYS)).date()
    cutoff_long = (datetime.now() - timedelta(days=ROLLING_DAYS_LONG)).date()
    print(f"Using 12m window: {cutoff} to today; long window: {cutoff_long} to today ({ROLLING_DAYS_LONG} days)\n")

    # Load reference data: games (date, tour_id), tours (court_id), courts (surface name)
    games_path = os.path.join(DATA_DIR, "games_atp.csv")
    tours_path = os.path.join(DATA_DIR, "tours_atp.csv")
    courts_path = os.path.join(DATA_DIR, "courts.csv")
    stat_path = os.path.join(DATA_DIR, "stat_atp.csv")

    for p, name in [(games_path, "games"), (stat_path, "stat")]:
        if not os.path.exists(p):
            print(f"Missing {p}. Run extract/sync first.")
            sys.exit(1)

    print("Loading games, tours, courts...")
    games = load_csv(games_path)
    tours = load_csv(tours_path)
    courts = load_csv(courts_path)

    court_id_to_surface = {}
    for r in courts:
        cid = r.get("id")
        name = r.get("name")
        if cid and name:
            try:
                court_id_to_surface[int(cid)] = name.strip()
            except ValueError:
                pass

    def _court_to_surface(court_name):
        """Map OnCourt court name to canonical surface so we don't split Red Clay vs Clay etc."""
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
        return court_name

    tour_id_to_surface = {}
    for r in tours:
        tid = r.get("id")
        cid = r.get("court_id")
        if tid and cid:
            try:
                raw = court_id_to_surface.get(int(cid), "N/A")
                surface = _court_to_surface(raw) if raw != "N/A" else raw
                tour_id_to_surface[int(tid)] = surface
            except ValueError:
                pass

    # Key games by (winner_id, loser_id, tour_id, round_id) -> (date, surface)
    game_key_to_info = {}
    game_key_to_info_long = {}
    for r in games:
        w = _int(r, "winner_id")
        l = _int(r, "loser_id")
        t = _int(r, "tour_id")
        rd = _int(r, "round_id")
        if not (w and l and t is not None):
            continue
        dt = parse_date(r.get("date"))
        if dt is None:
            continue
        surface = tour_id_to_surface.get(t, "N/A")
        if dt >= cutoff:
            game_key_to_info[(w, l, t, rd)] = (dt, surface)
        if dt >= cutoff_long:
            game_key_to_info_long[(w, l, t, rd)] = (dt, surface)

    print(f"  Games in 12m window: {len(game_key_to_info):,}, long window: {len(game_key_to_info_long):,}")

    print("Loading stat...")
    stat_rows = load_csv(stat_path)

    # Aggregate per (player_id, surface): 12m and long window
    agg = defaultdict(lambda: {"hold_num": 0, "hold_den": 0, "return_num": 0, "return_den": 0, "matches": 0})
    agg_long = defaultdict(lambda: {"hold_num": 0, "hold_den": 0, "return_num": 0, "return_den": 0, "matches": 0})

    for r in stat_rows:
        w = _int(r, "winner_id")
        l = _int(r, "loser_id")
        t = _int(r, "tour_id")
        rd = _int(r, "round_id")
        key = (w, l, t, rd)
        in_12m = key in game_key_to_info
        in_long = key in game_key_to_info_long
        if not in_12m and not in_long:
            continue
        _date, surface = game_key_to_info.get(key) or game_key_to_info_long[key]

        w_fsof = _int(r, "w_fsof")
        w_w2sof = _int(r, "w_w2sof")
        w_w1s = _int(r, "w_w1s")
        w_w2s = _int(r, "w_w2s")
        w_rpw = _int(r, "w_rpw")
        w_rpwof = _int(r, "w_rpwof")
        l_fsof = _int(r, "l_fsof")
        l_w2sof = _int(r, "l_w2sof")
        l_w1s = _int(r, "l_w1s")
        l_w2s = _int(r, "l_w2s")
        l_rpw = _int(r, "l_rpw")
        l_rpwof = _int(r, "l_rpwof")

        for ag, use in [(agg, in_12m), (agg_long, in_long)]:
            if not use:
                continue
            if w_fsof + w_w2sof > 0:
                ag[(w, surface)]["hold_num"] += w_w1s + w_w2s
                ag[(w, surface)]["hold_den"] += w_fsof + w_w2sof
            if w_rpwof > 0:
                ag[(w, surface)]["return_num"] += w_rpw
                ag[(w, surface)]["return_den"] += w_rpwof
            ag[(w, surface)]["matches"] += 1
            if l_fsof + l_w2sof > 0:
                ag[(l, surface)]["hold_num"] += l_w1s + l_w2s
                ag[(l, surface)]["hold_den"] += l_fsof + l_w2sof
            if l_rpwof > 0:
                ag[(l, surface)]["return_num"] += l_rpw
                ag[(l, surface)]["return_den"] += l_rpwof
            ag[(l, surface)]["matches"] += 1

    # Build rows for player_surface_stats (12m + long-window columns)
    out = []
    for (player_id, surface), v in agg.items():
        hold_den = v["hold_den"]
        return_den = v["return_den"]
        hold_pct = (v["hold_num"] / hold_den) if hold_den else None
        return_pct = (v["return_num"] / return_den) if return_den else None
        vlong = agg_long.get((player_id, surface), {})
        hold_den_long = vlong.get("hold_den", 0)
        return_den_long = vlong.get("return_den", 0)
        hold_pct_long = (vlong["hold_num"] / hold_den_long) if hold_den_long else None
        return_pct_long = (vlong["return_num"] / return_den_long) if return_den_long else None
        match_count_long = vlong.get("matches", 0)
        row = {
            "player_id": player_id,
            "surface": surface,
            "hold_pct": round(hold_pct, 4) if hold_pct is not None else None,
            "return_pct": round(return_pct, 4) if return_pct is not None else None,
            "match_count": v["matches"],
            "service_pts": v["hold_den"],
            "return_pts": v["return_den"],
        }
        if hold_pct_long is not None:
            row["hold_pct_long"] = round(hold_pct_long, 4)
        if return_pct_long is not None:
            row["return_pct_long"] = round(return_pct_long, 4)
        if match_count_long:
            row["match_count_long"] = match_count_long
        out.append(row)

    print(f"Computed {len(out):,} (player_id, surface) rows")
    if out:
        by_surface = defaultdict(int)
        for row in out:
            by_surface[row["surface"]] += 1
        print("  By surface:", dict(by_surface))

    if do_dry_run:
        print("\nDry run done. Run without --dry-run to upsert to Supabase.")
        return

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local")
        sys.exit(1)

    import requests
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }

    # Base columns (table may lack long-window columns until migration is run)
    BASE_COLS = ["player_id", "surface", "hold_pct", "return_pct", "match_count", "service_pts", "return_pts"]
    use_long_cols = True

    print("\nUpserting to player_surface_stats...")
    for i in range(0, len(out), BATCH):
        batch = out[i : i + BATCH]
        payload = [{k: row[k] for k in BASE_COLS if k in row} for row in batch] if not use_long_cols else batch
        r = requests.post(
            f"{url.rstrip('/')}/rest/v1/player_surface_stats",
            headers=headers,
            json=payload,
            timeout=60,
        )
        if r.status_code == 400 and use_long_cols:
            use_long_cols = False
            payload = [{k: row[k] for k in BASE_COLS if k in row} for row in batch]
            r = requests.post(
                f"{url.rstrip('/')}/rest/v1/player_surface_stats",
                headers=headers,
                json=payload,
                timeout=60,
            )
        r.raise_for_status()
        if (i + BATCH) % 5000 == 0 or i + BATCH >= len(out):
            print(f"  {min(i + BATCH, len(out)):,} / {len(out):,}")
    if not use_long_cols:
        print("  (Table has no long-window columns; run docs/supabase-migration-player-stats-long-window.sql to enable 36m blend)")
    print("Done.")


if __name__ == "__main__":
    main()
