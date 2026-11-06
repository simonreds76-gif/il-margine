"""Bounded recovery when this refresh has no fresh upcoming props prices.

Uses the existing authenticated CLI and workflow, never a local provider key.
One fallback dispatch per UTC day, no duplicate active runs, no Telegram calls.
"""
import argparse
import csv
import json
import math
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


def fresh_rows(rows, now, not_before=None):
    fresh = []
    for row in rows:
        captured = timestamp(row.get('capture_ts'))
        start = timestamp(row.get('match_start_utc'))
        try:
            odds = float(row.get('over_odds') or 0)
        except (TypeError, ValueError):
            continue
        if (captured and start and start > now
                and -300 <= (now - captured).total_seconds() <= 6 * 3600
                and (not_before is None or captured >= not_before)
                and math.isfinite(odds) and odds > 1
                and row.get('player') and row.get('opponent')):
            fresh.append(row)
    return fresh


def local_fresh(now, not_before=None):
    rows = []
    for offset in range(2):
        path = ROOT / f'data/tennis-props/inbox/bet365-lines-{(now-timedelta(days=offset)).date()}.csv'
        if path.exists():
            with path.open(encoding='utf-8-sig', newline='') as handle:
                rows.extend(csv.DictReader(handle))
    # The legacy filename contains all approved bookmakers, not just Bet365.
    return len(fresh_rows(rows, now, not_before))


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--not-before', help='Require quotes captured during this refresh')
    args = parser.parse_args(argv)
    not_before = timestamp(args.not_before) if args.not_before else None
    if args.not_before and not_before is None:
        raise ValueError('A timezone-aware refresh start is required')
    now = datetime.now(timezone.utc)
    # Check the local capture FIRST: a cloud cooldown/auth failure must not
    # invalidate fresh prices or replace them with an older hosted snapshot.
    count = local_fresh(now, not_before)
    if args.check_only or count:
        print(f'Fresh upcoming tennis props rows: {count}; no dispatch or sync performed. '
              'Individual bookmaker coverage remains in the capture audit.')
        return 0 if count else 2
    sync(now)
    if local_fresh(now, not_before):
        print('Fresh upcoming hosted props prices available; no fallback request.')
        return 0
    recent = runs()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    decision = recovery_decision(now, recent, state)
    print('Hosted tennis props recovery: ' + decision, flush=True)
    if decision in ('already_attempted', 'recent_attempt'):
        return 2
    if decision == 'dispatch':
        from odds_api_allocation import selected_bookmakers
        bookmakers = selected_bookmakers(scope='tennis_props')
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({'attempt_day': str(now.date()), 'started_at': now.isoformat()}))
        command(['gh', 'workflow', 'run', WORKFLOW, '--repo', REPO, '--ref', 'main',
                 '-f', 'days_ahead=3', '-f', 'max_events=128', '-f', f'bookmakers={bookmakers}',
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
            count = local_fresh(datetime.now(timezone.utc), not_before)
            print(f'Hosted tennis props recovery finished; fresh upcoming rows: {count}')
            return 0 if count else 2
    print('Hosted capture not ready within the bounded wait; stale prices remain blocked.')
    return 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError):
        print('Hosted capture recovery unavailable; existing freshness checks remain enforced.')
        raise SystemExit(2)
