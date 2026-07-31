#!/usr/bin/env python3
"""Report prospective evidence for the registered venue ace factor candidate."""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"
DEFAULT_FACTORS = PROPS_DIR / "venue-ace-factors.csv"
DEFAULT_OBSERVATIONS = PROPS_DIR / "shadow" / "venue-ace-factor-v1-observations.csv"
DEFAULT_JSON = PROPS_DIR / "backtest" / "venue-ace-factor-v1-gate.json"
DEFAULT_REPORT = PROPS_DIR / "backtest" / "venue-ace-factor-v1-report.txt"
MIN_SETTLED = 600
MIN_EVENTS = 150
MIN_SEGMENT_ROWS = 100


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def number(value: object, fallback: float = 0.0) -> float:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return fallback
    return parsed if math.isfinite(parsed) else fallback


def optional_number(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = number(text, float("nan"))
    return parsed if math.isfinite(parsed) else None


def log_loss(probability: float, outcome: float) -> float:
    bounded = min(1.0 - 1e-12, max(1e-12, probability))
    return -(outcome * math.log(bounded) + (1.0 - outcome) * math.log(1.0 - bounded))


def event_identity(row: dict[str, str]) -> str:
    event_id = str(row.get("event_id") or "").strip()
    if event_id:
        return f"event:{event_id}"
    return "|".join(
        [
            str(row.get("date") or ""),
            str(row.get("tour") or ""),
            str(row.get("player") or ""),
            str(row.get("opponent") or ""),
        ]
    )


def build_payload(
    factors: list[dict[str, str]],
    observations: list[dict[str, str]],
) -> dict[str, Any]:
    scope_factors = [
        row
        for row in factors
        if str(row.get("tour") or "").upper() == "ATP"
        and str(row.get("surface") or "") in {"Hard", "Clay"}
    ]
    eligible = [
        row for row in scope_factors if str(row.get("eligible") or "").lower() == "true"
    ]
    leakage_rows = [
        row
        for row in factors
        if int(number(row.get("source_end_season"))) >= int(number(row.get("target_season")))
    ]
    settled = [row for row in observations if str(row.get("settlement_status") or "").lower() == "settled"]
    pending = [row for row in observations if str(row.get("settlement_status") or "").lower() == "pending"]
    distinct_events = {event_identity(row) for row in observations if event_identity(row)}
    pnl = sum(number(row.get("pnl")) for row in settled)
    clv = [
        number(row.get("clv_pct"))
        for row in observations
        if str(row.get("clv_pct") or "").strip()
    ]
    factor_sorted = sorted(eligible, key=lambda row: number(row.get("ace_factor"), 1.0))
    scored: list[dict[str, Any]] = []
    for row in settled:
        actual = optional_number(row.get("actual"))
        line = optional_number(row.get("line"))
        control_prob = optional_number(row.get("control_p_over_no_push"))
        candidate_prob = optional_number(row.get("candidate_p_over_no_push"))
        if None in (actual, line, control_prob, candidate_prob) or actual == line:
            continue
        outcome = 1.0 if actual > line else 0.0
        scored.append(
            {
                "surface": str(row.get("surface") or "Unknown"),
                "outcome": outcome,
                "control_prob": control_prob,
                "candidate_prob": candidate_prob,
            }
        )

    def score(rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
        if not rows:
            return {"n": 0, "control_brier": None, "candidate_brier": None, "brier_delta": None,
                    "control_logloss": None, "candidate_logloss": None, "logloss_delta": None}
        control_brier = sum((row["control_prob"] - row["outcome"]) ** 2 for row in rows) / len(rows)
        candidate_brier = sum((row["candidate_prob"] - row["outcome"]) ** 2 for row in rows) / len(rows)
        control_ll = sum(log_loss(row["control_prob"], row["outcome"]) for row in rows) / len(rows)
        candidate_ll = sum(log_loss(row["candidate_prob"], row["outcome"]) for row in rows) / len(rows)
        return {
            "n": len(rows),
            "control_brier": control_brier,
            "candidate_brier": candidate_brier,
            "brier_delta": candidate_brier - control_brier,
            "control_logloss": control_ll,
            "candidate_logloss": candidate_ll,
            "logloss_delta": candidate_ll - control_ll,
        }

    paired = score(scored)
    segments = {
        surface: score([row for row in scored if row["surface"] == surface])
        for surface in ("Hard", "Clay")
    }
    brier_improved = (
        paired["n"] >= MIN_SETTLED
        and paired["brier_delta"] is not None
        and paired["brier_delta"] < 0
    )
    segment_regression = (
        paired["n"] >= MIN_SETTLED
        and all(
            segment["n"] >= MIN_SEGMENT_ROWS
            and segment["brier_delta"] is not None
            and segment["brier_delta"] <= 0.005
            for segment in segments.values()
        )
    )
    gates = {
        "strictly_prior_seasons": not leakage_rows,
        "settled_rows": len(settled) >= MIN_SETTLED,
        "distinct_events": len(distinct_events) >= MIN_EVENTS,
        "brier_improvement": brier_improved,
        "segment_regression": segment_regression,
    }
    return {
        "version": "venue-ace-factor-v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "PROSPECTIVE_SHADOW",
        "decision": "NOT_SELLABLE",
        "automatic_promotion": False,
        "coverage": {
            "eligible_venues": len(eligible),
            "total_venues": len(scope_factors),
            "factor_min": number(factor_sorted[0].get("ace_factor"), 1.0) if factor_sorted else None,
            "factor_max": number(factor_sorted[-1].get("ace_factor"), 1.0) if factor_sorted else None,
            "lowest": factor_sorted[:10],
            "highest": list(reversed(factor_sorted[-10:])),
        },
        "prospective": {
            "registered": len(observations),
            "settled": len(settled),
            "pending": len(pending),
            "distinct_events": len(distinct_events),
            "pnl_units": pnl,
            "roi_pct": (pnl / len(settled) * 100.0) if settled else None,
            "clv_rows": len(clv),
            "mean_clv_pct": (sum(clv) / len(clv)) if clv else None,
        },
        "paired_scoring": {
            "overall": paired,
            "by_surface": segments,
            "push_rows_excluded": len(settled) - len(scored),
        },
        "integrity": {
            "same_or_future_season_rows": len(leakage_rows),
            "leakage_examples": leakage_rows[:5],
        },
        "minimums": {
            "settled_rows": MIN_SETTLED,
            "distinct_events": MIN_EVENTS,
            "segment_rows": MIN_SEGMENT_ROWS,
        },
        "gates": gates,
        "passed_gate_count": sum(bool(value) for value in gates.values()),
        "total_gate_count": len(gates),
    }


def render(payload: dict[str, Any]) -> str:
    coverage = payload["coverage"]
    prospective = payload["prospective"]
    integrity = payload["integrity"]
    gates = payload["gates"]
    paired = payload["paired_scoring"]["overall"]
    roi = prospective["roi_pct"]
    clv = prospective["mean_clv_pct"]
    lines = [
        "Venue Ace Factor v1 - Registered Prospective Shadow",
        f"Generated UTC: {payload['generated_at']}",
        f"Status: {payload['status']} / {payload['decision']}",
        "Routing: shadow only; no public tips, staking or automatic promotion.",
        "",
        f"Venue coverage: {coverage['eligible_venues']}/{coverage['total_venues']} eligible",
        f"Factor range: {coverage['factor_min'] if coverage['factor_min'] is not None else '-'} to {coverage['factor_max'] if coverage['factor_max'] is not None else '-'}",
        f"Evidence: {prospective['settled']}/{payload['minimums']['settled_rows']} settled; {prospective['pending']} pending; {prospective['distinct_events']}/{payload['minimums']['distinct_events']} events",
        f"P/L: {prospective['pnl_units']:+.2f}u | ROI: {roi:+.2f}%" if roi is not None else f"P/L: {prospective['pnl_units']:+.2f}u | ROI: -",
        f"CLV: {clv:+.2f}% across {prospective['clv_rows']} rows" if clv is not None else "CLV: -",
        (
            f"Paired Brier: control {paired['control_brier']:.5f} vs candidate {paired['candidate_brier']:.5f} "
            f"(delta {paired['brier_delta']:+.5f}, n={paired['n']})"
            if paired["brier_delta"] is not None
            else "Paired Brier: awaiting settled main-line observations"
        ),
        (
            f"Paired log loss: control {paired['control_logloss']:.5f} vs candidate {paired['candidate_logloss']:.5f} "
            f"(delta {paired['logloss_delta']:+.5f})"
            if paired["logloss_delta"] is not None
            else "Paired log loss: awaiting settled main-line observations"
        ),
        f"Leakage check: {integrity['same_or_future_season_rows']} same/future-season factor rows",
        "",
        "Gates:",
        *[f"- {name}: {'PASS' if passed else 'BLOCKED'}" for name, passed in gates.items()],
        "",
        "DO NOT PROMOTE: paired scoring and prospective sample gates must all pass first.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factors", type=Path, default=DEFAULT_FACTORS)
    parser.add_argument("--observations", type=Path, default=DEFAULT_OBSERVATIONS)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--out-report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    payload = build_payload(read_csv(args.factors), read_csv(args.observations))
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.out_report.write_text(render(payload), encoding="utf-8")
    print(
        f"Venue ace v1: {payload['coverage']['eligible_venues']} eligible venues; "
        f"{payload['prospective']['settled']} settled -> {args.out_report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
