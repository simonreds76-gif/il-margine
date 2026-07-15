#!/usr/bin/env python3
"""Registered Team Fouls F2 Poisson experiment on the locked F1 holdouts.

F2 deliberately removes the referee, cards, closeness and NB complexity. The
mean model retains only causal team form, opponent fouls-drawn form and opening
market strength. It never emits betting signals and cannot clear the separate
market-price or settlement-definition gates.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_counts import prob_over  # noqa: E402
from football_market import brier, log_loss  # noqa: E402


DEFAULT_SOURCE = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_F1 = ROOT / "data" / "football-form" / "team-fouls-v1-fold-report.json"
DEFAULT_CSV = ROOT / "data" / "football-form" / "team-fouls-f2-fold-results.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "team-fouls-f2-fold-report.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "team-fouls-f2-fold-report.md"
FEATURE_INDICES = (0, 1, 4)
CORE_INDICES = (0, 1)
FEATURE_NAMES = ("team_committed", "opponent_drawn", "opening_strength")
RIDGE = 0.01
MAX_RELIABILITY_GAP = 0.02
MIN_MAE_IMPROVEMENT_PCT = 5.0
MIN_INCREMENTAL_NLL_GAIN = 0.0015


def load_f1_module() -> Any:
    path = SCRIPTS / "team-fouls-v1-folds.py"
    spec = importlib.util.spec_from_file_location("team_fouls_f1_harness", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load F1 harness: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


F1 = load_f1_module()
VALIDATION_SEASONS = F1.VALIDATION_SEASONS
LINES = F1.LINES
LEAGUES = F1.LEAGUES


@dataclass(frozen=True)
class PoissonMeanModel:
    beta: tuple[float, ...]
    centers: tuple[float, ...]
    scales: tuple[float, ...]
    indices: tuple[int, ...]

    def predict(self, sample: Any) -> float:
        selected = [sample.features[index] for index in self.indices]
        standardized = [
            (value - center) / scale
            for value, center, scale in zip(selected, self.centers, self.scales)
        ]
        linear = self.beta[0] + sum(
            weight * value for weight, value in zip(self.beta[1:], standardized)
        )
        return max(2.0, min(28.0, sample.baseline_mean * math.exp(linear)))


def poisson_log_pmf(actual: int, mean: float) -> float:
    return (actual * math.log(mean)) - mean - math.lgamma(actual + 1.0)


def fit_poisson(training: list[Any], indices: tuple[int, ...]) -> PoissonMeanModel:
    selected = [tuple(sample.features[index] for index in indices) for sample in training]
    columns = list(zip(*selected))
    centers = tuple(statistics.fmean(column) for column in columns)
    scales = tuple(max(1e-6, statistics.pstdev(column)) for column in columns)
    matrix = np.asarray(
        [
            [1.0, *[(value - center) / scale for value, center, scale in zip(row, centers, scales)]]
            for row in selected
        ],
        dtype=float,
    )
    offsets = np.log(np.asarray([sample.baseline_mean for sample in training], dtype=float))
    actuals = np.asarray([sample.actual for sample in training], dtype=float)

    def objective(beta: np.ndarray) -> float:
        means = np.clip(np.exp(offsets + matrix.dot(beta)), 2.0, 28.0)
        nll = float(np.sum(means - (actuals * np.log(means))))
        return nll + (RIDGE * float(np.dot(beta[1:], beta[1:])))

    result = minimize(
        objective,
        np.zeros(matrix.shape[1], dtype=float),
        method="L-BFGS-B",
        options={"maxiter": 350},
    )
    if not result.success:
        raise RuntimeError(f"Team Fouls F2 Poisson regression failed: {result.message}")
    return PoissonMeanModel(
        beta=tuple(float(value) for value in result.x),
        centers=centers,
        scales=scales,
        indices=indices,
    )


def count_metrics(model: PoissonMeanModel, rows: list[Any]) -> dict[str, float]:
    means = [model.predict(sample) for sample in rows]
    return {
        "mae": statistics.fmean(abs(sample.actual - mean) for sample, mean in zip(rows, means)),
        "nll": -statistics.fmean(
            poisson_log_pmf(sample.actual, mean) for sample, mean in zip(rows, means)
        ),
        "bias": statistics.fmean(mean - sample.actual for sample, mean in zip(rows, means)),
    }


def probability_metrics(model: PoissonMeanModel, rows: list[Any]) -> dict[str, Any]:
    scores: list[tuple[float, int]] = []
    by_league: dict[str, list[tuple[float, int]]] = {league: [] for league in LEAGUES}
    for sample in rows:
        mean = model.predict(sample)
        for line in LINES:
            probability = prob_over(line, mean, distribution="poisson")
            outcome = int(sample.actual > line)
            scores.append((probability, outcome))
            by_league[sample.league].append((probability, outcome))

    def summarize(items: list[tuple[float, int]]) -> dict[str, float | int]:
        return {
            "n": len(items),
            "brier": statistics.fmean(brier(probability, bool(outcome)) for probability, outcome in items),
            "log_loss": statistics.fmean(log_loss(probability, bool(outcome)) for probability, outcome in items),
        }

    return {
        **summarize(scores),
        "reliability": F1.reliability(scores),
        "by_league": [
            {"league": league, "matches": int(len(items) / len(LINES)), **summarize(items)}
            for league, items in by_league.items()
            if items
        ],
    }


def baseline_probability_metrics(rows: list[Any]) -> dict[str, float]:
    scores = [
        (prob_over(line, sample.baseline_mean, distribution="poisson"), int(sample.actual > line))
        for sample in rows
        for line in LINES
    ]
    return {
        "brier": statistics.fmean(brier(probability, bool(outcome)) for probability, outcome in scores),
        "log_loss": statistics.fmean(log_loss(probability, bool(outcome)) for probability, outcome in scores),
    }


def f1_control_for(f1_report: dict[str, Any], season: str) -> dict[str, float]:
    fold = next((item for item in f1_report.get("folds", []) if item.get("season") == season), {})
    distribution = fold.get("distribution") or {}
    return {
        "poisson_brier": float(distribution.get("poisson_brier", 1.0)),
        "poisson_log_loss": float(distribution.get("poisson_log_loss", 10.0)),
        "hierarchical_nb_brier": float(distribution.get("hierarchical_nb_brier", 1.0)),
        "hierarchical_nb_log_loss": float(distribution.get("hierarchical_nb_log_loss", 10.0)),
    }


def evaluate_fold(season: str, samples: list[Any], f1_report: dict[str, Any]) -> dict[str, Any]:
    validation = [sample for sample in samples if sample.season == season]
    if not validation:
        return {"season": season, "status": "NO_VALIDATION_ROWS"}
    validation_start = min(sample.match_date for sample in validation)
    training = [sample for sample in samples if sample.match_date < validation_start]
    if len(training) < 5000:
        return {"season": season, "status": "INSUFFICIENT_TRAIN_ROWS", "train": len(training)}

    core = fit_poisson(training, CORE_INDICES)
    f2 = fit_poisson(training, FEATURE_INDICES)
    core_metrics = count_metrics(core, validation)
    f2_metrics = count_metrics(f2, validation)
    baseline_mae = statistics.fmean(
        abs(sample.actual - sample.baseline_mean) for sample in validation
    )
    return {
        "season": season,
        "status": "OK",
        "train": len(training),
        "validation_legs": len(validation),
        "validation_matches": len({sample.fixture_id for sample in validation}),
        "causal_baseline_mae": baseline_mae,
        "baseline_probability": baseline_probability_metrics(validation),
        "core": core_metrics,
        "f2": f2_metrics,
        "opening_strength_transition": {
            "delta_nll": f2_metrics["nll"] - core_metrics["nll"],
            "delta_mae": f2_metrics["mae"] - core_metrics["mae"],
        },
        "coefficients": {
            name: value for name, value in zip(("intercept", *FEATURE_NAMES), f2.beta)
        },
        "poisson": probability_metrics(f2, validation),
        "f1_control": f1_control_for(f1_report, season),
    }


def apply_gates(folds: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [fold for fold in folds if fold.get("status") == "OK"]
    checks: list[dict[str, Any]] = []
    for fold in valid:
        improvement = 100.0 * (
            fold["causal_baseline_mae"] - fold["f2"]["mae"]
        ) / fold["causal_baseline_mae"]
        transition = fold["opening_strength_transition"]
        checks.append(
            {
                "season": fold["season"],
                "mae_improvement_pct": improvement,
                "opening_strength_pass": transition["delta_nll"] <= -MIN_INCREMENTAL_NLL_GAIN
                and transition["delta_mae"] <= 1e-9,
                "baseline_probability_pass": fold["poisson"]["brier"]
                < fold["baseline_probability"]["brier"]
                and fold["poisson"]["log_loss"] < fold["baseline_probability"]["log_loss"],
                "f1_distribution_pass": fold["poisson"]["brier"]
                <= fold["f1_control"]["hierarchical_nb_brier"]
                and fold["poisson"]["log_loss"]
                <= fold["f1_control"]["hierarchical_nb_log_loss"],
                "reliability_pass": fold["poisson"]["reliability"]["max_abs_gap"]
                <= MAX_RELIABILITY_GAP,
            }
        )
    gates = {
        "folds_complete": len(valid) == len(VALIDATION_SEASONS),
        "mae_improvement": bool(checks)
        and all(item["mae_improvement_pct"] >= MIN_MAE_IMPROVEMENT_PCT for item in checks),
        "opening_strength_increment": bool(checks)
        and all(item["opening_strength_pass"] for item in checks),
        "beats_causal_probability_baseline": bool(checks)
        and all(item["baseline_probability_pass"] for item in checks),
        "poisson_beats_f1_distribution": bool(checks)
        and all(item["f1_distribution_pass"] for item in checks),
        "reliability": bool(checks) and all(item["reliability_pass"] for item in checks),
        "market_prices": False,
        "settlement_definition": False,
    }
    count_gate = all(
        passed for name, passed in gates.items() if name not in {"market_prices", "settlement_definition"}
    )
    return {
        "status": "COUNT_GATE_PASS_EXTERNAL_GATES_BLOCKED"
        if count_gate
        else "COUNT_GATE_FAIL_EXTERNAL_GATES_BLOCKED",
        "count_gate_pass": count_gate,
        "market_gate_pass": False,
        "settlement_gate_pass": False,
        "signals_authorized": False,
        "gates": gates,
        "fold_checks": checks,
    }


def render_report(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    lines = [
        "# Team Fouls F2: Registered Poisson Holdout",
        "",
        f"Generated: {payload['generated_at']}",
        f"Samples: {payload['sample_legs']:,} team legs across {payload['sample_matches']:,} matches.",
        "",
        f"**Decision: {decision['status'].replace('_', ' ')}. Signals remain disabled.**",
        "",
        "F2 uses only team committed form, opponent fouls-drawn form and opening-market strength. It uses the locked F1 holdouts and performs no threshold or feature sweep.",
        "",
        "| Fold | Baseline MAE | F2 MAE | Improvement | Strength dNLL | Strength dMAE | F2 Brier | F1 NB Brier | Max decile gap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for fold in payload["folds"]:
        if fold.get("status") != "OK":
            lines.append(f"| {fold['season']} | - | - | - | - | - | - | - | {fold['status']} |")
            continue
        improvement = 100.0 * (fold["causal_baseline_mae"] - fold["f2"]["mae"]) / fold["causal_baseline_mae"]
        transition = fold["opening_strength_transition"]
        lines.append(
            f"| {fold['season']} | {fold['causal_baseline_mae']:.3f} | {fold['f2']['mae']:.3f} | {improvement:+.2f}% | "
            f"{transition['delta_nll']:+.5f} | {transition['delta_mae']:+.5f} | {fold['poisson']['brier']:.4f} | "
            f"{fold['f1_control']['hierarchical_nb_brier']:.4f} | {fold['poisson']['reliability']['max_abs_gap']:.2%} |"
        )
    lines.extend(["", "## Gate summary", ""])
    for name, passed in decision["gates"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'}: `{name}`")
    lines.extend(
        [
            "",
            "## Product status",
            "",
            "- Research only; no candidate, stake, ROI or CLV row is produced.",
            "- Paired Bet365 team-fouls O/U prices remain a hard external gate.",
            "- Settlement source agreement remains a hard external gate.",
            "- A count-gate pass alone never authorizes tips.",
            "",
        ]
    )
    return "\n".join(lines)


def write_csv(path: Path, folds: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for fold in folds:
        if fold.get("status") != "OK":
            rows.append({"season": fold["season"], "status": fold["status"]})
            continue
        rows.append(
            {
                "season": fold["season"],
                "status": fold["status"],
                "train_legs": fold["train"],
                "validation_matches": fold["validation_matches"],
                "baseline_mae": fold["causal_baseline_mae"],
                "f2_mae": fold["f2"]["mae"],
                "f2_nll": fold["f2"]["nll"],
                "opening_strength_delta_nll": fold["opening_strength_transition"]["delta_nll"],
                "opening_strength_delta_mae": fold["opening_strength_transition"]["delta_mae"],
                "poisson_brier": fold["poisson"]["brier"],
                "poisson_log_loss": fold["poisson"]["log_loss"],
                "max_reliability_gap": fold["poisson"]["reliability"]["max_abs_gap"],
            }
        )
    fields = sorted({field for row in rows for field in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run registered Team Fouls F2 Poisson folds.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--f1-report", type=Path, default=DEFAULT_F1)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    samples = F1.build_samples(F1.load_csv(args.source))
    f1_report = json.loads(args.f1_report.read_text(encoding="utf-8"))
    folds = [evaluate_fold(season, samples, f1_report) for season in VALIDATION_SEASONS]
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": str(args.source.relative_to(ROOT)).replace("\\", "/")
        if args.source.is_relative_to(ROOT)
        else str(args.source),
        "status": "RESEARCH_ONLY",
        "market_gate": "BLOCKED_TEAM_FOULS_NOT_OBSERVED",
        "settlement_gate": "BLOCKED_SOURCE_AGREEMENT_INCOMPLETE",
        "sample_legs": len(samples),
        "sample_matches": len({sample.fixture_id for sample in samples}),
        "registered": {
            "validation_seasons": list(VALIDATION_SEASONS),
            "lines": list(LINES),
            "mean_features": list(FEATURE_NAMES),
            "distribution": "poisson",
            "minimum_mae_improvement_pct": MIN_MAE_IMPROVEMENT_PCT,
            "minimum_opening_strength_nll_gain": MIN_INCREMENTAL_NLL_GAIN,
            "maximum_reliability_gap": MAX_RELIABILITY_GAP,
            "threshold_sweep": False,
        },
        "folds": folds,
    }
    payload["decision"] = apply_gates(folds)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_report(payload), encoding="utf-8")
    write_csv(args.csv_out, folds)
    print(
        f"Team Fouls F2: samples={len(samples):,}; decision={payload['decision']['status']}; "
        f"report={args.report_out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
