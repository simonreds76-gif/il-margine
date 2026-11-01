"""Durable step receipts for tennis orchestration; never prices or settles bets."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import signal
import uuid
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
REL = Path('data/tennis-input-health/runtime/steps')
DEFAULT_TIMEOUT = 1800
PROCESS_RUN = uuid.uuid4().hex

def utc():
    return datetime.now(timezone.utc)

def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))

def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}

def begin(root, label, script, timeout, *, now=None, run_id=None):
    now = now or utc()
    timeout = timeout or DEFAULT_TIMEOUT
    identity = hashlib.sha256((script + '\n' + label).encode()).hexdigest()[:24]
    path = root / REL / (identity + '.json')
    old = read(path)
    data = dict(step_id=identity, attempt_id=uuid.uuid4().hex, label=label, script=script,
                run_id=run_id or os.environ.get('TENNIS_RUNTIME_RUN_ID') or PROCESS_RUN,
                status='RUNNING', started_at=now.isoformat(),
                deadline=(now + timedelta(seconds=timeout)).isoformat(), timeout_seconds=timeout,
                last_success_at=old.get('last_success_at'),
                unresolved_failure=old.get('unresolved_failure'))
    atomic(path, data)
    return data

def finish(root, token, exit_code, *, now=None):
    now = now or utc()
    path = root / REL / (token['step_id'] + '.json')
    data = read(path)
    if data.get('attempt_id') != token['attempt_id']:
        raise RuntimeError('A newer step attempt exists; refusing to overwrite its health')
    duration = max(0, (now - stamp(data['started_at'])).total_seconds())
    data.update(status='OK' if exit_code == 0 else 'TIMED_OUT' if exit_code == 124 else 'FAILED',
                exit_code=exit_code, finished_at=now.isoformat(), duration_seconds=round(duration, 3),
                near_budget=duration >= .8 * data['timeout_seconds'])
    if exit_code == 0:
        data.update(last_success_at=now.isoformat(), unresolved_failure=None)
    else:
        data['unresolved_failure'] = dict(status=data['status'], failed_at=now.isoformat(),
                                          exit_code=exit_code)
    atomic(path, data)
    return data

def observed_run(cmd, *, root, label, timeout=None, **kwargs):
    """Keep subprocess semantics; record before launch and on every exit path."""
    script = next((Path(str(x)).name for x in cmd if str(x).endswith(('.py', '.ps1'))), Path(str(cmd[0])).name)
    timeout = timeout or DEFAULT_TIMEOUT
    token = begin(root, label, script, timeout)
    code = 1
    try:
        if kwargs.pop('capture_output', False):
            kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.name != 'nt':
            kwargs['start_new_session'] = True
        with subprocess.Popen(cmd, **kwargs) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Terminate descendants too: orphaned writers must not outlive
                # a timed-out model and modify files behind the next refresh.
                if os.name == 'nt':
                    try:
                        subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
                    finally:
                        if process.poll() is None:process.kill()
                else:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                process.communicate(timeout=10)
                raise
            code = process.returncode
            return subprocess.CompletedProcess(cmd,code,stdout,stderr)
    except subprocess.TimeoutExpired:
        code = 124
        raise
    finally:
        finish(root, token, code)

def summary(root=ROOT, *, now=None, run_id=None):
    now = now or utc()
    steps, issues, near = [], [], []
    for path in sorted((root / REL).glob('*.json')):
        try:
            row = read(path)
            if run_id and row.get('run_id') != run_id:
                continue
            state = row['status']
            if state not in {'OK','FAILED','TIMED_OUT','RUNNING'}:
                raise ValueError('Unknown receipt state')
            if state == 'RUNNING' and now > stamp(row['deadline']) + timedelta(seconds=30):
                state = 'DEADLINE_EXCEEDED'
            item = {k: row.get(k) for k in ('step_id','label','script','run_id','started_at','deadline',
                    'finished_at','duration_seconds','timeout_seconds','last_success_at')}
            item['status'] = state
            steps.append(item)
            if state in {'FAILED','TIMED_OUT','DEADLINE_EXCEEDED'} or row.get('unresolved_failure'):
                item = dict(item, issue=state if state != 'RUNNING' else 'RETRYING_AFTER_FAILURE')
                issues.append(item)
            if row.get('near_budget'):
                near.append(item)
        except (ValueError, OSError, KeyError, TypeError):
            issues.append(dict(step_id=path.stem, label='Unreadable tennis step receipt', issue='HEALTH_READ_FAILED'))
    return dict(schema_version=1, generated_at=now.isoformat(),
                state='DEGRADED' if issues else 'RUNNING' if any(s['status']=='RUNNING' for s in steps)
                else 'OK' if steps else 'NOT_YET_OBSERVED',
                step_count=len(steps), issues=issues, near_budget=near, steps=steps)

def overlay_feed_health(feed, runtime):
    result = dict(feed)
    if runtime['issues']:
        result.update(state='RUNTIME_STEP_FAILED', structural_error=True,
                      runtime_issues=runtime['issues'], underlying_feed_state=feed.get('state'))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('begin');b.add_argument('--label64',required=True);b.add_argument('--script',required=True)
    b.add_argument('--timeout',type=int,default=DEFAULT_TIMEOUT)
    e=sub.add_parser('finish');e.add_argument('--token',required=True);e.add_argument('--exit-code',type=int,required=True)
    s=sub.add_parser('check');s.add_argument('--run-id');s.add_argument('--json',action='store_true')
    a=p.parse_args()
    if a.action=='begin':
        token=begin(a.root,base64.b64decode(a.label64).decode(),a.script,a.timeout)
        print(base64.b64encode(json.dumps(token).encode()).decode());return 0
    if a.action=='finish':
        finish(a.root,json.loads(base64.b64decode(a.token)),a.exit_code);return 0
    result=summary(a.root,run_id=a.run_id)
    if a.json:print(json.dumps(result))
    else:
        for issue in result['issues']:
            print(f"{issue['label']}: {issue['issue']}; last successful step {issue.get('last_success_at') or 'not yet observed'}")
    return 1 if result['issues'] else 0

if __name__=='__main__':
    raise SystemExit(main())
