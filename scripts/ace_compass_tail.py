"""Forward-only mean-preserving dispersion comparison within Ace Compass."""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from fractions import Fraction
from pathlib import Path

from scipy.stats import nbinom
import ace_compass_engine as engine

LABELS = {'adjusted': 'Frozen dispersion', 'candidate': 'Compass', 'control': 'Control'}
POLICY_FILE = 'forward-policy.json'
PAIR_FILE = 'dispersion-observations.jsonl'
GRADE_FILE = 'dispersion-outcomes.json'


def dt(value):
    time = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not time.tzinfo:
        raise ValueError('Timezone missing')
    return time


def price_key(q, raw=False):
    def participant(key):
        return engine.norm(q[key] if raw else q.get('capture_'+key) or q[key])
    return (q['event_id'], q['bookmaker'], participant('player'), participant('opponent'),
            float(q['line']), dt(q['capture_ts']), dt(q['match_start_utc']))


def contract_key(q):
    return (q['bookmaker'], engine.norm(q['player']), engine.norm(q['opponent']),
            q['date'], engine.norm(q['tournament']), float(q['line']), dt(q['match_start_utc']))


def same_price(a, b):
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=.0000501)


def validate_raw(row):
    """Return compact evidence only after the original selection and price agree."""
    market = json.loads(row['raw_market_json'])
    label = row['raw_market_name']
    line, odds = float(row['line']), float(row['over_odds'])
    if market['name'] != label:
        raise ValueError('market_label')
    if row['bookmaker'] == 'Bet365' and label == 'Player Aces' and market.get('source') == 'moviodds_bet365':
        fid, gid = str(market['source_event_id']), '130440'
        group = market['raw_group_status']
        if market['source_group_id'] != gid or any(group.get(k) for k in ('stale','removed','suspended')):
            raise ValueError('inactive_group')
        if row['event_id'].startswith('bet365:') and row['event_id'].split(':')[1] != fid:
            raise ValueError('source_event')
        player = engine.norm(row['player'])
        candidates = [v for v in market['odds'] if engine.norm(v['label']) == player and float(v['hdp']) == line]
        if len(candidates) != 1:
            raise ValueError('named_selection')
        offer = candidates[0]
        q = offer['raw_quote']
        k = int(line + .5)
        if (q['line'] != f'{k}+' or engine.norm(q['side']) != player
                or str(q['fixture_id']) != fid or str(q['group_id']) != gid or str(q['market_id']) != gid
                or q['group_name'] != 'Ace Totals' or not str(q['sel_id']).isdigit() or int(q['sel_id']) <= 0
                or any(q.get(field) for field in ('stale','removed','suspended'))
                or not same_price(1 + Fraction(q['odds_frac']), q['odds_dec'])
                or not same_price(q['odds_dec'], offer['over']) or not same_price(offer['over'], odds)):
            raise ValueError('milestone_or_price')
        polled = dt(group['polled_at'])
        if (dt(q['ts']) > polled or polled >= dt(row['match_start_utc'])
                or abs((polled-dt(row['capture_ts'])).total_seconds()) > 600):
            raise ValueError('poll_time')
        return dict(kind='named_milestone', event=fid, selection=str(q['sel_id']), literal=q['line'],
                    source_at=q['ts'], polled_at=group['polled_at'], fraction=q['odds_frac'])
    if label not in ('Team Total (Aces) Home', 'Team Total (Aces) Away') or not row.get('under_odds'):
        raise ValueError('unverified_player_market')
    offers = [v for v in market['odds'] if float(v['hdp']) == line]
    if len(offers) != 1 or not same_price(offers[0]['over'],odds) or not same_price(offers[0]['under'],row['under_odds']):
        raise ValueError('two_way_price')
    return dict(kind='side_total', side=label.split()[-1], source_at=market.get('updatedAt'),
                under=float(row['under_odds']))


def proofs(root, quotes):
    days = {dt(q['capture_ts']).date().isoformat() for q in quotes}
    wanted = {price_key(q) for q in quotes}
    result, rejected = {}, set()
    selection_map, ladders = defaultdict(list), defaultdict(list)
    for day in sorted(days):
        for prefix in ('bet365-lines-', 'tennis-props-lines-'):
            path = root/'data/tennis-props/inbox'/(prefix+day+'.csv')
            if not path.exists():
                continue
            with path.open(encoding='utf-8-sig', newline='') as stream:
                for row in csv.DictReader(stream):
                    if row.get('market') != 'aces' or not row.get('over_odds'):
                        continue
                    try:
                        key = price_key(row, raw=True)
                    except (KeyError, ValueError, TypeError):
                        continue
                    if key not in wanted:
                        continue
                    try:
                        proof = validate_raw(row)
                        proof['odds'] = float(row['over_odds'])
                        if key in result and result[key] != proof:
                            raise ValueError('conflicting_raw_records')
                        result[key] = proof
                        if proof['kind'] == 'named_milestone':
                            selection_map[proof['event'],proof['selection']].append(key)
                            ladders[proof['event'],key[2],proof['polled_at']].append(key)
                    except (KeyError, ValueError, TypeError, ZeroDivisionError):
                        rejected.add(key)
    for keys in selection_map.values():
        if len({(k[2],k[4]) for k in keys}) != 1:
            rejected.update(keys)
    for keys in ladders.values():
        ordered = sorted(set(keys), key=lambda k:k[4])
        if any(result[a]['odds'] > result[b]['odds']+.00005 for a,b in zip(ordered,ordered[1:])):
            rejected.update(keys)
    return {k:v for k,v in result.items() if k not in rejected}


def forecasts(parent, line, odds, policy):
    mu = parent['candidate']['mean']
    size = 1 / max(policy['min_alpha'], min(policy['max_alpha'],
                    math.exp(policy['a'] + policy['b'] * math.log(mu/5))))
    probability = float(nbinom.sf(math.floor(line), size, size/(size+mu)))
    arms = {}
    for arm in LABELS:
        p = probability if arm == 'adjusted' else parent[arm]['p_win']
        ev = p*odds-1
        arms[arm] = dict(mean=mu if arm == 'adjusted' else parent[arm]['mean'],
                         p_win=p, ev=ev, selected=ev >= policy['minimum_ev']-1e-12)
    return arms


def capture(core,root,folder,parents,pairs,comparison,now,policy):
    reasons = Counter()
    quotes = engine.read(comparison) if comparison and comparison.is_file() else []
    fresh = [q for q in quotes if not core.eligible(q,now) and q.get('scope')=='player'
             and dt(q['capture_ts']) >= dt(policy['start'])]
    evidence = proofs(root,fresh)
    parents_by_key = defaultdict(list)
    for p in parents:
        parents_by_key[contract_key(p['row'])].append(p)
    seen = {r['id'] for r in pairs}
    native = engine.read(root/'data/oncourt/today_atp.csv') if fresh else []
    policy_hash = core.digest(policy)
    for q in sorted(fresh,key=lambda q:dt(q['capture_ts'])):
        matches = parents_by_key.get(contract_key(q),[])
        if len(matches) != 1:
            reasons['missing_or_ambiguous_parent'] += 1
            continue
        p = matches[0]
        if p['id'] in seen:
            reasons['already_recorded'] += 1
            continue
        n = p['native']
        rid, error = core.native_round(dict(tour_id=n['tid'],player_id=n['pid'],opponent_id=n['opp'],date=q['date']),native)
        if error or rid != n['round'] or p['id'] != core.digest([p['fixture_key'],n['pid'],engine.norm(q['bookmaker']),float(q['line'])]):
            reasons['native_fixture_unconfirmed'] += 1
            continue
        proof = evidence.get(price_key(q))
        if not proof or not same_price(proof['odds'],q['over_odds']) or ('under' in proof and not same_price(proof['under'],q['under_odds'])):
            reasons['raw_contract_unverified'] += 1
            continue
        recorded = datetime.now(now.tzinfo)
        if dt(q['match_start_utc']) <= recorded or dt(p['registered_at']) > recorded:
            reasons['timing'] += 1
            continue
        row = dict(id=p['id'],fixture_key=p['fixture_key'],native=n,row=q,registered_at=recorded.isoformat(),
                   parent_hash=p['hash'],parent_registered_at=p['registered_at'],input_hash=p['input_hash'],
                   policy_hash=policy_hash,proof=proof,primary=proof['kind']=='named_milestone' and float(q['line'])>=9.5,
                   **forecasts(p,float(q['line']),float(q['over_odds']),policy))
        core.append(folder/PAIR_FILE,pairs,row)
        seen.add(p['id'])
        reasons['captured'] += 1
    return dict(state='CAPTURED' if reasons['captured'] else 'NO_NEW_VERIFIED_QUOTES',checked_at=now.isoformat(),
                comparison_rows=len(quotes),fresh_player_offers=len(fresh),reasons=dict(reasons),added=reasons['captured'])


def stats(rows, outcomes):
    settled = [r for r in rows if outcomes.get(r['id'],{}).get('status')=='settled']
    report = dict(quotes=len(rows),fixtures=len({r['fixture_key'] for r in rows}),graded=len(settled),
                  settled_fixtures=len({r['fixture_key'] for r in settled}),arms={})
    for arm in LABELS:
        picked = [r for r in rows if r[arm]['selected']]
        selected = [r for r in settled if r[arm]['selected']]
        scores, entries = [], []
        wins = 0
        for r in settled:
            win = outcomes[r['id']]['actual'] > float(r['row']['line'])
            p = r[arm]['p_win']
            clipped = min(1-1e-12,max(1e-12,p))
            scores.append(((p-win)**2, -math.log(clipped if win else 1-clipped), p, win))
            if r[arm]['selected']:
                wins += win
                entries.append((r['id'],r['row']['match_start_utc'],float(r['row']['over_odds'])-1 if win else -1))
        stake = len(selected)
        pnl = sum(e[2] for e in entries)
        avg = lambda i: sum(s[i] for s in scores)/len(scores) if scores else None
        report['arms'][arm] = dict(bets=len(picked),passes=len(rows)-len(picked),wins=wins,losses=stake-wins,
            pending=sum(r['id'] not in outcomes for r in picked),void=sum(outcomes.get(r['id'],{}).get('status')=='void' for r in picked),
            settled=stake,stake_units=stake,pnl_units=pnl,roi_pct=100*pnl/stake if stake else None,
            brier=avg(0),log_loss=avg(1),expected_hit_rate=avg(2),observed_hit_rate=avg(3))
    return report


def update(core,root,folder,parents,comparison,now,capture_enabled):
    policy = core.readj(folder/POLICY_FILE,None)
    if policy is None:
        raise ValueError('Missing Ace Compass dispersion policy')
    pairs = core.ledger(folder/PAIR_FILE)
    grades = core.readj(folder/GRADE_FILE,{})
    status = core.readj(folder/'dispersion-capture-status.json',dict(state='AWAITING_FIRST_CAPTURE'))
    if capture_enabled:
        status = capture(core,root,folder,parents,pairs,comparison,now,policy)
        core.atomic(folder/'dispersion-capture-status.json',status)
    core.settle(root,pairs,grades,now)
    core.atomic(folder/GRADE_FILE,grades)
    return dict(id=policy['id'],start=policy['start'],capture=status,
                all=stats(pairs,grades),primary=stats([r for r in pairs if r['primary']],grades))
