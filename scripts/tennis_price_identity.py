"""Exact tennis price aliases only; callers still verify pair, event and time.

OnCourt ATP 29932: Taylor Harry Fritz (1997-10-28).
Primary Sackmann ATP 126203: Taylor Fritz. No surname-only/initial matching.
Display names, saved player IDs, historical records and numerical models stay intact.
"""
def canonical_price_name(normalized):
    return {'taylor harry fritz':'taylor fritz'}.get(normalized,normalized)
