"""
Matchup-Aware Point Probabilities — matchup_model.py
=====================================================
Computes p_a / p_b (serve point win probabilities) for K-M recursion
using DECOMPOSED serve/return stats instead of blunt hold%/return%.

This is the core of the Path B edge: two players with identical hold%
can have completely different point probabilities against specific
opponents, because their serve profiles interact differently.

Architecture:
  p_a = P(Player A wins a point on A's serve, given B is returning)

  Decomposed:
    p_a = first_serve_pct_A * first_serve_win_rate_A_vs_B_return
        + (1 - first_serve_pct_A) * (1 - df_rate_A) * second_serve_win_rate_A_vs_B_return
        + (1 - first_serve_pct_A) * df_rate_A * 0  (DF = point lost)

  Where:
    first_serve_win_rate_A_vs_B = adjusted for B's return quality vs first serves
    second_serve_win_rate_A_vs_B = adjusted for B's return quality vs second serves

  The adjustment uses the ratio method at the decomposed level:
    If B returns first serves better than average → A's first serve win rate drops
    If B returns second serves worse than average → A's second serve win rate rises

Usage:
  from matchup_model import compute_matchup_point_probs, MatchupStats

  stats_a = MatchupStats.from_db_row(player_surface_stats_v2_row_a)
  stats_b = MatchupStats.from_db_row(player_surface_stats_v2_row_b)
  p_a, p_b, debug = compute_matchup_point_probs(stats_a, stats_b, surface)

  # Feed into existing K-M recursion
  p_match = prob_match_best_of_3(p_a, p_b)

Integration:
  In oncourt-compute-fair-odds.py, replace the p_a/p_b calculation block
  with a call to compute_matchup_point_probs(). Everything downstream
  (K-M recursion, Elo hybrid, adjustments) stays the same.
"""

import math
from typing import Optional, Tuple, Dict, NamedTuple


# ══════════════════════════════════════════════════════════════════════════════
# Player stats container
# ══════════════════════════════════════════════════════════════════════════════

class MatchupStats:
    """Container for a player's decomposed serve/return profile on a surface."""

    def __init__(
        self,
        # Serve
        first_serve_pct: Optional[float] = None,       # 1st serves in / attempts
        first_serve_win_pct: Optional[float] = None,    # points won on 1st serve / 1st in
        second_serve_win_pct: Optional[float] = None,   # points won on 2nd serve / 2nd in
        ace_rate: Optional[float] = None,               # aces / total serve pts
        df_rate: Optional[float] = None,                # DFs / total serve pts

        # Return (aggregate)
        return_pct: Optional[float] = None,             # return points won / faced

        # Return (decomposed — NEW)
        ret_vs_first_win_pct: Optional[float] = None,   # return pts won vs opponent 1st serve / faced
        ret_vs_second_win_pct: Optional[float] = None,  # return pts won vs opponent 2nd serve / faced

        # Pressure
        bp_save_rate: Optional[float] = None,           # BP saved / BP faced
        bp_convert_rate: Optional[float] = None,        # BP won / BP opp faced

        # Legacy (for fallback)
        hold_pct: Optional[float] = None,
        match_count: int = 0,
        service_pts: int = 0,
    ):
        self.first_serve_pct = first_serve_pct
        self.first_serve_win_pct = first_serve_win_pct
        self.second_serve_win_pct = second_serve_win_pct
        self.ace_rate = ace_rate
        self.df_rate = df_rate
        self.return_pct = return_pct
        self.ret_vs_first_win_pct = ret_vs_first_win_pct
        self.ret_vs_second_win_pct = ret_vs_second_win_pct
        self.bp_save_rate = bp_save_rate
        self.bp_convert_rate = bp_convert_rate
        self.hold_pct = hold_pct
        self.match_count = match_count
        self.service_pts = service_pts

    @property
    def has_decomposed(self) -> bool:
        """Does this player have decomposed serve stats?"""
        # Guardrail: many rows can carry sentinel/invalid values (e.g. 0.0 / 1.0).
        # Only treat decomposed serve as usable when values are in realistic ATP ranges.
        if self.match_count < MIN_MATCHES_DECOMPOSED or self.service_pts < MIN_SERVICE_PTS_DECOMPOSED:
            return False
        if (
            self.first_serve_pct is None
            or self.first_serve_win_pct is None
            or self.second_serve_win_pct is None
        ):
            return False
        return (
            0.40 <= self.first_serve_pct <= 0.80
            and 0.45 <= self.first_serve_win_pct <= 0.90
            and 0.30 <= self.second_serve_win_pct <= 0.80
        )

    @property
    def has_decomposed_return(self) -> bool:
        """Does this player have decomposed return stats?"""
        if self.match_count < MIN_MATCHES_DECOMPOSED:
            return False
        if self.ret_vs_first_win_pct is None or self.ret_vs_second_win_pct is None:
            return False
        return (
            0.10 <= self.ret_vs_first_win_pct <= 0.55
            and 0.20 <= self.ret_vs_second_win_pct <= 0.80
        )

    @classmethod
    def from_db_row(cls, row: dict) -> "MatchupStats":
        """Create from a player_surface_stats_v2 row (dict)."""
        def _f(v):
            if v is None or v == "":
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        def _prob_or_none(v):
            x = _f(v)
            # Treat hard boundary values as missing/sentinel (common ETL artefacts).
            if x is None or x <= 0.0 or x >= 1.0:
                return None
            return x

        return cls(
            first_serve_pct=_prob_or_none(row.get("first_serve_pct")),
            first_serve_win_pct=_prob_or_none(row.get("first_serve_win_pct")),
            second_serve_win_pct=_prob_or_none(row.get("second_serve_win_pct")),
            ace_rate=_prob_or_none(row.get("ace_rate")),
            df_rate=_prob_or_none(row.get("df_rate")),
            return_pct=_prob_or_none(row.get("return_pct")),
            ret_vs_first_win_pct=_prob_or_none(row.get("ret_vs_first_win_pct")),
            ret_vs_second_win_pct=_prob_or_none(row.get("ret_vs_second_win_pct")),
            bp_save_rate=_prob_or_none(row.get("bp_save_rate")),
            bp_convert_rate=_prob_or_none(row.get("bp_convert_rate")),
            hold_pct=_prob_or_none(row.get("hold_pct")),
            match_count=int(row.get("match_count") or 0),
            service_pts=int(row.get("service_pts") or 0),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Surface averages (for ratio adjustments)
# ══════════════════════════════════════════════════════════════════════════════

# These should ideally come from surface_league_averages in DB.
# Hardcoded defaults from ATP tour averages (approximate).

SURFACE_AVG = {
    "Hard": {
        "first_serve_pct": 0.61,
        "first_serve_win_pct": 0.73,
        "second_serve_win_pct": 0.52,
        "return_pct": 0.36,
        "ret_vs_first_win_pct": 0.27,    # 1 - 0.73 = 0.27
        "ret_vs_second_win_pct": 0.48,   # 1 - 0.52 = 0.48
        "ace_rate": 0.08,
        "df_rate": 0.035,
        "bp_save_rate": 0.63,
        "bp_convert_rate": 0.40,
        "spw": 0.64,   # overall serve point win
    },
    "Clay": {
        "first_serve_pct": 0.60,
        "first_serve_win_pct": 0.69,
        "second_serve_win_pct": 0.51,
        "return_pct": 0.38,
        "ret_vs_first_win_pct": 0.31,
        "ret_vs_second_win_pct": 0.49,
        "ace_rate": 0.05,
        "df_rate": 0.035,
        "bp_save_rate": 0.60,
        "bp_convert_rate": 0.42,
        "spw": 0.62,
    },
    "Grass": {
        "first_serve_pct": 0.63,
        "first_serve_win_pct": 0.77,
        "second_serve_win_pct": 0.54,
        "return_pct": 0.33,
        "ret_vs_first_win_pct": 0.23,
        "ret_vs_second_win_pct": 0.46,
        "ace_rate": 0.12,
        "df_rate": 0.03,
        "bp_save_rate": 0.66,
        "bp_convert_rate": 0.37,
        "spw": 0.67,
    },
    "I.hard": {
        "first_serve_pct": 0.61,
        "first_serve_win_pct": 0.74,
        "second_serve_win_pct": 0.52,
        "return_pct": 0.36,
        "ret_vs_first_win_pct": 0.26,
        "ret_vs_second_win_pct": 0.48,
        "ace_rate": 0.09,
        "df_rate": 0.035,
        "bp_save_rate": 0.64,
        "bp_convert_rate": 0.39,
        "spw": 0.64,
    },
}

DEFAULT_SURFACE_AVG = SURFACE_AVG["Hard"]


def _get_avg(surface: str, stat: str) -> float:
    return SURFACE_AVG.get(surface, DEFAULT_SURFACE_AVG).get(stat, 0.5)


# ══════════════════════════════════════════════════════════════════════════════
# Matchup-aware point probability
# ══════════════════════════════════════════════════════════════════════════════

# How much to weight the pressure adjustment (BP save/convert)
PRESSURE_WEIGHT = 0.03
PRESSURE_CAP = 0.015

# Point probability clamp (realistic range for ATP serve points)
POINT_CLAMP = (0.52, 0.78)

# Reliability gates for decomposed profiles.
# Non-hard surfaces are especially sparse/noisy; require basic sample support
# before trusting decomposed serve/return.
MIN_MATCHES_DECOMPOSED = 8
MIN_SERVICE_PTS_DECOMPOSED = 250


def _prob_game(p: float) -> float:
    """Game hold probability from point win probability."""
    if p <= 0 or p >= 1:
        return max(0.0, min(1.0, p))
    d = (p * p) / (1.0 - 2.0 * p * (1.0 - p))
    return p**4 + 4 * p**4 * (1 - p) + 10 * p**4 * (1 - p)**2 + 20 * p**3 * (1 - p)**3 * d


def _estimate_spw_from_hold(hold_pct: float, tol: float = 1e-6, max_iter: int = 50) -> float:
    """
    Invert hold% -> serve point win% so fallback math stays on point-level units.
    """
    hold_pct = max(0.05, min(0.995, hold_pct))
    spw = 0.4 + 0.35 * hold_pct
    spw = max(0.45, min(0.85, spw))
    for _ in range(max_iter):
        g = _prob_game(spw)
        err = g - hold_pct
        if abs(err) < tol:
            break
        h = 1e-6
        dg = (_prob_game(spw + h) - _prob_game(spw - h)) / (2 * h)
        if abs(dg) < 1e-12:
            break
        spw -= err / dg
        spw = max(0.40, min(0.90, spw))
    return spw


def _ratio_adjust(player_stat: float, opponent_stat: float,
                  avg_player: float, avg_opponent: float) -> float:
    """
    Ratio-based adjustment: how much better/worse is the opponent
    than average at countering this specific aspect of the serve?

    If opponent returns first serves better than average:
      → player's first_serve_win_pct decreases
    If opponent returns first serves worse than average:
      → player's first_serve_win_pct increases

    Returns: adjusted player_stat.
    """
    if avg_opponent <= 0 or avg_opponent >= 1:
        return player_stat

    # Opponent quality ratio: >1 means opponent is above average
    opp_ratio = opponent_stat / avg_opponent if avg_opponent > 0 else 1.0

    # Player's stat adjusted: if opponent is 10% better than avg at returning,
    # player's win rate on that shot type drops proportionally
    # We use the complement because higher return = lower server win rate
    adjusted = player_stat * (avg_opponent / opponent_stat) if opponent_stat > 0 else player_stat

    # Soft clamp to avoid extreme adjustments
    return max(player_stat * 0.75, min(player_stat * 1.25, adjusted))


def compute_matchup_point_probs(
    server: MatchupStats,
    returner: MatchupStats,
    surface: str,
    debug: bool = False,
) -> Tuple[float, Optional[dict]]:
    """
    Compute P(server wins point on server's serve) accounting for
    the specific matchup between server's serve profile and returner's
    return abilities.

    This replaces the V4 formula: p_a = (hold1 * (1-ret2)) / league_avg

    Returns: (p_serve_point_win, debug_dict or None)
    """
    avg = SURFACE_AVG.get(surface, DEFAULT_SURFACE_AVG)
    dbg = {} if debug else None

    # ── Does the server have decomposed stats? ──
    if not server.has_decomposed:
        # Fallback: keep units consistent (point-level only).
        # hold_pct is game-level, so invert to SPW first.
        if server.hold_pct is not None:
            spw = _estimate_spw_from_hold(server.hold_pct)
            if returner.return_pct is not None:
                rpw_opponent = max(0.15, min(0.55, returner.return_pct))
                rpw_avg = avg.get("return_pct", 0.36)
                opp_factor = (1.0 - rpw_opponent) / (1.0 - rpw_avg) if rpw_avg < 1 else 1.0
                p = spw * opp_factor
                method = "fallback_spw_ratio"
            else:
                p = spw
                method = "fallback_spw_only"
            p = max(POINT_CLAMP[0], min(POINT_CLAMP[1], p))
            if dbg is not None:
                dbg["method"] = method
                dbg["p_serve_win"] = round(p, 4)
            return p, dbg
        # No data at all — return surface average
        p = avg.get("spw", 0.64)
        if dbg is not None:
            dbg["method"] = "surface_default"
        return p, dbg

    # ── Decomposed calculation ──
    fs_pct = server.first_serve_pct   # P(first serve in)
    fs_win = server.first_serve_win_pct  # P(win | first serve in)
    ss_win = server.second_serve_win_pct  # P(win | second serve, in play)
    df_rate = server.df_rate or 0.035  # P(double fault on second serve attempt)
    ace_rate = server.ace_rate or avg.get("ace_rate", 0.08)

    ret_pct = returner.return_pct     # Returner's overall return point win rate

    # ── Adjust for opponent quality ──
    # Two paths: decomposed return (precise) or aggregate return (fallback).
    #
    # DECOMPOSED (when returner has ret_vs_first_win_pct and ret_vs_second_win_pct):
    #   Use the ratio approach separately for first and second serve:
    #   server's adjusted_fs_win = fs_win * (1 - returner.ret_vs_first) / (1 - avg_ret_vs_first)
    #   → if returner wins more 1st-serve return pts than average, server's fs_win drops
    #   Same logic for second serve.
    #
    # AGGREGATE (fallback): use overall return_pct with power exponents (original method).

    avg_return = avg.get("return_pct", 0.36)
    avg_ret_vs_first = avg.get("ret_vs_first_win_pct", 0.27)   # ~27% on ATP hard
    avg_ret_vs_second = avg.get("ret_vs_second_win_pct", 0.50)  # ~50% on ATP hard

    if returner.has_decomposed_return:
        # PRECISE: adjust first serve and second serve independently
        # using the returner's actual decomposed return performance
        rvf = returner.ret_vs_first_win_pct
        rvs = returner.ret_vs_second_win_pct

        # Ratio: how much better/worse is this returner vs avg at returning each serve type?
        # If returner wins 32% of 1st-serve return pts vs avg 27% → difficulty = 32/27 = 1.19
        # Server's first_serve_win_pct drops proportionally
        if avg_ret_vs_first > 0 and rvf is not None:
            first_difficulty = rvf / avg_ret_vs_first
            fs_win_adj = fs_win / (first_difficulty ** 0.7)
        else:
            fs_win_adj = fs_win

        if avg_ret_vs_second > 0 and rvs is not None:
            second_difficulty = rvs / avg_ret_vs_second
            ss_win_adj = ss_win / (second_difficulty ** 0.8)
        else:
            ss_win_adj = ss_win

    elif ret_pct is not None and avg_return > 0:
        # FALLBACK: use aggregate return_pct with power exponents
        return_difficulty = ret_pct / avg_return
        fs_win_adj = fs_win / (return_difficulty ** 0.6)
        ss_win_adj = ss_win / (return_difficulty ** 0.9)
    else:
        fs_win_adj = fs_win
        ss_win_adj = ss_win

    # Clamp adjusted win rates to realistic bounds
    fs_win_adj = max(0.40, min(0.90, fs_win_adj))
    ss_win_adj = max(0.25, min(0.70, ss_win_adj))

    # ── Compute serve point win probability ──
    # P(win point on serve) =
    #   P(1st in) * P(win | 1st in, adjusted) +
    #   P(1st out) * P(2nd in) * P(win | 2nd in, adjusted) +
    #   P(1st out) * P(DF) * 0
    #
    # Where P(2nd in) = 1 - P(DF | 1st out)
    # Approximate: df_rate is per total serve point, not per second serve.
    # P(DF | 2nd serve needed) ≈ df_rate / (1 - fs_pct)  but capped

    p_first_out = 1.0 - fs_pct
    if p_first_out > 0:
        p_df_given_second = min(0.30, df_rate / p_first_out)  # cap at 30%
    else:
        p_df_given_second = df_rate

    p_second_in = 1.0 - p_df_given_second

    p_serve_win = (
        fs_pct * fs_win_adj +                          # first serve in → adjusted win rate
        p_first_out * p_second_in * ss_win_adj +       # second serve in → adjusted win rate
        p_first_out * p_df_given_second * 0.0          # double fault → lose point
    )

    # ── Pressure adjustment (small) ──
    # Players who save more break points than expected hold slightly better
    # in critical moments. This is a known underpriced factor.
    bp_adj = 0.0
    if server.bp_save_rate is not None:
        avg_bps = avg.get("bp_save_rate", 0.63)
        bp_adj += (server.bp_save_rate - avg_bps) * PRESSURE_WEIGHT
    if returner.bp_convert_rate is not None:
        avg_bpc = avg.get("bp_convert_rate", 0.40)
        bp_adj -= (returner.bp_convert_rate - avg_bpc) * PRESSURE_WEIGHT
    bp_adj = max(-PRESSURE_CAP, min(PRESSURE_CAP, bp_adj))
    p_serve_win += bp_adj

    # ── Final clamp ──
    p_serve_win = max(POINT_CLAMP[0], min(POINT_CLAMP[1], p_serve_win))

    if dbg is not None:
        dbg["method"] = "decomposed"
        dbg["return_method"] = "decomposed_return" if returner.has_decomposed_return else "aggregate_return"
        dbg["fs_pct"] = round(fs_pct, 4)
        dbg["fs_win_raw"] = round(fs_win, 4)
        dbg["fs_win_adj"] = round(fs_win_adj, 4)
        dbg["ss_win_raw"] = round(ss_win, 4)
        dbg["ss_win_adj"] = round(ss_win_adj, 4)
        dbg["df_rate"] = round(df_rate, 4)
        if returner.has_decomposed_return:
            dbg["ret_vs_first"] = round(returner.ret_vs_first_win_pct, 3) if returner.ret_vs_first_win_pct else None
            dbg["ret_vs_second"] = round(returner.ret_vs_second_win_pct, 3) if returner.ret_vs_second_win_pct else None
        dbg["return_difficulty"] = round(ret_pct / avg_return, 3) if ret_pct and avg_return else None
        dbg["bp_adj"] = round(bp_adj, 4)
        dbg["p_serve_win"] = round(p_serve_win, 4)

    return p_serve_win, dbg


def compute_match_point_probs(
    player_a: MatchupStats,
    player_b: MatchupStats,
    surface: str,
    debug: bool = False,
) -> Tuple[float, float, dict]:
    """
    Compute both p_a and p_b for a match.

    p_a = P(A wins point when A serves) — uses A's serve vs B's return
    p_b = P(B wins point when B serves) — uses B's serve vs A's return

    Returns (p_a, p_b, debug_dict).
    """
    p_a, dbg_a = compute_matchup_point_probs(player_a, player_b, surface, debug)
    p_b, dbg_b = compute_matchup_point_probs(player_b, player_a, surface, debug)

    full_debug = {}
    if debug:
        full_debug["p_a"] = dbg_a
        full_debug["p_b"] = dbg_b

    return p_a, p_b, full_debug


# ══════════════════════════════════════════════════════════════════════════════
# Self-test and comparison
# ══════════════════════════════════════════════════════════════════════════════

def _compare_matchup(name_a, name_b, stats_a, stats_b, surface):
    """Print detailed matchup comparison."""
    p_a, p_b, dbg = compute_match_point_probs(stats_a, stats_b, surface, debug=True)

    print(f"\n{'='*64}")
    print(f"  {name_a} vs {name_b}  |  {surface}")
    print(f"{'='*64}")
    print(f"  {name_a} serve profile:")
    print(f"    1st serve %:     {stats_a.first_serve_pct:.1%}" if stats_a.first_serve_pct else "    1st serve %: N/A")
    print(f"    1st serve win %: {stats_a.first_serve_win_pct:.1%}" if stats_a.first_serve_win_pct else "    1st serve win %: N/A")
    print(f"    2nd serve win %: {stats_a.second_serve_win_pct:.1%}" if stats_a.second_serve_win_pct else "    2nd serve win %: N/A")
    print(f"    Ace rate:        {stats_a.ace_rate:.1%}" if stats_a.ace_rate else "    Ace rate: N/A")
    print(f"    DF rate:         {stats_a.df_rate:.1%}" if stats_a.df_rate else "    DF rate: N/A")
    print(f"    BP save rate:    {stats_a.bp_save_rate:.1%}" if stats_a.bp_save_rate else "    BP save rate: N/A")
    print(f"  {name_b} return: {stats_b.return_pct:.1%}" if stats_b.return_pct else f"  {name_b} return: N/A")
    if stats_b.bp_convert_rate:
        print(f"  {name_b} BP convert: {stats_b.bp_convert_rate:.1%}")

    print(f"\n  Matchup p_a (A serves): {p_a:.4f}")
    if dbg.get("p_a"):
        d = dbg["p_a"]
        print(f"    Method: {d.get('method', '?')}")
        if d.get("return_difficulty"):
            print(f"    Return difficulty: {d['return_difficulty']:.3f} (>1 = harder)")
        if d.get("fs_win_adj"):
            print(f"    1st win adj: {d.get('fs_win_raw', 0):.4f} -> {d['fs_win_adj']:.4f}")
            print(f"    2nd win adj: {d.get('ss_win_raw', 0):.4f} -> {d['ss_win_adj']:.4f}")

    print(f"\n  Matchup p_b (B serves): {p_b:.4f}")
    if dbg.get("p_b"):
        d = dbg["p_b"]
        if d.get("return_difficulty"):
            print(f"    Return difficulty: {d['return_difficulty']:.3f}")

    # Compare to V4-style aggregate
    if stats_a.hold_pct and stats_b.return_pct:
        league_avg = _get_avg(surface, "spw")
        p_a_v4 = (stats_a.hold_pct * (1.0 - stats_b.return_pct)) / league_avg
        p_a_v4 = max(0.01, min(0.99, p_a_v4))
        print(f"\n  V4 comparison: p_a_v4 = {p_a_v4:.4f} (matchup: {p_a:.4f}, diff={p_a - p_a_v4:+.4f})")


if __name__ == "__main__":
    print("="*64)
    print("  matchup_model.py - Self-test")
    print("="*64)

    # ── Test 1: Two players with identical hold% but different profiles ──
    # Player A: ace machine, weak second serve
    ace_machine = MatchupStats(
        first_serve_pct=0.58, first_serve_win_pct=0.82,
        second_serve_win_pct=0.42, ace_rate=0.15, df_rate=0.04,
        return_pct=0.33, bp_save_rate=0.68, bp_convert_rate=0.35,
        hold_pct=0.65, match_count=30, service_pts=800,
    )

    # Player B: consistent grinder, no aces, strong second serve
    grinder = MatchupStats(
        first_serve_pct=0.65, first_serve_win_pct=0.70,
        second_serve_win_pct=0.56, ace_rate=0.03, df_rate=0.02,
        return_pct=0.40, bp_save_rate=0.60, bp_convert_rate=0.45,
        hold_pct=0.65, match_count=30, service_pts=800,
    )

    # Strong returner (punishes weak second serves)
    strong_returner = MatchupStats(
        first_serve_pct=0.62, first_serve_win_pct=0.74,
        second_serve_win_pct=0.50, ace_rate=0.07, df_rate=0.03,
        return_pct=0.42, bp_save_rate=0.62, bp_convert_rate=0.48,
        hold_pct=0.66, match_count=25, service_pts=700,
    )

    # Weak returner (lets servers dominate)
    weak_returner = MatchupStats(
        first_serve_pct=0.60, first_serve_win_pct=0.72,
        second_serve_win_pct=0.48, ace_rate=0.06, df_rate=0.04,
        return_pct=0.30, bp_save_rate=0.65, bp_convert_rate=0.32,
        hold_pct=0.63, match_count=20, service_pts=600,
    )

    print("\n-- Both players have 65% hold. V4 sees them as identical. --")
    print("-- The matchup model sees the difference. --")

    _compare_matchup("Ace Machine", "Strong Returner", ace_machine, strong_returner, "Hard")
    _compare_matchup("Grinder", "Strong Returner", grinder, strong_returner, "Hard")
    _compare_matchup("Ace Machine", "Weak Returner", ace_machine, weak_returner, "Hard")
    _compare_matchup("Grinder", "Weak Returner", grinder, weak_returner, "Hard")

    # -- Summary: did the model differentiate? --
    p_ace_vs_strong, _, _ = compute_match_point_probs(ace_machine, strong_returner, "Hard")
    p_grind_vs_strong, _, _ = compute_match_point_probs(grinder, strong_returner, "Hard")
    p_ace_vs_weak, _, _ = compute_match_point_probs(ace_machine, weak_returner, "Hard")
    p_grind_vs_weak, _, _ = compute_match_point_probs(grinder, weak_returner, "Hard")

    print(f"\n{'='*64}")
    print(f"  SUMMARY: Same hold% (65%), different matchup outcomes")
    print(f"{'='*64}")
    print(f"  {'Matchup':<35} {'p_a (serve)':>12}")
    print(f"  {'Ace Machine vs Strong Returner':<35} {p_ace_vs_strong:>12.4f}  (weak 2nd serve exposed)")
    print(f"  {'Grinder vs Strong Returner':<35} {p_grind_vs_strong:>12.4f}  (2nd serve holds up)")
    print(f"  {'Ace Machine vs Weak Returner':<35} {p_ace_vs_weak:>12.4f}  (aces dominate)")
    print(f"  {'Grinder vs Weak Returner':<35} {p_grind_vs_weak:>12.4f}  (consistent but less upside)")

    diff_vs_strong = abs(p_ace_vs_strong - p_grind_vs_strong)
    diff_vs_weak = abs(p_ace_vs_weak - p_grind_vs_weak)
    print(f"\n  V4 would give IDENTICAL p_a for all four matchups.")
    print(f"  Matchup model differentiates by {diff_vs_strong:.4f} vs strong returner")
    print(f"  and {diff_vs_weak:.4f} vs weak returner.")

    # -- Fallback test --
    print(f"\n-- Fallback: player without decomposed stats --")
    legacy_player = MatchupStats(hold_pct=0.68, return_pct=0.36, match_count=15)
    p_legacy, dbg_legacy = compute_matchup_point_probs(legacy_player, strong_returner, "Hard", debug=True)
    print(f"  p_a (fallback): {p_legacy:.4f}, method: {dbg_legacy.get('method')}")

    print(f"\n  Done.\n")
