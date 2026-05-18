#!/usr/bin/env python3
"""Evaluate Grand Slam ML segments from historical backtest rows.

This is research-only evidence. It does not write live signals, alter policy
rules, or approve any new lane.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"
DEFAULT_OUT = BACKTEST_DIR / "grand-slam-eval-2022-2025.txt"
DEFAULT_JSON_OUT = BACKTEST_DIR / "grand-slam-eval-2022-2025.json"


EVENTS = [
    {"key": "hard_grand_slam_aggregate", "label": "Hard Grand Slam aggregate", "surface": "Hard", "tournament": None},
    {"key": "australian_open", "label": "Australian Open", "surface": "Hard", "tournament": "Australian Open"},
    {"key": "us_open", "label": "US Open", "surface": "Hard", "tournament": "US Open"},
    {"key": "roland_garros", "label": "Roland Garros", "surface": "Clay", "tournament": "French Open"},
    {"key": "wimbledon", "label": "Wimbledon", "surface": "Grass", "tournament": "Wimbledon"},
]

CONFIDENCE_SCOPE = {"high", "medium"}
MIN_VALUE_PCT = 5.0
PROMOTION_MIN_BETS = 150
PROMOTION_MIN_TIER_ROI_PCT = 5.0
PROMOTION_MIN_POSITIVE_YEARS = 3


@dataclass
class Summary:
    bets: int = 0
    wins: int = 0
    losses: int = 0
    avg_value_pct: float = 0.0
    flat_pnl_units: float = 0.0
    flat_roi_pct: float = 0.0
    tier_staked_units: float = 0.0
    tier_pnl_units: float = 0.0
    tier_roi_pct: float = 0.0


def _units_for_value_pct(value_pct: float) -> float:
    if value_pct >= 20.0:
        return 2.0
    if value_pct >= 15.0:
        return 1.5
    if value_pct >= 10.0:
        return 1.0
    return 0.5


def _float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def _selected_odds(row: dict[str, str]) -> float | None:
    side = (row.get("bet_side") or "").strip().lower()
    if side == "winner":
        return _float(row.get("pinnacle_odds"))
    if side == "loser":
        return _float(row.get("pinnacle_odds_loser"))
    return None


def _load_rows(years: Iterable[int]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for year in years:
        path = BACKTEST_DIR / f"backtest-results-{year}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing backtest file: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows.extend(dict(row) for row in csv.DictReader(handle))
    return rows


def _event_rows(rows: Iterable[dict[str, str]], event: dict[str, str | None]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        if (row.get("series") or "").strip() != "Grand Slam":
            continue
        if (row.get("surface") or "").strip() != event["surface"]:
            continue
        if event["tournament"] and (row.get("tournament") or "").strip() != event["tournament"]:
            continue
        out.append(row)
    return out


def _candidate_rows(
    rows: Iterable[dict[str, str]],
    *,
    confidences: set[str] = CONFIDENCE_SCOPE,
    min_value_pct: float = MIN_VALUE_PCT,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        if _is_truthy(row.get("policy_excluded")):
            continue
        if (row.get("confidence") or "").strip().lower() not in confidences:
            continue
        value_pct = _float(row.get("value_pct"))
        if value_pct is None or value_pct < min_value_pct:
            continue
        if (row.get("bet_result") or "").strip().lower() not in {"win", "loss"}:
            continue
        odds = _selected_odds(row)
        if odds is None or odds <= 1.0:
            continue
        out.append(row)
    return out


def _summarise(rows: Iterable[dict[str, str]]) -> Summary:
    rows = list(rows)
    if not rows:
        return Summary()
    wins = losses = 0
    value_sum = 0.0
    flat_pnl = 0.0
    tier_pnl = 0.0
    tier_staked = 0.0
    for row in rows:
        value_pct = _float(row.get("value_pct")) or 0.0
        odds = _selected_odds(row)
        if odds is None:
            continue
        won = (row.get("bet_result") or "").strip().lower() == "win"
        wins += 1 if won else 0
        losses += 0 if won else 1
        value_sum += value_pct
        stake = _units_for_value_pct(value_pct)
        flat_pnl += odds - 1.0 if won else -1.0
        tier_pnl += stake * (odds - 1.0) if won else -stake
        tier_staked += stake
    bets = wins + losses
    return Summary(
        bets=bets,
        wins=wins,
        losses=losses,
        avg_value_pct=value_sum / bets if bets else 0.0,
        flat_pnl_units=flat_pnl,
        flat_roi_pct=(flat_pnl / bets * 100.0) if bets else 0.0,
        tier_staked_units=tier_staked,
        tier_pnl_units=tier_pnl,
        tier_roi_pct=(tier_pnl / tier_staked * 100.0) if tier_staked else 0.0,
    )


def _status(summary: Summary, yearly: list[dict[str, float | int | str | None]]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    positive_years = sum(1 for row in yearly if (row.get("tier_roi_pct") or 0.0) > 0)
    latest = yearly[-1] if yearly else None
    latest_roi = latest.get("tier_roi_pct") if latest else None
    if summary.bets < PROMOTION_MIN_BETS:
        reasons.append(f"sample {summary.bets} < {PROMOTION_MIN_BETS}")
    if summary.tier_roi_pct < PROMOTION_MIN_TIER_ROI_PCT:
        reasons.append(f"tier ROI {summary.tier_roi_pct:+.2f}% < +{PROMOTION_MIN_TIER_ROI_PCT:.0f}%")
    if positive_years < PROMOTION_MIN_POSITIVE_YEARS:
        reasons.append(f"positive years {positive_years} < {PROMOTION_MIN_POSITIVE_YEARS}")
    if latest_roi is None or latest_roi < 0:
        reasons.append(f"latest year ROI {latest_roi:+.2f}%" if latest_roi is not None else "latest year missing")
    if not reasons:
        return "PASS", ["meets research promotion evidence gate"]
    if summary.tier_roi_pct > 0 and summary.bets >= 80:
        return "WATCH", reasons
    return "FAIL", reasons


def _row_for_event(rows: list[dict[str, str]], event: dict[str, str | None], years: list[int]) -> dict:
    event_rows = _event_rows(rows, event)
    candidates = _candidate_rows(event_rows)
    summary = _summarise(candidates)
    yearly = []
    for year in years:
        year_rows = [row for row in candidates if (row.get("date") or "")[:4] == str(year)]
        year_summary = _summarise(year_rows)
        yearly.append({"year": str(year), **asdict(year_summary)})
    status, reasons = _status(summary, yearly)
    confidence_breakdown = {
        conf: asdict(_summarise(_candidate_rows(event_rows, confidences={conf}, min_value_pct=MIN_VALUE_PCT)))
        for conf in ["high", "medium"]
    }
    threshold_breakdown = [
        {"min_value_pct": threshold, **asdict(_summarise(_candidate_rows(event_rows, min_value_pct=threshold)))}
        for threshold in [5.0, 10.0, 15.0, 20.0]
    ]
    return {
        "key": event["key"],
        "label": event["label"],
        "surface": event["surface"],
        "tournament": event["tournament"] or "Hard Grand Slam aggregate",
        "candidate_definition": "Grand Slam, confidence high+medium, value_pct >= 5, policy_excluded=false, settled win/loss, valid selected Pinnacle odds",
        **asdict(summary),
        "status": status,
        "status_reasons": reasons,
        "yearly": yearly,
        "confidence_breakdown": confidence_breakdown,
        "threshold_breakdown": threshold_breakdown,
    }


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%"


def _write_text(report: dict, path: Path) -> None:
    lines = [
        "Grand Slam ML Evidence Report",
        f"Generated UTC: {report['generated_at_utc']}",
        f"Years: {', '.join(str(year) for year in report['years'])}",
        "",
        "Scope: research-only evidence. No live signal, public output, production flag, or policy rule is changed by this report.",
        "Candidate definition: Grand Slam rows with confidence high+medium, value_pct >= 5, policy_excluded=false, settled win/loss, and valid selected Pinnacle odds.",
        "Staking: value_tiered (5-10=0.5u, 10-15=1u, 15-20=1.5u, 20+=2u), matching policy-profile-backtest.",
        "",
        "Promotion evidence gate:",
        f"- bets >= {PROMOTION_MIN_BETS}",
        f"- tier ROI >= +{PROMOTION_MIN_TIER_ROI_PCT:.0f}%",
        f"- positive years >= {PROMOTION_MIN_POSITIVE_YEARS}",
        "- latest year tier ROI >= 0%",
        "",
        "Primary event table:",
        "event | status | bets | W-L | avg value | flat ROI | tier ROI | tier P/L | yearly tier ROI | reasons",
    ]
    for row in report["rows"]:
        yearly = ", ".join(f"{item['year']}:{_fmt_pct(item['tier_roi_pct'])}" for item in row["yearly"])
        lines.append(
            " | ".join(
                [
                    row["label"],
                    row["status"],
                    str(row["bets"]),
                    f"{row['wins']}-{row['losses']}",
                    f"{row['avg_value_pct']:.2f}%",
                    _fmt_pct(row["flat_roi_pct"]),
                    _fmt_pct(row["tier_roi_pct"]),
                    f"{row['tier_pnl_units']:+.2f}u on {row['tier_staked_units']:.2f}u",
                    yearly,
                    "; ".join(row["status_reasons"]),
                ]
            )
        )
    lines.extend(["", "Confidence diagnostics (min value 5):"])
    for row in report["rows"]:
        lines.append(f"[{row['label']}]")
        for confidence, summary in row["confidence_breakdown"].items():
            lines.append(
                f"  {confidence}: bets={summary['bets']} W-L={summary['wins']}-{summary['losses']} "
                f"tierROI={_fmt_pct(summary['tier_roi_pct'])} P/L={summary['tier_pnl_units']:+.2f}u on {summary['tier_staked_units']:.2f}u"
            )
    lines.extend(["", "Threshold diagnostics (high+medium):"])
    for row in report["rows"]:
        lines.append(f"[{row['label']}]")
        for summary in row["threshold_breakdown"]:
            lines.append(
                f"  value>={summary['min_value_pct']:.0f}: bets={summary['bets']} W-L={summary['wins']}-{summary['losses']} "
                f"tierROI={_fmt_pct(summary['tier_roi_pct'])} P/L={summary['tier_pnl_units']:+.2f}u on {summary['tier_staked_units']:.2f}u"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    years = sorted(args.years)
    rows = _load_rows(years)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "years": years,
        "source_files": [str(BACKTEST_DIR / f"backtest-results-{year}.csv") for year in years],
        "criteria": {
            "min_bets": PROMOTION_MIN_BETS,
            "min_tier_roi_pct": PROMOTION_MIN_TIER_ROI_PCT,
            "min_positive_years": PROMOTION_MIN_POSITIVE_YEARS,
            "latest_year_tier_roi_min_pct": 0.0,
        },
        "rows": [_row_for_event(rows, event, years) for event in EVENTS],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    _write_text(report, args.out)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    print(f"Wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
