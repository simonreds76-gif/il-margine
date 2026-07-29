#!/usr/bin/env python3
"""Register and score price-independent Most Aces 1X2 forecasts.

This ledger measures forecast quality from actual ace counts even when BetMGM
does not expose the Stat Bets market through the configured odds feed. It does
not calculate ROI, value, or CLV.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, date, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

from tennis_most_aces import norm_name, pair_key, result_from_counts


ROOT = Path(__file__).resolve().parents[1]
PROPS = ROOT / "data" / "tennis-props"
DEFAULT_BOARD = PROPS / "shadow" / "most-aces-1x2-board.csv"
DEFAULT_LEDGER = PROPS / "shadow" / "most-aces-1x2-forecasts.csv"
DEFAULT_REPORT = PROPS / "shadow" / "most-aces-1x2-forecast-report.txt"
DEFAULT_JSON = PROPS / "shadow" / "most-aces-1x2-forecast-report.json"
DEFAULT_SACKMANN = ROOT / "data" / "sackmann"
DEFAULT_ONCOURT = ROOT / "data" / "oncourt"
FIELDS = [
    "forecast_id", "registered_at_utc", "date", "tour", "tournament", "round",
    "surface", "player1", "player2", "player1_mean", "player2_mean", "rho",
    "p_player1", "p_draw", "p_player2", "fair_player1", "fair_draw",
    "fair_player2", "predicted_outcome", "settlement_status",
    "actual_player1_aces", "actual_player2_aces", "actual_outcome",
    "prediction_correct", "model_brier", "model_logloss", "player1_abs_error",
    "player2_abs_error", "settled_at_utc", "settlement_source",
    "settlement_note", "model", "notes",
]


def load_settlement_module():
    path = ROOT / "scripts" / "tennis-props-settle-shadow.py"
    spec = importlib.util.spec_from_file_location("most_aces_forecast_settlement", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import settlement helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SETTLE = load_settlement_module()


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
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def number(value: object) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def forecast_id(row: dict[str, str]) -> str:
    payload = "|".join(
        [
            str(row.get("date") or ""),
            str(row.get("tour") or "").upper(),
            SETTLE.norm_text(row.get("tournament")),
            str(row.get("round") or "").upper(),
            *pair_key(row.get("player1"), row.get("player2")),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def predicted_outcome(row: dict[str, str]) -> str:
    probabilities = {
        "P1": number(row.get("p_player1")) or 0.0,
        "DRAW": number(row.get("p_draw")) or 0.0,
        "P2": number(row.get("p_player2")) or 0.0,
    }
    return max(probabilities, key=probabilities.get)


def register(board_rows: list[dict[str, str]], ledger: list[dict[str, str]]) -> int:
    known = {row.get("forecast_id", "") for row in ledger}
    now = datetime.now(UTC).isoformat(timespec="seconds")
    added = 0
    for board in board_rows:
        row_id = forecast_id(board)
        if not row_id or row_id in known:
            continue
        row = {field: str(board.get(field) or "") for field in FIELDS}
        row.update(
            {
                "forecast_id": row_id,
                "registered_at_utc": now,
                "predicted_outcome": predicted_outcome(board),
                "settlement_status": "pending",
                "notes": "OUTCOME_ONLY_NO_PRICE_NO_ROI_NO_CLV",
            }
        )
        ledger.append(row)
        known.add(row_id)
        added += 1
    return added


def signal_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "date": row.get("date", ""),
        "tour": row.get("tour", ""),
        "tournament": row.get("tournament", ""),
        "player": row.get("player1", ""),
        "opponent": row.get("player2", ""),
    }


def settle(
    ledger: list[dict[str, str]],
    sackmann_dir: Path,
    oncourt_dir: Path,
) -> int:
    signals = [signal_row(row) for row in ledger if row.get("settlement_status") == "pending"]
    sackmann = SETTLE.load_sackmann_index(sackmann_dir)
    oncourt = SETTLE.load_oncourt_index(oncourt_dir, signals)
    now = datetime.now(UTC)
    settled = 0
    for row in ledger:
        if row.get("settlement_status") != "pending":
            continue
        try:
            target_date = date.fromisoformat(row["date"])
        except (KeyError, ValueError):
            row["settlement_note"] = "invalid_date"
            continue
        if target_date > now.date():
            row["settlement_note"] = "match_not_started"
            continue
        key = (
            (row.get("tour") or "").upper(),
            target_date.year,
            pair_key(row.get("player1"), row.get("player2")),
        )
        candidates = oncourt.get(key, []) or sackmann.get(key, [])
        match = SETTLE.choose_candidate(signal_row(row), candidates)
        if not match:
            row["settlement_note"] = "result_not_found"
            continue
        score = str(match.get("score") or "").upper()
        if any(token in score for token in ("RET", "W/O", "WO", "DEF", "ABD")):
            row.update(
                {
                    "settlement_status": "void",
                    "settled_at_utc": now.isoformat(timespec="seconds"),
                    "settlement_source": match.get("_settlement_source", "sackmann"),
                    "settlement_note": f"void_score:{score}",
                }
            )
            settled += 1
            continue
        winner = norm_name(match.get("winner_name"))
        try:
            winner_aces = int(round(float(match["w_ace"])))
            loser_aces = int(round(float(match["l_ace"])))
        except (KeyError, TypeError, ValueError):
            row["settlement_note"] = "missing_ace_stats"
            continue
        if norm_name(row.get("player1")) == winner:
            actual1, actual2 = winner_aces, loser_aces
        else:
            actual1, actual2 = loser_aces, winner_aces
        outcome = result_from_counts(actual1, actual2)
        probabilities = [
            number(row.get("p_player1")) or 0.0,
            number(row.get("p_draw")) or 0.0,
            number(row.get("p_player2")) or 0.0,
        ]
        outcome_index = {"P1": 0, "DRAW": 1, "P2": 2}[outcome]
        brier = sum(
            (probability - (1.0 if index == outcome_index else 0.0)) ** 2
            for index, probability in enumerate(probabilities)
        )
        row.update(
            {
                "settlement_status": "settled",
                "actual_player1_aces": str(actual1),
                "actual_player2_aces": str(actual2),
                "actual_outcome": outcome,
                "prediction_correct": "yes" if row.get("predicted_outcome") == outcome else "no",
                "model_brier": f"{brier:.6f}",
                "model_logloss": f"{-math.log(max(probabilities[outcome_index], 1e-12)):.6f}",
                "player1_abs_error": f"{abs(actual1 - (number(row.get('player1_mean')) or 0.0)):.3f}",
                "player2_abs_error": f"{abs(actual2 - (number(row.get('player2_mean')) or 0.0)):.3f}",
                "settled_at_utc": now.isoformat(timespec="seconds"),
                "settlement_source": match.get("_settlement_source", "sackmann"),
                "settlement_note": f"{match.get('tourney_name', '')}:{score}",
            }
        )
        settled += 1
    return settled


def mean(rows: list[dict[str, str]], field: str) -> float | None:
    values = [number(row.get(field)) for row in rows]
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def report_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    settled_rows = [row for row in rows if row.get("settlement_status") == "settled"]
    pending = [row for row in rows if row.get("settlement_status") == "pending"]
    predicted_draw = sum(row.get("predicted_outcome") == "DRAW" for row in settled_rows)
    actual_draw = sum(row.get("actual_outcome") == "DRAW" for row in settled_rows)
    correct = sum(row.get("prediction_correct") == "yes" for row in settled_rows)
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "REVIEW_READY" if len(settled_rows) >= 200 else "EVIDENCE_BUILDING",
        "rows_registered": len(rows),
        "rows_settled": len(settled_rows),
        "rows_pending": len(pending),
        "rows_void": sum(row.get("settlement_status") == "void" for row in rows),
        "accuracy_pct": (100.0 * correct / len(settled_rows)) if settled_rows else None,
        "brier": mean(settled_rows, "model_brier"),
        "logloss": mean(settled_rows, "model_logloss"),
        "player_count_mae": mean(
            [
                {"value": value}
                for row in settled_rows
                for value in (row.get("player1_abs_error"), row.get("player2_abs_error"))
            ],
            "value",
        ),
        "predicted_draw_rate_pct": (100.0 * predicted_draw / len(settled_rows)) if settled_rows else None,
        "actual_draw_rate_pct": (100.0 * actual_draw / len(settled_rows)) if settled_rows else None,
        "minimum_review_sample": 200,
        "can_claim_profitability": False,
        "notes": [
            "Outcome-only validation; no bookmaker prices, ROI, value or CLV.",
            "Parameters remain frozen until a registered review at 200 settled forecasts.",
        ],
    }


def write_report(path: Path, json_path: Path, payload: dict[str, Any]) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    def metric(name: str, digits: int = 3) -> str:
        value = payload.get(name)
        return "-" if value is None else f"{float(value):.{digits}f}"
    lines = [
        "Most Aces 1X2 outcome forecast evidence",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']}",
        (
            f"Rows: {payload['rows_registered']} | settled: {payload['rows_settled']} | "
            f"pending: {payload['rows_pending']} | void: {payload['rows_void']}"
        ),
        f"Three-way accuracy: {metric('accuracy_pct', 1)}%",
        f"Brier: {metric('brier', 4)} | log loss: {metric('logloss', 4)}",
        f"Player ace-count MAE: {metric('player_count_mae', 3)}",
        (
            f"Draw rate: predicted {metric('predicted_draw_rate_pct', 1)}% | "
            f"actual {metric('actual_draw_rate_pct', 1)}%"
        ),
        "No profitability claim: prices, value, ROI and CLV are unavailable.",
        "Review gate: 200 settled prospective forecasts; no automatic parameter changes.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", default=str(DEFAULT_BOARD))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--sackmann-dir", default=str(DEFAULT_SACKMANN))
    parser.add_argument("--oncourt-dir", default=str(DEFAULT_ONCOURT))
    args = parser.parse_args()
    ledger = read_csv(Path(args.ledger))
    added = register(read_csv(Path(args.board)), ledger)
    settled_now = settle(ledger, Path(args.sackmann_dir), Path(args.oncourt_dir))
    ledger.sort(key=lambda row: (row.get("date", ""), row.get("forecast_id", "")))
    write_csv(Path(args.ledger), ledger)
    payload = report_payload(ledger)
    write_report(Path(args.report), Path(args.json), payload)
    print(
        "Most Aces forecasts: "
        f"added={added}, settled={settled_now}, rows={len(ledger)}, "
        f"status={payload['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
