#!/usr/bin/env python3
"""Stage-0 validation for match-total tennis aces and double faults.

The side-level projection backtest is aggregated into matches. Negative
binomial dispersion is fitted on earlier seasons and evaluated on the latest
season only, so the live comparison can use totals-specific tails without
borrowing information from its holdout.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parent.parent
BACKTEST_DIR = ROOT / "data" / "tennis-props" / "backtest"
DEFAULT_SOURCE = BACKTEST_DIR / "aces-dfs-totals-source-rows.csv"
DEFAULT_ROWS = BACKTEST_DIR / "aces-dfs-totals-stage0-rows.csv"
DEFAULT_REPORT = BACKTEST_DIR / "aces-dfs-totals-stage0-report.txt"
DEFAULT_GATE = BACKTEST_DIR / "aces-dfs-totals-gate.json"

MIN_TOTAL_MATCHES = 1500
MIN_TRAIN_MATCHES = 900
MIN_HOLDOUT_MATCHES = 450
MARKETS = {
    "match_aces": ("actual_aces", "projected_aces", "naive_aces", "ace_confidence"),
    "match_double_faults": ("actual_dfs", "projected_dfs", "naive_dfs", "df_confidence"),
}
CONFIDENCE_RANK = {"LOW": 0, "MED": 1, "HIGH": 2}


@dataclass(frozen=True)
class TotalRow:
    tour: str
    year: int
    date: str
    tournament: str
    round: str
    surface: str
    player1: str
    player2: str
    actual_aces: int
    projected_aces: float
    naive_aces: float
    actual_dfs: int
    projected_dfs: float
    naive_dfs: float
    ace_confidence: str
    df_confidence: str


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def norm_name(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", raw).split())


def parse_float(value: object) -> float | None:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def confidence_floor(values: list[str]) -> str:
    if not values:
        return "LOW"
    return min(values, key=lambda item: CONFIDENCE_RANK.get(item.upper(), 0)).upper()


def aggregate_matches(side_rows: list[dict[str, str]]) -> list[TotalRow]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in side_rows:
        player = norm_name(row.get("player"))
        opponent = norm_name(row.get("opponent"))
        if not player or not opponent:
            continue
        pair = tuple(sorted((player, opponent)))
        key = (
            str(row.get("tour") or "").upper(),
            str(row.get("year") or ""),
            str(row.get("date") or ""),
            str(row.get("tournament") or ""),
            str(row.get("round") or ""),
            pair[0],
            pair[1],
        )
        grouped[key].append(row)

    totals: list[TotalRow] = []
    for key, rows in grouped.items():
        players = {norm_name(row.get("player")) for row in rows}
        if len(rows) != 2 or len(players) != 2:
            continue
        required = (
            "actual_aces", "projected_aces", "naive_aces",
            "actual_dfs", "projected_dfs", "naive_dfs",
        )
        parsed = {field: [parse_float(row.get(field)) for row in rows] for field in required}
        if any(any(value is None for value in values) for values in parsed.values()):
            continue
        ordered = sorted(rows, key=lambda row: norm_name(row.get("player")))
        totals.append(
            TotalRow(
                tour=key[0],
                year=int(key[1]),
                date=key[2],
                tournament=key[3],
                round=key[4],
                surface=str(rows[0].get("surface") or ""),
                player1=str(ordered[0].get("player") or ""),
                player2=str(ordered[1].get("player") or ""),
                actual_aces=int(round(sum(value or 0.0 for value in parsed["actual_aces"]))),
                projected_aces=sum(value or 0.0 for value in parsed["projected_aces"]),
                naive_aces=sum(value or 0.0 for value in parsed["naive_aces"]),
                actual_dfs=int(round(sum(value or 0.0 for value in parsed["actual_dfs"]))),
                projected_dfs=sum(value or 0.0 for value in parsed["projected_dfs"]),
                naive_dfs=sum(value or 0.0 for value in parsed["naive_dfs"]),
                ace_confidence=confidence_floor([str(row.get("ace_confidence") or "LOW") for row in rows]),
                df_confidence=confidence_floor([str(row.get("df_confidence") or "LOW") for row in rows]),
            )
        )
    return sorted(totals, key=lambda row: (row.date, row.tour, row.player1, row.player2))


def nb_log_pmf(actual: int, expected: float, alpha: float) -> float:
    if actual < 0 or expected <= 0 or alpha <= 0:
        return float("-inf")
    size = 1.0 / alpha
    prob = size / (size + expected)
    return (
        math.lgamma(actual + size)
        - math.lgamma(size)
        - math.lgamma(actual + 1)
        + size * math.log(prob)
        + actual * math.log1p(-prob)
    )


def fit_alpha(rows: list[TotalRow], actual_field: str, mean_field: str) -> float:
    def objective(log_alpha: float) -> float:
        alpha = math.exp(log_alpha)
        return -sum(
            nb_log_pmf(int(getattr(row, actual_field)), max(0.01, float(getattr(row, mean_field))), alpha)
            for row in rows
        )

    left = math.log(0.005)
    right = math.log(3.0)
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    x1 = right - ratio * (right - left)
    x2 = left + ratio * (right - left)
    f1 = objective(x1)
    f2 = objective(x2)
    for _ in range(90):
        if f1 <= f2:
            right, x2, f2 = x2, x1, f1
            x1 = right - ratio * (right - left)
            f1 = objective(x1)
        else:
            left, x1, f1 = x1, x2, f2
            x2 = left + ratio * (right - left)
            f2 = objective(x2)
    return math.exp((left + right) * 0.5)


def nb_cdf(cutoff: int, expected: float, alpha: float) -> float:
    if cutoff < 0:
        return 0.0
    return min(1.0, sum(math.exp(nb_log_pmf(k, expected, alpha)) for k in range(cutoff + 1)))


def prob_over_half_line(line: float, expected: float, alpha: float) -> float:
    return max(0.0, min(1.0, 1.0 - nb_cdf(math.floor(line), expected, alpha)))


def binary_log_loss(probabilities: list[float], outcomes: list[int]) -> float:
    if not probabilities:
        return float("nan")
    return mean(
        -outcome * math.log(max(1e-9, min(1.0 - 1e-9, probability)))
        - (1 - outcome) * math.log(max(1e-9, min(1.0 - 1e-9, 1.0 - probability)))
        for probability, outcome in zip(probabilities, outcomes, strict=True)
    )


def brier(probabilities: list[float], outcomes: list[int]) -> float:
    return mean((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes, strict=True))


def evaluate_market(
    train: list[TotalRow],
    holdout: list[TotalRow],
    market: str,
) -> dict[str, object]:
    actual_field, model_field, naive_field, _confidence_field = MARKETS[market]
    model_alpha = fit_alpha(train, actual_field, model_field)
    naive_alpha = fit_alpha(train, actual_field, naive_field)
    model_errors = [float(getattr(row, model_field)) - int(getattr(row, actual_field)) for row in holdout]
    naive_errors = [float(getattr(row, naive_field)) - int(getattr(row, actual_field)) for row in holdout]
    model_probabilities: list[float] = []
    naive_probabilities: list[float] = []
    outcomes: list[int] = []
    for row in holdout:
        actual = int(getattr(row, actual_field))
        model_mean = float(getattr(row, model_field))
        naive_mean = float(getattr(row, naive_field))
        line = math.floor(naive_mean) + 0.5
        model_probabilities.append(prob_over_half_line(line, model_mean, model_alpha))
        naive_probabilities.append(prob_over_half_line(line, naive_mean, naive_alpha))
        outcomes.append(1 if actual > line else 0)
    model_mae = mean(abs(error) for error in model_errors)
    naive_mae = mean(abs(error) for error in naive_errors)
    model_ll = binary_log_loss(model_probabilities, outcomes)
    naive_ll = binary_log_loss(naive_probabilities, outcomes)
    model_brier = brier(model_probabilities, outcomes)
    naive_brier = brier(naive_probabilities, outcomes)
    return {
        "model_alpha": round(model_alpha, 6),
        "naive_alpha": round(naive_alpha, 6),
        "model_mae": round(model_mae, 6),
        "naive_mae": round(naive_mae, 6),
        "model_log_loss": round(model_ll, 6),
        "naive_log_loss": round(naive_ll, 6),
        "model_brier": round(model_brier, 6),
        "naive_brier": round(naive_brier, 6),
        "model_bias": round(mean(model_errors), 6),
        "passed_accuracy": model_mae < naive_mae and model_ll < naive_ll and model_brier <= naive_brier,
    }


def build_gate(rows: list[TotalRow], source: Path = DEFAULT_SOURCE) -> dict[str, object]:
    years = sorted({row.year for row in rows})
    holdout_year = max(years)
    gate: dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
        "train_years": [year for year in years if year < holdout_year],
        "holdout_year": holdout_year,
        "minimums": {
            "total_matches_per_tour": MIN_TOTAL_MATCHES,
            "train_matches_per_tour": MIN_TRAIN_MATCHES,
            "holdout_matches_per_tour": MIN_HOLDOUT_MATCHES,
        },
        "markets": {},
    }
    markets: dict[str, object] = {}
    for market in MARKETS:
        tour_results: dict[str, object] = {}
        for tour in ("ATP", "WTA"):
            tour_rows = [row for row in rows if row.tour == tour]
            train = [row for row in tour_rows if row.year < holdout_year]
            holdout = [row for row in tour_rows if row.year == holdout_year]
            coverage_passed = (
                len(tour_rows) >= MIN_TOTAL_MATCHES
                and len(train) >= MIN_TRAIN_MATCHES
                and len(holdout) >= MIN_HOLDOUT_MATCHES
            )
            metrics = evaluate_market(train, holdout, market) if train and holdout else {}
            passed = coverage_passed and bool(metrics.get("passed_accuracy"))
            tour_results[tour] = {
                "passed": passed,
                "coverage_passed": coverage_passed,
                "total_matches": len(tour_rows),
                "train_matches": len(train),
                "holdout_matches": len(holdout),
                **metrics,
            }
        markets[market] = {
            "passed": all(bool(result.get("passed")) for result in tour_results.values()),
            "tours": tour_results,
        }
    gate["markets"] = markets
    return gate


def write_rows(path: Path, rows: list[TotalRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(rows[0]).keys()) if rows else list(TotalRow.__annotations__.keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_report(path: Path, gate: dict[str, object]) -> None:
    lines = [
        "Tennis Match-Total Aces/DF Stage-0",
        f"Generated UTC: {gate['generated_at_utc']}",
        f"Train years: {', '.join(map(str, gate['train_years']))}",
        f"Untouched holdout year: {gate['holdout_year']}",
        "Outcome-only validation. No odds, ROI or CLV evidence.",
        "Dispersion is fitted separately for model and naive means on training seasons only.",
        "",
    ]
    markets = gate.get("markets") or {}
    for market, market_data in markets.items():
        lines.append(f"{market}: {'PASS' if market_data['passed'] else 'BLOCKED'}")
        for tour, result in market_data["tours"].items():
            lines.append(
                f"  {tour}: {'PASS' if result['passed'] else 'BLOCKED'} "
                f"n={result['total_matches']} train={result['train_matches']} holdout={result['holdout_matches']} "
                f"alpha={result.get('model_alpha', 'n/a')} "
                f"MAE={result.get('model_mae', 'n/a')}/{result.get('naive_mae', 'n/a')} "
                f"LL={result.get('model_log_loss', 'n/a')}/{result.get('naive_log_loss', 'n/a')} "
                f"Brier={result.get('model_brier', 'n/a')}/{result.get('naive_brier', 'n/a')} "
                f"bias={result.get('model_bias', 'n/a')}"
            )
        lines.append("")
    lines.extend(
        [
            "Gate interpretation",
            "- A market is shadow-eligible only when ATP and WTA both pass coverage, MAE, log-loss and Brier gates.",
            "- The live comparison must use the fitted totals alpha for its tour and market.",
            "- A pass is research permission only; public/live promotion still requires settled Bet365 ROI and CLV.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit and validate tennis match-total aces/DF distributions")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--out-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out-gate", type=Path, default=DEFAULT_GATE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = aggregate_matches(read_csv(args.source))
    if not rows:
        raise SystemExit(f"No complete match pairs found in {args.source}")
    gate = build_gate(rows, args.source)
    write_rows(args.out_rows, rows)
    write_report(args.out_report, gate)
    args.out_gate.parent.mkdir(parents=True, exist_ok=True)
    args.out_gate.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out_rows} ({len(rows)} matches)")
    print(f"Wrote {args.out_report}")
    print(f"Wrote {args.out_gate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
