from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
RESULTS_SNAPSHOT_DIR = ROOT / "data" / "results-snapshot"
SNAPSHOT_LOOKBACK_DAYS = 7

LEAGUE_CODES = {
    "epl": "E0",
    "serie-a": "I1",
    "la-liga": "SP1",
    "bundesliga": "D1",
    "ligue-1": "F1",
}

GENERIC_TEAM_TOKENS = {
    "fc", "cf", "afc", "sc", "ac", "us", "ud", "rc", "ssc", "calcio", "1907",
}

TEAM_ALIASES: Dict[str, str] = {
    "brighton and hove albion": "brighton",
    "brighton hove albion": "brighton",
    "atalanta bc": "atalanta",
    "bologna fc": "bologna",
    "us lecce": "lecce",
    "tsg hoffenheim": "hoffenheim",
    "fc augsburg": "augsburg",
    "inter": "internazionale",
    "inter milan": "internazionale",
    "inter milano": "internazionale",
    "fc st pauli": "st pauli",
    "vfb stuttgart": "stuttgart",
    "hamburger sv": "hamburg",
    "vfl wolfsburg": "wolfsburg",
    "fsv mainz 05": "mainz",
    "mainz 05": "mainz",
    "borussia m gladbach": "borussia monchengladbach",
    "m gladbach": "borussia monchengladbach",
    "bayer 04 leverkusen": "bayer leverkusen",
    "sc freiburg": "freiburg",
    "1 fc union berlin": "union berlin",
    "1 fc heidenheim": "heidenheim",
    "1 fc cologne": "1 koln",
    "1 fc koln": "1 koln",
    "fc koln": "1 koln",
    "wolverhampton wanderers": "wolverhampton",
    "tottenham hotspur": "tottenham",
    "liverpool fc": "liverpool",
    "fulham fc": "fulham",
    "burnley fc": "burnley",
    "manchester city": "man city",
    "manchester united": "man united",
    "manchester utd": "man united",
    "man utd": "man united",
    "leeds united": "leeds",
    "west ham united": "west ham",
    "nottingham forest": "nott m forest",
    "newcastle united": "newcastle",
    "newcastle utd": "newcastle",
    "valencia cf": "valencia",
    "elche cf": "elche",
    "real sociedad": "sociedad",
    "real sociedad san sebastian": "sociedad",
    "deportivo alaves": "alaves",
    "atletico madrid": "ath madrid",
    "athletic club": "ath bilbao",
    "athletic bilbao": "ath bilbao",
    "real betis": "betis",
    "real betis seville": "betis",
    "ca osasuna": "osasuna",
    "fc barcelona": "barcelona",
    "espanyol": "espanol",
    "espanyol barcelona": "espanol",
    "rc celta de vigo": "celta",
    "celta vigo": "celta",
    "rcd mallorca": "mallorca",
    "rayo vallecano": "vallecano",
    "rayo vallecano de madrid": "vallecano",
    "bayern munchen": "bayern munich",
    "olympique de marseille": "marseille",
    "olympique marseille": "marseille",
    "olympique lyonnais": "lyon",
    "ogc nice": "nice",
    "as roma": "roma",
    "juventus turin": "juventus",
    "pisa sc": "pisa",
    "girona fc": "girona",
}


def normalize_text_basic(text: str) -> str:
    value = (text or "").strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def normalize_team_name(text: str) -> str:
    base = normalize_text_basic(text)
    simplified = " ".join(token for token in base.split() if token not in GENERIC_TEAM_TOKENS).strip()
    for candidate in (base, simplified):
        if candidate in TEAM_ALIASES:
            return TEAM_ALIASES[candidate]
    return simplified or base


def parse_isoish_date(raw: str) -> Optional[date]:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            dt = datetime.strptime(text[:19], fmt[: len(text[:19].replace("T", " "))])
            return dt.date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def snapshot_path_for(day: date) -> Path:
    return RESULTS_SNAPSHOT_DIR / f"{day.isoformat()}.json"


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def resolve_snapshot_paths(preferred_date: Optional[str] = None) -> list[Path]:
    target = parse_isoish_date(preferred_date or "") or datetime.now(UTC).date()
    candidates: list[Path] = []
    for offset in range(SNAPSHOT_LOOKBACK_DAYS):
        path = snapshot_path_for(target - timedelta(days=offset))
        if path.exists():
            candidates.append(path)
    if candidates:
        return candidates
    latest_path = RESULTS_SNAPSHOT_DIR / "latest.json"
    if latest_path.exists():
        return [latest_path]
    return []


def load_results_snapshot(preferred_date: Optional[str] = None) -> Tuple[Dict[str, dict], Dict[str, dict], Optional[Path], dict]:
    paths = resolve_snapshot_paths(preferred_date)
    if not paths:
        return {}, {}, None, {}

    primary_path = paths[0]
    results: Dict[str, dict] = {}
    source_freshness: Dict[str, dict] = {}
    merged_payload: dict[str, Any] = {
        "snapshot_date": None,
        "snapshot_paths": [display_path(path) for path in paths],
    }

    # Newest snapshot wins on duplicate keys; older snapshots only fill holes.
    for index, path in enumerate(paths):
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if index == 0:
            merged_payload["snapshot_date"] = payload.get("snapshot_date")
            merged_payload["fetched_at"] = payload.get("fetched_at")
        for league, league_data in (payload.get("leagues") or {}).items():
            if league not in source_freshness:
                source_freshness[league] = {
                    "football_data_latest": league_data.get("football_data_latest"),
                    "lag_days": league_data.get("lag_days"),
                    "football_data_count": league_data.get("football_data_count", 0),
                    "fotmob_count": league_data.get("fotmob_count", 0),
                    "fotmob_latest": league_data.get("fotmob_latest"),
                    "api_football_count": league_data.get("api_football_count", 0),
                    "api_football_latest": league_data.get("api_football_latest"),
                    "api_football_requests_used": league_data.get("api_football_requests_used", 0),
                    "api_football_requests_remaining_after_league": league_data.get(
                        "api_football_requests_remaining_after_league",
                        0,
                    ),
                    "api_football_error": league_data.get("api_football_error"),
                    "api_football_max_requests": league_data.get("api_football_max_requests", 0),
                    "snapshot_date": payload.get("snapshot_date"),
                    "snapshot_path": display_path(path),
                }
            for key, fixture in (league_data.get("fixtures") or {}).items():
                if key not in results:
                    results[key] = fixture
    return results, source_freshness, primary_path, merged_payload


def collect_target_dates(rows: Iterable[dict], kickoff_fields: Iterable[str], date_fields: Iterable[str]) -> Dict[str, set[str]]:
    target_dates_by_league: Dict[str, set[str]] = {}
    for row in rows:
        league = (row.get("league") or "").strip()
        if not league:
            continue
        raw_date = ""
        for field in kickoff_fields:
            raw_date = (row.get(field) or "").strip()
            if raw_date:
                break
        parsed = parse_isoish_date(raw_date)
        if parsed is None:
            for field in date_fields:
                parsed = parse_isoish_date((row.get(field) or "").strip())
                if parsed is not None:
                    break
        if parsed is None:
            continue
        bucket = target_dates_by_league.setdefault(league, set())
        for delta in (-1, 0, 1):
            bucket.add((parsed + timedelta(days=delta)).isoformat())
    return target_dates_by_league


def build_fixture_key(match_date: date | str, home_team: str, away_team: str) -> str:
    if isinstance(match_date, date):
        date_str = match_date.isoformat()
    else:
        date_str = str(match_date).strip()[:10]
    return f"{date_str}|{normalize_team_name(home_team)}|{normalize_team_name(away_team)}"


def ensure_snapshot_dir() -> None:
    RESULTS_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _parse_optional_int(raw: object) -> Optional[int]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _split_override_match(row: Mapping[str, object]) -> tuple[str, str]:
    home = str(row.get("home_team", "") or "").strip()
    away = str(row.get("away_team", "") or "").strip()
    if home and away:
        return home, away

    match = str(row.get("match", "") or "").strip()
    if not match:
        return "", ""

    parts = re.split(r"\s+vs\.?\s+|\s+v\s+", match, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", ""


def load_manual_settlement_results(path: Path) -> Dict[str, dict]:
    """
    Load optional manual settlement rows that can supplement a stale results snapshot.

    Supported columns are intentionally loose so the CSV can stay human-editable.
    Existing columns (`league,match,kickoff_iso,reason`) remain valid; when stat
    columns are also present, those rows become usable as manual result entries.
    """
    if not path.exists():
        return {}

    results: Dict[str, dict] = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            match_date = parse_isoish_date(str(row.get("kickoff_iso", "") or ""))
            if match_date is None:
                match_date = parse_isoish_date(str(row.get("fixture_date", "") or ""))
            if match_date is None:
                continue

            home_team, away_team = _split_override_match(row)
            if not home_team or not away_team:
                continue

            home_shots = _parse_optional_int(row.get("home_shots"))
            away_shots = _parse_optional_int(row.get("away_shots"))
            home_corners = _parse_optional_int(row.get("home_corners"))
            away_corners = _parse_optional_int(row.get("away_corners"))

            # Keep reason-only overrides valid for the audit path, but do not
            # manufacture fake results from them.
            if home_shots is None and away_shots is None and home_corners is None and away_corners is None:
                continue

            entry = {
                "home_team": normalize_team_name(home_team),
                "away_team": normalize_team_name(away_team),
                "source": "manual-override",
                "reason": str(row.get("reason", "") or "").strip(),
            }
            if home_shots is not None and away_shots is not None:
                entry["home_shots"] = home_shots
                entry["away_shots"] = away_shots
            if home_corners is not None and away_corners is not None:
                entry["home_corners"] = home_corners
                entry["away_corners"] = away_corners
                entry["total_corners"] = home_corners + away_corners

            key = build_fixture_key(match_date, home_team, away_team)
            results[key] = entry

    return results
