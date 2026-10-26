"""Compare current keeper/line offers before selection; no pricing-model changes."""
from datetime import datetime, timedelta
import math
import unicodedata


def stamp(value):
    try:
        d = datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
        return d if d.tzinfo else None
    except ValueError:
        return None


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').casefold()) if c.isalnum())


def contract_key(row):
    event = str(row.get('event_id') or '')
    player = normalized(row.get('goalkeeper'))
    line = number(row.get('line'))
    side = str(row.get('side') or '').casefold()
    if not event or not player or line is None or line < 0 or side not in ('over', 'under'):
        return None
    # Preserve scope and accept verified old and new lineup identity evidence.
    scope = str(row.get('contract_scope') or 'named_player')
    if scope.startswith('team_goalkeeper_'):
        if scope not in {'team_goalkeeper_home', 'team_goalkeeper_away'}:
            return None
        if row.get('identity_basis') == 'bookmaker_team_side':
            # Unknown names must not collapse into a named-player contract.
            player = scope
        elif row.get('identity_basis') not in {'same_event_bet365_and_lineup_side', 'same_fixture_lineup_side'}:
            return None
    return event, player, line, side


def current_offers(rows, now):
    """Use the newest fixture capture only, never yesterday's better quote."""
    newest = {}
    for row in rows:
        captured = stamp(row.get('captured_at'))
        event = str(row.get('event_id') or '')
        if event and captured and captured <= now:
            newest[event] = max(newest.get(event, captured), captured)
    offers = []
    for row in rows:
        key = contract_key(row)
        captured, kickoff = stamp(row.get('captured_at')), stamp(row.get('kickoff_at'))
        odds = number(row.get('odds_decimal'))
        if (not key or not captured or not kickoff or not kickoff > now
                or not timedelta(0) <= now-captured <= timedelta(hours=6)
                or captured != newest.get(key[0]) or odds is None or odds <= 1
                or not row.get('bookmaker') or row.get('blockers')
                or row.get('candidate_status') == 'blocked'):
            continue
        offers.append(row)
    return offers


def best_offers(rows, now):
    best = {}
    for row in current_offers(rows, now):
        key = contract_key(row)
        # Stable ties prefer named-player Bet365, not a second notification.
        rank = (float(row['odds_decimal']), str(row.get('bookmaker')).casefold() == 'bet365')
        previous = best.get(key)
        if previous is None or rank > (float(previous['odds_decimal']), str(previous.get('bookmaker')).casefold() == 'bet365'):
            best[key] = row
    return list(best.values())


def alert_price_check(row, offers, now):
    key = contract_key(row)
    comparable = [q for q in current_offers(offers, now) if contract_key(q) == key] if key else []
    own = [q for q in comparable if str(q['bookmaker']).casefold() == str(row.get('bookmaker') or 'Bet365').casefold()]
    if not own:
        return 'current_quote_unavailable', []
    price = number(row.get('odds_decimal'))
    if price is None or not any(abs(float(q['odds_decimal'])-price) < 1e-8 for q in own):
        return 'recorded_price_changed', []
    if any(float(q['odds_decimal']) > price + 1e-8 for q in comparable):
        return 'better_bookmaker_price_available', []
    comparison = [dict(bookmaker=q['bookmaker'], odds=float(q['odds_decimal']), captured_at=q['captured_at'],
                       contract_scope=q.get('contract_scope') or 'named_player') for q in sorted(comparable, key=lambda q: -float(q['odds_decimal']))]
    return None, comparison
