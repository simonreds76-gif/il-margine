#!/usr/bin/env python3
"""Review-only hard-court probability calibration overlay.

The script compares the stored fair-odds probability against a surface-specific
hard-court Platt overlay without changing the live model. It answers one narrow
question: would the refreshed hard calibration improve calibration quality and
the existing strict/volume hard policy picks?
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
BACKTEST_DIR = ROOT / "data" / "backtest"
DEFAULT_PARAMS = BACKTEST_DIR / "calibration-params-2022-2026-review.json"
DEFAULT_OUT_TXT = BACKTEST_DIR / "hard-calibration-overlay-report.txt"
DEFAULT_OUT_CSV = BACKTEST_DIR / "hard-calibration-overlay-picks.csv"

SERIES_FAVORITE_PROB_CAP = {
    "ATP250": {"high": 0.89, "medium": 0.85, "low": 0.82},
    "ATP500": {"high": 0.91, "medium": 0.87, "low": 0.84},
    "Masters 1000": {"high": 0.93, "medium": 0.90, "low": 0.87},
    "Grand Slam": {"high": 0.95, "medium": 0.92, "low": 0.89},
    "Masters Cup": {"high": 0.94, "medium": 0.91, "low": 0.88},
    "Grass": {"high": 0.87, "medium": 0.83, "low": 0.80},
    "Challenger": {"high": 0.84, "medium": 0.80, "low": 0.76},
}


@dataclass(frozen=True)
class ProfileRule:
    profile: str
    surface: str
    series: str
    confidence: frozenset[str]
    min_value_pct: float
    label: str


PROFILE_RULES = [
    ProfileRule("strict", "Hard", "Masters 1000", frozenset({"high"}), 10.0, "Hard|Masters 1000|high"),
    ProfileRule("volume_200_hard", "Hard", "Masters 1000", frozenset({"high"}), 15.0, "Hard|Masters 1000|high"),
    ProfileRule("volume_200_hard", "Hard", "Masters 1000", frozenset({"medium"}), 30.0, "Hard|Masters 1000|medium"),
    ProfileRule("volume_200_hard", "Hard", "Grand Slam", frozenset({"high", "medium"}), 5.0, "Hard|Grand Slam|high+medium"),
    ProfileRule("volume_200_hard", "Hard", "ATP500", frozenset({"high", "medium"}), 10.0, "Hard|ATP500|high+medium"),
    ProfileRule("hard_edge10_all", "Hard", "*", frozenset({"high", "medium"}), 10.0, "Hard|all|high+medium"),
]


@dataclass
class Pick:
    method: str
    profile: str
    segment: str
    year: int
    key: str
    side: str
    value_pct: float
    odds: float
    won: bool

    @property
    def flat_pnl(self) -> float:
        return self.odds - 1.0 if self.won else -1.0

    @property
    def stake(self) -> float:
        if self.value_pct >= 20.0:
            return 2.0
        if self.value_pct >= 15.0:
            return 1.5
        if self.value_pct >= 10.0:
            return 1.0
        return 0.5

    @property
    def tier_pnl(self) -> float:
        return self.stake * (self.odds - 1.0) if self.won else -self.stake


def _safe_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _safe_prob(value: float) -> float:
    return max(1e-6, min(1.0 - 1e-6, float(value)))


def _logit(value: float) -> float:
    p = _safe_prob(value)
    return math.log(p / (1.0 - p))


def _sigmoid(value: float) -> float:
    z = max(-20.0, min(20.0, float(value)))
    return 1.0 / (1.0 + math.exp(-z))


def _as_bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _read_rows(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows.extend(dict(row) for row in csv.DictReader(f))
    return rows


def _row_year(row: dict[str, str]) -> int | None:
    text = str(row.get("date") or "")
    if len(text) < 4:
        return None
    try:
        return int(text[:4])
    except ValueError:
        return None


def _actual_p1(row: dict[str, str]) -> int | None:
    p1 = (row.get("player1") or "").strip()
    winner = (row.get("actual_winner") or "").strip()
    if p1 and winner:
        return 1 if p1 == winner else 0
    result = (row.get("bet_result") or "").strip()
    side = (row.get("bet_side") or "").strip()
    if result in {"win", "loss"} and side in {"winner", "loser"}:
        selected_p1 = side == "winner"
        selected_won = result == "win"
        return 1 if selected_p1 == selected_won else 0
    return None


def _apply_guard(p1_prob: float, series: str, surface: str, confidence: str) -> float:
    cap_bucket = "Grass" if surface == "Grass" else series
    caps = SERIES_FAVORITE_PROB_CAP.get(cap_bucket)
    if not caps:
        return _safe_prob(p1_prob)
    cap = float(caps.get(confidence, 0.90))
    if series == "ATP500" and surface == "Hard":
        cap -= 0.02
    cap = max(0.78, min(0.93, cap))
    p = _safe_prob(p1_prob)
    fav_is_p1 = p >= 0.5
    q = p if fav_is_p1 else 1.0 - p
    q = min(q, cap)
    return q if fav_is_p1 else 1.0 - q


def _overlay_prob(row: dict[str, str], hard_params: dict[str, object], *, apply_guard: bool) -> float | None:
    raw = _safe_float(row.get("our_prob_raw"))
    if raw is None:
        raw = _safe_float(row.get("our_prob"))
    if raw is None or not (0.0 < raw < 1.0):
        return None

    series = (row.get("series") or "").strip()
    surface = (row.get("surface") or "").strip()
    confidence = (row.get("confidence") or "").strip().lower()
    a = float(hard_params.get("A", 0.0))
    b = float(hard_params.get("B", 1.0))
    blend_by_series = hard_params.get("blend_by_series") or {}
    blend = float(blend_by_series.get(series, 0.0)) if isinstance(blend_by_series, dict) else 0.0

    fav_is_p1 = raw >= 0.5
    q_raw = raw if fav_is_p1 else 1.0 - raw
    q_cal = _sigmoid(a + b * _logit(q_raw))
    q = (1.0 - blend) * q_raw + blend * q_cal
    p = q if fav_is_p1 else 1.0 - q
    return _apply_guard(p, series, surface, confidence) if apply_guard else _safe_prob(p)


def _ece(probs: list[float], outcomes: list[int], bins: int = 10) -> float:
    if not probs:
        return float("nan")
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for prob, outcome in zip(probs, outcomes, strict=True):
        idx = min(int(_safe_prob(prob) * bins), bins - 1)
        buckets[idx].append((prob, outcome))
    total = len(probs)
    ece = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        avg_prob = mean(item[0] for item in bucket)
        avg_outcome = mean(item[1] for item in bucket)
        ece += len(bucket) / total * abs(avg_prob - avg_outcome)
    return ece


def _logloss(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    total = 0.0
    for prob, outcome in zip(probs, outcomes, strict=True):
        p = _safe_prob(prob)
        total += -outcome * math.log(p) - (1 - outcome) * math.log(1.0 - p)
    return total / len(probs)


def _brier(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((prob - outcome) ** 2 for prob, outcome in zip(probs, outcomes, strict=True)) / len(probs)


def _metrics(rows: list[dict[str, str]], probs_by_key: dict[str, dict[str, float]]) -> dict[str, float]:
    current: list[float] = []
    overlay: list[float] = []
    current_fav_probs: list[float] = []
    overlay_fav_probs: list[float] = []
    current_fav_outcomes: list[int] = []
    overlay_fav_outcomes: list[int] = []
    p1_outcomes: list[int] = []
    for row in rows:
        key = _row_key(row)
        probs = probs_by_key.get(key)
        outcome = _actual_p1(row)
        if not probs or outcome is None:
            continue
        current_p = probs["current"]
        overlay_p = probs["overlay"]
        current.append(current_p)
        overlay.append(overlay_p)
        p1_outcomes.append(outcome)

        current_fav_is_p1 = current_p >= 0.5
        overlay_fav_is_p1 = overlay_p >= 0.5
        current_fav_probs.append(current_p if current_fav_is_p1 else 1.0 - current_p)
        overlay_fav_probs.append(overlay_p if overlay_fav_is_p1 else 1.0 - overlay_p)
        current_fav_outcomes.append(1 if (current_fav_is_p1 and outcome == 1) or (not current_fav_is_p1 and outcome == 0) else 0)
        overlay_fav_outcomes.append(1 if (overlay_fav_is_p1 and outcome == 1) or (not overlay_fav_is_p1 and outcome == 0) else 0)
    return {
        "n": float(len(p1_outcomes)),
        "current_logloss": _logloss(current, p1_outcomes),
        "overlay_logloss": _logloss(overlay, p1_outcomes),
        "current_ece": _ece(current_fav_probs, current_fav_outcomes),
        "overlay_ece": _ece(overlay_fav_probs, overlay_fav_outcomes),
        "current_brier": _brier(current, p1_outcomes),
        "overlay_brier": _brier(overlay, p1_outcomes),
    }


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


def _profile_rules(profile: str) -> list[ProfileRule]:
    return [rule for rule in PROFILE_RULES if rule.profile == profile]


def _match_rule(row: dict[str, str], rule: ProfileRule) -> bool:
    surface = (row.get("surface") or "").strip()
    series = (row.get("series") or "").strip()
    confidence = (row.get("confidence") or "").strip().lower()
    if surface != rule.surface:
        return False
    if rule.series != "*" and series != rule.series:
        return False
    return confidence in rule.confidence


def _make_pick(
    *,
    row: dict[str, str],
    method: str,
    profile: str,
    segment: str,
    min_value_pct: float,
    prob_p1: float,
) -> Pick | None:
    odds1 = _safe_float(row.get("pinnacle_odds"))
    odds2 = _safe_float(row.get("pinnacle_odds_loser"))
    actual_p1 = _actual_p1(row)
    year = _row_year(row)
    if odds1 is None or odds2 is None or odds1 <= 1.0 or odds2 <= 1.0 or actual_p1 is None or year is None:
        return None
    value1 = (odds1 * prob_p1 - 1.0) * 100.0
    value2 = (odds2 * (1.0 - prob_p1) - 1.0) * 100.0
    if value1 >= value2:
        side = "P1"
        value = value1
        odds = odds1
        won = actual_p1 == 1
    else:
        side = "P2"
        value = value2
        odds = odds2
        won = actual_p1 == 0
    if value < min_value_pct:
        return None
    return Pick(
        method=method,
        profile=profile,
        segment=segment,
        year=year,
        key=_row_key(row),
        side=side,
        value_pct=value,
        odds=odds,
        won=won,
    )


def _score_profile(
    rows: list[dict[str, str]],
    probs_by_key: dict[str, dict[str, float]],
    profile: str,
) -> list[Pick]:
    picks: list[Pick] = []
    rules = _profile_rules(profile)
    for row in rows:
        if _as_bool(row.get("policy_excluded")):
            continue
        probs = probs_by_key.get(_row_key(row))
        if not probs:
            continue
        for rule in rules:
            if not _match_rule(row, rule):
                continue
            for method in ("current", "overlay"):
                pick = _make_pick(
                    row=row,
                    method=method,
                    profile=profile,
                    segment=rule.label,
                    min_value_pct=rule.min_value_pct,
                    prob_p1=probs[method],
                )
                if pick:
                    picks.append(pick)
            break
    return picks


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
        "avg_value_pct": mean([pick.value_pct for pick in picks]) if picks else float("nan"),
    }


def _format_pct(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:+.2f}%"


def _format_num(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.4f}"


def _write_picks_csv(path: Path, rows_by_key: dict[str, dict[str, str]], picks: list[Pick]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "method",
        "profile",
        "segment",
        "date",
        "tournament",
        "round",
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
        for pick in sorted(picks, key=lambda item: (item.profile, item.method, item.year, item.key, item.side)):
            row = rows_by_key[pick.key]
            writer.writerow(
                {
                    "method": pick.method,
                    "profile": pick.profile,
                    "segment": pick.segment,
                    "date": row.get("date") or "",
                    "tournament": row.get("tournament") or "",
                    "round": row.get("round") or "",
                    "series": row.get("series") or "",
                    "confidence": row.get("confidence") or "",
                    "player1": row.get("player1") or "",
                    "player2": row.get("player2") or "",
                    "side": pick.side,
                    "value_pct": f"{pick.value_pct:.3f}",
                    "odds": f"{pick.odds:.4f}",
                    "won": "1" if pick.won else "0",
                    "stake": f"{pick.stake:.2f}",
                    "flat_pnl": f"{pick.flat_pnl:.4f}",
                    "tier_pnl": f"{pick.tier_pnl:.4f}",
                }
            )


def _write_report(
    path: Path,
    *,
    generated_utc: str,
    params_path: Path,
    params: dict[str, object],
    dataset_metrics: dict[str, dict[str, float]],
    profile_picks: dict[str, list[Pick]],
) -> None:
    lines: list[str] = []
    hard = (params.get("surfaces") or {}).get("Hard", {})
    lines.append("Hard Calibration Overlay Backtest")
    lines.append(f"Generated: {generated_utc}")
    lines.append(f"Params: {params_path}")
    lines.append(
        "Split from params: train="
        + ",".join(str(year) for year in params.get("train_years", []))
        + f" validation={params.get('validation_year')} holdout={params.get('holdout_year')}"
    )
    lines.append(
        f"Hard params: A={float(hard.get('A', 0.0)):.6f} B={float(hard.get('B', 1.0)):.6f} "
        f"blend={hard.get('blend_by_series', {})}"
    )
    lines.append("")

    lines.append("Calibration quality on hard rows")
    lines.append("Dataset      N    logloss current/overlay   ECE current/overlay   Brier current/overlay")
    for label in ("train", "validation", "holdout", "all"):
        m = dataset_metrics.get(label, {})
        lines.append(
            f"{label:10s} {int(m.get('n', 0)):4d}  "
            f"{_format_num(m.get('current_logloss', float('nan')))}/{_format_num(m.get('overlay_logloss', float('nan')))}       "
            f"{_format_num(m.get('current_ece', float('nan')))}/{_format_num(m.get('overlay_ece', float('nan')))}       "
            f"{_format_num(m.get('current_brier', float('nan')))}/{_format_num(m.get('overlay_brier', float('nan')))}"
        )
    lines.append("")

    for profile in ("strict", "volume_200_hard", "hard_edge10_all"):
        lines.append(f"[{profile}]")
        picks = profile_picks.get(profile, [])
        by_method = {
            method: [pick for pick in picks if pick.method == method]
            for method in ("current", "overlay")
        }
        for method, method_picks in by_method.items():
            s = _summarize_picks(method_picks)
            lines.append(
                f"  {method:8s} bets={int(s['bets']):4d} W-L={int(s['wins'])}-{int(s['losses'])} "
                f"flatROI={_format_pct(s['flat_roi_pct'])} tierROI={_format_pct(s['tier_roi_pct'])} "
                f"P/L={s['tier_pnl']:+.2f}u on {s['stake']:.2f}u avgValue={_format_pct(s['avg_value_pct'])}"
            )
            years: dict[int, list[Pick]] = defaultdict(list)
            for pick in method_picks:
                years[pick.year].append(pick)
            for year in sorted(years):
                ys = _summarize_picks(years[year])
                lines.append(
                    f"    {year}: bets={int(ys['bets']):3d} tierROI={_format_pct(ys['tier_roi_pct'])} "
                    f"P/L={ys['tier_pnl']:+.2f}u on {ys['stake']:.2f}u"
                )

        current_keys = {pick.key for pick in by_method["current"]}
        overlay_keys = {pick.key for pick in by_method["overlay"]}
        lines.append(
            f"  Change: common={len(current_keys & overlay_keys)} "
            f"dropped={len(current_keys - overlay_keys)} added={len(overlay_keys - current_keys)}"
        )
        lines.append("")

    validation = dataset_metrics.get("validation", {})
    holdout = dataset_metrics.get("holdout", {})
    validation_improved = validation.get("overlay_logloss", 1.0) < validation.get("current_logloss", 0.0)
    holdout_improved = holdout.get("overlay_logloss", 1.0) < holdout.get("current_logloss", 0.0)
    lines.append("Verdict")
    if validation_improved and holdout_improved:
        lines.append("- Probability calibration improves validation and holdout log-loss. Keep as a hard-only shadow overlay candidate.")
    elif validation_improved:
        lines.append("- Probability calibration improves validation only. Do not wire live; keep review-only until more holdout rows exist.")
    else:
        lines.append("- Probability calibration does not clearly improve validation. Do not wire live.")
    lines.append("- This report does not change live fair-odds scoring or signal archives.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review hard surface calibration overlay against historical backtests.")
    parser.add_argument("--params", type=Path, default=DEFAULT_PARAMS)
    parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025, 2026])
    parser.add_argument("--out-txt", type=Path, default=DEFAULT_OUT_TXT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--no-guard", action="store_true", help="Do not apply existing favorite probability caps to overlay probability.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.params.exists():
        raise SystemExit(f"Calibration params missing: {args.params}")
    params = json.loads(args.params.read_text(encoding="utf-8"))
    hard_params = (params.get("surfaces") or {}).get("Hard")
    if not isinstance(hard_params, dict):
        raise SystemExit(f"No Hard params found in {args.params}")

    paths = [BACKTEST_DIR / f"backtest-results-{year}.csv" for year in args.years]
    rows = [
        row for row in _read_rows(paths)
        if (row.get("surface") or "").strip() == "Hard"
    ]
    if not rows:
        raise SystemExit("No hard backtest rows loaded.")

    probs_by_key: dict[str, dict[str, float]] = {}
    rows_by_key: dict[str, dict[str, str]] = {}
    for row in rows:
        current = _safe_float(row.get("our_prob"))
        overlay = _overlay_prob(row, hard_params, apply_guard=not args.no_guard)
        if current is None or overlay is None:
            continue
        key = _row_key(row)
        probs_by_key[key] = {"current": _safe_prob(current), "overlay": _safe_prob(overlay)}
        rows_by_key[key] = row

    train_years = set(int(year) for year in params.get("train_years", []))
    validation_year = int(params.get("validation_year"))
    holdout_year = int(params.get("holdout_year"))

    dataset_rows = {
        "train": [row for row in rows if (_row_year(row) in train_years)],
        "validation": [row for row in rows if _row_year(row) == validation_year],
        "holdout": [row for row in rows if _row_year(row) == holdout_year],
        "all": rows,
    }
    dataset_metrics = {label: _metrics(items, probs_by_key) for label, items in dataset_rows.items()}

    profile_picks = {
        profile: _score_profile(rows, probs_by_key, profile)
        for profile in ("strict", "volume_200_hard", "hard_edge10_all")
    }
    all_picks = [pick for picks in profile_picks.values() for pick in picks]

    generated_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _write_picks_csv(args.out_csv, rows_by_key, all_picks)
    _write_report(
        args.out_txt,
        generated_utc=generated_utc,
        params_path=args.params,
        params=params,
        dataset_metrics=dataset_metrics,
        profile_picks=profile_picks,
    )
    print(f"Wrote {args.out_txt}")
    print(f"Wrote {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
