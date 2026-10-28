"""Bounded Bet365 price source; no credentials, model changes or inferred prices.

Verified 2026-10-28 against the rendered sportsbook. Only named-player full-match
GK saves / aces / double faults, plus verified named-player headed SOT.
Freshness uses the individual market's poll, never its last price change or the
fixture poll. All original quotes remain in the private capture evidence.
"""
from __future__ import annotations

import copy
import gzip
import json
import math
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://moviodds.com/odds'
GROUPS = {'soccer': {'177703': ('Goalkeeper Saves', 'Player Saves'),
                     '177727': ('Headed Shots on Target', 'Player Headed Shots on Target')},
          'tennis': {'130440': ('Ace Totals', 'Player Aces'),
                     '130443': ('Double Fault Totals', 'Player Double Faults')}}
LEAGUES = {'England Premier League': 'england-premier-league',
           'Italy Serie A': 'italy-serie-a', 'Spain La Liga': 'spain-la-liga',
           'Germany Bundesliga I': 'germany-bundesliga',
           'Germany Bundesliga': 'germany-bundesliga', 'France Ligue 1': 'france-ligue-1'}
MAX_AGE = timedelta(minutes=10)


def utc(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d if d.tzinfo else None
    except (ValueError, TypeError):
        return None


def key(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower())


def fresh(value, now, age=MAX_AGE):
    stamp = utc(value)
    return bool(stamp and timedelta(seconds=-30) <= now-stamp <= age)


def enabled(sport):
    cfg = json.loads((ROOT/'config/odds-api-bookmaker-allocation.json').read_text(encoding='utf-8-sig'))
    return cfg.get('direct_moviodds', {}).get(sport, False)


def download(sport, get=None):
    # Requests transparently decompresses gzip; cap decompressed bytes too.
    # One request, no retry loop, no account key and no browser bypass.
    response = (get or requests.get)(URL, params={'sport': sport, 'groups': ','.join(GROUPS[sport]), 'links': '1'},
                                    headers={'Accept-Encoding': 'gzip', 'User-Agent': 'IlMargineResearch/1.0'},
                                    timeout=(5, 20), stream=True)
    try:
        response.raise_for_status()
        body = bytearray()
        started = time.monotonic()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > 8_000_000 or time.monotonic()-started > 25:
                raise ValueError('MoviOdds response exceeded bounded capture')
        return json.loads(body)
    finally:
        response.close()


def normalize(data, sport, now, *, targets=(), days_ahead=3):
    skipped = Counter()
    if (not isinstance(data, dict) or data.get('warming') or data.get('warming_up')
            or not fresh(data.get('server_time'), now, timedelta(minutes=2))
            or not isinstance(data.get('matches'), list)):
        raise ValueError('Missing, stale or warming MoviOdds snapshot')
    output = []
    fixture_counts = Counter(str(m.get('id')) for m in data['matches'] if isinstance(m, dict))
    for m in data['matches']:
        if not isinstance(m, dict):
            continue
        start = utc(m.get('kickoff_utc'))
        if (m.get('sport') != sport or m.get('in_play') is not False or m.get('suspended')
                or m.get('removed') or not start or not now < start <= now+timedelta(days=days_ahead)
                or fixture_counts[str(m.get('id'))] != 1):
            skipped['fixture_not_eligible'] += 1
            continue
        if sport == 'soccer':
            from football_grosvenor import team_key, target_competition
            league = LEAGUES.get(m.get('league'))
            matched = [t for t in targets if league and target_competition(t) == league
                       and utc(t.get('date') or t.get('startTime')) == start
                       and all(t.get(s) and m.get(s) and team_key(t[s]) == team_key(m[s]) for s in ('home', 'away'))]
            if len(matched) != 1:
                skipped['unmatched_or_unsupported_fixture'] += 1
                continue
            event = copy.deepcopy(matched[0])
        else:
            league = str(m.get('league') or '')
            if (not re.match(r'^(ATP|WTA)\s', league) or re.search(r'Challenger|ITF|125|Doubles|Qualif', league, re.I)
                    or any(not m.get(s) or '/' in m[s] or ' & ' in m[s] for s in ('home', 'away'))
                    or key(m['home']) == key(m['away'])):
                skipped['unsupported_tennis_fixture'] += 1
                continue
            # Prefer the existing discovery's fixture ID and tournament metadata.
            # The source calls some WTA125 events simply "WTA <city>"; that alone
            # must never promote a lower-tier event into a main-tour model.
            matched = [t for t in targets if utc(t.get('date')) == start
                       and {key(t.get('home')), key(t.get('away'))} == {key(m['home']), key(m['away'])}]
            if len(matched) > 1:
                skipped['ambiguous_tennis_fixture'] += 1
                continue
            if matched:
                event = copy.deepcopy(matched[0])
            else:
                from tennis_tournament_category import resolve_category
                category = resolve_category(league, m['kickoff_utc']) if league.startswith('ATP ') else {}
                if category.get('official_category') not in {'ATP250','ATP500','Masters 1000','Grand Slam','Masters Cup'}:
                    skipped['unverified_tennis_edition'] += 1
                    continue
                tour, tournament = league.split(' ', 1)
                event = {'id': 'bet365:'+str(m['id']), 'home': m['home'], 'away': m['away'],
                         'date': m['kickoff_utc'], 'league': {'name': tour+' - '+tournament}}
        markets = []
        for gid, (original_name, name) in GROUPS[sport].items():
            status = (m.get('group_status') or {}).get(gid) or {}
            polled = status.get('polled_at')
            if (status.get('stale') or status.get('suspended') or status.get('removed')
                    or not fresh(polled, now)):
                skipped['stale_or_missing_market_poll'] += 1
                continue
            props, conflicts = {}, set()
            for q in m.get('quotes') or []:
                if str(q.get('group_id')) != gid:
                    continue
                price = q.get('odds_dec')
                if (str(q.get('fixture_id')) != str(m['id']) or q.get('group_name') != original_name
                        or q.get('suspended') or q.get('removed') or q.get('stale')
                        or str(q.get('sel_id', '0')) in {'', '0'}
                        or not isinstance(price, (float, int)) or isinstance(price, bool)
                        or not math.isfinite(price) or price <= 1
                        or not utc(q.get('ts')) or utc(q['ts']) > utc(polled)+timedelta(seconds=30)):
                    skipped['invalid_or_suspended_quote'] += 1
                    continue
                # Exact verified market IDs: no set/period/combined contracts.
                allowed_ids = {'177703', '177769'} if gid == '177703' else {gid}
                if str(q.get('market_id')) not in allowed_ids:
                    skipped['unverified_market_id'] += 1
                    continue
                player = str(q.get('line' if sport == 'soccer' else 'side') or '').strip()
                milestone = re.fullmatch(r'([1-9]\d*)\+', str(q.get('side' if sport == 'soccer' else 'line') or ''))
                if not player or not milestone or (sport == 'tennis' and key(player) not in {key(m['home']), key(m['away'])}):
                    skipped['non_named_player_or_non_milestone'] += 1
                    continue
                line = int(milestone[1])-.5
                if sport == 'soccer' and (gid != '177727' or q.get('handicap') is not None):
                    try:
                        if float(q.get('handicap')) != line:
                            raise ValueError()
                    except (TypeError, ValueError):
                        skipped['line_disagreement'] += 1
                        continue
                if gid == '177727':
                    # The source explicitly supplies the player's club in n2.
                    # Never guess the side from player ordering or name alone.
                    sides = [i+1 for i, s in enumerate(('home', 'away'))
                             if q.get('n2') and team_key(q['n2']) == team_key(m[s])]
                    if len(sides) != 1:
                        skipped['unmapped_player_team'] += 1
                        continue
                    player = f'{player} ({sides[0]})'
                fraction = re.fullmatch(r'(\d+)/(\d+)', str(q.get('odds_frac') or ''))
                if not fraction or int(fraction[2]) == 0 or abs(price-(1+int(fraction[1])/int(fraction[2]))) > 1e-7:
                    skipped['fraction_decimal_disagreement'] += 1
                    continue
                k = (key(player), line)
                if k in props and props[k]['over'] != price:
                    conflicts.add(k)
                props[k] = {'label': player, 'hdp': line, 'over': price, 'raw_quote': q}
            odds = [v for k, v in props.items() if k not in conflicts]
            skipped['conflicting_quotes'] += len(conflicts)
            if odds:
                markets.append({'name': name, 'odds': odds, 'source': 'moviodds_bet365',
                                'source_event_id': str(m['id']), 'source_group_id': gid,
                                'source_url': URL+'?sport='+sport+'&groups='+gid,
                                'captured_at': polled, 'updatedAt': max(p['raw_quote']['ts'] for p in odds),
                                'settlement_policy': 'bet365_named_nonstarter_void_v1; standard_no_promotional_replacement'
                                if sport == 'soccer' else 'bet365_named_full_match; retirement_void_unless_determined',
                                'raw_group_status': status})
        if markets:
            link = (m.get('links') or {}).get('match', '')
            event['urls'] = {'Bet365': link if link.startswith('https://www.bet365.com/') else ''}
            event['bookmakers'] = {'Bet365': markets}
            output.append(event)
    return output, dict(skipped)


def capture(sport, *, targets=(), days_ahead=3, get=None, raw_path=None, force=False):
    receipt = {'source': 'moviodds_bet365', 'status': 'DISABLED', 'requests': 0, 'market_count': 0, 'errors': []}
    if not force and not enabled(sport):
        return [], receipt
    try:
        receipt['requests'] = 1
        data = download(sport, get)
        now = datetime.now(timezone.utc)
        receipt['received_at'] = now.isoformat()
        events, skipped = normalize(data, sport, now, targets=targets, days_ahead=days_ahead)
        receipt.update(status='OK' if events else 'NO_VERIFIED_MARKETS', excluded=skipped,
                       market_count=sum(len(e['bookmakers']['Bet365']) for e in events),
                       quote_count=sum(len(m['odds']) for e in events for m in e['bookmakers']['Bet365']))
        if raw_path:
            raw_path = Path(raw_path)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            temp = raw_path.with_suffix(raw_path.suffix+'.tmp')
            temp.write_bytes(gzip.compress(json.dumps({'receipt': receipt, 'raw': data}).encode()))
            temp.replace(raw_path)
        return events, receipt
    except (requests.RequestException, OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        receipt.update(status='SOURCE_FAILED', errors=[type(error).__name__])
        return [], receipt


def merge_football(payload, targets, *, days_ahead=7, **kwargs):
    events, receipt = capture('soccer', targets=targets, days_ahead=days_ahead, **kwargs)
    # Retain existing books. If another route supplies Bet365 for the same event,
    # retain that whole book instead of mixing timestamps/contracts or duplicating.
    result = copy.deepcopy(payload)
    for e in events:
        existing = [x for x in result if str(x.get('id')) == str(e['id'])]
        if not existing:
            result.append(e)
        elif len(existing) == 1 and not any(b.casefold() == 'bet365' for b in existing[0].get('bookmakers', {})):
            existing[0].setdefault('bookmakers', {}).update(e['bookmakers'])
            existing[0].setdefault('urls', {}).update(e['urls'])
    return result, receipt


def refresh_headed(root, payload, now=None):
    """One bounded price read on the existing Skyline publication cycle.

    The independent hourly GK job can precede lineup publication by more than
    the price lifetime. Refresh here rather than relaxing the freshness rule.
    This writes only a separate price snapshot, never forecasts or results.
    """
    from aerial_market_capture import retain_headed_markets
    now = now or datetime.now(timezone.utc)
    leagues = {'Premier League':'england-premier-league','Serie A':'italy-serie-a',
               'Bundesliga':'germany-bundesliga','La Liga':'spain-la-liga','Ligue 1':'france-ligue-1'}
    targets = []
    for f in payload.get('fixtures', []):
        teams=f.get('teams', []);start=utc(f.get('kickoff'))
        if (f.get('competition') not in leagues or f.get('state') not in ('expected','confirmed')
                or len(teams)!=2 or not start or not now+timedelta(minutes=5)<start<=now+timedelta(hours=30)):
            continue
        targets.append({'id':'aerial:'+str(f['id']),'home':teams[0]['name'],'away':teams[1]['name'],
                        'date':f['kickoff'],'league':{'slug':leagues[f['competition']]}})
    folder=Path(root)/'data/aerial/moviodds';folder.mkdir(parents=True,exist_ok=True)
    if targets:
        events, receipt=capture('soccer',targets=targets,days_ahead=2,raw_path=folder/'latest.json.gz')
    else:
        events, receipt=[], {'source':'moviodds_bet365','status':'NO_ELIGIBLE_FIXTURES','requests':0,'errors':[]}
    retain_headed_markets(folder/'prices.json',events,{},now.isoformat())
    receipt['generated_at']=now.isoformat()
    receipt['headed_quotes']=sum(len(m['odds']) for e in events for m in e['bookmakers']['Bet365']
                                  if m['name']=='Player Headed Shots on Target')
    temp=folder/'status.tmp';temp.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    temp.replace(folder/'status.json')
    return receipt
