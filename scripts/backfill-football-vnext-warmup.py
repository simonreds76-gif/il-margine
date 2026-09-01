#!/usr/bin/env python3
"""Recover MD1-3 tracking selections from committed vNext scan history."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publish-football-vnext-shadow.py"
CANDIDATE_PATH = "data/football-form/football-counts-vnext-candidates.csv"


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("football_vnext_warmup_backfill", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def is_pre_kickoff(row: dict[str, Any]) -> bool:
    try:
        published = datetime.fromisoformat(str(row.get("published_at_utc") or "").replace("Z", "+00:00"))
        kickoff = datetime.fromisoformat(str(row.get("kickoff_utc") or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    return published < kickoff


def historical_rows(candidate_path: str) -> list[dict[str, str]]:
    commits = [line for line in git_output("log", "--format=%H", "--", candidate_path).splitlines() if line]
    rows: list[dict[str, str]] = []
    for commit in commits:
        try:
            payload = git_output("show", f"{commit}:{candidate_path}")
        except subprocess.CalledProcessError:
            continue
        rows.extend(dict(row) for row in csv.DictReader(io.StringIO(payload)))
    return rows


def first_qualifying_rows(publisher: Any, candidates: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Replay scans in publication order and freeze the first qualifying fixture pick."""
    snapshots: dict[str, list[dict[str, str]]] = {}
    for row in candidates:
        published_at = str(row.get("published_at_utc") or "")
        snapshots.setdefault(published_at, []).append(row)

    recovered: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for published_at in sorted(snapshots):
        for row in publisher.warmup_tracking_signals(snapshots[published_at]):
            fixture = (str(row.get("model") or ""), str(row.get("match_id") or ""))
            if fixture in seen:
                continue
            recovered.append(row)
            seen.add(fixture)
    return recovered


def without_warmup(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("signal_status") or "").strip().lower() != "warmup_tracking"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-path", default=CANDIDATE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    publisher = load_module()
    candidates = [row for row in historical_rows(args.candidate_path) if is_pre_kickoff(row)]
    tracking = first_qualifying_rows(publisher, candidates)
    team_rows = [row for row in tracking if row.get("model") == publisher.TEAM_MODEL]
    corners_rows = [row for row in tracking if row.get("model") == publisher.CORNERS_MODEL]

    print(
        f"Recovered fixture-level warm-up selections: "
        f"Team Shots v4={len(team_rows)}, Corners v3={len(corners_rows)}"
    )
    if args.dry_run:
        return 0

    team_ledger = publisher.PUB.merge_published_ledger(
        without_warmup(publisher.PUB.load_csv(publisher.TEAM_OUTPUT)), team_rows
    )
    corners_ledger = publisher.PUB.merge_published_ledger(
        without_warmup(publisher.PUB.load_csv(publisher.CORNERS_OUTPUT)), corners_rows
    )
    publisher.write_csv(publisher.TEAM_OUTPUT, team_ledger)
    publisher.write_csv(publisher.CORNERS_OUTPUT, corners_ledger)
    print(f"Wrote {publisher.TEAM_OUTPUT.relative_to(ROOT)} ({len(team_ledger)} rows)")
    print(f"Wrote {publisher.CORNERS_OUTPUT.relative_to(ROOT)} ({len(corners_ledger)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
