#!/usr/bin/env python3
"""
Goalscorer odds archive importer.

Canonicalizes anytime-goalscorer odds captures into one append-only CSV that we
can populate manually now and from automated scrapers later.

Expected input columns (flexible aliases supported):
  captured_at, match_date, bookmaker, competition, market,
  home_team, away_team, player_name, player_team, odds_decimal,
  event_id, kickoff_at, minutes_to_kickoff, snapshot_kind, source, notes

Example:
  python scripts/goalscorer-odds-archive.py --input data/goalscorer/goalscorer-odds-template.csv
  python scripts/goalscorer-odds-archive.py --input data/goalscorer/manual/*.csv --supabase
"""

from __future__ import annotations

import argparse
import csv
import glob
import html
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


DEFAULT_ARCHIVE = "data/goalscorer/goalscorer-odds-history.csv"
DEFAULT_MARKET = "ATGS"
DEFAULT_COMPETITION = "Serie A"


def load_env() -> None:
    root = Path(__file__).resolve().parent.parent
    for name in (".env.local", "env.local"):
        path = root / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _expand_paths(paths: Iterable[str]) -> List[str]:
    expanded: List[str] = []
    for path in paths:
        if "*" in path or "?" in path:
            matches = glob.glob(path)
            if not matches:
                print(f"  Warning: glob '{path}' matched no files")
            expanded.extend(matches)
        else:
            expanded.append(path)
    return expanded


def _parse_date(value: str) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_datetime(value: str) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    for fmt in (
        None,
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            if fmt is None:
                parsed = datetime.fromisoformat(text)
            else:
                parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return None


def _parse_float(value: str) -> Optional[float]:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _norm_text(value: str) -> str:
    normalized = html.unescape((value or "").strip().lower())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", cleaned).strip()


def _load_rows(paths: List[str]) -> List[dict]:
    rows: List[dict] = []
    for path in _expand_paths(paths):
        if not os.path.exists(path):
            print(f"  Warning: {path} not found")
            continue
        with open(path, "r", encoding="utf-8-sig") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(handle, dialect=dialect)
            loaded = list(reader)
            print(f"  Loaded {len(loaded):,} rows from {os.path.basename(path)}")
            rows.extend({(key or "").strip().lower(): value for key, value in row.items()} for row in loaded)
    return rows


def _find_key(row: dict, candidates: Iterable[str]) -> str:
    for candidate in candidates:
        for key in row.keys():
            if key == candidate.lower():
                return key
    return ""


def canonicalize_rows(raw_rows: List[dict], imported_at: str) -> tuple[List[dict], dict]:
    canonical: List[dict] = []
    stats = {
        "input_rows": len(raw_rows),
        "kept_rows": 0,
        "missing_player": 0,
        "missing_match": 0,
        "missing_odds": 0,
        "defaulted_capture_time": 0,
    }

    for row in raw_rows:
        captured_at_key = _find_key(row, ["captured_at", "capture_time", "timestamp"])
        match_date_key = _find_key(row, ["match_date", "date"])
        bookmaker_key = _find_key(row, ["bookmaker", "sportsbook"])
        competition_key = _find_key(row, ["competition", "league"])
        market_key = _find_key(row, ["market"])
        home_team_key = _find_key(row, ["home_team"])
        away_team_key = _find_key(row, ["away_team"])
        player_name_key = _find_key(row, ["player_name", "selection", "runner"])
        player_team_key = _find_key(row, ["player_team", "team"])
        odds_key = _find_key(row, ["odds_decimal", "decimal_odds", "odds"])
        event_id_key = _find_key(row, ["event_id", "eventid", "fixture_id", "match_id"])
        kickoff_at_key = _find_key(row, ["kickoff_at", "commence_time", "start_time", "match_time"])
        minutes_to_kickoff_key = _find_key(row, ["minutes_to_kickoff", "mins_to_kickoff", "lead_minutes"])
        snapshot_kind_key = _find_key(row, ["snapshot_kind", "snapshot_label", "capture_kind"])
        source_key = _find_key(row, ["source"])
        notes_key = _find_key(row, ["notes", "note"])

        player_name = (row.get(player_name_key, "") or "").strip()
        home_team = (row.get(home_team_key, "") or "").strip()
        away_team = (row.get(away_team_key, "") or "").strip()
        player_team = (row.get(player_team_key, "") or "").strip()
        match_date = _parse_date(row.get(match_date_key, "") or "")
        odds_decimal = _parse_float(row.get(odds_key, "") or "")

        if not player_name:
            stats["missing_player"] += 1
            continue
        if not home_team or not away_team or not match_date:
            stats["missing_match"] += 1
            continue
        if odds_decimal is None or odds_decimal <= 1.0:
            stats["missing_odds"] += 1
            continue

        captured_at = _parse_datetime(row.get(captured_at_key, "") or "")
        if not captured_at:
            captured_at = imported_at
            stats["defaulted_capture_time"] += 1

        kickoff_at = _parse_datetime(row.get(kickoff_at_key, "") or "")
        minutes_to_kickoff = _parse_float(row.get(minutes_to_kickoff_key, "") or "")
        if minutes_to_kickoff is None and kickoff_at:
            try:
                captured_dt = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
                kickoff_dt = datetime.fromisoformat(kickoff_at.replace("Z", "+00:00"))
                minutes_to_kickoff = (kickoff_dt - captured_dt).total_seconds() / 60.0
            except ValueError:
                minutes_to_kickoff = None

        canonical.append(
            {
                "capture_date": captured_at[:10],
                "captured_at": captured_at,
                "match_date": match_date,
                "event_id": (row.get(event_id_key, "") or "").strip(),
                "kickoff_at": kickoff_at or "",
                "minutes_to_kickoff": f"{minutes_to_kickoff:.1f}" if minutes_to_kickoff is not None else "",
                "snapshot_kind": (row.get(snapshot_kind_key, "") or "").strip(),
                "bookmaker": (row.get(bookmaker_key, "") or "").strip() or "Unknown",
                "competition": (row.get(competition_key, "") or "").strip() or DEFAULT_COMPETITION,
                "market": (row.get(market_key, "") or "").strip().upper() or DEFAULT_MARKET,
                "home_team": home_team,
                "away_team": away_team,
                "player_name": player_name,
                "player_team": player_team,
                "odds_decimal": f"{odds_decimal:.4f}",
                "implied_prob": f"{1.0 / odds_decimal:.6f}",
                "source": (row.get(source_key, "") or "").strip() or "manual",
                "notes": (row.get(notes_key, "") or "").strip(),
            }
        )
        stats["kept_rows"] += 1

    return canonical, stats


def _dedupe_key(row: dict) -> tuple[str, ...]:
    return (
        row["captured_at"],
        _norm_text(row["bookmaker"]),
        _norm_text(row["competition"]),
        _norm_text(row["market"]),
        row["match_date"],
        _norm_text(row["home_team"]),
        _norm_text(row["away_team"]),
        _norm_text(row["player_name"]),
    )


def load_existing_archive(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_archive(path: str, rows: List[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "capture_date",
        "captured_at",
        "match_date",
        "event_id",
        "kickoff_at",
        "minutes_to_kickoff",
        "snapshot_kind",
        "bookmaker",
        "competition",
        "market",
        "home_team",
        "away_team",
        "player_name",
        "player_team",
        "odds_decimal",
        "implied_prob",
        "source",
        "notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def upload_supabase(rows: List[dict]) -> None:
    import requests

    load_env()
    base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not base or not key:
        raise SystemExit("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to upload odds history.")

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    conflict_cols = "captured_at,bookmaker,competition,market,match_date,home_team,away_team,player_name"
    url = f"{base}/rest/v1/goalscorer_odds_history?on_conflict={conflict_cols}"
    response = requests.post(url, headers=headers, json=rows, timeout=30)
    if not response.ok:
        raise SystemExit(f"Supabase upload failed: {response.status_code} {response.text[:300]}")
    print(f"  Uploaded {len(rows):,} rows to goalscorer_odds_history")


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive anytime-goalscorer odds into a canonical CSV")
    parser.add_argument("--input", nargs="+", required=True, help="Manual or scraped CSV files")
    parser.add_argument("--archive", default=DEFAULT_ARCHIVE, help="Canonical archive CSV path")
    parser.add_argument("--supabase", action="store_true", help="Upload imported rows to Supabase")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer Odds Archive")
    print("=" * 64)

    imported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    raw_rows = _load_rows(args.input)
    if not raw_rows:
        print("  No input rows loaded.")
        raise SystemExit(1)

    canonical_rows, stats = canonicalize_rows(raw_rows, imported_at)
    print(f"  Input rows:          {stats['input_rows']:,}")
    print(f"  Canonical rows kept: {stats['kept_rows']:,}")
    print(f"  Missing player:      {stats['missing_player']:,}")
    print(f"  Missing match:       {stats['missing_match']:,}")
    print(f"  Missing odds:        {stats['missing_odds']:,}")
    print(f"  Defaulted capture time: {stats['defaulted_capture_time']:,}")

    existing_rows = load_existing_archive(args.archive)
    merged: Dict[tuple[str, ...], dict] = {_dedupe_key(row): row for row in existing_rows}
    before = len(merged)
    for row in canonical_rows:
        merged[_dedupe_key(row)] = row
    archive_rows = sorted(merged.values(), key=lambda row: (row["captured_at"], row["bookmaker"], row["player_name"]))
    added = len(archive_rows) - before

    write_archive(args.archive, archive_rows)
    print(f"  Archive rows:        {len(archive_rows):,}")
    print(f"  New unique rows:     {added:,}")
    print(f"  Saved: {args.archive}")

    if args.supabase and canonical_rows:
        upload_supabase(canonical_rows)

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
