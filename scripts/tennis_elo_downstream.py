"""Read-only downstream diagnostics using the existing frozen pricing functions."""
from datetime import date
from pathlib import Path
import importlib.util,json,sys

def mod(path):
    spec=importlib.util.spec_from_file_location('elo_down_'+path.stem.replace('-','_'),path)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def enrich(root, pairs, as_of):
    board=mod(root/'scripts/build-tennis-props-board.py')
    handicap=mod(root/'scripts/compute-handicap-values.py')
    v3=mod(root/'scripts/tennis-props-v3-live.py')
    most=mod(root/'scripts/build-tennis-most-aces-board.py')
    schedules=board.oncourt_schedule_rows('ATP',False,as_of,7)
    from tennis_elo_shadow import fixture
    def skey(s):return fixture({'tour_id':s['tour_id'],'round_id':s['round_id_raw'],'player1_id':s['player1_id'],'player2_id':s['player2_id']})
    schedules={skey(s):s for s in schedules}
    baseline=board.load_baseline(board.DEFAULT_BASELINE);activity=board.load_activity(board.DEFAULT_ACTIVITY)
    factors=board.load_factors(board.DEFAULT_FACTORS);surfaces=board.load_surface_baselines(board.DEFAULT_SURFACE_BASELINES)
    aliases=board.load_aliases(board.DEFAULT_ALIASES);names=board.baseline_names_by_tour(baseline)
    sch=list(schedules.values());day=date.fromisoformat(as_of)
    shared=dict(baseline=baseline,activity=activity,factors=factors,surface_baselines=surfaces,
        tournament_samples=board.load_tournament_samples(day),aliases=aliases,baseline_names=names,
        current_tournament_stats=board.load_current_tournament_stats(sch,day),
        current_tournament_logs=board.load_current_tournament_logs(sch,day),
        current_tournament_environment=board.load_current_tournament_environment(sch,day,factors,surfaces))
    gate=v3.read_json(v3.DEFAULT_GATE).get('deployment_safe_aces',{}).get('ATP',{})
    booster=v3.lgb.Booster(model_file=str(root/gate['model_path'])) if gate.get('passed') is True else None
    cats=(booster.pandas_categorical or [['Clay','Grass','Hard']])[0] if booster else []
    vb=v3.baseline_index(v3.read_csv(v3.DEFAULT_BASELINE));vs=v3.surface_index(v3.read_csv(v3.DEFAULT_SURFACE_BASELINES))
    va=v3.load_aliases(v3.read_csv(v3.DEFAULT_ALIASES));rho=most.load_rho(most.DEFAULT_CONFIG)
    for pair in pairs:
        for arm in ['baseline','candidate']:
            r=pair[arm];diag=r['elo_diagnostics'];best='bo5' if diag['best_of']==5 else 'bo3'
            # Exact model shape, before spread-specific empirical calibration.
            r['handicap_shape']={str(line):list(handicap._shape_cover_probabilities(r['p_a'],r['p_b'],line,best)) for line in [-3.5,-2.5,-1.5,1.5,2.5,3.5]}
            schedule=schedules.get(pair['key'])
            if not schedule:r['props_status']='outside_existing_general_props_schedule';continue
            fair={(str(r['tour_id']),str(a),str(b)):{'expected_total_games':r['expected_total_games'],'confidence':r['confidence']}
                  for a,b in [(r['player1_id'],r['player2_id']),(r['player2_id'],r['player1_id'])]}
            rows=[];vrows=[]
            for a,b in [('1','2'),('2','1')]:
                side=board.project_side(schedule=schedule,player=schedule['player'+a],opponent=schedule['player'+b],
                    player_id=str(schedule['player'+a+'_id']),fair_odds_expected_games=fair,**shared)
                rows.append({k:side.get(k) for k in ['player','player_id','opponent_id','projected_aces','projected_dfs','service_points_estimate','expected_match_games','ace_confidence','df_confidence']})
                if booster and side['surface'] in {'Hard','Clay'}:
                    features=v3.build_feature_row(side,vb,vs,names,va);frame=v3.pd.DataFrame([features])[booster.feature_name()]
                    frame['surface']=v3.pd.Categorical(frame['surface'],categories=cats)
                    count=max(.01,float(booster.predict(frame,num_threads=1)[0]))
                    vr={**side,'projected_aces':f'{count:.3f}','aces_alpha':f"{float(gate.get('candidate_alpha',0)):.6f}",'v3_eligible':'true'}
                    for window in ['l12m','l24m','career4y']:
                        for field in ['matches','svpt']:
                            vr['player_'+window+'_'+('svpt_sample' if field=='svpt' else field)]=str(features.get('player_'+window+'_'+field,''))
                    rows[-1]['v3_projected_aces']=count;vrows.append(vr)
            r['props']=rows;r['props_status']='same_functions_same_inputs_only_match_games_changed'
            count=most.build_rows(vrows,rho)
            r['count_most_aces']=[{k:v for k,v in x.items() if k in {'player1','player2','p_player1','p_draw','p_player2','fair_player1','fair_draw','fair_player2','quote_status','quote_reason'}} for x in count]
    return pairs
