"""Source-attempt accounting for tennis prices; never changes model probabilities."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from hashlib import sha256
import csv, json, math, os

def stamp(v):
    try:
        d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
        return d if d.tzinfo else None
    except (ValueError,TypeError):return None

def atomic(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf8');os.replace(tmp,path)

def expected_books(config):
    books=list(config.get('market_bookmakers',{}).get('tennis_props',[]))
    if config.get('direct_tennis_grosvenor',True):books.append('Grosvenor')
    if config.get('direct_moviodds',{}).get('tennis',False):books.append('Bet365')
    return sorted(set(books))

def source_status(receipt, count):
    if not receipt:return 'NOT_CHECKED'
    status=str(receipt.get('status','')).upper()
    if status in {'DISABLED','MISSING_KEY','SOURCE_FAILED','NOT_CHECKED'}:return status
    if receipt.get('errors'):return 'PARTIAL_FAILURE' if count else 'SOURCE_FAILED'
    if status in {'OK','CAPTURED','NO_VERIFIED_MARKETS','NO_MARKETS'}:
        return 'QUOTES_CAPTURED' if count else 'NO_VERIFIED_MARKETS'
    return 'NOT_CHECKED'

def save_receipt(out, config, sources, artifacts, generated_at):
    allrows=[];files={}
    for kind,path in artifacts.items():
        path=Path(path)
        if not path.exists():continue
        b=path.read_bytes();files[kind]={'name':path.name,'sha256':sha256(b).hexdigest()}
        with path.open(encoding='utf-8-sig',newline='') as f:
            allrows.extend(dict(r,_kind=kind) for r in csv.DictReader(f))
    statuses={}
    for book in expected_books(config):
        rows=[r for r in allrows if r.get('bookmaker')==book]
        supplied=sources.get(book,{})
        statuses[book]={'status':source_status(supplied,len(rows)), 'quotes':len(rows),
                        'checked_at':supplied.get('captured_at') or generated_at,
                        'error_types':[str(e) for e in supplied.get('errors',[])][:20]}
    payload={'schema_version':1,'generated_at':generated_at,'sources':statuses,'artifacts':files,
             'scope':'Configured tennis props sources only; no assertion of full bookmaker catalogue coverage.',
             'all_sources_checked':all(v['status'] not in {'NOT_CHECKED','MISSING_KEY','DISABLED'} for v in statuses.values())}
    atomic(out,payload);return payload

def check_receipt(root, day, *, now=None, max_age=timedelta(minutes=30)):
    """A fresh terminal receipt is required, not merely an old nonempty price CSV."""
    now=now or datetime.now(timezone.utc)
    inbox=Path(root)/'data/tennis-props/inbox'
    try:
        data=json.loads((inbox/f'bookmaker-check-{day}.json').read_text(encoding='utf8'))
        config=json.loads((Path(root)/'config/odds-api-bookmaker-allocation.json').read_text(encoding='utf-8-sig'))
        ts=stamp(data.get('generated_at'))
        if not ts or not timedelta(0)<=now-ts<=max_age:return None,'bookmaker_check_stale'
        expected=expected_books(config)
        if not expected or set(expected)!=set(data.get('sources',{})):return None,'bookmaker_configuration_changed'
        for entry in data['sources'].values():
            checked=stamp(entry.get('checked_at'))
            if not checked or not timedelta(0)<=now-checked<=max_age:
                return None,'bookmaker_source_check_stale'
        for item in data.get('artifacts',{}).values():
            name=item['name']
            if Path(name).name!=name:return None,'invalid_artifact_path'
            path=inbox/name
            if not path.exists() or sha256(path.read_bytes()).hexdigest()!=item['sha256']:
                return None,'bookmaker_snapshot_changed'
        if set(data.get('artifacts',{}))!={'props','most_aces','most_df'}:return None,'bookmaker_snapshot_incomplete'
        if any(x.get('status') in {'NOT_CHECKED','MISSING_KEY','DISABLED'} for x in data['sources'].values()):
            return data,'bookmaker_check_incomplete'
        return data,None
    except (OSError,ValueError,TypeError,KeyError):return None,'bookmaker_check_missing'

def source_note(data):
    return '; '.join(f"{book}: {entry['status'].lower().replace('_',' ')}" for book,entry in sorted(data['sources'].items()))

def retain_candidates(root, day, receipt, now):
    """Immutable audit evidence, including no-bets; never a paper bet ledger."""
    root=Path(root);entries={}
    for name in [f'comparison-{day}.csv',f'comparison-v3-aces-{day}.csv']:
        path=root/'data/tennis-props'/name
        if not path.exists():continue
        with path.open(encoding='utf-8-sig',newline='') as f:
            rows=[r for r in csv.DictReader(f) if stamp(r.get('match_start_utc')) and stamp(r['match_start_utc'])>now
                  and stamp(r.get('capture_ts')) and timedelta(0)<=now-stamp(r['capture_ts'])<=timedelta(minutes=30)]
        if rows:entries[name]={'source_sha256':sha256(path.read_bytes()).hexdigest(),'rows':rows}
    if not entries:return {'state':'NO_FRESH_PREMATCH_CANDIDATES','rows':0}
    stable={'schema_version':1,'scope':'audit only; all candidates including no-bets; no stakes or alerts',
            'source_receipt':receipt,'comparisons':entries}
    encoded=json.dumps(stable,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(encoded)>2*1024*1024:return {'state':'AUDIT_SIZE_LIMIT','rows':0}
    identity=sha256(encoded).hexdigest()
    target=root/'data/tennis-props/gate-evidence'/day/(identity+'.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        with target.open('x',encoding='utf8') as f:
            json.dump(dict(stable,first_observed_at=now.isoformat(),evidence_sha256=identity),f,separators=(',',':'))
    return {'state':'RETAINED','sha256':identity,'rows':sum(len(e['rows']) for e in entries.values()),'path':str(target.relative_to(root))}

def validate_signal(signal, root, receipt, now):
    """Compare the exact advertised contract against the completed source snapshots.

    Never substitute a price into a frozen forecast or bypass its trading gates.
    If a better valid quote was not evaluated, hold this alert and record why.
    """
    from tennis_paper_prices import norm
    source=signal.performance_source
    market=source.get('market','')
    kind='most_aces' if market=='most_aces' else 'most_df' if market=='most_df' else 'props'
    inbox=Path(root)/'data/tennis-props/inbox'
    with (inbox/receipt['artifacts'][kind]['name']).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    three=kind!='props'
    player1=source.get('player1') or source.get('player')
    player2=source.get('player2') or source.get('opponent')
    if not player1 or not player2:return 'signal_identity_missing',[]
    pair=sorted([norm(player1),norm(player2)])
    side=source.get('recommended_side') if source.get('bettable')=='true' else source.get('shadow_side')
    if three:
        side=source.get('recommended_side')
        subject='tie' if side=='DRAW' else norm(player1 if side=='P1' else player2) if side in {'P1','P2'} else None
        selected=source.get('selected_odds')
    else:
        subject=norm(player1) if not market.startswith('match_') else 'match'
        selected=source.get(str(side).lower()+'_odds')
    try:selected=float(selected)
    except (ValueError,TypeError):return 'selected_quote_missing',[]
    if not math.isfinite(selected) or selected<=1:return 'selected_quote_invalid',[]
    quotes=[]
    for row in rows:
        if row.get('bookmaker') not in receipt['sources']:continue
        a,b=(row.get('player1'),row.get('player2')) if three else (row.get('player'),row.get('opponent'))
        if sorted([norm(a),norm(b)])!=pair:continue
        if row.get('date')!=source.get('date'):continue
        if norm(row.get('tournament'))!=norm(source.get('tournament')):continue
        if source.get('tour') and norm(row.get('tour'))!=norm(source['tour']):continue
        captured,start=stamp(row.get('capture_ts')),stamp(row.get('match_start_utc'))
        if not captured or not start or not captured<=now<start or now-captured>timedelta(minutes=30):continue
        if start!=stamp(signal.scheduled_start_utc):return 'conflicting_current_kickoff',[]
        if three:
            field='draw' if subject=='tie' else 'player1' if norm(a)==subject else 'player2' if norm(b)==subject else None
            if field is None:continue
            price=row.get(field+'_odds')
            required=('player1_odds','draw_odds','player2_odds')
        else:
            if row.get('market')!=market:continue
            if subject!='match' and norm(a)!=subject:continue
            try:
                if float(row['line'])!=float(source['line']):continue
            except (ValueError,TypeError,KeyError):continue
            # Milestones intentionally have one side. The upstream gate owns
            # market completeness; execution compares the exact offered side.
            price=row.get(str(side).lower()+'_odds');required=(str(side).lower()+'_odds',)
        try:
            if any(not math.isfinite(float(row[k])) or float(row[k])<=1 for k in required):continue
            price=float(price)
        except (ValueError,TypeError,KeyError):continue
        quotes.append({'bookmaker':row['bookmaker'],'odds':price,'captured_at':captured.isoformat()})
    own=[q for q in quotes if q['bookmaker']==source.get('bookmaker') and abs(q['odds']-selected)<1e-7]
    if not own:return 'selected_quote_not_current',quotes
    if any(q['odds']>selected+1e-7 for q in quotes):return 'better_quote_not_evaluated',quotes
    return None,quotes

def preflight(signals, root, day, *, now=None):
    """Existing tennis props alerts only; ML/Pinnacle lanes remain independent."""
    now=now or datetime.now(timezone.utc)
    receipt,problem=check_receipt(root,day,now=now)
    accepted=[];checks=[]
    for s in signals:
        market=s.performance_source.get('market','')
        applicable=market in {'aces','double_faults','match_aces','match_double_faults','most_aces','most_df'} or 'break' in market
        if not applicable:accepted.append(s);continue
        reason,quotes=(problem,[]) if problem else validate_signal(s,root,receipt,now)
        checks.append({'key':list(s.key),'market':market,'status':reason or 'VERIFIED',
                       'quotes':quotes,'sources':receipt.get('sources',{}) if receipt else {}})
        if reason:continue
        # This text describes captured quotes, never claims whole-site market coverage.
        shown=', '.join(f"{q['bookmaker']} {q['odds']:.2f}" for q in sorted(quotes,key=lambda q:-q['odds']))
        quoted={q['bookmaker'] for q in quotes}
        missing=[f"{b}: {v['status'].lower().replace('_',' ')}; no matching validated quote" for b,v in receipt['sources'].items() if b not in quoted]
        # Remove the older comparison suffix, avoiding duplicate lists.
        s.selection=s.selection.split(' | compared: ')[0]+' | compared: '+shown
        if missing:s.selection+=' | partial comparison: '+'; '.join(missing)
        accepted.append(s)
    report={'checked_at':now.isoformat(),'scope':'existing tennis props delivery',
            'accepted':sum(c['status']=='VERIFIED' for c in checks),
            'held':sum(c['status']!='VERIFIED' for c in checks),'checks':checks,
            'models_changed':False,'alerts_sent_by_check':0}
    try:report['candidate_evidence']=retain_candidates(root,day,receipt,now)
    except (OSError,ValueError,TypeError) as exc:report['candidate_evidence']={'state':'AUDIT_WRITE_FAILED','error_type':type(exc).__name__}
    atomic(Path(root)/'data/backtest/tennis-bookmaker-preflight.json',report)
    return accepted,report

def v4_price_check(row, root, now):
    from types import SimpleNamespace
    receipt,problem=check_receipt(root,now.date().isoformat(),now=now)
    if problem:return problem,[],''
    source=dict(row,bettable='true',recommended_side='OVER',over_odds=row.get('selected_odds'))
    signal=SimpleNamespace(performance_source=source,scheduled_start_utc=row.get('match_start_utc'))
    problem,quotes=validate_signal(signal,root,receipt,now)
    quoted={q['bookmaker'] for q in quotes}
    note='; '.join(f"{b}: {v['status'].lower().replace('_',' ')}; no matching validated quote" for b,v in receipt['sources'].items() if b not in quoted)
    return problem,quotes,note
