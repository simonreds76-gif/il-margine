#!/usr/bin/env python3
"""Register and settle fixed opponent-shots shadow selections using existing archives.

No API calls and no fitting. Every execution may register only future fixtures
with fresh paired prices. Historical replay never writes this ledger.
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import sys

from team_shots_opponent import ROOT, key, read_base, history_before, mean_for
from football_counts import prob_over
from football_market import blend_logit, proportional_devig

def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

V = module('opponent_vnext', 'publish-football-vnext-shadow.py')
PUB = V.PUB
CLV = module('opponent_clv', 'team-shots-v1-clv-monitor.py')
SETTLE = module('opponent_settle', 'settle-football-research-lanes.py')
CONFIG = ROOT/'data/team-shots/team-shots-opponent-config.json'
FORM = ROOT/'data/football-form'
LEDGER = FORM/'team-shots-opponent-shadow.csv'
CANDIDATES = FORM/'team-shots-opponent-candidates.csv'
STATUS = FORM/'team-shots-opponent-status.json'
PAIR_FIELDS = ('league_slug','home_team','away_team','team','line_label','bookmaker')

def fresh_prices(rows, config, now):
    kept, rejected = [], Counter()
    for row in rows:
        capture, kickoff = PUB.parse_dt(row.get('captured_at')), PUB.parse_dt(row.get('kickoff_at'))
        if not capture or not kickoff:
            rejected['missing_timestamp'] += 1
        elif kickoff <= now:
            continue
        elif capture > now or capture >= kickoff:
            rejected['future_or_inplay_price'] += 1
        elif (now-capture).total_seconds() > config['max_price_age_hours']*3600:
            rejected['stale_price'] += 1
        elif (kickoff-now).total_seconds() > config['max_kickoff_hours']*3600:
            rejected['outside_capture_window'] += 1
        else:
            kept.append(row)
    return kept, rejected

def score_pairs(pairs, base, config, histories=None):
    candidates, rejected = [], Counter()
    histories = {} if histories is None else histories
    for pair in pairs:
        over, under = pair['over'], pair['under']
        league, home, away, team = over['league_slug'], key(over['home_team']), key(over['away_team']), key(over['team'])
        if league not in config['allowed_leagues']:
            rejected['league_not_registered'] += 1
            continue
        if team not in (home, away) or home == away:
            rejected['team_identity_mismatch'] += 1
            continue
        line = PUB.pf(over['line_label'])
        # Frozen replay is for half-lines: pushes need a separate price model.
        if line is None or line < 0 or abs(line % 1 - .5) > 1e-8:
            rejected['unsupported_line'] += 1
            continue
        day = min(over['captured_at_dt'], under['captured_at_dt']).date().isoformat()
        if day not in histories:
            histories[day] = history_before(base, day)
        history = histories[day]
        fixture = dict(date=over['kickoff'].date().isoformat(),league=league,home=home,away=away)
        sample = history.features(fixture,'shots','home' if team == home else 'away',day)
        if sample is None:
            rejected['fewer_than_six_prior_matches'] += 1
            continue
        model = config['parameters']
        mu = mean_for(model,sample)
        raw = prob_over(line,mu,distribution='negative_binomial',alpha=model['alpha'])
        market = proportional_devig(over['odds'],under['odds'])[0]
        probability = blend_logit(raw,market,config['calibrator']['weight'])
        if config['calibrator']['intercept'] != 0:
            raise ValueError('Unregistered calibration intercept')
        for side, source, p, raw_p, market_p in [('over',over,probability,raw,market),('under',under,1-probability,1-raw,1-market)]:
            edge = p*source['odds']-1
            blocked = 'edge_below_3pct' if edge < config['minimum_edge'] else ''
            row = V.candidate_row(model=config['model'],source=source,team=source['team'],side=side,probability=p,raw_probability=raw_p,market_probability=market_p,edge=edge,matchday=0,team_neff=len(history.teams[(league,team)]),opponent_neff=len(history.teams[(league,away if team == home else home)]),model_mean=mu,distribution_parameter=model['alpha'],status='blocked' if blocked else 'eligible',blocked_reason=blocked)
            row.update(model_input_version=config['model_version'],feature_asof=day,stake_units=1,real_stake_units=0)
            # Canonical identity must survive display-name changes between scans.
            row['match_id'] = '|'.join([fixture['date'],league,home,away])
            row['pick_id'] = '|'.join([config['model'],row['match_id'],team,side,str(line)])
            candidates.append(row)
    return candidates, rejected

def register(existing, candidates, config, now):
    if config['status'] != 'ACTIVE_SHADOW' or now < PUB.parse_dt(config['activated_at']):
        return list(existing)
    fresh = V.cap_signals([r for r in candidates if not r['blocked_reason'] and PUB.parse_dt(r['kickoff_utc']) > now])
    V.stamp_publications(existing,fresh,now)
    return V.merge_shadow_ledger(existing,fresh)

def track(ledger, odds, config):
    index = CLV.build_odds_index(odds)
    output = []
    for original in ledger:
        tracked = CLV.build_pick_row(original,index,allow_canonical_only=False,allowed_leagues=set(config['allowed_leagues']),config_valid=True,config_error='')
        # Keep first published terms and all provenance; CLV adds only observations.
        row = {**original,**tracked}
        row['book_price_at_publication'] = original.get('book_price_at_publication') or original['book_odds']
        output.append(row)
    results,freshness,_,_ = SETTLE.load_results_snapshot(None)
    results.update(SETTLE.load_manual_settlement_results(SETTLE.OVERRIDES_PATH))
    settled = SETTLE.settle_team_shots(output,results)
    return output,settled,freshness

def main():
    config = json.loads(CONFIG.read_text(encoding='utf8'))
    now = datetime.now(timezone.utc)
    odds = PUB.load_csv(PUB.DEFAULT_TEAM_ODDS)
    fresh,rejected = fresh_prices(odds,config,now)
    latest = PUB.latest_team_shots_odds(fresh,now)
    pairs = V.paired_rows(latest,PAIR_FIELDS)
    base = read_base(PUB.DEFAULT_TEAM_BASE) if pairs else []
    candidates, skipped = score_pairs(pairs,base,config)
    rejected.update(skipped)
    ledger = register(PUB.load_csv(LEDGER),candidates,config,now)
    ledger, settled, freshness = track(ledger,odds,config)
    SETTLE.write_csv(LEDGER,ledger,extras=V.FIELDS)
    SETTLE.write_csv(CANDIDATES,candidates,extras=V.FIELDS)
    done = [r for r in ledger if SETTLE.is_settled(r)]
    pnl = sum(float(r.get('pnl_units') or 0) for r in done)
    explanation = f'{len(pairs)} fresh paired contracts; {len(candidates)} sides scored. One fixed 1u hypothetical selection per fixture; real stake 0. '
    if rejected:
        explanation += 'Excluded archive rows: '+', '.join(f'{k}={v}' for k,v in sorted(rejected.items()))+'.'
    payload = dict(generated_at=PUB.fmt_dt(now),activated_at=config['activated_at'],status=config['status'],count_gate='FIXED CANDIDATE',market_gate='FORWARD COLLECTION ACTIVE',promotion_gate='BLOCKED',live_routing=False,prospective=dict(signals=len(ledger),settled=len(done),pending=len(ledger)-len(done),pnl_units=pnl,roi=pnl/len(done) if done else None),latest_scan=dict(scored_rows=len(candidates),scored_fixtures=len({r['match_id'] for r in candidates}),explanation=explanation),settled_this_run=settled,result_source=freshness,review_policy=config['review_policy'])
    closes = [float(r['published_to_close_clv']) for r in done if str(r.get('true_close')).lower() == 'true' and PUB.pf(r.get('published_to_close_clv')) is not None]
    age_days = (now-PUB.parse_dt(config['activated_at'])).days
    payload['prospective'].update(wins=sum(r['result']=='won' for r in done),losses=sum(r['result']=='lost' for r in done),true_close_count=len(closes),mean_clv=sum(closes)/len(closes) if closes else None)
    payload['review_status'] = 'MANUAL_REVIEW_DUE' if len(done)>=150 and age_days>=56 else 'COLLECTING_FIXED_POLICY'
    payload['age_days'] = age_days
    STATUS.write_text(json.dumps(payload,indent=2,default=str)+'\n',encoding='utf8')
    print(f"Opponent shots: {len(ledger)} registered, {len(done)} settled, {len(ledger)-len(done)} pending; {len(pairs)} paired markets")

if __name__ == '__main__':
    main()
