#!/usr/bin/env python3
"""Evaluate corrected tennis handicap mathematics on real Pinnacle prices."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

from handicap_probs import (
    cover_probs,
    game_margin_pmf_bo3,
    match_margin_pmf,
    match_win_probability,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "backtest" / "spread-real-scored-atp.csv"
DEFAULT_CSV = ROOT / "data" / "backtest" / "spread-shape-math-evaluation.csv"
DEFAULT_JSON = ROOT / "data" / "backtest" / "spread-shape-math-evaluation.json"
DEFAULT_REPORT = ROOT / "data" / "backtest" / "spread-shape-math-evaluation.txt"
SURFACE_AVG_SPW = {
    "Hard": 0.64,
    "Clay": 0.62,
    "Grass": 0.67,
    "I.hard": 0.64,
    "Carpet": 0.66,
    "Acrylic": 0.64,
    "N/A": 0.64,
}


def number(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        result = float(text) if text else None
        return result if result is None or math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def integer(value: object) -> int | None:
    parsed = number(value)
    return int(parsed) if parsed is not None else None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def devig(odds1: float, odds2: float) -> float:
    inv1 = 1.0 / odds1
    inv2 = 1.0 / odds2
    return inv1 / (inv1 + inv2)


def is_bo5(row: dict[str, str]) -> bool:
    tour_name = str(row.get("tour_name") or "").upper()
    slam = any(
        token in tour_name
        for token in (
            "AUSTRALIAN OPEN",
            "ROLAND GARROS",
            "WIMBLEDON",
            "US OPEN",
            "GRAND SLAM",
        )
    )
    return slam and (integer(row.get("round_id")) or 0) >= 4


def solve_point_probabilities(
    match_p1: float,
    avg_spw: float,
    best_of: str,
) -> tuple[float, float]:
    match_p1 = clamp(match_p1, 0.02, 0.98)
    avg_spw = clamp(avg_spw, 0.43, 0.79)
    max_delta = min(avg_spw - 0.42, 0.80 - avg_spw)
    low, high = -max_delta, max_delta
    for _ in range(48):
        delta = (low + high) / 2.0
        p_a = clamp(avg_spw + delta, 0.42, 0.80)
        p_b = clamp(avg_spw - delta, 0.42, 0.80)
        implied = match_win_probability(p_a, p_b, best_of)
        if abs(implied - match_p1) < 0.0005:
            return p_a, p_b
        if implied < match_p1:
            low = delta
        else:
            high = delta
    delta = (low + high) / 2.0
    return (
        clamp(avg_spw + delta, 0.42, 0.80),
        clamp(avg_spw - delta, 0.42, 0.80),
    )


def conditional_cover(pmf: dict[int, float], line: float) -> tuple[float, float]:
    p_win, p_push, p_loss = cover_probs(pmf, line)
    non_push = p_win + p_loss
    return (p_win / non_push if non_push else 0.5), p_push


def old_cover_probability(p_a: float, p_b: float, line: float) -> float:
    """Reproduce the former BO3-only, push-as-opposite-side calculation."""
    return sum(
        probability
        for margin, probability in game_margin_pmf_bo3(p_a, p_b).items()
        if margin + line > 1e-9
    )


def brier(rows: list[dict[str, object]], field: str) -> float | None:
    values = [
        (float(row[field]) - float(row["actual_p1"])) ** 2
        for row in rows
        if row.get("actual_p1") is not None
    ]
    return mean(values) if values else None


def log_loss(rows: list[dict[str, object]], field: str) -> float | None:
    values = []
    for row in rows:
        if row.get("actual_p1") is None:
            continue
        probability = clamp(float(row[field]), 1e-9, 1.0 - 1e-9)
        actual = float(row["actual_p1"])
        values.append(
            -(actual * math.log(probability) + (1.0 - actual) * math.log(1.0 - probability))
        )
    return mean(values) if values else None


def bootstrap_roi(pnls: list[float], draws: int = 5000) -> list[float] | None:
    if not pnls:
        return None
    rng = random.Random(20260728)
    samples = []
    for _ in range(draws):
        samples.append(
            100.0 * sum(rng.choice(pnls) for _ in pnls) / len(pnls)
        )
    samples.sort()
    return [samples[int(0.025 * draws)], samples[int(0.975 * draws)]]


def score_row(row: dict[str, str], edge_threshold: float) -> dict[str, object] | None:
    ml_odds1 = number(row.get("ml_odds1"))
    ml_odds2 = number(row.get("ml_odds2"))
    spread_odds1 = number(row.get("spread_odds1"))
    spread_odds2 = number(row.get("spread_odds2"))
    line = number(row.get("spread_line_p1"))
    market_p1 = number(row.get("spread_market_p1_devig"))
    if (
        ml_odds1 is None
        or ml_odds2 is None
        or spread_odds1 is None
        or spread_odds2 is None
        or line is None
        or market_p1 is None
        or min(ml_odds1, ml_odds2, spread_odds1, spread_odds2) <= 1.0
    ):
        return None

    best_of = "bo5" if is_bo5(row) else "bo3"
    surface = str(row.get("surface") or "N/A")
    p_a, p_b = solve_point_probabilities(
        devig(ml_odds1, ml_odds2),
        SURFACE_AVG_SPW.get(surface, SURFACE_AVG_SPW["N/A"]),
        best_of,
    )
    corrected_p1, push_mass = conditional_cover(
        match_margin_pmf(p_a, p_b, best_of),
        line,
    )
    old_p1 = old_cover_probability(p_a, p_b, line)
    actual_text = str(row.get("p1_cover_result") or "").upper()
    actual_p1 = (
        1.0 if actual_text == "WIN" else 0.0 if actual_text == "LOSS" else None
    )
    ev1 = corrected_p1 * spread_odds1 - 1.0
    ev2 = (1.0 - corrected_p1) * spread_odds2 - 1.0
    selection = ""
    selection_odds = None
    pnl = None
    clv = None
    if max(ev1, ev2) >= edge_threshold:
        selection = "P1" if ev1 >= ev2 else "P2"
        selection_odds = spread_odds1 if selection == "P1" else spread_odds2
        result = str(
            row.get("p1_cover_result" if selection == "P1" else "p2_cover_result")
            or ""
        ).upper()
        pnl = (
            selection_odds - 1.0
            if result == "WIN"
            else -1.0
            if result == "LOSS"
            else 0.0
        )
        if str(row.get("clv_eligible") or "") == "1":
            clv = number(
                row.get(
                    "published_to_close_clv_p1"
                    if selection == "P1"
                    else "published_to_close_clv_p2"
                )
            )

    return {
        "match_key": row.get("match_key"),
        "match_date": row.get("match_date"),
        "tour_name": row.get("tour_name"),
        "surface": surface,
        "best_of": best_of,
        "line": line,
        "integer_line": int(abs(line - round(line)) < 1e-9),
        "market_p1": market_p1,
        "old_p1": old_p1,
        "corrected_p1": corrected_p1,
        "push_mass": push_mass,
        "actual_p1": actual_p1,
        "selection": selection,
        "selection_odds": selection_odds,
        "model_ev_pct": 100.0 * max(ev1, ev2),
        "pnl": pnl,
        "clv_pct": clv,
    }


def segment_metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    non_push = [row for row in rows if row.get("actual_p1") is not None]
    return {
        "rows": len(rows),
        "non_push_rows": len(non_push),
        "market_brier": brier(non_push, "market_p1"),
        "old_brier": brier(non_push, "old_p1"),
        "corrected_brier": brier(non_push, "corrected_p1"),
        "market_log_loss": log_loss(non_push, "market_p1"),
        "old_log_loss": log_loss(non_push, "old_p1"),
        "corrected_log_loss": log_loss(non_push, "corrected_p1"),
        "mean_push_mass": mean([float(row["push_mass"]) for row in rows]) if rows else None,
    }


def evaluate(rows: list[dict[str, object]], edge_threshold: float) -> dict[str, object]:
    bets = [row for row in rows if row.get("pnl") is not None]
    pnls = [float(row["pnl"]) for row in bets]
    clv = [float(row["clv_pct"]) for row in bets if row.get("clv_pct") is not None]
    moved_clv = [value for value in clv if abs(value) > 1e-12]
    segments = {
        "all": segment_metrics(rows),
        "bo3": segment_metrics([row for row in rows if row["best_of"] == "bo3"]),
        "bo5": segment_metrics([row for row in rows if row["best_of"] == "bo5"]),
        "integer": segment_metrics([row for row in rows if row["integer_line"] == 1]),
        "half": segment_metrics([row for row in rows if row["integer_line"] == 0]),
    }
    all_metrics = segments["all"]
    roi = 100.0 * sum(pnls) / len(pnls) if pnls else None
    roi_ci = bootstrap_roi(pnls)
    mean_clv = mean(clv) if clv else None
    positive_clv = (
        100.0 * sum(value > 0 for value in moved_clv) / len(moved_clv)
        if moved_clv
        else None
    )
    gates = {
        "corrected_brier_beats_market": (
            all_metrics["corrected_brier"] is not None
            and all_metrics["market_brier"] is not None
            and all_metrics["corrected_brier"] <= all_metrics["market_brier"]
        ),
        "priced_bets_200": len(bets) >= 200,
        "mean_clv_1pct": mean_clv is not None and mean_clv >= 1.0,
        "positive_clv_55pct": positive_clv is not None and positive_clv >= 55.0,
        "roi_ci_lower_above_minus_2pct": roi_ci is not None and roi_ci[0] > -2.0,
    }
    return {
        "status": "PASS" if all(gates.values()) else "TESTED_AND_REJECTED",
        "edge_threshold_pct": 100.0 * edge_threshold,
        "priced_bets": len(bets),
        "pnl_units": sum(pnls),
        "roi_pct": roi,
        "roi_ci95_pct": roi_ci,
        "clv_rows": len(clv),
        "mean_clv_pct": mean_clv,
        "positive_clv_share_moved_pct": positive_clv,
        "segments": segments,
        "gates": gates,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0]) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def fmt(value: object, digits: int = 4) -> str:
    return "n/a" if value is None else f"{float(value):.{digits}f}"


def build_report(payload: dict[str, object]) -> str:
    evaluation = payload["evaluation"]
    segments = evaluation["segments"]
    lines = [
        "IL MARGINE - Tennis Spread Mathematics Real-Price Evaluation",
        "",
        "Fixed experiment: de-vigged Pinnacle ML -> neutral surface serve shape -> handicap.",
        "No threshold sweep. Prices and settlement are real captured Pinnacle rows.",
        "",
        f"Rows scored: {payload['rows_scored']}",
        f"Fixed edge threshold: {evaluation['edge_threshold_pct']:.1f}%",
        f"Priced bets: {evaluation['priced_bets']}",
        f"P/L: {fmt(evaluation['pnl_units'], 2)}u",
        f"ROI: {fmt(evaluation['roi_pct'], 2)}%",
        f"ROI CI95: {evaluation['roi_ci95_pct']}",
        f"Mean CLV: {fmt(evaluation['mean_clv_pct'], 3)}%",
        f"Positive CLV share (moved): {fmt(evaluation['positive_clv_share_moved_pct'], 2)}%",
        "",
        "Probability scoring:",
    ]
    for name, metrics in segments.items():
        lines.append(
            f"- {name}: n={metrics['non_push_rows']} "
            f"market={fmt(metrics['market_brier'], 6)} "
            f"old={fmt(metrics['old_brier'], 6)} "
            f"corrected={fmt(metrics['corrected_brier'], 6)} "
            f"push={fmt(100.0 * metrics['mean_push_mass'] if metrics['mean_push_mass'] is not None else None, 2)}%"
        )
    lines.extend(
        [
            "",
            f"Decision: {evaluation['status']}",
            "Gates:",
            *[
                f"- {name}: {'PASS' if passed else 'FAIL'}"
                for name, passed in evaluation["gates"].items()
            ],
            "",
            "Interpretation:",
            "- The old column reproduces the former BO3-only, push-as-opposite-side mathematics.",
            "- The corrected column uses explicit pushes, neutral first-server averaging and BO5 Slam main draws.",
            "- A mathematics fix is retained even when the betting lane fails; failure blocks signals, not correctness.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--out-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--edge-threshold", type=float, default=0.05)
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    scored = [
        scored_row
        for row in source_rows
        if (scored_row := score_row(row, args.edge_threshold)) is not None
    ]
    try:
        input_label = str(args.input.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        input_label = str(args.input)
    payload = {
        "version": "spread-shape-math-0.2",
        "input": input_label,
        "rows_scored": len(scored),
        "evaluation": evaluate(scored, args.edge_threshold),
    }
    write_csv(args.out_csv, scored)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.out_report.write_text(build_report(payload), encoding="utf-8")
    print(f"Scored {len(scored)} rows -> {args.out_csv}")
    print(f"Report -> {args.out_report}")
    print(f"Decision: {payload['evaluation']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
