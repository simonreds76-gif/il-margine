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

from fotmob_match_stats import fetch_fotmob_recent_results
from settlement_audit import (
    build_settlement_audit,
    emit_github_annotations,
    load_settlement_overrides,
    write_audit,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SIGNALS = ROOT / "data" / "team-shots" / "shadow" / "team-shots-shadow-signals.csv"
DEFAULT_SUMMARY = ROOT / "data" / "team-shots" / "shadow" / "team-shots-shadow-performance.txt"
DEFAULT_HISTORICAL = ROOT / "data" / "team-shots" / "historical"
DEFAULT_AUDIT = ROOT / "data" / "team-shots" / "shadow" / "settlement-audit.json"
DEFAULT_OVERRIDES = ROOT / "data" / "settlement-overrides.csv"

BASE_URL = "https://www.football-data.co.uk"

LEAGUE_CODES = {
    "epl": "E0", "serie-a": "I1", "la-liga": "SP1",
    "bundesliga": "D1", "ligue-1": "F1",
}

SIGNAL_FIELDS = [
    "date", "fixture_date", "kickoff_iso", "league", "home_team", "away_team", "team", "venue",
    "bookmaker", "line", "side", "book_odds", "model_prob",
    "model_fair_odds", "edge", "stake_units", "actual_shots", "result",
    "pnl", "pnl_staked", "settled_at", "closing_odds", "clv", "logged_at", "policy_version",
]

DEFAULT_ODDS_ARCHIVE = ROOT / "data" / "team-shots" / "team-shots-odds-history.csv"

TEAM_ALIASES = {
    "brighton and hove albion": "brighton",
    "brighton hove albion": "brighton",
    "atalanta bc": "atalanta",
    "bologna fc": "bologna",
    "us lecce": "lecce",
    "tsg hoffenheim": "hoffenheim",
    "fc augsburg": "augsburg",
    "inter": "internazionale",
    "inter milan": "internazionale",
    "inter milano": "internazionale",
    "fc st pauli": "st pauli",
    "vfb stuttgart": "stuttgart",
    "vfl wolfsburg": "wolfsburg",
    "borussia m gladbach": "borussia monchengladbach",
    "m gladbach": "borussia monchengladbach",
    "bayer 04 leverkusen": "bayer leverkusen",
    "sc freiburg": "freiburg",
    "1 fc union berlin": "union berlin",
    "1 fc heidenheim": "heidenheim",
    "1 fc cologne": "1 koln",
    "1 fc koln": "1 koln",
    "fc koln": "1 koln",
    "wolverhampton wanderers": "wolverhampton",
    "tottenham hotspur": "tottenham",
    "liverpool fc": "liverpool",
    "fulham fc": "fulham",
    "burnley fc": "burnley",
    "valencia cf": "valencia",
    "elche cf": "elche",
    "deportivo alaves": "alaves",
    "real sociedad": "sociedad",
    "real sociedad san sebastian": "sociedad",
    "atletico madrid": "ath madrid",
    "athletic club": "ath bilbao",
    "athletic bilbao": "ath bilbao",
    "real betis": "betis",
    "real betis seville": "betis",
    "ca osasuna": "osasuna",
    "fc barcelona": "barcelona",
    "espanyol": "espanol",
    "espanyol barcelona": "espanol",
    "rc celta de vigo": "celta",
    "celta vigo": "celta",
    "rcd mallorca": "mallorca",
    "manchester city": "man city",
    "newcastle united": "newcastle",
    "newcastle utd": "newcastle",
    "olympique de marseille": "marseille",
    "olympique marseille": "marseille",
    "olympique lyonnais": "lyon",
    "ogc nice": "nice",
    "as roma": "roma",
    "juventus turin": "juventus",
    "pisa sc": "pisa",
    "girona fc": "girona",
    "bayern munchen": "bayern munich",
}

GENERIC_TEAM_TOKENS = {
    "fc", "cf", "afc", "sc", "ac", "us", "ud", "rc", "ssc", "calcio", "1907",
}


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


def _norm_team(text: str) -> str:
    base = _norm(text)
    simplified = " ".join(token for token in base.split() if token not in GENERIC_TEAM_TOKENS).strip()
    for candidate in (base, simplified):
        if candidate in TEAM_ALIASES:
            return TEAM_ALIASES[candidate]
    return simplified or base


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


def season_code(start_year: int) -> str:
    end = (start_year + 1) % 100
    return f"{start_year % 100:02d}{end:02d}"


def current_season_historical_path(historical_dir: Path, league: str) -> Path:
    now = datetime.now()
    start_year = now.year if now.month >= 8 else now.year - 1
    return historical_dir / f"{league}-{start_year}-{start_year + 1}.csv"


def fetch_current_season_results(league: str, historical_dir: Optional[Path] = None) -> Dict[str, dict]:
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

    if historical_dir is not None:
        historical_dir.mkdir(parents=True, exist_ok=True)
        current_season_historical_path(historical_dir, league).write_text(resp.text, encoding="utf-8")

    results: Dict[str, dict] = {}
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        d = _parse_date(row.get("Date", ""))
        if d is None:
            continue
        home = _norm_team(row.get("HomeTeam", ""))
        away = _norm_team(row.get("AwayTeam", ""))
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
                home = _norm_team(row.get("HomeTeam", ""))
                away = _norm_team(row.get("AwayTeam", ""))
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


def canonicalize_results_lookup(results_lookup: Dict[str, dict]) -> Dict[str, dict]:
    """
    Re-key result rows onto the same canonical team aliases the signals use.

    FotMob results come back keyed with plain normalized team names, while our
    signals and historical CSV loaders resolve aliases like "Bologna FC" ->
    "bologna" and "US Lecce" -> "lecce". Without a canonical pass the rows
    exist, but the settler never finds them.
    """
    canonical: Dict[str, dict] = {}
    for key, payload in results_lookup.items():
        parts = str(key).split("|", 2)
        if len(parts) != 3:
            canonical[key] = payload
            continue
        match_date, home, away = parts
        canonical[f"{match_date}|{_norm_team(home)}|{_norm_team(away)}"] = payload
    return canonical


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
            # Already settled — still try to fill missing closing_odds/clv if absent.
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
    parser.add_argument("--historical-dir", type=Path, default=DEFAULT_HISTORICAL)
    parser.add_argument("--odds-archive", type=Path, default=DEFAULT_ODDS_ARCHIVE)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT)
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
        print("  No pending signals to settle — running CLV backfill only.")
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
        emit_github_annotations(audit)
        if int(audit.get("exit_code_recommendation", 0)):
            raise SystemExit(1)
        return

    leagues_needed = set()
    target_dates_by_league: Dict[str, set[str]] = {}
    for s in pending:
        league = (s.get("league") or "").strip()
        if league:
            leagues_needed.add(league)
            sig_date = resolve_match_date(s, odds_index)
            if sig_date:
                base_date = _parse_date(sig_date)
                if base_date is not None:
                    for delta in (-1, 0, 1):
                        target_dates_by_league.setdefault(league, set()).add((base_date + timedelta(days=delta)).isoformat())
                else:
                    target_dates_by_league.setdefault(league, set()).add(sig_date)
    print(f"  Leagues to fetch: {', '.join(sorted(leagues_needed))}")

    all_results: Dict[str, dict] = canonicalize_results_lookup(load_historical_results(args.historical_dir))
    print(f"  Historical results loaded: {len(all_results)}")

    source_freshness: Dict[str, dict] = {}
    for league in leagues_needed:
        fresh = canonicalize_results_lookup(fetch_current_season_results(league, args.historical_dir))
        latest_available = max((key.split("|", 1)[0] for key in fresh.keys()), default="none")
        print(f"  [live] {league}: {len(fresh)} matches fetched (latest {latest_available})")
        all_results.update(fresh)
        fotmob = canonicalize_results_lookup(fetch_fotmob_recent_results(league, target_dates_by_league.get(league, set())))
        if fotmob:
            latest_fotmob = max((key.split("|", 1)[0] for key in fotmob.keys()), default="none")
            print(f"  [fotmob] {league}: {len(fotmob)} matches fetched (latest {latest_fotmob})")
            all_results.update(fotmob)
        else:
            latest_fotmob = None
        lag_days = None
        if latest_available and latest_available != "none":
            try:
                lag_days = (datetime.now(timezone.utc).date() - date.fromisoformat(latest_available)).days
            except ValueError:
                lag_days = None
        source_freshness[league] = {
            "football_data_latest": None if latest_available == "none" else latest_available,
            "lag_days": lag_days,
            "football_data_count": len(fresh),
            "fotmob_count": len(fotmob),
            "fotmob_latest": latest_fotmob if latest_fotmob != "none" else None,
        }

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
    emit_github_annotations(audit)
    if int(audit.get("exit_code_recommendation", 0)):
        raise SystemExit(1)


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
