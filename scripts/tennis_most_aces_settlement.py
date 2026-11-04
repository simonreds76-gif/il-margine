"""Settle priced Most Aces evidence using the shared, bounded result index.

No registration, price refresh, repricing or alert dispatch. Used by the local
morning/nightly evidence runner independently of successful new price capture.
"""
from collections import defaultdict
from datetime import datetime, timezone
import json


def protected(row):
    note = row.get('settlement_note', '')
    return (row.get('settlement_status') == 'quarantined'
            or bool(row.get('quarantine_reason')) or bool(row.get('duplicate_of_signal_id'))
            or note.startswith(('duplicate_', 'void_replaced_match')))


def pending_signals(rows):
    return [dict(date=r.get('date'), tour=r.get('tour'), tournament=r.get('tournament'),
                 player=r.get('player1'), opponent=r.get('player2'))
            for r in rows if not protected(r) and r.get('settlement_status', 'pending') in ('', 'pending')]


def settle_priced(rows, result_index, counts, shadow):
    direct = defaultdict(list)
    for signal in pending_signals(rows):
        year = counts['parse_year'](signal.get('date'))
        if not year:
            continue
        key = (str(signal.get('tour') or '').upper(), year,
               counts['pair_key'](signal['player'], signal['opponent']))
        pair = shadow['pair_key'](signal['player'], signal['opponent'])
        for match in result_index.get(key, []):
            if match not in direct[pair]:
                direct[pair].append(match)
    # Keep quarantines and historical outcomes exactly as recorded, even when
    # another lane is requested to recheck older settlements.
    active = [r for r in rows if not protected(r)]
    return shadow['settle'](active, {}, direct_index=direct)


def refresh_current_records(path, rows, record_fn):
    """Refresh displayed ROI without relabelling old forecasts/prices as fresh."""
    if not path.exists():
        return
    report = json.loads(path.read_text(encoding='utf-8-sig'))
    report['records'] = [record_fn(rows, name) for name in sorted({r.get('model', '') for r in rows if r.get('model')})]
    report['records_updated_at'] = datetime.now(timezone.utc).isoformat()
    temp = path.with_suffix('.settlement.tmp')
    temp.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)
