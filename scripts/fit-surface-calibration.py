#!/usr/bin/env python3
"""
Fit surface-specific favorite-space calibration parameters from backtest results.

This script is intentionally offline and diagnostic-only. It does not touch the
live fair-odds pipeline; it generates artefacts we can review before wiring any
new calibration into production.

Outputs:
  - data/backtest/calibration-params.json
  - data/backtest/calibration-comparison-report.txt
  - data/backtest/clay-calibration-diagnostics.csv

Usage:
  python scripts/fit-surface-calibration.py
  python scripts/fit-surface-calibration.py --train-years 2022 2023 --validation-year 2024 --holdout-year 2025
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - hard dependency
    raise SystemExit("numpy is required for fit-surface-calibration.py") from exc

try:  # Prefer a proper constrained optimizer when available.
    from scipy.optimize import minimize

    HAS_SCIPY = True
except Exception:  # pragma: no cover - scipy optional
    HAS_SCIPY = False


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"

DEFAULT_TRAIN_YEARS = [2022, 2023]
DEFAULT_VALIDATION_YEAR = 2024
DEFAULT_HOLDOUT_YEAR = 2025
DEFAULT_BLEND_GRID_STEP = 0.05
DEFAULT_BLEND_MIN_N = 25
DEFAULT_VALUE_THRESHOLD = 10.0

DEFAULT_BLEND_BY_SERIES = {
    "ATP250": 0.35,
    "ATP500": 0.35,
    "Masters 1000": 1.0,
    "Grand Slam": 0.0,
    "Masters Cup": 0.0,
}


@dataclass
class FavoriteObservation:
    year: int
    surface: str
    series: str
    q_raw: float
    q_pinnacle: float
    favorite_won: int
    raw_p1: float
    pinnacle_p1: float
    actual_p1: int
    pin_odds1: float | None
    pin_odds2: float | None


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _logit(prob: float) -> float:
    p = _clamp(prob, 1e-6, 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    z = _clamp(z, -20.0, 20.0)
    return 1.0 / (1.0 + math.exp(-z))


def _safe_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _surface_key(surface: str | None) -> str:
    txt = (surface or "Unknown").strip()
    if not txt:
        return "Unknown"
    return txt


def _default_files_for_years(years: Iterable[int]) -> list[Path]:
    return [DATA_DIR / f"backtest-results-{year}.csv" for year in years]


def _extract_obs_from_rows(rows: list[dict[str, str]], year: int) -> list[FavoriteObservation]:
    out: list[FavoriteObservation] = []
    for row in rows:
        raw_p1 = _safe_float(row.get("our_prob_raw"))
        if raw_p1 is None:
            raw_p1 = _safe_float(row.get("our_prob"))
        pinnacle_p1 = _safe_float(row.get("pinnacle_prob_novig"))
        if raw_p1 is None or pinnacle_p1 is None:
            continue
        if not (0.0 < raw_p1 < 1.0 and 0.0 < pinnacle_p1 < 1.0):
            continue

        player1 = (row.get("player1") or "").strip()
        player2 = (row.get("player2") or "").strip()
        actual_winner = (row.get("actual_winner") or "").strip()
        if not player1 or not player2 or actual_winner not in {player1, player2}:
            continue

        favorite_is_p1 = raw_p1 >= 0.5
        q_raw = raw_p1 if favorite_is_p1 else (1.0 - raw_p1)
        q_pinn = pinnacle_p1 if favorite_is_p1 else (1.0 - pinnacle_p1)
        actual_p1 = 1 if actual_winner == player1 else 0
        favorite_won = actual_p1 if favorite_is_p1 else (1 - actual_p1)

        out.append(
            FavoriteObservation(
                year=year,
                surface=_surface_key(row.get("surface")),
                series=(row.get("series") or "Unknown").strip() or "Unknown",
                q_raw=q_raw,
                q_pinnacle=q_pinn,
                favorite_won=favorite_won,
                raw_p1=raw_p1,
                pinnacle_p1=pinnacle_p1,
                actual_p1=actual_p1,
                pin_odds1=_safe_float(row.get("pinnacle_odds")),
                pin_odds2=_safe_float(row.get("pinnacle_odds_loser")),
            )
        )
    return out


def _negative_log_likelihood(params: tuple[float, float], obs: list[FavoriteObservation]) -> float:
    a, b = params
    if a < 0.0 or b <= 0.0:
        return float("inf")
    total = 0.0
    for item in obs:
        p_cal = _sigmoid(a + b * _logit(item.q_raw))
        p_cal = _clamp(p_cal, 1e-9, 1.0 - 1e-9)
        actual = float(item.favorite_won)
        total += -actual * math.log(p_cal) - (1.0 - actual) * math.log(1.0 - p_cal)
    return total / max(1, len(obs))


def _grid_fit_platt(obs: list[FavoriteObservation]) -> tuple[float, float, dict[str, object]]:
    # Constrained favorite-space fit:
    # A >= 0 ensures q_cal >= 0.5 when q_raw = 0.5.
    best_a = 0.0
    best_b = 1.0
    best_nll = float("inf")
    for step_a, step_b in ((0.05, 0.05), (0.01, 0.01), (0.002, 0.002)):
        if step_a == 0.05:
            a_lo, a_hi = 0.0, 1.5
            b_lo, b_hi = 0.1, 3.0
        else:
            a_lo, a_hi = max(0.0, best_a - 0.10), best_a + 0.10
            b_lo, b_hi = max(0.1, best_b - 0.20), best_b + 0.20
        a_vals = np.arange(a_lo, a_hi + step_a / 2, step_a)
        b_vals = np.arange(b_lo, b_hi + step_b / 2, step_b)
        for a in a_vals:
            for b in b_vals:
                nll = _negative_log_likelihood((float(a), float(b)), obs)
                if nll < best_nll:
                    best_a = float(a)
                    best_b = float(b)
                    best_nll = float(nll)
    return best_a, best_b, {"backend": "grid", "nll": best_nll}


def fit_platt_constrained(obs: list[FavoriteObservation]) -> tuple[float, float, dict[str, object]]:
    if not obs:
        return 0.0, 1.0, {"backend": "empty", "nll": None}

    if HAS_SCIPY:
        result = minimize(
            lambda x: _negative_log_likelihood((float(x[0]), float(x[1])), obs),
            x0=np.array([0.05, 1.0], dtype=float),
            method="L-BFGS-B",
            bounds=((0.0, 2.0), (0.1, 3.0)),
        )
        a = float(result.x[0])
        b = float(result.x[1])
        meta = {
            "backend": "scipy",
            "success": bool(result.success),
            "message": str(result.message),
            "nll": float(result.fun),
            "iterations": int(getattr(result, "nit", 0)),
        }
    else:
        a, b, meta = _grid_fit_platt(obs)

    # Hard safety rail: favorite must remain favorite after calibration.
    for q in (0.50, 0.51, 0.53, 0.55, 0.60, 0.70, 0.80, 0.90):
        q_cal = _sigmoid(a + b * _logit(q))
        if q_cal < 0.5:
            raise RuntimeError(
                f"Invalid surface calibration fit: q={q:.3f} -> {q_cal:.4f} with A={a:.4f}, B={b:.4f}"
            )
    return a, b, meta


def apply_platt_favorite(q_raw: float, a: float, b: float, blend: float = 1.0) -> float:
    q = _clamp(q_raw, 0.5, 1.0 - 1e-6)
    q_cal = _sigmoid(a + b * _logit(q))
    if q_cal < 0.5:
        raise RuntimeError(f"Favorite-space calibration flipped side: raw={q:.4f} cal={q_cal:.4f}")
    mixed = (1.0 - blend) * q + blend * q_cal
    return _clamp(mixed, 0.5, 1.0 - 1e-6)


def favorite_to_p1(raw_p1: float, q_favorite: float) -> float:
    return q_favorite if raw_p1 >= 0.5 else (1.0 - q_favorite)


def log_loss(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    total = 0.0
    for prob, outcome in zip(probs, outcomes, strict=True):
        p = _clamp(prob, 1e-9, 1.0 - 1e-9)
        y = float(outcome)
        total += -y * math.log(p) - (1.0 - y) * math.log(1.0 - p)
    return total / len(probs)


def brier_score(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((prob - float(outcome)) ** 2 for prob, outcome in zip(probs, outcomes, strict=True)) / len(probs)


def expected_calibration_error(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    if not probs:
        return float("nan")
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for prob, outcome in zip(probs, outcomes, strict=True):
        idx = min(int(prob * n_bins), n_bins - 1)
        bins[idx].append((prob, outcome))
    ece = 0.0
    total_n = len(probs)
    for bucket in bins:
        if not bucket:
            continue
        weight = len(bucket) / total_n
        avg_prob = mean(item[0] for item in bucket)
        avg_actual = mean(item[1] for item in bucket)
        ece += weight * abs(avg_prob - avg_actual)
    return ece


def choose_best_blend(obs: list[FavoriteObservation], a: float, b: float) -> float:
    if not obs:
        return 0.0

    def score(blend: float) -> float:
        probs = [apply_platt_favorite(item.q_raw, a, b, blend) for item in obs]
        outcomes = [item.favorite_won for item in obs]
        return log_loss(probs, outcomes)

    best_blend = 0.0
    best_score = float("inf")
    for step in (DEFAULT_BLEND_GRID_STEP, 0.01):
        if step == DEFAULT_BLEND_GRID_STEP:
            candidates = np.arange(0.0, 1.0 + step / 2, step)
        else:
            lo = max(0.0, best_blend - 0.10)
            hi = min(1.0, best_blend + 0.10)
            candidates = np.arange(lo, hi + step / 2, step)
        for blend in candidates:
            ll = score(float(blend))
            if ll < best_score:
                best_blend = float(blend)
                best_score = float(ll)
    return round(best_blend, 2)


def build_surface_metrics(
    obs: list[FavoriteObservation],
    a: float,
    b: float,
    blend_by_series: dict[str, float],
) -> dict[str, float]:
    raw_probs = [item.q_raw for item in obs]
    cal_probs = [apply_platt_favorite(item.q_raw, a, b, blend_by_series.get(item.series, 0.0)) for item in obs]
    pin_probs = [item.q_pinnacle for item in obs]
    outcomes = [item.favorite_won for item in obs]
    return {
        "n": len(obs),
        "raw_ece": expected_calibration_error(raw_probs, outcomes),
        "cal_ece": expected_calibration_error(cal_probs, outcomes),
        "pinnacle_ece": expected_calibration_error(pin_probs, outcomes),
        "raw_brier": brier_score(raw_probs, outcomes),
        "cal_brier": brier_score(cal_probs, outcomes),
        "pinnacle_brier": brier_score(pin_probs, outcomes),
        "raw_log_loss": log_loss(raw_probs, outcomes),
        "cal_log_loss": log_loss(cal_probs, outcomes),
        "pinnacle_log_loss": log_loss(pin_probs, outcomes),
    }


def build_bin_rows(
    obs: list[FavoriteObservation],
    a: float,
    b: float,
    blend_by_series: dict[str, float],
    generated_utc: str,
    dataset: str,
    surface: str,
    year: int,
    n_bins: int = 10,
) -> list[dict[str, object]]:
    buckets: dict[int, list[tuple[FavoriteObservation, float]]] = {}
    for item in obs:
        calibrated = apply_platt_favorite(item.q_raw, a, b, blend_by_series.get(item.series, 0.0))
        idx = min(int(item.q_raw * n_bins), n_bins - 1)
        buckets.setdefault(idx, []).append((item, calibrated))

    rows: list[dict[str, object]] = []
    total_n = len(obs) or 1
    for idx in sorted(buckets):
        bucket = buckets[idx]
        bin_lo = idx / n_bins
        bin_hi = (idx + 1) / n_bins
        raw_probs = [item.q_raw for item, _ in bucket]
        cal_probs = [cal for _item, cal in bucket]
        pin_probs = [item.q_pinnacle for item, _ in bucket]
        outcomes = [item.favorite_won for item, _ in bucket]
        avg_raw = mean(raw_probs)
        avg_cal = mean(cal_probs)
        avg_pin = mean(pin_probs)
        avg_actual = mean(outcomes)
        weight = len(bucket) / total_n
        rows.append(
            {
                "generated_utc": generated_utc,
                "dataset": dataset,
                "surface": surface,
                "year": year,
                "bin_lo": round(bin_lo, 3),
                "bin_hi": round(bin_hi, 3),
                "n": len(bucket),
                "avg_raw_pred": round(avg_raw, 4),
                "avg_cal_pred": round(avg_cal, 4),
                "avg_pinnacle_novig": round(avg_pin, 4),
                "actual_win_rate": round(avg_actual, 4),
                "raw_ece_contribution": round(weight * abs(avg_raw - avg_actual), 6),
                "cal_ece_contribution": round(weight * abs(avg_cal - avg_actual), 6),
                "pinnacle_ece_contribution": round(weight * abs(avg_pin - avg_actual), 6),
                "raw_brier": round(brier_score(raw_probs, outcomes), 6),
                "cal_brier": round(brier_score(cal_probs, outcomes), 6),
                "pinnacle_brier": round(brier_score(pin_probs, outcomes), 6),
                "log_loss_raw": round(log_loss(raw_probs, outcomes), 6),
                "log_loss_cal": round(log_loss(cal_probs, outcomes), 6),
                "log_loss_pinnacle": round(log_loss(pin_probs, outcomes), 6),
            }
        )
    return rows


def simulate_flat_roi(
    obs: list[FavoriteObservation],
    a: float,
    b: float,
    blend_by_series: dict[str, float],
    value_threshold_pct: float = DEFAULT_VALUE_THRESHOLD,
) -> dict[tuple[str, str], dict[str, float]]:
    grouped: dict[tuple[str, str], dict[str, float]] = {}
    for item in obs:
        if item.pin_odds1 is None or item.pin_odds2 is None:
            continue
        p1_cal = favorite_to_p1(item.raw_p1, apply_platt_favorite(item.q_raw, a, b, blend_by_series.get(item.series, 0.0)))
        p2_cal = 1.0 - p1_cal
        raw_p1 = item.raw_p1
        raw_p2 = 1.0 - raw_p1
        raw_odds1 = 1.0 / _clamp(raw_p1, 1e-6, 1.0 - 1e-6)
        raw_odds2 = 1.0 / _clamp(raw_p2, 1e-6, 1.0 - 1e-6)
        cal_odds1 = 1.0 / _clamp(p1_cal, 1e-6, 1.0 - 1e-6)
        cal_odds2 = 1.0 / _clamp(p2_cal, 1e-6, 1.0 - 1e-6)

        for label, fair_odds1, fair_odds2 in (("raw", raw_odds1, raw_odds2), ("cal", cal_odds1, cal_odds2)):
            value_p1 = (item.pin_odds1 / fair_odds1 - 1.0) * 100.0
            value_p2 = (item.pin_odds2 / fair_odds2 - 1.0) * 100.0
            side = "P1" if value_p1 >= value_p2 else "P2"
            value = value_p1 if side == "P1" else value_p2
            if value < value_threshold_pct:
                continue
            won = item.actual_p1 == 1 if side == "P1" else item.actual_p1 == 0
            odds = item.pin_odds1 if side == "P1" else item.pin_odds2
            pnl = (odds - 1.0) if won else -1.0
            key = (item.surface, item.series)
            bucket = grouped.setdefault(key, {"raw_signals": 0.0, "raw_pnl": 0.0, "cal_signals": 0.0, "cal_pnl": 0.0})
            bucket[f"{label}_signals"] += 1.0
            bucket[f"{label}_pnl"] += pnl
    return grouped


def _format_metric(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.4f}"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    path: Path,
    *,
    generated_utc: str,
    train_years: list[int],
    validation_year: int,
    holdout_year: int,
    params_payload: dict[str, object],
    metrics_by_surface: dict[str, dict[str, dict[str, float]]],
    diagnostics_rows: list[dict[str, object]],
    holdout_roi: dict[tuple[str, str], dict[str, float]],
) -> None:
    lines: list[str] = []
    lines.append("Surface Calibration Validation Report")
    lines.append(f"Generated: {generated_utc}")
    lines.append(f"Train: {', '.join(map(str, train_years))}")
    lines.append(f"Validation: {validation_year}")
    lines.append(f"Holdout: {holdout_year}")
    lines.append("")

    lines.append("=== Fitted parameters ===")
    for surface, info in sorted((params_payload.get("surfaces") or {}).items()):
        lines.append(
            f"{surface}: A={info['A']:.4f} B={info['B']:.4f} "
            f"n_train={info['n_train']} backend={info['fit_backend']}"
        )
        lines.append(
            "  blend_by_series: "
            + ", ".join(f"{series}={blend:.2f}" for series, blend in sorted(info["blend_by_series"].items()))
        )
    lines.append("")

    lines.append("=== Calibration quality ===")
    for surface in sorted(metrics_by_surface):
        lines.append(f"[{surface}]")
        for dataset in ("train", "validation", "holdout"):
            info = metrics_by_surface[surface].get(dataset, {})
            if not info:
                continue
            lines.append(
                f"  {dataset:10s} n={int(info['n']):4d} "
                f"ECE raw/cal/pin={_format_metric(info['raw_ece'])}/{_format_metric(info['cal_ece'])}/{_format_metric(info['pinnacle_ece'])} "
                f"logloss raw/cal/pin={_format_metric(info['raw_log_loss'])}/{_format_metric(info['cal_log_loss'])}/{_format_metric(info['pinnacle_log_loss'])} "
                f"brier raw/cal/pin={_format_metric(info['raw_brier'])}/{_format_metric(info['cal_brier'])}/{_format_metric(info['pinnacle_brier'])}"
            )
        lines.append("")

    lines.append("=== Holdout ROI impact (flat stake, 10% threshold) ===")
    if not holdout_roi:
        lines.append("No qualifying holdout bets.")
    else:
        lines.append("Surface | Series | Raw N / ROI | Cal N / ROI")
        for (surface, series), info in sorted(holdout_roi.items()):
            raw_n = int(info["raw_signals"])
            cal_n = int(info["cal_signals"])
            raw_roi = (info["raw_pnl"] / raw_n) if raw_n else float("nan")
            cal_roi = (info["cal_pnl"] / cal_n) if cal_n else float("nan")
            lines.append(
                f"{surface:8s} | {series:12s} | "
                f"{raw_n:3d} / {_format_metric(raw_roi)} | {cal_n:3d} / {_format_metric(cal_roi)}"
            )
    lines.append("")

    lines.append("=== Clay diagnostics bins ===")
    clay_rows = [row for row in diagnostics_rows if row["surface"] == "Clay" and row["dataset"] in {"validation", "holdout"}]
    if not clay_rows:
        lines.append("No clay diagnostic rows.")
    else:
        lines.append("Dataset Year Bin       N  RawPred CalPred Pinn Pred Actual  RawGap  CalGap")
        for row in clay_rows:
            raw_gap = row["avg_raw_pred"] - row["actual_win_rate"]
            cal_gap = row["avg_cal_pred"] - row["actual_win_rate"]
            lines.append(
                f"{row['dataset']:9s} {row['year']} {row['bin_lo']:.2f}-{row['bin_hi']:.2f} "
                f"{int(row['n']):4d} {row['avg_raw_pred']:.3f}   {row['avg_cal_pred']:.3f}   "
                f"{row['avg_pinnacle_novig']:.3f}   {row['actual_win_rate']:.3f}   {raw_gap:+.3f}  {cal_gap:+.3f}"
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit surface-specific favorite-space calibration parameters.")
    parser.add_argument("--train-years", nargs="+", type=int, default=DEFAULT_TRAIN_YEARS)
    parser.add_argument("--validation-year", type=int, default=DEFAULT_VALIDATION_YEAR)
    parser.add_argument("--holdout-year", type=int, default=DEFAULT_HOLDOUT_YEAR)
    parser.add_argument("--files", nargs="*", help="Optional explicit backtest CSV files to read.")
    parser.add_argument("--out-json", default=str(DATA_DIR / "calibration-params.json"))
    parser.add_argument("--out-report", default=str(DATA_DIR / "calibration-comparison-report.txt"))
    parser.add_argument("--out-diagnostics", default=str(DATA_DIR / "clay-calibration-diagnostics.csv"))
    parser.add_argument("--blend-min-n", type=int, default=DEFAULT_BLEND_MIN_N)
    parser.add_argument("--value-threshold", type=float, default=DEFAULT_VALUE_THRESHOLD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    years = sorted(set(args.train_years + [args.validation_year, args.holdout_year]))
    files = [Path(path) for path in args.files] if args.files else _default_files_for_years(years)
    rows_by_year: dict[int, list[dict[str, str]]] = {}
    for path in files:
        stem = path.stem
        year = next((year for year in years if str(year) in stem), None)
        if year is None:
            raise SystemExit(f"Could not infer year from file name: {path}")
        rows_by_year[year] = _read_csv(path)

    obs_by_year: dict[int, list[FavoriteObservation]] = {
        year: _extract_obs_from_rows(rows_by_year.get(year, []), year) for year in years
    }
    surfaces = sorted({item.surface for year in years for item in obs_by_year.get(year, [])})
    if not surfaces:
        raise SystemExit("No backtest observations were loaded.")

    params_payload: dict[str, object] = {
        "generated_utc": generated_utc,
        "train_years": args.train_years,
        "validation_year": args.validation_year,
        "holdout_year": args.holdout_year,
        "notes": [
            "Favorite-space Platt calibration fitted from backtest results.",
            "A is constrained >= 0 and B > 0 so calibration cannot flip the favorite through 50%.",
            "This artefact is diagnostic only until wired into the live fair-odds model.",
        ],
        "surfaces": {},
    }

    metrics_by_surface: dict[str, dict[str, dict[str, float]]] = {}
    diagnostics_rows: list[dict[str, object]] = []
    holdout_roi: dict[tuple[str, str], dict[str, float]] = {}

    for surface in surfaces:
        train_obs = [item for year in args.train_years for item in obs_by_year.get(year, []) if item.surface == surface]
        validation_obs = [item for item in obs_by_year.get(args.validation_year, []) if item.surface == surface]
        holdout_obs = [item for item in obs_by_year.get(args.holdout_year, []) if item.surface == surface]
        if not train_obs:
            continue

        a, b, fit_meta = fit_platt_constrained(train_obs)
        surface_validation_blend = choose_best_blend(validation_obs, a, b) if validation_obs else 0.0

        seen_series = sorted({item.series for item in train_obs + validation_obs + holdout_obs})
        blend_by_series: dict[str, float] = {}
        for series in seen_series:
            series_validation = [item for item in validation_obs if item.series == series]
            if len(series_validation) >= args.blend_min_n:
                blend_by_series[series] = choose_best_blend(series_validation, a, b)
            else:
                blend_by_series[series] = surface_validation_blend
        for series, fallback_blend in DEFAULT_BLEND_BY_SERIES.items():
            blend_by_series.setdefault(series, fallback_blend if surface != "Clay" else surface_validation_blend)

        metrics_by_surface[surface] = {
            "train": build_surface_metrics(train_obs, a, b, blend_by_series),
            "validation": build_surface_metrics(validation_obs, a, b, blend_by_series),
            "holdout": build_surface_metrics(holdout_obs, a, b, blend_by_series),
        }

        params_payload["surfaces"][surface] = {
            "A": round(a, 6),
            "B": round(b, 6),
            "blend_by_series": {series: round(blend, 2) for series, blend in sorted(blend_by_series.items())},
            "n_train": len(train_obs),
            "train_ece": round(metrics_by_surface[surface]["train"]["cal_ece"], 6),
            "validation_ece": round(metrics_by_surface[surface]["validation"]["cal_ece"], 6),
            "holdout_ece": round(metrics_by_surface[surface]["holdout"]["cal_ece"], 6),
            "fit_backend": fit_meta.get("backend", "unknown"),
            "fit_meta": fit_meta,
        }

        for year, dataset_name in (
            (args.train_years[0], "train"),
            (args.validation_year, "validation"),
            (args.holdout_year, "holdout"),
        ):
            for source_year in (args.train_years if dataset_name == "train" else [year]):
                year_obs = [item for item in obs_by_year.get(source_year, []) if item.surface == surface]
                if not year_obs:
                    continue
                diagnostics_rows.extend(
                    build_bin_rows(
                        year_obs,
                        a,
                        b,
                        blend_by_series,
                        generated_utc,
                        dataset_name,
                        surface,
                        source_year,
                    )
                )

        if holdout_obs:
            holdout_roi.update(simulate_flat_roi(holdout_obs, a, b, blend_by_series, args.value_threshold))

    write_json(Path(args.out_json), params_payload)
    write_csv(Path(args.out_diagnostics), diagnostics_rows)
    write_report(
        Path(args.out_report),
        generated_utc=generated_utc,
        train_years=args.train_years,
        validation_year=args.validation_year,
        holdout_year=args.holdout_year,
        params_payload=params_payload,
        metrics_by_surface=metrics_by_surface,
        diagnostics_rows=diagnostics_rows,
        holdout_roi=holdout_roi,
    )

    print(f"Wrote calibration params: {args.out_json}")
    print(f"Wrote calibration report: {args.out_report}")
    print(f"Wrote diagnostics CSV: {args.out_diagnostics}")
    for surface, info in sorted((params_payload.get('surfaces') or {}).items()):
        print(
            f"  {surface}: A={info['A']:.4f} B={info['B']:.4f} "
            f"train_n={info['n_train']} val_ece={info['validation_ece']:.4f} holdout_ece={info['holdout_ece']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
