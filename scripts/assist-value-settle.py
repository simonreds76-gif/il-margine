#!/usr/bin/env python3
"""Settle Assist Value shadow signals from FotMob match-detail results.

The assist lane is still shadow-only, but a shadow signal without settlement is
just decoration. This script uses the same FotMob result layer as goalscorer
settlement, with the assist fields preserved by fotmob-fetch-match-detail.py.
Rows are left pending rather than guessed when match/player data is missing.
"""

from __future__ import annotations

import argparse
import csv
import json
import runpy
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._lib.run_status import run_status


DEFAULT_SIGNALS = ROOT / "data" / "assist-value" / "assist-value-shadow-signals.csv"
DEFAULT_SUMMARY = ROOT / "data" / "assist-value" / "assist-value-shadow-performance.txt"
DEFAULT_RESULTS_DIR = ROOT / "data" / "goalscorer" / "match-results"
DEFAULT_ALIAS_PATH = ROOT / "data" / "goalscorer" / "fotmob-player-aliases.json"

OUTPUT_FIELDS = [
    "settled",
    "assists_recorded",
    "bet_outcome",
    "settled_at",
    "pnl_units",
    "settlement_note",
]

SETTLEMENT_REVIEW_NOTE = (
    "Assist settlement is under review after the 2026-05-30 model-risk audit; "
    "use --resettle after refreshing FotMob assist payloads before trusting ROI."
)

TEAM_KEY_OVERRIDES = {
    "fc metz": "metz",
    "getafe cf": "getafe",
    "olympique lyon": "lyon",
    "olympique lyonnais": "lyon",
    "rc lens": "lens",
}

TEAM_KEY_DROP_TOKENS = {
    "ac",
    "afc",
    "as",
    "bc",
    "cf",
    "cfc",
    "club",
    "de",
    "fc",
    "la",
    "ogc",
    "olympique",
    "racing",
    "rc",
    "sc",
    "ss",
    "ud",
    "us",
}


def _assist_settlement_team_key(value: str, base_team_key) -> str:
    """Use goalscorer aliases first, then tolerate bookmaker/FotMob affixes."""
    key = str(base_team_key(value) or "").strip()
    if key in TEAM_KEY_OVERRIDES:
        return TEAM_KEY_OVERRIDES[key]
    tokens = [token for token in key.split() if token not in TEAM_KEY_DROP_TOKENS]
    compact = " ".join(tokens).strip()
    return TEAM_KEY_OVERRIDES.get(compact, compact or key)


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
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    aliases = payload.get("fotmob_aliases", payload) if isinstance(payload, dict) else {}
    return {
        str(key or "").strip(): str(value or "").strip()
        for key, value in aliases.items()
        if str(key or "").strip() and str(value or "").strip()
    }


def _canonical_player_name(row: dict, aliases: Dict[str, str]) -> str:
    name = str(row.get("player_name") or "").strip()
    return aliases.get(name, name)


def _load_match_results(results_dir: Path, team_key_func) -> Dict[tuple[str, str, str, str], dict]:
    loaded: Dict[tuple[str, str, str, str], dict] = {}
    if not results_dir.exists():
        return loaded
    for path in sorted(results_dir.glob("*/fotmob-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        league_key = str(payload.get("league") or path.parent.name).strip()
        match_date = str(payload.get("match_date") or "").strip()
        home_team = str(payload.get("home_team") or "").strip()
        away_team = str(payload.get("away_team") or "").strip()
        if not league_key or not match_date or not home_team or not away_team:
            continue
        loaded[(league_key, match_date, team_key_func(home_team), team_key_func(away_team))] = payload
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


def _has_complete_finished_fallback(match_result: dict, home_team_key: str, away_team_key: str, team_key_func) -> bool:
    home_score = match_result.get("home_score")
    away_score = match_result.get("away_score")
    if home_score is None or away_score is None:
        return False
    home_players = _find_team_players(match_result, home_team_key, team_key_func)
    away_players = _find_team_players(match_result, away_team_key, team_key_func)
    return _complete_team_sheet(home_players) and _complete_team_sheet(away_players)


def _has_trustworthy_assist_data(match_result: dict) -> bool:
    players = match_result.get("players") or []
    if not any(isinstance(player, dict) and "assists" in player for player in players):
        return False
    if "assist_data_complete" in match_result:
        return bool(match_result.get("assist_data_complete"))
    # Legacy fixed payloads had assist_events but no completeness marker.
    return "assist_events" in match_result


def settle_row(
    row: dict,
    *,
    match_results: Dict[tuple[str, str, str, str], dict],
    best_name_match,
    team_key_func,
    aliases: Dict[str, str],
    now_utc: datetime,
) -> tuple[str, str, int]:
    if str(row.get("signal_status") or "").strip() != "shadow_signal":
        return "skip", "not_a_shadow_signal", 0

    signal_date = _parse_date(row.get("match_date") or "")
    kickoff = _parse_datetime(row.get("kickoff_at") or row.get("match_date") or "")
    if signal_date is None:
        return "pending", "invalid_signal_date", 0
    if kickoff is not None and kickoff > now_utc:
        return "skip", "match_not_yet_played", 0
    if signal_date >= now_utc.date() and kickoff is None:
        return "skip", "match_not_yet_played", 0

    league_key = str(row.get("league_key") or "").strip()
    home_team_key = team_key_func(row.get("home_team") or "")
    away_team_key = team_key_func(row.get("away_team") or "")
    match_key = (league_key, (row.get("match_date") or "").strip(), home_team_key, away_team_key)
    match_result = match_results.get(match_key)
    if match_result is None:
        if kickoff is not None and kickoff + timedelta(hours=6) <= now_utc:
            return "pending", "pending_settlement_data", 0
        if signal_date < now_utc.date():
            return "pending", "pending_settlement_data", 0
        return "skip", "match_result_not_found", 0

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

    player_team_key = team_key_func(row.get("player_team") or "")
    if player_team_key not in {home_team_key, away_team_key}:
        return "pending", "player_team_does_not_match_fixture", 0

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

    if not _has_trustworthy_assist_data(match_result):
        return "pending", "needs_assist_data", 0

    assists = int(player_entry.get("assists") or 0)
    if assists > 0:
        return "won", f"assisted_{assists}_goals", assists
    return "lost", "played_no_assist", 0


def _summary_stats(rows: List[dict]) -> dict:
    signal_rows = [row for row in rows if str(row.get("signal_status") or "").strip() == "shadow_signal"]
    settled_rows = [row for row in signal_rows if str(row.get("settled") or "").strip().lower() in {"1", "true", "yes"}]
    won = [row for row in settled_rows if row.get("bet_outcome") == "won"]
    lost = [row for row in settled_rows if row.get("bet_outcome") == "lost"]
    void = [row for row in settled_rows if row.get("bet_outcome") == "void"]
    pnl = sum(_parse_float(row.get("pnl_units")) for row in settled_rows)
    stake = float(len(won) + len(lost))
    roi = (pnl / stake * 100.0) if stake > 0 else 0.0
    pending = len([row for row in signal_rows if row not in settled_rows])
    return {
        "signals": len(signal_rows),
        "settled": len(settled_rows),
        "pending": pending,
        "won": len(won),
        "lost": len(lost),
        "void": len(void),
        "pnl_units": pnl,
        "stake_units": stake,
        "roi_pct": roi,
    }


def write_summary(summary_path: Path, rows: List[dict], *, now_utc: datetime) -> None:
    stats = _summary_stats(rows)
    lines = [
        "Assist Value Shadow Performance",
        f"generated_at_utc: {now_utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z')}",
        "",
        "Status",
        "lane_status: SHADOW_ONLY",
        "public_status: NOT_PUBLIC",
        "settlement_source: fotmob_match_detail_assist_events",
        "settlement_validation: UNDER_REVIEW",
        "settlement_valid_for_roi: false",
        "",
        "Summary",
        f"shadow_signals: {stats['signals']}",
        f"settled: {stats['settled']}",
        f"pending: {stats['pending']}",
        f"won: {stats['won']}",
        f"lost: {stats['lost']}",
        f"void: {stats['void']}",
        f"stake_units: {stats['stake_units']:.2f}",
        f"pnl_units: {stats['pnl_units']:.4f}",
        f"roi_pct: {stats['roi_pct']:.2f}",
        "",
        "Notes",
        "Only rows with signal_status=shadow_signal count in this ledger.",
        "Rows with missing FotMob/player data stay pending rather than guessed.",
        SETTLEMENT_REVIEW_NOTE,
    ]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Settle Assist Value shadow signals from FotMob assist events")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS), help="Assist shadow signals CSV path")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="Assist shadow performance TXT path")
    parser.add_argument("--match-results-dir", default=str(DEFAULT_RESULTS_DIR), help="Directory of FotMob match result JSON files")
    parser.add_argument("--alias-path", default=str(DEFAULT_ALIAS_PATH), help="Optional FotMob player alias JSON path")
    parser.add_argument("--resettle", action="store_true", help="Recompute existing settled shadow rows from current FotMob assist payloads")
    parser.add_argument("--dry-run", action="store_true", help="Print the settlement summary without writing CSV/report files")
    args = parser.parse_args()

    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    base_team_key_func = model_mod["_team_key"]

    def team_key_func(value: str) -> str:
        return _assist_settlement_team_key(value, base_team_key_func)
    penalty_utils = runpy.run_path(str(ROOT / "scripts" / "goalscorer_penalty_utils.py"), run_name="goalscorer_penalty_utils")
    best_name_match = penalty_utils["best_name_match"]

    signals_path = Path(args.signals)
    summary_path = Path(args.summary)
    rows, fieldnames = _load_csv(signals_path)
    for field in OUTPUT_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)

    print("\n" + "=" * 64)
    print("  IL MARGINE - Assist Value FotMob Settler")
    print("=" * 64)
    print(f"  Signals:              {signals_path}")

    now_utc = datetime.now(timezone.utc)
    if not rows:
        _write_csv(signals_path, [], fieldnames)
        write_summary(summary_path, [], now_utc=now_utc)
        print("  No rows found. Wrote empty files.")
        print("\n  Done.\n")
        return 0

    aliases = _load_aliases(Path(args.alias_path))
    match_results = _load_match_results(Path(args.match_results_dir), team_key_func)
    settled_now = 0
    already_settled = 0
    pending = 0
    still_open = 0
    non_signal_rows = 0

    for row in rows:
        if str(row.get("settled") or "").strip().lower() in {"1", "true", "yes", "settled"} and not args.resettle:
            already_settled += 1
            continue

        outcome, note, assists_recorded = settle_row(
            row,
            match_results=match_results,
            best_name_match=best_name_match,
            team_key_func=team_key_func,
            aliases=aliases,
            now_utc=now_utc,
        )
        if outcome == "skip":
            if note == "not_a_shadow_signal":
                non_signal_rows += 1
            else:
                still_open += 1
            continue
        if outcome == "pending":
            row["settled"] = ""
            row["assists_recorded"] = ""
            row["bet_outcome"] = ""
            row["settled_at"] = ""
            row["pnl_units"] = ""
            row["settlement_note"] = note
            pending += 1
            continue

        odds = _parse_float(row.get("market_odds") or row.get("odds_decimal"))
        stake_units = _parse_float(row.get("stake_units"), 1.0)
        if stake_units <= 0.0:
            stake_units = 1.0
        pnl_units = 0.0 if outcome == "void" else ((stake_units * (odds - 1.0)) if outcome == "won" else -stake_units)
        row["settled"] = "1"
        row["assists_recorded"] = str(assists_recorded)
        row["bet_outcome"] = outcome
        row["settled_at"] = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        row["pnl_units"] = f"{pnl_units:.4f}"
        row["settlement_note"] = note
        settled_now += 1

    if not args.dry_run:
        _write_csv(signals_path, rows, fieldnames)
        write_summary(summary_path, rows, now_utc=now_utc)

    print(f"  Match result files:   {len(match_results):,}")
    print(f"  Settled now:          {settled_now:,}")
    print(f"  Already settled:      {already_settled:,}")
    print(f"  Pending:              {pending:,}")
    print(f"  Still open:           {still_open:,}")
    print(f"  Non-signal rows:      {non_signal_rows:,}")
    if args.dry_run:
        print("  Dry run:              CSV/report not written")
    else:
        print(f"  Saved:                {signals_path}")
        print(f"  Saved:                {summary_path}")
    print("\n  Done.\n")
    return settled_now


if __name__ == "__main__":
    with run_status("assist-value-settle", trigger_kind="schedule") as rs:
        rs.rows_out = main()
