#!/usr/bin/env python3
"""
Settle matchday shortlist value-bets against actual corner results.

Reads all value-bets-{date}.csv files from data/shortlist/, matches each bet
against actual corner results in data/corners-ou/historical/, and writes:

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
import io
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import sys
from typing import Dict, List, Optional
import re
import unicodedata

import requests

from fotmob_match_stats import fetch_fotmob_recent_results

ROOT = Path(__file__).resolve().parent.parent
SHORTLIST_DIR   = ROOT / "data" / "shortlist"
HISTORICAL_DIR  = ROOT / "data" / "corners-ou" / "historical"
LEGACY_HISTORICAL_DIR = ROOT / "data" / "team-shots" / "historical"
SETTLED_PATH    = ROOT / "data" / "shortlist" / "settled-pnl.csv"
PNL_REPORT_PATH = ROOT / "data" / "shortlist" / "corners-live-pnl.txt"
PINNACLE_ODDS_PATH = ROOT / "data" / "corners-ou" / "pinnacle-corners-odds.csv"
BASE_URL = "https://www.football-data.co.uk"
LEAGUE_CODES = {
    "epl": "E0",
    "serie-a": "I1",
    "la-liga": "SP1",
    "bundesliga": "D1",
    "ligue-1": "F1",
}
DEFAULT_POLICY_VERSION = "V2"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── Helpers ───────────────────────────────────────────────────────────────────

_TEAM_ALIASES: Dict[str, str] = {
    # Our model name → Pinnacle name (post-normalization, lowercase, ASCII)
    "brighton and hove albion": "brighton",
    "brighton hove albion": "brighton",
    "atalanta bc": "atalanta",
    "bologna fc": "bologna",
    "us lecce": "lecce",
    "tsg hoffenheim": "hoffenheim",
    "fc augsburg": "augsburg",
    "inter": "internazionale",
    "inter milan": "internazionale",
    "fc st pauli": "st pauli",
    "vfb stuttgart": "stuttgart",
    "fsv mainz 05": "mainz",
    "mainz 05": "mainz",
    "borussia m gladbach": "borussia monchengladbach",
    "m gladbach": "borussia monchengladbach",
    "bayer 04 leverkusen": "bayer leverkusen",
    "sc freiburg": "freiburg",
    "1 fc union berlin": "union berlin",
    "1 fc cologne": "fc koln",
    "wolverhampton wanderers": "wolverhampton",
    "tottenham hotspur": "tottenham",
    "liverpool fc": "liverpool",
    "fulham fc": "fulham",
    "burnley fc": "burnley",
    "valencia cf": "valencia",
    "elche cf": "elche",
    "real sociedad": "sociedad",
    "real sociedad san sebastian": "sociedad",
    "deportivo alaves": "alaves",
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
    "bayern munchen": "bayern munich",
    "as roma": "roma",
    "pisa sc": "pisa",
    "girona fc": "girona",
}

_GENERIC_TEAM_TOKENS = {
    "fc", "cf", "afc", "sc", "ac", "us", "ud", "rc", "ssc", "calcio", "1907",
}


def _norm_team(text: str) -> str:
    """Normalize a team name, stripping Pinnacle's '(Corners)' suffix."""
    text = re.sub(r"\s*\(corners\)\s*$", "", (text or "").strip(), flags=re.IGNORECASE)
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    base = re.sub(r"[^a-z0-9]+", " ", text).strip()
    simplified = " ".join(token for token in base.split() if token not in _GENERIC_TEAM_TOKENS).strip()
    for candidate in (base, simplified):
        if candidate in _TEAM_ALIASES:
            return _TEAM_ALIASES[candidate]
    return simplified or base


def load_pinnacle_odds_index() -> Dict[str, List[dict]]:
    """
    Build an index from the Pinnacle corners odds archive.

    Primary key:   match_date|home_norm|away_norm|line|side
    Secondary key: home_norm|away_norm|line|side  (dateless fallback for bets
                   where our match_date is the shortlist run date, not game date)
    Value: list of {captured_at, kickoff_iso, odds} sorted ascending by captured_at.
    """
    index: Dict[str, List[dict]] = {}
    if not PINNACLE_ODDS_PATH.exists():
        return index
    with open(PINNACLE_ODDS_PATH, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            home = _norm_team(row.get("home_team", ""))
            away = _norm_team(row.get("away_team", ""))
            match_date = (row.get("match_date") or "").strip()[:10]
            line = (row.get("line") or "").strip()
            side = (row.get("side") or "").strip().lower()
            if not (home and away and match_date and line and side):
                continue
            entry = {
                "captured_at": (row.get("captured_at") or "").strip(),
                "kickoff_iso": (row.get("kickoff_iso") or "").strip(),
                "odds": float(row.get("odds_decimal") or 0),
            }
            # Date-keyed (precise)
            index.setdefault(f"{match_date}|{home}|{away}|{line}|{side}", []).append(entry)
            # Dateless (fallback for bets logged with wrong match_date)
            index.setdefault(f"__any__|{home}|{away}|{line}|{side}", []).append(entry)
    for entries in index.values():
        entries.sort(key=lambda e: e["captured_at"])
    return index


def find_closing_odds(
    match: str,
    match_date_str: str,
    line: str,
    side: str,
    kick_off_raw: str,
    odds_index: Dict[str, List[dict]],
) -> Optional[float]:
    """
    Return the last Pinnacle odds captured on/before kickoff for this bet.
    Falls back to match_date 23:59:59 if kickoff_iso is unavailable.
    """
    parts = match.split(" vs ", 1)
    if len(parts) != 2:
        return None
    home = _norm_team(parts[0])
    away = _norm_team(parts[1])

    # Try date-keyed lookup first (exact match_date from the bet file)
    entries = odds_index.get(f"{match_date_str[:10]}|{home}|{away}|{line}|{side}")

    # Fallback: our match_date may be the shortlist run date, not the actual
    # game date (happens when kick_off wasn't written to the CSV). Use the
    # dateless index so we can still find the correct Pinnacle entries.
    if not entries:
        entries = odds_index.get(f"__any__|{home}|{away}|{line}|{side}")
    if not entries:
        return None

    # Determine cutoff: use kickoff_iso from the archive rows (most reliable),
    # then the kick_off field from the bet, then date-end fallback.
    kickoff_candidates = [e["kickoff_iso"] for e in entries if e.get("kickoff_iso")]
    if kickoff_candidates:
        cutoff = max(kickoff_candidates)
    elif kick_off_raw:
        cutoff = kick_off_raw
    else:
        cutoff = f"{match_date_str[:10]}T23:59:59Z"

    candidates = [e for e in entries if e["captured_at"] <= cutoff and e["odds"] > 0]
    if not candidates:
        return None
    return candidates[-1]["odds"]  # already sorted ascending


def find_match_kickoff(match: str, odds_index: Dict[str, List[dict]]) -> Optional[str]:
    """
    Resolve the fixture kickoff from the Pinnacle archive for bets that were
    logged before kick_off was written into the shortlist CSV.
    """
    parts = match.split(" vs ", 1)
    if len(parts) != 2:
        return None
    home = _norm_team(parts[0])
    away = _norm_team(parts[1])
    prefix = f"__any__|{home}|{away}|"
    kickoff_candidates: List[str] = []
    for key, entries in odds_index.items():
        if not key.startswith(prefix):
            continue
        kickoff_candidates.extend(
            entry["kickoff_iso"] for entry in entries if entry.get("kickoff_iso")
        )
    if not kickoff_candidates:
        return None
    return max(kickoff_candidates)


def _norm(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    base = re.sub(r"[^a-z0-9]+", " ", text).strip()
    simplified = " ".join(token for token in base.split() if token not in _GENERIC_TEAM_TOKENS).strip()
    for candidate in (base, simplified):
        if candidate in _TEAM_ALIASES:
            return _TEAM_ALIASES[candidate]
    return simplified or base


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


def _pf(val: object, default: float = 0.0) -> float:
    try:
        text = str(val or "").strip()
        return float(text or default)
    except (TypeError, ValueError):
        return default


def _fixture_date_for_row(row: dict) -> str:
    return (
        ((row.get("kick_off") or "").strip()[:10])
        or ((row.get("match_date") or "").strip()[:10])
        or ((row.get("file_date") or "").strip()[:10])
    )


def _policy_version(row: dict) -> str:
    return (row.get("policy_version") or "").strip() or DEFAULT_POLICY_VERSION


def _row_identity(row: dict) -> str:
    """
    Unique identity for a single logged bet.

    We include file_date, league, fixture_date, match, line, side, AND bookmaker so that:
      - Multiple bets on the same fixture (different lines or sides) are all preserved.
      - The same line/side at different bookmakers remains distinct if that ever happens.
      - The same bet re-appearing across consecutive shortlist runs (same file_date,
        same line/side) deduplicates correctly.
      - Old fixture-level deduplication that discarded earlier bets is gone.
    """
    match_norm = (row.get("match") or "").strip().lower()
    league_norm = (row.get("league") or "").strip().lower()
    fixture_date = _fixture_date_for_row(row)
    file_date = (row.get("file_date") or "").strip()[:10]
    line_norm = str(row.get("line") or "").strip()
    side_norm = (row.get("side") or "").strip().lower()
    bookmaker_norm = (row.get("bookmaker") or "").strip().lower()
    return f"{file_date}|{league_norm}|{fixture_date}|{match_norm}|{line_norm}|{side_norm}|{bookmaker_norm}"


def _row_identity_without_file_date(row: dict) -> str:
    match_norm = (row.get("match") or "").strip().lower()
    league_norm = (row.get("league") or "").strip().lower()
    fixture_date = _fixture_date_for_row(row)
    line_norm = str(row.get("line") or "").strip()
    side_norm = (row.get("side") or "").strip().lower()
    bookmaker_norm = (row.get("bookmaker") or "").strip().lower()
    return f"{league_norm}|{fixture_date}|{match_norm}|{line_norm}|{side_norm}|{bookmaker_norm}"


def resolve_historical_dir() -> Path:
    if HISTORICAL_DIR.exists():
        return HISTORICAL_DIR
    if LEGACY_HISTORICAL_DIR.exists():
        print(f"[warn] corners historical dir missing at {HISTORICAL_DIR}; using legacy {LEGACY_HISTORICAL_DIR}")
        return LEGACY_HISTORICAL_DIR
    return HISTORICAL_DIR


def season_code(start_year: int) -> str:
    end = (start_year + 1) % 100
    return f"{start_year % 100:02d}{end:02d}"


# ── Load actual results ────────────────────────────────────────────────────────

def load_actual_results() -> Dict[str, dict]:
    """
    Load historical corner results.
    Key: "{date}|{norm(home)}|{norm(away)}"
    """
    results: Dict[str, dict] = {}
    historical_dir = resolve_historical_dir()
    for csv_path in sorted(historical_dir.glob("*.csv")):
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


def canonicalize_actual_results(results_lookup: Dict[str, dict]) -> Dict[str, dict]:
    """
    Re-key result rows onto the same canonical aliases the shortlist uses.

    Football-Data and FotMob both key matches with plain normalized names.
    Our shortlist rows use alias-aware normalization (e.g. "SC Freiburg" ->
    "freiburg", "Inter Milan" -> "internazionale"). Without this pass the
    result exists, but the settlement lookup misses it.
    """
    canonical: Dict[str, dict] = {}
    for key, payload in results_lookup.items():
        parts = str(key).split("|", 2)
        if len(parts) != 3:
            canonical[key] = payload
            continue
        match_date, home, away = parts
        canonical[f"{match_date}|{_norm(home)}|{_norm(away)}"] = payload
    return canonical


def _rerun_fixture_identity(row: dict) -> str:
    """
    Identity for replacing stale same-day shortlist rows on rerun.

    If a date file is regenerated for the same fixture, the latest file should
    supersede older same-day rows even if the line/side changed.
    """
    match_norm = (row.get("match") or "").strip().lower()
    league_norm = (row.get("league") or "").strip().lower()
    fixture_date = _fixture_date_for_row(row)
    file_date = (row.get("file_date") or "").strip()[:10]
    return f"{file_date}|{league_norm}|{fixture_date}|{match_norm}"


def fetch_current_season_results(league: str) -> Dict[str, dict]:
    code = LEAGUE_CODES.get(league)
    if not code:
        return {}

    now = datetime.now()
    start_year = now.year if now.month >= 8 else now.year - 1
    season = season_code(start_year)
    url = f"{BASE_URL}/mmz4281/{season}/{code}.csv"

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
    actual = canonicalize_actual_results(load_actual_results())
    print(f"Loaded {len(actual)} historical results with corners")
    odds_index = load_pinnacle_odds_index()
    print(f"Loaded {len(odds_index)} Pinnacle odds series")

    bet_files = sorted(
        path for path in SHORTLIST_DIR.glob("value-bets-*.csv")
        if path.name != "value-bets-latest.csv"
    )
    if target_date:
        bet_files = [f for f in bet_files if target_date in f.name]

    if not bet_files:
        print("No value-bet files found.")
        return []

    existing_source_rows: List[dict] = []
    if SETTLED_PATH.exists():
        with open(SETTLED_PATH, "r", encoding="utf-8", newline="") as fh:
            existing_source_rows = list(csv.DictReader(fh))
        existing_source_rows = [
            row for row in existing_source_rows
            if (row.get("file_date") or "").strip().lower() != "latest"
        ]

    current_source_rows: List[dict] = []
    for path in bet_files:
        file_date = path.name.replace("value-bets-", "").replace(".csv", "")[:10]
        with open(path, "r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row = dict(row)
                if not (row.get("file_date") or "").strip():
                    row["file_date"] = file_date
                if not (row.get("kick_off") or "").strip():
                    row["kick_off"] = find_match_kickoff((row.get("match") or "").strip(), odds_index) or ""
                current_source_rows.append(row)

    rows_needing_results = current_source_rows + [
        row for row in existing_source_rows if (row.get("settled") or "").strip() == "pending"
    ]

    target_dates_by_league: Dict[str, set[str]] = defaultdict(set)
    leagues_needed = sorted({
        (row.get("league") or "").strip()
        for row in rows_needing_results
        if (row.get("league") or "").strip()
    })
    for row in rows_needing_results:
        league = (row.get("league") or "").strip()
        if not league:
            continue
        match_str = (row.get("match") or "").strip()
        file_date_str = (row.get("file_date") or "").strip()[:10]
        kick_off_raw = (row.get("kick_off") or "").strip()
        if not kick_off_raw and match_str:
            kick_off_raw = find_match_kickoff(match_str, odds_index) or ""
        match_date = _parse_date(kick_off_raw) or _parse_date(file_date_str)
        if match_date is not None:
            # FotMob date buckets can drift by a day around ingestion/timezone edges,
            # so fetch a small window around the target fixture date instead of only
            # the exact date. The settlement lookup remains strict on the final key.
            for delta in (-1, 0, 1):
                target_dates_by_league[league].add((match_date + timedelta(days=delta)).isoformat())

    for league in leagues_needed:
        fresh = canonicalize_actual_results(fetch_current_season_results(league))
        if fresh:
            latest_available = max((key.split("|", 1)[0] for key in fresh.keys()), default="none")
            print(f"  [live] {league}: {len(fresh)} matches fetched (latest {latest_available})")
            actual.update(fresh)
        fotmob = canonicalize_actual_results(fetch_fotmob_recent_results(league, target_dates_by_league.get(league, set())))
        if fotmob:
            latest_fotmob = max((key.split("|", 1)[0] for key in fotmob.keys()), default="none")
            print(f"  [fotmob] {league}: {len(fotmob)} matches fetched (latest {latest_fotmob})")
            actual.update(fotmob)

    current_file_dates_by_partial_identity: Dict[str, set[str]] = defaultdict(set)
    for row in current_source_rows:
        file_date = (row.get("file_date") or "").strip()[:10]
        if not file_date:
            continue
        current_file_dates_by_partial_identity[_row_identity_without_file_date(row)].add(file_date)
    for row in existing_source_rows:
        inferred_file_dates = current_file_dates_by_partial_identity.get(
            _row_identity_without_file_date(row),
            set(),
        )
        if len(inferred_file_dates) != 1:
            continue
        inferred_file_date = next(iter(inferred_file_dates))
        current_file_date = (row.get("file_date") or "").strip()[:10]
        if not current_file_date or current_file_date == "latest" or current_file_date != inferred_file_date:
            row["file_date"] = inferred_file_date

    current_keys = {_row_identity(row) for row in current_source_rows}
    current_rerun_keys = {_rerun_fixture_identity(row) for row in current_source_rows}
    source_rows = current_source_rows + [
        row
        for row in existing_source_rows
        if _row_identity(row) not in current_keys
        and _rerun_fixture_identity(row) not in current_rerun_keys
    ]

    rows: List[dict] = []
    for bet in source_rows:
        file_date_str = (bet.get("file_date") or "").strip() or _fixture_date_for_row(bet)
        match_str = bet.get("match", "")
        parts = match_str.split(" vs ")
        if len(parts) != 2:
            continue
        home_n = _norm(parts[0])
        away_n = _norm(parts[1])

        # Use kick_off date if present. Older shortlist files may not have
        # it yet, so backfill from the Pinnacle archive before falling
        # back to the shortlist run date.
        kick_off_raw = (bet.get("kick_off") or "").strip()
        if not kick_off_raw:
            kick_off_raw = find_match_kickoff(match_str, odds_index) or ""
        match_date = _parse_date(kick_off_raw) or _parse_date(file_date_str)

        settled = dict(bet)
        settled["file_date"] = file_date_str
        settled["kick_off"] = kick_off_raw

        if match_date is None:
            settled["match_date"] = ""
            settled["policy_version"] = _policy_version(bet)
            settled["settled"] = "pending"
            settled["actual_total_corners"] = ""
            settled["won"] = ""
            settled["pnl_units"] = ""
            settled["pnl_staked"] = ""
            rows.append(settled)
            continue

        settled["match_date"] = match_date.isoformat()
        settled["policy_version"] = _policy_version(bet)

        # Try exact date, then +/- 1 day (timezone/schedule fuzziness)
        result = None
        for delta in (0, 1, -1):
            check_date = match_date + timedelta(days=delta)
            key = f"{check_date.isoformat()}|{home_n}|{away_n}"
            result = actual.get(key)
            if result:
                break

        line_val = float(bet.get("line", 0))
        side = bet.get("side", "")
        bookie_odds = _pf(bet.get("bookie_odds", "0"))
        stake = _pf(bet.get("stake", "1"), 1.0)
        line_str = str(bet.get("line", "")).strip()

        closing = find_closing_odds(
            match=match_str,
            match_date_str=match_date.isoformat(),
            line=line_str,
            side=side,
            kick_off_raw=kick_off_raw,
            odds_index=odds_index,
        )
        if closing and closing > 0 and bookie_odds > 0:
            settled["closing_odds"] = round(closing, 4)
            settled["clv"] = round(bookie_odds / closing - 1, 4)
        else:
            settled["closing_odds"] = ""
            settled["clv"] = ""

        if result:
            total_corners = result["total_corners"]
            # Push/void detection: integer lines (8.0, 9.0, 10.0) push when the result
            # lands exactly on the line. Half-point lines (8.5, 9.5) never push.
            is_integer_line = (line_val == round(line_val))
            if is_integer_line and total_corners == round(line_val):
                # Push: stake returned, P&L is zero.
                outcome = "push"
                pnl_units = 0.0
                pnl_staked = 0.0
            elif side == "over":
                won_bool = total_corners > line_val
                outcome = "yes" if won_bool else "no"
                pnl_units = round((bookie_odds - 1.0) if won_bool else -1.0, 3)
                pnl_staked = round(pnl_units * stake, 3)
            else:  # under — strict less-than for both integer and half-point lines
                won_bool = total_corners < line_val
                outcome = "yes" if won_bool else "no"
                pnl_units = round((bookie_odds - 1.0) if won_bool else -1.0, 3)
                pnl_staked = round(pnl_units * stake, 3)

            now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            # Preserve settled_at from an existing settled row; only set it the first time.
            settled["settled_at"] = bet.get("settled_at") or now_iso
            settled["settled"] = "yes"
            settled["actual_total_corners"] = total_corners
            settled["won"] = outcome
            settled["pnl_units"] = pnl_units
            settled["pnl_staked"] = pnl_staked
        else:
            settled["settled_at"] = bet.get("settled_at") or ""
            settled["settled"] = "pending"
            settled["actual_total_corners"] = ""
            settled["won"] = ""
            settled["pnl_units"] = ""
            settled["pnl_staked"] = ""

        rows.append(settled)

    # Deduplicate only on the full bet identity
    # (file_date|league|fixture_date|match|line|side|bookmaker).
    # Multiple bets on the same fixture (different lines, different sides, or generated on
    # different days) are ALL preserved. No fixture-level collapse.
    seen: dict[str, dict] = {}
    for r in rows:
        key = _row_identity(r)
        if key not in seen:
            seen[key] = r
        # If the same full identity appears twice (e.g. the shortlist file and the existing
        # settled CSV), the one already in `seen` wins (current shortlist file was added first
        # in source_rows, so it takes precedence over the cached settled row).
    rows = list(seen.values())

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
    pushed = [b for b in bets if b.get("won") == "push"]
    n      = len(won) + len(lost) + len(pushed)
    if n == 0:
        lines.append(f"{p}{label}: no settled bets")
        return
    pnl    = sum(_pf(b.get("pnl_staked", "")) for b in won + lost + pushed)
    staked = sum(_pf(b.get("stake", "1"), 1.0) for b in won + lost + pushed)
    roi    = pnl / staked * 100 if staked else 0.0
    push_str = f"/P{len(pushed)}" if pushed else ""
    lines.append(
        f"{p}{label}: {n} settled  W{len(won)}/L{len(lost)}{push_str}  "
        f"({len(won)/n*100:.0f}%)  P&L {pnl:+.2f}u  ROI {roi:+.1f}%"
    )


def build_report(rows: List[dict]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
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

    # Sort settled by settled_at (when the bet was graded), falling back to match_date.
    # This ensures "recent" is truly recent even if the settler catches up late.
    settled_sorted = sorted(
        settled,
        key=lambda r: r.get("settled_at") or r.get("match_date", ""),
    )

    # Running P&L
    running = 0.0
    peak    = 0.0
    max_dd  = 0.0
    for b in settled_sorted:
        running += _pf(b.get("pnl_staked", ""))
        if running > peak:
            peak = running
        max_dd = max(max_dd, peak - running)

    won_all    = [b for b in settled if b.get("won") == "yes"]
    lost_all   = [b for b in settled if b.get("won") == "no"]
    pushed_all = [b for b in settled if b.get("won") == "push"]
    total_staked = sum(_pf(b.get("stake", "1"), 1.0) for b in settled)
    total_pnl    = sum(_pf(b.get("pnl_staked", "")) for b in settled)
    roi = total_pnl / total_staked * 100 if total_staked else 0.0
    n_decisive = len(won_all) + len(lost_all)  # exclude pushes from win-rate denominator

    out.append("  ── OVERALL ──────────────────────────────────────────────────")
    push_str = f"/P{len(pushed_all)}" if pushed_all else ""
    out.append(f"  Settled: {len(settled)}  W{len(won_all)}/L{len(lost_all)}{push_str}  "
               f"({len(won_all)/n_decisive*100:.0f}% ex-push)" if n_decisive else
               f"  Settled: {len(settled)}  (all pushes)")
    out.append(f"  Total staked : {total_staked:.1f}u")
    out.append(f"  P&L          : {total_pnl:+.2f}u")
    out.append(f"  ROI          : {roi:+.1f}%")
    out.append(f"  Max drawdown : {max_dd:.1f}u")

    clv_vals = [_pf(b.get("clv", ""), float("nan")) for b in settled if b.get("clv")]
    clv_vals = [v for v in clv_vals if v == v]  # drop NaN
    if clv_vals:
        avg_clv = sum(clv_vals) / len(clv_vals) * 100
        out.append(f"  Avg CLV      : {avg_clv:+.1f}%  (n={len(clv_vals)}, vs Pinnacle close)")
    out.append("")

    out.append("  ── BY LEAGUE ────────────────────────────────────────────────")
    leagues = sorted(set(b.get("league", "?") for b in settled))
    for lg in leagues:
        _section(out, lg, [b for b in settled if b.get("league") == lg])
    out.append("")

    out.append("  ── BY LINE ──────────────────────────────────────────────────")
    all_lines = sorted(set(str(b.get("line", "")) for b in settled), key=lambda x: float(x) if x else 0)
    for line in all_lines:
        subset = [b for b in settled if str(b.get("line", "")) == line]
        if subset:
            _section(out, f"Line {line}", subset)
    out.append("")

    out.append("  ── BY SIDE ──────────────────────────────────────────────────")
    for side in ["over", "under"]:
        _section(out, side.capitalize(), [b for b in settled if b.get("side") == side])
    out.append("")

    versions = sorted({_policy_version(b) for b in settled})
    if versions:
        out.append("  By policy version")
        for version in versions:
            _section(out, version, [b for b in settled if _policy_version(b) == version])
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
        won_str = "W" if b.get("won") == "yes" else ("P" if b.get("won") == "push" else "L")
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
    "lambda_h", "lambda_a", "lambda_h_recent", "lambda_a_recent",
    "divergence", "consensus", "policy_version",
    "settled", "settled_at", "actual_total_corners", "won", "pnl_units", "pnl_staked",
    "closing_odds", "clv",
]


def write_settled_csv(rows: List[dict]) -> None:
    if not rows:
        return
    # running P&L column — sorted by settled_at (when graded), then match_date as fallback.
    # Sorting by settled_at ensures "recent settled" in the monitor reflects actual recency,
    # not fixture date, which can be misleading when the settler catches up late.
    settled_rows = sorted(
        [r for r in rows if r.get("settled") == "yes"],
        key=lambda r: r.get("settled_at") or r.get("match_date", ""),
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
