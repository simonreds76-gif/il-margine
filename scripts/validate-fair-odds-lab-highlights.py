#!/usr/bin/env python3
"""Validate that Fair Odds Lab highlights match settled winning signals."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "goalscorer"
DEFAULT_HIGHLIGHTS = ROOT / "public" / "fair-odds-lab" / "highlights.json"


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def parse_timestamp(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def league_from_path(path: Path) -> str:
    return path.name.removeprefix("fair-odds-lab-").removesuffix("-signals.csv")


def highlight_id(date: str, league: str, match: str, player: str) -> str:
    return f"{date}-{league}-{match}-{player}".lower().replace(" ", "-")


def winning_rows(input_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(input_dir.glob("fair-odds-lab-*-signals.csv")):
        league = league_from_path(path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if clean_text(row.get("bet_outcome")).lower() != "won":
                    continue
                date = clean_text(row.get("date"))
                match = clean_text(row.get("match"))
                player = clean_text(row.get("player") or row.get("market_player_name"))
                row["_league"] = league
                row["_highlight_id"] = highlight_id(date, league, match, player)
                rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            clean_text(row.get("date")),
            clean_text(row.get("kickoff")),
            clean_text(row.get("settled_at")),
        ),
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Fair Odds Lab highlights freshness")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR), help="Directory containing fair-odds-lab-*-signals.csv")
    parser.add_argument("--highlights", default=str(DEFAULT_HIGHLIGHTS), help="Highlights JSON path")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    highlights_path = Path(args.highlights)
    winners = winning_rows(input_dir)

    if not winners:
        print("FAIR_ODDS_LAB_HIGHLIGHTS_OK no_settled_winners")
        return 0

    if not highlights_path.exists():
        raise SystemExit(f"Fair Odds Lab highlights missing: {highlights_path}")

    payload = json.loads(highlights_path.read_text(encoding="utf-8-sig"))
    highlights = payload.get("highlights")
    if not isinstance(highlights, list):
        raise SystemExit("Fair Odds Lab highlights payload has no highlights list")

    latest = winners[0]
    latest_id = clean_text(latest.get("_highlight_id"))
    latest_settled_at = parse_timestamp(latest.get("settled_at"))
    generated_at = parse_timestamp(payload.get("generated_at"))
    highlight_ids = {clean_text(row.get("id")) for row in highlights if isinstance(row, dict)}

    if latest_id not in highlight_ids:
        raise SystemExit(
            "Fair Odds Lab highlights stale: latest settled winner is missing "
            f"({latest_id}, settled_at={clean_text(latest.get('settled_at'))})"
        )

    if latest_settled_at is not None and generated_at is not None and generated_at < latest_settled_at:
        raise SystemExit(
            "Fair Odds Lab highlights stale: generated_at is older than latest settled winner "
            f"(generated_at={payload.get('generated_at')}, latest_settled_at={latest.get('settled_at')})"
        )

    print(
        "FAIR_ODDS_LAB_HIGHLIGHTS_OK "
        f"latest_winner={latest_id} generated_at={clean_text(payload.get('generated_at'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
