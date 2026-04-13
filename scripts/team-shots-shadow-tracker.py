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
DEFAULT_SCANNER = ROOT / "data" / "team-shots" / "team-shots-scanner.csv"
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
    "date", "fixture_date", "kickoff_iso", "league", "home_team", "away_team", "team", "venue",
    "bookmaker", "line", "side", "book_odds", "model_prob",
    "model_fair_odds", "edge", "stake_units", "actual_shots", "result",
    "pnl", "pnl_staked", "settled_at", "closing_odds", "clv", "logged_at",
]


def _pf(val, default=0.0):
    text = str(val or "").strip()
    try:
        return float(text) if text else default
    except ValueError:
        return default


def _signal_key(row: dict) -> str:
    return "|".join([
        str(row.get("fixture_date", "") or row.get("date", ""))[:10],
        str(row.get("home_team", "")).strip().lower(),
        str(row.get("away_team", "")).strip().lower(),
        str(row.get("team", "")).strip().lower(),
        str(row.get("line", "")),
        str(row.get("side", "")).strip().lower(),
        str(row.get("bookmaker", "")).strip().lower(),
    ])


def _fixture_date(row: dict) -> str:
    return str(
        row.get("fixture_date", "")
        or row.get("date", "")
        or row.get("kickoff_iso", "")
    )[:10]


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
    return 0.0


def resolve_effective_stake(row: dict, fallback_edge: float) -> float:
    raw = str(row.get("effective_stake", "")).strip()
    if raw:
        return max(_pf(raw, 0.0), 0.0)
    return stake_for_edge(fallback_edge)


def repair_existing_signals(existing_signals: List[dict], source_rows: List[dict]) -> bool:
    source_by_key = {_signal_key(row): row for row in source_rows}
    changed = False

    for row in existing_signals:
        source = source_by_key.get(_signal_key(row))
        if not source:
            continue

        if not str(row.get("kickoff_iso", "")).strip() and str(source.get("kickoff_iso", "")).strip():
            row["kickoff_iso"] = source.get("kickoff_iso", "")
            changed = True
        if not str(row.get("date", "")).strip():
            row["date"] = source.get("date", "") or _fixture_date(source)
            changed = True
        if not str(row.get("fixture_date", "")).strip():
            row["fixture_date"] = _fixture_date(source)
            changed = True
        if not str(row.get("model_fair_odds", "")).strip():
            fair = source.get("model_fair_odds", "") or source.get("model_fair", "")
            if str(fair).strip():
                row["model_fair_odds"] = fair
                changed = True

    return changed


def _signal_quality(row: dict) -> tuple[int, str]:
    score = 0
    for field in ("kickoff_iso", "model_fair_odds", "logged_at", "closing_odds", "clv"):
        if str(row.get(field, "")).strip():
            score += 1
    if str(row.get("actual_shots", "")).strip():
        score += 2
    return score, str(row.get("logged_at", ""))


def dedupe_signals(rows: List[dict]) -> List[dict]:
    best_by_key: dict[str, dict] = {}
    for row in rows:
        key = _signal_key(row)
        existing = best_by_key.get(key)
        if existing is None or _signal_quality(row) > _signal_quality(existing):
            best_by_key[key] = row
    return list(best_by_key.values())


def track_signals(
    source_rows: List[dict],
    existing_signals: List[dict],
    existing_keys: Set[str],
    min_edge: float,
    bookmaker_filter: str = "",
) -> List[dict]:
    new_signals: List[dict] = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for comp in source_rows:
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
        stake_units = resolve_effective_stake(comp, edge)
        if stake_units <= 0:
            continue

        settled_at = ""
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
            settled_at = now
        else:
            result = "pending"
            pnl = 0.0
            pnl_staked = ""

        signal = {
            "date": comp.get("date", "") or _fixture_date(comp),
            "fixture_date": _fixture_date(comp),
            "kickoff_iso": comp.get("kickoff_iso", ""),
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
            "model_fair_odds": comp.get("model_fair_odds", "") or comp.get("model_fair", ""),
            "edge": comp.get("edge", ""),
            "stake_units": stake_units,
            "actual_shots": actual if actual > 0 else "",
            "result": result,
            "pnl": round(pnl, 3) if result != "pending" else "",
            "pnl_staked": pnl_staked,
            "settled_at": settled_at,
            "closing_odds": "",
            "clv": "",
            "logged_at": now,
        }
        new_signals.append(signal)
        existing_keys.add(key)

    return new_signals


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
    parser.add_argument("--scanner", type=Path, default=DEFAULT_SCANNER)
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
    print(f"Loading scanner rows from {args.scanner}")
    scanner_rows = load_comparisons(args.scanner)
    print(f"  Scanner rows: {len(scanner_rows)}")

    # Never prune pending signals — once logged a signal survives until settled.
    # (Previously this filtered out pending signals not in the current comparison CSV,
    # which deleted signals when a match date passed but FBRef hadn't been scraped yet.)
    source_rows = scanner_rows if scanner_rows else comparisons
    source_name = args.scanner if scanner_rows else args.comparison
    print(f"Using signal source: {source_name}")

    if repair_existing_signals(existing, source_rows):
        print("  Repaired existing signal metadata from current source rows")

    keys = {_signal_key(row) for row in existing}

    new = track_signals(source_rows, existing, keys, args.min_edge, args.bookmaker)
    print(f"  New signals: {len(new)}")

    all_signals = dedupe_signals(existing + new)
    if new or not existing:
        write_signals(all_signals, args.signals)
        print(f"  Signals written to {args.signals}")

    summary_text = write_summary(all_signals, args.summary)
    print(summary_text)


if __name__ == "__main__":
    main()
