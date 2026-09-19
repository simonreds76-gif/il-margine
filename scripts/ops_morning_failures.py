"""Report completed morning failures through the existing hourly Telegram channel."""
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(method, url, headers, payload=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    request = Request(url, data=data, headers={**headers, 'Content-Type': 'application/json'}, method=method)
    try:
        with urlopen(request, timeout=25) as response:
            raw = response.read()
        return json.loads(raw) if raw else None
    except Exception:
        # URLs can contain Telegram tokens; never include transport exceptions.
        raise RuntimeError('Morning failure alert transport failed; retry on next ops check') from None


def check_morning_failure(env=None, transport=request_json):
    env = os.environ if env is None else env
    base = env.get('NEXT_PUBLIC_SUPABASE_URL', '').rstrip('/')
    key = env.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not base or not key:
        raise RuntimeError('Morning failure check needs Supabase REST credentials')
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
    query = urlencode({'pipeline': 'eq.oncourt-am-refresh', 'select': 'run_id,status,started_at,finished_at,error_type,details', 'order': 'started_at.desc', 'limit': '1'})
    rows = transport('GET', f'{base}/rest/v1/run_status?{query}', headers)
    if not isinstance(rows, list):
        raise RuntimeError('Morning failure check returned an invalid response')
    if not rows:
        raise RuntimeError('Morning failure check found no recorded morning run')
    row = rows[0]
    if row['status'] not in ('failed', 'timeout', 'aborted'):
        print(f"OPS_MORNING_FAILURE clear status={row['status']}")
        return False
    details = dict(row.get('details') or {})
    if details.get('ops_failure_notified_at'):
        print('OPS_MORNING_FAILURE already notified')
        return True
    token = env.get('OPS_ALERT_TELEGRAM_BOT_TOKEN', '')
    chat = env.get('OPS_ALERT_TELEGRAM_CHAT_ID', '')
    if not token or not chat:
        raise RuntimeError('Morning failure alert cannot send: Telegram credentials missing')
    atlas = row.get('error_type') == 'ReturnAtlasRefreshFailed'
    message = 'Morning tennis refresh failed.\n'
    message += ('Return Atlas could not complete its validated update. Check the publisher status before retrying.\n' if atlas else 'The morning pipeline did not complete successfully; review its run log.\n')
    message += f"Started: {row['started_at']}\nRun: {row['run_id']}\nThe failure needs review; this alert is sent once per failed run."
    response = transport('POST', f'https://api.telegram.org/bot{token}/sendMessage', {}, {'chat_id': chat, 'text': message, 'disable_web_page_preview': True})
    if not isinstance(response, dict) or response.get('ok') is not True:
        raise RuntimeError('Telegram did not confirm the morning failure alert; it will retry')
    details['ops_failure_notified_at'] = datetime.now(timezone.utc).isoformat()
    # Patch only the completed run; never overwrite a newly running/successful row.
    query = urlencode({'run_id': 'eq.' + row['run_id'], 'status': 'eq.' + row['status']})
    transport('PATCH', f'{base}/rest/v1/run_status?{query}', {**headers, 'Prefer': 'return=minimal'}, {'details': details})
    print('OPS_MORNING_FAILURE Telegram sent and acknowledged')
    return True
