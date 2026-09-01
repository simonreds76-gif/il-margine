#!/usr/bin/env python3
"""Record a current-season review without rewriting unchanged evidence dates.

The public files historically used ``last_verified`` for two different facts:
when the board was checked and when the hierarchy changed. This script records
the former in ``last_reviewed`` and updates ``last_verified`` only for supported
hierarchy changes.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "goalscorer"
LEAGUES = ("epl", "serie-a", "la-liga", "bundesliga", "ligue-1")
SEASON = "2026/27"

LEAGUE_SOURCES: dict[str, list[dict[str, str]]] = {
    "epl": [
        {
            "label": "Squawka 2026/27 set-piece board",
            "url": "https://www.squawka.com/en/features/premier-league-best-set-piece-takers-2026-27/",
            "date": "2026-08-10",
            "note": "Current all-club penalty and set-piece hierarchy, updated for confirmed transfers.",
        },
        {
            "label": "FPL Assistant current role audit",
            "url": "https://fplassistant.net/guides/fpl-penalty-set-piece-takers-2026-27",
            "date": "2026-08-15",
            "note": "Independent all-club cross-check with uncertainty and current-squad context.",
        },
    ],
    "serie-a": [
        {
            "label": "GOAL Italia 2026/27 rigoristi board",
            "url": "https://www.goal.com/it/liste/fantacalcio-rigoristi-serie-a-2026-2027-tiratori-e-gerarchie-dal-dischetto-delle-20-squadre-del-campionato/bltdebca56c3bd91419",
            "date": "2026-08-29",
            "note": "Current all-club order reflecting late-August transfers and role changes.",
        },
        {
            "label": "Lega Serie A current squads",
            "url": "https://www.legaseriea.it/en/serie-a/teams",
            "date": "2026-09-01",
            "note": "Current league squad directory used to reject departed candidates.",
        },
    ],
    "la-liga": [
        {
            "label": "Betfair Spain LaLiga penalty board",
            "url": "https://www.betfair.es/blog/futbol/futbol-espanol/laliga/quien-tira-los-penaltis-en-laliga-26-27-todo-lo-que-quieres-saber-120826-1377.html",
            "date": "2026-08-31",
            "note": "Current all-club primary and alternative order plus 2026/27 penalty events.",
        },
        {
            "label": "LaLiga 2026/27 squads and match records",
            "url": "https://www.laliga.com/en-GB/laliga-easports/clubs",
            "date": "2026-09-01",
            "note": "Official current club and competition cross-check.",
        },
    ],
    "bundesliga": [
        {
            "label": "LigaInsider 2026/27 set-piece board",
            "url": "https://www.ligainsider.de/ligainsider_1381/uebersicht-die-standardschuetzen-der-saison-2026-27-416770/",
            "date": "2026-08-31",
            "note": "Current club-by-club penalty and set-piece hierarchy.",
        },
        {
            "label": "Bundesliga official penalty statistics",
            "url": "https://www.bundesliga.com/de/bundesliga/statistiken/spieler/elfmeter",
            "date": "2026-09-01",
            "note": "Official current-season penalty event cross-check.",
        },
    ],
    "ligue-1": [
        {
            "label": "Ligue 1 official set-piece review",
            "url": "https://ligue1.com/fr/articles/l1_article_2916-",
            "date": "2026-06-01",
            "note": "Official role baseline retained only where current evidence has not superseded it.",
        },
        {
            "label": "StatBunker Ligue 1 2026/27 penalties",
            "url": "https://www.statbunker.com/competitions/Penalties?comp_id=796",
            "date": "2026-09-01",
            "note": "Current-season penalty event and taker cross-check.",
        },
    ],
}


def change(
    order: list[str],
    note: str,
    status: str = "probable",
    *,
    sources: list[dict[str, str]] | None = None,
    confidence: dict[str, str] | None = None,
    membership_sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"order": order, "note": note, "status": status}
    if sources:
        result["sources"] = sources
    if confidence:
        result["confidence"] = confidence
    if membership_sources:
        result["membership_sources"] = membership_sources
    return result


# Only source-supported changes belong here. Direct 2026/27 match evidence in the
# existing files takes precedence over a generic league board and is retained.
OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "epl": {
        "Newcastle United": change(
            ["Yoane Wissa", "Matias Fernandez-Pardo", "William Osula"],
            "Wissa is the provisional first call after starting Newcastle's latest league match as the central forward and bringing the strongest senior penalty record. New signing Fernandez-Pardo has two recent Ligue 1 conversions but no Newcastle assignment, while Osula is retained as the specialist-board alternative. Woltemade is removed after the reported Juventus loan agreement. The first competitive award with Wissa and Fernandez-Pardo available must settle the order.",
            "disputed",
            sources=[
                {
                    "label": "Newcastle United latest league lineup",
                    "url": "https://www.newcastleunited.com/en/news/confirmed-line-up-spurs-a",
                    "date": "2026-08-29",
                    "note": "Wissa started at centre-forward; Woltemade and Schar were substitutes.",
                },
                {
                    "label": "Newcastle United signing announcement",
                    "url": "https://www.newcastleunited.com/en/news/newcastle-united-sign-matias-fernandez-pardo",
                    "date": "2026-09-01",
                    "note": "Confirms Fernandez-Pardo joined Newcastle as the club's eighth summer signing.",
                },
                {
                    "label": "AS deadline-day transfer report",
                    "url": "https://as.com/futbol/internacional/woltemade-por-jonathan-david-f202609-n/",
                    "date": "2026-09-01",
                    "note": "Reports Newcastle and Juventus agreed Woltemade's season loan and that he travelled for his medical.",
                },
                {
                    "label": "Yoane Wissa penalty record",
                    "url": "https://www.transfermarkt.co.uk/yoane-wissa/elfmetertore/spieler/388165",
                    "date": "2026-09-01",
                    "note": "Records 13 scored penalties and two misses across Wissa's senior career.",
                },
                {
                    "label": "Matias Fernandez-Pardo penalty record",
                    "url": "https://www.transfermarkt.com/matias-fernandez-pardo/elfmetertore/spieler/724129",
                    "date": "2026-09-01",
                    "note": "Records two successful Ligue 1 penalties in April 2026 and no miss.",
                },
                {
                    "label": "Fantasy Football Scout set-piece table",
                    "url": "https://www.fantasyfootballscout.co.uk/fantasy-premier-league-set-piece-takers",
                    "date": "2026-09-01",
                    "note": "Still listed Woltemade on deadline day, so it was treated as a stale baseline rather than current squad truth.",
                },
            ],
            confidence={"primary": "medium", "secondary": "low", "tertiary": "low"},
            membership_sources={
                "primary": "https://www.newcastleunited.com/en/news/confirmed-line-up-spurs-a",
                "secondary": "https://www.newcastleunited.com/en/news/newcastle-united-sign-matias-fernandez-pardo",
                "tertiary": "https://www.newcastleunited.com/en/news/confirmed-line-up-spurs-a",
            },
        ),
    },
    "serie-a": {
        "Atalanta": change(
            ["Franck Kessié", "Gianluca Scamacca", "Charles De Ketelaere"],
            "Kessié is the late-August first-choice projection, with Scamacca and De Ketelaere the current alternatives.",
        ),
        "Bologna": change(
            ["Riccardo Orsolini", "Artem Dovbyk", "Federico Bernardeschi"],
            "Orsolini remains first choice. Dovbyk is now the principal backup, ahead of Bernardeschi.",
        ),
        "Como": change(
            ["Lucas Da Cunha", "Nico Paz", "Tasos Douvikas"],
            "Da Cunha leads the current order, followed by Paz and Douvikas.",
        ),
        "Fiorentina": change(
            ["Franco Mastantuono", "Mateo Pellegrino", "Rolando Mandragora"],
            "Fiorentina's rebuilt attack makes Mastantuono the current first call, Pellegrino the main alternative and Mandragora the retained third option.",
            "disputed",
        ),
        "Inter": change(
            ["Hakan Çalhanoğlu", "Lautaro Martínez", "Piotr Zieliński"],
            "Çalhanoğlu remains first choice; the current backup order is Lautaro then Zieliński.",
            "confirmed",
        ),
        "Lazio": change(
            ["Mattia Zaccagni", "Albert Gudmundsson", "Andrea Pinamonti"],
            "Zaccagni remains first choice. Gudmundsson and Pinamonti are the current specialist alternatives after Lazio's late-window changes.",
            "probable",
        ),
        "Lecce": change(
            ["Willem Geubbels", "Nikola Štulić", "Santiago Pierotti"],
            "Geubbels is the current first-choice projection after joining Lecce, with Štulić second and Pierotti retained as the next verified alternative.",
            "disputed",
        ),
        "Monza": change(
            ["Matteo Pessina", "Patrick Cutrone", "Andrea Petagna"],
            "Pessina remains first choice, followed by Cutrone and Petagna.",
        ),
        "Parma Calcio 1913": change(
            ["El Bilal Touré", "Adrián Bernabé", "Nesta Elphege"],
            "Touré is the current first-choice projection, Bernabé moves to second and Elphege remains the third filed option.",
            "conditional",
        ),
        "Sassuolo": change(
            ["Domenico Berardi", "Sebastiano Esposito", "Armand Laurienté"],
            "Berardi remains first choice. Esposito is now the main alternative, with Laurienté retained third.",
        ),
        "Torino": change(
            ["Nikola Vlašić", "Duván Zapata", "Giovanni Simeone"],
            "Vlašić remains first choice, followed by Zapata and Simeone.",
        ),
    },
    "la-liga": {
        "Athletic Club": change(
            ["Oihan Sancet", "Nico Williams", "Gorka Guruzeta"],
            "Sancet remains first choice; Nico Williams is the current principal alternative ahead of Guruzeta.",
        ),
        "Atletico Madrid": change(
            ["Julián Álvarez", "Ademola Lookman", "Alexander Sørloth"],
            "Álvarez remains first choice. Lookman is the current backup after Griezmann's departure, with Sørloth third.",
        ),
        "Elche": change(
            ["Fer Niño", "Germán Valera", "Ali Houary"],
            "Fer Niño now leads Elche's projected order, followed by Germán Valera and Ali Houary.",
            "disputed",
        ),
        "Espanyol": change(
            ["Roberto Fernández", "Pere Milla", "Kike García"],
            "Roberto Fernández remains first choice; Pere Milla is the current main alternative ahead of Kike García.",
            "probable",
        ),
        "Getafe": change(
            ["Juanmi", "Borja Mayoral", "Enes Ünal"],
            "Juanmi is the current first-choice projection, followed by Mayoral and Ünal.",
            "disputed",
        ),
    },
    "bundesliga": {
        "Borussia Dortmund": change(
            ["Emre Can", "Serhou Guirassy", "Ramy Bensebaini"],
            "The current specialist board places Can first and Guirassy second; Bensebaini remains a proven third option.",
            "disputed",
        ),
        "Borussia M.Gladbach": change(
            ["Kevin Diks", "Kevin Stöger", "Robin Hack"],
            "Diks remains first choice, with Stöger now filed ahead of Hack in the backup order.",
        ),
        "FC Cologne": change(
            ["Marius Bülter", "Said El Mala", "Linton Maina"],
            "Bülter is the current first-choice projection, followed by El Mala and Maina.",
            "disputed",
        ),
        "Hamburger SV": change(
            ["Albert Grønbæk", "Miro Muheim", "Otto Stange"],
            "Grønbæk leads the current order, followed by Muheim and Stange.",
            "conditional",
        ),
        "Mainz 05": change(
            ["Nadiem Amiri", "Ransford-Yeboah Königsdörffer", "Paul Nebel"],
            "Amiri remains first choice; Königsdörffer and Nebel are the current alternatives.",
            "probable",
        ),
        "Union Berlin": change(
            ["Aljoscha Kemlein", "Dejan Ljubičić", "Derrick Köhn"],
            "The current specialist board places Kemlein and Ljubičić first, with Köhn retained third.",
            "disputed",
        ),
        "VfB Stuttgart": change(
            ["Maximilian Mittelstädt", "Deniz Undav", "Ermedin Demirović"],
            "Mittelstädt remains first choice; Undav is now the principal alternative ahead of Demirović.",
        ),
        "Werder Bremen": change(
            ["Niclas Füllkrug", "Salim Musah", "Cedric Itten"],
            "Füllkrug remains first choice, with Musah now ahead of Itten in the backup order.",
            "probable",
        ),
    },
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def order(entry: dict[str, Any]) -> dict[str, str]:
    return {key: str(entry.get(key) or "").strip() for key in ("primary", "secondary", "tertiary")}


def review_sources(league: str, team: str) -> list[dict[str, str]]:
    override = OVERRIDES.get(league, {}).get(team) or {}
    return list(override.get("sources") or LEAGUE_SOURCES[league])


def event(team: str, league: str, audit_date: str, before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    changed = before != after
    source_rows = review_sources(league, team)
    override = OVERRIDES.get(league, {}).get(team)
    if changed:
        context = str(override["note"])
        headline = f"{team} penalty hierarchy updated"
    else:
        context = "Current squad, league-wide role reporting and available 2026/27 penalty events were checked; no stronger evidence justified changing the filed order."
        headline = f"{team} hierarchy rechecked"
    return {
        "id": f"evt_{audit_date.replace('-', '')}_{slug(team)}_current_review",
        "date": audit_date,
        "season": SEASON,
        "type": "current_season_board_review",
        "penalty_kind": None,
        "competition": None,
        "match": None,
        "headline": headline,
        "context": context,
        "sources": source_rows,
        "detection": "manual_multi_source_research",
        "review": {
            "status": "approved",
            "reviewed_by": "Il Margine",
            "reviewed_at": f"{audit_date}T12:00:00Z",
        },
        "affects_hierarchy": changed,
        "editorial_note": context,
    }


def apply(audit_date: str, write: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "audit_type": "current_season_all_club_review",
        "season": SEASON,
        "as_of": audit_date,
        "source_precedence": [
            "current competitive penalty with lineup context",
            "manager or official club assignment",
            "current specialist league board",
            "previous verified order",
        ],
        "leagues": {},
    }
    total = 0
    changed_total = 0

    for league in LEAGUES:
        path = DATA / f"{league}-penalty-takers.json"
        data = load(path)
        sources = LEAGUE_SOURCES[league]
        if len(sources) < 2 or any(not source["url"].startswith("https://") for source in sources):
            raise ValueError(f"{league}: current review requires two HTTPS sources")
        changed_teams: list[dict[str, Any]] = []
        reviewed_teams: list[str] = []

        for team, entry in data.items():
            if team.startswith("_") or not isinstance(entry, dict):
                continue
            reviewed_teams.append(team)
            current_order = order(entry)
            override = OVERRIDES.get(league, {}).get(team)
            if override:
                names = list(override["order"])
                if len(names) != 3 or len({name.casefold() for name in names}) != 3 or any(not name.strip() for name in names):
                    raise ValueError(f"{league}/{team}: override must contain three distinct names")
                after = dict(zip(("primary", "secondary", "tertiary"), names, strict=True))
            else:
                after = current_order

            prior_change = next(
                (
                    item for item in entry.get("change_log", [])
                    if isinstance(item, dict)
                    and item.get("changed_at") == audit_date
                    and item.get("change_type") == "current_season_hierarchy_update"
                ),
                None,
            )
            prior_order = prior_change.get("from") if isinstance(prior_change, dict) else None
            before = {
                position: str((prior_order or {}).get(position) or "").strip()
                for position in ("primary", "secondary", "tertiary")
            } if isinstance(prior_order, dict) else current_order

            changed = before != after
            if changed:
                entry.update(after)
                entry["hierarchy_status"] = str(override.get("status") or entry.get("hierarchy_status") or "probable")
                confidence = dict(entry.get("confidence") or {})
                for position in ("primary", "secondary", "tertiary"):
                    confidence[position] = str((override.get("confidence") or {}).get(position) or "medium")
                entry["confidence"] = confidence
                entry["condition_note"] = str(override["note"])
                entry["last_updated"] = audit_date
                entry["last_verified"] = {
                    "date": audit_date,
                    "by": "Il Margine",
                    "method": "current_roster_and_penalty_record_review",
                }
                team_sources = review_sources(league, team)
                entry["source"] = team_sources[0]["label"]
                entry["cross_check"] = team_sources[1]["label"]

            review_event = event(team, league, audit_date, before, after)
            evidence_log = [
                item for item in entry.get("evidence_log", [])
                if isinstance(item, dict) and item.get("id") != review_event["id"]
            ]
            entry["evidence_log"] = evidence_log + [review_event]
            entry["latest_evidence"] = {
                "id": review_event["id"],
                "date": audit_date,
                "type": review_event["type"],
                "source_count": len(review_event["sources"]),
            }
            entry["last_reviewed"] = {
                "date": audit_date,
                "by": "Il Margine",
                "method": "current_season_multi_source_review",
                "outcome": "hierarchy_updated" if changed else "order_unchanged",
                "sources": [source["url"] for source in review_sources(league, team)],
            }
            entry["public_updated_at"] = audit_date

            membership = dict(entry.get("squad_membership") or {})
            for position, player in after.items():
                if not player:
                    continue
                current = dict(membership.get(position) or {})
                current.update({
                    "player": player,
                    "status": "confirmed",
                    "source_url": (
                        (((override or {}).get("membership_sources") or {}).get(position))
                        or (current.get("source_url") if current.get("player") == player else review_sources(league, team)[0]["url"])
                    ),
                    "checked_at": audit_date,
                })
                membership[position] = current
            entry["squad_membership"] = membership

            if changed:
                changed_total += 1
                changed_teams.append({"team": team, "from": before, "to": after, "reason": override["note"]})
                changes = [
                    item for item in entry.get("change_log", [])
                    if isinstance(item, dict)
                    and not (
                        item.get("changed_at") == audit_date
                        and item.get("change_type") == "current_season_hierarchy_update"
                    )
                ]
                changes.append({
                    "changed_at": audit_date,
                    "season": SEASON,
                    "change_type": "current_season_hierarchy_update",
                    "from": before,
                    "to": after,
                    "reason": override["note"],
                    "evidence_ids": [review_event["id"]],
                    "detection": "manual_multi_source_research",
                    "approved_by": "Il Margine",
                    "approved_at": f"{audit_date}T12:00:00Z",
                    "article_slug": None,
                })
                entry["change_log"] = changes

            total += 1

        unknown_overrides = set(OVERRIDES.get(league, {})) - set(reviewed_teams)
        if unknown_overrides:
            raise ValueError(f"{league}: unknown override clubs: {sorted(unknown_overrides)}")

        meta = dict(data.get("_meta") or {})
        meta["last_verified"] = audit_date
        meta["last_reviewed"] = audit_date
        meta["public_updated_at"] = audit_date
        data["_meta"] = meta
        report["leagues"][league] = {
            "reviewed_count": len(reviewed_teams),
            "reviewed_clubs": sorted(reviewed_teams),
            "changed_count": len(changed_teams),
            "changes": changed_teams,
            "sources": LEAGUE_SOURCES[league],
        }
        if write:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report["summary"] = {"reviewed_clubs": total, "hierarchies_changed": changed_total}
    if write:
        report_path = DATA / "research" / f"club-penalty-current-review-{audit_date}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-date", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = apply(args.audit_date, args.write)
    for league, row in report["leagues"].items():
        print(f"{league}: reviewed={row['reviewed_count']} changed={row['changed_count']}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
