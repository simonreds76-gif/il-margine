"""Local-only companion to the existing Atlas publisher. No provider calls."""
import importlib.util
import json
from pathlib import Path
from tennis_score_integrity import score_detail_enrichment


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_snapshot(root, release):
    index_path = root / 'public' / release['indexUrl'].lstrip('/')
    index = read(index_path)
    rows = {}
    results = {}
    schedules = {}
    for i in range(len(index['players'])):
        shard = read(index_path.parent / f'{i}.json')
        if shard['version'] != index['version'] or shard['player'] != i:
            raise ValueError('Mixed Matchup snapshot')
        schedules[str(i)] = shard.get('schedule',[])
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
    return {**index, 'matches': list(rows.values()), 'results':list(results.values()),'context':{**index.get('context',{}),'players':schedules}}


def canonical(data):
    rows = {}
    for raw in data['matches']:
        row = dict(raw)
        for side in ('p1', 'p2'):
            row[side] = data['players'][row[side]]['id']
        rows[row['id']] = row
    return rows


def validate(old, new):
    from build_matchday_supplement import validate_supplement
    validate_supplement(old.get('matchdaySupplement'), new.get('matchdaySupplement'))
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
                    and (row['score']==before['score'] or score_detail_enrichment(before['score'], row['score'])) and row['event']==before['event']
                    and [row['p1'],row['p2']][row['winner']]==[before['p1'],before['p2']][before['winner']])
            replacements=[r for r in candidate.values() if equivalent(r)]
            if len(replacements)!=1: raise ValueError(f'H2H meeting disappeared: {mid}')
            after=replacements[0]
        else:
            for field in ('stats1','stats2'):
                if before.get(field) and any(v is not None and (after.get(field) or {}).get(k)!=v for k,v in before[field].items()):
                    raise ValueError(f'Existing H2H statistics changed: {mid}')
            for field in ('date','p1','p2','winner','score','event','surface','competition','o1','o2'):
                if field == 'score' and score_detail_enrichment(before.get(field), after.get(field)):
                    continue
                if before.get(field) is not None and after.get(field)!=before[field]:
                    raise ValueError(f'Existing H2H record changed: {mid} ({field})')
    if len(candidate) - len(previous) > 400:
        raise ValueError('Large Matchup backfill requires review')
    for mid, before in previous.items():
        after = candidate.get(mid)
        if after is None:
            raise ValueError(f'Matchup match disappeared: {mid}')
        for field, value in before.items():
            if field == 'score' and score_detail_enrichment(value, after.get(field)):
                continue
            if field.startswith('stats') and value:
                if not after.get(field) or any(v is not None and after[field].get(k) != v for k, v in value.items()):
                    raise ValueError(f'Existing Matchup statistics changed: {mid}')
            elif value is not None and after.get(field) != value:
                raise ValueError(f'Existing Matchup record changed: {mid} ({field})')
    # A new check date alone does not justify another deployment.
    return old.get('matchdaySupplement') != new.get('matchdaySupplement') or old.get('context') != new.get('context') or previous != candidate or old_extra != new_extra or any(old[k] != new[k] for k in ('players', 'portraits', 'countries'))


def prepare(checkout, candidate, atlas_release, as_of, historical_prices=(), schedule=None):
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
    old_release = read(checkout / 'src/data/tennis-matchup-release.json')
    old = load_snapshot(checkout, old_release)
    retained = canonical({**old,'matches':[r for r in old.get('results',[]) if r.get('o1') and r.get('o2')]})
    builder.build(atlas.parent, candidate / 'oncourt', private, as_of, data_only=True,
                  historical_prices=historical_prices, retained_prices=retained)
    from build_matchday_supplement import build as build_supplement, read_csv
    payload_path = private / 'data.json'
    payload = read(payload_path)
    audit_path = private / 'matchday-supplement-audit.json'
    prior_requests = read(audit_path).get('requests', []) if audit_path.exists() else []
    schedule_rows = read_csv(schedule) if schedule and schedule.exists() else []
    from matchday_saved_schedule import latest_saved_schedule
    remote_rows, remote_status = latest_saved_schedule(schedule.parent.parent) if schedule else ([], {'status': 'not_requested'})
    schedule_rows += remote_rows
    supplement, supplement_audit = build_supplement(candidate / 'oncourt',
        schedule_rows, payload['players'], as_of,
        old.get('matchdaySupplement'), prior_requests)
    supplement_audit.update(checkedAt=as_of, savedSchedule=remote_status, scheduleRows=len(schedule_rows),
        scheduleState='loaded' if schedule_rows else 'empty' if schedule and schedule.exists() else 'missing')
    if supplement['pairs']:
        payload['matchdaySupplement'] = supplement
        payload_path.write_text(json.dumps(payload), encoding='utf-8')
    (private / 'matchday-supplement-audit.json').write_text(json.dumps(supplement_audit, indent=2), encoding='utf-8')
    from refresh_matchday_portraits import prepare as prepare_portraits
    prepare_portraits(checkout, candidate, schedule_rows, here.parent / 'config/tennis-portrait-overrides.json')
    new_release = packager.package(private / 'data.json', candidate / 'release')
    new = load_snapshot(candidate / 'release', new_release)
    changed = validate(old, new)
    return old_release, new_release if changed else old_release, changed
