"""Bounded, unauthenticated Grosvenor/Kambi tennis stat-bet capture.

Use the sportsbook's public gruk offering, not Odds-API's incomplete Kambi
market subset. Prices and thresholds are integer thousandths, not fractions.
Only complete, open, pre-match full-match contracts enter the existing inbox.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone

import requests

BOOK = "Grosvenor"
BASE = "https://eu-offering-api.kambicdn.com/offering/v2018/gruk"
PARAMS = {"lang": "en_GB", "market": "GB", "client_id": 2}
MAX_EVENTS = 12


def utc(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else None
    except (TypeError, ValueError):
        return None


def eligible(event, now, days_ahead=2):
    start = utc(event.get("start"))
    tours = {p.get("termKey") for p in event.get("path", [])}
    return (event.get("sport") == "TENNIS" and event.get("state") == "NOT_STARTED"
            and bool(start and now < start <= now + timedelta(days=days_ahead))
            and bool(tours & {"atp", "wta"})
            and all(event.get(k) and "/" not in event[k] and " & " not in event[k]
                    for k in ("homeName", "awayName")))


def scaled(value, *, price=False):
    # Reject strings, booleans, already-decimal odds and non-finite numbers.
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    number = value / 1000
    return number if math.isfinite(number) and number >= 0 and (not price or number > 1) else None


def normalize(payload, requested_id, captured_at, days_ahead=2):
    now = utc(captured_at)
    events = [e for e in payload.get("events", []) if str(e.get("id")) == str(requested_id)]
    if not now or len(events) != 1 or not eligible(events[0], now, days_ahead):
        return None
    event = events[0]
    markets = []
    for offer in payload.get("betOffers", []):
        name = offer.get("criterion", {}).get("englishLabel")
        if (str(offer.get("eventId")) != str(requested_id)
                or name not in {"Total Aces", "Most Aces", "Total Double Faults", "Most Double Faults"}
                or "OFFERED_PREMATCH" not in offer.get("tags", [])):
            continue
        outcomes = offer.get("outcomes", [])
        if any(o.get("status") != "OPEN" or scaled(o.get("odds"), price=True) is None
               or str(o.get("betOfferId")) != str(offer.get("id")) for o in outcomes):
            continue
        by_type = {o.get("type"): o for o in outcomes}
        if len(by_type) != len(outcomes):
            continue
        if name in {"Total Aces", "Total Double Faults"}:
            if set(by_type) != {"OT_OVER", "OT_UNDER"} or offer.get("betOfferType", {}).get("id") != 6:
                continue
            over, under = by_type["OT_OVER"], by_type["OT_UNDER"]
            line = scaled(over.get("line"))
            if line is None or line != scaled(under.get("line")) or line % 0.5 != 0:
                continue
            odds = [{"label": "Over/Under", "hdp": line,
                     "over": scaled(over["odds"], price=True), "under": scaled(under["odds"], price=True)}]
        else:
            if set(by_type) != {"OT_ONE", "OT_CROSS", "OT_TWO"} or offer.get("betOfferType", {}).get("id") != 2:
                continue
            if (by_type["OT_ONE"].get("participant") != event["homeName"]
                    or by_type["OT_TWO"].get("participant") != event["awayName"]
                    or any(o.get("line") is not None for o in outcomes)):
                continue
            odds = [{"home": scaled(by_type["OT_ONE"]["odds"], price=True),
                     "draw": scaled(by_type["OT_CROSS"]["odds"], price=True),
                     "away": scaled(by_type["OT_TWO"]["odds"], price=True)}]
        updates = [o.get("changedDate", "") for o in outcomes]
        if any(not utc(t) or utc(t) > now for t in updates):
            continue
        markets.append({"name": name, "odds": odds, "updatedAt": max(updates),
                        "source_offer_id": str(offer["id"]), "raw_offer": offer,
                        "raw_event": event, "captured_at": captured_at,
                        "settlement_policy": "completed_match_only; unfinished_requires_contract_review"})
    tour = "WTA" if any(p.get("termKey") == "wta" for p in event["path"]) else "ATP"
    return {"id": f"kambi:{requested_id}", "date": event["start"],
            "home": event["homeName"], "away": event["awayName"],
            "league": {"name": f"{tour} - {event['group']}"},
            "urls": {BOOK: f"https://www.grosvenorcasinos.com/sport#event/{requested_id}"},
            "captured_at": captured_at, "bookmakers": {BOOK: markets}}


def capture(*, days_ahead=2, max_events=MAX_EVENTS, get=requests.get):
    """At most one catalogue plus twelve event GETs, with a 55s wall budget.

    A failed direct source never prevents the independent Sisal capture.
    HTTP errors are recorded without repeated retries or alternative hosts.
    """
    started = time.monotonic()
    now = datetime.now(timezone.utc)
    receipt = {"source": BASE, "bookmaker": BOOK, "captured_at": now.isoformat(),
               "requests": 0, "events": [], "errors": [], "eligible_events": 0}
    normalized = []

    def fetch(path):
        receipt["requests"] += 1
        response = get(f"{BASE}/{path}.json", params=PARAMS, timeout=8)
        response.raise_for_status()
        return response.json()

    try:
        catalog = fetch("listView/tennis/all/all/all/matches")
        events = [item["event"] for item in catalog.get("events", [])
                  if eligible(item.get("event", {}), now, days_ahead)]
        events = sorted({e["id"]: e for e in events}.values(), key=lambda e: (e["start"], e["id"]))
        receipt["eligible_events"] = len(events)
        for event in events[:min(MAX_EVENTS, max(0, max_events))]:
            if time.monotonic() - started > 47:
                receipt["errors"].append("wall_budget_reached")
                break
            try:
                raw = fetch(f"betoffer/event/{event['id']}")
                stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                receipt["events"].append({"captured_at": stamp, "requested_id": event["id"], "payload": raw})
                parsed = normalize(raw, event["id"], stamp, days_ahead)
                if parsed:
                    normalized.append(parsed)
            except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
                receipt["errors"].append(f"event:{event['id']}:{type(exc).__name__}")
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        receipt["errors"].append(f"catalog:{type(exc).__name__}")
    receipt["captured_events"] = len(normalized)
    receipt["market_count"] = sum(len(e["bookmakers"][BOOK]) for e in normalized)
    receipt["status"] = "CAPTURED" if receipt["market_count"] else "NO_VERIFIED_MARKETS"
    return normalized, receipt
