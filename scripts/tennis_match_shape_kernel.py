"""Frozen T1 score distribution. Research only; no IO, fitting or live writes."""
from collections import defaultdict
from functools import lru_cache
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.lib import tennis_prob as TP
import handicap_probs as HP

LAMBDA = 0.07801499643481327


@lru_cache(maxsize=256)
def joint(pa, pb):
    if HP.prob_tiebreak is not TP.prob_tiebreak or HP.prob_game is not TP.prob_game:
        raise ValueError('exact tennis probability implementation required; no fallback')
    if not all(math.isfinite(p) and .42 <= p <= .80 for p in (pa, pb)):
        raise ValueError('invalid solved serve probabilities')
    pa, pb = round(pa, 4), round(pb, 4)
    active = {(0, 0, True, 0, 0): .5, (0, 0, False, 0, 0): .5}
    done = defaultdict(float)
    for _ in range(3):
        nxt = defaultdict(float)
        for (sa, sb, server, margin, total), mass in active.items():
            for (a, b), p in HP.set_score_distribution(pa, pb, a_serves_first=server).items():
                weight = mass * p
                if weight < 1e-15:
                    continue
                wa, wb = sa + int(a > b), sb + int(b > a)
                m, t = margin + a - b, total + a + b
                if wa == 2 or wb == 2:
                    done[(wa == 2, m, t)] += weight
                else:
                    nxt[(wa, wb, server if (a + b) % 2 == 0 else not server, m, t)] += weight
        active = nxt
    total = math.fsum(done.values())
    return {key: p / total for key, p in done.items()}


def tilt(q, p_match, coefficient=LAMBDA):
    if not math.isfinite(p_match) or not 0 < p_match < 1:
        raise ValueError('invalid match-winner probability')
    weighted = {key: p * math.exp(-coefficient * (key[2] - (key[1] if key[0] else -key[1])) / 2)
                for key, p in q.items()}
    z = {winner: math.fsum(p for key, p in weighted.items() if key[0] == winner) for winner in (True, False)}
    return {key: p * (p_match if key[0] else 1 - p_match) / z[key[0]] for key, p in weighted.items()}


def marginal(q, index):
    result = defaultdict(float)
    for key, p in q.items():
        result[key[index]] += p
    return dict(result)


def contract(pmf, market, line):
    """Returns first side win/push/loss (Over or player1 + handicap)."""
    delta = (lambda x: x - line) if market == 'total_games' else (lambda x: x + line)
    return tuple(math.fsum(p for x, p in pmf.items() if test(delta(x)))
                 for test in (lambda x: x > 1e-9, lambda x: abs(x) <= 1e-9, lambda x: x < -1e-9))


def complete_score(score):
    """Native winner-first BO3 score only; partial and extended-set scores rejected."""
    import re
    if not isinstance(score, str):
        return None
    clean = re.sub(r'\(\d+\)', '', score.strip())
    if not re.fullmatch(r'\d+-\d+(?:\s+\d+-\d+){1,2}', clean):
        return None
    sets = [tuple(map(int, x.split('-'))) for x in clean.split()]
    wins = losses = 0
    for a, b in sets:
        if wins == 2 or losses == 2 or (max(a,b), min(a,b)) not in {(6,0),(6,1),(6,2),(6,3),(6,4),(7,5),(7,6)}:
            return None
        wins += a > b
        losses += b > a
    if wins != 2 or losses >= 2:
        return None
    return sum(a-b for a,b in sets), sum(a+b for a,b in sets)
