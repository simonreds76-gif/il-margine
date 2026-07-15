#!/usr/bin/env python3
"""Track every clean Bet365 match-total ace/DF line as model evidence.

This lane is deliberately separate from the betting shadow tracker. A row is
observed whenever a complete Bet365 main line matches the projection board,
even when every recommendation gate says NO BET. Actual counts train/evaluate
the count model; bookmaker prices are retained only as opening/closing
benchmarks and never overwrite model parameters.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
import importlib.util
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
PROPS_DIR = ROOT / "data" / "tennis-props"
DEFAULT_LEDGER = PROPS_DIR / "shadow" / "market-observations.csv"
DEFAULT_REPORT = PROPS_DIR / "shadow" / "market-observations-report.txt"
DEFAULT_SACKMANN = ROOT / "data" / "sackmann"
DEFAULT_ONCOURT = ROOT / "data" / "oncourt"

sys.path.insert(0, str(SCRIPTS_DIR))
from tennis_props_model import count_line_probabilities  # noqa: E402


def load_settlement_module():
    path = SCRIPTS_DIR / "tennis-props-settle-shadow.py"
    spec = importlib.util.spec_from_file_location("tennis_props_settle_shadow", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import settlement helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SETTLE = load_settlement_module()

FIELDNAMES = [
    "observation_id",
    "first_seen_utc",
    "date",
    "tour",
    "tournament",
    "surface",
    "player",
    "opponent",
    "market",
    "line",
    "bookmaker",
    "event_id",
    "observed_capture_ts",
    "match_start_utc",
    "observed_over_odds",
    "observed_under_odds",
    "observed_novig_p_over",
    "closing_over_odds",
    "closing_under_odds",
    "closing_novig_p_over",
    "closing_ts_utc",
    "closing_snapshot_count",
    "close_method",
    "projection_mean",
    "projection_p1",
    "projection_p2",
    "model_p_over_conditional",
    "fair_p_push",
    "distribution",
    "totals_alpha",
    "confidence",
    "p1_confidence",
    "p2_confidence",
    "combined_surface_svpt_sample",
    "notes",
    "source_file",
    "settlement_status",
    "actual",
    "outcome_over",
    "model_count_abs_error",
    "observed_market_implied_mean",
    "observed_market_count_abs_error",
    "closing_market_implied_mean",
    "closing_market_count_abs_error",
    "model_brier",
    "observed_market_brier",
    "closing_market_brier",
    "model_log_loss",
    "observed_market_log_loss",
    "closing_market_log_loss",
    "settled_at_utc",
    "settlement_note",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def parse_float(value: object) -> float | None:
    try:
        parsed = float(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def novig_over(over_odds: object, under_odds: object) -> float | None:
    over = parse_float(over_odds)
    under = parse_float(under_odds)
    if over is None or under is None or over <= 1.0 or under <= 1.0:
        return None
    over_raw = 1.0 / over
    under_raw = 1.0 / under
    return over_raw / (over_raw + under_raw)


def conditional_model_over(row: dict[str, str]) -> float | None:
    over = parse_float(row.get("fair_p_over"))
    under = parse_float(row.get("fair_p_under"))
    if over is None or under is None or over + under <= 0:
        return None
    return over / (over + under)


def observation_id(row: dict[str, str]) -> str:
    event_id = str(row.get("event_id") or "").strip()
    identity = event_id or "|".join(
        [
            str(row.get("date") or "").strip(),
            str(row.get("tour") or "").upper(),
            *SETTLE.pair_key(row.get("player"), row.get("opponent")),
        ]
    )
    return "|".join([identity, SETTLE.norm_text(row.get("market"))])


def is_clean_main_line(row: dict[str, str]) -> bool:
    return (
        str(row.get("scope") or "").lower() == "match_total"
        and str(row.get("market") or "").lower() in {"match_aces", "match_double_faults"}
        and str(row.get("matched_board") or "").lower() == "yes"
        and str(row.get("price_pair_status") or "").lower() == "two_way"
        and str(row.get("line_quality") or "").lower() == "complete"
        and str(row.get("main_line") or "").lower() == "true"
        and parse_float(row.get("line")) is not None
        and novig_over(row.get("over_odds"), row.get("under_odds")) is not None
    )


def build_observation(row: dict[str, str], source: Path, now: str) -> dict[str, str]:
    opening_prob = novig_over(row.get("over_odds"), row.get("under_odds"))
    model_prob = conditional_model_over(row)
    return {
        "observation_id": observation_id(row),
        "first_seen_utc": now,
        "date": str(row.get("date") or ""),
        "tour": str(row.get("tour") or "").upper(),
        "tournament": str(row.get("tournament") or ""),
        "surface": str(row.get("surface") or ""),
        "player": str(row.get("player") or ""),
        "opponent": str(row.get("opponent") or ""),
        "market": str(row.get("market") or ""),
        "line": str(row.get("line") or ""),
        "bookmaker": str(row.get("bookmaker") or "Bet365"),
        "event_id": str(row.get("event_id") or ""),
        "observed_capture_ts": str(row.get("capture_ts") or ""),
        "match_start_utc": str(row.get("match_start_utc") or ""),
        "observed_over_odds": str(row.get("over_odds") or ""),
        "observed_under_odds": str(row.get("under_odds") or ""),
        "observed_novig_p_over": fmt(opening_prob),
        "projection_mean": str(row.get("projection_mean") or ""),
        "projection_p1": str(row.get("projection_p1") or ""),
        "projection_p2": str(row.get("projection_p2") or ""),
        "model_p_over_conditional": fmt(model_prob),
        "fair_p_push": str(row.get("fair_p_push") or ""),
        "distribution": str(row.get("distribution") or "negative_binomial"),
        "totals_alpha": str(row.get("totals_alpha") or ""),
        "confidence": str(row.get("confidence") or ""),
        "p1_confidence": str(row.get("p1_confidence") or ""),
        "p2_confidence": str(row.get("p2_confidence") or ""),
        "combined_surface_svpt_sample": str(row.get("combined_surface_svpt_sample") or ""),
        "notes": str(row.get("notes") or ""),
        "source_file": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
        "settlement_status": "pending",
    }


def backfill_metadata(observation: dict[str, str], candidate: dict[str, str]) -> None:
    """Fill newly available descriptors without rewriting first-seen prices/model state."""
    for field in (
        "surface",
        "tournament",
        "match_start_utc",
        "p1_confidence",
        "p2_confidence",
        "combined_surface_svpt_sample",
        "notes",
    ):
        if not observation.get(field) and candidate.get(field):
            observation[field] = str(candidate[field])


def latest_comparison() -> Path | None:
    candidates = [
        path
        for path in PROPS_DIR.glob("comparison-*.csv")
        if "unmatched" not in path.name and "comparison-v3" not in path.name
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def enrich_closing_pair(
    row: dict[str, str],
    by_event: dict[tuple[object, ...], list[dict[str, str]]],
    by_pair: dict[tuple[object, ...], list[dict[str, str]]],
) -> bool:
    match_start = SETTLE.parse_utc_datetime(row.get("match_start_utc"))
    if match_start is None:
        return False
    lookup = {
        **row,
        "capture_ts": row.get("observed_capture_ts", ""),
        "over_odds": row.get("observed_over_odds", ""),
        "under_odds": row.get("observed_under_odds", ""),
    }
    candidates = by_event.get(SETTLE.history_key(lookup), [])
    method = "event_id_latest_prestart"
    if not candidates:
        candidates = by_pair.get(SETTLE.history_key(lookup, fallback=True), [])
        method = "pair_latest_prestart"
    priced: list[tuple[datetime, float, float]] = []
    for candidate in candidates:
        captured_at = SETTLE.parse_utc_datetime(candidate.get("capture_ts"))
        over = parse_float(candidate.get("over_odds"))
        under = parse_float(candidate.get("under_odds"))
        if (
            captured_at is None
            or captured_at > match_start
            or over is None
            or under is None
            or over <= 1.0
            or under <= 1.0
        ):
            continue
        priced.append((captured_at, over, under))
    if not priced:
        return False
    priced.sort(key=lambda item: item[0])
    closing_ts, over, under = priced[-1]
    row["closing_over_odds"] = fmt(over, 4)
    row["closing_under_odds"] = fmt(under, 4)
    row["closing_novig_p_over"] = fmt(novig_over(over, under))
    row["closing_ts_utc"] = closing_ts.isoformat(timespec="seconds")
    row["closing_snapshot_count"] = str(len({item[0] for item in priced}))
    row["close_method"] = method
    return True


def implied_mean(
    *,
    line: float,
    target_over: float,
    distribution: str,
    alpha: float | None,
    tour: str,
    market: str,
) -> float | None:
    if not 0.0 < target_over < 1.0:
        return None

    def probability(mean: float) -> float:
        over, under, _push = count_line_probabilities(
            line,
            mean,
            distribution=distribution,
            alpha=alpha,
            tour=tour,
            market=market,
        )
        return over / (over + under) if over + under > 0 else 0.0

    low = 1e-4
    high = max(20.0, line * 4.0 + 20.0)
    while probability(high) < target_over and high < 500.0:
        high *= 2.0
    if probability(high) < target_over:
        return None
    for _ in range(80):
        midpoint = (low + high) * 0.5
        if probability(midpoint) < target_over:
            low = midpoint
        else:
            high = midpoint
    return (low + high) * 0.5


def binary_metrics(probability: float | None, outcome: int) -> tuple[float | None, float | None]:
    if probability is None:
        return None, None
    probability = max(1e-9, min(1.0 - 1e-9, probability))
    return (probability - outcome) ** 2, -(
        outcome * math.log(probability) + (1 - outcome) * math.log(1.0 - probability)
    )


def score_settled_row(row: dict[str, str]) -> None:
    actual = parse_float(row.get("actual"))
    line = parse_float(row.get("line"))
    projection = parse_float(row.get("projection_mean"))
    opening_prob = parse_float(row.get("observed_novig_p_over"))
    closing_prob = parse_float(row.get("closing_novig_p_over"))
    model_prob = parse_float(row.get("model_p_over_conditional"))
    alpha = parse_float(row.get("totals_alpha"))
    if actual is None or line is None:
        return

    if projection is not None:
        row["model_count_abs_error"] = fmt(abs(actual - projection), 3)
    opening_mean = implied_mean(
        line=line,
        target_over=opening_prob or 0.0,
        distribution=row.get("distribution") or "negative_binomial",
        alpha=alpha,
        tour=row.get("tour") or "",
        market=row.get("market") or "",
    )
    closing_mean = implied_mean(
        line=line,
        target_over=closing_prob or 0.0,
        distribution=row.get("distribution") or "negative_binomial",
        alpha=alpha,
        tour=row.get("tour") or "",
        market=row.get("market") or "",
    )
    row["observed_market_implied_mean"] = fmt(opening_mean, 3)
    row["closing_market_implied_mean"] = fmt(closing_mean, 3)
    if opening_mean is not None:
        row["observed_market_count_abs_error"] = fmt(abs(actual - opening_mean), 3)
    if closing_mean is not None:
        row["closing_market_count_abs_error"] = fmt(abs(actual - closing_mean), 3)

    if actual == line:
        row["outcome_over"] = "push"
        return
    outcome = int(actual > line)
    row["outcome_over"] = str(outcome)
    for prefix, probability in (
        ("model", model_prob),
        ("observed_market", opening_prob),
        ("closing_market", closing_prob),
    ):
        brier, log_loss = binary_metrics(probability, outcome)
        row[f"{prefix}_brier"] = fmt(brier)
        row[f"{prefix}_log_loss"] = fmt(log_loss)


def settle_rows(
    rows: list[dict[str, str]],
    *,
    sackmann_dir: Path,
    oncourt_dir: Path,
    history_paths: list[Path],
) -> tuple[int, int]:
    history_by_event, history_by_pair = SETTLE.load_price_history(history_paths)
    close_updates = sum(enrich_closing_pair(row, history_by_event, history_by_pair) for row in rows)
    pending = [row for row in rows if (row.get("settlement_status") or "pending").lower() in {"", "pending"}]
    oncourt_index = SETTLE.load_oncourt_index(oncourt_dir, pending)
    sackmann_index = SETTLE.load_sackmann_index(sackmann_dir)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    settled_now = 0
    for row in pending:
        year = SETTLE.parse_year(row.get("date"))
        tour = (row.get("tour") or "").upper()
        if year is None or tour not in {"ATP", "WTA"}:
            row["settlement_note"] = "missing_tour_or_year"
            continue
        key = (tour, year, SETTLE.pair_key(row.get("player"), row.get("opponent")))
        candidates = oncourt_index.get(key, []) or sackmann_index.get(key, [])
        candidate = SETTLE.choose_candidate(row, candidates)
        if candidate is None:
            row["settlement_note"] = "match_ambiguous" if candidates else "match_not_found"
            continue
        if SETTLE.is_void_score(candidate.get("score")):
            row["settlement_status"] = "void"
            row["settled_at_utc"] = now
            row["settlement_note"] = f"void_score:{candidate.get('score', '')}"
            settled_now += 1
            continue
        actual, note = SETTLE.market_count(candidate, SETTLE.norm_text(row.get("player")), row.get("market", ""))
        if actual is None:
            row["settlement_note"] = note
            continue
        row["settlement_status"] = "settled"
        row["actual"] = str(actual)
        row["settled_at_utc"] = now
        source = candidate.get("_settlement_source") or "sackmann"
        row["settlement_note"] = f"{source}:{candidate.get('tourney_name', '')}:{candidate.get('score', '')}"
        score_settled_row(row)
        settled_now += 1
    for row in rows:
        if (row.get("settlement_status") or "").lower() == "settled":
            score_settled_row(row)
    return settled_now, close_updates


def mean_field(rows: list[dict[str, str]], field: str) -> float | None:
    values = [parse_float(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def metric_line(label: str, rows: list[dict[str, str]]) -> str:
    settled = [row for row in rows if row.get("settlement_status") == "settled"]
    scored = [row for row in settled if row.get("outcome_over") in {"0", "1"}]
    model_mae = mean_field(settled, "model_count_abs_error")
    open_mae = mean_field(settled, "observed_market_count_abs_error")
    close_mae = mean_field(settled, "closing_market_count_abs_error")
    model_brier = mean_field(scored, "model_brier")
    open_brier = mean_field(scored, "observed_market_brier")
    close_brier = mean_field(scored, "closing_market_brier")
    delta = (open_brier - model_brier) if open_brier is not None and model_brier is not None else None
    return (
        f"  {label}: observations={len(rows)} settled={len(settled)} scored={len(scored)} | "
        f"count_MAE model={fmt(model_mae, 3) or '-'} open={fmt(open_mae, 3) or '-'} close={fmt(close_mae, 3) or '-'} | "
        f"Brier model={fmt(model_brier, 4) or '-'} open={fmt(open_brier, 4) or '-'} close={fmt(close_brier, 4) or '-'} "
        f"delta_vs_open={fmt(delta, 4) or '-'}"
    )


def write_report(path: Path, rows: list[dict[str, str]]) -> None:
    settled = [row for row in rows if row.get("settlement_status") == "settled"]
    pending = [row for row in rows if (row.get("settlement_status") or "pending") == "pending"]
    voids = [row for row in rows if row.get("settlement_status") == "void"]
    scored = [row for row in settled if row.get("outcome_over") in {"0", "1"}]
    model_brier = mean_field(scored, "model_brier")
    open_brier = mean_field(scored, "observed_market_brier")
    brier_delta = (open_brier - model_brier) if open_brier is not None and model_brier is not None else None
    gate = "EVIDENCE BUILDING" if len(settled) < 100 else "REVIEW REQUIRED"
    lines = [
        "Tennis props model vs Bet365 market benchmark",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "Status: observational research only; this report cannot publish, stake or change model parameters.",
        f"Gate: {gate} | minimum 100 settled clean main lines before any challenger experiment is proposed.",
        f"Observations: {len(rows)} | settled: {len(settled)} | scored (non-push): {len(scored)} | pending: {len(pending)} | void: {len(voids)}",
        f"Headline Brier delta vs observed Bet365: {fmt(brier_delta, 4) or '-'} (positive means model lower/better)",
        "",
        "Overall:",
        metric_line("all", rows),
    ]
    for label, field in (("By market", "market"), ("By tour", "tour"), ("By surface", "surface")):
        lines.extend(["", f"{label}:"])
        for value in sorted({row.get(field) or "-" for row in rows}):
            subset = [row for row in rows if (row.get(field) or "-") == value]
            lines.append(metric_line(value, subset))
    tournament_counts: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        tournament_counts[row.get("tournament") or "-"].append(row)
    lines.extend(["", "By tournament (settled or active observations):"])
    for tournament, subset in sorted(tournament_counts.items()):
        lines.append(metric_line(tournament, subset))
    lines.extend(
        [
            "",
            "Interpretation:",
            "- Actual counts, not bookmaker prices, are the model target.",
            "- Bet365 opening/closing prices are challenger benchmarks for probability calibration and market disagreement.",
            "- A positive Brier delta is necessary but not sufficient; any parameter change still needs a registered walk-forward holdout.",
            "- Observed open means the first clean main line captured by this system, not the bookmaker's true market open.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe and settle every clean Bet365 ace/DF main line")
    parser.add_argument("--comparison", default="")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--sackmann-dir", default=str(DEFAULT_SACKMANN))
    parser.add_argument("--oncourt-dir", default=str(DEFAULT_ONCOURT))
    parser.add_argument("--history-glob", default=str(PROPS_DIR / "inbox" / "bet365-lines-history-*.csv"))
    args = parser.parse_args()

    comparison = Path(args.comparison) if args.comparison else latest_comparison()
    ledger_path = Path(args.ledger)
    rows = read_csv(ledger_path)
    existing_by_id = {row.get("observation_id"): row for row in rows if row.get("observation_id")}
    appended = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if comparison and comparison.exists():
        for candidate in read_csv(comparison):
            if not is_clean_main_line(candidate):
                continue
            oid = observation_id(candidate)
            if oid in existing_by_id:
                backfill_metadata(existing_by_id[oid], candidate)
                continue
            observation = build_observation(candidate, comparison, now)
            rows.append(observation)
            existing_by_id[oid] = observation
            appended += 1

    history_pattern = Path(args.history_glob)
    history_paths = sorted(history_pattern.parent.glob(history_pattern.name))
    settled_now, close_updates = settle_rows(
        rows,
        sackmann_dir=Path(args.sackmann_dir),
        oncourt_dir=Path(args.oncourt_dir),
        history_paths=history_paths,
    )
    rows.sort(key=lambda row: (row.get("date", ""), row.get("observation_id", "")))
    write_csv(ledger_path, rows)
    write_report(Path(args.report), rows)
    print(
        f"Market observations: appended={appended}; settled/voided={settled_now}; "
        f"close_refreshed={close_updates}; total={len(rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
