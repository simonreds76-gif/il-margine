#!/usr/bin/env python3
"""
Seed league-specific penalty taker hierarchies from Understat-style player logs.

This is meant to keep the penalty-transfer layer usable across leagues even when
we do not yet have a clean manual article like the current Serie A Goal.com page.
The output JSON is intentionally easy to edit by hand afterwards.
"""

from __future__ import annotations

import argparse
import csv
import glob
import html
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "goalscorer"
RECENCY_DECAY = 0.92

LEAGUE_OUTPUT_PREFIX = {
    "serie-a": "serie-a",
    "epl": "epl",
    "la-liga": "la-liga",
    "bundesliga": "bundesliga",
}


def _clean_text(value) -> str:
    text = str(value or "").strip()
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return text


def _safe_int(value, default: int = 0) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


@dataclass
class PenaltyEvent:
    match_date: str
    player_name: str
    attempts: int
    scored: int


def _expand(paths: Iterable[str]) -> List[Path]:
    expanded: List[Path] = []
    for path in paths:
        if "*" in path or "?" in path:
            expanded.extend(Path(item) for item in glob.glob(path))
        else:
            expanded.append(Path(path))
    return [path for path in expanded if path.exists()]


def _default_data_glob(league_key: str) -> str:
    prefix = LEAGUE_OUTPUT_PREFIX[league_key]
    return str(OUTPUT_DIR / f"{prefix}-player-match-logs-*.csv")


def _default_output_path(league_key: str) -> Path:
    prefix = LEAGUE_OUTPUT_PREFIX[league_key]
    return OUTPUT_DIR / f"{prefix}-penalty-takers.json"


def _load_penalty_events(paths: Iterable[Path]) -> tuple[Dict[str, List[PenaltyEvent]], Dict[str, str], set[str]]:
    events_by_team: Dict[str, List[PenaltyEvent]] = defaultdict(list)
    latest_team_label: Dict[str, tuple[str, str]] = {}
    current_season = ""
    current_teams: set[str] = set()

    for path in sorted(paths):
        with path.open("r", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                team = _clean_text(row.get("team"))
                if not team:
                    continue
                match_date = (row.get("match_date") or "").strip()
                if not match_date:
                    continue
                season_label = (row.get("season") or "").strip()
                if season_label:
                    if season_label > current_season:
                        current_season = season_label
                        current_teams = {team}
                    elif season_label == current_season:
                        current_teams.add(team)
                label_pair = latest_team_label.get(team)
                if label_pair is None or match_date >= label_pair[0]:
                    latest_team_label[team] = (match_date, team)

                attempts = _safe_int(row.get("penalties_attempted"), 0)
                if attempts <= 0:
                    continue

                events_by_team[team].append(
                    PenaltyEvent(
                        match_date=match_date,
                        player_name=_clean_text(row.get("player_name")),
                        attempts=attempts,
                        scored=_safe_int(row.get("penalties_scored"), 0),
                    )
                )

    latest_display = {team: value[1] for team, value in latest_team_label.items()}
    return events_by_team, latest_display, current_teams


def _rank_team_hierarchy(events: List[PenaltyEvent]) -> List[str]:
    if not events:
        return []

    ordered = sorted(events, key=lambda item: (item.match_date, item.player_name))
    weighted_attempts: Dict[str, float] = defaultdict(float)
    raw_attempts: Dict[str, int] = defaultdict(int)
    last_date: Dict[str, str] = {}

    for idx, event in enumerate(ordered):
        decay_steps = len(ordered) - 1 - idx
        weight = RECENCY_DECAY ** decay_steps
        weighted_attempts[event.player_name] += event.attempts * weight
        raw_attempts[event.player_name] += event.attempts
        last_date[event.player_name] = max(last_date.get(event.player_name, ""), event.match_date)

    ranked = sorted(
        weighted_attempts,
        key=lambda name: (
            weighted_attempts[name],
            raw_attempts[name],
            last_date.get(name, ""),
            name.lower(),
        ),
        reverse=True,
    )
    return ranked[:3]


def build_hierarchy(paths: Iterable[Path], source_label: str, cross_check: str) -> dict:
    events_by_team, latest_team_label, current_teams = _load_penalty_events(paths)
    last_updated = datetime.now(timezone.utc).date().isoformat()
    output: dict = {}

    target_teams = sorted(current_teams or latest_team_label.keys())
    for team in target_teams:
        ranked = _rank_team_hierarchy(events_by_team.get(team, []))
        output[latest_team_label[team]] = {
            "primary": ranked[0] if len(ranked) > 0 else "",
            "secondary": ranked[1] if len(ranked) > 1 else "",
            "tertiary": ranked[2] if len(ranked) > 2 else "",
            "last_updated": last_updated,
            "source": source_label,
            "cross_check": cross_check,
        }

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build penalty hierarchy JSONs from Understat-style logs")
    parser.add_argument(
        "--league",
        nargs="+",
        default=["serie-a", "epl", "la-liga", "bundesliga"],
        choices=sorted(LEAGUE_OUTPUT_PREFIX),
        help="League key(s) to build",
    )
    parser.add_argument("--data", nargs="+", help="Optional explicit CSV paths or globs")
    parser.add_argument("--out", help="Optional explicit output path (single-league only)")
    parser.add_argument("--source-label", default="understat_weighted_penalties", help="Source label written into JSON")
    parser.add_argument(
        "--cross-check",
        default="manual external verification pending",
        help="Cross-check note written into JSON",
    )
    args = parser.parse_args()

    if args.out and len(args.league) != 1:
        raise SystemExit("--out can only be used with a single --league value")

    for league_key in args.league:
        data_paths = _expand(args.data or [_default_data_glob(league_key)])
        if not data_paths:
            print(f"  Warning: no data files found for {league_key}")
            continue

        hierarchy = build_hierarchy(data_paths, args.source_label, args.cross_check)
        out_path = Path(args.out) if args.out else _default_output_path(league_key)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(hierarchy, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        print(f"  Saved {league_key}: {out_path} ({len(hierarchy):,} teams)")


if __name__ == "__main__":
    main()
