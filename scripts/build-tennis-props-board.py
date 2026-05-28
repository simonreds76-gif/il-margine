#!/usr/bin/env python3
"""Build an internal ATP/WTA Slam aces and double-fault projection board."""

from __future__ import annotations

import argparse
import csv
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
                "tournament": tournament,
                "round": ROUND_BY_ID.get(str(row.get("round_id") or ""), str(row.get("round_id") or "")),
                "surface": SURFACE_BY_COURT.get(str(tour.get("court_id") or ""), "Clay"),
                "player1": p1,
                "player2": p2,
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
                "tournament": tournament,
                "round": str(row.get("round") or "").strip(),
                "surface": str(row.get("surface") or "Clay").strip() or "Clay",
                "player1": p1,
                "player2": p2,
                "source": str(path),
            }
        )
    return rows


def project_side(
    *,
    schedule: dict[str, str],
    player: str,
    opponent: str,
    baseline: dict[tuple[str, str, str], dict[str, dict[str, str]]],
    factors: dict[tuple[str, str, str], dict[str, str]],
    slam_samples: dict[tuple[str, str, str], int],
    aliases: dict[tuple[str, str], str],
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
    projection = project_player(
        tour=tour,
        player_rows=player_rows,
        opponent_rows=opponent_rows,
        factor_row=factor,
        expected_match_games=expected_games or (35.0 if tour == "ATP" else 22.0),
        slam_matches=slam_n,
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
        "ace_confidence": projection.ace_confidence,
        "df_confidence": projection.df_confidence,
        "service_points_estimate": fmt(projection.expected_service_points, 1),
        "service_games_estimate": fmt(projection.expected_service_games, 1),
        "player_surface_svpt_sample": str(parse_int(career.get("svpt"))),
        "player_surface_matches": str(parse_int(career.get("matches"))),
        "player_slam_sample": str(slam_n),
        "venue_ace_factor": str(factor.get("ace_factor") or ""),
        "venue_df_factor": str(factor.get("df_factor") or ""),
        "ace_rate_adj": fmt(projection.ace_rate, 5),
        "df_rate_adj": fmt(projection.df_rate, 5),
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

    rows: list[dict[str, str]] = []
    for schedule in schedules:
        rows.append(
            project_side(
                schedule=schedule,
                player=schedule["player1"],
                opponent=schedule["player2"],
                baseline=baseline,
                factors=factors,
                slam_samples=slam_samples,
                aliases=aliases,
            )
        )
        rows.append(
            project_side(
                schedule=schedule,
                player=schedule["player2"],
                opponent=schedule["player1"],
                baseline=baseline,
                factors=factors,
                slam_samples=slam_samples,
                aliases=aliases,
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
        "ace_confidence",
        "df_confidence",
        "service_points_estimate",
        "service_games_estimate",
        "player_surface_svpt_sample",
        "player_surface_matches",
        "player_slam_sample",
        "venue_ace_factor",
        "venue_df_factor",
        "ace_rate_adj",
        "df_rate_adj",
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
