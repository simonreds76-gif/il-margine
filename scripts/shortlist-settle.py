#!/usr/bin/env python3
"""
Settle matchday shortlist value-bets against actual corner results.

Reads all value-bets-{date}.csv files from data/shortlist/, matches each bet
against actual corner results in data/team-shots/historical/, and writes:

  data/shortlist/settled-pnl.csv          — all bets with result + running P&L
  data/shortlist/corners-live-pnl.txt     — human-readable P&L report

Matching uses the bet's kick_off date if present (new format), falling back to
the file creation date for older files.  This fixes the bug where Tuesday
shortlists for Saturday games never settled.

Usage:
  python scripts/shortlist-settle.py
  python scripts/shortlist-settle.py --date 2026-04-12
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
from typing import Dict, List, Optional
import re
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
SHORTLIST_DIR   = ROOT / "data" / "shortlist"
HISTORICAL_DIR  = ROOT / "data" / "team-shots" / "historical"
SETTLED_PATH    = ROOT / "data" / "shortlist" / "settled-pnl.csv"
PNL_REPORT_PATH = ROOT / "data" / "shortlist" / "corners-live-pnl.txt"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _parse_date(val: str) -> Optional[date]:
    text = (val or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            dt = datetime.strptime(text[:19], fmt[:len(text[:19].replace("T", " "))])
            return dt.date()
        except ValueError:
            pass
    # ISO with timezone suffix
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _pf(val: str, default: float = 0.0) -> float:
    try:
        return float((val or "").strip() or default)
    except ValueError:
        return default


# ── Load actual results ────────────────────────────────────────────────────────

def load_actual_results() -> Dict[str, dict]:
    """
    Load historical corner results.
    Key: "{date}|{norm(home)}|{norm(away)}"
    """
    results: Dict[str, dict] = {}
    for csv_path in sorted(HISTORICAL_DIR.glob("*.csv")):
        if "all-historical" in csv_path.name:
            continue
        with open(csv_path, "r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                d = _parse_date(row.get("Date", "") or row.get("date", ""))
                if d is None:
                    continue
                home = _norm(row.get("HomeTeam") or row.get("home_team") or "")
                away = _norm(row.get("AwayTeam") or row.get("away_team") or "")
                hc = (row.get("HC") or "").strip()
                ac = (row.get("AC") or "").strip()
                if not hc or not ac:
                    continue
                key = f"{d.isoformat()}|{home}|{away}"
                results[key] = {
                    "total_corners": int(hc) + int(ac),
                }
    return results


# ── Settle ────────────────────────────────────────────────────────────────────

def settle_all(target_date: Optional[str] = None) -> List[dict]:
    actual = load_actual_results()
    print(f"Loaded {len(actual)} historical results with corners")

    bet_files = sorted(SHORTLIST_DIR.glob("value-bets-*.csv"))
    if target_date:
        bet_files = [f for f in bet_files if target_date in f.name]

    if not bet_files:
        print("No value-bet files found.")
        return []

    rows: List[dict] = []
    for path in bet_files:
        file_date_str = path.name.replace("value-bets-", "").replace(".csv", "")
        bets = list(csv.DictReader(open(path, "r", encoding="utf-8")))

        for bet in bets:
            match_str = bet.get("match", "")
            parts = match_str.split(" vs ")
            if len(parts) != 2:
                continue
            home_n = _norm(parts[0])
            away_n = _norm(parts[1])

            # Use kick_off date if present, else fall back to file date
            kick_off_raw = (bet.get("kick_off") or "").strip()
            match_date = _parse_date(kick_off_raw) or _parse_date(file_date_str)

            settled = dict(bet)
            settled["file_date"] = file_date_str

            if match_date is None:
                settled["match_date"] = ""
                settled["settled"] = "pending"
                settled["actual_total_corners"] = ""
                settled["won"] = ""
                settled["pnl_units"] = ""
                settled["pnl_staked"] = ""
                rows.append(settled)
                continue

            settled["match_date"] = match_date.isoformat()

            # Try exact date, then ±1 day (timezone/schedule fuzziness)
            result = None
            for delta in (0, 1, -1):
                check_date = match_date + timedelta(days=delta)
                key = f"{check_date.isoformat()}|{home_n}|{away_n}"
                result = actual.get(key)
                if result:
                    break

            if result:
                total_corners = result["total_corners"]
                line = float(bet.get("line", 0))
                side = bet.get("side", "")
                bookie_odds = _pf(bet.get("bookie_odds", "0"))
                stake = _pf(bet.get("stake", "1"), 1.0)

                won = (total_corners > line) if side == "over" else (total_corners <= int(line))
                pnl_units = round((bookie_odds - 1.0) if won else -1.0, 3)
                pnl_staked = round(pnl_units * stake, 3)

                settled["settled"]              = "yes"
                settled["actual_total_corners"] = total_corners
                settled["won"]                  = "yes" if won else "no"
                settled["pnl_units"]            = pnl_units
                settled["pnl_staked"]           = pnl_staked
            else:
                settled["settled"]              = "pending"
                settled["actual_total_corners"] = ""
                settled["won"]                  = ""
                settled["pnl_units"]            = ""
                settled["pnl_staked"]           = ""

            rows.append(settled)

    return rows


# ── P&L report ────────────────────────────────────────────────────────────────

def _section(
    lines: List[str],
    label: str,
    bets: List[dict],
    indent: int = 2,
) -> None:
    p = " " * indent
    won    = [b for b in bets if b.get("won") == "yes"]
    lost   = [b for b in bets if b.get("won") == "no"]
    n      = len(won) + len(lost)
    if n == 0:
        lines.append(f"{p}{label}: no settled bets")
        return
    pnl    = sum(_pf(b.get("pnl_staked", "")) for b in won + lost)
    staked = sum(_pf(b.get("stake", "1"), 1.0) for b in won + lost)
    roi    = pnl / staked * 100 if staked else 0.0
    lines.append(
        f"{p}{label}: {n} settled  W{len(won)}/L{len(lost)}  "
        f"({len(won)/n*100:.0f}%)  P&L {pnl:+.2f}u  ROI {roi:+.1f}%"
    )


def build_report(rows: List[dict]) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    out: List[str] = [
        "=" * 70,
        "  CORNERS O/U — LIVE P&L TRACKER",
        f"  Updated: {now}",
        "=" * 70,
        "",
    ]

    settled = [r for r in rows if r.get("settled") == "yes"]
    pending = [r for r in rows if r.get("settled") == "pending"]

    out.append(f"  Total bets tracked : {len(rows)}")
    out.append(f"  Settled            : {len(settled)}")
    out.append(f"  Pending            : {len(pending)}")
    out.append("")

    if not settled:
        out.append("  No settled bets yet.")
        out.append("=" * 70)
        return "\n".join(out)

    # Sort settled by match_date for running P&L
    settled_sorted = sorted(settled, key=lambda r: r.get("match_date", ""))

    # Running P&L
    running = 0.0
    peak    = 0.0
    max_dd  = 0.0
    for b in settled_sorted:
        running += _pf(b.get("pnl_staked", ""))
        if running > peak:
            peak = running
        max_dd = max(max_dd, peak - running)

    won_all  = [b for b in settled if b.get("won") == "yes"]
    lost_all = [b for b in settled if b.get("won") == "no"]
    total_staked = sum(_pf(b.get("stake", "1"), 1.0) for b in settled)
    total_pnl    = sum(_pf(b.get("pnl_staked", "")) for b in settled)
    roi = total_pnl / total_staked * 100 if total_staked else 0.0

    out.append("  ── OVERALL ──────────────────────────────────────────────────")
    out.append(f"  Settled: {len(settled)}  W{len(won_all)}/L{len(lost_all)}  "
               f"({len(won_all)/len(settled)*100:.0f}%)")
    out.append(f"  Total staked : {total_staked:.1f}u")
    out.append(f"  P&L          : {total_pnl:+.2f}u")
    out.append(f"  ROI          : {roi:+.1f}%")
    out.append(f"  Max drawdown : {max_dd:.1f}u")
    out.append("")

    out.append("  ── BY LEAGUE ────────────────────────────────────────────────")
    leagues = sorted(set(b.get("league", "?") for b in settled))
    for lg in leagues:
        _section(out, lg, [b for b in settled if b.get("league") == lg])
    out.append("")

    out.append("  ── BY LINE ──────────────────────────────────────────────────")
    for line in ["8.5", "9.5", "10.5", "11.5"]:
        subset = [b for b in settled if str(b.get("line", "")) == line]
        if subset:
            _section(out, f"Line {line}", subset)
    out.append("")

    out.append("  ── BY SIDE ──────────────────────────────────────────────────")
    for side in ["over", "under"]:
        _section(out, side.capitalize(), [b for b in settled if b.get("side") == side])
    out.append("")

    out.append("  ── BY EDGE BAND ─────────────────────────────────────────────")
    bands = [("12-15%", 0.12, 0.15), ("15-20%", 0.15, 0.20),
             ("20-25%", 0.20, 0.25), ("25%+",   0.25, 1.0)]
    for label, lo, hi in bands:
        subset = [b for b in settled if lo <= _pf(b.get("edge", "0")) < hi]
        if subset:
            _section(out, label, subset)
    out.append("")

    # Recent bets table (last 15 settled)
    recent = settled_sorted[-15:][::-1]
    out.append("  ── RECENT RESULTS (latest first) ────────────────────────────")
    out.append(f"  {'Date':<11}  {'Match':<28}  {'Line':>5}  {'Side':>5}  "
               f"{'Edge':>6}  {'Odds':>5}  {'W/L':>3}  {'P&L':>6}")
    out.append(f"  {'-'*11}  {'-'*28}  {'-'*5}  {'-'*5}  "
               f"{'-'*6}  {'-'*5}  {'-'*3}  {'-'*6}")
    for b in recent:
        won_str = "W" if b.get("won") == "yes" else "L"
        pnl_str = f"{_pf(b.get('pnl_staked','')):+.2f}u"
        edge_str = f"{_pf(b.get('edge','0')):.0%}"
        out.append(
            f"  {b.get('match_date','?'):<11}  "
            f"{b.get('match','?')[:28]:<28}  "
            f"{float(b.get('line',0)):>5.1f}  "
            f"{b.get('side','?'):>5}  "
            f"{edge_str:>6}  "
            f"{_pf(b.get('bookie_odds','0')):>5.2f}  "
            f"{won_str:>3}  "
            f"{pnl_str:>6}"
        )

    out += ["", "=" * 70]
    return "\n".join(out)


# ── Output CSV fields ─────────────────────────────────────────────────────────

SETTLED_FIELDS = [
    "file_date", "match_date", "match", "kick_off", "league", "market",
    "line", "side",
    "model_prob", "model_prob_raw", "model_fair", "bookmaker", "bookie_odds",
    "edge", "stake", "stake_label",
    "lambda_h", "lambda_a",
    "settled", "actual_total_corners", "won", "pnl_units", "pnl_staked",
]


def write_settled_csv(rows: List[dict]) -> None:
    if not rows:
        return
    # running P&L column — sorted by match_date, pending at end
    settled_rows = sorted(
        [r for r in rows if r.get("settled") == "yes"],
        key=lambda r: r.get("match_date", ""),
    )
    pending_rows = [r for r in rows if r.get("settled") != "yes"]

    running = 0.0
    for r in settled_rows:
        running += _pf(r.get("pnl_staked", ""))
        r["running_pnl"] = round(running, 3)
    for r in pending_rows:
        r["running_pnl"] = ""

    all_rows = settled_rows + pending_rows
    fields = SETTLED_FIELDS + ["running_pnl"]
    # include any extra columns from the bet CSV that aren't in SETTLED_FIELDS
    extra = [k for k in (all_rows[0].keys() if all_rows else [])
             if k not in fields]
    fields += extra

    with open(SETTLED_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Settled CSV  → {SETTLED_PATH}  ({len(settled_rows)} settled, {len(pending_rows)} pending)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Settle matchday shortlist")
    parser.add_argument("--date", type=str, default=None,
                        help="Settle only files containing this date string")
    args = parser.parse_args()

    rows = settle_all(args.date)
    if not rows:
        return

    write_settled_csv(rows)

    report = build_report(rows)
    print("\n" + report)

    with open(PNL_REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    print(f"P&L report   → {PNL_REPORT_PATH}")


if __name__ == "__main__":
    main()
