#!/usr/bin/env python3
"""
Audit defender calibration in the historical goalscorer backtest.

This is a focused diagnostic for centre-backs / sweepers, where we care about
whether predicted ATGS probabilities line up with actual scoring rates by
probability band.

Usage:
  python scripts/goalscorer-defender-calibration-audit.py
  python scripts/goalscorer-defender-calibration-audit.py --backtest data/goalscorer/goalscorer-backtest-results.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKTEST = ROOT / "data" / "goalscorer" / "goalscorer-backtest-results.csv"
DEFAULT_REPORT = ROOT / "data" / "goalscorer" / "goalscorer-defender-calibration-audit.txt"
DEFAULT_BINS = ROOT / "data" / "goalscorer" / "goalscorer-defender-calibration-bins.csv"
TARGET_POSITIONS = {"DC", "D S"}
PROBABILITY_BANDS = [
    (0.00, 0.03, "0-3%"),
    (0.03, 0.05, "3-5%"),
    (0.05, 0.07, "5-7%"),
    (0.07, 0.10, "7-10%"),
    (0.10, 0.13, "10-13%"),
    (0.13, 0.17, "13-17%"),
    (0.17, 1.01, "17%+"),
]


def _pf(value, default=0.0) -> float:
    try:
        text = str(value or "").strip()
        return float(text) if text else default
    except ValueError:
        return default


def _pi(value, default=0) -> int:
    try:
        text = str(value or "").strip()
        return int(float(text)) if text else default
    except ValueError:
        return default


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _bucket_rows(rows: list[dict]) -> list[dict]:
    bucketed: list[dict] = []
    for lo, hi, label in PROBABILITY_BANDS:
        bucket = [row for row in rows if lo <= _pf(row.get("model_p_atgs")) < hi]
        if not bucket:
            continue
        predicted = _mean(_pf(row.get("model_p_atgs")) for row in bucket)
        actual = _mean(_pi(row.get("scored")) for row in bucket)
        bucketed.append(
            {
                "bin": label,
                "n": len(bucket),
                "predicted": round(predicted, 4),
                "actual": round(actual, 4),
                "gap": round(actual - predicted, 4),
            }
        )
    return bucketed


def _threshold_rows(rows: list[dict], thresholds: list[float]) -> list[dict]:
    out: list[dict] = []
    for threshold in thresholds:
        subset = [row for row in rows if _pf(row.get("model_p_atgs")) >= threshold]
        if not subset:
            continue
        predicted = _mean(_pf(row.get("model_p_atgs")) for row in subset)
        actual = _mean(_pi(row.get("scored")) for row in subset)
        out.append(
            {
                "threshold": threshold,
                "n": len(subset),
                "predicted": round(predicted, 4),
                "actual": round(actual, 4),
                "gap": round(actual - predicted, 4),
            }
        )
    return out


def _season_rows(rows: list[dict]) -> list[dict]:
    seasons = sorted({(row.get("season") or "").strip() for row in rows if (row.get("season") or "").strip()})
    out: list[dict] = []
    for season in seasons:
        subset = [row for row in rows if (row.get("season") or "").strip() == season]
        predicted = _mean(_pf(row.get("model_p_atgs")) for row in subset)
        actual = _mean(_pi(row.get("scored")) for row in subset)
        out.append(
            {
                "season": season,
                "n": len(subset),
                "predicted": round(predicted, 4),
                "actual": round(actual, 4),
                "gap": round(actual - predicted, 4),
            }
        )
    return out


def _write_bins(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["bin", "n", "predicted", "actual", "gap"])
        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    path: Path,
    total_rows: int,
    defender_rows: list[dict],
    by_position: list[dict],
    by_season: list[dict],
    by_bin: list[dict],
    by_threshold: list[dict],
) -> None:
    predicted = _mean(_pf(row.get("model_p_atgs")) for row in defender_rows)
    actual = _mean(_pi(row.get("scored")) for row in defender_rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("Goalscorer Defender Calibration Audit\n")
        handle.write("===================================\n\n")
        handle.write(f"Backtest rows:          {total_rows:,}\n")
        handle.write(f"Target defender rows:   {len(defender_rows):,}\n")
        handle.write(f"Predicted score rate:   {predicted:.4f}\n")
        handle.write(f"Actual score rate:      {actual:.4f}\n")
        handle.write(f"Calibration gap:        {actual - predicted:+.4f}\n\n")

        handle.write("By position\n")
        handle.write("-----------\n")
        for row in by_position:
            handle.write(
                f"{row['position']:<10} n={row['n']:>5}  predicted={row['predicted']:.4f}  "
                f"actual={row['actual']:.4f}  gap={row['gap']:+.4f}\n"
            )

        handle.write("\nBy season\n")
        handle.write("---------\n")
        for row in by_season:
            handle.write(
                f"{row['season']:<10} n={row['n']:>5}  predicted={row['predicted']:.4f}  "
                f"actual={row['actual']:.4f}  gap={row['gap']:+.4f}\n"
            )

        handle.write("\nProbability bands\n")
        handle.write("-----------------\n")
        for row in by_bin:
            handle.write(
                f"{row['bin']:>8}  n={row['n']:>5}  predicted={row['predicted']:.4f}  "
                f"actual={row['actual']:.4f}  gap={row['gap']:+.4f}\n"
            )

        handle.write("\nTail thresholds\n")
        handle.write("---------------\n")
        for row in by_threshold:
            handle.write(
                f"p>={row['threshold']:.0%}  n={row['n']:>5}  predicted={row['predicted']:.4f}  "
                f"actual={row['actual']:.4f}  gap={row['gap']:+.4f}\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit defender calibration in the goalscorer backtest")
    parser.add_argument("--backtest", default=str(DEFAULT_BACKTEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--bins-out", default=str(DEFAULT_BINS))
    args = parser.parse_args()

    backtest_path = Path(args.backtest)
    rows = _load_rows(backtest_path)
    defender_rows = [
        row for row in rows
        if (row.get("position_group") or "").strip() in TARGET_POSITIONS
    ]
    if not defender_rows:
        raise SystemExit("No DC / D S rows found in backtest results.")

    positions = sorted({(row.get("position_group") or "").strip() for row in defender_rows})
    by_position = []
    for position in positions:
        subset = [row for row in defender_rows if (row.get("position_group") or "").strip() == position]
        predicted = _mean(_pf(row.get("model_p_atgs")) for row in subset)
        actual = _mean(_pi(row.get("scored")) for row in subset)
        by_position.append(
            {
                "position": position,
                "n": len(subset),
                "predicted": round(predicted, 4),
                "actual": round(actual, 4),
                "gap": round(actual - predicted, 4),
            }
        )

    by_season = _season_rows(defender_rows)
    by_bin = _bucket_rows(defender_rows)
    by_threshold = _threshold_rows(defender_rows, [0.07, 0.10, 0.13, 0.17])

    _write_bins(Path(args.bins_out), by_bin)
    _write_report(
        Path(args.report_out),
        len(rows),
        defender_rows,
        by_position,
        by_season,
        by_bin,
        by_threshold,
    )

    print(f"Defender rows: {len(defender_rows):,}")
    print(f"Saved: {args.bins_out}")
    print(f"Saved: {args.report_out}")


if __name__ == "__main__":
    main()
