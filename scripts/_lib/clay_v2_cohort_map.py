"""Tournament cohort mapping for the clay ML v2 research model."""

from __future__ import annotations


COHORTS = [
    "Madrid",
    "MonteCarlo",
    "Rome",
    "RolandGarros",
    "Hamburg",
    "Munich",
    "Geneva",
    "Bastad",
    "Estoril",
    "Barcelona",
    "Other",
]


def tournament_cohort(tournament: str) -> str:
    """Return the locked v2 clay cohort for a backtest tournament name."""

    text = (tournament or "").lower()
    compact = "".join(ch for ch in text if ch.isalnum())

    if "madrid" in compact:
        return "Madrid"
    if "montecarlo" in compact:
        return "MonteCarlo"
    if "internazionalibnlditalia" in compact or "rome" in compact:
        return "Rome"
    if "frenchopen" in compact or "rolandgarros" in compact:
        return "RolandGarros"
    if "hamburg" in compact:
        return "Hamburg"
    if "bmwopen" in compact or "munich" in compact:
        return "Munich"
    if "geneva" in compact:
        return "Geneva"
    if "bastad" in compact or "nordeaopen" in compact or "swedishopen" in compact:
        return "Bastad"
    if "estoril" in compact:
        return "Estoril"
    if "barcelona" in compact:
        return "Barcelona"
    return "Other"
