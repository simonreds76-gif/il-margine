#!/usr/bin/env python3
"""
Download historical match data from Football-Data.co.uk.

Fetches CSV files containing match results, shots (HS/AS/HST/AST),
corners, fouls, and bookmaker odds for the major European leagues.

Usage:
  python scripts/footballdata-download-historical.py
  python scripts/footballdata-download-historical.py --leagues epl serie-a --seasons 2020 2021 2022 2023 2024 2025
  python scripts/footballdata-download-historical.py --all-seasons
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "data" / "team-shots" / "historical"

BASE_URL = "https://www.football-data.co.uk"

LEAGUE_CODES: Dict[str, Dict] = {
    "epl": {"code": "E0", "country": "england", "label": "Premier League"},
    "championship": {"code": "E1", "country": "england", "label": "Championship"},
    "serie-a": {"code": "I1", "country": "italy", "label": "Serie A"},
    "la-liga": {"code": "SP1", "country": "spain", "label": "La Liga"},
    "bundesliga": {"code": "D1", "country": "germany", "label": "Bundesliga"},
    "ligue-1": {"code": "F1", "country": "france", "label": "Ligue 1"},
    "eredivisie": {"code": "N1", "country": "netherlands", "label": "Eredivisie"},
    "primeira-liga": {"code": "P1", "country": "portugal", "label": "Primeira Liga"},
}

DEFAULT_LEAGUES = ["epl", "serie-a", "la-liga", "bundesliga", "ligue-1"]

REQUIRED_COLUMNS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]
SHOTS_COLUMNS = ["HS", "AS", "HST", "AST"]
EXTRA_COLUMNS = ["HC", "AC", "HF", "AF", "HY", "AY", "HR", "AR"]

ALL_SEASONS = list(range(2005, 2026))


def season_code(start_year: int) -> str:
    """Convert e.g. 2023 -> '2324'."""
    end = (start_year + 1) % 100
    return f"{start_year % 100:02d}{end:02d}"


def build_url(league_code: str, start_year: int) -> str:
    sc = season_code(start_year)
    return f"{BASE_URL}/mmz4281/{sc}/{league_code}.csv"


def download_season(
    league_key: str,
    start_year: int,
    out_dir: Path,
    *,
    overwrite: bool = False,
) -> Optional[Path]:
    cfg = LEAGUE_CODES[league_key]
    url = build_url(cfg["code"], start_year)
    end_year = start_year + 1
    filename = f"{league_key}-{start_year}-{end_year}.csv"
    out_path = out_dir / filename

    if out_path.exists() and not overwrite:
        print(f"  [skip] {filename} (already exists)")
        return out_path

    print(f"  [GET]  {url}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [FAIL] {filename}: {exc}")
        return None

    raw_text = resp.text
    if not raw_text.strip():
        print(f"  [FAIL] {filename}: empty response")
        return None

    reader = csv.DictReader(io.StringIO(raw_text))
    fields = reader.fieldnames or []

    missing_required = [c for c in REQUIRED_COLUMNS if c not in fields]
    if missing_required:
        print(f"  [WARN] {filename}: missing columns {missing_required}")
        return None

    has_shots = all(c in fields for c in SHOTS_COLUMNS)
    if not has_shots:
        print(f"  [WARN] {filename}: no shots columns (HS/AS/HST/AST) -- skipping")
        return None

    keep_cols = REQUIRED_COLUMNS + SHOTS_COLUMNS + [c for c in EXTRA_COLUMNS if c in fields]
    keep_cols += [c for c in ["FTR", "HTHG", "HTAG", "HTR", "Referee"] if c in fields]
    keep_cols += [c for c in fields if c.startswith("B365") or c.startswith("BW") or c.startswith("IW")]

    rows_out = []
    for row in reader:
        date_raw = (row.get("Date") or "").strip()
        if not date_raw:
            continue
        out_row = {"league": league_key, "season": f"{start_year}-{end_year}"}
        for col in keep_cols:
            out_row[col] = (row.get(col) or "").strip()
        rows_out.append(out_row)

    if not rows_out:
        print(f"  [WARN] {filename}: no valid rows")
        return None

    out_fields = ["league", "season"] + keep_cols
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_out)

    n_with_shots = sum(1 for r in rows_out if r.get("HS"))
    print(f"  [OK]   {filename}: {len(rows_out)} matches, {n_with_shots} with shot data")
    return out_path


def merge_all(out_dir: Path) -> Path:
    """Merge all per-league-season CSVs into one combined file."""
    merged_path = out_dir / "all-historical-matches.csv"
    all_rows: List[dict] = []
    all_fields: List[str] = []

    for csv_path in sorted(out_dir.glob("*.csv")):
        if csv_path.name == "all-historical-matches.csv":
            continue
        with open(csv_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fields = reader.fieldnames or []
            for f in fields:
                if f not in all_fields:
                    all_fields.append(f)
            for row in reader:
                all_rows.append(row)

    all_rows.sort(key=lambda r: (r.get("Date", ""), r.get("league", "")))

    with open(merged_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n  Merged {len(all_rows)} rows -> {merged_path.name}")
    return merged_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Football-Data.co.uk historical CSVs")
    parser.add_argument("--leagues", nargs="+", default=DEFAULT_LEAGUES,
                        choices=list(LEAGUE_CODES.keys()), help="Leagues to download")
    parser.add_argument("--seasons", nargs="+", type=int,
                        default=list(range(2014, 2026)),
                        help="Start years (e.g. 2020 for 2020-2021 season)")
    parser.add_argument("--all-seasons", action="store_true",
                        help="Download all available seasons (2005-2025)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--overwrite", action="store_true", help="Re-download existing files")
    parser.add_argument("--no-merge", action="store_true", help="Skip merging into combined CSV")
    args = parser.parse_args()

    seasons = ALL_SEASONS if args.all_seasons else args.seasons
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    failed = 0
    for league in args.leagues:
        cfg = LEAGUE_CODES[league]
        print(f"\n{'='*60}")
        print(f"  {cfg['label']} ({league})")
        print(f"{'='*60}")
        for year in seasons:
            result = download_season(league, year, out_dir, overwrite=args.overwrite)
            if result:
                total += 1
            else:
                failed += 1
            time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"  Downloaded {total} files, {failed} failed/skipped")
    print(f"{'='*60}")

    if not args.no_merge and total > 0:
        merge_all(out_dir)


if __name__ == "__main__":
    main()
