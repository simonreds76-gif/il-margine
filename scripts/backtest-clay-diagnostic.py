#!/usr/bin/env python3
"""
Phase 1 diagnostic sweep for ATP clay ML.

This script deliberately reads 2022-2024 only by default. It tests a fixed
filter grid on the existing backtest-results files and joins tennis-data
Pinnacle close prices for open-to-close CLV.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import random
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"
DEFAULT_YEARS = (2022, 2023, 2024)
DEFAULT_OUT_CSV = BACKTEST_DIR / "clay-diagnostic-2022-2024.csv"
DEFAULT_OUT_TXT = BACKTEST_DIR / "clay-diagnostic-2022-2024.txt"

EDGE_BANDS = [
    (3.0, 8.0),
    (4.0, 10.0),
    (5.0, 12.0),
    (5.0, 13.0),
    (6.0, 12.0),
    (7.0, 13.0),
    (7.0, 15.0),
    (10.0, 15.0),
]
DIRECTION_FILTERS = ["agree-with-pinnacle", "disagree-with-pinnacle", "no-filter"]
CONFIDENCE_FILTERS = ["high-only", "high+medium", "all"]
SERIES_FILTERS = ["ATP250", "ATP500", "Masters1000", "ATP-non-Slam"]
SIDE_FILTERS = ["model-fav", "model-dog", "both"]

PASS_MIN_N = 100
PASS_MIN_YEAR_ROI = 0.0
PASS_MIN_CLV = 0.0
PASS_MAX_DELTA_LOG_LOSS = 0.0
PASS_MIN_ROI_BOOT_LB = 0.0
CLV_EPSILON = 1e-8


@dataclass(frozen=True)
class DiagnosticPick:
    year: int
    date_iso: str
    tournament: str
    series: str
    confidence: str
    player1: str
    player2: str
    selected_side: str
    selected_side_filter: str
    direction_filter: str
    edge_pct: float
    open_odds: float
    close_odds: float | None
    pnl: float
    won: bool
    model_fav_prob: float
    pin_fav_prob: float
    model_fav_won: bool
    clv_implied_delta: float | None


def parse_float(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def parse_bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def clean(value: object) -> str:
    return str(value or "").strip()


def clamp_prob(value: float) -> float:
    return max(1e-6, min(1.0 - 1e-6, float(value)))


def log_loss(prob: float, actual: int) -> float:
    p = clamp_prob(prob)
    return -(actual * math.log(p) + (1 - actual) * math.log(1.0 - p))


def brier(prob: float, actual: int) -> float:
    return (clamp_prob(prob) - actual) ** 2


def norm_name(value: object) -> str:
    return " ".join(clean(value).lower().replace("-", " ").split())


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_audit_module() -> Any:
    path = ROOT / "scripts" / "audit-strict-clv.py"
    module_name = "audit_strict_clv_for_clay_diag"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_close_lookup(years: Iterable[int]) -> tuple[dict[tuple[str, int, int], tuple[float, float]], dict[str, Any]]:
    audit_mod = load_audit_module()
    lookup: dict[tuple[str, int, int], tuple[float, float]] = {}
    meta: dict[str, Any] = {
        "files": [],
        "closing_rows_loaded": 0,
        "duplicate_keys": 0,
        "per_file": {},
    }
    for year in years:
        xlsx_path = BACKTEST_DIR / f"atp-{year}.xlsx"
        if not xlsx_path.exists():
            raise FileNotFoundError(f"Missing close-price workbook: {xlsx_path}")
        matches, file_meta = audit_mod.load_closing_matches(xlsx_path)
        meta["files"].append(str(xlsx_path.relative_to(ROOT)))
        meta["per_file"][str(year)] = file_meta
        meta["closing_rows_loaded"] += len(matches)
        for match in matches:
            key = (match.date_iso, int(match.player1_id), int(match.player2_id))
            if key in lookup:
                meta["duplicate_keys"] += 1
            lookup[key] = (float(match.close_odds1), float(match.close_odds2))
    return lookup, meta


def selected_player(row: dict[str, str]) -> str:
    actual_winner = clean(row.get("actual_winner"))
    player1 = clean(row.get("player1"))
    player2 = clean(row.get("player2"))
    if clean(row.get("bet_side")) == "winner":
        return actual_winner
    if actual_winner == player1:
        return player2
    if actual_winner == player2:
        return player1
    return ""


def selected_open_odds(row: dict[str, str]) -> float | None:
    if clean(row.get("bet_side")) == "winner":
        return parse_float(row.get("pinnacle_odds"))
    return parse_float(row.get("pinnacle_odds_loser"))


def selected_close_odds(row: dict[str, str], close_lookup: dict[tuple[str, int, int], tuple[float, float]]) -> float | None:
    date_iso = clean(row.get("date"))[:10]
    p1_id = clean(row.get("player1_id"))
    p2_id = clean(row.get("player2_id"))
    if not date_iso or not p1_id or not p2_id:
        return None
    try:
        key = (date_iso, int(float(p1_id)), int(float(p2_id)))
    except ValueError:
        return None
    close_pair = close_lookup.get(key)
    if close_pair is None:
        rev = close_lookup.get((key[0], key[2], key[1]))
        if rev is None:
            return None
        close_pair = (rev[1], rev[0])
    close_winner, close_loser = close_pair
    return close_winner if clean(row.get("bet_side")) == "winner" else close_loser


def series_bucket(value: str) -> str:
    series = clean(value)
    if series == "Masters 1000":
        return "Masters1000"
    return series


def selected_side_filter(row: dict[str, str]) -> str | None:
    selected = selected_player(row)
    model_favorite = clean(row.get("model_favorite"))
    if not selected or not model_favorite:
        return None
    return "model-fav" if norm_name(selected) == norm_name(model_favorite) else "model-dog"


def direction_filter(row: dict[str, str]) -> str | None:
    actual_winner = clean(row.get("actual_winner"))
    model_favorite = clean(row.get("model_favorite"))
    pin_winner_prob = parse_float(row.get("pinnacle_prob_novig"))
    if not actual_winner or not model_favorite or pin_winner_prob is None:
        return None
    model_fav_side = "winner" if norm_name(model_favorite) == norm_name(actual_winner) else "loser"
    pin_fav_side = "winner" if pin_winner_prob >= 0.5 else "loser"
    return "agree-with-pinnacle" if model_fav_side == pin_fav_side else "disagree-with-pinnacle"


def confidence_allowed(cell_confidence: str, row_confidence: str) -> bool:
    conf = row_confidence.lower()
    if cell_confidence == "all":
        return True
    if cell_confidence == "high+medium":
        return conf in {"high", "medium"}
    return conf == "high"


def series_allowed(cell_series: str, row_series: str) -> bool:
    bucket = series_bucket(row_series)
    if cell_series == "ATP-non-Slam":
        return bucket in {"ATP250", "ATP500", "Masters1000", "Masters Cup"}
    return bucket == cell_series


def row_to_pick(row: dict[str, str], close_lookup: dict[tuple[str, int, int], tuple[float, float]]) -> DiagnosticPick | None:
    if clean(row.get("surface")) != "Clay":
        return None
    if series_bucket(clean(row.get("series"))) == "Grand Slam":
        return None
    if parse_bool(row.get("policy_excluded")):
        return None
    if clean(row.get("bet_result")).lower() not in {"win", "loss"}:
        return None

    date_iso = clean(row.get("date"))[:10]
    try:
        year = int(date_iso[:4])
    except ValueError:
        return None
    if year not in DEFAULT_YEARS:
        return None

    edge_pct = parse_float(row.get("value_pct"))
    open_odds = selected_open_odds(row)
    if edge_pct is None or open_odds is None or open_odds <= 1.0:
        return None

    side_filter = selected_side_filter(row)
    dir_filter = direction_filter(row)
    if side_filter is None or dir_filter is None:
        return None

    actual_winner = clean(row.get("actual_winner"))
    model_favorite = clean(row.get("model_favorite"))
    model_fav_prob = parse_float(row.get("model_favorite_prob"))
    pin_winner_prob = parse_float(row.get("pinnacle_prob_novig"))
    if model_fav_prob is None or pin_winner_prob is None:
        return None
    model_fav_won = norm_name(model_favorite) == norm_name(actual_winner)
    pin_fav_prob = pin_winner_prob if model_fav_won else (1.0 - pin_winner_prob)

    close_odds = selected_close_odds(row, close_lookup)
    clv = None
    if close_odds is not None and close_odds > 1.0:
        clv = (1.0 / close_odds) - (1.0 / open_odds)

    won = clean(row.get("bet_result")).lower() == "win"
    return DiagnosticPick(
        year=year,
        date_iso=date_iso,
        tournament=clean(row.get("tournament")),
        series=clean(row.get("series")),
        confidence=clean(row.get("confidence")).lower(),
        player1=clean(row.get("player1")),
        player2=clean(row.get("player2")),
        selected_side=clean(row.get("bet_side")),
        selected_side_filter=side_filter,
        direction_filter=dir_filter,
        edge_pct=float(edge_pct),
        open_odds=float(open_odds),
        close_odds=float(close_odds) if close_odds is not None else None,
        pnl=(float(open_odds) - 1.0) if won else -1.0,
        won=won,
        model_fav_prob=clamp_prob(float(model_fav_prob)),
        pin_fav_prob=clamp_prob(float(pin_fav_prob)),
        model_fav_won=model_fav_won,
        clv_implied_delta=clv,
    )


def load_picks(years: Iterable[int], close_lookup: dict[tuple[str, int, int], tuple[float, float]]) -> tuple[list[DiagnosticPick], dict[str, int]]:
    stats = Counter()
    picks: list[DiagnosticPick] = []
    for year in years:
        path = BACKTEST_DIR / f"backtest-results-{year}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing backtest file: {path}")
        for row in load_csv(path):
            stats["rows_seen"] += 1
            if clean(row.get("surface")) == "Clay":
                stats["clay_rows_seen"] += 1
            pick = row_to_pick(row, close_lookup)
            if pick is None:
                continue
            stats["rows_used"] += 1
            if pick.close_odds is not None:
                stats["rows_with_close"] += 1
            picks.append(pick)
    return picks, dict(stats)


def pick_matches_cell(
    pick: DiagnosticPick,
    *,
    edge_lo: float,
    edge_hi: float,
    direction: str,
    confidence: str,
    series: str,
    side: str,
) -> bool:
    if not (edge_lo <= pick.edge_pct <= edge_hi):
        return False
    if direction != "no-filter" and pick.direction_filter != direction:
        return False
    if not confidence_allowed(confidence, pick.confidence):
        return False
    if not series_allowed(series, pick.series):
        return False
    if side != "both" and pick.selected_side_filter != side:
        return False
    return True


def roi_bootstrap_ci(picks: list[DiagnosticPick], *, runs: int, seed: int) -> tuple[float, float] | tuple[None, None]:
    if not picks:
        return None, None
    rng = random.Random(seed)
    n = len(picks)
    rois: list[float] = []
    for _ in range(runs):
        pnl = 0.0
        for _i in range(n):
            pnl += picks[rng.randrange(n)].pnl
        rois.append(pnl / n * 100.0)
    rois.sort()
    return rois[int(0.025 * (runs - 1))], rois[int(0.975 * (runs - 1))]


def ece(picks: list[DiagnosticPick]) -> float | None:
    if not picks:
        return None
    bins: dict[int, list[DiagnosticPick]] = {}
    for pick in picks:
        idx = min(9, int(pick.model_fav_prob * 10.0))
        bins.setdefault(idx, []).append(pick)
    total = len(picks)
    acc = 0.0
    for bucket in bins.values():
        avg_prob = mean(pick.model_fav_prob for pick in bucket)
        actual = mean(1.0 if pick.model_fav_won else 0.0 for pick in bucket)
        acc += (len(bucket) / total) * abs(avg_prob - actual)
    return acc


def metrics_for(picks: list[DiagnosticPick], *, bootstrap_runs: int, seed: int) -> dict[str, Any]:
    n = len(picks)
    if not n:
        return {
            "n_bets": 0,
            "wins": 0,
            "losses": 0,
            "roi_flat": "",
            "roi_boot_lb": "",
            "roi_boot_ub": "",
            "log_loss_model": "",
            "log_loss_pinnacle": "",
            "delta_log_loss": "",
            "brier_model": "",
            "brier_pinnacle": "",
            "ece": "",
            "clv_avg": "",
            "clv_pos_rate": "",
            "clv_n": 0,
            "clv_match_rate": "",
        }
    wins = sum(1 for pick in picks if pick.won)
    losses = n - wins
    pnl = sum(pick.pnl for pick in picks)
    lb, ub = roi_bootstrap_ci(picks, runs=bootstrap_runs, seed=seed) if n >= 5 else (None, None)
    model_ll = mean(log_loss(pick.model_fav_prob, 1 if pick.model_fav_won else 0) for pick in picks)
    pin_ll = mean(log_loss(pick.pin_fav_prob, 1 if pick.model_fav_won else 0) for pick in picks)
    model_brier = mean(brier(pick.model_fav_prob, 1 if pick.model_fav_won else 0) for pick in picks)
    pin_brier = mean(brier(pick.pin_fav_prob, 1 if pick.model_fav_won else 0) for pick in picks)
    clv_values = [pick.clv_implied_delta for pick in picks if pick.clv_implied_delta is not None]
    return {
        "n_bets": n,
        "wins": wins,
        "losses": losses,
        "roi_flat": pnl / n * 100.0,
        "roi_boot_lb": lb,
        "roi_boot_ub": ub,
        "log_loss_model": model_ll,
        "log_loss_pinnacle": pin_ll,
        "delta_log_loss": model_ll - pin_ll,
        "brier_model": model_brier,
        "brier_pinnacle": pin_brier,
        "ece": ece(picks),
        "clv_avg": mean(clv_values) * 100.0 if clv_values and any(abs(value) > CLV_EPSILON for value in clv_values) else "",
        "clv_pos_rate": (sum(1 for value in clv_values if value > CLV_EPSILON) / len(clv_values) * 100.0) if clv_values and any(abs(value) > CLV_EPSILON for value in clv_values) else "",
        "clv_n": len(clv_values),
        "clv_match_rate": len(clv_values) / n * 100.0,
        "clv_informative": 1 if clv_values and any(abs(value) > CLV_EPSILON for value in clv_values) else 0,
    }


def fmt_number(value: Any, digits: int = 4) -> Any:
    if value is None or value == "":
        return ""
    return round(float(value), digits)


def cell_id(edge_lo: float, edge_hi: float, direction: str, confidence: str, series: str, side: str) -> str:
    return f"edge{edge_lo:g}-{edge_hi:g}|{direction}|{confidence}|{series}|{side}"


def run_sweep(picks: list[DiagnosticPick], *, bootstrap_runs: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seed_base = 20260514
    for edge_lo, edge_hi in EDGE_BANDS:
        for direction in DIRECTION_FILTERS:
            for confidence in CONFIDENCE_FILTERS:
                for series in SERIES_FILTERS:
                    for side in SIDE_FILTERS:
                        cid = cell_id(edge_lo, edge_hi, direction, confidence, series, side)
                        selected = [
                            pick
                            for pick in picks
                            if pick_matches_cell(
                                pick,
                                edge_lo=edge_lo,
                                edge_hi=edge_hi,
                                direction=direction,
                                confidence=confidence,
                                series=series,
                                side=side,
                            )
                        ]
                        for split in ["pooled_2022_2024", "2022", "2023", "2024"]:
                            split_picks = selected if split == "pooled_2022_2024" else [pick for pick in selected if str(pick.year) == split]
                            metrics = metrics_for(split_picks, bootstrap_runs=bootstrap_runs, seed=seed_base + len(rows))
                            rows.append(
                                {
                                    "cell_id": cid,
                                    "edge_lo": edge_lo,
                                    "edge_hi": edge_hi,
                                    "direction_filter": direction,
                                    "confidence_filter": confidence,
                                    "series_filter": series,
                                    "side_filter": side,
                                    "split": split,
                                    **{key: fmt_number(value) for key, value in metrics.items()},
                                }
                            )
    return rows


def row_passes_pooled(row: dict[str, Any], by_year: dict[str, dict[str, Any]]) -> bool:
    if row["split"] != "pooled_2022_2024":
        return False
    if int(row["n_bets"] or 0) < PASS_MIN_N:
        return False
    if row["roi_boot_lb"] == "" or float(row["roi_boot_lb"]) <= PASS_MIN_ROI_BOOT_LB:
        return False
    if row["delta_log_loss"] == "" or float(row["delta_log_loss"]) > PASS_MAX_DELTA_LOG_LOSS:
        return False
    if int(row.get("clv_informative") or 0) <= 0:
        return False
    if row["clv_avg"] == "" or float(row["clv_avg"]) < PASS_MIN_CLV:
        return False
    for year in ("2022", "2023", "2024"):
        year_row = by_year.get(year)
        if not year_row or year_row["roi_flat"] == "" or float(year_row["roi_flat"]) <= PASS_MIN_YEAR_ROI:
            return False
    return True


def passing_cells(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["cell_id"]), {})[str(row["split"])] = row
    passes = []
    for cid, split_rows in grouped.items():
        pooled = split_rows.get("pooled_2022_2024")
        if pooled and row_passes_pooled(pooled, split_rows):
            passes.append(pooled)
    passes.sort(key=lambda row: (float(row["roi_boot_lb"]), float(row["roi_flat"]), int(row["n_bets"])), reverse=True)
    return passes


def top_rows(
    rows: list[dict[str, Any]],
    *,
    sort_key: str,
    reverse: bool,
    min_n: int = PASS_MIN_N,
    limit: int = 20,
) -> list[dict[str, Any]]:
    pooled = [
        row
        for row in rows
        if row["split"] == "pooled_2022_2024"
        and int(row["n_bets"] or 0) >= min_n
        and row.get(sort_key) != ""
    ]
    pooled.sort(key=lambda row: float(row[sort_key]), reverse=reverse)
    return pooled[:limit]


def fmt_pct(value: Any, digits: int = 2) -> str:
    if value == "" or value is None:
        return "n/a"
    return f"{float(value):+.{digits}f}%"


def fmt_metric(value: Any, digits: int = 4) -> str:
    if value == "" or value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def render_row(row: dict[str, Any]) -> str:
    return (
        f"{row['cell_id']} | n={int(row['n_bets'])} | "
        f"ROI={fmt_pct(row['roi_flat'])} | bootLB={fmt_pct(row['roi_boot_lb'])} | "
        f"dLL={fmt_metric(row['delta_log_loss'])} | ECE={fmt_metric(row['ece'])} | "
        f"CLV={fmt_pct(row['clv_avg'])} | CLV+={fmt_pct(row['clv_pos_rate'])}"
    )


def build_report(
    rows: list[dict[str, Any]],
    *,
    picks: list[DiagnosticPick],
    load_stats: dict[str, int],
    close_meta: dict[str, Any],
    bootstrap_runs: int,
) -> str:
    lines = [
        "Clay ML Diagnostic Sweep 2022-2024",
        f"Generated UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "Scope",
        "- Reads only `backtest-results-2022.csv`, `backtest-results-2023.csv`, `backtest-results-2024.csv`.",
        "- Joins close prices from `atp-2022.xlsx`, `atp-2023.xlsx`, `atp-2024.xlsx`.",
        "- 2025 is not read in this phase.",
        "- Policy-excluded rows are excluded from the sweep.",
        "- CLV is marked unavailable when the joined close odds are identical to the backtest odds.",
        f"- Grid size: {len(EDGE_BANDS) * len(DIRECTION_FILTERS) * len(CONFIDENCE_FILTERS) * len(SERIES_FILTERS) * len(SIDE_FILTERS)} cells x 4 splits.",
        f"- Bootstrap runs per aggregate: {bootstrap_runs}.",
        "",
        "Load Stats",
        f"- Rows seen: {load_stats.get('rows_seen', 0):,}",
        f"- Clay rows seen: {load_stats.get('clay_rows_seen', 0):,}",
        f"- Rows used after base safety filters: {load_stats.get('rows_used', 0):,}",
        f"- Rows with close-price join: {load_stats.get('rows_with_close', 0):,}/{len(picks):,}",
        f"- Rows with non-zero CLV after close join: {sum(1 for pick in picks if pick.clv_implied_delta is not None and abs(pick.clv_implied_delta) > CLV_EPSILON):,}/{len(picks):,}",
        f"- Closing rows loaded: {close_meta.get('closing_rows_loaded', 0):,}",
        f"- Close duplicate keys: {close_meta.get('duplicate_keys', 0):,}",
        "",
        "Pass Criteria",
        "- N >= 100 on pooled 2022-2024.",
        "- ROI bootstrap 95% lower bound > 0 on pooled 2022-2024.",
        "- Model log-loss delta vs Pinnacle <= 0 on pooled 2022-2024.",
        "- Average CLV >= 0 on pooled 2022-2024, and the CLV join must be non-degenerate.",
        "- ROI > 0 in each of 2022, 2023, and 2024.",
        "",
    ]

    passes = passing_cells(rows)
    lines.append("Passing Cells")
    if not passes:
        lines.append("- none")
    else:
        for row in passes[:30]:
            lines.append(f"- {render_row(row)}")
    lines.append("")

    sections = [
        ("Top 20 by pooled ROI", top_rows(rows, sort_key="roi_flat", reverse=True)),
        ("Top 20 by delta log-loss vs Pinnacle", top_rows(rows, sort_key="delta_log_loss", reverse=False)),
        ("Top 20 by CLV-positive rate", top_rows(rows, sort_key="clv_pos_rate", reverse=True)),
        ("Top 20 by bootstrap lower bound", top_rows(rows, sort_key="roi_boot_lb", reverse=True)),
    ]
    for title, section_rows in sections:
        lines.append(title)
        if not section_rows:
            lines.append("- none")
        for row in section_rows:
            lines.append(f"- {render_row(row)}")
        lines.append("")

    lines.append("Interpretation")
    if passes:
        lines.append("- At least one 2022-2024 cell passed the locked Phase 1 gates. Lock the best cell before any 2025 sealed touch.")
    else:
        lines.append("- No 2022-2024 cell passed the locked Phase 1 gates. Do not touch 2025; current clay ML output is not salvageable by this fixed grid.")
    if not any(pick.clv_implied_delta is not None and abs(pick.clv_implied_delta) > CLV_EPSILON for pick in picks):
        lines.append("- Historical CLV is not informative here: the backtest odds equal the tennis-data close odds, so there is no true open-close movement in these files.")
    lines.append("- Spread/handicap and totals remain out of scope because 2022-2024 line history is not available in repo data.")
    lines.append("- Challenger remains out of scope because the historical ATP backtest files contain no Challenger odds rows.")
    return "\n".join(lines).rstrip() + "\n"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "cell_id",
        "edge_lo",
        "edge_hi",
        "direction_filter",
        "confidence_filter",
        "series_filter",
        "side_filter",
        "split",
        "n_bets",
        "wins",
        "losses",
        "roi_flat",
        "roi_boot_lb",
        "roi_boot_ub",
        "log_loss_model",
        "log_loss_pinnacle",
        "delta_log_loss",
        "brier_model",
        "brier_pinnacle",
        "ece",
        "clv_avg",
        "clv_pos_rate",
        "clv_n",
        "clv_match_rate",
        "clv_informative",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fixed-grid clay ML diagnostic sweep on 2022-2024 only.")
    parser.add_argument("--years", nargs="*", type=int, default=list(DEFAULT_YEARS), help="Allowed diagnostic years. Default: 2022 2023 2024.")
    parser.add_argument("--bootstrap-runs", type=int, default=1000)
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-txt", default=str(DEFAULT_OUT_TXT))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    years = tuple(sorted(set(args.years)))
    if years != DEFAULT_YEARS:
        raise SystemExit("Phase 1 is locked to 2022 2023 2024 only. Do not pass 2025 to this script.")
    if args.bootstrap_runs <= 0:
        raise SystemExit("--bootstrap-runs must be positive")

    close_lookup, close_meta = load_close_lookup(years)
    picks, load_stats = load_picks(years, close_lookup)
    rows = run_sweep(picks, bootstrap_runs=args.bootstrap_runs)
    report = build_report(rows, picks=picks, load_stats=load_stats, close_meta=close_meta, bootstrap_runs=args.bootstrap_runs)

    print(report)
    if not args.dry_run:
        out_csv = Path(args.out_csv)
        out_txt = Path(args.out_txt)
        if not out_csv.is_absolute():
            out_csv = ROOT / out_csv
        if not out_txt.is_absolute():
            out_txt = ROOT / out_txt
        write_csv(out_csv, rows)
        out_txt.parent.mkdir(parents=True, exist_ok=True)
        out_txt.write_text(report, encoding="utf-8")
        print(f"Wrote CSV -> {out_csv}")
        print(f"Wrote TXT -> {out_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
