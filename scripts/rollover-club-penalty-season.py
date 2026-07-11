#!/usr/bin/env python3
"""Archive the prior club penalty season and create honest preseason files."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "goalscorer"
SEASON_PATH = DATA_DIR / "club-penalty-season.json"

LEAGUES = {
    "epl": {
        "label": "Premier League",
        "promoted": ["Coventry City", "Hull City", "Ipswich Town"],
        "relegated": ["Burnley", "West Ham", "Wolverhampton Wanderers"],
    },
    "serie-a": {
        "label": "Serie A",
        "promoted": ["Frosinone", "Monza", "Venezia"],
        "relegated": ["Cremonese", "Pisa", "Verona"],
    },
    "la-liga": {
        "label": "La Liga",
        "promoted": ["Deportivo La Coruna", "Malaga", "Racing Santander"],
        "relegated": ["Girona", "Mallorca", "Real Oviedo"],
    },
    "bundesliga": {
        "label": "Bundesliga",
        "promoted": ["SC Paderborn 07", "Schalke 04", "SV Elversberg"],
        "relegated": ["FC Heidenheim", "St. Pauli", "Wolfsburg"],
    },
    "ligue-1": {
        "label": "Ligue 1",
        "promoted": ["Le Mans", "Troyes"],
        "relegated": ["Metz", "Nantes"],
    },
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slug(value: str) -> str:
    normalized = value.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def carryover_entry(team: str, entry: dict, league: str, season: dict, rollover_date: str) -> dict:
    result = copy.deepcopy(entry)
    primary = str(result.get("primary") or "")
    secondary = str(result.get("secondary") or "")
    tertiary = str(result.get("tertiary") or "")
    previous_verified = str(result.get("last_updated") or "")
    event_id = f"evt_{rollover_date.replace('-', '')}_{slug(team).replace('-', '_')}_rollover"

    result.update(
        {
            "hierarchy_status": "probable" if primary else "unknown",
            "confidence": {
                "primary": "medium" if primary else "low",
                "secondary": "medium" if secondary else "low",
                "tertiary": "low",
            },
            "condition_note": "",
            "last_verified": {
                "date": previous_verified,
                "by": "Il Margine",
                "method": "prior_season_carryover",
            },
            "public_updated_at": rollover_date,
            "latest_evidence": None,
            "evidence_log": [
                {
                    "id": event_id,
                    "date": rollover_date,
                    "season": season["label"],
                    "type": "editorial_note",
                    "penalty_kind": None,
                    "competition": None,
                    "match": None,
                    "context": None,
                    "sources": [],
                    "detection": "manual",
                    "review": {
                        "status": "approved",
                        "reviewed_by": "Il Margine",
                        "reviewed_at": f"{rollover_date}T12:00:00Z",
                    },
                    "affects_hierarchy": False,
                    "editorial_note": (
                        f"The final {season['previous_label']} order is carried into {season['label']} "
                        "pending preseason re-verification."
                    ),
                }
            ],
            "change_log": [
                {
                    "changed_at": rollover_date,
                    "season": season["label"],
                    "change_type": "season_rollover",
                    "from": {"primary": primary, "secondary": secondary, "tertiary": tertiary},
                    "to": {"primary": primary, "secondary": secondary, "tertiary": tertiary},
                    "reason": (
                        f"Season rollover: {season['previous_label']} final order carried forward; "
                        "confidence reduced pending re-verification."
                    ),
                    "evidence_ids": [event_id],
                    "detection": "manual",
                    "approved_by": "Il Margine",
                    "approved_at": f"{rollover_date}T12:00:00Z",
                    "article_slug": None,
                }
            ],
            "flags": {
                "carryover_from_previous_season": True,
                "weak_evidence": True,
                "stale_override": None,
            },
            "prior_season": {
                "label": season["previous_label"],
                "primary": primary,
                "secondary": secondary,
                "tertiary": tertiary,
                "archive": (
                    f"data/goalscorer/archive/{season['previous_label'].replace('/', '-')}/"
                    f"{league}-penalty-takers.json"
                ),
            },
            "player_ids": result.get("player_ids", {}),
        }
    )
    return result


def promoted_entry(team: str, league: str, season: dict, rollover_date: str) -> dict:
    source = season.get("league_sources", {}).get(league, "")
    return {
        "primary": "",
        "secondary": "",
        "tertiary": "",
        "last_updated": rollover_date,
        "hierarchy_status": "unknown",
        "confidence": {"primary": "low", "secondary": "low", "tertiary": "low"},
        "condition_note": "Newly promoted club; the 2026/27 order is not yet verified.",
        "last_verified": {"date": rollover_date, "by": "Il Margine", "method": "league_membership_audit"},
        "public_updated_at": rollover_date,
        "latest_evidence": None,
        "evidence_log": [],
        "change_log": [],
        "flags": {"carryover_from_previous_season": False, "weak_evidence": True, "stale_override": None},
        "prior_season": None,
        "player_ids": {},
        "source": source,
        "cross_check": "Official 2026/27 league roster",
    }


def rollover(force: bool = False) -> None:
    season = read_json(SEASON_PATH)
    rollover_date = season["published_at"]
    archive_dir = DATA_DIR / "archive" / season["previous_label"].replace("/", "-")

    for league, config in LEAGUES.items():
        source_path = DATA_DIR / f"{league}-penalty-takers.json"
        current = read_json(source_path)
        current_meta = current.get("_meta", {})
        if current_meta.get("schema_version") == 2 and current_meta.get("season", {}).get("label") == season["label"]:
            print(f"SKIP {league}: already rolled over to {season['label']}")
            continue

        archive_path = archive_dir / source_path.name
        if archive_path.exists() and not force:
            raise RuntimeError(f"Archive already exists but current file is not rolled over: {archive_path}")
        write_json(archive_path, current)

        missing_relegated = [team for team in config["relegated"] if team not in current]
        if missing_relegated:
            raise RuntimeError(f"{league}: relegated clubs missing from prior file: {missing_relegated}")

        active = {
            team: carryover_entry(team, entry, league, season, rollover_date)
            for team, entry in current.items()
            if not team.startswith("_") and team not in config["relegated"]
        }
        for team in config["promoted"]:
            active[team] = promoted_entry(team, league, season, rollover_date)

        expected = 18 if league in {"bundesliga", "ligue-1"} else 20
        if len(active) != expected:
            raise RuntimeError(f"{league}: expected {expected} active clubs, found {len(active)}")

        payload = {
            "_meta": {
                "schema_version": 2,
                "league": {"key": league, "name": config["label"]},
                "season": {"label": season["label"], "status": season["status"]},
                "relegated": [
                    {"team": team, "archived_slug": slug(team), "archive": str(archive_path.relative_to(ROOT)).replace("\\", "/")}
                    for team in config["relegated"]
                ],
                "promoted": list(config["promoted"]),
                "last_verified": rollover_date,
                "public_updated_at": rollover_date,
                "membership_source": season.get("league_sources", {}).get(league, ""),
            },
            **dict(sorted(active.items())),
        }
        write_json(source_path, payload)
        print(f"ROLLED {league}: {len(active)} active, {len(config['relegated'])} archived")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing archive")
    args = parser.parse_args()
    rollover(force=args.force)


if __name__ == "__main__":
    main()
