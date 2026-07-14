#!/usr/bin/env python3
"""Compare Football-Data shots-on-target counts with independent FotMob outcomes."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fotmob_match_stats import fetch_fotmob_recent_results
from settlement_utils import build_fixture_key, parse_isoish_date


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_CSV = ROOT / "data" / "team-shots" / "sot-definition-agreement.csv"
DEFAULT_REPORT = ROOT / "data" / "team-shots" / "sot-definition-agreement.md"
TOP_FIVE = ("epl", "serie-a", "la-liga", "bundesliga", "ligue-1")


def count(value: Any) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def load_reference(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            league = str(row.get("league") or "").strip().lower()
            day = parse_isoish_date(str(row.get("Date") or ""))
            home_sot = count(row.get("HST"))
            away_sot = count(row.get("AST"))
            if league not in TOP_FIVE or day is None or home_sot is None or away_sot is None:
                continue
            rows.append(
                {
                    "league": league,
                    "date": day.isoformat(),
                    "home_team": str(row.get("HomeTeam") or "").strip(),
                    "away_team": str(row.get("AwayTeam") or "").strip(),
                    "home_sot": home_sot,
                    "away_sot": away_sot,
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


def compare_rows(
    reference_rows: list[dict[str, Any]],
    independent: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in reference_rows:
        key = build_fixture_key(row["date"], row["home_team"], row["away_team"])
        actual = independent.get(key)
        if not actual:
            continue
        for side in ("home", "away"):
            reference = int(row[f"{side}_sot"])
            comparison = count(actual.get(f"{side}_sot"))
            if comparison is None:
                continue
            delta = comparison - reference
            output.append(
                {
                    "date": row["date"],
                    "league": row["league"],
                    "home_team": row["home_team"],
                    "away_team": row["away_team"],
                    "team_side": side,
                    "football_data_sot": reference,
                    "fotmob_sot": comparison,
                    "delta": delta,
                    "absolute_delta": abs(delta),
                    "exact_match": abs(delta) == 0,
                    "within_one": abs(delta) <= 1,
                    "fotmob_match_id": actual.get("match_id") or "",
                }
            )
    return output


def load_compared(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            parsed = dict(row)
            for field in ("football_data_sot", "fotmob_sot", "delta", "absolute_delta"):
                parsed[field] = int(float(str(row.get(field) or 0)))
            parsed["exact_match"] = str(row.get("exact_match") or "").strip().lower() == "true"
            parsed["within_one"] = str(row.get("within_one") or "").strip().lower() == "true"
            rows.append(parsed)
    return rows


def summarize(rows: list[dict[str, Any]], attempted_matches: int) -> dict[str, Any]:
    matched_team_rows = len(rows)
    matched_matches = len(
        {
            (row["date"], row["league"], row["home_team"], row["away_team"])
            for row in rows
        }
    )
    exact = sum(bool(row["exact_match"]) for row in rows)
    within_one = sum(bool(row["within_one"]) for row in rows)
    mean_abs = (
        sum(float(row["absolute_delta"]) for row in rows) / matched_team_rows
        if matched_team_rows
        else None
    )
    within_rate = within_one / matched_team_rows if matched_team_rows else None
    definition_pass = matched_team_rows >= 100 and within_rate is not None and within_rate >= 0.97
    return {
        "attempted_matches": attempted_matches,
        "matched_matches": matched_matches,
        "match_coverage": matched_matches / attempted_matches if attempted_matches else None,
        "matched_team_rows": matched_team_rows,
        "exact_team_rows": exact,
        "exact_rate": exact / matched_team_rows if matched_team_rows else None,
        "within_one_team_rows": within_one,
        "within_one_rate": within_rate,
        "mean_absolute_delta": mean_abs,
        "definition_pass": definition_pass,
        "provider_grade_sample_complete": matched_matches >= 200,
    }


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def render_report(
    summary: dict[str, Any],
    by_league: dict[str, dict[str, Any]],
    compared_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# Shots-on-Target Definition Agreement",
        "",
        f"Generated: {datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}",
        "",
        "Football-Data HST/AST is compared with independently fetched FotMob full-time `ShotsOnTarget`.",
        "The existing `all-understat-matches.csv` is deliberately not used as an independent source: its SOT fields are copied from Football-Data and Understat supplies only xG.",
        "",
        "## Decision",
        "",
        f"- Definition gate: {'PASS' if summary['definition_pass'] else 'WAIT/FAIL'}",
        f"- Provider-grade sample (>=200 matched fixtures): {'complete' if summary['provider_grade_sample_complete'] else 'incomplete'}",
        f"- Matched fixtures: {summary['matched_matches']}/{summary['attempted_matches']} ({pct(summary['match_coverage'])})",
        f"- Exact team-count agreement: {summary['exact_team_rows']}/{summary['matched_team_rows']} ({pct(summary['exact_rate'])})",
        f"- Within one SOT: {summary['within_one_team_rows']}/{summary['matched_team_rows']} ({pct(summary['within_one_rate'])})",
        f"- Mean absolute delta: {summary['mean_absolute_delta']:.3f}" if summary["mean_absolute_delta"] is not None else "- Mean absolute delta: -",
        "",
        "The definition gate requires at least 100 matched team rows and >=97% agreement within one SOT. Model development may continue after that gate, but promotion still requires the 200-fixture provider-grade sample.",
        "",
        "## League Breakdown",
        "",
        "| League | Fixtures | Team rows | Exact | Within one | MAE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for league in TOP_FIVE:
        item = by_league.get(league, summarize([], 0))
        lines.append(
            f"| {league} | {item['matched_matches']} | {item['matched_team_rows']} | "
            f"{pct(item['exact_rate'])} | {pct(item['within_one_rate'])} | "
            f"{item['mean_absolute_delta']:.3f} |"
            if item["mean_absolute_delta"] is not None
            else f"| {league} | 0 | 0 | - | - | - |"
        )
    material = sorted(
        (row for row in compared_rows if int(row["absolute_delta"]) > 1),
        key=lambda row: (-int(row["absolute_delta"]), row["date"], row["home_team"]),
    )
    lines.extend(
        [
            "",
            "## Material Discrepancies",
            "",
            "Rows differing by more than one SOT fail closed and require a third-source check before this market can be settled automatically.",
            "",
            "| Date | League | Fixture | Side | Football-Data | FotMob | Delta |",
            "|---|---|---|---|---:|---:|---:|",
        ]
    )
    if material:
        for row in material:
            lines.append(
                f"| {row['date']} | {row['league']} | {row['home_team']} vs {row['away_team']} | "
                f"{row['team_side']} | {row['football_data_sot']} | {row['fotmob_sot']} | "
                f"{int(row['delta']):+d} |"
            )
    else:
        lines.append("| - | - | None | - | - | - | - |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Football-Data versus FotMob SOT definitions")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dates-per-league", type=int, default=2)
    parser.add_argument(
        "--reuse-csv",
        action="store_true",
        help="Rebuild the report from the existing comparison CSV without refetching FotMob.",
    )
    args = parser.parse_args()

    reference = load_reference(args.source)
    dates = selected_dates(reference, args.dates_per_league)
    selected = [row for row in reference if row["date"] in dates.get(row["league"], [])]

    if args.reuse_csv:
        compared = load_compared(args.csv)
        if not compared:
            raise SystemExit(f"No reusable comparison rows in {args.csv}")
    else:
        independent: dict[str, dict[str, Any]] = {}
        for league in TOP_FIVE:
            league_dates = dates.get(league, [])
            if not league_dates:
                continue
            print(f"Fetching FotMob {league}: {', '.join(league_dates)}")
            independent.update(fetch_fotmob_recent_results(league, league_dates))
        compared = compare_rows(selected, independent)
    summary = summarize(compared, len(selected))
    by_league = {
        league: summarize(
            [row for row in compared if row["league"] == league],
            sum(1 for row in selected if row["league"] == league),
        )
        for league in TOP_FIVE
    }

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    fields = list(compared[0]) if compared else [
        "date", "league", "home_team", "away_team", "team_side",
        "football_data_sot", "fotmob_sot", "delta", "absolute_delta",
        "exact_match", "within_one", "fotmob_match_id",
    ]
    if not args.reuse_csv:
        with args.csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(compared)
    args.report.write_text(render_report(summary, by_league, compared), encoding="utf-8")
    print(
        "SOT definition agreement: "
        f"matches={summary['matched_matches']}/{summary['attempted_matches']} "
        f"within_one={pct(summary['within_one_rate'])} "
        f"gate={'PASS' if summary['definition_pass'] else 'WAIT/FAIL'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
