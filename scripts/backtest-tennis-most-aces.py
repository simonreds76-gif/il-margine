#!/usr/bin/env python3
"""Untouched-2026 outcome validation for Most Aces 1X2 probabilities."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tennis_most_aces import (
    DEFAULT_RHO,
    independent_most_aces_probabilities,
    most_aces_probabilities,
    pair_key,
    result_from_counts,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-v3-all-tour-2026-predictions.csv"
DEFAULT_CONFIG = ROOT / "data" / "tennis-props" / "models" / "most-aces-1x2-config.json"
DEFAULT_REPORT = ROOT / "data" / "tennis-props" / "backtest" / "most-aces-1x2-stage0-report.txt"
DEFAULT_JSON = ROOT / "data" / "tennis-props" / "backtest" / "most-aces-1x2-stage0.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_rho(path: Path) -> float:
    try:
        return float(json.loads(path.read_text(encoding="utf-8")).get("rho", DEFAULT_RHO))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return DEFAULT_RHO


def paired_rows(rows: list[dict[str, str]]) -> list[tuple[dict[str, str], dict[str, str]]]:
    grouped: dict[tuple[object, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if (
            (row.get("tour") or "").upper() != "ATP"
            or row.get("surface") not in {"Hard", "Clay"}
            or (row.get("market") or "").lower() != "aces"
        ):
            continue
        key = (
            row.get("date"), row.get("tour"), row.get("tournament"), row.get("round"),
            pair_key(row.get("player"), row.get("opponent")),
        )
        grouped[key].append(row)
    output = []
    for group in grouped.values():
        if len(group) != 2:
            continue
        left, right = group
        if pair_key(left.get("player"), left.get("opponent")) != pair_key(right.get("player"), right.get("opponent")):
            continue
        output.append((left, right))
    return output


def score(probabilities: tuple[float, float, float], outcome: str) -> tuple[float, float, int]:
    index = {"P1": 0, "DRAW": 1, "P2": 2}[outcome]
    brier = sum((probability - (1.0 if idx == index else 0.0)) ** 2 for idx, probability in enumerate(probabilities))
    logloss = -math.log(max(probabilities[index], 1e-12))
    correct = int(max(range(3), key=lambda idx: probabilities[idx]) == index)
    return brier, logloss, correct


def summarise(rows: list[dict[str, object]], prefix: str) -> dict[str, float | int]:
    count = len(rows)
    return {
        "n": count,
        "brier": sum(float(row[f"{prefix}_brier"]) for row in rows) / count if count else 0.0,
        "logloss": sum(float(row[f"{prefix}_logloss"]) for row in rows) / count if count else 0.0,
        "accuracy_pct": 100.0 * sum(int(row[f"{prefix}_correct"]) for row in rows) / count if count else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--simulations", type=int, default=2048)
    args = parser.parse_args()
    rho = load_rho(Path(args.config))
    evaluated: list[dict[str, object]] = []
    for left, right in paired_rows(read_csv(Path(args.source))):
        try:
            mean1 = float(left["candidate_mean"])
            mean2 = float(right["candidate_mean"])
            alpha1 = float(left["candidate_alpha"])
            alpha2 = float(right["candidate_alpha"])
            actual1 = int(round(float(left["actual_aces"])))
            actual2 = int(round(float(right["actual_aces"])))
        except (KeyError, TypeError, ValueError):
            continue
        outcome = result_from_counts(actual1, actual2)
        independent = independent_most_aces_probabilities(
            mean1, mean2, alpha1=alpha1, alpha2=alpha2
        )
        correlated = most_aces_probabilities(
            mean1, mean2, alpha1=alpha1, alpha2=alpha2, rho=rho,
            simulations=args.simulations,
        )
        independent_score = score(independent, outcome)
        correlated_score = score(correlated, outcome)
        evaluated.append({
            "surface": left.get("surface") or "",
            "outcome": outcome,
            "independent_brier": independent_score[0],
            "independent_logloss": independent_score[1],
            "independent_correct": independent_score[2],
            "correlated_brier": correlated_score[0],
            "correlated_logloss": correlated_score[1],
            "correlated_correct": correlated_score[2],
        })

    overall_independent = summarise(evaluated, "independent")
    overall_correlated = summarise(evaluated, "correlated")
    surfaces = {}
    for surface in ("Hard", "Clay"):
        subset = [row for row in evaluated if row["surface"] == surface]
        surfaces[surface] = {
            "independent": summarise(subset, "independent"),
            "correlated": summarise(subset, "correlated"),
        }
    outcomes = {
        name: sum(row["outcome"] == name for row in evaluated)
        for name in ("P1", "DRAW", "P2")
    }
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "PASS" if overall_correlated["brier"] <= overall_independent["brier"] else "FAIL",
        "scope": "ATP Hard/Clay untouched 2026",
        "rho": rho,
        "simulations": args.simulations,
        "outcomes": outcomes,
        "independent": overall_independent,
        "correlated": overall_correlated,
        "surfaces": surfaces,
        "interpretation": "Outcome calibration only; no historical BetMGM prices, ROI or CLV.",
    }
    json_path = Path(args.json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report = [
        "Most Aces 1X2 stage-0 outcome validation",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']} | Scope: {payload['scope']}",
        f"Matches: {len(evaluated)} | Draws: {outcomes['DRAW']} ({100.0 * outcomes['DRAW'] / len(evaluated):.1f}%)",
        f"Independent NB2: Brier {overall_independent['brier']:.6f} | log-loss {overall_independent['logloss']:.6f} | accuracy {overall_independent['accuracy_pct']:.1f}%",
        f"Correlated NB2: Brier {overall_correlated['brier']:.6f} | log-loss {overall_correlated['logloss']:.6f} | accuracy {overall_correlated['accuracy_pct']:.1f}%",
        f"Delta correlated-independent: Brier {float(overall_correlated['brier']) - float(overall_independent['brier']):+.6f} | log-loss {float(overall_correlated['logloss']) - float(overall_independent['logloss']):+.6f}",
    ]
    for surface, values in surfaces.items():
        control = values["independent"]
        challenger = values["correlated"]
        report.append(
            f"{surface}: n={challenger['n']} | Brier {challenger['brier']:.6f} vs {control['brier']:.6f} | "
            f"log-loss {challenger['logloss']:.6f} vs {control['logloss']:.6f}"
        )
    report.extend([
        "",
        "This validates probability shape only. Profitability requires captured BetMGM 1X2 prices, settlement and CLV.",
    ])
    Path(args.report).write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
