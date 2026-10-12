"""Local, exact-fixture count evidence. Never changes a forecast or its odds."""
from __future__ import annotations
import json
import math
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
