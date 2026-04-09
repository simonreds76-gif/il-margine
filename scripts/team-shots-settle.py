#!/usr/bin/env python3
"""
Settle pending team-shots shadow signals using actual match shot data.

Downloads the current season's CSV from Football-Data.co.uk for each league,
extracts the actual shots (HS/AS), and updates any pending signals with
won/lost/push result and PnL.

Usage:
  python scripts/team-shots-settle.py
  python scripts/team-shots-settle.py --signals data/team-shots/shadow/team-shots-shadow-signals.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SIGNALS = ROOT / "data" / "team-shots" / "shadow" / "team-shots-shadow-signals.csv"
DEFAULT_SUMMARY = ROOT / "data" / "team-shots" / "shadow" / "team-shots-shadow-performance.txt"
DEFAULT_HISTORICAL = ROOT / "data" / "team-shots" / "historical"

BASE_URL = "https://www.football-data.co.uk"

LEAGUE_CODES = {
    "epl": "E0", "serie-a": "I1", "la-liga": "SP1",
    "bundesliga": "D1", "ligue-1": "F1",
}

SIGNAL_FIELDS = [
    "date", "league", "home_team", "away_team", "team", "venue",
    "bookmaker", "line", "side", "book_odds", "model_prob",
    "model_fair_odds", "edge", "actual_shots", "result", "pnl",
    "logged_at",
]


def _pf(val, default=0.0):
    text = str(val or "").strip()
    try:
        return float(text) if text else default
    except ValueError:
        return default


def _norm(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _parse_date(val: str) -> Optional[date]:
    text = (val or "").strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def season_code(start_year: int) -> str:
    end = (start_year + 1) % 100
    return f"{start_year % 100:02d}{end:02d}"


def fetch_current_season_results(league: str) -> Dict[str, dict]:
    """
    Fetch the current season's CSV and return a lookup keyed by
    (date, home_team_norm, away_team_norm) -> {HS, AS, HST, AST}.
    """
    code = LEAGUE_CODES.get(league)
    if not code:
        return {}

    now = datetime.now()
    start_year = now.year if now.month >= 8 else now.year - 1
    sc = season_code(start_year)
    url = f"{BASE_URL}/mmz4281/{sc}/{code}.csv"

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [WARN] Could not fetch {url}: {exc}")
        return {}

    results: Dict[str, dict] = {}
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        d = _parse_date(row.get("Date", ""))
        if d is None:
            continue
        home = _norm(row.get("HomeTeam", ""))
        away = _norm(row.get("AwayTeam", ""))
        hs = row.get("HS", "")
        as_ = row.get("AS", "")
        if not hs and not as_:
            continue
        key = f"{d.isoformat()}|{home}|{away}"
        results[key] = {
            "home_shots": int(_pf(hs)),
            "away_shots": int(_pf(as_)),
            "home_sot": int(_pf(row.get("HST", "0"))),
            "away_sot": int(_pf(row.get("AST", "0"))),
        }

    return results


def load_historical_results(historical_dir: Path) -> Dict[str, dict]:
    """Load from previously downloaded CSVs as fallback."""
    results: Dict[str, dict] = {}
    if not historical_dir.exists():
        return results

    for csv_path in historical_dir.glob("*.csv"):
        if csv_path.name == "all-historical-matches.csv":
            continue
        with open(csv_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                d = _parse_date(row.get("Date", ""))
                if d is None:
                    continue
                home = _norm(row.get("HomeTeam", ""))
                away = _norm(row.get("AwayTeam", ""))
                hs = row.get("HS", "")
                if not hs:
                    continue
                key = f"{d.isoformat()}|{home}|{away}"
                results[key] = {
                    "home_shots": int(_pf(row.get("HS", "0"))),
                    "away_shots": int(_pf(row.get("AS", "0"))),
                    "home_sot": int(_pf(row.get("HST", "0"))),
                    "away_sot": int(_pf(row.get("AST", "0"))),
                }
    return results


def settle_signals(
    signals: List[dict],
    results_lookup: Dict[str, dict],
) -> Tuple[int, int]:
    """Update pending signals in-place. Returns (settled_count, still_pending)."""
    settled = 0
    still_pending = 0

    for sig in signals:
        if sig.get("result") not in ("pending", ""):
            continue

        sig_date_str = (sig.get("date") or "")[:10]
        home_norm = _norm(sig.get("home_team", ""))
        away_norm = _norm(sig.get("away_team", ""))

        try:
            sig_date_obj = date.fromisoformat(sig_date_str)
        except ValueError:
            still_pending += 1
            continue

        # Try exact date, then ±1 day (timezone/schedule fuzziness)
        match_data = None
        for delta in (0, 1, -1):
            check_date = sig_date_obj + timedelta(days=delta)
            key = f"{check_date.isoformat()}|{home_norm}|{away_norm}"
            match_data = results_lookup.get(key)
            if match_data:
                break

        if match_data is None:
            still_pending += 1
            continue

        team_norm = _norm(sig.get("team", ""))
        if team_norm == home_norm:
            actual_shots = match_data["home_shots"]
        elif team_norm == away_norm:
            actual_shots = match_data["away_shots"]
        else:
            actual_shots = match_data["home_shots"]

        line = _pf(sig.get("line"))
        side = (sig.get("side") or "").strip().lower()
        book_odds = _pf(sig.get("book_odds"))

        if side == "over":
            won = actual_shots > line
            result = "won" if won else "lost"
            pnl = (book_odds - 1.0) if won else -1.0
        else:
            if actual_shots < line:
                result = "won"
                pnl = book_odds - 1.0
            elif actual_shots == int(line):
                result = "push"
                pnl = 0.0
            else:
                result = "lost"
                pnl = -1.0

        sig["actual_shots"] = actual_shots
        sig["result"] = result
        sig["pnl"] = round(pnl, 3)
        settled += 1

    return settled, still_pending


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle team-shots shadow signals")
    parser.add_argument("--signals", type=Path, default=DEFAULT_SIGNALS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--historical-dir", type=Path, default=DEFAULT_HISTORICAL)
    args = parser.parse_args()

    if not args.signals.exists():
        print(f"No signals file at {args.signals}")
        return

    print(f"Loading signals from {args.signals}")
    signals: List[dict] = []
    with open(args.signals, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            signals.append(row)
    pending = [s for s in signals if s.get("result") in ("pending", "")]
    print(f"  Total: {len(signals)}, pending: {len(pending)}")

    if not pending:
        print("  No pending signals to settle.")
        return

    leagues_needed = set()
    for s in pending:
        league = (s.get("league") or "").strip()
        if league:
            leagues_needed.add(league)
    print(f"  Leagues to fetch: {', '.join(sorted(leagues_needed))}")

    all_results: Dict[str, dict] = load_historical_results(args.historical_dir)
    print(f"  Historical results loaded: {len(all_results)}")

    for league in leagues_needed:
        fresh = fetch_current_season_results(league)
        print(f"  [live] {league}: {len(fresh)} matches fetched")
        all_results.update(fresh)

    settled, still_pending = settle_signals(signals, all_results)
    print(f"\n  Settled: {settled}, still pending: {still_pending}")

    with open(args.signals, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SIGNAL_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(signals)
    print(f"  Updated {args.signals}")

    _write_summary(signals, args.summary)


def _write_summary(signals: List[dict], path: Path) -> None:
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("  TEAM SHOTS SHADOW -- PERFORMANCE SUMMARY")
    lines.append("=" * 60)

    settled = [s for s in signals if s.get("result") in ("won", "lost", "push")]
    pending = [s for s in signals if s.get("result") == "pending"]
    lines.append(f"  Total signals:  {len(signals)}")
    lines.append(f"  Settled:        {len(settled)}")
    lines.append(f"  Pending:        {len(pending)}")

    if settled:
        total_pnl = sum(_pf(s.get("pnl")) for s in settled)
        wins = sum(1 for s in settled if s.get("result") == "won")
        losses = sum(1 for s in settled if s.get("result") == "lost")
        pushes = sum(1 for s in settled if s.get("result") == "push")
        roi = total_pnl / len(settled) * 100

        lines.append(f"  PnL:            {total_pnl:+.1f}u")
        lines.append(f"  ROI:            {roi:+.1f}%")
        lines.append(f"  Record:         {wins}W / {losses}L / {pushes}P")

    lines.append(f"\n  Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)

    text = "\n".join(lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
