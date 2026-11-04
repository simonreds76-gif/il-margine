#!/usr/bin/env python3
"""Refresh saved tennis evidence from local results, independent of new captures.

No new forecasts, prices, model fits, Telegram dispatch or remote database reads.
Frozen forecast ledgers and existing quarantine decisions are preserved.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def protected_row(row):
    note=row.get('settlement_note','')
    return (row.get('settlement_status')=='quarantined' or bool(row.get('quarantine_reason'))
            or bool(row.get('duplicate_of_signal_id')) or note.startswith('duplicate_')
            or note.startswith('void_replaced_match'))


def cancellation(row, resolutions, normalize):
    pair=sorted((normalize(row.get('player') or row.get('player1','')),normalize(row.get('opponent') or row.get('player2',''))))
    for item in resolutions:
        if (item.get('outcome')=='VOID' and item.get('source_url')
            and (not item.get('tour') or item['tour']==row.get('tour'))
            and (not item.get('tournament') or normalize(item['tournament'])==normalize(row.get('tournament','')))
            and item['from']<=row.get('date','')<=item['to'] and pair==sorted(map(normalize,item['players']))):
            return item
    return None


def apply_capture_lifecycle(result, name, current_config):
    """Keep operational retirement separate from the frozen forecast config."""
    if name == 'full-refresh-v1' and current_config.get('capture_enabled') is False:
        result['capture_enabled'] = False
        result['revision_note'] = current_config.get('retirement_reason', 'New comparison capture retired; retain and settle existing forecasts.')
        if not result.get('error') and result.get('status') not in ('BLOCKED', 'SOURCE_MISSING'):
            result['status'] = 'SOURCE_UPGRADE_APPLIED_SETTLING'
    return result


def write_paired_report(folder, result, atomic_json):
    atomic_json(folder / 'report.json', result)
    if folder.name == 'full-refresh-v1':
        from tennis_full_refresh_reporting import build
        # Settlement updates outcomes without running the capture pipeline.
        # Keep milestone ROI synchronized with that exact new report.
        atomic_json(folder / 'milestones.json', build(folder))


def apply_paired_cancellations(records, outcomes, resolutions, normalize, now):
    """Resolve explicitly reviewed withdrawals without modifying predictions."""
    changed = 0
    for record in records:
        if record['id'] in outcomes:
            continue
        void = cancellation(record['row'], resolutions, normalize)
        if void:
            outcomes[record['id']] = {'status': 'void', 'actual': None,
                'settled_at': now.isoformat(), 'source': 'verified_cancellation',
                'source_url': void['source_url'], 'source_evidence_sha256':void.get('source_evidence_sha256'), 'reason': void['reason']}
            changed += 1
    return changed


def run(code_root, data_root, source, recheck=False):
    sys.path.insert(0,str(code_root/'scripts'))
    def load(name): return runpy.run_path(str(code_root/'scripts'/name))
    M=load('tennis-props-settle-shadow.py')
    base=data_root/'data/tennis-props/shadow';now=datetime.now(timezone.utc)
    simple=['aces-dfs-shadow-signals.csv','aces-v3-shadow-signals.csv','venue-ace-factor-v1-observations.csv']
    groups={n:M['read_csv'](base/n) for n in simple}
    v4=M['read_csv'](base/'aces-over-v4-observations.csv')
    F=load('tennis-most-aces-forecast.py');forecasts=F['read_csv'](base/'most-aces-1x2-forecasts.csv')
    from tennis_most_aces_settlement import pending_signals, settle_priced, refresh_current_records
    from tennis_most_aces_current import record as priced_record
    priced_shadow=load('tennis-most-aces-shadow.py')
    priced_rows=M['read_csv'](base/'most-aces-1x2-observations.csv')
    P=load('tennis-props-rate-trend-prospective.py');paired={}
    signals=[r for rows in groups.values() for r in rows]+v4+[F['signal_row'](r) for r in forecasts]
    for name in ('rate-trend-v1','full-refresh-v1'):
        folder=base/name
        if not (folder/'observations.jsonl').exists(): continue
        records=P['ledger'](folder/'observations.jsonl');outcomes=P['read_json'](folder/'outcomes.json',{})
        paired[name]=(records,outcomes)
        signals.extend(r['row'] for r in records)
    # Historical settled rows need reporting, not another result lookup. Paired
    # ledgers store outcomes separately, so select their unresolved rows explicitly.
    lookup = [r for rows in groups.values() for r in rows
              if not protected_row(r) and (recheck or r.get('settlement_status', 'pending') in ('', 'pending'))]
    lookup.extend(r for r in v4 if recheck or r.get('settlement_status', 'pending') in ('', 'pending'))
    lookup.extend(F['signal_row'](r) for r in forecasts
                  if recheck or r.get('settlement_status', 'pending') in ('', 'pending'))
    for records, outcomes in paired.values():
        lookup.extend(r['row'] for r in records if r['id'] not in outcomes)
    lookup.extend(pending_signals(priced_rows))
    started = time.monotonic()
    print(f'Settlement lookup: {len(lookup)} unresolved/recheck rows; {len(signals)} retained rows', flush=True)
    idx=M['load_oncourt_index'](source,lookup)
    index_seconds = time.monotonic() - started
    print(f'Settlement index ready in {index_seconds:.2f}s', flush=True)
    timings = {'result_index': round(index_seconds, 3)}
    last_stage = time.monotonic()
    def checkpoint(name):
        nonlocal last_stage
        timings[name] = round(time.monotonic() - last_stage, 3)
        print(f'Settlement stage {name}: {timings[name]:.2f}s', flush=True)
        last_stage = time.monotonic()
    from player_name_matching import fold_name_text
    import re
    norm=lambda name: re.sub(r'[^a-z0-9]+',' ',fold_name_text(name).lower()).strip()
    journal=data_root/'config/tennis-settlement-resolutions.json'
    resolutions=json.loads(journal.read_text()) if journal.exists() else []
    # Official pre-draw withdrawals are not in result exports. Fetch at most four
    # relevant official PDFs, cached daily, only where no exact result exists.
    from tennis_official_withdrawals import collect
    no_result=[r for r in lookup if not any(M['tournament_overlap'](r.get('tournament',''),c.get('tourney_name','')) and abs((M['parse_sackmann_date'](c.get('tourney_date'))-M['parse_signal_date'](r.get('date'))).days)<=3 for c in idx.get((r.get('tour'),M['parse_year'](r.get('date')),M['pair_key'](r.get('player'),r.get('opponent'))),[]))]
    names=[p.get('name','') for tour in ('atp','wta') for p in M['iter_csv'](source/f'players_{tour}.csv')]
    resolutions+=collect(no_result,base/'rate-trend-v1/official-draws',names,now)
    def candidate(row):
        year=M['parse_year'](row.get('date'))
        if not year: return None
        key=(row.get('tour'),year,M['pair_key'](row.get('player'),row.get('opponent')))
        day=M['parse_signal_date'](row.get('date'))
        # OnCourt dates are match dates. Never select another week's meeting.
        pool=[r for r in idx.get(key,[]) if -1 <= (M['parse_sackmann_date'](r.get('tourney_date'))-day).days <= 4
              and M['parse_sackmann_date'](r.get('tourney_date'))<=now.date()]
        return M['choose_candidate'](row,pool)
    counts=Counter()
    for name,rows in groups.items():
        for row in rows:
            if protected_row(row):continue
            status=row.get('settlement_status','pending')
            if status not in ('','pending') and not (recheck and status in ('settled','void')):continue
            void=cancellation(row,resolutions,norm)
            if void:
                row.update(settlement_status='void',result='void',pnl='0.000',actual='',settled_at_utc=now.isoformat(),settlement_note='void_replaced_match:'+void['reason']+' | '+void['source_url'])
                counts[name]+=1;continue
            match=candidate(row)
            if not match: continue
            actual,note=M['market_count'](match,M['norm_text'](row.get('player')),row.get('market',''))
            line=M['parse_float'](row.get('line'));odds=M['parse_float'](row.get('selected_odds'))
            if line is None:continue
            incomplete=M['is_void_score'](match.get('score'))
            # Bet365 count totals already exceeded are determined, including unders.
            determined=__import__('tennis_count_settlement').determined_count(row.get('bookmaker'),row.get('market'),actual,line,match.get('score'))
            if incomplete and not determined:
                result='void';row.update(actual='',pnl='0.000')
            elif actual is None:continue
            else:
                result='calibration' if row.get('decision_mode')==M['BREAK_CALIBRATION_MODE'] else M['result_for'](actual,line,row.get('side','').upper())
                if result!='calibration' and (odds is None or odds<=1):continue
                row.update(actual=str(actual),pnl='' if result=='calibration' else f"{M['pnl_for'](result,odds):.3f}")
            row.update(result=result,settlement_status='void' if result=='void' else 'settled',settled_at_utc=now.isoformat(),settlement_note='oncourt_verified:'+match.get('tourney_name','')+':'+match.get('score',''))
            counts[name]+=1
        M['write_csv'](base/name,rows)
        perf={'aces-dfs-shadow-signals.csv':'aces-dfs-shadow-performance.txt','aces-v3-shadow-signals.csv':'aces-v3-shadow-performance.txt','venue-ace-factor-v1-observations.csv':'venue-ace-factor-v1-performance.txt'}[name]
        M['write_performance'](base/perf,rows)
    V3=load('tennis-props-v3-weekly-report.py')
    payload=V3['build_payload'](V3['load_json'](V3['DEFAULT_GATE']),groups['aces-v3-shadow-signals.csv'])
    for const,value in [('DEFAULT_JSON',json.dumps(payload,indent=2)),('DEFAULT_REPORT',V3['report_text'](payload))]:
        out=data_root/V3[const].relative_to(code_root);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(value,encoding='utf-8')
    # Refresh v4 counts with frozen pricing/weights; register no new observations.
    V=load('tennis-props-aces-over-v4.py')
    checkpoint('props_and_v3')
    for row in v4:
        if row.get('settlement_status') not in ('','pending') and not recheck:continue
        void=cancellation(row,resolutions,norm)
        if void:
            row.update(settlement_status='void',result='void' if row.get('v4_signal')=='true' else '',pnl='0.000' if row.get('v4_signal')=='true' else '',actual='',settled_at_utc=now.isoformat(),settlement_note='void_replaced_match:'+void['reason']+' | '+void['source_url'])
            counts['v4']+=1;continue
        match=candidate(dict(row,tour='ATP',market='aces'))
        if not match:continue
        actual,_=M['market_count'](match,M['norm_text'](row.get('player')),'aces')
        if M['is_void_score'](match.get('score')):
            # Count calibration excludes incomplete matches under its registered convention.
            row.update(settlement_status='void',result='void' if row.get('v4_signal')=='true' else '',pnl='0.000' if row.get('v4_signal')=='true' else '')
        elif actual is not None:
            row.update(settlement_status='settled',actual=str(actual));V['score_row'](row)
        else:continue
        row.update(settled_at_utc=now.isoformat(),settlement_note='oncourt_verified:'+match.get('score',''));counts['v4']+=1
    V['write_csv'](base/'aces-over-v4-observations.csv',v4)
    payload=V['report_payload'](v4,accepted_ladders=0,rejected=Counter(),generated_at=now)
    V['write_report'](data_root/V['DEFAULT_REPORT'].relative_to(code_root),data_root/V['DEFAULT_JSON'].relative_to(code_root),payload)
    checkpoint('aces_v4')
    # Use the Most Aces module's stricter fixture matcher and preserve quarantines.
    for row in forecasts:
        if row.get('settlement_status')!='pending':continue
        void=cancellation(row,resolutions,norm)
        if void:row.update(settlement_status='void',settled_at_utc=now.isoformat(),settlement_source='verified_cancellation',settlement_note=void['reason']+' | '+void['source_url'])
    if recheck:
        for row in forecasts:
            if row.get('settlement_status') not in ('settled','void'):continue
            sig=F['signal_row'](row)
            key=(sig['tour'],int(sig['date'][:4]),M['pair_key'](sig['player'],sig['opponent']))
            if F['choose_forecast_result'](row,idx.get(key,[])):row['settlement_status']='pending'
    counts['most_aces']=F['settle'](forecasts,code_root/'data/sackmann',source,({},idx))
    F['write_csv'](base/'most-aces-1x2-forecasts.csv',forecasts)
    F['write_report'](base/'most-aces-1x2-forecast-report.txt',base/'most-aces-1x2-forecast-report.json',F['report_payload'](forecasts))
    counts['most_aces_priced']=settle_priced(priced_rows,idx,M,priced_shadow)
    priced_shadow['write_csv'](base/'most-aces-1x2-observations.csv',priced_rows)
    priced_shadow['write_report'](base/'most-aces-1x2-performance.txt',priced_rows)
    refresh_current_records(base/'most-aces-current.json',priced_rows,priced_record)
    checkpoint('most_aces')
    # Settling paired experiments never changes their append-only predictions.
    P['SETTLE']['load_oncourt_index']=lambda *a,**kw:idx
    FULL=load('tennis-props-full-refresh-shadow.py') if 'full-refresh-v1' in paired else None
    for name,(records,outcomes) in paired.items():
        old=len(outcomes)
        apply_paired_cancellations(records,outcomes,resolutions,norm,now)
        P['settle'](records,source,outcomes,now)
        folder=base/name;P['atomic_json'](folder/'outcomes.json',outcomes)
        config=P['read_json'](folder/'registration.json',{})['config']
        health={'settlement_only':True,'newly_settled':len(outcomes)-old}
        result=(FULL['summarize'] if name=='full-refresh-v1' else P['report'])(records,outcomes,health,config,now)
        if name=='rate-trend-v1':
            for market, group in result['markets'].items():
                for arm in ('control','candidate'):
                    tallies=Counter()
                    for r in records:
                        out=outcomes.get(r['id'],{})
                        if r['row']['market']!=market or out.get('status')!='settled' or not r[arm+'_side']:continue
                        side=r[arm+'_side'];row=r['row']
                        payoff,win=P['MODEL']['outcomes'](out['actual'],float(row['line']),side,float(row[side.lower()+'_odds']))
                        tallies['pushes' if win is None else 'wins' if win else 'losses']+=1
                    group[arm].update(wins=tallies['wins'],losses=tallies['losses'],pushes=tallies['pushes'],stake_units=group[arm]['bets'])
        previous=P['read_json'](folder/'report.json',{})
        # A settlement refresh does not assert that registration/capture is healthy.
        result['registration_health']=previous.get('registration_health',previous.get('health',{}))
        if previous.get('error'):result.update(error=previous['error'],status=previous.get('status','BLOCKED'))
        current_config=P['read_json'](code_root/'config/tennis-props-full-refresh-v1.json',{}) if name=='full-refresh-v1' else {}
        apply_capture_lifecycle(result,name,current_config)
        write_paired_report(folder,result,P['atomic_json']);counts[name]=len(outcomes)-old
        checkpoint(name)
    VEN=load('tennis-venue-ace-factor-v1-report.py')
    payload=VEN['build_payload'](VEN['read_csv'](code_root/'data/tennis-props/venue-ace-factors.csv'),groups['venue-ace-factor-v1-observations.csv'])
    for const,value in [('DEFAULT_JSON',json.dumps(payload,indent=2)),('DEFAULT_REPORT',VEN['render'](payload))]:
        out=data_root/VEN[const].relative_to(code_root);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(value,encoding='utf-8')
    if (data_root/'data/tennis-ml-research/context-forward-v1').exists():
        checkpoint('venue')
        from tennis_context_forward import summarize, RELATIVE
        summarize(code_root, output=data_root/RELATIVE)
        checkpoint('astra_volume')
    if (data_root/'data/tennis-ml-research/astrissimo-v1').exists():
        from tennis_astrissimo import summarize as summarize_astrissimo, RELATIVE as ASTRISSIMO_RELATIVE
        summarize_astrissimo(code_root, folder=data_root/ASTRISSIMO_RELATIVE)
        checkpoint('astrissimo')
    if (data_root/'data/tennis-ml-research/hardcourt-scout-v1/registration.json').exists():
        from tennis_hardcourt_scout import summarize as summarize_scout, RELATIVE as SCOUT_RELATIVE
        summarize_scout(code_root, folder=data_root/SCOUT_RELATIVE)
        checkpoint('hardcourt_scout')
    if (data_root/'data/tennis-props/shadow/ace-compass-v1/registration.json').exists():
        from tennis_ace_compass import run as settle_ace_compass
        settle_ace_compass(data_root, code_root, settle_only=True)
        checkpoint('ace_compass')
    if (data_root/'data/tennis-props/shadow/sisal-5050-v1/registration.json').exists():
        from tennis_sisal_5050 import run as settle_sisal_5050
        settle_sisal_5050(data_root, settle_only=True)
        checkpoint('sisal_5050')
    report={'generated_at':now.isoformat(),'settlement_changes':dict(counts),'source':'local_oncourt','forecasts_registered':0,
            'lookup_rows':len(lookup),'retained_rows':len(signals),'index_seconds':round(index_seconds,3),
            'stage_seconds':timings,
            'duration_seconds':round(time.monotonic()-started,3)}
    (base/'settlement-refresh-status.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--code-root',type=Path,default=ROOT);p.add_argument('--data-root',type=Path,default=ROOT);p.add_argument('--source',type=Path);p.add_argument('--recheck',action='store_true');a=p.parse_args()
    raise SystemExit(run(a.code_root,a.data_root,a.source or a.code_root/'data/oncourt',a.recheck))
