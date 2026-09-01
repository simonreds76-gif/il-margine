#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from goalscorer_penalty_utils import player_match_score as shared_player_match_score


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "goalscorer" / "goalscorer-monitor-snapshot.json"
SNAPSHOT_TABLE = "goalscorer_live_snapshot"
DEFAULT_SNAPSHOT_KEY = "monitor_state"
LONDON_TZ = ZoneInfo("Europe/London")

LEAGUE_CONFIGS: list[dict[str, str]] = [
    {
        "key": "serie-a",
        "label": "Serie A",
        "comparison_json": "data/goalscorer/live-board.json",
        "comparison_csv": "data/goalscorer/goalscorer-live-comparison.csv",
        "comparison_txt": "data/goalscorer/goalscorer-live-comparison.txt",
        "lineups_json": "data/goalscorer/confirmed-lineups.json",
        "penalty_review_json": "data/goalscorer/penalty-duty-review.json",
        "live_penalty_review_json": "data/goalscorer/penalty-duty-live-review.json",
        "penalty_context_json": "data/goalscorer/penalty-duty-context.json",
        "penalty_takers_json": "data/goalscorer/serie-a-penalty-takers.json",
        "shadow_signals_csv": "data/goalscorer/goalscorer-shadow-signals.csv",
        "public_signals_csv": "data/goalscorer/goalscorer-public-signals.csv",
        "quarantine_signals_csv": "data/goalscorer/fair-odds-lab-serie-a-quarantine.csv",
    },
    {
        "key": "epl",
        "label": "Premier League",
        "comparison_json": "data/goalscorer/epl/live-board.json",
        "comparison_csv": "data/goalscorer/epl/goalscorer-live-comparison.csv",
        "comparison_txt": "data/goalscorer/epl/goalscorer-live-comparison.txt",
        "lineups_json": "data/goalscorer/epl-confirmed-lineups.json",
        "penalty_review_json": "data/goalscorer/epl-penalty-duty-review.json",
        "live_penalty_review_json": "data/goalscorer/epl-penalty-duty-live-review.json",
        "preseason_role_review_json": "data/goalscorer/epl-preseason-penalty-role-review.json",
        "penalty_context_json": "data/goalscorer/epl/penalty-duty-context.json",
        "penalty_takers_json": "data/goalscorer/epl-penalty-takers.json",
        "shadow_signals_csv": "data/goalscorer/epl-shadow-signals.csv",
        "public_signals_csv": "data/goalscorer/epl-public-signals.csv",
        "quarantine_signals_csv": "data/goalscorer/fair-odds-lab-epl-quarantine.csv",
    },
    {
        "key": "la-liga",
        "label": "La Liga",
        "comparison_json": "data/goalscorer/la-liga/live-board.json",
        "comparison_csv": "data/goalscorer/la-liga/goalscorer-live-comparison.csv",
        "comparison_txt": "data/goalscorer/la-liga/goalscorer-live-comparison.txt",
        "lineups_json": "data/goalscorer/la-liga-confirmed-lineups.json",
        "penalty_review_json": "data/goalscorer/la-liga-penalty-duty-review.json",
        "live_penalty_review_json": "data/goalscorer/la-liga-penalty-duty-live-review.json",
        "penalty_context_json": "data/goalscorer/la-liga/penalty-duty-context.json",
        "penalty_takers_json": "data/goalscorer/la-liga-penalty-takers.json",
        "shadow_signals_csv": "data/goalscorer/la-liga-shadow-signals.csv",
        "public_signals_csv": "data/goalscorer/la-liga-public-signals.csv",
        "quarantine_signals_csv": "data/goalscorer/fair-odds-lab-la-liga-quarantine.csv",
    },
    {
        "key": "bundesliga",
        "label": "Bundesliga",
        "comparison_json": "data/goalscorer/bundesliga/live-board.json",
        "comparison_csv": "data/goalscorer/bundesliga/goalscorer-live-comparison.csv",
        "comparison_txt": "data/goalscorer/bundesliga/goalscorer-live-comparison.txt",
        "lineups_json": "data/goalscorer/bundesliga-confirmed-lineups.json",
        "penalty_review_json": "data/goalscorer/bundesliga-penalty-duty-review.json",
        "live_penalty_review_json": "data/goalscorer/bundesliga-penalty-duty-live-review.json",
        "penalty_context_json": "data/goalscorer/bundesliga/penalty-duty-context.json",
        "penalty_takers_json": "data/goalscorer/bundesliga-penalty-takers.json",
        "shadow_signals_csv": "data/goalscorer/bundesliga-shadow-signals.csv",
        "public_signals_csv": "data/goalscorer/bundesliga-public-signals.csv",
        "quarantine_signals_csv": "data/goalscorer/fair-odds-lab-bundesliga-quarantine.csv",
    },
    {
        "key": "ligue-1",
        "label": "Ligue 1",
        "comparison_json": "data/goalscorer/ligue-1/live-board.json",
        "comparison_csv": "data/goalscorer/ligue-1/goalscorer-live-comparison.csv",
        "comparison_txt": "data/goalscorer/ligue-1/goalscorer-live-comparison.txt",
        "lineups_json": "data/goalscorer/ligue-1-confirmed-lineups.json",
        "penalty_review_json": "data/goalscorer/ligue-1-penalty-duty-review.json",
        "live_penalty_review_json": "data/goalscorer/ligue-1-penalty-duty-live-review.json",
        "penalty_context_json": "data/goalscorer/ligue-1/penalty-duty-context.json",
        "penalty_takers_json": "data/goalscorer/ligue-1-penalty-takers.json",
        "shadow_signals_csv": "data/goalscorer/ligue-1-shadow-signals.csv",
        "public_signals_csv": "data/goalscorer/ligue-1-public-signals.csv",
        "quarantine_signals_csv": "data/goalscorer/fair-odds-lab-ligue-1-quarantine.csv",
    },
]

TEAM_ALIASES: dict[str, str] = {
    "ac milan": "milan",
    "milan": "milan",
    "inter": "inter",
    "inter milan": "inter",
    "inter milano": "inter",
    "internazionale": "inter",
    "lazio rome": "lazio",
    "lazio": "lazio",
    "ss lazio": "lazio",
    "as roma": "roma",
    "roma": "roma",
    "como 1907": "como",
    "como": "como",
    "pisa sc": "pisa",
    "pisa": "pisa",
    "cagliari calcio": "cagliari",
    "cagliari": "cagliari",
    "ssc napoli": "napoli",
    "napoli": "napoli",
    "sassuolo calcio": "sassuolo",
    "sassuolo": "sassuolo",
    "bologna fc": "bologna",
    "bologna fc 1909": "bologna",
    "bologna": "bologna",
    "us cremonese": "cremonese",
    "cremonese": "cremonese",
    "acf fiorentina": "fiorentina",
    "fiorentina": "fiorentina",
    "verona": "verona",
    "hellas verona": "verona",
    "genoa": "genoa",
    "genoa cfc": "genoa",
    "udinese": "udinese",
    "udinese calcio": "udinese",
    "juventus turin": "juventus",
    "juventus": "juventus",
    "parma calcio": "parma",
    "torino": "torino",
    "torino fc": "torino",
    "ca osasuna": "osasuna",
    "osasuna": "osasuna",
    "deportivo alaves": "alaves",
    "deportivo alaves": "alaves",
    "alaves": "alaves",
    "alaves": "alaves",
    "burnley": "burnley",
    "burnley fc": "burnley",
    "bournemouth": "bournemouth",
    "afc bournemouth": "bournemouth",
    "chelsea": "chelsea",
    "chelsea fc": "chelsea",
    "everton": "everton",
    "everton fc": "everton",
    "fulham": "fulham",
    "fulham fc": "fulham",
    "liverpool": "liverpool",
    "liverpool fc": "liverpool",
    "leeds united": "leeds",
    "brighton hove albion": "brighton hove albion",
    "brentford fc": "brentford",
    "tsg hoffenheim": "hoffenheim",
    "hoffenheim": "hoffenheim",
    "vfl wolfsburg": "wolfsburg",
    "wolfsburg": "wolfsburg",
    "1 fc koln": "fc cologne",
    "1 fc heidenheim": "fc heidenheim",
    "1 fc cologne": "fc cologne",
    "atalanta bc": "atalanta",
    "us lecce": "lecce",
    "sunderland afc": "sunderland",
    "fc st pauli": "st pauli",
    "sc freiburg": "freiburg",
    "fc augsburg": "augsburg",
    "vfb stuttgart": "stuttgart",
    "toulouse fc": "toulouse",
    "fc lorient": "lorient",
    "ogc nice": "nice",
    "racing club de lens": "lens",
    "angers sco": "angers",
    "aj auxerre": "auxerre",
    "stade brest 29": "brest",
    "real betis": "real betis",
    "real betis seville": "real betis",
    "real betis balompie": "real betis",
    "espanyol": "espanyol",
    "rcd espanyol": "espanyol",
    "espanyol barcelona": "espanyol",
    "real sociedad": "real sociedad",
    "real sociedad san sebastian": "real sociedad",
    "real sociedad de futbol": "real sociedad",
    "elche": "elche",
    "elche cf": "elche",
    "levante": "levante",
    "levante ud": "levante",
    "paris saint germain": "paris saint germain",
    "paris saint-germain": "paris saint germain",
}

FULL_BACK_POSITION_IDS = {32, 38, 62, 68, 71, 72, 78, 79}
CENTRE_BACK_POSITION_IDS = {33, 34, 35, 36, 37}
MIDFIELD_POSITION_IDS = {64, 65, 66, 73, 74, 75, 76, 77, 84, 85, 86}
ATTACKING_MID_WIDE_POSITION_IDS = {82, 83, 87, 88}
POSITION_LABELS: dict[int, str] = {
    11: "GK",
    32: "RB",
    33: "RCB",
    34: "RCB",
    35: "CB",
    36: "LCB",
    37: "LCB",
    38: "LB",
    62: "RM/WB",
    64: "DM",
    65: "DM",
    66: "DM",
    68: "LM/WB",
    71: "RWB",
    72: "RM",
    73: "RCM",
    74: "CM",
    75: "CM",
    76: "CM",
    77: "LCM",
    78: "LM",
    79: "LWB",
    82: "RAM",
    83: "RW/AM",
    84: "AM",
    85: "AM",
    86: "AM",
    87: "LW/AM",
    88: "LAM",
    103: "RF",
    104: "ST",
    105: "ST",
    106: "ST",
    107: "LF",
    115: "ST",
}


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_mtime_iso(relative_path: str) -> str | None:
    path = ROOT / relative_path
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(relative_path: str) -> str | None:
    path = ROOT / relative_path
    if not path.exists():
        return None
    # Use utf-8-sig so that PowerShell-written files with a UTF-8 BOM (\ufeff)
    # are read correctly. Python's json.loads rejects a leading BOM character,
    # so without this, goalscorer-live-status.json silently parses as {} and
    # hot_live_updated_at is always null.
    return path.read_text(encoding="utf-8-sig", errors="replace")


def read_json(relative_path: str) -> Any:
    text = read_text(relative_path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def read_csv_rows(relative_path: str) -> list[dict[str, str]]:
    path = ROOT / relative_path
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{str(key or ""): str(value or "") for key, value in row.items()} for row in reader]


def repair_mojibake(value: str) -> str:
    if not value or not any(marker in value for marker in ("Ã", "Â", "â", "\ufffd")):
        return value
    try:
        repaired = value.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
        if repaired and repaired.count("\ufffd") <= value.count("\ufffd"):
            return repaired
    except Exception:
        pass
    return value


def decode_html_value(value: Any) -> str:
    return repair_mojibake(html.unescape("" if value is None else str(value))).strip()


def norm_text(value: Any) -> str:
    text = decode_html_value(value).lower()
    if any(ord(char) > 127 for char in text):
        text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return re.sub(r"\s+", " ", text)


def team_key(value: Any) -> str:
    cleaned = norm_text(value)
    return TEAM_ALIASES.get(cleaned, cleaned)


def person_key(value: Any) -> str:
    return norm_text(value)


def taker_key(value: Any) -> str:
    normalized = norm_text(value)
    if not normalized:
        return ""
    parts = normalized.split(" ")
    return parts[-1] if parts else normalized


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number == number else None


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "settled", "won"}


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return datetime.fromisoformat(f"{text}T00:00:00+00:00")
        except ValueError:
            return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def iso_date_in_timezone(timezone: ZoneInfo) -> str:
    return datetime.now(timezone).date().isoformat()


def add_days_iso(iso_date: str, days: int) -> str:
    base = datetime.fromisoformat(f"{iso_date}T00:00:00+00:00").date()
    return (base + timedelta(days=days)).isoformat()


def is_date_only(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()))


def iso_date_for_value_in_timezone(value: str | None, timezone: ZoneInfo = LONDON_TZ) -> str | None:
    if not value:
        return None
    if is_date_only(value):
        return value.strip()[:10]
    parsed = parse_iso(value)
    if not parsed:
        return None
    return parsed.astimezone(timezone).date().isoformat()


def kickoff_sort_value(value: str | None) -> float:
    if not value:
        return float("inf")
    parsed = parse_iso(value)
    if parsed:
        return parsed.timestamp()
    if is_date_only(value):
        parsed_date = parse_iso(f"{value}T23:59:59Z")
        return parsed_date.timestamp() if parsed_date else float("inf")
    return float("inf")


def newest_timestamp(values: list[str | None]) -> str | None:
    newest_value: str | None = None
    newest_ms = float("-inf")
    for value in values:
        parsed = parse_iso(value)
        if not parsed:
            continue
        if parsed.timestamp() > newest_ms:
            newest_ms = parsed.timestamp()
            newest_value = value
    return newest_value


def format_date_time(value: str | None) -> str:
    parsed = parse_iso(value)
    if not parsed:
        return value or "missing"
    return parsed.astimezone(LONDON_TZ).strftime("%d/%m/%Y, %H:%M")


def league_short_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if "premier league" in normalized:
        return "PL"
    if "serie a" in normalized:
        return "SA"
    if "la liga" in normalized:
        return "LL"
    if "bundesliga" in normalized:
        return "BL"
    if "ligue 1" in normalized:
        return "L1"
    return (value or "n/a")[:3].upper()


def humanize_token(value: str | None) -> str:
    return " ".join(part.capitalize() for part in str(value or "").split("_") if part)


def format_lineup_label(row: dict[str, str]) -> str:
    canonical = str(row.get("lineup_status", "")).strip().lower()
    if canonical == "confirmed_starter":
        return "Confirmed starter"
    if canonical == "expected_starter":
        return "FotMob Expected XI"
    if canonical == "confirmed_bench":
        return "Confirmed bench"
    if canonical == "expected_bench":
        return "Expected bench"
    if canonical == "not_in_squad":
        return "Out of squad"
    if canonical == "expected_out":
        return "Expected out"
    if row.get("lineup_input") == "confirmed_xi":
        return "Confirmed XI"
    if row.get("lineup_input") == "expected_xi":
        return "FotMob Expected XI"
    return "No XI yet"


def lineup_short_label(row: dict[str, str]) -> str:
    canonical = str(row.get("lineup_status", "")).strip().lower()
    if canonical == "confirmed_starter":
        return "Yes"
    if canonical == "expected_starter":
        return "~"
    if canonical in {"confirmed_bench", "expected_bench"}:
        return "B"
    if canonical in {"not_in_squad", "expected_out"}:
        return "No"
    return "?"


def parse_summary_metrics(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    metrics: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or re.fullmatch(r"=+", line):
            continue
        match = re.match(r"^(.+?)\s{2,}(.+)$", line)
        if match:
            metrics[match.group(1).strip()] = match.group(2).strip()
    return metrics


def league_output_status(summary: dict[str, str], has_output: bool) -> dict[str, str | None]:
    if not has_output:
        return {"status_key": "not_run", "label": "not run yet", "detail": None}
    historical_rows = parse_int(summary.get("Historical Rows")) or 0
    odds_rows = parse_int(summary.get("Odds Rows")) or 0
    matched_rows = parse_int(summary.get("Matched Rows")) or 0
    if historical_rows > 0 and odds_rows == 0 and matched_rows == 0:
        return {
            "status_key": "no_feed",
            "label": "no ATGS feed",
            "detail": "Source feed returned 0 current ATGS rows for this league window.",
        }
    return {"status_key": "live_file", "label": "live file", "detail": None}


def parse_live_board_rows(payload: Any) -> list[dict[str, str]]:
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    return [{str(key): "" if value is None else str(value) for key, value in row.items()} for row in rows if isinstance(row, dict)]


def fixture_status_label(fixture: dict[str, Any] | None) -> str:
    if not fixture:
        return "Lineup Clean"
    if fixture.get("trust_tier") == "T2" and fixture.get("lineup_input") == "expected_xi" and (fixture.get("corruption_score") or 0) <= 0:
        return "Expected XI"
    if fixture.get("trust_tier") == "T2" and fixture.get("lineup_input") == "none":
        return "Awaiting Lineup"
    if fixture.get("trust_tier") == "T3":
        return "Lineup Quarantined"
    if fixture.get("trust_tier") == "T2":
        return "Lineup Degraded"
    return "Lineup Clean"


def fixture_health_summary(fixture: dict[str, Any]) -> str:
    if fixture.get("trust_tier") == "T3":
        return "Structural lineup issue detected. Keep this fixture out of trust-sensitive decisions until the feed is sane again."
    if fixture.get("lineup_input") == "none":
        return "No FotMob lineup payload yet. This fixture stays soft until a real expected or confirmed XI lands."
    if fixture.get("lineup_input") == "expected_xi":
        return "Expected XI only. Useful for monitoring and shadow context, but not confirmed-lineup decisions yet."
    if fixture.get("corruption_flags"):
        return "Lineup health warning present. The fixture is still visible, but treat it as a monitor-first state."
    return "This fixture is visible in the monitor, but not in a fully confirmed clean state yet."


def parse_live_board_fixtures(payload: Any, league_key: str, league_label: str) -> list[dict[str, Any]]:
    fixtures = payload.get("fixtures") if isinstance(payload, dict) else None
    if not isinstance(fixtures, list):
        return []
    output: list[dict[str, Any]] = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        row = {
            "key": f"{league_key}|{fixture.get('match_date', '')}|{team_key(fixture.get('home_team'))}|{team_key(fixture.get('away_team'))}",
            "league_key": league_key,
            "league_label": league_label,
            "match_date": decode_html_value(fixture.get("match_date")),
            "home_team": decode_html_value(fixture.get("home_team")),
            "away_team": decode_html_value(fixture.get("away_team")),
            "competition": decode_html_value(fixture.get("competition")),
            "bookmaker": decode_html_value(fixture.get("bookmaker")),
            "lineup_input": decode_html_value(fixture.get("lineup_input")),
            "trust_tier": decode_html_value(fixture.get("trust_tier")),
            "corruption_score": parse_float(fixture.get("corruption_score")),
            "corruption_flags": [decode_html_value(item) for item in (fixture.get("corruption_flags") or []) if decode_html_value(item)],
        }
        row["status_label"] = fixture_status_label(row)
        row["summary"] = fixture_health_summary(row)
        output.append(row)
    return output


def parse_fixture_health_rows(rows: list[dict[str, str]], league_key: str, league_label: str) -> list[dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{league_key}|{row.get('match_date', '')}|{team_key(row.get('home_team'))}|{team_key(row.get('away_team'))}"
        if not key.replace("|", ""):
            continue
        corruption_flags = [decode_html_value(flag) for flag in re.split(r"[|;,]", row.get("fixture_corruption_flags", "")) if decode_html_value(flag)]
        candidate = {
            "key": key,
            "league_key": league_key,
            "league_label": league_label,
            "match_date": decode_html_value(row.get("match_date")),
            "home_team": decode_html_value(row.get("home_team")),
            "away_team": decode_html_value(row.get("away_team")),
            "competition": decode_html_value(row.get("competition")),
            "bookmaker": decode_html_value(row.get("bookmaker")),
            "lineup_input": decode_html_value(row.get("lineup_input")),
            "trust_tier": decode_html_value(row.get("trust_tier")),
            "corruption_score": parse_float(row.get("fixture_corruption_score")),
            "corruption_flags": corruption_flags,
        }
        existing = fixtures.get(key)
        if not existing:
            fixtures[key] = candidate
            continue
        existing_rank = 3 if existing["trust_tier"] == "T3" else 2 if existing["trust_tier"] == "T2" else 1
        candidate_rank = 3 if candidate["trust_tier"] == "T3" else 2 if candidate["trust_tier"] == "T2" else 1
        if candidate_rank > existing_rank or (candidate_rank == existing_rank and (candidate["corruption_score"] or 0) > (existing["corruption_score"] or 0)):
            fixtures[key] = candidate
    output = list(fixtures.values())
    for row in output:
        row["status_label"] = fixture_status_label(row)
        row["summary"] = fixture_health_summary(row)
    return output


def parse_stored_lineups(text: str | None, league_key: str) -> list[dict[str, Any]]:
    if not text:
        return []
    try:
        payload = json.loads(text)
    except Exception:
        return []
    raw_fixtures = payload if isinstance(payload, list) else payload.get("fixtures", [])
    output: list[dict[str, Any]] = []
    for fixture in raw_fixtures:
        if not isinstance(fixture, dict):
            continue
        home_team = decode_html_value(fixture.get("home_team"))
        away_team = decode_html_value(fixture.get("away_team"))
        home_starters = fixture.get("home_starters") or []
        away_starters = fixture.get("away_starters") or []
        home_players = [
            {
                "name": decode_html_value(entry.get("name")),
                "position": decode_html_value(entry.get("role_group")),
                "position_id": parse_int(entry.get("position_id")),
            }
            for entry in home_starters
            if isinstance(entry, dict) and decode_html_value(entry.get("name"))
        ] or [
            {"name": decode_html_value(name), "position": "", "position_id": None}
            for name in (fixture.get("home_players") or [])
            if decode_html_value(name)
        ]
        away_players = [
            {
                "name": decode_html_value(entry.get("name")),
                "position": decode_html_value(entry.get("role_group")),
                "position_id": parse_int(entry.get("position_id")),
            }
            for entry in away_starters
            if isinstance(entry, dict) and decode_html_value(entry.get("name"))
        ] or [
            {"name": decode_html_value(name), "position": "", "position_id": None}
            for name in (fixture.get("away_players") or [])
            if decode_html_value(name)
        ]
        if home_team and away_team and home_players and away_players:
            output.append(
                {
                    "league_key": league_key,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_key": team_key(home_team),
                    "away_key": team_key(away_team),
                    "home_status": decode_html_value(fixture.get("home_status")),
                    "away_status": decode_html_value(fixture.get("away_status")),
                    "home_players": home_players,
                    "away_players": away_players,
                }
            )
    return output


def effective_monitor_action(row: dict[str, str]) -> str:
    public_action = row.get("public_action", "").strip().lower()
    shadow_action = row.get("shadow_action", "").strip().lower()
    legacy_public_action = row.get("legacy_public_action", "").strip().lower()
    if public_action == "surface":
        return "surface"
    if shadow_action == "shadow_track":
        return "shadow_track"
    if legacy_public_action == "surface_with_caveat":
        return "surface_with_caveat"
    if public_action == "suppress":
        return "suppress"
    return "monitor"


def effective_monitor_action_label(row: dict[str, str]) -> str:
    action = effective_monitor_action(row)
    if action == "surface":
        return "live"
    if action == "shadow_track":
        return "shadow"
    if action == "surface_with_caveat":
        return "caveat"
    if action == "suppress":
        return "suppressed"
    return "monitor"


def row_kickoff_key(row: dict[str, str]) -> str:
    player_key = row.get("player_id", "").strip() or norm_text(row.get("player_name"))
    return "|".join([row.get("match_date", "")[:10], team_key(row.get("home_team")), team_key(row.get("away_team")), player_key])


def build_kickoff_lookup(rows: list[dict[str, str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in rows:
        kickoff = row.get("kickoff", "").strip()
        if kickoff:
            key = row_kickoff_key(row)
            if key.replace("|", "") and key not in lookup:
                lookup[key] = kickoff
    return lookup


def resolve_row_kickoff(row: dict[str, str], kickoff_lookup: dict[str, str]) -> str:
    return row.get("kickoff", "").strip() or kickoff_lookup.get(row_kickoff_key(row)) or row.get("match_date", "").strip()


def filter_active_rows(rows: list[dict[str, str]], start_iso: str, end_iso: str) -> list[dict[str, str]]:
    return [row for row in rows if row.get("match_date", "")[:10] and start_iso <= row.get("match_date", "")[:10] <= end_iso]


def shadow_row_activity_time(row: dict[str, str]) -> float:
    for candidate in (row.get("settled_at"), row.get("compared_at"), row.get("kickoff"), row.get("date")):
        parsed = parse_iso(candidate)
        if parsed:
            return parsed.timestamp()
    return 0.0


def is_settled_shadow_row(row: dict[str, str]) -> bool:
    return row.get("settled", "").strip().lower() in {"1", "true", "yes", "settled"}


def shadow_result_label(row: dict[str, str]) -> str:
    if is_settled_shadow_row(row):
        return (row.get("bet_outcome") or "settled").upper()
    kickoff = parse_iso(row.get("kickoff") or row.get("date"))
    has_settlement_note = bool((row.get("settlement_note") or "").strip())
    if (kickoff and kickoff.timestamp() < datetime.now(UTC).timestamp()) or has_settlement_note:
        return "PENDING"
    return "OPEN"


def compute_shadow_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    settled = [row for row in rows if is_settled_shadow_row(row)]
    pending_rows = [row for row in rows if not is_settled_shadow_row(row) and shadow_result_label(row) == "PENDING"]
    open_rows = [row for row in rows if not is_settled_shadow_row(row) and shadow_result_label(row) == "OPEN"]
    wins = sum(1 for row in settled if row.get("bet_outcome", "").strip().lower() == "won")
    losses = sum(1 for row in settled if row.get("bet_outcome", "").strip().lower() == "lost")
    voids = sum(1 for row in settled if row.get("bet_outcome", "").strip().lower() in {"void", "push"})
    pnl_units = sum(parse_float(row.get("pnl_units")) or 0 for row in settled)
    staked_units = sum(parse_float(row.get("recommended_stake_units")) or 1 for row in settled)
    return {
        "signals": len(rows),
        "settled": len(settled),
        "pending": len(pending_rows),
        "open": len(open_rows),
        "wins": wins,
        "losses": losses,
        "voids": voids,
        "roi": (pnl_units / staked_units * 100) if staked_units > 0 else 0,
        "pnl_units": pnl_units,
    }


def compute_public_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    settled = [row for row in rows if parse_bool(row.get("settled")) and row.get("bet_outcome", "").lower() != "void"]
    wins = sum(1 for row in settled if row.get("bet_outcome", "").lower() == "won")
    losses = sum(1 for row in settled if row.get("bet_outcome", "").lower() == "lost")
    pnl_units = sum(parse_float(row.get("pnl_units")) or 0 for row in settled)
    staked_units = sum(parse_float(row.get("recommended_stake_units")) or 1 for row in settled)
    return {
        "signals": len(rows),
        "settled": len(settled),
        "wins": wins,
        "losses": losses,
        "roi": (pnl_units / staked_units * 100) if staked_units > 0 else 0,
        "pnl_units": pnl_units,
    }


def compute_evidence_summary(rows: list[dict[str, str]], stake_field: str) -> dict[str, Any]:
    settled = [row for row in rows if is_settled_shadow_row(row)]
    wins = sum(1 for row in settled if row.get("bet_outcome", "").strip().lower() == "won")
    losses = sum(1 for row in settled if row.get("bet_outcome", "").strip().lower() == "lost")
    voids = sum(1 for row in settled if row.get("bet_outcome", "").strip().lower() in {"void", "push"})
    pnl_units = sum(parse_float(row.get("pnl_units")) or 0 for row in settled)
    staked_units = sum(max(0.0, parse_float(row.get(stake_field)) or 0.0) for row in settled)
    return {
        "registered": len(rows),
        "settled": len(settled),
        "pending": len(rows) - len(settled),
        "wins": wins,
        "losses": losses,
        "voids": voids,
        "staked_units": staked_units,
        "pnl_units": pnl_units,
        "roi": (pnl_units / staked_units * 100) if staked_units > 0 else None,
    }


def build_settled_row(row: dict[str, str], league_key: str, competition: str | None = None) -> dict[str, Any]:
    ev_value = parse_float(row.get("ev"))
    return {
        "key": f"{row.get('date', '')}|{row.get('player', '')}|{row.get('match', '')}|{league_key}",
        "player": row.get("player") or "Unknown player",
        "team": row.get("team") or "Unknown team",
        "match": row.get("match") or "Unknown match",
        "competition": competition or row.get("competition") or "",
        "league_key": league_key,
        "kickoff": row.get("kickoff", ""),
        "compared_at": row.get("compared_at", ""),
        "settled_at": row.get("settled_at", ""),
        "date": row.get("date", ""),
        "lineup_state": row.get("lineup_state", ""),
        "best_bookmaker_odds": parse_float(row.get("best_bookmaker_odds")),
        "model_fair_odds": parse_float(row.get("model_fair_odds")),
        "ev_pct": ev_value * 100 if ev_value is not None else None,
        "settled": is_settled_shadow_row(row),
        "bet_outcome": row.get("bet_outcome", ""),
        "settlement_note": row.get("settlement_note", ""),
        "pnl_units": parse_float(row.get("pnl_units")),
        "tracking_tier": row.get("tracking_tier", ""),
        "quarantine_reason": row.get("quarantine_reason", ""),
        "evaluation_stake_units": parse_float(row.get("evaluation_stake_units")),
    }


def player_match_score(left: Any, right: Any) -> int:
    return shared_player_match_score(str(left or ""), str(right or ""))


def resolve_lineup_rows(lineup_players: list[dict[str, Any]], team_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    used: set[int] = set()
    output: list[dict[str, Any]] = []
    for lineup_player in lineup_players:
        best_idx = -1
        best_score = 0
        for idx, row in enumerate(team_rows):
            if idx in used:
                continue
            score = player_match_score(lineup_player.get("name"), row.get("player_name"))
            if score > best_score:
                best_idx = idx
                best_score = score
        if best_idx >= 0 and best_score >= 68:
            used.add(best_idx)
            output.append({"lineup": lineup_player, "row": team_rows[best_idx]})
        else:
            output.append({"lineup": lineup_player, "row": None})
    return output


def position_band(position: str | None, position_id: int | None) -> str:
    text = (position or "").split(",")[0].strip().upper()
    if not text:
        return "util"
    if text.startswith("GK"):
        return "gk"
    if position_id in FULL_BACK_POSITION_IDS:
        return "wide"
    if position_id in CENTRE_BACK_POSITION_IDS:
        return "cb"
    if position_id in MIDFIELD_POSITION_IDS or position_id in ATTACKING_MID_WIDE_POSITION_IDS:
        return "mid"
    if text in {"DMC", "MID", "AM"}:
        return "mid"
    if text == "DEF":
        return "cb"
    if text == "FW":
        return "att"
    return "util"


def position_label(position: str | None, position_id: int | None) -> str:
    if position_id in POSITION_LABELS:
        return POSITION_LABELS[position_id]
    text = (position or "").strip().upper()
    return {"DMC": "DM", "MID": "MID", "AM": "AM", "DEF": "DEF", "FW": "FW", "GK": "GK"}.get(text, text or "UTIL")


def penalty_role_label(role: str | None) -> str:
    if not role or role == "none":
        return ""
    return humanize_token(role)


def penalty_component_meta(row: dict[str, str] | None) -> dict[str, str] | None:
    if not row:
        return None
    role = row.get("penalty_role", "").strip().lower()
    penalty_lambda = parse_float(row.get("penalty_lambda")) or 0
    penalty_share = parse_float(row.get("penalty_share")) or 0
    baseline_penalty_share = parse_float(row.get("baseline_penalty_share")) or 0
    baseline_penalty_sample = parse_float(row.get("baseline_penalty_sample")) or 0
    baseline_penalty_source = row.get("baseline_penalty_source", "").strip().lower()
    career_player_penalties = parse_float(row.get("career_player_penalties")) or 0
    career_team_penalties = parse_float(row.get("career_team_penalties")) or 0
    evidence_share = parse_float(row.get("penalty_evidence_share")) or 0
    evidence_sample = parse_float(row.get("penalty_evidence_sample")) or 0
    evidence_source = row.get("penalty_evidence_source", "").strip().lower()
    penalty_prior = parse_float(row.get("penalty_share_prior")) or 0
    penalty_prior_weight = parse_float(row.get("penalty_share_prior_weight")) or 0
    non_pen_lambda = parse_float(row.get("non_pen_lambda")) or 0
    if role == "none" and penalty_lambda <= 0.0001 and baseline_penalty_share <= 0.0001 and penalty_prior <= 0.0001:
        return None
    if penalty_share <= 0.01 and penalty_lambda <= 0.001:
        return None
    if role in {"tertiary", "none"} and penalty_share < 0.08 and penalty_lambda < 0.005:
        return None

    detail_bits = [
        f"pen duty {penalty_role_label(role)}" if role != "none" else "pen component",
        f"share {(penalty_share * 100):.1f}%",
        f"base {(baseline_penalty_share * 100):.1f}%",
    ]
    if penalty_prior > 0:
        detail_bits.append(f"prior {(penalty_prior * 100):.1f}%")
    if penalty_prior_weight > 0:
        detail_bits.append(f"w {penalty_prior_weight:.1f}")
    if baseline_penalty_source and baseline_penalty_source != "none":
        detail_bits.append(f"src {baseline_penalty_source.replace('_', '+')}")
    if baseline_penalty_sample > 0:
        detail_bits.append(f"sample {baseline_penalty_sample:.1f}")
    if career_player_penalties > 0 and career_team_penalties > 0:
        detail_bits.append(f"career {career_player_penalties:.0f}/{career_team_penalties:.0f}")
    if evidence_sample > 0:
        detail_bits.append(f"ev {(evidence_share * 100):.1f}%")
        detail_bits.append(f"evs {evidence_sample:.1f}")
    if evidence_source:
        detail_bits.append(f"evsrc {evidence_source.replace('_', '+')}")
    detail_bits.append(f"lambda_pen {penalty_lambda:.3f}")
    detail_bits.append(f"lambda_open {non_pen_lambda:.3f}")

    compact_bits = [
        f"{penalty_role_label(role)} pen" if role != "none" else "Pen angle",
        f"{(penalty_share * 100):.0f}% share",
        f"lambda {penalty_lambda:.3f}",
    ]
    return {"compact": " | ".join(compact_bits), "detail": " | ".join(detail_bits)}


def build_lineup_signal(lineup: dict[str, Any], row: dict[str, str] | None) -> dict[str, Any]:
    ev_value = parse_float(row.get("ev")) if row else None
    return {
        "key": f"{lineup.get('name', '')}-{lineup.get('position', '')}-{lineup.get('position_id', '')}",
        "name": lineup.get("name", ""),
        "position": position_label(lineup.get("position") or (row or {}).get("position"), lineup.get("position_id")),
        "note": None if row else "No price matched",
        "has_price": bool(row),
        "odds": parse_float(row.get("odds_decimal")) if row else None,
        "fair": parse_float(row.get("model_fair_odds_atgs")) if row else None,
        "ev_pct": ev_value * 100 if ev_value is not None else None,
        "expected_minutes": parse_float(row.get("expected_minutes")) if row else None,
        "action": effective_monitor_action(row or {}),
        "action_label": effective_monitor_action_label(row or {}),
        "penalty_meta": penalty_component_meta(row),
    }


def build_lineup_team_card(team: str, lineup_status: str, lineup_players: list[dict[str, Any]], team_rows: list[dict[str, str]]) -> dict[str, Any]:
    lineup_rows = resolve_lineup_rows(lineup_players, team_rows) if lineup_players else []
    keeper = None
    attackers: list[dict[str, Any]] = []
    midfielders: list[dict[str, Any]] = []
    wide_players: list[dict[str, Any]] = []
    centre_backs: list[dict[str, Any]] = []
    utilities: list[dict[str, Any]] = []
    for item in lineup_rows:
        signal = build_lineup_signal(item["lineup"], item["row"])
        band = position_band(item["lineup"].get("position"), item["lineup"].get("position_id"))
        if band == "gk":
            keeper = signal
        elif band == "att":
            attackers.append(signal)
        elif band == "mid":
            midfielders.append(signal)
        elif band == "wide":
            wide_players.append(signal)
        elif band == "cb":
            centre_backs.append(signal)
        else:
            utilities.append(signal)

    for signal in utilities:
        if len(midfielders) <= len(centre_backs) and len(midfielders) <= len(attackers):
            midfielders.append(signal)
        elif len(wide_players) <= len(centre_backs):
            wide_players.append(signal)
        elif len(attackers) <= len(centre_backs):
            attackers.append(signal)
        else:
            centre_backs.append(signal)

    return {
        "team": team,
        "lineup_status": lineup_status,
        "total_players": len(lineup_rows),
        "matched_players": sum(1 for item in lineup_rows if item["row"]),
        "keeper": keeper,
        "attackers": attackers,
        "midfielders": midfielders,
        "wide_players": wide_players,
        "centre_backs": centre_backs,
        "unplaced": [],
    }


def penalty_review_identity(row: dict[str, Any]) -> str:
    return "|".join([
        str(row.get("date") or "").strip().lower(),
        str(row.get("league") or "").strip().lower(),
        team_key(row.get("team")),
        team_key(row.get("opponent")),
        taker_key(row.get("actual_taker")),
    ])


def priority_rank(priority: str | None) -> int:
    return 3 if priority == "high" else 2 if priority == "medium" else 1


def penalty_review_source_rank(source: str | None) -> int:
    return 2 if source == "settled_logs" else 1 if source == "fotmob_live" else 0


def merge_penalty_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = penalty_review_identity(row)
        if not key.replace("|", ""):
            continue
        existing = merged.get(key)
        if not existing:
            merged[key] = row
            continue
        current_priority = priority_rank(str(row.get("review_priority") or ""))
        existing_priority = priority_rank(str(existing.get("review_priority") or ""))
        current_source_rank = penalty_review_source_rank(str(row.get("review_source") or ""))
        existing_source_rank = penalty_review_source_rank(str(existing.get("review_source") or ""))
        current_wins = current_priority > existing_priority or (current_priority == existing_priority and current_source_rank > existing_source_rank)
        preferred, fallback = (row, existing) if current_wins else (existing, row)
        next_row = {**fallback, **preferred}
        for field in (
            "match", "team", "opponent", "primary_pre_match", "secondary_pre_match", "tertiary_pre_match",
            "primary_lineup_status", "secondary_lineup_status", "tertiary_lineup_status", "active_taker_pre_match",
            "active_slot_pre_match", "team_lineup_status", "inherited_from_pre_match", "transfer_level_pre_match", "editorial_note",
        ):
            if not str(next_row.get(field) or "").strip():
                fallback_value = str(fallback.get(field) or "").strip()
                next_row[field] = fallback.get(field) if fallback_value else row.get(field)
        for field in ("minute", "event_type", "event_result", "context_generated_at", "context_source_path"):
            if not next_row.get(field):
                next_row[field] = existing.get(field) or row.get(field) or ""
        actual_role = str(next_row.get("actual_role_pre_match") or "").strip()
        if not actual_role or actual_role == "none":
            fallback_role = str(fallback.get("actual_role_pre_match") or "").strip()
            row_role = str(row.get("actual_role_pre_match") or "").strip()
            if fallback_role and fallback_role != "none":
                next_row["actual_role_pre_match"] = fallback.get("actual_role_pre_match")
            elif row_role and row_role != "none":
                next_row["actual_role_pre_match"] = row.get("actual_role_pre_match")
        merged[key] = next_row
    return list(merged.values())


def penalty_context_identity(row: dict[str, Any], league_key: str) -> str:
    team = row.get("team") or row.get("home_team") or ""
    opponent = row.get("opponent") or (row.get("away_team") if team_key(team) == team_key(row.get("home_team")) else row.get("home_team")) or ""
    return "|".join([str(row.get("match_date") or "").strip().lower(), league_key, team_key(team), team_key(opponent)])


def penalty_context_freshness(row: dict[str, Any]) -> float:
    compared = parse_iso(row.get("compared_at"))
    if compared:
        return compared.timestamp()
    match_date = parse_iso(row.get("match_date"))
    return match_date.timestamp() if match_date else float("-inf")


def build_penalty_context_maps(rows: list[dict[str, Any]], baselines: dict[str, Any] | None, league_key: str) -> dict[str, Any]:
    fixture_map: dict[str, dict[str, Any]] = {}
    team_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        fixture_map[penalty_context_identity(row, league_key)] = row
        team_lookup_key = f"{league_key}|{team_key(row.get('team'))}".strip().lower()
        existing = team_map.get(team_lookup_key)
        if team_lookup_key.replace("|", "") and (not existing or penalty_context_freshness(row) >= penalty_context_freshness(existing)):
            team_map[team_lookup_key] = row
    baseline_map = {
        f"{league_key}|{team_key(team_name)}".strip().lower(): entry
        for team_name, entry in (baselines or {}).items()
        if f"{league_key}|{team_key(team_name)}".replace("|", "")
    }
    return {"fixture_map": fixture_map, "team_map": team_map, "baseline_map": baseline_map}


def enrich_penalty_review_row_from_context(row: dict[str, Any], league_key: str, maps: dict[str, Any]) -> dict[str, Any]:
    fixture_key = "|".join([str(row.get("date") or "").strip().lower(), str(row.get("league") or league_key).strip().lower(), team_key(row.get("team")), team_key(row.get("opponent"))])
    team_lookup_key = f"{row.get('league') or league_key}|{team_key(row.get('team'))}".strip().lower()
    context = maps["fixture_map"].get(fixture_key) or maps["team_map"].get(team_lookup_key)
    baseline = None if context else maps["baseline_map"].get(team_lookup_key)
    if not context and not baseline:
        return row

    def prefer_context_value(current: Any, fallback: Any) -> str:
        current_value = str(current or "").strip()
        if current_value and current_value.lower() not in {"unknown", "none"}:
            return current_value
        return str(fallback or "").strip()

    actual_taker = taker_key(row.get("actual_taker"))
    primary_name = (context or {}).get("primary") or (baseline or {}).get("primary") or ""
    secondary_name = (context or {}).get("secondary") or (baseline or {}).get("secondary") or ""
    tertiary_name = (context or {}).get("tertiary") or (baseline or {}).get("tertiary") or ""
    actual_role = str(row.get("actual_role_pre_match") or "").strip()
    if not actual_role or actual_role == "none":
        if actual_taker and actual_taker == taker_key(primary_name):
            actual_role = "primary"
        elif actual_taker and actual_taker == taker_key(secondary_name):
            actual_role = "secondary"
        elif actual_taker and actual_taker == taker_key(tertiary_name):
            actual_role = "tertiary"
        elif actual_taker and actual_taker == taker_key((context or {}).get("active_taker_pre_match")) and str((context or {}).get("active_slot_pre_match") or "").strip():
            actual_role = str((context or {}).get("active_slot_pre_match") or "").strip()

    next_row = dict(row)
    next_row["primary_pre_match"] = row.get("primary_pre_match") or primary_name or ""
    next_row["secondary_pre_match"] = row.get("secondary_pre_match") or secondary_name or ""
    next_row["tertiary_pre_match"] = row.get("tertiary_pre_match") or tertiary_name or ""
    next_row["primary_lineup_status"] = prefer_context_value(row.get("primary_lineup_status"), (context or {}).get("primary_lineup_status"))
    next_row["secondary_lineup_status"] = prefer_context_value(row.get("secondary_lineup_status"), (context or {}).get("secondary_lineup_status"))
    next_row["tertiary_lineup_status"] = prefer_context_value(row.get("tertiary_lineup_status"), (context or {}).get("tertiary_lineup_status"))
    next_row["active_taker_pre_match"] = prefer_context_value(row.get("active_taker_pre_match"), (context or {}).get("active_taker_pre_match"))
    next_row["active_slot_pre_match"] = prefer_context_value(row.get("active_slot_pre_match"), (context or {}).get("active_slot_pre_match"))
    next_row["team_lineup_status"] = prefer_context_value(row.get("team_lineup_status"), (context or {}).get("team_lineup_status"))
    next_row["penalty_transfer_pre_match"] = row.get("penalty_transfer_pre_match") or (context or {}).get("penalty_transfer_pre_match") or 0
    next_row["inherited_from_pre_match"] = row.get("inherited_from_pre_match") or (context or {}).get("inherited_from_pre_match") or ""
    next_row["transfer_level_pre_match"] = row.get("transfer_level_pre_match") or (context or {}).get("transfer_level_pre_match") or ""
    next_row["actual_role_pre_match"] = actual_role or ""
    return next_row


def parse_match_minute(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or "").strip())
    return int(match.group(0)) if match else None


def list_match_result_candidate_paths(league_key: str, match_date: str) -> list[Path]:
    league_dir = ROOT / "data" / "goalscorer" / "match-results" / league_key
    return sorted(path for path in league_dir.glob(f"fotmob-{match_date}-*.json") if path.is_file()) if league_dir.exists() else []


def read_match_result_payload(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def find_penalty_match_result(row: dict[str, Any]) -> dict[str, Any] | None:
    league_key, match_date = str(row.get("league") or "").strip(), str(row.get("date") or "").strip()
    team, opponent = team_key(row.get("team")), team_key(row.get("opponent"))
    if not league_key or not match_date or not team or not opponent:
        return None
    for candidate_path in list_match_result_candidate_paths(league_key, match_date):
        payload = read_match_result_payload(candidate_path)
        if not payload:
            continue
        home_key = team_key(payload.get("home_team"))
        away_key = team_key(payload.get("away_team"))
        if (home_key == team and away_key == opponent) or (home_key == opponent and away_key == team):
            return payload
    return None


def find_match_result_player(payload: dict[str, Any] | None, team_name: Any, player_name: Any) -> dict[str, Any] | None:
    if not payload or not player_name:
        return None
    team = team_key(team_name)
    exact = person_key(player_name)
    last_name = taker_key(player_name)
    team_players = [entry for entry in (payload.get("players") or []) if team_key(entry.get("team")) == team]
    for entry in team_players:
        if person_key(entry.get("name")) == exact:
            return entry
    last_name_matches = [entry for entry in team_players if taker_key(entry.get("name")) == last_name]
    return last_name_matches[0] if len(last_name_matches) == 1 else None


def has_team_roster(payload: dict[str, Any] | None, team_name: Any) -> bool:
    team = team_key(team_name)
    return bool(payload and any(team_key(entry.get("team")) == team for entry in (payload.get("players") or [])))


def describe_player_at_penalty(player: dict[str, Any] | None, minute: int | None, team_roster_known: bool) -> str:
    if minute is None:
        return "Unknown"
    if not player:
        return "No, not in squad" if team_roster_known else "Unknown"
    squad_status = str(player.get("squad_status") or "").strip().lower()
    started, subbed_on, subbed_off = bool(player.get("started")), bool(player.get("subbed_on")), bool(player.get("subbed_off"))
    sub_in, sub_out = parse_int(player.get("sub_in_minute")) or 0, parse_int(player.get("sub_out_minute")) or 0
    on_pitch = (started and (not subbed_off or sub_out <= 0 or minute < sub_out)) or (subbed_on and minute >= sub_in and (not subbed_off or sub_out <= 0 or minute < sub_out))
    if on_pitch:
        if started and subbed_off and sub_out > 0:
            return f"Yes, started (off {sub_out}')"
        if started:
            return "Yes, starter"
        if subbed_on and sub_in > 0:
            return f"Yes, on from {sub_in}'"
        return "Yes"
    if subbed_off and sub_out > 0:
        return f"No, off {sub_out}'"
    if subbed_on and sub_in > 0 and minute < sub_in:
        return f"No, on from {sub_in}'"
    if squad_status == "unavailable":
        return "No, unavailable"
    if squad_status == "sub":
        return "No, unused bench"
    return "No" if started else "Unknown"


def enrich_penalty_review_row_with_match_result(row: dict[str, Any]) -> dict[str, Any]:
    minute = parse_match_minute(row.get("minute"))
    if minute is None:
        return row
    payload = find_penalty_match_result(row)
    if not payload:
        return row
    primary_player = find_match_result_player(payload, row.get("team"), row.get("primary_pre_match"))
    active_player = find_match_result_player(payload, row.get("team"), row.get("active_taker_pre_match"))
    actual_taker_player = find_match_result_player(payload, row.get("team"), row.get("actual_taker"))
    roster_known = has_team_roster(payload, row.get("team"))
    active_taker_name = str(row.get("active_taker_pre_match") or "").strip()
    next_row = dict(row)
    next_row["primary_on_pitch_at_penalty"] = row.get("primary_on_pitch_at_penalty") or describe_player_at_penalty(primary_player, minute, roster_known)
    next_row["active_on_pitch_at_penalty"] = row.get("active_on_pitch_at_penalty") or (describe_player_at_penalty(active_player, minute, roster_known) if active_taker_name else "")
    next_row["actual_taker_on_pitch_at_penalty"] = row.get("actual_taker_on_pitch_at_penalty") or describe_player_at_penalty(actual_taker_player, minute, roster_known)
    return next_row


def read_penalty_review_rows(config: dict[str, str]) -> tuple[list[dict[str, Any]], str | None]:
    settled_payload = read_json(config["penalty_review_json"]) or {}
    live_payload = read_json(config["live_penalty_review_json"]) or {}
    settled_rows = [{**row, "league": row.get("league") or config["key"]} for row in (settled_payload.get("rows") or []) if isinstance(row, dict)]
    live_rows = [{**row, "league": row.get("league") or config["key"]} for row in (live_payload.get("rows") or []) if isinstance(row, dict)]
    merged = merge_penalty_review_rows([*settled_rows, *live_rows])
    context_payload = read_json(config["penalty_context_json"]) or {}
    baselines = read_json(config["penalty_takers_json"]) or {}
    hierarchy_by_team = {
        team_key(team_name): {
            "public_team": str(team_name),
            "hierarchy_status": str(entry.get("hierarchy_status") or "unknown").strip().lower(),
        }
        for team_name, entry in (baselines.items() if isinstance(baselines, dict) else [])
        if not str(team_name).startswith("_") and isinstance(entry, dict)
    }
    maps = build_penalty_context_maps([row for row in (context_payload.get("rows") or []) if isinstance(row, dict)], baselines if isinstance(baselines, dict) else {}, config["key"])
    enriched = [enrich_penalty_review_row_with_match_result(enrich_penalty_review_row_from_context(row, config["key"], maps)) for row in merged]
    latest_generated = newest_timestamp([(settled_payload.get("generated_at") if isinstance(settled_payload, dict) else None), (live_payload.get("generated_at") if isinstance(live_payload, dict) else None)])
    rows: list[dict[str, Any]] = []
    for row in enriched:
        rows.append({
            "row_id": penalty_review_identity(row),
            "date": row.get("date"), "league": decode_html_value(row.get("league")), "review_source": decode_html_value(row.get("review_source")),
            "review_priority": decode_html_value(row.get("review_priority")), "review_type": decode_html_value(row.get("review_type")), "match": decode_html_value(row.get("match")),
            "public_team": hierarchy_by_team.get(team_key(row.get("team")), {}).get("public_team", ""),
            "hierarchy_status": hierarchy_by_team.get(team_key(row.get("team")), {}).get("hierarchy_status", "unknown"),
            "team": decode_html_value(row.get("team")), "opponent": decode_html_value(row.get("opponent")), "actual_taker": decode_html_value(row.get("actual_taker")),
            "actual_role_pre_match": decode_html_value(row.get("actual_role_pre_match")), "penalties_attempted": parse_int(row.get("penalties_attempted")),
            "penalties_scored": parse_int(row.get("penalties_scored")), "distinct_takers_in_match": parse_int(row.get("distinct_takers_in_match")),
            "minute": row.get("minute"), "event_type": decode_html_value(row.get("event_type")), "event_result": decode_html_value(row.get("event_result")),
            "primary_pre_match": decode_html_value(row.get("primary_pre_match")), "secondary_pre_match": decode_html_value(row.get("secondary_pre_match")), "tertiary_pre_match": decode_html_value(row.get("tertiary_pre_match")),
            "primary_lineup_status": decode_html_value(row.get("primary_lineup_status")), "secondary_lineup_status": decode_html_value(row.get("secondary_lineup_status")), "tertiary_lineup_status": decode_html_value(row.get("tertiary_lineup_status")),
            "active_taker_pre_match": decode_html_value(row.get("active_taker_pre_match")), "active_slot_pre_match": decode_html_value(row.get("active_slot_pre_match")), "team_lineup_status": decode_html_value(row.get("team_lineup_status")),
            "penalty_transfer_pre_match": parse_int(row.get("penalty_transfer_pre_match")), "inherited_from_pre_match": decode_html_value(row.get("inherited_from_pre_match")), "transfer_level_pre_match": decode_html_value(row.get("transfer_level_pre_match")),
            "editorial_note": decode_html_value(row.get("editorial_note")), "context_generated_at": row.get("context_generated_at"), "context_source_path": decode_html_value(row.get("context_source_path")),
            "actual_taker_match_status": decode_html_value(row.get("actual_taker_match_status")),
            "primary_on_pitch_at_penalty": decode_html_value(row.get("primary_on_pitch_at_penalty")), "secondary_on_pitch_at_penalty": decode_html_value(row.get("secondary_on_pitch_at_penalty")), "tertiary_on_pitch_at_penalty": decode_html_value(row.get("tertiary_on_pitch_at_penalty")),
            "active_on_pitch_at_penalty": decode_html_value(row.get("active_on_pitch_at_penalty")), "actual_taker_on_pitch_at_penalty": decode_html_value(row.get("actual_taker_on_pitch_at_penalty")),
        })
    rows.sort(key=lambda row: (
        0 if row.get("hierarchy_status") in {"conditional", "disputed"} else 1,
        -priority_rank(str(row.get("review_priority") or "")),
        -(parse_iso(str(row.get("date") or "")) or datetime(1970, 1, 1, tzinfo=UTC)).timestamp(),
        f"{row.get('team') or ''}{row.get('actual_taker') or ''}",
    ))
    return rows, latest_generated


def report_value(text: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def report_int(text: str, label: str) -> int | None:
    match = re.search(r"-?[0-9][0-9,]*", report_value(text, label))
    return int(match.group(0).replace(",", "")) if match else None


def report_float(text: str, label: str) -> float | None:
    match = re.search(r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", report_value(text, label))
    return float(match.group(0)) if match else None


def report_percent(text: str, label: str) -> float | None:
    value = report_float(text, label)
    return value if value is not None else None


def report_csv_row(text: str, section: str, row_name: str) -> list[str]:
    section_match = re.search(
        rf"^{re.escape(section)}\s*$([\s\S]*?)(?=^[A-Z][^\n]*\s*$|\Z)",
        text,
        flags=re.MULTILINE,
    )
    if not section_match:
        return []
    for line in section_match.group(1).splitlines():
        columns = [column.strip() for column in line.split(",")]
        if columns and columns[0] == row_name:
            return columns
    return []


def build_research_status() -> dict[str, Any]:
    parity_path = "data/goalscorer/backtest/parity-report.txt"
    walkforward_path = "data/goalscorer/backtest/walkforward-report.txt"
    segment_path = "data/goalscorer/backtest/segment-diagnostics.txt"
    clv_path = "data/goalscorer/fair-odds-lab-clv-weekly.txt"
    parity = read_text(parity_path)
    walkforward = read_text(walkforward_path)
    segments = read_text(segment_path)
    clv = read_text(clv_path)

    pooled_raw = report_csv_row(walkforward, "Pooled metrics", "raw")
    pooled_beta = report_csv_row(walkforward, "Pooled metrics", "beta")
    beta_gate = report_csv_row(walkforward, "Promotion gate", "beta")
    clv_coverage_match = re.search(
        r"^Matched closes/references:\s*(\d+)\s*\(([0-9.]+)%\)",
        clv,
        flags=re.MULTILINE,
    )

    return {
        "status": "RESEARCH_ONLY",
        "model_variant": report_value(walkforward, "Model variant") or "v2_minutes_absolute_share_repair",
        "updated_at": newest_timestamp(
            [file_mtime_iso(parity_path), file_mtime_iso(walkforward_path), file_mtime_iso(segment_path), file_mtime_iso(clv_path)]
        ),
        "parity": {
            "decision": report_value(parity, "Decision") or "NOT_RUN",
            "golden_rows": report_int(parity, "Golden rows") or 0,
            "mean_abs_delta": report_float(parity, "Mean absolute probability delta"),
            "max_abs_delta": report_float(parity, "Maximum absolute probability delta"),
            "gate": report_float(parity, "Gate"),
        },
        "calibration": {
            "candidate": "beta",
            "n": parse_int(pooled_beta[1]) if len(pooled_beta) > 1 else 0,
            "brier": parse_float(pooled_beta[2]) if len(pooled_beta) > 2 else None,
            "log_loss": parse_float(pooled_beta[3]) if len(pooled_beta) > 3 else None,
            "ece": parse_float(pooled_beta[4]) if len(pooled_beta) > 4 else None,
            "predicted": parse_float(pooled_beta[5]) if len(pooled_beta) > 5 else None,
            "actual": parse_float(pooled_beta[6]) if len(pooled_beta) > 6 else None,
            "raw_brier": parse_float(pooled_raw[2]) if len(pooled_raw) > 2 else None,
            "raw_log_loss": parse_float(pooled_raw[3]) if len(pooled_raw) > 3 else None,
            "raw_ece": parse_float(pooled_raw[4]) if len(pooled_raw) > 4 else None,
            "evaluated_folds": parse_int(beta_gate[1]) if len(beta_gate) > 1 else 0,
            "fold_wins": parse_int(beta_gate[2]) if len(beta_gate) > 2 else 0,
            "probability_gate": beta_gate[3] if len(beta_gate) > 3 else "NOT_RUN",
            "market_roi_gate": beta_gate[4] if len(beta_gate) > 4 else "UNAVAILABLE",
            "decision": beta_gate[5] if len(beta_gate) > 5 else "KEEP_RESEARCH",
        },
        "segments": {
            "rows": report_int(segments, "Rows") or 0,
            "position_sub_rows": report_int(segments, "Position=Sub rows") or 0,
            "minutes_gap_pct": report_percent(segments, "30-59 gap vs overall"),
            "minutes_gate": report_value(segments, "30-59 within +/-5pp") or "NOT_RUN",
        },
        "clv": {
            "signals": report_int(clv, "Signals") or 0,
            "captures_loaded": report_int(clv, "Captured price rows loaded") or 0,
            "matched": int(clv_coverage_match.group(1)) if clv_coverage_match else 0,
            "coverage_pct": float(clv_coverage_match.group(2)) if clv_coverage_match else 0.0,
            "true_closes": report_int(clv, "True same-book closes (<= 45m)") or 0,
            "lagged_closes": report_int(clv, "Lagged same-book closes") or 0,
            "pinnacle_references": report_int(clv, "Pinnacle references") or 0,
            "missing": report_int(clv, "Missing") or 0,
        },
    }


def build_snapshot(snapshot_key: str) -> dict[str, Any]:
    today_iso = iso_date_in_timezone(LONDON_TZ)
    yesterday_iso = add_days_iso(today_iso, -1)
    horizon_iso = add_days_iso(today_iso, 3)
    live_status = read_json("data/goalscorer/goalscorer-live-status.json") or {}
    schedule_state = read_json("data/goalscorer/goalscorer-live-schedule-state.json") or {}
    live_log_mtime = file_mtime_iso("data/goalscorer/goalscorer-live.log")

    league_cards: list[dict[str, Any]] = []
    live_bets: list[dict[str, Any]] = []
    fixture_health_rows: list[dict[str, Any]] = []
    fixture_lineups: list[dict[str, Any]] = []
    shadow_recent_rows: list[dict[str, Any]] = []
    shadow_today_rows: list[dict[str, Any]] = []
    shadow_yesterday_rows: list[dict[str, Any]] = []
    shadow_by_league: list[dict[str, Any]] = []
    public_by_league: list[dict[str, Any]] = []
    quarantine_by_league: list[dict[str, Any]] = []
    quarantine_recent_rows: list[dict[str, Any]] = []
    all_quarantine_rows: list[dict[str, str]] = []
    source_feed_gap_leagues: list[dict[str, Any]] = []
    raw_monitor_summary_chunks: list[str] = []
    penalty_watchlist_rows: list[dict[str, Any]] = []
    penalty_generated_values: list[str | None] = []
    preseason_role_review_rows: list[dict[str, Any]] = []
    preseason_role_generated_values: list[str | None] = []
    all_active_rows: list[dict[str, str]] = []
    all_public_signal_rows: list[dict[str, str]] = []
    comparison_mtims: list[str | None] = []

    for config in LEAGUE_CONFIGS:
        comparison_json = read_json(config["comparison_json"]) or {}
        comparison_rows = parse_live_board_rows(comparison_json) or read_csv_rows(config["comparison_csv"])
        active_rows = filter_active_rows(comparison_rows, today_iso, horizon_iso)
        all_active_rows.extend(active_rows)
        comparison_text = read_text(config["comparison_txt"])
        comparison_metrics = parse_summary_metrics(comparison_text)
        comparison_mtime = newest_timestamp([file_mtime_iso(config["comparison_json"]), file_mtime_iso(config["comparison_csv"])])
        comparison_mtims.append(comparison_mtime)

        league_fixture_health = parse_live_board_fixtures(comparison_json, config["key"], config["label"]) or parse_fixture_health_rows(active_rows, config["key"], config["label"])
        league_fixture_health = [row for row in league_fixture_health if row.get("match_date") and today_iso <= row["match_date"] <= horizon_iso]
        fixture_health_rows.extend(league_fixture_health)

        shadow_rows = read_csv_rows(config["shadow_signals_csv"])
        public_rows = read_csv_rows(config["public_signals_csv"])
        quarantine_rows = read_csv_rows(config["quarantine_signals_csv"])
        all_quarantine_rows.extend(quarantine_rows)
        all_public_signal_rows.extend(public_rows)
        kickoff_lookup = build_kickoff_lookup([*shadow_rows, *public_rows])

        league_public_live = [row for row in active_rows if row.get("public_action") == "surface"]
        league_shadow_live = [row for row in active_rows if row.get("shadow_action") == "shadow_track" and row.get("public_action") != "surface"]
        shadow_summary = compute_shadow_summary(shadow_rows)
        public_summary = compute_public_summary(public_rows)
        quarantine_summary = compute_evidence_summary(quarantine_rows, "evaluation_stake_units")
        output_status = league_output_status(comparison_metrics, bool(comparison_json or comparison_rows))

        if output_status["detail"]:
            source_feed_gap_leagues.append({"key": config["key"], "label": config["label"], "detail": output_status["detail"]})

        league_cards.append({
            "key": config["key"],
            "label": config["label"],
            "status_key": output_status["status_key"],
            "status_label": output_status["label"],
            "status_detail": output_status["detail"],
            "updated_at": newest_timestamp([comparison_mtime, file_mtime_iso(config["shadow_signals_csv"]), file_mtime_iso(config["public_signals_csv"])]),
            "live_rows": len(active_rows),
            "public_now": len(league_public_live),
            "shadow_now": len(league_shadow_live),
            "clean_fixtures": sum(1 for row in league_fixture_health if row.get("trust_tier") == "T1"),
            "degraded_fixtures": sum(1 for row in league_fixture_health if row.get("trust_tier") == "T2"),
            "quarantined_fixtures": sum(1 for row in league_fixture_health if row.get("trust_tier") == "T3"),
            "public_record": {"settled": public_summary["settled"], "wins": public_summary["wins"], "losses": public_summary["losses"], "roi": public_summary["roi"], "pnl_units": public_summary["pnl_units"]},
            "shadow_record": {"signals": shadow_summary["signals"], "settled": shadow_summary["settled"], "open": shadow_summary["pending"] + shadow_summary["open"], "wins": shadow_summary["wins"], "losses": shadow_summary["losses"], "voids": shadow_summary["voids"], "roi": shadow_summary["roi"], "pnl_units": shadow_summary["pnl_units"]},
        })
        shadow_by_league.append({"key": config["key"], "label": config["label"], "signals": shadow_summary["signals"], "settled": shadow_summary["settled"], "open": shadow_summary["pending"] + shadow_summary["open"], "wins": shadow_summary["wins"], "losses": shadow_summary["losses"], "voids": shadow_summary["voids"], "roi": shadow_summary["roi"], "pnl_units": shadow_summary["pnl_units"]})
        public_by_league.append({"key": config["key"], "label": config["label"], "settled": public_summary["settled"], "wins": public_summary["wins"], "losses": public_summary["losses"], "roi": public_summary["roi"], "pnl_units": public_summary["pnl_units"]})
        quarantine_by_league.append({"key": config["key"], "label": config["label"], **quarantine_summary})
        raw_monitor_summary_chunks.append(f"=== {config['label']} | {'Updated ' + format_date_time(comparison_mtime) if comparison_mtime else 'Update time unavailable'} ===\n{comparison_text or 'Missing goalscorer live summary.'}")

        for row in shadow_rows:
            settled_row = build_settled_row(row, config["key"], row.get("competition") or config["label"])
            if is_settled_shadow_row(row):
                shadow_recent_rows.append(settled_row)
            target_iso = iso_date_for_value_in_timezone(row.get("settled_at") or row.get("date"))
            if is_settled_shadow_row(row) and target_iso == today_iso:
                shadow_today_rows.append(settled_row)
            if is_settled_shadow_row(row) and target_iso == yesterday_iso:
                shadow_yesterday_rows.append(settled_row)

        for row in quarantine_rows:
            quarantine_recent_rows.append(
                build_settled_row(row, config["key"], row.get("competition") or config["label"])
            )

        for row in [*league_public_live, *league_shadow_live]:
            ev_value = parse_float(row.get("ev"))
            live_bets.append({
                "key": f"{row.get('player_name', '')}-{row.get('match_date', '')}-{row.get('bookmaker', '')}-{effective_monitor_action(row)}",
                "status": "PUBLIC" if row.get("public_action") == "surface" else "SHADOW",
                "action": effective_monitor_action(row),
                "action_label": effective_monitor_action_label(row),
                "league_key": config["key"],
                "league_label": league_short_label(row.get("competition") or row.get("league") or config["label"]),
                "competition": row.get("competition", ""),
                "player": row.get("player_name") or "Unknown player",
                "team": row.get("player_team") or "Unknown team",
                "opponent": row.get("opponent") or "Unknown opponent",
                "match": f"{row.get('player_team') or 'Unknown team'} vs {row.get('opponent') or 'Unknown opponent'}",
                "match_date": row.get("match_date", ""),
                "kickoff": resolve_row_kickoff(row, kickoff_lookup),
                "bookmaker": row.get("bookmaker", ""),
                "lineup_short": lineup_short_label(row),
                "lineup_label": format_lineup_label(row),
                "lineup_status": row.get("lineup_status", ""),
                "odds": parse_float(row.get("odds_decimal")),
                "fair": parse_float(row.get("model_fair_odds_atgs")),
                "edge_pct": ev_value * 100 if ev_value is not None else None,
                "stake_label": row.get("recommended_stake_label") or row.get("recommended_stake_band") or "-",
            })

        stored_lineups = parse_stored_lineups(read_text(config["lineups_json"]), config["key"])
        lineup_map = {f"{config['key']}|{entry['home_key']}|{entry['away_key']}": entry for entry in stored_lineups}
        fixture_groups: dict[str, dict[str, Any]] = {}
        for row in active_rows:
            home_team, away_team = row.get("home_team", ""), row.get("away_team", "")
            if not home_team or not away_team:
                continue
            key = f"{row.get('match_date', '')}|{row.get('bookmaker', '')}|{home_team}|{away_team}"
            group = fixture_groups.setdefault(key, {"key": key, "league_key": config["key"], "league_label": config["label"], "competition": row.get("competition") or config["label"], "match_date": row.get("match_date", ""), "kickoff": resolve_row_kickoff(row, kickoff_lookup), "bookmaker": row.get("bookmaker", ""), "home_team": home_team, "away_team": away_team, "home_rows": [], "away_rows": []})
            if row.get("is_home") == "1":
                group["home_rows"].append(row)
            elif row.get("is_home") == "0":
                group["away_rows"].append(row)
        health_map = {row["key"]: row for row in league_fixture_health}
        for group in sorted(fixture_groups.values(), key=lambda item: (kickoff_sort_value(item["kickoff"]), item["key"])):
            lineup = lineup_map.get(f"{config['key']}|{team_key(group['home_team'])}|{team_key(group['away_team'])}")
            health = health_map.get(f"{config['key']}|{group['match_date']}|{team_key(group['home_team'])}|{team_key(group['away_team'])}")
            home_players = (lineup or {}).get("home_players") or []
            away_players = (lineup or {}).get("away_players") or []
            fixture_lineups.append({
                "key": group["key"], "league_key": config["key"], "league_label": config["label"], "competition": group["competition"], "match_date": group["match_date"], "kickoff": group["kickoff"], "bookmaker": group["bookmaker"], "home_team": group["home_team"], "away_team": group["away_team"], "matched_player_prices": len(group["home_rows"]) + len(group["away_rows"]), "health": health, "home": build_lineup_team_card(group["home_team"], (lineup or {}).get("home_status", ""), home_players, group["home_rows"]), "away": build_lineup_team_card(group["away_team"], (lineup or {}).get("away_status", ""), away_players, group["away_rows"]), "has_any_lineup": bool(home_players or away_players),
            })

        rows, latest_generated = read_penalty_review_rows(config)
        penalty_watchlist_rows.extend(rows)
        penalty_generated_values.append(latest_generated)
        preseason_path = config.get("preseason_role_review_json")
        if preseason_path:
            preseason_payload = read_json(preseason_path) or {}
            preseason_role_review_rows.extend(
                row for row in (preseason_payload.get("rows") or []) if isinstance(row, dict)
            )
            preseason_role_generated_values.append(preseason_payload.get("generated_at"))

    live_bets.sort(key=lambda row: (kickoff_sort_value(str(row.get("kickoff") or "")), 0 if row.get("status") == "PUBLIC" else 1, -((row.get("edge_pct") or 0) if isinstance(row.get("edge_pct"), (int, float)) else 0)))
    shadow_recent_rows.sort(key=lambda row: shadow_row_activity_time({"settled_at": row.get("settled_at", ""), "compared_at": row.get("compared_at", ""), "kickoff": row.get("kickoff", ""), "date": row.get("date", "")}), reverse=True)
    quarantine_recent_rows.sort(key=lambda row: shadow_row_activity_time({"settled_at": row.get("settled_at", ""), "compared_at": row.get("compared_at", ""), "kickoff": row.get("kickoff", ""), "date": row.get("date", "")}), reverse=True)
    quarantine_summary = compute_evidence_summary(all_quarantine_rows, "evaluation_stake_units")
    clean_count = sum(1 for row in fixture_health_rows if row.get("trust_tier") == "T1")
    degraded_count = sum(1 for row in fixture_health_rows if row.get("trust_tier") == "T2")
    quarantined_count = sum(1 for row in fixture_health_rows if row.get("trust_tier") == "T3")
    hidden_pending_count = sum(1 for row in fixture_health_rows if row.get("trust_tier") == "T2" and row.get("lineup_input") == "none")
    hidden_expected_count = sum(1 for row in fixture_health_rows if row.get("trust_tier") == "T2" and row.get("lineup_input") == "expected_xi" and (row.get("corruption_score") or 0) <= 0)
    flagged_rows = sorted([row for row in fixture_health_rows if row.get("trust_tier") == "T3" or (row.get("trust_tier") == "T2" and row.get("lineup_input") not in {"none"} and not (row.get("lineup_input") == "expected_xi" and (row.get("corruption_score") or 0) <= 0) and ((row.get("corruption_score") or 0) > 0 or row.get("corruption_flags")))], key=lambda row: (-(2 if row.get("trust_tier") == "T3" else 1), f"{row.get('match_date', '')}|{row.get('home_team', '')}|{row.get('away_team', '')}"))
    ev_values = [parse_float(row.get("ev")) for row in all_active_rows if parse_float(row.get("ev")) is not None]
    avg_ev_pct = (sum(ev_values) / len(ev_values) * 100) if ev_values else None

    payload = {
        "schema_version": 3,
        "generated_at": utc_now_iso(),
        "source_status": {
            "compared_at": newest_timestamp([*(row.get("compared_at") for row in all_active_rows), newest_timestamp(comparison_mtims)]),
            "hot_live_updated_at": newest_timestamp([live_status.get("last_successful_finished_at"), live_status.get("updated_at")]),
            "expected_refresh_updated_at": newest_timestamp(comparison_mtims),
            "settlement_updated_at": newest_timestamp([*(row.get("settled_at") for row in shadow_recent_rows if row.get("settled")), *penalty_generated_values]),
            "scheduler_heartbeat_at": newest_timestamp([live_status.get("last_successful_finished_at"), live_status.get("updated_at"), schedule_state.get("updated_at"), live_log_mtime]),
            "snapshot_generated_at": utc_now_iso(),
            "live_status_state": live_status.get("state"),
            "live_status_message": live_status.get("message"),
        },
        "league_cards": league_cards,
        "live_bets": live_bets,
        "fixture_health": {"rows": fixture_health_rows, "clean_count": clean_count, "degraded_count": degraded_count, "quarantined_count": quarantined_count, "hidden_pending_count": hidden_pending_count, "hidden_expected_count": hidden_expected_count, "flagged_rows": flagged_rows},
        "fixture_lineups": fixture_lineups,
        "penalty_watchlist": {"generated_at": newest_timestamp(penalty_generated_values), "row_count": len(penalty_watchlist_rows), "rows": penalty_watchlist_rows},
        "preseason_role_review": {"generated_at": newest_timestamp(preseason_role_generated_values), "row_count": len(preseason_role_review_rows), "rows": preseason_role_review_rows},
        "shadow_summary": {"by_league": shadow_by_league, "recent_rows": shadow_recent_rows[:50], "settled_today": shadow_today_rows, "settled_yesterday": shadow_yesterday_rows},
        "public_summary": {"by_league": public_by_league},
        "extreme_gap_quarantine": {
            **quarantine_summary,
            "by_league": quarantine_by_league,
            "recent_rows": quarantine_recent_rows[:50],
        },
        "diagnostics": {"matched_rows": len(all_active_rows), "suppressed_rows": sum(1 for row in all_active_rows if effective_monitor_action(row) == "suppress"), "fixtures_with_confirmed_lineups": sum(parse_int(parse_summary_metrics(read_text(config["comparison_txt"])).get("Fixtures With Confirmed Lineups")) or 0 for config in LEAGUE_CONFIGS), "fixtures_with_expected_xis": sum(parse_int(parse_summary_metrics(read_text(config["comparison_txt"])).get("Fixtures With Expected Lineups")) or 0 for config in LEAGUE_CONFIGS), "history_mapped_rows": sum(1 for row in all_active_rows if row.get("resolver_source") == "history"), "roster_mapped_rows": sum(1 for row in all_active_rows if row.get("resolver_source") == "live_roster"), "fallback_rows": sum(parse_int(parse_summary_metrics(read_text(config["comparison_txt"])).get("Fallback Rows")) or 0 for config in LEAGUE_CONFIGS), "low_confidence_rows": sum(1 for row in all_active_rows if row.get("signal_confidence") == "low"), "missing_player_history_rows": sum(parse_int(parse_summary_metrics(read_text(config["comparison_txt"])).get("Missing Player History")) or 0 for config in LEAGUE_CONFIGS), "starter_rows": sum(1 for row in all_active_rows if row.get("lineup_status", "").lower() == "confirmed_starter"), "expected_starter_rows": sum(1 for row in all_active_rows if row.get("lineup_status", "").lower() == "expected_starter"), "avg_ev_pct": avg_ev_pct, "source_feed_gap_leagues": source_feed_gap_leagues, "raw_monitor_summary": "\n\n".join(raw_monitor_summary_chunks)},
        "research_status": build_research_status(),
        "snapshot_key": snapshot_key,
    }
    payload["payload_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return payload


def read_existing_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def upload_snapshot(snapshot_key: str, payload: dict[str, Any]) -> None:
    import requests
    load_env()
    base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not base or not key:
        raise SystemExit("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to upload the monitor snapshot.")
    row = {"snapshot_key": snapshot_key, "updated_at": payload["generated_at"], "payload": payload}
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"}
    url = f"{base}/rest/v1/{SNAPSHOT_TABLE}?on_conflict=snapshot_key"
    attempts = max(1, int(os.environ.get("SUPABASE_SNAPSHOT_UPLOAD_ATTEMPTS", "3") or "3"))
    read_timeout = max(10, int(os.environ.get("SUPABASE_SNAPSHOT_UPLOAD_TIMEOUT", "45") or "45"))
    required = (os.environ.get("SUPABASE_SNAPSHOT_UPLOAD_REQUIRED", "0") or "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, headers=headers, json=[row], timeout=(10, read_timeout))
        except requests.exceptions.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if response.ok:
                return
            if 400 <= response.status_code < 500 and response.status_code != 429:
                raise SystemExit(f"Supabase upload failed: {response.status_code} {response.text[:400]}")
            last_error = f"{response.status_code} {response.text[:400]}"

        if attempt < attempts:
            sleep_seconds = min(2 ** attempt, 10)
            print(f"Supabase upload attempt {attempt}/{attempts} failed: {last_error}; retrying in {sleep_seconds}s")
            time.sleep(sleep_seconds)

    message = f"Supabase upload failed after {attempts} attempt(s): {last_error}"
    if required:
        raise SystemExit(message)
    print(f"WARNING: {message}; continuing because SUPABASE_SNAPSHOT_UPLOAD_REQUIRED is not enabled")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the hosted goalscorer monitor snapshot")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Local snapshot JSON path")
    parser.add_argument("--snapshot-key", default=DEFAULT_SNAPSHOT_KEY, help="Supabase snapshot_key value")
    parser.add_argument("--supabase", action="store_true", help="Upload snapshot payload to Supabase")
    args = parser.parse_args()
    output_path = Path(args.output)
    previous_payload = read_existing_snapshot(output_path)
    payload = build_snapshot(args.snapshot_key)
    write_snapshot(output_path, payload)
    unchanged = bool(previous_payload) and previous_payload.get("payload_hash") == payload.get("payload_hash")
    print(f"Generated {output_path} at {payload['generated_at']} with {len(payload['live_bets'])} live rows.")
    if args.supabase:
        if unchanged:
            print(f"Skipped Supabase upload for snapshot '{args.snapshot_key}' (unchanged payload)")
        else:
            upload_snapshot(args.snapshot_key, payload)
            print(f"Uploaded snapshot '{args.snapshot_key}' to {SNAPSHOT_TABLE}")


if __name__ == "__main__":
    main()

