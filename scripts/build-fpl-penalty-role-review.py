#!/usr/bin/env python3
"""Build an internal, non-authoritative EPL penalty-role review queue.

The official FPL role fields are useful evidence, but they are not allowed to
rewrite the public hierarchy. This script compares the current FPL roster and
penalty order with Il Margine's registered 2026/27 hierarchy and emits review
tickets for a human decision.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROLES = ROOT / "data" / "assist-value" / "fpl-setpiece-roles.csv"
DEFAULT_ROSTER = ROOT / "data" / "assist-value" / "fpl-player-roster.csv"
DEFAULT_HIERARCHY = ROOT / "data" / "goalscorer" / "epl-penalty-takers.json"
DEFAULT_JSON = ROOT / "data" / "goalscorer" / "epl-preseason-penalty-role-review.json"
DEFAULT_CSV = ROOT / "data" / "goalscorer" / "epl-preseason-penalty-role-review.csv"
SOURCE_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

TEAM_ALIASES = {
    "man city": "Manchester City",
    "man utd": "Manchester United",
    "newcastle": "Newcastle United",
    "nott'm forest": "Nottingham Forest",
    "spurs": "Tottenham",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def normalize(value: Any) -> str:
    text = str(value or "").casefold().translate(str.maketrans({"ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th"}))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def canonical_team(value: Any) -> str:
    raw = str(value or "").strip()
    return TEAM_ALIASES.get(raw.casefold(), raw)


def names_match(expected: Any, *, player_name: Any, web_name: Any = "") -> bool:
    target = normalize(expected)
    full = normalize(player_name)
    web = normalize(web_name)
    if not target or not full:
        return False
    if target == full:
        return True
    target_tokens = target.split()
    full_tokens = full.split()
    if web and (target == web or (target_tokens and target_tokens[-1] == web)):
        return True
    # FPL can include additional legal-name tokens after the familiar name,
    # e.g. "Bruno Guimaraes" vs "Bruno Guimaraes Rodriguez Moura".
    if len(target_tokens) >= 2 and all(token in full_tokens for token in target_tokens):
        return True
    return bool(target_tokens and full_tokens and target_tokens[-1] == full_tokens[-1])


def parse_order(value: Any) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() and int(text) > 0 else None


def slug(value: str) -> str:
    return normalize(value).replace(" ", "-")


def hierarchy_names(entry: dict[str, Any]) -> dict[str, str]:
    return {
        "primary": str(entry.get("primary") or "").strip(),
        "secondary": str(entry.get("secondary") or "").strip(),
        "tertiary": str(entry.get("tertiary") or "").strip(),
    }


def build_review_rows(
    hierarchy: dict[str, Any],
    role_rows: list[dict[str, str]],
    roster_rows: list[dict[str, str]],
    *,
    generated_at: str,
) -> tuple[list[dict[str, Any]], str]:
    meta = hierarchy.get("_meta") if isinstance(hierarchy.get("_meta"), dict) else {}
    season_meta = meta.get("season") if isinstance(meta.get("season"), dict) else {}
    season = str(season_meta.get("label") or "2026/27")

    roles_by_team: dict[str, list[dict[str, str]]] = {}
    roster_by_team: dict[str, list[dict[str, str]]] = {}
    for row in role_rows:
        team = canonical_team(row.get("team"))
        if parse_order(row.get("penalty_order")) is not None:
            roles_by_team.setdefault(team, []).append(row)
    for row in roster_rows:
        roster_by_team.setdefault(canonical_team(row.get("team")), []).append(row)

    output: list[dict[str, Any]] = []
    for team, raw_entry in hierarchy.items():
        if team == "_meta" or not isinstance(raw_entry, dict):
            continue
        current = hierarchy_names(raw_entry)
        roster = roster_by_team.get(team, [])
        ordered = sorted(
            roles_by_team.get(team, []),
            key=lambda row: (parse_order(row.get("penalty_order")) or 999, normalize(row.get("player_name"))),
        )
        fpl_order = [
            {
                "order": parse_order(row.get("penalty_order")),
                "player": str(row.get("player_name") or row.get("web_name") or "").strip(),
                "web_name": str(row.get("web_name") or row.get("player_name") or "").strip(),
                "element_id": str(row.get("element_id") or "").strip(),
                "status": str(row.get("status") or "").strip(),
            }
            for row in ordered
        ]
        fpl_first = fpl_order[0] if fpl_order else None
        primary_present = any(
            names_match(current["primary"], player_name=row.get("player_name"), web_name=row.get("web_name"))
            for row in roster
        ) if current["primary"] else False
        fpl_first_matches = bool(
            fpl_first
            and names_match(
                current["primary"],
                player_name=fpl_first.get("player"),
                web_name=fpl_first.get("web_name"),
            )
        )

        review_type = ""
        priority = ""
        reason = ""
        if not current["primary"]:
            review_type = "unknown_hierarchy"
            priority = "high"
            reason = "Our 2026/27 hierarchy has no primary taker, while the official FPL source has a ranked order."
        elif roster and not primary_present:
            review_type = "primary_not_in_current_roster"
            priority = "high"
            reason = "Our current primary is absent from the official FPL 2026/27 squad roster."
        elif fpl_first and not fpl_first_matches:
            review_type = "official_order_conflict"
            priority = "medium"
            reason = "The official FPL first penalty order differs from our current primary."
        elif not roster:
            review_type = "missing_team_roster"
            priority = "high"
            reason = "The source snapshot contains no roster for this registered Premier League club."

        if not review_type:
            continue
        proposed_primary = str((fpl_first or {}).get("player") or "").strip()
        order_label = ", ".join(f"{item['order']}. {item['player']}" for item in fpl_order) or "no ranked order"
        output.append(
            {
                "row_id": f"fpl-role|epl|{season}|{slug(team)}",
                "generated_at": generated_at,
                "season": season,
                "league": "epl",
                "team": team,
                "review_source": "official_fpl_role_fields",
                "review_priority": priority,
                "review_type": review_type,
                "current_primary": current["primary"],
                "current_secondary": current["secondary"],
                "current_tertiary": current["tertiary"],
                "proposed_primary": proposed_primary,
                "fpl_penalty_order": fpl_order,
                "current_primary_in_fpl_roster": primary_present,
                "reason": reason,
                "editorial_note": (
                    f"{reason} Current order: {current['primary'] or 'unknown'} / "
                    f"{current['secondary'] or 'unknown'}. FPL reference: "
                    f"{order_label}. "
                    "Review squad status and direct match evidence before applying any hierarchy change."
                ),
                "source_url": SOURCE_URL,
                "public_source_link": False,
                "auto_apply": False,
                "status": "active",
            }
        )
    output.sort(key=lambda row: (0 if row["review_priority"] == "high" else 1, row["team"]))
    return output, season


def flatten_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    next_row = dict(row)
    next_row["fpl_penalty_order"] = " | ".join(
        f"{item.get('order')}. {item.get('player')}" for item in row.get("fpl_penalty_order") or []
    )
    return next_row


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flattened = [flatten_for_csv(row) for row in rows]
    fieldnames = sorted({key for row in flattened for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(flattened)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roles", type=Path, default=DEFAULT_ROLES)
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    parser.add_argument("--hierarchy", type=Path, default=DEFAULT_HIERARCHY)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    hierarchy = json.loads(args.hierarchy.read_text(encoding="utf-8"))
    generated_at = utc_now()
    rows, season = build_review_rows(
        hierarchy,
        read_csv(args.roles),
        read_csv(args.roster),
        generated_at=generated_at,
    )
    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "league": "epl",
        "season": season,
        "source": {
            "name": "official_fpl_role_fields",
            "url": SOURCE_URL,
            "public_source_link": False,
        },
        "mode": "internal_evidence_only",
        "auto_apply": False,
        "row_count": len(rows),
        "rows": rows,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(args.csv_output, rows)
    print(f"FPL penalty-role review: {len(rows)} active ticket(s) -> {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
