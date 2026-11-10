"""Price-only Match Shape transport. Runs with requests, without model packages.

No native database, model registration, forecasts or settlements on this host.
The Windows tracker owns those; observations retain their original timestamps.
"""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json
import time
import requests
from tennis_grosvenor import BASE, PARAMS, eligible, scaled, utc

RELATIVE = Path('data/tennis-ml-research/match-shape-v1')

def digest(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    tmp.replace(path)

def parse_receipt(receipt, clock):
    """Allowlist full-match contracts. Keep negative handicap signs and raw evidence."""
    result = []
    for item in receipt.get('events', []):
        stamp = utc(item.get('captured_at'))
        if not stamp or not stamp <= clock or clock-stamp > timedelta(minutes=30):
            continue
        payload = item.get('payload', {})
        events = [e for e in payload.get('events', []) if str(e.get('id')) == str(item.get('requested_id'))]
        if len(events) != 1 or not eligible(events[0], stamp) or not any(p.get('termKey') == 'atp' for p in events[0].get('path', [])):
            continue
        e = events[0]
        if not clock < utc(e['start']):
            continue
        for offer in payload.get('betOffers', []):
            name = offer.get('criterion', {}).get('englishLabel')
            if name not in ('Total Games', 'Game Handicap') or str(offer.get('eventId')) != str(e['id']) or 'OFFERED_PREMATCH' not in offer.get('tags', []):
                continue
            outcomes = offer.get('outcomes', [])
            types = {o.get('type'): o for o in outcomes}
            market = 'total_games' if name == 'Total Games' else 'game_handicap'
            expected = ('OT_OVER', 'OT_UNDER') if market == 'total_games' else ('OT_ONE', 'OT_TWO')
            if len(outcomes) != 2 or set(types) != set(expected) or offer.get('betOfferType', {}).get('id') != (6 if market == 'total_games' else 1):
                continue
            if any(o.get('status') != 'OPEN' or scaled(o.get('odds'), price=True) is None or str(o.get('betOfferId')) != str(offer['id']) or not utc(o.get('changedDate')) or utc(o['changedDate']) > stamp for o in outcomes):
                continue
            a,b = (types[t] for t in expected)
            if any(isinstance(o.get('line'), bool) or not isinstance(o.get('line'), int) for o in (a,b)):
                continue
            line, other = a['line']/1000, b['line']/1000
            if line % .5 or (market == 'total_games' and (line != other or not 10 <= line <= 45)):
                continue
            if market == 'game_handicap' and (line != -other or abs(line)>15 or a.get('participant') != e['homeName'] or b.get('participant') != e['awayName']):
                continue
            result.append(dict(event_id=str(e['id']), home=e['homeName'], away=e['awayName'], group=e['group'],
                               scheduled_start=e['start'], captured_at=stamp.isoformat(), market=market, line=line,
                               odds1=scaled(a['odds'], price=True), odds2=scaled(b['odds'], price=True),
                               bookmaker='Grosvenor', offer_id=str(offer['id']),
                               changed_at=max(o['changedDate'] for o in outcomes), main_line='MAIN_LINE' in offer.get('tags', []),
                               url=f"https://www.grosvenorcasinos.com/sport#event/{e['id']}", raw_event=e, raw_offer=offer))
    return result

def collect(get=requests.get, max_events=4):
    now=datetime.now(timezone.utc);began=time.monotonic()
    receipt=dict(source=BASE,bookmaker='Grosvenor',captured_at=now.isoformat(),requests=0,events=[],errors=[],
                 collector_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),scope='ATP games paper fallback')
    def fetch(path):
        receipt['requests']+=1
        response=get(f'{BASE}/{path}.json',params=PARAMS,timeout=8)
        response.raise_for_status()
        return response.json()
    try:
        catalogue=fetch('listView/tennis/all/all/all/matches')
        events=[i['event'] for i in catalogue.get('events',[]) if eligible(i.get('event',{}),now)
                and any(p.get('termKey')=='atp' for p in i['event'].get('path',[]))]
        events=sorted({e['id']:e for e in events}.values(),key=lambda e:(e['start'],e['id']))
        receipt['eligible_atp_events']=len(events)
        for event in events[:min(4,max(0,max_events))]:
            if time.monotonic()-began>35:receipt['errors'].append('wall_budget');break
            try:
                payload=fetch(f"betoffer/event/{event['id']}")
                receipt['events'].append(dict(requested_id=event['id'],captured_at=datetime.now(timezone.utc).isoformat(),payload=payload))
            except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
                receipt['errors'].append(f"{event['id']}:{type(exc).__name__}")
    except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
        receipt['errors'].append(f'catalogue:{type(exc).__name__}')
    return receipt

def capture_quotes(root, receipt, *, clock=None, collector=collect):
    clock=clock or datetime.now(timezone.utc)
    quotes=parse_receipt(receipt,clock)
    if not quotes:
        receipt=collector()
        clock=datetime.now(timezone.utc)
        quotes=parse_receipt(receipt,clock)
    # Store only validated full-match ATP offers, retaining original raw offer,
    # source event and first observation times. No private forecast data.
    offers={};events={}
    for q in quotes:
        key=(q['event_id'],q['captured_at'])
        events[key]=q['raw_event']
        offers.setdefault(key,[]).append(q['raw_offer'])
    # The J1 paper comparison needs the exact winner pair from this response.
    # Retaining it makes no extra request and does not change the old game quotes.
    from tennis_match_winner_quotes import winner_offer
    for item in receipt.get('events',[]):
        key=(str(item.get('requested_id')),utc(item.get('captured_at')).isoformat() if utc(item.get('captured_at')) else '')
        if key in events:
            winner=winner_offer(item,events[key])
            if winner:offers[key].append(winner)
    packet=dict(source=BASE,bookmaker='Grosvenor',captured_at=clock.isoformat(),
        events=[dict(requested_id=eid,captured_at=stamp,payload=dict(events=[events[(eid,stamp)]],betOffers=rows))
                for (eid,stamp),rows in sorted(offers.items())])
    if quotes:
        # Identity is tied to source observations, never re-stamped on a retry.
        packet['captured_at']=max(q['captured_at'] for q in quotes)
        path=root/RELATIVE/'cloud-quotes'/packet['captured_at'][:10]/(digest(packet)+'.json')
        encoded=json.dumps(packet,sort_keys=True,indent=2,allow_nan=False)+'\n'
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.read_text(encoding='utf-8')!=encoded:raise ValueError('immutable_quote_conflict')
        else:
            with path.open('x',encoding='utf-8') as stream:stream.write(encoded)
    status=dict(state='QUOTES_SAVED_FOR_NATIVE_TRACKER' if quotes else 'NO_FRESH_ATP_GAMES_QUOTES',
        checked_at=clock.isoformat(),source='Grosvenor',quote_count=len(quotes),
        fixtures=len({q['event_id'] for q in quotes}),errors=receipt.get('errors',[]),
        forecasts_created=0,settlements_created=0,model_execution='Windows native tracker',
        latest_observed_at=max((q['captured_at'] for q in quotes),default=None))
    if status['errors']:status['state']='PARTIAL_QUOTES' if quotes else 'SOURCE_ERROR'
    atomic(root/RELATIVE/'cloud-capture-status.json',status)
    return status
