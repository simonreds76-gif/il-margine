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
        "hierarchy": ROOT / "data" / "goalscorer" / "serie-a-penalty-takers.json",
        "context": ROOT / "data" / "goalscorer" / "penalty-duty-context.json",
        "context_history": ROOT / "data" / "goalscorer" / "live-history" / "penalty-duty-context-*.json",
        "output_csv": ROOT / "data" / "goalscorer" / "penalty-duty-live-review.csv",
        "output_json": ROOT / "data" / "goalscorer" / "penalty-duty-live-review.json",
    },
    "epl": {
        "league_id": 47,
        "hierarchy": ROOT / "data" / "goalscorer" / "epl-penalty-takers.json",
        "context": ROOT / "data" / "goalscorer" / "epl" / "penalty-duty-context.json",
        "context_history": ROOT / "data" / "goalscorer" / "epl" / "live-history" / "penalty-duty-context-*.json",
        "output_csv": ROOT / "data" / "goalscorer" / "epl-penalty-duty-live-review.csv",
        "output_json": ROOT / "data" / "goalscorer" / "epl-penalty-duty-live-review.json",
    },
    "la-liga": {
        "league_id": 87,
        "hierarchy": ROOT / "data" / "goalscorer" / "la-liga-penalty-takers.json",
        "context": ROOT / "data" / "goalscorer" / "la-liga" / "penalty-duty-context.json",
        "context_history": ROOT / "data" / "goalscorer" / "la-liga" / "live-history" / "penalty-duty-context-*.json",
        "output_csv": ROOT / "data" / "goalscorer" / "la-liga-penalty-duty-live-review.csv",
        "output_json": ROOT / "data" / "goalscorer" / "la-liga-penalty-duty-live-review.json",
    },
    "bundesliga": {
        "league_id": 54,
        "hierarchy": ROOT / "data" / "goalscorer" / "bundesliga-penalty-takers.json",
        "context": ROOT / "data" / "goalscorer" / "bundesliga" / "penalty-duty-context.json",
        "context_history": ROOT / "data" / "goalscorer" / "bundesliga" / "live-history" / "penalty-duty-context-*.json",
        "output_csv": ROOT / "data" / "goalscorer" / "bundesliga-penalty-duty-live-review.csv",
        "output_json": ROOT / "data" / "goalscorer" / "bundesliga-penalty-duty-live-review.json",
    },
    "ligue-1": {
        "league_id": 53,
        "hierarchy": ROOT / "data" / "goalscorer" / "ligue-1-penalty-takers.json",
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
    "actual_taker_match_status",
    "primary_on_pitch_at_penalty",
    "secondary_on_pitch_at_penalty",
    "tertiary_on_pitch_at_penalty",
    "actual_taker_on_pitch_at_penalty",
    "review_type",
    "review_priority",
    "editorial_note",
    "context_generated_at",
    "context_source_path",
]


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


def _write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
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


def _load_hierarchy_map(path: Path, team_key_func) -> Dict[str, dict]:
    payload = _load_json(path)
    loaded: Dict[str, dict] = {}
    if not isinstance(payload, dict):
        return loaded
    for team_name, entry in payload.items():
        if str(team_name).startswith("_") or not isinstance(entry, dict):
            continue
        key = str(team_key_func(str(team_name)) or "").strip()
        if not key:
            continue
        last_verified = entry.get("last_verified") if isinstance(entry.get("last_verified"), dict) else {}
        loaded[key] = {
            "primary": str(entry.get("primary") or "").strip(),
            "secondary": str(entry.get("secondary") or "").strip(),
            "tertiary": str(entry.get("tertiary") or "").strip(),
            "_generated_at": str(last_verified.get("date") or entry.get("public_updated_at") or ""),
            "_source_path": _display_path(path),
        }
    return loaded


def _apply_hierarchy_fallback(context: dict, fallback: dict | None) -> dict:
    merged = dict(context)
    if not fallback:
        return merged
    for field in ("primary", "secondary", "tertiary"):
        if not str(merged.get(field) or "").strip():
            merged[field] = str(fallback.get(field) or "").strip()
    if not str(merged.get("_generated_at") or "").strip():
        merged["_generated_at"] = str(fallback.get("_generated_at") or "")
    if not str(merged.get("_source_path") or "").strip():
        merged["_source_path"] = str(fallback.get("_source_path") or "")
    return merged


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
) -> dict:
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
        "primary": "",
        "secondary": "",
        "tertiary": "",
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


def _substitution_minute(player: dict, event_type: str) -> int | None:
    performance = player.get("performance") if isinstance(player.get("performance"), dict) else {}
    events = performance.get("substitutionEvents") or []
    for event in events:
        if str(event.get("type") or "").strip().lower() == event_type.lower():
            try:
                return int(event.get("time"))
            except (TypeError, ValueError):
                return None
    return None


def _player_at_penalty_status(lineup_side: dict, player_name: str, minute: int, best_name_match) -> str:
    if not player_name:
        return "-"
    if not lineup_side:
        return "Unknown - lineup unavailable"

    for bucket in ("starters", "subs", "unavailable"):
        players = lineup_side.get(bucket) or []
        names = [str(player.get("name") or "").strip() for player in players]
        matched_name = best_name_match(player_name, names)
        if not matched_name:
            continue
        player = next(item for item in players if str(item.get("name") or "").strip() == matched_name)
        if bucket == "starters":
            sub_out = _substitution_minute(player, "subOut")
            if sub_out is not None and sub_out <= minute:
                return f"No - starter, off {sub_out}'"
            return "Yes - starter"
        if bucket == "subs":
            sub_in = _substitution_minute(player, "subIn")
            if sub_in is None:
                return "No - unused bench"
            if sub_in <= minute:
                return f"Yes - bench, on {sub_in}'"
            return f"No - bench, on {sub_in}'"

        reason = str(
            player.get("unavailableReason")
            or player.get("reason")
            or (player.get("injury") or {}).get("description")
            or "unavailable"
        ).strip()
        return f"No - {reason}"

    return "No - not in match squad"


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
    best_name_match = penalty_utils["best_name_match"]

    context_map = _load_context_map([config["context"], config["context_history"]])
    hierarchy_map = _load_hierarchy_map(config["hierarchy"], team_key_func)

    grouped_events: Dict[tuple[str, str, str, str], List[dict]] = defaultdict(list)
    distinct_takers_by_team_match: Dict[tuple[str, str, str], set[str]] = defaultdict(set)
    seen_match_ids: set[int] = set()

    for fotmob_date in fotmob_dates:
        matches_payload = _fetch_json(
            MATCHES_URL,
            {"date": fotmob_date, "timezone": "Europe/London", "ccode3": "GBR"},
        )
        leagues = matches_payload.get("leagues", [])
        league_matches = [
            match
            for league in leagues
            if league.get("id") == config["league_id"]
            for match in league.get("matches", [])
        ]

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
            lineup = content.get("lineup", {}) or {}
            shots = shotmap.get("shots", [])
            if not isinstance(shots, list):
                shots = []

            home_team = str(
                general.get("homeTeam", {}).get("name")
                or match.get("home", {}).get("longName")
                or match.get("home", {}).get("name")
                or ""
            ).strip()
            away_team = str(
                general.get("awayTeam", {}).get("name")
                or match.get("away", {}).get("longName")
                or match.get("away", {}).get("name")
                or ""
            ).strip()
            match_date = str(general.get("matchTimeUTCDate") or status.get("utcTime") or "").strip()[:10]
            if not home_team or not away_team or not match_date:
                continue

            home_id = int(general.get("homeTeam", {}).get("id") or match.get("home", {}).get("id") or 0)
            away_id = int(general.get("awayTeam", {}).get("id") or match.get("away", {}).get("id") or 0)

            for shot in shots:
                if str(shot.get("situation") or "").strip().lower() != "penalty":
                    continue
                if str(shot.get("period") or "").strip().lower() == "penaltyshootout":
                    continue

                team_id = int(shot.get("teamId") or 0)
                if team_id == home_id:
                    team_name = home_team
                    opponent_name = away_team
                    is_home = True
                    lineup_side = lineup.get("homeTeam", {}) or {}
                elif team_id == away_id:
                    team_name = away_team
                    opponent_name = home_team
                    is_home = False
                    lineup_side = lineup.get("awayTeam", {}) or {}
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
                        "lineup_side": lineup_side,
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
            )
        )
        context = _apply_hierarchy_fallback(context, hierarchy_map.get(team_key))

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
        penalty_minute = min((int(event.get("minute") or 0) for event in events), default=0)
        lineup_side = sample.get("lineup_side") if isinstance(sample.get("lineup_side"), dict) else {}
        primary_pitch = _player_at_penalty_status(lineup_side, hierarchy["primary"], penalty_minute, best_name_match)
        secondary_pitch = _player_at_penalty_status(lineup_side, hierarchy["secondary"], penalty_minute, best_name_match)
        tertiary_pitch = _player_at_penalty_status(lineup_side, hierarchy["tertiary"], penalty_minute, best_name_match)
        actual_pitch = _player_at_penalty_status(lineup_side, player_name, penalty_minute, best_name_match)
        review_type = classify_review_type(
            context=context,
            actual_role=actual_role,
            distinct_takers_in_match=distinct_takers,
        )

        rows.append(
            {
                "date": match_date,
                "league": league_key,
                "review_source": "fotmob_live",
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
                "team_lineup_status": "confirmed" if lineup_side else context.get("team_lineup_status", ""),
                "actual_taker_match_status": actual_pitch,
                "primary_on_pitch_at_penalty": primary_pitch,
                "secondary_on_pitch_at_penalty": secondary_pitch,
                "tertiary_on_pitch_at_penalty": tertiary_pitch,
                "actual_taker_on_pitch_at_penalty": actual_pitch,
                "review_type": review_type,
                "review_priority": review_priority(review_type),
                "editorial_note": build_editorial_note(
                    actual_taker=player_name,
                    attempts=attempts,
                    event_result=_summarise_event_result(scored, attempts),
                    team=sample["team"],
                    opponent=sample["opponent"],
                    context=context,
                    review_type=review_type,
                ),
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
