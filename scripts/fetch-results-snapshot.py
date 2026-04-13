#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import UTC, datetime
from typing import Dict

import requests

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
        hs = (row.get("HS") or "").strip()
        a_s = (row.get("AS") or "").strip()
        hc = (row.get("HC") or "").strip()
        ac = (row.get("AC") or "").strip()
        if not any([hs, a_s, hc, ac]):
            continue
        key = build_fixture_key(match_date, home, away)
        results[key] = {
            "home_team": normalize_team_name(home),
            "away_team": normalize_team_name(away),
            "home_shots": int(float(hs or 0)),
            "away_shots": int(float(a_s or 0)),
            "home_sot": int(float((row.get("HST") or 0) or 0)),
            "away_sot": int(float((row.get("AST") or 0) or 0)),
            "home_corners": int(float(hc or 0)),
            "away_corners": int(float(ac or 0)),
            "total_corners": int(float(hc or 0)) + int(float(ac or 0)),
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


def load_pending_rows() -> list[dict]:
    rows: list[dict] = []
    if SHORTLIST_SETTLED.exists():
        with open(SHORTLIST_SETTLED, "r", encoding="utf-8", newline="") as fh:
            rows.extend([dict(r) for r in csv.DictReader(fh) if (r.get("settled") or "").strip() == "pending"])
    if TEAM_SHOTS_SIGNALS.exists():
        with open(TEAM_SHOTS_SIGNALS, "r", encoding="utf-8", newline="") as fh:
            rows.extend([dict(r) for r in csv.DictReader(fh) if (r.get("result") or "").strip() == "pending"])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a committed football results snapshot for settlement")
    parser.add_argument("--date", type=str, default=None, help="Snapshot date in YYYY-MM-DD (defaults to today UTC)")
    args = parser.parse_args()

    snapshot_day = parse_isoish_date(args.date or "") or datetime.now(UTC).date()
    pending_rows = load_pending_rows()
    target_dates_by_league = collect_target_dates(
        pending_rows,
        kickoff_fields=("kick_off", "kickoff_iso"),
        date_fields=("match_date", "fixture_date", "date", "file_date"),
    )

    payload: dict = {
        "snapshot_date": snapshot_day.isoformat(),
        "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "leagues": {},
    }

    for league in sorted(LEAGUE_CODES.keys()):
        fixtures, freshness = fetch_football_data_results(league)

        target_dates = target_dates_by_league.get(league, set())
        fotmob_results = fetch_fotmob_recent_results(league, target_dates) if target_dates else {}
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
                "home_shots": int(row.get("home_shots", 0) or 0),
                "away_shots": int(row.get("away_shots", 0) or 0),
                "home_sot": int(row.get("home_sot", 0) or 0),
                "away_sot": int(row.get("away_sot", 0) or 0),
                "home_corners": int(row.get("home_corners", 0) or 0),
                "away_corners": int(row.get("away_corners", 0) or 0),
                "total_corners": int(row.get("total_corners", 0) or 0),
                "source": "fotmob",
                "match_id": row.get("match_id"),
            }

        merged = dict(fixtures)
        for key, row in normalized_fotmob.items():
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
            "target_dates": sorted(target_dates),
            "fetch_error": freshness.get("error"),
            "fixtures": merged,
        }

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


if __name__ == "__main__":
    main()
