#!/usr/bin/env python3
"""Apply reviewed post-deadline penalty corrections and current-squad evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "goalscorer"
RESEARCH_PATH = DATA_DIR / "research" / "club-penalty-post-deadline-2026-09-02.json"
AUDIT_PATH = DATA_DIR / "club-penalty-squad-audit.json"
LEAGUES = ("epl", "serie-a", "la-liga", "bundesliga", "ligue-1")
ROLE_SOURCES = {
    "epl": {
        "label": "Current FPL set-piece order",
        "url": "https://aifpl.co.uk/set-pieces",
    },
    "serie-a": {
        "label": "Goal Italia 2026/27 rigoristi",
        "url": "https://www.goal.com/it/liste/fantacalcio-rigoristi-serie-a-2026-2027-tiratori-e-gerarchie-dal-dischetto-delle-20-squadre-del-campionato/bltdebca56c3bd91419",
    },
    "la-liga": {
        "label": "Betfair España 2026/27 penalty guide",
        "url": "https://www.betfair.es/blog/futbol/futbol-espanol/laliga/quien-tira-los-penaltis-en-laliga-26-27-todo-lo-que-quieres-saber-120826-1377.html",
    },
    "bundesliga": {
        "label": "Bundesliga official summer 2026 transfer centre",
        "url": "https://www.bundesliga.com/en/bundesliga/news/official-bundesliga-transfer-centre-summer-2026-37051",
    },
    "ligue-1": {
        "label": "Ligue 1 official penalty and set-piece review",
        "url": "https://ligue1.com/fr/articles/l1_article_2916-",
    },
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_changes(write_files: bool) -> int:
    research = load(RESEARCH_PATH)
    audit = load(AUDIT_PATH)
    membership_sources = {
        (str(row.get("league")), str(row.get("club")), str(row.get("rank"))): str(row.get("source_url") or "")
        for row in audit.get("rows", [])
        if isinstance(row, dict)
    }
    audit_date = str(research["audit_date"])
    audit_time = f"{audit_date}T18:00:00Z"
    season = str(research["season"])
    by_league: dict[str, list[dict[str, Any]]] = {league: [] for league in LEAGUES}
    for row in research["changes"]:
        by_league[str(row["league"])].append(row)

    changed = 0
    for league in LEAGUES:
        path = DATA_DIR / f"{league}-penalty-takers.json"
        payload = load(path)
        for row in by_league[league]:
            club = str(row["club"])
            entry = payload[club]
            before = {rank: str(entry.get(rank) or "") for rank in ("primary", "secondary", "tertiary")}
            after = dict(zip(("primary", "secondary", "tertiary"), row["order"], strict=True))
            recorded_before = dict(
                zip(
                    ("primary", "secondary", "tertiary"),
                    row.get("before", list(before.values())),
                    strict=True,
                )
            )
            if before != after:
                changed += 1

            event_id = f"evt_{audit_date.replace('-', '')}_{slug(club)}_post_deadline"
            existing_events = [event for event in entry.get("evidence_log", []) if event.get("id") != event_id]
            role_source = ROLE_SOURCES[league]
            squad_url = membership_sources.get((league, club, "primary")) or "https://www.fotmob.com"
            existing_events.append(
                {
                    "id": event_id,
                    "date": audit_date,
                    "season": season,
                    "type": "post_deadline_roster_review",
                    "penalty_kind": None,
                    "competition": None,
                    "match": None,
                    "context": str(row["note"]),
                    "sources": [
                        {
                            "label": "FotMob current club squad",
                            "url": squad_url,
                            "date": audit_date,
                            "note": "Current squad membership checked after the transfer deadline.",
                        },
                        {
                            "label": role_source["label"],
                            "url": role_source["url"],
                            "date": audit_date,
                            "note": "Current role evidence cross-checked before reordering.",
                        },
                    ],
                    "detection": "manual_multi_source_research",
                    "review": {
                        "status": "approved",
                        "reviewed_by": "Il Margine",
                        "reviewed_at": audit_time,
                    },
                    "affects_hierarchy": True,
                    "editorial_note": "Post-deadline roster correction; uncertain depth remains explicitly provisional.",
                }
            )
            entry.update(after)
            entry["hierarchy_status"] = str(row["status"])
            entry["condition_note"] = str(row["note"])
            entry["last_updated"] = audit_date
            entry["last_verified"] = {
                "date": audit_date,
                "by": "Il Margine",
                "method": "multi_source_preseason_research",
            }
            entry["public_updated_at"] = audit_date
            entry["latest_evidence"] = {
                "id": event_id,
                "date": audit_date,
                "type": "post_deadline_roster_review",
                "source_count": 2,
            }
            entry["evidence_log"] = existing_events
            old_changes = [
                item
                for item in entry.get("change_log", [])
                if not (item.get("changed_at") == audit_date and item.get("change_type") == "post_deadline_roster_correction")
            ]
            old_changes.append(
                {
                    "changed_at": audit_date,
                    "season": season,
                    "change_type": "post_deadline_roster_correction",
                    "from": recorded_before,
                    "to": after,
                    "reason": str(row["note"]),
                    "evidence_ids": [event_id],
                    "detection": "manual_multi_source_research",
                    "approved_by": "Il Margine",
                    "approved_at": audit_time,
                    "article_slug": None,
                }
            )
            entry["change_log"] = old_changes
            flags = dict(entry.get("flags") or {})
            flags["carryover_from_previous_season"] = False
            flags["weak_evidence"] = row["status"] in {"conditional", "disputed", "unknown"}
            entry["flags"] = flags

        payload["_meta"]["last_verified"] = audit_date
        payload["_meta"]["public_updated_at"] = audit_date
        if write_files:
            write(path, payload)
    return changed


def refresh_membership(write_files: bool) -> int:
    audit = load(AUDIT_PATH)
    research = load(RESEARCH_PATH)
    audit_date = str(research["audit_date"])
    hierarchy_reviews = {(str(row["league"]), str(row["club"])) for row in research["changes"]}
    rows = audit.get("rows", [])
    failures = [row for row in rows if row.get("status") != "present"]
    if failures:
        labels = ", ".join(f"{row['league']}/{row['club']}/{row['player']}" for row in failures[:10])
        raise RuntimeError(f"Refusing membership refresh: {len(failures)} non-present rows: {labels}")
    indexed = {(row["league"], row["club"], row["rank"]): row for row in rows}

    refreshed = 0
    for league in LEAGUES:
        path = DATA_DIR / f"{league}-penalty-takers.json"
        payload = load(path)
        for club, entry in payload.items():
            if club.startswith("_") or not isinstance(entry, dict):
                continue
            membership: dict[str, dict[str, str]] = {}
            for rank in ("primary", "secondary", "tertiary"):
                row = indexed[(league, club, rank)]
                membership[rank] = {
                    "player": str(entry[rank]),
                    "status": "confirmed",
                    "source_url": str(row["source_url"]),
                    "checked_at": audit_date,
                }
                refreshed += 1
            entry["squad_membership"] = membership
            if (league, club) not in hierarchy_reviews:
                entry["last_verified"] = {
                    "date": audit_date,
                    "by": "Il Margine",
                    "method": "current_squad_membership_audit",
                }
            entry["public_updated_at"] = audit_date
        payload["_meta"]["last_verified"] = audit_date
        payload["_meta"]["public_updated_at"] = audit_date
        if write_files:
            write(path, payload)
    return refreshed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--refresh-membership", action="store_true")
    args = parser.parse_args()
    if args.refresh_membership:
        count = refresh_membership(args.write)
        print(f"membership rows {'updated' if args.write else 'checked'}: {count}")
    else:
        count = apply_changes(args.write)
        print(f"hierarchies {'updated' if args.write else 'checked'}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
