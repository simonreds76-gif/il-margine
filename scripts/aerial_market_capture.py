"""Retain headed-market evidence from an already downloaded Bet365 response.
No requests, probability estimates or cross-provider identity guesses.
"""
from datetime import datetime, timezone, timedelta
import json

def retain_headed_markets(path, payload, event_index, captured_at):
    now = datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
    try:
        previous = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        previous = {}
    events = {}
    for event in previous.get('events', []):
        try:
            observed = datetime.fromisoformat(event['captured_at'].replace('Z', '+00:00'))
            if timedelta(0) <= now - observed < timedelta(days=2):
                events[str(event['event_id'])] = event
        except (KeyError, ValueError, TypeError):
            continue
    for event in payload:
        eid = str(event.get('id') or '')
        if not eid:
            continue
        meta = {**event_index.get(eid, {}), **event}
        books = event.get('bookmakers') or {}
        # A missing bookmaker is not proof that its markets are absent.
        book = next((k for k in books if k.casefold() == 'bet365'), None)
        if book is None:
            continue
        markets = [m for m in books[book] or []
                   if 'head' in str(m.get('name', '')).casefold()
                   or 'goal method' in str(m.get('name', '')).casefold()]
        events[eid] = dict(event_id=eid, home=meta.get('home'), away=meta.get('away'),
                           kickoff=meta.get('date') or meta.get('startTime'),
                           captured_at=captured_at, bookmaker='Bet365',
                           source='odds-api.io/v3/odds/multi', markets=markets)
    result = dict(schema_version=1, generated_at=captured_at,
                  purpose='Exact market evidence; Goal Method is not assumed to be a player market',
                  events=list(events.values()))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tmp.replace(path)
    return sum(len(e['markets']) for e in result['events'])


def quoted_markets(fixture, candidate, snapshot, now):
    """Exact fixture/team/player joins only. Ambiguous or stale quotes stay absent."""
    import re
    import math
    from football_team_names import football_form_team_key
    from player_name_matching import fold_name_text
    def name(value):
        return re.sub(r'[^a-z0-9]+', '', fold_name_text(value).casefold())
    def price(value):
        try:
            v=float(value)
            return v if math.isfinite(v) and v>1 else None
        except (ValueError,TypeError):
            return None
    teams=fixture.get('teams', [])
    if len(teams)!=2:
        return []
    side=next((i+1 for i,t in enumerate(teams) if str(t['id'])==str(candidate['team_id'])),None)
    if side is None:
        return []
    target=name(candidate['player'])
    # A normalized full name must identify exactly one player in this team.
    if sum(name(p['name'])==target for p in teams[side-1]['players'])!=1:
        return []
    matches=[]
    for event in snapshot.get('events', []):
        try:
            captured=datetime.fromisoformat(event['captured_at'].replace('Z','+00:00'))
            kickoff=datetime.fromisoformat(event['kickoff'].replace('Z','+00:00'))
            expected=datetime.fromisoformat(fixture['kickoff'].replace('Z','+00:00'))
            if event.get('bookmaker')!='Bet365' or not timedelta(0)<=now-captured<=timedelta(hours=2) or now>=kickoff:
                continue
            if kickoff!=expected:
                continue
            if (football_form_team_key(event['home']),football_form_team_key(event['away'])) != tuple(football_form_team_key(t['name']) for t in teams):
                continue
        except (KeyError,ValueError,TypeError):
            continue
        matches.append(event)
    if len(matches)!=1:
        return []
    event=matches[0];quotes={}
    for market in event.get('markets', []):
        market_name=market.get('name','')
        for prop in market.get('odds', []):
            label=str(prop.get('label') or '')
            parsed=re.fullmatch(r'(.+?) \(Header\) \(([12])\)',label) if market_name=='Goal Method' else re.fullmatch(r'(.+?) \(([12])\)',label)
            if not parsed or name(parsed[1])!=target or int(parsed[2])!=side:
                continue
            if market_name=='Player Headed Shots on Target':
                try:
                    if float(prop.get('hdp'))!=0.5:continue
                except (ValueError,TypeError):continue
                key='1+ headed shot on target';value=price(prop.get('over'));field='over'
            elif market_name=='Goal Method' and prop.get('hdp') is None:
                # Categorical Goal Method encodes its single labelled outcome in
                # a generic price field. Never reinterpret it as an Under bet.
                values=[(k,price(prop.get(k))) for k in ('over','under','home','away','odds') if price(prop.get(k)) is not None]
                if len(values)!=1:continue
                field,value=values[0];key='headed goal'
            else:
                continue
            if key not in candidate['markets_to_check'] or value is None:
                continue
            quotes.setdefault(key,[]).append(dict(market=key,odds=value,bookmaker='Bet365',
                captured_at=event['captured_at'],event_id=event['event_id'],
                source=event['source'],source_market=market_name,source_label=label,source_price_field=field))
    # Do not pick the best of conflicting duplicate prices.
    return [rows[0] for rows in quotes.values() if len({q['odds'] for q in rows})==1]
