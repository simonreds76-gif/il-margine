#!/usr/bin/env python3
"""Append current Assist model rows to a compact market-evidence ledger."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "assist-value" / "assist-value-shadow-signals.csv"
DEFAULT_HISTORY = ROOT / "data" / "assist-value" / "research" / "assist-value-market-history.csv"


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def row_identity(row: dict[str, str]) -> str:
    raw = "|".join(
        str(row.get(field) or "").strip().casefold()
        for field in (
            "model_version",
            "captured_at",
            "match_date",
            "home_team",
            "away_team",
            "player_name",
            "bookmaker",
            "market_odds",
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def append_rows(current: list[dict[str, str]], history: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    known = {str(row.get("market_history_id") or row_identity(row)) for row in history}
    output = list(history)
    added = 0
    for row in current:
        identity = row_identity(row)
        if identity in known:
            continue
        candidate = dict(row)
        candidate["market_history_id"] = identity
        output.append(candidate)
        known.add(identity)
        added += 1
    output.sort(
        key=lambda row: (
            str(row.get("captured_at") or ""),
            str(row.get("match_date") or ""),
            str(row.get("player_name") or ""),
        )
    )
    return output, added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    args = parser.parse_args()

    current, current_fields = read_rows(args.input)
    history, history_fields = read_rows(args.history)
    output, added = append_rows(current, history)
    fields = list(dict.fromkeys(["market_history_id", *history_fields, *current_fields]))
    args.history.parent.mkdir(parents=True, exist_ok=True)
    with args.history.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output)
    print(f"Assist market history: added {added}, total {len(output)} -> {args.history}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
