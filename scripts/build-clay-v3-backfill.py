#!/usr/bin/env python3
"""Clay ML v3 Phase A backfill: prove data joins only.

No model code is written or run here. The script builds four caches and writes a
PASS/FAIL report for the approved prerequisite data joins.
"""

from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _lib.clay_v3_altitude import altitude_coverage
from _lib.clay_v3_tournament_map import TOURNAMENT_VENUE, canonical_tournament_key, venue_key_for_tournament
from _lib.clay_v3_venues import load_venue_geo_csv, write_venue_geo_csv
from _lib.clay_v3_weather import build_weather_cache
from _lib.clay_v3_xlsx import join_fixture_ranks, write_rank_cache


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "data" / "backtest"
ONCOURT_DIR = ROOT / "data" / "oncourt"
SURFACE_SPEED_CSV = BACKTEST_DIR / "tennisabstract-atp-surface-speed.csv"
SURFACE_SPEED_TMP = BACKTEST_DIR / "tennisabstract-atp-surface-speed.phase-a.tmp.csv"
VENUE_GEO_CSV = ONCOURT_DIR / "clay_venues_geo.csv"
WEATHER_CSV = ONCOURT_DIR / "weather_clay_2022_2024.csv"
RANKS_CSV = BACKTEST_DIR / "clay-v3-xlsx-ranks-2022-2024.csv"
POSTMORTEM = BACKTEST_DIR / "clay-v3-postmortem.md"

SURFACE_SPEED_MIN_FIXTURE_COVERAGE = 0.80
ALTITUDE_MIN_VENUE_COVERAGE = 0.95
WEATHER_MIN_FIXTURE_COVERAGE = 0.90
RANKS_MIN_FIXTURE_COVERAGE = 0.95


class TaskError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Clay ML v3 Phase A backfill caches and report.")
    parser.add_argument("--years", nargs="+", type=int, required=True, help="Backtest years to audit, expected 2022 2023 2024.")
    parser.add_argument("--report-out", type=Path, default=BACKTEST_DIR / "clay-v3-backfill-report.txt")
    parser.add_argument("--skip-scrape", action="store_true", help="Use existing TennisAbstract CSV without calling the scraper.")
    return parser.parse_args()


def pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{n / d:.1%}"


def load_clay_fixtures(years: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year in years:
        path = BACKTEST_DIR / f"backtest-results-{year}.csv"
        with path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if (row.get("surface") or "").strip().lower() != "clay":
                    continue
                rows.append(row)
    rows.sort(key=lambda row: (row["date"], row["tournament"], row["player1_id"], row["player2_id"]))
    return rows


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_surface_speed_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "season_year",
        "surface",
        "tournament_name",
        "tournament_key",
        "cpi",
        "ta_surface_speed",
        "sample_size",
        "source_url",
        "updated_at",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {name: row.get(name, "") for name in fieldnames}
            if out["ta_surface_speed"] == "":
                out["ta_surface_speed"] = out.get("cpi", "")
            if out["cpi"] == "":
                out["cpi"] = out.get("ta_surface_speed", "")
            writer.writerow(out)


def dedupe_surface_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[int, str, str], dict[str, Any]] = {}
    for row in rows:
        try:
            season_year = int(str(row.get("season_year") or "0"))
        except ValueError:
            continue
        surface = str(row.get("surface") or "")
        tournament_key = str(row.get("tournament_key") or "")
        if not season_year or not surface or not tournament_key:
            continue
        row["ta_surface_speed"] = row.get("ta_surface_speed") or row.get("cpi") or ""
        row["cpi"] = row.get("cpi") or row.get("ta_surface_speed") or ""
        key = (season_year, surface, tournament_key)
        prev = best.get(key)
        if prev is None:
            best[key] = row
            continue
        try:
            prev_n = int(prev.get("sample_size") or -1)
        except ValueError:
            prev_n = -1
        try:
            new_n = int(row.get("sample_size") or -1)
        except ValueError:
            new_n = -1
        if new_n >= prev_n:
            best[key] = row
    out = list(best.values())
    out.sort(key=lambda row: (int(row["season_year"]), str(row["surface"]), str(row["tournament_name"])))
    return out


def run_surface_speed_scrape(years: list[int]) -> str | None:
    scrape_years = sorted(set(years + [2025]))
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "scrape-tennisabstract-surface-speed.py"),
        "--years",
        ",".join(str(y) for y in scrape_years),
        "--out-csv",
        str(SURFACE_SPEED_TMP),
        "--no-supabase",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        return (proc.stdout + "\n" + proc.stderr).strip()
    existing = read_csv_rows(SURFACE_SPEED_CSV)
    fetched = read_csv_rows(SURFACE_SPEED_TMP)
    fetched_years = {str(y) for y in scrape_years}
    kept = [row for row in existing if str(row.get("season_year") or "") not in fetched_years]
    merged = dedupe_surface_rows(kept + fetched)
    write_surface_speed_csv(SURFACE_SPEED_CSV, merged)
    try:
        SURFACE_SPEED_TMP.unlink()
    except FileNotFoundError:
        pass
    return None


def surface_speed_coverage(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    rows = read_csv_rows(SURFACE_SPEED_CSV)
    speed_by_year_key: dict[tuple[int, str], dict[str, Any]] = {}
    malformed_2025: list[str] = []
    for row in rows:
        try:
            year = int(str(row.get("season_year") or "0"))
        except ValueError:
            continue
        if str(row.get("surface") or "").lower() != "clay":
            continue
        canonical = canonical_tournament_key(str(row.get("tournament_key") or "")) or canonical_tournament_key(str(row.get("tournament_name") or ""))
        if not canonical:
            continue
        speed = row.get("ta_surface_speed") or row.get("cpi") or ""
        if speed == "":
            continue
        speed_by_year_key[(year, canonical)] = row
        name_norm = " ".join(str(row.get("tournament_name") or "").lower().split())
        if year == 2025 and name_norm in {"nd garros", "garros"}:
            malformed_2025.append(str(row.get("tournament_name") or ""))

    covered = 0
    missing: list[dict[str, Any]] = []
    tournament_counts = Counter()
    tournament_covered = Counter()
    for fixture in fixtures:
        year = int(str(fixture["date"])[:4])
        canonical = canonical_tournament_key(fixture.get("tournament"))
        tournament_counts[str(fixture.get("tournament") or "")] += 1
        if canonical and (year, canonical) in speed_by_year_key:
            covered += 1
            tournament_covered[str(fixture.get("tournament") or "")] += 1
        else:
            missing.append({"date": fixture["date"], "tournament": fixture.get("tournament", ""), "canonical": canonical or ""})
    unique_tournament_covered = sum(1 for t in tournament_counts if tournament_covered[t] > 0)
    return {
        "covered": covered,
        "total": len(fixtures),
        "coverage": covered / len(fixtures) if fixtures else 1.0,
        "missing": missing,
        "unique_tournaments": len(tournament_counts),
        "unique_tournaments_covered": unique_tournament_covered,
        "malformed_2025": malformed_2025,
        "speed_index": speed_by_year_key,
    }


def fixture_venue_keys(fixtures: list[dict[str, Any]]) -> dict[int, str | None]:
    return {idx: venue_key_for_tournament(fixture.get("tournament")) for idx, fixture in enumerate(fixtures)}


def report_no_model_artifacts() -> list[str]:
    forbidden = [
        BACKTEST_DIR / "clay-v3-model.json",
        ROOT / "scripts" / "fit-clay-v3-model.py",
    ]
    forbidden.extend(BACKTEST_DIR.glob("clay-v3-features-*.csv"))
    return [str(path.relative_to(ROOT)) for path in forbidden if path.exists()]


def write_postmortem(report_text: str) -> None:
    POSTMORTEM.write_text(
        "Clay ML v3 Phase A failed. No v3 model fit is authorised.\n\n" + report_text,
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    fixtures = load_clay_fixtures(years)
    if not fixtures:
        raise SystemExit("No clay fixtures found for requested years")

    scrape_error = None
    if not args.skip_scrape:
        scrape_error = run_surface_speed_scrape(years)

    surface = surface_speed_coverage(fixtures)
    fixture_venues = fixture_venue_keys(fixtures)
    required_venues = {v for v in fixture_venues.values() if v}
    write_venue_geo_csv(VENUE_GEO_CSV, required_venues)
    venue_geo = load_venue_geo_csv(VENUE_GEO_CSV)
    altitude = altitude_coverage(required_venues, venue_geo)

    weather_error = None
    try:
        weather = build_weather_cache(fixtures, fixture_venues, venue_geo, WEATHER_CSV)
    except Exception as exc:
        weather_error = str(exc)
        from _lib.clay_v3_weather import WeatherCoverage
        weather = WeatherCoverage([], 0, len(fixtures), {}, [])

    xlsx_paths = [BACKTEST_DIR / f"atp-{year}.xlsx" for year in years]
    ranks = join_fixture_ranks(fixtures, xlsx_paths)
    write_rank_cache(RANKS_CSV, ranks.rows)

    forbidden_model_artifacts = report_no_model_artifacts()
    unresolved_alias = sorted({str(f["tournament"]) for idx, f in enumerate(fixtures) if fixture_venues.get(idx) is None})
    bridge_rows = []
    for canonical, venue_key in sorted(TOURNAMENT_VENUE.items()):
        geo = venue_geo.get(venue_key)
        bridge_rows.append((canonical, venue_key, "" if geo is None else f"{geo.altitude_m:.1f}"))

    task1_pass = scrape_error is None and surface["coverage"] >= SURFACE_SPEED_MIN_FIXTURE_COVERAGE and not surface["malformed_2025"]
    task2_pass = altitude.coverage >= ALTITUDE_MIN_VENUE_COVERAGE
    task3_pass = weather_error is None and weather.coverage >= WEATHER_MIN_FIXTURE_COVERAGE
    task4_pass = ranks.coverage >= RANKS_MIN_FIXTURE_COVERAGE
    overall_pass = task1_pass and task2_pass and task3_pass and task4_pass and not forbidden_model_artifacts

    lines: list[str] = []
    lines.append("Clay ML v3 Phase A backfill report")
    lines.append("====================================")
    lines.append(f"generated_at_utc: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"years: {years}")
    lines.append(f"fixture_denominator: {len(fixtures)}")
    lines.append("scope: backfill only; no model, no signal lane, no monitor")
    lines.append("note_2025: TennisAbstract 2025 may be re-scraped only as scraper hygiene for malformed names; it is not used in v3 backfill/model training.")
    lines.append("")

    lines.append("Task 1 - TennisAbstract surface-speed proxy")
    lines.append(f"status: {'PASS' if task1_pass else 'FAIL'}")
    if scrape_error:
        lines.append(f"scrape_error: {scrape_error[:1000]}")
    lines.append(f"fixture_coverage: {surface['covered']}/{surface['total']} ({pct(surface['covered'], surface['total'])})")
    lines.append(f"fixture_gate: >= {math.ceil(SURFACE_SPEED_MIN_FIXTURE_COVERAGE * len(fixtures))}/{len(fixtures)}")
    lines.append(f"tournament_coverage: {surface['unique_tournaments_covered']}/{surface['unique_tournaments']}")
    if surface["malformed_2025"]:
        lines.append(f"malformed_2025_rows: {surface['malformed_2025']}")
    if surface["missing"]:
        lines.append("surface_speed_gaps_sample:")
        for row in surface["missing"][:20]:
            lines.append(f"- {row['date']} {row['tournament']} canonical={row['canonical']}")
    lines.append("")

    lines.append("Task 2 - Altitude / venue geo")
    lines.append(f"status: {'PASS' if task2_pass else 'FAIL'}")
    lines.append(f"venue_coverage: {altitude.resolved_venues}/{altitude.required_venues} ({pct(altitude.resolved_venues, altitude.required_venues)})")
    lines.append(f"venue_gate: >= {ALTITUDE_MIN_VENUE_COVERAGE:.0%}")
    if unresolved_alias:
        lines.append("unresolved_tournament_aliases:")
        for name in unresolved_alias:
            lines.append(f"- {name}")
    if altitude.unresolved_venues:
        lines.append("unresolved_venues:")
        for venue in altitude.unresolved_venues:
            lines.append(f"- {venue}")
    lines.append("")

    lines.append("tournament_venue_bridge")
    for canonical, venue_key, altitude_m in bridge_rows:
        lines.append(f"- {canonical} -> {venue_key} -> altitude_m={altitude_m}")
    lines.append("")

    lines.append("Task 3 - Weather")
    lines.append(f"status: {'PASS' if task3_pass else 'FAIL'}")
    if weather_error:
        lines.append(f"weather_error: {weather_error[:1000]}")
    lines.append(f"fixture_coverage: {weather.fixture_coverage_count}/{weather.fixture_total} ({pct(weather.fixture_coverage_count, weather.fixture_total)})")
    lines.append(f"fixture_gate: >= {math.ceil(WEATHER_MIN_FIXTURE_COVERAGE * len(fixtures))}/{len(fixtures)}")
    lines.append("granularity_limit: daily venue aggregate; match start times are unavailable, so intra-day weather swings are lost.")
    lines.append(f"humidity_sources: {weather.humidity_sources}")
    lines.append("")

    lines.append("Task 4 - Point-in-time ranks from tennis-data xlsx")
    lines.append(f"status: {'PASS' if task4_pass else 'FAIL'}")
    lines.append(f"fixture_coverage: {ranks.coverage_count}/{ranks.total_count} ({pct(ranks.coverage_count, ranks.total_count)})")
    lines.append(f"fixture_gate: >= {math.ceil(RANKS_MIN_FIXTURE_COVERAGE * len(fixtures))}/{len(fixtures)}")
    lines.append(f"join_methods: {ranks.join_methods}")
    lines.append(f"xlsx_retirement_rows_loaded: {ranks.retirement_count}")
    if ranks.misses:
        lines.append("rank_join_gaps_sample:")
        for row in ranks.misses[:20]:
            lines.append(f"- {row['date']} {row['tournament']} {row['winner_name']} d. {row['loser_name']}")
    lines.append("")

    lines.append("No model artefact check")
    lines.append(f"status: {'PASS' if not forbidden_model_artifacts else 'FAIL'}")
    if forbidden_model_artifacts:
        for path in forbidden_model_artifacts:
            lines.append(f"- forbidden_exists: {path}")
    lines.append("")
    lines.append(f"overall_status: {'PASS' if overall_pass else 'FAIL'}")
    if not overall_pass:
        lines.append("decision: clay ML killed at Phase A unless a fresh plan explicitly reopens the failed gate.")
    else:
        lines.append("decision: Phase A passed; a separate future PR may propose the v3 residual model.")

    report_text = "\n".join(lines) + "\n"
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(report_text, encoding="utf-8")
    print(report_text)
    if not overall_pass:
        write_postmortem(report_text)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
