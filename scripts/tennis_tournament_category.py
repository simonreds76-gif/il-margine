"""Season-scoped tournament identity. OnCourt rank 2 is not an ATP tier.

New forecasts and selections use this resolver. Historical issued rows retain
their recorded model buckets. Unknown editions fail closed for new signals.
"""
from __future__ import annotations

import re
import unicodedata

POLICY_VERSION = "atp-category-20261001-v2-live"
CALENDAR_2026 = "https://www.atptour.com/en/news/what-is-the-2026-atp-tour-calendar/"
CALENDAR_CHANGE = "https://www.atptour.com/en/news/2026-atp-tour-calendar-announced"

# Edition-specific calendar names; never carry this mapping into another year.
CALENDARS = {
    2026: {
        "ATP250": (
            "brisbane", "hong kong", "adelaide", "auckland", "montpellier",
            "buenos aires", "delray beach", "santiago", "bucharest", "houston",
            "marrakech", "geneva", "stuttgart", "s hertogenbosch", "den bosch",
            "libema", "mallorca", "eastbourne", "bastad", "gstaad", "umag",
            "kitzbuhel", "estoril", "los cabos", "winston salem", "chengdu",
            "hangzhou", "almaty", "brussels", "lyon", "stockholm",
        ),
        "ATP500": (
            "dallas", "rotterdam", "doha", "rio de janeiro", "acapulco",
            "dubai", "barcelona", "munich", "hamburg", "halle", "queen s",
            "queens", "hsbc championships", "washington", "tokyo", "beijing",
            "basel", "vienna",
        ),
        "Masters 1000": (
            "indian wells", "miami", "monte carlo", "madrid", "rome",
            "montreal", "cincinnati", "shanghai", "paris",
        ),
    }
}


def normalized(value):
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def contains(name, token):
    return f" {token} " in f" {name} "


def resolve_category(name, edition_date, rank=None, round_id=None):
    """Return official category separately from the supported parameter bucket.

    An explicit Challenger label wins over a same-city main-tour calendar entry.
    Generic rank codes and numbers in sponsor names never identify an ATP tier.
    OnCourt qualifying rounds are 0..3; ATP Slam main rounds start at 4.
    """
    name = normalized(name)
    try:
        year = int(str(edition_date)[:4])
    except (TypeError, ValueError):
        year = None
    try:
        round_number = int(round_id)
    except (TypeError, ValueError):
        round_number = None
    result = {
        "official_category": "Unknown", "model_bucket": None,
        "category_policy_version": POLICY_VERSION, "season": year,
        "category_source": None, "category_reason": "edition_not_verified",
        "candidate_eligible": False, "best_of": None, "event_key": None,
    }
    category, source = None, "explicit_tournament_name"
    if any(contains(name, t) for t in ("davis cup", "laver cup", "united cup", "atp cup", "olympics", "olympic games")):
        category = "Team / non-tour event"
    elif "next gen" in name or "nextgen" in name:
        category = "Next Gen Finals"
    elif "challenger" in name:
        category = "Challenger"
    elif "futures" in name or "itf" in name or re.search(r"\b[wm]\d{1,3}\b", name):
        category = "ITF"
    elif any(contains(name, t) for t in ("australian open", "roland garros", "french open", "wimbledon", "us open", "u s open")):
        category = "Grand Slam"
    elif any(contains(name, t) for t in ("masters cup", "atp finals", "tour finals")):
        category = "Masters Cup"
    elif year == 2025 and contains(name, "estoril"):
        category, source = "Challenger", CALENDAR_CHANGE
    elif year in CALENDARS:
        matches = {tier for tier, aliases in CALENDARS[year].items()
                   if any(contains(name, alias) for alias in aliases)}
        if len(matches) == 1:
            category, source = matches.pop(), CALENDAR_2026
            result["event_key"] = max((alias for alias in CALENDARS[year][category]
                                       if contains(name, alias)), key=len)
        elif len(matches) > 1:
            result["category_reason"] = "ambiguous_calendar_name"
    if category is None:
        return result
    result.update(official_category=category, category_source=source,
                  category_reason="verified_category")
    if category not in {"ATP250", "ATP500", "Masters 1000", "Grand Slam", "Masters Cup", "Challenger"}:
        result["category_reason"] = "unsupported_competition_format"
        return result
    if category == "Grand Slam":
        if round_number is None or round_number < 0:
            result["category_reason"] = "slam_round_unverified"
            return result
        result["best_of"] = 5 if round_number >= 4 else 3
        if "qualif" in name and round_number >= 4:
            result["category_reason"] = "conflicting_slam_round_identity"
            return result
    else:
        result["best_of"] = 3
    result.update(model_bucket="ATP250" if category == "Challenger" else category,
                  candidate_eligible=year is not None)
    if year is None:
        result["category_reason"] = "missing_edition_year"
    return result
