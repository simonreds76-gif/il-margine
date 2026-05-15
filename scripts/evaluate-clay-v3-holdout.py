#!/usr/bin/env python3
"""Evaluate Clay ML v3 on the 2024 hold-out."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EPS = 1e-12
MIN_LOGLOSS_ABS_IMPROVEMENT = 0.005
MIN_LOGLOSS_REL_IMPROVEMENT = 0.01
MIN_BRIER_IMPROVEMENT = 0.002
MAX_ECE = 0.035
MAX_MONTH_LOGLOSS_WORSE_BY = 0.005


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Clay ML v3 hold-out gates.")
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--test-year", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-z))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, EPS, 1.0 - EPS)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> tuple[float, list[dict[str, Any]]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(y)
    score = 0.0
    rows: list[dict[str, Any]] = []
    for i in range(bins):
        lo = edges[i]
        hi = edges[i + 1]
        if i == bins - 1:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        n = int(mask.sum())
        if n == 0:
            rows.append({"bin": i + 1, "lo": lo, "hi": hi, "n": 0, "pred": math.nan, "obs": math.nan})
            continue
        pred = float(p[mask].mean())
        obs = float(y[mask].mean())
        score += (n / total) * abs(pred - obs)
        rows.append({"bin": i + 1, "lo": lo, "hi": hi, "n": n, "pred": pred, "obs": obs})
    return float(score), rows


def predict(model: dict[str, Any], df: pd.DataFrame) -> np.ndarray:
    names = model["feature_names"]
    x_raw = df[names].astype(float).to_numpy()
    means = np.asarray(model["feature_means"], dtype=float)
    stds = np.asarray(model["feature_stds"], dtype=float)
    x = (x_raw - means) / stds
    beta = np.asarray(model["betas"], dtype=float)
    alpha = float(model["alpha"])
    pin = df["pin_implied_a"].astype(float).to_numpy()
    return sigmoid(logit(pin) + alpha + x @ beta)


def month_rows(df: pd.DataFrame, y: np.ndarray, p_v3: np.ndarray, p_pin: np.ndarray) -> tuple[list[str], bool]:
    lines: list[str] = []
    ok = True
    lines.append("Per-month log-loss")
    lines.append("month,n,v3,pinnacle,delta_pin_minus_v3,status")
    for month in sorted(df["month"].astype(int).unique()):
        mask = df["month"].astype(int).to_numpy() == month
        n = int(mask.sum())
        v3 = log_loss(y[mask], p_v3[mask])
        pin = log_loss(y[mask], p_pin[mask])
        status = "PASS"
        if n >= 30 and v3 > pin + MAX_MONTH_LOGLOSS_WORSE_BY:
            status = "FAIL"
            ok = False
        lines.append(f"{month},{n},{v3:.6f},{pin:.6f},{pin - v3:.6f},{status}")
    return lines, ok


def tournament_rows(df: pd.DataFrame, y: np.ndarray, p_v3: np.ndarray, p_pin: np.ndarray) -> list[str]:
    lines = ["", "Per-tournament log-loss", "tournament,n,v3,pinnacle,delta_pin_minus_v3"]
    for tournament in sorted(df["tournament_canonical_key"].unique()):
        mask = df["tournament_canonical_key"].to_numpy() == tournament
        lines.append(
            f"{tournament},{int(mask.sum())},{log_loss(y[mask], p_v3[mask]):.6f},"
            f"{log_loss(y[mask], p_pin[mask]):.6f},{log_loss(y[mask], p_pin[mask]) - log_loss(y[mask], p_v3[mask]):.6f}"
        )
    return lines


def write_failure_report(path: Path, report_text: str) -> None:
    failure_path = path.with_name("clay-v3-failure-report.md")
    failure_path.write_text(
        "# Clay ML v3 Failure Report\n\n"
        "The Phase B residual model failed at least one locked 2024 hold-out gate. "
        "Clay ML is dead for this design cycle; no signal wiring is authorised.\n\n"
        "```text\n"
        + report_text
        + "```\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.test_year >= 2025:
        raise SystemExit("Phase B evaluator refuses 2025+ sealed years.")
    model = json.loads(args.model.read_text(encoding="utf-8"))
    if args.test_year in model.get("training_years", []):
        raise SystemExit("Hold-out leakage guard: test year is in model training_years.")

    df = pd.read_csv(args.features)
    df["year"] = df["year"].astype(int)
    test_df = df[df["year"].eq(args.test_year)].copy()
    if test_df.empty:
        raise SystemExit(f"No rows for test year {args.test_year}.")
    y = test_df["a_won"].astype(int).to_numpy(dtype=float)
    p_pin = test_df["pin_implied_a"].astype(float).to_numpy()
    p_v3 = predict(model, test_df)

    ll_v3 = log_loss(y, p_v3)
    ll_pin = log_loss(y, p_pin)
    brier_v3 = brier(y, p_v3)
    brier_pin = brier(y, p_pin)
    ece_v3, calibration = ece(y, p_v3)
    ece_pin, _ = ece(y, p_pin)
    ll_abs_improvement = ll_pin - ll_v3
    ll_rel_improvement = ll_abs_improvement / ll_pin if ll_pin else 0.0
    brier_improvement = brier_pin - brier_v3

    gate_logloss = ll_abs_improvement >= MIN_LOGLOSS_ABS_IMPROVEMENT or ll_rel_improvement >= MIN_LOGLOSS_REL_IMPROVEMENT
    gate_brier = brier_improvement >= MIN_BRIER_IMPROVEMENT
    gate_ece = ece_v3 <= MAX_ECE and ece_v3 <= ece_pin
    month_table, gate_month = month_rows(test_df, y, p_v3, p_pin)
    overall = gate_logloss and gate_brier and gate_ece and gate_month

    lines: list[str] = []
    lines.append("Clay ML v3 hold-out report")
    lines.append("===========================")
    lines.append(f"model_version: {model.get('model_version')}")
    lines.append(f"training_years: {model.get('training_years')}")
    lines.append(f"test_year: {args.test_year}")
    lines.append(f"n_test: {len(test_df)}")
    lines.append(f"lambda_selected: {model.get('lambda_selected')}")
    lines.append(f"alpha: {float(model['alpha']):.12g}")
    for name, beta, mean, std in zip(model["feature_names"], model["betas"], model["feature_means"], model["feature_stds"]):
        lines.append(f"beta_{name}: {float(beta):.12g} mean={float(mean):.12g} std={float(std):.12g}")
    lines.append("")
    lines.append("Gate metrics")
    lines.append("metric,v3,pinnacle,delta_pin_minus_v3,gate,status")
    lines.append(
        f"log_loss,{ll_v3:.6f},{ll_pin:.6f},{ll_abs_improvement:.6f},"
        f">=0.005 abs OR >=1.0% rel ({ll_rel_improvement:.2%}),{'PASS' if gate_logloss else 'FAIL'}"
    )
    lines.append(
        f"brier,{brier_v3:.6f},{brier_pin:.6f},{brier_improvement:.6f},"
        f">=0.002,{'PASS' if gate_brier else 'FAIL'}"
    )
    lines.append(
        f"ece,{ece_v3:.6f},{ece_pin:.6f},{ece_pin - ece_v3:.6f},"
        f"<=0.035 and <=pinnacle_ece,{'PASS' if gate_ece else 'FAIL'}"
    )
    lines.append(f"worst_month_stability,,,,not worse than pinnacle +0.005,{'PASS' if gate_month else 'FAIL'}")
    lines.append("")
    lines.extend(month_table)
    lines.extend(tournament_rows(test_df, y, p_v3, p_pin))
    lines.append("")
    lines.append("Calibration curve - p_v3 equal-width bins")
    lines.append("bin,lo,hi,n,pred,observed")
    for row in calibration:
        pred = "" if math.isnan(row["pred"]) else f"{row['pred']:.6f}"
        obs = "" if math.isnan(row["obs"]) else f"{row['obs']:.6f}"
        lines.append(f"{row['bin']},{row['lo']:.1f},{row['hi']:.1f},{row['n']},{pred},{obs}")
    lines.append("")
    lines.append(f"overall_status: {'PASS' if overall else 'FAIL'}")
    if overall:
        lines.append("decision: model JSON may ship as an unwired research artefact. No signal lane is authorised here.")
    else:
        lines.append("decision: clay ML v3 failed the locked hold-out gates; no signal wiring is authorised.")

    report_text = "\n".join(lines) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report_text, encoding="utf-8")
    print(report_text)
    if not overall:
        write_failure_report(args.out, report_text)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
