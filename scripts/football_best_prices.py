"""Execution-price comparison only: no model probability or parameter changes."""
import json
import math
import copy
from datetime import datetime, timezone

MAX_PRICE_SECONDS=600


def add_execution_quotes(candidates,latest,now,minimum_edge,publisher):
    """A one-sided offer may execute a priced contract, but cannot calibrate it.

    Reuse an intact fresh reference pair's model probability for the exact
    fixture/team/line/side. No synthetic Under, cross-book devig or new model.
    """
    def contract(row,quote=False):
        return (row['kickoff'] if quote else stamp(row['kickoff_utc']),
                row['league_slug'] if quote else row['league'],
                publisher.team_key(row['home_team']),publisher.team_key(row['away_team']),
                publisher.team_key(row.get('team','')),str(row['line_label'] if quote else row['line']),row['side'])
    refs={};existing=set()
    for row in candidates:
        key=contract(row);existing.add((key,row['bookmaker']))
        if any(reason in row.get('blocked_reason','') for reason in
               ('price_not_fresh_10m','price_older_than_3h','future_price_timestamp','missing_price_timestamp')):continue
        captured=stamp(row.get('price_captured_at_utc'))
        if captured and 0 <= (now-captured).total_seconds() <= MAX_PRICE_SECONDS:
            refs.setdefault(key,[]).append(row)
    for quote in latest:
        key=contract(quote,True);book=quote['bookmaker'];captured=quote.get('captured_at_dt')
        if ((key,book) in existing or key not in refs or not captured or quote['kickoff']<=now
                or not 0 <= (now-captured).total_seconds() <= MAX_PRICE_SECONDS):continue
        reference=max(refs[key],key=lambda r:(float(r['book_odds']),r['bookmaker']))
        row=copy.deepcopy(reference)
        edge=float(row['model_implied_prob'])*float(quote['odds'])-1
        reasons=[r for r in row['blocked_reason'].split(';') if r and r!='edge_below_3pct']
        if edge<minimum_edge:reasons.append('edge_below_3pct')
        row.update(bookmaker=book,book_odds=round(float(quote['odds']),6),edge=round(edge,6),
                   price_source=quote.get('source',''),price_captured_at_utc=publisher.fmt_dt(captured),
                   probability_reference_bookmaker=reference['bookmaker'],
                   probability_reference_captured_at_utc=reference['price_captured_at_utc'],
                   blocked_reason=';'.join(reasons))
        candidates.append(row);existing.add((key,book))


def stamp(value):
    try:
        result=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return result if result.tzinfo else None
    except (ValueError,TypeError): return None


def fresh_pair(pair,now):
    return all(isinstance(row.get('captured_at_dt'),datetime)
               and 0 <= (now-row['captured_at_dt']).total_seconds() <= MAX_PRICE_SECONDS
               for row in (pair['over'],pair['under']))


def best_candidates(rows,now):
    """Compare the same contract before eligibility; never pick a worse-price book
    merely because its own market blend produced a larger estimated edge.
    All original rows remain available in the diagnostic board.
    """
    grouped={}
    for row in rows:
        captured=stamp(row.get('price_captured_at_utc'))
        kickoff=stamp(row.get('kickoff_utc'))
        reasons=[x for x in str(row.get('blocked_reason') or '').split(';') if x]
        try: valid_price=math.isfinite(float(row['book_odds'])) and float(row['book_odds'])>1
        except (KeyError,TypeError,ValueError): valid_price=False
        if not valid_price and 'invalid_price' not in reasons:reasons.append('invalid_price')
        if (not captured or not kickoff or kickoff<=now
                or not 0 <= (now-captured).total_seconds() <= MAX_PRICE_SECONDS):
            if 'price_not_fresh_10m' not in reasons: reasons.append('price_not_fresh_10m')
        row['blocked_reason']=';'.join(reasons)
        row['signal_status']='blocked' if reasons else 'eligible'
        row['current_model_would_have_priced']='false' if reasons else 'true'
        row['confidence_guard_applied']='true' if reasons else 'false'
        grouped.setdefault((row['pick_id'],row['kickoff_utc']),[]).append(row)
    for group in grouped.values():
        usable=[r for r in group if not any(x in str(r.get('blocked_reason','')) for x in
                   ('price_not_fresh_10m','price_older_than_3h','future_price_timestamp','missing_price_timestamp','invalid_price'))]
        usable=[r for r in usable if math.isfinite(float(r['book_odds'])) and float(r['book_odds'])>1]
        if not usable:continue
        best=max(usable,key=lambda r:(float(r['book_odds']),str(r.get('price_captured_at_utc','')),str(r.get('bookmaker',''))))
        comparison=json.dumps([{'bookmaker':r['bookmaker'],'odds':r['book_odds'],
                               'captured_at':r['price_captured_at_utc']} for r in sorted(usable,key=lambda r:-float(r['book_odds']))],separators=(',',':'))
        for row in group:
            row['compared_prices']=comparison
            if row is not best and row in usable:
                reasons=[x for x in row['blocked_reason'].split(';') if x]
                reasons.append('better_fresh_price_available')
                row.update(blocked_reason=';'.join(reasons),signal_status='blocked',
                           current_model_would_have_priced='false',confidence_guard_applied='true')
    return [r for r in rows if not r.get('blocked_reason')]


def latest_corners(rows,now,publisher):
    """Keep the original Pinnacle archive intact; add separate named-book rows."""
    books={}
    for source in rows:
        row=dict(source)
        if row.get('market') and row['market'] not in {'MATCH_CORNERS','MATCH_CORNERS_ALT'}:continue
        row['bookmaker']=row.get('bookmaker') or 'Pinnacle'
        row['kickoff_iso']=row.get('kickoff_iso') or row.get('kickoff_at')
        row['league']=row.get('league') or row.get('competition')
        books.setdefault(row['bookmaker'],[]).append(row)
    return [r for items in books.values() for r in publisher.latest_corners_odds(items,now)]
