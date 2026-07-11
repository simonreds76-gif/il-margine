#!/usr/bin/env python3
"""Past-only calibration comparison for the Goalscorer Fair Odds Lab.

REGISTERED 2026-07-11: folds, live-proxy population and promotion gates in
this file are fixed before inspecting variant results. No threshold sweep is
performed and this script never changes live display probabilities.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import runpy
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean

from goalscorer_calibration_lib import apply_calibrator, fit_calibrator


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "goalscorer" / "backtest"
LEAGUES = ("serie-a", "epl", "la-liga", "bundesliga", "ligue-1")
FOLDS = (
    ("F1", date(1900, 1, 1), date(2024, 6, 30), date(2024, 7, 1), date(2024, 12, 31)),
    ("F2", date(1900, 1, 1), date(2024, 12, 31), date(2025, 1, 1), date(2025, 6, 30)),
    ("F3", date(1900, 1, 1), date(2025, 6, 30), date(2025, 7, 1), date(2025, 12, 31)),
    ("F4", date(1900, 1, 1), date(2025, 12, 31), date(2026, 1, 1), date(2026, 6, 30)),
    ("F5", date(1900, 1, 1), date(2026, 6, 30), date(2026, 7, 1), date(2027, 6, 30)),
)
VARIANTS = ("raw", "platt", "beta", "isotonic")
MIN_EXPECTED_MINUTES = 65.0
ISOTONIC_MIN_TRAIN_ROWS = 20_000
PROMOTION_MAX_ECE = 0.02
PROMOTION_REQUIRED_FOLD_WINS = 4


def parse_date(value: object) -> date | None:
    try:
        return datetime.strptime(str(value or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expand_league_files(league: str) -> list[Path]:
    return [Path(path) for path in sorted(glob.glob(str(ROOT / "data" / "goalscorer" / f"{league}-player-match-logs-*.csv")))]


def build_base_rows() -> tuple[list[dict], list[dict]]:
    model = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_walkforward_model")
    rows: list[dict] = []
    inputs: list[dict] = []
    for league in LEAGUES:
        paths = expand_league_files(league)
        for path in paths:
            inputs.append({"league": league, "path": path.relative_to(ROOT).as_posix(), "rows": sum(1 for _ in path.open(encoding="utf-8")) - 1, "sha256": file_hash(path)})
        normalized = model["load_match_logs"]([str(path) for path in paths])
        if not normalized:
            continue
        observed_penalty_rate = model["infer_league_penalties_per_match"](normalized)
        model["run_backtest"].__globals__["LEAGUE_AVG"] = model["league_avg_for"](league, observed_penalty_rate)
        league_rows, _stats = model["run_backtest"](normalized)
        for row in league_rows:
            row["league"] = league
            row["_date"] = parse_date(row.get("match_date"))
            rows.append(row)
    return rows, inputs


def eligible(row: dict) -> bool:
    return (
        row.get("method") == "model"
        and float(row.get("expected_minutes") or 0.0) >= MIN_EXPECTED_MINUTES
        and str(row.get("position_group") or "").strip().lower() != "sub"
        and row.get("_date") is not None
    )


def log_loss(probabilities: list[float], labels: list[int]) -> float:
    import math

    values = []
    for probability, label in zip(probabilities, labels):
        probability = min(1.0 - 1e-9, max(1e-9, probability))
        values.append(-(label * math.log(probability) + (1 - label) * math.log(1.0 - probability)))
    return mean(values) if values else float("nan")


def brier(probabilities: list[float], labels: list[int]) -> float:
    return mean((probability - label) ** 2 for probability, label in zip(probabilities, labels)) if labels else float("nan")


def ece(probabilities: list[float], labels: list[int]) -> float:
    if not labels:
        return float("nan")
    total = len(labels)
    score = 0.0
    for lower, upper in ((0.0, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 0.20), (0.20, 0.25), (0.25, 0.30), (0.30, 0.40), (0.40, 0.50), (0.50, 1.01)):
        indices = [index for index, probability in enumerate(probabilities) if lower <= probability < upper]
        if not indices:
            continue
        predicted = mean(probabilities[index] for index in indices)
        actual = mean(labels[index] for index in indices)
        score += len(indices) / total * abs(predicted - actual)
    return score


def metrics(probabilities: list[float], labels: list[int]) -> dict:
    return {
        "n": len(labels),
        "predicted": mean(probabilities) if probabilities else None,
        "actual": mean(labels) if labels else None,
        "brier": brier(probabilities, labels) if labels else None,
        "log_loss": log_loss(probabilities, labels) if labels else None,
        "ece": ece(probabilities, labels) if labels else None,
    }


def fmt(value: float | None, digits: int = 5) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def run_walkforward(rows: list[dict]) -> tuple[list[dict], list[dict], dict]:
    population = [row for row in rows if eligible(row)]
    fold_metrics: list[dict] = []
    detail_rows: list[dict] = []
    pooled: dict[str, tuple[list[float], list[int]]] = {variant: ([], []) for variant in VARIANTS}
    fitted: dict[str, dict] = {}

    for fold_name, train_start, train_end, test_start, test_end in FOLDS:
        train = [row for row in population if train_start <= row["_date"] <= train_end]
        test = [row for row in population if test_start <= row["_date"] <= test_end]
        if train and test:
            assert max(row["_date"] for row in train) < min(row["_date"] for row in test)
        train_probs = [float(row["model_p_atgs"]) for row in train]
        train_labels = [int(row["scored"]) for row in train]
        test_probs = [float(row["model_p_atgs"]) for row in test]
        test_labels = [int(row["scored"]) for row in test]

        calibrators: dict[str, dict] = {}
        if train and len(set(train_labels)) > 1:
            calibrators["platt"] = fit_calibrator("platt", train_probs, train_labels)
            calibrators["beta"] = fit_calibrator("beta", train_probs, train_labels)
            if len(train) >= ISOTONIC_MIN_TRAIN_ROWS:
                calibrators["isotonic"] = fit_calibrator("isotonic", train_probs, train_labels)
        fitted[fold_name] = calibrators

        predictions: dict[str, list[float]] = {"raw": test_probs}
        for variant in ("platt", "beta", "isotonic"):
            predictions[variant] = (
                [apply_calibrator(calibrators[variant], probability) for probability in test_probs]
                if variant in calibrators
                else []
            )
        for variant in VARIANTS:
            variant_metrics = metrics(predictions[variant], test_labels) if predictions[variant] else {"n": 0, "predicted": None, "actual": None, "brier": None, "log_loss": None, "ece": None}
            fold_metrics.append({"fold": fold_name, "variant": variant, "train_n": len(train), "test_start": test_start.isoformat(), "test_end": test_end.isoformat(), **variant_metrics})
            if predictions[variant]:
                pooled[variant][0].extend(predictions[variant])
                pooled[variant][1].extend(test_labels)

        for index, row in enumerate(test):
            detail_rows.append(
                {
                    "fold": fold_name,
                    "league": row["league"],
                    "season": row.get("season", ""),
                    "match_date": row.get("match_date", ""),
                    "player_id": row.get("player_id", ""),
                    "player_name": row.get("player_name", ""),
                    "position_group": row.get("position_group", ""),
                    "expected_minutes": row.get("expected_minutes", ""),
                    "scored": row.get("scored", ""),
                    "p_raw": fmt(test_probs[index], 8),
                    "p_platt": fmt(predictions["platt"][index], 8) if predictions["platt"] else "",
                    "p_beta": fmt(predictions["beta"][index], 8) if predictions["beta"] else "",
                    "p_isotonic": fmt(predictions["isotonic"][index], 8) if predictions["isotonic"] else "",
                }
            )

    pooled_metrics = {variant: metrics(*pooled[variant]) for variant in VARIANTS}
    return fold_metrics, detail_rows, {"fold_calibrators": fitted, "pooled_metrics": pooled_metrics}


def write_outputs(fold_metrics: list[dict], detail_rows: list[dict], payload: dict, inputs: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / "walkforward-metrics.csv"
    with metrics_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fold_metrics[0].keys()))
        writer.writeheader()
        writer.writerows(fold_metrics)
    detail_path = out_dir / "walkforward-rows.csv"
    with detail_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail_rows[0].keys()) if detail_rows else ["fold"])
        writer.writeheader()
        writer.writerows(detail_rows)

    raw_by_fold = {row["fold"]: row for row in fold_metrics if row["variant"] == "raw"}
    lines = [
        "Goalscorer Walk-Forward Calibration Report",
        "=============================================",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}",
        "Status: RESEARCH_ONLY_NOT_LIVE",
        "Registered: 2026-07-11",
        f"Live proxy: method=model, expected_minutes>={MIN_EXPECTED_MINUTES:.0f}, position_group!=Sub",
        "ROI/market gate: unavailable until historical ATGS price coverage exists",
        "",
        "Fold metrics",
        "fold,variant,train_n,test_n,brier,log_loss,ece,predicted,actual",
    ]
    for row in fold_metrics:
        lines.append(
            f"{row['fold']},{row['variant']},{row['train_n']},{row['n']},{fmt(row['brier'])},{fmt(row['log_loss'])},{fmt(row['ece'])},{fmt(row['predicted'],4)},{fmt(row['actual'],4)}"
        )
    lines.extend(["", "Pooled metrics", "variant,n,brier,log_loss,ece,predicted,actual"])
    for variant in VARIANTS:
        row = payload["pooled_metrics"][variant]
        lines.append(f"{variant},{row['n']},{fmt(row['brier'])},{fmt(row['log_loss'])},{fmt(row['ece'])},{fmt(row['predicted'],4)},{fmt(row['actual'],4)}")

    promotion_rows = []
    for variant in ("platt", "beta", "isotonic"):
        wins = 0
        evaluated = 0
        for fold_name, *_ in FOLDS:
            raw = raw_by_fold.get(fold_name)
            candidate = next((row for row in fold_metrics if row["fold"] == fold_name and row["variant"] == variant), None)
            if not raw or not candidate or not raw["n"] or not candidate["n"]:
                continue
            evaluated += 1
            if candidate["brier"] < raw["brier"] and candidate["log_loss"] < raw["log_loss"]:
                wins += 1
        pooled = payload["pooled_metrics"][variant]
        probability_gate = (
            evaluated == len(FOLDS)
            and wins >= PROMOTION_REQUIRED_FOLD_WINS
            and pooled["ece"] is not None
            and pooled["ece"] <= PROMOTION_MAX_ECE
        )
        promotion_rows.append((variant, evaluated, wins, probability_gate))
    lines.extend(["", "Promotion gate", "variant,evaluated_folds,fold_wins,probability_gate,market_roi_gate,decision"])
    for variant, evaluated, wins, probability_gate in promotion_rows:
        lines.append(f"{variant},{evaluated},{wins},{'PASS' if probability_gate else 'FAIL'},UNAVAILABLE,KEEP_RESEARCH")
    lines.extend(
        [
            "",
            "Decision",
            "No calibrator is promoted unless all five folds exist, at least four beat raw on both Brier and log-loss, pooled ECE <= 2pp, and the fixed real-price ROI gate is non-negative.",
            "The public Fair Odds Lab remains on the incumbent probability until every gate passes.",
        ]
    )
    (out_dir / "walkforward-report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    metadata = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "research_only_not_live",
        "registered_at": "2026-07-11",
        "inputs": inputs,
        **payload,
    }
    (out_dir / "walkforward-calibrators.json").write_text(json.dumps(metadata, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the registered goalscorer probability walk-forward")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args()
    rows, inputs = build_base_rows()
    fold_metrics, detail_rows, payload = run_walkforward(rows)
    write_outputs(fold_metrics, detail_rows, payload, inputs, Path(args.out_dir))
    print(f"Base rows: {len(rows):,}")
    print(f"Live-proxy rows: {sum(eligible(row) for row in rows):,}")
    print(f"Walk-forward rows: {len(detail_rows):,}")
    print(f"Report: {Path(args.out_dir) / 'walkforward-report.txt'}")


if __name__ == "__main__":
    main()
