"""Single-book evidence inside Most Aces; independent from the frozen paired gate."""
from __future__ import annotations
import copy, hashlib, json, math, os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tennis_most_aces_reference as paired

VERSION='most-aces-single-book-v1'
REL=Path('data/tennis-props/shadow/most-aces-single-book-v1')
CONTRACT=dict(version=VERSION,minimum_complete_books=1,maximum_quality_books=1,gap_pp=20,min_ev_pct=8,max_overround=1.2,
              quote_age_seconds=1800,forecast_age_seconds=21600,paper_stake_units=1,real_stake_units=0,
              alerts=False,models=list(paired.MODELS),selection='current_gate_on_only_quality_book_else_no_bet',paired_ledger_unchanged=True)

def registration(root):
    spec=paired.read(root/'config/most-aces-single-book-v1.json',{})
    if spec.get('contract')!=CONTRACT or not paired.stamp(spec.get('enabled_at')):
        raise ValueError('single_book_registration_mismatch')
    path=root/REL/'registration.json';old=paired.read(path,None)
    if old is not None and old!=spec:raise ValueError('frozen_single_book_registration_changed')
    if old is None:paired.atomic(path,spec)
    return spec

def fixture_key(record):
    ident=record['identity']
    return paired.digest([record['model'],ident['tour_id'],ident['round_id'],sorted(ident['player_ids'])])

def decide(match,ident,raw,sources,now):
    p,candidates,starts=paired.validated_candidates(match,ident,raw,sources,now)
    # Overround/EV/confidence are selection reasons, not missing data. A complete
    # single-book vector is retained as a no-bet when one of those gates fails.
    if not candidates:raise ValueError('no_verified_book_candidates')
    valid=[q for q in candidates if q['overround']<=1.2]
    if len(valid)>=2:raise ValueError('paired_coverage_available')
    q=valid[0] if valid else min(candidates,key=lambda q:(-q['ev'],q['observed_at'],q['quote_at'],q['book']))
    reasons=list(q['reasons'])
    if q['own_gap']>20:reasons.append(paired.GAP)
    selected=not reasons;execution=dict(q['row'],bet_eligible='yes' if selected else 'no',
                                      eligibility_reason='ELIGIBLE_SHADOW' if selected else '|'.join(sorted(reasons)))
    return dict(model=match['model'],identity=ident,date=match['date'],tournament=match['tournament'],
                start=next(iter(starts)).isoformat(),p=p,book_market_p=q['market'],bookmaker=q['book'],
                execution=execution,quote=q,excluded_vectors=[r for r in candidates if r['book']!=q['book']],
                selection=dict(selected=selected,reasons=sorted(reasons),gap_pp=q['own_gap']),
                verified_books=len(candidates),quality_books=len(valid),
                cohort='single_quote' if len(candidates)==1 else 'multiple_quotes_one_quality' if valid else 'no_quality_no_bet',
                gate_comparison_applicable=False,gates_identical_one_book=len(candidates)==1)

def capture(root,report,now=None):
    root=Path(root);now=now or datetime.now(timezone.utc);folder=root/REL
    with paired.locked(folder):
        spec=registration(root);old=paired.ledger(folder);known={r['id'] for r in old};added=[];excluded=Counter()
        paired_keys={fixture_key(r) for r in paired.ledger(root/paired.REL)}
        receipt,problem=paired.check_receipt(root,now.date().isoformat(),now=now)
        if now<paired.stamp(spec['enabled_at']):problem='before_single_book_registration'
        generated=paired.stamp(report.get('generated_at'))
        if not generated or not 0<=(now-generated).total_seconds()<=120:problem='current_report_stale'
        if not problem:
            raw=paired.rows(root/'data/tennis-props/inbox'/receipt['artifacts']['most_aces']['name'])
            for match in report.get('matches',[]):
                if match.get('model') not in paired.MODELS:continue
                try:
                    potential=[q for q in raw if q.get('date')==match.get('date') and q.get('tour')==match.get('tour')
                               and {paired.norm(q.get('player1')),paired.norm(q.get('player2'))}=={paired.norm(match.get('player1')),paired.norm(match.get('player2'))}]
                    if not potential:excluded['no_current_price_candidates']+=1;continue
                    ident=paired.identity(match,root);key=fixture_key(dict(model=match['model'],identity=ident))
                    id=paired.digest([VERSION,key])
                    if id in known:excluded['already_recorded']+=1;continue
                    if key in paired_keys:excluded['already_in_paired_before_single']+=1;continue
                    bound,bound_raw=paired.bind_edition_aliases(match,ident,raw,root,now)
                    d=decide(bound,ident,bound_raw,receipt['sources'],now)
                    d.update(id=id,fixture_id=key,version=VERSION,captured_at=now.isoformat(),
                             registration_sha256=paired.digest(spec),code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                             validation_code_sha256=hashlib.sha256(Path(paired.__file__).read_bytes()).hexdigest(),
                             source_receipt=receipt,forecast_generated_at=match.get('generated_at_utc'),
                             paper_label_bindings=bound['paper_label_bindings'],
                             raw_quotes=potential)
                    added.append(d);known.add(id)
                except (ValueError,KeyError,TypeError,OverflowError) as exc:
                    excluded[str(exc) if isinstance(exc,ValueError) else type(exc).__name__]+=1
        if added:
            with (folder/'observations.jsonl').open('a',encoding='utf8') as f:
                for d in added:f.write(json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
                f.flush();os.fsync(f.fileno())
        paired.atomic(folder/'capture-status.json',dict(checked_at=now.isoformat(),status='BLOCKED' if problem else 'CAPTURED' if added else 'CHECKED_NO_NEW_OBSERVATIONS',
                     reason=problem,added=len(added),excluded=dict(excluded),sources=(receipt or {}).get('sources',{})))
        return summarize(root,now)

def pending(root):
    folder=Path(root)/REL;outcomes=paired.read(folder/'outcomes.json',{})
    return [dict(r['execution'],player=r['execution']['player1'],opponent=r['execution']['player2'])
            for r in paired.ledger(folder) if r['id'] not in outcomes]

def failure(root,phase,exc):
    folder=Path(root)/REL
    status=dict(checked_at=datetime.now(timezone.utc).isoformat(),status='BLOCKED',phase=phase,reason=type(exc).__name__+':'+str(exc)[:180])
    paired.atomic(folder/'capture-status.json',status)
    report=paired.read(folder/'report.json',{})
    if report:report['capture']=status;paired.atomic(folder/'report.json',report)
    print('Most Aces single-book '+phase+' blocked: '+status['reason'])

def safe_capture(root,report):
    try:return capture(root,report)
    except Exception as exc:
        try:failure(root,'capture',exc)
        except Exception:print('Most Aces single-book status unavailable: '+type(exc).__name__)
        return None

def settle(root,result_index,counts,shadow,now=None):
    return paired.settle_cohort(Path(root),Path(root)/REL,result_index,counts,shadow,registration,summarize,now)

def calibration(records,outcomes,field):
    scores=[];bins=[dict(n=0,predicted=0.,actual=0) for _ in range(10)]
    for r in records:
        p=r[field];y=paired.SIDES.index(outcomes[r['id']]['outcome'])
        scores.append((sum((v-int(i==y))**2 for i,v in enumerate(p)),-math.log(max(p[y],1e-12))))
        for i,v in enumerate(p):
            b=bins[min(9,int(v*10))];b['n']+=1;b['predicted']+=v;b['actual']+=int(i==y)
    return dict(n=len(scores),brier=sum(x[0] for x in scores)/len(scores) if scores else None,
                log_loss=sum(x[1] for x in scores)/len(scores) if scores else None,
                reliability=[dict(low=i/10,high=(i+1)/10,n=b['n'],predicted=b['predicted']/b['n'] if b['n'] else None,observed=b['actual']/b['n'] if b['n'] else None) for i,b in enumerate(bins)],
                convention='Three-class summed Brier; natural log loss; ten pooled bins descriptive, outcomes within fixture dependent.')

def summarize(root,now=None):
    root=Path(root);folder=root/REL;now=now or datetime.now(timezone.utc)
    ds=paired.ledger(folder);outcomes=paired.read(folder/'outcomes.json',{})
    paired_keys={fixture_key(r) for r in paired.ledger(root/paired.REL)};models={}
    for model,label in paired.MODELS.items():
        group=[r for r in ds if r['model']==model]
        done=[r for r in group if outcomes.get(r['id'],{}).get('settlement_status')=='settled']
        selected=[r for r in group if r['selection']['selected']];bets=[r for r in done if r['selection']['selected']]
        pnl=[float(outcomes[r['id']]['pnl']) for r in bets];days=defaultdict(lambda:[0.,0])
        for r,profit in zip(bets,pnl):
            d=days[outcomes[r['id']]['actual_date']];d[0]+=profit;d[1]+=1
        cumulative=peak=drawdown=0.;curve=[]
        for day,(profit,n) in sorted(days.items()):
            cumulative+=profit;peak=max(peak,cumulative);drawdown=max(drawdown,peak-cumulative)
            curve.append(dict(date=day,profit=round(profit,6),cumulative=round(cumulative,6),settled=n))
        overlap=[r['id'] for r in group if fixture_key(r) in paired_keys]
        models[model]=dict(label=label,fixtures=len(group),settled_fixtures=len(done),selected=len(selected),no_bets=len(group)-len(selected),
            settled=len(bets),wins=sum(p>0 for p in pnl),losses=sum(p<0 for p in pnl),stake_units=len(bets),pnl_units=round(sum(pnl),6),
            roi_pct=100*sum(pnl)/len(bets) if bets else None,void=sum(outcomes.get(r['id'],{}).get('settlement_status')=='void' for r in selected),
            pending=sum(r['id'] not in outcomes for r in selected),
            overdue=sum(r['id'] not in outcomes and now-paired.stamp(r['start'])>timedelta(days=2) for r in selected),
            pending_fixtures=sum(r['id'] not in outcomes for r in group),
            overdue_fixtures=sum(r['id'] not in outcomes and now-paired.stamp(r['start'])>timedelta(days=2) for r in group),
            calibration=dict(model=calibration(done,outcomes,'p'),book_market=calibration(done,outcomes,'book_market_p'),selected_model=calibration(bets,outcomes,'p')),
            editions=len({r['identity']['tour_id'] for r in done}),books=dict(Counter(r['bookmaker'] for r in group)),cohorts=dict(Counter(r['cohort'] for r in group)),
            overlap_with_paired=len(overlap),overlap_observation_ids=overlap,aggregate_eligible=False,max_drawdown_units=drawdown,
            history=dict(days=curve,settled=len(bets),profit=round(sum(pnl),6),omitted=0,note='Single-book current-gate cohort only; 1u paper, zero real stake. No-bets excluded from stake and P/L. Do not add to paired or source-row totals.'),
            records=[dict(id=r['id'],fixture_id=fixture_key(r),fixture=r['execution']['player1']+' vs '+r['execution']['player2'],date=r['date'],
                bookmaker=r['bookmaker'],odds=float(r['execution']['selected_odds']),side=r['execution']['recommended_side'],selected=r['selection']['selected'],
                cohort=r['cohort'],verified_books=r['verified_books'],quality_books=r['quality_books'],
                reasons=r['selection']['reasons'],captured_at=r['captured_at'],quote_at=r['quote']['quote_at'],
                settlement_status=outcomes.get(r['id'],{}).get('settlement_status','pending'),
                outcome=outcomes.get(r['id'],{}).get('outcome'),
                paper_pnl=float(outcomes[r['id']]['pnl']) if r['selection']['selected'] and outcomes.get(r['id'],{}).get('settlement_status')=='settled' else 0.,
                also_in_paired=r['id'] in overlap) for r in group])
    result=dict(version=VERSION,generated_at=now.isoformat(),models=models,capture=paired.read(folder/'capture-status.json',{}),
        settlement=paired.read(folder/'settlement-status.json',{}),real_stake_units=0,alerts=False,aggregate_eligible=False,
        note='Single-book / limited-coverage current-gate evidence, including no-bets. At most one quality-valid book; excluded high-margin vectors retained. With no quality-valid book the record is always a no-bet. No multi-book consensus or gate-improvement claim. Gates coincide only when exactly one complete book is present. Descriptive only. Separate from >=2-book paired and existing source-row views; never sum these as a portfolio. Frozen first observations; later overlap is derived, not a second bet in any combined total.')
    paired.atomic(folder/'report.json',result);return result

def monitor_rows(report):
    output=[]
    for model,d in report.get('models',{}).items():
        fmt=lambda x:'n/a' if x is None else f'{x:.4f}'
        cal=d['calibration'];book=cal['book_market'];health=report.get('capture',{})
        coverage='; '.join(f"{b}: {s.get('status','unknown')}" for b,s in health.get('sources',{}).items())
        recent='; '.join(f"{r['fixture']} ({r['date']}): {'selected' if r['selected'] else 'no bet: '+', '.join(r['reasons'])}; {r['bookmaker']} {r['odds']:.3f}; {r['settlement_status']}" for r in d['records'][-5:])
        output.append(dict(id='most-aces-single-'+d['label'].lower(),name='Most Aces '+d['label']+(' (primary)' if d['label']=='Count' else ' (secondary)')+' · single-book current gate',
            group='Tennis props',cohort='Forward paper · single-book only',date=report['generated_at'],aggregate_eligible=False,
            note=report['note']+f" {d['fixtures']} captured, {d['selected']} selected, {d['no_bets']} no-bets. Coverage groups: {d['cohorts']}. {d['pending_fixtures']} fixtures awaiting outcomes, {d['overdue_fixtures']} overdue. {d['overlap_with_paired']} also in paired view (not extra bets). Books: {d['books']}. Book-market Brier/LL {fmt(book['brier'])}/{fmt(book['log_loss'])}. {coverage}. Recent observations: {recent}",
            settled=d['settled'],pending=d['pending'],wins=d['wins'],losses=d['losses'],stake=d['stake_units'],profit=d['pnl_units'],roi=d['roi_pct'],
            overdue=d['overdue'],fixtures=d['settled_fixtures'],history=d['history'],calibration={**cal['model'],'market_brier':book['brier'],'market_log_loss':book['log_loss']},
            status=health.get('status','Awaiting first capture'),capture_at=health.get('checked_at'),link=None))
    return output

def weekly_text(report):
    lines=['Most Aces single-book evidence | current gate, separate from paired comparison']
    fmt=lambda x:'n/a' if x is None else f'{x:.4f}'
    for d in report.get('models',{}).values():
        roi='n/a' if d['roi_pct'] is None else f"{d['roi_pct']:+.2f}%"
        lines.append(f"{d['label']}: {d['fixtures']} captured, {d['selected']} selected, {d['no_bets']} no-bets | {d['wins']}W/{d['losses']}L | {d['stake_units']}u | {d['pnl_units']:+.2f}u | ROI {roi} | pending bets {d['pending']}, overdue {d['overdue']}.")
        m=d['calibration']['model'];b=d['calibration']['book_market']
        lines.append(f"{d['settled_fixtures']} settled fixtures, {d['editions']} editions; model Brier/LL {fmt(m['brier'])}/{fmt(m['log_loss'])}, book {fmt(b['brier'])}/{fmt(b['log_loss'])}. Pending outcomes {d['pending_fixtures']}; overdue {d['overdue_fixtures']}. {d['overlap_with_paired']} also in paired view; never add totals. Books {d['books']}; coverage {d['cohorts']}.")
    h=report.get('capture',{});lines.append(f"Capture: {h.get('status','not run')}; {h.get('reason') or h.get('excluded',{})}. Gate comparison not applicable to single-book rows. Descriptive only; zero real stake, no alerts.")
    return '\n'.join(lines)
