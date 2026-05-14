"""Scaffold for future internal tennis feature building.

Phase 0 intentionally emits no features by default. Later phases will compute
per-fixture feature files consumed by clay, slam, grass, indoor, and challenger
research lanes.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TODAY_FEATURES_PATH = PROJECT_ROOT / "data" / "oncourt" / "match-features-today.csv"
HISTORY_FEATURES_PATH = PROJECT_ROOT / "data" / "oncourt" / "match-features-history.parquet"
FEATURE_COLUMNS = [
    "date",
    "tour_id",
    "match_id",
    "player1",
    "player2",
    "lane_id",
]


def write_empty_today(path: Path = TODAY_FEATURES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=FEATURE_COLUMNS).writeheader()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build internal tennis research-lane feature files.")
    parser.add_argument(
        "--write-empty",
        action="store_true",
        help="Write an empty today CSV header. Default is no writes in Phase 0.",
    )
    args = parser.parse_args()

    if args.write_empty:
        write_empty_today()
        print(f"wrote empty feature scaffold: {TODAY_FEATURES_PATH}")
    else:
        print("tennis feature builder: Phase 0 scaffold (no features written)")
        print(f"today target: {TODAY_FEATURES_PATH}")
        print(f"history target: {HISTORY_FEATURES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
