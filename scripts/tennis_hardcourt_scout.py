"""Hardcourt Scout v1: immutable, zero-real-stake Challenger Hard evidence.

Consumes the existing full engine's fresh components and saved Pinnacle quotes.
No HTTP, model fitting, live forecast writes, tips or message delivery.
"""
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import ast, csv, io, json, math, os, re, unicodedata

RELATIVE = Path('data/tennis-ml-research/hardcourt-scout-v1')
NAME = 'Hardcourt Scout'
VERSION = 'hardcourt-scout-v1'
MODEL_FILES = ('scripts/oncourt-compute-fair-odds.py', 'scripts/live_model_v2.py',
               'scripts/matchup_model.py', 'scripts/tennis_tournament_category.py',
               'scripts/tennis_source_contract.py', 'src/lib/tennis_prob.py',
               'scripts/tennis_hardcourt_scout.py')
RULES = {'surface':'Hard', 'category':'Challenger', 'confidence':'high', 'coverage':'HIGH',
         'model_favourite_max':.8, 'minimum_both_prices':1.25, 'max_favourite_gap':.10,
         'side_flip_distance':.03, 'ev_min_pct':10, 'ev_max_pct':15,
         'paper_stake':1, 'actual_stake':0, 'quote_max_age_hours':2,
         'settlement':'completed best-of-three singles; retirement/walkover/default/abandonment void',
         'capture':'first eligible priced forecast per exact edition/round/player pair, including rejected selections'}


def utc(value):
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,TypeError): return None


def read(path, default=None):
    return json.loads(path.read_bytes()) if path.exists() else ({} if default is None else default)


def atomic(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False),encoding='utf8')
    temp.replace(path)


def immutable(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf8') as f: json.dump(data,f,sort_keys=True,allow_nan=False)


@contextmanager
def locked(folder):
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/'worker.lock').open('a+b') as f:
        if os.name=='nt':
            import msvcrt
            if not f.tell():f.write(b'0');f.flush()
            f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def environment(root):
    source=(root/MODEL_FILES[0]).read_text(encoding='utf-8-sig')
    # Only known numerical/model flags; never credentials or arbitrary environment.
    keys=set(re.findall(r'[\"\']((?:FAIR_ODDS_|STRICT_)[A-Z_]+)[\"\']',source))
    keys={k for k in keys if not any(x in k for x in ('SUPABASE','RETR','TIMEOUT','TOKEN','KEY','URL'))}
    return {k:os.environ[k] for k in sorted(keys) if k in os.environ}


def hashes(root):
    # Formatting-only changes do not change the registered model identity.
    return {name:sha256(ast.dump(ast.parse((root/name).read_text(encoding='utf-8-sig')),
                                include_attributes=False).encode()).hexdigest() for name in MODEL_FILES}


def register(root, now=None):
    now=now or datetime.now(timezone.utc);folder=root/RELATIVE
    with locked(folder):
        path=folder/'registration.json'
        if path.exists():return read(path)
        contract_tree=ast.parse((root/'scripts/tennis_source_contract.py').read_text(encoding='utf-8-sig'))
        contract=next(ast.literal_eval(n.value) for n in contract_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in n.targets))
        registration={'name':NAME,'version':VERSION,'registered_at':now.isoformat(),'input_contract':contract,
                      'model_hashes':hashes(root),'model_environment':environment(root), 'rules':RULES,
                      'historical_replay_included':False,'review_milestones':[50,100],
                      'input_note':'Current native inputs going forward; historical reconstruction had missing-input fallbacks. Records are separate.'}
        immutable(path,registration)
        atomic(folder/'capture-status.json',{'state':'CONNECTED_AWAITING_FIRST_RUN','checked_at':now.isoformat(),'captured':0,'actual_stake':0})
    return registration


def select(p,q,m):
    """Exact existing Challenger code-default gates used by the 3,410-fixture replay."""
    a,b=q['odds1'],q['odds2'];market=(1/a)/(1/a+1/b)
    side=1 if p*a-1 >= (1-p)*b-1 else 2
    ev=100*((p if side==1 else 1-p)*(a if side==1 else b)-1)
    reason=None
    if m['surface'] not in {'Hard','Clay','Grass','Indoor','I.hard'}: reason='surface'
    elif m['confidence'].lower()!='high' or m['data_coverage_tag'].upper()!='HIGH': reason='confidence_or_coverage'
    elif max(p,1-p)>.8: reason='model_short_favourite'
    elif min(a,b)<1.25: reason='market_short_favourite'
    elif abs(max(p,1-p)-max(market,1-market))>.10: reason='market_gap'
    elif (p>=.5)!=(market>=.5) and abs(p-.5)>=.03 and abs(market-.5)>=.03: reason='side_flip'
    elif not 10<=ev<=15: reason='edge_outside_10_15'
    return {'side':side,'ev_pct':ev,'qualifies':reason is None,'reason':reason}


def normal(value):
    text=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode().lower()
    return ' '.join(re.findall(r'[a-z0-9]+',text))


def tokens(value):
    return set(normal(value).split())-{'atp','challenger','masters','1000','500','250','qualifying','qualification'}


def quotes(root, now):
    paths=sorted([p for d in (now,now-timedelta(days=1)) for p in (root/'data/pinnacle-history').glob(f'pinnacle-history-{d:%Y%m%d}-*.csv')],reverse=True)[:8]
    rows=[];sources={}
    for path in paths:
        raw=path.read_bytes();sources[path.name]=sha256(raw).hexdigest()
        for q in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
            captured,start=utc(q.get('captured_at')),utc(q.get('kickoff_iso'))
            if not captured or not start or not captured<=now<start:continue
            if now-captured>timedelta(hours=2) or start-now>timedelta(days=7):continue
            if q.get('bookmaker','').casefold()!='pinnacle' or q.get('league')!='Challenger':continue
            if str(q.get('is_live','')).lower() in ('true','1') or q.get('capture_mode','').lower() in ('live','inplay','in-play'):continue
            rows.append(q)
    return rows,sources


def match_quote(row, available):
    names=[normal(row.get('player1')),normal(row.get('player2'))];tour=tokens(row.get('event_key') or row.get('tour_name'))
    if not all(names) or not tour:return None,'missing_identity'
    matches=[q for q in available if {normal(q['player1_name']),normal(q['player2_name'])}==set(names) and tour<=tokens(q['league_name'])]
    if not matches:return None,'no_fresh_matching_price'
    if len({q['kickoff_iso'] for q in matches})!=1:return None,'ambiguous_start'
    latest=max(utc(q['captured_at']) for q in matches);matches=[q for q in matches if utc(q['captured_at'])==latest]
    aligned=[]
    for q in matches:
        rev=normal(q['player1_name'])!=names[0]
        try:a,b=float(q['odds2' if rev else 'odds1']),float(q['odds1' if rev else 'odds2'])
        except (ValueError,TypeError,KeyError):return None,'invalid_price'
        if not all(math.isfinite(x) and x>1 for x in (a,b)):return None,'invalid_price'
        aligned.append((a,b))
    if len(set(aligned))!=1:return None,'conflicting_prices'
    a,b=aligned[0];q=matches[0]
    return dict(odds1=a,odds2=b,market_p1=(1/a)/(1/a+1/b),captured_at=q['captured_at'],
                kickoff_iso=q['kickoff_iso'],bookmaker='Pinnacle',league_name=q['league_name'],
                capture_mode=q.get('capture_mode'),actual_start_verified=False),None


def fixture_key(row):
    values=[str(row[k]) for k in ('tour_id','round_id','player1_id','player2_id')]
    if not all(v.isdigit() and int(v)>0 for v in values) or values[2]==values[3]:raise ValueError('invalid fixture identity')
    return '|'.join(values[:2]+sorted(values[2:]))


def capture(root,rows,now=None,as_of=None,forecast_generated_at=None):
    now=now or datetime.now(timezone.utc);folder=root/RELATIVE
    with locked(folder):
        reg=read(folder/'registration.json');reasons=Counter()
        if not reg or not utc(reg.get('registered_at')) or now<utc(reg['registered_at']):raise ValueError('tracker not registered')
        if reg['model_hashes']!=hashes(root) or reg['model_environment']!=environment(root):raise ValueError('frozen model code or environment changed')
        if reg['rules']!=RULES:raise ValueError('frozen rules changed')
        if str(as_of)!=now.date().isoformat():raise ValueError('forecast must be freshly generated today')
        forecast_stamp=utc(forecast_generated_at) if forecast_generated_at else now
        if not forecast_stamp or not utc(reg['registered_at'])<=forecast_stamp<=now or now-forecast_stamp>timedelta(hours=2):raise ValueError('forecast generation time invalid or stale')
        available,price_hashes=quotes(root,now)
        known_results=set();game_file=root/'data/oncourt/games_atp.csv'
        if game_file.exists():
            with game_file.open(encoding='utf-8-sig',newline='') as f:
                for g in csv.DictReader(f):
                    if g.get('result','').strip():known_results.add('|'.join([g['tour_id'],g['round_id']]+sorted([g['winner_id'],g['loser_id']])))
        seen=set();pending=[]
        for row in rows:
            if row.get('surface')!='Hard' or row.get('official_category')!='Challenger':reasons['outside_scope']+=1;continue
            if row.get('model_policy')!='category_corrected' or row.get('source_contract')!=reg['input_contract']:reasons['input_contract_mismatch']+=1;continue
            key=fixture_key(row)
            if key in known_results:reasons['result_already_known']+=1;continue
            if key in seen:raise ValueError('duplicate fixture')
            seen.add(key);path=folder/'captures'/(sha256(key.encode()).hexdigest()+'.json')
            if path.exists():reasons['already_recorded']+=1;continue
            p=float(row['p1_win_prob'])
            if not math.isfinite(p) or not 0<p<1:raise ValueError('invalid probability')
            q,reason=match_quote(row,available)
            if not q:reasons[reason]+=1;continue
            selection=select(p,q,row)
            pending.append((path,dict(version=VERSION,fixture_key=key,registered_at=now.isoformat(),
                forecast_as_of=str(as_of),forecast_generated_at=forecast_stamp.isoformat(),tour_id=str(row['tour_id']),round_id=str(row['round_id']),
                players=[str(row['player1_id']),str(row['player2_id'])],names=[row['player1'],row['player2']],
                tournament=row['tour_name'],surface='Hard',category='Challenger',
                probability=p,market_probability=q['market_p1'],selection=selection,quote=q,
                components=row,price_hashes=price_hashes,registration_sha256=sha256((folder/'registration.json').read_bytes()).hexdigest(),
                paper_stake=1 if selection['qualifies'] else 0,actual_stake=0)))
        if len(pending)>150:raise ValueError('unexpected fixture volume')
        for path,packet in pending:immutable(path,packet);reasons['captured']+=1
        health={'state':'CAPTURED' if pending else 'WAITING_FOR_ELIGIBLE_FIXTURES','checked_at':now.isoformat(),
                'captured':len(pending),'selected':sum(p['selection']['qualifies'] for _,p in pending),
                'exclusions':dict(reasons),'actual_stake':0}
        atomic(folder/'capture-status.json',health)
    return health


def completed(score):
    clean=re.sub(r'\([^)]*\)','',score.strip())
    parts=clean.split()
    if not parts or any(not re.fullmatch(r'\d+-\d+',s) for s in parts):return False
    w=l=0
    for part in parts:
        a,b=map(int,part.split('-'))
        if w==2 or l==2:return False
        if not ((max(a,b)==6 and min(a,b)<=4) or (max(a,b)==7 and min(a,b) in (5,6))):return False
        w+=a>b;l+=b>a
    return w==2 and l<2


def summarize(root,folder=None,now=None):
    now=now or datetime.now(timezone.utc);folder=folder or root/RELATIVE
    with locked(folder):
        reg=read(folder/'registration.json');records=[read(p) for p in sorted((folder/'captures').glob('*.json'))]
        reg_hash=sha256((folder/'registration.json').read_bytes()).hexdigest() if reg else None
        games=defaultdict(list);game_path=root/'data/oncourt/games_atp.csv';source_hash=None
        if records and game_path.exists():
            raw=game_path.read_bytes();source_hash=sha256(raw).hexdigest()
            wanted={r['fixture_key'] for r in records}
            for g in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
                k='|'.join([g['tour_id'],g['round_id']]+sorted([g['winner_id'],g['loser_id']]))
                if k in wanted:games[k].append(g)
        outcomes={};selected=[];scores=[];exclusions=Counter()
        for r in records:
            k=r['fixture_key'];q=r['quote'];start=utc(q['kickoff_iso']);stamp=utc(r['registered_at']);out={'status':'pending'}
            if r['registration_sha256']!=reg_hash or not stamp or not start or not utc(reg['registered_at'])<=stamp<start or r['actual_stake']!=0:
                out={'status':'quarantined','reason':'capture_integrity'}
            elif start<=now:
                matched=games[k]
                if len(matched)>1:out={'status':'quarantined','reason':'duplicate_or_ambiguous_result'}
                elif matched:
                    g=matched[0];day=date.fromisoformat(g['date'][:10]);score=g.get('result','').upper()
                    if day>now.date() or abs((day-start.date()).days)>1 or day<stamp.date():out={'status':'quarantined','reason':'result_timing'}
                    elif re.search(r'RET|W/O|WALK|DEF|ABD|BYE',score):out={'status':'void','score':score,'date':day.isoformat()}
                    elif completed(score):out={'status':'settled','winner_id':g['winner_id'],'score':score,'date':day.isoformat()}
                    else:out={'status':'pending','reason':'incomplete_or_unrecognised_score'}
            outcomes[k]=out
            if out['status']=='settled':scores.append((r['probability'],r['market_probability'],int(out['winner_id']==r['players'][0])))
            if not r['selection']['qualifies']:exclusions[r['selection']['reason']]+=1;continue
            side=r['selection']['side'];odds=q['odds'+str(side)];won=None;profit=None
            if out['status']=='settled':won=r['players'][side-1]==out['winner_id'];profit=odds-1 if won else -1
            elif out['status']=='void':profit=0
            selected.append(dict(fixture_key=k,kickoff=q['kickoff_iso'],captured_at=r['registered_at'],
                player=r['names'][side-1],opponent=r['names'][2-side],tournament=r['tournament'],
                probability=r['probability'] if side==1 else 1-r['probability'],odds=odds,
                ev_pct=r['selection']['ev_pct'],status=out['status'],reason=out.get('reason'),score=out.get('score'),
                result_date=out.get('date'),won=won,pnl_units=profit,paper_stake=1,actual_stake=0))
        tally=Counter(b['status'] for b in selected);settled=tally['settled'];profit=math.fsum(b['pnl_units'] for b in selected if b['status']=='settled')
        overdue=sum(b['status']=='pending' and now-utc(b['kickoff'])>timedelta(hours=48) for b in selected)
        performance={name:{'n':len(scores),'brier':sum((r[i]-r[2])**2 for r in scores)/len(scores) if scores else None,
                           'log_loss':sum(-math.log(r[i] if r[2] else 1-r[i]) for r in scores)/len(scores) if scores else None}
                     for name,i in [('baseline',0),('market',1)]}
        result={'name':NAME,'version':VERSION,'generated_at':now.isoformat(),'registered_at':reg.get('registered_at'),
                'capture':read(folder/'capture-status.json'),'actual_stake':0,'paper_stake_per_bet':1,
                'registered_fixtures':len(records),'settled_fixtures':len(scores),'selections_total':len(selected),
                'settled':settled,'wins':sum(b['won'] is True for b in selected),'losses':sum(b['won'] is False for b in selected),
                'pending':tally['pending'],'void':tally['void'],'quarantined':tally['quarantined'],'overdue':overdue,
                'recent_pending':tally['pending']-overdue,'stake_units':settled,'pnl_units':profit,
                'roi_pct':100*profit/settled if settled else None,'clv_rows':0,'closing_price_status':'NOT_VERIFIED',
                'as_of_date':max((b['result_date'] for b in selected if b['result_date']),default=None),
                'latest_signal_date':max((b['captured_at'] for b in selected),default=None),
                'review_milestones_reached':[n for n in (50,100) if settled>=n],
                'next_review_at':50 if settled<50 else 100 if settled<100 else None,
                'selections':sorted(selected,key=lambda b:b['captured_at'],reverse=True)[:100],
                'selection_exclusions':dict(exclusions),'paired_accuracy':performance,
                'result_source_sha256':source_hash,'historical_replay_included':False,
                'evidence_period':'prospective paper only; 2026 historical replay excluded',
                'timing_note':'Pre scheduled kickoff only; actual first serve and fill limits unverified.'}
        previous=read(folder/'outcomes.json')
        if previous and previous!=outcomes:
            old_hash=sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest()
            audit=folder/'outcome-history'/f'{old_hash}.json'
            if not audit.exists():immutable(audit,previous)
        atomic(folder/'outcomes.json',outcomes);atomic(folder/'report.json',result)
        return result


def capture_current(root,rows,as_of=None,forecast_generated_at=None):
    """Fail visibly for research without changing or blocking live forecasting."""
    try:
        status=capture(root,rows,as_of=as_of,forecast_generated_at=forecast_generated_at)
        summarize(root)
        return json.dumps(status)
    except Exception as exc:
        atomic(root/RELATIVE/'capture-status.json',{'state':'BLOCKED','checked_at':datetime.now(timezone.utc).isoformat(),
               'reason':str(exc),'actual_stake':0})
        try:summarize(root)
        except Exception:pass
        return 'BLOCKED: see hardcourt-scout-v1/capture-status.json'


def capture_latest(root,now=None):
    """The existing daily price save can follow forecasting; reuse only its fresh packet."""
    now=now or datetime.now(timezone.utc);folder=root/RELATIVE
    reg=read(folder/'registration.json')
    if not reg:return 'not registered'
    packets=[]
    for path in (root/'data/tennis-ml-research/components'/now.strftime('%Y-%m-%d')).glob('*.json'):
        if path.stat().st_size>500_000:continue
        packet=read(path);stamp=utc(packet.get('captured_at'))
        if stamp and utc(reg['registered_at'])<=stamp<=now and now-stamp<=timedelta(hours=2):packets.append((stamp,packet))
    if not packets:return 'No fresh post-registration component packet; next normal forecast required.'
    stamp,packet=max(packets,key=lambda item:item[0])
    if packet.get('model_file_sha256')!=sha256((root/MODEL_FILES[0]).read_bytes()).hexdigest():return 'Component engine version mismatch; new forecast required.'
    body=json.dumps(packet['rows'],sort_keys=True,separators=(',',':'),allow_nan=False)
    if sha256(body.encode()).hexdigest()!=packet.get('payload_sha256'):raise ValueError('component packet checksum mismatch')
    return capture_current(root,packet['rows'],as_of=stamp.date().isoformat(),forecast_generated_at=stamp.isoformat())


def weekly_text(report):
    if not report:return 'Hardcourt Scout: private paper evidence snapshot missing.'
    roi=report.get('roi_pct');record=f"ROI {roi:+.2f}%" if roi is not None else 'ROI awaits first settled selection'
    c=report.get('capture') or {}
    text = (f"Hardcourt Scout | Challenger outdoor hard | PAPER ONLY\n"
            f"{report.get('wins',0)}W / {report.get('losses',0)}L | {record} | {report.get('pnl_units',0):+.2f}u on {report.get('stake_units',0):g}u\n"
            f"{report.get('pending',0)} pending ({report.get('overdue',0)} overdue), {report.get('void',0)} void, {report.get('quarantined',0)} quarantined. "
            f"1u hypothetical stakes; zero real stake. Review at 50 and 100 settled selections. "
            f"Capture {c.get('state','UNKNOWN')} at {c.get('checked_at','unknown')}. "
            f"Report {report.get('generated_at','unknown')}. Historical +22.65% replay excluded; closing prices unverified.")
    if report.get('fable_comparison'):
        from tennis_scout_opposition import weekly_text as comparison_text
        text += '\n' + comparison_text(report['fable_comparison'])
    return text


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--register',action='store_true');args=ap.parse_args()
    if args.register:register(args.root)
    report=summarize(args.root)
    print(weekly_text(report))

