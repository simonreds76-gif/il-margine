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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from settlement_audit import (
    build_settlement_audit,
    load_settlement_overrides,
    write_audit,
)
from settlement_utils import (
    load_manual_settlement_results,
    load_results_snapshot,
    normalize_team_name,
    normalize_text_basic,
    resolve_fixture_result,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SIGNALS = ROOT / "data" / "team-shots" / "shadow" / "team-shots-shadow-signals.csv"
DEFAULT_SUMMARY = ROOT / "data" / "team-shots" / "shadow" / "team-shots-shadow-performance.txt"
DEFAULT_AUDIT = ROOT / "data" / "team-shots" / "shadow" / "settlement-audit.json"
DEFAULT_OVERRIDES = ROOT / "data" / "settlement-overrides.csv"

SIGNAL_FIELDS = [
    "date", "fixture_date", "kickoff_iso", "league", "home_team", "away_team", "team", "venue",
    "bookmaker", "line", "side", "book_odds", "model_prob",
    "model_fair_odds", "edge", "stake_units", "actual_shots", "result",
    "pnl", "pnl_staked", "settled_at", "closing_odds", "clv", "logged_at", "policy_version",
]

DEFAULT_ODDS_ARCHIVE = ROOT / "data" / "team-shots" / "team-shots-odds-history.csv"

def _pf(val, default=0.0):
    text = str(val or "").strip()
    try:
        return float(text) if text else default
    except ValueError:
        return default


def _norm(text: str) -> str:
    return normalize_text_basic(text)


def _norm_team(text: str) -> str:
    return normalize_team_name(text)


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


def load_odds_archive(path: Path) -> Dict[str, List[dict]]:
    """
    Load odds archive indexed by (match_date|home_norm|away_norm|team_norm|bookmaker_norm|line|side).
    Each key maps to a list of rows sorted by captured_at ascending.
    """
    index: Dict[str, List[dict]] = {}
    if not path.exists():
        return index
    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            match_date = (row.get("match_date") or "").strip()[:10]
            home = _norm_team(row.get("home_team", ""))
            away = _norm_team(row.get("away_team", ""))
            team = _norm_team(row.get("team", ""))
            bm = _norm(row.get("bookmaker", ""))
            line = str(row.get("line", "")).strip()
            side = (row.get("side") or "").strip().lower()
            if not match_date or not home or not team or not side:
                continue
            key = f"{match_date}|{home}|{away}|{team}|{bm}|{line}|{side}"
            any_key = f"__any__|{home}|{away}|{team}|{bm}|{line}|{side}"
            row = dict(row)
            index.setdefault(key, []).append(row)
            index.setdefault(any_key, []).append(row)
    for rows in index.values():
        rows.sort(key=lambda r: (r.get("captured_at") or ""))
    return index


def _signal_odds_keys(sig: dict, match_date: str = "") -> tuple[str, str]:
    home = _norm_team(sig.get("home_team", ""))
    away = _norm_team(sig.get("away_team", ""))
    team = _norm_team(sig.get("team", ""))
    bm = _norm(sig.get("bookmaker", ""))
    line = str(sig.get("line", "")).strip()
    side = (sig.get("side") or "").strip().lower()
    exact_key = f"{match_date}|{home}|{away}|{team}|{bm}|{line}|{side}" if match_date else ""
    any_key = f"__any__|{home}|{away}|{team}|{bm}|{line}|{side}"
    return exact_key, any_key


def resolve_match_date(sig: dict, odds_index: Dict[str, List[dict]]) -> str:
    """Resolve the fixture date, preferring explicit fields over logged-at date."""
    explicit = ((sig.get("fixture_date") or "").strip()[:10]) or ((sig.get("kickoff_iso") or "").strip()[:10])
    if explicit:
        return explicit

    _, any_key = _signal_odds_keys(sig)
    rows = odds_index.get(any_key, [])
    candidates = sorted({str(r.get("match_date") or "").strip()[:10] for r in rows if str(r.get("match_date") or "").strip()})
    if not candidates:
        return (sig.get("date") or "").strip()[:10]
    if len(candidates) == 1:
        return candidates[0]

    logged_date = ((sig.get("logged_at") or "").strip()[:10]) or ((sig.get("date") or "").strip()[:10])
    futureish = [candidate for candidate in candidates if not logged_date or candidate >= logged_date]
    if len(futureish) == 1:
        return futureish[0]
    if futureish:
        return min(futureish)
    return candidates[-1]


def find_closing_odds(
    sig: dict,
    odds_index: Dict[str, List[dict]],
) -> Optional[float]:
    """
    Return the latest scraped odds for this signal's match/team/line/book/side
    that were captured on or before the match date (i.e. before kickoff).
    """
    match_date = resolve_match_date(sig, odds_index)
    exact_key, any_key = _signal_odds_keys(sig, match_date)
    rows = odds_index.get(exact_key, []) if exact_key else []
    if not rows:
        rows = odds_index.get(any_key, [])

    # We do not need an exact kickoff scrape for a useful CLV proxy.
    # We do need to avoid accidentally using post-kickoff same-day prices.
    # The odds archive already carries kickoff_at, so use the latest sampled
    # price captured on/before the stored kickoff timestamp when available.
    kickoff_candidates = [str(r.get("kickoff_at") or "").strip() for r in rows if str(r.get("kickoff_at") or "").strip()]
    cutoff = max(kickoff_candidates) if kickoff_candidates else match_date + "T23:59:59"
    candidates = [r for r in rows if (r.get("captured_at") or "") <= cutoff]
    if not candidates:
        return None
    latest = max(candidates, key=lambda r: (r.get("captured_at") or ""))
    val = latest.get("odds_decimal", "")
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


def signal_fields_for_rows(signals: List[dict]) -> List[str]:
    ordered = list(SIGNAL_FIELDS)
    seen = set(ordered)
    for row in signals:
        for key in row.keys():
            if key not in seen:
                ordered.append(key)
                seen.add(key)
    return ordered


def settle_signals(
    signals: List[dict],
    results_lookup: Dict[str, dict],
    odds_index: Optional[Dict[str, List[dict]]] = None,
) -> Tuple[int, int]:
    """Update pending signals in-place. Returns (settled_count, still_pending)."""
    settled = 0
    still_pending = 0

    for sig in signals:
        if sig.get("result") not in ("pending", ""):
            if not sig.get("settled_at"):
                sig["settled_at"] = sig.get("logged_at", "")
            # Already settled â€” still try to fill missing closing_odds/clv if absent.
            if odds_index and not sig.get("closing_odds"):
                closing = find_closing_odds(sig, odds_index)
                if closing:
                    entry = _pf(sig.get("book_odds"))
                    sig["closing_odds"] = round(closing, 3)
                    sig["clv"] = round(entry / closing - 1, 4) if closing > 0 and entry > 0 else ""
            continue

        sig_date_str = resolve_match_date(sig, odds_index)
        home_norm = _norm_team(sig.get("home_team", ""))
        away_norm = _norm_team(sig.get("away_team", ""))

        try:
            sig_date_obj = date.fromisoformat(sig_date_str)
        except ValueError:
            still_pending += 1
            continue
        match_data = resolve_fixture_result(
            results_lookup,
            sig_date_obj,
            sig.get("home_team", ""),
            sig.get("away_team", ""),
        )
        if match_data is None:
            still_pending += 1
            continue

        if match_data.get("home_shots") is None or match_data.get("away_shots") is None:
            still_pending += 1
            continue

        team_norm = _norm_team(sig.get("team", ""))
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
        sig["fixture_date"] = sig_date_str
        sig["result"] = result
        sig["pnl"] = round(pnl, 3)
        stake_units = _pf(sig.get("stake_units", "1")) or 1.0
        sig["pnl_staked"] = round(pnl * stake_units, 3)
        sig["settled_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        # Capture closing odds and CLV from the odds archive.
        if odds_index:
            closing = find_closing_odds(sig, odds_index)
            if closing:
                sig["closing_odds"] = round(closing, 3)
                sig["clv"] = round(book_odds / closing - 1, 4) if closing > 0 and book_odds > 0 else ""
        settled += 1

    return settled, still_pending


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle team-shots shadow signals")
    parser.add_argument("--signals", type=Path, default=DEFAULT_SIGNALS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--odds-archive", type=Path, default=DEFAULT_ODDS_ARCHIVE)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--snapshot-date", type=str, default=None,
                        help="Preferred results snapshot date (YYYY-MM-DD). Defaults to today UTC.")
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

    # Always load the odds archive so we can backfill closing_odds/CLV on
    # already-settled signals that were logged before this feature existed.
    missing_clv = [s for s in signals if s.get("result") in ("won", "lost", "push") and not s.get("closing_odds")]
    print(f"Loading odds archive from {args.odds_archive}")
    odds_index = load_odds_archive(args.odds_archive)
    print(f"  {len(odds_index)} odds entries indexed (will backfill CLV for {len(missing_clv)} settled signals)")

    if not pending:
        print("  No pending signals to settle â€” running CLV backfill only.")
        settle_signals(signals, {}, odds_index)
        if missing_clv:
            fieldnames = signal_fields_for_rows(signals)
            with open(args.signals, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(signals)
            print(f"  CLV backfill written to {args.signals}")
        _write_summary(signals, args.summary)
        audit = build_settlement_audit(
            rows=signals,
            model="team-shots",
            now_utc=datetime.now(timezone.utc),
            settled_this_run=0,
            is_pending=lambda row: (row.get("result") or "").strip() == "pending",
            is_settled=lambda row: (row.get("result") or "").strip() in ("won", "lost", "push"),
            kickoff_fields=("kickoff_iso",),
            date_fields=("fixture_date", "date"),
            source_freshness={},
            overrides=load_settlement_overrides(DEFAULT_OVERRIDES),
        )
        write_audit(args.audit_out, audit)
        print(f"  Settlement audit written to {args.audit_out}")
        return

    all_results, source_freshness, snapshot_path, _snapshot_payload = load_results_snapshot(args.snapshot_date)
    if snapshot_path is None:
        print("  No results snapshot found; pending rows will remain pending.")
    else:
        print(f"  Loaded {len(all_results)} snapshot results from {snapshot_path}")
    manual_results = load_manual_settlement_results(DEFAULT_OVERRIDES)
    if manual_results:
        all_results = {**all_results, **manual_results}
        print(f"  Loaded {len(manual_results)} manual settlement override result(s)")

    settled, still_pending = settle_signals(signals, all_results, odds_index)
    print(f"\n  Settled: {settled}, still pending: {still_pending}")

    fieldnames = signal_fields_for_rows(signals)
    with open(args.signals, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(signals)
    print(f"  Updated {args.signals}")

    _write_summary(signals, args.summary)
    audit = build_settlement_audit(
        rows=signals,
        model="team-shots",
        now_utc=datetime.now(timezone.utc),
        settled_this_run=settled,
        is_pending=lambda row: (row.get("result") or "").strip() == "pending",
        is_settled=lambda row: (row.get("result") or "").strip() in ("won", "lost", "push"),
        kickoff_fields=("kickoff_iso",),
        date_fields=("fixture_date", "date"),
        source_freshness=source_freshness,
        overrides=load_settlement_overrides(DEFAULT_OVERRIDES),
    )
    write_audit(args.audit_out, audit)
    print(f"  Settlement audit written to {args.audit_out}")


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

        clv_vals = [_pf(s.get("clv"), float("nan")) for s in settled if s.get("clv")]
        clv_vals = [v for v in clv_vals if v == v]  # drop NaN
        if clv_vals:
            avg_clv = sum(clv_vals) / len(clv_vals) * 100
            lines.append(f"  Avg CLV:        {avg_clv:+.1f}%  (n={len(clv_vals)}, vs Bet365 close)")

    lines.append(f"\n  Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)

    text = "\n".join(lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
