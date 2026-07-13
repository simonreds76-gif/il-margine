#!/usr/bin/env python3
"""Report settled performance for the extreme model/market gap research lane."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVE = ROOT / "data" / "backtest" / "tennis-model-market-gap-archive.csv"
DEFAULT_ML_CLV = ROOT / "data" / "backtest" / "tennis-model-market-gap-clv-ml.csv"
DEFAULT_SPREAD_CLV = ROOT / "data" / "backtest" / "tennis-model-market-gap-clv-spread.csv"
DEFAULT_JSON = ROOT / "data" / "backtest" / "tennis-model-market-gap-report.json"
DEFAULT_TEXT = ROOT / "data" / "backtest" / "tennis-model-market-gap-report.txt"


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_settled_bet(row: dict[str, str]) -> bool:
    return (row.get("settlement_status") or "").lower() == "settled" and (row.get("bet_outcome") or "").upper() in {"WIN", "LOSS", "VOID"}


def pnl(row: dict[str, str]) -> float:
    outcome = (row.get("bet_outcome") or "").upper()
    stake = number(row.get("stake_units"), 1.0)
    odds = number(row.get("selected_odds"))
    if outcome == "WIN" and odds > 1:
        return (odds - 1.0) * stake
    if outcome == "LOSS":
        return -stake
    return 0.0


def clv_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    values = [number(row.get("clv_implied_delta_pct")) for row in rows if row.get("clv_implied_delta_pct") not in {None, ""}]
    return {
        "rows": len(values),
        "avg_clv_pct": round(sum(values) / len(values), 4) if values else None,
        "positive_clv_pct": round(sum(value > 0 for value in values) / len(values) * 100.0, 2) if values else None,
    }


def performance(rows: list[dict[str, str]], clv: dict[str, Any] | None = None) -> dict[str, Any]:
    settled = [row for row in rows if is_settled_bet(row)]
    decided = [row for row in settled if (row.get("bet_outcome") or "").upper() in {"WIN", "LOSS"}]
    wins = sum((row.get("bet_outcome") or "").upper() == "WIN" for row in decided)
    losses = len(decided) - wins
    voids = len(settled) - len(decided)
    staked = sum(number(row.get("stake_units"), 1.0) for row in decided)
    pnl_units = sum(pnl(row) for row in decided)
    values = [number(row.get("value_pct")) for row in rows if row.get("value_pct") not in {None, ""}]
    gaps = [number(row.get("model_market_gap_pp")) for row in rows if row.get("model_market_gap_pp") not in {None, ""}]
    return {
        "signals": len(rows),
        "pending": sum(not is_settled_bet(row) for row in rows),
        "settled": len(settled),
        "wins": wins,
        "losses": losses,
        "voids": voids,
        "pnl_units": round(pnl_units, 4),
        "roi_pct": round(pnl_units / staked * 100.0, 2) if staked else None,
        "avg_value_pct": round(sum(values) / len(values), 2) if values else None,
        "avg_gap_pp": round(sum(gaps) / len(gaps), 2) if gaps else None,
        "clv_rows": (clv or {}).get("rows", 0),
        "avg_clv_pct": (clv or {}).get("avg_clv_pct"),
        "positive_clv_pct": (clv or {}).get("positive_clv_pct"),
    }


def build_report(archive: list[dict[str, str]], ml_clv_rows: list[dict[str, str]], spread_clv_rows: list[dict[str, str]]) -> dict[str, Any]:
    ml_rows = [row for row in archive if (row.get("bet_type") or "match").lower() != "spread"]
    spread_rows = [row for row in archive if (row.get("bet_type") or "").lower() == "spread"]
    ml_clv = clv_summary(ml_clv_rows)
    spread_clv = clv_summary(spread_clv_rows)

    by_diagnosis: dict[str, dict[str, Any]] = {}
    diagnoses = sorted({row.get("diagnosis_primary") or "unknown" for row in archive})
    for diagnosis in diagnoses:
        group = [row for row in archive if (row.get("diagnosis_primary") or "unknown") == diagnosis]
        by_diagnosis[diagnosis] = {
            "ml": performance([row for row in group if (row.get("bet_type") or "match") != "spread"]),
            "spread": performance([row for row in group if (row.get("bet_type") or "") == "spread"]),
        }

    pairs: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in archive:
        if is_settled_bet(row):
            pairs[row.get("anomaly_id") or ""][row.get("hypothesis") or ""] = row
    paired = [group for group in pairs.values() if "extreme_ml_side" in group and "same_player_spread" in group]
    matrix: Counter[str] = Counter()
    for group in paired:
        ml_outcome = (group["extreme_ml_side"].get("bet_outcome") or "").upper()
        spread_outcome = (group["same_player_spread"].get("bet_outcome") or "").upper()
        matrix[f"ml_{ml_outcome.lower()}__spread_{spread_outcome.lower()}"] += 1

    spread_perf = performance(spread_rows, spread_clv)
    gate_checks = {
        "settled_200": spread_perf["settled"] >= 200,
        "roi_positive": spread_perf["roi_pct"] is not None and spread_perf["roi_pct"] > 0,
        "clv_at_least_0_5pct": spread_perf["avg_clv_pct"] is not None and spread_perf["avg_clv_pct"] >= 0.5,
        "positive_clv_at_least_55pct": spread_perf["positive_clv_pct"] is not None and spread_perf["positive_clv_pct"] >= 55,
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "RESEARCH_ONLY",
        "explanation": "Extreme ML gaps are guarded anomalies. The spread is a separately settled hypothesis, never an inferred recommendation.",
        "anomalies": len({row.get("anomaly_id") for row in archive if row.get("anomaly_id")}),
        "ml": performance(ml_rows, ml_clv),
        "spread": spread_perf,
        "paired_settled": len(paired),
        "paired_outcomes": dict(matrix),
        "by_diagnosis": by_diagnosis,
        "spread_promotion_gate": {
            "passes": all(gate_checks.values()),
            "checks": gate_checks,
            "rule": "n>=200, ROI>0, mean CLV>=+0.5%, positive CLV share>=55%",
        },
    }


def format_metric(metric: dict[str, Any]) -> str:
    roi = "n/a" if metric.get("roi_pct") is None else f"{metric['roi_pct']:+.2f}%"
    clv = "n/a" if metric.get("avg_clv_pct") is None else f"{metric['avg_clv_pct']:+.3f}%"
    return (
        f"signals={metric['signals']} pending={metric['pending']} settled={metric['settled']} "
        f"{metric['wins']}W/{metric['losses']}L/{metric['voids']}V "
        f"P/L={metric['pnl_units']:+.2f}u ROI={roi} CLV={clv} (n={metric['clv_rows']})"
    )


def report_text(report: dict[str, Any]) -> str:
    lines = [
        "TENNIS EXTREME MODEL/MARKET GAP LAB",
        "===================================",
        f"Generated: {report['generated_at']}",
        "Status: RESEARCH ONLY - live ML guard remains active",
        "",
        "ML anomaly hypothesis",
        format_metric(report["ml"]),
        "",
        "Same-player spread hypothesis",
        format_metric(report["spread"]),
        "",
        f"Paired settled anomalies: {report['paired_settled']}",
    ]
    for key, value in sorted(report["paired_outcomes"].items()):
        lines.append(f"  {key}: {value}")
    lines.extend(["", "Primary diagnosis cuts"])
    for diagnosis, values in report["by_diagnosis"].items():
        lines.append(f"  {diagnosis}")
        lines.append(f"    ML:     {format_metric(values['ml'])}")
        lines.append(f"    Spread: {format_metric(values['spread'])}")
    gate = report["spread_promotion_gate"]
    lines.extend(
        [
            "",
            f"Spread gate: {'PASS' if gate['passes'] else 'FAIL'} - {gate['rule']}",
            "A large ML EV is not proof of spread value. Only settled ROI plus closing-line evidence can establish that.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--ml-clv", default=str(DEFAULT_ML_CLV))
    parser.add_argument("--spread-clv", default=str(DEFAULT_SPREAD_CLV))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--text", default=str(DEFAULT_TEXT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(load_csv(Path(args.archive)), load_csv(Path(args.ml_clv)), load_csv(Path(args.spread_clv)))
    json_path, text_path = Path(args.json), Path(args.text)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    text_path.write_text(report_text(report), encoding="utf-8")
    print(format_metric(report["ml"]))
    print(format_metric(report["spread"]))
    print(f"Spread gate: {'PASS' if report['spread_promotion_gate']['passes'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
