#!/usr/bin/env python3
"""Audit pre-kickoff odds capture coverage independently of published picks."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEAM_DIR = ROOT / "data" / "team-shots" / "inbox"
DEFAULT_CORNERS = ROOT / "data" / "corners-ou" / "pinnacle-corners-odds.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "football-counts-capture-coverage.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "football-counts-capture-coverage.md"
TRUE_CLOSE_MINUTES = 120.0


def parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def percentile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * proportion)))
    return ordered[index]


def summarize(
    fixtures: dict[str, dict[str, Any]],
    *,
    now: datetime,
    lookback_days: int,
    target: float,
) -> dict[str, Any]:
    cutoff = now - timedelta(days=max(1, lookback_days))
    completed = [
        fixture
        for fixture in fixtures.values()
        if cutoff <= fixture["kickoff"] <= now
    ]
    lags: list[float] = []
    no_pre_kickoff = 0
    for fixture in completed:
        before = [capture for capture in fixture["captures"] if capture <= fixture["kickoff"]]
        if not before:
            no_pre_kickoff += 1
            continue
        close = max(before)
        lags.append((fixture["kickoff"] - close).total_seconds() / 60.0)

    true_close = [lag for lag in lags if lag <= TRUE_CLOSE_MINUTES]
    tracked = len(completed)
    coverage = len(true_close) / tracked if tracked else None
    return {
        "tracked_fixtures": tracked,
        "fixtures_with_pre_kickoff_snapshot": len(lags),
        "fixtures_without_pre_kickoff_snapshot": no_pre_kickoff,
        "true_close_fixtures": len(true_close),
        "true_close_coverage": round(coverage, 6) if coverage is not None else None,
        "median_close_lag_minutes": round(statistics.median(lags), 2) if lags else None,
        "p90_close_lag_minutes": round(percentile(lags, 0.90), 2) if lags else None,
        "target": target,
        "passes": coverage is not None and coverage >= target,
    }


def read_csv(path: Path) -> Iterable[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            yield from csv.DictReader(handle)
    except OSError:
        return


def load_team_fixtures(directory: Path) -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("team-shots-*.csv")) if directory.exists() else []:
        for row in read_csv(path):
            kickoff = parse_dt(row.get("kickoff_at"))
            captured = parse_dt(row.get("captured_at"))
            if kickoff is None or captured is None:
                continue
            event_id = str(row.get("event_id") or "").strip()
            fallback = "|".join(
                [
                    kickoff.date().isoformat(),
                    norm(row.get("competition")),
                    norm(row.get("home_team")),
                    norm(row.get("away_team")),
                    norm(row.get("bookmaker")),
                ]
            )
            key = f"event:{event_id}|{norm(row.get('bookmaker'))}" if event_id else fallback
            fixture = fixtures.setdefault(key, {"kickoff": kickoff, "captures": set()})
            fixture["captures"].add(captured)
    return fixtures


def load_corner_fixtures(path: Path) -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return fixtures
    for row in read_csv(path):
        kickoff = parse_dt(row.get("kickoff_iso"))
        captured = parse_dt(row.get("captured_at"))
        if kickoff is None or captured is None:
            continue
        key = "|".join(
            [
                kickoff.date().isoformat(),
                norm(row.get("league")),
                norm(row.get("home_team")),
                norm(row.get("away_team")),
            ]
        )
        fixture = fixtures.setdefault(key, {"kickoff": kickoff, "captures": set()})
        fixture["captures"].add(captured)
    return fixtures


def format_metric(value: Any, suffix: str = "") -> str:
    return "-" if value is None else f"{value}{suffix}"


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Football Counts Capture Coverage",
        "",
        f"Generated: {payload['generated_at_utc']}",
        f"Lookback: {payload['lookback_days']} days",
        "",
        "This operational report covers every priced fixture, not only model selections.",
        "A true close is the final captured pre-kickoff snapshot no more than 120 minutes before kickoff.",
        "",
        "| Market | Tracked | Pre-KO snapshot | True close | Coverage | Median lag | P90 lag | Target | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label, key in (("Bet365 team shots", "team_shots"), ("Pinnacle corners", "corners")):
        item = payload[key]
        coverage = item["true_close_coverage"]
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    str(item["tracked_fixtures"]),
                    str(item["fixtures_with_pre_kickoff_snapshot"]),
                    str(item["true_close_fixtures"]),
                    f"{coverage:.1%}" if coverage is not None else "-",
                    format_metric(item["median_close_lag_minutes"], "m"),
                    format_metric(item["p90_close_lag_minutes"], "m"),
                    f"{item['target']:.0%}",
                    "PASS" if item["passes"] else "WAIT",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "`WAIT` before fixtures exist is expected. Once a full match weekend is present, failure means the capture cadence must be fixed before judging either model.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit near-kickoff football count price coverage")
    parser.add_argument("--team-dir", type=Path, default=DEFAULT_TEAM_DIR)
    parser.add_argument("--corners", type=Path, default=DEFAULT_CORNERS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--now", default="", help="UTC ISO timestamp for deterministic testing")
    args = parser.parse_args()

    now = parse_dt(args.now) if args.now else datetime.now(UTC)
    if now is None:
        raise SystemExit("Invalid --now timestamp")

    payload = {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "lookback_days": max(1, args.lookback_days),
        "team_shots": summarize(
            load_team_fixtures(args.team_dir),
            now=now,
            lookback_days=args.lookback_days,
            target=0.70,
        ),
        "corners": summarize(
            load_corner_fixtures(args.corners),
            now=now,
            lookback_days=args.lookback_days,
            target=0.50,
        ),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(render_report(payload), encoding="utf-8")
    print(
        "Capture coverage: "
        f"team_shots={payload['team_shots']['true_close_coverage']} "
        f"corners={payload['corners']['true_close_coverage']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
