"""Skyline: immutable prematch forecasts, fixed 1u paper selections, exact-fixture outcomes."""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from pathlib import Path
from aerial_data import read, save
from aerial_market_capture import quoted_markets
from skyline_model import History, POLICY, VARIANTS, utc, valid, height_gap, predict, qualifies


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def retain(path, value):
    if path.exists(): return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f: json.dump(value, f, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return True


def resolve(record, matches, now):
    m=matches.get(str(record['fixture_id']))
    if not m or utc(m['date'])+timedelta(hours=3)>now: return None
    if utc(m['date']) != utc(record['kickoff']): return None
    rows=[p for p in m['players'] if str(p['id'])==record['player_id'] and str(p.get('team_id'))==record['team_id']]
    if len(rows)!=1: return None
    p=rows[0]
    # Paper convention: named starter only, own statistics, no substitution promotions.
    if p.get('starter') is False:
        return dict(status='void',headed_sot=None,source_sha256=m.get('source_sha256'),reason='Did not start')
    if p.get('starter') is not True or not valid(p.get('minutes')) or p['minutes']<=0:return None
    sot=p.get('headed_sot');headers=p.get('headed_shots')
    if not valid(sot) or not valid(headers) or not 0<=sot<=headers:return None
    return dict(status='win' if sot>=1 else 'loss',headed_sot=sot,minutes=p['minutes'],
                source_sha256=m.get('source_sha256'),settled_at=now.isoformat(),reason='Completed source match; own headed SOT')


def summarize(records, outcomes, variant, now):
    bets=[];paired=[]
    for r in records:
        if variant not in r['predictions']: continue
        o=outcomes.get(r['key'],{});status=o.get('status','pending');p=r['predictions'][variant]
        if status in ('win','loss'):paired.append((p,int(status=='win')))
        if r['selections'].get(variant):bets.append((r,status))
    settled=[(r,s) for r,s in bets if s in ('win','loss')]
    profit=sum(r['odds']-1 if s=='win' else -1 for r,s in settled)
    import math
    return dict(selections=len(bets),settled=len(settled),wins=sum(s=='win' for r,s in bets),losses=sum(s=='loss' for r,s in bets),
                void=sum(s=='void' for r,s in bets),pending=sum(s in ('pending','review') for r,s in bets),
                overdue=sum(s in ('pending','review') and utc(r['kickoff'])+timedelta(hours=8)<now for r,s in bets),
                settled_stake=len(settled),profit=profit,roi=100*profit/len(settled) if settled else None,
                fixtures=len({r['fixture_id'] for r,s in bets}),accuracy_n=len(paired),
                brier=sum((p-y)**2 for p,y in paired)/len(paired) if paired else None,
                log_loss=-sum(y*math.log(max(p,1e-8))+(1-y)*math.log(max(1-p,1e-8)) for p,y in paired)/len(paired) if paired else None)


def run(root, now=None, capture=False):
    now=now or datetime.now(timezone.utc);directory=root/'data/aerial/skyline'
    artifact=read(directory/'model.json',{});research=read(directory/'research.json',{})
    if not artifact.get('models'): raise ValueError('Skyline frozen model artifact missing')
    if artifact.get('created_at') and now < utc(artifact['created_at']): raise ValueError('Cannot capture before artifact exists')
    model_hash=digest(artifact)
    payload=read(root/'public/fair-odds-lab/aerial.json',{})
    prices=read(root/'data/goalkeeper-saves/aerial-headed-market-prices.json',{})
    archive=read(root/'data/aerial/history.json.gz',{}).get('matches',[])
    heights=read(root/'data/aerial/heights.json.gz',{})
    # Read-only research context is built solely from completed prior days.
    state=History()
    for m in sorted(archive,key=lambda m:m['date']):
        if m['date'][:10]<now.date().isoformat():state.add(m)
    excluded=Counter();board=[];added=0
    generated=payload.get('generated_at')
    fresh=generated and timedelta(0)<=now-utc(generated)<=timedelta(hours=3)
    if not fresh:excluded['stale_lineup_snapshot']+=1
    for f in payload.get('fixtures',[]) if fresh else []:
        if f.get('state') not in ('confirmed','expected'):continue
        if not now+timedelta(minutes=5)<utc(f['kickoff'])<=now+timedelta(hours=30) or now>=utc(f['valid_until']):continue
        if not f.get('observed_at') or not timedelta(0)<=now-utc(f['observed_at'])<=timedelta(hours=2 if f['state']=='confirmed' else 30):continue
        teams=f.get('teams',[]);ids=[str(p['id']) for t in teams for p in t['players']]
        if len(teams)!=2 or any(len(t['players'])!=11 for t in teams) or len(set(ids))!=22:
            excluded['incomplete_lineup']+=1;continue
        league_id=next((k for k,v in {'47':'Premier League','54':'Bundesliga','55':'Serie A','53':'Ligue 1','87':'La Liga'}.items() if v==f['competition']),None)
        if league_id is None:
            excluded['unsupported_competition']+=1;continue
        for i,t in enumerate(teams):
            for player in t['players']:
                if player.get('role') in ('GK','UNK'):continue
                gap=height_gap(player['id'],[p['id'] for p in teams[1-i]['players']],heights)
                features=state.features(player['id'],t['id'],league_id,f['kickoff'],gap)
                if not features:excluded['insufficient_history']+=1;continue
                c={'player':player['name'],'team_id':str(t['id']),'markets_to_check':['1+ headed shot on target']}
                quotes=quoted_markets(f,c,prices,now)
                if len(quotes)!=1:excluded['no_fresh_exact_price']+=1;continue
                quote=quotes[0];predictions=predict(features,artifact)
                key=digest([artifact['version'],str(f['id']),str(player['id']),'headed_sot_over_0.5'])
                record=dict(key=key,version=artifact['version'],model_sha256=model_hash,captured_at=now.isoformat(),
                    fixture_id=str(f['id']),player_id=str(player['id']),team_id=str(t['id']),player=player['name'],
                    team=t['name'],match=' v '.join(t['name'] for t in teams),competition=f['competition'],kickoff=f['kickoff'],
                    lineup=f['state'],lineup_observed_at=f['observed_at'],lineup_hash=digest(ids),
                    height_evidence={str(pid):heights.get(str(pid)) for pid in [player['id']]+[p['id'] for p in teams[1-i]['players']]},
                    market='1+ headed shot on target',odds=quote['odds'],quote=quote,features=features,predictions=predictions,
                    selections={v:qualifies(p,quote['odds'],features['expected_minutes']) for v,p in predictions.items()},
                    cohort='prospective_paper' if capture and f['state']=='confirmed' else 'preview',stake_policy=POLICY)
                board.append(record)
                if capture and f['state']=='confirmed':
                    added+=retain(directory/'forecasts'/f'{key}.json',record)
    records=[read(p) for p in sorted((directory/'forecasts').glob('*.json'))]
    if any(r['model_sha256'] != model_hash for r in records): raise ValueError('Frozen Skyline artifact changed within version')
    outcomes={};matches={str(m['id']):m for m in archive}
    for r in records:
        existing=read(directory/'outcomes'/f"{r['key']}.json",None)
        outcome=resolve(r,matches,now)
        # Recorded outcome conflicts are held for review, never silently overwritten.
        if existing and outcome and existing['status']!=outcome['status']:
            excluded['settlement_conflict']+=1
            outcomes[r['key']]={'status':'review'};continue
        if existing:outcomes[r['key']]=existing
        elif outcome:
            if capture:retain(directory/'outcomes'/f"{r['key']}.json",outcome)
            outcomes[r['key']]=outcome
    compact=lambda r:dict(key=r['key'],player=r['player'],match=r['match'],kickoff=r['kickoff'],lineup=r['lineup'],
        odds=r['odds'],price_at=r['quote']['captured_at'],predictions=r['predictions'],selections=r['selections'],
        captured_at=r['captured_at'],status=outcomes.get(r['key'],{}).get('status','pending'),
        headed_sot=outcomes.get(r['key'],{}).get('headed_sot'),expected_minutes=r['features']['expected_minutes'])
    ledger=sorted(records,key=lambda r:r['kickoff'],reverse=True)
    paired=[r for r in records if all(v in r['predictions'] for v in VARIANTS)]
    report=dict(version=artifact['version'],name='Skyline',generated_at=now.isoformat(),status='CAPTURING' if capture else 'PREVIEW',
        primary='baseline',policy=POLICY,model_sha256=model_hash,forecasts=len(records),new_forecasts=added,
        stats={v:summarize(records,outcomes,v,now) for v in VARIANTS},
        paired_stats={v:summarize(paired,outcomes,v,now) for v in VARIANTS},exclusions=dict(excluded),
        board=[compact(r) for r in board],ledger=[compact(r) for r in ledger[:1000]],ledger_total=len(ledger),
        research=research,price_generated_at=prices.get('generated_at'),lineup_generated_at=generated,
        settlement_policy='1u paper, own headed SOT only, void if not a starter. No Sub On Play On or promotional settlement. Source counts are not bookmaker receipts.',
        historical_roi=None,paired_settled_fixtures=len({r['fixture_id'] for r in paired if outcomes.get(r['key'],{}).get('status') in ('win','loss')}),paired_forward_count=sum(all(v in r['predictions'] for v in VARIANTS) and outcomes.get(r['key'],{}).get('status') in ('win','loss') for r in records))
    save(directory/'report.json',report)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--capture',action='store_true');args=p.parse_args()
    r=run(args.root,capture=args.capture);print(json.dumps({k:r[k] for k in ['version','status','forecasts','new_forecasts','stats','exclusions']}))
