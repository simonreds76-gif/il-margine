#!/usr/bin/env python3
"""Backfill missing ATP qualifying fixtures into ``oncourt_today``.

OnCourt can publish the main-tour shell before its qualifying draw. Pinnacle may
already carry those matches, which otherwise means the pricing pipeline silently
sees zero qualifying fixtures. This script runs after the fresh Pinnacle scrape
and adds only uniquely resolved, pre-match singles for a current ATP tournament.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import sackmann_tml_id_map as idmap


DEFAULT_REPORT = ROOT / "data" / "backtest" / "masters-qualifying-coverage.json"
# Legacy filename/report retained for existing callers. Coverage includes ranks 2/3/4.
from tennis_qualifying_coverage import (
    event_key, current_tours, is_upcoming_quote, schedule_coverage,
)



def load_env(root: Path = ROOT) -> None:
    for filename in (".env.local", "env.local"):
        path = root / filename
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str | None) -> str:
    return idmap.normalize_name(value or "")


def compact_name(value: str | None) -> str:
    return normalize(value).replace(" ", "")


def is_singles_name(value: str | None) -> bool:
    raw = str(value or "")
    return bool(raw.strip()) and "/" not in raw and "&" not in raw


def is_qualifier_market(row: dict[str, str], target: date) -> bool:
    if str(row.get("league") or "").strip().upper() != "ATP":
        return False
    league_name = str(row.get("league_name") or "")
    if "qualif" not in league_name.lower() or event_key(league_name) is None:
        return False
    if not is_singles_name(row.get("player1_name")) or not is_singles_name(row.get("player2_name")):
        return False
    try:
        match_day = date.fromisoformat(str(row.get("match_date") or "")[:10])
    except ValueError:
        return False
    return target <= match_day <= target + timedelta(days=1)


def load_players(path: Path) -> list[dict[str, Any]]:
    players: list[dict[str, Any]] = []
    for row in read_csv(path):
        try:
            pid = int(row.get("id") or 0)
        except ValueError:
            continue
        name = str(row.get("name") or "").strip()
        if not pid or not is_singles_name(name):
            continue
        players.append(
            {
                "id": pid,
                "name": name,
                "birthdate": str(row.get("birthdate") or "")[:10] or None,
                "country": str(row.get("country") or "").strip().upper() or None,
            }
        )
    return players


def build_player_resolver(players: list[dict[str, Any]]):
    normalized: dict[str, set[int]] = defaultdict(set)
    compact: dict[str, set[int]] = defaultdict(set)
    reversed_full: dict[str, set[int]] = defaultdict(set)
    for row in players:
        pid = int(row["id"])
        norm = normalize(row.get("name"))
        normalized[norm].add(pid)
        compact[norm.replace(" ", "")].add(pid)
        reversed_full[" ".join(reversed(norm.split()))].add(pid)

    def resolve(name: str) -> tuple[int | None, str | None]:
        norm = normalize(name)
        attempts = (
            (normalized.get(norm, set()), "normalized_full"),
            (compact.get(norm.replace(" ", ""), set()), "compact_full"),
            (reversed_full.get(norm, set()), "reversed_full"),
        )
        for candidates, method in attempts:
            if len(candidates) == 1:
                return next(iter(candidates)), method
        return None, None

    return resolve


def find_current_masters_tours(
    rows: list[dict[str, str]], target: date
) -> dict[str, dict[str, Any]]:
    # Compatibility function name for old callers/tests.
    return current_tours(rows, target)


def resolve_fixture_rows(
    market_rows: list[dict[str, str]],
    resolve_player,
    tours_by_key: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int]] = set()
    for row in market_rows:
        key = event_key(row.get("league_name"))
        tour = tours_by_key.get(str(key))
        p1, method1 = resolve_player(str(row.get("player1_name") or ""))
        p2, method2 = resolve_player(str(row.get("player2_name") or ""))
        reason = None
        if tour is None:
            reason = "current_atp_tour_missing_or_ambiguous"
        elif p1 is None or p2 is None:
            reason = "player_name_unresolved"
        elif p1 == p2:
            reason = "same_player_id"
        if reason:
            unresolved.append(
                {
                    "player1_name": row.get("player1_name"),
                    "player2_name": row.get("player2_name"),
                    "league_name": row.get("league_name"),
                    "match_date": row.get("match_date"),
                    "reason": reason,
                    "player1_id": p1,
                    "player2_id": p2,
                }
            )
            continue
        pair = tuple(sorted((int(p1), int(p2))))
        unique_key = (int(tour["tour_id"]), pair[0], pair[1])
        if unique_key in seen:
            continue
        seen.add(unique_key)
        resolved.append(
            {
                "tour_id": int(tour["tour_id"]),
                "tour_name": tour["tour_name"],
                "player1_id": int(p1),
                "player2_id": int(p2),
                "player1_name": row.get("player1_name"),
                "player2_name": row.get("player2_name"),
                "player1_method": method1,
                "player2_method": method2,
                "round_id": 1,
                "match_date": row.get("match_date"),
                "kickoff_iso": row.get("kickoff_iso"),
                "league_name": row.get("league_name"),
            }
        )
    return resolved, unresolved


def supabase_config() -> tuple[str, dict[str, str]]:
    load_env()
    base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or ""
    if not base or not key:
        raise RuntimeError("Supabase URL/key unavailable")
    return base, {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def fetch_open_pairs(base: str, headers: dict[str, str]) -> set[tuple[int, int, int]]:
    response = requests.get(
        f"{base}/rest/v1/oncourt_today",
        headers=headers,
        params={"select": "tour_id,player1_id,player2_id", "limit": "5000"},
        timeout=60,
    )
    response.raise_for_status()
    pairs: set[tuple[int, int, int]] = set()
    for row in response.json() or []:
        try:
            tour_id = int(row["tour_id"])
            pair = sorted((int(row["player1_id"]), int(row["player2_id"])))
        except (KeyError, TypeError, ValueError):
            continue
        pairs.add((tour_id, pair[0], pair[1]))
    return pairs


def insert_fixtures(base: str, headers: dict[str, str], rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    payload = []
    for index, row in enumerate(rows, start=1):
        payload.append(
            {
                "tour_id": row["tour_id"],
                "player1_id": row["player1_id"],
                "player2_id": row["player2_id"],
                "round_id": row["round_id"],
                "draw": 9000 + index,
                "result": "",
            }
        )
    post_headers = dict(headers)
    post_headers["Prefer"] = "return=minimal"
    response = requests.post(
        f"{base}/rest/v1/oncourt_today",
        headers=post_headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()


def latest_pinnacle_file(data_dir: Path, target: date) -> Path | None:
    exact = data_dir / f"pinnacle-odds-{target.isoformat()}.csv"
    if exact.exists():
        return exact
    candidates = sorted(data_dir.glob("pinnacle-odds-*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Supplement missing ATP qualifying fixtures")
    parser.add_argument("--date", default=date.today().isoformat(), help="Target date (YYYY-MM-DD)")
    parser.add_argument("--pinnacle-file", default="", help="Override Pinnacle snapshot CSV")
    parser.add_argument("--players-file", default=str(ROOT / "data" / "oncourt" / "players_atp.csv"))
    parser.add_argument("--tours-file", default=str(ROOT / "data" / "oncourt" / "tours_atp.csv"))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--schedule-file", default=str(ROOT / "data" / "oncourt" / "today_atp.csv"))
    parser.add_argument("--max-snapshot-age-hours", type=float, default=2.0)
    parser.add_argument("--min-coverage", type=float, default=0.80)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = date.fromisoformat(args.date)
    pinnacle_path = Path(args.pinnacle_file) if args.pinnacle_file else latest_pinnacle_file(ROOT / "data", target)
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_date": target.isoformat(),
        "pinnacle_file": str(pinnacle_path) if pinnacle_path else None,
        "dry_run": bool(args.dry_run),
    }
    if pinnacle_path is None or not pinnacle_path.exists():
        report.update({"status": "no_pinnacle_snapshot", "pinnacle_qualifier_matches": 0})
        write_report(Path(args.report), report)
        print("ATP qualifier coverage: no Pinnacle snapshot; cannot verify coverage.")
        return 1

    now = datetime.now(timezone.utc)
    snapshot_age = (now.timestamp() - pinnacle_path.stat().st_mtime) / 3600
    if not 0 <= snapshot_age <= args.max_snapshot_age_hours:
        report.update({"status": "stale_pinnacle_snapshot", "snapshot_age_hours": snapshot_age})
        write_report(Path(args.report), report)
        print("ERROR: ATP qualifying coverage requires a fresh Pinnacle snapshot.")
        return 1
    all_market_rows = read_csv(pinnacle_path)
    candidates = [row for row in all_market_rows if is_qualifier_market(row, target)]
    market_rows = [row for row in candidates if is_upcoming_quote(row, now)]
    report["excluded_started_or_untimed_quotes"] = len(candidates) - len(market_rows)
    report["pinnacle_qualifier_matches"] = len(market_rows)
    report["events"] = sorted({str(row.get("league_name") or "") for row in market_rows})
    players = load_players(Path(args.players_file))
    tours = find_current_masters_tours(read_csv(Path(args.tours_file)), target)
    coverage = schedule_coverage(read_csv(Path(args.schedule_file)), tours, all_market_rows,
                                 build_player_resolver(players), target, now)
    report["scheduled_tournament_coverage"] = coverage
    report["missing_scheduled_prices"] = sum(row["missing_prices"] for row in coverage)
    for row in coverage:
        print(f"ATP qualifying: {row['tournament']}: {row['scheduled_qualifiers']} scheduled, "
              f"{row['with_current_prices']} priced, {row['missing_prices']} awaiting Pinnacle prices.")
    if not market_rows:
        report["status"] = "awaiting_prices" if report["missing_scheduled_prices"] else "no_current_atp_qualifiers"
        write_report(Path(args.report), report)
        print("ATP qualifier coverage: no upcoming qualifying quotes to supplement. Missing prices are not a no-value verdict.")
        return 0

    resolved, unresolved = resolve_fixture_rows(market_rows, build_player_resolver(players), tours)
    report.update(
        {
            "resolved_matches": len(resolved),
            "unresolved_matches": len(unresolved),
            "unresolved": unresolved,
            "resolved": resolved,
        }
    )

    if args.dry_run:
        existing: set[tuple[int, int, int]] = set()
        inserted = resolved
    else:
        base, headers = supabase_config()
        existing = fetch_open_pairs(base, headers)
        inserted = []
        for row in resolved:
            pair = sorted((row["player1_id"], row["player2_id"]))
            if (row["tour_id"], pair[0], pair[1]) not in existing:
                inserted.append(row)
        insert_fixtures(base, headers, inserted)

    existing_count = len(resolved) - len(inserted)
    covered = existing_count + len(inserted)
    coverage = covered / len(market_rows) if market_rows else 1.0
    report.update(
        {
            "already_present_matches": existing_count,
            "inserted_matches": len(inserted),
            "covered_matches": covered,
            "coverage_ratio": round(coverage, 6),
            "status": ("schedule_covered_awaiting_prices" if report["missing_scheduled_prices"] else "covered")
            if coverage >= args.min_coverage else "coverage_failed",
        }
    )
    write_report(Path(args.report), report)
    print(
        "ATP qualifier coverage: "
        f"Pinnacle={len(market_rows)}, resolved={len(resolved)}, existing={existing_count}, "
        f"inserted={len(inserted)}, unresolved={len(unresolved)}, coverage={coverage:.1%}"
    )
    if coverage < args.min_coverage:
        print(f"ERROR: ATP qualifying coverage below required {args.min_coverage:.0%}.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
