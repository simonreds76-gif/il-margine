#!/usr/bin/env python3
"""Calibration diagnostics for repaired goalscorer population segments."""

from __future__ import annotations

import argparse
import csv
import runpy
from collections import defaultdict
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "goalscorer" / "backtest" / "segment-diagnostics.csv"
MIN_SEGMENT_ROWS = 100


def summarize(rows: list[dict]) -> dict:
    probabilities = [float(row["model_p_atgs"]) for row in rows]
    labels = [int(row["scored"]) for row in rows]
    predicted = mean(probabilities) if probabilities else 0.0
    actual = mean(labels) if labels else 0.0
    return {
        "n": len(rows),
        "predicted": predicted,
        "actual": actual,
        "gap": actual - predicted,
        "brier": mean((probability - label) ** 2 for probability, label in zip(probabilities, labels)) if rows else 0.0,
    }


def cohort_rows(rows: list[dict], cohort: str) -> list[dict]:
    model_rows = [row for row in rows if row.get("method") == "model"]
    if cohort == "live_proxy":
        return [
            row
            for row in model_rows
            if float(row.get("expected_minutes") or 0.0) >= 65
            and str(row.get("position_group") or "").upper() != "SUB"
        ]
    return model_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    walkforward = runpy.run_path(str(ROOT / "scripts" / "goalscorer-walkforward.py"), run_name="goalscorer_segment_loader")
    rows, _inputs = walkforward["build_base_rows"]()
    report_rows: list[dict] = []

    for cohort in ("all_model", "live_proxy"):
        population = cohort_rows(rows, cohort)
        overall = summarize(population)
        report_rows.append({"cohort": cohort, "dimension": "overall", "segment": "all", **overall, "gap_vs_overall": 0.0})
        dimensions = {
            "league": lambda row: str(row.get("league") or "unknown"),
            "position": lambda row: str(row.get("position_group") or "Unknown"),
            "minutes": lambda row: str(row.get("minutes_band") or "unknown"),
            "starter": lambda row: "starter" if str(row.get("confirmed_started")) == "1" else "bench" if str(row.get("confirmed_started")) == "0" else "unknown",
        }
        for dimension, key_func in dimensions.items():
            grouped: dict[str, list[dict]] = defaultdict(list)
            for row in population:
                grouped[key_func(row)].append(row)
            for segment, segment_rows in sorted(grouped.items()):
                if len(segment_rows) < MIN_SEGMENT_ROWS:
                    continue
                summary = summarize(segment_rows)
                report_rows.append(
                    {
                        "cohort": cohort,
                        "dimension": dimension,
                        "segment": segment,
                        **summary,
                        "gap_vs_overall": summary["gap"] - overall["gap"],
                    }
                )

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["cohort", "dimension", "segment", "n", "predicted", "actual", "gap", "gap_vs_overall", "brier"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report_rows:
            writer.writerow(
                {
                    **row,
                    "predicted": f"{row['predicted']:.6f}",
                    "actual": f"{row['actual']:.6f}",
                    "gap": f"{row['gap']:.6f}",
                    "gap_vs_overall": f"{row['gap_vs_overall']:.6f}",
                    "brier": f"{row['brier']:.6f}",
                }
            )

    all_model = cohort_rows(rows, "all_model")
    assert not any(str(row.get("position_group") or "").upper() == "SUB" for row in all_model), "Sub leaked into position groups"
    minutes_30_59 = next(
        row for row in report_rows if row["cohort"] == "all_model" and row["dimension"] == "minutes" and row["segment"] == "30-59"
    )
    within_five_pp = abs(float(minutes_30_59["gap_vs_overall"])) <= 0.05
    text_path = output.with_suffix(".txt")
    text_path.write_text(
        "Goalscorer Segment Diagnostics\n"
        "===============================\n\n"
        f"Rows: {len(all_model):,}\n"
        "Position=Sub rows: 0\n"
        f"30-59 gap vs overall: {float(minutes_30_59['gap_vs_overall']):+.3%}\n"
        f"30-59 within +/-5pp: {'PASS' if within_five_pp else 'FAIL'}\n"
        f"CSV: {(output.relative_to(ROOT) if output.is_relative_to(ROOT) else output).as_posix()}\n",
        encoding="utf-8",
    )
    print(f"GOALSCORER_SEGMENTS rows={len(all_model)} 30_59_gap_delta={float(minutes_30_59['gap_vs_overall']):+.6f}")
    print(f"Report: {text_path}")
    assert within_five_pp, "30-59 minute segment remains more than 5pp from overall calibration gap"


if __name__ == "__main__":
    main()
