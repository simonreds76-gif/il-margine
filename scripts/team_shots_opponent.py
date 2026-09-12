"""Fixed opponent-adjusted shots inference. No fitting, network or third-party dependencies.

Feature equations copied from the registered 2026-09-12 research candidate;
parity tests protect the conversion from numpy to the standard library.
"""
from __future__ import annotations
import csv, importlib.util, math, sys
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from itertools import groupby
from football_team_names import football_form_team_key
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('opponent_runtime_publisher', ROOT/'scripts/publish-football-research-picks.py')
PUBLISHER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PUBLISHER)
PRIOR_MATCHES = 8
MIN_HISTORY = 6

def key(value):
    canonical = football_form_team_key(PUBLISHER.team_key(value))
    aliases = {'dep a coruna': 'la coruna', 'atl madrid': 'ath madrid',
               'tsg hoffenheim': 'hoffenheim', 'nottingham forest': "nott m forest",
               'tottenham hotspur': 'tottenham', 'athletic bilbao': 'ath bilbao',
               'deportivo alaves': 'alaves', 'rcd mallorca': 'mallorca',
               'olympique marseille': 'marseille', 'stade rennais': 'rennes',
               'strasbourg alsace': 'strasbourg', 'paderborn 07': 'paderborn',
               'ipswich town': 'ipswich', 'hull city': 'hull', 'west ham united': 'west ham', 'cologne': 'koln'}
    return aliases.get(canonical, canonical)


def market_identity(row):
    return '|'.join([row['date'], row['league'], key(row['home']), key(row['away'])])


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) and n >= 0 else None
    except (ValueError, TypeError):
        return None


def shrunk(values, prior, window=20):
    values = [v for v in values if v is not None][-window:]
    weights = [.93 ** i for i in range(len(values) - 1, -1, -1)]
    return float((sum(v*w for v,w in zip(values,weights)) + PRIOR_MATCHES * prior) / (sum(weights) + PRIOR_MATCHES))


class History:
    def __init__(self):
        self.teams = defaultdict(lambda: deque(maxlen=40))
        self.leagues = defaultdict(lambda: deque(maxlen=1000))
        self.league_sums = defaultdict(float)
        self.league_counts = defaultdict(int)

    def prior(self, league, venue, metric):
        fallback = 13.5 if metric == 'shots' else 5.0
        identity = (league, venue, metric)
        return (self.league_sums[identity] + 50 * fallback) / (self.league_counts[identity] + 50)

    def features(self, fixture, metric, team_venue, asof):
        league = fixture['league']
        other_venue = 'away' if team_venue == 'home' else 'home'
        team = fixture['home'] if team_venue == 'home' else fixture['away']
        opponent = fixture['away'] if team_venue == 'home' else fixture['home']
        own, opp = self.teams[(league, team)], self.teams[(league, opponent)]
        if min(sum(r[metric + '_for'] is not None for r in own), sum(r[metric + '_against'] is not None for r in opp)) < MIN_HISTORY:
            return None
        league_mean = (self.prior(league, 'home', metric) + self.prior(league, 'away', metric)) / 2
        venue_mean = self.prior(league, team_venue, metric)
        attack = shrunk([r[metric + '_for'] for r in own], league_mean)
        defence = shrunk([r[metric + '_against'] for r in opp], league_mean)
        va = shrunk([r[metric + '_for'] for r in own if r['venue'] == team_venue], attack)
        vd = shrunk([r[metric + '_against'] for r in opp if r['venue'] == other_venue], defence)
        shot_mean = (self.prior(league, 'home', 'shots') + self.prior(league, 'away', 'shots')) / 2
        # Residuals were recorded against the opponent's pre-match rating,
        # never recomputed using its later-season strength.
        x = [math.log(attack / league_mean), math.log(defence / league_mean),
             math.log(va / attack), math.log(vd / defence),
             math.log(shrunk([r[metric + '_for'] for r in own], attack, 5) / attack),
             math.log(shrunk([r[metric + '_against'] for r in opp], defence, 5) / defence),
             shrunk([r[metric + '_attack_residual'] for r in own], 0),
             shrunk([r[metric + '_defence_residual'] for r in opp], 0),
             math.log(shrunk([r['shots_for'] for r in own], shot_mean) / shot_mean),
             math.log(shrunk([r['shots_against'] for r in opp], shot_mean) / shot_mean),
             min(14, (date.fromisoformat(fixture['date']) - date.fromisoformat(own[-1]['date'])).days),
             min(14, (date.fromisoformat(fixture['date']) - date.fromisoformat(opp[-1]['date'])).days)]
        return dict(x=x, offset=venue_mean, team=team)

    def update_day(self, rows):
        pending = []
        for row in rows:
            r = dict(row)
            league = r['league']
            opponent = self.teams[(league, key(r['opponent']))]
            for metric in ('shots', 'corners'):
                prior = (self.prior(league, 'home', metric) + self.prior(league, 'away', metric)) / 2
                for suffix, field in [('attack', 'against'), ('defence', 'for')]:
                    expectation = shrunk([p[metric + '_' + field] for p in opponent], prior)
                    actual = r[metric + ('_for' if suffix == 'attack' else '_against')]
                    r[metric + '_' + suffix + '_residual'] = math.log((actual + .5) / (expectation + .5)) if actual is not None else None
            pending.append(r)
        # Batch update: no other fixture on this day can enter today's inputs.
        for r in pending:
            self.teams[(r['league'], key(r['team']))].append(r)
            queue = self.leagues[(r['league'], r['venue'])]
            expired = queue[0] if len(queue) == queue.maxlen else None
            for metric in ('shots', 'corners'):
                identity = (r['league'], r['venue'], metric)
                if expired is not None and expired[metric + '_for'] is not None:
                    self.league_sums[identity] -= expired[metric + '_for']
                    self.league_counts[identity] -= 1
                if r[metric + '_for'] is not None:
                    self.league_sums[identity] += r[metric + '_for']
                    self.league_counts[identity] += 1
            queue.append(r)


def read_base(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    seen = {}
    clean = []
    for r in rows:
        identity = (r['date'], r['league'], key(r['team']))
        for metric in ('shots', 'corners'):
            for side in ('for', 'against'):
                r[metric + '_' + side] = number(r[metric + '_' + side])
        if identity in seen:
            fields = ['venue', 'shots_for', 'shots_against', 'corners_for', 'corners_against', 'goals_for', 'goals_against']
            previous = seen[identity]
            if key(previous['opponent']) != key(r['opponent']) or any(previous[f] != r[f] for f in fields):
                raise ValueError(f'Conflicting duplicate team/day: {identity}')
            continue
        seen[identity] = r
        clean.append(r)
    print('Base rows', len(rows), 'unique', len(clean), 'exact alias duplicates removed', len(rows)-len(clean), flush=True)
    return clean



def mean_for(model, sample):
    terms = [(x-c)/s*b for x,c,s,b in zip(sample['x'],model['centers'],model['scales'],model['beta'][1:])]
    value = math.log(sample['offset']) + model['beta'][0] + sum(terms)
    return math.exp(max(-2, min(5, value)))

def history_before(base, day):
    history = History()
    for when, rows in groupby(sorted(base, key=lambda r:r['date']), key=lambda r:r['date']):
        if when >= day:
            break
        history.update_day(list(rows))
    return history
