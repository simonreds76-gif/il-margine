#!/usr/bin/env python3
"""Temporal, fixture-weighted calibration audit; never mutates live model parameters."""
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, math, sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from football_counts import prob_over, fit_dispersion_alpha_mle
from football_market import shading_aware_devig

COUNT_CUTOFF=date(2026,4,1)
CALIBRATION_END=date(2026,5,9)
FORWARD_START=date(2026,8,1)

def module(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/filename)
    obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj);return obj

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def dt(s):return datetime.fromisoformat(str(s).replace('Z','+00:00'))
def clip(p):return np.clip(p,1e-6,1-1e-6)

def earliest_markets(rows, pub, kind):
    snapshots={}
    for r in rows:
        try:
            captured=dt(r['captured_at']); kickoff=dt(r.get('kickoff_at') or r.get('kickoff_iso'))
            line=float(r['line']);odds=float(r['odds_decimal'])
        except (KeyError,TypeError,ValueError):continue
        if captured>=kickoff or odds<=1 or line%1!=0.5:continue
        if kind=='shots' and r.get('market')!='TEAM_SHOTS':continue
        league=pub.league_slug(r.get('competition') or r.get('league'))
        home=pub.team_key(r['home_team']);away=pub.team_key(r['away_team'])
        fixture='|'.join([kickoff.date().isoformat(),league,home,away])
        team=pub.team_key(r.get('team','')) if kind=='shots' else ''
        bookmaker=r.get('bookmaker','')
        k=(fixture,team,line,captured,bookmaker)
        row=snapshots.setdefault(k,dict(fixture=fixture,team=team,line=line,captured=captured.isoformat(),
            kickoff=kickoff.isoformat(),date=kickoff.date().isoformat(),league=league,home=home,away=away,bookmaker=bookmaker))
        row[r['side']]=odds
    # Evaluate only the first captured market board per fixture. Later prices
    # cannot be selected retrospectively because they happened to be better.
    paired=[r for r in snapshots.values() if 'over' in r and 'under' in r]
    first={}
    for r in paired:first[r['fixture']]=min(first.get(r['fixture'],r['captured']),r['captured'])
    return [r for r in paired if r['captured']==first[r['fixture']]]

def fit_calibrator(rows,bias=False):
    raw=clip(np.array([r['raw'] for r in rows]));market=clip(np.array([r['market'] for r in rows]));y=np.array([r['y'] for r in rows])
    counts=Counter(r['fixture'] for r in rows); weights=np.array([1/counts[r['fixture']] for r in rows]);weights/=weights.sum()
    def objective(theta):
        p=clip(expit(logit(market)+theta[0]*(logit(raw)-logit(market))+(theta[1] if bias else 0)))
        penalty=5*theta[1]**2/len(counts) if bias else 0
        return float(-np.sum(weights*(y*np.log(p)+(1-y)*np.log(1-p)))+penalty)
    result=minimize(objective,[0.2,0.0] if bias else [0.2],method='L-BFGS-B',bounds=[(0,1),(-1,1)] if bias else [(0,1)])
    if not result.success:raise RuntimeError(result.message)
    return {'weight':float(result.x[0]),'intercept':float(result.x[1]) if bias else 0}

def predict(r,cal):return float(expit(logit(clip(r['market']))+cal['weight']*(logit(clip(r['raw']))-logit(clip(r['market'])))+cal['intercept']))

def evaluate(rows,probability,raw_cap=False):
    if not rows:return {'rows':0,'fixtures':0,'bets':0,'roi':None}
    counts=Counter(r['fixture'] for r in rows); metrics=defaultdict(float);candidates={}
    for r in rows:
        p=float(clip(probability(r))); y=r['y'];weight=1/counts[r['fixture']]
        metrics['brier']+=weight*(p-y)**2
        metrics['log_loss']+=weight*(-math.log(p if y else 1-p))
        metrics['calibration_bias']+=weight*(p-y)
        for side,prob,odds in [('over',p,r['over']),('under',1-p,r['under'])]:
            edge=prob*odds-1
            if edge<0.03:continue
            if raw_cap and 4<=r['matchday']<=6 and abs(r['raw']-r['shaded_market'])>0.12:continue
            pick=dict(r,side=side,p=prob,edge=edge,odds=odds,
                      pnl=odds-1 if bool(y)==(side=='over') else -1)
            if r['fixture'] not in candidates or edge>candidates[r['fixture']]['edge']:candidates[r['fixture']]=pick
    picks=list(candidates.values());n=len(picks);pnl=sum(r['pnl'] for r in picks)
    for k in metrics:metrics[k]/=len(counts)
    return dict(rows=len(rows),fixtures=len(counts),**metrics,bets=n,wins=sum(r['pnl']>0 for r in picks),
                pnl=pnl,roi=pnl/n if n else None,overs=sum(r['side']=='over' for r in picks),picks=picks)

def build_observations(out):
    pub=module('calibration_pub','publish-football-research-picks.py')
    shots=module('calibration_shots','team-shots-v4-folds.py')
    corners=module('calibration_corners','corners-v3-folds.py')
    # Rebuild causal rolling features from the current durable base. This does
    # not overwrite the registered historical input or its lock.
    base=read_csv(pub.DEFAULT_TEAM_BASE)
    numeric=set(base[0])-{'date','league','season','team','team_key','opponent','opponent_key','venue','home_team','away_team','match_source','xg_source'}
    for r in base:
        for k in numeric:r[k]=float(r[k]) if r[k] else None
    print('Rebuilding causal form:',len(base),'team rows',flush=True)
    form=pub.FORM_BUILD.build_rolling_rows(base)
    for r in form:
        for k,v in list(r.items()):r[k]='' if v is None else str(v)
    served=shots.build_predictions(form,use_market=False)
    team_index={(r.match_date.isoformat(),r.league,pub.team_key(r.team)):r for r in served}
    training=[r for r in served if r.match_date<COUNT_CUTOFF]
    print('Fitting shots dispersion on',len(training),'pre-April count rows',flush=True)
    league_alpha,team_alpha=shots.fitted_alphas(training)
    fallback=fit_dispersion_alpha_mle([(r.actual,r.lam) for r in training],min_sample=30)
    md={};season_counts=Counter()
    for r in sorted(base,key=lambda r:r['date']):
        k=(r['league'],r['season'],pub.team_key(r['team']))
        md[(r['date'],r['league'],pub.team_key(r['team']))]=season_counts[k]+1;season_counts[k]+=1
    result={'shots':[],'corners':[]}
    for r in earliest_markets(read_csv(shots.DEFAULT_ODDS),pub,'shots'):
        prediction=team_index.get((r['date'],r['league'],r['team']))
        if prediction is None or prediction.match_date<COUNT_CUTOFF:continue
        alpha=team_alpha.get((prediction.league,prediction.team_key),league_alpha.get(prediction.league,fallback))
        raw=prob_over(r['line'],prediction.lam,distribution='negative_binomial',alpha=alpha)
        m=(1/r['over'])/(1/r['over']+1/r['under'])
        shaded=shading_aware_devig(r['over'],r['under'],over_vig_share=.856)[0]
        result['shots'].append(dict(r,raw=raw,market=m,shaded_market=shaded,y=int(prediction.actual>r['line']),
            actual=prediction.actual,mean=prediction.lam,matchday=min(md.get((r['date'],r['league'],t),99) for t in [r['home'],r['away']])))
    # The baseline is unused by the fitted v3 model; supply its positive league
    # reference to satisfy sample eligibility without recomputing v0.
    baselines={corners.fixture_key(r['date'],r['home_team'],r['away_team']):9.8 for r in form}
    samples,coverage=corners.build_samples(form,read_csv(corners.DEFAULT_EVENTS),baselines)
    train=[s for s in samples if s.match_date<COUNT_CUTOFF]
    print('Fitting corners on',len(train),'pre-April fixtures',flush=True)
    fitted=corners.fit_model(train)
    index={(s.match_date.isoformat(),s.league,pub.team_key(s.home_team),pub.team_key(s.away_team)):s for s in samples}
    for r in earliest_markets(read_csv(ROOT/'data/corners-ou/pinnacle-corners-odds.csv'),pub,'corners'):
        sample=index.get((r['date'],r['league'],r['home'],r['away']))
        if sample is None or sample.match_date<COUNT_CUTOFF:continue
        mu=fitted.predict(sample);raw=prob_over(r['line'],mu,distribution='negative_binomial',alpha=fitted.alpha)
        m=(1/r['over'])/(1/r['over']+1/r['under'])
        result['corners'].append(dict(r,raw=raw,market=m,shaded_market=m,y=int(sample.actual>r['line']),actual=sample.actual,mean=mu,
            matchday=min(md.get((r['date'],r['league'],t),99) for t in [r['home'],r['away']])))
    for rows in result.values():rows.sort(key=lambda r:(r['date'],r['fixture'],r.get('team',''),r['line']))
    (out/'observations.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--reuse-observations',action='store_true');args=ap.parse_args()
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    observations=json.loads((out/'observations.json').read_text()) if args.reuse_observations else build_observations(out)
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'count_training_before':str(COUNT_CUTOFF),
            'calibration_before':str(CALIBRATION_END),'forward_from':str(FORWARD_START),'models':{}}
    report['input_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [ROOT/'data/football-form/team-match-base.csv',
                     ROOT/'data/team-shots/team-shots-odds-history.csv',
                     ROOT/'data/corners-ou/pinnacle-corners-odds.csv',
                     ROOT/'data/team-shots/understat/corner-event-features.csv']}
    for kind,rows in observations.items():
        train=[r for r in rows if r['date']<str(CALIBRATION_END)]
        if len(train)<40:raise RuntimeError(f'{kind}: insufficient calibration sample ({len(train)})')
        calibrators={name:fit_calibrator(train,bias=(name=='blend_bias')) for name in ['blend','blend_bias']}
        variants={'raw':lambda r:r['raw'],'market':lambda r:r['market']}
        if kind=='shots':variants['legacy']=lambda r:float(expit(.18*logit(clip(r['raw']))+.82*logit(clip(r['shaded_market']))))
        else:variants['legacy']=variants['raw']
        for name,cal in calibrators.items():variants[name]=lambda r,c=cal:predict(r,c)
        models={'calibrators':calibrators,'phases':{}}
        for phase,subset in [('calibration',train),('validation',[r for r in rows if str(CALIBRATION_END)<=r['date']<str(FORWARD_START)]),
                             ('forward',[r for r in rows if r['date']>=str(FORWARD_START)])]:
            models['phases'][phase]={name:evaluate(subset,fn,raw_cap=(kind=='shots' and name=='legacy')) for name,fn in variants.items()}
            print(kind,phase,json.dumps({name:{k:v for k,v in stats.items() if k!='picks'} for name,stats in models['phases'][phase].items()}),flush=True)
        report['models'][kind]=models
    (out/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Saved',out/'audit.json',flush=True)

if __name__=='__main__':main()
