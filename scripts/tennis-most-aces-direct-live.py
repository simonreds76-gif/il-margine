#!/usr/bin/env python3
"""Build the frozen direct Most Aces 1X2 prospective shadow board."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from tennis_props_names import norm_name


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PROPS = ROOT / "data" / "tennis-props"
ONCOURT = ROOT / "data" / "oncourt"
DEFAULT_SIDE_BOARD = PROPS / "shadow" / "aces-v3-projection-board.csv"
DEFAULT_A0_BOARD = PROPS / "shadow" / "most-aces-1x2-board.csv"
DEFAULT_BASELINE = PROPS / "player-props-baseline.csv"
DEFAULT_LEVEL_FACTORS = (
    PROPS / "experiments" / "most-aces-coverage-a1" / "level-factors.json"
)
DEFAULT_MODEL_DIR = PROPS / "experiments" / "most-aces-direct-1x2"
DEFAULT_OUT = PROPS / "shadow" / "most-aces-direct-1x2-board.csv"
DEFAULT_REPORT = PROPS / "shadow" / "most-aces-direct-1x2-live-parity.json"
MODEL_NAME = "most_aces_direct_1x2_v1"
VISIBLE_QUOTE_STATUSES = {
    "READY",
    "HISTORICAL_ESTIMATE",
    "COVERAGE_GAP_ESTIMATE",
}
FIELDS = [
    "generated_at_utc",
    "feature_as_of",
    "date",
    "tour",
    "tournament",
    "round",
    "surface",
    "player1",
    "player2",
    "player1_mean",
    "player2_mean",
    "p_player1",
    "p_draw",
    "p_player2",
    "fair_player1",
    "fair_draw",
    "fair_player2",
    "a0_p_player1",
    "a0_p_draw",
    "a0_p_player2",
    "probability_l1_delta",
    "quote_status",
    "quote_reason",
    "predicted_outcome",
    "player1_rank",
    "player2_rank",
    "player1_rank_source",
    "player2_rank_source",
    "player1_id",
    "player2_id",
    "evidence_tier",
    "live_parity_status",
    "live_feature_count",
    "model",
    "scope",
    "notes",
]


def load_module(name: str, filename: str):
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def number(value: object, default: float = 0.0) -> float:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def integer(value: object, default: int = 0) -> int:
    try:
        text = str(value or "").strip()
        return int(float(text)) if text else default
    except (TypeError, ValueError):
        return default


def parse_iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def age_on(birthdate: object, as_of: date) -> float | None:
    born = parse_iso_date(birthdate)
    if born is None or born >= as_of:
        return None
    return (as_of - born).days / 365.2425


def baseline_id_index(rows: list[dict[str, str]]) -> dict[str, str]:
    output: dict[str, str] = {}
    for row in rows:
        if str(row.get("tour") or "").upper() != "ATP":
            continue
        name = norm_name(row.get("player_name"))
        player_id = str(row.get("player_id") or "").strip()
        if name and player_id:
            output.setdefault(name, player_id)
    return output


def oncourt_player_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        name = norm_name(row.get("name"))
        if not name or "/" in str(row.get("name") or ""):
            continue
        incumbent = output.get(name)
        rank = integer(row.get("atp_rank"), 999)
        if incumbent is None or rank < integer(incumbent.get("atp_rank"), 999):
            output[name] = row
    return output


def latest_metadata(
    matches: list[dict[str, str]],
    as_of: date,
) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    cutoff = as_of.isoformat()
    for row in matches:
        if str(row.get("_date") or "") >= cutoff:
            continue
        for prefix, id_field, name_field in (
            ("winner", "winner_id", "winner_name"),
            ("loser", "loser_id", "loser_name"),
        ):
            player_id = str(row.get(id_field) or "").strip()
            if not player_id:
                continue
            rank = integer(row.get(f"{prefix}_rank"), 999)
            age = number(row.get(f"{prefix}_age"), 0.0)
            height = number(row.get(f"{prefix}_ht"), 0.0)
            hand = str(row.get(f"{prefix}_hand") or "U")
            prior = output.get(player_id, {})
            output[player_id] = {
                "date": str(row.get("_date") or ""),
                "name": str(row.get(name_field) or prior.get("name") or ""),
                "rank": rank if 0 < rank < 999 else prior.get("rank", 999),
                "age": age if age > 0 else prior.get("age", 26.0),
                "height": height if height > 0 else prior.get("height", 0.0),
                "hand": hand if hand and hand != "U" else prior.get("hand", "U"),
            }
    return output


def current_metadata(
    *,
    player_name: str,
    sackmann_id: str,
    as_of: date,
    oncourt_players: dict[str, dict[str, str]],
    latest: dict[str, dict[str, object]],
) -> dict[str, object]:
    oncourt = oncourt_players.get(norm_name(player_name), {})
    historical = latest.get(sackmann_id, {})
    current_rank = integer(oncourt.get("atp_rank"), 999)
    if 0 < current_rank < 999:
        rank = current_rank
        rank_source = "oncourt_current"
    else:
        rank = integer(historical.get("rank"), 999)
        rank_source = "sackmann_latest" if rank < 999 else "registered_missing"
    age = age_on(oncourt.get("birthdate"), as_of)
    if age is None:
        historical_age = number(historical.get("age"), 26.0)
        historical_date = parse_iso_date(historical.get("date"))
        age = (
            historical_age + (as_of - historical_date).days / 365.2425
            if historical_date is not None
            else historical_age
        )
    return {
        "rank": rank,
        "rank_source": rank_source,
        "age": age,
        "height": number(historical.get("height"), 0.0),
        "hand": str(historical.get("hand") or "U"),
    }


def tour_level(tour_id: str, tournament: str, tours: dict[str, dict[str, str]]) -> str:
    name = tournament.casefold()
    if tournament in {"Australian Open", "Roland Garros", "Wimbledon", "US Open"}:
        return "G"
    if "finals" in name and "next gen" not in name:
        return "F"
    rank = integer((tours.get(tour_id) or {}).get("rank"), 2)
    return "M" if rank == 3 else "G" if rank == 4 else "A"


def side_index(rows: list[dict[str, str]]) -> dict[tuple[str, ...], dict[str, str]]:
    return {
        (
            str(row.get("date") or ""),
            str(row.get("tournament") or ""),
            str(row.get("round") or ""),
            norm_name(row.get("player")),
            norm_name(row.get("opponent")),
        ): row
        for row in rows
    }


def feature_side(
    *,
    v3,
    state: dict[str, object],
    as_of: date,
    forecast: dict[str, str],
    side: dict[str, str],
    opponent_side: dict[str, str],
    sackmann_ids: dict[str, str],
    oncourt_players: dict[str, dict[str, str]],
    latest: dict[str, dict[str, object]],
    tours: dict[str, dict[str, str]],
) -> tuple[pd.Series, dict[str, object]]:
    player_name = str(side.get("player") or "")
    opponent_name = str(side.get("opponent") or "")
    player_baseline = str(side.get("player_baseline_name") or player_name)
    opponent_baseline = str(side.get("opponent_baseline_name") or opponent_name)
    player_id = sackmann_ids.get(norm_name(player_baseline), "")
    opponent_id = sackmann_ids.get(norm_name(opponent_baseline), "")
    if not player_id or not opponent_id:
        missing = player_name if not player_id else opponent_name
        raise ValueError(f"Sackmann player ID missing: {missing}")
    player_meta = current_metadata(
        player_name=player_name,
        sackmann_id=player_id,
        as_of=as_of,
        oncourt_players=oncourt_players,
        latest=latest,
    )
    opponent_meta = current_metadata(
        player_name=opponent_name,
        sackmann_id=opponent_id,
        as_of=as_of,
        oncourt_players=oncourt_players,
        latest=latest,
    )
    tour_id = str(side.get("tour_id") or opponent_side.get("tour_id") or "")
    level = tour_level(tour_id, str(forecast.get("tournament") or ""), tours)
    best_of = 5 if level == "G" else 3
    synthetic = {
        "_tour": "ATP",
        "_date": as_of.isoformat(),
        "_surface": str(forecast.get("surface") or ""),
        "tourney_name": str(forecast.get("tournament") or ""),
        "tourney_level": level,
        "round": str(forecast.get("round") or ""),
        "best_of": str(best_of),
        "draw_size": "0",
        "winner_id": player_id,
        "loser_id": opponent_id,
        "winner_name": player_name,
        "loser_name": opponent_name,
        "winner_rank": str(player_meta["rank"]),
        "loser_rank": str(opponent_meta["rank"]),
        "winner_age": str(player_meta["age"]),
        "loser_age": str(opponent_meta["age"]),
        "winner_ht": str(player_meta["height"]),
        "loser_ht": str(opponent_meta["height"]),
        "winner_hand": str(player_meta["hand"]),
        "loser_hand": str(opponent_meta["hand"]),
    }
    rendered = v3.side_row(
        synthetic,
        prefix="w",
        opponent_prefix="l",
        player_id_field="winner_id",
        opponent_id_field="loser_id",
        player_name_field="winner_name",
        opponent_name_field="loser_name",
        player_rank_field="winner_rank",
        opponent_rank_field="loser_rank",
        player_age_field="winner_age",
        opponent_age_field="loser_age",
        player_height_field="winner_ht",
        opponent_height_field="loser_ht",
        player_hand_field="winner_hand",
        opponent_hand_field="loser_hand",
        **state,
        include_a3_features=True,
    )
    return pd.Series(rendered), {
        "player_id": player_id,
        "rank": player_meta["rank"],
        "rank_source": player_meta["rank_source"],
    }


def temperature_scale(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probabilities, 1e-12, 1.0)) / temperature
    logits -= logits.max(axis=1, keepdims=True)
    exponent = np.exp(logits)
    return exponent / exponent.sum(axis=1, keepdims=True)


def mirror_features(frame: pd.DataFrame) -> pd.DataFrame:
    mirrored = frame.copy()
    for column in mirrored.columns:
        if column.endswith("_diff"):
            mirrored[column] = -pd.to_numeric(
                mirrored[column], errors="coerce"
            ).fillna(0.0)
    return mirrored


def predict(
    booster: lgb.Booster,
    pair_row: dict[str, object],
    temperature: float,
) -> tuple[np.ndarray, float]:
    features = booster.feature_name()
    frame = pd.DataFrame([pair_row])
    missing = [field for field in features if field not in frame.columns]
    if missing:
        raise RuntimeError(f"Direct live features missing: {', '.join(missing)}")
    frame = frame[features]
    categories = (booster.pandas_categorical or [["Clay", "Hard"]])[0]
    frame["surface"] = pd.Categorical(frame["surface"], categories=categories)
    canonical = np.asarray(booster.predict(frame), dtype=float)
    reversed_raw = np.asarray(booster.predict(mirror_features(frame)), dtype=float)
    reversed_mapped = reversed_raw[:, [2, 1, 0]]
    symmetry_gap = float(np.mean(np.abs(canonical - reversed_mapped)))
    averaged = (canonical + reversed_mapped) * 0.5
    return temperature_scale(averaged, temperature)[0], symmetry_gap


def fair(probability: float, visible: bool) -> str:
    return f"{1.0 / probability:.3f}" if visible and probability > 0 else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--side-board", type=Path, default=DEFAULT_SIDE_BOARD)
    parser.add_argument("--a0-board", type=Path, default=DEFAULT_A0_BOARD)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--level-factors", type=Path, default=DEFAULT_LEVEL_FACTORS)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of)
    validation = read_json(args.model_dir / "result.json")
    if str(validation.get("status") or "").upper() != "PASS":
        raise SystemExit("Direct Most Aces retrospective gate is not PASS")
    model_path = args.model_dir / "direct-1x2-model.txt"
    if not model_path.exists():
        raise SystemExit(f"Direct Most Aces model missing: {model_path}")

    v3 = load_module("tennis_props_v3_direct_live", "build-tennis-props-v3-dataset.py")
    direct_data = load_module(
        "tennis_most_aces_direct_dataset_live",
        "build-tennis-most-aces-direct-dataset.py",
    )
    level_factors = v3.load_level_factors(args.level_factors)
    matches = v3.load_matches(
        args.start_year,
        as_of.year,
        include_qual_chall=True,
        level_factors=level_factors,
    )
    state = v3.build_feature_state(matches, as_of=as_of)
    latest = latest_metadata(matches, as_of)
    sackmann_ids = baseline_id_index(read_csv(args.baseline))
    oncourt_players = oncourt_player_index(read_csv(ONCOURT / "players_atp.csv"))
    tours = {
        str(row.get("id") or ""): row
        for row in read_csv(ONCOURT / "tours_atp.csv")
    }
    sides = side_index(read_csv(args.side_board))
    booster = lgb.Booster(model_file=str(model_path))
    temperature = number(validation.get("temperature"), 1.0)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    rank_sources: dict[str, int] = {}
    symmetry_gaps: list[float] = []

    for forecast in read_csv(args.a0_board):
        event_date = parse_iso_date(forecast.get("date"))
        if (
            str(forecast.get("tour") or "").upper() != "ATP"
            or str(forecast.get("surface") or "") not in {"Hard", "Clay"}
            or event_date is None
            or event_date < as_of
        ):
            continue
        side_key1 = (
            str(forecast.get("date") or ""),
            str(forecast.get("tournament") or ""),
            str(forecast.get("round") or ""),
            norm_name(forecast.get("player1")),
            norm_name(forecast.get("player2")),
        )
        side_key2 = (
            str(forecast.get("date") or ""),
            str(forecast.get("tournament") or ""),
            str(forecast.get("round") or ""),
            norm_name(forecast.get("player2")),
            norm_name(forecast.get("player1")),
        )
        left = sides.get(side_key1)
        right = sides.get(side_key2)
        if left is None or right is None:
            blocked.append({
                "fixture": f"{forecast.get('player1')} vs {forecast.get('player2')}",
                "reason": "reciprocal_side_rows_missing",
            })
            continue
        try:
            left_features, left_meta = feature_side(
                v3=v3,
                state=state,
                as_of=as_of,
                forecast=forecast,
                side=left,
                opponent_side=right,
                sackmann_ids=sackmann_ids,
                oncourt_players=oncourt_players,
                latest=latest,
                tours=tours,
            )
            right_features, right_meta = feature_side(
                v3=v3,
                state=state,
                as_of=as_of,
                forecast=forecast,
                side=right,
                opponent_side=left,
                sackmann_ids=sackmann_ids,
                oncourt_players=oncourt_players,
                latest=latest,
                tours=tours,
            )
            pair = direct_data.pairwise_feature_row(
                left_features,
                right_features,
                include_target=False,
            )
            probabilities, symmetry_gap = predict(booster, pair, temperature)
        except (KeyError, RuntimeError, ValueError) as exc:
            blocked.append({
                "fixture": f"{forecast.get('player1')} vs {forecast.get('player2')}",
                "reason": str(exc),
            })
            continue

        symmetry_gaps.append(symmetry_gap)
        for meta in (left_meta, right_meta):
            source = str(meta["rank_source"])
            rank_sources[source] = rank_sources.get(source, 0) + 1
        p1, draw, p2 = (float(value) for value in probabilities)
        a0 = np.asarray([
            number(forecast.get("p_player1")),
            number(forecast.get("p_draw")),
            number(forecast.get("p_player2")),
        ])
        quote_status = str(forecast.get("quote_status") or "")
        visible = quote_status in VISIBLE_QUOTE_STATUSES
        predicted = ("P1", "DRAW", "P2")[int(np.argmax(probabilities))]
        output.append({
            "generated_at_utc": generated,
            "feature_as_of": as_of.isoformat(),
            "date": str(forecast.get("date") or ""),
            "tour": "ATP",
            "tournament": str(forecast.get("tournament") or ""),
            "round": str(forecast.get("round") or ""),
            "surface": str(forecast.get("surface") or ""),
            "player1": str(forecast.get("player1") or ""),
            "player2": str(forecast.get("player2") or ""),
            "player1_mean": "",
            "player2_mean": "",
            "p_player1": f"{p1:.6f}",
            "p_draw": f"{draw:.6f}",
            "p_player2": f"{p2:.6f}",
            "fair_player1": fair(p1, visible),
            "fair_draw": fair(draw, visible),
            "fair_player2": fair(p2, visible),
            "a0_p_player1": f"{a0[0]:.6f}",
            "a0_p_draw": f"{a0[1]:.6f}",
            "a0_p_player2": f"{a0[2]:.6f}",
            "probability_l1_delta": f"{float(np.abs(probabilities - a0).sum()):.6f}",
            "quote_status": quote_status,
            "quote_reason": str(forecast.get("quote_reason") or ""),
            "predicted_outcome": predicted,
            "player1_rank": str(left_meta["rank"]),
            "player2_rank": str(right_meta["rank"]),
            "player1_rank_source": str(left_meta["rank_source"]),
            "player2_rank_source": str(right_meta["rank_source"]),
            "player1_id": str(left_meta["player_id"]),
            "player2_id": str(right_meta["player_id"]),
            "evidence_tier": str(pair.get("evidence_tier") or ""),
            "live_parity_status": "EXACT_REGISTERED_FEATURES",
            "live_feature_count": str(len(booster.feature_name())),
            "model": MODEL_NAME,
            "scope": "ATP_HARD_CLAY_PROSPECTIVE_SHADOW",
            "notes": (
                "DIRECT_1X2_PROSPECTIVE_SHADOW|"
                "OUTCOME_ONLY_NO_PRICE_NO_ROI_NO_CLV"
            ),
        })

    write_csv(args.out, output)
    report = {
        "generated_at_utc": generated,
        "feature_as_of": as_of.isoformat(),
        "model": MODEL_NAME,
        "status": "ACTIVE" if output else "BLOCKED",
        "routing": "PROSPECTIVE_SHADOW_ONLY",
        "input_rows": len(read_csv(args.a0_board)),
        "scored_rows": len(output),
        "blocked_rows": len(blocked),
        "blocked": blocked,
        "rank_sources": rank_sources,
        "feature_count": len(booster.feature_name()),
        "mean_symmetry_gap": (
            sum(symmetry_gaps) / len(symmetry_gaps)
            if symmetry_gaps
            else None
        ),
        "notes": [
            "The live scorer uses the same causal state and pair algebra as the frozen retrospective model.",
            "No betting, public routing, ROI or CLV claim is enabled.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "Direct Most Aces live shadow: "
        f"scored={len(output)}, blocked={len(blocked)} -> {args.out}"
    )
    return 0 if output else 2


if __name__ == "__main__":
    raise SystemExit(main())
