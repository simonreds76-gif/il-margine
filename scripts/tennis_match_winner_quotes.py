"""Validate same-response ATP winner pairs; no network or model dependencies."""
from tennis_grosvenor import scaled, utc

def winner_offer(item, event):
    stamp=utc(item.get('captured_at')); matches=[]
    for offer in item.get('payload',{}).get('betOffers',[]):
        if (offer.get('criterion',{}).get('englishLabel')!='Match Odds'
            or offer.get('betOfferType',{}).get('id')!=2
            or str(offer.get('eventId'))!=str(event['id'])
            or 'OFFERED_PREMATCH' not in offer.get('tags',[])):continue
        outcomes=offer.get('outcomes',[]);by={o.get('type'):o for o in outcomes}
        if len(outcomes)!=2 or set(by)!={'OT_ONE','OT_TWO'}:continue
        a,b=by['OT_ONE'],by['OT_TWO']
        if a.get('participant')!=event['homeName'] or b.get('participant')!=event['awayName']:continue
        if any(o.get('status')!='OPEN' or o.get('line') is not None or scaled(o.get('odds'),price=True) is None
               or str(o.get('betOfferId'))!=str(offer['id']) or not utc(o.get('changedDate'))
               or not stamp or utc(o['changedDate'])>stamp for o in outcomes):continue
        matches.append(offer)
    return matches[0] if len(matches)==1 else None

def bind_winner(receipt,q):
    matches=[]
    for item in receipt.get('events',[]):
        if str(item.get('requested_id'))!=q['event_id'] or utc(item.get('captured_at'))!=utc(q['captured_at']):continue
        events=[e for e in item.get('payload',{}).get('events',[]) if str(e.get('id'))==q['event_id']]
        if len(events)!=1 or events[0]!=q['raw_event']:continue
        offer=winner_offer(item,events[0])
        if offer:
            by={o['type']:o for o in offer['outcomes']};a,b=[scaled(by[t]['odds'],price=True) for t in ('OT_ONE','OT_TWO')]
            matches.append(dict(probability=(1/a)/(1/a+1/b),odds=[a,b],raw_offer=offer,
                event_id=q['event_id'],captured_at=q['captured_at'],bookmaker=q['bookmaker']))
    if len(matches)!=1:raise ValueError('missing_or_ambiguous_same_response_winner_pair')
    return matches[0]
