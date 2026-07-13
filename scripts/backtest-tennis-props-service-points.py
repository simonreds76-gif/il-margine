#!/usr/bin/env python3
"""Registered shadow gate for matchup-recursion service-point expectations.

The incumbent ace/DF rates and count dispersion remain unchanged. This test
changes only expected service workload and scores the fixed 2025 diagnostic
holdout produced by backtest-tennis-player-props.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from tennis_props_model import count_line_probabilities, resolve_count_dispersion  # noqa: E402


DEFAULT_SOURCE = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-totals-source-rows.csv"
DEFAULT_REPORT = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-service-points-report.txt"
DEFAULT_GATE = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-service-points-gate.json"
DEFAULT_CELLS = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-service-points-cells.csv"
TEST_YEAR = 2025
MIN_LOGLOSS_IMPROVEMENT = 0.001


def parse_float(value: object) -> float:
    try:
        return float(str(value or "").strip())
    except (TypeError, ValueError):
        return float("nan")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def binary_log_loss(probability: float, outcome: int) -> float:
    p = max(1e-8, min(1.0 - 1e-8, probability))
    return -(outcome * math.log(p) + (1 - outcome) * math.log1p(-p))


def service_point_summary(rows: list[dict[str, str]]) -> dict[str, float | int | bool]:
    current_errors: list[float] = []
    candidate_errors: list[float] = []
    for row in rows:
        actual = parse_float(row.get("actual_service_points"))
        current = parse_float(row.get("expected_service_points"))
        candidate = parse_float(row.get("candidate_expected_service_points"))
        if not all(math.isfinite(value) for value in (actual, current, candidate)):
            continue
        current_errors.append(abs(current - actual))
        candidate_errors.append(abs(candidate - actual))
    current_mae = mean(current_errors)
    candidate_mae = mean(candidate_errors)
    return {
        "n": len(current_errors),
        "current_mae": current_mae,
        "candidate_mae": candidate_mae,
        "mae_delta": candidate_mae - current_mae,
        "passed": candidate_mae <= current_mae,
    }


def market_summary(rows: list[dict[str, str]], tour: str, market: str) -> dict[str, float | int | bool | str]:
    actual_field = "actual_aces" if market == "aces" else "actual_dfs"
    current_field = "projected_aces" if market == "aces" else "projected_dfs"
    candidate_field = "candidate_projected_aces" if market == "aces" else "candidate_projected_dfs"
    naive_field = "naive_aces" if market == "aces" else "naive_dfs"
    alpha = resolve_count_dispersion(tour, market)
    current_errors: list[float] = []
    candidate_errors: list[float] = []
    current_signed: list[float] = []
    candidate_signed: list[float] = []
    current_losses: list[float] = []
    candidate_losses: list[float] = []

    for row in rows:
        actual = parse_float(row.get(actual_field))
        current = parse_float(row.get(current_field))
        candidate = parse_float(row.get(candidate_field))
        naive = parse_float(row.get(naive_field))
        if not all(math.isfinite(value) for value in (actual, current, candidate, naive)):
            continue
        line = math.floor(naive) + 0.5
        outcome = int(actual > line)
        current_prob = count_line_probabilities(
            line,
            current,
            distribution="negative_binomial",
            alpha=alpha,
            tour=tour,
            market=market,
        )[0]
        candidate_prob = count_line_probabilities(
            line,
            candidate,
            distribution="negative_binomial",
            alpha=alpha,
            tour=tour,
            market=market,
        )[0]
        current_errors.append(abs(current - actual))
        candidate_errors.append(abs(candidate - actual))
        current_signed.append(current - actual)
        candidate_signed.append(candidate - actual)
        current_losses.append(binary_log_loss(current_prob, outcome))
        candidate_losses.append(binary_log_loss(candidate_prob, outcome))

    current_mae = mean(current_errors)
    candidate_mae = mean(candidate_errors)
    current_ll = mean(current_losses)
    candidate_ll = mean(candidate_losses)
    mae_delta = candidate_mae - current_mae
    logloss_delta = candidate_ll - current_ll
    return {
        "tour": tour,
        "market": market,
        "n": len(current_errors),
        "mae_current": current_mae,
        "mae_candidate": candidate_mae,
        "mae_delta": mae_delta,
        "logloss_current": current_ll,
        "logloss_candidate": candidate_ll,
        "logloss_delta": logloss_delta,
        "bias_current": mean(current_signed),
        "bias_candidate": mean(candidate_signed),
        "passed_market": mae_delta <= 0.0 and logloss_delta <= -MIN_LOGLOSS_IMPROVEMENT,
    }


def write_cells(path: Path, cells: list[dict[str, object]]) -> None:
    fields = [
        "tour",
        "market",
        "n",
        "mae_current",
        "mae_candidate",
        "mae_delta",
        "logloss_current",
        "logloss_candidate",
        "logloss_delta",
        "bias_current",
        "bias_candidate",
        "service_points_mae_current",
        "service_points_mae_candidate",
        "service_points_mae_delta",
        "passed_market",
        "passed",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(cells)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out-gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--out-cells", type=Path, default=DEFAULT_CELLS)
    args = parser.parse_args()

    source_rows = [row for row in read_rows(args.source) if int(float(row.get("year") or 0)) == TEST_YEAR]
    if not source_rows:
        raise SystemExit(f"No {TEST_YEAR} service-point experiment rows in {args.source}")
    required = {
        "actual_service_points",
        "candidate_expected_service_points",
        "candidate_projected_aces",
        "candidate_projected_dfs",
    }
    missing = sorted(required - set(source_rows[0]))
    if missing:
        raise SystemExit(f"Source is missing candidate columns: {', '.join(missing)}")

    by_tour: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        by_tour[str(row.get("tour") or "").upper()].append(row)

    service_points = {tour: service_point_summary(by_tour[tour]) for tour in ("ATP", "WTA")}
    cells: list[dict[str, object]] = []
    for tour in ("ATP", "WTA"):
        for market in ("aces", "dfs"):
            cell = market_summary(by_tour[tour], tour, market)
            sp = service_points[tour]
            passed = bool(cell["passed_market"]) and bool(sp["passed"])
            cells.append(
                {
                    **cell,
                    "service_points_mae_current": sp["current_mae"],
                    "service_points_mae_candidate": sp["candidate_mae"],
                    "service_points_mae_delta": sp["mae_delta"],
                    "passed": passed,
                }
            )

    passed = all(bool(cell["passed"]) for cell in cells)
    generated_at = datetime.now(timezone.utc).isoformat()
    gate = {
        "version": "tennis-props-service-points-v1",
        "generated_at": generated_at,
        "status": "PASS" if passed else "FAIL",
        "routing": "shadow_eligible" if passed else "blocked",
        "diagnostic_test_year": TEST_YEAR,
        "registered_change": "expected service points only; ace/DF rates and dispersion unchanged",
        "minimum_logloss_improvement": MIN_LOGLOSS_IMPROVEMENT,
        "service_points": service_points,
        "cells": cells,
        "next_action": "prospective shadow comparison" if passed else "keep incumbent service-point driver",
    }
    args.out_gate.parent.mkdir(parents=True, exist_ok=True)
    args.out_gate.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    write_cells(args.out_cells, cells)

    lines = [
        "Tennis Props - Registered Service-Point Recursion Experiment",
        f"Generated UTC: {generated_at}",
        f"Diagnostic test year: {TEST_YEAR}",
        "Change: expected service points only; incumbent ace/DF rates and dispersion unchanged.",
        f"Gate: service-point MAE must improve and every tour/market must have MAE <= incumbent plus log-loss delta <= -{MIN_LOGLOSS_IMPROVEMENT:.3f}.",
        "",
        "Tour Market     N   SP MAE current/candidate   Count MAE current/candidate   LL current/candidate   Delta LL   Gate",
    ]
    for cell in cells:
        lines.append(
            f"{cell['tour']:3s}  {cell['market']:5s} {int(cell['n']):5d}   "
            f"{float(cell['service_points_mae_current']):.4f}/{float(cell['service_points_mae_candidate']):.4f}              "
            f"{float(cell['mae_current']):.4f}/{float(cell['mae_candidate']):.4f}                  "
            f"{float(cell['logloss_current']):.6f}/{float(cell['logloss_candidate']):.6f}  "
            f"{float(cell['logloss_delta']):+.6f}   {'PASS' if cell['passed'] else 'FAIL'}"
        )
    lines.extend(
        [
            "",
            f"VERDICT: {gate['status']}",
            f"Routing: {gate['routing']}",
            f"Next: {gate['next_action']}",
            "This is outcome-only evidence. It is not ROI or CLV evidence.",
        ]
    )
    args.out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.out_report)
    print(args.out_gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
