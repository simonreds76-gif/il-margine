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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


LONDON = ZoneInfo("Europe/London")
MATCH_VISIBILITY_AFTER_KICKOFF = timedelta(minutes=150)

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
DEFAULT_TEAM_KIT_COLORS = Path("data/goalscorer/team-kit-colors.json")
DEFAULT_MATCH_STATUS = Path("data/goalscorer/goalscorer-match-status.json")
DEFAULT_TEAM_MATCH_BASE = Path("data/football-form/team-match-base.csv")
DEFAULT_EXPOSURE_LOG_DIR = Path("data/goalscorer")
DEFAULT_LINEUP_FIXTURES = [
    Path("data/goalscorer/confirmed-lineups.json"),
    Path("data/goalscorer/epl-confirmed-lineups.json"),
    Path("data/goalscorer/la-liga-confirmed-lineups.json"),
    Path("data/goalscorer/bundesliga-confirmed-lineups.json"),
    Path("data/goalscorer/ligue-1-confirmed-lineups.json"),
]
DEFAULT_FORM_PLAYER_LOG_DIR = Path("data/goalscorer")

PUBLIC_EDGE_THRESHOLD_PP = 6.0
PUBLIC_MAX_SIGNALS = 5
PUBLIC_MIN_MODEL_PROB_PCT = 20.0
PUBLIC_MAX_MARKET_ODDS = 6.0
PUBLIC_MAX_MODEL_MARKET_GAP_PP = 10.0
PUBLIC_MAX_MODEL_MARKET_PROBABILITY_RATIO = 1.50
PUBLIC_OFFICIAL_LINEUP_WINDOW_MINUTES = 0
FAIR_ODDS_LAB_POLICY_REASON = "fair_odds_lab_likely_starters_top5_edge6_prob20_odds6"
GOALSCORER_MODEL_VERSION = "goalscorer_v1_raw"
GOALSCORER_CALIBRATION_VERSION = "raw_incumbent_v0"
DEFENSIVE_POSITION_TOKENS = {
    "GK",
    "D",
    "DC",
    "DEF",
    "CB",
    "LB",
    "RB",
    "LWB",
    "RWB",
    "DL",
    "DR",
    "FB",
}

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


def load_team_kit_color_overrides(path: Path = DEFAULT_TEAM_KIT_COLORS) -> dict[str, tuple[str, str, str]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}

    overrides: dict[str, tuple[str, str, str]] = {}
    for raw_key, raw_value in payload.items():
        if not isinstance(raw_value, dict):
            continue
        primary = str(raw_value.get("primary") or "").strip()
        secondary = str(raw_value.get("secondary") or "").strip()
        pattern = str(raw_value.get("pattern") or "solid").strip()
        if not primary or not secondary:
            continue
        if pattern not in {"solid", "vertical-stripes", "halves", "sash"}:
            pattern = "solid"
        key = unicodedata.normalize("NFKD", str(raw_key or ""))
        key = "".join(ch for ch in key if not unicodedata.combining(ch)).lower()
        key = re.sub(r"[^a-z0-9]+", " ", key).strip()
        key = re.sub(r"\s+", " ", key)
        if key:
            overrides[key] = (primary, secondary, pattern)
    return overrides


TEAM_STYLE_OVERRIDES.update(load_team_kit_color_overrides())

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

FAIR_ODDS_LAB_LOG_FIELDS = [
    "date",
    "kickoff",
    "match",
    "competition",
    "player",
    "team",
    "opponent",
    "signal_type",
    "finishing_luck",
    "fixture_swing",
    "penalty_transfer",
    "penalty_transfer_from",
    "position_upgrade",
    "role_adjustment_factor",
    "role_adjustment_reason",
    "lineup_state",
    "model_p_atgs",
    "model_fair_odds",
    "model_version",
    "calibration_version",
    "p_calibrated",
    "edge_vs_novig_pp",
    "pinnacle_odds_at_publish",
    "tracking_tier",
    "best_bookmaker",
    "best_bookmaker_odds",
    "ev",
    "confidence",
    "compared_at",
    "fotmob_match_id",
    "player_id",
    "market_player_name",
    "home_team",
    "away_team",
    "position_group",
    "position",
    "historical_minutes",
    "trust_tier",
    "public_action",
    "public_policy_reason",
    "penalty_dependent",
    "penalty_dependency_share",
    "recommended_stake_units",
    "recommended_stake_band",
    "recommended_stake_label",
    "super_sub_eligible_bookmaker",
    "super_sub_checked",
    "super_sub_replacement",
    "super_sub_replacement_goals",
    "settled",
    "goals_scored",
    "bet_outcome",
    "settled_at",
    "pnl_units",
    "settlement_note",
]

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
    team_form: dict[str, Any] | None
    opponent_form: dict[str, Any] | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        help="Input CSV or live-board JSON. May be supplied multiple times. Defaults to all goalscorer live-board/comparison files.",
    )
    parser.add_argument("--monitor-snapshot", type=Path, default=DEFAULT_MONITOR_SNAPSHOT)
    parser.add_argument(
        "--match-status",
        type=Path,
        default=DEFAULT_MATCH_STATUS,
        help="FotMob fixture-status artifact used to remove completed matches immediately.",
    )
    parser.add_argument("--team-logo-map", type=Path, default=DEFAULT_TEAM_LOGO_MAP)
    parser.add_argument(
        "--team-match-base",
        type=Path,
        default=DEFAULT_TEAM_MATCH_BASE,
        help="Optional canonical team-match base CSV used for public rolling-form explanations.",
    )
    parser.add_argument(
        "--lineups",
        type=Path,
        action="append",
        help="Confirmed/expected lineup JSON files used to enrich signals with FotMob ids and kickoff UTC. Defaults to all goalscorer lineup files.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--exposure-log-dir",
        type=Path,
        default=DEFAULT_EXPOSURE_LOG_DIR,
        help="Directory for append-only Fair Odds Lab public exposure logs.",
    )
    parser.add_argument(
        "--skip-exposure-log",
        action="store_true",
        help="Local QA only. Do not append the public exposure log.",
    )
    parser.add_argument("--edge-threshold-pp", type=float, default=PUBLIC_EDGE_THRESHOLD_PP)
    parser.add_argument("--max-signals", type=int, default=PUBLIC_MAX_SIGNALS)
    parser.add_argument("--min-model-prob-pct", type=float, default=PUBLIC_MIN_MODEL_PROB_PCT)
    parser.add_argument("--max-market-odds", type=float, default=PUBLIC_MAX_MARKET_ODDS)
    parser.add_argument(
        "--official-lineup-window-minutes",
        type=int,
        default=PUBLIC_OFFICIAL_LINEUP_WINDOW_MINUTES,
        help="Require confirmed starters inside this many minutes before kickoff. Default 0 keeps likely starters visible until official teams update them.",
    )
    parser.set_defaults(allow_projected_lineups=True)
    parser.add_argument(
        "--allow-projected-lineups",
        dest="allow_projected_lineups",
        action="store_true",
        help="Allow FotMob expected starters on the public board. This is the default.",
    )
    parser.add_argument(
        "--confirmed-lineups-only",
        dest="allow_projected_lineups",
        action="store_false",
        help="Hide projected starters and publish confirmed starters only.",
    )
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


def avg_float(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def round_float(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def load_team_match_base_index(path: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Load causal team-match rows for public explanation context.

    The model signal itself is still driven by the goalscorer output. This layer
    only adds plain-English form context such as last-5 xGD and opponent xGA.
    """

    if not path.exists():
        return {}

    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            date_key = clean_text(row.get("date"))
            league = league_slug(clean_text(row.get("league")))
            team = canonical_team_key(row.get("team"))
            if not date_key or not team:
                continue
            index.setdefault((league, team), []).append(dict(row))

    for rows in index.values():
        rows.sort(key=lambda item: clean_text(item.get("date")))
    return index


def load_goalscorer_player_log_form_index() -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Fallback recent-form source from goalscorer player logs.

    The preferred form layer is team-match-base.csv, but CI can build it into a
    temp directory and still fail to pass that path forward. The player logs are
    already required for the goalscorer model, so this keeps the public page
    from leaking "Unknown" form tiles when the temp form artifact is missing.
    """

    fixture_rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for path in sorted(DEFAULT_FORM_PLAYER_LOG_DIR.glob("*player-match-logs-*.csv")):
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                date_key = clean_text(row.get("match_date"))
                league = league_slug(clean_text(row.get("competition")))
                team = clean_text(row.get("team"))
                opponent = clean_text(row.get("opponent"))
                team_key = canonical_team_key(team)
                opponent_key = canonical_team_key(opponent)
                if not date_key or not league or not team_key or not opponent_key:
                    continue
                key = (date_key, league, team_key, opponent_key)
                fixture = fixture_rows.setdefault(
                    key,
                    {
                        "date": date_key,
                        "league": league,
                        "team": team,
                        "team_key": team_key,
                        "opponent": opponent,
                        "opponent_key": opponent_key,
                        "xg_for": None,
                        "xg_against": None,
                        "shots_for": 0.0,
                        "sot_for": 0.0,
                    },
                )
                team_xg = parse_float(row.get("team_xg"))
                team_xga = parse_float(row.get("team_xga"))
                if fixture.get("xg_for") is None and team_xg is not None:
                    fixture["xg_for"] = team_xg
                if fixture.get("xg_against") is None and team_xga is not None:
                    fixture["xg_against"] = team_xga
                fixture["shots_for"] = float(fixture.get("shots_for") or 0.0) + (parse_float(row.get("shots")) or 0.0)
                fixture["sot_for"] = float(fixture.get("sot_for") or 0.0) + (parse_float(row.get("shots_on_target")) or 0.0)

    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for (date_key, league, team_key, opponent_key), fixture in fixture_rows.items():
        opponent_fixture = fixture_rows.get((date_key, league, opponent_key, team_key))
        row = {
            "date": date_key,
            "league": league,
            "team": fixture.get("team"),
            "team_key": team_key,
            "opponent": fixture.get("opponent"),
            "opponent_key": opponent_key,
            "xg_for": fixture.get("xg_for"),
            "xg_against": fixture.get("xg_against"),
            "shots_for": fixture.get("shots_for"),
            "shots_against": opponent_fixture.get("shots_for") if opponent_fixture else None,
            "sot_for": fixture.get("sot_for"),
            "sot_against": opponent_fixture.get("sot_for") if opponent_fixture else None,
        }
        index.setdefault((league, team_key), []).append(row)

    for rows in index.values():
        rows.sort(key=lambda item: clean_text(item.get("date")))
    return index


def team_rows_for_form(
    index: dict[tuple[str, str], list[dict[str, Any]]],
    league: str,
    team: str,
) -> list[dict[str, Any]]:
    team = canonical_team_key(team)
    if not team:
        return []
    exact = index.get((league, team))
    if exact:
        return exact
    # Promotion/relegation names can drift between league slugs; same-team fallback
    # is safer than dropping context entirely.
    merged: list[dict[str, Any]] = []
    for (_row_league, row_team), rows in index.items():
        if row_team == team:
            merged.extend(rows)
    return sorted(merged, key=lambda item: clean_text(item.get("date")))


def recent_form_context(
    index: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    league: str,
    team: str,
    before_date: str,
    window: int = 5,
) -> dict[str, Any] | None:
    rows = team_rows_for_form(index, league, team)
    if not rows:
        return None

    cutoff = before_date[:10]
    eligible = [row for row in rows if not cutoff or clean_text(row.get("date")) < cutoff]
    recent = eligible[-window:]
    if not recent:
        return None

    xg_for = avg_float([parse_float(row.get("xg_for")) for row in recent])
    xg_against = avg_float([parse_float(row.get("xg_against")) for row in recent])
    xgd = xg_for - xg_against if xg_for is not None and xg_against is not None else None

    return {
        "window": window,
        "matches": len(recent),
        "through_date": clean_text(recent[-1].get("date")),
        "xg_for_avg": round_float(xg_for),
        "xg_against_avg": round_float(xg_against),
        "xgd_per90": round_float(xgd),
        "shots_for_avg": round_float(avg_float([parse_float(row.get("shots_for")) for row in recent]), 1),
        "shots_against_avg": round_float(avg_float([parse_float(row.get("shots_against")) for row in recent]), 1),
        "sot_for_avg": round_float(avg_float([parse_float(row.get("sot_for")) for row in recent]), 1),
        "sot_against_avg": round_float(avg_float([parse_float(row.get("sot_against")) for row in recent]), 1),
        "corners_for_avg": round_float(avg_float([parse_float(row.get("corners_for")) for row in recent]), 1),
        "corners_against_avg": round_float(avg_float([parse_float(row.get("corners_against")) for row in recent]), 1),
    }


def opponent_team_for_row(row: dict[str, Any]) -> str:
    explicit = clean_text(row.get("opponent"))
    if explicit:
        return explicit

    player_team = canonical_team_key(row.get("player_team"))
    home = clean_text(row.get("home_team"))
    away = clean_text(row.get("away_team"))
    if player_team and canonical_team_key(home) == player_team:
        return away
    if player_team and canonical_team_key(away) == player_team:
        return home
    return ""


def recent_team_form_tier(context: dict[str, Any] | None) -> str:
    xgd = parse_float((context or {}).get("xgd_per90"))
    if xgd is None:
        return "Unknown"
    if xgd >= 0.65:
        return "Strong"
    if xgd >= 0.25:
        return "Positive"
    if xgd >= -0.25:
        return "Average"
    return "Quiet"


def recent_defence_weakness_tier(context: dict[str, Any] | None) -> str:
    xga = parse_float((context or {}).get("xg_against_avg"))
    if xga is None:
        return "Unknown"
    if xga >= 1.7:
        return "High"
    if xga >= 1.35:
        return "Positive"
    if xga >= 1.0:
        return "Average"
    return "Low"


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


def canonical_person_key(value: Any | None) -> str:
    normalized = normalize_logo_key(value)
    normalized = re.sub(r"\b(?:jr|junior|sr|ii|iii|iv)\b", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


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


def load_completed_fixture_keys(path: Path) -> set[tuple[str, str, str, str]]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return set()
    fixtures = payload.get("completed_fixtures", []) if isinstance(payload, dict) else []
    keys: set[tuple[str, str, str, str]] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        if not (fixture.get("finished") or fixture.get("cancelled")):
            continue
        league = clean_text(fixture.get("league"))
        match_date = clean_text(fixture.get("match_date"))
        home = clean_text(fixture.get("home_team"))
        away = clean_text(fixture.get("away_team"))
        if league and match_date and home and away:
            keys.add(lineup_fixture_key(league, match_date, home, away))
    return keys


def is_confirmed_lineup_type(value: Any | None) -> bool:
    return clean_text(value).lower() in {"confirmed", "standard", "confirmed xi", "confirmed_lineup"}


def lineup_player_keys(fixture: dict[str, Any], side: str) -> set[str]:
    keys: set[str] = set()
    for field in (f"{side}_starters", f"{side}_players"):
        players = fixture.get(field)
        if not isinstance(players, list):
            continue
        for player in players:
            if isinstance(player, dict):
                key = canonical_person_key(player.get("name"))
            else:
                key = canonical_person_key(player)
            if key:
                keys.add(key)
    return keys


def fixture_side_for_row(row: dict[str, Any], fixture: dict[str, Any]) -> str:
    player_team = canonical_team_key(row.get("player_team") or row.get("team"))
    if player_team and player_team == canonical_team_key(fixture.get("home_team")):
        return "home"
    if player_team and player_team == canonical_team_key(fixture.get("away_team")):
        return "away"
    row_home = canonical_team_key(row.get("home_team"))
    if row_home and row_home == canonical_team_key(fixture.get("home_team")):
        return "home"
    return "away"


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
            lineup_type = clean_text(fixture.get("lineup_type")).lower()
            copied["_lineup_type"] = lineup_type
            lineup_is_confirmed = is_confirmed_lineup_type(lineup_type)

            side = fixture_side_for_row(copied, fixture)
            player_key = canonical_person_key(copied.get("canonical_player_name") or copied.get("player_name"))
            starter_keys = lineup_player_keys(fixture, side)
            matched_starter = bool(player_key and player_key in starter_keys)
            if matched_starter:
                copied["lineup_state"] = "starter"
                copied["lineup_status"] = "confirmed" if lineup_is_confirmed else "projected xi"
                copied["lineup_source"] = "confirmed_lineups" if lineup_is_confirmed else "expected_lineups"
            elif lineup_is_confirmed and starter_keys:
                copied["lineup_state"] = "bench"
                copied["lineup_status"] = "confirmed"
                copied["lineup_source"] = "confirmed_lineups"
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


def kickoff_datetime_utc(row: dict[str, Any]) -> datetime | None:
    kickoff = clean_text(row.get("kickoff"))
    if not kickoff:
        return None
    value = kickoff.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def position_label(row: dict[str, Any]) -> str:
    return clean_text(row.get("today_position_group") or row.get("position_group") or row.get("position")).upper()


def is_defensive_position(row: dict[str, Any]) -> bool:
    text = position_label(row)
    if not text:
        return False
    tokens = {token for token in re.split(r"[^A-Z0-9]+", text) if token}
    return bool(tokens & DEFENSIVE_POSITION_TOKENS)


def minutes_until_kickoff(row: dict[str, Any]) -> float | None:
    kickoff_dt = kickoff_datetime_utc(row)
    if kickoff_dt is None:
        return None
    return (kickoff_dt - datetime.now(timezone.utc)).total_seconds() / 60


def official_lineup_required(row: dict[str, Any], window_minutes: int) -> bool:
    if window_minutes <= 0:
        return False
    minutes = minutes_until_kickoff(row)
    return minutes is not None and 0 <= minutes <= window_minutes


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
    team_form_index: dict[tuple[str, str], list[dict[str, Any]]],
    completed_fixture_keys: set[tuple[str, str, str, str]] | None = None,
) -> tuple[list[dict[str, Any]], list[Candidate]]:
    raw_future_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    now_utc = datetime.now(timezone.utc)

    for row in all_rows:
        date_key = row_date_key(row)
        fixture_key = lineup_fixture_key(
            league_slug(clean_text(row.get("competition"))),
            date_key,
            row.get("home_team"),
            row.get("away_team"),
        )
        if completed_fixture_keys and fixture_key in completed_fixture_keys:
            continue
        if not include_past:
            kickoff_dt = kickoff_datetime_utc(row)
            if kickoff_dt is not None:
                if kickoff_dt <= now_utc and now_utc - kickoff_dt > MATCH_VISIBILITY_AFTER_KICKOFF:
                    continue
            elif date_key and date_key < today_iso:
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
        competition = clean_text(row.get("competition"), "Football")
        league = league_slug(competition)
        match_date = row_date_key(row)
        player_team = clean_text(row.get("player_team"))
        opponent_team = opponent_team_for_row(row)
        team_form = recent_form_context(
            team_form_index,
            league=league,
            team=player_team,
            before_date=match_date,
        )
        opponent_form = recent_form_context(
            team_form_index,
            league=league,
            team=opponent_team,
            before_date=match_date,
        )

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
                team_form=team_form,
                opponent_form=opponent_form,
            )
        )

    return raw_future_rows, candidates


def read_grouped_candidates(
    input_paths: list[Path],
    monitor_snapshot_path: Path,
    lineup_fixture_paths: list[Path],
    today_iso: str,
    include_past: bool,
    team_form_index: dict[tuple[str, str], list[dict[str, Any]]],
    completed_fixture_keys: set[tuple[str, str, str, str]],
) -> tuple[list[dict[str, Any]], list[Candidate], list[str]]:
    source_paths: list[str] = []
    source_rows: list[dict[str, Any]] = []
    for input_path in input_paths:
        rows = read_rows_from_input(input_path)
        if rows:
            source_paths.append(str(input_path).replace("\\", "/"))
            source_rows.extend(rows)

    source_rows = enrich_rows_with_lineups(source_rows, load_lineup_fixture_lookup(lineup_fixture_paths))
    raw_rows, candidates = build_candidates_from_rows(source_rows, today_iso, include_past, team_form_index, completed_fixture_keys)
    if raw_rows:
        return raw_rows, candidates, source_paths

    monitor_rows = monitor_live_bets_to_rows(monitor_snapshot_path)
    if monitor_rows:
        source_paths = [str(monitor_snapshot_path).replace("\\", "/")]
        return (*build_candidates_from_rows(monitor_rows, today_iso, include_past, team_form_index, completed_fixture_keys), source_paths)

    return raw_rows, candidates, source_paths


def fair_odds_lab_log_path(log_dir: Path, league: str, suffix: str = "signals.csv") -> Path:
    return log_dir / f"fair-odds-lab-{league}-{suffix}"


def exposure_log_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        clean_text(row.get("date")),
        normalize_logo_key(row.get("match")),
        normalize_logo_key(row.get("player") or row.get("market_player_name")),
    )


def read_exposure_log(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], FAIR_ODDS_LAB_LOG_FIELDS.copy()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or FAIR_ODDS_LAB_LOG_FIELDS)
        for field in FAIR_ODDS_LAB_LOG_FIELDS:
            if field not in fieldnames:
                fieldnames.append(field)
        return list(reader), fieldnames


def write_exposure_log(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_rows = [{field: clean_text(row.get(field)) for field in fieldnames} for row in rows]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(normalized_rows)


def fmt_decimal(value: float | None, digits: int) -> str:
    if value is None:
        value = 0.0
    return f"{value:.{digits}f}"


def exposure_row_from_candidate(candidate: Candidate) -> dict[str, str]:
    row = candidate.row
    date_key = row_date_key(row)
    home_team = clean_text(row.get("home_team"))
    away_team = clean_text(row.get("away_team"))
    player_name = clean_text(row.get("canonical_player_name") or row.get("player_name"))
    fixture_swing = candidate.fixture_swing if candidate.fixture_swing is not None else parse_float(row.get("fixture_swing_3"))
    best_ev = (candidate.model_prob_pct / 100 * candidate.best_odds) - 1.0

    return {
        "date": date_key,
        "kickoff": clean_text(row.get("kickoff")) or date_key,
        "match": f"{home_team} vs {away_team}".strip(),
        "competition": clean_text(row.get("competition")),
        "player": player_name,
        "team": clean_text(row.get("player_team")),
        "opponent": clean_text(row.get("opponent")),
        "signal_type": "fair_odds_lab",
        "finishing_luck": fmt_decimal(parse_float(row.get("finishing_luck_8")), 4),
        "fixture_swing": fmt_decimal(fixture_swing, 4),
        "penalty_transfer": "1" if clean_text(row.get("penalty_transfer")).lower() in {"1", "true", "yes"} else "0",
        "penalty_transfer_from": clean_text(row.get("penalty_transfer_from")),
        "position_upgrade": "1" if clean_text(row.get("position_upgrade")).lower() in {"1", "true", "yes"} else "0",
        "role_adjustment_factor": fmt_decimal(parse_float(row.get("role_adjustment_factor")) or 1.0, 4),
        "role_adjustment_reason": clean_text(row.get("role_adjustment_reason")),
        "lineup_state": clean_text(row.get("lineup_state")) or lineup_label(row),
        "model_p_atgs": fmt_decimal(candidate.model_prob_pct / 100, 6),
        "model_fair_odds": fmt_decimal(candidate.fair_odds, 4),
        "model_version": clean_text(row.get("model_version"), GOALSCORER_MODEL_VERSION),
        "calibration_version": clean_text(
            row.get("calibration_version"),
            GOALSCORER_CALIBRATION_VERSION,
        ),
        # The incumbent is uncalibrated. Keeping the value explicit makes the
        # forward cutover auditable without pretending a calibrator is live.
        "p_calibrated": fmt_decimal(candidate.model_prob_pct / 100, 6),
        # ATGS is one-sided in the current feed, so a true no-vig probability
        # and Pinnacle reference do not exist. Record that limitation instead
        # of manufacturing a comparison from raw implied probability.
        "edge_vs_novig_pp": "unavailable_one_sided_market",
        "pinnacle_odds_at_publish": "unavailable",
        "tracking_tier": "display_row",
        "best_bookmaker": clean_text(row.get("bookmaker"), "Best market"),
        "best_bookmaker_odds": fmt_decimal(candidate.best_odds, 4),
        "ev": fmt_decimal(best_ev, 6),
        "confidence": normalize_confidence(row.get("signal_confidence"), lineup_label(row), candidate.expected_minutes),
        "compared_at": clean_text(row.get("compared_at")) or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fotmob_match_id": clean_text(row.get("_fotmob_match_id")),
        "player_id": clean_text(row.get("player_id")),
        "market_player_name": clean_text(row.get("player_name")) or player_name,
        "home_team": home_team,
        "away_team": away_team,
        "position_group": clean_text(row.get("today_position_group") or row.get("position_group")),
        "position": clean_text(row.get("position")),
        "historical_minutes": fmt_decimal(parse_float(row.get("historical_minutes")) or candidate.expected_minutes, 1),
        "trust_tier": clean_text(row.get("trust_tier")),
        "public_action": "surface",
        "public_policy_reason": FAIR_ODDS_LAB_POLICY_REASON,
        "penalty_dependent": "1" if clean_text(row.get("penalty_dependent")).lower() in {"1", "true", "yes"} else "0",
        "penalty_dependency_share": fmt_decimal(parse_float(row.get("penalty_dependency_share")), 4),
        "recommended_stake_units": "1.00",
        "recommended_stake_band": "research",
        "recommended_stake_label": "Research only",
        "super_sub_eligible_bookmaker": "",
        "super_sub_checked": "",
        "super_sub_replacement": "",
        "super_sub_replacement_goals": "",
        "settled": "",
        "goals_scored": "",
        "bet_outcome": "",
        "settled_at": "",
        "pnl_units": "",
        "settlement_note": "",
    }


def append_exposure_logs(candidates: list[Candidate], log_dir: Path) -> dict[str, int]:
    rows_by_league: dict[str, list[dict[str, str]]] = {}
    for candidate in candidates:
        league = league_slug(clean_text(candidate.row.get("competition"), "football"))
        rows_by_league.setdefault(league, []).append(exposure_row_from_candidate(candidate))

    added_by_league: dict[str, int] = {}
    for league, rows in sorted(rows_by_league.items()):
        path = fair_odds_lab_log_path(log_dir, league)
        existing_rows, fieldnames = read_exposure_log(path)
        existing_keys = {exposure_log_key(row) for row in existing_rows}
        added_rows = [row for row in rows if exposure_log_key(row) not in existing_keys]
        if not added_rows:
            added_by_league[league] = 0
            continue
        merged = existing_rows + added_rows
        merged.sort(key=lambda row: (clean_text(row.get("date")), clean_text(row.get("kickoff")), clean_text(row.get("match")), clean_text(row.get("player"))))
        write_exposure_log(path, merged, fieldnames)
        added_by_league[league] = len(added_rows)
    return added_by_league


def build_reasons(
    candidate: Candidate,
    recent_tier: str,
    opponent_tier: str,
    penalty: str,
    fixture_boost_pct: int,
) -> list[str]:
    team_form_tier = recent_team_form_tier(candidate.team_form)
    opponent_recent_tier = recent_defence_weakness_tier(candidate.opponent_form)
    reasons = [
        "The model price is shorter than the bookmaker's best available price",
    ]

    if candidate.team_share is not None and candidate.team_share >= 0.25:
        reasons.append("A large share of the team's chances runs through him")
    if recent_tier in {"Strong", "Very strong"}:
        reasons.append(f"Recent chance quality grades as {recent_tier.lower()}")
    if team_form_tier in {"Strong", "Positive"}:
        reasons.append("Recent team form supports the attacking case")
    if opponent_tier in {"High", "Very high"}:
        reasons.append("Opponent defensive profile is a positive matchup")
    elif opponent_recent_tier in {"High", "Positive"}:
        reasons.append("Opponent has been allowing chances recently")
    if fixture_boost_pct >= 10:
        reasons.append("The fixture profile adds to his scoring case")
    role_factor = parse_float(candidate.row.get("role_adjustment_factor"))
    if role_factor is not None and role_factor >= 1.03:
        reasons.append("Confirmed XI shows a more advanced scoring role")
    if penalty == "Primary":
        reasons.append("Primary penalty role adds a clear scoring route")

    return reasons[:5]


def public_quality_exclusion_reason(
    candidate: Candidate,
    *,
    min_model_prob_pct: float,
    max_market_odds: float,
    official_lineup_window_minutes: int,
    allow_projected_lineups: bool,
) -> str:
    lineup = lineup_label(candidate.row).lower()
    confidence = normalize_confidence(
        candidate.row.get("signal_confidence"),
        lineup,
        candidate.expected_minutes,
    )

    if "unknown" in lineup or "bench" in lineup:
        return "lineup_not_public_quality"
    if confidence == "Low":
        return "low_signal_confidence"
    if not allow_projected_lineups and "confirmed starter" not in lineup:
        return "confirmed_lineup_required"
    if candidate.expected_minutes is not None and candidate.expected_minutes < 70:
        return "expected_minutes_lt_70"
    if candidate.model_prob_pct < min_model_prob_pct:
        return "model_probability_below_floor"
    if candidate.best_odds > max_market_odds:
        return "market_odds_above_cap"
    if is_defensive_position(candidate.row):
        return "defensive_position"
    if official_lineup_required(candidate.row, official_lineup_window_minutes) and "confirmed starter" not in lineup:
        return "official_lineup_required"
    if candidate.price_gap_pp > PUBLIC_MAX_MODEL_MARKET_GAP_PP:
        return "model_market_gap_gt_10pp"
    if candidate.implied_pct <= 0:
        return "invalid_market_probability"
    if candidate.model_prob_pct / candidate.implied_pct > PUBLIC_MAX_MODEL_MARKET_PROBABILITY_RATIO:
        return "model_market_probability_ratio_gt_1_5x"
    return ""


def is_public_quality_signal(
    candidate: Candidate,
    *,
    min_model_prob_pct: float,
    max_market_odds: float,
    official_lineup_window_minutes: int,
    allow_projected_lineups: bool,
) -> bool:
    return not public_quality_exclusion_reason(
        candidate,
        min_model_prob_pct=min_model_prob_pct,
        max_market_odds=max_market_odds,
        official_lineup_window_minutes=official_lineup_window_minutes,
        allow_projected_lineups=allow_projected_lineups,
    )


def public_signal_score(signal: dict[str, Any]) -> float:
    confidence_rank = {"High": 3, "Medium": 2, "Low": 1}
    metrics = signal.get("metrics", {})
    lineup = clean_text(metrics.get("lineup_confidence"))
    share = float(metrics.get("share_of_team_chances_pct") or 0)
    best_odds = float(signal.get("market_data", {}).get("best_odds") or 0)
    model_prob = float(signal.get("model", {}).get("scoring_chance_pct") or 0)
    gap = float(signal.get("edge", {}).get("price_gap_pp") or 0)
    score = model_prob + (gap * 1.6) + (share * 0.18)
    score += confidence_rank.get(clean_text(signal.get("confidence_tier")), 0) * 4
    if lineup == "Confirmed starter":
        score += 5
    score -= max(0.0, best_odds - 5.0) * 1.5
    return score


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
    recent_team_form = recent_team_form_tier(candidate.team_form)
    opponent_recent_defence = recent_defence_weakness_tier(candidate.opponent_form)
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
            "lineup_type": "confirmed" if is_confirmed_lineup_type(row.get("_lineup_type")) else clean_text(row.get("_lineup_type")),
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
            "recent_team_form": {
                "tier": recent_team_form,
                **(candidate.team_form or {}),
            },
            "opponent_defensive_weakness": {
                "tier": opponent_tier,
                "percentile": percentiles["opponent_xga"],
            },
            "opponent_recent_defence": {
                "tier": opponent_recent_defence,
                **(candidate.opponent_form or {}),
            },
            "fixture_boost_pct": fixture_boost_pct,
            "projected_minutes": round(candidate.expected_minutes) if candidate.expected_minutes is not None else None,
            "penalty_role": penalty,
            "role_adjustment_factor": parse_float(row.get("role_adjustment_factor")) or 1.0,
            "role_adjustment_reason": clean_text(row.get("role_adjustment_reason")),
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
    completed_fixture_keys = load_completed_fixture_keys(args.match_status)
    team_form_index = load_team_match_base_index(args.team_match_base)
    team_form_source = str(args.team_match_base).replace("\\", "/") if team_form_index else ""
    if not team_form_index:
        team_form_index = load_goalscorer_player_log_form_index()
        team_form_source = "data/goalscorer/*player-match-logs-*.csv" if team_form_index else ""
    raw_rows, candidates, source_paths = read_grouped_candidates(
        input_paths,
        args.monitor_snapshot,
        lineup_paths,
        today_iso,
        args.include_past,
        team_form_index,
        completed_fixture_keys,
    )

    values = {
        "recent": [c.recent_npxg for c in candidates if c.recent_npxg is not None],
        "team_xg": [c.team_xg for c in candidates if c.team_xg is not None],
        "team_share": [c.team_share for c in candidates if c.team_share is not None],
        "opponent_xga": [c.opponent_xga for c in candidates if c.opponent_xga is not None],
        "minutes": [c.expected_minutes for c in candidates if c.expected_minutes is not None],
    }

    qualifying: list[Candidate] = []
    safety_exclusions: dict[str, int] = {}
    for candidate in candidates:
        if candidate.price_gap_pp < args.edge_threshold_pp or candidate.best_odds <= candidate.fair_odds:
            continue
        exclusion_reason = public_quality_exclusion_reason(
            candidate,
            min_model_prob_pct=args.min_model_prob_pct,
            max_market_odds=args.max_market_odds,
            official_lineup_window_minutes=args.official_lineup_window_minutes,
            allow_projected_lineups=args.allow_projected_lineups,
        )
        if exclusion_reason:
            safety_exclusions[exclusion_reason] = safety_exclusions.get(exclusion_reason, 0) + 1
            continue
        qualifying.append(candidate)

    signal_entries: list[tuple[Candidate, dict[str, Any]]] = []
    for candidate in qualifying:
        percentiles = {
            "recent": percentile(candidate.recent_npxg, values["recent"]),
            "team_xg": percentile(candidate.team_xg, values["team_xg"]),
            "team_share": percentile(candidate.team_share, values["team_share"]),
            "opponent_xga": percentile(candidate.opponent_xga, values["opponent_xga"]),
            "minutes": percentile(candidate.expected_minutes, values["minutes"]),
        }
        signal_entries.append((candidate, build_signal(candidate, percentiles, logo_manifest)))

    signal_entries.sort(
        key=lambda item: (
            -public_signal_score(item[1]),
            item[1]["match"].get("kickoff_utc") or item[1]["match"].get("kickoff_display") or "",
        )
    )
    if args.max_signals > 0:
        signal_entries = signal_entries[: args.max_signals]
    selected_candidates = [candidate for candidate, _signal in signal_entries]
    signals = [signal for _candidate, signal in signal_entries]

    exposure_added_by_league: dict[str, int] = {}
    if not args.skip_exposure_log:
        exposure_added_by_league = append_exposure_logs(selected_candidates, args.exposure_log_dir)

    fixtures_evaluated = len({(row_date_key(row), clean_text(row.get("home_team")), clean_text(row.get("away_team"))) for row in raw_rows})
    leagues_covered = sorted({signal["match"]["league"] for signal in signals})

    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_file": source_paths,
        "team_form_source": team_form_source,
        "edge_threshold_pp": args.edge_threshold_pp,
        "public_filters": {
            "min_model_prob_pct": args.min_model_prob_pct,
            "max_market_odds": args.max_market_odds,
            "max_model_market_gap_pp": PUBLIC_MAX_MODEL_MARKET_GAP_PP,
            "max_model_market_probability_ratio": PUBLIC_MAX_MODEL_MARKET_PROBABILITY_RATIO,
            "max_signals": args.max_signals,
            "official_lineup_window_minutes": args.official_lineup_window_minutes,
            "require_confirmed_starter": not args.allow_projected_lineups,
            "defensive_positions_hidden": sorted(DEFENSIVE_POSITION_TOKENS),
            "post_kickoff_visibility_minutes": int(MATCH_VISIBILITY_AFTER_KICKOFF.total_seconds() / 60),
            "completed_fixture_filter": "fotmob_status_with_150_minute_fallback",
        },
        "fixtures_evaluated": fixtures_evaluated,
        "signals_qualifying": len(signals),
        "safety_exclusions": safety_exclusions,
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
    print(f"Team form context: {team_form_source or 'not available'}")
    print(f"Output: {args.output}")
    print(f"Today filter: {today_iso} (include_past={args.include_past})")
    print(f"Fixtures evaluated: {fixtures_evaluated}")
    print(f"Signals qualifying: {len(signals)}")
    print(f"Edge threshold: +{args.edge_threshold_pp:.1f}pp")
    print(f"Min model chance: {args.min_model_prob_pct:.1f}%")
    print(f"Max market odds: {args.max_market_odds:.2f}")
    print(f"Official lineup window: {args.official_lineup_window_minutes} minutes")
    if args.skip_exposure_log:
        print("Exposure log: skipped")
    elif exposure_added_by_league:
        added_summary = ", ".join(f"{league} +{count}" for league, count in sorted(exposure_added_by_league.items()))
        print(f"Exposure log additions: {added_summary}")
    else:
        print("Exposure log additions: none")


if __name__ == "__main__":
    main()
