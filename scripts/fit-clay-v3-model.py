#!/usr/bin/env python3
"""Fit Clay ML v3 residual model.

Model form:
    logit(p_a) = logit(pin_implied_a) + alpha + X beta

The Pinnacle offset coefficient is fixed at 1.0. This script never trains on
2024 unless explicitly passed as a training year, and Phase B calls it with
2022+2023 only.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize


FEATURE_NAMES = ["ta_surface_speed", "altitude_m", "temp_mean_c"]
LAMBDA_GRID = [0.01, 0.1, 1.0, 10.0]
EPS = 1e-12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit Clay ML v3 ridge residual model.")
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--train-years", nargs="+", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-z))


def standardise(train_x: np.ndarray, apply_x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    means = train_x.mean(axis=0)
    stds = train_x.std(axis=0, ddof=0)
    stds = np.where(stds <= 0.0, 1.0, stds)
    return (apply_x - means) / stds, means, stds


def objective(theta: np.ndarray, x: np.ndarray, y: np.ndarray, pin: np.ndarray, lam: float) -> tuple[float, np.ndarray]:
    z = logit(pin) + theta[0] + x @ theta[1:]
    p = sigmoid(z)
    nll = -np.sum(y * np.log(np.clip(p, EPS, 1.0)) + (1.0 - y) * np.log(np.clip(1.0 - p, EPS, 1.0)))
    penalty = 0.5 * lam * float(theta @ theta)
    grad_common = p - y
    grad = np.empty_like(theta)
    grad[0] = np.sum(grad_common)
    grad[1:] = x.T @ grad_common
    grad += lam * theta
    return nll + penalty, grad


def fit_theta(x: np.ndarray, y: np.ndarray, pin: np.ndarray, lam: float) -> np.ndarray:
    init = np.zeros(x.shape[1] + 1, dtype=float)
    result = minimize(
        fun=lambda theta: objective(theta, x, y, pin, lam),
        x0=init,
        jac=True,
        method="L-BFGS-B",
        options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 10000},
    )
    if not result.success:
        raise RuntimeError(f"ridge fit failed for lambda={lam}: {result.message}")
    return result.x


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, EPS, 1.0 - EPS)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def predict(theta: np.ndarray, x: np.ndarray, pin: np.ndarray) -> np.ndarray:
    return sigmoid(logit(pin) + theta[0] + x @ theta[1:])


def select_lambda_cv(df: pd.DataFrame, train_years: list[int]) -> tuple[float, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    best_lambda = LAMBDA_GRID[0]
    best_loss = math.inf
    for lam in LAMBDA_GRID:
        fold_losses: list[float] = []
        for val_year in train_years:
            fold_train = df[df["year"].astype(int).isin([y for y in train_years if y != val_year])]
            fold_val = df[df["year"].astype(int).eq(val_year)]
            if fold_train.empty or fold_val.empty:
                continue
            train_x = fold_train[FEATURE_NAMES].astype(float).to_numpy()
            val_x_raw = fold_val[FEATURE_NAMES].astype(float).to_numpy()
            val_x, means, stds = standardise(train_x, val_x_raw)
            train_x_std = (train_x - means) / stds
            theta = fit_theta(
                train_x_std,
                fold_train["a_won"].astype(int).to_numpy(dtype=float),
                fold_train["pin_implied_a"].astype(float).to_numpy(),
                lam,
            )
            pred = predict(theta, val_x, fold_val["pin_implied_a"].astype(float).to_numpy())
            fold_losses.append(log_loss(fold_val["a_won"].astype(int).to_numpy(dtype=float), pred))
        avg_loss = float(np.mean(fold_losses)) if fold_losses else math.inf
        results.append({"lambda": lam, "fold_log_losses": fold_losses, "avg_log_loss": avg_loss})
        if avg_loss < best_loss:
            best_loss = avg_loss
            best_lambda = lam
    return best_lambda, results


def main() -> int:
    args = parse_args()
    np.random.seed(args.seed)
    train_years = sorted(set(args.train_years))
    if any(year >= 2025 for year in train_years):
        raise SystemExit("Phase B fit refuses 2025+ sealed years.")

    df = pd.read_csv(args.features)
    df["year"] = df["year"].astype(int)
    train_df = df[df["year"].isin(train_years)].copy()
    if train_df.empty:
        raise SystemExit("No training rows for requested years.")
    seen_years = sorted(train_df["year"].unique().tolist())
    if seen_years != train_years:
        raise SystemExit(f"Training year mismatch: requested={train_years}, seen={seen_years}")
    if 2024 in train_years:
        raise SystemExit("Phase B hold-out leakage guard: 2024 cannot be a training year.")

    selected_lambda, cv_results = select_lambda_cv(train_df, train_years)
    train_x_raw = train_df[FEATURE_NAMES].astype(float).to_numpy()
    train_x, means, stds = standardise(train_x_raw, train_x_raw)
    y = train_df["a_won"].astype(int).to_numpy(dtype=float)
    pin = train_df["pin_implied_a"].astype(float).to_numpy()
    theta = fit_theta(train_x, y, pin, selected_lambda)
    train_pred = predict(theta, train_x, pin)

    model = {
        "model_version": "clay-v3",
        "fit_date_utc": datetime.now(timezone.utc).isoformat(),
        "training_years": train_years,
        "n_train": int(len(train_df)),
        "lambda_selected": selected_lambda,
        "lambda_grid": LAMBDA_GRID,
        "cv_results": cv_results,
        "feature_names": FEATURE_NAMES,
        "feature_means": [float(v) for v in means],
        "feature_stds": [float(v) for v in stds],
        "alpha": float(theta[0]),
        "betas": [float(v) for v in theta[1:]],
        "offset_coefficient": 1.0,
        "train_log_loss_v3": log_loss(y, train_pred),
        "train_log_loss_pinnacle": log_loss(y, pin),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"train_years_seen: {seen_years}")
    print(f"n_train: {len(train_df)}")
    print(f"lambda_selected: {selected_lambda}")
    print(f"train_log_loss_v3: {model['train_log_loss_v3']:.6f}")
    print(f"train_log_loss_pinnacle: {model['train_log_loss_pinnacle']:.6f}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
