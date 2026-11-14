"""Resolve cosmetic provider event labels only against a unique native fixture.

Raw provider evidence is retained by the collectors. Never infer a player from a
surname, merge editions, remove qualifying/Challenger labels or change a forecast.
"""
import csv
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

def normal(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))
from tennis_price_identity import canonical_price_name


def player_name(value):
    return canonical_price_name(normal(value))


@lru_cache(maxsize=8)
def _tables(paths):
    result = []
    for path, _ in paths:
        with Path(path).open(encoding='utf-8-sig', newline='') as f:
            result.append(list(csv.DictReader(f)))
    return result


def event_tournament(root, event, label, tour):
    """Keep the source label unless pair, tour, date and native edition agree."""
    if tour not in {'ATP', 'WTA'}:
        return label
    pair = {player_name(event.get('home')), player_name(event.get('away'))}
    if len(pair) != 2 or '' in pair:
        return label
    try:
        day = date.fromisoformat(str(event.get('date', ''))[:10])
        folder = Path(root) / 'data/oncourt'
        paths = [folder / f'{name}_{tour.lower()}.csv' for name in ('players', 'tours', 'today')]
        players, tours, fixtures = _tables(tuple((str(p), p.stat().st_mtime_ns) for p in paths))
    except (OSError, ValueError, TypeError):
        return label
    board_path=Path(root)/'data/tennis-props/player-props-board.csv'
    try:
        boards=_tables(((str(board_path),board_path.stat().st_mtime_ns),))[0]
    except OSError:
        boards=[]
    names = {p['id']: player_name(p.get('name')) for p in players}
    editions = {t['id']: t for t in tours}
    candidates = []
    for fixture in fixtures:
        if {names.get(fixture.get('player1_id')), names.get(fixture.get('player2_id'))} != pair:
            continue
        if str(fixture.get('result') or '').strip() or str(fixture.get('live') or '').strip() not in ('', '0'):
            continue
        if fixture.get('date') and fixture['date'][:10] != day.isoformat():
            continue
        edition = editions.get(fixture.get('tour_id'), {})
        try:
            start = date.fromisoformat(edition['date'][:10])
        except (KeyError, ValueError, TypeError):
            continue
        if not start - timedelta(days=3) <= day <= start + timedelta(days=13):
            continue
        native_pair={fixture.get('player1_id'),fixture.get('player2_id')}
        labels={b.get('tournament') for b in boards if b.get('tour_id')==fixture.get('tour_id')
                and b.get('tour')==tour and b.get('date')==day.isoformat()
                and {b.get('player_id'),b.get('opponent_id')}==native_pair
                and {player_name(b.get('player')),player_name(b.get('opponent'))}==pair
                and b.get('tournament')}
        if len(labels)>1:continue
        target_label=next(iter(labels)) if labels else edition.get('name','')
        source, target = normal(label), normal(target_label)
        # Only an optional terminal "Open" is cosmetic here. All other words,
        # numbers, tour levels and qualification labels remain significant.
        bare = lambda value: re.sub(r' open$', '', value)
        if not target or bare(source) != bare(target):
            continue
        candidates.append((fixture.get('tour_id'), fixture.get('round_id'), target_label))
    return candidates[0][2] if len(candidates) == 1 else label
