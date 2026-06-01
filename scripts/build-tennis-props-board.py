#!/usr/bin/env python3
"""Build an internal ATP/WTA Slam aces/DF board with break-count context."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from tennis_props_model import project_player


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ONCOURT_DIR = DATA_DIR / "oncourt"
SACKMANN_DIR = DATA_DIR / "sackmann"
PROPS_DIR = DATA_DIR / "tennis-props"
INBOX_DIR = PROPS_DIR / "inbox"
DEFAULT_BASELINE = PROPS_DIR / "player-props-baseline.csv"
DEFAULT_FACTORS = PROPS_DIR / "slam-venue-factors.csv"
DEFAULT_ALIASES = PROPS_DIR / "player-name-aliases.csv"
DEFAULT_OUT = PROPS_DIR / "player-props-board.csv"
SURFACE_BY_COURT = {
    "1": "Hard",
    "2": "Clay",
    "3": "Grass",
    "4": "Hard",
}
ROUND_BY_ID = {
    "1": "F",
    "2": "SF",
    "3": "QF",
    "4": "R16",
    "5": "R32",
    "6": "R64",
    "7": "R128",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def norm_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def parse_float(value: object, default: float | None = None) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def parse_int(value: object, default: int = 0) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def add_stat_totals(
    target: dict[str, int],
    *,
    aces: object,
    dfs: object,
    svpt: object,
    breaks_for: object,
    broken: object,
    return_games: object,
) -> None:
    target["matches"] = target.get("matches", 0) + 1
    target["aces"] = target.get("aces", 0) + parse_int(aces)
    target["dfs"] = target.get("dfs", 0) + parse_int(dfs)
    target["svpt"] = target.get("svpt", 0) + parse_int(svpt)
    target["breaks_for"] = target.get("breaks_for", 0) + parse_int(breaks_for)
    target["broken"] = target.get("broken", 0) + parse_int(broken)
    target["return_games"] = target.get("return_games", 0) + parse_int(return_games)


def broken_from_stat(stat: dict[str, str], prefix: str) -> int:
    return max(0, parse_int(stat.get(f"{prefix}_bpfaced")) - parse_int(stat.get(f"{prefix}_bpsaved")))


def fmt(value: float | None, digits: int = 3) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def slam_name(value: object) -> str | None:
    lower = str(value or "").lower()
    if "roland garros" in lower or "french open" in lower:
        return "Roland Garros"
    if "wimbledon" in lower:
        return "Wimbledon"
    if "australian open" in lower:
        return "Australian Open"
    if "us open" in lower or "u.s. open" in lower:
        return "US Open"
    return None


def load_baseline(path: Path) -> dict[tuple[str, str, str], dict[str, dict[str, str]]]:
    out: dict[tuple[str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in read_csv(path):
        full_name_norm = norm_name(row.get("player_name"))
        key = (
            str(row.get("tour") or "").upper(),
            full_name_norm,
            str(row.get("surface") or "").strip(),
        )
        out[key][str(row.get("window") or "")] = row
    return out


def load_factors(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    factors: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in read_csv(path):
        if str(row.get("year") or "") != "ALL":
            continue
        key = (
            str(row.get("tour") or "").upper(),
            str(row.get("tournament") or "").strip(),
            str(row.get("surface") or "").strip(),
        )
        factors[key] = row
    return factors


def load_aliases(path: Path) -> dict[tuple[str, str], str]:
    aliases: dict[tuple[str, str], str] = {}
    for row in read_csv(path):
        tour = str(row.get("tour") or "").upper()
        alias = norm_name(row.get("alias"))
        player_name = norm_name(row.get("player_name"))
        if tour and alias and player_name:
            aliases[(tour, alias)] = player_name
    return aliases


def load_oncourt_player_names(tour: str) -> dict[str, str]:
    names = {}
    for row in read_csv(ONCOURT_DIR / f"players_{tour.lower()}.csv"):
        pid = str(row.get("id") or "").strip()
        name = str(row.get("name") or "").strip()
        if pid and name:
            names[pid] = name
    return names


def load_oncourt_tours(tour: str) -> dict[str, dict[str, str]]:
    tours = {}
    for row in read_csv(ONCOURT_DIR / f"tours_{tour.lower()}.csv"):
        tid = str(row.get("id") or "").strip()
        if tid:
            tours[tid] = row
    return tours


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def load_slam_samples(as_of: date) -> dict[tuple[str, str, str], int]:
    samples: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for tour in ("atp", "wta"):
        for path in sorted(SACKMANN_DIR.glob(f"{tour}_matches_*.csv")):
            if "qual_chall" in path.name:
                continue
            for row in read_csv(path):
                match_date = parse_date(row.get("tourney_date"))
                tournament = slam_name(row.get("tourney_name"))
                if match_date is None or match_date >= as_of or not tournament:
                    continue
                winner_norm = norm_name(row.get("winner_name"))
                loser_norm = norm_name(row.get("loser_name"))
                key_w = (tour.upper(), winner_norm, tournament)
                key_l = (tour.upper(), loser_norm, tournament)
                match_id = "|".join(
                    [
                        str(row.get("tourney_id") or ""),
                        str(row.get("match_num") or ""),
                        str(row.get("winner_id") or ""),
                        str(row.get("loser_id") or ""),
                    ]
                )
                samples[key_w].add(match_id)
                samples[key_l].add(match_id)
    return {key: len(value) for key, value in samples.items()}


def oncourt_schedule_rows(tour_code: str, include_completed: bool, board_date: str) -> list[dict[str, str]]:
    tour_lower = tour_code.lower()
    player_names = load_oncourt_player_names(tour_lower)
    tours = load_oncourt_tours(tour_lower)
    rows: list[dict[str, str]] = []
    for row in read_csv(ONCOURT_DIR / f"today_{tour_lower}.csv"):
        if not include_completed and str(row.get("result") or "").strip():
            continue
        tour = tours.get(str(row.get("tour_id") or "").strip()) or {}
        tournament = slam_name(tour.get("name"))
        if not tournament:
            continue
        p1 = player_names.get(str(row.get("player1_id") or "").strip(), "")
        p2 = player_names.get(str(row.get("player2_id") or "").strip(), "")
        if not p1 or not p2:
            continue
        if norm_name(p1) == "unknown player" or norm_name(p2) == "unknown player":
            continue
        if "/" in p1 or "/" in p2:
            continue
        rows.append(
            {
                "date": board_date,
                "tour": tour_code.upper(),
                "tour_id": str(row.get("tour_id") or "").strip(),
                "tournament": tournament,
                "round": ROUND_BY_ID.get(str(row.get("round_id") or ""), str(row.get("round_id") or "")),
                "surface": SURFACE_BY_COURT.get(str(tour.get("court_id") or ""), "Clay"),
                "player1": p1,
                "player2": p2,
                "player1_id": str(row.get("player1_id") or "").strip(),
                "player2_id": str(row.get("player2_id") or "").strip(),
                "source": f"oncourt_today_{tour_lower}",
            }
        )
    return rows


def wta_schedule_rows(path: Path) -> list[dict[str, str]]:
    rows = []
    for row in read_csv(path):
        p1 = str(row.get("player1") or "").strip()
        p2 = str(row.get("player2") or "").strip()
        if not p1 or not p2:
            continue
        tournament = slam_name(row.get("tournament")) or str(row.get("tournament") or "Roland Garros").strip()
        rows.append(
            {
                "date": str(row.get("date") or "").strip(),
                "tour": "WTA",
                "tour_id": str(row.get("tour_id") or "").strip(),
                "tournament": tournament,
                "round": str(row.get("round") or "").strip(),
                "surface": str(row.get("surface") or "Clay").strip() or "Clay",
                "player1": p1,
                "player2": p2,
                "player1_id": str(row.get("player1_id") or "").strip(),
                "player2_id": str(row.get("player2_id") or "").strip(),
                "source": str(path),
            }
        )
    return rows


def load_current_tournament_stats(schedules: list[dict[str, str]], as_of: date) -> dict[tuple[str, str, str], dict[str, str]]:
    """Same-edition aces/DFs from OnCourt completed matches."""
    tour_ids_by_tour: dict[str, set[str]] = defaultdict(set)
    for row in schedules:
        tour = str(row.get("tour") or "").upper()
        tour_id = str(row.get("tour_id") or "").strip()
        if tour in {"ATP", "WTA"} and tour_id:
            tour_ids_by_tour[tour].add(tour_id)
    if not tour_ids_by_tour:
        return {}

    totals: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
    for tour, tour_ids in tour_ids_by_tour.items():
        tour_lower = tour.lower()
        stat_index: dict[tuple[str, str, str, str], dict[str, str]] = {}
        for row in read_csv(ONCOURT_DIR / f"stat_{tour_lower}.csv"):
            tour_id = str(row.get("tour_id") or "").strip()
            if tour_id not in tour_ids:
                continue
            key = (
                str(row.get("winner_id") or "").strip(),
                str(row.get("loser_id") or "").strip(),
                tour_id,
                str(row.get("round_id") or "").strip(),
            )
            stat_index.setdefault(key, row)

        for game in read_csv(ONCOURT_DIR / f"games_{tour_lower}.csv"):
            tour_id = str(game.get("tour_id") or "").strip()
            if tour_id not in tour_ids:
                continue
            match_date = parse_date(game.get("date"))
            if match_date is None or match_date >= as_of:
                continue
            winner_id = str(game.get("winner_id") or "").strip()
            loser_id = str(game.get("loser_id") or "").strip()
            if not winner_id or not loser_id or winner_id == loser_id:
                continue
            stat = stat_index.get((winner_id, loser_id, tour_id, str(game.get("round_id") or "").strip()))
            if not stat:
                continue
            add_stat_totals(
                totals[(tour, tour_id, winner_id)],
                aces=stat.get("w_ace"),
                dfs=stat.get("w_df"),
                svpt=stat.get("w_svpt"),
                breaks_for=stat.get("w_bpw"),
                broken=broken_from_stat(stat, "w"),
                return_games=stat.get("l_SvGms"),
            )
            add_stat_totals(
                totals[(tour, tour_id, loser_id)],
                aces=stat.get("l_ace"),
                dfs=stat.get("l_df"),
                svpt=stat.get("l_svpt"),
                breaks_for=stat.get("l_bpw"),
                broken=broken_from_stat(stat, "l"),
                return_games=stat.get("w_SvGms"),
            )

    return {
        key: {field: str(value) for field, value in values.items()}
        for key, values in totals.items()
    }


def load_current_tournament_logs(schedules: list[dict[str, str]], as_of: date) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    """Per-round aces/DF logs for players still in the current Slam draw."""
    tour_ids_by_tour: dict[str, set[str]] = defaultdict(set)
    for row in schedules:
        tour = str(row.get("tour") or "").upper()
        tour_id = str(row.get("tour_id") or "").strip()
        if tour in {"ATP", "WTA"} and tour_id:
            tour_ids_by_tour[tour].add(tour_id)
    if not tour_ids_by_tour:
        return {}

    logs: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for tour, tour_ids in tour_ids_by_tour.items():
        tour_lower = tour.lower()
        player_names = load_oncourt_player_names(tour_lower)
        stat_index: dict[tuple[str, str, str, str], dict[str, str]] = {}
        for row in read_csv(ONCOURT_DIR / f"stat_{tour_lower}.csv"):
            tour_id = str(row.get("tour_id") or "").strip()
            if tour_id not in tour_ids:
                continue
            key = (
                str(row.get("winner_id") or "").strip(),
                str(row.get("loser_id") or "").strip(),
                tour_id,
                str(row.get("round_id") or "").strip(),
            )
            stat_index.setdefault(key, row)

        for game in read_csv(ONCOURT_DIR / f"games_{tour_lower}.csv"):
            tour_id = str(game.get("tour_id") or "").strip()
            if tour_id not in tour_ids:
                continue
            match_date = parse_date(game.get("date"))
            if match_date is None or match_date >= as_of:
                continue
            winner_id = str(game.get("winner_id") or "").strip()
            loser_id = str(game.get("loser_id") or "").strip()
            round_id = str(game.get("round_id") or "").strip()
            if not winner_id or not loser_id or winner_id == loser_id:
                continue
            stat = stat_index.get((winner_id, loser_id, tour_id, round_id))
            if not stat:
                continue
            winner_name = player_names.get(winner_id, winner_id)
            loser_name = player_names.get(loser_id, loser_id)
            base = {
                "date": match_date.isoformat(),
                "round": ROUND_BY_ID.get(round_id, round_id),
                "result": str(game.get("result") or "").strip(),
            }
            logs[(tour, tour_id, winner_id)].append(
                {
                    **base,
                    "opponent": loser_name,
                    "aces": str(parse_int(stat.get("w_ace"))),
                    "dfs": str(parse_int(stat.get("w_df"))),
                    "breaks_for": str(parse_int(stat.get("w_bpw"))),
                    "broken": str(broken_from_stat(stat, "w")),
                    "total_breaks": str(parse_int(stat.get("w_bpw")) + broken_from_stat(stat, "w")),
                    "svpt": str(parse_int(stat.get("w_svpt"))),
                }
            )
            logs[(tour, tour_id, loser_id)].append(
                {
                    **base,
                    "opponent": winner_name,
                    "aces": str(parse_int(stat.get("l_ace"))),
                    "dfs": str(parse_int(stat.get("l_df"))),
                    "breaks_for": str(parse_int(stat.get("l_bpw"))),
                    "broken": str(broken_from_stat(stat, "l")),
                    "total_breaks": str(parse_int(stat.get("l_bpw")) + broken_from_stat(stat, "l")),
                    "svpt": str(parse_int(stat.get("l_svpt"))),
                }
            )

    for player_logs in logs.values():
        player_logs.sort(key=lambda item: (item.get("date", ""), item.get("round", "")))
        for index, item in enumerate(player_logs, start=1):
            item["draw_round"] = item.get("round", "")
            item["round"] = f"Round {index}"
    return logs


def project_side(
    *,
    schedule: dict[str, str],
    player: str,
    opponent: str,
    player_id: str,
    baseline: dict[tuple[str, str, str], dict[str, dict[str, str]]],
    factors: dict[tuple[str, str, str], dict[str, str]],
    slam_samples: dict[tuple[str, str, str], int],
    aliases: dict[tuple[str, str], str],
    current_tournament_stats: dict[tuple[str, str, str], dict[str, str]],
    current_tournament_logs: dict[tuple[str, str, str], list[dict[str, str]]],
) -> dict[str, str]:
    tour = schedule["tour"].upper()
    surface = schedule["surface"]
    tournament = schedule["tournament"]
    player_lookup = aliases.get((tour, norm_name(player)), norm_name(player))
    opponent_lookup = aliases.get((tour, norm_name(opponent)), norm_name(opponent))
    player_rows = baseline.get((tour, player_lookup, surface), {})
    opponent_rows = baseline.get((tour, opponent_lookup, surface), {})
    factor = factors.get((tour, tournament, surface)) or {}
    expected_games = parse_float(factor.get("match_games_per_match"), 35.0 if tour == "ATP" else 22.0)
    slam_n = slam_samples.get((tour, player_lookup, tournament), 0)
    same_tournament_row = current_tournament_stats.get((tour, str(schedule.get("tour_id") or ""), player_id))
    same_tournament_log = current_tournament_logs.get((tour, str(schedule.get("tour_id") or ""), player_id), [])
    projection = project_player(
        tour=tour,
        player_rows=player_rows,
        opponent_rows=opponent_rows,
        factor_row=factor,
        expected_match_games=expected_games or (35.0 if tour == "ATP" else 22.0),
        slam_matches=slam_n,
        same_tournament_row=same_tournament_row,
    )
    career = player_rows.get("career_4y") or {}
    notes = list(projection.notes)
    if not factor:
        notes.append("NO_SLAM_FACTOR")
    return {
        "date": schedule["date"],
        "tour": tour,
        "tournament": tournament,
        "round": schedule["round"],
        "player": player,
        "opponent": opponent,
        "surface": surface,
        "projected_aces": fmt(projection.expected_aces),
        "projected_dfs": fmt(projection.expected_dfs),
        "projected_breaks_for": fmt(projection.expected_breaks_for),
        "projected_broken": fmt(projection.expected_broken),
        "projected_total_breaks": fmt(projection.expected_total_breaks),
        "ace_confidence": projection.ace_confidence,
        "df_confidence": projection.df_confidence,
        "break_confidence": projection.break_confidence,
        "service_points_estimate": fmt(projection.expected_service_points, 1),
        "service_games_estimate": fmt(projection.expected_service_games, 1),
        "player_surface_svpt_sample": str(parse_int(career.get("svpt"))),
        "player_surface_matches": str(parse_int(career.get("matches"))),
        "player_slam_sample": str(slam_n),
        "same_tournament_matches": str(projection.same_tournament_matches),
        "same_tournament_svpt": str(projection.same_tournament_svpt),
        "same_tournament_ace_weight": fmt(projection.same_tournament_ace_weight, 3),
        "same_tournament_df_weight": fmt(projection.same_tournament_df_weight, 3),
        "same_tournament_breaks_for": str(parse_int(same_tournament_row.get("breaks_for") if same_tournament_row else "")),
        "same_tournament_broken": str(parse_int(same_tournament_row.get("broken") if same_tournament_row else "")),
        "same_tournament_total_breaks": str(
            parse_int(same_tournament_row.get("breaks_for") if same_tournament_row else "")
            + parse_int(same_tournament_row.get("broken") if same_tournament_row else "")
        ),
        "tournament_round_log": json.dumps(same_tournament_log, ensure_ascii=True, separators=(",", ":")),
        "venue_ace_factor": str(factor.get("ace_factor") or ""),
        "venue_df_factor": str(factor.get("df_factor") or ""),
        "ace_rate_adj": fmt(projection.ace_rate, 5),
        "df_rate_adj": fmt(projection.df_rate, 5),
        "break_rate_adj": fmt(projection.break_rate, 5),
        "broken_rate_adj": fmt(projection.broken_rate, 5),
        "break_notes": "|".join(projection.break_notes),
        "notes": "|".join(dict.fromkeys(notes)),
        "source": schedule["source"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    parser.add_argument("--factors", default=str(DEFAULT_FACTORS))
    parser.add_argument("--aliases", default=str(DEFAULT_ALIASES))
    parser.add_argument("--wta-schedule", default="")
    parser.add_argument("--include-completed", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date()
    baseline = load_baseline(Path(args.baseline))
    factors = load_factors(Path(args.factors))
    aliases = load_aliases(Path(args.aliases))
    slam_samples = load_slam_samples(as_of)

    schedules = oncourt_schedule_rows("ATP", args.include_completed, args.as_of)
    schedules.extend(oncourt_schedule_rows("WTA", args.include_completed, args.as_of))
    oncourt_wta_count = sum(1 for row in schedules if row.get("source") == "oncourt_today_wta")
    if args.wta_schedule:
        schedules.extend(wta_schedule_rows(Path(args.wta_schedule)))
    current_tournament_stats = load_current_tournament_stats(schedules, as_of)
    current_tournament_logs = load_current_tournament_logs(schedules, as_of)

    rows: list[dict[str, str]] = []
    for schedule in schedules:
        rows.append(
            project_side(
                schedule=schedule,
                player=schedule["player1"],
                opponent=schedule["player2"],
                player_id=str(schedule.get("player1_id") or ""),
                baseline=baseline,
                factors=factors,
                slam_samples=slam_samples,
                aliases=aliases,
                current_tournament_stats=current_tournament_stats,
                current_tournament_logs=current_tournament_logs,
            )
        )
        rows.append(
            project_side(
                schedule=schedule,
                player=schedule["player2"],
                opponent=schedule["player1"],
                player_id=str(schedule.get("player2_id") or ""),
                baseline=baseline,
                factors=factors,
                slam_samples=slam_samples,
                aliases=aliases,
                current_tournament_stats=current_tournament_stats,
                current_tournament_logs=current_tournament_logs,
            )
        )

    fieldnames = [
        "date",
        "tour",
        "tournament",
        "round",
        "player",
        "opponent",
        "surface",
        "projected_aces",
        "projected_dfs",
        "projected_breaks_for",
        "projected_broken",
        "projected_total_breaks",
        "ace_confidence",
        "df_confidence",
        "break_confidence",
        "service_points_estimate",
        "service_games_estimate",
        "player_surface_svpt_sample",
        "player_surface_matches",
        "player_slam_sample",
        "same_tournament_matches",
        "same_tournament_svpt",
        "same_tournament_ace_weight",
        "same_tournament_df_weight",
        "same_tournament_breaks_for",
        "same_tournament_broken",
        "same_tournament_total_breaks",
        "tournament_round_log",
        "venue_ace_factor",
        "venue_df_factor",
        "ace_rate_adj",
        "df_rate_adj",
        "break_rate_adj",
        "broken_rate_adj",
        "break_notes",
        "notes",
        "source",
    ]
    write_csv(Path(args.out), rows, fieldnames)
    print(f"Saved {len(rows)} rows: {args.out}")
    if oncourt_wta_count:
        print(f"WTA schedule source: OnCourt today_wta ({oncourt_wta_count} matches)")
    elif not args.wta_schedule:
        print("WTA schedule source missing: OnCourt today_wta had no usable Slam rows; manual fallback not provided.")


if __name__ == "__main__":
    main()
