#!/usr/bin/env python3
"""Diagnose ATP clay ML calibration without touching live signal files.

The goal is to understand whether the clay-calibrated ML lane is structurally
well-priced before re-enabling any shadow generation. The script deliberately
uses 2022-2025 only by default and reports any 2026 rows as skipped so the
current season remains sealed for future evaluation.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"
DEFAULT_BACKTEST_FILES = [
    BACKTEST_DIR / "backtest-results-2022.csv",
    BACKTEST_DIR / "backtest-results-2023.csv",
    BACKTEST_DIR / "backtest-results-2024.csv",
    BACKTEST_DIR / "backtest-results-2025.csv",
]
DEFAULT_SIGNAL_GLOBS = [
    "strict-signals-claycal*.csv",
    "strict-signals-clay-cal*.csv",
    "strict-signals.csv",
]
DEFAULT_REPORT = BACKTEST_DIR / "clay-ml-calibration-analysis.txt"
DEFAULT_CURVE = BACKTEST_DIR / "clay-ml-calibration-analysis.csv"


def clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def parse_float(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def norm_name(value: Any) -> str:
    return " ".join(clean_text(value).lower().replace("-", " ").split())


def clamp_prob(value: float) -> float:
    return max(1e-6, min(1.0 - 1e-6, value))


def log_loss(prob: float, actual: int) -> float:
    p = clamp_prob(prob)
    return -(actual * math.log(p) + (1 - actual) * math.log(1.0 - p))


def brier(prob: float, actual: int) -> float:
    return (prob - actual) ** 2


def prob_bin(prob: float, width: float) -> tuple[float, float]:
    lo = math.floor(clamp_prob(prob) / width) * width
    lo = max(0.0, min(1.0 - width, lo))
    return round(lo, 4), round(lo + width, 4)


def dataset_for(match_date: date) -> str | None:
    if match_date.year in (2022, 2023):
        return "train"
    if match_date.year == 2024:
        return "validation"
    if match_date.year == 2025:
        return "holdout"
    return None


def tournament_cohort(tournament: str, match_date: date | None) -> str:
    key = clean_text(tournament).lower()
    if "monte carlo" in key:
        return "Monte Carlo"
    if "madrid" in key:
        return "Madrid"
    if "rome" in key or "internazionali" in key or "italian open" in key:
        return "Rome"
    if "roland garros" in key or "french open" in key:
        return "Roland Garros"
    if match_date and match_date.month <= 3:
        return "Early clay"
    if match_date and match_date.month >= 7:
        return "Late clay"
    return "Other clay"


@dataclass(frozen=True)
class CalibrationObs:
    source: str
    dataset: str
    match_date: date
    tournament: str
    series: str
    favorite: str
    raw_prob: float
    cal_prob: float
    pinnacle_prob: float
    actual: int


@dataclass(frozen=True)
class SignalObs:
    source: str
    match_date: date
    cohort: str
    series: str
    prob: float | None
    value_pct: float | None
    stake: float
    pnl: float
    outcome: str




def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def observation_from_backtest(row: dict[str, str], source: str) -> CalibrationObs | None:
    if clean_text(row.get("surface")).lower() != "clay":
        return None
    match_date = parse_date(row.get("date"))
    if match_date is None:
        return None
    dataset = dataset_for(match_date)
    if dataset is None:
        return None

    player1 = clean_text(row.get("player1"))
    player2 = clean_text(row.get("player2"))
    actual_winner = norm_name(row.get("actual_winner"))
    p1_cal = parse_float(row.get("our_prob"))
    p1_raw = parse_float(row.get("our_prob_raw")) or p1_cal
    p1_pin = parse_float(row.get("pinnacle_prob_novig"))
    if not player1 or not player2 or p1_cal is None or p1_raw is None or p1_pin is None:
        return None

    favorite = clean_text(row.get("model_favorite"))
    if not favorite:
        favorite = player1 if p1_cal >= 0.5 else player2
    favorite_key = norm_name(favorite)
    if favorite_key == norm_name(player1):
        raw_prob = p1_raw
        cal_prob = parse_float(row.get("model_favorite_prob")) or p1_cal
        pinnacle_prob = p1_pin
    elif favorite_key == norm_name(player2):
        raw_prob = 1.0 - p1_raw
        cal_prob = parse_float(row.get("model_favorite_prob")) or (1.0 - p1_cal)
        pinnacle_prob = 1.0 - p1_pin
    else:
        return None

    actual = 1 if actual_winner == favorite_key else 0
    return CalibrationObs(
        source=source,
        dataset=dataset,
        match_date=match_date,
        tournament=clean_text(row.get("tournament")),
        series=clean_text(row.get("series"), "Unknown"),
        favorite=favorite,
        raw_prob=clamp_prob(raw_prob),
        cal_prob=clamp_prob(cal_prob),
        pinnacle_prob=clamp_prob(pinnacle_prob),
        actual=actual,
    )


def load_backtest_observations(paths: Iterable[Path]) -> tuple[list[CalibrationObs], dict[str, int]]:
    observations: list[CalibrationObs] = []
    stats = {"files_seen": 0, "rows_seen": 0, "rows_used": 0, "rows_skipped_2026_plus": 0}
    for path in paths:
        rows, _fieldnames = read_csv(path)
        if not rows:
            continue
        stats["files_seen"] += 1
        for row in rows:
            stats["rows_seen"] += 1
            match_date = parse_date(row.get("date"))
            if match_date and match_date.year >= 2026:
                stats["rows_skipped_2026_plus"] += 1
                continue
            obs = observation_from_backtest(row, str(path.relative_to(ROOT)))
            if obs is None:
                continue
            observations.append(obs)
            stats["rows_used"] += 1
    return observations, stats


def aggregate_curve(
    observations: list[CalibrationObs],
    *,
    bin_width: float,
    min_bin_n: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    curve_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    group_keys = [("overall", "all")]
    for series in sorted({obs.series for obs in observations}):
        group_keys.append(("series", series))

    for dataset in ("train", "validation", "holdout"):
        dataset_obs = [obs for obs in observations if obs.dataset == dataset]
        for group_type, group_value in group_keys:
            group_obs = dataset_obs if group_type == "overall" else [obs for obs in dataset_obs if obs.series == group_value]
            if not group_obs:
                continue

            bins: dict[tuple[float, float], list[CalibrationObs]] = {}
            for obs in group_obs:
                bins.setdefault(prob_bin(obs.cal_prob, bin_width), []).append(obs)

            included_for_ece = 0
            ece_sum = 0.0
            for (lo, hi), rows in sorted(bins.items()):
                n = len(rows)
                avg_raw = sum(obs.raw_prob for obs in rows) / n
                avg_cal = sum(obs.cal_prob for obs in rows) / n
                avg_pin = sum(obs.pinnacle_prob for obs in rows) / n
                actual = sum(obs.actual for obs in rows) / n
                abs_error = abs(avg_cal - actual)
                if n >= min_bin_n:
                    included_for_ece += n
                    ece_sum += n * abs_error
                curve_rows.append(
                    {
                        "dataset": dataset,
                        "group_type": group_type,
                        "group": group_value,
                        "bin_lo": f"{lo:.2f}",
                        "bin_hi": f"{hi:.2f}",
                        "n": n,
                        "avg_raw_prob": f"{avg_raw:.4f}",
                        "avg_cal_prob": f"{avg_cal:.4f}",
                        "actual_win_rate": f"{actual:.4f}",
                        "avg_pinnacle_novig": f"{avg_pin:.4f}",
                        "abs_error": f"{abs_error:.4f}",
                        "included_in_ece": "1" if n >= min_bin_n else "0",
                    }
                )

            n_all = len(group_obs)
            metric_rows.append(
                {
                    "dataset": dataset,
                    "group_type": group_type,
                    "group": group_value,
                    "n": n_all,
                    "ece": (ece_sum / included_for_ece) if included_for_ece else None,
                    "ece_n": included_for_ece,
                    "log_loss_cal": sum(log_loss(obs.cal_prob, obs.actual) for obs in group_obs) / n_all,
                    "log_loss_pinnacle": sum(log_loss(obs.pinnacle_prob, obs.actual) for obs in group_obs) / n_all,
                    "brier_cal": sum(brier(obs.cal_prob, obs.actual) for obs in group_obs) / n_all,
                    "brier_pinnacle": sum(brier(obs.pinnacle_prob, obs.actual) for obs in group_obs) / n_all,
                }
            )

    return curve_rows, metric_rows


def find_signal_files(input_dir: Path, globs: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in globs:
        paths.extend(input_dir.glob(pattern))
    return sorted(set(path for path in paths if path.exists()))


def is_claycal_signal_row(row: dict[str, str], path: Path) -> bool:
    name = path.name.lower()
    profile = clean_text(row.get("signal_profile")).lower()
    if "claycal" in name or "clay-cal" in name:
        return True
    return profile == "clay_calibrated"


def signal_probability(row: dict[str, str]) -> float | None:
    side = clean_text(row.get("side")).upper()
    if side in {"P1", "P1+"}:
        odds = parse_float(row.get("our_odds1"))
    elif side in {"P2", "P2-"}:
        odds = parse_float(row.get("our_odds2"))
    else:
        odds = parse_float(row.get("our_odds"))
    if odds is None or odds <= 1.0:
        return None
    return clamp_prob(1.0 / odds)


def signal_pnl(row: dict[str, str]) -> tuple[float | None, float]:
    explicit = parse_float(row.get("pnl_units"))
    stake = parse_float(row.get("stake_units")) or 1.0
    if explicit is not None:
        return explicit, stake

    outcome = clean_text(row.get("bet_outcome") or row.get("result")).lower()
    if outcome in {"void", "push"}:
        return 0.0, stake
    if outcome not in {"won", "win", "lost", "loss"}:
        return None, stake

    side = clean_text(row.get("side")).upper()
    odds = parse_float(row.get("pin_odds1" if side in {"P1", "P1+"} else "pin_odds2"))
    if odds is None or odds <= 1.0:
        return None, stake
    return (stake * (odds - 1.0) if outcome in {"won", "win"} else -stake), stake


def load_signal_observations(input_dir: Path, globs: Iterable[str]) -> tuple[list[SignalObs], list[str]]:
    observations: list[SignalObs] = []
    files = find_signal_files(input_dir, globs)
    for path in files:
        rows, _fieldnames = read_csv(path)
        for row in rows:
            if not is_claycal_signal_row(row, path):
                continue
            if clean_text(row.get("surface")).lower() != "clay":
                continue
            match_date = parse_date(row.get("match_date") or row.get("date"))
            if match_date is None or match_date.year >= 2026:
                continue
            status = clean_text(row.get("settlement_status") or row.get("settled")).lower()
            outcome = clean_text(row.get("bet_outcome") or row.get("result")).lower()
            if status not in {"settled", "1", "true", "yes"} and outcome not in {"won", "win", "lost", "loss", "void", "push"}:
                continue
            pnl, stake = signal_pnl(row)
            if pnl is None:
                continue
            observations.append(
                SignalObs(
                    source=str(path.relative_to(ROOT)),
                    match_date=match_date,
                    cohort=tournament_cohort(clean_text(row.get("tournament")), match_date),
                    series=clean_text(row.get("series"), "Unknown"),
                    prob=signal_probability(row),
                    value_pct=parse_float(row.get("value_pct")),
                    stake=stake,
                    pnl=pnl,
                    outcome=outcome,
                )
            )
    return observations, [str(path.relative_to(ROOT)) for path in files]


def summarize_signals(observations: list[SignalObs], key_func) -> list[dict[str, Any]]:
    grouped: dict[str, list[SignalObs]] = {}
    for obs in observations:
        grouped.setdefault(key_func(obs), []).append(obs)
    rows: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items()):
        stake = sum(obs.stake for obs in group)
        pnl = sum(obs.pnl for obs in group)
        wins = sum(1 for obs in group if obs.outcome in {"won", "win"})
        losses = sum(1 for obs in group if obs.outcome in {"lost", "loss"})
        rows.append(
            {
                "segment": key,
                "n": len(group),
                "wins": wins,
                "losses": losses,
                "pnl": pnl,
                "roi": (pnl / stake * 100.0) if stake else 0.0,
            }
        )
    return rows


def format_float(value: float | None, digits: int = 4) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def write_curve(path: Path, curve_rows: list[dict[str, Any]]) -> None:
    fields = [
        "dataset",
        "group_type",
        "group",
        "bin_lo",
        "bin_hi",
        "n",
        "avg_raw_prob",
        "avg_cal_prob",
        "actual_win_rate",
        "avg_pinnacle_novig",
        "abs_error",
        "included_in_ece",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(curve_rows)


def write_report(
    path: Path,
    *,
    backtest_paths: list[Path],
    backtest_stats: dict[str, int],
    metric_rows: list[dict[str, Any]],
    signal_files: list[str],
    signal_obs: list[SignalObs],
    curve_path: Path,
    min_bin_n: int,
) -> None:
    lines: list[str] = []
    lines.append("Tennis Clay ML Calibration Analysis")
    lines.append("=" * 40)
    lines.append(f"Generated UTC: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}")
    lines.append("")
    lines.append("Inputs")
    for input_path in backtest_paths:
        lines.append(f"- {repo_path(input_path)}")
    lines.append(f"- Curve CSV: {repo_path(curve_path)}")
    lines.append("")
    lines.append("Sealed-data rule")
    lines.append("- Default run uses 2022-2025 only.")
    lines.append(f"- 2026+ rows skipped: {backtest_stats.get('rows_skipped_2026_plus', 0)}")
    lines.append("- Do not use 2026 for parameter selection.")
    lines.append("")
    lines.append("Backtest rows")
    lines.append(f"- Files loaded: {backtest_stats.get('files_seen', 0)}")
    lines.append(f"- Rows seen: {backtest_stats.get('rows_seen', 0):,}")
    lines.append(f"- Clay favourite observations used: {backtest_stats.get('rows_used', 0):,}")
    lines.append("")
    lines.append(f"Calibration metrics (ECE includes bins with n >= {min_bin_n})")
    lines.append("dataset      group        n     ece    ll_model  ll_pin   brier_model  brier_pin")
    for row in metric_rows:
        if row["group_type"] != "overall":
            continue
        lines.append(
            f"{row['dataset']:<12} {row['group']:<8} {row['n']:>5} "
            f"{format_float(row['ece']):>7} {row['log_loss_cal']:>9.4f} "
            f"{row['log_loss_pinnacle']:>7.4f} {row['brier_cal']:>12.4f} {row['brier_pinnacle']:>10.4f}"
        )
    lines.append("")
    lines.append("Per-series calibration metrics")
    lines.append("dataset      series          n     ece    ll_model  ll_pin")
    for row in metric_rows:
        if row["group_type"] != "series":
            continue
        lines.append(
            f"{row['dataset']:<12} {row['group']:<14} {row['n']:>5} "
            f"{format_float(row['ece']):>7} {row['log_loss_cal']:>9.4f} {row['log_loss_pinnacle']:>7.4f}"
        )
    lines.append("")
    lines.append("Clay-calibrated signal archive")
    if signal_files:
        for signal_file in signal_files:
            lines.append(f"- scanned: {signal_file}")
    else:
        lines.append("- no matching strict-signals-claycal*.csv files found")
    if not signal_obs:
        lines.append("- no settled pre-2026 clay_calibrated archive rows found; ROI by bin/series/cohort cannot be evaluated yet")
    else:
        total_stake = sum(obs.stake for obs in signal_obs)
        total_pnl = sum(obs.pnl for obs in signal_obs)
        lines.append(f"- settled rows: {len(signal_obs)}")
        lines.append(f"- pnl: {total_pnl:+.2f}u")
        lines.append(f"- roi: {(total_pnl / total_stake * 100.0) if total_stake else 0.0:+.1f}%")
        lines.append("")
        for title, key_func in (
            ("ROI by probability bin", lambda obs: f"{prob_bin(obs.prob or 0.0, 0.05)[0]:.2f}-{prob_bin(obs.prob or 0.0, 0.05)[1]:.2f}" if obs.prob is not None else "unknown"),
            ("ROI by series", lambda obs: obs.series),
            ("ROI by tournament cohort", lambda obs: obs.cohort),
        ):
            lines.append(title)
            lines.append("segment             n   W-L      pnl      roi")
            for row in summarize_signals(signal_obs, key_func):
                lines.append(
                    f"{row['segment']:<18} {row['n']:>3} {row['wins']:>2}-{row['losses']:<2} "
                    f"{row['pnl']:>+8.2f}u {row['roi']:>+8.1f}%"
                )
            lines.append("")
    lines.append("")
    lines.append("Gate interpretation")
    holdout = next((row for row in metric_rows if row["dataset"] == "holdout" and row["group_type"] == "overall"), None)
    if holdout:
        ece = holdout.get("ece")
        ll_delta = holdout["log_loss_cal"] - holdout["log_loss_pinnacle"]
        if ece is not None:
            lines.append(f"- Holdout 2025 ECE: {ece:.4f} ({'acceptable' if ece <= 0.03 else 'watch' if ece <= 0.05 else 'fail'})")
        lines.append(f"- Holdout 2025 log-loss delta vs Pinnacle: {ll_delta:+.4f}")
        if ece is not None and (ece > 0.05 or ll_delta > 0.005):
            lines.append("- Verdict: do not re-enable clay ML shadow before refitting/reviewing the calibration map.")
        else:
            lines.append("- Verdict: calibration is not the obvious blocker; review archive ROI before re-enabling.")
    else:
        lines.append("- No holdout metrics available.")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyse ATP clay ML calibration and clay_calibrated archive health.")
    parser.add_argument("--files", nargs="+", default=[str(path) for path in DEFAULT_BACKTEST_FILES], help="Backtest result CSVs. Default uses 2022-2025 only.")
    parser.add_argument("--signal-dir", default=str(BACKTEST_DIR), help="Directory containing strict signal CSV archives.")
    parser.add_argument("--signal-glob", action="append", default=[], help="Additional signal glob to scan.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Text report output path.")
    parser.add_argument("--curve-output", default=str(DEFAULT_CURVE), help="Calibration curve CSV output path.")
    parser.add_argument("--bin-width", type=float, default=0.05, help="Probability bin width.")
    parser.add_argument("--min-bin-n", type=int, default=30, help="Minimum bin size included in ECE.")
    args = parser.parse_args()

    backtest_paths = [Path(path) for path in args.files]
    observations, stats = load_backtest_observations(backtest_paths)
    curve_rows, metric_rows = aggregate_curve(observations, bin_width=args.bin_width, min_bin_n=args.min_bin_n)
    curve_output = Path(args.curve_output)
    report_output = Path(args.output)
    write_curve(curve_output, curve_rows)

    signal_globs = DEFAULT_SIGNAL_GLOBS + args.signal_glob
    signal_obs, signal_files = load_signal_observations(Path(args.signal_dir), signal_globs)
    write_report(
        report_output,
        backtest_paths=backtest_paths,
        backtest_stats=stats,
        metric_rows=metric_rows,
        signal_files=signal_files,
        signal_obs=signal_obs,
        curve_path=curve_output,
        min_bin_n=args.min_bin_n,
    )

    print("================================================================")
    print("  IL MARGINE - Clay ML Calibration Analysis")
    print("================================================================")
    print(f"Backtest observations: {len(observations):,}")
    print(f"Signal archive rows:   {len(signal_obs):,}")
    print(f"Report:                {repo_path(report_output)}")
    print(f"Curve CSV:             {repo_path(curve_output)}")
    print("\nDone.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
