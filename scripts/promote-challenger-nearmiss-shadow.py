#!/usr/bin/env python3
"""Promote Challenger ML near-miss rows into the internal settlement ledger.

The near-miss file is useful only if it can be evaluated like a shadow lane.
This script turns those rows into strict-signal-shaped rows, enriches local
Pinnacle odds when available, and writes the Challenger ML archive/live files.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NEARMISS = ROOT / "data" / "backtest" / "challenger-ml-shadow-nearmiss.csv"
DEFAULT_ARCHIVE = ROOT / "data" / "backtest" / "strict-signals-challenger-ml-archive.csv"
DEFAULT_LIVE = ROOT / "data" / "backtest" / "strict-signals-challenger-ml-live.csv"
PINNACLE_GLOB = "pinnacle-odds-*.csv"

FIELDNAMES = [
    "date",
    "time_utc",
    "player1",
    "player2",
    "surface",
    "league",
    "series",
    "tour_id",
    "tour_name",
    "challenger_event",
    "data_coverage_tag",
    "match_count_12m_p1",
    "match_count_12m_p2",
    "matches_total_p1",
    "matches_total_p2",
    "recent_challenger_plus_p1",
    "recent_challenger_plus_p2",
    "last_match_days_p1",
    "last_match_days_p2",
    "confidence",
    "side",
    "value_pct",
    "skip_reason",
    "shadow_reason",
    "odds_capture_status",
    "pin_odds1",
    "pin_odds2",
    "pinnacle_margin",
    "pinnacle_league_name",
    "bet_type",
    "policy_mode",
    "stake_units",
    "stake_gbp",
    "stake_model",
    "signal_profile",
    "settlement_status",
    "result",
    "bet_outcome",
    "won_bet",
    "match_date",
    "player1_id",
    "player2_id",
    "winner_id",
    "loser_id",
    "settled_at",
    "settlement_note",
    "closing_odds1",
    "closing_odds2",
    "closing_source",
]


def norm(text: str | None) -> str:
    value = "".join(
        ch for ch in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(ch)
    ).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def pair_key(player1: str | None, player2: str | None) -> tuple[str, str]:
    return tuple(sorted((norm(player1), norm(player2))))  # type: ignore[return-value]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def load_pinnacle_odds() -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for path in sorted((ROOT / "data").glob(PINNACLE_GLOB)):
        rows = read_csv(path)
        for row in rows:
            key = pair_key(row.get("player1_name"), row.get("player2_name"))
            if not key[0] or not key[1]:
                continue
            # Keep the first matching snapshot. These daily files are already local audit snapshots.
            out.setdefault(
                key,
                {
                    "pin_odds1": row.get("odds1", ""),
                    "pin_odds2": row.get("odds2", ""),
                    "pinnacle_margin": row.get("pinnacle_margin", ""),
                    "pinnacle_league_name": row.get("league_name", ""),
                    "odds_source_file": path.name,
                },
            )
    return out


def signal_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("date", ""),
        norm(row.get("player1")),
        norm(row.get("player2")),
        (row.get("side") or "").upper(),
        row.get("signal_profile", ""),
    )


def promote_row(row: dict[str, str], odds_index: dict[tuple[str, str], dict[str, str]]) -> dict[str, str]:
    odds = odds_index.get(pair_key(row.get("player1"), row.get("player2")), {})
    has_odds = bool(odds.get("pin_odds1") and odds.get("pin_odds2"))
    promoted = {field: "" for field in FIELDNAMES}
    for field in row:
        if field in promoted:
            promoted[field] = row.get(field, "")

    promoted.update(
        {
            "league": "Challenger",
            "series": row.get("series") or "Challenger",
            "shadow_reason": row.get("skip_reason", ""),
            "odds_capture_status": "matched_local_pinnacle" if has_odds else "missing_local_pinnacle",
            "pin_odds1": odds.get("pin_odds1", ""),
            "pin_odds2": odds.get("pin_odds2", ""),
            "pinnacle_margin": odds.get("pinnacle_margin", ""),
            "pinnacle_league_name": odds.get("pinnacle_league_name", ""),
            "bet_type": "match",
            "policy_mode": "base",
            "stake_units": row.get("stake_units") or "1.0",
            "stake_gbp": row.get("stake_gbp") or "100.0",
            "stake_model": row.get("stake_model") or "flat_match",
            "signal_profile": row.get("signal_profile") or "challenger_ml_nearmiss",
            "settlement_status": row.get("settlement_status") or "pending",
            "settlement_note": row.get("settlement_note", ""),
        }
    )
    return promoted


def merge_existing(existing: list[dict[str, str]], promoted: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    for row in existing:
        if not row.get("date") or not row.get("player1") or not row.get("player2"):
            continue
        by_key[signal_key(row)] = {field: row.get(field, "") for field in FIELDNAMES}

    for row in promoted:
        key = signal_key(row)
        prev = by_key.get(key)
        if not prev:
            by_key[key] = row
            continue
        # Preserve settlement fields if the row already settled, but refresh odds/metadata.
        settled = (prev.get("settlement_status") or "").strip().lower() == "settled"
        merged = {**prev, **row}
        if settled:
            for field in [
                "settlement_status",
                "result",
                "bet_outcome",
                "won_bet",
                "match_date",
                "player1_id",
                "player2_id",
                "winner_id",
                "loser_id",
                "settled_at",
                "settlement_note",
                "closing_odds1",
                "closing_odds2",
                "closing_source",
            ]:
                merged[field] = prev.get(field, "")
        by_key[key] = merged

    return sorted(by_key.values(), key=lambda r: (r.get("date", ""), r.get("time_utc", ""), r.get("player1", "")))


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nearmiss", default=str(DEFAULT_NEARMISS))
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--live", default=str(DEFAULT_LIVE))
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()

    nearmiss_path = Path(args.nearmiss)
    archive_path = Path(args.archive)
    live_path = Path(args.live)
    as_of = parse_date(args.as_of) or date.today()

    nearmiss_rows = read_csv(nearmiss_path)
    odds_index = load_pinnacle_odds()
    promoted = [promote_row(row, odds_index) for row in nearmiss_rows]
    archive_rows = merge_existing(read_csv(archive_path), promoted)
    live_rows = [
        row
        for row in archive_rows
        if (row.get("settlement_status") or "").strip().lower() != "settled"
        and (parse_date(row.get("date", "")) or as_of) >= as_of
    ]

    write_csv(archive_path, archive_rows)
    write_csv(live_path, live_rows)

    matched_odds = sum(1 for row in archive_rows if row.get("odds_capture_status") == "matched_local_pinnacle")
    print(f"promoted={len(promoted)} archive_rows={len(archive_rows)} live_rows={len(live_rows)} odds_matched={matched_odds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
