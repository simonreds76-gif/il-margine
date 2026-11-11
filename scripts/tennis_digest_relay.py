"""Durable local outbox; a GitHub dispatch acknowledgement is not delivery."""
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo


class DeliveryPending(RuntimeError):
    pass


def save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    tmp.replace(path)


def gh(*args, input=None):
    result = subprocess.run(['gh', *args], input=input, capture_output=True, text=True, timeout=20)
    if result.returncode:
        # Never expose credentials or message payload in error output.
        raise DeliveryPending('GitHub relay request failed; retain outbox for reconciliation')
    return result.stdout


def confirm(state, repository, workflow):
    runs = json.loads(gh('run', 'list', '--repo', repository, '--workflow', workflow,
                        '--limit', '30', '--json', 'databaseId,displayTitle,status,conclusion'))
    found = [r for r in runs if r['displayTitle'] == 'tennis-delivery-' + state['delivery_id']]
    if len(found) > 1:
        raise RuntimeError('Ambiguous relay run identity; automatic resend blocked')
    if not found:
        return False
    run = found[0]
    state['run_id'] = run['databaseId']
    if run['status'] != 'completed':
        state['status'] = 'QUEUED'
        return False
    if run['conclusion'] != 'success':
        state['status'] = 'FAILED_NEEDS_RECONCILIATION'
        raise RuntimeError('Telegram relay failed; run ' + str(run['databaseId']) + '; no blind resend')
    state.update(status='DELIVERED', delivered_at=datetime.now(timezone.utc).isoformat())
    return True


def confirmed_dispatch(messages, *, root, repository, workflow, ref, encoded, wait_seconds=65):
    digest = hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()
    # Daily summaries may render different counts during a second refresh. A
    # queued/acknowledged summary for that London day must still be one delivery.
    title = messages[0].splitlines()[0] if len(messages) == 1 else ''
    if title.startswith('PAPER ACE MODEL DAILY') or title == 'ASTRISSIMO v1 | DAILY PAPER TRACKER':
        family = 'aces-v4-daily' if title.startswith('PAPER ACE') else 'astrissimo-daily'
        day = datetime.now(ZoneInfo('Europe/London')).date().isoformat()
        key = hashlib.sha256((family + '|' + day).encode()).hexdigest()
    else:
        key = digest
    path = Path(root) / 'data/backtest/tennis-telegram-outbox' / (key + '.json')
    state = json.loads(path.read_bytes()) if path.exists() else None
    if state and state.get('status') == 'DELIVERED':
        return state
    if state is None:
        state = {'delivery_id': uuid.uuid4().hex, 'payload_sha256': digest,
                 'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'DISPATCHING'}
        save(path, state)
        # State is durable first: a timeout cannot cause an automatic duplicate dispatch.
        gh('workflow', 'run', workflow, '--repo', repository, '--ref', ref, '--json',
           input=json.dumps({'payload_b64': encoded, 'delivery_id': state['delivery_id']}))
        state['status'] = 'QUEUED'
        save(path, state)
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            done = confirm(state, repository, workflow)
        finally:
            save(path, state)
        if done:
            return state
        if time.monotonic() >= deadline:
            raise DeliveryPending('Telegram delivery still pending; saved run identity will be reconciled, not resent')
        time.sleep(3)
