#!/usr/bin/env python3
"""Fit and evaluate the registered direct Most Aces P1/Draw/P2 model."""

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
EXPERIMENT_DIR = (
    ROOT / "data" / "tennis-props" / "experiments"
    / "most-aces-direct-1x2"
)
DEFAULT_SOURCE = EXPERIMENT_DIR / "pairwise-features.csv"
DEFAULT_A0_SOURCE = (
    ROOT / "data" / "tennis-props" / "backtest"
    / "aces-dfs-v3-all-tour-features.csv"
)
DEFAULT_OUT = EXPERIMENT_DIR
LABELS = ("P1", "DRAW", "P2")
LABEL_TO_INDEX = {label: index for index, label in enumerate(LABELS)}
IDENTITY = {
    "date", "year", "tour", "tournament", "level", "round",
    "player1_id", "player1", "player2_id", "player2",
    "actual_aces1", "actual_aces2", "outcome", "evidence_tier",
}
RHO = 0.22
SIMULATIONS = 2048


def load_module(name: str, filename: str):
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def feature_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column not in IDENTITY]


def prepare_features(
    frame: pd.DataFrame,
    features: list[str],
    *,
    categories: list[str] | None = None,
) -> pd.DataFrame:
    output = frame[features].copy()
    surface_categories = categories or ["Clay", "Hard"]
    output["surface"] = pd.Categorical(
        output["surface"], categories=surface_categories
    )
    for column in features:
        if column != "surface":
            output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0.0)
    return output


def mirror_features(frame: pd.DataFrame) -> pd.DataFrame:
    mirrored = frame.copy()
    for column in frame.columns:
        if column.endswith("_diff"):
            mirrored[column] = -pd.to_numeric(
                mirrored[column], errors="coerce"
            ).fillna(0.0)
    return mirrored


def mirror_labels(labels: np.ndarray) -> np.ndarray:
    return np.asarray([
        2 if value == 0 else 0 if value == 2 else 1
        for value in labels
    ], dtype=int)


def augment(frame: pd.DataFrame, labels: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
    return (
        pd.concat([frame, mirror_features(frame)], ignore_index=True),
        np.concatenate([labels, mirror_labels(labels)]),
    )


def classifier(n_estimators: int) -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(
        objective="multiclass",
        num_class=3,
        n_estimators=n_estimators,
        learning_rate=0.025,
        num_leaves=15,
        min_child_samples=120,
        subsample=0.85,
        colsample_bytree=0.80,
        reg_alpha=1.0,
        reg_lambda=5.0,
        random_state=20260729,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
        n_jobs=4,
    )


def symmetrised_probabilities(
    model: lgb.LGBMClassifier,
    frame: pd.DataFrame,
) -> tuple[np.ndarray, float]:
    canonical = np.asarray(model.predict_proba(frame), dtype=float)
    reversed_raw = np.asarray(
        model.predict_proba(mirror_features(frame)), dtype=float
    )
    reversed_mapped = reversed_raw[:, [2, 1, 0]]
    symmetry_gap = float(np.mean(np.abs(canonical - reversed_mapped)))
    return (canonical + reversed_mapped) * 0.5, symmetry_gap


def apply_temperature(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probabilities, 1e-12, 1.0)) / temperature
    logits -= logits.max(axis=1, keepdims=True)
    exponent = np.exp(logits)
    return exponent / exponent.sum(axis=1, keepdims=True)


def multiclass_logloss(
    probabilities: np.ndarray, labels: np.ndarray
) -> float:
    return float(np.mean(
        -np.log(np.clip(probabilities[np.arange(len(labels)), labels], 1e-12, 1.0))
    ))


def fit_temperature(probabilities: np.ndarray, labels: np.ndarray) -> float:
    left, right = math.log(0.5), math.log(2.5)
    ratio = (math.sqrt(5.0) - 1.0) / 2.0

    def objective(log_temperature: float) -> float:
        return multiclass_logloss(
            apply_temperature(probabilities, math.exp(log_temperature)),
            labels,
        )

    x1 = right - ratio * (right - left)
    x2 = left + ratio * (right - left)
    f1, f2 = objective(x1), objective(x2)
    for _ in range(70):
        if f1 <= f2:
            right, x2, f2 = x2, x1, f1
            x1 = right - ratio * (right - left)
            f1 = objective(x1)
        else:
            left, x1, f1 = x1, x2, f2
            x2 = left + ratio * (right - left)
            f2 = objective(x2)
    return math.exp((left + right) * 0.5)


def metrics(
    probabilities: np.ndarray,
    labels: np.ndarray,
    surfaces: pd.Series,
    evidence: pd.Series,
) -> dict[str, object]:
    targets = np.eye(3)[labels]
    brier_rows = np.sum(np.square(probabilities - targets), axis=1)
    predicted = np.argmax(probabilities, axis=1)

    def subset(mask: np.ndarray) -> dict[str, float | int]:
        count = int(mask.sum())
        if count == 0:
            return {
                "n": 0, "brier": 0.0, "logloss": 0.0,
                "accuracy_pct": 0.0, "predicted_draw_pct": 0.0,
                "actual_draw_pct": 0.0,
            }
        selected_probabilities = probabilities[mask]
        selected_labels = labels[mask]
        return {
            "n": count,
            "brier": float(np.mean(brier_rows[mask])),
            "logloss": multiclass_logloss(
                selected_probabilities, selected_labels
            ),
            "accuracy_pct": float(
                100.0 * np.mean(predicted[mask] == selected_labels)
            ),
            "predicted_draw_pct": float(
                100.0 * np.mean(selected_probabilities[:, 1])
            ),
            "actual_draw_pct": float(
                100.0 * np.mean(selected_labels == 1)
            ),
        }

    output = subset(np.ones(len(labels), dtype=bool))
    surface_values = surfaces.astype(str).to_numpy()
    evidence_values = evidence.astype(str).to_numpy()
    output["surfaces"] = {
        surface: subset(surface_values == surface)
        for surface in ("Hard", "Clay")
    }
    output["evidence"] = {
        tier: subset(evidence_values == tier)
        for tier in ("RECENT", "COVERAGE_GAP", "HISTORICAL", "INSUFFICIENT")
    }
    return output


def a0_side_predictions(
    fit_module,
    a2_module,
    source: Path,
) -> tuple[pd.DataFrame, dict[int, np.ndarray], float]:
    frame, columns = fit_module.prepare_frame(source)
    frame = frame[frame["tour"] == "ATP"].copy()
    features = fit_module.live_ace_feature_columns(columns)
    model = a2_module.fit(frame, features, (2023, 2024), 2025)
    selection = frame[frame["year"] == 2025].copy()
    diagnostic = frame[frame["year"] == 2026].copy()
    predictions = {
        2025: np.maximum(0.01, model.predict(selection[features])),
        2026: np.maximum(0.01, model.predict(diagnostic[features])),
    }
    alpha = fit_module.fit_alpha(
        selection["actual_aces"].to_numpy(dtype=float),
        predictions[2025],
    )
    combined = pd.concat([selection, diagnostic], axis=0).copy()
    combined["_candidate"] = np.concatenate([
        predictions[2025], predictions[2026]
    ])
    return combined, predictions, alpha


def side_key(row: pd.Series) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("date") or ""),
        str(row.get("tournament") or ""),
        str(row.get("round") or ""),
        str(row.get("player_id") or ""),
        str(row.get("opponent_id") or ""),
    )


def a0_probabilities(
    most_aces_module,
    side_rows: pd.DataFrame,
    pairs: pd.DataFrame,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray]:
    index = {
        side_key(row): float(row["_candidate"])
        for _position, row in side_rows.iterrows()
    }
    probabilities: list[tuple[float, float, float]] = []
    keep: list[bool] = []
    for _position, row in pairs.iterrows():
        key1 = (
            str(row["date"]), str(row["tournament"]), str(row["round"]),
            str(row["player1_id"]), str(row["player2_id"]),
        )
        key2 = (
            str(row["date"]), str(row["tournament"]), str(row["round"]),
            str(row["player2_id"]), str(row["player1_id"]),
        )
        mean1 = index.get(key1)
        mean2 = index.get(key2)
        if mean1 is None or mean2 is None:
            probabilities.append((1 / 3, 1 / 3, 1 / 3))
            keep.append(False)
            continue
        probabilities.append(most_aces_module.most_aces_probabilities(
            mean1,
            mean2,
            alpha1=alpha,
            alpha2=alpha,
            rho=RHO,
            simulations=SIMULATIONS,
        ))
        keep.append(True)
    return np.asarray(probabilities, dtype=float), np.asarray(keep, dtype=bool)


def comparison(
    control: dict[str, object], challenger: dict[str, object]
) -> dict[str, float | int | bool]:
    brier_delta = float(challenger["brier"]) - float(control["brier"])
    logloss_delta = (
        float(challenger["logloss"]) - float(control["logloss"])
    )
    accuracy_delta = (
        float(challenger["accuracy_pct"]) - float(control["accuracy_pct"])
    )
    return {
        "n": int(challenger["n"]),
        "a0_brier": float(control["brier"]),
        "direct_brier": float(challenger["brier"]),
        "brier_delta": brier_delta,
        "a0_logloss": float(control["logloss"]),
        "direct_logloss": float(challenger["logloss"]),
        "logloss_delta": logloss_delta,
        "accuracy_delta_pp": accuracy_delta,
        "brier_gate": brier_delta <= -0.005,
        "logloss_gate": logloss_delta <= -0.005,
        "accuracy_gate": accuracy_delta >= -1.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--a0-source", type=Path, default=DEFAULT_A0_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    fit_module = load_module("fit_props_direct", "fit-tennis-props-v3.py")
    a2_module = load_module(
        "coverage_a2_direct", "run-tennis-props-coverage-a2.py"
    )
    most_aces_module = load_module(
        "most_aces_direct", "tennis_most_aces.py"
    )
    frame = pd.read_csv(args.source)
    features = feature_columns(frame)
    categories = ["Clay", "Hard"]
    prepared = prepare_features(frame, features, categories=categories)
    labels = frame["outcome"].map(LABEL_TO_INDEX).to_numpy(dtype=int)

    development_train = frame["year"] == 2023
    development_validation = frame["year"] == 2024
    development_x, development_y = augment(
        prepared[development_train].reset_index(drop=True),
        labels[development_train.to_numpy()],
    )
    validation_x, validation_y_augmented = augment(
        prepared[development_validation].reset_index(drop=True),
        labels[development_validation.to_numpy()],
    )
    development_model = classifier(1200)
    development_model.fit(
        development_x,
        development_y,
        categorical_feature=["surface"],
        eval_set=[(validation_x, validation_y_augmented)],
        eval_metric="multi_logloss",
        callbacks=[lgb.early_stopping(100, verbose=False)],
    )
    validation_probabilities, _validation_symmetry = symmetrised_probabilities(
        development_model,
        prepared[development_validation].reset_index(drop=True),
    )
    validation_labels = labels[development_validation.to_numpy()]
    temperature = fit_temperature(
        validation_probabilities, validation_labels
    )
    best_iteration = int(
        development_model.best_iteration_
        or development_model.n_estimators
    )

    final_train = frame["year"].isin((2023, 2024))
    final_x, final_y = augment(
        prepared[final_train].reset_index(drop=True),
        labels[final_train.to_numpy()],
    )
    final_model = classifier(best_iteration)
    final_model.fit(
        final_x,
        final_y,
        categorical_feature=["surface"],
    )

    side_rows, _a0_predictions, a0_alpha = a0_side_predictions(
        fit_module, a2_module, args.a0_source
    )
    results: dict[str, object] = {}
    prediction_rows: list[pd.DataFrame] = []
    raw_symmetry: dict[str, float] = {}
    for year, period in ((2025, "selection_2025"), (2026, "diagnostic_2026")):
        mask = frame["year"] == year
        period_frame = frame[mask].reset_index(drop=True)
        period_x = prepared[mask].reset_index(drop=True)
        period_labels = labels[mask.to_numpy()]
        direct_raw, symmetry_gap = symmetrised_probabilities(
            final_model, period_x
        )
        direct = apply_temperature(direct_raw, temperature)
        raw_symmetry[period] = symmetry_gap
        a0, keep = a0_probabilities(
            most_aces_module,
            side_rows[side_rows["year"] == year],
            period_frame,
            a0_alpha,
        )
        if not keep.all():
            period_frame = period_frame[keep].reset_index(drop=True)
            direct = direct[keep]
            a0 = a0[keep]
            period_labels = period_labels[keep]
        direct_metrics = metrics(
            direct,
            period_labels,
            period_frame["surface"],
            period_frame["evidence_tier"],
        )
        a0_metrics = metrics(
            a0,
            period_labels,
            period_frame["surface"],
            period_frame["evidence_tier"],
        )
        results[period] = {
            "comparison": comparison(a0_metrics, direct_metrics),
            "a0": a0_metrics,
            "direct": direct_metrics,
            "raw_symmetry_gap": symmetry_gap,
        }
        rendered = period_frame[[
            "date", "tournament", "surface", "round", "player1", "player2",
            "actual_aces1", "actual_aces2", "outcome", "evidence_tier",
        ]].copy()
        rendered["period"] = period
        for index, label in enumerate(("p1", "draw", "p2")):
            rendered[f"a0_{label}"] = a0[:, index]
            rendered[f"direct_{label}"] = direct[:, index]
        prediction_rows.append(rendered)

    selection = results["selection_2025"]
    diagnostic = results["diagnostic_2026"]
    selection_comparison = selection["comparison"]
    diagnostic_comparison = diagnostic["comparison"]
    surface_gate = all(
        (
            int(selection["direct"]["surfaces"][surface]["n"]) < 200
            or (
                float(selection["direct"]["surfaces"][surface]["brier"])
                - float(selection["a0"]["surfaces"][surface]["brier"])
                <= 0.010
            )
        )
        for surface in ("Hard", "Clay")
    )
    draw_gap = abs(
        float(selection["direct"]["predicted_draw_pct"])
        - float(selection["direct"]["actual_draw_pct"])
    )
    gates = {
        "selection_brier": bool(selection_comparison["brier_gate"]),
        "selection_logloss": bool(selection_comparison["logloss_gate"]),
        "selection_accuracy": bool(selection_comparison["accuracy_gate"]),
        "surface_brier": surface_gate,
        "draw_calibration": draw_gap <= 3.0,
        "symmetry": float(selection["raw_symmetry_gap"]) <= 0.03,
        "selection_sample": int(selection_comparison["n"]) >= 1000,
        "diagnostic_brier": (
            float(diagnostic_comparison["brier_delta"]) <= 0.0
        ),
        "diagnostic_logloss": (
            float(diagnostic_comparison["logloss_delta"]) <= 0.0
        ),
    }
    status = "PASS" if all(gates.values()) else "FAIL"
    importance = pd.DataFrame({
        "feature": features,
        "gain": final_model.booster_.feature_importance(importance_type="gain"),
        "splits": final_model.booster_.feature_importance(importance_type="split"),
    }).sort_values("gain", ascending=False)
    payload = {
        "version": "most-aces-direct-1x2-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "routing": "EXPERIMENT_ONLY_NO_LIVE_CHANGE",
        "chronology": {
            "development_train": 2023,
            "iteration_and_temperature": 2024,
            "frozen_train": [2023, 2024],
            "selection": 2025,
            "diagnostic_only": 2026,
        },
        "best_iteration": best_iteration,
        "temperature": temperature,
        "a0_alpha": a0_alpha,
        "gates": gates,
        "results": results,
        "top_features": importance.head(20).to_dict("records"),
        "decision": (
            "Eligible for frozen prospective shadow only"
            if status == "PASS"
            else "Rejected; retain count-derived A0"
        ),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    final_model.booster_.save_model(args.out_dir / "direct-1x2-model.txt")
    importance.to_csv(args.out_dir / "feature-importance.csv", index=False)
    pd.concat(prediction_rows, ignore_index=True).to_csv(
        args.out_dir / "predictions.csv", index=False
    )
    (args.out_dir / "result.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "Most Aces Direct 1X2 registered experiment",
        f"Status: {status} | EXPERIMENT_ONLY_NO_LIVE_CHANGE",
        (
            f"Development best iteration: {best_iteration} | "
            f"temperature: {temperature:.4f}"
        ),
        (
            "Selection 2025: "
            f"Brier {selection_comparison['a0_brier']:.6f} -> "
            f"{selection_comparison['direct_brier']:.6f} "
            f"({selection_comparison['brier_delta']:+.6f}); "
            f"log-loss {selection_comparison['a0_logloss']:.6f} -> "
            f"{selection_comparison['direct_logloss']:.6f} "
            f"({selection_comparison['logloss_delta']:+.6f})"
        ),
        (
            "Diagnostic 2026: "
            f"Brier {diagnostic_comparison['a0_brier']:.6f} -> "
            f"{diagnostic_comparison['direct_brier']:.6f} "
            f"({diagnostic_comparison['brier_delta']:+.6f}); "
            f"log-loss {diagnostic_comparison['a0_logloss']:.6f} -> "
            f"{diagnostic_comparison['direct_logloss']:.6f} "
            f"({diagnostic_comparison['logloss_delta']:+.6f})"
        ),
        (
            "Selection draw calibration: "
            f"predicted {selection['direct']['predicted_draw_pct']:.2f}% vs "
            f"actual {selection['direct']['actual_draw_pct']:.2f}%"
        ),
        (
            "Raw symmetry gap: "
            f"{selection['raw_symmetry_gap']:.6f}"
        ),
        "Gates: " + ", ".join(
            f"{name}={'PASS' if passed else 'FAIL'}"
            for name, passed in gates.items()
        ),
        f"Decision: {payload['decision']}",
        "No production or public fair-odds routing changed.",
    ]
    (args.out_dir / "report.txt").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
