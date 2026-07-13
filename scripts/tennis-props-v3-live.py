#!/usr/bin/env python3
"""Build the deployment-safe ATP ace challenger board for prospective shadow."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from pathlib import Path

import lightgbm as lgb
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"
DEFAULT_BOARD = PROPS_DIR / "player-props-board.csv"
DEFAULT_BASELINE = PROPS_DIR / "player-props-baseline.csv"
DEFAULT_SURFACE_BASELINES = PROPS_DIR / "tour-surface-baselines.csv"
DEFAULT_GATE = PROPS_DIR / "backtest" / "aces-dfs-v3-all-tour-gate.json"
DEFAULT_OUT = PROPS_DIR / "shadow" / "aces-v3-projection-board.csv"
WINDOWS = ("L12M", "L24M", "career_4y")
WINDOW_WEIGHTS = {"L12M": 1.0, "L24M": 0.55, "career_4y": 0.25}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def norm_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def number(value: object, fallback: float = 0.0) -> float:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return fallback
    return parsed if math.isfinite(parsed) else fallback


def baseline_index(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, dict[str, str]]]:
    index: dict[tuple[str, str, str], dict[str, dict[str, str]]] = {}
    for row in rows:
        key = (
            str(row.get("tour") or "").upper(),
            norm_name(row.get("player_name")),
            str(row.get("surface") or ""),
        )
        index.setdefault(key, {})[str(row.get("window") or "")] = row
    return index


def surface_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (str(row.get("tour") or "").upper(), str(row.get("surface") or "")): row
        for row in rows
        if str(row.get("year") or "") == "ALL"
    }


def blended_value(
    rows: dict[str, dict[str, str]],
    value_field: str,
    sample_field: str,
    prior: float,
    prior_weight: float,
) -> float:
    numerator = prior * prior_weight
    denominator = prior_weight
    for window in WINDOWS:
        row = rows.get(window) or {}
        sample = number(row.get(sample_field))
        value = number(row.get(value_field), prior)
        weight = WINDOW_WEIGHTS[window]
        if sample > 0:
            numerator += value * sample * weight
            denominator += sample * weight
    return numerator / denominator if denominator > 0 else prior


def side_features(
    rows: dict[str, dict[str, str]],
    *,
    tour: str,
    prior_ace: float,
    prior_df: float,
    prior_ret_first: float,
    prior_ret_second: float,
) -> dict[str, float]:
    result = {
        "ace_rate_blend": blended_value(rows, "ace_rate", "svpt", prior_ace, 400.0 if tour == "ATP" else 600.0),
        "df_rate_blend": blended_value(rows, "df_rate", "svpt", prior_df, 600.0 if tour == "ATP" else 800.0),
        "ret_first_blend": blended_value(rows, "ret_first_win_pct", "ret_first_points", prior_ret_first, 350.0),
        "ret_second_blend": blended_value(rows, "ret_second_win_pct", "ret_second_points", prior_ret_second, 350.0),
        "aces_allowed_blend": blended_value(rows, "aces_allowed_rate", "opponent_svpt", prior_ace, 400.0),
        "svpt_per_svg_blend": blended_value(rows, "svpt_per_svgame", "svgms", 6.35, 60.0),
    }
    for window, prefix in (("L12M", "l12m"), ("L24M", "l24m"), ("career_4y", "career4y")):
        row = rows.get(window) or {}
        matches = number(row.get("matches"))
        svpt = number(row.get("svpt"))
        result.update({
            f"{prefix}_matches": matches,
            f"{prefix}_svpt": svpt,
            f"{prefix}_ace_rate": number(row.get("ace_rate"), prior_ace),
            f"{prefix}_df_rate": number(row.get("df_rate"), prior_df),
            f"{prefix}_svpt_per_match": svpt / matches if matches > 0 else 65.0,
            f"{prefix}_first_serve_pct": number(row.get("first_serve_pct"), 0.61),
            f"{prefix}_first_win_pct": number(row.get("first_serve_win_pct"), 0.70),
            f"{prefix}_second_win_pct": number(row.get("second_serve_win_pct"), 0.52),
            f"{prefix}_aces_allowed_rate": number(row.get("aces_allowed_rate"), prior_ace),
        })
    return result


def build_feature_row(
    row: dict[str, str],
    baselines: dict[tuple[str, str, str], dict[str, dict[str, str]]],
    surfaces: dict[tuple[str, str], dict[str, str]],
) -> dict[str, object]:
    tour = str(row.get("tour") or "").upper()
    surface = str(row.get("surface") or "")
    surface_row = surfaces.get((tour, surface), {})
    prior_ace = number(surface_row.get("ace_rate"), 0.065 if tour == "ATP" else 0.027)
    prior_df = number(surface_row.get("df_rate"), 0.035 if tour == "ATP" else 0.048)
    prior_ret_first = 0.315 if tour == "ATP" else 0.365
    prior_ret_second = 0.520 if tour == "ATP" else 0.550
    player_rows = baselines.get((tour, norm_name(row.get("player")), surface), {})
    opponent_rows = baselines.get((tour, norm_name(row.get("opponent")), surface), {})
    player = side_features(
        player_rows, tour=tour, prior_ace=prior_ace, prior_df=prior_df,
        prior_ret_first=prior_ret_first, prior_ret_second=prior_ret_second,
    )
    opponent = side_features(
        opponent_rows, tour=tour, prior_ace=prior_ace, prior_df=prior_df,
        prior_ret_first=prior_ret_first, prior_ret_second=prior_ret_second,
    )
    tournament = str(row.get("tournament") or "")
    best_of = 5 if tour == "ATP" and tournament in {"Australian Open", "Roland Garros", "Wimbledon", "US Open"} else 3
    features: dict[str, object] = {
        "surface": surface,
        "best_of": best_of,
        "surface_prior_ace_rate": prior_ace,
        "surface_prior_df_rate": prior_df,
        "venue_ace_factor": number(row.get("venue_ace_factor"), 1.0),
        "venue_df_factor": number(row.get("venue_df_factor"), 1.0),
        "expected_match_games": number(row.get("expected_match_games"), 21.5),
        "expected_service_points": number(row.get("service_points_estimate"), 65.0),
        "opponent_return_factor": max(0.76, min(1.22, (prior_ret_first / max(0.18, opponent["ret_first_blend"])) ** 0.6)),
        "incumbent_aces": number(row.get("projected_aces"), 0.01),
        "incumbent_dfs": number(row.get("projected_dfs"), 0.01),
    }
    features.update({f"player_{key}": value for key, value in player.items()})
    features.update({f"opponent_{key}": value for key, value in opponent.items()})
    return features


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--surface-baselines", type=Path, default=DEFAULT_SURFACE_BASELINES)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    gate = read_json(args.gate)
    deployment = gate.get("deployment_safe_aces")
    atp_gate = deployment.get("ATP") if isinstance(deployment, dict) else None
    if not isinstance(atp_gate, dict) or atp_gate.get("passed") is not True:
        print("ATP v3 live gate is blocked; no prospective board written.")
        return 0
    model_path = ROOT / str(atp_gate.get("model_path") or "")
    if not model_path.exists():
        print(f"ATP v3 live model missing: {model_path}")
        return 0

    board_rows = read_csv(args.board)
    if not board_rows:
        print(f"Projection board has no rows; keeping the last v3 board: {args.board}")
        return 0
    booster = lgb.Booster(model_file=str(model_path))
    baselines = baseline_index(read_csv(args.baseline))
    surfaces = surface_index(read_csv(args.surface_baselines))
    output: list[dict[str, str]] = []
    for row in board_rows:
        if str(row.get("tour") or "").upper() != "ATP" or str(row.get("surface") or "") not in {"Hard", "Clay"}:
            continue
        feature_row = build_feature_row(row, baselines, surfaces)
        feature_frame = pd.DataFrame([feature_row])
        missing = [name for name in booster.feature_name() if name not in feature_frame.columns]
        if missing:
            raise RuntimeError(f"Missing v3 live features: {', '.join(missing)}")
        feature_frame = feature_frame[booster.feature_name()]
        categories = (booster.pandas_categorical or [["Clay", "Grass", "Hard"]])[0]
        feature_frame["surface"] = pd.Categorical(feature_frame["surface"], categories=categories)
        candidate = max(0.01, float(booster.predict(feature_frame)[0]))
        incumbent = number(row.get("projected_aces"), 0.01)
        out_row = dict(row)
        out_row.update({
            "incumbent_projected_aces": f"{incumbent:.3f}",
            "projected_aces": f"{candidate:.3f}",
            "v3_ace_delta": f"{candidate - incumbent:+.3f}",
            "aces_alpha": f"{number(atp_gate.get('candidate_alpha')):.6f}",
            "v3_eligible": "true",
            "v3_model": "all_tour_deployment_safe_atp_aces_v1",
            "notes": "|".join(part for part in (row.get("notes", ""), "V3_ATP_ACES_PROSPECTIVE_SHADOW") if part),
        })
        output.append(out_row)

    if not output:
        print("Projection board has no eligible ATP Hard/Clay rows; keeping the last v3 board.")
        return 0
    original_fields = list(board_rows[0])
    extra_fields = ["incumbent_projected_aces", "v3_ace_delta", "aces_alpha", "v3_eligible", "v3_model"]
    write_csv(args.out, output, original_fields + [field for field in extra_fields if field not in original_fields])
    print(f"V3 ATP ace prospective board: {len(output)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
