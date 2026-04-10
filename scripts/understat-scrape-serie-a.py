"""
Understat football player match-log scraper.

Backward-compatible default:
  python scripts/understat-scrape-serie-a.py --season 2025-2026

Extended usage:
  python scripts/understat-scrape-serie-a.py --league serie-a epl la-liga bundesliga ligue-1 --season 2024-2025 2025-2026

The script keeps the legacy Serie A filename shape for the active goalscorer
pipeline, while also supporting multi-league background data builds.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests


OUTPUT_DIR = "data/goalscorer"
REQUEST_DELAY = 0.8
MIN_SEASON_MINUTES = 90
BIG_CHANCE_XG_THRESHOLD = 0.20

AVAILABLE_SEASONS = ["2023-2024", "2024-2025", "2025-2026"]
DEFAULT_SEASONS = ["2023-2024", "2024-2025", "2025-2026"]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
}

LEAGUE_CONFIGS = {
    "serie-a": {
        "label": "Serie A",
        "slug": "Serie_A",
        "output_prefix": "serie-a",
        "competition": "Serie A",
        "team_aliases": {
            "inter": "inter",
            "internazionale": "inter",
            "inter milan": "inter",
            "ac milan": "milan",
            "milan": "milan",
            "verona": "verona",
            "hellas verona": "verona",
            "juventus": "juventus",
            "roma": "roma",
            "as roma": "roma",
            "lazio": "lazio",
            "ss lazio": "lazio",
            "fiorentina": "fiorentina",
            "acf fiorentina": "fiorentina",
            "napoli": "napoli",
            "ssc napoli": "napoli",
            "parma": "parma",
            "parma calcio 1913": "parma",
            "monza": "monza",
            "ac monza": "monza",
            "udinese": "udinese",
            "udinese calcio": "udinese",
            "lecce": "lecce",
            "us lecce": "lecce",
            "cagliari": "cagliari",
            "cagliari calcio": "cagliari",
            "como": "como",
            "como 1907": "como",
            "empoli": "empoli",
            "empoli fc": "empoli",
            "genoa": "genoa",
            "genoa cfc": "genoa",
            "torino": "torino",
            "torino fc": "torino",
            "venezia": "venezia",
            "venezia fc": "venezia",
            "cremonese": "cremonese",
            "pisa": "pisa",
            "sassuolo": "sassuolo",
        },
    },
    "epl": {
        "label": "Premier League",
        "slug": "EPL",
        "output_prefix": "epl",
        "competition": "Premier League",
        "team_aliases": {
            "arsenal": "arsenal",
            "aston villa": "aston villa",
            "afc bournemouth": "bournemouth",
            "bournemouth": "bournemouth",
            "brentford": "brentford",
            "brighton": "brighton",
            "brighton hove albion": "brighton",
            "brighton and hove albion": "brighton",
            "burnley": "burnley",
            "chelsea": "chelsea",
            "crystal palace": "crystal palace",
            "everton": "everton",
            "fulham": "fulham",
            "ipswich": "ipswich",
            "ipswich town": "ipswich",
            "leicester": "leicester",
            "leicester city": "leicester",
            "liverpool": "liverpool",
            "manchester city": "manchester city",
            "man city": "manchester city",
            "manchester united": "manchester united",
            "man utd": "manchester united",
            "newcastle": "newcastle united",
            "newcastle united": "newcastle united",
            "nottingham forest": "nottingham forest",
            "forest": "nottingham forest",
            "southampton": "southampton",
            "sunderland": "sunderland",
            "tottenham": "tottenham",
            "tottenham hotspur": "tottenham",
            "spurs": "tottenham",
            "west ham": "west ham",
            "west ham united": "west ham",
            "wolves": "wolves",
            "wolverhampton": "wolves",
            "wolverhampton wanderers": "wolves",
        },
    },
    "la-liga": {
        "label": "La Liga",
        "slug": "La_liga",
        "output_prefix": "la-liga",
        "competition": "La Liga",
        "team_aliases": {
            "alaves": "alaves",
            "deportivo alaves": "alaves",
            "athletic club": "athletic club",
            "athletic bilbao": "athletic club",
            "atletico": "atletico madrid",
            "atletico madrid": "atletico madrid",
            "barcelona": "barcelona",
            "fc barcelona": "barcelona",
            "betis": "real betis",
            "real betis": "real betis",
            "celta": "celta vigo",
            "celta vigo": "celta vigo",
            "espanyol": "espanyol",
            "rcd espanyol": "espanyol",
            "getafe": "getafe",
            "girona": "girona",
            "las palmas": "las palmas",
            "leganes": "leganes",
            "cd leganes": "leganes",
            "mallorca": "mallorca",
            "rcd mallorca": "mallorca",
            "osasuna": "osasuna",
            "ca osasuna": "osasuna",
            "rayo vallecano": "rayo vallecano",
            "real madrid": "real madrid",
            "real sociedad": "real sociedad",
            "sevilla": "sevilla",
            "valencia": "valencia",
            "villarreal": "villarreal",
            "valladolid": "valladolid",
            "real valladolid": "valladolid",
            "elche": "elche",
            "levante": "levante",
        },
    },
    "bundesliga": {
        "label": "Bundesliga",
        "slug": "Bundesliga",
        "output_prefix": "bundesliga",
        "competition": "Bundesliga",
        "team_aliases": {
            "augsburg": "augsburg",
            "fc augsburg": "augsburg",
            "bayer leverkusen": "bayer leverkusen",
            "leverkusen": "bayer leverkusen",
            "bayern": "bayern munich",
            "bayern munich": "bayern munich",
            "borussia dortmund": "borussia dortmund",
            "dortmund": "borussia dortmund",
            "borussia monchengladbach": "borussia monchengladbach",
            "monchengladbach": "borussia monchengladbach",
            "gladbach": "borussia monchengladbach",
            "eintracht frankfurt": "eintracht frankfurt",
            "frankfurt": "eintracht frankfurt",
            "freiburg": "freiburg",
            "sc freiburg": "freiburg",
            "hamburger sv": "hamburger sv",
            "hamburg": "hamburger sv",
            "hsv": "hamburger sv",
            "heidenheim": "heidenheim",
            "koln": "koln",
            "cologne": "koln",
            "1 fc koln": "koln",
            "fc koln": "koln",
            "mainz": "mainz 05",
            "mainz 05": "mainz 05",
            "rb leipzig": "rb leipzig",
            "leipzig": "rb leipzig",
            "st pauli": "st pauli",
            "fc st pauli": "st pauli",
            "stuttgart": "stuttgart",
            "vfb stuttgart": "stuttgart",
            "union berlin": "union berlin",
            "werder bremen": "werder bremen",
            "bremen": "werder bremen",
            "bochum": "bochum",
            "vfl bochum": "bochum",
            "hoffenheim": "hoffenheim",
            "tsg hoffenheim": "hoffenheim",
            "wolfsburg": "wolfsburg",
            "vfl wolfsburg": "wolfsburg",
        },
    },
    "ligue-1": {
        "label": "Ligue 1",
        "slug": "Ligue_1",
        "output_prefix": "ligue-1",
        "competition": "Ligue 1",
        "team_aliases": {
            "angers": "angers",
            "angers sco": "angers",
            "aj auxerre": "auxerre",
            "auxerre": "auxerre",
            "brest": "brest",
            "stade brestois": "brest",
            "stade brestois 29": "brest",
            "havre": "havre",
            "havre ac": "havre",
            "lens": "lens",
            "rc lens": "lens",
            "lille": "lille",
            "losc": "lille",
            "losc lille": "lille",
            "lorient": "lorient",
            "fc lorient": "lorient",
            "lyon": "lyon",
            "olympique lyonnais": "lyon",
            "marseille": "marseille",
            "om": "marseille",
            "olympique de marseille": "marseille",
            "metz": "metz",
            "fc metz": "metz",
            "monaco": "monaco",
            "as monaco": "monaco",
            "nantes": "nantes",
            "fc nantes": "nantes",
            "nice": "nice",
            "ogc nice": "nice",
            "paris fc": "paris fc",
            "paris saint germain": "psg",
            "paris saint-germain": "psg",
            "psg": "psg",
            "rennes": "rennes",
            "stade rennais": "rennes",
            "stade rennais fc": "rennes",
            "strasbourg": "strasbourg",
            "rc strasbourg alsace": "strasbourg",
            "toulouse": "toulouse",
            "toulouse fc": "toulouse",
        },
    },
}


def _team_key(name: str, aliases: Dict[str, str]) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (name or "").strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return aliases.get(cleaned, cleaned)


def _season_label_to_understat(season_label: str) -> tuple[str, str]:
    if re.fullmatch(r"\d{4}-\d{4}", season_label):
        start_year = season_label.split("-")[0]
        return start_year, season_label
    raise ValueError(f"Unsupported season format: {season_label}")


def _safe_int(value, default: int = 0) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def _safe_float(value, default: float = 0.0) -> float:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


@dataclass
class ScrapeState:
    league_key: str
    league_slug: str
    league_label: str
    competition: str
    output_prefix: str
    team_aliases: Dict[str, str]
    season_label: str
    season_start: str
    session: requests.Session
    output_dir: str
    max_players: Optional[int] = None
    resume: bool = False


def _fetch_json(session: requests.Session, url: str) -> dict:
    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return response.json()


def _fetch_player_json(session: requests.Session, player_url: str) -> Optional[dict]:
    """
    GET getPlayerData/{id}. Returns None if Understat has no page (404/410) for this id
    (league list can still reference removed/merged players). Other errors raise.
    """
    response = session.get(player_url, headers=HEADERS, timeout=30)
    if response.status_code in (404, 410):
        time.sleep(REQUEST_DELAY)
        return None
    response.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return response.json()


def scrape_season(state: ScrapeState) -> str:
    os.makedirs(state.output_dir, exist_ok=True)
    output_path = os.path.join(state.output_dir, f"{state.output_prefix}-player-match-logs-{state.season_label}.csv")
    progress_path = os.path.join(state.output_dir, f".understat-progress-{state.output_prefix}-{state.season_label}.json")

    done_players = set()
    rows: List[dict] = []
    if state.resume and os.path.exists(progress_path):
        with open(progress_path, "r", encoding="utf-8") as handle:
            progress = json.load(handle)
            done_players = set(progress.get("done_players", []))
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
        print(f"  Resuming: {len(done_players)} players already done, {len(rows)} rows loaded")

    print(f"\n{'=' * 64}")
    print(f"  Scraping Understat {state.league_label} {state.season_label}")
    print(f"{'=' * 64}")

    league_url = f"https://understat.com/getLeagueData/{state.league_slug}/{state.season_start}"
    league_payload = _fetch_json(state.session, league_url)
    players = league_payload["players"]
    dates = league_payload["dates"]

    if state.max_players is not None:
        players = players[: state.max_players]

    match_lookup: Dict[str, dict] = {}
    for item in dates:
        match_lookup[str(item["id"])] = {
            "date": str(item["datetime"]).split(" ")[0],
            "home_team": item["h"]["title"],
            "away_team": item["a"]["title"],
            "home_key": _team_key(item["h"]["title"], state.team_aliases),
            "away_key": _team_key(item["a"]["title"], state.team_aliases),
            "home_xg": _safe_float(item["xG"]["h"]),
            "away_xg": _safe_float(item["xG"]["a"]),
        }

    total_players = 0
    skipped_players = 0
    processed_players = 0
    player_fetch_failures = 0
    join_hits = 0
    join_misses = 0

    for player in players:
        player_id = str(player["id"])
        total_players += 1

        season_minutes = _safe_int(player.get("time"), 0)
        if season_minutes < MIN_SEASON_MINUTES:
            skipped_players += 1
            continue
        if player_id in done_players:
            continue

        print(f"  {player.get('player_name')} ({season_minutes}min)...", end="", flush=True)
        player_url = f"https://understat.com/getPlayerData/{player_id}"
        payload = _fetch_player_json(state.session, player_url)
        if payload is None:
            print(
                f" skip (404/410: no player page — often removed/renamed on Understat; id={player_id})",
                flush=True,
            )
            player_fetch_failures += 1
            done_players.add(player_id)
            with open(progress_path, "w", encoding="utf-8") as handle:
                json.dump({"done_players": sorted(done_players)}, handle)
            continue

        matches = payload.get("matches", [])
        shots = payload.get("shots", [])

        penalty_by_match: Dict[str, dict] = {}
        big_chance_by_match: Dict[str, dict] = {}
        for shot in shots:
            if str(shot.get("season")) != state.season_start:
                continue

            match_id = str(shot.get("match_id"))
            situation = str(shot.get("situation") or "")
            shot_xg = _safe_float(shot.get("xG"), 0.0)
            result = str(shot.get("result") or "")

            if situation == "Penalty":
                summary = penalty_by_match.setdefault(match_id, {"attempted": 0, "scored": 0})
                summary["attempted"] += 1
                if result == "Goal":
                    summary["scored"] += 1

            if situation != "Penalty" and shot_xg >= BIG_CHANCE_XG_THRESHOLD:
                summary = big_chance_by_match.setdefault(match_id, {"count": 0, "goals": 0, "misses": 0, "xg": 0.0})
                summary["count"] += 1
                summary["xg"] += shot_xg
                if result == "Goal":
                    summary["goals"] += 1
                else:
                    summary["misses"] += 1

        player_rows = 0
        for match in matches:
            if str(match.get("season")) != state.season_start:
                continue
            minutes = _safe_int(match.get("time"), 0)
            if minutes <= 0:
                continue

            match_id = str(match.get("id"))
            team_title = str(player.get("team_title") or match.get("h_team") or "")
            team_key = _team_key(team_title, state.team_aliases)
            match_meta = match_lookup.get(match_id)
            if match_meta is None:
                join_misses += 1
                continue

            if match_meta["home_key"] == team_key:
                is_home = True
                opponent = match_meta["away_team"]
                team_xg = match_meta["home_xg"]
                team_xga = match_meta["away_xg"]
            elif match_meta["away_key"] == team_key:
                is_home = False
                opponent = match_meta["home_team"]
                team_xg = match_meta["away_xg"]
                team_xga = match_meta["home_xg"]
            else:
                raw_h = _team_key(match.get("h_team", ""), state.team_aliases)
                raw_a = _team_key(match.get("a_team", ""), state.team_aliases)
                if raw_h == team_key:
                    is_home = True
                    opponent = match_meta["away_team"]
                    team_xg = match_meta["home_xg"]
                    team_xga = match_meta["away_xg"]
                elif raw_a == team_key:
                    is_home = False
                    opponent = match_meta["home_team"]
                    team_xg = match_meta["away_xg"]
                    team_xga = match_meta["home_xg"]
                else:
                    join_misses += 1
                    continue

            join_hits += 1
            penalties = penalty_by_match.get(match_id, {"attempted": 0, "scored": 0})
            big_chances = big_chance_by_match.get(match_id, {"count": 0, "goals": 0, "misses": 0, "xg": 0.0})
            rows.append(
                {
                    "season": state.season_label,
                    "competition": state.competition,
                    "match_date": match_meta["date"],
                    "team": team_title,
                    "opponent": opponent,
                    "is_home": 1 if is_home else 0,
                    "player_id": player_id,
                    "player_name": player.get("player_name", ""),
                    "position": match.get("position", "") or player.get("position", ""),
                    "started": "",
                    "minutes": minutes,
                    "goals": _safe_int(match.get("goals"), 0),
                    "assists": _safe_int(match.get("assists"), 0),
                    "shots": _safe_int(match.get("shots"), 0),
                    "shots_on_target": "",
                    "xg": round(_safe_float(match.get("xG"), 0.0), 6),
                    "npxg": round(_safe_float(match.get("npxG"), 0.0), 6),
                    "xa": round(_safe_float(match.get("xA"), 0.0), 6),
                    "big_chances": big_chances["count"],
                    "big_chance_goals": big_chances["goals"],
                    "big_chance_misses": big_chances["misses"],
                    "big_chance_xg": round(big_chances["xg"], 6),
                    "penalties_scored": penalties["scored"],
                    "penalties_attempted": penalties["attempted"],
                    "team_xg": round(team_xg, 6),
                    "team_xga": round(team_xga, 6),
                }
            )
            player_rows += 1

        print(f" {player_rows} matches")
        done_players.add(player_id)
        processed_players += 1

        if processed_players % 10 == 0:
            with open(progress_path, "w", encoding="utf-8") as handle:
                json.dump({"done_players": sorted(done_players)}, handle)

    fieldnames = [
        "season",
        "competition",
        "match_date",
        "team",
        "opponent",
        "is_home",
        "player_id",
        "player_name",
        "position",
        "started",
        "minutes",
        "goals",
        "assists",
        "shots",
        "shots_on_target",
        "xg",
        "npxg",
        "xa",
        "big_chances",
        "big_chance_goals",
        "big_chance_misses",
        "big_chance_xg",
        "penalties_scored",
        "penalties_attempted",
        "team_xg",
        "team_xga",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if os.path.exists(progress_path):
        os.remove(progress_path)

    join_total = join_hits + join_misses
    join_rate = (join_hits / join_total * 100.0) if join_total else 0.0
    print(f"\n  Saved: {output_path} ({len(rows):,} rows)")
    print("  QA")
    print(f"    Players seen:       {total_players:,}")
    print(f"    Players skipped:    {skipped_players:,}")
    print(f"    Players processed:  {processed_players:,}")
    if player_fetch_failures:
        print(f"    Player fetch 404/410: {player_fetch_failures:,} (skipped, no rows)")
    print(f"    Match joins:        {join_hits:,} hit / {join_misses:,} miss ({join_rate:.1f}% match rate)")

    return output_path


def main() -> None:
    global REQUEST_DELAY
    parser = argparse.ArgumentParser(description="Understat football player match-log scraper")
    parser.add_argument(
        "--league",
        nargs="+",
        default=["serie-a"],
        choices=sorted(LEAGUE_CONFIGS.keys()),
        help="League key(s) to scrape",
    )
    parser.add_argument("--season", nargs="+", help="Season(s) to scrape, for example 2025-2026")
    parser.add_argument("--out-dir", default=OUTPUT_DIR)
    parser.add_argument("--resume", action="store_true", help="Resume interrupted scrape")
    parser.add_argument("--max-players", type=int, help="Optional limit for testing")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY, help="Delay between requests in seconds")
    args = parser.parse_args()

    seasons = args.season or DEFAULT_SEASONS
    REQUEST_DELAY = args.delay

    session = requests.Session()
    print("\n" + "=" * 64)
    print("  IL MARGINE - Understat Football Scraper")
    print("=" * 64)
    print(f"  Leagues: {args.league}")
    print(f"  Seasons: {seasons}")
    print(f"  Output:  {args.out_dir}")
    print(f"  Delay:   {REQUEST_DELAY:.1f}s between requests")

    for league_key in args.league:
        config = LEAGUE_CONFIGS[league_key]
        for season_label in seasons:
            if season_label not in AVAILABLE_SEASONS:
                print(f"\n  Warning: {season_label} not in supported season list")
            season_start, normalized_label = _season_label_to_understat(season_label)
            output = scrape_season(
                ScrapeState(
                    league_key=league_key,
                    league_slug=config["slug"],
                    league_label=config["label"],
                    competition=config["competition"],
                    output_prefix=config["output_prefix"],
                    team_aliases=config["team_aliases"],
                    season_label=normalized_label,
                    season_start=season_start,
                    session=session,
                    output_dir=args.out_dir,
                    max_players=args.max_players,
                    resume=args.resume,
                )
            )

            with open(output, "r", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))

            unique_players = len({row["player_id"] for row in rows})
            unique_matches = len({(row["match_date"], row["team"], row["opponent"]) for row in rows})
            goals = sum(int(row.get("goals", 0) or 0) for row in rows)

            print(f"\n  {config['label']} {normalized_label} summary:")
            print(f"    Players:           {unique_players:,}")
            print(f"    Team-match rows:   {unique_matches:,}")
            print(f"    Player-match rows: {len(rows):,}")
            print(f"    Goals:             {goals:,}")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
