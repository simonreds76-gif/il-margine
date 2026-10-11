"""Astrissimo v1: frozen market residual model, ATP main-draw paper evidence.

No odds requests, refitting, real stakes, or retrospective forward enrolment.
Seed generation is an explicit offline operation; daily runs only replay new results.
"""
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import csv, itertools, json, math, os, re, subprocess, sys, tempfile
from tennis_astrissimo_quotes import load_quotes, quote_for, utc, full_name
from tennis_source_contract import VERSION as INPUT_CONTRACT, court_surfaces, service_points

RELATIVE = Path('data/tennis-ml-research/astrissimo-v1')
WEIGHTS = [0.16764673546760073, -0.24399983383530335, 0.3263749765950651, -0.3500502033877772]
MODEL = {'name':'Astrissimo', 'version':'astrissimo-v1', 'weights':WEIGHTS,
         'features':['overall_elo_gap_400','surface_elo_gap_400','serve_return_gap_x10','shrunk_h2h_gap'],
         'scope':'ATP main draw only; no Challenger, qualifying, team events or doubles',
         'odds_min':1.5, 'odds_max':4., 'probability_min':.4, 'ev_min':.05,
         'paper_stake':1., 'actual_stake':0, 'calibration':'fixed logistic market residual; no automatic fitting'}
MODEL_HASH = sha256(json.dumps(MODEL,sort_keys=True).encode()).hexdigest()
CATEGORIES = {'ATP250','ATP500','Masters 1000','Grand Slam','Masters Cup'}

def read(path, default=None):
    return json.loads(path.read_bytes()) if path.exists() else ({} if default is None else default)

def atomic(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False),encoding='utf8');tmp.replace(path)

@contextmanager
def locked(folder):
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/'worker.lock').open('a+b') as f:
        if os.name=='nt':
            import msvcrt
            if not f.tell():f.write(b'0');f.flush()
            f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield

def sigmoid(x):return 1/(1+math.exp(-max(-30,min(30,x))))
def surface(x):
    x=str(x).lower()
    return 'hard' if 'hard' in x else x if x in ('clay','grass','carpet') else 'unknown'
def skey(a,s):return f'{a}|{s}'
def pair(a,b):return '|'.join(sorted((str(a),str(b)),key=int))
def empty():return {'elo':{},'surface_elo':{},'stats':{},'h2h':{}}
def features(state,a,b,s):
    a,b=str(a),str(b)
    def rate(p):
        v=state['stats'].get(skey(p,s),[0]*4)
        return (v[0]+325)/(v[1]+500)+(v[2]+175)/(v[3]+500)
    h=state['h2h'].get(pair(a,b),[0,0]);gap=(h[0]-h[1])/(sum(h)+20)*(1 if int(a)<int(b) else -1)
    return [(state['elo'].get(a,1500)-state['elo'].get(b,1500))/400,
            (state['surface_elo'].get(skey(a,s),1500)-state['surface_elo'].get(skey(b,s),1500))/400,
            (rate(a)-rate(b))*10,gap]
def probability(x,q):
    if not 0<q<1 or len(x)!=4 or not all(math.isfinite(v) for v in x):raise ValueError('invalid inputs')
    return sigmoid(math.log(q/(1-q))+sum(w*v for w,v in zip(WEIGHTS,x)))
def update(state,m):
    a,b=str(m['p1']),str(m['p2']);s=surface(m['surface']);y=int(m['winner']==0)
    for field,aa,bb in [('elo',a,b),('surface_elo',skey(a,s),skey(b,s))]:
        values=state[field];ea,eb=values.get(aa,1500.),values.get(bb,1500.)
        change=24*(y-sigmoid(math.log(10)*(ea-eb)/400));values[aa]=ea+change;values[bb]=eb-change
    h=state['h2h'].setdefault(pair(a,b),[0,0]);h[0 if int(a if y else b)==min(int(a),int(b)) else 1]+=1
    for side,p in [(1,a),(2,b)]:
        v=m.get(f'stats{side}') or {};sv,rv=v.get('serve'),v.get('return')
        if sv and rv and sv[1]>0 and rv[1]>0 and 0<=sv[0]<=sv[1] and 0<=rv[0]<=rv[1]:
            key=skey(p,s);old=state['stats'].get(key,[0]*4)
            state['stats'][key]=[o*.97+n for o,n in zip(old,[*sv,*rv])]
def choose(p,q):
    eligible=[]
    for side,prob,odds in [(0,p,q['odds1']),(1,1-p,q['odds2'])]:
        ev=prob*odds-1
        if 1.5<=odds<=4 and prob>=.4 and ev>=.05:
            eligible.append({'side':side,'odds':odds,'probability':prob,'fair_odds':1/prob,'ev_pct':100*ev,'paper_stake':1.})
    return max(eligible,key=lambda s:s['ev_pct']) if eligible else None

def build_seed(archive_path,predictions_path,folder):
    """Replay original history and verify every archived evaluation probability."""
    archive=read(archive_path);seen={}
    for m in archive['matches']+archive['results']:
        if re.search(r'ret|w/o|walk|abd|def',m.get('score',''),re.I) or not re.search(r'\d[-:]\d',m.get('score','')) or m['winner'] not in (0,1):continue
        key=(m['date'],min(m['p1'],m['p2']),max(m['p1'],m['p2']))
        if key in seen:
            previous=seen[key]
            if previous['p1' if previous['winner']==0 else 'p2']!=m['p1' if m['winner']==0 else 'p2']:raise ValueError('conflicting result')
        else:seen[key]=m
    with predictions_path.open(newline='',encoding='utf8') as f:expected={r['id']:r for r in csv.DictReader(f)}
    state=empty();checked=0;error=0.
    for day,group in itertools.groupby(sorted(seen.values(),key=lambda m:(m['date'],m['id'])),key=lambda m:m['date']):
        group=list(group)
        for m in group:
            if m['id'] in expected:
                r=expected[m['id']];p=probability(features(state,m['p1'],m['p2'],surface(m['surface'])),float(r['market']))
                error=max(error,abs(p-float(r['market_residual'])));checked+=1
        for m in group:update(state,m)
    if checked!=len(expected) or error>1e-10:raise ValueError(f'parity failed: {checked}, {error}')
    state.update(through=archive['through'],players=archive['players'],source_sha256=sha256(archive_path.read_bytes()).hexdigest(),model_hash=MODEL_HASH)
    atomic(folder/'seed.json',state)
    receipt={'seed_sha256':sha256((folder/'seed.json').read_bytes()).hexdigest(),'model_hash':MODEL_HASH,
             'parity_fixtures':checked,'maximum_probability_error':error,'historical_matches':len(seen),'through':archive['through']}
    atomic(folder/'seed-receipt.json',receipt);atomic(folder/'model.json',MODEL);return receipt

def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)

def live_state(root,folder,cutoff,now):
    seed=folder/'seed.json';receipt=read(folder/'seed-receipt.json')
    if sha256(seed.read_bytes()).hexdigest()!=receipt.get('seed_sha256') or receipt.get('model_hash')!=MODEL_HASH:raise ValueError('seed or frozen model changed')
    state=read(seed)
    if state['through']>=cutoff:raise ValueError('seed contains results on or after forecast cutoff')
    source=root/'data/oncourt';paths=[source/f'{kind}_atp.csv' for kind in ('players','tours','games','stat')]+[source/'courts.csv']
    manifest={}
    for path in paths:
        age=now.timestamp()-path.stat().st_mtime
        if not -60<=age<=48*3600:raise ValueError('OnCourt source export stale: '+path.name)
        manifest[path.name]={'mtime_ns':path.stat().st_mtime_ns,'size':path.stat().st_size}
    names=defaultdict(list)
    for p in state['players']:names[full_name(p['name'])].append(str(p['index']))
    identities={};native_players={p['id']:p for p in rows(source/'players_atp.csv')}
    for p in native_players.values():
        matches=names.get(full_name(p['name']),[])
        if len(matches)==1 and '/' not in p['name']:identities[p['id']]=matches[0]
    tours={r['id']:r for r in rows(source/'tours_atp.csv')};courts=court_surfaces(source/'courts.csv',combine_hard=True)
    games={};conflicts=set();skipped=Counter()
    for g in rows(source/'games_atp.csv'):
        if not state['through']<g.get('date','')[:10]<cutoff:continue
        t=tours.get(g['tour_id'],{});sf=surface(courts.get(t.get('court_id')))
        if any(p not in identities for p in [g['winner_id'],g['loser_id']]):skipped['identity_unmapped']+=1;continue
        if sf=='unknown' or not re.search(r'\d-\d',g['result']) or re.search(r'RET|W/O|WALK|ABD|DEF',g['result'],re.I):continue
        # The seed includes ATP/Challenger/qualifying history. Avoid adding ITF or team/doubles records.
        from tennis_tournament_category import resolve_category
        category=resolve_category(t.get('name'),t.get('date'),t.get('rank'),g['round_id'])['official_category']
        if category not in CATEGORIES|{'Challenger'}:skipped['unsupported_history_category']+=1;continue
        sets=[(int(a),int(b)) for a,b in re.findall(r'(\d+)-(\d+)',re.sub(r'\([^)]*\)','',g['result']))]
        required=3 if category=='Grand Slam' and int(g['round_id'])>=4 else 2
        if sum(a>b for a,b in sets)!=required or sum(b>a for a,b in sets)>=required:skipped['incomplete_history_result']+=1;continue
        key=(g['winner_id'],g['loser_id'],g['tour_id'],g['round_id'])
        if key in games and games[key]!=g:conflicts.add(key)
        games[key]=g
    stats={}
    for r in rows(source/'stat_atp.csv'):
        key=tuple(r[k] for k in ('winner_id','loser_id','tour_id','round_id'))
        if key in games:
            if key in stats and stats[key]!=r:conflicts.add(key)
            stats[key]=r
    accepted=[]
    for key,g in games.items():
        if key in conflicts:skipped['conflicting_history']+=1;continue
        t=tours[g['tour_id']];m={'id':'|'.join(key),'date':g['date'][:10],'p1':identities[g['winner_id']],'p2':identities[g['loser_id']],
                              'winner':0,'surface':courts[t['court_id']]}
        stat=stats.get(key)
        if stat:
            for n,prefix in [(1,'w_'),(2,'l_')]:
                try:
                    sv=service_points(stat,prefix);won=int(stat[prefix+'w1s'])+int(stat[prefix+'w2s']);rv=[int(stat[prefix+'rpw']),int(stat[prefix+'rpwof'])]
                    m[f'stats{n}']={'serve':[won,sv],'return':rv}
                except (ValueError,KeyError,TypeError):skipped['invalid_point_statistics']+=1
        accepted.append(m)
    for m in sorted(accepted,key=lambda r:(r['date'],r['id'])):update(state,m)
    # Detect concurrent exports without hashing 100MB repeatedly.
    if any(path.stat().st_mtime_ns!=manifest[path.name]['mtime_ns'] or path.stat().st_size!=manifest[path.name]['size'] for path in paths):raise ValueError('sources changed during replay')
    evidence={'seed_sha256':receipt['seed_sha256'],'source_manifest':manifest,'history_updates':len(accepted),'exclusions':dict(skipped),'last_result':max([state['through']]+[m['date'] for m in accepted]),'replayed_results_sha256':sha256(json.dumps(accepted,sort_keys=True).encode()).hexdigest()}
    return state,identities,evidence

def eligible(row):
    if str(row.get('player1_id'))==str(row.get('player2_id')):return 'placeholder_fixture'
    if row.get('official_category') not in CATEGORIES:return 'outside_ATP_main_draw'
    if row.get('source_contract')!=INPUT_CONTRACT or row.get('model_policy')!='category_corrected':return 'unsupported_inputs'
    if int(row.get('round_id',-1))<4:return 'qualifying_excluded'
    if surface(row.get('surface'))=='unknown':return 'unknown_surface'
    return None

def capture(root,production_rows,folder=None,now=None):
    folder=folder or root/RELATIVE;now=now or datetime.now(timezone.utc)
    with locked(folder):
        counts=Counter();quotes,qhash=load_quotes(root,now);candidates=[];seen=set()
        for row in production_rows:
            reason=eligible(row)
            if reason:counts[reason]+=1;continue
            q,reason=quote_for(row,quotes)
            if not q:counts[reason]+=1;continue
            if not .95<=1/q['odds1']+1/q['odds2']<=1.3:counts['invalid_book_percentage']+=1;continue
            key='|'.join([str(row['tour_id']),str(row['round_id']),*sorted([str(row['player1_id']),str(row['player2_id'])])])
            if key in seen:raise ValueError('duplicate fixture')
            seen.add(key);path=folder/'captures'/(sha256(key.encode()).hexdigest()+'.json')
            if path.exists():counts['already_captured']+=1;continue
            candidates.append((row,q,key,path))
        if len(candidates)>100:raise ValueError('unexpected candidate count')
        if candidates:
            state,identities,evidence=live_state(root,folder,now.date().isoformat(),now)
            source=root/'data/oncourt';native_players={p['id']:p for p in rows(source/'players_atp.csv')}
            tours={r['id']:r for r in rows(source/'tours_atp.csv')};courts=court_surfaces(source/'courts.csv',combine_hard=True)
            from tennis_tournament_category import resolve_category
            for row,q,key,path in candidates:
                ids=[str(row['player1_id']),str(row['player2_id'])]
                if any(p not in identities for p in ids):counts['unverified_player_identity']+=1;continue
                if any(full_name(native_players[p]['name'])!=full_name(row[f'player{i+1}']) for i,p in enumerate(ids)):counts['forecast_name_id_mismatch']+=1;continue
                tour=tours.get(str(row['tour_id']),{})
                verified=resolve_category(tour.get('name'),tour.get('date'),tour.get('rank'),row['round_id'])
                if verified['official_category']!=row['official_category'] or surface(courts.get(tour.get('court_id')))!=surface(row['surface']):counts['forecast_tournament_mismatch']+=1;continue
                mapped=[identities[p] for p in ids]
                if mapped[0]==mapped[1]:counts['ambiguous_player_identity']+=1;continue
                x=features(state,*mapped,surface(row['surface']));p=probability(x,q['market_p1']);selection=choose(p,q)
                registered=datetime.now(timezone.utc)
                if not utc(q['captured_at'])<=registered<utc(q['kickoff_iso']) or registered-utc(q['captured_at'])>timedelta(hours=2):counts['expired_quote']+=1;continue
                packet={'schema_version':1,'model_hash':MODEL_HASH,'implementation_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'version':MODEL['version'],'fixture_key':key,
                        'registered_at':registered.isoformat(),'players':ids,'names':[row['player1'],row['player2']],
                        'tour_id':str(row['tour_id']),'round_id':str(row['round_id']),'category':row['official_category'],'surface':row['surface'],
                        'tournament':row['tour_name'],'features':x,'probability':p,'quote':q,'quote_hashes':qhash,
                        'selection':selection,'history':evidence,'input_contract':INPUT_CONTRACT,'actual_stake':0}
                path.parent.mkdir(exist_ok=True)
                with path.open('x',encoding='utf8') as f:json.dump(packet,f,sort_keys=True,allow_nan=False)
                counts['captured']+=1;counts['selected']+=int(selection is not None)
        status={'state':'CAPTURED' if counts['captured'] else 'WAITING_FOR_FRESH_ELIGIBLE_FORECAST','checked_at':datetime.now(timezone.utc).isoformat(),'counts':dict(counts),'actual_stake':0}
        atomic(folder/'capture-status.json',status);return status

def summarize(root,folder=None,now=None):
    folder=folder or root/RELATIVE;now=now or datetime.now(timezone.utc)
    records=[read(p) for p in sorted((folder/'captures').glob('*.json'))];wanted={(r['tour_id'],r['round_id'],*sorted(r['players'])) for r in records}
    games=defaultdict(list)
    if wanted:
        for g in rows(root/'data/oncourt/games_atp.csv'):
            key=(g['tour_id'],g['round_id'],*sorted([g['winner_id'],g['loser_id']]))
            if key in wanted:games[key].append(g)
    outcomes={};bets=[];paired=[];excluded=Counter()
    for r in records:
        registered,kickoff=utc(r.get('registered_at')),utc(r['quote']['kickoff_iso'])
        valid=registered and kickoff and registered<kickoff and r.get('model_hash')==MODEL_HASH and r.get('actual_stake')==0
        if not valid:excluded['invalid_capture']+=1;continue
        status='pending';result={}
        if kickoff<=now:
            found=[g for g in games[(r['tour_id'],r['round_id'],*sorted(r['players']))] if g['date'][:10]<=now.date().isoformat() and abs((date.fromisoformat(g['date'][:10])-kickoff.date()).days)<=1]
            if len(found)==1:
                g=found[0];score=g['result'].upper();sets=[(int(a),int(b)) for a,b in re.findall(r'(\d+)-(\d+)',re.sub(r'\([^)]*\)','',score))]
                required=3 if r['category']=='Grand Slam' else 2
                if re.search(r'RET|W/O|WALK|ABD|DEF|BYE',score):status='void'
                elif sum(a>b for a,b in sets)==required and sum(b>a for a,b in sets)<required:status='settled'
                else:excluded['incomplete_result']+=1
                result={'winner_id':g['winner_id'],'score':score,'date':g['date'][:10]}
            elif len(found)>1:excluded['ambiguous_result']+=1
        outcomes[r['fixture_key']]={'status':status,**result}
        if status=='settled':paired.append((r,int(result['winner_id']==r['players'][0])))
        s=r['selection']
        if s:
            won=status=='settled' and r['players'][s['side']]==result['winner_id']
            bets.append({'fixture_key':r['fixture_key'],'player':r['names'][s['side']],'opponent':r['names'][1-s['side']],
                         'tournament':r['tournament'],'kickoff':r['quote']['kickoff_iso'],'registered_at':r['registered_at'],'quote_captured_at':r['quote'].get('captured_at'),
                         'status':status,'won':won if status=='settled' else None,'odds':s['odds'],'probability':s['probability'],
                         'ev_pct':s['ev_pct'],'stake_units':1.,'pnl_units':(s['odds']-1 if won else -1) if status=='settled' else 0.,'result':result})
    settled=[b for b in bets if b['status']=='settled'];pending=[b for b in bets if b['status']=='pending'];profit=sum(b['pnl_units'] for b in settled)
    scores={}
    for arm in ('model','market'):
        vals=[(r['probability'] if arm=='model' else r['quote']['market_p1'],y) for r,y in paired]
        scores[arm]={'n':len(vals),'brier':sum((p-y)**2 for p,y in vals)/len(vals) if vals else None,
                     'log_loss':sum(-y*math.log(p)-(1-y)*math.log(1-p) for p,y in vals)/len(vals) if vals else None}
    report={'name':'Astrissimo','version':MODEL['version'],'generated_at':now.isoformat(),'scope':MODEL['scope'],
            'status':'PAPER_ONLY','capture':read(folder/'capture-status.json'),'registered':len(records),'independent_fixtures':len(records),
            'settled_fixtures':len(paired),'settled':len(settled),'wins':sum(b['won'] for b in settled),'losses':sum(not b['won'] for b in settled),
            'pending':len(pending),'void':sum(b['status']=='void' for b in bets),'stake_units':len(settled),'pnl_units':round(profit,6),
            'roi_pct':100*profit/len(settled) if settled else None,'actual_stake':0,'clv_rows':0,
            'overdue':sum(now-utc(b['kickoff'])>timedelta(hours=48) for b in pending),'recent_pending':sum(now-utc(b['kickoff'])<=timedelta(hours=48) for b in pending),
            'as_of_date':max([b['result']['date'] for b in settled],default=None),'latest_signal_date':max([b['registered_at'] for b in bets],default=None),
            'paired_scores':scores,'exclusions':dict(excluded),'review_milestones_reached':[n for n in (50,100) if len(paired)>=n],
            'selections':sorted(bets,key=lambda b:b['kickoff'],reverse=True)[:100],
            'historical':{'settled':24,'wins':17,'losses':7,'profit_units':12.348,'roi_pct':51.45,'period':'2025 to 8 October 2026',
                          'scope':'ATP subset inspected after the research results; mixed historical price snapshots, not closing prices',
                          'included_in_forward_record':False},'model_hash':MODEL_HASH}
    atomic(folder/'outcomes.json',outcomes);atomic(folder/'report.json',report);return report

def record_text(report):
    if not report['settled']:return f"No settled paper bets yet | {report['pending']} pending | {report['void']} void. ROI starts after settlement."
    return f"{report['wins']}W / {report['losses']}L | {report['pending']} pending | {report['void']} void\n{report['pnl_units']:+.2f}u on {report['stake_units']}u | ROI {report['roi_pct']:+.2f}%"

def alerts(root,sender,*,print_only=False,include_daily=True,now=None):
    now=now or datetime.now(timezone.utc);folder=root/RELATIVE
    with locked(folder):
        report=summarize(root,now=now);state=read(folder/'telegram-state.json');sent=state.setdefault('sent',{})
        candidates=[]
        for b in report['selections']:
            quote_time=utc(b.get('quote_captured_at'))
            if b['fixture_key'] in sent or b['status']!='pending' or not utc(b['kickoff'])>now or not quote_time or not timedelta(0)<=now-quote_time<=timedelta(hours=2):continue
            text=f"ASTRISSIMO v1 | PAPER SELECTION\n{b['player']} to beat {b['opponent']}\n{b['tournament']} | {b['kickoff']}\nPinnacle {b['odds']:.3f} | model {100*b['probability']:.1f}% | fair {1/b['probability']:.3f}\nPrice recorded {b['quote_captured_at']}\nEstimated edge {b['ev_pct']:.1f}% | 1u paper, zero real stake\n\nFull forward record:\n{record_text(report)}\nATP main draw only. Challenger excluded.\nMonitor on your PC: http://localhost:3000/model-monitor/tennis#astrissimo"
            candidates.append((b['fixture_key'],text))
        from zoneinfo import ZoneInfo
        day=now.astimezone(ZoneInfo('Europe/London')).date().isoformat()
        if include_daily and state.get('daily_date')!=day:
            text=f"ASTRISSIMO v1 | DAILY PAPER TRACKER\n{record_text(report)}\n{report['registered']} forecasts captured before play; {report['settled_fixtures']} matches settled.\nCapture: {report['capture'].get('state','NOT_RUN')}\nATP main draw only, across surfaces. Challenger excluded. Fixed model; no automatic calibration or real stakes.\nHistorical backtest is separate from this new record.\nReview at 50 and 100 settled matches.\nMonitor on your PC: http://localhost:3000/model-monitor/tennis#astrissimo"
            candidates.append(('daily:'+day,text))
        for milestone in report['review_milestones_reached']:
            key='milestone:'+str(milestone)
            if key not in sent:candidates.append((key,f"ASTRISSIMO REVIEW: {milestone} independent matches settled.\n{record_text(report)}\nReview paired probability accuracy and price coverage before any promotion. Actual stake remains zero."))
        for key,text in candidates:
            if print_only:print(text);continue
            sender([text])
            if key.startswith('daily:'):state['daily_date']=day
            else:sent[key]={'accepted_at':now.isoformat(),'sha256':sha256(text.encode()).hexdigest()}
            state['last_relay_accepted_at']=now.isoformat();atomic(folder/'telegram-state.json',state)
        return {'messages':len(candidates),'preview':print_only}

def capture_current(root,production_rows):
    folder=root/RELATIVE;folder.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',dir=folder,encoding='utf8',delete=False) as f:
        json.dump({'generated_at':datetime.now(timezone.utc).isoformat(),'rows':production_rows},f);path=Path(f.name)
    try:
        run=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--root',str(root),'--input',str(path)],capture_output=True,text=True,timeout=120)
        if run.returncode:raise RuntimeError(run.stderr[-400:])
        return run.stdout.strip()
    except Exception as exc:
        atomic(folder/'capture-status.json',{'state':'BLOCKED','checked_at':datetime.now(timezone.utc).isoformat(),'reason':str(exc),'actual_stake':0})
        return 'BLOCKED: see astrissimo-v1/capture-status.json'
    finally:path.unlink(missing_ok=True)

def current_fixture_rows(root):
    """Fresh fixture metadata from today's OnCourt export, never an old forecast."""
    from tennis_tournament_category import resolve_category
    source=root/'data/oncourt';path=source/'today_atp.csv';now=datetime.now(timezone.utc)
    if not -60<=now.timestamp()-path.stat().st_mtime<=48*3600:raise ValueError('current fixture export stale')
    players={r['id']:r for r in rows(source/'players_atp.csv')};tours={r['id']:r for r in rows(source/'tours_atp.csv')}
    courts=court_surfaces(source/'courts.csv',combine_hard=True);result=[];seen=set()
    for g in rows(path):
        if g['player1_id']==g['player2_id']:continue
        if g.get('result','').strip() or str(g.get('complete','')).strip() not in ('','0') or str(g.get('live','')).strip() not in ('','0'):continue
        if any(g[k] not in players for k in ('player1_id','player2_id')):continue
        p1,p2=players[g['player1_id']],players[g['player2_id']]
        if '/' in p1['name']+p2['name']:continue
        tour=tours.get(g['tour_id'],{});category=resolve_category(tour.get('name'),tour.get('date'),tour.get('rank'),g['round_id'])
        key=(g['tour_id'],g['round_id'],*sorted([g['player1_id'],g['player2_id']]))
        if key in seen:raise ValueError('ambiguous current fixture')
        seen.add(key)
        result.append({**g,'player1':p1['name'],'player2':p2['name'],'tour_name':tour.get('name'),
                       'surface':courts.get(tour.get('court_id')),'official_category':category['official_category'],
                       'event_key':category.get('event_key'),'model_policy':'category_corrected','source_contract':INPUT_CONTRACT})
    return result

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--input',type=Path)
    ap.add_argument('--forecast-current',action='store_true');args=ap.parse_args()
    if args.forecast_current:print(json.dumps(capture(args.root,current_fixture_rows(args.root))))
    if args.input:
        packet=read(args.input);now=datetime.now(timezone.utc);stamp=utc(packet.get('generated_at'))
        if not stamp or not timedelta(0)<=now-stamp<=timedelta(minutes=5):raise ValueError('stale forecast packet')
        print(json.dumps(capture(args.root,packet['rows'],now=now)))
    result=summarize(args.root);print(json.dumps({k:v for k,v in result.items() if k not in ('selections','historical')}))
