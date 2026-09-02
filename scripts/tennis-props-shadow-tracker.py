#!/usr/bin/env python3
"""Append Bet365 tennis aces/DF comparison rows to a shadow evidence file.

This records only model-vs-line edges that pass a simple confidence/value gate.
It does not publish picks and it does not rewrite settled rows.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone, date
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "data" / "tennis-props"
SHADOW_DIR = PROPS_DIR / "shadow"
DEFAULT_SIGNALS = SHADOW_DIR / "aces-dfs-shadow-signals.csv"
DEFAULT_PERFORMANCE = SHADOW_DIR / "aces-dfs-shadow-performance.txt"
BREAK_MARKETS = {"player_breaks", "match_breaks"}
BREAK_CALIBRATION_MODE = "breaks_calibration_unfiltered"
BREAK_PROSPECTIVE_MODE = "breaks_prospective_shadow"
BREAK_SINGLE_SOURCE_MODE = "breaks_single_source_shadow"
BREAK_PROSPECTIVE_MODES = {BREAK_PROSPECTIVE_MODE, BREAK_SINGLE_SOURCE_MODE}
BREAK_GATE_VERSION = "breaks_v1_p1"
BREAK_MIN_VALUE_PCT = 3.0

FIELDNAMES = [
    "signal_id",
    "logged_at_utc",
    "date",
    "tour",
    "tournament",
    "scope",
    "player",
    "opponent",
    "market",
    "line",
    "side",
    "projection_mean",
    "projection_p1",
    "projection_p2",
    "confidence",
    "p1_confidence",
    "p2_confidence",
    "combined_surface_svpt_sample",
    "bookmaker",
    "event_id",
    "capture_ts",
    "match_start_utc",
    "over_odds",
    "under_odds",
    "selected_odds",
    "closing_odds",
    "closing_ts_utc",
    "closing_snapshot_count",
    "clv_pct",
    "clv_method",
    "fair_over_odds",
    "fair_under_odds",
    "fair_odds",
    "fair_p_push",
    "distribution",
    "totals_alpha",
    "totals_stage0_passed",
    "breaks_alpha",
    "breaks_stage0_passed",
    "value_over_pct",
    "value_under_pct",
    "value_pct",
    "novig_p_over",
    "novig_p_under",
    "edge_over_novig_pct",
    "edge_under_novig_pct",
    "matched_board",
    "decision_mode",
    "price_pair_status",
    "cohort",
    "gate_version",
    "trackable_shadow",
    "shadow_side",
    "shadow_block_reasons",
    "calibration_eligible",
    "line_quality",
    "main_line",
    "best_available_line",
    "model_market_gap_pp",
    "source_agreement",
    "source_agreement_bookmakers",
    "source_agreement_gap_pp",
    "observed_side",
    "observed_odds",
    "observed_value_pct",
    "notes",
    "source_file",
    "settlement_status",
    "actual",
    "result",
    "pnl",
    "settled_at_utc",
    "settlement_note",
]


def norm_text(value: object) -> str:
    raw = str(value or "").strip()
    text = unicodedata.normalize("NFKD", raw)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def parse_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and parsed not in (float("inf"), float("-inf")) else None


def fmt_float(value: float | None, digits: int = 3) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def signal_id(row: dict[str, str], side: str) -> str:
    if (row.get("scope") or "").strip().lower() == "match_total":
        pair = sorted((norm_text(row.get("player")), norm_text(row.get("opponent"))))
        return "|".join(
            [
                row.get("date") or "",
                (row.get("tour") or "").upper(),
                norm_text(row.get("tournament")),
                *pair,
                norm_text(row.get("market")),
                str(row.get("line") or "").strip(),
                side.upper(),
            ]
        )
    parts = [
        row.get("date") or "",
        (row.get("tour") or "").upper(),
        norm_text(row.get("tournament")),
        norm_text(row.get("player")),
        norm_text(row.get("opponent")),
        norm_text(row.get("market")),
        str(row.get("line") or "").strip(),
        side.upper(),
    ]
    return "|".join(parts)


def pick_side(row: dict[str, str], min_value_pct: float, allow_watch: bool) -> tuple[str, float, float] | None:
    recommended = (row.get("recommended_side") or "").strip().upper()
    value_over = parse_float(row.get("value_over_pct"))
    value_under = parse_float(row.get("value_under_pct"))
    over_odds = parse_float(row.get("over_odds"))
    under_odds = parse_float(row.get("under_odds"))

    if recommended == "OVER" and value_over is not None and over_odds and value_over >= min_value_pct:
        return "OVER", value_over, over_odds
    if recommended == "UNDER" and value_under is not None and under_odds and value_under >= min_value_pct:
        return "UNDER", value_under, under_odds
    if not allow_watch:
        return None

    candidates: list[tuple[str, float, float]] = []
    if value_over is not None and over_odds and value_over >= min_value_pct:
        candidates.append(("OVER", value_over, over_odds))
    if value_under is not None and under_odds and value_under >= min_value_pct:
        candidates.append(("UNDER", value_under, under_odds))
    return max(candidates, key=lambda item: item[1]) if candidates else None


def fair_odds_for_side(row: dict[str, str], side: str) -> str:
    key = "fair_over_odds" if side == "OVER" else "fair_under_odds"
    return row.get(key, "")


def is_break_market(row: dict[str, str]) -> bool:
    return str(row.get("market") or "").strip().lower() in BREAK_MARKETS


def best_observation(row: dict[str, str]) -> tuple[str, float, float] | None:
    candidates: list[tuple[str, float, float]] = []
    for side, value_key, odds_key in (
        ("OVER", "value_over_pct", "over_odds"),
        ("UNDER", "value_under_pct", "under_odds"),
    ):
        value = parse_float(row.get(value_key))
        odds = parse_float(row.get(odds_key))
        if value is not None and odds is not None and odds > 1.0:
            candidates.append((side, value, odds))
    return max(candidates, key=lambda item: item[1]) if candidates else None


def normalize_existing_row(row: dict[str, str]) -> dict[str, str]:
    """Migrate legacy break selections into non-betting calibration evidence."""
    normalized = dict(row)
    if not is_break_market(normalized):
        return normalized
    mode = str(normalized.get("decision_mode") or "").strip()
    if mode in BREAK_PROSPECTIVE_MODES:
        normalized.setdefault("cohort", mode)
        normalized.setdefault("gate_version", BREAK_GATE_VERSION)
        return normalized
    if mode not in {"", "breaks_shadow", BREAK_CALIBRATION_MODE}:
        return normalized

    normalized["observed_side"] = normalized.get("observed_side") or normalized.get("side", "")
    normalized["observed_odds"] = normalized.get("observed_odds") or normalized.get("selected_odds", "")
    normalized["observed_value_pct"] = normalized.get("observed_value_pct") or normalized.get("value_pct", "")
    normalized["side"] = ""
    normalized["selected_odds"] = ""
    normalized["closing_odds"] = ""
    normalized["closing_ts_utc"] = ""
    normalized["closing_snapshot_count"] = ""
    normalized["clv_pct"] = ""
    normalized["clv_method"] = ""
    normalized["fair_odds"] = ""
    normalized["value_pct"] = ""
    normalized["decision_mode"] = BREAK_CALIBRATION_MODE
    normalized["cohort"] = BREAK_CALIBRATION_MODE
    normalized["gate_version"] = BREAK_GATE_VERSION
    normalized["trackable_shadow"] = "false"
    normalized["shadow_side"] = ""
    if (normalized.get("settlement_status") or "").lower() == "settled":
        normalized["result"] = "calibration"
        normalized["pnl"] = ""
    normalized["signal_id"] = signal_id(normalized, "CALIBRATION")
    return normalized


def build_signal(row: dict[str, str], source: Path, args: argparse.Namespace) -> dict[str, str] | None:
    scope = (row.get("scope") or "player").strip().lower()
    decision_mode = (row.get("decision_mode") or "").strip()
    is_break_calibration = is_break_market(row) and decision_mode == BREAK_CALIBRATION_MODE
    is_break_prospective = is_break_market(row) and decision_mode in BREAK_PROSPECTIVE_MODES
    confidence = (row.get("confidence") or "").strip().upper()
    allowed_conf = {"HIGH", "MED"} if scope == "match_total" or args.allow_medium else {"HIGH"}
    if not is_break_calibration and confidence not in allowed_conf:
        return None
    if not is_break_calibration and (row.get("matched_board") or "").strip().lower() != "yes":
        return None
    observation = best_observation(row) if is_break_market(row) else None
    if is_break_calibration:
        if (row.get("calibration_eligible") or "").strip().lower() != "true":
            return None
        picked = None
    elif is_break_prospective:
        if (row.get("trackable_shadow") or "").strip().lower() != "true":
            return None
        picked = pick_side(row, BREAK_MIN_VALUE_PCT, True)
        shadow_side = (row.get("shadow_side") or "").strip().upper()
        if picked is None or picked[0] != shadow_side:
            return None
    elif scope == "match_total":
        if (row.get("bettable") or "").strip().lower() != "true":
            return None
        picked = pick_side(row, args.min_value, args.allow_watch)
    else:
        if (row.get("trackable_shadow") or "").strip().lower() != "true":
            return None
        if decision_mode not in {"one_sided_over_shadow", "two_way_player_shadow"}:
            return None
        shadow_side = (row.get("shadow_side") or "").strip().upper()
        if shadow_side not in {"OVER", "UNDER"}:
            return None
        if decision_mode == "one_sided_over_shadow" and shadow_side != "OVER":
            return None
        picked = pick_side(row, args.min_value, True)
        if picked is not None and picked[0] != shadow_side:
            return None
    if picked is None and not is_break_calibration:
        return None
    side = "" if is_break_calibration else picked[0]
    value_pct = None if is_break_calibration else picked[1]
    selected_odds = None if is_break_calibration else picked[2]
    sid = signal_id(row, "CALIBRATION" if is_break_calibration else side)
    return {
        "signal_id": sid,
        "logged_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "date": row.get("date", ""),
        "tour": (row.get("tour") or "").upper(),
        "tournament": row.get("tournament", ""),
        "scope": scope,
        "player": row.get("player", ""),
        "opponent": row.get("opponent", ""),
        "market": row.get("market", ""),
        "line": row.get("line", ""),
        "side": side,
        "projection_mean": row.get("projection_mean", ""),
        "projection_p1": row.get("projection_p1", ""),
        "projection_p2": row.get("projection_p2", ""),
        "confidence": confidence,
        "p1_confidence": row.get("p1_confidence", ""),
        "p2_confidence": row.get("p2_confidence", ""),
        "combined_surface_svpt_sample": row.get("combined_surface_svpt_sample", ""),
        "bookmaker": row.get("bookmaker", "") or args.bookmaker,
        "event_id": row.get("event_id", ""),
        "capture_ts": row.get("capture_ts", ""),
        "match_start_utc": row.get("match_start_utc", ""),
        "over_odds": row.get("over_odds", ""),
        "under_odds": row.get("under_odds", ""),
        "selected_odds": fmt_float(selected_odds, 3),
        "closing_odds": "",
        "closing_ts_utc": "",
        "closing_snapshot_count": "",
        "clv_pct": "",
        "clv_method": "",
        "fair_over_odds": row.get("fair_over_odds", ""),
        "fair_under_odds": row.get("fair_under_odds", ""),
        "fair_odds": "" if is_break_calibration else fair_odds_for_side(row, side),
        "fair_p_push": row.get("fair_p_push", ""),
        "distribution": row.get("distribution", ""),
        "totals_alpha": row.get("totals_alpha", ""),
        "totals_stage0_passed": row.get("totals_stage0_passed", ""),
        "breaks_alpha": row.get("breaks_alpha", ""),
        "breaks_stage0_passed": row.get("breaks_stage0_passed", ""),
        "value_over_pct": row.get("value_over_pct", ""),
        "value_under_pct": row.get("value_under_pct", ""),
        "value_pct": fmt_float(value_pct, 2),
        "novig_p_over": row.get("novig_p_over", ""),
        "novig_p_under": row.get("novig_p_under", ""),
        "edge_over_novig_pct": row.get("edge_over_novig_pct", ""),
        "edge_under_novig_pct": row.get("edge_under_novig_pct", ""),
        "matched_board": row.get("matched_board", ""),
        "decision_mode": row.get("decision_mode", ""),
        "price_pair_status": row.get("price_pair_status", ""),
        "cohort": row.get("cohort", "") or row.get("decision_mode", ""),
        "gate_version": row.get("gate_version", ""),
        "trackable_shadow": row.get("trackable_shadow", ""),
        "shadow_side": row.get("shadow_side", ""),
        "shadow_block_reasons": row.get("shadow_block_reasons", ""),
        "calibration_eligible": row.get("calibration_eligible", ""),
        "line_quality": row.get("line_quality", ""),
        "main_line": row.get("main_line", ""),
        "best_available_line": row.get("best_available_line", ""),
        "model_market_gap_pp": row.get("model_market_gap_pp", ""),
        "source_agreement": row.get("source_agreement", ""),
        "source_agreement_bookmakers": row.get("source_agreement_bookmakers", ""),
        "source_agreement_gap_pp": row.get("source_agreement_gap_pp", ""),
        "observed_side": observation[0] if observation else "",
        "observed_odds": fmt_float(observation[2], 3) if observation else "",
        "observed_value_pct": fmt_float(observation[1], 2) if observation else "",
        "notes": row.get("notes", ""),
        "source_file": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
        "settlement_status": "pending",
        "actual": "",
        "result": "",
        "pnl": "",
        "settled_at_utc": "",
        "settlement_note": "",
    }


def write_performance(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    calibration = [r for r in rows if r.get("decision_mode") == BREAK_CALIBRATION_MODE]
    betting_rows = [r for r in rows if r.get("decision_mode") != BREAK_CALIBRATION_MODE]
    settled = [r for r in betting_rows if (r.get("settlement_status") or "").lower() == "settled"]
    pending = [r for r in betting_rows if (r.get("settlement_status") or "").lower() == "pending"]
    voids = [r for r in betting_rows if (r.get("settlement_status") or "").lower() == "void"]
    calibration_settled = [r for r in calibration if (r.get("settlement_status") or "").lower() == "settled"]
    pnl = sum(parse_float(r.get("pnl")) or 0.0 for r in settled)
    roi = pnl / len(settled) * 100.0 if settled else 0.0
    settled_clv = [parse_float(r.get("clv_pct")) for r in settled]
    settled_clv = [value for value in settled_clv if value is not None]
    mean_clv = sum(settled_clv) / len(settled_clv) if settled_clv else 0.0
    positive_clv = sum(value > 0 for value in settled_clv) / len(settled_clv) * 100.0 if settled_clv else 0.0

    def bucket(label: str, key: str) -> list[str]:
        out = [f"\n{label}:"]
        values = sorted({r.get(key, "") or "-" for r in betting_rows})
        for value in values:
            subset = [r for r in betting_rows if (r.get(key, "") or "-") == value]
            settled_subset = [r for r in subset if (r.get("settlement_status") or "").lower() == "settled"]
            subset_pnl = sum(parse_float(r.get("pnl")) or 0.0 for r in settled_subset)
            subset_roi = subset_pnl / len(settled_subset) * 100.0 if settled_subset else 0.0
            out.append(f"  {value}: rows={len(subset)} settled={len(settled_subset)} pnl={subset_pnl:+.2f}u roi={subset_roi:+.1f}%")
        return out

    lines = [
        "Tennis aces/DF shadow evidence",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Status: internal shadow only; no public betting record or live staking.",
        f"Betting rows: {len(betting_rows)} | settled: {len(settled)} | pending: {len(pending)} | void: {len(voids)}",
        f"Break calibration rows: {len(calibration)} | counts settled: {len(calibration_settled)} | excluded from ROI/CLV",
        f"PnL: {pnl:+.2f}u | ROI: {roi:+.1f}%",
        f"CLV: coverage={len(settled_clv)}/{len(settled)} | mean={mean_clv:+.2f}% | positive={positive_clv:.1f}%",
        "Promotion guard: do not read ROI seriously before 300 settled lines across at least two Slams.",
    ]
    for label, key in [
        ("By cohort", "cohort"),
        ("By market", "market"),
        ("By side", "side"),
        ("By tour", "tour"),
        ("By confidence", "confidence"),
    ]:
        lines.extend(bucket(label, key))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Append Bet365 aces/DF comparison rows to the internal shadow tracker")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--comparison", default="")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS))
    parser.add_argument("--performance", default=str(DEFAULT_PERFORMANCE))
    parser.add_argument("--min-value", type=float, default=8.0, help="Minimum model edge percentage to track")
    parser.add_argument("--allow-medium", action="store_true", help="Also track MED confidence rows")
    parser.add_argument("--allow-notes", action="store_true", help="Track rows even when projection notes are present")
    parser.add_argument("--allow-watch", action="store_true", help="Track best-side rows even if compare script did not mark recommended_side")
    parser.add_argument("--bookmaker", default="Bet365")
    args = parser.parse_args()

    comparison = Path(args.comparison) if args.comparison else PROPS_DIR / f"comparison-{args.date}.csv"
    if not comparison.exists():
        print(f"Comparison file not found: {comparison}")
        return 0

    existing = [normalize_existing_row(row) for row in read_csv(Path(args.signals))]
    existing_by_id = {row.get("signal_id", ""): row for row in existing if row.get("signal_id")}
    added = 0
    for row in read_csv(comparison):
        signal = build_signal(row, comparison, args)
        if signal is None:
            continue
        sid = signal["signal_id"]
        if sid in existing_by_id:
            continue
        existing_by_id[sid] = signal
        existing.append(signal)
        added += 1

    write_csv(Path(args.signals), existing)
    write_performance(Path(args.performance), existing)
    print(f"Shadow tracker: added {added}, total {len(existing)} -> {args.signals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
