"""Shared schedule/board integrity checks; no probabilities or selection rules."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

DATABASE = Path('C:/Program Files (x86)/OnCourt/OnCourt.mdb')
STATUS = Path('data/tennis-input-health/pairing-status.json')
BOARD = Path('data/tennis-props/player-props-board.csv')


def csvrows(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def native_epoch(root, database=DATABASE):
    """An update must replace both tours' schedule and identity exports."""
    folder = root / 'data/oncourt'
    files = ['courts.csv'] + [f'{kind}_{tour}.csv' for tour in ('atp', 'wta')
                             for kind in ('today', 'players', 'tours')]
    version = database.stat().st_mtime_ns if database.exists() else None
    result = {}
    for name in files:
        path = folder / name
        if not path.exists() or path.stat().st_size == 0:
            raise ValueError('native_export_missing:' + name)
        if version and path.stat().st_mtime_ns < version:
            raise ValueError('database_newer_than_export:' + name)
        result[name] = {'sha256': sha(path), 'mtime_ns': path.stat().st_mtime_ns}
    return result


def load_env(root):
    for name in ('.env.local', 'env.local'):
        path = root / name
        if path.exists():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def verify_remote_schedule(root, get=None):
    """Verify actual rows, not the legacy uploader's process exit alone."""
    import requests
    get = get or requests.get
    load_env(root)
    base = (os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or os.environ.get('SUPABASE_URL') or '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not base or not key:
        raise ValueError('schedule_verification_credentials_missing')
    path = root / 'data/oncourt/today_atp.csv'
    before = sha(path)
    local = csvrows(path)
    if len(local) > 20000:
        raise ValueError('unexpected_schedule_size')
    cols = ('tour_id', 'player1_id', 'player2_id', 'round_id', 'draw')
    identity = lambda r: tuple(int(r.get(k) or 0) for k in cols) + (str(r.get('result') or '').strip(),)
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key}
    remote = []
    for offset in range(0, len(local) + 1000, 1000):
        response = get(base + '/rest/v1/oncourt_today', headers=headers, params={
            'select': ','.join(cols) + ',result', 'limit': 1000, 'offset': offset,
            'order': 'tour_id.asc,round_id.asc,draw.asc,player1_id.asc,player2_id.asc'}, timeout=15)
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise ValueError('invalid_remote_schedule')
        remote.extend(page)
        if len(page) < 1000:
            break
    if Counter(map(identity, remote)) != Counter(map(identity, local)):
        raise ValueError('remote_schedule_does_not_match_native_export')
    if sha(path) != before:
        raise ValueError('schedule_changed_during_verification')
    return {'rows': len(remote), 'native_schedule_sha256': before,
            'verified_at': datetime.now(timezone.utc).isoformat()}


def expected_props(root, as_of):
    """Use the current generator's exact scope/round rules; never broaden them."""
    sys.path.insert(0, str(root / 'scripts'))
    spec = importlib.util.spec_from_file_location('_pairing_board_scope', root / 'scripts/build-tennis-props-board.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schedules = module.oncourt_schedule_rows('ATP', False, as_of, 3)
    schedules += module.oncourt_schedule_rows('WTA', False, as_of, 3)
    return schedules


def side_key(row, player, opponent):
    return (str(row['tour']), str(row['tour_id']), str(row['round']), str(player), str(opponent))


def board_state(root, as_of, *, expected=None, database=DATABASE):
    epoch = native_epoch(root, database)
    expected = expected_props(root, as_of) if expected is None else expected
    want = Counter(side_key(r, r[a], r[b]) for r in expected
                   for a, b in (('player1_id', 'player2_id'), ('player2_id', 'player1_id')))
    path = root / BOARD
    rows = csvrows(path) if path.exists() and path.stat().st_size else []
    got = Counter(side_key(r, r.get('player_id'), r.get('opponent_id')) for r in rows)
    missing, extra = list((want - got).elements()), list((got - want).elements())
    fresh = path.exists() and path.stat().st_mtime_ns >= max(v['mtime_ns'] for v in epoch.values())
    dated = all(r.get('generation_date') == as_of for r in rows)
    return {'state': 'CURRENT' if fresh and dated and not missing and not extra else 'REBUILD_REQUIRED',
            'as_of': as_of, 'expected_fixtures': len(expected), 'expected_sides': sum(want.values()),
            'actual_sides': len(rows), 'missing_sides': missing, 'unexpected_sides': extra,
            'board_after_exports': fresh, 'generation_date_current': dated, 'native_epoch': epoch,
            'board_sha256': sha(path) if path.exists() else None}


def ensure_props_board(root, as_of, runner=None):
    """Repair a changed draw before any derived model consumes the old board."""
    status_path = root / STATUS
    try:
        before = board_state(root, as_of)
        rebuilt = before['state'] != 'CURRENT'
        if rebuilt:
            command = [sys.executable, str(root / 'scripts/build-tennis-props-board.py'),
                       '--as-of', as_of, '--days-ahead', '3']
            if runner is None:
                subprocess.run(command, cwd=root, check=True, timeout=600)
            elif runner(command, 'Recover projections from current native pairings', fatal=False, timeout_seconds=600):
                raise RuntimeError('projection_recovery_failed')
        after = board_state(root, as_of)
        if after['native_epoch'] != before['native_epoch']:
            raise ValueError('native_pairings_changed_during_board_rebuild')
        if after['state'] != 'CURRENT':
            raise ValueError('projection_recovery_incomplete')
        after.update(rebuilt=rebuilt, checked_at=datetime.now(timezone.utc).isoformat())
        atomic(status_path, after)
        return after
    except Exception as exc:
        atomic(status_path, {'state': 'BLOCKED', 'as_of': as_of,
                            'reason': type(exc).__name__ + ': ' + str(exc),
                            'checked_at': datetime.now(timezone.utc).isoformat()})
        raise


def verify_derived_board(root, name):
    """Check complete current pair identities, not merely a rewritten timestamp."""
    base = root / BOARD
    target = root / 'data/tennis-props/shadow' / name
    if not target.exists() or target.stat().st_mtime_ns < base.stat().st_mtime_ns:
        raise ValueError('derived_board_predates_current_projections:' + name)
    parent = [r for r in csvrows(base) if r.get('tour') == 'ATP' and r.get('surface') in {'Hard', 'Clay'}]
    actual = csvrows(target) if target.stat().st_size else []
    if name == 'aces-v3-projection-board.csv':
        wanted = Counter(side_key(r, r['player_id'], r['opponent_id']) for r in parent)
        got = Counter(side_key(r, r.get('player_id'), r.get('opponent_id')) for r in actual)
    else:
        def key(row, a, b):
            return (row.get('date'), row.get('tour'), row.get('tournament'), row.get('round'),
                    *sorted((row.get(a, ''), row.get(b, ''))))
        wanted = Counter({key(r, 'player', 'opponent'): 1 for r in parent})
        got = Counter(key(r, 'player1', 'player2') for r in actual)
    missing, extra = list((wanted - got).elements()), list((got - wanted).elements())
    if missing or extra:
        raise ValueError('derived_pairing_mismatch:' + name + ':' + json.dumps({'missing': missing, 'extra': extra}))
    return {'file': name, 'rows': len(actual), 'missing': 0, 'unexpected': 0, 'sha256': sha(target)}


def clear_empty_derived_scope(root):
    """Remove obsolete current projections when no eligible ATP pair remains.

    Only derived current boards change; observations/results are never touched.
    Keep this outside the frozen model generator and its fingerprint.
    """
    rows = csvrows(root / BOARD)
    if any(r.get('tour') == 'ATP' and r.get('surface') in {'Hard', 'Clay'} for r in rows):
        return False
    folder = root / 'data/tennis-props/shadow'
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('aces-v3-projection-board.csv', 'venue-ace-factor-v1-projection-board.csv',
                 'most-aces-1x2-board.csv', 'most-aces-direct-1x2-board.csv'):
        path = folder / name
        header = 'date,tour,tournament,round,player,opponent,player1,player2,player_id,opponent_id,tour_id'
        if path.exists() and path.stat().st_size:
            header = path.read_text(encoding='utf-8-sig').splitlines()[0]
        path.write_text(header + '\n', encoding='utf-8')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--verify-sync', action='store_true')
    parser.add_argument('--check-board', action='store_true')
    parser.add_argument('--ensure-board', action='store_true')
    parser.add_argument('--as-of', default=datetime.now(timezone.utc).date().isoformat())
    args = parser.parse_args()
    if args.ensure_board:
        result = ensure_props_board(args.root, args.as_of)
    elif args.check_board:
        result = board_state(args.root, args.as_of)
    else:
        result = {'native_epoch': native_epoch(args.root)}
        if args.verify_sync:
            result['remote_schedule'] = verify_remote_schedule(args.root)
    print(json.dumps(result))
    return 1 if result.get('state') == 'REBUILD_REQUIRED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
