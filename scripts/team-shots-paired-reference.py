#!/usr/bin/env python3
"""Append first-quote forecasts from fixed models on identical future contracts.

Uses existing local archives only. No historical replay, API, fitting, real
stake, Telegram message or model promotion. Missing models remain explicit.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import team_shots_ema20_reference as OLD
import team_shots_ema20_features as FEATURES

spec = importlib.util.spec_from_file_location('paired_opponent', ROOT/'scripts/team-shots-opponent-shadow.py')
O = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = O
spec.loader.exec_module(O)
V, PUB = O.V, O.PUB
MODELS = ('ema20_v3', 'v4', 'opponent', 'shots_market_offset_v1')
CALIBRATION_PATH = ROOT/'data/team-shots/shots-market-offset-v1.json'
VERSION = 'paired-market-offset-20260930-v2'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

def model_fingerprint():
    # Normalize checkout line endings so Windows and Linux agree. Changing
    # weights, helpers or selection code requires a new registered experiment.
    names=['scripts/team-shots-paired-reference.py','scripts/team_shots_ema20_reference.py',
        'scripts/team_shots_ema20_features.py','scripts/publish-football-vnext-shadow.py',
        'scripts/publish-football-research-picks.py','scripts/build-football-form-layer.py',
        'scripts/backtest-football-form-layer.py','scripts/team_shots_opponent.py',
        'scripts/team-shots-opponent-shadow.py','scripts/football_counts.py','scripts/football_market.py',
        'scripts/football_team_names.py','data/team-shots/team-shots-v4-params.json',
        'data/team-shots/team-shots-v4-lock.json','data/team-shots/team-shots-opponent-config.json',
        'data/team-shots/shots-market-offset-v1.json']
    values={name:hashlib.sha256((ROOT/name).read_text(encoding='utf8').encode()).hexdigest() for name in names}
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()

def check_fingerprint(existing, fingerprint):
    if any(r.get('model_fingerprint')!=fingerprint for r in existing):
        raise ValueError('Comparison model code or weights changed; review and register a new cohort before collecting')

def calibrated_forecast(opponent, pair):
    if 'raw_p_over' not in opponent:
        return {'unavailable':'missing_opponent_raw_probability'}
    config = json.loads(CALIBRATION_PATH.read_text(encoding='utf8'))
    w, b = config['weight'], config['intercept']
    if (config['status'] != 'FROZEN_RESEARCH_ONLY' or config['real_stake_units'] != 0
        or config['automatic_promotion'] or not 0 <= w <= 1 or not -.5 <= b <= .5):
        raise ValueError('Invalid frozen research calibration')
    raw = opponent['raw_p_over']
    over, under = (float(pair[s]['odds']) for s in ('over','under'))
    if not 0 < raw < 1 or not all(math.isfinite(v) and v > 1 for v in (over,under)):
        return {'unavailable':'invalid_paired_probability'}
    market = (1/over)/(1/over+1/under)
    logit = lambda p: math.log(p/(1-p))
    z = logit(market)+b+w*(logit(raw)-logit(market))
    return dict(mean=opponent['mean'],alpha=opponent['alpha'],raw_p_over=raw,
        p_over=1/(1+math.exp(-z)),market_p_over=market,minimum_edge=config['minimum_edge'],
        calibration_sha256=digest(CALIBRATION_PATH),
        feature_inputs=opponent.get('feature_inputs'),count_model='opponent',real_stake_units=0)


def current_cohort(records):
    return [r for r in records if r.get('version') == VERSION]


def contract(row):
    kickoff = row.get('kickoff') or PUB.parse_dt(row.get('kickoff_utc'))
    return '|'.join([kickoff.isoformat(),row.get('league_slug') or row['league'],
        O.key(row['home_team']),O.key(row['away_team']),O.key(row['team']),
        str(float(row.get('line_label') or row['line'])),str(row['bookmaker']).lower()])

def prior_rows(base, cutoff):
    return [r for r in base if (d := PUB.parse_date(r.get('date'))) and d < cutoff]

def old_form(by_team, league, team, venue):
    history = by_team.get((league, PUB.team_key(team)), [])
    if not history:
        return None
    form = {'venue':venue, 'market_team_win_prob':'', 'market_opp_win_prob':''}
    form.update(FEATURES.summarize_window(history,10))
    form.update(FEATURES.summarize_ema_window(history))
    return form

def old_forecast(pair, base, by_team, alpha_cache):
    source = pair['over']
    league, team = source['league_slug'], source['team']
    home, away = source['home_team'], source['away_team']
    is_home = PUB.team_key(team)==PUB.team_key(home)
    own = old_form(by_team,league,team,'home' if is_home else 'away')
    opp = old_form(by_team,league,away if is_home else home,'away' if is_home else 'home')
    if own is None or opp is None:
        return {'unavailable':'missing_team_history'}
    mu = OLD.canonical_team_shots_ema20_lambda(own,opp,use_market=True)
    if mu is None:
        return {'unavailable':'fewer_than_six_prior_matches'}
    if league not in alpha_cache:
        values=[x for r in base if r['league']==league and (x:=PUB.pf(r.get('shots_for'))) is not None]
        alpha=OLD.estimate_alpha(values)
        if alpha<=0:
            alpha=OLD.estimate_alpha([x for r in base if (x:=PUB.pf(r.get('shots_for'))) is not None])
        alpha_cache[league]=alpha
    alpha=alpha_cache[league]
    p=OLD.negative_binomial_prob_over(float(source['line_label']),mu,alpha)
    return dict(mean=mu,alpha=alpha,p_over=p,minimum_edge=.05,
        feature_inputs={'team':own,'opponent':opp},market_strength='neutral_historical_live_path')

def compact(row, threshold, other=None):
    return dict(mean=float(row['model_mean']),alpha=float(row['distribution_parameter']),
        p_over=float(row['model_implied_prob']),raw_p_over=float(row['raw_model_probability']),
        minimum_edge=threshold,selection_blockers={s:r.get('blocked_reason','') for s,r in [('over',row),('under',other or row)]},
        input_version=row.get('model_input_version',''))

def score(pairs, raw_odds, base, opponent_base, config, params, lock, match_odds, now):
    by_day=defaultdict(list)
    for pair in pairs:
        # Conservative feature cutoff shared by every model, including v4.
        cutoff=min(pair[s]['captured_at_dt'] for s in ('over','under')).date()
        by_day[cutoff].append(pair)
    output=[]
    for cutoff, group in by_day.items():
        prior=prior_rows(base,cutoff)
        by_team,by_league=PUB.build_base_indexes(prior)
        prior=[r for rows in by_team.values() for r in rows]
        day_keys={contract(p['over']) for p in group}
        day_odds=[r for r in PUB.latest_team_shots_odds(raw_odds,now) if contract(r) in day_keys]
        # The current v4 path receives only rows available before this quote day.
        _,v4=V.score_team_shots(by_team=by_team,by_league=by_league,odds_rows=day_odds,
            params=params,lock=lock,now=now,match_odds_rows=match_odds)
        opponent,_=O.score_pairs(group,opponent_base,config)
        indices=[{(contract(r),r['side']):r for r in rows} for rows in (v4,opponent)]
        strength_index=V.match_strength_index(match_odds)
        opponent_history=O.history_before(opponent_base,cutoff.isoformat())
        alpha_cache={}
        for pair in group:
            source=pair['over']; cid=contract(source)
            forecasts={'ema20_v3':old_forecast(pair,prior,by_team,alpha_cache)}
            for model,index,threshold in zip(('v4','opponent'),indices,(float(lock['selection_rules']['minimum_edge']),config['minimum_edge'])):
                forecasts[model]=compact(index[(cid,'over')],threshold,index.get((cid,'under'))) if (cid,'over') in index else {'unavailable':'insufficient_registered_inputs'}
            is_home=PUB.team_key(source['team'])==PUB.team_key(source['home_team'])
            opponent_team=source['away_team'] if is_home else source['home_team']
            if 'p_over' in forecasts['v4']:
                forms=[]
                for team,opp,venue in [(source['team'],opponent_team,'home' if is_home else 'away'),(opponent_team,source['team'],'away' if is_home else 'home')]:
                    forms.append(PUB.live_form_row(by_team=by_team,by_league=by_league,league=source['league_slug'],
                        fixture_date=source['kickoff'].date(),team=team,opponent=opp,venue=venue,
                        home=source['home_team'],away=source['away_team']))
                strength=V.strength_at_quote(strength_index,min((pair['over'],pair['under']),key=lambda r:r['captured_at_dt']))
                forecasts['v4']['feature_inputs']=dict(forms=forms,market_strength=[PUB.fmt_dt(strength[0]),*strength[1:]] if strength else None)
            if 'p_over' in forecasts['opponent']:
                fixture=dict(date=source['kickoff'].date().isoformat(),league=source['league_slug'],home=O.key(source['home_team']),away=O.key(source['away_team']))
                forecasts['opponent']['feature_inputs']=opponent_history.features(fixture,'shots','home' if is_home else 'away',cutoff.isoformat())
            forecasts['shots_market_offset_v1']=calibrated_forecast(forecasts['opponent'],pair)
            for forecast in forecasts.values():
                if 'p_over' in forecast and not (math.isfinite(forecast['p_over']) and 0<forecast['p_over']<1 and math.isfinite(forecast['mean'])):
                    raise ValueError('Nonfinite or invalid model output')
            output.append(dict(contract_id=cid,registered_at_utc=PUB.fmt_dt(now),
                kickoff_utc=PUB.fmt_dt(source['kickoff']),match_date=source['kickoff'].date().isoformat(),
                league=source['league_slug'],home_team=source['home_team'],away_team=source['away_team'],
                team=source['team'],line=float(source['line_label']),bookmaker=source['bookmaker'],
                odds={s:float(pair[s]['odds']) for s in ('over','under')},
                captured_at_utc={s:PUB.fmt_dt(pair[s]['captured_at_dt']) for s in ('over','under')},
                feature_cutoff_exclusive=cutoff.isoformat(),models=forecasts,
                statshub={'status':'NOT_CAPTURED','reason':'No contemporaneous matching displayed forecast recorded'},
                version=VERSION,real_stake_units=0))
    return output

def fixture_key(row):
    return (row['match_date'],row['league'],O.key(row['home_team']),O.key(row['away_team']))

def select_first_scan(records, existing):
    """One hypothetical selection per model/fixture at its first observed scan.

    A no-bet decision is retained too. Later lines/prices cannot replace losses
    or turn an old no-bet into a selected winner.
    """
    seen={fixture_key(r) for r in existing}
    groups=defaultdict(list)
    for row in records:
        groups[fixture_key(row)].append(row)
        for forecast in row['models'].values(): forecast['selected_side']=None
    for fixture,rows in groups.items():
        if fixture in seen: continue
        for model in MODELS:
            choices=[]
            for row in rows:
                f=row['models'][model]
                if 'p_over' not in f: continue
                for side,p in [('over',f['p_over']),('under',1-f['p_over'])]:
                    edge=p*row['odds'][side]-1
                    blockers=f.get('selection_blockers',{}).get(side,'')
                    if not blockers and edge>=f['minimum_edge']:
                        choices.append((edge,p,row['odds'][side],row['contract_id'],side,row))
            if choices:
                best=max(choices,key=lambda x:x[:5]); best[-1]['models'][model]['selected_side']=best[-2]

def append_new(path, fresh):
    existing=[]
    if path.exists():
        existing=[json.loads(line) for line in path.read_text(encoding='utf8').splitlines() if line.strip()]
    seen={(r.get('version'),r['contract_id']) for r in existing}
    additions=[]
    for row in fresh:
        if (row.get('version'),row['contract_id']) not in seen:
            additions.append(row); seen.add((row.get('version'),row['contract_id']))
    if additions:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a',encoding='utf8',newline='\n') as handle:
            for row in additions:
                handle.write(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
    return existing+additions,len(additions)

def summarize(ledger, base, now):
    # Recompute results separately; forecasts and original offered odds never change.
    results={}
    for r in base:
        key=(r.get('date'),r.get('league'),O.key(r.get('home_team','')),O.key(r.get('away_team','')),O.key(r.get('team','')))
        actual=PUB.pf(r.get('shots_for'))
        if actual is not None and math.isfinite(actual) and actual>=0:
            results.setdefault(key,set()).add(actual)
    common=[]; settled=[]; conflicts=0
    for row in ledger:
        key=(row['match_date'],row['league'],O.key(row['home_team']),O.key(row['away_team']),O.key(row['team']))
        counts=results.get(key,set())
        if len(counts)>1:
            conflicts+=1; continue
        if not counts or PUB.parse_dt(row['kickoff_utc'])+timedelta(hours=3)>now:
            continue
        actual=next(iter(counts))
        item=(row,actual); settled.append(item)
        if all('p_over' in row['models'][m] for m in MODELS): common.append(item)
    # Average contracts within fixture first: alternate lines must not multiply sample size.
    report={}
    for model in MODELS:
        buckets=defaultdict(list)
        for row,actual in common:
            p=row['models'][model]['p_over']; y=int(actual>row['line'])
            market=(1/row['odds']['over'])/(1/row['odds']['over']+1/row['odds']['under'])
            fixture=(row['match_date'],row['league'],O.key(row['home_team']),O.key(row['away_team']))
            buckets[fixture].append(dict(brier=(p-y)**2,log_loss=-math.log(p if y else 1-p),
                market_brier=(market-y)**2,mean_error=row['models'][model]['mean']-actual,
                absolute_error=abs(row['models'][model]['mean']-actual)))
        report[model]={metric:mean(mean(x[metric] for x in items) for items in buckets.values()) if buckets else None
            for metric in ('brier','log_loss','market_brier','mean_error','absolute_error')}
        selected=[]
        resolved_ids={r['contract_id'] for r,_ in settled}
        pending=[r for r in ledger if r['models'][model].get('selected_side') and r['contract_id'] not in resolved_ids]
        for row,actual in settled:
            side=row['models'][model].get('selected_side')
            if side:
                won=(actual>row['line']) if side=='over' else (actual<row['line'])
                selected.append(row['odds'][side]-1 if won else -1)
        report[model]['hypothetical_selections']=dict(settled=len(selected),
            wins=sum(x>0 for x in selected),losses=sum(x<0 for x in selected),
            pnl_units=sum(selected),roi=sum(selected)/len(selected) if selected else None,
            stake_units=len(selected),pending=len(pending),
            overdue=sum(PUB.parse_dt(r['kickoff_utc'])+timedelta(hours=48)<now for r in pending),
            unavailable_contracts=sum('p_over' not in r['models'][model] for r in ledger),
            note='Selection cohorts can differ; compare forecast scores on the paired cohort above.')
    return dict(contracts=len(ledger),settled_contracts=len(settled),paired_contracts=len(common),
        paired_fixtures=len({(r['match_date'],r['league'],O.key(r['home_team']),O.key(r['away_team'])) for r,_ in common}),
        conflicting_results=conflicts,models=report,real_stake_units=0,
        interpretation='Same-contract first quotes; scores averaged within fixture. Research only. No automatic promotion.',
        statshub_status='NOT_CONNECTED',clv_status='NOT_YET_MEASURED',
        review_milestones_fixtures=[50,150],automatic_promotion=False)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=ROOT)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'data/football-form')
    args=parser.parse_args(); now=datetime.now(timezone.utc)
    def data(relative): return args.data_root/relative
    config=V.load_json(ROOT/'data/team-shots/team-shots-opponent-config.json')
    params=V.load_json(V.TEAM_PARAMS); lock=V.load_json(V.TEAM_LOCK)
    odds_path=data('data/team-shots/team-shots-odds-history.csv')
    base_path=data('data/football-form/team-match-base.csv')
    if not base_path.exists() or not odds_path.exists():
        raise SystemExit('Missing archive input; existing paired evidence retained')
    raw=PUB.load_csv(odds_path); base=PUB.load_csv(base_path)
    registered=[r for r in raw if r.get('bookmaker','').lower()=='bet365' and r.get('market')=='TEAM_SHOTS']
    fresh,rejected=O.fresh_prices(registered,config,now)
    latest=PUB.latest_team_shots_odds(fresh,now)
    pairs=[]
    for pair in V.paired_rows(latest,O.PAIR_FIELDS):
        r=pair['over']; line=PUB.pf(r['line_label'])
        if (r['kickoff']!=pair['under']['kickoff'] or r['league_slug'] not in V.TOP_FIVE
            or not V.is_fixture_team(r['team'],r['home_team'],r['away_team'])
            or line is None or not math.isfinite(line) or line<0 or abs(line%1-.5)>1e-8
            or any(not math.isfinite(pair[s]['odds']) or pair[s]['odds']<=1 for s in ('over','under'))
            or any((r['kickoff']-pair[s]['captured_at_dt']).total_seconds()>24*3600 for s in ('over','under'))
            or abs((r['captured_at_dt']-pair['under']['captured_at_dt']).total_seconds())>900):
            rejected['unsupported_contract']+=1; continue
        pairs.append(pair)
    ledger_path=args.output_dir/'team-shots-paired-reference.jsonl'
    existing=[json.loads(s) for s in ledger_path.read_text(encoding='utf8').splitlines() if s.strip()] if ledger_path.exists() else []
    historical=existing
    existing=current_cohort(historical)
    fingerprint=model_fingerprint()
    check_fingerprint(existing,fingerprint)
    seen={r['contract_id'] for r in existing}
    pairs=[p for p in pairs if contract(p['over']) not in seen]
    opponent_base=O.read_base(base_path) if pairs else []
    match_path=data('data/football-form/football-1x2-odds-history.csv')
    records=score(pairs,raw,base,opponent_base,config,params,lock,PUB.load_csv(match_path),now) if pairs else []
    select_first_scan(records,existing)
    hashes={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'scripts/team_shots_ema20_reference.py',ROOT/'scripts/team_shots_ema20_features.py',V.TEAM_PARAMS,V.TEAM_LOCK,O.CONFIG,ROOT/'scripts/publish-football-vnext-shadow.py',ROOT/'scripts/team_shots_opponent.py']}
    hashes['calibration_sha256']=digest(CALIBRATION_PATH)
    hashes.update(base_sha256=digest(base_path),odds_sha256=digest(odds_path),match_odds_sha256=digest(match_path))
    for record in records:
        record['source_hashes']=hashes
        record['model_fingerprint']=fingerprint
    ledger,added=append_new(ledger_path,records)
    ledger=current_cohort(ledger)
    status=summarize(ledger,base,now)
    status.update(version=VERSION,model_fingerprint=fingerprint,calibration_sha256=digest(CALIBRATION_PATH),
        preserved_prior_cohort_contracts=len(historical)-len(existing),
        generated_at=PUB.fmt_dt(now),new_contracts=added,scan_exclusions=dict(rejected),
        latest_archived_capture=max((r.get('captured_at','') for r in raw),default=None),
        latest_result_date=max((r.get('date','') for r in base),default=None),
        raw_upcoming_rows=sum(bool((kickoff:=PUB.parse_dt(r.get('kickoff_at'))) and kickoff>now) for r in raw),
        status='COLLECTING' if ledger else 'WAITING_FOR_FRESH_PAIRED_MARKETS')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    target=args.output_dir/'team-shots-paired-reference-status.json'
    temp=target.with_suffix('.tmp'); temp.write_text(json.dumps(status,indent=2)+'\n',encoding='utf8'); temp.replace(target)
    print(json.dumps(status,indent=2))

if __name__=='__main__': main()
