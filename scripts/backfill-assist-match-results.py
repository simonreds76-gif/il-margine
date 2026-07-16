#!/usr/bin/env python3
"""Refresh legacy FotMob result files that predate assist completeness fields."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import runpy
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = ROOT / "data" / "goalscorer" / "match-results"


def needs_refresh(payload: dict, *, include_incomplete: bool = False) -> bool:
    if "assist_data_complete" not in payload:
        return True
    return bool(include_incomplete and not payload.get("assist_data_complete"))


def match_stub(payload: dict) -> dict:
    return {
        "id": payload.get("match_id"),
        "home": {
            "id": payload.get("home_fotmob_team_id"),
            "name": payload.get("home_team"),
            "longName": payload.get("home_team"),
        },
        "away": {
            "id": payload.get("away_fotmob_team_id"),
            "name": payload.get("away_team"),
            "longName": payload.get("away_team"),
        },
        "status": {
            "started": payload.get("status_started", True),
            "finished": payload.get("status_finished", True),
            "cancelled": payload.get("status_cancelled", False),
            "scoreStr": f"{int(payload.get('home_score') or 0)}-{int(payload.get('away_score') or 0)}",
            "utcTime": payload.get("match_date"),
            "reason": {"long": payload.get("status_reason", "Full-Time")},
        },
    }


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if ch.isalnum()).casefold()


def identity_matches(existing: dict, rebuilt: dict, *, max_date_drift_days: int = 2) -> bool:
    existing_teams = {
        normalize_name(existing.get("home_team")),
        normalize_name(existing.get("away_team")),
    }
    rebuilt_teams = {
        normalize_name(rebuilt.get("home_team")),
        normalize_name(rebuilt.get("away_team")),
    }
    if "" in existing_teams or existing_teams != rebuilt_teams:
        return False
    try:
        old_date = dt.date.fromisoformat(str(existing.get("match_date") or "")[:10])
        new_date = dt.date.fromisoformat(str(rebuilt.get("match_date") or "")[:10])
    except ValueError:
        return False
    return abs((new_date - old_date).days) <= max_date_drift_days


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill assist metadata in legacy FotMob result files")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--limit", type=int, default=0, help="Maximum files to refresh; zero means all")
    parser.add_argument("--include-incomplete", action="store_true", help="Also retry modern files explicitly marked incomplete")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    module = runpy.run_path(str(ROOT / "scripts" / "fotmob-fetch-match-detail.py"), run_name="fotmob_assist_backfill")
    fetch_payload = module["_fetch_match_payload"]
    build_result = module["_build_match_result"]

    candidates: list[tuple[Path, dict]] = []
    for path in sorted(Path(args.results_dir).glob("*/fotmob-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if needs_refresh(payload, include_incomplete=args.include_incomplete):
            candidates.append((path, payload))
    if args.limit > 0:
        candidates = candidates[: args.limit]

    print(f"Legacy assist result files selected: {len(candidates)}")
    if args.dry_run:
        for path, _payload in candidates[:20]:
            print(f" - {path}")
        return 0

    refreshed = 0
    complete = 0
    failed = 0
    for index, (path, existing) in enumerate(candidates, start=1):
        match_id = int(existing.get("match_id") or 0)
        if not match_id:
            failed += 1
            continue
        try:
            raw = fetch_payload(match_id)
            rebuilt = build_result(str(existing.get("league") or path.parent.name), match_stub(existing), raw)
            if rebuilt is None:
                raise ValueError("FotMob rebuild returned no result")
            if not identity_matches(existing, rebuilt):
                raise ValueError(
                    "FotMob identity mismatch; refusing overwrite: "
                    f"{existing.get('match_date')} {existing.get('home_team')} vs {existing.get('away_team')} -> "
                    f"{rebuilt.get('match_date')} {rebuilt.get('home_team')} vs {rebuilt.get('away_team')}"
                )
            path.write_text(json.dumps(rebuilt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            refreshed += 1
            complete += int(bool(rebuilt.get("assist_data_complete")))
            print(f"[{index}/{len(candidates)}] {match_id}: complete={bool(rebuilt.get('assist_data_complete'))}")
        except Exception as exc:
            failed += 1
            print(f"[{index}/{len(candidates)}] {match_id}: FAILED {exc}")

    print(f"Refreshed: {refreshed}; assist-complete: {complete}; failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
