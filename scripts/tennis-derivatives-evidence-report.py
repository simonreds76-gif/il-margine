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

ROOT = Path(__file__).resolve().parent.parent
PROPS_INBOX = ROOT / "data" / "tennis-props" / "inbox"
SPREAD_DATASET = ROOT / "data" / "backtest" / "spread-v1-training-dataset.csv"
SPREAD_CLV = ROOT / "data" / "backtest" / "strict-clv-audit-spreadv1-2026.csv"
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


def props_status(rows: list[dict[str, str]]) -> dict[str, object]:
    events = {str(row.get("event_id") or "") for row in rows if row.get("event_id")}
    dates = sorted({str(row.get("date") or "") for row in rows if row.get("date")})
    markets = Counter(str(row.get("market") or "unknown") for row in rows)
    tours = Counter(str(row.get("tour") or "unknown") for row in rows)
    row_gate = len(rows) >= 300
    event_gate = len(events) >= 100
    return {
        "status": "COLLECTING" if rows else "NO_CAPTURE",
        "promotion_status": "BLOCKED_REAL_LINE_SAMPLE",
        "line_rows": len(rows),
        "distinct_events": len(events),
        "dates": dates,
        "markets": dict(markets),
        "tours": dict(tours),
        "settled_shadow_bets": 0,
        "gates": {
            "line_rows_300": row_gate,
            "distinct_events_100": event_gate,
            "settled_shadow_bets_300": False,
            "mean_clv_0_5pct": False,
        },
        "reason": "Captured prices exist, but current Sackmann results stop before Wimbledon; no July prop line can be honestly settled yet.",
    }


def spread_status(dataset: list[dict[str, str]], clv_rows: list[dict[str, str]]) -> dict[str, object]:
    clv = [value for row in clv_rows if (value := number(row.get("clv_implied_delta_pct"))) is not None]
    settled = [row for row in clv_rows if str(row.get("bet_outcome") or "").upper() in {"WIN", "LOSS", "PUSH"}]
    avg_clv = mean(clv)
    positive_share = (100.0 * sum(value > 0 for value in clv) / len(clv)) if clv else None
    gates = {
        "real_line_rows_600": len(dataset) >= 600,
        "settled_shadow_bets_200": len(settled) >= 200,
        "mean_clv_1pct": avg_clv is not None and avg_clv >= 1.0,
        "positive_clv_share_55pct": positive_share is not None and positive_share >= 55.0,
    }
    return {
        "status": "COLLECTING" if dataset else "NO_CAPTURE",
        "promotion_status": "PASS" if all(gates.values()) else "BLOCKED_REAL_LINE_SAMPLE",
        "real_line_rows": len(dataset),
        "settled_shadow_bets": len(settled),
        "clv_rows": len(clv),
        "mean_clv_pct": avg_clv,
        "positive_clv_share_pct": positive_share,
        "gates": gates,
        "reason": "The existing spread correction regressed on validation; base-only shadow evidence remains below promotion gates.",
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
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-txt", type=Path, default=OUT_TXT)
    args = parser.parse_args()

    props = props_status(props_history_rows(args.props_inbox))
    spread = spread_status(csv_rows(args.spread_dataset), csv_rows(args.spread_clv))
    props_model = json.loads(PROPS_GATE.read_text(encoding="utf-8")) if PROPS_GATE.exists() else {"status": "MISSING"}
    payload = {
        "version": "tennis-serve-derivatives-0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "moneyline_routing_changed": False,
        "overall_status": "BLOCKED",
        "spread_shape": spread,
        "total_games_shape": {
            "status": "BLOCKED",
            "promotion_status": "BLOCKED_NO_REGISTERED_REAL_LINE_DATASET",
            "real_line_rows": 0,
            "reason": "No reproducible paired Pinnacle total-games dataset is committed yet; synthetic total prices are forbidden as evidence.",
        },
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
        f"- Settled shadow: {spread['settled_shadow_bets']} / 200",
        f"- Mean CLV: {fmt(spread['mean_clv_pct'])}% / +1.00%",
        f"- Positive CLV share: {fmt(spread['positive_clv_share_pct'])}% / 55.00%",
        f"- Status: {spread['promotion_status']}",
        "",
        "Total-games shape",
        "- Real paired line rows: 0 / 600",
        "- Status: BLOCKED_NO_REGISTERED_REAL_LINE_DATASET",
        "",
        "Aces / double faults",
        f"- Captured Bet365 line rows: {props['line_rows']} / 300",
        f"- Distinct events: {props['distinct_events']} / 100",
        f"- Settled shadow: {props['settled_shadow_bets']} / 300",
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
