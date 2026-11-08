"""Results-only H2H for scheduled pairs outside the priced ATP cohort.

Consumes saved inputs only. Never modifies a source archive, model or odds.
"""
import argparse
from collections import defaultdict, Counter
import csv
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unicodedata

# Reviewed full-name variants; never infer surnames or initials. Official ATP
# MW75 bio and RD48 profile identify these same Brazilian players.
ALIASES = {'igor marcondes': ('29610', 'Igor Ribeiro Marcondes'),
           'felipe meligeni rodrigues alves': ('36617', 'Felipe Meligeni Alves'),
           'tai leonard sach': ('68624', 'Tai Sach')}


def normal(value):
    text = unicodedata.normalize('NFD', str(value)).lower()
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub('[^a-z0-9]+', ' ', text).strip()


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def build(oncourt, schedule, base_players, as_of, old=None, prior_requests=()):
    spec = importlib.util.spec_from_file_location('matchday_score_rules', Path(__file__).with_name('build-tennis-matchup.py'))
    rules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules)
    old = old or {'pairs': {}}
    people = {r['id']: r for r in read_csv(oncourt / 'players_atp.csv')}
    names = defaultdict(list)
    for p in people.values():
        if '/' not in p['name']:
            names[normal(p['name'])].append(p['id'])
    base_names = {normal(p['name']) for p in base_players}
    tours = {r['id']: r for r in read_csv(oncourt / 'tours_atp.csv')}
    games = read_csv(oncourt / 'games_atp.csv')
    recent = set()
    since = date.fromordinal(date.fromisoformat(as_of).toordinal()-366).isoformat()
    for r in games:
        if since <= r['date'] < as_of and tours.get(r['tour_id'], {}).get('rank') in ('0', '1', '2', '3', '4') and rules.completed(r['result']):
            recent.update((r['winner_id'], r['loser_id']))
    pairs = json.loads(json.dumps(old['pairs']))
    audit = {'method': 'unique_full_name_and_recent_activity_and_age', 'second_key_independently_verified': False,
             'unresolved': [], 'identities': {}, 'excluded': Counter()}
    requests = {(r['pair'], r['date'], r['event']): r for r in prior_requests}
    for row in schedule:
        if row.get('league') not in ('ATP', 'Challenger'):
            continue
        if not (as_of <= row.get('match_date', '') <= date.fromordinal(date.fromisoformat(as_of).toordinal()+3).isoformat()):
            continue
        raw = [row.get('player1_name', ''), row.get('player2_name', '')]
        keys = [normal(n) for n in raw]
        if all(k in base_names for k in keys):
            continue
        def candidate(k):
            if k in ALIASES:
                pid, expected = ALIASES[k]
                return [pid] if people.get(pid, {}).get('name') == expected and names[normal(expected)] == [pid] else []
            return names.get(k, [])
        candidates = [candidate(k) for k in keys]
        if any(len(c) != 1 for c in candidates) or candidates[0] == candidates[1]:
            audit['unresolved'].append({'players': raw, 'reason': 'missing_or_ambiguous_exact_identity'})
            continue
        ids = [c[0] for c in candidates]
        keys = [normal(people[pid]['name']) for pid in ids]
        if all(k in base_names for k in keys):
            continue
        try:
            ages = [(date.fromisoformat(row['match_date'])-date.fromisoformat(people[pid]['birthdate'][:10])).days/365.2425 for pid in ids]
        except (ValueError, KeyError):
            ages = []
        if len(ages) != 2 or any(not 15 <= age <= 45 for age in ages) or any(pid not in recent for pid in ids):
            audit['unresolved'].append({'players': raw, 'reason': 'age_or_recent_activity_unconfirmed'})
            continue
        pair_key = '|'.join(sorted(keys))
        ordered = sorted(zip(keys, ids))
        identities = [{'name': people[pid]['name'], 'nativeId': pid} for _, pid in ordered]
        if pair_key in pairs and pairs[pair_key]['players'] != identities:
            pairs[pair_key]['quarantined'] = 'identity_changed'
            audit['unresolved'].append({'players': raw, 'reason': 'retained_identity_changed'})
            continue
        pairs.setdefault(pair_key, {'players': identities, 'matches': [], 'checkedThrough': as_of,
                                    'method': audit['method']})
        request = {'pair': pair_key, 'date': row['match_date'], 'event': row.get('league_name', '')}
        requests[(pair_key, request['date'], request['event'])] = request
        for pid in ids:
            audit['identities'][pid] = {k: people[pid].get(k) for k in ('name', 'birthdate', 'country')}
    targets = {tuple(sorted(p['nativeId'] for p in v['players'])): k for k, v in pairs.items()}
    found = defaultdict(dict)
    games_by_pair = defaultdict(list)
    conflicts = set()
    for r in games:
        pair = tuple(sorted([r['winner_id'], r['loser_id']]))
        if pair not in targets:
            continue
        games_by_pair[pair].append(r)
        t = tours.get(r['tour_id'], {})
        reason = None
        if not ('1990-01-01' <= r['date'] < as_of): reason = 'outside_date_window'
        elif t.get('rank') not in ('0', '1', '2', '3', '4', '5'): reason = 'unsupported_category'
        elif re.search(r'junior|exhibition|next.?gen|laver|hopman|diriyah', t.get('name', ''), re.I): reason = 'excluded_event'
        elif not rules.completed(r['result']): reason = 'unfinished_or_nonstandard'
        elif t.get('court_id') not in rules.SURFACES: reason = 'unknown_surface'
        if reason:
            audit['excluded'][reason] += 1
            continue
        key = targets[pair]
        ids = [p['nativeId'] for p in pairs[key]['players']]
        mid = 'oc-'+'-'.join(r[k] for k in ('winner_id', 'loser_id', 'tour_id', 'round_id'))
        competition = 'Qualifying' if int(r['round_id']) < 4 else {'0': 'ITF', '1': 'Challenger', '5': 'Team'}.get(t['rank'], 'ATP')
        record = {'id': mid, 'date': r['date'], 'winner': ids.index(r['winner_id']),
                  'odds': [None, None], 'surface': rules.SURFACES[t['court_id']],
                  'score': r['result'], 'event': t['name'], 'competition': competition}
        if mid in found[key] and found[key][mid] != record:
            conflicts.add((key, mid))
        found[key][mid] = record
    for key, pair in pairs.items():
        for p in pair['players']:
            if p['nativeId'] not in people or people[p['nativeId']]['name'] != p['name'] or names[normal(p['name'])] != [p['nativeId']]:
                pair['quarantined'] = 'identity_changed'
                audit['unresolved'].append({'players': [v['name'] for v in pair['players']], 'reason': 'retained_identity_changed'})
        dates = Counter(m['date'] for m in found[key].values())
        prior = {m['id']: m for m in pair['matches']}
        for mid, m in found[key].items():
            if (key, mid) in conflicts or dates[m['date']] > 1:
                audit['excluded']['conflicting_result'] += 1
                continue
            if mid in prior and prior[mid] != m:
                pair['quarantined'] = 'result_changed'
                audit['excluded']['retained_result_changed'] += 1
                continue
            prior[mid] = m
        # No replacement or deletion of prior records, even if a source is incomplete.
        pair['matches'] = sorted(prior.values(), key=lambda m: (m['date'], m['id']))
        pair['checkedThrough'] = as_of
    result = {'schema': 1, 'asOf': as_of, 'pairs': dict(sorted(pairs.items()))}
    def event_key(value):
        value = re.sub(r'^ATP\s+(?:Challenger\s+)?', '', value, flags=re.I)
        value = re.sub(r'\s+[-–—]\s+(?:Qualifiers?|Qualifying|R\d+|Q\d+|SF|F|Final|Semi Final|Quarter Final)$', '', value, flags=re.I)
        return normal(re.sub(r'\s+Challenger$', '', value, flags=re.I))
    audit['requests'] = sorted(requests.values(), key=lambda r: (r['date'], r['pair'], r['event']))
    audit['postMatchChecks'] = []
    for request in audit['requests']:
        if request['date'] >= as_of or request['pair'] not in pairs: continue
        ids = {p['nativeId'] for p in pairs[request['pair']]['players']}
        candidates = [g for g in games_by_pair[tuple(sorted(ids))] if abs((date.fromisoformat(g['date'])-date.fromisoformat(request['date'])).days) <= 1
                      and event_key(tours.get(g['tour_id'],{}).get('name','')) == event_key(request['event'])]
        state = 'confirmed' if len(candidates)==1 else 'ambiguous' if candidates else 'awaiting_result'
        if not candidates and (date.fromisoformat(as_of)-date.fromisoformat(request['date'])).days > 3: state = 'overdue_result'
        audit['postMatchChecks'].append({**request,'status':state,'candidateCount':len(candidates),
            'includedCompletedResult':len(candidates)==1 and rules.completed(candidates[0]['result'])})
    def content_only(value):
        return {k: {f: x for f, x in p.items() if f != 'checkedThrough'} for k, p in value.get('pairs', {}).items()}
    if old.get('schema') == 1 and content_only(old) == content_only(result):
        result = old  # A new check date alone must not create another deployment.
    audit.update(pairs=len(pairs), matches=sum(len(p['matches']) for p in pairs.values()),
                 schedule_sha256=hashlib.sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest())
    return result, audit


def validate_supplement(old, new):
    if not new:
        if old and old.get('pairs'): raise ValueError('H2H supplement disappeared')
        return
    if new.get('schema') != 1: raise ValueError('Unsupported H2H supplement')
    for key, pair in new['pairs'].items():
        names = [normal(p['name']) for p in pair['players']]
        if len(names) != 2 or names[0] == names[1] or key != '|'.join(sorted(names)):
            raise ValueError('Invalid supplemental pair')
        ids = set()
        for row in pair['matches']:
            if row['id'] in ids or row['winner'] not in (0, 1) or row['odds'] != [None, None] or not '1990-01-01' <= row['date'] < pair['checkedThrough']:
                raise ValueError('Invalid supplemental result')
            ids.add(row['id'])
    for key, pair in (old or {}).get('pairs', {}).items():
        after = new['pairs'].get(key)
        if not after or after['players'] != pair['players']:
            raise ValueError('Existing supplemental identity changed')
        lookup = {m['id']: m for m in after['matches']}
        if any(lookup.get(m['id']) != m for m in pair['matches']):
            raise ValueError('Existing supplemental result changed')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--oncourt', type=Path, required=True)
    ap.add_argument('--schedule', type=Path, required=True)
    ap.add_argument('--index', type=Path, required=True)
    ap.add_argument('--as-of', required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--audit', type=Path, required=True)
    ap.add_argument('--previous', type=Path)
    args = ap.parse_args()
    old = json.loads(args.previous.read_text(encoding='utf-8')) if args.previous and args.previous.exists() else None
    result, audit = build(args.oncourt, read_csv(args.schedule), json.loads(args.index.read_text(encoding='utf-8'))['players'], args.as_of, old)
    args.output.write_text(json.dumps(result, separators=(',', ':'))+'\n', encoding='utf-8')
    args.audit.write_text(json.dumps(audit, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: audit[k] for k in ('pairs', 'matches', 'unresolved', 'excluded')}))
