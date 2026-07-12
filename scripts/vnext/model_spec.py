"""REGISTERED vNext MVE hierarchical process model.

Version: vnext-mve-0.1
Scope: ATP hard, main-tour/Grand-Slam, 2015-2025.

This is a deterministic MAP implementation of the registered binomial
hierarchy. It intentionally contains no CPI, event, H2H or fatigue terms.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


VERSION = "vnext-mve-0.1"
PROCESS_SPECS = {
    "first_in": ("first_in", "serve_points", False),
    "first_win": ("first_won", "first_in", True),
    "second_win": ("second_won", "second_in", True),
    "double_fault": ("double_faults", "second_attempts", False),
    "ace": ("aces", "first_in", True),
}


def sigmoid(value: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -30.0, 30.0)))


def logit(value: float) -> float:
    p = min(max(float(value), 1e-8), 1.0 - 1e-8)
    return math.log(p / (1.0 - p))


@dataclass
class ProcessModel:
    name: str
    intercept: float
    player_ids: np.ndarray
    server_effects: np.ndarray
    return_effects: np.ndarray | None
    pooling_strength: float
    iterations: int
    max_delta: float

    def __post_init__(self) -> None:
        self._index = {int(player_id): idx for idx, player_id in enumerate(self.player_ids.tolist())}

    def eta(self, server_id: int, returner_id: int, server_delta: float = 0.0, return_delta: float = 0.0) -> float:
        server_idx = self._index.get(int(server_id))
        return_idx = self._index.get(int(returner_id))
        value = self.intercept + server_delta
        if server_idx is not None:
            value += float(self.server_effects[server_idx])
        if self.return_effects is not None:
            value -= return_delta
            if return_idx is not None:
                value -= float(self.return_effects[return_idx])
        return value

    def probability(self, server_id: int, returner_id: int, server_delta: float = 0.0, return_delta: float = 0.0) -> float:
        return float(sigmoid(self.eta(server_id, returner_id, server_delta, return_delta)))

    def to_json(self) -> dict[str, object]:
        return {
            "name": self.name,
            "intercept": self.intercept,
            "pooling_strength": self.pooling_strength,
            "iterations": self.iterations,
            "max_delta": self.max_delta,
            "player_ids": self.player_ids.astype(int).tolist(),
            "server_effects": self.server_effects.tolist(),
            "return_effects": None if self.return_effects is None else self.return_effects.tolist(),
        }

    @classmethod
    def from_json(cls, payload: dict[str, object]) -> "ProcessModel":
        return cls(
            name=str(payload["name"]),
            intercept=float(payload["intercept"]),
            pooling_strength=float(payload["pooling_strength"]),
            iterations=int(payload["iterations"]),
            max_delta=float(payload["max_delta"]),
            player_ids=np.asarray(payload["player_ids"], dtype=np.int64),
            server_effects=np.asarray(payload["server_effects"], dtype=float),
            return_effects=None if payload.get("return_effects") is None else np.asarray(payload["return_effects"], dtype=float),
        )


def fit_process(rows: list[dict[str, object]], name: str, pooling_strength: float, max_iterations: int = 80) -> ProcessModel:
    success_field, total_field, has_return = PROCESS_SPECS[name]
    valid = [row for row in rows if int(row[total_field]) > 0 and 0 <= int(row[success_field]) <= int(row[total_field])]
    if not valid:
        raise ValueError(f"No valid rows for {name}")
    player_ids = np.asarray(sorted({int(row["server_id"]) for row in valid} | {int(row["returner_id"]) for row in valid}), dtype=np.int64)
    index = {int(player_id): idx for idx, player_id in enumerate(player_ids.tolist())}
    server = np.asarray([index[int(row["server_id"])] for row in valid], dtype=np.int64)
    returner = np.asarray([index[int(row["returner_id"])] for row in valid], dtype=np.int64)
    y = np.asarray([int(row[success_field]) for row in valid], dtype=float)
    n = np.asarray([int(row[total_field]) for row in valid], dtype=float)
    total_rate = min(max(float(y.sum() / n.sum()), 1e-5), 1.0 - 1e-5)
    intercept = logit(total_rate)
    server_effects = np.zeros(len(player_ids), dtype=float)
    return_effects = np.zeros(len(player_ids), dtype=float) if has_return else None
    max_delta = float("inf")

    for iteration in range(1, max_iterations + 1):
        eta = intercept + server_effects[server]
        if return_effects is not None:
            eta -= return_effects[returner]
        p = np.asarray(sigmoid(eta), dtype=float)
        variance = np.maximum(n * p * (1.0 - p), 1e-8)
        residual = y - n * p

        intercept_step = float(residual.sum() / variance.sum())
        intercept += float(np.clip(intercept_step, -0.5, 0.5))

        server_gradient = np.bincount(server, weights=residual, minlength=len(player_ids)) - pooling_strength * server_effects
        server_information = np.bincount(server, weights=variance, minlength=len(player_ids)) + pooling_strength
        server_step = server_gradient / np.maximum(server_information, 1e-8)
        server_effects += np.clip(server_step, -0.5, 0.5)
        server_effects = np.clip(server_effects, -3.0, 3.0)

        return_step = np.zeros(1, dtype=float)
        if return_effects is not None:
            return_gradient = np.bincount(returner, weights=-residual, minlength=len(player_ids)) - pooling_strength * return_effects
            return_information = np.bincount(returner, weights=variance, minlength=len(player_ids)) + pooling_strength
            return_step = return_gradient / np.maximum(return_information, 1e-8)
            return_effects += np.clip(return_step, -0.5, 0.5)
            return_effects = np.clip(return_effects, -3.0, 3.0)

        max_delta = max(abs(intercept_step), float(np.max(np.abs(server_step))), float(np.max(np.abs(return_step))))
        if max_delta < 1e-7:
            break

    return ProcessModel(name, intercept, player_ids, server_effects, return_effects, pooling_strength, iteration, max_delta)


class DynamicResiduals:
    def __init__(self, half_life_days: float, prior_precision: float) -> None:
        self.half_life_days = float(half_life_days)
        self.prior_precision = float(prior_precision)
        self._state: dict[tuple[str, str, int], tuple[float, float, int]] = {}

    def _at(self, key: tuple[str, str, int], date_ord: int) -> tuple[float, float]:
        mean, precision, last_date = self._state.get(key, (0.0, self.prior_precision, date_ord))
        elapsed = max(0, date_ord - last_date)
        decay = 0.5 ** (elapsed / max(self.half_life_days, 1.0))
        return mean * decay, self.prior_precision + (precision - self.prior_precision) * decay

    def value(self, process: str, role: str, player_id: int, date_ord: int) -> float:
        return self._at((process, role, int(player_id)), date_ord)[0]

    def update(self, process: str, role: str, player_id: int, date_ord: int, gradient: float, information: float) -> None:
        key = (process, role, int(player_id))
        mean, precision = self._at(key, date_ord)
        new_precision = precision + max(0.0, information)
        new_mean = mean + gradient / max(new_precision, 1e-8)
        self._state[key] = (float(np.clip(new_mean, -1.5, 1.5)), new_precision, date_ord)


def process_probability(model: ProcessModel, state: DynamicResiduals, server_id: int, returner_id: int, date_ord: int) -> float:
    server_delta = state.value(model.name, "server", server_id, date_ord)
    return_delta = state.value(model.name, "return", returner_id, date_ord) if model.return_effects is not None else 0.0
    return model.probability(server_id, returner_id, server_delta, return_delta)


def update_process(model: ProcessModel, state: DynamicResiduals, row: dict[str, object]) -> None:
    success_field, total_field, has_return = PROCESS_SPECS[model.name]
    total = int(row[total_field])
    success = int(row[success_field])
    if total <= 0 or success < 0 or success > total:
        return
    date_ord = int(row["date_ord"])
    server_id = int(row["server_id"])
    returner_id = int(row["returner_id"])
    probability = process_probability(model, state, server_id, returner_id, date_ord)
    gradient = success - total * probability
    information = max(total * probability * (1.0 - probability), 1e-6)
    if has_return:
        state.update(model.name, "server", server_id, date_ord, gradient * 0.5, information * 0.5)
        state.update(model.name, "return", returner_id, date_ord, -gradient * 0.5, information * 0.5)
    else:
        state.update(model.name, "server", server_id, date_ord, gradient, information)


def serve_point_probability(models: dict[str, ProcessModel], state: DynamicResiduals, server_id: int, returner_id: int, date_ord: int) -> tuple[float, dict[str, float]]:
    values = {name: process_probability(model, state, server_id, returner_id, date_ord) for name, model in models.items()}
    point_probability = values["first_in"] * values["first_win"] + (1.0 - values["first_in"]) * (1.0 - values["double_fault"]) * values["second_win"]
    return float(np.clip(point_probability, 0.45, 0.82)), values


def prior_predictive_hold_range(models: dict[str, ProcessModel]) -> dict[str, float]:
    from src.lib.tennis_prob import prob_game

    points: list[float] = []
    sample_ids = models["first_in"].player_ids[: min(500, len(models["first_in"].player_ids))]
    for player_id in sample_ids:
        pid = int(player_id)
        first_in = models["first_in"].probability(pid, pid)
        first_win = models["first_win"].probability(pid, pid)
        second_win = models["second_win"].probability(pid, pid)
        double_fault = models["double_fault"].probability(pid, pid)
        points.append(first_in * first_win + (1.0 - first_in) * (1.0 - double_fault) * second_win)
    if not points:
        return {"min": 0.0, "max": 0.0}
    holds = [prob_game(float(np.clip(point, 0.45, 0.82))) for point in points]
    return {"min": float(np.percentile(holds, 1)), "max": float(np.percentile(holds, 99))}
