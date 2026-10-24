"""Ace Compass v1: immutable paired ATP aces paper evidence; no live pricing writes."""
from __future__ import annotations
import argparse, hashlib, json, math, os, pickle
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone, date
from pathlib import Path
import ace_compass_engine as E

ROOT=Path(__file__).resolve().parents[1]
REL=Path('data/tennis-props/shadow/ace-compass-v1')
CONFIG=dict(id='ace-compass-v1',name='Ace Compass',markets=['aces'],tour='ATP',paper_stake=1,real_stake=0,
            threshold=.08,alpha=E.ALPHA,scale=E.SCALE,beta=E.BETA,history_days=730,embargo_days=2,
            opponent_prior=500,review_fixtures=[50,100],selection='OVER half-point lines only; first verified price per native fixture/player/bookmaker/line',
            scope='ATP and Challenger, qualifying and main draws, all supported surfaces; separate strata',
            historical=dict(bets=19,wins=10,losses=9,profit=2.05,roi_pct=10.7894736842),automatic_promotion=False)

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n') if p.suffix=='.py' else p.read_bytes()).hexdigest()
def readj(p,default):return json.loads(p.read_text(encoding='utf8')) if p.exists() else default
def stamp(s):
    try:
        d=datetime.fromisoformat(str(s).replace('Z','+00:00'))
        return d if d.tzinfo else None
    except ValueError:return None
def atomic(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix(p.suffix+'.tmp')
    with q.open('w',encoding='utf8') as h:json.dump(obj,h,indent=2,allow_nan=False);h.flush();os.fsync(h.fileno())
    os.replace(q,p)
@contextmanager
def lock(folder):
    folder.mkdir(parents=True,exist_ok=True);p=folder/'.writer.lock';fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:os.write(fd,str(os.getpid()).encode());yield
    finally:os.close(fd);p.unlink()
def ledger(path):
    rows=[];previous=''
    for line in path.read_text().splitlines() if path.exists() else []:
        r=json.loads(line);own=r.pop('hash')
        if r.get('previous_hash')!=previous or digest(r)!=own:raise ValueError('ledger_integrity_failure')
        r['hash']=own;rows.append(r);previous=own
    return rows
def append(path,rows,r):
    r['previous_hash']=rows[-1]['hash'] if rows else '';r['hash']=digest(r)
    with path.open('a',encoding='utf8') as f:f.write(json.dumps(r,sort_keys=True,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    rows.append(r)
def fingerprint(code):return {n:sha(code/'scripts'/n) for n in ('tennis_ace_compass.py','ace_compass_engine.py','ace_compass_integrity.py')}
def source_manifest(root,now):
    paths=[root/'data/oncourt'/f'{k}_atp.csv' for k in ('players','games','stat','tours')]
    for p in paths:
        if not p.exists():raise ValueError('source_missing:'+p.name)
        age=now.timestamp()-p.stat().st_mtime
        if age < -60 or age>36*3600:raise ValueError('source_stale:'+p.name)
    return {p.name:dict(size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,sha256=sha(p)) for p in paths}
def identity(b):return ':'.join([str(b['tour_id']),str(b['round']),*sorted([str(b['player_id']),str(b['opponent_id'])])])
def eligible(row,now):
    if row.get('tour')!='ATP' or row.get('market')!='aces':return 'out_of_scope'
    try:line=float(row['line']);odds=float(row['over_odds'])
    except (ValueError,KeyError):return 'invalid_price'
    if not math.isfinite(line+odds) or line<0 or line%1!=.5 or odds<=1:return 'unsupported_contract'
    cap,start=stamp(row.get('capture_ts')),stamp(row.get('match_start_utc'))
    if not cap or not start or not cap<=now<start:return 'not_verified_prematch'
    if (now-cap).total_seconds()>6*3600:return 'stale_price'
    if row.get('matched_board')!='yes' or row.get('match_source')!='exact':return 'ambiguous_board_match'
    if not row.get('bookmaker'):return 'missing_bookmaker'
    return None
def join_board(row,board):
    matched=[b for b in board if b.get('tour')=='ATP' and b.get('date')==row.get('date') and E.norm(b.get('player'))==E.norm(row.get('player')) and E.norm(b.get('opponent'))==E.norm(row.get('opponent')) and E.norm(b.get('tournament'))==E.norm(row.get('tournament'))]
    return matched[0] if len(matched)==1 else None
def capture(root,code,folder,rows,comparison,now,registration):
    health=Counter();quotes=E.read(comparison) if comparison and comparison.exists() else []
    board=E.read(root/'data/tennis-props/player-props-board.csv');pending=[];seen={r['id'] for r in rows}
    for q in sorted(quotes,key=lambda r:r.get('capture_ts','')):
        reason=eligible(q,now)
        if reason:health[reason]+=1;continue
        b=join_board(q,board)
        if not b or b.get('generation_date')!=now.date().isoformat():health['board_missing_or_stale']+=1;continue
        if not all(b.get(k) for k in ('tour_id','round','player_id','opponent_id')):health['native_identity_missing']+=1;continue
        fk=identity(b);rid=digest([fk,b['player_id'],E.norm(q['bookmaker']),float(q['line'])])
        if rid in seen:health['already_registered']+=1;continue
        pending.append((q,b,fk,rid));seen.add(rid)
    if not pending:
        return dict(state='NO_NEW_ELIGIBLE_QUOTES',checked_at=now.isoformat(),comparison=str(comparison) if comparison else None,reasons=dict(health),added=0)
    manifest=source_manifest(root,now);cachekey=digest([now.date().isoformat(),manifest,registration['implementation']])
    cache=folder/'cache';cache.mkdir(exist_ok=True);meta=readj(cache/'metadata.json',{})
    if meta.get('key')==cachekey and (cache/'state.pkl').exists() and sha(cache/'state.pkl')==meta.get('sha256'):
        # Locally generated cache only; hash verified, never loads external pickle files.
        with (cache/'state.pkl').open('rb') as h:state,tours,audit=pickle.load(h)
    else:
        hist,tours,audit=E.history(root/'data/oncourt',now.date());state=E.build_state(hist,now.date(),excluded=[tid for tid,t in tours.items() if not E.event_condition_eligible(t['name'])])
        temp=cache/'state.tmp'
        with temp.open('wb') as h:pickle.dump((state,tours,audit),h)
        os.replace(temp,cache/'state.pkl')
        atomic(cache/'metadata.json',dict(key=cachekey,sha256=sha(cache/'state.pkl')))
    predictions=[]
    for q,b,fk,rid in pending:
        t=tours.get(b['tour_id']);phase=E.event_phase(b['round'])
        if not t or phase is None:health['unsupported_event_or_round']+=1;continue
        bo=E.match_best_of('ATP',t['name'],b['round'],slam=t['rank']=='4')
        if bo is None:health['unsupported_format']+=1;continue
        sf=E.SURF[t['court_id']]
        f=state.feature(b['player_id'],b['opponent_id'],sf,b['tour_id'],t['rank'],bo)
        if f['event_latest']>now.date().toordinal()-2:raise ValueError('future_event_input')
        p=E.predict(f,float(q['line']),float(q['over_odds']))
        stratum=('Challenger' if t['rank']=='1' else 'ATP')+' '+phase.replace('_',' ')
        predictions.append(dict(id=rid,fixture_key=fk,player_key=fk+':'+b['player_id'],registered_at=now.isoformat(),row=q,
            native=dict(tid=b['tour_id'],round=b['round'],pid=b['player_id'],opp=b['opponent_id']),surface=sf,stratum=stratum,
            features={k:float(v) for k,v in f.items()},input_hash=cachekey,**p))
    if source_manifest(root,datetime.now(timezone.utc))!=manifest:raise ValueError('source_changed_during_capture')
    atomic(folder/'inputs'/f'{cachekey}.json',dict(manifest=manifest,cutoff=now.date().isoformat(),audit=audit,implementation=registration['implementation']))
    for r in predictions:
        if stamp(r['row']['match_start_utc'])<=datetime.now(timezone.utc):health['started_during_build']+=1;continue
        append(folder/'observations.jsonl',rows,r);health['captured']+=1
    return dict(state='CAPTURED' if health['captured'] else 'NO_NEW_ELIGIBLE_QUOTES',checked_at=now.isoformat(),reasons=dict(health),added=health['captured'])

def settle(root,rows,outcomes,now):
    pending=[r for r in rows if r['id'] not in outcomes and stamp(r['row']['match_start_utc'])<now]
    if not pending:return
    tids={r['native']['tid'] for r in pending};games=defaultdict(list);stats=defaultdict(list)
    for g in E.read(root/'data/oncourt/games_atp.csv'):
        if g['tour_id'] in tids:games[(g['tour_id'],g['round_id'],tuple(sorted([g['winner_id'],g['loser_id']])))].append(g)
    for s in E.read(root/'data/oncourt/stat_atp.csv'):
        if s['tour_id'] in tids:stats[E.key(s)].append(s)
    for r in pending:
        n=r['native'];c=games.get((n['tid'],n['round'],tuple(sorted([n['pid'],n['opp']]))),[])
        unique={digest(g):g for g in c}
        if len(unique)!=1:continue
        g=next(iter(unique.values()))
        if not r['registered_at'][:10]<=g['date']<=now.date().isoformat():continue
        text=g.get('result','').upper()
        if any(v in text for v in ('RET','W/O','DEF','ABN')):out=dict(status='void',actual=None)
        else:
            ss={digest(s):s for s in stats.get(E.key(g),[])}
            if len(ss)!=1:continue
            s=next(iter(ss.values()));a,error=E.adapt(g,s)
            if error:continue
            prefix='w' if n['pid']==g['winner_id'] else 'l';out=dict(status='settled',actual=int(s[prefix+'_ace']))
        outcomes[r['id']]=dict(out,settled_at=now.isoformat(),result_date=g['date'],source='exact OnCourt IDs, edition and round',source_hash=digest([g,ss if out['status']=='settled' else {}]))

def summarize(rows,outcomes,registration,capture,now):
    result=dict(model='Ace Compass v1',status='PAPER ONLY',generated_at=now.isoformat(),registered_at=registration['registered_at'],capture=capture,registered_quotes=len(rows),automatic_promotion=False,historical=CONFIG['historical'])
    selections=[];arms={}
    for arm in ('control','candidate'):
        chosen=[r for r in rows if r[arm]['selected']];t=Counter();pnl=0.;prob=[]
        for r in rows:
            out=outcomes.get(r['id'],{});actual=out.get('actual')
            if out.get('status')=='settled':
                y=int(actual>float(r['row']['line']));p=min(1-1e-12,max(1e-12,r[arm]['p_win']));prob.append(((p-y)**2,-(y*math.log(p)+(1-y)*math.log1p(-p))))
            if not r[arm]['selected']:continue
            status=out.get('status','pending');profit=None
            if status=='settled':
                won=actual>float(r['row']['line']);t['wins' if won else 'losses']+=1;profit=float(r['row']['over_odds'])-1 if won else -1;pnl+=profit
            else:t[status]+=1
            if status=='pending' and (now-stamp(r['row']['match_start_utc'])).total_seconds()>48*3600:t['overdue']+=1
            if arm=='candidate':selections.append(dict(id=r['id'],player=r['row']['player'],opponent=r['row']['opponent'],tournament=r['row']['tournament'],start=r['row']['match_start_utc'],line=float(r['row']['line']),odds=float(r['row']['over_odds']),bookmaker=r['row']['bookmaker'],fair=r[arm]['fair_odds'],ev=r[arm]['ev'],status='won' if status=='settled' and profit>0 else 'lost' if status=='settled' else status,actual=actual,profit=profit,captured_at=r['registered_at']))
        settled=t['wins']+t['losses'];arms[arm]=dict(bets=len(chosen),settled=settled,wins=t['wins'],losses=t['losses'],pending=t['pending'],void=t['void'],overdue=t['overdue'],stake_units=settled,pnl_units=pnl,roi_pct=100*pnl/settled if settled else None,brier=sum(v[0] for v in prob)/len(prob) if prob else None,log_loss=sum(v[1] for v in prob)/len(prob) if prob else None)
    # First player-match observation across bookmakers/lines; no ladder pseudoreplication.
    first={}
    for r in rows:first.setdefault(r['player_key'],r)
    groups=defaultdict(list)
    for r in first.values():
        if outcomes.get(r['id'],{}).get('status')=='settled':
            groups['All'].append(r);groups[r['stratum']].append(r)
    bias=[]
    for label,rs in groups.items():
        actual=sum(outcomes[r['id']]['actual'] for r in rs)
        bias.append(dict(group=label,player_matches=len(rs),fixtures=len({r['fixture_key'] for r in rs}),actual=actual,**{arm:dict(predicted=sum(r[arm]['mean'] for r in rs),bias_pct=100*(sum(r[arm]['mean'] for r in rs)/actual-1) if actual else None) for arm in arms}))
    result.update(arms=arms,bias=bias,selections=selections[-200:][::-1],selection_count=len(selections),independent_fixtures=len({r['fixture_key'] for r in first.values() if outcomes.get(r['id'],{}).get('status')=='settled'}),pending_quotes=sum(r['id'] not in outcomes for r in rows))
    result['review_due']=result['independent_fixtures']>=50
    result['next_review_at']=next((n for n in CONFIG['review_fixtures'] if n>result['independent_fixtures']),None)
    return result

def weekly_text(report):
    if not report:return 'Ace Compass [PAPER ONLY]: report unavailable'
    a=report.get('arms',{}).get('candidate',{});roi=a.get('roi_pct');bias=next((b for b in report.get('bias',[]) if b['group']=='All'),{})
    bp=bias.get('candidate',{}).get('bias_pct')
    return ('Ace Compass v1 [PAPER ONLY]\n'+f"{a.get('wins',0)}W/{a.get('losses',0)}L | {a.get('pnl_units',0):+.2f}u on {a.get('stake_units',0)}u | "+(f'ROI {roi:+.2f}%' if roi is not None else 'No settled bets yet')+f" | {a.get('pending',0)} pending, {a.get('void',0)} void, {a.get('overdue',0)} overdue.\n"+(f"Predicted ace total bias {bp:+.1f}% across {bias.get('player_matches',0)} player matches (negative = underprediction). " if bp is not None else 'Prediction bias awaits completed matches. ')+f"Capture: {report.get('capture',{}).get('state','unknown')}. Historical +10.79%/19 bets stays separate."+(' Manual review milestone reached.' if report.get('review_due') else ''))

def run(root,code,comparison=None,settle_only=False):
    now=datetime.now(timezone.utc);folder=root/REL
    with lock(folder):
        reg=readj(folder/'registration.json',None);imp=fingerprint(code)
        if not reg:
            reg=dict(registered_at=now.isoformat(),config=CONFIG,implementation=imp);atomic(folder/'registration.json',reg)
        rows=ledger(folder/'observations.jsonl');outcomes=readj(folder/'outcomes.json',{})
        capture_status=readj(folder/'capture-status.json',dict(state='AWAITING_FIRST_RUN'))
        if not settle_only:
            try:
                if reg['implementation']!=imp or reg['config']!=CONFIG:raise ValueError('frozen_implementation_changed')
                capture_status=capture(root,code,folder,rows,comparison,now,reg)
            except Exception as exc:capture_status=dict(state='BLOCKED',checked_at=now.isoformat(),reason=str(exc),added=0)
            atomic(folder/'capture-status.json',capture_status)
        settle(root,rows,outcomes,now);atomic(folder/'outcomes.json',outcomes)
        report=summarize(rows,outcomes,reg,capture_status,now);atomic(folder/'report.json',report)
        print(weekly_text(report))
        return 1 if capture_status.get('state')=='BLOCKED' and not settle_only else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--code-root',type=Path,default=ROOT);p.add_argument('--comparison',type=Path);p.add_argument('--settle-only',action='store_true');a=p.parse_args()
    raise SystemExit(run(a.root,a.code_root,a.comparison,a.settle_only))
