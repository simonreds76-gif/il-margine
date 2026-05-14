"""Metrics for the clay ML v2 research scripts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np


EPS = 1e-6


@dataclass(frozen=True)
class MetricSummary:
    n: int
    log_loss: float
    brier: float
    ece: float | None
    ece_n: int


def clip_probs(probs: Iterable[float]) -> np.ndarray:
    return np.clip(np.asarray(list(probs), dtype=float), EPS, 1.0 - EPS)


def binary_log_loss(labels: Iterable[int], probs: Iterable[float]) -> float:
    y = np.asarray(list(labels), dtype=float)
    p = clip_probs(probs)
    return float(-(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)).mean())


def brier_score(labels: Iterable[int], probs: Iterable[float]) -> float:
    y = np.asarray(list(labels), dtype=float)
    p = clip_probs(probs)
    return float(np.mean((p - y) ** 2))


def expected_calibration_error(
    labels: Iterable[int],
    probs: Iterable[float],
    *,
    bins: int = 10,
    min_bin_n: int = 30,
) -> tuple[float | None, int, list[dict[str, float | int]]]:
    y = np.asarray(list(labels), dtype=float)
    p = clip_probs(probs)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, float | int]] = []
    weighted = 0.0
    included = 0
    for idx in range(bins):
        lo = edges[idx]
        hi = edges[idx + 1]
        if idx == bins - 1:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        n = int(mask.sum())
        if n:
            avg_prob = float(p[mask].mean())
            observed = float(y[mask].mean())
            abs_error = abs(avg_prob - observed)
        else:
            avg_prob = math.nan
            observed = math.nan
            abs_error = math.nan
        include = n >= min_bin_n
        if include:
            weighted += n * abs_error
            included += n
        rows.append(
            {
                "bin": idx + 1,
                "lo": float(lo),
                "hi": float(hi),
                "n": n,
                "avg_prob": avg_prob,
                "observed": observed,
                "abs_error": abs_error,
                "included": int(include),
            }
        )
    if not included:
        return None, 0, rows
    return float(weighted / included), included, rows


def metric_summary(labels: Iterable[int], probs: Iterable[float]) -> MetricSummary:
    labels_list = list(labels)
    probs_list = list(probs)
    ece, ece_n, _ = expected_calibration_error(labels_list, probs_list)
    return MetricSummary(
        n=len(labels_list),
        log_loss=binary_log_loss(labels_list, probs_list),
        brier=brier_score(labels_list, probs_list),
        ece=ece,
        ece_n=ece_n,
    )


def roi_by_edge_band(
    labels: Iterable[int],
    model_probs: Iterable[float],
    market_probs: Iterable[float],
    odds_a: Iterable[float],
    odds_b: Iterable[float],
) -> list[dict[str, float | int | str]]:
    y = np.asarray(list(labels), dtype=int)
    m = clip_probs(model_probs)
    pin = clip_probs(market_probs)
    oa = np.asarray(list(odds_a), dtype=float)
    ob = np.asarray(list(odds_b), dtype=float)
    bands = [(3, 6), (6, 8), (8, 10), (10, 12), (12, 100)]
    rows: list[dict[str, float | int | str]] = []
    edge = np.abs(m - pin) * 100.0
    bet_a = m > pin
    pnl = np.where(bet_a, np.where(y == 1, oa - 1.0, -1.0), np.where(y == 0, ob - 1.0, -1.0))
    wins = np.where(bet_a, y == 1, y == 0)
    for lo, hi in bands:
        if hi == 100:
            mask = edge >= lo
            label = f"{lo}+"
        else:
            mask = (edge >= lo) & (edge < hi)
            label = f"{lo}-{hi}"
        n = int(mask.sum())
        rows.append(
            {
                "edge_band": label,
                "n": n,
                "wins": int(wins[mask].sum()) if n else 0,
                "pnl": float(pnl[mask].sum()) if n else 0.0,
                "roi": float(pnl[mask].mean()) if n else 0.0,
            }
        )
    return rows
