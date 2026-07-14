#!/usr/bin/env python3
"""Freeze the registered Team Shots v4 and Corners v3 model parameters.

This is a release-time command, not a daily refit. The prospective scorers read
the generated JSON files so their parameters cannot drift during the locked
2026-27 shadow window.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_counts import fit_dispersion_alpha_mle  # noqa: E402


TEAM_PARAMS = ROOT / "data" / "team-shots" / "team-shots-v4-params.json"
CORNERS_PARAMS = ROOT / "data" / "corners-ou" / "corners-v3-params.json"


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def freeze_team_params(module: Any, output: Path) -> None:
    predictions = module.build_predictions(module.load_csv(module.DEFAULT_FORM))
    if not predictions:
        raise RuntimeError("Team Shots v4 produced no historical predictions")
    league_alpha, team_alpha = module.fitted_alphas(predictions)
    pooled_alpha = fit_dispersion_alpha_mle(
        [(row.actual, row.lam) for row in predictions],
        min_sample=30,
    )
    sample_counts = Counter((row.league, row.team_key) for row in predictions)
    payload = {
        "schema_version": 1,
        "model": "team_shots_v4",
        "frozen_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "training_through": max(row.match_date for row in predictions).isoformat(),
        "training_rows": len(predictions),
        "mean_model": "canonical_form_v3_ema20_frozen",
        "distribution": "nb2_hierarchical_team_alpha",
        "pooled_alpha": pooled_alpha,
        "league_alpha": dict(sorted(league_alpha.items())),
        "team_alpha": {
            f"{league}|{team}": {
                "alpha": alpha,
                "sample": sample_counts[(league, team)],
            }
            for (league, team), alpha in sorted(team_alpha.items())
        },
        "team_alpha_prior_weight": module.TEAM_PRIOR_WEIGHT,
        "market": {
            "blend": "shading_aware_logit",
            "model_weight": 0.18,
            "over_vig_share": 0.856,
        },
    }
    write_json(output, payload)


def freeze_corners_params(module: Any, output: Path) -> None:
    samples, coverage = module.build_samples(
        module.load_csv(module.DEFAULT_FORM),
        module.load_csv(module.DEFAULT_EVENTS),
        module.baseline_lookup(module.DEFAULT_HISTORICAL),
    )
    if not samples:
        raise RuntimeError("Corners v3 produced no historical samples")
    model = module.fit_model(samples)
    payload = {
        "schema_version": 1,
        "model": "corners_v3",
        "frozen_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "training_through": max(sample.match_date for sample in samples).isoformat(),
        "training_rows": len(samples),
        "mean_model": "nb_regression_cf_ca_wide_block_tempo",
        "distribution": "nb2_fitted_alpha",
        "feature_names": list(module.FEATURE_NAMES),
        "feature_indices": list(model.feature_indices),
        "beta": list(model.beta),
        "centers": list(model.centers),
        "scales": list(model.scales),
        "alpha": model.alpha,
        "event_feature_coverage": coverage["event_coverage"],
        "event_min_history": module.MIN_HISTORY,
        "event_decay": module.DECAY,
        "event_window": module.WINDOW,
    }
    write_json(output, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-output", type=Path, default=TEAM_PARAMS)
    parser.add_argument("--corners-output", type=Path, default=CORNERS_PARAMS)
    args = parser.parse_args()

    team_module = load_module("team_shots_v4_freeze", SCRIPTS / "team-shots-v4-folds.py")
    corners_module = load_module("corners_v3_freeze", SCRIPTS / "corners-v3-folds.py")
    freeze_team_params(team_module, args.team_output)
    freeze_corners_params(corners_module, args.corners_output)
    print(f"Wrote {args.team_output.relative_to(ROOT)}")
    print(f"Wrote {args.corners_output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
