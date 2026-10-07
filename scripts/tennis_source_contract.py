"""OnCourt field meanings shared by live models and offline validation.

Court 3 is indoor hard, 4 carpet, 5 grass. FSOF already counts ALL service
points; second-serve opportunities are a subset. Unknown metadata is not clay.
"""
from __future__ import annotations

import csv
import math
import json
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "oncourt-surface-points-20261007-v1"


def canonical_surface(value: object, *, combine_hard: bool = False) -> str:
    text = str(value or "").strip().casefold()
    if "clay" in text or "terre" in text:
        return "Clay"
    if "grass" in text:
        return "Grass"
    if "carpet" in text:
        return "Carpet"
    if text in {"i.hard", "i. hard", "ihard"} or ("indoor" in text and "hard" in text):
        return "Hard" if combine_hard else "I.hard"
    if "hard" in text or "acrylic" in text or "decoturf" in text:
        return "Hard"
    return "N/A"


def court_surfaces(path: Path, *, combine_hard: bool = False) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {}
    for row in rows:
        key = str(row.get("id") or "").strip()
        value = canonical_surface(row.get("name"), combine_hard=combine_hard)
        if not key or key in result:
            raise ValueError("missing or duplicate OnCourt court identity")
        result[key] = value
    return result


def service_points(row: dict, prefix: str) -> int:
    """Resolve actual service points, rejecting conflicting exported totals."""
    values = []
    for key in (prefix + "svpt", prefix + "fsof"):
        raw = row.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        value = float(raw)
        if not math.isfinite(value) or value < 0 or not value.is_integer():
            raise ValueError("invalid service-point count")
        values.append(int(value))
    if not values or len(set(values)) != 1:
        raise ValueError("missing or conflicting service-point totals")
    return values[0]


def validate_profiles(rows: list[dict]) -> None:
    """A decomposed serve rate must reconstruct aggregate SPW on the same window.

    Prevent corrected inference from consuming old inflated-denominator profiles.
    Missing decomposition remains an explicit supported fallback.
    """
    for row in rows:
        for suffix in ("", "_long"):
            fields = ["first_serve_pct", "first_serve_win_pct", "second_serve_win_pct", "hold_pct"]
            values = [row.get(k + suffix) for k in fields]
            if any(v is None for v in values):
                continue
            first, win1, win2, aggregate = map(float, values)
            if not all(math.isfinite(v) and 0 <= v <= 1 for v in (first, win1, win2, aggregate)):
                raise ValueError("invalid player service probability")
            if abs(first * win1 + (1 - first) * win2 - aggregate) > 0.005:
                raise ValueError("player service profiles use inconsistent point denominators; rebuild profiles")


def stat_problem(row: dict) -> str | None:
    """Verify reciprocal ATP point counts before deriving any player rates."""
    counts = {}
    try:
        for p in ("w_", "l_"):
            total = service_points(row, p)
            values = []
            for field in ("fs", "w1s", "w2s", "w2sof", "rpw", "rpwof"):
                raw = row.get(p + field)
                if raw is None or str(raw).strip() == "":
                    return "missing_point_count"
                value = float(raw)
                if not math.isfinite(value) or value < 0 or not value.is_integer():
                    return "invalid_point_count"
                values.append(int(value))
            first, win1, win2, second, returned, faced = values
            if not (total > 0 and first + second == total and win1 <= first and win2 <= second and returned <= faced):
                return "inconsistent_point_counts"
            counts[p] = (total, win1 + win2, returned, faced)
        for p, q in (("w_", "l_"), ("l_", "w_")):
            total, won, returned, faced = counts[p]
            other = counts[q]
            if faced != other[0] or returned != other[0] - other[1]:
                return "nonreciprocal_point_counts"
    except (ValueError, TypeError):
        return "invalid_service_total"
    return None


def unique_fixture_rows(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        try:
            winner, loser = int(row['winner_id']), int(row['loser_id'])
            key = (int(row['tour_id']), int(row['round_id']), *sorted((winner, loser)))
        except (KeyError, TypeError, ValueError):
            continue
        if winner == loser:
            continue
        grouped[key].append(row)
    accepted = []
    for group in grouped.values():
        signatures = {(str(r.get('date') or '')[:10], str(r.get('result') or r.get('score') or ''), str(r['winner_id'])) for r in group}
        if len(signatures) == 1:
            accepted.append(group[0])
    return accepted


def validated_stat_rows(rows: list[dict], wanted_keys: set) -> tuple[list[dict], dict]:
    grouped = defaultdict(list)
    reasons = Counter()
    for row in rows:
        try:
            key = tuple(int(row[k]) for k in ("winner_id", "loser_id", "tour_id", "round_id"))
        except (ValueError, TypeError, KeyError):
            reasons["invalid_fixture_identity"] += 1
            continue
        if key in wanted_keys:
            grouped[key].append(row)
    accepted = []
    for group in grouped.values():
        if any(row != group[0] for row in group[1:]):
            reasons["conflicting_duplicate_stat"] += len(group)
            continue
        reasons["identical_duplicates_removed"] += len(group) - 1
        row = group[0]
        reason = stat_problem(row)
        if reason:
            reasons[reason] += 1
        else:
            accepted.append(row)
    return accepted, dict(reasons)



def write_profile_contract(rows: list[dict], path: Path | None = None) -> None:
    """Publish an explicit current key set without deleting any older DB rows."""
    path = path or Path(__file__).resolve().parents[1] / "data/oncourt/player-profile-contract.json"
    keys = sorted({(int(row["player_id"]), row["surface"]) for row in rows})
    if len(keys) < 100:
        raise ValueError("incomplete player profile build")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"source_contract":VERSION,"profile_keys":keys}), encoding="utf-8")
    temporary.replace(path)


def current_profile_rows(rows: list[dict], path: Path | None = None) -> list[dict]:
    path = path or Path(__file__).resolve().parents[1] / "data/oncourt/player-profile-contract.json"
    if not path.exists():
        raise ValueError("validated player-profile contract missing; rebuild player stats first")
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("source_contract") != VERSION:
        raise ValueError("unsupported player profile source contract")
    keys = {(int(pid), surface) for pid,surface in contract["profile_keys"]}
    return [row for row in rows if (int(row["player_id"]),row["surface"]) in keys]
