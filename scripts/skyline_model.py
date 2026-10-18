"""Skyline v1: isolated headed SOT paper probabilities. No network or fitting here."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from statistics import mean
import math

VARIANTS = ('baseline', 'delivery', 'height', 'combined')
FEATURES = {'baseline': [0], 'delivery': [0, 1, 2], 'height': [0, 3], 'combined': [0, 1, 2, 3]}
POLICY = dict(min_matches=3, min_minutes=180, max_history=20, max_age_days=365,
              prior_minutes=450, prior_headers=20, min_expected_minutes=60,
              min_ev=0.10, min_probability=0.08, min_odds=1.5, max_odds=20,
              paper_units=1, real_units=0, quote_max_age_minutes=120)


def utc(s):
    d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('Timezone missing')
    return d.astimezone(timezone.utc)


def valid(v):
    return type(v) in (float, int) and math.isfinite(v)


def sigmoid(x):
    return 1 / (1 + math.exp(-max(-30, min(30, x))))


class History:
    def __init__(self):
        self.players = defaultdict(list)
        self.teams = defaultdict(list)
        self.leagues = defaultdict(lambda: [0, 0, 0, 0, 0, 0])

    def add(self, match):
        league = self.leagues[str(match['league_id'])]
        for p in match['players']:
            minutes, headers, sot = p.get('minutes'), p.get('headed_shots'), p.get('headed_sot')
            if not valid(minutes) or not 0 < minutes <= 130: continue
            if not valid(headers) or not valid(sot) or not 0 <= sot <= headers: continue
            self.players[str(p['id'])].append({**p, 'date': match['date'], 'fixture_id': str(match['id'])})
            league[0] += minutes; league[1] += headers; league[2] += sot
        for d in match['delivery']:
            self.teams[str(d['team_id'])].append({**d, 'date': match['date']})
            if valid(d.get('corners')) and valid(d.get('crosses_attempted')):
                league[3] += d['corners']; league[4] += d['crosses_attempted']; league[5] += 1

    def features(self, player_id, team_id, league_id, kickoff, height_gap=None):
        # The entire target date is excluded, including matches with unreliable kickoff times.
        cutoff = utc(kickoff)
        rows = [p for p in self.players[str(player_id)]
                if p['date'][:10] < kickoff[:10] and cutoff - utc(p['date']) <= timedelta(days=365)][-20:]
        minutes = sum(p['minutes'] for p in rows)
        if len(rows) < POLICY['min_matches'] or minutes < POLICY['min_minutes']: return None
        if cutoff - utc(rows[-1]['date']) > timedelta(days=60): return None
        starts = [p['minutes'] for p in rows if p.get('starter') is True][-10:]
        if len(starts) < 3: return None
        expected_minutes = min(90, (sum(starts) + 3 * 75) / (len(starts) + 3))
        lg = self.leagues[str(league_id)]
        # Weak starting priors only matter before the league has substantial data.
        global_rate = (lg[1] + 50) / (lg[0] / 90 + 100)
        global_target_rate = (lg[2] + 6) / (lg[1] + 20)
        headers = sum(p['headed_shots'] for p in rows)
        sot = sum(p['headed_sot'] for p in rows)
        rate = (headers + 5 * global_rate) / (minutes / 90 + 5)
        target_rate = (sot + 20 * global_target_rate) / (headers + 20)
        intensity = rate * target_rate * expected_minutes / 90
        p0 = min(.98, max(.001, -math.expm1(-intensity)))
        deliveries = [d for d in self.teams[str(team_id)] if d['date'][:10] < kickoff[:10]
                      and cutoff - utc(d['date']) <= timedelta(days=60)][-5:]
        deliveries = [d for d in deliveries if valid(d.get('corners')) and valid(d.get('crosses_attempted'))]
        delivery_ok = len(deliveries) >= 3
        corner_base = (lg[3] + 50) / (lg[5] + 10)
        cross_base = (lg[4] + 180) / (lg[5] + 10)
        corners = mean(d['corners'] for d in deliveries) if delivery_ok else None
        crosses = mean(d['crosses_attempted'] for d in deliveries) if delivery_ok else None
        features = [math.log(p0 / (1-p0)),
                    math.log((corners+2)/(corner_base+2)) if delivery_ok else 0,
                    math.log((crosses+5)/(cross_base+5)) if delivery_ok else 0,
                    max(-3, min(3, height_gap/10)) if valid(height_gap) else 0]
        return dict(x=features, expected_minutes=expected_minutes, matches=len(rows), minutes=minutes,
                    headers=headers, headed_sot=sot, shrunk_headers_per90=rate,
                    shrunk_sot_per_header=target_rate, poisson_probability=p0,
                    delivery_available=delivery_ok, height_available=valid(height_gap),
                    height_gap_cm=height_gap, corners=corners, crosses=crosses,
                    prior_fixture_ids=[p['fixture_id'] for p in rows], history_latest=rows[-1]['date'])


def height_gap(player_id, opponent_ids, heights):
    own = heights.get(str(player_id), {}).get('height_cm')
    defenders = [heights.get(str(pid), {}) for pid in opponent_ids]
    defenders = [p for p in defenders if p.get('role_group') == 'defenders']
    if not valid(own) or len(defenders) < 3 or any(not valid(p.get('height_cm')) for p in defenders): return None
    return own - mean(p['height_cm'] for p in defenders)


def predict(features, artifact):
    result = {}
    for variant in VARIANTS:
        if variant in ('delivery', 'combined') and not features['delivery_available']: continue
        if variant in ('height', 'combined') and not features['height_available']: continue
        model = artifact['models'][variant]
        result[variant] = sigmoid(model['intercept'] + sum(w*features['x'][i] for i,w in zip(FEATURES[variant],model['weights'])))
    return result


def qualifies(p, odds, expected_minutes):
    return (POLICY['min_odds'] <= odds <= POLICY['max_odds'] and p >= POLICY['min_probability']
            and expected_minutes >= POLICY['min_expected_minutes'] and p*odds-1 >= POLICY['min_ev'])
