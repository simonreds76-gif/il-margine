"""Isolate verified identity conflicts; never merge fuzzy player identities."""
from collections import defaultdict
import csv
import json
from datetime import datetime, timezone
from tennis_props_names import norm_name

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))

def inspect_identity_buckets(root, baseline):
    verified=[];unverified=[]
    for tour in ('atp','wta'):
        native={r['id']:r for r in read(root/f'data/oncourt/players_{tour}.csv')}
        archive=read(root/f'data/sackmann/{tour}_players.csv');index=defaultdict(list)
        active={str(r['player_id']) for r in baseline if r['tour']==tour.upper()}
        for player in archive:
            tokens=norm_name(player['name_first']+' '+player['name_last']).split()
            if len(tokens)>=2 and player['player_id'] in active:index[(tokens[0],tokens[-1])].append(player)
        singles={(r['player_id'][3:],r['player_name']) for r in baseline if r['tour']==tour.upper() and r['player_id'].startswith('oc:') and '/' not in r['player_name'] and '&' not in r['player_name']}
        for oid,name in sorted(singles):
            tokens=norm_name(name).split()
            if len(tokens)<2:continue
            candidates=index.get((tokens[0],tokens[-1]),[]);person=native.get(oid,{})
            if not candidates:continue
            same=[p for p in candidates if person.get('birthdate') and person['birthdate'].replace('-','')==p.get('dob') and person.get('country') and person['country']==p.get('ioc')]
            entry=dict(tour=tour.upper(),native_id=oid,name=name,archive_ids=[p['player_id'] for p in same or candidates])
            (verified if same else unverified).append(entry)
    return dict(state='VERIFIED_SPLITS' if verified else 'NO_VERIFIED_SPLITS',
                verified_splits=len(verified), conflicts=verified, unverified_name_candidates=unverified,
                rule='Explicit aliases only; splits require matching birthdate and country. No inferred merge.')


def verify_identity_buckets(root, baseline):
    """Strict compatibility check for callers that require an all-clean history."""
    audit = inspect_identity_buckets(root, baseline)
    if audit['conflicts']:
        raise ValueError('verified_split_player_histories:' + str(audit['conflicts']))
    return audit


def quarantine_identity_buckets(root, baseline):
    """Remove only conflicting player buckets, retaining opponents' valid stats."""
    audit = inspect_identity_buckets(root, baseline)
    quarantine = []
    for conflict in audit['conflicts']:
        ids = {'oc:' + conflict['native_id'], *conflict['archive_ids']}
        names = {r['player_name'] for r in baseline
                 if r['tour'] == conflict['tour'] and str(r['player_id']) in ids}
        quarantine.append(dict(conflict, player_ids=sorted(ids), names=sorted(names),
                               reason='VERIFIED_SPLIT_IDENTITY'))
    blocked = {(q['tour'], pid) for q in quarantine for pid in q['player_ids']}
    clean = [r for r in baseline if (r['tour'], str(r['player_id'])) not in blocked]
    audit.update(state='QUARANTINED' if quarantine else 'NO_VERIFIED_SPLITS',
                 quarantined_players=quarantine, excluded_baseline_rows=len(baseline)-len(clean))
    return clean, audit


def exclude_quarantined_activity(rows, audit):
    blocked = {(q['tour'], pid) for q in audit.get('quarantined_players', []) for pid in q['player_ids']}
    return [r for r in rows if (r['tour'], str(r['player_id'])) not in blocked]


def partition_schedules(schedules, history, as_of):
    """Hold both sides of an affected fixture; unrelated fixtures stay available."""
    quarantine = history.get('identity_audit', {}).get('quarantined_players', [])
    if quarantine and (history.get('state') != 'CURRENT' or history.get('as_of') != str(as_of)):
        raise ValueError('Identity quarantine is not from current validated inputs')
    ready, held = [], []
    for row in schedules:
        tour = str(row.get('tour', '')).upper()
        affected = [q for q in quarantine if q['tour'] == tour and any(
            str(row.get(side+'_id', '')) == q['native_id']
            or norm_name(row.get(side, '')) in {norm_name(n) for n in q['names']}
            for side in ('player1', 'player2'))]
        if affected:
            held.append(dict(row, quarantine_reason='VERIFIED_SPLIT_IDENTITY',
                             quarantined_native_ids=sorted({q['native_id'] for q in affected})))
        else:
            ready.append(row)
    return ready, held


QUARANTINE_PATH = 'data/tennis-input-health/props-identity-quarantine.json'


def load_quarantine(root):
    path = root / QUARANTINE_PATH
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or not isinstance(value.get('held_fixtures'), list):
        raise ValueError('Invalid props fixture quarantine')
    return value


def fixture_blocked(row, receipt):
    """Reject current recommendations only; historical observations stay intact.

    An old hold cannot expire into permission to bet. Only a validated rebuild
    clears it. Use native IDs where supplied; names are an exact fallback for
    current derived boards which do not retain those IDs.
    """
    tour = str(row.get('tour') or '').upper()
    ids = {str(row.get(k) or '') for k in ('player_id', 'opponent_id', 'player1_id', 'player2_id')}
    ids.update(str(v) for v in row.get('players', []))
    ids.discard('')
    names = {norm_name(row.get(k) or '') for k in ('player', 'opponent', 'player1', 'player2')}
    names.update(norm_name(v) for v in row.get('names', []))
    names.discard('')
    for held in receipt.get('held_fixtures', []):
        if tour and tour != str(held.get('tour') or '').upper():
            continue
        hids = {str(held.get(k) or '') for k in ('player1_id', 'player2_id')}
        hids.discard('')
        hnames = {norm_name(held.get(k) or '') for k in ('player1', 'player2')}
        hnames.discard('')
        # Both players in this fixture are held. Conservative name overlap also
        # catches an old pairing for the same affected player in a derived file.
        if ids & hids or names & hnames:
            return True
    return False


def publish_quarantine(root, history, ready, held, as_of, now=None):
    from tennis_pairing_consistency import atomic
    now = now or datetime.now(timezone.utc)
    previous = load_quarantine(root)
    key = lambda r: (r.get('tour'), r.get('tour_id'), r.get('round', r.get('round_id')),
                     *sorted((str(r.get('player1_id', '')), str(r.get('player2_id', '')))), r.get('quarantine_reason'))
    first = {key(r): r.get('first_seen_at', previous.get('generated_at')) for r in previous.get('held_fixtures', [])}
    entries = []
    for row in held:
        seen = first.get(key(row)) or now.isoformat()
        age = max(0, (now - datetime.fromisoformat(seen)).total_seconds() / 86400)
        entries.append(dict(row, first_seen_at=seen, last_seen_at=now.isoformat(), age_days=round(age, 3)))
    receipt = dict(as_of=as_of, generated_at=now.isoformat(),
                   state='PARTIAL_QUARANTINE' if held else 'CLEAR',
                   history_version=history['version'],
                   history_fingerprint=history.get('output_hashes', {}).get('player-props-baseline.csv', ''),
                   ready_fixtures=len(ready), held_fixtures=entries,
                   review_required=len(held) >= 5 or any(r['age_days'] >= 2 for r in entries))
    atomic(root / QUARANTINE_PATH, receipt)
    return receipt


def remove_held_current_rows(root, receipt):
    """Invalidate only replaceable current views, never ledgers or captures."""
    from tennis_pairing_consistency import atomic
    if not receipt.get('held_fixtures'):
        return {}
    props = root / 'data/tennis-props'
    paths = [props / 'shadow' / name for name in (
        'aces-v3-projection-board.csv', 'venue-ace-factor-v1-projection-board.csv',
        'most-aces-1x2-board.csv', 'most-aces-direct-1x2-board.csv')]
    paths += [props / f'comparison{suffix}-{receipt["as_of"]}.csv' for suffix in ('', '-v3-aces')]
    removed = {}
    for path in paths:
        if not path.exists() or not path.stat().st_size:
            continue
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream); fields = reader.fieldnames; rows = list(reader)
        kept = [r for r in rows if not fixture_blocked(r, receipt)]
        if len(kept) != len(rows):
            temp = path.with_suffix('.quarantine.tmp')
            with temp.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(kept)
            temp.replace(path); removed[str(path.relative_to(root))] = len(rows)-len(kept)
    path = props / 'shadow/most-aces-current.json'
    if path.exists():
        value = json.loads(path.read_text(encoding='utf-8'))
        rows = value.get('matches', [])
        value['matches'] = [r for r in rows if not fixture_blocked(r, receipt)]
        value['fixture_quarantine'] = receipt
        if len(rows) != len(value['matches']):
            removed[str(path.relative_to(root))] = len(rows)-len(value['matches'])
        atomic(path, value)
    return removed
