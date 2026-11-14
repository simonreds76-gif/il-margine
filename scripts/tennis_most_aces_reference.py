"""Frozen paired gate comparison inside Most Aces. No alerts or model changes."""
from __future__ import annotations
import argparse, contextlib, copy, csv, hashlib, json, math, os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from tennis_bookmaker_check import atomic, check_receipt
from tennis_paper_prices import norm, stamp

VERSION = 'most-aces-fixed-reference-v1'
REL = Path('data/tennis-props/shadow/most-aces-fixed-reference-v1')
MODELS = {'v3_aces_gaussian_copula_nb2_evidence_tiers_v3': 'Count',
          'most_aces_direct_1x2_v1_oncourt_20261029': 'Direct'}
SIDES = ('P1', 'DRAW', 'P2')
GAP = 'MODEL_MARKET_GAP_GT_20PP'
CONTRACT = dict(version=VERSION, gap_pp=20, min_ev_pct=8, max_overround=1.2,
                quote_age_seconds=1800, forecast_age_seconds=21600,
                minimum_books=2, paper_stake_units=1, real_stake_units=0,
                alerts=False, models=list(MODELS))

def read(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except FileNotFoundError: return default

def rows(path):
    try:
        with Path(path).open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
    except FileNotFoundError: return []

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def ledger(folder):
    path = folder/'observations.jsonl'
    if not path.exists(): return []
    return [json.loads(s) for s in path.read_text(encoding='utf8').splitlines() if s.strip()]

@contextlib.contextmanager
def locked(folder):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder/'.lock').open('a+b') as f:
        f.seek(0, 2)
        if not f.tell(): f.write(b'0'); f.flush()
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: yield
        finally:
            f.seek(0)
            if os.name == 'nt': msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def registration(root):
    spec = read(root/'config/most-aces-fixed-reference-v1.json', {})
    if spec.get('contract') != CONTRACT or not stamp(spec.get('enabled_at')):
        raise ValueError('fixed_reference_registration_mismatch')
    folder = root/REL
    old = read(folder/'registration.json', None)
    if old is not None and old != spec: raise ValueError('frozen_registration_changed')
    if old is None: atomic(folder/'registration.json', spec)
    return spec

def identity(match, root):
    names = [norm(match.get('player1')), norm(match.get('player2'))]
    if not all(names) or len(set(names)) != 2: raise ValueError('player_identity_missing')
    logs = match.get('tournament_players', [])
    by_name = {norm(r.get('player')): r for r in logs}
    if len(logs)!=2 or len(by_name)!=2 or any(n not in by_name for n in names): raise ValueError('verified_player_ids_missing')
    a, b = [by_name[n] for n in names]
    ids = [str(r.get('player_id') or '') for r in (a, b)]
    tour = str(a.get('tour_id') or '')
    if not tour or str(b.get('tour_id')) != tour or not all(ids) or len(set(ids)) != 2:
        raise ValueError('edition_identity_missing')
    players={p['id']:p.get('name') for p in rows(root/'data/oncourt/players_atp.csv')}
    if any(norm(players.get(pid))!=name for pid,name in zip(ids,names)): raise ValueError('player_id_name_conflict')
    fixtures = [f for f in rows(root/'data/oncourt/today_atp.csv') if f.get('tour_id') == tour
                and {f.get('player1_id'), f.get('player2_id')} == set(ids)]
    fixtures = [f for f in fixtures if not f.get('result', '').strip() and f.get('live', '').strip() in ('', '0')]
    if len(fixtures) != 1 or not fixtures[0].get('round_id'):
        raise ValueError('current_round_unverified')
    edition = next((t for t in rows(root/'data/oncourt/tours_atp.csv') if t.get('id') == tour), {})
    try: edition_day = datetime.fromisoformat(edition['date'][:10]).date()
    except (KeyError, ValueError): raise ValueError('edition_date_unverified')
    return dict(player_names=names, player_ids=ids, tour_id=tour,
                round_id=fixtures[0]['round_id'], edition_date=edition_day.isoformat())

def validated_candidates(match, ident, raw_quotes, sources, now):
    """Complete matching source snapshots only; reference frozen once per decision."""
    names = ident['player_names']
    p = [float(match[k]) for k in ('p_player1', 'p_draw', 'p_player2')]
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in p) or abs(sum(p)-1) > 2e-5:
        raise ValueError('invalid_probability')
    latest = {}
    for q in raw_quotes:
        if ({norm(q.get('player1')), norm(q.get('player2'))} != set(names)
            or norm(q.get('tournament')) != norm(match.get('tournament'))
            or q.get('date') != match.get('date') or q.get('tour') != match.get('tour')): continue
        book, t = q.get('bookmaker'), stamp(q.get('capture_ts'))
        if book not in sources or t is None: continue
        if book not in latest or t > latest[book][0]: latest[book] = (t, [q])
        elif t == latest[book][0]: latest[book][1].append(q)
    candidates, starts = [], set()
    for price in match.get('prices', []):
        r = price.get('candidate')
        if not r: continue
        book = r.get('bookmaker'); obs = stamp(r.get('registered_at_utc'))
        q, start, fg = [stamp(r.get(k)) for k in ('price_captured_at', 'match_start_utc', 'forecast_generated_at')]
        if book not in latest or not all((obs, q, start, fg)): continue
        if not (fg <= now and 0 <= (now-fg).total_seconds() <= 21600
                and q <= obs <= now < start and 0 <= (now-q).total_seconds() <= 1800): continue
        if latest[book][0] != q: continue  # no resurrection of an older valid row
        edition = datetime.fromisoformat(ident['edition_date']).date()
        if not edition-timedelta(days=3) <= start.date() <= edition+timedelta(days=13): continue
        if start.date().isoformat() != r.get('date') or r.get('date') != match.get('date'): continue
        if r.get('model') != match.get('model') or r.get('tour') != match.get('tour'): continue
        rn = [norm(r.get('player1')), norm(r.get('player2'))]
        if set(rn) != set(names) or norm(r.get('tournament')) != norm(match.get('tournament')): continue
        reverse = rn[0] != names[0]
        rp = [float(r[k]) for k in ('p_player1', 'p_draw', 'p_player2')]
        if reverse: rp.reverse()
        if any(abs(x-y) > 1e-9 for x,y in zip(p,rp)): continue
        # Exact current raw vector, not rounded report prices, determines execution.
        vectors = []
        for raw in latest[book][1]:
            if stamp(raw.get('match_start_utc')) != start: raise ValueError('conflicting_current_kickoff')
            o = [float(raw[k]) for k in ('player1_odds','draw_odds','player2_odds')]
            if norm(raw.get('player1')) != names[0]: o.reverse()
            if any(not math.isfinite(v) or v <= 1 for v in o): raise ValueError('invalid_current_quote')
            vectors.append(o)
        if not vectors or any(v != vectors[0] for v in vectors): raise ValueError('conflicting_current_prices')
        o = vectors[0]; inv = [1/x for x in o]; over = sum(inv); market = [x/over for x in inv]
        ev = [(a*b-1)*100 for a,b in zip(p,o)]; side = max(range(3), key=lambda i: ev[i])
        own_gap = max(abs(a-b) for a,b in zip(p,market))*100
        # Preserve confidence and every existing non-price exclusion, recompute only
        # arithmetic from the same stored model p and exact current quote.
        reasons = set(r.get('eligibility_reason','').split('|'))-{'', 'ELIGIBLE_SHADOW', GAP, 'VALUE_LT_8', 'OVERROUND_GT_20'}
        if ev[side] < 8: reasons.add('VALUE_LT_8')
        if over > 1.2: reasons.add('OVERROUND_GT_20')
        canonical = dict(r, player1=match['player1'], player2=match['player2'], recommended_side=SIDES[side],
                         selected_odds=str(o[side]), settlement_status='pending')
        for fields, values in [(('p_player1','p_draw','p_player2'),p),
                               (('open_player1_odds','open_draw_odds','open_player2_odds'),o),
                               (('market_p_player1','market_p_draw','market_p_player2'),market)]:
            canonical.update(zip(fields,map(str,values)))
        starts.add(start)
        candidates.append(dict(book=book, odds=o, market=market, overround=over, ev=ev[side], side=side,
                               own_gap=own_gap, reasons=sorted(reasons), row=canonical, source_candidate=r,
                               quote_at=q.isoformat(), observed_at=obs.isoformat()))
    if len(starts) > 1: raise ValueError('conflicting_current_kickoff')
    if len({q['book'] for q in candidates}) != len(candidates): raise ValueError('duplicate_book_candidates')
    return p,candidates,starts

def decide(match, ident, raw_quotes, sources, now):
    p,candidates,starts=validated_candidates(match,ident,raw_quotes,sources,now)
    valid = [q for q in candidates if q['overround'] <= 1.2]
    if len(valid) < 2: raise ValueError('fewer_than_two_valid_books')
    ranked = min(candidates, key=lambda q:(-q['ev'],q['observed_at'],q['quote_at'],q['book']))
    ref = [median(q['market'][i] for q in valid) for i in range(3)]; total = sum(ref); ref = [v/total for v in ref]
    gap = max(abs(a-b) for a,b in zip(p,ref))*100
    return dict(model=match['model'], identity=ident, date=match['date'], tournament=match['tournament'],
                start=next(iter(starts)).isoformat(), p=p, reference=ref, reference_gap_pp=gap,
                execution=ranked['row'], quotes=candidates, reference_books=[q['book'] for q in valid],
                baseline=dict(selected=not ranked['reasons'] and ranked['own_gap']<=20, gap_pp=ranked['own_gap']),
                fixed_reference=dict(selected=not ranked['reasons'] and gap<=20, gap_pp=gap),
                non_gap_reasons=ranked['reasons'])

def bind_edition_aliases(match, ident, raw_quotes, root, now, shadow=None):
    """Paper-only label bridge, verified against the exact native edition.

    Dates, probabilities, prices and raw files stay unchanged. Undated forecasts
    are not rescheduled here. Original provider labels remain in binding evidence.
    """
    from tennis_tournament_identity import same_edition_label
    native=dict(match,tour_id=ident['tour_id'],player_id=ident['player_ids'][0],opponent_id=ident['player_ids'][1])
    adapted=copy.deepcopy(match); adapted_raw=[]; bindings=[]
    for raw in raw_quotes:
        if (raw.get('date')!=match.get('date') or raw.get('tour')!=match.get('tour')
            or {norm(raw.get('player1')),norm(raw.get('player2'))}!=set(ident['player_names'])
            or norm(raw.get('tournament'))==norm(match.get('tournament'))):
            adapted_raw.append(raw);continue
        if not same_edition_label(raw,native,root):
            adapted_raw.append(raw);continue
        quote=dict(raw,tournament=match['tournament']);adapted_raw.append(quote)
        if shadow is None:
            from tennis_most_aces_current import load_shadow
            shadow=load_shadow()
        candidate=shadow.registration_row(shadow.orient_board(match,quote),quote)
        if candidate:
            # One observation time for this already-collected snapshot. The
            # provider's price_captured_at is retained and must be <= now;
            # registration must not depend on how long label matching takes.
            candidate['registered_at_utc']=now.isoformat()
            binding=dict(provider_tournament=raw['tournament'],forecast_tournament=match['tournament'],
                         tour_id=ident['tour_id'],round_id=ident['round_id'],player_ids=ident['player_ids'],
                         raw_quote_sha256=digest(raw),date_unchanged=True,probabilities_unchanged=True)
            candidate['fixture_label_binding']=binding
            adapted.setdefault('prices',[]).append(dict(candidate=candidate));bindings.append(binding)
    adapted['paper_label_bindings']=bindings
    return adapted,adapted_raw


def capture(root, report, now=None):
    root=Path(root); now=now or datetime.now(timezone.utc); folder=root/REL
    with locked(folder):
        spec=registration(root); old=ledger(folder); known={r['id'] for r in old}; rejected=Counter(); added=[]; alias_bound=0
        receipt, problem=check_receipt(root,now.date().isoformat(),now=now)
        if now < stamp(spec['enabled_at']): problem='before_registration'
        generated=stamp(report.get('generated_at'))
        if not generated or not 0 <= (now-generated).total_seconds() <= 120: problem='current_report_stale'
        if not problem:
            raw=rows(root/'data/tennis-props/inbox'/receipt['artifacts']['most_aces']['name'])
            for match in report.get('matches',[]):
                if match.get('model') not in MODELS: continue
                try:
                    potential=[q for q in raw if q.get('date')==match.get('date') and q.get('tour')==match.get('tour')
                               and {norm(q.get('player1')),norm(q.get('player2'))}=={norm(match.get('player1')),norm(match.get('player2'))}]
                    if not any(p.get('candidate') for p in match.get('prices',[])) and not potential:
                        rejected['no_current_price_candidates']+=1;continue
                    ident=identity(match,root)
                    key=digest([VERSION,match['model'],ident['tour_id'],ident['round_id'],sorted(ident['player_ids'])])
                    if key in known: rejected['already_recorded']+=1; continue
                    bound,bound_raw=bind_edition_aliases(match,ident,raw,root,now)
                    alias_bound+=len(bound['paper_label_bindings'])
                    d=decide(bound,ident,bound_raw,receipt['sources'],now)
                    d['paper_label_bindings']=bound['paper_label_bindings']
                    d.update(id=key,version=VERSION,captured_at=now.isoformat(),registration_sha256=digest(spec),
                             code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                             source_receipt=receipt,forecast_generated_at=match.get('generated_at_utc'))
                    added.append(d); known.add(key)
                except (ValueError,KeyError,TypeError,OverflowError) as exc:
                    rejected[str(exc) if isinstance(exc,ValueError) else type(exc).__name__]+=1
        if added:
            with (folder/'observations.jsonl').open('a',encoding='utf8') as f:
                for d in added: f.write(json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
                f.flush(); os.fsync(f.fileno())
        health=dict(checked_at=now.isoformat(),status='BLOCKED' if problem else 'CAPTURED' if added else 'CHECKED_NO_NEW_COMPARISONS',
                    reason=problem,added=len(added),excluded=dict(rejected),native_edition_alias_candidates=alias_bound,sources=(receipt or {}).get('sources',{}))
        atomic(folder/'capture-status.json',health)
        return summarize(root,now=now)

def pending(root):
    folder=Path(root)/REL; outcomes=read(folder/'outcomes.json',{})
    return [dict(r['execution'],player=r['execution']['player1'],opponent=r['execution']['player2'])
            for r in ledger(folder) if r['id'] not in outcomes]

def failure(root, phase, exc):
    """Make an independent paper-lane failure visible without blocking other models."""
    folder=Path(root)/REL
    status=dict(checked_at=datetime.now(timezone.utc).isoformat(),status='BLOCKED',phase=phase,
                reason=type(exc).__name__+':'+str(exc)[:180])
    atomic(folder/'capture-status.json',status)
    report=read(folder/'report.json',{})
    if report:
        report['capture']=status;atomic(folder/'report.json',report)
    print('Most Aces fixed-reference comparison blocked: '+status['reason'])

def safe_capture(root, report):
    try: return capture(root,report)
    except Exception as exc:
        try: failure(root,'capture',exc)
        except Exception: print('Most Aces fixed-reference status unavailable: '+type(exc).__name__)
        return None

def settle(root, result_index, counts, shadow, now=None):
    """Use the existing bounded result index, pinning edition AND round; no repricing."""
    root=Path(root)
    return settle_cohort(root,root/REL,result_index,counts,shadow,registration,summarize,now)

def settle_cohort(root,folder,result_index,counts,shadow,ensure_registration,summarizer,now=None):
    """Shared exact-result join; each cohort owns its immutable inputs/outcomes."""
    now=now or datetime.now(timezone.utc)
    if not (folder/'registration.json').exists(): return 0
    with locked(folder):
        ensure_registration(root); observations=ledger(folder); outcomes=read(folder/'outcomes.json',{}); added=0; held=Counter()
        for d in observations:
            if d['id'] in outcomes: continue
            row=copy.deepcopy(d['execution']); ident=d['identity']
            if now <= stamp(d['start']): held['not_started']+=1; continue
            key=(row['tour'],int(row['date'][:4]),counts['pair_key'](row['player1'],row['player2']))
            matches=[m for m in result_index.get(key,[]) if str(m.get('_tour_id'))==ident['tour_id']
                     and m.get('_settlement_source')=='oncourt'
                     and str(m.get('round_id'))==ident['round_id']
                     and {norm(m.get('winner_name')),norm(m.get('loser_name'))}==set(ident['player_names'])]
            if len(matches)!=1: held['missing_or_ambiguous_exact_result']+=1; continue
            match=matches[0]
            day=counts['parse_sackmann_date'](match.get('tourney_date'))
            if not day or not stamp(d['captured_at']).date()<=day<=now.date(): held['result_timing_unverified']+=1; continue
            # Actual date is settlement evidence; immutable forecast date is retained.
            row['date']=day.isoformat()
            shadow['settle']([row],{},direct_index={shadow['pair_key'](row['player1'],row['player2']):[match]})
            if row.get('settlement_status') not in ('settled','void'):
                held[row.get('settlement_note','held')]+=1; continue
            outcomes[d['id']]={k:row.get(k) for k in ('settlement_status','outcome','actual_player1_aces','actual_player2_aces','result','pnl','settlement_note')}
            outcomes[d['id']].update(settled_at=now.isoformat(),actual_date=day.isoformat(),result_sha256=digest(match),
                                     tour_id=ident['tour_id'],round_id=ident['round_id'],decision_sha256=digest(d))
            if row['settlement_status']=='settled':
                outcomes[d['id']]['pnl']=float(d['execution']['selected_odds'])-1 if row['result']=='win' else -1.
            added+=1
        atomic(folder/'outcomes.json',outcomes)
        atomic(folder/'settlement-status.json',dict(checked_at=now.isoformat(),newly_settled=added,held=dict(held)))
        summarizer(root,now=now)
        return added

def summarize(root, now=None):
    root=Path(root); folder=root/REL; now=now or datetime.now(timezone.utc)
    ds=ledger(folder); outcomes=read(folder/'outcomes.json',{}); models={}
    for model,label in MODELS.items():
        group=[r for r in ds if r['model']==model]; settled=[r for r in group if outcomes.get(r['id'],{}).get('settlement_status')=='settled']
        cal={}
        for source in ('p','reference'):
            scores=[]; bins=[dict(n=0,predicted_sum=0.,wins=0) for _ in range(10)]
            for r in settled:
                y=SIDES.index(outcomes[r['id']]['outcome']); p=r[source]
                scores.append((sum((v-int(i==y))**2 for i,v in enumerate(p)),-math.log(max(p[y],1e-12))))
                for i,v in enumerate(p):
                    bucket=bins[min(9,int(v*10))];bucket['n']+=1;bucket['predicted_sum']+=v;bucket['wins']+=int(i==y)
            cal[source]=dict(brier=sum(v[0] for v in scores)/len(scores) if scores else None,
                             log_loss=sum(v[1] for v in scores)/len(scores) if scores else None,
                             convention='Three-class summed Brier; natural log loss; fixed ten-bin pooled outcome reliability is descriptive, outcomes within fixture dependent.',
                             reliability=[dict(low=i/10,high=(i+1)/10,n=b['n'],predicted=b['predicted_sum']/b['n'] if b['n'] else None,observed=b['wins']/b['n'] if b['n'] else None) for i,b in enumerate(bins)])
        arms={}
        for arm in ('baseline','fixed_reference'):
            selected=[r for r in group if r[arm]['selected']]; bets=[r for r in settled if r[arm]['selected']]
            profits=[float(outcomes[r['id']]['pnl']) for r in bets]; days=defaultdict(lambda:[0.,0]); selections=[]
            for r,profit in zip(bets,profits):
                day=outcomes[r['id']]['actual_date']; days[day][0]+=profit; days[day][1]+=1
                selections.append(dict(id=r['id'],date=day,bookmaker=r['execution']['bookmaker'],odds=float(r['execution']['selected_odds']),profit=profit))
            curve=[]; cumulative=peak=dd=0.
            for day,(profit,n) in sorted(days.items()):
                cumulative+=profit; peak=max(peak,cumulative); dd=max(dd,peak-cumulative)
                curve.append(dict(date=day,profit=round(profit,6),cumulative=round(cumulative,6),settled=n))
            selected_brier=selected_ll=expected_wins=0.
            for r in bets:
                y=SIDES.index(outcomes[r['id']]['outcome']); p=r['p']
                selected_brier+=sum((v-int(i==y))**2 for i,v in enumerate(p));selected_ll-=math.log(max(p[y],1e-12))
                expected_wins+=p[SIDES.index(r['execution']['recommended_side'])]
            arms[arm]=dict(settled=len(bets),wins=sum(x>0 for x in profits),losses=sum(x<0 for x in profits),stake_units=len(bets),
                           pnl_units=round(sum(profits),6),roi_pct=100*sum(profits)/len(bets) if bets else None,
                           pending=sum(r['id'] not in outcomes for r in selected),
                           overdue=sum(r['id'] not in outcomes and now-stamp(r['start'])>timedelta(days=2) for r in selected),
                           void=sum(outcomes.get(r['id'],{}).get('settlement_status')=='void' for r in selected),
                           no_bets=len(group)-len(selected),max_drawdown_units=dd,selections=selections,
                           selected_brier=selected_brier/len(bets) if bets else None,
                           selected_log_loss=selected_ll/len(bets) if bets else None,selected_expected_wins=expected_wins,
                           history=dict(days=curve,settled=len(bets),profit=round(sum(profits),6),omitted=0,
                                        note='Forward paired comparison only; 1u paper per frozen selection. By actual match date. Historical replay excluded.'))
        changed=[r for r in settled if r['baseline']['selected']!=r['fixed_reference']['selected']]
        models[model]=dict(label=label,fixtures=len(group),settled_fixtures=len(settled),arms=arms,calibration=cal,
                          pending_fixtures=sum(r['id'] not in outcomes for r in group),
                          overdue_fixtures=sum(r['id'] not in outcomes and now-stamp(r['start'])>timedelta(days=2) for r in group),
                          changed_settled=len(changed),editions=len({r['identity']['tour_id'] for r in settled}),
                          added=sum(not r['baseline']['selected'] and r['fixed_reference']['selected'] for r in settled),
                          removed=sum(r['baseline']['selected'] and not r['fixed_reference']['selected'] for r in settled),
                          paired_pnl_difference=arms['fixed_reference']['pnl_units']-arms['baseline']['pnl_units'],
                          paired_pnl_difference_per_opportunity=(arms['fixed_reference']['pnl_units']-arms['baseline']['pnl_units'])/len(settled) if settled else None,
                          decision='KEEP PAPER; no automatic promotion. Edition-cluster uncertainty and precision review required at registered milestones.',
                          calibration_identical_between_gates=True)
    result=dict(version=VERSION,generated_at=now.isoformat(),models=models,capture=read(folder/'capture-status.json',{}),
                settlement=read(folder/'settlement-status.json',{}),real_stake_units=0,alerts=False,
                note='One frozen paired decision per model/fixture. First fresh complete multi-book capture after registration, including no-bets. Probabilities unchanged: both gates have identical full-cohort calibration. No promotion.')
    atomic(folder/'report.json',result); return result

def monitor_rows(report):
    output=[]
    for model,data in report.get('models',{}).items():
        for arm,stats in data['arms'].items():
            fmt=lambda x:'n/a' if x is None else f'{x:.4f}'
            market=data['calibration']['reference']
            coverage='; '.join(f"{b}: {s.get('status','unknown')}" for b,s in report.get('capture',{}).get('sources',{}).items())
            diagnostics=f" Difference per paired fixture {fmt(data['paired_pnl_difference_per_opportunity'])}u. {data['changed_settled']} changed decisions across {data['editions']} editions; descriptive only until at least 30 changed / 10 editions and precision review. Reference Brier/log loss {fmt(market['brier'])}/{fmt(market['log_loss'])}; selected-only model Brier/log loss {fmt(stats['selected_brier'])}/{fmt(stats['selected_log_loss'])}. {data['pending_fixtures']} fixtures await results, {data['overdue_fixtures']} overdue. Capture: {report.get('capture',{}).get('status','not run')}; {coverage}."
            output.append(dict(id='most-aces-reference-'+data['label'].lower()+'-'+arm,
                name='Most Aces '+data['label']+(' (primary)' if data['label']=='Count' else ' (secondary)')+' · '+('current gate (paired)' if arm=='baseline' else 'fixed-reference gate'),
                group='Tennis props',cohort='Forward paper · >=2-book gate comparison',aggregate_eligible=False,date=report['generated_at'],
                note=report['note']+f" Paired P/L difference {data['paired_pnl_difference']:+.2f}u; added {data['added']}, removed {data['removed']} settled selections."+diagnostics,
                settled=stats['settled'],pending=stats['pending'],wins=stats['wins'],losses=stats['losses'],
                stake=stats['stake_units'],profit=stats['pnl_units'],roi=stats['roi_pct'],overdue=stats['overdue'],
                fixtures=data['settled_fixtures'],history=stats['history'],
                calibration={**data['calibration']['p'],'market_brier':data['calibration']['reference']['brier'],
                             'market_log_loss':data['calibration']['reference']['log_loss'],
                             'selected_brier':stats['selected_brier'],'selected_log_loss':stats['selected_log_loss']},
                status=report.get('capture',{}).get('status','Awaiting first capture'),
                capture_at=report.get('capture',{}).get('checked_at'),link=None))
    return output

def weekly_text(report):
    lines=['Most Aces fixed-reference comparison | >=2-book forward paper, no extra alerts']
    for d in report.get('models',{}).values():
        for arm,s in d['arms'].items():
            roi='n/a' if s['roi_pct'] is None else f"{s['roi_pct']:+.2f}%"
            lines.append(f"{d['label']} {arm}: {s['wins']}W/{s['losses']}L | {s['stake_units']}u | {s['pnl_units']:+.2f}u | ROI {roi} | pending {s['pending']}, overdue {s['overdue']}")
        c=d['calibration']['p']; m=d['calibration']['reference']
        fmt=lambda x:'n/a' if x is None else f'{x:.4f}'
        lines.append(f"{d['settled_fixtures']} paired fixtures; model Brier/LL {fmt(c['brier'])}/{fmt(c['log_loss'])}, reference {fmt(m['brier'])}/{fmt(m['log_loss'])}; unchanged probabilities. Added {d['added']}, removed {d['removed']}; paired P/L difference {d['paired_pnl_difference']:+.2f}u.")
        lines.append(f"{'Primary' if d['label']=='Count' else 'Secondary'}: difference per paired fixture {fmt(d['paired_pnl_difference_per_opportunity'])}u; {d['changed_settled']} changed, {d['editions']} editions. Descriptive only until at least 30 changed / 10 editions and precision review. Pending fixtures {d['pending_fixtures']}, overdue {d['overdue_fixtures']}.")
    h=report.get('capture',{}); lines.append(f"Capture: {h.get('status','not yet run')}; {h.get('reason') or h.get('excluded',{})}. Zero real stake; no promotion.")
    lines.append('Bookmaker checks: '+'; '.join(f"{b}: {s.get('status','unknown')}" for b,s in h.get('sources',{}).items()))
    return '\n'.join(lines)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args()
    root=a.root; report=read(root/'data/tennis-props/shadow/most-aces-current.json',{})
    print(weekly_text(capture(root,report)))
