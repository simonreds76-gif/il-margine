"""Online, outcome-free forecaster for frozen BP-total model C (v2 constants; NO refitting).
Inputs: frozen-bp-params.json (v2), a validated completed-results history snapshot (history.csv schema), and fixtures WITHOUT outcomes:
  fixture_id, capture_at (UTC ISO), p1_id, p2_id, surface, level, phase, line, over, under  (line/over/under optional)
For each fixture the history is truncated to results dated <= capture_date(UTC) - 2 days, so the target match and anything later can never enter.
Usage (library): from bp_c_forward import load_history, forecast
Usage (parity self-test): python3 bp_c_forward.py parity <packet dir> <v2 out dir>
"""
import sys, json, re, math, hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np, pandas as pd
from scipy import stats, special

LAG = 2
SET = re.compile(r'^(\d+)-(\d+)(?:\((\d+)\))?$')
ADV_FINAL_SET_CONTEXTS = {('Wimbledon - London', 2021, 'qualifying')}

def valid_row(r):
    """identical to v2 strict validation; returns True only for fully consistent completed rows"""
    sets = str(r.score).split()
    if not 2 <= len(sets) <= 3: return False
    adv_ok = (r.tournament, int(str(r.result_date)[:4]), r.phase) in ADV_FINAL_SET_CONTEXTS
    gw = gl = sw = sl = tbw = tbl = 0; last = None
    for i, s in enumerate(sets):
        m = SET.match(s)
        if not m: return False
        a, b, tb = int(m.group(1)), int(m.group(2)), m.group(3); hi, lo = max(a, b), min(a, b)
        ok = (hi == 6 and lo <= 4) or (hi == 7 and lo in (5, 6))
        if not ok and adv_ok and i == 2 and hi >= 8 and hi - lo == 2 and tb is None: ok = True
        if not ok or (tb is not None and not (hi == 7 and lo == 6)): return False
        gw += a; gl += b
        if a > b: sw += 1; last = 'w'; tbw += (hi == 7 and lo == 6)
        else: sl += 1; last = 'l'; tbl += (hi == 7 and lo == 6)
    if not (sw == 2 and sl <= 1 and last == 'w'): return False
    if r.w_SvGms + r.l_SvGms != gw + gl - tbw - tbl: return False
    for p in ('w', 'l'):
        f, sv, g = getattr(r, p + '_bpFaced'), getattr(r, p + '_bpSaved'), getattr(r, p + '_SvGms')
        if not (0 <= sv <= f) or f - sv > g: return False
    if r.w_SvGms - (r.w_bpFaced - r.w_bpSaved) + (r.l_bpFaced - r.l_bpSaved) != gw - tbw: return False
    if r.l_SvGms - (r.l_bpFaced - r.l_bpSaved) + (r.w_bpFaced - r.w_bpSaved) != gl - tbl: return False
    if r.w_created != r.l_bpFaced or r.l_created != r.w_bpFaced: return False
    if r.w_converted != r.l_bpFaced - r.l_bpSaved or r.l_converted != r.w_bpFaced - r.w_bpSaved: return False
    if r.y != r.w_bpFaced + r.l_bpFaced or r.status != 'completed' or r.best_of != 3: return False
    return True

def load_history(path):
    H = pd.read_csv(path); H = H[[valid_row(r) for r in H.itertuples(index=False)]].copy()
    H['d'] = pd.to_datetime(H.result_date).values.astype('datetime64[D]').astype(np.int64)
    return H.sort_values(['d', 'match_id']).reset_index(drop=True)

class Frozen:
    def __init__(self, params_path):
        p = json.loads(Path(params_path).read_text()); self.p = p; self.sha = hashlib.sha256(Path(params_path).read_bytes()).hexdigest()
        self.lam = p['lambda_cell']; self.exp = p['exposure_table']; self.alpha = p['nb_alpha']; self.win = p['window_days']
        s = p['shrinkage']; self.k0c, self.k0g, self.k1c, self.k1g = (s[k]['k'] for k in ('pass0_concession', 'pass0_creation', 'pass1_concession', 'pass1_creation'))
        self.bins = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]
    def lam_of(self, surface, level, phase):
        return self.lam.get(f'cell:{surface}|{level}|{phase}', self.lam.get(f'surface:{surface}', self.lam['global']))
    def exp_of(self, surface, level, phase, b):
        for k in (f'cellbin:{surface}|{level}|{phase}|{b}', f'surfbin:{surface}|{b}', f'bin:{b}'):
            if k in self.exp: return self.exp[k], k.split(':')[0]
        return self.exp['global'], 'global'

class Win:
    def __init__(self, pid, d, O, E):
        o = np.lexsort((d, pid)); self.pid, self.d = pid[o], d[o]
        self.cO = np.r_[0, np.cumsum(O[o])]; self.cE = np.r_[0, np.cumsum(E[o])]
        u, st = np.unique(self.pid, return_index=True); self.s = dict(zip(u, st)); self.e = dict(zip(u, np.r_[st[1:], len(self.pid)]))
    def ratio(self, p, cutoff, k, win):
        if p not in self.s: return 1.0
        a, b = self.s[p], self.e[p]; dd = self.d[a:b]; hi = a + np.searchsorted(dd, cutoff, 'right'); lo = a + np.searchsorted(dd, cutoff - win, 'right')
        return (self.cO[hi] - self.cO[lo] + k) / (self.cE[hi] - self.cE[lo] + k)

def state_at(H, F, cutoff):
    """all model state from results dated <= cutoff only (no refit; frozen constants)"""
    Hc = H[H.d <= cutoff].reset_index(drop=True)
    R = defaultdict(lambda: 1500.0)
    for d, g in Hc.groupby('d', sort=True):
        delta = defaultdict(float)
        for w, l in zip(g.w_id.values, g.l_id.values):
            e = 1 / (1 + 10 ** ((R[l] - R[w]) / 400)); delta[w] += 32 * (1 - e); delta[l] -= 32 * (1 - e)
        for p, v in delta.items(): R[p] += v
    lam = np.array([F.lam_of(s, l, ph) for s, l, ph in zip(Hc.surface, Hc.level, Hc.phase)])
    def obs(mc, mg):
        out = []
        for s, o in (('w', 'l'), ('l', 'w')):
            base = Hc[s + '_SvGms'].values * lam
            out.append((Hc[s + '_id'].values, Hc[o + '_id'].values, Hc.d.values, Hc[s + '_bpFaced'].values.astype(float), base * mc[s], base * mg[s]))
        cat = lambda i: np.concatenate([x[i] for x in out]); return cat(0), cat(1), cat(2), cat(3), cat(4), cat(5)
    one = {'w': np.ones(len(Hc)), 'l': np.ones(len(Hc))}
    srv, ret, dd, O, Ec, Eg = obs(one, one); W0c = Win(srv, dd, O, Ec); W0g = Win(ret, dd, O, Eg)
    asof = Hc.d.values - LAG
    c0 = {s: np.array([W0c.ratio(p, t, F.k0c, F.win) for p, t in zip(Hc[s + '_id'].values, asof)]) for s in ('w', 'l')}
    g0 = {s: np.array([W0g.ratio(p, t, F.k0g, F.win) for p, t in zip(Hc[s + '_id'].values, asof)]) for s in ('w', 'l')}
    srv, ret, dd, O, Ec, Eg = obs({'w': g0['l'], 'l': g0['w']}, {'w': c0['w'], 'l': c0['l']})
    return dict(R=R, W1c=Win(srv, dd, O, Ec), W1g=Win(ret, dd, O, Eg), rows=len(Hc), last_result_d=int(Hc.d.max()) if len(Hc) else None)

def nb_over(mu, alpha, line):
    """P(Y > line) for half-lines via survival function (stable in the tail) + independent log-space cross-check"""
    n = 1 / alpha; p = n / (n + mu); k = int(math.floor(line))
    sf = float(stats.nbinom.sf(k, n, p))
    j = np.arange(0, k + 1); lp = special.gammaln(j + n) - special.gammaln(n) - special.gammaln(j + 1) + n * np.log(p) + j * np.log1p(-p)
    cdf = float(np.exp(special.logsumexp(lp))); return sf, abs(sf - (1 - cdf))

def forecast(H, F, fixtures):
    fx = fixtures.copy(); cap = pd.to_datetime(fx.capture_at, utc=True)
    fx['cutoff'] = cap.dt.tz_localize(None).dt.floor('D').values.astype('datetime64[D]').astype(np.int64) - LAG
    out = []
    for c, g in fx.groupby('cutoff'):
        S = state_at(H, F, c)
        for r in g.itertuples(index=False):
            R = S['R']; e = 1 / (1 + 10 ** ((R[r.p2_id] - R[r.p1_id]) / 400)); pfav = max(e, 1 - e); b = int(np.clip(np.digitize(pfav, F.bins) - 1, 0, 4))
            Ehat, tier = F.exp_of(r.surface, r.level, r.phase, b); lam = F.lam_of(r.surface, r.level, r.phase)
            cA, gA = S['W1c'].ratio(r.p1_id, c, F.k1c, F.win), S['W1g'].ratio(r.p1_id, c, F.k1g, F.win)
            cB, gB = S['W1c'].ratio(r.p2_id, c, F.k1c, F.win), S['W1g'].ratio(r.p2_id, c, F.k1g, F.win)
            mu = (lam * cA * gB + lam * cB * gA) * Ehat / 2
            rec = dict(fixture_id=r.fixture_id, capture_at=r.capture_at, cutoff_date=str(np.datetime64(int(c), 'D')), history_rows_used=S['rows'],
                       last_result_date=str(np.datetime64(S['last_result_d'], 'D')), pfav=pfav, bin=b, Ehat=Ehat, exposure_tier=tier, lam=lam, cA=cA, gA=gA, cB=cB, gB=gB, mu_C=mu, alpha=F.alpha,
                       params_sha256=F.sha)
            if hasattr(r, 'line') and pd.notna(getattr(r, 'line', np.nan)):
                po, chk = nb_over(mu, F.alpha, r.line); rec.update(line=r.line, p_over_C=po, tail_crosscheck_abs=chk)
                if pd.notna(getattr(r, 'over', np.nan)):
                    rec.update(over=r.over, under=r.under, mkt_over=(1 / r.over) / (1 / r.over + 1 / r.under), ev_over_C=po * r.over - 1, bet_C=int(po * r.over - 1 >= 0.05))
            out.append(rec)
    return pd.DataFrame(out)

