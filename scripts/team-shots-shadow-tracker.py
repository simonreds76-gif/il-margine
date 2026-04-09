#!/usr/bin/env python3
"""
Shadow-log team shots bets when model edge exceeds threshold.

Reads the latest team-shots comparison output (or live model predictions
+ odds archive) and appends qualifying rows to the shadow signals CSV.
Also writes a compact performance summary.

Usage:
  python scripts/team-shots-shadow-tracker.py
  python scripts/team-shots-shadow-tracker.py --min-edge 0.08 --bookmaker Bet365
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMPARISON = ROOT / "data" / "team-shots" / "team-shots-comparison.csv"
DEFAULT_SIGNALS = ROOT / "data" / "team-shots" / "shadow" / "team-shots-shadow-signals.csv"
DEFAULT_SUMMARY = ROOT / "data" / "team-shots" / "shadow" / "team-shots-shadow-performance.txt"

MIN_EDGE = 0.05
MIN_ODDS = 1.50
MAX_ODDS = 5.00

# Edge % → stake units. Same ladder as corners.
# 5-8%: 0.5u  |  8-12%: 1u  |  12-16%: 1.5u  |  16%+: 2u
STAKE_BANDS: list[tuple[float, float]] = [
    (0.16, 2.0),
    (0.12, 1.5),
    (0.08, 1.0),
    (0.05, 0.5),
]

SIGNAL_FIELDS = [
    "date", "league", "home_team", "away_team", "team", "venue",
    "bookmaker", "line", "side", "book_odds", "model_prob",
    "model_fair_odds", "edge", "stake_units", "actual_shots", "result",
    "pnl", "pnl_staked", "logged_at",
]


def _pf(val, default=0.0):
    text = str(val or "").strip()
    try:
        return float(text) if text else default
    except ValueError:
        return default


def _signal_key(row: dict) -> str:
    return "|".join([
        str(row.get("date", ""))[:10],
        str(row.get("home_team", "")).strip().lower(),
        str(row.get("away_team", "")).strip().lower(),
        str(row.get("team", "")).strip().lower(),
        str(row.get("line", "")),
        str(row.get("side", "")).strip().lower(),
        str(row.get("bookmaker", "")).strip().lower(),
    ])


def load_existing_signals(path: Path) -> tuple[list[dict], set[str]]:
    rows: List[dict] = []
    keys: Set[str] = set()
    if not path.exists():
        return rows, keys
    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
            keys.add(_signal_key(row))
    return rows, keys


def load_comparisons(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


def stake_for_edge(edge: float) -> float:
    for threshold, units in STAKE_BANDS:
        if edge >= threshold:
            return units
    return 0.5


def track_signals(
    comparisons: List[dict],
    existing_signals: List[dict],
    existing_keys: Set[str],
    min_edge: float,
    bookmaker_filter: str = "",
) -> List[dict]:
    new_signals: List[dict] = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for comp in comparisons:
        edge = _pf(comp.get("edge"))
        book_odds = _pf(comp.get("book_odds"))
        line = _pf(comp.get("line"))

        if edge < min_edge:
            continue
        if book_odds < MIN_ODDS or book_odds > MAX_ODDS:
            continue
        if bookmaker_filter:
            bm = (comp.get("bookmaker") or "").strip().lower()
            if bm != bookmaker_filter.lower():
                continue

        key = _signal_key(comp)
        if key in existing_keys:
            continue

        actual = int(_pf(comp.get("actual_shots", 0)))
        side = (comp.get("side") or "").strip().lower()
        stake_units = stake_for_edge(edge)

        if actual > 0:
            if side == "over":
                result = "won" if actual > line else "lost"
            else:
                if actual < line:
                    result = "won"
                elif actual == int(line):
                    result = "push"
                else:
                    result = "lost"
            pnl = _pf(comp.get("pnl"))
            pnl_staked = round(pnl * stake_units, 3)
        else:
            result = "pending"
            pnl = 0.0
            pnl_staked = ""

        signal = {
            "date": comp.get("date", ""),
            "league": comp.get("league", ""),
            "home_team": comp.get("home_team", ""),
            "away_team": comp.get("away_team", ""),
            "team": comp.get("team", ""),
            "venue": comp.get("venue", ""),
            "bookmaker": comp.get("bookmaker", ""),
            "line": comp.get("line", ""),
            "side": side,
            "book_odds": comp.get("book_odds", ""),
            "model_prob": comp.get("model_prob", ""),
            "model_fair_odds": comp.get("model_fair_odds", ""),
            "edge": comp.get("edge", ""),
            "stake_units": stake_units,
            "actual_shots": actual if actual > 0 else "",
            "result": result,
            "pnl": round(pnl, 3) if result != "pending" else "",
            "pnl_staked": pnl_staked,
            "logged_at": now,
        }
        new_signals.append(signal)
        existing_keys.add(key)

    return new_signals


def current_live_keys(
    comparisons: List[dict],
    min_edge: float,
    bookmaker_filter: str = "",
) -> Set[str]:
    keys: Set[str] = set()
    for comp in comparisons:
        edge = _pf(comp.get("edge"))
        book_odds = _pf(comp.get("book_odds"))
        line = _pf(comp.get("line"))

        if edge < min_edge:
            continue
        if book_odds < MIN_ODDS or book_odds > MAX_ODDS:
            continue
        if bookmaker_filter:
            bm = (comp.get("bookmaker") or "").strip().lower()
            if bm != bookmaker_filter.lower():
                continue
        keys.add(_signal_key(comp))
    return keys


def write_signals(all_signals: List[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SIGNAL_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_signals)


def write_summary(all_signals: List[dict], path: Path) -> str:
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("  TEAM SHOTS SHADOW -- PERFORMANCE SUMMARY")
    lines.append("=" * 60)

    settled = [s for s in all_signals if s.get("result") in ("won", "lost", "push")]
    pending = [s for s in all_signals if s.get("result") == "pending"]
    lines.append(f"  Total signals:  {len(all_signals)}")
    lines.append(f"  Settled:        {len(settled)}")
    lines.append(f"  Pending:        {len(pending)}")

    if settled:
        total_pnl = sum(_pf(s.get("pnl")) for s in settled)
        total_staked = sum(_pf(s.get("stake_units", 1)) for s in settled)
        total_pnl_staked = sum(_pf(s.get("pnl_staked")) for s in settled)
        wins = sum(1 for s in settled if s.get("result") == "won")
        losses = sum(1 for s in settled if s.get("result") == "lost")
        pushes = sum(1 for s in settled if s.get("result") == "push")
        roi_flat = total_pnl / len(settled) * 100
        roi_staked = total_pnl_staked / total_staked * 100 if total_staked else 0

        lines.append(f"  PnL (flat 1u):  {total_pnl:+.1f}u   ROI: {roi_flat:+.1f}%")
        lines.append(f"  PnL (staked):   {total_pnl_staked:+.1f}u   ROI: {roi_staked:+.1f}%  ({total_staked:.1f}u staked)")
        lines.append(f"  Record:         {wins}W / {losses}L / {pushes}P")
        lines.append(f"  Avg odds:       {sum(_pf(s.get('book_odds')) for s in settled)/len(settled):.3f}")
        lines.append(f"  Avg edge:       {sum(_pf(s.get('edge')) for s in settled)/len(settled):.3f}")

        lines.append("")
        lines.append("  By league:")
        leagues = sorted(set(s.get("league", "") for s in settled))
        for league in leagues:
            lb = [s for s in settled if s.get("league") == league]
            lp = sum(_pf(s.get("pnl")) for s in lb)
            lps = sum(_pf(s.get("pnl_staked")) for s in lb)
            lw = sum(1 for s in lb if s.get("result") == "won")
            lr = lp / len(lb) * 100 if lb else 0
            lines.append(f"    {league:15s}: n={len(lb):4d}  PnL={lp:+6.1f}u  ROI={lr:+5.1f}%  staked={lps:+.1f}u  W={lw}")

        lines.append("")
        lines.append("  By side:")
        for side in ["over", "under"]:
            sb = [s for s in settled if s.get("side") == side]
            if not sb:
                continue
            sp = sum(_pf(s.get("pnl")) for s in sb)
            sw = sum(1 for s in sb if s.get("result") == "won")
            sr = sp / len(sb) * 100
            lines.append(f"    {side:6s}: n={len(sb):4d}  PnL={sp:+6.1f}u  ROI={sr:+5.1f}%  W={sw}")

    lines.append("")
    lines.append(f"  Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)

    text = "\n".join(lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Team shots shadow signal tracker")
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--signals", type=Path, default=DEFAULT_SIGNALS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--min-edge", type=float, default=MIN_EDGE)
    parser.add_argument("--bookmaker", default="")
    args = parser.parse_args()

    print("Loading existing shadow signals...")
    existing, keys = load_existing_signals(args.signals)
    print(f"  Existing: {len(existing)}")

    print(f"Loading comparisons from {args.comparison}")
    comparisons = load_comparisons(args.comparison)
    print(f"  Comparisons: {len(comparisons)}")

    live_keys = current_live_keys(comparisons, args.min_edge, args.bookmaker)
    existing = [
        row
        for row in existing
        if row.get("result") in ("won", "lost", "push") or _signal_key(row) in live_keys
    ]
    keys = {_signal_key(row) for row in existing}

    new = track_signals(comparisons, existing, keys, args.min_edge, args.bookmaker)
    print(f"  New signals: {len(new)}")

    all_signals = existing + new
    if new or not existing:
        write_signals(all_signals, args.signals)
        print(f"  Signals written to {args.signals}")

    summary_text = write_summary(all_signals, args.summary)
    print(summary_text)


if __name__ == "__main__":
    main()
