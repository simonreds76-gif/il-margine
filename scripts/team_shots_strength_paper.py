"""Frozen Opponent + as-of strength, paired future cohort; no alerts/network."""
import argparse,csv,importlib.util,json,math,sys
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
import frozen_paper_common as C
from football_counts import prob_over
from football_market import blend_logit
from football_fixture_identity import FixtureIndex, fixture, TOP_FIVE
from football_team_names import football_form_team_key as team_key
from football_count_results import count_result_index, exact_result
from tennis_hardcourt_scout import locked

RELATIVE=Path('data/football-form/shots-strength-v1')
PROTOCOL='config/team-shots-strength-paper.json'
ARMS=('opponent','opponent_strength')
FILES=(PROTOCOL,'scripts/team_shots_strength_paper.py','scripts/frozen_paper_common.py',
    'scripts/football_counts.py','scripts/football_market.py','scripts/football_fixture_identity.py',
    'scripts/football_team_names.py','scripts/football_count_results.py',
    'data/team-shots/team-shots-opponent-config.json')

def paired(root):
    spec=importlib.util.spec_from_file_location('_strength_paired',root/'scripts/team-shots-paired-reference.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def csv_rows(path):
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    return []

def normalized(row,P):
    return {**row,'league_slug':P.PUB.league_slug(row.get('competition',''))}

def stable_key(row):
    keys=FixtureIndex().keys(row)
    legs=[k for k in keys if k[0]=='league-home-leg']
    return '|'.join(map(str,legs[0] if legs else sorted(keys)[0]))

def bind_strength(record,quotes,winners,P):
    """Require the exact archived shots contract and its canonical event ID.

    A complete 1X2 response may precede the shots quote by <=3h. It may never
    arrive later. Canonical source event IDs, book, kickoff and ordered teams
    all agree; name similarity alone does not join the markets.
    """
    seen=min(C.utc(v) for v in record['captured_at_utc'].values());ko=C.utc(record['kickoff_utc'])
    if not seen<ko:raise ValueError('non_prematch_shots')
    candidates=[]
    for side in ('over','under'):
        valid=[]
        for raw in quotes:
            r=normalized(raw,P)
            if (r.get('market')!='TEAM_SHOTS' or fixture(r)!=fixture(record) or r.get('bookmaker')!=record['bookmaker']
                or r.get('side')!=side or team_key(r.get('team'))!=team_key(record['team'])
                or C.utc(r.get('kickoff_at'))!=ko or C.utc(r.get('captured_at'))!=C.utc(record['captured_at_utc'][side])):continue
            try:
                if float(r['line'])!=record['line'] or abs(float(r['odds_decimal'])-record['odds'][side])>1e-8:continue
            except (ValueError,TypeError):continue
            if r.get('source') not in ('odds_api_io','moviodds_bet365','grosvenor_direct') or not r.get('event_id'):continue
            valid.append(raw)
        if not valid:raise ValueError('missing_exact_archived_shots_contract')
        ids={r['event_id'] for r in valid}
        if len(ids)!=1:raise ValueError('ambiguous_shots_event_id')
        candidates.append(valid[0])
    if candidates[0]['event_id']!=candidates[1]['event_id']:raise ValueError('paired_shots_event_mismatch')
    event=candidates[0]['event_id'];groups=defaultdict(list)
    for raw in winners:
        r=normalized(raw,P);stamp=C.utc(r.get('captured_at'))
        if (r.get('market')=='MATCH_ODDS' and r.get('bookmaker')==record['bookmaker'] and r.get('event_id')==event
            and r.get('source') in ('odds_api_io','moviodds_bet365','grosvenor_direct')
            and fixture(r)==fixture(record) and C.utc(r.get('kickoff_at'))==ko and stamp and stamp<=seen<ko
            and seen-stamp<=timedelta(hours=3)):
            groups[stamp].append(raw)
    for stamp,rows in sorted(groups.items(),reverse=True):
        sides=defaultdict(set)
        for r in rows:
            try:
                odds=float(r['odds_decimal'])
                if math.isfinite(odds) and odds>1:sides[r['side']].add(odds)
            except (ValueError,TypeError):continue
        if set(sides)!={'home','draw','away'} or any(len(v)!=1 for v in sides.values()):continue
        inv={s:1/next(iter(v)) for s,v in sides.items()};total=sum(inv.values())
        return dict(event_id=event,captured_at=stamp.isoformat(),p_home=inv['home']/total,p_away=inv['away']/total,
            bookmaker=record['bookmaker'],winner_rows=rows,shots_rows=candidates)
    raise ValueError('missing_asof_exact_fixture_1x2')

def predictions(row,strength,cfg):
    f=row['models']['opponent'];mu=float(f['mean']);alpha=float(f['alpha'])
    # Historical compact rows store alpha to eight decimal places.
    if abs(alpha-cfg['alpha'])>5e-9:raise ValueError('opponent_distribution_changed')
    ph,pa=strength['p_home'],strength['p_away']
    own=team_key(row['team']);home=team_key(row['home_team']);away=team_key(row['away_team'])
    if own not in (home,away):raise ValueError('ambiguous_team_side')
    s=math.log(ph/pa)*(1 if own==home else -1);changed=mu*math.exp(cfg['gamma']*s)
    o,u=row['odds']['over'],row['odds']['under'];m=(1/o)/(1/o+1/u)
    raw=prob_over(row['line'],changed,distribution='negative_binomial',alpha=alpha)
    p=blend_logit(raw,m,cfg['market_logit_weight'])
    if not all(math.isfinite(x) for x in (mu,changed,p)) or not 0<p<1:raise ValueError('invalid_strength_forecast')
    return dict(opponent=dict(mean=mu,p_over=f['p_over']),opponent_strength=dict(mean=changed,p_over=p,raw_p_over=raw,strength=s))

def select_batch(records,cfg):
    """Retain every first-batch decision, one best-EV selection per arm."""
    for arm in ARMS:
        choices=[]
        for r in records:
            p=r['forecasts'][arm]['p_over'];row=r['source_record'];o,u=row['odds']['over'],row['odds']['under']
            opts=[]
            for i,(side,prob,odds) in enumerate([('over',p,o),('under',1-p,u)],1):
                blocker=';'.join(x for x in str(row['models']['opponent'].get('selection_blockers',{}).get(side,'') or '').split(';') if x and x!='edge_below_3pct')
                ev=prob*odds-1;m=(1/odds)/(1/o+1/u)
                val=dict(side=i,odds=odds,fair_odds=1/prob,probability=prob,win_probability=prob,push_probability=0,
                    ev_pct=100*ev,edge_pct=100*(prob-m),selected=False,blocker=blocker)
                opts.append(val)
                if not blocker and ev>=cfg['minimum_ev']:choices.append((ev,row['contract_id'],side,r,val))
            r['selections'][arm]=max(opts,key=lambda x:x['ev_pct'])
        if choices:
            _,_,_,r,val=max(choices,key=lambda x:x[:3]);r['selections'][arm]={**val,'selected':True}

def capture(root,folder,reg,clock,P):
    path=root/'data/football-form/team-shots-paired-reference.jsonl';counts=Counter()
    if not path.exists():return dict(state='WAITING_FOR_PAIRED_FORECASTS',checked_at=clock.isoformat(),captured=0)
    rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    groups=defaultdict(list)
    for r in rows:groups[stable_key(r)].append(r)
    quotes=csv_rows(root/'data/team-shots/team-shots-odds-history.csv')
    winners=csv_rows(root/'data/football-form/football-1x2-odds-history.csv')
    for fx,items in groups.items():
        decision=folder/'decisions'/(C.digest(fx)+'.json')
        first=min(C.utc(r['registered_at_utc']) for r in items)
        if first<C.utc(reg['registered_at']) or first>clock or decision.exists():continue
        batch=[r for r in items if C.utc(r['registered_at_utc'])==first]
        fresh=[];reasons=Counter()
        for row in batch:
            try:
                ko=C.utc(row['kickoff_utc']);observed=[C.utc(v) for v in row['captured_at_utc'].values()]
                if row['bookmaker']!='Bet365' or row['league'] not in TOP_FIVE:raise ValueError('outside_frozen_scope')
                if not all(t and C.utc(reg['registered_at'])<=t<=clock<ko and clock-t<=timedelta(hours=3) for t in observed):raise ValueError('no_fresh_prospective_quote')
                if row.get('model_fingerprint')!=reg['paired_model_fingerprint']:raise ValueError('paired_forecast_fingerprint_mismatch')
                if 'p_over' not in row['models']['opponent']:raise ValueError('opponent_forecast_missing')
                strength=bind_strength(row,quotes,winners,P);forecast=predictions(row,strength,reg['protocol'])
                record=dict(id=C.digest(row['contract_id']),fixture_key=fx,captured_at=clock.isoformat(),
                    source_record=row,strength=strength,forecasts=forecast,selections={},actual_stake=0,
                    registration_sha256=C.digest(reg),display=dict(players=[row['home_team'],row['away_team']],team=row['team'],
                        tournament=row['league'],start=row['kickoff_utc'],market='team_shots',line=row['line'],
                        bookmaker=row['bookmaker'],odds=[row['odds']['over'],row['odds']['under']],price_observed_at=min(observed).isoformat()))
                fresh.append(record)
            except (ValueError,KeyError,TypeError) as exc:reasons[str(exc)]+=1
        select_batch(fresh,reg['protocol'])
        # Commit the immutable first-batch decision before derived per-contract files.
        # Recovery can recreate files from this exact decision, never rescore later quotes.
        C.immutable(decision,dict(fixture_key=fx,first_observed_at=clock.isoformat(),source_first_batch=first.isoformat(),
            captured=len(fresh),reasons=dict(reasons),records=fresh))
        counts.update(reasons);counts['captured']+=len(fresh)
    for path in sorted((folder/'decisions').glob('*.json')):
        for r in C.read(path).get('records',[]):C.immutable(folder/'captures'/(r['id']+'.json'),r)
    return dict(state='CAPTURED' if counts['captured'] else 'NO_NEW_ELIGIBLE_CONTRACTS',checked_at=clock.isoformat(),captured=counts['captured'],counts=dict(counts))

def settle(record,results,clock):
    row=record['source_record'];candidates=[]
    # Top-five ordered home-leg identity handles verified reschedules; never +/-day guessing.
    for ident,value in results.items():
        candidate={**row,'match_date':ident[0]}
        if ident[1:]==(row['league'],team_key(row['home_team']),team_key(row['away_team'])) and stable_key(candidate)==record['fixture_key']:
            if ident[0]<record['captured_at'][:10]:continue
            candidate['kickoff_utc']=ident[0]+row['kickoff_utc'][10:]
            resolved=exact_result(candidate,results,clock)
            if value.get('conflicting_counts'):return dict(status='quarantined',reason='conflicting_verified_counts')
            if resolved:candidates.append({**resolved,'date':ident[0]})
    if not candidates:return dict(status='pending')
    if len(candidates)!=1:return dict(status='quarantined',reason='ambiguous_exact_fixture_result')
    result=candidates[0];side='home' if team_key(row['team'])==team_key(row['home_team']) else 'away'
    actual=result.get(side+'_shots')
    if actual is None:return dict(status='pending')
    delta=actual-row['line']
    return dict(status='settled',actual=actual,side1_outcome=1 if delta>0 else -1 if delta<0 else 0,
        result_date=result.get('date') or row['match_date'],evidence_path=result['evidence_path'],source=result['source'])

def refresh(root,clock=None,settle_only=False):
    clock=clock or datetime.now(timezone.utc);folder=root/RELATIVE
    if not (folder/'registration.json').exists():return {}
    with locked(folder):
        try:
            reg=verified_registration(root,folder);P=paired(root)
            if P.model_fingerprint()!=reg['paired_model_fingerprint']:raise ValueError('paired_model_changed')
        except (ValueError,OSError) as exc:
            C.atomic(folder/'capture-status.json',dict(state='BLOCKED_MODEL_CHANGE',reason=str(exc),checked_at=clock.isoformat()))
            return report(root)
        if not settle_only:
            try:health=capture(root,folder,reg,clock,P)
            except Exception as exc:health=dict(state='CAPTURE_ERROR',reason=str(exc),checked_at=clock.isoformat(),captured=0)
            C.atomic(folder/'capture-status.json',health)
        records=[C.read(p) for p in sorted((folder/'captures').glob('*.json'))]
        results=count_result_index(root,clock) if records else {}
        outcomes=C.preserve_outcomes(folder,{r['id']:settle(r,results,clock) for r in records},clock)
        result=dict(name='Team Shots strength correction',registered_at=reg['registered_at'],updated_at=clock.isoformat(),
            protocol=reg['protocol'],actual_stake=0,historical_replay_included=False,capture=C.read(folder/'capture-status.json'),
            conflicts=len(list((folder/'conflicts').glob('*.json'))),**C.summary(records,outcomes,ARMS,clock))
        C.atomic(folder/'report.json',result);return result

def report(root):
    folder=root/RELATIVE;r=C.read(folder/'report.json')
    return {**r,'capture':C.read(folder/'capture-status.json')} if r else {}

def verified_registration(root,folder):
    """A reviewed input-only amendment retains the original frozen registration.

    Never accept arbitrary changed code. Exact old registration, exact amended
    code hashes and exact new upstream fingerprint must all match.
    """
    reg=C.read(folder/'registration.json')
    amendment=C.read(root/'config/shots-strength-input-amendment.json')
    if amendment and C.digest(reg)==amendment.get('original_registration_sha256'):
        if C.hashes(root,FILES)!=amendment.get('fingerprints'):
            raise ValueError('reviewed input amendment code mismatch')
        if C.digest(reg['protocol'])!=amendment.get('unchanged_protocol_sha256'):
            raise ValueError('frozen strength protocol changed')
        return {**reg,'paired_model_fingerprint':amendment['paired_model_fingerprint'],'input_revision':amendment['policy']}
    return C.verify(root,folder,FILES)

def register(root,clock=None):
    clock=clock or datetime.now(timezone.utc);folder=root/RELATIVE
    with locked(folder):
        if (folder/'registration.json').exists():return verified_registration(root,folder)
        P=paired(root);fingerprint=P.model_fingerprint();P.check_registration(fingerprint)
        cfg=C.read(root/PROTOCOL)
        assert cfg['actual_stake']==0 and not cfg['alerts'] and not cfg['automatic_promotion']
        reg=dict(registered_at=clock.isoformat(),protocol=cfg,fingerprints=C.hashes(root,FILES),
                 paired_model_fingerprint=fingerprint,actual_stake=0,historical_replay_included=False)
        C.immutable(folder/'registration.json',reg)
        C.atomic(folder/'capture-status.json',dict(state='CONNECTED_AWAITING_FIRST_RUN',checked_at=clock.isoformat()))
        return reg

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--register',action='store_true');p.add_argument('--settle-only',action='store_true');a=p.parse_args()
    if a.register:register(a.root)
    r=refresh(a.root,settle_only=a.settle_only);print(json.dumps({k:r.get(k) for k in ('name','fixtures','contracts','settled_fixtures','capture')}))
