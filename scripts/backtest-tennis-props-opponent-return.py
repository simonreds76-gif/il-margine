#!/usr/bin/env python3
"""Registered ace-rate experiment for the opponent-return exponent.

The candidate changes only the exponent applied to opponent first-return
quality. Player rates, venue factors, workload and distribution family remain
fixed. Exponents are selected on pre-2025 matches and scored once on 2025.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parent.parent
BACKTEST_DIR = ROOT / "data" / "tennis-props" / "backtest"
DEFAULT_SOURCE = BACKTEST_DIR / "aces-dfs-totals-source-rows.csv"
DEFAULT_REPORT = BACKTEST_DIR / "aces-opponent-return-report.txt"
DEFAULT_GATE = BACKTEST_DIR / "aces-opponent-return-gate.json"
DEFAULT_GRID = BACKTEST_DIR / "aces-opponent-return-grid.csv"

HOLDOUT_YEAR = 2025
CURRENT_EXPONENT = 0.6
EXPONENT_GRID = tuple(round(step * 0.05, 2) for step in range(21))
MIN_TRAIN_NLL_IMPROVEMENT = 0.0005
MIN_HOLDOUT_LOGLOSS_IMPROVEMENT = 0.001


@dataclass(frozen=True)
class SideInput:
    pre_opponent_rate: float
    return_ratio: float
    expected_service_points: float


@dataclass(frozen=True)
class MatchRow:
    tour: str
    year: int
    date: str
    tournament: str
    actual_aces: int
    current_aces: float
    naive_aces: float
    sides: tuple[SideInput, SideInput]


def parse_float(value: object) -> float | None:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def norm_name(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch)).lower()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in raw).split())


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def candidate_side_mean(side: SideInput, exponent: float) -> float:
    return (
        clip(side.pre_opponent_rate * clip(side.return_ratio**exponent, 0.76, 1.22), 0.002, 0.28)
        * side.expected_service_points
    )


def candidate_match_mean(row: MatchRow, exponent: float) -> float:
    return sum(candidate_side_mean(side, exponent) for side in row.sides)


def read_matches(path: Path) -> list[MatchRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    required = {
        "ace_rate_pre_opponent",
        "opponent_return_ratio",
        "expected_service_points",
    }
    if not source_rows:
        return []
    missing = sorted(required - set(source_rows[0]))
    if missing:
        raise SystemExit(f"Source is missing opponent-return columns: {', '.join(missing)}")

    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        player = norm_name(row.get("player"))
        opponent = norm_name(row.get("opponent"))
        if not player or not opponent:
            continue
        pair = tuple(sorted((player, opponent)))
        key = (
            str(row.get("tour") or "").upper(),
            str(row.get("year") or ""),
            str(row.get("date") or ""),
            str(row.get("tournament") or ""),
            str(row.get("round") or ""),
            pair[0],
            pair[1],
        )
        grouped[key].append(row)

    matches: list[MatchRow] = []
    for key, rows in grouped.items():
        if len(rows) != 2 or len({norm_name(row.get("player")) for row in rows}) != 2:
            continue
        numeric_fields = (
            "actual_aces",
            "projected_aces",
            "naive_aces",
            "ace_rate_pre_opponent",
            "opponent_return_ratio",
            "expected_service_points",
        )
        parsed = {field: [parse_float(row.get(field)) for row in rows] for field in numeric_fields}
        if any(any(value is None for value in values) for values in parsed.values()):
            continue
        sides = tuple(
            SideInput(
                pre_opponent_rate=float(parsed["ace_rate_pre_opponent"][index]),
                return_ratio=float(parsed["opponent_return_ratio"][index]),
                expected_service_points=float(parsed["expected_service_points"][index]),
            )
            for index in range(2)
        )
        matches.append(
            MatchRow(
                tour=key[0],
                year=int(key[1]),
                date=key[2],
                tournament=key[3],
                actual_aces=int(round(sum(float(value) for value in parsed["actual_aces"]))),
                current_aces=sum(float(value) for value in parsed["projected_aces"]),
                naive_aces=sum(float(value) for value in parsed["naive_aces"]),
                sides=(sides[0], sides[1]),
            )
        )
    return sorted(matches, key=lambda row: (row.date, row.tour, row.tournament))


def nb_log_pmf(actual: int, expected: float, alpha: float) -> float:
    size = 1.0 / alpha
    probability = size / (size + max(0.01, expected))
    return (
        math.lgamma(actual + size)
        - math.lgamma(size)
        - math.lgamma(actual + 1)
        + size * math.log(probability)
        + actual * math.log1p(-probability)
    )


def fit_alpha(rows: list[MatchRow], exponent: float | None) -> float:
    def expected(row: MatchRow) -> float:
        return row.current_aces if exponent is None else candidate_match_mean(row, exponent)

    def objective(log_alpha: float) -> float:
        alpha = math.exp(log_alpha)
        return -sum(nb_log_pmf(row.actual_aces, expected(row), alpha) for row in rows)

    left, right = math.log(0.005), math.log(3.0)
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    x1, x2 = right - ratio * (right - left), left + ratio * (right - left)
    f1, f2 = objective(x1), objective(x2)
    for _ in range(80):
        if f1 <= f2:
            right, x2, f2 = x2, x1, f1
            x1 = right - ratio * (right - left)
            f1 = objective(x1)
        else:
            left, x1, f1 = x1, x2, f2
            x2 = left + ratio * (right - left)
            f2 = objective(x2)
    return math.exp((left + right) * 0.5)


def average_nll(rows: list[MatchRow], exponent: float, alpha: float) -> float:
    return mean(-nb_log_pmf(row.actual_aces, candidate_match_mean(row, exponent), alpha) for row in rows)


def choose_exponent(train: list[MatchRow]) -> tuple[float, list[dict[str, float]]]:
    grid: list[dict[str, float]] = []
    for exponent in EXPONENT_GRID:
        alpha = fit_alpha(train, exponent)
        grid.append({"exponent": exponent, "alpha": alpha, "train_nll": average_nll(train, exponent, alpha)})
    best = min(grid, key=lambda item: (item["train_nll"], abs(item["exponent"] - CURRENT_EXPONENT)))
    return best["exponent"], grid


def nb_cdf(cutoff: int, expected: float, alpha: float) -> float:
    if cutoff < 0:
        return 0.0
    return min(1.0, sum(math.exp(nb_log_pmf(k, expected, alpha)) for k in range(cutoff + 1)))


def probability_over(line: float, expected: float, alpha: float) -> float:
    return clip(1.0 - nb_cdf(math.floor(line), expected, alpha), 1e-9, 1.0 - 1e-9)


def binary_log_loss(probabilities: list[float], outcomes: list[int]) -> float:
    return mean(
        -outcome * math.log(probability) - (1 - outcome) * math.log1p(-probability)
        for probability, outcome in zip(probabilities, outcomes, strict=True)
    )


def evaluate(train: list[MatchRow], holdout: list[MatchRow], exponent: float) -> dict[str, float | int | bool]:
    current_alpha = fit_alpha(train, None)
    candidate_alpha = fit_alpha(train, exponent)
    current_errors = [row.current_aces - row.actual_aces for row in holdout]
    candidate_errors = [candidate_match_mean(row, exponent) - row.actual_aces for row in holdout]
    current_probs: list[float] = []
    candidate_probs: list[float] = []
    outcomes: list[int] = []
    for row in holdout:
        line = math.floor(row.naive_aces) + 0.5
        current_probs.append(probability_over(line, row.current_aces, current_alpha))
        candidate_probs.append(probability_over(line, candidate_match_mean(row, exponent), candidate_alpha))
        outcomes.append(int(row.actual_aces > line))
    current_ll = binary_log_loss(current_probs, outcomes)
    candidate_ll = binary_log_loss(candidate_probs, outcomes)
    current_brier = mean((probability - outcome) ** 2 for probability, outcome in zip(current_probs, outcomes, strict=True))
    candidate_brier = mean((probability - outcome) ** 2 for probability, outcome in zip(candidate_probs, outcomes, strict=True))
    current_mae = mean(abs(error) for error in current_errors)
    candidate_mae = mean(abs(error) for error in candidate_errors)
    return {
        "n": len(holdout),
        "current_alpha": current_alpha,
        "candidate_alpha": candidate_alpha,
        "current_mae": current_mae,
        "candidate_mae": candidate_mae,
        "mae_delta": candidate_mae - current_mae,
        "current_logloss": current_ll,
        "candidate_logloss": candidate_ll,
        "logloss_delta": candidate_ll - current_ll,
        "current_brier": current_brier,
        "candidate_brier": candidate_brier,
        "brier_delta": candidate_brier - current_brier,
        "current_bias": mean(current_errors),
        "candidate_bias": mean(candidate_errors),
    }


def write_grid(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["tour", "exponent", "alpha", "train_nll", "selected"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out-gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--out-grid", type=Path, default=DEFAULT_GRID)
    args = parser.parse_args()

    matches = read_matches(args.source)
    generated_at = datetime.now(timezone.utc).isoformat()
    results: dict[str, object] = {}
    grid_rows: list[dict[str, object]] = []
    for tour in ("ATP", "WTA"):
        train = [row for row in matches if row.tour == tour and row.year < HOLDOUT_YEAR]
        holdout = [row for row in matches if row.tour == tour and row.year == HOLDOUT_YEAR]
        if not train or not holdout:
            raise SystemExit(f"Missing train/holdout rows for {tour}")
        exponent, grid = choose_exponent(train)
        current_grid = next(item for item in grid if item["exponent"] == CURRENT_EXPONENT)
        selected_grid = next(item for item in grid if item["exponent"] == exponent)
        train_improvement = current_grid["train_nll"] - selected_grid["train_nll"]
        metrics = evaluate(train, holdout, exponent)
        passed = (
            exponent != CURRENT_EXPONENT
            and train_improvement >= MIN_TRAIN_NLL_IMPROVEMENT
            and float(metrics["mae_delta"]) <= 0.0
            and float(metrics["logloss_delta"]) <= -MIN_HOLDOUT_LOGLOSS_IMPROVEMENT
            and float(metrics["brier_delta"]) <= 0.0
        )
        results[tour] = {
            "train_n": len(train),
            "holdout_n": len(holdout),
            "current_exponent": CURRENT_EXPONENT,
            "selected_exponent": exponent,
            "train_nll_current": current_grid["train_nll"],
            "train_nll_selected": selected_grid["train_nll"],
            "train_nll_improvement": train_improvement,
            **metrics,
            "passed": passed,
        }
        for item in grid:
            grid_rows.append({"tour": tour, **item, "selected": item["exponent"] == exponent})

    passed = all(bool(result["passed"]) for result in results.values())
    gate = {
        "version": "tennis-props-opponent-return-v1",
        "generated_at": generated_at,
        "status": "PASS" if passed else "FAIL",
        "routing": "shadow_eligible" if passed else "blocked",
        "holdout_year": HOLDOUT_YEAR,
        "registered_change": "opponent first-return exponent for ace rate only",
        "fixed_components": ["player rate", "venue factor", "service workload", "negative-binomial family"],
        "selection": "tour-specific exponent selected on pre-2025 NB likelihood",
        "minimum_train_nll_improvement": MIN_TRAIN_NLL_IMPROVEMENT,
        "minimum_holdout_logloss_improvement": MIN_HOLDOUT_LOGLOSS_IMPROVEMENT,
        "tours": results,
        "next_action": "prospective shadow comparison" if passed else "keep exponent 0.6",
    }
    args.out_gate.parent.mkdir(parents=True, exist_ok=True)
    args.out_gate.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    write_grid(args.out_grid, grid_rows)

    lines = [
        "Tennis Props - Opponent Return Ace-Rate Experiment",
        f"Generated UTC: {generated_at}",
        f"Train: years before {HOLDOUT_YEAR}; untouched holdout: {HOLDOUT_YEAR}",
        "Change: opponent first-return exponent only. All other mean and distribution components fixed.",
        "Historical validation disables post-hoc Slam count corrections and uses production-compatible shrunk venue factors.",
        "",
        "Tour Train/Holdout Exp current/selected Train NLL gain Holdout MAE current/candidate Holdout LL current/candidate Delta LL Gate",
    ]
    for tour, result in results.items():
        lines.append(
            f"{tour:3s} {int(result['train_n']):4d}/{int(result['holdout_n']):4d} "
            f"{float(result['current_exponent']):.2f}/{float(result['selected_exponent']):.2f} "
            f"{float(result['train_nll_improvement']):+.6f} "
            f"{float(result['current_mae']):.4f}/{float(result['candidate_mae']):.4f} "
            f"{float(result['current_logloss']):.6f}/{float(result['candidate_logloss']):.6f} "
            f"{float(result['logloss_delta']):+.6f} {'PASS' if result['passed'] else 'FAIL'}"
        )
    lines.extend(
        [
            "",
            f"VERDICT: {gate['status']}",
            f"Routing: {gate['routing']}",
            f"Next: {gate['next_action']}",
            "Outcome-only evidence; no ROI or CLV claim.",
        ]
    )
    args.out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.out_report)
    print(args.out_gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
