"""
Extended Player Stats — oncourt-compute-player-stats-extended.py
================================================================
Drop-in replacement for oncourt-compute-player-stats.py that computes
DECOMPOSED serve/return profiles alongside the existing hold%/return%.

New stats per (player_id, surface):

  SERVE DECOMPOSITION:
    first_serve_pct       = first_serves_in / first_serve_attempts
    first_serve_win_pct   = points_won_on_first_serve / first_serves_in
    second_serve_win_pct  = points_won_on_second_serve / second_serves_in
    ace_rate              = aces / total_serve_points
    df_rate               = double_faults / total_serve_points

  PRESSURE:
    bp_save_rate          = break_points_saved / break_points_faced
    bp_convert_rate       = break_points_won / break_points_faced_on_return

  RETURN DECOMPOSITION:
    return_pct (existing)  = return_points_won / return_points_faced
    ret_vs_first_win_pct   = return points won vs opponent's first serve
    ret_vs_second_win_pct  = return points won vs opponent's second serve

All stats computed for both 12m and 36m windows, matching the existing
script's dual-window approach.

Writes to player_surface_stats_v2 (new table) to avoid breaking existing
pipeline. Run migration first: docs/supabase-migration-player-stats-v2.sql

Usage:
  python scripts/oncourt-compute-player-stats-extended.py [--dry-run]
  python scripts/oncourt-compute-player-stats-extended.py --dry-run --sample 10

Backwards compatible: also writes to player_surface_stats (existing table)
with the same hold%/return% columns, so the existing fair-odds pipeline
continues to work unchanged.
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
ROLLING_DAYS_LONG = 1095  # 36 months
BATCH = 500

TOUR_CLASS_WEIGHTS = {
    4: 1.08,  # Grand Slams
    3: 1.04,  # Masters / Tour Finals
    2: 1.00,  # ATP Tour level
    1: 0.72,  # Challengers
    0: 0.42,  # ITF / Futures
    5: 0.88,  # Davis Cup / team events
    6: 0.15,  # Juniors
}


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
        return int(float(v))
    except (ValueError, TypeError):
        return default


def _safe_div(num, den, ndigits=4):
    """Safe division with rounding. Returns None if denominator is 0."""
    if den > 0:
        return round(num / den, ndigits)
    return None


def _weighted_count(value):
    if value is None:
        return 0
    if value <= 0:
        return 0
    return max(1, int(round(value)))


def _tour_class_weight(tour_rank, tour_name):
    try:
        rank = int(tour_rank) if tour_rank is not None else None
    except (TypeError, ValueError):
        rank = None

    name = (tour_name or "").upper()
    if "JUNIOR" in name:
        return TOUR_CLASS_WEIGHTS[6]
    if "DAVIS CUP" in name or "BILLIE JEAN KING" in name:
        return TOUR_CLASS_WEIGHTS[5]
    if rank in TOUR_CLASS_WEIGHTS:
        return TOUR_CLASS_WEIGHTS[rank]
    return 0.80


# ══════════════════════════════════════════════════════════════════════════════
# Aggregation template: all the buckets we need
# ══════════════════════════════════════════════════════════════════════════════

def new_agg():
    """Create a fresh aggregation bucket with all stat accumulators."""
    return {
        # Existing (hold/return)
        "hold_num": 0, "hold_den": 0,     # hold% = (w1s+w2s) / (fsof+w2sof)
        "return_num": 0, "return_den": 0,  # return% = rpw / rpwof

        # Serve decomposition
        "first_in": 0,             # first serves in (w_1stin / l_1stin)
        "first_attempts": 0,       # first serve attempts (fsof)
        "first_won": 0,            # points won on first serve (w_1stwon or w_w1s)
        "second_attempts": 0,      # second serve attempts (w2sof)
        "second_won": 0,           # points won on second serve (w_w2s)
        "aces": 0,                 # aces
        "dfs": 0,                  # double faults
        "total_serve_pts": 0,      # total serve points played (svpt or fsof+w2sof)

        # Return decomposition (derived from opponent's serve stats)
        "ret_vs_first_won": 0,     # return points won vs opponent's first serve
        "ret_vs_first_faced": 0,   # opponent's first serves in (= chances to return)
        "ret_vs_second_won": 0,    # return points won vs opponent's second serve
        "ret_vs_second_faced": 0,  # opponent's second serves in

        # Pressure
        "bp_saved": 0, "bp_faced": 0,         # break points on serve
        "bp_won": 0, "bp_opp_faced": 0,       # break points on return

        # Meta
        "matches": 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    do_dry_run = "--dry-run" in sys.argv
    show_sample = 0
    for i, arg in enumerate(sys.argv):
        if arg == "--sample" and i + 1 < len(sys.argv):
            try:
                show_sample = int(sys.argv[i + 1])
            except ValueError:
                pass

    if do_dry_run:
        print("Dry run: will not write to Supabase\n")

    cutoff = (datetime.now() - timedelta(days=ROLLING_DAYS)).date()
    cutoff_long = (datetime.now() - timedelta(days=ROLLING_DAYS_LONG)).date()
    print(f"Windows: 12m from {cutoff}, 36m from {cutoff_long}\n")

    # ── Load reference data ──
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

    # Court → surface mapping
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
    tour_id_to_weight = {}
    for r in tours:
        tid = r.get("id")
        cid = r.get("court_id")
        if tid and cid:
            try:
                raw = court_id_to_surface.get(int(cid), "N/A")
                tid_int = int(tid)
                tour_id_to_surface[tid_int] = _court_to_surface(raw) if raw != "N/A" else raw
                tour_id_to_weight[tid_int] = _tour_class_weight(r.get("rank"), r.get("name"))
            except ValueError:
                pass

    # Game key → (date, surface) for window filtering
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
        weight = tour_id_to_weight.get(t, 0.80)
        if dt >= cutoff:
            game_key_to_info[(w, l, t, rd)] = (dt, surface, weight)
        if dt >= cutoff_long:
            game_key_to_info_long[(w, l, t, rd)] = (dt, surface, weight)

    print(f"  Games in 12m: {len(game_key_to_info):,}, 36m: {len(game_key_to_info_long):,}")

    # ── Load stat rows ──
    print("Loading stat...")
    stat_rows = load_csv(stat_path)
    print(f"  Stat rows: {len(stat_rows):,}")

    # Detect which columns are available (with OnCourt alias support)
    sample_row = stat_rows[0] if stat_rows else {}
    available_cols = set(sample_row.keys())

    # OnCourt exports use varying column names across versions.
    # Build a resolver: concept → actual column name in this CSV.
    # For each stat, try primary name first, then known aliases.
    ALIASES = {
        "ace":      ["ace", "aces"],
        "df":       ["df", "dfs"],
        "1stin":    ["1stin", "fs", "fsin", "1st_in"],           # first serves in
        # OnCourt stat_atp exports first-serve points won as w_w1s / l_w1s.
        # Include w1s aliases so we don't silently default first_serve_win_pct to 0.0.
        "1stwon":   ["1stwon", "fsw", "fs_won", "1st_won", "w1s"],     # first serve points won
        "2ndwon":   ["2ndwon", "ssw", "ss_won", "2nd_won"],     # second serve points won (alt source for w2s)
        "svpt":     ["svpt", "sv_pt", "serve_pts"],
        "bpsaved":  ["bpsaved", "bp_saved", "bps"],
        "bpfaced":  ["bpfaced", "bp_faced", "bpf"],
        "bpw":      ["bpw", "bp_won"],
        "bpof":     ["bpof", "bp_offered", "bp_opp"],
        "svgms":    ["svgms", "sv_gms", "service_games"],
    }

    def _resolve_col(prefix, concept):
        """Find the actual column name for a concept given a prefix (w_ or l_)."""
        for alias in ALIASES.get(concept, [concept]):
            candidate = f"{prefix}{alias}"
            if candidate in available_cols:
                return candidate
        return None

    # Detect availability using winner prefix
    col_ace = _resolve_col("w_", "ace")
    col_df = _resolve_col("w_", "df")
    col_1stin = _resolve_col("w_", "1stin")
    col_1stwon = _resolve_col("w_", "1stwon")
    col_svpt = _resolve_col("w_", "svpt")
    col_bpsaved = _resolve_col("w_", "bpsaved")
    col_bpfaced = _resolve_col("w_", "bpfaced")
    col_bpw = _resolve_col("w_", "bpw")
    col_bpof = _resolve_col("w_", "bpof")

    has_ace = col_ace is not None
    has_df = col_df is not None
    has_1stin = col_1stin is not None
    has_1stwon = col_1stwon is not None
    has_bp_saved = col_bpsaved is not None
    has_bp_won = col_bpw is not None
    has_svpt = col_svpt is not None

    def _get_stat(r, prefix, concept, default=0):
        """Read a stat column using alias resolution."""
        for alias in ALIASES.get(concept, [concept]):
            candidate = f"{prefix}{alias}"
            if candidate in available_cols:
                return _int(r, candidate, default)
        return default

    print(f"\n  Available columns for decomposition:")
    print(f"    Aces: {'OK '+col_ace if has_ace else 'NO'}  DF: {'OK '+col_df if has_df else 'NO'}  "
          f"1st-in: {'OK '+col_1stin if has_1stin else 'NO'}  1st-won: {'OK '+col_1stwon if has_1stwon else 'NO'}")
    print(f"    BP saved: {'OK '+col_bpsaved if has_bp_saved else 'NO'}  BP won: {'OK '+col_bpw if has_bp_won else 'NO'}  "
          f"SvPt: {'OK '+col_svpt if has_svpt else 'NO'}")
    if not has_1stin:
        print(f"    WARN: No first-serve-in column found. first_serve_pct and first_serve_win_pct will be None.")
        print(f"      Check OnCourt export for columns like: w_1stin, w_fs, w_fsin")
    if not has_ace:
        print(f"    WARN: No aces column found. ace_rate will be None.")
        print(f"      Check OnCourt export for: w_ace, w_aces")
    if not has_bp_saved:
        print(f"    WARN: No break point columns found. bp_save_rate/bp_convert_rate will be None.")
        print(f"      Check OnCourt export for: w_bpsaved, w_bpfaced, w_bpw, w_bpof")

    # ── Aggregate ──
    print("\nAggregating...")
    agg = defaultdict(new_agg)
    agg_long = defaultdict(new_agg)

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
        _date, surface, class_weight = game_key_to_info.get(key) or game_key_to_info_long[key]

        # Read all stat columns for winner and loser
        # We need BOTH sides to compute return decomposition
        # (Player A's return vs 1st serve = opponent's 1st serves in - opponent's 1st serve won)
        player_stats = {}
        for prefix, pid in [("w_", w), ("l_", l)]:
            fsof = _int(r, f"{prefix}fsof")
            w2sof = _int(r, f"{prefix}w2sof")
            w1s = _int(r, f"{prefix}w1s")
            w2s = _int(r, f"{prefix}w2s")
            rpw = _int(r, f"{prefix}rpw")
            rpwof = _int(r, f"{prefix}rpwof")

            # Optional columns (using alias resolver)
            aces = _get_stat(r, prefix, "ace") if has_ace else 0
            dfs = _get_stat(r, prefix, "df") if has_df else 0
            first_in = _get_stat(r, prefix, "1stin") if has_1stin else 0
            first_won = _get_stat(r, prefix, "1stwon") if has_1stwon else 0
            svpt = _get_stat(r, prefix, "svpt") if has_svpt else (fsof + w2sof)
            bp_saved = _get_stat(r, prefix, "bpsaved") if has_bp_saved else 0
            bp_faced = _get_stat(r, prefix, "bpfaced") if has_bp_saved else 0
            bp_won = _get_stat(r, prefix, "bpw") if has_bp_won else 0
            bp_opp_faced = _get_stat(r, prefix, "bpof") if has_bp_won else 0

            player_stats[pid] = {
                "fsof": fsof, "w2sof": w2sof, "w1s": w1s, "w2s": w2s,
                "rpw": rpw, "rpwof": rpwof,
                "aces": aces, "dfs": dfs, "first_in": first_in,
                "first_won": first_won, "svpt": svpt,
                "bp_saved": bp_saved, "bp_faced": bp_faced,
                "bp_won": bp_won, "bp_opp_faced": bp_opp_faced,
            }

        # Now accumulate for each player, using opponent's serve for return decomposition
        for pid, opp_pid in [(w, l), (l, w)]:
            ps = player_stats[pid]
            opp = player_stats[opp_pid]

            # Accumulate into both windows
            for ag, use in [(agg, in_12m), (agg_long, in_long)]:
                if not use:
                    continue
                k = (pid, surface)

                # Existing hold/return
                if ps["fsof"] + ps["w2sof"] > 0:
                    ag[k]["hold_num"] += (ps["w1s"] + ps["w2s"]) * class_weight
                    ag[k]["hold_den"] += (ps["fsof"] + ps["w2sof"]) * class_weight
                if ps["rpwof"] > 0:
                    ag[k]["return_num"] += ps["rpw"] * class_weight
                    ag[k]["return_den"] += ps["rpwof"] * class_weight

                # Serve decomposition (own serve stats)
                ag[k]["first_attempts"] += ps["fsof"] * class_weight
                ag[k]["first_in"] += ps["first_in"] * class_weight
                ag[k]["first_won"] += ps["first_won"] * class_weight
                ag[k]["second_attempts"] += ps["w2sof"] * class_weight
                ag[k]["second_won"] += ps["w2s"] * class_weight
                ag[k]["aces"] += ps["aces"] * class_weight
                ag[k]["dfs"] += ps["dfs"] * class_weight
                ag[k]["total_serve_pts"] += ps["svpt"] * class_weight

                # Return decomposition (from OPPONENT's serve stats)
                # My return vs opponent's first serve:
                #   opponent had first_in first serves in, won first_won of them
                #   → I won (first_in - first_won) return points vs their first serve
                if opp["first_in"] > 0:
                    ag[k]["ret_vs_first_won"] += (opp["first_in"] - opp["first_won"]) * class_weight
                    ag[k]["ret_vs_first_faced"] += opp["first_in"] * class_weight
                # My return vs opponent's second serve:
                #   opponent had w2sof second serves, won w2s of them
                #   → I won (w2sof - w2s) return points vs their second serve
                if opp["w2sof"] > 0:
                    ag[k]["ret_vs_second_won"] += (opp["w2sof"] - opp["w2s"]) * class_weight
                    ag[k]["ret_vs_second_faced"] += opp["w2sof"] * class_weight

                # Pressure
                ag[k]["bp_saved"] += ps["bp_saved"] * class_weight
                ag[k]["bp_faced"] += ps["bp_faced"] * class_weight
                ag[k]["bp_won"] += ps["bp_won"] * class_weight
                ag[k]["bp_opp_faced"] += ps["bp_opp_faced"] * class_weight

                ag[k]["matches"] += class_weight

    # ── Build output rows ──
    print("Building output rows...")
    out = []
    for (player_id, surface), v in agg.items():
        vlong = agg_long.get((player_id, surface), new_agg())

        row = {
            "player_id": player_id,
            "surface": surface,
            "match_count": _weighted_count(v["matches"]),
            "service_pts": _weighted_count(v["hold_den"]),
            "return_pts": _weighted_count(v["return_den"]),

            # ── Existing stats (12m) ──
            "hold_pct": _safe_div(v["hold_num"], v["hold_den"]),
            "return_pct": _safe_div(v["return_num"], v["return_den"]),

            # ── Existing stats (36m) ──
            "hold_pct_long": _safe_div(vlong["hold_num"], vlong["hold_den"]),
            "return_pct_long": _safe_div(vlong["return_num"], vlong["return_den"]),
            "match_count_long": _weighted_count(vlong["matches"]),

            # ── NEW: Serve decomposition (12m) ──
            "first_serve_pct": _safe_div(v["first_in"], v["first_attempts"]),
            "first_serve_win_pct": _safe_div(v["first_won"], v["first_in"]) if v["first_in"] > 0 else None,
            "second_serve_win_pct": _safe_div(v["second_won"], v["second_attempts"]),
            "ace_rate": _safe_div(v["aces"], v["total_serve_pts"]) if has_ace else None,
            "df_rate": _safe_div(v["dfs"], v["total_serve_pts"]) if has_df else None,

            # ── NEW: Pressure (12m) ──
            "bp_save_rate": _safe_div(v["bp_saved"], v["bp_faced"]) if has_bp_saved else None,
            "bp_convert_rate": _safe_div(v["bp_won"], v["bp_opp_faced"]) if has_bp_won else None,

            # ── NEW: Return decomposition (12m) ──
            "ret_vs_first_win_pct": _safe_div(v["ret_vs_first_won"], v["ret_vs_first_faced"]),
            "ret_vs_second_win_pct": _safe_div(v["ret_vs_second_won"], v["ret_vs_second_faced"]),

            # ── NEW: Raw counts for downstream use ──
            "aces_total": _weighted_count(v["aces"]),
            "dfs_total": _weighted_count(v["dfs"]),
            "bp_faced_total": _weighted_count(v["bp_faced"]),
            "bp_saved_total": _weighted_count(v["bp_saved"]),
            "ret_vs_first_faced_total": _weighted_count(v["ret_vs_first_faced"]),
            "ret_vs_second_faced_total": _weighted_count(v["ret_vs_second_faced"]),

            # ── NEW: Serve decomposition (36m) ──
            "first_serve_pct_long": _safe_div(vlong["first_in"], vlong["first_attempts"]),
            "first_serve_win_pct_long": _safe_div(vlong["first_won"], vlong["first_in"]) if vlong["first_in"] > 0 else None,
            "second_serve_win_pct_long": _safe_div(vlong["second_won"], vlong["second_attempts"]),
            "ace_rate_long": _safe_div(vlong["aces"], vlong["total_serve_pts"]) if has_ace else None,
            "df_rate_long": _safe_div(vlong["dfs"], vlong["total_serve_pts"]) if has_df else None,
            "bp_save_rate_long": _safe_div(vlong["bp_saved"], vlong["bp_faced"]) if has_bp_saved else None,
            "bp_convert_rate_long": _safe_div(vlong["bp_won"], vlong["bp_opp_faced"]) if has_bp_won else None,

            # ── NEW: Return decomposition (36m) ──
            "ret_vs_first_win_pct_long": _safe_div(vlong["ret_vs_first_won"], vlong["ret_vs_first_faced"]),
            "ret_vs_second_win_pct_long": _safe_div(vlong["ret_vs_second_won"], vlong["ret_vs_second_faced"]),
        }

        out.append(row)

    print(f"\nComputed {len(out):,} (player_id, surface) rows")
    if out:
        by_surface = defaultdict(int)
        for row in out:
            by_surface[row["surface"]] += 1
        print(f"  By surface: {dict(by_surface)}")

        # Coverage report: how many players have the new stats?
        has_fsw = sum(1 for r in out if r.get("first_serve_win_pct") is not None)
        has_ssw = sum(1 for r in out if r.get("second_serve_win_pct") is not None)
        has_ace = sum(1 for r in out if r.get("ace_rate") is not None)
        has_bp = sum(1 for r in out if r.get("bp_save_rate") is not None)
        has_rvf = sum(1 for r in out if r.get("ret_vs_first_win_pct") is not None)
        has_rvs = sum(1 for r in out if r.get("ret_vs_second_win_pct") is not None)
        print(f"\n  Coverage (12m):")
        print(f"    first_serve_win_pct:    {has_fsw:,} / {len(out):,} ({has_fsw/len(out)*100:.0f}%)")
        print(f"    second_serve_win_pct:   {has_ssw:,} / {len(out):,} ({has_ssw/len(out)*100:.0f}%)")
        print(f"    ace_rate:               {has_ace:,} / {len(out):,} ({has_ace/len(out)*100:.0f}%)")
        print(f"    bp_save_rate:           {has_bp:,} / {len(out):,} ({has_bp/len(out)*100:.0f}%)")
        print(f"    ret_vs_first_win_pct:   {has_rvf:,} / {len(out):,} ({has_rvf/len(out)*100:.0f}%)")
        print(f"    ret_vs_second_win_pct:  {has_rvs:,} / {len(out):,} ({has_rvs/len(out)*100:.0f}%)")

    # Show sample profiles
    if show_sample > 0 and out:
        print(f"\n  Sample profiles (top {show_sample} by match count)")
        sorted_out = sorted(out, key=lambda r: -r.get("match_count", 0))
        for r in sorted_out[:show_sample]:
            print(f"\n  Player {r['player_id']} on {r['surface']} ({r['match_count']} matches):")
            print(f"    hold%={r.get('hold_pct','?')} return%={r.get('return_pct','?')}")
            print(f"    1st serve %:     {r.get('first_serve_pct', '?')}")
            print(f"    1st serve win %: {r.get('first_serve_win_pct', '?')}")
            print(f"    2nd serve win %: {r.get('second_serve_win_pct', '?')}")
            print(f"    ace rate:        {r.get('ace_rate', '?')}")
            print(f"    DF rate:         {r.get('df_rate', '?')}")
            print(f"    BP save rate:    {r.get('bp_save_rate', '?')}")
            print(f"    BP convert rate: {r.get('bp_convert_rate', '?')}")
            print(f"    ret vs 1st win%: {r.get('ret_vs_first_win_pct', '?')}")
            print(f"    ret vs 2nd win%: {r.get('ret_vs_second_win_pct', '?')}")

    if do_dry_run:
        print("\nDry run done. Run without --dry-run to upsert.")
        return

    # ── Write to Supabase ──
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

    # 1. Write to player_surface_stats_v2 (new table with all columns)
    V2_TABLE = "player_surface_stats_v2"
    print(f"\nUpserting to {V2_TABLE}...")
    v2_success = True
    for i in range(0, len(out), BATCH):
        batch = out[i : i + BATCH]
        r = requests.post(
            f"{url.rstrip('/')}/rest/v1/{V2_TABLE}",
            headers=headers,
            json=batch,
            timeout=60,
        )
        if r.status_code >= 400:
            print(f"  ERROR {r.status_code} posting to {V2_TABLE} at batch starting row {i}.")
            print(f"  Response: {r.text[:2000]}")
        if r.status_code in (404, 400) and i == 0:
            print(f"  Table {V2_TABLE} does not exist. Run the migration SQL first:")
            print(f"  docs/supabase-migration-player-stats-v2.sql")
            v2_success = False
            break
        r.raise_for_status()
        if (i + BATCH) % 5000 == 0 or i + BATCH >= len(out):
            print(f"  {min(i + BATCH, len(out)):,} / {len(out):,}")
    if v2_success:
        print(f"  {V2_TABLE}: done.")

    # 2. Also write to existing player_surface_stats (backwards compatibility)
    BASE_COLS = ["player_id", "surface", "hold_pct", "return_pct", "match_count",
                 "service_pts", "return_pts"]
    LONG_COLS = BASE_COLS + ["hold_pct_long", "return_pct_long", "match_count_long"]
    use_long = True

    print(f"\nUpserting to player_surface_stats (backwards compat)...")
    for i in range(0, len(out), BATCH):
        batch = out[i : i + BATCH]
        cols = LONG_COLS if use_long else BASE_COLS
        payload = [{k: row.get(k) for k in cols} for row in batch]
        r = requests.post(
            f"{url.rstrip('/')}/rest/v1/player_surface_stats",
            headers=headers,
            json=payload,
            timeout=60,
        )
        if r.status_code == 400 and use_long:
            use_long = False
            payload = [{k: row.get(k) for k in BASE_COLS} for row in batch]
            r = requests.post(
                f"{url.rstrip('/')}/rest/v1/player_surface_stats",
                headers=headers,
                json=payload,
                timeout=60,
            )
        r.raise_for_status()
        if (i + BATCH) % 5000 == 0 or i + BATCH >= len(out):
            print(f"  {min(i + BATCH, len(out)):,} / {len(out):,}")
    print("  player_surface_stats: done.")

    print("\nAll done.")


if __name__ == "__main__":
    main()
