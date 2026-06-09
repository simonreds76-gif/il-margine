#!/usr/bin/env python3
"""Compute ATP/WTA venue ace and double-fault factors from Sackmann.

The original v0 only emitted Slam rows. The live board now covers grass
warmups too, so this script also emits supported tour events plus a separate
tour-surface baseline fallback for events with no usable venue sample yet.
"""

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
DEFAULT_BASELINE_OUT = OUT_DIR / "tour-surface-baselines.csv"
SLAMS = {
    "australian open": "Australian Open",
    "roland garros": "Roland Garros",
    "french open": "Roland Garros",
    "wimbledon": "Wimbledon",
    "us open": "US Open",
    "u.s. open": "US Open",
}


def canonical_tournament_name(value: object) -> str | None:
    raw = str(value or "")
    lower = raw.lower()
    slam = slam_name(raw)
    if slam:
        return slam
    if "hertogenbosch" in lower or "rosmalen" in lower or "libema open" in lower:
        return "Hertogenbosch"
    if (
        "queen" in lower
        or "hsbc championships" in lower
        or "lta london championships" in lower
        or "cinch championships" in lower
        or "stella artois" in lower
    ):
        return "Queen's Club"
    if "stuttgart" in lower or "boss open" in lower:
        return "Stuttgart"
    if "halle" in lower or "terra wortmann" in lower or "gerry weber" in lower:
        return "Halle"
    if "nottingham" in lower:
        return "Nottingham"
    if "berlin" in lower and ("open" in lower or "tennis" in lower or "bett1" in lower):
        return "Berlin"
    if "eastbourne" in lower:
        return "Eastbourne"
    if "bad homburg" in lower:
        return "Bad Homburg"
    if "mallorca" in lower:
        return "Mallorca"
    return None


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


def add_match(totals: dict[str, float], row: dict[str, str]) -> bool:
    w_svpt = parse_int(row.get("w_svpt"))
    l_svpt = parse_int(row.get("l_svpt"))
    if w_svpt <= 0 or l_svpt <= 0:
        return False
    totals["matches"] += 1
    totals["aces"] += parse_int(row.get("w_ace")) + parse_int(row.get("l_ace"))
    totals["dfs"] += parse_int(row.get("w_df")) + parse_int(row.get("l_df"))
    totals["svpt"] += w_svpt + l_svpt
    totals["svgms"] += parse_int(row.get("w_SvGms")) + parse_int(row.get("l_SvGms"))
    games = score_games(row.get("score"))
    if games is not None:
        totals["match_games"] += games
        totals["match_games_n"] += 1
    return True


def subtract_totals(total: dict[str, float], part: dict[str, float]) -> dict[str, float]:
    out = empty_totals()
    for key in out:
        out[key] = max(0.0, float(total.get(key, 0.0)) - float(part.get(key, 0.0)))
    return out


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
    raw_ace_factor = None if ace_rate is None or not base_ace else ace_rate / base_ace
    raw_df_factor = None if df_rate is None or not base_df else df_rate / base_df
    sample_weight = slam["matches"] / (slam["matches"] + 100.0) if slam["matches"] > 0 else 0.0
    ace_factor = None if raw_ace_factor is None else 1.0 + (raw_ace_factor - 1.0) * sample_weight
    df_factor = None if raw_df_factor is None else 1.0 + (raw_df_factor - 1.0) * sample_weight
    sample_flag = "OK" if slam["matches"] >= 50 and baseline["matches"] >= 150 else "LOW_SAMPLE"
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
        "raw_ace_factor": fmt(raw_ace_factor, 4),
        "raw_df_factor": fmt(raw_df_factor, 4),
        "ace_factor": fmt(ace_factor, 4),
        "df_factor": fmt(df_factor, 4),
        "sample_weight": fmt(sample_weight, 4),
        "sample_flag": sample_flag,
    }


def surface_baseline_row(
    *,
    tour: str,
    surface: str,
    year: str,
    totals: dict[str, float],
) -> dict[str, str]:
    ace_rate = rate(totals["aces"], totals["svpt"])
    df_rate = rate(totals["dfs"], totals["svpt"])
    svpt_per_svg = rate(totals["svpt"], totals["svgms"])
    match_games = rate(totals["match_games"], totals["match_games_n"])
    return {
        "tour": tour.upper(),
        "surface": surface,
        "year": year,
        "matches": str(int(totals["matches"])),
        "ace_rate": fmt(ace_rate),
        "df_rate": fmt(df_rate),
        "svpt_per_svgame": fmt(svpt_per_svg, 4),
        "match_games_per_match": fmt(match_games, 3),
        "sample_flag": "OK" if totals["matches"] >= 150 else "LOW_SAMPLE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=min(date.today().year, 2026))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--baseline-out", default=str(DEFAULT_BASELINE_OUT))
    args = parser.parse_args()

    event_totals: dict[tuple[str, str, str, int], dict[str, float]] = defaultdict(empty_totals)
    surface_totals: dict[tuple[str, str, int], dict[str, float]] = defaultdict(empty_totals)
    agg_event: dict[tuple[str, str, str], dict[str, float]] = defaultdict(empty_totals)
    agg_surface: dict[tuple[str, str], dict[str, float]] = defaultdict(empty_totals)

    for tour in ("atp", "wta"):
        for year in range(args.start_year, args.end_year + 1):
            path = SACKMANN_DIR / f"{tour}_matches_{year}.csv"
            for row in read_csv(path):
                match_year = parse_year(row.get("tourney_date")) or year
                if match_year < args.start_year or match_year > args.end_year:
                    continue
                surface = norm_surface(row.get("surface"))
                if not add_match(surface_totals[(tour, surface, match_year)], row):
                    continue
                add_match(agg_surface[(tour, surface)], row)
                tournament = canonical_tournament_name(row.get("tourney_name"))
                if tournament:
                    add_match(event_totals[(tour, tournament, surface, match_year)], row)
                    add_match(agg_event[(tour, tournament, surface)], row)

    rows: list[dict[str, str]] = []
    for (tour, tournament, surface, year), event in sorted(event_totals.items()):
        baseline = subtract_totals(surface_totals[(tour, surface, year)], event)
        rows.append(
            row_from_totals(
                tour=tour,
                tournament=tournament,
                surface=surface,
                year=str(year),
                slam=event,
                baseline=baseline,
            )
        )
    for (tour, tournament, surface), event in sorted(agg_event.items()):
        baseline = subtract_totals(agg_surface[(tour, surface)], event)
        rows.append(
            row_from_totals(
                tour=tour,
                tournament=tournament,
                surface=surface,
                year="ALL",
                slam=event,
                baseline=baseline,
            )
        )

    baseline_rows: list[dict[str, str]] = []
    for (tour, surface, year), totals in sorted(surface_totals.items()):
        baseline_rows.append(surface_baseline_row(tour=tour, surface=surface, year=str(year), totals=totals))
    for (tour, surface), totals in sorted(agg_surface.items()):
        baseline_rows.append(surface_baseline_row(tour=tour, surface=surface, year="ALL", totals=totals))

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
        "raw_ace_factor",
        "raw_df_factor",
        "ace_factor",
        "df_factor",
        "sample_weight",
        "sample_flag",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows: {out}")

    baseline_out = Path(args.baseline_out)
    baseline_out.parent.mkdir(parents=True, exist_ok=True)
    baseline_fields = [
        "tour",
        "surface",
        "year",
        "matches",
        "ace_rate",
        "df_rate",
        "svpt_per_svgame",
        "match_games_per_match",
        "sample_flag",
    ]
    with baseline_out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=baseline_fields)
        writer.writeheader()
        writer.writerows(baseline_rows)
    print(f"Saved {len(baseline_rows)} surface baseline rows: {baseline_out}")


if __name__ == "__main__":
    main()
