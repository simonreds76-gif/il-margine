"""
Class Gap Adjustment — class_gap.py
=====================================
Fixes the model's inability to produce extreme probabilities for
heavy mismatches (e.g. Sinner 1.20 when bookies have 1.01).

Problem:
  The K-M recursion from serve/return stats has a natural ceiling.
  Even with p_a=0.78 (max clamp) and p_b=0.52 (min clamp), the
  match win prob tops out at ~97%. But Sinner vs a qualifier is 99%+.

  Serve stats can't express the full class gap because both players
  are professionals who hold serve at reasonable rates. The difference
  is in shot quality, movement, pressure handling, tactical depth —
  none of which appear in point-level stats.

Solution:
  When there's a large Elo/rank gap, apply a post-hoc adjustment
  that pushes the probability toward the empirical win rate for
  that class gap. This uses historical data: how often does a
  player with Elo X actually beat a player with Elo Y?

  The Elo system already encodes this: P(win) = 1/(1+10^(Δ/400)).
  An Elo gap of 500 → 95%, 600 → 97%, 700 → 98.3%, 800 → 99%.

  The model's serve/return + Elo hybrid currently caps the Elo
  contribution at 70% weight. For extreme mismatches, Elo should
  dominate because serve stats become uninformative (both players
  hold at high rates, the difference is elsewhere).

Usage:
  from class_gap import apply_class_gap

  # After computing p1_win from the hybrid model:
  p1_win = apply_class_gap(
      p1_win, elo1_surface, elo2_surface, elo1_overall, elo2_overall,
      rank1, rank2
  )
"""

import math
from typing import Optional


def elo_expected(elo_a: float, elo_b: float) -> float:
    """Standard Elo expected score."""
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def apply_class_gap(
    model_prob: float,
    elo1_surface: float,
    elo2_surface: float,
    elo1_overall: Optional[float] = None,
    elo2_overall: Optional[float] = None,
    rank1: Optional[int] = None,
    rank2: Optional[int] = None,
    # Thresholds
    elo_gap_onset: float = 250,     # start adjusting at 250 Elo gap
    elo_gap_full: float = 500,      # full adjustment at 500+ Elo gap
    rank_gap_onset: int = 40,       # start adjusting at 40 rank gap
    rank_gap_full: int = 120,       # full adjustment at 120+ rank gap
    max_blend: float = 0.85,         # max weight given to Elo-based prob (vs model)
) -> float:
    """
    Adjust model probability for extreme class gaps.

    When the Elo/rank gap is large, the serve/return model underestimates
    the favourite because it can't express the full quality difference.
    This blends the model's probability toward the pure Elo expectation,
    with the blend weight increasing as the gap grows.

    Parameters:
      model_prob:     P(player 1 wins) from the hybrid model
      elo1/2_surface: surface Elo ratings
      elo1/2_overall: overall Elo ratings (optional, used for 50/50 blend)
      rank1/2:        ATP rankings (optional, used as secondary signal)
      elo_gap_onset:  Elo gap where adjustment starts
      elo_gap_full:   Elo gap where adjustment reaches max_blend
      rank_gap_onset: rank gap (in positions) where adjustment starts
      rank_gap_full:  rank gap where adjustment reaches max_blend
      max_blend:      maximum weight given to Elo probability

    Returns:
      adjusted P(player 1 wins)
    """
    # Compute pure Elo probability (50/50 surface + overall blend)
    p_elo_surface = elo_expected(elo1_surface, elo2_surface)
    if elo1_overall is not None and elo2_overall is not None:
        p_elo_overall = elo_expected(elo1_overall, elo2_overall)
        p_elo = 0.5 * p_elo_surface + 0.5 * p_elo_overall
    else:
        p_elo = p_elo_surface

    # Elo gap (absolute)
    elo_gap = abs(elo1_surface - elo2_surface)
    if elo1_overall is not None and elo2_overall is not None:
        elo_gap = max(elo_gap, abs(elo1_overall - elo2_overall))

    # Rank gap (if available)
    rank_gap = 0
    if rank1 is not None and rank2 is not None and rank1 > 0 and rank2 > 0:
        rank_gap = abs(rank1 - rank2)

    # Compute blend weight: how much to trust Elo over the model
    # Ramps from 0 at onset to max_blend at full gap
    elo_blend = 0.0
    if elo_gap > elo_gap_onset:
        elo_ramp = min(1.0, (elo_gap - elo_gap_onset) / (elo_gap_full - elo_gap_onset))
        elo_blend = elo_ramp * max_blend

    rank_blend = 0.0
    if rank_gap > rank_gap_onset:
        rank_ramp = min(1.0, (rank_gap - rank_gap_onset) / (rank_gap_full - rank_gap_onset))
        rank_blend = rank_ramp * max_blend * 0.7  # rank is somewhat noisier, 70% weight

    # Take the stronger signal
    blend_weight = max(elo_blend, rank_blend)

    if blend_weight <= 0:
        return model_prob  # no adjustment needed

    # Blend: push model probability toward Elo probability
    # But only in the direction that makes the favourite MORE favoured
    # (never reduce the favourite's probability — the model's floor is the issue, not excess)
    adjusted = (1.0 - blend_weight) * model_prob + blend_weight * p_elo

    # Safety: the adjustment should push AWAY from 0.5 for the favourite
    # If model says 0.83 and Elo says 0.97, adjusted should be >0.83
    # If model says 0.83 and Elo says 0.75 (disagreement), don't adjust
    model_favours_p1 = model_prob > 0.5
    elo_favours_p1 = p_elo > 0.5

    if model_favours_p1 and elo_favours_p1:
        # Both agree P1 is favourite — push toward Elo if it's more extreme
        adjusted = max(model_prob, adjusted)
    elif not model_favours_p1 and not elo_favours_p1:
        # Both agree P2 is favourite — push toward Elo if it's more extreme
        adjusted = min(model_prob, adjusted)
    else:
        # Disagreement on who's favourite — don't apply class gap
        return model_prob

    # Clamp to realistic range (never go below 1.01 odds = 99%)
    adjusted = max(0.01, min(0.99, adjusted))

    return adjusted


def estimate_fair_odds_range(
    elo1_surface: float,
    elo2_surface: float,
    elo1_overall: Optional[float] = None,
    elo2_overall: Optional[float] = None,
) -> dict:
    """
    Quick estimate: what odds range should we expect for this Elo gap?
    Useful for sanity-checking model output.
    """
    p = elo_expected(elo1_surface, elo2_surface)
    if elo1_overall is not None and elo2_overall is not None:
        p2 = elo_expected(elo1_overall, elo2_overall)
        p = 0.5 * p + 0.5 * p2

    gap = abs(elo1_surface - elo2_surface)

    return {
        "elo_gap": round(gap, 0),
        "elo_p1_win": round(p, 4),
        "elo_odds_p1": round(1/p, 2) if p > 0.01 else 99,
        "elo_odds_p2": round(1/(1-p), 2) if p < 0.99 else 99,
        "expected_model_range": f"If model gives P1 > {1/p + 0.15:.2f}, class gap fix needed",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Self-test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("="*60)
    print("  class_gap.py — Self-test")
    print("="*60)

    # Test cases: increasing Elo gaps
    cases = [
        ("Close match (Elo gap 100)",     1800, 1700, 1750, 1650, 10, 20),
        ("Clear favourite (gap 300)",     2000, 1700, 1950, 1650, 5, 40),
        ("Strong favourite (gap 500)",    2100, 1600, 2050, 1550, 2, 80),
        ("Sinner vs qualifier (gap 600)", 2200, 1600, 2150, 1500, 1, 150),
        ("Extreme mismatch (gap 800)",    2300, 1500, 2250, 1450, 1, 250),
    ]

    print(f"\n  {'Case':<35} {'Model':>7} {'Elo':>7} {'Adjusted':>9} {'Odds':>7} {'d':>7}")
    print(f"  {'-'*35} {'-'*7} {'-'*7} {'-'*9} {'-'*7} {'-'*7}")

    for name, e1s, e2s, e1o, e2o, r1, r2 in cases:
        # Simulate model output (capped by K-M recursion)
        # Model typically gives ~83-97% for these gaps
        p_elo = elo_expected(e1s, e2s)
        p_elo_blend = 0.5 * p_elo + 0.5 * elo_expected(e1o, e2o)
        # Simulate model being less extreme than Elo
        model_prob = 0.5 + (p_elo_blend - 0.5) * 0.85  # model is 85% of Elo's extremity

        adjusted = apply_class_gap(model_prob, e1s, e2s, e1o, e2o, r1, r2)
        odds = round(1/adjusted, 2) if adjusted > 0.01 else 99

        print(f"  {name:<35} {model_prob:>7.3f} {p_elo_blend:>7.3f} {adjusted:>9.4f} {odds:>7.2f} {adjusted-model_prob:>+7.4f}")

    # Specific Sinner test
    print(f"\n  -- Sinner vs Qualifier scenario --")
    # Sinner: ~2150 surface Elo, ~2100 overall, rank 1
    # Qualifier: ~1550 surface, ~1500 overall, rank 180
    model_prob = 0.83  # what the model currently gives (odds ~1.20)
    adj = apply_class_gap(model_prob, 2150, 1550, 2100, 1500, 1, 180)
    print(f"  Model says: {model_prob:.2f} (odds {1/model_prob:.2f})")
    print(f"  Elo says:   {elo_expected(2150, 1550):.4f} surface, "
          f"{0.5*elo_expected(2150,1550)+0.5*elo_expected(2100,1500):.4f} blended")
    print(f"  Adjusted:   {adj:.4f} (odds {1/adj:.2f})")
    print(f"  Market:     ~0.99 (odds ~1.01)")
    if 1/adj < 1.05:
        print(f"  [OK] Now in realistic range")
    else:
        print(f"  Still above market — may need Elo recalibration or wider gap parameters")

    # Show that close matches aren't affected
    print(f"\n  -- Close match (no adjustment expected) --")
    model_prob = 0.55
    adj = apply_class_gap(model_prob, 1700, 1650, 1680, 1640, 25, 35)
    print(f"  Model: {model_prob:.2f} -> Adjusted: {adj:.4f} (d={adj-model_prob:+.4f})")
    print(f"  {'[OK] No change' if abs(adj - model_prob) < 0.001 else '[!] Unexpected change'}")

    print(f"\n  Done.\n")
