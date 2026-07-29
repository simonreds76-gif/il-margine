#!/usr/bin/env python3
"""Build coverage-inclusive player activity windows for tennis props.

This file measures whether a player has been active. It deliberately does not
mix Challenger/qualifying performance rates into the main-tour prop baseline.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SACKMANN_DIR = ROOT / "data" / "sackmann"
DEFAULT_OUT = ROOT / "data" / "tennis-props" / "player-props-activity.csv"
WINDOW_DAYS = {"L12M": 365, "L24M": 730, "career_4y": 1460}
FIELDS = [
    "tour",
    "player_id",
    "player_name",
    "window",
    "matches",
    "svpt",
    "main_matches",
    "main_svpt",
    "qual_chall_matches",
    "qual_chall_svpt",
    "last_match_date",
    "days_since_last_match",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    for pattern in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def integer(value: object) -> int:
    try:
        return int(float(str(value or "").strip()))
    except (TypeError, ValueError):
        return 0


def match_key(tour: str, row: dict[str, str]) -> tuple[str, ...]:
    return (
        tour,
        str(row.get("tourney_id") or ""),
        str(row.get("tourney_date") or ""),
        str(row.get("match_num") or ""),
        str(row.get("winner_id") or ""),
        str(row.get("loser_id") or ""),
    )


def build_rows(
    sackmann_dir: Path,
    *,
    as_of: date,
    start_year: int,
    end_year: int,
) -> list[dict[str, str]]:
    names: dict[tuple[str, str], str] = {}
    buckets: dict[tuple[str, str, str], dict[str, object]] = defaultdict(
        lambda: {
            "matches": 0,
            "svpt": 0,
            "main_matches": 0,
            "main_svpt": 0,
            "qual_chall_matches": 0,
            "qual_chall_svpt": 0,
            "last_match_date": None,
        }
    )
    seen: set[tuple[str, ...]] = set()
    for tour in ("atp", "wta"):
        for year in range(start_year, end_year + 1):
            sources = (
                ("main", sackmann_dir / f"{tour}_matches_{year}.csv"),
                ("qual_chall", sackmann_dir / f"{tour}_matches_qual_chall_{year}.csv"),
            )
            for source, path in sources:
                for row in read_csv(path):
                    match_date = parse_date(row.get("tourney_date"))
                    if match_date is None or match_date >= as_of:
                        continue
                    key = match_key(tour, row)
                    if key in seen:
                        continue
                    seen.add(key)
                    for prefix, id_col, name_col in (
                        ("w", "winner_id", "winner_name"),
                        ("l", "loser_id", "loser_name"),
                    ):
                        player_id = str(row.get(id_col) or "").strip()
                        player_name = str(row.get(name_col) or "").strip()
                        service_points = integer(row.get(f"{prefix}_svpt"))
                        if not player_id or not player_name or service_points <= 0:
                            continue
                        names[(tour, player_id)] = player_name
                        age_days = (as_of - match_date).days
                        for window, days in WINDOW_DAYS.items():
                            if age_days > days:
                                continue
                            bucket = buckets[(tour, player_id, window)]
                            bucket["matches"] = int(bucket["matches"]) + 1
                            bucket["svpt"] = int(bucket["svpt"]) + service_points
                            count_key = f"{source}_matches"
                            svpt_key = f"{source}_svpt"
                            bucket[count_key] = int(bucket[count_key]) + 1
                            bucket[svpt_key] = int(bucket[svpt_key]) + service_points
                            previous = bucket["last_match_date"]
                            if previous is None or match_date > previous:
                                bucket["last_match_date"] = match_date

    output: list[dict[str, str]] = []
    for (tour, player_id, window), bucket in sorted(buckets.items()):
        last_match = bucket["last_match_date"]
        output.append({
            "tour": tour.upper(),
            "player_id": player_id,
            "player_name": names.get((tour, player_id), ""),
            "window": window,
            "matches": str(bucket["matches"]),
            "svpt": str(bucket["svpt"]),
            "main_matches": str(bucket["main_matches"]),
            "main_svpt": str(bucket["main_svpt"]),
            "qual_chall_matches": str(bucket["qual_chall_matches"]),
            "qual_chall_svpt": str(bucket["qual_chall_svpt"]),
            "last_match_date": last_match.isoformat() if isinstance(last_match, date) else "",
            "days_since_last_match": (
                str((as_of - last_match).days) if isinstance(last_match, date) else ""
            ),
        })
    return output


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--sackmann-dir", type=Path, default=SACKMANN_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date()
    rows = build_rows(
        args.sackmann_dir,
        as_of=as_of,
        start_year=args.start_year,
        end_year=args.end_year,
    )
    write_csv(args.out, rows)
    print(f"Saved {len(rows)} activity rows: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
