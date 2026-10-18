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
