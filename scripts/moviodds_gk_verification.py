"""Reconcile cached GK contracts with a bounded full-match live fetch.

The main selection ID is mutable: it may move from 3+ to 4+. Cached price
updates must never be attached to an older number merely because its ID agrees.
Keep only complete contract AND price agreement; never relabel either response.
"""
import copy
import json
import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from goalkeeper_quote_integrity import VERIFICATION_VERSION

MAX_FIXTURES = 30


def identity(q, fixture):
    """Read all identity fields from the same quote, including the milestone."""
    if (str(q.get('fixture_id')) != fixture or str(q.get('group_id')) != '177703'
            or q.get('group_name') != 'Goalkeeper Saves'
            or str(q.get('market_id')) not in ('177703','177769')
            or q.get('suspended') or q.get('removed') or q.get('stale')):
        return None
    milestone=re.fullmatch(r'([1-9]\d*)\+',str(q.get('side') or ''))
    fraction=re.fullmatch(r'(\d+)/(\d+)',str(q.get('odds_frac') or ''))
    try:
        line=float(q['handicap']);price=float(q['odds_dec'])
        if (not milestone or line != int(milestone[1])-.5 or not fraction or int(fraction[2])==0
                or not math.isfinite(price) or price<=1
                or abs(price-(1+int(fraction[1])/int(fraction[2])))>1e-7
                or not str(q.get('line') or '').strip() or str(q.get('sel_id') or '') in ('','0')):
            return None
        return str(q['market_id']),str(q['sel_id']),str(q['line']).strip(),line,price
    except (KeyError,ValueError,TypeError,OverflowError):
        return None


def reconcile(board_match, live, event_id, now):
    from moviodds_prices import fresh, utc
    fixture=str(board_match['id']);issues=Counter()
    board_status=(board_match.get('group_status') or {}).get('177703') or {}
    live_status=(live.get('group_status') or {}).get('177703') or {}
    if (live.get('site')!='com' or str(live.get('fixture'))!=fixture or live.get('source')!='live-fetch'
            or not fresh(live.get('server_time'),now)
            or any(s.get('stale') or s.get('suspended') or s.get('removed') or not fresh(s.get('polled_at'),now)
                   for s in (board_status,live_status))):
        return [],{'unverified_live_response':1}
    by_id={};duplicates=set()
    for q in live.get('quotes') or []:
        ident=identity(q,fixture)
        if ident:
            k=ident[:2]
            if k in by_id: duplicates.add(k)
            by_id[k]=(ident,q)
    # Duplicate selection IDs and inconsistent same-player ladders fail closed.
    accepted=[];seen=set()
    for q in board_match.get('quotes') or []:
        if str(q.get('group_id'))!='177703':continue
        ident=identity(q,fixture)
        if not ident:issues['invalid_cached_contract']+=1;continue
        k=ident[:2]
        if k in seen or k in duplicates:
            issues['duplicate_selection_identity']+=1
            accepted=[a for a in accepted if (str(a['market_id']),str(a['sel_id']))!=k]
            duplicates.add(k);continue
        seen.add(k)
        counterpart=by_id.get(k)
        if not counterpart:issues['missing_live_selection']+=1;continue
        other,live_quote=counterpart
        if ident[:4]!=other[:4]:issues['selection_contract_changed']+=1;continue
        if abs(ident[4]-other[4])>1e-7:issues['price_disagreement']+=1;continue
        if any(not utc(x.get('ts')) or utc(x['ts'])>utc(s['polled_at'])+timedelta(seconds=30)
               for x,s in ((q,board_status),(live_quote,live_status))):
            issues['invalid_quote_timestamp']+=1;continue
        proof={'version':VERIFICATION_VERSION,'site':'com','fixture_id':fixture,'event_id':str(event_id),
               'market_id':ident[0],'sel_id':ident[1],'player':ident[2],'line':ident[3],
               'odds_decimal':round(ident[4],4),'board_polled_at':board_status['polled_at'],
               'live_polled_at':live_status['polled_at'],'verified_at':now.isoformat()}
        accepted.append({**copy.deepcopy(q),'quote_verification':json.dumps(proof,separators=(',',':'))})
    by_player={}
    for q in accepted:by_player.setdefault(q['line'],[]).append(q)
    for player,ladder in by_player.items():
        ordered=sorted(ladder,key=lambda q:float(q['handicap']))
        if any(float(a['handicap'])==float(b['handicap']) or float(a['odds_dec'])>=float(b['odds_dec']) for a,b in zip(ordered,ordered[1:])):
            issues['inconsistent_ladder']+=len(ladder);accepted=[q for q in accepted if q['line']!=player]
    return accepted,dict(issues)


def verify_board(data, targets, get=None, now=None, days_ahead=3):
    from moviodds_prices import download_response, soccer_target_matches, fresh, utc
    fixed_now=now
    now=now or datetime.now(timezone.utc)
    result=copy.deepcopy(data); jobs=[]; receipts=[];responses={}
    for match in result.get('matches') or []:
        quotes=[q for q in match.get('quotes') or [] if str(q.get('group_id'))=='177703']
        # Remove all GK quotes first; only individually reconciled quotes return.
        match['quotes']=[q for q in match.get('quotes') or [] if str(q.get('group_id'))!='177703']
        matches=[t for t in targets if soccer_target_matches(match,t)]
        start=utc(match.get('kickoff_utc'));status=(match.get('group_status') or {}).get('177703') or {}
        if (len(matches)!=1 or not quotes or match.get('in_play') is not False or match.get('suspended')
                or match.get('removed') or not start or not now<start<=now+timedelta(days=days_ahead)
                or not fresh(status.get('polled_at'),now) or status.get('stale')):continue
        jobs.append((match,{**match,'quotes':quotes},str(matches[0]['id'])))
    def read(job):
        _,original,event_id=job;fixture=str(original['id'])
        try:
            live=download_response('https://moviodds.com/quotes',{'fi':fixture,'site':'com'},get)
            checked=fixed_now or datetime.now(timezone.utc)
            accepted,issues=reconcile(original,live,event_id,checked)
            # Retain the raw GK quotes and response envelope, not unrelated
            # markets from a potentially large full-match response.
            evidence={k:live.get(k) for k in ('site','fixture','source','server_time')}
            evidence.update(evidence_scope='goalkeeper_saves_only',
                            group_status={'177703':(live.get('group_status') or {}).get('177703')},
                            quotes=[q for q in live.get('quotes') or [] if str(q.get('group_id'))=='177703'])
            return accepted,{'fixture_id':fixture,'event_id':event_id,'accepted':len(accepted),'excluded':issues},evidence
        except Exception as error:
            # A failed fixture must not discard the other bookmakers or fixtures.
            return [],{'fixture_id':fixture,'event_id':event_id,'accepted':0,'error':type(error).__name__},None
    with ThreadPoolExecutor(max_workers=3) as pool:
        for (match,original,_),(accepted,receipt,live) in zip(jobs[:MAX_FIXTURES],pool.map(read,jobs[:MAX_FIXTURES])):
            match['quotes'].extend(accepted);receipts.append(receipt)
            responses[str(original['id'])]=live
            if accepted:
                board=utc(original['group_status']['177703']['polled_at']);polled=utc(live['group_status']['177703']['polled_at'])
                match['group_status']['177703']={'polled_at':min(board,polled).isoformat()}
    return result,{'version':VERIFICATION_VERSION,'requests':len(jobs[:MAX_FIXTURES]),'fixtures':receipts,
                   'deferred_by_budget':len(jobs[MAX_FIXTURES:]),'verified_quotes':sum(r['accepted'] for r in receipts)},responses
