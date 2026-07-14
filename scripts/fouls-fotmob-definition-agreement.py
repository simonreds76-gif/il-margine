#!/usr/bin/env python3
"""Compare Football-Data foul counts with independent FotMob full-time counts."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fotmob_match_stats import fetch_fotmob_recent_results
from settlement_utils import build_fixture_key, parse_isoish_date


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_CSV = ROOT / "data" / "football-form" / "team-fouls-fotmob-agreement.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "team-fouls-fotmob-agreement.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "team-fouls-fotmob-agreement.md"
LEAGUES = ("epl", "serie-a", "la-liga", "bundesliga", "ligue-1")


def count(value: Any) -> int | None:
    try:
        text = str(value or "").strip()
        return int(float(text)) if text else None
    except ValueError:
        return None


def load_reference(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            league = str(row.get("league") or "").strip().lower()
            match_date = parse_isoish_date(str(row.get("Date") or ""))
            home_fouls, away_fouls = count(row.get("HF")), count(row.get("AF"))
            if league not in LEAGUES or match_date is None or home_fouls is None or away_fouls is None:
                continue
            rows.append(
                {
                    "league": league,
                    "date": match_date.isoformat(),
                    "home_team": str(row.get("HomeTeam") or "").strip(),
                    "away_team": str(row.get("AwayTeam") or "").strip(),
                    "home_fouls": home_fouls,
                    "away_fouls": away_fouls,
                }
            )
    return rows


def selected_dates(rows: list[dict[str, Any]], dates_per_league: int) -> dict[str, list[str]]:
    values: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        values[row["league"]].add(row["date"])
    return {
        league: sorted(dates)[-max(1, dates_per_league) :]
        for league, dates in values.items()
    }


def compare(
    reference: list[dict[str, Any]], independent: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for reference_row in reference:
        key = build_fixture_key(
            reference_row["date"], reference_row["home_team"], reference_row["away_team"]
        )
        actual = independent.get(key)
        if not actual:
            continue
        for side in ("home", "away"):
            left = int(reference_row[f"{side}_fouls"])
            right = count(actual.get(f"{side}_fouls"))
            if right is None:
                continue
            delta = right - left
            rows.append(
                {
                    "date": reference_row["date"],
                    "league": reference_row["league"],
                    "home_team": reference_row["home_team"],
                    "away_team": reference_row["away_team"],
                    "team_side": side,
                    "football_data_fouls": left,
                    "fotmob_fouls": right,
                    "delta": delta,
                    "absolute_delta": abs(delta),
                    "exact_match": abs(delta) == 0,
                    "within_one": abs(delta) <= 1,
                    "fotmob_match_id": actual.get("match_id") or "",
                }
            )
    return rows


def load_existing(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            parsed: dict[str, Any] = dict(row)
            for field in ("football_data_fouls", "fotmob_fouls", "delta", "absolute_delta"):
                parsed[field] = int(float(str(row.get(field) or 0)))
            parsed["exact_match"] = str(row.get("exact_match") or "").lower() == "true"
            parsed["within_one"] = str(row.get("within_one") or "").lower() == "true"
            rows.append(parsed)
    return rows


def row_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("date") or ""),
        str(row.get("league") or ""),
        str(row.get("home_team") or ""),
        str(row.get("away_team") or ""),
        str(row.get("team_side") or ""),
    )


def summarize(rows: list[dict[str, Any]], attempted_matches: int) -> dict[str, Any]:
    values = len(rows)
    matches = len({(row["date"], row["league"], row["home_team"], row["away_team"]) for row in rows})
    exact = sum(bool(row["exact_match"]) for row in rows)
    within = sum(bool(row["within_one"]) for row in rows)
    return {
        "attempted_matches": attempted_matches,
        "matched_matches": matches,
        "comparable_team_values": values,
        "exact_pct": (100.0 * exact / values) if values else 0.0,
        "within_one_pct": (100.0 * within / values) if values else 0.0,
        "mae": (sum(float(row["absolute_delta"]) for row in rows) / values) if values else None,
        "passed": values >= 200 and (100.0 * within / values) >= 97.0 if values else False,
    }


def render(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    mae = "-" if summary["mae"] is None else f"{summary['mae']:.3f}"
    return "\n".join(
        [
            "# Team Fouls v1: FotMob Definition Agreement",
            "",
            f"Generated: {payload['generated_at']}",
            f"Status: **{'PASS' if summary['passed'] else 'WAIT/FAIL'}**",
            "",
            f"- Matched fixtures: {summary['matched_matches']}/{summary['attempted_matches']}",
            f"- Comparable team values: {summary['comparable_team_values']} (required 200)",
            f"- Exact agreement: {summary['exact_pct']:.1f}%",
            f"- Within one foul: {summary['within_one_pct']:.1f}% (required 97.0%)",
            f"- Mean absolute difference: {mae}",
            "",
            "This is a settlement-definition audit only. It does not validate model probabilities or betting edge.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Football-Data versus FotMob foul definitions.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dates-per-league", type=int, default=2)
    parser.add_argument("--allow-empty", action="store_true")
    args = parser.parse_args()

    reference = load_reference(args.source)
    existing = load_existing(args.csv_out)
    completed_dates = {
        (str(row["date"]), str(row["league"]))
        for row in existing
    }
    unseen = [
        row
        for row in reference
        if (row["date"], row["league"]) not in completed_dates
    ]
    dates = selected_dates(unseen, args.dates_per_league)
    selected = [row for row in unseen if row["date"] in dates.get(row["league"], [])]
    independent: dict[str, dict[str, Any]] = {}
    for league in LEAGUES:
        league_dates = dates.get(league, [])
        if league_dates:
            print(f"Fetching FotMob fouls {league}: {', '.join(league_dates)}")
            independent.update(fetch_fotmob_recent_results(league, league_dates))
    fresh = compare(selected, independent)
    combined = {row_key(row): row for row in existing}
    combined.update({row_key(row): row for row in fresh})
    compared = sorted(combined.values(), key=row_key)
    existing_matches = len({row_key(row)[:4] for row in existing})
    summary = summarize(compared, existing_matches + len(selected))
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "Football-Data vs FotMob full-time fouls",
        "new_comparable_team_values": len(fresh),
        "summary": summary,
    }
    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(compared[0]) if compared else [
        "date", "league", "home_team", "away_team", "team_side",
        "football_data_fouls", "fotmob_fouls", "delta", "absolute_delta",
        "exact_match", "within_one", "fotmob_match_id",
    ]
    with args.csv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(compared)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render(payload), encoding="utf-8")
    print(
        f"FotMob foul agreement: {summary['matched_matches']}/{summary['attempted_matches']} matches; "
        f"new_team_values={len(fresh)}"
    )
    return 0 if compared or args.allow_empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
