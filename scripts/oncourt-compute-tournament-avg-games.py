#!/usr/bin/env python3
"""
Build tournament-level pace tables from local OnCourt CSVs.

Outputs / upserts:
  - tournament_game_averages      (tour_id, surface, shift_from_surface, match_count)
  - tournament_serve_profile      (tour_id, surface, venue_avg_spw, match_count)

Method:
  - For each tour edition, look back 3 years across prior editions of the same
    tournament key on the same surface.
  - Venue SPW = total serve points won / total serve points over prior editions.
  - Games shift = tournament avg total games minus surface avg total games over
    the same rolling window.

Usage:
  python scripts/oncourt-compute-tournament-avg-games.py --dry-run --debug-key houston
  python scripts/oncourt-compute-tournament-avg-games.py
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "oncourt"
LOOKBACK_DAYS = 365 * 3
MIN_TOUR_MATCHES_FOR_SHIFT = 30
MIN_VENUE_SPW_MATCHES = 50
POSTGREST_TIMEOUT = 180
BATCH_SIZE = 5000


def _load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

SUPABASE_URL = (
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    or os.environ.get("SUPABASE_URL")
    or ""
).rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    or ""
)


@dataclass
class TourMeta:
    tour_id: int
    date_ord: int
    surface: str
    speed_key: str
    name: str


@dataclass
class TourAgg:
    serve_won: float = 0.0
    serve_total: float = 0.0
    serve_matches: int = 0
    total_games: float = 0.0
    game_matches: int = 0


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _upsert_rows(table: str, rows: list[dict], on_conflict: str) -> None:
    if not rows:
        print(f"  {table}: no rows to upsert")
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    headers = _headers()
    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    sent = 0
    for start in range(0, len(rows), BATCH_SIZE):
        chunk = rows[start : start + BATCH_SIZE]
        resp = requests.post(url, json=chunk, headers=headers, timeout=POSTGREST_TIMEOUT)
        if not resp.ok:
            raise RuntimeError(f"{table} upsert failed ({resp.status_code}): {resp.text[:400]}")
        sent += len(chunk)
    print(f"  {table}: upserted {sent:,} rows")


def _court_to_surface(court_name: str | None) -> str:
    c = (court_name or "").upper()
    if "CLAY" in c or "TERRE" in c:
        return "Clay"
    if "GRASS" in c:
        return "Grass"
    if "INDOOR" in c and "HARD" in c:
        return "I.hard"
    if "HARD" in c or "DECOTURF" in c or "ACRYLIC" in c:
        return "Hard"
    return "N/A"


def _normalize_speed_fragment(text: str | None) -> str:
    raw = (text or "").strip().lower()
    if not raw:
        return ""
    raw = raw.replace("&", " and ")
    raw = raw.replace("’", "'")
    raw = re.sub(r"\bu[\.\s]*s[\.\s]*\b", "us ", raw)
    raw = re.sub(r"\bmens[' ]s\b", "mens", raw)
    raw = re.sub(r"\bwomens[' ]s\b", "womens", raw)
    raw = re.sub(r"\bmen[' ]s\b", "mens", raw)
    raw = re.sub(r"\bwomen[' ]s\b", "womens", raw)
    raw = re.sub(r"\bchampionships\b", "championship", raw)
    raw = re.sub(r"\bqualifiers?\b|\bqualifying\b|\bqualification\b", " ", raw)
    raw = re.sub(r"\b(challenger|atp|wta)\b", " ", raw)
    raw = re.sub(r"\b\d{4}\b", " ", raw)
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    return " ".join(raw.split())


def _tournament_speed_key(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    title = parts[0] if parts else raw
    location = parts[-1] if len(parts) >= 2 else ""
    title_key = _normalize_speed_fragment(title)
    location_key = _normalize_speed_fragment(location)
    if title_key and location_key:
        return f"{title_key} {location_key}"
    return title_key or location_key


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def _parse_total_games(result: str | None) -> int | None:
    text = (result or "").strip()
    if not text:
        return None
    upper = text.upper()
    if any(token in upper for token in ("W/O", "RET", "ABN", "DEF", "BYE", "LIVE", "UNFINISHED")):
        return None
    total = 0
    found = 0
    for left, right in re.findall(r"(\d+)-(\d+)", text):
        a = int(left)
        b = int(right)
        if a > 7 or b > 7:
            continue
        total += a + b
        found += 1
    return total if found else None


def _load_tours() -> dict[int, TourMeta]:
    courts = {}
    with (DATA_DIR / "courts.csv").open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cid = row.get("id")
            if not cid:
                continue
            courts[int(cid)] = (row.get("name") or "").strip()

    out: dict[int, TourMeta] = {}
    with (DATA_DIR / "tours_atp.csv").open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tid = row.get("id")
            if not tid:
                continue
            d = _parse_date(row.get("date"))
            if not d:
                continue
            name = (row.get("name") or "").strip()
            court_id = row.get("court_id")
            surface = _court_to_surface(courts.get(int(court_id), "") if court_id else "")
            if surface == "N/A":
                continue
            out[int(tid)] = TourMeta(
                tour_id=int(tid),
                date_ord=d.toordinal(),
                surface=surface,
                speed_key=_tournament_speed_key(name),
                name=name,
            )
    return out


def _aggregate_tour_stats(tours: dict[int, TourMeta]) -> dict[int, TourAgg]:
    aggs: dict[int, TourAgg] = defaultdict(TourAgg)

    with (DATA_DIR / "stat_atp.csv").open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tid_raw = row.get("tour_id")
            if not tid_raw:
                continue
            tid = int(tid_raw)
            if tid not in tours:
                continue
            serve_won = (
                int(row.get("w_w1s") or 0)
                + int(row.get("w_w2s") or 0)
                + int(row.get("l_w1s") or 0)
                + int(row.get("l_w2s") or 0)
            )
            # OnCourt total service points are carried by *_fsof. The *_w2sof
            # columns are second-serve opportunities, not extra points.
            serve_total = int(row.get("w_fsof") or 0) + int(row.get("l_fsof") or 0)
            if serve_total <= 0:
                continue
            agg = aggs[tid]
            agg.serve_won += float(serve_won)
            agg.serve_total += float(serve_total)
            agg.serve_matches += 1

    with (DATA_DIR / "games_atp.csv").open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tid_raw = row.get("tour_id")
            if not tid_raw:
                continue
            tid = int(tid_raw)
            if tid not in tours:
                continue
            total_games = _parse_total_games(row.get("result"))
            if total_games is None:
                continue
            agg = aggs[tid]
            agg.total_games += float(total_games)
            agg.game_matches += 1

    return aggs


def _build_group_indexes(
    tours: dict[int, TourMeta], aggs: dict[int, TourAgg]
) -> tuple[
    dict[tuple[str, str], list[tuple[int, int, TourAgg]]],
    dict[str, list[tuple[int, int, TourAgg]]],
]:
    by_tournament: dict[tuple[str, str], list[tuple[int, int, TourAgg]]] = defaultdict(list)
    by_surface: dict[str, list[tuple[int, int, TourAgg]]] = defaultdict(list)
    for tid, meta in tours.items():
        agg = aggs.get(tid)
        if not agg:
            continue
        by_tournament[(meta.speed_key, meta.surface)].append((meta.date_ord, tid, agg))
        by_surface[meta.surface].append((meta.date_ord, tid, agg))
    for entries in by_tournament.values():
        entries.sort(key=lambda item: (item[0], item[1]))
    for entries in by_surface.values():
        entries.sort(key=lambda item: (item[0], item[1]))
    return by_tournament, by_surface


def _rolling_aggregate(
    entries: list[tuple[int, int, TourAgg]],
    current_date_ord: int,
    lookback_days: int,
    *,
    value_attr: str,
    matches_attr: str,
) -> tuple[float, int]:
    if not entries:
        return (0.0, 0)
    dates = [item[0] for item in entries]
    hi = bisect_left(dates, current_date_ord)
    lo = bisect_left(dates, current_date_ord - lookback_days, 0, hi)
    if hi <= lo:
        return (0.0, 0)
    value = 0.0
    matches = 0
    for _date_ord, _tid, agg in entries[lo:hi]:
        value += float(getattr(agg, value_attr) or 0.0)
        matches += int(getattr(agg, matches_attr) or 0)
    return (value, matches)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build tournament pace tables from local OnCourt CSVs.")
    parser.add_argument("--dry-run", action="store_true", help="Compute rows locally without upserting to Supabase.")
    parser.add_argument("--lookback-days", type=int, default=LOOKBACK_DAYS)
    parser.add_argument("--debug-key", default="", help="Tournament key or substring to print examples for (e.g. houston).")
    args = parser.parse_args()

    tours = _load_tours()
    aggs = _aggregate_tour_stats(tours)
    by_tournament, by_surface = _build_group_indexes(tours, aggs)

    serve_rows: list[dict] = []
    games_rows: list[dict] = []
    debug_key = (args.debug_key or "").strip().lower()

    for tid, meta in sorted(tours.items(), key=lambda item: item[1].date_ord):
        tournament_entries = by_tournament.get((meta.speed_key, meta.surface), [])
        serve_won, serve_matches = _rolling_aggregate(
            tournament_entries,
            meta.date_ord,
            args.lookback_days,
            value_attr="serve_won",
            matches_attr="serve_matches",
        )
        serve_total, _ = _rolling_aggregate(
            tournament_entries,
            meta.date_ord,
            args.lookback_days,
            value_attr="serve_total",
            matches_attr="serve_matches",
        )
        if serve_matches > 0 and serve_total > 0:
            row = {
                "tour_id": tid,
                "surface": meta.surface,
                "venue_avg_spw": round(serve_won / serve_total, 6),
                "match_count": serve_matches,
            }
            serve_rows.append(row)
            if debug_key and (debug_key in meta.speed_key or debug_key in meta.name.lower()):
                print(
                    f"[serve] {meta.name} {date.fromordinal(meta.date_ord)} "
                    f"matches={serve_matches} venue_avg_spw={row['venue_avg_spw']}"
                )

        tournament_games, tournament_game_matches = _rolling_aggregate(
            tournament_entries,
            meta.date_ord,
            args.lookback_days,
            value_attr="total_games",
            matches_attr="game_matches",
        )
        surface_entries = by_surface.get(meta.surface, [])
        surface_games, surface_game_matches = _rolling_aggregate(
            surface_entries,
            meta.date_ord,
            args.lookback_days,
            value_attr="total_games",
            matches_attr="game_matches",
        )
        if tournament_game_matches > 0 and surface_game_matches > 0:
            avg_tournament = tournament_games / float(tournament_game_matches)
            avg_surface = surface_games / float(surface_game_matches)
            row = {
                "tour_id": tid,
                "surface": meta.surface,
                "shift_from_surface": round(avg_tournament - avg_surface, 6),
                "match_count": tournament_game_matches,
            }
            games_rows.append(row)
            if debug_key and (debug_key in meta.speed_key or debug_key in meta.name.lower()):
                print(
                    f"[games] {meta.name} {date.fromordinal(meta.date_ord)} "
                    f"matches={tournament_game_matches} shift={row['shift_from_surface']} "
                    f"(tour_avg={avg_tournament:.3f} surface_avg={avg_surface:.3f})"
                )

    print(f"Tours loaded: {len(tours):,}")
    print(f"Tournament serve rows: {len(serve_rows):,}")
    print(f"Tournament game rows: {len(games_rows):,}")
    eligible_serve = sum(1 for row in serve_rows if int(row["match_count"]) >= MIN_VENUE_SPW_MATCHES)
    eligible_games = sum(1 for row in games_rows if int(row["match_count"]) >= MIN_TOUR_MATCHES_FOR_SHIFT)
    print(f"Eligible live serve rows (match_count>={MIN_VENUE_SPW_MATCHES}): {eligible_serve:,}")
    print(f"Eligible live game rows (match_count>={MIN_TOUR_MATCHES_FOR_SHIFT}): {eligible_games:,}")

    if args.dry_run:
        print("Dry run: skipped Supabase upserts.")
        return

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing Supabase credentials in .env.local")

    _upsert_rows("tournament_serve_profile", serve_rows, "tour_id,surface")
    _upsert_rows("tournament_game_averages", games_rows, "tour_id,surface")
    print("Done.")


if __name__ == "__main__":
    main()
