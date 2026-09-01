#!/usr/bin/env python3
"""Settle football-form research CLV lanes.

The V3 team-shots and V0 corners research lanes publish picks into CLV monitor
CSVs. This script is the missing settlement bridge: it updates those monitor
rows with actual results, PnL, and audit files so the model monitor can track
open and settled research picks without manual intervention.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from settlement_audit import build_settlement_audit, load_settlement_overrides, write_audit
from settlement_utils import (
    ROOT,
    build_fixture_key,
    load_manual_settlement_results,
    load_results_snapshot,
    normalize_team_name,
    parse_isoish_date,
    resolve_fixture_result,
)

FOOTBALL_FORM_DIR = ROOT / "data" / "football-form"
DEFAULT_TEAM_SHOTS = FOOTBALL_FORM_DIR / "team-shots-v3-ema20-clv-monitor.csv"
DEFAULT_CORNERS = FOOTBALL_FORM_DIR / "corners-v0-clv-monitor.csv"
DEFAULT_TEAM_AUDIT = FOOTBALL_FORM_DIR / "team-shots-v3-ema20-settlement-audit.json"
DEFAULT_CORNERS_AUDIT = FOOTBALL_FORM_DIR / "corners-v0-settlement-audit.json"
OVERRIDES_PATH = ROOT / "data" / "settlement-overrides.csv"
HISTORICAL_CORNERS_DIR = ROOT / "data" / "corners-ou" / "historical"

SETTLED_RESULTS = {"won", "lost", "push"}
PENDING_RESULTS = {"", "pending"}


def _pf(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value or "").strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def _parse_optional_int(raw: object) -> int | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _norm_team(text: str) -> str:
    return normalize_team_name((text or "").replace("(Corners)", ""))


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fieldnames_for(rows: Iterable[Mapping[str, Any]], extras: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                ordered.append(key)
                seen.add(key)
    for key in extras:
        if key not in seen:
            ordered.append(key)
            seen.add(key)
    return ordered


def write_csv(path: Path, rows: list[dict[str, Any]], extras: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames_for(rows, extras)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def match_date_for(row: Mapping[str, Any]) -> date | None:
    for field in ("kickoff_utc", "kickoff_iso", "kick_off", "match_date", "fixture_date", "date"):
        parsed = parse_isoish_date(str(row.get(field, "") or ""))
        if parsed is not None:
            return parsed
    return None


def result_for_fixture(results: Mapping[str, dict], row: Mapping[str, Any]) -> dict | None:
    match_date = match_date_for(row)
    home = str(row.get("home_team", "") or "").strip()
    away = str(row.get("away_team", "") or "").strip()
    if match_date is None or not home or not away:
        return None
    return resolve_fixture_result(results, match_date, home, away)


def settle_market(side: str, line: float, actual: float, odds: float) -> tuple[str, float]:
    side = (side or "").strip().lower()
    if actual == line:
        return "push", 0.0
    if side == "over":
        won = actual > line
    else:
        won = actual < line
    return ("won", odds - 1.0) if won else ("lost", -1.0)


def load_historical_corner_results() -> dict[str, dict]:
    results: dict[str, dict] = {}
    if not HISTORICAL_CORNERS_DIR.exists():
        return results
    for path in sorted(HISTORICAL_CORNERS_DIR.glob("*.csv")):
        if path.name == "all-historical-matches.csv":
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                match_date = parse_isoish_date(row.get("Date") or row.get("date") or "")
                home = str(row.get("HomeTeam") or row.get("home_team") or "").strip()
                away = str(row.get("AwayTeam") or row.get("away_team") or "").strip()
                home_corners = _parse_optional_int(row.get("HC") or row.get("actual_home_corners"))
                away_corners = _parse_optional_int(row.get("AC") or row.get("actual_away_corners"))
                if match_date is None or not home or not away or home_corners is None or away_corners is None:
                    continue
                key = build_fixture_key(match_date, home, away)
                results[key] = {
                    "home_team": _norm_team(home),
                    "away_team": _norm_team(away),
                    "home_corners": home_corners,
                    "away_corners": away_corners,
                    "total_corners": home_corners + away_corners,
                    "source": f"historical-corners:{path.name}",
                }
    return results


def merge_manual_corner_results(results: dict[str, dict], manual_results: Mapping[str, dict]) -> dict[str, dict]:
    merged = dict(results)
    for key, manual in manual_results.items():
        existing = merged.get(key)
        if existing and existing.get("total_corners") is not None and manual.get("total_corners") is None:
            combined = {**manual, **existing}
            for stat_key in ("home_shots", "away_shots"):
                if stat_key in manual:
                    combined[stat_key] = manual[stat_key]
            merged[key] = combined
        else:
            merged[key] = {**(existing or {}), **manual}
    return merged


def settle_team_shots(rows: list[dict[str, Any]], results: Mapping[str, dict]) -> int:
    settled = 0
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for row in rows:
        result = str(row.get("result") or "").strip().lower()
        if result in SETTLED_RESULTS:
            continue
        row["result"] = "pending"
        fixture = result_for_fixture(results, row)
        if not fixture:
            continue
        if fixture.get("home_shots") is None or fixture.get("away_shots") is None:
            continue

        team = _norm_team(str(row.get("team") or ""))
        home = _norm_team(str(row.get("home_team") or ""))
        away = _norm_team(str(row.get("away_team") or ""))
        if team == home:
            actual = int(fixture["home_shots"])
        elif team == away:
            actual = int(fixture["away_shots"])
        else:
            continue

        line = _pf(row.get("line"))
        odds = _pf(row.get("book_price_at_publication") or row.get("book_price_close"))
        market_result, pnl = settle_market(str(row.get("side") or ""), line, float(actual), odds)
        row["actual_team_shots"] = actual
        row["result"] = market_result
        row["pnl_units"] = round(pnl, 3)
        row["settled_at"] = now
        settled += 1
    return settled


def settle_corners(rows: list[dict[str, Any]], results: Mapping[str, dict]) -> int:
    settled = 0
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for row in rows:
        result = str(row.get("result") or "").strip().lower()
        if result in SETTLED_RESULTS:
            continue
        row["result"] = "pending"
        fixture = result_for_fixture(results, row)
        if not fixture:
            continue
        total = fixture.get("total_corners")
        if total is None and fixture.get("home_corners") is not None and fixture.get("away_corners") is not None:
            total = int(fixture["home_corners"]) + int(fixture["away_corners"])
        if total is None:
            continue

        line = _pf(row.get("line"))
        odds = _pf(row.get("pinnacle_price_at_publication") or row.get("pinnacle_price_close"))
        market_result, pnl = settle_market(str(row.get("side") or ""), line, float(total), odds)
        row["actual_total_corners"] = int(total)
        row["result"] = market_result
        row["pnl_units"] = round(pnl, 3)
        row["settled_at"] = now
        settled += 1
    return settled


def is_pending(row: Mapping[str, Any]) -> bool:
    return str(row.get("result") or "").strip().lower() in PENDING_RESULTS


def is_settled(row: Mapping[str, Any]) -> bool:
    return str(row.get("result") or "").strip().lower() in SETTLED_RESULTS


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle team-shots/corners football-form research lanes")
    parser.add_argument("--team-shots", type=Path, default=DEFAULT_TEAM_SHOTS)
    parser.add_argument("--corners", type=Path, default=DEFAULT_CORNERS)
    parser.add_argument("--team-audit", type=Path, default=DEFAULT_TEAM_AUDIT)
    parser.add_argument("--corners-audit", type=Path, default=DEFAULT_CORNERS_AUDIT)
    parser.add_argument("--team-model", default="team-shots-v3-ema20-research")
    parser.add_argument("--corners-model", default="corners-v0-research")
    parser.add_argument("--snapshot-date", type=str, default=None)
    args = parser.parse_args()

    snapshot_results, source_freshness, snapshot_path, _payload = load_results_snapshot(args.snapshot_date)
    if snapshot_path is None:
        print("No results snapshot found; research rows will remain pending.")
    else:
        print(f"Loaded {len(snapshot_results)} snapshot result(s) from {_display(snapshot_path)}")

    manual_results = load_manual_settlement_results(OVERRIDES_PATH)
    team_results = {**snapshot_results, **manual_results}

    historical_corners = load_historical_corner_results()
    corner_results = {**historical_corners, **snapshot_results}
    corner_results = merge_manual_corner_results(corner_results, manual_results)
    if historical_corners:
        print(f"Loaded {len(historical_corners)} historical corner fallback result(s)")
    if manual_results:
        print(f"Loaded {len(manual_results)} manual settlement override result(s)")

    team_rows: list[dict[str, Any]] = [dict(row) for row in load_csv(args.team_shots)]
    corner_rows: list[dict[str, Any]] = [dict(row) for row in load_csv(args.corners)]

    team_settled = settle_team_shots(team_rows, team_results)
    corner_settled = settle_corners(corner_rows, corner_results)

    if team_rows:
        write_csv(args.team_shots, team_rows, extras=("actual_team_shots", "settled_at"))
    if corner_rows:
        write_csv(args.corners, corner_rows, extras=("actual_total_corners", "settled_at"))

    overrides = load_settlement_overrides(OVERRIDES_PATH)
    now_utc = datetime.now(timezone.utc)
    team_audit = build_settlement_audit(
        rows=team_rows,
        model=args.team_model,
        now_utc=now_utc,
        settled_this_run=team_settled,
        is_pending=is_pending,
        is_settled=is_settled,
        kickoff_fields=("kickoff_utc", "kickoff_iso", "kick_off"),
        date_fields=("match_date", "fixture_date", "date"),
        source_freshness=source_freshness,
        overrides=overrides,
    )
    corners_audit = build_settlement_audit(
        rows=corner_rows,
        model=args.corners_model,
        now_utc=now_utc,
        settled_this_run=corner_settled,
        is_pending=is_pending,
        is_settled=is_settled,
        kickoff_fields=("kickoff_utc", "kickoff_iso", "kick_off"),
        date_fields=("match_date", "fixture_date", "date"),
        source_freshness=source_freshness,
        overrides=overrides,
    )
    write_audit(args.team_audit, team_audit)
    write_audit(args.corners_audit, corners_audit)

    print(f"Team-shots research: settled {team_settled}, total rows {len(team_rows)}")
    print(f"Corners research: settled {corner_settled}, total rows {len(corner_rows)}")
    print(f"Wrote {_display(args.team_audit)}")
    print(f"Wrote {_display(args.corners_audit)}")


if __name__ == "__main__":
    main()
