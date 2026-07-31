#!/usr/bin/env python3
"""Register paired control/candidate ace-line observations for venue-factor v1."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from tennis_props_model import negative_binomial_line_probabilities


ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"
DEFAULT_CONTROL = PROPS_DIR / "shadow" / "aces-v3-projection-board.csv"
DEFAULT_CANDIDATE = PROPS_DIR / "shadow" / "venue-ace-factor-v1-projection-board.csv"
DEFAULT_GATE = PROPS_DIR / "backtest" / "aces-dfs-v3-all-tour-gate.json"
DEFAULT_OBSERVATIONS = PROPS_DIR / "shadow" / "venue-ace-factor-v1-observations.csv"
CUSTOM_FIELDS = [
    "control_projection_mean",
    "candidate_projection_mean",
    "control_p_over_no_push",
    "candidate_p_over_no_push",
    "venue_v1_factor",
    "venue_v1_control_factor",
    "venue_v1_prior_svpt",
    "venue_v1_source_seasons",
    "venue_v1_model",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def number(value: object, fallback: float | None = None) -> float | None:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return fallback
    return parsed if math.isfinite(parsed) else fallback


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def board_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        str(row.get("date") or ""),
        str(row.get("tour") or "").upper(),
        norm(row.get("player")),
        norm(row.get("opponent")),
    )


def market_key(value: object) -> str:
    return str(value or "").lower().replace(" ", "_")


def no_push_probability(over: float, under: float) -> float | None:
    denominator = over + under
    return over / denominator if denominator > 0 else None


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def load_alpha(path: Path) -> float:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload["deployment_safe_aces"]["ATP"]["candidate_alpha"]
        alpha = float(value)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot load frozen ATP ace dispersion from {path}") from exc
    if alpha <= 0:
        raise RuntimeError(f"Invalid ATP ace dispersion in {path}: {alpha}")
    return alpha


def choose_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        if str(row.get("matched_board") or "").lower() != "yes":
            continue
        if market_key(row.get("market")) not in {"aces", "ace", "player_aces"}:
            continue
        key = (
            str(row.get("date") or ""),
            str(row.get("tour") or "").upper(),
            norm(row.get("player")),
            norm(row.get("opponent")),
            market_key(row.get("market")),
            str(row.get("event_id") or ""),
        )
        groups.setdefault(key, []).append(row)
    selected = []
    for candidates in groups.values():
        main = [row for row in candidates if str(row.get("main_line") or "").lower() == "true"]
        best = [row for row in candidates if str(row.get("best_available_line") or "").lower() == "true"]
        pool = main or best or candidates
        selected.append(pool[0])
    return selected


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--control-board", type=Path, default=DEFAULT_CONTROL)
    parser.add_argument("--candidate-board", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--observations", type=Path, default=DEFAULT_OBSERVATIONS)
    args = parser.parse_args()

    control = {board_key(row): row for row in read_csv(args.control_board)}
    candidate = {board_key(row): row for row in read_csv(args.candidate_board)}
    existing = read_csv(args.observations)
    existing_ids = {str(row.get("signal_id") or "") for row in existing}
    alpha = load_alpha(args.gate)
    added = 0
    for row in choose_rows(read_csv(args.comparison)):
        key = board_key(row)
        control_row = control.get(key)
        candidate_row = candidate.get(key)
        line = number(row.get("line"))
        control_mean = number((control_row or {}).get("projected_aces"))
        candidate_mean = number((candidate_row or {}).get("projected_aces"))
        if line is None or control_mean is None or candidate_mean is None:
            continue
        control_over, control_under, _ = negative_binomial_line_probabilities(line, control_mean, alpha)
        candidate_over = number(row.get("fair_p_over"))
        candidate_under = number(row.get("fair_p_under"))
        if candidate_over is None or candidate_under is None:
            continue
        signal_id = "|".join(
            [
                "venue-ace-factor-v1",
                str(row.get("date") or args.date),
                str(row.get("tour") or "").upper(),
                norm(row.get("player")),
                norm(row.get("opponent")),
                market_key(row.get("market")),
                str(row.get("line") or ""),
            ]
        )
        if signal_id in existing_ids:
            continue
        candidate_prob = no_push_probability(candidate_over, candidate_under)
        control_prob = no_push_probability(control_over, control_under)
        output = dict(row)
        output.update(
            {
                "signal_id": signal_id,
                "logged_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "scope": "player",
                "side": "OVER",
                "projection_mean": fmt(candidate_mean, 3),
                "selected_odds": str(row.get("over_odds") or ""),
                "fair_odds": str(row.get("fair_over_odds") or ""),
                "control_projection_mean": fmt(control_mean, 3),
                "candidate_projection_mean": fmt(candidate_mean, 3),
                "control_p_over_no_push": fmt(control_prob),
                "candidate_p_over_no_push": fmt(candidate_prob),
                "venue_v1_factor": str((candidate_row or {}).get("venue_v1_factor") or ""),
                "venue_v1_control_factor": str((candidate_row or {}).get("venue_v1_control_factor") or ""),
                "venue_v1_prior_svpt": str((candidate_row or {}).get("venue_v1_prior_svpt") or ""),
                "venue_v1_source_seasons": str((candidate_row or {}).get("venue_v1_source_seasons") or ""),
                "venue_v1_model": "venue-ace-factor-v1",
                "source_file": str(args.comparison),
                "settlement_status": "pending",
                "actual": "",
                "result": "",
                "pnl": "",
                "settled_at_utc": "",
                "settlement_note": "",
            }
        )
        existing.append(output)
        existing_ids.add(signal_id)
        added += 1
    write_csv(args.observations, existing)
    print(f"Venue ace factor v1 paired observations: added {added}, total {len(existing)} -> {args.observations}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
