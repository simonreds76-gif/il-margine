#!/usr/bin/env python3
"""Build the offline feature CSV for the clay ML v2 validation model.

This script is deliberately year-driven: the caller decides which historical
years are materialized. Do not build sealed-year features before the validation
report has passed review.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from _lib.clay_v2_features import (
    OUTPUT_COLUMNS,
    build_feature_row,
    build_history_index,
    load_backtest_rows,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "backtest" / "clay-v2-features-2022-2024.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build clay ML v2 feature rows.")
    parser.add_argument("--years", nargs="+", type=int, required=True, help="Backtest years to materialize.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output feature CSV path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    print(f"building clay v2 features for years={years}")
    index = build_history_index()
    source_rows = load_backtest_rows(years)
    built: list[dict[str, object]] = []
    skipped = 0
    for source_row in source_rows:
        row = build_feature_row(source_row, index)
        if row is None:
            skipped += 1
            continue
        built.append(row)

    built.sort(key=lambda row: (str(row["date"]), int(row["winner_id"]), int(row["loser_id"])))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(built)

    labels = Counter(int(row["label_player_a_win"]) for row in built)
    cohorts = Counter(str(row["tournament_cohort"]) for row in built)
    print(f"wrote {len(built)} rows to {args.out}")
    print(f"skipped {skipped} non-clay/incomplete rows")
    print(f"label counts: {dict(sorted(labels.items()))}")
    print(f"top cohorts: {cohorts.most_common(12)}")
    print(f"feature columns: {len(OUTPUT_COLUMNS) - 19}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
