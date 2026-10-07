#!/usr/bin/env python3
"""Isolated full-input refresh: local data, real captured quotes, zero real stake."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import runpy
import sys

from tennis_event_integrity import revision_records, revision_transition_allowed
import tennis_props_full_refresh as C
from tennis_props_model import negative_binomial_pmf

ROOT=C.ROOT
P=runpy.run_path(str(ROOT/'scripts/tennis-props-rate-trend-prospective.py'))
V=runpy.run_path(str(ROOT/'scripts/tennis-props-v3-live.py'))

def sha(path):
    data = path.read_bytes()
    if path.suffix == '.py':
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()
def record_key(row, config):
    return P['digest']([P['contract_key'](row), config.get('implementation_revision', 'original')])

def board_key(r): return (r['tour'],P['norm'](r['player']),P['norm'](r['opponent']),P['MODEL']['tournament_identity'](r['tournament']),r['date'],r['surface'])
def index(rows):
    result={}
    for r in rows:
        k=board_key(r)
        if k in result: raise ValueError('Ambiguous candidate board identity')
        result[k]=r
    return result

def prepare(out,now,config):
    source=ROOT/'data/oncourt'; manifest,reason=P['source_manifest'](source,['ATP','WTA'],now,config['max_source_age_hours'])
    if reason: raise ValueError(reason)
    base=ROOT/'data/tennis-props'
    paths=[base/n for n in ('player-props-board.csv','player-props-baseline.csv','tour-surface-baselines.csv','slam-venue-factors.csv','player-name-aliases.csv')]
    paths+=list((ROOT/'data/sackmann').glob('*_matches_*.csv'))
    fingerprint=P['digest']([now.date().isoformat(),manifest,[(str(p.relative_to(ROOT)),p.stat().st_size,p.stat().st_mtime_ns) for p in paths],config['implementation_hashes']])
    folder=out/'inputs'/fingerprint;meta_path=folder/'metadata.json'
    if meta_path.exists():
        meta=P['read_json'](meta_path,{})
        for name,digest in meta['files'].items():
            if sha(folder/name)!=digest: raise ValueError('Frozen candidate input integrity failure')
        return folder,meta
    folder.mkdir(parents=True,exist_ok=True)
    baseboard=C.read(base/'player-props-board.csv')
    if not baseboard or any(r.get('generation_date')!=now.date().isoformat() for r in baseboard): raise ValueError('control_board_not_current_day')
    histories,fixtures,audit=C.sources(now.date(),folder)
    for t,r in audit.items():
        if r['overlap_matches']<100: raise ValueError('source_parity_sample_too_small:'+t)
        for f in ('w_ace','l_ace','w_df','l_df'):
            x=r['parity'].get(f,{})
            if not x.get('n') or x['exact']/x['n']<.98: raise ValueError('source_parity_failed:'+t+':'+f)
    C.write(folder/'baseline.csv',C.build(now.date(),histories,True))
    C.write(folder/'control-board.csv',baseboard)
    # The activity CSV is kept unchanged: this lane changes count forecasts only.
    # Saved operational expected games are reused; no provider/database call.
    totals={(r['tour_id'],r['player_id'],r['opponent_id']):dict(expected_total_games=r['expected_match_games'],confidence=r['expected_match_games_confidence']) for r in baseboard if r['expected_match_games_source']=='fair_odds'}
    main=C.BOARD['main']; saved_argv=sys.argv[:]
    original=main.__globals__['load_fair_odds_expected_games']
    try:
        main.__globals__['load_fair_odds_expected_games']=lambda *a,**kw:totals
        sys.argv=['board','--as-of',now.date().isoformat(),'--baseline',str(folder/'baseline.csv'),'--out',str(folder/'candidate-board.csv')]
        main()
    finally:
        main.__globals__['load_fair_odds_expected_games']=original;sys.argv=saved_argv
    # Same frozen v3 weights and alpha in both arms; WTA/DF retain canonical models.
    import lightgbm as lgb
    import pandas as pd
    model=ROOT/config['v3_model']; booster=lgb.Booster(model_file=str(model))
    surfaces=V['surface_index'](C.read(base/'tour-surface-baselines.csv'))
    for arm,baseline in [('control',base/'player-props-baseline.csv'),('candidate',folder/'baseline.csv')]:
        rows=C.read(folder/f'{arm}-board.csv'); idx=V['baseline_index'](C.read(baseline)); alias=V['load_aliases'](C.read(base/'player-name-aliases.csv'))
        eligible=[r for r in rows if r['tour']=='ATP' and r['surface'] in ('Hard','Clay')]
        if eligible:
            frame=pd.DataFrame([V['build_feature_row'](r,idx,surfaces,aliases=alias) for r in eligible])[booster.feature_name()]
            frame['surface']=pd.Categorical(frame['surface'],categories=booster.pandas_categorical[0])
            for r,mu in zip(eligible,booster.predict(frame,num_threads=2)):r['projected_aces']=str(max(.01,float(mu)))
        C.write(folder/f'{arm}-counts.csv',rows)
    after,_=P['source_manifest'](source,['ATP','WTA'],datetime.now(timezone.utc),config['max_source_age_hours'])
    after_paths=[(str(p.relative_to(ROOT)),p.stat().st_size,p.stat().st_mtime_ns) for p in paths]
    if fingerprint!=P['digest']([now.date().isoformat(),after,after_paths,config['implementation_hashes']]): raise ValueError('inputs_changed_during_build')
    files={p.name:sha(p) for p in folder.iterdir() if p.suffix in ('.csv','.json') and p.name!='metadata.json'}
    meta=dict(input_hash=fingerprint,generated_at=datetime.now(timezone.utc).isoformat(),feature_cutoff=now.date().isoformat(),files=files,source_manifest=manifest,source_audit=audit,recent_rate_trend='OFF')
    P['atomic_json'](meta_path,meta)
    return folder,meta

def pair(row,control,candidate,config):
    predictions={}
    for arm,mean in [('control',control),('candidate',candidate)]:
        predictions[arm]={}
        for side in ('OVER','UNDER'):
            odds=P['numeric'](row.get(side.lower()+'_odds'))
            if odds is not None and odds>1:
                predictions[arm][side]=P['MODEL']['prediction'](mean,dict(row,side=side,selected_odds=odds),config)
    return predictions

def summarize(records,outcomes,health,config,now):
    current, archived = revision_records(records, config.get('implementation_revision'))
    result=P['report'](current,outcomes,health,config,now)
    result['implementation_revision'] = config.get('implementation_revision', 'original')
    archives=[]
    for config_hash in sorted({r['config_hash'] for r in archived}):
        cohort=[r for r in archived if r['config_hash']==config_hash]
        saved=P['report'](cohort,outcomes,{},config,now)
        saved.update(config_hash=config_hash,implementation_revision=cohort[0].get('implementation_revision','original'))
        archives.append(saved)
    result['archived_revisions'] = archives
    result['archived_revision'] = archives[0] if len(archives)==1 else None
    result['revision_note'] = 'Tournament adjustment now uses this event’s previous editions. Qualifying is included against prior qualifying. Earlier forecasts are retained separately; fitted weights and stakes are unchanged.'
    records = current
    for market,group in result['markets'].items():
        rows=[r for r in records if r['row']['market']==market]
        group['overdue']=sum(r['id'] not in outcomes and (now-P['stamp'](r['row']['match_start_utc'])).total_seconds()>48*3600 for r in rows)
        group['void']=sum(outcomes.get(r['id'],{}).get('status')=='void' for r in rows)
        group['registered_fixtures']=len({r['fixture_key'] for r in rows})
        for arm in ('control','candidate'):
            counts=Counter(); errors=[];nll=[];seen=set()
            for r in rows:
                outcome=outcomes.get(r['id'],{})
                if outcome.get('status')!='settled': continue
                actual=outcome['actual']; side=r[arm+'_side']; row=r['row']
                if side:
                    _,win=P['MODEL']['outcomes'](actual,float(row['line']),side,float(row[side.lower()+'_odds']))
                    counts['pushes' if win is None else 'wins' if win else 'losses']+=1
                key=(r['fixture_key'],P['norm'](row['player']))
                if key not in seen:
                    seen.add(key); mean=r[arm]['OVER']['mean']; errors.append(abs(mean-actual))
                    nll.append(-math.log(max(1e-15,negative_binomial_pmf(int(actual),mean,config['alpha'][row['tour']][market]))))
            group[arm].update(wins=counts['wins'],losses=counts['losses'],pushes=counts['pushes'],stake_units=group[arm]['bets'],count_samples=len(errors),count_mae=sum(errors)/len(errors) if errors else None,count_nll=sum(nll)/len(nll) if nll else None)
    result.update(recent_rate_trend='OFF',production_changed=False,control_description='Frozen ATP v3 aces on Hard/Clay; canonical WTA aces and ATP/WTA double faults.',candidate_description='Identical models with the full OnCourt input refresh; no recent-rate multiplier.',pending_rows=[dict(id=r['id'],player=r['row']['player'],opponent=r['row']['opponent'],market=r['row']['market'],line=r['row']['line'],start=r['row']['match_start_utc'],bookmaker=r['row']['bookmaker'],control_side=r['control_side'],candidate_side=r['candidate_side']) for r in records if r['id'] not in outcomes][:80])
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',type=Path,required=True);parser.add_argument('--out',type=Path,default=ROOT/'data/tennis-props/shadow/full-refresh-v1');parser.add_argument('--config',type=Path,default=ROOT/'config/tennis-props-full-refresh-v1.json');parser.add_argument('--settle-only',action='store_true');args=parser.parse_args()
    config=P['read_json'](args.config,None);now=datetime.now(timezone.utc)
    with P['lock'](args.out):
        if args.settle_only:
            reg=P['read_json'](args.out/'registration.json',None)
            if not reg:
                print('No retained input-refresh comparison to settle');return 0
            config=reg['config']
            records=P['ledger'](args.out/'observations.jsonl')
            outcomes=P['read_json'](args.out/'outcomes.json',{})
            P['settle'](records,ROOT/'data/oncourt',outcomes,now)
            P['atomic_json'](args.out/'outcomes.json',outcomes)
            result=summarize(records,outcomes,{'settlement_only':True},config,now)
            result.update(status='SOURCE_UPGRADE_APPLIED_SETTLING',capture_enabled=False,
                revision_note='Current OnCourt history is now the standard input. Earlier comparison forecasts are retained and settled; no new stale-history comparison forecasts are added.')
            P['atomic_json'](args.out/'report.json',result)
            print(json.dumps({'status':result['status'],'markets':result['markets']}));return 0
        if config.get('capture_enabled') is False:
            raise ValueError('Input upgrade applied; this comparison is retained for --settle-only')
        # Validate the installed files before accepting the explicitly registered repair.
        for path, digest in config['implementation_hashes'].items():
            if sha(ROOT/path) != digest:
                raise ValueError('frozen_implementation_changed:' + path)
        reg=P['read_json'](args.out/'registration.json',None)
        if reg and reg['config_hash']!=P['digest'](config):
            if not revision_transition_allowed(reg['config_hash'], config):
                raise ValueError('Frozen experiment configuration changed')
            # One named data-integrity repair, with the prior registration retained.
            (args.out/'registration-history').mkdir(parents=True, exist_ok=True)
            P['atomic_json'](args.out/'registration-history'/f"{reg['config_hash']}.json", reg)
            P['atomic_json'](args.out/'registration-history'/f"{reg['config_hash']}-report.json", P['read_json'](args.out/'report.json', {}))
            reg = None
        if not reg:P['atomic_json'](args.out/'registration.json',dict(registered_at=now.isoformat(),config_hash=P['digest'](config),config=config))
        records=P['ledger'](args.out/'observations.jsonl');outcomes=P['read_json'](args.out/'outcomes.json',{});health=Counter();failure=None
        try:
            eligible=[];seen={r['id'] for r in records}
            for row in C.read(args.comparison):
                if row.get('market') not in config['markets']:continue
                reason=P['eligibility'](row,now)
                if P['norm'](row.get('bookmaker'))!='bet365':reason='unsupported_bookmaker'
                if row.get('surface') not in ('Hard','Clay'):reason='unvalidated_surface'
                if reason:health[reason]+=1
                elif record_key(row, config) in seen:health['already_registered']+=1
                else:eligible.append(row)
            if eligible:
                folder,meta=prepare(args.out,now,config)
                boards={a:index(C.read(folder/f'{a}-counts.csv')) for a in ('control','candidate')}
                for row in eligible:
                    registered=datetime.now(timezone.utc);reason=P['eligibility'](row,registered);key=board_key(row)
                    if reason:health[reason]+=1;continue
                    if key not in boards['control'] or key not in boards['candidate']:health['no_exact_paired_board']+=1;continue
                    contract=record_key(row, config)
                    if contract in seen:continue
                    field='projected_aces' if row['market']=='aces' else 'projected_dfs'
                    means={a:float(boards[a][key][field]) for a in boards}
                    if any(not math.isfinite(v) or v<=0 for v in means.values()):health['invalid_mean']+=1;continue
                    if any(boards[a][key].get('player_name_resolution')=='unresolved' or boards[a][key].get('opponent_name_resolution')=='unresolved' for a in boards):health['unresolved_identity']+=1;continue
                    predictions=pair(row,means['control'],means['candidate'],config)
                    fixture=P['digest']([row['tour'],row['date'][:4],P['MODEL']['tournament_identity'](row['tournament']),sorted([P['norm'](row['player']),P['norm'](row['opponent'])])])
                    P['append'](args.out/'observations.jsonl',records,dict(implementation_revision=config.get("implementation_revision", "original"),id=contract,fixture_key=fixture,registered_at=registered.isoformat(),row=row,input_hash=meta['input_hash'],config_hash=P['digest'](config),capture_hash=P['digest'](row),feature_cutoff=meta['feature_cutoff'],**predictions,**{a+'_side':P['policy'](predictions[a],config['min_ev']) for a in predictions}))
                    seen.add(contract);health['registered_now']+=1
            else:health['no_new_eligible_contracts']+=1
        except Exception as exc:
            failure=str(exc);health['registration_blocked']+=1
        try:P['settle'](records,ROOT/'data/oncourt',outcomes,datetime.now(timezone.utc))
        except Exception as exc:failure=(failure+'; ' if failure else '')+'settlement:'+str(exc);health['settlement_failed']+=1
        P['atomic_json'](args.out/'outcomes.json',outcomes)
        result=summarize(records,outcomes,dict(health),config,datetime.now(timezone.utc));result['error']=failure
        if failure:result['status']='BLOCKED'
        P['atomic_json'](args.out/'report.json',result)
        print(json.dumps({k:result[k] for k in ('status','health','markets','error')}))
        return 1 if failure else 0

if __name__=='__main__':raise SystemExit(main())
