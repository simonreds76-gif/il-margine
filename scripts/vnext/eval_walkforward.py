#!/usr/bin/env python3
"""Locked 2024 selection and single-shot 2025 paired vNext MVE evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from common import DEFAULT_OUTPUT_DIR, ROOT, read_rows_csv_gz, sha256_file, write_json
from fit_offline import fit_models
from model_spec import DynamicResiduals, ProcessModel, PROCESS_SPECS, VERSION, serve_point_probability, update_process

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.lib.tennis_prob import prob_match_best_of_3, prob_match_best_of_5


BACKTEST_DIR = ROOT / "data" / "backtest"
REGISTRATION = DEFAULT_OUTPUT_DIR / "experiment-registration-v0.1.json"
REPORT = BACKTEST_DIR / "vnext-mve-report.txt"
PREDICTIONS = DEFAULT_OUTPUT_DIR / "vnext-mve-predictions.csv"
LEDGER = DEFAULT_OUTPUT_DIR / "vnext-mve-test-ledger.json"


def _typed(row: dict[str, str]) -> dict[str, object]:
    numeric = {"date_ord", "year", "tour_rank", "round_id", "server_id", "returner_id", "server_won_match", "serve_points", "first_in", "first_won", "second_attempts", "second_in", "second_won", "aces", "double_faults"}
    return {key: int(value) if key in numeric else value for key, value in row.items()}


def _load_incumbent(year: int, suffix: str = "") -> dict[tuple[str, int, int], dict[str, str]]:
    suffix_part = f"-{suffix}" if suffix else ""
    path = BACKTEST_DIR / f"backtest-results-{year}{suffix_part}.csv"
    rows: dict[tuple[str, int, int], dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("surface") != "Hard":
                continue
            winner_id = int(row["player1_id"])
            loser_id = int(row["player2_id"])
            rows[(row["date"], winner_id, loser_id)] = row
    return rows


def _models(payload: dict[str, object]) -> dict[str, ProcessModel]:
    return {name: ProcessModel.from_json(model) for name, model in payload["models"].items()}


def _group_matches(rows: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["tour_level"] not in {"ATP", "Grand Slam"}:
            continue
        grouped[str(row["match_key"])].append(row)
    matches = [group for group in grouped.values() if len(group) == 2 and {int(row["server_won_match"]) for row in group} == {0, 1}]
    return sorted(matches, key=lambda group: (int(group[0]["date_ord"]), str(group[0]["match_key"])))


def _score_timeline(
    models: dict[str, ProcessModel],
    matches: list[list[dict[str, object]]],
    targets: dict[tuple[str, int, int], dict[str, str]],
    half_life_days: float,
    prior_precision: float,
) -> list[dict[str, object]]:
    state = DynamicResiduals(half_life_days, prior_precision)
    scored: list[dict[str, object]] = []
    for group in matches:
        winner = next(row for row in group if int(row["server_won_match"]) == 1)
        loser = next(row for row in group if int(row["server_won_match"]) == 0)
        key = (str(winner["date"]), int(winner["server_id"]), int(loser["server_id"]))
        target = targets.get(key)
        if target is not None:
            p_winner_serve, winner_parts = serve_point_probability(models, state, int(winner["server_id"]), int(loser["server_id"]), int(winner["date_ord"]))
            p_loser_serve, loser_parts = serve_point_probability(models, state, int(loser["server_id"]), int(winner["server_id"]), int(loser["date_ord"]))
            recursion = prob_match_best_of_5 if target.get("series") == "Grand Slam" else prob_match_best_of_3
            vnext_probability = float(recursion(p_winner_serve, p_loser_serve))
            scored.append({
                "date": target["date"],
                "tournament": target["tournament"],
                "series": target["series"],
                "winner_id": int(winner["server_id"]),
                "loser_id": int(loser["server_id"]),
                "winner": target["player1"],
                "loser": target["player2"],
                "incumbent_prob": float(target["our_prob"]),
                "vnext_prob": vnext_probability,
                "winner_serve_point_prob": p_winner_serve,
                "loser_serve_point_prob": p_loser_serve,
                **{f"winner_{name}": value for name, value in winner_parts.items()},
                **{f"loser_{name}": value for name, value in loser_parts.items()},
            })
        for row in group:
            for model in models.values():
                update_process(model, state, row)
    return scored


def _metrics(rows: list[dict[str, object]], field: str) -> dict[str, float]:
    probabilities = np.asarray([min(max(float(row[field]), 1e-8), 1.0 - 1e-8) for row in rows], dtype=float)
    if not len(probabilities):
        return {"n": 0, "log_loss": float("nan"), "brier": float("nan"), "ece": float("nan")}
    log_loss = float(np.mean(-np.log(probabilities)))
    brier = float(np.mean((1.0 - probabilities) ** 2))
    favourite_probability = np.maximum(probabilities, 1.0 - probabilities)
    favourite_won = (probabilities >= 0.5).astype(float)
    ece = 0.0
    for low in np.linspace(0.5, 0.95, 10):
        high = low + 0.05
        mask = (favourite_probability >= low) & (favourite_probability < high if high < 1.0 else favourite_probability <= high)
        if np.any(mask):
            ece += float(np.mean(mask)) * abs(float(np.mean(favourite_probability[mask]) - np.mean(favourite_won[mask])))
    return {"n": int(len(probabilities)), "log_loss": log_loss, "brier": brier, "ece": ece}


def _bootstrap_delta(rows: list[dict[str, object]], samples: int = 2000, seed: int = 20260712) -> tuple[float, float]:
    clusters: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        dt = date.fromisoformat(str(row["date"]))
        iso = dt.isocalendar()
        clusters[f"{iso.year}-{iso.week:02d}:{row['tournament']}"] .append(row)
    keys = sorted(clusters)
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        sample_rows = []
        for _key in keys:
            sample_rows.extend(clusters[rng.choice(keys)])
        if sample_rows:
            deltas.append(_metrics(sample_rows, "vnext_prob")["log_loss"] - _metrics(sample_rows, "incumbent_prob")["log_loss"])
    return float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))


def _write_predictions(rows: list[dict[str, object]]) -> None:
    PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["date"]
    with PREDICTIONS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_DIR / "serve-counts-atp.csv.gz")
    parser.add_argument("--registration", type=Path, default=REGISTRATION)
    parser.add_argument("--incumbent-suffix", default="", help="Optional regenerated incumbent CSV suffix.")
    args = parser.parse_args()

    registration = json.loads(args.registration.read_text(encoding="utf-8"))
    rows = [_typed(row) for row in read_rows_csv_gz(args.input)]
    train = [row for row in rows if 2015 <= int(row["year"]) <= 2023 and row["tour_level"] in {"ATP", "Grand Slam"}]
    timeline = _group_matches([row for row in rows if 2024 <= int(row["year"]) <= 2025])
    validation_targets = _load_incumbent(2024, args.incumbent_suffix)
    test_targets = _load_incumbent(2025, args.incumbent_suffix)

    grid = registration["hyperparameter_grid"]
    candidates = []
    fitted_by_pool: dict[float, dict[str, object]] = {}
    for pooling in grid["pooling_strength"]:
        payload = fit_models(train, float(pooling))
        fitted_by_pool[float(pooling)] = payload
        for half_life in grid["state_half_life_days"]:
            for precision in grid["state_prior_precision"]:
                validation_rows = _score_timeline(_models(payload), timeline, validation_targets, float(half_life), float(precision))
                metric = _metrics(validation_rows, "vnext_prob")
                candidates.append({"pooling_strength": float(pooling), "half_life_days": float(half_life), "prior_precision": float(precision), **metric})
    selected = min(candidates, key=lambda row: (row["log_loss"], row["ece"], row["pooling_strength"], row["half_life_days"], row["prior_precision"]))

    selected_payload = fitted_by_pool[selected["pooling_strength"]]
    test_rows = _score_timeline(_models(selected_payload), timeline, test_targets, selected["half_life_days"], selected["prior_precision"])
    incumbent = _metrics(test_rows, "incumbent_prob")
    vnext = _metrics(test_rows, "vnext_prob")
    delta_log_loss = vnext["log_loss"] - incumbent["log_loss"]
    delta_brier = vnext["brier"] - incumbent["brier"]
    ci_low, ci_high = _bootstrap_delta(test_rows)
    gates = registration["promotion_gates"]
    pass_log_loss = delta_log_loss <= float(gates["paired_log_loss_delta_max"])
    pass_ece = vnext["ece"] <= float(gates["raw_ece_max"])
    verdict = "PASS_MVE" if pass_log_loss and pass_ece else "FAIL_MVE"
    coverage = len(test_rows) / max(1, len(test_targets))

    _write_predictions(test_rows)
    manifest_hash = sha256_file(args.input)
    registration_hash = sha256_file(args.registration)
    write_json(DEFAULT_OUTPUT_DIR / f"params-{VERSION}.json", {**selected_payload, "selected_hyperparameters": selected, "input_sha256": manifest_hash, "registration_sha256": registration_hash})
    ledger = {
        "version": VERSION,
        "test_window": registration["scope"]["test"],
        "input_sha256": manifest_hash,
        "registration_sha256": registration_hash,
        "selected_hyperparameters": selected,
        "test_rows": len(test_rows),
        "incumbent_suffix": args.incumbent_suffix,
        "verdict": verdict,
    }
    if LEDGER.exists():
        existing = json.loads(LEDGER.read_text(encoding="utf-8"))
        if (
            existing.get("registration_sha256") != registration_hash
            or existing.get("input_sha256") != manifest_hash
            or existing.get("incumbent_suffix") != args.incumbent_suffix
        ):
            raise RuntimeError("Registered test was already evaluated with different inputs/specification; create a new version")
    write_json(LEDGER, ledger)

    lines = [
        "Tennis vNext MVE Paired Evaluation",
        f"Version: {VERSION}",
        "Status: research-only; no routing, staking or public signal changes",
        "",
        "Locked design",
        "- ATP hard courts; ATP/Grand Slam only",
        "- Train 2015-2023; validation 2024; single-shot test 2025",
        "- Five binomial processes; no CPI, event, H2H or fatigue terms",
        "- Hyperparameters selected only by 2024 validation match log-loss",
        "",
        "Selected hyperparameters",
        f"- pooling_strength: {selected['pooling_strength']:.0f}",
        f"- state_half_life_days: {selected['half_life_days']:.0f}",
        f"- state_prior_precision: {selected['prior_precision']:.0f}",
        f"- validation rows: {selected['n']}",
        f"- validation vNext log-loss: {selected['log_loss']:.6f}",
        "",
        "Locked 2025 paired test",
        f"- incumbent hard rows available: {len(test_targets)}",
        f"- incumbent source suffix: {args.incumbent_suffix or 'committed-default'}",
        f"- paired count/model rows: {len(test_rows)} ({coverage * 100:.1f}% coverage)",
        f"- incumbent log-loss: {incumbent['log_loss']:.6f}",
        f"- vNext log-loss: {vnext['log_loss']:.6f}",
        f"- paired log-loss delta: {delta_log_loss:+.6f} (gate <= {float(gates['paired_log_loss_delta_max']):+.4f})",
        f"- tournament-week bootstrap 95% CI: [{ci_low:+.6f}, {ci_high:+.6f}]",
        f"- incumbent Brier: {incumbent['brier']:.6f}",
        f"- vNext Brier: {vnext['brier']:.6f}",
        f"- paired Brier delta: {delta_brier:+.6f}",
        f"- incumbent ECE: {incumbent['ece']:.6f}",
        f"- vNext raw ECE: {vnext['ece']:.6f} (gate <= {float(gates['raw_ece_max']):.4f})",
        "",
        f"VERDICT: {verdict}",
        "Proceed to CPI/event/simulator stages only if both registered MVE gates pass.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-13:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
