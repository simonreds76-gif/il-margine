#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"
DEFAULT_SIGNALS = DATA_DIR / "strict-signals-spreadv1-archive.csv"
DEFAULT_CLV_DETAIL = DATA_DIR / "strict-clv-audit-spreadv1-2026.csv"
DEFAULT_CALIBRATION = DATA_DIR / "spread-v1-calibration-params.json"
DEFAULT_REPORT = DATA_DIR / "spread-v1-shadow-report.txt"
DEFAULT_STATUS = DATA_DIR / "spread-v1-shadow-status.json"
DEFAULT_SWEEP = DATA_DIR / "spread-v1-shadow-threshold-sweep.csv"
THRESHOLDS = [5.0, 8.0, 10.0, 12.0, 15.0, 20.0]
SURFACES = ["Hard", "Clay"]
PROMOTION_MIN_SETTLED = 50
PROMOTION_POSITIVE_SHARE_MIN = 52.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build spread_v1_shadow research report and status artifacts.")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS))
    parser.add_argument("--clv-detail", default=str(DEFAULT_CLV_DETAIL))
    parser.add_argument("--calibration", default=str(DEFAULT_CALIBRATION))
    parser.add_argument("--report-txt", default=str(DEFAULT_REPORT))
    parser.add_argument("--status-json", default=str(DEFAULT_STATUS))
    parser.add_argument("--threshold-sweep-csv", default=str(DEFAULT_SWEEP))
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def norm(value: str | None) -> str:
    return (value or "").strip().lower()


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def settled_spread_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        if norm(row.get("bet_type")) != "spread":
            continue
        if norm(row.get("settlement_status")) != "settled":
            continue
        if norm(row.get("side")) not in {"p1+", "p2-"}:
            continue
        out.append(row)
    return out


def is_settled(row: dict[str, str]) -> bool:
    return norm(row.get("settlement_status")) == "settled"


def logical_pick_key(row: dict[str, str]) -> tuple[str, ...]:
    event_date = norm(row.get("match_date")) or norm(row.get("date"))
    return (
        event_date,
        norm(row.get("player1")),
        norm(row.get("player2")),
        norm(row.get("bet_type") or "match"),
        norm(row.get("side")),
        norm(row.get("policy_mode") or "base"),
        norm(row.get("signal_profile")),
    )


def dedupe_logical_picks(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep first published entry price; merge settlement from later refreshes."""
    out: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = logical_pick_key(row)
        prev = out.get(key)
        if prev is None:
            out[key] = dict(row)
            continue
        if is_settled(row):
            for field in (
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
            ):
                if norm(row.get(field)):
                    prev[field] = row.get(field) or ""
    return list(out.values())


def line_bucket(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{abs(value):.1f}"


def row_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    spread_line = parse_float(row.get("spread_line"))
    spread_key = "" if spread_line is None else f"{spread_line:.1f}"
    return (
        (row.get("signal_date") or row.get("date") or "").strip(),
        (row.get("player1") or "").strip().lower(),
        (row.get("player2") or "").strip().lower(),
        (row.get("side") or "").strip().lower(),
        spread_key,
    )


def build_clv_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str, str], dict[str, str]]:
    lookup: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    for row in rows:
        lookup[row_key(row)] = row
    return lookup


def row_pnl_units(row: dict[str, str]) -> tuple[float, float]:
    outcome = norm(row.get("bet_outcome"))
    stake_units = parse_float(row.get("stake_units")) or 0.0
    odds = parse_float(row.get("spread_odds")) or 0.0
    if outcome == "win" and odds > 1:
        return stake_units * (odds - 1.0), stake_units
    if outcome == "loss":
        return -stake_units, stake_units
    if outcome == "void":
        return 0.0, 0.0
    return 0.0, 0.0


def evaluate_threshold(
    rows: list[dict[str, str]],
    clv_lookup: dict[tuple[str, str, str, str, str], dict[str, str]],
    threshold: float,
) -> dict[str, Any]:
    eligible = [row for row in rows if (parse_float(row.get("value_pct")) or 0.0) >= threshold]
    pnl_units = 0.0
    staked_units = 0.0
    line_bucket_pnl: dict[str, float] = defaultdict(float)
    clv_values: list[float] = []
    for row in eligible:
        pnl, staked = row_pnl_units(row)
        pnl_units += pnl
        staked_units += staked
        bucket = line_bucket(parse_float(row.get("spread_line")))
        line_bucket_pnl[bucket] += pnl
        clv_row = clv_lookup.get(row_key(row))
        if clv_row:
            clv_val = parse_float(clv_row.get("clv_implied_delta_pct"))
            if clv_val is not None:
                clv_values.append(clv_val)

    roi_pct = (100.0 * pnl_units / staked_units) if staked_units > 0 else None
    avg_clv = mean(clv_values) if clv_values else None
    median_clv = median(clv_values) if clv_values else None
    positive_clv = sum(1 for value in clv_values if value > 0)
    positive_share = (100.0 * positive_clv / len(clv_values)) if clv_values else None
    abs_total = sum(abs(value) for value in line_bucket_pnl.values())
    dominant_share = (
        max((abs(value) for value in line_bucket_pnl.values()), default=0.0) / abs_total
        if abs_total > 0
        else None
    )
    live_ready = bool(
        len(eligible) >= PROMOTION_MIN_SETTLED
        and avg_clv is not None
        and avg_clv > 0
        and positive_share is not None
        and positive_share >= PROMOTION_POSITIVE_SHARE_MIN
        and roi_pct is not None
        and roi_pct > 0
        and dominant_share is not None
        and dominant_share <= 0.5
    )
    return {
        "threshold_pct": threshold,
        "settled": len(eligible),
        "staked_units": round(staked_units, 4),
        "pnl_units": round(pnl_units, 4),
        "roi_pct": round(roi_pct, 4) if roi_pct is not None else None,
        "clv_matched": len(clv_values),
        "avg_clv_pct": round(avg_clv, 4) if avg_clv is not None else None,
        "median_clv_pct": round(median_clv, 4) if median_clv is not None else None,
        "positive_clv_share_pct": round(positive_share, 4) if positive_share is not None else None,
        "line_bucket_dominance_share": round(dominant_share, 4) if dominant_share is not None else None,
        "line_bucket_pnl": {key: round(value, 4) for key, value in sorted(line_bucket_pnl.items())},
        "live_ready": live_ready,
    }


def calibration_status(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "valid": False,
            "reason": "missing",
            "line_source_used": "",
            "fit_timestamp": "",
            "usable_scope": {},
            "base_calibration_valid": False,
            "base_calibration_reason": "missing",
            "correction_valid": False,
            "correction_reason": "missing",
        }
    line_source = str(payload.get("line_source_used") or "").strip().lower()
    usable_scope = payload.get("usable_scope") if isinstance(payload.get("usable_scope"), dict) else {}
    surfaces = {str(item).strip() for item in usable_scope.get("surfaces") or [] if str(item).strip()}
    leagues = {str(item).strip() for item in usable_scope.get("leagues") or [] if str(item).strip()}
    best_of = str(usable_scope.get("best_of") or "").strip().lower()
    valid = line_source == "snapshot" and best_of == "bo3" and "ATP" in leagues and {"Hard", "Clay"}.issubset(surfaces)
    correction_valid = bool(payload.get("correction_valid"))
    correction_reason = str(payload.get("correction_reason") or "missing")
    base_calibration_valid = payload.get("calibration_valid") is not False
    warning = ""
    if valid and not base_calibration_valid and not correction_valid:
        valid = False
        reason = f"base:{payload.get('calibration_reason') or 'invalid'};correction:{correction_reason}"
    elif valid and base_calibration_valid and not correction_valid:
        reason = "ok-base-only"
        warning = f"correction:{correction_reason}"
    else:
        reason = "ok" if (valid and base_calibration_valid) else ("ok-correction-only" if valid else "invalid-scope-or-source")
    return {
        "valid": valid,
        "reason": reason,
        "line_source_used": line_source,
        "fit_timestamp": payload.get("correction_fit_timestamp") or payload.get("fit_timestamp") or payload.get("generated_at_utc") or payload.get("generated_at") or "",
        "usable_scope": usable_scope,
        "train_sample_size": payload.get("train_sample_size"),
        "test_sample_size": payload.get("test_sample_size"),
        "surface_eval": payload.get("surface_eval"),
        "base_calibration_valid": base_calibration_valid,
        "base_calibration_reason": str(
            payload.get("calibration_reason") or ("ok" if payload.get("calibration_valid") is not False else "invalid")
        ),
        "correction_valid": correction_valid,
        "correction_reason": correction_reason,
        "correction_model": payload.get("correction_model") if isinstance(payload.get("correction_model"), dict) else {},
        "warning": warning,
    }


def main() -> None:
    args = parse_args()
    signals_path = resolve_path(args.signals)
    clv_detail_path = resolve_path(args.clv_detail)
    calibration_path = resolve_path(args.calibration)
    report_path = resolve_path(args.report_txt)
    status_path = resolve_path(args.status_json)
    sweep_path = resolve_path(args.threshold_sweep_csv)

    raw_rows = dedupe_logical_picks(load_csv_rows(signals_path))
    settled_rows_all = settled_spread_rows(raw_rows)
    clv_rows = load_csv_rows(clv_detail_path)
    clv_lookup = build_clv_lookup(clv_rows)
    calibration = calibration_status(load_json(calibration_path))
    manual_live_surfaces = {
        token.strip().title()
        for token in (os.environ.get("SPREAD_V1_LIVE_SURFACES") or "").split(",")
        if token.strip()
    }

    sweep_rows: list[dict[str, Any]] = []
    surfaces_payload: dict[str, Any] = {}
    recommended_thresholds: dict[str, float | None] = {}

    for surface in SURFACES:
        surface_rows = [row for row in settled_rows_all if (row.get("surface") or "").strip() == surface]
        threshold_results = [evaluate_threshold(surface_rows, clv_lookup, threshold) for threshold in THRESHOLDS]
        for result in threshold_results:
            sweep_rows.append({"surface": surface, **result})
        recommended = next((result for result in threshold_results if result["live_ready"]), None)
        recommended_thresholds[surface] = recommended["threshold_pct"] if recommended else None
        current_surface = threshold_results[0] if threshold_results else None
        if not calibration["valid"]:
            promotion_status = "off"
        elif recommended is not None and surface in manual_live_surfaces:
            promotion_status = "live"
        elif recommended is not None:
            promotion_status = "live-ready"
        else:
            promotion_status = "shadow"
        surfaces_payload[surface.lower()] = {
            "settled_total": len(surface_rows),
            "recommended_threshold_pct": recommended_thresholds[surface],
            "promotion_status": promotion_status,
            "threshold_results": threshold_results,
            "current_threshold_pct": THRESHOLDS[0] if current_surface else None,
            "current": current_surface,
        }

    tracked_rows = [row for row in raw_rows if norm(row.get("bet_type")) == "spread" and norm(row.get("signal_profile")) == "spread_v1_shadow"]
    settled_count = len(settled_rows_all)
    open_count = sum(1 for row in tracked_rows if norm(row.get("settlement_status")) != "settled")
    last_spread_capture_at = max(
        (row.get("history_captured_at") or "" for row in clv_rows if (row.get("history_captured_at") or "").strip()),
        default="",
    )
    if not last_spread_capture_at:
        last_spread_capture_at = max((row.get("time_utc") or "" for row in tracked_rows), default="")

    status_payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "signals_file": str(signals_path.relative_to(ROOT)),
        "clv_detail_file": str(clv_detail_path.relative_to(ROOT)),
        "calibration_file": str(calibration_path.relative_to(ROOT)),
        "legacy_profile": "spread_shadow",
        "active_profile": "spread_v1_shadow",
        "tracked": len(tracked_rows),
        "settled": settled_count,
        "open": open_count,
        "clv_rows": len(clv_rows),
        "last_spread_capture_at": last_spread_capture_at,
        "calibration": calibration,
        "surfaces": surfaces_payload,
    }

    report_lines = [
        "Spread v1 Shadow Report",
        f"Generated UTC: {status_payload['generated_at']}",
        f"Signals file: {status_payload['signals_file']}",
        f"CLV detail file: {status_payload['clv_detail_file']}",
        f"Calibration file: {status_payload['calibration_file']}",
        "",
        "Overall",
        f"  Tracked rows: {status_payload['tracked']}",
        f"  Settled rows: {status_payload['settled']}",
        f"  Open rows: {status_payload['open']}",
        f"  CLV rows: {status_payload['clv_rows']}",
        f"  Last spread capture at: {status_payload['last_spread_capture_at'] or 'n/a'}",
        "",
        "Calibration",
        f"  Valid: {calibration['valid']}",
        f"  Reason: {calibration['reason']}",
        f"  Line source: {calibration['line_source_used'] or 'n/a'}",
        f"  Fit timestamp: {calibration['fit_timestamp'] or 'n/a'}",
        f"  Usable scope: {calibration['usable_scope'] or {}}",
        f"  Base calibration valid: {calibration.get('base_calibration_valid', False)}",
        f"  Base calibration reason: {calibration.get('base_calibration_reason', 'n/a')}",
        f"  Correction valid: {calibration.get('correction_valid', False)}",
        f"  Correction reason: {calibration.get('correction_reason', 'n/a')}",
    ]
    if calibration["valid"] and not calibration.get("base_calibration_valid", False):
        report_lines.extend(
            [
                "  WARNING: correction-only mode is active because base calibration is invalid.",
                "  Treat promotion status as shadow-only until snapshot/base calibration is refit.",
            ]
        )
    if calibration.get("warning"):
        report_lines.append(f"  WARNING: {calibration['warning']}")

    for surface in SURFACES:
        payload = surfaces_payload[surface.lower()]
        report_lines.extend(
            [
                "",
                f"{surface}",
                f"  Promotion status: {payload['promotion_status']}",
                f"  Settled total: {payload['settled_total']}",
                f"  Recommended threshold: {payload['recommended_threshold_pct'] if payload['recommended_threshold_pct'] is not None else 'n/a'}",
            ]
        )
        for result in payload["threshold_results"]:
            report_lines.append(
                "  "
                + f"thr={result['threshold_pct']:.1f}% settled={result['settled']} "
                + f"roi={result['roi_pct'] if result['roi_pct'] is not None else 'n/a'} "
                + f"avg_clv={result['avg_clv_pct'] if result['avg_clv_pct'] is not None else 'n/a'} "
                + f"pos_clv={result['positive_clv_share_pct'] if result['positive_clv_share_pct'] is not None else 'n/a'} "
                + f"line_dom={result['line_bucket_dominance_share'] if result['line_bucket_dominance_share'] is not None else 'n/a'} "
                + f"ready={result['live_ready']}"
            )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status_payload, indent=2), encoding="utf-8")

    sweep_path.parent.mkdir(parents=True, exist_ok=True)
    with sweep_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "surface",
            "threshold_pct",
            "settled",
            "staked_units",
            "pnl_units",
            "roi_pct",
            "clv_matched",
            "avg_clv_pct",
            "median_clv_pct",
            "positive_clv_share_pct",
            "line_bucket_dominance_share",
            "live_ready",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in sweep_rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    print("\n".join(report_lines))


if __name__ == "__main__":
    main()
