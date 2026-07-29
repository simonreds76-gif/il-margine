#!/usr/bin/env python3
"""Run the registered A0/A1 ATP ace coverage experiment."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEFAULT_A0 = (
    ROOT / "data" / "tennis-props" / "backtest"
    / "aces-dfs-v3-all-tour-features.csv"
)
DEFAULT_A1 = (
    ROOT / "data" / "tennis-props" / "experiments"
    / "most-aces-coverage-a1" / "aces-dfs-v3-features.csv"
)
DEFAULT_DIR = (
    ROOT / "data" / "tennis-props" / "experiments" / "most-aces-coverage-a1"
)


def load_fit_module():
    path = SCRIPTS / "fit-tennis-props-v3.py"
    spec = importlib.util.spec_from_file_location("fit_tennis_props_v3_a1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fit_arm(module, source: Path, model_dir: Path):
    frame, feature_columns = module.prepare_frame(source)
    live_features = module.live_ace_feature_columns(feature_columns)
    result, predictions, importance = module.fit_cell(
        frame,
        live_features,
        "ATP",
        "aces",
        model_dir,
        categorical_columns=module.LIVE_CATEGORICAL,
        model_suffix="-live",
    )
    return result, predictions, importance


def metric_delta(a1: dict[str, object], a0: dict[str, object], key: str) -> float:
    return float(a1[key]) - float(a0[key])


def comparison(a0: dict[str, object], a1: dict[str, object], period: str) -> dict[str, object]:
    left = a0 if period == "confirmatory_2026" else a0["selection_2025"]
    right = a1 if period == "confirmatory_2026" else a1["selection_2025"]
    assert isinstance(left, dict) and isinstance(right, dict)
    a0_mae = float(left["candidate_mae"])
    a1_mae = float(right["candidate_mae"])
    mae_improvement = 100.0 * (a0_mae - a1_mae) / a0_mae
    logloss_delta = metric_delta(right, left, "candidate_logloss")
    return {
        "a0_candidate_mae": a0_mae,
        "a1_candidate_mae": a1_mae,
        "a1_vs_a0_mae_improvement_pct": mae_improvement,
        "a0_candidate_logloss": float(left["candidate_logloss"]),
        "a1_candidate_logloss": float(right["candidate_logloss"]),
        "a1_vs_a0_logloss_delta": logloss_delta,
        "g1_mae_pass": mae_improvement >= 1.0,
        "g2_logloss_pass": logloss_delta <= -0.002,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a0-source", type=Path, default=DEFAULT_A0)
    parser.add_argument("--a1-source", type=Path, default=DEFAULT_A1)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    module = load_fit_module()
    a0, a0_predictions, a0_importance = fit_arm(
        module, args.a0_source, args.out_dir / "models-a0"
    )
    a1, a1_predictions, a1_importance = fit_arm(
        module, args.a1_source, args.out_dir / "models-a1"
    )
    selection = comparison(a0, a1, "selection_2025")
    confirmatory = comparison(a0, a1, "confirmatory_2026")
    selection_pass = bool(selection["g1_mae_pass"] and selection["g2_logloss_pass"])
    confirmatory_pass = bool(
        confirmatory["g1_mae_pass"] and confirmatory["g2_logloss_pass"]
    )
    payload = {
        "version": "most-aces-coverage-a1-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "PASS" if selection_pass and confirmatory_pass else "FAIL",
        "routing": "EXPERIMENT_ONLY_NO_LIVE_CHANGE",
        "a0_source": str(args.a0_source),
        "a1_source": str(args.a1_source),
        "selection_2025": selection,
        "confirmatory_2026": confirmatory,
        "a0": a0,
        "a1": a1,
        "decision": (
            "A1 eligible for prospective freeze"
            if selection_pass and confirmatory_pass
            else "A1 rejected; retain A0 projection model"
        ),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "a0-predictions-2026.csv").write_text(
        a0_predictions.to_csv(index=False), encoding="utf-8"
    )
    (args.out_dir / "a1-predictions-2026.csv").write_text(
        a1_predictions.to_csv(index=False), encoding="utf-8"
    )
    (args.out_dir / "a0-importance.csv").write_text(
        a0_importance.to_csv(index=False), encoding="utf-8"
    )
    (args.out_dir / "a1-importance.csv").write_text(
        a1_importance.to_csv(index=False), encoding="utf-8"
    )
    (args.out_dir / "result.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "Most Aces coverage A1 registered experiment",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']} | {payload['routing']}",
        "",
        (
            "Selection 2025: "
            f"MAE {selection['a0_candidate_mae']:.4f} -> "
            f"{selection['a1_candidate_mae']:.4f} "
            f"({selection['a1_vs_a0_mae_improvement_pct']:+.2f}%); "
            f"log-loss delta {selection['a1_vs_a0_logloss_delta']:+.6f}"
        ),
        (
            "Confirmatory 2026: "
            f"MAE {confirmatory['a0_candidate_mae']:.4f} -> "
            f"{confirmatory['a1_candidate_mae']:.4f} "
            f"({confirmatory['a1_vs_a0_mae_improvement_pct']:+.2f}%); "
            f"log-loss delta {confirmatory['a1_vs_a0_logloss_delta']:+.6f}"
        ),
        "",
        f"Decision: {payload['decision']}",
        "No production model, signal routing, ROI or CLV claim changed.",
    ]
    (args.out_dir / "report.txt").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
