#!/usr/bin/env python3
"""Apply verified departures without inventing replacement penalty takers."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "goalscorer" / "confirmed-penalty-departures-2026-09-01.json"
FILES = {
    "epl": "epl-penalty-takers.json",
    "serie-a": "serie-a-penalty-takers.json",
    "la-liga": "la-liga-penalty-takers.json",
    "bundesliga": "bundesliga-penalty-takers.json",
    "ligue-1": "ligue-1-penalty-takers.json",
}
SLOTS = ("primary", "secondary", "tertiary")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ledger = load(LEDGER)
    verified_at = str(ledger["verified_at"])
    by_league: dict[str, list[dict]] = {}
    for row in ledger["entries"]:
        by_league.setdefault(row["league"], []).append(row)
    retained_by_league: dict[str, list[dict]] = {}
    for row in ledger.get("retained") or []:
        retained_by_league.setdefault(row["league"], []).append(row)

    updated = 0
    for league, filename in FILES.items():
        path = ROOT / "data" / "goalscorer" / filename
        payload = load(path)
        meta = payload.get("_meta") or {}
        meta["last_verified"] = verified_at
        meta["public_updated_at"] = verified_at
        if isinstance(meta.get("season"), dict):
            meta["season"]["status"] = "live"

        for change in by_league.get(league, []):
            team = change["team"]
            entry = payload[team]
            old_order = [str(entry.get(slot) or "").strip() for slot in SLOTS]
            new_order = [str(player).strip() for player in change["new_order"]]
            if any(player not in old_order for player in new_order):
                raise ValueError(f"{league}/{team}: new order must only promote existing names")
            departed = [str(player).strip() for player in change["departed"]]
            slot_departures = [player for player in departed if player in old_order]
            already_applied = [player for player in old_order if player] == new_order
            if not slot_departures and not already_applied:
                raise ValueError(f"{league}/{team}: no departed hierarchy player found")

            slug = re.sub(r"[^a-z0-9]+", "-", team.lower()).strip("-")
            event_id = f"evt_20260901_{slug}_departure"
            previous_change = next(
                (
                    row
                    for row in entry.get("change_log") or []
                    if event_id in (row.get("evidence_ids") or [])
                ),
                None,
            )
            previous = (previous_change or {}).get("from") or dict(zip(SLOTS, old_order))
            padded = (new_order + ["", "", ""])[:3]
            for slot, player in zip(SLOTS, padded):
                entry[slot] = player

            remaining_label = " then ".join(new_order)
            entry["condition_note"] = change.get("public_note") or (
                f"The hierarchy was reset after confirmed squad departures. The current filed order is {remaining_label}. "
                "Any unfilled backup position remains under review until direct 2026/27 club evidence identifies a replacement."
            )
            entry["hierarchy_status"] = "disputed" if team == "Juventus" else "conditional"
            entry["last_updated"] = verified_at
            entry["last_verified"] = {
                "date": verified_at,
                "by": "Il Margine",
                "method": "confirmed_departure_roster_review",
            }
            entry["public_updated_at"] = verified_at

            sources = [change["source"], *(change.get("additional_sources") or [])]
            event = {
                "id": event_id,
                "date": verified_at,
                "season": "2026/27",
                "type": "roster_integrity_review",
                "penalty_kind": None,
                "competition": None,
                "match": None,
                "headline": "Penalty order reset after squad change",
                "context": entry["condition_note"],
                "sources": [
                    {
                        **source,
                        "note": f"Confirmed squad departure relevant to the {team} penalty hierarchy.",
                    }
                    for source in sources
                ],
                "detection": "automated_roster_audit_manual_verification",
                "review": {
                    "status": "approved",
                    "reviewed_by": "Il Margine",
                    "reviewed_at": "2026-09-01T12:00:00Z",
                },
                "affects_hierarchy": True,
                "editorial_note": entry["condition_note"],
            }
            evidence_log = entry.setdefault("evidence_log", [])
            entry["evidence_log"] = [row for row in evidence_log if row.get("id") != event_id]
            entry["evidence_log"].append(event)
            entry["latest_evidence"] = {
                "id": event_id,
                "date": verified_at,
                "type": "roster_integrity_review",
                "source_count": len(sources),
            }
            change_log = entry.setdefault("change_log", [])
            entry["change_log"] = [row for row in change_log if event_id not in (row.get("evidence_ids") or [])]
            entry["change_log"].append(
                {
                    "changed_at": verified_at,
                    "season": "2026/27",
                    "change_type": "confirmed_departure_reorder",
                    "from": previous,
                    "to": dict(zip(SLOTS, padded)),
                    "reason": entry["condition_note"],
                    "evidence_ids": [event_id],
                    "detection": "automated_roster_audit_manual_verification",
                    "approved_by": "Il Margine",
                    "approved_at": "2026-09-01T12:00:00Z",
                    "article_slug": None,
                }
            )
            membership = entry.get("squad_membership") or {}
            entry["squad_membership"] = {
                slot: {**membership.get(slot, {}), "player": player, "status": "confirmed", "checked_at": verified_at}
                for slot, player in zip(SLOTS, padded)
                if player
            }
            flags = entry.get("flags") or {}
            flags["carryover_from_previous_season"] = False
            flags["weak_evidence"] = True
            entry["flags"] = flags
            updated += 1

        for review in retained_by_league.get(league, []):
            team = review["team"]
            entry = payload[team]
            slug = re.sub(r"[^a-z0-9]+", "-", team.lower()).strip("-")
            event_id = f"evt_20260901_{slug}_retained"
            public_note = str(review["public_note"]).strip()
            entry["condition_note"] = public_note
            entry["hierarchy_status"] = review.get("hierarchy_status") or entry.get("hierarchy_status") or "probable"
            entry["last_updated"] = verified_at
            entry["last_verified"] = {
                "date": verified_at,
                "by": "Il Margine",
                "method": "current_roster_and_penalty_record_review",
            }
            entry["public_updated_at"] = verified_at
            event = {
                "id": event_id,
                "date": verified_at,
                "season": "2026/27",
                "type": "roster_integrity_review",
                "penalty_kind": None,
                "competition": None,
                "match": None,
                "headline": "Current penalty order re-verified",
                "context": public_note,
                "sources": [
                    {
                        **source,
                        "note": f"Current squad and penalty-duty evidence reviewed for {team}.",
                    }
                    for source in review.get("sources") or []
                ],
                "detection": "manual_current_roster_review",
                "review": {
                    "status": "approved",
                    "reviewed_by": "Il Margine",
                    "reviewed_at": "2026-09-01T12:00:00Z",
                },
                "affects_hierarchy": False,
                "editorial_note": public_note,
            }
            evidence_log = entry.setdefault("evidence_log", [])
            entry["evidence_log"] = [row for row in evidence_log if row.get("id") != event_id]
            entry["evidence_log"].append(event)
            entry["latest_evidence"] = {
                "id": event_id,
                "date": verified_at,
                "type": "roster_integrity_review",
                "source_count": len(event["sources"]),
            }
            membership = entry.get("squad_membership") or {}
            entry["squad_membership"] = {
                slot: {**membership.get(slot, {}), "player": str(entry.get(slot) or ""), "status": "confirmed", "checked_at": verified_at}
                for slot in SLOTS
                if str(entry.get(slot) or "").strip()
            }
            flags = entry.get("flags") or {}
            flags["carryover_from_previous_season"] = False
            entry["flags"] = flags
            updated += 1

        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Applied {updated} confirmed departure corrections.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
