#!/usr/bin/env python3
"""Apply the reviewed 2026/27 club penalty audit to the public hierarchy files."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "goalscorer"
RESEARCH_DIR = DATA_DIR / "research"
AUDIT_DATE = "2026-07-27"
AUDIT_TIME = f"{AUDIT_DATE}T12:00:00Z"
SEASON = "2026/27"
LEAGUES = ("epl", "serie-a", "la-liga", "bundesliga", "ligue-1")


def normalize(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def slug(value: str) -> str:
    return normalize(value).replace(" ", "_")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def recommendation(row: dict[str, Any]) -> list[str | None]:
    raw = row.get("recommended_hierarchy", row.get("recommended_order"))
    if isinstance(raw, dict):
        return [raw.get("primary"), raw.get("secondary"), raw.get("tertiary")]
    if isinstance(raw, list):
        return (raw + [None, None, None])[:3]
    return [None, None, None]


def verdict_code(row: dict[str, Any]) -> str:
    raw = row.get("verdict", "")
    if isinstance(raw, dict):
        return str(raw.get("code", "")).upper()
    return str(raw).upper()


def row_note(row: dict[str, Any]) -> str:
    note = (
        row.get("confidence_note")
        or row.get("recommended_notes")
        or row.get("reason")
        or ""
    )
    text = str(note).strip()
    if text:
        return text
    if str(row.get("club") or "") == "SC Paderborn 07":
        return (
            "Mika Baur is the only current player with a documented regular-time attempt after "
            "Filip Bilbija's departure, but transfer interest makes the call provisional."
        )
    return ""


def confidence_values(row: dict[str, Any]) -> tuple[str, list[str]]:
    raw = row.get("confidence", "LOW")
    if isinstance(raw, dict):
        overall = str(raw.get("overall", "LOW"))
        positions = [str(value) for value in raw.get("by_position", [])]
    else:
        overall = str(raw)
        positions = []
    return overall.upper(), positions


def confidence_level(value: str) -> str:
    upper = value.upper()
    if "VERY_HIGH" in upper or upper == "HIGH" or upper.startswith("HIGH_"):
        return "high"
    if "MEDIUM" in upper:
        return "medium"
    return "low"


def hierarchy_status(row: dict[str, Any], primary: str | None) -> str:
    verdict = verdict_code(row)
    note = row_note(row).lower()
    overall, _ = confidence_values(row)
    if not primary:
        if any(term in note for term in ("disagree", "conflict", "committee")):
            return "disputed"
        return "unknown"
    if "FIXED_ORDER" in verdict or "COMMITTEE" in note:
        return "disputed"
    if "CONDITIONAL" in verdict or "ROSTER_RISK" in verdict:
        return "conditional"
    if "VERY_HIGH" in overall:
        return "confirmed"
    return "probable"


def evidence_source(evidence: dict[str, Any]) -> tuple[str, str]:
    source = str(evidence.get("source") or "Il Margine source review").strip()
    url = str(evidence.get("url") or "").strip()
    return source, url


def evidence_summary(evidence: dict[str, Any]) -> str:
    return str(
        evidence.get("summary")
        or evidence.get("claim")
        or evidence.get("title")
        or "Source reviewed for the current hierarchy."
    ).strip()


def evidence_type(evidence: dict[str, Any]) -> str:
    return str(evidence.get("type") or evidence.get("evidence_type") or "source_review").lower()


def evidence_context(evidence: dict[str, Any]) -> str | None:
    value = evidence.get("penalty_context")
    return str(value).lower() if value else None


def build_evidence_events(team: str, evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, str | None]] = []
    notes: list[str] = []
    dates: list[str] = []
    for evidence in evidence_rows:
        source, url = evidence_source(evidence)
        summary = evidence_summary(evidence)
        evidence_date = str(evidence.get("date") or AUDIT_DATE)
        if not any(existing.get("url") == url for existing in sources):
            sources.append(
                {
                    "label": source,
                    "url": url or None,
                    "date": evidence_date,
                    "note": summary,
                }
            )
        if summary and summary not in notes:
            notes.append(summary)
        dates.append(evidence_date)
    if not evidence_rows:
        return []
    event_id = f"evt_{AUDIT_DATE.replace('-', '')}_{slug(team)}_research"
    return [
        {
            "id": event_id,
            "date": AUDIT_DATE,
            "season": SEASON,
            "type": "multi_source_preseason_research",
            "penalty_kind": None,
            "competition": None,
            "match": None,
            "context": " ".join(notes[:3]),
            "sources": sources[:8],
            "detection": "manual_multi_source_research",
            "review": {
                "status": "approved",
                "reviewed_by": "Il Margine",
                "reviewed_at": AUDIT_TIME,
            },
            "affects_hierarchy": True,
            "editorial_note": f"Reviewed {len(evidence_rows)} source records for the {SEASON} hierarchy.",
        }
    ]


def current_order(entry: dict[str, Any]) -> dict[str, str]:
    return {
        "primary": str(entry.get("primary") or ""),
        "secondary": str(entry.get("secondary") or ""),
        "tertiary": str(entry.get("tertiary") or ""),
    }


def find_team_name(hierarchy: dict[str, Any], research_name: str) -> str:
    candidates = [name for name in hierarchy if not name.startswith("_")]
    target = normalize(research_name)
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
    }
    alias = aliases.get(target)
    if alias:
        matched = [name for name in candidates if normalize(name) == alias]
        if len(matched) == 1:
            return matched[0]
    raise ValueError(f"Could not map researched club {research_name!r}")


def apply_row(entry: dict[str, Any], team: str, row: dict[str, Any]) -> bool:
    before = current_order(entry)
    recommended = recommendation(row)
    primary, secondary, tertiary = [str(value).strip() if value else "" for value in recommended]
    status = hierarchy_status(row, primary or None)
    overall, positions = confidence_values(row)
    levels = [
        confidence_level(positions[index] if index < len(positions) else overall)
        for index in range(3)
    ]
    note = row_note(row)
    evidence_rows = [item for item in row.get("evidence", []) if isinstance(item, dict)]
    events = build_evidence_events(team, evidence_rows)
    sources = [evidence_source(item) for item in evidence_rows]
    source_labels = [label for label, _ in sources if label]
    after = {"primary": primary, "secondary": secondary, "tertiary": tertiary}

    entry.update(after)
    entry["last_updated"] = AUDIT_DATE
    entry["source"] = source_labels[0] if source_labels else "Il Margine multi-source research"
    entry["cross_check"] = source_labels[1] if len(source_labels) > 1 else "Il Margine roster cross-check"
    entry["hierarchy_status"] = status
    entry["confidence"] = {
        "primary": levels[0],
        "secondary": levels[1] if secondary else "low",
        "tertiary": levels[2] if tertiary else "low",
    }
    entry["condition_note"] = note
    entry["last_verified"] = {
        "date": AUDIT_DATE,
        "by": "Il Margine",
        "method": "multi_source_preseason_research",
    }
    entry["public_updated_at"] = AUDIT_DATE
    entry["latest_evidence"] = (
        {
            "id": events[0]["id"],
            "date": AUDIT_DATE,
            "type": "multi_source_preseason_research",
            "source_count": len(events[0]["sources"]),
        }
        if events
        else None
    )

    old_events = [
        event
        for event in entry.get("evidence_log", [])
        if not str(event.get("id", "")).startswith(f"evt_{AUDIT_DATE.replace('-', '')}_{slug(team)}_research")
    ]
    entry["evidence_log"] = old_events + events

    change_type = "preseason_reverification" if before == after else "hierarchy_research_update"
    change_id_list = [event["id"] for event in events]
    existing_research_change = next(
        (
            change
            for change in entry.get("change_log", [])
            if change.get("changed_at") == AUDIT_DATE
            and change.get("change_type") in {"preseason_reverification", "hierarchy_research_update"}
        ),
        None,
    )
    old_changes = [
        change
        for change in entry.get("change_log", [])
        if not (
            change.get("changed_at") == AUDIT_DATE
            and change.get("change_type") in {"preseason_reverification", "hierarchy_research_update"}
        )
    ]
    old_changes.append(
        existing_research_change
        or {
            "changed_at": AUDIT_DATE,
            "season": SEASON,
            "change_type": change_type,
            "from": before,
            "to": after,
            "reason": note or "Current hierarchy checked against the 2026/27 multi-source preseason audit.",
            "evidence_ids": change_id_list,
            "detection": "manual_multi_source_research",
            "approved_by": "Il Margine",
            "approved_at": AUDIT_TIME,
            "article_slug": None,
        }
    )
    entry["change_log"] = old_changes
    flags = dict(entry.get("flags") or {})
    flags["carryover_from_previous_season"] = False
    flags["weak_evidence"] = status in {"unknown", "disputed", "conditional"} or levels[0] == "low"
    entry["flags"] = flags
    return before != after


def apply_league(league: str, write: bool) -> tuple[int, int]:
    hierarchy_path = DATA_DIR / f"{league}-penalty-takers.json"
    research_path = RESEARCH_DIR / f"{league}-penalty-research-{AUDIT_DATE}.json"
    hierarchy = load_json(hierarchy_path)
    research = load_json(research_path)
    rows = research.get("clubs", [])
    if not isinstance(rows, list):
        raise ValueError(f"{research_path}: clubs must be a list")

    changed = 0
    mapped: set[str] = set()
    for row in rows:
        research_name = str(row.get("club") or "").strip()
        team = find_team_name(hierarchy, research_name)
        if team in mapped:
            raise ValueError(f"{league}: duplicate research row for {team}")
        mapped.add(team)
        changed += int(apply_row(hierarchy[team], team, row))

    expected = {name for name in hierarchy if not name.startswith("_")}
    if mapped != expected:
        missing = sorted(expected - mapped)
        extra = sorted(mapped - expected)
        raise ValueError(f"{league}: mapping mismatch; missing={missing}, extra={extra}")

    meta = hierarchy.get("_meta", {})
    meta["last_verified"] = AUDIT_DATE
    meta["public_updated_at"] = AUDIT_DATE
    hierarchy["_meta"] = meta
    if write:
        hierarchy_path.write_text(
            json.dumps(hierarchy, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return len(mapped), changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write the five hierarchy JSON files.")
    args = parser.parse_args()

    total_rows = 0
    total_changes = 0
    for league in LEAGUES:
        rows, changes = apply_league(league, write=args.write)
        total_rows += rows
        total_changes += changes
        action = "updated" if args.write else "would update"
        print(f"{league}: {action} {rows} clubs; hierarchy changes={changes}")
    print(f"total: clubs={total_rows}; hierarchy changes={total_changes}; write={args.write}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
