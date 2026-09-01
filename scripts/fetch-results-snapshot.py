#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Dict, List

import requests

_RS_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_RS_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_RS_REPO_ROOT))

from scripts._lib.run_status import run_status

from api_football_match_stats import fetch_api_football_results
from fotmob_match_stats import fetch_fotmob_recent_results
from settlement_utils import (
    LEAGUE_CODES,
    ROOT,
    build_fixture_key,
    collect_target_dates,
    ensure_snapshot_dir,
    normalize_team_name,
    parse_isoish_date,
    snapshot_path_for,
)

BASE_URL = "https://www.football-data.co.uk"
SHORTLIST_SETTLED = ROOT / "data" / "shortlist" / "settled-pnl.csv"
TEAM_SHOTS_SIGNALS = ROOT / "data" / "team-shots" / "shadow" / "team-shots-shadow-signals.csv"
TEAM_SHOTS_V3_RESEARCH = ROOT / "data" / "football-form" / "team-shots-v3-ema20-clv-monitor.csv"
CORNERS_V0_RESEARCH = ROOT / "data" / "football-form" / "corners-v0-clv-monitor.csv"
DEFAULT_PENDING_PATHS = [SHORTLIST_SETTLED, TEAM_SHOTS_SIGNALS, TEAM_SHOTS_V3_RESEARCH, CORNERS_V0_RESEARCH]
DEFAULT_API_FOOTBALL_MAX_REQUESTS = 10


def optional_int(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            raw_line = raw_line.strip()
            if raw_line and not raw_line.startswith("#") and "=" in raw_line:
                key, value = raw_line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def fetch_football_data_results(league: str) -> tuple[Dict[str, dict], dict]:
    code = LEAGUE_CODES.get(league)
    if not code:
        return {}, {"source": "football-data", "error": "unknown league"}

    now = datetime.now(UTC)
    start_year = now.year if now.month >= 8 else now.year - 1
    season = f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"
    url = f"{BASE_URL}/mmz4281/{season}/{code}.csv"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {}, {
            "source": "football-data",
            "error": str(exc),
            "football_data_latest": None,
            "football_data_count": 0,
            "lag_days": None,
        }

    results: Dict[str, dict] = {}
    latest_available = None
    reader = csv.DictReader(io.StringIO(response.text))
    for row in reader:
        match_date = parse_isoish_date(row.get("Date", ""))
        if match_date is None:
            continue
        latest_available = max(latest_available, match_date.isoformat()) if latest_available else match_date.isoformat()
        home = row.get("HomeTeam", "")
        away = row.get("AwayTeam", "")
        home_shots = optional_int(row.get("HS"))
        away_shots = optional_int(row.get("AS"))
        home_sot = optional_int(row.get("HST"))
        away_sot = optional_int(row.get("AST"))
        home_corners = optional_int(row.get("HC"))
        away_corners = optional_int(row.get("AC"))
        if all(value is None for value in (home_shots, away_shots, home_sot, away_sot, home_corners, away_corners)):
            continue
        key = build_fixture_key(match_date, home, away)
        results[key] = {
            "home_team": normalize_team_name(home),
            "away_team": normalize_team_name(away),
            "home_shots": home_shots,
            "away_shots": away_shots,
            "home_sot": home_sot,
            "away_sot": away_sot,
            "home_corners": home_corners,
            "away_corners": away_corners,
            "total_corners": (
                home_corners + away_corners
                if home_corners is not None and away_corners is not None
                else None
            ),
            "home_fouls": optional_int(row.get("HF")),
            "away_fouls": optional_int(row.get("AF")),
            "home_yellow_cards": optional_int(row.get("HY")),
            "away_yellow_cards": optional_int(row.get("AY")),
            "home_red_cards": optional_int(row.get("HR")),
            "away_red_cards": optional_int(row.get("AR")),
            "referee": str(row.get("Referee") or "").strip() or None,
            "source": "football-data",
        }

    lag_days = None
    if latest_available:
        lag_days = (datetime.now(UTC).date() - datetime.fromisoformat(latest_available).date()).days

    return results, {
        "source": "football-data",
        "football_data_latest": latest_available,
        "football_data_count": len(results),
        "lag_days": lag_days,
        "error": None,
    }


def load_pending_rows(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if (row.get("settled") or "").strip() == "pending" or (row.get("result") or "").strip() == "pending":
                    rows.append(dict(row))
    return rows


def _split_match(row: dict) -> tuple[str, str]:
    home = str(row.get("home_team", "") or "").strip()
    away = str(row.get("away_team", "") or "").strip()
    if home and away:
        return home, away
    match = str(row.get("match", "") or "").strip()
    if " vs " in match:
        parts = match.split(" vs ", 1)
        return parts[0].strip(), parts[1].strip()
    return "", ""


def collect_target_fixtures(rows: List[dict]) -> Dict[str, List[dict]]:
    fixtures_by_league: Dict[str, List[dict]] = {}
    seen: set[str] = set()
    for row in rows:
        league = str(row.get("league", "") or "").strip()
        if not league:
            continue
        raw_date = ""
        for field in ("kick_off", "kickoff_iso", "kickoff_utc", "match_date", "fixture_date", "date", "file_date"):
            raw_date = str(row.get(field, "") or "").strip()
            if raw_date:
                break
        match_date = parse_isoish_date(raw_date)
        if match_date is None:
            continue
        home_team, away_team = _split_match(row)
        if not home_team or not away_team:
            continue
        key = f"{league}|{match_date.isoformat()}|{normalize_team_name(home_team)}|{normalize_team_name(away_team)}"
        if key in seen:
            continue
        seen.add(key)
        fixtures_by_league.setdefault(league, []).append(
            {
                "date": match_date.isoformat(),
                "home_team": home_team,
                "away_team": away_team,
            }
        )
    return fixtures_by_league


def fixture_present(results: Dict[str, dict], fixture: dict) -> bool:
    try:
        match_date = datetime.fromisoformat(str(fixture["date"])).date()
    except ValueError:
        return False
    for delta in (-1, 0, 1):
        key = build_fixture_key(
            match_date + timedelta(days=delta),
            fixture["home_team"],
            fixture["away_team"],
        )
        if key in results:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a committed football results snapshot for settlement")
    parser.add_argument("--date", type=str, default=None, help="Snapshot date in YYYY-MM-DD (defaults to today UTC)")
    parser.add_argument(
        "--pending-path",
        dest="pending_paths",
        action="append",
        default=None,
        help="Relative or absolute CSV path to scan for pending rows. Repeat to add more paths.",
    )
    parser.add_argument(
        "--api-football-max-requests",
        type=int,
        default=DEFAULT_API_FOOTBALL_MAX_REQUESTS,
        help="Hard cap on API-Football fallback requests per run (default: 10).",
    )
    args = parser.parse_args()

    load_env()
    snapshot_day = parse_isoish_date(args.date or "") or datetime.now(UTC).date()
    pending_paths = args.pending_paths or [str(path.relative_to(ROOT)) for path in DEFAULT_PENDING_PATHS]
    pending_rows = load_pending_rows(pending_paths)
    target_dates_by_league = collect_target_dates(
        pending_rows,
        kickoff_fields=("kick_off", "kickoff_iso", "kickoff_utc"),
        date_fields=("match_date", "fixture_date", "date", "file_date"),
    )
    target_fixtures_by_league = collect_target_fixtures(pending_rows)

    payload: dict = {
        "snapshot_date": snapshot_day.isoformat(),
        "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "leagues": {},
    }
    api_football_requests_remaining = max(0, args.api_football_max_requests)

    for league in sorted(LEAGUE_CODES.keys()):
        fixtures, freshness = fetch_football_data_results(league)

        target_dates = target_dates_by_league.get(league, set())
        fotmob_results = (
            fetch_fotmob_recent_results(
                league,
                target_dates,
                target_fixtures_by_league.get(league, []),
            )
            if target_dates
            else {}
        )
        normalized_fotmob: Dict[str, dict] = {}
        for key, row in fotmob_results.items():
            parts = key.split("|")
            if len(parts) != 3:
                continue
            date_str, home, away = parts
            normalized_key = build_fixture_key(date_str, home, away)
            normalized_fotmob[normalized_key] = {
                "home_team": normalize_team_name(home),
                "away_team": normalize_team_name(away),
                "home_shots": optional_int(row.get("home_shots")),
                "away_shots": optional_int(row.get("away_shots")),
                "home_sot": optional_int(row.get("home_sot")),
                "away_sot": optional_int(row.get("away_sot")),
                "home_corners": optional_int(row.get("home_corners")),
                "away_corners": optional_int(row.get("away_corners")),
                "total_corners": optional_int(row.get("total_corners")),
                "source": "fotmob",
                "match_id": row.get("match_id"),
            }

        merged = dict(fixtures)
        for key, row in normalized_fotmob.items():
            merged.setdefault(key, row)

        unresolved_fixtures = [
            fixture
            for fixture in target_fixtures_by_league.get(league, [])
            if not fixture_present(merged, fixture)
        ]
        api_football_results: Dict[str, dict] = {}
        api_football_meta = {
            "error": None,
            "requests_used": 0,
            "api_football_latest": None,
            "api_football_count": 0,
            "max_requests": args.api_football_max_requests,
        }
        if unresolved_fixtures and api_football_requests_remaining > 0:
            api_football_results, api_football_meta = fetch_api_football_results(
                league,
                unresolved_fixtures,
                max_requests=api_football_requests_remaining,
            )
            api_football_requests_remaining = max(
                0,
                api_football_requests_remaining - int(api_football_meta.get("requests_used", 0) or 0),
            )
            for key, row in api_football_results.items():
                merged.setdefault(key, row)

        latest_fotmob = max((key.split("|", 1)[0] for key in normalized_fotmob.keys()), default=None)
        payload["leagues"][league] = {
            "source": "football-data",
            "source_latest": freshness.get("football_data_latest"),
            "football_data_latest": freshness.get("football_data_latest"),
            "lag_days": freshness.get("lag_days"),
            "football_data_count": freshness.get("football_data_count", 0),
            "fotmob_count": len(normalized_fotmob),
            "fotmob_latest": latest_fotmob,
            "api_football_count": api_football_meta.get("api_football_count", 0),
            "api_football_latest": api_football_meta.get("api_football_latest"),
            "api_football_requests_used": api_football_meta.get("requests_used", 0),
            "api_football_requests_remaining_after_league": api_football_requests_remaining,
            "api_football_error": api_football_meta.get("error"),
            "api_football_max_requests": api_football_meta.get("max_requests", args.api_football_max_requests),
            "target_dates": sorted(target_dates),
            "target_fixture_count": len(target_fixtures_by_league.get(league, [])),
            "unresolved_fixture_count": len(unresolved_fixtures),
            "fetch_error": freshness.get("error"),
            "fixtures": merged,
        }

    total_fixtures = sum(len((league_data.get("fixtures") or {})) for league_data in payload["leagues"].values())
    if total_fixtures == 0:
        raise SystemExit("No fixtures were fetched for the results snapshot; refusing to write an empty snapshot.")

    ensure_snapshot_dir()
    out_path = snapshot_path_for(snapshot_day)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    latest_path = out_path.parent / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"Results snapshot -> {out_path}")
    return total_fixtures


def run_cli() -> int:
    load_env()
    if os.environ.get("FETCH_RESULTS_SNAPSHOT_RUN_STATUS_EXTERNAL") == "1":
        main()
        return 0

    with run_status("fetch-results-snapshot", trigger_kind="schedule") as rs:
        rs.rows_out = main()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
