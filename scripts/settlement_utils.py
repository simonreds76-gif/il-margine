from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
RESULTS_SNAPSHOT_DIR = ROOT / "data" / "results-snapshot"

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


def resolve_snapshot_path(preferred_date: Optional[str] = None) -> Optional[Path]:
    target = parse_isoish_date(preferred_date or "") or datetime.now(UTC).date()
    candidates = [snapshot_path_for(target), snapshot_path_for(target - timedelta(days=1))]
    for path in candidates:
        if path.exists():
            return path
    return None


def load_results_snapshot(preferred_date: Optional[str] = None) -> Tuple[Dict[str, dict], Dict[str, dict], Optional[Path], dict]:
    path = resolve_snapshot_path(preferred_date)
    if path is None:
        return {}, {}, None, {}
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    results: Dict[str, dict] = {}
    source_freshness: Dict[str, dict] = {}
    for league, league_data in (payload.get("leagues") or {}).items():
        source_freshness[league] = {
            "football_data_latest": league_data.get("football_data_latest"),
            "lag_days": league_data.get("lag_days"),
            "football_data_count": league_data.get("football_data_count", 0),
            "fotmob_count": league_data.get("fotmob_count", 0),
            "fotmob_latest": league_data.get("fotmob_latest"),
            "snapshot_date": payload.get("snapshot_date"),
            "snapshot_path": str(path),
        }
        for key, fixture in (league_data.get("fixtures") or {}).items():
            results[key] = fixture
    return results, source_freshness, path, payload


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
