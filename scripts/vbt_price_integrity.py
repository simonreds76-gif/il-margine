"""Reviewed historical quote corrections and a fail-closed source sanity check.

This is ingestion validation, not a betting rule or a market-movement model.
An outlier is held for review; it is never silently replaced with opening odds.
"""
import json
import math
from functools import lru_cache
from pathlib import Path


def pair(row, snapshot):
    try:
        values = [float(row['cote1_' + snapshot]), float(row['cote2_' + snapshot])]
    except (KeyError, TypeError, ValueError):
        return None
    return values if all(math.isfinite(v) and 1 < v < 1001 for v in values) else None


@lru_cache(maxsize=1)
def corrections():
    path = Path(__file__).resolve().parents[1] / 'config/tennis-price-corrections.json'
    rows = json.loads(path.read_text(encoding='utf-8'))
    index = {r['sourceId']: r for r in rows}
    if len(index) != len(rows):
        raise ValueError('Duplicate reviewed tennis price correction')
    return index


def reviewed_price(row):
    correction = corrections().get(row.get('match_id'))
    if correction is None:
        return None
    if (row['date'][:10] != correction['sourceDate'] or
            [row['joueur1_id'], row['joueur2_id']] != correction['sourcePlayerIds']):
        raise ValueError('Reviewed tennis price identity changed; manual review required')
    if pair(row, 'cloture') not in (correction['oldSourceOdds'], correction['sourceOdds']):
        raise ValueError('Reviewed tennis price source changed; manual review required')
    if not all(math.isfinite(v) and 1 < v < 1001 for v in correction['sourceOdds']):
        raise ValueError('Invalid reviewed tennis prices')
    return correction


def suspicious_close(row):
    opening, closing = pair(row, 'ouverture'), pair(row, 'cloture')
    if not opening or not closing:
        return False
    probability = lambda values: values[1] / sum(values)
    # Large moves towards a near-certain outcome need timestamp/source review.
    # This alone does not establish an error or an in-play capture.
    return min(closing) < 1.10 and abs(probability(opening) - probability(closing)) > .20
