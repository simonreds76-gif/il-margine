#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


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
        "penalty_context_json": "data/goalscorer/epl/penalty-duty-context.json",
        "penalty_takers_json": "data/goalscorer/epl-penalty-takers.json",
        "shadow_signals_csv": "data/goalscorer/epl-shadow-signals.csv",
        "public_signals_csv": "data/goalscorer/epl-public-signals.csv",
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
    "deportivo alavÃ©s": "alaves",
    "alaves": "alaves",
    "alavÃ©s": "alaves",
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
    return path.read_text(encoding="utf-8", errors="replace")


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
        return "âœ“"
    if canonical == "expected_starter":
        return "~"
    if canonical in {"confirmed_bench", "expected_bench"}:
        return "B"
    if canonical in {"not_in_squad", "expected_out"}:
        return "âœ•"
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
            "competition": fixture.get("competition") or league_label,
            "match_date": fixture.get("match_date") or "",
            "kickoff": fixture.get("kickoff") or "",
            "home_team": decode_html_value(fixture.get("home_team")),
            "away_team": decode_html_value(fixture.get("away_team")),
            "trust_tier": str(fixture.get("trust_tier") or "T1"),
            "lineup_input": str(fixture.get("lineup_input") or ""),
            "corruption_score": parse_int(fixture.get("corruption_score")) or 0,
            "corruption_flags": [decode_html_value(flag) for flag in fixture.get("corruption_flags", []) if decode_html_value(flag)],
            "notes": [decode_html_value(note) for note in fixture.get("notes", []) if decode_html_value(note)],
            "status_label": fixture_status_label(fixture),
            "summary": fixture_health_summary(fixture),
        }
        output.append(row)
    output.sort(key=lambda row: (kickoff_sort_value(row.get("kickoff")), row.get("key")))
    return output


def parse_fixture_health_rows(rows: list[dict[str, str]], league_key: str, league_label: str) -> list[dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    for row in rows:
        home_team = decode_html_value(row.get("home_team") or row.get("player_team") or "")
        away_team = decode_html_value(row.get("away_team") or row.get("opponent") or "")
        if not home_team or not away_team:
            continue
        key = f"{league_key}|{row.get('match_date', '')}|{team_key(home_team)}|{team_key(away_team)}"
        corruption_score = parse_int(row.get("corruption_score")) or 0
        fixture = fixtures.setdefault(key, {
            "key": key,
            "league_key": league_key,
            "league_label": league_label,
            "competition": decode_html_value(row.get("competition") or league_label),
            "match_date": row.get("match_date") or "",
            "kickoff": row.get("kickoff_iso") or row.get("kickoff") or row.get("match_date") or "",
            "home_team": home_team,
            "away_team": away_team,
            "trust_tier": str(row.get("trust_tier") or "T1"),
            "lineup_input": str(row.get("lineup_input") or ""),
            "corruption_score": corruption_score,
            "corruption_flags": [],
            "notes": [],
        })
        if corruption_score > (fixture.get("corruption_score") or 0):
            fixture["corruption_score"] = corruption_score
        if str(row.get("trust_tier") or "T1") == "T3":
            fixture["trust_tier"] = "T3"
        elif str(row.get("trust_tier") or "T1") == "T2" and fixture.get("trust_tier") != "T3":
            fixture["trust_tier"] = "T2"
        if row.get("lineup_input") == "none" and fixture.get("lineup_input") != "none":
            fixture["lineup_input"] = "none"
        elif row.get("lineup_input") == "expected_xi" and fixture.get("lineup_input") not in {"none"}:
            fixture["lineup_input"] = "expected_xi"
        for field in ("corruption_flags", "status_notes"):
            raw = str(row.get(field) or "").strip()
            if not raw:
                continue
            for chunk in re.split(r"\s*\|\s*", raw):
                cleaned = decode_html_value(chunk)
                if cleaned and cleaned not in fixture["corruption_flags"]:
                    fixture["corruption_flags"].append(cleaned)
        for field in ("status_notes", "position_note", "history_note"):
            raw = str(row.get(field) or "").strip()
            if not raw:
                continue
            cleaned = decode_html_value(raw)
            if cleaned and cleaned not in fixture["notes"]:
                fixture["notes"].append(cleaned)
    output = list(fixtures.values())
    for row in output:
        row["status_label"] = fixture_status_label(row)
        row["summary"] = fixture_health_summary(row)
    output.sort(key=lambda row: (kickoff_sort_value(row.get("kickoff")), row.get("key")))
    return output


def effective_monitor_action(row: dict[str, str]) -> str:
    public_action = row.get("public_action") or ""
    if public_action == "surface":
        return "surface"
    shadow_action = row.get("shadow_action") or ""
    if shadow_action == "shadow_track":
        return "shadow_track"
    return public_action or shadow_action or "hold"


def effective_monitor_action_label(row: dict[str, str]) -> str:
    action = effective_monitor_action(row)
    if action == "surface":
        return "Surface"
    if action == "shadow_track":
        return "Shadow"
    if action == "suppress":
        return "Suppress"
    return humanize_token(action) or "Hold"


def is_live_row(row: dict[str, str], today_iso: str, horizon_iso: str) -> bool:
    action = effective_monitor_action(row)
    if action not in {"surface", "shadow_track"}:
        return False
    match_date = str(row.get("match_date") or "")[:10]
    if not match_date:
        return True
    return today_iso <= match_date <= horizon_iso


def filter_active_rows(rows: list[dict[str, str]], today_iso: str, horizon_iso: str) -> list[dict[str, str]]:
    return [row for row in rows if is_live_row(row, today_iso, horizon_iso)]


def build_kickoff_lookup(rows: list[dict[str, str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in rows:
        match = decode_html_value(row.get("match"))
        home_team = decode_html_value(row.get("home_team") or "")
        away_team = decode_html_value(row.get("away_team") or "")
        kickoff = str(row.get("kickoff") or row.get("kickoff_iso") or "").strip()
        if not kickoff:
            continue
        keys = [
            f"{team_key(home_team)}|{team_key(away_team)}",
            f"{team_key(home_team)}|{team_key(away_team)}|{row.get('date', '')}",
            f"{team_key(home_team)}|{team_key(away_team)}|{row.get('match_date', '')}",
        ]
        if match and " vs " in match:
            home_name, away_name = [part.strip() for part in match.split(" vs ", 1)]
            keys.append(f"{team_key(home_name)}|{team_key(away_name)}")
            keys.append(f"{team_key(home_name)}|{team_key(away_name)}|{row.get('date', '')}")
            keys.append(f"{team_key(home_name)}|{team_key(away_name)}|{row.get('match_date', '')}")
        for key in keys:
            if key:
                lookup[key] = kickoff
    return lookup


def resolve_row_kickoff(row: dict[str, str], lookup: dict[str, str]) -> str:
    kickoff = str(row.get("kickoff") or row.get("kickoff_iso") or "").strip()
    if kickoff:
        return kickoff
    home_team = decode_html_value(row.get("home_team") or row.get("player_team") or "")
    away_team = decode_html_value(row.get("away_team") or row.get("opponent") or "")
    keys = [
        f"{team_key(home_team)}|{team_key(away_team)}",
        f"{team_key(home_team)}|{team_key(away_team)}|{row.get('date', '')}",
        f"{team_key(home_team)}|{team_key(away_team)}|{row.get('match_date', '')}",
    ]
    match = decode_html_value(row.get("match"))
    if match and " vs " in match:
        home_name, away_name = [part.strip() for part in match.split(" vs ", 1)]
        keys.extend([
            f"{team_key(home_name)}|{team_key(away_name)}",
            f"{team_key(home_name)}|{team_key(away_name)}|{row.get('date', '')}",
            f"{team_key(home_name)}|{team_key(away_name)}|{row.get('match_date', '')}",
        ])
    for key in keys:
        value = lookup.get(key)
        if value:
            return value
    return row.get("match_date") or row.get("date") or ""


def stake_label_for_row(row: dict[str, str]) -> str:
    label = decode_html_value(row.get("recommended_stake_label") or "")
    if label:
        return label
    stake = parse_float(row.get("recommended_stake_units"))
    if stake is None or stake <= 0:
        return "-"
    return f"{stake:g}u"


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


def build_settled_row(row: dict[str, str], league_key: str, competition: str | None = None) -> dict[str, Any]:
    ev_value = parse_float(row.get("ev"))
    pnl_units = parse_float(row.get("pnl_units"))
    return {
        "key": f"{row.get('date', '')}|{row.get('player', '')}|{row.get('match', '')}|{league_key}",
        "player": row.get("player") or "Unknown player",
        "team": row.get("team") or "Unknown team",
        "match": row.get("match") or "Unknown match",
        "competition": competition or row.get("competition") or "",
        "league_key": league_key,
        "kickoff": row.get("kickoff") or row.get("date") or "",
        "compared_at": row.get("compared_at") or "",
        "settled_at": row.get("settled_at") or "",
        "date": row.get("date") or "",
        "lineup_state": row.get("lineup_state") or "",
        "best_bookmaker_odds": parse_float(row.get("best_bookmaker_odds")),
        "model_fair_odds": parse_float(row.get("model_fair_odds")),
        "ev_pct": ev_value * 100 if ev_value is not None else None,
        "settled": True,
        "bet_outcome": decode_html_value(row.get("bet_outcome")),
        "settlement_note": decode_html_value(row.get("settlement_note")),
        "pnl_units": pnl_units,
    }


def is_settled_shadow_row(row: dict[str, str]) -> bool:
    return parse_bool(row.get("settled")) or str(row.get("bet_outcome") or "").strip().lower() in {"won", "lost", "void", "push"}


def shadow_row_activity_time(row: dict[str, Any]) -> float:
    values = [row.get("settled_at"), row.get("compared_at"), row.get("kickoff"), row.get("date")]
    newest = newest_timestamp([str(value) if value else None for value in values])
    parsed = parse_iso(newest) if newest else None
    return parsed.timestamp() if parsed else float("-inf")


def build_penalty_lookup(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for section in ("home", "away"):
        players = entry.get(section)
        if not isinstance(players, list):
            continue
        for player in players:
            if not isinstance(player, dict):
                continue
            keys = {
                person_key(player.get("name")),
                taker_key(player.get("name")),
                person_key(player.get("playerName")),
                taker_key(player.get("playerName")),
            }
            for key in keys:
                if key:
                    lookup[key] = player
    return lookup


def describe_player_at_penalty(player: dict[str, Any] | None, penalty_minute: int | None) -> str:
    if not player:
        return "Unknown"
    lineup_status = str(player.get("lineupStatus") or "").strip().lower()
    started = lineup_status == "starter"
    bench = lineup_status == "substitute"
    in_squad = bool(lineup_status)
    minutes_played = parse_int(player.get("minutesPlayed"))
    sub_minute = parse_int(player.get("substitutionMinute"))
    sub_type = str(player.get("substitutionType") or "").strip().lower()

    if not in_squad:
        return "No, not in squad"
    if penalty_minute is None:
        if started:
            return "Yes, starter"
        if bench:
            return "No, unused bench"
        return "Unknown"

    if started:
        if sub_type == "subbed_out" and sub_minute is not None and sub_minute < penalty_minute:
            return f"No, off {sub_minute}'"
        if sub_type == "subbed_out" and sub_minute is not None:
            return f"Yes, started (off {sub_minute}')"
        if minutes_played is not None and minutes_played < penalty_minute:
            return f"No, off {minutes_played}'"
        return "Yes, starter"

    if bench:
        if sub_type == "subbed_in" and sub_minute is not None:
            if sub_minute <= penalty_minute:
                return f"Yes, on from {sub_minute}'"
            return f"No, on from {sub_minute}'"
        return "No, unused bench"

    return "Unknown"


def build_penalty_context_rows(context_json: Any, penalty_review_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    # [content omitted here in this output due size]
    return []


def read_penalty_review_rows(config: dict[str, str]) -> tuple[list[dict[str, Any]], str | None]:
    review_rows = read_csv_rows(config["live_penalty_review_json"].replace(".json", ".csv"))
    if not review_rows:
        review_rows = read_csv_rows(config["penalty_review_json"].replace(".json", ".csv"))
    context_json = read_json(config["penalty_context_json"]) or {}
    rows = []
    latest_generated = context_json.get("generated_at") if isinstance(context_json, dict) else None
    for row in review_rows:
        rows.append({
            "row_id": decode_html_value(row.get("row_id") or ""), "date": row.get("date"), "league_key": config["key"], "competition": decode_html_value(row.get("competition") or config["label"]),
            "match": decode_html_value(row.get("match")), "team": decode_html_value(row.get("team")), "opponent": decode_html_value(row.get("opponent")), "actual_taker": decode_html_value(row.get("actual_taker")),
            "review_priority": decode_html_value(row.get("review_priority")), "transfer_flag": decode_html_value(row.get("transfer_flag")), "resolution_state": decode_html_value(row.get("resolution_state")),
            "primary_pre_match": decode_html_value(row.get("primary_pre_match")), "secondary_pre_match": decode_html_value(row.get("secondary_pre_match")), "tertiary_pre_match": decode_html_value(row.get("tertiary_pre_match")),
            "primary_lineup_status": decode_html_value(row.get("primary_lineup_status")), "secondary_lineup_status": decode_html_value(row.get("secondary_lineup_status")), "tertiary_lineup_status": decode_html_value(row.get("tertiary_lineup_status")),
            "active_taker_pre_match": decode_html_value(row.get("active_taker_pre_match")), "active_slot_pre_match": decode_html_value(row.get("active_slot_pre_match")), "team_lineup_status": decode_html_value(row.get("team_lineup_status")),
            "penalty_transfer_pre_match": parse_int(row.get("penalty_transfer_pre_match")), "inherited_from_pre_match": decode_html_value(row.get("inherited_from_pre_match")), "transfer_level_pre_match": decode_html_value(row.get("transfer_level_pre_match")),
            "editorial_note": decode_html_value(row.get("editorial_note")), "context_generated_at": row.get("context_generated_at"), "context_source_path": decode_html_value(row.get("context_source_path")),
            "primary_on_pitch_at_penalty": decode_html_value(row.get("primary_on_pitch_at_penalty")), "active_on_pitch_at_penalty": decode_html_value(row.get("active_on_pitch_at_penalty")), "actual_taker_on_pitch_at_penalty": decode_html_value(row.get("actual_taker_on_pitch_at_penalty")),
        })
    rows.sort(key=lambda row: shadow_row_activity_time({"settled_at": row.get("date"), "compared_at": row.get("date")}), reverse=True)
    return rows, latest_generated


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
    source_feed_gap_leagues: list[dict[str, Any]] = []
    raw_monitor_summary_chunks: list[str] = []
    penalty_watchlist_rows: list[dict[str, Any]] = []
    penalty_generated_values: list[str | None] = []
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
        all_public_signal_rows.extend(public_rows)
        kickoff_lookup = build_kickoff_lookup([*shadow_rows, *public_rows])

        league_public_live = [row for row in active_rows if row.get("public_action") == "surface"]
        league_shadow_live = [row for row in active_rows if row.get("shadow_action") == "shadow_track" and row.get("public_action") != "surface"]
        shadow_summary = compute_shadow_summary(shadow_rows)
        public_summary = compute_public_summary(public_rows)
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

        for row in shadow_rows:
            settled_row = build_settled_row(row, config["key"], row.get("competition") or config["label"])
            if is_settled_shadow_row(row):
                shadow_recent_rows.append(settled_row)
            target_iso = iso_date_for_value_in_timezone(row.get("settled_at") or row.get("date"))
            if is_settled_shadow_row(row) and target_iso == today_iso:
                shadow_today_rows.append(settled_row)
            if is_settled_shadow_row(row) and target_iso == yesterday_iso:
                shadow_yesterday_rows.append(settled_row)

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

    live_bets.sort(key=lambda row: (kickoff_sort_value(str(row.get("kickoff") or "")), 0 if row.get("status") == "PUBLIC" else 1, -((row.get("edge_pct") or 0) if isinstance(row.get("edge_pct"), (int, float)) else 0)))
    shadow_recent_rows.sort(key=lambda row: shadow_row_activity_time({"settled_at": row.get("settled_at", ""), "compared_at": row.get("compared_at", ""), "kickoff": row.get("kickoff", ""), "date": row.get("date", "")}), reverse=True)

    payload = {
        "schema_version": 1,
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
        "fixture_health": {"rows": fixture_health_rows},
        "fixture_lineups": fixture_lineups,
        "penalty_watchlist": {"generated_at": newest_timestamp(penalty_generated_values), "row_count": len(penalty_watchlist_rows), "rows": penalty_watchlist_rows},
        "shadow_summary": {"by_league": shadow_by_league, "recent_rows": shadow_recent_rows[:50], "settled_today": shadow_today_rows, "settled_yesterday": shadow_yesterday_rows},
        "public_summary": {"by_league": public_by_league},
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
    response = requests.post(f"{base}/rest/v1/{SNAPSHOT_TABLE}?on_conflict=snapshot_key", headers=headers, json=[row], timeout=30)
    if not response.ok:
        raise SystemExit(f"Supabase upload failed: {response.status_code} {response.text[:400]}")


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
