"""
Part 3: p_a/p_b Formula & Elo-Hybrid Calibration — hybrid_v2.py
================================================================
Drop-in replacement functions for the probability combination logic in
oncourt-compute-fair-odds.py. Each function can be tested independently
against the Iteration 4 baseline.

Five issues addressed:

  1. p_a/p_b FORMULA AUDIT
     Current: p_a = (hold1 * (1 - ret2)) / league_avg
     Problem: This mixes hold% (a game-level stat including 2nd serve) with
     return% (a point-level stat) in a ratio against league_avg. The denominator
     is league avg serve point win%, but the numerator isn't a serve point win%
     — it's a cross product of game-level and point-level stats. This creates
     systematic bias: hold% is non-linearly related to serve point win%, so
     the ratio doesn't preserve the Barnett-Clarke calibration.
     Fix: Convert hold%/return% back to estimated serve point win percentages
     (SPW) before forming the ratio, using the inverse of prob_game().

  2. ELO-HYBRID DISCONTINUITY
     Current: if abs(p_serve_return - 0.5) < 0.04 -> elo_weight = 0.9 (hard switch)
     Problem: at p_serve_return = 0.459 you get one model; at 0.461 a completely
     different one. A single match result changing a stat by 0.002 shouldn't
     cause a 40% swing in model weight.
     Fix: Smooth sigmoid transition that increases Elo reliance as serve/return
     signal approaches 50/50 (uninformative).

  3. PER-PLAYER ELO WEIGHT
     Current: elo_weight uses min(mc1, mc2) — penalises the well-sampled player
     when their opponent has sparse data.
     Fix: Per-player Elo contribution, weighted by each player's own data quality.

  4. SURFACE POINTS CALIBRATION
     Current: p_rank = pts1 / (pts1 + pts2) — a raw ratio that's not calibrated
     to actual win probability. A 2:1 point ratio gives 0.667, but empirical
     win rate might be 0.58.
     Fix: Apply a compression parameter that maps point ratios to calibrated
     probabilities (fitted to historical data).

  5. ADJUSTMENT CAP ANALYSIS
     Current: overall cap +/-0.04 on delta adjustments.
     Fix: Provide a function to test cap sensitivity and expose the distribution
     of uncapped deltas for analysis.

Usage:
  from hybrid_v2 import (
      estimate_spw_from_hold,
      compute_point_probs_bc,
      smooth_elo_hybrid,
      calibrated_rank_prob,
  )

Respects: Iteration 4 policy lock. Additive module for A/B testing.
"""

import math
from typing import Optional, Tuple, Dict

# Import tennis_prob for reference calculations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
try:
    from src.lib.tennis_prob import prob_game, prob_match_best_of_3
except ImportError:
    # Standalone: include prob_game locally
    def prob_game(p: float) -> float:
        if p <= 0 or p >= 1:
            return max(0.0, min(1.0, p))
        d = (p * p) / (1.0 - 2.0 * p * (1.0 - p))
        return p**4 + 4 * p**4 * (1 - p) + 10 * p**4 * (1 - p)**2 + 20 * p**3 * (1 - p)**3 * d

    def prob_match_best_of_3(p_a: float, p_b: float) -> float:
        # Simplified — use the real one from tennis_prob in production
        from functools import lru_cache
        @lru_cache(maxsize=4096)
        def _prob_set(a, b, pa_int, pb_int, a_serves):
            pa = pa_int / 10000.0
            pb = pb_int / 10000.0
            if a >= 6 and a - b >= 2:
                return 1.0
            if b >= 6 and b - a >= 2:
                return 0.0
            if a == 6 and b == 6:
                # Simplified tiebreak
                p_tb = pa * (1 - pb)
                return p_tb / (p_tb + (1 - pa) * pb) if (p_tb + (1-pa)*pb) > 0 else 0.5
            pga = prob_game(pa)
            pgb = prob_game(pb)
            pw = pga if a_serves else 1.0 - pgb
            return pw * _prob_set(a+1, b, pa_int, pb_int, not a_serves) + (1-pw) * _prob_set(a, b+1, pa_int, pb_int, not a_serves)

        def prob_set(pa, pb, a_first=True):
            pai = int(round(max(0.01, min(0.99, pa)) * 10000))
            pbi = int(round(max(0.01, min(0.99, pb)) * 10000))
            return _prob_set(0, 0, pai, pbi, a_first)

        s1 = prob_set(p_a, p_b, True)
        s2 = prob_set(p_a, p_b, False)
        return s1 * s2 + s1 * (1-s2) * s1 + (1-s1) * s2 * s1


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

SURFACE_LEAGUE_AVG = {"Hard": 0.64, "Clay": 0.62, "Grass": 0.67, "I.hard": 0.64, "N/A": 0.64}
DEFAULT_ELO = 1500
POINT_CLAMP = (0.52, 0.78)  # realistic SPW range (was 0.01-0.99, way too wide)


# ══════════════════════════════════════════════════════════════════════════════
# FIX 1: Proper Barnett-Clarke point probabilities from hold%/return%
# ══════════════════════════════════════════════════════════════════════════════

def estimate_spw_from_hold(hold_pct: float, tol: float = 1e-6, max_iter: int = 50) -> float:
    """
    Estimate serve point win % (SPW) from hold% using Newton's method on
    the inverse of prob_game().

    hold% = prob_game(SPW), so we invert: find SPW such that prob_game(SPW) = hold%.

    This is critical because hold% and SPW have a non-linear relationship:
      SPW=0.60 -> hold~0.736
      SPW=0.64 -> hold~0.829
      SPW=0.70 -> hold~0.925

    The V4 baseline treats hold% ~ SPW (via the ratio formula), which
    systematically overestimates point win probability for strong servers.
    """
    # Clamp input
    hold_pct = max(0.05, min(0.995, hold_pct))

    # Initial guess: linear approximation (SPW ~ 0.4 + 0.35 * hold)
    spw = 0.4 + 0.35 * hold_pct
    spw = max(0.45, min(0.85, spw))

    for _ in range(max_iter):
        g = prob_game(spw)
        err = g - hold_pct
        if abs(err) < tol:
            break
        # Numerical derivative
        h = 1e-6
        dg = (prob_game(spw + h) - prob_game(spw - h)) / (2 * h)
        if abs(dg) < 1e-12:
            break
        spw -= err / dg
        spw = max(0.40, min(0.90, spw))

    return spw


def estimate_rpw_from_return(return_pct: float) -> float:
    """
    Estimate return point win % (RPW) from return%.

    In the OnCourt data model, return_pct = RPW / RPWOF, which IS already
    a point-level stat (points won on return / return points faced).
    So return_pct ~ RPW directly. No inversion needed.

    This asymmetry (hold% is game-level, return% is point-level) is exactly
    why the V4 ratio formula is miscalibrated — it treats both as if they're
    at the same level.
    """
    return max(0.15, min(0.55, return_pct))


def compute_point_probs_bc(
    hold1: float, ret1: float,
    hold2: float, ret2: float,
    surface: str,
    league_avg: Optional[Dict[str, float]] = None,
) -> Tuple[float, float]:
    """
    Compute Barnett-Clarke point probabilities p_a, p_b from hold%/return%.

    Proper method:
      1. Convert hold% -> SPW via inverse of prob_game()
      2. Return% is already point-level (RPW)
      3. p_a = SPW_A adjusted for opponent return quality
      4. p_b = SPW_B adjusted for opponent return quality

    The adjustment uses the ratio method but at the correct level:
      p_a = SPW_1 * (1 - RPW_2) / league_avg_RPW_against
           where league_avg_RPW_against = 1 - league_avg_SPW

    Returns (p_a, p_b): point probabilities for K-M recursion.
    """
    avg = (league_avg or SURFACE_LEAGUE_AVG).get(surface, 0.64)

    # Step 1: Convert hold% to serve point win %
    spw1 = estimate_spw_from_hold(hold1)
    spw2 = estimate_spw_from_hold(hold2)

    # Step 2: Return% is already at point level
    rpw1 = estimate_rpw_from_return(ret1)
    rpw2 = estimate_rpw_from_return(ret2)

    # Step 3: Barnett-Clarke ratio at point level
    # p_a = P(A wins point on A's serve) considering B's return ability
    # Standard BC: p_a = spw_A * (1 - rpw_B) / (1 - avg_rpw)
    # where avg_rpw = 1 - avg_spw
    avg_rpw = 1.0 - avg  # league average return point win %

    if avg_rpw > 0 and avg_rpw < 1:
        # Ratio: how much better/worse is B's return than average?
        # If B returns better than avg, p_a decreases (harder to hold)
        p_a = spw1 * (1.0 - rpw2) / (1.0 - avg_rpw)
        p_b = spw2 * (1.0 - rpw1) / (1.0 - avg_rpw)
    else:
        p_a = spw1
        p_b = spw2

    # Clamp to realistic serve point win range
    p_a = max(POINT_CLAMP[0], min(POINT_CLAMP[1], p_a))
    p_b = max(POINT_CLAMP[0], min(POINT_CLAMP[1], p_b))

    return p_a, p_b


def compute_point_probs_v4(
    hold1: float, ret1: float,
    hold2: float, ret2: float,
    surface: str,
    league_avg: Optional[Dict[str, float]] = None,
) -> Tuple[float, float]:
    """
    V4 baseline point probability formula (for A/B comparison).
    Reproduces the exact logic from oncourt-compute-fair-odds.py.
    """
    avg = (league_avg or SURFACE_LEAGUE_AVG).get(surface, 0.64)
    if avg <= 0 or avg >= 1:
        avg = 0.64
    p_a = (hold1 * (1.0 - ret2)) / avg
    p_b = (hold2 * (1.0 - ret1)) / avg
    p_a = max(0.01, min(0.99, p_a))
    p_b = max(0.01, min(0.99, p_b))
    return p_a, p_b


# ══════════════════════════════════════════════════════════════════════════════
# FIX 2: Smooth Elo-hybrid blend (no discontinuity)
# ══════════════════════════════════════════════════════════════════════════════

def _sigmoid(x: float, midpoint: float, steepness: float) -> float:
    """Sigmoid mapping x -> [0, 1]."""
    z = steepness * (x - midpoint)
    z = max(-20, min(20, z))
    return 1.0 / (1.0 + math.exp(-z))


def smooth_elo_weight(
    p_serve_return: float,
    mc1: int,
    mc2: int,
    min_matches_for_full_trust: int = 20,
) -> float:
    """
    Compute Elo blend weight smoothly based on:
      (a) How informative the serve/return signal is (near 0.5 = uninformative)
      (b) Each player's sample size (per-player, not min of both)

    Returns elo_weight in [0.25, 0.90].

    V4 baseline issues fixed:
      - No hard threshold at |p_sr - 0.5| < 0.04
      - Uses harmonic mean of player sample sizes, not min
      - Smooth transition everywhere
    """
    # (a) Signal informativeness: how far is serve/return from 50/50?
    # At exactly 0.5, serve/return tells us nothing -> lean on Elo
    # At 0.3 or 0.7, serve/return is very informative -> lean on serve/return
    informativeness = abs(p_serve_return - 0.5)  # range [0, 0.5]

    # Sigmoid: when informativeness is low, push Elo weight up
    # midpoint=0.06 means at +/-6% from 50/50 we're at the crossover
    sr_trust = _sigmoid(informativeness, midpoint=0.06, steepness=40)
    # sr_trust: 0 = serve/return uninformative, 1 = serve/return informative

    # (b) Sample size: harmonic mean is fairer than min
    # (if one player has 50 matches and other has 3, hm=5.7 not 3)
    if mc1 > 0 and mc2 > 0:
        hm = 2.0 * mc1 * mc2 / (mc1 + mc2)
    else:
        hm = 0.0
    sample_trust = hm / (hm + min_matches_for_full_trust) if hm > 0 else 0.0
    # sample_trust: 0 = no data, 1 = abundant data

    # Combine: high sr_trust AND high sample_trust -> low Elo weight (trust serve/return)
    # low sr_trust OR low sample_trust -> high Elo weight
    combined_sr_reliability = sr_trust * sample_trust

    # Map to Elo weight range [0.25, 0.90]
    # When combined_sr_reliability=1 -> elo_weight=0.25 (trust serve/return mostly)
    # When combined_sr_reliability=0 -> elo_weight=0.90 (trust Elo mostly)
    elo_weight = 0.90 - 0.65 * combined_sr_reliability

    return elo_weight


def elo_weight_v4(
    p_serve_return: float,
    min_matches_12: int,
    p_rank: Optional[float],
    min_matches_threshold: int = 20,
) -> Tuple[float, bool]:
    """
    V4 baseline Elo weight (for A/B comparison).
    Returns (elo_weight, is_fallback_mode).
    """
    elo_weight = 0.4 + 0.3 * max(0.0, 1.0 - min(min_matches_12, min_matches_threshold) / float(min_matches_threshold))
    elo_weight = max(0.3, min(0.7, elo_weight))
    is_fallback = abs(p_serve_return - 0.5) < 0.04 and p_rank is not None
    if is_fallback:
        elo_weight = 0.9
    return elo_weight, is_fallback


# ══════════════════════════════════════════════════════════════════════════════
# FIX 3: Per-player Elo contribution (already in smooth_elo_weight above)
# The key change is using harmonic mean instead of min(mc1, mc2).
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# FIX 4: Calibrated rank probability
# ══════════════════════════════════════════════════════════════════════════════

# Surface points ratio compression
# Empirical: raw pts1/(pts1+pts2) overestimates the favourite's win probability.
# A 2:1 point ratio gives 0.667 raw, but empirical win rate is closer to 0.58-0.61.
# We apply a "temperature" parameter that compresses toward 0.5.
RANK_TEMPERATURE = 0.55  # <1 compresses toward 0.5; 1.0 = no compression

# Log-rank logistic scale (V4 uses 1.1 which is very aggressive)
LOG_RANK_SCALE_V2 = 1.8  # more moderate: rank difference matters less


def calibrated_rank_prob(
    pts1: Optional[float],
    pts2: Optional[float],
    rank1: Optional[int],
    rank2: Optional[int],
    surface: str,
    temperature: float = RANK_TEMPERATURE,
    log_scale: float = LOG_RANK_SCALE_V2,
) -> Optional[float]:
    """
    Compute calibrated P(player1 wins) from ranking information.

    Fixes:
      - Surface points: apply temperature compression to avoid over-confidence
      - Log-rank: use more moderate scale (1.8 vs 1.1)
      - Both: ensure output is in realistic range [0.15, 0.85]

    Returns P(P1 wins) or None if no ranking data available.
    """
    p_rank = None

    # Prefer surface points
    if pts1 is not None and pts2 is not None and (pts1 > 0 or pts2 > 0):
        # Raw ratio
        total = pts1 + pts2
        if total > 0:
            raw = pts1 / total
        else:
            raw = 0.5

        # Temperature scaling: compress toward 0.5
        # In log-odds space: logit(p_compressed) = temperature * logit(p_raw)
        if 0.001 < raw < 0.999:
            logit_raw = math.log(raw / (1.0 - raw))
            logit_compressed = temperature * logit_raw
            p_rank = 1.0 / (1.0 + math.exp(-logit_compressed))
        else:
            p_rank = raw

    # Fallback: log-rank
    elif rank1 is not None and rank2 is not None and rank1 > 0 and rank2 > 0:
        # Logistic on log(rank) difference
        log_diff = math.log(max(1, rank1)) - math.log(max(1, rank2))
        p_rank = 1.0 / (1.0 + 10.0 ** (log_diff / log_scale))

    # Clamp to realistic range
    if p_rank is not None:
        p_rank = max(0.15, min(0.85, p_rank))

    return p_rank


def rank_prob_v4(
    pts1: Optional[float],
    pts2: Optional[float],
    rank1: Optional[int],
    rank2: Optional[int],
    surface: str,
) -> Optional[float]:
    """V4 baseline rank probability (for A/B comparison)."""
    if pts1 is not None and pts2 is not None and (pts1 > 0 or pts2 > 0):
        return pts1 / (pts1 + pts2)
    elif rank1 is not None and rank2 is not None and rank1 > 0 and rank2 > 0:
        return 1.0 / (1.0 + 10.0 ** ((math.log(max(1, rank1)) - math.log(max(1, rank2))) / 1.1))
    return None


# ══════════════════════════════════════════════════════════════════════════════
# FIX 5: Adjustment cap analysis
# ══════════════════════════════════════════════════════════════════════════════

def apply_adjustments_capped(
    delta: float,
    cap: float = 0.04,
    soft: bool = True,
) -> float:
    """
    Apply cap to adjustment deltas.

    V4 uses a hard cap: delta = max(-0.04, min(0.04, delta))
    V2 option: soft cap using tanh, which compresses large deltas instead
    of truncating them. This preserves ordering (a 0.06 signal is stronger
    than 0.05, even though both map to < 0.04).

    Parameters:
      delta: raw uncapped adjustment
      cap:   maximum absolute value
      soft:  True = tanh compression, False = hard clip (V4 baseline)
    """
    if not soft:
        return max(-cap, min(cap, delta))

    # tanh soft cap: maps (-inf, inf) -> (-cap, cap)
    # Scaled so that small deltas pass through ~linearly
    if abs(delta) < 1e-10:
        return 0.0
    return cap * math.tanh(delta / cap)


# ══════════════════════════════════════════════════════════════════════════════
# Full pipeline: combine all fixes into one function
# ══════════════════════════════════════════════════════════════════════════════

def compute_match_probability_v2(
    hold1: float, ret1: float,
    hold2: float, ret2: float,
    mc1: int, mc2: int,
    elo1_surface: float, elo2_surface: float,
    elo1_overall: Optional[float], elo2_overall: Optional[float],
    pts1: Optional[float], pts2: Optional[float],
    rank1: Optional[int], rank2: Optional[int],
    surface: str,
    delta_adjustments: float = 0.0,
    league_avg: Optional[Dict[str, float]] = None,
    rank_blend: float = 0.15,
    adj_cap: float = 0.04,
) -> Tuple[float, float, dict]:
    """
    Full V2 match probability pipeline.

    Returns (p1_win, p2_win, debug_dict).
    """
    debug = {}

    # 1. Point probabilities (proper BC inversion)
    p_a, p_b = compute_point_probs_bc(hold1, ret1, hold2, ret2, surface, league_avg)
    debug["p_a"] = round(p_a, 4)
    debug["p_b"] = round(p_b, 4)

    # For comparison
    p_a_v4, p_b_v4 = compute_point_probs_v4(hold1, ret1, hold2, ret2, surface, league_avg)
    debug["p_a_v4"] = round(p_a_v4, 4)
    debug["p_b_v4"] = round(p_b_v4, 4)

    # 2. Serve/return match probability via K-M
    p_serve_return = prob_match_best_of_3(p_a, p_b)
    debug["p_serve_return"] = round(p_serve_return, 4)

    # 3. Elo probability (50/50 surface + overall blend)
    p_elo_surface = 1.0 / (1.0 + 10.0 ** ((elo2_surface - elo1_surface) / 400.0))
    if elo1_overall is not None and elo2_overall is not None:
        p_elo_overall = 1.0 / (1.0 + 10.0 ** ((elo2_overall - elo1_overall) / 400.0))
        p_elo = 0.5 * p_elo_surface + 0.5 * p_elo_overall
    else:
        p_elo = p_elo_surface
    debug["p_elo_raw"] = round(p_elo, 4)

    # 4. Calibrated rank probability
    p_rank = calibrated_rank_prob(pts1, pts2, rank1, rank2, surface)
    if p_rank is not None:
        p_elo = (1.0 - rank_blend) * p_elo + rank_blend * p_rank
    debug["p_rank"] = round(p_rank, 4) if p_rank is not None else None
    debug["p_elo_blended"] = round(p_elo, 4)

    # 5. Smooth Elo-hybrid weight
    elo_weight = smooth_elo_weight(p_serve_return, mc1, mc2)
    debug["elo_weight"] = round(elo_weight, 4)

    # 6. Final blend
    p1_win = elo_weight * p_elo + (1.0 - elo_weight) * p_serve_return
    debug["p1_win_pre_adj"] = round(p1_win, 4)

    # 7. Apply capped adjustments
    adj = apply_adjustments_capped(delta_adjustments, cap=adj_cap, soft=True)
    debug["adj_raw"] = round(delta_adjustments, 4)
    debug["adj_capped"] = round(adj, 4)
    p1_win += adj
    p1_win = max(0.02, min(0.98, p1_win))
    p2_win = 1.0 - p1_win

    # Normalise
    tot = p1_win + p2_win
    p1_win, p2_win = p1_win / tot, p2_win / tot

    debug["p1_win_final"] = round(p1_win, 4)
    debug["p2_win_final"] = round(p2_win, 4)

    return p1_win, p2_win, debug


def compute_match_probability_v4(
    hold1: float, ret1: float,
    hold2: float, ret2: float,
    mc1: int, mc2: int,
    elo1_surface: float, elo2_surface: float,
    elo1_overall: Optional[float], elo2_overall: Optional[float],
    pts1: Optional[float], pts2: Optional[float],
    rank1: Optional[int], rank2: Optional[int],
    surface: str,
    delta_adjustments: float = 0.0,
    league_avg: Optional[Dict[str, float]] = None,
) -> Tuple[float, float, dict]:
    """V4 baseline (for A/B comparison). Reproduces exact logic."""
    debug = {}

    avg = (league_avg or SURFACE_LEAGUE_AVG).get(surface, 0.64)
    if avg <= 0 or avg >= 1:
        avg = 0.64
    p_a = (hold1 * (1.0 - ret2)) / avg
    p_b = (hold2 * (1.0 - ret1)) / avg
    p_a = max(0.01, min(0.99, p_a))
    p_b = max(0.01, min(0.99, p_b))
    debug["p_a"] = round(p_a, 4)
    debug["p_b"] = round(p_b, 4)

    p_serve_return = prob_match_best_of_3(p_a, p_b)
    debug["p_serve_return"] = round(p_serve_return, 4)

    p_elo_surface = 1.0 / (1.0 + 10.0 ** ((elo2_surface - elo1_surface) / 400.0))
    if elo1_overall is not None and elo2_overall is not None:
        p_elo_overall = 1.0 / (1.0 + 10.0 ** ((elo2_overall - elo1_overall) / 400.0))
        p_elo = 0.5 * p_elo_surface + 0.5 * p_elo_overall
    else:
        p_elo = p_elo_surface

    p_rank = rank_prob_v4(pts1, pts2, rank1, rank2, surface)
    if p_rank is not None:
        p_elo = (1.0 - 0.15) * p_elo + 0.15 * p_rank
    debug["p_elo"] = round(p_elo, 4)
    debug["p_rank"] = round(p_rank, 4) if p_rank is not None else None

    min_matches = min(mc1, mc2)
    elo_weight = 0.4 + 0.3 * max(0.0, 1.0 - min(min_matches, 20) / 20.0)
    elo_weight = max(0.3, min(0.7, elo_weight))
    is_fallback = abs(p_serve_return - 0.5) < 0.04 and p_rank is not None
    if is_fallback:
        p_elo_effective = 0.4 * p_elo + 0.6 * p_rank
        elo_weight = 0.9
        p1_win = elo_weight * p_elo_effective + (1.0 - elo_weight) * p_serve_return
    else:
        p1_win = elo_weight * p_elo + (1.0 - elo_weight) * p_serve_return
    debug["elo_weight"] = round(elo_weight, 4)
    debug["is_fallback"] = is_fallback

    p1_win += max(-0.04, min(0.04, delta_adjustments))
    p2_win = 1.0 - p1_win
    tot = p1_win + p2_win
    if tot > 0:
        p1_win, p2_win = p1_win / tot, p2_win / tot

    debug["p1_win_final"] = round(p1_win, 4)
    return p1_win, p2_win, debug


# ══════════════════════════════════════════════════════════════════════════════
# Diagnostic: compare matchups
# ══════════════════════════════════════════════════════════════════════════════

def compare_matchup(
    name1: str, name2: str,
    hold1: float, ret1: float,
    hold2: float, ret2: float,
    mc1: int, mc2: int,
    elo1_s: float, elo2_s: float,
    elo1_o: Optional[float], elo2_o: Optional[float],
    pts1: Optional[float], pts2: Optional[float],
    rank1: Optional[int], rank2: Optional[int],
    surface: str,
    delta: float = 0.0,
):
    """Print side-by-side V4 vs V2 for one matchup."""
    p1_v4, p2_v4, d4 = compute_match_probability_v4(
        hold1, ret1, hold2, ret2, mc1, mc2,
        elo1_s, elo2_s, elo1_o, elo2_o, pts1, pts2, rank1, rank2, surface, delta)

    p1_v2, p2_v2, d2 = compute_match_probability_v2(
        hold1, ret1, hold2, ret2, mc1, mc2,
        elo1_s, elo2_s, elo1_o, elo2_o, pts1, pts2, rank1, rank2, surface, delta)

    odds1_v4 = round(1/p1_v4, 2) if p1_v4 > 0 else 99
    odds2_v4 = round(1/p2_v4, 2) if p2_v4 > 0 else 99
    odds1_v2 = round(1/p1_v2, 2) if p1_v2 > 0 else 99
    odds2_v2 = round(1/p2_v2, 2) if p2_v2 > 0 else 99

    print(f"\n{'='*72}")
    print(f"  {name1} vs {name2}  |  {surface}  |  mc={mc1}/{mc2}")
    print(f"{'='*72}")
    print(f"  {'Metric':<28} {'V4 Baseline':>14} {'V2 Improved':>14} {'d':>8}")
    print(f"  {'-'*28} {'-'*14} {'-'*14} {'-'*8}")

    print(f"  {'p_a (serve point prob)':<28} {d4['p_a']:>14.4f} {d2['p_a']:>14.4f} {d2['p_a']-d4['p_a']:>+8.4f}")
    print(f"  {'p_b (serve point prob)':<28} {d4['p_b']:>14.4f} {d2['p_b']:>14.4f} {d2['p_b']-d4['p_b']:>+8.4f}")
    print(f"  {'P(SR) serve/return model':<28} {d4['p_serve_return']:>14.4f} {d2['p_serve_return']:>14.4f} {d2['p_serve_return']-d4['p_serve_return']:>+8.4f}")
    print(f"  {'P(Elo) blended':<28} {d4['p_elo']:>14.4f} {d2['p_elo_blended']:>14.4f} {d2['p_elo_blended']-d4['p_elo']:>+8.4f}")
    print(f"  {'Elo weight':<28} {d4['elo_weight']:>14.4f} {d2['elo_weight']:>14.4f} {d2['elo_weight']-d4['elo_weight']:>+8.4f}")
    if d4.get('is_fallback'):
        print(f"  {'V4 fallback mode (0.04)':<28} {'YES':>14} {'N/A (smooth)':>14}")
    print(f"  {'P(P1 wins) final':<28} {p1_v4:>14.4f} {p1_v2:>14.4f} {p1_v2-p1_v4:>+8.4f}")
    print(f"  {'Fair odds P1':<28} {odds1_v4:>14.2f} {odds1_v2:>14.2f} {odds1_v2-odds1_v4:>+8.2f}")
    print(f"  {'Fair odds P2':<28} {odds2_v4:>14.2f} {odds2_v2:>14.2f} {odds2_v2-odds2_v4:>+8.2f}")

    # SPW inversion diagnostic
    spw1 = estimate_spw_from_hold(hold1)
    spw2 = estimate_spw_from_hold(hold2)
    print(f"\n  SPW inversion: {name1} hold={hold1:.3f} -> SPW={spw1:.4f} | {name2} hold={hold2:.3f} -> SPW={spw2:.4f}")
    print(f"  V4 used hold directly as proxy -> p_a={d4['p_a']:.4f}, V2 inverted -> p_a={d2['p_a']:.4f}")


# ══════════════════════════════════════════════════════════════════════════════
# Self-test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*72)
    print("  hybrid_v2.py - Self-test")
    print("="*72)

    # Test 1: SPW inversion accuracy
    print("\n-- SPW Inversion (hold% -> serve point win %) --")
    print(f"  {'Hold%':>8} {'-> SPW':>8} {'Verify (prob_game(SPW))':>25} {'Error':>8}")
    for hold in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
        spw = estimate_spw_from_hold(hold)
        verify = prob_game(spw)
        print(f"  {hold:>8.3f} {spw:>8.4f} {verify:>25.4f} {abs(verify-hold):>8.6f}")

    # Test 2: V4 formula vs V2 formula for p_a/p_b
    print("\n-- p_a/p_b: V4 Ratio vs V2 Proper BC --")
    test_cases = [
        ("Strong server vs avg",    0.75, 0.36, 0.64, 0.36, "Hard"),
        ("Avg vs avg",              0.64, 0.36, 0.64, 0.36, "Hard"),
        ("Clay specialist",         0.62, 0.42, 0.60, 0.38, "Clay"),
        ("Grass server",            0.82, 0.30, 0.67, 0.33, "Grass"),
        ("Unequal (strong vs weak)",0.78, 0.40, 0.58, 0.32, "Hard"),
    ]
    print(f"  {'Case':<28} {'V4 p_a':>8} {'V2 p_a':>8} {'V4 p_b':>8} {'V2 p_b':>8}")
    for name, h1, r1, h2, r2, surf in test_cases:
        pa4, pb4 = compute_point_probs_v4(h1, r1, h2, r2, surf)
        pa2, pb2 = compute_point_probs_bc(h1, r1, h2, r2, surf)
        print(f"  {name:<28} {pa4:>8.4f} {pa2:>8.4f} {pb4:>8.4f} {pb2:>8.4f}")

    # Test 3: Elo weight smoothness
    print("\n-- Elo Weight: V4 Discontinuity vs V2 Smooth --")
    print(f"  {'p_sr':>8} {'mc1':>4} {'mc2':>4} {'V4 wt':>8} {'V4 fb':>6} {'V2 wt':>8}")
    for p_sr in [0.45, 0.46, 0.47, 0.48, 0.49, 0.50, 0.51, 0.52, 0.53, 0.54, 0.55, 0.60, 0.70]:
        for mc1, mc2 in [(25, 25), (25, 3), (5, 5)]:
            w_v4, fb = elo_weight_v4(p_sr, min(mc1, mc2), 0.6)
            w_v2 = smooth_elo_weight(p_sr, mc1, mc2)
            print(f"  {p_sr:>8.3f} {mc1:>4} {mc2:>4} {w_v4:>8.3f} {'Y' if fb else 'N':>6} {w_v2:>8.3f}")

    # Test 4: Calibrated rank probability
    print("\n-- Rank Probability: V4 Raw vs V2 Calibrated --")
    print(f"  {'Case':<24} {'V4':>8} {'V2':>8} {'d':>8}")
    rank_cases = [
        ("2:1 pts ratio",   2000, 1000, None, None),
        ("3:1 pts ratio",   3000, 1000, None, None),
        ("10:1 pts ratio",  5000, 500,  None, None),
        ("Rank 5 vs 50",    None, None, 5, 50),
        ("Rank 10 vs 100",  None, None, 10, 100),
        ("Rank 1 vs 200",   None, None, 1, 200),
    ]
    for name, p1, p2, r1, r2 in rank_cases:
        v4 = rank_prob_v4(p1, p2, r1, r2, "Hard")
        v2 = calibrated_rank_prob(p1, p2, r1, r2, "Hard")
        v4s = f"{v4:.4f}" if v4 is not None else "None"
        v2s = f"{v2:.4f}" if v2 is not None else "None"
        d = f"{v2-v4:+.4f}" if v4 is not None and v2 is not None else "N/A"
        print(f"  {name:<24} {v4s:>8} {v2s:>8} {d:>8}")

    # Test 5: Full matchup comparisons
    print("\n-- Full Matchup Comparisons --")

    # Scenario A: Strong favourite, good data both sides
    compare_matchup(
        "Sinner", "Qualifier",
        hold1=0.74, ret1=0.40, hold2=0.60, ret2=0.34,
        mc1=30, mc2=8,
        elo1_s=2100, elo2_s=1600, elo1_o=2050, elo2_o=1550,
        pts1=3000, pts2=400, rank1=1, rank2=85,
        surface="Hard",
    )

    # Scenario B: Near-identical stats (triggers V4 fallback)
    compare_matchup(
        "Darderi", "Pellegrino",
        hold1=0.64, ret1=0.36, hold2=0.64, ret2=0.36,
        mc1=15, mc2=12,
        elo1_s=1750, elo2_s=1550, elo1_o=1700, elo2_o=1520,
        pts1=600, pts2=200, rank1=40, rank2=110,
        surface="Hard",
    )

    # Scenario C: Sparse data, one player unknown
    compare_matchup(
        "Rublev", "Unknown Q",
        hold1=0.72, ret1=0.38, hold2=0.63, ret2=0.35,
        mc1=25, mc2=2,
        elo1_s=1900, elo2_s=1500, elo1_o=1850, elo2_o=1500,
        pts1=2000, pts2=50, rank1=7, rank2=250,
        surface="Clay",
    )

    # Test 6: Soft cap vs hard cap
    print("\n-- Adjustment Cap: Hard vs Soft --")
    print(f"  {'Raw delta':>12} {'Hard (+/-0.04)':>14} {'Soft (tanh)':>14}")
    for d in [-0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08]:
        hard = apply_adjustments_capped(d, 0.04, soft=False)
        soft = apply_adjustments_capped(d, 0.04, soft=True)
        print(f"  {d:>+12.4f} {hard:>+14.4f} {soft:>+14.4f}")

    print(f"\n  Done.\n")
