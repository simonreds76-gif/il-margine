#!/usr/bin/env python3
"""Shadow harness for tennis ML model variants.

This script does not publish picks and does not change live fair-odds routing.
It gives us one durable place to compare Claude/Fable model ideas against the
same historical row-level backtest files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Callable, Iterable


ROOT = Path(__file__).resolve().parent.parent
BACKTEST_DIR = ROOT / "data" / "backtest"
DEFAULT_PARAMS = BACKTEST_DIR / "calibration-params-2022-2026-review.json"
DEFAULT_OUT = BACKTEST_DIR / "model-variants-shadow.csv"
DEFAULT_REPORT = BACKTEST_DIR / "model-variants-shadow-report.txt"
DEFAULT_PICKS = BACKTEST_DIR / "model-variants-shadow-picks.csv"
DEFAULT_YEARS = (2022, 2023, 2024, 2025, 2026)

VALUE_TIERS = ((20.0, 2.0), (15.0, 1.5), (10.0, 1.0), (5.0, 0.5))
MISPRICE_IMPLIED_GAP_PP = 0.10
MISPRICE_FAV_ODDS_MIN = 1.25


@dataclass(frozen=True)
class ProfileRule:
    profile: str
    surface: str
    series: str
    confidences: frozenset[str]
    min_value_pct: float
    label: str


PROFILE_RULES = [
    ProfileRule("strict", "Hard", "Masters 1000", frozenset({"high"}), 10.0, "Hard|Masters1000|high"),
    ProfileRule("volume_200_hard", "Hard", "Masters 1000", frozenset({"high"}), 15.0, "Hard|Masters1000|high"),
    ProfileRule("volume_200_hard", "Hard", "Masters 1000", frozenset({"medium"}), 30.0, "Hard|Masters1000|medium"),
    ProfileRule("volume_200_hard", "Hard", "Grand Slam", frozenset({"high", "medium"}), 5.0, "Hard|GrandSlam|high+medium"),
    ProfileRule("volume_200_hard", "Hard", "ATP500", frozenset({"high", "medium"}), 10.0, "Hard|ATP500|high+medium"),
    ProfileRule("hard_edge10_all", "Hard", "*", frozenset({"high", "medium"}), 10.0, "Hard|all|high+medium"),
    ProfileRule("clay_edge10_all", "Clay", "*", frozenset({"high", "medium"}), 10.0, "Clay|all|high+medium"),
    ProfileRule("clay_masters_high", "Clay", "Masters 1000", frozenset({"high"}), 10.0, "Clay|Masters1000|high"),
    ProfileRule("atp250_hard_20", "Hard", "ATP250", frozenset({"high", "medium"}), 20.0, "Hard|ATP250|high+medium|edge20"),
    ProfileRule("all_edge10", "*", "*", frozenset({"high", "medium"}), 10.0, "All|all|high+medium"),
]


@dataclass(frozen=True)
class Variant:
    name: str
    source_suffix: str
    transform: str
    profiles: tuple[str, ...]
    description: str
    rerun_args: tuple[str, ...] = ()


VARIANTS = [
    Variant(
        name="baseline_current",
        source_suffix="",
        transform="current",
        profiles=("strict", "volume_200_hard", "hard_edge10_all", "clay_edge10_all", "all_edge10"),
        description="Current row-level backtest probabilities and policy guards.",
    ),
    Variant(
        name="hardcal_strict_live",
        source_suffix="",
        transform="surface_cal:Hard",
        profiles=("strict", "volume_200_hard", "hard_edge10_all"),
        description="Apply validated Hard Platt overlay to raw probabilities; score strict/volume only.",
    ),
    Variant(
        name="claycal_lanes",
        source_suffix="",
        transform="surface_cal:Clay",
        profiles=("clay_edge10_all", "clay_masters_high"),
        description="Apply Clay surface calibration to raw probabilities; shadow only.",
    ),
    Variant(
        name="atp250_hard_20",
        source_suffix="",
        transform="current",
        profiles=("atp250_hard_20",),
        description="Hard ATP250 high/medium only at >=20% edge. Candidate expansion, not live.",
    ),
    Variant(
        name="h2h_n2_shrunk",
        source_suffix="h2h-n2-shrunk",
        transform="current",
        profiles=("strict", "volume_200_hard", "hard_edge10_all", "all_edge10"),
        description="Model rerun: H2H active from n>=2 with 3-match prior shrinkage toward 50%.",
        rerun_args=("--h2h-min-matches", "2", "--h2h-prior-k", "3.0", "--output-suffix", "h2h-n2-shrunk"),
    ),
    Variant(
        name="fatigue_x1.5",
        source_suffix="fatigue-x1.5",
        transform="current",
        profiles=("strict", "volume_200_hard", "hard_edge10_all", "all_edge10"),
        description="Model rerun: multiply v2 fatigue/rust delta by 1.5.",
        rerun_args=("--fatigue-multiplier", "1.5", "--output-suffix", "fatigue-x1.5"),
    ),
    Variant(
        name="tournament_form_caps_up",
        source_suffix="tournament-form-caps-up",
        transform="current",
        profiles=("strict", "volume_200_hard", "hard_edge10_all", "all_edge10"),
        description="Model rerun: raise same-tournament history cap from 3pp to 4pp.",
        rerun_args=("--tournament-history-cap", "0.04", "--output-suffix", "tournament-form-caps-up"),
    ),
]


@dataclass
class Pick:
    variant: str
    profile: str
    segment: str
    year: int
    key: str
    side: str
    value_pct: float
    odds: float
    won: bool

    @property
    def stake(self) -> float:
        for min_value, stake in VALUE_TIERS:
            if self.value_pct >= min_value:
                return stake
        return 0.0

    @property
    def flat_pnl(self) -> float:
        return self.odds - 1.0 if self.won else -1.0

    @property
    def tier_pnl(self) -> float:
        return self.stake * (self.odds - 1.0) if self.won else -self.stake


def _safe_float(value: object, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        parsed = float(text)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def _safe_prob(value: float) -> float:
    return max(1e-6, min(1.0 - 1e-6, float(value)))


def _logit(value: float) -> float:
    p = _safe_prob(value)
    return math.log(p / (1.0 - p))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, float(value)))))


def _as_bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _year(row: dict[str, str]) -> int | None:
    text = str(row.get("date") or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _row_key(row: dict[str, str]) -> str:
    return "|".join(
        [
            str(row.get("date") or ""),
            str(row.get("tournament") or ""),
            str(row.get("round") or ""),
            str(row.get("player1_id") or row.get("player1") or ""),
            str(row.get("player2_id") or row.get("player2") or ""),
        ]
    )


def _result_paths(years: Iterable[int], suffix: str) -> list[Path]:
    suffix_part = f"-{suffix}" if suffix else ""
    return [BACKTEST_DIR / f"backtest-results-{year}{suffix_part}.csv" for year in years]


def _read_rows(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows.extend(dict(row) for row in csv.DictReader(f))
    return rows


def _load_calibration_params(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("surfaces") or {}


def _surface_calibrated_prob(row: dict[str, str], params: dict[str, dict[str, object]], target_surface: str) -> float:
    current = _safe_prob(_safe_float(row.get("our_prob"), 0.5) or 0.5)
    raw = _safe_prob(_safe_float(row.get("our_prob_raw"), current) or current)
    surface = str(row.get("surface") or "").strip()
    if surface != target_surface:
        return current
    surface_params = params.get(surface) or {}
    a = _safe_float(surface_params.get("A"))
    b = _safe_float(surface_params.get("B"))
    if a is None or b is None:
        return current
    series = str(row.get("series") or "").strip()
    blend_by_series = surface_params.get("blend_by_series") or {}
    try:
        blend = float(blend_by_series.get(series, 1.0))
    except (AttributeError, TypeError, ValueError):
        blend = 1.0
    blend = max(0.0, min(1.0, blend))
    fav_is_p1 = raw >= 0.5
    fav_prob = raw if fav_is_p1 else 1.0 - raw
    fav_cal = _sigmoid(a + b * _logit(fav_prob))
    restored = fav_cal if fav_is_p1 else 1.0 - fav_cal
    return _safe_prob((1.0 - blend) * current + blend * restored)


def _prob_for_variant(row: dict[str, str], variant: Variant, params: dict[str, dict[str, object]]) -> float:
    if variant.transform.startswith("surface_cal:"):
        return _surface_calibrated_prob(row, params, variant.transform.split(":", 1)[1])
    return _safe_prob(_safe_float(row.get("our_prob"), 0.5) or 0.5)


def _pin_prob_winner(row: dict[str, str]) -> float | None:
    odds1 = _safe_float(row.get("pinnacle_odds"))
    odds2 = _safe_float(row.get("pinnacle_odds_loser"))
    if odds1 is None or odds2 is None or odds1 <= 1.0 or odds2 <= 1.0:
        return None
    p1 = 1.0 / odds1
    p2 = 1.0 / odds2
    total = p1 + p2
    return p1 / total if total > 0 else None


def _policy_excluded(row: dict[str, str], prob_p1: float) -> bool:
    if _as_bool(row.get("policy_excluded")):
        return True
    odds1 = _safe_float(row.get("pinnacle_odds"))
    odds2 = _safe_float(row.get("pinnacle_odds_loser"))
    pin_w = _pin_prob_winner(row)
    if odds1 is None or odds2 is None or pin_w is None:
        return True
    model_fav_implied = max(prob_p1, 1.0 - prob_p1)
    pin_fav_implied = max(pin_w, 1.0 - pin_w)
    if abs(model_fav_implied - pin_fav_implied) > MISPRICE_IMPLIED_GAP_PP:
        return True
    model_fav_odds = 1.0 / model_fav_implied
    pin_fav_odds = min(odds1, odds2)
    return model_fav_odds < MISPRICE_FAV_ODDS_MIN or pin_fav_odds < MISPRICE_FAV_ODDS_MIN


def _logloss(prob: float, outcome: int) -> float:
    p = _safe_prob(prob)
    return -(outcome * math.log(p) + (1 - outcome) * math.log(1.0 - p))


def _ece(rows: list[tuple[float, int]], bins: int = 10) -> float:
    if not rows:
        return float("nan")
    total = 0.0
    for idx in range(bins):
        lo = idx / bins
        hi = (idx + 1) / bins
        bucket = [(p, y) for p, y in rows if (lo <= p < hi or (idx == bins - 1 and p <= hi))]
        if not bucket:
            continue
        pred = mean(p for p, _ in bucket)
        actual = mean(y for _, y in bucket)
        total += (len(bucket) / len(rows)) * abs(pred - actual)
    return total


def _rule_matches(row: dict[str, str], rule: ProfileRule) -> bool:
    surface = str(row.get("surface") or "").strip()
    series = str(row.get("series") or "").strip()
    confidence = str(row.get("confidence") or "").strip().lower()
    if rule.surface != "*" and surface != rule.surface:
        return False
    if rule.series != "*" and series != rule.series:
        return False
    return confidence in rule.confidences


def _make_pick(row: dict[str, str], variant_name: str, profile: str, rule: ProfileRule, prob_p1: float) -> Pick | None:
    year = _year(row)
    odds1 = _safe_float(row.get("pinnacle_odds"))
    odds2 = _safe_float(row.get("pinnacle_odds_loser"))
    if year is None or odds1 is None or odds2 is None or odds1 <= 1.0 or odds2 <= 1.0:
        return None
    if _policy_excluded(row, prob_p1):
        return None
    value1 = (odds1 * prob_p1 - 1.0) * 100.0
    value2 = (odds2 * (1.0 - prob_p1) - 1.0) * 100.0
    if value1 >= value2:
        side = "P1"
        value = value1
        odds = odds1
        won = True
    else:
        side = "P2"
        value = value2
        odds = odds2
        won = False
    if value < rule.min_value_pct:
        return None
    return Pick(
        variant=variant_name,
        profile=profile,
        segment=rule.label,
        year=year,
        key=_row_key(row),
        side=side,
        value_pct=value,
        odds=odds,
        won=won,
    )


def _score_variant(variant: Variant, rows: list[dict[str, str]], params: dict[str, dict[str, object]]) -> tuple[list[Pick], dict[str, float]]:
    picks: list[Pick] = []
    eval_pairs: list[tuple[float, int]] = []
    fav_pairs: list[tuple[float, int]] = []
    for row in rows:
        prob_p1 = _prob_for_variant(row, variant, params)
        if _pin_prob_winner(row) is not None:
            eval_pairs.append((prob_p1, 1))
            fav_prob = max(prob_p1, 1.0 - prob_p1)
            fav_won = 1 if prob_p1 >= 0.5 else 0
            fav_pairs.append((fav_prob, fav_won))
        for profile in variant.profiles:
            for rule in PROFILE_RULES:
                if rule.profile != profile or not _rule_matches(row, rule):
                    continue
                pick = _make_pick(row, variant.name, profile, rule, prob_p1)
                if pick:
                    picks.append(pick)
                break
    quality = {
        "rows": float(len(eval_pairs)),
        "logloss": mean(_logloss(p, y) for p, y in eval_pairs) if eval_pairs else float("nan"),
        "brier": mean((p - y) ** 2 for p, y in eval_pairs) if eval_pairs else float("nan"),
        "ece": _ece(fav_pairs),
    }
    return picks, quality


def _summarize_picks(picks: list[Pick]) -> dict[str, float]:
    bets = len(picks)
    wins = sum(1 for pick in picks if pick.won)
    flat_pnl = sum(pick.flat_pnl for pick in picks)
    stake = sum(pick.stake for pick in picks)
    tier_pnl = sum(pick.tier_pnl for pick in picks)
    return {
        "bets": float(bets),
        "wins": float(wins),
        "losses": float(bets - wins),
        "flat_pnl": flat_pnl,
        "flat_roi_pct": flat_pnl / bets * 100.0 if bets else float("nan"),
        "stake": stake,
        "tier_pnl": tier_pnl,
        "tier_roi_pct": tier_pnl / stake * 100.0 if stake else float("nan"),
        "avg_value_pct": mean(pick.value_pct for pick in picks) if picks else float("nan"),
    }


def _by_year_summary(picks: list[Pick]) -> str:
    parts = []
    for year in sorted({pick.year for pick in picks}):
        stats = _summarize_picks([pick for pick in picks if pick.year == year])
        parts.append(f"{year}:{int(stats['bets'])}/{stats['tier_roi_pct']:+.1f}%")
    return " ".join(parts)


def _fmt(value: float, digits: int = 3) -> str:
    if math.isnan(value):
        return ""
    return f"{value:.{digits}f}"


def _run_variant_backtests(variants: list[Variant], years: tuple[int, ...]) -> None:
    xlsx_paths = [BACKTEST_DIR / f"atp-{year}.xlsx" for year in years]
    missing = [path for path in xlsx_paths if not path.exists()]
    if missing:
        print("Skipping model reruns; missing XLSX files:")
        for path in missing:
            print(f"  - {path}")
        return
    files_args = ["--files", *[str(path) for path in xlsx_paths]]
    for variant in variants:
        if not variant.rerun_args:
            continue
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "backtest-fair-odds.py"),
            *files_args,
            "--thresholds",
            "5,10,15,20",
            *variant.rerun_args,
        ]
        print(f"Running {variant.name}: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=str(ROOT), check=True)


def _write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "generated_utc",
        "variant",
        "profile",
        "status",
        "description",
        "source_suffix",
        "transform",
        "rows",
        "logloss",
        "brier",
        "ece",
        "bets",
        "wins",
        "losses",
        "flat_pnl",
        "flat_roi_pct",
        "stake",
        "tier_pnl",
        "tier_roi_pct",
        "avg_value_pct",
        "by_year",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _load_previous_summary(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {
            (row.get("variant", ""), row.get("profile", "")): dict(row)
            for row in csv.DictReader(f)
            if row.get("variant") and row.get("profile")
        }


def _write_picks(path: Path, rows_by_key: dict[str, dict[str, str]], picks: list[Pick]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "variant",
        "profile",
        "segment",
        "year",
        "date",
        "tournament",
        "round",
        "surface",
        "series",
        "confidence",
        "player1",
        "player2",
        "side",
        "value_pct",
        "odds",
        "won",
        "stake",
        "flat_pnl",
        "tier_pnl",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for pick in sorted(picks, key=lambda p: (p.variant, p.profile, p.year, p.key, p.side)):
            row = rows_by_key.get(pick.key, {})
            writer.writerow(
                {
                    "variant": pick.variant,
                    "profile": pick.profile,
                    "segment": pick.segment,
                    "year": pick.year,
                    "date": row.get("date", ""),
                    "tournament": row.get("tournament", ""),
                    "round": row.get("round", ""),
                    "surface": row.get("surface", ""),
                    "series": row.get("series", ""),
                    "confidence": row.get("confidence", ""),
                    "player1": row.get("player1", ""),
                    "player2": row.get("player2", ""),
                    "side": pick.side,
                    "value_pct": f"{pick.value_pct:.3f}",
                    "odds": f"{pick.odds:.4f}",
                    "won": "1" if pick.won else "0",
                    "stake": f"{pick.stake:.2f}",
                    "flat_pnl": f"{pick.flat_pnl:.3f}",
                    "tier_pnl": f"{pick.tier_pnl:.3f}",
                }
            )


def _write_report(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "Tennis Model Variants Shadow Harness",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "Purpose: compare candidate model changes without changing live fair-odds routing.",
        "A variant marked pending needs its suffixed backtest CSVs generated with --run-model-reruns.",
        "A variant marked stale_ok is the last successful summary retained because the heavy rerun source CSVs were unavailable in this environment.",
        "",
    ]
    for row in rows:
        lines.append(
            f"{row['variant']:26s} {row['profile']:18s} {row['status']:8s} "
            f"bets={row['bets'] or '0':>4s} tierROI={row['tier_roi_pct'] or '':>8s}% "
            f"logloss={row['logloss']} ece={row['ece']} {row['by_year']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Score tennis ML shadow model variants.")
    parser.add_argument("--years", default=",".join(str(year) for year in DEFAULT_YEARS))
    parser.add_argument("--params", default=str(DEFAULT_PARAMS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--picks-out", default=str(DEFAULT_PICKS))
    parser.add_argument("--run-model-reruns", action="store_true")
    args = parser.parse_args()

    years = tuple(int(part) for part in re.split(r"[, ]+", args.years.strip()) if part)
    variants = list(VARIANTS)
    if args.run_model_reruns:
        _run_variant_backtests(variants, years)

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    params = _load_calibration_params(Path(args.params))
    previous_summary = _load_previous_summary(Path(args.out))
    summary_rows: list[dict[str, str]] = []
    all_picks: list[Pick] = []
    rows_by_key: dict[str, dict[str, str]] = {}

    for variant in variants:
        paths = _result_paths(years, variant.source_suffix)
        rows = _read_rows(paths)
        status = "ok" if rows else "pending"
        if rows:
            for row in rows:
                rows_by_key.setdefault(_row_key(row), row)
            picks, quality = _score_variant(variant, rows, params)
            all_picks.extend(picks)
        else:
            picks = []
            quality = {"rows": 0.0, "logloss": float("nan"), "brier": float("nan"), "ece": float("nan")}

        for profile in variant.profiles:
            previous = previous_summary.get((variant.name, profile))
            if not rows and previous and previous.get("status") in {"ok", "stale_ok"}:
                retained = dict(previous)
                retained["generated_utc"] = generated
                retained["status"] = "stale_ok"
                retained["description"] = variant.description
                retained["source_suffix"] = variant.source_suffix
                retained["transform"] = variant.transform
                summary_rows.append(retained)
                continue
            profile_picks = [pick for pick in picks if pick.profile == profile]
            stats = _summarize_picks(profile_picks)
            summary_rows.append(
                {
                    "generated_utc": generated,
                    "variant": variant.name,
                    "profile": profile,
                    "status": status,
                    "description": variant.description,
                    "source_suffix": variant.source_suffix,
                    "transform": variant.transform,
                    "rows": str(int(quality["rows"])),
                    "logloss": _fmt(quality["logloss"], 5),
                    "brier": _fmt(quality["brier"], 5),
                    "ece": _fmt(quality["ece"], 5),
                    "bets": str(int(stats["bets"])) if not math.isnan(stats["bets"]) else "0",
                    "wins": str(int(stats["wins"])) if not math.isnan(stats["wins"]) else "0",
                    "losses": str(int(stats["losses"])) if not math.isnan(stats["losses"]) else "0",
                    "flat_pnl": _fmt(stats["flat_pnl"], 3),
                    "flat_roi_pct": _fmt(stats["flat_roi_pct"], 3),
                    "stake": _fmt(stats["stake"], 2),
                    "tier_pnl": _fmt(stats["tier_pnl"], 3),
                    "tier_roi_pct": _fmt(stats["tier_roi_pct"], 3),
                    "avg_value_pct": _fmt(stats["avg_value_pct"], 3),
                    "by_year": _by_year_summary(profile_picks),
                }
            )

    _write_summary(Path(args.out), summary_rows)
    _write_picks(Path(args.picks_out), rows_by_key, all_picks)
    _write_report(Path(args.report), summary_rows)
    print(f"Wrote {len(summary_rows)} variant/profile rows -> {args.out}")
    print(f"Wrote {len(all_picks)} shadow picks -> {args.picks_out}")
    print(f"Wrote report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
