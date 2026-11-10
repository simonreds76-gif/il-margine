"""Frozen J1 rolling joint rates. Same objective and numerical solver as Fable's verified study.
The daily fit is the registered prediction recipe, not retuning or live pricing.
"""
import csv, json, math, hashlib
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import scipy.sparse as sp
from scipy.special import expit
from scipy.sparse.linalg import splu, cg
from tennis_source_contract import unique_fixture_rows, validated_stat_rows, canonical_surface
from frozen_paper_common import read, atomic, digest
DIRECT=False
PREC,TOL,MAXIT=16.0,1e-7,100
FALLBACK=[0]
WEIGHTS={4:1.08,3:1.04,2:1.0,1:.72,0:.42,5:.88,6:.15}
INPUTS=('players_atp.csv','courts.csv','tours_atp.csv','games_atp.csv','stat_atp.csv')

def newton(X, n, w, wt, pen, start):
    """Maximise sum wt*(w*log q + (n-w)*log(1-q)) - 0.5*PREC*sum(beta[pen]^2), q = sigmoid(X beta)."""
    b = start.copy(); Xt = X.T.tocsr(); D = sp.diags(np.where(pen, PREC, 0.0))
    def obj(bb):
        z = X @ bb; return float((wt * (w * z - n * np.logaddexp(0, z))).sum() - 0.5 * PREC * (bb[pen] ** 2).sum())
    cur = obj(b)
    for it in range(1, MAXIT + 1):
        q = expit(X @ b); g = Xt @ (wt * (w - n * q)) - np.where(pen, PREC * b, 0.0)
        if np.abs(g).max() <= TOL: return b, it - 1, True, float(np.abs(g).max())
        Hm = (Xt @ sp.diags(wt * n * q * (1 - q)) @ X + D).tocsc()
        if DIRECT: step = splu(Hm).solve(g)
        else:
            step, info = cg(Hm, g, rtol=1e-12, maxiter=5000, M=sp.diags(1.0 / Hm.diagonal()))
            if info != 0: step = splu(Hm).solve(g); FALLBACK[0] += 1
        t = 1.0; dec = float(g @ step)                      # Newton decrement: predicted gain is dec/2
        while True:
            nb_ = b + t * step; val = obj(nb_)
            # Near the optimum the gain is below the rounding error of the objective (about 1e-10 here), so the comparison is noise:
            # take the full Newton step there. Same objective, same gradient test (A1.3 resolution of first-pass stalls).
            if val >= cur - 1e-12 or dec < 1e-6 or t < 1e-8: break
            t /= 2
        b, cur = nb_, val
    q = expit(X @ b); g = Xt @ (wt * (w - n * q)) - np.where(pen, PREC * b, 0.0)
    return b, MAXIT, bool(np.abs(g).max() <= TOL), float(np.abs(g).max())

def fit(history, surface, day):
    """History fields match the immutable research export, strict prior-day cutoff."""
    start=(date.fromisoformat(day)-timedelta(days=365)).isoformat()
    rows=[r for r in history if r[3]==surface and start<=r[0]<day and r[8]+r[10]>0 and r[13]+r[15]>0]
    if not rows:raise ValueError('missing_same_surface_history')
    ids=np.unique([r[i] for r in rows for i in (6,7)]); P=len(ids); M=len(rows)
    ia=np.searchsorted(ids,[r[6] for r in rows]);ib=np.searchsorted(ids,[r[7] for r in rows])
    srv=np.r_[ia,ib];ret=np.r_[ib,ia];idx=np.arange(2*M)
    n=np.array([r[o]+r[o+2] for o in (8,13) for r in rows],float)
    w=np.array([r[o+1]+r[o+3] for o in (8,13) for r in rows],float)
    wt=np.array([r[5] for _ in range(2) for r in rows],float)
    X=sp.csr_matrix((np.r_[np.ones(2*M),np.ones(2*M),-np.ones(2*M)],
        (np.r_[idx,idx,idx],np.r_[np.zeros(2*M,int),1+srv,1+P+ret])),shape=(2*M,1+2*P))
    pen=np.r_[False,np.ones(2*P,bool)];st=np.zeros(1+2*P);st[0]=math.log((wt*w).sum()/(wt*(n-w)).sum())
    b,it,ok,gradient=newton(X,n,w,wt,pen,st)
    if not ok:raise ValueError('joint_fit_did_not_converge')
    profiles=defaultdict(lambda:np.zeros(6))
    for r in rows:
        for pid,o in ((r[6],8),(r[7],13)):
            profiles[str(pid)]+=r[5]*np.array([1,r[o],r[o+1],r[o+2],r[o+3],r[o]+r[o+2]])
    detailed={}
    for pid,v in profiles.items():
        mc,fs,w1,ss,w2,sv=v
        ratios=[round(fs/sv,4),round(w1/fs,4) if fs else 0,round(w2/ss,4) if ss else 0]
        detailed[pid]=bool(max(1,round(mc))>=8 and max(1,round(sv))>=250 and .40<=ratios[0]<=.80 and .45<=ratios[1]<=.90 and .30<=ratios[2]<=.80)
    return dict(surface=surface,cutoff_exclusive=day,window_start=start,mu=float(b[0]),
        S={str(pid):float(v) for pid,v in zip(ids,b[1:1+P])},R={str(pid):float(v) for pid,v in zip(ids,b[1+P:])},
        detailed=detailed,matches=M,players=P,iterations=it,max_gradient=gradient)

def rates(model,a,b,cal):
    a,b=str(a),str(b)
    if not model['detailed'].get(a) or not model['detailed'].get(b):raise ValueError('detailed_same_surface_inputs_missing')
    la=model['mu']+model['S'][a]-model['R'][b];lb=model['mu']+model['S'][b]-model['R'][a]
    L=(la+lb)/2;G=la-lb
    center=cal['Lbar']+cal['a']+cal['lam']*(L-cal['Lbar'])
    return dict(raw=[float(expit(la)),float(expit(lb))],
        calibrated=[float(expit(center+cal['gam']*G/2)),float(expit(center-cal['gam']*G/2))])

def signature(base):
    return {n:dict(size=(base/n).stat().st_size,mtime_ns=(base/n).stat().st_mtime_ns) for n in INPUTS}

def native_history(root,day):
    base=root/'data/oncourt'; before=signature(base)
    sha={n:hashlib.sha256((base/n).read_bytes()).hexdigest() for n in INPUTS}
    def rows(n):
        with (base/n).open(encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)
    players={r['id']:r['name'] for r in rows('players_atp.csv')}
    courts={r['id']:canonical_surface(r['name']) for r in rows('courts.csv')}
    tours={r['id']:r for r in rows('tours_atp.csv')}
    start=(date.fromisoformat(day)-timedelta(days=365)).isoformat()
    key=lambda r:tuple(int(r[k]) for k in ('winner_id','loser_id','tour_id','round_id'))
    games={key(r):r for r in unique_fixture_rows([r for r in rows('games_atp.csv')
        if start<=r.get('date','')<day and all('/' not in players.get(r[k],'/') for k in ('winner_id','loser_id'))])}
    stats,rejected=validated_stat_rows(rows('stat_atp.csv'),set(games));history=[]
    for r in stats:
        g=games[key(r)];t=tours.get(r['tour_id']);sf=courts.get(t['court_id']) if t else None
        if not sf or sf=='N/A':continue
        rank=int(t['rank']);name=t['name'].upper()
        wt=WEIGHTS[6] if 'JUNIOR' in name else WEIGHTS[5] if 'DAVIS CUP' in name or 'BILLIE JEAN KING' in name else WEIGHTS.get(rank,.80)
        rr=[g['date'],int(t['id']),int(r['round_id']),sf,rank,wt,int(r['winner_id']),int(r['loser_id'])]
        rr += [int(float(r.get(p+k) or 0)) for p in ('w_','l_') for k in ('fs','w1s','w2sof','w2s','df')]
        if any(not 0<=rr[o+3]<=rr[o+2]-rr[o+4] for o in (8,13)):
            rejected['inconsistent_double_faults']=rejected.get('inconsistent_double_faults',0)+1;continue
        history.append(rr)
    history.sort(key=lambda x:(x[0],x[1],x[2],x[6],x[7]))
    if before!=signature(base):raise ValueError('native_inputs_changed_during_fit')
    return history,dict(source_sha256=sha,source_metadata=before,stat_exclusions=rejected)

class DailyRates:
    def __init__(self,root,folder,day,recipe_hash):
        self.root,self.folder,self.day,self.recipe_hash=root,folder,day,recipe_hash
        self.history=None;self.provenance=None;self.models={}
        self.source=signature(root/'data/oncourt')

    def get(self,surface):
        if surface in self.models:return self.models[surface]
        cachekey=digest([self.day,surface,self.recipe_hash,self.source])
        path=self.folder/'fit-cache'/(cachekey+'.json');old=read(path)
        if old:
            self.models[surface]=old;return old
        if self.history is None:self.history,self.provenance=native_history(self.root,self.day)
        model=fit(self.history,surface,self.day)
        model.update(self.provenance,recipe_sha256=self.recipe_hash)
        atomic(path,model);self.models[surface]=model
        return model
