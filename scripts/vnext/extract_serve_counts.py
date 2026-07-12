#!/usr/bin/env python3
"""Extract causal ATP player-match serve counts for the registered vNext MVE."""

from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from common import COUNT_FIELDS, DEFAULT_ONCOURT_DIR, DEFAULT_OUTPUT_DIR, iter_serve_count_rows, sha256_file, write_json, write_rows_csv_gz


VERSION = "vnext-mve-0.1"


def _load_backtest_module():
    module_path = Path(__file__).resolve().parents[1] / "backtest-fair-odds.py"
    spec = importlib.util.spec_from_file_location("backtest_fair_odds_vnext_reconcile", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _reconcile(path: Path, oncourt_dir: Path, sample_size: int, seed: int, end_year: int) -> dict[str, object]:
    extracted: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    reference: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        key = (int(row["server_id"]), row["date"][:7])
        for field in COUNT_FIELDS:
            extracted[key][field] += int(row[field])

    keys = sorted(extracted)
    rng = random.Random(seed)
    sampled = rng.sample(keys, min(sample_size, len(keys)))
    sampled_set = set(sampled)

    # Rebuild the same sampled player-month aggregates through the incumbent
    # backtest's independent stat-map/history-event path. This catches join,
    # date, surface and count-semantic drift between vNext and the incumbent.
    backtest = _load_backtest_module()
    players = backtest._load_oncourt_players(oncourt_dir / "players_atp.csv")
    players_by_id = {int(row["id"]): row for row in players}
    tours = backtest._load_tour_info(oncourt_dir / "tours_atp.csv", oncourt_dir / "courts.csv")
    stat_map = backtest._load_stat_map(oncourt_dir / "stat_atp.csv")
    events, _skips = backtest._history_from_oncourt(
        oncourt_dir / "games_atp.csv",
        players_by_id,
        tours,
        stat_map,
        max_date_ord=date(end_year + 1, 1, 1).toordinal(),
    )
    for event in events:
        if event.surface not in {"Hard", "I.hard"}:
            continue
        month = date.fromordinal(event.date_ord).isoformat()[:7]
        for player_id, stats in ((event.winner_id, event.winner_stats), (event.loser_id, event.loser_stats)):
            key = (int(player_id), month)
            if key not in sampled_set or not stats or len(stats) < 9:
                continue
            reference[key]["serve_points"] += int(stats[5])
            reference[key]["first_in"] += int(stats[4])
            reference[key]["first_won"] += int(stats[6])
            reference[key]["second_attempts"] += int(stats[7])
            reference[key]["second_won"] += int(stats[8])

    compared_fields = ("serve_points", "first_in", "first_won", "second_attempts", "second_won")
    checks = []
    for player_id, month in sampled:
        lhs = {field: extracted[(player_id, month)][field] for field in compared_fields}
        rhs = {field: reference[(player_id, month)][field] for field in compared_fields}
        checks.append({"player_id": player_id, "month": month, "pass": lhs == rhs, "extracted": lhs, "backtest_reference": rhs})
    return {
        "reference_path": "scripts/backtest-fair-odds.py::_history_from_oncourt",
        "compared_fields": list(compared_fields),
        "sample_seed": seed,
        "sample_size": len(checks),
        "passed": all(item["pass"] for item in checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oncourt-dir", type=Path, default=DEFAULT_ONCOURT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--surface", default="Hard")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260712)
    args = parser.parse_args()

    required = ["games_atp.csv", "stat_atp.csv", "players_atp.csv", "tours_atp.csv", "courts.csv"]
    missing = [name for name in required if not (args.oncourt_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing OnCourt inputs in {args.oncourt_dir}: {', '.join(missing)}")

    output = args.output_dir / "serve-counts-atp.csv.gz"
    iterator, counters = iter_serve_count_rows(
        args.oncourt_dir,
        start_year=args.start_year,
        end_year=args.end_year,
        surface=args.surface or None,
    )
    row_count = write_rows_csv_gz(iterator, output)
    reconciliation = _reconcile(output, args.oncourt_dir, args.sample_size, args.seed, args.end_year)
    if not reconciliation["passed"]:
        raise RuntimeError("Serve-count reconciliation failed")

    inputs = {}
    for name in required:
        path = args.oncourt_dir / name
        inputs[name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    try:
        artifact_path = str(output.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        artifact_path = str(output)
    manifest = {
        "version": VERSION,
        "registered": True,
        "scope": {"tour": "ATP", "surface": args.surface, "start_year": args.start_year, "end_year": args.end_year},
        "artifact": {"path": artifact_path, "format": "csv.gz", "rows": row_count, "sha256": sha256_file(output)},
        "inputs": inputs,
        "counters": dict(counters),
        "reconciliation": {"passed": reconciliation["passed"], "sample_size": reconciliation["sample_size"], "sample_seed": reconciliation["sample_seed"]},
    }
    write_json(args.output_dir / "serve-counts-atp-manifest.json", manifest)
    write_json(args.output_dir / "serve-counts-atp-reconciliation.json", reconciliation)
    print(f"Wrote {row_count:,} player-match rows to {output}")
    print(f"Reconciliation: {reconciliation['sample_size']}/{reconciliation['sample_size']} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
