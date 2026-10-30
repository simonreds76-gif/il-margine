"""Most DF: separate, frozen independent-NB paper observation; no messages or live writes."""
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
import argparse,csv,json,math,os
from tennis_paper_prices import norm as folded_name,stamp
from tennis_price_identity import canonical_price_name
from tennis_props_model import resolve_count_dispersion
from tennis_ace_compass import native_round
from tennis_hardcourt_scout import locked
import tennis_event_integrity as E

ROOT=Path(__file__).resolve().parents[1]
def norm(value):return canonical_price_name(folded_name(value))
REL=Path('data/tennis-props/shadow/most-df-v1')
CONFIG={'version':'most-df-independent-nb-v1','market':'most_df','distribution':'independent NB2 convolution',
        'selection':'first verified priced forecast; highest EV outcome at best fresh price; EV >=5%',
        'paper_stake':1,'actual_stake':0,'alerts':False,'review_settled_fixtures':150,
        'retirement':'manual contract review; never infer completed counts from a retirement',
        'alpha':{'ATP':0.10,'WTA':0.20},'automatic_promotion':False}
def digest(x):return sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def readj(p,default=None):return json.loads(p.read_bytes()) if p.exists() else ({} if default is None else default)
def csvrows(p):
    if not p.exists():return []
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def atomic(p,data):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False),encoding='utf8');os.replace(tmp,p)
def nb(mean,alpha):
    if not math.isfinite(mean+alpha) or not 0<=mean<=100 or not 0<alpha<=2:raise ValueError('invalid distribution')
    if mean==0:return [1.]
    r=1/alpha;p=r/(r+mean);values=[p**r];total=values[0]
    for k in range(1,4096):
        values.append(values[-1]*(k-1+r)/k*(1-p));total+=values[-1]
        if 1-total<1e-12:break
    if abs(1-total)>1e-10:raise ValueError('distribution tail not bounded')
    return [v/total for v in values]
def probabilities(mu1,mu2,a1,a2):
    left,right=nb(mu1,a1),nb(mu2,a2);p1=tie=p2=0.;below=0.
    for i,v in enumerate(left):
        eq=right[i] if i<len(right) else 0.;p1+=v*below;tie+=v*eq;p2+=v*max(0.,1-below-eq)
        below+=eq
    result=[p1,tie,p2]
    if min(result)<0 or abs(sum(result)-1)>1e-10:raise ValueError('invalid three-way probability')
    return result
def select(prices,probs):
    best=[]
    for i in range(3):
        q=max(prices,key=lambda r:(r['prices'][i],r['captured_at'],r['bookmaker']))
        best.append(dict(outcome=i,probability=probs[i],fair_odds=1/probs[i] if probs[i]>0 else None,
                         odds=q['prices'][i],ev_pct=100*(probs[i]*q['prices'][i]-1),bookmaker=q['bookmaker'],
                         source=q['source'],captured_at=q['captured_at'],market_probabilities=q['market_probabilities']))
    chosen=max(best,key=lambda r:(r['ev_pct'],-r['outcome']))
    return best,dict(chosen,selected=chosen['ev_pct']>=5)
def current_prices(rows,left,right,now):
    matching=[]
    for r in rows:
        if r.get('raw_market_name')!='Most Double Faults':continue
        if r.get('bookmaker') not in {'Bet365','Grosvenor'}:continue
        if (r.get('date')!=left['date'] or norm(r.get('tour'))!=norm(left['tour'])
            or norm(r.get('tournament'))!=norm(left['tournament'])
            or sorted([norm(r.get('player1')),norm(r.get('player2'))])!=sorted([norm(left['player']),norm(right['player'])])):continue
        ts,start=stamp(r.get('capture_ts')),stamp(r.get('match_start_utc'))
        if not ts or not start or not ts<=now<start or now-ts>timedelta(minutes=30):continue
        try:
            odds=[float(r[k]) for k in ['player1_odds','draw_odds','player2_odds']]
            if any(not math.isfinite(x) or x<=1 for x in odds):continue
            raw=json.loads(r['raw_market_json'])
            if sha256(r['raw_market_json'].encode()).hexdigest()!=r['evidence_sha256']:continue
            if raw.get('name')!='Most Double Faults':continue
            contracts=raw.get('odds')
            if not isinstance(contracts,list):continue
            if len(contracts)==1:
                evidence=[float(contracts[0][k]) for k in ['home','draw','away']]
            elif len(contracts)==3:
                values={norm(o.get('label')):float(o['odds']) for o in contracts}
                if len(values)!=3:continue
                evidence=[values[norm(r['player1'])],values['tie'],values[norm(r['player2'])]]
            else:continue
            if any(abs(a-b)>0.000051 for a,b in zip(odds,evidence)):continue
            if raw.get('captured_at') and stamp(raw['captured_at'])!=ts:continue
        except (KeyError,ValueError,TypeError):continue
        if norm(r['player1'])!=norm(left['player']):odds.reverse()
        book=r['bookmaker'];inv=[1/x for x in odds];total=sum(inv)
        if not .98<=total<=1.40:continue
        matching.append(dict(bookmaker=book,prices=odds,captured_at=ts.isoformat(),start=start.isoformat(),
                             source=r,market_probabilities=[p/total for p in inv]))
    latest={}
    for r in matching:latest[r['bookmaker']]=max(r['captured_at'],latest.get(r['bookmaker'],''))
    current=[r for r in matching if r['captured_at']==latest[r['bookmaker']]]
    if len({r['start'] for r in current})!=1:return [],'missing_or_conflicting_current_start'
    books=defaultdict(list)
    for r in current:books[r['bookmaker']].append(r)
    selected=[]
    for book,rs in books.items():
        if len({tuple(r['prices']) for r in rs})!=1:continue
        selected.append(rs[0])
    return selected,None if selected else 'missing_complete_fresh_contract'
def capture(root,folder,reg,now):
    board=root/'data/tennis-props/player-props-board.csv';reasons=Counter();pending=[]
    if not board.exists() or not 0<=now.timestamp()-board.stat().st_mtime<=7200:
        return dict(state='AWAITING_FRESH_FORECAST',checked_at=now.isoformat(),added=0,reasons={'board_stale_or_missing':1})
    board_sha=sha256(board.read_bytes()).hexdigest();rows=csvrows(board);grouped=defaultdict(list)
    for r in rows:
        if r.get('tour') not in CONFIG['alpha'] or r.get('generation_date')!=now.date().isoformat():reasons['unsupported_or_old_forecast']+=1;continue
        grouped[(r.get('tour'),r.get('tour_id'),r.get('date'),tuple(sorted([r.get('player_id',''),r.get('opponent_id','')])))].append(r)
    quote_path=root/'data/tennis-props/inbox'/f'most-df-1x2-{now.date().isoformat()}.csv'
    sources=[quote_path]+[root/'data/oncourt'/f'today_{tour.lower()}.csv' for tour in CONFIG['alpha']]
    source_hashes={str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in sources}
    quotes=csvrows(quote_path)
    native={tour:csvrows(root/'data/oncourt'/f'today_{tour.lower()}.csv') for tour in CONFIG['alpha']}
    for key,rs in grouped.items():
        if len(rs)!=2 or rs[0].get('player_id')!=rs[1].get('opponent_id') or rs[1].get('player_id')!=rs[0].get('opponent_id'):
            reasons['nonreciprocal_forecast']+=1;continue
        left,right=sorted(rs,key=lambda r:r['player_id'])
        if any(r.get('player_name_resolution') not in {'exact','explicit_alias','unique_first_last'} or r.get('df_confidence') not in {'HIGH','MED'} for r in rs):reasons['input_quality']+=1;continue
        rid,reason=native_round(left,native[left['tour']])
        if reason:reasons[reason]+=1;continue
        fixture=':'.join([left['tour'],left['tour_id'],rid,*sorted([left['player_id'],right['player_id']])]);uid=digest([fixture,'most_df'])
        dest=folder/'captures'/f'{uid}.json'
        if dest.exists():reasons['already_recorded']+=1;continue
        prices,reason=current_prices(quotes,left,right,now)
        if reason:reasons[reason]+=1;continue
        try:
            mu=[float(r['projected_dfs']) for r in [left,right]];alpha=CONFIG['alpha'][left['tour']]
            if alpha!=resolve_count_dispersion(left['tour'],'dfs'):raise ValueError('dispersion drift')
            p=probabilities(*mu,alpha,alpha)
        except (ValueError,KeyError,TypeError):reasons['invalid_distribution']+=1;continue
        best,selection=select(prices,p)
        item=dict(id=uid,fixture=fixture,market='most_df',captured_at=now.isoformat(),forecast_at=datetime.fromtimestamp(board.stat().st_mtime,timezone.utc).isoformat(),
                  board_sha256=board_sha,tour=left['tour'],tour_id=left['tour_id'],round_id=rid,date=left['date'],
                  players=[left['player_id'],right['player_id']],names=[left['player'],right['player']],tournament=left['tournament'],
                  start=prices[0]['start'],means=mu,alpha=[alpha,alpha],probabilities=p,prices=prices,best_prices=best,selection=selection,
                  inputs=rs,source_hashes=source_hashes,registration_sha256=sha256((folder/'registration.json').read_bytes()).hexdigest(),actual_stake=0)
        pending.append((dest,item));reasons['captured']+=1
    if sha256(board.read_bytes()).hexdigest()!=board_sha:raise ValueError('forecast changed during capture')
    if source_hashes!={str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in sources}:raise ValueError('fixture or quote source changed during capture')
    for dest,item in pending:
        dest.parent.mkdir(exist_ok=True)
        with dest.open('x',encoding='utf8') as f:json.dump(item,f,sort_keys=True,allow_nan=False)
    return dict(state='CAPTURED' if pending else 'NO_NEW_ELIGIBLE_QUOTES',checked_at=now.isoformat(),added=len(pending),reasons=dict(reasons))
def settle(root,records,outcomes,now):
    match_key=lambda r:tuple(r[k] for k in ('winner_id','loser_id','tour_id','round_id'))
    for tour in CONFIG['alpha']:
        pending=[r for r in records if r['id'] not in outcomes and r['tour']==tour and stamp(r['start'])<now]
        if not pending:continue
        tids={r['tour_id'] for r in pending};games=defaultdict(list);stats=defaultdict(list)
        for g in csvrows(root/'data/oncourt'/f'games_{tour.lower()}.csv'):
            if g['tour_id'] in tids:games[(g['tour_id'],g['round_id'],tuple(sorted([g['winner_id'],g['loser_id']])))].append(g)
        for s in csvrows(root/'data/oncourt'/f'stat_{tour.lower()}.csv'):
            if s['tour_id'] in tids:stats[match_key(s)].append(s)
        for r in pending:
            gs={digest(g):g for g in games[(r['tour_id'],r['round_id'],tuple(sorted(r['players'])))]}
            if len(gs)!=1:continue
            g=next(iter(gs.values()))
            if not r['captured_at'][:10]<=g['date']<=now.date().isoformat():continue
            if any(t in g.get('result','').upper() for t in ['RET','W/O','DEF','ABN']):continue
            if not E.completed_score(g.get('result')):continue
            ss={digest(s):s for s in stats.get(match_key(g),[])}
            if len(ss)!=1:continue
            s=next(iter(ss.values()))
            try:
                counts=[int(s['w_df']),int(s['l_df'])]
                if any(v<0 for v in counts):continue
            except (KeyError,ValueError,TypeError):continue
            if r['players'][0]!=g['winner_id']:counts.reverse()
            outcome=0 if counts[0]>counts[1] else 2 if counts[1]>counts[0] else 1
            outcomes[r['id']]=dict(status='settled',outcome=outcome,counts=counts,settled_at=now.isoformat(),result_date=g['date'],source_sha256=digest([g,s]))
def summary(records,outcomes,capture,reg,now):
    t=Counter();profit=0.;selections=[];cal=[]
    for r in records:
        s=r['selection'];o=outcomes.get(r['id']);status='pending';pnl=None
        if o:
            y=o['outcome'];p=r['probabilities'];q=s['market_probabilities'];status='settled'
            cal.append(dict(model_ll=-math.log(max(p[y],1e-15)),market_ll=-math.log(max(q[y],1e-15)),
                            model_brier=sum((v-int(i==y))**2 for i,v in enumerate(p)),market_brier=sum((v-int(i==y))**2 for i,v in enumerate(q)),
                            tie=int(y==1),p_tie=p[1],q_tie=q[1]))
        if not s['selected']:continue
        if o:
            won=s['outcome']==o['outcome'];t['wins' if won else 'losses']+=1;pnl=s['odds']-1 if won else -1;profit+=pnl;status='won' if won else 'lost'
        else:
            t['pending']+=1
            if now-stamp(r['start'])>timedelta(hours=48):t['overdue']+=1
        label=r['names'][0] if s['outcome']==0 else r['names'][1] if s['outcome']==2 else 'Tie'
        selections.append(dict(id=r['id'],date=r['date'],match=' vs '.join(r['names']),selection=label+' · Most double faults',
                               market='Most double faults',odds=s['odds'],bookmaker=s['bookmaker'],fair_odds=s['fair_odds'],ev_pct=s['ev_pct'],stake_units=1,status=status,pnl_units=pnl,captured_at=r['captured_at']))
    settled=t['wins']+t['losses'];calibration={k:sum(x[k] for x in cal)/len(cal) for k in cal[0]} if cal else {}
    return dict(model='Most Double Faults — independent NB benchmark',version=CONFIG['version'],status='PAPER OBSERVATION ONLY',generated_at=now.isoformat(),registered_at=reg['registered_at'],capture=capture,
                records=len(records),settled_fixtures=len(cal),settled=settled,wins=t['wins'],losses=t['losses'],pending=t['pending'],overdue=t['overdue'],void=0,stake_units=settled,pnl_units=profit,roi_pct=100*profit/settled if settled else None,
                calibration=calibration,selections=selections[::-1],review_due=len(cal)>=150,alerts_enabled=False,actual_stake=0,
                note='Uncalibrated independent DF benchmark. No ace dependence parameter. No alerts until contract/pricing review; unfinished matches await manual contract review. One first capture per fixture; historical quotes excluded.')
def weekly_text(r):
    if not r:return 'Most DF: no paper evidence snapshot.'
    roi=f"{r['roi_pct']:+.2f}%" if r.get('roi_pct') is not None else 'not available'
    return f"Most DF | PAPER OBSERVATION ONLY | {r.get('wins',0)}W/{r.get('losses',0)}L | {r.get('pnl_units',0):+.2f}u on {r.get('stake_units',0):g}u | ROI {roi} | {r.get('pending',0)} pending ({r.get('overdue',0)} overdue). {r.get('settled_fixtures',0)}/150 independent settled fixtures. Capture: {r.get('capture',{}).get('state','UNKNOWN')}. {'Fresh qualifying paper alerts enabled' if r.get('alerts_enabled') else 'Alerts disabled'}; unvalidated independent-count benchmark."
def run(root,now=None,register=False,settle_only=False,capture_only=False):
    now=now or datetime.now(timezone.utc);folder=root/REL
    with locked(folder):
        path=folder/'registration.json'
        if not path.exists():
            if not register:raise ValueError('Most DF not registered')
            atomic(path,dict(config=CONFIG,registered_at=now.isoformat(),code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),model_sha256=sha256((root/'scripts/tennis_props_model.py').read_bytes()).hexdigest()))
        reg=readj(path)
        from tennis_most_df_delivery import activated
        delivery_enabled=activated(root,reg,now)
        if reg['config']!=CONFIG or (reg['code_sha256']!=sha256(Path(__file__).read_bytes()).hexdigest() and not delivery_enabled) or reg['model_sha256']!=sha256((root/'scripts/tennis_props_model.py').read_bytes()).hexdigest():raise ValueError('Most DF frozen implementation changed')
        if now<stamp(reg['registered_at']):raise ValueError('Cannot capture before registration')
        health=readj(folder/'capture-status.json') if settle_only else capture(root,folder,reg,now)
        records=[readj(p) for p in sorted((folder/'captures').glob('*.json'))];outcomes=readj(folder/'outcomes.json')
        if not capture_only:settle(root,records,outcomes,now)
        report=summary(records,outcomes,health,reg,now)
        report['alerts_enabled']=delivery_enabled
        if delivery_enabled:
            report['note']='Uncalibrated independent DF benchmark. Qualifying fresh selections use the existing deduplicated paper Telegram digest; 1u reference, zero real stake. Retirements await contract review. Original registration, probabilities and first entry odds are unchanged.'
        atomic(folder/'outcomes.json',outcomes);atomic(folder/'capture-status.json',health);atomic(folder/'report.json',report)
        return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--register',action='store_true');ap.add_argument('--settle-only',action='store_true');ap.add_argument('--capture-only',action='store_true');a=ap.parse_args()
    print(weekly_text(run(a.root,register=a.register,settle_only=a.settle_only,capture_only=a.capture_only)))
