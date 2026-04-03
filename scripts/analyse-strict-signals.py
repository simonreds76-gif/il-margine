#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from signal_storage import STRICT_SIGNAL_PATHS


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = STRICT_SIGNAL_PATHS.archive
DEFAULT_REPORT_TXT = ROOT / "data" / "backtest" / "strict-signals-weekly.txt"
DEFAULT_SUMMARY_CSV = ROOT / "data" / "backtest" / "strict-signals-weekly.csv"


@dataclass
class SignalRow:
    signal_date: date
    series: str
    confidence: str
    value_pct: float | None


def parse_iso_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    txt = str(raw).strip()
    if not txt:
        return None
    try:
        return date.fromisoformat(txt[:10])
    except ValueError:
        return None


def parse_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    txt = str(raw).strip()
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def load_signal_rows(path: Path) -> list[SignalRow]:
    rows: list[SignalRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            d = parse_iso_date(r.get("date"))
            if d is None:
                continue
            series = (r.get("series") or "N/A").strip() or "N/A"
            confidence = (r.get("confidence") or "n/a").strip().lower() or "n/a"
            value_pct = parse_float(r.get("value_pct"))
            rows.append(
                SignalRow(
                    signal_date=d,
                    series=series,
                    confidence=confidence,
                    value_pct=value_pct,
                )
            )
    return rows


def value_metrics(rows: list[SignalRow]) -> tuple[float | None, float | None, float | None]:
    vals = [r.value_pct for r in rows if r.value_pct is not None]
    if not vals:
        return None, None, None
    return sum(vals) / len(vals), min(vals), max(vals)


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v:.2f}%"


def fmt_counter(c: Counter[str]) -> str:
    if not c:
        return "none"
    parts = [f"{k}={v}" for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]
    return ", ".join(parts)


def load_last_as_of(summary_csv: Path) -> date | None:
    if not summary_csv.exists():
        return None
    last_row: dict[str, str] | None = None
    with summary_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            last_row = row
    if not last_row:
        return None
    return parse_iso_date(last_row.get("as_of_date"))


def append_summary_csv(
    summary_csv: Path,
    generated_utc: str,
    as_of: date,
    window_days: int,
    window_start: date,
    window_rows: list[SignalRow],
    total_rows: list[SignalRow],
    since_prev_start: date | None,
    since_prev_rows: list[SignalRow] | None,
) -> None:
    summary_csv.parent.mkdir(parents=True, exist_ok=True)

    w_avg, w_min, w_max = value_metrics(window_rows)
    s_avg, s_min, s_max = value_metrics(since_prev_rows or [])
    w_series = Counter(r.series for r in window_rows)
    w_conf = Counter(r.confidence for r in window_rows)

    fieldnames = [
        "generated_utc",
        "as_of_date",
        "window_days",
        "window_start",
        "window_end",
        "total_count",
        "window_count",
        "window_avg_value_pct",
        "window_min_value_pct",
        "window_max_value_pct",
        "window_series_breakdown",
        "window_confidence_breakdown",
        "since_prev_start",
        "since_prev_end",
        "since_prev_count",
        "since_prev_avg_value_pct",
        "since_prev_min_value_pct",
        "since_prev_max_value_pct",
    ]

    write_header = not summary_csv.exists()
    with summary_csv.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "generated_utc": generated_utc,
                "as_of_date": as_of.isoformat(),
                "window_days": str(window_days),
                "window_start": window_start.isoformat(),
                "window_end": as_of.isoformat(),
                "total_count": str(len(total_rows)),
                "window_count": str(len(window_rows)),
                "window_avg_value_pct": "" if w_avg is None else f"{w_avg:.4f}",
                "window_min_value_pct": "" if w_min is None else f"{w_min:.4f}",
                "window_max_value_pct": "" if w_max is None else f"{w_max:.4f}",
                "window_series_breakdown": fmt_counter(w_series),
                "window_confidence_breakdown": fmt_counter(w_conf),
                "since_prev_start": since_prev_start.isoformat() if since_prev_start else "",
                "since_prev_end": as_of.isoformat() if since_prev_start else "",
                "since_prev_count": "" if since_prev_rows is None else str(len(since_prev_rows)),
                "since_prev_avg_value_pct": "" if s_avg is None else f"{s_avg:.4f}",
                "since_prev_min_value_pct": "" if s_min is None else f"{s_min:.4f}",
                "since_prev_max_value_pct": "" if s_max is None else f"{s_max:.4f}",
            }
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly analysis for strict POLICY signals CSV.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input strict-signals CSV path.")
    parser.add_argument("--report-txt", default=str(DEFAULT_REPORT_TXT), help="Output text report path.")
    parser.add_argument("--summary-csv", default=str(DEFAULT_SUMMARY_CSV), help="Append-only summary CSV path.")
    parser.add_argument("--days", type=int, default=7, help="Window size in days (default: 7).")
    parser.add_argument("--as-of", default="", help="As-of date YYYY-MM-DD. Default: latest date in input file.")
    args = parser.parse_args()

    input_path = Path(args.input)
    report_txt = Path(args.report_txt)
    summary_csv = Path(args.summary_csv)
    window_days = max(1, int(args.days))

    generated_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if not input_path.exists():
        msg = f"Strict signals analysis: input not found: {input_path}"
        print(msg)
        report_txt.parent.mkdir(parents=True, exist_ok=True)
        report_txt.write_text(msg + "\n", encoding="utf-8")
        return 0

    rows = load_signal_rows(input_path)
    if not rows:
        msg = f"Strict signals analysis: no valid rows found in {input_path}"
        print(msg)
        report_txt.parent.mkdir(parents=True, exist_ok=True)
        report_txt.write_text(msg + "\n", encoding="utf-8")
        return 0

    max_date = max(r.signal_date for r in rows)
    as_of = parse_iso_date(args.as_of) if args.as_of else max_date
    if as_of is None:
        print(f"Invalid --as-of date: {args.as_of}")
        return 1

    window_start = as_of - timedelta(days=window_days - 1)
    window_rows = [r for r in rows if window_start <= r.signal_date <= as_of]

    total_series = Counter(r.series for r in rows)
    total_conf = Counter(r.confidence for r in rows)

    window_series = Counter(r.series for r in window_rows)
    window_conf = Counter(r.confidence for r in window_rows)

    w_avg, w_min, w_max = value_metrics(window_rows)
    t_avg, t_min, t_max = value_metrics(rows)

    prev_as_of = load_last_as_of(summary_csv)
    since_prev_start: date | None = None
    since_prev_rows: list[SignalRow] | None = None
    s_avg = s_min = s_max = None
    if prev_as_of and prev_as_of < as_of:
        since_prev_start = prev_as_of + timedelta(days=1)
        since_prev_rows = [r for r in rows if since_prev_start <= r.signal_date <= as_of]
        s_avg, s_min, s_max = value_metrics(since_prev_rows)

    lines = [
        "Strict Signals Weekly Analysis",
        f"Generated UTC: {generated_utc}",
        f"Input file: {input_path}",
        "",
        f"As-of date: {as_of.isoformat()}",
        f"Window ({window_days}d): {window_start.isoformat()} -> {as_of.isoformat()}",
        "",
        f"Signals in window: {len(window_rows)}",
        f"Total signals in file: {len(rows)}",
        "",
        "Window breakdown",
        f"  Series: {fmt_counter(window_series)}",
        f"  Confidence: {fmt_counter(window_conf)}",
        f"  Value pct: avg {fmt_pct(w_avg)}, min {fmt_pct(w_min)}, max {fmt_pct(w_max)}",
        "",
        "All-time breakdown",
        f"  Series: {fmt_counter(total_series)}",
        f"  Confidence: {fmt_counter(total_conf)}",
        f"  Value pct: avg {fmt_pct(t_avg)}, min {fmt_pct(t_min)}, max {fmt_pct(t_max)}",
    ]

    if since_prev_rows is None:
        lines.extend(
            [
                "",
                "Since previous summary run: n/a (no previous summary row found)",
            ]
        )
    else:
        lines.extend(
            [
                "",
                f"Since previous summary run: {since_prev_start.isoformat()} -> {as_of.isoformat()}",
                f"  Signals: {len(since_prev_rows)}",
                f"  Value pct: avg {fmt_pct(s_avg)}, min {fmt_pct(s_min)}, max {fmt_pct(s_max)}",
            ]
        )

    report_text = "\n".join(lines) + "\n"
    print(report_text)

    report_txt.parent.mkdir(parents=True, exist_ok=True)
    report_txt.write_text(report_text, encoding="utf-8")

    append_summary_csv(
        summary_csv=summary_csv,
        generated_utc=generated_utc,
        as_of=as_of,
        window_days=window_days,
        window_start=window_start,
        window_rows=window_rows,
        total_rows=rows,
        since_prev_start=since_prev_start,
        since_prev_rows=since_prev_rows,
    )

    print(f"Wrote report: {report_txt}")
    print(f"Appended summary CSV: {summary_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
