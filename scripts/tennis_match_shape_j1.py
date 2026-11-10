"""Frozen MJ1/MJ1-S inside Match Shape, separate future-only cohort.

Uses native same-surface inputs and same-response winner prices. Never changes
live rates, original Match Shape registrations/forecasts, or alert settings.
"""
import argparse
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tennis_match_shape as M
from tennis_match_shape_results import resolve_quote, supplemental
from tennis_match_winner_quotes import bind_winner
import frozen_paper_common as C

RELATIVE=M.RELATIVE/'j1-exploratory-v1'
PROTOCOL='config/tennis-match-shape-j1-protocol.json'
ARMS=('current','MJ1','MJ1_S')
FILES=tuple(sorted(set(M.FILES+(
    PROTOCOL,'scripts/tennis_j1_rates.py','scripts/tennis_match_shape_j1.py',
    'scripts/tennis_match_winner_quotes.py','scripts/frozen_paper_common.py',
    'scripts/tennis_source_contract.py','scripts/tennis_match_shape_results.py'))))

def solve(p,center):
    from src.lib import tennis_prob as TP
    target=max(.02,min(.98,p));center=max(.43,min(.79,center))
    delta=min(center-.42,.80-center);lo,hi=-delta,delta
    for _ in range(60):
        mid=(lo+hi)/2;pa,pb=center+mid,center-mid
        value=TP.prob_match_best_of_3(pa,pb)
        if abs(value-target)<.0005:return pa,pb
        if value<target:lo=mid
        else:hi=mid
    raise ValueError('market_winner_solve_failed')

def candidate_probabilities(rates,p,q,coefficient):
    pa,pb=solve(p,sum(rates)/2);raw=M.joint(pa,pb);idx=2 if q['market']=='total_games' else 1
    kernels={'MJ1':M.tilt(raw,p,0),'MJ1_S':M.tilt(raw,p,coefficient)}
    if any(abs(math.fsum(v for k,v in kernel.items() if k[0])-p)>1e-12 for kernel in kernels.values()):
        raise ValueError('market_winner_mass_changed')
    return ({a:M.contract(M.marginal(k,idx),q['market'],q['line']) for a,k in kernels.items()},
            {a:math.fsum(key[2]*v for key,v in k.items()) for a,k in kernels.items()},[pa,pb])

def capture(root,folder,reg,clock,receipt):
    began=time.monotonic();counts=Counter();registered=C.utc(reg['registered_at'])
    stamp,packet=M.fresh_components(root,root/M.RELATIVE,clock,registered)
    quotes=[q for q in M.parse_receipt(receipt,clock) if C.utc(q['captured_at'])>=registered]
    from tennis_match_shape_prepare import readiness
    ready=readiness(root,clock)
    rows=defaultdict(list)
    for r in (packet or {}).get('rows',[]):
        if r.get('best_of')==3 and r.get('model_policy')=='category_corrected' and r.get('official_category') in ('ATP250','ATP500','Masters 1000','Grand Slam'):
            rows[M.fixture_key(r)].append(r)
    index=M.identity_index(root);known=M.game_index(root,set(rows));groups=defaultdict(list)
    for q in quotes:
        try:
            ident=resolve_quote(q,index)
            key='|'.join([str(ident['edition_id']),str(ident['round_id'])]+sorted([str(ident['p1_id']),str(ident['p2_id'])]))
            if known.get(key):raise ValueError('result_already_known')
            # Persist the first verified fixture observation even when the
            # candidate or current inputs are missing. A later scan cannot rescue it.
            groups[key,q['market']].append((q,ident))
        except (ValueError,KeyError,TypeError) as exc:counts[str(exc)]+=1
    if groups:
        from tennis_j1_rates import DailyRates, rates
        daily_by_quote_day={}
        h,cfg,cal=M.settings(root)
        if cal!=reg['current_handicap_settings']:raise ValueError('paired_current_pricing_settings_changed')
    existing={C.read(p)['fixture_key'] for p in (folder/'decisions').glob('*.json')}
    decisions=defaultdict(lambda:dict(records=[],missing={}))
    for (key,market),choices in sorted(groups.items()):
        rid=C.digest([key,market]);path=folder/'captures'/(rid+'.json')
        if key in existing:counts['already_recorded']+=1;continue
        try:
            if not packet:raise ValueError('missing_fresh_current_forecast')
            if not ready['ready']:raise ValueError('current_inputs_not_ready:'+ready['reason'])
            if len(rows[key])!=1:raise ValueError('missing_or_ambiguous_current_forecast')
            row=rows[key][0]
            q,ident=min(choices,key=lambda x:(not x[0]['main_line'],abs((1/x[0]['odds1'])/(1/x[0]['odds1']+1/x[0]['odds2'])-.5),x[0]['line'],x[0]['offer_id']))
            if stamp>=C.utc(q['scheduled_start']):raise ValueError('forecast_after_start')
            winner=bind_winner(receipt,q)
            if str(row['player1_id'])!=str(ident['p1_id']):
                winner={**winner,'probability':1-winner['probability'],'orientation_reversed':True}
                if q['market']=='game_handicap':q={**q,'line':-q['line'],'odds1':q['odds2'],'odds2':q['odds1']}
            q={**q,'home':row['player1'],'away':row['player2'],'native_identity':ident}
            if time.monotonic()-began>90:raise ValueError('bounded_fit_budget_deferred')
            day=C.utc(q['captured_at']).date().isoformat()
            if day not in daily_by_quote_day:daily_by_quote_day[day]=DailyRates(root,folder,day,C.digest(reg['fingerprints']))
            daily=daily_by_quote_day[day]
            fit=daily.get(row['surface']);rate=rates(fit,row['player1_id'],row['player2_id'],reg['protocol']['point_calibration'])
            probs,means,solved=candidate_probabilities(rate['calibrated'],winner['probability'],q,reg['protocol']['lambda'])
            old,oldmeans,_=M.probabilities(row,q,h,cfg,cal)
            probs['current']=old['current'];means['current']=oldmeans['current']
            captured=clock+timedelta(seconds=time.monotonic()-began)
            if captured>=C.utc(q['scheduled_start']):raise ValueError('kickoff_reached_during_fit')
            from tennis_j1_rates import signature
            if signature(root/'data/oncourt')!=daily.source:raise ValueError('native_inputs_changed_during_capture')
            record=dict(id=rid,fixture_key=key,market=market,quote=q,components=row,captured_at=captured.isoformat(),
                forecast_generated_at=stamp.isoformat(),registration_sha256=M.file_sha(folder/'registration.json'),
                component_sha256=packet['payload_sha256'],raw_receipt_sha256=C.digest(receipt),probabilities=probs,means=means,
                selections={a:M.decision(probs[a],q,reg['protocol']) for a in ARMS},actual_stake=0,
                winner_quote=winner,j1_rates=rate,solved_rates=solved,fit_sha256=C.digest(fit),
                fit_cutoff_exclusive=fit['cutoff_exclusive'],fit_sources=fit['source_sha256'],
                display=dict(players=[row['player1'],row['player2']],tournament=row['tour_name'],surface=row['surface'],
                    qualifying=int(row['round_id'])<4,start=q['scheduled_start'],market=market,line=q['line'],
                    bookmaker=q['bookmaker'],odds=[q['odds1'],q['odds2']],price_observed_at=q['captured_at'],means=means))
            C.immutable(folder/'fit-evidence'/(C.digest(fit)+'.json'),fit)
            C.immutable(folder/'quote-evidence'/(C.digest(receipt)+'.json'),receipt)
            decisions[key]['records'].append(record);counts['captured']+=1
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            counts[str(exc)]+=1;decisions[key]['missing'][market]=str(exc)
    for key,value in decisions.items():
        C.immutable(folder/'decisions'/(C.digest(key)+'.json'),dict(fixture_key=key,first_observed_at=clock.isoformat(),**value))
    for path in (folder/'decisions').glob('*.json'):
        for record in C.read(path).get('records',[]):C.immutable(folder/'captures'/(record['id']+'.json'),record)
    return dict(state='CAPTURED' if counts['captured'] else 'NO_NEW_ELIGIBLE_CONTRACTS',checked_at=clock.isoformat(),
                captured=counts['captured'],fresh_quotes=len(quotes),counts=dict(counts))

def refresh(root,clock=None,receipt=None,settle_only=False):
    clock=clock or datetime.now(timezone.utc);folder=root/RELATIVE
    if not (folder/'registration.json').exists():return {}
    with M.locked(folder):
        try:reg=C.verify(root,folder,FILES)
        except (ValueError,OSError) as exc:
            C.atomic(folder/'capture-status.json',dict(state='BLOCKED_MODEL_CHANGE',reason=str(exc),checked_at=clock.isoformat()))
            return report(root)
        if not settle_only:
            if receipt is None:receipt,_=M.newest_receipt(root,clock)
            try:health=capture(root,folder,reg,clock,receipt)
            except Exception as exc:health=dict(state='CAPTURE_ERROR',reason=str(exc),checked_at=clock.isoformat(),captured=0)
            C.atomic(folder/'capture-status.json',health)
        else:
            from tennis_match_shape_prepare import readiness
            state=readiness(root,clock)
            C.atomic(folder/'capture-status.json',dict(state='AWAITING_FRESH_QUOTES' if state['ready'] else 'INPUT_REFRESH_REQUIRED',
                reason=state['reason'],checked_at=clock.isoformat(),captured=0,settlement_only=True))
        records=[C.read(p) for p in sorted((folder/'captures').glob('*.json'))]
        games=M.game_index(root,{r['fixture_key'] for r in records}) if records else {}
        extra=supplemental(root,records,clock);rh=M.file_sha(folder/'registration.json')
        proposed={r['id']:M.outcome(r,games.get(r['fixture_key'],[]),clock,rh) for r in records}
        for r in records:
            if proposed[r['id']]['status']=='pending' and r['fixture_key'] in extra:proposed[r['id']]=extra[r['fixture_key']]
        outcomes=C.preserve_outcomes(folder,proposed,clock)
        result=dict(name='ATP J1 score correction',registered_at=reg['registered_at'],updated_at=clock.isoformat(),protocol=reg['protocol'],
            capture=C.read(folder/'capture-status.json'),actual_stake=0,historical_replay_included=False,
            conflicts=len(list((folder/'conflicts').glob('*.json'))),**C.summary(records,outcomes,ARMS,clock))
        C.atomic(folder/'report.json',result)
        return result

def report(root):
    folder=root/RELATIVE;r=C.read(folder/'report.json')
    return {**r,'capture':C.read(folder/'capture-status.json')} if r else {}

def register(root,clock=None):
    clock=clock or datetime.now(timezone.utc);folder=root/RELATIVE
    with M.locked(folder):
        if (folder/'registration.json').exists():return C.verify(root,folder,FILES)
        reg=dict(registered_at=clock.isoformat(),protocol=C.read(root/PROTOCOL),fingerprints=C.hashes(root,FILES),
            current_handicap_settings=M.settings(root)[2],actual_stake=0,historical_replay_included=False)
        assert reg['protocol']['actual_stake']==0 and not reg['protocol']['alerts'] and not reg['protocol']['automatic_promotion']
        C.immutable(folder/'registration.json',reg)
        C.atomic(folder/'capture-status.json',dict(state='CONNECTED_AWAITING_FIRST_RUN',checked_at=clock.isoformat()))
        return reg

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--register',action='store_true');p.add_argument('--settle-only',action='store_true');a=p.parse_args()
    if a.register:register(a.root)
    r=refresh(a.root,settle_only=a.settle_only)
    print(json.dumps({k:r.get(k) for k in ('name','fixtures','contracts','settled_fixtures','capture')}))
