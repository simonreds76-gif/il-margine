#!/usr/bin/env python3
"""
Build a same-night penalty-duty review queue from FotMob match events.

This complements `goalscorer-penalty-review.py`:
  - settled review uses next-day player logs
  - live review uses FotMob match events for same-night visibility

The output is editorial only. It does not auto-edit any penalty boards.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import runpy
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).resolve().parents[1]
MATCHES_URL = "https://www.fotmob.com/api/data/matches"
MATCH_URL = "https://www.fotmob.com/api/data/match"
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.fotmob.com/",
}

LEAGUE_CONFIGS = {
    "serie-a": {
        "league_id": 55,
        "penalty_hierarchy": ROOT / "data" / "goalscorer" / "serie-a-penalty-takers.json",
        "context": ROOT / "data" / "goalscorer" / "penalty-duty-context.json",
        "context_history": ROOT / "data" / "goalscorer" / "live-history" / "penalty-duty-context-*.json",
        "output_csv": ROOT / "data" / "goalscorer" / "penalty-duty-live-review.csv",
        "output_json": ROOT / "data" / "goalscorer" / "penalty-duty-live-review.json",
    },
    "epl": {
        "league_id": 47,
        "penalty_hierarchy": ROOT / "data" / "goalscorer" / "epl-penalty-takers.json",
        "context": ROOT / "data" / "goalscorer" / "epl" / "penalty-duty-context.json",
        "context_history": ROOT / "data" / "goalscorer" / "epl" / "live-history" / "penalty-duty-context-*.json",
        "output_csv": ROOT / "data" / "goalscorer" / "epl-penalty-duty-live-review.csv",
        "output_json": ROOT / "data" / "goalscorer" / "epl-penalty-duty-live-review.json",
    },
    "la-liga": {
        "league_id": 87,
        "penalty_hierarchy": ROOT / "data" / "goalscorer" / "la-liga-penalty-takers.json",
        "context": ROOT / "data" / "goalscorer" / "la-liga" / "penalty-duty-context.json",
        "context_history": ROOT / "data" / "goalscorer" / "la-liga" / "live-history" / "penalty-duty-context-*.json",
        "output_csv": ROOT / "data" / "goalscorer" / "la-liga-penalty-duty-live-review.csv",
        "output_json": ROOT / "data" / "goalscorer" / "la-liga-penalty-duty-live-review.json",
    },
    "bundesliga": {
        "league_id": 54,
        "penalty_hierarchy": ROOT / "data" / "goalscorer" / "bundesliga-penalty-takers.json",
        "context": ROOT / "data" / "goalscorer" / "bundesliga" / "penalty-duty-context.json",
        "context_history": ROOT / "data" / "goalscorer" / "bundesliga" / "live-history" / "penalty-duty-context-*.json",
        "output_csv": ROOT / "data" / "goalscorer" / "bundesliga-penalty-duty-live-review.csv",
        "output_json": ROOT / "data" / "goalscorer" / "bundesliga-penalty-duty-live-review.json",
    },
    "ligue-1": {
        "league_id": 53,
        "penalty_hierarchy": ROOT / "data" / "goalscorer" / "ligue-1-penalty-takers.json",
        "context": ROOT / "data" / "goalscorer" / "ligue-1" / "penalty-duty-context.json",
        "context_history": ROOT / "data" / "goalscorer" / "ligue-1" / "live-history" / "penalty-duty-context-*.json",
        "output_csv": ROOT / "data" / "goalscorer" / "ligue-1-penalty-duty-live-review.csv",
        "output_json": ROOT / "data" / "goalscorer" / "ligue-1-penalty-duty-live-review.json",
    },
}

FIELDNAMES = [
    "date",
    "league",
    "review_source",
    "competition",
    "is_friendly",
    "evidence_strength",
    "match",
    "team",
    "opponent",
    "actual_taker",
    "actual_role_pre_match",
    "penalties_attempted",
    "penalties_scored",
    "distinct_takers_in_match",
    "minute",
    "event_type",
    "event_result",
    "primary_pre_match",
    "secondary_pre_match",
    "tertiary_pre_match",
    "primary_lineup_status",
    "secondary_lineup_status",
    "tertiary_lineup_status",
    "active_taker_pre_match",
    "active_slot_pre_match",
    "team_lineup_status",
    "review_type",
    "review_priority",
    "editorial_note",
    "context_generated_at",
    "context_source_path",
]

CLUB_FRIENDLY_NAMES = {"club friendlies", "club friendly"}


def _today_fotmob_date() -> str:
    return datetime.now(ZoneInfo("Europe/London")).strftime("%Y%m%d")


def _fotmob_date_window(end_date: str, days_back: int) -> List[str]:
    base = datetime.strptime(end_date, "%Y%m%d").replace(tzinfo=ZoneInfo("Europe/London"))
    return [
        (base - timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(max(days_back, 0), -1, -1)
    ]


def _fetch_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def _fetch_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_active_hierarchy(path: Path) -> tuple[List[str], Dict[str, dict]]:
    payload = _load_json(path)
    teams = {
        str(team): dict(entry)
        for team, entry in payload.items()
        if not str(team).startswith("_") and isinstance(entry, dict)
    }
    return list(teams), teams


def _resolve_active_team(observed_name: str, active_teams: List[str], team_name_match_score) -> str:
    observed = str(observed_name or "").strip()
    if not observed:
        return ""

    candidates = sorted(
        (
            (float(team_name_match_score(observed, candidate)), candidate)
            for candidate in active_teams
        ),
        key=lambda item: (item[0], item[1]),
        reverse=True,
    )
    if not candidates or candidates[0][0] < 0.82:
        return ""
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.08:
        return ""
    return candidates[0][1]


def _select_matches(
    leagues: Iterable[dict],
    *,
    domestic_league_id: int,
    active_teams: List[str],
    team_name_match_score,
) -> List[dict]:
    selected: List[dict] = []
    for league in leagues:
        competition = str(league.get("name") or "").strip()
        competition_key = competition.lower()
        is_domestic = league.get("id") == domestic_league_id
        is_friendly = competition_key in CLUB_FRIENDLY_NAMES
        if not is_domestic and not is_friendly:
            continue

        for raw_match in league.get("matches", []):
            match = dict(raw_match)
            home_observed = str(
                match.get("home", {}).get("longName")
                or match.get("home", {}).get("name")
                or ""
            ).strip()
            away_observed = str(
                match.get("away", {}).get("longName")
                or match.get("away", {}).get("name")
                or ""
            ).strip()
            home_canonical = _resolve_active_team(home_observed, active_teams, team_name_match_score)
            away_canonical = _resolve_active_team(away_observed, active_teams, team_name_match_score)
            if is_friendly and not home_canonical and not away_canonical:
                continue

            match["_competition"] = competition or "Domestic league"
            match["_is_friendly"] = is_friendly
            match["_home_canonical"] = home_canonical
            match["_away_canonical"] = away_canonical
            selected.append(match)
    return selected


def _write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _normalize_event_result(event_type: str) -> tuple[str, int]:
    key = (event_type or "").strip().lower()
    if key == "goal":
        return "scored", 1
    if key in {"attemptsaved", "miss", "post", "blocked", "shotsaved"}:
        return "missed", 0
    return "unknown", 0


def _extract_next_payload(html_text: str) -> dict:
    match = NEXT_DATA_RE.search(html_text)
    if not match:
        raise ValueError("Could not find __NEXT_DATA__ payload on FotMob page")
    return json.loads(match.group(1))


def _fetch_match_payload(match_id: int) -> dict:
    match_payload = _fetch_json(MATCH_URL, {"id": match_id})
    page_url = str(match_payload.get("pageUrl") or "").strip()
    if not page_url:
        raise ValueError(f"Missing pageUrl for match {match_id}")
    return _extract_next_payload(_fetch_text(f"https://www.fotmob.com{page_url}"))


def _expand_context_paths(paths: Iterable[Path]) -> List[Path]:
    expanded: List[Path] = []
    for path in paths:
        text = str(path)
        if "*" in text or "?" in text:
            expanded.extend(Path(item) for item in glob.glob(text))
        elif path.exists():
            expanded.append(path)
    return sorted(expanded)


def _context_quality(row: dict) -> int:
    score = 0
    if str(row.get("active_taker_pre_match") or "").strip():
        score += 4
    for field in ("primary_lineup_status", "secondary_lineup_status", "tertiary_lineup_status"):
        status = str(row.get(field) or "").strip().lower()
        if status and status != "unknown":
            score += 1
    team_status = str(row.get("team_lineup_status") or "").strip().lower()
    if team_status and team_status != "unknown":
        score += 1
    return score


def _load_context_map(paths: Iterable[Path]) -> Dict[tuple[str, str, str], dict]:
    loaded: Dict[tuple[str, str, str], dict] = {}
    for path in _expand_context_paths(paths):
        payload = _load_json(path)
        generated_at = str(payload.get("generated_at") or "")
        rows = payload.get("rows", [])
        if not isinstance(rows, list):
            continue

        for row in rows:
            item = dict(row)
            item["_generated_at"] = generated_at
            item["_source_path"] = _display_path(path)
            key = (
                str(item.get("match_date") or "").strip(),
                str(item.get("team_key") or "").strip(),
                str(item.get("opponent_key") or "").strip(),
            )
            if not all(key):
                continue
            current = loaded.get(key)
            if current is None:
                loaded[key] = item
                continue
            current_quality = _context_quality(current)
            item_quality = _context_quality(item)
            if item_quality > current_quality or (
                item_quality == current_quality
                and generated_at >= str(current.get("_generated_at") or "")
            ):
                loaded[key] = item
    return loaded


def _blank_context(
    *,
    league_key: str,
    match_date: str,
    team_name: str,
    team_key: str,
    opponent_name: str,
    opponent_key: str,
    home_team: str,
    away_team: str,
    is_home: bool,
    hierarchy: dict | None = None,
) -> dict:
    hierarchy = hierarchy or {}
    return {
        "league": league_key,
        "match_date": match_date,
        "home_team": home_team,
        "away_team": away_team,
        "team": team_name,
        "team_key": team_key,
        "opponent": opponent_name,
        "opponent_key": opponent_key,
        "is_home": int(is_home),
        "primary": str(hierarchy.get("primary") or ""),
        "secondary": str(hierarchy.get("secondary") or ""),
        "tertiary": str(hierarchy.get("tertiary") or ""),
        "primary_lineup_status": "",
        "secondary_lineup_status": "",
        "tertiary_lineup_status": "",
        "active_taker_pre_match": "",
        "active_slot_pre_match": "",
        "team_lineup_status": "unknown",
        "_generated_at": "",
        "_source_path": "",
    }


def _summarise_event_result(scored: int, attempts: int) -> str:
    if attempts <= 0:
        return "unknown"
    if scored == attempts:
        return "scored"
    if scored == 0:
        return "missed"
    return "mixed"


def _summarise_event_type(types: Iterable[str]) -> str:
    distinct = sorted({(value or "").strip() for value in types if (value or "").strip()})
    if not distinct:
        return "Penalty"
    if len(distinct) == 1:
        return distinct[0]
    return " / ".join(distinct)


def build_live_review_rows(league_key: str, fotmob_dates: Iterable[str]) -> List[dict]:
    config = LEAGUE_CONFIGS[league_key]
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    team_key_func = model_mod["_team_key"]

    penalty_review_mod = runpy.run_path(
        str(ROOT / "scripts" / "goalscorer-penalty-review.py"),
        run_name="goalscorer_penalty_review",
    )
    classify_review_type = penalty_review_mod["_classify_review_type"]
    build_editorial_note = penalty_review_mod["_build_editorial_note"]
    review_priority = penalty_review_mod["_review_priority"]

    penalty_utils = runpy.run_path(
        str(ROOT / "scripts" / "goalscorer_penalty_utils.py"),
        run_name="goalscorer_penalty_utils",
    )
    penalty_role_for_player = penalty_utils["penalty_role_for_player"]
    settlement_utils = runpy.run_path(
        str(ROOT / "scripts" / "settlement_utils.py"),
        run_name="goalscorer_settlement_utils",
    )
    team_name_match_score = settlement_utils["team_name_match_score"]

    context_map = _load_context_map([config["context"], config["context_history"]])
    active_teams, hierarchy_by_team = _load_active_hierarchy(config["penalty_hierarchy"])

    grouped_events: Dict[tuple[str, str, str, str], List[dict]] = defaultdict(list)
    distinct_takers_by_team_match: Dict[tuple[str, str, str], set[str]] = defaultdict(set)
    seen_match_ids: set[int] = set()

    for fotmob_date in fotmob_dates:
        matches_payload = _fetch_json(
            MATCHES_URL,
            {"date": fotmob_date, "timezone": "Europe/London", "ccode3": "GBR"},
        )
        leagues = matches_payload.get("leagues", [])
        league_matches = _select_matches(
            leagues,
            domestic_league_id=int(config["league_id"]),
            active_teams=active_teams,
            team_name_match_score=team_name_match_score,
        )

        for match in league_matches:
            status = match.get("status", {}) or {}
            if not status.get("started") and not status.get("finished"):
                continue
            match_id = match.get("id")
            if not match_id:
                continue
            match_id = int(match_id)
            if match_id in seen_match_ids:
                continue
            seen_match_ids.add(match_id)

            try:
                match_payload = _fetch_match_payload(match_id)
            except Exception as exc:
                print(f"WARNING: failed to fetch FotMob match {match_id}: {exc}")
                continue

            page_props = match_payload.get("props", {}).get("pageProps", {})
            general = page_props.get("general", {}) or {}
            content = page_props.get("content", {}) or {}
            shotmap = content.get("shotmap", {}) or {}
            shots = shotmap.get("shots", [])
            if not isinstance(shots, list):
                shots = []

            home_team = str(
                match.get("_home_canonical")
                or general.get("homeTeam", {}).get("name")
                or match.get("home", {}).get("longName")
                or match.get("home", {}).get("name")
                or ""
            ).strip()
            away_team = str(
                match.get("_away_canonical")
                or general.get("awayTeam", {}).get("name")
                or match.get("away", {}).get("longName")
                or match.get("away", {}).get("name")
                or ""
            ).strip()
            match_date = str(general.get("matchTimeUTCDate") or status.get("utcTime") or "").strip()[:10]
            if not home_team or not away_team or not match_date:
                continue

            home_id = int(general.get("homeTeam", {}).get("id") or match.get("home", {}).get("id") or 0)
            away_id = int(general.get("awayTeam", {}).get("id") or match.get("away", {}).get("id") or 0)
            tracked_team_ids = {
                team_id
                for team_id, canonical_name in (
                    (home_id, str(match.get("_home_canonical") or "")),
                    (away_id, str(match.get("_away_canonical") or "")),
                )
                if canonical_name
            }
            is_friendly = bool(match.get("_is_friendly"))
            competition = str(match.get("_competition") or "").strip()

            for shot in shots:
                if str(shot.get("situation") or "").strip().lower() != "penalty":
                    continue
                if str(shot.get("period") or "").strip().lower() == "penaltyshootout":
                    continue

                team_id = int(shot.get("teamId") or 0)
                if is_friendly and team_id not in tracked_team_ids:
                    continue
                if team_id == home_id:
                    team_name = home_team
                    opponent_name = away_team
                    is_home = True
                elif team_id == away_id:
                    team_name = away_team
                    opponent_name = home_team
                    is_home = False
                else:
                    continue

                player_name = str(shot.get("fullName") or shot.get("playerName") or "").strip()
                if not player_name:
                    continue

                team_key = team_key_func(team_name)
                opponent_key = team_key_func(opponent_name)
                if not team_key or not opponent_key:
                    continue

                minute = int(shot.get("min") or 0)
                event_type = str(shot.get("eventType") or "").strip()
                event_result, scored_flag = _normalize_event_result(event_type)
                team_match_key = (match_date, team_key, opponent_key)
                taker_key = (match_date, team_key, opponent_key, player_name)

                distinct_takers_by_team_match[team_match_key].add(player_name)
                grouped_events[taker_key].append(
                    {
                        "date": match_date,
                        "match": f"{home_team} vs {away_team}",
                        "team": team_name,
                        "opponent": opponent_name,
                        "team_key": team_key,
                        "opponent_key": opponent_key,
                        "is_home": is_home,
                        "player_name": player_name,
                        "minute": minute,
                        "event_type": event_type,
                        "event_result": event_result,
                        "penalties_scored": scored_flag,
                        "competition": competition,
                        "is_friendly": is_friendly,
                    }
                )

    rows: List[dict] = []
    for (match_date, team_key, opponent_key, player_name), events in grouped_events.items():
        sample = events[0]
        context = dict(
            context_map.get((match_date, team_key, opponent_key))
            or _blank_context(
                league_key=league_key,
                match_date=match_date,
                team_name=sample["team"],
                team_key=team_key,
                opponent_name=sample["opponent"],
                opponent_key=opponent_key,
                home_team=sample["match"].split(" vs ")[0],
                away_team=sample["match"].split(" vs ")[1],
                is_home=bool(sample["is_home"]),
                hierarchy=hierarchy_by_team.get(sample["team"], {}),
            )
        )

        hierarchy = {
            "primary": context.get("primary", ""),
            "secondary": context.get("secondary", ""),
            "tertiary": context.get("tertiary", ""),
        }
        actual_role = penalty_role_for_player(hierarchy, player_name)
        attempts = len(events)
        scored = sum(int(event.get("penalties_scored") or 0) for event in events)
        minute_label = ", ".join(str(event["minute"]) for event in sorted(events, key=lambda item: item["minute"]) if event["minute"])
        distinct_takers = len(distinct_takers_by_team_match[(match_date, team_key, opponent_key)])
        review_type = classify_review_type(
            context=context,
            actual_role=actual_role,
            distinct_takers_in_match=distinct_takers,
        )
        is_friendly = bool(sample.get("is_friendly"))
        priority = review_priority(review_type)
        if is_friendly and priority == "high":
            priority = "medium"
        evidence_strength = "supporting" if is_friendly else "competitive"
        editorial_note = build_editorial_note(
            actual_taker=player_name,
            attempts=attempts,
            event_result=_summarise_event_result(scored, attempts),
            team=sample["team"],
            opponent=sample["opponent"],
            context=context,
            review_type=review_type,
        )
        if is_friendly:
            editorial_note = (
                "Club-friendly supporting evidence only; do not change the hierarchy from this event alone. "
                + editorial_note
            )

        rows.append(
            {
                "date": match_date,
                "league": league_key,
                "review_source": "fotmob_friendly" if is_friendly else "fotmob_live",
                "competition": sample.get("competition", ""),
                "is_friendly": int(is_friendly),
                "evidence_strength": evidence_strength,
                "match": sample["match"],
                "team": sample["team"],
                "opponent": sample["opponent"],
                "actual_taker": player_name,
                "actual_role_pre_match": actual_role,
                "penalties_attempted": attempts,
                "penalties_scored": scored,
                "distinct_takers_in_match": distinct_takers,
                "minute": minute_label,
                "event_type": _summarise_event_type(event["event_type"] for event in events),
                "event_result": _summarise_event_result(scored, attempts),
                "primary_pre_match": context.get("primary", ""),
                "secondary_pre_match": context.get("secondary", ""),
                "tertiary_pre_match": context.get("tertiary", ""),
                "primary_lineup_status": context.get("primary_lineup_status", ""),
                "secondary_lineup_status": context.get("secondary_lineup_status", ""),
                "tertiary_lineup_status": context.get("tertiary_lineup_status", ""),
                "active_taker_pre_match": context.get("active_taker_pre_match", ""),
                "active_slot_pre_match": context.get("active_slot_pre_match", ""),
                "team_lineup_status": context.get("team_lineup_status", ""),
                "review_type": review_type,
                "review_priority": priority,
                "editorial_note": editorial_note,
                "context_generated_at": context.get("_generated_at", ""),
                "context_source_path": context.get("_source_path", ""),
            }
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    rows.sort(
        key=lambda row: (
            row.get("date", ""),
            priority_order.get(str(row.get("review_priority", "medium")), 9),
            row.get("team", ""),
            row.get("actual_taker", ""),
        ),
        reverse=True,
    )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a same-night FotMob penalty review queue")
    parser.add_argument("--league", choices=sorted(LEAGUE_CONFIGS), required=True, help="League to fetch")
    parser.add_argument("--date", default=_today_fotmob_date(), help="FotMob date in YYYYMMDD format")
    parser.add_argument("--days-back", type=int, default=6, help="Include this many days before --date in the live review queue")
    parser.add_argument("--output", default="", help="Override CSV output path")
    parser.add_argument("--json-output", default="", help="Override JSON output path")
    args = parser.parse_args()

    config = LEAGUE_CONFIGS[args.league]
    rows = build_live_review_rows(args.league, _fotmob_date_window(args.date, args.days_back))
    output_csv = Path(args.output) if args.output else config["output_csv"]
    output_json = Path(args.json_output) if args.json_output else config["output_json"]
    _write_csv(output_csv, rows)
    _write_json(
        output_json,
        {
            "schema_version": 1,
            "generated_at": datetime.now(ZoneInfo("UTC")).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "league": args.league,
            "row_count": len(rows),
            "rows": rows,
        },
    )

    print(f"League:      {args.league}")
    print(f"FotMob date: {args.date}")
    print(f"Days back:   {args.days_back}")
    print(f"Rows:        {len(rows)}")
    print(f"Saved CSV:   {output_csv}")
    print(f"Saved JSON:  {output_json}")


if __name__ == "__main__":
    main()
