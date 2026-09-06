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
AGENT_AUDIT_PATTERN = re.compile(
    r"agent-(?:epl|serie-a|la-liga|bundesliga|ligue-1)-hierarchy-audit-(\d{4}-\d{2}-\d{2})\.json$"
)
CURRENT_REVIEW_PATTERN = re.compile(r"club-penalty-current-review-(\d{4}-\d{2}-\d{2})\.json$")
POSITIONS = ("primary", "secondary", "tertiary")
UNVERIFIED_TAKER_VALUES = {"", "tbc", "tbd", "n/a", "-", "unknown", "not yet verified"}


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AssertionError(f"Invalid JSON: {path.relative_to(ROOT)}: {exc}") from exc


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def date_is_current_or_newer(value: object, baseline: str) -> bool:
    """Allow targeted editorial updates after the latest full-league audit."""
    candidate = str(value or "").strip()
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate)) and candidate >= baseline


def latest_agent_audit_dates() -> dict[str, str]:
    dates_by_league: dict[str, str] = {}
    research_dir = DATA / "research"
    for league in LEAGUES:
        dates = []
        for path in research_dir.glob(f"agent-{league}-hierarchy-audit-*.json"):
            match = AGENT_AUDIT_PATTERN.fullmatch(path.name)
            if match:
                dates.append(match.group(1))
        if not dates:
            raise AssertionError(f"{league}: no agent hierarchy audit found")
        dates_by_league[league] = max(dates)
    return dates_by_league


def latest_current_review() -> tuple[str, dict]:
    candidates: list[tuple[str, Path]] = []
    for path in (DATA / "research").glob("club-penalty-current-review-*.json"):
        match = CURRENT_REVIEW_PATTERN.fullmatch(path.name)
        if match:
            candidates.append((match.group(1), path))
    if not candidates:
        raise AssertionError("No current-season all-club review found")
    review_date, path = max(candidates)
    return review_date, load(path)


def main() -> int:
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    season = load(DATA / "club-penalty-season.json")
    logo_manifest = load(DATA / "team-logo-map.json")
    audit_dates = latest_agent_audit_dates()
    current_review_date, current_review = latest_current_review()
    check(
        current_review.get("summary", {}).get("reviewed_clubs") == sum(row["count"] for row in LEAGUES.values()),
        "Current-season review must cover every active club",
    )
    check(season.get("label") == "2026/27", "Season config must publish 2026/27")
    check(season.get("status") == "preseason", "Season must remain preseason until league kickoff")
    check(season.get("league_start_dates", {}).get("epl") == "2026-08-21", "Premier League start date must match the released fixture list")
    check(all(str(url).startswith("https://") for url in season.get("league_sources", {}).values()), "League membership sources must be HTTPS URLs")
    archive_dir = DATA / "archive" / str(season.get("previous_label", "")).replace("/", "-")

    all_urls: set[str] = set()
    for league, expected in LEAGUES.items():
        audit_date = audit_dates[league]
        current_path = DATA / f"{league}-penalty-takers.json"
        archive_path = archive_dir / current_path.name
        current = load(current_path)
        archive = load(archive_path)
        meta = current.get("_meta", {})
        teams = {key: value for key, value in current.items() if not key.startswith("_")}

        check(meta.get("schema_version") == 2, f"{league}: schema_version must be 2")
        check(meta.get("season", {}).get("label") == season["label"], f"{league}: season mismatch")
        check(
            date_is_current_or_newer(meta.get("last_verified"), audit_date),
            f"{league}: audit verification date predates the latest full-league audit",
        )
        check(
            date_is_current_or_newer(meta.get("public_updated_at"), audit_date),
            f"{league}: public update date predates the latest full-league audit",
        )
        check(
            date_is_current_or_newer(meta.get("last_reviewed"), current_review_date),
            f"{league}: board review predates the latest current-season review",
        )
        reviewed_clubs = set(current_review.get("leagues", {}).get(league, {}).get("reviewed_clubs", []))
        check(reviewed_clubs == set(teams), f"{league}: current-season review coverage mismatch")
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
            verification_method = entry.get("last_verified", {}).get("method")
            is_researched = verification_method in {
                "multi_source_preseason_research",
                "reviewed_live_penalty_event",
                "reviewed_manual_hierarchy_override",
                "confirmed_departure_roster_review",
                "current_roster_and_penalty_record_review",
                "current_squad_membership_audit",
            }
            research_events = [
                event
                for event in entry.get("evidence_log", [])
                if event.get("detection") == "manual_multi_source_research"
                and event.get("review", {}).get("status") == "approved"
            ]
            roster_events = [
                event
                for event in entry.get("evidence_log", [])
                if event.get("type") == "roster_integrity_review"
                and event.get("review", {}).get("status") == "approved"
            ]
            documented_vacancy = (
                bool(roster_events)
                and entry.get("hierarchy_status") in {"conditional", "disputed"}
                and "under review" in str(entry.get("condition_note") or "").lower()
            )
            check(is_researched, f"{league}/{team}: multi-source preseason verification missing")
            check(bool(research_events), f"{league}/{team}: approved research evidence missing")
            last_reviewed = entry.get("last_reviewed") if isinstance(entry.get("last_reviewed"), dict) else {}
            check(
                date_is_current_or_newer(last_reviewed.get("date"), current_review_date),
                f"{league}/{team}: current-season review is stale",
            )
            check(
                last_reviewed.get("method") == "current_season_multi_source_review",
                f"{league}/{team}: current-season review method missing",
            )
            check(
                len(last_reviewed.get("sources") or []) >= 2,
                f"{league}/{team}: current-season review needs two sources",
            )
            evidence_ids = {
                str(event.get("id") or "").strip()
                for event in entry.get("evidence_log", [])
                if isinstance(event, dict) and str(event.get("id") or "").strip()
            }
            for change in entry.get("change_log", []):
                referenced_ids = change.get("evidence_ids") if isinstance(change, dict) else None
                check(
                    isinstance(referenced_ids, list) and bool(referenced_ids),
                    f"{league}/{team}: change log entry has no evidence references",
                )
                if isinstance(referenced_ids, list):
                    check(
                        all(str(evidence_id) in evidence_ids for evidence_id in referenced_ids),
                        f"{league}/{team}: change log contains dangling evidence references",
                    )
            if research_events:
                source_urls = [
                    source.get("url")
                    for event in research_events
                    for source in event.get("sources", [])
                    if source.get("url")
                ]
                check(len(source_urls) >= 2, f"{league}/{team}: research event needs at least two source URLs")
                check(all(str(url).startswith("https://") for url in source_urls), f"{league}/{team}: research source URL must be HTTPS")
            for position in POSITIONS:
                player = str(entry.get(position) or "").strip()
                check(
                    bool(player) or documented_vacancy,
                    f"{league}/{team}: {position} candidate must be named; express uncertainty in status/note",
                )
                check(
                    player.lower() not in UNVERIFIED_TAKER_VALUES or not player,
                    f"{league}/{team}: {position} uses an unverified sentinel as a player name",
                )
                if not player:
                    check(
                        (entry.get("confidence") or {}).get(position) is None,
                        f"{league}/{team}: blank {position} slot must not carry confidence",
                    )
            check(
                bool(str(entry.get("secondary") or "").strip()) or not str(entry.get("tertiary") or "").strip(),
                f"{league}/{team}: tertiary cannot be filed while secondary is blank",
            )
            hierarchy_names = {
                re.sub(r"[^a-z0-9]+", " ", str(entry.get(position) or "").lower()).strip()
                for position in ("primary", "secondary", "tertiary")
                if str(entry.get(position) or "").strip()
            }
            check(
                len(hierarchy_names) == sum(bool(str(entry.get(position) or "").strip()) for position in POSITIONS),
                f"{league}/{team}: primary, secondary and tertiary must be distinct players",
            )
            unavailable_candidates = entry.get("unavailable_candidates") or []
            check(
                isinstance(unavailable_candidates, list),
                f"{league}/{team}: unavailable_candidates must be a list",
            )
            if isinstance(unavailable_candidates, list):
                for unavailable in unavailable_candidates:
                    check(
                        isinstance(unavailable, dict),
                        f"{league}/{team}: invalid unavailable candidate record",
                    )
                    if not isinstance(unavailable, dict):
                        continue
                    unavailable_player = str(unavailable.get("player") or "").strip()
                    check(bool(unavailable_player), f"{league}/{team}: unavailable candidate has no player")
                    check(
                        normalize_name(unavailable_player) not in {normalize_name(name) for name in hierarchy_names},
                        f"{league}/{team}/{unavailable_player}: unavailable player remains in the active hierarchy",
                    )
                    check(
                        str(unavailable.get("source_url") or "").startswith("https://"),
                        f"{league}/{team}/{unavailable_player}: unavailable status needs an HTTPS source",
                    )
                    check(
                        date_is_current_or_newer(unavailable.get("checked_at"), current_review_date),
                        f"{league}/{team}/{unavailable_player}: unavailable status predates the latest review",
                    )
            check(
                entry.get("flags", {}).get("carryover_from_previous_season") is False,
                f"{league}/{team}: researched hierarchy must not remain labelled as carryover",
            )
            squad_membership = entry.get("squad_membership")
            check(isinstance(squad_membership, dict), f"{league}/{team}: current-squad verification missing")
            if isinstance(squad_membership, dict):
                for position in POSITIONS:
                    player = str(entry.get(position) or "").strip()
                    if not player and documented_vacancy:
                        continue
                    membership = squad_membership.get(position)
                    check(isinstance(membership, dict), f"{league}/{team}/{player}: {position} squad verification missing")
                    if not isinstance(membership, dict):
                        continue
                    check(
                        normalize_name(str(membership.get("player") or "")) == normalize_name(player),
                        f"{league}/{team}/{position}: squad verification player mismatch",
                    )
                    check(
                        str(membership.get("status") or "").lower() == "confirmed",
                        f"{league}/{team}/{player}: player is not confirmed in the current 2026/27 squad",
                    )
                    check(
                        str(membership.get("source_url") or "").startswith("https://"),
                        f"{league}/{team}/{player}: squad verification source must be HTTPS",
                    )
                    check(
                        date_is_current_or_newer(membership.get("checked_at"), current_review_date),
                        f"{league}/{team}/{player}: squad verification predates the latest current-season review",
                    )
            if team in expected["promoted"]:
                check(
                    is_researched and (
                        all(bool(str(entry.get(position) or "").strip()) for position in POSITIONS)
                        or documented_vacancy
                    ),
                    f"{league}/{team}: promoted team needs three researched candidates",
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
        ROOT / "src" / "lib" / "club-penalty-takers.ts": [
            "club-penalty-season.json",
            "isVerifiedTaker",
            "hierarchyDepth",
            "last_reviewed",
            "buildClubPenaltyFaq",
        ],
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
