#!/usr/bin/env python3
"""Audit every published club penalty hierarchy against current FotMob squads."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

import requests

from goalscorer_penalty_utils import best_name_match


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "goalscorer" / "club-penalty-roster-audit.json"
TEAM_URL = "https://www.fotmob.com/api/data/teams"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.fotmob.com/",
}
HIERARCHY_FILES = {
    "epl": "epl-penalty-takers.json",
    "serie-a": "serie-a-penalty-takers.json",
    "la-liga": "la-liga-penalty-takers.json",
    "bundesliga": "bundesliga-penalty-takers.json",
    "ligue-1": "ligue-1-penalty-takers.json",
}
SLOTS = ("primary", "secondary", "tertiary")
ROSTER_NAME_ALIASES = {
    "Cucho Hernández": ("Juan Hernández",),
    "Junior Adamu": ("Chukwubuike Adamu",),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def squad_names(payload: dict) -> list[str]:
    groups = (payload.get("squad") or {}).get("squad") or []
    names: list[str] = []
    for group in groups:
        for member in group.get("members") or []:
            name = str(member.get("name") or member.get("fullName") or "").strip()
            if name:
                names.append(name)
    return names


def audit_team(*, league: str, team: str, entry: dict, names: Iterable[str], checked_at: str) -> list[dict]:
    candidates = [str(name).strip() for name in names if str(name).strip()]
    rows: list[dict] = []
    for slot in SLOTS:
        player = str(entry.get(slot) or "").strip()
        if not player or player.lower() in {"tbc", "not yet verified"}:
            continue
        matched = best_name_match(player, candidates)
        if not matched:
            matched = next(
                (
                    candidate
                    for alias in ROSTER_NAME_ALIASES.get(player, ())
                    if (candidate := best_name_match(alias, candidates))
                ),
                None,
            )
        if matched:
            continue
        rows.append(
            {
                "date": checked_at,
                "league": league,
                "review_source": "fotmob_roster_audit",
                "match": "Current squad check",
                "team": team,
                "opponent": "FotMob current squad",
                "actual_taker": player,
                "actual_role_pre_match": slot,
                "event_type": "roster_check",
                "event_result": "not listed in current squad",
                "primary_pre_match": str(entry.get("primary") or ""),
                "secondary_pre_match": str(entry.get("secondary") or ""),
                "tertiary_pre_match": str(entry.get("tertiary") or ""),
                "review_type": "roster_departure_check",
                "review_priority": "high" if slot == "primary" else "medium",
                "editorial_note": f"{player} is the filed {slot} but was not found in {team}'s current FotMob squad. Verify against an official transfer or squad source before editing the public hierarchy.",
                "roster_slot": slot,
                "squad_player_count": len(candidates),
            }
        )
    return rows


def fetch_team(team_id: int) -> dict:
    response = requests.get(
        TEAM_URL,
        params={"id": team_id, "ccode3": "GBR"},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def build_audit() -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    generated_at = now.isoformat().replace("+00:00", "Z")
    checked_at = now.date().isoformat()
    logo_map = load_json(ROOT / "data" / "goalscorer" / "team-logo-map.json")
    league_maps = logo_map.get("leagues") or {}
    rows: list[dict] = []
    failures: list[dict] = []
    checked_teams = 0
    checked_slots = 0

    for league, filename in HIERARCHY_FILES.items():
        hierarchy = load_json(ROOT / "data" / "goalscorer" / filename)
        team_map = ((league_maps.get(league) or {}).get("teams") or {})
        for team, entry in hierarchy.items():
            if team.startswith("_") or not isinstance(entry, dict):
                continue
            metadata = team_map.get(team) or {}
            team_id = int(metadata.get("fotmob_team_id") or 0)
            if not team_id:
                failures.append({"league": league, "team": team, "reason": "missing_fotmob_team_id"})
                continue
            try:
                payload = fetch_team(team_id)
                names = squad_names(payload)
                if not names:
                    raise ValueError("empty squad")
            except Exception as exc:  # noqa: BLE001 - failures belong in the report
                failures.append({"league": league, "team": team, "reason": str(exc)})
                continue
            checked_teams += 1
            checked_slots += sum(bool(str(entry.get(slot) or "").strip()) for slot in SLOTS)
            team_rows = audit_team(
                league=league,
                team=team,
                entry=entry,
                names=names,
                checked_at=checked_at,
            )
            for row in team_rows:
                row["source_url"] = f"https://www.fotmob.com/teams/{team_id}/overview"
            rows.extend(team_rows)

    rows.sort(key=lambda row: (row["league"], row["team"], SLOTS.index(row["roster_slot"])))
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "row_count": len(rows),
        "checked_teams": checked_teams,
        "checked_slots": checked_slots,
        "failure_count": len(failures),
        "failures": failures,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    payload = build_audit()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Roster audit: {payload['checked_teams']} teams, {payload['checked_slots']} slots, "
        f"{payload['row_count']} review rows, {payload['failure_count']} fetch failures"
    )
    print(f"Saved: {output}")
    return 1 if payload["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
