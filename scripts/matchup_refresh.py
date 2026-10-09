"""Local-only companion to the existing Atlas publisher. No provider calls."""
import importlib.util
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_snapshot(root, release):
    index_path = root / 'public' / release['indexUrl'].lstrip('/')
    index = read(index_path)
    rows = {}
    results = {}
    for i in range(len(index['players'])):
        shard = read(index_path.parent / f'{i}.json')
        if shard['version'] != index['version'] or shard['player'] != i:
            raise ValueError('Mixed Matchup snapshot')
        for row in shard['matches']:
            if row['id'] in rows and rows[row['id']] != row:
                raise ValueError('Conflicting Matchup shards')
            rows[row['id']] = row
        for row in shard.get('results',[]):
            if row['id'] in results and results[row['id']] != row:
                raise ValueError('Conflicting H2H shards')
            results[row['id']] = row
    if len(rows) != index['totalMatches']:
        raise ValueError('Incomplete Matchup snapshot')
    if len(results) != index.get('additionalResults',0) or rows.keys() & results.keys():
        raise ValueError('Incomplete or duplicate H2H snapshot')
    return {**index, 'matches': list(rows.values()), 'results':list(results.values())}


def canonical(data):
    rows = {}
    for raw in data['matches']:
        row = dict(raw)
        for side in ('p1', 'p2'):
            row[side] = data['players'][row[side]]['id']
        rows[row['id']] = row
    return rows


def validate(old, new):
    previous, candidate = canonical(old), canonical(new)
    old_extra=canonical({**old,'matches':old.get('results',[])})
    new_extra=canonical({**new,'matches':new.get('results',[])})
    if len(new_extra)-len(old_extra)>400:
        raise ValueError('Large H2H backfill requires review')
    # Price arrival may move an extra into the established ATP archive. Compare
    # fixture identities and oriented results rather than dropping integrity checks.
    for mid,before in old_extra.items():
        after=new_extra.get(mid)
        if after is None:
            def equivalent(row):
                return (row['date']==before['date'] and {row['p1'],row['p2']}=={before['p1'],before['p2']}
                    and row['score']==before['score'] and row['event']==before['event']
                    and [row['p1'],row['p2']][row['winner']]==[before['p1'],before['p2']][before['winner']])
            replacements=[r for r in candidate.values() if equivalent(r)]
            if len(replacements)!=1: raise ValueError(f'H2H meeting disappeared: {mid}')
            after=replacements[0]
        else:
            for field in ('stats1','stats2'):
                if before.get(field) and any(v is not None and (after.get(field) or {}).get(k)!=v for k,v in before[field].items()):
                    raise ValueError(f'Existing H2H statistics changed: {mid}')
            for field in ('date','p1','p2','winner','score','event','surface','competition','o1','o2'):
                if before.get(field) is not None and after.get(field)!=before[field]:
                    raise ValueError(f'Existing H2H record changed: {mid} ({field})')
    if len(candidate) - len(previous) > 400:
        raise ValueError('Large Matchup backfill requires review')
    for mid, before in previous.items():
        after = candidate.get(mid)
        if after is None:
            raise ValueError(f'Matchup match disappeared: {mid}')
        for field, value in before.items():
            if field.startswith('stats') and value:
                if not after.get(field) or any(v is not None and after[field].get(k) != v for k, v in value.items()):
                    raise ValueError(f'Existing Matchup statistics changed: {mid}')
            elif value is not None and after.get(field) != value:
                raise ValueError(f'Existing Matchup record changed: {mid} ({field})')
    # A new check date alone does not justify another deployment.
    return previous != candidate or old_extra != new_extra or any(old[k] != new[k] for k in ('players', 'portraits', 'countries'))


def prepare(checkout, candidate, atlas_release, as_of):
    here = Path(__file__).resolve().parent
    def module(name, filename):
        spec = importlib.util.spec_from_file_location(name, here / filename)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    builder = module('matchup_builder', 'build-tennis-matchup.py')
    packager = module('matchup_packager', 'package-tennis-matchup.py')
    atlas = candidate / 'release/public' / atlas_release['indexUrl'].lstrip('/')
    private = candidate / 'matchup-private'
    builder.build(atlas.parent, candidate / 'oncourt', private, as_of, data_only=True)
    new_release = packager.package(private / 'data.json', candidate / 'release')
    old_release = read(checkout / 'src/data/tennis-matchup-release.json')
    old = load_snapshot(checkout, old_release)
    new = load_snapshot(candidate / 'release', new_release)
    changed = validate(old, new)
    return old_release, new_release if changed else old_release, changed
