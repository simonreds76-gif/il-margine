#!/usr/bin/env python3
"""Download aggregate Understat shot features for the registered corners v3 test.

Only match-level aggregates are written. Raw responses are cached locally so a
multi-season backfill is resumable and does not repeatedly hit Understat.

WIDE is a declared proxy: the share of shots with ``abs(Y - 0.5) >= 0.18``.
BLOCK is the share whose result is ``BlockedShot``. These proxies stay research
only until the separate event-level causality check is complete.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "team-shots" / "understat" / "corner-event-features.csv"
DEFAULT_CACHE = ROOT / "data" / "team-shots" / "understat" / "event-cache"
LEAGUE_URL = "https://understat.com/getLeagueData/{slug}/{season}"
MATCH_URL = "https://understat.com/getMatchData/{match_id}"
LEAGUES = {
    "epl": "EPL",
    "serie-a": "Serie_A",
    "la-liga": "La_liga",
    "bundesliga": "Bundesliga",
    "ligue-1": "Ligue_1",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}
WIDE_Y_DISTANCE = 0.18
FIELDS = (
    "match_id",
    "date",
    "league",
    "season",
    "home_team",
    "away_team",
    "home_shots",
    "away_shots",
    "home_wide_shots",
    "away_wide_shots",
    "home_wide_share",
    "away_wide_share",
    "home_blocked_shots",
    "away_blocked_shots",
    "home_blocked_rate",
    "away_blocked_rate",
    "wide_proxy_definition",
    "source",
)


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def aggregate_shots(shots: list[dict[str, Any]]) -> dict[str, float | int]:
    valid = [shot for shot in shots if isinstance(shot, dict)]
    wide = 0
    blocked = 0
    for shot in valid:
        y = safe_float(shot.get("Y"))
        if y is not None and abs(y - 0.5) >= WIDE_Y_DISTANCE:
            wide += 1
        if str(shot.get("result") or "").strip().lower() == "blockedshot":
            blocked += 1
    total = len(valid)
    return {
        "shots": total,
        "wide_shots": wide,
        "wide_share": wide / total if total else 0.0,
        "blocked_shots": blocked,
        "blocked_rate": blocked / total if total else 0.0,
    }


def parse_match_payload(
    payload: dict[str, Any],
    *,
    match_id: str,
    league: str,
    season: int,
    fixture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shots = payload.get("shots") or {}
    if not isinstance(shots, dict):
        raise ValueError(f"Understat match {match_id} has no shot dictionary")
    home_shots = shots.get("h") or []
    away_shots = shots.get("a") or []
    home = aggregate_shots(home_shots if isinstance(home_shots, list) else [])
    away = aggregate_shots(away_shots if isinstance(away_shots, list) else [])

    fixture = fixture or {}
    first_shot = next(
        (shot for side in (home_shots, away_shots) if isinstance(side, list) for shot in side if isinstance(shot, dict)),
        {},
    )
    date_value = str(first_shot.get("date") or fixture.get("datetime") or "").split(" ")[0]
    home_team = str(first_shot.get("h_team") or (fixture.get("h") or {}).get("title") or "").strip()
    away_team = str(first_shot.get("a_team") or (fixture.get("a") or {}).get("title") or "").strip()
    return {
        "match_id": match_id,
        "date": date_value,
        "league": league,
        "season": f"{season}-{season + 1}",
        "home_team": home_team,
        "away_team": away_team,
        "home_shots": home["shots"],
        "away_shots": away["shots"],
        "home_wide_shots": home["wide_shots"],
        "away_wide_shots": away["wide_shots"],
        "home_wide_share": round(float(home["wide_share"]), 6),
        "away_wide_share": round(float(away["wide_share"]), 6),
        "home_blocked_shots": home["blocked_shots"],
        "away_blocked_shots": away["blocked_shots"],
        "home_blocked_rate": round(float(home["blocked_rate"]), 6),
        "away_blocked_rate": round(float(away["blocked_rate"]), 6),
        "wide_proxy_definition": f"abs(Y-0.5)>={WIDE_Y_DISTANCE}",
        "source": "understat_getMatchData",
    }


def request_json(url: str, *, timeout: int = 30, retries: int = 3) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object from {url}")
            return payload
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def load_existing(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {str(row.get("match_id") or ""): row for row in csv.DictReader(handle) if row.get("match_id")}


def write_output(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (str(row.get("date")), str(row.get("match_id")))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leagues", nargs="+", choices=sorted(LEAGUES), default=sorted(LEAGUES))
    parser.add_argument("--seasons", nargs="+", type=int, default=list(range(2019, 2026)))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--limit", type=int, default=0, help="Global match limit; 0 means all discovered matches")
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    existing = {} if args.overwrite else load_existing(args.output)
    output: dict[str, dict[str, Any]] = dict(existing)
    processed = 0
    failures = 0
    discovered = 0
    jobs: list[tuple[str, int, dict[str, Any], str]] = []

    for league in args.leagues:
        slug = LEAGUES[league]
        for season in sorted(set(args.seasons)):
            try:
                league_payload = request_json(LEAGUE_URL.format(slug=slug, season=season))
            except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
                failures += 1
                print(f"WARN {league}/{season}/league: {exc}")
                continue
            fixtures = league_payload.get("dates") or []
            for fixture in fixtures:
                if not isinstance(fixture, dict):
                    continue
                match_id = str(fixture.get("id") or "").strip()
                if not match_id:
                    continue
                discovered += 1
                if match_id in output and not args.overwrite:
                    continue
                jobs.append((league, season, fixture, match_id))

    if args.limit:
        jobs = jobs[: args.limit]

    def fetch_job(job: tuple[str, int, dict[str, Any], str]) -> tuple[str, dict[str, Any]]:
        league, season, fixture, match_id = job
        cache_path = args.cache_dir / f"{match_id}.json"
        if cache_path.exists() and not args.overwrite:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            payload = request_json(MATCH_URL.format(match_id=match_id))
            cache_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            time.sleep(max(0.0, args.delay))
        return match_id, parse_match_payload(
            payload,
            match_id=match_id,
            league=league,
            season=season,
            fixture=fixture,
        )

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_jobs = {executor.submit(fetch_job, job): job for job in jobs}
        for future in as_completed(future_jobs):
            league, season, _fixture, match_id = future_jobs[future]
            try:
                result_id, row = future.result()
                output[result_id] = row
                processed += 1
                if processed % 100 == 0:
                    write_output(args.output, list(output.values()))
                    print(f"Processed {processed}; total cached aggregates {len(output)}", flush=True)
            except (OSError, ValueError, requests.RequestException, json.JSONDecodeError) as exc:
                failures += 1
                print(f"WARN {league}/{season}/{match_id}: {exc}", flush=True)

    write_output(args.output, list(output.values()))
    print(f"Discovered={discovered} processed={processed} failures={failures} total={len(output)}")
    return 0 if failures == 0 or output else 1


if __name__ == "__main__":
    raise SystemExit(main())
