"""Compact read-only health checks for the existing tennis evidence snapshot."""
from __future__ import annotations
import csv
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

LANES={'strict':'strict-signals', 'volume_200':'strict-signals-volume200',
       'challenger':'strict-signals-challenger-ml-v2', 'spread_v1':'strict-signals-spreadv1'}

def csv_rows(path):
    if not path.exists(): return []
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))

def read_json(path):
    try: return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError): return {}

def timestamp(value):
    try:
        result=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return result if result.tzinfo else None
    except ValueError: return None

def ledger_health(rows, now):
    unresolved=[r for r in rows if r.get('settlement_status')!='settled']
    overdue=[]
    for row in unresolved:
        due=timestamp(row.get('scheduled_start_utc')) or timestamp(str(row.get('date',''))[:10]+'T23:59:59Z')
        if due and due+timedelta(hours=48)<now: overdue.append(row)
    issue_fields=('date','player1','player2','settlement_status','settlement_note')
    return dict(archive_rows=len(rows),latest_signal_date=max((r.get('date','') for r in rows),default=None),
        unresolved=len(unresolved),overdue=len(overdue),recent_pending=len(unresolved)-len(overdue),
        statuses=dict(Counter(r.get('settlement_status') or 'unknown' for r in unresolved)),
        oldest_unresolved=min((r.get('date','') for r in unresolved),default=None),
        issues=[{k:r.get(k,'') for k in issue_fields} for r in overdue[:20]],
        scope='Full retained archive; current-policy ROI is a separate filtered cohort. Unresolved rows are not losses, wins or voids.')

def build_integrity(root: Path, now=None):
    now=now or datetime.now(timezone.utc)
    lanes={}
    for key,stem in LANES.items():
        path=root/'data/backtest'/f'{stem}-archive.csv'
        value=ledger_health(csv_rows(path),now)
        value['source_available']=path.exists()
        live=root/'data/backtest'/f'{stem}-live.csv'
        value['live_rows']=len(csv_rows(live)) if live.exists() else None
        value['live_file_updated_at']=datetime.fromtimestamp(live.stat().st_mtime,timezone.utc).isoformat() if live.exists() else None
        lanes[key]=value
    generation=read_json(root/'data/backtest/tennis-signal-generation-status.json')
    finished=timestamp(generation.get('completed_at'))
    capture=read_json(root/'data/pinnacle-close-capture-heartbeat.json')
    health=read_json(root/'data/tennis-props/pipeline-health.json')
    captime=timestamp(health.get('latest_capture_utc'))
    most=read_json(root/'data/tennis-props/shadow/most-aces-1x2-forecast-report.json')
    return dict(generated_at=now.isoformat(),lanes=lanes,
        generation=dict(status=generation.get('status','unavailable'),completed_at=generation.get('completed_at'),
            stale=not finished or now-finished>timedelta(hours=36),refresh_id=generation.get('refresh_id')),
        closing_capture={k:capture.get(k) for k in ('state','utc_time','exit_code')},
        props=dict(state=health.get('state','UNAVAILABLE'),captured_at=health.get('latest_capture_utc'),
            stale=not captime or now-captime>timedelta(hours=6),two_way_rows=health.get('two_way_rows'),
            one_sided_rows=health.get('over_only_rows'),quarantined_most_aces=most.get('rows_quarantined'),
            explanation='Ace and double-fault milestones may legitimately have only a back price. Model EV uses that offered price; a margin-free market benchmark requires both sides.'),
        strict_scope='High-confidence hard-court Masters policy. No new qualifying selection is different from a failed refresh.',
        retired=['original_challenger_batch','invalidated_hard_calibration','legacy_vnext'],
        paused=['cpi_speed_shadow'],automatic_promotion=False)
