#!/usr/bin/env python3
"""Run registered A2 rank-band calibration on the isolated A1 ace arm."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEFAULT_DIR = (
    ROOT / "data" / "tennis-props" / "experiments" / "most-aces-coverage-a1"
)
DEFAULT_SOURCE = DEFAULT_DIR / "aces-dfs-v3-features.csv"
THIN_SVPT_MAX = 600
CALIBRATION_PRIOR_SIDES = 100
RANK_BANDS = (
    ("TOP_50", 0, 50),
    ("RANK_51_100", 51, 100),
    ("RANK_101_200", 101, 200),
    ("RANK_201_500", 201, 500),
    ("RANK_501_PLUS", 501, 100000),
)


def load_fit_module():
    path = SCRIPTS / "fit-tennis-props-v3.py"
    spec = importlib.util.spec_from_file_location("fit_tennis_props_v3_a2", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def model() -> lgb.LGBMRegressor:
    return lgb.LGBMRegressor(
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


def fit(
    frame: pd.DataFrame,
    features: list[str],
    train_years: tuple[int, ...],
    validation_year: int,
) -> lgb.LGBMRegressor:
    train = frame[frame["year"].isin(train_years)]
    validation = frame[frame["year"] == validation_year]
    fitted = model()
    fitted.fit(
        train[features],
        train["actual_aces"],
        categorical_feature=["surface"],
        eval_set=[(validation[features], validation["actual_aces"])],
        eval_metric="poisson",
        callbacks=[lgb.early_stopping(80, verbose=False)],
    )
    return fitted


def rank_band(rank: float) -> str:
    for name, low, high in RANK_BANDS:
        if low <= rank <= high:
            return name
    return "RANK_501_PLUS"


def fit_factors(rows: pd.DataFrame, predictions: np.ndarray) -> dict[str, dict[str, float | int]]:
    work = rows.copy()
    work["_prediction"] = predictions
    work["_rank_band"] = work["player_rank"].fillna(999).map(rank_band)
    work["_thin"] = work["player_l12m_svpt"].fillna(0) <= THIN_SVPT_MAX
    output: dict[str, dict[str, float | int]] = {}
    for name, _low, _high in RANK_BANDS:
        subset = work[(work["_thin"]) & (work["_rank_band"] == name)]
        actual = float(subset["actual_aces"].sum())
        predicted = float(subset["_prediction"].sum())
        raw = actual / predicted if predicted > 0 else 1.0
        weight = len(subset) / (len(subset) + CALIBRATION_PRIOR_SIDES)
        factor = min(1.25, max(0.75, 1.0 + (raw - 1.0) * weight))
        output[name] = {
            "n": len(subset),
            "raw_actual_to_predicted": raw,
            "shrunk_factor": factor,
        }
    return output


def apply_factors(
    rows: pd.DataFrame,
    predictions: np.ndarray,
    factors: dict[str, dict[str, float | int]],
) -> np.ndarray:
    adjusted = np.asarray(predictions, dtype=float).copy()
    for position, (_index, row) in enumerate(rows.iterrows()):
        if float(row.get("player_l12m_svpt") or 0) > THIN_SVPT_MAX:
            continue
        band = rank_band(float(row.get("player_rank") or 999))
        adjusted[position] *= float(factors[band]["shrunk_factor"])
    return np.maximum(0.01, adjusted)


def metrics(module, rows: pd.DataFrame, predictions: np.ndarray, alpha: float) -> dict[str, object]:
    actual = rows["actual_aces"].to_numpy(dtype=float)
    incumbent = rows["incumbent_aces"].to_numpy(dtype=float)
    result = module.count_metrics(actual, incumbent, predictions)
    incumbent_alpha = module.fit_alpha(actual, incumbent)
    result.update(module.binary_metrics(
        actual, incumbent, predictions, incumbent_alpha, alpha,
    ))
    cohorts: dict[str, dict[str, float | int]] = {}
    cohort_masks = {
        "low_rank_thin": (
            (rows["player_rank"].fillna(999) > 200)
            & (rows["player_l12m_svpt"].fillna(0) <= THIN_SVPT_MAX)
        ),
        "top_200": rows["player_rank"].fillna(999) <= 200,
    }
    for name, mask in cohort_masks.items():
        subset_actual = actual[mask.to_numpy()]
        subset_predicted = predictions[mask.to_numpy()]
        cohorts[name] = {
            "n": len(subset_actual),
            "predicted_to_actual_ratio": (
                float(subset_predicted.sum() / subset_actual.sum())
                if subset_actual.sum() > 0 else 0.0
            ),
        }
    surfaces: dict[str, dict[str, float | int]] = {}
    for surface_name in ("Hard", "Clay"):
        mask = (rows["surface"].astype(str) == surface_name).to_numpy()
        surface_actual = actual[mask]
        surface_incumbent = incumbent[mask]
        surface_predicted = predictions[mask]
        surface_metrics = module.count_metrics(
            surface_actual, surface_incumbent, surface_predicted
        )
        surface_metrics.update(module.binary_metrics(
            surface_actual,
            surface_incumbent,
            surface_predicted,
            incumbent_alpha,
            alpha,
        ))
        surfaces[surface_name] = {"n": len(surface_actual), **surface_metrics}
    result["cohorts"] = cohorts
    result["surfaces"] = surfaces
    return result


def compare(
    a0: dict[str, object],
    a2: dict[str, object],
) -> dict[str, float | bool]:
    a0_mae = float(a0["candidate_mae"])
    a2_mae = float(a2["candidate_mae"])
    mae_improvement = 100.0 * (a0_mae - a2_mae) / a0_mae
    logloss_delta = float(a2["candidate_logloss"]) - float(a0["candidate_logloss"])
    return {
        "mae_improvement_pct": mae_improvement,
        "logloss_delta": logloss_delta,
        "g1_pass": mae_improvement >= 1.0,
        "g2_pass": logloss_delta <= -0.002,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--experiment-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    module = load_fit_module()
    frame, feature_columns = module.prepare_frame(args.source)
    frame = frame[frame["tour"] == "ATP"].copy()
    features = module.live_ace_feature_columns(feature_columns)

    development_model = fit(frame, features, (2023,), 2024)
    development_rows = frame[frame["year"] == 2024].copy()
    development_predictions = np.maximum(
        0.01, development_model.predict(development_rows[features])
    )
    factors = fit_factors(development_rows, development_predictions)

    final_model = fit(frame, features, (2023, 2024), 2025)
    selection_rows = frame[frame["year"] == 2025].copy()
    confirmatory_rows = frame[frame["year"] == 2026].copy()
    selection_raw = np.maximum(0.01, final_model.predict(selection_rows[features]))
    confirmatory_raw = np.maximum(0.01, final_model.predict(confirmatory_rows[features]))
    selection_predictions = apply_factors(selection_rows, selection_raw, factors)
    confirmatory_predictions = apply_factors(
        confirmatory_rows, confirmatory_raw, factors
    )
    alpha = module.fit_alpha(
        selection_rows["actual_aces"].to_numpy(dtype=float),
        selection_predictions,
    )
    selection_metrics = metrics(
        module, selection_rows, selection_predictions, alpha
    )
    confirmatory_metrics = metrics(
        module, confirmatory_rows, confirmatory_predictions, alpha
    )

    a1_result = json.loads(
        (args.experiment_dir / "result.json").read_text(encoding="utf-8")
    )
    a0_selection = a1_result["a0"]["selection_2025"]
    a0_confirmatory = a1_result["a0"]
    selection_comparison = compare(a0_selection, selection_metrics)
    confirmatory_comparison = compare(a0_confirmatory, confirmatory_metrics)
    g5 = 0.95 <= float(
        confirmatory_metrics["cohorts"]["low_rank_thin"]["predicted_to_actual_ratio"]
    ) <= 1.05
    g6 = 0.97 <= float(
        confirmatory_metrics["cohorts"]["top_200"]["predicted_to_actual_ratio"]
    ) <= 1.05
    g7 = (
        len(confirmatory_rows) >= 900
        and int(confirmatory_metrics["cohorts"]["low_rank_thin"]["n"]) >= 150
    )
    status = "PASS" if all((
        selection_comparison["g1_pass"],
        selection_comparison["g2_pass"],
        confirmatory_comparison["g1_pass"],
        confirmatory_comparison["g2_pass"],
        g5,
        g6,
        g7,
    )) else "FAIL"
    payload = {
        "version": "most-aces-coverage-a2-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "routing": "EXPERIMENT_ONLY_NO_LIVE_CHANGE",
        "development_factor_year": 2024,
        "thin_sample_svpt_max": THIN_SVPT_MAX,
        "calibration_prior_sides": CALIBRATION_PRIOR_SIDES,
        "factors": factors,
        "selection_2025": selection_metrics,
        "confirmatory_2026": confirmatory_metrics,
        "selection_vs_a0": selection_comparison,
        "confirmatory_vs_a0": confirmatory_comparison,
        "g5_low_rank_thin_ratio_pass": g5,
        "g6_top_200_ratio_pass": g6,
        "g7_sample_pass": g7,
        "decision": (
            "A2 eligible for prospective freeze"
            if status == "PASS" else "A2 rejected; retain A0 projection model"
        ),
    }
    output_dir = args.experiment_dir / "a2"
    output_dir.mkdir(parents=True, exist_ok=True)
    final_model.booster_.save_model(output_dir / "v3-atp-aces-live.txt")
    (output_dir / "result.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "Most Aces coverage A2 registered experiment",
        f"Status: {status} | EXPERIMENT_ONLY_NO_LIVE_CHANGE",
        (
            "Selection 2025 vs A0: "
            f"MAE {selection_comparison['mae_improvement_pct']:+.2f}% | "
            f"log-loss {selection_comparison['logloss_delta']:+.6f}"
        ),
        (
            "Confirmatory 2026 vs A0: "
            f"MAE {confirmatory_comparison['mae_improvement_pct']:+.2f}% | "
            f"log-loss {confirmatory_comparison['logloss_delta']:+.6f}"
        ),
        (
            "Low-rank thin ratio: "
            f"{confirmatory_metrics['cohorts']['low_rank_thin']['predicted_to_actual_ratio']:.3f} "
            f"(n={confirmatory_metrics['cohorts']['low_rank_thin']['n']})"
        ),
        (
            "Top-200 ratio: "
            f"{confirmatory_metrics['cohorts']['top_200']['predicted_to_actual_ratio']:.3f} "
            f"(n={confirmatory_metrics['cohorts']['top_200']['n']})"
        ),
        f"Decision: {payload['decision']}",
    ]
    (output_dir / "report.txt").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
