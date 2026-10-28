"""Bounded public Paddy header quotes. No account key, wagers or model changes.

Only the existing five-league aerial fixtures are joined, by competition,
oriented full club names and exact kickoff. A successful empty response clears
old quotes; failures retain their original observation time and never refresh it.
"""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import math
import os
import re
import time
from urllib.parse import urlparse

import requests
from aerial_data import read, save, utc
from football_team_names import football_form_team_key
from player_name_matching import fold_name_text

BOOK = 'Paddy Power'
# Explicit user revocation, 28 October 2026. No website access or quote use.
DIRECT_COLLECTION_ENABLED = False
COMPETITIONS = {'Premier League': 10932509, 'Serie A': 81, 'Bundesliga': 59,
                'La Liga': 117, 'Ligue 1': 55}
TYPES = {'PLAYER_TO_HAVE_1_OR_MORE_HEADED_SHOTS_ON_TARGET': '1+ headed shot on target',
         'PLAYER_TO_SCORE_A_HEADER': 'headed goal'}
RULES = 'https://helpcenter.paddypower.com/app/answers/detail/a_id/10079/'
SOCCER_RULES = 'https://helpcenter.paddypower.com/app/answers/detail/football-soccer-rules/'
PARAMS = dict(exchangeLocale='en_GB', currencyCode='GBP', betexRegion='GBR',
              capiJurisdiction='intl', language='en', regionCode='UK', countryCode='GB', loggedIn='false')


def name(value):
    return re.sub('[^a-z0-9]', '', fold_name_text(str(value)).casefold())


def team(value):
    key = football_form_team_key(value)
    return {'psg': 'paris sg'}.get(key, key)


def context(html):
    key = re.search(r'appKey:\s*"([^"]+)"', html)
    if not key:
        raise ValueError('Public client configuration unavailable')
    endpoints = {}
    for label in ('markets', 'competitionPage'):
        hit = re.search(r'"'+label+r'":\s*"(//[^\"]+)"', html)
        if not hit or urlparse('https:'+hit[1]).hostname != 'apisms.paddypower.com':
            raise ValueError('Public endpoint changed')
        endpoints[label] = 'https:'+hit[1]
    return key[1], endpoints


def matches(event, fixture, now):
    try:
        clubs = event['name'].split(' v ')
        return (event['eventTypeId'] == 1 and len(clubs) == 2
                and event['competitionId'] == COMPETITIONS.get(fixture['competition'])
                and utc(event['openDate']) == utc(fixture['kickoff']) > now
                and [team(x) for x in clubs] == [team(t['name']) for t in fixture['teams']])
    except (KeyError, ValueError, TypeError):
        return False


def normalize(event, fixture, markets, captured_at, raw_hash):
    now = utc(captured_at)
    if not matches(event, fixture, now):
        return None
    # This rules version covers the existing five leagues only. Re-review the
    # explicitly dated offer at expiry; never silently assume a future promotion.
    if now >= utc('2027-07-01T00:00:00Z'):
        raise ValueError('Paddy contract rules require re-verification')
    contract = 'paddy_super_sub_v1' if fixture['competition'] == 'Premier League' else 'paddy_named_player_v1'
    roster = {}
    for t in fixture['teams']:
        for p in t.get('players', []):
            roster.setdefault(name(p['name']), []).append((str(p['id']), str(t['id'])))
    rows = []
    for mid, market in markets.items():
        kind = market.get('marketType')
        if (kind not in TYPES or str(market.get('marketId')) != str(mid)
                or market.get('eventId') != event['eventId'] or market.get('eventTypeId') != 1
                or market.get('competitionId') != event['competitionId']
                or market.get('marketStatus') != 'OPEN' or market.get('inPlay') is not False
                or utc(market['marketTime']) != utc(fixture['kickoff'])):
            continue
        runners = market.get('runners', [])
        identities = [str(r.get('selectionId')) for r in runners]
        if len(identities) != len(set(identities)):
            continue
        for r in runners:
            try:
                odds = r['winRunnerOdds']['trueOdds']['decimalOdds']['decimalOdds']
                if (r.get('runnerStatus') != 'ACTIVE' or not r.get('selectionId')
                        or type(odds) not in (int, float) or not math.isfinite(odds) or odds <= 1):
                    continue
                identified = roster.get(name(r['runnerName']), [])
                rows.append(dict(market=TYPES[kind], odds=odds, bookmaker=BOOK,
                    player_id=identified[0][0] if len(identified)==1 else None,
                    team_id=identified[0][1] if len(identified)==1 else None,
                    identity_status='exact_roster' if len(identified)==1 else 'unmapped_or_ambiguous',
                    source_label=r['runnerName'], source_market=kind, source_market_id=str(mid),
                    source_selection_id=str(r['selectionId']), source='paddy_direct',
                    raw_runner=r,
                    source_url='https://www.paddypower.com/football', event_id=str(event['eventId']),
                    captured_at=captured_at, source_price_changed_at=None, raw_sha256=raw_hash,
                    source_market_status=market['marketStatus'], source_in_play=market['inPlay'],
                    source_market_time=market['marketTime'], source_competition_id=event['competitionId'],
                    contract=contract, rules_verified_at='2026-10-28', rules_url=RULES,
                    standard_rules_url=SOCCER_RULES, probability_basis='named_player_only'))
            except (KeyError, TypeError, ValueError):
                continue
    return dict(fixture_id=str(fixture['id']), event_id=str(event['eventId']), bookmaker=BOOK,
                home=fixture['teams'][0]['name'], away=fixture['teams'][1]['name'],
                kickoff=fixture['kickoff'], captured_at=captured_at, quotes=rows)


def quoted(fixture, candidate, snapshot, now):
    if not DIRECT_COLLECTION_ENABLED:
        return []
    if not any(e.get('bookmaker')==BOOK for e in snapshot.get('events', [])):
        return []
    teams = fixture.get('teams', [])
    players = [(str(p['id']), str(t['id'])) for t in teams for p in t.get('players', [])
               if name(p['name']) == name(candidate['player'])]
    if len(players) != 1 or players[0][1] != str(candidate['team_id']):
        return []
    events = []
    for e in snapshot.get('events', []):
        try:
            if (e.get('bookmaker') == BOOK and str(e.get('fixture_id')) == str(fixture.get('id'))
                    and utc(e['kickoff']) == utc(fixture['kickoff']) > now
                    and [team(e['home']), team(e['away'])] == [team(t['name']) for t in teams]
                    and timedelta(0) <= now-utc(e['captured_at']) <= timedelta(hours=2)):
                events.append(e)
        except (KeyError, TypeError, ValueError):
            continue
    if len(events) != 1:
        return []
    grouped = {}
    for q in events[0].get('quotes', []):
        if (q.get('identity_status') == 'exact_roster' and q.get('player_id') == players[0][0]
                and q.get('team_id') == players[0][1] and q.get('market') in candidate['markets_to_check']
                and q.get('contract') in ('paddy_super_sub_v1', 'paddy_named_player_v1')):
            grouped.setdefault(q['market'], []).append(q)
    # Duplicate contracts/lines with conflicting identity/price are held, not cherry-picked.
    return [qs[0] for qs in grouped.values() if len(qs)==1]


def capture(root, payload, now=None, get=None, post=None, force=False):
    now = now or datetime.now(timezone.utc)
    directory = root/'data/aerial/paddy'
    get, post = get or requests.get, post or requests.post
    status = dict(generated_at=now.isoformat(), requests=0, fixtures=0, headed_sot=0,
                  headed_goals=0, mapped_quotes=0, missing=[], errors=[])
    if not DIRECT_COLLECTION_ENABLED:
        status['status'] = 'DISABLED_BY_USER'
        save(directory/'prices.json', dict(generated_at=now.isoformat(), events=[]))
        save(directory/'status.json', status)
        return status
    last = read(directory/'status.json', {})
    # Verified 28 Oct: both website and API return country-related HTTP 403
    # from the hosted runner. Consume the existing private local capture instead;
    # never retry it through another location or relabel its original timestamp.
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        status = dict(last) if last else dict(status, status='LOCAL_CAPTURE_AWAITING_PC')
        status['transport'] = 'local_pc_private_snapshot'
        if last and last.get('status') == 'CAPTURED':
            age = now-utc(last['generated_at'])
            status['status'] = 'LOCAL_CAPTURE_READY' if timedelta(0) <= age <= timedelta(hours=2) else 'LOCAL_CAPTURE_STALE'
        save(directory/'status.json', status)
        print('Paddy header capture: '+json.dumps(status))
        return status
    if not force and last.get('generated_at') and timedelta(0) <= now-utc(last['generated_at']) < timedelta(minutes=5):
        return {**last, 'cache_reused': True}
    targets = sorted([f for f in payload.get('fixtures', [])
                      if f.get('competition') in COMPETITIONS and len(f.get('teams', []))==2
                      and now+timedelta(minutes=5) < utc(f['kickoff']) <= now+timedelta(hours=30)],
                     key=lambda f:f['kickoff'])[:40]
    started = time.monotonic()
    def request(method, url, **kw):
        if status['requests'] >= 8 or time.monotonic()-started > 55:
            raise ValueError('Paddy bounded request budget reached')
        status['requests'] += 1
        response = method(url, timeout=8, **kw)
        response.raise_for_status()  # No retries on blocks, challenges or rate limits.
        return response
    try:
        if not targets:
            save(directory/'prices.json', dict(generated_at=now.isoformat(), events=[]))
            status['status'] = 'NO_UPCOMING_SUPPORTED_FIXTURES'
        else:
            html = request(get, 'https://www.paddypower.com/football').text
            key, endpoints = context(html)
            sources = []
            catalogues = {}
            for competition in sorted({f['competition'] for f in targets}):
                data = request(get, endpoints['competitionPage'], params={**PARAMS, '_ak':key,
                    'eventTypeId':1, 'competitionId':COMPETITIONS[competition],
                    'includeLayout':'true', 'includePrices':'false'}).json()
                if not isinstance(data.get('attachments', {}).get('events'), dict):
                    raise ValueError('Invalid competition catalogue')
                catalogues[competition] = data
                sources.extend(data['attachments']['events'].values())
            matched = []
            for f in targets:
                candidates = [e for e in sources if matches(e, f, now)]
                if len(candidates)==1: matched.append((candidates[0], f))
                else: status['missing'].append(dict(fixture_id=f['id'], reason='no_unique_exact_fixture'))
            events = []
            for start in range(0, len(matched), 20):
                batch = matched[start:start+20]
                body = dict(eventIds=[e['eventId'] for e,f in batch], marketTypeCodes=list(TYPES),
                    includePrices=True, priceHistory=1, exchangeLocale='en_GB', currencyCode='GBP',
                    language='en', regionCode='UK')
                raw = request(post, endpoints['markets'], params={'_ak':key}, json=body).json()
                if not isinstance(raw.get('markets'), dict): raise ValueError('Invalid markets response')
                observed = datetime.now(timezone.utc).isoformat()
                # Raw market IDs and exact prices survive independently of model selection.
                raw_hash = sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
                save(directory/f'raw-{start//20}.json.gz', dict(captured_at=observed,
                    request=body, response=raw, catalogues=catalogues, sha256=raw_hash))
                for e,f in batch:
                    event = normalize(e, f, raw['markets'], observed, raw_hash)
                    if event:
                        events.append(event)
                        if not event['quotes']: status['missing'].append(dict(fixture_id=f['id'], reason='requested_markets_not_returned'))
            save(directory/'prices.json', dict(generated_at=now.isoformat(), events=events))
            quotes = [q for e in events for q in e['quotes']]
            status.update(status='CAPTURED', fixtures=len(events),
                headed_sot=sum(q['market']=='1+ headed shot on target' for q in quotes),
                headed_goals=sum(q['market']=='headed goal' for q in quotes),
                mapped_quotes=sum(q['identity_status']=='exact_roster' for q in quotes))
    except (requests.RequestException, ValueError, TypeError, KeyError, OSError) as exc:
        # Never expose a request URL containing client configuration in health logs.
        status.update(status='FAILED', errors=[type(exc).__name__])
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            status['http_status'] = exc.response.status_code
    save(directory/'status.json', status)
    print('Paddy header capture: '+json.dumps(status))
    return status
