"""
Refresh local Jeff Sackmann CSV snapshots used by auxiliary tennis pipelines.

This updates:
  - atp_players.csv
  - atp_matches_<year>.csv
  - atp_matches_qual_chall_<year>.csv
  - wta_players.csv
  - wta_matches_<year>.csv

We keep this lightweight and resilient:
  - try the original Sackmann repository first, then the archival mirror
  - if neither remote exists, preserve a verified local snapshot
  - if content matches local bytes, we leave the file untouched

Run:
  python scripts/sackmann-refresh-data.py
  python scripts/sackmann-refresh-data.py --start-year 2022 --end-year 2026
  python scripts/sackmann-refresh-data.py --tour wta
  python scripts/sackmann-refresh-data.py --dry-run
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "sackmann"
BASE_URLS = {
    "atp": (
        "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master",
        "https://huggingface.co/datasets/Aneeshers/tennis-sackmann-archive/resolve/main/atp",
    ),
    "wta": (
        "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master",
        "https://huggingface.co/datasets/Aneeshers/tennis-sackmann-archive/resolve/main/wta",
    ),
}
REQ_TIMEOUT = 60


def _fetch_bytes(url: str) -> tuple[int, bytes | None]:
    try:
        r = requests.get(url, timeout=REQ_TIMEOUT)
    except requests.RequestException:
        return 0, None
    if r.status_code == 404:
        return 404, None
    try:
        r.raise_for_status()
    except requests.RequestException:
        return r.status_code, None
    return r.status_code, r.content


def _valid_csv(content: bytes | None) -> bool:
    if content is None or len(content) <= 100:
        return False
    first_line = content.splitlines()[0].decode("utf-8-sig", errors="ignore").lower()
    return "," in first_line and ("player" in first_line or "tourney" in first_line)


def _refresh_file(filename: str, base_urls: tuple[str, ...], dry_run: bool) -> str:
    content: bytes | None = None
    source = ""
    for base_url in base_urls:
        candidate_url = f"{base_url}/{filename}"
        _status, candidate = _fetch_bytes(candidate_url)
        if _valid_csv(candidate):
            content = candidate
            source = "archive_mirror" if "huggingface.co" in base_url else "sackmann"
            break

    path = DATA_DIR / filename
    if content is None:
        # Sackmann's repositories can be temporarily unavailable or removed.
        # A verified local snapshot is still valid historical input; never
        # describe it as missing and never replace it with a 404 body.
        if path.exists() and path.stat().st_size > 100:
            return f"kept_local_snapshot {filename}"
        return f"skip_missing_remote {filename}"

    if path.exists():
        current = path.read_bytes()
        if current == content:
            return f"unchanged {filename} source={source}"

    if not dry_run:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return f"{'would_update' if dry_run else 'updated'} {filename} source={source}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--tour", choices=("atp", "wta", "both"), default="both")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.end_year < args.start_year:
        raise SystemExit("--end-year must be >= --start-year")

    files: list[tuple[str, str]] = []
    tours = ("atp", "wta") if args.tour == "both" else (args.tour,)
    for tour in tours:
        files.append((tour, f"{tour}_players.csv"))
        for year in range(args.start_year, args.end_year + 1):
            files.append((tour, f"{tour}_matches_{year}.csv"))
            if tour == "atp":
                files.append((tour, f"{tour}_matches_qual_chall_{year}.csv"))

    print(f"Refreshing Sackmann {args.tour.upper()} files from {args.start_year} to {args.end_year}")
    print(f"Target dir: {DATA_DIR}")

    counts = {
        "updated": 0,
        "unchanged": 0,
        "kept_local_snapshot": 0,
        "skip_missing_remote": 0,
        "would_update": 0,
    }

    for tour, filename in files:
        result = _refresh_file(filename, BASE_URLS[tour], dry_run=args.dry_run)
        key = result.split()[0]
        counts[key] = counts.get(key, 0) + 1
        print(f"  {result}")

    print("Summary:")
    for key in ("updated", "would_update", "unchanged", "kept_local_snapshot", "skip_missing_remote"):
        print(f"  {key}: {counts.get(key, 0)}")


if __name__ == "__main__":
    main()
