--- Copy everything below this line and paste into Claude at the start of a session ---

**IMPORTANT:** Before pasting this code bundle, paste the role/task prompt from docs/Claude-Model-Transformation-Prompt.rtf. That file has the full context: model lock (Iteration 4), strict policy (Hard|Masters 1000, high confidence, 10% value), tournament/injury overlays, daily/weekly pipeline schedules, settlement, individual tip pages, William Hill affiliate tracking, file paths, commands, and testing horizon/decision gates. This bundle below is the **code** that goes alongside it.



I'm working on the il-margine repo (fair-odds pipeline, Pinnacle, expected totals). So we're not inferring from context, please read these first â€” they're the real code and schemas.

If you can't read the repo files directly, paste the contents of these docs (they contain the full code):
- docs/CLAUDE-CORE-FILES-1-tennis-prob-and-schema.md   (tennis_prob.py + player_surface_stats schema excerpt)
- docs/CLAUDE-CORE-FILES-2-player-stats.md            (oncourt-compute-player-stats.py, full)
- docs/CLAUDE-CORE-FILES-3-fair-odds.md              (oncourt-compute-fair-odds.py, full script)

Core logic (paths for when you have repo access):
- scripts/oncourt-compute-fair-odds.py   (main fair-odds model, writes daily_fair_odds)
- scripts/oncourt-compute-player-stats.py (hold/return â†’ player_surface_stats)
- src/lib/tennis_prob.py                 (K-M recursion: win prob + expected_total_games_best_of_3)

Pipeline and policy:
- Daily pipeline: scripts/run-daily-odds.py (runs at 23:55 UTC: Pinnacle scrape -> fair-odds compute -> strict report)
- Weekly pipeline: scripts/oncourt-weekly.ps1 (Sunday 22:00: full OnCourt extract + sync + stats + settlement + performance)
- Strict policy report: scripts/strict-policy-report.py (appends to data/backtest/strict-signals.csv)
- Settlement: scripts/settle-strict-signals.py (settles signals against actual results, weekly)
- Performance: scripts/strict-policy-performance.py (base vs overlay ROI/PnL)
- Injury scraper: scripts/scrape-tennisexplorer-injured.py -> data/injured-players-tennisexplorer.csv
- Walk-forward: scripts/backtest-walkforward-tune.py
- Policy lock: docs/FAIR-ODDS-POLICY-LOCK.md (Iteration 4 locked; any change needs approval + backtest comparison)

Pinnacle and comparisons: scripts/pinnacle-scrape-odds.py, compare-fair-odds-pinnacle-snapshot.py, compare-oncourt-sackmann-stats.py
Frontend and API: src/app/fair-odds/page.tsx, src/app/api/fair-odds/route.ts (falls back to yesterday if today has no Pinnacle rows)
Schemas: docs/supabase-oncourt-schema.sql, docs/supabase-phase4-daily-fair-odds.sql, docs/bookmaker-odds-snapshot-schema.sql

Full index: docs/CLAUDE-CODEBASE-INDEX.md

Once you've read the core files (or the three CLAUDE-CORE-FILES-*.md docs), we can safely change the migration plan, expected-totals recipe, or Pinnacle flow.


=== PART 1 (tennis_prob + schema) ===

# Core files for Claude â€” Part 1: tennis_prob.py + supabase-oncourt-schema.sql

Paste this (and Part 2 + Part 3) into your conversation with Claude so he can read the real code. See docs/CLAUDE-CODEBASE-INDEX.md for the full list.

---

## File 1: `src/lib/tennis_prob.py`

```python
"""
Tennis match probability from point probabilities p_A, p_B (Klaassen & Magnus style).
p_A = P(A wins point when A serves), p_B = P(B wins point when B serves).
Best-of-3: set 1 A serves first, set 2 B, set 3 A.
"""

from functools import lru_cache


def prob_game(p: float) -> float:
    """P(server wins game) given P(server wins point) = p. Deuce formula: d = pÂ²/(1-2p(1-p))."""
    if p <= 0 or p >= 1:
        return max(0.0, min(1.0, p))
    # P(win game) = P(40-0)+P(40-15)+P(40-30)+P(deuce)*d
    # 40-0 = p^4, 40-15 = 4*p^4*(1-p), 40-30 = 10*p^4*(1-p)^2, deuce = 20*p^3*(1-p)^3
    d = (p * p) / (1.0 - 2.0 * p * (1.0 - p))
    return p**4 + 4 * p**4 * (1 - p) + 10 * p**4 * (1 - p) ** 2 + 20 * p**3 * (1 - p) ** 3 * d


def _tb_server_is_a(total_points: int) -> bool:
    """True if A serves for the next point in tiebreak (A serves points 0,3,4,7,8,...)."""
    return (total_points % 4) in (0, 3)


def _prob_tiebreak_dp(p_a: float, p_b: float, a_serves_first: bool) -> float:
    """P(A wins tiebreak) via DP. At 6-6 we use iterative fixed point for extended TB."""
    p_a = max(0.01, min(0.99, p_a))
    p_b = max(0.01, min(0.99, p_b))
    max_pts = 30
    dp = [[None] * (max_pts + 1) for _ in range(max_pts + 1)]

    def p_win_point(total: int) -> float:
        srv_a = _tb_server_is_a(total) if a_serves_first else not _tb_server_is_a(total)
        return p_a if srv_a else (1.0 - p_b)

    for a in range(max_pts, -1, -1):
        for b in range(max_pts, -1, -1):
            if a >= 7 and a - b >= 2:
                dp[a][b] = 1.0
            elif b >= 7 and b - a >= 2:
                dp[a][b] = 0.0
            elif a + b >= 12 and a == b and a > 6:
                total = a + b
                p = p_win_point(total)
                p_next_a = p_win_point(total + 1)
                p_next_b = p_win_point(total + 2)
                denom = 1.0 - (p * (1 - p_next_a) + (1 - p) * (1 - p_next_b))
                dp[a][b] = (p * p_next_a) / denom if abs(denom) >= 1e-9 else 0.5
            else:
                total = a + b
                p = p_win_point(total)
                next_a = dp[a + 1][b] if a + 1 <= max_pts else 0.5
                next_b = dp[a][b + 1] if b + 1 <= max_pts else 0.5
                dp[a][b] = p * next_a + (1.0 - p) * next_b

    return dp[0][0]


def prob_tiebreak(p_a: float, p_b: float, a_serves_first: bool = True) -> float:
    """P(A wins tiebreak). A serves first point."""
    return _prob_tiebreak_dp(p_a, p_b, a_serves_first)


@lru_cache(maxsize=8192)
def _prob_set(a: int, b: int, pa_int: int, pb_int: int, a_serves: bool) -> float:
    """P(A wins set) from (a,b). pa_int, pb_int = point probs * 10000."""
    p_a = pa_int / 10000.0
    p_b = pb_int / 10000.0
    if a >= 6 and a - b >= 2:
        return 1.0
    if b >= 6 and b - a >= 2:
        return 0.0
    if a == 6 and b == 6:
        return prob_tiebreak(p_a, p_b, a_serves)
    p_game_a = prob_game(p_a)
    p_game_b = prob_game(p_b)
    if a_serves:
        p_win_game = p_game_a
    else:
        p_win_game = 1.0 - p_game_b
    win = p_win_game * _prob_set(a + 1, b, pa_int, pb_int, not a_serves)
    lose = (1.0 - p_win_game) * _prob_set(a, b + 1, pa_int, pb_int, not a_serves)
    return win + lose


def prob_set(p_a: float, p_b: float, a_serves_first: bool = True) -> float:
    """P(A wins set). A serves first game."""
    pa_int = int(round(max(0.01, min(0.99, p_a)) * 10000))
    pb_int = int(round(max(0.01, min(0.99, p_b)) * 10000))
    return _prob_set(0, 0, pa_int, pb_int, a_serves_first)


def prob_match_best_of_3(p_a: float, p_b: float) -> float:
    """P(A wins best-of-3). Set 1 A serves first, set 2 B, set 3 A."""
    s1 = prob_set(p_a, p_b, a_serves_first=True)
    s2 = prob_set(p_a, p_b, a_serves_first=False)
    return s1 * s2 + s1 * (1 - s2) * s1 + (1 - s1) * s2 * s1


@lru_cache(maxsize=8192)
def _expected_games_set(a: int, b: int, pa_int: int, pb_int: int, a_serves: bool) -> float:
    """Expected number of games REMAINING in the set from (a,b) to finish. Tiebreak counts as 1 game."""
    p_a = pa_int / 10000.0
    p_b = pb_int / 10000.0
    if a >= 6 and a - b >= 2:
        return 0.0  # set over, no games remaining
    if b >= 6 and b - a >= 2:
        return 0.0
    if a == 6 and b == 6:
        return 1.0  # one tiebreak remaining
    p_game_a = prob_game(p_a)
    p_game_b = prob_game(p_b)
    if a_serves:
        p_win_game = p_game_a
    else:
        p_win_game = 1.0 - p_game_b
    return 1.0 + p_win_game * _expected_games_set(a + 1, b, pa_int, pb_int, not a_serves) + (1.0 - p_win_game) * _expected_games_set(a, b + 1, pa_int, pb_int, not a_serves)


def expected_games_set(p_a: float, p_b: float, a_serves_first: bool = True) -> float:
    """Expected number of games in a single set. Tiebreak = 1 game."""
    pa_int = int(round(max(0.01, min(0.99, p_a)) * 10000))
    pb_int = int(round(max(0.01, min(0.99, p_b)) * 10000))
    return _expected_games_set(0, 0, pa_int, pb_int, a_serves_first)


def expected_total_games_best_of_3(p_a: float, p_b: float) -> float:
    """Expected total games in a best-of-3 match (same point model as match win prob). Set 1 A first, set 2 B, set 3 A."""
    e_s1 = expected_games_set(p_a, p_b, a_serves_first=True)
    e_s2 = expected_games_set(p_a, p_b, a_serves_first=False)
    s1 = prob_set(p_a, p_b, a_serves_first=True)
    s2 = prob_set(p_a, p_b, a_serves_first=False)
    p_2_0 = s1 * s2 + (1 - s1) * (1 - s2)
    p_2_1 = 1.0 - p_2_0
    return p_2_0 * (e_s1 + e_s2) + p_2_1 * (e_s1 + e_s2 + e_s1)
```

---

## File 2: `docs/supabase-oncourt-schema.sql` (excerpt: player_surface_stats + related)

```sql
-- Phase 2: Player stats by surface (rolling 12 months)
-- Populated by scripts/oncourt-compute-player-stats.py after each sync
CREATE TABLE IF NOT EXISTS player_surface_stats (
  player_id INTEGER NOT NULL REFERENCES oncourt_players(id),
  surface TEXT NOT NULL,
  hold_pct NUMERIC,
  return_pct NUMERIC,
  match_count INTEGER NOT NULL DEFAULT 0,
  service_pts INTEGER,
  return_pts INTEGER,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (player_id, surface)
);

CREATE INDEX IF NOT EXISTS idx_player_surface_stats_player ON player_surface_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_player_surface_stats_surface ON player_surface_stats(surface);

-- Also in this schema: oncourt_courts, oncourt_players, oncourt_tours, oncourt_games, oncourt_stat,
-- oncourt_today, oncourt_player_extra, oncourt_categories, player_elo.
-- daily_fair_odds is in docs/supabase-phase4-daily-fair-odds.sql
```

Full schema: see repo file `docs/supabase-oncourt-schema.sql` for all tables (oncourt_games, oncourt_stat, etc.).


=== PART 2 (player-stats) ===

# Core files for Claude â€” Part 2: oncourt-compute-player-stats.py

Paste this (and Part 1 + Part 3) into your conversation with Claude so he can read the real code. See docs/CLAUDE-CODEBASE-INDEX.md for the full list.

---

## File: `scripts/oncourt-compute-player-stats.py`

Hold/return computation: reads games_atp + stat_atp, aggregates by (player_id, surface) for 12m and 36m windows, upserts to `player_surface_stats`. Column names: hold_pct, return_pct, match_count, service_pts, return_pts; optional hold_pct_long, return_pct_long, match_count_long.

```python
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
```


=== PART 3 (fair-odds) ===

# Core files for Claude â€” Part 3: oncourt-compute-fair-odds.py

Paste this (and Part 1 + Part 2) into your conversation with Claude so he can read the real code. See docs/CLAUDE-CODEBASE-INDEX.md for the full list.

---

## File: `scripts/oncourt-compute-fair-odds.py`

Full script: main fair-odds model. Reads oncourt_today, player_surface_stats, player_elo, tournament_serve_profile, tournament_game_averages, venue/altitude/form/leftie/big-server lookups; computes p_a/p_b (Barnettâ€“Clarke), blend 12m/36m holdâ€“return, hybrid with Elo; uses `prob_match_best_of_3` and `expected_total_games_best_of_3` from `src.lib.tennis_prob`; venue SPW for expected games (TOURNAMENT_TOTAL_WEIGHT=0.20, TOURNAMENT_TOTAL_SHIFT_CAP=1.5); writes daily_fair_odds.

```python
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
from src.lib.tennis_prob import prob_match_best_of_3, expected_total_games_best_of_3

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

# P = w*P_elo + (1-w)*P_serve_return. Default 40% Elo / 60% serve-return; adaptive by sample size (see below).
HYBRID_ELO_WEIGHT_DEFAULT = 0.4   # when both have 20+ matches on surface
HYBRID_ELO_WEIGHT_MIN_MATCHES = 20  # below this we lean more on Elo
POINT_CLAMP = (0.01, 0.99)
DEFAULT_ELO = 1500
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
# Rank: blend with Elo; 0.15 so rank is tiebreaker not major input. Log-rank for ATP; surface points primary when available.
RANK_ELO_BLEND = 0.15
LOG_RANK_SCALE = 1.1   # for log(rank) difference in log-odds
# Shrinkage toward surface average when match count is low (hold/return noisy)
SHRINKAGE_N = 15   # matches needed for ~50% trust in raw stats
# League avg serve point win % by surface (for ratio-based p_a/p_b; Barnett-Clarke). Replace with DB-computed if available.
SURFACE_LEAGUE_AVG = {"Hard": 0.64, "Clay": 0.62, "Grass": 0.67, "I.hard": 0.64, "N/A": 0.64}
# Surface averages for shrinkage (hold, return) when match_count is low
SURFACE_AVG_HOLD = {"Hard": 0.64, "Clay": 0.62, "Grass": 0.67, "I.hard": 0.64, "N/A": 0.64}
SURFACE_AVG_RETURN = {"Hard": 0.36, "Clay": 0.38, "Grass": 0.33, "I.hard": 0.36, "N/A": 0.36}
# Tournament totals: residual shift after venue-SPW adjustment (Claude: reduce from 0.5 to 0.2, cap Â±1.5)
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
RUST_THRESHOLD_MODERATE = 28       # days without match â†’ moderate rust
RUST_THRESHOLD_SEVERE = 42         # days â†’ significant rust
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
    # ITF/Futures: M15, M25, M5, W15, W25, W5 etc. â€” exclude these
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
    print(f"  Venue stats: {len(venue_lookup):,} rows" + (" (venue adjustment active)" if venue_lookup else " (none â€“ run venue pipeline or create table)"))

    # 5b) Player record at altitude (win % at high-altitude venues by surface) â€“ used when match is at altitude
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
    # Warn if same surname appears for multiple players in today's fixtures (e.g. two Cerundolos) â€“ wrong ID in OnCourt today_atp can cause wrong odds
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

        if s1 is None or s2 is None:
            if s1 is None and s2 is None:
                skip_missing_both += 1
            elif s1 is None:
                skip_missing_p1 += 1
            else:
                skip_missing_p2 += 1
            continue

        # Blend 12m with long-window (36m); adaptive by match count (less recent when few matches)
        h1_12 = _float(s1.get("hold_pct"), 0.65)
        r1_12 = _float(s1.get("return_pct"), 0.35)
        h2_12 = _float(s2.get("hold_pct"), 0.65)
        r2_12 = _float(s2.get("return_pct"), 0.35)
        h1_long = _float(s1.get("hold_pct_long"), h1_12)
        r1_long = _float(s1.get("return_pct_long"), r1_12)
        h2_long = _float(s2.get("hold_pct_long"), h2_12)
        r2_long = _float(s2.get("return_pct_long"), r2_12)
        mc1_12 = int(s1.get("match_count") or 0)
        mc2_12 = int(s2.get("match_count") or 0)
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
        surf_hold = SURFACE_AVG_HOLD.get(surface, 0.64)
        surf_ret = SURFACE_AVG_RETURN.get(surface, 0.36)
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
        # Venue SPW adjustment: use venue-adjusted p_a, p_b for expected games when tournament_serve_profile has data
        p_a_eg, p_b_eg = p_a, p_b
        if tid is not None:
            venue_spw = venue_serve_lookup.get((tid, surface))
            if venue_spw is not None and league_avg > 0:
                speed_ratio = venue_spw / league_avg
                speed_ratio = max(SPEED_RATIO_CLAMP[0], min(SPEED_RATIO_CLAMP[1], speed_ratio))
                p_a_eg = max(0.50, min(0.80, p_a * speed_ratio))
                p_b_eg = max(0.50, min(0.80, p_b * speed_ratio))
        exp_games = expected_total_games_best_of_3(p_a_eg, p_b_eg)
        tour_shift = tour_shift_lookup.get((tid, surface)) if tid is not None else None
        if tour_shift is not None:
            # Residual shift only (venue SPW adjustment does most of the work when tournament_serve_profile is populated)
            raw_add = TOURNAMENT_TOTAL_WEIGHT * tour_shift
            exp_games = exp_games + max(-TOURNAMENT_TOTAL_SHIFT_CAP, min(TOURNAMENT_TOTAL_SHIFT_CAP, raw_add))
        # Soft clamp: bo3 realistic range [12, 48]; 38 was too low and clamped too many matches to same value
        exp_games = max(12.0, min(48.0, exp_games))
        # Sackmann: 50/50 blend of single-surface and overall Elo predicts best
        p_elo_surface = 1.0 / (1.0 + 10.0 ** ((e2_s - e1_s) / 400.0))
        if e1_o is not None and e2_o is not None:
            p_elo_overall = 1.0 / (1.0 + 10.0 ** ((float(e2_o) - float(e1_o)) / 400.0))
            p_elo = 0.5 * p_elo_surface + 0.5 * p_elo_overall
        else:
            p_elo = p_elo_surface
        # General ability: surface points primary when available; else log-rank (ATP); rank blend 0.15
        r1, r2 = atp_rank_by_player.get(p1), atp_rank_by_player.get(p2)
        pts1 = surface_points_by_player.get(p1, {}).get(surface) if surface in ("Hard", "Clay", "Grass", "I.hard") else None
        pts2 = surface_points_by_player.get(p2, {}).get(surface) if surface in ("Hard", "Clay", "Grass", "I.hard") else None
        p_rank = None
        if pts1 is not None and pts2 is not None and (pts1 > 0 or pts2 > 0):
            p_rank = pts1 / (pts1 + pts2)
        elif r1 is not None and r2 is not None and r1 > 0 and r2 > 0:
            log_scale = LOG_RANK_SCALE
            p_rank = 1.0 / (1.0 + 10.0 ** ((math.log(max(1, r1)) - math.log(max(1, r2))) / log_scale))
        if p_rank is not None:
            p_elo = (1.0 - RANK_ELO_BLEND) * p_elo + RANK_ELO_BLEND * p_rank
        # Hybrid: default 40% Elo / 60% serve-return; lean more on Elo when either player has few surface matches
        elo_weight = HYBRID_ELO_WEIGHT_DEFAULT + 0.3 * max(0.0, 1.0 - min(min_matches_12, HYBRID_ELO_WEIGHT_MIN_MATCHES) / float(HYBRID_ELO_WEIGHT_MIN_MATCHES))
        elo_weight = max(0.3, min(0.7, elo_weight))
        # When serve/return is uninformative (near 50/50) but Elo/rank strongly favour one player, trust Elo+rank more
        # (e.g. Pellegrino vs Darderi: identical hold/return in DB -> 50/50; Elo and rank say Darderi heavy favourite)
        if abs(p_serve_return - 0.5) < 0.04 and p_rank is not None:
            p_elo_effective = 0.4 * p_elo + 0.6 * p_rank
            elo_weight = 0.9
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
            server_strength = max(0.0, (hold2 - surf_hold) / 0.13) if surf_hold < 0.75 else 1.0  # 0.75 - 0.62 â‰ˆ 0.13 for clay
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
        # Age: prime vs decline (scale so max effect ~ Â±0.01)
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
        delta_p1 = max(-0.04, min(0.04, delta_p1))  # overall cap Â±0.04
        p1_win += delta_p1
        p2_win -= delta_p1

        if do_debug:
            n1, n2 = name_by_player.get(p1, ""), name_by_player.get(p2, "")
            n1_l, n2_l = n1.lower(), n2.lower()
            if any(d in n1_l or d in n2_l for d in debug_names):
                print(f"\n  [DEBUG] {n1} (P1 id={p1}) vs {n2} (P2 id={p2}) surface={surface}")
                print(f"    Elo surface: P1={e1_s:.0f} P2={e2_s:.0f}  Overall: P1={e1_o} P2={e2_o}")
                mc1 = s1.get("match_count"); sp1 = s1.get("service_pts"); mc2 = s2.get("match_count"); sp2 = s2.get("service_pts")
                print(f"    Hold/return 12m: P1 hold={hold1:.3f} ret={ret1:.3f}  P2 hold={hold2:.3f} ret={ret2:.3f}  (P1 matches={mc1} svc_pts={sp1}  P2 matches={mc2} svc_pts={sp2})")
                print(f"    ATP rank: P1={atp_rank_by_player.get(p1)} P2={atp_rank_by_player.get(p2)}")
                print(f"    p_elo={p_elo:.4f} p_serve_return={p_serve_return:.4f} -> p1_win={p1_win:.4f} (after adj)")
                o1 = 1.0 / p1_win if p1_win > 0 else 0
                o2 = 1.0 / p2_win if p2_win > 0 else 0
                print(f"    Our fair odds: P1={o1:.2f} P2={o2:.2f}  (if P1 favoured, P1 odds should be lower e.g. ~1.2)")
                print(f"    Expected total games: {exp_games:.1f}")
                if (mc1 is not None and int(mc1 or 0) < 10) or (mc2 is not None and int(mc2 or 0) < 10):
                    print(f"    ^ Low match_count -> hold/return may be noisy. Re-run oncourt-compute-player-stats after fresh extract, or add prior when sample small.")

        # Normalize
        tot = p1_win + p2_win
        if tot > 0:
            p1_win, p2_win = p1_win / tot, p2_win / tot
        odds1 = 1.0 / p1_win if p1_win > 0 else 100.0
        odds2 = 1.0 / p2_win if p2_win > 0 else 100.0

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
        })

    print(f"Computed {len(out)} fair odds rows")
    print(f"  Fixture surfaces (from tour_id): {dict(surface_counts)}")
    print(f"  Skipped: no player1/player2 = {skip_no_players}, missing stats both = {skip_missing_both}, P1 only = {skip_missing_p1}, P2 only = {skip_missing_p2}")
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
    main()
```

This is the full script (all 716 lines). Paste Part 1 + Part 2 + this file into Claude when he doesnâ€™t have repo access so he can check column names, function signatures, and table shapes against the migration plan and expected-totals recipe.

