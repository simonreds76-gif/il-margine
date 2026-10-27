"""Sisal 50/50 v1. Append-only paper evidence; never sends alerts or prices live bets."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
import re
import runpy
import random
import unicodedata
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = Path('data/tennis-props/shadow/sisal-5050-v1')
BOARD = Path('data/tennis-props/shadow/aces-v3-projection-board.csv')
MODEL = Path('data/tennis-props/models/v3-atp-aces-live.txt')
GENERATOR = Path('scripts/tennis-props-v3-live.py')
ALPHA = 0.1800339589347608
CONFIG = dict(version='sisal-5050-v1', name='Sisal 50/50', bookmaker='Sisal IT',
              model_weight=0.5, alpha=ALPHA, min_ev=0.08, paper_stake=1, real_stake=0,
              min_lead_minutes=15, max_quote_age_hours=6, max_provider_age_hours=24,
              scope='ATP main tour, Hard/Clay, main draw and qualifying; half-point individual aces O/U',
              canonical='First eligible paired capture per exact fixture/player; closest market probability to 50%, then lower line',
              settlement='Sisal individual totals: completed counts, or already-determined overs after retirement; otherwise void',
              reviews=[50, 100], review_date='2026-11-30', bias_review_contracts=100, bias_review_aces=1,
              primary_metric='Paired log loss blend minus market, fixture-clustered interval, BO3/BO5 separately',
              alerts=False, alert_eligibility='Requires a separate explicit user decision; never enabled automatically', automatic_promotion=False)

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def stamp(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError):
        return None

def norm(value):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower())

def number(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None

def atomic(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf8') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

@contextmanager
def lock(folder):
    # OS-released advisory lock survives process crashes without a stale PID file.
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / '.writer.lock').open('a+b') as f:
        f.seek(0); f.write(b'0'); f.flush(); f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            f.seek(0)
            if os.name == 'nt':
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)

def ledger(path):
    rows, previous = [], ''
    for line in path.read_text(encoding='utf8').splitlines() if path.exists() else []:
        r = json.loads(line); own = r.pop('hash')
        if r.get('previous_hash') != previous or digest(r) != own:
            raise ValueError('ledger_integrity_failure')
        r['hash'] = own; rows.append(r); previous = own
    return rows

def append(path, rows, row):
    row = dict(row, previous_hash=rows[-1]['hash'] if rows else '')
    row['hash'] = digest(row)
    with path.open('a', encoding='utf8') as f:
        f.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n'); f.flush(); os.fsync(f.fileno())
    rows.append(row)

def over_probability(mean, line):
    # NB2: variance = mean + alpha * mean**2. Stable recurrence, no fitted calibration.
    r = 1 / ALPHA; p = r / (r + mean)
    mass = p ** r; cdf = mass
    for k in range(1, math.floor(line) + 1):
        mass *= (k - 1 + r) / k * (1 - p); cdf += mass
    return max(1e-12, min(1 - 1e-12, 1 - cdf))

def arms(mean, line, over, under):
    model = over_probability(mean, line)
    market = (1 / over) / (1 / over + 1 / under)
    result = {}
    for name, p in [('model', model), ('market', market), ('blend50', (model + market) / 2)]:
        ev_o, ev_u = p * over - 1, (1 - p) * under - 1
        side = 'over' if ev_o >= ev_u else 'under'
        ev, prob, odds = (ev_o, p, over) if side == 'over' else (ev_u, 1 - p, under)
        result[name] = dict(p_over=p, side=side, ev=ev, fair_odds=1/prob, odds=odds, selected=ev >= CONFIG['min_ev'])
    return result

def quote_reason(q, now, registered):
    if q.get('bookmaker') != 'Sisal IT' or q.get('tour') != 'ATP' or q.get('market') != 'aces':
        return 'out_of_scope'
    line, over, under = (number(q.get(k)) for k in ('line', 'over_odds', 'under_odds'))
    if None in (line, over, under) or line < 0 or line > 100 or line % 1 != .5 or min(over, under) <= 1:
        return 'invalid_or_unpaired_half_point_market'
    if not 1 <= 1/over + 1/under <= 1.5:
        return 'invalid_book_percentage'
    cap, start, provider = (stamp(q.get(k)) for k in ('capture_ts', 'match_start_utc', 'provider_updated_at'))
    if not cap or not start or not provider or cap < registered or cap > now or provider > cap:
        return 'unverified_or_pre_registration_timestamp'
    if (now-cap).total_seconds() > 6*3600 or (cap-provider).total_seconds() > 24*3600:
        return 'stale_quote'
    if (start-now).total_seconds() < 900:
        return 'started_or_less_than_15_minutes'
    if not q.get('source_url') or not q.get('raw_market_json'):
        return 'missing_price_provenance'
    try:
        raw = json.loads(q['raw_market_json'])
        if not re.fullmatch(r'Team Total \(Aces\) (Home|Away)', str(raw.get('name', '')), re.I):
            return 'unsupported_market_semantics'
        pairs = [v for v in raw.get('odds', []) if number(v.get('hdp')) == line
                 and number(v.get('over')) == over and number(v.get('under')) == under]
        if not pairs:
            return 'raw_pair_mismatch'
    except (ValueError, TypeError, AttributeError):
        return 'invalid_raw_market'
    return None

def raw_round(board, today):
    found = {r['round_id'] for r in today if r.get('tour_id') == board['tour_id']
             and {r.get('player1_id'), r.get('player2_id')} == {board['player_id'], board['opponent_id']}
             and r.get('date') in ('', board['date']) and not r.get('result') and not r.get('complete') and not r.get('live')}
    return next(iter(found)) if len(found) == 1 else None

def feature_reader(root):
    """Read the existing frozen generator; verify parity without writing its board."""
    import lightgbm as lgb
    import pandas as pd
    v = runpy.run_path(str(root/GENERATOR))
    paths = [root/'data/tennis-props'/n for n in ('player-props-baseline.csv','tour-surface-baselines.csv','player-name-aliases.csv')]
    baselines = v['baseline_index'](read_csv(paths[0])); surfaces = v['surface_index'](read_csv(paths[1]))
    names = v['baseline_names_by_tour'](baselines); aliases = v['load_aliases'](read_csv(paths[2]))
    model = lgb.Booster(model_file=str(root/MODEL))
    manifest = {str(p.relative_to(root)):sha(p) for p in paths}
    def evaluate(row):
        original = dict(row, projected_aces=row['incumbent_projected_aces'])
        f = v['build_feature_row'](original, baselines, surfaces, names, aliases)
        frame = pd.DataFrame([f])[model.feature_name()]
        frame['surface'] = pd.Categorical(frame['surface'],categories=(model.pandas_categorical or [['Clay','Grass','Hard']])[0])
        prediction = max(.01,float(model.predict(frame)[0]))
        if abs(prediction-float(row['projected_aces'])) > .00051:
            raise ValueError('board_input_parity_failed')
        return f, manifest
    return evaluate

def capture(root, folder, rows, quotes_path, now, reg, clock=None):
    reasons = Counter(); seen = {r['id'] for r in rows}; candidates = []
    if not quotes_path or not quotes_path.exists():
        return dict(state='PRICE_FILE_MISSING', checked_at=now.isoformat(), added=0)
    board_path = root/BOARD
    if not board_path.exists() or now.timestamp()-board_path.stat().st_mtime > 48*3600:
        return dict(state='BOARD_MISSING_OR_STALE', checked_at=now.isoformat(), added=0)
    board, today = read_csv(board_path), read_csv(root/'data/oncourt/today_atp.csv')
    tours = {r['id']: r for r in read_csv(root/'data/oncourt/tours_atp.csv')}
    for q in read_csv(quotes_path):
        reason = quote_reason(q, now, stamp(reg['registered_at']))
        if reason:
            reasons[reason] += 1; continue
        matches = [b for b in board if b.get('date') == q.get('date') and b.get('tour') == 'ATP'
                   and all(norm(b.get(k)) == norm(q.get(k)) for k in ('player', 'opponent', 'tournament'))]
        if len(matches) != 1:
            reasons['ambiguous_board_match'] += 1; continue
        b = matches[0]; t = tours.get(b.get('tour_id'), {})
        if t.get('rank') not in ('2', '3', '4') or 'challenger' in t.get('name', '').lower() or b.get('surface') not in ('Hard', 'Clay'):
            reasons['unsupported_tournament_or_surface'] += 1; continue
        if b.get('v3_eligible') != 'true' or b.get('v3_model') != 'all_tour_deployment_safe_atp_aces_v1':
            reasons['wrong_model_board'] += 1; continue
        cap = stamp(q['capture_ts'])
        history = b.get('history_as_of', ''); generation = b.get('generation_date', '')
        if not history or not generation or not history <= generation <= now.date().isoformat() or history >= cap.date().isoformat() or (now.date()-datetime.fromisoformat(history).date()).days > 2:
            reasons['invalid_or_stale_history_cutoff'] += 1; continue
        mu, points, games, alpha = (number(b.get(k)) for k in ('projected_aces','service_points_estimate','expected_match_games','aces_alpha'))
        if None in (mu, points, games, alpha) or min(mu, points, games) <= 0 or abs(alpha-ALPHA)>1e-6 or not b.get('history_fingerprint'):
            reasons['missing_or_incompatible_prediction_inputs'] += 1; continue
        rd = raw_round(b, today)
        if not rd or not rd.isdigit() or not 1 <= int(rd) <= 12:
            reasons['missing_exact_upcoming_fixture'] += 1; continue
        fk = ':'.join([b['tour_id'], rd, *sorted([b['player_id'], b['opponent_id']])])
        rid = digest([fk, b['player_id'], 'Sisal IT'])
        if rid in seen:
            reasons['already_registered'] += 1; continue
        a = arms(mu, float(q['line']), float(q['over_odds']), float(q['under_odds']))
        candidates.append(dict(id=rid, fixture_key=fk, registered_at=now.isoformat(), row=q, board=b,
            native=dict(tid=b['tour_id'], round=rd, pid=b['player_id'], opp=b['opponent_id']),
            best_of=5 if t['rank']=='4' and int(rd)>=4 else 3, phase='qualifying' if int(rd)<4 else 'main_draw',
            category=t['rank'], surface=b['surface'], mean=mu, alpha=ALPHA, expected_points=points,
            expected_games=games, length_source=b.get('expected_match_games_source'), arms=a))
    # Order is time first, then the canonical balanced line, never the most favourable EV.
    candidates.sort(key=lambda r:(r['row']['capture_ts'], abs(r['arms']['market']['p_over']-.5), float(r['row']['line'])))
    paths = [board_path, root/'data/oncourt/today_atp.csv', root/'data/oncourt/tours_atp.csv']
    manifest = {str(p.relative_to(root)): sha(p) for p in paths}
    added = 0
    excluded = []
    verified = []
    evaluate = feature_reader(root) if candidates else None
    for r in candidates:
        if r['id'] in seen:
            reasons['duplicate_or_noncanonical_line'] += 1; continue
        try:
            features, feature_manifest = evaluate(r['board'])
        except (ValueError, KeyError) as exc:
            reasons['input_parity_excluded'] += 1
            excluded.append(dict(id=r['id'],reason=str(exc),row=r['row'],board=r['board']))
            continue
        if int(features['best_of']) != r['best_of']:
            reasons['forecast_format_mismatch'] += 1; continue
        r['features'] = features
        r['input_manifest'] = dict(manifest, **feature_manifest); r['frozen_artifacts'] = reg['artifacts']
        verified.append(r); seen.add(r['id'])
    if verified:
        fingerprints=dict(verified[0]['input_manifest'], **reg['artifacts'])
        if any(sha(root/p)!=h for p,h in fingerprints.items()):
            raise ValueError('inputs_changed_during_capture')
    for r in verified:
        if (stamp(r['row']['match_start_utc'])-(clock() if clock else datetime.now(timezone.utc))).total_seconds()<900:
            reasons['started_during_input_verification'] += 1; continue
        append(folder/'observations.jsonl', rows, r); added += 1
    if excluded:
        atomic(folder/'exclusions'/f"{now.strftime('%Y%m%dT%H%M%S%f')}.json",excluded)
    return dict(state='CAPTURED' if added else 'NO_NEW_ELIGIBLE_QUOTES', checked_at=now.isoformat(),
                added=added, reasons=dict(reasons), source=str(quotes_path), registered_total=len(rows))

def count(value):
    n = number(value)
    return int(n) if n is not None and n >= 0 and n.is_integer() else None

def outcome(game, stat, record):
    text = game.get('result', '').upper()
    if any(s in text for s in ('W/O', 'WO')):
        return dict(status='void', completed=False, actual=None, actual_points=None, reason='walkover')
    p = 'w' if game['winner_id'] == record['native']['pid'] else 'l'
    actual = count(stat.get(p+'_ace')) if stat else None
    points = count(stat.get(p+'_svpt')) if stat else None
    if actual is not None and points is not None and (points <= 0 or actual > points):
        return None
    # Sisal's individual-total rule also covers disqualification during play.
    # DEF without counts does not prove a pre-match walkover; leave it pending.
    if any(s in text for s in ('RET', 'ABN', 'ABD', 'DEF', 'DQ', 'DISQ')):
        if actual is None:
            return None  # Missing counts cannot establish whether the total was already determined.
        if actual > float(record['row']['line']):
            return dict(status='settled', completed=False, actual=actual, actual_points=points, reason='sisal_total_already_determined')
        return dict(status='void', completed=False, actual=actual, actual_points=points, reason='sisal_undetermined_retirement')
    parts = re.findall(r'(\d+)-(\d+)(?:\(\d+\))?', text)
    if not parts or re.sub(r'\d+-\d+(?:\(\d+\))?|\s', '', text):
        return None
    sets = [(int(a), int(b)) for a,b in parts]
    target = (record['best_of']+1)//2
    if any(not ((max(a,b)==6 and min(a,b)<=4) or (max(a,b)>=7 and abs(a-b)==2) or {a,b}=={6,7}) for a,b in sets):
        return None
    if sum(a>b for a,b in sets)!=target or sum(b>a for a,b in sets)>=target or sets[-1][0]<=sets[-1][1] or actual is None:
        return None
    return dict(status='settled', completed=True, actual=actual, actual_points=points, reason='exact_completed_fixture')

def settle(root, rows, outcomes, now):
    pending = [r for r in rows if r['id'] not in outcomes and stamp(r['row']['match_start_utc']) < now]
    if not pending:
        return Counter()
    tids = {r['native']['tid'] for r in pending}; games, stats = defaultdict(dict), defaultdict(dict)
    def key(r):
        return (r['tour_id'], r['round_id'], tuple(sorted([r['winner_id'],r['loser_id']])))
    for filename, target in [('games_atp.csv', games), ('stat_atp.csv', stats)]:
        for r in read_csv(root/'data/oncourt'/filename):
            if r['tour_id'] in tids:
                target[key(r)][digest(r)] = r
    reasons = Counter()
    for r in pending:
        n = r['native']; k = (n['tid'], n['round'], tuple(sorted([n['pid'],n['opp']])))
        gs, ss = list(games[k].values()), list(stats[k].values())
        if len(gs)!=1 or len(ss)>1:
            reasons['missing_or_conflicting_exact_result']+=1; continue
        g = gs[0]
        if not r['registered_at'][:10] <= g['date'] <= now.date().isoformat():
            reasons['ambiguous_result_timing']+=1; continue
        s = ss[0] if ss else None
        if s and (s['winner_id'],s['loser_id']) != (g['winner_id'],g['loser_id']):
            reasons['stat_orientation_conflict']+=1; continue
        out = outcome(g,s,r)
        if out is None:
            reasons['unfinished_or_missing_valid_counts']+=1; continue
        outcomes[r['id']] = dict(out, settled_at=now.isoformat(), result_date=g['date'], source_hash=digest([g,s]), source_result=g, source_stat=s)
    return reasons

def summarize(rows, outcomes, reg, health, now, settlement_reasons):
    completed = [r for r in rows if outcomes.get(r['id'],{}).get('completed')]
    result = dict(model='Sisal 50/50', status='PAPER ONLY', generated_at=now.isoformat(), registered_at=reg['registered_at'],
                  capture=health, quotes=len(rows), completed_contracts=len(completed), independent_fixtures=len({r['fixture_key'] for r in completed}),
                  config=CONFIG, ledger_head=rows[-1]['hash'] if rows else None, settlement_reasons=dict(settlement_reasons), arms={}, selections=[], bias=[], format_results={})
    for name in ('model','market','blend50'):
        tally = Counter(); pnl = 0.; brier = []; logs = []
        for r in rows:
            a = r['arms'][name]; out = outcomes.get(r['id'],{}); status = out.get('status','pending'); profit=None
            if out.get('completed'):
                y = int(out['actual']>float(r['row']['line'])); p=a['p_over']
                brier.append((p-y)**2); logs.append(-(y*math.log(p)+(1-y)*math.log1p(-p)))
            if not a['selected']:
                continue
            if status=='settled':
                won = (out['actual']>float(r['row']['line'])) == (a['side']=='over')
                status='won' if won else 'lost'; profit=a['odds']-1 if won else -1.; pnl+=profit
                if not out.get('completed'):tally['retirement_settled']+=1
            tally[status]+=1
            if status=='pending' and (now-stamp(r['row']['match_start_utc'])).total_seconds()>48*3600:
                tally['overdue']+=1
            if name=='blend50':
                result['selections'].append(dict(id=r['id'],player=r['row']['player'],opponent=r['row']['opponent'],tournament=r['row']['tournament'],
                    start=r['row']['match_start_utc'],captured_at=r['row']['capture_ts'],line=float(r['row']['line']),side=a['side'],odds=a['odds'],fair=a['fair_odds'],ev=a['ev'],
                    status=status,profit=profit,actual=out.get('actual'),best_of=r['best_of'],fixture_key=r['fixture_key'],retirement_settled=out.get('status')=='settled' and not out.get('completed')))
        settled=tally['won']+tally['lost']
        result['arms'][name]=dict(wins=tally['won'],losses=tally['lost'],settled=settled,stake_units=settled,pnl_units=round(pnl,8),roi_pct=100*pnl/settled if settled else None,
            pending=tally['pending'],void=tally['void'],overdue=tally['overdue'],retirement_settled=tally['retirement_settled'],brier=sum(brier)/len(brier) if brier else None,log_loss=sum(logs)/len(logs) if logs else None)
    for label, rs in [('All',completed),('BO3',[r for r in completed if r['best_of']==3]),('BO5',[r for r in completed if r['best_of']==5])]:
        if not rs:
            continue
        actual=sum(outcomes[r['id']]['actual'] for r in rs); predicted=sum(r['mean'] for r in rs)
        with_points=[r for r in rs if outcomes[r['id']].get('actual_points')]
        opportunity=rate=0.
        for r in with_points:
            o=outcomes[r['id']]; mp=r['expected_points']; ap=o['actual_points']; mr=r['mean']/mp; ar=o['actual']/ap
            opportunity+=(mp-ap)*(mr+ar)/2; rate+=(mr-ar)*(mp+ap)/2
        result['bias'].append(dict(group=label,n=len(rs),predicted_mean=predicted/len(rs),actual_mean=actual/len(rs),bias_aces=(predicted-actual)/len(rs),
            diagnostic_n=len(with_points),opportunity_error=opportunity/len(with_points) if with_points else None,rate_error=rate/len(with_points) if with_points else None))
    for bo in (3,5):
        chosen=[s for s in result['selections'] if s['best_of']==bo]; settled=[s for s in chosen if s['status'] in ('won','lost')]
        profit=sum(s['profit'] for s in settled)
        result['format_results'][str(bo)]=dict(settled=len(settled),profit=profit,roi_pct=100*profit/len(settled) if settled else None,pending=sum(s['status']=='pending' for s in chosen))
    result['selection_count']=len(result['selections']);result['selections']=result['selections'][::-1] # Full record, never truncated.
    result['paired_log_loss']={}
    for group,rs in [('All',completed),('BO3',[r for r in completed if r['best_of']==3]),('BO5',[r for r in completed if r['best_of']==5])]:
        values=[]
        for r in rs:
            y=int(outcomes[r['id']]['actual']>float(r['row']['line']))
            losses={k:-(y*math.log(a['p_over'])+(1-y)*math.log1p(-a['p_over'])) for k,a in r['arms'].items()}
            values.append((r['fixture_key'],losses['blend50']-losses['market']))
        result['paired_log_loss'][group]=cluster_interval(values)
    chosen=[(s['fixture_key'],s['profit']*100) for s in result['selections'] if s['profit'] is not None]
    result['paper_roi_interval']=cluster_interval(chosen)
    result['bias_review_due']=any(b['n']>=100 and abs(b['bias_aces'])>1 for b in result['bias'])
    result['review_due']=result['independent_fixtures']>=50 or result['bias_review_due'] or now.date().isoformat()>=CONFIG['review_date']
    result['next_review_at']=next((n for n in CONFIG['reviews'] if result['independent_fixtures']<n),None)
    return result

def cluster_interval(values):
    """Fixed-seed fixture bootstrap; descriptive interval, not a sequential promotion test."""
    groups=defaultdict(list)
    for fixture,value in values:groups[fixture].append(value)
    point=sum(v for _,v in values)/len(values) if values else None
    summary=dict(n=len(values),fixtures=len(groups),mean=point,interval_95=None)
    if len(groups)<2:return summary
    clusters=[(sum(v),len(v)) for v in groups.values()];rng=random.Random(5050);estimates=[]
    for _ in range(1000):
        sample=rng.choices(clusters,k=len(clusters));estimates.append(sum(x[0] for x in sample)/sum(x[1] for x in sample))
    estimates.sort();summary['interval_95']=[estimates[24],estimates[974]]
    return summary

def run(root=ROOT, quotes=None, settle_only=False, now=None):
    now=now or datetime.now(timezone.utc); folder=root/REL
    with lock(folder):
        artifacts={str(p):sha(root/p) for p in (MODEL, GENERATOR)}
        reg=read_json(folder/'registration.json',None)
        if not reg:
            reg=dict(registered_at=now.isoformat(),config=CONFIG,artifacts=artifacts)
            atomic(folder/'registration.json',reg)
        rows=ledger(folder/'observations.jsonl');outcomes=read_json(folder/'outcomes.json',{})
        health=read_json(folder/'capture-status.json',dict(state='AWAITING_FIRST_CAPTURE'))
        if not settle_only:
            try:
                if reg['artifacts']!=artifacts or reg['config']!=CONFIG:
                    raise ValueError('frozen_model_or_policy_changed')
                health=capture(root,folder,rows,quotes,now,reg)
            except Exception as exc:
                health=dict(state='BLOCKED',checked_at=now.isoformat(),reason=str(exc),added=0)
            atomic(folder/'capture-status.json',health)
        reasons=settle(root,rows,outcomes,now);atomic(folder/'outcomes.json',outcomes)
        report=summarize(rows,outcomes,reg,health,now,reasons);atomic(folder/'report.json',report)
        from sisal_5050_reporting import weekly_text
        print(weekly_text(report))
        return 1 if health['state']=='BLOCKED' and not settle_only else 0

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--quotes',type=Path);p.add_argument('--settle-only',action='store_true');a=p.parse_args()
    raise SystemExit(run(a.root,a.quotes,a.settle_only))
