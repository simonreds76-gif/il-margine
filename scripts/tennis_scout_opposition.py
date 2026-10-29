"""Frozen Fable comparison inside Hardcourt Scout. No network, alerts or live writes."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import ast, json, math, time

VERSION = 'fable-opposition-20261029-v1'
COEFFICIENTS = (0.9360995904874146, 0.08770306603399654, -0.07668374220690655, 0.786588356542098)
CLASS_WEIGHTS = {4: 1.08, 3: 1.04, 2: 1.0, 1: .72, 0: .42}
FILES = ('scripts/tennis_scout_opposition.py', 'scripts/tennis_scout_opposition_history.py',
         'scripts/tennis_direct_history.py', 'scripts/tennis_event_integrity.py', 'scripts/tennis_source_contract.py')

def read(path):
    return json.loads(path.read_bytes()) if path.exists() else {}

def digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def code_hash(path):
    return sha256(ast.dump(ast.parse(path.read_text(encoding='utf-8-sig')),include_attributes=False).encode()).hexdigest()

def sources(root):
    paths=[root/'data/oncourt'/n for n in ('players_atp.csv','tours_atp.csv','games_atp.csv','courts.csv')]
    paths += [root/'data/sackmann/atp_players.csv',root/'data/tennis-props/player-name-aliases.csv']
    paths += sorted((root/'data/sackmann').glob('atp_matches_*.csv'))
    return {p.relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest() for p in paths}

def history_features(history, as_of):
    """Exact reviewed proxy: pre-day overall K22, 1500 initial, 365d same surface."""
    low=(date.fromisoformat(as_of)-timedelta(days=365)).isoformat()
    history=sorted((r for r in history if r['available_date']<as_of),key=lambda r:(r['available_date'],r['key']))
    ratings={};idx=defaultdict(list);i=0
    while i<len(history):
        start=i;day=history[i]['available_date'];delta=defaultdict(list)
        while i<len(history) and history[i]['available_date']==day:i+=1
        for g in history[start:i]:
            a,b=g['winner'],g['loser'];ra,rb=ratings.get(a,1500.),ratings.get(b,1500.)
            change=22*(1-1/(1+10**((rb-ra)/400)));delta[a].append(change);delta[b].append(-change)
            if low<=g['date']<as_of:
                weight=CLASS_WEIGHTS.get(g['rank'],.8)
                idx[f"{a}|{g['surface']}"].append((rb,weight));idx[f"{b}|{g['surface']}"].append((ra,weight))
        for pid,ds in delta.items():ratings[pid]=ratings.get(pid,1500.)+math.fsum(ds)
    features={k:{'mean_opponent_elo':math.fsum(e*w for e,w in v)/math.fsum(w for _,w in v),'matches':len(v)} for k,v in idx.items()}
    return features,len(history)

def prepare(root,folder,as_of,now):
    """One replaceable cache; rebuild only when cutoff or source content changes."""
    from tennis_hardcourt_scout import atomic, utc
    reg=read(folder/'comparison-registration.json')
    if not reg:return None
    if reg.get('version')!=VERSION or reg.get('coefficients')!=list(COEFFICIENTS):raise ValueError('comparison registration differs')
    if not utc(reg.get('effective_at')) or now<utc(reg['effective_at']):raise ValueError('comparison not effective')
    actual={name:code_hash(root/name) for name in FILES}
    if actual!=reg.get('code_hashes'):raise ValueError('comparison code changed; review required')
    hashes=sources(root);key=digest({'as_of':as_of,'sources':hashes,'code':actual})
    cache=read(folder/'opposition-cache.json')
    if cache.get('key')==key:
        if digest(cache['features'])!=cache.get('feature_sha256'):raise ValueError('opposition cache checksum mismatch')
        return cache
    from tennis_scout_opposition_history import source_history
    # Preserve the original restricted history exactly; append only validated adult ITF.
    base,audit=source_history(root,False);adult,_=source_history(root,True)
    known={r['key'] for r in base};history=base+[r for r in adult if r['rank']==0 and r['key'] not in known]
    features,n=history_features(history,as_of)
    if n<100_000:raise ValueError('incomplete history; comparison unavailable')
    if sources(root)!=hashes:raise ValueError('history changed during comparison build')
    cache={'key':key,'as_of_exclusive':as_of,'generated_at':now.isoformat(),'source_hashes':hashes,
           'history_matches':n,'features':features,'feature_sha256':digest(features),'audit':audit}
    atomic(folder/'opposition-cache.json',cache)
    return cache

def predict(row,cache,registration_sha256):
    features=[cache['features'].get(f"{int(row[k])}|{row['surface']}") for k in ('player1_id','player2_id')]
    p=float(row['p1_win_prob']);values=[]
    for k in ('p_elo','p_serve_return','p_rank'):
        v=row.get(k)
        if v is None and k=='p_rank':values.append(0.);continue
        if v is None or not math.isfinite(float(v)) or not 0<=float(v)<=1:raise ValueError('missing or invalid '+k)
        v=max(1e-6,min(1-1e-6,float(v)));values.append(math.log(v/(1-v)))
    missing=not all(features)
    d=None if missing else features[0]['mean_opponent_elo']-features[1]['mean_opponent_elo']
    if not missing:
        z=math.fsum(a*b for a,b in zip(COEFFICIENTS,values+[d/400]))
        p=1/(1+math.exp(-z))
    return {'version':VERSION,'probability':p,'source':'baseline_fallback' if missing else 'correction',
            'reason':'no_same_surface_365d_history' if missing else None,'features':features,'opposition_difference':d,
            'source_as_of':cache['as_of_exclusive'],'source_sha256':cache['key'],'registration_sha256':registration_sha256,
            'actual_stake':0}

def attach(root,folder,pending,now,forecast_stamp):
    """Fail independently: the unchanged baseline packet still gets captured."""
    from tennis_hardcourt_scout import atomic,utc,select
    path=folder/'comparison-registration.json';reg=read(path)
    if not reg:return
    status={'version':VERSION,'checked_at':now.isoformat(),'actual_stake':0}
    if forecast_stamp<utc(reg['effective_at']):
        atomic(folder/'comparison-status.json',dict(status,state='WAITING_FOR_POST_REGISTRATION_FORECAST'));return
    if not pending:
        # Do not hide a real failure or stale history behind an empty pass.
        old=read(folder/'comparison-status.json')
        atomic(folder/'comparison-status.json',dict(old or status,last_checked_at=now.isoformat()));return
    began=time.monotonic()
    try:
        cache=prepare(root,folder,forecast_stamp.date().isoformat(),now)
        reg_hash=sha256(path.read_bytes()).hexdigest();counts=Counter()
        for _,p in pending:
            try:
                c=predict(p['components'],cache,reg_hash)
                finished=now+timedelta(seconds=time.monotonic()-began)
                if finished>=utc(p['quote']['kickoff_iso']):raise ValueError('comparison completed after scheduled start')
                c['calculated_at']=finished.isoformat();c['selection']=select(c['probability'],p['quote'],p['components'])
                c['paper_stake']=1 if c['selection']['qualifies'] else 0;p['comparison']=c;counts[c['source']]+=1
            except (KeyError,TypeError,ValueError) as exc:
                p['comparison']={'version':VERSION,'source':'unavailable','reason':str(exc),'actual_stake':0,'registration_sha256':reg_hash};counts['unavailable']+=1
        atomic(folder/'comparison-status.json',dict(status,state='CAPTURED' if not counts['unavailable'] else 'PARTIAL',coverage=dict(counts),source_as_of=cache['as_of_exclusive'],history_matches=cache['history_matches']))
    except Exception as exc:
        for _,p in pending:p['comparison']={'version':VERSION,'source':'unavailable','reason':str(exc),'actual_stake':0}
        atomic(folder/'comparison-status.json',dict(status,state='BLOCKED',reason=str(exc)))

def accuracy(scores):
    if not scores:return {'n':0,'brier':None,'log_loss':None,'mean_probability':None,'observed_win_rate':None,'bins':[]}
    bins=[]
    for lo in range(10):
        rows=[(p,y) for p,y in scores if lo/10<=p<(lo+1)/10 or lo==9 and p==1]
        if rows:bins.append({'from':lo/10,'to':(lo+1)/10,'n':len(rows),'predicted':math.fsum(p for p,y in rows)/len(rows),'observed':math.fsum(y for p,y in rows)/len(rows)})
    return {'n':len(scores),'brier':math.fsum((p-y)**2 for p,y in scores)/len(scores),
            'log_loss':math.fsum(-math.log(max(1e-12,p if y else 1-p)) for p,y in scores)/len(scores),
            'mean_probability':math.fsum(p for p,y in scores)/len(scores),'observed_win_rate':math.fsum(y for p,y in scores)/len(scores),'bins':bins}

def summary(folder,records,outcomes,active_hash,now):
    from tennis_hardcourt_scout import utc
    path=folder/'comparison-registration.json';reg=read(path)
    if not reg:return None
    rh=sha256(path.read_bytes()).hexdigest();effective=utc(reg['effective_at']);paired=[];coverage=Counter();bets={'baseline':[],'fable':[]};fixture_rows=[]
    for r in records:
        stamp=utc(r.get('registered_at'));c=r.get('comparison') or {};out=outcomes[r['fixture_key']]
        if not stamp or stamp<effective or r['registration_sha256']!=active_hash:continue
        coverage['since_registration']+=1
        if c.get('source') not in ('correction','baseline_fallback') or c.get('registration_sha256')!=rh:
            coverage['unavailable']+=1;continue
        coverage[c['source']]+=1
        calculated=utc(c.get('calculated_at'))
        if (c.get('actual_stake')!=0 or not 0<c.get('probability',0)<1 or not calculated
            or not effective<=stamp<=calculated<utc(r['quote']['kickoff_iso'])):
            coverage['invalid']+=1;continue
        p=c['probability'];y=int(out.get('winner_id')==r['players'][0])
        if out['status']=='settled':paired.append((r['probability'],p,r['market_probability'],y))
        fixture_rows.append({'fixture_key':r['fixture_key'],'players':r['names'],'tournament':r['tournament'],'kickoff':r['quote']['kickoff_iso'],
            'baseline_probability':r['probability'],'fable_probability':p,'source':c['source'],'status':out['status']})
        for arm,prob,sel in [('baseline',r['probability'],r['selection']),('fable',p,c['selection'])]:
            if not sel['qualifies']:continue
            side=sel['side'];odds=r['quote']['odds'+str(side)];won=None;pnl=None
            if out['status']=='settled':won=r['players'][side-1]==out['winner_id'];pnl=odds-1 if won else -1
            elif out['status']=='void':pnl=0
            bets[arm].append({'fixture_key':r['fixture_key'],'kickoff':r['quote']['kickoff_iso'],'captured_at':r['registered_at'],
                'player':r['names'][side-1],'opponent':r['names'][2-side],'tournament':r['tournament'],'odds':odds,
                'probability':prob if side==1 else 1-prob,'status':out['status'],'score':out.get('score'),'reason':out.get('reason'),
                'won':won,'pnl_units':pnl,'paper_stake':1,'actual_stake':0,'source':c['source']})
    arms={}
    for arm,rows in bets.items():
        done=[b for b in rows if b['status']=='settled'];profit=math.fsum(b['pnl_units'] for b in done);tally=Counter(b['status'] for b in rows)
        arms[arm]={'selections_total':len(rows),'settled':len(done),'wins':sum(b['won'] for b in done),'losses':sum(not b['won'] for b in done),
            'stake_units':len(done),'pnl_units':profit,'roi_pct':100*profit/len(done) if done else None,
            'pending':tally['pending'],'void':tally['void'],'quarantined':tally['quarantined'],
            'overdue':sum(b['status']=='pending' and now-utc(b['kickoff'])>timedelta(hours=48) for b in rows),
            'selections':sorted(rows,key=lambda b:b['captured_at'],reverse=True)[:100]}
    acc={name:accuracy([(r[i],r[3]) for r in paired]) for name,i in [('baseline',0),('fable',1),('market',2)]}
    return {'version':VERSION,'effective_at':reg['effective_at'],'actual_stake':0,'cohort':'same post-registration captures; active Scout input revision',
        'coverage':dict(coverage),'paired_settled_fixtures':len(paired),'accuracy':acc,'arms':arms,'capture':read(folder/'comparison-status.json'),
        'fixtures':sorted(fixture_rows,key=lambda r:r['kickoff'],reverse=True)[:100],
        'milestones_reached':[n for n in (50,100) if len(paired)>=n],'historical_replay_included':False,
        'note':'Frozen coefficients; 1u paper selections. Same captured Pinnacle prices and exact outcomes. Missing history uses baseline; source/code failures remain unavailable. No alerts or automatic promotion.'}

def weekly_text(c):
    if not c:return ''
    lines=['Fable correction alongside Scout | same forward cohort | PAPER ONLY']
    for name,label in [('baseline','Scout baseline'),('fable','Fable frozen')]:
        a=c['arms'][name];q=c['accuracy'][name];roi='awaits settlement' if a['roi_pct'] is None else f"{a['roi_pct']:+.2f}%"
        scores='awaits settlement' if not q['n'] else f"Brier {q['brier']:.4f}; log loss {q['log_loss']:.4f}; predicted {q['mean_probability']:.1%} / observed {q['observed_win_rate']:.1%}"
        lines.append(f"{label}: {a['wins']}W/{a['losses']}L, {a['pnl_units']:+.2f}u/{a['stake_units']}u, ROI {roi}; {a['pending']} pending, {a['void']} void, {a['quarantined']} quarantined. {scores}.")
    cov=c['coverage'];lines.append(f"{c['paired_settled_fixtures']} paired settled fixtures; {cov.get('baseline_fallback',0)} history fallbacks, {cov.get('unavailable',0)} unavailable. Since {c['effective_at']}. Capture {c['capture'].get('state','AWAITING_FIRST_RUN')}. Same 50/100 fixture review; no automatic promotion.")
    return '\n'.join(lines)
