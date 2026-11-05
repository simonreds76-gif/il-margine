"""Verify recovery of a props refresh from the existing private Monitor bundle.

No model runs, alerts, or historical-status rewrites. Recovery proves a later
successful input/price comparison, not current betting value or alert delivery.
"""
import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlencode

HEALTHY = {'HEALTHY_NO_QUALIFYING_EDGE', 'SHADOW_EVIDENCE_READY',
           'MILESTONE_SHADOW_READY', 'MILESTONE_MARKETS_AVAILABLE',
           'ONE_SIDED_FEED_NO_QUALIFYING_EDGE'}
METHOD = 'verified_hosted_props_comparison'


def stamp(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('timezone_required')
    return value


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def content(entry):
    raw = entry['content'].encode('utf-8')
    if len(raw) != entry['size_bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise ValueError('snapshot_file_hash_mismatch')
    return entry['content']


def props_failure(row):
    if row.get('error_type') in {'TennisPropsRefreshFailed', 'TennisPropsCaptureFailed',
                                  'TennisPropsBoardFailed', 'TennisPropsComparisonFailed'}:
        return True
    # Legacy PowerShell hid the stage behind RuntimeException. Require a
    # reviewed, exact-run diagnosis; never clear arbitrary generic failures.
    diagnosis = (row.get('details') or {}).get('ops_failure_diagnosis', {})
    return (row.get('error_type') == 'RuntimeException'
            and row.get('trigger_kind') == 'manual'
            and diagnosis.get('run_id') == row.get('run_id')
            and diagnosis.get('scope') == 'sisal-evidence-capture-gate-only'
            and diagnosis.get('reason') == 'event_comparison_frozen_policy_or_artifact_changed'
            and sha(diagnosis.get('run_log_sha256'))
            and sha(diagnosis.get('manual_status_sha256')))


def verified_props_recovery(row, details):
    r = details.get('ops_failure_resolution')
    if not props_failure(row) or not isinstance(r, dict):
        return False
    try:
        h = r['health']
        return (r['method'] == METHOD and r['run_id'] == row['run_id']
                and r['snapshot_key'] == 'tennis_evidence_v1'
                and r['source'] == 'windows_local_tennis_pipeline'
                and stamp(row['finished_at']) < stamp(r['resolved_at']) <= stamp(r['snapshot_at'])
                <= stamp(r['verified_at']) <= datetime.now(timezone.utc)
                and sha(r['snapshot_hash']) and len(r['file_hashes']) == 3
                and all(sha(x) for x in r['file_hashes'].values())
                and h['state'] in HEALTHY and h['history_state'] == 'CURRENT'
                and h['compared_rows'] > 0 and h['unmatched_rows'] == 0
                and h['fresh_upcoming_rows'] == h['upcoming_rows'] > 0
                and h['uncompared_upcoming_rows'] == 0
                and h['structural_error'] is False)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def discover_props_recovery(row, base, headers, transport):
    if not props_failure(row):
        return None
    fields = ('updated_at,source:payload->source,schema:payload->schema_version,'
              'generated_at:payload->generated_at,payload_hash:payload->payload_hash,'
              'bundle:payload->monitor_bundle,'
              'health_file:payload->files->"data/tennis-props/pipeline-health.json"')
    def get(select):
        query = urlencode({'snapshot_key': 'eq.tennis_evidence_v1', 'select': select, 'limit': '1'})
        rows = transport('GET', base + '/rest/v1/goalscorer_live_snapshot?' + query, headers)
        if not isinstance(rows, list) or len(rows) != 1:
            raise ValueError('snapshot_unavailable')
        return rows[0]
    try:
        s = get(fields)
        h = json.loads(content(s['health_file']))
        now = datetime.now(timezone.utc)
        generated = stamp(h['generated_at'])
        if not (s['schema'] == 3 and s['source'] == 'windows_local_tennis_pipeline'
                and sha(s['payload_hash']) and s['bundle']['status'] == 'AVAILABLE'
                and not s['bundle']['missing_required_files']
                and stamp(row['finished_at']) < generated <= stamp(s['generated_at'])
                == stamp(s['updated_at']) <= now
                and h['as_of'] == generated.date().isoformat()
                and h['state'] in HEALTHY and h['structural_error'] is False
                and h['player_history']['state'] == 'CURRENT'
                and h['player_history']['as_of'] == h['as_of']
                and h['baseline_source_health']['state'] == 'CURRENT'
                and not h.get('fixture_quarantine', {}).get('held_fixtures')
                and h['fresh_upcoming_line_rows'] == h['upcoming_line_rows'] > 0
                and h['uncompared_upcoming_rows'] == 0 and h['unmatched_rows'] == 0
                and h['matched_rows'] == h['comparison_rows'] == h['eligible_line_rows'] > 0
                and not h['freshness_problems']):
            return None
        age = (generated - stamp(h['latest_capture_utc'])).total_seconds() / 3600
        if not 0 <= age <= h['max_capture_age_hours'] <= 24:
            return None
        date = h['as_of']
        line_name = h['lines_file'].replace('\\', '/').rsplit('/', 1)[-1]
        compare_name = h['comparison_file'].replace('\\', '/').rsplit('/', 1)[-1]
        if line_name not in {f'bet365-lines-{date}.csv', f'tennis-props-lines-{date}.csv'} or compare_name != f'comparison-{date}.csv':
            return None
        names = {'lines': 'data/tennis-props/inbox/' + line_name,
                 'comparison': 'data/tennis-props/' + compare_name}
        bundle = get('payload_hash:payload->payload_hash,' + ','.join(f'{k}:payload->files->"{v}"' for k,v in names.items()))
        if bundle['payload_hash'] != s['payload_hash']:
            return None  # Concurrent publication: retry on the next existing check.
        lines = list(csv.DictReader(io.StringIO(content(bundle['lines']))))
        comparisons = list(csv.DictReader(io.StringIO(content(bundle['comparison']))))
        if len(lines) != h['line_rows'] or len(comparisons) != h['comparison_rows']:
            return None
        def identity(x):
            return tuple(x.get(k, '') for k in ('event_id','player','opponent','market','line','capture_ts','bookmaker'))
        if Counter(map(identity, lines)) != Counter(map(identity, comparisons)):
            return None
        history = h['player_history']
        if any(x['matched_board'] != 'yes' or x['history_as_of'] != date
               or x['history_version'] != history['version']
               or x['history_fingerprint'] != history['output_hashes']['player-props-baseline.csv'] for x in comparisons):
            return None
        receipt = {'method': METHOD, 'run_id': row['run_id'], 'snapshot_key': 'tennis_evidence_v1',
                   'source': s['source'], 'resolved_at': h['generated_at'], 'snapshot_at': s['generated_at'],
                   'verified_at': now.isoformat(), 'snapshot_hash': s['payload_hash'],
                   'file_hashes': {'health': s['health_file']['sha256'], **{k: bundle[k]['sha256'] for k in names}},
                   'health': {'state':h['state'], 'history_state':history['state'], 'compared_rows':len(comparisons),
                              'unmatched_rows':0, 'fresh_upcoming_rows':h['fresh_upcoming_line_rows'],
                              'upcoming_rows':h['upcoming_line_rows'], 'uncompared_upcoming_rows':0,
                              'structural_error':False},
                   'scope':'Recovered inputs and price comparison; original failure retained. No claim of Telegram delivery.'}
        return receipt if verified_props_recovery(row, {'ops_failure_resolution': receipt}) else None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
