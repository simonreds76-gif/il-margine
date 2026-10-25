"""Validated Championship extension. Never replaces the top-five archive.

Historical-only release authorised by the site owner on 25 October 2026.
Source provenance is retained; this is not a claim of a changed source licence.
The seed is frozen. New results come from the separate verified weekly ledger.
Manager attribution requires a separate match-specific evidence record.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASES = {1: 'closing', 2: 'last-pre-match', 3: 'bet365-last-pre-match',
         4: 'bet365-closing', 5: 'bet365-pre-match', 6: 'pinnacle-pre-match'}
COLUMNS = ['id', 'date', 'league', 'season', 'home', 'away', 'hg', 'ag', 'odds', 'basis']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(encoded(value))
    temp.replace(path)


def parse_season(content, year, cutoff, aliases):
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('cp1252')
    records = list(csv.DictReader(io.StringIO(text)))
    if not records or not {'Div', 'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR'} <= records[0].keys():
        raise ValueError('Invalid Championship CSV schema')
    rows = []
    for row in records:
        if not row.get('HomeTeam') and not row.get('AwayTeam'):
            continue
        if row['Div'] != 'E1':
            raise ValueError('Wrong division in Championship source')
        date = datetime.strptime(row['Date'], '%d/%m/%Y' if len(row['Date']) == 10 else '%d/%m/%y').date()
        if not year <= date.year <= year + 1:
            raise ValueError('Wrong season in Championship source')
        if date.isoformat() >= cutoff:
            continue
        # Incomplete past rows must be investigated, not silently discarded.
        hg, ag = int(row['FTHG']), int(row['FTAG'])
        if min(hg, ag) < 0 or row['FTR'] != ('H' if hg > ag else 'A' if ag > hg else 'D'):
            raise ValueError('Score/result conflict')
        home, away = aliases[row['HomeTeam']], aliases[row['AwayTeam']]
        odds, basis = None, None
        # Provider warns its Pinnacle quotes are stale from 23 July 2025.
        priorities = [('PSC', 'closing'), ('PS', 'pinnacle-pre-match')] if date.isoformat() < '2025-07-23' else []
        priorities += [('B365C', 'bet365-closing'), ('B365', 'bet365-pre-match')]
        for prefix, label in priorities:
            try:
                values = [float(row[prefix + side]) for side in 'HDA']
            except (KeyError, ValueError, TypeError):
                continue
            if all(math.isfinite(p) and 1 < p <= 1000 for p in values) and .98 <= sum(1 / p for p in values) <= 1.30:
                odds, basis = values, label
                break
        identity = 'e1-' + hashlib.sha256(encoded([date.isoformat(), home, away])).hexdigest()[:18]
        rows.append(dict(zip(COLUMNS, [identity, date.isoformat(), 'championship', f'{year}-{year+1}', home, away, hg, ag, odds, basis])))
    validate(rows)
    return rows


def validate(rows):
    ids, keys = set(), set()
    for row in rows:
        key = (row['date'], row['home'], row['away'])
        if row['id'] in ids or key in keys or row['home'] == row['away'] or row['league'] != 'championship':
            raise ValueError('Duplicate or invalid Championship fixture')
        ids.add(row['id']); keys.add(key)
        if any(type(row[s]) is not int or row[s] < 0 for s in ('hg', 'ag')):
            raise ValueError('Invalid result')
        if row['odds'] is not None and (len(row['odds']) != 3 or row['basis'] not in BASES.values() or
                not all(type(p) in (int, float) and math.isfinite(p) and 1 < p <= 1000 for p in row['odds'])):
            raise ValueError('Invalid price contract')


def sync_forward_checkpoint():
    """Install the verified collector artifact without rewriting existing records."""
    incoming = os.environ.get('CHAMPIONSHIP_CHECKPOINT')
    if not incoming:
        return []
    candidate = read(incoming)  # Explicit input missing/corrupt must never silently pass.
    target = ROOT / 'data/football-atlas/championship-forward.json'
    previous = read(target)
    for key in ('schema', 'competition', 'scope', 'startDate'):
        if candidate.get(key) != previous.get(key):
            raise ValueError('Forward checkpoint identity changed')
    validate(candidate['rows'])
    if candidate.get('conflicts') or any(r.get('provenance') != 'goaloo+fotmob+oddspapi' or r['date'] < previous['startDate'] for r in candidate['rows']):
        raise ValueError('Forward checkpoint contains unresolved evidence')
    by_id = {r['id']: r for r in candidate['rows']}
    for row in previous['rows']:
        new = by_id.get(row['id'])
        if new is None:
            raise ValueError('Forward checkpoint would remove an existing match')
        for key in ('date', 'home', 'away', 'hg', 'ag', 'league', 'season', 'kickoff'):
            if row.get(key) != new.get(key):
                raise ValueError('Forward checkpoint would change an existing result')
        if row['odds'] is not None and any(row.get(k) != new.get(k) for k in ('odds', 'basis', 'priceEvidence')):
            raise ValueError('Forward checkpoint would rewrite recorded prices')
    if encoded(candidate) == encoded(previous):
        return []
    atomic(target, candidate)
    return [target.relative_to(ROOT).as_posix()]


def refresh(state, *, offline=False, now=None, extension_state=None):
    from atlas_fixture_board import build
    now = now or datetime.now(timezone.utc)
    state = Path(state) / 'covered-history'
    seed = read(ROOT / 'data/football-atlas/championship-seed.json')
    rows = [dict(zip(COLUMNS, r)) for r in seed['rows']]
    sources = seed['sources'].copy()
    if not offline:
        raise ValueError('Frozen seed: automatic source downloads are disabled')
    ledger_path = Path(extension_state) / 'ledger.json' if extension_state else ROOT / 'data/football-atlas/championship-forward.json'
    ledger = read(ledger_path)
    if (ledger.get('schema'), ledger.get('competition'), ledger.get('scope'), ledger.get('startDate')) != (1, 'championship', 'regular-season', '2026-10-23'):
        raise ValueError('Wrong forward Championship checkpoint')
    if ledger.get('conflicts'):
        raise ValueError('Forward checkpoint has unresolved conflicts')
    validate(ledger['rows'])
    if any(r['date'] < ledger['startDate'] or r.get('provenance') != 'goaloo+fotmob+oddspapi' for r in ledger['rows']):
        raise ValueError('Forward checkpoint lacks verified provenance')
    keys = {(r['date'], r['home'], r['away']): r for r in rows}
    new_rows = []
    for row in ledger['rows']:
        key = (row['date'], row['home'], row['away'])
        if key in keys:
            if (row['hg'], row['ag']) != (keys[key]['hg'], keys[key]['ag']):
                raise ValueError('Forward result conflicts with frozen seed')
            continue  # Existing quotes are never replaced.
        if row['date'] >= now.date().isoformat():
            continue  # Date-only history excludes today and future fixtures.
        new_rows.append(row)
    rows += new_rows
    pipeline = {'results': len(new_rows), 'priced': sum(r['odds'] is not None for r in new_rows),
                'pending': len(ledger['pending']), 'through': max((r['date'] for r in new_rows), default=None),
                'ledgerSha256': hashlib.sha256(encoded(ledger)).hexdigest()}
    sources.append({'source': 'Goaloo + FotMob results; OddsPapi pre-match prices', 'sha256': pipeline['ledgerSha256']})
    validate(rows)
    football_release = read(ROOT / 'src/data/football-atlas-release.json')
    manager_release = read(ROOT / 'src/data/manager-atlas-release.json')
    football = read(ROOT / 'public' / football_release['indexUrl'].lstrip('/'))
    managers = read(ROOT / 'public' / manager_release['indexUrl'].lstrip('/'))
    board = read(ROOT / 'src/data/atlas-fixtures.json')
    if board['footballVersion'] != football_release['version'] or board['managerVersion'] != manager_release['version']:
        raise ValueError('Base archive/board versions do not match')
    known_managers = {m['id'] for m in managers['managers']}
    by_key = {(r['date'], r['home'], r['away']): r for r in rows}
    assignments = read(ROOT / 'scripts/config/championship-manager-evidence.json')
    verified, seen = [], set()
    for assignment in assignments:
        key = tuple(assignment[k] for k in ('date', 'home', 'away'))
        if key in seen or key not in by_key or not assignment.get('source') or assignment.get('status') != 'verified':
            raise ValueError('Invalid match-specific manager evidence')
        if assignment['homeManager'] not in known_managers or assignment['awayManager'] not in known_managers or assignment['homeManager'] == assignment['awayManager']:
            raise ValueError('Unknown manager identity')
        seen.add(key)
        verified.append({**by_key[key], **{k: assignment[k] for k in ('homeManager', 'awayManager')}})
    # Positional extension, not duplicate copies of the large existing archives.
    competition = read(ROOT / 'scripts/config/football-atlas-competitions.json')['championship']
    extra_crests = {name: f"https://images.fotmob.com/image_resources/logo/teamlogo/{club['fotmob']}.png"
                    for name, club in competition['clubs'].items() if club.get('fotmob')}
    extension = {'columns': COLUMNS, 'rows': [[r[k] for k in COLUMNS] for r in rows], 'crests': extra_crests,
                 'managerColumns': managers['columns'], 'managerRows': [],
                 'scope': 'historical-clubs-only',
                 'provenance': {'seedRows': len(seed['rows']), 'independentNewRows': len(new_rows)}, 'pipeline': pipeline}
    clubs = [{'id': r[0], 'date': r[1], 'league': football['leagues'][r[2]], 'season': football['seasons'][r[3]],
              'home': football['teams'][r[4]], 'away': football['teams'][r[5]], 'hg': r[6], 'ag': r[7],
              'odds': r[8:11] if r[8] else None, 'basis': BASES.get(r[11])} for r in football['fixtures']]
    base_managers = [dict(zip(managers['columns'], r)) for r in managers['rows']]
    cutoff = datetime.fromisoformat(board['historyCutoff']).replace(tzinfo=timezone.utc)
    # Preserve the original board's result cutoff and every manager statistic.
    # New Championship rows can appear in the extension only before the fixture date.
    cards, evidence = [], {}
    seed_rows = [dict(zip(COLUMNS, r)) for r in seed['rows']]
    fixtures = list(board['fixtures'])
    if any(f['league'] not in {'premier-league', 'serie-a', 'la-liga', 'bundesliga', 'ligue-1'} for f in fixtures):
        raise ValueError('Historical extension must not add upcoming competitions')
    for fixture in fixtures:
        fixture_date = datetime.fromisoformat(fixture['kickoff'].replace('Z', '+00:00'))
        extension_cutoff = min(now, fixture_date)
        eligible_new = [r for r in new_rows if r['date'] < extension_cutoff.date().isoformat()]
        eligible_seed = [r for r in seed_rows if r['date'] < min(cutoff, fixture_date).date().isoformat()]
        eligible_clubs = [r for r in clubs if r['date'] < min(cutoff, fixture_date).date().isoformat()]
        eligible_managers = [r for r in base_managers if r['date'] < min(cutoff, fixture_date).date().isoformat()]
        batch, detail = build([fixture], eligible_clubs + eligible_seed + eligible_new, eligible_managers,
                              max(cutoff, extension_cutoff), {**football['crests'], **extra_crests})
        cards.extend(batch); evidence.update(detail)
    base_by_id = {f['id']: f for f in board['fixtures']}
    for card in cards:
        original = base_by_id.get(card['id'])
        if original is None:
            card['additionalClubMeetings'] = 0
            card['additionalManagerMeetings'] = 0
            continue
        card['additionalClubMeetings'] = card['clubs']['meetings'] - original['clubs']['meetings']
        card['additionalManagerMeetings'] = card['managers']['meetings'] - original['managers']['meetings']
    version = hashlib.sha256(encoded([extension, board['version'], cards, evidence])).hexdigest()[:12]
    directory = Path('public/football-atlas/covered')
    data_path, board_path, evidence_path = [directory / f'{kind}-{version}.json' for kind in ('history', 'board', 'evidence')]
    expanded = {**board, 'version': version, 'fixtures': cards, 'scope': 'covered',
                'evidenceUrl': '/' + evidence_path.relative_to('public').as_posix()}
    manifest = {'scope': 'historical-clubs-only', 'version': version, 'baseBoardVersion': board['version'], 'footballVersion': football_release['version'],
                'managerVersion': manager_release['version'], 'historyUrl': '/' + data_path.relative_to('public').as_posix(),
                'boardUrl': '/' + board_path.relative_to('public').as_posix(), 'matches': len(rows),
                'priced': sum(bool(r['odds']) for r in rows), 'verifiedManagerMatches': 0, 'internalVerifiedManagerMatches': len(verified),
                'through': max(r['date'] for r in rows), 'pipeline': pipeline,
                'additionalClubMeetings': {f['id']: f['additionalClubMeetings'] for f in cards if f['additionalClubMeetings']}}
    target = ROOT / 'src/data/covered-leagues-release.json'
    previous = read(target) if target.exists() else None
    for path, payload in [(data_path, extension), (board_path, expanded), (evidence_path, {'version': version, 'fixtures': evidence})]:
        atomic(ROOT / path, payload)
    atomic(target, manifest)
    paths = [p.as_posix() for p in (data_path, board_path, evidence_path)] + ['src/data/covered-leagues-release.json']
    # Retain current and previous complete versions for open browser tabs.
    keep = {version, (previous or {}).get('version')}
    if previous != manifest:
        for path in (ROOT / directory).glob('*.json'):
            suffix = path.stem.rsplit('-', 1)[-1]
            if len(suffix) == 12 and all(c in '0123456789abcdef' for c in suffix) and suffix not in keep:
                path.unlink(); paths.append(path.relative_to(ROOT).as_posix())
    report = {'state': 'ready', 'version': version, 'sources': sources, 'matches': len(rows), 'priced': manifest['priced'],
              'verifiedManagerMatches': 0, 'internalVerifiedManagerMatches': len(verified), 'unverifiedManagerMatches': len(rows)-len(verified)}
    atomic(state / 'report.json', report)
    return {'paths': paths, 'changed': previous != manifest, 'report': report}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-directory', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--extension-state', type=Path)
    args = parser.parse_args()
    print(json.dumps(refresh(args.state_directory, offline=args.offline, extension_state=args.extension_state)['report']))
