"""Durable paper evidence and explicitly approved operational fingerprints.

No pricing, network, automatic registration, alerts or historical rewrites.
Call registration/refresh under the existing Match Shape worker lock.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

RELATIVE = Path('data/tennis-ml-research/match-shape-v1')
DEPENDENCIES = (
    'scripts/tennis_match_shape_results.py', 'scripts/tennis_match_shape_integrity.py',
    'scripts/tennis_match_shape_collect.py', 'scripts/tennis_match_shape_prepare.py',
    'scripts/tennis_match_shape_quotes.py',
    'scripts/tennis_tournament_category.py', 'scripts/tennis_grosvenor.py',
    'scripts/tennis_indoor_paper.py', 'scripts/tennis_hardcourt_scout.py',
    'scripts/tennis_breakpoint_evidence.py', 'scripts/ace_compass_integrity.py',
    'scripts/tennis_event_integrity.py',
)
REASONS = {'native_schedule_walkover_grading_review',
           'native_draw_opponent_changed_grading_review'}
HEX = re.compile(r'[0-9a-f]{64}')
MAX_FILES, MAX_BYTES = 10000, 2*1024*1024


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def utc(value):
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError,ValueError):return None


def read(path):
    if path.stat().st_size>MAX_BYTES:raise ValueError('operational_file_too_large: '+path.name)
    return json.loads(path.read_bytes())


def immutable(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if read(path)!=value:raise ValueError('immutable_operational_file_changed: '+path.name)
        return
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,sort_keys=True,allow_nan=False)


def fingerprints(root):
    return {name:file_hash(root/name) for name in DEPENDENCIES}


def report_with_health(root):
    """Read-only reporting overlay; never rewrite the last validated results."""
    folder=root/RELATIVE;path=folder/'report.json'
    try:report=json.loads(path.read_bytes()) if path.exists() else {}
    except (OSError,ValueError):return {}
    if not isinstance(report,dict):return {}
    if not report:return report
    def health_file(path,fallback):
        try:
            value=read(path) if path.exists() else fallback
            if isinstance(value,dict):return value
        except (OSError,ValueError):pass
        return dict(state='UNREADABLE',reason='Match Shape health file unreadable')
    capture=folder/'capture-status.json';status=folder/'operational/status.json'
    health=health_file(status,{})
    capture_health=health_file(capture,report.get('capture',{}))
    if health.get('state')=='UNREADABLE':capture_health=health
    return {**report,'capture':capture_health,
            'operational':health}


def register(root,approved,clock):
    """Explicit installation only; never called by the scheduled refresh.

    approved contains exact reviewed fingerprints, original registration hash
    and previous_manifest_sha256 (None for first installation).
    """
    folder=root/RELATIVE; op=folder/'operational'
    if not clock.tzinfo:raise ValueError('operational_registration_time_naive')
    if approved['registration_sha256']!=file_hash(folder/'registration.json'):
        raise ValueError('approved_original_registration_mismatch')
    if approved['fingerprints']!=fingerprints(root):raise ValueError('approved_operational_code_mismatch')
    active=read(op/'active.json') if (op/'active.json').exists() else None
    old=active['manifest_sha256'] if active else None
    if old:
        if not isinstance(old,str) or not HEX.fullmatch(old):raise ValueError('operational_pointer_invalid')
        current=read(op/'registrations'/(old+'.json'))
        if digest(current)!=old:raise ValueError('operational_manifest_hash_mismatch')
        stamp=utc(current.get('registered_at'))
        if not stamp or clock<stamp:raise ValueError('operational_upgrade_time_before_parent')
        if current['fingerprints']==approved['fingerprints'] and current['registration_sha256']==approved['registration_sha256']:
            return old  # explicit repeated install is idempotent
    if old!=approved.get('previous_manifest_sha256'):raise ValueError('operational_upgrade_parent_mismatch')
    manifest=dict(version=1,registered_at=clock.isoformat(),registration_sha256=approved['registration_sha256'],
                  previous_manifest_sha256=old,fingerprints=approved['fingerprints'],
                  scope='paper acquisition/settlement only; pricing and original registration unchanged')
    key=digest(manifest);immutable(op/'registrations'/(key+'.json'),manifest)
    # The caller holds the existing tracker lock; pointer publication is atomic.
    temporary=op/'active.json.tmp';temporary.write_text(json.dumps({'manifest_sha256':key}),encoding='utf-8')
    temporary.replace(op/'active.json')
    return key


def verify(root,clock):
    folder=root/RELATIVE;op=folder/'operational'
    if not (op/'active.json').exists():raise ValueError('operational_registration_missing')
    key=read(op/'active.json').get('manifest_sha256','')
    if not HEX.fullmatch(key):raise ValueError('operational_pointer_invalid')
    seen=set();head=None;child_time=clock
    while key:
        if key in seen or len(seen)>=100:raise ValueError('operational_manifest_chain_invalid')
        seen.add(key);manifest=read(op/'registrations'/(key+'.json'))
        if digest(manifest)!=key:raise ValueError('operational_manifest_hash_mismatch')
        stamp=utc(manifest.get('registered_at'))
        if manifest.get('version')!=1:raise ValueError('operational_manifest_version_invalid')
        if not stamp or stamp>child_time:raise ValueError('operational_manifest_time_invalid')
        child_time=stamp
        if manifest.get('registration_sha256')!=file_hash(folder/'registration.json'):
            raise ValueError('operational_original_registration_mismatch')
        if head is None:head=(key,manifest)
        parent=manifest.get('previous_manifest_sha256')
        if parent is not None and not HEX.fullmatch(parent):raise ValueError('operational_manifest_parent_invalid')
        key=parent
    expected=head[1].get('fingerprints',{})
    if set(expected)!=set(DEPENDENCIES):raise ValueError('operational_dependency_set_changed')
    for name,wanted in expected.items():
        if not (root/name).is_file() or file_hash(root/name)!=wanted:
            raise ValueError('operational_code_changed: '+name)
    original=read(folder/'registration.json')
    for name,wanted in original['fingerprints'].items():
        if not (root/name).is_file() or file_hash(root/name)!=wanted:
            raise ValueError('frozen_code_changed: '+name)
    return head


def retain(folder,records,clock):
    if not records:return
    path=folder/'result-evidence'/(digest(records)+'.json')
    # Repeated observation never moves the original first-seen timestamp.
    if not path.exists():immutable(path,dict(observed_at=clock.isoformat(),records=records))


def evidence(folder,captures,clock,complete_score=None):
    """Read all evidence, never just the newest N snapshots."""
    paths=sorted((folder/'result-evidence').glob('*.json'))
    if len(paths)>MAX_FILES:raise ValueError('retained_evidence_limit_exceeded')
    wanted={r['fixture_key']:r for r in captures};found={}
    for path in paths:
        if not HEX.fullmatch(path.stem):raise ValueError('retained_evidence_filename_invalid')
        packet=read(path);rows=packet.get('records');stamp=utc(packet.get('observed_at'))
        if not isinstance(rows,dict) or digest(rows)!=path.stem:raise ValueError('retained_evidence_hash_mismatch')
        if not stamp or stamp>clock:raise ValueError('retained_evidence_observation_invalid')
        for key,row in rows.items():
            if key not in wanted:continue  # unrelated exact fixtures cannot affect this cohort
            start=utc(wanted[key]['quote']['scheduled_start'])
            if not start or stamp<start:raise ValueError('retained_evidence_before_start')
            if row.get('status')!='excluded' or row.get('reason') not in REASONS:
                raise ValueError('retained_evidence_reason_invalid')
            if not HEX.fullmatch(row.get('source_sha256','')):raise ValueError('retained_evidence_source_hash_invalid')
            if row['reason']=='native_schedule_walkover_grading_review':
                dates=[row.get('result_date','')]
                if row.get('evidence')!='today_atp.csv' or not re.fullmatch(r'(?:w\s*/\s*o|walkover)',row.get('score',''),re.I):
                    raise ValueError('retained_walkover_invalid')
            else:
                replacement=row.get('replacement_results',[]);edition,round_id,a,b=key.split('|')
                if row.get('evidence')!='games_atp.csv' or not replacement:raise ValueError('retained_replacement_invalid')
                for game in replacement:
                    pair={str(game.get('winner_id')),str(game.get('loser_id'))}
                    if (str(game.get('tour_id')),str(game.get('round_id')))!=(edition,round_id) or not pair&{a,b} or pair=={a,b}:
                        raise ValueError('retained_replacement_identity_invalid')
                    if complete_score is not None and not complete_score(game.get('result','')):
                        raise ValueError('retained_replacement_score_invalid')
                dates=[g.get('date','') for g in replacement]
            try:dates=[datetime.fromisoformat(day[:10]).date() for day in dates]
            except (ValueError,TypeError):raise ValueError('retained_evidence_result_date_invalid')
            if any(day>stamp.date() or abs((day-start.date()).days)>1 for day in dates):
                raise ValueError('retained_evidence_result_time_invalid')
            found.setdefault(key,[]).append(dict(observed_at=packet['observed_at'],snapshot_sha256=path.stem,evidence=row))
    return {key:sorted(rows,key=lambda row:(utc(row['observed_at']),row['snapshot_sha256'])) for key,rows in found.items()}


def resolve(record,current,previous,retained):
    """Preserve integrity failures and issued settled records; explain conflicts."""
    notices=[]
    if current['status']=='quarantined':
        if previous.get('status') in ('settled','excluded'):
            notices.append(dict(reason='resolved_record_quarantined_requires_review',original=previous,new=current))
        return current,notices
    if previous.get('status')=='settled':
        if current['status']!='pending' and current!=previous:
            notices.append(dict(reason='settled_record_changed_requires_review',original=previous,new=current))
        return previous,notices
    if current['status']=='settled':
        if retained or previous.get('status')=='excluded':
            notices.append(dict(reason='completed_result_after_exclusion_requires_review',original=previous,new=current,evidence=retained))
        return current,notices
    if current['status']!='pending':return current,notices
    if previous.get('status')=='excluded':return previous,notices
    if not retained:return current,notices
    first=retained[0]
    return dict(status='excluded',reason=first['evidence']['reason'],
                first_observed_at=first['observed_at'],first_evidence_sha256=first['snapshot_sha256']),notices


def unresolved_conflicts(folder,clock):
    """Conflicts stay open until an explicit, dated review acknowledges them."""
    paths=sorted((folder/'operational/conflicts').glob('*.json'))
    if len(paths)>MAX_FILES:raise ValueError('operational_conflict_limit_exceeded')
    unresolved=[]
    for path in paths:
        packet=read(path);notice={k:v for k,v in packet.items() if k!='first_observed_at'}
        first=utc(packet.get('first_observed_at'))
        if digest(notice)!=path.stem or not first or first>clock:raise ValueError('operational_conflict_invalid')
        resolution=folder/'operational/resolutions'/path.name
        if not resolution.exists():unresolved.append(path.stem);continue
        review=read(resolution);at=utc(review.get('reviewed_at'))
        if (review.get('conflict_sha256')!=path.stem or not at or not first<=at<=clock
            or review.get('decision')!='accept_recorded_outcome' or not review.get('rationale','').strip()):
            raise ValueError('operational_resolution_invalid')
    return unresolved


def record_cohorts(folder,captures,manifest_hash,manifest,clock,new_ids=()):
    """Sidecars bind future captures without editing the frozen capture schema."""
    for row in captures:
        path=folder/'operational/cohorts'/(row['id']+'.json')
        if path.exists():
            if read(path)['capture_sha256']!=digest(row):raise ValueError('operational_capture_changed: '+row['id'])
            continue
        # A timestamp alone does not prove the guarded refresh created a row.
        verified=row['id'] in new_ids and utc(row['captured_at'])>=utc(manifest['registered_at'])
        identity=row['quote'].get('native_identity',{})
        item=dict(capture_id=row['id'],capture_sha256=digest(row),fixture_key=row['fixture_key'],
                  manifest_sha256=manifest_hash,documented_at=clock.isoformat(),
                  binding='verified_operational_capture' if verified else 'retrospective_coverage_documentation',
                  operational_hash_at_capture=manifest_hash if verified else 'unrecorded',
                  mapping_path='season_calendar' if identity.get('venue_identity_source')=='verified_season_calendar' else
                               'blank_native_date' if identity.get('native_date_was_blank') else
                               'wrapper_exact_venue' if identity.get('schedule_source') else 'original_exact_mapper',
                  probabilities_and_selections_unchanged=True)
        immutable(path,item)
