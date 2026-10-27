"""Reconcile moved provisional dates only with two saved quotes and an exact result.

No widened name/date settlement window: the same named tournament/round must
appear in both saved Pinnacle snapshots, with one independently settled native
fixture. Keep original prices, stakes, generation dates and all archive rows.
Normal performance reporting deduplicates by the verified match date and keeps
the first published price. The journal retains both schedule snapshots.
"""
import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

FIELDS = ('result','bet_outcome','won_bet','match_date','player1_id','player2_id',
          'winner_id','loser_id','settlement_score','settlement_tour_id',
          'settlement_round_id','settlement_version','game_margin')

def read(path):
    if not path.exists(): return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def norm(value):return ' '.join(str(value or '').casefold().split())
def pair(row, raw=False):return tuple(norm(row.get(k)) for k in (('player1_name','player2_name') if raw else ('player1','player2')))
def lane(row):return tuple(norm(row.get(k) or default) for k,default in [('side',''),('bet_type','match'),('spread_line',''),('policy_mode','base'),('signal_profile','strict')])
def stamp(row):return str(row.get('generation_date') or '')[:10]

def reconcile(rows, root):
    root=Path(root);pending=[r for r in rows if r.get('settlement_status')=='no_match' and stamp(r)]
    if not pending:return []
    # Bounded recovery: unusual mass failures need investigation, not broad joins.
    if len(pending)>50:return []
    snapshots={};evidence=[]
    def quote(row):
        day=stamp(row);path=root/'data'/f'pinnacle-odds-{day}.csv'
        if day not in snapshots:snapshots[day]=(read(path),hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else '')
        matches=[q for q in snapshots[day][0] if pair(q,True)==pair(row) and q.get('match_date')==str(row.get('scheduled_date') or row.get('date'))[:10]]
        leagues={q.get('league_name') for q in matches}
        return (matches[0],snapshots[day][1]) if matches and len(leagues)==1 else (None,'')
    for old in pending:
        before,before_sha=quote(old)
        if not before or not before.get('league_name'):continue
        candidates=[]
        for other in rows:
            if other.get('settlement_status')!='settled' or pair(other)!=pair(old) or lane(other)!=lane(old):continue
            if not (stamp(old)<stamp(other)<=str(other.get('match_date') or '')):continue
            if any(not other.get(k) for k in ('settlement_tour_id','settlement_round_id','settlement_score','winner_id','loser_id')):continue
            after,after_sha=quote(other)
            if not after or after.get('league_name')!=before.get('league_name') or after.get('match_date')!=other.get('match_date'):continue
            try:drift=(date.fromisoformat(after['match_date'])-date.fromisoformat(before['match_date'])).days
            except ValueError:continue
            if drift==0 or abs(drift)>3:continue
            if old.get('source_tour_id') and old['source_tour_id']!=other['settlement_tour_id']:continue
            candidates.append((other,after,after_sha))
        keys={(r['settlement_tour_id'],r['settlement_round_id'],r['winner_id'],r['loser_id'],r['match_date'],r['settlement_score']) for r,_,_ in candidates}
        if len(keys)!=1:continue
        other,after,after_sha=min(candidates,key=lambda x:stamp(x[0]))
        evidence.append((old,other,before,after,before_sha,after_sha))
    if not evidence:return []
    # Native IDs, edition, round, date and score must all agree with source results.
    needed={(o['settlement_tour_id'],o['settlement_round_id'],o['winner_id'],o['loser_id'],o['match_date'],o['settlement_score']) for _,o,*_ in evidence}
    verified=set()
    with (root/'data/oncourt/games_atp.csv').open(encoding='utf-8-sig',newline='') as f:
        for g in csv.DictReader(f):
            k=tuple(g.get(field,'') for field in ('tour_id','round_id','winner_id','loser_id','date','result'))
            if k in needed:verified.add(k)
    journal=[];now=datetime.now(timezone.utc).isoformat()
    for old,other,before,after,before_sha,after_sha in evidence:
        key=tuple(other[k] for k in ('settlement_tour_id','settlement_round_id','winner_id','loser_id','match_date','settlement_score'))
        if key not in verified:continue
        original=dict(old);later_original=dict(other)
        for field in FIELDS:old[field]=other.get(field,'')
        old.update(settlement_status='settled',settled_at=now,
                   original_scheduled_start_utc=original.get('scheduled_start_utc',''),
                   original_scheduled_date=original.get('scheduled_date',''),
                   scheduled_start_utc=after.get('kickoff_iso',''),scheduled_date=after['match_date'],
                   settlement_note='Verified schedule correction from saved Pinnacle tournament/round snapshots and exact OnCourt result; repeated fixture, first published price retained in performance.',
                   schedule_reconciliation_version='1')
        other['duplicate_of']='strict:'+':'.join(key[:5])+':'+stamp(old)
        other['settlement_note']='Repeated capture of the reconciled fixture; first published price is retained for performance. '+other.get('settlement_note','')
        journal.append(dict(before=original,after=dict(old),native_fixture=list(key),
                            later_capture_before=later_original,later_capture_after=dict(other),
                            original_quote=before,corrected_quote=after,
                            original_snapshot_sha256=before_sha,corrected_snapshot_sha256=after_sha))
    return journal

def reconcile_and_save_journal(rows, root, *, dry_run=False):
    journal=reconcile(rows,root)
    if journal and not dry_run:
        folder=Path(root)/'data/backtest/schedule-reconciliations'
        folder.mkdir(parents=True,exist_ok=True)
        key=hashlib.sha256(json.dumps(journal,sort_keys=True).encode()).hexdigest()[:16]
        (folder/f'{key}.json').write_text(json.dumps(journal,indent=2),encoding='utf-8')
    return len(journal)
