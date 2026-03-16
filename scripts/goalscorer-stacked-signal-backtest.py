#!/usr/bin/env python3
"""
Backtest a stacked selective ATGS signal rather than broad market pricing.

Phase 1 uses only features we can validate historically from the current
dataset and archive:
  - attacking role
  - starter proxy via expected minutes
  - recent open-play xG/90 quality
  - finishing-luck drought
  - fixture difficulty swing
  - best-price EV
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
from typing import Dict, List, Optional

from goalscorer_penalty_utils import best_name_match, load_penalty_hierarchy, penalty_transfer_info


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKTEST = "data/goalscorer/test-run/historical-all-rawshare/goalscorer-historical-backtest.csv"
DEFAULT_DATA = [
    "data/goalscorer/serie-a-player-match-logs-2023-2024.csv",
    "data/goalscorer/serie-a-player-match-logs-2024-2025.csv",
    "data/goalscorer/serie-a-player-match-logs-2025-2026.csv",
]
DEFAULT_OUT_DIR = "data/goalscorer/test-run/historical-all-rawshare/stacked-signal"
DEFAULT_PENALTY_HIERARCHY = "data/goalscorer/serie-a-penalty-takers.json"
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


def select_best_price_rows(rows: List[dict]) -> List[dict]:
    best_by_pick: Dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (row["match_date"], row["player_name"], row["player_team"])
        current = best_by_pick.get(key)
        if current is None or row["odds_decimal"] > current["odds_decimal"]:
            best_by_pick[key] = row
    return list(best_by_pick.values())


def build_feature_lookup(
    data_paths: List[str],
    recent_window: int,
    recent_fixture_window: int,
    penalty_hierarchy_path: str,
) -> Dict[tuple[str, str, str, str], dict]:
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    load_match_logs = model_mod["load_match_logs"]
    TeamHistory = model_mod["TeamHistory"]
    team_key_func = model_mod["_team_key"]
    LEAGUE_AVG = model_mod["LEAGUE_AVG"]
    penalty_hierarchy = load_penalty_hierarchy(ROOT / penalty_hierarchy_path, team_key_func=team_key_func)

    rows = load_match_logs(data_paths)
    player_histories: Dict[str, List[dict]] = defaultdict(list)
    team_histories: Dict[str, object] = defaultdict(TeamHistory)
    feature_lookup: Dict[tuple[str, str, str, str], dict] = {}

    history_index = 0
    while history_index < len(rows):
        batch_date = rows[history_index].match_date
        batch = []
        while history_index < len(rows) and rows[history_index].match_date == batch_date:
            batch.append(rows[history_index])
            history_index += 1

        team_match_summaries: Dict[tuple[str, str, bool], dict] = {}
        team_available_names: Dict[str, List[str]] = defaultdict(list)
        for row in batch:
            key = (row.team_key, row.opponent_key, row.is_home)
            summary = team_match_summaries.setdefault(
                key,
                {
                    "team_npxg": None,
                    "team_xg": None,
                    "team_xga": None,
                    "team_penalties_attempted": 0,
                },
            )
            summary["team_penalties_attempted"] += row.penalties_attempted
            if row.minutes > 0:
                team_available_names[row.team_key].append(row.player_name)
            if row.team_xg is not None and summary["team_xg"] is None:
                summary["team_xg"] = row.team_xg
            if row.team_xga is not None and summary["team_xga"] is None:
                summary["team_xga"] = row.team_xga
        for summary in team_match_summaries.values():
            if summary["team_xg"] is not None:
                summary["team_npxg"] = max(
                    0.0,
                    summary["team_xg"] - (summary["team_penalties_attempted"] * LEAGUE_AVG["penalty_conversion"]),
                )

        team_penalty_events = {
            team_key: penalty_transfer_info(penalty_hierarchy.get(team_key), names)
            for team_key, names in team_available_names.items()
        }

        for row in batch:
            history = player_histories[row.player_id]
            recent = history[-recent_window:]
            recent_minutes = sum(match["minutes"] for match in recent)
            recent_npxg = sum(match["npxg"] for match in recent)
            recent_np_goals = sum(match["np_goals"] for match in recent)
            recent_npxg_per90 = (recent_npxg / (recent_minutes / 90.0)) if recent_minutes > 0 else 0.0
            finishing_luck = recent_np_goals - recent_npxg

            last_fixture_block = history[-recent_fixture_window:]
            last_fixture_xga = [match["opp_xga_pre"] for match in last_fixture_block if match["opp_xga_pre"] is not None]
            last_fixture_avg_xga = (
                sum(last_fixture_xga) / len(last_fixture_xga) if last_fixture_xga else None
            )

            opponent_summary = team_histories[row.opponent_key].summary()
            next_opponent_xga = (
                opponent_summary["xga_per_match"]
                if opponent_summary is not None
                else LEAGUE_AVG["team_xga_per_match"]
            )
            fixture_swing = (
                next_opponent_xga / last_fixture_avg_xga
                if last_fixture_avg_xga and last_fixture_avg_xga > 0
                else None
            )
            team_penalty_event = team_penalty_events.get(row.team_key, {})
            penalty_transfer = bool(team_penalty_event.get("penalty_transfer")) and (
                best_name_match(row.player_name, [team_penalty_event.get("active_taker", "")]) is not None
            )

            feature_lookup[
                _join_key(
                    row.match_date_str,
                    row.player_name,
                    row.team,
                    row.opponent,
                    team_key_func,
                )
            ] = {
                "player_id": row.player_id,
                "prior_matches": len(history),
                "recent_matches": len(recent),
                "recent_npxg": recent_npxg,
                "recent_np_goals": recent_np_goals,
                "recent_npxg_per90": recent_npxg_per90,
                "finishing_luck": finishing_luck,
                "last_fixture_avg_xga": last_fixture_avg_xga,
                "next_opponent_xga": next_opponent_xga,
                "fixture_swing": fixture_swing,
                "position_group": (row.position or "").split(",")[0].strip() or "Unknown",
                "team_penalty_transfer": bool(team_penalty_event.get("penalty_transfer")),
                "penalty_transfer": penalty_transfer,
                "penalty_transfer_from": team_penalty_event.get("inherited_from", "") if penalty_transfer else "",
                "penalty_transfer_level": team_penalty_event.get("transfer_level", "") if penalty_transfer else "",
            }

        for row in batch:
            opponent_summary = team_histories[row.opponent_key].summary()
            opponent_xga_pre = (
                opponent_summary["xga_per_match"]
                if opponent_summary is not None
                else LEAGUE_AVG["team_xga_per_match"]
            )
            player_histories[row.player_id].append(
                {
                    "minutes": row.minutes,
                    "npxg": row.npxg,
                    "np_goals": max(row.goals - row.penalties_scored, 0),
                    "opp_xga_pre": opponent_xga_pre,
                }
            )

        for (team_key, _, _), summary in team_match_summaries.items():
            team_histories[team_key].add_match(summary)

    return feature_lookup


def load_backtest_rows(
    path: str,
    feature_lookup: Dict[tuple[str, str, str, str], dict],
    min_ev: float,
    min_expected_minutes: float,
    min_recent_matches: int,
    min_recent_npxg_per90: float,
    max_finishing_luck: float,
    min_fixture_swing: float,
    penalty_transfer_filter: str,
) -> tuple[List[dict], dict]:
    model_mod = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_model")
    team_key_func = model_mod["_team_key"]

    rows = _load_csv(path)
    loaded: List[dict] = []
    stats = {
        "rows": len(rows),
        "joined_features": 0,
        "missing_features": 0,
    }

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
        fixture_swing = features["fixture_swing"]
        penalty_transfer = bool(features["penalty_transfer"])
        transfer_filter_pass = (
            penalty_transfer_filter == "any"
            or (penalty_transfer_filter == "only" and penalty_transfer)
            or (penalty_transfer_filter == "exclude" and not penalty_transfer)
        )

        base_eligible = (
            (row.get("method") or "").strip() == "model"
            and position_group in ATTACKING_POSITIONS
            and expected_minutes >= min_expected_minutes
            and features["recent_matches"] >= min_recent_matches
            and features["recent_npxg_per90"] >= min_recent_npxg_per90
            and features["finishing_luck"] <= max_finishing_luck
            and fixture_swing is not None
            and fixture_swing >= min_fixture_swing
            and odds_decimal > fair_odds
            and ev >= min_ev
            and transfer_filter_pass
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
                "recent_matches": int(features["recent_matches"]),
                "recent_npxg": round(features["recent_npxg"], 4),
                "recent_np_goals": round(features["recent_np_goals"], 4),
                "recent_npxg_per90": round(features["recent_npxg_per90"], 4),
                "finishing_luck": round(features["finishing_luck"], 4),
                "last_fixture_avg_xga": round(features["last_fixture_avg_xga"], 4) if features["last_fixture_avg_xga"] is not None else "",
                "next_opponent_xga": round(features["next_opponent_xga"], 4),
                "fixture_swing": round(features["fixture_swing"], 4) if features["fixture_swing"] is not None else "",
                "penalty_transfer": int(penalty_transfer),
                "penalty_transfer_from": features["penalty_transfer_from"],
                "penalty_transfer_level": features["penalty_transfer_level"],
                "selected": base_eligible,
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
        "avg_finishing_luck": (sum(row["finishing_luck"] for row in rows) / len(rows)) if rows else 0.0,
        "avg_fixture_swing": (
            sum(float(row["fixture_swing"]) for row in rows if row["fixture_swing"] != "") / len(rows)
        ) if rows else 0.0,
        "penalty_transfer_rows": sum(1 for row in rows if row["penalty_transfer"]),
        "resolved_rows": len(resolved),
        "roi": (sum(row["pnl"] for row in resolved) / len(resolved)) if resolved else 0.0,
        "win_rate": (sum(row["scored"] for row in resolved) / len(resolved)) if resolved else 0.0,
    }


def run_sweeps(rows: List[dict]) -> List[dict]:
    results: List[dict] = []
    for finishing_luck_cut in (-0.25, -0.5, -0.75, -1.0):
        for fixture_swing_cut in (1.1, 1.2, 1.3, 1.4):
            for transfer_filter in ("any", "only", "exclude"):
                subset = [
                    row for row in rows
                    if row["position_group"] in ATTACKING_POSITIONS
                    and row["expected_minutes"] >= 70.0
                    and row["recent_matches"] >= 8
                    and row["recent_npxg_per90"] >= 0.30
                    and row["finishing_luck"] <= finishing_luck_cut
                    and row["fixture_swing"] != ""
                    and float(row["fixture_swing"]) >= fixture_swing_cut
                    and row["ev"] >= 0.08
                    and (
                        transfer_filter == "any"
                        or (transfer_filter == "only" and row["penalty_transfer"])
                        or (transfer_filter == "exclude" and not row["penalty_transfer"])
                    )
                ]
                summary = _summarize(subset)
                results.append(
                    {
                        "finishing_luck_cut": finishing_luck_cut,
                        "fixture_swing_cut": fixture_swing_cut,
                        "penalty_transfer_filter": transfer_filter,
                        **summary,
                    }
                )
    return results


def write_outputs(stats: dict, selected_rows: List[dict], sweep_rows: List[dict], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    selected_path = os.path.join(out_dir, "goalscorer-stacked-signal-backtest.csv")
    summary_path = os.path.join(out_dir, "goalscorer-stacked-signal-backtest.txt")
    sweep_path = os.path.join(out_dir, "goalscorer-stacked-signal-sweeps.csv")

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
        handle.write("Goalscorer Stacked Signal Backtest\n")
        handle.write("=================================\n\n")
        handle.write(f"Rows loaded:              {stats['rows']:,}\n")
        handle.write(f"Joined features:          {stats['joined_features']:,}\n")
        handle.write(f"Missing features:         {stats['missing_features']:,}\n")
        handle.write(f"Selected rows:            {summary['selected_rows']:,}\n")
        handle.write(f"Average EV:               {summary['avg_ev']:.4f}\n")
        handle.write(f"Average odds:             {summary['avg_odds']:.4f}\n")
        handle.write(f"Average expected mins:    {summary['avg_expected_minutes']:.1f}\n")
        handle.write(f"Average recent npxG/90:   {summary['avg_recent_npxg_per90']:.4f}\n")
        handle.write(f"Average finishing luck:   {summary['avg_finishing_luck']:.4f}\n")
        handle.write(f"Average fixture swing:    {summary['avg_fixture_swing']:.4f}\n")
        handle.write(f"Penalty transfer rows:    {summary['penalty_transfer_rows']:,}\n")
        handle.write(f"Resolved rows:            {summary['resolved_rows']:,}\n")
        handle.write(f"ROI:                      {summary['roi']:.4f}\n")
        handle.write(f"Win rate:                 {summary['win_rate']:.4f}\n")

        if sweep_rows:
            handle.write("\nSweeps\n")
            handle.write("------\n")
            best_rows = sorted(sweep_rows, key=lambda row: (-row["roi"], -row["selected_rows"], row["fixture_swing_cut"], row["finishing_luck_cut"]))[:10]
            for row in best_rows:
                handle.write(
                    f"luck<={row['finishing_luck_cut']:>5.2f}  swing>={row['fixture_swing_cut']:.1f}  "
                    f"transfer={row['penalty_transfer_filter']:<7}  "
                    f"sel={row['selected_rows']:>4}  roi={row['roi']:+.4f}  avg_ev={row['avg_ev']:+.4f}\n"
                )

    print(f"  Saved: {selected_path}")
    print(f"  Saved: {sweep_path}")
    print(f"  Saved: {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest a stacked selective ATGS signal")
    parser.add_argument("--backtest", default=DEFAULT_BACKTEST, help="Historical goalscorer backtest CSV")
    parser.add_argument("--data", nargs="+", default=DEFAULT_DATA, help="Historical player-log CSVs or globs")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--recent-window", type=int, default=8, help="Rolling window for finishing-luck and npxG form")
    parser.add_argument("--fixture-window", type=int, default=3, help="Number of recent opponents for the fixture swing baseline")
    parser.add_argument("--min-ev", type=float, default=0.08, help="Minimum EV threshold")
    parser.add_argument("--min-expected-minutes", type=float, default=70.0, help="Starter proxy minutes threshold")
    parser.add_argument("--min-recent-matches", type=int, default=8, help="Minimum matches inside the recent form window")
    parser.add_argument("--min-recent-npxg-per90", type=float, default=0.30, help="Minimum recent npxG/90")
    parser.add_argument("--max-finishing-luck", type=float, default=-0.5, help="Maximum finishing luck (goals - npxG)")
    parser.add_argument("--min-fixture-swing", type=float, default=1.3, help="Minimum fixture swing")
    parser.add_argument("--penalty-hierarchy", default=DEFAULT_PENALTY_HIERARCHY, help="Penalty taker hierarchy JSON")
    parser.add_argument(
        "--penalty-transfer-filter",
        choices=("any", "only", "exclude"),
        default="any",
        help="Require, exclude, or ignore penalty-transfer matches",
    )
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Stacked Signal Backtest")
    print("=" * 64)

    feature_lookup = build_feature_lookup(args.data, args.recent_window, args.fixture_window, args.penalty_hierarchy)
    rows, stats = load_backtest_rows(
        args.backtest,
        feature_lookup,
        args.min_ev,
        args.min_expected_minutes,
        args.min_recent_matches,
        args.min_recent_npxg_per90,
        args.max_finishing_luck,
        args.min_fixture_swing,
        args.penalty_transfer_filter,
    )
    rows = select_best_price_rows(rows)
    stats["rows"] = len(rows)
    selected_rows = [row for row in rows if row["selected"]]
    sweeps = run_sweeps(rows)
    summary = _summarize(selected_rows)

    print(f"  Rows loaded:           {stats['rows']:,}")
    print(f"  Joined features:       {stats['joined_features']:,}")
    print(f"  Selected rows:         {summary['selected_rows']:,}")
    print(f"  Penalty filter:        {args.penalty_transfer_filter}")
    print(f"  Transfer rows:         {summary['penalty_transfer_rows']:,}")
    print(f"  Average EV:            {summary['avg_ev']:.4f}")
    print(f"  ROI:                   {summary['roi']:.4f}")
    print(f"  Win rate:              {summary['win_rate']:.4f}")

    write_outputs(stats, selected_rows, sweeps, args.out_dir)
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
