"""Audit simple tennis aces/DF projection variants against stage-0 rows.

This is deliberately post-model and outcome-only. It does not use odds, ROI, or
CLV. The point is to test whether a small adjustment is worth wiring into the
live projection code before we touch the production board.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Callable

from tennis_props_model import count_line_probabilities, resolve_count_dispersion


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-stage0-rows.csv"
DEFAULT_OUT_TXT = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-variant-audit.txt"
DEFAULT_OUT_CSV = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-variant-audit.csv"


Market = str
Predictor = Callable[["EvalRow", Market], float]


@dataclass(frozen=True)
class EvalRow:
    tour: str
    year: int
    date: str
    tournament: str
    surface: str
    player: str
    opponent: str
    actual_aces: float
    projected_aces: float
    naive_aces: float
    actual_dfs: float
    projected_dfs: float
    naive_dfs: float
    ace_confidence: str
    df_confidence: str
    expected_service_points: float
    same_tournament_matches: int
    notes: str

    def actual(self, market: Market) -> float:
        return self.actual_dfs if market == "dfs" else self.actual_aces

    def projected(self, market: Market) -> float:
        return self.projected_dfs if market == "dfs" else self.projected_aces

    def naive(self, market: Market) -> float:
        return self.naive_dfs if market == "dfs" else self.naive_aces

    def confidence(self, market: Market) -> str:
        return self.df_confidence if market == "dfs" else self.ace_confidence


@dataclass(frozen=True)
class VariantResult:
    market: str
    variant: str
    n_train: int
    n_eval: int
    train_mae: float
    train_logloss: float
    eval_mae: float
    eval_bias: float
    eval_rmse: float
    eval_logloss: float
    eval_delta_mae_vs_current: float
    eval_delta_ll_vs_current: float


def parse_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default


def parse_int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(value if value not in (None, "") else default))
    except (TypeError, ValueError):
        return default


def load_rows(path: Path) -> list[EvalRow]:
    rows: list[EvalRow] = []
    with path.open(encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            rows.append(
                EvalRow(
                    tour=str(raw.get("tour") or "").strip().upper(),
                    year=parse_int(raw.get("year")),
                    date=str(raw.get("date") or ""),
                    tournament=str(raw.get("tournament") or "").strip(),
                    surface=str(raw.get("surface") or "").strip().title(),
                    player=str(raw.get("player") or "").strip(),
                    opponent=str(raw.get("opponent") or "").strip(),
                    actual_aces=parse_float(raw.get("actual_aces")),
                    projected_aces=parse_float(raw.get("projected_aces")),
                    naive_aces=parse_float(raw.get("naive_aces")),
                    actual_dfs=parse_float(raw.get("actual_dfs")),
                    projected_dfs=parse_float(raw.get("projected_dfs")),
                    naive_dfs=parse_float(raw.get("naive_dfs")),
                    ace_confidence=str(raw.get("ace_confidence") or "").strip().upper(),
                    df_confidence=str(raw.get("df_confidence") or "").strip().upper(),
                    expected_service_points=parse_float(raw.get("expected_service_points")),
                    same_tournament_matches=parse_int(raw.get("same_tournament_matches")),
                    notes=str(raw.get("notes") or ""),
                )
            )
    return rows


def safe_mean(values: list[float]) -> float:
    return mean(values) if values else float("nan")


def rmse(errors: list[float]) -> float:
    return math.sqrt(safe_mean([err * err for err in errors])) if errors else float("nan")


def log_loss(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    total = 0.0
    for prob, outcome in zip(probs, outcomes, strict=True):
        p = max(1e-6, min(1.0 - 1e-6, prob))
        total += -outcome * math.log(p) - (1 - outcome) * math.log(1.0 - p)
    return total / len(probs)


def metrics(rows: list[EvalRow], market: Market, predictor: Predictor) -> dict[str, float]:
    errors: list[float] = []
    probs: list[float] = []
    outcomes: list[int] = []
    for row in rows:
        pred = max(0.0, predictor(row, market))
        actual = row.actual(market)
        errors.append(pred - actual)

        # Synthetic O/U line mirrors the stage-0 report: the naive baseline line.
        line = math.floor(row.naive(market)) + 0.5
        alpha = resolve_count_dispersion(row.tour, market)
        probs.append(
            count_line_probabilities(
                line,
                pred,
                distribution="negative_binomial",
                alpha=alpha,
                tour=row.tour,
                market=market,
            )[0]
        )
        outcomes.append(1 if actual > line else 0)

    return {
        "n": float(len(rows)),
        "mae": safe_mean([abs(err) for err in errors]),
        "bias": safe_mean(errors),
        "rmse": rmse(errors),
        "logloss": log_loss(probs, outcomes),
    }


def current_predictor(row: EvalRow, market: Market) -> float:
    return row.projected(market)


def naive_predictor(row: EvalRow, market: Market) -> float:
    return row.naive(market)


def blend_predictor(weight_model: float) -> Predictor:
    def _predict(row: EvalRow, market: Market) -> float:
        return weight_model * row.projected(market) + (1.0 - weight_model) * row.naive(market)

    return _predict


def confidence_blend_predictor(low_med_model_weight: float) -> Predictor:
    def _predict(row: EvalRow, market: Market) -> float:
        weight = 1.0 if row.confidence(market) == "HIGH" else low_med_model_weight
        return weight * row.projected(market) + (1.0 - weight) * row.naive(market)

    return _predict


def build_prior_biases(
    rows: list[EvalRow],
    market: Market,
    *,
    group_fn: Callable[[EvalRow], tuple[str, ...]],
    min_rows: int,
) -> dict[tuple[int, tuple[str, ...]], float]:
    by_year_group: dict[tuple[int, tuple[str, ...]], list[float]] = defaultdict(list)
    for row in rows:
        by_year_group[(row.year, group_fn(row))].append(row.projected(market) - row.actual(market))

    biases: dict[tuple[int, tuple[str, ...]], float] = {}
    years = sorted({row.year for row in rows})
    groups = sorted({group_fn(row) for row in rows})
    for year in years:
        for group in groups:
            prior_errors: list[float] = []
            for prior_year in years:
                if prior_year >= year:
                    continue
                prior_errors.extend(by_year_group.get((prior_year, group), []))
            if len(prior_errors) >= min_rows:
                biases[(year, group)] = mean(prior_errors)
    return biases


def prior_bias_predictor(
    rows: list[EvalRow],
    market: Market,
    *,
    name: str,
    group_fn: Callable[[EvalRow], tuple[str, ...]],
    min_rows: int,
    shrink: float,
) -> tuple[str, Predictor]:
    biases = build_prior_biases(rows, market, group_fn=group_fn, min_rows=min_rows)

    def _predict(row: EvalRow, selected_market: Market) -> float:
        if selected_market != market:
            return row.projected(selected_market)
        bias = biases.get((row.year, group_fn(row)), 0.0)
        return row.projected(market) - shrink * bias

    return name, _predict


def candidate_predictors(rows: list[EvalRow], market: Market) -> list[tuple[str, Predictor]]:
    candidates: list[tuple[str, Predictor]] = [
        ("current", current_predictor),
        ("naive", naive_predictor),
        ("blend_model_75", blend_predictor(0.75)),
        ("blend_model_50", blend_predictor(0.50)),
        ("blend_model_25", blend_predictor(0.25)),
        ("conf_high_current_else_75", confidence_blend_predictor(0.75)),
        ("conf_high_current_else_50", confidence_blend_predictor(0.50)),
    ]
    for shrink in (0.50, 0.75, 1.00):
        label = str(shrink).replace(".", "")
        candidates.append(
            prior_bias_predictor(
                rows,
                market,
                name=f"prior_tour_tournament_bias_{label}",
                group_fn=lambda r: (r.tour, r.tournament),
                min_rows=80,
                shrink=shrink,
            )
        )
        candidates.append(
            prior_bias_predictor(
                rows,
                market,
                name=f"prior_tour_surface_conf_bias_{label}",
                group_fn=lambda r, m=market: (r.tour, r.surface, r.confidence(m)),
                min_rows=80,
                shrink=shrink,
            )
        )
    return candidates


def evaluate_variants(rows: list[EvalRow], train_year: int, eval_year: int) -> list[VariantResult]:
    train_rows = [row for row in rows if row.year == train_year]
    eval_rows = [row for row in rows if row.year == eval_year]
    results: list[VariantResult] = []
    for market in ("aces", "dfs"):
        current_train = metrics(train_rows, market, current_predictor)
        current_eval = metrics(eval_rows, market, current_predictor)
        for variant, predictor in candidate_predictors(rows, market):
            train = metrics(train_rows, market, predictor)
            evaluation = metrics(eval_rows, market, predictor)
            results.append(
                VariantResult(
                    market=market,
                    variant=variant,
                    n_train=int(train["n"]),
                    n_eval=int(evaluation["n"]),
                    train_mae=train["mae"],
                    train_logloss=train["logloss"],
                    eval_mae=evaluation["mae"],
                    eval_bias=evaluation["bias"],
                    eval_rmse=evaluation["rmse"],
                    eval_logloss=evaluation["logloss"],
                    eval_delta_mae_vs_current=evaluation["mae"] - current_eval["mae"],
                    eval_delta_ll_vs_current=evaluation["logloss"] - current_eval["logloss"],
                )
            )
    return results


def best_by_market(results: list[VariantResult]) -> dict[str, VariantResult]:
    best: dict[str, VariantResult] = {}
    for market in ("aces", "dfs"):
        market_rows = [r for r in results if r.market == market]
        best[market] = min(market_rows, key=lambda r: (r.eval_mae, r.eval_logloss, r.variant != "current"))
    return best


def segment_rows(
    rows: list[EvalRow],
    market: Market,
    predictor: Predictor,
    key_fn: Callable[[EvalRow], str],
) -> list[tuple[str, dict[str, float]]]:
    grouped: dict[str, list[EvalRow]] = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(row)
    output: list[tuple[str, dict[str, float]]] = []
    for key in sorted(grouped):
        output.append((key, metrics(grouped[key], market, predictor)))
    return output


def format_num(value: float, digits: int = 3) -> str:
    return "n/a" if math.isnan(value) else f"{value:.{digits}f}"


def write_csv(path: Path, results: list[VariantResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "market",
        "variant",
        "n_train",
        "n_eval",
        "train_mae",
        "train_logloss",
        "eval_mae",
        "eval_bias",
        "eval_rmse",
        "eval_logloss",
        "eval_delta_mae_vs_current",
        "eval_delta_ll_vs_current",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for result in sorted(results, key=lambda r: (r.market, r.eval_mae, r.eval_logloss)):
            writer.writerow(
                {
                    "market": result.market,
                    "variant": result.variant,
                    "n_train": result.n_train,
                    "n_eval": result.n_eval,
                    "train_mae": f"{result.train_mae:.6f}",
                    "train_logloss": f"{result.train_logloss:.6f}",
                    "eval_mae": f"{result.eval_mae:.6f}",
                    "eval_bias": f"{result.eval_bias:.6f}",
                    "eval_rmse": f"{result.eval_rmse:.6f}",
                    "eval_logloss": f"{result.eval_logloss:.6f}",
                    "eval_delta_mae_vs_current": f"{result.eval_delta_mae_vs_current:.6f}",
                    "eval_delta_ll_vs_current": f"{result.eval_delta_ll_vs_current:.6f}",
                }
            )


def write_report(path: Path, rows: list[EvalRow], results: list[VariantResult], train_year: int, eval_year: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result_map = {(r.market, r.variant): r for r in results}
    best = best_by_market(results)
    lines: list[str] = [
        "Tennis Aces/DF Model Variant Audit",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Rows: {len(rows)}",
        f"Train year: {train_year}",
        f"Evaluation year: {eval_year}",
        "Outcome-only. No odds, no ROI, no CLV.",
        "",
        "Headline",
    ]

    for market in ("aces", "dfs"):
        current = result_map[(market, "current")]
        winner = best[market]
        if winner.variant == "current":
            lines.append(
                f"- {market.upper()}: current model remains best on {eval_year} "
                f"(MAE {current.eval_mae:.3f}, bias {current.eval_bias:+.3f})."
            )
        else:
            lines.append(
                f"- {market.upper()}: {winner.variant} improves {eval_year} MAE by "
                f"{-winner.eval_delta_mae_vs_current:.3f} counts vs current "
                f"({current.eval_mae:.3f} -> {winner.eval_mae:.3f}); "
                f"log-loss delta {winner.eval_delta_ll_vs_current:+.3f}."
            )
    lines.append("")

    for market in ("aces", "dfs"):
        lines.append(f"{market.upper()} variants")
        lines.append("Variant                              TrainMAE  EvalMAE  DeltaMAE  EvalBias  EvalLL  DeltaLL")
        market_results = sorted([r for r in results if r.market == market], key=lambda r: (r.eval_mae, r.eval_logloss))
        for result in market_results:
            marker = "*" if result.variant == best[market].variant else " "
            lines.append(
                f"{marker} {result.variant[:34]:34s} "
                f"{format_num(result.train_mae):>8s} "
                f"{format_num(result.eval_mae):>8s} "
                f"{result.eval_delta_mae_vs_current:+9.3f} "
                f"{result.eval_bias:+8.3f} "
                f"{format_num(result.eval_logloss):>7s} "
                f"{result.eval_delta_ll_vs_current:+8.3f}"
            )
        lines.append("")

    eval_rows = [row for row in rows if row.year == eval_year]
    predictor_by_name = dict(candidate_predictors(rows, "aces"))
    for market in ("aces", "dfs"):
        winner = best[market]
        predictor = predictor_by_name.get(winner.variant) if market == "aces" else dict(candidate_predictors(rows, "dfs")).get(winner.variant)
        if predictor is None:
            continue
        lines.append(f"{market.upper()} winning variant by tournament ({winner.variant})")
        lines.append("Bucket                         N  MAE   Bias   RMSE  LogLoss")
        for key, summary in segment_rows(eval_rows, market, predictor, lambda r: f"{r.tour} {r.tournament}"):
            lines.append(
                f"{key[:28]:28s} {int(summary['n']):4d} "
                f"{summary['mae']:5.3f} {summary['bias']:+6.3f} {summary['rmse']:6.3f} {summary['logloss']:7.3f}"
            )
        lines.append("")

    lines.append("Decision rule")
    lines.append("- Wire a variant only if it improves MAE and does not materially worsen synthetic O/U log-loss.")
    lines.append("- If the winning delta is tiny (<0.03 counts), keep the live model unchanged and collect line/settlement evidence.")
    lines.append("- This report should be refreshed after each full Slam or after stage-0 rows are regenerated.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare simple aces/DF model variants on stage-0 backtest rows.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--train-year", type=int, default=2024)
    parser.add_argument("--eval-year", type=int, default=2025)
    parser.add_argument("--out-txt", type=Path, default=DEFAULT_OUT_TXT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_rows(args.input)
    if not rows:
        raise SystemExit(f"No rows found in {args.input}")
    results = evaluate_variants(rows, args.train_year, args.eval_year)
    write_csv(args.out_csv, results)
    write_report(args.out_txt, rows, results, args.train_year, args.eval_year)
    print(f"Wrote {args.out_txt}")
    print(f"Wrote {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
