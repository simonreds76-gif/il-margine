#!/usr/bin/env python3
"""Validate the club penalty data, routing inputs and season rollover."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from goalscorer_penalty_utils import load_penalty_hierarchy


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "goalscorer"
LEAGUES = {
    "epl": {"count": 20, "promoted": {"Coventry City", "Hull City", "Ipswich Town"}, "relegated": {"Burnley", "West Ham", "Wolverhampton Wanderers"}},
    "serie-a": {"count": 20, "promoted": {"Frosinone", "Monza", "Venezia"}, "relegated": {"Cremonese", "Pisa", "Verona"}},
    "la-liga": {"count": 20, "promoted": {"Deportivo La Coruna", "Malaga", "Racing Santander"}, "relegated": {"Girona", "Mallorca", "Real Oviedo"}},
    "bundesliga": {"count": 18, "promoted": {"SC Paderborn 07", "Schalke 04", "SV Elversberg"}, "relegated": {"FC Heidenheim", "St. Pauli", "Wolfsburg"}},
    "ligue-1": {"count": 18, "promoted": {"Le Mans", "Troyes"}, "relegated": {"Metz", "Nantes"}},
}
BAD_TEXT = re.compile(r"(?:Ã.|Â.|â.|�)")


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AssertionError(f"Invalid JSON: {path.relative_to(ROOT)}: {exc}") from exc


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def main() -> int:
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    season = load(DATA / "club-penalty-season.json")
    logo_manifest = load(DATA / "team-logo-map.json")
    check(season.get("label") == "2026/27", "Season config must publish 2026/27")
    check(season.get("status") == "preseason", "Season must remain preseason until league kickoff")
    check(season.get("league_start_dates", {}).get("epl") == "2026-08-21", "Premier League start date must match the released fixture list")
    check(all(str(url).startswith("https://") for url in season.get("league_sources", {}).values()), "League membership sources must be HTTPS URLs")
    archive_dir = DATA / "archive" / str(season.get("previous_label", "")).replace("/", "-")

    all_urls: set[str] = set()
    for league, expected in LEAGUES.items():
        current_path = DATA / f"{league}-penalty-takers.json"
        archive_path = archive_dir / current_path.name
        current = load(current_path)
        archive = load(archive_path)
        meta = current.get("_meta", {})
        teams = {key: value for key, value in current.items() if not key.startswith("_")}

        check(meta.get("schema_version") == 2, f"{league}: schema_version must be 2")
        check(meta.get("season", {}).get("label") == season["label"], f"{league}: season mismatch")
        check(meta.get("last_verified") == "2026-07-27", f"{league}: audit verification date is stale")
        check(meta.get("public_updated_at") == "2026-07-27", f"{league}: public update date is stale")
        check(len(teams) == expected["count"], f"{league}: expected {expected['count']} active teams, found {len(teams)}")
        check(expected["promoted"].issubset(teams), f"{league}: promoted teams missing")
        check(expected["relegated"].isdisjoint(teams), f"{league}: relegated teams still active")
        check(expected["relegated"].issubset(archive), f"{league}: relegated teams missing from archive")
        loaded_hierarchy = load_penalty_hierarchy(current_path)
        check(len(loaded_hierarchy) == expected["count"], f"{league}: shared hierarchy loader returned {len(loaded_hierarchy)} teams")

        meta_relegated = {row.get("team") for row in meta.get("relegated", [])}
        check(meta_relegated == expected["relegated"], f"{league}: _meta.relegated mismatch")

        for team, entry in teams.items():
            check(isinstance(entry, dict), f"{league}/{team}: entry must be an object")
            for field in ("primary", "secondary", "tertiary", "last_updated"):
                check(field in entry, f"{league}/{team}: missing {field}")
            check(entry.get("hierarchy_status") in {"confirmed", "probable", "conditional", "disputed", "unknown"}, f"{league}/{team}: invalid hierarchy_status")
            is_researched = entry.get("last_verified", {}).get("method") == "multi_source_preseason_research"
            research_events = [
                event
                for event in entry.get("evidence_log", [])
                if event.get("detection") == "manual_multi_source_research"
                and event.get("review", {}).get("status") == "approved"
            ]
            check(is_researched, f"{league}/{team}: multi-source preseason verification missing")
            check(bool(research_events), f"{league}/{team}: approved research evidence missing")
            if research_events:
                source_urls = [
                    source.get("url")
                    for event in research_events
                    for source in event.get("sources", [])
                    if source.get("url")
                ]
                check(bool(source_urls), f"{league}/{team}: research event has no source URLs")
                check(all(str(url).startswith("https://") for url in source_urls), f"{league}/{team}: research source URL must be HTTPS")
            has_named_primary = bool(str(entry.get("primary") or "").strip())
            has_explicit_unresolved_state = (
                entry.get("hierarchy_status") in {"unknown", "disputed"}
                and bool(str(entry.get("condition_note") or "").strip())
            )
            check(
                has_named_primary or has_explicit_unresolved_state,
                f"{league}/{team}: needs a named primary or an explicit unresolved state",
            )
            check(
                entry.get("flags", {}).get("carryover_from_previous_season") is False,
                f"{league}/{team}: researched hierarchy must not remain labelled as carryover",
            )
            if team in expected["promoted"]:
                check(
                    is_researched and (has_named_primary or has_explicit_unresolved_state),
                    f"{league}/{team}: promoted team needs researched evidence or an explicit unresolved state",
                )

            url = f"/penalty-takers/{league}/{slug(team)}"
            check(url not in all_urls, f"Duplicate team URL: {url}")
            all_urls.add(url)

            logo_entry = (
                logo_manifest.get("leagues", {})
                .get(league, {})
                .get("teams", {})
                .get(team, {})
            )
            logo_path = str(logo_entry.get("logo_path") or "")
            check(bool(logo_path), f"{league}/{team}: active club crest missing from manifest")
            if logo_path:
                crest_file = ROOT / "public" / logo_path.lstrip("/")
                check(crest_file.exists(), f"{league}/{team}: crest file missing: {logo_path}")
                if crest_file.exists():
                    check(crest_file.stat().st_size > 512, f"{league}/{team}: crest file is unexpectedly small")
                    check(crest_file.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"{league}/{team}: crest is not a PNG")

        raw = current_path.read_text(encoding="utf-8")
        check(not BAD_TEXT.search(raw), f"{league}: mojibake detected")

    source_checks = {
        ROOT / "src" / "lib" / "club-penalty-takers.ts": ["club-penalty-season.json"],
        ROOT / "src" / "app" / "penalty-takers" / "page.tsx": ["CLUB_PENALTY_SEASON"],
        ROOT / "src" / "app" / "penalty-takers" / "[leagueSlug]" / "page.tsx": ["generateStaticParams", "archivedTeams"],
        ROOT / "src" / "app" / "penalty-takers" / "methodology" / "page.tsx": ["Absence is not a promotion", "Shootouts are supporting evidence"],
        ROOT / "src" / "app" / "sitemap.ts": ["CLUB_LEAGUES", "/penalty-takers/methodology"],
        ROOT / ".github" / "workflows" / "club-penalty-weekly-evidence.yml": [
            'cron: "20 6 * * 1"',
            "goalscorer-live-penalty-review.py",
            "Public hierarchies are unchanged until editorial approval.",
        ],
    }
    for path, needles in source_checks.items():
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            check(needle in text, f"{path.relative_to(ROOT)} missing {needle}")

    for path in (
        ROOT / "src" / "app" / "penalty-takers" / "page.tsx",
        ROOT / "src" / "app" / "penalty-takers" / "opengraph-image.tsx",
        ROOT / "src" / "app" / "resources" / "page.tsx",
    ):
        check("2025/26" not in path.read_text(encoding="utf-8"), f"Stale season label in {path.relative_to(ROOT)}")

    team_page = (ROOT / "src" / "app" / "penalty-takers" / "[leagueSlug]" / "[teamSlug]" / "page.tsx").read_text(encoding="utf-8")
    check("/penalty-takers#" not in team_page, "Team pages still link league anchors instead of league hubs")
    check("${team.absoluteUrl}/opengraph-image" in team_page, "Team pages must use their own social image")

    workflow_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / ".github" / "workflows").glob("*.yml"))
    for league in LEAGUES:
        check(f"data/goalscorer/{league}-penalty-takers.json" not in workflow_text, f"{league}: workflow must not auto-publish hierarchy JSON")

    if errors:
        print("CLUB_PENALTY_VALIDATION_FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"CLUB_PENALTY_VALIDATION_OK active_urls={len(all_urls)} season={season['label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
