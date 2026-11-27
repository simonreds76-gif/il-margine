"""Shared keeper pick identities and Telegram delivery checks for the two publishers."""
import html
import json
import re

from goalkeeper_price_selection import normalized, number


def pick_keys(row):
    event, line, side = row.get('event_id'), number(row.get('line')), row.get('side')
    keeper = normalized(row.get('goalkeeper'))
    if not event or not keeper or line is None or side not in ('over', 'under'):
        return set()
    subjects = {keeper}
    scope = row.get('contract_scope') or ''
    if scope in ('team_goalkeeper_home', 'team_goalkeeper_away'):
        subjects.add(scope.split('_')[-1] + 'goalkeeper')
        named = {normalized(q['goalkeeper']) for q in row.get('display_prices', [])
                 if q.get('bookmaker') == 'Bet365' and q.get('goalkeeper')}
        if len(named) == 1:
            subjects.update(named)
    return {f'gk_saves_v1|{event}|{subject}|{line:g}|{side}' for subject in subjects}


def digest_keys(sent):
    keys = set()
    for identity, receipt in sent.items():
        parts = identity.split('|')
        if len(parts) == 5 and parts[0] == 'gk_saves_v1':
            _, event, keeper, line, side = parts
            keys.update(pick_keys(dict(event_id=event, goalkeeper=keeper, line=line, side=side)))
            if isinstance(receipt, dict):
                keys.update(receipt.get('keeper_keys', []))
    return keys


def dedicated_keys(entries):
    return {key for item in entries.values()
            if item.get('status') in ('sent', 'delivery_unconfirmed', 'claimed')
            for key in pick_keys(item.get('signal', {}))}


def read_receipts(path, field):
    if not path.exists():
        return {}
    state = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(state.get(field), dict):
        raise ValueError('Keeper delivery ledger has an unexpected format')
    return state[field]


def three_books(prices):
    return {'bet365', 'grosvenor', 'paddy power'} <= {q['bookmaker'].casefold() for q in prices}


def telegram_text_matches(result, message, *, rich=False):
    if rich:
        message = html.unescape(re.sub(r'</?(?:b|a)(?:\s[^>]*)?>', '', message))
    return isinstance(result, dict) and bool(result.get('message_id')) and result.get('text') == message
