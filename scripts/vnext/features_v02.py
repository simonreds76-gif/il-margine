#!/usr/bin/env python3
"""Export causal rung-1 features for the registered anchored residual v0.2."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from common import DEFAULT_OUTPUT_DIR, ROOT, read_rows_csv_gz, sha256_file, write_json
from fit_offline import fit_models
from model_spec import DynamicResiduals, PROCESS_SPECS, ProcessModel, serve_point_probability, update_process


BACKTEST_DIR = ROOT / "data" / "backtest"
REGISTRATION = DEFAULT_OUTPUT_DIR / "experiment-registration-v0.2.json"
DEFAULT_OUTPUT = DEFAULT_OUTPUT_DIR / "vnext-v02-features.csv"


def typed(row: dict[str, str]) -> dict[str, object]:
    numeric = {
        "date_ord", "year", "tour_rank", "round_id", "server_id", "returner_id", "server_won_match",
        "serve_points", "first_in", "first_won", "second_attempts", "second_in", "second_won", "aces", "double_faults",
    }
    return {key: int(value) if key in numeric else value for key, value in row.items()}


def group_matches(rows: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["tour_level"] in {"ATP", "Grand Slam"}:
            grouped[str(row["match_key"])].append(row)
    matches = [group for group in grouped.values() if len(group) == 2 and {int(row["server_won_match"]) for row in group} == {0, 1}]
    return sorted(matches, key=lambda group: (int(group[0]["date_ord"]), str(group[0]["match_key"])))


def load_incumbent(years: range, early_suffix: str) -> dict[tuple[str, int, int], dict[str, str]]:
    out: dict[tuple[str, int, int], dict[str, str]] = {}
    for year in years:
        suffix = f"-{early_suffix}" if year <= 2021 and early_suffix else ""
        path = BACKTEST_DIR / f"backtest-results-{year}{suffix}.csv"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("surface") != "Hard":
                    continue
                out[(row["date"], int(row["player1_id"]), int(row["player2_id"]))] = row
    return out


def models_from_payload(payload: dict[str, object]) -> dict[str, ProcessModel]:
    return {name: ProcessModel.from_json(model) for name, model in payload["models"].items()}


def matchup_precision(
    models: dict[str, ProcessModel],
    state: DynamicResiduals,
    server_id: int,
    returner_id: int,
    date_ord: int,
    information_discount: float,
) -> float:
    values: list[float] = []
    for name, (_success, _total, has_return) in PROCESS_SPECS.items():
        model = models[name]
        static_server = model.precision(server_id, "server")
        dynamic_server = state.precision(name, "server", server_id, date_ord)
        values.append(model.pooling_strength + information_discount * max(0.0, static_server - model.pooling_strength))
        values.append(model.pooling_strength + information_discount * max(0.0, dynamic_server - state.prior_precision))
        if has_return:
            static_return = model.precision(returner_id, "return")
            dynamic_return = state.precision(name, "return", returner_id, date_ord)
            values.append(model.pooling_strength + information_discount * max(0.0, static_return - model.pooling_strength))
            values.append(model.pooling_strength + information_discount * max(0.0, dynamic_return - state.prior_precision))
    return min(values) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_DIR / "serve-counts-atp.csv.gz")
    parser.add_argument("--registration", type=Path, default=REGISTRATION)
    parser.add_argument("--early-incumbent-suffix", default="vnext-v02-idclean")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    registration = json.loads(args.registration.read_text(encoding="utf-8"))
    config = registration["feature_factory"]
    rows = [typed(row) for row in read_rows_csv_gz(args.input)]
    base_train = [
        row for row in rows
        if 2015 <= int(row["year"]) <= 2018 and row["tour_level"] in {"ATP", "Grand Slam"}
    ]
    payload = fit_models(base_train, float(config["pooling_strength"]))
    models = models_from_payload(payload)
    state = DynamicResiduals(float(config["state_half_life_days"]), float(config["state_prior_precision"]))
    targets = load_incumbent(range(2019, 2026), args.early_incumbent_suffix)
    timeline = group_matches([row for row in rows if 2019 <= int(row["year"]) <= 2025])
    precision_scale = float(config["uncertainty_precision_scale"])
    information_discount = float(config["information_discount"])
    output_rows: list[dict[str, object]] = []

    for group in timeline:
        winner = next(row for row in group if int(row["server_won_match"]) == 1)
        loser = next(row for row in group if int(row["server_won_match"]) == 0)
        key = (str(winner["date"]), int(winner["server_id"]), int(loser["server_id"]))
        target = targets.get(key)
        if target is not None:
            date_ord = int(winner["date_ord"])
            winner_spw, _winner_parts = serve_point_probability(models, state, key[1], key[2], date_ord)
            loser_spw, _loser_parts = serve_point_probability(models, state, key[2], key[1], date_ord)
            winner_precision = matchup_precision(models, state, key[1], key[2], date_ord, information_discount)
            loser_precision = matchup_precision(models, state, key[2], key[1], date_ord, information_discount)
            effective_precision = min(winner_precision, loser_precision)
            uncertainty_weight = min(1.0, math.sqrt(max(effective_precision, 0.0) / max(precision_scale, 1e-9)))
            serve_logit_diff = math.log(winner_spw / (1.0 - winner_spw)) - math.log(loser_spw / (1.0 - loser_spw))
            output_rows.append({
                "match_key": winner["match_key"],
                "date": target["date"],
                "tournament": target["tournament"],
                "series": target["series"],
                "winner_id": key[1],
                "loser_id": key[2],
                "incumbent_prob_winner": target["our_prob"],
                "winner_serve_point_prob": f"{winner_spw:.8f}",
                "loser_serve_point_prob": f"{loser_spw:.8f}",
                "serve_logit_differential": f"{serve_logit_diff:.8f}",
                "effective_precision": f"{effective_precision:.6f}",
                "uncertainty_weight": f"{uncertainty_weight:.8f}",
                "uncertainty_weighted_serve_logit_differential": f"{uncertainty_weight * serve_logit_diff:.8f}",
            })
        for row in group:
            for model in models.values():
                update_process(model, state, row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(output_rows[0]) if output_rows else ["match_key"]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    write_json(
        DEFAULT_OUTPUT_DIR / "vnext-v02-features-manifest.json",
        {
            "version": registration["version"],
            "registered": True,
            "count_input_sha256": sha256_file(args.input),
            "registration_sha256": sha256_file(args.registration),
            "feature_output_sha256": sha256_file(args.output),
            "feature_rows": len(output_rows),
            "feature_base_train_rows": len(base_train),
            "early_incumbent_suffix": args.early_incumbent_suffix,
        },
    )
    print(f"Wrote {len(output_rows):,} causal v0.2 feature rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
