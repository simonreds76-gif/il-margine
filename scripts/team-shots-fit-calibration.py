#!/usr/bin/env python3
"""
Fit Platt scaling calibration on held-out historical team-shots predictions.

The raw Poisson model produces S-curve miscalibrated probabilities:
  - Low-probability predictions are too low (under-estimates)
  - High-probability predictions are too high (over-estimates)

This script fits a per-line Platt transform:
  p_calibrated = sigmoid(a * logit(p_raw) + b)
on a fit split (default: before 2022-08-01) and evaluates on a held-out
validation split (2022-08-01 onward). The fitted parameters are written to
JSON and loaded at runtime by team-shots-compare.py and the shadow tracker.

Usage:
  python scripts/team-shots-fit-calibration.py
  python scripts/team-shots-fit-calibration.py --fit-before 2023-08-01
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PREDICTIONS = ROOT / "data" / "team-shots" / "team-shots-predictions.csv"
DEFAULT_PARAMS_OUT  = ROOT / "data" / "team-shots" / "team-shots-calibration-params.json"
DEFAULT_DIAG_OUT    = ROOT / "data" / "team-shots" / "team-shots-calibration-diagnostics.txt"

DEFAULT_FIT_BEFORE = "2026-01-01"

LINES = [8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 19.5, 20.5]

PLATT_LR    = 0.3
PLATT_STEPS = 800
PLATT_L2    = 1e-4

RELIABILITY_BINS: List[Tuple[float, float]] = [
    (0.00, 0.25), (0.25, 0.40), (0.40, 0.50),
    (0.50, 0.60), (0.60, 0.75), (0.75, 1.01),
]


# ── Numerics ─────────────────────────────────────────────────────────

def _pf(v: object, d: float = 0.0) -> float:
    try:
        return float(str(v or "").strip() or d)
    except ValueError:
        return d


def _logit(p: float) -> float:
    p = max(1e-7, min(1.0 - 1e-7, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


# ── Platt fitting ────────────────────────────────────────────────────

def platt_fit(
    p_raws: List[float],
    actuals: List[int],
    lr: float = PLATT_LR,
    steps: int = PLATT_STEPS,
    l2: float = PLATT_L2,
) -> Tuple[float, float]:
    """
    Gradient ascent on binary log-likelihood with L2 regularisation toward
    the identity transform (a=1, b=0).

    Returns (a, b) for: p_cal = sigmoid(a * logit(p_raw) + b).
    """
    xs = [_logit(p) for p in p_raws]
    a, b = 1.0, 0.0
    n = len(xs)
    for _ in range(steps):
        da = db = 0.0
        for xi, yi in zip(xs, actuals):
            err = float(yi) - _sigmoid(a * xi + b)
            da += err * xi
            db += err
        a += lr * (da / n - l2 * (a - 1.0))
        b += lr * (db / n - l2 * b)
    return a, b


def platt_apply(p_raw: float, a: float, b: float) -> float:
    return _sigmoid(a * _logit(p_raw) + b)


# ── Metrics ──────────────────────────────────────────────────────────

def brier_score(probs: List[float], actuals: List[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, actuals)) / len(probs)


def reliability_table(
    probs: List[float],
    actuals: List[int],
) -> List[Tuple[float, float, int, float, float]]:
    rows: List[Tuple[float, float, int, float, float]] = []
    for lo, hi in RELIABILITY_BINS:
        idx = [i for i, p in enumerate(probs) if lo <= p < hi]
        if not idx:
            continue
        n = len(idx)
        pred_mean   = sum(probs[i] for i in idx) / n
        actual_rate = sum(actuals[i] for i in idx) / n
        rows.append((lo, hi, n, pred_mean, actual_rate))
    return rows


def ece(table: List[Tuple[float, float, int, float, float]]) -> float:
    total_n = sum(r[2] for r in table)
    if total_n == 0:
        return 0.0
    return sum(r[2] * abs(r[3] - r[4]) for r in table) / total_n


# ── Data loading ─────────────────────────────────────────────────────

def load_and_split(
    path: Path,
    fit_before: date,
) -> Tuple[List[dict], List[dict]]:
    """
    Load predictions CSV and split into fit / validation by date.
    Rows without actual_shots (upcoming fixtures) are excluded.
    Each row in team-shots-predictions.csv is per-team, so actual_shots is
    the team's shot count (home_shots or away_shots depending on venue).
    """
    fit: List[dict] = []
    val: List[dict] = []
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            d_str = (row.get("date") or "").strip()
            try:
                d = date.fromisoformat(d_str)
            except ValueError:
                continue
            # Skip rows without a recorded outcome
            actual = _pf(row.get("actual_shots", ""))
            if actual <= 0:
                continue
            (fit if d < fit_before else val).append(row)
    return fit, val


def _extract_line_data(
    rows: List[dict], line: float,
) -> Tuple[List[float], List[int]]:
    key = f"p_over_{line}"
    probs: List[float] = []
    labels: List[int]  = []
    for r in rows:
        p = _pf(r.get(key))
        if p <= 0.0 or p >= 1.0:
            continue
        actual = _pf(r.get("actual_shots"))
        probs.append(p)
        labels.append(1 if actual > line else 0)
    return probs, labels


# ── Report helpers ───────────────────────────────────────────────────

def _append_split_section(
    out: List[str],
    label: str,
    raw_probs: List[float],
    cal_probs: List[float],
    actuals: List[int],
) -> None:
    n = len(raw_probs)
    bs_raw = brier_score(raw_probs, actuals)
    bs_cal = brier_score(cal_probs, actuals)
    tbl_raw = reliability_table(raw_probs, actuals)
    tbl_cal = reliability_table(cal_probs, actuals)
    ece_raw = ece(tbl_raw)
    ece_cal = ece(tbl_cal)

    out.append(f"  {label} (n={n}):")
    out.append(f"    Brier : raw={bs_raw:.5f}  cal={bs_cal:.5f}  "
               f"delta={bs_cal - bs_raw:+.5f}")
    out.append(f"    ECE   : raw={ece_raw:.5f}  cal={ece_cal:.5f}  "
               f"delta={ece_cal - ece_raw:+.5f}")
    out.append("")
    out.append(
        f"    {'Bin':>14s}  {'n':>5s}  "
        f"{'raw_pred':>8s}  {'cal_pred':>8s}  "
        f"{'actual':>8s}  {'raw_err':>8s}  {'cal_err':>8s}"
    )
    cal_by_bin = {(r[0], r[1]): r for r in tbl_cal}
    for lo, hi, n_b, pred_raw, actual_r in tbl_raw:
        cr = cal_by_bin.get((lo, hi))
        pred_cal = cr[3] if cr else float("nan")
        out.append(
            f"    [{lo:.2f}, {hi:.2f})  "
            f"{n_b:>5d}  "
            f"{pred_raw:>8.3f}  "
            f"{pred_cal:>8.3f}  "
            f"{actual_r:>8.3f}  "
            f"{pred_raw - actual_r:>+8.3f}  "
            f"{pred_cal - actual_r:>+8.3f}"
        )
    out.append("")


# ── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fit per-line Platt calibration for team shots O/U model"
    )
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--params-out",  type=Path, default=DEFAULT_PARAMS_OUT)
    parser.add_argument("--diag-out",    type=Path, default=DEFAULT_DIAG_OUT)
    parser.add_argument(
        "--fit-before", default=DEFAULT_FIT_BEFORE,
        help="Cutoff date (ISO, exclusive) - rows before this date form the fit set "
             f"(default: {DEFAULT_FIT_BEFORE})",
    )
    args = parser.parse_args()

    cutoff = date.fromisoformat(args.fit_before)
    fit_rows, val_rows = load_and_split(args.predictions, cutoff)

    print(f"Predictions   : {args.predictions}")
    print(f"  Fit  set  (<{cutoff}) : {len(fit_rows)} rows")
    print(f"  Val  set  (>={cutoff}) : {len(val_rows)} rows")

    if len(fit_rows) < 200:
        print(
            "ERROR: fewer than 200 fit rows - run team-shots-model.py first "
            "or widen --fit-before"
        )
        return

    params: Dict[str, Dict[str, float]] = {}
    diag: List[str] = [
        "=" * 72,
        "  TEAM SHOTS O/U - PLATT CALIBRATION DIAGNOSTICS",
        "=" * 72,
        f"  Source     : {args.predictions}",
        f"  Fit  split : before {cutoff}  (n={len(fit_rows)})",
        f"  Val  split : from   {cutoff}  (n={len(val_rows)})",
        "",
    ]

    for line in LINES:
        fit_p, fit_y = _extract_line_data(fit_rows, line)
        if len(fit_p) < 100:
            diag.append(
                f"  Line {line}: skipped - not enough data ({len(fit_p)} rows)"
            )
            continue

        a, b = platt_fit(fit_p, fit_y)
        params[str(line)] = {"a": round(a, 6), "b": round(b, 6)}

        fit_p_cal = [platt_apply(p, a, b) for p in fit_p]

        diag += [
            f"  Line {line}  -  Platt: a={a:.4f}  b={b:+.4f}",
            "",
        ]
        _append_split_section(diag, "Fit set", fit_p, fit_p_cal, fit_y)

        if val_rows:
            val_p, val_y = _extract_line_data(val_rows, line)
            val_p_cal = [platt_apply(p, a, b) for p in val_p]
            _append_split_section(diag, "Validation set", val_p, val_p_cal, val_y)

        diag += ["-" * 72, ""]

    diag.append("=" * 72)
    diag_text = "\n".join(diag)

    args.params_out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.params_out, "w", encoding="utf-8") as fh:
        json.dump(
            {"fit_before": args.fit_before, "method": "platt", "lines": params},
            fh, indent=2,
        )
    print(f"Params written   -> {args.params_out}")

    with open(args.diag_out, "w", encoding="utf-8") as fh:
        fh.write(diag_text + "\n")
    print(f"Diagnostics      -> {args.diag_out}")

    print("\n" + diag_text)


if __name__ == "__main__":
    main()
