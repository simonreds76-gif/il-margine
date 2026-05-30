#!/usr/bin/env python3
"""Corners v2 NB prediction export.

This is an additive research script. It reuses the causal EMA lambdas from
corners-ou-model.py, fits NB dispersion on past historical totals, and writes
NB over/under probabilities alongside the v1 Poisson baseline. It does not
claim ROI; real-odds validation lives in corners-real-odds-backtest.py.
"""

from __future__ import annotations

import argparse
import csv
import runpy
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from corners_nb import fair_decimal, fit_dispersion, nb_total_prob_over  # noqa: E402

DEFAULT_INPUT = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_OUTPUT = ROOT / "data" / "corners-ou" / "corners-nb-predictions.csv"
DEFAULT_REPORT = ROOT / "data" / "corners-ou" / "corners-nb-model-report.txt"
STANDARD_LINES = [7.5, 8.5, 9.5, 10.5, 11.5, 12.5]


def load_v1_module() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT_DIR / "corners-ou-model.py"), run_name="corners_ou_model")


def fit_dispersions(matches: list[Any], train_before: date | None) -> tuple[float, dict[str, float], dict[str, int]]:
    train = [m for m in matches if train_before is None or m.match_date < train_before]
    pooled = fit_dispersion([m.home_corners + m.away_corners for m in train])
    by_league_values: dict[str, list[float]] = defaultdict(list)
    for m in train:
        by_league_values[m.league].append(m.home_corners + m.away_corners)
    by_league: dict[str, float] = {}
    counts: dict[str, int] = {}
    for league, totals in by_league_values.items():
        counts[league] = len(totals)
        by_league[league] = fit_dispersion(totals, fallback=pooled) if len(totals) >= 150 else pooled
    return pooled, by_league, counts


def add_nb_probs(predictions: list[dict[str, Any]], by_league_r: dict[str, float], pooled_r: float) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in predictions:
        league = str(row.get("league") or "").strip()
        r = by_league_r.get(league, pooled_r)
        mean = float(row.get("lambda_total") or 0.0)
        new_row = dict(row)
        new_row["nb_r"] = round(r, 4)
        for line in STANDARD_LINES:
            p_over = nb_total_prob_over(line, mean, r)
            p_under = 1.0 - p_over
            new_row[f"nb_p_over_{line}"] = round(p_over, 4)
            new_row[f"nb_fair_over_{line}"] = fair_decimal(p_over)
            new_row[f"nb_fair_under_{line}"] = fair_decimal(p_under)
        output.append(new_row)
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_report(rows: list[dict[str, Any]], pooled_r: float, by_league_r: dict[str, float], counts: dict[str, int]) -> str:
    lines = [
        "Corners NB Model Report",
        "",
        "Status: RESEARCH_ONLY",
        "Purpose: count/probability calibration only; ROI validation must use corners-real-odds-backtest.py.",
        "",
        f"predictions: {len(rows)}",
        f"pooled_nb_r: {pooled_r:.4f}",
        "",
        "League dispersion",
        "league,n_train,nb_r",
    ]
    for league in sorted(by_league_r):
        lines.append(f"{league},{counts.get(league, 0)},{by_league_r[league]:.4f}")
    lines.append("")
    for line in STANDARD_LINES:
        key = f"nb_p_over_{line}"
        subset = [row for row in rows if key in row]
        if not subset:
            continue
        actual = sum(1 for row in subset if float(row.get("actual_total") or 0.0) > line) / len(subset)
        pred = sum(float(row.get(key) or 0.0) for row in subset) / len(subset)
        lines.append(f"line_{line}: predicted={pred:.4f} actual={actual:.4f} diff={pred-actual:+.4f} n={len(subset)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build corners v2 NB prediction file")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--holdout-start", default=None, help="Optional YYYY-MM-DD output holdout start")
    parser.add_argument("--dispersion-train-before", default=None, help="Fit NB r only on matches before YYYY-MM-DD")
    args = parser.parse_args()

    v1 = load_v1_module()
    input_path = v1["resolve_historical_input"](args.input)
    matches = v1["load_matches"](input_path)
    holdout = date.fromisoformat(args.holdout_start) if args.holdout_start else None
    train_before = date.fromisoformat(args.dispersion_train_before) if args.dispersion_train_before else holdout
    pooled_r, by_league_r, counts = fit_dispersions(matches, train_before)
    predictions, _ = v1["run_model"](matches, holdout_start=holdout)
    rows = add_nb_probs(predictions, by_league_r, pooled_r)
    write_csv(args.output, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(rows, pooled_r, by_league_r, counts), encoding="utf-8")
    print(f"Wrote {args.output.relative_to(ROOT)}")
    print(f"Wrote {args.report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
