#!/usr/bin/env python3
"""
Backtest historical anytime-goalscorer odds against the goalscorer model.

This is the market-backtest companion to `goalscorer-model.py`.
It joins settled model rows to archived ATGS odds, selects one historical
capture per player/bookmaker/match, and reports EV / ROI / capture timing.
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional


DEFAULT_MODEL = "data/goalscorer/goalscorer-backtest-results.csv"
DEFAULT_ODDS = "data/goalscorer/goalscorer-odds-history.csv"
DEFAULT_OUT_DIR = "data/goalscorer"


def _norm_text(value: str) -> str:
    normalized = html.unescape((value or "").strip().lower())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_float(value: str, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_iso_dt(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _load_csv(path: str) -> List[dict]:
    if not os.path.exists(path):
        raise SystemExit(f"File not found: {path}")
    with open(path, "r", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _match_key(match_date: str, team_a: str, team_b: str) -> tuple[str, str]:
    teams = sorted([_norm_text(team_a), _norm_text(team_b)])
    return match_date, " | ".join(teams)


def _season_from_match_date(match_date: str) -> str:
    try:
        parsed = datetime.strptime(match_date[:10], "%Y-%m-%d").date()
    except ValueError:
        return ""
    start_year = parsed.year if parsed.month >= 7 else parsed.year - 1
    return f"{start_year}-{start_year + 1}"


def _lead_bucket(minutes_to_kickoff: Optional[float]) -> str:
    if minutes_to_kickoff is None:
        return "unknown"
    if minutes_to_kickoff < 0:
        return "after_kickoff"
    if minutes_to_kickoff <= 30:
        return "0-30m"
    if minutes_to_kickoff <= 90:
        return "30-90m"
    if minutes_to_kickoff <= 360:
        return "90m-6h"
    if minutes_to_kickoff <= 1440:
        return "6h-24h"
    return "24h+"


def load_model_rows(path: str) -> List[dict]:
    rows = _load_csv(path)
    loaded: List[dict] = []
    for row in rows:
        match_date = (row.get("match_date") or "").strip()
        player_name = (row.get("player_name") or "").strip()
        team = (row.get("team") or "").strip()
        opponent = (row.get("opponent") or "").strip()
        if not match_date or not player_name or not team or not opponent:
            continue
        loaded.append(
            {
                "season": (row.get("season") or "").strip() or _season_from_match_date(match_date),
                "match_date": match_date,
                "player_name": player_name,
                "player_key": _norm_text(player_name),
                "team": team,
                "team_key": _norm_text(team),
                "opponent": opponent,
                "position": (row.get("position") or "").strip(),
                "position_group": (row.get("position_group") or "").strip(),
                "minutes_band": (row.get("minutes_band") or "").strip(),
                "match_key": _match_key(match_date, team, opponent),
                "model_p_atgs": _parse_float(row.get("model_p_atgs")),
                "model_fair_odds_atgs": _parse_float(row.get("model_fair_odds_atgs")),
                "model_lambda": _parse_float(row.get("model_lambda")),
                "expected_minutes": _parse_float(row.get("expected_minutes")),
                "method": (row.get("method") or "").strip(),
                "penalty_role": (row.get("penalty_role") or "").strip(),
                "scored": int(_parse_float(row.get("scored"))),
            }
        )
    return loaded


def load_odds_rows(path: str, bookmaker_filter: str = "") -> List[dict]:
    rows = _load_csv(path)
    bookmaker_norm = _norm_text(bookmaker_filter) if bookmaker_filter else ""
    loaded: List[dict] = []
    for row in rows:
        match_date = (row.get("match_date") or "").strip()
        home_team = (row.get("home_team") or "").strip()
        away_team = (row.get("away_team") or "").strip()
        player_name = (row.get("player_name") or "").strip()
        bookmaker = (row.get("bookmaker") or "").strip()
        market = (row.get("market") or "").strip().upper()
        if bookmaker_norm and _norm_text(bookmaker) != bookmaker_norm:
            continue
        if market and market != "ATGS":
            continue
        if not match_date or not home_team or not away_team or not player_name:
            continue

        captured_at = (row.get("captured_at") or "").strip()
        kickoff_at = (row.get("kickoff_at") or "").strip()
        captured_dt = _parse_iso_dt(captured_at)
        kickoff_dt = _parse_iso_dt(kickoff_at)
        lead_minutes = _parse_float(row.get("minutes_to_kickoff"), -999999.0)
        if lead_minutes <= -999998.0:
            lead_minutes = None
            if captured_dt and kickoff_dt:
                lead_minutes = (kickoff_dt - captured_dt).total_seconds() / 60.0

        loaded.append(
            {
                "captured_at": captured_at,
                "captured_dt": captured_dt,
                "match_date": match_date,
                "event_id": (row.get("event_id") or "").strip(),
                "kickoff_at": kickoff_at,
                "kickoff_dt": kickoff_dt,
                "minutes_to_kickoff": lead_minutes,
                "snapshot_kind": (row.get("snapshot_kind") or "").strip(),
                "bookmaker": bookmaker,
                "competition": (row.get("competition") or "").strip(),
                "home_team": home_team,
                "away_team": away_team,
                "player_name": player_name,
                "player_key": _norm_text(player_name),
                "player_team": (row.get("player_team") or "").strip(),
                "player_team_key": _norm_text(row.get("player_team") or ""),
                "match_key": _match_key(match_date, home_team, away_team),
                "odds_decimal": _parse_float(row.get("odds_decimal")),
                "implied_prob": _parse_float(row.get("implied_prob")),
                "source": (row.get("source") or "").strip(),
                "notes": (row.get("notes") or "").strip(),
            }
        )
    return loaded


def _select_rows(group: List[dict], strategy: str, target_minutes_before: int) -> List[dict]:
    if not group:
        return []
    if strategy == "all":
        return sorted(group, key=lambda row: (row["captured_at"], row["odds_decimal"]))

    group = list(group)
    before_kickoff = [row for row in group if row["minutes_to_kickoff"] is not None and row["minutes_to_kickoff"] >= 0]

    if strategy == "opening":
        return [min(group, key=lambda row: row["captured_at"])]

    if strategy == "closing":
        target_group = before_kickoff or group
        return [max(target_group, key=lambda row: row["captured_at"])]

    if strategy == "target_before_kickoff":
        target_group = before_kickoff or group

        def rank(row: dict) -> tuple[float, float, str]:
            lead = row["minutes_to_kickoff"]
            if lead is None:
                return (10_000_000.0, 10_000_000.0, row["captured_at"])
            return (abs(lead - target_minutes_before), abs(lead), row["captured_at"])

        ranked = sorted(target_group, key=rank)
        if not ranked:
            return []
        best = ranked[0]
        return [best]

    raise SystemExit(f"Unsupported selection strategy: {strategy}")


def _group_key(row: dict) -> tuple[str, str, str, str]:
    return (
        row["match_date"],
        row["bookmaker"],
        row["player_key"],
        row["match_key"][1],
    )


def compare(
    model_rows: List[dict],
    odds_rows: List[dict],
    strategy: str,
    target_minutes_before: int,
) -> tuple[List[dict], dict]:
    model_lookup: Dict[tuple[str, str, str], List[dict]] = defaultdict(list)
    for row in model_rows:
        model_lookup[(row["match_date"], row["player_key"], row["match_key"][1])].append(row)

    grouped_odds: Dict[tuple[str, str, str, str], List[dict]] = defaultdict(list)
    for row in odds_rows:
        grouped_odds[_group_key(row)].append(row)

    selected_odds: List[dict] = []
    for group_rows in grouped_odds.values():
        selected_odds.extend(_select_rows(group_rows, strategy, target_minutes_before))

    comparisons: List[dict] = []
    unmatched = 0
    for odds in selected_odds:
        candidates = model_lookup.get((odds["match_date"], odds["player_key"], odds["match_key"][1]), [])
        if odds["player_team_key"]:
            candidates = [candidate for candidate in candidates if candidate["team_key"] == odds["player_team_key"]] or candidates
        if not candidates:
            unmatched += 1
            continue
        model = candidates[0]

        all_market_rows = grouped_odds[_group_key(odds)]
        opening_row = min(all_market_rows, key=lambda row: row["captured_at"])
        if any(row["minutes_to_kickoff"] is not None and row["minutes_to_kickoff"] >= 0 for row in all_market_rows):
            close_pool = [row for row in all_market_rows if row["minutes_to_kickoff"] is not None and row["minutes_to_kickoff"] >= 0]
            closing_row = max(close_pool, key=lambda row: row["captured_at"])
        else:
            closing_row = max(all_market_rows, key=lambda row: row["captured_at"])

        model_prob = model["model_p_atgs"]
        odds_decimal = odds["odds_decimal"]
        implied_prob = odds["implied_prob"] or (1.0 / odds_decimal if odds_decimal > 1.0 else 0.0)
        ev = (model_prob * odds_decimal) - 1.0 if odds_decimal > 1.0 else 0.0
        pnl = (odds_decimal - 1.0) if model["scored"] else -1.0
        closing_odds = closing_row["odds_decimal"]
        opening_odds = opening_row["odds_decimal"]
        closing_ev = (model_prob * closing_odds) - 1.0 if closing_odds > 1.0 else 0.0
        opening_ev = (model_prob * opening_odds) - 1.0 if opening_odds > 1.0 else 0.0
        beat_closing = int(closing_odds < odds_decimal)

        comparisons.append(
            {
                "season": model["season"],
                "match_date": odds["match_date"],
                "captured_at": odds["captured_at"],
                "kickoff_at": odds["kickoff_at"],
                "minutes_to_kickoff": round(odds["minutes_to_kickoff"], 1) if odds["minutes_to_kickoff"] is not None else "",
                "lead_bucket": _lead_bucket(odds["minutes_to_kickoff"]),
                "snapshot_kind": odds["snapshot_kind"],
                "selection_strategy": strategy,
                "bookmaker": odds["bookmaker"],
                "competition": odds["competition"],
                "player_name": model["player_name"],
                "player_team": model["team"],
                "opponent": model["opponent"],
                "position": model["position"],
                "position_group": model["position_group"],
                "minutes_band": model["minutes_band"],
                "odds_decimal": round(odds_decimal, 4),
                "opening_odds_decimal": round(opening_odds, 4),
                "closing_odds_decimal": round(closing_odds, 4),
                "opening_ev": round(opening_ev, 6),
                "closing_ev": round(closing_ev, 6),
                "selected_vs_closing_odds_delta": round(closing_odds - odds_decimal, 4),
                "beat_closing_price": beat_closing,
                "implied_prob": round(implied_prob, 6),
                "model_p_atgs": round(model_prob, 6),
                "model_fair_odds_atgs": round(model["model_fair_odds_atgs"], 4),
                "model_lambda": round(model["model_lambda"], 4),
                "expected_minutes": round(model["expected_minutes"], 1),
                "ev": round(ev, 6),
                "edge_pct": round(((model_prob - implied_prob) / implied_prob) * 100.0, 3) if implied_prob > 0 else 0.0,
                "method": model["method"],
                "penalty_role": model["penalty_role"],
                "scored": model["scored"],
                "pnl": round(pnl, 4),
                "source": odds["source"],
                "notes": odds["notes"],
            }
        )

    stats = {
        "model_rows": len(model_rows),
        "odds_rows": len(odds_rows),
        "selected_rows": len(selected_odds),
        "matched_rows": len(comparisons),
        "unmatched_selected_rows": unmatched,
    }
    return comparisons, stats


def _segment_summary(rows: List[dict], min_ev: float) -> dict:
    qualified = [row for row in rows if row["ev"] >= min_ev]
    resolved = [row for row in qualified if row["scored"] in (0, 1)]
    beat_close_rows = [row for row in qualified if row["closing_odds_decimal"] > 1.0]
    return {
        "rows": len(rows),
        "qualified_rows": len(qualified),
        "avg_ev": (sum(row["ev"] for row in qualified) / len(qualified)) if qualified else 0.0,
        "avg_odds": (sum(row["odds_decimal"] for row in qualified) / len(qualified)) if qualified else 0.0,
        "resolved_rows": len(resolved),
        "roi": (sum(row["pnl"] for row in resolved) / len(resolved)) if resolved else 0.0,
        "win_rate": (sum(row["scored"] for row in resolved) / len(resolved)) if resolved else 0.0,
        "avg_minutes_to_kickoff": (
            sum(row["minutes_to_kickoff"] for row in qualified if row["minutes_to_kickoff"] != "") / len([row for row in qualified if row["minutes_to_kickoff"] != ""])
            if any(row["minutes_to_kickoff"] != "" for row in qualified)
            else 0.0
        ),
        "beat_closing_rate": (
            sum(row["beat_closing_price"] for row in beat_close_rows) / len(beat_close_rows) if beat_close_rows else 0.0
        ),
    }


def summarize(comparisons: List[dict], min_ev: float) -> tuple[dict, List[dict]]:
    overall = _segment_summary(comparisons, min_ev)
    segments: List[dict] = []

    def append_segments(label: str, key_name: str) -> None:
        buckets: Dict[str, List[dict]] = defaultdict(list)
        for row in comparisons:
            buckets[str(row[key_name] or "Unknown")].append(row)
        for key, rows in sorted(buckets.items()):
            segment = _segment_summary(rows, min_ev)
            segments.append(
                {
                    "segment_type": label,
                    "segment_key": key,
                    **segment,
                }
            )

    append_segments("bookmaker", "bookmaker")
    append_segments("season", "season")
    append_segments("lead_bucket", "lead_bucket")
    append_segments("position_group", "position_group")
    return overall, segments


def write_outputs(comparisons: List[dict], stats: dict, summary: dict, segments: List[dict], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    comparison_path = os.path.join(out_dir, "goalscorer-historical-backtest.csv")
    summary_path = os.path.join(out_dir, "goalscorer-historical-backtest.txt")
    segments_path = os.path.join(out_dir, "goalscorer-historical-backtest-segments.csv")

    if comparisons:
        fieldnames = list(comparisons[0].keys())
        with open(comparison_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted(comparisons, key=lambda row: (row["match_date"], row["bookmaker"], -row["ev"])))
    else:
        with open(comparison_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["no_rows"])

    if segments:
        fieldnames = list(segments[0].keys())
        with open(segments_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(segments)
    else:
        with open(segments_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["no_rows"])

    with open(summary_path, "w", encoding="utf-8") as handle:
        handle.write("Goalscorer Historical Backtest\n")
        handle.write("==============================\n\n")
        handle.write(f"Model rows:             {stats['model_rows']:,}\n")
        handle.write(f"Odds rows:              {stats['odds_rows']:,}\n")
        handle.write(f"Selected rows:          {stats['selected_rows']:,}\n")
        handle.write(f"Matched rows:           {stats['matched_rows']:,}\n")
        handle.write(f"Unmatched selected:     {stats['unmatched_selected_rows']:,}\n\n")
        handle.write(f"Qualified rows:         {summary['qualified_rows']:,}\n")
        handle.write(f"Average EV:             {summary['avg_ev']:.4f}\n")
        handle.write(f"Average odds:           {summary['avg_odds']:.4f}\n")
        handle.write(f"Resolved rows:          {summary['resolved_rows']:,}\n")
        handle.write(f"ROI:                    {summary['roi']:.4f}\n")
        handle.write(f"Win rate:               {summary['win_rate']:.4f}\n")
        handle.write(f"Avg minutes to kickoff: {summary['avg_minutes_to_kickoff']:.1f}\n")
        handle.write(f"Beat closing rate:      {summary['beat_closing_rate']:.4f}\n")

    print(f"  Saved: {comparison_path}")
    print(f"  Saved: {segments_path}")
    print(f"  Saved: {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest historical ATGS odds against the goalscorer model")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model results CSV")
    parser.add_argument("--odds", default=DEFAULT_ODDS, help="Canonical odds archive CSV")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--bookmaker", default="", help="Optional bookmaker filter")
    parser.add_argument("--min-ev", type=float, default=0.05, help="Minimum EV threshold for summary")
    parser.add_argument(
        "--selection",
        default="target_before_kickoff",
        choices=["target_before_kickoff", "closing", "opening", "all"],
        help="How to select one capture per player/bookmaker/match",
    )
    parser.add_argument("--target-minutes-before", type=int, default=60, help="Target pre-kickoff lead time when selection=target_before_kickoff")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer Historical Backtest")
    print("=" * 64)

    model_rows = load_model_rows(args.model)
    odds_rows = load_odds_rows(args.odds, bookmaker_filter=args.bookmaker)
    comparisons, stats = compare(model_rows, odds_rows, args.selection, args.target_minutes_before)
    summary, segments = summarize(comparisons, args.min_ev)

    print(f"  Model rows:          {stats['model_rows']:,}")
    print(f"  Odds rows:           {stats['odds_rows']:,}")
    print(f"  Selected rows:       {stats['selected_rows']:,}")
    print(f"  Matched rows:        {stats['matched_rows']:,}")
    print(f"  Unmatched selected:  {stats['unmatched_selected_rows']:,}")
    print(f"  Qualified rows:      {summary['qualified_rows']:,}")
    print(f"  Average EV:          {summary['avg_ev']:.4f}")
    print(f"  ROI:                 {summary['roi']:.4f}")
    print(f"  Beat close rate:     {summary['beat_closing_rate']:.4f}")

    write_outputs(comparisons, stats, summary, segments, args.out_dir)
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
