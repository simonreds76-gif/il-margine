"""Local, exact-fixture count evidence. Never changes a forecast or its odds."""
from __future__ import annotations
import json
import math
import csv
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from football_team_names import football_form_team_key as key

def stamp(value):
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError,TypeError):return None

def identity(row):
    return (row.get('match_date') or row.get('date'),row.get('league'),key(row.get('home_team')),key(row.get('away_team')))

def count(value):
    try:
        x=float(value)
        return int(x) if math.isfinite(x) and x>=0 and x.is_integer() else None
    except (ValueError,TypeError):return None

def verified_base_index(root: Path, now: datetime):
    """Only reciprocal, completed provider results; never forecasts or xG counts."""
    path=root/'data/football-form/team-match-base.csv'
    if not path.exists():return {}
    grouped=defaultdict(list)
    with path.open(encoding='utf-8-sig',newline='') as handle:
        for row in csv.DictReader(handle):
            if row.get('match_source') in {'football-data','fotmob_verified_fulltime'}:
                grouped[identity(row)].append(row)
    result={}
    for ident,rows in grouped.items():
        home=[r for r in rows if r.get('venue')=='home' and key(r['team'])==ident[2] and key(r['opponent'])==ident[3]]
        away=[r for r in rows if r.get('venue')=='away' and key(r['team'])==ident[3] and key(r['opponent'])==ident[2]]
        if len(home)!=1 or len(away)!=1:continue
        h,a=home[0],away[0];item={};conflict=False
        for metric in ('shots','corners'):
            values=[count(r.get(f'{metric}_{s}')) for r,s in [(h,'for'),(a,'against'),(a,'for'),(h,'against')]]
            if any(v is None for v in values):continue
            if values[0]!=values[1] or values[2]!=values[3]:conflict=True;break
            item.update({f'home_{metric}':values[0],f'away_{metric}':values[2]})
            if metric=='corners':item['total_corners']=values[0]+values[2]
        if conflict or not item:continue
        result[ident]=dict(item,home_team=h['team'],away_team=a['team'],source=h['match_source'],
            observed_at=now.isoformat(),evidence_path=str(path.relative_to(root)))
    return result

def count_result_index(root: Path, now: datetime):
    results=verified_base_index(root,now)
    for ident,row in snapshot_index(root,now).items():
        old=results.get(ident,{})
        conflicts=[k for k in ('home_shots','away_shots','total_corners')
                   if count(old.get(k)) is not None and count(row.get(k)) is not None and count(old[k])!=count(row[k])]
        results[ident]=dict(old,**row)
        if conflicts:results[ident]['conflicting_counts']=conflicts
    return results

def exact_result(row, results, now):
    kickoff=stamp(row.get('kickoff_utc'))
    result=results.get(identity(row))
    if not kickoff or now<kickoff+timedelta(hours=3) or not result or result.get('conflicting_counts'):return None
    observed=stamp(result.get('observed_at'))
    if observed is None or observed<kickoff+timedelta(hours=3) or observed>now:return None
    return result

def snapshot_index(root: Path, now: datetime):
    """Keep dated evidence, including corrections, without arbitrary +/-day joins."""
    result={}
    for path in sorted((root/'data/results-snapshot').glob('????-??-??.json')):
        payload=json.loads(path.read_text(encoding='utf-8-sig'))
        observed=stamp(payload.get('fetched_at'))
        if observed is None or observed>now:continue
        for league, data in payload.get('leagues',{}).items():
            for fid,row in data.get('fixtures',{}).items():
                parts=fid.split('|')
                if len(parts)!=3 or not row.get('source'):continue
                date,home,away=parts
                if key(row.get('home_team'))!=key(home) or key(row.get('away_team'))!=key(away):continue
                ident=(date,league,key(home),key(away))
                item=dict(row,observed_at=observed.isoformat(),evidence_path=str(path.relative_to(root)))
                if ident not in result or observed>stamp(result[ident]['observed_at']):result[ident]=item
    return result

def paired_result_rows(ledger, base, snapshots, now):
    """Overlay only verified post-match counts, retaining conflicts for the report."""
    output=list(base); audit=[]
    for row in ledger:
        kickoff=stamp(row.get('kickoff_utc')); fixture=snapshots.get(identity(row))
        if kickoff is None or now<kickoff+timedelta(hours=3) or not fixture:continue
        observed=stamp(fixture.get('observed_at'))
        if observed is None or observed<kickoff+timedelta(hours=3):continue
        side='home' if key(row['team'])==key(row['home_team']) else 'away' if key(row['team'])==key(row['away_team']) else None
        actual=count(fixture.get(f'{side}_shots')) if side else None
        if actual is None:continue
        output.append(dict(date=row['match_date'],league=row['league'],home_team=row['home_team'],away_team=row['away_team'],team=row['team'],shots_for=actual))
        audit.append(dict(contract_id=row['contract_id'],actual_team_shots=actual,source=fixture['source'],observed_at=fixture['observed_at'],evidence_path=fixture['evidence_path']))
    return output,audit
