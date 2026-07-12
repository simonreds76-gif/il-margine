#!/usr/bin/env python3
"""Fit the registered vNext static hierarchical process models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import DEFAULT_OUTPUT_DIR, read_rows_csv_gz, sha256_file, write_json
from model_spec import PROCESS_SPECS, VERSION, fit_process, prior_predictive_hold_range


def _typed(row: dict[str, str]) -> dict[str, object]:
    numeric = {"date_ord", "year", "tour_rank", "round_id", "server_id", "returner_id", "server_won_match", "serve_points", "first_in", "first_won", "second_attempts", "second_in", "second_won", "aces", "double_faults"}
    return {key: int(value) if key in numeric else value for key, value in row.items()}


def fit_models(rows: list[dict[str, object]], pooling_strength: float) -> dict[str, object]:
    models = {name: fit_process(rows, name, pooling_strength) for name in PROCESS_SPECS}
    return {
        "version": VERSION,
        "pooling_strength": pooling_strength,
        "models": {name: model.to_json() for name, model in models.items()},
        "prior_predictive_hold_range": prior_predictive_hold_range(models),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_DIR / "serve-counts-atp.csv.gz")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR / f"params-{VERSION}.json")
    parser.add_argument("--pooling-strength", type=float, default=75.0)
    parser.add_argument("--train-end-year", type=int, default=2023)
    args = parser.parse_args()

    rows = [_typed(row) for row in read_rows_csv_gz(args.input)]
    train = [row for row in rows if int(row["year"]) <= args.train_end_year and row["tour_level"] in {"ATP", "Grand Slam"}]
    payload = fit_models(train, args.pooling_strength)
    payload["input"] = {"path": str(args.input), "sha256": sha256_file(args.input), "train_rows": len(train), "train_end_year": args.train_end_year}
    write_json(args.output, payload)
    hold = payload["prior_predictive_hold_range"]
    print(f"Fitted {len(PROCESS_SPECS)} processes on {len(train):,} player-match rows")
    print(f"Prior predictive hold p01-p99: {hold['min']:.3f}-{hold['max']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
