"""Shared, conservative ATP qualifying identity and schedule coverage helpers."""
from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ALIASES = {
    "australian_open": {"australian open"},
    "french_open": {"french open", "roland garros"},
    "us_open": {"us open", "u s open"},
    "wimbledon": {"wimbledon"},
    "indian_wells": {"indian wells"}, "miami": {"miami"},
    "monte_carlo": {"monte carlo", "montecarlo"}, "madrid": {"madrid"},
    "rome": {"rome", "roma", "italian open", "internazionali bnl"},
    "canada": {"canada", "canadian open", "montreal", "toronto", "national bank open", "rogers cup"},
    "cincinnati": {"cincinnati", "western southern"},
    "shanghai": {"shanghai"}, "paris": {"paris"},
}


def normalized(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return re.sub(r"[^a-z0-9]+", " ", text.encode("ascii", "ignore").decode().lower()).strip()


def event_key(text):
    raw = str(text or "")
    norm = normalized(raw)
    if re.search(r"\b(wta|women|challenger|itf|doubles|futures|laver|davis|united cup)\b", norm):
        return None
    for key, aliases in ALIASES.items():
        if any(f" {alias} " in f" {norm} " for alias in aliases):
            return key
    # OnCourt supplies 'sponsor/tournament - city'; Pinnacle 'ATP city - Qualifiers'.
    # Use the entire city token sequence, never fuzzy substring matches.
    raw = re.sub(r"\s*[-–]\s*qualif.*$", "", raw, flags=re.I)
    raw = re.sub(r"\bqualif\w*\b", "", raw, flags=re.I)
    raw = re.sub(r"^ATP\s+", "", raw, flags=re.I)
    core = normalized(re.split(r"\s+[-–]\s+", raw)[-1])
    return core or None


def read_rows(path):
    if not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def current_tours(rows, target):
    candidates = defaultdict(list)
    for row in rows:
        try:
            rank, tid = int(row.get("rank") or 0), int(row.get("id") or 0)
            day = date.fromisoformat(str(row.get("date") or "")[:10])
        except (ValueError, TypeError):
            continue
        key = event_key(row.get("name"))
        if rank not in (2, 3, 4) or not tid or not key or not -7 <= (day - target).days <= 10:
            continue
        candidates[key].append({"tour_id": tid, "tour_name": row["name"],
                                "tour_date": day.isoformat(), "court_id": int(row.get("court_id") or 0)})
    # Two current editions with the same city are ambiguous: do not guess.
    return {key: values[0] for key, values in candidates.items() if len(values) == 1}


def scheduled_qualifiers(schedule, tours, target):
    by_id = {row["tour_id"]: row for row in tours.values()}
    result, seen = [], set()
    for row in schedule:
        try:
            tid, p1, p2, rnd = [int(row.get(k) or 0) for k in ("tour_id", "player1_id", "player2_id", "round_id")]
            day = date.fromisoformat(str(row.get("date") or "")[:10])
        except (ValueError, TypeError):
            continue
        identity = (tid, *sorted((p1, p2)))
        if (tid not in by_id or rnd not in (1, 2, 3) or not p1 or not p2 or p1 == p2
                or str(row.get("result") or "").strip() or str(row.get("complete") or "").lower() in ("1", "true")
                or str(row.get("live") or "").lower() in ("1", "true")
                or not target <= day <= target + timedelta(days=1) or identity in seen):
            continue
        seen.add(identity)
        result.append({**row, "tour_id": tid, "player1_id": p1, "player2_id": p2,
                       "tour_name": by_id[tid]["tour_name"]})
    return result


def is_upcoming_quote(row, now):
    try:
        kickoff = datetime.fromisoformat(str(row.get("kickoff_iso") or "").replace("Z", "+00:00"))
        return kickoff.tzinfo is not None and kickoff > now
    except ValueError:
        return False


def missing_qualifier_keys(schedule, tours, active_leagues, target):
    expected = {event_key(r["tour_name"]) for r in scheduled_qualifiers(schedule, tours, target)}
    present = {event_key(r.get("name")) for r in active_leagues if "qualif" in str(r.get("name", "")).lower()}
    return expected - present


def fallback_leagues(catalogue, missing):
    return {int(r["id"]): r for r in catalogue
            if str(r.get("name", "")).upper().startswith("ATP ")
            and "qualif" in str(r.get("name", "")).lower()
            and event_key(r.get("name")) in missing}


def schedule_coverage(schedule, tours, markets, resolve_player, target, now):
    priced = set()
    for row in markets:
        if not is_upcoming_quote(row, now):
            continue
        try:
            if float(row.get("odds1") or 0) <= 1 or float(row.get("odds2") or 0) <= 1:
                continue
        except ValueError:
            continue
        p1, _ = resolve_player(str(row.get("player1_name") or ""))
        p2, _ = resolve_player(str(row.get("player2_name") or ""))
        if p1 and p2:
            priced.add((event_key(row.get("league_name")), *sorted((p1, p2))))
    grouped = {}
    for row in scheduled_qualifiers(schedule, tours, target):
        group = grouped.setdefault(row["tour_id"], {"tour_id": row["tour_id"], "tournament": row["tour_name"],
                                                   "scheduled_qualifiers": 0, "with_current_prices": 0})
        group["scheduled_qualifiers"] += 1
        identity = (event_key(row["tour_name"]), *sorted((row["player1_id"], row["player2_id"])))
        group["with_current_prices"] += int(identity in priced)
    for group in grouped.values():
        group["missing_prices"] = group["scheduled_qualifiers"] - group["with_current_prices"]
        group["status"] = "awaiting_prices" if group["missing_prices"] else "priced"
    return list(grouped.values())
