#!/usr/bin/env python3
"""Build the match-level team-shots dataset with an Understat xG overlay.

Understat supplies match xG. Football-Data.co.uk supplies shots, shots on
target, corners, goals and bookmaker 1X2 prices. These sources are distinct;
the output records that provenance explicitly and makes no FBref, StatsBomb or
Opta equivalence claim.

Output:
  data/team-shots/understat/all-understat-matches.csv

Columns:
  date, league, season, home_team, away_team,
  home_shots, away_shots, home_sot, away_sot,
  home_goals, away_goals,
  home_xg, away_xg,
  home_corners, away_corners,
  B365H, B365D, B365A, B365_over25, B365_under25, source
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parent.parent
FOOTBALLDATA_DIR = ROOT / "data" / "team-shots" / "historical"
OUTPUT_DIR = ROOT / "data" / "team-shots" / "understat"
OUTPUT_FILE = OUTPUT_DIR / "all-understat-matches.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}
REQUEST_DELAY = 1.0

LEAGUE_MAP = {
    "epl":        {"understat_slug": "EPL",        "label": "Premier League"},
    "serie-a":    {"understat_slug": "Serie_A",     "label": "Serie A"},
    "la-liga":    {"understat_slug": "La_liga",     "label": "La Liga"},
    "bundesliga": {"understat_slug": "Bundesliga",  "label": "Bundesliga"},
    "ligue-1":    {"understat_slug": "Ligue_1",     "label": "Ligue 1"},
}

DEFAULT_LEAGUES = list(LEAGUE_MAP.keys())
DEFAULT_SEASONS = list(range(2014, 2026))

OUTPUT_COLUMNS = [
    "date", "league", "season",
    "home_team", "away_team",
    "home_shots", "away_shots", "home_sot", "away_sot",
    "home_goals", "away_goals",
    "home_xg", "away_xg",
    "home_corners", "away_corners",
    "B365H", "B365D", "B365A", "B365_over25", "B365_under25",
    "source",
]


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


TEAM_ALIASES: Dict[str, str] = {
    # EPL
    "mancity": "manchestercity",
    "manunited": "manchesterunited",
    "newcastle": "newcastleunited",
    "nottmforest": "nottinghamforest",
    "wolves": "wolverhamptonwanderers",
    "spurs": "tottenham",
    "tottenhamhotspur": "tottenham",
    "westhamunited": "westham",
    "sheffieldutd": "sheffieldunited",
    "brightonhovealbion": "brighton",
    "brightonandhovealbion": "brighton",
    "afcbournemouth": "bournemouth",
    "westbromwichalbion": "westbrom",
    "westbromwich": "westbrom",
    "leicestercity": "leicester",
    "leedsleedsunited": "leedsunited",
    "ipswich": "ipswichtown",
    # Bundesliga
    "dortmund": "borussiadortmund",
    "einfrankfurt": "eintrachtfrankfurt",
    "fckoln": "fccologne",
    "koln": "fccologne",
    "heidenheim": "fcheidenheim",
    "leverkusen": "bayerleverkusen",
    "mainz": "mainz05",
    "mgladbach": "borussiamgladbach",
    "rbleipzig": "rasenballsportleipzig",
    "stuttgart": "vfbstuttgart",
    "augsburg": "fcaugsburg",
    "freiburg": "scfreiburg",
    "wolfsburg": "vflwolfsburg",
    "bochum": "vflbochum",
    "hoffenheim": "1899hoffenheim",
    "union": "unionberlin",
    "paderborn": "scpaderborn07",
    "fortuna": "fortunadusseldorf",
    "hertha": "herthaberlin",
    "herthabsc": "herthaberlin",
    "greuther": "greutherfurth",
    "furth": "greutherfurth",
    "bielefeld": "arminiabilelefeld",
    "darmstadt": "svdarmstadt98",
    "stpauli": "fcstpauli",
    "holstein": "holsteinkiel",
    "holsteinkiel": "holsteinkiel",
    # La Liga
    "athbilbao": "athleticclub",
    "athmadrid": "atleticomadrid",
    "betis": "realbetis",
    "celta": "celtavigo",
    "sociedad": "realsociedad",
    "vallecano": "rayovallecano",
    "laspalmas": "udlaspalmas",
    "alaves": "deportivoalaves",
    "depor": "deportivolacoruna",
    "leganes": "cdleganes",
    "eibar": "sdeibar",
    "huesca": "sdhuesca",
    # Serie A
    "milan": "acmilan",
    "inter": "internazionale",
    "verona": "hellasverona",
    "hellasverona": "hellasverona",
    "spal": "spal2013",
    # Ligue 1
    "parissg": "parissaintgermain",
    "psg": "parissaintgermain",
    "clermont": "clermontfoot",
    "strassbourg": "strasbourg",
    "stetienne": "saintetienne",
    "nimes": "nimesolympique",
}


def _normalise_team(name: str) -> str:
    raw = re.sub(r"[^a-z0-9]", "", name.lower().strip())
    return TEAM_ALIASES.get(raw, raw)


def fetch_understat_xg(league_key: str, season_start: int) -> Dict[str, Dict[str, float]]:
    """Fetch match-level xG from Understat. Returns {match_key: {home_xg, away_xg}}."""
    slug = LEAGUE_MAP[league_key]["understat_slug"]
    url = f"https://understat.com/getLeagueData/{slug}/{season_start}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"    [WARN] Understat {league_key}/{season_start}: {e}")
        return {}

    time.sleep(REQUEST_DELAY)

    try:
        data = r.json()
    except json.JSONDecodeError:
        print(f"    [WARN] Invalid JSON from Understat {league_key}/{season_start}")
        return {}

    dates = data.get("dates", [])
    result: Dict[str, Dict[str, float]] = {}

    for m in dates:
        dt_str = str(m.get("datetime", "")).split(" ")[0]
        home = _normalise_team(m.get("h", {}).get("title", ""))
        away = _normalise_team(m.get("a", {}).get("title", ""))
        if not dt_str or not home or not away:
            continue

        key = f"{dt_str}:{home}:{away}"
        result[key] = {
            "home_xg": round(_safe_float(m.get("xG", {}).get("h")), 3),
            "away_xg": round(_safe_float(m.get("xG", {}).get("a")), 3),
        }

    return result


def load_footballdata_season(
    league_key: str,
    season_start: int,
    *,
    football_data_dir: Path = FOOTBALLDATA_DIR,
) -> List[dict]:
    """Load one Football-Data.co.uk CSV and return rows with standardised columns."""
    end_year = season_start + 1
    filename = f"{league_key}-{season_start}-{end_year}.csv"
    path = football_data_dir / filename

    if not path.exists():
        return []

    rows: List[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            date_raw = (row.get("Date") or "").strip()
            if not date_raw:
                continue

            parsed_date = None
            for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
                try:
                    parsed_date = datetime.strptime(date_raw, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

            if not parsed_date:
                continue

            home = row.get("HomeTeam", "").strip()
            away = row.get("AwayTeam", "").strip()
            if not home or not away:
                continue

            hs = _safe_float(row.get("HS"))
            as_ = _safe_float(row.get("AS"))
            if hs == 0 and as_ == 0:
                continue

            rows.append({
                "date": parsed_date,
                "league": league_key,
                "season": f"{season_start}-{end_year}",
                "home_team": home,
                "away_team": away,
                "home_shots": int(hs),
                "away_shots": int(as_),
                "home_sot": int(_safe_float(row.get("HST"))),
                "away_sot": int(_safe_float(row.get("AST"))),
                "home_goals": int(_safe_float(row.get("FTHG"))),
                "away_goals": int(_safe_float(row.get("FTAG"))),
                "home_corners": int(_safe_float(row.get("HC"))),
                "away_corners": int(_safe_float(row.get("AC"))),
                "B365H": row.get("B365H", ""),
                "B365D": row.get("B365D", ""),
                "B365A": row.get("B365A", ""),
                "B365_over25": row.get("B365>2.5", ""),
                "B365_under25": row.get("B365<2.5", ""),
                "source": "football-data",
                "_norm_home": _normalise_team(home),
                "_norm_away": _normalise_team(away),
            })

    return rows


def merge_xg(
    fd_rows: List[dict],
    xg_lookup: Dict[str, Dict[str, float]],
) -> Tuple[int, int]:
    """Merge Understat xG into Football-Data rows. Returns (matched, total)."""
    matched = 0
    for row in fd_rows:
        key = f"{row['date']}:{row['_norm_home']}:{row['_norm_away']}"
        xg = xg_lookup.get(key)
        if xg:
            row["home_xg"] = xg["home_xg"]
            row["away_xg"] = xg["away_xg"]
            row["source"] = "football-data+understat-xg"
            matched += 1
        else:
            row["home_xg"] = ""
            row["away_xg"] = ""
    return matched, len(fd_rows)


def row_key(row: dict) -> tuple[str, str, str, str]:
    return (
        str(row.get("date") or "").strip(),
        str(row.get("league") or "").strip(),
        _normalise_team(str(row.get("home_team") or "")),
        _normalise_team(str(row.get("away_team") or "")),
    )


def load_existing_rows(path: Path) -> List[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def merge_existing_rows(existing: List[dict], incoming: List[dict]) -> List[dict]:
    """Upsert refreshed fixtures without dropping seasons not in this run."""
    merged = {row_key(row): row for row in existing if all(row_key(row))}
    for row in incoming:
        key = row_key(row)
        if all(key):
            merged[key] = row
    return sorted(merged.values(), key=lambda row: (str(row.get("date") or ""), row_key(row)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Football-Data shots with an Understat xG overlay")
    parser.add_argument("--leagues", nargs="+", default=DEFAULT_LEAGUES,
                        choices=list(LEAGUE_MAP.keys()))
    parser.add_argument("--seasons", nargs="+", type=int, default=DEFAULT_SEASONS)
    parser.add_argument("--skip-xg", action="store_true",
                        help="Skip Understat xG fetch (use only Football-Data.co.uk)")
    parser.add_argument("--football-data-dir", type=Path, default=FOOTBALLDATA_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Replace the output with only this run (unsafe for routine refreshes)",
    )
    parser.add_argument(
        "--allow-shrink",
        action="store_true",
        help="Allow a replacement run to write fewer rows than the existing archive",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    all_rows: List[dict] = []
    total_matched = 0
    total_rows = 0

    for league in args.leagues:
        print(f"\n{'='*50}")
        print(f"  {LEAGUE_MAP[league]['label']} ({league})")
        print(f"{'='*50}")

        for season in args.seasons:
            fd_rows = load_footballdata_season(
                league,
                season,
                football_data_dir=args.football_data_dir,
            )
            if not fd_rows:
                print(f"  {season}-{season+1}: no data")
                continue

            if not args.skip_xg:
                print(f"  {season}-{season+1}: {len(fd_rows)} matches, fetching xG...", end=" ")
                xg_data = fetch_understat_xg(league, season)
                matched, total = merge_xg(fd_rows, xg_data)
                total_matched += matched
                total_rows += total
                print(f"xG matched {matched}/{total} ({matched/total*100:.0f}%)")
            else:
                total_rows += len(fd_rows)
                for r in fd_rows:
                    r["home_xg"] = ""
                    r["away_xg"] = ""
                print(f"  {season}-{season+1}: {len(fd_rows)} matches (no xG)")

            all_rows.extend(fd_rows)

    for r in all_rows:
        r.pop("_norm_home", None)
        r.pop("_norm_away", None)

    existing_rows = load_existing_rows(args.output)
    output_rows = all_rows if args.no_merge else merge_existing_rows(existing_rows, all_rows)
    if existing_rows and len(output_rows) < len(existing_rows) and not args.allow_shrink:
        raise RuntimeError(
            f"Refusing to shrink {args.output} from {len(existing_rows)} to {len(output_rows)} rows; "
            "use --allow-shrink only for an intentional archive replacement"
        )

    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=OUTPUT_COLUMNS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\n{'='*50}")
    print(f"  SUMMARY")
    print(f"{'='*50}")
    print(f"  Refreshed:     {len(all_rows)}")
    print(f"  Preserved:     {max(0, len(output_rows) - len(all_rows))}")
    print(f"  Total matches: {len(output_rows)}")
    print(f"  xG coverage:   {total_matched}/{total_rows} "
          f"({total_matched/total_rows*100:.1f}%)" if total_rows else "  xG coverage: N/A")
    print(f"  Output:         {args.output}")

    xg_rows = [r for r in output_rows if r.get("home_xg") not in ("", None)]
    print(f"  Rows with xG:   {len(xg_rows)}")
    if xg_rows:
        avg_hxg = sum(_safe_float(r["home_xg"]) for r in xg_rows) / len(xg_rows)
        avg_axg = sum(_safe_float(r["away_xg"]) for r in xg_rows) / len(xg_rows)
        print(f"  Avg home xG:    {avg_hxg:.3f}")
        print(f"  Avg away xG:    {avg_axg:.3f}")


if __name__ == "__main__":
    main()
