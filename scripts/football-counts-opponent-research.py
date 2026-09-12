#!/usr/bin/env python3
"""Offline, causal count-mean research. Never writes live parameters or ledgers.

One registered candidate per market, fitted to counts (not betting profit).
History is frozen before the price capture day for price replay. Same-day
results, untimestamped historical odds, and StatsHub outputs are not inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import nbinom

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from football_team_names import football_form_team_key

FEATURES = ['attack20', 'opponent_concession20', 'venue_attack_delta',
            'opponent_venue_concession_delta', 'attack_recent_delta',
            'opponent_concession_recent_delta', 'opponent_adjusted_attack',
            'opponent_adjusted_concession', 'shot_pressure', 'opponent_shot_pressure',
            'rest_days', 'opponent_rest_days']
PRIOR_MATCHES = 8
RIDGE = 10.0
MIN_HISTORY = 6
TRAIN_BEFORE = '2026-04-01'


def load_audit():
    spec = importlib.util.spec_from_file_location('opponent_audit', ROOT / 'scripts/football-counts-calibration-audit.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PUBLISHER = load_audit().module('opponent_research_publisher', 'publish-football-research-picks.py')


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
    weights = np.power(.93, np.arange(len(values) - 1, -1, -1))
    return float((np.dot(values, weights) + PRIOR_MATCHES * prior) / (weights.sum() + PRIOR_MATCHES))


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


def samples_at(history, fixture, asof, actuals):
    out = {'shots': [], 'corners': []}
    for metric in out:
        home = history.features(fixture, metric, 'home', asof)
        away = history.features(fixture, metric, 'away', asof)
        if metric == 'shots':
            for view in (home, away):
                if view is not None:
                    y = actuals.get((metric, view['team']))
                    if y is not None:
                        out[metric].append(dict(fixture, **view, y=y, asof=asof))
        elif home is not None and away is not None:
            ys = [actuals.get((metric, fixture[t])) for t in ('home', 'away')]
            if all(y is not None for y in ys):
                # Exchangeable total: both teams contribute; asymmetry measures
                # capture uneven attacking strength without arbitrary club IDs.
                x = ((np.asarray(home['x']) + np.asarray(away['x'])) / 2).tolist()
                x.extend([abs(home['x'][0] - away['x'][0]), abs(home['x'][1] - away['x'][1])])
                out[metric].append(dict(fixture, x=x, offset=home['offset'] + away['offset'], team='', y=sum(ys), asof=asof))
    return out


def build_samples(base, markets):
    byday = defaultdict(list)
    fixtures = {}
    for r in base:
        byday[r['date']].append(r)
        ident = '|'.join([r['date'], r['league'], key(r['home_team']), key(r['away_team'])])
        fixture = fixtures.setdefault(ident, dict(date=r['date'], league=r['league'], home=key(r['home_team']), away=key(r['away_team']), fixture=ident, actuals={}))
        for metric in ('shots', 'corners'):
            fixture['actuals'][(metric, key(r['team']))] = r[metric + '_for']
    requests = defaultdict(set)
    for rows in markets.values():
        for r in rows:
            # Conservative when we have only match dates, not result timestamps.
            requests[min(r['date'], r['captured'][:10])].add(market_identity(r))
    history = History()
    counts, prices = {'shots': [], 'corners': []}, {'shots': {}, 'corners': {}}
    fixture_days = defaultdict(list)
    for f in fixtures.values():
        fixture_days[f['date']].append(f)
    for day in sorted(set(byday) | set(requests)):
        for ident in requests[day]:
            if ident not in fixtures:
                continue
            f = fixtures[ident]
            payload = {k: v for k, v in f.items() if k != 'actuals'}
            for metric, samples in samples_at(history, payload, day, f['actuals']).items():
                for s in samples:
                    prices[metric][(ident, s['team'], day)] = s
        for f in fixture_days[day]:
            payload = {k: v for k, v in f.items() if k != 'actuals'}
            for metric, samples in samples_at(history, payload, day, f['actuals']).items():
                counts[metric].extend(samples)
        history.update_day(byday[day])
    return counts, prices


def fit(samples):
    x = np.asarray([s['x'] for s in samples])
    centers, scales = x.mean(axis=0), np.maximum(x.std(axis=0), .01)
    matrix = np.column_stack([np.ones(len(x)), (x - centers) / scales])
    offset = np.log([s['offset'] for s in samples])
    y = np.asarray([s['y'] for s in samples])

    def objective(theta):
        beta, shape = theta[:-1], math.exp(-theta[-1])
        mu = np.exp(np.clip(offset + matrix @ beta, -2, 5))
        ll = gammaln(y + shape) - gammaln(shape) - gammaln(y + 1) + shape * np.log(shape / (shape + mu)) + y * np.log(mu / (shape + mu))
        return float(-ll.sum() + RIDGE * (beta[1:] @ beta[1:]))

    initial = np.zeros(matrix.shape[1] + 1)
    initial[-1] = math.log(.05)
    fitted = minimize(objective, initial, method='L-BFGS-B', bounds=[(-2, 2)] * matrix.shape[1] + [(math.log(.002), math.log(1))], options={'maxiter': 250})
    if not fitted.success:
        raise RuntimeError(f'Count fit failed: {fitted.message}')
    return dict(beta=fitted.x[:-1].tolist(), alpha=math.exp(fitted.x[-1]), centers=centers.tolist(), scales=scales.tolist(), train_n=len(samples), train_last=max(s['date'] for s in samples))


def mean_for(model, sample):
    x = (np.asarray(sample['x']) - model['centers']) / model['scales']
    return float(math.exp(np.clip(math.log(sample['offset']) + model['beta'][0] + x @ model['beta'][1:], -2, 5)))


def count_metrics(model, samples):
    y = np.asarray([s['y'] for s in samples])
    mu = np.asarray([mean_for(model, s) for s in samples])
    baseline = np.asarray([s['offset'] for s in samples])
    return dict(n=len(samples), candidate_mae=float(np.mean(abs(mu-y))), league_venue_mae=float(np.mean(abs(baseline-y))), candidate_bias=float(np.mean(mu-y)), candidate_rmse=float(np.sqrt(np.mean((mu-y)**2))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    base_path = ROOT / 'data/football-form/team-match-base.csv'
    markets = json.loads(args.observations.read_text(encoding='utf8'))
    counts, price_features = build_samples(read_base(base_path), markets)
    print('Causal samples built', {metric: len(rows) for metric, rows in counts.items()}, flush=True)
    audit = load_audit()
    report = dict(status='RESEARCH_ONLY', generated_at=datetime.now(timezone.utc).isoformat(),
                  protocol='One count-likelihood candidate per market. No ROI search. Previously inspected 2026 periods are diagnostic, not fresh holdouts. 1u flat, >=3% EV, max one selection/fixture.',
                  feature_names=dict(shots=FEATURES, corners=FEATURES + ['attack_asymmetry', 'concession_asymmetry']),
                  input_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (base_path, args.observations, Path(__file__))}, models={})
    for metric in ('shots', 'corners'):
        all_samples = counts[metric]
        folds = {}
        for start, stop in [('2024-01-01', '2025-01-01'), ('2025-01-01', '2026-01-01'), (TRAIN_BEFORE, '2027-01-01')]:
            lower = str(int(start[:4]) - 3) + start[4:]
            train = [s for s in all_samples if lower <= s['date'] < start]
            test = [s for s in all_samples if start <= s['date'] < stop]
            model = fit(train)
            folds[start] = dict(training_n=len(train), test=count_metrics(model, test))
            print(metric, start, folds[start], flush=True)
        # Final fit above is frozen before April, including all preprocessing.
        matched, exclusions = [], []
        for row in markets[metric]:
            asof = min(row['date'], row['captured'][:10])
            sample = price_features[metric].get((market_identity(row), key(row['team']), asof))
            if sample is None or asof < TRAIN_BEFORE:
                exclusions.append(dict(fixture=row['fixture'], team=row['team'], asof=asof,
                                       available_teams=sorted({k[1] for k in price_features[metric] if k[0] == market_identity(row) and k[2] == asof}),
                                       reason='before_parameter_freeze' if asof < TRAIN_BEFORE else 'fixture_or_team_history_unavailable'))
                continue
            if sample['y'] != row['actual']:
                raise ValueError(f"Outcome mismatch: {row['fixture']}")
            mu = mean_for(model, sample)
            shape = 1 / model['alpha']
            p = float(nbinom.sf(math.floor(row['line']), shape, shape / (shape + mu)))
            matched.append(dict(row, incumbent_raw=row['raw'], incumbent_mean=row['mean'], raw=p, mean=mu, feature_asof=asof))
        calibration = [r for r in matched if r['date'] < '2026-05-09']
        calibrator = audit.fit_calibrator(calibration)
        phases = {}
        for phase, start, end in [('validation', '2026-05-09', '2026-08-01'), ('historical_diagnostic', '2026-08-01', '2027-01-01')]:
            subset = [r for r in matched if start <= r['date'] < end]
            variants = dict(candidate_raw=lambda r: r['raw'], candidate_calibrated=lambda r: audit.predict(r, calibrator), incumbent_raw=lambda r:r['incumbent_raw'], market=lambda r:r['market'])
            phases[phase] = {name: audit.evaluate(subset, fn) for name, fn in variants.items()}
            print(metric, phase, {name: {k: s.get(k) for k in ('bets','wins','roi','brier')} for name,s in phases[phase].items()}, flush=True)
        report['models'][metric] = dict(parameters=model, calibrator=calibrator, count_folds=folds, market_rows=len(matched), excluded_rows=len(markets[metric])-len(matched), exclusions=exclusions, phases=phases)
    (args.output_dir / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf8')
    print('Saved', args.output_dir / 'report.json', flush=True)


if __name__ == '__main__':
    main()
