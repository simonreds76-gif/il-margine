"""Supplement exact-fixture settlement evidence without altering frozen pricing.

Only unresolved contracts are affected. Current-schedule walkovers and a proven
replacement opponent are excluded for grading review, never fabricated results.
"""
import csv,json,re
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import tennis_match_shape as M


def supplemental(root,records,clock):
    wanted={r['fixture_key']:r for r in records if M.utc(r['quote']['scheduled_start'])<clock}
    if not wanted:return {}
    base=root/'data/oncourt';found={};games=[]
    today=base/'today_atp.csv';archive=base/'games_atp.csv'
    hashes={p.name:sha256(p.read_bytes()).hexdigest() for p in (today,archive) if p.exists()}
    if today.exists():
        with today.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                key='|'.join([r['tour_id'],r['round_id']]+sorted([r['player1_id'],r['player2_id']]))
                record=wanted.get(key);day=r.get('date','');score=r.get('result','').strip()
                if not record or not day or not re.fullmatch(r'(?:w\s*/\s*o|walkover)',score,re.I):continue
                start=M.utc(record['quote']['scheduled_start'])
                if day>clock.date().isoformat() or abs((datetime.fromisoformat(day[:10]).date()-start.date()).days)>1:continue
                found[key]=dict(status='excluded',reason='native_schedule_walkover_grading_review',score=score,result_date=day,evidence='today_atp.csv',source_sha256=hashes[today.name])
    pending={k:r for k,r in wanted.items() if k not in found and clock-M.utc(r['quote']['scheduled_start'])>timedelta(hours=48)}
    if pending and archive.exists():
        scopes={(k.split('|')[0],k.split('|')[1]) for k in pending}
        with archive.open(encoding='utf-8-sig',newline='') as f:
            games=[g for g in csv.DictReader(f) if (g['tour_id'],g['round_id']) in scopes and M.complete_score(g.get('result',''))]
        for key,r in pending.items():
            edition,round_id,a,b=key.split('|');pair={a,b};start=M.utc(r['quote']['scheduled_start'])
            candidates=[g for g in games if g['tour_id']==edition and g['round_id']==round_id and {g['winner_id'],g['loser_id']}&pair and g['date']<=clock.date().isoformat() and abs((datetime.fromisoformat(g['date'][:10]).date()-start.date()).days)<=1]
            if any({g['winner_id'],g['loser_id']}==pair for g in candidates):continue
            if candidates:
                found[key]=dict(status='excluded',reason='native_draw_opponent_changed_grading_review',evidence='games_atp.csv',source_sha256=hashes[archive.name],replacement_results=candidates)
    if hashes!={p.name:sha256(p.read_bytes()).hexdigest() for p in (today,archive) if p.exists()}:raise RuntimeError('native_results_changed_during_reconciliation')
    return found


def refresh_with_results(root,*args,**kwargs):
    clock=kwargs.get('clock') or (args[0] if args else None) or datetime.now(timezone.utc)
    folder=root/M.RELATIVE
    records=[M.read(p) for p in (folder/'captures').glob('*.json')]
    extra=supplemental(root,records,clock)
    if extra:
        evidence=dict(observed_at=clock.isoformat(),records=extra)
        path=folder/'result-evidence'/(M.digest(extra)+'.json')
        if not path.exists():M.immutable(path,evidence)
    original=M.outcome
    def resolve(record,games,at,reg_hash):
        result=original(record,games,at,reg_hash)
        if result['status']=='pending' and record['fixture_key'] in extra:
            # Integrity failures remain quarantined by original(), never overridden.
            return extra[record['fixture_key']]
        return result
    with patch.object(M,'outcome',resolve):
        return M.refresh(root,*args,**kwargs)
