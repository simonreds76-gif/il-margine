"""Keeper Watch v1: fixed forward-only paper comparison; no network or live edits."""
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean

from football_identity import read, write, folded
from goalkeeper_forecast_evidence import encode, timestamp
from goalkeeper_saves_live import predict_mean, price_side

LEAGUES = {'47':'epl','87':'la-liga','55':'serie-a','54':'bundesliga','53':'ligue-1'}
LABELS = {'Premier League':'epl','LaLiga':'la-liga','Serie A':'serie-a','Bundesliga':'bundesliga','Ligue 1':'ligue-1'}
LINES = (1.5, 2.5, 3.5, 4.5, 5.5)


def digest(value):
    return sha256(encode(value)).hexdigest()


def retain(folder, key, record):
    """An existing forecast/selection is never replaced by a later run."""
    path = folder / (sha256(key.encode()).hexdigest() + '.json')
    if path.exists():
        return False
    folder.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(record, handle, sort_keys=True, allow_nan=False)
    return True


def load_records(folder):
    paths = sorted(folder.glob('*.json'))
    if len(paths)>20000:
        raise ValueError('Keeper Watch archive requires review: record budget reached')
    return [read(p) for p in paths]


def targets(root, now):
    """Only already available source versions; disagreements remain unresolved."""
    versions = defaultdict(list)
    archive = read(root/'data/aerial/keeper-history.json.gz', {})
    for mid, records in archive.get('fixtures', {}).items():
        for r in records:
            observed=timestamp(r.get('observed_at') or r.get('recovered_at'))
            if observed and observed<=now:
                versions[str(mid)].append({'kickoff':r['kickoff'], 'league':LEAGUES.get(str(r.get('league_id'))),
                    'keepers':r['keepers'], 'source_hash':r['source_sha256']})
    for path in (root/'data/goalkeeper-saves/verified-player-targets').glob('*/*.json'):
        packet=read(path); observed=timestamp(packet.get('observed_at'))
        if not observed or observed>now:continue
        rows=[r for r in packet.get('rows',[]) if r.get('is_goalkeeper')]
        if not rows:continue
        mid=str(rows[0]['match_id'])
        if any(str(r['match_id'])!=mid for r in rows):continue
        versions[mid].append({'kickoff':rows[0]['kickoff'],'league':LABELS.get(rows[0].get('league')),
            'keepers':rows, 'source_hash':packet['targets_sha256']})
    resolved={}; history=defaultdict(list)
    for mid, records in versions.items():
        signatures={digest({'kickoff':r['kickoff'][:10], 'keepers':sorted([
            [str(k['player_id']),str(k['team_id']),k.get('started'),k.get('minutes'),k.get('saves'),k.get('event_saves'),k.get('target_conflict')]
            for k in r['keepers']])}) for r in records}
        if len(signatures)!=1:
            resolved[mid]={'conflict':True};continue
        r=records[0]
        if timestamp(r['kickoff']) is None or timestamp(r['kickoff'])+timedelta(hours=3)>now:continue
        resolved[mid]=r
        keepers=r['keepers']
        full=len(keepers)==2 and all(k.get('started') and k.get('minutes')==90 and k.get('saves') is not None
            and k['saves']==k.get('event_saves') and not k.get('target_conflict') for k in keepers)
        r['full_match_agreement']=full
        if full and r['league']:
            for k in keepers:
                history[(str(k['player_id']),str(k['team_id']),r['league'])].append(
                    {'date':r['kickoff'][:10], 'match_id':mid,'saves':k['saves']})
    for rows in history.values():rows.sort(key=lambda r:(r['date'],r['match_id']))
    return resolved,history


def keeper_feature(original, identity, league, now, history):
    day=now.date(); lower=(day-timedelta(days=365)).isoformat()
    rows=[r for r in history.get((identity['player_id'],identity['team_id'],league),[])
          if lower<=r['date']<day.isoformat()][-20:]
    if not rows:return original, {'appearances':0,'keeper_share':0}
    weights=[.93**(len(rows)-1-i) for i in range(len(rows))]; total=sum(weights)
    value=math.log((10*math.exp(original)+sum(w*r['saves'] for w,r in zip(weights,rows)))/(10+total))
    return value, {'appearances':len(rows),'keeper_share':total/(10+total),'latest_history':rows[-1]['date']}


def identity(row):
    lineup=row.get('_research_lineup') or {}; side=row.get('venue')
    if side not in ('home','away'):return None
    people=[p for p in lineup.get(side+'_starters',[]) if p.get('role_group')=='GK'
            and folded(p.get('name'))==folded(row.get('goalkeeper'))]
    mid=str(lineup.get('fotmob_match_id') or '');team=str(lineup.get(side+'_fotmob_team_id') or '')
    if len(people)!=1 or not mid.isdigit() or not team.isdigit():return None
    return {'match_id':mid,'player_id':str(people[0]['player_id']),'team_id':team}


def outcome(row, outcomes, now):
    r=outcomes.get(row['match_id'])
    if not r:return {'status':'pending','reason':'awaiting_verified_keeper_result'}
    if r.get('conflict'):return {'status':'review','reason':'conflicting_source_versions'}
    if r['kickoff'][:10]!=row['kickoff_at'][:10]:return {'status':'review','reason':'fixture_date_mismatch'}
    people=[k for k in r['keepers'] if str(k['player_id'])==row['player_id'] and str(k['team_id'])==row['team_id']]
    if len(people)!=1:return {'status':'review','reason':'keeper_identity_unresolved'}
    k=people[0];source={'source_hash':r['source_hash'],'settled_at':now.isoformat()}
    if k.get('started') is False:return {**source,'status':'void','reason':'confirmed_nonstarter'}
    if not r.get('full_match_agreement'):return {'status':'review','reason':'incomplete_or_conflicting_full_match_count'}
    return {**source,'status':'verified','actual':k['saves']}


def summary_rows(rows):
    settled=[r for r in rows if r['status'] in ('won','lost')];stake=.5*len(settled)
    profit=sum(r.get('profit',0) for r in rows)
    return {'selections':len(rows),'settled':len(settled),'wins':sum(r['status']=='won' for r in rows),
        'losses':sum(r['status']=='lost' for r in rows),'voids':sum(r['status']=='void' for r in rows),
        'pushes':sum(r['status']=='push' for r in rows),'pending':sum(r['status']=='pending' for r in rows),
        'review':sum(r['status']=='review' for r in rows),'overdue':sum(r.get('overdue',False) for r in rows),
        'stake':stake,'profit':profit,'roi':profit/stake if stake else None}


def run(candidates, live_params, root, *, now=None):
    now=now or datetime.now(UTC)
    config_path=root/'data/goalkeeper-saves/keeper-watch-v1.json'
    config=read(config_path); folder=root/'data/goalkeeper-saves/keeper-watch'
    if not config:return {'status':'NOT_INSTALLED'}
    config_hash=digest(config);start=timestamp(config['start_at'])
    if not start or now<start:raise ValueError('Invalid forward start')
    if digest(live_params)!=config['control_params_sha256']:raise ValueError('Current model changed: paired trial requires review')
    if digest(config['candidate_params'])!=config['candidate_params_sha256']:raise ValueError('Candidate parameter integrity failed')
    lock=read(folder/'lock.json')
    if lock and lock.get('config_sha256')!=config_hash:raise ValueError('Frozen trial configuration changed')
    if not lock:write(folder/'lock.json',{'config_sha256':config_hash,'start_at':config['start_at'],'actual_stake':0})
    outcomes,history=targets(root,now); history_hash=digest({str(k):v for k,v in history.items()})
    boards=defaultdict(list); skips=Counter();new_forecasts=0
    if len(candidates)>5000:raise ValueError('Candidate budget exceeded')
    for row in candidates:
        captured=timestamp(row.get('captured_at'));kickoff=timestamp(row.get('kickoff_at'))
        if not captured or not kickoff or not start<=captured<=now<kickoff or now-captured>timedelta(hours=6):
            skips['not_new_fresh_prematch']+=1;continue
        if row.get('blockers') or row.get('_research_features') is None:
            skips['blocked_or_missing_inputs']+=1;continue
        if row.get('lineup_status') not in ('predicted_starter','confirmed_starter'):
            skips['starter_unavailable']+=1;continue
        ids=identity(row)
        if not ids:skips['exact_identity_unavailable']+=1;continue
        features=list(row['_research_features'])
        if len(features)!=9 or not all(math.isfinite(x) for x in features):raise ValueError('Invalid features')
        if row['bookmaker'].casefold()!='bet365':skips['unregistered_settlement_rules']+=1;continue
        odds=float(row['odds_decimal']);line=float(row['line'])
        if not math.isfinite(odds) or odds<=1 or not math.isfinite(line) or line<0 or row['side'] not in ('over','under'):
            skips['invalid_market']+=1;continue
        control_mu=predict_mean(live_params,features,row['league'],row['venue'])
        if abs(control_mu-float(row['model_mean']))>.000051:raise ValueError('Current feature parity failed')
        candidate_features=features.copy()
        candidate_features[8],coverage=keeper_feature(features[8],ids,row['league'],now,history)
        candidate_mu=predict_mean(config['candidate_params'],candidate_features,row['league'],row['venue'])
        base={**ids,'event_id':str(row['event_id']),'kickoff_at':kickoff.isoformat(),'captured_at':captured.isoformat(),
            'registered_at':now.isoformat(),'goalkeeper':row['goalkeeper'],'home':row['home_team'],'away':row['away_team'],
            'league':row['league'],'lineup_status':row['lineup_status'],'features':features,'candidate_features':candidate_features,
            'history':coverage,'history_sha256':history_hash,'config_sha256':config_hash,'actual_stake':0}
        models={'current':(live_params,control_mu),'keeper_watch':(config['candidate_params'],candidate_mu)}
        forecast={**base,'models':{n:{'mean':mu,'probabilities':[price_side('over',x,2,mu,p['alpha'])['model_probability'] for x in LINES]}
                    for n,(p,mu) in models.items()}}
        new_forecasts+=retain(folder/'forecasts',ids['match_id']+':'+ids['player_id'],forecast)
        for name,(params,mu) in models.items():
            value=price_side(row['side'],line,odds,mu,params['alpha'])
            if 1.7<=odds<=3 and value['edge']>=.05:
                boards[(name,ids['match_id'])].append({**base,'model':name,'side':row['side'],'line':line,
                    'bookmaker':row['bookmaker'],'odds':odds,**value,'paper_stake':.5})
    new_selections=0
    for (name,mid),offers in boards.items():
        pick=min(offers,key=lambda r:(abs(r['odds']-2),-r['model_probability'],-r['edge']))
        new_selections+=retain(folder/'selections',name+':'+mid,pick)
    forecasts=load_records(folder/'forecasts'); selections=load_records(folder/'selections')
    paired=defaultdict(list);reasons=Counter(); settled_fixtures=set()
    for row in forecasts:
        result=outcome(row,outcomes,now)
        if result['status']!='verified':reasons[result.get('reason',result['status'])]+=1;continue
        # Retain first verified target separately. Later source corrections trigger review.
        key=row['match_id']+':'+row['player_id'];target_path=folder/'outcomes'/(sha256(key.encode()).hexdigest()+'.json')
        prior=read(target_path)
        if prior and prior['actual']!=result['actual']:reasons['changed_verified_result_requires_review']+=1;continue
        retain(folder/'outcomes',key,{**result,**{k:row[k] for k in ('match_id','player_id','team_id')}})
        settled_fixtures.add(row['match_id'])
        labels=[int(result['actual']>x) for x in LINES]
        for name,p in row['models'].items():
            probabilities=p['probabilities']
            paired[name].append({'fixture':row['match_id'],
                'brier':mean((p-y)**2 for p,y in zip(probabilities,labels)),
                'log_loss':mean(-y*math.log(max(1e-12,p))-(1-y)*math.log(max(1e-12,1-p)) for p,y in zip(probabilities,labels))})
    scored=[]
    for row in selections:
        result=outcome(row,outcomes,now)
        key=row['match_id']+':'+row['player_id'];prior=read(folder/'outcomes'/(sha256(key.encode()).hexdigest()+'.json'))
        if prior and result.get('actual') is not None and prior['actual']!=result['actual']:
            result={'status':'review','reason':'changed_verified_result_requires_review'}
        status=result['status'];profit=0
        if status=='verified':
            y=result['actual'];won=y>row['line'] if row['side']=='over' else y<row['line']
            status='push' if y==row['line'] else 'won' if won else 'lost'
            profit=0 if status=='push' else .5*(row['odds']-1) if won else -.5
        scored.append({**row,**result,'status':status,'profit':profit,
            'overdue':status in ('pending','review') and now-timestamp(row['kickoff_at'])>timedelta(hours=48)})
    metrics={}
    for name in ('current','keeper_watch'):
        groups=defaultdict(list)
        for r in paired[name]:groups[r['fixture']].append(r)
        metrics[name]={metric:mean(mean(r[metric] for r in rr) for rr in groups.values()) if groups else None for metric in ('brier','log_loss')}
    n=len(settled_fixtures)
    report={'name':'Keeper Watch v1','status':'TRACKING' if forecasts else 'CONNECTED_AWAITING_FIRST_CAPTURE',
        'generated_at':now.isoformat(),'start_at':config['start_at'],'actual_stake':0,'paper_stake':.5,'auto_promote':False,
        'forecast_keepers':len(forecasts),'forecast_fixtures':len({r['match_id'] for r in forecasts}),
        'new_forecasts':new_forecasts,'new_selections':new_selections,
        'last_capture_at':max((r['registered_at'] for r in forecasts),default=None),
        'paired_settled_fixtures':n,'paired_scores':metrics,'review_milestone':100 if n>=100 else 50 if n>=50 else None,
        'next_review_at':50 if n<50 else 100 if n<100 else None,'exclusions':dict(skips),'settlement_reasons':dict(reasons),
        'records':{name:summary_rows([r for r in scored if r['model']==name]) for name in ('current','keeper_watch')},
        'selections':[{k:r[k] for k in ('model','match_id','player_id','team_id','event_id','kickoff_at','registered_at',
            'captured_at','home','away','goalkeeper','side','line','bookmaker','odds','fair_odds','edge','lineup_status',
            'status','profit','actual','reason','overdue') if k in r} for r in sorted(scored,key=lambda r:r['kickoff_at'],reverse=True)],
        'coverage':'Captured Bet365 lines only; no claim of complete bookmaker coverage. No historical replay in this forward record.'}
    write(folder/'report.json',report)
    return report


def weekly_text(report):
    r=report or {}; records=r.get('records') or {}; parts=[]
    for key,label in (('keeper_watch','Keeper Watch'),('current','paired current')):
        s=records.get(key,{})
        roi=s.get('roi');text=f'{roi*100:+.1f}%' if roi is not None else 'awaiting settlement'
        parts.append(f"{label}: {s.get('wins',0)}W/{s.get('losses',0)}L, {s.get('profit',0):+.2f}u, ROI {text}, pending {s.get('pending',0)}, review {s.get('review',0)}, overdue {s.get('overdue',0)}")
    return f"GK paper comparison | {r.get('status','NOT_INSTALLED')} | "+' | '.join(parts)+f" | paired fixtures {r.get('paired_settled_fixtures',0)}; review {r.get('review_milestone') or r.get('next_review_at',50)} | no automatic promotion"
