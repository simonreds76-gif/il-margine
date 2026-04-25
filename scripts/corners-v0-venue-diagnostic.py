#!/usr/bin/env python3
"""Venue/component diagnostic for canonical corners v0.

This checks whether the Bundesliga/La Liga last-90 regression looks like the
team-shots home-row overshoot. Corners v0 already uses pooled corner concession,
so this script is deliberately diagnostic only: it reports the home/away
component errors instead of assuming the same root cause.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_CURRENT = ROOT / "data" / "corners-ou" / "corners-ou-predictions.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "corners-v0-venue-diagnostic.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "corners-v0-venue-diagnostic.md"
DEFAULT_CSV = ROOT / "data" / "football-form" / "corners-v0-venue-worst.csv"


def load_backtest_module() -> Any:
    path = ROOT / "scripts" / "backtest-football-form-layer.py"
    spec = importlib.util.spec_from_file_location("football_form_backtest_mod", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["football_form_backtest_mod"] = module
    spec.loader.exec_module(module)
    return module


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def ensure_form_input(path: Path) -> None:
    if path.exists():
        return
    if path != DEFAULT_FORM:
        raise SystemExit(f"Missing canonical form input: {path}")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build-football-form-layer.py")], check=True)
    if not path.exists():
        raise SystemExit(f"Canonical form build did not create expected input: {path}")


def pf(value: Any, default: float | None = None) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def rounded(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def build_records(form_rows: list[dict[str, str]], current_rows: list[dict[str, str]], bt: Any) -> list[dict[str, Any]]:
    current_by_key = {bt.row_key(row): row for row in current_rows}
    rows_by_fixture: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in form_rows:
        rows_by_fixture[bt.row_key(row)].append(row)

    league_shots_avg = bt.league_shots_averages(form_rows)
    records: list[dict[str, Any]] = []
    for fixture_key, fixture_rows in rows_by_fixture.items():
        current = current_by_key.get(fixture_key)
        if current is None or len(fixture_rows) != 2:
            continue
        home_rows = [row for row in fixture_rows if str(row.get("venue", "")).strip() == "home"]
        away_rows = [row for row in fixture_rows if str(row.get("venue", "")).strip() == "away"]
        if len(home_rows) != 1 or len(away_rows) != 1:
            continue
        home = home_rows[0]
        away = away_rows[0]
        league = str(home.get("league", "")).strip()
        fixture_date = parse_date(home.get("date"))
        if fixture_date is None:
            continue

        canonical_home = bt.canonical_corners_lambda(home, away, league_shots_avg.get(league, 0.0))
        canonical_away = bt.canonical_corners_lambda(away, home, league_shots_avg.get(league, 0.0))
        current_home = pf(current.get("lambda_home"))
        current_away = pf(current.get("lambda_away"))
        actual_home = pf(current.get("actual_home_corners"))
        actual_away = pf(current.get("actual_away_corners"))
        if (
            canonical_home is None
            or canonical_away is None
            or current_home is None
            or current_away is None
            or actual_home is None
            or actual_away is None
        ):
            continue

        current_total = current_home + current_away
        canonical_total = canonical_home + canonical_away
        actual_total = actual_home + actual_away
        records.append(
            {
                "date": fixture_date.isoformat(),
                "league": league,
                "home_team": home.get("home_team", ""),
                "away_team": home.get("away_team", ""),
                "current_home_lambda": current_home,
                "canonical_home_lambda": canonical_home,
                "actual_home_corners": actual_home,
                "home_lambda_gap": canonical_home - current_home,
                "home_current_error": current_home - actual_home,
                "home_canonical_error": canonical_home - actual_home,
                "current_away_lambda": current_away,
                "canonical_away_lambda": canonical_away,
                "actual_away_corners": actual_away,
                "away_lambda_gap": canonical_away - current_away,
                "away_current_error": current_away - actual_away,
                "away_canonical_error": canonical_away - actual_away,
                "current_total_lambda": current_total,
                "canonical_total_lambda": canonical_total,
                "actual_total_corners": actual_total,
                "total_lambda_gap": canonical_total - current_total,
                "current_total_error": current_total - actual_total,
                "canonical_total_error": canonical_total - actual_total,
                "canonical_abs_error_minus_current": abs(canonical_total - actual_total) - abs(current_total - actual_total),
            }
        )
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n": len(records),
        "current_total_mae": rounded(mean(abs(row["current_total_error"]) for row in records)),
        "canonical_total_mae": rounded(mean(abs(row["canonical_total_error"]) for row in records)),
        "total_mae_delta": rounded(
            mean(abs(row["canonical_total_error"]) for row in records)
            - mean(abs(row["current_total_error"]) for row in records)
        )
        if records
        else None,
        "current_home_mae": rounded(mean(abs(row["home_current_error"]) for row in records)),
        "canonical_home_mae": rounded(mean(abs(row["home_canonical_error"]) for row in records)),
        "mean_home_lambda_gap": rounded(mean(row["home_lambda_gap"] for row in records)),
        "current_away_mae": rounded(mean(abs(row["away_current_error"]) for row in records)),
        "canonical_away_mae": rounded(mean(abs(row["away_canonical_error"]) for row in records)),
        "mean_away_lambda_gap": rounded(mean(row["away_lambda_gap"] for row in records)),
        "mean_total_lambda_gap": rounded(mean(row["total_lambda_gap"] for row in records)),
        "canonical_worse_share": rounded(
            mean(1.0 if row["canonical_abs_error_minus_current"] > 0 else 0.0 for row in records)
        ),
    }


def group_summary(records: list[dict[str, Any]], *, recent_cutoff: date | None) -> dict[str, Any]:
    samples = {
        "full_common": records,
        "last_90_common": [
            row for row in records if recent_cutoff is not None and parse_date(row["date"]) is not None and parse_date(row["date"]) >= recent_cutoff
        ],
    }
    payload: dict[str, Any] = {}
    for sample, sample_records in samples.items():
        league_payload = {"ALL": summarize(sample_records)}
        by_league: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in sample_records:
            by_league[str(row.get("league", ""))].append(row)
        for league, league_records in sorted(by_league.items()):
            league_payload[league] = summarize(league_records)
        payload[sample] = league_payload
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Corners V0 Venue Diagnostic",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "Corners v0 already uses pooled opponent corner concession, not venue-specific opponent concession.",
        "This report checks whether the blocked Bundesliga/La Liga segments still show a home/away component bias.",
        "",
        "## Last-90 Component Split",
        "",
        "| League | N | Current total MAE | V0 total MAE | Delta | Current home MAE | V0 home MAE | Home lambda gap | Current away MAE | V0 away MAE | Away lambda gap | Worse share |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    last90 = payload["summaries"]["last_90_common"]
    for league, item in last90.items():
        lines.append(
            "| {league} | {n} | {current_total_mae} | {canonical_total_mae} | {total_mae_delta} | "
            "{current_home_mae} | {canonical_home_mae} | {mean_home_lambda_gap} | "
            "{current_away_mae} | {canonical_away_mae} | {mean_away_lambda_gap} | {canonical_worse_share} |".format(
                league=league,
                **{key: "-" if value is None else value for key, value in item.items()},
            )
        )

    lines.extend(
        [
            "",
            "## Read",
            "",
            "- If home lambda gap is strongly positive and home MAE regresses, corners may share the team-shots home overshoot shape.",
            "- If not, Bundesliga/La Liga corners need a corners-specific fix rather than the team-shots pooled-opponent defence patch.",
            f"- Worst rows written to `{payload['worst_csv']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_worst(records: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "date",
        "league",
        "home_team",
        "away_team",
        "current_total_lambda",
        "canonical_total_lambda",
        "actual_total_corners",
        "canonical_abs_error_minus_current",
        "current_home_lambda",
        "canonical_home_lambda",
        "actual_home_corners",
        "home_lambda_gap",
        "current_away_lambda",
        "canonical_away_lambda",
        "actual_away_corners",
        "away_lambda_gap",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    worst = sorted(records, key=lambda row: row["canonical_abs_error_minus_current"], reverse=True)[:50]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in worst])


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose canonical corners v0 home/away component bias")
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    ensure_form_input(args.form)
    form_rows = load_csv(args.form)
    current_rows = load_csv(args.current)
    if not form_rows:
        raise SystemExit(f"Missing/empty form rows: {args.form}")
    if not current_rows:
        raise SystemExit(f"Missing/empty current corners rows: {args.current}")

    bt = load_backtest_module()
    records = build_records(form_rows, current_rows, bt)
    latest = bt.latest_form_date(form_rows)
    recent_cutoff = latest - timedelta(days=90) if latest else None
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": {
            "form": str(args.form.relative_to(ROOT)).replace("\\", "/"),
            "current": str(args.current.relative_to(ROOT)).replace("\\", "/"),
        },
        "latest_form_date": latest.isoformat() if latest else None,
        "recent_cutoff": recent_cutoff.isoformat() if recent_cutoff else None,
        "model": "canonical_form_v0",
        "market": "corners_total",
        "summaries": group_summary(records, recent_cutoff=recent_cutoff),
        "worst_csv": str(args.csv_out.relative_to(ROOT)).replace("\\", "/"),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    write_worst(records, args.csv_out)
    print(f"Wrote {args.json_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")
    print(f"Wrote {args.csv_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
