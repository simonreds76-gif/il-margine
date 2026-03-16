#!/usr/bin/env python3
"""
Backtest a big-chance regression ATGS signal on the existing historical archive.

This keeps the signal separate from the finishing-luck stack so we can see
whether it adds genuine incremental value or just more noise.
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
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKTEST = "data/goalscorer/test-run/historical-all-rawshare/goalscorer-historical-backtest.csv"
DEFAULT_DATA = [
    "data/goalscorer/serie-a-player-match-logs-2023-2024.csv",
    "data/goalscorer/serie-a-player-match-logs-2024-2025.csv",
    "data/goalscorer/serie-a-player-match-logs-2025-2026.csv",
]
DEFAULT_OUT_DIR = "data/goalscorer/test-run/historical-all-rawshare/big-chance"
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


def _parse_date(value: str) -> Optional[date]:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _load_rows(path: str) -> List[dict]:
    if not os.path.exists(path):
        raise SystemExit(f"File not found: {path}")
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _expand_paths(paths: Iterable[str]) -> List[str]:
    expanded: List[str] = []
    for path in paths:
        if "*" in path or "?" in path:
            import glob

            expanded.extend(glob.glob(path))
        else:
            expanded.append(path)
    return [path for path in expanded if os.path.exists(path)]


def _join_key(match_date: str, player_name: str, team: str, opponent: str, team_key_func) -> tuple[str, str, str, str]:
    return (
        (match_date or "").strip(),
        _norm_text(player_name),
        team_key_func(team),
        team_key_func(opponent),
    )


def select_best_price_rows(rows: List[dict]) -> List[dict]:
    best_by_pick: Dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (row["match_date"], row["player_name"], row["player_team"])
        current = best_by_pick.get(key)
        if current is None or row["odds_decimal"] > current["odds_decimal"]:
            best_by_pick[key] = row
    return list(best_by_pick.values())


def build_feature_lookup(data_paths: List[str], big_window: int, quality_window: int) -> Dict[tuple[str, str, str, str], dict]:
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    team_key_func = model_mod["_team_key"]
    coarse_position = model_mod["coarse_position"]

    raw_rows: List[dict] = []
    for path in _expand_paths(data_paths):
        rows = _load_rows(path)
        raw_rows.extend({k.strip().lower(): v for k, v in row.items()} for row in rows)

    if not raw_rows:
        raise SystemExit("No player-log rows loaded.")

    required = {"big_chances", "big_chance_misses", "big_chance_goals", "big_chance_xg"}
    if not required.issubset(set(raw_rows[0].keys())):
        raise SystemExit(
            "Player logs do not contain big-chance columns yet. Refresh the Understat CSVs with the updated scraper first."
        )

    normalized_rows: List[dict] = []
    for row in raw_rows:
        match_date = _parse_date(row.get("match_date") or "")
        if match_date is None:
            continue
        normalized_rows.append(
            {
                "season": (row.get("season") or "").strip(),
                "match_date": match_date,
                "match_date_str": match_date.isoformat(),
                "player_id": (row.get("player_id") or "").strip(),
                "player_name": (row.get("player_name") or "").strip(),
                "team": (row.get("team") or "").strip(),
                "team_key": team_key_func(row.get("team") or ""),
                "opponent": (row.get("opponent") or "").strip(),
                "opponent_key": team_key_func(row.get("opponent") or ""),
                "position_group": coarse_position(row.get("position") or ""),
                "minutes": int(_parse_float(row.get("minutes"), 0.0)),
                "npxg": _parse_float(row.get("npxg"), 0.0),
                "big_chances": int(_parse_float(row.get("big_chances"), 0.0)),
                "big_chance_misses": int(_parse_float(row.get("big_chance_misses"), 0.0)),
                "big_chance_goals": int(_parse_float(row.get("big_chance_goals"), 0.0)),
                "big_chance_xg": _parse_float(row.get("big_chance_xg"), 0.0),
            }
        )

    normalized_rows.sort(key=lambda row: (row["match_date"], row["player_id"], row["team_key"]))

    player_histories: Dict[str, List[dict]] = defaultdict(list)
    feature_lookup: Dict[tuple[str, str, str, str], dict] = {}

    idx = 0
    while idx < len(normalized_rows):
        batch_date = normalized_rows[idx]["match_date"]
        batch: List[dict] = []
        while idx < len(normalized_rows) and normalized_rows[idx]["match_date"] == batch_date:
            batch.append(normalized_rows[idx])
            idx += 1

        for row in batch:
            history = player_histories[row["player_id"]]
            recent_big = history[-big_window:]
            recent_quality = history[-quality_window:]
            big_minutes = sum(item["minutes"] for item in recent_big)
            quality_minutes = sum(item["minutes"] for item in recent_quality)
            recent_big_chances = sum(item["big_chances"] for item in recent_big)
            recent_big_chance_misses = sum(item["big_chance_misses"] for item in recent_big)
            recent_big_chance_goals = sum(item["big_chance_goals"] for item in recent_big)
            recent_big_chance_xg = sum(item["big_chance_xg"] for item in recent_big)
            recent_npxg_quality = sum(item["npxg"] for item in recent_quality)
            recent_npxg_per90 = (recent_npxg_quality / (quality_minutes / 90.0)) if quality_minutes > 0 else 0.0

            feature_lookup[
                _join_key(row["match_date_str"], row["player_name"], row["team"], row["opponent"], team_key_func)
            ] = {
                "season": row["season"],
                "position_group": row["position_group"] or "Unknown",
                "big_window_matches": len(recent_big),
                "quality_window_matches": len(recent_quality),
                "recent_big_chances": recent_big_chances,
                "recent_big_chance_misses": recent_big_chance_misses,
                "recent_big_chance_goals": recent_big_chance_goals,
                "recent_big_chance_xg": recent_big_chance_xg,
                "recent_npxg_per90": recent_npxg_per90,
                "recent_big_minutes": big_minutes,
                "recent_quality_minutes": quality_minutes,
            }

        for row in batch:
            player_histories[row["player_id"]].append(
                {
                    "minutes": row["minutes"],
                    "npxg": row["npxg"],
                    "big_chances": row["big_chances"],
                    "big_chance_misses": row["big_chance_misses"],
                    "big_chance_goals": row["big_chance_goals"],
                    "big_chance_xg": row["big_chance_xg"],
                }
            )

    return feature_lookup


def load_backtest_rows(
    path: str,
    feature_lookup: Dict[tuple[str, str, str, str], dict],
    big_window: int,
    quality_window: int,
    min_ev: float,
    min_expected_minutes: float,
    min_recent_npxg_per90: float,
    min_big_chance_misses: int,
) -> tuple[List[dict], dict]:
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    team_key_func = model_mod["_team_key"]

    rows = _load_rows(path)
    loaded: List[dict] = []
    stats = {"rows": len(rows), "joined_features": 0, "missing_features": 0}

    for row in rows:
        key = _join_key(
            row.get("match_date") or "",
            row.get("player_name") or "",
            row.get("player_team") or "",
            row.get("opponent") or "",
            team_key_func,
        )
        features = feature_lookup.get(key)
        if features is None:
            stats["missing_features"] += 1
            continue

        stats["joined_features"] += 1
        position_group = (row.get("position_group") or features["position_group"] or "").strip()
        expected_minutes = _parse_float(row.get("expected_minutes"))
        ev = _parse_float(row.get("ev"))
        fair_odds = _parse_float(row.get("model_fair_odds_atgs"))
        odds_decimal = _parse_float(row.get("odds_decimal"))

        selected = (
            (row.get("method") or "").strip() == "model"
            and position_group in ATTACKING_POSITIONS
            and expected_minutes >= min_expected_minutes
            and features["big_window_matches"] >= big_window
            and features["quality_window_matches"] >= quality_window
            and features["recent_big_chance_misses"] >= min_big_chance_misses
            and features["recent_npxg_per90"] >= min_recent_npxg_per90
            and odds_decimal > fair_odds
            and ev >= min_ev
        )

        loaded.append(
            {
                "season": (row.get("season") or "").strip(),
                "match_date": (row.get("match_date") or "").strip(),
                "bookmaker": (row.get("bookmaker") or "").strip(),
                "player_name": (row.get("player_name") or "").strip(),
                "player_team": (row.get("player_team") or "").strip(),
                "opponent": (row.get("opponent") or "").strip(),
                "position_group": position_group,
                "odds_decimal": odds_decimal,
                "model_fair_odds_atgs": fair_odds,
                "expected_minutes": expected_minutes,
                "ev": ev,
                "pnl": _parse_float(row.get("pnl")),
                "scored": int(_parse_float(row.get("scored"))),
                "recent_big_chances": int(features["recent_big_chances"]),
                "recent_big_chance_misses": int(features["recent_big_chance_misses"]),
                "recent_big_chance_goals": int(features["recent_big_chance_goals"]),
                "recent_big_chance_xg": round(features["recent_big_chance_xg"], 4),
                "recent_npxg_per90": round(features["recent_npxg_per90"], 4),
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
        "avg_recent_npxg_per90": (sum(row["recent_npxg_per90"] for row in rows) / len(rows)) if rows else 0.0,
        "avg_big_chance_misses": (sum(row["recent_big_chance_misses"] for row in rows) / len(rows)) if rows else 0.0,
        "avg_big_chance_xg": (sum(row["recent_big_chance_xg"] for row in rows) / len(rows)) if rows else 0.0,
        "resolved_rows": len(resolved),
        "roi": (sum(row["pnl"] for row in resolved) / len(resolved)) if resolved else 0.0,
        "win_rate": (sum(row["scored"] for row in resolved) / len(resolved)) if resolved else 0.0,
    }


def run_sweeps(rows: List[dict]) -> List[dict]:
    sweep_rows: List[dict] = []
    for miss_cut in (3, 4, 5, 6):
        for npxg_cut in (0.25, 0.30, 0.35):
            subset = [
                row
                for row in rows
                if row["position_group"] in ATTACKING_POSITIONS
                and row["expected_minutes"] >= 70.0
                and row["recent_big_chance_misses"] >= miss_cut
                and row["recent_npxg_per90"] >= npxg_cut
                and row["ev"] >= 0.08
            ]
            summary = _summarize(subset)
            sweep_rows.append(
                {
                    "big_chance_miss_cut": miss_cut,
                    "npxg_per90_cut": npxg_cut,
                    "selected_rows": summary["selected_rows"],
                    "avg_ev": round(summary["avg_ev"], 4),
                    "avg_odds": round(summary["avg_odds"], 4),
                    "roi": round(summary["roi"], 4),
                    "win_rate": round(summary["win_rate"], 4),
                }
            )
    return sweep_rows


def season_rows(rows: List[dict]) -> List[dict]:
    grouped: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["season"]].append(row)

    summaries: List[dict] = []
    for season, season_subset in sorted(grouped.items()):
        summary = _summarize(season_subset)
        summaries.append(
            {
                "season": season,
                "selected_rows": summary["selected_rows"],
                "avg_ev": round(summary["avg_ev"], 4),
                "roi": round(summary["roi"], 4),
                "win_rate": round(summary["win_rate"], 4),
            }
        )
    return summaries


def write_outputs(stats: dict, selected_rows: List[dict], sweeps: List[dict], season_summary: List[dict], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    picks_path = os.path.join(out_dir, "goalscorer-big-chance-backtest.csv")
    sweep_path = os.path.join(out_dir, "goalscorer-big-chance-sweeps.csv")
    summary_path = os.path.join(out_dir, "goalscorer-big-chance-backtest.txt")
    season_path = os.path.join(out_dir, "goalscorer-big-chance-seasons.csv")

    if selected_rows:
        with open(picks_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(selected_rows[0].keys()))
            writer.writeheader()
            writer.writerows(selected_rows)
    else:
        with open(picks_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["no_rows"])

    with open(sweep_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sweeps[0].keys()) if sweeps else ["no_rows"])
        writer.writeheader()
        if sweeps:
            writer.writerows(sweeps)

    with open(season_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(season_summary[0].keys()) if season_summary else ["season"])
        writer.writeheader()
        if season_summary:
            writer.writerows(season_summary)

    summary = _summarize(selected_rows)
    with open(summary_path, "w", encoding="utf-8") as handle:
        handle.write("Goalscorer Big-Chance Regression Backtest\n")
        handle.write("========================================\n\n")
        handle.write(f"Rows loaded:             {stats['rows']:,}\n")
        handle.write(f"Joined features:         {stats['joined_features']:,}\n")
        handle.write(f"Missing features:        {stats['missing_features']:,}\n")
        handle.write(f"Selected rows:           {summary['selected_rows']:,}\n")
        handle.write(f"Average EV:              {summary['avg_ev']:.4f}\n")
        handle.write(f"Average odds:            {summary['avg_odds']:.4f}\n")
        handle.write(f"Average expected mins:   {summary['avg_expected_minutes']:.1f}\n")
        handle.write(f"Average recent npxG/90:  {summary['avg_recent_npxg_per90']:.4f}\n")
        handle.write(f"Average big-chance miss: {summary['avg_big_chance_misses']:.2f}\n")
        handle.write(f"Average big-chance xG:   {summary['avg_big_chance_xg']:.4f}\n")
        handle.write(f"Resolved rows:           {summary['resolved_rows']:,}\n")
        handle.write(f"ROI:                     {summary['roi']:.4f}\n")
        handle.write(f"Win rate:                {summary['win_rate']:.4f}\n\n")
        handle.write("By season\n")
        for row in season_summary:
            handle.write(
                f"  {row['season']}: rows={row['selected_rows']:>3} roi={row['roi']:+.4f} "
                f"win_rate={row['win_rate']:.4f} avg_ev={row['avg_ev']:.4f}\n"
            )
        handle.write("\nSweep highlights\n")
        best_rows = sorted(sweeps, key=lambda row: (-row["roi"], -row["selected_rows"], row["big_chance_miss_cut"]))[:10]
        for row in best_rows:
            handle.write(
                f"  misses>={row['big_chance_miss_cut']}  npxg/90>={row['npxg_per90_cut']:.2f}  "
                f"rows={row['selected_rows']:>3}  roi={row['roi']:+.4f}  win_rate={row['win_rate']:.4f}\n"
            )

    print(f"  Saved: {picks_path}")
    print(f"  Saved: {sweep_path}")
    print(f"  Saved: {season_path}")
    print(f"  Saved: {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest a big-chance regression goalscorer signal")
    parser.add_argument("--backtest", default=DEFAULT_BACKTEST, help="Historical goalscorer backtest CSV")
    parser.add_argument("--data", nargs="+", default=DEFAULT_DATA, help="Player-log CSVs or globs")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--big-window", type=int, default=4, help="Rolling window for big-chance misses")
    parser.add_argument("--quality-window", type=int, default=8, help="Rolling window for npxG/90 quality")
    parser.add_argument("--min-ev", type=float, default=0.08, help="Minimum EV threshold")
    parser.add_argument("--min-expected-minutes", type=float, default=70.0, help="Starter proxy minutes threshold")
    parser.add_argument("--min-recent-npxg-per90", type=float, default=0.30, help="Minimum recent npxG/90")
    parser.add_argument("--min-big-chance-misses", type=int, default=5, help="Minimum recent big-chance misses")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Big Chance Backtest")
    print("=" * 64)

    feature_lookup = build_feature_lookup(args.data, args.big_window, args.quality_window)
    rows, stats = load_backtest_rows(
        args.backtest,
        feature_lookup,
        args.big_window,
        args.quality_window,
        args.min_ev,
        args.min_expected_minutes,
        args.min_recent_npxg_per90,
        args.min_big_chance_misses,
    )
    rows = select_best_price_rows(rows)
    stats["rows"] = len(rows)
    selected_rows = [row for row in rows if row["selected"]]
    sweeps = run_sweeps(rows)
    seasons = season_rows(selected_rows)
    summary = _summarize(selected_rows)

    print(f"  Rows loaded:           {stats['rows']:,}")
    print(f"  Joined features:       {stats['joined_features']:,}")
    print(f"  Missing features:      {stats['missing_features']:,}")
    print(f"  Selected rows:         {summary['selected_rows']:,}")
    print(f"  Average EV:            {summary['avg_ev']:.4f}")
    print(f"  ROI:                   {summary['roi']:.4f}")
    print(f"  Win rate:              {summary['win_rate']:.4f}")

    write_outputs(stats, selected_rows, sweeps, seasons, args.out_dir)
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
