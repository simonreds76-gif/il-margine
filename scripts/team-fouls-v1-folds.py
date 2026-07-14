#!/usr/bin/env python3
"""Walk-forward Team Fouls v1 count-model experiment.

This is a registered research harness. It never emits betting signals and it
cannot clear the separate M0 market-price gate.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_counts import fit_dispersion_alpha_mle, nb_log_pmf, prob_over  # noqa: E402
from football_market import brier, log_loss  # noqa: E402
from football_team_names import football_form_team_key  # noqa: E402


DEFAULT_SOURCE = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_M1 = ROOT / "data" / "football-form" / "fouls-empirical-baseline.json"
DEFAULT_CSV = ROOT / "data" / "football-form" / "team-fouls-v1-fold-results.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "team-fouls-v1-fold-report.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "team-fouls-v1-fold-report.md"
VALIDATION_SEASONS = ("2024-2025", "2025-2026")
LEAGUES = ("bundesliga", "epl", "la-liga", "ligue-1", "serie-a")
LINES = (9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5)
DECAY = 0.93
WINDOW = 20
MIN_HISTORY = 6
REFEREE_K = 18.0
TEAM_ALPHA_K = 60.0
RIDGE = 0.01
FIXED_ALPHA = 0.025
FEATURE_NAMES = (
    "team_committed",
    "opponent_drawn",
    "referee_epl",
    "opening_closeness",
    "opening_strength",
    "team_cards",
    "opponent_cards",
)
RUNGS = {
    "core": (0, 1),
    "core_referee": (0, 1, 2),
    "core_referee_market": (0, 1, 2, 3, 4),
    "full": tuple(range(len(FEATURE_NAMES))),
}


def numeric(value: object) -> float | None:
    try:
        parsed = float(str(value or "").strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0.0 else None


def parse_match_date(value: object) -> date | None:
    text = str(value or "").strip()[:10]
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


@dataclass
class TeamState:
    committed: list[float] = field(default_factory=list)
    drawn: list[float] = field(default_factory=list)
    cards: list[float] = field(default_factory=list)

    def add(self, committed: float, drawn: float, cards: float) -> None:
        for values, observation in (
            (self.committed, committed),
            (self.drawn, drawn),
            (self.cards, cards),
        ):
            values.append(observation)
            if len(values) > WINDOW:
                del values[0]

    @property
    def matches(self) -> int:
        return len(self.committed)

    @staticmethod
    def ema(values: list[float]) -> float:
        weights = [DECAY ** (len(values) - 1 - index) for index in range(len(values))]
        return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


@dataclass
class RunningMean:
    total: float = 0.0
    count: int = 0

    def add(self, value: float) -> None:
        self.total += value
        self.count += 1

    def value(self, fallback: float) -> float:
        return self.total / self.count if self.count else fallback


@dataclass(frozen=True)
class Sample:
    fixture_id: str
    match_date: date
    season: str
    league: str
    venue: str
    team_key: str
    opponent_key: str
    actual: int
    opponent_actual: int
    baseline_mean: float
    features: tuple[float, ...]


@dataclass(frozen=True)
class FittedModel:
    beta: tuple[float, ...]
    alpha: float
    centers: tuple[float, ...]
    scales: tuple[float, ...]
    indices: tuple[int, ...]

    def predict(self, sample: Sample) -> float:
        selected = [sample.features[index] for index in self.indices]
        standardized = [
            (value - center) / scale
            for value, center, scale in zip(selected, self.centers, self.scales)
        ]
        linear = self.beta[0] + sum(weight * value for weight, value in zip(self.beta[1:], standardized))
        return max(2.0, min(28.0, sample.baseline_mean * math.exp(linear)))


def _opening_features(row: dict[str, str], venue: str) -> tuple[float, float]:
    home = numeric(row.get("B365H"))
    draw = numeric(row.get("B365D"))
    away = numeric(row.get("B365A"))
    if None in (home, draw, away) or min(float(home), float(draw), float(away)) <= 1.0:
        return 0.0, 0.0
    home_p = 1.0 / float(home)
    away_p = 1.0 / float(away)
    closeness = 1.0 - abs(home_p - away_p)
    strength = math.log(max(1e-6, home_p) / max(1e-6, away_p))
    return closeness, strength if venue == "home" else -strength


def _league_fallbacks(rows: Iterable[dict[str, str]]) -> dict[tuple[str, str], float]:
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        league = str(row.get("league") or "").strip().lower()
        home = numeric(row.get("HF"))
        away = numeric(row.get("AF"))
        if league in LEAGUES and home is not None and away is not None:
            values[(league, "home")].append(home)
            values[(league, "away")].append(away)
            home_cards = numeric(row.get("HY"))
            away_cards = numeric(row.get("AY"))
            if home_cards is not None:
                values[(league, "home_cards")].append(home_cards)
            if away_cards is not None:
                values[(league, "away_cards")].append(away_cards)
    return {key: statistics.fmean(observations) for key, observations in values.items() if observations}


def build_samples(rows: list[dict[str, str]]) -> list[Sample]:
    """Build pre-match samples; all fixtures on a date are scored before that date updates state."""
    prepared: list[tuple[date, dict[str, str]]] = []
    for row in rows:
        match_date = parse_match_date(row.get("Date"))
        league = str(row.get("league") or "").strip().lower()
        if match_date and league in LEAGUES:
            prepared.append((match_date, row))
    prepared.sort(key=lambda item: (item[0], str(item[1].get("league")), str(item[1].get("HomeTeam"))))

    fallbacks = _league_fallbacks(row for _, row in prepared)
    states: dict[tuple[str, str], TeamState] = defaultdict(TeamState)
    league_history: dict[tuple[str, str], RunningMean] = defaultdict(RunningMean)
    league_card_history: dict[tuple[str, str], RunningMean] = defaultdict(RunningMean)
    season_history: dict[tuple[str, str, str], RunningMean] = defaultdict(RunningMean)
    referee_history: dict[str, RunningMean] = defaultdict(RunningMean)
    epl_total = RunningMean()
    samples: list[Sample] = []

    by_day: dict[date, list[dict[str, str]]] = defaultdict(list)
    for match_date, row in prepared:
        by_day[match_date].append(row)

    for match_date in sorted(by_day):
        updates: list[tuple[str, str, float, float, float, str, str, str, float, str]] = []
        for row in by_day[match_date]:
            league = str(row.get("league") or "").strip().lower()
            season = str(row.get("season") or "").strip()
            home_name = football_form_team_key(row.get("HomeTeam"))
            away_name = football_form_team_key(row.get("AwayTeam"))
            home_fouls = numeric(row.get("HF"))
            away_fouls = numeric(row.get("AF"))
            home_cards = numeric(row.get("HY"))
            away_cards = numeric(row.get("AY"))
            if not home_name or not away_name or None in (home_fouls, away_fouls, home_cards, away_cards):
                continue

            fixture_id = f"{match_date.isoformat()}|{league}|{home_name}|{away_name}"
            referee = str(row.get("Referee") or "").strip()
            league_total_mean = epl_total.value(
                fallbacks.get(("epl", "home"), 11.0) + fallbacks.get(("epl", "away"), 11.0)
            )
            referee_mean = referee_history[referee]
            referee_effect = 0.0
            if league == "epl" and referee and referee_mean.count:
                shrunk = (
                    referee_mean.total + (REFEREE_K * league_total_mean)
                ) / (referee_mean.count + REFEREE_K)
                referee_effect = (shrunk - league_total_mean) / 2.0

            for venue, team_name, opponent_name, actual, opponent_actual, cards, opponent_cards in (
                ("home", home_name, away_name, float(home_fouls), float(away_fouls), float(home_cards), float(away_cards)),
                ("away", away_name, home_name, float(away_fouls), float(home_fouls), float(away_cards), float(home_cards)),
            ):
                team_state = states[(league, team_name)]
                opponent_state = states[(league, opponent_name)]
                fallback = fallbacks.get((league, venue), 12.0)
                season_mean = season_history[(league, season, venue)]
                historical_mean = league_history[(league, venue)]
                baseline = season_mean.value(historical_mean.value(fallback)) if season_mean.count >= 20 else historical_mean.value(fallback)
                card_fallback = league_card_history[(league, venue)].value(
                    fallbacks.get((league, f"{venue}_cards"), 2.0)
                )
                closeness, strength = _opening_features(row, venue)
                if team_state.matches >= MIN_HISTORY and opponent_state.matches >= MIN_HISTORY:
                    features = (
                        math.log(max(0.1, team_state.ema(team_state.committed)) / baseline),
                        math.log(max(0.1, opponent_state.ema(opponent_state.drawn)) / baseline),
                        referee_effect,
                        closeness,
                        strength,
                        math.log(max(0.1, team_state.ema(team_state.cards)) / max(0.1, card_fallback)),
                        math.log(max(0.1, opponent_state.ema(opponent_state.cards)) / max(0.1, card_fallback)),
                    )
                    samples.append(
                        Sample(
                            fixture_id=fixture_id,
                            match_date=match_date,
                            season=season,
                            league=league,
                            venue=venue,
                            team_key=team_name,
                            opponent_key=opponent_name,
                            actual=int(round(actual)),
                            opponent_actual=int(round(opponent_actual)),
                            baseline_mean=baseline,
                            features=features,
                        )
                    )

            updates.append(
                (
                    league,
                    season,
                    float(home_fouls),
                    float(away_fouls),
                    float(home_cards),
                    home_name,
                    away_name,
                    referee,
                    float(away_cards),
                    fixture_id,
                )
            )

        for league, season, home_fouls, away_fouls, home_cards, home_name, away_name, referee, away_cards, _ in updates:
            states[(league, home_name)].add(home_fouls, away_fouls, home_cards)
            states[(league, away_name)].add(away_fouls, home_fouls, away_cards)
            league_history[(league, "home")].add(home_fouls)
            league_history[(league, "away")].add(away_fouls)
            league_card_history[(league, "home")].add(home_cards)
            league_card_history[(league, "away")].add(away_cards)
            season_history[(league, season, "home")].add(home_fouls)
            season_history[(league, season, "away")].add(away_fouls)
            if league == "epl":
                epl_total.add(home_fouls + away_fouls)
                if referee:
                    referee_history[referee].add(home_fouls + away_fouls)
    return samples


def fit_model(training: list[Sample], indices: tuple[int, ...]) -> FittedModel:
    selected = [tuple(sample.features[index] for index in indices) for sample in training]
    columns = list(zip(*selected))
    centers = tuple(statistics.fmean(column) for column in columns)
    scales = tuple(max(1e-6, statistics.pstdev(column)) for column in columns)
    matrix = np.asarray(
        [[1.0, *[(value - center) / scale for value, center, scale in zip(row, centers, scales)]] for row in selected],
        dtype=float,
    )
    offsets = np.log(np.asarray([sample.baseline_mean for sample in training], dtype=float))
    actuals = np.asarray([sample.actual for sample in training], dtype=int)

    def objective(parameters: np.ndarray) -> float:
        beta = parameters[:-1]
        alpha = math.exp(float(parameters[-1]))
        means = np.clip(np.exp(offsets + matrix.dot(beta)), 2.0, 28.0)
        size = 1.0 / alpha
        success = size / (size + means)
        log_probabilities = (
            gammaln(actuals + size)
            - gammaln(size)
            - gammaln(actuals + 1)
            + (size * np.log(success))
            + (actuals * np.log1p(-success))
        )
        nll = -float(np.sum(log_probabilities))
        return float(nll + (RIDGE * np.dot(beta[1:], beta[1:])))

    initial = np.zeros(matrix.shape[1] + 1, dtype=float)
    initial[-1] = math.log(FIXED_ALPHA)
    result = minimize(
        objective,
        initial,
        method="L-BFGS-B",
        bounds=[(None, None)] * matrix.shape[1] + [(math.log(0.002), math.log(0.20))],
        options={"maxiter": 350},
    )
    if not result.success:
        raise RuntimeError(f"Team Fouls NB regression failed: {result.message}")
    return FittedModel(
        beta=tuple(float(value) for value in result.x[:-1]),
        alpha=math.exp(float(result.x[-1])),
        centers=centers,
        scales=scales,
        indices=indices,
    )


def count_metrics(model: FittedModel, rows: list[Sample]) -> dict[str, float]:
    means = [model.predict(sample) for sample in rows]
    return {
        "mae": statistics.fmean(abs(sample.actual - mean) for sample, mean in zip(rows, means)),
        "nll": -statistics.fmean(nb_log_pmf(sample.actual, mean, model.alpha) for sample, mean in zip(rows, means)),
        "bias": statistics.fmean(mean - sample.actual for sample, mean in zip(rows, means)),
        "alpha": model.alpha,
    }


def fitted_alphas(
    training: list[Sample], model: FittedModel
) -> tuple[float, dict[str, float], dict[tuple[str, str], float]]:
    predicted = [(sample, model.predict(sample)) for sample in training]
    pooled = fit_dispersion_alpha_mle(((sample.actual, mean) for sample, mean in predicted), fallback=FIXED_ALPHA, min_sample=100)
    by_league: dict[str, list[tuple[float, float]]] = defaultdict(list)
    by_team: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for sample, mean in predicted:
        by_league[sample.league].append((sample.actual, mean))
        by_team[(sample.league, sample.team_key)].append((sample.actual, mean))
    league_alpha = {
        league: fit_dispersion_alpha_mle(values, fallback=pooled, min_sample=100)
        for league, values in by_league.items()
    }
    team_alpha: dict[tuple[str, str], float] = {}
    for key, values in by_team.items():
        prior = league_alpha.get(key[0], pooled)
        raw = fit_dispersion_alpha_mle(values, fallback=prior, min_sample=10)
        sample = len(values)
        team_alpha[key] = ((sample * raw) + (TEAM_ALPHA_K * prior)) / (sample + TEAM_ALPHA_K)
    return pooled, league_alpha, team_alpha


def residual_frailty(
    training: list[Sample], model: FittedModel, ceilings: dict[str, float]
) -> dict[str, float]:
    pairs: dict[tuple[str, str], list[tuple[float, float, float, float]]] = defaultdict(list)
    fixture_rows: dict[str, list[Sample]] = defaultdict(list)
    for sample in training:
        fixture_rows[sample.fixture_id].append(sample)
    for rows in fixture_rows.values():
        if len(rows) != 2:
            continue
        home = next((row for row in rows if row.venue == "home"), None)
        away = next((row for row in rows if row.venue == "away"), None)
        if home and away:
            mh, ma = model.predict(home), model.predict(away)
            pairs[(home.league, "pairs")].append((home.actual - mh, away.actual - ma, mh, ma))
    result: dict[str, float] = {}
    for league in LEAGUES:
        rows = pairs.get((league, "pairs"), [])
        if not rows:
            result[league] = 0.0
            continue
        estimate = statistics.fmean(left * right for left, right, _, _ in rows) / max(
            1e-6, statistics.fmean(home * away for _, _, home, away in rows)
        )
        result[league] = max(0.0, min(ceilings.get(league, 0.0), estimate))
    return result


def reliability(rows: list[tuple[float, int]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda item: item[0])
    bins: list[dict[str, float | int]] = []
    for index in range(10):
        start = round(index * len(ordered) / 10)
        end = round((index + 1) * len(ordered) / 10)
        chunk = ordered[start:end]
        if not chunk:
            continue
        predicted = statistics.fmean(value[0] for value in chunk)
        actual = statistics.fmean(value[1] for value in chunk)
        bins.append({"bin": index + 1, "n": len(chunk), "predicted": predicted, "actual": actual, "gap": predicted - actual})
    return {
        "bins": bins,
        "max_abs_gap": max((abs(float(item["gap"])) for item in bins), default=1.0),
    }


def distribution_metrics(
    training: list[Sample], validation: list[Sample], model: FittedModel, ceilings: dict[str, float]
) -> dict[str, Any]:
    pooled, league_alpha, team_alpha = fitted_alphas(training, model)
    nu = residual_frailty(training, model, ceilings)
    models = ("poisson", "fixed_alpha", "hierarchical_nb")
    totals = {name: {"brier": 0.0, "log_loss": 0.0, "n": 0} for name in models}
    by_league = {
        league: {name: {"brier": 0.0, "n": 0} for name in models} for league in LEAGUES
    }
    calibration_rows: list[tuple[float, int]] = []
    for sample in validation:
        mean = model.predict(sample)
        hierarchical = team_alpha.get((sample.league, sample.team_key), league_alpha.get(sample.league, pooled))
        alphas = {"poisson": 0.0, "fixed_alpha": FIXED_ALPHA, "hierarchical_nb": hierarchical}
        for line in LINES:
            outcome = int(sample.actual > line)
            for name, alpha in alphas.items():
                distribution = "poisson" if name == "poisson" else "negative_binomial"
                probability = prob_over(line, mean, distribution=distribution, alpha=alpha)
                totals[name]["brier"] += brier(probability, bool(outcome))
                totals[name]["log_loss"] += log_loss(probability, bool(outcome))
                totals[name]["n"] += 1
                by_league[sample.league][name]["brier"] += brier(probability, bool(outcome))
                by_league[sample.league][name]["n"] += 1
                if name == "hierarchical_nb":
                    calibration_rows.append((probability, outcome))

    fixture_rows: dict[str, list[Sample]] = defaultdict(list)
    for sample in validation:
        fixture_rows[sample.fixture_id].append(sample)
    actual_totals: list[float] = []
    predicted_totals: list[float] = []
    conditional_variances: list[float] = []
    for rows in fixture_rows.values():
        if len(rows) != 2:
            continue
        home = next((row for row in rows if row.venue == "home"), None)
        away = next((row for row in rows if row.venue == "away"), None)
        if not home or not away:
            continue
        mh, ma = model.predict(home), model.predict(away)
        ah = team_alpha.get((home.league, home.team_key), league_alpha.get(home.league, pooled))
        aa = team_alpha.get((away.league, away.team_key), league_alpha.get(away.league, pooled))
        shared = nu.get(home.league, 0.0)
        conditional = (
            mh + ma
            + max(0.0, ah - shared) * mh * mh
            + max(0.0, aa - shared) * ma * ma
            + shared * (mh + ma) ** 2
        )
        actual_totals.append(float(home.actual + away.actual))
        predicted_totals.append(mh + ma)
        conditional_variances.append(conditional)

    empirical_vmr = statistics.pvariance(actual_totals) / statistics.fmean(actual_totals)
    priced_variance = statistics.fmean(conditional_variances) + statistics.pvariance(predicted_totals)
    priced_vmr = priced_variance / statistics.fmean(predicted_totals)
    result: dict[str, Any] = {
        "pooled_alpha": pooled,
        "league_alpha": league_alpha,
        "residual_nu": nu,
        "by_league": [],
        "reliability": reliability(calibration_rows),
        "empirical_total_vmr": empirical_vmr,
        "priced_total_vmr": priced_vmr,
        "total_vmr_gap": priced_vmr - empirical_vmr,
    }
    for name, values in totals.items():
        result[f"{name}_brier"] = values["brier"] / max(1, values["n"])
        result[f"{name}_log_loss"] = values["log_loss"] / max(1, values["n"])
    for league in LEAGUES:
        values = by_league[league]
        result["by_league"].append(
            {
                "league": league,
                "matches": int(values["hierarchical_nb"]["n"] / len(LINES)),
                **{
                    f"{name}_brier": values[name]["brier"] / max(1, values[name]["n"])
                    for name in models
                },
            }
        )
    return result


def evaluate_fold(season: str, samples: list[Sample], ceilings: dict[str, float]) -> dict[str, Any]:
    validation = [sample for sample in samples if sample.season == season]
    if not validation:
        return {"season": season, "status": "NO_VALIDATION_ROWS"}
    validation_start = min(sample.match_date for sample in validation)
    training = [sample for sample in samples if sample.match_date < validation_start]
    if len(training) < 5000:
        return {"season": season, "status": "INSUFFICIENT_TRAIN_ROWS", "train": len(training)}

    fitted = {name: fit_model(training, indices) for name, indices in RUNGS.items()}
    rungs = {name: count_metrics(model, validation) for name, model in fitted.items()}
    transition_specs = (
        ("core", "core_referee", "epl"),
        ("core_referee", "core_referee_market", "all"),
        ("core_referee_market", "full", "all"),
    )
    transitions: list[dict[str, Any]] = []
    for previous, current, scope in transition_specs:
        scoped = [sample for sample in validation if scope == "all" or sample.league == scope]
        old = count_metrics(fitted[previous], scoped)
        new = count_metrics(fitted[current], scoped)
        transitions.append(
            {
                "from": previous,
                "to": current,
                "scope": scope,
                "n": len(scoped),
                "delta_nll": new["nll"] - old["nll"],
                "delta_mae": new["mae"] - old["mae"],
            }
        )
    baseline_mae = statistics.fmean(abs(sample.actual - sample.baseline_mean) for sample in validation)
    full_model = fitted["full"]
    distribution = distribution_metrics(training, validation, full_model, ceilings)
    return {
        "season": season,
        "status": "OK",
        "train": len(training),
        "validation_legs": len(validation),
        "validation_matches": len({sample.fixture_id for sample in validation}),
        "causal_baseline_mae": baseline_mae,
        "rungs": rungs,
        "transitions": transitions,
        "coefficients": {name: value for name, value in zip(("intercept", *FEATURE_NAMES), full_model.beta)},
        "distribution": distribution,
    }


def apply_gates(folds: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [fold for fold in folds if fold.get("status") == "OK"]
    ladder_checks: list[dict[str, Any]] = []
    for fold in valid:
        for transition in fold["transitions"]:
            passed = transition["delta_nll"] <= -0.0015 and transition["delta_mae"] <= 1e-9
            ladder_checks.append(
                {"season": fold["season"], **transition, "passed": passed}
            )
    mae_checks = [
        {
            "season": fold["season"],
            "improvement_pct": 100.0 * (fold["causal_baseline_mae"] - fold["rungs"]["full"]["mae"]) / fold["causal_baseline_mae"],
        }
        for fold in valid
    ]
    league_cells = [
        row
        for fold in valid
        for row in fold["distribution"]["by_league"]
        if row["matches"] > 0
    ]
    nb_wins = sum(
        row["hierarchical_nb_brier"] < row["poisson_brier"]
        and row["hierarchical_nb_brier"] < row["fixed_alpha_brier"]
        for row in league_cells
    )
    gates = {
        "folds_complete": len(valid) == len(VALIDATION_SEASONS),
        "feature_ladder": bool(ladder_checks) and all(check["passed"] for check in ladder_checks),
        "mae_improvement": bool(mae_checks) and all(check["improvement_pct"] >= 5.0 for check in mae_checks),
        "hierarchical_nb_cells": nb_wins >= 8 and len(league_cells) >= 10,
        "reliability": bool(valid) and all(fold["distribution"]["reliability"]["max_abs_gap"] <= 0.02 for fold in valid),
        "total_variance": bool(valid) and all(abs(fold["distribution"]["total_vmr_gap"]) <= 0.10 for fold in valid),
        "market_prices": False,
    }
    count_gate = all(value for name, value in gates.items() if name != "market_prices")
    return {
        "status": "COUNT_GATE_PASS_MARKET_BLOCKED" if count_gate else "COUNT_GATE_FAIL_MARKET_BLOCKED",
        "count_gate_pass": count_gate,
        "market_gate_pass": False,
        "signals_authorized": False,
        "gates": gates,
        "ladder_checks": ladder_checks,
        "mae_checks": mae_checks,
        "hierarchical_nb_wins": nb_wins,
        "hierarchical_nb_cells": len(league_cells),
    }


def render_report(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    lines = [
        "# Team Fouls v1: F1 Walk-Forward Count Gate",
        "",
        f"Generated: {payload['generated_at']}",
        f"Samples: {payload['sample_legs']:,} team legs across {payload['sample_matches']:,} matches.",
        "",
        f"**Decision: {decision['status'].replace('_', ' ')}. No bets or public signals are authorized.**",
        "",
        "The model is evaluated without bookmaker foul prices. Passing this report would validate count estimates only; M0 remains a separate hard block.",
        "",
        "## Fold results",
        "",
        "| Fold | Train legs | Validation matches | Baseline MAE | Full MAE | Improvement | Full NLL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for fold in payload["folds"]:
        if fold.get("status") != "OK":
            lines.append(f"| {fold['season']} | - | - | - | - | - | {fold['status']} |")
            continue
        improvement = 100.0 * (fold["causal_baseline_mae"] - fold["rungs"]["full"]["mae"]) / fold["causal_baseline_mae"]
        lines.append(
            f"| {fold['season']} | {fold['train']:,} | {fold['validation_matches']:,} | {fold['causal_baseline_mae']:.3f} | "
            f"{fold['rungs']['full']['mae']:.3f} | {improvement:+.2f}% | {fold['rungs']['full']['nll']:.4f} |"
        )
    lines.extend([
        "",
        "## Registered feature ladder",
        "",
        "| Fold | Transition | Scope | Delta NLL | Delta MAE | Gate |",
        "|---|---|---|---:|---:|---|",
    ])
    for check in decision["ladder_checks"]:
        lines.append(
            f"| {check['season']} | {check['from']} -> {check['to']} | {check['scope'].upper()} | {check['delta_nll']:+.5f} | {check['delta_mae']:+.5f} | {'PASS' if check['passed'] else 'FAIL'} |"
        )
    lines.extend([
        "",
        "## Distribution and calibration",
        "",
        "| Fold | Poisson Brier | Fixed NB Brier | Hierarchical NB Brier | Max decile gap | Empirical total VMR | Priced total VMR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for fold in payload["folds"]:
        if fold.get("status") != "OK":
            continue
        dist = fold["distribution"]
        lines.append(
            f"| {fold['season']} | {dist['poisson_brier']:.4f} | {dist['fixed_alpha_brier']:.4f} | {dist['hierarchical_nb_brier']:.4f} | "
            f"{dist['reliability']['max_abs_gap']:.3%} | {dist['empirical_total_vmr']:.3f} | {dist['priced_total_vmr']:.3f} |"
        )
    lines.extend([
        "",
        "## Gate summary",
        "",
    ])
    for name, passed in decision["gates"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'}: `{name}`")
    lines.extend([
        "",
        f"Hierarchical NB wins: {decision['hierarchical_nb_wins']}/{decision['hierarchical_nb_cells']} league-fold cells (required 8/10).",
        "",
        "## Product status",
        "",
        "- Research only. This script does not write candidates, picks, stakes, or settlement rows.",
        "- Team/match fouls prices remain unobserved in the configured feed.",
        "- A future lock requires paired bookmaker prices, source-definition agreement, and prospective CLV evidence.",
    ])
    return "\n".join(lines) + "\n"


def write_csv(path: Path, folds: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for fold in folds:
        if fold.get("status") != "OK":
            rows.append({"season": fold["season"], "status": fold["status"]})
            continue
        improvement = 100.0 * (fold["causal_baseline_mae"] - fold["rungs"]["full"]["mae"]) / fold["causal_baseline_mae"]
        rows.append(
            {
                "season": fold["season"],
                "status": fold["status"],
                "train_legs": fold["train"],
                "validation_matches": fold["validation_matches"],
                "baseline_mae": fold["causal_baseline_mae"],
                "full_mae": fold["rungs"]["full"]["mae"],
                "mae_improvement_pct": improvement,
                "poisson_brier": fold["distribution"]["poisson_brier"],
                "fixed_alpha_brier": fold["distribution"]["fixed_alpha_brier"],
                "hierarchical_nb_brier": fold["distribution"]["hierarchical_nb_brier"],
                "max_reliability_gap": fold["distribution"]["reliability"]["max_abs_gap"],
                "empirical_total_vmr": fold["distribution"]["empirical_total_vmr"],
                "priced_total_vmr": fold["distribution"]["priced_total_vmr"],
            }
        )
    fields = sorted({field for row in rows for field in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the registered Team Fouls v1 F1 fold harness.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--m1", type=Path, default=DEFAULT_M1)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    rows = load_csv(args.source)
    m1 = json.loads(args.m1.read_text(encoding="utf-8"))
    ceilings = {
        league: max(0.0, float(m1["leg_structure"][league]["nu_hat_raw_ceiling"]))
        for league in LEAGUES
    }
    samples = build_samples(rows)
    folds = [evaluate_fold(season, samples, ceilings) for season in VALIDATION_SEASONS]
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": str(args.source.relative_to(ROOT)).replace("\\", "/") if args.source.is_relative_to(ROOT) else str(args.source),
        "status": "RESEARCH_ONLY",
        "market_gate": "BLOCKED_TEAM_FOULS_NOT_OBSERVED",
        "sample_legs": len(samples),
        "sample_matches": len({sample.fixture_id for sample in samples}),
        "registered": {
            "validation_seasons": list(VALIDATION_SEASONS),
            "lines": list(LINES),
            "ema_decay": DECAY,
            "window": WINDOW,
            "minimum_history": MIN_HISTORY,
            "referee_k": REFEREE_K,
            "team_alpha_k": TEAM_ALPHA_K,
            "fixed_alpha": FIXED_ALPHA,
            "features": list(FEATURE_NAMES),
        },
        "folds": folds,
    }
    payload["decision"] = apply_gates(folds)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_report(payload), encoding="utf-8")
    write_csv(args.csv_out, folds)
    print(
        f"Team Fouls F1: samples={len(samples):,}; decision={payload['decision']['status']}; "
        f"report={args.report_out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
