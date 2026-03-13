"""
Exact policy-profile scorer for generated backtest CSVs.

Purpose:
- Score the current strict and shadow policy rules against backtest-results-YYYY.csv
- Use the same exact segment gates as strict-policy-report.py
- Report both flat stake and current value-tiered staking
- Show by-year, by-segment, and simple consecutive-year walk-forward summaries

Usage:
  python scripts/backtest-policy-profiles.py
  python scripts/backtest-policy-profiles.py --profiles strict volume_275 volume_200
  python scripts/backtest-policy-profiles.py --out-txt data/backtest/policy-profile-backtest-2022-2025.txt
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent.parent
BACKTEST_DIR = ROOT / "data" / "backtest"
DEFAULT_FILES = [BACKTEST_DIR / f"backtest-results-{year}.csv" for year in (2022, 2023, 2024, 2025)]
DEFAULT_OUT = BACKTEST_DIR / "policy-profile-backtest-2022-2025.txt"

STRICT_PUBLIC_MIN_VALUE_PCT = 10.0


@dataclass(frozen=True)
class ProfileRule:
    surface: str
    series: str
    confidence: frozenset[str]
    min_value_pct: float
    label: str


STRICT_RULES = [
    ProfileRule("Hard", "Masters 1000", frozenset({"high"}), STRICT_PUBLIC_MIN_VALUE_PCT, "Hard|Masters 1000|high"),
]

VOLUME_275_RULES = [
    ProfileRule("Hard", "Masters 1000", frozenset({"high"}), 15.0, "Hard|Masters 1000|high"),
    ProfileRule("Hard", "Masters 1000", frozenset({"medium"}), 30.0, "Hard|Masters 1000|medium"),
    ProfileRule("Clay", "Masters 1000", frozenset({"high"}), 20.0, "Clay|Masters 1000|high"),
    ProfileRule("Hard", "Grand Slam", frozenset({"high", "medium"}), 5.0, "Hard|Grand Slam|high+medium"),
    ProfileRule("Grass", "ATP500", frozenset({"high", "medium"}), 10.0, "Grass|ATP500|high+medium"),
    ProfileRule("Hard", "ATP250", frozenset({"high", "medium"}), 20.0, "Hard|ATP250|high+medium"),
]

VOLUME_200_RULES = [
    rule for rule in VOLUME_275_RULES if not (rule.surface == "Clay" and rule.series == "Masters 1000")
]

PROFILE_RULES: dict[str, list[ProfileRule]] = {
    "strict": STRICT_RULES,
    "volume_275": VOLUME_275_RULES,
    "volume_200": VOLUME_200_RULES,
    "volume_trimmed_no_clay": VOLUME_200_RULES,
}


@dataclass
class Pick:
    year: str
    segment: str
    confidence: str
    value_pct: float
    flat_pnl: float
    tier_stake: float
    tier_pnl: float
    won: bool


def _as_bool(value: str | bool | None) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def _units_for_value_pct(value_pct: float) -> float:
    if value_pct >= 20.0:
        return 2.0
    if value_pct >= 15.0:
        return 1.5
    if value_pct >= 10.0:
        return 1.0
    return 0.5


def _match_segment(row: dict[str, str], rules: list[ProfileRule]) -> str | None:
    surface = str(row.get("surface") or "")
    series = str(row.get("series") or "")
    confidence = str(row.get("confidence") or "").strip().lower()
    try:
        value_pct = float(row.get("value_pct") or 0.0)
    except ValueError:
        return None

    for rule in rules:
        if surface != rule.surface or series != rule.series:
            continue
        if confidence not in rule.confidence:
            continue
        if value_pct < rule.min_value_pct:
            continue
        return rule.label
    return None


def _odds_for_pick(row: dict[str, str]) -> float | None:
    try:
        if row.get("bet_side") == "winner":
            return float(row.get("pinnacle_odds") or 0.0)
        return float(row.get("pinnacle_odds_loser") or 0.0)
    except ValueError:
        return None


def _load_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as f:
            rows.extend(list(csv.DictReader(f)))
    return rows


def _score_profile(rows: list[dict[str, str]], rules: list[ProfileRule]) -> list[Pick]:
    picks: list[Pick] = []
    for row in rows:
        if _as_bool(row.get("policy_excluded")):
            continue
        if row.get("bet_result") not in {"win", "loss"}:
            continue
        segment = _match_segment(row, rules)
        if segment is None:
            continue
        odds = _odds_for_pick(row)
        if odds is None or odds <= 1.0:
            continue
        value_pct = float(row.get("value_pct") or 0.0)
        tier_stake = _units_for_value_pct(value_pct)
        won = row.get("bet_result") == "win"
        flat_pnl = (odds - 1.0) if won else -1.0
        tier_pnl = (tier_stake * (odds - 1.0)) if won else -tier_stake
        picks.append(
            Pick(
                year=str(row.get("date") or "")[:4],
                segment=segment,
                confidence=str(row.get("confidence") or "").strip().lower(),
                value_pct=value_pct,
                flat_pnl=flat_pnl,
                tier_stake=tier_stake,
                tier_pnl=tier_pnl,
                won=won,
            )
        )
    return picks


def _summarize(picks: list[Pick]) -> dict[str, float]:
    bets = len(picks)
    wins = sum(1 for pick in picks if pick.won)
    flat_profit = sum(pick.flat_pnl for pick in picks)
    tier_staked = sum(pick.tier_stake for pick in picks)
    tier_profit = sum(pick.tier_pnl for pick in picks)
    return {
        "bets": float(bets),
        "wins": float(wins),
        "losses": float(bets - wins),
        "win_rate_pct": (wins / bets * 100.0) if bets else 0.0,
        "avg_value_pct": (sum(pick.value_pct for pick in picks) / bets) if bets else 0.0,
        "flat_profit": flat_profit,
        "flat_roi_pct": (flat_profit / bets * 100.0) if bets else 0.0,
        "tier_staked": tier_staked,
        "tier_profit": tier_profit,
        "tier_roi_pct": (tier_profit / tier_staked * 100.0) if tier_staked else 0.0,
        "avg_bets_per_year": (bets / 4.0) if bets else 0.0,
    }


def _group_summary(picks: list[Pick], key_fn: Callable[[Pick], str]) -> list[tuple[str, dict[str, float]]]:
    grouped: dict[str, list[Pick]] = defaultdict(list)
    for pick in picks:
        grouped[key_fn(pick)].append(pick)
    return [(key, _summarize(grouped[key])) for key in sorted(grouped)]


def _walkforward_lines(profile_name: str, picks: list[Pick]) -> list[str]:
    lines: list[str] = []
    yearly: dict[str, list[Pick]] = defaultdict(list)
    for pick in picks:
        yearly[pick.year].append(pick)
    years = sorted(yearly)
    lines.append("  Consecutive-year view:")
    if len(years) < 2:
        lines.append("    (not enough yearly buckets)")
        return lines
    for train_year, test_year in zip(years, years[1:]):
        train_summary = _summarize(yearly[train_year])
        test_summary = _summarize(yearly[test_year])
        lines.append(
            f"    {train_year}->{test_year}: "
            f"train tierROI={train_summary['tier_roi_pct']:+.2f}% ({int(train_summary['bets'])} bets) | "
            f"test tierROI={test_summary['tier_roi_pct']:+.2f}% ({int(test_summary['bets'])} bets)"
        )
    return lines


def _format_profile(profile_name: str, picks: list[Pick]) -> list[str]:
    summary = _summarize(picks)
    lines = [
        f"[{profile_name}]",
        (
            f"  Bets={int(summary['bets'])}  Avg/Year={summary['avg_bets_per_year']:.1f}  "
            f"W-L={int(summary['wins'])}-{int(summary['losses'])}  WR={summary['win_rate_pct']:.2f}%  "
            f"AvgValue={summary['avg_value_pct']:.2f}%"
        ),
        f"  Flat stake:    P/L={summary['flat_profit']:+.2f}u  ROI={summary['flat_roi_pct']:+.2f}%",
        (
            f"  Value-tiered:  Staked={summary['tier_staked']:.2f}u  "
            f"P/L={summary['tier_profit']:+.2f}u  ROI={summary['tier_roi_pct']:+.2f}%"
        ),
        "  By year:",
    ]
    for year, year_summary in _group_summary(picks, lambda pick: pick.year):
        lines.append(
            f"    {year}: bets={int(year_summary['bets'])}  "
            f"flatROI={year_summary['flat_roi_pct']:+.2f}%  "
            f"tierROI={year_summary['tier_roi_pct']:+.2f}%  "
            f"P/L={year_summary['tier_profit']:+.2f}u on {year_summary['tier_staked']:.2f}u"
        )
    lines.append("  By segment:")
    for segment, seg_summary in _group_summary(picks, lambda pick: pick.segment):
        lines.append(
            f"    {segment}: bets={int(seg_summary['bets'])}  "
            f"flatROI={seg_summary['flat_roi_pct']:+.2f}%  "
            f"tierROI={seg_summary['tier_roi_pct']:+.2f}%  "
            f"P/L={seg_summary['tier_profit']:+.2f}u on {seg_summary['tier_staked']:.2f}u"
        )
    lines.extend(_walkforward_lines(profile_name, picks))
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Score exact fair-odds policy profiles from backtest CSV outputs.")
    parser.add_argument("--files", nargs="*", default=[str(path) for path in DEFAULT_FILES], help="Backtest CSV files.")
    parser.add_argument(
        "--profiles",
        nargs="*",
        default=["strict", "volume_275", "volume_200"],
        choices=sorted(PROFILE_RULES),
        help="Profiles to score.",
    )
    parser.add_argument("--out-txt", default=str(DEFAULT_OUT), help="Text report output path.")
    parser.add_argument("--dry-run", action="store_true", help="Print report only, do not write file.")
    args = parser.parse_args()

    paths = [Path(p) for p in args.files]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing backtest CSVs: {', '.join(missing)}")

    rows = _load_rows(paths)
    lines = [
        "Policy Profile Backtest",
        "Generated: 2026-03-13",
        f"Rows loaded: {len(rows):,}",
        "Policy exclusions honored from backtest CSV (misprice + <1.25 favorite filters + ATP500 hard short-fav).",
        "Match staking: value_tiered (5-10=0.5u, 10-15=1u, 15-20=1.5u, 20+=2u).",
        "Historical report is ML-only; spread backtest is not integrated here.",
        "",
    ]

    for profile_name in args.profiles:
        picks = _score_profile(rows, PROFILE_RULES[profile_name])
        lines.extend(_format_profile(profile_name, picks))

    output = "\n".join(lines).rstrip() + "\n"
    print(output)
    if not args.dry_run:
        out_path = Path(args.out_txt)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Wrote report -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
