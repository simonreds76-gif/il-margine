"""
Handicap / Game Margin Probabilities — handicap_probs.py
=========================================================
Extends the K-M recursion to compute:

  1. Game margin distribution: P(games_A - games_B = k) for all k
  2. P(dog covers +N.5 games) — for handicap betting
  3. P(straight sets) and P(match goes to 3 sets)
  4. P(favourite covers -N.5 games)
  5. Expected game margin

Uses the same p_a/p_b point probabilities as the match winner model.
No new data needed — pure maths on top of existing serve stats.

Usage:
  from handicap_probs import (
      game_margin_pmf_bo3, prob_dog_covers, prob_straight_sets,
      expected_game_margin, handicap_value
  )

  # Same p_a, p_b from the matchup model
  p_a, p_b = 0.65, 0.60

  # Full margin distribution
  pmf = game_margin_pmf_bo3(p_a, p_b)  # dict: margin → probability

  # Handicap checks
  p_cover = prob_dog_covers(p_a, p_b, line=4.5)  # P(dog loses by <4.5 games)
  p_ss = prob_straight_sets(p_a, p_b)              # P(favourite wins in 2 sets)
  margin = expected_game_margin(p_a, p_b)          # E[games_A - games_B]

  # Compare to Pinnacle handicap line
  val = handicap_value(p_a, p_b, line=4.5, pinnacle_odds=1.95)
"""

from functools import lru_cache
from typing import Dict, Tuple

try:
    from src.lib.tennis_prob import prob_game, prob_tiebreak
except ImportError:
    def prob_game(p: float) -> float:
        if p <= 0 or p >= 1:
            return max(0.0, min(1.0, p))
        d = (p * p) / (1.0 - 2.0 * p * (1.0 - p))
        return p**4 + 4 * p**4 * (1 - p) + 10 * p**4 * (1 - p)**2 + 20 * p**3 * (1 - p)**3 * d

    def prob_tiebreak(p_a: float, p_b: float, a_serves_first: bool = True) -> float:
        p = p_a if a_serves_first else (1 - p_b)
        q = (1 - p_a) if a_serves_first else p_b
        return p / (p + q) if (p + q) > 0 else 0.5


# ══════════════════════════════════════════════════════════════════════════════
# Set outcome distribution: P(set ends A-B games) for all valid (A,B) scores
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=16384)
def _set_score_probs(pa_int: int, pb_int: int, a_serves_first: bool) -> Tuple[Tuple[Tuple[int, int, float], ...], ...]:
    """
    Compute probability of each possible set score (a, b).

    Valid final scores for a set:
      6-0, 6-1, 6-2, 6-3, 6-4 (A wins without tiebreak)
      0-6, 1-6, 2-6, 3-6, 4-6 (B wins without tiebreak)
      7-5, 5-7 (after 5-5, one player wins two in a row)
      7-6, 6-7 (tiebreak at 6-6)

    Returns tuple of (a_games, b_games, probability).
    Uses DP on the game-by-game tree.
    """
    p_a = pa_int / 10000.0
    p_b = pb_int / 10000.0

    max_games = 14

    dp: Dict[Tuple[int, int, bool], float] = {}
    dp[(0, 0, a_serves_first)] = 1.0

    results: list[Tuple[int, int, float]] = []

    for total in range(0, max_games + 1):
        for a in range(0, min(total + 1, 8)):
            b = total - a
            if b < 0 or b > 7:
                continue

            for serving in [True, False]:
                prob = dp.get((a, b, serving), 0.0)
                if prob < 1e-15:
                    continue

                if a >= 6 and a - b >= 2:
                    results.append((a, b, prob))
                    continue
                if b >= 6 and b - a >= 2:
                    results.append((a, b, prob))
                    continue
                if a == 7 and b == 6:
                    results.append((a, b, prob))
                    continue
                if a == 6 and b == 7:
                    results.append((a, b, prob))
                    continue

                if a == 6 and b == 6:
                    p_tb = prob_tiebreak(p_a, p_b, serving)
                    results.append((7, 6, prob * p_tb))
                    results.append((6, 7, prob * (1.0 - p_tb)))
                    continue

                p_game_a = prob_game(p_a)
                p_game_b = prob_game(p_b)
                if serving:
                    p_win = p_game_a
                else:
                    p_win = 1.0 - p_game_b

                next_serving = not serving
                key_a = (a + 1, b, next_serving)
                dp[key_a] = dp.get(key_a, 0.0) + prob * p_win
                key_b = (a, b + 1, next_serving)
                dp[key_b] = dp.get(key_b, 0.0) + prob * (1.0 - p_win)

    score_probs: Dict[Tuple[int, int], float] = {}
    for a, b, p in results:
        score_probs[(a, b)] = score_probs.get((a, b), 0.0) + p

    return tuple((a, b, p) for (a, b), p in sorted(score_probs.items()))


def set_score_distribution(p_a: float, p_b: float, a_serves_first: bool = True) -> Dict[Tuple[int, int], float]:
    """
    P(set ends with score (a, b)) for all valid final scores.
    Returns dict: (games_A, games_B) → probability.
    """
    pa_int = int(round(max(0.01, min(0.99, p_a)) * 10000))
    pb_int = int(round(max(0.01, min(0.99, p_b)) * 10000))
    raw = _set_score_probs(pa_int, pb_int, a_serves_first)
    return {(a, b): p for a, b, p in raw}


# ══════════════════════════════════════════════════════════════════════════════
# Match outcome distribution (bo3): joint over set scores
# ══════════════════════════════════════════════════════════════════════════════

def match_outcome_distribution_bo3(p_a: float, p_b: float) -> Dict[Tuple[Tuple[int, int], ...], float]:
    """
    Full match outcome distribution for best-of-3.
    Returns dict: ((set1_a, set1_b), (set2_a, set2_b), ...) → probability.

    Set 1: A serves first. Set 2: B serves first. Set 3: A serves first.
    """
    set1_dist = set_score_distribution(p_a, p_b, a_serves_first=True)
    set2_dist = set_score_distribution(p_a, p_b, a_serves_first=False)
    set3_dist = set_score_distribution(p_a, p_b, a_serves_first=True)

    outcomes: Dict[Tuple[Tuple[int, int], ...], float] = {}

    for (s1a, s1b), p1 in set1_dist.items():
        if p1 < 1e-12:
            continue
        a_won_s1 = s1a > s1b

        for (s2a, s2b), p2 in set2_dist.items():
            if p2 < 1e-12:
                continue
            a_won_s2 = s2a > s2b
            p12 = p1 * p2

            if a_won_s1 and a_won_s2:
                key = ((s1a, s1b), (s2a, s2b))
                outcomes[key] = outcomes.get(key, 0.0) + p12
            elif not a_won_s1 and not a_won_s2:
                key = ((s1a, s1b), (s2a, s2b))
                outcomes[key] = outcomes.get(key, 0.0) + p12
            else:
                for (s3a, s3b), p3 in set3_dist.items():
                    if p3 < 1e-12:
                        continue
                    key = ((s1a, s1b), (s2a, s2b), (s3a, s3b))
                    outcomes[key] = outcomes.get(key, 0.0) + p12 * p3

    return outcomes


# ══════════════════════════════════════════════════════════════════════════════
# Game margin distribution
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=4096)
def _game_margin_pmf_cached(pa_int: int, pb_int: int) -> tuple:
    """Cached by quantized p_a, p_b (int = round * 10000)."""
    p_a = pa_int / 10000.0
    p_b = pb_int / 10000.0
    outcomes = match_outcome_distribution_bo3(p_a, p_b)
    margin_pmf: Dict[int, float] = {}
    for sets, prob in outcomes.items():
        total_a = sum(s[0] for s in sets)
        total_b = sum(s[1] for s in sets)
        margin = total_a - total_b
        margin_pmf[margin] = margin_pmf.get(margin, 0.0) + prob
    return tuple(sorted(margin_pmf.items()))


def game_margin_pmf_bo3(p_a: float, p_b: float) -> Dict[int, float]:
    """
    PMF of game margin (games_A - games_B) for a best-of-3 match.
    Positive margin = A won more games. Negative = B won more.

    Returns dict: margin → probability.
    """
    pa_int = int(round(max(0.01, min(0.99, p_a)) * 10000))
    pb_int = int(round(max(0.01, min(0.99, p_b)) * 10000))
    cached = _game_margin_pmf_cached(pa_int, pb_int)
    return dict(cached)


def _best_of_sets(best_of: str | int) -> int:
    text = str(best_of).strip().lower()
    if text in {"5", "bo5", "best_of_5", "best-of-5"}:
        return 5
    if text in {"3", "bo3", "best_of_3", "best-of-3"}:
        return 3
    raise ValueError(f"Unsupported best_of value: {best_of!r}")


@lru_cache(maxsize=8192)
def _match_outcome_pmf_cached(pa_int: int, pb_int: int, best_of: int) -> tuple:
    """Aggregate match margins and winner while carrying the next server."""
    p_a = pa_int / 10000.0
    p_b = pb_int / 10000.0
    sets_to_win = best_of // 2 + 1
    # The pricing rows do not identify the first server. Averaging both possible
    # starters avoids giving Player A a hidden serving-order advantage.
    active: Dict[Tuple[int, int, bool, int], float] = {
        (0, 0, True, 0): 0.5,
        (0, 0, False, 0): 0.5,
    }
    completed: Dict[Tuple[int, bool], float] = {}

    for _ in range(best_of):
        next_active: Dict[Tuple[int, int, bool, int], float] = {}
        for (sets_a, sets_b, a_serves_next, margin), state_prob in active.items():
            set_dist = set_score_distribution(
                p_a,
                p_b,
                a_serves_first=a_serves_next,
            )
            for (games_a, games_b), set_prob in set_dist.items():
                probability = state_prob * set_prob
                if probability < 1e-15:
                    continue
                next_sets_a = sets_a + int(games_a > games_b)
                next_sets_b = sets_b + int(games_b > games_a)
                next_margin = margin + games_a - games_b
                if next_sets_a == sets_to_win or next_sets_b == sets_to_win:
                    outcome = (next_margin, next_sets_a == sets_to_win)
                    completed[outcome] = (
                        completed.get(outcome, 0.0) + probability
                    )
                    continue
                next_server = (
                    a_serves_next
                    if (games_a + games_b) % 2 == 0
                    else not a_serves_next
                )
                key = (next_sets_a, next_sets_b, next_server, next_margin)
                next_active[key] = next_active.get(key, 0.0) + probability
        active = next_active

    total = sum(completed.values())
    if total <= 0:
        raise RuntimeError("Match-margin PMF has no probability mass")
    return tuple(
        (margin, player_a_won, probability / total)
        for (margin, player_a_won), probability in sorted(completed.items())
    )


def match_margin_pmf(
    p_a: float,
    p_b: float,
    best_of: str | int = "bo3",
) -> Dict[int, float]:
    """Return P(games_A - games_B) for a BO3 or BO5 match."""
    pa_int = int(round(max(0.01, min(0.99, p_a)) * 10000))
    pb_int = int(round(max(0.01, min(0.99, p_b)) * 10000))
    margin_pmf: Dict[int, float] = {}
    for margin, _, probability in _match_outcome_pmf_cached(
        pa_int,
        pb_int,
        _best_of_sets(best_of),
    ):
        margin_pmf[margin] = margin_pmf.get(margin, 0.0) + probability
    return margin_pmf


@lru_cache(maxsize=16384)
def _match_win_probability_cached(
    pa_int: int,
    pb_int: int,
    best_of: int,
) -> float:
    """Fast match-win recursion used by the reverse point-probability solver."""
    p_a = pa_int / 10000.0
    p_b = pb_int / 10000.0
    sets_to_win = best_of // 2 + 1
    active: Dict[Tuple[int, int, bool], float] = {
        (0, 0, True): 0.5,
        (0, 0, False): 0.5,
    }
    player_a_wins = 0.0

    for _ in range(best_of):
        next_active: Dict[Tuple[int, int, bool], float] = {}
        for (sets_a, sets_b, a_serves_next), state_prob in active.items():
            for (games_a, games_b), set_prob in set_score_distribution(
                p_a,
                p_b,
                a_serves_first=a_serves_next,
            ).items():
                probability = state_prob * set_prob
                next_sets_a = sets_a + int(games_a > games_b)
                next_sets_b = sets_b + int(games_b > games_a)
                if next_sets_a == sets_to_win:
                    player_a_wins += probability
                    continue
                if next_sets_b == sets_to_win:
                    continue
                next_server = (
                    a_serves_next
                    if (games_a + games_b) % 2 == 0
                    else not a_serves_next
                )
                key = (next_sets_a, next_sets_b, next_server)
                next_active[key] = next_active.get(key, 0.0) + probability
        active = next_active
    return player_a_wins


def match_win_probability(
    p_a: float,
    p_b: float,
    best_of: str | int = "bo3",
) -> float:
    """Return P(Player A wins the match) for a BO3 or BO5 match."""
    pa_int = int(round(max(0.01, min(0.99, p_a)) * 10000))
    pb_int = int(round(max(0.01, min(0.99, p_b)) * 10000))
    return _match_win_probability_cached(
        pa_int,
        pb_int,
        _best_of_sets(best_of),
    )


def cover_probs(
    pmf: Dict[int, float],
    line: float,
) -> Tuple[float, float, float]:
    """Return explicit win, push and loss probabilities for player A +line."""
    p_win = p_push = p_loss = 0.0
    for margin, probability in pmf.items():
        adjusted_margin = float(margin) + float(line)
        if adjusted_margin > 1e-9:
            p_win += probability
        elif adjusted_margin < -1e-9:
            p_loss += probability
        else:
            p_push += probability
    total = p_win + p_push + p_loss
    if total <= 0:
        raise ValueError("Cannot price an empty margin PMF")
    return p_win / total, p_push / total, p_loss / total


def p_cover_conditional(
    pmf: Dict[int, float],
    line: float,
) -> float:
    """Return the two-way fair cover probability conditional on no push."""
    p_win, p_push, _ = cover_probs(pmf, line)
    non_push = 1.0 - p_push
    return p_win / non_push if non_push > 1e-12 else 0.5


# ══════════════════════════════════════════════════════════════════════════════
# Handicap probabilities
# ══════════════════════════════════════════════════════════════════════════════

def prob_dog_covers(p_a: float, p_b: float, line: float = 4.5) -> float:
    """
    P(dog covers +line games).
    Dog is player B (assumed weaker). Covers if B loses by fewer than 'line' games.
    i.e. P(games_A - games_B < line).

    Example: line=4.5 → P(B loses by 4 or fewer games).
    """
    pmf = game_margin_pmf_bo3(p_a, p_b)
    return sum(p for margin, p in pmf.items() if margin < line)


def prob_fav_covers(p_a: float, p_b: float, line: float = -4.5) -> float:
    """
    P(favourite covers -line games).
    Favourite is player A. Covers if A wins by more than abs(line) games.
    i.e. P(games_A - games_B > abs(line)).

    Example: line=-4.5 → P(A wins by 5+ games).
    """
    pmf = game_margin_pmf_bo3(p_a, p_b)
    threshold = abs(line)
    return sum(p for margin, p in pmf.items() if margin > threshold)


def prob_straight_sets(p_a: float, p_b: float) -> float:
    """P(match ends in straight sets — either player wins 2-0)."""
    outcomes = match_outcome_distribution_bo3(p_a, p_b)
    return sum(p for sets, p in outcomes.items() if len(sets) == 2)


def prob_a_straight_sets(p_a: float, p_b: float) -> float:
    """P(player A wins in straight sets)."""
    outcomes = match_outcome_distribution_bo3(p_a, p_b)
    return sum(
        p for sets, p in outcomes.items()
        if len(sets) == 2 and sets[0][0] > sets[0][1]
    )


def prob_three_sets(p_a: float, p_b: float) -> float:
    """P(match goes to 3 sets)."""
    return 1.0 - prob_straight_sets(p_a, p_b)


def expected_game_margin(p_a: float, p_b: float) -> float:
    """E[games_A - games_B]. Positive = A expected to win more games."""
    pmf = game_margin_pmf_bo3(p_a, p_b)
    return sum(margin * prob for margin, prob in pmf.items())


def prob_p1_covers_plus(
    p_a: float,
    p_b: float,
    line: float,
    best_of: str | int = "bo3",
) -> float:
    """
    Two-way fair P(P1 covers +line), conditional on an integer-line non-push.

    Kept for compatibility. New code should call match_margin_pmf(),
    cover_probs() and p_cover_conditional() explicitly.
    """
    pmf = match_margin_pmf(p_a, p_b, best_of=best_of)
    return p_cover_conditional(pmf, line)


def prob_p2_covers_minus(p_a: float, p_b: float, line: float) -> float:
    """
    P(P2 covers -line). P2 -line means we subtract line from P2's games.
    Covers if (games_P2 - line) > games_P1, i.e. games_P1 - games_P2 < -line.
    With margin = games_P1 - games_P2:
    Returns P(margin < -line). Works for both fav and dog.
    """
    pmf = game_margin_pmf_bo3(p_a, p_b)
    threshold = -line
    return sum(p for m, p in pmf.items() if m < threshold)


def handicap_value(
    p_a: float,
    p_b: float,
    line: float,
    pinnacle_odds: float,
    side: str = "dog",
) -> Dict:
    """
    Compare model handicap probability to Pinnacle handicap odds.

    Parameters:
      p_a, p_b:       serve point win probabilities (from matchup model)
      line:            handicap line (e.g. 4.5 for dog +4.5, -4.5 for fav -4.5)
      pinnacle_odds:   decimal odds from Pinnacle for this side
      side:            "dog" (backing underdog +line) or "fav" (backing favourite -line)

    Returns dict with model_prob, implied_prob, edge, and recommendation.
    """
    if side == "dog":
        model_prob = prob_dog_covers(p_a, p_b, abs(line))
    else:
        model_prob = prob_fav_covers(p_a, p_b, abs(line))

    if pinnacle_odds <= 1:
        return {"error": "invalid odds"}

    implied_prob = 1.0 / pinnacle_odds
    edge = (model_prob - implied_prob) / implied_prob * 100

    return {
        "side": side,
        "line": line,
        "model_prob": round(model_prob, 4),
        "pinnacle_implied": round(implied_prob, 4),
        "edge_pct": round(edge, 2),
        "has_value": edge > 3.0,
        "pinnacle_odds": pinnacle_odds,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Summary for a match: all handicap lines at once
# ══════════════════════════════════════════════════════════════════════════════

def match_handicap_summary(
    p_a: float,
    p_b: float,
    name_a: str = "Player A",
    name_b: str = "Player B",
) -> Dict:
    """
    Full handicap summary for a match.
    Useful for the chatbot / fair-odds page.
    """
    margin = expected_game_margin(p_a, p_b)
    pmf = game_margin_pmf_bo3(p_a, p_b)

    lines: Dict[float, Dict] = {}
    for spread in [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]:
        dog_covers = sum(p for m, p in pmf.items() if m < spread)
        fav_covers = sum(p for m, p in pmf.items() if m > spread)
        lines[spread] = {
            "dog_covers_prob": round(dog_covers, 4),
            "dog_covers_odds": round(1.0 / dog_covers, 2) if dog_covers > 0.01 else 99.0,
            "fav_covers_prob": round(fav_covers, 4),
            "fav_covers_odds": round(1.0 / fav_covers, 2) if fav_covers > 0.01 else 99.0,
        }

    p_ss = prob_straight_sets(p_a, p_b)
    p_a_ss = prob_a_straight_sets(p_a, p_b)
    p_3s = prob_three_sets(p_a, p_b)

    return {
        "expected_margin": round(margin, 2),
        "margin_favour": name_a if margin > 0 else name_b,
        "prob_straight_sets": round(p_ss, 3),
        "prob_a_straight_sets": round(p_a_ss, 3),
        "prob_three_sets": round(p_3s, 3),
        "handicap_lines": lines,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Self-test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  handicap_probs.py - Self-test")
    print("=" * 60)

    print("\n-- Set Score Distribution (p_a=0.65, p_b=0.60) --")
    ssd = set_score_distribution(0.65, 0.60)
    for (a, b), p in sorted(ssd.items(), key=lambda x: -x[1])[:8]:
        print(f"  {a}-{b}: {p:.4f}")
    total = sum(ssd.values())
    print(f"  Total: {total:.6f} (should be ~1.0)")

    print("\n-- Game Margin PMF (p_a=0.65, p_b=0.60) --")
    pmf = game_margin_pmf_bo3(0.65, 0.60)
    print(f"  {'Margin':>8} {'Prob':>8} {'Cumul':>8}")
    cumul = 0.0
    for margin in sorted(pmf.keys()):
        cumul += pmf[margin]
        if pmf[margin] > 0.01:
            print(f"  {margin:>+8d} {pmf[margin]:>8.4f} {cumul:>8.4f}")
    print(f"  Total: {sum(pmf.values()):.6f}")

    print("\n-- Handicap Lines --")
    for pa, pb, label in [(0.65, 0.60, "Close match"), (0.70, 0.58, "Clear fav"), (0.75, 0.55, "Heavy fav")]:
        margin = expected_game_margin(pa, pb)
        p_ss = prob_straight_sets(pa, pb)
        print(f"\n  {label} (p_a={pa}, p_b={pb}):")
        print(f"    Expected margin: {margin:+.2f} games")
        print(f"    P(straight sets): {p_ss:.3f}")
        print(f"    P(3 sets): {1-p_ss:.3f}")
        for line in [2.5, 3.5, 4.5, 5.5]:
            dc = prob_dog_covers(pa, pb, line)
            print(f"    Dog +{line}: {dc:.3f} (fair odds {1/dc:.2f})" if dc > 0.01 else f"    Dog +{line}: <1%")

    print("\n-- Match Summary: Sinner vs Shapovalov --")
    summary = match_handicap_summary(0.70, 0.58, "Sinner", "Shapovalov")
    print(f"  Expected margin: {summary['expected_margin']:+.1f} games ({summary['margin_favour']})")
    print(f"  P(straight sets): {summary['prob_straight_sets']:.1%}")
    print(f"  P(Sinner in straights): {summary['prob_a_straight_sets']:.1%}")
    print(f"  P(3 sets): {summary['prob_three_sets']:.1%}")
    print(f"\n  {'Line':>6} {'Dog covers':>12} {'Fair odds':>10} {'Fav covers':>12} {'Fair odds':>10}")
    for line, data in summary["handicap_lines"].items():
        print(f"  +{line:>4.1f} {data['dog_covers_prob']:>12.3f} {data['dog_covers_odds']:>10.2f} "
              f"{data['fav_covers_prob']:>12.3f} {data['fav_covers_odds']:>10.2f}")

    print("\n-- Value Check --")
    val = handicap_value(0.70, 0.58, line=4.5, pinnacle_odds=1.85, side="dog")
    print(f"  Dog +4.5 @ 1.85: model={val['model_prob']:.3f}, implied={val['pinnacle_implied']:.3f}, "
          f"edge={val['edge_pct']:+.1f}%, value={'YES' if val['has_value'] else 'NO'}")

    val2 = handicap_value(0.70, 0.58, line=4.5, pinnacle_odds=2.10, side="fav")
    print(f"  Fav -4.5 @ 2.10: model={val2['model_prob']:.3f}, implied={val2['pinnacle_implied']:.3f}, "
          f"edge={val2['edge_pct']:+.1f}%, value={'YES' if val2['has_value'] else 'NO'}")

    print("\n  Done.\n")
