#!/usr/bin/env python3
"""Registered corners v3 mean-model experiment.

The model uses only lagged inputs. WIDE and BLOCK are Understat proxies and the
script fails closed when their historical coverage is insufficient. Outputs are
research artifacts; no live selection or routing file is modified.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import runpy
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import numpy as np
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_counts import fit_dispersion_alpha_mle, nb_log_pmf, prob_over  # noqa: E402
from football_team_names import football_form_team_key  # noqa: E402
from football_market import brier, log_loss  # noqa: E402
from model_experiment_integrity import assert_variable_columns, verify_locked_input  # noqa: E402


DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_EVENTS = ROOT / "data" / "team-shots" / "understat" / "corner-event-features.csv"
DEFAULT_HISTORICAL = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_RESULTS = ROOT / "data" / "corners-ou" / "corners-v3-fold-results.csv"
DEFAULT_REPORT = ROOT / "data" / "corners-ou" / "corners-v3-fold-report.md"
DEFAULT_LOCK = ROOT / "data" / "corners-ou" / "corners-v3-lock.json"
VALIDATION_SEASONS = ("2024-2025", "2025-2026")
LINES = (7.5, 8.5, 9.5, 10.5, 11.5, 12.5)
DECAY = 0.93
WINDOW = 20
MIN_HISTORY = 6
MIN_EVENT_COVERAGE = 0.70
RIDGE = 0.01
FEATURE_NAMES = ("CF home", "CA away", "CF away", "CA home", "WIDE", "BLOCK", "TEMPO")


@dataclass
class EventState:
    wide_for: list[float] = field(default_factory=list)
    wide_against: list[float] = field(default_factory=list)
    block_for: list[float] = field(default_factory=list)
    block_against: list[float] = field(default_factory=list)

    def add(self, wide_for: float, wide_against: float, block_for: float, block_against: float) -> None:
        for history, value in (
            (self.wide_for, wide_for),
            (self.wide_against, wide_against),
            (self.block_for, block_for),
            (self.block_against, block_against),
        ):
            history.append(value)
            if len(history) > WINDOW:
                del history[0]

    @property
    def matches(self) -> int:
        return len(self.wide_for)

    @staticmethod
    def ema(values: list[float]) -> float:
        weights = [DECAY ** (len(values) - 1 - index) for index in range(len(values))]
        return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


@dataclass(frozen=True)
class Sample:
    match_date: date
    season: str
    league: str
    home_team: str
    away_team: str
    actual: int
    baseline_mean: float
    league_mean: float
    features: tuple[float, ...]


@dataclass(frozen=True)
class FittedModel:
    beta: tuple[float, ...]
    alpha: float
    centers: tuple[float, ...]
    scales: tuple[float, ...]
    feature_indices: tuple[int, ...]

    def predict(self, sample: Sample) -> float:
        selected = [sample.features[index] for index in self.feature_indices]
        standardized = [
            (value - center) / scale
            for value, center, scale in zip(selected, self.centers, self.scales)
        ]
        linear = self.beta[0] + sum(beta * value for beta, value in zip(self.beta[1:], standardized))
        return max(2.0, min(22.0, sample.league_mean * math.exp(linear)))


def pf(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


def normalized_name(value: Any) -> str:
    return football_form_team_key(value)


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing required input: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(match_date: Any, home: Any, away: Any) -> tuple[str, str, str]:
    return (str(match_date or "")[:10], normalized_name(home), normalized_name(away))


def baseline_lookup(historical: Path) -> dict[tuple[str, str, str], float]:
    module = runpy.run_path(str(SCRIPTS / "corners-ou-model.py"), run_name="corners_v3_baseline")
    matches = module["load_matches"](module["resolve_historical_input"](historical))
    rows, _ = module["run_model"](matches)
    return {
        fixture_key(row.get("date"), row.get("home_team"), row.get("away_team")): float(row["lambda_total"])
        for row in rows
    }


def preferred(row: dict[str, str], primary: str, fallback: str) -> float | None:
    return pf(row.get(primary), None) or pf(row.get(fallback), None)


def build_samples(
    form_rows: list[dict[str, str]],
    event_rows: list[dict[str, str]],
    baseline: dict[tuple[str, str, str], float],
) -> tuple[list[Sample], dict[str, float]]:
    events = {
        fixture_key(row.get("date"), row.get("home_team"), row.get("away_team")): row
        for row in event_rows
    }
    fixtures: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in form_rows:
        fixtures[(str(row.get("date")), str(row.get("league")), str(row.get("home_team")), str(row.get("away_team")))].append(row)

    states: dict[tuple[str, str], EventState] = defaultdict(EventState)
    samples: list[Sample] = []
    eligible_fixtures = 0
    event_matches = 0
    for key, rows in sorted(fixtures.items()):
        home_rows = [row for row in rows if row.get("venue") == "home"]
        away_rows = [row for row in rows if row.get("venue") == "away"]
        if len(home_rows) != 1 or len(away_rows) != 1:
            continue
        home, away = home_rows[0], away_rows[0]
        match_date = parse_date(home.get("date"))
        if match_date is None or match_date.year < 2019:
            continue
        eligible_fixtures += 1
        event = events.get(fixture_key(home.get("date"), home.get("home_team"), home.get("away_team")))
        league = str(home.get("league") or "")
        h_state = states[(league, normalized_name(home.get("team")))]
        a_state = states[(league, normalized_name(away.get("team")))]

        if event is not None:
            event_matches += 1
            league_corner_values = [
                pf(home.get("league_prior_corners_for_avg"), None),
                pf(away.get("league_prior_corners_for_avg"), None),
            ]
            valid_corner_values = [value for value in league_corner_values if value is not None and value > 0]
            league_team_corners = mean(valid_corner_values) if valid_corner_values else 4.9
            league_total = 2.0 * league_team_corners
            home_cf = preferred(home, "ema20_corners_for_home_avg", "ema20_corners_for_avg")
            home_ca = preferred(home, "ema20_corners_against_home_avg", "ema20_corners_against_avg")
            away_cf = preferred(away, "ema20_corners_for_away_avg", "ema20_corners_for_avg")
            away_ca = preferred(away, "ema20_corners_against_away_avg", "ema20_corners_against_avg")
            home_shots = pf(home.get("ema20_shots_for_avg"), None)
            away_shots = pf(away.get("ema20_shots_for_avg"), None)
            league_shots_values = [
                pf(home.get("league_prior_shots_for_avg"), None),
                pf(away.get("league_prior_shots_for_avg"), None),
            ]
            valid_shots = [value for value in league_shots_values if value is not None and value > 0]
            league_shots = mean(valid_shots) if valid_shots else 12.5
            actual_home = pf(home.get("current_corners_for"), None)
            actual_away = pf(away.get("current_corners_for"), None)
            base = baseline.get(fixture_key(home.get("date"), home.get("home_team"), home.get("away_team")))

            required = (home_cf, home_ca, away_cf, away_ca, home_shots, away_shots, actual_home, actual_away, base)
            if h_state.matches >= MIN_HISTORY and a_state.matches >= MIN_HISTORY and all(value is not None for value in required):
                wide = mean(
                    [
                        h_state.ema(h_state.wide_for),
                        h_state.ema(h_state.wide_against),
                        a_state.ema(a_state.wide_for),
                        a_state.ema(a_state.wide_against),
                    ]
                )
                blocked = mean(
                    [
                        h_state.ema(h_state.block_for),
                        h_state.ema(h_state.block_against),
                        a_state.ema(a_state.block_for),
                        a_state.ema(a_state.block_against),
                    ]
                )
                features = (
                    math.log(max(0.1, float(home_cf)) / league_team_corners),
                    math.log(max(0.1, float(away_ca)) / league_team_corners),
                    math.log(max(0.1, float(away_cf)) / league_team_corners),
                    math.log(max(0.1, float(home_ca)) / league_team_corners),
                    wide,
                    blocked,
                    math.log(max(0.1, float(home_shots) + float(away_shots)) / (2.0 * league_shots)),
                )
                samples.append(
                    Sample(
                        match_date=match_date,
                        season=str(home.get("season") or ""),
                        league=league,
                        home_team=str(home.get("home_team") or ""),
                        away_team=str(home.get("away_team") or ""),
                        actual=int(round(float(actual_home) + float(actual_away))),
                        baseline_mean=float(base),
                        league_mean=league_total,
                        features=features,
                    )
                )

            h_state.add(
                float(event.get("home_wide_share") or 0.0),
                float(event.get("away_wide_share") or 0.0),
                float(event.get("home_blocked_rate") or 0.0),
                float(event.get("away_blocked_rate") or 0.0),
            )
            a_state.add(
                float(event.get("away_wide_share") or 0.0),
                float(event.get("home_wide_share") or 0.0),
                float(event.get("away_blocked_rate") or 0.0),
                float(event.get("home_blocked_rate") or 0.0),
            )

    coverage = event_matches / max(1, eligible_fixtures)
    return samples, {
        "eligible_fixtures": eligible_fixtures,
        "event_matches": event_matches,
        "event_coverage": coverage,
        "model_samples": len(samples),
    }


def fit_model(training: list[Sample], feature_indices: tuple[int, ...] | None = None) -> FittedModel:
    indices = feature_indices or tuple(range(len(FEATURE_NAMES)))
    selected_rows = [tuple(sample.features[index] for index in indices) for sample in training]
    assert_variable_columns(selected_rows, [FEATURE_NAMES[index] for index in indices])
    feature_columns = list(zip(*selected_rows))
    centers = tuple(mean(column) for column in feature_columns)
    scales = tuple(max(1e-6, pstdev(column)) for column in feature_columns)
    matrix = np.asarray(
        [[1.0, *[(value - center) / scale for value, center, scale in zip(values, centers, scales)]] for values in selected_rows],
        dtype=float,
    )
    offsets = np.log(np.asarray([sample.league_mean for sample in training], dtype=float))
    actuals = np.asarray([sample.actual for sample in training], dtype=int)

    def objective(parameters: np.ndarray) -> float:
        beta = parameters[:-1]
        alpha = math.exp(float(parameters[-1]))
        means = np.clip(np.exp(offsets + matrix.dot(beta)), 2.0, 22.0)
        loss = -sum(nb_log_pmf(int(actual), float(mu), alpha) for actual, mu in zip(actuals, means))
        return float(loss + (RIDGE * np.dot(beta[1:], beta[1:])))

    initial = np.zeros(matrix.shape[1] + 1, dtype=float)
    initial[-1] = math.log(1.0 / 60.0)
    result = minimize(
        objective,
        initial,
        method="L-BFGS-B",
        bounds=[(None, None)] * matrix.shape[1] + [(math.log(1.0 / 500.0), math.log(0.8))],
        options={"maxiter": 300},
    )
    if not result.success:
        raise RuntimeError(f"NB regression failed: {result.message}")
    return FittedModel(
        beta=tuple(float(value) for value in result.x[:-1]),
        alpha=math.exp(float(result.x[-1])),
        centers=centers,
        scales=scales,
        feature_indices=indices,
    )


def score_fitted_model(model: FittedModel, validation: list[Sample]) -> dict[str, Any]:
    predictions = [model.predict(sample) for sample in validation]
    brier_total = 0.0
    log_loss_total = 0.0
    count = 0
    for sample, prediction in zip(validation, predictions):
        for line in LINES:
            actual_over = sample.actual > line
            probability = prob_over(line, prediction, distribution="negative_binomial", alpha=model.alpha)
            brier_total += brier(probability, actual_over)
            log_loss_total += log_loss(probability, actual_over)
            count += 1
    return {
        "mae": mean(abs(sample.actual - prediction) for sample, prediction in zip(validation, predictions)),
        "brier": brier_total / max(1, count),
        "log_loss": log_loss_total / max(1, count),
        "alpha": model.alpha,
        "beta": model.beta,
    }


def evaluate_fold(season: str, samples: list[Sample]) -> dict[str, Any]:
    validation = [sample for sample in samples if sample.season == season]
    if not validation:
        return {"season": season, "status": "NO_VALIDATION_ROWS"}
    start = min(sample.match_date for sample in validation)
    training = [sample for sample in samples if sample.match_date < start]
    if len(training) < 1000:
        return {"season": season, "status": "INSUFFICIENT_TRAIN_ROWS", "train": len(training)}
    ablation_specs = {
        "CF/CA": (0, 1, 2, 3),
        "CF/CA + TEMPO": (0, 1, 2, 3, 6),
        "FULL": tuple(range(len(FEATURE_NAMES))),
    }
    fitted = {name: fit_model(training, indices) for name, indices in ablation_specs.items()}
    ablation = {name: score_fitted_model(model, validation) for name, model in fitted.items()}
    model = fitted["FULL"]
    baseline_alpha = fit_dispersion_alpha_mle(
        [(sample.actual, sample.baseline_mean) for sample in training], min_sample=100
    )
    totals = {
        "baseline": {"brier": 0.0, "log_loss": 0.0, "n": 0},
        "v3": {"brier": 0.0, "log_loss": 0.0, "n": 0},
    }
    by_league: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {"baseline": {"brier": 0.0, "n": 0}, "v3": {"brier": 0.0, "n": 0}}
    )
    v3_means = []
    for sample in validation:
        v3_mean = model.predict(sample)
        v3_means.append(v3_mean)
        for line in LINES:
            actual_over = sample.actual > line
            probabilities = {
                "baseline": prob_over(line, sample.baseline_mean, distribution="negative_binomial", alpha=baseline_alpha),
                "v3": prob_over(line, v3_mean, distribution="negative_binomial", alpha=model.alpha),
            }
            for name, probability in probabilities.items():
                totals[name]["brier"] += brier(probability, actual_over)
                totals[name]["log_loss"] += log_loss(probability, actual_over)
                totals[name]["n"] += 1
                by_league[sample.league][name]["brier"] += brier(probability, actual_over)
                by_league[sample.league][name]["n"] += 1

    output: dict[str, Any] = {
        "season": season,
        "status": "OK",
        "train": len(training),
        "validation": len(validation),
        "baseline_mae": mean(abs(sample.actual - sample.baseline_mean) for sample in validation),
        "v3_mae": mean(abs(sample.actual - prediction) for sample, prediction in zip(validation, v3_means)),
        "baseline_bias": mean(sample.baseline_mean - sample.actual for sample in validation),
        "v3_bias": mean(prediction - sample.actual for sample, prediction in zip(validation, v3_means)),
        "baseline_alpha": baseline_alpha,
        "v3_alpha": model.alpha,
        "beta": model.beta,
        "ablation": ablation,
        "by_league": [],
    }
    for name, values in totals.items():
        output[f"{name}_brier"] = values["brier"] / max(1, values["n"])
        output[f"{name}_log_loss"] = values["log_loss"] / max(1, values["n"])
    for league, values in sorted(by_league.items()):
        output["by_league"].append(
            {
                "league": league,
                "matches": int(values["v3"]["n"] / len(LINES)),
                "baseline_brier": values["baseline"]["brier"] / max(1, values["baseline"]["n"]),
                "v3_brier": values["v3"]["brier"] / max(1, values["v3"]["n"]),
            }
        )
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = (
        "season", "status", "train", "validation", "baseline_mae", "v3_mae", "baseline_bias", "v3_bias",
        "baseline_alpha", "v3_alpha", "baseline_brier", "v3_brier", "baseline_log_loss", "v3_log_loss",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def write_report(path: Path, coverage: dict[str, float], folds: list[dict[str, Any]]) -> None:
    coverage_ok = coverage["event_coverage"] >= MIN_EVENT_COVERAGE
    count_gate = coverage_ok and bool(folds) and all(
        row.get("status") == "OK"
        and row["v3_mae"] < row["baseline_mae"]
        and row["v3_brier"] < row["baseline_brier"]
        and row["v3_log_loss"] < row["baseline_log_loss"]
        and all(
            league["v3_brier"] <= league["baseline_brier"]
            for league in row.get("by_league", [])
        )
        for row in folds
    )
    lines = [
        "# Corners v3 registered experiment",
        "",
        "**Status: research only. Corners publication remains blocked.**",
        "",
        "## Event-feature coverage",
        "",
        f"- Eligible 2019+ top-five fixtures: {int(coverage['eligible_fixtures'])}",
        f"- Matched Understat event fixtures: {int(coverage['event_matches'])}",
        f"- Coverage: {coverage['event_coverage']:.1%} (required {MIN_EVENT_COVERAGE:.0%})",
        f"- Lagged model samples after history gate: {int(coverage['model_samples'])}",
        f"- Coverage gate: **{'PASS' if coverage_ok else 'DATA_BLOCKED'}**",
        f"- Count-model gate: **{'PASS' if count_gate else 'FAIL'}**",
        "- Market/sell gate: **BLOCKED** pending the registered 2026-27 real-price sample.",
        "",
        "WIDE is `abs(Y-0.5)>=0.18`; BLOCK is the Understat `BlockedShot` rate. Both are lagged EMA20 proxies.",
        "",
        "## Walk-forward folds",
        "",
        "| Fold | Train | Validation | Baseline MAE | v3 MAE | Baseline Brier | v3 Brier | Baseline log loss | v3 log loss |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in folds:
        if row.get("status") != "OK":
            lines.append(f"| {row['season']} | {row.get('train', '-')} | - | - | - | - | - | - | **{row['status']}** |")
            continue
        lines.append(
            f"| {row['season']} | {row['train']} | {row['validation']} | {row['baseline_mae']:.4f} | {row['v3_mae']:.4f} | "
            f"{row['baseline_brier']:.4f} | {row['v3_brier']:.4f} | {row['baseline_log_loss']:.4f} | {row['v3_log_loss']:.4f} |"
        )
    lines.extend(["", "### Per-league Brier guard", "", "| Fold | League | Matches | Baseline | v3 | Delta |", "|---|---|---:|---:|---:|---:|"])
    for row in folds:
        for league in row.get("by_league", []):
            delta = league["v3_brier"] - league["baseline_brier"]
            lines.append(
                f"| {row['season']} | {league['league']} | {league['matches']} | {league['baseline_brier']:.4f} | {league['v3_brier']:.4f} | {delta:+.4f} |"
            )
    lines.extend(
        [
            "",
            "### Pre-registered feature ablation",
            "",
            "| Fold | Variant | MAE | Brier | Log loss | NB alpha |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in folds:
        for name, values in row.get("ablation", {}).items():
            lines.append(
                f"| {row['season']} | {name} | {values['mae']:.4f} | {values['brier']:.4f} | "
                f"{values['log_loss']:.4f} | {values['alpha']:.4f} |"
            )
    lines.extend(
        [
            "",
            "### Standardized fitted coefficients",
            "",
            "Coefficients are fitted on each fold's training window only. They are shown for auditability, not causal interpretation.",
            "",
            "| Fold | Intercept | " + " | ".join(FEATURE_NAMES) + " | NB alpha |",
            "|---|---:|" + "---:|" * len(FEATURE_NAMES) + "---:|",
        ]
    )
    for row in folds:
        if row.get("status") != "OK":
            continue
        coefficients = " | ".join(f"{value:+.3f}" for value in row["beta"])
        lines.append(f"| {row['season']} | {coefficients} | {row['v3_alpha']:.4f} |")
    lines.extend(
        [
            "",
            "## Market gate",
            "",
            "**BLOCKED.** Historical 2024-25/2025-26 Pinnacle corner prices do not exist in this repository. "
            "Count accuracy can reject v3, but cannot promote it. The 2026-27 prospective window must beat de-vigged real Pinnacle Brier and log loss.",
            "",
            "If the count folds fail, corners v3 is killed before prospective selection. If they pass, it enters shadow only; it does not become sellable.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--historical", type=Path, default=DEFAULT_HISTORICAL)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args()

    verify_locked_input(args.lock, "team_rolling_form", args.form)
    samples, coverage = build_samples(
        load_csv(args.form),
        load_csv(args.events),
        baseline_lookup(args.historical),
    )
    folds = [evaluate_fold(season, samples) for season in VALIDATION_SEASONS]
    write_csv(args.results, folds)
    write_report(args.report, coverage, folds)
    print(f"Coverage={coverage['event_coverage']:.1%}; samples={len(samples)}")
    print(f"Wrote {args.results.resolve().relative_to(ROOT)}")
    print(f"Wrote {args.report.resolve().relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
