"""Frozen event-error comparison within Sisal paper tracking. No network or alerts."""
from __future__ import annotations
import json, runpy
from collections import Counter, defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
import tennis_sisal_5050 as T

SUB = 'event-comparison-v1'
POLICY = dict(version=SUB, name='Event-adjusted 50/50', k=100, lag_days=1,
              model_weight=.5, min_ev=.08, paper_stake=1, real_stake=0, alerts=False,
              evidence='Exact edition, completed main draw, prior UTC date and observed before quote',
              no_evidence='Neutral V3, multiplier 1; unavailable evidence never silently treated as zero',
              reviews=[50,100], automatic_promotion=False)
FROZEN = [str(T.MODEL),str(T.GENERATOR),'scripts/tennis_props_model.py',
          'scripts/build-tennis-props-board.py','scripts/tennis_props_full_refresh.py',
          'scripts/tennis_event_integrity.py','scripts/sisal_event_comparison.py']

def folder(root): return root/T.REL/SUB
SELF = 'scripts/sisal_event_comparison.py'

def register_source_revision(root, now, expected_old, expected_new):
    """Explicit, dated input-scope repair; never rewrite the original registration."""
    p=folder(root)
    with T.lock(root/T.REL), T.lock(p):
        reg=T.read_json(p/'registration.json',None)
        if not reg or reg['policy']!=POLICY:raise ValueError('missing_or_changed_registration')
        hashes={n:T.sha(root/n) for n in FROZEN}
        if reg['artifacts'][SELF]!=expected_old or hashes[SELF]!=expected_new:
            raise ValueError('revision_hash_mismatch')
        if any(hashes[n]!=h for n,h in reg['artifacts'].items() if n!=SELF):
            raise ValueError('non_source_artifact_changed')
        revision=dict(id='singles-evidence-scope-20261028',effective_from=now.isoformat(),
            artifact=SELF,previous_hash=expected_old,current_hash=expected_new,
            reason='Exclude identified doubles from required singles evidence; pricing policy unchanged')
        path=p/'source-filter-revision.json'
        if path.exists():
            existing=T.read_json(path,{})
            if any(existing.get(k)!=revision[k] for k in ('id','artifact','previous_hash','current_hash')):
                raise ValueError('source_revision_already_registered')
            return existing
        T.atomic(path,revision)
        return revision

def register(root, now):
    p=folder(root);p.mkdir(parents=True,exist_ok=True)
    hashes={n:T.sha(root/n) for n in FROZEN}
    reg=T.read_json(p/'registration.json',None)
    if reg is None:
        reg=dict(registered_at=now.isoformat(),policy=POLICY,artifacts=hashes)
        T.atomic(p/'registration.json',reg)
    expected=dict(reg['artifacts']);revision=T.read_json(p/'source-filter-revision.json',None)
    if revision:
        if (revision.get('id')!='singles-evidence-scope-20261028' or revision.get('artifact')!=SELF
            or revision.get('previous_hash')!=expected[SELF]
            or T.stamp(revision.get('effective_from')) is None
            or T.stamp(revision['effective_from'])<T.stamp(reg['registered_at'])):
            raise ValueError('invalid_source_revision')
        expected[SELF]=revision['current_hash']
    from sisal_observation_amendment import accepted_observation_amendment
    amendment=accepted_observation_amendment(p,T.sha(p/'registration.json'),expected,hashes,'event',now)
    if reg['policy']!=POLICY or (expected!=hashes and not amendment):
        raise ValueError('event_comparison_frozen_policy_or_artifact_changed')
    return dict(reg,artifacts=hashes,source_revision=revision,observation_amendment_sha256=amendment,
                effective_from=revision['effective_from'] if revision else reg['registered_at'])

def required_singles(games,names,tids,score):
    """Keep unknown identities as gaps; exclude only positively identified doubles."""
    known={tid:set() for tid in tids};excluded=Counter()
    for g in games:
        tid=g['tour_id']
        if tid not in known or int(g['round_id'])<4 or score(g['result']) is None:continue
        if any('/' in names.get(g[k],'') for k in ('winner_id','loser_id')):
            excluded[tid]+=1;continue
        known[tid].add(tuple(g[k] for k in ('winner_id','loser_id','tour_id','round_id')))
    return known,dict(excluded)

def neutral_mean(record, score, corrections):
    """Neutralise the incumbent INPUT, never the final V3 output.

    The saved incumbent has three decimals. Bound its rounding uncertainty and
    require every possible rounded neutral input to reach the same tree output.
    Clipped rates cannot be inverted and are explicitly held out.
    """
    b=record['board'];f=record['features'];factor=T.number(b.get('current_env_ace_factor'))
    if factor is None or not .94<=factor<=1.06:raise ValueError('invalid_event_factor')
    if factor==1:return score([f])[0],dict(method='factor_already_neutral',input=f['incumbent_aces'])
    rate=T.number(b.get('ace_rate_adj'))
    if rate is None or not .00202<rate<.27998 or not .00202<rate/factor<.27998:
        raise ValueError('neutral_input_rate_clipped_or_unknown')
    correction=corrections.get(('ATP',b['tournament']),{}).get('aces',0.)
    original=float(f['incumbent_aces'])
    if original<=.001:raise ValueError('neutral_input_zero_clipped')
    # Each endpoint includes half a final three-decimal rounding unit.
    lo=(original-.000500001-correction)/factor+correction
    hi=(original+.000500001-correction)/factor+correction
    first=int(round(lo*1000));last=int(round(hi*1000))
    possible=[dict(f,incumbent_aces=i/1000) for i in range(first,last+1)]
    values=score(possible)
    if max(values)-min(values)>1e-12:raise ValueError('neutral_input_rounding_ambiguous')
    return values[0],dict(method='incumbent_counterfactual_rounding_bound',input_min=first/1000,input_max=last/1000,correction=correction)

def predictor(root):
    import lightgbm as lgb
    import pandas as pd
    model=lgb.Booster(model_file=str(root/T.MODEL))
    def score(rows):
        frame=pd.DataFrame(rows)[model.feature_name()]
        frame['surface']=pd.Categorical(frame.surface,categories=model.pandas_categorical[0])
        return [max(.01,float(v)) for v in model.predict(frame,num_threads=2)]
    return score

def prepare(root, now=None):
    """Snapshot completed evidence BEFORE odds requests. Bounded to current editions.

    Earlier means are chronological reconstructions, not claimed original logs.
    first_observed_complete_at proves the result was known before the target quote;
    it is deliberately not labelled the actual match-finish timestamp.
    """
    now=now or datetime.now(timezone.utc);p=folder(root)
    with T.lock(root/T.REL), T.lock(p):
        try:
            reg=register(root,now)
            return _prepare(root,p,now,reg)
        except Exception as exc:
            T.atomic(p/'evidence-status.json',dict(state='BLOCKED',checked_at=now.isoformat(),reason=str(exc)))
            raise

def _prepare(root,p,now,reg):
    import pandas as pd
    import tennis_props_full_refresh as C
    from tennis_event_integrity import clean_event_rows
    from tennis_source_contract import court_surfaces
    from tennis_props_names import baseline_names_by_tour
    B=C.BOARD;V=runpy.run_path(str(root/T.GENERATOR));S=root/'data/oncourt'
    paths=[S/n for n in ['players_atp.csv','tours_atp.csv','games_atp.csv','stat_atp.csv','courts.csv','today_atp.csv']]
    paths += [root/'data/tennis-props'/n for n in ['slam-venue-factors.csv','tour-surface-baselines.csv']]
    manifest={str(x.relative_to(root)):T.sha(x) for x in paths}
    names={x['id']:x['name'] for x in T.read_csv(paths[0])};tours={x['id']:x for x in T.read_csv(paths[1])}
    tids={x['tour_id'] for x in T.read_csv(S/'today_atp.csv') if now.date().isoformat()<=x.get('date','')<=(now+timedelta(days=4)).date().isoformat()}
    tids={tid for tid in tids if tid in tours and B['is_supported_main_tour'](tours[tid])}
    eligible={tid for tid,t in tours.items() if B['is_supported_main_tour'](t) and t['date']>=f'{now.year-5}-01-01'}
    games=[g for g in T.read_csv(S/'games_atp.csv') if g['tour_id'] in eligible and g['date']<now.date().isoformat()]
    stats=[s for s in T.read_csv(S/'stat_atp.csv') if s['tour_id'] in eligible]
    known,excluded_doubles=required_singles(games,names,tids,C.score)
    stats,games,excluded=clean_event_rows(stats,games,names)
    key=lambda x:tuple(x[k] for k in ('winner_id','loser_id','tour_id','round_id'))
    si={key(s):s for s in stats};surface=court_surfaces(S/'courts.csv',combine_hard=True)
    hist=defaultdict(list);valid={};invalid={};ge=defaultdict(list);se=defaultdict(list)
    for g in games:
        raw,err=C.adapt(g,si[key(g)]);t=tours[g['tour_id']]
        if err or t['court_id'] not in surface:
            invalid[key(g)]=err or 'surface_unmapped';continue
        raw.update(surface=surface[t['court_id']],tournament=B['scheduled_tournament_name'](t['name']) or t['name'])
        valid[key(g)]=(g,raw);ge[g['tour_id']].append(g);se[g['tour_id']].append(si[key(g)])
        if int(g['round_id'])>=4:
            for pref,side in [('w','winner'),('l','loser')]:
                pid=g[side+'_id'];hist['atp',pid,names[pid]].append((date.fromisoformat(g['date']),raw,pref,'oncourt'))
    evidence=T.ledger(p/'evidence.jsonl');saved={(x['id'],x['source_hash']):x for x in evidence}
    queries=defaultdict(list);missing=Counter();new=[]
    for tid,keys in known.items():
        missing[tid]+=len(keys-set(valid))
        for k in sorted(keys&set(valid)):
            g,raw=valid[k]
            for pref,side,opp in [('w','winner','loser'),('l','loser','winner')]:
                identity=':'.join([tid,g['round_id'],*sorted([g['winner_id'],g['loser_id']]),g[side+'_id']])
                source_hash=T.digest([g,si[k]])
                if (identity,source_hash) not in saved:
                    queries[g['date']].append((identity,source_hash,g,raw,pref,side,opp))
    globals_=B['project_side'].__globals__
    globals_['load_current_event_rows']=lambda tour,ids:([s for tid in ids for s in se[tid]],[g for tid in ids for g in ge[tid]])
    globals_['load_oncourt_tours']=lambda tour:tours
    factors=B['load_factors'](paths[-2]);surfaces=B['load_surface_baselines'](paths[-1]);score=predictor(root)
    reference_years=[int(x['year']) for f in paths[-2:] for x in T.read_csv(f) if x.get('year','ALL')!='ALL']
    for day,items in sorted(queries.items()):
        if reference_years and max(reference_years)>=int(day[:4]):raise ValueError('future_reference_year')
        ids={g[side+'_id'] for _,_,g,_,_,server,opponent in items for side in (server,opponent)}
        baselines=C.build(date.fromisoformat(day),{k:v for k,v in hist.items() if k[1] in ids},True)
        bi=V['baseline_index'](baselines);bn=baseline_names_by_tour(bi)
        schedules=[dict(tour='ATP',tournament=raw['tournament'],surface=raw['surface'],tour_id=g['tour_id'],round_id_raw=g['round_id'],round=B['round_label'](g['round_id'],tours[g['tour_id']]['name']),date=day,generation_date=day,player1_id=g[s+'_id'],player2_id=g[o+'_id'],source='chronological_event_evidence') for _,_,g,raw,_,s,o in items]
        samples=B['load_current_tournament_stats'](schedules,date.fromisoformat(day))
        feats=[];meta=[]
        for (identity,source_hash,g,raw,pref,side,opp),schedule in zip(items,schedules):
            b=B['project_side'](schedule=schedule,player=names[g[side+'_id']],opponent=names[g[opp+'_id']],player_id=g[side+'_id'],baseline=bi,activity={},factors=factors,surface_baselines=surfaces,tournament_samples={},aliases={},baseline_names=bn,current_tournament_stats=samples,current_tournament_logs={},current_tournament_environment={},fair_odds_expected_games={})
            if 'unresolved' in (b['player_name_resolution'],b['opponent_name_resolution']):missing[g['tour_id']]+=1;continue
            f=V['build_feature_row'](b,bi,surfaces,bn,{})
            feats.append(f);meta.append(dict(id=identity,source_hash=source_hash,tid=g['tour_id'],result_date=day,pid=g[side+'_id'],opp=g[opp+'_id'],round=g['round_id'],actual_aces=int(raw[pref+'_ace']),actual_points=int(raw[pref+'_svpt']),expected_points=f['expected_service_points'],historical_mean_reconstructed=True))
        for row,mu in zip(meta,score(feats) if feats else []):
            row.update(neutral_mean=mu,expected_aces_on_actual_points=mu/row['expected_points']*row['actual_points']);new.append(row)
    if any(T.sha(root/n)!=h for n,h in manifest.items()):raise ValueError('event_sources_changed_during_read')
    observed=datetime.now(timezone.utc)
    for row in new:
        row.update(first_observed_complete_at=observed.isoformat(),manifest=manifest,artifact_hashes=reg['artifacts'],observation_amendment_sha256=reg.get('observation_amendment_sha256'))
        T.append(p/'evidence.jsonl',evidence,row)
    status=dict(state='READY',checked_at=observed.isoformat(),prepared_at=observed.isoformat(),editions=sorted(tids),missing_by_edition=dict(missing),missing_fixtures=[dict(edition=tid,fixture=list(k),reason=invalid.get(k,'missing_or_rejected_statistics')) for tid,keys in known.items() for k in sorted(keys-set(valid))],added=len(new),evidence_rows=len(evidence),manifest=manifest,clean_exclusions=excluded)
    status.update(excluded_doubles_by_edition=excluded_doubles,source_revision=reg.get('source_revision'),observation_amendment_sha256=reg.get('observation_amendment_sha256'))
    T.atomic(p/'evidence-status.json',status)
    return status

def choose_evidence(evidence,tid,cap):
    latest={}
    for e in evidence:
        if e['tid']!=tid or e['result_date']>=cap.date().isoformat():continue
        observed=T.stamp(e['first_observed_complete_at'])
        if observed is None or observed>cap:continue
        if e['id'] not in latest or observed>T.stamp(latest[e['id']]['first_observed_complete_at']):latest[e['id']]=e
    return list(latest.values())

def capture_pairs(root,records,now):
    p=folder(root);reg=register(root,now);pairs=T.ledger(p/'pairs.jsonl');seen={x['id'] for x in pairs}
    status=T.read_json(p/'evidence-status.json',{});evidence=T.ledger(p/'evidence.jsonl')
    score=predictor(root) if records else None
    corrections=runpy.run_path(str(root/'scripts/tennis_props_model.py'))['SLAM_COUNT_BIAS_CORRECTION'] if records else {}
    for r in records:
        if r['id'] in seen:continue
        pair=dict(id=r['id'],base_hash=r['hash'],registered_at=now.isoformat(),state='UNAVAILABLE',source_revision=reg.get('source_revision'),observation_amendment_sha256=reg.get('observation_amendment_sha256'))
        try:
            cap=T.stamp(r['row']['capture_ts']);prepared=T.stamp(status.get('prepared_at'))
            if cap<T.stamp(reg['registered_at']):raise ValueError('price_precedes_comparison_registration')
            if cap<T.stamp(reg.get('effective_from',reg['registered_at'])):raise ValueError('price_precedes_source_revision')
            if status.get('state')!='READY' or not prepared or prepared>cap or (cap-prepared).total_seconds()>24*3600:raise ValueError('event_evidence_not_verified_before_quote')
            tid=r['native']['tid']
            if tid not in status['editions']:raise ValueError('edition_not_verified')
            if status['missing_by_edition'].get(tid,0):raise ValueError('incomplete_event_evidence')
            previous=choose_evidence(evidence,tid,cap)
            a=sum(e['actual_aces'] for e in previous);exp=sum(e['expected_aces_on_actual_points'] for e in previous)
            multiplier=(a+100)/(exp+100)
            neutral,proof=neutral_mean(r,score,corrections)
            mean=neutral*multiplier
            if (T.stamp(r['row']['match_start_utc'])-datetime.now(timezone.utc)).total_seconds()<900:raise ValueError('started_during_comparison')
            pair.update(state='PAIRED',neutral_mean=neutral,mean=mean,multiplier=multiplier,prior_actual=a,prior_expected=exp,
                        evidence_ids=[e['hash'] for e in previous],evidence_rows=len(previous),evidence_prepared_at=prepared.isoformat(),
                        latest_observed_at=max((e['first_observed_complete_at'] for e in previous),default=None),
                        latest_result_date=max((e['result_date'] for e in previous),default=None),neutral_proof=proof,
                        original=r['arms'],adjusted=T.arms(mean,float(r['row']['line']),float(r['row']['over_odds']),float(r['row']['under_odds'])))
        except (ValueError,KeyError,TypeError) as exc:pair['reason']=str(exc)
        T.append(p/'pairs.jsonl',pairs,pair);seen.add(r['id'])

def comparison_report(root,rows,outcomes,reg,now):
    p=folder(root);registration=T.read_json(p/'registration.json',{})
    pairs=T.ledger(p/'pairs.jsonl');index={r['id']:r for r in rows}
    accepted=[x for x in pairs if x['state']=='PAIRED']
    for x in pairs:
        if x['id'] not in index or index[x['id']]['hash']!=x['base_hash']:raise ValueError('event_pair_base_mismatch')
    versions={}
    for name,armkey in [('original','original'),('event_adjusted','adjusted')]:
        records=[]
        for x in accepted:
            r=index[x['id']];records.append(dict(r,arms=x[armkey],mean=x.get('mean',r['mean']) if name=='event_adjusted' else r['mean']))
        summary=T.summarize(records,outcomes,reg,{},now,{})
        versions[name]=dict(summary,model='Original 50/50' if name=='original' else POLICY['name'])
    return dict(policy=POLICY,registered_at=registration.get('registered_at'),source_revision=T.read_json(p/'source-filter-revision.json',None),paired_contracts=len(accepted),
                unavailable=Counter(x.get('reason','unknown') for x in pairs if x['state']!='PAIRED'),
                without_event_results=sum(x['evidence_rows']==0 for x in accepted),versions=versions,
                capture=T.read_json(p/'evidence-status.json',{}),ledger_head=pairs[-1]['hash'] if pairs else None,
                unpaired_base_records=len(rows)-len(pairs))
