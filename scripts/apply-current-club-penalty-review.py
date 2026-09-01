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
            "date": "2026-05-11",
            "note": "Official 2025/26 role baseline retained only for players still at the same club; it is not treated as a current hierarchy by itself.",
        },
        {
            "label": "StatBunker Ligue 1 2026/27 penalties",
            "url": "https://www.statbunker.com/competitions/Penalties?comp_id=796",
            "date": "2026-09-01",
            "note": "Current-season penalty event and taker cross-check.",
        },
        {
            "label": "Deux-Zero Ligue 1 2026/27 penalty archive",
            "url": "https://www.deux-zero.com/ligue-1/penalties-tireurs-epreuve/joueur/6874",
            "date": "2026-09-01",
            "note": "Independent French current-season archive used to cross-check every recorded penalty taker and outcome.",
        },
        {
            "label": "Starting11 Ligue 1 set-piece and lineup tracker",
            "url": "https://starting11.com/set-piece-takers/ligue-1",
            "date": "2026-09-01",
            "note": "Current squads, starting roles and retained penalty history used for lineup and membership checks, not as proof of an unobserved 2026/27 assignment.",
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
    unavailable: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"order": order, "note": note, "status": status}
    if sources:
        result["sources"] = sources
    if confidence:
        result["confidence"] = confidence
    if membership_sources:
        result["membership_sources"] = membership_sources
    if unavailable:
        result["unavailable"] = unavailable
    return result


# Only source-supported changes belong here. Direct 2026/27 match evidence in the
# existing files takes precedence over a generic league board and is retained.
OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "epl": {
        "Bournemouth": change(
            ["Justin Kluivert", "Marcus Tavernier", "Evanilson"],
            "Kroupi remains the nominal long-term specialist but is excluded from the active matchday order while recovering from foot surgery. Kluivert's established Premier League record makes him the practical first call, with Tavernier second after converting with Kroupi in the side. Current starting striker Evanilson is the low-confidence active third candidate; he has no observed 2026/27 assignment.",
            "conditional",
            sources=[
                {
                    "label": "Cadena SER Kroupi injury report",
                    "url": "https://cadenaser.com/nacional/2026/07/29/eli-junior-kroupi-alternativa-del-barca-para-reforzar-el-ataque-lesionado-para-los-proximos-tres-o-cuatro-meses-cadena-ser/",
                    "date": "2026-07-29",
                    "note": "Reports foot surgery and an expected absence of three to four months, removing Kroupi from the active matchday hierarchy until medical clearance.",
                },
                {
                    "label": "AFC Bournemouth Kluivert penalty record",
                    "url": "https://www.afcb.co.uk/news/2024/november/30/kluivert-makes-premier-league-history-in-wolves-win/",
                    "date": "2024-11-30",
                    "note": "Kluivert converted three regular-time Premier League penalties in one match.",
                },
                {
                    "label": "AFC Bournemouth Kroupi event",
                    "url": "https://www.afcb.co.uk/news/2026/may/03/cherries-shine-in-strong-showing-against-crystal-palace/",
                    "date": "2026-05-03",
                    "note": "Kroupi converted with Tavernier playing; this preserves his nominal role but does not make him currently available.",
                },
                {
                    "label": "Evanilson 2026/27 match log",
                    "url": "https://fbref.com/en/players/6f3cc2fe/matchlogs/2026-2027/summary/Evanilson-Match-Logs",
                    "date": "2026-09-01",
                    "note": "Confirms Evanilson started Bournemouth's first two league matches; this supports active depth only, not a penalty assignment.",
                },
            ],
            confidence={"primary": "medium", "secondary": "medium", "tertiary": "low"},
            membership_sources={
                "primary": "https://www.afcb.co.uk/news/2024/november/30/kluivert-makes-premier-league-history-in-wolves-win/",
                "secondary": "https://www.afcb.co.uk/news/2026/may/03/cherries-shine-in-strong-showing-against-crystal-palace/",
                "tertiary": "https://fbref.com/en/players/6f3cc2fe/matchlogs/2026-2027/summary/Evanilson-Match-Logs",
            },
            unavailable=[
                {
                    "player": "Junior Kroupi",
                    "reason": "foot surgery; reported three-to-four-month absence",
                    "source_url": "https://cadenaser.com/nacional/2026/07/29/eli-junior-kroupi-alternativa-del-barca-para-reforzar-el-ataque-lesionado-para-los-proximos-tres-o-cuatro-meses-cadena-ser/",
                    "checked_at": "2026-09-01",
                    "return_rule": "Restore only after current medical clearance and matchday availability are verified.",
                }
            ],
        ),
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
            ["Mateo Pellegrino", "Beto", "Franco Mastantuono"],
            "Deadline-day exits remove Gudmundsson, Kean and Mandragora. Pellegrino is the provisional first call, with Beto and Mastantuono the unassigned alternatives. All three positions remain low-confidence until Fiorentina's first competitive penalty with two candidates available.",
            "disputed",
            sources=[
                {
                    "label": "Fantacalcio current Pellegrino role file",
                    "url": "https://www.fantacalcio.it/serie-a/squadre/fiorentina/pellegrino-m/7023/2026-27",
                    "date": "2026-09-01",
                    "note": "Lists Pellegrino as a current Fiorentina starter and explicitly flags him as a possible penalty taker when on the pitch.",
                },
                {
                    "label": "ANSA Beto signing report",
                    "url": "https://www.ansa.it/english/newswire/english_service/2026/08/31/soccer-fiorentina-sign-beto-and-gnonto-3_12fcb577-a703-4056-9e07-0d324193393a.html",
                    "date": "2026-08-31",
                    "note": "Confirms Beto joined Fiorentina as the central-forward replacement for outgoing Moise Kean.",
                },
                {
                    "label": "Premier League Beto penalty report",
                    "url": "https://www.premierleague.com/en/news/3916734/everton-v-west-ham-homepage-report",
                    "date": "2024-03-02",
                    "note": "Records that Beto's only Premier League penalty was saved, limiting the case for promoting him automatically on arrival.",
                },
                {
                    "label": "Mastantuono career penalty record",
                    "url": "https://www.transfermarkt.com/franco-mastantuono/elfmetertore/spieler/1057316",
                    "date": "2026-09-01",
                    "note": "Records three conversions and no misses, but none establishes a Fiorentina or senior European league assignment.",
                },
                {
                    "label": "ANSA Mandragora transfer report",
                    "url": "https://www.ansa.it/amp/piemonte/notizie/2026/09/01/torino-riecco-mandragora-operazione-da-cinque-milioni_f3ad4b17-c251-4df9-a2ad-0b9c50e44d5f.html",
                    "date": "2026-09-01",
                    "note": "Confirms Mandragora left Fiorentina for Torino and must be removed from the hierarchy.",
                },
                {
                    "label": "FiorentinaNews Gudmundsson transfer confirmation",
                    "url": "https://www.fiorentinanews.com/news/522505326086/ufficiale-paratici-smonta-completamente-l-attacco-viola-che-fu-gudmundsson-saluta",
                    "date": "2026-09-01",
                    "note": "Reports the Lega Serie A registration of Gudmundsson's move from Fiorentina to Lazio.",
                },
            ],
            confidence={"primary": "low", "secondary": "low", "tertiary": "low"},
            membership_sources={
                "primary": "https://www.fantacalcio.it/serie-a/squadre/fiorentina/pellegrino-m/7023/2026-27",
                "secondary": "https://www.ansa.it/english/newswire/english_service/2026/08/31/soccer-fiorentina-sign-beto-and-gnonto-3_12fcb577-a703-4056-9e07-0d324193393a.html",
                "tertiary": "https://elpais.com/deportes/futbol/2026-08-07/franco-mastantuono-cedido-por-el-madrid-a-la-fiorentina.html",
            },
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
        "Bayern Munich": change(
            ["Harry Kane", "Arijon Ibrahimović", "Jamal Musiala"],
            "Kane remains the confirmed first choice. LigaInsider identifies Ibrahimović as the current preseason backup; Musiala is retained third pending a direct assignment.",
            "probable",
            confidence={"primary": "high", "secondary": "medium", "tertiary": "low"},
        ),
        "Borussia Dortmund": change(
            ["Ramy Bensebaini", "Serhou Guirassy", "Félix Nmecha"],
            "Can is excluded from the active order while still in ACL rehabilitation. Bensebaini is first: he converted two penalties against HSV while Guirassy and Nmecha were both on the pitch, directly outranking them in the same match. Guirassy is the practical alternative when Bensebaini does not start; Nmecha remains third after missing the earlier penalty in that HSV match.",
            "conditional",
            sources=[
                {
                    "label": "Borussia Dortmund HSV match report",
                    "url": "https://www.bvb.de/de/en/news/news-overview/news.html/2026/3/21/3-2-from-0-2-down-BVBs-second-half-onslaught-against-HSV.html",
                    "date": "2026-03-21",
                    "note": "Bensebaini converted twice after entering with Guirassy; Nmecha remained on the pitch after missing the first-half penalty.",
                },
                {
                    "label": "Borussia Dortmund preseason medical update",
                    "url": "https://www.bvb.de/de/de/aktuelles/news/news.html/2026/7/12/An-die-Arbeit-BVB-startet-mit-Leistungsdiagnostik-in-die-Vorbereitung.html",
                    "date": "2026-07-12",
                    "note": "The club states that Can remained in rehabilitation after his cruciate-ligament injury.",
                },
                {
                    "label": "Borussia Dortmund opening league lineup",
                    "url": "https://www.bvb.de/de/en/news/news-overview/news.html/2026/8/29/From-dominance-to-gritty-defending-BVB-celebrates-first-win-of-the-season.html",
                    "date": "2026-08-29",
                    "note": "Can was absent from Dortmund's opening league matchday squad, providing a current-season availability cross-check.",
                },
                {
                    "label": "LigaInsider 2026/27 set-piece board",
                    "url": "https://www.ligainsider.de/ligainsider_1381/uebersicht-die-standardschuetzen-der-saison-2026-27-416770/",
                    "date": "2026-08-31",
                    "note": "Lists the nominal Can/Guirassy order but does not account for Can's current unavailability, so direct club evidence takes precedence.",
                },
            ],
            confidence={"primary": "high", "secondary": "medium", "tertiary": "low"},
            membership_sources={
                "primary": "https://www.bvb.de/de/en/news/news-overview/news.html/2026/3/21/3-2-from-0-2-down-BVBs-second-half-onslaught-against-HSV.html",
                "secondary": "https://www.bvb.de/de/en/news/news-overview/news.html/2026/3/21/3-2-from-0-2-down-BVBs-second-half-onslaught-against-HSV.html",
                "tertiary": "https://www.bvb.de/de/en/news/news-overview/news.html/2026/3/21/3-2-from-0-2-down-BVBs-second-half-onslaught-against-HSV.html",
            },
            unavailable=[
                {
                    "player": "Emre Can",
                    "reason": "ACL rehabilitation",
                    "source_url": "https://www.bvb.de/de/de/aktuelles/news/news.html/2026/7/12/An-die-Arbeit-BVB-startet-mit-Leistungsdiagnostik-in-die-Vorbereitung.html",
                    "checked_at": "2026-09-01",
                    "return_rule": "Restore only after current official medical clearance and matchday availability are verified.",
                }
            ],
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
        "RasenBallsport Leipzig": change(
            ["Christopher Nkunku", "Rômulo", "David Raum"],
            "Leipzig's order remains open. Nkunku is the provisional first call after his confirmed return and four successful Bundesliga penalties from five recorded attempts; Rômulo and Raum remain low-confidence alternatives until the first direct assignment.",
            "disputed",
            sources=[
                {
                    "label": "RB Leipzig Nkunku announcement",
                    "url": "https://rbleipzig.com/de/news/christopher-nkunku-rb-leipzig-transfer-leihe-ac-mailand",
                    "date": "2026-08-25",
                    "note": "Confirms Nkunku's return to Leipzig for 2026/27.",
                },
                {
                    "label": "LigaInsider 2026/27 set-piece board",
                    "url": "https://www.ligainsider.de/ligainsider_1381/uebersicht-die-standardschuetzen-der-saison-2026-27-416770/",
                    "date": "2026-09-01",
                    "note": "Marks Leipzig's hierarchy open but identifies Nkunku as the leading candidate if his transfer is completed, citing four Bundesliga conversions from five attempts.",
                },
            ],
            confidence={"primary": "low", "secondary": "low", "tertiary": "low"},
            membership_sources={
                "primary": "https://rbleipzig.com/de/news/christopher-nkunku-rb-leipzig-transfer-leihe-ac-mailand",
            },
        ),
        "Schalke 04": change(
            ["Kenan Karaman", "Bryan Lasme", "Moussa Sylla"],
            "Karaman remains first choice after a five-from-five league season. LigaInsider places Lasme next despite his preseason miss; Sylla is retained as the third current forward candidate.",
            "probable",
            confidence={"primary": "high", "secondary": "low", "tertiary": "low"},
        ),
        "SV Elversberg": change(
            ["Lukas Petkov", "Francis Onyeka", "Maurice Krattenmacher"],
            "LigaInsider still marks Elversberg's penalty role open. Petkov, Onyeka and Krattenmacher are provisional candidates only, not a confirmed assignment.",
            "disputed",
            confidence={"primary": "low", "secondary": "low", "tertiary": "low"},
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
    "ligue-1": {
        "Le Mans": change(
            ["Louis Mafouta", "Dame Gueye", "Antoine Rabillard"],
            "Louis Mafouta is now first choice after taking and converting Le Mans' 54th-minute penalty at Rennes with Dame Gueye still on the pitch. This satisfies the preseason promotion condition exactly. Gueye moves to second and Antoine Rabillard remains third.",
            "confirmed",
            sources=[
                {
                    "label": "L'Équipe Rennes-Le Mans match report",
                    "url": "https://www.lequipe.fr/Football/Actualites/Apres-s-etre-fait-peur-contre-le-promu-le-mans-rennes-s-offre-sa-premiere-victoire-de-la-saison-grace-a-un-penalty-tardif-de-lepaul/1714776",
                    "date": "2026-08-30",
                    "note": "Records Mafouta converting Le Mans' penalty against Rennes.",
                },
                *LEAGUE_SOURCES["ligue-1"][1:],
            ],
            confidence={"primary": "high", "secondary": "medium", "tertiary": "low"},
        ),
        "Lens": change(
            ["Florian Thauvin", "Odsonne Édouard", "Thorgan Hazard"],
            "Florian Thauvin remains directly confirmed as Lens' primary. Coach Dino Toppmöller stated that Thauvin takes whenever he is on the pitch; Édouard may receive a delegated attempt, while Hazard remains the next filed alternative.",
            "confirmed",
            sources=[
                {
                    "label": "L'Équipe Lens coach confirmation",
                    "url": "https://www.lequipe.fr/Football/Actualites/Deux-courses-sans-elan-sur-penalty-et-un-echec-florian-thauvin-a-pris-le-gout-du-risque-contre-auxerre/1712884",
                    "date": "2026-08-22",
                    "note": "Quotes Dino Toppmoller confirming Thauvin is the designated taker whenever he is on the pitch.",
                },
                *LEAGUE_SOURCES["ligue-1"][1:],
            ],
            confidence={"primary": "high", "secondary": "medium", "tertiary": "medium"},
        ),
        "Marseille": change(
            ["Amine Gouiri", "Himad Abdelli", "Pierre-Emile Højbjerg"],
            "Gouiri converted Marseille's first 2026/27 Ligue 1 penalty against Strasbourg with Abdelli and Højbjerg both on the pitch. This directly confirms Gouiri as first choice. Abdelli remains the strongest deputy on prior penalty record; Højbjerg remains tertiary, but the backup order has not yet been tested.",
            "confirmed",
            sources=[
                {
                    "label": "L'Équipe Marseille-Strasbourg report",
                    "url": "https://www.lequipe.fr/Football/Actualites/Gouiri-lance-l-om-thauvin-voit-double-ferran-torres-en-sauveur-des-attaquants-en-feu-dans-l-equipe-type-de-la-premiere-journee-de-ligue-1/1713197",
                    "date": "2026-08-24",
                    "note": "Records Gouiri converting Marseille's penalty against Strasbourg.",
                },
                *LEAGUE_SOURCES["ligue-1"][1:],
            ],
            confidence={"primary": "high", "secondary": "medium", "tertiary": "low"},
        ),
        "Rennes": change(
            ["Estéban Lepaul", "Ludovic Blas", "Issa Soumaré"],
            "Estéban Lepaul moves first after taking and converting Rennes' 90+6 penalty against Le Mans with Ludovic Blas on the pitch from the 74th minute. Blas had previously described himself as first and Lepaul second, so one current-season reversal does not make the order fully settled; Blas remains the live deputy and Issa Soumaré stays third.",
            "disputed",
            sources=[
                {
                    "label": "L'Équipe Rennes-Le Mans match report",
                    "url": "https://www.lequipe.fr/Football/Actualites/Apres-s-etre-fait-peur-contre-le-promu-le-mans-rennes-s-offre-sa-premiere-victoire-de-la-saison-grace-a-un-penalty-tardif-de-lepaul/1714776",
                    "date": "2026-08-30",
                    "note": "Records Lepaul converting Rennes' stoppage-time penalty against Le Mans.",
                },
                *LEAGUE_SOURCES["ligue-1"][1:],
            ],
            confidence={"primary": "high", "secondary": "medium", "tertiary": "low"},
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
    elif override:
        context = str(override["note"])
        headline = f"{team} hierarchy rechecked"
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
                filed_names = [name.strip() for name in names if name.strip()]
                if (
                    len(names) != 3
                    or not names[0].strip()
                    or (not names[1].strip() and names[2].strip())
                    or len({name.casefold() for name in filed_names}) != len(filed_names)
                ):
                    raise ValueError(f"{league}/{team}: override must contain an ordered set of distinct names")
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
            if override:
                entry["hierarchy_status"] = str(override.get("status") or entry.get("hierarchy_status") or "probable")
                confidence = dict(entry.get("confidence") or {})
                for position in ("primary", "secondary", "tertiary"):
                    confidence[position] = str((override.get("confidence") or {}).get(position) or "medium")
                entry["confidence"] = confidence
                entry["condition_note"] = str(override["note"])
                team_sources = review_sources(league, team)
                entry["source"] = team_sources[0]["label"]
                entry["cross_check"] = team_sources[1]["label"]
                if override.get("unavailable"):
                    entry["unavailable_candidates"] = list(override["unavailable"])

                ranked = {name.casefold() for name in after.values() if name}
                unavailable_ranked = [
                    row["player"] for row in entry.get("unavailable_candidates", [])
                    if str(row.get("player") or "").casefold() in ranked
                ]
                if unavailable_ranked:
                    raise ValueError(f"{league}/{team}: unavailable players remain actively ranked: {unavailable_ranked}")

            if changed:
                entry.update(after)
                entry["last_updated"] = audit_date
                entry["last_verified"] = {
                    "date": audit_date,
                    "by": "Il Margine",
                    "method": "current_roster_and_penalty_record_review",
                }

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
                    membership.pop(position, None)
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
