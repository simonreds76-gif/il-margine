#!/usr/bin/env python3
"""
Compare archived anytime-goalscorer odds against our goalscorer model output.

This is bookmaker-agnostic: it works with the canonical goalscorer odds history
CSV produced by `goalscorer-odds-archive.py`.
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
import unicodedata
from collections import defaultdict
from typing import Dict, Iterable, List


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


def _load_csv(path: str) -> List[dict]:
    if not os.path.exists(path):
        raise SystemExit(f"File not found: {path}")
    with open(path, "r", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _match_key(match_date: str, team_a: str, team_b: str) -> tuple[str, str]:
    teams = sorted([_norm_text(team_a), _norm_text(team_b)])
    return match_date, " | ".join(teams)


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
                "match_date": match_date,
                "player_name": player_name,
                "player_key": _norm_text(player_name),
                "team": team,
                "team_key": _norm_text(team),
                "opponent": opponent,
                "match_key": _match_key(match_date, team, opponent),
                "model_p_atgs": _parse_float(row.get("model_p_atgs")),
                "model_fair_odds_atgs": _parse_float(row.get("model_fair_odds_atgs")),
                "model_lambda": _parse_float(row.get("model_lambda")),
                "expected_minutes": _parse_float(row.get("expected_minutes")),
                "method": row.get("method") or "",
                "scored": int(_parse_float(row.get("scored"))),
            }
        )
    return loaded


def load_odds_rows(path: str, bookmaker_filter: str = "") -> List[dict]:
    rows = _load_csv(path)
    loaded: List[dict] = []
    bookmaker_norm = _norm_text(bookmaker_filter) if bookmaker_filter else ""
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
        loaded.append(
            {
                "captured_at": (row.get("captured_at") or "").strip(),
                "match_date": match_date,
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


def latest_rows_per_market(rows: List[dict]) -> List[dict]:
    latest: Dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        key = (row["match_date"], row["bookmaker"], row["player_key"], row["match_key"][1])
        current = latest.get(key)
        if current is None or row["captured_at"] > current["captured_at"]:
            latest[key] = row
    return list(latest.values())


def compare(model_rows: List[dict], odds_rows: List[dict]) -> tuple[List[dict], dict]:
    model_lookup: Dict[tuple[str, str, str], List[dict]] = defaultdict(list)
    for row in model_rows:
        model_lookup[(row["match_date"], row["player_key"], row["match_key"][1])].append(row)

    comparisons: List[dict] = []
    unmatched = 0
    for odds in odds_rows:
        candidates = model_lookup.get((odds["match_date"], odds["player_key"], odds["match_key"][1]), [])
        if odds["player_team_key"]:
            candidates = [candidate for candidate in candidates if candidate["team_key"] == odds["player_team_key"]] or candidates
        if not candidates:
            unmatched += 1
            continue
        model = candidates[0]
        model_prob = model["model_p_atgs"]
        odds_decimal = odds["odds_decimal"]
        implied_prob = odds["implied_prob"] or (1.0 / odds_decimal if odds_decimal > 1.0 else 0.0)
        ev = (model_prob * odds_decimal) - 1.0 if odds_decimal > 1.0 else 0.0
        pnl = (odds_decimal - 1.0) if model["scored"] else -1.0
        comparisons.append(
            {
                "captured_at": odds["captured_at"],
                "match_date": odds["match_date"],
                "bookmaker": odds["bookmaker"],
                "competition": odds["competition"],
                "player_name": model["player_name"],
                "player_team": model["team"],
                "opponent": model["opponent"],
                "odds_decimal": round(odds_decimal, 4),
                "implied_prob": round(implied_prob, 6),
                "model_p_atgs": round(model_prob, 6),
                "model_fair_odds_atgs": round(model["model_fair_odds_atgs"], 4),
                "model_lambda": round(model["model_lambda"], 4),
                "expected_minutes": round(model["expected_minutes"], 1),
                "ev": round(ev, 6),
                "edge_pct": round(((model_prob - implied_prob) / implied_prob) * 100.0, 3) if implied_prob > 0 else 0.0,
                "method": model["method"],
                "scored": model["scored"],
                "pnl": round(pnl, 4),
                "source": odds["source"],
                "notes": odds["notes"],
            }
        )

    stats = {
        "model_rows": len(model_rows),
        "odds_rows": len(odds_rows),
        "matched_rows": len(comparisons),
        "unmatched_odds_rows": unmatched,
    }
    return comparisons, stats


def summarize(comparisons: List[dict], min_ev: float) -> dict:
    qualified = [row for row in comparisons if row["ev"] >= min_ev]
    resolved = [row for row in qualified if row["scored"] in (0, 1)]
    avg_ev = sum(row["ev"] for row in qualified) / len(qualified) if qualified else 0.0
    roi = sum(row["pnl"] for row in resolved) / len(resolved) if resolved else 0.0
    win_rate = sum(row["scored"] for row in resolved) / len(resolved) if resolved else 0.0
    return {
        "qualified_rows": len(qualified),
        "avg_ev": avg_ev,
        "resolved_rows": len(resolved),
        "roi": roi,
        "win_rate": win_rate,
        "avg_odds": sum(row["odds_decimal"] for row in qualified) / len(qualified) if qualified else 0.0,
    }


def write_outputs(comparisons: List[dict], stats: dict, summary: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    comparison_path = os.path.join(out_dir, "goalscorer-odds-comparison.csv")
    summary_path = os.path.join(out_dir, "goalscorer-odds-comparison.txt")

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

    with open(summary_path, "w", encoding="utf-8") as handle:
        handle.write("Goalscorer Odds Comparison\n")
        handle.write("==========================\n\n")
        handle.write(f"Model rows:          {stats['model_rows']:,}\n")
        handle.write(f"Odds rows:           {stats['odds_rows']:,}\n")
        handle.write(f"Matched rows:        {stats['matched_rows']:,}\n")
        handle.write(f"Unmatched odds rows: {stats['unmatched_odds_rows']:,}\n\n")
        handle.write(f"Qualified rows:      {summary['qualified_rows']:,}\n")
        handle.write(f"Average EV:          {summary['avg_ev']:.4f}\n")
        handle.write(f"Average odds:        {summary['avg_odds']:.4f}\n")
        handle.write(f"Resolved rows:       {summary['resolved_rows']:,}\n")
        handle.write(f"ROI:                 {summary['roi']:.4f}\n")
        handle.write(f"Win rate:            {summary['win_rate']:.4f}\n")

    print(f"  Saved: {comparison_path}")
    print(f"  Saved: {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare archived ATGS odds against the goalscorer model")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model results CSV")
    parser.add_argument("--odds", default=DEFAULT_ODDS, help="Canonical odds archive CSV")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--bookmaker", default="", help="Optional bookmaker filter")
    parser.add_argument("--min-ev", type=float, default=0.05, help="Minimum EV threshold for summary")
    parser.add_argument(
        "--all-captures",
        action="store_true",
        help="Use every captured row instead of the latest price per player/bookmaker/match",
    )
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer Odds Comparison")
    print("=" * 64)

    model_rows = load_model_rows(args.model)
    odds_rows = load_odds_rows(args.odds, bookmaker_filter=args.bookmaker)
    if not args.all_captures:
        odds_rows = latest_rows_per_market(odds_rows)

    comparisons, stats = compare(model_rows, odds_rows)
    summary = summarize(comparisons, args.min_ev)

    print(f"  Model rows:          {stats['model_rows']:,}")
    print(f"  Odds rows:           {stats['odds_rows']:,}")
    print(f"  Matched rows:        {stats['matched_rows']:,}")
    print(f"  Unmatched odds rows: {stats['unmatched_odds_rows']:,}")
    print(f"  Qualified rows:      {summary['qualified_rows']:,}")
    print(f"  Average EV:          {summary['avg_ev']:.4f}")
    print(f"  ROI:                 {summary['roi']:.4f}")

    write_outputs(comparisons, stats, summary, args.out_dir)
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
