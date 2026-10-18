"""One registered chronological ablation. Offline only; never called by daily jobs."""
import argparse
from collections import Counter
from itertools import groupby
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy.optimize import minimize
from aerial_data import read, save
from skyline_model import History, FEATURES, POLICY, height_gap, predict

TRAIN_END = '2026-02-28'
VALID_END = '2026-04-30'


def fit(rows, indices):
    x=np.array([[1]+[r['features']['x'][i] for i in indices] for r in rows]); y=np.array([r['y'] for r in rows])
    # Fixed weak ridge, intercept unpenalized. No hyperparameter/ROI search.
    def objective(w):
        z=x@w; p=1/(1+np.exp(-np.clip(z,-30,30)))
        return np.sum(np.logaddexp(0,z)-y*z)+.5*np.sum(w[1:]**2), x.T@(p-y)+np.r_[0,w[1:]]
    result=minimize(objective,np.r_[0,1,np.zeros(len(indices)-1)],jac=True,method='BFGS',options={'gtol':1e-5})
    if not np.isfinite(result.fun) or np.linalg.norm(result.jac)>0.02: raise ValueError('Fit failed')
    return dict(intercept=float(result.x[0]),weights=result.x[1:].tolist(),train_rows=len(rows))


def metrics(rows, variant, artifact):
    observations=[(r,predict(r['features'],artifact).get(variant)) for r in rows]
    observations=[(r,p) for r,p in observations if p is not None]
    if not observations:return {'n':0}
    y=np.array([r['y'] for r,p in observations]);p=np.clip([p for r,p in observations],1e-8,1-1e-8)
    bins=[]
    for low,high in [(0,.05),(.05,.1),(.1,.2),(.2,.3),(.3,.5),(.5,1.01)]:
        mask=(p>=low)&(p<high)
        if mask.any():bins.append(dict(range=[low,high],n=int(mask.sum()),predicted=float(p[mask].mean()),observed=float(y[mask].mean())))
    return dict(n=len(y),fixtures=len({r['fixture_id'] for r,_ in observations}),hits=int(y.sum()),
                log_loss=float(-(y*np.log(p)+(1-y)*np.log(1-p)).mean()),brier=float(((p-y)**2).mean()),
                mean_probability=float(p.mean()),hit_rate=float(y.mean()),calibration=bins,roi=None,
                roi_reason='No historical exact-market Bet365 prices in this replay.')


def main(root):
    raw=root/'data/aerial/history.json.gz';height_file=root/'data/aerial/heights.json.gz'
    history=read(raw)['matches'];heights=read(height_file,{})
    state=History();rows=[];excluded=Counter()
    for day,items in groupby(sorted(history,key=lambda m:m['date']),key=lambda m:m['date'][:10]):
        matches=list(items)
        for m in matches:
            starters={str(t):[str(p['id']) for p in m['players'] if str(p.get('team_id'))==str(t) and p.get('starter') is True]
                      for t in (m['home_id'],m['away_id'])}
            if any(len(ids)!=11 or len(set(ids))!=11 for ids in starters.values()):
                excluded['incomplete_historical_starting_XI']+=1;continue
            for p in m['players']:
                if p.get('starter') is not True or p.get('goalkeeper') or heights.get(str(p['id']),{}).get('role_group')=='keepers':continue
                if not isinstance(p.get('headed_sot'),(int,float)) or not isinstance(p.get('headed_shots'),(int,float)) or not 0<=p['headed_sot']<=p['headed_shots']:
                    excluded['missing_target']+=1;continue
                team=str(p.get('team_id'));other=str(m['away_id']) if team==str(m['home_id']) else str(m['home_id'])
                gap=height_gap(p['id'],starters[other],heights)
                f=state.features(p['id'],team,m['league_id'],m['date'],gap)
                if not f:excluded['insufficient_prior_history']+=1;continue
                rows.append(dict(date=day,fixture_id=str(m['id']),player_id=str(p['id']),features=f,y=int(p['headed_sot']>0)))
        for m in matches:state.add(m)
    train=[r for r in rows if r['date']<=TRAIN_END]
    # Common rows across all variants: comparison cannot benefit from different coverage.
    complete=lambda rs:[r for r in rs if r['features']['height_available'] and r['features']['delivery_available']]
    artifact=dict(version='skyline-v1',market='1+ headed shot on target',created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                  train_end=TRAIN_END,validation_end=VALID_END,policy=POLICY,primary='baseline',
                  history_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),height_sha256=hashlib.sha256(height_file.read_bytes()).hexdigest(),
                  height_limit='Historical height and defender roles use the current registry: retrospective approximation, not archived prematch height evidence.',
                  models={v:fit(complete(train),indices) for v,indices in FEATURES.items()})
    report=dict(version=artifact['version'],train_end=TRAIN_END,validation_end=VALID_END,rows=len(rows),train_common=len(complete(train)),
                excluded=dict(excluded),height_limit=artifact['height_limit'],history_sha256=artifact['history_sha256'],
                note='Retrospective chronological probability replay. Archived starting identities reconstructed from results; prior rates exclude the entire target day. Not prospective or ROI evidence.',periods={})
    for label,rs in [('validation',[r for r in rows if TRAIN_END<r['date']<=VALID_END]),('test',[r for r in rows if r['date']>VALID_END])]:
        paired=complete(rs)
        report['periods'][label]={'start':min(r['date'] for r in rs),'end':max(r['date'] for r in rs),
            'all_eligible':len(rs),'common_rows':len(paired),'models':{v:metrics(paired,v,artifact) for v in FEATURES}}
        # Paired bootstrap by fixture, preserving correlation among teammates/opponents.
        by_fixture={}
        for r in paired:
            ps=predict(r['features'],artifact);y=r['y']
            loss={v:-(y*np.log(p)+(1-y)*np.log(1-p)) for v,p in ps.items()}
            by_fixture.setdefault(r['fixture_id'],[]).append(loss)
        fixture_values=list(by_fixture.values());rng=np.random.default_rng(1801026)
        sums=np.array([[sum(x[v]-x['baseline'] for x in group) for v in FEATURES] for group in fixture_values]);sizes=np.array([len(g) for g in fixture_values])
        draws=[]
        for _ in range(500):
            idx=rng.integers(0,len(sizes),len(sizes));draws.append(sums[idx].sum(axis=0)/sizes[idx].sum())
        ci=np.percentile(draws,[2.5,97.5],axis=0)
        report['periods'][label]['paired_log_loss_delta_95pct']={v:ci[:,i].tolist() for i,v in enumerate(FEATURES)}
    report['decision']='Freeze baseline as primary paper model. Track all variants on identical forward quotes; do not promote height from retrospective registry tests.'
    save(root/'data/aerial/skyline/model.json',artifact);save(root/'data/aerial/skyline/research.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args();main(args.root)
