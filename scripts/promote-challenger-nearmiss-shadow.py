#!/usr/bin/env python3
"""Promote Challenger ML near-miss rows into the internal audit ledger.

The near-miss file is useful only if it can be settled and audited.
This script turns those rows into strict-signal-shaped rows, enriches local
Pinnacle odds when available, and writes the Challenger ML archive/live files.
Rows remain audit artifacts: they must not carry stake or be counted as bets.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NEARMISS = ROOT / "data" / "backtest" / "challenger-ml-v2-nearmiss.csv"
DEFAULT_ARCHIVE = ROOT / "data" / "backtest" / "strict-signals-challenger-ml-v2-archive.csv"
DEFAULT_LIVE = ROOT / "data" / "backtest" / "strict-signals-challenger-ml-v2-live.csv"
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


def load_pinnacle_odds(data_dir: Path | None = None) -> dict[tuple[str, str, str], dict[str, str]]:
    """Index snapshots by event date and pair so rematches cannot inherit stale odds."""
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    root = data_dir or (ROOT / "data")
    for path in sorted(root.glob(PINNACLE_GLOB)):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
        snapshot_date = match.group(1) if match else ""
        if not snapshot_date:
            continue
        rows = read_csv(path)
        for row in rows:
            pair = pair_key(row.get("player1_name"), row.get("player2_name"))
            if not pair[0] or not pair[1]:
                continue
            key = (snapshot_date, *pair)
            # Keep the first same-day snapshot as the immutable publication price.
            out.setdefault(
                key,
                {
                    "player1_name": row.get("player1_name", ""),
                    "player2_name": row.get("player2_name", ""),
                    "pin_odds1": row.get("odds1", ""),
                    "pin_odds2": row.get("odds2", ""),
                    "pinnacle_margin": row.get("pinnacle_margin", ""),
                    "pinnacle_league_name": row.get("league_name", ""),
                    "odds_source_file": path.name,
                },
            )
    return out


def orient_odds(
    signal_player1: str | None,
    signal_player2: str | None,
    odds: dict[str, str],
) -> dict[str, str]:
    if not odds:
        return {}
    signal_p1 = norm(signal_player1)
    signal_p2 = norm(signal_player2)
    odds_p1 = norm(odds.get("player1_name"))
    odds_p2 = norm(odds.get("player2_name"))
    if signal_p1 == odds_p1 and signal_p2 == odds_p2:
        return odds
    if signal_p1 == odds_p2 and signal_p2 == odds_p1:
        return {
            **odds,
            "player1_name": odds.get("player2_name", ""),
            "player2_name": odds.get("player1_name", ""),
            "pin_odds1": odds.get("pin_odds2", ""),
            "pin_odds2": odds.get("pin_odds1", ""),
        }
    return {}


def signal_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("date", ""),
        norm(row.get("player1")),
        norm(row.get("player2")),
        (row.get("side") or "").upper(),
        row.get("signal_profile", ""),
    )


def promote_row(row: dict[str, str], odds_index: dict[tuple[str, str, str], dict[str, str]]) -> dict[str, str]:
    pair = pair_key(row.get("player1"), row.get("player2"))
    odds = orient_odds(
        row.get("player1"),
        row.get("player2"),
        odds_index.get((row.get("date", ""), *pair), {}),
    )
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
            "stake_units": "0.0",
            "stake_gbp": "0.0",
            "stake_model": "audit_nearmiss_no_stake",
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
        # Preserve the first publication price and all settlement fields.
        settled = (prev.get("settlement_status") or "").strip().lower() == "settled"
        merged = {**prev, **row}
        for field in [
            "odds_capture_status",
            "pin_odds1",
            "pin_odds2",
            "pinnacle_margin",
            "pinnacle_league_name",
        ]:
            if prev.get(field):
                merged[field] = prev[field]
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
