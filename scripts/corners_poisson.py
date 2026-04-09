#!/usr/bin/env python3
"""
Shared Poisson helpers for the corners O/U stack.

Imported by:
  scripts/corners-ou-model.py
  scripts/corners-ou-backtest.py
  scripts/matchday-shortlist.py

Do not add pipeline-specific logic here.  This module is pure maths +
calibration I/O only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Optional, Tuple


# ── Core Poisson maths ───────────────────────────────────────────────────────

def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def match_total_prob_over(line: float, lam_h: float, lam_a: float) -> float:
    """P(home_corners + away_corners > line) via independent Poisson convolution."""
    threshold = int(line)
    p_under_or_eq = 0.0
    for i in range(min(threshold + 1, 30)):
        for j in range(min(threshold + 1 - i, 30)):
            p_under_or_eq += poisson_pmf(i, lam_h) * poisson_pmf(j, lam_a)
    return 1.0 - p_under_or_eq


def fair_decimal(prob: float) -> float:
    if prob <= 0:
        return 999.0
    if prob >= 1:
        return 1.001
    return round(1.0 / prob, 3)


# ── Platt calibration ────────────────────────────────────────────────────────

def _logit(p: float) -> float:
    p = max(1e-7, min(1.0 - 1e-7, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def calibrate_prob(p_raw: float, a: float, b: float) -> float:
    """Apply Platt scaling: p_cal = sigmoid(a * logit(p_raw) + b)."""
    return _sigmoid(a * _logit(p_raw) + b)


def load_calibration_params(
    path: Path,
) -> Optional[Dict[str, Tuple[float, float]]]:
    """
    Load per-line Platt (a, b) from JSON written by corners-fit-calibration.py.
    Returns None (with a warning) if the file is missing; callers fall back to
    raw Poisson probabilities without error.
    """
    if not path.exists():
        print(f"  [calibration] params not found at {path.name} — using raw probabilities")
        print("  Run: python scripts/corners-fit-calibration.py")
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    result: Dict[str, Tuple[float, float]] = {}
    for line_key, ab in data.get("lines", {}).items():
        result[line_key] = (float(ab["a"]), float(ab["b"]))
    fit_before = data.get("fit_before", "?")
    print(
        f"  [calibration] Platt params for lines {sorted(result)}  "
        f"(fit_before={fit_before})"
    )
    return result
