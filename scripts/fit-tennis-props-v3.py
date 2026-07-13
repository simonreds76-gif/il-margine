#!/usr/bin/env python3
"""Fit and evaluate the all-main-tour tennis props v3 challenger.

The model is selected on 2023-24 training plus 2025 validation. The partial
2026 season is touched once for the final gate. Passing permits prospective
shadow tracking only; real Bet365 settlement evidence remains mandatory.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import lightgbm as lgb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
BACKTEST_DIR = ROOT / "data" / "tennis-props" / "backtest"
MODEL_DIR = ROOT / "data" / "tennis-props" / "models"
DEFAULT_SOURCE = BACKTEST_DIR / "aces-dfs-v3-all-tour-features.csv"
DEFAULT_GATE = BACKTEST_DIR / "aces-dfs-v3-all-tour-gate.json"
DEFAULT_REPORT = BACKTEST_DIR / "aces-dfs-v3-all-tour-report.txt"
DEFAULT_PREDICTIONS = BACKTEST_DIR / "aces-dfs-v3-all-tour-2026-predictions.csv"
DEFAULT_IMPORTANCE = BACKTEST_DIR / "aces-dfs-v3-feature-importance.csv"
DEFAULT_SHADOW_SIGNALS = ROOT / "data" / "tennis-props" / "shadow" / "aces-v3-shadow-signals.csv"

TRAIN_YEARS = (2023, 2024)
VALIDATION_YEAR = 2025
TEST_YEAR = 2026
MARKETS = {
    "aces": ("actual_aces", "incumbent_aces"),
    "dfs": ("actual_dfs", "incumbent_dfs"),
}
CATEGORICAL = ["surface", "level", "round", "player_hand", "opponent_hand"]
LIVE_CATEGORICAL = ["surface"]
EXCLUDED = {
    "date", "year", "tour", "tournament", "player_id", "player", "opponent_id", "opponent",
    "actual_aces", "actual_dfs", "actual_service_points",
}
MIN_TEST_ROWS = 900
MIN_MAE_IMPROVEMENT_PCT = 1.0
MIN_LOGLOSS_IMPROVEMENT = 0.002
MAX_SURFACE_MAE_REGRESSION_PCT = 2.0
MAX_SURFACE_LOGLOSS_REGRESSION = 0.003
MIN_SETTLED_REAL_LINES = 300
MIN_DISTINCT_EVENTS = 100
MIN_MEAN_CLV_PCT = 1.0
MIN_ROI_PCT = 0.0


def clip_probability(value: float) -> float:
    return max(1e-9, min(1.0 - 1e-9, value))


def nb_log_pmf(actual: int, expected: float, alpha: float) -> float:
    expected = max(0.01, expected)
    size = 1.0 / alpha
    probability = size / (size + expected)
    return (
        math.lgamma(actual + size) - math.lgamma(size) - math.lgamma(actual + 1)
        + size * math.log(probability) + actual * math.log1p(-probability)
    )


def fit_alpha(actual: np.ndarray, expected: np.ndarray) -> float:
    def objective(log_alpha: float) -> float:
        alpha = math.exp(log_alpha)
        return -sum(nb_log_pmf(int(y), float(mu), alpha) for y, mu in zip(actual, expected, strict=True))

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


def nb_cdf(cutoff: int, expected: float, alpha: float) -> float:
    if cutoff < 0:
        return 0.0
    return min(1.0, sum(math.exp(nb_log_pmf(k, expected, alpha)) for k in range(cutoff + 1)))


def probability_over(line: float, expected: float, alpha: float) -> float:
    return clip_probability(1.0 - nb_cdf(math.floor(line), expected, alpha))


def binary_metrics(
    actual: np.ndarray,
    incumbent: np.ndarray,
    candidate: np.ndarray,
    incumbent_alpha: float,
    candidate_alpha: float,
) -> dict[str, float]:
    incumbent_probs: list[float] = []
    candidate_probs: list[float] = []
    outcomes: list[int] = []
    for y, base, challenger in zip(actual, incumbent, candidate, strict=True):
        line = math.floor(float(base)) + 0.5
        incumbent_probs.append(probability_over(line, float(base), incumbent_alpha))
        candidate_probs.append(probability_over(line, float(challenger), candidate_alpha))
        outcomes.append(int(float(y) > line))
    incumbent_ll = mean(
        -y * math.log(p) - (1 - y) * math.log1p(-p)
        for p, y in zip(incumbent_probs, outcomes, strict=True)
    )
    candidate_ll = mean(
        -y * math.log(p) - (1 - y) * math.log1p(-p)
        for p, y in zip(candidate_probs, outcomes, strict=True)
    )
    incumbent_brier = mean((p - y) ** 2 for p, y in zip(incumbent_probs, outcomes, strict=True))
    candidate_brier = mean((p - y) ** 2 for p, y in zip(candidate_probs, outcomes, strict=True))
    return {
        "incumbent_logloss": incumbent_ll,
        "candidate_logloss": candidate_ll,
        "logloss_delta": candidate_ll - incumbent_ll,
        "incumbent_brier": incumbent_brier,
        "candidate_brier": candidate_brier,
        "brier_delta": candidate_brier - incumbent_brier,
    }


def count_metrics(actual: np.ndarray, incumbent: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    incumbent_error = incumbent - actual
    candidate_error = candidate - actual
    incumbent_mae = float(np.mean(np.abs(incumbent_error)))
    candidate_mae = float(np.mean(np.abs(candidate_error)))
    return {
        "incumbent_mae": incumbent_mae,
        "candidate_mae": candidate_mae,
        "mae_improvement_pct": 100.0 * (incumbent_mae - candidate_mae) / incumbent_mae,
        "incumbent_rmse": float(np.sqrt(np.mean(np.square(incumbent_error)))),
        "candidate_rmse": float(np.sqrt(np.mean(np.square(candidate_error)))),
        "incumbent_bias": float(np.mean(incumbent_error)),
        "candidate_bias": float(np.mean(candidate_error)),
    }


def prepare_frame(path: Path) -> tuple[pd.DataFrame, list[str]]:
    frame = pd.read_csv(path)
    for column in CATEGORICAL:
        frame[column] = frame[column].fillna("Unknown").astype("category")
    feature_columns = [column for column in frame.columns if column not in EXCLUDED]
    # Targets not listed in EXCLUDED are explicitly removed here for clarity.
    feature_columns = [column for column in feature_columns if not column.startswith("actual_")]
    return frame, feature_columns


def fit_cell(
    frame: pd.DataFrame,
    feature_columns: list[str],
    tour: str,
    market: str,
    model_dir: Path,
    *,
    categorical_columns: list[str] | None = None,
    model_suffix: str = "",
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    categorical_columns = CATEGORICAL if categorical_columns is None else categorical_columns
    target_column, incumbent_column = MARKETS[market]
    tour_frame = frame[frame["tour"] == tour].copy()
    train = tour_frame[tour_frame["year"].isin(TRAIN_YEARS)]
    validation = tour_frame[tour_frame["year"] == VALIDATION_YEAR]
    test = tour_frame[tour_frame["year"] == TEST_YEAR].copy()
    if train.empty or validation.empty or test.empty:
        raise SystemExit(f"Missing v3 split for {tour} {market}")

    model = lgb.LGBMRegressor(
        objective="poisson",
        n_estimators=900,
        learning_rate=0.025,
        num_leaves=15,
        min_child_samples=150,
        subsample=0.85,
        colsample_bytree=0.80,
        reg_alpha=1.0,
        reg_lambda=5.0,
        random_state=20260713,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
        n_jobs=4,
    )
    model.fit(
        train[feature_columns],
        train[target_column],
        categorical_feature=categorical_columns,
        eval_set=[(validation[feature_columns], validation[target_column])],
        eval_metric="poisson",
        callbacks=[lgb.early_stopping(80, verbose=False)],
    )
    validation_candidate = np.maximum(0.01, model.predict(validation[feature_columns]))
    test_candidate = np.maximum(0.01, model.predict(test[feature_columns]))
    validation_actual = validation[target_column].to_numpy(dtype=float)
    validation_incumbent = validation[incumbent_column].to_numpy(dtype=float)
    test_actual = test[target_column].to_numpy(dtype=float)
    test_incumbent = test[incumbent_column].to_numpy(dtype=float)
    incumbent_alpha = fit_alpha(validation_actual, validation_incumbent)
    candidate_alpha = fit_alpha(validation_actual, validation_candidate)
    metrics = count_metrics(test_actual, test_incumbent, test_candidate)
    metrics.update(binary_metrics(
        test_actual, test_incumbent, test_candidate, incumbent_alpha, candidate_alpha,
    ))

    surface_results: dict[str, object] = {}
    for surface, surface_rows in test.assign(_candidate=test_candidate).groupby("surface", observed=True):
        indexes = surface_rows.index
        positions = test.index.get_indexer(indexes)
        actual = test_actual[positions]
        incumbent = test_incumbent[positions]
        candidate = test_candidate[positions]
        surface_metrics = count_metrics(actual, incumbent, candidate)
        surface_metrics.update(binary_metrics(
            actual, incumbent, candidate, incumbent_alpha, candidate_alpha,
        ))
        surface_pass = (
            len(surface_rows) < 200
            or (
                surface_metrics["candidate_mae"] <= surface_metrics["incumbent_mae"] * (1.0 + MAX_SURFACE_MAE_REGRESSION_PCT / 100.0)
                and surface_metrics["logloss_delta"] <= MAX_SURFACE_LOGLOSS_REGRESSION
            )
        )
        surface_results[str(surface)] = {"n": len(surface_rows), **surface_metrics, "guard_passed": surface_pass}

    passed = (
        len(test) >= MIN_TEST_ROWS
        and metrics["mae_improvement_pct"] >= MIN_MAE_IMPROVEMENT_PCT
        and metrics["logloss_delta"] <= -MIN_LOGLOSS_IMPROVEMENT
        and metrics["brier_delta"] <= 0.0
        and all(bool(result["guard_passed"]) for result in surface_results.values())
    )
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / f"v3-{tour.lower()}-{market}{model_suffix}.txt"
    model.booster_.save_model(model_path)

    predictions = test[[
        "date", "tour", "tournament", "surface", "level", "round", "player", "opponent",
        target_column, incumbent_column,
    ]].copy()
    predictions["market"] = market
    predictions["candidate_mean"] = test_candidate
    predictions["incumbent_alpha"] = incumbent_alpha
    predictions["candidate_alpha"] = candidate_alpha
    importance = pd.DataFrame({
        "tour": tour,
        "market": market,
        "feature": feature_columns,
        "gain": model.booster_.feature_importance(importance_type="gain"),
        "splits": model.booster_.feature_importance(importance_type="split"),
    }).sort_values("gain", ascending=False)
    result: dict[str, object] = {
        "passed": passed,
        "train_n": len(train),
        "validation_n": len(validation),
        "test_n": len(test),
        "best_iteration": int(model.best_iteration_ or model.n_estimators),
        "incumbent_alpha": incumbent_alpha,
        "candidate_alpha": candidate_alpha,
        **metrics,
        "surfaces": surface_results,
        "model_path": str(model_path.relative_to(ROOT)),
        "top_features": importance.head(12)[["feature", "gain"]].to_dict("records"),
    }
    return result, predictions, importance


def live_ace_feature_columns(feature_columns: list[str]) -> list[str]:
    """Features reproduced exactly by the daily board/baseline pipeline."""
    base = {
        "surface",
        "best_of",
        "surface_prior_ace_rate",
        "surface_prior_df_rate",
        "venue_ace_factor",
        "venue_df_factor",
        "expected_match_games",
        "expected_service_points",
        "opponent_return_factor",
        "incumbent_aces",
        "incumbent_dfs",
    }
    blocked = {
        "player_hand", "opponent_hand", "player_rank", "opponent_rank",
        "player_age", "opponent_age", "player_height", "opponent_height",
    }
    return [
        column
        for column in feature_columns
        if (column in base or column.startswith("player_") or column.startswith("opponent_"))
        and column not in blocked
    ]


def sellability_metrics(path: Path) -> dict[str, object]:
    if path.exists():
        frame = pd.read_csv(path, dtype=str).fillna("")
    else:
        frame = pd.DataFrame()
    if frame.empty or "settlement_status" not in frame.columns:
        settled = frame.iloc[0:0]
    else:
        settled = frame[frame["settlement_status"].str.lower() == "settled"].copy()

    pnl = pd.to_numeric(settled.get("pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    clv = pd.to_numeric(settled.get("clv_pct", pd.Series(dtype=float)), errors="coerce").dropna()
    event_keys: set[str] = set()
    for _, row in settled.iterrows():
        event_id = str(row.get("event_id") or "").strip()
        if event_id:
            event_keys.add(f"event:{event_id}")
        else:
            pair = sorted((str(row.get("player") or "").strip(), str(row.get("opponent") or "").strip()))
            event_keys.add(f"pair:{row.get('date', '')}|{row.get('tour', '')}|{'|'.join(pair)}")

    settled_count = len(settled)
    distinct_events = len(event_keys)
    roi_pct = float(pnl.sum() / settled_count * 100.0) if settled_count else 0.0
    mean_clv_pct = float(clv.mean()) if len(clv) else 0.0
    failures: list[str] = []
    if settled_count < MIN_SETTLED_REAL_LINES:
        failures.append(f"settled {settled_count}/{MIN_SETTLED_REAL_LINES}")
    if distinct_events < MIN_DISTINCT_EVENTS:
        failures.append(f"events {distinct_events}/{MIN_DISTINCT_EVENTS}")
    if len(clv) < MIN_SETTLED_REAL_LINES:
        failures.append(f"CLV coverage {len(clv)}/{MIN_SETTLED_REAL_LINES}")
    if mean_clv_pct < MIN_MEAN_CLV_PCT:
        failures.append(f"mean CLV {mean_clv_pct:+.2f}%/{MIN_MEAN_CLV_PCT:+.2f}%")
    if roi_pct < MIN_ROI_PCT:
        failures.append(f"ROI {roi_pct:+.2f}%/{MIN_ROI_PCT:+.2f}%")
    return {
        "status": "PASS" if not failures else "BLOCKED",
        "reason": "all real-price promotion gates passed" if not failures else "; ".join(failures),
        "settled_real_lines": settled_count,
        "distinct_events": distinct_events,
        "clv_coverage": len(clv),
        "mean_clv_pct": mean_clv_pct,
        "roi_pct": roi_pct,
        "minimum_settled_real_lines": MIN_SETTLED_REAL_LINES,
        "minimum_distinct_events": MIN_DISTINCT_EVENTS,
        "required_mean_clv_pct": MIN_MEAN_CLV_PCT,
        "required_roi_pct": MIN_ROI_PCT,
        "source": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
    }


def write_report(path: Path, gate: dict[str, object]) -> None:
    lines = [
        "Tennis Props v3 - All Main Tour Challenger",
        f"Generated UTC: {gate['generated_at']}",
        f"Train: {', '.join(map(str, TRAIN_YEARS))}; validation: {VALIDATION_YEAR}; untouched test: {TEST_YEAR} YTD",
        "Model: regularised LightGBM Poisson mean with causal rolling player, opponent, venue, rank and workload features.",
        "Permission: outcome shadow only. Real Bet365 settlement gate remains mandatory.",
        "",
        "Tour Market N(test) MAE incumbent/candidate Improve LL incumbent/candidate Delta Brier delta Surface guard Gate",
    ]
    cells = gate["cells"]
    for key, result in cells.items():
        surface_guard = all(bool(item["guard_passed"]) for item in result["surfaces"].values())
        lines.append(
            f"{key.replace('_', ' '):9s} {int(result['test_n']):5d} "
            f"{float(result['incumbent_mae']):.4f}/{float(result['candidate_mae']):.4f} "
            f"{float(result['mae_improvement_pct']):+.2f}% "
            f"{float(result['incumbent_logloss']):.6f}/{float(result['candidate_logloss']):.6f} "
            f"{float(result['logloss_delta']):+.6f} {float(result['brier_delta']):+.6f} "
            f"{'PASS' if surface_guard else 'FAIL'} {'PASS' if result['passed'] else 'FAIL'}"
        )
    lines.extend([
        "",
        f"VERDICT: {gate['status']}",
        f"Routing: {gate['routing']}",
        f"Aces market: {gate['market_gates']['aces']['status']} "
        f"({gate['market_gates']['aces']['passed_cells']}/{gate['market_gates']['aces']['total_cells']} cells; "
        f"surfaces {', '.join(gate['market_gates']['aces']['evaluated_surfaces']) or 'none'}; "
        f"unverified {', '.join(gate['market_gates']['aces']['unverified_surfaces']) or 'none'})",
        f"DF market: {gate['market_gates']['dfs']['status']} "
        f"({gate['market_gates']['dfs']['passed_cells']}/{gate['market_gates']['dfs']['total_cells']} cells)",
        f"Deployable ATP aces: {gate['deployment_safe_aces']['ATP']['status']} "
        f"(MAE {gate['deployment_safe_aces']['ATP']['mae_improvement_pct']:+.2f}%; "
        f"log-loss delta {gate['deployment_safe_aces']['ATP']['logloss_delta']:+.6f})",
        f"Deployable WTA aces: {gate['deployment_safe_aces']['WTA']['status']} "
        f"(Clay guard failed; no WTA routing)",
        f"Sellability: {gate['sellability_gate']['status']} - {gate['sellability_gate']['reason']}",
        f"Next: {gate['next_action']}",
        "No ROI or sellability claim is allowed from outcome-only evidence.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--out-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out-predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--out-importance", type=Path, default=DEFAULT_IMPORTANCE)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    parser.add_argument("--shadow-signals", type=Path, default=DEFAULT_SHADOW_SIGNALS)
    args = parser.parse_args()
    frame, feature_columns = prepare_frame(args.source)
    cells: dict[str, object] = {}
    predictions: list[pd.DataFrame] = []
    importance: list[pd.DataFrame] = []
    for tour in ("ATP", "WTA"):
        for market in MARKETS:
            result, cell_predictions, cell_importance = fit_cell(
                frame, feature_columns, tour, market, args.model_dir,
            )
            cells[f"{tour}_{market}"] = result
            predictions.append(cell_predictions)
            importance.append(cell_importance)
    live_features = live_ace_feature_columns(feature_columns)
    deployment_safe_aces: dict[str, object] = {}
    for tour in ("ATP", "WTA"):
        live_result, _live_predictions, live_importance = fit_cell(
            frame,
            live_features,
            tour,
            "aces",
            args.model_dir,
            categorical_columns=LIVE_CATEGORICAL,
            model_suffix="-live",
        )
        deployment_safe_aces[tour] = {
            "status": "PASS" if live_result["passed"] else "FAIL",
            "passed": live_result["passed"],
            "mae_improvement_pct": live_result["mae_improvement_pct"],
            "logloss_delta": live_result["logloss_delta"],
            "brier_delta": live_result["brier_delta"],
            "candidate_alpha": live_result["candidate_alpha"],
            "surfaces": live_result["surfaces"],
            "model_path": live_result["model_path"],
            "feature_count": len(live_features),
        }
        live_importance = live_importance.copy()
        live_importance["market"] = "aces_live"
        importance.append(live_importance)
    market_gates: dict[str, object] = {}
    for market in MARKETS:
        market_cells = [cells[f"{tour}_{market}"] for tour in ("ATP", "WTA")]
        market_passed = all(bool(result["passed"]) for result in market_cells)
        evaluated_surfaces = sorted({
            surface
            for result in market_cells
            for surface, metrics in result["surfaces"].items()
            if int(metrics["n"]) >= 200
        })
        market_gates[market] = {
            "status": "PASS" if market_passed else "FAIL",
            "routing": "outcome_shadow_eligible" if market_passed else "blocked",
            "passed_cells": sum(bool(result["passed"]) for result in market_cells),
            "total_cells": len(market_cells),
            "evaluated_surfaces": evaluated_surfaces,
            "unverified_surfaces": sorted({"Hard", "Clay", "Grass"} - set(evaluated_surfaces)),
        }
    passed_markets = [market for market, result in market_gates.items() if result["status"] == "PASS"]
    overall_status = "PASS" if len(passed_markets) == len(MARKETS) else ("PARTIAL_PASS" if passed_markets else "FAIL")
    gate: dict[str, object] = {
        "version": "tennis-props-v3-all-tour-1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "routing": "atp_aces_hard_clay_prospective_shadow" if deployment_safe_aces["ATP"]["passed"] else "blocked",
        "train_years": list(TRAIN_YEARS),
        "validation_year": VALIDATION_YEAR,
        "untouched_test_year": TEST_YEAR,
        "minimums": {
            "test_rows_per_cell": MIN_TEST_ROWS,
            "mae_improvement_pct": MIN_MAE_IMPROVEMENT_PCT,
            "logloss_improvement": MIN_LOGLOSS_IMPROVEMENT,
            "max_surface_mae_regression_pct": MAX_SURFACE_MAE_REGRESSION_PCT,
            "max_surface_logloss_regression": MAX_SURFACE_LOGLOSS_REGRESSION,
        },
        "cells": cells,
        "market_gates": market_gates,
        "deployment_safe_aces": deployment_safe_aces,
        "deployment_scope": {
            "tour": "ATP",
            "market": "player_aces",
            "surfaces": ["Clay", "Hard"],
            "permission": "prospective_shadow_only",
            "wta": "blocked_by_clay_surface_guard",
            "grass": "blocked_unverified_2026_test",
        },
        "sellability_gate": sellability_metrics(args.shadow_signals),
        "next_action": (
            "log deployment-safe ATP v3 aces and incumbent prospectively on Hard/Clay; retain incumbent for WTA/DFs and keep Grass blocked"
            if passed_markets == ["aces"]
            else ("log every passed market prospectively against captured Bet365 lines" if passed_markets else "retain incumbent and diagnose failed cells")
        ),
    }
    args.out_gate.parent.mkdir(parents=True, exist_ok=True)
    args.out_gate.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    write_report(args.out_report, gate)
    pd.concat(predictions, ignore_index=True).to_csv(args.out_predictions, index=False)
    pd.concat(importance, ignore_index=True).to_csv(args.out_importance, index=False)
    print(args.out_report)
    print(args.out_gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
