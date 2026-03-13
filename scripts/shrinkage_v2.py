"""
Part 2: Improved Shrinkage & Priors — shrinkage_v2.py
=====================================================
Drop-in replacement functions for the shrinkage/blend logic in
oncourt-compute-fair-odds.py. Each function can be tested independently
against the Iteration 4 baseline.

Three improvements:
  1. Service-point-based shrinkage (not match_count)
     → uses actual information content, not just "how many matches"
  2. Cross-surface borrowing when surface data is sparse
     → a player with 0 Grass matches but 30 Hard matches gets individualized
       estimates instead of pure league average
  3. Smooth 12m/36m blend (logistic, not step-function)
     → eliminates discontinuities at 8/15/25 match thresholds

Usage in fair-odds compute:
  from shrinkage_v2 import shrink_hold_return, blend_12m_36m, cross_surface_estimate

Respects: Iteration 4 policy lock. This module is additive — import and
A/B test before replacing baseline logic. Any switch requires backtest
comparison and explicit approval per FAIR-ODDS-POLICY-LOCK.md.
"""

import math
from typing import Optional, Dict, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Surface correlation matrix (empirical, from Sackmann + OnCourt analysis)
# ──────────────────────────────────────────────────────────────────────────────
# Interpretation: SURFACE_CORRELATION[source][target] = how much a player's
# hold/return on 'source' surface predicts their hold/return on 'target'.
# Values are transfer weights (0 = no information, 1 = identical).
#
# Hard ↔ I.hard: very high (same ball bounce, just roof)
# Hard → Grass: moderate (fast surface similarity, but bounce differs)
# Clay → Hard: low (very different play styles rewarded)
# Clay → Grass: very low (opposite extremes)

SURFACE_CORRELATION: Dict[str, Dict[str, float]] = {
    "Hard": {"Hard": 1.0, "I.hard": 0.90, "Grass": 0.45, "Clay": 0.30},
    "I.hard": {"I.hard": 1.0, "Hard": 0.90, "Grass": 0.40, "Clay": 0.28},
    "Grass": {"Grass": 1.0, "Hard": 0.45, "I.hard": 0.40, "Clay": 0.15},
    "Clay": {"Clay": 1.0, "Hard": 0.30, "I.hard": 0.28, "Grass": 0.15},
}

# Fallback for unknown surfaces
DEFAULT_CORRELATION = 0.20

# ──────────────────────────────────────────────────────────────────────────────
# Surface averages (same as Iteration 4 defaults; override with DB values)
# ──────────────────────────────────────────────────────────────────────────────

SURFACE_AVG_HOLD = {"Hard": 0.640, "Clay": 0.620, "Grass": 0.670, "I.hard": 0.640, "N/A": 0.640}
SURFACE_AVG_RETURN = {"Hard": 0.360, "Clay": 0.380, "Grass": 0.330, "I.hard": 0.360, "N/A": 0.360}


# ──────────────────────────────────────────────────────────────────────────────
# 1. Service-point-based shrinkage
# ──────────────────────────────────────────────────────────────────────────────
#
# The Iteration 4 baseline uses:
#   alpha = match_count / (match_count + SHRINKAGE_N)    where SHRINKAGE_N=15
#
# Problem: a player with 10 three-setters (~400 service points) gets the same
# alpha as a player with 10 straight-set wins (~200 service points). The first
# has 2x the statistical information.
#
# Fix: shrink based on service_pts (denominator of hold_pct calculation).
# The prior "pseudo-count" is expressed in service points, not matches.
#
# Calibration: SHRINKAGE_PTS=300 means ~50% trust at 300 service points
# (roughly 15 average-length matches). This aligns with the old SHRINKAGE_N=15
# at the median but correctly handles outliers.

SHRINKAGE_PTS_DEFAULT = 300  # service points for 50% trust in raw hold/return
SHRINKAGE_PTS_RETURN = 350   # return stats are noisier, need more points


def shrink_hold_return(
    hold_raw: float,
    return_raw: float,
    service_pts: int,
    return_pts: int,
    surface: str,
    surface_avg_hold: Optional[Dict[str, float]] = None,
    surface_avg_return: Optional[Dict[str, float]] = None,
    shrinkage_pts_hold: int = SHRINKAGE_PTS_DEFAULT,
    shrinkage_pts_return: int = SHRINKAGE_PTS_RETURN,
) -> Tuple[float, float]:
    """
    Shrink raw hold/return toward surface average, weighted by service point count.

    Returns (shrunk_hold, shrunk_return).

    Parameters:
      hold_raw:      blended 12m/36m hold percentage
      return_raw:    blended 12m/36m return percentage
      service_pts:   total service points in the hold calculation window
      return_pts:    total return points in the return calculation window
      surface:       canonical surface name
      surface_avg_*: override surface averages (else uses module defaults)
      shrinkage_pts_*: pseudo-count for 50% trust (higher = more shrinkage)
    """
    avg_hold = (surface_avg_hold or SURFACE_AVG_HOLD).get(surface, 0.64)
    avg_ret = (surface_avg_return or SURFACE_AVG_RETURN).get(surface, 0.36)

    # Alpha based on service point count (not match count)
    alpha_hold = service_pts / (service_pts + shrinkage_pts_hold) if service_pts > 0 else 0.0
    alpha_ret = return_pts / (return_pts + shrinkage_pts_return) if return_pts > 0 else 0.0

    hold_shrunk = alpha_hold * hold_raw + (1.0 - alpha_hold) * avg_hold
    ret_shrunk = alpha_ret * return_raw + (1.0 - alpha_ret) * avg_ret

    return hold_shrunk, ret_shrunk


def shrink_hold_return_v4(
    hold_raw: float,
    return_raw: float,
    match_count: int,
    surface: str,
    surface_avg_hold: Optional[Dict[str, float]] = None,
    surface_avg_return: Optional[Dict[str, float]] = None,
    shrinkage_n: int = 15,
) -> Tuple[float, float]:
    """
    Iteration 4 baseline shrinkage (for A/B comparison).
    Reproduces the exact logic from oncourt-compute-fair-odds.py.
    """
    avg_hold = (surface_avg_hold or SURFACE_AVG_HOLD).get(surface, 0.64)
    avg_ret = (surface_avg_return or SURFACE_AVG_RETURN).get(surface, 0.36)

    alpha = match_count / (match_count + shrinkage_n) if match_count > 0 else 0.0
    hold = alpha * hold_raw + (1.0 - alpha) * avg_hold if alpha > 0 else avg_hold
    ret = alpha * return_raw + (1.0 - alpha) * avg_ret if alpha > 0 else avg_ret

    return hold, ret


# ──────────────────────────────────────────────────────────────────────────────
# 2. Cross-surface borrowing
# ──────────────────────────────────────────────────────────────────────────────
#
# When a player has 0 (or very few) matches on the target surface, the
# Iteration 4 baseline collapses them to pure league average. This throws
# away everything we know about the player on other surfaces.
#
# Fix: build a weighted composite from all surfaces the player has data on,
# using the correlation matrix above. Then shrink toward *that* composite
# instead of the raw league average.
#
# The result is a "personalised prior" — a player who holds 72% on Hard
# doesn't get a 64% prior on Grass; they get ~67% (blended toward Grass avg
# but pulled up by their Hard court strength through the 0.45 correlation).

MIN_MATCHES_FOR_DONOR = 5  # don't borrow from a surface with < 5 matches


def cross_surface_estimate(
    target_surface: str,
    player_stats: Dict[str, dict],
    stat_key: str = "hold_pct",
    surface_avg: Optional[Dict[str, float]] = None,
) -> Optional[float]:
    """
    Estimate a player's hold_pct (or return_pct) on target_surface by
    borrowing from correlated surfaces where they have data.

    Parameters:
      target_surface:  the surface we need an estimate for
      player_stats:    dict of {surface: {"hold_pct": x, "return_pct": y, "match_count": n, ...}}
      stat_key:        "hold_pct" or "return_pct"
      surface_avg:     surface average lookup (defaults to module constants)

    Returns:
      Estimated value on target_surface, or None if no usable donor surfaces.
    """
    if surface_avg is None:
        surface_avg = SURFACE_AVG_HOLD if stat_key == "hold_pct" else SURFACE_AVG_RETURN

    target_avg = surface_avg.get(target_surface, 0.64 if "hold" in stat_key else 0.36)
    corr_row = SURFACE_CORRELATION.get(target_surface, {})

    weighted_sum = 0.0
    weight_total = 0.0

    for donor_surface, donor_data in player_stats.items():
        if donor_surface == target_surface:
            continue
        mc = int(donor_data.get("match_count") or 0)
        if mc < MIN_MATCHES_FOR_DONOR:
            continue
        val = donor_data.get(stat_key)
        if val is None:
            continue
        try:
            val = float(val)
        except (ValueError, TypeError):
            continue

        # Correlation weight (how predictive is donor_surface for target_surface?)
        corr = corr_row.get(donor_surface, DEFAULT_CORRELATION)
        if corr <= 0:
            continue

        # Sample-size weight (more matches on donor = more trust)
        sample_weight = mc / (mc + 10)  # soft cap so 100 matches ≈ 0.91

        # Transfer: convert donor stat to target scale
        # donor_stat relative to donor's surface average → apply same relative
        # strength to target surface average
        donor_avg = surface_avg.get(donor_surface, target_avg)
        if donor_avg > 0:
            # Ratio transfer: if player is 5% above donor avg, apply 5% * corr above target avg
            relative_strength = val - donor_avg
            transferred = target_avg + relative_strength * corr
        else:
            transferred = val  # fallback

        w = corr * sample_weight
        weighted_sum += transferred * w
        weight_total += w

    if weight_total <= 0:
        return None

    return weighted_sum / weight_total


def personalised_prior(
    target_surface: str,
    player_stats: Dict[str, dict],
    surface_avg_hold: Optional[Dict[str, float]] = None,
    surface_avg_return: Optional[Dict[str, float]] = None,
) -> Tuple[float, float]:
    """
    Build a personalised prior (hold, return) for the target surface,
    using cross-surface borrowing. Falls back to league average if no
    donor surfaces are available.

    Returns (prior_hold, prior_return).
    """
    avg_h = (surface_avg_hold or SURFACE_AVG_HOLD).get(target_surface, 0.64)
    avg_r = (surface_avg_return or SURFACE_AVG_RETURN).get(target_surface, 0.36)

    est_h = cross_surface_estimate(target_surface, player_stats, "hold_pct", surface_avg_hold or SURFACE_AVG_HOLD)
    est_r = cross_surface_estimate(target_surface, player_stats, "return_pct", surface_avg_return or SURFACE_AVG_RETURN)

    # Blend cross-surface estimate with league average (don't fully trust transfer)
    CROSS_SURFACE_TRUST = 0.65  # 65% personalised, 35% league avg

    prior_h = CROSS_SURFACE_TRUST * est_h + (1.0 - CROSS_SURFACE_TRUST) * avg_h if est_h is not None else avg_h
    prior_r = CROSS_SURFACE_TRUST * est_r + (1.0 - CROSS_SURFACE_TRUST) * avg_r if est_r is not None else avg_r

    return prior_h, prior_r


# ──────────────────────────────────────────────────────────────────────────────
# 3. Smooth 12m/36m blend
# ──────────────────────────────────────────────────────────────────────────────
#
# The Iteration 4 baseline uses a step function:
#   25+ matches → 0.75
#   15+ matches → 0.60
#   8+  matches → 0.50
#   <8  matches → 0.30
# with Clay capped at 0.60 and Grass floored at 0.55.
#
# Problems:
#   - Discontinuity: player with 14 matches gets 0.50; player with 15 gets 0.60
#     (10 percentage point jump from a single match)
#   - Uses min(mc1, mc2) — penalises the well-sampled player when their opponent
#     is sparse
#   - Surface caps are ad-hoc
#
# Fix: logistic function that smoothly maps match_count to recent_weight,
# with per-surface parameters. Each player gets their own weight based on
# their own match count (not min of both).

# Logistic parameters per surface: (midpoint, steepness, floor, ceiling)
# midpoint: match_count where recent_weight = (floor+ceiling)/2
# steepness: how fast the transition is (higher = sharper)
BLEND_PARAMS = {
    "Hard":   {"midpoint": 15, "steepness": 0.18, "floor": 0.30, "ceiling": 0.78},
    "Clay":   {"midpoint": 15, "steepness": 0.15, "floor": 0.28, "ceiling": 0.60},
    "Grass":  {"midpoint": 12, "steepness": 0.20, "floor": 0.40, "ceiling": 0.80},
    "I.hard": {"midpoint": 15, "steepness": 0.18, "floor": 0.30, "ceiling": 0.78},
}

DEFAULT_BLEND_PARAMS = {"midpoint": 15, "steepness": 0.18, "floor": 0.30, "ceiling": 0.75}


def _logistic(x: float, midpoint: float, steepness: float) -> float:
    """Standard logistic function normalised to [0, 1]."""
    z = steepness * (x - midpoint)
    z = max(-20, min(20, z))  # prevent overflow
    return 1.0 / (1.0 + math.exp(-z))


def blend_weight_smooth(match_count: int, surface: str) -> float:
    """
    Smooth logistic blend weight: how much to trust 12m vs 36m data.
    Returns recent_weight ∈ [floor, ceiling] for the given surface.

    Higher recent_weight → more trust in 12m (recent) data.
    Lower recent_weight → more trust in 36m (long-window) data.
    """
    params = BLEND_PARAMS.get(surface, DEFAULT_BLEND_PARAMS)
    raw = _logistic(match_count, params["midpoint"], params["steepness"])
    # Scale from [0,1] to [floor, ceiling]
    return params["floor"] + raw * (params["ceiling"] - params["floor"])


def blend_weight_v4(min_matches_12: int, surface: str) -> float:
    """
    Iteration 4 baseline blend weight (for A/B comparison).
    Reproduces the exact step-function logic.
    """
    if min_matches_12 >= 25:
        recent_weight = 0.75
    elif min_matches_12 >= 15:
        recent_weight = 0.6
    elif min_matches_12 >= 8:
        recent_weight = 0.5
    else:
        recent_weight = 0.3
    if surface == "Clay":
        recent_weight = min(recent_weight, 0.6)
    elif surface == "Grass":
        recent_weight = max(recent_weight, 0.55)
    return recent_weight


def blend_12m_36m(
    h_12: float, r_12: float,
    h_36: float, r_36: float,
    match_count: int,
    surface: str,
    smooth: bool = True,
) -> Tuple[float, float]:
    """
    Blend 12m and 36m hold/return for a single player.

    Parameters:
      h_12, r_12:    12-month hold/return
      h_36, r_36:    36-month hold/return
      match_count:   player's 12m match count on this surface
      surface:       canonical surface
      smooth:        True = use logistic blend (v2), False = step function (v4 baseline)

    Returns (blended_hold, blended_return).
    """
    if smooth:
        w = blend_weight_smooth(match_count, surface)
    else:
        w = blend_weight_v4(match_count, surface)

    hold = w * h_12 + (1.0 - w) * h_36
    ret = w * r_12 + (1.0 - w) * r_36
    return hold, ret


# ──────────────────────────────────────────────────────────────────────────────
# Full pipeline: combine all three improvements
# ──────────────────────────────────────────────────────────────────────────────

def compute_adjusted_stats_v2(
    h1_12: float, r1_12: float, h1_36: float, r1_36: float,
    mc1_12: int, sp1: int, rp1: int,
    h2_12: float, r2_12: float, h2_36: float, r2_36: float,
    mc2_12: int, sp2: int, rp2: int,
    surface: str,
    p1_all_surface_stats: Optional[Dict[str, dict]] = None,
    p2_all_surface_stats: Optional[Dict[str, dict]] = None,
    surface_avg_hold: Optional[Dict[str, float]] = None,
    surface_avg_return: Optional[Dict[str, float]] = None,
) -> Tuple[float, float, float, float]:
    """
    Full v2 pipeline: blend → shrink (with personalised prior if available).
    Returns (hold1, ret1, hold2, ret2) ready for Barnett-Clarke p_a/p_b.

    This is the function that replaces the ~30 lines in oncourt-compute-fair-odds.py
    between "Blend 12m with long-window" and "p_A, p_B: ratio-based".
    """
    # Step 1: Smooth 12m/36m blend (per-player, not min of both)
    hold1_raw, ret1_raw = blend_12m_36m(h1_12, r1_12, h1_36, r1_36, mc1_12, surface, smooth=True)
    hold2_raw, ret2_raw = blend_12m_36m(h2_12, r2_12, h2_36, r2_36, mc2_12, surface, smooth=True)

    # Step 2: Personalised prior via cross-surface borrowing (when target surface data is sparse)
    # Override module-level surface averages for shrinkage target
    prior_h1, prior_r1 = SURFACE_AVG_HOLD.get(surface, 0.64), SURFACE_AVG_RETURN.get(surface, 0.36)
    prior_h2, prior_r2 = prior_h1, prior_r1

    if p1_all_surface_stats and mc1_12 < 10:
        pp = personalised_prior(surface, p1_all_surface_stats, surface_avg_hold, surface_avg_return)
        prior_h1, prior_r1 = pp

    if p2_all_surface_stats and mc2_12 < 10:
        pp = personalised_prior(surface, p2_all_surface_stats, surface_avg_hold, surface_avg_return)
        prior_h2, prior_r2 = pp

    # Step 3: Service-point-based shrinkage toward (personalised) prior
    alpha_h1 = sp1 / (sp1 + SHRINKAGE_PTS_DEFAULT) if sp1 > 0 else 0.0
    alpha_r1 = rp1 / (rp1 + SHRINKAGE_PTS_RETURN) if rp1 > 0 else 0.0
    alpha_h2 = sp2 / (sp2 + SHRINKAGE_PTS_DEFAULT) if sp2 > 0 else 0.0
    alpha_r2 = rp2 / (rp2 + SHRINKAGE_PTS_RETURN) if rp2 > 0 else 0.0

    hold1 = alpha_h1 * hold1_raw + (1.0 - alpha_h1) * prior_h1
    ret1 = alpha_r1 * ret1_raw + (1.0 - alpha_r1) * prior_r1
    hold2 = alpha_h2 * hold2_raw + (1.0 - alpha_h2) * prior_h2
    ret2 = alpha_r2 * ret2_raw + (1.0 - alpha_r2) * prior_r2

    return hold1, ret1, hold2, ret2


def compute_adjusted_stats_v4(
    h1_12: float, r1_12: float, h1_36: float, r1_36: float,
    mc1_12: int,
    h2_12: float, r2_12: float, h2_36: float, r2_36: float,
    mc2_12: int,
    surface: str,
    shrinkage_n: int = 15,
) -> Tuple[float, float, float, float]:
    """
    Iteration 4 baseline (for A/B comparison).
    Reproduces the exact logic from oncourt-compute-fair-odds.py.
    """
    min_matches = min(mc1_12, mc2_12)
    w = blend_weight_v4(min_matches, surface)

    hold1_raw = w * h1_12 + (1.0 - w) * h1_36
    ret1_raw = w * r1_12 + (1.0 - w) * r1_36
    hold2_raw = w * h2_12 + (1.0 - w) * h2_36
    ret2_raw = w * r2_12 + (1.0 - w) * r2_36

    surf_hold = SURFACE_AVG_HOLD.get(surface, 0.64)
    surf_ret = SURFACE_AVG_RETURN.get(surface, 0.36)

    alpha1 = mc1_12 / (mc1_12 + shrinkage_n) if mc1_12 > 0 else 0.0
    alpha2 = mc2_12 / (mc2_12 + shrinkage_n) if mc2_12 > 0 else 0.0

    hold1 = alpha1 * hold1_raw + (1.0 - alpha1) * surf_hold if alpha1 > 0 else surf_hold
    ret1 = alpha1 * ret1_raw + (1.0 - alpha1) * surf_ret if alpha1 > 0 else surf_ret
    hold2 = alpha2 * hold2_raw + (1.0 - alpha2) * surf_hold if alpha2 > 0 else surf_hold
    ret2 = alpha2 * ret2_raw + (1.0 - alpha2) * surf_ret if alpha2 > 0 else surf_ret

    return hold1, ret1, hold2, ret2


# ──────────────────────────────────────────────────────────────────────────────
# Diagnostic: show what changes for a specific matchup
# ──────────────────────────────────────────────────────────────────────────────

def compare_matchup(
    name1: str, name2: str,
    h1_12: float, r1_12: float, h1_36: float, r1_36: float,
    mc1_12: int, sp1: int, rp1: int,
    h2_12: float, r2_12: float, h2_36: float, r2_36: float,
    mc2_12: int, sp2: int, rp2: int,
    surface: str,
    p1_all_surface_stats: Optional[Dict[str, dict]] = None,
    p2_all_surface_stats: Optional[Dict[str, dict]] = None,
):
    """Print side-by-side comparison of v4 baseline vs v2 for one matchup."""
    h1_v4, r1_v4, h2_v4, r2_v4 = compute_adjusted_stats_v4(
        h1_12, r1_12, h1_36, r1_36, mc1_12,
        h2_12, r2_12, h2_36, r2_36, mc2_12,
        surface,
    )
    h1_v2, r1_v2, h2_v2, r2_v2 = compute_adjusted_stats_v2(
        h1_12, r1_12, h1_36, r1_36, mc1_12, sp1, rp1,
        h2_12, r2_12, h2_36, r2_36, mc2_12, sp2, rp2,
        surface,
        p1_all_surface_stats, p2_all_surface_stats,
    )

    print(f"\n{'='*64}")
    print(f"  {name1} vs {name2}  |  Surface: {surface}")
    print(f"{'='*64}")
    print(f"  {'':20} {'V4 Baseline':>14} {'V2 Improved':>14} {'Δ':>8}")
    print(f"  {'-'*20} {'-'*14} {'-'*14} {'-'*8}")
    print(f"  {name1 + ' hold':<20} {h1_v4:>14.4f} {h1_v2:>14.4f} {h1_v2 - h1_v4:>+8.4f}")
    print(f"  {name1 + ' return':<20} {r1_v4:>14.4f} {r1_v2:>14.4f} {r1_v2 - r1_v4:>+8.4f}")
    print(f"  {name2 + ' hold':<20} {h2_v4:>14.4f} {h2_v2:>14.4f} {h2_v2 - h2_v4:>+8.4f}")
    print(f"  {name2 + ' return':<20} {r2_v4:>14.4f} {r2_v2:>14.4f} {r2_v2 - r2_v4:>+8.4f}")

    # Show blend weights
    min_mc = min(mc1_12, mc2_12)
    w_v4 = blend_weight_v4(min_mc, surface)
    w1_v2 = blend_weight_smooth(mc1_12, surface)
    w2_v2 = blend_weight_smooth(mc2_12, surface)
    print(f"\n  Blend weights (12m vs 36m):")
    print(f"    V4: {w_v4:.3f} (min matches={min_mc})")
    print(f"    V2: {name1}={w1_v2:.3f} (mc={mc1_12}), {name2}={w2_v2:.3f} (mc={mc2_12})")

    # Show shrinkage alphas
    alpha_v4_1 = mc1_12 / (mc1_12 + 15) if mc1_12 > 0 else 0
    alpha_v4_2 = mc2_12 / (mc2_12 + 15) if mc2_12 > 0 else 0
    alpha_v2_h1 = sp1 / (sp1 + SHRINKAGE_PTS_DEFAULT) if sp1 > 0 else 0
    alpha_v2_h2 = sp2 / (sp2 + SHRINKAGE_PTS_DEFAULT) if sp2 > 0 else 0
    print(f"\n  Shrinkage alpha (trust in raw stats):")
    print(f"    V4: {name1}={alpha_v4_1:.3f} (mc-based), {name2}={alpha_v4_2:.3f}")
    print(f"    V2: {name1}={alpha_v2_h1:.3f} (svc-pts-based, sp={sp1}), {name2}={alpha_v2_h2:.3f} (sp={sp2})")


# ──────────────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("="*64)
    print("  shrinkage_v2.py — Self-test")
    print("="*64)

    # Test 1: Blend weight comparison
    print("\n── Blend Weight Comparison (Hard) ──")
    print(f"  {'MC':>4}  {'V4 (step)':>10}  {'V2 (smooth)':>12}  {'Δ':>8}")
    for mc in [0, 3, 5, 7, 8, 10, 14, 15, 16, 20, 25, 30, 40, 50]:
        w_v4 = blend_weight_v4(mc, "Hard")
        w_v2 = blend_weight_smooth(mc, "Hard")
        print(f"  {mc:>4}  {w_v4:>10.3f}  {w_v2:>12.3f}  {w_v2 - w_v4:>+8.3f}")

    print("\n── Blend Weight Comparison (Clay) ──")
    print(f"  {'MC':>4}  {'V4 (step)':>10}  {'V2 (smooth)':>12}  {'Δ':>8}")
    for mc in [0, 5, 8, 15, 25, 40]:
        w_v4 = blend_weight_v4(mc, "Clay")
        w_v2 = blend_weight_smooth(mc, "Clay")
        print(f"  {mc:>4}  {w_v4:>10.3f}  {w_v2:>12.3f}  {w_v2 - w_v4:>+8.3f}")

    print("\n── Blend Weight Comparison (Grass) ──")
    print(f"  {'MC':>4}  {'V4 (step)':>10}  {'V2 (smooth)':>12}  {'Δ':>8}")
    for mc in [0, 5, 8, 12, 15, 25, 40]:
        w_v4 = blend_weight_v4(mc, "Grass")
        w_v2 = blend_weight_smooth(mc, "Grass")
        print(f"  {mc:>4}  {w_v4:>10.3f}  {w_v2:>12.3f}  {w_v2 - w_v4:>+8.3f}")

    # Test 2: Cross-surface borrowing
    print("\n── Cross-Surface Borrowing ──")
    player_stats = {
        "Hard": {"hold_pct": 0.72, "return_pct": 0.40, "match_count": 30},
        "Clay": {"hold_pct": 0.60, "return_pct": 0.42, "match_count": 20},
    }
    for target in ["Grass", "I.hard"]:
        est_h = cross_surface_estimate(target, player_stats, "hold_pct")
        est_r = cross_surface_estimate(target, player_stats, "return_pct")
        avg_h = SURFACE_AVG_HOLD[target]
        avg_r = SURFACE_AVG_RETURN[target]
        print(f"  Target={target}: personalised hold={est_h:.4f} (vs avg {avg_h:.3f}), "
              f"return={est_r:.4f} (vs avg {avg_r:.3f})")

    # Test 3: Full matchup comparison
    # Scenario: well-known player vs sparse data opponent on Grass
    compare_matchup(
        "Sinner", "Qualifier",
        h1_12=0.74, r1_12=0.40, h1_36=0.72, r1_36=0.39,
        mc1_12=25, sp1=800, rp1=750,
        h2_12=0.62, r2_12=0.34, h2_36=0.61, r2_36=0.35,
        mc2_12=4, sp2=120, rp2=110,
        surface="Grass",
        p1_all_surface_stats={
            "Hard": {"hold_pct": 0.73, "return_pct": 0.41, "match_count": 40},
            "Clay": {"hold_pct": 0.65, "return_pct": 0.38, "match_count": 30},
        },
        p2_all_surface_stats={
            "Hard": {"hold_pct": 0.63, "return_pct": 0.35, "match_count": 25},
            "Clay": {"hold_pct": 0.60, "return_pct": 0.40, "match_count": 15},
        },
    )

    # Scenario: two similarly-ranked players, one with many service points from long matches
    compare_matchup(
        "Player A (3-setters)", "Player B (bagels)",
        h1_12=0.66, r1_12=0.37, h1_36=0.65, r1_36=0.36,
        mc1_12=12, sp1=480, rp1=460,  # 12 matches but lots of service points
        h2_12=0.66, r2_12=0.37, h2_36=0.65, r2_36=0.36,
        mc2_12=12, sp2=200, rp2=190,  # 12 matches but short (straight sets / bagels)
        surface="Hard",
    )

    print("\n  Done.\n")
