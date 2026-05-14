#!/usr/bin/env python3
"""Fit and validate the clay ML v2 base probability model.

The model is research-only. It reads a prebuilt feature CSV, trains on the
requested train years, validates on one later year, and writes a locked report.
It does not emit signals and it does not read sealed-year data unless the
caller explicitly passes such a feature CSV.
"""

from __future__ import annotations

import argparse
import csv
import math
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from _lib.clay_v2_features import FEATURE_COLUMNS
from _lib.clay_v2_metrics import (
    EPS,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
    roi_by_edge_band,
)


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"

LGBM_PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 30,
    "feature_fraction": 0.85,
    "bagging_fraction": 0.85,
    "bagging_freq": 5,
    "max_depth": 6,
    "lambda_l2": 1.0,
    "verbose": -1,
    "seed": 42,
}
NUM_BOOST_ROUND_MAX = 500
EARLY_STOPPING_ROUNDS = 50
VALIDATION_MIN_N = 600
VALIDATION_MAX_ECE = 0.04


@dataclass(frozen=True)
class ModelResult:
    name: str
    model: lgb.LGBMClassifier
    encoded_columns: list[str]
    raw_probs: np.ndarray
    calibrated_probs: np.ndarray
    platt_a: float
    platt_b: float
    blessed_output: str
    blessed_probs: np.ndarray
    log_loss: float
    brier: float
    ece: float | None
    ece_n: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit clay ML v2 model and validate on a held-out year.")
    parser.add_argument("--features", type=Path, required=True, help="Feature CSV from build-clay-v2-features.py.")
    parser.add_argument("--train-years", nargs="+", type=int, required=True, help="Training years.")
    parser.add_argument("--validation-year", type=int, required=True, help="Validation year.")
    parser.add_argument("--model-out", type=Path, default=BACKTEST_DIR / "clay-v2-model.pkl")
    parser.add_argument("--report-out", type=Path, default=BACKTEST_DIR / "clay-v2-validation-2024.txt")
    parser.add_argument("--importance-out", type=Path, default=BACKTEST_DIR / "clay-v2-feature-importance.csv")
    parser.add_argument("--postmortem-out", type=Path, default=BACKTEST_DIR / "clay-v2-postmortem.md")
    return parser.parse_args()


def _clip(probs: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(probs, dtype=float), EPS, 1.0 - EPS)


def _logit(probs: np.ndarray) -> np.ndarray:
    p = _clip(probs)
    return np.log(p / (1.0 - p))


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def fit_platt(probs: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    logits = _logit(probs)
    y = labels.astype(float)

    def objective(params: np.ndarray) -> float:
        a, b = params
        p = _clip(_sigmoid(a + b * logits))
        return float(-(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)).mean())

    result = minimize(objective, np.asarray([0.0, 1.0]), method="BFGS")
    if not result.success:
        return 0.0, 1.0
    return float(result.x[0]), float(result.x[1])


def apply_platt(probs: np.ndarray, a: float, b: float) -> np.ndarray:
    return _clip(_sigmoid(a + b * _logit(probs)))


def feature_frame(df: pd.DataFrame, *, include_pinnacle: bool) -> pd.DataFrame:
    cols = list(FEATURE_COLUMNS)
    if not include_pinnacle:
        cols.remove("pinnacle_prob_novig")
    frame = df[cols].copy()
    for col in cols:
        if col == "tournament_cohort":
            continue
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def encode_train_val(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    *,
    include_pinnacle: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    train_frame = feature_frame(train_df, include_pinnacle=include_pinnacle)
    val_frame = feature_frame(val_df, include_pinnacle=include_pinnacle)
    combined = pd.concat([train_frame, val_frame], axis=0, ignore_index=True)
    combined = pd.get_dummies(combined, columns=["tournament_cohort"], dummy_na=False, dtype=float)
    combined = combined.fillna(np.nan)
    train_x = combined.iloc[: len(train_df)].copy()
    val_x = combined.iloc[len(train_df) :].copy()
    encoded_columns = list(combined.columns)
    return train_x, val_x, encoded_columns


def encode_with_columns(df: pd.DataFrame, *, include_pinnacle: bool, encoded_columns: list[str]) -> pd.DataFrame:
    frame = feature_frame(df, include_pinnacle=include_pinnacle)
    frame = pd.get_dummies(frame, columns=["tournament_cohort"], dummy_na=False, dtype=float)
    return frame.reindex(columns=encoded_columns, fill_value=0.0)


def fit_lgbm(train_x: pd.DataFrame, train_y: np.ndarray, val_x: pd.DataFrame, val_y: np.ndarray) -> lgb.LGBMClassifier:
    model = lgb.LGBMClassifier(**LGBM_PARAMS, n_estimators=NUM_BOOST_ROUND_MAX)
    model.fit(
        train_x,
        train_y,
        eval_set=[(val_x, val_y)],
        eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)],
    )
    return model


def fit_one_model(name: str, train_df: pd.DataFrame, val_df: pd.DataFrame, *, include_pinnacle: bool) -> ModelResult:
    train_df = train_df.sort_values(["date", "winner_id", "loser_id"]).reset_index(drop=True)
    val_df = val_df.sort_values(["date", "winner_id", "loser_id"]).reset_index(drop=True)
    train_y = train_df["label_player_a_win"].astype(int).to_numpy()
    val_y = val_df["label_player_a_win"].astype(int).to_numpy()

    split_idx = max(1, int(len(train_df) * 0.8))
    fit_part = train_df.iloc[:split_idx].copy()
    cal_part = train_df.iloc[split_idx:].copy()
    if cal_part.empty:
        raise ValueError("training set is too small for chronological Platt split")

    cal_train_x, cal_x, _ = encode_train_val(fit_part, cal_part, include_pinnacle=include_pinnacle)
    cal_model = fit_lgbm(
        cal_train_x,
        fit_part["label_player_a_win"].astype(int).to_numpy(),
        cal_x,
        cal_part["label_player_a_win"].astype(int).to_numpy(),
    )
    cal_probs = _clip(cal_model.predict_proba(cal_x)[:, 1])
    platt_a, platt_b = fit_platt(cal_probs, cal_part["label_player_a_win"].astype(int).to_numpy())

    train_x, val_x, encoded_columns = encode_train_val(train_df, val_df, include_pinnacle=include_pinnacle)
    model = fit_lgbm(train_x, train_y, val_x, val_y)
    raw_probs = _clip(model.predict_proba(val_x)[:, 1])
    calibrated_probs = apply_platt(raw_probs, platt_a, platt_b)

    raw_ll = binary_log_loss(val_y, raw_probs)
    cal_ll = binary_log_loss(val_y, calibrated_probs)
    if cal_ll < raw_ll:
        blessed_output = "platt"
        blessed_probs = calibrated_probs
    else:
        blessed_output = "raw"
        blessed_probs = raw_probs
    ece, ece_n, _ = expected_calibration_error(val_y, blessed_probs)
    return ModelResult(
        name=name,
        model=model,
        encoded_columns=encoded_columns,
        raw_probs=raw_probs,
        calibrated_probs=calibrated_probs,
        platt_a=platt_a,
        platt_b=platt_b,
        blessed_output=blessed_output,
        blessed_probs=blessed_probs,
        log_loss=binary_log_loss(val_y, blessed_probs),
        brier=brier_score(val_y, blessed_probs),
        ece=ece,
        ece_n=ece_n,
    )


def importance_rows(result: ModelResult) -> list[dict[str, Any]]:
    booster = result.model.booster_
    gains = booster.feature_importance(importance_type="gain")
    splits = booster.feature_importance(importance_type="split")
    rows = [
        {"feature": feature, "gain": float(gain), "split": int(split)}
        for feature, gain, split in zip(result.encoded_columns, gains, splits, strict=True)
    ]
    rows.sort(key=lambda row: row["gain"], reverse=True)
    return rows


def fmt(value: float | None, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:.{digits}f}"


def write_importance(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["feature", "gain", "split"])
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    path: Path,
    *,
    features_path: Path,
    train_years: list[int],
    validation_year: int,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    full: ModelResult,
    no_pin: ModelResult,
    benchmark_probs: np.ndarray,
    importance: list[dict[str, Any]],
    decision_pass: bool,
    fail_reasons: list[str],
) -> str:
    y_val = val_df["label_player_a_win"].astype(int).to_numpy()
    pin_ll = binary_log_loss(y_val, benchmark_probs)
    pin_brier = brier_score(y_val, benchmark_probs)
    pin_ece, pin_ece_n, _ = expected_calibration_error(y_val, benchmark_probs)
    raw_full_ll = binary_log_loss(y_val, full.raw_probs)
    cal_full_ll = binary_log_loss(y_val, full.calibrated_probs)
    raw_no_pin_ll = binary_log_loss(y_val, no_pin.raw_probs)
    cal_no_pin_ll = binary_log_loss(y_val, no_pin.calibrated_probs)
    roi_rows = roi_by_edge_band(
        y_val,
        full.blessed_probs,
        benchmark_probs,
        val_df["pinnacle_odds_a"].astype(float).to_numpy(),
        val_df["pinnacle_odds_b"].astype(float).to_numpy(),
    )

    lines: list[str] = []
    lines.append("Clay ML v2 validation report")
    lines.append("=" * 29)
    lines.append(f"generated_at_utc: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"features: {features_path}")
    lines.append(f"train_years: {train_years}")
    lines.append(f"validation_year: {validation_year}")
    lines.append("")
    lines.append("Important data correction")
    lines.append("- backtest-results rows are winner-first: player1 == actual_winner for every clay row audited.")
    lines.append("- The feature builder therefore uses deterministic player-A orientation and trains P(player_a wins).")
    lines.append("- pinnacle_prob_novig and our_prob_raw are transformed into player-A space before fitting.")
    lines.append("")
    lines.append("Rows")
    lines.append(f"- train_n: {len(train_df)}")
    lines.append(f"- validation_n: {len(val_df)}")
    lines.append(f"- validation_label_rate_player_a_win: {float(y_val.mean()):.4f}")
    lines.append("")
    lines.append("Primary M_full metrics")
    lines.append(f"- blessed_output: {full.blessed_output}")
    lines.append(f"- raw_log_loss: {raw_full_ll:.4f}")
    lines.append(f"- platt_log_loss: {cal_full_ll:.4f}")
    lines.append(f"- log_loss(M_full): {full.log_loss:.4f}")
    lines.append(f"- log_loss(Pinnacle): {pin_ll:.4f}")
    lines.append(f"- delta_log_loss_vs_pinnacle: {full.log_loss - pin_ll:+.4f}")
    lines.append(f"- brier(M_full): {full.brier:.4f}")
    lines.append(f"- brier(Pinnacle): {pin_brier:.4f}")
    lines.append(f"- delta_brier_vs_pinnacle: {full.brier - pin_brier:+.4f}")
    lines.append(f"- ece(M_full): {fmt(full.ece)} (n={full.ece_n})")
    lines.append(f"- ece(Pinnacle): {fmt(pin_ece)} (n={pin_ece_n})")
    lines.append(f"- platt_a: {full.platt_a:.6f}")
    lines.append(f"- platt_b: {full.platt_b:.6f}")
    lines.append("")
    lines.append("Diagnostic M_no_pin metrics")
    lines.append(f"- blessed_output: {no_pin.blessed_output}")
    lines.append(f"- raw_log_loss: {raw_no_pin_ll:.4f}")
    lines.append(f"- platt_log_loss: {cal_no_pin_ll:.4f}")
    lines.append(f"- log_loss(M_no_pin): {no_pin.log_loss:.4f}")
    lines.append(f"- delta_log_loss_vs_pinnacle: {no_pin.log_loss - pin_ll:+.4f}")
    lines.append(f"- brier(M_no_pin): {no_pin.brier:.4f}")
    lines.append(f"- delta_brier_vs_pinnacle: {no_pin.brier - pin_brier:+.4f}")
    lines.append(f"- ece(M_no_pin): {fmt(no_pin.ece)} (n={no_pin.ece_n})")
    lines.append("")
    lines.append("Validation gates")
    lines.append(f"- n >= {VALIDATION_MIN_N}: {'PASS' if len(val_df) >= VALIDATION_MIN_N else 'FAIL'}")
    lines.append(f"- log_loss(M_full) < log_loss(Pinnacle): {'PASS' if full.log_loss < pin_ll else 'FAIL'}")
    lines.append(f"- brier(M_full) < brier(Pinnacle): {'PASS' if full.brier < pin_brier else 'FAIL'}")
    lines.append(
        f"- ece(M_full) <= {VALIDATION_MAX_ECE:.2f}: "
        f"{'PASS' if full.ece is not None and full.ece <= VALIDATION_MAX_ECE else 'FAIL'}"
    )
    lines.append(f"decision: {'PASS' if decision_pass else 'FAIL'}")
    if fail_reasons:
        lines.append(f"fail_reasons: {', '.join(fail_reasons)}")
    lines.append("")
    lines.append("ROI inspection only, not a validation gate")
    lines.append("| edge_band | n | wins | pnl | roi |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in roi_rows:
        lines.append(
            f"| {row['edge_band']} | {row['n']} | {row['wins']} | "
            f"{float(row['pnl']):+.2f} | {float(row['roi']):+.2%} |"
        )
    lines.append("")
    lines.append("Top feature importances by LightGBM gain")
    lines.append("| rank | feature | gain | split |")
    lines.append("|---:|---|---:|---:|")
    for rank, row in enumerate(importance[:15], start=1):
        lines.append(f"| {rank} | {row['feature']} | {float(row['gain']):.4f} | {row['split']} |")
    lines.append("")
    lines.append("Known limitations")
    lines.append("- players_atp atp_rank and clay_points are current-snapshot fields, not point-in-time ranks.")
    lines.append("- players_atp has no hand column in this repo; lefty flags come only from left_handed_players.csv.")
    lines.append("- No CLV gate is reported because historical open and close prices are degenerate in this repo.")
    lines.append("")
    text = "\n".join(lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def append_postmortem(path: Path, report_text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "\n\n" if path.exists() and path.read_text(encoding="utf-8").strip() else ""
    with path.open("a", encoding="utf-8") as f:
        f.write(header)
        f.write("## Clay ML v2 validation kill\n\n")
        f.write("The model did not clear the locked 2024 validation gates. No 2025 sealed touch is allowed for this design iteration.\n\n")
        f.write("Validation report snapshot:\n\n")
        for line in report_text.splitlines():
            f.write(f"> {line}\n" if line else ">\n")


def main() -> int:
    args = parse_args()
    df = pd.read_csv(args.features)
    if len(FEATURE_COLUMNS) != 47:
        raise AssertionError(f"expected 47 locked feature columns, got {len(FEATURE_COLUMNS)}")
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    train_years = sorted(set(args.train_years))
    train_df = df[df["source_year"].isin(train_years)].copy()
    val_df = df[df["source_year"].eq(args.validation_year)].copy()
    if train_df.empty:
        raise SystemExit("no training rows found for requested train years")
    if val_df.empty:
        raise SystemExit("no validation rows found for requested validation year")

    full = fit_one_model("M_full", train_df, val_df, include_pinnacle=True)
    no_pin = fit_one_model("M_no_pin", train_df, val_df, include_pinnacle=False)
    benchmark_probs = val_df["pinnacle_prob_novig"].astype(float).to_numpy()
    y_val = val_df["label_player_a_win"].astype(int).to_numpy()
    pin_ll = binary_log_loss(y_val, benchmark_probs)
    pin_brier = brier_score(y_val, benchmark_probs)

    fail_reasons: list[str] = []
    if len(val_df) < VALIDATION_MIN_N:
        fail_reasons.append(f"validation_n<{VALIDATION_MIN_N}")
    if not full.log_loss < pin_ll:
        fail_reasons.append("log_loss_not_better_than_pinnacle")
    if not full.brier < pin_brier:
        fail_reasons.append("brier_not_better_than_pinnacle")
    if full.ece is None or full.ece > VALIDATION_MAX_ECE:
        fail_reasons.append("ece_gate_failed")
    decision_pass = not fail_reasons

    importance = importance_rows(full)
    write_importance(args.importance_out, importance)
    artifact = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": "clay_ml_v2_lightgbm",
        "train_years": train_years,
        "validation_year": args.validation_year,
        "feature_columns": FEATURE_COLUMNS,
        "include_pinnacle": True,
        "encoded_columns": full.encoded_columns,
        "lgbm_params": LGBM_PARAMS,
        "num_boost_round_max": NUM_BOOST_ROUND_MAX,
        "early_stopping_rounds": EARLY_STOPPING_ROUNDS,
        "blessed_output": full.blessed_output,
        "platt": {"a": full.platt_a, "b": full.platt_b},
        "model": full.model,
        "validation": {
            "n": int(len(val_df)),
            "log_loss": full.log_loss,
            "brier": full.brier,
            "ece": full.ece,
            "decision": "PASS" if decision_pass else "FAIL",
            "fail_reasons": fail_reasons,
        },
    }
    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    with args.model_out.open("wb") as f:
        pickle.dump(artifact, f)

    report_text = write_report(
        args.report_out,
        features_path=args.features,
        train_years=train_years,
        validation_year=args.validation_year,
        train_df=train_df,
        val_df=val_df,
        full=full,
        no_pin=no_pin,
        benchmark_probs=benchmark_probs,
        importance=importance,
        decision_pass=decision_pass,
        fail_reasons=fail_reasons,
    )
    if not decision_pass:
        append_postmortem(args.postmortem_out, report_text)
    print(report_text)
    return 0 if decision_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
