"""Refresh recent ATP/Challenger activity used by the fair-odds model.

The fair-odds engine reads ``player_recent_activity`` for form, fatigue,
inactivity and data-coverage adjustments.  This job deliberately updates only
players in the current OnCourt ATP/Challenger schedule, keeping the daily
Supabase write small while ensuring every priced fixture has fresh inputs.

Usage:
  python scripts/oncourt-compute-recent-activity.py
  python scripts/oncourt-compute-recent-activity.py --dry-run
  python scripts/oncourt-compute-recent-activity.py --as-of 2026-07-17
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "oncourt"
STATUS_PATH = DATA_DIR / "recent-activity-status.json"
ITF_PATTERN = re.compile(r"\b[MW]\d{1,2}\b", re.IGNORECASE)
GRAND_SLAMS = (
    "AUSTRALIAN OPEN",
    "FRENCH OPEN",
    "ROLAND GARROS",
    "WIMBLEDON",
    "US OPEN",
    "U.S. OPEN",
)
WALKOVER_MARKERS = ("W/O", "W.O", "WALKOVER", "BYE")
DEFAULT_ELO = 1500.0
REQUEST_TIMEOUT = 45
UPSERT_BATCH = 200
ELO_QUERY_BATCH = 150


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not os.environ.get(key):
                os.environ[key] = value.strip().strip('"').strip("'")


def parse_date(value: object) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def safe_int(value: object) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def read_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def is_supported_tour(row: dict[str, str]) -> bool:
    name = (row.get("name") or "").strip()
    upper = name.upper()
    if ITF_PATTERN.search(name) or "ITF" in upper or "FUTURES" in upper or "JUNIOR" in upper:
        return False
    rank = safe_int(row.get("rank"))
    if any(slam in upper for slam in GRAND_SLAMS):
        return True
    if rank is not None and rank <= 3:
        return True
    return "CHALLENGER" in upper or "ATP" in upper or "MASTERS" in upper or "GRAND SLAM" in upper


def load_fixture_player_ids(today_path: Path, tours_path: Path) -> set[int]:
    if not today_path.exists() or not tours_path.exists():
        missing = today_path if not today_path.exists() else tours_path
        raise FileNotFoundError(f"Missing OnCourt input: {missing}")

    supported_tours = {
        tour_id
        for row in read_csv(tours_path)
        if (tour_id := safe_int(row.get("id"))) is not None and is_supported_tour(row)
    }
    player_ids: set[int] = set()
    for row in read_csv(today_path):
        if (row.get("result") or "").strip():
            continue
        tour_id = safe_int(row.get("tour_id"))
        player1_id = safe_int(row.get("player1_id"))
        player2_id = safe_int(row.get("player2_id"))
        if tour_id not in supported_tours or not player1_id or not player2_id:
            continue
        # OnCourt uses a self-pair placeholder while future draw slots are unknown.
        if player1_id == player2_id:
            continue
        player_ids.update((player1_id, player2_id))
    return player_ids


def is_played_match(result: object) -> bool:
    upper = str(result or "").strip().upper()
    return bool(upper) and not any(marker in upper for marker in WALKOVER_MARKERS)


def aggregate_activity(
    game_paths: Iterable[Path],
    fixture_player_ids: set[int],
    as_of: date,
) -> tuple[dict[int, dict[str, object]], date | None]:
    activity: dict[int, dict[str, object]] = {
        player_id: {
            "matches_last_21d": 0,
            "wins_last_21d": 0,
            "matches_last_5d": 0,
            "played_yesterday": False,
            "last_match_date": None,
            "recent_opponents": [],
        }
        for player_id in fixture_player_ids
    }
    cutoff_21d = as_of - timedelta(days=20)
    cutoff_5d = as_of - timedelta(days=4)
    yesterday = as_of - timedelta(days=1)
    max_source_date: date | None = None
    seen: set[tuple[int, int, int | None, int | None, date]] = set()

    for path in game_paths:
        if not path.exists():
            continue
        for row in read_csv(path):
            match_date = parse_date(row.get("date"))
            if match_date is None or match_date > as_of or not is_played_match(row.get("result")):
                continue
            if max_source_date is None or match_date > max_source_date:
                max_source_date = match_date
            winner_id = safe_int(row.get("winner_id"))
            loser_id = safe_int(row.get("loser_id"))
            if not winner_id or not loser_id or winner_id == loser_id:
                continue
            if winner_id not in fixture_player_ids and loser_id not in fixture_player_ids:
                continue
            key = (
                winner_id,
                loser_id,
                safe_int(row.get("tour_id")),
                safe_int(row.get("round_id")),
                match_date,
            )
            if key in seen:
                continue
            seen.add(key)

            for player_id, opponent_id, won in (
                (winner_id, loser_id, True),
                (loser_id, winner_id, False),
            ):
                if player_id not in fixture_player_ids:
                    continue
                rec = activity[player_id]
                last_match = rec["last_match_date"]
                if last_match is None or match_date > last_match:
                    rec["last_match_date"] = match_date
                if match_date < cutoff_21d:
                    continue
                rec["matches_last_21d"] = int(rec["matches_last_21d"]) + 1
                if won:
                    rec["wins_last_21d"] = int(rec["wins_last_21d"]) + 1
                recent_opponents = rec["recent_opponents"]
                assert isinstance(recent_opponents, list)
                recent_opponents.append(opponent_id)
                if match_date >= cutoff_5d:
                    rec["matches_last_5d"] = int(rec["matches_last_5d"]) + 1
                if match_date == yesterday:
                    rec["played_yesterday"] = True

    return activity, max_source_date


def build_rows(
    activity: dict[int, dict[str, object]],
    opponent_elo: dict[int, float],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for player_id in sorted(activity):
        rec = activity[player_id]
        matches = int(rec["matches_last_21d"])
        wins = int(rec["wins_last_21d"])
        opponents = rec["recent_opponents"]
        assert isinstance(opponents, list)
        average_opponent = (
            sum(opponent_elo.get(int(opponent_id), DEFAULT_ELO) for opponent_id in opponents) / len(opponents)
            if opponents
            else DEFAULT_ELO
        )
        last_match = rec["last_match_date"]
        rows.append(
            {
                "player_id": player_id,
                "matches_last_21d": matches,
                "wins_last_21d": wins,
                "win_rate_21d": round(wins / matches, 4) if matches else None,
                "matches_last_5d": int(rec["matches_last_5d"]),
                "played_yesterday": bool(rec["played_yesterday"]),
                "last_match_date": last_match.isoformat() if isinstance(last_match, date) else None,
                "avg_opponent_elo": round(average_opponent, 1),
            }
        )
    return rows


def supabase_headers(key: str, *, write: bool = False) -> dict[str, str]:
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if write:
        headers.update(
            {
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            }
        )
    return headers


def fetch_opponent_elo(base: str, key: str, opponent_ids: set[int]) -> dict[int, float]:
    import requests

    values: dict[int, list[float]] = defaultdict(list)
    overall: dict[int, float] = {}
    ordered = sorted(opponent_ids)
    for offset in range(0, len(ordered), ELO_QUERY_BATCH):
        batch = ordered[offset : offset + ELO_QUERY_BATCH]
        response = requests.get(
            f"{base}/rest/v1/player_elo",
            headers=supabase_headers(key),
            params={
                "select": "player_id,surface,elo",
                "player_id": "in.(" + ",".join(str(player_id) for player_id in batch) + ")",
                "limit": 2000,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        for row in response.json():
            player_id = safe_int(row.get("player_id"))
            try:
                elo = float(row.get("elo"))
            except (TypeError, ValueError):
                continue
            if not player_id:
                continue
            values[player_id].append(elo)
            if (row.get("surface") or "").strip() == "Overall":
                overall[player_id] = elo
    return {
        player_id: overall.get(player_id, sum(player_values) / len(player_values))
        for player_id, player_values in values.items()
        if player_values
    }


def upsert_rows(base: str, key: str, rows: list[dict[str, object]]) -> None:
    import requests

    for offset in range(0, len(rows), UPSERT_BATCH):
        batch = rows[offset : offset + UPSERT_BATCH]
        response = requests.post(
            f"{base}/rest/v1/player_recent_activity?on_conflict=player_id",
            headers=supabase_headers(key, write=True),
            json=batch,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()


def write_status(
    *,
    as_of: date,
    rows: list[dict[str, object]],
    max_source_date: date | None,
    dry_run: bool,
) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of.isoformat(),
        "dry_run": dry_run,
        "fixture_players": len(rows),
        "players_with_21d_matches": sum(1 for row in rows if int(row["matches_last_21d"]) > 0),
        "players_who_played_yesterday": sum(1 for row in rows if row["played_yesterday"]),
        "latest_source_match_date": max_source_date.isoformat() if max_source_date else None,
    }
    STATUS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh fair-odds recent activity for current ATP fixtures")
    parser.add_argument("--as-of", default=date.today().isoformat(), help="Model date in YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Compute locally without Supabase reads/writes")
    parser.add_argument(
        "--max-source-lag-days",
        type=int,
        default=2,
        help="Fail when local OnCourt results are older than this many days",
    )
    args = parser.parse_args()
    as_of = parse_date(args.as_of)
    if as_of is None:
        parser.error("--as-of must be YYYY-MM-DD")

    fixture_player_ids = load_fixture_player_ids(DATA_DIR / "today_atp.csv", DATA_DIR / "tours_atp.csv")
    if not fixture_player_ids:
        print("Recent activity: no supported unplayed ATP/Challenger fixture players; nothing to update.")
        write_status(as_of=as_of, rows=[], max_source_date=None, dry_run=args.dry_run)
        return 0

    print(f"Recent activity: {len(fixture_player_ids):,} current ATP/Challenger fixture players")
    activity, max_source_date = aggregate_activity(
        (DATA_DIR / "games_atp.csv",),
        fixture_player_ids,
        as_of,
    )
    if max_source_date is None:
        raise RuntimeError("No valid played matches found in data/oncourt/games_atp.csv")
    source_lag = (as_of - max_source_date).days
    if source_lag > max(0, args.max_source_lag_days):
        raise RuntimeError(
            f"OnCourt results are stale: latest={max_source_date.isoformat()}, as_of={as_of.isoformat()}, "
            f"lag={source_lag}d"
        )

    opponent_ids = {
        int(opponent_id)
        for rec in activity.values()
        for opponent_id in rec["recent_opponents"]
    }
    opponent_elo: dict[int, float] = {}
    if not args.dry_run and opponent_ids:
        load_env()
        base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not base or not key:
            raise RuntimeError("Missing NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        opponent_elo = fetch_opponent_elo(base, key, opponent_ids)

    rows = build_rows(activity, opponent_elo)
    with_recent = sum(1 for row in rows if int(row["matches_last_21d"]) > 0)
    played_yesterday = sum(1 for row in rows if row["played_yesterday"])
    print(
        f"  latest local result={max_source_date.isoformat()} | with 21d matches={with_recent:,}/{len(rows):,} "
        f"| played yesterday={played_yesterday:,}"
    )

    if args.dry_run:
        print("Dry run: Supabase read/write skipped.")
    else:
        base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not base or not key:
            raise RuntimeError("Missing NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        upsert_rows(base, key, rows)
        print(f"  upserted {len(rows):,} rows to player_recent_activity")

    write_status(as_of=as_of, rows=rows, max_source_date=max_source_date, dry_run=args.dry_run)
    print(f"  status: {STATUS_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: recent activity refresh failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
