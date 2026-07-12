#!/usr/bin/env python3
"""Run the registered rolling-fold rung-1 anchored residual experiment."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from common import DEFAULT_OUTPUT_DIR, ROOT, sha256_file, write_json


BACKTEST_DIR = ROOT / "data" / "backtest"
REGISTRATION = DEFAULT_OUTPUT_DIR / "experiment-registration-v0.2.json"
FEATURES = DEFAULT_OUTPUT_DIR / "vnext-v02-features.csv"
REPORT = BACKTEST_DIR / "vnext-v02-folds-report.txt"
LADDER = BACKTEST_DIR / "vnext-v02-ladder.csv"
EXPOSED = BACKTEST_DIR / "vnext-v02-exposed-2025.txt"
LEDGER = DEFAULT_OUTPUT_DIR / "vnext-v02-ledger.json"
PREDICTIONS = DEFAULT_OUTPUT_DIR / "vnext-v02-fold-predictions.csv"


def logit(value: float) -> float:
    p = min(max(value, 1e-8), 1.0 - 1e-8)
    return math.log(p / (1.0 - p))


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(value, 30.0), -30.0)))


def orient(row: dict[str, str]) -> tuple[float, float, int]:
    incumbent = float(row["incumbent_prob_winner"])
    feature = float(row["uncertainty_weighted_serve_logit_differential"])
    reverse = int(row["winner_id"]) > int(row["loser_id"])
    return ((1.0 - incumbent, -feature, 0) if reverse else (incumbent, feature, 1))


def fit_theta(rows: list[dict[str, str]], l2_precision: float) -> float:
    theta = 0.0
    for _ in range(80):
        gradient = l2_precision * theta
        information = l2_precision
        for row in rows:
            incumbent, feature, outcome = orient(row)
            probability = sigmoid(logit(incumbent) + theta * feature)
            gradient += (probability - outcome) * feature
            information += probability * (1.0 - probability) * feature * feature
        step = gradient / max(information, 1e-9)
        theta -= step
        if abs(step) < 1e-9:
            break
    return theta


def score(rows: list[dict[str, str]], theta: float, cap: float) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        incumbent, feature, outcome = orient(row)
        delta = max(-cap, min(cap, theta * feature))
        residual_prob = sigmoid(logit(incumbent) + delta)
        winner_incumbent = incumbent if outcome == 1 else 1.0 - incumbent
        winner_residual = residual_prob if outcome == 1 else 1.0 - residual_prob
        out.append({
            **row,
            "outcome": outcome,
            "theta": theta,
            "logit_delta": delta,
            "incumbent_prob_oriented": incumbent,
            "residual_prob_oriented": residual_prob,
            "incumbent_prob_winner_scored": winner_incumbent,
            "residual_prob_winner_scored": winner_residual,
        })
    return out


def metrics(rows: list[dict[str, object]]) -> dict[str, float]:
    if not rows:
        return {"n": 0, "incumbent_log_loss": float("nan"), "residual_log_loss": float("nan"), "delta": float("nan"), "incumbent_brier": float("nan"), "residual_brier": float("nan")}
    incumbent = np.asarray([float(row["incumbent_prob_winner_scored"]) for row in rows], dtype=float)
    residual = np.asarray([float(row["residual_prob_winner_scored"]) for row in rows], dtype=float)
    incumbent_ll = float(np.mean(-np.log(np.clip(incumbent, 1e-8, 1.0))))
    residual_ll = float(np.mean(-np.log(np.clip(residual, 1e-8, 1.0))))
    return {
        "n": len(rows),
        "incumbent_log_loss": incumbent_ll,
        "residual_log_loss": residual_ll,
        "delta": residual_ll - incumbent_ll,
        "incumbent_brier": float(np.mean((1.0 - incumbent) ** 2)),
        "residual_brier": float(np.mean((1.0 - residual) ** 2)),
    }


def bootstrap_ci(rows: list[dict[str, object]], samples: int = 3000, seed: int = 20260712) -> tuple[float, float]:
    clusters: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        dt = date.fromisoformat(str(row["date"]))
        iso = dt.isocalendar()
        clusters[f"{iso.year}-{iso.week:02d}:{row['tournament']}"] .append(row)
    keys = sorted(clusters)
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(samples):
        sampled: list[dict[str, object]] = []
        for _key in keys:
            sampled.extend(clusters[rng.choice(keys)])
        if sampled:
            deltas.append(metrics(sampled)["delta"])
    return float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["date"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=FEATURES)
    parser.add_argument("--registration", type=Path, default=REGISTRATION)
    args = parser.parse_args()

    registration = json.loads(args.registration.read_text(encoding="utf-8"))
    with args.features.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    config = registration["residual_fit"]
    l2_precision = float(config["l2_precision"])
    cap = float(config["max_abs_logit_delta"])
    folds: list[dict[str, object]] = []
    oof_rows: list[dict[str, object]] = []
    for index, fold in enumerate(registration["rolling_folds"], start=1):
        train = [row for row in rows if row["date"] <= fold["train_end"]]
        test = [row for row in rows if fold["test_start"] <= row["date"] <= fold["test_end"]]
        if not train or not test:
            raise RuntimeError(f"Fold {index} lacks train/test rows: train={len(train)} test={len(test)}")
        theta = fit_theta(train, l2_precision)
        scored = score(test, theta, cap)
        result = metrics(scored)
        folds.append({"fold": index, **fold, "train_n": len(train), "theta": theta, **result})
        oof_rows.extend([{**row, "fold": index} for row in scored])

    oof = metrics(oof_rows)
    ci_low, ci_high = bootstrap_ci(oof_rows)
    gates = registration["rung_acceptance"]
    no_bad_fold = all(float(row["delta"]) <= float(gates["single_fold_log_loss_delta_max"]) for row in folds)
    passed = (
        oof["delta"] <= float(gates["mean_oof_log_loss_delta_max"])
        and ci_high < float(gates["bootstrap_ci_high_max"])
        and no_bad_fold
    )
    verdict = "PASS_RUNG_1" if passed else "FAIL_RUNG_1"

    exposed_train = [row for row in rows if row["date"] <= "2024-12-31"]
    exposed_test = [row for row in rows if "2025-01-01" <= row["date"] <= "2025-12-31"]
    exposed_theta = fit_theta(exposed_train, l2_precision)
    exposed_metrics = metrics(score(exposed_test, exposed_theta, cap)) if exposed_test else metrics([])

    ladder_row = {
        "rung": 1,
        "feature_family": "serve_return_differential+uncertainty_gate",
        "status": verdict,
        "folds": len(folds),
        "oof_n": oof["n"],
        "incumbent_log_loss": f"{oof['incumbent_log_loss']:.6f}",
        "residual_log_loss": f"{oof['residual_log_loss']:.6f}",
        "delta_log_loss": f"{oof['delta']:+.6f}",
        "ci_low": f"{ci_low:+.6f}",
        "ci_high": f"{ci_high:+.6f}",
        "worst_fold_delta": f"{max(float(row['delta']) for row in folds):+.6f}",
    }
    write_csv(LADDER, [ladder_row])
    write_csv(PREDICTIONS, oof_rows)
    feature_hash = sha256_file(args.features)
    registration_hash = sha256_file(args.registration)
    ledger = {
        "version": registration["version"],
        "registration_sha256": registration_hash,
        "features_sha256": feature_hash,
        "rung": 1,
        "verdict": verdict,
        "oof_rows": len(oof_rows),
        "exposed_2025_rows": int(exposed_metrics["n"]),
    }
    if LEDGER.exists():
        prior = json.loads(LEDGER.read_text(encoding="utf-8"))
        if prior.get("registration_sha256") != registration_hash or prior.get("features_sha256") != feature_hash:
            raise RuntimeError("v0.2 rung 1 already evaluated with different registered inputs")
    write_json(LEDGER, ledger)

    report_lines = [
        "Tennis vNext v0.2 Anchored Residual - Rolling Folds",
        f"Version: {registration['version']}",
        "Scope: ATP hard, identity-clean incumbent anchor",
        "2025 STATUS: EXPOSED DIAGNOSTIC ONLY - excluded from every decision below",
        "",
        "Registered rung 1",
        "- opponent-adjusted serve/return point differential",
        "- uncertainty gate from static and causal dynamic process precision",
        "- incumbent recovered exactly at theta=0",
        "",
    ]
    for row in folds:
        report_lines.append(
            f"Fold {row['fold']}: train_n={row['train_n']} test_n={row['n']} theta={row['theta']:+.6f} "
            f"inc={row['incumbent_log_loss']:.6f} residual={row['residual_log_loss']:.6f} delta={row['delta']:+.6f}"
        )
    report_lines.extend([
        "",
        f"OOF rows: {oof['n']}",
        f"Incumbent log-loss: {oof['incumbent_log_loss']:.6f}",
        f"Residual log-loss: {oof['residual_log_loss']:.6f}",
        f"Delta log-loss: {oof['delta']:+.6f} (gate <= {float(gates['mean_oof_log_loss_delta_max']):+.4f})",
        f"Tournament-week bootstrap 95% CI: [{ci_low:+.6f}, {ci_high:+.6f}] (upper gate < 0)",
        f"Worst fold delta: {max(float(row['delta']) for row in folds):+.6f} (gate <= {float(gates['single_fold_log_loss_delta_max']):+.4f})",
        "",
        f"VERDICT: {verdict}",
        "Subsequent feature rungs and live shadow wiring remain blocked unless this rung passes all gates.",
    ])
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    EXPOSED.write_text(
        "\n".join([
            "Tennis vNext v0.2 - EXPOSED 2025 Diagnostic",
            "This file cannot be used for model selection, rung acceptance or promotion.",
            f"Rows: {exposed_metrics['n']}",
            f"Incumbent log-loss: {exposed_metrics['incumbent_log_loss']:.6f}",
            f"Residual log-loss: {exposed_metrics['residual_log_loss']:.6f}",
            f"Delta: {exposed_metrics['delta']:+.6f}",
        ]) + "\n",
        encoding="utf-8",
    )
    print("\n".join(report_lines[-10:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
