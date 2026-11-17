"""Settlement-only OnCourt non-played results; never a training input."""
import csv
import os
import tempfile
from pathlib import Path

FIELDS = ['winner_id', 'loser_id', 'tour_id', 'round_id', 'result', 'date',
          'date_source', 'status']
WALKOVERS = {'w/o', 'wo', 'w.o.', 'walkover', 'walk over'}


def nonplayed_row(winner, loser, edition, round_id, result, match_date,
                  fallback_date=''):
    """Preserve unknown text for audit, but only explicit walkovers are actionable.

    winner/loser are source column names, not a claim that a match was played
    or evidence about which player withdrew.
    """
    raw = str(result or '').strip()
    if not raw or raw[0].isdigit() or winner is None or loser is None:
        return None
    day = match_date or fallback_date or ''
    if hasattr(day, 'strftime'):
        day = day.strftime('%Y-%m-%d')
    return dict(winner_id=winner, loser_id=loser, tour_id=edition or 0,
                round_id=round_id or 0, result=raw, date=day,
                date_source='match' if match_date else 'tournament_fallback',
                status='walkover' if raw.casefold() in WALKOVERS else 'unresolved')


def write_sidecar(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def verified_nonplayed(path):
    """No guessed dates, byes, defaults, unknown statuses or stats manufacture."""
    path = Path(path)
    if not path.exists():
        return
    seen = set()
    with path.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if (row.get('status') != 'walkover' or row.get('date_source') != 'match'
                    or row.get('result', '').strip().casefold() not in WALKOVERS):
                continue
            key = tuple(row.get(k, '') for k in FIELDS)
            if key not in seen:
                seen.add(key)
                yield row


def settlement_games(directory, tour, played_reader):
    """Merge only for settlement; conflicting played/non-played records are held."""
    directory = Path(directory)
    def identity(row):
        return (row.get('tour_id'), row.get('round_id'),
                tuple(sorted((row.get('winner_id',''), row.get('loser_id','')))))
    extras = {}
    for row in verified_nonplayed(directory / f'nonplayed-results_{tour}.csv'):
        extras.setdefault(identity(row), []).append(row)
    collisions = set()
    for row in played_reader(directory / f'games_{tour}.csv'):
        key = identity(row)
        if key in extras:
            collisions.add(key)
        else:
            yield row
    for key, rows in extras.items():
        if key not in collisions and len(rows) == 1:
            yield rows[0]
