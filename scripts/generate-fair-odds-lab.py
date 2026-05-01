#!/usr/bin/env python3
"""Generate the public Fair Odds Lab artifact from goalscorer model output.

This is intentionally a static-file generator:
- no Supabase reads
- no Supabase writes
- no polling
- no network calls

The page should render this JSON only. If no current/future signals qualify,
the artifact still gets written with an empty signals array so the public page
can show a deliberate empty state instead of stale picks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


LONDON = ZoneInfo("Europe/London")

DEFAULT_INPUTS = [
    Path("data/goalscorer/all-leagues-live-board.json"),
    Path("data/goalscorer/goalscorer-live-comparison.csv"),
    Path("data/goalscorer/epl/goalscorer-live-comparison.csv"),
    Path("data/goalscorer/la-liga/goalscorer-live-comparison.csv"),
    Path("data/goalscorer/bundesliga/goalscorer-live-comparison.csv"),
    Path("data/goalscorer/ligue-1/goalscorer-live-comparison.csv"),
    Path("data/goalscorer/serie-a/goalscorer-live-comparison.csv"),
]
DEFAULT_MONITOR_SNAPSHOT = Path("data/goalscorer/goalscorer-monitor-snapshot.json")
DEFAULT_OUTPUT = Path("public/fair-odds-lab/signals.json")
DEFAULT_TEAM_LOGO_MAP = Path("data/goalscorer/team-logo-map.json")
DEFAULT_LINEUP_FIXTURES = [
    Path("data/goalscorer/confirmed-lineups.json"),
    Path("data/goalscorer/epl-confirmed-lineups.json"),
    Path("data/goalscorer/la-liga-confirmed-lineups.json"),
    Path("data/goalscorer/bundesliga-confirmed-lineups.json"),
    Path("data/goalscorer/ligue-1-confirmed-lineups.json"),
]

TEAM_COLOR_PALETTE = [
    ("#1d4ed8", "#b91c1c"),
    ("#7f1d1d", "#38bdf8"),
    ("#0f172a", "#f8fafc"),
    ("#dc2626", "#1e3a8a"),
    ("#111827", "#f8fafc"),
    ("#0e7490", "#34d399"),
    ("#166534", "#facc15"),
    ("#581c87", "#f97316"),
]

TEAM_STYLE_OVERRIDES = {
    "arsenal": ("#b91c1c", "#f8fafc", "sash"),
    "aston villa": ("#7f1d1d", "#38bdf8", "solid"),
    "bournemouth": ("#dc2626", "#111827", "vertical-stripes"),
    "brentford": ("#f8fafc", "#dc2626", "vertical-stripes"),
    "brighton": ("#2563eb", "#f8fafc", "vertical-stripes"),
    "burnley": ("#7f1d1d", "#38bdf8", "solid"),
    "chelsea": ("#1d4ed8", "#f8fafc", "solid"),
    "crystal palace": ("#1d4ed8", "#dc2626", "vertical-stripes"),
    "everton": ("#1d4ed8", "#f8fafc", "solid"),
    "fulham": ("#f8fafc", "#111827", "solid"),
    "leeds": ("#f8fafc", "#facc15", "solid"),
    "liverpool": ("#dc2626", "#f8fafc", "solid"),
    "manchester city": ("#7dd3fc", "#f8fafc", "solid"),
    "manchester united": ("#dc2626", "#111827", "solid"),
    "newcastle united": ("#f8fafc", "#111827", "vertical-stripes"),
    "tottenham": ("#f8fafc", "#1e3a8a", "solid"),
    "west ham": ("#7f1d1d", "#38bdf8", "solid"),
    "wolverhampton wanderers": ("#f59e0b", "#111827", "solid"),
    "bayer leverkusen": ("#111827", "#dc2626", "vertical-stripes"),
    "rasenballsport leipzig": ("#f8fafc", "#dc2626", "sash"),
    "cologne": ("#f8fafc", "#dc2626", "solid"),
    "borussia dortmund": ("#facc15", "#111827", "solid"),
    "union berlin": ("#b91c1c", "#facc15", "solid"),
    "bayern munich": ("#dc2626", "#f8fafc", "solid"),
    "eintracht frankfurt": ("#111827", "#f8fafc", "vertical-stripes"),
    "hoffenheim": ("#1d4ed8", "#f8fafc", "solid"),
    "mainz 05": ("#dc2626", "#f8fafc", "solid"),
    "wolfsburg": ("#16a34a", "#f8fafc", "solid"),
    "pisa": ("#0f172a", "#1d4ed8", "halves"),
    "lecce": ("#facc15", "#dc2626", "vertical-stripes"),
    "napoli": ("#0ea5e9", "#f8fafc", "solid"),
    "como": ("#1d4ed8", "#f8fafc", "solid"),
    "juventus": ("#f8fafc", "#111827", "vertical-stripes"),
    "inter": ("#1d4ed8", "#111827", "vertical-stripes"),
    "milan": ("#dc2626", "#111827", "vertical-stripes"),
    "roma": ("#7f1d1d", "#f59e0b", "solid"),
    "lazio": ("#7dd3fc", "#f8fafc", "solid"),
    "fiorentina": ("#7e22ce", "#f8fafc", "solid"),
    "atalanta": ("#1d4ed8", "#111827", "vertical-stripes"),
    "barcelona": ("#1e3a8a", "#b91c1c", "vertical-stripes"),
    "real madrid": ("#f8fafc", "#facc15", "solid"),
    "atletico madrid": ("#f8fafc", "#dc2626", "vertical-stripes"),
    "sociedad": ("#f8fafc", "#2563eb", "vertical-stripes"),
    "athletic club": ("#f8fafc", "#dc2626", "vertical-stripes"),
    "valencia": ("#f8fafc", "#f97316", "solid"),
    "villarreal": ("#facc15", "#1d4ed8", "solid"),
    "monaco": ("#f8fafc", "#dc2626", "sash"),
    "psg": ("#1e3a8a", "#dc2626", "solid"),
    "marseille": ("#f8fafc", "#0ea5e9", "solid"),
    "lyon": ("#f8fafc", "#dc2626", "sash"),
    "lille": ("#dc2626", "#1e3a8a", "solid"),
    "lens": ("#dc2626", "#facc15", "vertical-stripes"),
}

LEAGUE_SLUGS = {
    "england - premier league": "epl",
    "premier league": "epl",
    "italy - serie a": "serie-a",
    "serie a": "serie-a",
    "spain - la liga": "la-liga",
    "spain - laliga": "la-liga",
    "la liga": "la-liga",
    "laliga": "la-liga",
    "germany - bundesliga": "bundesliga",
    "bundesliga": "bundesliga",
    "france - ligue 1": "ligue-1",
    "ligue 1": "ligue-1",
}

LEAGUE_LABELS = {
    "epl": "Premier League",
    "serie-a": "Serie A",
    "la-liga": "La Liga",
    "bundesliga": "Bundesliga",
    "ligue-1": "Ligue 1",
}

TEAM_NAME_ALIASES = {
    "fc st pauli": "st pauli",
    "ca osasuna": "osasuna",
    "athletic bilbao": "athletic club",
    "aj auxerre": "auxerre",
    "angers sco": "angers",
    "rb leipzig": "rasenballsport leipzig",
    "tsg hoffenheim": "hoffenheim",
    "borussia monchengladbach": "borussia m gladbach",
    "brighton and hove albion": "brighton",
    "brighton hove albion": "brighton",
    "afc bournemouth": "bournemouth",
    "1 fc koln": "fc cologne",
    "1 fc cologne": "fc cologne",
    "fc koln": "fc cologne",
    "1 fc heidenheim": "fc heidenheim",
    "heidenheim": "fc heidenheim",
    "fsv mainz 05": "mainz 05",
    "sc freiburg": "freiburg",
    "vfl wolfsburg": "wolfsburg",
    "leeds united": "leeds",
    "tottenham hotspur": "tottenham",
    "west ham united": "west ham",
    "wolves": "wolverhampton wanderers",
    "wolverhampton": "wolverhampton wanderers",
    "getafe cf": "getafe",
    "levante ud": "levante",
    "as monaco": "monaco",
    "rc lens": "lens",
    "acf fiorentina": "fiorentina",
    "as roma": "roma",
    "como 1907": "como",
    "atalanta bc": "atalanta",
    "hellas verona": "verona",
    "lazio rome": "lazio",
    "parma calcio 1913": "parma",
    "parma calcio": "parma",
    "internazionale": "inter",
    "inter milano": "inter",
    "inter milan": "inter",
    "deportivo alaves": "alaves",
    "real sociedad": "sociedad",
    "real sociedad san sebastian": "sociedad",
    "juventus turin": "juventus",
    "espanyol barcelona": "espanyol",
    "ogc nice": "nice",
    "racing club de lens": "lens",
    "real betis seville": "real betis",
    "stade brest 29": "brest",
}


@dataclass(frozen=True)
class Candidate:
    row: dict[str, str]
    best_odds: float
    model_prob_pct: float
    fair_odds: float
    implied_pct: float
    price_gap_pp: float
    recent_npxg: float | None
    team_xg: float | None
    team_share: float | None
    opponent_xga: float | None
    fixture_swing: float | None
    expected_minutes: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        help="Input CSV or live-board JSON. May be supplied multiple times. Defaults to all goalscorer live-board/comparison files.",
    )
    parser.add_argument("--monitor-snapshot", type=Path, default=DEFAULT_MONITOR_SNAPSHOT)
    parser.add_argument("--team-logo-map", type=Path, default=DEFAULT_TEAM_LOGO_MAP)
    parser.add_argument(
        "--lineups",
        type=Path,
        action="append",
        help="Confirmed/expected lineup JSON files used to enrich signals with FotMob ids and kickoff UTC. Defaults to all goalscorer lineup files.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--edge-threshold-pp", type=float, default=0.0)
    parser.add_argument("--max-signals", type=int, default=36)
    parser.add_argument(
        "--today",
        help="London date override, YYYY-MM-DD. Defaults to today's London date.",
    )
    parser.add_argument(
        "--include-past",
        action="store_true",
        help="For local QA only. Do not use for the public artifact.",
    )
    return parser.parse_args()


def parse_float(value: Any | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if result == result else None
    text = str(value).strip()
    if not text:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    return result if result == result else None


def clean_text(value: Any | None, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value).strip() or fallback


def normalize_logo_key(value: Any | None) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def simplify_club_key(value: str) -> str:
    return re.sub(r"\b(?:ac|afc|as|bc|ca|cf|cfc|fc|rc|rcd|sc|ssc|us)\b", " ", value).replace(
        "calcio",
        " ",
    )


def canonical_team_key(value: Any | None) -> str:
    normalized = normalize_logo_key(value)
    if not normalized:
        return ""
    aliased = TEAM_NAME_ALIASES.get(normalized, normalized)
    simplified = re.sub(r"\s+", " ", simplify_club_key(aliased)).strip()
    return TEAM_NAME_ALIASES.get(simplified, simplified)


def load_logo_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def team_logo_path(logo_manifest: dict[str, Any], league: str, team: str) -> str:
    leagues = logo_manifest.get("leagues")
    if not isinstance(leagues, dict):
        return ""
    league_entry = leagues.get(league)
    if not isinstance(league_entry, dict):
        return ""
    teams = league_entry.get("teams")
    if not isinstance(teams, dict):
        return ""

    direct = teams.get(team)
    if isinstance(direct, dict) and clean_text(direct.get("logo_path")):
        return clean_text(direct.get("logo_path"))

    target = canonical_team_key(team)
    for name, row in teams.items():
        if not isinstance(row, dict):
            continue
        if canonical_team_key(name) == target or canonical_team_key(row.get("team_key")) == target:
            return clean_text(row.get("logo_path"))
    return ""


def league_logo_path(league: str) -> str:
    if league in LEAGUE_LABELS:
        return f"/league-logos/{league}.png"
    return ""


def infer_lineup_league(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("epl-"):
        return "epl"
    if name.startswith("la-liga-"):
        return "la-liga"
    if name.startswith("bundesliga-"):
        return "bundesliga"
    if name.startswith("ligue-1-"):
        return "ligue-1"
    if name.startswith("serie-a-") or name == "confirmed-lineups.json":
        return "serie-a"
    return ""


def lineup_fixture_key(league: str, match_date: str, home_team: Any, away_team: Any) -> tuple[str, str, str, str]:
    return (
        league,
        match_date[:10],
        canonical_team_key(home_team),
        canonical_team_key(away_team),
    )


def load_lineup_fixture_lookup(paths: list[Path]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        fixtures = payload.get("fixtures") if isinstance(payload, dict) else None
        if not isinstance(fixtures, list):
            continue
        league = infer_lineup_league(path)
        for fixture in fixtures:
            if not isinstance(fixture, dict):
                continue
            match_date = clean_text(fixture.get("match_date")) or clean_text(fixture.get("kickoff_utc"))[:10]
            home = clean_text(fixture.get("home_team"))
            away = clean_text(fixture.get("away_team"))
            if not (league and match_date and home and away):
                continue
            lookup[lineup_fixture_key(league, match_date, home, away)] = fixture
    return lookup


def enrich_rows_with_lineups(
    rows: list[dict[str, Any]],
    lineup_lookup: dict[tuple[str, str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    if not lineup_lookup:
        return rows

    enriched: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        competition = clean_text(copied.get("competition"))
        league = league_slug(competition)
        match_date = row_date_key(copied)
        home = clean_text(copied.get("home_team"))
        away = clean_text(copied.get("away_team"))
        fixture = lineup_lookup.get(lineup_fixture_key(league, match_date, home, away))
        if fixture:
            if not clean_text(copied.get("kickoff")):
                copied["kickoff"] = clean_text(fixture.get("kickoff_utc"))
            copied["_fotmob_match_id"] = clean_text(fixture.get("fotmob_match_id"))
            copied["_fotmob_page_url"] = clean_text(fixture.get("fotmob_page_url"))
            copied["_lineup_type"] = clean_text(fixture.get("lineup_type"))
        enriched.append(copied)
    return enriched


def real_jersey_number(row: dict[str, str]) -> str:
    for key in ("jersey_number", "shirt_number", "squad_number"):
        value = clean_text(row.get(key))
        if re.fullmatch(r"\d{1,2}", value):
            return value
    return ""


def london_today_iso(today_override: str | None) -> str:
    if today_override:
        return today_override
    return datetime.now(tz=LONDON).date().isoformat()


def row_date_key(row: dict[str, str]) -> str:
    kickoff = clean_text(row.get("kickoff"))
    return clean_text(row.get("match_date")) or clean_text(row.get("date")) or kickoff[:10]


def display_kickoff(row: dict[str, str]) -> str:
    kickoff = clean_text(row.get("kickoff"))
    if not kickoff:
        return row_date_key(row) or "TBC"

    value = kickoff.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(value).astimezone(LONDON)
    except ValueError:
        return kickoff

    return dt.strftime("%a %d %b %H:%M UK")


def match_label(row: dict[str, str]) -> str:
    home = clean_text(row.get("home_team"))
    away = clean_text(row.get("away_team"))
    if home and away:
        return f"{home} vs {away}"
    return clean_text(row.get("match"), "Unknown match")


def league_slug(competition: str) -> str:
    key = competition.strip().lower()
    if key in LEAGUE_SLUGS:
        return LEAGUE_SLUGS[key]
    return (
        key.replace(" - ", "-")
        .replace(" ", "-")
        .replace("/", "-")
        .replace("--", "-")
        or "other"
    )


def percentile(value: float | None, values: list[float]) -> int | None:
    if value is None or not values:
        return None
    ordered = sorted(v for v in values if v is not None)
    if not ordered:
        return None
    below_or_equal = sum(1 for item in ordered if item <= value)
    return max(1, min(99, round((below_or_equal / len(ordered)) * 100)))


def tier_from_percentile(value: int | None, strong: str, good: str, average: str, low: str) -> str:
    if value is None:
        return "Unknown"
    if value >= 75:
        return strong
    if value >= 55:
        return good
    if value >= 35:
        return average
    return low


def normalize_confidence(value: str | None, lineup_label: str, expected_minutes: float | None) -> str:
    text = clean_text(value).lower()
    if text.startswith("high"):
        base = "High"
    elif text.startswith("low"):
        base = "Low"
    else:
        base = "Medium"

    if "unknown" in lineup_label.lower() or "bench" in lineup_label.lower():
        return "Low" if base == "Medium" else base
    if expected_minutes is not None and expected_minutes < 65:
        return "Medium" if base == "High" else base
    return base


def lineup_label(row: dict[str, str]) -> str:
    state = clean_text(row.get("lineup_state")).lower()
    status = clean_text(row.get("lineup_status")).lower()
    source = clean_text(row.get("lineup_source")).lower()

    if "confirmed" in status or "confirmed" in source:
        if "bench" in state or "sub" in state:
            return "Confirmed bench"
        return "Confirmed starter"
    if "starter" in state or "xi" in status:
        return "Projected starter"
    if "bench" in state or "sub" in state:
        return "Bench risk"
    return "Lineup unknown"


def penalty_label(row: dict[str, str]) -> str:
    role = clean_text(row.get("penalty_role")).lower()
    dependent = clean_text(row.get("penalty_dependent")).lower() in {"1", "true", "yes"}

    if role in {"primary", "taker"}:
        return "Primary"
    if role in {"secondary", "backup"}:
        return "Secondary"
    if dependent:
        return "Set-piece boost"
    return "Not on penalties"


def stable_colors(team: str) -> tuple[str, str]:
    digest = hashlib.sha1(team.encode("utf-8")).hexdigest()
    index = int(digest[:2], 16) % len(TEAM_COLOR_PALETTE)
    return TEAM_COLOR_PALETTE[index]


def team_style(team: str) -> tuple[str, str, str]:
    key = canonical_team_key(team)
    override = TEAM_STYLE_OVERRIDES.get(key)
    if override:
        return override
    primary, secondary = stable_colors(team)
    return primary, secondary, "solid"


def signal_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row_date_key(row),
        clean_text(row.get("home_team")),
        clean_text(row.get("away_team")),
        clean_text(row.get("canonical_player_name") or row.get("player_name")),
        clean_text(row.get("player_team")),
    )


def signal_id(row: dict[str, str]) -> str:
    source = "|".join(signal_key(row))
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:10]
    date_key = row_date_key(row).replace("-", "")
    player = clean_text(row.get("canonical_player_name") or row.get("player_name"), "player")
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in player).strip("-")
    return f"{date_key}-{slug[:32]}-{digest}"


def read_rows_from_input(input_path: Path) -> list[dict[str, Any]]:
    if not input_path.exists():
        return []

    if input_path.suffix.lower() == ".json":
        payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get("rows")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return []

    rows: list[dict[str, Any]] = []
    with input_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows.extend(dict(row) for row in reader)
    return rows


def monitor_live_bets_to_rows(snapshot_path: Path) -> list[dict[str, Any]]:
    if not snapshot_path.exists():
        return []
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return []

    rows: list[dict[str, Any]] = []
    for item in payload.get("live_bets", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        odds = parse_float(item.get("odds"))
        fair = parse_float(item.get("fair"))
        if odds is None or fair is None or odds <= 1.01 or fair <= 1.01:
            continue
        model_prob = 1 / fair
        rows.append(
            {
                "match_date": item.get("match_date"),
                "kickoff": item.get("kickoff"),
                "bookmaker": item.get("bookmaker"),
                "competition": item.get("competition"),
                "home_team": item.get("team"),
                "away_team": item.get("opponent"),
                "match": item.get("match"),
                "player_name": item.get("player"),
                "canonical_player_name": item.get("player"),
                "player_team": item.get("team"),
                "opponent": item.get("opponent"),
                "position": "FW",
                "position_group": "FW",
                "odds_decimal": odds,
                "model_p_atgs": model_prob,
                "model_fair_odds_atgs": fair,
                "team_share": None,
                "team_expected_npxg": None,
                "recent_npxg_per90_8": None,
                "next_opponent_xga": None,
                "fixture_swing_3": 1.0,
                "expected_minutes": 75 if "starter" in clean_text(item.get("lineup_status")).lower() else None,
                "lineup_state": item.get("lineup_status"),
                "lineup_status": item.get("lineup_label"),
                "lineup_source": "monitor_snapshot",
                "penalty_role": "none",
                "signal_confidence": "high" if item.get("status") == "PUBLIC" else "medium",
                "public_action": item.get("action"),
                "shadow_action": item.get("action"),
            }
        )
    return rows


def build_candidates_from_rows(
    all_rows: list[dict[str, Any]],
    today_iso: str,
    include_past: bool,
) -> tuple[list[dict[str, Any]], list[Candidate]]:
    raw_future_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str, str], dict[str, str]] = {}

    for row in all_rows:
        date_key = row_date_key(row)
        if not include_past and date_key and date_key < today_iso:
            continue

        odds = parse_float(row.get("odds_decimal"))
        model_prob = parse_float(row.get("model_p_atgs"))
        if odds is None or odds <= 1.01 or model_prob is None or not 0 < model_prob < 1:
            continue

        raw_future_rows.append(row)
        key = signal_key(row)
        existing = grouped.get(key)
        existing_odds = parse_float(existing.get("odds_decimal")) if existing else None
        if existing is None or existing_odds is None or odds > existing_odds:
            grouped[key] = row

    candidates: list[Candidate] = []
    for row in grouped.values():
        best_odds = parse_float(row.get("odds_decimal"))
        model_prob = parse_float(row.get("model_p_atgs"))
        if best_odds is None or model_prob is None:
            continue

        fair_odds = parse_float(row.get("model_fair_odds_atgs")) or (1 / model_prob)
        model_prob_pct = model_prob * 100
        implied_pct = 100 / best_odds
        price_gap_pp = model_prob_pct - implied_pct

        candidates.append(
            Candidate(
                row=row,
                best_odds=best_odds,
                model_prob_pct=model_prob_pct,
                fair_odds=fair_odds,
                implied_pct=implied_pct,
                price_gap_pp=price_gap_pp,
                recent_npxg=parse_float(row.get("recent_npxg_per90_8")),
                team_xg=parse_float(row.get("team_expected_npxg")),
                team_share=parse_float(row.get("team_share")),
                opponent_xga=parse_float(row.get("next_opponent_xga")),
                fixture_swing=parse_float(row.get("fixture_swing_3")),
                expected_minutes=parse_float(row.get("expected_minutes") or row.get("minutes_estimate")),
            )
        )

    return raw_future_rows, candidates


def read_grouped_candidates(
    input_paths: list[Path],
    monitor_snapshot_path: Path,
    lineup_fixture_paths: list[Path],
    today_iso: str,
    include_past: bool,
) -> tuple[list[dict[str, Any]], list[Candidate], list[str]]:
    source_paths: list[str] = []
    source_rows: list[dict[str, Any]] = []
    for input_path in input_paths:
        rows = read_rows_from_input(input_path)
        if rows:
            source_paths.append(str(input_path).replace("\\", "/"))
            source_rows.extend(rows)

    source_rows = enrich_rows_with_lineups(source_rows, load_lineup_fixture_lookup(lineup_fixture_paths))
    raw_rows, candidates = build_candidates_from_rows(source_rows, today_iso, include_past)
    if raw_rows:
        return raw_rows, candidates, source_paths

    monitor_rows = monitor_live_bets_to_rows(monitor_snapshot_path)
    if monitor_rows:
        source_paths = [str(monitor_snapshot_path).replace("\\", "/")]
        return (*build_candidates_from_rows(monitor_rows, today_iso, include_past), source_paths)

    return raw_rows, candidates, source_paths


def build_reasons(
    candidate: Candidate,
    recent_tier: str,
    opponent_tier: str,
    penalty: str,
    fixture_boost_pct: int,
) -> list[str]:
    row = candidate.row
    player = clean_text(row.get("canonical_player_name") or row.get("player_name"), "Player")
    team = clean_text(row.get("player_team"), "his team")
    reasons = [
        f"Model scores {player} at {candidate.model_prob_pct:.1f}%, market implies {candidate.implied_pct:.1f}%",
    ]

    if candidate.team_share is not None and candidate.team_share > 0:
        reasons.append(f"Takes {candidate.team_share * 100:.0f}% of {team}'s scoring chances")
    if recent_tier in {"Strong", "Very strong"}:
        reasons.append(f"Recent chance quality grades as {recent_tier.lower()}")
    if opponent_tier in {"High", "Very high"}:
        reasons.append("Opponent defensive profile is a positive matchup")
    if fixture_boost_pct >= 10:
        reasons.append(f"Fixture profile adds a {fixture_boost_pct:+d}% goal-threat boost")
    if penalty == "Primary":
        reasons.append("Primary penalty role adds a clear scoring route")

    return reasons[:5]


def is_public_quality_signal(candidate: Candidate) -> bool:
    lineup = lineup_label(candidate.row).lower()
    confidence = normalize_confidence(
        candidate.row.get("signal_confidence"),
        lineup,
        candidate.expected_minutes,
    )

    if "unknown" in lineup or "bench" in lineup:
        return False
    if confidence == "Low":
        return False
    if candidate.expected_minutes is not None and candidate.expected_minutes < 70:
        return False
    return True


def build_signal(
    candidate: Candidate,
    percentiles: dict[str, int | None],
    logo_manifest: dict[str, Any],
) -> dict[str, Any]:
    row = candidate.row
    competition = clean_text(row.get("competition"), "Football")
    league = league_slug(competition)
    team = clean_text(row.get("player_team"), "Unknown team")
    primary, secondary, shirt_pattern = team_style(team)

    recent_tier = tier_from_percentile(
        percentiles["recent"],
        "Strong",
        "Good",
        "Average",
        "Limited",
    )
    team_tier = tier_from_percentile(
        percentiles["team_xg"],
        "Strong",
        "Positive",
        "Average",
        "Quiet",
    )
    opponent_tier = tier_from_percentile(
        percentiles["opponent_xga"],
        "High",
        "Positive",
        "Average",
        "Low",
    )
    lineup = lineup_label(row)
    penalty = penalty_label(row)
    confidence = normalize_confidence(row.get("signal_confidence"), lineup, candidate.expected_minutes)
    fixture_boost_pct = round(((candidate.fixture_swing or 1.0) - 1.0) * 100)
    share_pct = round((candidate.team_share or 0) * 100)

    player_name = clean_text(row.get("canonical_player_name") or row.get("player_name"), "Unknown player")
    position = clean_text(row.get("today_position_group") or row.get("position_group") or row.get("position"), "FW")
    logo_path = team_logo_path(logo_manifest, league, team)

    return {
        "id": signal_id(row),
        "match": {
            "home_team": clean_text(row.get("home_team")),
            "away_team": clean_text(row.get("away_team")),
            "league": league,
            "league_display": LEAGUE_LABELS.get(league, competition),
            "league_logo_path": league_logo_path(league),
            "kickoff_utc": clean_text(row.get("kickoff")),
            "kickoff_display": display_kickoff(row),
            "fotmob_match_id": clean_text(row.get("_fotmob_match_id")),
            "fotmob_page_url": clean_text(row.get("_fotmob_page_url")),
            "lineup_type": clean_text(row.get("_lineup_type")),
            "venue": "",
        },
        "player": {
            "name": player_name,
            "team": team,
            "position": position,
            "jersey_label": real_jersey_number(row),
            "team_logo_path": logo_path,
            "team_primary_color": primary,
            "team_secondary_color": secondary,
            "team_shirt_pattern": shirt_pattern,
        },
        "market": "Anytime goalscorer",
        "model": {
            "scoring_chance_pct": round(candidate.model_prob_pct, 1),
            "fair_odds": round(candidate.fair_odds, 2),
        },
        "market_data": {
            "best_odds": round(candidate.best_odds, 2),
            "best_book": clean_text(row.get("bookmaker"), "Best market"),
            "implied_chance_pct": round(candidate.implied_pct, 1),
        },
        "edge": {
            "price_gap_pp": round(candidate.price_gap_pp, 1),
            "model_advantage": candidate.price_gap_pp > 0,
        },
        "metrics": {
            "recent_chance_quality": {
                "tier": recent_tier,
                "percentile": percentiles["recent"],
            },
            "share_of_team_chances_pct": share_pct,
            "share_of_team_chances_percentile": percentiles["team_share"],
            "team_attacking_outlook": {
                "tier": team_tier,
                "percentile": percentiles["team_xg"],
            },
            "opponent_defensive_weakness": {
                "tier": opponent_tier,
                "percentile": percentiles["opponent_xga"],
            },
            "fixture_boost_pct": fixture_boost_pct,
            "projected_minutes": round(candidate.expected_minutes) if candidate.expected_minutes is not None else None,
            "penalty_role": penalty,
            "lineup_confidence": lineup,
        },
        "confidence_tier": confidence,
        "reasons": build_reasons(candidate, recent_tier, opponent_tier, penalty, fixture_boost_pct),
        "risk_flags": [],
    }


def main() -> None:
    args = parse_args()
    today_iso = london_today_iso(args.today)
    input_paths = args.input or DEFAULT_INPUTS
    lineup_paths = args.lineups or DEFAULT_LINEUP_FIXTURES
    logo_manifest = load_logo_manifest(args.team_logo_map)
    raw_rows, candidates, source_paths = read_grouped_candidates(
        input_paths,
        args.monitor_snapshot,
        lineup_paths,
        today_iso,
        args.include_past,
    )

    values = {
        "recent": [c.recent_npxg for c in candidates if c.recent_npxg is not None],
        "team_xg": [c.team_xg for c in candidates if c.team_xg is not None],
        "team_share": [c.team_share for c in candidates if c.team_share is not None],
        "opponent_xga": [c.opponent_xga for c in candidates if c.opponent_xga is not None],
        "minutes": [c.expected_minutes for c in candidates if c.expected_minutes is not None],
    }

    qualifying = [
        candidate
        for candidate in candidates
        if candidate.price_gap_pp >= args.edge_threshold_pp
        and candidate.best_odds > candidate.fair_odds
        and is_public_quality_signal(candidate)
    ]

    signals = []
    for candidate in qualifying:
        percentiles = {
            "recent": percentile(candidate.recent_npxg, values["recent"]),
            "team_xg": percentile(candidate.team_xg, values["team_xg"]),
            "team_share": percentile(candidate.team_share, values["team_share"]),
            "opponent_xga": percentile(candidate.opponent_xga, values["opponent_xga"]),
            "minutes": percentile(candidate.expected_minutes, values["minutes"]),
        }
        signals.append(build_signal(candidate, percentiles, logo_manifest))

    confidence_rank = {"High": 3, "Medium": 2, "Low": 1}
    signals.sort(
        key=lambda item: (
            -item["edge"]["price_gap_pp"],
            -confidence_rank.get(item["confidence_tier"], 0),
            -item["model"]["scoring_chance_pct"],
            item["match"].get("kickoff_utc") or item["match"].get("kickoff_display") or "",
        )
    )
    if args.max_signals > 0:
        signals = signals[: args.max_signals]

    fixtures_evaluated = len({(row_date_key(row), clean_text(row.get("home_team")), clean_text(row.get("away_team"))) for row in raw_rows})
    leagues_covered = sorted({signal["match"]["league"] for signal in signals})

    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_file": source_paths,
        "edge_threshold_pp": args.edge_threshold_pp,
        "fixtures_evaluated": fixtures_evaluated,
        "signals_qualifying": len(signals),
        "leagues_covered": leagues_covered,
        "featured_signal_id": signals[0]["id"] if signals else None,
        "signals": signals,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("================================================================")
    print("  IL MARGINE - Fair Odds Lab Artifact")
    print("================================================================")
    print(f"Inputs: {', '.join(source_paths) if source_paths else 'none'}")
    print(f"Monitor snapshot: {args.monitor_snapshot}")
    print(f"Output: {args.output}")
    print(f"Today filter: {today_iso} (include_past={args.include_past})")
    print(f"Fixtures evaluated: {fixtures_evaluated}")
    print(f"Signals qualifying: {len(signals)}")
    print(f"Edge threshold: +{args.edge_threshold_pp:.1f}pp")


if __name__ == "__main__":
    main()
