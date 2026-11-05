"""Diagnose unfinished Windows runs after reboot; no models or notifications."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
import argparse
import ctypes
import json
import os

ROOT = Path(__file__).resolve().parents[1]
STEPS = Path('data/tennis-input-health/runtime/steps')


def boot_time():
    if os.name != 'nt':
        return None
    try:
        uptime = ctypes.windll.kernel32.GetTickCount64
        uptime.restype = ctypes.c_ulonglong
        return datetime.now(timezone.utc) - timedelta(milliseconds=uptime())
    except (AttributeError, OSError):
        return None


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result


def interrupted(row, boot, now):
    """Only unfinished work predating this Windows boot is proven interrupted."""
    try:
        return (row.get('status') == 'RUNNING' and boot is not None
                and timestamp(row['started_at']) + timedelta(seconds=5) < boot <= now)
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def reconcile(root, env, transport, *, boot, now):
    if boot is None:
        return []
    grouped = {}
    for path in (root/STEPS).glob('*.json'):
        try:
            row = json.loads(path.read_text(encoding='utf-8-sig'))
            if interrupted(row, boot, now):
                grouped.setdefault(row['run_id'], []).append({k: row.get(k) for k in
                    ('step_id', 'attempt_id', 'label', 'script', 'started_at')})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not grouped:
        return []
    base = env.get('NEXT_PUBLIC_SUPABASE_URL', '').rstrip('/')
    key = env.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not base or not key:
        raise RuntimeError('Restart reconciliation requires existing run-status credentials')
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key}
    query = urlencode({'pipeline':'eq.oncourt-am-refresh', 'host':'eq.laptop-win',
        'status':'eq.running', 'select':'run_id,pipeline,host,status,started_at,details',
        'order':'started_at.desc', 'limit':'10'})
    rows = transport('GET', base+'/rest/v1/run_status?'+query, headers)
    if not isinstance(rows, list):
        raise RuntimeError('Invalid run-status response')
    receipts = []
    for row in rows:
        # Exact correlation, no guessing by date or overwriting completed runs.
        if (row.get('run_id') not in grouped or row.get('pipeline') != 'oncourt-am-refresh'
                or row.get('host') != 'laptop-win' or row.get('status') != 'running'
                or not interrupted({**row, 'status':'RUNNING'}, boot, now)):
            continue
        details = dict(row.get('details') or {})
        diagnosis = {'schema_version':1, 'run_id':row['run_id'],
            'reason':'windows_restarted_during_unfinished_steps', 'observed_at':now.isoformat(),
            'boot_at':boot.isoformat(), 'steps':grouped[row['run_id']]}
        query = urlencode({'run_id':'eq.'+row['run_id'], 'status':'eq.running',
            'details': 'is.null' if row.get('details') is None else
                       'eq.'+json.dumps(row['details'], separators=(',', ':'))})
        changed = transport('PATCH', base+'/rest/v1/run_status?'+query,
            {**headers, 'Prefer':'return=representation'},
            {'status':'aborted', 'finished_at':now.isoformat(), 'error_type':'HostRestartInterrupted',
             'error_message':'Windows restarted while this refresh had unfinished steps; recovery is not yet verified.',
             'details':{**details, 'host_interruption':diagnosis}})
        if not isinstance(changed, list):
            raise RuntimeError('Invalid run-status reconciliation response')
        if len(changed) == 1:
            receipts.append(diagnosis)
        elif changed:
            raise RuntimeError('Unexpected run-status reconciliation count')
    return receipts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args=parser.parse_args()
    # Existing provider and encrypted environment only; never print secrets.
    for name in ('.env.local', 'env.local'):
        path=args.root/name
        if path.exists():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    key, value=line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    from ops_morning_failures import request_json
    try:
        receipts=reconcile(args.root, os.environ, request_json,
                           boot=boot_time(), now=datetime.now(timezone.utc))
    except Exception:
        print('Restart reconciliation unavailable; existing incident and watchdog checks retained.')
        return 1
    if receipts:
        print(f'Recorded {len(receipts)} restart-interrupted refresh(es); recovery remains unverified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
