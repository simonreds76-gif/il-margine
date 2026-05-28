#!/usr/bin/env python3
"""Build ATP/WTA player ace and double-fault baselines for Slam props."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SACKMANN_DIR = ROOT / "data" / "sackmann"
OUT_DIR = ROOT / "data" / "tennis-props"
DEFAULT_OUT = OUT_DIR / "player-props-baseline.csv"
WINDOW_DAYS = {
    "L12M": 365,
    "L24M": 730,
    "career_4y": 1460,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


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


def parse_int(value: object) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return 0
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def norm_surface(value: object) -> str:
    lower = str(value or "").strip().lower()
    if "clay" in lower:
        return "Clay"
    if "grass" in lower:
        return "Grass"
    if "hard" in lower:
        return "Hard"
    if "carpet" in lower:
        return "Carpet"
    return str(value or "Unknown").strip().title() or "Unknown"


def empty_totals() -> dict[str, float]:
    return {
        "matches": 0,
        "wins": 0,
        "svpt": 0,
        "svgms": 0,
        "aces": 0,
        "dfs": 0,
        "first_in": 0,
        "first_won": 0,
        "second_won": 0,
        "second_attempts": 0,
        "ret_first_points": 0,
        "ret_first_won": 0,
        "ret_second_points": 0,
        "ret_second_won": 0,
    }


def add_side(
    totals: dict[str, float],
    row: dict[str, str],
    *,
    won: bool,
    prefix: str,
    opp_prefix: str,
) -> None:
    svpt = parse_int(row.get(f"{prefix}_svpt"))
    opp_svpt = parse_int(row.get(f"{opp_prefix}_svpt"))
    if svpt <= 0 or opp_svpt <= 0:
        return
    first_in = parse_int(row.get(f"{prefix}_1stIn"))
    opp_first_in = parse_int(row.get(f"{opp_prefix}_1stIn"))
    second_attempts = max(0, svpt - first_in)
    opp_second_attempts = max(0, opp_svpt - opp_first_in)
    opp_first_won = parse_int(row.get(f"{opp_prefix}_1stWon"))
    opp_second_won = parse_int(row.get(f"{opp_prefix}_2ndWon"))

    totals["matches"] += 1
    totals["wins"] += 1 if won else 0
    totals["svpt"] += svpt
    totals["svgms"] += parse_int(row.get(f"{prefix}_SvGms"))
    totals["aces"] += parse_int(row.get(f"{prefix}_ace"))
    totals["dfs"] += parse_int(row.get(f"{prefix}_df"))
    totals["first_in"] += first_in
    totals["first_won"] += parse_int(row.get(f"{prefix}_1stWon"))
    totals["second_won"] += parse_int(row.get(f"{prefix}_2ndWon"))
    totals["second_attempts"] += second_attempts
    totals["ret_first_points"] += opp_first_in
    totals["ret_first_won"] += max(0, opp_first_in - opp_first_won)
    totals["ret_second_points"] += opp_second_attempts
    totals["ret_second_won"] += max(0, opp_second_attempts - opp_second_won)


def safe_div(num: float, den: float) -> float | None:
    return None if den <= 0 else num / den


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def totals_row(
    *,
    tour: str,
    player_id: str,
    player_name: str,
    surface: str,
    window: str,
    totals: dict[str, float],
) -> dict[str, str]:
    return {
        "tour": tour.upper(),
        "player_id": player_id,
        "player_name": player_name,
        "surface": surface,
        "window": window,
        "matches": str(int(totals["matches"])),
        "wins": str(int(totals["wins"])),
        "svpt": str(int(totals["svpt"])),
        "svgms": str(int(totals["svgms"])),
        "aces": str(int(totals["aces"])),
        "dfs": str(int(totals["dfs"])),
        "ace_rate": fmt(safe_div(totals["aces"], totals["svpt"])),
        "df_rate": fmt(safe_div(totals["dfs"], totals["svpt"])),
        "first_serve_pct": fmt(safe_div(totals["first_in"], totals["svpt"])),
        "first_serve_win_pct": fmt(safe_div(totals["first_won"], totals["first_in"])),
        "second_serve_win_pct": fmt(safe_div(totals["second_won"], totals["second_attempts"])),
        "ret_first_points": str(int(totals["ret_first_points"])),
        "ret_first_win_pct": fmt(safe_div(totals["ret_first_won"], totals["ret_first_points"])),
        "ret_second_points": str(int(totals["ret_second_points"])),
        "ret_second_win_pct": fmt(safe_div(totals["ret_second_won"], totals["ret_second_points"])),
        "svpt_per_svgame": fmt(safe_div(totals["svpt"], totals["svgms"]), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date()
    names: dict[tuple[str, str], str] = {}
    buckets: dict[tuple[str, str, str, str], dict[str, float]] = defaultdict(empty_totals)

    for tour in ("atp", "wta"):
        for year in range(args.start_year, args.end_year + 1):
            path = SACKMANN_DIR / f"{tour}_matches_{year}.csv"
            for row in read_csv(path):
                match_date = parse_date(row.get("tourney_date"))
                if match_date is None or match_date >= as_of:
                    continue
                surface = norm_surface(row.get("surface"))
                sides = (
                    ("w", True, "winner_id", "winner_name", "l"),
                    ("l", False, "loser_id", "loser_name", "w"),
                )
                for prefix, won, id_col, name_col, opp_prefix in sides:
                    player_id = str(row.get(id_col) or "").strip()
                    player_name = str(row.get(name_col) or "").strip()
                    if not player_id or not player_name:
                        continue
                    names[(tour, player_id)] = player_name
                    age_days = (as_of - match_date).days
                    for window, days in WINDOW_DAYS.items():
                        if age_days > days:
                            continue
                        key = (tour, player_id, surface, window)
                        add_side(buckets[key], row, won=won, prefix=prefix, opp_prefix=opp_prefix)

    rows: list[dict[str, str]] = []
    for (tour, player_id, surface, window), totals in sorted(buckets.items()):
        if totals["matches"] <= 0:
            continue
        rows.append(
            totals_row(
                tour=tour,
                player_id=player_id,
                player_name=names.get((tour, player_id), ""),
                surface=surface,
                window=window,
                totals=totals,
            )
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "tour",
        "player_id",
        "player_name",
        "surface",
        "window",
        "matches",
        "wins",
        "svpt",
        "svgms",
        "aces",
        "dfs",
        "ace_rate",
        "df_rate",
        "first_serve_pct",
        "first_serve_win_pct",
        "second_serve_win_pct",
        "ret_first_points",
        "ret_first_win_pct",
        "ret_second_points",
        "ret_second_win_pct",
        "svpt_per_svgame",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows: {out}")


if __name__ == "__main__":
    main()
