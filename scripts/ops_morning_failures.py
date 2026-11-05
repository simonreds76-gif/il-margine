"""Report completed morning failures through the existing hourly Telegram channel."""
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from ops_tennis_recovery import discover_props_recovery, verified_props_recovery


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


def verified_atlas_recovery(row, details):
    """Accept a run-specific recovery receipt without rewriting failure history."""
    recovery = details.get('ops_failure_resolution')
    if not isinstance(recovery, dict):
        return False
    # Older wrappers masked the Atlas error with a generic final-step failure.
    # Accept recovery only when the saved runtime diagnosis proves Atlas was
    # the sole failed step; other generic tennis failures remain actionable.
    diagnosed_atlas_only = (
        row.get('error_type') == 'TennisStepFailed'
        and recovery.get('diagnosed_error_type') == 'ReturnAtlasAuthRequired'
        and recovery.get('runtime_failed_scripts') == ['refresh-return-atlas.py']
        and bool(recovery.get('runtime_run_id'))
    )
    if row.get('error_type') not in ('ReturnAtlasRefreshFailed', 'ReturnAtlasAuthRequired') and not diagnosed_atlas_only:
        return False
    expected = recovery.get('expected_commit', '')
    version = recovery.get('expected_data_version', '')
    try:
        resolved = datetime.fromisoformat(recovery.get('resolved_at', '').replace('Z', '+00:00'))
        finished = datetime.fromisoformat(row.get('finished_at', '').replace('Z', '+00:00'))
        valid_time = resolved.tzinfo is not None and finished.tzinfo is not None and finished <= resolved <= datetime.now(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return False
    return (
        valid_time
        and recovery.get('run_id') == row.get('run_id')
        and recovery.get('method') == 'verified_production_deployment'
        and recovery.get('public_url') == 'https://ilmargine.bet'
        and str(recovery.get('deployment_id', '')).startswith('dpl_')
        and len(expected) == 40 and all(c in '0123456789abcdef' for c in expected)
        and recovery.get('verified_commit') == expected
        and bool(version) and recovery.get('verified_data_version') == version
    )


def report_incident(row, notification, env):
    # An incident is not a checker crash. Keep it visible without repeating
    # GitHub failure emails after successful delivery/deduplication.
    run_id = str(row.get('run_id', 'unknown')).replace('\n', ' ')
    error = str(row.get('error_type') or 'Unclassified').replace('\n', ' ')
    started = str(row.get('started_at', 'unknown')).replace('\n', ' ')
    print(f"OPS_MORNING_INCIDENT run={run_id} error={error} notification={notification} recovery=unverified")
    summary = env.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf8') as stream:
            stream.write(f"## Recorded morning incident\n\nRun: `{run_id}`; started: {started}; error: `{error}`.\n\n"
                         f"Notification: **{notification}**. Original failed-run history retained; recovery is not asserted. "
                         "The alert checker completed; this is not a new checker failure.\n")


def check_morning_failure(env=None, transport=request_json, *, read_only=False):
    env = os.environ if env is None else env
    base = env.get('NEXT_PUBLIC_SUPABASE_URL', '').rstrip('/')
    key = env.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not base or not key:
        raise RuntimeError('Morning failure check needs Supabase REST credentials')
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
    query = urlencode({'pipeline': 'eq.oncourt-am-refresh', 'select': 'run_id,status,started_at,finished_at,error_type,trigger_kind,details', 'order': 'started_at.desc', 'limit': '1'})
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
    if verified_atlas_recovery(row, details):
        print('OPS_MORNING_FAILURE resolved by verified production deployment; original failure retained')
        return False
    if verified_props_recovery(row, details):
        print('OPS_MORNING_FAILURE resolved by verified later props comparison; original failure retained')
        return False
    recovery = discover_props_recovery(row, base, headers, transport)
    if recovery:
        if not read_only:
            # Compare-and-swap: never clobber another acknowledgement/recovery.
            query = urlencode({'run_id': 'eq.' + row['run_id'], 'status': 'eq.' + row['status'],
                               'details': ('is.null' if row.get('details') is None else
                                           'eq.' + json.dumps(row['details'], separators=(',', ':')))})
            changed = transport('PATCH', f'{base}/rest/v1/run_status?{query}',
                                {**headers, 'Prefer':'return=representation'},
                                {'details': {**details, 'ops_failure_resolution': recovery}})
            if not isinstance(changed, list) or len(changed) != 1:
                raise RuntimeError('Recovery receipt changed concurrently; retry on next ops check')
        print('OPS_MORNING_FAILURE verified later input/price recovery; no Telegram alert')
        return False
    if details.get('ops_failure_notified_at'):
        print('OPS_MORNING_FAILURE already notified')
        report_incident(row, 'already-notified', env)
        return True
    if read_only:
        report_incident(row, 'pending-delivery (read-only)', env)
        return True
    token = env.get('OPS_ALERT_TELEGRAM_BOT_TOKEN', '')
    chat = env.get('OPS_ALERT_TELEGRAM_CHAT_ID', '')
    if not token or not chat:
        raise RuntimeError('Morning failure alert cannot send: Telegram credentials missing')
    atlas = row.get('error_type') in ('ReturnAtlasRefreshFailed', 'ReturnAtlasAuthRequired')
    message = failure_message(row)
    response = transport('POST', f'https://api.telegram.org/bot{token}/sendMessage', {}, {'chat_id': chat, 'text': message, 'disable_web_page_preview': True})
    if not isinstance(response, dict) or response.get('ok') is not True:
        raise RuntimeError('Telegram did not confirm the morning failure alert; it will retry')
    details['ops_failure_notified_at'] = datetime.now(timezone.utc).isoformat()
    # Patch only the completed run; never overwrite a newly running/successful row.
    query = urlencode({'run_id': 'eq.' + row['run_id'], 'status': 'eq.' + row['status']})
    transport('PATCH', f'{base}/rest/v1/run_status?{query}', {**headers, 'Prefer': 'return=minimal'}, {'details': details})
    print('OPS_MORNING_FAILURE Telegram sent and acknowledged')
    report_incident(row, 'sent-and-acknowledged', env)
    return True


def failure_message(row):
    atlas = row.get('error_type') in ('ReturnAtlasRefreshFailed', 'ReturnAtlasAuthRequired')
    name = 'On-demand tennis refresh' if row.get('trigger_kind') == 'manual' else 'Tennis refresh'
    message = 'Tennis: Return Atlas publication failed.\n' if atlas else name + ' incomplete.\n'
    if row.get('error_type') == 'ReturnAtlasAuthRequired':
        message += 'Vercel CLI sign-in is required on the publishing PC. Retry publication only; do not rerun pricing or betting alerts.\n'
    elif atlas:
        message += 'Return Atlas could not complete its validated update. Check the publisher status before retrying publication.\n'
    elif row.get('error_type') in ('TennisPropsCaptureFailed', 'TennisPropsBoardFailed', 'TennisPropsComparisonFailed'):
        stage = {'TennisPropsCaptureFailed': 'bookmaker price capture',
                 'TennisPropsBoardFailed': 'player props projection build',
                 'TennisPropsComparisonFailed': 'props price comparison'}[row['error_type']]
        message += f'Match pricing completed, but {stage} failed. Check that stage before using its props.\n'
    else:
        message += 'The refresh did not complete successfully; check the saved runtime steps for the failed stage.\n'
    message += f"Started: {row['started_at']}\nRun: {row['run_id']}\nThe failure needs review; this alert is sent once per failed run."
    return message
