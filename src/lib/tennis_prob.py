"""
Tennis match probability from point probabilities p_A, p_B (Klaassen & Magnus style).
p_A = P(A wins point when A serves), p_B = P(B wins point when B serves).
Best-of-3: set 1 A serves first, set 2 B, set 3 A.
"""

from functools import lru_cache


def prob_game(p: float) -> float:
    """P(server wins game) given P(server wins point) = p. Deuce formula: d = p²/(1-2p(1-p))."""
    if p <= 0 or p >= 1:
        return max(0.0, min(1.0, p))
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


def prob_match_best_of_5(p_a: float, p_b: float) -> float:
    """P(A wins best-of-5). Grand Slam format. Serve order: A,B,A,B,A for sets 1-5."""
    s1 = prob_set(p_a, p_b, a_serves_first=True)
    s2 = prob_set(p_a, p_b, a_serves_first=False)
    s3 = prob_set(p_a, p_b, a_serves_first=True)
    s4 = prob_set(p_a, p_b, a_serves_first=False)
    s5 = prob_set(p_a, p_b, a_serves_first=True)
    # A wins 3-0
    p_30 = s1 * s2 * s3
    # A wins 3-1 (A loses one of s1,s2,s3; A must win s4 to close)
    p_31 = (1 - s1) * s2 * s3 * s4 + s1 * (1 - s2) * s3 * s4 + s1 * s2 * (1 - s3) * s4
    # A wins 3-2 (A loses two of s1..s4 only; A must win s5)
    p_32 = (
        (1 - s1) * (1 - s2) * s3 * s4 * s5
        + (1 - s1) * s2 * (1 - s3) * s4 * s5
        + (1 - s1) * s2 * s3 * (1 - s4) * s5
        + s1 * (1 - s2) * (1 - s3) * s4 * s5
        + s1 * (1 - s2) * s3 * (1 - s4) * s5
        + s1 * s2 * (1 - s3) * (1 - s4) * s5
    )
    return p_30 + p_31 + p_32


@lru_cache(maxsize=8192)
def _expected_games_set(a: int, b: int, pa_int: int, pb_int: int, a_serves: bool) -> float:
    """Expected number of games REMAINING in the set from (a,b) to finish. Tiebreak counts as 1 game."""
    p_a = pa_int / 10000.0
    p_b = pb_int / 10000.0
    if a >= 6 and a - b >= 2:
        return 0.0
    if b >= 6 and b - a >= 2:
        return 0.0
    if a == 6 and b == 6:
        return 1.0
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


def expected_total_games_best_of_5(p_a: float, p_b: float) -> float:
    """Expected total games in a best-of-5 match (Grand Slam). Same serve order as prob_match_best_of_5."""
    e_a = expected_games_set(p_a, p_b, a_serves_first=True)
    e_b = expected_games_set(p_a, p_b, a_serves_first=False)
    s1 = prob_set(p_a, p_b, a_serves_first=True)
    s2 = prob_set(p_a, p_b, a_serves_first=False)
    s3 = prob_set(p_a, p_b, a_serves_first=True)
    s4 = prob_set(p_a, p_b, a_serves_first=False)
    s5 = prob_set(p_a, p_b, a_serves_first=True)
    # 3-0: 3 sets (A wins or B wins)
    p_30 = s1 * s2 * s3 + (1 - s1) * (1 - s2) * (1 - s3)
    # 3-1: 4 sets (A wins 3-1 or B wins 1-3)
    p_31_a = (1 - s1) * s2 * s3 * s4 + s1 * (1 - s2) * s3 * s4 + s1 * s2 * (1 - s3) * s4  # A loses 1,2,or 3
    p_31_b = s1 * (1 - s2) * (1 - s3) * (1 - s4) + (1 - s1) * s2 * (1 - s3) * (1 - s4) + (1 - s1) * (1 - s2) * s3 * (1 - s4) + (1 - s1) * (1 - s2) * (1 - s3) * s4  # B loses 1,2,3,or 4
    p_31 = p_31_a + p_31_b
    # 3-2: 5 sets
    p_32 = 1.0 - p_30 - p_31
    e_3 = e_a + e_b + e_a
    e_4 = e_a + e_b + e_a + e_b
    e_5 = e_a + e_b + e_a + e_b + e_a
    return p_30 * e_3 + p_31 * e_4 + p_32 * e_5


# ── O/U game distribution ──────────────────────────────────────────


def _set_outcome_distribution(p_a: float, p_b: float, a_serves_first: bool) -> dict:
    """P(set ends with G total games, A wins/loses) via forward-probability propagation.

    Returns dict mapping (total_games, a_won: bool) -> probability.
    Possible game totals per set: 6,7,8,9,10,12,13 (13 = 7-6 TB counted as 1 game).
    """
    p_a = max(0.01, min(0.99, p_a))
    p_b = max(0.01, min(0.99, p_b))
    pg_a = prob_game(p_a)
    pg_b = prob_game(p_b)

    reach = {(0, 0): 1.0}
    outcomes = {}

    for total in range(13):
        for a in range(min(total + 1, 8)):
            b = total - a
            if b < 0 or b > 7:
                continue
            p_state = reach.get((a, b), 0.0)
            if p_state == 0.0:
                continue

            if a >= 6 and a - b >= 2:
                outcomes[(a + b, True)] = outcomes.get((a + b, True), 0.0) + p_state
                continue
            if b >= 6 and b - a >= 2:
                outcomes[(a + b, False)] = outcomes.get((a + b, False), 0.0) + p_state
                continue
            if a == 6 and b == 6:
                p_tb = prob_tiebreak(p_a, p_b, a_serves_first)
                outcomes[(13, True)] = outcomes.get((13, True), 0.0) + p_state * p_tb
                outcomes[(13, False)] = outcomes.get((13, False), 0.0) + p_state * (1.0 - p_tb)
                continue

            a_serves_this = ((total % 2 == 0) == a_serves_first)
            p_win = pg_a if a_serves_this else (1.0 - pg_b)

            reach[(a + 1, b)] = reach.get((a + 1, b), 0.0) + p_state * p_win
            reach[(a, b + 1)] = reach.get((a, b + 1), 0.0) + p_state * (1.0 - p_win)

    return outcomes


def _match_games_pmf(p_a: float, p_b: float) -> dict:
    """PMF of total games in a best-of-3 match. Returns dict: total_games -> probability."""
    s1 = _set_outcome_distribution(p_a, p_b, a_serves_first=True)
    s2 = _set_outcome_distribution(p_a, p_b, a_serves_first=False)

    def split(dist):
        wins, losses = {}, {}
        for (g, won), p in dist.items():
            (wins if won else losses)[g] = (wins if won else losses).get(g, 0.0) + p
        return wins, losses

    s1w, s1l = split(s1)
    s2w, s2l = split(s2)
    # s3 same as s1 (A serves first)
    s3w, s3l = s1w, s1l

    pmf = {}

    def add(g, p):
        pmf[g] = pmf.get(g, 0.0) + p

    # 2-0 for A: A wins s1, A wins s2
    for g1, p1 in s1w.items():
        for g2, p2 in s2w.items():
            add(g1 + g2, p1 * p2)
    # 0-2 for B: B wins s1, B wins s2
    for g1, p1 in s1l.items():
        for g2, p2 in s2l.items():
            add(g1 + g2, p1 * p2)
    # 2-1 for A (A-B-A)
    for g1, p1 in s1w.items():
        for g2, p2 in s2l.items():
            for g3, p3 in s3w.items():
                add(g1 + g2 + g3, p1 * p2 * p3)
    # 2-1 for A (B-A-A)
    for g1, p1 in s1l.items():
        for g2, p2 in s2w.items():
            for g3, p3 in s3w.items():
                add(g1 + g2 + g3, p1 * p2 * p3)
    # 1-2 for B (A-B-B)
    for g1, p1 in s1w.items():
        for g2, p2 in s2l.items():
            for g3, p3 in s3l.items():
                add(g1 + g2 + g3, p1 * p2 * p3)
    # 1-2 for B (B-A-B)
    for g1, p1 in s1l.items():
        for g2, p2 in s2w.items():
            for g3, p3 in s3l.items():
                add(g1 + g2 + g3, p1 * p2 * p3)

    return pmf


def prob_over_games(p_a: float, p_b: float, line: float) -> float:
    """P(total games in best-of-3 > line). For half-integer lines this is clean;
    for integer lines, exact-on-line is excluded (push)."""
    pmf = _match_games_pmf(p_a, p_b)
    return sum(p for g, p in pmf.items() if g > line)
