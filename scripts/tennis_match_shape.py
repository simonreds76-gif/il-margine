"""Append-only Match Shape paper comparison; no requests, alerts or live writes.

Reuses existing Grosvenor raw polling and fresh current-model components. The
published totals/handicap transformations are a separate arm from raw C/C0/T1.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import csv
import gzip
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

from tennis_hardcourt_scout import utc, read, atomic, immutable, locked, fixture_key
from tennis_indoor_paper import game_index
from tennis_match_shape_kernel import joint, tilt, marginal, contract, complete_score, LAMBDA
from tennis_breakpoint_forward import identity_index, map_quote
from tennis_grosvenor import eligible, scaled

RELATIVE = Path('data/tennis-ml-research/match-shape-v1')
PROTOCOL = 'config/tennis-match-shape-protocol.json'
CODE = Path(__file__).resolve().parents[1]
ARMS = ('current', 'T1', 'raw', 'C0')
FILES = ('scripts/tennis_match_shape.py', 'scripts/tennis_match_shape_kernel.py', PROTOCOL,
         'scripts/handicap_probs.py', 'src/lib/tennis_prob.py',
         'scripts/compute-handicap-values.py', 'scripts/spread_v1_model.py',
         'scripts/oncourt-compute-fair-odds.py', 'scripts/tennis_breakpoint_forward.py')


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_sha(path):
    return sha256(path.read_bytes()).hexdigest()


def handicap_module(root):
    name = '_match_shape_current_handicap'
    spec = importlib.util.spec_from_file_location(name, root / 'scripts/compute-handicap-values.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def settings(root):
    h = handicap_module(root)
    # Loads the same existing environment/settings, but never invokes its main.
    h.load_env()
    cfg = h.load_handicap_calibration(SimpleNamespace(disable_calibration=False, calibration_file=None))
    return h, cfg, dict(enabled=cfg.enabled, platt_a=cfg.platt_a, platt_b=cfg.platt_b,
                       source=cfg.source, payload=cfg.payload,
                       allow_sign_flip=h._env_bool('SPREAD_V1_ALLOW_CORRECTION_SIGN_FLIP', False))


def fingerprints(root):
    return {p: file_sha(root / p) for p in FILES}


def register(root, clock=None):
    clock = clock or datetime.now(timezone.utc)
    out = root / RELATIVE
    with locked(out):
        if (out / 'registration.json').exists():
            return read(out / 'registration.json')
        protocol = read(root / PROTOCOL)
        assert protocol['lambda'] == LAMBDA and protocol['actual_stake'] == 0 and protocol['alerts'] is False
        _, _, calibration = settings(root)
        reg = dict(registered_at=clock.isoformat(), protocol=protocol,
                   fingerprints=fingerprints(root), current_handicap_settings=calibration,
                   actual_stake=0, historical_replay_included=False)
        immutable(out / 'registration.json', reg)
        atomic(out / 'capture-status.json', dict(state='CONNECTED_AWAITING_FIRST_RUN', checked_at=clock.isoformat()))
    return reg


def parse_receipt(receipt, clock):
    """Allowlist full-match contracts. Keep negative handicap signs and raw evidence."""
    result = []
    for item in receipt.get('events', []):
        stamp = utc(item.get('captured_at'))
        if not stamp or not stamp <= clock or clock-stamp > timedelta(minutes=30):
            continue
        payload = item.get('payload', {})
        events = [e for e in payload.get('events', []) if str(e.get('id')) == str(item.get('requested_id'))]
        if len(events) != 1 or not eligible(events[0], stamp) or not any(p.get('termKey') == 'atp' for p in events[0].get('path', [])):
            continue
        e = events[0]
        if not clock < utc(e['start']):
            continue
        for offer in payload.get('betOffers', []):
            name = offer.get('criterion', {}).get('englishLabel')
            if name not in ('Total Games', 'Game Handicap') or str(offer.get('eventId')) != str(e['id']) or 'OFFERED_PREMATCH' not in offer.get('tags', []):
                continue
            outcomes = offer.get('outcomes', [])
            types = {o.get('type'): o for o in outcomes}
            market = 'total_games' if name == 'Total Games' else 'game_handicap'
            expected = ('OT_OVER', 'OT_UNDER') if market == 'total_games' else ('OT_ONE', 'OT_TWO')
            if len(outcomes) != 2 or set(types) != set(expected) or offer.get('betOfferType', {}).get('id') != (6 if market == 'total_games' else 1):
                continue
            if any(o.get('status') != 'OPEN' or scaled(o.get('odds'), price=True) is None or str(o.get('betOfferId')) != str(offer['id']) or not utc(o.get('changedDate')) or utc(o['changedDate']) > stamp for o in outcomes):
                continue
            a,b = (types[t] for t in expected)
            if any(isinstance(o.get('line'), bool) or not isinstance(o.get('line'), int) for o in (a,b)):
                continue
            line, other = a['line']/1000, b['line']/1000
            if line % .5 or (market == 'total_games' and (line != other or not 10 <= line <= 45)):
                continue
            if market == 'game_handicap' and (line != -other or abs(line)>15 or a.get('participant') != e['homeName'] or b.get('participant') != e['awayName']):
                continue
            result.append(dict(event_id=str(e['id']), home=e['homeName'], away=e['awayName'], group=e['group'],
                               scheduled_start=e['start'], captured_at=stamp.isoformat(), market=market, line=line,
                               odds1=scaled(a['odds'], price=True), odds2=scaled(b['odds'], price=True),
                               bookmaker='Grosvenor', offer_id=str(offer['id']),
                               changed_at=max(o['changedDate'] for o in outcomes), main_line='MAIN_LINE' in offer.get('tags', []),
                               url=f"https://www.grosvenorcasinos.com/sport#event/{e['id']}", raw_event=e, raw_offer=offer))
    return result


def newest_receipt(root, clock):
    paths = sorted((root/'data/tennis-props/inbox').glob('bet365-tennis-market-audit-*.json.gz'), reverse=True)[:4]
    for path in paths:
        if path.stat().st_size > 32*1024*1024:
            continue
        data = json.loads(gzip.decompress(path.read_bytes()))
        stamp = utc(data.get('captured_at'))
        if stamp and stamp <= clock and clock-stamp <= timedelta(minutes=30):
            # Only latest poll: absent/suspended markets must not reappear from an older poll.
            return data.get('grosvenor_receipt') or {}, file_sha(path)
    return {}, None


def fresh_components(root, out, clock, registered):
    paths = list((root/'data/tennis-ml-research/components'/clock.strftime('%Y-%m-%d')).glob('*.json'))
    paths += list((out/'component-evidence').glob('*.json'))
    valid = []
    model_hash = file_sha(root/'scripts/oncourt-compute-fair-odds.py')
    for path in paths:
        if path.stat().st_size > 2*1024*1024:
            continue
        packet = read(path); stamp = utc(packet.get('captured_at'))
        if not stamp or not registered <= stamp <= clock or clock-stamp > timedelta(hours=2):
            continue
        if digest(packet.get('rows')) != packet.get('payload_sha256') or packet.get('model_file_sha256') != model_hash:
            raise ValueError('component checksum or model version mismatch')
        valid.append((stamp, packet))
    return max(valid, key=lambda x:x[0]) if valid else (None, None)


def probabilities(row, q, h, cfg, calibration):
    d = row['opportunity_diagnostics']; pa, pb = d['p_a_unrounded'], d['p_b_unrounded']
    p = row['p1_win_prob']; raw = joint(pa,pb)
    kernels = {'raw':raw, 'C0':tilt(raw,p,0), 'T1':tilt(raw,p)}
    index = 2 if q['market'] == 'total_games' else 1
    result = {a:contract(marginal(k,index),q['market'],q['line']) for a,k in kernels.items()}
    if q['market'] == 'total_games':
        # Exactly the existing totals line-space transformation; do not stack onto T1.
        result['current'] = contract(marginal(raw,2),q['market'],q['line'] + d['ou_shift'] - d['tournament_residual_adjustment'])
    else:
        # Existing handicap uses the saved rounded solved pair and its calibration/guard.
        first,second,push = h._shape_cover_probabilities(row['p_a'],row['p_b'],q['line'],'bo3')
        a,b = h._calibrate_prob(first,cfg),h._calibrate_prob(second,cfg)
        current,reason = h.apply_correction(cfg.payload,base_prob=a/(a+b),surface=row['surface'],line=q['line'],
                                            p1_match_prob=p,odds1=q['odds1'],odds2=q['odds2'],league='ATP',best_of='bo3')
        if not calibration['allow_sign_flip'] and ((first*q['odds1']<=1<current*q['odds1']) or (second*q['odds2']<=1<(1-current)*q['odds2'])):
            current = first
        result['current'] = (current*(1-push),push,(1-current)*(1-push))
    means = {a:math.fsum(k[2]*v for k,v in kernel.items()) for a,kernel in kernels.items()}
    means['current'] = d['final_expected_games_unrounded']
    for values in result.values():
        if abs(sum(values)-1)>1e-8 or any(not math.isfinite(x) or x<0 for x in values):
            raise ValueError('invalid contract probabilities')
    invariant = abs(math.fsum(v for k,v in kernels['T1'].items() if k[0])-p)
    if invariant>1e-12:
        raise ValueError('T1 changed match winner probability')
    return result,means,invariant


def decision(probs,q,protocol):
    win,push,loss = probs
    pairs = [(win,push,loss,q['odds1']), (loss,push,win,q['odds2'])]
    side = max(range(2),key=lambda i:pairs[i][0]*pairs[i][3]+push-1)
    w,_,_,odds = pairs[side]
    conditional = w/(1-push)
    market = (1/odds)/(1/q['odds1']+1/q['odds2'])
    ev = w*odds+push-1
    return dict(side=side+1,odds=odds,fair_odds=(1-push)/w if w else None,probability=conditional,
                win_probability=w,push_probability=push,ev_pct=100*ev,edge_pct=100*(conditional-market),
                selected=ev+1e-12>=protocol['minimum_ev'] and conditional-market+1e-12>=protocol['minimum_probability_edge'])


def capture(root, clock, receipt=None):
    out=root/RELATIVE; reg=read(out/'registration.json'); effective=utc(reg['registered_at'])
    if reg['fingerprints'] != fingerprints(root):
        raise ValueError('frozen implementation changed; manual review required')
    h,cfg,calibration=settings(root)
    if calibration != reg['current_handicap_settings']:
        raise ValueError('current handicap settings changed; separate cohort required')
    stamp,packet=fresh_components(root,out,clock,effective)
    if receipt is None:
        receipt,receipt_hash=newest_receipt(root,clock)
    else:
        receipt_hash=digest(receipt)
    quotes=[q for q in parse_receipt(receipt,clock) if utc(q['captured_at'])>=effective]
    reasons=Counter(); mapped=[]
    if not packet:
        return dict(state='WAITING_FOR_FRESH_MODEL_INPUTS',checked_at=clock.isoformat(),fresh_quotes=len(quotes),captured=0)
    idx=identity_index(root)
    rows=defaultdict(list)
    for row in packet['rows']:
        if row.get('best_of')==3 and row.get('model_policy')=='category_corrected' and row.get('official_category') in ('ATP250','ATP500','Masters 1000','Grand Slam'):
            rows[fixture_key(row)].append(row)
    known=game_index(root,set(rows))
    for q in quotes:
        try:
            ident=map_quote(q,idx)
            key='|'.join([str(ident['edition_id']),str(ident['round_id'])]+sorted([str(ident['p1_id']),str(ident['p2_id'])]))
            if len(rows[key])!=1:raise ValueError('missing_or_ambiguous_forecast')
            row=rows[key][0]
            if known[key]:raise ValueError('result_already_known')
            if stamp>=utc(q['scheduled_start']):raise ValueError('forecast_after_scheduled_start')
            if str(row['player1_id'])!=str(ident['p1_id']):
                if q['market']=='game_handicap':q={**q,'line':-q['line'],'odds1':q['odds2'],'odds2':q['odds1']}
            q={**q,'home':row['player1'],'away':row['player2'],'native_identity':ident}
            mapped.append((key,row,q))
        except (ValueError,KeyError,TypeError) as exc:
            reasons[str(exc)]+=1
    groups=defaultdict(list)
    for key,row,q in mapped:groups[(key,q['market'])].append((row,q))
    for (key,market),candidates in sorted(groups.items()):
        path=out/'captures'/(digest([key,market])+'.json')
        if path.exists():reasons['already_recorded']+=1;continue
        # No EV-based line shopping: identical main/central contract for all arms.
        row,q=min(candidates,key=lambda rq:(not rq[1]['main_line'],abs((1/rq[1]['odds1'])/(1/rq[1]['odds1']+1/rq[1]['odds2'])-.5),rq[1]['line'],rq[1]['offer_id']))
        probs,means,error=probabilities(row,q,h,cfg,calibration)
        record=dict(id=digest([key,market]),fixture_key=key,market=market,quote=q,components=row,
                    captured_at=clock.isoformat(),forecast_generated_at=stamp.isoformat(),
                    component_sha256=packet['payload_sha256'],raw_receipt_sha256=receipt_hash,
                    registration_sha256=file_sha(out/'registration.json'),probabilities=probs,means=means,
                    selections={a:decision(probs[a],q,reg['protocol']) for a in ARMS},actual_stake=0,
                    preserved_match_probability=row['p1_win_prob'],winner_mass_error=error)
        immutable(path,record);reasons['captured']+=1
    if reasons['captured']:
        immutable_path=out/'quote-evidence'/(receipt_hash+'.json')
        if not immutable_path.exists():immutable(immutable_path,receipt)
    return dict(state='CAPTURED' if reasons['captured'] else 'NO_NEW_ELIGIBLE_CONTRACTS',checked_at=clock.isoformat(),
                fresh_quotes=len(quotes),mapped_quotes=len(mapped),counts=dict(reasons),captured=reasons['captured'],forecast_at=stamp.isoformat())


def outcome(record,games,clock,reg_hash):
    q=record['quote'];start=utc(q['scheduled_start']);capture_at=utc(record['captured_at'])
    if record['registration_sha256']!=reg_hash or not capture_at<start or record['actual_stake']!=0:
        return dict(status='quarantined',reason='capture_integrity')
    if start>clock or not games:return dict(status='pending')
    unique={(g['winner_id'],g['loser_id'],g['date'],g['result']) for g in games}
    if len(unique)!=1:return dict(status='quarantined',reason='conflicting_result')
    winner,loser,day,score=next(iter(unique));d=datetime.fromisoformat(day[:10]).date()
    if d>clock.date() or d<capture_at.date() or abs((d-start.date()).days)>1:
        return dict(status='quarantined',reason='result_timing')
    parsed=complete_score(score)
    if not parsed:return dict(status='excluded',reason='unfinished_or_unsupported_score',score=score,result_date=day)
    margin,total=parsed
    if str(winner)!=str(record['components']['player1_id']):margin=-margin
    delta=total-q['line'] if record['market']=='total_games' else margin+q['line']
    return dict(status='settled',score=score,result_date=day,total_games=total,margin=margin,
                side1_outcome=0 if abs(delta)<1e-9 else 1 if delta>0 else -1)


def summarize(root,clock=None):
    clock=clock or datetime.now(timezone.utc);out=root/RELATIVE;reg=read(out/'registration.json')
    if not reg:return {}
    records=[read(p) for p in sorted((out/'captures').glob('*.json'))]
    games=game_index(root,{r['fixture_key'] for r in records}) if records else {}
    outcomes={r['id']:outcome(r,games.get(r['fixture_key'],[]),clock,file_sha(out/'registration.json')) for r in records}
    old=read(out/'outcomes.json')
    if old and old!=outcomes:
        path=out/'outcome-history'/(digest(old)+'.json')
        if not path.exists():immutable(path,old)
    atomic(out/'outcomes.json',outcomes)
    arms={};display=[]
    for r in records:
        o=outcomes[r['id']];q=r['quote'];c=r['components'];sels={}
        for a in ARMS:
            s=r['selections'][a];y=o.get('side1_outcome');profit=None
            if o['status']=='settled' and s['selected']:
                profit=0 if y==0 else s['odds']-1 if y==(1 if s['side']==1 else -1) else -1
            sels[a]={**s,'profit':profit}
        display.append(dict(id=r['id'],fixture_key=r['fixture_key'],players=[c['player1'],c['player2']],tournament=c['tour_name'],
                            surface=c['surface'],qualifying=int(c['round_id'])<4,start=q['scheduled_start'],market=r['market'],line=q['line'],
                            bookmaker=q['bookmaker'],odds=[q['odds1'],q['odds2']],captured_at=r['captured_at'],
                            price_observed_at=q['captured_at'],price_changed_at=q['changed_at'],means=r['means'],arms=sels,**o))
    for a in ARMS:
        arms[a]={}
        for market in ('all','total_games','game_handicap'):
            rows=[r for r in display if market=='all' or r['market']==market]
            bets=[r for r in rows if r['arms'][a]['selected']]
            settled=[r for r in bets if r['status']=='settled']
            profit=math.fsum(r['arms'][a]['profit'] for r in settled)
            counts=Counter(r['status'] for r in bets)
            samples=[];market_samples=[]
            for r in rows:
                if r['status']!='settled' or r['side1_outcome']==0:continue
                s=r['arms'][a];p=s['probability'] if s['side']==1 else 1-s['probability'];y=int(r['side1_outcome']==1)
                samples.append((p,y));market_samples.append(((1/r['odds'][0])/(1/r['odds'][0]+1/r['odds'][1]),y))
            def scores(samples):
                n=len(samples)
                return dict(n=n,brier=math.fsum((p-y)**2 for p,y in samples)/n if n else None,
                            log_loss=math.fsum(-math.log(max(1e-12,p if y else 1-p)) for p,y in samples)/n if n else None,
                            mean_probability=math.fsum(p for p,y in samples)/n if n else None,observed_rate=sum(y for p,y in samples)/n if n else None)
            arms[a][market]=dict(settled=len(settled),wins=sum(r['arms'][a]['profit']>0 for r in settled),losses=sum(r['arms'][a]['profit']<0 for r in settled),
                                pushes=sum(r['arms'][a]['profit']==0 for r in settled),pending=counts['pending'],excluded=counts['excluded'],quarantined=counts['quarantined'],
                                overdue=sum(r['status']=='pending' and clock-utc(r['start'])>timedelta(hours=48) for r in bets),
                                stake=len(settled),profit=profit,roi_pct=100*profit/len(settled) if settled else None,
                                calibration=scores(samples),market_calibration=scores(market_samples))
    settled_fixtures={r['fixture_key'] for r in display if r['status']=='settled'}
    # One mean error per fixture, regardless of how many markets were captured.
    unique={r['fixture_key']:r for r in display if r['status']=='settled'}
    length={a:dict(n=len(unique),bias=math.fsum(r['means'][a]-r['total_games'] for r in unique.values())/len(unique) if unique else None,
                   mae=math.fsum(abs(r['means'][a]-r['total_games']) for r in unique.values())/len(unique) if unique else None) for a in ARMS}
    report=dict(name='Match Shape',version=reg['protocol']['version'],updated_at=clock.isoformat(),registered_at=reg['registered_at'],
                capture=read(out/'capture-status.json'),protocol=reg['protocol'],actual_stake=0,historical_replay_included=False,
                fixtures=len({r['fixture_key'] for r in display}),contracts=len(display),settled_fixtures=len(settled_fixtures),
                arms=arms,length=length,records=sorted(display,key=lambda r:(r['start'],r['id']),reverse=True),
                statuses=dict(Counter(r['status'] for r in display)),review_milestones_reached=[n for n in (50,100) if len(settled_fixtures)>=n],
                limitations=['Same-fixture markets are correlated; combined ROI is descriptive.',
                             'Fresh observed offer, not verified closing price or execution.',
                             'Current pricing is replayed on the same contract, not the original Strict signal ledger.',
                             'T1 replaces legacy distribution corrections; raw and C0 controls isolate the tilt.',
                             'Grosvenor bounded shared polling; not guaranteed full ATP or bookmaker coverage.',
                             'Unfinished/ambiguous grading remains explicit and excluded; no bookmaker settlement claim.'])
    atomic(out/'report.json',report)
    return report


def refresh(root,clock=None,receipt=None,settle_only=False):
    clock=clock or datetime.now(timezone.utc);out=root/RELATIVE
    if not (out/'registration.json').exists():return {}
    with locked(out):
        if not settle_only:
            try:health=capture(root,clock,receipt)
            except Exception as exc:health=dict(state='BLOCKED',checked_at=clock.isoformat(),reason=str(exc),captured=0)
            atomic(out/'capture-status.json',health)
        return summarize(root,clock)


from match_shape_reporting import weekly_text


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=CODE);ap.add_argument('--register',action='store_true');ap.add_argument('--settle-only',action='store_true');args=ap.parse_args()
    if args.register:register(args.root)
    print(weekly_text(refresh(args.root,settle_only=args.settle_only)))
