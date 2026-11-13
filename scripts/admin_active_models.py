"""Read-only display adapters for running model lanes omitted by the old Admin UI.

Uses registered selections and saved settlements only. Does not run models, change
eligibility, settle records, or expose blinded experiment arms.
"""
import csv
import json
import math
import os
from datetime import datetime, timezone
from admin_profit_history import daily, load_module, strict_history


def read(path, fallback=None):
    try: return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError): return fallback


def csvrows(path):
    try:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))
    except (OSError, ValueError): return []


def records(path):
    try:
        with path.open(encoding='utf-8-sig') as stream:
            return [json.loads(line) for line in stream if line.strip()]
    except (OSError, ValueError): return []


def finite(value):
    if value in (None, '') or isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def value(raw, *keys):
    return next((finite(raw[k]) for k in keys if finite(raw.get(k)) is not None), None)


def history(entries, expected):
    try:
        ids = [entry[0] for entry in entries]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate dated selections')
        result = daily([(day, profit) for _, day, profit in entries], 'Original recorded selection and settlement cohort; daily results by match date. No backtest rows added.')
        if result['settled'] != expected['settled'] or expected['profit'] is None or abs(result['profit'] - expected['profit']) > .011:
            raise ValueError('Dated results do not reconcile')
        return result
    except (ValueError, TypeError):
        return {'message': 'Dated results do not reconcile with the complete report; headline figures retained.'}


def selection_entries(rows):
    entries = []
    for index, row in enumerate(rows):
        if str(row.get('status', '')).lower() not in ('settled', 'won', 'lost', 'win', 'loss', 'push'):
            continue
        p = value(row, 'pnl_units', 'profit')
        entries.append((row.get('id') or row.get('fixture_key') or str(index), row.get('start') or row.get('kickoff') or row.get('date') or row.get('match_date'), p))
    return entries


def build_active_models(root, sections):
    output = []
    stamp = datetime.now(timezone.utc).isoformat()
    def add(id, name, raw, report, note, *, group='Tennis research', calibration=None, entries=None, link=None, cohort='Forward paper'):
        raw = raw or {}; report = report or {}
        health = report.get('capture') or report.get('health') or {}
        result = dict(id=id, name=name, group=group, cohort=cohort, note=note,
            date=report.get('generated_at') or report.get('updated_at') or report.get('generated_at_utc'),
            settled=value(raw, 'settled'), pending=value(raw, 'pending'), wins=value(raw, 'wins'), losses=value(raw, 'losses'),
            stake=value(raw, 'stake_units', 'staked_units'), profit=value(raw, 'pnl_units'), roi=value(raw, 'roi_pct'),
            status=health.get('state') or health.get('status') or report.get('status') or 'Collecting',
            capture_at=health.get('checked_at'), overdue=value(raw, 'overdue'), fixtures=value(report, 'settled_fixtures', 'independent_fixtures', 'paired_settled_fixtures'),
            calibration=calibration or {}, link=link)
        if result['settled'] == 0:
            result['roi'] = None
        result['history'] = history(entries, result) if entries is not None else {'message': 'A dated selection history is not supplied for this report.'}
        output.append(result)
        return result

    def selection_lanes():
        # Existing live selection lanes use their original reporting policy.
        lane_module = load_module(root, 'strict-policy-performance.py', 'active_monitor_strict')
        lanes = sections.get('tennis_model_evidence', {}).get('lanes', {})
        for key, tag, label in [('grass_bo3','-grass_bo3','Grass BO3'), ('clay_bo3','-clay_bo3','Clay BO3')]:
            report = lanes.get(key, {})
            item = add(key,label,report,report,'Original saved policy and stakes; seasonal lanes remain active outside their tournament window.', group='Tennis match markets',cohort='Model selection ledger',link=f'/admin/models/signals?model=tennis&view=tennis-{tag[1:]}-archive')
            try: item['history'] = strict_history(root,tag,lane_module)
            except (ValueError,KeyError,TypeError,OSError): pass

    def compass():
        compass = sections.get('tennis_ace_compass', {})
        folder = root/'data/tennis-props/shadow/ace-compass-v1'
        observations = records(folder/'observations.jsonl'); outcomes = read(folder/'outcomes.json', {})
        for arm, name in [('candidate','Ace Compass'),('control','Ace Compass · original reference')]:
            entries = []
            for record in observations:
                outcome = outcomes.get(record['id'], {})
                if record[arm]['selected'] and outcome.get('status') == 'settled':
                    row = record['row']
                    profit = float(row['over_odds'])-1 if outcome['actual'] > float(row['line']) else -1
                    entries.append((record['id'],row['match_start_utc'],profit))
            bias = next((b.get(arm,{}) for b in compass.get('bias',[]) if b.get('group')=='All'),{})
            raw=compass.get('arms',{}).get(arm,{})
            add('ace-compass-'+arm,name,raw,compass,'Frozen opponent-adjustment comparison. 1u per saved qualifying selection; historical replay excluded. Probability scores cover all settled observations, not only bets.',calibration={k:v for k,v in dict(raw,**bias).items() if k in ('brier','log_loss','bias_pct')},entries=entries)

    def most_df():
        report = sections.get('tennis_most_df',{})
        add('most-df','Most Double Faults 1X2',report,report,report.get('note','Saved 1u paper benchmark.'),calibration=report.get('calibration'),entries=selection_entries(report.get('selections',[])),link='/admin/models/signals?model=mostdf&view=most-df-current')

    def scout():
        scout = sections.get('tennis_hardcourt_scout',{}).get('fable_comparison',{})
        for arm, name in [('baseline','Hardcourt Scout · paired baseline'),('fable','Hardcourt Scout · Fable correction')]:
            raw=scout.get('arms',{}).get(arm,{})
            add('scout-'+arm,name,raw,dict(scout,generated_at=sections.get('tennis_hardcourt_scout',{}).get('generated_at')),scout.get('note','Frozen paired cohort; not the full Scout ledger.'),calibration=scout.get('accuracy',{}).get(arm,{}),entries=selection_entries(raw.get('selections',[])))

    def rate_trend():
        trend = sections.get('tennis_rate_trend',{})
        folder = root/'data/tennis-props/shadow/rate-trend-v1'
        observations = records(folder/'observations.jsonl'); outcomes=read(folder/'outcomes.json',{})
        for market,label in [('aces','Astra Aces'),('double_faults','Astra DF')]:
            for arm in ['candidate','control']:
                raw=dict(trend.get('markets',{}).get(market,{}).get(arm,{})); entries=[]; pending=0
                for record in observations:
                    row=record['row']; side=record.get(arm+'_side'); outcome=outcomes.get(record['id'],{})
                    if row['market']!=market or not side: continue
                    if not outcome: pending+=1
                    if outcome.get('status')!='settled':continue
                    actual=outcome['actual'];line=float(row['line']);odds=float(row[side.lower()+'_odds'])
                    profit=0 if actual==line else odds-1 if ((actual>line)==(side=='OVER')) else -1
                    entries.append((record['id'],row['match_start_utc'],profit))
                raw.update(settled=raw.get('bets'),pending=pending)
                add('trend-'+market+'-'+arm,label+(' · rate trend' if arm=='candidate' else ' · reference'),raw,trend,trend.get('interpretation',''),calibration={k:v for k,v in raw.items() if k in ['brier']},entries=entries)

    def most_aces():
        most=sections.get('tennis_most_aces_forecast',{}); prices=sections.get('tennis_most_aces_prices',{})
        rows=csvrows(root/'data/tennis-props/shadow/most-aces-1x2-observations.csv')
        for model,label in [('most_aces_direct_1x2_v1_oncourt_20261029','Most Aces · Direct current inputs'),('v3_aces_gaussian_copula_nb2_evidence_tiers_v3','Most Aces · count model')]:
            bets=[r for r in rows if r.get('model')==model and r.get('bet_eligible')=='yes']
            settled=[r for r in bets if r.get('settlement_status')=='settled']
            raw=dict(prices.get(model,{}));raw.update(settled=raw.get('eligible_settled'),stake_units=raw.get('eligible_settled'),pending=sum(r.get('settlement_status')=='pending' for r in bets),wins=sum(float(r['pnl'])>0 for r in settled),losses=sum(float(r['pnl'])<0 for r in settled))
            entries=[(r.get('signal_id') or r.get('observation_id'),r.get('match_date') or r.get('match_start_utc') or r.get('date'),float(r['pnl'])) for r in settled]
            add('most-aces-'+model,label,raw,most,'Only saved bet-eligible priced observations enter ROI. Each model and current input version is separate; calibration covers its forecast observations.',calibration=most.get('models',{}).get(model,{}),entries=entries,link='/admin/models/signals?model=mostaces&view=most-aces-record')

    def count_variants():
        for id,name,filename,report in [
            ('aces-v3','ATP aces v3','aces-v3-shadow-signals.csv',sections.get('tennis_props_v3',{}).get('evidence',{})),
            ('venue-aces','Venue ace factor','venue-ace-factor-v1-observations.csv',sections.get('tennis_venue_ace_factor_v1',{}))]:
            rows=csvrows(root/'data/tennis-props/shadow'/filename)
            settled=[r for r in rows if r.get('settlement_status')=='settled']
            raw=dict(report);raw['stake_units']=report.get('settled')
            raw.update(wins=sum(float(r['pnl'])>0 for r in settled),losses=sum(float(r['pnl'])<0 for r in settled))
            entries=[(r.get('signal_id') or str(i),r.get('match_date') or r.get('match_start_utc') or r.get('date'),float(r['pnl'])) for i,r in enumerate(settled)]
            add(id,name,raw,dict(report,generated_at=sections.get('tennis_props_v3',{}).get('generated_at')),'Separate running paper comparison, using the full retained selection ledger. No promotion implied by a positive period.',calibration={k:v for k,v in report.items() if 'brier' in k},entries=entries)

    def first_return():
        # Keep the registered no-interim-comparison rule. Visibility is not permission
        # to unblind outcomes or create a new synthetic paper strategy.
        first=read(root/'data/tennis-ml-research/first-return-keep-remove-v2/report.json',{})
        blinded=add('first-return','First-return · keep/remove',{},first,
            f"Collecting {first.get('fixtures','unknown')} fixtures. Arm results remain blinded until the registered review ({first.get('descriptive_at','not supplied')}); no interim P/L comparison.",cohort='Active · blinded comparison')
        blinded['history']={'message':'Results intentionally blinded under the frozen protocol; capture and settlement progress remain visible.'}
    errors = []
    for family in [selection_lanes, compass, most_df, scout, rate_trend, most_aces, count_variants, first_return]:
        try: family()
        except (OSError, ValueError, KeyError, TypeError, ImportError, AttributeError) as error:
            errors.append({'family':family.__name__,'error_type':type(error).__name__})
    # These collectors are active but do not yet provide a settled betting ledger.
    category = read(root/'data/tennis-ml-research/category-live-status.json', {})
    packet_paths = sorted((root/'data/tennis-ml-research/category-comparison').glob('*/*.json'))
    category_row=add('category-calibration','Tournament-category calibration',{},
        {'generated_at':category.get('published_at')},
        f"Active paired-input capture: {len(packet_paths)} saved packets. No automatically settled selection ledger is supplied; packets are not bets. Legacy-category diagnostic is not an active live model.",cohort='Active input comparison')
    category_row['history']={'message':'Capture-only comparison: no settled paper betting ledger is available.'}
    overlay=read(root/'data/tennis-ml-research/components/overlay-stage-review-v1/status.json',{})
    item=add('atp-overlays','ATP adjustment-chain comparison',{},
        {'generated_at':overlay.get('checked_at'),'status':overlay.get('state')},
        f"Existing archive collection; {overlay.get('verified_eligible_fixtures',0)} verified eligible fixtures and {overlay.get('verified_settlements',0)} verified settlements. Registered review gates remain unchanged.",cohort='Active archive audit')
    item['history']={'message':'No interim arm contrast before the registered review gate; no synthetic paper bets added.'}
    # BO5 remains in the actual daily pipeline; use its saved report and original policy.
    try:
        rows=csvrows(root/'data/backtest/strict-policy-performance-slam-bo5-weekly.csv')
        report=next((r for r in rows if r.get('scope')=='all_time' and r.get('eval_period')=='clean' and r.get('policy_mode')=='base' and not r.get('bet_type')), {})
        report=dict(report,generated_at=report.get('generated_utc'),pending=report.get('unsettled'))
        item=add('slam-bo5','Grand Slam BO5 handicaps',report,report,'Scheduled seasonal raw-probability comparison. Saved report stake convention; zero real stake. Last report date is shown separately from current activity.',group='Tennis match markets')
        item['history']=strict_history(root,'-slam-bo5',load_module(root,'strict-policy-performance.py','active_monitor_slam'))
    except (ValueError,KeyError,TypeError,OSError):
        errors.append({'family':'slam_bo5','error_type':'display_unavailable'})
    # The review register is independent of the UI. A newly registered family
    # must become a visible coverage warning until its adapter is added.
    covered={'tennis_ml','tennis_gaps','tennis_aces_df','astra_aces_df','tennis_props',
        'tennis_breaks','football_counts','team_fouls','gk_saves','goalscorers','assists',
        'infrastructure','tennis_full_refresh','tennis_category_calibration','hardcourt_scout',
        'ace_compass','sisal_5050','elo_rebuild_v1','tennis_indoor_paper','tennis_breakpoint_c',
        'match_shape','tennis_indoor_expansion','astra_volume_context_v1','astrissimo_v1',
        'match_shape_j1_exploratory_v1','shots_strength_exploratory_v1','atp_overlay_stage_review_v1'}
    register=read(root/'config/model-review-watchlist.json',{}) or {}
    unrepresented=sorted({r.get('id') for r in register.get('families',[])+register.get('candidates',[])
        if r.get('id') and r.get('id') not in covered and not any(x in str(r.get('status','')).upper() for x in ['PAUSED','RETIRED','DISCONTINUED'])})
    return {'generated_at':stamp,'rows':output,'errors': errors, 'unrepresented_running':unrepresented, 'excluded_states':['retired','paused','settlement_only'], 'formula_changes':False}
