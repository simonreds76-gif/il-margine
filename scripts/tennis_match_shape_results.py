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
import tennis_match_shape_integrity as I


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

def refresh_with_results(root,clock=None,receipt=None,settle_only=False):
    clock=clock or datetime.now(timezone.utc)
    folder=root/M.RELATIVE
    if not (folder/'registration.json').exists():return {}
    # Own the existing lock once; M.refresh would attempt to acquire it again.
    with M.locked(folder):
        try:
            manifest_hash,manifest=I.verify(root,clock)
            records=[M.read(p) for p in sorted((folder/'captures').glob('*.json'))]
            old_ids={r['id'] for r in records}
            # Validate retained material before capturing or changing any outcome.
            I.evidence(folder,records,clock,M.complete_score)
            I.unresolved_conflicts(folder,clock)
            I.record_cohorts(folder,records,manifest_hash,manifest,clock)
            I.retain(folder,supplemental(root,records,clock),clock)
            retained=I.evidence(folder,records,clock,M.complete_score)
        except (ValueError,OSError,KeyError,TypeError,RuntimeError) as exc:
            health=dict(state='BLOCKED',checked_at=clock.isoformat(),reason=str(exc),captured=0,
                        operational_guard='manual_review_required')
            M.atomic(folder/'capture-status.json',health)
            M.atomic(folder/'operational/status.json',health)
            # Keep last validated report/outcomes byte-for-byte on a guard failure.
            return {**M.read(folder/'report.json'),'capture':health}
        previous=M.read(folder/'outcomes.json');original=M.outcome;notices=[]
        def resolve(record,games,at,reg_hash):
            result,conflicts=I.resolve(record,original(record,games,at,reg_hash),
                                       previous.get(record['id'],{}),retained.get(record['fixture_key'],[]))
            notices.extend(dict(capture_id=record['id'],fixture_key=record['fixture_key'],**x) for x in conflicts)
            return result
        with patch.object(M,'outcome',resolve),patch.object(M,'map_quote',resolve_quote):
            if not settle_only:
                try:health=M.capture(root,clock,receipt)
                except Exception as exc:health=dict(state='BLOCKED',checked_at=clock.isoformat(),reason=str(exc),captured=0)
                M.atomic(folder/'capture-status.json',health)
            records=[M.read(p) for p in sorted((folder/'captures').glob('*.json'))]
            I.record_cohorts(folder,records,manifest_hash,manifest,clock,{r['id'] for r in records}-old_ids)
            report=M.summarize(root,clock)
        for notice in notices:
            path=folder/'operational/conflicts'/(I.digest(notice)+'.json')
            if not path.exists():I.immutable(path,dict(first_observed_at=clock.isoformat(),**notice))
        conflicts=I.unresolved_conflicts(folder,clock)
        M.atomic(folder/'operational/status.json',dict(state='REVIEW_REQUIRED' if conflicts else 'VERIFIED',
                 checked_at=clock.isoformat(),manifest_sha256=manifest_hash,retained_fixtures=len(retained),
                 retained_evidence_packets=sum(len(rows) for rows in retained.values()),conflicts=len(conflicts)))
        return report
