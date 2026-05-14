#!/usr/bin/env python3
"""Evaluate a locked clay ML v2 model on the 2025 sealed set.

This script does not train. It exists so the sealed touch is mechanically
separate from validation.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import pickle
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from _lib.clay_v2_features import FEATURE_COLUMNS
from _lib.clay_v2_metrics import (
    EPS,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"
SEALED_YEAR = 2025
SEALED_MIN_N = 600
SEALED_MAX_ECE = 0.04


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate locked clay ML v2 model on 2025 sealed data.")
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, default=BACKTEST_DIR / "clay-v2-2025-sealed.txt")
    parser.add_argument("--holdout-log", type=Path, default=BACKTEST_DIR / "_holdout-log.md")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clip(probs: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(probs, dtype=float), EPS, 1.0 - EPS)


def _logit(probs: np.ndarray) -> np.ndarray:
    p = _clip(probs)
    return np.log(p / (1.0 - p))


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def apply_platt(probs: np.ndarray, a: float, b: float) -> np.ndarray:
    return _clip(_sigmoid(a + b * _logit(probs)))


def encoded_features(df: pd.DataFrame, artifact: dict) -> pd.DataFrame:
    cols = list(FEATURE_COLUMNS)
    if not artifact.get("include_pinnacle", True):
        cols.remove("pinnacle_prob_novig")
    frame = df[cols].copy()
    for col in cols:
        if col == "tournament_cohort":
            continue
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = pd.get_dummies(frame, columns=["tournament_cohort"], dummy_na=False, dtype=float)
    return frame.reindex(columns=artifact["encoded_columns"], fill_value=0.0)


def predict(df: pd.DataFrame, artifact: dict) -> np.ndarray:
    model = artifact["model"]
    x = encoded_features(df, artifact)
    raw = _clip(model.predict_proba(x)[:, 1])
    if artifact.get("blessed_output") == "platt":
        params = artifact.get("platt") or {"a": 0.0, "b": 1.0}
        return apply_platt(raw, float(params["a"]), float(params["b"]))
    return raw


def main() -> int:
    args = parse_args()
    if not args.model.exists():
        raise SystemExit(f"model artifact missing - did you run validation first? path={args.model}")
    if not args.features.exists():
        raise SystemExit(f"sealed feature CSV missing - build it only after validation passes: path={args.features}")

    with args.model.open("rb") as f:
        artifact = pickle.load(f)
    if artifact.get("validation", {}).get("decision") != "PASS":
        raise SystemExit("locked model did not pass validation; sealed evaluation is blocked")

    df = pd.read_csv(args.features)
    if set(df["source_year"].astype(int).unique()) != {SEALED_YEAR}:
        raise SystemExit(f"sealed script only accepts source_year={SEALED_YEAR}")
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    labels = df["label_player_a_win"].astype(int).to_numpy()
    probs = predict(df, artifact)
    pin = df["pinnacle_prob_novig"].astype(float).to_numpy()

    ll = binary_log_loss(labels, probs)
    pin_ll = binary_log_loss(labels, pin)
    brier = brier_score(labels, probs)
    pin_brier = brier_score(labels, pin)
    ece, ece_n, _ = expected_calibration_error(labels, probs)

    month_failures: list[str] = []
    month_rows: list[str] = []
    for month, group in df.groupby(df["date"].dt.month):
        if len(group) < 30:
            continue
        idx = group.index.to_numpy()
        month_ll = binary_log_loss(labels[idx], probs[idx])
        month_pin_ll = binary_log_loss(labels[idx], pin[idx])
        ok = month_ll <= month_pin_ll + 0.005
        if not ok:
            month_failures.append(str(month))
        month_rows.append(f"| {month} | {len(group)} | {month_ll:.4f} | {month_pin_ll:.4f} | {'PASS' if ok else 'FAIL'} |")

    fail_reasons: list[str] = []
    if len(df) < SEALED_MIN_N:
        fail_reasons.append(f"sealed_n<{SEALED_MIN_N}")
    if not ll < pin_ll:
        fail_reasons.append("log_loss_not_better_than_pinnacle")
    if not brier < pin_brier:
        fail_reasons.append("brier_not_better_than_pinnacle")
    if ece is None or ece > SEALED_MAX_ECE:
        fail_reasons.append("ece_gate_failed")
    if month_failures:
        fail_reasons.append(f"month_stability_failed:{','.join(month_failures)}")
    decision = "PASS" if not fail_reasons else "FAIL"

    lines = [
        "Clay ML v2 2025 sealed report",
        "==============================",
        f"generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"features: {args.features}",
        f"model: {args.model}",
        f"n: {len(df)}",
        f"log_loss(M_full): {ll:.4f}",
        f"log_loss(Pinnacle): {pin_ll:.4f}",
        f"delta_log_loss_vs_pinnacle: {ll - pin_ll:+.4f}",
        f"brier(M_full): {brier:.4f}",
        f"brier(Pinnacle): {pin_brier:.4f}",
        f"delta_brier_vs_pinnacle: {brier - pin_brier:+.4f}",
        f"ece(M_full): {'n/a' if ece is None else f'{ece:.4f}'} (n={ece_n})",
        "",
        "Per-month log-loss stability",
        "| month | n | model_ll | pinnacle_ll | gate |",
        "|---:|---:|---:|---:|---|",
        *month_rows,
        "",
        f"decision: {decision}",
    ]
    if fail_reasons:
        lines.append(f"fail_reasons: {', '.join(fail_reasons)}")
    report = "\n".join(lines) + "\n"
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(report, encoding="utf-8")

    args.holdout_log.parent.mkdir(parents=True, exist_ok=True)
    with args.holdout_log.open("a", encoding="utf-8") as f:
        f.write(
            "\n"
            f"| {datetime.now(timezone.utc).isoformat()} | clay_v2 | "
            f"{sha256(args.model)} | {sha256(args.features)} | {sha256(args.report_out)} | "
            f"{ll:.6f} | {pin_ll:.6f} | {brier:.6f} | {pin_brier:.6f} | "
            f"{'n/a' if ece is None else f'{ece:.6f}'} | {decision} |\n"
        )
    print(report)
    return 0 if decision == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
