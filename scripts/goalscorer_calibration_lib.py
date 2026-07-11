#!/usr/bin/env python3
"""Small serializable probability calibrators for the goalscorer model."""

from __future__ import annotations

import bisect
import math
from typing import Iterable

import numpy as np
from scipy.optimize import minimize


EPS = 1e-6


def clip_probability(value: float) -> float:
    return min(1.0 - EPS, max(EPS, float(value)))


def sigmoid(value: float) -> float:
    if value >= 0:
        exp_neg = math.exp(-value)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(value)
    return exp_pos / (1.0 + exp_pos)


def logit(value: float) -> float:
    value = clip_probability(value)
    return math.log(value / (1.0 - value))


def _log_loss(labels: np.ndarray, predictions: np.ndarray) -> float:
    predictions = np.clip(predictions, EPS, 1.0 - EPS)
    return float(-np.mean(labels * np.log(predictions) + (1.0 - labels) * np.log(1.0 - predictions)))


def fit_platt(probabilities: Iterable[float], labels: Iterable[int]) -> dict:
    probs = np.asarray([clip_probability(value) for value in probabilities], dtype=float)
    y = np.asarray(list(labels), dtype=float)
    x = np.asarray([logit(value) for value in probs], dtype=float)

    def objective(params: np.ndarray) -> float:
        predictions = 1.0 / (1.0 + np.exp(-np.clip(params[0] + params[1] * x, -35.0, 35.0)))
        return _log_loss(y, predictions)

    result = minimize(objective, np.asarray([0.0, 1.0]), method="BFGS")
    if not result.success and not np.isfinite(result.fun):
        raise RuntimeError(f"Platt calibration failed: {result.message}")
    return {"kind": "platt", "intercept": float(result.x[0]), "slope": float(result.x[1])}


def fit_beta(probabilities: Iterable[float], labels: Iterable[int]) -> dict:
    probs = np.asarray([clip_probability(value) for value in probabilities], dtype=float)
    y = np.asarray(list(labels), dtype=float)
    log_p = np.log(probs)
    log_q = np.log(1.0 - probs)

    def objective(params: np.ndarray) -> float:
        linear = params[0] + params[1] * log_p + params[2] * log_q
        predictions = 1.0 / (1.0 + np.exp(-np.clip(linear, -35.0, 35.0)))
        return _log_loss(y, predictions)

    result = minimize(objective, np.asarray([0.0, 1.0, -1.0]), method="BFGS")
    if not result.success and not np.isfinite(result.fun):
        raise RuntimeError(f"Beta calibration failed: {result.message}")
    return {
        "kind": "beta",
        "intercept": float(result.x[0]),
        "log_p_coefficient": float(result.x[1]),
        "log_one_minus_p_coefficient": float(result.x[2]),
    }


def fit_isotonic(probabilities: Iterable[float], labels: Iterable[int]) -> dict:
    pairs = sorted((clip_probability(probability), int(label)) for probability, label in zip(probabilities, labels))
    if not pairs:
        raise ValueError("Cannot fit isotonic calibration without rows")

    grouped: list[dict] = []
    for probability, label in pairs:
        if grouped and grouped[-1]["max_x"] == probability:
            grouped[-1]["weight"] += 1.0
            grouped[-1]["positive"] += label
            grouped[-1]["value"] = grouped[-1]["positive"] / grouped[-1]["weight"]
        else:
            grouped.append(
                {
                    "min_x": probability,
                    "max_x": probability,
                    "weight": 1.0,
                    "positive": float(label),
                    "value": float(label),
                }
            )

    blocks: list[dict] = []
    for group in grouped:
        blocks.append(dict(group))
        while len(blocks) >= 2 and blocks[-2]["value"] > blocks[-1]["value"]:
            right = blocks.pop()
            left = blocks.pop()
            weight = left["weight"] + right["weight"]
            positive = left["positive"] + right["positive"]
            blocks.append(
                {
                    "min_x": left["min_x"],
                    "max_x": right["max_x"],
                    "weight": weight,
                    "positive": positive,
                    "value": positive / weight,
                }
            )

    return {
        "kind": "isotonic",
        "blocks": [
            {"max_x": float(block["max_x"]), "value": float(min(0.85, max(0.01, block["value"])))}
            for block in blocks
        ],
    }


def apply_calibrator(calibrator: dict, probability: float) -> float:
    probability = clip_probability(probability)
    kind = calibrator.get("kind")
    if kind == "platt":
        return clip_probability(sigmoid(float(calibrator["intercept"]) + float(calibrator["slope"]) * logit(probability)))
    if kind == "beta":
        linear = (
            float(calibrator["intercept"])
            + float(calibrator["log_p_coefficient"]) * math.log(probability)
            + float(calibrator["log_one_minus_p_coefficient"]) * math.log(1.0 - probability)
        )
        return clip_probability(sigmoid(linear))
    if kind == "isotonic":
        blocks = calibrator.get("blocks") or []
        if not blocks:
            raise ValueError("Isotonic calibrator has no blocks")
        maxima = [float(block["max_x"]) for block in blocks]
        index = min(bisect.bisect_left(maxima, probability), len(blocks) - 1)
        return clip_probability(float(blocks[index]["value"]))
    raise ValueError(f"Unsupported calibrator kind: {kind}")


def fit_calibrator(kind: str, probabilities: Iterable[float], labels: Iterable[int]) -> dict:
    probabilities = list(probabilities)
    labels = list(labels)
    if kind == "platt":
        return fit_platt(probabilities, labels)
    if kind == "beta":
        return fit_beta(probabilities, labels)
    if kind == "isotonic":
        return fit_isotonic(probabilities, labels)
    raise ValueError(f"Unsupported calibrator kind: {kind}")
