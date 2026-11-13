"""Versioned, prospective shots inputs. Never writes source/settlement records.

Pricing functions and parameters are outside this module. Old replays use their
saved inputs; new captures bind to the bytes read here, not a later file hash.
"""
from __future__ import annotations
import csv, hashlib, io, json, math, os, tempfile
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from football_team_names import football_form_team_key as key

POLICY = 'shots-input-integrity-20261113-v1'
MIN_PAIRED_XG_R10 = 5  # Frozen prospectively on 13 Nov, before the floor binds.
REPAIR_REGISTERED_AT = '2026-11-13T16:30:00Z'
CONFIG = 'config/shots-input-corrections.json'
LEAGUES = ('epl','serie-a','la-liga','bundesliga','ligue-1')
COHORTS=('before_xg_gap','xg_gap_before_repair','repaired_inputs')
COHORT_LABELS=dict(before_xg_gap='Before 30 October 2026',xg_gap_before_repair='30 October 2026 to input repair',repaired_inputs='Prospective repaired inputs')

def utc(value):
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (ValueError,TypeError): return None

def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) and n>=0 else None
    except (ValueError,TypeError): return None

def identity(row):
    return (row['date'],row['league'],key(row['home_team']),key(row['away_team']))

def read_csv_bound(path):
    raw=path.read_bytes()
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))),hashlib.sha256(raw).hexdigest()

def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    tmp=Path(name)
    try:
        with os.fdopen(fd,'w',encoding='utf8',newline='\n') as handle:
            json.dump(value,handle,indent=2);handle.write('\n')
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)

def prepare(rows, amendments, now):
    """Correct only an exact reciprocal fixture with the registered old values.

    A conflicting source revision is quarantined rather than forced to the
    amendment. Missing/invalid counts never become zero or an invented result.
    """
    groups=defaultdict(list)
    for r in rows: groups[identity(r)].append(dict(r))
    corrections={identity(r):r for r in amendments.get('corrections',[])
                 if utc(r.get('effective_from')) and utc(r['effective_from'])<=now}
    exclusions={identity(r):r for r in amendments.get('excluded_inputs',[])}
    output=[];applied=[];quarantined=[]
    for fid, pair in groups.items():
        h=[r for r in pair if r.get('venue')=='home' and key(r.get('team'))==fid[2] and key(r.get('opponent'))==fid[3]]
        a=[r for r in pair if r.get('venue')=='away' and key(r.get('team'))==fid[3] and key(r.get('opponent'))==fid[2]]
        reason=None
        if len(h)!=1 or len(a)!=1: reason='non_unique_reciprocal_fixture'
        elif fid in exclusions: reason=exclusions[fid]['reason']
        else:
            h,a=h[0],a[0]
            correction=corrections.get(fid)
            if correction:
                observed=[number(h.get('shots_for')),number(a.get('shots_for'))]
                mirror=[number(a.get('shots_against')),number(h.get('shots_against'))]
                if observed!=mirror or observed not in (correction['before'],correction['after']):
                    reason='correction_source_conflict'
                else:
                    for i,(r,other) in enumerate(((h,a),(a,h))):
                        r['shots_for']=str(correction['after'][i]);other['shots_against']=str(correction['after'][i])
                    applied.append(dict(fixture=list(fid),id=correction['id'],source_already_correct=observed==correction['after']))
            for r,other in ((h,a),(a,h)):
                sf,sa,st=map(number,(r.get('shots_for'),r.get('shots_against'),r.get('sot_for')))
                if sf is None or sa is None or not sf.is_integer() or not sa.is_integer(): reason=reason or 'missing_or_invalid_total_shots'
                elif st is not None and st>sf: reason=reason or 'on_target_exceeds_total'
                elif number(other.get('shots_against'))!=sf: reason=reason or 'non_reciprocal_total_shots'
        if reason:
            quarantined.append(dict(fixture=list(fid),reason=reason));continue
        for r in pair:
            r['_shots_input_policy']=POLICY
            output.append(r)
    return output,dict(applied_corrections=applied,quarantined_fixtures=quarantined)

def quality_fields(history):
    """The same ratio, on rows where numerator AND denominator were observed.

    True zero xG remains zero. No pairs returns missing, so the existing frozen
    quality function uses its existing neutral branch. No new weight is fitted.
    """
    result={}
    for prefix,window,decay in [('r5',5,1),('r10',10,1),('ema20',20,.93)]:
        recent=history[-window:]
        for side in ('for','against'):
            pairs=[(number(r.get('xg_'+side)),number(r.get('shots_'+side)),decay**(len(recent)-1-i)) for i,r in enumerate(recent)]
            valid=[(x,s,w) for x,s,w in pairs if x is not None and s is not None]
            den=sum(s*w for x,s,w in valid)
            sufficient=prefix!='r10' or len(valid)>=MIN_PAIRED_XG_R10
            value=sum(x*w for x,s,w in valid)/den if den>0 and sufficient else None
            result[f'{prefix}_xg_per_shot_{side}']='' if value is None else f'{value:.4f}'.rstrip('0').rstrip('.')
            result[f'{prefix}_xg_shots_paired_{side}']=len(valid)
        result[f'{prefix}_xg_window_matches']=len(recent)
    result['shots_input_policy']=POLICY
    return result

def freshness(rows, check, now):
    known={identity(r) for r in rows}
    blocked={};missing=[]
    observed=utc(check.get('observed_at'))
    current=observed is not None and timedelta(0)<=now-observed<=timedelta(hours=36)
    for league in LEAGUES:
        entry=check.get('leagues',{}).get(league,{})
        if not current or entry.get('status')!='VERIFIED':
            blocked[league]='completed_fixture_check_unverified';continue
        for fixture in entry.get('completed',[]):
            # Today's matches cannot enter the frozen date-exclusive features.
            if fixture['date']>=now.date().isoformat():continue
            if identity(fixture) not in known:
                missing.append(fixture);blocked[league]='completed_matches_missing_from_inputs'
    return dict(check_observed_at=check.get('observed_at'),blocked_leagues=blocked,missing_completed=missing)

def load(root, now=None, base_path=None, write_status=False, data_root=None):
    now=now or datetime.now(timezone.utc)
    data_root=data_root or root
    path=base_path or data_root/'data/football-form/team-match-base.csv'
    rows,base_hash=read_csv_bound(path)
    raw=(root/CONFIG).read_bytes();amendments=json.loads(raw)
    policy=amendments.get('paper_quality_policy',{})
    if policy.get('minimum_paired_xg_r10')!=MIN_PAIRED_XG_R10 or utc(policy.get('registered_at'))!=utc(REPAIR_REGISTERED_AT):
        raise ValueError('registered_paper_input_policy_mismatch')
    view,audit=prepare(rows,amendments,now)
    check_path=data_root/'data/football-form/count-input-completed-check.json'
    check=json.loads(check_path.read_text(encoding='utf8')) if check_path.exists() else {}
    # Presence and fitness for prediction are different checks. A quarantined
    # source fixture must not masquerade as an unrecovered whole-league gap.
    health=freshness(rows,check,now)
    missing_xg=[r for r in view if r['date']>=(now-timedelta(days=30)).date().isoformat() and (number(r.get('xg_for')) is None or number(r.get('xg_against')) is None)]
    status=dict(policy=POLICY,generated_at=now.isoformat(),base_sha256=base_hash,
        amendment_sha256=hashlib.sha256(raw).hexdigest(),source_rows=len(rows),prediction_rows=len(view),
        latest_result_date=max((r['date'] for r in view),default=None),
        recent_missing_xg_team_rows=len(missing_xg),**audit,**health,
        historical_records_changed=False,formulas_changed=False,paper_input_transform_changed=True,
        minimum_paired_xg_r10=MIN_PAIRED_XG_R10,
        status='INPUTS_HELD' if health['blocked_leagues'] else 'READY_WITH_PARTIAL_XG' if missing_xg else 'READY')
    if write_status: atomic_json(data_root/'data/football-form/count-input-integrity-status.json',status)
    return view,status,rows

def load_for_capture(root, now=None, base_path=None, write_status=False, data_root=None):
    """Hold new forecasts on input failure; independent settlement still runs."""
    now=now or datetime.now(timezone.utc);data_root=data_root or root
    try:
        return load(root,now,base_path,write_status,data_root)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        path=base_path or data_root/'data/football-form/team-match-base.csv'
        try:rows,base_hash=read_csv_bound(path)
        except (OSError,ValueError):rows,base_hash=[],None
        status=dict(policy=POLICY,generated_at=now.isoformat(),status='INPUTS_HELD',
            base_sha256=base_hash,amendment_sha256=None,source_rows=len(rows),prediction_rows=0,
            blocked_leagues={league:'input_integrity_check_failed' for league in LEAGUES},
            reason=type(exc).__name__,missing_completed=[],quarantined_fixtures=[],
            historical_records_changed=False,formulas_changed=False)
        if write_status:atomic_json(data_root/'data/football-form/count-input-integrity-status.json',status)
        return [],status,rows

def permitted(rows,status):
    return [r for r in rows if r.get('league') not in status['blocked_leagues']]

def input_cohort(row):
    """Classify without editing a single issued row or using its outcome."""
    marker=str(row.get('input_policy') or row.get('model_input_version') or '')
    observed=next((utc(row.get(field)) for field in ('registered_at_utc','published_at_utc','published_at','captured_at_utc','captured_at') if isinstance(row.get(field),str) and utc(row.get(field))),None)
    if POLICY in marker and observed and observed>=utc(REPAIR_REGISTERED_AT):return 'repaired_inputs'
    # Missing provenance cannot be relabelled as clean pre-outage evidence.
    return 'before_xg_gap' if observed and observed.date().isoformat()<'2026-10-30' else 'xg_gap_before_repair'

def cohort_groups(rows):
    groups={name:[] for name in COHORTS}
    for row in rows:groups[input_cohort(row)].append(row)
    return groups

def cohort_note(cohorts,kind='settled'):
    counts=', '.join(f"{COHORT_LABELS[name]}: {cohorts[name].get(kind,0)} settled" for name in COHORTS)
    return 'Input cohorts kept separate. '+counts+'. Promotion review uses repaired inputs only; original records remain intact.'

def cohort_performance_text(cohorts):
    parts=[]
    for name in COHORTS:
        row=cohorts.get(name,{})
        roi=row.get('roi');roi_text=f'{roi:+.1%}' if roi is not None else 'awaiting results'
        parts.append(f"{COHORT_LABELS[name]}: {row.get('settled',0)} settled, {row.get('pnl_units',0):+.2f}u, ROI {roi_text}")
    return ' | '.join(parts)+'. Promotion evidence: repaired inputs only.'

def settlement_exceptions(ledger, raw_rows, amendments):
    """Flag known count discrepancies without changing any recorded outcome."""
    result=[]
    for correction in amendments.get('corrections',[]):
        fixture=identity(correction)
        contracts=[r for r in ledger if (r.get('match_date'),r.get('league'),key(r.get('home_team','')),key(r.get('away_team','')))==fixture]
        source=[r for r in raw_rows if identity(r)==fixture and r.get('venue')=='home']
        expected=tuple(correction['after'])
        if not contracts or not source:continue
        observed=(number(source[0].get('shots_for')),number(source[0].get('shots_against')))
        if observed==expected:continue
        result.append(dict(fixture='|'.join(fixture),contract_ids=[r.get('contract_id') for r in contracts],
            recorded_counts=observed,verified_counts=expected,evidence=correction.get('evidence',[]),
            status='INVESTIGATE_DATA',historical_records_changed=False))
    return result

def describe(status):
    if not status:return 'Shots input verification unavailable.'
    held=status.get('blocked_leagues',{})
    freshness_text=('New captures held for '+', '.join(sorted(held))+'.') if held else f"Completed-fixture coverage checked at {status.get('check_observed_at','unknown')}; results after that check await the next refresh."
    return (f"Inputs: {status.get('policy','unknown')} · {status.get('generated_at','unknown')}. "
            f"{freshness_text} Missing xG uses observed pairs only; fewer than {MIN_PAIRED_XG_R10} pairs in the last 10 uses the existing neutral quality factor (recent missing team rows: {status.get('recent_missing_xg_team_rows',0)}). "
            'Earlier forecasts, outcomes and ROI retained as issued; corrected inputs apply to new forecasts only.')
