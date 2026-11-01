"""Frozen ATP break-point chances paper tracking. Never writes live model tables.

Consumes existing quote evidence. No HTTP calls, odds downloads or alerts.
Predictions and the registration are immutable; outcomes come from the separate
exact-fixture evidence ledger and are explicitly research outcomes, not grading.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,os,sys
from pathlib import Path
from datetime import datetime,date,timedelta,timezone
from collections import Counter,defaultdict
import pandas as pd
import numpy as np
from scipy.stats import nbinom
from scipy.optimize import minimize
from tennis_breakpoint_model import Frozen,load_history,forecast,valid_row
from tennis_breakpoint_evidence import rows,append,atomic,digest,process_lock,norm,same_venue,read_csv,RELATIVE as EVIDENCE
from tennis_grosvenor import utc
from ace_compass_integrity import match_best_of,event_phase

RELATIVE=Path('data/tennis-break-points/forward-c-v1')
VERSION='bp-chances-c-v1-20261101'
FILES=('scripts/tennis_breakpoint_model.py','scripts/tennis_breakpoint_forward.py',
       'scripts/tennis_breakpoint_history_build.py','config/tennis-breakpoint-c-frozen.json',
       'config/tennis-breakpoint-forward-protocol.md','scripts/tennis_breakpoint_evidence.py',
       'scripts/tennis_grosvenor.py','scripts/ace_compass_integrity.py','scripts/tennis_event_integrity.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p,default=None):return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else ({} if default is None else default)
def now():return datetime.now(timezone.utc)
def fingerprints(code):return {p:sha(code/p) for p in FILES}
def event_pair(q):return (q['event_id'],*sorted((norm(q['home']),norm(q['away']))))

def strict_outcome(f,s):
    from types import SimpleNamespace
    import re
    v=s.get('validated_counts',{});sp=[tuple(map(int,x)) for x in re.findall(r'(\d+)-(\d+)',str(s.get('score','')))]
    if len(sp) not in (2,3):return False
    row={'score':s.get('score'),'tournament':s.get('native_tournament',f.get('tournament','')),'result_date':s.get('result_date',''),
         'phase':f.get('phase'),'status':'completed','best_of':f.get('best_of',3),'y':s.get('y')}
    try:
        gw=[sum(x[i] for x in sp) for i in (0,1)]
        tb=[sum({a,b}=={6,7} and ((a>b) if i==0 else b>a) for a,b in sp) for i in (0,1)]
        br=[v[p+'_bpfaced']-v[p+'_bpsaved'] for p in ('w','l')]
        sg=[gw[i]-tb[i]-br[1-i]+br[i] for i in (0,1)]
        if min(sg)<=0 or abs(sg[0]-sg[1])>1+sum(tb):return False
        for i,p in enumerate(('w','l')):
            q='l' if p=='w' else 'w'
            row.update({p+'_SvGms':sg[i],p+'_bpFaced':v[p+'_bpfaced'],p+'_bpSaved':v[p+'_bpsaved'],p+'_created':v[p+'_bpof'],p+'_converted':v[p+'_bpw']})
        return all(isinstance(x,(int,float)) and math.isfinite(x) and x>=0 and int(x)==x for x in v.values()) and valid_row(SimpleNamespace(**row))
    except (KeyError,ValueError,TypeError,AttributeError):return False

def refresh_history(root,out,code):
    from tennis_breakpoint_history_build import build
    native=root/'data/oncourt';source={x:sha(native/(x+'_atp.csv')) for x in ('games','stat','players','tours')}
    source['aliases']=sha(root/'data/tennis-props/player-name-aliases.csv')
    source.update({str(p.relative_to(root)):sha(p) for p in sorted((root/'data/sackmann').glob('atp_matches*202*.csv'))})
    state=load(out/'history-status.json')
    if state.get('inputs')==source and (out/'history.csv.gz').exists() and state.get('history_sha256')==sha(out/'history.csv.gz'):return state
    records,counts,excluded,raw_hashes=build(root,now().date().isoformat())
    if not records:raise ValueError('empty_history')
    # Preserve old snapshots; forecasts reference exact compressed bytes.
    import io
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    raw=gzip.compress(stream.getvalue().encode(),mtime=0);h=hashlib.sha256(raw).hexdigest()
    snapshots=out/'history';snapshots.mkdir(parents=True,exist_ok=True)
    if sum(p.stat().st_size for p in snapshots.glob('*.gz'))+len(raw)>256*1024*1024:raise ValueError('history_archive_capacity_requires_review')
    saved=snapshots/(h+'.csv.gz')
    if not saved.exists():saved.write_bytes(raw)
    temp=out/'history.tmp';temp.write_bytes(raw);temp.replace(out/'history.csv.gz')
    state={'generated_at':now().isoformat(),'inputs':source,'raw_hashes':raw_hashes,'history_sha256':h,'rows':len(records),
           'last_result':max(r['result_date'] for r in records),'counts':counts,'exclusions':dict(Counter(r['reason'] for r in excluded))}
    atomic(out/'history-status.json',state);return state

def identity_index(root):
    base=root/'data/oncourt';paths=[base/(x+'_atp.csv') for x in ('players','tours','today')]
    paths.append(root/'data/tennis-props/player-name-aliases.csv')
    hashes={str(p.relative_to(root)):sha(p) for p in paths}
    aliases={norm(r['alias']):norm(r['player_name']) for r in read_csv(paths[-1]) if r.get('tour','').upper()=='ATP'}
    names=defaultdict(list)
    for p in read_csv(paths[0]):names[aliases.get(norm(p['name']),norm(p['name']))].append(int(p['id']))
    tours={int(r['id']):r for r in read_csv(paths[1])}
    today=list(read_csv(paths[2]))
    if hashes!={str(p.relative_to(root)):sha(p) for p in paths}:raise ValueError('schedule_changed_during_read')
    return names,aliases,tours,today,hashes

def map_quote(q,index):
    names,aliases,tours,today,hashes=index
    ids=[names.get(aliases.get(norm(q[k]),norm(q[k])),[]) for k in ('home','away')]
    if not all(len(x)==1 for x in ids) or ids[0]==ids[1]:raise ValueError('UNMAPPED_PLAYER')
    p1,p2=ids[0][0],ids[1][0];day=utc(q['scheduled_start']).date().isoformat();found={}
    for r in today:
        if {int(r['player1_id']),int(r['player2_id'])}!={p1,p2} or r.get('date')!=day:continue
        t=tours.get(int(r['tour_id']),{})
        if not same_venue(q['group'],t.get('name','')):continue
        found[(r['tour_id'],r['round_id'])]=(r,t)
    if len(found)!=1:raise ValueError('UNMAPPED_EXACT_UPCOMING_FIXTURE')
    r,t=next(iter(found.values()));name=t['name'].lower()
    if t['rank'] not in ('2','3','4') or any(x in name for x in ('junior','itf','next gen','nextgen','laver','exhibition','wildcard','wild card','play-off','playoff','united cup','atp cup','davis','hopman','olympic','atp finals','masters cup','world tour finals')):raise ValueError('OUTSIDE_FROZEN_SCOPE')
    phase=event_phase(r['round_id']);bo=match_best_of('ATP',t['name'],r['round_id'])
    surface={'1':'Hard','2':'Clay','3':'Indoor hard','5':'Grass','6':'Hard'}.get(t['court_id'])
    if bo!=3 or phase not in ('main_draw','qualifying') or not surface:raise ValueError('UNSUPPORTED_FORMAT_OR_CONTEXT')
    return {'fixture_id':f"{r['tour_id']}:{r['round_id']}:{min(p1,p2)}:{max(p1,p2)}",'p1_id':p1,'p2_id':p2,
            'edition_id':r['tour_id'],'round_id':r['round_id'],'tournament':t['name'],'surface':surface,
            'level':'Slam' if t['rank']=='4' else 'Masters' if t['rank']=='3' else '250_500','phase':phase,'best_of':bo,'schedule_hashes':hashes}

def capture(root,out,code,clock=None):
    stamp=clock or now();reg=load(out/'registration.json');history=load(out/'history-status.json')
    if not reg:raise ValueError('not_activated')
    if reg['hashes']!=fingerprints(code):raise ValueError('frozen_code_or_parameters_changed')
    previous=rows(out/'forecasts.jsonl');seen={event_pair(r) for r in previous};seen_native={r['fixture_id'] for r in previous};bad=Counter();eligible=[]
    quotes=rows(root/EVIDENCE/'quotes.jsonl');groups=defaultdict(list);skipped=Counter()
    for q in quotes:
        if q['tour']!='ATP':continue
        cap=utc(q['capture_at']);start=utc(q['scheduled_start'])
        if cap<utc(reg['activated_at']):bad['PRE_ACTIVATION_QUOTE']+=1;continue
        if event_pair(q) in seen:continue
        if cap>stamp or (stamp-cap).total_seconds()>1800 or start<=stamp:bad['STALE_OR_STARTED']+=1;skipped[event_pair(q)]+=1;continue
        groups[event_pair(q)].append(q)
    if groups:
        if not history or history.get('history_sha256')!=sha(out/'history.csv.gz'):raise ValueError('missing_or_changed_history')
        index=identity_index(root)
        for eid,qq in groups.items():
            qq.sort(key=lambda q:(utc(q['capture_at']),abs((1/q['over'])/(1/q['over']+1/q['under'])-.5),q['line'],q['offer_id']))
            # A failed identity/history check can be retried only on a fresh capture.
            for q in qq:
                try:
                    if utc(history['generated_at'])>utc(q['capture_at']):raise ValueError('HISTORY_NOT_AVAILABLE_AT_QUOTE')
                    if (utc(q['capture_at']).date()-date.fromisoformat(history['last_result'])).days>7:raise ValueError('STALE_HISTORY')
                    mapped=map_quote(q,index)
                    if mapped['fixture_id'] in seen_native:break
                    seen_native.add(mapped['fixture_id'])
                    eligible.append({**q,**mapped,'fixture_id':mapped['fixture_id'],'capture_at':q['capture_at']});break
                except ValueError as e:bad[str(e)]+=1
    added=[]
    if eligible:
        H=load_history(out/'history.csv.gz');F=Frozen(code/'config/tennis-breakpoint-c-frozen.json')
        predictions=forecast(H,F,pd.DataFrame(eligible)).to_dict('records')
        by={(p['fixture_id'],p['capture_at']):p for p in predictions}
        for q in eligible:
            p=by[q['fixture_id'],q['capture_at']];written=now() if clock is None else clock
            if not(math.isfinite(p['mu_C']) and p['mu_C']>0 and 0<p['p_over_C']<1 and p['tail_crosscheck_abs']<1e-10):bad['INVALID_PREDICTION']+=1;continue
            late=written>=utc(q['scheduled_start'])
            added.append({**q,**p,'quote_id':q['id'],'id':digest([VERSION,q['event_id'],q['fixture_id']]),'version':VERSION,
                          'forecasted_at':written.isoformat(),'cohort':'LATE' if late else 'FORWARD_PAPER',
                          'history_sha256':history['history_sha256'],'code_hashes':reg['hashes'],'earlier_stale_or_started_quotes':skipped[event_pair(q)],
                          'selected':bool(p['bet_C']) and not late,'paper_stake':1.0 if p['bet_C'] and not late else 0.0,'real_stake':0.0})
        append(out/'forecasts.jsonl',added)
    status={'checked_at':stamp.isoformat(),'new_forecasts':len(added),'forecasts':len(previous)+len(added),'exclusions':dict(bad),
            'status':'CAPTURING' if previous or added else 'AWAITING_FIRST_ELIGIBLE_ATP_QUOTE','paper_only':True,'telegram_enabled':False}
    atomic(out/'capture-status.json',status);return status

def summarize(out,evidence):
    forecasts=rows(out/'forecasts.jsonl');latest={r['quote_id']:r for r in rows(evidence/'results.jsonl')};settled=[];display=[];states=Counter()
    for f in forecasts:
        s=latest.get(f['quote_id'],{'status':'PENDING_RESULT'});status=s['status']
        if f['cohort']!='FORWARD_PAPER':status='LATE'
        # Frozen exact fixture includes both native IDs, edition and round.
        if status=='COMPLETED_RESEARCH_OUTCOME':
            parts=s.get('native_fixture','').split(':')
            if len(parts)!=4 or set(parts[:2])!={str(f['p1_id']),str(f['p2_id'])} or parts[2:]!=[str(f['edition_id']),str(f['round_id'])]:status='RESULT_IDENTITY_CONFLICT'
        if status=='COMPLETED_RESEARCH_OUTCOME' and not strict_outcome(f,s):status='INVALID_COMPLETED_OUTCOME'
        item={**f,'status':status,'actual_chances':s.get('y'),'result_observed_at':s.get('observed_at'),'profit':None}
        if status=='COMPLETED_RESEARCH_OUTCOME':
            item['over_hit']=int(s['y']>f['line']);item['profit']=f['over']*item['over_hit']-1 if f['selected'] else None;settled.append(item)
        states[status]+=1;display.append(item)
    bets=[r for r in settled if r['selected']];pending=[r for r in display if r['selected'] and r['status']=='PENDING_RESULT']
    n=len(settled);cal={}
    if n:
        y=np.array([r['over_hit'] for r in settled]);actual=np.array([r['actual_chances'] for r in settled]);mu=np.array([r['mu_C'] for r in settled]);alpha=settled[0]['alpha']
        for name,key in [('C','p_over_C'),('market','mkt_over')]:
            p=np.clip(np.array([r[key] for r in settled]),1e-12,1-1e-12);cal[name]={'brier':float(np.mean((p-y)**2)),'log_loss':float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p)))}
            cal[name]['calibration_fit']=None
            if n>=100 and min(sum(y),n-sum(y))>=20:
                x=np.log(p/(1-p));fit=minimize(lambda b:np.mean(np.logaddexp(0,b[0]+b[1]*x)-y*(b[0]+b[1]*x)),[0.,1.],method='BFGS')
                if fit.success and np.isfinite(fit.x).all():cal[name]['calibration_fit']={'intercept':float(fit.x[0]),'slope':float(fit.x[1]),'diagnostic_only':True}
        count_dist=nbinom(1/alpha,1/(1+alpha*mu));cal['count']={'mean_bias':float(np.mean(mu-actual)),'negative_log_score':float(np.mean(-count_dist.logpmf(actual))),
            'interval_coverage':{str(level):float(np.mean((actual>=count_dist.ppf((1-level)/2))&(actual<=count_dist.ppf((1+level)/2)))) for level in (.5,.8,.9)}}
        u=np.array([int(hashlib.sha256(r['id'].encode()).hexdigest()[:12],16)/16**12 for r in settled])
        pit=count_dist.cdf(actual-1)+u*count_dist.pmf(actual)
        cal['count']['randomized_pit_deciles']=np.histogram(pit,bins=np.linspace(0,1,11))[0].tolist()
        cal['count']['monthly_bias']={m:float(np.mean([r['mu_C']-r['actual_chances'] for r in settled if r['capture_at'][:7]==m])) for m in sorted({r['capture_at'][:7] for r in settled})}
        cal['paired_log_loss_difference_ci95']=None
        editions=sorted({r['edition_id'] for r in settled})
        if len(editions)>=8:
            buckets=[]
            for edition in editions:
                rr=[r for r in settled if r['edition_id']==edition]
                d=[-math.log(r['p_over_C'] if r['over_hit'] else 1-r['p_over_C'])+math.log(r['mkt_over'] if r['over_hit'] else 1-r['mkt_over']) for r in rr]
                buckets.append((sum(d),len(d)))
            buckets=np.array(buckets);rng=np.random.default_rng(20261101);draw=buckets[rng.integers(0,len(buckets),size=(2000,len(buckets)))].sum(axis=1)
            cal['paired_log_loss_difference_ci95']=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist()
    profit=sum(r['profit'] for r in bets);wins=sum(r['over_hit'] for r in bets);roi_ci=None
    bet_editions=sorted({r['edition_id'] for r in bets})
    if len(bet_editions)>=8:
        b=np.array([(sum(r['profit'] for r in bets if r['edition_id']==e),sum(r['edition_id']==e for r in bets)) for e in bet_editions])
        rng=np.random.default_rng(20261101);draw=b[rng.integers(0,len(b),size=(2000,len(b)))].sum(axis=1)
        roi_ci=np.quantile(100*draw[:,0]/draw[:,1],[.025,.975]).tolist()
    revisions=defaultdict(set)
    for s in rows(evidence/'results.jsonl'):
        if s['status']=='COMPLETED_RESEARCH_OUTCOME':revisions[s['quote_id']].add((s.get('native_fixture'),s.get('y')))
    excluded=Counter(r['status'] for r in display if r['selected'] and r['status'] not in ('COMPLETED_RESEARCH_OUTCOME','PENDING_RESULT'))
    report={'version':VERSION,'title':'Break Point C — paper','updated_at':now().isoformat(),'activation':load(out/'registration.json').get('activated_at'),
            'capture':load(out/'capture-status.json'),'history':load(out/'history-status.json'), 'forecast_count':len(forecasts),'settled_fixtures':n,
            'editions':len({r['edition_id'] for r in settled}),'statuses':dict(states),'bets':len(bets),'wins':wins,'losses':len(bets)-wins,'stake':float(len(bets)),
            'profit':profit,'roi_pct':100*profit/len(bets) if bets else None,'roi_ci95_pct':roi_ci,'pending_bets':len(pending),'calibration':cal,'records':display[-300:],
            'excluded_selected_bets':dict(excluded),'revised_results':sum(len(revisions[f['quote_id']])>1 for f in forecasts),'bias_definition':'predicted minus actual',
            'review_milestones':[20,100,300,600],'next_review':next((k for k in (20,100,300,600) if n<k),None),
            'note':'Frozen C; 1u hypothetical Over EV >=5%, zero real stake. Completed research outcomes; bookmaker grading unverified. No alerts. Historical replay remains separate.'}
    atomic(out/'report.json',report);return report

from tennis_breakpoint_reporting import weekly_text

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path);p.add_argument('--activate',action='store_true');p.add_argument('--refresh-history',action='store_true');p.add_argument('--settle-only',action='store_true')
    a=p.parse_args();code=Path(__file__).resolve().parents[1];out=a.output or a.root/RELATIVE
    with process_lock(out):
        if a.activate and not (out/'registration.json').exists():
            if not (out/'history.csv.gz').exists():refresh_history(a.root,out,code)
            atomic(out/'registration.json',{'version':VERSION,'activated_at':now().isoformat(),'hashes':fingerprints(code),'paper_only':True,'real_stake':0,'telegram_enabled':False})
        if (out/'registration.json').exists() and not a.settle_only:capture(a.root,out,code)
        if a.refresh_history:refresh_history(a.root,out,code)
        r=summarize(out,a.root/EVIDENCE);print(weekly_text(r))
if __name__=='__main__':main()
