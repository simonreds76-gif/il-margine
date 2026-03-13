#!/usr/bin/env python3
"""
Collect settled data for Hard | Masters 1000 | value ≥5% segment.

Extracts from backtest-results-*.csv the rows that match the live pipeline
strict policy: Hard surface, Masters 1000 series, value_pct >= 5,
policy_excluded = False, bet_result in (win, loss).

Output: data/backtest/settled-strict-segment.csv

This is the gold dataset for validating the model's best segment.
Run after backtest to refresh.

Usage:
  python scripts/collect-settled-strict-segment.py
  python scripts/collect-settled-strict-segment.py --files data/backtest/backtest-results-2024.csv data/backtest/backtest-results-2025.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILES = [
    ROOT / "data" / "backtest" / "backtest-results-2024.csv",
    ROOT / "data" / "backtest" / "backtest-results-2025.csv",
]
DEFAULT_OUTPUT = ROOT / "data" / "backtest" / "settled-strict-segment.csv"


def main():
    parser = argparse.ArgumentParser(description="Collect Hard | Masters 1000 | value≥10% settled segment from backtest.")
    parser.add_argument("--files", nargs="+", default=[str(p) for p in DEFAULT_FILES if p.exists()])
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--min-value", type=float, default=5.0)
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    for path in args.files:
        p = Path(path)
        if not p.exists():
            print(f"  Skip (not found): {p}")
            continue
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                surface = (r.get("surface") or "").strip()
                series = (r.get("series") or "").strip()
                try:
                    value_pct = float(r.get("value_pct") or 0)
                except (ValueError, TypeError):
                    value_pct = 0
                policy_excluded = (r.get("policy_excluded") or "").strip().lower() in ("true", "1", "yes")
                bet_result = (r.get("bet_result") or "").strip().lower()

                if surface != "Hard" or series != "Masters 1000":
                    continue
                if value_pct < args.min_value:
                    continue
                if policy_excluded:
                    continue
                if bet_result not in ("win", "loss"):
                    continue

                rows.append(r)

    rows.sort(key=lambda r: (r.get("date") or "", r.get("player1") or ""))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        print("No rows matching Hard | Masters 1000 | value≥5% | bet placed.")
        return

    fieldnames = list(rows[0].keys())
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    wins = sum(1 for r in rows if (r.get("bet_result") or "").strip().lower() == "win")
    # ROI: flat 1u per bet at Pinnacle closing odds (psw/psl)
    # pinnacle_odds = p1, pinnacle_odds_loser = p2
    profit_units = 0.0
    for r in rows:
        side = (r.get("bet_side") or "").strip().lower()
        res = (r.get("bet_result") or "").strip().lower()
        try:
            odds1 = float(r.get("pinnacle_odds") or r.get("our_odds") or 0)
            odds2 = float(r.get("pinnacle_odds_loser") or 0)
            if odds2 <= 0:
                prob1 = float(r.get("our_prob") or 0.5)
                odds2 = 1.0 / (1.0 - prob1) if prob1 < 1 else 2.0
        except (ValueError, TypeError):
            odds1, odds2 = 2.0, 2.0
        odds = odds1 if side == "winner" else odds2
        profit_units += (odds - 1.0) if res == "win" else -1.0
    roi_pct = 100.0 * profit_units / len(rows) if rows else 0.0
    print(f"Collected {len(rows)} settled bets (Hard | Masters 1000 | value>={args.min_value}%)")
    print(f"  Wins: {wins}, Losses: {len(rows)-wins}")
    print(f"  ROI: {roi_pct:+.2f}%  P/L: {profit_units:+.2f}u")
    print(f"  Output: {out_path}")


if __name__ == "__main__":
    main()
