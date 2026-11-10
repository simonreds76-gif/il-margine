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



def calendar_venue(group,tournament):
    """Same verified season/event, despite sponsor and Open-name differences.

    Use the category resolver already used by live inputs; do not introduce a
    fuzzy city join or broaden the paper protocol's competition scope.
    """
    from tennis_tournament_category import resolve_category, CALENDARS, normalized, contains
    date=tournament.get('date','')
    a=resolve_category(group,date,rank=tournament.get('rank'),round_id=4)
    b=resolve_category(tournament.get('name',''),date,rank=tournament.get('rank'),round_id=4)
    key=a.get('event_key')
    if not key or key!=b.get('event_key') or a['official_category']!=b['official_category']:
        return None
    # The shared resolver permits multiple aliases within a tier. A join must
    # additionally refuse a label naming two distinct calendar events.
    aliases=[x for values in CALENDARS.get(a.get('season'),{}).values() for x in values]
    for label in (group,tournament.get('name','')):
        hits={x for x in aliases if contains(normalized(label),x)}
        if hits!={key}:return None
    return key


def resolve_quote(q,index):
    """Resolve exact fresh fixtures without changing native files or formulas.

    Calendar event identity permits sponsor-name variants. A missing native
    date may use the verified bookmaker day; an existing date is never changed.
    The frozen player, edition, round, format and scope checks still run.
    """
    from tennis_breakpoint_forward import map_quote, norm, same_venue
    try:return map_quote(q,index)
    except ValueError as exc:
        if str(exc)!='UNMAPPED_EXACT_UPCOMING_FIXTURE':raise
    names,aliases,tours,today,hashes=index
    ids=[names.get(aliases.get(norm(q[k]),norm(q[k])),[]) for k in ('home','away')]
    if not all(len(x)==1 for x in ids) or ids[0]==ids[1]:raise ValueError('UNMAPPED_PLAYER')
    pair={ids[0][0],ids[1][0]}
    start=M.utc(q['scheduled_start']);seen=M.utc(q['captured_at'])
    if not seen or not start or not seen<start or start-seen>timedelta(days=3):raise ValueError('UNVERIFIED_BOOKMAKER_SCHEDULE')
    candidates=[]
    for row in today:
        if {int(row['player1_id']),int(row['player2_id'])}!=pair or row.get('result','').strip():continue
        if row.get('date') and row['date']!=start.date().isoformat():continue
        tournament=tours.get(int(row['tour_id']),{})
        key=calendar_venue(q['group'],tournament)
        if same_venue(q['group'],tournament.get('name','')) or key:
            candidates.append((row,tournament,key))
    if len(candidates)!=1:raise ValueError('UNMAPPED_EXACT_UPCOMING_FIXTURE')
    row,tournament,key=candidates[0]
    copy={**row,'date':start.date().isoformat()}
    # Only the mapper's local view is normalised; the raw quote remains intact.
    local_quote={**q,'group':tournament['name']} if key else q
    resolved=map_quote(local_quote,(names,aliases,tours,[copy],hashes))
    return {**resolved,'schedule_source':'native_schedule' if row.get('date') else 'exact_fresh_bookmaker_fixture',
            'native_date_was_blank':not bool(row.get('date')),'scheduled_start':q['scheduled_start'],
            'venue_identity_source':'verified_season_calendar' if key else 'exact_venue_phrase',
            'venue_event_key':key,'bookmaker_group':q['group'],'native_tournament_name':tournament['name']}

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
    with patch.object(M,'outcome',resolve), patch.object(M,'map_quote',resolve_quote):
        return M.refresh(root,*args,**kwargs)
