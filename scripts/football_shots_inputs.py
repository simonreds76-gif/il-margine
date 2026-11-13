"""Versioned, prospective shots inputs. Never writes source/settlement records.

Pricing functions and parameters are outside this module. Old replays use their
saved inputs; new captures bind to the bytes read here, not a later file hash.
"""
from __future__ import annotations
import csv, hashlib, io, json, math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from football_team_names import football_form_team_key as key

POLICY = 'shots-input-integrity-20261113-v1'
CONFIG = 'config/shots-input-corrections.json'
LEAGUES = ('epl','serie-a','la-liga','bundesliga','ligue-1')

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
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');tmp.replace(path)

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
            value=sum(x*w for x,s,w in valid)/den if den>0 else None
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

def load(root, now=None, base_path=None, write_status=False):
    now=now or datetime.now(timezone.utc)
    path=base_path or root/'data/football-form/team-match-base.csv'
    rows,base_hash=read_csv_bound(path)
    raw=(root/CONFIG).read_bytes();amendments=json.loads(raw)
    view,audit=prepare(rows,amendments,now)
    check_path=root/'data/football-form/count-input-completed-check.json'
    check=json.loads(check_path.read_text(encoding='utf8')) if check_path.exists() else {}
    health=freshness(view,check,now)
    missing_xg=[r for r in view if r['date']>=(now-timedelta(days=30)).date().isoformat() and (number(r.get('xg_for')) is None or number(r.get('xg_against')) is None)]
    status=dict(policy=POLICY,generated_at=now.isoformat(),base_sha256=base_hash,
        amendment_sha256=hashlib.sha256(raw).hexdigest(),source_rows=len(rows),prediction_rows=len(view),
        latest_result_date=max((r['date'] for r in view),default=None),
        recent_missing_xg_team_rows=len(missing_xg),**audit,**health,
        historical_records_changed=False,formulas_changed=False,
        status='INPUTS_HELD' if health['blocked_leagues'] else 'READY_WITH_PARTIAL_XG' if missing_xg else 'READY')
    if write_status: atomic_json(root/'data/football-form/count-input-integrity-status.json',status)
    return view,status,rows

def permitted(rows,status):
    return [r for r in rows if r.get('league') not in status['blocked_leagues']]

def describe(status):
    if not status:return 'Shots input verification unavailable.'
    held=status.get('blocked_leagues',{})
    freshness_text=('New captures held for '+', '.join(sorted(held))+'.') if held else 'Completed-fixture coverage verified; a break without new results is not stale.'
    return (f"Inputs: {status.get('policy','unknown')} · {status.get('generated_at','unknown')}. "
            f"{freshness_text} Missing xG uses observed pairs only (recent missing team rows: {status.get('recent_missing_xg_team_rows',0)}). "
            'Earlier forecasts, outcomes and ROI retained as issued; corrected inputs apply to new forecasts only.')
