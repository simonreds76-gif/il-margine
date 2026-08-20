#!/usr/bin/env python3
"""Settle GK Saves v1 shadow signals from API-Football player statistics.

The script is daily-only and hard-capped. It never substitutes team saves for
the named goalkeeper's own saves.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from football_team_names import football_form_team_key
from goalkeeper_saves_live import ROOT, parse_float, person_match_score


BASE_URL = "https://v3.football.api-sports.io"
DEFAULT_SIGNALS = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-shadow-signals.csv"
DEFAULT_ODDS = ROOT / "data" / "goalkeeper-saves" / "gk-saves-odds-history.csv"
LEAGUES = {
    "epl": 39,
    "serie-a": 135,
    "la-liga": 140,
    "bundesliga": 78,
    "ligue-1": 61,
}
FINISHED = {"FT", "AET", "PEN"}


def load_env() -> None:
    for path in (ROOT / ".env.local", ROOT / "env.local"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def request_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    key = (os.environ.get("API_FOOTBALL_KEY") or "").strip()
    if not key:
        raise RuntimeError("API_FOOTBALL_KEY is missing")
    response = requests.get(
        f"{BASE_URL}/{path.lstrip('/')}",
        params=params,
        headers={"x-apisports-key": key, "Accept": "application/json", "User-Agent": "il-margine/gk-saves-shadow"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def season_for_day(day: date) -> int:
    return day.year if day.month >= 8 else day.year - 1


def fixture_match(row: dict[str, Any], home: str, away: str) -> bool:
    teams = row.get("teams") or {}
    source_home = football_form_team_key((teams.get("home") or {}).get("name"))
    source_away = football_form_team_key((teams.get("away") or {}).get("name"))
    return source_home == football_form_team_key(home) and source_away == football_form_team_key(away)


def player_saves(payload: dict[str, Any], goalkeeper: str) -> tuple[int | None, dict[str, Any]]:
    matches: list[tuple[int, int, dict[str, Any]]] = []
    for team in payload.get("response") or []:
        for item in team.get("players") or []:
            player = item.get("player") or {}
            score = person_match_score(goalkeeper, player.get("name"))
            if not score:
                continue
            for stats in item.get("statistics") or []:
                games = stats.get("games") or {}
                goals = stats.get("goals") or {}
                saves = goals.get("saves")
                try:
                    actual = int(float(saves))
                except (TypeError, ValueError):
                    continue
                matches.append(
                    (
                        score,
                        actual,
                        {
                            "player_id": player.get("id"),
                            "player_name": player.get("name"),
                            "minutes": games.get("minutes"),
                            "position": games.get("position"),
                            "substitute": games.get("substitute"),
                        },
                    )
                )
    if not matches:
        return None, {}
    matches.sort(key=lambda item: item[0], reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        return None, {"error": "ambiguous_player"}
    return matches[0][1], matches[0][2]


def latest_close(
    odds_rows: list[dict[str, str]],
    signal: dict[str, str],
) -> float | None:
    candidates = []
    for row in odds_rows:
        if str(row.get("event_id") or "") != str(signal.get("event_id") or ""):
            continue
        if str(row.get("line") or "") != str(signal.get("line") or ""):
            continue
        if str(row.get("side") or "").casefold() != str(signal.get("side") or "").casefold():
            continue
        if person_match_score(row.get("player"), signal.get("goalkeeper")) < 80:
            continue
        if str(row.get("captured_at") or "") >= str(signal.get("kickoff_at") or ""):
            continue
        price = parse_float(row.get("odds_decimal"))
        if price and price > 1.0:
            candidates.append((str(row.get("captured_at") or ""), price))
    return max(candidates)[1] if candidates else None


def settle_row(signal: dict[str, str], actual: int, close_odds: float | None, settled_at: str) -> None:
    line = parse_float(signal.get("line")) or 0.0
    price = parse_float(signal.get("odds_decimal")) or 0.0
    stake = parse_float(signal.get("stake_units")) or 0.0
    side = str(signal.get("side") or "over").casefold()
    won = actual > line if side == "over" else actual < line
    lost = actual < line if side == "over" else actual > line
    if won:
        result, pnl = "won", stake * (price - 1.0)
    elif lost:
        result, pnl = "lost", -stake
    else:
        result, pnl = "push", 0.0
    signal.update(
        {
            "status": result,
            "result": result,
            "actual_saves": str(actual),
            "pnl_units": f"{pnl:.4f}",
            "settled_at": settled_at,
            "settlement_source": "api_football_fixture_players",
            "close_odds": f"{close_odds:.4f}" if close_odds else "",
            "clv": f"{(price / close_odds) - 1.0:.6f}" if close_odds else "",
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle Goalkeeper Saves v1 shadow signals")
    parser.add_argument("--signals", type=Path, default=DEFAULT_SIGNALS)
    parser.add_argument("--odds", type=Path, default=DEFAULT_ODDS)
    parser.add_argument("--max-requests", type=int, default=10)
    args = parser.parse_args()
    load_env()

    fields, signals = read_csv(args.signals)
    if not signals:
        print("No goalkeeper-save shadow signals to settle.")
        return
    pending = [row for row in signals if str(row.get("status") or "").lower() == "pending"]
    today = datetime.now(UTC).date()
    pending = [row for row in pending if (date.fromisoformat(str(row["match_date"])[:10]) <= today)]
    if not pending:
        print("No due goalkeeper-save shadow signals.")
        return

    odds_rows = read_csv(args.odds)[1]
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for signal in pending:
        groups[(str(signal.get("league") or ""), str(signal.get("match_date") or "")[:10])].append(signal)

    requests_used = 0
    settled = 0
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for (league, day_text), group in sorted(groups.items()):
        if requests_used >= args.max_requests or league not in LEAGUES:
            break
        day = date.fromisoformat(day_text)
        fixture_payload = request_json(
            "fixtures",
            {"league": LEAGUES[league], "season": season_for_day(day), "date": day_text, "status": "FT-AET-PEN"},
        )
        requests_used += 1
        fixtures = fixture_payload.get("response") or []
        for signal in group:
            if requests_used >= args.max_requests:
                break
            fixture = next(
                (
                    row for row in fixtures
                    if fixture_match(row, signal.get("home_team", ""), signal.get("away_team", ""))
                    and str(((row.get("fixture") or {}).get("status") or {}).get("short") or "") in FINISHED
                ),
                None,
            )
            fixture_id = ((fixture or {}).get("fixture") or {}).get("id")
            if not fixture_id:
                continue
            players_payload = request_json("fixtures/players", {"fixture": fixture_id})
            requests_used += 1
            actual, metadata = player_saves(players_payload, str(signal.get("goalkeeper") or ""))
            if actual is None:
                continue
            # The signal gate already required a confirmed starter. The player
            # payload must independently identify a goalkeeper, not an outfield
            # name collision.
            if str(metadata.get("position") or "").upper() not in {"G", "GK", "GOALKEEPER"}:
                continue
            settle_row(signal, actual, latest_close(odds_rows, signal), now)
            settled += 1

    write_csv(args.signals, fields, signals)
    print(json.dumps({"settled": settled, "requests_used": requests_used, "max_requests": args.max_requests}, sort_keys=True))


if __name__ == "__main__":
    main()
