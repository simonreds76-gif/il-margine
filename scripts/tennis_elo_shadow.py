"""Isolated full-hybrid Elo comparison. Paper only; no pricing writes or messages.

The production module is compiled in memory with an early return before all
publication/alert hooks. Its arithmetic is unchanged. A second identical solve
must reproduce every output before the raw Elo source and opponent average change.
"""
from __future__ import annotations
import argparse, ast, contextlib, copy, csv, gzip, hashlib, importlib.util, io, json, math, os, sys, types
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import requests
from tennis_elo_rebuild import VERSION, atomic, digest, read_csv, rebuild, sha

RELATIVE=Path('data/tennis-elo-rebuild')
MODEL_FILES=('scripts/oncourt-compute-fair-odds.py','scripts/live_model_v2.py','scripts/matchup_model.py','src/lib/tennis_prob.py','scripts/tennis-model-market-gap-audit.py')
DOWNSTREAM_FILES=('scripts/build-tennis-props-board.py','scripts/compute-handicap-values.py','scripts/tennis-props-v3-live.py','scripts/build-tennis-most-aces-board.py')
MAX_EVIDENCE_BYTES=256*1024*1024
MAX_DAILY_CAPTURES=1

def load(path,default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else ({} if default is None else default)
def fixture(r):return ':'.join(str(r.get(k,'')) for k in ('tour_id','round_id'))+':'+':'.join(map(str,sorted([int(r['player1_id']),int(r['player2_id'])])))
def module(path):
    spec=importlib.util.spec_from_file_location('elo_'+path.stem.replace('-','_'),path)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def opponent_averages(root, ratings, as_of):
    # Use the same played-match population/window as the live activity writer.
    # Change its dependent average only; do not change counts/fatigue/reliability.
    act=module(root/'scripts/oncourt-compute-recent-activity.py')
    ids={int(k[0]) for k in ratings}
    activity,_=act.aggregate_activity([root/'data/oncourt/games_atp.csv'],ids,as_of)
    overall={p:v for (p,s),v in ratings.items() if s=='Overall'}
    return {r['player_id']:r['avg_opponent_elo'] for r in act.build_rows(activity,overall)}

def instrument(source):
    anchor='    out, research_components, category_excluded = _compute_fixture_rows("category_corrected")'
    if source.count(anchor)!=1:raise ValueError('Engine entry changed; review required')
    replacement='''    baseline = _compute_fixture_rows("category_corrected", ml_only=ELO_ML_ONLY)
    control = _compute_fixture_rows("category_corrected", ml_only=ELO_ML_ONLY)
    if baseline != control: raise ValueError("Elo identity replay failed")
    old_elo = dict(elo_lookup)
    elo_lookup.clear()
    elo_lookup.update(ELO_CANDIDATE)
    has_overall_elo = any(s == "Overall" for p,s in elo_lookup)
    for pid, row in recent_activity_by_player.items():
        if pid in ELO_OPPONENTS:
            row["avg_opponent_elo"] = ELO_OPPONENTS[pid]
    candidate = _compute_fixture_rows("category_corrected", ml_only=ELO_ML_ONLY)
    return {"baseline": baseline, "candidate": candidate, "incumbent_ratings": old_elo}
'''
    source=source.replace(anchor,replacement+anchor,1)
    marker='            exp_games = expected_total_games_from_pmf(match_pmf)'
    if source.count(marker)!=1:raise ValueError('Expected-games instrumentation changed')
    source=source.replace(marker,marker+'\n            elo_raw_expected_games = exp_games',1)
    marker='            # Keep components for offline model research without adding DB columns.'
    if source.count(marker)!=1:raise ValueError('Output instrumentation changed')
    source=source.replace(marker,'''            out[-1]["elo_diagnostics"] = {"raw_expected_games": elo_raw_expected_games,
                "final_expected_games": exp_games_cal, "tournament_adjustment": tournament_total_adjustment,
                "line_shift": ou_shift, "best_of": 5 if totals_best_of_5 else 3,
                "elo_surface_p1": e1_s, "elo_surface_p2": e2_s, "elo_overall_p1": e1_o, "elo_overall_p2": e2_o}
'''+marker,1)
    tree=ast.parse(source)
    tree.body=[n for n in tree.body if not (isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='__name__')]
    return tree

def run_engine(root, candidate, averages, *, request=None, as_of=None, ml_only=False):
    path=root/'scripts/oncourt-compute-fair-odds.py';tree=instrument(path.read_text(encoding='utf-8-sig'))
    m=types.ModuleType('elo_shadow_engine');m.__file__=str(path);sys.modules[m.__name__]=m
    real_request=requests.request;old_argv=sys.argv;packets=[]
    def guarded(method,url,**kw):
        if method.upper()!='GET':raise RuntimeError('Research forbids all HTTP writes')
        r=(request or real_request)(method,url,**kw)
        # No URLs, headers, credentials or account data in research evidence.
        try: body=r.json()
        except ValueError:body=None
        packets.append({'table':url.rsplit('/',1)[-1],'params':kw.get('params',{}),'status':r.status_code,'body':body})
        return r
    import tennis_pricing_context
    original_context=tennis_pricing_context.load_inputs
    def frozen_context(*args,**kwargs):
        value=original_context(*args,**kwargs)
        packets.append({'table':'local_pricing_context','body':value[0]})
        return value
    originals={k:getattr(requests,k) for k in ('request','get','post','patch','put','delete')}
    def forbidden(*a,**k):raise RuntimeError('Research write forbidden')
    try:
        tennis_pricing_context.load_inputs=frozen_context
        requests.request=guarded;requests.get=lambda url,**kw:guarded('GET',url,**kw)
        requests.post=requests.patch=requests.put=requests.delete=forbidden
        exec(compile(tree,str(path),'exec'),m.__dict__)
        m.ELO_CANDIDATE=candidate;m.ELO_OPPONENTS=averages;m.ELO_ML_ONLY=ml_only
        if as_of:
            class Clock(date):
                @classmethod
                def today(cls):return date.fromisoformat(as_of)
            m.date=Clock
        sys.argv=[str(path),'--dry-run','--skip-handicap-values']
        log=io.StringIO()
        with contextlib.redirect_stdout(log):result=m.main()
        return result,packets,log.getvalue()
    finally:
        tennis_pricing_context.load_inputs=original_context
        for k,v in originals.items():setattr(requests,k,v)
        sys.argv=old_argv

def joined(result,arm):
    out,components,excluded=result[arm]
    full={fixture(r):r for r in out}
    return {fixture(r):{**full.get(fixture(r),{}),**r} for r in components},excluded

def input_epoch(root):
    # Research releases the live pipeline lock. Reject overlapping manual refreshes
    # and input changes, rather than delaying the user's urgent pricing work.
    paths=['data/backtest/tennis-on-demand-status.json','data/tennis-context-live/status.json',
           'data/oncourt/games_atp.csv','data/oncourt/stat_atp.csv','data/oncourt/today_atp.csv',
           'data/tennis-props/player-props-baseline.csv','data/tennis-props/player-props-activity.csv']
    return {p:sha(root/p) if (root/p).exists() else None for p in paths}

def manual_pending(root):
    r=load(root/'data/locks/tennis-on-demand-request.json')
    try:return bool(r.get('request_id') and datetime.fromisoformat(r['expires_at'].replace('Z','+00:00'))>datetime.now(timezone.utc))
    except (KeyError,ValueError,TypeError):return False

def capture(root,output,candidate):
    from tennis_category_shadow import load_quotes,quote_for,selection,load_policy,utc
    now=datetime.now(timezone.utc);day=now.date().isoformat()
    if manual_pending(root):return {'skipped':'manual_refresh_has_priority'}
    epoch=input_epoch(root)
    if len(list((output/'evidence').glob(now.strftime('%Y%m%d')+'*.gz'))) >= MAX_DAILY_CAPTURES:
        return {'skipped':'daily_capture_limit'}
    previous_report=load(output/'report.json')
    if previous_report.get('cohorts',{}).get('ATP',{}).get('baseline',{}).get('settled_fixtures',0)>=300:
        return {'skipped':'manual_300_ATP_review_due'}
    if candidate.get('audit',{}).get('source_hashes',{}).get('data/oncourt/games_atp.csv')!=epoch['data/oncourt/games_atp.csv']:raise ValueError('History changed after rebuild')
    if candidate['as_of_exclusive']!=day:raise ValueError('Candidate date differs from capture')
    if (now.date()-date.fromisoformat(candidate['latest_available_result'])).days>7:raise ValueError('Candidate result history stale')
    source=root/'data/oncourt/games_atp.csv'
    if now.timestamp()-source.stat().st_mtime>48*3600:raise ValueError('Native export older than48h')
    hashes={p:sha(root/p) for p in MODEL_FILES}
    registration=load(output/'registration.json')
    if registration and registration['model_hashes']!=hashes:raise ValueError('Live model changed; paired cohort needs review')
    dh={p:sha(root/p) for p in DOWNSTREAM_FILES}
    dr=load(output/'downstream-registration.json')
    if dr and dr['hashes']!=dh:raise ValueError('Downstream model changed; review required')
    quotes,qhash=load_quotes(root,now)
    # No extra odds download; empty prices are a coverage condition, not an edge.
    ratings={(r['player_id'],r['surface']):r['elo'] for r in candidate['ratings']}
    averages=opponent_averages(root,ratings,now.date())
    result,packets,log=run_engine(root,ratings,averages)
    baseline,bexcluded=joined(result,'baseline');challenger,cexcluded=joined(result,'candidate')
    if baseline.keys()!=challenger.keys():raise ValueError('Candidate changed fixture universe')
    if hashes!={p:sha(root/p) for p in MODEL_FILES}:raise ValueError('Source changed during capture')
    from tennis_elo_downstream import enrich
    enriched=enrich(root,[{'key':k,'baseline':a,'candidate':challenger[k]} for k,a in baseline.items()],day)
    completed=datetime.now(timezone.utc)
    if manual_pending(root) or epoch!=input_epoch(root):return {'skipped':'inputs_changed_or_manual_refresh_has_priority'}
    if dh!={p:sha(root/p) for p in DOWNSTREAM_FILES}:raise ValueError('Downstream changed during capture')
    if completed.date()!=now.date():raise ValueError('UTC date changed during capture')
    if hashes!={p:sha(root/p) for p in MODEL_FILES}:raise ValueError('Model changed during downstream evaluation')
    policy=load_policy(root); ledger=load(output/'ledger.json',[]);known={r['key'] for r in ledger};missing=Counter();added=[]
    for key,a in baseline.items():
        if a['official_category']=='Challenger':missing['challenger_v1_stopped_after_negative_replay']+=1;continue
        if key in known:continue
        q,reason=quote_for(a,quotes);missing[reason]+=1
        if not q:continue
        if utc(q['kickoff_iso'])<=datetime.now(timezone.utc):missing['started_during_compute']+=1;continue
        b=challenger[key]
        row={'key':key,'captured_at':completed.isoformat(),'compute_started_at':now.isoformat(),'as_of_exclusive':day,'kickoff':q['kickoff_iso'],
             'tournament':a['tour_name'],'category':a['official_category'],'surface':a['surface'],'player1':a['player1'],'player2':a['player2'],
             'baseline':a,'candidate':b,'quote':q,'baseline_selection':selection(a,q,policy),'candidate_selection':selection(b,q,policy),
             'result':'pending','history_hash':candidate['history_hash'],'rating_hash':candidate['rating_hash'],'model_hashes':hashes}
        added.append(row)
    stamp=now.strftime('%Y%m%dT%H%M%SZ');evidence=output/'evidence'
    data={'captured_at':completed.isoformat(),'compute_started_at':now.isoformat(),'query_responses':packets,'baseline':list(baseline.values()),'candidate':list(challenger.values()),
          'candidate_ratings':candidate['ratings'],'dependent_opponent_averages':averages,
          'source_hashes':{**hashes,**dh},'candidate_hash':candidate['rating_hash'],'quotes_hashes':qhash,'exclusions':{'baseline':bexcluded,'candidate':cexcluded}}
    raw=gzip.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode(),mtime=0)
    evidence.mkdir(parents=True,exist_ok=True)
    if sum(p.stat().st_size for p in evidence.glob('*.gz'))+len(raw)>MAX_EVIDENCE_BYTES:raise ValueError('Evidence capacity reached; preserve records and request archive')
    with (evidence/(stamp+'.json.gz')).open('xb') as f:f.write(raw)
    atomic(output/'ledger.json',ledger+added)
    if not dr:atomic(output/'downstream-registration.json',{'hashes':dh,'started':completed.isoformat()})
    common=[(v,result['incumbent_ratings'][k]) for k,v in ratings.items() if k in result['incumbent_ratings']]
    def sd(v):
        if not v:return None
        mean=sum(v)/len(v);return math.sqrt(sum((a-mean)**2 for a in v)/len(v))
    spread={'common_ratings':len(common),'candidate_sd':sd([x for x,y in common]),'incumbent_sd':sd([y for x,y in common]),
        'common_fixture_elo_difference_sd':{arm:sd([float(r.get('elo_diagnostics',{}).get('elo_surface_p1',1500))-float(r.get('elo_diagnostics',{}).get('elo_surface_p2',1500)) for r in rows.values()]) for arm,rows in [('baseline',baseline),('candidate',challenger)]}}
    latest={'captured_at':completed.isoformat(),'compute_started_at':now.isoformat(),'candidate_as_of':day,'fixtures_compared':len(baseline),'new_forward_fixtures':len(added),'quote_health':dict(missing),'spread':spread,
            'rows':[{'key':k,'baseline':a,'candidate':challenger[k]} for k,a in baseline.items()]}
    atomic(output/'latest.json',latest)
    if not registration:atomic(output/'registration.json',{'version':VERSION,'model_hashes':hashes,'installed_at':now.isoformat(),
        'policy':'existing category-shadow provisional hard/expansion gates; 1u flat paper only, best eligible side per fixture; no actual bets',
        'milestone':300,'promotion':'never automatic; ATP paired log loss primary, edition-clustered uncertainty; downstream harm gates; ROI descriptive',
        'settlement':'completed exact native fixture only; RET/WO remain explicitly excluded from ROI until bookmaker rules verified'})
    return latest

def settle(root,output):
    from tennis_event_integrity import completed_score
    ledger=load(output/'ledger.json',[]);index=defaultdict(list)
    stat_index=defaultdict(list);wanted={r['key'] for r in ledger}
    for g in read_csv(root/'data/oncourt/stat_atp.csv'):
        k=':'.join([g['tour_id'],g['round_id'],*sorted([g['winner_id'],g['loser_id']],key=int)])
        if k in wanted:stat_index[k].append(g)
    for g in read_csv(root/'data/oncourt/games_atp.csv'):
        if g.get('date','')<'2026-10-29':continue
        key=':'.join([g['tour_id'],g['round_id'],*sorted([g['winner_id'],g['loser_id']],key=int)])
        index[key].append(g)
    def quarantine(r, reason):
        r['settlement_health']=reason
        if r['result']=='settled':
            r.setdefault('correction_history',[]).append({k:r.get(k) for k in ('result','y','score','result_date','actual_games','actual_stats')})
            r['result']='quarantined'
            for key in ('y','score','result_date','actual_games','actual_margin_p1','actual_stats'):r.pop(key,None)
    for r in ledger:
        matches=index.get(r['key'],[])
        unique={digest(g):g for g in matches};matches=list(unique.values())
        if len(matches)!=1:
            quarantine(r, 'ambiguous_native_results' if matches else 'result_not_available')
            continue
        g=matches[0];kick=r['kickoff'][:10]
        if not kick<=g['date']<=(date.fromisoformat(kick)+timedelta(days=7)).isoformat():quarantine(r,'result_date_outside_fixture');continue
        if not completed_score(g.get('result')):
            quarantine(r,'unfinished_or_void_rules_unverified');continue
        y=int(int(g['winner_id'])==int(r['baseline']['player1_id']))
        import re
        sets=[(int(a),int(b)) for a,b in re.findall(r'(\d+)-(\d+)',g['result'])]
        outcome={'result':'settled','y':y,'result_date':g['date'],'score':g['result'],'actual_games':sum(a+b for a,b in sets),'settlement_health':'exact_fixture_complete'}
        if r.get('result')=='settled' and any(r.get(k)!=v for k,v in outcome.items()):
            r.setdefault('correction_history',[]).append({k:r.get(k) for k in outcome})
        outcome['actual_margin_p1']=sum(a-b for a,b in sets)*(1 if y else -1)
        stats={digest(g):g for g in stat_index.get(r['key'],[])}
        if len(stats)==1:
            st=next(iter(stats.values()))
            if st['winner_id']==g['winner_id'] and st['loser_id']==g['loser_id']:
                actual={}
                for pid,prefix in [(g['winner_id'],'w'),(g['loser_id'],'l')]:
                    values={}
                    for field in ('ace','df','svpt'):
                        try:
                            v=float(st[prefix+'_'+field])
                            if math.isfinite(v) and v>=0:values[field]=v
                        except (KeyError,ValueError,TypeError):pass
                    actual[pid]=values
                outcome['actual_stats']=actual
        r.update(outcome)
    atomic(output/'ledger.json',ledger);return ledger

def summarize(ledger,arm):
    complete=[r for r in ledger if r['result']=='settled'];bets=[]
    for r in complete:
        s=r[arm+'_selection']
        if s.get('lane'):
            side=s['side'];win=(r['y']==1)==(side=='P1');price=r['quote']['odds1' if side=='P1' else 'odds2']
            bets.append((win,price-1 if win else -1))
    stake=len(bets);profit=sum(x[1] for x in bets)
    ll=lambda p,y:-(y*math.log(max(1e-9,p))+(1-y)*math.log(max(1e-9,1-p)))
    errors=defaultdict(list);h_brier=[];most_ll=[]
    for r in complete:
        pred=r[arm]
        for pr in pred.get('props',[]):
            actual=r.get('actual_stats',{}).get(str(pr['player_id']),{})
            for field,outcome in [('projected_aces','ace'),('projected_dfs','df'),('service_points_estimate','svpt'),('v3_projected_aces','ace')]:
                if actual.get(outcome) is not None and pr.get(field) is not None:
                    errors[field].append(float(pr[field])-actual[outcome])
        if 'actual_margin_p1' in r:
            values=[]
            for line,probs in pred.get('handicap_shape',{}).items():
                values.append((probs[0]-int(r['actual_margin_p1']+float(line)>0))**2)
            if values:h_brier.append(sum(values)/len(values))
        counts=pred.get('count_most_aces',[])
        ac=r.get('actual_stats',{})
        p1=ac.get(str(pred.get('player1_id')),{}).get('ace');p2=ac.get(str(pred.get('player2_id')),{}).get('ace')
        if counts and p1 is not None and p2 is not None and counts[0].get('quote_status')!='BLOCKED_INPUT_QUALITY':
            k='p_player1' if p1>p2 else 'p_player2' if p2>p1 else 'p_draw'
            most_ll.append(-math.log(max(1e-9,float(counts[0][k]))))
    downstream={k:{'observations':len(v),'bias':sum(v)/len(v),'mae':sum(abs(x) for x in v)/len(v)} for k,v in errors.items()}
    downstream['handicap_raw_shape']={'fixtures':len(h_brier),'brier':sum(h_brier)/len(h_brier) if h_brier else None}
    downstream['count_most_aces']={'fixtures':len(most_ll),'log_loss':sum(most_ll)/len(most_ll) if most_ll else None}
    return {'captured_fixtures':len(ledger),'pending_fixtures':sum(r['result']=='pending' for r in ledger),'quarantined_fixtures':sum(r['result']=='quarantined' for r in ledger),'downstream':downstream,'settled_fixtures':len(complete),'settled_bets':stake,'wins':sum(x[0] for x in bets),'losses':sum(not x[0] for x in bets),
        'pending_bets':sum(r['result']=='pending' and bool(r[arm+'_selection'].get('lane')) for r in ledger),
        'stake':stake,'profit':round(profit,6),'roi_pct':100*profit/stake if stake else None,
        'brier':sum((r[arm]['p1_win_prob']-r['y'])**2 for r in complete)/len(complete) if complete else None,
        'log_loss':sum(ll(r[arm]['p1_win_prob'],r['y']) for r in complete)/len(complete) if complete else None,
        'games_bias':sum(r[arm]['elo_diagnostics']['final_expected_games']-r['actual_games'] for r in complete)/len(complete) if complete else None,
        'games_mae':sum(abs(r[arm]['elo_diagnostics']['final_expected_games']-r['actual_games']) for r in complete)/len(complete) if complete else None}

def report(output):
    ledger=load(output/'ledger.json',[]);latest=load(output/'latest.json');c=load(output/'candidate.json');health=load(output/'health.json')
    cohorts={label:[r for r in ledger if (r['category']=='Challenger')==chall] for label,chall in [('ATP',False),('Challenger',True)]}
    result={'name':'Elo Rebuild','version':VERSION,'status':'PAPER_ONLY','generated_at':datetime.now(timezone.utc).isoformat(),
        'capture_health':health,'last_capture':latest.get('captured_at'),'history_through':c.get('latest_available_result'),'history_matches':c.get('history_matches'),
        'ratings':len(c.get('ratings',[])),'new_forward_fixtures':latest.get('new_forward_fixtures',0),'fixtures':len(ledger),
        'pending':sum(r['result']=='pending' for r in ledger),'cohorts':{label:{a:summarize(rows,a) for a in ('baseline','candidate')} for label,rows in cohorts.items()},
        'quote_health':latest.get('quote_health',{}),'spread':latest.get('spread',{}),'source_gaps':c.get('audit',{}).get('archive_reconciliation',{}),
        'notes':['Raw K22 ratings rebuilt separately; existing live Elo and formulas untouched.','Forward paper record only; one unit hypothetical, no betting alerts.',
                 'Historical source reconstruction is separate and is not a live-vintage backtest.','300 settled priced ATP fixtures trigger manual review; negative/inconclusive ends v1, never automatic promotion.', 'Challenger v1 failed retrospective validation. New Challenger captures stopped; initial records retained.', 'Unpriced fixtures remain in evidence. Unverified kickoff timing excludes them from forward calibration.', 'Handicap diagnostics are raw model shape; no handicap or props ROI without paired recorded prices.']}
    result['historical']=load(output/'historical-report.json')
    result['current_prices']=[{'key':r['key'],'match':r['baseline']['player1']+' vs '+r['baseline']['player2'],
        'category':r['baseline']['official_category'],'tournament':r['baseline']['tour_name'],
        **{a:{'probability':r[a]['p1_win_prob'],'fair1':round(1/r[a]['p1_win_prob'],3),'fair2':round(1/(1-r[a]['p1_win_prob']),3),
            'games':r[a]['elo_diagnostics']['final_expected_games'],'props':r[a].get('props',[])} for a in ('baseline','candidate')}} for r in latest.get('rows',[])]
    result['record']=[{'key':r['key'],'match':r['player1']+' vs '+r['player2'],'kickoff':r['kickoff'],'result':r['result'],
        'score':r.get('score'),'quote':r['quote'],'captured_at':r['captured_at'],
        **{a:{'probability':r[a]['p1_win_prob'],'selection':r[a+'_selection']} for a in ('baseline','candidate')}} for r in ledger[-100:]]
    result['record_limit']=100
    atomic(output/'report.json',result)
    # Flat rows are consumable by the existing private Monitor record browser.
    rows=[]
    for r in ledger:
        for arm in ('baseline','candidate'):
            s=r[arm+'_selection'];side=s.get('side');q=r['quote'];p=r[arm]['p1_win_prob']
            price=q['odds1' if side=='P1' else 'odds2'] if side else None
            won=((r.get('y')==1)==(side=='P1')) if r['result']=='settled' and side else None
            rows.append({'date':r['kickoff'][:10],'match':r['player1']+' vs '+r['player2'],'model':arm,'tournament':r['tournament'],
                'selection':(r['player1'] if side=='P1' else r['player2']) if side else 'No qualifying selection','market':'ML','odds':price,
                'fair_odds':round(1/(p if side=='P1' else 1-p),3) if side else None,'stake':1 if side else 0,
                'result':('W' if won else 'L') if won is not None else r['result'],'profit':(price-1 if won else -1) if won is not None else None,
                'paper_only':True,'captured_at':r['captured_at']})
    target=output/'selections.csv';stream=io.StringIO(newline='')
    fields=list(rows[0]) if rows else ['date','match','model','selection','market','odds','stake','result','profit','paper_only']
    w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
    tmp=target.with_suffix('.tmp');tmp.write_text(stream.getvalue(),encoding='utf8');tmp.replace(target)
    return result

def weekly_text(r):
    if not r:return 'ELO REBUILD | evidence unavailable; live unchanged.'
    atp=r.get('cohorts',{}).get('ATP',{})
    current=atp.get('baseline',{})
    lines=['ELO REBUILD | ATP paper comparison; live unchanged',f"History through {r.get('history_through','unavailable')} | {current.get('captured_fixtures',0)} ATP pairs | {current.get('pending_fixtures',0)} pending fixtures."]
    for arm,m in atp.items():
        roi=f"{m['roi_pct']:+.2f}%" if m.get('roi_pct') is not None else 'not available'
        lines.append(f"{arm}: {m['wins']}W/{m['losses']}L, {m['stake']}u, {m['profit']:+.2f}u; ROI {roi}; {m['pending_bets']} pending bets.")
    if current.get('quarantined_fixtures',0):lines.append(f"RESULTS NEED REVIEW: {current['quarantined_fixtures']} quarantined fixtures excluded from ROI.")
    action=r.get('capture_health',{}).get('capture_action')
    if action and action not in ('captured','daily_capture_limit'):lines.append('CAPTURE: '+action.replace('_',' '))
    if r.get('capture_health',{}).get('status')=='failed':lines.append('CAPTURE NEEDS ATTENTION: '+r['capture_health'].get('error','unknown'))
    lines.append('Review at 300 settled priced ATP fixtures; no automatic promotion.')
    return '\n'.join(lines)

@contextlib.contextmanager
def process_lock(output):
    handle=(output/'.runner.lock').open('a+b')
    try:
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            if handle.read(1)==b'':handle.write(b'0');handle.flush()
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:handle.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path);p.add_argument('--settle-only',action='store_true')
    a=p.parse_args();out=a.output or a.root/RELATIVE;out.mkdir(parents=True,exist_ok=True)
    try:
        with process_lock(out):
            if not a.settle_only:
                c,_=rebuild(a.root,out,datetime.now(timezone.utc).date().isoformat());status=capture(a.root,out,c)
                if status.get('skipped') not in (None,'daily_capture_limit'):
                    declines=load(out/'declines.json',[]);declines.append({'at':datetime.now(timezone.utc).isoformat(),'reason':status['skipped']})
                    atomic(out/'declines.json',declines)
                atomic(out/'health.json',{'status':'ok','checked_at':datetime.now(timezone.utc).isoformat(),'capture_action':status.get('skipped','captured')})
            settle(a.root,out);r=report(out);print(weekly_text(r));return 0
    except BlockingIOError:
        print('Elo Rebuild already running; no duplicate run.');return 0
    except Exception as e:
        atomic(out/'health.json',{'status':'failed','checked_at':datetime.now(timezone.utc).isoformat(),'error':type(e).__name__+':'+str(e)[:300]})
        report(out);print('Elo Rebuild failed; production unchanged:',type(e).__name__,str(e)[:300]);return 1
if __name__=='__main__':raise SystemExit(main())
