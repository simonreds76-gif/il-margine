#!/usr/bin/env python3
"""Held-out ablation for opponent-position concessions and fixture rest.

This script is deliberately research-only. It reuses the production goalscorer
probabilities, builds context features strictly from matches before each scored
fixture, and compares a standard calibration against the context extension on
the untouched 2025-26 season.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "scripts" / "goalscorer-model.py"
DEFAULT_OUT_DIR = ROOT / "data" / "goalscorer" / "backtest"
LEAGUES = ("epl", "serie-a", "la-liga", "bundesliga", "ligue-1")
TRAIN_SEASONS = {"2023-2024", "2024-2025"}
TEST_SEASON = "2025-2026"
POSITION_PRIOR_NPXG = {
    "forward": 0.48,
    "attacking_midfield": 0.31,
    "midfield": 0.18,
    "defender": 0.10,
    "other": 0.16,
}
SHRINK_MATCHES = 8.0
HISTORY_WINDOW = 20


@dataclass(frozen=True)
class Context:
    opponent_position_factor: float
    opponent_position_matches: int
    team_rest_days: float
    opponent_rest_days: float
    team_short_rest: float
    opponent_short_rest: float
    rest_advantage: float


def load_model_module() -> Any:
    spec = importlib.util.spec_from_file_location("goalscorer_model_context", MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def position_bucket(value: str) -> str:
    position = str(value or "").split(",")[0].strip().upper()
    if position.startswith("FW") or position in {"ST", "CF"}:
        return "forward"
    if position.startswith("AM") or position in {"LW", "RW", "W"}:
        return "attacking_midfield"
    if position.startswith("M") or position.startswith("DM"):
        return "midfield"
    if position.startswith("D") or position.startswith("WB"):
        return "defender"
    return "other"


def _context_key(row: Any) -> tuple[str, str, str, str]:
    return row.match_date_str, row.player_id, row.team_key, row.opponent_key


def build_causal_context(rows: list[Any]) -> dict[tuple[str, str, str, str], Context]:
    """Build features before updating state with the current match date."""
    defense_history: dict[tuple[str, str], list[float]] = defaultdict(list)
    league_position_history: dict[str, list[float]] = defaultdict(list)
    last_match: dict[str, date] = {}
    output: dict[tuple[str, str, str, str], Context] = {}

    by_date: dict[date, list[Any]] = defaultdict(list)
    for row in rows:
        by_date[row.match_date].append(row)

    for match_date in sorted(by_date):
        date_rows = by_date[match_date]
        fixture_sides: dict[tuple[str, str, bool], list[Any]] = defaultdict(list)
        for row in date_rows:
            fixture_sides[(row.team_key, row.opponent_key, row.is_home)].append(row)

        for (team_key, opponent_key, _is_home), team_rows in fixture_sides.items():
            team_previous = last_match.get(team_key)
            opponent_previous = last_match.get(opponent_key)
            team_rest = float((match_date - team_previous).days) if team_previous else 7.0
            opponent_rest = float((match_date - opponent_previous).days) if opponent_previous else 7.0
            team_rest = min(max(team_rest, 1.0), 21.0)
            opponent_rest = min(max(opponent_rest, 1.0), 21.0)

            for row in team_rows:
                bucket = position_bucket(row.position)
                team_samples = defense_history[(opponent_key, bucket)][-HISTORY_WINDOW:]
                league_samples = league_position_history[bucket][-400:]
                prior = (
                    sum(league_samples) / len(league_samples)
                    if league_samples
                    else POSITION_PRIOR_NPXG[bucket]
                )
                observed = sum(team_samples) / len(team_samples) if team_samples else prior
                shrunk = (
                    (observed * len(team_samples)) + (prior * SHRINK_MATCHES)
                ) / (len(team_samples) + SHRINK_MATCHES)
                factor = max(0.70, min(1.40, shrunk / prior if prior > 0 else 1.0))
                output[_context_key(row)] = Context(
                    opponent_position_factor=factor,
                    opponent_position_matches=len(team_samples),
                    team_rest_days=team_rest,
                    opponent_rest_days=opponent_rest,
                    team_short_rest=1.0 if team_rest <= 3.0 else 0.0,
                    opponent_short_rest=1.0 if opponent_rest <= 3.0 else 0.0,
                    rest_advantage=max(-1.0, min(1.0, (team_rest - opponent_rest) / 7.0)),
                )

        # Aggregate each attacking side once, then record what its opponent conceded.
        for (_team_key, opponent_key, _is_home), team_rows in fixture_sides.items():
            by_position: dict[str, float] = defaultdict(float)
            for row in team_rows:
                by_position[position_bucket(row.position)] += max(float(row.npxg or 0.0), 0.0)
            for bucket, conceded_npxg in by_position.items():
                defense_history[(opponent_key, bucket)].append(conceded_npxg)
                league_position_history[bucket].append(conceded_npxg)

        for team_key, _opponent_key, _is_home in fixture_sides:
            last_match[team_key] = match_date

    return output


def sigmoid(value: float) -> float:
    if value >= 0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def logit(probability: float) -> float:
    probability = min(max(probability, 1e-6), 1.0 - 1e-6)
    return math.log(probability / (1.0 - probability))


def solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for pivot in range(size):
        best = max(range(pivot, size), key=lambda row: abs(augmented[row][pivot]))
        if abs(augmented[best][pivot]) < 1e-10:
            raise RuntimeError("Singular context calibration matrix")
        augmented[pivot], augmented[best] = augmented[best], augmented[pivot]
        scale = augmented[pivot][pivot]
        augmented[pivot] = [value / scale for value in augmented[pivot]]
        for row in range(size):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            augmented[row] = [
                current - (factor * source)
                for current, source in zip(augmented[row], augmented[pivot])
            ]
    return [augmented[index][-1] for index in range(size)]


def fit_logistic(rows: list[dict[str, Any]], fields: tuple[str, ...], ridge: float = 1.0) -> list[float]:
    coefficients = [0.0] * (len(fields) + 1)
    for _ in range(60):
        gradient = [0.0] * len(coefficients)
        information = [[0.0] * len(coefficients) for _ in coefficients]
        for row in rows:
            features = [1.0] + [float(row[field]) for field in fields]
            prediction = sigmoid(sum(coef * value for coef, value in zip(coefficients, features)))
            residual = float(row["scored"]) - prediction
            weight = max(prediction * (1.0 - prediction), 1e-8)
            for left in range(len(coefficients)):
                gradient[left] += features[left] * residual
                for right in range(len(coefficients)):
                    information[left][right] += weight * features[left] * features[right]
        for index in range(1, len(coefficients)):
            gradient[index] -= ridge * coefficients[index]
            information[index][index] += ridge
        update = solve_linear(information, gradient)
        coefficients = [value + delta for value, delta in zip(coefficients, update)]
        if max(abs(delta) for delta in update) < 1e-7:
            break
    return coefficients


def predict(row: dict[str, Any], fields: tuple[str, ...], coefficients: list[float]) -> float:
    features = [1.0] + [float(row[field]) for field in fields]
    return sigmoid(sum(coef * value for coef, value in zip(coefficients, features)))


def metrics(rows: Iterable[dict[str, Any]], probability_field: str) -> dict[str, float | int]:
    materialized = list(rows)
    if not materialized:
        return {"n": 0, "brier": 0.0, "log_loss": 0.0, "predicted": 0.0, "actual": 0.0}
    probabilities = [min(max(float(row[probability_field]), 1e-6), 1.0 - 1e-6) for row in materialized]
    outcomes = [float(row["scored"]) for row in materialized]
    return {
        "n": len(materialized),
        "brier": sum((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes)) / len(materialized),
        "log_loss": -sum(
            outcome * math.log(probability) + (1.0 - outcome) * math.log(1.0 - probability)
            for probability, outcome in zip(probabilities, outcomes)
        ) / len(materialized),
        "predicted": sum(probabilities) / len(materialized),
        "actual": sum(outcomes) / len(materialized),
    }


def build_rows(model: Any) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    seasons = ("2023-2024", "2024-2025", "2025-2026")
    for league in LEAGUES:
        paths = [ROOT / "data" / "goalscorer" / f"{league}-player-match-logs-{season}.csv" for season in seasons]
        rows = model.load_match_logs([str(path) for path in paths if path.exists()])
        if not rows:
            continue
        model.V2_REPAIR_ENABLED = False
        model.LEAGUE_AVG = model.league_avg_for(league, model.infer_league_penalties_per_match(rows))
        context = build_causal_context(rows)
        results, _stats = model.run_backtest(rows)
        for result in results:
            if result.get("method") != "model":
                continue
            key = (
                str(result["match_date"]),
                str(result["player_id"]),
                model._team_key(str(result["team"])),
                model._team_key(str(result["opponent"])),
            )
            feature = context.get(key)
            if feature is None:
                continue
            combined.append(
                {
                    **result,
                    "league": league,
                    "base_logit": logit(float(result["model_p_atgs"])),
                    "opponent_position_factor": feature.opponent_position_factor,
                    "opponent_position_log_factor": math.log(feature.opponent_position_factor),
                    "opponent_position_matches": feature.opponent_position_matches,
                    "team_rest_days": feature.team_rest_days,
                    "opponent_rest_days": feature.opponent_rest_days,
                    "team_short_rest": feature.team_short_rest,
                    "opponent_short_rest": feature.opponent_short_rest,
                    "rest_advantage": feature.rest_advantage,
                }
            )
    return combined


def main() -> int:
    parser = argparse.ArgumentParser(description="Held-out goalscorer context-feature ablation")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    model = load_model_module()
    rows = build_rows(model)
    train = [row for row in rows if row["season"] in TRAIN_SEASONS]
    holdout = [row for row in rows if row["season"] == TEST_SEASON]
    if not train or not holdout:
        raise SystemExit(f"Insufficient train/holdout rows: train={len(train)}, holdout={len(holdout)}")

    calibration_fields = ("base_logit",)
    context_fields = (
        "base_logit",
        "opponent_position_log_factor",
        "team_short_rest",
        "opponent_short_rest",
        "rest_advantage",
    )
    calibration_coefficients = fit_logistic(train, calibration_fields)
    context_coefficients = fit_logistic(train, context_fields)
    for row in rows:
        row["base_probability"] = float(row["model_p_atgs"])
        row["calibrated_probability"] = predict(row, calibration_fields, calibration_coefficients)
        row["context_probability"] = predict(row, context_fields, context_coefficients)

    holdout_base = metrics(holdout, "base_probability")
    holdout_calibrated = metrics(holdout, "calibrated_probability")
    holdout_context = metrics(holdout, "context_probability")
    league_rows: list[dict[str, Any]] = []
    harmful_leagues = 0
    for league in LEAGUES:
        league_holdout = [row for row in holdout if row["league"] == league]
        calibrated = metrics(league_holdout, "calibrated_probability")
        context_result = metrics(league_holdout, "context_probability")
        delta = float(context_result["brier"]) - float(calibrated["brier"])
        if int(context_result["n"]) >= 500 and delta > 0.002:
            harmful_leagues += 1
        league_rows.append(
            {
                "league": league,
                "n": context_result["n"],
                "calibrated_brier": round(float(calibrated["brier"]), 7),
                "context_brier": round(float(context_result["brier"]), 7),
                "brier_delta": round(delta, 7),
                "calibrated_log_loss": round(float(calibrated["log_loss"]), 7),
                "context_log_loss": round(float(context_result["log_loss"]), 7),
            }
        )

    brier_delta = float(holdout_context["brier"]) - float(holdout_calibrated["brier"])
    log_loss_delta = float(holdout_context["log_loss"]) - float(holdout_calibrated["log_loss"])
    accepted = len(holdout) >= 5000 and brier_delta < 0 and log_loss_delta < 0 and harmful_leagues == 0
    decision = "QUALIFIES_FOR_PROSPECTIVE_SHADOW" if accepted else "REJECTED_OR_MORE_EVIDENCE_REQUIRED"

    detail_fields = [
        "league", "season", "match_date", "player_id", "player_name", "team", "opponent",
        "position_group", "expected_minutes", "scored", "base_probability", "calibrated_probability",
        "context_probability", "opponent_position_factor", "opponent_position_matches",
        "team_rest_days", "opponent_rest_days", "team_short_rest", "opponent_short_rest", "rest_advantage",
    ]
    detail_path = args.out_dir / "goalscorer-context-ablation.csv"
    with detail_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=detail_fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(holdout)

    league_path = args.out_dir / "goalscorer-context-ablation-leagues.csv"
    with league_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(league_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(league_rows)

    report_path = args.out_dir / "goalscorer-context-ablation.txt"
    with report_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("Goalscorer Context Feature Ablation\n")
        handle.write("===================================\n\n")
        handle.write("Research only. No live probabilities, routing, stakes, or public output changed.\n")
        handle.write(f"Train seasons: {', '.join(sorted(TRAIN_SEASONS))}; n={len(train):,}\n")
        handle.write(f"Held-out season: {TEST_SEASON}; n={len(holdout):,}\n")
        handle.write(f"Decision: {decision}\n\n")
        for label, result in (
            ("Raw production probability", holdout_base),
            ("Base logistic recalibration", holdout_calibrated),
            ("Context extension", holdout_context),
        ):
            handle.write(
                f"{label}: Brier={float(result['brier']):.7f}; log_loss={float(result['log_loss']):.7f}; "
                f"predicted={float(result['predicted']):.4f}; actual={float(result['actual']):.4f}\n"
            )
        handle.write(f"\nContext minus calibrated Brier: {brier_delta:+.7f}\n")
        handle.write(f"Context minus calibrated log loss: {log_loss_delta:+.7f}\n")
        handle.write(f"Leagues materially harmed (>0.002 Brier, n>=500): {harmful_leagues}\n")
        handle.write("\nContext coefficients\n--------------------\n")
        for name, value in zip(("intercept",) + context_fields, context_coefficients):
            handle.write(f"{name}: {value:+.6f}\n")
        handle.write("\nLeague holdout\n--------------\n")
        for row in league_rows:
            handle.write(
                f"{row['league']}: n={row['n']}; Brier delta={row['brier_delta']:+.7f}; "
                f"log-loss delta={row['context_log_loss'] - row['calibrated_log_loss']:+.7f}\n"
            )

    print(f"{decision}: holdout={len(holdout):,}, Brier delta={brier_delta:+.7f}, log-loss delta={log_loss_delta:+.7f}")
    print(f"Wrote {detail_path}")
    print(f"Wrote {league_path}")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
