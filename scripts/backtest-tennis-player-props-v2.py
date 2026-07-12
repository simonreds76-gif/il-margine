#!/usr/bin/env python3
"""Registered props-v2 rung 1: causal hierarchical count dispersion.

The incumbent count means remain untouched. This script fits negative-binomial
dispersion on 2022-2024 only, scores the untouched 2025 rows, and fails closed
unless every tour/market cell improves O/U log-loss without worsening MAE.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-v2-source-rows.csv"
OUT_CSV = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-v2-rung1-rows.csv"
OUT_REPORT = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-v2-rung1-report.txt"
OUT_GATE = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-v2-rung1-gate.json"

CURRENT_ALPHA = {
    ("ATP", "aces"): 0.35,
    ("WTA", "aces"): 0.50,
    ("ATP", "dfs"): 0.10,
    ("WTA", "dfs"): 0.20,
}
TRAIN_YEARS = {2022, 2023, 2024}
TEST_YEAR = 2025
MIN_GROUP = 8
TOURNAMENT_PRIOR = 300.0
PLAYER_PRIOR = 30.0


@dataclass(frozen=True)
class CountRow:
    tour: str
    year: int
    tournament: str
    player_id: str
    player: str
    market: str
    actual: int
    mean: float
    naive: float


def read_rows(path: Path) -> list[CountRow]:
    rows: list[CountRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            for market, actual_col, mean_col, naive_col in (
                ("aces", "actual_aces", "projected_aces", "naive_aces"),
                ("dfs", "actual_dfs", "projected_dfs", "naive_dfs"),
            ):
                rows.append(
                    CountRow(
                        tour=str(raw["tour"]).upper(),
                        year=int(raw["year"]),
                        tournament=str(raw["tournament"]),
                        player_id=str(raw["player_id"]),
                        player=str(raw["player"]),
                        market=market,
                        actual=int(float(raw[actual_col])),
                        mean=max(1e-6, float(raw[mean_col])),
                        naive=max(1e-6, float(raw[naive_col])),
                    )
                )
    return rows


def nb_log_pmf(actual: int, mean: float, alpha: float) -> float:
    alpha = max(1e-6, alpha)
    size = 1.0 / alpha
    prob = size / (size + mean)
    return (
        math.lgamma(actual + size)
        - math.lgamma(size)
        - math.lgamma(actual + 1)
        + size * math.log(prob)
        + actual * math.log1p(-prob)
    )


def nb_cdf(cutoff: int, mean: float, alpha: float) -> float:
    if cutoff < 0:
        return 0.0
    total = 0.0
    for actual in range(cutoff + 1):
        total += math.exp(nb_log_pmf(actual, mean, alpha))
    return max(0.0, min(1.0, total))


def over_probability(line: float, mean: float, alpha: float) -> float:
    return 1.0 - nb_cdf(math.floor(line), mean, alpha)


def binary_log_loss(probability: float, outcome: int) -> float:
    p = max(1e-8, min(1.0 - 1e-8, probability))
    return -(outcome * math.log(p) + (1 - outcome) * math.log1p(-p))


def alpha_grid() -> list[float]:
    lo, hi, count = math.log(0.01), math.log(1.5), 121
    return [math.exp(lo + (hi - lo) * idx / (count - 1)) for idx in range(count)]


def fit_alpha(rows: list[CountRow], fallback: float) -> float:
    if len(rows) < MIN_GROUP:
        return fallback
    return min(alpha_grid(), key=lambda alpha: -sum(nb_log_pmf(r.actual, r.mean, alpha) for r in rows))


def shrink_alpha(raw: float, parent: float, sample: int, prior: float) -> float:
    if sample < MIN_GROUP:
        return parent
    weight = sample / (sample + prior)
    return math.exp(weight * math.log(raw) + (1.0 - weight) * math.log(parent))


def fit_hierarchy(train: list[CountRow]) -> dict[str, dict[tuple[str, ...], float]]:
    by_base: dict[tuple[str, str], list[CountRow]] = defaultdict(list)
    by_tournament: dict[tuple[str, str, str], list[CountRow]] = defaultdict(list)
    by_player: dict[tuple[str, str, str], list[CountRow]] = defaultdict(list)
    for row in train:
        by_base[(row.tour, row.market)].append(row)
        by_tournament[(row.tour, row.market, row.tournament)].append(row)
        by_player[(row.tour, row.market, row.player_id)].append(row)

    base: dict[tuple[str, ...], float] = {}
    tournament: dict[tuple[str, ...], float] = {}
    player: dict[tuple[str, ...], float] = {}
    for key, group in by_base.items():
        base[key] = fit_alpha(group, CURRENT_ALPHA[key])
    for key, group in by_tournament.items():
        parent = base[key[:2]]
        tournament[key] = shrink_alpha(fit_alpha(group, parent), parent, len(group), TOURNAMENT_PRIOR)
    for key, group in by_player.items():
        parent = base[key[:2]]
        player[key] = shrink_alpha(fit_alpha(group, parent), parent, len(group), PLAYER_PRIOR)
    return {"base": base, "tournament": tournament, "player": player}


def resolved_alpha(row: CountRow, fitted: dict[str, dict[tuple[str, ...], float]]) -> float:
    base = fitted["base"][(row.tour, row.market)]
    event = fitted["tournament"].get((row.tour, row.market, row.tournament), base)
    player = fitted["player"].get((row.tour, row.market, row.player_id), base)
    # Tournament and player are independent children of the same train-only
    # tour/market parent. Combine their log deviations conservatively.
    delta = 0.55 * (math.log(event) - math.log(base)) + 0.45 * (math.log(player) - math.log(base))
    return max(0.01, min(1.5, math.exp(math.log(base) + delta)))


def summarise(rows: list[CountRow], fitted: dict[str, dict[tuple[str, ...], float]]) -> dict[str, float]:
    current_losses: list[float] = []
    v2_losses: list[float] = []
    absolute_errors: list[float] = []
    for row in rows:
        line = math.floor(row.naive) + 0.5
        outcome = int(row.actual > line)
        current_alpha = CURRENT_ALPHA[(row.tour, row.market)]
        v2_alpha = resolved_alpha(row, fitted)
        current_losses.append(binary_log_loss(over_probability(line, row.mean, current_alpha), outcome))
        v2_losses.append(binary_log_loss(over_probability(line, row.mean, v2_alpha), outcome))
        absolute_errors.append(abs(row.mean - row.actual))
    n = len(rows)
    return {
        "n": n,
        "mae_current": sum(absolute_errors) / n,
        "mae_v2": sum(absolute_errors) / n,
        "mae_delta": 0.0,
        "logloss_current": sum(current_losses) / n,
        "logloss_v2": sum(v2_losses) / n,
        "logloss_delta": (sum(v2_losses) - sum(current_losses)) / n,
    }


def serialise_params(fitted: dict[str, dict[tuple[str, ...], float]]) -> dict[str, dict[str, float]]:
    return {
        level: {"|".join(key): round(value, 8) for key, value in sorted(values.items())}
        for level, values in fitted.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--out-report", type=Path, default=OUT_REPORT)
    parser.add_argument("--out-gate", type=Path, default=OUT_GATE)
    args = parser.parse_args()

    rows = read_rows(args.source)
    train = [row for row in rows if row.year in TRAIN_YEARS]
    test = [row for row in rows if row.year == TEST_YEAR]
    if not train or not test:
        raise SystemExit("Missing registered train or untouched test rows")
    fitted = fit_hierarchy(train)

    cells: list[dict[str, object]] = []
    for tour in ("ATP", "WTA"):
        for market in ("aces", "dfs"):
            group = [row for row in test if row.tour == tour and row.market == market]
            summary = summarise(group, fitted)
            passed = summary["mae_delta"] <= 0.0 and summary["logloss_delta"] <= -0.001
            cells.append({"tour": tour, "market": market, **summary, "passed": passed})

    passed = all(bool(cell["passed"]) for cell in cells)
    gate = {
        "version": "tennis-props-v2-rung-1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "routing": "research_only" if passed else "blocked",
        "train_years": sorted(TRAIN_YEARS),
        "untouched_test_year": TEST_YEAR,
        "cells": cells,
        "parameters": serialise_params(fitted),
        "next_action": "evaluate expected-service-points rung" if passed else "keep incumbent; do not wire v2",
    }
    args.out_gate.parent.mkdir(parents=True, exist_ok=True)
    args.out_gate.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")

    with args.out_csv.open("w", encoding="utf-8", newline="") as handle:
        fields = ["tour", "market", "n", "mae_current", "mae_v2", "mae_delta", "logloss_current", "logloss_v2", "logloss_delta", "passed"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(cells)

    lines = [
        "Tennis Props v2 - Registered Rung 1",
        f"Generated UTC: {gate['generated_at']}",
        "Train: 2022-2024 | untouched test: 2025",
        "Incumbent means unchanged; only negative-binomial dispersion changes.",
        "Gate: every tour/market cell must have MAE delta <= 0 and log-loss delta <= -0.001.",
        "",
        "Tour Market      N   MAE current/v2  LL current/v2   Delta LL   Gate",
    ]
    for cell in cells:
        lines.append(
            f"{cell['tour']:3s}  {cell['market']:5s} {int(cell['n']):5d}   "
            f"{cell['mae_current']:.4f}/{cell['mae_v2']:.4f}     "
            f"{cell['logloss_current']:.6f}/{cell['logloss_v2']:.6f}  "
            f"{cell['logloss_delta']:+.6f}   {'PASS' if cell['passed'] else 'FAIL'}"
        )
    lines.extend(["", f"VERDICT: {gate['status']}", f"Routing: {gate['routing']}", f"Next: {gate['next_action']}"])
    args.out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.out_report)
    print(args.out_gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
