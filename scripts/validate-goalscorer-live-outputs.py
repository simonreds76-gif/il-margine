#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local goalscorer live output contracts.")
    parser.add_argument("--league", default="", help="League label for logging")
    parser.add_argument("--live-board", required=True, help="League live-board.json path")
    parser.add_argument("--lineups", default="", help="Lineups JSON path")
    parser.add_argument("--merged-live-board", default="", help="Merged all-leagues live board JSON path")
    return parser.parse_args()


def load_json(path_str: str) -> Any:
    path = Path(path_str)
    if not path.exists():
        raise ValueError(f"Missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def require_mapping(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def require_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{label}.{key} must be a list")
    return value


def require_nonempty_string(payload: dict[str, Any], key: str, label: str) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be a non-empty string")


def require_integerish(payload: dict[str, Any], key: str, label: str) -> None:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{label}.{key} must be an integer")


def validate_live_board(path_str: str, label: str) -> list[str]:
    payload = require_mapping(load_json(path_str), label)
    require_integerish(payload, "schema_version", label)
    require_nonempty_string(payload, "generated_at", label)
    rows = require_list(payload, "rows", label)
    fixtures = require_list(payload, "fixtures", label)
    require_integerish(payload, "row_count", label)

    if payload["row_count"] != len(rows):
        raise ValueError(f"{label}.row_count ({payload['row_count']}) does not match rows length ({len(rows)})")

    if rows:
        first_row = require_mapping(rows[0], f"{label}.rows[0]")
        for key in ("match_date", "bookmaker", "competition", "home_team", "away_team", "player_name"):
            require_nonempty_string(first_row, key, f"{label}.rows[0]")

    if fixtures:
        first_fixture = require_mapping(fixtures[0], f"{label}.fixtures[0]")
        for key in ("match_date", "home_team", "away_team", "trust_tier"):
            require_nonempty_string(first_fixture, key, f"{label}.fixtures[0]")

    return [
        f"{label}: rows={len(rows)} fixtures={len(fixtures)} generated_at={payload['generated_at']}",
    ]


def validate_lineups(path_str: str, label: str) -> list[str]:
    payload = require_mapping(load_json(path_str), label)
    fixtures = require_list(payload, "fixtures", label)

    if not fixtures:
        return [f"{label}: fixtures=0"]

    first_fixture = require_mapping(fixtures[0], f"{label}.fixtures[0]")
    for key in ("match_date", "home_team", "away_team", "home_status", "away_status", "lineup_type"):
        require_nonempty_string(first_fixture, key, f"{label}.fixtures[0]")

    home_starters = first_fixture.get("home_starters")
    away_starters = first_fixture.get("away_starters")
    home_players = first_fixture.get("home_players")
    away_players = first_fixture.get("away_players")
    if not any(
        isinstance(value, list) and len(value) > 0
        for value in (home_starters, away_starters, home_players, away_players)
    ):
        raise ValueError(f"{label}.fixtures[0] must include players or starter entries")

    return [f"{label}: fixtures={len(fixtures)} first_lineup_type={first_fixture.get('lineup_type')}"]


def validate_merged_live_board(path_str: str, label: str) -> list[str]:
    payload = require_mapping(load_json(path_str), label)
    require_integerish(payload, "schema_version", label)
    require_nonempty_string(payload, "generated_at", label)
    leagues = require_list(payload, "leagues", label)
    rows = require_list(payload, "rows", label)
    require_integerish(payload, "league_count", label)
    require_integerish(payload, "row_count", label)

    if payload["league_count"] != len(leagues):
        raise ValueError(f"{label}.league_count ({payload['league_count']}) does not match leagues length ({len(leagues)})")
    if payload["row_count"] != len(rows):
        raise ValueError(f"{label}.row_count ({payload['row_count']}) does not match rows length ({len(rows)})")

    if leagues:
        first_league = require_mapping(leagues[0], f"{label}.leagues[0]")
        for key in ("league", "label", "path"):
            require_nonempty_string(first_league, key, f"{label}.leagues[0]")
        if not isinstance(first_league.get("row_count"), int):
            raise ValueError(f"{label}.leagues[0].row_count must be an integer")

    return [f"{label}: leagues={len(leagues)} rows={len(rows)} generated_at={payload['generated_at']}"]


def main() -> int:
    args = parse_args()
    prefix = f"[{args.league}] " if args.league else ""
    messages: list[str] = []

    try:
        messages.extend(validate_live_board(args.live_board, "live_board"))
        if args.lineups:
            messages.extend(validate_lineups(args.lineups, "lineups"))
        if args.merged_live_board:
            messages.extend(validate_merged_live_board(args.merged_live_board, "merged_live_board"))
    except ValueError as exc:
        print(f"{prefix}Goalscorer live output validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"{prefix}Goalscorer live output validation passed.")
    for message in messages:
        print(f"  {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
