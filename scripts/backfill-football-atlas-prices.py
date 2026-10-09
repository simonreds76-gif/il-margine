"""Recover missing Atlas prices from retained source rows, with exact joins.

Dry run by default. No downloads, fuzzy joins, source-price overrides or manager
inferences. Closing bet365 markets take priority over earlier bet365 snapshots.
"""
import argparse
from collections import Counter
import copy
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODES = {'closing': 1, 'last-pre-match': 2, 'bet365-last-pre-match': 3,
         'bet365-closing': 4, 'bet365-pre-match': 5}
DIVISIONS = {'premier-league': 'E0', 'serie-a': 'I1', 'la-liga': 'SP1',
             'bundesliga': 'D1', 'ligue-1': 'F1'}


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def valid(odds):
    return len(odds) == 3 and all(type(p) in (int, float) and math.isfinite(p) and 1 < p < 1001 for p in odds)


def source_prices(row):
    for basis, columns in [('bet365-closing', ['B365CH', 'B365CD', 'B365CA']),
                           ('bet365-pre-match', ['B365H', 'B365D', 'B365A'])]:
        try:
            odds = [float(row[k]) for k in columns]
        except (ValueError, KeyError, TypeError):
            continue
        if valid(odds):
            book = sum(1 / p for p in odds)
            if not 0.99 <= book <= 1.5:
                raise ValueError('Implausible complete bookmaker market')
            return odds, basis, columns
    raise ValueError('No complete bet365 market')


def source_date(value):
    for fmt in ('%d/%m/%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def collect(index, raw_directory):
    builder = module('backfill_source_names', 'build-football-atlas.py')
    cache, accepted = {}, {}
    for fixture in index['fixtures']:
        if valid(fixture[8:11]):
            continue
        fid, date, li, si, hi, ai, hg, ag = fixture[:8]
        league, season = index['leagues'][li], index['seasons'][si]
        home, away = index['teams'][hi], index['teams'][ai]
        key = (league, season)
        if key not in cache:
            path = Path(raw_directory) / f'{league}-{season}.csv'
            raw = path.read_bytes()
            rows = list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
            cache[key] = rows, hashlib.sha256(raw).hexdigest()
        rows, digest = cache[key]
        def same_name(raw, canonical):
            return builder.norm(builder.DISPLAY.get(raw, raw)) == builder.norm(canonical)
        matches = [(n, row) for n, row in enumerate(rows, 2)
                   if source_date(row.get('Date', '')) == date
                   and same_name(row['HomeTeam'], home) and same_name(row['AwayTeam'], away)]
        if len(matches) != 1:
            raise ValueError(f'{fid}: expected one exact source row, got {len(matches)}')
        line, row = matches[0]
        if row['Div'] != DIVISIONS[league] or [int(row['FTHG']), int(row['FTAG'])] != [hg, ag]:
            raise ValueError(f'{fid}: source league or score mismatch')
        odds, basis, columns = source_prices(row)
        season_code = season[2:4] + season[7:9]
        accepted[fid] = {'date': date, 'league': league, 'season': season,
                         'home': home, 'away': away, 'score': [hg, ag],
                         'bookmaker': 'bet365', 'market': '90-minute 1X2',
                         'odds': odds, 'basis': basis, 'columns': columns,
                         'source': f'https://www.football-data.co.uk/mmz4281/{season_code}/{DIVISIONS[league]}.csv',
                         'sourceFile': f'{league}-{season}.csv', 'sourceSha256': digest,
                         'sourceRow': line, 'reviewedAt': datetime.now(timezone.utc).date().isoformat(),
                         'timingEvidence': 'https://www.football-data.co.uk/notes.txt',
                         'note': 'Retained source row. C columns are source-reported closing prices; unmarked columns are earlier prematch prices. No exact quote timestamp inferred.'}
    return accepted


def apply(index, reviews):
    result = copy.deepcopy(index)
    found = set()
    for row in result['fixtures']:
        if row[0] not in reviews:
            continue
        item = reviews[row[0]]
        identity = [row[1], result['leagues'][row[2]], result['seasons'][row[3]],
                    result['teams'][row[4]], result['teams'][row[5]], row[6:8]]
        if identity != [item['date'], item['league'], item['season'], item['home'], item['away'], item['score']]:
            raise ValueError('Review identity mismatch: ' + row[0])
        if not valid(item['odds']) or item['basis'] not in CODES:
            raise ValueError('Invalid reviewed prices')
        expected = [*item['odds'], CODES[item['basis']]]
        if valid(row[8:11]) and row[8:12] != expected:
            raise ValueError('Cannot overwrite a published market: ' + row[0])
        row[8:12] = expected
        found.add(row[0])
    if found != set(reviews):
        raise ValueError('Review fixture not in archive')
    result.setdefault('reviewedPriceFallbacks', {}).update(reviews)
    return result


def publish_files(old, new, old_meta, root=ROOT):
    """Write all derived data locally after validation; never deploy or refresh APIs."""
    pack = module('backfill_manager_pack', 'package-manager-release.py')
    board = module('backfill_board', 'atlas_fixture_board.py')
    manager_meta = read(root / 'src/data/manager-atlas-release.json')
    managers = pack.unpack(read(root / 'public' / manager_meta['indexUrl'].lstrip('/')))
    source = {r[0]: r for r in new['fixtures']}
    manager_changed = 0
    for row in managers['fixtures']:
        match = source[row['id']]
        if row['odds'] is None and valid(match[8:11]):
            identity = [row[k] for k in ('date', 'league', 'season', 'home', 'away', 'hg', 'ag')]
            expected = [match[1], new['leagues'][match[2]], new['seasons'][match[3]],
                        new['teams'][match[4]], new['teams'][match[5]], match[6], match[7]]
            if identity != expected:
                raise ValueError('Manager identity mismatch: ' + row['id'])
            row.update(odds=match[8:11], basis=next(k for k, v in CODES.items() if v == match[11]))
            manager_changed += 1
        elif row['odds'] != match[8:11] or CODES.get(row['basis']) != match[11]:
            raise ValueError('Club/manager prices disagree: ' + row['id'])
    pack.validate(managers)
    raw = board.encoded(new)
    version = hashlib.sha256(raw).hexdigest()[:12]
    index_path = root / 'public/football-atlas' / f'index-{version}.json'
    priced = [r for r in new['fixtures'] if valid(r[8:11])]
    meta = {**old_meta, 'version': version, 'indexUrl': '/football-atlas/' + index_path.name,
            'checkedAt': datetime.now(timezone.utc).isoformat(), 'matches': len(priced),
            'bytes': len(raw), 'previewOnly': False}
    meta['coverage'] = {league: {season: {'eligible': sum(r[2] == li and r[3] == si for r in new['fixtures']),
                                          'priced': sum(r[2] == li and r[3] == si for r in priced)}
                                  for si, season in enumerate(new['seasons'])}
                          for li, league in enumerate(new['leagues'])}
    managers['atlasVersion'] = version
    managers['coverage']['basis'] = dict(Counter(r['basis'] for r in managers['fixtures']))
    old_board = read(root / 'src/data/atlas-fixtures.json')
    club_rows = [{'id': r[0], 'date': r[1], 'league': new['leagues'][r[2]], 'home': new['teams'][r[4]],
                 'away': new['teams'][r[5]], 'hg': r[6], 'ag': r[7], 'odds': r[8:11],
                 'basis': next(k for k, v in CODES.items() if v == r[11])} for r in new['fixtures']]
    # Recalculate history only. Keep fixture/manager source freshness unchanged.
    cards, evidence = board.build(old_board['fixtures'], club_rows, managers['fixtures'],
                                  datetime.fromisoformat(old_board['historyCutoff']).replace(tzinfo=timezone.utc), new['crests'])
    index_path.write_bytes(raw)
    write(root / 'src/data/football-atlas-release.json', meta)
    manager_meta, _ = pack.package(managers, root)
    payload = {k: v for k, v in old_board.items() if k not in ('version', 'evidenceUrl')}
    payload.update(footballVersion=version, managerVersion=manager_meta['version'], fixtures=cards)
    board_version = hashlib.sha256(board.encoded([payload, evidence])).hexdigest()[:12]
    evidence_url = f'/football-atlas/fixtures/evidence-{board_version}.json'
    payload.update(version=board_version, evidenceUrl=evidence_url)
    board.atomic(root / 'public' / evidence_url.lstrip('/'), {'version': board_version, 'fixtures': evidence})
    board.atomic(root / 'src/data/atlas-fixtures.json', payload)
    return {'footballVersion': version, 'managerVersion': manager_meta['version'], 'matchdayVersion': board_version,
            'managerPricesRestored': manager_changed, 'remainingFootballGaps': len(new['fixtures']) - len(priced),
            'remainingManagerPriceGaps': sum(r['odds'] is None for r in managers['fixtures'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    meta = read(ROOT / 'src/data/football-atlas-release.json')
    old = read(ROOT / 'public' / meta['indexUrl'].lstrip('/'))
    reviews = collect(old, args.raw_directory)
    new = apply(old, reviews)
    report = {'beforeVersion': meta['version'], 'beforeGaps': len(reviews),
              'byBasis': dict(Counter(r['basis'] for r in reviews.values())),
              'afterGaps': sum(not valid(r[8:11]) for r in new['fixtures']), 'write': args.write}
    write(args.output / 'reviewed-prices.json', reviews)
    if args.write and reviews:
        if report['afterGaps']:
            raise ValueError('Incomplete backfill; no release written')
        config_path = ROOT / 'scripts/config/football-atlas-reviewed-prices.json'
        config = read(config_path)
        for fid in reviews:
            if fid in config['fixtures'] and config['fixtures'][fid] != reviews[fid]:
                raise ValueError('Existing review conflicts: ' + fid)
        report.update(publish_files(old, new, meta))
        config['fixtures'].update(reviews)
        config['policy'] = 'Pinnacle is primary. Missing markets may use complete reviewed bet365 1X2 rows. Never mix outcomes or overwrite existing prices. Codes: 3 timestamped last prematch, 4 source-reported closing, 5 earlier prematch snapshot. Retain source evidence.'
        write(config_path, config)
    write(args.output / 'report.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
