"""Offline identity sidecar. Never changes model inputs, targets or settlements.

Reep establishes a registry link, not permission to fetch another provider,
employment status, statistical equivalence or an independently verified identity.
"""
import csv
import gzip
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REGISTRY = Path('data/aerial/identity-registry.json.gz')


def read(path, default=None):
    if not path.exists():
        return default
    body = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return json.loads(body.decode('utf-8'))


def write(path, value):
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if path.suffix == '.gz':
        body = gzip.compress(body, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(body)
    temp.replace(path)


def folded(value):
    value = (value or '').casefold().translate(str.maketrans({'ø': 'o', 'ł': 'l', 'đ': 'd', 'ð': 'd', 'þ': 'th'}))
    return ''.join(c for c in unicodedata.normalize('NFKD', value)
                   if c.isalnum() and not unicodedata.combining(c))


def compatible_label(local_names, registry_label):
    """Sanity check AFTER an exact ID join, never a name-to-ID matching rule.

    Permit omitted middle names/additional surnames in the same order. Nicknames
    and initials still require review. Identity comes from the full native ID.
    """
    if not local_names:
        return True
    full = [folded(t) for t in re.findall(r'[^\W_]+', registry_label or '')]
    for name in local_names:
        if folded(name) == folded(registry_label):
            return True
        short = [folded(t) for t in re.findall(r'[^\W_]+', name)]
        if len(short) < 2 or any(len(t) < 2 for t in short):
            continue
        remaining = iter(full)
        if all(any(token == candidate for candidate in remaining) for token in short):
            return True
    return False


def key(provider, namespace, external_id):
    return '|'.join((provider, namespace, str(external_id)))


def canonical(rid, redirects):
    seen = set()
    while rid in redirects:
        if rid in seen:
            return None
        seen.add(rid)
        rid = redirects[rid]
        if not rid:
            return None
    return rid or None


def resolve(registry, provider, namespace, external_id, target_provider, target_namespace,
            existing_target_id=None):
    """Exact, namespace-aware lookup; never resolve by name or overwrite an ID."""
    if registry.get('schema_version') != 1:
        return {'status': 'registry_unavailable'}
    entry = registry.get('entities', {}).get(key(provider, namespace, external_id))
    if not entry:
        return {'status': 'not_in_registry'}
    if entry['status'] != 'linked':
        return {'status': entry['status']}
    target = entry.get('targets', {}).get(key(target_provider, target_namespace, ''))
    if not target:
        return {'status': 'provider_not_mapped'}
    if target['status'] != 'linked':
        return {'status': target['status']}
    value = target['id']
    if existing_target_id is not None and str(existing_target_id) != value:
        return {'status': 'existing_id_conflict'}
    return {'status': 'registry_linked', 'id': value, 'reep_id': entry['reep_id'],
            'release': registry['release'], 'independently_verified': False}


def inventory(root):
    """Use native IDs. Penalty names may select only an exact same-club roster row."""
    root = Path(root)
    entities = {}
    scopes = defaultdict(set)
    unresolved = []
    inputs = {}

    def load(relative, default):
        path = root / relative
        if path.exists():
            inputs[str(relative).replace('\\', '/')] = hashlib.sha256(path.read_bytes()).hexdigest()
        return read(path, default)

    def add(pid, name, scope):
        if pid is None or str(pid) in ('', 'None'):
            return
        k = key('fotmob', 'person', pid)
        entity = entities.setdefault(k, {'provider': 'fotmob', 'namespace': 'person',
                                        'external_id': str(pid), 'names': set()})
        if name:
            entity['names'].add(name)
        scopes[scope].add(k)

    heights = load(Path('data/aerial/heights.json.gz'), {})
    by_club_name = defaultdict(set)
    for pid, row in heights.items():
        if str(row.get('id')) != str(pid):
            unresolved.append({'scope': 'air_control', 'reason': 'source_id_conflict', 'id': pid})
            continue
        add(pid, row.get('name'), 'air_control_roster')
        if row.get('role_group') == 'keepers' or row.get('positions') == 'GK':
            add(pid, row.get('name'), 'goalkeeper_roster')
        if row.get('source_kind') == 'current_squad' and row.get('team_id'):
            by_club_name[(str(row['team_id']), folded(row.get('name')))].add(str(pid))

    history = load(Path('data/aerial/history.json.gz'), {})
    for match in history.get('matches', []):
        for row in match.get('players', []):
            add(row.get('id'), None, 'air_control_history')

    for path in sorted((root / 'data/goalkeeper-saves/verified-player-targets').rglob('*.json')):
        packet = load(path.relative_to(root), {})
        for row in packet.get('rows', []):
            if row.get('is_goalkeeper'):
                add(row.get('player_id'), row.get('player'), 'goalkeeper_observed_targets')

    logos = load(Path('data/goalscorer/team-logo-map.json'), {})
    penalty_slots = 0
    for league in ('epl', 'la-liga', 'serie-a', 'bundesliga', 'ligue-1'):
        teams = logos.get('leagues', {}).get(league, {}).get('teams', {})
        club_ids = defaultdict(set)
        for name, row in teams.items():
            for label in (name, row.get('fotmob_name'), row.get('team_key')):
                if label and row.get('fotmob_team_id'):
                    club_ids[folded(label)].add(str(row['fotmob_team_id']))
        penalties = load(Path(f'data/goalscorer/{league}-penalty-takers.json'), {})
        for club, row in penalties.items():
            if club.startswith('_') or not isinstance(row, dict):
                continue
            tids = club_ids.get(folded(club), set())
            for rank in ('primary', 'secondary', 'tertiary'):
                name = row.get(rank)
                if not isinstance(name, str) or not name.strip():
                    continue
                penalty_slots += 1
                pids = by_club_name.get((next(iter(tids)), folded(name)), set()) if len(tids) == 1 else set()
                if len(pids) == 1:
                    add(next(iter(pids)), name, 'penalty_takers')
                else:
                    unresolved.append({'scope': 'penalty_takers', 'league': league, 'club': club,
                                       'name': name, 'rank': rank,
                                       'reason': 'club_unresolved' if len(tids) != 1 else 'no_unique_same_club_roster_match'})

    # These historical selections have names but no native player ID. Do not
    # attach today's roster to a historical bet, especially across transfers.
    name_only = 0
    ledger = root / 'data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv'
    if ledger.exists():
        inputs[str(ledger.relative_to(root)).replace('\\', '/')] = hashlib.sha256(ledger.read_bytes()).hexdigest()
        with ledger.open(encoding='utf-8-sig', newline='') as stream:
            name_only = sum(1 for row in csv.DictReader(stream) if not row.get('player_id'))

    for row in entities.values():
        row['names'] = sorted(row['names'])
    return {'entities': entities, 'scopes': {k: sorted(v) for k, v in scopes.items()},
            'unresolved': unresolved, 'input_sha256': inputs, 'penalty_slots': penalty_slots,
            'gk_ledger_rows_without_player_id': name_only}


def audit(root, registry=None):
    root = Path(root)
    registry = registry if registry is not None else read(root / REGISTRY, {})
    population = inventory(root)
    # Recheck labels against the current input snapshot, not only build-time
    # names. This does not release previous quarantines automatically.
    registry = dict(registry, entities=dict(registry.get('entities', {})))
    for k, local in population['entities'].items():
        entry = registry['entities'].get(k)
        if entry and entry['status'] == 'linked' and not compatible_label(local['names'], entry.get('registry_label')):
            registry['entities'][k] = dict(entry, status='name_review_required')
    summaries = {}
    for scope, keys in population['scopes'].items():
        counts = Counter(registry.get('entities', {}).get(k, {}).get('status', 'not_in_registry') for k in keys)
        summaries[scope] = {'unique_players': len(keys), 'status': dict(counts), 'providers': {}}
        for provider, namespace in [('sofascore', 'player'), ('api_football', 'player'), ('opta', 'person')]:
            results = Counter(resolve(registry, 'fotmob', 'person', k.split('|')[2], provider, namespace)['status'] for k in keys)
            summaries[scope]['providers'][provider] = dict(results)
    return {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'registry_release': registry.get('release'), 'mode': 'advisory_only',
            'scopes': summaries, 'penalty_slots': population['penalty_slots'],
            'gk_ledger_rows_without_player_id': population['gk_ledger_rows_without_player_id'],
            'unresolved': population['unresolved'], 'input_sha256': population['input_sha256'],
            'limits': ['No model, hierarchy, result or price changes.',
                       'Registry identity links do not verify provider statistics or current employment.',
                       'Roster evidence dates remain in the source files; registry release is not a freshness guarantee.']}


def refresh_health(root):
    """Existing batch hook: local reads only; failure cannot stop publication."""
    try:
        report = audit(root)
        write(Path(root) / 'data/aerial/identity-health.json', report)
        return report
    except Exception as exc:
        report = {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
                  'mode': 'advisory_only', 'status': 'error', 'error': str(exc)}
        write(Path(root) / 'data/aerial/identity-health.json', report)
        return report
