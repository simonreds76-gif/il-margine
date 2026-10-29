"""Frozen reviewed source validator for Scout opposition inputs only."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math, os, uuid
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
SURFACES = {'Hard', 'I.hard', 'Clay', 'Grass', 'Carpet'}

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_history(root, include_adult_itf=False):
    from tennis_direct_history import crosswalk
    from tennis_event_integrity import completed_score, event_phase
    from tennis_source_contract import court_surfaces
    native = root / 'data/oncourt'
    sack = root / 'data/sackmann'
    source = [native / 'players_atp.csv', native / 'tours_atp.csv', native / 'games_atp.csv', native / 'courts.csv', sack / 'atp_players.csv', root / 'data/tennis-props/player-name-aliases.csv']
    paths = sorted(sack.glob('atp_matches_*.csv'))
    source += paths
    before = {str(p.relative_to(root)): sha(p) for p in source}
    players = list(read_csv(source[0]))
    names = {r['id']: r['name'] for r in players}
    tours = {r['id']: r for r in read_csv(source[1])}
    surfaces = court_surfaces(source[3], combine_hard=False)
    mapping, audit = crosswalk(players, list(read_csv(source[4])), list(read_csv(source[5])))
    inverse = defaultdict(list)
    for a, b in mapping.items():
        inverse[b].append(a)
    unique = {k: v[0] for k, v in inverse.items() if len(v) == 1}
    excluded = Counter()
    groups = defaultdict(list)
    keys = {}
    conflicts = set()
    for g in read_csv(source[2]):
        t = tours.get(g['tour_id'], {})
        surface = surfaces.get(t.get('court_id'))
        if t.get('rank') not in ({'0', '1', '2', '3', '4'} if include_adult_itf else {'1', '2', '3', '4'}) or event_phase(g['round_id']) is None:
            excluded['unsupported_level_or_round'] += 1
            continue
        if surface not in SURFACES:
            excluded['unknown_surface'] += 1
            continue
        if not completed_score(g['result']):
            excluded['unfinished_retirement_walkover'] += 1
            continue
        if g['winner_id'] == g['loser_id'] or any((not names.get(g[s]) or '/' in names[g[s]] or '&' in names[g[s]] for s in ('winner_id', 'loser_id'))):
            excluded['unknown_identity_or_team'] += 1
            continue
        try:
            day = date.fromisoformat(g['date'])
            edition = date.fromisoformat(t['date'])
        except ValueError:
            excluded['invalid_date'] += 1
            continue
        if not -14 <= (day - edition).days <= 35:
            excluded['date_outside_edition'] += 1
            continue
        key = ':'.join([g['tour_id'], g['round_id'], *sorted([g['winner_id'], g['loser_id']], key=int)])
        row = {'key': key, 'date': day.isoformat(), 'available_date': day.isoformat(), 'tournament_id': int(g['tour_id']), 'tournament': t['name'], 'round': int(g['round_id']), 'winner': int(g['winner_id']), 'loser': int(g['loser_id']), 'surface': surface, 'rank': int(t['rank']), 'score': g['result'].strip(), 'source': 'oncourt', 'date_policy': 'native_result_date'}
        if key in keys:
            if keys[key] != row:
                conflicts.add(key)
            else:
                excluded['duplicate_native'] += 1
        else:
            keys[key] = row
            groups[g['tour_id']].append(row)
    for tid, rows in groups.items():
        if len(rows) > 10 and len({r['date'] for r in rows}) == 1:
            safe = (date.fromisoformat(max(rows[0]['date'], tours[tid]['date'])) + timedelta(days=14)).isoformat()
            for r in rows:
                r['available_date'] = safe
                r['date_policy'] = 'edition_date_plus_14d'
            excluded['date_delayed_matches'] += len(rows)
    index = defaultdict(list)
    for r in keys.values():
        index[frozenset((r['winner'], r['loser']))].append(r)
    sack_audit = Counter()
    used = set()
    norm = lambda s: ' '.join(str(s).replace('(', '').replace(')', '').split())
    for path in paths:
        for s in read_csv(path):
            if not completed_score(s.get('score')):
                sack_audit['unfinished'] += 1
                continue
            if s.get('tourney_level') not in {'A', 'M', 'G', 'C'}:
                sack_audit['unsupported'] += 1
                continue
            w, l = (unique.get(s.get('winner_id')), unique.get(s.get('loser_id')))
            if not w or not l:
                sack_audit['unmapped_unique_identity'] += 1
                continue
            try:
                start = datetime.strptime(s['tourney_date'], '%Y%m%d').date()
            except (KeyError, ValueError):
                sack_audit['invalid_date'] += 1
                continue
            possible = [r for r in index[frozenset((int(w), int(l)))] if -7 <= (date.fromisoformat(r['date']) - start).days <= 21]
            candidates = [r for r in possible if r['winner'] == int(w) and norm(r['score']) == norm(s.get('score')) and (('Hard' if r['surface'] == 'I.hard' else r['surface']) == s.get('surface'))]
            if len(candidates) != 1:
                sack_audit['ambiguous_or_conflicting' if possible else 'no_native_result_date'] += 1
                conflicts.update((r['key'] for r in possible))
                continue
            r = candidates[0]
            if r['key'] in used:
                sack_audit['duplicate_archive'] += 1
                continue
            used.add(r['key'])
            r['source'] = 'sackmann_with_native_date'
            r['archive_id'] = s.get('tourney_id')
            sack_audit['primary_reconciled'] += 1
    rows = sorted((r for k, r in keys.items() if k not in conflicts), key=lambda r: (r['available_date'], r['tournament_id'], r['round'], r['key']))
    excluded['conflicting_fixture'] = len(conflicts)
    if before != {str(p.relative_to(root)): sha(p) for p in source}:
        raise ValueError('Source changed during rebuild')
    return (rows, {'source_hashes': before, 'native_exclusions': dict(excluded), 'archive_reconciliation': dict(sack_audit), 'unique_crosswalk': len(unique), 'ambiguous_crosswalk': sum((len(v) > 1 for v in inverse.values())), 'sources': dict(Counter((r['source'] for r in rows))), 'limitations': ['Current corrected source snapshot, not historically archived knowledge.', 'Archive primary only where unique native identity, completed score and result date reconcile; remaining validated native history retained.', 'Unmatched archive matches withheld; no guessed actual match dates. ATP and Challenger only.']})
