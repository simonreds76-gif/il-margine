#!/usr/bin/env python3
"""Build the Fair Odds Lab winners-only highlight artifact.

This intentionally publishes a highlight reel, not a performance record. The
official record stays separate until the goalscorer model is promoted.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "goalscorer"
DEFAULT_OUTPUT = ROOT / "public" / "fair-odds-lab" / "highlights.json"


def clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def parse_float(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_date_sort_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        clean_text(row.get("date")),
        clean_text(row.get("kickoff")),
        clean_text(row.get("settled_at")),
    )


def league_from_path(path: Path) -> str:
    name = path.name
    return name.removeprefix("fair-odds-lab-").removesuffix("-signals.csv")


def highlight_from_row(row: dict[str, str], league: str) -> dict[str, Any] | None:
    if clean_text(row.get("bet_outcome")).lower() != "won":
        return None

    best_odds = parse_float(row.get("best_bookmaker_odds"))
    fair_odds = parse_float(row.get("model_fair_odds"))
    model_prob = parse_float(row.get("model_p_atgs"))
    if best_odds is None or fair_odds is None or model_prob is None or best_odds <= 0:
        return None

    market_prob = 1.0 / best_odds
    price_gap_pp = (model_prob - market_prob) * 100.0
    date = clean_text(row.get("date"))
    match = clean_text(row.get("match"))
    player = clean_text(row.get("player") or row.get("market_player_name"))
    settlement_note = clean_text(row.get("settlement_note"))
    super_sub_replacement = clean_text(row.get("super_sub_replacement"))
    super_sub_replacement_goals = int(parse_float(row.get("super_sub_replacement_goals")) or 0)
    super_sub_win = settlement_note.startswith("super_sub_replacement_scored:")

    return {
        "id": f"{date}-{league}-{match}-{player}".lower().replace(" ", "-"),
        "date": date,
        "kickoff": clean_text(row.get("kickoff")) or date,
        "competition": clean_text(row.get("competition"), league),
        "league": league,
        "match": match,
        "player": player,
        "team": clean_text(row.get("team")),
        "best_bookmaker": clean_text(row.get("best_bookmaker"), "Best market"),
        "best_odds": round(best_odds, 2),
        "fair_odds": round(fair_odds, 2),
        "model_chance_pct": round(model_prob * 100.0, 1),
        "market_chance_pct": round(market_prob * 100.0, 1),
        "price_gap_pp": round(price_gap_pp, 1),
        "goals_scored": int(parse_float(row.get("goals_scored")) or 1),
        "super_sub_win": super_sub_win,
        "super_sub_replacement": super_sub_replacement,
        "super_sub_replacement_goals": super_sub_replacement_goals,
        "settled_at": clean_text(row.get("settled_at")),
        "settlement_note": settlement_note,
    }


def read_highlights(input_dir: Path) -> list[dict[str, Any]]:
    highlights: list[dict[str, Any]] = []
    for path in sorted(input_dir.glob("fair-odds-lab-*-signals.csv")):
        league = league_from_path(path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                highlight = highlight_from_row(row, league)
                if highlight:
                    highlights.append(highlight)
    return sorted(
        highlights,
        key=lambda row: (
            clean_text(row.get("date")),
            clean_text(row.get("kickoff")),
            clean_text(row.get("settled_at")),
        ),
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Fair Odds Lab winning highlights")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR), help="Directory containing fair-odds-lab-*-signals.csv")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path")
    parser.add_argument("--max-highlights", type=int, default=6, help="Maximum winning highlights to publish")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output = Path(args.output)
    highlights = read_highlights(input_dir)[: max(args.max_highlights, 0)]

    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "fair_odds_lab_settled_winners",
        "description": "Winning highlights from Fair Odds Lab research signals.",
        "highlights": highlights,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("================================================================")
    print("  IL MARGINE - Fair Odds Lab Highlights")
    print("================================================================")
    print(f"Input dir:   {input_dir}")
    print(f"Output:      {output}")
    print(f"Highlights:  {len(highlights)}")
    print("\nDone.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
