"""Comparison-only Paddy Power full-match saves from the existing football poll."""
import re
from datetime import timedelta

from football_count_markets import normalize_market_name
from football_grosvenor import team_key
from goalkeeper_price_selection import normalized, number, stamp


def unavailable(item):
    return any(item.get(flag) for flag in ('suspended', 'removed', 'inPlay', 'in_play', 'live')) or (
        str(item.get('status', '')).casefold() in {'live', 'inplay', 'in-play', 'suspended', 'closed', 'settled', 'finished'})


def capture_paddy_prices(events, now):
    """Keep only explicit team or named contracts, with both observation times."""
    rows = []
    for event in events:
        kickoff = stamp(event.get('date') or event.get('startTime'))
        home, away = event.get('home'), event.get('away')
        if unavailable(event) or not kickoff or kickoff <= now or not all((event.get('id'), home, away)):
            continue
        for market in (event.get('bookmakers') or {}).get('Paddy Power', []) or []:
            if not isinstance(market, dict) or unavailable(market):
                continue
            name = normalize_market_name(market.get('name'))
            ladder = re.fullmatch(r'goalkeeper to make ([1-9]\d*) or more saves', name)
            team = re.fullmatch(r'goalkeeper saves (home|away)', name)
            if not ladder and not team and name not in {'goalkeeper saves', 'player saves', 'player goalkeeper saves'}:
                continue
            for offer in market.get('odds') or []:
                if not isinstance(offer, dict) or unavailable(offer):
                    continue
                updated = stamp(offer.get('updatedAt') or market.get('updatedAt'))
                if not updated or not timedelta(0) <= now-updated <= timedelta(minutes=10):
                    continue
                label = str(offer.get('label') or offer.get('name') or '').strip()
                venue = team[1] if team else ''
                if not venue and label:
                    for side, club in [('home', home), ('away', away)]:
                        if normalized(label) in {normalized(side), normalized(side+' goalkeeper'),
                                                normalized(club+' goalkeeper')}:
                            venue = side
                if ladder:
                    line = int(ladder[1]) - .5
                    if label:
                        outcomes = [(venue, '' if venue else label, 'over', offer.get('price') or offer.get('odds'))]
                    else:
                        outcomes = [(side, '', 'over', offer.get(side)) for side in ('home', 'away')]
                else:
                    line = number(offer.get('hdp'))
                    if line is None or line < 0 or line % 1 not in (0, .5) or not (venue or label):
                        continue
                    outcomes = [(venue, '' if venue else label, side, offer.get(side)) for side in ('over', 'under')]
                for side, keeper, direction, value in outcomes:
                    odds = number(value)
                    if odds is None or odds <= 1:
                        continue
                    rows.append(dict(event_id=str(event['id']), home_team=home, away_team=away,
                                     kickoff_at=kickoff.isoformat(), venue=side, goalkeeper=keeper,
                                     line=line, side=direction, odds=odds, captured_at=updated.isoformat(),
                                     checked_at=now.isoformat()))
    return rows


def matching_paddy_prices(row, snapshot, bet365_names, venue, now):
    if not row.get('home_team') or not row.get('away_team'):
        return []
    matches = []
    for offer in snapshot:
        updated, checked = stamp(offer.get('captured_at')), stamp(offer.get('checked_at'))
        if (not updated or not checked or not updated <= checked <= now
                or now-updated > timedelta(minutes=10)
                or str(row.get('event_id')) != offer['event_id'] or stamp(row.get('kickoff_at')) != stamp(offer['kickoff_at'])
                or any(team_key(row[k]) != team_key(offer[k]) for k in ('home_team', 'away_team'))
                or number(row.get('line')) != offer['line'] or row.get('side') != offer['side']):
            continue
        if offer['venue']:
            if offer['venue'] != venue:
                continue
            scope = 'team_goalkeeper_' + venue
        else:
            if normalized(offer['goalkeeper']) not in bet365_names:
                continue
            scope = 'named_player'
        matches.append(dict(bookmaker='Paddy Power', goalkeeper=offer['goalkeeper'], odds=offer['odds'],
                            captured_at=offer['captured_at'], contract_scope=scope, observed_only=False))
    return matches
