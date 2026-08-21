#!/usr/bin/env python3
"""Evaluate additive Corners v4 features without modifying the live v3 lane.

The experiment keeps the registered v3 model as its control, adds only causal
pre-match favourite-strength and corners-per-shot features, and scores both
count folds and real Pinnacle market calibration. It never writes signal,
routing, lock, or production parameter files.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import mean
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_EVENTS = ROOT / "data" / "team-shots" / "understat" / "corner-event-features.csv"
DEFAULT_HISTORICAL = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_PINNACLE = ROOT / "data" / "corners-ou" / "pinnacle-corners-odds.csv"
DEFAULT_LOCK = ROOT / "data" / "corners-ou" / "corners-v3-lock.json"
DEFAULT_RESULTS = ROOT / "data" / "corners-ou" / "corners-v4-g0-fold-results.csv"
DEFAULT_JSON = ROOT / "data" / "corners-ou" / "corners-v4-g0-diagnostic.json"
DEFAULT_REPORT = ROOT / "data" / "corners-ou" / "corners-v4-g0-diagnostic.md"
G0_LINES = (7.5, 8.5, 9.5, 10.5, 11.5, 12.5)
MAX_LINE_RESIDUAL = 0.015
MAX_BRIER_DELTA = 0.010


def load_script(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def key_for(v3: ModuleType, sample: Any) -> tuple[str, str, str]:
    return (
        sample.match_date.isoformat(),
        v3.normalized_name(sample.home_team),
        v3.normalized_name(sample.away_team),
    )


def enrich_samples(
    v3: ModuleType,
    diagnostic: ModuleType,
    samples: list[Any],
    historical_path: Path,
) -> tuple[list[Any], dict[str, int]]:
    feature_index = diagnostic.build_feature_index(diagnostic.load_historical(historical_path))
    enriched: list[Any] = []
    missing = defaultdict(int)
    for sample in samples:
        extra = feature_index.get(key_for(v3, sample))
        if not extra:
            missing["fixture_not_found"] += 1
            continue
        fav_gap = diagnostic.pf(extra.get("fav_gap"))
        corner_per_shot = diagnostic.pf(extra.get("pre_corner_per_shot"))
        if fav_gap is None:
            missing["fav_gap_missing"] += 1
            continue
        if corner_per_shot is None or corner_per_shot <= 0:
            missing["corner_per_shot_missing"] += 1
            continue
        enriched.append(
            replace(
                sample,
                features=tuple(sample.features) + (float(fav_gap), math.log(float(corner_per_shot))),
            )
        )
    return enriched, dict(sorted(missing.items()))


def variant_specs() -> dict[str, tuple[int, ...]]:
    return {
        "v3_control": tuple(range(7)),
        "v3_plus_fav_gap": tuple(range(8)),
        "v3_plus_corner_per_shot": (*tuple(range(7)), 8),
        "v4_full": tuple(range(9)),
        "v4_lean_no_wide_block": (0, 1, 2, 3, 6, 7, 8),
        "v4_core": (0, 1, 2, 3, 7, 8),
    }


def evaluate_count_folds(v3: ModuleType, samples: list[Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for season in v3.VALIDATION_SEASONS:
        validation = [sample for sample in samples if sample.season == season]
        if not validation:
            continue
        start = min(sample.match_date for sample in validation)
        training = [sample for sample in samples if sample.match_date < start]
        for variant, indices in variant_specs().items():
            model = v3.fit_model(training, indices)
            scored = v3.score_fitted_model(model, validation)
            predictions = [model.predict(sample) for sample in validation]
            output.append(
                {
                    "season": season,
                    "variant": variant,
                    "train": len(training),
                    "validation": len(validation),
                    "mae": scored["mae"],
                    "brier": scored["brier"],
                    "log_loss": scored["log_loss"],
                    "bias": mean(prediction - sample.actual for sample, prediction in zip(validation, predictions)),
                    "alpha": scored["alpha"],
                }
            )
    return output


def score_market_g0(
    v3: ModuleType,
    real: ModuleType,
    samples: list[Any],
    pinnacle_path: Path,
) -> dict[str, Any]:
    markets = real.load_market_snapshots(pinnacle_path)
    market_dates = sorted(date.fromisoformat(key[0]) for key in markets)
    if not market_dates:
        return {"status": "NO_REAL_MARKETS", "variants": {}}
    training_cutoff = market_dates[0]
    training = [sample for sample in samples if sample.match_date < training_cutoff]
    sample_index = {key_for(v3, sample): sample for sample in samples}
    variants: dict[str, Any] = {}

    for variant, indices in variant_specs().items():
        model = v3.fit_model(training, indices)
        total_model_sq = 0.0
        total_market_sq = 0.0
        total_n = 0
        line_stats: dict[float, dict[str, float]] = defaultdict(
            lambda: {"n": 0.0, "prob": 0.0, "actual": 0.0, "model_sq": 0.0, "market_sq": 0.0}
        )
        misses: dict[str, int] = defaultdict(int)
        for (match_date, home, away, line_text, _league), snapshots in markets.items():
            sample = sample_index.get((match_date, home, away))
            if sample is None:
                misses["sample_not_found"] += 1
                continue
            try:
                line = float(line_text)
            except ValueError:
                misses["invalid_line"] += 1
                continue
            if line not in G0_LINES:
                continue
            pre_kickoff, kickoff = real.pre_kickoff_window(snapshots)
            if kickoff is None:
                misses["missing_kickoff"] += 1
                continue
            if not pre_kickoff:
                misses["no_pre_kickoff_price"] += 1
                continue
            if abs(sample.actual - line) < 1e-9:
                misses["push"] += 1
                continue
            publication = pre_kickoff[0]
            market_prob, _ = real.devig_two_way(publication.over_odds, publication.under_odds)
            model_prob = v3.prob_over(
                line,
                model.predict(sample),
                distribution="negative_binomial",
                alpha=model.alpha,
            )
            actual = 1.0 if sample.actual > line else 0.0
            model_sq = (model_prob - actual) ** 2
            market_sq = (market_prob - actual) ** 2
            total_model_sq += model_sq
            total_market_sq += market_sq
            total_n += 1
            stats = line_stats[line]
            stats["n"] += 1
            stats["prob"] += model_prob
            stats["actual"] += actual
            stats["model_sq"] += model_sq
            stats["market_sq"] += market_sq

        per_line: dict[str, Any] = {}
        line_gate = True
        for line in G0_LINES:
            stats = line_stats.get(line)
            if not stats or stats["n"] <= 0:
                per_line[f"{line:.1f}"] = {"n": 0, "status": "MISSING"}
                line_gate = False
                continue
            n = int(stats["n"])
            predicted = stats["prob"] / n
            actual_rate = stats["actual"] / n
            residual = predicted - actual_rate
            passed = abs(residual) <= MAX_LINE_RESIDUAL
            line_gate = line_gate and passed
            per_line[f"{line:.1f}"] = {
                "n": n,
                "predicted_over_rate": predicted,
                "actual_over_rate": actual_rate,
                "residual": residual,
                "model_brier": stats["model_sq"] / n,
                "market_brier": stats["market_sq"] / n,
                "gate": "PASS" if passed else "FAIL",
            }
        model_brier = total_model_sq / total_n if total_n else None
        market_brier = total_market_sq / total_n if total_n else None
        brier_gate = (
            model_brier is not None
            and market_brier is not None
            and model_brier <= market_brier + MAX_BRIER_DELTA
        )
        variants[variant] = {
            "training_cutoff": training_cutoff.isoformat(),
            "train": len(training),
            "market_rows": total_n,
            "model_brier": model_brier,
            "market_brier": market_brier,
            "brier_delta": model_brier - market_brier if model_brier is not None and market_brier is not None else None,
            "g0a_per_line_residual": "PASS" if line_gate else "FAIL",
            "g0b_brier": "PASS" if brier_gate else "FAIL",
            "g0_status": "PASS" if line_gate and brier_gate else "FAIL",
            "per_line": per_line,
            "misses": dict(sorted(misses.items())),
        }
    return {"status": "OK", "training_cutoff": training_cutoff.isoformat(), "variants": variants}


def write_fold_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ("season", "variant", "train", "validation", "mae", "brier", "log_loss", "bias", "alpha")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Corners v4 G0 diagnostic",
        "",
        "**RESEARCH ONLY. The live Corners v3 lane, locks, routing and stakes are unchanged.**",
        "",
        "Additive candidates: pre-match favourite-strength gap and lagged corners per shot.",
        f"Enriched samples: {payload['samples']['enriched']} / {payload['samples']['v3']}",
        f"Missing features: `{json.dumps(payload['samples']['missing'], sort_keys=True)}`",
        "",
        "## Count folds",
        "",
        "| Season | Variant | MAE | Brier | Log loss | Bias | NB alpha |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["folds"]:
        lines.append(
            f"| {row['season']} | {row['variant']} | {row['mae']:.4f} | {row['brier']:.4f} | "
            f"{row['log_loss']:.4f} | {row['bias']:+.4f} | {row['alpha']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Real-market G0",
            "",
            f"G0a: absolute predicted-minus-actual over-rate <= {MAX_LINE_RESIDUAL:.3f} at every line 7.5-12.5.",
            f"G0b: raw model Brier <= de-vigged Pinnacle Brier + {MAX_BRIER_DELTA:.3f}.",
            "",
            "| Variant | n | Model Brier | Market Brier | Delta | G0a | G0b | Overall |",
            "|---|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for name, result in payload["market_g0"].get("variants", {}).items():
        model_brier = result.get("model_brier")
        market_brier = result.get("market_brier")
        delta = result.get("brier_delta")
        lines.append(
            f"| {name} | {result['market_rows']} | "
            f"{model_brier:.6f} | {market_brier:.6f} | {delta:+.6f} | "
            f"{result['g0a_per_line_residual']} | {result['g0b_brier']} | {result['g0_status']} |"
        )
    lines.extend(["", "### Per-line calibration", ""])
    for name, result in payload["market_g0"].get("variants", {}).items():
        lines.extend(
            [
                f"#### {name}",
                "",
                "| Line | n | Predicted over | Actual over | Residual | Model Brier | Market Brier | Gate |",
                "|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for line, stats in result["per_line"].items():
            if stats.get("status") == "MISSING":
                lines.append(f"| {line} | 0 | - | - | - | - | - | FAIL |")
                continue
            lines.append(
                f"| {line} | {stats['n']} | {stats['predicted_over_rate']:.3%} | "
                f"{stats['actual_over_rate']:.3%} | {stats['residual']:+.3%} | "
                f"{stats['model_brier']:.6f} | {stats['market_brier']:.6f} | {stats['gate']} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Decision",
            "",
            "No candidate is promoted by this script. Passing G0 would only justify a locked prospective shadow registration; it would not establish a sellable edge.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--historical", type=Path, default=DEFAULT_HISTORICAL)
    parser.add_argument("--pinnacle", type=Path, default=DEFAULT_PINNACLE)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    v3 = load_script("corners_v3_g0_module", "corners-v3-folds.py")
    diagnostic = load_script("corners_v2_feature_module", "corners-v2-feature-diagnostics.py")
    real = load_script("corners_real_market_module", "corners-real-odds-backtest.py")
    v3.verify_locked_input(args.lock, "team_rolling_form", args.form)
    samples, coverage = v3.build_samples(
        v3.load_csv(args.form),
        v3.load_csv(args.events),
        v3.baseline_lookup(args.historical),
    )
    enriched, missing = enrich_samples(v3, diagnostic, samples, args.historical)
    if len(enriched) < 1000:
        raise SystemExit(f"Insufficient enriched samples: {len(enriched)}")
    v3.FEATURE_NAMES = (*tuple(v3.FEATURE_NAMES), "FAV_GAP", "LOG_CORNER_PER_SHOT")
    folds = evaluate_count_folds(v3, enriched)
    market_g0 = score_market_g0(v3, real, enriched, args.pinnacle)
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "RESEARCH_ONLY_NO_ROUTING_CHANGE",
        "coverage": coverage,
        "samples": {"v3": len(samples), "enriched": len(enriched), "missing": missing},
        "features": ["favourite_strength_gap", "lagged_corner_per_shot"],
        "folds": folds,
        "market_g0": market_g0,
        "guards": {
            "live_v3_modified": False,
            "routing_modified": False,
            "lock_modified": False,
            "promotion_automatic": False,
        },
    }
    write_fold_csv(args.results, folds)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(render_report(payload), encoding="utf-8")
    print(f"Enriched {len(enriched)}/{len(samples)} v3 samples")
    print(f"Wrote {args.results.relative_to(ROOT)}")
    print(f"Wrote {args.json.relative_to(ROOT)}")
    print(f"Wrote {args.report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
