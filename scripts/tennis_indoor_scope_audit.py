"""One frozen, chronological indoor-scope paper audit; no live inputs or records written."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import argparse
import csv
import io
import json
import math
from pathlib import Path
from tennis_paper_quote_identity import match_quote, normal, utc
from tennis_indoor_paper import select, completed


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))


def key(r):
    return '|'.join([str(r['tour_id']),str(r['round_id'])]+sorted([str(r['player1_id']),str(r['player2_id'])]))


def audit(root, output):
    now=datetime.now(timezone.utc);root=Path(root);output=Path(output)
    spec=json.loads((output/'indoor-experiment.json').read_bytes())
    packets=[];exclusions=Counter();evidence={}
    for path in sorted((root/'data/tennis-ml-research/components').glob('*/*.json')):
        if path.stat().st_size>1_000_000:continue
        raw=path.read_bytes();packet=json.loads(raw);stamp=utc(packet.get('captured_at'))
        if not stamp or stamp>now:continue
        body=json.dumps(packet.get('rows',[]),sort_keys=True,separators=(',',':'),allow_nan=False)
        if sha256(body.encode()).hexdigest()!=packet.get('payload_sha256'):
            exclusions['component_checksum']+=1;continue
        packets.append((stamp,path,packet));evidence[str(path.relative_to(root))]=sha256(raw).hexdigest()
    quotes_by_date={};captures={};unpriced=set();opportunities=set()
    for stamp,path,packet in sorted(packets,key=lambda x:x[0]):
        day=stamp.date().isoformat()
        if day not in quotes_by_date:
            quotes=[]
            for d in [stamp,stamp-timedelta(days=1)]:
                for f in sorted((root/'data/pinnacle-history').glob(f'pinnacle-history-{d:%Y%m%d}-*.csv')):
                    raw=f.read_bytes();evidence[str(f.relative_to(root))]=sha256(raw).hexdigest()
                    for q in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
                        t,start=utc(q.get('captured_at')),utc(q.get('kickoff_iso'))
                        if not t or not start or q.get('bookmaker','').casefold()!='pinnacle' or q.get('league')!='ATP':continue
                        if q.get('is_live','').lower() in ('true','1') or q.get('capture_mode','').lower() in ('live','inplay','in-play'):continue
                        quotes.append(q)
            quotes_by_date[day]=quotes
        available=[q for q in quotes_by_date[day] if utc(q['captured_at'])<=stamp<utc(q['kickoff_iso'])
                   and stamp-utc(q['captured_at'])<=timedelta(hours=2) and utc(q['kickoff_iso'])-stamp<=timedelta(days=7)]
        rounds_by_pair=defaultdict(set)
        for r in packet['rows']:
            pair=(str(r['tour_id']),*sorted([str(r['player1_id']),str(r['player2_id'])]))
            rounds_by_pair[pair].add(str(r['round_id']))
        for row in packet['rows']:
            if row.get('surface')!='I.hard' or row.get('official_category') not in ('ATP250','ATP500','Masters 1000'):continue
            k=key(row);opportunities.add(k)
            if k in captures:continue
            if row.get('model_policy')!='category_corrected' or row.get('source_contract')!='oncourt-surface-points-20261007-v1':
                exclusions['input_contract']+=1;continue
            if row.get('best_of',3)!=3:exclusions['not_bo3']+=1;continue
            # Historical price gaps are counted explicitly without consulting
            # today's quote diagnostics or substituting a later snapshot.
            if not available:unpriced.add(k);continue
            pair=(str(row['tour_id']),*sorted([str(row['player1_id']),str(row['player2_id'])]))
            identity_row=dict(row,_ambiguous_round_in_snapshot=len(rounds_by_pair[pair])>1)
            q,reason=match_quote(root,identity_row,available,require_current_fixture=False)
            if not q:unpriced.add(k);continue
            p=float(row['p1_win_prob'])
            if not math.isfinite(p) or not 0<p<1:exclusions['invalid_probability']+=1;continue
            # Reuse precisely the original numerical gates; only category scope differs.
            selection=select(p,q,dict(row,official_category='Masters 1000'))
            captures[k]=dict(fixture_key=k,forecast_at=stamp.isoformat(),quote=q,probability=p,
                            model_sha256=packet.get('model_file_sha256'),input_contract=row['source_contract'],
                            category=row['official_category'],tournament=row['tour_name'],tour_id=str(row['tour_id']),
                            round_id=str(row['round_id']),players=[str(row['player1_id']),str(row['player2_id'])],
                            names=[row['player1'],row['player2']],qualifying=int(row['round_id']) in (1,2,3),
                            selection=selection,baseline_selected=selection['qualifies'] and row['official_category']=='Masters 1000',
                            candidate_selected=selection['qualifies'],actual_stake=0,
                            cohort='retrospective_saved_prematch_forecast',source_component=str(path.relative_to(root)))
    # Freeze predictions before reading results.
    prediction_bytes=json.dumps(list(captures.values()),sort_keys=True,indent=2).encode()
    (output/'indoor-predictions-before-outcomes.json').write_bytes(prediction_bytes)
    games=defaultdict(list)
    for g in read_csv(root/'data/oncourt/games_atp.csv'):
        k='|'.join([g['tour_id'],g['round_id']]+sorted([g['winner_id'],g['loser_id']]))
        if k in captures:games[k].append(g)
    rows=[]
    for k,r in captures.items():
        start=utc(r['quote']['kickoff_iso']);matched=[g for g in games[k] if g.get('result','').strip()]
        status='pending';won=None;score=None
        if len(matched)>1:status='ambiguous'
        elif matched:
            g=matched[0];day=datetime.fromisoformat(g['date'][:10]).date();score=g['result'].upper()
            if day<utc(r['forecast_at']).date() or abs((day-start.date()).days)>1:status='ambiguous'
            elif any(x in score for x in ['RET','W/O','WALK','ABD','DEF']):status='void'
            elif completed(score):status='settled';won=int(g['winner_id']==r['players'][0])
            else:status='unfinished'
        side=r['selection']['side'];chosen_won=bool(won==(side==1)) if won is not None else None
        pnl=(r['quote']['odds'+str(side)]-1 if chosen_won else -1) if status=='settled' else (0 if status=='void' else None)
        rows.append(dict(r,status=status,outcome=won,score=score,selection_won=chosen_won,pnl_units=pnl,
                         overdue=status=='pending' and now-start>timedelta(hours=48)))
    def metrics(items):
        settled=[r for r in items if r['status']=='settled'];scores={}
        for name in ['model','market']:
            pairs=[(r['probability'] if name=='model' else r['quote']['market_p1'],r['outcome']) for r in settled]
            scores[name]={'n':len(pairs),'brier':sum((p-y)**2 for p,y in pairs)/len(pairs) if pairs else None,
                          'log_loss':sum(-math.log(p if y else 1-p) for p,y in pairs)/len(pairs) if pairs else None}
        strategies={}
        for label,field in [('baseline','baseline_selected'),('candidate','candidate_selected')]:
            chosen=[r for r in items if r[field]];done=[r for r in chosen if r['status']=='settled'];pnl=sum(r['pnl_units'] for r in done)
            curve=peak=drawdown=0
            for r in sorted(done,key=lambda r:r['quote']['kickoff_iso']):
                curve+=r['pnl_units'];peak=max(peak,curve);drawdown=max(drawdown,peak-curve)
            strategies[label]=dict(selected=len(chosen),settled=len(done),wins=sum(r['selection_won'] for r in done),losses=sum(not r['selection_won'] for r in done),
                                   stake_units=len(done),pnl_units=pnl,roi_pct=100*pnl/len(done) if done else None,max_drawdown=drawdown,
                                   pending=sum(r['status']=='pending' for r in chosen),overdue=sum(r['overdue'] for r in chosen),void=sum(r['status']=='void' for r in chosen))
        reliability=[]
        for i in range(10):
            group=[r for r in settled if i/10<=r['probability']<(i+1)/10]
            reliability.append(dict(bin=[i/10,(i+1)/10],n=len(group),predicted=sum(r['probability'] for r in group)/len(group) if group else None,observed=sum(r['outcome'] for r in group)/len(group) if group else None))
        return dict(fixtures=len(items),settled_fixtures=len(settled),tournament_editions=len({r['tour_id'] for r in settled}),paired_accuracy=scores,strategies=strategies,reliability=reliability)
    report=dict(generated_at=now.isoformat(),spec_sha256=sha256((output/'indoor-experiment.json').read_bytes()).hexdigest(),prediction_sha256=sha256(prediction_bytes).hexdigest(),
                decision='INCONCLUSIVE: NO LIVE CHANGE',exclusions=dict(exclusions),scope_fixtures=len(opportunities),priced_fixtures=len(captures),unpriced_fixtures=len(opportunities-set(captures)),
                all=metrics(rows),added=metrics([r for r in rows if r['category']!='Masters 1000']),
                by_category={c:metrics([r for r in rows if r['category']==c]) for c in ['ATP250','ATP500','Masters 1000']},
                model_cohorts={h:metrics([r for r in rows if r['model_sha256']==h]) for h in sorted({r['model_sha256'] for r in rows})},
                qualifying=metrics([r for r in rows if r['qualifying']]),
                limitations=['Exploratory saved-forecast replay, not a newly issued or prospective betting record.','Scheduled kickoff verified; actual first-serve time not independently verified.','Existing historical selection record unavailable for full issued-Strict parity; baseline is the registered Indoor Scout core policy.','Few tournament editions: no reliable cluster confidence interval or profitability conclusion.','Freshness/price coverage excludes missing contracts; no substituted later odds.'])
    (output/'indoor-results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (output/'indoor-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (output/'indoor-source-hashes.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['scope_fixtures','priced_fixtures','unpriced_fixtures','added','by_category','decision']}))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();audit(args.root,args.output)
