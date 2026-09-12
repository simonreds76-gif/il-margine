#!/usr/bin/env python3
"""Matched archived-price replay of fixed opponent shots vs actual v4 scoring code.

Never appends prospective evidence. Current v4 parameters are applied
retrospectively, including periods preceding their July parameter freeze.
"""
import argparse, json
from collections import defaultdict
from pathlib import Path
from team_shots_opponent import read_base, key, ROOT, History
import importlib.util, sys

spec=importlib.util.spec_from_file_location('opponent_shadow_replay',ROOT/'scripts/team-shots-opponent-shadow.py')
S=importlib.util.module_from_spec(spec);sys.modules[spec.name]=S;spec.loader.exec_module(S)

def summarize(rows):
    chosen=S.V.cap_signals([r for r in rows if not r.get('blocked_reason')])
    pnl=sum(r['pnl'] for r in chosen)
    return dict(bets=len(chosen),wins=sum(r['pnl']>0 for r in chosen),losses=sum(r['pnl']<0 for r in chosen),pnl=pnl,roi=pnl/len(chosen) if chosen else None,picks=chosen)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    observations=json.loads(args.observations.read_text())['shots']
    config=json.loads(S.CONFIG.read_text())
    base=read_base(S.PUB.DEFAULT_TEAM_BASE)
    rawbase=S.PUB.load_csv(S.PUB.DEFAULT_TEAM_BASE)
    for r in rawbase:
        for f in ('team','opponent','home_team','away_team'):
            r[f]=key(r[f])
    outcomes={(r['date'],r['league'],key(r['home_team']),key(r['away_team']),key(r['team'])):r['shots_for'] for r in base}
    groups=defaultdict(list)
    excluded=[]
    for obs in observations:
        if obs['date']<'2026-05-09':continue
        identity=(obs['date'],obs['league'],key(obs['home']),key(obs['away']),key(obs['team']))
        if outcomes.get(identity) != obs['actual']:
            excluded.append(dict(fixture=obs['fixture'],reason='fixture_orientation_or_result_mismatch'));continue
        groups[min(obs['date'],obs['captured'][:10])].append(obs)
    params=S.V.load_json(S.V.TEAM_PARAMS);lock=S.V.load_json(S.V.TEAM_LOCK)
    matchodds=S.PUB.load_csv(S.V.MATCH_ODDS_INPUT)
    for r in matchodds:
        for f in ('home_team','away_team'):r[f]=key(r[f])
    selected={'candidate':[],'served_v4':[]}; matched=0; strength=0
    history=History()
    daily=defaultdict(list)
    for r in base:daily[r['date']].append(r)
    days=iter(sorted(daily))
    nextday=next(days,None)
    for day, batch in sorted(groups.items()):
        while nextday is not None and nextday<day:
            history.update_day(daily[nextday])
            nextday=next(days,None)
        by_team,by_league=S.PUB.build_base_indexes([r for r in rawbase if r['date']<day])
        pairs=[];actuals={};old=[]
        for obs in batch:
            source=dict(captured_at=obs['captured'],kickoff_at=obs['kickoff'],competition=obs['league'],home_team=key(obs['home']),away_team=key(obs['away']),team=key(obs['team']),line=str(obs['line']),bookmaker=obs['bookmaker'])
            odds=[dict(source,side=side,odds_decimal=str(obs[side])) for side in ('over','under')]
            now=S.PUB.parse_dt(obs['captured'])
            latest=S.PUB.latest_team_shots_odds(odds,now)
            pair=S.V.paired_rows(latest,S.PAIR_FIELDS)
            if not pair:continue
            pairs.extend(pair)
            _, rows=S.V.score_team_shots(by_team=by_team,by_league=by_league,odds_rows=odds,params=params,lock=lock,now=now,match_odds_rows=matchodds)
            old.extend(rows)
            actuals[(obs['date'],obs['league'],key(obs['home']),key(obs['away']),key(obs['team']),str(float(obs['line'])))]=obs['actual']
        candidate,_=S.score_pairs(pairs,base,config,{day:history})
        # Require both methodologies to be able to price exactly this contract.
        def ident(r):return (r['match_date'],r['league'],key(r['home_team']),key(r['away_team']),key(r['team']),str(float(r['line'])))
        common={ident(r) for r in candidate}&{ident(r) for r in old}
        matched+=len(common)
        strength+=sum(bool(r.get('market_strength_captured_at_utc')) for r in old if r['side']=='over' and ident(r) in common)
        for lane,rows in [('candidate',candidate),('served_v4',old)]:
            for r in rows:
                if ident(r) not in common:continue
                actual=actuals[ident(r)]
                r['actual_team_shots']=actual
                _,r['pnl']=S.SETTLE.settle_market(r['side'],float(r['line']),actual,float(r['book_odds']))
                r['match_id']='|'.join(ident(r)[:4])
                selected[lane].append(r)
        print(day,matched,'matched contracts',flush=True)
    phases={}
    for phase,start,end in [('may_july','2026-05-09','2026-08-01'),('august_september','2026-08-01','2027-01-01'),('combined','2026-05-09','2027-01-01')]:
        phases[phase]={name:summarize([r for r in rows if start<=r['match_date']<end]) for name,rows in selected.items()}
    report=dict(status='RETROSPECTIVE_COMPARISON_ONLY',matched_contracts=matched,matched_1x2_contracts=strength,excluded=excluded,v4_parameter_freeze=params.get('frozen_at'),limitations=['Current v4 July parameters used retrospectively; May/June comparison is not out-of-sample for v4.','History strictly before capture day for both lanes; identical paired prices and one highest-edge selection per fixture.','Missing archived 1X2 uses the actual v4 fallback, not invented prices.','Historical selections do not enter forward ROI.'],phases=phases)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    for phase,lanes in phases.items():print(phase,{k:{f:r[f] for f in ('bets','wins','losses','pnl','roi')} for k,r in lanes.items()})

if __name__=='__main__':main()
