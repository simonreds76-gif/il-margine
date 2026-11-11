"""Indoor Scout ATP250/500: prospective expansion paper evidence; no network or live writes.

The comparison changes the admitted surface for Strict's core numerical gates.
Optional issued-signal injury/handicap overlays are NOT simulated. This is not
the Strict betting ledger and never authorises an alert or a real stake.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from hashlib import sha256
import ast, csv, io, json, math, re
from tennis_hardcourt_scout import (utc, read, atomic, immutable, locked,
                                  fixture_key, match_quote, completed, environment)

RELATIVE = Path('data/tennis-ml-research/indoor-expansion-v1')
NAME = 'Indoor Scout ATP250/500'
VERSION = 'indoor-expansion-v1'
FILES = ('scripts/oncourt-compute-fair-odds.py', 'scripts/live_model_v2.py',
         'scripts/matchup_model.py', 'scripts/tennis_pricing_context.py',
         'scripts/tennis_source_contract.py', 'scripts/tennis_tournament_category.py',
         'src/lib/tennis_prob.py', 'scripts/tennis_indoor_expansion.py', 'scripts/tennis_indoor_paper.py',
         'scripts/tennis_paper_quote_identity.py', 'scripts/tennis_price_identity.py',
         'scripts/tennis_hardcourt_scout.py')
RULES = dict(surface='I.hard', categories=['ATP250','ATP500'], qualifying=True,
             confidence='high', minimum_ev_pct=5, minimum_both_prices=1.25,
             maximum_model_favourite=.8, maximum_favourite_gap=.10,
             heavy_favourite_dog_guard=.74, paper_stake=1, actual_stake=0,
             price_max_age_hours=2, market='match winner',
             timing='first fresh priced forecast per edition, round and player pair',
             settlement='completed BO3 singles; retirement/walkover/default/abandonment void',
             optional_live_overlays='injury and handicap vetoes not simulated')


def hashes(root):
    return {f:sha256(ast.dump(ast.parse((root/f).read_text(encoding='utf-8-sig'))).encode()).hexdigest() for f in FILES}


def register(root, now=None):
    now=now or datetime.now(timezone.utc); folder=root/RELATIVE
    with locked(folder):
        path=folder/'registration.json'
        if path.exists(): return read(path)
        tree=ast.parse((root/'scripts/tennis_source_contract.py').read_text(encoding='utf-8-sig'))
        contract=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in n.targets))
        reg=dict(name=NAME, version=VERSION, registered_at=now.isoformat(), rules=RULES,
                 model_hashes=hashes(root), model_environment=environment(root), input_contract=contract, review_milestones=[50,100],
                 historical_replay_included=False, actual_stake=0, alerts=False, automatic_promotion=False,
                 protocol=read(root/'config/indoor-expansion-paper-v1.json'))
        immutable(path,reg)
        atomic(folder/'capture-status.json',dict(state='CONNECTED_AWAITING_FIRST_RUN',checked_at=now.isoformat(),actual_stake=0))
    return reg


def select(p,q,row):
    a,b=q['odds1'],q['odds2']; market=(1/a)/(1/a+1/b)
    side=1 if p*a-1 >= (1-p)*b-1 else 2
    ev=100*((p if side==1 else 1-p)*(a if side==1 else b)-1)
    reasons=[]
    if row.get('surface')!='I.hard': reasons.append('surface')
    if row.get('official_category') not in RULES['categories']: reasons.append('category')
    if int(row.get('best_of',3))!=3: reasons.append('format')
    if str(row.get('confidence','')).lower()!='high': reasons.append('confidence')
    if max(p,1-p)>.8: reasons.append('model_short_favourite')
    if min(a,b)<1.25: reasons.append('market_short_favourite')
    if abs(max(p,1-p)-max(market,1-market))>.10: reasons.append('market_gap')
    # Strict explicitly permits a side flip in the Hard/Masters/high segment
    # when its favourite-gap check passes. No extra side-flip exclusion here.
    if max(p,1-p)>=.74 and side!=(1 if p>=.5 else 2): reasons.append('heavy_favourite_dog')
    if ev+1e-10<5: reasons.append('ev_below_5')
    return dict(side=side, ev_pct=ev, qualifies=not reasons, reasons=reasons)


def quotes(root,now):
    paths=sorted([p for d in (now,now-timedelta(days=1)) for p in (root/'data/pinnacle-history').glob(f'pinnacle-history-{d:%Y%m%d}-*.csv')],reverse=True)[:8]
    available=[]; sources={}
    for path in paths:
        raw=path.read_bytes(); sources[path.name]=sha256(raw).hexdigest()
        for q in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
            stamp,start=utc(q.get('captured_at')),utc(q.get('kickoff_iso'))
            if not stamp or not start or not stamp<=now<start: continue
            if now-stamp>timedelta(hours=2) or start-now>timedelta(days=7): continue
            if q.get('bookmaker','').casefold()!='pinnacle' or q.get('league','').casefold()=='challenger': continue
            if str(q.get('is_live','')).lower() in ('true','1') or q.get('capture_mode','').lower() in ('live','inplay','in-play'): continue
            available.append(q)
    return available,sources


def game_index(root,wanted=None):
    out=defaultdict(list); path=root/'data/oncourt/games_atp.csv'
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f:
            for g in csv.DictReader(f):
                key='|'.join([g['tour_id'],g['round_id']]+sorted([g['winner_id'],g['loser_id']]))
                if (wanted is None or key in wanted) and g.get('result','').strip(): out[key].append(g)
    return out


def capture(root,rows,now=None,forecast_generated_at=None):
    now=now or datetime.now(timezone.utc); stamp=utc(forecast_generated_at) if forecast_generated_at else now
    folder=root/RELATIVE
    with locked(folder):
        reg=read(folder/'registration.json'); effective=utc(reg.get('registered_at'))
        if not effective or not stamp or not effective<=stamp<=now or stamp.date()!=now.date() or now-stamp>timedelta(hours=2): raise ValueError('fresh post-registration forecast required')
        if reg['rules']!=RULES or reg.get('protocol')!=read(root/'config/indoor-expansion-paper-v1.json') or reg['model_hashes']!=hashes(root): raise ValueError('registered implementation changed; review required')
        if reg['model_environment']!=environment(root): raise ValueError('registered model settings changed')
        available,price_hashes=quotes(root,now); reasons=Counter(); decisions=[]
        scope=[r for r in rows if r.get('surface')=='I.hard' and r.get('official_category') in RULES['categories']]
        keys=[fixture_key(r) for r in scope]
        key_counts=Counter(keys)
        known=game_index(root,set(keys)); reg_hash=sha256((folder/'registration.json').read_bytes()).hexdigest()
        for row,key in zip(scope,keys):
            path=folder/'captures'/(sha256(key.encode()).hexdigest()+'.json')
            reason='duplicate_forecast_fixture' if key_counts[key]>1 else None
            if row.get('source_contract')!=reg['input_contract'] or row.get('model_policy')!='category_corrected': reason='input_contract'
            elif int(row.get('best_of',3))!=3: reason='not_bo3'
            elif known[key]: reason='result_already_known'
            elif path.exists(): reason='already_recorded'
            try:p=float(row['p1_win_prob'])
            except (TypeError,ValueError):p=float('nan')
            if not math.isfinite(p) or not 0<p<1: reason='invalid_probability'
            q=None
            if not reason:
                from tennis_paper_quote_identity import match_quote as exact_quote
                q,reason=exact_quote(root,row,[q for q in available if utc(q['captured_at'])<=stamp])
            if reason:
                reasons[reason]+=1; decisions.append(dict(fixture_key=key,players=[row['player1'],row['player2']],reason=reason)); continue
            selection=select(p,q,row)
            packet=dict(version=VERSION,fixture_key=key,captured_at=now.isoformat(),forecast_generated_at=stamp.isoformat(),
                        tour_id=str(row['tour_id']),round_id=str(row['round_id']), players=[str(row['player1_id']),str(row['player2_id'])],
                        names=[row['player1'],row['player2']],tournament=row['tour_name'],surface='I.hard',category=row['official_category'],
                        qualifying=int(row['round_id']) in (1,2,3),probability=p,quote=q,selection=selection,
                        components=row,price_hashes=price_hashes,registration_sha256=reg_hash,
                        paper_stake=1 if selection['qualifies'] else 0,actual_stake=0)
            path.parent.mkdir(parents=True,exist_ok=True)
            immutable(path,packet); reasons['captured']+=1
            for why in selection['reasons']: reasons['selection:'+why]+=1
            decisions.append(dict(fixture_key=key,players=packet['names'],qualifies=selection['qualifies'],reasons=selection['reasons']))
        health=dict(state='CAPTURED' if reasons['captured'] else 'WAITING_FOR_FRESH_PRICED_FIXTURES',checked_at=now.isoformat(),
                    scope_fixtures=len(scope),fresh_price_rows=len(available),counts=dict(reasons),decisions=decisions,actual_stake=0)
        atomic(folder/'capture-status.json',health)
    return health


def settle(r,matched,now,effective,reg_hash):
    stamp=utc(r['captured_at']); start=utc(r['quote']['kickoff_iso'])
    if not stamp or not start or not effective<=stamp<start or r['registration_sha256']!=reg_hash or r['actual_stake']!=0:
        return dict(status='quarantined',reason='capture_integrity')
    if start>now: return dict(status='pending')
    if len(matched)>1: return dict(status='quarantined',reason='ambiguous_result')
    if not matched: return dict(status='pending',reason='result_not_available')
    g=matched[0]; day=date.fromisoformat(g['date'][:10]); score=g['result'].upper()
    if day>now.date() or day<stamp.date() or abs((day-start.date()).days)>1: return dict(status='quarantined',reason='result_timing')
    if re.search(r'RET|W/O|WALK|DEF|ABD|BYE',score): return dict(status='void',score=score,result_date=day.isoformat())
    if not completed(score): return dict(status='pending',reason='incomplete_score')
    return dict(status='settled',score=score,result_date=day.isoformat(),winner_id=g['winner_id'])


def summarize(root,now=None):
    now=now or datetime.now(timezone.utc);folder=root/RELATIVE
    with locked(folder):
        reg=read(folder/'registration.json')
        if not reg:return {}
        reg_hash=sha256((folder/'registration.json').read_bytes()).hexdigest(); effective=utc(reg['registered_at'])
        records=[read(p) for p in sorted((folder/'captures').glob('*.json'))]; games=game_index(root,{r['fixture_key'] for r in records}) if records else {}
        outcomes={}; selections=[]; forecasts=[]; accuracy=[]
        previous=read(folder/'outcomes.json')
        for r in records:
            out=settle(r,games.get(r['fixture_key'],[]),now,effective,reg_hash)
            old=previous.get(r['fixture_key'],{})
            if old.get('status') in ('settled','void') and out!=old:
                conflict=dict(fixture_key=r['fixture_key'],retained=old,proposed=out)
                path=folder/'conflicts'/(sha256(json.dumps(conflict,sort_keys=True).encode()).hexdigest()+'.json')
                path.parent.mkdir(parents=True,exist_ok=True)
                if not path.exists():immutable(path,conflict)
                out=old
            outcomes[r['fixture_key']]=out
            q=r['quote']; sel=r['selection']; side=sel['side']; won=None; pnl=None
            if out['status']=='settled':
                y=int(out['winner_id']==r['players'][0]);accuracy.append((r['probability'],q['market_p1'],y))
                won=out['winner_id']==r['players'][side-1]; pnl=q['odds'+str(side)]-1 if won else -1
            elif out['status']=='void':pnl=0
            row=dict(fixture_key=r['fixture_key'],kickoff=q['kickoff_iso'],captured_at=r['captured_at'],tournament=r['tournament'],
                     round_id=r['round_id'],category=r['category'],qualifying=r['qualifying'],player=r['names'][side-1],opponent=r['names'][2-side],
                     probability=r['probability'] if side==1 else 1-r['probability'],fair_odds=1/(r['probability'] if side==1 else 1-r['probability']),
                     odds=q['odds'+str(side)],bookmaker=q['bookmaker'],ev_pct=sel['ev_pct'],status=out['status'],
                     score=out.get('score'),result_date=out.get('result_date'),won=won,pnl_units=pnl if sel['qualifies'] else None,
                     qualifies=sel['qualifies'],rejections='; '.join(sel['reasons']),paper_stake=r['paper_stake'],actual_stake=0)
            forecasts.append(row)
            if sel['qualifies']:selections.append(row)
        tally=Counter(r['status'] for r in selections); settled=[r for r in selections if r['status']=='settled'];profit=math.fsum(r['pnl_units'] for r in settled)
        scores={name:dict(n=len(accuracy),brier=sum((x[i]-x[2])**2 for x in accuracy)/len(accuracy) if accuracy else None,
                 log_loss=sum(-math.log(x[i] if x[2] else 1-x[i]) for x in accuracy)/len(accuracy) if accuracy else None) for name,i in [('model',0),('market',1)]}
        curve=peak=drawdown=0
        for item in sorted(settled,key=lambda x:(x.get('result_date') or x['kickoff'],x['fixture_key'])):
            curve+=item['pnl_units'];peak=max(peak,curve);drawdown=max(drawdown,peak-curve)
        report=dict(name=NAME,version=VERSION,generated_at=now.isoformat(),registered_at=reg['registered_at'],capture=read(folder/'capture-status.json'),
                    rules=RULES,registered_fixtures=len(records),qualifying_fixtures=sum(r['qualifying'] for r in records),settled_fixtures=len(accuracy),
                    selections_total=len(selections),settled=len(settled),wins=sum(r['won'] is True for r in settled),losses=sum(r['won'] is False for r in settled),
                    pending=tally['pending'],void=tally['void'],quarantined=tally['quarantined'],
                    overdue=sum(r['status']=='pending' and now-utc(r['kickoff'])>timedelta(hours=48) for r in selections),
                    stake_units=len(settled),pnl_units=profit,roi_pct=100*profit/len(settled) if settled else None,
                    actual_stake=0,paper_stake_per_bet=1,paired_accuracy=scores,selections=selections[-500:],
                    forecasts=forecasts[-500:],max_drawdown=drawdown,
                    baseline=dict(name='Masters-only policy on added fixtures',stake_units=0,pnl_units=0,roi_pct=None),
                    category_mix=dict(Counter(r['category'] for r in records)),
                    tournament_editions=len({r['tour_id'] for r in records}),
                    uncertainty='Descriptive until at least 100 settled fixtures and 10 tournament editions; then review paired edition-cluster intervals. Milestones are not promotion.',
                    comparison='Same current-model probabilities; scope expansion only. Original Masters ledger remains separate.',
                    alerts=False,automatic_promotion=False,
                    historical_replay_included=False,closing_prices_verified=False,
                    limitations=['Paper prices, no execution claim.','Core Strict numerical gates; optional injury/handicap overlays not simulated.','Scheduled start verified; actual first serve not independently verified.'],
                    review_milestones_reached=[n for n in (50,100) if len(accuracy)>=n])
        if previous and previous!=outcomes:
            path=folder/'outcome-history'/(sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest()+'.json')
            path.parent.mkdir(parents=True,exist_ok=True)
            if not path.exists():immutable(path,previous)
        atomic(folder/'outcomes.json',outcomes);atomic(folder/'report.json',report)
        fields=['fixture_key','kickoff','captured_at','tournament','round_id','category','qualifying','player','opponent','probability','fair_odds','odds','bookmaker','ev_pct','status','score','result_date','won','pnl_units','qualifies','rejections','paper_stake','actual_stake']
        for name,rows in [('selections',selections),('forecasts',forecasts)]:
            buff=io.StringIO(); w=csv.DictWriter(buff,fieldnames=fields);w.writeheader();w.writerows(rows)
            temp=folder/(name+'.csv.tmp');temp.write_text(buff.getvalue(),encoding='utf8');temp.replace(folder/(name+'.csv'))
    return report


def observe(root,rows,now=None,forecast_generated_at=None):
    if not (root/RELATIVE/'registration.json').exists():return 'not registered'
    try:
        result=capture(root,rows,now,forecast_generated_at)
        summarize(root,now)
        return result
    except Exception as exc:
        atomic(root/RELATIVE/'capture-status.json',dict(state='BLOCKED',checked_at=(now or datetime.now(timezone.utc)).isoformat(),reason=str(exc),actual_stake=0))
        return 'BLOCKED: see Indoor Scout expansion capture status'


def refresh(root,now=None):
    now=now or datetime.now(timezone.utc);folder=root/RELATIVE;reg=read(folder/'registration.json')
    if not reg:return {}
    packets=[]
    for path in (root/'data/tennis-ml-research/components'/now.strftime('%Y-%m-%d')).glob('*.json'):
        if path.stat().st_size>500_000:continue
        packet=read(path);stamp=utc(packet.get('captured_at'))
        if stamp and utc(reg['registered_at'])<=stamp<=now and now-stamp<=timedelta(hours=2):packets.append((stamp,packet))
    if packets:
        stamp,p=max(packets,key=lambda x:x[0]);body=json.dumps(p['rows'],sort_keys=True,separators=(',',':'),allow_nan=False)
        if sha256(body.encode()).hexdigest()!=p.get('payload_sha256') or p.get('model_file_sha256')!=sha256((root/FILES[0]).read_bytes()).hexdigest():
            atomic(folder/'capture-status.json',dict(state='BLOCKED',checked_at=now.isoformat(),reason='component checksum/version mismatch',actual_stake=0))
        else:observe(root,p['rows'],now,stamp.isoformat())
    else:
        atomic(folder/'capture-status.json',dict(state='WAITING_FOR_FRESH_FORECAST',checked_at=now.isoformat(),reason='No verified post-registration component packet within two hours',actual_stake=0))
    return summarize(root,now)


def weekly_text(report):
    if not report:return 'Indoor Scout ATP250/500: paper snapshot unavailable.'
    roi=report.get('roi_pct');rt=f'{roi:+.2f}% ROI' if roi is not None else 'ROI awaits settled selections'
    c=report.get('capture') or {};a=report.get('paired_accuracy',{}).get('model',{})
    market=report.get('paired_accuracy',{}).get('market',{})
    acc=f"Brier {a['brier']:.4f}, log loss {a['log_loss']:.4f}" if a.get('brier') is not None else 'calibration awaits completed fixtures'
    if market.get('brier') is not None:acc+=f" vs market {market['brier']:.4f}/{market['log_loss']:.4f}"
    return (f"Indoor Scout ATP250/500 | qualifying included | PAPER ONLY\n"
            f"{report.get('wins',0)}W/{report.get('losses',0)}L | {report.get('pnl_units',0):+.2f}u on {report.get('stake_units',0):g}u | {rt}\n"
            f"{report.get('pending',0)} pending ({report.get('overdue',0)} overdue), {report.get('void',0)} void, {report.get('quarantined',0)} quarantined. "
            f"{report.get('registered_fixtures',0)} captured fixtures; {acc}. Core Strict gates; optional overlays not simulated. "
            f"1u paper, zero real stake. Capture {c.get('state','UNKNOWN')} at {c.get('checked_at','unknown')}. {c.get('reason','')}")


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--register',action='store_true');args=ap.parse_args()
    if args.register:register(args.root)
    print(weekly_text(refresh(args.root)))
