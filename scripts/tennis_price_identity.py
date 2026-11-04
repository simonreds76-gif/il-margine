"""Exact tennis price aliases only; callers still verify pair, event and time.

OnCourt ATP 29932: Taylor Harry Fritz (1997-10-28).
Primary Sackmann ATP 126203: Taylor Fritz. No surname-only/initial matching.
Display names, saved player IDs, historical records and numerical models stay intact.

Daniel Merida / Daniel Merida Aguilar: ATP M0N7, native 83223,
Sackmann 210017; Spain, DOB 2004-09-26. Verified against ATP biography:
https://www.atptour.com/es/players/daniel-merida/m0n7/bio
"""
def canonical_price_name(normalized):
    return {'taylor harry fritz':'taylor fritz',
            'daniel merida aguilar':'daniel merida'}.get(normalized,normalized)
