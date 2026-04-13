#!/usr/bin/env python3
"""
Roll up defender calibration audits across multiple league backtest outputs.

Usage:
  python scripts/goalscorer-defender-calibration-rollup.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "goalscorer" / "goalscorer-defender-calibration-rollup.txt"
DEFAULT_CSV = ROOT / "data" / "goalscorer" / "goalscorer-defender-calibration-rollup.csv"
TARGET_POSITIONS = {"DC", "D S"}
BANDS = [
    (0.00, 0.03, "0-3%"),
    (0.03, 0.05, "3-5%"),
    (0.05, 0.07, "5-7%"),
    (0.07, 0.10, "7-10%"),
    (0.10, 0.13, "10-13%"),
    (0.13, 0.17, "13-17%"),
    (0.17, 1.01, "17%+"),
]
DEFAULT_INPUTS = {
    "serie-a": ROOT / "data" / "goalscorer" / "goalscorer-backtest-results.csv",
    "epl": ROOT / "data" / "goalscorer" / "epl" / "goalscorer-backtest-results.csv",
    "la-liga": ROOT / "data" / "goalscorer" / "la-liga" / "goalscorer-backtest-results.csv",
    "bundesliga": ROOT / "data" / "goalscorer" / "bundesliga" / "goalscorer-backtest-results.csv",
    "ligue-1": ROOT / "data" / "goalscorer" / "ligue-1" / "goalscorer-backtest-results.csv",
}


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


def _mean_total(rows: list[dict], field: str, fn) -> float:
    if not rows:
        return 0.0
    return sum(fn(row.get(field)) for row in rows) / len(rows)


def _load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if (row.get("position_group") or "").strip() in TARGET_POSITIONS
        ]


def _summarize(rows: list[dict], label: str) -> dict:
    return {
        "league": label,
        "n": len(rows),
        "predicted": round(_mean_total(rows, "model_p_atgs", _pf), 4),
        "actual": round(_mean_total(rows, "scored", _pi), 4),
    }


def _band_rows(rows: list[dict], label: str) -> list[dict]:
    out: list[dict] = []
    for lo, hi, band in BANDS:
        subset = [row for row in rows if lo <= _pf(row.get("model_p_atgs")) < hi]
        if not subset:
            continue
        predicted = _mean_total(subset, "model_p_atgs", _pf)
        actual = _mean_total(subset, "scored", _pi)
        out.append(
            {
                "league": label,
                "band": band,
                "n": len(subset),
                "predicted": round(predicted, 4),
                "actual": round(actual, 4),
                "gap": round(actual - predicted, 4),
            }
        )
    return out


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["league", "band", "n", "predicted", "actual", "gap"])
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, summaries: list[dict], all_band_rows: list[dict], combined: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("Goalscorer Defender Calibration Rollup\n")
        handle.write("=====================================\n\n")
        handle.write(
            f"Combined defenders: n={combined['n']:,}  predicted={combined['predicted']:.4f}  "
            f"actual={combined['actual']:.4f}  gap={combined['actual'] - combined['predicted']:+.4f}\n\n"
        )

        handle.write("By league\n")
        handle.write("---------\n")
        for row in summaries:
            handle.write(
                f"{row['league']:<12} n={row['n']:>5}  predicted={row['predicted']:.4f}  "
                f"actual={row['actual']:.4f}  gap={row['actual'] - row['predicted']:+.4f}\n"
            )

        handle.write("\nBy league and probability band\n")
        handle.write("-----------------------------\n")
        for row in all_band_rows:
            handle.write(
                f"{row['league']:<12} {row['band']:>8}  n={row['n']:>5}  predicted={row['predicted']:.4f}  "
                f"actual={row['actual']:.4f}  gap={row['gap']:+.4f}\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Roll up defender calibration across leagues")
    parser.add_argument("--report-out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--csv-out", default=str(DEFAULT_CSV))
    args = parser.parse_args()

    summaries: list[dict] = []
    all_band_rows: list[dict] = []
    combined_rows: list[dict] = []
    for league, path in DEFAULT_INPUTS.items():
        rows = _load_rows(path)
        if not rows:
            continue
        combined_rows.extend(rows)
        summaries.append(_summarize(rows, league))
        all_band_rows.extend(_band_rows(rows, league))

    if not combined_rows:
        raise SystemExit("No defender rows found across the configured league backtests.")

    combined = _summarize(combined_rows, "all-leagues")
    summaries.insert(0, combined)
    _write_csv(Path(args.csv_out), all_band_rows)
    _write_report(Path(args.report_out), summaries, all_band_rows, combined)

    print(f"Combined defenders: {combined['n']:,}")
    print(f"Saved: {args.csv_out}")
    print(f"Saved: {args.report_out}")


if __name__ == "__main__":
    main()
