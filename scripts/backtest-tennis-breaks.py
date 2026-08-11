#!/usr/bin/env python3
"""Walk-forward validation for player and match service-break projections.

The model is evaluated on counts only. No synthetic bookmaker prices are used,
so the report is calibration evidence rather than ROI evidence.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SACKMANN_DIR = ROOT / "data" / "sackmann"
OUT_DIR = ROOT / "data" / "tennis-props" / "backtest"
DEFAULT_ROWS = OUT_DIR / "breaks-stage0-rows.csv"
DEFAULT_REPORT = OUT_DIR / "breaks-stage0-report.txt"
DEFAULT_GATE = OUT_DIR / "breaks-stage0-gate.json"

sys.path.insert(0, str(SCRIPTS))
from tennis_props_model import (  # noqa: E402
    negative_binomial_pmf,
    negative_binomial_line_probabilities,
    poisson_line_probabilities,
    project_player,
)


def load_backtest_core():
    path = SCRIPTS / "backtest-tennis-player-props.py"
    spec = importlib.util.spec_from_file_location("tennis_props_backtest_core", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CORE = load_backtest_core()


@dataclass(frozen=True)
class BreakEvalRow:
    tour: str
    year: int
    date: str
    tournament: str
    surface: str
    best_of: int
    player: str
    opponent: str
    scope: str
    actual: int
    projected: float
    naive: float
    expected_match_games: float
    event_prior_matches: int
    event_break_factor: float
    confidence: str


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def rank_bucket(row: dict[str, str]) -> str:
    winner_rank = CORE.parse_int(row.get("winner_rank"))
    loser_rank = CORE.parse_int(row.get("loser_rank"))
    if winner_rank <= 0 or loser_rank <= 0:
        return "unknown"
    gap = abs(math.log(max(1, winner_rank) / max(1, loser_rank)))
    if gap < 0.25:
        return "close"
    if gap < 0.80:
        return "medium"
    return "wide"


def default_match_games(tour: str, best_of: int) -> float:
    if best_of >= 5:
        return 38.5
    return 21.7 if tour == "atp" else 21.5


def context_expected_games(
    contexts: dict[tuple[str, str, int, str], list[float]],
    *,
    tour: str,
    surface: str,
    best_of: int,
    bucket: str,
) -> float:
    exact = contexts.get((tour, surface, best_of, bucket), [])
    pooled: list[float] = []
    for (ctx_tour, ctx_surface, ctx_best_of, _), values in contexts.items():
        if ctx_tour == tour and ctx_surface == surface and ctx_best_of == best_of:
            pooled.extend(values)
    if len(exact) >= 80:
        return clip(mean(exact[-600:]), 15.0 if best_of == 3 else 27.0, 29.0 if best_of == 3 else 52.0)
    if len(pooled) >= 160:
        return clip(mean(pooled[-1200:]), 15.0 if best_of == 3 else 27.0, 29.0 if best_of == 3 else 52.0)
    return default_match_games(tour, best_of)


def match_break_counts(row: dict[str, str]) -> tuple[int, int] | None:
    winner_service_games = CORE.parse_int(row.get("w_SvGms"))
    loser_service_games = CORE.parse_int(row.get("l_SvGms"))
    if winner_service_games <= 0 or loser_service_games <= 0:
        return None
    winner_breaks = max(0, CORE.parse_int(row.get("l_bpFaced")) - CORE.parse_int(row.get("l_bpSaved")))
    loser_breaks = max(0, CORE.parse_int(row.get("w_bpFaced")) - CORE.parse_int(row.get("w_bpSaved")))
    return winner_breaks, loser_breaks


def event_environment(state: dict[str, float], tour: str) -> tuple[dict[str, str], int, float]:
    matches = int(state.get("matches", 0))
    games = state.get("games", 0.0)
    breaks = state.get("breaks", 0.0)
    if matches < 2 or games <= 0:
        return {}, matches, 1.0
    baseline = 0.235 if tour == "atp" else 0.285
    current_rate = breaks / games
    weight = clip(matches / 20.0 * 0.10, 0.0, 0.10)
    ratio = clip(current_rate / baseline, 0.25, 4.0)
    factor = clip(math.exp(math.log(ratio) * weight), 0.92, 1.08)
    return {
        "matches": str(matches),
        "weight": f"{weight:.4f}",
        "break_factor": f"{factor:.6f}",
    }, matches, factor


def factor_row(tour: str, surface: str, tournament: str, best_of: int) -> dict[str, str]:
    return {
        "tour": tour.upper(),
        "surface": surface,
        "tournament": tournament if best_of >= 5 else "",
        "tour_surface_baseline_ace": "0.065" if tour == "atp" else "0.027",
        "tour_surface_baseline_df": "0.035" if tour == "atp" else "0.048",
        "svpt_per_svgame": "6.35",
        "ace_factor": "1.0",
        "df_factor": "1.0",
    }


def naive_break_rate(tour: str) -> float:
    return 0.235 if tour == "atp" else 0.285


def build_rows(
    sackmann_dir: Path,
    years: Iterable[int],
    *,
    first_eval_year: int,
) -> list[BreakEvalRow]:
    matches, events = CORE.load_data(sackmann_dir, years)
    events_by_player: dict[tuple[str, str], list[object]] = defaultdict(list)
    for event in events:
        events_by_player[(event.tour, event.player_id)].append(event)

    game_contexts: dict[tuple[str, str, int, str], list[float]] = defaultdict(list)
    event_states: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    out: list[BreakEvalRow] = []

    for row in matches:
        match_date = CORE.parse_date(row.get("_date_iso"))
        if match_date is None:
            continue
        tour = str(row.get("_tour") or "")
        surface = str(row.get("_surface_norm") or "")
        best_of = CORE.parse_int(row.get("best_of")) or 3
        tournament = str(row.get("tourney_name") or "").strip()
        tourney_id = str(row.get("tourney_id") or "").strip()
        counts = match_break_counts(row)
        match_games = CORE.parse_int(row.get("_match_games"))
        if counts is None or match_games <= 0 or surface not in {"Hard", "Clay", "Grass", "Carpet"}:
            continue
        winner_breaks, loser_breaks = counts
        bucket = rank_bucket(row)
        expected_games = context_expected_games(
            game_contexts,
            tour=tour,
            surface=surface,
            best_of=best_of,
            bucket=bucket,
        )
        env_row, env_matches, env_factor = event_environment(event_states[(tour, tourney_id)], tour)

        winner_id = str(row.get("winner_id") or "").strip()
        loser_id = str(row.get("loser_id") or "").strip()
        winner_name = str(row.get("winner_name") or "").strip()
        loser_name = str(row.get("loser_name") or "").strip()
        if not winner_id or not loser_id:
            continue
        winner_rows = CORE.build_window_rows(
            tour=tour,
            player_id=winner_id,
            player_name=winner_name,
            surface=surface,
            as_of=match_date,
            events_by_player=events_by_player,
        )
        loser_rows = CORE.build_window_rows(
            tour=tour,
            player_id=loser_id,
            player_name=loser_name,
            surface=surface,
            as_of=match_date,
            events_by_player=events_by_player,
        )
        winner_same = CORE.build_same_tournament_row(
            tour=tour,
            player_id=winner_id,
            tourney_id=tourney_id,
            as_of=match_date,
            events_by_player=events_by_player,
        )
        loser_same = CORE.build_same_tournament_row(
            tour=tour,
            player_id=loser_id,
            tourney_id=tourney_id,
            as_of=match_date,
            events_by_player=events_by_player,
        )
        factors = factor_row(tour, surface, tournament, best_of)
        winner_projection = project_player(
            tour=tour,
            player_rows=winner_rows,
            opponent_rows=loser_rows,
            factor_row=factors,
            expected_match_games=expected_games,
            slam_matches=0,
            same_tournament_row=winner_same,
            current_tournament_env_row=env_row,
        )
        loser_projection = project_player(
            tour=tour,
            player_rows=loser_rows,
            opponent_rows=winner_rows,
            factor_row=factors,
            expected_match_games=expected_games,
            slam_matches=0,
            same_tournament_row=loser_same,
            current_tournament_env_row=env_row,
        )

        if match_date.year >= first_eval_year:
            base_player = naive_break_rate(tour) * expected_games * 0.5
            match_projection = winner_projection.expected_breaks_for + loser_projection.expected_breaks_for
            shared = {
                "tour": tour.upper(),
                "year": match_date.year,
                "date": match_date.isoformat(),
                "tournament": tournament,
                "surface": surface,
                "best_of": best_of,
                "expected_match_games": expected_games,
                "event_prior_matches": env_matches,
                "event_break_factor": env_factor,
            }
            out.extend(
                [
                    BreakEvalRow(
                        **shared,
                        player=winner_name,
                        opponent=loser_name,
                        scope="player_breaks",
                        actual=winner_breaks,
                        projected=winner_projection.expected_breaks_for,
                        naive=base_player,
                        confidence=winner_projection.break_confidence,
                    ),
                    BreakEvalRow(
                        **shared,
                        player=loser_name,
                        opponent=winner_name,
                        scope="player_breaks",
                        actual=loser_breaks,
                        projected=loser_projection.expected_breaks_for,
                        naive=base_player,
                        confidence=loser_projection.break_confidence,
                    ),
                    BreakEvalRow(
                        **shared,
                        player=winner_name,
                        opponent=loser_name,
                        scope="match_breaks",
                        actual=winner_breaks + loser_breaks,
                        projected=match_projection,
                        naive=naive_break_rate(tour) * expected_games,
                        confidence=min(
                            (winner_projection.break_confidence, loser_projection.break_confidence),
                            key=lambda value: {"LOW": 0, "MED": 1, "HIGH": 2}.get(value, 0),
                        ),
                    ),
                ]
            )

        game_contexts[(tour, surface, best_of, bucket)].append(float(match_games))
        state = event_states[(tour, tourney_id)]
        state["matches"] += 1
        state["games"] += match_games
        state["breaks"] += winner_breaks + loser_breaks

    return out


def fit_alpha(rows: list[BreakEvalRow]) -> float:
    best_alpha = 0.0
    best_loss = float("inf")
    for step in range(0, 81):
        alpha = step * 0.01
        loss = 0.0
        for row in rows:
            probability = max(1e-12, negative_binomial_pmf(row.actual, row.projected, alpha))
            loss -= math.log(probability)
        loss /= max(1, len(rows))
        if loss < best_loss:
            best_loss = loss
            best_alpha = alpha
    return best_alpha


def lines_for(scope: str) -> list[float]:
    return [1.5, 2.5, 3.5, 4.5, 5.5] if scope == "player_breaks" else [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5]


def probability_metrics(rows: list[BreakEvalRow], alpha: float) -> dict[str, float]:
    model_errors: list[float] = []
    poisson_errors: list[float] = []
    naive_errors: list[float] = []
    calibration: dict[int, list[float]] = defaultdict(list)
    poisson_calibration: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        for line in lines_for(row.scope):
            outcome = 1.0 if row.actual > line else 0.0
            model_prob = negative_binomial_line_probabilities(line, row.projected, alpha)[0]
            poisson_prob = poisson_line_probabilities(line, row.projected)[0]
            naive_prob = negative_binomial_line_probabilities(line, row.naive, alpha)[0]
            model_errors.append((model_prob - outcome) ** 2)
            poisson_errors.append((poisson_prob - outcome) ** 2)
            naive_errors.append((naive_prob - outcome) ** 2)
            calibration[int(clip(model_prob, 0.0, 0.999999) * 10)].append(outcome - model_prob)
            poisson_calibration[int(clip(poisson_prob, 0.0, 0.999999) * 10)].append(outcome - poisson_prob)
    ece = sum(abs(mean(values)) * len(values) for values in calibration.values()) / max(1, len(model_errors))
    poisson_ece = sum(abs(mean(values)) * len(values) for values in poisson_calibration.values()) / max(1, len(poisson_errors))
    return {
        "brier": mean(model_errors) if model_errors else float("nan"),
        "poisson_brier": mean(poisson_errors) if poisson_errors else float("nan"),
        "naive_brier": mean(naive_errors) if naive_errors else float("nan"),
        "ece": ece,
        "poisson_ece": poisson_ece,
    }


def count_metrics(rows: list[BreakEvalRow]) -> dict[str, float]:
    errors = [row.projected - row.actual for row in rows]
    naive_errors = [row.naive - row.actual for row in rows]
    return {
        "n": float(len(rows)),
        "mae": mean(abs(value) for value in errors) if errors else float("nan"),
        "naive_mae": mean(abs(value) for value in naive_errors) if naive_errors else float("nan"),
        "bias": mean(errors) if errors else float("nan"),
        "rmse": math.sqrt(mean(value * value for value in errors)) if errors else float("nan"),
        "actual_mean": mean(row.actual for row in rows) if rows else float("nan"),
        "projected_mean": mean(row.projected for row in rows) if rows else float("nan"),
    }


def write_csv(path: Path, rows: list[BreakEvalRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(rows[0]).keys()) if rows else list(BreakEvalRow.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def build_gate(rows: list[BreakEvalRow], train_years: set[int], eval_years: set[int]) -> dict[str, object]:
    scopes: dict[str, object] = {}
    for scope in ("player_breaks", "match_breaks"):
        tours: dict[str, object] = {}
        for tour in ("ATP", "WTA"):
            train = [row for row in rows if row.scope == scope and row.tour == tour and row.year in train_years]
            holdout = [row for row in rows if row.scope == scope and row.tour == tour and row.year in eval_years]
            alpha = fit_alpha(train) if train else 0.0
            train_probabilities = probability_metrics(train, alpha)
            distribution = (
                "negative_binomial"
                if train_probabilities["brier"] <= train_probabilities["poisson_brier"]
                else "poisson"
            )
            counts = count_metrics(holdout)
            probabilities = probability_metrics(holdout, alpha)
            selected_brier = (
                probabilities["brier"]
                if distribution == "negative_binomial"
                else probabilities["poisson_brier"]
            )
            selected_ece = probabilities["ece"] if distribution == "negative_binomial" else probabilities["poisson_ece"]
            passed = bool(
                len(holdout) >= 500
                and counts["mae"] <= counts["naive_mae"]
                and selected_brier <= probabilities["naive_brier"]
                and selected_ece <= 0.05
                and abs(counts["bias"]) <= 0.35
            )
            tours[tour] = {
                "passed": passed,
                "distribution": distribution,
                "model_alpha": round(alpha, 4),
                "train_n": len(train),
                "holdout_n": len(holdout),
                **{key: round(value, 6) for key, value in counts.items()},
                **{key: round(value, 6) for key, value in probabilities.items()},
                "selected_brier": round(selected_brier, 6),
                "selected_ece": round(selected_ece, 6),
            }
        scopes[scope] = {"passed": all(bool(row["passed"]) for row in tours.values()), "tours": tours}
    return {
        "status": "PASS" if all(bool(row["passed"]) for row in scopes.values()) else "FAIL_CLOSED",
        "method": "walk_forward_player_opponent_break_rates_plus_event_environment_registered_count_family",
        "train_years": sorted(train_years),
        "holdout_years": sorted(eval_years),
        "real_price_evidence": False,
        "scopes": scopes,
    }


def write_report(path: Path, gate: dict[str, object]) -> None:
    lines = [
        "Tennis service breaks Stage-0",
        "",
        f"Status: {gate['status']}",
        "Evidence: outcome-only walk-forward validation; no synthetic ROI and no Bet365 price claim.",
        "Provider audit: the 2026-08-11 exact unfiltered Bet365 payload for Merida-Tien exposed no service-break market.",
        f"Train years: {gate['train_years']} | Holdout years: {gate['holdout_years']}",
        "",
    ]
    for scope, scope_row in gate["scopes"].items():
        lines.append(f"{scope}: {'PASS' if scope_row['passed'] else 'FAIL'}")
        for tour, row in scope_row["tours"].items():
            lines.append(
                f"  {tour}: n={row['holdout_n']} {row['distribution']} alpha={row['model_alpha']:.2f} "
                f"MAE={row['mae']:.3f} (naive {row['naive_mae']:.3f}) "
                f"bias={row['bias']:+.3f} Brier={row['selected_brier']:.4f} "
                f"(Poisson {row['poisson_brier']:.4f}, naive {row['naive_brier']:.4f}) "
                f"ECE={row['selected_ece']:.4f} {'PASS' if row['passed'] else 'FAIL'}"
            )
        lines.append("")
    lines.extend(
        [
            "Decision",
            "- Fair-odds ladders may be shown as internal research even when the gate fails.",
            "- No break bet becomes a recommendation without a captured real price and a separate prospective gate.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest tennis player/match service-break projections.")
    parser.add_argument("--sackmann-dir", type=Path, default=SACKMANN_DIR)
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--train-years", nargs="+", type=int, default=[2023, 2024])
    parser.add_argument("--eval-years", nargs="+", type=int, default=[2025, 2026])
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--out-txt", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out-gate", type=Path, default=DEFAULT_GATE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    all_years = list(range(args.start_year, args.end_year + 1))
    first_eval_year = min(min(args.train_years), min(args.eval_years))
    rows = build_rows(args.sackmann_dir, all_years, first_eval_year=first_eval_year)
    if not rows:
        raise SystemExit("No break backtest rows generated.")
    gate = build_gate(rows, set(args.train_years), set(args.eval_years))
    write_csv(args.out_csv, [row for row in rows if row.year in set(args.eval_years)])
    args.out_gate.parent.mkdir(parents=True, exist_ok=True)
    args.out_gate.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    write_report(args.out_txt, gate)
    print(f"Wrote {args.out_txt}")
    print(f"Wrote {args.out_gate}")
    print(f"Wrote {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
