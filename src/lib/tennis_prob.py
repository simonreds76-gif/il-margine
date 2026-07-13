"""
Tennis match probability from point probabilities p_A, p_B (Klaassen & Magnus style).
p_A = P(A wins point when A serves), p_B = P(B wins point when B serves).
Best-of-3: set 1 A serves first, set 2 B, set 3 A.
"""

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ServicePointExpectation:
    """Expected service workload for both players in one match."""

    player_a_points: float
    player_b_points: float
    player_a_games: float
    player_b_games: float
    total_service_games: float


def expected_points_in_service_game(p_server: float) -> float:
    """Expected points played in an advantage game at serve-point probability p."""
    p = max(0.01, min(0.99, p_server))
    q = 1.0 - p
    p_end_4 = p**4 + q**4
    p_end_5 = 4.0 * (p**4 * q + q**4 * p)
    p_end_6 = 10.0 * (p**4 * q**2 + q**4 * p**2)
    p_deuce = 20.0 * p**3 * q**3
    expected_from_deuce = 2.0 / max(1e-12, p * p + q * q)
    return (
        4.0 * p_end_4
        + 5.0 * p_end_5
        + 6.0 * p_end_6
        + p_deuce * (6.0 + expected_from_deuce)
    )


def expected_tiebreak_service_points(
    p_a: float,
    p_b: float,
    a_serves_first: bool = True,
    *,
    max_points: int = 200,
) -> tuple[float, float]:
    """Expected points served by A and B in a standard first-to-seven tiebreak."""
    pa = max(0.01, min(0.99, p_a))
    pb = max(0.01, min(0.99, p_b))
    states: dict[tuple[int, int], float] = {(0, 0): 1.0}
    expected_a = 0.0
    expected_b = 0.0

    for total in range(max_points):
        next_states: dict[tuple[int, int], float] = {}
        for (a, b), reach in states.items():
            if reach <= 0.0 or a + b != total:
                continue
            if (a >= 7 or b >= 7) and abs(a - b) >= 2:
                continue
            a_serves = _tb_server_is_a(total) if a_serves_first else not _tb_server_is_a(total)
            if a_serves:
                expected_a += reach
                p_a_wins_point = pa
            else:
                expected_b += reach
                p_a_wins_point = 1.0 - pb
            next_states[(a + 1, b)] = next_states.get((a + 1, b), 0.0) + reach * p_a_wins_point
            next_states[(a, b + 1)] = next_states.get((a, b + 1), 0.0) + reach * (1.0 - p_a_wins_point)
        states = next_states
        if sum(states.values()) < 1e-12:
            break
    return expected_a, expected_b


@lru_cache(maxsize=16384)
def _expected_service_games_set(
    a: int,
    b: int,
    pa_int: int,
    pb_int: int,
    a_serves: bool,
) -> tuple[float, float, float]:
    """Expected A games, B games and probability of a tiebreak from a set state."""
    if (a >= 6 or b >= 6) and abs(a - b) >= 2:
        return 0.0, 0.0, 0.0
    if a == 6 and b == 6:
        return 0.0, 0.0, 1.0

    p_a = pa_int / 10000.0
    p_b = pb_int / 10000.0
    p_win_game = prob_game(p_a) if a_serves else 1.0 - prob_game(p_b)
    win = _expected_service_games_set(a + 1, b, pa_int, pb_int, not a_serves)
    lose = _expected_service_games_set(a, b + 1, pa_int, pb_int, not a_serves)
    current_a = 1.0 if a_serves else 0.0
    current_b = 0.0 if a_serves else 1.0
    return (
        current_a + p_win_game * win[0] + (1.0 - p_win_game) * lose[0],
        current_b + p_win_game * win[1] + (1.0 - p_win_game) * lose[1],
        p_win_game * win[2] + (1.0 - p_win_game) * lose[2],
    )


def expected_service_points_set(
    p_a: float,
    p_b: float,
    a_serves_first: bool = True,
) -> tuple[float, float, float, float]:
    """Expected service points and service games for A and B in one set."""
    pa = max(0.01, min(0.99, p_a))
    pb = max(0.01, min(0.99, p_b))
    pa_int = int(round(pa * 10000))
    pb_int = int(round(pb * 10000))
    games_a, games_b, p_tiebreak = _expected_service_games_set(
        0,
        0,
        pa_int,
        pb_int,
        a_serves_first,
    )
    tb_a, tb_b = expected_tiebreak_service_points(pa, pb, a_serves_first)
    points_a = games_a * expected_points_in_service_game(pa) + p_tiebreak * tb_a
    points_b = games_b * expected_points_in_service_game(pb) + p_tiebreak * tb_b
    return points_a, points_b, games_a, games_b


def _service_point_expectation_for_order(
    p_a: float,
    p_b: float,
    best_of: int,
    a_serves_first_set_one: bool,
) -> ServicePointExpectation:
    sets_to_win = 3 if best_of >= 5 else 2
    set_count = 5 if sets_to_win == 3 else 3
    starts = [a_serves_first_set_one if index % 2 == 0 else not a_serves_first_set_one for index in range(set_count)]
    set_win_probs = [prob_set(p_a, p_b, start) for start in starts]
    set_workloads = [expected_service_points_set(p_a, p_b, start) for start in starts]

    reach = [1.0] * set_count
    if sets_to_win == 2:
        s1, s2 = set_win_probs[:2]
        reach[2] = s1 * (1.0 - s2) + (1.0 - s1) * s2
    else:
        s1, s2, s3, s4 = set_win_probs[:4]
        reach[3] = 1.0 - (s1 * s2 * s3 + (1.0 - s1) * (1.0 - s2) * (1.0 - s3))
        reach[4] = (
            s1 * s2 * (1.0 - s3) * (1.0 - s4)
            + s1 * (1.0 - s2) * s3 * (1.0 - s4)
            + s1 * (1.0 - s2) * (1.0 - s3) * s4
            + (1.0 - s1) * s2 * s3 * (1.0 - s4)
            + (1.0 - s1) * s2 * (1.0 - s3) * s4
            + (1.0 - s1) * (1.0 - s2) * s3 * s4
        )

    points_a = sum(weight * workload[0] for weight, workload in zip(reach, set_workloads, strict=True))
    points_b = sum(weight * workload[1] for weight, workload in zip(reach, set_workloads, strict=True))
    games_a = sum(weight * workload[2] for weight, workload in zip(reach, set_workloads, strict=True))
    games_b = sum(weight * workload[3] for weight, workload in zip(reach, set_workloads, strict=True))
    return ServicePointExpectation(
        player_a_points=points_a,
        player_b_points=points_b,
        player_a_games=games_a,
        player_b_games=games_b,
        total_service_games=games_a + games_b,
    )


def expected_match_service_points(p_a: float, p_b: float, best_of: int = 3) -> ServicePointExpectation:
    """Expected match service workload, averaged over the unknown first server."""
    first_a = _service_point_expectation_for_order(p_a, p_b, best_of, True)
    first_b = _service_point_expectation_for_order(p_a, p_b, best_of, False)
    return ServicePointExpectation(
        player_a_points=(first_a.player_a_points + first_b.player_a_points) / 2.0,
        player_b_points=(first_a.player_b_points + first_b.player_b_points) / 2.0,
        player_a_games=(first_a.player_a_games + first_b.player_a_games) / 2.0,
        player_b_games=(first_a.player_b_games + first_b.player_b_games) / 2.0,
        total_service_games=(first_a.total_service_games + first_b.total_service_games) / 2.0,
    )


# ── O/U game distribution ──────────────────────────────────────────


def _set_outcome_distribution(p_a: float, p_b: float, a_serves_first: bool) -> dict:
    """Return P(games, A won, A serves first next set) for one set."""
    p_a = max(0.01, min(0.99, p_a))
    p_b = max(0.01, min(0.99, p_b))
    pg_a = prob_game(p_a)
    pg_b = prob_game(p_b)

    reach = {(0, 0): 1.0}
    outcomes = {}

    def add_outcome(games: int, a_won: bool, probability: float) -> None:
        next_a_serves_first = a_serves_first if games % 2 == 0 else not a_serves_first
        key = (games, a_won, next_a_serves_first)
        outcomes[key] = outcomes.get(key, 0.0) + probability

    for total in range(13):
        for a in range(min(total + 1, 8)):
            b = total - a
            if b < 0 or b > 7:
                continue
            p_state = reach.get((a, b), 0.0)
            if p_state == 0.0:
                continue

            if a >= 6 and a - b >= 2:
                add_outcome(a + b, True, p_state)
                continue
            if b >= 6 and b - a >= 2:
                add_outcome(a + b, False, p_state)
                continue
            if a == 6 and b == 6:
                p_tb = prob_tiebreak(p_a, p_b, a_serves_first)
                add_outcome(13, True, p_state * p_tb)
                add_outcome(13, False, p_state * (1.0 - p_tb))
                continue

            a_serves_this = ((total % 2 == 0) == a_serves_first)
            p_win = pg_a if a_serves_this else (1.0 - pg_b)

            reach[(a + 1, b)] = reach.get((a + 1, b), 0.0) + p_state * p_win
            reach[(a, b + 1)] = reach.get((a, b + 1), 0.0) + p_state * (1.0 - p_win)

    return outcomes


def _match_games_pmf_for_first_server(
    p_a: float,
    p_b: float,
    best_of: int,
    a_serves_first: bool,
) -> dict:
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    sets_to_win = best_of // 2 + 1
    states = {(0, 0, 0, a_serves_first): 1.0}
    completed = {}
    set_distributions = {
        True: _set_outcome_distribution(p_a, p_b, True),
        False: _set_outcome_distribution(p_a, p_b, False),
    }

    while states:
        next_states = {}
        for (sets_a, sets_b, total_games, next_a_serves), state_probability in states.items():
            if sets_a == sets_to_win or sets_b == sets_to_win:
                completed[total_games] = completed.get(total_games, 0.0) + state_probability
                continue

            set_distribution = set_distributions[next_a_serves]
            for (set_games, a_won, following_a_serves), set_probability in set_distribution.items():
                key = (
                    sets_a + int(a_won),
                    sets_b + int(not a_won),
                    total_games + set_games,
                    following_a_serves,
                )
                next_states[key] = next_states.get(key, 0.0) + state_probability * set_probability
        states = next_states

    total_probability = sum(completed.values())
    if total_probability <= 0.0:
        raise RuntimeError("total-games PMF has no probability mass")
    return {games: probability / total_probability for games, probability in completed.items()}


def match_games_pmf(
    p_a: float,
    p_b: float,
    best_of: int = 3,
    average_first_server: bool = True,
) -> dict:
    """PMF of match total games with serve order propagated across sets."""
    p_a = int(round(max(0.01, min(0.99, p_a)) * 10000)) / 10000.0
    p_b = int(round(max(0.01, min(0.99, p_b)) * 10000)) / 10000.0
    first_a = _match_games_pmf_for_first_server(p_a, p_b, best_of, True)
    if not average_first_server:
        return first_a
    first_b = _match_games_pmf_for_first_server(p_a, p_b, best_of, False)
    games = set(first_a) | set(first_b)
    return {
        total: 0.5 * first_a.get(total, 0.0) + 0.5 * first_b.get(total, 0.0)
        for total in games
    }


def _match_games_pmf(p_a: float, p_b: float) -> dict:
    """Backward-compatible best-of-3 PMF wrapper."""
    return match_games_pmf(p_a, p_b, best_of=3)


def over_push_under_from_pmf(pmf: dict, line: float) -> tuple[float, float, float]:
    """Return full over, push and under probabilities at a totals line."""
    p_over = sum(probability for games, probability in pmf.items() if games > line + 1e-9)
    p_push = sum(probability for games, probability in pmf.items() if abs(games - line) <= 1e-9)
    p_under = sum(probability for games, probability in pmf.items() if games < line - 1e-9)
    total = p_over + p_push + p_under
    if total <= 0.0:
        raise RuntimeError("total-games probabilities have no mass")
    return p_over / total, p_push / total, p_under / total


def over_push_under_games(
    p_a: float,
    p_b: float,
    line: float,
    best_of: int = 3,
) -> tuple[float, float, float]:
    return over_push_under_from_pmf(match_games_pmf(p_a, p_b, best_of=best_of), line)


def fair_total_prices(p_over: float, p_push: float, p_under: float) -> tuple[float, float]:
    """Return refund-aware fair decimal prices for over and under."""
    active_mass = max(0.0, 1.0 - p_push)
    if active_mass <= 0.0 or p_over <= 0.0 or p_under <= 0.0:
        raise ValueError("over and under probabilities must both be positive")
    return active_mass / p_over, active_mass / p_under


def expected_total_games_from_pmf(pmf: dict) -> float:
    return sum(float(games) * probability for games, probability in pmf.items())


def prob_over_games(p_a: float, p_b: float, line: float, best_of: int = 3) -> float:
    """P(total games > line); exact integer-line outcomes are pushes."""
    p_over, _, _ = over_push_under_games(p_a, p_b, line, best_of=best_of)
    return p_over
