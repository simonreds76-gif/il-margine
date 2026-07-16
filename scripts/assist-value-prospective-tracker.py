#!/usr/bin/env python3
"""Append locked Assist Value v1 candidates to the prospective evidence ledger."""

from __future__ import annotations

import argparse
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIGNALS = ROOT / "data" / "assist-value" / "assist-value-shadow-signals.csv"
DEFAULT_LEDGER = ROOT / "data" / "assist-value" / "research" / "assist-value-v1-prospective.csv"
MODEL_VERSION = "assist_research_v1"
EXTRA_FIELDS = ["signal_id", "registered_at", "stake_units"]


def _read(path: Path) -> tuple[list[dict], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _write(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def signal_identity(row: dict) -> str:
    raw = "|".join(
        str(row.get(field) or "").strip().casefold()
        for field in ("model_version", "match_date", "league_key", "home_team", "away_team", "player_name", "bookmaker")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _is_pregame(row: dict) -> bool:
    captured = str(row.get("captured_at") or "").strip()
    kickoff = str(row.get("kickoff_at") or "").strip()
    return not captured or not kickoff or captured <= kickoff


def eligible(row: dict) -> bool:
    try:
        market_odds = float(str(row.get("market_odds") or "0"))
    except ValueError:
        return False
    return bool(
        str(row.get("model_version") or "") == MODEL_VERSION
        and str(row.get("signal_status") or "") == "shadow_signal"
        and str(row.get("lineup_state") or "") == "confirmed_starter"
        and market_odds > 1.0
        and _is_pregame(row)
    )


def update_ledger(signal_rows: list[dict], existing_rows: list[dict], now_iso: str) -> tuple[list[dict], int]:
    known = {str(row.get("signal_id") or signal_identity(row)) for row in existing_rows}
    latest: dict[str, dict] = {}
    for row in signal_rows:
        if not eligible(row):
            continue
        identity = signal_identity(row)
        if identity not in latest or str(row.get("captured_at") or "") > str(latest[identity].get("captured_at") or ""):
            latest[identity] = row
    added = 0
    output = list(existing_rows)
    for identity, row in sorted(latest.items(), key=lambda item: (str(item[1].get("kickoff_at") or ""), item[0])):
        if identity in known:
            continue
        candidate = dict(row)
        candidate["signal_id"] = identity
        candidate["registered_at"] = now_iso
        candidate["stake_units"] = "1.0"
        output.append(candidate)
        known.add(identity)
        added += 1
    return output, added


def main() -> int:
    parser = argparse.ArgumentParser(description="Append Assist Value v1 confirmed-lineup candidates")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    args = parser.parse_args()

    signals, signal_fields = _read(Path(args.signals))
    existing, existing_fields = _read(Path(args.ledger))
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows, added = update_ledger(signals, existing, now_iso)
    fields = list(dict.fromkeys([*EXTRA_FIELDS, *existing_fields, *signal_fields]))
    for field in ("settled", "assists_recorded", "bet_outcome", "settled_at", "pnl_units", "settlement_note"):
        if field not in fields:
            fields.append(field)
    _write(Path(args.ledger), rows, fields)
    print(f"Assist v1 prospective ledger: added {added}, total {len(rows)} -> {args.ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
