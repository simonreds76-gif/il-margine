"""
Compound Fatigue Model — fatigue_model.py
==========================================
Replaces the basic binary fatigue flags in the fair-odds pipeline with
a rich multi-factor fatigue system.

Current model (V4):
  played_yesterday → -0.008
  3+ matches in 5d → -0.007
  Total cap: ±0.015

What this misses:
  - A 3-hour three-set semifinal yesterday ≠ a 55-minute bagel yesterday
  - Back-to-back-to-back days compound non-linearly
  - Surface transitions (clay → hard) add physical/tactical fatigue
  - The DIFFERENTIAL matters: fatigued vs fresh is bigger than both fatigued
  - Tournament load (R1 vs QF after 3 matches that week)
  - Travel (different continent last week)

New model computes a continuous FATIGUE SCORE per player (0 = fresh, 1 = exhausted),
then converts the differential to a probability adjustment.

Data sources (all from games_atp.csv, no new data needed):
  - Match dates → rest days, consecutive days, back-to-back detection
  - Scores → match intensity (sets played, total games)
  - Tour_id → surface transitions, tournament load
  - Round_id → how deep in the draw (more matches = more fatigue)

Usage:
  from fatigue_model import compute_fatigue_score, fatigue_adjustment

  score_a = compute_fatigue_score(player_a_recent_matches)
  score_b = compute_fatigue_score(player_b_recent_matches)
  delta = fatigue_adjustment(score_a, score_b)
  # delta is added to p1_win (positive = favours p1, negative = favours p2)

Integration:
  In oncourt-compute-fair-odds.py, replace the _form_fatigue_rust function
  with calls to this module. The fatigue_adjustment output replaces
  delta_fatigue and delta_rust in the current pipeline.
"""

import math
from datetime import date, timedelta
from typing import List, Optional, Dict, Tuple, Any
from collections import defaultdict


# ══════════════════════════════════════════════════════════════════════════════
# Recent match record (input to fatigue model)
# ══════════════════════════════════════════════════════════════════════════════

class RecentMatch:
    """One recent match for a player, used to compute fatigue."""

    def __init__(
        self,
        match_date: date,
        sets_played: int = 2,        # 2 or 3 for bo3
        total_games: int = 20,       # total games in match
        won: bool = True,
        surface: str = "Hard",
        tour_id: Optional[int] = None,
        round_id: Optional[int] = None,  # higher = later round (e.g. 7=F, 6=SF, 5=QF)
        is_retirement: bool = False,  # opponent retired (shorter match)
        is_walkover: bool = False,    # walkover (no match played)
    ):
        self.match_date = match_date
        self.sets_played = sets_played
        self.total_games = total_games
        self.won = won
        self.surface = surface
        self.tour_id = tour_id
        self.round_id = round_id
        self.is_retirement = is_retirement
        self.is_walkover = is_walkover

    @property
    def intensity(self) -> float:
        """
        Match intensity on [0, 1] scale.
        0.0 = walkover / very short match
        0.5 = average two-setter (~22 games)
        1.0 = grueling three-setter (~38+ games)
        """
        if self.is_walkover:
            return 0.0
        if self.is_retirement:
            # Opponent retired — shorter match, but still played
            return max(0.1, min(0.6, self.total_games / 40.0))

        # Intensity based on total games (proxy for match duration)
        # 12 games (6-0 6-0) = very low intensity
        # 24 games (6-3 6-3) = moderate
        # 36 games (7-6 6-7 7-5) = very high
        # 39+ games = grueling
        game_intensity = (self.total_games - 12) / 27.0  # normalise: 12→0, 39→1
        game_intensity = max(0.0, min(1.0, game_intensity))

        # Three-setters are disproportionately tiring
        set_bonus = 0.15 if self.sets_played >= 3 else 0.0

        return min(1.0, game_intensity + set_bonus)


# ══════════════════════════════════════════════════════════════════════════════
# Fatigue score computation
# ══════════════════════════════════════════════════════════════════════════════

# How quickly fatigue decays per rest day (exponential decay)
FATIGUE_HALF_LIFE_DAYS = 2.0  # fatigue halves every 2 days of rest

# Consecutive days multiplier (non-linear compounding)
CONSECUTIVE_DAYS_MULTIPLIER = {
    1: 1.0,   # played yesterday — base fatigue
    2: 1.6,   # played yesterday AND day before — much worse
    3: 2.3,   # three consecutive days — tournament grind
    4: 3.0,   # four consecutive — extreme (rare)
}

# Surface transition penalty
SURFACE_TRANSITION_PENALTY = {
    # (from_surface, to_surface) → additional fatigue multiplier
    # Clay ↔ Hard/Grass is the biggest transition (different movement, footwork)
    ("Clay", "Hard"): 0.12,
    ("Hard", "Clay"): 0.10,
    ("Clay", "Grass"): 0.15,
    ("Grass", "Clay"): 0.13,
    ("Hard", "Grass"): 0.06,
    ("Grass", "Hard"): 0.06,
    ("Clay", "I.hard"): 0.10,
    ("I.hard", "Clay"): 0.10,
    # Same surface → no penalty (already in base fatigue)
}

# Tournament load: cumulative fatigue from multiple matches in same event
# Each additional match in the same tournament adds residual fatigue
TOURNAMENT_LOAD_PER_MATCH = 0.05  # small but cumulative

# Maximum individual match fatigue contribution
MAX_MATCH_FATIGUE = 0.45

# How fatigue differential converts to probability adjustment
# This is the key parameter: how much does a fatigued-vs-fresh matchup matter?
FATIGUE_TO_PROB_SCALE = 0.08  # 1.0 fatigue differential → 8% prob adjustment
FATIGUE_PROB_CAP = 0.05       # max probability adjustment from fatigue


def compute_fatigue_score(
    recent_matches: List[RecentMatch],
    match_date: date,
    current_surface: str = "Hard",
    current_tour_id: Optional[int] = None,
    lookback_days: int = 14,
) -> Tuple[float, Dict]:
    """
    Compute a continuous fatigue score for a player.

    Parameters:
      recent_matches: list of RecentMatch objects, sorted by date (most recent first)
      match_date: date of the upcoming match
      current_surface: surface of the upcoming match
      current_tour_id: tournament id of the upcoming match
      lookback_days: how far back to look for fatigue effects

    Returns:
      (fatigue_score, debug_dict)
      fatigue_score ∈ [0, 1]: 0 = fresh, 1 = heavily fatigued
    """
    if not recent_matches:
        return 0.0, {"reason": "no recent matches", "components": {}}

    cutoff = match_date - timedelta(days=lookback_days)
    relevant = [m for m in recent_matches if m.match_date >= cutoff and m.match_date < match_date]

    if not relevant:
        # Check for rust (no matches in lookback window)
        days_since_last = None
        if recent_matches:
            last = max(m.match_date for m in recent_matches if m.match_date < match_date)
            days_since_last = (match_date - last).days
        return 0.0, {"reason": "no matches in window", "days_since_last": days_since_last}

    # Sort by date descending (most recent first)
    relevant.sort(key=lambda m: m.match_date, reverse=True)

    decay_rate = math.log(2) / FATIGUE_HALF_LIFE_DAYS

    # ── Component 1: Cumulative match fatigue (with time decay) ──
    cumulative_fatigue = 0.0
    for m in relevant:
        days_ago = (match_date - m.match_date).days
        if days_ago < 1:
            days_ago = 0.5  # same day = half day decay

        # Raw fatigue from this match
        raw = m.intensity * MAX_MATCH_FATIGUE

        # Decay: fatigue reduces exponentially with rest days
        decayed = raw * math.exp(-decay_rate * days_ago)
        cumulative_fatigue += decayed

    # ── Component 2: Consecutive days played (non-linear compounding) ──
    consecutive_bonus = 0.0
    consecutive_count = 0
    check_date = match_date - timedelta(days=1)
    for i in range(5):
        played_on_day = any(m.match_date == check_date for m in relevant)
        if played_on_day:
            consecutive_count += 1
            check_date -= timedelta(days=1)
        else:
            break

    if consecutive_count > 0:
        multiplier = CONSECUTIVE_DAYS_MULTIPLIER.get(consecutive_count, 3.0 + consecutive_count * 0.5)
        # The bonus is applied to the most recent match's fatigue
        most_recent = relevant[0]
        consecutive_bonus = most_recent.intensity * 0.1 * multiplier

    # ── Component 3: Surface transition ──
    surface_penalty = 0.0
    # Check if most recent match was on a different surface
    if relevant:
        last_surface = relevant[0].surface
        key = (last_surface, current_surface)
        surface_penalty = SURFACE_TRANSITION_PENALTY.get(key, 0.0)
        # Only apply if the transition was recent (within 3 days)
        days_since_last_match = (match_date - relevant[0].match_date).days
        if days_since_last_match > 3:
            surface_penalty *= 0.3  # decay the surface transition effect

    # ── Component 4: Tournament load (matches at same event this week) ──
    tournament_load = 0.0
    if current_tour_id is not None:
        same_event = [m for m in relevant if m.tour_id == current_tour_id]
        tournament_load = len(same_event) * TOURNAMENT_LOAD_PER_MATCH

    # ── Combine ──
    total = cumulative_fatigue + consecutive_bonus + surface_penalty + tournament_load

    # Soft clamp to [0, 1] using sigmoid-like compression
    # This prevents extreme values while preserving ordering
    fatigue_score = 1.0 - math.exp(-total * 2.5)  # 0→0, 0.3→0.53, 0.5→0.71, 1.0→0.92
    fatigue_score = max(0.0, min(1.0, fatigue_score))

    debug = {
        "matches_in_window": len(relevant),
        "cumulative_fatigue": round(cumulative_fatigue, 4),
        "consecutive_days": consecutive_count,
        "consecutive_bonus": round(consecutive_bonus, 4),
        "surface_transition": round(surface_penalty, 4),
        "tournament_load": round(tournament_load, 4),
        "raw_total": round(total, 4),
        "fatigue_score": round(fatigue_score, 4),
    }

    return fatigue_score, debug


def fatigue_adjustment(
    fatigue_a: float,
    fatigue_b: float,
    scale: float = FATIGUE_TO_PROB_SCALE,
    cap: float = FATIGUE_PROB_CAP,
) -> float:
    """
    Convert fatigue differential to probability adjustment.

    Positive return = favours player A (B is more fatigued).
    Negative return = favours player B (A is more fatigued).

    The adjustment is applied to P(A wins).
    """
    diff = fatigue_b - fatigue_a  # positive = B more fatigued = good for A
    raw_adj = diff * scale

    # Soft cap using tanh
    adj = cap * math.tanh(raw_adj / cap) if abs(raw_adj) > 0.001 else raw_adj
    return adj


# ══════════════════════════════════════════════════════════════════════════════
# Rust model (inactivity)
# ══════════════════════════════════════════════════════════════════════════════

# Rust is separate from fatigue — it penalises long breaks, not recent activity
RUST_ONSET_DAYS = 21        # start applying rust after 21 days inactive
RUST_SEVERE_DAYS = 42       # severe rust after 42+ days
RUST_MAX_PENALTY = 0.025    # max probability penalty from rust
RUST_GROWTH_RATE = 0.04     # how fast rust grows per day past onset


def compute_rust_penalty(
    days_since_last_match: Optional[int],
) -> float:
    """
    Compute rust penalty for inactivity.
    Returns a NEGATIVE value (penalty to win probability).
    """
    if days_since_last_match is None or days_since_last_match < RUST_ONSET_DAYS:
        return 0.0

    excess_days = days_since_last_match - RUST_ONSET_DAYS
    raw_penalty = excess_days * RUST_GROWTH_RATE * 0.001  # small per day
    # Accelerate for severe rust
    if days_since_last_match >= RUST_SEVERE_DAYS:
        raw_penalty *= 1.5

    return -min(RUST_MAX_PENALTY, raw_penalty)


# ══════════════════════════════════════════════════════════════════════════════
# Combined fatigue + rust adjustment (drop-in replacement)
# ══════════════════════════════════════════════════════════════════════════════

def compute_fatigue_rust_delta(
    p1_matches: List[RecentMatch],
    p2_matches: List[RecentMatch],
    match_date: date,
    surface: str,
    tour_id: Optional[int] = None,
    debug: bool = False,
) -> Tuple[float, Optional[Dict]]:
    """
    Complete fatigue + rust adjustment for a match.

    Returns (delta_p1, debug_dict).
    delta_p1 is added to P(player 1 wins).
    Positive = fatigue favours P1, negative = favours P2.

    This replaces the entire _form_fatigue_rust function in the fair-odds pipeline
    (minus the form component, which is separate).
    """
    # Fatigue scores
    fat1, dbg1 = compute_fatigue_score(p1_matches, match_date, surface, tour_id)
    fat2, dbg2 = compute_fatigue_score(p2_matches, match_date, surface, tour_id)

    # Fatigue differential → probability adjustment
    delta_fatigue = fatigue_adjustment(fat1, fat2)

    # Rust (for each player independently)
    def _days_since(matches, md):
        played = [m.match_date for m in matches if m.match_date < md]
        if played:
            return (md - max(played)).days
        return None

    days1 = _days_since(p1_matches, match_date)
    days2 = _days_since(p2_matches, match_date)
    rust1 = compute_rust_penalty(days1)
    rust2 = compute_rust_penalty(days2)
    delta_rust = 0.5 * (rust2 - rust1)  # differential: P2 rustier = good for P1

    total_delta = delta_fatigue + delta_rust

    dbg = None
    if debug:
        dbg = {
            "p1_fatigue_score": round(fat1, 4),
            "p2_fatigue_score": round(fat2, 4),
            "fatigue_diff": round(fat2 - fat1, 4),
            "delta_fatigue": round(delta_fatigue, 4),
            "p1_days_since": days1,
            "p2_days_since": days2,
            "p1_rust": round(rust1, 4),
            "p2_rust": round(rust2, 4),
            "delta_rust": round(delta_rust, 4),
            "total_delta": round(total_delta, 4),
            "p1_detail": dbg1,
            "p2_detail": dbg2,
        }

    return total_delta, dbg


# ══════════════════════════════════════════════════════════════════════════════
# Helper: build RecentMatch list from games_atp data
# ══════════════════════════════════════════════════════════════════════════════

def parse_score_to_games(score: str) -> Tuple[int, int]:
    """
    Parse a tennis score string into (sets_played, total_games).
    Handles formats like: "6-3 7-5", "6-4 3-6 7-6(5)", "6-1 6-0", "RET", "W/O"
    """
    if not score or not score.strip():
        return 2, 20  # default

    score = score.strip().upper()
    if "W/O" in score or "WO" in score or "WALKOVER" in score:
        return 0, 0
    if "RET" in score or "RETIRED" in score:
        # Try to parse what was played before retirement
        pass

    total_games = 0
    sets = 0
    for part in score.replace("  ", " ").split():
        part = part.strip().rstrip(")")
        # Remove tiebreak score
        if "(" in part:
            part = part[:part.index("(")]
        parts = part.split("-")
        if len(parts) == 2:
            try:
                a, b = int(parts[0]), int(parts[1])
                total_games += a + b
                sets += 1
            except ValueError:
                continue

    if sets == 0:
        return 2, 20  # couldn't parse, use default
    return sets, total_games


def build_recent_matches(
    player_id: int,
    games_data: List[Dict],
    tour_surface_map: Dict[int, str],
    before_date: date,
    lookback_days: int = 21,
) -> List[RecentMatch]:
    """
    Build a list of RecentMatch objects from games_atp.csv data.

    games_data should be pre-filtered or indexed for the player.
    Each row needs: winner_id, loser_id, tour_id, round_id, date, result/score.
    """
    cutoff = before_date - timedelta(days=lookback_days)
    matches = []

    for g in games_data:
        w = g.get("winner_id")
        l = g.get("loser_id")
        if w is None and l is None:
            continue

        try:
            wid = int(float(w)) if w else 0
            lid = int(float(l)) if l else 0
        except (ValueError, TypeError):
            continue

        if wid != player_id and lid != player_id:
            continue

        # Parse date
        d = g.get("date")
        if not d:
            continue
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d.strip()[:10])
            except ValueError:
                continue

        if d < cutoff or d >= before_date:
            continue

        # Parse score
        score = g.get("result") or g.get("score") or ""
        sets_played, total_games = parse_score_to_games(str(score))

        is_wo = total_games == 0 and sets_played == 0
        is_ret = "RET" in str(score).upper()

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

        surface = tour_surface_map.get(tid, "Hard") if tid else "Hard"

        matches.append(RecentMatch(
            match_date=d,
            sets_played=sets_played,
            total_games=total_games,
            won=(wid == player_id),
            surface=surface,
            tour_id=tid,
            round_id=rid,
            is_retirement=is_ret,
            is_walkover=is_wo,
        ))

    # Sort most recent first
    matches.sort(key=lambda m: m.match_date, reverse=True)
    return matches


# ══════════════════════════════════════════════════════════════════════════════
# Self-test
# ══════════════════════════════════════════════════════════════════════════════

def _test_scenario(name, p1_matches, p2_matches, match_date, surface, tour_id=None):
    """Print a scenario comparison."""
    delta, dbg = compute_fatigue_rust_delta(p1_matches, p2_matches, match_date, surface, tour_id, debug=True)

    print(f"\n{'-'*60}")
    print(f"  {name}")
    print(f"{'-'*60}")
    print(f"  P1 fatigue: {dbg['p1_fatigue_score']:.3f}  ({dbg['p1_detail'].get('matches_in_window', 0)} matches)")
    if dbg['p1_detail'].get('consecutive_days', 0) > 0:
        print(f"    Consecutive days: {dbg['p1_detail']['consecutive_days']}")
    if dbg['p1_detail'].get('surface_transition', 0) > 0:
        print(f"    Surface transition: +{dbg['p1_detail']['surface_transition']:.3f}")

    print(f"  P2 fatigue: {dbg['p2_fatigue_score']:.3f}  ({dbg['p2_detail'].get('matches_in_window', 0)} matches)")
    if dbg['p2_detail'].get('consecutive_days', 0) > 0:
        print(f"    Consecutive days: {dbg['p2_detail']['consecutive_days']}")

    print(f"  Fatigue delta (→ P1 win prob): {dbg['delta_fatigue']:+.4f}")
    if dbg['delta_rust'] != 0:
        print(f"  Rust delta: {dbg['delta_rust']:+.4f}")
    print(f"  Total delta: {dbg['total_delta']:+.4f}")

    # Compare to V4
    v4_delta = 0.0
    if dbg['p1_detail'].get('consecutive_days', 0) >= 1:
        v4_delta -= 0.008  # played_yesterday
    if dbg['p2_detail'].get('consecutive_days', 0) >= 1:
        v4_delta += 0.008
    print(f"  V4 baseline would give: {v4_delta:+.4f}")
    print(f"  Improvement: {abs(delta) - abs(v4_delta):+.4f} additional information")


if __name__ == "__main__":
    print("="*60)
    print("  fatigue_model.py — Self-test")
    print("="*60)

    today = date(2025, 3, 6)
    yesterday = today - timedelta(days=1)
    two_days = today - timedelta(days=2)
    three_days = today - timedelta(days=3)
    week_ago = today - timedelta(days=7)

    # Scenario 1: Grueling SF yesterday vs fresh opponent
    _test_scenario(
        "Grueling SF yesterday vs fresh opponent",
        p1_matches=[
            RecentMatch(yesterday, sets_played=3, total_games=38, won=True, surface="Hard", tour_id=100, round_id=6),
            RecentMatch(three_days, sets_played=2, total_games=22, won=True, surface="Hard", tour_id=100, round_id=5),
        ],
        p2_matches=[
            RecentMatch(week_ago, sets_played=2, total_games=20, won=True, surface="Hard"),
        ],
        match_date=today, surface="Hard", tour_id=100,
    )

    # Scenario 2: Three consecutive days vs two days rest
    _test_scenario(
        "Three consecutive days (tournament grind) vs 2 days rest",
        p1_matches=[
            RecentMatch(yesterday, sets_played=2, total_games=24, won=True, surface="Hard", tour_id=100),
            RecentMatch(two_days, sets_played=3, total_games=35, won=True, surface="Hard", tour_id=100),
            RecentMatch(three_days, sets_played=2, total_games=22, won=True, surface="Hard", tour_id=100),
        ],
        p2_matches=[
            RecentMatch(three_days, sets_played=2, total_games=20, won=True, surface="Hard", tour_id=100),
        ],
        match_date=today, surface="Hard", tour_id=100,
    )

    # Scenario 3: Quick bagel yesterday vs opponent's grueling match
    _test_scenario(
        "Easy bagel yesterday (low intensity) vs opponent fresh",
        p1_matches=[
            RecentMatch(yesterday, sets_played=2, total_games=13, won=True, surface="Hard"),
        ],
        p2_matches=[
            RecentMatch(week_ago, sets_played=2, total_games=22, won=True, surface="Hard"),
        ],
        match_date=today, surface="Hard",
    )

    # Scenario 4: Surface transition (clay → hard)
    _test_scenario(
        "Surface transition: played on clay 2 days ago, now on hard",
        p1_matches=[
            RecentMatch(two_days, sets_played=3, total_games=34, won=True, surface="Clay", tour_id=200),
        ],
        p2_matches=[
            RecentMatch(two_days, sets_played=2, total_games=22, won=True, surface="Hard", tour_id=100),
        ],
        match_date=today, surface="Hard",
    )

    # Scenario 5: Both fatigued but asymmetric
    _test_scenario(
        "Both played yesterday, but P1 had 3-setter, P2 had quick win",
        p1_matches=[
            RecentMatch(yesterday, sets_played=3, total_games=36, won=True, surface="Hard"),
        ],
        p2_matches=[
            RecentMatch(yesterday, sets_played=2, total_games=14, won=True, surface="Hard"),
        ],
        match_date=today, surface="Hard",
    )

    # Scenario 6: Rust vs active
    _test_scenario(
        "P1 hasn't played in 35 days (moderate rust) vs P2 active",
        p1_matches=[
            RecentMatch(today - timedelta(days=35), sets_played=2, total_games=22, won=False, surface="Hard"),
        ],
        p2_matches=[
            RecentMatch(three_days, sets_played=2, total_games=24, won=True, surface="Hard"),
            RecentMatch(week_ago, sets_played=2, total_games=20, won=True, surface="Hard"),
        ],
        match_date=today, surface="Hard",
    )

    # Score parser test
    print(f"\n{'-'*60}")
    print(f"  Score Parser Tests")
    print(f"{'-'*60}")
    test_scores = [
        "6-3 7-5", "6-4 3-6 7-6(5)", "6-1 6-0", "6-7(3) 6-4 6-3",
        "W/O", "RET", "6-3 4-1 RET", "",
    ]
    for s in test_scores:
        sets, games = parse_score_to_games(s)
        print(f"  '{s}' → sets={sets}, games={games}")

    print(f"\n  Done.\n")
