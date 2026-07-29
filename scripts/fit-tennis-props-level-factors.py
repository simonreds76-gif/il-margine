#!/usr/bin/env python3
"""Fit ATP qualifying/Challenger-to-main-tour ace-rate factors.

Factors are fitted on paired player-surface development samples only. They are
used by the registered A1 experiment and never alter production automatically.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SACKMANN_DIR = ROOT / "data" / "sackmann"
DEFAULT_OUT = (
    ROOT / "data" / "tennis-props" / "experiments"
    / "most-aces-coverage-a1" / "level-factors.json"
)
MIN_SOURCE_SVPT = 250


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def integer(value: object) -> int:
    try:
        return int(float(str(value or "").strip()))
    except (TypeError, ValueError):
        return 0


def surface(value: object) -> str:
    text = str(value or "").lower()
    if "hard" in text:
        return "Hard"
    if "clay" in text:
        return "Clay"
    if "grass" in text:
        return "Grass"
    return "Unknown"


def add_file(
    totals: dict[tuple[str, str, str], list[int]],
    path: Path,
    source: str,
) -> None:
    for row in read_csv(path):
        court = surface(row.get("surface"))
        if court == "Unknown":
            continue
        for prefix, id_field in (("w", "winner_id"), ("l", "loser_id")):
            player_id = str(row.get(id_field) or "").strip()
            svpt = integer(row.get(f"{prefix}_svpt"))
            aces = integer(row.get(f"{prefix}_ace"))
            if not player_id or svpt <= 0:
                continue
            key = (player_id, court, source)
            totals[key][0] += aces
            totals[key][1] += svpt


def weighted_log_factor(
    pairs: list[tuple[float, float]],
) -> tuple[float, int, float]:
    if not pairs:
        return 1.0, 0, 0.0
    logs = sorted(value for value, _weight in pairs)
    low = logs[max(0, int(len(logs) * 0.05) - 1)]
    high = logs[min(len(logs) - 1, int(len(logs) * 0.95))]
    numerator = 0.0
    denominator = 0.0
    for value, weight in pairs:
        clipped = min(high, max(low, value))
        numerator += clipped * weight
        denominator += weight
    mean_log = numerator / denominator if denominator else 0.0
    return math.exp(mean_log), len(pairs), denominator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--sackmann-dir", type=Path, default=SACKMANN_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    totals: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for year in range(args.start_year, args.end_year + 1):
        add_file(totals, args.sackmann_dir / f"atp_matches_{year}.csv", "main")
        add_file(
            totals,
            args.sackmann_dir / f"atp_matches_qual_chall_{year}.csv",
            "qual_chall",
        )

    factors: dict[str, dict[str, float | int]] = {}
    all_pairs: list[tuple[float, float]] = []
    for court in ("Hard", "Clay", "Grass"):
        pairs: list[tuple[float, float]] = []
        player_ids = {
            player_id for player_id, pair_surface, _source in totals
            if pair_surface == court
        }
        for player_id in player_ids:
            main_aces, main_svpt = totals[(player_id, court, "main")]
            lower_aces, lower_svpt = totals[(player_id, court, "qual_chall")]
            if main_svpt < MIN_SOURCE_SVPT or lower_svpt < MIN_SOURCE_SVPT:
                continue
            main_rate = (main_aces + 0.5) / (main_svpt + 1.0)
            lower_rate = (lower_aces + 0.5) / (lower_svpt + 1.0)
            effective_weight = min(main_svpt, lower_svpt, 2000)
            pairs.append((math.log(main_rate / lower_rate), effective_weight))
        factor, pair_count, weight = weighted_log_factor(pairs)
        factors[court] = {
            "ace_count_factor": factor,
            "paired_players": pair_count,
            "effective_weight": weight,
        }
        all_pairs.extend(pairs)
    global_factor, pair_count, weight = weighted_log_factor(all_pairs)
    payload = {
        "version": "atp-qual-chall-level-factor-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "development_years": list(range(args.start_year, args.end_year + 1)),
        "method": "paired player-surface weighted log main/lower ace-rate ratio",
        "minimum_service_points_each_source": MIN_SOURCE_SVPT,
        "winsorisation": "5th/95th percentile of paired log ratios",
        "global": {
            "ace_count_factor": global_factor,
            "paired_player_surfaces": pair_count,
            "effective_weight": weight,
        },
        "surfaces": factors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
