#!/usr/bin/env python3
"""Build a fail-closed UK bookmaker margin index from pre-match odds.

The index compares complete outcome sets captured in the same API response.
It reports both conventional raw overround and normalized hold; lower is
better. A separate synthetic best-price market shows the combined price a
line shopper could build across operators.
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
TARGET_BOOKMAKERS = {
    "10bet": ("10bet", "tenbet"),
    "Bally Bet": ("ballybet",),
    "Bet365": ("bet365",),
    "Betfred": ("betfred",),
    "BetVictor": ("betvictor",),
    "William Hill": ("williamhill",),
    "Unibet": ("unibet",),
    "Betway": ("betway",),
    "BetMGM": ("betmgm",),
    "Paddy Power": ("paddypower",),
    "Sky Bet": ("skybet",),
    "Coral": ("coral",),
    "Ladbrokes": ("ladbrokes",),
    "BoyleSports": ("boylesports", "boylesport"),
    "SBK": ("sbk", "smarketsbookmaker"),
    "Spreadex": ("spreadex",),
    "Virgin Bet": ("virginbet",),
    "Midnite": ("midnite",),
    "Bwin": ("bwin",),
}
LEAGUE_TOKENS = (
    "premierleague",
    "laliga",
    "seriea",
    "bundesliga",
    "ligue1",
    "championship",
)
FAMILY_ORDER = ("Moneyline", "Handicap", "Over/Under", "BTTS", "Draw No Bet")
MIN_OPERATOR_SAMPLES = 6
MIN_OPERATOR_FAMILIES = 3
MIN_PUBLISH_OPERATORS = 4
MIN_PUBLISH_FAMILIES = 3
MIN_PUBLISH_OBSERVATIONS = 20
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
    for display, aliases in TARGET_BOOKMAKERS.items():
        if normalized in aliases or any(alias in normalized for alias in aliases):
            return display
    return str(value or "Unknown")


def market_family(name: str) -> str | None:
    text = str(name or "").strip().lower()
    compact = norm(text)
    if any(token in text for token in ("player", "corner", "card", "booking", "shot", "foul", "offside")):
        return None
    if "draw no bet" in text or "drawnobet" in compact or compact == "dnb":
        return "Draw No Bet"
    if "both teams to score" in text or "btts" in compact:
        return "BTTS"
    if any(token in text for token in ("handicap", "spread")):
        return "Handicap"
    if any(token in text for token in ("over/under", "total goals", "match total")) or compact in {"totals", "total"}:
        return "Over/Under"
    if compact == "ml" or any(token in text for token in ("moneyline", "match winner", "full time result", "fulltime result", "1x2")):
        return "Moneyline"
    return None


def required_outcomes(family: str) -> tuple[str, ...]:
    return {
        "Moneyline": ("home", "draw", "away"),
        "Handicap": ("home", "away"),
        "Over/Under": ("over", "under"),
        "BTTS": ("yes", "no"),
        "Draw No Bet": ("home", "away"),
    }[family]


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 1.0 else None


def line_value(item: dict[str, Any], label: str = "", family: str = "") -> str:
    if family in {"Moneyline", "BTTS", "Draw No Bet"}:
        return "main"
    for key in ("hdp", "line", "point", "handicap"):
        value = item.get(key)
        if value not in (None, ""):
            try:
                return f"{float(value):g}"
            except (TypeError, ValueError):
                return str(value).strip()
    match = re.search(r"(?<!\d)([+-]?\d+(?:\.\d+)?)", label)
    return f"{float(match.group(1)):g}" if match else "main"


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


def quote_sets(market: dict[str, Any], family: str, home: str, away: str) -> list[dict[str, Any]]:
    required = required_outcomes(family)
    buckets: dict[str, dict[str, float]] = defaultdict(dict)
    containers = [market, *(market.get("odds") or [])]
    for item in containers:
        if not isinstance(item, dict):
            continue
        line = line_value(item, family=family)
        compound: dict[str, float] = {}
        for outcome in required:
            aliases = OUTCOME_ALIASES[outcome] | {outcome}
            for key, value in item.items():
                if norm(key) in aliases:
                    parsed = number(value)
                    if parsed is not None:
                        compound[outcome] = parsed
                        break
        if set(required).issubset(compound):
            buckets[line].update(compound)
            continue

        label = str(item.get("label") or item.get("name") or item.get("selection") or "")
        outcome = canonical_label(label, home, away)
        if outcome not in required:
            continue
        price = next((number(item.get(key)) for key in ("odds", "price", "value", "decimal", "back") if number(item.get(key)) is not None), None)
        if price is not None:
            buckets[line_value(item, label, family)][outcome] = price

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
    synthetic: dict[tuple[str, str, str], dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))

    for event in payload:
        if str(event.get("status") or "pending").lower() not in {"pending", "scheduled", "upcoming", ""}:
            continue
        event_id = str(event.get("id") or "")
        home, away = str(event.get("home") or ""), str(event.get("away") or "")
        if not event_id or not home or not away:
            continue
        for bookmaker_raw, markets in (event.get("bookmakers") or {}).items():
            bookmaker = display_bookmaker(bookmaker_raw)
            for market in markets or []:
                family = market_family(str(market.get("name") or ""))
                if family is None:
                    continue
                for quote in quote_sets(market, family, home, away):
                    signature = (event_id, family, quote["line"])
                    observations.append(
                        {
                            "event_id": event_id,
                            "family": family,
                            "line": quote["line"],
                            "bookmaker": bookmaker,
                            **quote,
                        }
                    )
                    for outcome, price in quote["outcomes"].items():
                        current = synthetic[signature][outcome].get("price", 0.0)
                        if price > current:
                            synthetic[signature][outcome] = {"price": price, "bookmaker": bookmaker}

    # One contribution per bookmaker/event/family prevents operators with many
    # alternate lines from receiving extra weight.
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        grouped[(row["bookmaker"], row["event_id"], row["family"])].append(row)
    collapsed = [
        {
            "bookmaker": key[0],
            "event_id": key[1],
            "family": key[2],
            "raw_overround_pct": median(row["raw_overround_pct"] for row in rows),
            "normalized_hold_pct": median(row["normalized_hold_pct"] for row in rows),
            "line_count": len(rows),
        }
        for key, rows in grouped.items()
    ]

    universe = {(row["event_id"], row["family"]) for row in collapsed}
    by_book: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in collapsed:
        by_book[row["bookmaker"]].append(row)
    diagnostic_operators = []
    for bookmaker, rows in by_book.items():
        families = sorted({row["family"] for row in rows}, key=lambda value: FAMILY_ORDER.index(value))
        covered = {(row["event_id"], row["family"]) for row in rows}
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

    synthetic_rows = []
    for signature, outcomes in synthetic.items():
        required = required_outcomes(signature[1])
        if not set(required).issubset(outcomes):
            continue
        implied = sum(1.0 / outcomes[key]["price"] for key in required)
        if not 0.75 <= implied <= 1.25:
            continue
        synthetic_rows.append(
            {
                "raw_overround_pct": (implied - 1.0) * 100.0,
                "normalized_hold_pct": (1.0 - (1.0 / implied)) * 100.0,
            }
        )

    families = sorted({row["family"] for row in collapsed}, key=lambda value: FAMILY_ORDER.index(value))
    status = (
        "PASS"
        if len(operators) >= MIN_PUBLISH_OPERATORS
        and len(families) >= MIN_PUBLISH_FAMILIES
        and len(collapsed) >= MIN_PUBLISH_OBSERVATIONS
        else "INSUFFICIENT_COVERAGE"
    )
    return {
        "schema_version": 1,
        "generated_at": captured_at,
        "status": status,
        "methodology": {
            "raw_overround": "sum(1/decimal_odds)-1",
            "normalized_hold": "1-(1/sum(1/decimal_odds))",
            "aggregation": "median alternate lines per operator/event/family, then equal-weight mean",
            "scope": "pre-match football; complete like-for-like outcome sets only",
            "minimum_publish_gate": (
                "4 qualified operators, 3 market families, 20 operator/event/family observations; "
                "each ranked operator needs 6 observations across 3 families"
            ),
        },
        "summary": {
            "operators": len(operators),
            "diagnostic_operators": len(diagnostic_operators),
            "events": len({row["event_id"] for row in collapsed}),
            "market_families": families,
            "observations": len(collapsed),
            "raw_quote_sets": len(observations),
        },
        "synthetic_best_price": {
            "raw_overround_pct": round(sum(row["raw_overround_pct"] for row in synthetic_rows) / len(synthetic_rows), 2) if synthetic_rows else None,
            "normalized_hold_pct": round(sum(row["normalized_hold_pct"] for row in synthetic_rows) / len(synthetic_rows), 2) if synthetic_rows else None,
            "samples": len(synthetic_rows),
        },
        "operators": operators if status == "PASS" else [],
        "diagnostic_operators": diagnostic_operators,
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
        match = next((name for name in available if norm(name) in aliases or any(alias in norm(name) for alias in aliases)), None)
        if match and match not in selected:
            selected.append(match)
    return selected


def fetch_payload(api_key: str, days_ahead: int, max_events: int, max_requests: int) -> tuple[list[dict[str, Any]], list[str]]:
    now = datetime.now(timezone.utc)
    response = requests.get(
        f"{BASE_URL}/events",
        params={
            "apiKey": api_key,
            "sport": "football",
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
        if any(token in norm((event.get("league") or {}).get("name") or (event.get("league") or {}).get("slug")) for token in LEAGUE_TOKENS)
    ]
    selected_events.sort(key=lambda event: str(event.get("date") or ""))
    selected_events = selected_events[:max_events]
    bookmakers = discover_bookmakers(api_key)
    if not bookmakers:
        raise RuntimeError("No target UK bookmakers were returned by /bookmakers")

    payload: list[dict[str, Any]] = []
    chunks = [selected_events[index:index + 10] for index in range(0, len(selected_events), 10)][:max_requests]
    for chunk in chunks:
        odds = requests.get(
            f"{BASE_URL}/odds/multi",
            params={
                "apiKey": api_key,
                "eventIds": ",".join(str(event["id"]) for event in chunk),
                "bookmakers": ",".join(bookmakers[:30]),
            },
            timeout=45,
        )
        odds.raise_for_status()
        body = odds.json()
        if isinstance(body, list):
            payload.extend(body)
    return payload, bookmakers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", help="Use a saved /odds/multi payload instead of calling the API.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--days-ahead", type=int, default=4)
    parser.add_argument("--max-events", type=int, default=10)
    parser.add_argument("--max-requests", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if args.input_json:
        payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        bookmakers: list[str] = []
    else:
        load_env()
        api_key = (os.environ.get("ODDS_API_KEY") or os.environ.get("ODDS_API_IO_KEY") or "").strip()
        if not api_key:
            raise SystemExit("Set ODDS_API_KEY or ODDS_API_IO_KEY, or pass --input-json")
        try:
            payload, bookmakers = fetch_payload(api_key, args.days_ahead, args.max_events, args.max_requests)
        except (requests.RequestException, RuntimeError) as exc:
            payload, bookmakers = [], []
            result = build_index([], captured_at)
            result["status"] = "CAPTURE_FAILED"
            result["error"] = safe_error_summary(exc)
        else:
            result = build_index(payload if isinstance(payload, list) else [], captured_at)
    if args.input_json:
        result = build_index(payload if isinstance(payload, list) else [], captured_at)
    result["requested_bookmakers"] = bookmakers
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
