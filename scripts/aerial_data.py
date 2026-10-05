"""Aerial Matchup: descriptive prior-match statistics, never betting probabilities."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import gzip
import json
import math

ROOT = Path(__file__).resolve().parents[1]
LEAGUES = {'47': ('epl', 'Premier League', 20), '53': ('ligue-1', 'Ligue 1', 18),
           '54': ('bundesliga', 'Bundesliga', 18), '55': ('serie-a', 'Serie A', 20), '87': ('la-liga', 'La Liga', 20)}

def utc(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    return dt.astimezone(timezone.utc)

def read(path, default=None):
    if not path.exists():
        return default
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(gzip.compress(body, mtime=0) if path.suffix == '.gz' else body)
    tmp.replace(path)

def number(v):
    return type(v) in (int, float) and math.isfinite(v)

def player_history(rows):
    rows = rows[:10]
    duel = [r for r in rows if number(r.get('aerials_won')) and number(r.get('aerials_attempted'))
            and 0 <= r['aerials_won'] <= r['aerials_attempted']]
    headers = [r for r in rows if number(r.get('headed_shots'))]
    won = sum(r['aerials_won'] for r in duel)
    attempts = sum(r['aerials_attempted'] for r in duel)
    minutes = sum(r['minutes'] for r in rows)
    head_minutes = sum(r['minutes'] for r in headers)
    return dict(matches=len(rows), minutes=minutes, duel_matches=len(duel), aerial_won=won,
                aerial_attempts=attempts, aerial_win_pct=round(100*won/attempts, 1) if attempts else None,
                head_matches=len(headers), head_minutes=head_minutes,
                headed_shots=sum(r['headed_shots'] for r in headers),
                headers_per90=round(90*sum(r['headed_shots'] for r in headers)/head_minutes, 2)
                if len(headers) >= 3 and head_minutes >= 270 else None,
                small_sample=len(rows) < 5 or minutes < 450 or attempts < 20,
                appearances=[dict(fixture_id=r['fixture_id'], date=r['date'][:10], match=r['match'],
                                  minutes=r['minutes'], won=r.get('aerials_won'), attempts=r.get('aerials_attempted'),
                                  headed_shots=r.get('headed_shots')) for r in rows])

def team_history(rows, team_id):
    rows = [r for r in rows if team_id in (r['home_id'], r['away_id'])][:5]
    result = {}
    for label, stat in [('corners', 'corners'), ('crosses', 'crosses_attempted')]:
        values = [t[stat] for r in rows for t in r['delivery'] if t['team_id'] == team_id and number(t.get(stat))]
        result[label] = dict(average=round(sum(values)/len(values), 1) if values else None, matches=len(values))
    return result

def height_summary(players):
    values = [p['height_cm'] for p in players if p['role'] != 'GK' and number(p['height_cm'])]
    full = len(values) == 10 and sum(p['role'] != 'GK' for p in players) == 10
    return dict(known=len(values), total=10, mean_cm=round(sum(values)/10, 1) if full else None,
                tallest_three_mean_cm=round(sum(sorted(values)[-3:])/3, 1) if full else None,
                at_least_185=sum(v >= 185 for v in values) if full else None)

def make_fixture(row, lineup, matches, heights, now):
    kickoff = utc(row['date'])
    f = dict(id=row['id'], competition=row['league'], kickoff=row['date'], source_url=row['match_url'],
             state='pending', observed_at=None, valid_until=row['date'], teams=[])
    state = (lineup or {}).get('lineup_type')
    observed = (lineup or {}).get('observed_at')
    valid = False
    if state in ('standard', 'predicted') and observed:
        seen = utc(observed)
        # Freshness is based on source observation, never the publishing time.
        expiry = min(kickoff, seen + timedelta(hours=2 if state == 'standard' else 30))
        valid = seen <= now + timedelta(minutes=5) and now < expiry
        f.update(observed_at=observed, valid_until=expiry.isoformat(), state=('confirmed' if state == 'standard' else 'expected') if valid else 'stale')
    prior = sorted([m for m in matches if m['id'] != row['id'] and m['date'][:10] < row['date'][:10]], key=lambda m: m['date'], reverse=True)
    windows = {'recent': prior, 'current': [m for m in prior if m['season'] == row['season']],
               'previous': [m for m in prior if m['season'] != row['season']]}
    by_player = {}
    for key, rows in windows.items():
        index = defaultdict(list)
        for m in rows:
            for p in m['players']:
                if number(p.get('minutes')) and p['minutes'] > 0:
                    index[p['id']].append({**p, 'fixture_id': m['id'], 'date': m['date'], 'match': m['home']+' v '+m['away']})
        by_player[key] = index
    all_ids = set()
    for side in ('home', 'away'):
        team_id = row[side+'_id']
        team = dict(id=team_id, name=row[side], formation=(lineup or {}).get(side+'_formation', ''), players=[],
                    histories={key: team_history(rows, team_id) for key, rows in windows.items()})
        raw = (lineup or {}).get(side+'_starters', []) if valid else []
        if valid:
            ids = [str(p.get('player_id', '')) for p in raw]
            if (len(ids) != 11 or len(set(ids)) != 11 or any(not x.isdigit() for x in ids)
                    or all_ids.intersection(ids) or str(lineup.get(side+'_fotmob_team_id')) != team_id):
                raise ValueError('Invalid fixture/player identity or incomplete XI: '+row['id'])
            if str(lineup.get('fotmob_match_id')) != row['id'] or utc(lineup['kickoff_utc']) != kickoff:
                raise ValueError('Fixture or kickoff mismatch')
            all_ids.update(ids)
        for p in raw:
            pid = str(p['player_id']); h = heights.get(pid, {})
            pos = str(h.get('positions') or '')
            role = {'keepers':'GK','defenders':'DEF','midfielders':'MID','attackers':'ATT','forwards':'ATT'}.get(h.get('role_group'),'UNK')
            if role == 'UNK':
                primary = pos.split(',')[0].strip()
                role = 'GK' if primary=='GK' else 'DEF' if primary in ('CB','LB','RB','LWB','RWB') else 'MID' if primary in ('CM','DM','AM','LM','RM','CAM','CDM') else 'ATT' if primary in ('ST','CF','LW','RW') else 'UNK'
            # Existing collector explicitly assigns the keeper role score 0 and line_size 1.
            if p.get('line_index') == -1 and p.get('line_size') == 1:
                role = 'GK'
            height = h.get('height_cm')
            height = height if number(height) and 130 <= height <= 230 and h.get('status') != 'held' else None
            team['players'].append(dict(id=pid, name=p['name'], role=role, height_cm=height,
                height_source=h.get('source_url'), height_observed_at=h.get('observed_at'),
                photo_url=f'https://images.fotmob.com/image_resources/playerimages/{pid}.png',
                histories={key: player_history(index.get(pid, [])) for key, index in by_player.items()}))
        if valid and sum(p['role'] == 'GK' for p in team['players']) != 1:
            raise ValueError('Goalkeeper identity missing or duplicated')
        team['height'] = height_summary(team['players'])
        f['teams'].append(team)
    return f

def build(root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    data = root/'data/aerial'
    calendar = read(data/'calendar.json.gz')
    matches = read(data/'history.json.gz')['matches']
    heights = read(data/'heights.json.gz')
    if len({m['id'] for m in matches}) != len(matches):
        raise ValueError('Duplicate history fixtures')
    lineups = {}
    for slug, _, _ in LEAGUES.values():
        filename = 'confirmed-lineups.json' if slug == 'serie-a' else slug+'-confirmed-lineups.json'
        for f in read(root/'data/goalscorer'/filename, {}).get('fixtures', []):
            mid = str(f.get('fotmob_match_id'))
            if mid in lineups:
                raise ValueError('Duplicate live fixture')
            lineups[mid] = f
    fixtures, exclusions = [], []
    for row in calendar['fixtures']:
        if row['disposition'] != 'not_completed' or not now < utc(row['date']) <= now + timedelta(days=8):
            continue
        try:
            fixtures.append(make_fixture(row, lineups.get(row['id']), matches, heights, now))
        except (ValueError, KeyError) as exc:
            exclusions.append(dict(id=row['id'], reason=str(exc)))
            fixtures.append(make_fixture(row, None, matches, heights, now))
    fixtures.sort(key=lambda f: f['kickoff'])
    payload = dict(schema_version=1, generated_at=now.isoformat(), calendar_observed_at=calendar['observed_at'],
        history_through=max(m['date'] for m in matches), history_matches=len(matches),
        seasons=sorted({m['season'] for m in matches}, reverse=True), fixtures=fixtures, exclusions=exclusions)
    payload['version'] = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    validate(payload, now)
    return payload

def validate(payload, now=None):
    now = now or datetime.now(timezone.utc)
    if payload.get('schema_version') != 1 or not isinstance(payload.get('fixtures'), list):
        raise ValueError('Invalid Aerial schema')
    if abs((now-utc(payload['generated_at'])).total_seconds()) > 1800:
        raise ValueError('Build is not current')
    if now-utc(payload['calendar_observed_at']) > timedelta(hours=36):
        raise ValueError('Fixture calendar is stale; retaining the last public snapshot')
    seen = set()
    for f in payload['fixtures']:
        if f['id'] in seen or len(f['teams']) != 2 or utc(f['kickoff']) <= now:
            raise ValueError('Invalid upcoming fixture')
        seen.add(f['id'])
        for t in f['teams']:
            for p in t['players']:
                for s in p['histories'].values():
                    if any(r['date'] >= f['kickoff'][:10] or r['fixture_id'] == f['id'] for r in s['appearances']):
                        raise ValueError('Future or target-match history leaked into comparison')
    if len(json.dumps(payload).encode()) > 4_000_000:
        raise ValueError('Public board exceeds 4 MB budget')
    return True

