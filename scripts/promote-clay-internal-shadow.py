#!/usr/bin/env python3
"""Materialise internal clay research lanes for monitor settlement.

Two clay lanes are intentionally research-only:
- Clay-Fav HC: extracted from spread_v1_shadow favorite-handicap rows.
- Clay Calibrated: already produced by strict-signals-claycal; this helper keeps
  the monitor-facing performance artifacts fresh without changing production.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPREAD_V1_ARCHIVE = ROOT / "data" / "backtest" / "strict-signals-spreadv1-archive.csv"
CLAY_FAV_ARCHIVE = ROOT / "data" / "backtest" / "strict-signals-clay-fav-archive.csv"
CLAY_FAV_LIVE = ROOT / "data" / "backtest" / "strict-signals-clay-fav-live.csv"
CLAY_FAV_REPORT = ROOT / "data" / "backtest" / "strict-policy-performance-clay-fav-weekly.txt"
CLAY_FAV_SUMMARY = ROOT / "data" / "backtest" / "strict-policy-performance-clay-fav-weekly.csv"
CLAYCAL_ARCHIVE = ROOT / "data" / "backtest" / "strict-signals-claycal-archive.csv"
CLAYCAL_REPORT = ROOT / "data" / "backtest" / "strict-policy-performance-clay2026-weekly.txt"
CLAYCAL_SUMMARY = ROOT / "data" / "backtest" / "strict-policy-performance-clay2026-weekly.csv"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def selected_side_is_favorite(row: dict[str, str]) -> bool:
    side = (row.get("side") or "").strip().upper()
    try:
        line = float(row.get("spread_line") or "0")
    except ValueError:
        return False
    if side == "P1+":
        return line < 0
    if side == "P2-":
        return line > 0
    return False


def build_clay_fav_archive() -> int:
    fields, rows = read_csv(SPREAD_V1_ARCHIVE)
    if not fields:
        raise FileNotFoundError(f"Missing spread v1 archive: {SPREAD_V1_ARCHIVE}")
    out_fields = list(fields)
    for field in ["source_signal_profile", "derived_lane", "orientation"]:
        if field not in out_fields:
            out_fields.append(field)

    selected: list[dict[str, str]] = []
    for row in rows:
        if (row.get("surface") or "").strip().lower() != "clay":
            continue
        if (row.get("bet_type") or "").strip().lower() != "spread":
            continue
        if not selected_side_is_favorite(row):
            continue
        promoted = dict(row)
        promoted["source_signal_profile"] = promoted.get("signal_profile", "")
        promoted["signal_profile"] = "clay_fav_hc_internal"
        promoted["derived_lane"] = "spread_v1_shadow_favorite_handicap"
        promoted["orientation"] = "favorite_handicap"
        selected.append(promoted)

    live_rows = [
        row
        for row in selected
        if (row.get("settlement_status") or "").strip().lower() not in {"settled", "no_match"}
    ]
    write_csv(CLAY_FAV_ARCHIVE, out_fields, selected)
    write_csv(CLAY_FAV_LIVE, out_fields, live_rows)
    return len(selected)


def refresh_performance(signals: Path, report: Path, summary: Path) -> None:
    if summary.exists():
        summary.unlink()
    if report.exists():
        report.unlink()
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "strict-policy-performance.py"),
            "--signals",
            str(signals),
            "--report-txt",
            str(report),
            "--summary-csv",
            str(summary),
            "--days",
            "7",
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-claycal", action="store_true", help="Only build Clay-Fav HC artifacts")
    args = parser.parse_args()

    clay_fav_count = build_clay_fav_archive()
    refresh_performance(CLAY_FAV_ARCHIVE, CLAY_FAV_REPORT, CLAY_FAV_SUMMARY)
    if not args.skip_claycal:
        refresh_performance(CLAYCAL_ARCHIVE, CLAYCAL_REPORT, CLAYCAL_SUMMARY)
    print(f"clay_fav_rows={clay_fav_count} clay_fav_archive={CLAY_FAV_ARCHIVE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
