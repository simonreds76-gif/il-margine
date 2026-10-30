"""Fresh, bookmaker-independent contract selection for existing paper lanes."""
from datetime import datetime, timedelta, timezone
import math
from player_name_matching import fold_name_text

TOTALS = {'match_aces', 'match_double_faults'}
MAX_AGE = timedelta(minutes=30)


def norm(value):
    return ' '.join(fold_name_text(str(value or '')).lower().split())


def stamp(value):
    try:
        value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return value if value.tzinfo else None
    except (ValueError, TypeError):
        return None


def fixture(row):
    pair = sorted(norm(row.get(k)) for k in ('player', 'opponent')) if 'player' in row else sorted(norm(row.get(k)) for k in ('player1', 'player2'))
    start = stamp(row.get('match_start_utc'))
    return (row.get('date', ''), norm(row.get('tour')), norm(row.get('tournament')),
            *pair, start.isoformat() if start else '', row.get('market') or 'most_aces')


def latest_snapshot_rows(rows, now=None):
    """Newest source poll only. Never resurrect a removed line from an older poll."""
    now = now or datetime.now(timezone.utc)
    latest = {}
    for row in rows:
        captured = stamp(row.get('capture_ts'))
        if captured:
            key = (fixture(row), norm(row.get('bookmaker')))
            latest[key] = max(captured, latest.get(key, captured))
    result = []
    for row in rows:
        captured, start = stamp(row.get('capture_ts')), stamp(row.get('match_start_utc'))
        if not captured or not start or not captured <= now < start or now-captured > MAX_AGE:
            continue
        if captured == latest.get((fixture(row), norm(row.get('bookmaker')))):
            result.append(row)
    return result


def best_total_rows(rows, now=None):
    """Keep each exact selected contract once at its highest eligible fresh price.

    Leave the bookmaker's complete price pair intact for margin/quality checks;
    never manufacture a synthetic two-way market from different bookmakers.
    """
    other = [r for r in rows if r.get('market') not in TOTALS]
    chosen = {}
    for row in latest_snapshot_rows([r for r in rows if r.get('market') in TOTALS], now):
        side = row.get('recommended_side') if row.get('bettable') == 'true' else row.get('shadow_side')
        if side not in {'OVER', 'UNDER'} or not (row.get('bettable') == 'true' or row.get('trackable_shadow') == 'true'):
            continue
        try:
            line, price = float(row['line']), float(row[side.lower()+'_odds'])
        except (ValueError, TypeError, KeyError):
            continue
        if not math.isfinite(line) or not math.isfinite(price) or price <= 1:
            continue
        key = (*fixture(row), line, side)
        rank = (price, stamp(row['capture_ts']), norm(row.get('bookmaker')))
        if key not in chosen or rank > chosen[key][0]:
            chosen[key] = (rank, row)
    return other + [value[1] for value in chosen.values()]
