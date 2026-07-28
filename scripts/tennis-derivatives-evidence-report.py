#!/usr/bin/env python3
"""Build the single source of truth for tennis derivative evidence coverage."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PROPS_INBOX = ROOT / "data" / "tennis-props" / "inbox"
PROPS_SHADOW = ROOT / "data" / "tennis-props" / "shadow" / "aces-dfs-shadow-signals.csv"
SPREAD_DATASET = ROOT / "data" / "backtest" / "spread-real-scored-atp.csv"
SPREAD_CLV = ROOT / "data" / "backtest" / "strict-clv-audit-spreadv1-2026.csv"
PINNACLE_COVERAGE = ROOT / "data" / "vnext" / "tennis-derivatives-pinnacle-coverage.json"
REGISTRATION = ROOT / "data" / "vnext" / "experiment-registration-derivatives-0.1.json"
PROPS_GATE = ROOT / "data" / "tennis-props" / "backtest" / "aces-dfs-v2-rung1-gate.json"
OUT_JSON = ROOT / "data" / "vnext" / "tennis-derivatives-evidence-status.json"
OUT_TXT = ROOT / "data" / "vnext" / "tennis-derivatives-evidence-report.txt"


def csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def props_history_rows(inbox: Path) -> list[dict[str, str]]:
    rows_by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for path in sorted(inbox.glob("bet365-lines-history-*.csv")):
        for row in csv_rows(path):
            key = (
                str(row.get("event_id") or ""),
                str(row.get("date") or ""),
                str(row.get("player") or ""),
                str(row.get("market") or ""),
                str(row.get("line") or ""),
                str(row.get("capture_ts") or ""),
            )
            rows_by_key[key] = row
    return list(rows_by_key.values())


def number(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def league_count(coverage: dict[str, Any], field: str, league: str) -> int:
    values = coverage.get(field)
    if not isinstance(values, dict):
        return 0
    return int(number(values.get(league)) or 0)


def registered_evaluation(registration: dict[str, Any], lane: str) -> dict[str, Any]:
    evaluations = registration.get("evaluations")
    if not isinstance(evaluations, list):
        return {}
    matches = [
        item for item in evaluations
        if isinstance(item, dict) and str(item.get("lane") or "") == lane
    ]
    return matches[-1] if matches else {}


def total_games_status(
    evaluation: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, object]:
    if evaluation.get("status") == "TESTED_AND_REJECTED":
        return {
            "status": "TESTED",
            "promotion_status": "TESTED_AND_REJECTED",
            "evaluated_at": evaluation.get("evaluated_at"),
            "settled_joined_rows": int(number(evaluation.get("settled_joined_rows")) or 0),
            "real_line_rows": int(number(evaluation.get("scored_non_push_rows")) or 0),
            "priced_bets": int(number(evaluation.get("priced_bets")) or 0),
            "edge_threshold_pct": number(evaluation.get("edge_threshold_pct")),
            "roi_pct": number(evaluation.get("roi_pct")),
            "roi_ci95_pct": evaluation.get("roi_ci95_pct"),
            "mean_clv_pct": number(evaluation.get("mean_clv_pct")),
            "positive_clv_share_moved_pct": number(evaluation.get("positive_clv_share_moved_pct")),
            "market_brier": number(evaluation.get("market_brier")),
            "model_brier": number(evaluation.get("best_model_brier")),
            "best_model": evaluation.get("best_model"),
            "captured_line_offers": league_count(coverage, "unique_line_offers_by_league", "ATP"),
            "captured_matches": league_count(coverage, "unique_matches_by_league", "ATP"),
            "captured_challenger_line_offers": league_count(
                coverage,
                "unique_line_offers_by_league",
                "Challenger",
            ),
            "reason": str(
                evaluation.get("decision")
                or "Tested on real Pinnacle totals and rejected as a betting lane."
            ),
        }
    return {
        "status": "COLLECTING" if coverage else "BLOCKED",
        "promotion_status": "BLOCKED_NO_REGISTERED_REAL_LINE_DATASET",
        "real_line_rows": 0,
        "captured_line_offers": league_count(coverage, "unique_line_offers_by_league", "ATP"),
        "captured_matches": league_count(coverage, "unique_matches_by_league", "ATP"),
        "captured_challenger_line_offers": league_count(
            coverage,
            "unique_line_offers_by_league",
            "Challenger",
        ),
        "reason": "No registered real-line evaluation exists.",
    }


def props_status(rows: list[dict[str, str]], shadow_rows: list[dict[str, str]]) -> dict[str, object]:
    events = {str(row.get("event_id") or "") for row in rows if row.get("event_id")}
    offers = {
        (
            str(row.get("event_id") or ""),
            str(row.get("player") or ""),
            str(row.get("market") or ""),
            str(row.get("line") or ""),
        )
        for row in rows
        if row.get("event_id")
    }
    dates = sorted({str(row.get("date") or "") for row in rows if row.get("date")})
    markets = Counter(str(row.get("market") or "unknown") for row in rows)
    tours = Counter(str(row.get("tour") or "unknown") for row in rows)
    settled = [row for row in shadow_rows if str(row.get("settlement_status") or "").lower() == "settled"]
    pending = [row for row in shadow_rows if str(row.get("settlement_status") or "").lower() == "pending"]
    voids = [row for row in shadow_rows if str(row.get("settlement_status") or "").lower() == "void"]
    clv = [value for row in settled if (value := number(row.get("clv_pct"))) is not None]
    avg_clv = mean(clv)
    positive_clv = 100.0 * sum(value > 0 for value in clv) / len(clv) if clv else None
    pnl = sum(number(row.get("pnl")) or 0.0 for row in settled)
    roi = 100.0 * pnl / len(settled) if settled else None
    row_gate = len(offers) >= 300
    event_gate = len(events) >= 100
    settled_gate = len(settled) >= 300
    clv_gate = avg_clv is not None and avg_clv >= 0.5
    gates = {
        "unique_line_offers_300": row_gate,
        "distinct_events_100": event_gate,
        "settled_shadow_bets_300": settled_gate,
        "mean_clv_0_5pct": clv_gate,
    }
    return {
        "status": "COLLECTING" if rows else "NO_CAPTURE",
        "promotion_status": "PASS" if all(gates.values()) else "BLOCKED_REAL_LINE_SAMPLE",
        "snapshot_rows": len(rows),
        "line_rows": len(offers),
        "distinct_events": len(events),
        "dates": dates,
        "markets": dict(markets),
        "tours": dict(tours),
        "settled_shadow_bets": len(settled),
        "pending_shadow_bets": len(pending),
        "void_shadow_bets": len(voids),
        "clv_rows": len(clv),
        "mean_clv_pct": avg_clv,
        "positive_clv_share_pct": positive_clv,
        "pnl_units": pnl,
        "roi_pct": roi,
        "gates": gates,
        "reason": "Collection and settlement are active; promotion remains blocked until every registered real-price gate passes.",
    }


def spread_status(dataset: list[dict[str, str]], clv_rows: list[dict[str, str]], coverage: dict[str, Any]) -> dict[str, object]:
    clv = [value for row in clv_rows if (value := number(row.get("clv_implied_delta_pct"))) is not None]
    settled = [row for row in clv_rows if str(row.get("bet_outcome") or "").upper() in {"WIN", "LOSS", "PUSH"}]
    non_push = [row for row in dataset if str(row.get("p1_cover_result") or "").upper() in {"WIN", "LOSS"}]
    market_brier = mean(
        [value for row in non_push if (value := number(row.get("market_brier"))) is not None]
    )
    verified_prestart = sum(
        str(row.get("publication_timing_quality") or "") == "verified_prestart"
        for row in dataset
    )
    true_close_rows = sum(str(row.get("clv_eligible") or "") == "1" for row in dataset)
    avg_clv = mean(clv)
    positive_share = (100.0 * sum(value > 0 for value in clv) / len(clv)) if clv else None
    gates = {
        "real_line_rows_600": len(dataset) >= 600,
        "settled_shadow_bets_200": len(settled) >= 200,
        "mean_clv_1pct": avg_clv is not None and avg_clv >= 1.0,
        "positive_clv_share_55pct": positive_share is not None and positive_share >= 55.0,
    }
    if all(gates.values()):
        promotion_status = "PASS"
    elif not gates["real_line_rows_600"]:
        promotion_status = "BLOCKED_REAL_LINE_SAMPLE"
    else:
        promotion_status = "BLOCKED_PROSPECTIVE_EVIDENCE"
    return {
        "status": "COLLECTING" if dataset else "NO_CAPTURE",
        "promotion_status": promotion_status,
        "real_line_rows": len(dataset),
        "non_push_rows": len(non_push),
        "market_brier": market_brier,
        "verified_prestart_rows": verified_prestart,
        "true_close_rows": true_close_rows,
        "captured_line_offers": league_count(coverage, "unique_line_offers_by_league", "ATP"),
        "captured_matches": league_count(coverage, "unique_matches_by_league", "ATP"),
        "captured_challenger_line_offers": league_count(coverage, "unique_line_offers_by_league", "Challenger"),
        "settled_shadow_bets": len(settled),
        "clv_rows": len(clv),
        "mean_clv_pct": avg_clv,
        "positive_clv_share_pct": positive_share,
        "gates": gates,
        "reason": (
            "The canonical scorer removes the stale 188-row bottleneck. "
            "The existing spread correction regressed on validation and "
            "prospective ROI/CLV gates remain blocked."
        ),
    }


def fmt(value: object, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float) and not math.isfinite(value):
        return "n/a"
    return f"{float(value):.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--props-inbox", type=Path, default=PROPS_INBOX)
    parser.add_argument("--spread-dataset", type=Path, default=SPREAD_DATASET)
    parser.add_argument("--spread-clv", type=Path, default=SPREAD_CLV)
    parser.add_argument("--props-shadow", type=Path, default=PROPS_SHADOW)
    parser.add_argument("--pinnacle-coverage", type=Path, default=PINNACLE_COVERAGE)
    parser.add_argument("--registration", type=Path, default=REGISTRATION)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-txt", type=Path, default=OUT_TXT)
    args = parser.parse_args()

    pinnacle = json.loads(args.pinnacle_coverage.read_text(encoding="utf-8")) if args.pinnacle_coverage.exists() else {}
    spread_coverage = pinnacle.get("spread") if isinstance(pinnacle.get("spread"), dict) else {}
    total_coverage = pinnacle.get("total") if isinstance(pinnacle.get("total"), dict) else {}
    registration = json.loads(args.registration.read_text(encoding="utf-8")) if args.registration.exists() else {}
    totals = total_games_status(registered_evaluation(registration, "total_games_shape"), total_coverage)
    props = props_status(props_history_rows(args.props_inbox), csv_rows(args.props_shadow))
    spread = spread_status(csv_rows(args.spread_dataset), csv_rows(args.spread_clv), spread_coverage)
    props_model = json.loads(PROPS_GATE.read_text(encoding="utf-8")) if PROPS_GATE.exists() else {"status": "MISSING"}
    payload = {
        "version": "tennis-serve-derivatives-0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "moneyline_routing_changed": False,
        "overall_status": "BLOCKED",
        "spread_shape": spread,
        "total_games_shape": totals,
        "aces_dfs": props,
        "props_v2_rung1": {
            "status": props_model.get("status", "MISSING"),
            "routing": props_model.get("routing", "blocked"),
        },
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "Tennis Serve-Derivatives Evidence Ledger",
        f"Generated UTC: {payload['generated_at']}",
        "Moneyline routing changed: NO",
        "Overall: BLOCKED (research collection only)",
        "",
        "Spread shape",
        f"- Real line rows: {spread['real_line_rows']} / 600",
        f"- Scored non-push rows: {spread['non_push_rows']}",
        f"- Market baseline Brier: {fmt(spread['market_brier'], 5)}",
        f"- Verified pre-start rows: {spread['verified_prestart_rows']}",
        f"- True-close eligible rows: {spread['true_close_rows']}",
        f"- Captured ATP coverage inventory: {spread['captured_line_offers']} offers across {spread['captured_matches']} dated pairs",
        f"- Challenger inventory kept separate: {spread['captured_challenger_line_offers']} offers",
        f"- Settled shadow: {spread['settled_shadow_bets']} / 200",
        f"- Mean CLV: {fmt(spread['mean_clv_pct'])}% / +1.00%",
        f"- Positive CLV share: {fmt(spread['positive_clv_share_pct'])}% / 55.00%",
        f"- Status: {spread['promotion_status']}",
        "",
        "Total-games shape",
        f"- Scored non-push real paired rows: {totals['real_line_rows']}",
        f"- Settled joined rows: {totals.get('settled_joined_rows', 0)}",
        f"- ROI at registered threshold: {fmt(totals.get('roi_pct'))}%",
        f"- ROI CI95: {totals.get('roi_ci95_pct', 'n/a')}",
        f"- Mean CLV: {fmt(totals.get('mean_clv_pct'), 3)}%",
        f"- Brier, best model / market: {fmt(totals.get('model_brier'), 5)} / {fmt(totals.get('market_brier'), 5)}",
        f"- Status: {totals['promotion_status']}",
        f"- Decision: {totals['reason']}",
        "",
        "Aces / double faults",
        f"- Captured Bet365 snapshots: {props['snapshot_rows']}",
        f"- Unique Bet365 line offers: {props['line_rows']} / 300",
        f"- Distinct events: {props['distinct_events']} / 100",
        f"- Settled shadow: {props['settled_shadow_bets']} / 300",
        f"- Pending / void: {props['pending_shadow_bets']} / {props['void_shadow_bets']}",
        f"- Mean CLV: {fmt(props['mean_clv_pct'])}% / +0.50%",
        f"- ROI: {fmt(props['roi_pct'])}% (research only)",
        f"- Status: {props['promotion_status']}",
        "",
        f"Props v2 rung 1: {props_model.get('status', 'MISSING')} ({props_model.get('routing', 'blocked')})",
        "No lane above is authorised for live routing or staking.",
    ]
    args.out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.out_txt)
    print(args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
