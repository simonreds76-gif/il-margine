#!/usr/bin/env python3
"""Build a fail-closed, one-off UK bookmaker margin snapshot.

The index compares complete outcome sets captured in the same source snapshot.
It reports both conventional raw overround and normalized hold; lower is
better. Incomplete or mismatched line sets are never published.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import requests


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "bookmakers" / "margin-index.json"
BASE_URL = "https://api.odds-api.io/v3"
# Exact Odds-API catalogue names for UK-facing sportsbooks. Regional variants
# are deliberately explicit so, for example, Unibet cannot resolve to a
# non-UK feed and Bwin DE cannot be presented as a UK measurement.
TARGET_BOOKMAKERS = {
    "10BET": ("10BET",),
    "888sport": ("888Sport",),
    "Bally Bet": ("Bally Bet",),
    "Bet365": ("Bet365", "Bet365 (no latency)"),
    "Betano": ("Betano UK",),
    "Betfair Sportsbook": ("Betfair Sportsbook",),
    "BetMGM": ("BetMGM",),
    "BetUK": ("BetUK",),
    "BetVictor": ("BetVictor",),
    "Betway": ("Betway",),
    "Coral": ("Coral",),
    "Ladbrokes": ("Ladbrokes",),
    "LeoVegas": ("LeoVegas",),
    "Lottoland": ("Lottoland",),
    "Mr Green": ("MrGreen",),
    "NetBet": ("NetBet",),
    "Paddy Power": ("Paddy Power",),
    "Parimatch": ("Parimatch UK",),
    "QuinnBet": ("QuinnBet",),
    "Unibet": ("Unibet UK",),
    "William Hill": ("William Hill",),
}
ODDSCHECKER_TARGET_BOOKMAKERS = (
    "10BET",
    "AK Bets",
    "Bet365",
    "BetAhoy",
    "Betfred",
    "BetGoodwin",
    "BetMGM",
    "BetTom",
    "BetVictor",
    "Betway",
    "BoyleSports",
    "Coral",
    "IvyBet",
    "Ladbrokes",
    "Paddy Power",
    "PricedUp",
    "QuinnBet",
    "Sky Bet",
    "Spreadex",
    "Star Sports",
    "Unibet",
    "Virgin Bet",
    "William Hill",
)
# Exchange and spread-betting prices are not comparable with fixed-odds
# sportsbook overround. They remain in the raw browser export only.
ODDSCHECKER_EXCLUDED_CODES = {"BF", "MA", "SI"}
BOOKMAKER_DISPLAY_ALIASES = {
    **TARGET_BOOKMAKERS,
    "10BET": ("10bet",),
    "Bet365": ("Bet365", "Bet365 (no latency)"),
    "BetMGM": ("BetMGM", "BetMGM UK"),
    "BoyleSports": ("BOYLE Sports", "Boylesports"),
    "Sky Bet": ("Skybet",),
}
ODDSCHECKER_MARKETS = {
    "football": {
        "Win Market": "ML",
        "Draw No Bet": "Draw No Bet",
        "Total Goals Over/Under": "Goals Over/Under",
        "Both Teams To Score": "Both Teams To Score",
        "Total Corners": "Corners Totals",
    },
    "tennis": {
        "Win Market": "ML",
        "Handicaps": "Spread (Games)",
    },
}
SPORT_CONFIG = {
    "football": {
        "display": "Football",
        "league_tokens": (
            "premierleague",
            "laliga",
            "seriea",
            "bundesliga",
            "ligue1",
            "championship",
        ),
        "markets": (
            "ML",
            "Draw No Bet",
            "Spread",
            "Totals",
            "Goals Over/Under",
            "Both Teams To Score",
            "Player Props",
            "Corners Totals",
            "Bookings Totals",
            "Total Shots Home",
            "Total Shots Away",
            "Goalkeeper Saves Home",
            "Goalkeeper Saves Away",
        ),
    },
    "tennis": {
        "display": "Tennis",
        "league_tokens": ("atp", "wta", "usopen", "australianopen", "frenchopen", "wimbledon"),
        "markets": (
            "ML",
            "Spread",
            "Spread (Games)",
            "Totals",
            "Totals (Games)",
            "Totals (Aces)",
            "Totals (Double Faults)",
            "Team Total (Aces) Home",
            "Team Total (Aces) Away",
            "Team Total (Double Faults) Home",
            "Team Total (Double Faults) Away",
        ),
    },
}
FAMILY_ORDER = (
    "Match Winner",
    "Handicap",
    "Game Handicap",
    "Over/Under",
    "Game Total",
    "Aces Total",
    "Double Fault Total",
    "Player Aces",
    "Player Double Faults",
    "Corners",
    "Cards",
    "Team Shots",
    "Goalkeeper Saves",
    "Player Props",
    "BTTS",
    "Draw No Bet",
)
MIN_OPERATOR_SAMPLES = 6
MIN_OPERATOR_FAMILIES = 3
MIN_PUBLISH_OPERATORS = 4
MIN_PUBLISH_FAMILIES = 3
MIN_PUBLISH_OBSERVATIONS = 20
MIN_SEGMENT_SAMPLES = 2
MIN_SEGMENT_OPERATORS = 3
MIN_LIMITED_SEGMENT_OPERATORS = 2
OUTCOME_ALIASES = {
    "home": {"home", "1"},
    "away": {"away", "2"},
    "draw": {"draw", "x"},
    "over": {"over", "o"},
    "under": {"under", "u"},
    "yes": {"yes"},
    "no": {"no"},
}


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def display_bookmaker(value: Any) -> str:
    normalized = norm(value)
    for display, aliases in BOOKMAKER_DISPLAY_ALIASES.items():
        if normalized in {norm(alias) for alias in aliases}:
            return display
    return str(value or "Unknown")


def fractional_to_decimal(value: Any) -> float | None:
    text = str(value or "").strip().lower()
    if text in {"evens", "even", "evs"}:
        return 2.0
    match = re.fullmatch(r"(\d+)\s*/\s*(\d+)", text)
    if not match or int(match.group(2)) == 0:
        return None
    return 1.0 + (int(match.group(1)) / int(match.group(2)))


def split_handicap_label(label: str) -> tuple[str, float | None]:
    match = re.fullmatch(r"(.+?)\s+([+-]\d+(?:\.\d+)?)", label.strip())
    if not match:
        return label.strip(), None
    return match.group(1).strip(), abs(float(match.group(2)))


def market_family(name: str, sport: str = "football") -> str | None:
    text = str(name or "").strip().lower()
    compact = norm(text)
    if sport == "tennis":
        if compact in {"ml", "moneyline", "matchwinner"}:
            return "Match Winner"
        if compact in {"spread", "spreadgames"}:
            return "Game Handicap"
        if compact in {"totals", "total", "totalsgames"}:
            return "Game Total"
        if compact == "totalsaces":
            return "Aces Total"
        if compact == "totalsdoublefaults":
            return "Double Fault Total"
        if compact in {"teamtotalaceshome", "teamtotalacesaway"}:
            return "Player Aces"
        if compact in {"teamtotaldoublefaultshome", "teamtotaldoublefaultsaway"}:
            return "Player Double Faults"
        return None
    if compact == "playerprops":
        return "Player Props"
    if compact in {"cornerstotals", "corners", "totalcorners"}:
        return "Corners"
    if compact in {"bookingstotals", "numberofcardsinmatch"}:
        return "Cards"
    if compact in {"totalshotshome", "totalshotsaway"}:
        return "Team Shots"
    if compact in {"goalkeepersaveshome", "goalkeepersavesaway"}:
        return "Goalkeeper Saves"
    if any(token in text for token in ("player", "corner", "card", "booking", "shot", "foul", "offside")):
        return None
    if "draw no bet" in text or "drawnobet" in compact or compact == "dnb":
        return "Draw No Bet"
    if "both teams to score" in text or "btts" in compact:
        return "BTTS"
    if compact in {"spread", "handicap", "asianhandicap"}:
        return "Handicap"
    if compact in {"totals", "total", "overunder", "goalsoverunder", "totalgoals", "matchtotal"}:
        return "Over/Under"
    if compact in {"ml", "moneyline", "matchwinner", "fulltimeresult", "3wayresult", "1x2"}:
        return "Match Winner"
    return None


def required_outcomes(family: str, sport: str = "football") -> tuple[str, ...]:
    if family == "Match Winner":
        return ("home", "away") if sport == "tennis" else ("home", "draw", "away")
    return {
        "Handicap": ("home", "away"),
        "Game Handicap": ("home", "away"),
        "Over/Under": ("over", "under"),
        "Game Total": ("over", "under"),
        "Aces Total": ("over", "under"),
        "Double Fault Total": ("over", "under"),
        "Player Aces": ("over", "under"),
        "Player Double Faults": ("over", "under"),
        "Corners": ("over", "under"),
        "Cards": ("over", "under"),
        "Team Shots": ("over", "under"),
        "Goalkeeper Saves": ("over", "under"),
        "Player Props": ("over", "under"),
        "BTTS": ("yes", "no"),
        "Draw No Bet": ("home", "away"),
    }[family]


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 1.0 else None


def line_value(item: dict[str, Any], label: str = "", family: str = "") -> str | None:
    if family in {"Match Winner", "BTTS", "Draw No Bet"}:
        return "main"
    for key in ("hdp", "line", "point", "handicap"):
        value = item.get(key)
        if value not in (None, ""):
            try:
                return f"{float(value):g}"
            except (TypeError, ValueError):
                return str(value).strip()
    match = re.search(r"(?<!\d)([+-]?\d+(?:\.\d+)?)", label)
    return f"{float(match.group(1)):g}" if match else None


def canonical_label(label: str, home: str, away: str) -> str | None:
    compact = norm(label)
    if compact == norm(home):
        return "home"
    if compact == norm(away):
        return "away"
    for outcome, aliases in OUTCOME_ALIASES.items():
        if compact in aliases or any(compact.startswith(alias) for alias in aliases if len(alias) > 1):
            return outcome
    return None


def prop_identity(item: dict[str, Any], label: str) -> str | None:
    """Return a stable player/stat identity without side or line text."""
    text = " ".join(
        str(item.get(key) or "")
        for key in ("player", "participant", "stat", "market", "description")
    ).strip()
    text = f"{text} {label}".strip()
    text = re.sub(r"\b(over|under|yes|no)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)[+-]?\d+(?:\.\d+)?(?!\w)", " ", text)
    identity = norm(text)
    return identity or None


def quote_sets(
    market: dict[str, Any],
    family: str,
    home: str,
    away: str,
    sport: str = "football",
) -> list[dict[str, Any]]:
    required = required_outcomes(family, sport)
    buckets: dict[str, dict[str, float]] = defaultdict(dict)
    containers = [market, *(market.get("odds") or [])]
    for item in containers:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("name") or item.get("selection") or "")
        line = line_value(item, label, family)
        if line is None:
            continue
        bucket_key = line
        if family == "Player Props":
            identity = prop_identity(item, label)
            if identity is None:
                continue
            bucket_key = f"{identity}|{line}"
        compound: dict[str, float] = {}
        for outcome in required:
            aliases = OUTCOME_ALIASES[outcome] | {outcome}
            for key, value in item.items():
                if norm(key) in aliases:
                    parsed = number(value)
                    if parsed is not None:
                        compound[outcome] = parsed
                        break
        if family == "Player Props":
            over = number(item.get("over")) or number(item.get("home"))
            under = number(item.get("under")) or number(item.get("away"))
            if over is not None:
                compound["over"] = over
            if under is not None:
                compound["under"] = under
        if set(required).issubset(compound):
            buckets[bucket_key].update(compound)
            continue

        outcome = canonical_label(label, home, away)
        if family == "Player Props":
            lower_label = label.lower()
            outcome = "over" if "over" in lower_label else "under" if "under" in lower_label else None
        if outcome not in required:
            continue
        price = next((number(item.get(key)) for key in ("odds", "price", "value", "decimal", "back") if number(item.get(key)) is not None), None)
        selection_line = line_value(item, label, family)
        if price is not None and selection_line is not None:
            selection_key = selection_line
            if family == "Player Props":
                identity = prop_identity(item, label)
                if identity is None:
                    continue
                selection_key = f"{identity}|{selection_line}"
            buckets[selection_key][outcome] = price

    output: list[dict[str, Any]] = []
    for line, outcomes in buckets.items():
        if not set(required).issubset(outcomes):
            continue
        ordered = {key: outcomes[key] for key in required}
        implied = sum(1.0 / value for value in ordered.values())
        if not 0.98 <= implied <= 1.35:
            continue
        output.append(
            {
                "line": line,
                "outcomes": ordered,
                "raw_overround_pct": (implied - 1.0) * 100.0,
                "normalized_hold_pct": (1.0 - (1.0 / implied)) * 100.0,
            }
        )
    return output


def median(values: Iterable[float]) -> float:
    data = list(values)
    return float(statistics.median(data)) if data else 0.0


def safe_error_summary(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is not None:
        return f"{type(exc).__name__}: HTTP {status}"
    return type(exc).__name__


def build_index(payload: list[dict[str, Any]], captured_at: str) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []

    for event in payload:
        if str(event.get("status") or "pending").lower() not in {"pending", "scheduled", "upcoming", ""}:
            continue
        event_id = str(event.get("id") or "")
        home, away = str(event.get("home") or ""), str(event.get("away") or "")
        if not event_id or not home or not away:
            continue
        sport_slug = norm(event.get("_snapshot_sport") or event.get("sport") or "football")
        sport_slug = sport_slug if sport_slug in SPORT_CONFIG else "football"
        sport = str(SPORT_CONFIG[sport_slug]["display"])
        for bookmaker_raw, markets in (event.get("bookmakers") or {}).items():
            bookmaker = display_bookmaker(bookmaker_raw)
            for market in markets or []:
                family = market_family(str(market.get("name") or ""), sport_slug)
                if family is None:
                    continue
                for quote in quote_sets(market, family, home, away, sport_slug):
                    observations.append(
                        {
                            "sport": sport,
                            "sport_slug": sport_slug,
                            "event_id": event_id,
                            "family": family,
                            "line": quote["line"],
                            "bookmaker": bookmaker,
                            **quote,
                        }
                    )

    # One contribution per bookmaker/event/family prevents operators with many
    # alternate lines from receiving extra weight.
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        grouped[(row["bookmaker"], row["sport_slug"], row["event_id"], row["family"])].append(row)
    collapsed = [
        {
            "bookmaker": key[0],
            "sport_slug": key[1],
            "sport": str(SPORT_CONFIG[key[1]]["display"]),
            "event_id": key[2],
            "family": key[3],
            "raw_overround_pct": median(row["raw_overround_pct"] for row in rows),
            "normalized_hold_pct": median(row["normalized_hold_pct"] for row in rows),
            "line_count": len(rows),
        }
        for key, rows in grouped.items()
    ]

    universe = {(row["sport_slug"], row["event_id"], row["family"]) for row in collapsed}
    by_book: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in collapsed:
        by_book[row["bookmaker"]].append(row)
    diagnostic_operators = []
    for bookmaker, rows in by_book.items():
        families = sorted({row["family"] for row in rows}, key=lambda value: FAMILY_ORDER.index(value))
        covered = {(row["sport_slug"], row["event_id"], row["family"]) for row in rows}
        diagnostic_operators.append(
            {
                "name": bookmaker,
                "raw_overround_pct": round(sum(row["raw_overround_pct"] for row in rows) / len(rows), 2),
                "normalized_hold_pct": round(sum(row["normalized_hold_pct"] for row in rows) / len(rows), 2),
                "samples": len(rows),
                "market_families": families,
                "coverage_pct": round((len(covered) / len(universe) * 100.0) if universe else 0.0, 1),
            }
        )
    diagnostic_operators.sort(key=lambda row: (row["normalized_hold_pct"], -row["samples"], row["name"]))
    operators = [
        row
        for row in diagnostic_operators
        if row["samples"] >= MIN_OPERATOR_SAMPLES
        and len(row["market_families"]) >= MIN_OPERATOR_FAMILIES
    ]
    for rank, operator in enumerate(operators, 1):
        operator["rank"] = rank

    segments = []
    segment_keys = sorted(
        {(row["sport_slug"], row["family"]) for row in collapsed},
        key=lambda key: (list(SPORT_CONFIG).index(key[0]), FAMILY_ORDER.index(key[1])),
    )
    for sport_slug, family in segment_keys:
        segment_rows = [
            row for row in collapsed
            if row["sport_slug"] == sport_slug and row["family"] == family
        ]
        segment_by_book: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in segment_rows:
            segment_by_book[row["bookmaker"]].append(row)
        segment_operators = [
            {
                "name": bookmaker,
                "raw_overround_pct": round(sum(row["raw_overround_pct"] for row in rows) / len(rows), 2),
                "normalized_hold_pct": round(sum(row["normalized_hold_pct"] for row in rows) / len(rows), 2),
                "samples": len(rows),
            }
            for bookmaker, rows in segment_by_book.items()
            if len(rows) >= MIN_SEGMENT_SAMPLES
        ]
        segment_operators.sort(key=lambda row: (row["normalized_hold_pct"], -row["samples"], row["name"]))
        for rank, operator in enumerate(segment_operators, 1):
            operator["rank"] = rank
        segment_status = (
            "PASS"
            if len(segment_operators) >= MIN_SEGMENT_OPERATORS
            else "PASS_LIMITED"
            if len(segment_operators) >= MIN_LIMITED_SEGMENT_OPERATORS
            else "THIN_SAMPLE"
        )
        segments.append(
            {
                "sport": str(SPORT_CONFIG[sport_slug]["display"]),
                "sport_slug": sport_slug,
                "market_family": family,
                "events": len({row["event_id"] for row in segment_rows}),
                "observations": len(segment_rows),
                "status": segment_status,
                "operators": segment_operators,
            }
        )

    families = sorted({row["family"] for row in collapsed}, key=lambda value: FAMILY_ORDER.index(value))
    sports = [
        str(SPORT_CONFIG[slug]["display"])
        for slug in SPORT_CONFIG
        if any(row["sport_slug"] == slug for row in collapsed)
    ]
    global_gate = (
        len(operators) >= MIN_PUBLISH_OPERATORS
        and len(families) >= MIN_PUBLISH_FAMILIES
        and len(collapsed) >= MIN_PUBLISH_OBSERVATIONS
    )
    passing_segments = [segment for segment in segments if segment["status"] == "PASS"]
    segment_sports = {segment["sport"] for segment in passing_segments}
    segment_gate = (
        {"Football", "Tennis"}.issubset(segment_sports)
        and len(passing_segments) >= 4
        and len(collapsed) >= MIN_PUBLISH_OBSERVATIONS
    )
    limited_segments = [
        segment for segment in segments
        if segment["status"] in {"PASS", "PASS_LIMITED"}
    ]
    limited_segment_sports = {segment["sport"] for segment in limited_segments}
    limited_segment_gate = (
        {"Football", "Tennis"}.issubset(limited_segment_sports)
        and len(limited_segments) >= 4
        and len(collapsed) >= MIN_PUBLISH_OBSERVATIONS
    )
    status = (
        "PASS"
        if global_gate or segment_gate
        else "PASS_LIMITED"
        if limited_segment_gate
        else "INSUFFICIENT_COVERAGE"
    )
    return {
        "schema_version": 3,
        "generated_at": captured_at,
        "capture_mode": "manual_one_off",
        "status": status,
        "methodology": {
            "raw_overround": "sum(1/decimal_odds)-1",
            "normalized_hold": "1-(1/sum(1/decimal_odds))",
            "aggregation": "median alternate lines per operator/event/family, then equal-weight mean",
            "scope": "one-off pre-match football and tennis snapshot; complete like-for-like outcome sets only",
            "minimum_publish_gate": (
                "Either a broad four-operator ranking, or at least four market-specific tables spanning "
                "football and tennis. Three operators produces a full table; two operators produces an "
                "explicitly labelled limited comparison. Every operator needs two observations per table"
            ),
        },
        "summary": {
            "operators": len(operators),
            "diagnostic_operators": len(diagnostic_operators),
            "sports": sports,
            "events": len({(row["sport_slug"], row["event_id"]) for row in collapsed}),
            "market_families": families,
            "observations": len(collapsed),
            "raw_quote_sets": len(observations),
        },
        "operators": operators if global_gate else [],
        "diagnostic_operators": diagnostic_operators,
        "segments": segments,
    }


def discover_bookmakers(api_key: str) -> list[str]:
    response = requests.get(
        f"{BASE_URL}/bookmakers",
        params={"apiKey": api_key},
        timeout=30,
    )
    response.raise_for_status()
    available = [str(row.get("name") or "") for row in response.json() if row.get("active", True)]
    selected: list[str] = []
    for display, aliases in TARGET_BOOKMAKERS.items():
        normalized_aliases = {norm(alias) for alias in aliases}
        match = next((name for name in available if norm(name) in normalized_aliases), None)
        if match and match not in selected:
            selected.append(match)
    return selected


def select_target_bookmakers(api_key: str, bookmakers: list[str]) -> None:
    if not bookmakers:
        raise RuntimeError("No target UK bookmakers are available to select")
    response = requests.put(
        f"{BASE_URL}/bookmakers/selected/select",
        params={
            "apiKey": api_key,
            "bookmakers": ",".join(bookmakers),
        },
        timeout=30,
    )
    response.raise_for_status()


def selected_bookmaker_names(body: Any) -> list[str]:
    """Normalize the provider's selected-bookmakers response variants."""
    if isinstance(body, list):
        values = body
    elif isinstance(body, dict):
        values = next(
            (
                body[key]
                for key in ("bookmakers", "selectedBookmakers", "selected", "data")
                if key in body
            ),
            [],
        )
        if not values:
            values = [key for key, value in body.items() if value is True]
    else:
        values = []

    if isinstance(values, dict):
        values = [key for key, value in values.items() if value]
    if not isinstance(values, list):
        return []

    names: list[str] = []
    for value in values:
        name = value.get("name") if isinstance(value, dict) else value
        text = str(name or "").strip()
        if text and text not in names:
            names.append(text)
    return names


def get_selected_bookmakers(api_key: str) -> list[str]:
    response = requests.get(
        f"{BASE_URL}/bookmakers/selected",
        params={"apiKey": api_key},
        timeout=30,
    )
    response.raise_for_status()
    return selected_bookmaker_names(response.json())


def reset_target_bookmakers(api_key: str, bookmakers: list[str]) -> list[str]:
    """Replace the account selection once, restoring the original set on failure."""
    if not bookmakers:
        raise RuntimeError("No target UK bookmakers are available to select")
    original = get_selected_bookmakers(api_key)
    if not original:
        raise RuntimeError("Refusing to clear: the current bookmaker selection could not be verified")

    cleared = requests.put(
        f"{BASE_URL}/bookmakers/selected/clear",
        params={"apiKey": api_key},
        timeout=30,
    )
    cleared.raise_for_status()

    try:
        select_target_bookmakers(api_key, bookmakers)
    except requests.RequestException as selection_error:
        try:
            select_target_bookmakers(api_key, original)
        except requests.RequestException as restore_error:
            raise RuntimeError(
                "Target selection failed and the original bookmaker selection could not be restored"
            ) from restore_error
        raise RuntimeError(
            "Target selection failed; the original bookmaker selection was restored"
        ) from selection_error

    selected = get_selected_bookmakers(api_key)
    selected_norm = {norm(name) for name in selected}
    missing = [name for name in bookmakers if norm(name) not in selected_norm]
    if missing:
        # All original books are part of the target catalogue, but explicitly
        # add them back if the provider accepted only a partial replacement.
        original_missing = [name for name in original if norm(name) not in selected_norm]
        if original_missing:
            select_target_bookmakers(api_key, original_missing)
        raise RuntimeError(
            f"Provider accepted only {len(selected)}/{len(bookmakers)} target bookmakers"
        )
    return original


def payload_bookmakers(body: Any) -> set[str]:
    names: set[str] = set()
    if not isinstance(body, list):
        return names
    for event in body:
        if isinstance(event, dict):
            names.update(str(name) for name in (event.get("bookmakers") or {}))
    return names


def operator_payload_counts(body: Any, bookmaker: str) -> tuple[int, int]:
    events = 0
    markets = 0
    target = norm(bookmaker)
    if not isinstance(body, list):
        return events, markets
    for event in body:
        if not isinstance(event, dict):
            continue
        for name, rows in (event.get("bookmakers") or {}).items():
            if norm(name) != target:
                continue
            events += 1
            markets += len(rows or [])
    return events, markets


def append_sport_payload(payload: list[dict[str, Any]], body: Any, sport: str) -> None:
    if not isinstance(body, list):
        return
    for event in body:
        if isinstance(event, dict):
            event["_snapshot_sport"] = sport
            payload.append(event)


def load_oddschecker_capture(
    path: str | Path,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """Convert a browser-exported Oddschecker grid into the common payload."""
    source = json.loads(Path(path).read_text(encoding="utf-8"))
    pages = source.get("pages") if isinstance(source, dict) else None
    if not isinstance(pages, list):
        raise RuntimeError("Oddschecker capture must contain a pages array")

    payload: list[dict[str, Any]] = []
    observed: set[str] = set()
    sport_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for page_index, page in enumerate(pages, 1):
        if not isinstance(page, dict):
            continue
        sport = str(page.get("sport") or "").lower()
        if sport not in ODDSCHECKER_MARKETS:
            continue
        home = str(page.get("home") or "").strip()
        away = str(page.get("away") or "").strip()
        event_name = str(page.get("event") or f"{home} vs {away}").strip()
        if not home or not away:
            continue

        event: dict[str, Any] = {
            "id": f"oddschecker:{sport}:{page_index}:{norm(event_name)}",
            "status": "pending",
            "home": home,
            "away": away,
            "_snapshot_sport": sport,
            "bookmakers": {},
        }
        for grid in page.get("grids") or []:
            if not isinstance(grid, dict):
                continue
            source_market = str(grid.get("market") or "").strip()
            market_name = ODDSCHECKER_MARKETS[sport].get(source_market)
            if not market_name:
                continue

            by_book: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for selection in grid.get("selections") or []:
                if not isinstance(selection, dict):
                    continue
                label = str(selection.get("label") or "").strip()
                if not label:
                    continue
                clean_label, handicap = (
                    split_handicap_label(label)
                    if sport == "tennis" and source_market == "Handicaps"
                    else (label, None)
                )
                for price in selection.get("prices") or []:
                    if not isinstance(price, dict):
                        continue
                    code = str(price.get("code") or "").strip().upper()
                    if code in ODDSCHECKER_EXCLUDED_CODES:
                        continue
                    bookmaker = display_bookmaker(price.get("bookmaker") or code)
                    decimal = fractional_to_decimal(price.get("fractional"))
                    if decimal is None:
                        continue
                    item: dict[str, Any] = {"label": clean_label, "odds": decimal}
                    if handicap is not None:
                        item["hdp"] = handicap
                    by_book[bookmaker].append(item)
                    observed.add(bookmaker)

            for bookmaker, selections in by_book.items():
                event["bookmakers"].setdefault(bookmaker, []).append(
                    {"name": market_name, "odds": selections}
                )
                sport_counts[sport][bookmaker] += 1
        if event["bookmakers"]:
            payload.append(event)

    ordered_observed = sorted(observed, key=str.lower)
    capture = {
        "source": "oddschecker_public_browser_grid",
        "source_capture_mode": source.get("capture_mode", "manual_browser_one_off"),
        "source_captured_at": source.get("captured_at"),
        "source_pages": len(pages),
        "target_operators": list(ODDSCHECKER_TARGET_BOOKMAKERS),
        "discovered_operators": ordered_observed,
        "not_discovered": [
            name for name in ODDSCHECKER_TARGET_BOOKMAKERS if name not in observed
        ],
        "sports": [
            {
                "sport": sport,
                "events_selected": sum(
                    1 for event in payload if event.get("_snapshot_sport") == sport
                ),
                "operators": [
                    {"name": bookmaker, "market_blocks": count, "status": "returned"}
                    for bookmaker, count in sorted(sport_counts[sport].items())
                ],
            }
            for sport in ODDSCHECKER_MARKETS
        ],
    }
    return payload, ordered_observed, capture


def fetch_payload(
    api_key: str,
    days_ahead: int,
    max_events: int,
    max_requests: int,
    sports: tuple[str, ...] = ("football", "tennis"),
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    now = datetime.now(timezone.utc)
    bookmakers = discover_bookmakers(api_key)
    if not bookmakers:
        raise RuntimeError("No target UK bookmakers were returned by /bookmakers")

    payload: list[dict[str, Any]] = []
    discovered_displays = {display_bookmaker(name) for name in bookmakers}
    capture: dict[str, Any] = {
        "target_operators": list(TARGET_BOOKMAKERS),
        "discovered_operators": [display_bookmaker(name) for name in bookmakers],
        "not_discovered": [name for name in TARGET_BOOKMAKERS if name not in discovered_displays],
        "sports": [],
    }
    for sport in sports:
        config = SPORT_CONFIG[sport]
        response = requests.get(
            f"{BASE_URL}/events",
            params={
                "apiKey": api_key,
                "sport": sport,
                "status": "pending",
                "from": now.isoformat().replace("+00:00", "Z"),
                "to": (now + timedelta(days=days_ahead)).isoformat().replace("+00:00", "Z"),
            },
            timeout=30,
        )
        response.raise_for_status()
        events = response.json() if isinstance(response.json(), list) else []
        selected_events = [
            event for event in events
            if any(
                token in norm((event.get("league") or {}).get("name") or (event.get("league") or {}).get("slug"))
                for token in config["league_tokens"]
            )
        ]
        selected_events.sort(key=lambda event: str(event.get("date") or ""))
        selected_events = selected_events[:max_events]
        chunks = [selected_events[index:index + 10] for index in range(0, len(selected_events), 10)][:max_requests]
        operator_results = {
            bookmaker: {
                "name": display_bookmaker(bookmaker),
                "provider_name": bookmaker,
                "status": "not_returned",
                "request_mode": None,
                "http_statuses": [],
                "events_returned": 0,
                "market_blocks": 0,
            }
            for bookmaker in bookmakers
        }
        sport_capture = {
            "sport": sport,
            "events_discovered": len(events),
            "events_selected": len(selected_events),
            "chunks": len(chunks),
            "combined_http_statuses": [],
            "operators": [],
        }
        for chunk in chunks:
            params = {
                "apiKey": api_key,
                "eventIds": ",".join(str(event["id"]) for event in chunk),
                "bookmakers": ",".join(bookmakers[:30]),
                "markets": ",".join(str(value) for value in config["markets"]),
            }
            odds = requests.get(
                f"{BASE_URL}/odds/multi",
                params=params,
                timeout=45,
            )
            sport_capture["combined_http_statuses"].append(odds.status_code)
            returned: set[str] = set()
            if odds.ok:
                body = odds.json()
                returned = payload_bookmakers(body)
                append_sport_payload(payload, body, sport)
                returned_norm = {norm(name) for name in returned}
                for bookmaker in bookmakers:
                    if norm(bookmaker) not in returned_norm:
                        continue
                    events_returned, market_blocks = operator_payload_counts(body, bookmaker)
                    result = operator_results[bookmaker]
                    result["status"] = "returned"
                    result["request_mode"] = "combined"
                    result["http_statuses"].append(odds.status_code)
                    result["events_returned"] += events_returned
                    result["market_blocks"] += market_blocks
            elif odds.status_code in {401, 429}:
                odds.raise_for_status()

            # A successful combined request can silently omit books that are
            # not selected on the account or have no payload. Probe every
            # missing book once so a two-book response cannot masquerade as a
            # complete UK comparison.
            returned_norm = {norm(name) for name in returned}
            missing = [bookmaker for bookmaker in bookmakers if norm(bookmaker) not in returned_norm]
            if missing:
                print(
                    f"Combined {sport} request returned {len(returned_norm)}/{len(bookmakers)} books; "
                    f"probing {len(missing)} missing books individually."
                )
            for bookmaker in missing:
                single = requests.get(
                    f"{BASE_URL}/odds/multi",
                    params={
                        "apiKey": api_key,
                        "eventIds": params["eventIds"],
                        "bookmakers": bookmaker,
                        "markets": params["markets"],
                    },
                    timeout=45,
                )
                result = operator_results[bookmaker]
                result["request_mode"] = "fallback"
                result["http_statuses"].append(single.status_code)
                if not single.ok:
                    result["status"] = f"http_{single.status_code}"
                    print(f"Skipping unavailable {sport} bookmaker {bookmaker}: HTTP {single.status_code}")
                    continue
                body = single.json()
                events_returned, market_blocks = operator_payload_counts(body, bookmaker)
                result["events_returned"] += events_returned
                result["market_blocks"] += market_blocks
                result["status"] = "returned" if events_returned else "empty"
                append_sport_payload(payload, body, sport)
        sport_capture["operators"] = [operator_results[name] for name in bookmakers]
        capture["sports"].append(sport_capture)
    return payload, bookmakers, capture


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input-json", help="Use a saved /odds/multi payload instead of calling the API.")
    source.add_argument(
        "--oddschecker-json",
        help="Use a manual browser export of public Oddschecker comparison grids.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--days-ahead", type=int, default=4)
    parser.add_argument("--max-events", type=int, default=10)
    parser.add_argument("--max-requests", type=int, default=1)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--select-target-bookmakers",
        action="store_true",
        help="Add the exact UK target catalogue to the authenticated Odds-API account before capture.",
    )
    selection.add_argument(
        "--reset-target-bookmakers",
        action="store_true",
        help="One-time replacement of the account selection, with rollback if the target selection fails.",
    )
    parser.add_argument(
        "--sports",
        default="football,tennis",
        help="Comma-separated sports. Supported: football,tennis.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if args.input_json:
        payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        bookmakers: list[str] = []
        capture: dict[str, Any] = {}
    elif args.oddschecker_json:
        try:
            payload, bookmakers, capture = load_oddschecker_capture(args.oddschecker_json)
            captured_at = str(capture.get("source_captured_at") or captured_at)
        except (OSError, json.JSONDecodeError, RuntimeError) as exc:
            raise SystemExit(f"Oddschecker capture failed: {exc}") from exc
    else:
        load_env()
        api_key = (os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY") or "").strip()
        if not api_key:
            raise SystemExit(
                "Set ODDS_API_KEY or ODDS_API_IO_KEY, pass --input-json, "
                "or pass --oddschecker-json"
            )
        try:
            sports = tuple(value.strip().lower() for value in args.sports.split(",") if value.strip())
            invalid = sorted(set(sports) - set(SPORT_CONFIG))
            if invalid:
                raise SystemExit(f"Unsupported sport(s): {','.join(invalid)}")
            if args.select_target_bookmakers or args.reset_target_bookmakers:
                selectable = discover_bookmakers(api_key)
                if args.reset_target_bookmakers:
                    reset_target_bookmakers(api_key, selectable)
                    print(f"Reset the Odds-API account to {len(selectable)} UK target sportsbooks.")
                else:
                    select_target_bookmakers(api_key, selectable)
                    print(f"Selected {len(selectable)} UK target sportsbooks on the Odds-API account.")
            payload, bookmakers, capture = fetch_payload(
                api_key,
                args.days_ahead,
                args.max_events,
                args.max_requests,
                sports,
            )
        except (requests.RequestException, RuntimeError) as exc:
            payload, bookmakers = [], []
            capture = {}
            result = build_index([], captured_at)
            result["status"] = "CAPTURE_FAILED"
            result["error"] = safe_error_summary(exc)
        else:
            result = build_index(payload if isinstance(payload, list) else [], captured_at)
    if args.input_json:
        result = build_index(payload if isinstance(payload, list) else [], captured_at)
    elif args.oddschecker_json:
        result = build_index(payload if isinstance(payload, list) else [], captured_at)
        result["capture_mode"] = "manual_oddschecker_browser_one_off"
        result["methodology"]["scope"] = (
            "one-off public Oddschecker UK pre-match football and tennis snapshot; "
            "complete like-for-like sportsbook outcome sets only; exchanges excluded"
        )
    result["requested_bookmakers"] = bookmakers
    result["capture"] = capture
    payload_operators = sorted(
        {display_bookmaker(name) for name in payload_bookmakers(payload)},
        key=str.lower,
    )
    qualified_operators = sorted(
        {row["name"] for row in result.get("diagnostic_operators", [])},
        key=str.lower,
    )
    target_operator_names = (
        list(ODDSCHECKER_TARGET_BOOKMAKERS)
        if args.oddschecker_json
        else list(TARGET_BOOKMAKERS)
    )
    result["coverage"] = {
        "target_operators": len(target_operator_names),
        "discovered_operators": len(bookmakers),
        "payload_operators": len(payload_operators),
        "qualified_operators": len(qualified_operators),
        "payload_operator_names": payload_operators,
        "qualified_operator_names": qualified_operators,
        "not_discovered": capture.get("not_discovered", []) if capture else [],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(
        f"Bookmaker margin index: {result['status']} | operators={result['summary']['operators']} "
        f"families={len(result['summary']['market_families'])} observations={result['summary']['observations']}"
    )
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
