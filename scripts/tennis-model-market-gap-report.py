#!/usr/bin/env python3
"""Report settled performance for the extreme model/market gap research lane."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVE = ROOT / "data" / "backtest" / "tennis-model-market-gap-archive.csv"
DEFAULT_ML_CLV = ROOT / "data" / "backtest" / "tennis-model-market-gap-clv-ml.csv"
DEFAULT_SPREAD_CLV = ROOT / "data" / "backtest" / "tennis-model-market-gap-clv-spread.csv"
DEFAULT_JSON = ROOT / "data" / "backtest" / "tennis-model-market-gap-report.json"
DEFAULT_TEXT = ROOT / "data" / "backtest" / "tennis-model-market-gap-report.txt"
DEFAULT_WEEKLY = ROOT / "data" / "backtest" / "tennis-model-market-gap-weekly.csv"


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


def row_date(row: dict[str, str]) -> date | None:
    for key in ("date", "signal_date", "match_date"):
        value = (row.get(key) or "").strip()
        if not value:
            continue
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            continue
    return None


def rows_in_window(rows: list[dict[str, str]], days: int, today: date) -> list[dict[str, str]]:
    cutoff = today - timedelta(days=max(days - 1, 0))
    return [row for row in rows if (parsed := row_date(row)) is not None and cutoff <= parsed <= today]


def evidence_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    signal_date = row_date(row)
    ids = sorted((str(row.get("player1_id") or ""), str(row.get("player2_id") or "")))
    bet_type = (row.get("bet_type") or "match").lower()
    return (signal_date.isoformat() if signal_date else "", ids[0], ids[1], bet_type)


def clv_for_signals(signals: list[dict[str, str]], clv_rows: list[dict[str, str]]) -> dict[str, Any]:
    keys = {evidence_key(row) for row in signals}
    return clv_summary([row for row in clv_rows if evidence_key(row) in keys])


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


def paired_summary(archive: list[dict[str, str]]) -> dict[str, Any]:
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

    ml_losses = sum((group["extreme_ml_side"].get("bet_outcome") or "").upper() == "LOSS" for group in paired)
    spread_rescues = matrix.get("ml_loss__spread_win", 0)
    return {
        "settled": len(paired),
        "outcomes": dict(matrix),
        "ml_losses": ml_losses,
        "spread_rescues": spread_rescues,
        "spread_rescue_rate_pct": round(spread_rescues / ml_losses * 100.0, 2) if ml_losses else None,
    }


def cohort_summary(
    archive: list[dict[str, str]],
    ml_clv_rows: list[dict[str, str]],
    spread_clv_rows: list[dict[str, str]],
) -> dict[str, Any]:
    ml_rows = [row for row in archive if (row.get("bet_type") or "match").lower() != "spread"]
    spread_rows = [row for row in archive if (row.get("bet_type") or "").lower() == "spread"]
    pairs = paired_summary(archive)
    return {
        "anomalies": len({row.get("anomaly_id") for row in archive if row.get("anomaly_id")}),
        "ml": performance(ml_rows, clv_for_signals(ml_rows, ml_clv_rows)),
        "spread": performance(spread_rows, clv_for_signals(spread_rows, spread_clv_rows)),
        "paired_settled": pairs["settled"],
        "paired_outcomes": pairs["outcomes"],
        "spread_rescues": pairs["spread_rescues"],
        "spread_rescue_rate_pct": pairs["spread_rescue_rate_pct"],
    }


def segment_summary(
    archive: list[dict[str, str]],
    ml_clv_rows: list[dict[str, str]],
    spread_clv_rows: list[dict[str, str]],
    field: str,
) -> dict[str, dict[str, Any]]:
    values = sorted({(row.get(field) or "unknown").strip() or "unknown" for row in archive})
    return {
        value: cohort_summary(
            [row for row in archive if ((row.get(field) or "unknown").strip() or "unknown") == value],
            ml_clv_rows,
            spread_clv_rows,
        )
        for value in values
    }


def review_assessment(spread_perf: dict[str, Any], gate_passes: bool) -> tuple[str, str]:
    settled = spread_perf["settled"]
    roi = spread_perf["roi_pct"]
    avg_clv = spread_perf["avg_clv_pct"]
    positive_clv = spread_perf["positive_clv_pct"]
    if gate_passes:
        return "REVIEW_CANDIDATE", "The registered evidence gate passed. Manual model-risk review is required before any live change."
    if settled < 50:
        label = "spread" if settled == 1 else "spreads"
        return "KEEP_COLLECTING", f"Only {settled} settled {label}; at least 50 are required for an early directional read and 200 for promotion review."
    if avg_clv is None:
        return "KEEP_COLLECTING_NO_CLV", "Settlement exists but usable closing-line evidence is missing."
    if avg_clv < 0 or (positive_clv is not None and positive_clv < 45):
        return "PAUSE_NEGATIVE_CLV", "The handicap hypothesis is not beating the close on the current evidence."
    if roi is not None and roi < -5:
        return "PAUSE_NEGATIVE_ROI", "Real-price ROI is materially negative despite the available CLV evidence."
    return "KEEP_COLLECTING", "Evidence is directionally interesting but remains below the registered promotion gate."


def build_report(
    archive: list[dict[str, str]],
    ml_clv_rows: list[dict[str, str]],
    spread_clv_rows: list[dict[str, str]],
    today: date | None = None,
) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    all_time = cohort_summary(archive, ml_clv_rows, spread_clv_rows)
    spread_perf = all_time["spread"]

    gate_checks = {
        "settled_200": spread_perf["settled"] >= 200,
        "roi_positive": spread_perf["roi_pct"] is not None and spread_perf["roi_pct"] > 0,
        "clv_at_least_0_5pct": spread_perf["avg_clv_pct"] is not None and spread_perf["avg_clv_pct"] >= 0.5,
        "positive_clv_at_least_55pct": spread_perf["positive_clv_pct"] is not None and spread_perf["positive_clv_pct"] >= 55,
    }
    gate_passes = all(gate_checks.values())
    review_status, review_reason = review_assessment(spread_perf, gate_passes)
    windows = {
        "last_7_days": cohort_summary(rows_in_window(archive, 7, today), ml_clv_rows, spread_clv_rows),
        "last_30_days": cohort_summary(rows_in_window(archive, 30, today), ml_clv_rows, spread_clv_rows),
    }
    long_ev_rows = [row for row in archive if number(row.get("value_pct")) >= 100]
    segments = {
        "ev_bucket": segment_summary(archive, ml_clv_rows, spread_clv_rows, "ev_bucket"),
        "gap_bucket": segment_summary(archive, ml_clv_rows, spread_clv_rows, "gap_bucket"),
        "surface": segment_summary(archive, ml_clv_rows, spread_clv_rows, "surface"),
        "series": segment_summary(archive, ml_clv_rows, spread_clv_rows, "series"),
        "diagnosis": segment_summary(archive, ml_clv_rows, spread_clv_rows, "diagnosis_primary"),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "RESEARCH_ONLY",
        "explanation": "Extreme ML gaps are guarded anomalies. The spread is a separately settled hypothesis, never an inferred recommendation.",
        **all_time,
        "windows": windows,
        "long_ev_100_plus": cohort_summary(long_ev_rows, ml_clv_rows, spread_clv_rows),
        "segments": segments,
        "by_diagnosis": segments["diagnosis"],
        "weekly_review": {
            "verdict": review_status,
            "reason": review_reason,
            "handicap_trustworthy_live": False,
            "automatic_promotion": False,
        },
        "spread_promotion_gate": {
            "passes": gate_passes,
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
    review = report["weekly_review"]
    seven = report["windows"]["last_7_days"]
    thirty = report["windows"]["last_30_days"]
    long_ev = report["long_ev_100_plus"]
    lines = [
        "TENNIS EXTREME MODEL/MARKET GAP LAB",
        "===================================",
        f"Generated: {report['generated_at']}",
        "Status: RESEARCH ONLY - live ML guard remains active",
        f"Weekly verdict: {review['verdict']}",
        f"Reason: {review['reason']}",
        "",
        "ML anomaly hypothesis",
        format_metric(report["ml"]),
        "",
        "Same-player spread hypothesis",
        format_metric(report["spread"]),
        "",
        "Trailing evidence",
        f"  Last 7d spread:  {format_metric(seven['spread'])}",
        f"  Last 30d spread: {format_metric(thirty['spread'])}",
        "",
        "Long ML EV subset (>=100%)",
        f"  ML:     {format_metric(long_ev['ml'])}",
        f"  Spread: {format_metric(long_ev['spread'])}",
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
            f"Spread gate: {'REVIEW CANDIDATE' if gate['passes'] else 'FAIL'} - {gate['rule']}",
            "Automatic promotion: disabled",
            "A large ML EV is not proof of spread value. Only settled ROI plus closing-line evidence can establish that.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_weekly_snapshot(path: Path, report: dict[str, Any], generated: datetime | None = None) -> None:
    generated = generated or datetime.now(timezone.utc)
    week_start = (generated.date() - timedelta(days=generated.weekday())).isoformat()
    spread = report["spread"]
    ml = report["ml"]
    row = {
        "week_start": week_start,
        "generated_at": report["generated_at"],
        "verdict": report["weekly_review"]["verdict"],
        "anomalies": report["anomalies"],
        "paired_settled": report["paired_settled"],
        "ml_settled": ml["settled"],
        "ml_roi_pct": ml["roi_pct"],
        "ml_avg_clv_pct": ml["avg_clv_pct"],
        "spread_settled": spread["settled"],
        "spread_roi_pct": spread["roi_pct"],
        "spread_avg_clv_pct": spread["avg_clv_pct"],
        "spread_positive_clv_pct": spread["positive_clv_pct"],
        "spread_rescues": report["spread_rescues"],
        "spread_rescue_rate_pct": report["spread_rescue_rate_pct"],
        "gate_passes": int(report["spread_promotion_gate"]["passes"]),
    }
    fields = list(row)
    existing = load_csv(path)
    by_week = {existing_row.get("week_start") or "": existing_row for existing_row in existing}
    by_week[week_start] = {key: "" if value is None else str(value) for key, value in row.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(by_week[key] for key in sorted(by_week))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--ml-clv", default=str(DEFAULT_ML_CLV))
    parser.add_argument("--spread-clv", default=str(DEFAULT_SPREAD_CLV))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--text", default=str(DEFAULT_TEXT))
    parser.add_argument("--weekly-snapshot-csv", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(load_csv(Path(args.archive)), load_csv(Path(args.ml_clv)), load_csv(Path(args.spread_clv)))
    json_path, text_path = Path(args.json), Path(args.text)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    text_path.write_text(report_text(report), encoding="utf-8")
    if args.weekly_snapshot_csv:
        write_weekly_snapshot(Path(args.weekly_snapshot_csv), report)
    print(format_metric(report["ml"]))
    print(format_metric(report["spread"]))
    print(f"Weekly verdict: {report['weekly_review']['verdict']}")
    print(f"Spread gate: {'REVIEW CANDIDATE' if report['spread_promotion_gate']['passes'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
