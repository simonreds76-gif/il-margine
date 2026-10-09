"""Package an explicitly approved Matchup Lab snapshot; never export raw source tables.

Run after build-tennis-matchup.py, then review the diff and publish the changed
static files. No network calls, credentials, model weights or scheduled jobs.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('id', 'date', 'p1', 'p2', 'winner', 'o1', 'o2', 'surface', 'region',
          'country', 'event', 'score', 'stats1', 'stats2')

def package(source, root=ROOT):
    data = json.loads(source.read_text(encoding='utf-8'))
    if data['schema'] != 1 or not data['matches']:
        raise ValueError('Missing validated snapshot')
    players = data['players']
    rows = [{key: row.get(key) for key in FIELDS} for row in data['matches']]
    extra_fields = FIELDS + ('competition','priceSource','priceBasis')
    results = [{key:row.get(key) for key in extra_fields} for row in data.get('results',[])]
    seen = set()
    fixtures = set()
    for row in rows + results:
        if row['id'] in seen or row['p1'] == row['p2']:
            raise ValueError('Duplicate or invalid match')
        seen.add(row['id'])
        fixture=(row['date'],tuple(sorted((row['p1'],row['p2']))))
        if fixture in fixtures: raise ValueError('Ambiguous repeated pair on one date')
        fixtures.add(fixture)
        if not all(isinstance(row[key], int) and 0 <= row[key] < len(players) for key in ('p1', 'p2')):
            raise ValueError('Invalid player reference')
        unpriced = row.get('competition') and row['o1'] is None and row['o2'] is None
        if row['winner'] not in (0, 1) or not (unpriced or all(isinstance(row[key], (int, float)) and 1 < row[key] < 1001 for key in ('o1', 'o2'))):
            raise ValueError('Invalid winner or paired prices')
        if not (('1990-01-01' if row.get('competition') else '2021-01-01') <= row['date'] < data['asOf']):
            raise ValueError('Date outside completed-match snapshot')
    content = {key: data[key] for key in ('through', 'countries', 'players', 'portraits')}
    content['matches'] = rows
    content['results'] = results
    version = data['asOf'].replace('-', '') + '-' + hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:12]
    target = root / 'public/tennis-matchup/data' / version
    target.mkdir(parents=True, exist_ok=True)
    shards = [[] for _ in players]
    result_shards = [[] for _ in players]
    for row in rows:
        shards[row['p1']].append(row)
        shards[row['p2']].append(row)
    for row in results:
        result_shards[row['p1']].append(row)
        result_shards[row['p2']].append(row)
    def write(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    for index, matches in enumerate(shards):
        write(target / f'{index}.json', {'version': version, 'player': index, 'matches': matches, 'results':result_shards[index]})
    manifest = {key: data[key] for key in ('asOf', 'through', 'countries', 'players', 'portraits')}
    manifest.update(schema=2, version=version, totalMatches=len(rows))
    manifest.update(additionalResults=len(results), historyFrom=data.get('historyFrom','2021-01-01'))
    write(target / 'index.json', manifest)
    release = {'version': version, 'checkedAt': data['asOf'], 'through': data['through'],
               'matches': len(rows), 'players': len(players), 'indexUrl': f'/tennis-matchup/data/{version}/index.json'}
    release.update(additionalResults=len(results), historyFrom=manifest['historyFrom'])
    (root / 'src/data').mkdir(parents=True, exist_ok=True)
    write(root / 'src/data/tennis-matchup-release.json', release)
    return release

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.snapshot), indent=2))
