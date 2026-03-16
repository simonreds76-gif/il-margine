#!/usr/bin/env python3
"""
Backtest a narrow ATGS signal based on finishing luck.

This intentionally does not try to price the whole market. Instead it asks:
when a likely starter in an attacking role has materially underperformed recent
non-penalty xG, does the market overreact to the goal drought?
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
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKTEST = "data/goalscorer/test-run/historical-all-rawshare/goalscorer-historical-backtest.csv"
DEFAULT_DATA = [
    "data/goalscorer/serie-a-player-match-logs-2023-2024.csv",
    "data/goalscorer/serie-a-player-match-logs-2024-2025.csv",
    "data/goalscorer/serie-a-player-match-logs-2025-2026.csv",
]
DEFAULT_OUT_DIR = "data/goalscorer/test-run/historical-all-rawshare"

ATTACKING_POSITIONS = {"FW", "FWL", "FWR", "AMC", "AML", "AMR"}


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


def _join_key(match_date: str, player_name: str, team: str, opponent: str, team_key_func) -> tuple[str, str, str, str]:
    return (
        (match_date or "").strip(),
        _norm_text(player_name),
        team_key_func(team),
        team_key_func(opponent),
    )


def build_finishing_luck_lookup(data_paths: List[str], window: int) -> Dict[tuple[str, str, str, str], dict]:
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    load_match_logs = model_mod["load_match_logs"]
    team_key_func = model_mod["_team_key"]

    rows = load_match_logs(data_paths)
    histories: Dict[str, List[dict]] = defaultdict(list)
    lookup: Dict[tuple[str, str, str, str], dict] = {}

    for row in rows:
        history = histories[row.player_id]
        recent = history[-window:]
        recent_npxg = sum(match["npxg"] for match in recent)
        recent_np_goals = sum(match["np_goals"] for match in recent)
        finishing_luck = recent_np_goals - recent_npxg

        lookup[
            _join_key(
                row.match_date_str,
                row.player_name,
                row.team,
                row.opponent,
                team_key_func,
            )
        ] = {
            "player_id": row.player_id,
            "recent_matches": len(recent),
            "prior_matches": len(history),
            "recent_npxg": recent_npxg,
            "recent_np_goals": recent_np_goals,
            "finishing_luck": finishing_luck,
            "position_group": (row.position or "").split(",")[0].strip() or "Unknown",
        }

        history.append(
            {
                "npxg": row.npxg,
                "np_goals": max(row.goals - row.penalties_scored, 0),
            }
        )

    return lookup


def load_backtest_rows(
    path: str,
    finishing_luck_lookup: Dict[tuple[str, str, str, str], dict],
    min_ev: float,
    min_expected_minutes: float,
    min_prior_matches: int,
    min_recent_matches: int,
    max_finishing_luck: float,
    attacking_positions: set[str],
) -> Tuple[List[dict], dict]:
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    team_key_func = model_mod["_team_key"]

    rows = _load_csv(path)
    loaded: List[dict] = []
    stats = {
        "rows": len(rows),
        "joined_finishing_luck": 0,
        "missing_finishing_luck": 0,
        "selected_rows": 0,
    }

    for row in rows:
        join_key = _join_key(
            row.get("match_date") or "",
            row.get("player_name") or "",
            row.get("player_team") or "",
            row.get("opponent") or "",
            team_key_func,
        )
        features = finishing_luck_lookup.get(join_key)
        if features is None:
            stats["missing_finishing_luck"] += 1
            continue

        stats["joined_finishing_luck"] += 1
        odds_decimal = _parse_float(row.get("odds_decimal"))
        fair_odds = _parse_float(row.get("model_fair_odds_atgs"))
        expected_minutes = _parse_float(row.get("expected_minutes"))
        ev = _parse_float(row.get("ev"))
        position_group = (row.get("position_group") or features["position_group"] or "").strip()
        base_eligible = (
            (row.get("method") or "").strip() == "model"
            and position_group in attacking_positions
            and expected_minutes >= min_expected_minutes
            and features["prior_matches"] >= min_prior_matches
            and features["recent_matches"] >= min_recent_matches
            and odds_decimal > fair_odds
            and ev >= min_ev
        )
        selected = base_eligible and features["finishing_luck"] <= max_finishing_luck
        if selected:
            stats["selected_rows"] += 1

        loaded.append(
            {
                "season": (row.get("season") or "").strip(),
                "bookmaker": (row.get("bookmaker") or "").strip(),
                "match_date": (row.get("match_date") or "").strip(),
                "player_name": (row.get("player_name") or "").strip(),
                "player_team": (row.get("player_team") or "").strip(),
                "opponent": (row.get("opponent") or "").strip(),
                "position_group": position_group,
                "expected_minutes": expected_minutes,
                "odds_decimal": odds_decimal,
                "model_fair_odds_atgs": fair_odds,
                "ev": ev,
                "pnl": _parse_float(row.get("pnl")),
                "scored": int(_parse_float(row.get("scored"))),
                "recent_matches": int(features["recent_matches"]),
                "prior_matches": int(features["prior_matches"]),
                "recent_npxg": round(features["recent_npxg"], 4),
                "recent_np_goals": round(features["recent_np_goals"], 4),
                "finishing_luck": round(features["finishing_luck"], 4),
                "base_eligible": base_eligible,
                "selected": selected,
            }
        )

    return loaded, stats


def _summarize(rows: List[dict]) -> dict:
    resolved = [row for row in rows if row["scored"] in (0, 1)]
    return {
        "selected_rows": len(rows),
        "avg_ev": (sum(row["ev"] for row in rows) / len(rows)) if rows else 0.0,
        "avg_odds": (sum(row["odds_decimal"] for row in rows) / len(rows)) if rows else 0.0,
        "avg_expected_minutes": (sum(row["expected_minutes"] for row in rows) / len(rows)) if rows else 0.0,
        "avg_recent_npxg": (sum(row["recent_npxg"] for row in rows) / len(rows)) if rows else 0.0,
        "avg_recent_np_goals": (sum(row["recent_np_goals"] for row in rows) / len(rows)) if rows else 0.0,
        "avg_finishing_luck": (sum(row["finishing_luck"] for row in rows) / len(rows)) if rows else 0.0,
        "resolved_rows": len(resolved),
        "roi": (sum(row["pnl"] for row in resolved) / len(resolved)) if resolved else 0.0,
        "win_rate": (sum(row["scored"] for row in resolved) / len(resolved)) if resolved else 0.0,
    }


def select_best_price_rows(rows: List[dict]) -> List[dict]:
    best_by_pick: Dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (row["match_date"], row["player_name"], row["player_team"])
        current = best_by_pick.get(key)
        if current is None or row["odds_decimal"] > current["odds_decimal"]:
            best_by_pick[key] = row
    return list(best_by_pick.values())


def run_threshold_sweep(rows: List[dict], thresholds: Iterable[float]) -> List[dict]:
    results: List[dict] = []
    for threshold in thresholds:
        subset = [row for row in rows if row["base_eligible"] and row["finishing_luck"] <= threshold]
        summary = _summarize(subset)
        results.append({"finishing_luck_threshold": threshold, **summary})
    return results


def write_outputs(stats: dict, selected_rows: List[dict], sweep_rows: List[dict], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    selected_path = os.path.join(out_dir, "goalscorer-finishing-luck-backtest.csv")
    summary_path = os.path.join(out_dir, "goalscorer-finishing-luck-backtest.txt")
    sweep_path = os.path.join(out_dir, "goalscorer-finishing-luck-thresholds.csv")

    if selected_rows:
        fieldnames = list(selected_rows[0].keys())
        with open(selected_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted(selected_rows, key=lambda row: (row["match_date"], -row["ev"], row["player_name"])))
    else:
        with open(selected_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["no_rows"])

    if sweep_rows:
        with open(sweep_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(sweep_rows[0].keys()))
            writer.writeheader()
            writer.writerows(sweep_rows)
    else:
        with open(sweep_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["no_rows"])

    summary = _summarize(selected_rows)
    with open(summary_path, "w", encoding="utf-8") as handle:
        handle.write("Goalscorer Finishing Luck Backtest\n")
        handle.write("=================================\n\n")
        handle.write(f"Rows loaded:              {stats['rows']:,}\n")
        handle.write(f"Joined finishing-luck:    {stats['joined_finishing_luck']:,}\n")
        handle.write(f"Missing finishing-luck:   {stats['missing_finishing_luck']:,}\n")
        handle.write(f"Selected rows:            {summary['selected_rows']:,}\n")
        handle.write(f"Average EV:               {summary['avg_ev']:.4f}\n")
        handle.write(f"Average odds:             {summary['avg_odds']:.4f}\n")
        handle.write(f"Average expected mins:    {summary['avg_expected_minutes']:.1f}\n")
        handle.write(f"Average recent npxG:      {summary['avg_recent_npxg']:.4f}\n")
        handle.write(f"Average recent NP goals:  {summary['avg_recent_np_goals']:.4f}\n")
        handle.write(f"Average finishing luck:   {summary['avg_finishing_luck']:.4f}\n")
        handle.write(f"Resolved rows:            {summary['resolved_rows']:,}\n")
        handle.write(f"ROI:                      {summary['roi']:.4f}\n")
        handle.write(f"Win rate:                 {summary['win_rate']:.4f}\n")

        if sweep_rows:
            handle.write("\nThreshold sweep\n")
            handle.write("--------------\n")
            for row in sweep_rows:
                handle.write(
                    f"{row['finishing_luck_threshold']:>5.1f}  sel={row['selected_rows']:>4}  "
                    f"roi={row['roi']:+.4f}  avg_ev={row['avg_ev']:+.4f}\n"
                )

    print(f"  Saved: {selected_path}")
    print(f"  Saved: {sweep_path}")
    print(f"  Saved: {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest an unlucky-finisher ATGS signal")
    parser.add_argument("--backtest", default=DEFAULT_BACKTEST, help="Historical goalscorer backtest CSV")
    parser.add_argument("--data", nargs="+", default=DEFAULT_DATA, help="Historical player-log CSVs or globs")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--window", type=int, default=10, help="Rolling match window for finishing luck")
    parser.add_argument("--min-ev", type=float, default=0.10, help="Minimum EV threshold")
    parser.add_argument("--min-expected-minutes", type=float, default=70.0, help="Minimum expected minutes")
    parser.add_argument("--min-prior-matches", type=int, default=15, help="Minimum prior matches before the bet")
    parser.add_argument("--min-recent-matches", type=int, default=10, help="Minimum matches inside the finishing-luck window")
    parser.add_argument("--max-finishing-luck", type=float, default=-1.5, help="Maximum finishing luck (goals - npxG)")
    parser.add_argument("--best-price-only", action="store_true", help="Keep one row per player-match using the best odds across books")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Finishing Luck Backtest")
    print("=" * 64)

    finishing_luck_lookup = build_finishing_luck_lookup(args.data, args.window)
    loaded_rows, stats = load_backtest_rows(
        args.backtest,
        finishing_luck_lookup,
        args.min_ev,
        args.min_expected_minutes,
        args.min_prior_matches,
        args.min_recent_matches,
        args.max_finishing_luck,
        ATTACKING_POSITIONS,
    )
    if args.best_price_only:
        loaded_rows = select_best_price_rows(loaded_rows)
        stats["rows"] = len(loaded_rows)
        stats["selected_rows"] = sum(1 for row in loaded_rows if row["selected"])
    selected_rows = [row for row in loaded_rows if row["selected"]]
    sweep_rows = run_threshold_sweep(
        loaded_rows,
        thresholds=[-0.5, -1.0, -1.5, -2.0, -2.5],
    )

    summary = _summarize(selected_rows)
    print(f"  Rows loaded:           {stats['rows']:,}")
    print(f"  Joined finishing-luck: {stats['joined_finishing_luck']:,}")
    print(f"  Selected rows:         {summary['selected_rows']:,}")
    print(f"  Average EV:            {summary['avg_ev']:.4f}")
    print(f"  ROI:                   {summary['roi']:.4f}")
    print(f"  Win rate:              {summary['win_rate']:.4f}")

    write_outputs(stats, selected_rows, sweep_rows, args.out_dir)
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
