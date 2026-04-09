#!/usr/bin/env python3
"""
Merge team-shots odds inbox CSVs into a canonical odds history file.

Only **team total shots** rows are kept (market TEAM_SHOTS). Legacy rows from
the mistaken player_shots scrape (The Odds API) are dropped on rewrite.

Usage:
  python scripts/team-shots-odds-archive.py
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
from pathlib import Path
from typing import List, Set

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_GLOB = "data/team-shots/inbox/*.csv"
DEFAULT_ARCHIVE = ROOT / "data" / "team-shots" / "team-shots-odds-history.csv"

ARCHIVE_FIELDS = [
    "captured_at", "match_date", "event_id", "kickoff_at",
    "snapshot_kind", "bookmaker", "competition",
    "home_team", "away_team", "team", "market",
    "line", "side", "odds_decimal", "source", "notes",
]


def _is_team_total_row(row: dict) -> bool:
    """Keep only team total shots lines; drop player prop rows."""
    m = (row.get("market") or "").strip().lower()
    if m in ("player_shots", "player_shots_on_target"):
        return False
    if row.get("player") and not (row.get("team") or "").strip():
        return False
    return True


def dedup_key(row: dict) -> str:
    return "|".join([
        (row.get("match_date") or "").strip(),
        (row.get("home_team") or "").strip().lower(),
        (row.get("away_team") or "").strip().lower(),
        (row.get("team") or "").strip().lower(),
        (row.get("bookmaker") or "").strip().lower(),
        str(row.get("line", "")).strip(),
        (row.get("side") or "").strip().lower(),
        (row.get("captured_at") or "").strip()[:16],
    ])


def load_existing(path: Path) -> tuple[list[dict], set[str], int]:
    rows: List[dict] = []
    keys: Set[str] = set()
    dropped = 0
    if not path.exists():
        return rows, keys, dropped
    with open(path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not _is_team_total_row(row):
                dropped += 1
                continue
            rows.append(row)
            keys.add(dedup_key(row))
    return rows, keys, dropped


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive team-shots odds into canonical history")
    parser.add_argument("--input", default=DEFAULT_INPUT_GLOB)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    args = parser.parse_args()

    input_pattern = str(ROOT / args.input) if not os.path.isabs(args.input) else args.input
    inbox_files = sorted(glob.glob(input_pattern))

    existing_rows, existing_keys, pruned = load_existing(args.archive)
    print(f"Existing archive: {len(existing_rows)} team-total rows (dropped {pruned} non-team rows)")
    print(f"Inbox files: {len(inbox_files)}")

    new_count = 0
    for fpath in inbox_files:
        with open(fpath, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if not _is_team_total_row(row):
                    continue
                key = dedup_key(row)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                existing_rows.append(row)
                new_count += 1

    if new_count == 0 and pruned == 0:
        print("No changes.")
        return

    existing_rows.sort(key=lambda r: (r.get("match_date", ""), r.get("captured_at", "")))
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with open(args.archive, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ARCHIVE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing_rows)

    print(f"Added {new_count} new rows -> total {len(existing_rows)}")
    print(f"Archive: {args.archive}")


if __name__ == "__main__":
    main()
