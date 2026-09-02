#!/usr/bin/env python3
"""Build weekly/monthly diagnostics for the tennis props decision board.

This report tracks whether model/feed changes improve the live research lane:
matched rows, usable two-way prices, main-line candidates, bettable rows,
blockers, and settled shadow evidence. It does not create picks.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"
SHADOW_SIGNALS = PROPS_DIR / "shadow" / "aces-dfs-shadow-signals.csv"
DEFAULT_SUMMARY = PROPS_DIR / "model-monitor-summary.csv"
DEFAULT_REPORT = PROPS_DIR / "model-monitor-report.txt"
BREAK_CALIBRATION_MODE = "breaks_calibration_unfiltered"

SUMMARY_FIELDS = [
    "period_type",
    "period",
    "first_date",
    "last_date",
    "comparison_files",
    "line_rows",
    "matched_rows",
    "match_rate_pct",
    "two_way_rows",
    "one_sided_rows",
    "deep_alt_rows",
    "best_available_rows",
    "main_line_rows",
    "bettable_rows",
    "trackable_shadow_rows",
    "top_blocker",
    "avg_best_raw_edge_pct",
    "avg_best_novig_edge_pct",
    "shadow_signals",
    "shadow_settled",
    "shadow_pending",
    "shadow_void",
    "shadow_pnl_units",
    "shadow_roi_pct",
    "break_calibration_rows",
    "break_calibration_settled",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed else None


def fmt(value: float | None, digits: int = 2) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def parse_date(value: object) -> datetime | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return None


def row_date(row: dict[str, str]) -> str:
    return str(row.get("date") or "")[:10]


def period_key(value: str, period_type: str) -> str:
    parsed = parse_date(value)
    if parsed is None:
        return "unknown"
    if period_type == "day":
        return parsed.strftime("%Y-%m-%d")
    if period_type == "week":
        year, week, _weekday = parsed.isocalendar()
        return f"{year}-W{week:02d}"
    if period_type == "month":
        return parsed.strftime("%Y-%m")
    raise ValueError(f"Unsupported period type: {period_type}")


def first_blocker(row: dict[str, str]) -> str:
    raw = str(row.get("block_reasons") or row.get("blocked_reason") or "")
    return raw.split("|")[0] if raw else "none"


def best_edge(row: dict[str, str]) -> float | None:
    values = [parse_float(row.get("value_over_pct")), parse_float(row.get("value_under_pct"))]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def best_novig_edge(row: dict[str, str]) -> float | None:
    values = [parse_float(row.get("edge_over_novig_pct")), parse_float(row.get("edge_under_novig_pct"))]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def shadow_period_rows(rows: list[dict[str, str]], period_type: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        key = period_key(row_date(row), period_type)
        grouped.setdefault(key, []).append(row)
    return grouped


def shadow_stats(rows: list[dict[str, str]]) -> dict[str, str]:
    calibration = [row for row in rows if row.get("decision_mode") == BREAK_CALIBRATION_MODE]
    betting_rows = [row for row in rows if row.get("decision_mode") != BREAK_CALIBRATION_MODE]
    settled = [row for row in betting_rows if str(row.get("settlement_status") or "").lower() == "settled"]
    pending = [row for row in betting_rows if str(row.get("settlement_status") or "").lower() == "pending"]
    voided = [row for row in betting_rows if str(row.get("settlement_status") or "").lower() == "void"]
    pnl = sum(parse_float(row.get("pnl")) or 0.0 for row in settled)
    stake = len(settled)
    return {
        "shadow_signals": str(len(betting_rows)),
        "shadow_settled": str(len(settled)),
        "shadow_pending": str(len(pending)),
        "shadow_void": str(len(voided)),
        "shadow_pnl_units": fmt(pnl, 2),
        "shadow_roi_pct": fmt((pnl / stake * 100.0) if stake else 0.0, 1),
        "break_calibration_rows": str(len(calibration)),
        "break_calibration_settled": str(sum(str(row.get("settlement_status") or "").lower() == "settled" for row in calibration)),
    }


def summarize_rows(
    period_type: str,
    period: str,
    rows: list[dict[str, str]],
    files: set[str],
    shadow_rows: list[dict[str, str]],
) -> dict[str, str]:
    dates = sorted({row_date(row) for row in rows if row_date(row)})
    matched = [row for row in rows if row.get("matched_board") == "yes"]
    two_way = [row for row in rows if row.get("price_pair_status") == "two_way"]
    one_sided = [row for row in rows if row.get("line_quality") == "one_sided"]
    deep_alt = [row for row in rows if row.get("line_quality") == "deep_alt"]
    best_available = [row for row in rows if row.get("best_available_line") == "true"]
    main_line = [row for row in rows if row.get("main_line") == "true"]
    bettable = [row for row in rows if row.get("bettable") == "true"]
    trackable_shadow = [row for row in rows if row.get("trackable_shadow") == "true"]
    blockers = Counter(first_blocker(row) for row in rows if row.get("bettable") != "true")
    edge_values = [value for value in (best_edge(row) for row in best_available or main_line or matched) if value is not None]
    novig_values = [value for value in (best_novig_edge(row) for row in best_available or main_line or matched) if value is not None]
    out = {
        "period_type": period_type,
        "period": period,
        "first_date": dates[0] if dates else "",
        "last_date": dates[-1] if dates else "",
        "comparison_files": str(len(files)),
        "line_rows": str(len(rows)),
        "matched_rows": str(len(matched)),
        "match_rate_pct": fmt((len(matched) / len(rows) * 100.0) if rows else 0.0, 1),
        "two_way_rows": str(len(two_way)),
        "one_sided_rows": str(len(one_sided)),
        "deep_alt_rows": str(len(deep_alt)),
        "best_available_rows": str(len(best_available)),
        "main_line_rows": str(len(main_line)),
        "bettable_rows": str(len(bettable)),
        "trackable_shadow_rows": str(len(trackable_shadow)),
        "top_blocker": blockers.most_common(1)[0][0] if blockers else "none",
        "avg_best_raw_edge_pct": fmt(mean(edge_values), 1) if edge_values else "",
        "avg_best_novig_edge_pct": fmt(mean(novig_values), 1) if novig_values else "",
    }
    out.update(shadow_stats(shadow_rows))
    return out


def load_comparison_rows(start: str, end: str) -> list[tuple[Path, dict[str, str]]]:
    rows: list[tuple[Path, dict[str, str]]] = []
    for path in sorted(PROPS_DIR.glob("comparison-*.csv")):
        if path.name.endswith("-unmatched.csv"):
            continue
        for row in read_csv(path):
            if not (row.get("scope") == "match_total" or row.get("market") in {"match_aces", "match_double_faults"}):
                continue
            date_text = row_date(row)
            if start and date_text and date_text < start:
                continue
            if end and date_text and date_text > end:
                continue
            rows.append((path, row))
    return rows


def build_summary(start: str, end: str) -> list[dict[str, str]]:
    comparison_rows = load_comparison_rows(start, end)
    shadow_rows = [
        row for row in read_csv(SHADOW_SIGNALS)
        if (not start or row_date(row) >= start) and (not end or row_date(row) <= end)
    ]
    summary: list[dict[str, str]] = []
    for period_type in ("day", "week", "month"):
        grouped: dict[str, list[tuple[Path, dict[str, str]]]] = {}
        for item in comparison_rows:
            _path, row = item
            grouped.setdefault(period_key(row_date(row), period_type), []).append(item)
        shadow_grouped = shadow_period_rows(shadow_rows, period_type)
        for period in sorted(set(grouped) | set(shadow_grouped)):
            items = grouped.get(period, [])
            rows = [row for _path, row in items]
            files = {str(path.relative_to(ROOT)) for path, _row in items}
            summary.append(summarize_rows(period_type, period, rows, files, shadow_grouped.get(period, [])))
    return summary


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    latest_day = [row for row in rows if row["period_type"] == "day"]
    latest_week = [row for row in rows if row["period_type"] == "week"]
    latest_month = [row for row in rows if row["period_type"] == "month"]

    def line(row: dict[str, str]) -> str:
        return (
            f"{row['period_type']} {row['period']}: rows={row['line_rows']} matched={row['matched_rows']} "
            f"two_way={row['two_way_rows']} best_available={row['best_available_rows']} "
            f"main={row['main_line_rows']} bettable={row['bettable_rows']} "
            f"shadow_candidates={row['trackable_shadow_rows']} "
            f"top_blocker={row['top_blocker']} shadow_settled={row['shadow_settled']} "
            f"pnl={row['shadow_pnl_units']}u roi={row['shadow_roi_pct']}% "
            f"break_calibration={row['break_calibration_settled']}/{row['break_calibration_rows']}"
        )

    report = [
        "Tennis props model monitor report",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Purpose: track feed quality, decision gates, and settled shadow evidence over time.",
        "Status: research/decision support only; no automatic staking.",
        "",
        "Latest day:",
        line(latest_day[-1]) if latest_day else "no day rows",
        "",
        "Latest week:",
        line(latest_week[-1]) if latest_week else "no week rows",
        "",
        "Latest month:",
        line(latest_month[-1]) if latest_month else "no month rows",
        "",
        "Interpretation:",
        "- bettable_rows is the only count that can become a recommendation candidate.",
        "- trackable_shadow_rows are prospective over-only observations, never public recommendations.",
        "- two_way_rows shows whether odds-api is giving both sides of a line.",
        "- best_available_rows shows the closest ladder row even when it is still blocked.",
        "- main_line_rows should rise only if the feed contains clean, fairly balanced two-way lines.",
        "- shadow ROI is not meaningful until the settled sample is large enough.",
        "- break calibration rows test counts only and never enter shadow ROI or CLV.",
    ]
    path.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build tennis props weekly/monthly model diagnostics")
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    rows = build_summary(args.start, args.end)
    write_csv(Path(args.summary), rows)
    write_report(Path(args.report), rows)
    print(f"Wrote {args.summary} ({len(rows)} rows)")
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
