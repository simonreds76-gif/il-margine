"""Conservative cross-provider tournament labels, verified against native editions.

No pricing or eligibility changes. City aliases never imply a tournament alone.
"""
import csv
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
import re
import unicodedata


def normal(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.findall(r'[a-z0-9]+', text))


@lru_cache(maxsize=4)
def _native(folder, tournaments_stamp, schedule_stamp):
    def read(name):
        with (Path(folder) / name).open(encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))
    return {r['id']: r for r in read('tours_atp.csv')}, read('today_atp.csv')


def same_edition_label(quote, board, root):
    """Preserve exact labels; expand aliases only with a unique current native pair."""
    left, right = normal(quote.get('tournament')), normal(board.get('tournament'))
    if not left or not right:
        return False
    if left == right:
        return True
    if str(quote.get('tour', '')).upper() != 'ATP' or str(board.get('tour', '')).upper() != 'ATP':
        return False
    try:
        tid, p1, p2 = (str(int(board[k])) for k in ('tour_id', 'player_id', 'opponent_id'))
        if min(map(int, (tid, p1, p2))) <= 0 or p1 == p2:
            return False
        folder = Path(root) / 'data/oncourt'
        tours, fixtures = _native(str(folder), (folder/'tours_atp.csv').stat().st_mtime_ns,
                                  (folder/'today_atp.csv').stat().st_mtime_ns)
        edition = tours.get(tid, {})
        name = normal(edition.get('name'))
        day = date.fromisoformat(str(quote.get('date', ''))[:10])
        edition_day = date.fromisoformat(str(edition.get('date', ''))[:10])
        if not edition_day - timedelta(days=3) <= day <= edition_day + timedelta(days=13):
            return False
    except (KeyError, ValueError, TypeError, OSError):
        return False
    if not re.search(r'\b(atp finals|world tour finals|masters cup)\b', name):
        return False
    if any(term in name for term in ('next gen', 'nextgen', 'challenger', 'junior', 'wta')):
        return False
    aliases = {'finals', 'atp finals', 'nitto atp finals', 'world tour finals', 'masters cup', name}
    # Turin/Finals aliases apply only to the dated native Finals edition in Turin.
    if re.search(r'\b(turin|torino)\b', name):
        aliases.update(('turin', 'torino'))
    def without_current_year(value):
        years = re.findall(r'\b20\d\d\b', value)
        if any(int(y) != edition_day.year for y in years):
            return ''
        return ' '.join(re.sub(r'\b20\d\d\b', '', value).split())
    if without_current_year(left) not in aliases or without_current_year(right) not in aliases:
        return False
    pair = {p1, p2}
    exact = [r for r in fixtures if r.get('tour_id') == tid
             and {r.get('player1_id'), r.get('player2_id')} == pair]
    # Never bridge duplicate rounds, a completed fixture, a live match or another edition.
    return (len(exact) == 1 and not str(exact[0].get('result') or '').strip()
            and str(exact[0].get('live') or '').strip() in ('', '0'))
