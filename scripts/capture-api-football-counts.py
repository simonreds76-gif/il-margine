#!/usr/bin/env python3
"""Archive completed top-five-league match counts from API-Football.

The collector is deliberately bounded for the 100-request free tier. It lists
fixtures for a short date window, requests statistics only for fixture IDs not
already in the archive, and never writes to Supabase.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable, Optional

from api_football_match_stats import LEAGUE_CONFIGS, _request, _safe_int, _season_for_day, parse_fixture_statistics
from settlement_utils import normalize_team_name


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "football-form" / "api-football-counts.csv"
DEFAULT_HEALTH_JSON = ROOT / "data" / "football-form" / "api-football-counts-health.json"
DEFAULT_HEALTH_MD = ROOT / "data" / "football-form" / "api-football-counts-health.md"
FINISHED_STATUSES = {"FT", "AET", "PEN"}
COUNT_FIELDS = (
    "home_shots",
    "away_shots",
    "home_sot",
    "away_sot",
    "home_corners",
    "away_corners",
    "home_fouls",
    "away_fouls",
    "home_yellow_cards",
    "away_yellow_cards",
    "home_red_cards",
    "away_red_cards",
    "home_offsides",
    "away_offsides",
    "home_blocked_shots",
    "away_blocked_shots",
    "home_goalkeeper_saves",
    "away_goalkeeper_saves",
)
ARCHIVE_FIELDS = (
    "fixture_id",
    "date",
    "kickoff_utc",
    "league",
    "league_id",
    "season",
    "fixture_status",
    "home_team",
    "away_team",
    "home_team_source_name",
    "away_team_source_name",
    "home_team_id",
    "away_team_id",
    *COUNT_FIELDS,
    "total_corners",
    "referee",
    "source",
    "captured_at",
)


def load_env_files() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_archive(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_archive_atomic(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: (str(row.get("date") or ""), str(row.get("fixture_id") or "")))
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=ARCHIVE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ordered)
        temporary = Path(handle.name)
    temporary.replace(path)


def _fixture_date(row: dict, fallback: date) -> str:
    timestamp = str((row.get("fixture") or {}).get("date") or "").strip()
    return timestamp[:10] if len(timestamp) >= 10 else fallback.isoformat()


def _blank_counts() -> dict[str, None]:
    return {field: None for field in COUNT_FIELDS}


def collect_counts(
    target_dates: Iterable[date],
    existing_rows: list[dict[str, str]],
    *,
    max_requests: int,
    request_fn: Callable[[str, dict], dict] = _request,
    captured_at: Optional[datetime] = None,
) -> tuple[list[dict], dict]:
    """Collect uncaptured fixture counts and return the complete archive plus health."""
    captured_at = captured_at or datetime.now(UTC)
    rows_by_fixture = {
        str(row.get("fixture_id") or "").strip(): dict(row)
        for row in existing_rows
        if str(row.get("fixture_id") or "").strip()
    }
    requests_used = 0
    discovered = 0
    new_rows = 0
    skipped_existing = 0
    truncated = False
    errors: list[str] = []

    def request(path: str, params: dict) -> Optional[dict]:
        nonlocal requests_used, truncated
        if requests_used >= max_requests:
            truncated = True
            return None
        requests_used += 1
        try:
            return request_fn(path, params)
        except Exception as exc:
            errors.append(f"{path} {params}: {exc}")
            return None

    # Newest first: a tight quota should preserve the most actionable results.
    for day in sorted(set(target_dates), reverse=True):
        for league_key, config in LEAGUE_CONFIGS.items():
            if requests_used >= max_requests:
                truncated = True
                break
            season = _season_for_day(day)
            payload = request(
                "fixtures",
                {
                    "league": config["league_id"],
                    "season": season,
                    "date": day.isoformat(),
                    "status": "FT-AET-PEN",
                },
            )
            if payload is None:
                continue
            if payload.get("errors"):
                errors.append(f"fixtures {league_key} {day.isoformat()}: {payload['errors']}")
                continue
            for fixture_row in payload.get("response") or []:
                fixture = fixture_row.get("fixture") or {}
                status = str((fixture.get("status") or {}).get("short") or "").upper()
                if status not in FINISHED_STATUSES:
                    continue
                fixture_id = _safe_int(fixture.get("id"))
                if fixture_id is None:
                    continue
                discovered += 1
                fixture_key = str(fixture_id)
                if fixture_key in rows_by_fixture:
                    skipped_existing += 1
                    continue
                if requests_used >= max_requests:
                    truncated = True
                    break

                stats_payload = request("fixtures/statistics", {"fixture": fixture_id})
                if stats_payload is None:
                    break
                if stats_payload.get("errors"):
                    errors.append(f"fixtures/statistics {fixture_id}: {stats_payload['errors']}")
                    continue
                teams = fixture_row.get("teams") or {}
                home_source = str((teams.get("home") or {}).get("name") or "").strip()
                away_source = str((teams.get("away") or {}).get("name") or "").strip()
                parsed = parse_fixture_statistics(fixture_row, stats_payload.get("response") or [])
                if parsed is None:
                    parsed = {
                        "home_team": normalize_team_name(home_source),
                        "away_team": normalize_team_name(away_source),
                        "home_team_id": _safe_int((teams.get("home") or {}).get("id")),
                        "away_team_id": _safe_int((teams.get("away") or {}).get("id")),
                        **_blank_counts(),
                        "total_corners": None,
                        "referee": str(fixture.get("referee") or "").strip() or None,
                        "source": "api-football",
                        "fixture_id": fixture_id,
                    }
                row = {
                    **parsed,
                    "fixture_id": fixture_id,
                    "date": _fixture_date(fixture_row, day),
                    "kickoff_utc": str(fixture.get("date") or ""),
                    "league": league_key,
                    "league_id": config["league_id"],
                    "season": season,
                    "fixture_status": status,
                    "home_team_source_name": home_source,
                    "away_team_source_name": away_source,
                    "captured_at": captured_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                }
                rows_by_fixture[fixture_key] = row
                new_rows += 1
            if truncated:
                break
        if truncated:
            break

    rows = list(rows_by_fixture.values())
    latest_date = max((str(row.get("date") or "") for row in rows), default="")
    coverage = {}
    for field in COUNT_FIELDS:
        present = sum(str(row.get(field) if row.get(field) is not None else "").strip() != "" for row in rows)
        coverage[field] = {
            "present": present,
            "rows": len(rows),
            "pct": round((present / len(rows) * 100) if rows else 0.0, 1),
        }
    health = {
        "generated_at": captured_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "archive_rows": len(rows),
        "new_rows": new_rows,
        "fixtures_discovered": discovered,
        "skipped_existing": skipped_existing,
        "latest_fixture_date": latest_date or None,
        "requests_used": requests_used,
        "max_requests": max_requests,
        "truncated_by_request_budget": truncated,
        "errors": errors,
        "coverage": coverage,
        "database_writes": 0,
    }
    return rows, health


def render_health(health: dict) -> str:
    lines = [
        "# API-Football Count Archive Health",
        "",
        f"- Generated: {health['generated_at']}",
        f"- Archive: {health['archive_rows']} fixtures; {health['new_rows']} new this run",
        f"- Latest fixture: {health['latest_fixture_date'] or '-'}",
        f"- Requests: {health['requests_used']}/{health['max_requests']}",
        f"- Request-budget truncation: {'YES' if health['truncated_by_request_budget'] else 'no'}",
        f"- Errors: {len(health['errors'])}",
        "- Storage: local CSV only; zero database writes",
        "",
        "## Field Coverage",
        "",
    ]
    for field, row in health["coverage"].items():
        lines.append(f"- {field}: {row['present']}/{row['rows']} ({row['pct']:.1f}%)")
    if health["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in health["errors"][:20])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture bounded API-Football top-five match counts.")
    parser.add_argument("--date", action="append", help="Target YYYY-MM-DD; repeatable.")
    parser.add_argument("--days-back", type=int, default=2, help="Include today plus this many prior UTC days.")
    parser.add_argument("--max-requests", type=int, default=90)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--health-json", type=Path, default=DEFAULT_HEALTH_JSON)
    parser.add_argument("--health-report", type=Path, default=DEFAULT_HEALTH_MD)
    parser.add_argument("--allow-missing-key", action="store_true")
    args = parser.parse_args()

    load_env_files()
    if not (os.getenv("API_FOOTBALL_KEY") or "").strip():
        message = "API_FOOTBALL_KEY is not configured; archive capture skipped."
        if args.allow_missing_key:
            print(message)
            return 0
        raise SystemExit(message)
    if args.max_requests <= 0 or args.max_requests > 100:
        raise SystemExit("--max-requests must be between 1 and 100")

    if args.date:
        target_dates = [date.fromisoformat(value) for value in args.date]
    else:
        today = datetime.now(UTC).date()
        target_dates = [today - timedelta(days=offset) for offset in range(max(0, args.days_back) + 1)]

    rows, health = collect_counts(
        target_dates,
        read_archive(args.output),
        max_requests=args.max_requests,
    )
    write_archive_atomic(args.output, rows)
    args.health_json.parent.mkdir(parents=True, exist_ok=True)
    args.health_json.write_text(json.dumps(health, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.health_report.write_text(render_health(health), encoding="utf-8")
    print(
        f"API-Football archive: {health['archive_rows']} rows, {health['new_rows']} new, "
        f"requests {health['requests_used']}/{health['max_requests']}, "
        f"truncated={health['truncated_by_request_budget']}"
    )
    return 1 if health["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
