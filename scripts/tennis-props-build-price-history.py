#!/usr/bin/env python3
"""Seed append-only monthly Bet365 tennis-props price history from daily captures."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "tennis-props" / "inbox"
FIELDS = [
    "event_id", "date", "tour", "tournament", "bookmaker", "player", "opponent",
    "market", "line", "over_odds", "under_odds", "capture_ts", "match_start_utc",
    "raw_market_name", "raw_outcome_count", "raw_label_sample",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inbox", type=Path, default=INBOX)
    args = parser.parse_args()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for path in sorted(args.inbox.glob("bet365-lines-????-??-??.csv")):
        rows = read_csv(path)
        for row in rows:
            # Legacy files predate event/timestamp capture and cannot support
            # closing-price matching. Keep them out rather than fabricate time.
            if not row.get("event_id") or not row.get("capture_ts") or not row.get("match_start_utc"):
                continue
            month = str(row.get("date") or "")[:7]
            if len(month) == 7:
                grouped[month].append({field: str(row.get(field) or "") for field in FIELDS})
    if not grouped:
        print("No timestamped Bet365 line captures found.")
        return 0
    for month, rows in grouped.items():
        output = args.inbox / f"bet365-lines-history-{month}.csv"
        existing = [
            {field: str(row.get(field) or "") for field in FIELDS}
            for row in (read_csv(output) if output.exists() else [])
            if row.get("event_id") and row.get("capture_ts") and row.get("match_start_utc")
        ]
        seen = {tuple(str(row.get(field) or "") for field in FIELDS) for row in existing}
        for row in rows:
            key = tuple(str(row.get(field) or "") for field in FIELDS)
            if key not in seen:
                seen.add(key)
                existing.append(row)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(existing)
        print(f"Wrote {output} ({len(existing)} snapshots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
