"""Offline, chronological model comparison. Never edits live forecasts or stakes.

Stored ATP probabilities are winner-oriented: restore an identity-based orientation
before fitting. Historical input vintages/quote timestamps are not fully archived;
these are exploratory replays, not pristine holdouts or executable ROI evidence.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import expit, logit

SPEC = {
    'experiment': 'tennis-market-residual-v1', 'created': '2026-09-09',
    'automatic_promotion': False, 'ridge': 0.01,
    'features': ['stored_model', 'elo', 'serve_return', 'rank'],
    'constraints': 'nonnegative residual weights, sum <= 1; market logit offset fixed; no intercept',
    'folds': [2023, 2024, 2025], 'fit': 'strictly earlier calendar dates only',
    'bet_rule': 'one side per match, highest EV >= 10%, side-specific market gap <= 10pp; flat 1u',
    'roi_selection': 'No candidate or parameter selected by ROI',
    'bootstrap': '1000 calendar-week block resamples, seed 20260909',
    'limitations': ['Historical forecasts reconstructed; input vintages unavailable',
                    'Historical price timing unavailable; ROI illustrative',
                    'These years were examined in earlier research, not untouched holdouts',
                    'Main-tour coefficients must not be transferred to Challenger without validation'],
}

def read_csv(p):
    with p.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))

def finite(s):
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None

def load_history(root):
    rows, excluded, seen, sources = [], Counter(), set(), []
    for year in range(2022, 2026):
        p = root / 'data/backtest' / f'backtest-results-{year}.csv'
        sources.append({'file': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        for r in read_csv(p):
            if r.get('has_pinnacle_odds') != 'True': excluded['unverified_price_flag'] += 1; continue
            probs = [finite(r.get(k)) for k in ('our_prob', 'p_elo', 'p_serve_return', 'p_rank')]
            odds = [finite(r.get(k)) for k in ('pinnacle_odds', 'pinnacle_odds_loser')]
            if any(x is None or not 0 < x < 1 for x in probs): excluded['missing_component'] += 1; continue
            if any(x is None or not 1 < x <= 1000 for x in odds): excluded['invalid_price'] += 1; continue
            if r.get('actual_winner') != r.get('player1'): excluded['outcome_orientation'] += 1; continue
            if any(s in r.get('score', '').upper() for s in ['RET', 'W/O', 'DEF', 'ABD']): excluded['incomplete_match'] += 1; continue
            ids = [r.get('player1_id'), r.get('player2_id')]
            if not all(ids) or ids[0] == ids[1]: excluded['invalid_identity'] += 1; continue
            key = (r['date'][:10], *sorted(ids))
            if key in seen: excluded['duplicate_match'] += 1; continue
            seen.add(key)
            # The sorted ID does not depend on the outcome. A swap complements ALL
            # probabilities and swaps BOTH prices, keeping paired losses invariant.
            swap = ids[0] > ids[1]
            market = (1 / odds[0]) / (1 / odds[0] + 1 / odds[1])
            rows.append({'date': r['date'][:10], 'key': '|'.join(key), 'y': 0 if swap else 1,
                'probs': [1-x for x in probs] if swap else probs,
                'market': 1-market if swap else market, 'odds': odds[::-1] if swap else odds,
                'surface': r['surface'], 'series': r['series'], 'confidence': r['confidence']})
    return sorted(rows, key=lambda r: (r['date'], r['key'])), dict(excluded), sources

def arrays(rows):
    return (np.array([r['probs'] for r in rows]), np.array([r['market'] for r in rows]),
            np.array([r['y'] for r in rows]), np.array([r['odds'] for r in rows]))

def fit_stack(probs, market, y):
    offset = logit(np.clip(market, 1e-6, 1-1e-6))
    x = logit(np.clip(probs, 1e-6, 1-1e-6)) - offset[:, None]
    def loss(w):
        z = offset + x @ w
        return np.mean(np.logaddexp(0, z) - y*z) + SPEC['ridge'] * np.sum(w*w)
    def grad(w): return x.T @ (expit(offset+x@w)-y)/len(y) + 2*SPEC['ridge']*w
    result = minimize(loss, np.zeros(probs.shape[1]), jac=grad, method='SLSQP',
        bounds=[(0, 1)]*probs.shape[1], constraints=[{'type':'ineq','fun':lambda w:1-w.sum()}],
        options={'maxiter':250,'ftol':1e-12})
    if not result.success: raise RuntimeError(result.message)
    return result.x

def stack_predict(probs, market, weights):
    z = logit(np.clip(market, 1e-6, 1-1e-6))
    return expit(z + (logit(np.clip(probs, 1e-6, 1-1e-6))-z[:, None]) @ weights)

def metrics(rows, p):
    _, market, y, odds = arrays(rows)
    p = np.clip(p, 1e-6, 1-1e-6)
    ll = -(y*np.log(p)+(1-y)*np.log1p(-p))
    ev = np.column_stack((p, 1-p))*odds-1
    side = ev.argmax(axis=1)
    take = (ev.max(axis=1) >= 0.10) & (np.abs(p-market) <= 0.10)
    # All eligible matches contribute probability scores, not just selected bets.
    won = side == (1-y)
    pnl = np.where(take, np.where(won, odds[np.arange(len(rows)),side]-1, -1), 0)
    n = int(take.sum())
    blocks = defaultdict(lambda: [0., 0.])
    for r, b, profit in zip(rows, take, pnl):
        d = date.fromisoformat(r['date']); key = d.isocalendar()[:2]
        blocks[key][0] += int(b); blocks[key][1] += profit
    intervals = None
    if n and len(blocks) >= 8:
        a = np.array(list(blocks.values())); rng = np.random.default_rng(20260909)
        samples = a[rng.integers(0,len(a),size=(1000,len(a)))].sum(axis=1)
        valid = samples[:,0] > 0
        intervals = np.quantile(100*samples[valid,1]/samples[valid,0],[.025,.975]).tolist()
    return {'matches':len(rows),'brier':float(np.mean((p-y)**2)), 'log_loss':float(ll.mean()),
            'bets':n,'wins':int((take & won).sum()),'losses':int((take & ~won).sum()),
            'pnl_units':float(pnl.sum()),'roi_pct':float(100*pnl.sum()/n) if n else None,
            'roi_week_block_95pct':intervals,
            'largest_win_profit':float(pnl.max()) if n else None,
            'roi_without_best_win_pct':float(100*(pnl.sum()-pnl.max())/(n-1)) if n>1 and (take & won).any() else None}

def challenger_diagnostic(root):
    rows=[]; seen=set()
    for r in read_csv(root/'data/backtest/backtest-results-challenger-2026.csv'):
        p=finite(r.get('our_prob')); odds=[finite(r.get(k)) for k in ('pinnacle_odds','pinnacle_odds_loser')]
        if p is None or not 0<p<1 or any(o is None or o<=1 for o in odds):continue
        if r.get('actual_winner')!=r.get('player1'):continue
        key=(r['date'],*sorted((r['player1_id'],r['player2_id'])))
        if key in seen:continue
        seen.add(key);m=(1/odds[0])/(1/odds[0]+1/odds[1])
        # Only stored probability and market are used; unavailable rank is not imputed.
        rows.append({'key':'|'.join(key),'date':r['date'],'probs':[p], 'market':m,'odds':odds,'y':1})
    p,m,_,_=arrays(rows)
    return {'warning':'Small historical hybrid sample, incomplete quote timing; exploratory only. No coefficients transferred from ATP.',
        'stored_model':metrics(rows,p[:,0]),'market_no_vig':metrics(rows,m),
        'market75_model25':metrics(rows,.75*m+.25*p[:,0])}

def prospective_coverage(root):
    # Audit coverage only: selection-biased ledgers are not training universes.
    out = {}
    for stem, name in [('', 'Strict'),('-volume200','Volume 200'),('-challenger-ml-v2','Challenger ML v2')]:
        path = root/'data/backtest'/f'strict-signals{stem}-archive.csv'
        if not path.exists(): continue
        a = read_csv(path)
        ml = [r for r in a if r.get('bet_type','match') in ('','match')]
        out[name] = {'file':str(path),'raw_rows':len(a),'match_rows':len(ml),
            'with_scheduled_start':sum(bool(r.get('scheduled_start_utc')) for r in ml),
            'with_both_closing_prices':sum(all(finite(r.get(k)) is not None for k in ('closing_odds1','closing_odds2')) for r in ml),
            'use':'coverage audit only; repeats/settlement updates not independent bets'}
    p = root/'data/backtest/backtest-results-challenger-2026.csv'
    if p.exists():
        a=read_csv(p)
        out['Challenger historical hybrid']={'rows':len(a),'missing_rank':sum(finite(r.get('p_rank')) is None for r in a),
            'use':'not pooled with main-tour training; too little independent hybrid history'}
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    # Persist specification before calculations; this is not a prospective preregistration.
    (args.output/'spec.json').write_text(json.dumps(SPEC,indent=2),encoding='utf-8')
    rows,excluded,sources=load_history(args.root);folds=[]; pooled=defaultdict(lambda: [[],[]]); predictions=[]
    for year in SPEC['folds']:
        train=[r for r in rows if r['date'] < f'{year}-01-01']
        test=[r for r in rows if f'{year}-01-01' <= r['date'] < f'{year+1}-01-01']
        tp,tm,ty,_=arrays(train);p,m,y,_=arrays(test)
        slope=minimize_scalar(lambda s: np.mean(np.logaddexp(0,s*logit(tp[:,0]))-ty*s*logit(tp[:,0])),bounds=(.4,1.6),method='bounded').x
        w=fit_stack(tp,tm,ty)
        candidates={'stored_model':p[:,0], 'market_no_vig':m, 'elo_only':p[:,1],
            'temperature_prior_fit':expit(slope*logit(p[:,0])),
            'market75_model25':.75*m+.25*p[:,0],
            'market_residual_stack_v1':stack_predict(p,m,w)}
        scores={}
        for name,prob in candidates.items():
            scores[name]=metrics(test,prob); pooled[name][0].extend(test);pooled[name][1].extend(prob)
        folds.append({'year':year,'train_n':len(train),'train_end':train[-1]['date'],'test_start':test[0]['date'],
            'test_n':len(test),'temperature':float(slope),'residual_weights':dict(zip(SPEC['features'],w.tolist())), 'scores':scores})
        for i,r in enumerate(test):
            predictions.append({'match_key':r['key'],'date':r['date'],'y':r['y'],'surface':r['surface'],'odds1':r['odds'][0],'odds2':r['odds'][1],
                'series':r['series'], **{k:float(v[i]) for k,v in candidates.items()}})
    summaries={k:metrics(a,np.array(p)) for k,(a,p) in pooled.items()}
    segmented={}
    for segment,accept in [('Hard Masters high',lambda r:r['surface']=='Hard' and r['series']=='Masters 1000' and r['confidence']=='high'),
                          ('Clay',lambda r:r['surface']=='Clay'),('Hard',lambda r:r['surface']=='Hard')]:
        segmented[segment]={}
        for name,(a,p) in pooled.items():
            idx=[i for i,r in enumerate(a) if accept(r)]
            if idx:segmented[segment][name]=metrics([a[i] for i in idx],np.array([p[i] for i in idx]))
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'spec':SPEC,'sources':sources,'excluded':excluded,
        'folds':folds,'pooled':summaries,'segments':segmented,'prospective_coverage':prospective_coverage(args.root),
        'challenger_diagnostic':challenger_diagnostic(args.root),
        'verdict':'RESEARCH_ONLY_NO_LIVE_PROMOTION','additional_exclusions':['2026 ATP legacy file omitted: missing explicit real-price flags and inconsistent historical schema']}
    (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (args.output/'predictions.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(predictions[0]));writer.writeheader();writer.writerows(predictions)
    lines=['# Tennis ML improvement experiment — 9 September 2026','',
        'Local offline research. No live model, stake, schedule, website or database writes.',
        'Three chronological evaluation folds; weights fit only to earlier calendar dates. These historical years have been studied before: this is not untouched prospective validation.',
        'ROI uses recorded historical prices with incomplete timing provenance; it is diagnostic, not a verified executable return. The fixed evaluation policy is not a replay of all current live routing rules.','',
        '| Candidate | Matches | Log loss | Brier | Bets | W/L | ROI | 95% week-block ROI interval |',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    for k,s in summaries.items():
        roi='—' if s['roi_pct'] is None else f"{s['roi_pct']:+.2f}%"
        ci=s['roi_week_block_95pct']; cis='—' if ci is None else f'{ci[0]:+.1f}% to {ci[1]:+.1f}%'
        lines.append(f"| {k} | {s['matches']} | {s['log_loss']:.5f} | {s['brier']:.5f} | {s['bets']} | {s['wins']}/{s['losses']} | {roi} | {cis} |")
    lines += ['', '## Fold fits', '', '```json',json.dumps([{k:v for k,v in f.items() if k!='scores'} for f in folds],indent=2),'```',
        '', '## Challenger and live-archive coverage','', '```json',json.dumps(report['prospective_coverage'],indent=2),'```',
        '', '## Challenger fixed-formula diagnostic', '', '```json',json.dumps(report['challenger_diagnostic'],indent=2),'```',
        '', 'The small Challenger hybrid file is not enough to train or validate a new Challenger model. The larger rejected context dataset is a different model and cannot substitute for it.',
        '', 'Next evidence requirement: capture all priced pre-match candidates (including rejected selections), immutable probabilities/components, source vintage, schedule and real entry/closing odds. Then evaluate the frozen residual candidate on fresh ATP and Challenger matches separately.',
        '', 'No parameter search is repeated after seeing these results. No automatic promotion.']
    (args.output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'pooled':summaries,'weights':[f['residual_weights'] for f in folds],'excluded':excluded},indent=2))

if __name__=='__main__':main()
