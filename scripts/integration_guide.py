"""
INTEGRATION GUIDE - Wiring matchup + fatigue into the live pipeline
==================================================================
Exact code changes for scripts/oncourt-compute-fair-odds.py.

Files that must be in scripts/:
  - matchup_model.py
  - fatigue_model.py
  - live_model_v2.py

Prerequisites:
  - Run supabase-migration-player-stats-v2.sql in Supabase
  - Run oncourt-compute-player-stats-extended.py to populate v2 table
  - oncourt_games table must exist (it already does from your OnCourt sync)

All changes below use ## CHANGE markers. Search for these in your editor.
"""

# -----------------------------------------------------------------------
# CHANGE 1: Add import (top of file, after existing imports)
# -----------------------------------------------------------------------

CHANGE_1 = """
# --- V2 MODEL ---
from live_model_v2 import LiveModelV2
# --- END V2 ---
"""

# -----------------------------------------------------------------------
# CHANGE 2: Initialise model and load data (after existing data fetches)
# -----------------------------------------------------------------------

CHANGE_2 = """
    # --- V2 MODEL: load decomposed stats + recent games ---
    v2_model = LiveModelV2(url, key)
    v2_model.load_data(fixture_player_ids, venue_tour_ids, tour_to_surface)
    # --- END V2 ---
"""

# -----------------------------------------------------------------------
# CHANGE 3: Replace p_a/p_b calculation (in the fixture loop)
# -----------------------------------------------------------------------

CHANGE_3 = """
        # --- V2 MODEL: matchup-aware point probabilities ---
        p_a, p_b, _matchup_method = v2_model.point_probs(
            p1, p2, surface,
            hold1=hold1, ret1=ret1, hold2=hold2, ret2=ret2,
            league_avg=league_avg,
        )
        # --- END V2 ---
"""

# -----------------------------------------------------------------------
# CHANGE 4: Replace fatigue calculation (in the fixture loop)
# -----------------------------------------------------------------------

CHANGE_4 = """
        # --- V2 MODEL: compound fatigue + form ---
        delta_fatigue_v2 = v2_model.fatigue_delta(p1, p2, date.today(), surface, tid)

        def _form_only(pid, player_elo_surface):
            act = recent_activity_by_player.get(pid)
            if not act:
                return 0.0
            m21 = int(act.get("matches_last_21d") or 0)
            wr = _float(act.get("win_rate_21d"))
            avg_opp = _float(act.get("avg_opponent_elo"), 1500)
            delta_form = 0.0
            if m21 >= FORM_MIN_MATCHES and wr is not None and avg_opp is not None:
                expected_wr = 1.0 / (1.0 + 10.0 ** ((avg_opp - player_elo_surface) / 400.0))
                delta_form = (wr - expected_wr) * FORM_WEIGHT
                delta_form = max(-FORM_CAP, min(FORM_CAP, delta_form))
            return delta_form

        p1_form = _form_only(p1, e1_s)
        p2_form = _form_only(p2, e2_s)
        delta_p1_form = 0.5 * (p1_form - p2_form)
        delta_p1_form = max(-FORM_TOTAL_CAP, min(FORM_TOTAL_CAP, delta_p1_form))

        delta_p1 += delta_p1_form + delta_fatigue_v2
        # --- END V2 ---
"""

# -----------------------------------------------------------------------
# CHANGE 5: Print summary at end (after the main loop, before DB write)
# -----------------------------------------------------------------------

CHANGE_5 = """
    # --- V2 MODEL: summary ---
    v2_model.print_summary()
    # --- END V2 ---
"""


if __name__ == "__main__":
    print("Integration Guide - changes to oncourt-compute-fair-odds.py")
    print("=" * 60)
    print("\nChange 1 (import):")
    print(CHANGE_1)
    print("Change 2 (init + load):")
    print(CHANGE_2)
    print("Change 3 (p_a/p_b):")
    print(CHANGE_3)
    print("Change 4 (fatigue):")
    print(CHANGE_4)
    print("Change 5 (summary):")
    print(CHANGE_5)
    print("\nTotal: 5 changes, ~30 lines of new code.")
    print("All existing logic preserved as fallback.")
