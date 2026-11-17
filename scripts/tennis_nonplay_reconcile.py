"""Resolve paper records from dated non-played evidence. No forecasts or deliveries."""
import hashlib,json
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
from tennis_paper_walkover import csv_rows
from oncourt_nonplayed import verified_nonplayed
from tennis_settlement_evidence import game_key,registry,utc
from tennis_hardcourt_scout import atomic,locked,read

SCOUT=Path('data/tennis-ml-research/hardcourt-scout-v1')
DF=Path('data/tennis-props/shadow/most-df-v1')
EVIDENCE='verified-nonplayed.json'


def source_rows(base,tour,wanted):
    matches=defaultdict(list)
    if not wanted:return matches
    for g in verified_nonplayed(base/f'nonplayed-results_{tour}.csv'):
        key=game_key(g)
        if key in wanted:matches[key].append(g)
    return matches


def conflicts(base,tour,wanted):
    if not wanted:return set()
    found=set()
    for n in ('games','stat'):
        path=base/f'{n}_{tour}.csv'
        for row in csv_rows(path):
            k=game_key(row)
            if k in wanted:found.add(k)
    return found


def in_time(start,stamp,day,now):
    start,stamp=utc(start),utc(stamp)
    if not (start and stamp and stamp<start<=now):return False
    try:
        day=datetime.strptime(day,'%Y-%m-%d').date()
    except (ValueError,TypeError):return False
    return day<=now.date() and abs((start.date()-day).days)<=1


def compass(root,now):
    import tennis_ace_compass as ac
    folder=root/ac.REL
    if not (folder/'registration.json').is_file():return {}
    with ac.lock(folder):
        chain,head,error=registry(root)
        if error:raise ValueError(error)
        obs=ac.ledger(folder/'observations.jsonl');out=ac.readj(folder/'outcomes.json',{})
        pending={r['id']:r for r in obs if r['id'] not in out and r['fixture_key'].replace(':','|') in chain}
        wanted={r['fixture_key'].replace(':','|') for r in pending.values()}
        bad=conflicts(root/'data/oncourt','atp',wanted)
        side=source_rows(root/'data/oncourt','atp',wanted)
        changes={}
        for rid,r in pending.items():
            key=r['fixture_key'].replace(':','|');item=chain[key];q=r['row']
            if (item['kind']!='pair_not_played' or key in bad or side.get(key)
                or utc(item['observed_at'])>now or not in_time(q['match_start_utc'],r['registered_at'],item['event_date'],now)):continue
            changes[rid]=dict(status='void',actual=None,reason='verified_original_pair_not_played',
                settled_at=now.isoformat(),result_date=item['event_date'],source=item['note'],
                source_hash=item['sha256'],source_urls=[x['url'] for x in item['sources']],fixture_key=key)
        if changes:out.update(changes);ac.atomic(folder/'outcomes.json',out)
        # Catch recovery after an interruption between outcomes and the derived report.
        rep=ac.summarize(obs,out,ac.readj(folder/'registration.json',{}),ac.readj(folder/'capture-status.json',{}),now)
        old=ac.readj(folder/'report.json',{})
        if any(rep.get(k)!=old.get(k) for k in rep if k!='generated_at'):ac.atomic(folder/'report.json',rep)
        return {'added':len(changes),'ids':list(changes),'registry_head':head}


def evidence_for_lane(root,relative,now):
    folder=root/relative
    if not (folder/'registration.json').exists():return {}
    with locked(folder):
        book=read(folder/'outcomes.json');previous=read(folder/EVIDENCE);items=dict(previous)
        by_tour=defaultdict(dict)
        for f in sorted((folder/'captures').glob('*.json')):
            r=read(f)
            if relative==SCOUT:
                key=r['fixture_key'];record_id=key;start=r['quote']['kickoff_iso'];registered=r['registered_at'];tour='atp'
            else:
                key='|'.join([str(r['tour_id']),str(r['round_id']),*sorted(map(str,r['players']))])
                record_id=r['id'];start=r['start'];registered=r['captured_at'];tour=r['tour'].lower()
            if book.get(record_id,{}).get('status') not in (None,'pending') and record_id not in previous:continue
            by_tour[tour][key]=(record_id,start,registered)
        for tour,rows in by_tour.items():
            base=root/'data/oncourt';native=source_rows(base,tour,set(rows))
            wanted=set(native)|{k for k,(rid,*_) in rows.items() if rid in previous}
            bad=conflicts(base,tour,wanted)
            for key in wanted:
                rid,start,registered=rows[key];g=native.get(key,[])
                if key in bad or len(g)>1:
                    if rid in items:items[rid]=dict(status='quarantined',fixture_key=key,reason='conflicting_nonplayed_sources')
                    continue
                if not g or not in_time(start,registered,g[0]['date'],now):continue
                source=g[0]
                items[rid]=dict(status='void' if relative==SCOUT else 'contract_review',fixture_key=key,
                    reason='verified_native_walkover',date=source['date'],score=source['result'],source=source,
                    source_hash=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest())
        if items!=previous or not (folder/EVIDENCE).exists():atomic(folder/EVIDENCE,items)
        return {'retained':len(items),'new':len(items.keys()-previous.keys())}


def report(root,relative,raw):
    """Layer verified terminal evidence onto the latest frozen report, even after a new capture."""
    folder=Path(root)/relative;decisions=read(folder/EVIDENCE)
    if not decisions or not raw:return raw
    from copy import deepcopy
    if relative==DF:
        terminal=read(folder/'outcomes.json')
        ids={k for k,v in decisions.items() if v['status']=='contract_review' and k not in terminal}
        view=deepcopy(raw)
        view['verified_walkovers_for_contract_review']=sorted(ids)
        for row in view.get('selections',[]):
            if row['id'] in ids and row['status']=='pending':row['reason']='confirmed walkover; bookmaker contract review'
        return view
    from tennis_hardcourt_scout import active_registration,registrations
    from tennis_scout_opposition import summary
    view=deepcopy(raw);outcomes=read(folder/'outcomes.json')
    records=[read(p) for p in sorted((folder/'captures').glob('*.json'))]
    now=utc(view['generated_at']);active_hash,_=active_registration(folder,now)
    labels={k:r.get('input_revision','original') for k,r in registrations(folder)}
    corrections={}
    for r in records:
        k=r['fixture_key'];v=decisions.get(k)
        if not v or outcomes.get(k,{}).get('status')!='pending':continue
        outcomes[k]=v;corrections[k]=v
        if not r['selection']['qualifies']:continue
        revision=view['input_revisions'][labels[r['registration_sha256']]]
        revision['pending']-=1;revision[v['status']]=revision.get(v['status'],0)+1
        if r['registration_sha256']==active_hash:
            view['pending']-=1;view[v['status']]+=1
            if now-utc(r['quote']['kickoff_iso'])>timedelta(hours=48):view['overdue']-=1
    if not corrections:return raw
    view['recent_pending']=view['pending']-view['overdue']
    for name in ('selections','archived_selections'):
        for row in view.get(name,[]):
            v=corrections.get(row['fixture_key'])
            if v and row.get('status')=='pending':row.update(status=v['status'],reason=v['reason'],score=v.get('score'),result_date=v.get('date'),pnl_units=0 if v['status']=='void' else None)
    if view.get('fable_comparison'):
        view['fable_comparison']=summary(folder,records,outcomes,active_hash,now)
    view['nonplayed_settlements']=corrections
    return view


def run(root):
    now=datetime.now(timezone.utc)
    return dict(compass=compass(root,now),scout=evidence_for_lane(root,SCOUT,now),most_df=evidence_for_lane(root,DF,now))


def load_report(root,relative):
    folder=Path(root)/relative
    if not folder.exists():return {}
    with locked(folder):
        return report(root,relative,read(folder/'report.json'))

