#!/usr/bin/env python3
"""Apply reviewed league audit files to the public club penalty hierarchy."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "goalscorer"
RESEARCH_DIR = DATA_DIR / "research"
LEAGUES = ("epl", "serie-a", "la-liga", "bundesliga", "ligue-1")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def find_team_name(hierarchy: dict[str, Any], researched_name: str) -> str:
    candidates = [name for name in hierarchy if not name.startswith("_")]
    target = normalize(researched_name)
    exact = [name for name in candidates if normalize(name) == target]
    if len(exact) == 1:
        return exact[0]

    aliases = {
        "angers sco": "angers",
        "aj auxerre": "auxerre",
        "stade brestois 29": "brest",
        "le havre ac": "le havre",
        "le mans fc": "le mans",
        "rc lens": "lens",
        "losc lille": "lille",
        "fc lorient": "lorient",
        "olympique lyonnais": "lyon",
        "olympique de marseille": "marseille",
        "as monaco": "monaco",
        "ogc nice": "nice",
        "stade rennais": "rennes",
        "rc strasbourg alsace": "strasbourg",
        "toulouse fc": "toulouse",
        "estac troyes": "troyes",
        "parma calcio 1913": "parma calcio 1913",
    }
    alias = aliases.get(target)
    if alias:
        matched = [name for name in candidates if normalize(name) == alias]
        if len(matched) == 1:
            return matched[0]
    raise ValueError(f"Could not map audited club {researched_name!r}")


def public_status(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("classification") or value.get("status") or value.get("note")
    status = str(value or "").lower()
    if "disput" in status or "contest" in status:
        return "disputed"
    if any(
        token in status
        for token in (
            "conditional",
            "dependent",
            "injury",
            "transfer",
            "competition",
        )
    ):
        return "conditional"
    if "provisional" in status:
        return "probable"
    if "confirm" in status or "verified" in status:
        return "confirmed"
    return "probable"


def confidence_values(row: dict[str, Any]) -> dict[str, str]:
    raw = (
        row.get("confidence_by_position")
        or row.get("position_confidence")
        or row.get("per_position_confidence")
        or row.get("confidence")
        or {}
    )
    if not isinstance(raw, dict):
        raw = {}
    return {
        position: str(raw.get(position) or "low").lower()
        for position in ("primary", "secondary", "tertiary")
    }


def order_values(row: dict[str, Any], field: str) -> dict[str, str] | None:
    raw = row.get(field)
    if isinstance(raw, dict):
        return {
            position: str(raw.get(position) or "").strip()
            for position in ("primary", "secondary", "tertiary")
        }
    if isinstance(raw, list) and len(raw) >= 3:
        return {
            position: str(raw[index] or "").strip()
            for index, position in enumerate(("primary", "secondary", "tertiary"))
        }
    return None


def recommended_order(row: dict[str, Any]) -> dict[str, str]:
    order = order_values(row, "recommended_order")
    if order is None:
        raise ValueError(f"{row.get('club')}: recommended_order must contain three positions")
    return order


def source_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    rows = row.get("sources") or []
    return [source for source in rows if isinstance(source, dict)]


def text_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get("note")
            or value.get("summary")
            or value.get("condition")
            or value.get("player")
            or ""
        ).strip()
    return str(value or "").strip()


def evidence_event(
    team: str,
    row: dict[str, Any],
    audit_date: str,
    season: str,
) -> dict[str, Any]:
    sources = []
    for source in source_rows(row):
        sources.append(
            {
                "label": str(
                    source.get("label")
                    or source.get("source")
                    or source.get("publisher")
                    or "Il Margine source review"
                ),
                "url": str(source.get("url") or "") or None,
                "date": str(source.get("date") or audit_date),
                "note": str(
                    source.get("claim")
                    or source.get("finding")
                    or source.get("summary")
                    or source.get("note")
                    or source.get("title")
                    or "Source reviewed."
                ),
            }
        )
    return {
        "id": f"evt_{audit_date.replace('-', '')}_{slug(team)}_research",
        "date": audit_date,
        "season": season,
        "type": "multi_source_preseason_research",
        "penalty_kind": None,
        "competition": None,
        "match": None,
        "context": str(row.get("rationale") or "").strip(),
        "sources": sources[:10],
        "detection": "manual_multi_source_research",
        "review": {
            "status": "approved",
            "reviewed_by": "Il Margine",
            "reviewed_at": f"{audit_date}T12:00:00Z",
        },
        "affects_hierarchy": True,
        "editorial_note": f"Reviewed {len(sources)} source records for the {season} hierarchy.",
    }


def condition_note(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("rationale") or "").strip(),
        str(row.get("note") or "").strip(),
        str(row.get("uncertainty_note") or "").strip(),
    ]
    conditions = row.get("transfer_conditions") or row.get("conditions") or []
    if not isinstance(conditions, list):
        conditions = [conditions]
    condition_text = [text_value(item) for item in conditions]
    condition_text = [item for item in condition_text if item]
    if condition_text:
        parts.append("Conditions: " + " ".join(condition_text))
    return " ".join(part for part in parts if part)


def apply_league(league: str, audit_date: str, write: bool) -> tuple[int, int]:
    hierarchy_path = DATA_DIR / f"{league}-penalty-takers.json"
    audit_path = RESEARCH_DIR / f"agent-{league}-hierarchy-audit-{audit_date}.json"
    hierarchy = load_json(hierarchy_path)
    audit = load_json(audit_path)
    rows = audit.get("clubs") or []
    if not isinstance(rows, list):
        raise ValueError(f"{audit_path}: clubs must be a list")

    expected = {name for name in hierarchy if not name.startswith("_")}
    mapped: set[str] = set()
    changed = 0
    season = str(hierarchy.get("_meta", {}).get("season", {}).get("label") or "2026/27")

    for row in rows:
        team = find_team_name(hierarchy, str(row.get("club") or ""))
        if team in mapped:
            raise ValueError(f"{league}: duplicate audit row for {team}")
        mapped.add(team)

        after = recommended_order(row)
        missing = [position for position, player in after.items() if not player]
        if missing:
            raise ValueError(f"{league}/{team}: blank recommended positions: {missing}")
        if len({normalize(player) for player in after.values()}) != 3:
            raise ValueError(f"{league}/{team}: recommended positions must name three distinct players")

        entry = hierarchy[team]
        current = {
            position: str(entry.get(position) or "").strip()
            for position in ("primary", "secondary", "tertiary")
        }
        before = order_values(row, "existing_order") or current
        changed += int(before != after)
        event = evidence_event(team, row, audit_date, season)
        confidence = confidence_values(row)
        sources = source_rows(row)
        labels = [
            str(
                source.get("label")
                or source.get("source")
                or source.get("publisher")
                or ""
            ).strip()
            for source in sources
            if str(
                source.get("label")
                or source.get("source")
                or source.get("publisher")
                or ""
            ).strip()
        ]

        entry.update(after)
        entry["last_updated"] = audit_date
        entry["source"] = labels[0] if labels else "Il Margine multi-source research"
        entry["cross_check"] = labels[1] if len(labels) > 1 else "Il Margine roster cross-check"
        entry["hierarchy_status"] = public_status(row.get("status"))
        entry["confidence"] = confidence
        entry["condition_note"] = condition_note(row)
        entry["last_verified"] = {
            "date": audit_date,
            "by": "Il Margine",
            "method": "multi_source_preseason_research",
        }
        entry["public_updated_at"] = audit_date
        entry["latest_evidence"] = {
            "id": event["id"],
            "date": audit_date,
            "type": event["type"],
            "source_count": len(event["sources"]),
        }
        entry["evidence_log"] = [
            item
            for item in entry.get("evidence_log", [])
            if item.get("id") != event["id"]
        ] + [event]

        change_type = "preseason_reverification" if before == after else "hierarchy_research_update"
        entry["change_log"] = [
            item
            for item in entry.get("change_log", [])
            if not (
                item.get("changed_at") == audit_date
                and item.get("change_type") in {"preseason_reverification", "hierarchy_research_update"}
            )
        ] + [
            {
                "changed_at": audit_date,
                "season": season,
                "change_type": change_type,
                "from": before,
                "to": after,
                "reason": entry["condition_note"],
                "evidence_ids": [event["id"]],
                "detection": "manual_multi_source_research",
                "approved_by": "Il Margine",
                "approved_at": f"{audit_date}T12:00:00Z",
                "article_slug": None,
            }
        ]
        flags = dict(entry.get("flags") or {})
        flags["carryover_from_previous_season"] = False
        flags["weak_evidence"] = entry["hierarchy_status"] in {"conditional", "disputed"} or "low" in confidence.values()
        entry["flags"] = flags

    if mapped != expected:
        raise ValueError(
            f"{league}: audit coverage mismatch; missing={sorted(expected - mapped)}, extra={sorted(mapped - expected)}"
        )

    meta = hierarchy.get("_meta") or {}
    meta["last_verified"] = audit_date
    meta["public_updated_at"] = audit_date
    hierarchy["_meta"] = meta
    if write:
        hierarchy_path.write_text(
            json.dumps(hierarchy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return len(mapped), changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-date", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    total = 0
    changed = 0
    for league in LEAGUES:
        league_total, league_changed = apply_league(league, args.audit_date, args.write)
        total += league_total
        changed += league_changed
        print(f"{league}: clubs={league_total} changes={league_changed}")
    print(f"total: clubs={total} changes={changed} write={args.write}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
