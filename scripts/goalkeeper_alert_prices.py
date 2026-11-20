"""Build the Telegram comparison for one keeper saves contract from existing captures."""
import gzip
import html
import json
from datetime import timedelta, timezone

from football_grosvenor import team_key
from goalkeeper_price_selection import contract_key, current_offers, normalized, number, stamp
from moviodds_gk_verification import reconcile
from moviodds_prices import soccer_target_matches


MAX_AGE = timedelta(minutes=10)
COMPETITIONS = {'serie-a': 'italy-serie-a', 'bundesliga': 'germany-bundesliga',
                'epl': 'england-premier-league', 'la-liga': 'spain-la-liga',
                'ligue-1': 'france-ligue-1'}


def read_capture(path):
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            data = json.load(stream)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, EOFError):
        return {}


def load_sources(folder):
    aerial = folder.parent / 'aerial'
    return (read_capture(folder / 'moviodds-direct-latest.json.gz'),
            read_capture(aerial / 'calendar.json.gz'), read_capture(aerial / 'heights.json.gz'))


def fixture_team_ids(row, calendar, now):
    kickoff = stamp(row.get('kickoff_at'))
    observed = stamp(calendar.get('observed_at'))
    if not observed or observed > now or not kickoff:
        return {}
    matches = [m for m in calendar.get('fixtures', []) if stamp(m.get('date')) == kickoff
               and all(team_key(m.get(s)) == team_key(row.get(s + '_team'))
                       and m.get(s + '_id') and m.get(s) for s in ('home', 'away'))]
    if len(matches) != 1:
        return {}
    return {s: str(matches[0][s + '_id']) for s in ('home', 'away')}


def club_for(player, roster, now):
    clubs = set()
    for member in roster.values():
        if normalized(member.get('name')) != normalized(player):
            continue
        observed = stamp(member.get('club_observed_at'))
        if (observed and timedelta(0) <= now-observed <= timedelta(days=90)
                and member.get('club_source_sha256') and member.get('team_id')
                and (member.get('role_group') == 'keepers' or member.get('positions') == 'GK')):
            clubs.add((str(member.get('id')), str(member['team_id'])))
    return next(iter(clubs))[1] if len(clubs) == 1 else None


def listed_prices(row, packet, team_ids, roster, now):
    # The receipt binds the two raw reads to the internal event. Check orientation,
    # competition and kickoff again before using any player ladder.
    raw = packet.get('raw') or {}
    if row.get('side') != 'over' or raw.get('site') != 'com':
        return []
    links = [r for r in (packet.get('receipt') or {}).get('goalkeeper_fixture_coverage', [])
             if str(r.get('event_id')) == str(row.get('event_id')) and r.get('source_event_id')]
    if len(links) != 1:
        return []
    fixture = str(links[0]['source_event_id'])
    target = dict(home=row.get('home_team'), away=row.get('away_team'), date=row.get('kickoff_at'),
                  league=COMPETITIONS.get(row.get('league'), row.get('league')))
    boards = [b for b in raw.get('matches', []) if str(b.get('id')) == fixture
              and soccer_target_matches(b, target)]
    live = (packet.get('goalkeeper_live_responses') or {}).get(fixture)
    if len(boards) != 1 or not live:
        return []
    board = boards[0]
    if board.get('in_play') is not False or board.get('suspended') or board.get('removed'):
        return []
    quotes, _ = reconcile(board, live, row['event_id'], now, display_only=True)
    if not quotes:
        return []
    observed = min(stamp(b['group_status']['177703']['polled_at']) for b in (board, live))
    scope = row.get('contract_scope') or 'named_player'
    team_contract = scope.startswith('team_goalkeeper_') and row.get('alert_model') != 'keeper_watch_v1'
    team_id = team_ids.get(scope.removeprefix('team_goalkeeper_'))
    prices = []
    for quote in quotes:
        if float(quote['handicap']) != number(row.get('line')):
            continue
        name = quote['line']
        if team_contract:
            club = club_for(name, roster, now)
            if team_id and club:
                if club != team_id:
                    continue
            elif not (row.get('identity_basis') in ('same_fixture_lineup_side','same_event_bet365_and_lineup_side')
                      and normalized(name) == normalized(row.get('goalkeeper'))):
                continue
        elif normalized(name) != normalized(row.get('goalkeeper')):
            continue
        prices.append(dict(bookmaker='Bet365', goalkeeper=name, odds=float(quote['odds_dec']),
                           captured_at=observed.isoformat(), contract_scope='named_player',
                           observed_only=live.get('source') == 'cache'))
    return prices


def paired_prices(row, offers, now, sources):
    kickoff = stamp(row.get('kickoff_at'))
    key = contract_key(row)
    fair = number(row.get('fair_odds'))
    if not key or not kickoff or kickoff <= now or fair is None or fair <= 1:
        return []
    packet, calendar, roster = sources
    team_ids = fixture_team_ids(row, calendar, now)
    venue = row.get('venue') or str(row.get('contract_scope') or '').removeprefix('team_goalkeeper_')
    if venue not in team_ids:
        club = club_for(row.get('goalkeeper'), roster, now)
        venue = next((s for s, team in team_ids.items() if team == club), None)
    quotes = []
    leagues = set()
    for offer in current_offers(offers, now):
        other = contract_key(offer)
        if (other[0] != key[0] or other[2:] != key[2:] or stamp(offer.get('kickoff_at')) != kickoff
                or now-stamp(offer['captured_at']) > MAX_AGE
                or any(team_key(offer.get(s)) != team_key(row.get(s)) for s in ('home_team','away_team'))):
            continue
        scope = offer.get('contract_scope') or 'named_player'
        same_team_market = venue in ('home', 'away') and scope == 'team_goalkeeper_' + venue
        if other != key and not same_team_market:
            continue
        if scope.startswith('team_goalkeeper_') and venue in ('home','away') and not same_team_market:
            continue
        quotes.append(dict(bookmaker=offer['bookmaker'], odds=float(offer['odds_decimal']),
                           goalkeeper=offer['goalkeeper'] if scope == 'named_player' else '',
                           contract_scope=scope, captured_at=offer['captured_at'], observed_only=False))
        if offer.get('league'):
            leagues.add(offer['league'])
    # Compact Keeper Watch reports omit the league. Recover it from this
    # fixture's exact current contract instead of guessing by club name.
    context = row
    if not row.get('league') and len(leagues) == 1:
        context = {**row, 'league':next(iter(leagues))}
    quotes += listed_prices(context, packet, team_ids, roster, now)
    groups = {}
    for q in quotes:
        identity = (q['bookmaker'].casefold(), q['contract_scope'], normalized(q['goalkeeper']))
        groups.setdefault(identity, []).append(q)
    unique = []
    for group in groups.values():
        if max(q['odds'] for q in group)-min(q['odds'] for q in group) > .0001:
            continue
        unique.append(min(group, key=lambda q:q['observed_only']))
    if not {'bet365','grosvenor'} <= {q['bookmaker'].casefold() for q in unique}:
        return []
    return sorted(unique, key=lambda q:(-q['odds'], q['bookmaker'], q['goalkeeper']))


def format_prices(row, *, rich=True):
    quotes = row['display_prices']
    push = number(row.get('push_probability')) or 0
    win = number(row.get('model_probability'))
    if win is None:
        win = (1-push)/float(row['fair_odds'])
    lines = []
    best = max(q['odds'] for q in quotes)
    for q in quotes:
        name = q['goalkeeper'] or 'team keeper'
        price = f"{q['odds']:.3f}"
        if price.endswith('0'):
            price = price[:-1]
        ev = 100*(win*q['odds']+push-1)
        label = ' · best price' if abs(q['odds']-best) < .000001 else ''
        if q['observed_only']:
            label += ' · unconfirmed feed quote'
        book = q['bookmaker']
        if rich:
            book, name, price = html.escape(book), html.escape(name), f'<b>{price}</b>'
        observed = stamp(q['captured_at']).astimezone(timezone.utc).strftime('%H:%M')
        lines.append(f"{book} · {name} · {price} · EV {ev:+.1f}%{label} · {observed} UTC")
    return '\n'.join(lines)+'\n'
