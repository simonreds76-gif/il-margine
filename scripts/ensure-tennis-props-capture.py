"""Bounded local recovery when GitHub's scheduled Bet365 capture did not run.

Uses the existing authenticated CLI and workflow, never a local provider key.
One fallback dispatch per UTC day, no duplicate active runs, no Telegram calls.
"""
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = 'simonreds76-gif/il-margine'
WORKFLOW = 'tennis-props-bet365-refresh.yml'
STATE = ROOT / 'data/tennis-props/hosted-capture-recovery.json'


def timestamp(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return stamp if stamp.tzinfo else None
    except ValueError:
        return None


def fresh_rows(rows, now):
    fresh = []
    for row in rows:
        captured = timestamp(row.get('capture_ts'))
        start = timestamp(row.get('match_start_utc'))
        if (captured and start and start > now
                and -300 <= (now - captured).total_seconds() <= 6 * 3600
                and row.get('over_odds') and row.get('player') and row.get('opponent')):
            fresh.append(row)
    return fresh


def local_fresh(now):
    rows = []
    for offset in range(2):
        path = ROOT / f'data/tennis-props/inbox/bet365-lines-{(now-timedelta(days=offset)).date()}.csv'
        if path.exists():
            with path.open(encoding='utf-8-sig', newline='') as handle:
                rows.extend(csv.DictReader(handle))
    return len(fresh_rows(rows, now))


def command(args, timeout=25):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # Do not echo auth/transport output, which may contain sensitive URLs.
        raise RuntimeError('Hosted capture command failed: ' + args[0])
    return result.stdout


def sync(now):
    command([sys.executable, 'scripts/sync-tennis-props-hosted-captures.py',
             '--as-of', str(now.date()), '--lookback-days', '1'], timeout=110)


def runs():
    return json.loads(command(['gh', 'run', 'list', '--repo', REPO, '--workflow', WORKFLOW,
        '--limit', '10', '--json', 'databaseId,status,conclusion,createdAt']))


def recovery_decision(now, recent, state):
    if any(run.get('status') != 'completed' for run in recent):
        return 'wait'
    if state.get('attempt_day') == str(now.date()):
        return 'already_attempted'
    if any((created := timestamp(run.get('createdAt'))) and
           (now-created).total_seconds() < 1800 for run in recent):
        return 'recent_attempt'
    return 'dispatch'


def main():
    now = datetime.now(timezone.utc)
    if '--check-only' in sys.argv:
        count = local_fresh(now)
        print(f'Fresh upcoming Bet365 rows: {count}; no dispatch or sync performed.')
        return 0 if count else 2
    sync(now)
    if local_fresh(now):
        print('Fresh hosted Bet365 prices already available; no fallback request.')
        return 0
    recent = runs()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    decision = recovery_decision(now, recent, state)
    print('Hosted Bet365 recovery: ' + decision, flush=True)
    if decision in ('already_attempted', 'recent_attempt'):
        return 2
    if decision == 'dispatch':
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({'attempt_day': str(now.date()), 'started_at': now.isoformat()}))
        command(['gh', 'workflow', 'run', WORKFLOW, '--repo', REPO, '--ref', 'main',
                 '-f', 'days_ahead=3', '-f', 'max_events=128', '-f', 'bookmakers=Bet365',
                 '-f', 'commit_results=true', '-f', 'probe_markets=false', '-f', 'price_shape_probe=false'])
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        time.sleep(15)
        current = runs()
        if any(run.get('status') != 'completed' for run in current):
            continue
        if any((created := timestamp(run.get('createdAt'))) and
               created >= now - timedelta(minutes=30) and run.get('conclusion') == 'success'
               for run in current):
            sync(datetime.now(timezone.utc))
            count = local_fresh(datetime.now(timezone.utc))
            print(f'Hosted Bet365 recovery finished; fresh upcoming rows: {count}')
            return 0 if count else 2
    print('Hosted capture not ready within the bounded wait; stale prices remain blocked.')
    return 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError):
        print('Hosted capture recovery unavailable; existing freshness checks remain enforced.')
        raise SystemExit(2)
