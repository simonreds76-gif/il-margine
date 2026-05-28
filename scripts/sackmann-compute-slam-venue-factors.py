#!/usr/bin/env python3
"""Compute ATP/WTA Slam-specific ace and double-fault factors from Sackmann."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SACKMANN_DIR = ROOT / "data" / "sackmann"
OUT_DIR = ROOT / "data" / "tennis-props"
DEFAULT_OUT = OUT_DIR / "slam-venue-factors.csv"
SLAMS = {
    "australian open": "Australian Open",
    "roland garros": "Roland Garros",
    "french open": "Roland Garros",
    "wimbledon": "Wimbledon",
    "us open": "US Open",
    "u.s. open": "US Open",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_int(value: object) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return 0
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def parse_year(value: object) -> int | None:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").year
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return datetime.strptime(text, "%Y-%m-%d").year
        except ValueError:
            return None
    return None


def norm_surface(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "Unknown"
    lower = text.lower()
    if "clay" in lower:
        return "Clay"
    if "grass" in lower:
        return "Grass"
    if "carpet" in lower:
        return "Carpet"
    if "hard" in lower:
        return "Hard"
    return text.title()


def slam_name(tourney_name: object) -> str | None:
    lower = str(tourney_name or "").strip().lower()
    for needle, label in SLAMS.items():
        if needle in lower:
            return label
    return None


def score_games(score: object) -> int | None:
    text = str(score or "").strip()
    if not text or re.search(r"\b(W/O|WO|DEF)\b", text, re.I):
        return None
    total = 0
    for a, b in re.findall(r"(\d+)-(\d+)", text):
        total += int(a) + int(b)
    return total or None


def empty_totals() -> dict[str, float]:
    return {
        "matches": 0,
        "aces": 0,
        "dfs": 0,
        "svpt": 0,
        "svgms": 0,
        "match_games": 0,
        "match_games_n": 0,
    }


def add_match(totals: dict[str, float], row: dict[str, str]) -> None:
    w_svpt = parse_int(row.get("w_svpt"))
    l_svpt = parse_int(row.get("l_svpt"))
    if w_svpt <= 0 or l_svpt <= 0:
        return
    totals["matches"] += 1
    totals["aces"] += parse_int(row.get("w_ace")) + parse_int(row.get("l_ace"))
    totals["dfs"] += parse_int(row.get("w_df")) + parse_int(row.get("l_df"))
    totals["svpt"] += w_svpt + l_svpt
    totals["svgms"] += parse_int(row.get("w_SvGms")) + parse_int(row.get("l_SvGms"))
    games = score_games(row.get("score"))
    if games is not None:
        totals["match_games"] += games
        totals["match_games_n"] += 1


def rate(num: float, den: float) -> float | None:
    return None if den <= 0 else num / den


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def row_from_totals(
    *,
    tour: str,
    tournament: str,
    surface: str,
    year: str,
    slam: dict[str, float],
    baseline: dict[str, float],
) -> dict[str, str]:
    ace_rate = rate(slam["aces"], slam["svpt"])
    df_rate = rate(slam["dfs"], slam["svpt"])
    svpt_per_svg = rate(slam["svpt"], slam["svgms"])
    match_games = rate(slam["match_games"], slam["match_games_n"])
    base_ace = rate(baseline["aces"], baseline["svpt"])
    base_df = rate(baseline["dfs"], baseline["svpt"])
    ace_factor = None if ace_rate is None or not base_ace else ace_rate / base_ace
    df_factor = None if df_rate is None or not base_df else df_rate / base_df
    sample_flag = "OK" if slam["matches"] >= 80 and baseline["matches"] >= 200 else "LOW_SAMPLE"
    return {
        "tour": tour.upper(),
        "tournament": tournament,
        "surface": surface,
        "year": year,
        "matches": str(int(slam["matches"])),
        "ace_rate": fmt(ace_rate),
        "df_rate": fmt(df_rate),
        "svpt_per_svgame": fmt(svpt_per_svg, 4),
        "match_games_per_match": fmt(match_games, 3),
        "tour_surface_baseline_ace": fmt(base_ace),
        "tour_surface_baseline_df": fmt(base_df),
        "ace_factor": fmt(ace_factor, 4),
        "df_factor": fmt(df_factor, 4),
        "sample_flag": sample_flag,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=min(date.today().year, 2026))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    slam_totals: dict[tuple[str, str, str, int], dict[str, float]] = defaultdict(empty_totals)
    baseline_totals: dict[tuple[str, str, int], dict[str, float]] = defaultdict(empty_totals)
    agg_slam: dict[tuple[str, str, str], dict[str, float]] = defaultdict(empty_totals)
    agg_baseline: dict[tuple[str, str], dict[str, float]] = defaultdict(empty_totals)

    for tour in ("atp", "wta"):
        for year in range(args.start_year, args.end_year + 1):
            path = SACKMANN_DIR / f"{tour}_matches_{year}.csv"
            for row in read_csv(path):
                match_year = parse_year(row.get("tourney_date")) or year
                if match_year < args.start_year or match_year > args.end_year:
                    continue
                surface = norm_surface(row.get("surface"))
                tournament = slam_name(row.get("tourney_name"))
                if tournament:
                    add_match(slam_totals[(tour, tournament, surface, match_year)], row)
                    add_match(agg_slam[(tour, tournament, surface)], row)
                else:
                    add_match(baseline_totals[(tour, surface, match_year)], row)
                    add_match(agg_baseline[(tour, surface)], row)

    rows: list[dict[str, str]] = []
    for (tour, tournament, surface, year), slam in sorted(slam_totals.items()):
        baseline = baseline_totals[(tour, surface, year)]
        rows.append(
            row_from_totals(
                tour=tour,
                tournament=tournament,
                surface=surface,
                year=str(year),
                slam=slam,
                baseline=baseline,
            )
        )
    for (tour, tournament, surface), slam in sorted(agg_slam.items()):
        baseline = agg_baseline[(tour, surface)]
        rows.append(
            row_from_totals(
                tour=tour,
                tournament=tournament,
                surface=surface,
                year="ALL",
                slam=slam,
                baseline=baseline,
            )
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "tour",
        "tournament",
        "surface",
        "year",
        "matches",
        "ace_rate",
        "df_rate",
        "svpt_per_svgame",
        "match_games_per_match",
        "tour_surface_baseline_ace",
        "tour_surface_baseline_df",
        "ace_factor",
        "df_factor",
        "sample_flag",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows: {out}")


if __name__ == "__main__":
    main()
