#!/usr/bin/env python3
"""Registered L12M player-rate weighting experiment for tennis props.

Only the L12M weight used for the player's ace/DF rate changes. The L24M and
career weights, priors, same-tournament adjustment, venue, opponent return,
service workload and count distribution remain fixed. Selection uses matches
before 2025 and the chosen weight is scored once on the 2025 holdout.
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
DEFAULT_REPORT = BACKTEST_DIR / "aces-dfs-rate-recency-report.txt"
DEFAULT_GATE = BACKTEST_DIR / "aces-dfs-rate-recency-gate.json"
DEFAULT_GRID = BACKTEST_DIR / "aces-dfs-rate-recency-grid.csv"

HOLDOUT_YEAR = 2025
CURRENT_L12M_WEIGHT = 1.0
L12M_WEIGHT_GRID = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
L24M_WEIGHT = 0.55
CAREER_WEIGHT = 0.25
MIN_TRAIN_NLL_IMPROVEMENT = 0.0005
MIN_HOLDOUT_LOGLOSS_IMPROVEMENT = 0.001
MAX_RECONSTRUCTION_ERROR = 0.02
MARKETS = ("aces", "dfs")


@dataclass(frozen=True)
class WindowRate:
    sample: int
    ace_rate: float
    df_rate: float


@dataclass(frozen=True)
class SideInput:
    current_aces: float
    current_dfs: float
    expected_service_points: float
    prior_ace_rate: float
    prior_df_rate: float
    ace_environment_factor: float
    df_environment_factor: float
    opponent_return_factor: float
    same_tournament_ace_rate: float
    same_tournament_df_rate: float
    same_tournament_ace_weight: float
    same_tournament_df_weight: float
    l12m: WindowRate
    l24m: WindowRate
    career_4y: WindowRate


@dataclass(frozen=True)
class MatchRow:
    tour: str
    year: int
    date: str
    tournament: str
    actual_aces: int
    actual_dfs: int
    current_aces: float
    current_dfs: float
    naive_aces: float
    naive_dfs: float
    sides: tuple[SideInput, SideInput]


def parse_float(value: object) -> float | None:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def parse_int(value: object) -> int:
    parsed = parse_float(value)
    return int(parsed) if parsed is not None else 0


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def norm_name(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch)).lower()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in raw).split())


def prior_weight(tour: str, market: str) -> float:
    if market == "aces":
        return 400.0 if tour == "ATP" else 600.0
    return 600.0 if tour == "ATP" else 800.0


def player_rate(side: SideInput, tour: str, market: str, l12m_weight: float) -> float:
    prior = side.prior_ace_rate if market == "aces" else side.prior_df_rate
    numerator = prior * prior_weight(tour, market)
    denominator = prior_weight(tour, market)
    for window, weight in (
        (side.l12m, l12m_weight),
        (side.l24m, L24M_WEIGHT),
        (side.career_4y, CAREER_WEIGHT),
    ):
        rate = window.ace_rate if market == "aces" else window.df_rate
        if window.sample <= 0:
            continue
        numerator += rate * window.sample * weight
        denominator += window.sample * weight
    return numerator / denominator if denominator > 0 else prior


def candidate_side_mean(side: SideInput, tour: str, market: str, l12m_weight: float) -> float:
    rate = player_rate(side, tour, market, l12m_weight)
    if market == "aces":
        rate = (
            (1.0 - side.same_tournament_ace_weight) * rate
            + side.same_tournament_ace_weight * side.same_tournament_ace_rate
        )
        adjusted = clip(
            rate * side.ace_environment_factor * side.opponent_return_factor,
            0.002,
            0.28,
        )
    else:
        rate = (
            (1.0 - side.same_tournament_df_weight) * rate
            + side.same_tournament_df_weight * side.same_tournament_df_rate
        )
        adjusted = clip(rate * side.df_environment_factor, 0.002, 0.16)
    return adjusted * side.expected_service_points


def candidate_match_mean(row: MatchRow, market: str, l12m_weight: float) -> float:
    return sum(candidate_side_mean(side, row.tour, market, l12m_weight) for side in row.sides)


def current_mean(row: MatchRow, market: str) -> float:
    return row.current_aces if market == "aces" else row.current_dfs


def actual_count(row: MatchRow, market: str) -> int:
    return row.actual_aces if market == "aces" else row.actual_dfs


def naive_mean(row: MatchRow, market: str) -> float:
    return row.naive_aces if market == "aces" else row.naive_dfs


def side_from_row(row: dict[str, str]) -> SideInput:
    def required(name: str) -> float:
        value = parse_float(row.get(name))
        if value is None:
            raise ValueError(f"missing {name}")
        return value

    def window(prefix: str) -> WindowRate:
        return WindowRate(
            sample=parse_int(row.get(f"{prefix}_svpt")),
            ace_rate=required(f"{prefix}_ace_rate"),
            df_rate=required(f"{prefix}_df_rate"),
        )

    return SideInput(
        current_aces=required("projected_aces"),
        current_dfs=required("projected_dfs"),
        expected_service_points=required("expected_service_points"),
        prior_ace_rate=required("prior_ace_rate"),
        prior_df_rate=required("prior_df_rate"),
        ace_environment_factor=required("ace_environment_factor"),
        df_environment_factor=required("df_environment_factor"),
        opponent_return_factor=required("opponent_return_factor"),
        same_tournament_ace_rate=required("same_tournament_ace_rate"),
        same_tournament_df_rate=required("same_tournament_df_rate"),
        same_tournament_ace_weight=required("same_tournament_ace_weight"),
        same_tournament_df_weight=required("same_tournament_df_weight"),
        l12m=window("l12m"),
        l24m=window("l24m"),
        career_4y=window("career_4y"),
    )


def read_matches(path: Path) -> list[MatchRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    required = {
        "prior_ace_rate", "prior_df_rate", "ace_environment_factor", "df_environment_factor",
        "same_tournament_ace_rate", "same_tournament_df_rate",
        "same_tournament_ace_weight", "same_tournament_df_weight",
        "l12m_svpt", "l12m_ace_rate", "l12m_df_rate",
        "l24m_svpt", "l24m_ace_rate", "l24m_df_rate",
        "career_4y_svpt", "career_4y_ace_rate", "career_4y_df_rate",
    }
    if not source_rows:
        return []
    missing = sorted(required - set(source_rows[0]))
    if missing:
        raise SystemExit(f"Source is missing rate-recency columns: {', '.join(missing)}")

    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        player = norm_name(row.get("player"))
        opponent = norm_name(row.get("opponent"))
        if not player or not opponent:
            continue
        pair = tuple(sorted((player, opponent)))
        key = (
            str(row.get("tour") or "").upper(), str(row.get("year") or ""),
            str(row.get("date") or ""), str(row.get("tournament") or ""),
            str(row.get("round") or ""), pair[0], pair[1],
        )
        grouped[key].append(row)

    matches: list[MatchRow] = []
    for key, rows in grouped.items():
        if len(rows) != 2 or len({norm_name(row.get("player")) for row in rows}) != 2:
            continue
        try:
            sides = (side_from_row(rows[0]), side_from_row(rows[1]))
            numeric = {
                field: [parse_float(row.get(field)) for row in rows]
                for field in ("actual_aces", "actual_dfs", "naive_aces", "naive_dfs")
            }
            if any(any(value is None for value in values) for values in numeric.values()):
                continue
            matches.append(
                MatchRow(
                    tour=key[0], year=int(key[1]), date=key[2], tournament=key[3],
                    actual_aces=int(round(sum(float(value) for value in numeric["actual_aces"]))),
                    actual_dfs=int(round(sum(float(value) for value in numeric["actual_dfs"]))),
                    current_aces=sum(side.current_aces for side in sides),
                    current_dfs=sum(side.current_dfs for side in sides),
                    naive_aces=sum(float(value) for value in numeric["naive_aces"]),
                    naive_dfs=sum(float(value) for value in numeric["naive_dfs"]),
                    sides=sides,
                )
            )
        except ValueError:
            continue
    return sorted(matches, key=lambda row: (row.date, row.tour, row.tournament))


def nb_log_pmf(actual: int, expected: float, alpha: float) -> float:
    size = 1.0 / alpha
    probability = size / (size + max(0.01, expected))
    return (
        math.lgamma(actual + size) - math.lgamma(size) - math.lgamma(actual + 1)
        + size * math.log(probability) + actual * math.log1p(-probability)
    )


def fit_alpha(rows: list[MatchRow], market: str, weight: float | None) -> float:
    def expected(row: MatchRow) -> float:
        return current_mean(row, market) if weight is None else candidate_match_mean(row, market, weight)

    def objective(log_alpha: float) -> float:
        alpha = math.exp(log_alpha)
        return -sum(nb_log_pmf(actual_count(row, market), expected(row), alpha) for row in rows)

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


def average_nll(rows: list[MatchRow], market: str, weight: float, alpha: float) -> float:
    return mean(
        -nb_log_pmf(actual_count(row, market), candidate_match_mean(row, market, weight), alpha)
        for row in rows
    )


def choose_weight(train: list[MatchRow], market: str) -> tuple[float, list[dict[str, float]]]:
    grid: list[dict[str, float]] = []
    for weight in L12M_WEIGHT_GRID:
        alpha = fit_alpha(train, market, weight)
        grid.append({"l12m_weight": weight, "alpha": alpha, "train_nll": average_nll(train, market, weight, alpha)})
    best = min(grid, key=lambda item: (item["train_nll"], abs(item["l12m_weight"] - CURRENT_L12M_WEIGHT)))
    return best["l12m_weight"], grid


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


def evaluate(train: list[MatchRow], holdout: list[MatchRow], market: str, weight: float) -> dict[str, float | int]:
    current_alpha = fit_alpha(train, market, None)
    candidate_alpha = fit_alpha(train, market, weight)
    current_errors = [current_mean(row, market) - actual_count(row, market) for row in holdout]
    candidate_errors = [candidate_match_mean(row, market, weight) - actual_count(row, market) for row in holdout]
    current_probs: list[float] = []
    candidate_probs: list[float] = []
    outcomes: list[int] = []
    for row in holdout:
        line = math.floor(naive_mean(row, market)) + 0.5
        current_probs.append(probability_over(line, current_mean(row, market), current_alpha))
        candidate_probs.append(probability_over(line, candidate_match_mean(row, market, weight), candidate_alpha))
        outcomes.append(int(actual_count(row, market) > line))
    current_ll = binary_log_loss(current_probs, outcomes)
    candidate_ll = binary_log_loss(candidate_probs, outcomes)
    current_brier = mean((prob - out) ** 2 for prob, out in zip(current_probs, outcomes, strict=True))
    candidate_brier = mean((prob - out) ** 2 for prob, out in zip(candidate_probs, outcomes, strict=True))
    current_mae = mean(abs(error) for error in current_errors)
    candidate_mae = mean(abs(error) for error in candidate_errors)
    return {
        "n": len(holdout), "current_alpha": current_alpha, "candidate_alpha": candidate_alpha,
        "current_mae": current_mae, "candidate_mae": candidate_mae,
        "mae_delta": candidate_mae - current_mae,
        "current_logloss": current_ll, "candidate_logloss": candidate_ll,
        "logloss_delta": candidate_ll - current_ll,
        "current_brier": current_brier, "candidate_brier": candidate_brier,
        "brier_delta": candidate_brier - current_brier,
        "current_bias": mean(current_errors), "candidate_bias": mean(candidate_errors),
    }


def reconstruction_error(rows: list[MatchRow], market: str) -> float:
    return max(
        abs(candidate_match_mean(row, market, CURRENT_L12M_WEIGHT) - current_mean(row, market))
        for row in rows
    )


def write_grid(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["tour", "market", "l12m_weight", "alpha", "train_nll", "selected"])
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
    if not matches:
        raise SystemExit("No rate-recency source rows loaded")
    generated_at = datetime.now(timezone.utc).isoformat()
    results: dict[str, object] = {}
    grid_rows: list[dict[str, object]] = []
    for tour in ("ATP", "WTA"):
        tour_results: dict[str, object] = {}
        train = [row for row in matches if row.tour == tour and row.year < HOLDOUT_YEAR]
        holdout = [row for row in matches if row.tour == tour and row.year == HOLDOUT_YEAR]
        if not train or not holdout:
            raise SystemExit(f"Missing train/holdout rows for {tour}")
        for market in MARKETS:
            error = reconstruction_error(train + holdout, market)
            if error > MAX_RECONSTRUCTION_ERROR:
                raise SystemExit(f"{tour} {market} reconstruction error {error:.6f} exceeds {MAX_RECONSTRUCTION_ERROR}")
            weight, grid = choose_weight(train, market)
            current_grid = next(item for item in grid if item["l12m_weight"] == CURRENT_L12M_WEIGHT)
            selected_grid = next(item for item in grid if item["l12m_weight"] == weight)
            train_improvement = current_grid["train_nll"] - selected_grid["train_nll"]
            metrics = evaluate(train, holdout, market, weight)
            passed = (
                weight != CURRENT_L12M_WEIGHT
                and train_improvement >= MIN_TRAIN_NLL_IMPROVEMENT
                and float(metrics["mae_delta"]) <= 0.0
                and float(metrics["logloss_delta"]) <= -MIN_HOLDOUT_LOGLOSS_IMPROVEMENT
                and float(metrics["brier_delta"]) <= 0.0
            )
            tour_results[market] = {
                "train_n": len(train), "holdout_n": len(holdout),
                "current_l12m_weight": CURRENT_L12M_WEIGHT, "selected_l12m_weight": weight,
                "train_nll_current": current_grid["train_nll"],
                "train_nll_selected": selected_grid["train_nll"],
                "train_nll_improvement": train_improvement,
                "max_reconstruction_error": error, **metrics, "passed": passed,
            }
            for item in grid:
                grid_rows.append({"tour": tour, "market": market, **item, "selected": item["l12m_weight"] == weight})
        results[tour] = tour_results

    cells = [cell for tour in results.values() for cell in tour.values()]
    passed = all(bool(cell["passed"]) for cell in cells)
    gate = {
        "version": "tennis-props-rate-recency-v1",
        "generated_at": generated_at,
        "status": "PASS" if passed else "FAIL",
        "routing": "shadow_eligible" if passed else "blocked",
        "holdout_year": HOLDOUT_YEAR,
        "registered_change": "L12M player ace/DF rate weight only",
        "fixed_weights": {"L24M": L24M_WEIGHT, "career_4y": CAREER_WEIGHT},
        "grid": list(L12M_WEIGHT_GRID),
        "minimum_train_nll_improvement": MIN_TRAIN_NLL_IMPROVEMENT,
        "minimum_holdout_logloss_improvement": MIN_HOLDOUT_LOGLOSS_IMPROVEMENT,
        "selection": "tour-and-market-specific L12M weight selected on pre-2025 NB likelihood",
        "tours": results,
        "next_action": "prospective shadow comparison" if passed else "keep L12M weight 1.0",
    }
    args.out_gate.parent.mkdir(parents=True, exist_ok=True)
    args.out_gate.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    write_grid(args.out_grid, grid_rows)

    lines = [
        "Tennis Props - Player Rate Recency Experiment",
        f"Generated UTC: {generated_at}",
        f"Train: years before {HOLDOUT_YEAR}; untouched holdout: {HOLDOUT_YEAR}",
        "Change: L12M player ace/DF rate weight only; L24M=0.55 and career_4y=0.25 stay fixed.",
        "Opponent, venue, same-tournament, workload and negative-binomial family stay fixed.",
        "",
        "Tour Market Train/Holdout L12 current/selected Train NLL gain MAE current/candidate LL current/candidate Delta LL Gate",
    ]
    for tour, tour_results in results.items():
        for market, result in tour_results.items():
            lines.append(
                f"{tour:3s} {market:4s} {int(result['train_n']):4d}/{int(result['holdout_n']):4d} "
                f"{float(result['current_l12m_weight']):.2f}/{float(result['selected_l12m_weight']):.2f} "
                f"{float(result['train_nll_improvement']):+.6f} "
                f"{float(result['current_mae']):.4f}/{float(result['candidate_mae']):.4f} "
                f"{float(result['current_logloss']):.6f}/{float(result['candidate_logloss']):.6f} "
                f"{float(result['logloss_delta']):+.6f} {'PASS' if result['passed'] else 'FAIL'}"
            )
    lines.extend([
        "", f"VERDICT: {gate['status']}", f"Routing: {gate['routing']}",
        f"Next: {gate['next_action']}", "Outcome-only evidence; no ROI or CLV claim.",
    ])
    args.out_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.out_report)
    print(args.out_gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
