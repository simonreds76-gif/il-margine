#!/usr/bin/env python3
"""Test whether a home/away corners correction can improve total-corners gates.

The corners venue diagnostic found home components low and away components high.
For a total-corners O/U market, a symmetric home/away redistribution cannot
change the total lambda, so this script explicitly proves that and also checks
whether a one-sided home premium helps. It is diagnostic only.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_CURRENT = ROOT / "data" / "corners-ou" / "corners-ou-predictions.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "corners-home-correction-diagnostic.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "corners-home-correction-diagnostic.md"
SCALES = [0.0, 0.25, 0.5, 0.75, 1.0]


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
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def mae(rows: list[dict[str, Any]], key: str) -> float:
    return sum(abs(row[key] - row["actual_total"]) for row in rows) / len(rows) if rows else 0.0


def build_records(form_rows: list[dict[str, str]], current_rows: list[dict[str, str]], bt: Any) -> tuple[list[dict[str, Any]], dict[str, float], str, str]:
    current_by_key = {bt.row_key(row): row for row in current_rows}
    latest = bt.latest_form_date(form_rows)
    recent_cutoff = latest - timedelta(days=90) if latest else None
    league_shots_avg = bt.league_shots_averages(form_rows)
    rows_by_fixture: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in form_rows:
        rows_by_fixture[bt.row_key(row)].append(row)

    train_bias: dict[str, list[list[float]]] = defaultdict(lambda: [[], []])
    test_records: list[dict[str, Any]] = []
    for fixture_key, fixture_rows in rows_by_fixture.items():
        current = current_by_key.get(fixture_key)
        if current is None or len(fixture_rows) != 2:
            continue
        home_rows = [row for row in fixture_rows if row.get("venue") == "home"]
        away_rows = [row for row in fixture_rows if row.get("venue") == "away"]
        if len(home_rows) != 1 or len(away_rows) != 1:
            continue
        home = home_rows[0]
        away = away_rows[0]
        league = str(home.get("league", "")).strip()
        fixture_date = bt.row_date(home)
        if fixture_date is None:
            continue
        canonical_home = bt.canonical_corners_lambda(home, away, league_shots_avg.get(league, 0.0))
        canonical_away = bt.canonical_corners_lambda(away, home, league_shots_avg.get(league, 0.0))
        actual_home = bt.pf(home.get("current_corners_for"), None)
        actual_away = bt.pf(away.get("current_corners_for"), None)
        current_total = bt.pf(current.get("lambda_total"), None)
        actual_total = bt.pf(current.get("actual_total"), None)
        if None in (canonical_home, canonical_away, actual_home, actual_away, current_total, actual_total):
            continue
        if recent_cutoff is not None and fixture_date < recent_cutoff:
            train_bias[league][0].append(canonical_home - actual_home)
            train_bias[league][1].append(canonical_away - actual_away)
        elif recent_cutoff is not None:
            test_records.append(
                {
                    "league": league,
                    "current_total": current_total,
                    "canonical_total": canonical_home + canonical_away,
                    "actual_total": actual_total,
                }
            )

    shifts: dict[str, float] = {}
    for league, (home_biases, away_biases) in train_bias.items():
        if len(home_biases) < 50 or len(away_biases) < 50:
            continue
        home_bias = sum(home_biases) / len(home_biases)
        away_bias = sum(away_biases) / len(away_biases)
        shifts[league] = max(-1.0, min(1.0, (away_bias - home_bias) / 2.0))
    return test_records, shifts, latest.isoformat() if latest else "", recent_cutoff.isoformat() if recent_cutoff else ""


def summarize(records: list[dict[str, Any]], shifts: dict[str, float], mode: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for scale in SCALES:
        adjusted: list[dict[str, Any]] = []
        for row in records:
            shift = shifts.get(row["league"], 0.0) * scale
            if mode == "symmetric":
                candidate = row["canonical_total"]
            elif mode == "home_only":
                candidate = row["canonical_total"] + shift
            else:
                raise ValueError(mode)
            adjusted.append({**row, "candidate": candidate})
        by_league: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in adjusted:
            by_league[row["league"]].append(row)
        league_metrics = {}
        for league, league_rows in sorted(by_league.items()):
            league_metrics[league] = {
                "n": len(league_rows),
                "current_mae": round(mae(league_rows, "current_total"), 4),
                "candidate_mae": round(mae(league_rows, "candidate"), 4),
            }
        out.append(
            {
                "mode": mode,
                "scale": scale,
                "current_mae": round(mae(adjusted, "current_total"), 4),
                "candidate_mae": round(mae(adjusted, "candidate"), 4),
                "league_metrics": league_metrics,
            }
        )
    return out


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Corners Home-Correction Diagnostic",
        "",
        f"Generated: {payload['generated_at']}",
        f"Latest form date: `{payload['latest_form_date']}`",
        f"Recent cutoff: `{payload['recent_cutoff']}`",
        "",
        "This is diagnostic only. It does not change corners publication.",
        "",
        "## Derived Home Shifts",
        "",
        "| League | Shift |",
        "| --- | ---: |",
    ]
    for league, shift in sorted(payload["shifts"].items()):
        lines.append(f"| {league} | {shift:.4f} |")
    lines.extend(
        [
            "",
            "## Best Reads",
            "",
            "- Symmetric home/away correction has no effect on total-corners O/U because the home addition is cancelled by the away subtraction.",
            "- One-sided home premium worsens Bundesliga and La Liga, the exact leagues we need to rescue.",
            "- The next corners test should target total-corners calibration or pressure, not home/away redistribution.",
            "",
            "## Last-90 Candidate MAE",
            "",
            "| Mode | Scale | Current ALL | Candidate ALL | Bundesliga | La Liga |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for mode, rows in payload["summaries"].items():
        for row in rows:
            leagues = row["league_metrics"]
            lines.append(
                "| {mode} | {scale:.2f} | {current:.4f} | {candidate:.4f} | {bundesliga:.4f} | {laliga:.4f} |".format(
                    mode=mode,
                    scale=row["scale"],
                    current=row["current_mae"],
                    candidate=row["candidate_mae"],
                    bundesliga=leagues.get("bundesliga", {}).get("candidate_mae", 0.0),
                    laliga=leagues.get("la-liga", {}).get("candidate_mae", 0.0),
                )
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose home/away corners corrections against total corners")
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    bt = load_backtest_module()
    records, shifts, latest, recent_cutoff = build_records(load_csv(args.form), load_csv(args.current), bt)
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "latest_form_date": latest,
        "recent_cutoff": recent_cutoff,
        "model": "canonical_form_v0",
        "market": "corners_total",
        "diagnostic": "home_correction",
        "shifts": {league: round(shift, 4) for league, shift in shifts.items()},
        "summaries": {
            "symmetric": summarize(records, shifts, "symmetric"),
            "home_only": summarize(records, shifts, "home_only"),
        },
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(f"Wrote {args.json_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
