#!/usr/bin/env python3
"""
Settle goalscorer shadow signals using FotMob post-match data.

This is the safer short-term replacement for Understat-based participation
inference. FotMob tells us who appeared and who scored; if that data is missing
or ambiguous, we leave the row pending rather than guessing.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import runpy
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._lib.run_status import run_status

DEFAULT_RESULTS_DIR = ROOT / "data" / "goalscorer" / "match-results"
DEFAULT_ALIAS_PATH = ROOT / "data" / "goalscorer" / "fotmob-player-aliases.json"
SUPER_SUB_BOOKMAKER_TOKENS = {"bet365"}

TEAM_KEY_OVERRIDES = {
    "arsenal fc": "arsenal",
    "burnley fc": "burnley",
    "chelsea fc": "chelsea",
    "liverpool fc": "liverpool",
    "getafe cf": "getafe",
    "rcd mallorca": "mallorca",
    "ca osasuna": "osasuna",
}

TEAM_KEY_DROP_TOKENS = {
    "1",
    "ac",
    "afc",
    "as",
    "bc",
    "ca",
    "cf",
    "cfc",
    "club",
    "de",
    "fc",
    "la",
    "rc",
    "rcd",
    "sc",
    "ss",
    "ud",
    "us",
}


def _goalscorer_settlement_team_key(value: str, base_team_key) -> str:
    key = str(base_team_key(value) or "").strip()
    if key in TEAM_KEY_OVERRIDES:
        return TEAM_KEY_OVERRIDES[key]
    tokens = [token for token in key.split() if token not in TEAM_KEY_DROP_TOKENS]
    compact = " ".join(tokens).strip()
    return TEAM_KEY_OVERRIDES.get(compact, compact or key)


LEAGUE_CONFIGS = {
    "serie-a": {
        "signals": ROOT / "data" / "goalscorer" / "goalscorer-shadow-signals.csv",
        "summary": ROOT / "data" / "goalscorer" / "goalscorer-shadow-performance.txt",
    },
    "epl": {
        "signals": ROOT / "data" / "goalscorer" / "epl-shadow-signals.csv",
        "summary": ROOT / "data" / "goalscorer" / "epl-shadow-performance.txt",
    },
    "la-liga": {
        "signals": ROOT / "data" / "goalscorer" / "la-liga-shadow-signals.csv",
        "summary": ROOT / "data" / "goalscorer" / "la-liga-shadow-performance.txt",
    },
    "bundesliga": {
        "signals": ROOT / "data" / "goalscorer" / "bundesliga-shadow-signals.csv",
        "summary": ROOT / "data" / "goalscorer" / "bundesliga-shadow-performance.txt",
    },
    "ligue-1": {
        "signals": ROOT / "data" / "goalscorer" / "ligue-1-shadow-signals.csv",
        "summary": ROOT / "data" / "goalscorer" / "ligue-1-shadow-performance.txt",
    },
    "wc-2026": {
        "signals": ROOT / "data" / "goalscorer" / "world-cup-2026-shadow-signals.csv",
        "summary": ROOT / "data" / "goalscorer" / "world-cup-2026-shadow-performance.txt",
    },
}


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            raw_line = raw_line.strip()
            if raw_line and not raw_line.startswith("#") and "=" in raw_line:
                key, value = raw_line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _parse_date(value: str) -> Optional[date]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_datetime(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _parse_float(value: Any, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value or "").strip()))
    except (TypeError, ValueError):
        return default


def _load_csv(path: Path) -> tuple[List[dict], List[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_aliases(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    aliases = payload.get("fotmob_aliases", payload) if isinstance(payload, dict) else {}
    return {
        str(key or "").strip(): str(value or "").strip()
        for key, value in aliases.items()
        if str(key or "").strip() and str(value or "").strip()
    }


def _canonical_player_name(row: dict, aliases: Dict[str, str]) -> str:
    for raw_name in (
        row.get("market_player_name"),
        row.get("player"),
    ):
        name = str(raw_name or "").strip()
        if not name:
            continue
        return aliases.get(name, name)
    return ""


def _load_match_results(results_dir: Path, league_key: str, team_key_func) -> Dict[tuple[str, str, str], dict]:
    league_dir = results_dir / league_key
    if not league_dir.exists():
        return {}
    loaded: Dict[tuple[str, str, str], dict] = {}
    for path in sorted(league_dir.glob("fotmob-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        match_date = str(payload.get("match_date") or "").strip()
        home_team = str(payload.get("home_team") or "").strip()
        away_team = str(payload.get("away_team") or "").strip()
        if not match_date or not home_team or not away_team:
            continue
        loaded[(match_date, team_key_func(home_team), team_key_func(away_team))] = payload
        match_id = str(payload.get("match_id") or "").strip()
        if match_id:
            loaded[("fotmob_match_id", match_id, "")] = payload
    return loaded


def _find_team_players(match_result: dict, team_key: str, team_key_func) -> List[dict]:
    players = match_result.get("players") or []
    return [
        player
        for player in players
        if team_key_func(str(player.get("team") or "").strip()) == team_key
    ]


def _complete_team_sheet(team_players: List[dict]) -> bool:
    return len(team_players) >= 14


def _player_name(player: dict) -> str:
    return str(player.get("name") or "").strip()


def _non_own_goal_count(player: dict) -> int:
    return max(_parse_int(player.get("goals")) - _parse_int(player.get("own_goals")), 0)


def _normalise_bookmaker(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def _is_super_sub_eligible_bookmaker(row: dict) -> bool:
    bookmaker = _normalise_bookmaker(row.get("best_bookmaker"))
    return bookmaker in SUPER_SUB_BOOKMAKER_TOKENS


def _settle_super_sub_replacement(
    row: dict,
    *,
    team_players: List[dict],
    player_entry: dict,
) -> tuple[str, str, int] | None:
    """Settle Bet365 Sub On Play On only when the replacement is unambiguous.

    FotMob exposes each player's sub-in/sub-out minute in the match detail we
    archive. We only treat that as a verified direct replacement when exactly
    one player left and exactly one player entered for the same team/minute.
    Multiple substitutions at the same minute stay as normal named-player
    losses because we cannot prove the direct replacement from this source.
    """

    row["super_sub_eligible_bookmaker"] = "1" if _is_super_sub_eligible_bookmaker(row) else "0"
    row["super_sub_checked"] = "0"
    row["super_sub_replacement"] = ""
    row["super_sub_replacement_goals"] = "0"

    if row["super_sub_eligible_bookmaker"] != "1":
        return None
    if not bool(player_entry.get("subbed_off")):
        return None

    sub_out_minute = _parse_int(player_entry.get("sub_out_minute"))
    if sub_out_minute <= 0:
        return None

    outgoing = [
        player
        for player in team_players
        if bool(player.get("subbed_off")) and _parse_int(player.get("sub_out_minute")) == sub_out_minute
    ]
    incoming = [
        player
        for player in team_players
        if bool(player.get("subbed_on")) and _parse_int(player.get("sub_in_minute")) == sub_out_minute
    ]
    row["super_sub_checked"] = "1"

    if len(outgoing) != 1 or len(incoming) != 1:
        return None

    replacement = incoming[0]
    replacement_name = _player_name(replacement)
    replacement_goals = _non_own_goal_count(replacement)
    row["super_sub_replacement"] = replacement_name
    row["super_sub_replacement_goals"] = str(replacement_goals)

    if replacement_goals > 0:
        return "won", f"super_sub_replacement_scored:{replacement_name}", replacement_goals
    return None


def _has_complete_finished_fallback(match_result: dict, home_team_key: str, away_team_key: str, team_key_func) -> bool:
    home_score = match_result.get("home_score")
    away_score = match_result.get("away_score")
    if home_score is None or away_score is None:
        return False
    home_players = _find_team_players(match_result, home_team_key, team_key_func)
    away_players = _find_team_players(match_result, away_team_key, team_key_func)
    return _complete_team_sheet(home_players) and _complete_team_sheet(away_players)


def settle_row(
    row: dict,
    *,
    match_results: Dict[tuple[str, str, str], dict],
    best_name_match,
    team_key_func,
    aliases: Dict[str, str],
    now_utc: datetime,
) -> tuple[str, str, int]:
    signal_date = _parse_date(row.get("date") or "")
    kickoff = _parse_datetime(row.get("kickoff") or row.get("date") or "")
    if signal_date is None:
        return "pending", "invalid_signal_date", 0
    if kickoff is not None and kickoff > now_utc:
        return "skip", "match_not_yet_played", 0
    if signal_date >= now_utc.date() and kickoff is None:
        return "skip", "match_not_yet_played", 0

    match_key = (
        (row.get("date") or "").strip(),
        team_key_func(row.get("home_team") or ""),
        team_key_func(row.get("away_team") or ""),
    )
    match_result = match_results.get(match_key)
    if match_result is None:
        fotmob_match_id = str(row.get("fotmob_match_id") or "").strip()
        if fotmob_match_id:
            match_result = match_results.get(("fotmob_match_id", fotmob_match_id, ""))
    if match_result is None:
        if kickoff is not None and kickoff + timedelta(hours=6) <= now_utc:
            return "pending", "pending_settlement_data", 0
        if signal_date < now_utc.date():
            return "pending", "pending_settlement_data", 0
        return "skip", "match_result_not_found", 0

    home_team_key = team_key_func(row.get("home_team") or "")
    away_team_key = team_key_func(row.get("away_team") or "")
    match_finished = bool(match_result.get("status_finished")) or _has_complete_finished_fallback(
        match_result,
        home_team_key,
        away_team_key,
        team_key_func,
    )

    if not match_finished:
        if match_result.get("status_cancelled"):
            return "pending", "match_cancelled_or_postponed", 0
        return "pending", "match_not_finished", 0

    player_team_key = team_key_func(row.get("team") or "")
    team_players = _find_team_players(match_result, player_team_key, team_key_func)
    if not team_players:
        return "pending", "missing_team_sheet", 0

    player_name = _canonical_player_name(row, aliases)
    candidate_names = [str(player.get("name") or "").strip() for player in team_players if str(player.get("name") or "").strip()]
    matched_name = best_name_match(player_name, candidate_names, minimum_score=76) if player_name else None
    if not matched_name:
        if _complete_team_sheet(team_players):
            return "void", "not_in_matchday_squad", 0
        return "pending", "incomplete_team_sheet", 0

    player_entry = next(
        (player for player in team_players if str(player.get("name") or "").strip() == matched_name),
        None,
    )
    if player_entry is None:
        return "pending", "pending_player_name_match", 0

    minutes_played = int(player_entry.get("minutes_played") or 0)
    subbed_on = bool(player_entry.get("subbed_on"))
    squad_status = str(player_entry.get("squad_status") or "").strip().lower()
    if minutes_played <= 0 and not subbed_on:
        if squad_status == "sub":
            return "void", "unused_substitute", 0
        if squad_status == "unavailable":
            return "void", "not_in_matchday_squad", 0
        return "void", "confirmed_non_runner", 0

    non_og_goals = _non_own_goal_count(player_entry)

    if non_og_goals > 0:
        return "won", f"scored_{non_og_goals}_goals", non_og_goals

    super_sub_result = _settle_super_sub_replacement(
        row,
        team_players=team_players,
        player_entry=player_entry,
    )
    if super_sub_result is not None:
        return super_sub_result
    if row.get("super_sub_checked") == "1":
        replacement = str(row.get("super_sub_replacement") or "").strip()
        if replacement:
            return "lost", f"played_did_not_score_super_sub_checked:{replacement}", 0
        return "lost", "played_did_not_score_super_sub_ambiguous", 0
    return "lost", "played_did_not_score", 0


def write_summary(summary_path: Path, signals_path: Path) -> None:
    tracker_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-shadow-tracker.py"), run_name="goalscorer_shadow_tracker")
    tracker_mod["write_summary"](summary_path, signals_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Settle goalscorer shadow rows from FotMob match detail")
    parser.add_argument("--league", choices=sorted(LEAGUE_CONFIGS), required=True, help="League key")
    parser.add_argument("--signals", default="", help="Shadow signals CSV path")
    parser.add_argument("--summary", default="", help="Shadow summary TXT path")
    parser.add_argument("--match-results-dir", default=str(DEFAULT_RESULTS_DIR), help="Directory of FotMob match result JSON files")
    parser.add_argument("--alias-path", default=str(DEFAULT_ALIAS_PATH), help="Optional alias JSON path")
    args = parser.parse_args()

    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    base_team_key_func = model_mod["_team_key"]

    def team_key_func(value: str) -> str:
        return _goalscorer_settlement_team_key(value, base_team_key_func)

    penalty_utils = runpy.run_path(str(ROOT / "scripts" / "goalscorer_penalty_utils.py"), run_name="goalscorer_penalty_utils")
    best_name_match = penalty_utils["best_name_match"]
    tracker_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-shadow-tracker.py"), run_name="goalscorer_shadow_tracker")
    output_fields = list(tracker_mod["OUTPUT_FIELDS"])

    config = LEAGUE_CONFIGS[args.league]
    signals_path = Path(args.signals) if args.signals else config["signals"]
    summary_path = Path(args.summary) if args.summary else config["summary"]
    results_dir = Path(args.match_results_dir)
    aliases = _load_aliases(Path(args.alias_path))

    rows, fieldnames = _load_csv(signals_path)
    if not fieldnames:
        fieldnames = output_fields
    else:
        for field in output_fields:
            if field not in fieldnames:
                fieldnames.append(field)

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer FotMob Settler")
    print("=" * 64)
    print(f"  League:               {args.league}")
    print(f"  Signals:              {signals_path}")

    if not rows:
        _write_csv(signals_path, [], fieldnames)
        write_summary(summary_path, signals_path)
        print("  No rows found. Wrote empty files.")
        print("\n  Done.\n")
        return 0

    match_results = _load_match_results(results_dir, args.league, team_key_func)
    now_utc = datetime.now(timezone.utc)
    settled_now = 0
    already_settled = 0
    pending = 0
    still_open = 0

    for row in rows:
        if str(row.get("settled") or "").strip().lower() in {"1", "true", "yes", "settled"}:
            already_settled += 1
            continue

        outcome, note, goals_scored = settle_row(
            row,
            match_results=match_results,
            best_name_match=best_name_match,
            team_key_func=team_key_func,
            aliases=aliases,
            now_utc=now_utc,
        )
        if outcome == "skip":
            still_open += 1
            continue
        if outcome == "pending":
            row["settlement_note"] = note
            pending += 1
            continue

        odds = _parse_float(row.get("best_bookmaker_odds"))
        stake_units = _parse_float(row.get("evaluation_stake_units") or row.get("recommended_stake_units"))
        if stake_units <= 0.0:
            stake_units = 1.0
        pnl_units = 0.0 if outcome == "void" else ((stake_units * (odds - 1.0)) if outcome == "won" else -stake_units)
        row["settled"] = "1"
        row["goals_scored"] = str(goals_scored)
        row["bet_outcome"] = outcome
        row["settled_at"] = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        row["pnl_units"] = f"{pnl_units:.4f}"
        row["settlement_note"] = note
        settled_now += 1

    _write_csv(signals_path, rows, fieldnames)
    write_summary(summary_path, signals_path)

    print(f"  Match result files:   {len(match_results):,}")
    print(f"  Settled now:          {settled_now:,}")
    print(f"  Already settled:      {already_settled:,}")
    print(f"  Pending:              {pending:,}")
    print(f"  Still open:           {still_open:,}")
    print(f"  Saved:                {signals_path}")
    print(f"  Saved:                {summary_path}")
    print("\n  Done.\n")
    return settled_now


if __name__ == "__main__":
    load_env()
    with run_status("goalscorer-settle", trigger_kind="schedule") as rs:
        rs.rows_out = main()
