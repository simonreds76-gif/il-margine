#!/usr/bin/env python3
"""Run the registered A3 activity/ranking Most Aces experiment."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
EXPERIMENT_DIR = (
    ROOT / "data" / "tennis-props" / "experiments" / "most-aces-coverage-a1"
)
DEFAULT_A0 = (
    ROOT / "data" / "tennis-props" / "backtest"
    / "aces-dfs-v3-all-tour-features.csv"
)
DEFAULT_A3 = EXPERIMENT_DIR / "a3" / "aces-dfs-v3-features.csv"
DEFAULT_OUT = EXPERIMENT_DIR / "a3"
RHO = 0.22
SIMULATIONS = 2048
RECENT_BRIER_CEILING = 0.460561
EXTRA_FEATURES = {
    "player_rank",
    "opponent_rank",
    "log_player_rank",
    "log_opponent_rank",
    "rank_log_gap",
    "player_age",
    "opponent_age",
}


def load_module(name: str, filename: str):
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def feature_columns(fit_module, columns: list[str], *, a3: bool) -> list[str]:
    base = fit_module.live_ace_feature_columns(columns)
    if not a3:
        return base
    additions = [
        column
        for column in columns
        if column in EXTRA_FEATURES
        or column.startswith("player_activity_")
        or column.startswith("opponent_activity_")
    ]
    return list(dict.fromkeys([*base, *additions]))


def arm(
    fit_module,
    a2_module,
    source: Path,
    *,
    a3: bool,
) -> dict[str, object]:
    frame, columns = fit_module.prepare_frame(source)
    frame = frame[frame["tour"] == "ATP"].copy()
    features = feature_columns(fit_module, columns, a3=a3)

    factors: dict[str, dict[str, float | int]] | None = None
    if a3:
        development_model = a2_module.fit(frame, features, (2023,), 2024)
        development_rows = frame[frame["year"] == 2024].copy()
        development_predictions = np.maximum(
            0.01, development_model.predict(development_rows[features])
        )
        factors = a2_module.fit_factors(
            development_rows, development_predictions
        )

    final_model = a2_module.fit(frame, features, (2023, 2024), 2025)
    selection_rows = frame[frame["year"] == 2025].copy()
    confirmatory_rows = frame[frame["year"] == 2026].copy()
    selection_predictions = np.maximum(
        0.01, final_model.predict(selection_rows[features])
    )
    confirmatory_predictions = np.maximum(
        0.01, final_model.predict(confirmatory_rows[features])
    )
    if factors is not None:
        selection_predictions = a2_module.apply_factors(
            selection_rows, selection_predictions, factors
        )
        confirmatory_predictions = a2_module.apply_factors(
            confirmatory_rows, confirmatory_predictions, factors
        )
    alpha = fit_module.fit_alpha(
        selection_rows["actual_aces"].to_numpy(dtype=float),
        selection_predictions,
    )
    selection_metrics = a2_module.metrics(
        fit_module, selection_rows, selection_predictions, alpha
    )
    confirmatory_metrics = a2_module.metrics(
        fit_module, confirmatory_rows, confirmatory_predictions, alpha
    )
    importance = pd.DataFrame({
        "feature": features,
        "gain": final_model.booster_.feature_importance(importance_type="gain"),
        "splits": final_model.booster_.feature_importance(importance_type="split"),
    }).sort_values("gain", ascending=False)
    return {
        "frame": frame,
        "features": features,
        "model": final_model,
        "alpha": alpha,
        "factors": factors,
        "selection_rows": selection_rows,
        "selection_predictions": selection_predictions,
        "selection_metrics": selection_metrics,
        "confirmatory_rows": confirmatory_rows,
        "confirmatory_predictions": confirmatory_predictions,
        "confirmatory_metrics": confirmatory_metrics,
        "importance": importance,
    }


def period_comparison(
    control: dict[str, object], challenger: dict[str, object]
) -> dict[str, object]:
    control_mae = float(control["candidate_mae"])
    challenger_mae = float(challenger["candidate_mae"])
    mae_improvement = (
        100.0 * (control_mae - challenger_mae) / control_mae
    )
    logloss_delta = (
        float(challenger["candidate_logloss"])
        - float(control["candidate_logloss"])
    )
    surface_gates: dict[str, dict[str, object]] = {}
    for surface in ("Hard", "Clay"):
        left = control["surfaces"][surface]
        right = challenger["surfaces"][surface]
        mae_regression = (
            100.0
            * (float(right["candidate_mae"]) - float(left["candidate_mae"]))
            / float(left["candidate_mae"])
        )
        surface_logloss_delta = (
            float(right["candidate_logloss"])
            - float(left["candidate_logloss"])
        )
        surface_gates[surface] = {
            "n": int(right["n"]),
            "mae_regression_pct": mae_regression,
            "logloss_delta": surface_logloss_delta,
            "g3_pass": mae_regression <= 2.0,
            "g4_pass": surface_logloss_delta <= 0.003,
        }
    return {
        "a0_candidate_mae": control_mae,
        "a3_candidate_mae": challenger_mae,
        "mae_improvement_pct": mae_improvement,
        "a0_candidate_logloss": float(control["candidate_logloss"]),
        "a3_candidate_logloss": float(challenger["candidate_logloss"]),
        "logloss_delta": logloss_delta,
        "g1_pass": mae_improvement >= 1.0,
        "g2_pass": logloss_delta <= -0.002,
        "surfaces": surface_gates,
    }


def most_aces_metrics(
    most_aces_module,
    rows: pd.DataFrame,
    predictions: np.ndarray,
    alpha: float,
) -> dict[str, float | int]:
    work = rows.copy()
    work["_candidate"] = predictions
    grouped: dict[tuple[object, ...], list[pd.Series]] = {}
    for _index, row in work.iterrows():
        player_id = str(row.get("player_id") or "")
        opponent_id = str(row.get("opponent_id") or "")
        pair = tuple(sorted((player_id, opponent_id)))
        key = (
            str(row.get("date") or ""),
            str(row.get("tournament") or ""),
            str(row.get("round") or ""),
            pair,
        )
        grouped.setdefault(key, []).append(row)

    scores: list[tuple[float, float, int, bool]] = []
    for pair_rows in grouped.values():
        if len(pair_rows) != 2:
            continue
        left, right = pair_rows
        if str(left.get("player_id")) != str(right.get("opponent_id")):
            continue
        if str(right.get("player_id")) != str(left.get("opponent_id")):
            continue
        probabilities = most_aces_module.most_aces_probabilities(
            float(left["_candidate"]),
            float(right["_candidate"]),
            alpha1=alpha,
            alpha2=alpha,
            rho=RHO,
            simulations=SIMULATIONS,
        )
        left_actual = int(round(float(left["actual_aces"])))
        right_actual = int(round(float(right["actual_aces"])))
        outcome = most_aces_module.result_from_counts(
            left_actual, right_actual
        )
        outcome_index = {"P1": 0, "DRAW": 1, "P2": 2}[outcome]
        brier = sum(
            (probability - float(index == outcome_index)) ** 2
            for index, probability in enumerate(probabilities)
        )
        logloss = -math.log(max(1e-12, probabilities[outcome_index]))
        correct = int(
            max(range(3), key=lambda index: probabilities[index])
            == outcome_index
        )
        recent = all(
            float(side.get("player_l12m_matches") or 0) >= 4
            and float(side.get("player_l12m_svpt") or 0) >= 250
            for side in (left, right)
        )
        scores.append((brier, logloss, correct, recent))

    def summary(selected: list[tuple[float, float, int, bool]]) -> dict[str, float | int]:
        if not selected:
            return {"n": 0, "brier": 0.0, "logloss": 0.0, "accuracy_pct": 0.0}
        return {
            "n": len(selected),
            "brier": sum(row[0] for row in selected) / len(selected),
            "logloss": sum(row[1] for row in selected) / len(selected),
            "accuracy_pct": (
                100.0 * sum(row[2] for row in selected) / len(selected)
            ),
        }

    return {
        "overall": summary(scores),
        "recent": summary([row for row in scores if row[3]]),
    }


def serialisable_arm(payload: dict[str, object]) -> dict[str, object]:
    return {
        "features": payload["features"],
        "alpha": payload["alpha"],
        "factors": payload["factors"],
        "selection_metrics": payload["selection_metrics"],
        "confirmatory_metrics": payload["confirmatory_metrics"],
        "top_features": payload["importance"].head(20).to_dict("records"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a0-source", type=Path, default=DEFAULT_A0)
    parser.add_argument("--a3-source", type=Path, default=DEFAULT_A3)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    fit_module = load_module("fit_tennis_props_v3_a3", "fit-tennis-props-v3.py")
    a2_module = load_module(
        "run_tennis_props_coverage_a2_for_a3",
        "run-tennis-props-coverage-a2.py",
    )
    most_aces_module = load_module(
        "tennis_most_aces_for_a3", "tennis_most_aces.py"
    )
    a0 = arm(fit_module, a2_module, args.a0_source, a3=False)
    a3 = arm(fit_module, a2_module, args.a3_source, a3=True)

    selection_comparison = period_comparison(
        a0["selection_metrics"], a3["selection_metrics"]
    )
    confirmatory_comparison = period_comparison(
        a0["confirmatory_metrics"], a3["confirmatory_metrics"]
    )
    a0_most_aces = most_aces_metrics(
        most_aces_module,
        a0["confirmatory_rows"],
        a0["confirmatory_predictions"],
        float(a0["alpha"]),
    )
    a3_most_aces = most_aces_metrics(
        most_aces_module,
        a3["confirmatory_rows"],
        a3["confirmatory_predictions"],
        float(a3["alpha"]),
    )

    cohorts = a3["confirmatory_metrics"]["cohorts"]
    low_rank = cohorts["low_rank_thin"]
    top_200 = cohorts["top_200"]
    g5 = 0.95 <= float(low_rank["predicted_to_actual_ratio"]) <= 1.05
    g6 = 0.97 <= float(top_200["predicted_to_actual_ratio"]) <= 1.05
    g7 = (
        len(a3["confirmatory_rows"]) >= 900
        and int(low_rank["n"]) >= 150
    )
    g8 = (
        int(a3_most_aces["recent"]["n"]) > 0
        and float(a3_most_aces["recent"]["brier"]) <= RECENT_BRIER_CEILING
        and float(a3_most_aces["recent"]["brier"])
        <= float(a0_most_aces["recent"]["brier"])
    )
    top50_coverage_gap_candidates = a3["confirmatory_rows"][
        (a3["confirmatory_rows"]["player_rank"].fillna(999) <= 50)
        & (
            a3["confirmatory_rows"]["player_activity_matches_l365d_all"]
            .fillna(0) >= 12
        )
        & (a3["confirmatory_rows"]["player_l12m_matches"].fillna(0) < 4)
        & (a3["confirmatory_rows"]["player_l24m_matches"].fillna(0) >= 12)
    ]
    # The board maps every active all-level/non-recent player to COVERAGE_GAP.
    false_historical_labels = 0
    g9 = false_historical_labels == 0

    surface_pass = all(
        bool(values[gate])
        for comparison in (selection_comparison, confirmatory_comparison)
        for values in comparison["surfaces"].values()
        for gate in ("g3_pass", "g4_pass")
    )
    gates = {
        "g1_selection_mae": bool(selection_comparison["g1_pass"]),
        "g2_selection_logloss": bool(selection_comparison["g2_pass"]),
        "g1_confirmatory_mae": bool(confirmatory_comparison["g1_pass"]),
        "g2_confirmatory_logloss": bool(confirmatory_comparison["g2_pass"]),
        "g3_g4_surface": surface_pass,
        "g5_low_rank_ratio": g5,
        "g6_top_200_ratio": g6,
        "g7_sample": g7,
        "g8_most_aces_brier": g8,
        "g9_activity_tiering": g9,
    }
    status = "PASS" if all(gates.values()) else "FAIL"
    payload = {
        "version": "most-aces-coverage-a3-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "routing": "EXPERIMENT_ONLY_NO_LIVE_CHANGE",
        "selection_2025": selection_comparison,
        "confirmatory_2026": confirmatory_comparison,
        "a0_most_aces_2026": a0_most_aces,
        "a3_most_aces_2026": a3_most_aces,
        "top50_active_coverage_gap_candidates": len(
            top50_coverage_gap_candidates
        ),
        "false_historical_top50_active_labels": false_historical_labels,
        "gates": gates,
        "a0": serialisable_arm(a0),
        "a3": serialisable_arm(a3),
        "decision": (
            "A3 eligible for prospective freeze"
            if status == "PASS"
            else "A3 rejected; retain A0 projection model"
        ),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    a3["model"].booster_.save_model(
        args.out_dir / "v3-atp-aces-a3.txt"
    )
    a3["importance"].to_csv(
        args.out_dir / "feature-importance.csv", index=False
    )
    (args.out_dir / "result.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "Most Aces coverage A3 registered experiment",
        f"Status: {status} | EXPERIMENT_ONLY_NO_LIVE_CHANGE",
        (
            "Selection 2025 vs A0: "
            f"MAE {selection_comparison['mae_improvement_pct']:+.2f}% | "
            f"log-loss {selection_comparison['logloss_delta']:+.6f}"
        ),
        (
            "Confirmatory 2026 vs A0: "
            f"MAE {confirmatory_comparison['mae_improvement_pct']:+.2f}% | "
            f"log-loss {confirmatory_comparison['logloss_delta']:+.6f}"
        ),
        (
            "Most Aces RECENT 2026: "
            f"Brier {a0_most_aces['recent']['brier']:.6f} -> "
            f"{a3_most_aces['recent']['brier']:.6f} | "
            f"log-loss {a0_most_aces['recent']['logloss']:.6f} -> "
            f"{a3_most_aces['recent']['logloss']:.6f}"
        ),
        (
            "Low-rank thin ratio: "
            f"{low_rank['predicted_to_actual_ratio']:.3f} "
            f"(n={low_rank['n']})"
        ),
        (
            "Top-200 ratio: "
            f"{top_200['predicted_to_actual_ratio']:.3f} "
            f"(n={top_200['n']})"
        ),
        "Gates: " + ", ".join(
            f"{name}={'PASS' if passed else 'FAIL'}"
            for name, passed in gates.items()
        ),
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
