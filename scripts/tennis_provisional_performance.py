"""Audited provisional model selections, separate from confirmed alert delivery."""
from __future__ import annotations
import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from player_name_matching import fold_name_text

def read(path):
    if not path.exists(): return []
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))

def num(value):
    try: return float(value)
    except (TypeError,ValueError): return None

def norm(value):
    return ' '.join(fold_name_text(value or '').lower().replace('-', ' ').split())

def provisional_lane(row):
    if row.get('bet_type') == 'spread': return None
    truth={'1','true','yes'}
    gap=num(row.get('model_market_gap_pp'))
    hard=(row.get('side_flip','').lower() in truth and row.get('surface','').lower()=='hard'
          and gap is not None and gap <= 10 and set(row.get('policy_profiles','').split('|')) & {'strict','volume_200'}
          and row.get('data_coverage_tag','').upper()=='HIGH' and row.get('short_favorite_guard','').lower() not in truth)
    if hard: return 'provisional_hard'
    if row.get('replacement_cohorts') and (row.get('replacement_forward_eligible') or '1').lower() in truth:
        return 'provisional_expansion'
    return None

def fixture_key(row):
    pair=tuple(sorted((norm(row.get('player1')),norm(row.get('player2')))))
    side=row.get('selected_side') or row.get('side')
    selected=norm(row.get('player1' if side=='P1' else 'player2'))
    # Exact settled edition/date also joins a later capture of a rescheduled match.
    tour=row.get('tour_id') or row.get('source_tour_id') or row.get('settlement_tour_id') or ''
    return (row.get('match_date') or row.get('scheduled_date') or row.get('date'),pair,selected,tour)

def provisional_summary(root: Path, now: datetime | None=None) -> dict[str,Any]:
    now=now or datetime.now(timezone.utc)
    backtest=root/'data/backtest'
    # Same selection routed to an existing alert lane belongs to that lane's record.
    shared=set()
    for tag in ('','-volume200','-grass_bo3','-clay_bo3','-cpi_speed'):
        for row in read(backtest/f'strict-signals{tag}-archive.csv'):
            if row.get('side') in {'P1','P2'} and row.get('bet_type')!='spread':
                key=fixture_key(row)
                shared.add(key[:3])
    groups={lane:[] for lane in ('provisional_hard','provisional_expansion')}
    for row in read(backtest/'tennis-model-market-gap-archive.csv'):
        lane=provisional_lane(row)
        if lane: groups[lane].append(row)
    result={}
    for lane,raw in groups.items():
        unique={};duplicate=0
        for row in sorted(raw,key=lambda r:(r.get('captured_at') or r.get('date') or '',r.get('time_utc',''))):
            key=fixture_key(row)
            if key in unique: duplicate+=1;continue
            unique[key]=row
        overlap=0;counts=Counter();pnl=0.;stake=0.;dates=[];issues=[]
        for key,row in unique.items():
            if key[:3] in shared: overlap+=1;continue
            dates.append(row.get('captured_at','')[:10] or row.get('date',''))
            outcome=row.get('bet_outcome')
            odds=num(row.get('selected_odds'))
            status=row.get('settlement_status')
            capture=row.get('captured_at','')[:10]
            day=row.get('match_date')
            if status=='settled' and outcome=='VOID': counts['void']+=1;continue
            if odds is None or odds<=1 or (status=='settled' and capture and day and capture>day):
                counts['excluded']+=1;issues.append({'id':row.get('anomaly_id'),'reason':'invalid_price_or_capture_after_result_day'});continue
            if status=='settled' and row.get('settlement_version')=='2' and outcome in ('WIN','LOSS'):
                counts['wins' if outcome=='WIN' else 'losses']+=1
                stake+=.5;pnl+=.5*(odds-1 if outcome=='WIN' else -1)
            elif row.get('date','')>=now.date().isoformat() or status=='pending':counts['pending']+=1
            else:
                counts['unresolved']+=1
                issues.append({'id':row.get('anomaly_id'),'players':[row.get('player1'),row.get('player2')],'date':row.get('date'),'reason':row.get('settlement_note') or 'awaiting_verified_settlement'})
        result[lane]=dict(name='Provisional Hard' if lane=='provisional_hard' else 'Provisional Expansion',
            settled=counts['wins']+counts['losses'],wins=counts['wins'],losses=counts['losses'],void=counts['void'],
            pending=counts['pending']+counts['unresolved'],recent_pending=counts['pending'],overdue=counts['unresolved'],
            excluded=counts['excluded'],overlap_excluded=overlap,duplicate_captures=duplicate,
            roi_pct=100*pnl/stake if stake else None,pnl_units=round(pnl,6),staked_units=stake,
            since=min(dates,default=None),latest_signal_date=max(dates,default=None),as_of_date=now.date().isoformat(),generated_at=now.isoformat(),
            evidence_period='Reconstructed model-selection history; first recorded price, 0.5u per fixture. Shared selections assigned to their existing alert lane. Not a record of confirmed Telegram delivery.',issues=issues)
    return result

def format_provisional(record):
    title=record['name']+' model history'
    n=record['settled']
    if not n: return f"{title}: no verified settled selections yet | {record['pending']} pending."
    return (f"{title}: ROI {record['roi_pct']:+.2f}% | P/L {record['pnl_units']:+.2f}u | {n} settled ({record['wins']}W/{record['losses']}L)"
            + (' | small sample' if n<50 else '') + '\n'
            + f"Since {record['since']} | {record['void']} void | {record['recent_pending']} awaiting results | {record['overdue']} unresolved | {record['excluded']} excluded. Archived selections at 0.5u.")
