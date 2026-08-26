#!/usr/bin/env python3
"""Registered count-only backtest for Goalkeeper Saves v1.

This script measures count and probability accuracy. It deliberately does not
create selections, P/L, ROI, CLV, public output, or live routing because the
repository has no historical Bet365 goalkeeper-saves price archive.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean, pvariance
from typing import Any, Iterable, Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_counts import prob_over, total_probs  # noqa: E402
from football_market import brier, log_loss  # noqa: E402
from model_experiment_integrity import assert_variable_columns, sha256_file  # noqa: E402


DEFAULT_HISTORICAL = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "goalkeeper-saves"
VALIDATION_SEASONS = ("2024-2025", "2025-2026")
LINES = (1.5, 2.5, 3.5, 4.5, 5.5)
WINDOW = 20
DECAY = 0.93
MIN_HISTORY = 6
RIDGE = 0.01
MIN_MEAN = 0.1
MAX_MEAN = 12.0
ALPHA_BOUNDS = (1.0 / 500.0, 0.8)

FEATURE_NAMES = (
    "opponent_sot_for_ema20_venue",
    "team_sot_against_ema20_venue",
    "opponent_shots_for_ema20_venue",
    "team_shots_against_ema20_venue",
    "market_strength_gap",
    "opponent_xg_for_ema20",
    "team_xga_ema20",
    "opponent_xg_per_shot_ema20",
    "team_saves_ema20",
)
VARIANTS = {
    "NB2_CORE": (0, 1),
    "NB2_CORE_SHOTS": (0, 1, 2, 3),
    "NB2_MARKET": (0, 1, 2, 3, 4),
    "NB2_XG": (0, 1, 2, 3, 4, 5, 6, 7),
    "NB2_FULL": tuple(range(len(FEATURE_NAMES))),
}


@dataclass(frozen=True)
class TargetObservation:
    match_date: date
    season: str
    league: str
    team: str
    opponent: str
    venue: str
    saves: int


@dataclass(frozen=True)
class Sample:
    match_date: date
    season: str
    league: str
    team: str
    team_key: str
    opponent: str
    venue: str
    actual: int
    features: tuple[float, ...]


@dataclass
class SaveState:
    values: list[float] = field(default_factory=list)

    def add(self, value: float) -> None:
        self.values.append(float(value))
        if len(self.values) > WINDOW:
            del self.values[0]

    @property
    def matches(self) -> int:
        return len(self.values)

    def ema(self) -> float:
        weights = [DECAY ** (len(self.values) - 1 - index) for index in range(len(self.values))]
        return sum(value * weight for value, weight in zip(self.values, weights)) / sum(weights)


@dataclass(frozen=True)
class FittedModel:
    name: str
    feature_indices: tuple[int, ...]
    beta: tuple[float, ...]
    alpha: float
    centers: tuple[float, ...]
    scales: tuple[float, ...]
    league_venue_means: dict[str, float]
    fallback_mean: float

    def predict(self, sample: Sample) -> float:
        values = [sample.features[index] for index in self.feature_indices]
        standardized = [
            (value - center) / scale
            for value, center, scale in zip(values, self.centers, self.scales)
        ]
        linear = self.beta[0] + sum(beta * value for beta, value in zip(self.beta[1:], standardized))
        offset = self.league_venue_means.get(f"{sample.league}|{sample.venue}", self.fallback_mean)
        return max(MIN_MEAN, min(MAX_MEAN, offset * math.exp(linear)))


@dataclass(frozen=True)
class IncumbentModel:
    weight: float
    alpha: float
    league_venue_means: dict[str, float]
    fallback_mean: float

    def predict(self, sample: Sample) -> float:
        baseline = self.league_venue_means.get(f"{sample.league}|{sample.venue}", self.fallback_mean)
        save_ema = sample.features[8]
        return max(MIN_MEAN, min(MAX_MEAN, ((1.0 - self.weight) * baseline) + (self.weight * save_ema)))


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def parse_day(value: Any) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def reconstruct_targets(rows: Iterable[dict[str, str]]) -> tuple[list[TargetObservation], dict[str, Any]]:
    observations: list[TargetObservation] = []
    missing_fixtures = 0
    anomalous_fixtures = 0
    negative_rows = 0
    fixture_count = 0
    for row in rows:
        fixture_count += 1
        match_date = parse_day(row.get("Date") or row.get("date"))
        values = {
            "home_sot": parse_float(row.get("HST") or row.get("home_sot")),
            "away_sot": parse_float(row.get("AST") or row.get("away_sot")),
            "home_goals": parse_float(row.get("FTHG") or row.get("home_goals")),
            "away_goals": parse_float(row.get("FTAG") or row.get("away_goals")),
        }
        if match_date is None or any(value is None for value in values.values()):
            missing_fixtures += 1
            continue
        home_saves = int(round(float(values["away_sot"]) - float(values["away_goals"])))
        away_saves = int(round(float(values["home_sot"]) - float(values["home_goals"])))
        negative_rows += int(home_saves < 0) + int(away_saves < 0)
        if home_saves < 0 or away_saves < 0:
            anomalous_fixtures += 1
            continue
        season = str(row.get("season") or "").strip()
        league = str(row.get("league") or "").strip()
        home = str(row.get("HomeTeam") or row.get("home_team") or "").strip()
        away = str(row.get("AwayTeam") or row.get("away_team") or "").strip()
        observations.extend(
            (
                TargetObservation(match_date, season, league, home, away, "home", home_saves),
                TargetObservation(match_date, season, league, away, home, "away", away_saves),
            )
        )
    values = [row.saves for row in observations]
    average = mean(values)
    variance = pvariance(values)
    by_league: dict[str, dict[str, float]] = {}
    for league in sorted({row.league for row in observations}):
        league_values = [row.saves for row in observations if row.league == league]
        league_mean = mean(league_values)
        league_variance = pvariance(league_values)
        by_league[league] = {
            "n": len(league_values),
            "mean": league_mean,
            "variance_to_mean": league_variance / league_mean if league_mean else 0.0,
        }
    audit = {
        "fixtures": fixture_count,
        "missing_fixtures": missing_fixtures,
        "anomalous_fixtures": anomalous_fixtures,
        "negative_rows": negative_rows,
        "valid_team_observations": len(observations),
        "mean": average,
        "variance": variance,
        "variance_to_mean": variance / average if average else 0.0,
        "zero_rate": sum(value == 0 for value in values) / len(values),
        "by_league": by_league,
    }
    return observations, audit


def preferred(row: dict[str, str], specific: str, generic: str) -> float | None:
    return parse_float(row.get(specific)) or parse_float(row.get(generic))


def transformed_positive(value: float | None) -> float | None:
    if value is None or value <= 0.0:
        return None
    return math.log(value)


def build_samples(form_rows: Iterable[dict[str, str]]) -> tuple[list[Sample], dict[str, int]]:
    fixtures: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in form_rows:
        key = (
            str(row.get("date") or ""),
            str(row.get("league") or ""),
            str(row.get("home_team") or ""),
            str(row.get("away_team") or ""),
        )
        fixtures[key].append(row)

    states: dict[str, SaveState] = defaultdict(SaveState)
    samples: list[Sample] = []
    counters: dict[str, int] = defaultdict(int)
    for key in sorted(fixtures):
        rows = fixtures[key]
        home = [row for row in rows if str(row.get("venue")) == "home"]
        away = [row for row in rows if str(row.get("venue")) == "away"]
        if len(home) != 1 or len(away) != 1:
            counters["bad_fixture_identity"] += 1
            continue
        home_row, away_row = home[0], away[0]
        match_date = parse_day(home_row.get("date"))
        home_actual = parse_float(home_row.get("current_sot_against"))
        home_goals_against = parse_float(home_row.get("current_goals_against"))
        away_actual = parse_float(away_row.get("current_sot_against"))
        away_goals_against = parse_float(away_row.get("current_goals_against"))
        if None in (match_date, home_actual, home_goals_against, away_actual, away_goals_against):
            counters["missing_target"] += 1
            continue
        actuals = (
            int(round(float(home_actual) - float(home_goals_against))),
            int(round(float(away_actual) - float(away_goals_against))),
        )
        if min(actuals) < 0:
            counters["anomalous_fixture"] += 1
            continue

        fixture_samples: list[Sample] = []
        for team, opponent, actual in ((home_row, away_row, actuals[0]), (away_row, home_row, actuals[1])):
            team_key = str(team.get("team_key") or team.get("team") or "").strip()
            opp_key = str(opponent.get("team_key") or opponent.get("team") or "").strip()
            venue = str(team.get("venue") or "").strip()
            opp_venue = str(opponent.get("venue") or "").strip()
            team_history = parse_float(team.get("ema20_matches")) or 0.0
            opp_history = parse_float(opponent.get("ema20_matches")) or 0.0
            if team_history < MIN_HISTORY or opp_history < MIN_HISTORY or states[team_key].matches < MIN_HISTORY:
                counters["history_gate"] += 1
                continue

            values = (
                transformed_positive(preferred(opponent, f"ema20_sot_for_{opp_venue}_avg", "ema20_sot_for_avg")),
                transformed_positive(preferred(team, f"ema20_sot_against_{venue}_avg", "ema20_sot_against_avg")),
                transformed_positive(preferred(opponent, f"ema20_shots_for_{opp_venue}_avg", "ema20_shots_for_avg")),
                transformed_positive(preferred(team, f"ema20_shots_against_{venue}_avg", "ema20_shots_against_avg")),
                None,
                transformed_positive(parse_float(opponent.get("ema20_xg_for_avg"))),
                transformed_positive(parse_float(team.get("ema20_xg_against_avg"))),
                transformed_positive(parse_float(opponent.get("ema20_xg_per_shot_for"))),
                transformed_positive(states[team_key].ema()),
            )
            team_market = parse_float(team.get("market_team_win_prob"))
            opp_market = parse_float(team.get("market_opp_win_prob"))
            mutable = list(values)
            mutable[4] = (opp_market - team_market) if team_market is not None and opp_market is not None else None
            if any(value is None or not math.isfinite(float(value)) for value in mutable):
                counters["feature_missing"] += 1
                continue
            fixture_samples.append(
                Sample(
                    match_date=match_date,
                    season=str(team.get("season") or "").strip(),
                    league=str(team.get("league") or "").strip(),
                    team=str(team.get("team") or "").strip(),
                    team_key=team_key,
                    opponent=str(opponent.get("team") or "").strip(),
                    venue=venue,
                    actual=actual,
                    features=tuple(float(value) for value in mutable),
                )
            )
            counters["eligible"] += 1
            if not opp_key:
                counters["missing_opponent_key"] += 1
        samples.extend(fixture_samples)
        states[str(home_row.get("team_key") or home_row.get("team") or "").strip()].add(actuals[0])
        states[str(away_row.get("team_key") or away_row.get("team") or "").strip()].add(actuals[1])
    return samples, dict(counters)


def league_venue_means(training: Sequence[Sample]) -> tuple[dict[str, float], float]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for sample in training:
        grouped[f"{sample.league}|{sample.venue}"].append(sample.actual)
    fallback = mean(sample.actual for sample in training)
    return {key: mean(values) for key, values in grouped.items()}, fallback


def nb2_nll(actuals: np.ndarray, means: np.ndarray, alpha: float) -> float:
    if alpha <= 0.0:
        return float(np.sum(means - (actuals * np.log(means)) + gammaln(actuals + 1.0)))
    r = 1.0 / alpha
    success = r / (r + means)
    log_likelihood = (
        gammaln(actuals + r)
        - gammaln(r)
        - gammaln(actuals + 1.0)
        + (r * np.log(success))
        + (actuals * np.log1p(-success))
    )
    return float(-np.sum(log_likelihood))


def fit_regression(
    name: str,
    training: Sequence[Sample],
    feature_indices: tuple[int, ...],
    *,
    poisson: bool = False,
) -> FittedModel:
    selected = [tuple(sample.features[index] for index in feature_indices) for sample in training]
    names = [FEATURE_NAMES[index] for index in feature_indices]
    assert_variable_columns(selected, names)
    matrix_values = np.asarray(selected, dtype=float)
    centers = np.mean(matrix_values, axis=0)
    scales = np.std(matrix_values, axis=0)
    if np.any(scales <= 1e-12):
        raise RuntimeError(f"Constant feature entered {name}")
    matrix = np.column_stack((np.ones(len(training)), (matrix_values - centers) / scales))
    baselines, fallback = league_venue_means(training)
    offsets = np.log(
        np.asarray([baselines.get(f"{row.league}|{row.venue}", fallback) for row in training], dtype=float)
    )
    actuals = np.asarray([row.actual for row in training], dtype=float)

    def objective(parameters: np.ndarray) -> float:
        beta = parameters[: matrix.shape[1]]
        means = np.clip(np.exp(offsets + matrix.dot(beta)), MIN_MEAN, MAX_MEAN)
        alpha = 0.0 if poisson else math.exp(float(parameters[-1]))
        penalty = RIDGE * float(np.dot(beta[1:], beta[1:]))
        return nb2_nll(actuals, means, alpha) + penalty

    parameter_count = matrix.shape[1] + (0 if poisson else 1)
    initial = np.zeros(parameter_count, dtype=float)
    bounds: list[tuple[float | None, float | None]] = [(None, None)] * matrix.shape[1]
    if not poisson:
        initial[-1] = math.log(0.08)
        bounds.append((math.log(ALPHA_BOUNDS[0]), math.log(ALPHA_BOUNDS[1])))
    result = minimize(objective, initial, method="L-BFGS-B", bounds=bounds, options={"maxiter": 300})
    if not result.success:
        raise RuntimeError(f"{name} fit failed: {result.message}")
    beta = tuple(float(value) for value in result.x[: matrix.shape[1]])
    alpha = 0.0 if poisson else math.exp(float(result.x[-1]))
    return FittedModel(
        name=name,
        feature_indices=feature_indices,
        beta=beta,
        alpha=alpha,
        centers=tuple(float(value) for value in centers),
        scales=tuple(float(value) for value in scales),
        league_venue_means=baselines,
        fallback_mean=fallback,
    )


def fit_incumbent(training: Sequence[Sample]) -> IncumbentModel:
    baselines, fallback = league_venue_means(training)
    actuals = np.asarray([row.actual for row in training], dtype=float)
    league_values = np.asarray(
        [baselines.get(f"{row.league}|{row.venue}", fallback) for row in training], dtype=float
    )
    save_emas = np.asarray([row.features[8] for row in training], dtype=float)

    def objective(parameters: np.ndarray) -> float:
        weight = float(parameters[0])
        alpha = math.exp(float(parameters[1]))
        means = np.clip(((1.0 - weight) * league_values) + (weight * save_emas), MIN_MEAN, MAX_MEAN)
        return nb2_nll(actuals, means, alpha)

    result = minimize(
        objective,
        np.asarray([0.45, math.log(0.10)]),
        method="L-BFGS-B",
        bounds=[(0.0, 1.0), (math.log(ALPHA_BOUNDS[0]), math.log(ALPHA_BOUNDS[1]))],
    )
    if not result.success:
        raise RuntimeError(f"Incumbent fit failed: {result.message}")
    return IncumbentModel(
        weight=float(result.x[0]),
        alpha=math.exp(float(result.x[1])),
        league_venue_means=baselines,
        fallback_mean=fallback,
    )


def score_model(model: FittedModel | IncumbentModel, validation: Sequence[Sample]) -> dict[str, Any]:
    predictions = [model.predict(sample) for sample in validation]
    alpha = model.alpha
    errors = [prediction - sample.actual for sample, prediction in zip(validation, predictions)]
    probability_rows: list[tuple[float, bool, str]] = []
    for sample, prediction in zip(validation, predictions):
        for line in LINES:
            probability_rows.append(
                (
                    prob_over(line, prediction, distribution="negative_binomial", alpha=alpha),
                    sample.actual > line,
                    sample.league,
                )
            )
    overall = {
        "n": len(validation),
        "mae": mean(abs(error) for error in errors),
        "bias": mean(errors),
        "brier": mean(brier(probability, actual) for probability, actual, _league in probability_rows),
        "log_loss": mean(log_loss(probability, actual) for probability, actual, _league in probability_rows),
        "alpha": alpha,
    }
    per_league: dict[str, dict[str, float]] = {}
    for league in sorted({sample.league for sample in validation}):
        league_indices = [index for index, sample in enumerate(validation) if sample.league == league]
        league_probabilities = [row for row in probability_rows if row[2] == league]
        league_errors = [errors[index] for index in league_indices]
        per_league[league] = {
            "n": len(league_indices),
            "mae": mean(abs(error) for error in league_errors),
            "bias": mean(league_errors),
            "brier": mean(brier(probability, actual) for probability, actual, _ in league_probabilities),
            "log_loss": mean(log_loss(probability, actual) for probability, actual, _ in league_probabilities),
        }
    bins: list[dict[str, float | int]] = []
    for index in range(10):
        low = index / 10.0
        high = (index + 1) / 10.0
        bucket = [row for row in probability_rows if low <= row[0] < high or (index == 9 and row[0] == 1.0)]
        if bucket:
            bins.append(
                {
                    "low": low,
                    "high": high,
                    "n": len(bucket),
                    "predicted": mean(row[0] for row in bucket),
                    "actual": mean(float(row[1]) for row in bucket),
                }
            )
    overall["per_league"] = per_league
    overall["calibration_bins"] = bins
    return overall


def evaluate_fold(season: str, samples: Sequence[Sample]) -> dict[str, Any]:
    validation = [sample for sample in samples if sample.season == season]
    if not validation:
        raise RuntimeError(f"No validation rows for {season}")
    first_date = min(sample.match_date for sample in validation)
    training = [sample for sample in samples if sample.match_date < first_date]
    incumbent = fit_incumbent(training)
    models: dict[str, FittedModel | IncumbentModel] = {"INCUMBENT": incumbent}
    models["POISSON_CORE_SHOTS"] = fit_regression(
        "POISSON_CORE_SHOTS", training, VARIANTS["NB2_CORE_SHOTS"], poisson=True
    )
    for name, indices in VARIANTS.items():
        models[name] = fit_regression(name, training, indices)
    return {
        "season": season,
        "train": len(training),
        "validation": len(validation),
        "first_validation_date": first_date.isoformat(),
        "models": {name: score_model(model, validation) for name, model in models.items()},
        "fitted": {
            name: serialize_model(model)
            for name, model in models.items()
            if isinstance(model, FittedModel)
        },
        "incumbent": {
            "weight": incumbent.weight,
            "alpha": incumbent.alpha,
        },
    }


def serialize_model(model: FittedModel) -> dict[str, Any]:
    return {
        "name": model.name,
        "features": [FEATURE_NAMES[index] for index in model.feature_indices],
        "beta": list(model.beta),
        "alpha": model.alpha,
        "centers": list(model.centers),
        "scales": list(model.scales),
        "league_venue_means": model.league_venue_means,
        "fallback_mean": model.fallback_mean,
    }


def write_csv(path: Path, folds: Sequence[dict[str, Any]]) -> None:
    fields = ("season", "model", "train", "validation", "mae", "bias", "brier", "log_loss", "alpha")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for fold in folds:
            for model_name, metrics in fold["models"].items():
                writer.writerow(
                    {
                        "season": fold["season"],
                        "model": model_name,
                        "train": fold["train"],
                        "validation": fold["validation"],
                        "mae": f"{metrics['mae']:.6f}",
                        "bias": f"{metrics['bias']:.6f}",
                        "brier": f"{metrics['brier']:.6f}",
                        "log_loss": f"{metrics['log_loss']:.6f}",
                        "alpha": f"{metrics['alpha']:.6f}",
                    }
                )


def report_lines(audit: dict[str, Any], samples: Sequence[Sample], counters: dict[str, int], folds: Sequence[dict[str, Any]]) -> list[str]:
    lines = [
        "# Goalkeeper Saves v1 registered count backtest",
        "",
        "**Status: RESEARCH / COUNT GATE ONLY. No historical goalkeeper-saves prices exist, so ROI and CLV are unavailable.**",
        "",
        "## Target integrity",
        "",
        f"- Historical fixtures: {audit['fixtures']:,}",
        f"- Missing fixtures: {audit['missing_fixtures']:,}",
        f"- Anomalous fixtures dropped in full: {audit['anomalous_fixtures']:,}",
        f"- Valid team-save observations: {audit['valid_team_observations']:,}",
        f"- Mean / variance-to-mean / zero rate: {audit['mean']:.4f} / {audit['variance_to_mean']:.4f} / {audit['zero_rate']:.2%}",
        f"- Model samples after lagged-history and feature gates: {len(samples):,}",
        "",
        "Target is team saves (`opponent SOT - opponent goals`) and may only be published against a named goalkeeper after a confirmed starting XI.",
        "",
        "## Walk-forward folds",
        "",
        "| Fold | Model | Train | Validation | MAE | Bias | Brier | Log loss | NB2 alpha |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    order = ("INCUMBENT", "POISSON_CORE_SHOTS", *VARIANTS.keys())
    for fold in folds:
        for model_name in order:
            metric = fold["models"][model_name]
            lines.append(
                f"| {fold['season']} | {model_name} | {fold['train']} | {fold['validation']} | "
                f"{metric['mae']:.4f} | {metric['bias']:+.4f} | {metric['brier']:.4f} | "
                f"{metric['log_loss']:.4f} | {metric['alpha']:.4f} |"
            )
    lines.extend(
        [
            "",
            "## Full candidate per-league guard",
            "",
            "| Fold | League | n | Incumbent Brier | NB2 Full Brier | Delta |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for fold in folds:
        incumbent = fold["models"]["INCUMBENT"]["per_league"]
        candidate = fold["models"]["NB2_FULL"]["per_league"]
        for league in sorted(candidate):
            delta = candidate[league]["brier"] - incumbent[league]["brier"]
            lines.append(
                f"| {fold['season']} | {league} | {candidate[league]['n']} | {incumbent[league]['brier']:.4f} | "
                f"{candidate[league]['brier']:.4f} | {delta:+.4f} |"
            )
    lines.extend(
        [
            "",
            "## Registered decision",
            "",
            "- Candidate: `goalkeeper-saves-v1-nb2-confirmed-starter` (legacy experiment ID).",
            "- Count evidence can authorize prospective shadow capture only.",
            "- Shadow tracking accepts predicted or confirmed starting goalkeepers, paired real prices and one strongest selection per fixture.",
            "- Sell gate remains blocked until >=150 settled real-price selections, >=70% true-close coverage and mean true-close CLV >=+0.5%.",
            "- No synthetic-price P/L, inferred CLV or public/live routing is permitted.",
            "",
            "## Sample build counters",
            "",
        ]
    )
    lines.extend(f"- {key}: {value:,}" for key, value in sorted(counters.items()))
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", type=Path, default=DEFAULT_HISTORICAL)
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    targets, target_audit = reconstruct_targets(load_csv(args.historical))
    form_rows = load_csv(args.form)
    samples, counters = build_samples(form_rows)
    folds = [evaluate_fold(season, samples) for season in VALIDATION_SEASONS]
    final_model = fit_regression("NB2_FULL", samples, VARIANTS["NB2_FULL"])

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "gk-saves-v1-fold-report.md"
    results_path = args.output_dir / "gk-saves-v1-fold-results.csv"
    evidence_path = args.output_dir / "gk-saves-v1-evidence.json"
    params_path = args.output_dir / "gk-saves-v1-params.json"
    lock_path = args.output_dir / "gk-saves-v1-lock.json"
    write_csv(results_path, folds)
    report_path.write_text("\n".join(report_lines(target_audit, samples, counters, folds)), encoding="utf-8")
    evidence_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "status": "COUNT_BACKTEST_COMPLETE_MARKET_GATE_BLOCKED",
                "target_audit": target_audit,
                "sample_counters": counters,
                "model_samples": len(samples),
                "folds": folds,
                "roi": None,
                "clv": None,
                "sellable": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    params_path.write_text(json.dumps(serialize_model(final_model), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lock_path.write_text(
        json.dumps(
            {
                "experiment": "goalkeeper_saves_v1",
                "status": "research_count_gate_only",
                "live_routing": False,
                "candidate": "goalkeeper-saves-v1-nb2-confirmed-starter",
                "target": "team_saves_equals_opponent_sot_minus_opponent_goals",
                "distribution": "nb2",
                "lines": list(LINES),
                "history_gate": MIN_HISTORY,
                "ema_window": WINDOW,
                "ema_decay": DECAY,
                "publication_gate": "predicted_or_confirmed_starting_goalkeeper_shadow_only",
                "input_files": {
                    "historical": {"path": str(args.historical.relative_to(ROOT)), "sha256": sha256_file(args.historical)},
                    "team_rolling_form": {"path": str(args.form.relative_to(ROOT)), "sha256": sha256_file(args.form)},
                },
                "promotion_gates": {
                    "settled_real_price_selections": 150,
                    "true_close_coverage": 0.70,
                    "mean_true_close_clv": 0.005,
                    "beat_devigged_market_brier_and_log_loss": True,
                },
                "do_not_sell": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Valid historical team-save observations: {len(targets):,}")
    print(f"Model samples: {len(samples):,}")
    print(f"Wrote {report_path.relative_to(ROOT)}")
    print(f"Wrote {results_path.relative_to(ROOT)}")
    print(f"Wrote {evidence_path.relative_to(ROOT)}")
    print(f"Wrote {params_path.relative_to(ROOT)}")
    print(f"Wrote {lock_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
