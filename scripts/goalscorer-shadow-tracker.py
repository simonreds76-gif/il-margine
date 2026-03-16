#!/usr/bin/env python3
"""
Append and settle private goalscorer shadow signals.

This is the goalscorer equivalent of the tennis strict shadow tracking:
  - read the latest live comparison output
  - apply the selective stacked-signal filters
  - append one row per qualifying player-match
  - settle older rows from Understat-style player logs
  - write a compact performance summary
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
import runpy
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIVE_COMPARE = ROOT / "data" / "goalscorer" / "goalscorer-live-comparison.csv"
DEFAULT_ODDS_ARCHIVE = ROOT / "data" / "goalscorer" / "goalscorer-odds-history.csv"
DEFAULT_SIGNALS = ROOT / "data" / "goalscorer" / "goalscorer-shadow-signals.csv"
DEFAULT_SUMMARY = ROOT / "data" / "goalscorer" / "goalscorer-shadow-performance.txt"
DEFAULT_DATA = [
    "data/goalscorer/serie-a-player-match-logs-2023-2024.csv",
    "data/goalscorer/serie-a-player-match-logs-2024-2025.csv",
    "data/goalscorer/serie-a-player-match-logs-2025-2026.csv",
]

ATTACKING_POSITIONS = {"FW", "FWL", "FWR", "AMC", "AML", "AMR"}
CLEAN_EVAL_START = date(2026, 3, 15)
STACKED_MAX_FINISHING_LUCK = -0.50
STACKED_MIN_FIXTURE_SWING = 1.2
STACKED_MIN_BEST_EV = 0.08
TRANSFER_MIN_BEST_EV = 0.05
REQUIRED_LINEUP_STATE = "starter"
REQUIRED_CONFIDENCE = "high"

OUTPUT_FIELDS = [
    "date",
    "kickoff",
    "match",
    "competition",
    "player",
    "team",
    "opponent",
    "signal_type",
    "finishing_luck",
    "fixture_swing",
    "penalty_transfer",
    "penalty_transfer_from",
    "position_upgrade",
    "lineup_state",
    "model_p_atgs",
    "model_fair_odds",
    "best_bookmaker",
    "best_bookmaker_odds",
    "ev",
    "confidence",
    "compared_at",
    "player_id",
    "market_player_name",
    "home_team",
    "away_team",
    "position_group",
    "settled",
    "goals_scored",
    "bet_outcome",
    "settled_at",
    "pnl_units",
    "settlement_note",
]


def _norm_text(value: str) -> str:
    normalized = html.unescape((value or "").strip().lower())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_float(value: Any, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


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
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_csv(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _dedupe_key(row: dict) -> tuple[str, str, str]:
    return (
        (row.get("date") or "").strip(),
        _norm_text(row.get("player") or ""),
        _norm_text(row.get("match") or ""),
    )


def _best_row_key(row: dict) -> tuple[str, str, str, str]:
    return (
        (row.get("match_date") or "").strip(),
        _norm_text(row.get("home_team") or ""),
        _norm_text(row.get("away_team") or ""),
        _norm_text(row.get("player_name") or ""),
    )


def _signal_row_key(row: dict) -> tuple[str, str, str, str]:
    return (
        (row.get("match_date") or "").strip(),
        _norm_text(row.get("home_team") or ""),
        _norm_text(row.get("away_team") or ""),
        _norm_text(row.get("market_player_name") or row.get("player_name") or ""),
    )


def dedupe_live_rows(rows: List[dict]) -> List[dict]:
    best: Dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        key = _best_row_key(row)
        current = best.get(key)
        if current is None or _parse_float(row.get("odds_decimal")) > _parse_float(current.get("odds_decimal")):
            best[key] = row
    return list(best.values())


def build_best_price_lookup(archive_rows: List[dict]) -> Dict[tuple[str, str, str, str], List[dict]]:
    grouped: Dict[tuple[str, str, str, str], List[dict]] = defaultdict(list)
    for row in archive_rows:
        if (row.get("market") or "").strip().upper() != "ATGS":
            continue
        if _parse_float(row.get("odds_decimal")) <= 1.0:
            continue
        grouped[_best_row_key(row)].append(row)

    for rows in grouped.values():
        rows.sort(key=lambda row: (row.get("captured_at") or "", row.get("bookmaker") or ""))
    return grouped


def resolve_best_price(signal_row: dict, archive_lookup: Dict[tuple[str, str, str, str], List[dict]]) -> dict:
    key = _signal_row_key(signal_row)
    candidates = archive_lookup.get(key, [])
    compared_at = signal_row.get("compared_at") or ""
    per_bookmaker: Dict[str, dict] = {}
    for candidate in candidates:
        captured_at = candidate.get("captured_at") or ""
        bookmaker = (candidate.get("bookmaker") or "").strip()
        if compared_at and captured_at and captured_at > compared_at:
            continue
        current = per_bookmaker.get(bookmaker)
        if current is None or captured_at > (current.get("captured_at") or ""):
            per_bookmaker[bookmaker] = candidate

    if not per_bookmaker:
        bookmaker = (signal_row.get("bookmaker") or "").strip()
        odds_decimal = _parse_float(signal_row.get("odds_decimal"))
        return {
            "bookmaker": bookmaker,
            "odds_decimal": odds_decimal,
            "kickoff_at": signal_row.get("kickoff_at", "") or signal_row.get("match_date", ""),
            "captured_at": signal_row.get("captured_at", ""),
        }

    best_row = max(per_bookmaker.values(), key=lambda row: _parse_float(row.get("odds_decimal")))
    return {
        "bookmaker": (best_row.get("bookmaker") or "").strip(),
        "odds_decimal": _parse_float(best_row.get("odds_decimal")),
        "kickoff_at": (best_row.get("kickoff_at") or "").strip(),
        "captured_at": (best_row.get("captured_at") or "").strip(),
    }


def qualify_signal(row: dict, best_price: dict) -> tuple[bool, str]:
    if (row.get("signal_confidence") or "").strip().lower() != REQUIRED_CONFIDENCE:
        return False, ""
    if (row.get("lineup_state") or "").strip().lower() != REQUIRED_LINEUP_STATE:
        return False, ""

    position_group = (row.get("position_group") or "").strip()
    finishing_luck = _parse_float(row.get("finishing_luck_8"))
    fixture_swing = _parse_float(row.get("fixture_swing_3"))
    model_prob = _parse_float(row.get("model_p_atgs"))
    best_odds = _parse_float(best_price.get("odds_decimal"))
    best_ev = (model_prob * best_odds) - 1.0 if best_odds > 1.0 else 0.0
    penalty_transfer = str(row.get("penalty_transfer") or "").strip() in {"1", "true", "True"}
    recent_matches = int(_parse_float(row.get("recent_matches_8")))

    stacked = (
        position_group in ATTACKING_POSITIONS
        and recent_matches >= 8
        and finishing_luck <= STACKED_MAX_FINISHING_LUCK
        and fixture_swing >= STACKED_MIN_FIXTURE_SWING
        and best_ev >= STACKED_MIN_BEST_EV
    )
    transfer = penalty_transfer and best_ev >= TRANSFER_MIN_BEST_EV

    if stacked and transfer:
        return True, "both"
    if stacked:
        return True, "stacked"
    if transfer:
        return True, "penalty_transfer"
    return False, ""


def build_shadow_rows(live_rows: List[dict], archive_lookup: Dict[tuple[str, str, str, str], List[dict]]) -> List[dict]:
    output: List[dict] = []
    for row in dedupe_live_rows(live_rows):
        best_price = resolve_best_price(row, archive_lookup)
        qualifies, signal_type = qualify_signal(row, best_price)
        if not qualifies:
            continue

        model_prob = _parse_float(row.get("model_p_atgs"))
        fair_odds = _parse_float(row.get("model_fair_odds_atgs"))
        best_odds = _parse_float(best_price.get("odds_decimal"))
        best_ev = (model_prob * best_odds) - 1.0 if best_odds > 1.0 else 0.0
        home_team = (row.get("home_team") or "").strip()
        away_team = (row.get("away_team") or "").strip()
        canonical_player = (row.get("canonical_player_name") or row.get("player_name") or "").strip()

        output.append(
            {
                "date": (row.get("match_date") or "").strip(),
                "kickoff": (best_price.get("kickoff_at") or row.get("match_date") or "").strip(),
                "match": f"{home_team} vs {away_team}",
                "competition": (row.get("competition") or "").strip(),
                "player": canonical_player,
                "team": (row.get("player_team") or "").strip(),
                "opponent": (row.get("opponent") or "").strip(),
                "signal_type": signal_type,
                "finishing_luck": f"{_parse_float(row.get('finishing_luck_8')):.4f}",
                "fixture_swing": f"{_parse_float(row.get('fixture_swing_3')):.4f}",
                "penalty_transfer": "1" if str(row.get("penalty_transfer") or "").strip() in {"1", "true", "True"} else "0",
                "penalty_transfer_from": (row.get("penalty_transfer_from") or "").strip(),
                "position_upgrade": "1" if str(row.get("position_upgrade") or "").strip() in {"1", "true", "True"} else "0",
                "lineup_state": (row.get("lineup_state") or "").strip(),
                "model_p_atgs": f"{model_prob:.6f}",
                "model_fair_odds": f"{fair_odds:.4f}",
                "best_bookmaker": (best_price.get("bookmaker") or "").strip(),
                "best_bookmaker_odds": f"{best_odds:.4f}",
                "ev": f"{best_ev:.6f}",
                "confidence": (row.get("signal_confidence") or "").strip(),
                "compared_at": (row.get("compared_at") or "").strip(),
                "player_id": (row.get("player_id") or "").strip(),
                "market_player_name": (row.get("player_name") or "").strip(),
                "home_team": home_team,
                "away_team": away_team,
                "position_group": (row.get("position_group") or "").strip(),
                "settled": "",
                "goals_scored": "",
                "bet_outcome": "",
                "settled_at": "",
                "pnl_units": "",
                "settlement_note": "",
            }
        )
    return output


def append_rows_dedup(path: Path, rows: List[dict]) -> int:
    existing_rows = _load_csv(path)
    existing_by_key = {_dedupe_key(row): row for row in existing_rows}
    added = 0
    for row in rows:
        key = _dedupe_key(row)
        if key in existing_by_key:
            continue
        existing_by_key[key] = {field: row.get(field, "") for field in OUTPUT_FIELDS}
        added += 1

    merged = list(existing_by_key.values())
    merged.sort(key=lambda row: ((row.get("date") or ""), (row.get("match") or ""), (row.get("player") or "")))
    _write_csv(path, merged, OUTPUT_FIELDS)
    return added


def settle_rows(path: Path, data_paths: Iterable[str]) -> dict:
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    load_match_logs = model_mod["load_match_logs"]
    team_key_func = model_mod["_team_key"]

    rows = _load_csv(path)
    if not rows:
        _write_csv(path, [], OUTPUT_FIELDS)
        return {"settled_now": 0, "already_settled": 0, "pending": 0}

    historical_rows = load_match_logs(list(data_paths))
    lookup_by_player_id: Dict[tuple[str, str, str, str], Any] = {}
    lookup_by_name: Dict[tuple[str, str, str, str], Any] = {}
    for row in historical_rows:
        team_key = team_key_func(row.team)
        opp_key = team_key_func(row.opponent)
        lookup_by_player_id[(row.match_date_str, row.player_id, team_key, opp_key)] = row
        lookup_by_name[(row.match_date_str, _norm_text(row.player_name), team_key, opp_key)] = row

    today = datetime.now(timezone.utc).date()
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    settled_now = 0
    already_settled = 0
    pending = 0

    for row in rows:
        if (row.get("settled") or "").strip().lower() in {"1", "true", "yes", "settled"}:
            already_settled += 1
            continue

        signal_date = _parse_date(row.get("date") or "")
        if signal_date is None or signal_date >= today:
            pending += 1
            continue

        team_key = team_key_func(row.get("team") or "")
        opp_key = team_key_func(row.get("opponent") or "")
        player_id = (row.get("player_id") or "").strip()
        historical = None
        if player_id:
            historical = lookup_by_player_id.get(((row.get("date") or "").strip(), player_id, team_key, opp_key))
        if historical is None:
            historical = lookup_by_name.get(
                ((row.get("date") or "").strip(), _norm_text(row.get("player") or ""), team_key, opp_key)
            )
        if historical is None:
            row["settlement_note"] = "no_understat_match"
            pending += 1
            continue

        goals_scored = int(historical.goals)
        won = goals_scored >= 1
        odds = _parse_float(row.get("best_bookmaker_odds"))
        pnl_units = (odds - 1.0) if won else -1.0

        row["settled"] = "1"
        row["goals_scored"] = str(goals_scored)
        row["bet_outcome"] = "won" if won else "lost"
        row["settled_at"] = now_iso
        row["pnl_units"] = f"{pnl_units:.4f}"
        row["settlement_note"] = ""
        settled_now += 1

    _write_csv(path, rows, OUTPUT_FIELDS)
    return {"settled_now": settled_now, "already_settled": already_settled, "pending": pending}


def _summary_metrics(rows: List[dict]) -> dict:
    settled_rows = [row for row in rows if (row.get("settled") or "").strip().lower() in {"1", "true", "yes", "settled"}]
    pnl = sum(_parse_float(row.get("pnl_units")) for row in settled_rows)
    wins = sum(1 for row in settled_rows if (row.get("bet_outcome") or "").strip().lower() == "won")
    return {
        "signals": len(rows),
        "settled": len(settled_rows),
        "unsettled": len(rows) - len(settled_rows),
        "roi": (pnl / len(settled_rows)) if settled_rows else 0.0,
        "win_rate": (wins / len(settled_rows)) if settled_rows else 0.0,
        "pnl_units": pnl,
    }


def write_summary(path: Path, signals_path: Path) -> None:
    rows = _load_csv(signals_path)
    today = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=7)

    clean_rows = [row for row in rows if (_parse_date(row.get("date") or "") or date.min) >= CLEAN_EVAL_START]
    weekly_rows = [row for row in rows if (_parse_date(row.get("date") or "") or date.min) >= week_start]

    lines = [
        "Goalscorer Shadow Performance",
        "=============================",
        "",
        f"As of:                 {datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}",
        f"Signals file:          {signals_path}",
        f"Clean evaluation start:{CLEAN_EVAL_START.isoformat()}",
        "",
    ]

    for label, subset in (
        ("All time", rows),
        ("Clean sample", clean_rows),
        ("Last 7 days", weekly_rows),
    ):
        metrics = _summary_metrics(subset)
        lines.extend(
            [
                f"{label}",
                f"  signals:    {metrics['signals']}",
                f"  settled:    {metrics['settled']}",
                f"  unsettled:  {metrics['unsettled']}",
                f"  ROI:        {metrics['roi']:+.2%}",
                f"  win rate:   {metrics['win_rate']:.2%}",
                f"  P/L units:  {metrics['pnl_units']:+.2f}",
                "",
            ]
        )

    lines.append("By signal type (clean sample)")
    signal_groups: Dict[str, List[dict]] = defaultdict(list)
    for row in clean_rows:
        signal_groups[(row.get("signal_type") or "").strip() or "unknown"].append(row)
    for signal_type in sorted(signal_groups):
        metrics = _summary_metrics(signal_groups[signal_type])
        lines.append(
            f"  {signal_type:<16} signals={metrics['signals']:3d} settled={metrics['settled']:3d} "
            f"roi={metrics['roi']:+.2%} win_rate={metrics['win_rate']:.2%} pnl={metrics['pnl_units']:+.2f}u"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append and settle goalscorer shadow signals")
    parser.add_argument("--live-compare", default=str(DEFAULT_LIVE_COMPARE), help="Live compare CSV path")
    parser.add_argument("--odds-archive", default=str(DEFAULT_ODDS_ARCHIVE), help="Canonical odds archive CSV")
    parser.add_argument("--data", nargs="+", default=DEFAULT_DATA, help="Historical player-log CSVs or globs")
    parser.add_argument("--output", default=str(DEFAULT_SIGNALS), help="Append-only shadow signals CSV")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="Shadow performance summary TXT")
    parser.add_argument("--settle-only", action="store_true", help="Skip appending new rows and settle existing signals only")
    args = parser.parse_args()

    output_path = Path(args.output)
    summary_path = Path(args.summary)

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer Shadow Tracker")
    print("=" * 64)

    if not args.settle_only:
        live_rows = _load_csv(Path(args.live_compare))
        archive_rows = _load_csv(Path(args.odds_archive))
        archive_lookup = build_best_price_lookup(archive_rows)
        shadow_rows = build_shadow_rows(live_rows, archive_lookup)
        added = append_rows_dedup(output_path, shadow_rows)
        print(f"  Live compare rows:      {len(live_rows):,}")
        print(f"  Shadow qualifiers:      {len(shadow_rows):,}")
        print(f"  Appended new signals:   {added:,}")
    else:
        if not output_path.exists():
            _write_csv(output_path, [], OUTPUT_FIELDS)
        print("  Settle-only mode:       yes")

    settlement_stats = settle_rows(output_path, args.data)
    write_summary(summary_path, output_path)

    print(f"  Settled now:            {settlement_stats['settled_now']:,}")
    print(f"  Already settled:        {settlement_stats['already_settled']:,}")
    print(f"  Pending:                {settlement_stats['pending']:,}")
    print(f"  Saved:                  {output_path}")
    print(f"  Saved:                  {summary_path}")
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
