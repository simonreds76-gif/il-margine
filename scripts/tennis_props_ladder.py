#!/usr/bin/env python3
"""Fit an NB2 count mean from a one-sided bookmaker Over ladder.

Under a common multiplicative margin, consecutive implied-probability ratios
remove that margin. The fitted mean is therefore a market-shape benchmark, not
an assumed no-vig probability from a single one-sided quote.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from statistics import median
from typing import Iterable

from tennis_props_model import count_line_probabilities


@dataclass(frozen=True)
class LadderFit:
    mu_mkt: float | None
    overround: float | None
    shape_rmse: float | None
    n_points: int
    dropped_ceiling: int
    accepted: bool
    reject_reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def over_probability(line: float, mean: float, alpha: float) -> float:
    over, _under, _push = count_line_probabilities(
        line,
        mean,
        distribution="negative_binomial",
        alpha=alpha,
        tour="ATP",
        market="aces",
    )
    return max(1e-12, min(1.0 - 1e-12, over))


def clean_ladder(points: Iterable[tuple[float, float]]) -> tuple[list[tuple[float, float]], int]:
    by_line: dict[float, float] = {}
    dropped_ceiling = 0
    for raw_line, raw_odds in points:
        try:
            line = float(raw_line)
            odds = float(raw_odds)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(line) or not math.isfinite(odds):
            continue
        if odds >= 26.0:
            dropped_ceiling += 1
            continue
        if odds <= 1.01:
            continue
        by_line[round(line, 3)] = odds
    return sorted(by_line.items()), dropped_ceiling


def _objective(log_mean: float, ladder: list[tuple[float, float]], alpha: float) -> float:
    mean = math.exp(log_mean)
    errors: list[float] = []
    for (left_line, left_odds), (right_line, right_odds) in zip(ladder, ladder[1:]):
        observed_ratio = (1.0 / right_odds) / (1.0 / left_odds)
        model_ratio = (
            over_probability(right_line, mean, alpha)
            / over_probability(left_line, mean, alpha)
        )
        if observed_ratio <= 0 or model_ratio <= 0:
            return math.inf
        errors.append((math.log(observed_ratio) - math.log(model_ratio)) ** 2)
    return sum(errors) / len(errors) if errors else math.inf


def _golden_section(
    objective,
    left: float,
    right: float,
    iterations: int = 80,
) -> float:
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    x1 = right - ratio * (right - left)
    x2 = left + ratio * (right - left)
    f1 = objective(x1)
    f2 = objective(x2)
    for _ in range(iterations):
        if f1 <= f2:
            right, x2, f2 = x2, x1, f1
            x1 = right - ratio * (right - left)
            f1 = objective(x1)
        else:
            left, x1, f1 = x1, x2, f2
            x2 = left + ratio * (right - left)
            f2 = objective(x2)
    return (left + right) / 2.0


def fit_market_ladder(
    points: Iterable[tuple[float, float]],
    *,
    alpha: float,
    max_rmse: float = 0.25,
    min_overround: float = 1.0,
    max_overround: float = 2.0,
) -> LadderFit:
    ladder, dropped_ceiling = clean_ladder(points)
    if len(ladder) < 3:
        return LadderFit(None, None, None, len(ladder), dropped_ceiling, False, "INSUFFICIENT_POINTS")
    implied = [1.0 / odds for _line, odds in ladder]
    if any(right >= left for left, right in zip(implied, implied[1:])):
        return LadderFit(None, None, None, len(ladder), dropped_ceiling, False, "NON_MONOTONE_LADDER")
    if not math.isfinite(alpha) or alpha <= 0:
        return LadderFit(None, None, None, len(ladder), dropped_ceiling, False, "INVALID_ALPHA")

    lower = math.log(0.05)
    upper = math.log(max(60.0, ladder[-1][0] * 2.5 + 10.0))
    grid = [lower + (upper - lower) * index / 240.0 for index in range(241)]
    scores = [_objective(value, ladder, alpha) for value in grid]
    best_index = min(range(len(grid)), key=scores.__getitem__)
    bracket_left = grid[max(0, best_index - 1)]
    bracket_right = grid[min(len(grid) - 1, best_index + 1)]
    best_log_mean = _golden_section(
        lambda value: _objective(value, ladder, alpha),
        bracket_left,
        bracket_right,
    )
    mean = math.exp(best_log_mean)
    rmse = math.sqrt(_objective(best_log_mean, ladder, alpha))
    margins = [
        (1.0 / odds) / over_probability(line, mean, alpha)
        for line, odds in ladder
    ]
    overround = median(margins)

    if rmse > max_rmse:
        reason = "SHAPE_RMSE_HIGH"
    elif not min_overround <= overround <= max_overround:
        reason = "OVERROUND_OUT_OF_RANGE"
    else:
        reason = ""
    return LadderFit(
        mu_mkt=mean,
        overround=overround,
        shape_rmse=rmse,
        n_points=len(ladder),
        dropped_ceiling=dropped_ceiling,
        accepted=not reason,
        reject_reason=reason,
    )


def canonical_quote(points: Iterable[tuple[float, float]]) -> tuple[float, float] | None:
    ladder, _dropped = clean_ladder(points)
    if not ladder:
        return None
    return min(ladder, key=lambda item: (abs(item[1] - 2.0), item[0]))
