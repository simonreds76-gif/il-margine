#!/usr/bin/env python3
"""
Build per-league penalty baseline evidence from reviewed penalty events.

This sits between the raw review queue and the live goalscorer model:
- live / settled penalty reviews tell us who actually took recent penalties
- this script deduplicates those events and turns them into lightweight
  observed share evidence per team/player
- live compare can then blend that evidence into the penalty component before
  falling back to the manual hierarchy prior
"""

from __future__ import annotations

import argparse
import json
import re
import runpy
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from goalscorer_penalty_utils import best_name_match


ROOT = Path(__file__).resolve().parents[1]

LEAGUE_PATHS = {
    "serie-a": {
        "review_json": ROOT / "data" / "goalscorer" / "penalty-duty-review.json",
        "live_review_json": ROOT / "data" / "goalscorer" / "penalty-duty-live-review.json",
        "output": ROOT / "data" / "goalscorer" / "penalty-baseline-evidence.json",
    },
    "epl": {
        "review_json": ROOT / "data" / "goalscorer" / "epl-penalty-duty-review.json",
        "live_review_json": ROOT / "data" / "goalscorer" / "epl-penalty-duty-live-review.json",
        "output": ROOT / "data" / "goalscorer" / "epl-penalty-baseline-evidence.json",
    },
    "la-liga": {
        "review_json": ROOT / "data" / "goalscorer" / "la-liga-penalty-duty-review.json",
        "live_review_json": ROOT / "data" / "goalscorer" / "la-liga-penalty-duty-live-review.json",
        "output": ROOT / "data" / "goalscorer" / "la-liga-penalty-baseline-evidence.json",
    },
    "bundesliga": {
        "review_json": ROOT / "data" / "goalscorer" / "bundesliga-penalty-duty-review.json",
        "live_review_json": ROOT / "data" / "goalscorer" / "bundesliga-penalty-duty-live-review.json",
        "output": ROOT / "data" / "goalscorer" / "bundesliga-penalty-baseline-evidence.json",
    },
    "ligue-1": {
        "review_json": ROOT / "data" / "goalscorer" / "ligue-1-penalty-duty-review.json",
        "live_review_json": ROOT / "data" / "goalscorer" / "ligue-1-penalty-duty-live-review.json",
        "output": ROOT / "data" / "goalscorer" / "ligue-1-penalty-baseline-evidence.json",
    },
}

SOURCE_PRIORITY = {
    "settled_logs": 2,
    "fotmob_live": 1,
}


def _norm_text(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower())
    return re.sub(r"\s+", " ", cleaned).strip()


MODEL_MOD = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
TEAM_KEY = MODEL_MOD["_team_key"]


def _load_payload(path: Path) -> List[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _dedupe_events(rows: Iterable[dict]) -> List[dict]:
    kept: List[dict] = []

    for row in rows:
        team = str(row.get("team") or "").strip()
        taker = str(row.get("actual_taker") or "").strip()
        if not team or not taker:
            continue

        attempts = int(float(row.get("penalties_attempted") or 0))
        scored = int(float(row.get("penalties_scored") or 0))
        date = str(row.get("date") or "").strip()
        match = str(row.get("match") or "").strip()
        team_key = TEAM_KEY(team)
        source = str(row.get("review_source") or "").strip()

        duplicate_index = -1
        for idx, existing in enumerate(kept):
            same_bucket = (
                str(existing.get("date") or "").strip() == date
                and TEAM_KEY(str(existing.get("team") or "").strip()) == team_key
                and str(existing.get("match") or "").strip() == match
                and int(float(existing.get("penalties_attempted") or 0)) == attempts
                and int(float(existing.get("penalties_scored") or 0)) == scored
            )
            if not same_bucket:
                continue
            existing_taker = str(existing.get("actual_taker") or "").strip()
            if best_name_match(taker, [existing_taker]):
                duplicate_index = idx
                break

        if duplicate_index >= 0:
            existing = kept[duplicate_index]
            if SOURCE_PRIORITY.get(source, 0) > SOURCE_PRIORITY.get(str(existing.get("review_source") or ""), 0):
                kept[duplicate_index] = row
            continue

        kept.append(row)

    return sorted(kept, key=lambda row: (str(row.get("date") or ""), str(row.get("team") or ""), str(row.get("actual_taker") or "")))


def build_payload(league_key: str, settled_rows: List[dict], live_rows: List[dict]) -> dict:
    deduped = _dedupe_events([*live_rows, *settled_rows])

    team_totals: Dict[str, int] = defaultdict(int)
    team_labels: Dict[str, str] = {}
    player_labels: Dict[Tuple[str, str], str] = {}
    player_totals: Dict[Tuple[str, str], int] = defaultdict(int)
    player_sources: Dict[Tuple[str, str], set[str]] = defaultdict(set)
    player_dates: Dict[Tuple[str, str], str] = {}
    player_events: Dict[Tuple[str, str], int] = defaultdict(int)

    for row in deduped:
        team = str(row.get("team") or "").strip()
        taker = str(row.get("actual_taker") or "").strip()
        if not team or not taker:
            continue

        attempts = int(float(row.get("penalties_attempted") or 0))
        if attempts <= 0:
            continue

        team_key = TEAM_KEY(team)
        player_key = _norm_text(taker)
        existing_keys = [existing_player_key for existing_team_key, existing_player_key in player_totals.keys() if existing_team_key == team_key]
        matched_existing = ""
        if existing_keys:
            existing_names = [player_labels[(team_key, existing_key)] for existing_key in existing_keys]
            matched_name = best_name_match(taker, existing_names)
            if matched_name:
                for existing_key in existing_keys:
                    if player_labels[(team_key, existing_key)] == matched_name:
                        matched_existing = existing_key
                        break
        if matched_existing:
            player_key = matched_existing
        pair_key = (team_key, player_key)

        team_totals[team_key] += attempts
        team_labels[team_key] = team
        current_label = player_labels.get(pair_key, "")
        player_labels[pair_key] = taker if len(taker) >= len(current_label) else current_label
        player_totals[pair_key] += attempts
        player_sources[pair_key].add(str(row.get("review_source") or "").strip() or "unknown")
        player_dates[pair_key] = max(player_dates.get(pair_key, ""), str(row.get("date") or "").strip())
        player_events[pair_key] += 1

    rows: List[dict] = []
    for (team_key, player_key), player_attempts in sorted(player_totals.items()):
        team_attempts = team_totals.get(team_key, 0)
        if player_attempts <= 0 or team_attempts <= 0:
            continue
        rows.append(
            {
                "team": team_labels.get(team_key, team_key),
                "team_key": team_key,
                "player_name": player_labels[(team_key, player_key)],
                "player_key": player_key,
                "observed_player_penalties": player_attempts,
                "observed_team_penalties": team_attempts,
                "observed_share": round(player_attempts / team_attempts, 4),
                "observed_sample": round(min(float(team_attempts), 6.0), 2),
                "evidence_source": "review_events",
                "review_sources": sorted(player_sources[(team_key, player_key)]),
                "event_count": player_events[(team_key, player_key)],
                "last_event_date": player_dates.get((team_key, player_key), ""),
            }
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "league": league_key,
        "row_count": len(rows),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build penalty baseline evidence from review files")
    parser.add_argument("--league", choices=sorted(LEAGUE_PATHS), required=True)
    parser.add_argument("--review-json", default="", help="Optional settled review JSON override")
    parser.add_argument("--live-review-json", default="", help="Optional live review JSON override")
    parser.add_argument("--output", default="", help="Optional output JSON override")
    args = parser.parse_args()

    paths = LEAGUE_PATHS[args.league]
    review_json = Path(args.review_json) if args.review_json else paths["review_json"]
    live_review_json = Path(args.live_review_json) if args.live_review_json else paths["live_review_json"]
    output_path = Path(args.output) if args.output else paths["output"]

    payload = build_payload(args.league, _load_payload(review_json), _load_payload(live_review_json))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  Saved {args.league}: {output_path} ({payload['row_count']:,} rows)")


if __name__ == "__main__":
    main()
