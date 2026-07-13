"""Main-tour venue backtest for tennis aces/DF projections.

The original stage-0 backtest is Slam-only. This script reuses its causal
windowing helpers but evaluates every ATP/WTA main-tour venue present in
data/tennis-props/slam-venue-factors.csv, including grass warm-ups such as
Halle, Stuttgart, Queen's Club, Eastbourne, Hertogenbosch and Nottingham.

Outcome-only: no odds, no ROI, no CLV.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SACKMANN_DIR = ROOT / "data" / "sackmann"
FACTOR_CSV = ROOT / "data" / "tennis-props" / "slam-venue-factors.csv"
OUT_DIR = ROOT / "data" / "tennis-props" / "backtest"
DEFAULT_OUT_TXT = OUT_DIR / "aces-dfs-main-tour-stage0-report.txt"
DEFAULT_OUT_CSV = OUT_DIR / "aces-dfs-main-tour-stage0-rows.csv"

sys.path.insert(0, str(SCRIPTS))


def load_stage0_module():
    path = SCRIPTS / "backtest-tennis-player-props.py"
    spec = importlib.util.spec_from_file_location("stage0_props", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


stage0 = load_stage0_module()


def keyify(value: str | None) -> str:
    import re

    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def read_factor_tournaments(path: Path) -> set[tuple[str, str, str]]:
    allowed: set[tuple[str, str, str]] = set()
    if not path.exists():
        return allowed
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tour = str(row.get("tour") or "").strip().lower()
            tournament = keyify(row.get("tournament"))
            surface = stage0.norm_surface(row.get("surface"))
            if tour in {"atp", "wta"} and tournament and surface in {"Hard", "Clay", "Grass"}:
                allowed.add((tour, tournament, surface))
    return allowed


def tournament_prior_matches(events_by_player, tour: str, player_id: str, tournament_key: str, as_of: date) -> int:
    return sum(
        1
        for event in events_by_player.get((tour, player_id), [])
        if event.match_date < as_of and keyify(event.tournament) == tournament_key
    )


def build_factor_row(*, tour: str, tournament: str, surface: str, as_of: date, matches, events, fallback_best_of: int) -> dict[str, str]:
    target_key = keyify(tournament)
    target_totals = stage0.empty_totals()
    base_totals = stage0.empty_totals()
    match_games_sum = 0
    match_games_n = 0
    for event in events:
        if event.tour != tour or event.surface != surface or event.match_date >= as_of:
            continue
        if keyify(event.tournament) == target_key:
            stage0.add_event(target_totals, event)
        else:
            stage0.add_event(base_totals, event)

    for row in matches:
        row_date = stage0.parse_date(row.get("_date_iso"))
        if row_date is None or row_date >= as_of:
            continue
        if row.get("_tour") != tour or row.get("_surface_norm") != surface or keyify(row.get("tourney_name")) != target_key:
            continue
        games = stage0.parse_int(row.get("_match_games"))
        if games > 0:
            match_games_sum += games
            match_games_n += 1

    base_ace = stage0.safe_div(base_totals["aces"], base_totals["svpt"])
    base_df = stage0.safe_div(base_totals["dfs"], base_totals["svpt"])
    target_ace = stage0.safe_div(target_totals["aces"], target_totals["svpt"])
    target_df = stage0.safe_div(target_totals["dfs"], target_totals["svpt"])
    fallback_games = 38.5 if tour == "atp" and fallback_best_of == 5 else 21.5
    match_games = stage0.safe_div(match_games_sum, match_games_n) or fallback_games
    venue_matches = int(target_totals["matches"] / 2)
    sample_weight = venue_matches / (venue_matches + 100.0) if venue_matches > 0 else 0.0
    raw_ace_factor = (target_ace / base_ace) if target_ace and base_ace else 1.0
    raw_df_factor = (target_df / base_df) if target_df and base_df else 1.0
    return {
        "tour": tour.upper(),
        "tournament": tournament,
        "surface": surface,
        "year": "PAST_ONLY",
        "matches": str(venue_matches),
        "ace_rate": stage0.fmt(target_ace),
        "df_rate": stage0.fmt(target_df),
        "svpt_per_svgame": stage0.fmt(stage0.safe_div(target_totals["svpt"], target_totals["svgms"]) or 6.35, 4),
        "match_games_per_match": stage0.fmt(match_games, 3),
        "tour_surface_baseline_ace": stage0.fmt(base_ace),
        "tour_surface_baseline_df": stage0.fmt(base_df),
        "raw_ace_factor": stage0.fmt(raw_ace_factor, 4),
        "raw_df_factor": stage0.fmt(raw_df_factor, 4),
        "sample_weight": stage0.fmt(sample_weight, 4),
        "ace_factor": stage0.fmt(stage0.shrink_venue_factor(raw_ace_factor, venue_matches), 4),
        "df_factor": stage0.fmt(stage0.shrink_venue_factor(raw_df_factor, venue_matches), 4),
        "sample_flag": "OK" if target_totals["matches"] >= 80 and base_totals["matches"] >= 250 else "LOW_SAMPLE",
    }


def evaluate(sackmann_dir: Path, years: list[int], eval_years: set[int], allowed: set[tuple[str, str, str]]):
    matches, events = stage0.load_data(sackmann_dir, years)
    events_by_player = defaultdict(list)
    for event in events:
        events_by_player[(event.tour, event.player_id)].append(event)

    rows = []
    coverage = defaultdict(int)
    factor_cache = {}
    for row in matches:
        match_date = stage0.parse_date(row.get("_date_iso"))
        if match_date is None or match_date.year not in eval_years:
            continue
        tour = str(row.get("_tour") or "")
        surface = str(row.get("_surface_norm") or "")
        tournament = str(row.get("tourney_name") or "").strip()
        tournament_key = keyify(tournament)
        if (tour, tournament_key, surface) not in allowed:
            coverage[(match_date.year, tour.upper(), surface, "not_in_factor_file")] += 1
            continue
        best_of = stage0.parse_int(row.get("best_of")) or (5 if stage0.slam_name(tournament) and tour == "atp" else 3)
        factor_key = (tour, tournament_key, surface, match_date, best_of)
        factor = factor_cache.get(factor_key)
        if factor is None:
            factor = build_factor_row(
                tour=tour,
                tournament=tournament,
                surface=surface,
                as_of=match_date,
                matches=matches,
                events=events,
                fallback_best_of=best_of,
            )
            factor_cache[factor_key] = factor
        expected_match_games = float(factor.get("match_games_per_match") or (38.5 if best_of == 5 else 21.5))
        sides = (
            ("winner_id", "winner_name", "loser_id", "loser_name", "w"),
            ("loser_id", "loser_name", "winner_id", "winner_name", "l"),
        )
        for id_col, name_col, opp_id_col, opp_name_col, prefix in sides:
            player_id = str(row.get(id_col) or "").strip()
            opponent_id = str(row.get(opp_id_col) or "").strip()
            player = str(row.get(name_col) or "").strip()
            opponent = str(row.get(opp_name_col) or "").strip()
            if not player_id or not opponent_id:
                continue
            player_rows = stage0.build_window_rows(
                tour=tour,
                player_id=player_id,
                player_name=player,
                surface=surface,
                as_of=match_date,
                events_by_player=events_by_player,
            )
            opponent_rows = stage0.build_window_rows(
                tour=tour,
                player_id=opponent_id,
                player_name=opponent,
                surface=surface,
                as_of=match_date,
                events_by_player=events_by_player,
            )
            same = stage0.build_same_tournament_row(
                tour=tour,
                player_id=player_id,
                tourney_id=str(row.get("tourney_id") or ""),
                as_of=match_date,
                events_by_player=events_by_player,
            )
            projection = stage0.project_player(
                tour=tour,
                player_rows=player_rows,
                opponent_rows=opponent_rows,
                factor_row=factor,
                expected_match_games=expected_match_games,
                slam_matches=tournament_prior_matches(events_by_player, tour, player_id, tournament_key, match_date),
                same_tournament_row=same,
                apply_slam_bias_correction=False,
            )
            naive_aces, naive_dfs = stage0.naive_projection(player_rows, factor, projection.expected_service_points, tour)
            rows.append(
                stage0.EvalRow(
                    tour=tour.upper(),
                    year=match_date.year,
                    date=match_date,
                    tournament=tournament,
                    round=str(row.get("round") or ""),
                    surface=surface,
                    player_id=player_id,
                    player=player,
                    opponent_id=opponent_id,
                    opponent=opponent,
                    actual_aces=stage0.parse_int(row.get(f"{prefix}_ace")),
                    actual_dfs=stage0.parse_int(row.get(f"{prefix}_df")),
                    projected_aces=projection.expected_aces,
                    projected_dfs=projection.expected_dfs,
                    naive_aces=naive_aces,
                    naive_dfs=naive_dfs,
                    ace_confidence=projection.ace_confidence,
                    df_confidence=projection.df_confidence,
                    notes=";".join(list(projection.notes) + [f"VENUE_SCOPE:{tournament_key}", f"VENUE_SAMPLE:{factor.get('sample_flag')}"]),
                    actual_service_points=stage0.parse_int(row.get(f"{prefix}_svpt")),
                    expected_service_points=projection.expected_service_points,
                    candidate_expected_service_points=projection.expected_service_points,
                    candidate_projected_aces=projection.expected_aces,
                    candidate_projected_dfs=projection.expected_dfs,
                    player_service_point_win=projection.player_service_point_win,
                    opponent_service_point_win=projection.opponent_service_point_win,
                    same_tournament_matches=projection.same_tournament_matches,
                    ace_rate_pre_opponent=projection.ace_rate_pre_opponent,
                    opponent_return_ratio=projection.opponent_return_ratio,
                    opponent_return_factor=projection.opponent_return_factor,
                )
            )
            coverage[(match_date.year, tour.upper(), surface, "included_sides")] += 1
    return rows, coverage


def write_report(path: Path, rows, coverage, years: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "Tennis Main-Tour Aces/DF Stage-0 Backtest",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Evaluation years: {', '.join(map(str, years))}",
        "Outcome-only validation. No odds, no ROI, no CLV.",
        "Scope: tournaments present in data/tennis-props/slam-venue-factors.csv.",
        "",
        "Coverage",
    ]
    for key, count in sorted(coverage.items()):
        lines.append(f"- {key}: {count}")
    lines.append("")

    def section(title: str, items):
        lines.append(title)
        lines.append("Bucket                         N  AceMAE model/naive  AceLL model/naive  DfMAE model/naive  DfLL model/naive  AceBias  DfBias")
        for key, summary in items:
            lines.append(
                f"{key[:28]:28s} {int(summary['n']):4d}  "
                f"{stage0.fmt_num(summary['aces_mae'])}/{stage0.fmt_num(summary['aces_naive_mae'])}        "
                f"{stage0.fmt_num(summary['aces_synth_logloss'])}/{stage0.fmt_num(summary['aces_naive_synth_logloss'])}        "
                f"{stage0.fmt_num(summary['dfs_mae'])}/{stage0.fmt_num(summary['dfs_naive_mae'])}        "
                f"{stage0.fmt_num(summary['dfs_synth_logloss'])}/{stage0.fmt_num(summary['dfs_naive_synth_logloss'])}        "
                f"{summary['aces_bias']:+.3f}  {summary['dfs_bias']:+.3f}"
            )
        lines.append("")

    section("Overall", [("all", stage0.bucket_summary(rows))])
    section("By tour", stage0.group_rows(rows, lambda r: r.tour))
    section("By surface", stage0.group_rows(rows, lambda r: f"{r.tour} {r.surface}"))
    section("By tournament", stage0.group_rows(rows, lambda r: f"{r.tour} {r.tournament}"))
    section("By year", stage0.group_rows(rows, lambda r: str(r.year)))
    lines.append("Decision")
    if rows:
        overall = stage0.bucket_summary(rows)
        if overall["aces_mae"] < overall["aces_naive_mae"]:
            lines.append("- Aces beat naive on this main-tour venue sample.")
        else:
            lines.append("- Aces do not beat naive on this main-tour venue sample.")
        if overall["dfs_mae"] < overall["dfs_naive_mae"]:
            lines.append("- DFs beat naive on this main-tour venue sample.")
        else:
            lines.append("- DFs do not beat naive on this main-tour venue sample.")
    lines.append("- This is not promotion evidence until ATP 2025/2026 Sackmann rows are present and Bet365 lines settle.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest main-tour tennis aces/DF projections for factor-file venues.")
    parser.add_argument("--sackmann-dir", type=Path, default=SACKMANN_DIR)
    parser.add_argument("--factor-csv", type=Path, default=FACTOR_CSV)
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--eval-years", nargs="+", type=int, default=[2024, 2025])
    parser.add_argument("--out-txt", type=Path, default=DEFAULT_OUT_TXT)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    allowed = read_factor_tournaments(args.factor_csv)
    years = list(range(args.start_year, args.end_year + 1))
    rows, coverage = evaluate(args.sackmann_dir, years, set(args.eval_years), allowed)
    if not rows:
        raise SystemExit("No main-tour prop backtest rows generated.")
    stage0.write_rows(args.out_csv, rows)
    write_report(args.out_txt, rows, coverage, args.eval_years)
    print(f"Wrote {args.out_txt}")
    print(f"Wrote {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
