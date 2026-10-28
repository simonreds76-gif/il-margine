"""Direct Grosvenor prices, joined to existing fixture IDs without changing models.

Only exact, oriented club/competition/start matches are accepted. The public
offering receives no Odds-API credential. At most five league catalogues and 30 event
requests per process; five-minute cache shared by existing football collectors.
Raw latest responses are bounded to recent fixtures; canonical price ledgers
continue to retain their original bookmaker, price and capture time.
"""
from __future__ import annotations

import copy
import gzip
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from football_team_names import football_form_team_key
from tennis_grosvenor import BASE, PARAMS, scaled, utc

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/goalkeeper-saves/grosvenor-direct-latest.json.gz'
BOOK = 'Grosvenor'
LEAGUES = {('england', 'premier_league'): 'england-premier-league',
           ('italy', 'serie_a'): 'italy-serie-a',
           ('spain', 'la_liga'): 'spain-la-liga',
           ('germany', 'bundesliga'): 'germany-bundesliga',
           ('france', 'ligue_1'): 'france-ligue-1'}
_catalog = {}
_attempted = set()
_started = None


def team_key(value):
    # Grosvenor's verified Ligue 1 name; keep this source alias out of models.
    key = football_form_team_key(value)
    return 'paris sg' if key == 'psg' else key


def competition(event):
    path = event.get('path', [])
    return LEAGUES.get(tuple(p.get('termKey') for p in path[1:3]), '')


def target_competition(event):
    import re
    league = event.get('league') or {}
    name = (league.get('slug') or league.get('name') or '') if isinstance(league, dict) else league
    name = re.sub('[^a-z0-9]+', '-', str(name).casefold()).strip('-')
    return {'spain-laliga': 'spain-la-liga', 'spain-la-liga-ea-sports': 'spain-la-liga'}.get(name, name)


def matches(source, target, now):
    a, b = utc(source.get('start')), utc(target.get('date') or target.get('startTime'))
    return bool(source.get('sport') == 'FOOTBALL' and source.get('state') == 'NOT_STARTED'
                and a and b and a == b and a > now
                and competition(source) and competition(source) == target_competition(target)
                and all(source.get(s+'Name') and target.get(s)
                        and team_key(source[s+'Name']) == team_key(target[s]) for s in ('home','away')))


def normalize(raw, target, captured_at):
    now = utc(captured_at)
    events = [e for e in raw.get('events', []) if now and matches(e, target, now)]
    if len(events) != 1:
        return None
    event = events[0]
    markets = []
    for offer in raw.get('betOffers', []):
        criterion = offer.get('criterion') or {}
        label = criterion.get('englishLabel', '')
        if (str(offer.get('eventId')) != str(event['id'])
                or criterion.get('lifetime') != 'FULL_TIME'
                or 'OFFERED_PREMATCH' not in offer.get('tags', [])):
            continue
        outcomes = offer.get('outcomes') or []
        if not outcomes or any(o.get('status') != 'OPEN' or scaled(o.get('odds'), price=True) is None
                or str(o.get('betOfferId')) != str(offer.get('id'))
                or not utc(o.get('changedDate')) or utc(o['changedDate']) > now for o in outcomes):
            continue
        name, odds = None, []
        types = {o.get('type'): o for o in outcomes}
        if label == 'Full Time' and offer.get('betOfferType', {}).get('id') == 2:
            if set(types) == {'OT_ONE','OT_CROSS','OT_TWO'} and len(outcomes) == 3:
                if (types['OT_ONE'].get('participant') == event['homeName']
                        and types['OT_TWO'].get('participant') == event['awayName']):
                    name = 'ML'
                    odds = [dict(home=scaled(types['OT_ONE']['odds'], price=True),
                                 draw=scaled(types['OT_CROSS']['odds'], price=True),
                                 away=scaled(types['OT_TWO']['odds'], price=True))]
        elif label in {'To Score', 'To give an assist (Settled using Opta data)'}:
            # Occurrence 1 = at least one, not a 2+/3+ scorer/assist ladder.
            name = 'Anytime Goalscorer' if label == 'To Score' else 'Anytime Assist'
            odds = [dict(label=o['participant'], odds=scaled(o['odds'], price=True)) for o in outcomes
                    if o.get('type') == 'OT_YES' and o.get('line') == 1000 and o.get('participant')]
        else:
            names = {'Total Corners': 'Corners Totals'}
            for side in ('home', 'away'):
                club = event[side+'Name']
                names.update({f'Goalkeeper Saves - {club} (Settled using Opta data)': f'Goalkeeper Saves {side.title()}',
                              f'Total Shots by {club} (Settled using Opta data)': f'Total Shots {side.title()}',
                              f'Total Corners by {club}': f'Corners Totals {side.title()}'})
            name = names.get(label)
            if name and offer.get('betOfferType', {}).get('id') == 6:
                # Preserve one-sided ladders; never fabricate the absent Under.
                lines = {scaled(o.get('line')) for o in outcomes}
                if (len(lines) == 1 and None not in lines and next(iter(lines)) % .5 == 0
                        and len(types) == len(outcomes) and set(types) <= {'OT_OVER','OT_UNDER'}):
                    odds = [dict(hdp=next(iter(lines)), **{
                        'over' if t == 'OT_OVER' else 'under': scaled(o['odds'], price=True)
                        for t,o in types.items()})]
        if name and odds:
            markets.append(dict(name=name, odds=odds, source='grosvenor_direct',
                                source_event_id=str(event['id']), source_offer_id=str(offer['id']),
                                source_url=f'{BASE}/betoffer/event/{event["id"]}.json',
                                updatedAt=max(o['changedDate'] for o in outcomes),
                                captured_at=captured_at, raw_offer=offer))
    return {**target, 'bookmakers': {BOOK: markets},
            'urls': {BOOK: f'https://www.grosvenorcasinos.com/sport#event/{event["id"]}'}}


def enabled():
    config = json.loads((ROOT / 'config/odds-api-bookmaker-allocation.json').read_text(encoding='utf-8-sig'))
    return config.get('direct_football_grosvenor', False)


def capture_and_merge(payload, targets, *, now=None, cache_path=CACHE, get=None, force=False, cache_seconds=300):
    """Return existing provider rows plus verified direct markets and health.

    Mapping stays on the existing event ID so a source change cannot produce a
    second GK signal. Cache reuse keeps its original captured_at, never now.
    """
    global _catalog, _started
    receipt = dict(bookmaker=BOOK, requests=0, matched=0, rows=0, errors=[], missing=[], deferred=[])
    if not force and not enabled():
        return payload, receipt
    now = now or datetime.now(timezone.utc)
    get = get or requests.get
    if _started is None:
        _started = time.monotonic()
    merged = {str(e['id']): copy.deepcopy(e) for e in payload if e.get('id') is not None}
    try:
        cache = json.loads(gzip.decompress(cache_path.read_bytes()))
    except (OSError, ValueError, EOFError):
        cache = {}
    cache = {k:v for k,v in cache.items() if utc(v.get('captured_at'))
             and timedelta(0) <= now-utc(v['captured_at']) < timedelta(days=2)}

    def fetch(path):
        receipt['requests'] += 1
        response = get(f'{BASE}/{path}.json', params=PARAMS, timeout=8)
        response.raise_for_status()
        return response.json()

    try:
        # The global football listing truncates future rounds. Use each exact
        # league catalogue once, rather than silently losing tomorrow/weekend.
        routes = {value: key for key,value in LEAGUES.items()}
        sources = []
        for league in sorted({target_competition(t) for t in targets} & routes.keys()):
            if league not in _catalog:
                country, group = routes[league]
                try:
                    _catalog[league] = fetch(f'listView/football/{country}/{group}/all/matches')
                except (requests.RequestException, ValueError) as exc:
                    receipt['errors'].append(f'catalog:{league}:{type(exc).__name__}')
                    _catalog[league] = {'events': []}
            sources.extend(e.get('event', {}) for e in _catalog[league].get('events', []))
        for target in targets:
            eid = str(target.get('id') or '')
            candidates = [e for e in sources if matches(e, target, now)]
            if len(candidates) != 1:
                receipt['missing'].append(dict(id=eid, reason='ambiguous_fixture' if candidates else 'no_exact_fixture'))
                continue
            source = candidates[0]
            sid = str(source['id'])
            cached = cache.get(sid, {})
            age = now-utc(cached['captured_at']) if utc(cached.get('captured_at')) else timedelta(days=9)
            try:
                if not timedelta(0) <= age < timedelta(seconds=cache_seconds):
                    if sid in _attempted or len(_attempted) >= 30 or time.monotonic()-_started > 72:
                        receipt['deferred'].append(eid)
                        continue
                    _attempted.add(sid)
                    raw = fetch(f'betoffer/event/{sid}')
                    cached = dict(captured_at=now.isoformat(), source=f'{BASE}/betoffer/event/{sid}.json', data=raw)
                    cache[sid] = cached
                normalized = normalize(cached['data'], target, cached['captured_at'])
                # A cached prematch response must still be prematch NOW.
                if not normalized or not matches(source, target, now):
                    receipt['missing'].append(dict(id=eid, reason='invalid_event_response'))
                    continue
                current = merged.setdefault(eid, {**target, 'bookmakers': {}})
                current.setdefault('bookmakers', {})[BOOK] = normalized['bookmakers'][BOOK]
                current.setdefault('urls', {}).update(normalized['urls'])
                receipt['matched'] += 1
                receipt['rows'] += len(normalized['bookmakers'][BOOK])
            except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
                receipt['errors'].append(f'event:{sid}:{type(exc).__name__}')
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        receipt['errors'].append(f'catalog:{type(exc).__name__}')
    if cache:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(f'.{os.getpid()}.tmp')
        tmp.write_bytes(gzip.compress(json.dumps(cache, ensure_ascii=False).encode('utf-8')))
        tmp.replace(cache_path)
    status_path = cache_path.with_suffix('.status.json')
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(dict(captured_at=now.isoformat(), **receipt), indent=2)+'\n', encoding='utf-8')
    print('Grosvenor direct: '+json.dumps(receipt, separators=(',', ':')))
    return list(merged.values()), receipt
