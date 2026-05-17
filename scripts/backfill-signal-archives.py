#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from signal_storage import (
    SPREAD_SHADOW_SIGNAL_PATHS,
    SPREAD_V1_SIGNAL_PATHS,
    STRICT_SIGNAL_PATHS,
    VOLUME_200_SIGNAL_PATHS,
)


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"
ARCHIVE_KEY_FIELDS = [
    "date",
    "time_utc",
    "player1",
    "player2",
    "bet_type",
    "side",
    "spread_line",
    "policy_mode",
    "signal_profile",
]

PROFILE_PATHS = {
    "strict": STRICT_SIGNAL_PATHS,
    "volume_200": VOLUME_200_SIGNAL_PATHS,
    "spread_shadow": SPREAD_SHADOW_SIGNAL_PATHS,
    "spread_v1_shadow": SPREAD_V1_SIGNAL_PATHS,
}


def load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        return list(reader.fieldnames or []), rows


def write_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows([{header: row.get(header, "") for header in headers} for row in rows])


def merge_headers(*header_sets: list[str]) -> list[str]:
    merged: list[str] = []
    for headers in header_sets:
        for header in headers:
            if header not in merged:
                merged.append(header)
    return merged


def lane_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple((row.get(field) or "").strip().lower() for field in ARCHIVE_KEY_FIELDS)


def latest_backup_for(paths) -> Path | None:
    pattern = f"{paths.legacy.stem}.bak-*.csv"
    backups = sorted(DATA_DIR.glob(pattern))
    return backups[-1] if backups else None


def backfill_profile(profile: str, dry_run: bool = False) -> tuple[int, int, Path | None]:
    paths = PROFILE_PATHS[profile]
    backup_path = latest_backup_for(paths)
    backup_headers, backup_rows = load_rows(backup_path) if backup_path else ([], [])
    archive_headers, archive_rows = load_rows(paths.archive)

    merged_headers = merge_headers(backup_headers, archive_headers)
    merged_rows: dict[tuple[str, ...], dict[str, str]] = {}

    for row in backup_rows:
        merged_rows[lane_key(row)] = row
    for row in archive_rows:
        merged_rows[lane_key(row)] = row

    ordered_rows = list(merged_rows.values())
    if not dry_run:
        write_rows(paths.archive, merged_headers, ordered_rows)

    return len(backup_rows), len(ordered_rows), backup_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill split signal archives from latest local backups.")
    parser.add_argument(
        "--profile",
        action="append",
        choices=sorted(PROFILE_PATHS.keys()),
        help="Limit to one or more signal profiles",
    )
    parser.add_argument("--dry-run", action="store_true", help="Inspect backup merge without writing archives")
    args = parser.parse_args()

    profiles = args.profile or list(PROFILE_PATHS.keys())
    for profile in profiles:
        backup_rows, merged_rows, backup_path = backfill_profile(profile, dry_run=args.dry_run)
        backup_label = str(backup_path.relative_to(ROOT)) if backup_path else "none"
        action = "would write" if args.dry_run else "wrote"
        print(
            f"[{profile}] backup={backup_label} backup_rows={backup_rows} {action} "
            f"{merged_rows} rows to {PROFILE_PATHS[profile].archive.relative_to(ROOT)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
