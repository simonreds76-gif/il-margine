"""Bookmaker count contracts whose outcome is already determined on retirement.

Sisal U/O ACE GIOCATORE X and U/O DOPPI FALLI GIOCATORE X, verified
2026-10-27: https://www.sisal.it/content/dam/new-dam/italy/canali/sisal-it/doc-pdf/scommesse/info-scommesse/tennis.pdf
Incomplete counts must never become complete-match calibration targets.
"""
from math import isfinite


def determined_count(bookmaker, market, actual, line, score=""):
    book = str(bookmaker or "").strip().casefold()
    allowed = {"aces", "double_faults"}
    if book == "bet365":
        allowed |= {"match_aces", "match_double_faults"}
    elif book != "sisal it":
        return False
    if market not in allowed:
        return False
    if any(x in str(score).upper() for x in ("W/O", "WALKOVER", "DEF.", "DEFAULT")):
        return False
    try:
        count, threshold = float(actual), float(line)
        return isfinite(count) and isfinite(threshold) and count >= 0 and count > threshold
    except (TypeError, ValueError):
        return False
