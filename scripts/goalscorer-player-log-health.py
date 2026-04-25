#!/usr/bin/env python3
"""Check freshness of goalscorer Understat player-match logs.

Used by hosted workflows before live goalscorer refresh/settlement. The old
workflow only checked whether log files existed, which allowed current-season
logs to sit stale for days while live models kept using them.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEAGUES = ["serie-a", "epl", "la-liga", "bundesliga", "ligue-1"]
DEFAULT_OUTPUT = ROOT / "data" / "football-form" / "player-log-health.json"


def current_season(today: date | None = None) -> str:
    today = today or datetime.now(UTC).date()
    start_year = today.year if today.month >= 7 else today.year - 1
    return f"{start_year}-{start_year + 1}"


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text, text[:10]):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def inspect_log(path: Path, *, today: date, max_age_days: int) -> dict[str, Any]:
    rows = 0
    latest: date | None = None
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows += 1
                row_date = parse_date(row.get("match_date") or row.get("date"))
                if row_date and (latest is None or row_date > latest):
                    latest = row_date

    age_days: int | None = (today - latest).days if latest else None
    missing = not path.exists()
    stale = missing or latest is None or (age_days is not None and age_days > max_age_days)
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "exists": path.exists(),
        "rows": rows,
        "latest_match_date": latest.isoformat() if latest else None,
        "age_days": age_days,
        "max_age_days": max_age_days,
        "stale": stale,
        "reason": "missing" if missing else ("no dated rows" if latest is None else ("old" if stale else "fresh")),
    }


def write_github_output(payload: dict[str, Any]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"season={payload['season']}\n")
        handle.write(f"has_stale={'true' if payload['stale_leagues'] else 'false'}\n")
        handle.write(f"stale_leagues={' '.join(payload['stale_leagues'])}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check goalscorer player-log freshness.")
    parser.add_argument("--league", nargs="+", default=DEFAULT_LEAGUES)
    parser.add_argument("--season", default="current", help="Season label, or 'current'.")
    parser.add_argument("--max-age-days", type=int, default=3)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--github-output", action="store_true", help="Write stale_leagues to $GITHUB_OUTPUT.")
    parser.add_argument("--fail-on-stale", action="store_true")
    args = parser.parse_args()

    today = datetime.now(UTC).date()
    season = current_season(today) if args.season == "current" else args.season
    leagues = list(dict.fromkeys(args.league))

    checks: dict[str, Any] = {}
    stale_leagues: list[str] = []
    for league in leagues:
        path = ROOT / "data" / "goalscorer" / f"{league}-player-match-logs-{season}.csv"
        result = inspect_log(path, today=today, max_age_days=args.max_age_days)
        checks[league] = result
        if result["stale"]:
            stale_leagues.append(league)

    payload = {
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "season": season,
        "today": today.isoformat(),
        "max_age_days": args.max_age_days,
        "stale_leagues": stale_leagues,
        "checks": checks,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_github_output(payload)

    if stale_leagues:
        print(f"Stale goalscorer player logs: {' '.join(stale_leagues)}")
    else:
        print("Goalscorer player logs fresh.")
    print(f"Wrote {args.output.relative_to(ROOT)}")

    return 1 if args.fail_on_stale and stale_leagues else 0


if __name__ == "__main__":
    raise SystemExit(main())
