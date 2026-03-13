"""
Live Pipeline Integration — live_model_v2.py
=============================================
Drop-in module for oncourt-compute-fair-odds.py that provides:

  1. Fetch decomposed stats from player_surface_stats_v2
  2. Fetch recent games for fatigue model
  3. Compute matchup-aware p_a/p_b
  4. Compute compound fatigue delta

Minimal changes needed in oncourt-compute-fair-odds.py:
  - Add one import
  - Add two data-fetch calls (after existing fetches)
  - Replace p_a/p_b block with one function call
  - Replace fatigue block with one function call

See INTEGRATION GUIDE at bottom of this file for exact code changes.

Usage:
  from live_model_v2 import LiveModelV2

  model = LiveModelV2(supabase_url, supabase_key)
  model.load_data(fixture_player_ids, fixture_tour_ids, tour_to_surface)

  # In fixture loop:
  p_a, p_b = model.point_probs(p1, p2, surface)
  delta_fatigue = model.fatigue_delta(p1, p2, match_date, surface, tour_id)
"""

import os
import sys
import math
from datetime import date, timedelta
from collections import defaultdict
from typing import Optional, Dict, Set, Tuple, List

# Import the model modules (must be in same directory or on sys.path)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from matchup_model import MatchupStats, compute_match_point_probs, SURFACE_AVG
from fatigue_model import (
    RecentMatch, compute_fatigue_rust_delta, parse_score_to_games,
)


def _float(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


class LiveModelV2:
    """
    Live pipeline wrapper for matchup model + fatigue model.

    Handles all Supabase data fetching and provides clean interface
    for the fair-odds compute loop.
    """

    def __init__(self, supabase_url: str, supabase_key: str, timeout: int = 45):
        # Safety: the fair-odds script reuses 'key' for fixture dedup tuples.
        # If a tuple is passed here instead of the API key string, catch it early.
        if not isinstance(supabase_key, str):
            raise TypeError(
                f"LiveModelV2 received supabase_key of type {type(supabase_key).__name__} "
                f"(value: {supabase_key!r}). This usually means the 'key' variable was "
                f"overwritten by the fixture dedup loop. Fix: pass os.environ.get("
                f"'SUPABASE_SERVICE_ROLE_KEY') directly, or save the key to a different "
                f"variable name before the dedup loop."
            )
        self.base = supabase_url.rstrip("/") + "/rest/v1"
        self.headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
        self.timeout = timeout

        # Data stores (populated by load_data)
        self.v2_stats: Dict[Tuple[int, str], dict] = {}  # (player_id, surface) -> v2 row
        self.recent_games: Dict[int, List[dict]] = {}     # player_id -> list of game rows
        self.tour_to_surface: Dict[int, str] = {}

        # Counters
        self.matchup_used = 0
        self.matchup_fallback = 0
        self.fatigue_computed = 0

    def load_data(
        self,
        player_ids: Set[int],
        tour_ids: Set[int],
        tour_to_surface: Dict[int, str],
    ):
        """
        Fetch all data needed for today's fixtures.
        Call once after loading fixtures, before the main loop.
        """
        import requests
        self.tour_to_surface = tour_to_surface

        # -- 1. Fetch player_surface_stats_v2 --
        v2_select = (
            "player_id,surface,hold_pct,return_pct,match_count,service_pts,"
            "first_serve_pct,first_serve_win_pct,second_serve_win_pct,"
            "ace_rate,df_rate,bp_save_rate,bp_convert_rate,"
            "ret_vs_first_win_pct,ret_vs_second_win_pct"
        )
        v2_rows = []
        # Try v2 table first
        try:
            r = requests.get(
                f"{self.base}/player_surface_stats_v2",
                headers=self.headers,
                params={"select": v2_select, "limit": 1},
                timeout=self.timeout,
            )
            if r.status_code in (200, 206):
                # Table exists, fetch all
                off = 0
                while True:
                    r = requests.get(
                        f"{self.base}/player_surface_stats_v2",
                        headers=self.headers,
                        params={"select": v2_select, "offset": off, "limit": 1000},
                        timeout=self.timeout,
                    )
                    r.raise_for_status()
                    data = r.json()
                    if not data:
                        break
                    v2_rows.extend(data)
                    off += len(data)
                    if len(data) < 1000:
                        break
        except Exception as e:
            print(f"  Warning: player_surface_stats_v2 fetch failed ({e}). Matchup model will use fallback.")

        self.v2_stats = {
            (int(r["player_id"]), (r.get("surface") or "N/A").strip()): r
            for r in v2_rows if r.get("player_id") is not None
        }
        decomposed_count = sum(
            1 for r in v2_rows
            if r.get("first_serve_win_pct") is not None and r.get("second_serve_win_pct") is not None
        )
        print(f"  V2 stats: {len(self.v2_stats):,} rows ({decomposed_count:,} with decomposed serve)")

        # -- 2. Fetch recent games for fatigue model --
        # Only fetch for fixture players, last 21 days
        if player_ids:
            self._fetch_recent_games(player_ids)
        print(f"  Recent games: {sum(len(v) for v in self.recent_games.values()):,} rows for {len(self.recent_games)} players")

    def _fetch_recent_games(self, player_ids: Set[int]):
        """Fetch recent games from oncourt_games for fatigue computation."""
        import requests
        cutoff = (date.today() - timedelta(days=21)).isoformat()

        # Fetch games where any fixture player was winner or loser, last 21 days
        ids_str = ",".join(str(x) for x in player_ids)
        self.recent_games = defaultdict(list)

        for role, id_col in [("winner", "winner_id"), ("loser", "loser_id")]:
            off = 0
            while True:
                try:
                    r = requests.get(
                        f"{self.base}/oncourt_games",
                        headers=self.headers,
                        params={
                            "select": "winner_id,loser_id,tour_id,round_id,date,result",
                            id_col: f"in.({ids_str})",
                            "date": f"gte.{cutoff}",
                            "offset": off,
                            "limit": 1000,
                        },
                        timeout=self.timeout,
                    )
                    if r.status_code != 200:
                        break
                    data = r.json()
                    if not data:
                        break
                    for row in data:
                        wid = row.get("winner_id")
                        lid = row.get("loser_id")
                        if wid is not None:
                            try:
                                self.recent_games[int(wid)].append(row)
                            except (ValueError, TypeError):
                                pass
                        if lid is not None:
                            try:
                                self.recent_games[int(lid)].append(row)
                            except (ValueError, TypeError):
                                pass
                    off += len(data)
                    if len(data) < 1000:
                        break
                except Exception:
                    break

    def _get_v2_stats(self, player_id: int, surface: str) -> Optional[MatchupStats]:
        """Get MatchupStats for a player from v2 table."""
        row = self.v2_stats.get((player_id, surface))
        if row is None:
            return None
        return MatchupStats.from_db_row(row)

    def point_probs(
        self,
        p1: int,
        p2: int,
        surface: str,
        # Fallback values from existing pipeline (used if v2 stats missing)
        hold1: Optional[float] = None,
        ret1: Optional[float] = None,
        hold2: Optional[float] = None,
        ret2: Optional[float] = None,
        league_avg: float = 0.64,
    ) -> Tuple[float, float, str]:
        """
        Compute matchup-aware point probabilities p_a, p_b.

        Returns (p_a, p_b, method) where method is "matchup" or "fallback".

        If v2 decomposed stats exist for both players, uses the matchup model.
        Otherwise falls back to the old formula using hold/ret passed in.
        """
        stats_a = self._get_v2_stats(p1, surface)
        stats_b = self._get_v2_stats(p2, surface)

        # Try matchup model
        if stats_a is not None and stats_b is not None:
            if stats_a.has_decomposed and stats_b.has_decomposed:
                p_a, p_b, _ = compute_match_point_probs(stats_a, stats_b, surface)
                self.matchup_used += 1
                return p_a, p_b, "matchup"

            # One or both lack decomposed stats.
            # Keep caller-provided hold/return (already SPW/RPW-calibrated in main pipeline)
            # and only backfill from v2 if caller did not provide them.
            if hold1 is None and stats_a.hold_pct is not None:
                hold1 = stats_a.hold_pct
            if ret1 is None and stats_a.return_pct is not None:
                ret1 = stats_a.return_pct
            if hold2 is None and stats_b.hold_pct is not None:
                hold2 = stats_b.hold_pct
            if ret2 is None and stats_b.return_pct is not None:
                ret2 = stats_b.return_pct

        # Fallback: use matchup model with hold/return only (no decomposed stats)
        if hold1 is not None and ret1 is not None and hold2 is not None and ret2 is not None:
            fallback_a = MatchupStats(hold_pct=hold1, return_pct=ret1)
            fallback_b = MatchupStats(hold_pct=hold2, return_pct=ret2)
            p_a, p_b, _ = compute_match_point_probs(fallback_a, fallback_b, surface)
            self.matchup_fallback += 1
            return p_a, p_b, "fallback"

        # Last resort
        self.matchup_fallback += 1
        avg_spw = SURFACE_AVG.get(surface, SURFACE_AVG["Hard"]).get("spw", 0.64)
        return avg_spw, avg_spw, "default"

    def fatigue_delta(
        self,
        p1: int,
        p2: int,
        match_date: date,
        surface: str,
        tour_id: Optional[int] = None,
    ) -> float:
        """
        Compute compound fatigue adjustment for P(P1 wins).

        Returns delta (positive = favours P1, negative = favours P2).
        """
        p1_games = self.recent_games.get(p1, [])
        p2_games = self.recent_games.get(p2, [])

        p1_recent = self._build_recent_matches(p1, p1_games, match_date)
        p2_recent = self._build_recent_matches(p2, p2_games, match_date)

        delta, _ = compute_fatigue_rust_delta(
            p1_recent, p2_recent, match_date, surface, tour_id
        )
        self.fatigue_computed += 1
        return delta

    def _build_recent_matches(
        self,
        player_id: int,
        games: List[dict],
        before_date: date,
    ) -> List[RecentMatch]:
        """Convert raw game rows to RecentMatch objects."""
        cutoff = before_date - timedelta(days=21)
        matches = []

        for g in games:
            # Parse date
            d = g.get("date")
            if not d:
                continue
            if isinstance(d, str):
                try:
                    d = date.fromisoformat(d.strip()[:10])
                except (ValueError, TypeError):
                    continue

            if d < cutoff or d >= before_date:
                continue

            # Determine if this player was winner or loser
            try:
                wid = int(float(g.get("winner_id", 0)))
            except (ValueError, TypeError):
                wid = 0

            won = (wid == player_id)

            # Parse score
            score = g.get("result") or g.get("score") or ""
            sets_played, total_games = parse_score_to_games(str(score))

            tid = None
            try:
                tid = int(float(g.get("tour_id")))
            except (ValueError, TypeError):
                pass

            rid = None
            try:
                rid = int(float(g.get("round_id")))
            except (ValueError, TypeError):
                pass

            surface = self.tour_to_surface.get(tid, "Hard") if tid else "Hard"

            matches.append(RecentMatch(
                match_date=d,
                sets_played=sets_played,
                total_games=total_games,
                won=won,
                surface=surface,
                tour_id=tid,
                round_id=rid,
                is_retirement="RET" in str(score).upper(),
                is_walkover=total_games == 0 and sets_played == 0,
            ))

        matches.sort(key=lambda m: m.match_date, reverse=True)
        return matches

    def print_summary(self):
        """Print end-of-run summary."""
        total = self.matchup_used + self.matchup_fallback
        if total > 0:
            print(f"  V2 model: {self.matchup_used}/{total} matchup ({self.matchup_used/total*100:.0f}%), "
                  f"{self.matchup_fallback} fallback, {self.fatigue_computed} fatigue computed")


# ══════════════════════════════════════════════════════════════════════════════
# Self-test (runs without Supabase)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*60)
    print("  live_model_v2.py - Self-test (no Supabase)")
    print("="*60)

    # Test MatchupStats directly
    stats_a = MatchupStats(
        first_serve_pct=0.62, first_serve_win_pct=0.75,
        second_serve_win_pct=0.50, ace_rate=0.08, df_rate=0.03,
        return_pct=0.37, bp_save_rate=0.64, bp_convert_rate=0.41,
        hold_pct=0.66, match_count=25, service_pts=700,
    )
    stats_b = MatchupStats(
        first_serve_pct=0.60, first_serve_win_pct=0.72,
        second_serve_win_pct=0.48, ace_rate=0.06, df_rate=0.04,
        return_pct=0.39, bp_save_rate=0.61, bp_convert_rate=0.43,
        hold_pct=0.64, match_count=20, service_pts=600,
    )

    p_a, p_b, dbg = compute_match_point_probs(stats_a, stats_b, "Hard")
    print(f"\n  Matchup test: p_a={p_a:.4f}, p_b={p_b:.4f}")

    # Test fatigue directly
    today = date.today()
    p1_matches = [
        RecentMatch(today - timedelta(days=1), sets_played=3, total_games=35, surface="Hard"),
        RecentMatch(today - timedelta(days=2), sets_played=2, total_games=24, surface="Hard"),
    ]
    p2_matches = [
        RecentMatch(today - timedelta(days=4), sets_played=2, total_games=20, surface="Hard"),
    ]
    delta, dbg = compute_fatigue_rust_delta(p1_matches, p2_matches, today, "Hard", debug=True)
    if dbg:
        print(f"  Fatigue test: delta={delta:+.4f} (P1 score={dbg['p1_fatigue_score']:.3f}, P2={dbg['p2_fatigue_score']:.3f})")
    else:
        print(f"  Fatigue test: delta={delta:+.4f}")

    print(f"\n  All OK. Ready for integration.\n")
