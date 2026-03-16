"""
Refresh local Jeff Sackmann ATP CSV snapshots used by auxiliary tennis pipelines.

This updates:
  - atp_players.csv
  - atp_matches_<year>.csv
  - atp_matches_qual_chall_<year>.csv

We keep this lightweight and opportunistic:
  - if a remote file doesn't exist yet (404), we skip it
  - if content matches local bytes, we leave the file untouched

Run:
  python scripts/sackmann-refresh-data.py
  python scripts/sackmann-refresh-data.py --start-year 2023 --end-year 2026
  python scripts/sackmann-refresh-data.py --dry-run
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "sackmann"
BASE_URL = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"
REQ_TIMEOUT = 60


def _fetch_bytes(url: str) -> tuple[int, bytes | None]:
    r = requests.get(url, timeout=REQ_TIMEOUT)
    if r.status_code == 404:
        return 404, None
    r.raise_for_status()
    return r.status_code, r.content


def _refresh_file(filename: str, dry_run: bool) -> str:
    url = f"{BASE_URL}/{filename}"
    status, content = _fetch_bytes(url)
    if status == 404 or content is None:
        return f"skip_missing_remote {filename}"

    path = DATA_DIR / filename
    if path.exists():
        current = path.read_bytes()
        if current == content:
            return f"unchanged {filename}"

    if not dry_run:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return f"{'would_update' if dry_run else 'updated'} {filename}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.end_year < args.start_year:
        raise SystemExit("--end-year must be >= --start-year")

    files: list[str] = ["atp_players.csv"]
    for year in range(args.start_year, args.end_year + 1):
        files.append(f"atp_matches_{year}.csv")
        files.append(f"atp_matches_qual_chall_{year}.csv")

    print(f"Refreshing Sackmann ATP files from {args.start_year} to {args.end_year}")
    print(f"Target dir: {DATA_DIR}")

    counts = {
        "updated": 0,
        "unchanged": 0,
        "skip_missing_remote": 0,
        "would_update": 0,
    }

    for filename in files:
        result = _refresh_file(filename, dry_run=args.dry_run)
        key = result.split()[0]
        counts[key] = counts.get(key, 0) + 1
        print(f"  {result}")

    print("Summary:")
    for key in ("updated", "would_update", "unchanged", "skip_missing_remote"):
        print(f"  {key}: {counts.get(key, 0)}")


if __name__ == "__main__":
    main()
