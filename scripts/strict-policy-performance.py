#!/usr/bin/env python3
"""
Weekly settled-performance report for strict policy signals.

Purpose:
- Compare `base` vs `overlay` policy outcomes using settled rows.
- Use `strict-signals-overlay-compare.csv` when available (preferred).
- If settlement fields are missing on compare rows, backfill from
  `strict-signals.csv` by signal key.

Outputs:
- Text report (stdout + file)
- Append-only summary CSV (unless --dry-run)

Usage:
  python scripts/strict-policy-performance.py
  python scripts/strict-policy-performance.py --days 7
  python scripts/strict-policy-performance.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from signal_storage import STRICT_SIGNAL_PATHS


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"
DEFAULT_SIGNALS = STRICT_SIGNAL_PATHS.archive
DEFAULT_COMPARE = DATA_DIR / "strict-signals-overlay-compare.csv"
DEFAULT_REPORT_TXT = DATA_DIR / "strict-policy-performance-weekly.txt"
DEFAULT_SUMMARY_CSV = DATA_DIR / "strict-policy-performance-weekly.csv"
CLEAN_EVAL_START = date(2026, 3, 14)

KEY_FIELDS = ["date", "player1", "player2", "surface", "series", "confidence", "side", "bet_type", "spread_line"]
LANE_FIELDS = ["date", "player1", "player2", "bet_type", "spread_line", "signal_profile"]
BET_TYPE_ML = "ml"
BET_TYPE_HANDICAP = "handicap"
LEAGUE_SCOPES = ["combined", "ATP", "Challenger"]

SETTLEMENT_FIELDS = [
    "settlement_status",
    "result",
    "bet_outcome",
    "won_bet",
    "match_date",
    "player1_id",
    "player2_id",
    "winner_id",
    "loser_id",
    "settled_at",
    "settlement_note",
    "closing_odds1",
    "closing_odds2",
    "closing_source",
]

STAKE_FIELDS = [
    "stake_units",
    "stake_gbp",
    "stake_model",
]


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


def parse_stake_units(raw: str | None, default: float = 1.0) -> float:
    v = parse_float(raw)
    if v is None or v <= 0:
        return default
    return v


def norm_key_val(v: str | None) -> str:
    return (v or "").strip().lower()


def row_key_val(row: dict[str, str], field: str) -> str:
    if field == "policy_mode":
        return norm_key_val(row.get(field) or "base")
    if field == "bet_type":
        return norm_key_val(row.get(field) or "match")
    return norm_key_val(row.get(field))


def row_key(row: dict[str, str], include_mode: bool = True) -> tuple[str, ...]:
    out = [row_key_val(row, f) for f in KEY_FIELDS]
    if include_mode:
        out.append(row_key_val(row, "policy_mode"))
    return tuple(out)


def lane_key(row: dict[str, str], include_mode: bool = True) -> tuple[str, ...]:
    out = [row_key_val(row, f) for f in LANE_FIELDS]
    if include_mode:
        out.append(row_key_val(row, "policy_mode"))
    return tuple(out)


def lookup_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row_key_val(row, f) for f in KEY_FIELDS)


def is_settled(row: dict[str, str]) -> bool:
    return norm_key_val(row.get("settlement_status")) == "settled"


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        return [dict(r) for r in rd]


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for r in rows:
        k = lane_key(r, include_mode=True)
        prev = by_key.get(k)
        if prev is None:
            by_key[k] = r
            continue
        # Prefer settled rows; otherwise keep the latest row seen in file order.
        if is_settled(prev) and not is_settled(r):
            continue
        by_key[k] = r
    return list(by_key.values())


def build_settlement_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, ...], dict[str, str]]:
    out: dict[tuple[str, ...], dict[str, str]] = {}
    for r in rows:
        k = lookup_key(r)
        if not any(k):
            continue
        prev = out.get(k)
        if prev is None:
            out[k] = r
            continue
        if is_settled(prev) and not is_settled(r):
            continue
        out[k] = r
    return out


def attach_settlement(compare_rows: list[dict[str, str]], settlement_lookup: dict[tuple[str, ...], dict[str, str]]) -> tuple[int, int]:
    patched = 0
    patched_settled = 0
    for r in compare_rows:
        src = settlement_lookup.get(lookup_key(r))
        if src is None:
            continue
        wrote_any = False
        for f in [*SETTLEMENT_FIELDS, *STAKE_FIELDS]:
            if not norm_key_val(r.get(f)) and norm_key_val(src.get(f)):
                r[f] = src.get(f) or ""
                wrote_any = True
        if wrote_any:
            patched += 1
            if is_settled(r):
                patched_settled += 1
    return patched, patched_settled


@dataclass
class ModeSummary:
    mode: str
    signals: int
    settled: int
    unsettled: int
    wins: int
    losses: int
    invalid_odds: int
    staked_units: float
    pnl_units: float
    roi_pct: float | None
    win_rate_pct: float | None
    avg_value_pct: float | None
    avg_pin_odds: float | None


def _bet_type_for_row(row: dict[str, str]) -> str:
    """Classify row as ML (match winner) or handicap (spread)."""
    bt = norm_key_val(row.get("bet_type") or "match")
    side = norm_key_val(row.get("side"))
    if bt == "spread" or side in {"p1+", "p2-"}:
        return BET_TYPE_HANDICAP
    return BET_TYPE_ML


def _summarize_mode_subset(
    rows: list[dict[str, str]],
    mode: str,
    bet_type: str,
) -> ModeSummary:
    """Summarize a subset of rows by mode and bet_type (ml or handicap)."""
    sel = [
        r
        for r in rows
        if norm_key_val(r.get("policy_mode") or "base") == mode
        and _bet_type_for_row(r) == bet_type
    ]
    settled_rows = [r for r in sel if is_settled(r)]

    wins = 0
    losses = 0
    invalid_odds = 0
    staked = 0.0
    pnl = 0.0
    odds_vals: list[float] = []
    value_vals: list[float] = []

    for r in sel:
        v = parse_float(r.get("value_pct"))
        if v is not None:
            value_vals.append(v)

    for r in settled_rows:
        side = norm_key_val(r.get("side"))
        outcome = norm_key_val(r.get("bet_outcome"))
        if outcome not in {"win", "loss"}:
            continue
        # ML: side in P1/P2, pin_odds1/pin_odds2
        # Handicap: side in P1+/P2-, spread_odds
        if bet_type == BET_TYPE_ML:
            if side not in {"p1", "p2"}:
                continue
            odds = parse_float(r.get("pin_odds1") if side == "p1" else r.get("pin_odds2"))
        else:
            if side not in {"p1+", "p2-"}:
                continue
            odds = parse_float(r.get("spread_odds"))
        if odds is None or odds <= 1.0:
            invalid_odds += 1
            continue
        stake_units = parse_stake_units(r.get("stake_units"), default=1.0)
        staked += stake_units
        odds_vals.append(odds)
        if outcome == "win":
            wins += 1
            pnl += stake_units * (odds - 1.0)
        else:
            losses += 1
            pnl -= stake_units

    roi = (pnl / staked * 100.0) if staked > 0 else None
    wr = (wins / (wins + losses) * 100.0) if (wins + losses) > 0 else None
    avg_value = (sum(value_vals) / len(value_vals)) if value_vals else None
    avg_odds = (sum(odds_vals) / len(odds_vals)) if odds_vals else None

    return ModeSummary(
        mode=mode,
        signals=len(sel),
        settled=len(settled_rows),
        unsettled=len(sel) - len(settled_rows),
        wins=wins,
        losses=losses,
        invalid_odds=invalid_odds,
        staked_units=staked,
        pnl_units=pnl,
        roi_pct=roi,
        win_rate_pct=wr,
        avg_value_pct=avg_value,
        avg_pin_odds=avg_odds,
    )


def summarize_mode(rows: list[dict[str, str]], mode: str) -> ModeSummary:
    """Combined ML + handicap summary (legacy)."""
    ml = _summarize_mode_subset(rows, mode, BET_TYPE_ML)
    hc = _summarize_mode_subset(rows, mode, BET_TYPE_HANDICAP)
    return ModeSummary(
        mode=mode,
        signals=ml.signals + hc.signals,
        settled=ml.settled + hc.settled,
        unsettled=ml.unsettled + hc.unsettled,
        wins=ml.wins + hc.wins,
        losses=ml.losses + hc.losses,
        invalid_odds=ml.invalid_odds + hc.invalid_odds,
        staked_units=ml.staked_units + hc.staked_units,
        pnl_units=ml.pnl_units + hc.pnl_units,
        roi_pct=(ml.pnl_units + hc.pnl_units) / (ml.staked_units + hc.staked_units) * 100.0
        if (ml.staked_units + hc.staked_units) > 0
        else None,
        win_rate_pct=(
            (ml.wins + hc.wins) / (ml.wins + ml.losses + hc.wins + hc.losses) * 100.0
            if (ml.wins + ml.losses + hc.wins + hc.losses) > 0
            else None
        ),
        avg_value_pct=ml.avg_value_pct if ml.avg_value_pct is not None else hc.avg_value_pct,
        avg_pin_odds=ml.avg_pin_odds if ml.avg_pin_odds is not None else hc.avg_pin_odds,
    )


def summarize_mode_by_bet_type(
    rows: list[dict[str, str]], mode: str
) -> dict[str, ModeSummary]:
    """Return separate ML and handicap summaries for settlement ROI and backlog."""
    return {
        BET_TYPE_ML: _summarize_mode_subset(rows, mode, BET_TYPE_ML),
        BET_TYPE_HANDICAP: _summarize_mode_subset(rows, mode, BET_TYPE_HANDICAP),
    }


def filter_rows_by_league(rows: list[dict[str, str]], league_scope: str) -> list[dict[str, str]]:
    if league_scope == "combined":
        return rows
    target = norm_key_val(league_scope)
    return [r for r in rows if norm_key_val(r.get("league")) == target]


def fmt_num(v: float | None, digits: int = 2, suffix: str = "") -> str:
    if v is None:
        return "n/a"
    return f"{v:.{digits}f}{suffix}"


def as_summary_row(
    generated_utc: str,
    as_of: date,
    scope: str,
    window_days: int,
    mode_summary: ModeSummary,
    source: str,
    bet_type: str = "",
    eval_period: str = "overall",
    league_scope: str = "combined",
) -> dict[str, str]:
    row = {
        "generated_utc": generated_utc,
        "as_of_date": as_of.isoformat(),
        "scope": scope,
        "eval_period": eval_period,
        "league_scope": league_scope,
        "window_days": str(window_days),
        "source_file": source,
        "policy_mode": mode_summary.mode,
        "bet_type": bet_type,
        "signals": str(mode_summary.signals),
        "settled": str(mode_summary.settled),
        "unsettled": str(mode_summary.unsettled),
        "wins": str(mode_summary.wins),
        "losses": str(mode_summary.losses),
        "invalid_odds": str(mode_summary.invalid_odds),
        "staked_units": f"{mode_summary.staked_units:.4f}",
        "pnl_units": f"{mode_summary.pnl_units:.4f}",
        "roi_pct": "" if mode_summary.roi_pct is None else f"{mode_summary.roi_pct:.4f}",
        "win_rate_pct": "" if mode_summary.win_rate_pct is None else f"{mode_summary.win_rate_pct:.4f}",
        "avg_value_pct": "" if mode_summary.avg_value_pct is None else f"{mode_summary.avg_value_pct:.4f}",
        "avg_pin_odds": "" if mode_summary.avg_pin_odds is None else f"{mode_summary.avg_pin_odds:.4f}",
    }
    return row


def append_summary(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows: list[dict[str, str]] = []
    fields = list(rows[0].keys())
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as f:
            rd = csv.DictReader(f)
            existing_fields = list(rd.fieldnames or [])
            existing_rows = [dict(r) for r in rd]
        for field in existing_fields:
            if field not in fields:
                fields.append(field)
    for row in existing_rows:
        for field in row.keys():
            if field not in fields:
                fields.append(field)
    normalized_existing = [{field: row.get(field, "") for field in fields} for row in existing_rows]
    normalized_new = [{field: row.get(field, "") for field in fields} for row in rows]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields)
        wr.writeheader()
        wr.writerows(normalized_existing)
        wr.writerows(normalized_new)
    tmp.replace(path)


def filter_window(rows: list[dict[str, str]], start: date, end: date) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for r in rows:
        d = parse_iso_date(r.get("date"))
        if d is None:
            continue
        if start <= d <= end:
            out.append(r)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare settled base vs overlay policy performance.")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS), help="Path to strict-signals.csv")
    parser.add_argument(
        "--compare",
        default="",
        help="Path to strict-signals-overlay-compare.csv (defaults only for main strict-signals.csv runs)",
    )
    parser.add_argument("--report-txt", default=str(DEFAULT_REPORT_TXT), help="Output text report")
    parser.add_argument("--summary-csv", default=str(DEFAULT_SUMMARY_CSV), help="Append-only summary CSV")
    parser.add_argument("--days", type=int, default=7, help="Window size in days (default: 7)")
    parser.add_argument("--as-of", default="", help="As-of date YYYY-MM-DD (default: max date in source)")
    parser.add_argument("--dry-run", action="store_true", help="Print report only, do not write files")
    args = parser.parse_args()

    signals_path = Path(args.signals)
    compare_path = Path(args.compare) if args.compare else (DEFAULT_COMPARE if signals_path == DEFAULT_SIGNALS else None)
    report_path = Path(args.report_txt)
    summary_path = Path(args.summary_csv)
    window_days = max(1, int(args.days))
    generated_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if not signals_path.exists():
        print(f"Signals file missing: {signals_path}")
        return 0

    signal_rows = dedupe_rows(load_csv_rows(signals_path))
    if not signal_rows:
        print(f"No rows in signals file: {signals_path}")
        # Header-only CSV (e.g. spread_shadow before first 20%+ handicap) — write zero stub so
        # model monitor / Vercel have a valid weekly CSV instead of missing file + settle errors.
        if args.dry_run:
            return 0
        as_of_stub = date.today()
        source_name = f"{signals_path.name}+{compare_path.name}" if compare_path and compare_path.exists() else signals_path.name
        z = summarize_mode([], "base")
        z_ml = _summarize_mode_subset([], "base", BET_TYPE_ML)
        z_hc = _summarize_mode_subset([], "base", BET_TYPE_HANDICAP)
        stub_rows = [
            as_summary_row(generated_utc, as_of_stub, "window", window_days, z, source_name, "", "overall"),
            as_summary_row(generated_utc, as_of_stub, "all_time", window_days, z, source_name, "", "overall"),
            as_summary_row(generated_utc, as_of_stub, "all_time", window_days, z, source_name, "", "clean"),
            as_summary_row(generated_utc, as_of_stub, "window", window_days, z, source_name, "", "clean"),
            as_summary_row(generated_utc, as_of_stub, "all_time", window_days, z_ml, source_name, BET_TYPE_ML, "overall"),
            as_summary_row(generated_utc, as_of_stub, "all_time", window_days, z_ml, source_name, BET_TYPE_ML, "clean"),
            as_summary_row(generated_utc, as_of_stub, "all_time", window_days, z_hc, source_name, BET_TYPE_HANDICAP, "overall"),
            as_summary_row(generated_utc, as_of_stub, "all_time", window_days, z_hc, source_name, BET_TYPE_HANDICAP, "clean"),
        ]
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            "Strict Policy Settled Performance\n"
            f"Generated UTC: {generated_utc}\n"
            f"As-of date: {as_of_stub.isoformat()}\n"
            f"No signal rows in {signals_path.name}; stub summary (all zeros).\n",
            encoding="utf-8",
        )
        append_summary(summary_path, stub_rows)
        print(f"Wrote empty stub: {report_path}")
        print(f"Appended summary CSV: {summary_path}")
        return 0

    use_compare = compare_path is not None and compare_path.exists()
    if use_compare:
        compare_rows = dedupe_rows(load_csv_rows(compare_path))
        settlement_lookup = build_settlement_lookup(signal_rows)
        patched, patched_settled = attach_settlement(compare_rows, settlement_lookup)
        base_rows = [{**r, "policy_mode": (r.get("policy_mode") or "base")} for r in signal_rows]
        overlay_rows = [r for r in compare_rows if norm_key_val(r.get("policy_mode")) == "overlay"]
        report_rows = base_rows + overlay_rows
    else:
        report_rows = signal_rows
        patched = 0
        patched_settled = 0

    if not report_rows:
        print("No report rows available.")
        return 0

    max_date = max((parse_iso_date(r.get("date")) for r in report_rows if parse_iso_date(r.get("date"))), default=None)
    if max_date is None:
        print("No valid date rows in source.")
        return 0
    as_of = parse_iso_date(args.as_of) if args.as_of else max_date
    if as_of is None:
        print(f"Invalid --as-of date: {args.as_of}")
        return 1

    window_start = as_of - timedelta(days=window_days - 1)
    window_rows = filter_window(report_rows, window_start, as_of)
    all_rows = [r for r in report_rows if parse_iso_date(r.get("date")) is not None and parse_iso_date(r.get("date")) <= as_of]
    legacy_rows = [r for r in all_rows if (parse_iso_date(r.get("date")) or CLEAN_EVAL_START) < CLEAN_EVAL_START]
    clean_rows = [r for r in all_rows if (parse_iso_date(r.get("date")) or date.min) >= CLEAN_EVAL_START]
    clean_window_start = max(window_start, CLEAN_EVAL_START)
    clean_window_rows = filter_window(clean_rows, clean_window_start, as_of) if as_of >= CLEAN_EVAL_START else []

    modes = sorted({norm_key_val(r.get("policy_mode") or "base") or "base" for r in all_rows})
    if "base" in modes and "overlay" in modes:
        ordered_modes = ["base", "overlay"]
    else:
        ordered_modes = modes

    window_summary = {m: summarize_mode(window_rows, m) for m in ordered_modes}
    all_summary = {m: summarize_mode(all_rows, m) for m in ordered_modes}
    legacy_summary = {m: summarize_mode(legacy_rows, m) for m in ordered_modes}
    clean_summary = {m: summarize_mode(clean_rows, m) for m in ordered_modes}
    clean_window_summary = {m: summarize_mode(clean_window_rows, m) for m in ordered_modes}

    lines: list[str] = []
    lines.append("Strict Policy Settled Performance")
    lines.append(f"Generated UTC: {generated_utc}")
    lines.append(f"As-of date: {as_of.isoformat()}")
    lines.append(f"Window: {window_start.isoformat()} -> {as_of.isoformat()} ({window_days}d)")
    lines.append(f"Clean evaluation start: {CLEAN_EVAL_START.isoformat()}")
    lines.append(
        f"Source: {'base from strict-signals + overlay from overlay-compare' if use_compare else 'strict-signals only'}"
    )
    if use_compare:
        lines.append(
            f"Settlement backfill from strict-signals: patched_rows={patched}, patched_to_settled={patched_settled}"
        )
    lines.append("")

    def add_scope(title: str, summaries: dict[str, ModeSummary]) -> None:
        lines.append(title)
        for mode in ordered_modes:
            s = summaries[mode]
            lines.append(
                "  "
                f"{mode.upper():7s} "
                f"signals={s.signals:4d} settled={s.settled:4d} unsettled={s.unsettled:4d} "
                f"W-L={s.wins:3d}-{s.losses:3d} "
                f"staked={fmt_num(s.staked_units, 2)}u pnl={fmt_num(s.pnl_units, 2)}u "
                f"ROI={fmt_num(s.roi_pct, 2, '%')} WR={fmt_num(s.win_rate_pct, 2, '%')} "
                f"avg_value={fmt_num(s.avg_value_pct, 2, '%')} avg_pin={fmt_num(s.avg_pin_odds, 3)} "
                f"invalid_odds={s.invalid_odds}"
            )
        if "base" in summaries and "overlay" in summaries:
            b = summaries["base"]
            o = summaries["overlay"]
            roi_diff = (o.roi_pct - b.roi_pct) if (o.roi_pct is not None and b.roi_pct is not None) else None
            pnl_diff = o.pnl_units - b.pnl_units
            lines.append(
                "  "
                f"DELTA overlay-base: "
                f"signals={o.signals - b.signals:+d} settled={o.settled - b.settled:+d} "
                f"pnl={pnl_diff:+.2f}u roi={fmt_num(roi_diff, 2, 'pp')}"
            )
        lines.append("")

    def add_scope_by_bet_type(title: str, by_mode_bt: dict[str, dict[str, ModeSummary]]) -> None:
        lines.append(title)
        for bt_label, bt_key in [("ML (match winner)", BET_TYPE_ML), ("Handicap (spread)", BET_TYPE_HANDICAP)]:
            lines.append(f"  [{bt_label}]")
            for mode in ordered_modes:
                s = by_mode_bt.get(mode, {}).get(bt_key)
                if s is None:
                    continue
                lines.append(
                    "    "
                    f"{mode.upper():7s} "
                    f"signals={s.signals:4d} settled={s.settled:4d} backlog={s.unsettled:4d} "
                    f"W-L={s.wins:3d}-{s.losses:3d} "
                    f"ROI={fmt_num(s.roi_pct, 2, '%')} pnl={fmt_num(s.pnl_units, 2)}u"
                )
        lines.append("")

    add_scope("Window performance (combined)", window_summary)
    add_scope("All-time performance (combined)", all_summary)
    add_scope("Legacy period (mixed-vintage, all-time)", legacy_summary)
    add_scope("Clean period (all-time)", clean_summary)
    add_scope("Clean period window (combined)", clean_window_summary)

    window_by_bt = {m: summarize_mode_by_bet_type(window_rows, m) for m in ordered_modes}
    all_by_bt = {m: summarize_mode_by_bet_type(all_rows, m) for m in ordered_modes}
    legacy_by_bt = {m: summarize_mode_by_bet_type(legacy_rows, m) for m in ordered_modes}
    clean_by_bt = {m: summarize_mode_by_bet_type(clean_rows, m) for m in ordered_modes}
    clean_window_by_bt = {m: summarize_mode_by_bet_type(clean_window_rows, m) for m in ordered_modes}
    add_scope_by_bet_type("Window performance by bet type (ML vs Handicap)", window_by_bt)
    add_scope_by_bet_type("All-time performance by bet type (ML vs Handicap)", all_by_bt)
    add_scope_by_bet_type("Legacy period by bet type (ML vs Handicap)", legacy_by_bt)
    add_scope_by_bet_type("Clean period by bet type (ML vs Handicap)", clean_by_bt)
    add_scope_by_bet_type("Clean period window by bet type (ML vs Handicap)", clean_window_by_bt)

    report_text = "\n".join(lines).rstrip() + "\n"
    print(report_text)

    if not args.dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")

        source_name = f"{signals_path.name}+{compare_path.name}" if use_compare else signals_path.name
        summary_rows: list[dict[str, str]] = []
        league_scopes = (
            LEAGUE_SCOPES
            if any(norm_key_val(r.get("league")) in {"atp", "challenger"} for r in signal_rows)
            else ["combined"]
        )
        for league_scope in league_scopes:
            window_rows_scope = filter_rows_by_league(window_rows, league_scope)
            all_rows_scope = filter_rows_by_league(all_rows, league_scope)
            legacy_rows_scope = filter_rows_by_league(legacy_rows, league_scope)
            clean_rows_scope = filter_rows_by_league(clean_rows, league_scope)
            clean_window_rows_scope = filter_rows_by_league(clean_window_rows, league_scope)
            window_summary_scope = {m: summarize_mode(window_rows_scope, m) for m in ordered_modes}
            all_summary_scope = {m: summarize_mode(all_rows_scope, m) for m in ordered_modes}
            legacy_summary_scope = {m: summarize_mode(legacy_rows_scope, m) for m in ordered_modes}
            clean_summary_scope = {m: summarize_mode(clean_rows_scope, m) for m in ordered_modes}
            clean_window_summary_scope = {m: summarize_mode(clean_window_rows_scope, m) for m in ordered_modes}
            window_by_bt_scope = {m: summarize_mode_by_bet_type(window_rows_scope, m) for m in ordered_modes}
            all_by_bt_scope = {m: summarize_mode_by_bet_type(all_rows_scope, m) for m in ordered_modes}
            legacy_by_bt_scope = {m: summarize_mode_by_bet_type(legacy_rows_scope, m) for m in ordered_modes}
            clean_by_bt_scope = {m: summarize_mode_by_bet_type(clean_rows_scope, m) for m in ordered_modes}
            clean_window_by_bt_scope = {m: summarize_mode_by_bet_type(clean_window_rows_scope, m) for m in ordered_modes}
            for mode in ordered_modes:
                summary_rows.append(
                    as_summary_row(
                        generated_utc=generated_utc,
                        as_of=as_of,
                        scope="window",
                        eval_period="overall",
                        window_days=window_days,
                        mode_summary=window_summary_scope[mode],
                        source=source_name,
                        bet_type="",
                        league_scope=league_scope,
                    )
                )
                summary_rows.append(
                    as_summary_row(
                        generated_utc=generated_utc,
                        as_of=as_of,
                        scope="all_time",
                        eval_period="overall",
                        window_days=window_days,
                        mode_summary=all_summary_scope[mode],
                        source=source_name,
                        bet_type="",
                        league_scope=league_scope,
                    )
                )
                for bt in [BET_TYPE_ML, BET_TYPE_HANDICAP]:
                    summary_rows.append(
                        as_summary_row(
                            generated_utc=generated_utc,
                            as_of=as_of,
                            scope="window",
                            eval_period="overall",
                            window_days=window_days,
                            mode_summary=window_by_bt_scope[mode][bt],
                            source=source_name,
                            bet_type=bt,
                            league_scope=league_scope,
                        )
                    )
                    summary_rows.append(
                        as_summary_row(
                            generated_utc=generated_utc,
                            as_of=as_of,
                            scope="all_time",
                            eval_period="overall",
                            window_days=window_days,
                            mode_summary=all_by_bt_scope[mode][bt],
                            source=source_name,
                            bet_type=bt,
                            league_scope=league_scope,
                        )
                    )
                summary_rows.append(
                    as_summary_row(
                        generated_utc=generated_utc,
                        as_of=as_of,
                        scope="all_time",
                        eval_period="legacy",
                        window_days=window_days,
                        mode_summary=legacy_summary_scope[mode],
                        source=source_name,
                        bet_type="",
                        league_scope=league_scope,
                    )
                )
                summary_rows.append(
                    as_summary_row(
                        generated_utc=generated_utc,
                        as_of=as_of,
                        scope="all_time",
                        eval_period="clean",
                        window_days=window_days,
                        mode_summary=clean_summary_scope[mode],
                        source=source_name,
                        bet_type="",
                        league_scope=league_scope,
                    )
                )
                summary_rows.append(
                    as_summary_row(
                        generated_utc=generated_utc,
                        as_of=as_of,
                        scope="window",
                        eval_period="clean",
                        window_days=window_days,
                        mode_summary=clean_window_summary_scope[mode],
                        source=source_name,
                        bet_type="",
                        league_scope=league_scope,
                    )
                )
                for bt in [BET_TYPE_ML, BET_TYPE_HANDICAP]:
                    summary_rows.append(
                        as_summary_row(
                            generated_utc=generated_utc,
                            as_of=as_of,
                            scope="all_time",
                            eval_period="legacy",
                            window_days=window_days,
                            mode_summary=legacy_by_bt_scope[mode][bt],
                            source=source_name,
                            bet_type=bt,
                            league_scope=league_scope,
                        )
                    )
                    summary_rows.append(
                        as_summary_row(
                            generated_utc=generated_utc,
                            as_of=as_of,
                            scope="all_time",
                            eval_period="clean",
                            window_days=window_days,
                            mode_summary=clean_by_bt_scope[mode][bt],
                            source=source_name,
                            bet_type=bt,
                            league_scope=league_scope,
                        )
                    )
                    summary_rows.append(
                        as_summary_row(
                            generated_utc=generated_utc,
                            as_of=as_of,
                            scope="window",
                            eval_period="clean",
                            window_days=window_days,
                            mode_summary=clean_window_by_bt_scope[mode][bt],
                            source=source_name,
                            bet_type=bt,
                            league_scope=league_scope,
                        )
                    )
        append_summary(summary_path, summary_rows)
        print(f"Wrote report: {report_path}")
        print(f"Appended summary CSV: {summary_path}")
    else:
        print("Dry run: report/summary files not written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
