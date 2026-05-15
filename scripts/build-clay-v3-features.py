#!/usr/bin/env python3
"""Build Clay ML v3 Phase B feature CSV.

This is a join-only script. It consumes the Phase A caches and creates the
lean three-feature residual-model dataset. It does not fit a model and it
refuses sealed years.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from collections import Counter
from pathlib import Path
from typing import Any

from _lib.clay_v3_tournament_map import canonical_tournament_key, venue_key_for_tournament


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"
ONCOURT_DIR = ROOT / "data" / "oncourt"

SURFACE_SPEED_CSV = BACKTEST_DIR / "tennisabstract-atp-surface-speed.csv"
VENUE_GEO_CSV = ONCOURT_DIR / "clay_venues_geo.csv"
WEATHER_CSV = ONCOURT_DIR / "weather_clay_2022_2024.csv"
RANKS_CSV = BACKTEST_DIR / "clay-v3-xlsx-ranks-2022-2024.csv"

FIELDNAMES = [
    "match_id",
    "date",
    "year",
    "month",
    "tournament",
    "tournament_canonical_key",
    "venue_key",
    "player_a_id",
    "player_b_id",
    "player_a",
    "player_b",
    "a_won",
    "best_of",
    "pin_close_a",
    "pin_close_b",
    "pin_implied_a",
    "pin_implied_b",
    "ta_surface_speed",
    "altitude_m",
    "temp_mean_c",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Clay ML v3 residual-model features.")
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--exclude-bo5", action="store_true", help="Exclude Roland Garros / French Open Bo5 clay rows.")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def parse_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def deterministic_a_is_winner(row: dict[str, Any]) -> bool:
    payload = "|".join(
        [
            str(row.get("date", "")),
            str(row.get("tournament", "")),
            str(row.get("player1_id", "")),
            str(row.get("player2_id", "")),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return digest[0] % 2 == 0


def load_backtest_rows(years: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year in years:
        path = BACKTEST_DIR / f"backtest-results-{year}.csv"
        with path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if (row.get("surface") or "").strip().lower() == "clay":
                    rows.append(row)
    rows.sort(key=lambda r: (r["date"], r["tournament"], r["player1_id"], r["player2_id"]))
    return rows


def load_surface_speed() -> dict[tuple[int, str], float]:
    out: dict[tuple[int, str], float] = {}
    with SURFACE_SPEED_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (row.get("surface") or "").strip().lower() != "clay":
                continue
            try:
                year = int(str(row.get("season_year") or "0"))
            except ValueError:
                continue
            canonical = canonical_tournament_key(row.get("tournament_key")) or canonical_tournament_key(row.get("tournament_name"))
            speed = parse_float(row.get("ta_surface_speed") or row.get("cpi"))
            if canonical and not math.isnan(speed):
                out[(year, canonical)] = speed
    return out


def load_venue_geo() -> dict[str, float]:
    out: dict[str, float] = {}
    with VENUE_GEO_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            altitude = parse_float(row.get("altitude_m"))
            if row.get("venue_key") and not math.isnan(altitude):
                out[str(row["venue_key"])] = altitude
    return out


def load_weather() -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    with WEATHER_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            temp = parse_float(row.get("temp_mean_c"))
            venue = str(row.get("venue_key") or "")
            date = str(row.get("match_date") or "")
            if venue and date and not math.isnan(temp):
                out[(venue, date)] = temp
    return out


def load_rank_cache() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    with RANKS_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (
                str(row.get("date") or ""),
                str(row.get("tournament") or ""),
                str(row.get("winner_id") or ""),
                str(row.get("loser_id") or ""),
            )
            out[key] = row
    return out


def build_rows(years: list[int], exclude_bo5: bool) -> tuple[list[dict[str, Any]], Counter[str]]:
    source_rows = load_backtest_rows(years)
    speed = load_surface_speed()
    altitude = load_venue_geo()
    weather = load_weather()
    ranks = load_rank_cache()
    drops: Counter[str] = Counter()
    out: list[dict[str, Any]] = []

    for row in source_rows:
        year = int(str(row["date"])[:4])
        canonical = canonical_tournament_key(row.get("tournament"))
        if not canonical:
            drops["tournament_alias"] += 1
            continue
        if exclude_bo5 and canonical == "french_open":
            drops["bo5_french_open"] += 1
            continue
        venue_key = venue_key_for_tournament(row.get("tournament"))
        if not venue_key:
            drops["venue_key"] += 1
            continue
        rank_row = ranks.get((row["date"], row["tournament"], row["player1_id"], row["player2_id"]))
        if not rank_row or not rank_row.get("winner_rank") or not rank_row.get("loser_rank"):
            drops["rank_missing"] += 1
            continue
        pin_winner = parse_float(row.get("pinnacle_prob_novig"))
        odds_winner = parse_float(row.get("pinnacle_odds"))
        odds_loser = parse_float(row.get("pinnacle_odds_loser"))
        if any(math.isnan(v) for v in [pin_winner, odds_winner, odds_loser]):
            drops["pinnacle_missing"] += 1
            continue
        surface_speed = speed.get((year, canonical), math.nan)
        altitude_m = altitude.get(venue_key, math.nan)
        temp_mean_c = weather.get((venue_key, row["date"]), math.nan)
        if any(math.isnan(v) for v in [surface_speed, altitude_m, temp_mean_c]):
            drops["context_missing"] += 1
            continue

        a_is_winner = deterministic_a_is_winner(row)
        player_a_id = row["player1_id"] if a_is_winner else row["player2_id"]
        player_b_id = row["player2_id"] if a_is_winner else row["player1_id"]
        player_a = row["player1"] if a_is_winner else row["player2"]
        player_b = row["player2"] if a_is_winner else row["player1"]
        pin_a = pin_winner if a_is_winner else 1.0 - pin_winner
        pin_b = 1.0 - pin_a
        odds_a = odds_winner if a_is_winner else odds_loser
        odds_b = odds_loser if a_is_winner else odds_winner
        match_id = "|".join([row["date"], row["tournament"], row["player1_id"], row["player2_id"]])
        out.append(
            {
                "match_id": match_id,
                "date": row["date"],
                "year": str(year),
                "month": str(int(str(row["date"])[5:7])),
                "tournament": row.get("tournament", ""),
                "tournament_canonical_key": canonical,
                "venue_key": venue_key,
                "player_a_id": player_a_id,
                "player_b_id": player_b_id,
                "player_a": player_a,
                "player_b": player_b,
                "a_won": "1" if a_is_winner else "0",
                "best_of": "3",
                "pin_close_a": f"{odds_a:.6g}",
                "pin_close_b": f"{odds_b:.6g}",
                "pin_implied_a": f"{pin_a:.12g}",
                "pin_implied_b": f"{pin_b:.12g}",
                "ta_surface_speed": f"{surface_speed:.12g}",
                "altitude_m": f"{altitude_m:.12g}",
                "temp_mean_c": f"{temp_mean_c:.12g}",
            }
        )

    return out, drops


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    if any(year >= 2025 for year in years):
        raise SystemExit("Phase B feature build refuses 2025+ sealed years.")
    rows, drops = build_rows(years, args.exclude_bo5)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out}")
    print("drop_counts:", dict(drops))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
