"""Build a static upcoming-fixture board from verified Atlas history and current rosters.

No odds requests, bets or notifications. League/roster requests are bounded and
cached privately; a failed calendar validation leaves the last snapshot intact.
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import requests
from football_atlas_update import normal, dt
from settlement_utils import normalize_team_name

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
LEAGUES = {'premier-league': 47, 'serie-a': 55, 'la-liga': 87, 'bundesliga': 54, 'ligue-1': 53}
POLICY = 'atlas-fixtures-v1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def encoded(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(encoded(data))
    tmp.replace(path)


def league_fixtures(payload, league, now, aliases, teams, days=21):
    if int(payload.get('details', {}).get('id', -1)) != LEAGUES[league]:
        raise ValueError('League identity mismatch: ' + league)
    matches = payload.get('fixtures', {}).get('allMatches', [])
    if len(matches) < 200:
        raise ValueError('Incomplete fixture calendar: ' + league)
    known = {normal(name): name for name in teams}
    result = []
    for m in matches:
        status = m.get('status', {})
        if any(status.get(key) for key in ('finished', 'started', 'cancelled', 'awarded')):
            continue
        reason = json.dumps(status.get('reason', {})).lower()
        if any(word in reason for word in ('postpon', 'cancel', 'abandon', 'suspend')):
            continue
        if not status.get('utcTime'):
            continue
        kickoff = dt(status['utcTime'])
        if not now < kickoff < now + timedelta(days=days):
            continue
        clubs = []
        for side in ('home', 'away'):
            team = m[side]
            source_name = {'Deportivo A Coruña': 'Deportivo La Coruña'}.get(team['name'], team['name'])
            name = aliases.get(league, {}).get(normal(source_name)) or known.get(normal(source_name))
            if not name:
                matches = {n for n in teams if normalize_team_name(n) == normalize_team_name(source_name)}
                name = next(iter(matches)) if len(matches) == 1 else None
            if name not in teams:
                raise ValueError('Unmapped fixture club: ' + team['name'])
            clubs.append({'name': name, 'providerId': str(team['id'])})
        if clubs[0]['providerId'] == clubs[1]['providerId']:
            raise ValueError('Identical fixture teams')
        result.append({'id': 'fm-' + str(m['id']), 'league': league, 'round': str(m.get('roundName', m.get('round', ''))),
                       'kickoff': kickoff.isoformat(), 'home': clubs[0], 'away': clubs[1]})
    return result


def resolve_manager(payload, team_id, registry, crosswalk, portraits, now):
    if str(payload.get('details', {}).get('id')) != str(team_id):
        raise ValueError('Roster team identity mismatch')
    coaches = [m for g in payload.get('squad', {}).get('squad', []) if g.get('title') == 'coach'
               for m in g.get('members', []) if m.get('role', {}).get('key') == 'coach']
    if len(coaches) != 1:
        return None
    coach = coaches[0]
    candidates = [m for m in registry['managers'] if normal(coach['name']) in
                  {normal(n) for n in [m['name'], *m.get('aliases', [])]}]
    mapped = crosswalk.get(str(coach['id']))
    if mapped:
        candidates = [m for m in registry['managers'] if m['id'] == mapped['managerId']]
        if (normal(coach['name']) not in {normal(n) for n in mapped['names']}
                or mapped.get('birthDate') and mapped['birthDate'] != coach.get('dateOfBirth')):
            candidates = []
    # A reviewed portrait provider ID can disambiguate a shared name, never a fuzzy match.
    if len(candidates) > 1:
        candidates = [m for m in candidates if str(portraits.get(m['id'], {}).get('providerId')) == str(coach['id'])]
    manager = candidates[0] if len(candidates) == 1 else None
    return {'id': manager['id'] if manager else None, 'name': manager['name'] if manager else coach['name'],
            'checkedAt': now.isoformat(), 'status': 'verified' if manager else 'unmatched',
            'portrait': portraits.get(manager['id'], {}).get('file') if manager else None}


def valid_history(rows, cutoff):
    seen = {}
    for row in rows:
        # Archive has result dates, not completion timestamps. Exclude the entire
        # snapshot date, even if a kickoff is earlier, rather than guess availability.
        if row['date'] >= cutoff.date().isoformat():
            continue
        if not (isinstance(row['hg'], int) and isinstance(row['ag'], int) and min(row['hg'], row['ag']) >= 0):
            continue
        odds = row.get('odds')
        if not odds or len(odds) != 3 or not all(isinstance(p, (int, float)) and 1 < p <= 1000 for p in odds):
            continue
        if row['id'] in seen and seen[row['id']] != row:
            raise ValueError('Conflicting historical fixture: ' + row['id'])
        seen[row['id']] = row
    return list(seen.values())


def orient(row, first_is_home):
    prices = row['odds'] if first_is_home else list(reversed(row['odds']))
    winner = 1 if row['hg'] == row['ag'] else (0 if (row['hg'] > row['ag']) == first_is_home else 2)
    book = sum(1 / p for p in prices)
    return {'id': row['id'], 'date': row['date'], 'league': row['league'], 'home': row['home'], 'away': row['away'],
            'score': [row['hg'], row['ag']], 'odds': prices, 'basis': row['basis'],
            'firstWasHome': first_is_home, 'winner': winner,
            'profits': [round(p - 1 if i == winner else -1, 4) for i, p in enumerate(prices)],
            'expected': [(1 / p) / book for p in prices]}


def summarize(rows):
    n = len(rows)
    outcomes = []
    for i in range(3):
        values = [r['profits'][i] for r in rows]
        profit = sum(values)
        wins = sum(r['winner'] == i for r in rows)
        outcomes.append({'roi': round(100 * profit / n, 2) if n else None, 'profit': round(profit, 3), 'wins': wins,
                         'expectedWins': round(sum(r['expected'][i] for r in rows), 2),
                         'withoutBest': round(profit - max(values), 3) if values and max(values) > 0 else None,
                         'positive': n >= 3 and profit > 0.000001})
    return {'count': n, 'firstDate': min((r['date'] for r in rows), default=None),
            'lastDate': max((r['date'] for r in rows), default=None), 'outcomes': outcomes}


def pair_key(a, b):
    return tuple(sorted((a, b)))


def build(fixtures, clubs, managers, now, crests):
    club_index, manager_index = defaultdict(list), defaultdict(list)
    for r in valid_history(clubs, now):
        club_index[pair_key(r['home'], r['away'])].append(r)
    for r in valid_history(managers, now):
        manager_index[pair_key(r['homeManager'], r['awayManager'])].append(r)
    cards, evidence = [], {}
    for fixture in sorted(fixtures, key=lambda f: (f['kickoff'], f['id'])):
        h, a = fixture['home'], fixture['away']
        club_rows = [orient(r, r['home'] == h['name']) for r in club_index[pair_key(h['name'], a['name'])]]
        hm, am = h.get('manager'), a.get('manager')
        manager_rows = []
        if hm and am and hm['id'] and am['id']:
            if hm['id'] == am['id']:
                raise ValueError('Same current manager on both sides')
            manager_rows = [orient(r, r['homeManager'] == hm['id']) for r in manager_index[pair_key(hm['id'], am['id'])]]
        shared_ids = {r['id'] for r in club_rows} & {r['id'] for r in manager_rows}
        club_by_id = {r['id']: r for r in club_rows}
        for r in manager_rows:
            if r['id'] in shared_ids and any(r[k] != club_by_id[r['id']][k] for k in ('odds', 'winner', 'profits')):
                raise ValueError('Shared match orientation or price mismatch: ' + r['id'])
        shared = len(shared_ids)
        c, m = summarize(club_rows), summarize(manager_rows)
        alignment = [i for i in range(3) if c['outcomes'][i]['positive'] and m['outcomes'][i]['positive']]
        cards.append({**fixture, 'home': {**h, 'crest': crests.get(h['name'])}, 'away': {**a, 'crest': crests.get(a['name'])},
                      'clubs': c, 'managers': m, 'shared': shared, 'alignment': alignment})
        evidence[fixture['id']] = {'clubs': sorted(club_rows, key=lambda r: (r['date'], r['id']), reverse=True),
                                   'managers': sorted(manager_rows, key=lambda r: (r['date'], r['id']), reverse=True)}
    return cards, evidence


def refresh(state, *, offline=False, now=None, days=21):
    now = now or datetime.now(UTC)
    state = Path(state) / 'fixture-board'
    state.mkdir(parents=True, exist_ok=True)
    cache = state / 'provider'
    cache.mkdir(exist_ok=True)
    football_release = read(ROOT / 'src/data/football-atlas-release.json')
    manager_release = read(ROOT / 'src/data/manager-atlas-release.json')
    football = read(ROOT / 'public' / football_release['indexUrl'].lstrip('/'))
    manager_data = read(ROOT / 'public' / manager_release['indexUrl'].lstrip('/'))
    aliases = read(ROOT / 'scripts/config/football-atlas-clubs.json')
    registry = read(ROOT / 'scripts/config/manager-atlas-identities.json')
    crosswalk = read(ROOT / 'scripts/config/manager-fotmob-identities.json')
    portraits = read(ROOT / 'public/manager-atlas/portraits.json')
    calls, issues, source_times = [], [], {}

    def get(kind, identity):
        path = cache / f'{kind}-{identity}.json'
        old = read(path) if path.exists() else None
        if old and timedelta(0) <= now - dt(old['checkedAt']) < timedelta(hours=6):
            source_times[path.name] = old['checkedAt']
            return old['payload']
        if offline:
            raise ValueError('Fresh provider cache missing: ' + path.name)
        response = requests.get('https://www.fotmob.com/api/data/' + kind, params={'id': identity},
                                headers={'User-Agent': 'IlMargine-Atlas/1.0', 'Accept': 'application/json'}, timeout=25)
        calls.append(path.name)
        response.raise_for_status()
        payload = response.json()
        atomic(path, {'checkedAt': now.isoformat(), 'payload': payload})
        source_times[path.name] = now.isoformat()
        return payload

    fixtures = []
    for league, identity in LEAGUES.items():
        fixtures.extend(league_fixtures(get('leagues', identity), league, now, aliases, football['teams'], days))
    if len(fixtures) > 220 or len({f['id'] for f in fixtures}) != len(fixtures):
        raise ValueError('Fixture count/uniqueness validation failed')
    ids = sorted({f[s]['providerId'] for f in fixtures for s in ('home', 'away')})
    if len(ids) > 100:
        raise ValueError('Roster request budget exceeded')

    def roster(identity):
        try:
            payload = get('teams', identity)
            return identity, resolve_manager(payload, identity, registry, crosswalk, portraits,
                                              dt(source_times[f'teams-{identity}.json']))
        except (requests.RequestException, ValueError, KeyError) as exc:
            issues.append({'teamId': identity, 'reason': type(exc).__name__})
            return identity, None

    with ThreadPoolExecutor(max_workers=3) as pool:
        coaches = dict(pool.map(roster, ids))
    for fixture in fixtures:
        for side in ('home', 'away'):
            fixture[side]['manager'] = coaches.get(fixture[side]['providerId'])
    # A broken roster source must not wipe every manager record in a good snapshot.
    if ids and all(not value for value in coaches.values()):
        raise ValueError('No coaching rosters available; previous board retained')
    club_rows = [{'id': r[0], 'date': r[1], 'league': football['leagues'][r[2]],
                  'home': football['teams'][r[4]], 'away': football['teams'][r[5]], 'hg': r[6], 'ag': r[7],
                  'odds': r[8:11] if r[8] is not None else None,
                  'basis': 'closing' if r[11] == 1 else 'last-pre-match'} for r in football['fixtures']]
    manager_rows = [dict(zip(manager_data['columns'], r)) for r in manager_data['rows']]
    cards, evidence = build(fixtures, club_rows, manager_rows, now, football['crests'])
    checked = min(dt(t) for t in source_times.values())
    payload = {'schema': 1, 'policy': POLICY, 'checkedAt': checked.isoformat(), 'expiresAt': (checked + timedelta(days=7)).isoformat(),
               'historyCutoff': now.date().isoformat(), 'footballThrough': football_release['through'],
               'managerThrough': manager_release['through'], 'footballVersion': football_release['version'],
               'managerVersion': manager_release['version'], 'windowEnd': (now + timedelta(days=days)).date().isoformat(),
               'fixtures': cards}
    version = hashlib.sha256(encoded([payload, evidence])).hexdigest()[:12]
    evidence_path = Path('public/football-atlas/fixtures') / f'evidence-{version}.json'
    payload.update(version=version, evidenceUrl='/' + evidence_path.relative_to('public').as_posix())
    target = ROOT / 'src/data/atlas-fixtures.json'
    previous = read(target) if target.exists() else None
    # All validation has completed before publishing either file; manifest is last.
    atomic(ROOT / evidence_path, {'version': version, 'fixtures': evidence})
    atomic(target, payload)
    # Exact versioned research observation, outside the deployment tree; no odds/EV invented.
    snapshot = state / 'snapshots' / f'{now.strftime("%Y%m%dT%H%M%S")}-{version}.json'
    if not snapshot.exists():
        atomic(snapshot, {'board': payload, 'evidence': evidence})
    report = {'version': version, 'fixtures': len(cards), 'rosters': len(ids), 'requests': len(calls),
              'verifiedManagers': sum(bool(m and m['id']) for m in coaches.values()), 'issues': issues,
              'checkedAt': payload['checkedAt'], 'snapshot': snapshot.name,
              'pendingManagerClubs': sorted({f[s]['name'] for f in fixtures for s in ('home', 'away')
                                             if not (f[s].get('manager') or {}).get('id')})}
    atomic(state / 'report.json', report)
    paths = ['src/data/atlas-fixtures.json', evidence_path.as_posix()]
    # Retain the previous evidence file for already-open browser tabs.
    keep = {payload['evidenceUrl'], (previous or {}).get('evidenceUrl')}
    for old in (ROOT / 'public/football-atlas/fixtures').glob('evidence-*.json'):
        if previous == payload:
            break  # An unchanged rerun must retain the previous release's evidence too.
        if '/' + old.relative_to(ROOT / 'public').as_posix() not in keep:
            # Only prune validated generated names inside this exact directory.
            if len(old.stem.removeprefix('evidence-')) == 12 and all(c in '0123456789abcdef' for c in old.stem.removeprefix('evidence-')):
                old.unlink()
                paths.append(old.relative_to(ROOT).as_posix())
    return {'paths': paths, 'report': report, 'changed': previous != payload}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-directory', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    print(json.dumps(refresh(args.state_directory, offline=args.offline)['report']))
