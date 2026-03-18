"""
Goalscorer calibration model.

This is a first confirmed-lineup goalscorer model for Serie A. It uses prior
player history plus team context to estimate P(scores at least one goal) for
each player-match row in the historical log.

Inputs:
  data/goalscorer/serie-a-player-match-logs-*.csv

Outputs:
  data/goalscorer/goalscorer-backtest-results.csv
  data/goalscorer/goalscorer-calibration.txt
  data/goalscorer/goalscorer-calibration-bins.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from itertools import groupby
from typing import Dict, Iterable, List, Optional


RECENT_WINDOW = 16
LONG_WINDOW = 40
MIN_PLAYER_MATCHES = 4
MIN_LONG_MATCHES = 10
FORM_DECAY = 0.94
RECENT_BLEND = 0.7
HOME_FACTOR = 1.08
PLAYER_SHRINK_MINUTES = 900.0
TEAM_SHRINK_MATCHES = 8.0
DEFAULT_START_MINUTES = 79.0
DEFAULT_SUB_MINUTES = 24.0
DEFAULT_UNKNOWN_MINUTES = 62.0
UNALLOCATED_SHARE_FLOOR = 0.10

LEAGUE_AVG = {
    "npxg_per_90": 0.20,
    "team_npxg_per_match": 1.21,
    "team_xg_per_match": 1.30,
    "team_xga_per_match": 1.30,
    "penalties_per_match": 0.12,
    "penalty_conversion": 0.77,
}

POSITION_PRIORS = {
    "FW": 0.34,
    "FWR": 0.26,
    "FWL": 0.26,
    "AMC": 0.19,
    "AMR": 0.17,
    "AML": 0.17,
    "MC": 0.11,
    "ML": 0.10,
    "MR": 0.10,
    "DMC": 0.08,
    "DC": 0.04,
    "DL": 0.05,
    "DR": 0.05,
    "DML": 0.06,
    "DMR": 0.06,
    "Sub": 0.08,
    "Unknown": 0.12,
}

TEAM_ALIASES = {
    "ac milan": "milan",
    "milan": "milan",
    "inter": "inter",
    "inter milan": "inter",
    "internazionale": "inter",
    "lazio rome": "lazio",
    "hellas verona": "verona",
    "verona": "verona",
    "juventus": "juventus",
    "juventus fc": "juventus",
    "juventus turin": "juventus",
    "as roma": "roma",
    "roma": "roma",
    "pisa sc": "pisa",
    "us cremonese": "cremonese",
    "sassuolo calcio": "sassuolo",
    "bologna fc": "bologna",
    "genoa cfc": "genoa",
    "ss lazio": "lazio",
    "lazio": "lazio",
    "atalanta": "atalanta",
    "atalanta bc": "atalanta",
    "acf fiorentina": "fiorentina",
    "fiorentina": "fiorentina",
    "bologna": "bologna",
    "bologna fc 1909": "bologna",
    "cagliari": "cagliari",
    "cagliari calcio": "cagliari",
    "como": "como",
    "como 1907": "como",
    "hellas verona fc": "verona",
    "empoli": "empoli",
    "empoli fc": "empoli",
    "genoa": "genoa",
    "genoa cfc": "genoa",
    "lecce": "lecce",
    "us lecce": "lecce",
    "monza": "monza",
    "ac monza": "monza",
    "napoli": "napoli",
    "ssc napoli": "napoli",
    "parma": "parma",
    "parma calcio 1913": "parma",
    "parma calcio": "parma",
    "torino": "torino",
    "torino fc": "torino",
    "udinese": "udinese",
    "udinese calcio": "udinese",
    "venezia": "venezia",
    "venezia fc": "venezia",
    "acf fiorentina": "fiorentina",
    "cremonese": "cremonese",
    "pisa": "pisa",
    "sassuolo": "sassuolo",
    "arsenal": "arsenal",
    "aston villa": "aston villa",
    "afc bournemouth": "bournemouth",
    "bournemouth": "bournemouth",
    "brentford": "brentford",
    "brentford fc": "brentford",
    "brighton": "brighton",
    "brighton hove albion": "brighton",
    "brighton and hove albion": "brighton",
    "burnley": "burnley",
    "burnley fc": "burnley",
    "chelsea": "chelsea",
    "chelsea fc": "chelsea",
    "crystal palace": "crystal palace",
    "everton": "everton",
    "everton fc": "everton",
    "fulham": "fulham",
    "fulham fc": "fulham",
    "ipswich": "ipswich",
    "ipswich town": "ipswich",
    "leicester": "leicester",
    "leicester city": "leicester",
    "leeds united": "leeds",
    "liverpool": "liverpool",
    "liverpool fc": "liverpool",
    "manchester city": "manchester city",
    "man city": "manchester city",
    "manchester united": "manchester united",
    "man utd": "manchester united",
    "newcastle": "newcastle united",
    "newcastle united": "newcastle united",
    "nottingham forest": "nottingham forest",
    "forest": "nottingham forest",
    "southampton": "southampton",
    "sunderland": "sunderland",
    "tottenham": "tottenham",
    "tottenham hotspur": "tottenham",
    "spurs": "tottenham",
    "west ham": "west ham",
    "west ham united": "west ham",
    "wolves": "wolves",
    "wolverhampton": "wolves",
    "wolverhampton wanderers": "wolves",
    "alaves": "alaves",
    "deportivo alaves": "alaves",
    "athletic club": "athletic club",
    "athletic bilbao": "athletic club",
    "atletico": "atletico madrid",
    "atletico madrid": "atletico madrid",
    "fc barcelona": "barcelona",
    "barcelona": "barcelona",
    "betis": "real betis",
    "real betis": "real betis",
    "celta": "celta vigo",
    "celta vigo": "celta vigo",
    "espanyol": "espanyol",
    "rcd espanyol": "espanyol",
    "getafe": "getafe",
    "girona": "girona",
    "las palmas": "las palmas",
    "leganes": "leganes",
    "cd leganes": "leganes",
    "mallorca": "mallorca",
    "rcd mallorca": "mallorca",
    "osasuna": "osasuna",
    "ca osasuna": "osasuna",
    "rayo vallecano": "rayo vallecano",
    "real madrid": "real madrid",
    "real sociedad": "real sociedad",
    "sevilla": "sevilla",
    "valencia": "valencia",
    "villarreal": "villarreal",
    "valladolid": "valladolid",
    "real valladolid": "valladolid",
    "elche": "elche",
    "levante": "levante",
    "fc augsburg": "augsburg",
    "augsburg": "augsburg",
    "bayer leverkusen": "bayer leverkusen",
    "leverkusen": "bayer leverkusen",
    "bayern": "bayern munich",
    "bayern munich": "bayern munich",
    "borussia dortmund": "borussia dortmund",
    "dortmund": "borussia dortmund",
    "borussia monchengladbach": "borussia m gladbach",
    "borussia m gladbach": "borussia m gladbach",
    "monchengladbach": "borussia m gladbach",
    "gladbach": "borussia m gladbach",
    "eintracht frankfurt": "eintracht frankfurt",
    "frankfurt": "eintracht frankfurt",
    "freiburg": "freiburg",
    "sc freiburg": "freiburg",
    "hamburger sv": "hamburger sv",
    "hamburg": "hamburger sv",
    "hsv": "hamburger sv",
    "heidenheim": "fc heidenheim",
    "fc heidenheim": "fc heidenheim",
    "1 fc heidenheim": "fc heidenheim",
    "koln": "fc cologne",
    "cologne": "fc cologne",
    "1 fc cologne": "fc cologne",
    "1 fc koln": "fc cologne",
    "fc koln": "fc cologne",
    "fc cologne": "fc cologne",
    "mainz": "mainz 05",
    "mainz 05": "mainz 05",
    "rb leipzig": "rasenballsport leipzig",
    "rasenballsport leipzig": "rasenballsport leipzig",
    "leipzig": "rasenballsport leipzig",
    "st pauli": "st pauli",
    "fc st pauli": "st pauli",
    "stuttgart": "vfb stuttgart",
    "vfb stuttgart": "vfb stuttgart",
    "union berlin": "union berlin",
    "werder bremen": "werder bremen",
    "bremen": "werder bremen",
    "bochum": "bochum",
    "vfl bochum": "bochum",
    "hoffenheim": "hoffenheim",
    "tsg hoffenheim": "hoffenheim",
    "wolfsburg": "wolfsburg",
    "vfl wolfsburg": "wolfsburg",
    "toulouse fc": "toulouse",
    "fc lorient": "lorient",
    "ogc nice": "nice",
    "racing club de lens": "lens",
    "angers sco": "angers",
    "aj auxerre": "auxerre",
    "stade brest 29": "brest",
    "paris saint germain": "paris saint germain",
    "paris saint-germain": "paris saint germain",
}


@dataclass
class NormalizedRow:
    season: str
    match_date: date
    match_date_str: str
    player_id: str
    player_name: str
    team: str
    team_key: str
    opponent: str
    opponent_key: str
    is_home: bool
    position: str
    started: Optional[bool]
    minutes: int
    goals: int
    shots: int
    xg: float
    npxg: float
    penalties_scored: int
    penalties_attempted: int
    team_xg: Optional[float]
    team_xga: Optional[float]


def _team_key(name: str) -> str:
    import re

    cleaned = re.sub(r"[^a-z0-9]+", " ", (name or "").strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return TEAM_ALIASES.get(cleaned, cleaned)


def _mean(values: Iterable[float], default: float = 0.0) -> float:
    data = list(values)
    return sum(data) / len(data) if data else default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _shrink(value: float, sample: float, prior_value: float, prior_sample: float) -> float:
    if sample <= 0:
        return prior_value
    return ((value * sample) + (prior_value * prior_sample)) / (sample + prior_sample)


def _parse_date(value: str) -> Optional[date]:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def coarse_position(position: str) -> str:
    text = (position or "").split(",")[0].strip()
    if not text:
        return "Unknown"
    return text


def position_prior(position: str) -> float:
    return POSITION_PRIORS.get(coarse_position(position), LEAGUE_AVG["npxg_per_90"])


def _parse_bool(value: str) -> Optional[bool]:
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "nan"}:
        return None
    if text.upper() in {"1", "TRUE", "Y", "YES", "*"}:
        return True
    if text.upper() in {"0", "FALSE", "N", "NO"}:
        return False
    return None


def _parse_int(value: str, default: int = 0) -> int:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def _parse_float(value: str, default: Optional[float] = 0.0) -> Optional[float]:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _expand_paths(paths: List[str]) -> List[str]:
    expanded: List[str] = []
    for path in paths:
        if "*" in path or "?" in path:
            matches = glob.glob(path)
            if not matches:
                print(f"  Warning: glob '{path}' matched no files")
            expanded.extend(matches)
        else:
            expanded.append(path)
    return expanded


def detect_columns(rows: List[dict]) -> Dict[str, Optional[str]]:
    keys = set(rows[0].keys()) if rows else set()

    def find(candidates: Iterable[str]) -> Optional[str]:
        for candidate in candidates:
            for key in keys:
                if key.lower() == candidate.lower():
                    return key
        return None

    return {
        "season": find(["season", "dataset"]),
        "match_date": find(["match_date", "date"]),
        "player_id": find(["player_id"]),
        "player_name": find(["player_name"]),
        "team": find(["team"]),
        "opponent": find(["opponent", "opponent_name"]),
        "is_home": find(["is_home"]),
        "position": find(["position"]),
        "started": find(["started"]),
        "minutes": find(["minutes"]),
        "goals": find(["goals"]),
        "shots": find(["shots", "shots_total"]),
        "xg": find(["xg"]),
        "npxg": find(["npxg"]),
        "penalties_scored": find(["penalties_scored", "pens_made", "penalty_goals"]),
        "penalties_attempted": find(["penalties_attempted", "pens_att", "penalties_taken"]),
        "team_xg": find(["team_xg"]),
        "team_xga": find(["team_xga"]),
    }


def load_match_logs(paths: List[str]) -> List[NormalizedRow]:
    raw_rows: List[dict] = []
    for path in _expand_paths(paths):
        if not os.path.exists(path):
            print(f"  Warning: {path} not found")
            continue
        with open(path, "r", encoding="utf-8-sig") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = list(csv.DictReader(handle, dialect=dialect))
            print(f"  Loaded {len(rows):,} rows from {os.path.basename(path)}")
            raw_rows.extend({k.strip().lower(): v for k, v in row.items()} for row in rows)

    if not raw_rows:
        return []

    columns = detect_columns(raw_rows)
    normalized: List[NormalizedRow] = []
    for row in raw_rows:
        match_date = _parse_date(row.get(columns["match_date"] or "", ""))
        player_id = row.get(columns["player_id"] or "", "")
        if match_date is None or not player_id:
            continue

        team = row.get(columns["team"] or "", "").strip()
        opponent = row.get(columns["opponent"] or "", "").strip()
        normalized.append(
            NormalizedRow(
                season=row.get(columns["season"] or "", ""),
                match_date=match_date,
                match_date_str=match_date.isoformat(),
                player_id=player_id.strip(),
                player_name=row.get(columns["player_name"] or "", "").strip(),
                team=team,
                team_key=_team_key(team),
                opponent=opponent,
                opponent_key=_team_key(opponent),
                is_home=str(row.get(columns["is_home"] or "", "")).strip().lower() in {"1", "true", "y", "yes"},
                position=(row.get(columns["position"] or "", "") or "").strip(),
                started=_parse_bool(row.get(columns["started"] or "", "")),
                minutes=_parse_int(row.get(columns["minutes"] or "", "0"), 0),
                goals=_parse_int(row.get(columns["goals"] or "", "0"), 0),
                shots=_parse_int(row.get(columns["shots"] or "", "0"), 0),
                xg=_parse_float(row.get(columns["xg"] or "", "0"), 0.0) or 0.0,
                npxg=_parse_float(row.get(columns["npxg"] or "", "0"), None)
                if columns["npxg"]
                else None,
                penalties_scored=_parse_int(row.get(columns["penalties_scored"] or "", "0"), 0),
                penalties_attempted=_parse_int(row.get(columns["penalties_attempted"] or "", "0"), 0),
                team_xg=_parse_float(row.get(columns["team_xg"] or "", ""), None),
                team_xga=_parse_float(row.get(columns["team_xga"] or "", ""), None),
            )
        )

    filtered: List[NormalizedRow] = []
    for row in normalized:
        if row.npxg is None:
            row.npxg = row.xg
        position_upper = (row.position or "").upper()
        if position_upper.startswith("GK"):
            continue
        filtered.append(row)

    filtered.sort(key=lambda row: (row.match_date, row.team_key, row.player_id))
    return filtered


class PlayerHistory:
    def __init__(self) -> None:
        self.matches: List[dict] = []

    def add_match(self, match: dict) -> None:
        self.matches.append(match)

    def summary(self, window: int) -> Optional[dict]:
        if not self.matches:
            return None

        recent = self.matches[-window:]
        weights = [FORM_DECAY ** (len(recent) - 1 - idx) for idx in range(len(recent))]
        total_weight = sum(weights)
        weighted_minutes = sum(match["minutes"] * weight for match, weight in zip(recent, weights))
        if total_weight <= 0 or weighted_minutes <= 0:
            return None

        weighted_90s = weighted_minutes / 90.0
        known_started = [(match, weight) for match, weight in zip(recent, weights) if match["started"] is not None]
        start_rows = [(match, weight) for match, weight in known_started if match["started"]]
        sub_rows = [(match, weight) for match, weight in known_started if match["started"] is False]

        known_start_weight = sum(weight for _, weight in known_started)
        start_weight = sum(weight for _, weight in start_rows)
        start_rate = (start_weight / known_start_weight) if known_start_weight > 0 else None
        avg_start_minutes = (
            sum(match["minutes"] * weight for match, weight in start_rows) / start_weight if start_weight > 0 else None
        )
        sub_weight = sum(weight for _, weight in sub_rows)
        avg_sub_minutes = (
            sum(match["minutes"] * weight for match, weight in sub_rows) / sub_weight if sub_weight > 0 else None
        )

        if start_rate is not None and avg_start_minutes is not None and avg_sub_minutes is not None:
            expected_minutes = (start_rate * avg_start_minutes) + ((1.0 - start_rate) * avg_sub_minutes)
        elif avg_start_minutes is not None:
            expected_minutes = avg_start_minutes
        elif avg_sub_minutes is not None:
            expected_minutes = avg_sub_minutes
        else:
            expected_minutes = weighted_minutes / total_weight

        weighted_npxg = sum(match["npxg"] * weight for match, weight in zip(recent, weights))
        weighted_shots = sum(match["shots"] * weight for match, weight in zip(recent, weights))
        weighted_player_pens = sum(match["penalties_attempted"] * weight for match, weight in zip(recent, weights))
        weighted_team_pens = sum(match["team_penalties_attempted"] * weight for match, weight in zip(recent, weights))

        return {
            "n_matches": len(recent),
            "weighted_minutes": weighted_minutes,
            "weighted_npxg": weighted_npxg,
            "avg_minutes": weighted_minutes / total_weight,
            "expected_minutes": expected_minutes,
            "avg_start_minutes": avg_start_minutes,
            "avg_sub_minutes": avg_sub_minutes,
            "start_rate": start_rate,
            "npxg_per_90": weighted_npxg / weighted_90s if weighted_90s > 0 else 0.0,
            "shots_per_90": weighted_shots / weighted_90s if weighted_90s > 0 else 0.0,
            "player_pen_weighted": weighted_player_pens,
            "team_pen_weighted": weighted_team_pens,
            "penalty_share": (weighted_player_pens / weighted_team_pens) if weighted_team_pens > 0 else 0.0,
        }


class TeamHistory:
    def __init__(self) -> None:
        self.matches: List[dict] = []

    def add_match(self, match: dict) -> None:
        self.matches.append(match)

    def summary(self, window: int = 20) -> Optional[dict]:
        if not self.matches:
            return None

        recent = self.matches[-window:]
        weights = [FORM_DECAY ** (len(recent) - 1 - idx) for idx in range(len(recent))]
        total_weight = sum(weights)
        if total_weight <= 0:
            return None

        def weighted(field: str, fallback: float) -> float:
            values = [match[field] for match in recent if match[field] is not None]
            if not values:
                return fallback
            weighted_total = sum(match[field] * weight for match, weight in zip(recent, weights) if match[field] is not None)
            weight_total = sum(weight for match, weight in zip(recent, weights) if match[field] is not None)
            return weighted_total / weight_total if weight_total > 0 else fallback

        return {
            "n_matches": len(recent),
            "weighted_npxg_total": sum(
                match["team_npxg"] * weight for match, weight in zip(recent, weights) if match["team_npxg"] is not None
            ),
            "npxg_per_match": weighted("team_npxg", LEAGUE_AVG["team_npxg_per_match"]),
            "xg_per_match": weighted("team_xg", LEAGUE_AVG["team_xg_per_match"]),
            "xga_per_match": weighted("team_xga", LEAGUE_AVG["team_xga_per_match"]),
            "penalties_per_match": weighted("team_penalties_attempted", LEAGUE_AVG["penalties_per_match"]),
        }


def expected_minutes_from_summary(summary: Optional[dict], confirmed_started: Optional[bool]) -> float:
    if summary is None:
        if confirmed_started is True:
            return DEFAULT_START_MINUTES
        if confirmed_started is False:
            return DEFAULT_SUB_MINUTES
        return DEFAULT_UNKNOWN_MINUTES

    if confirmed_started is True:
        return summary["avg_start_minutes"] or max(summary["avg_minutes"], DEFAULT_START_MINUTES)
    if confirmed_started is False:
        return summary["avg_sub_minutes"] or min(summary["avg_minutes"], DEFAULT_SUB_MINUTES)
    return summary["expected_minutes"]


def team_factor(summary: Optional[dict], field: str, league_key: str, low: float, high: float) -> tuple[float, bool]:
    if summary is None:
        return 1.0, True
    shrunk = _shrink(summary[field], summary["n_matches"], LEAGUE_AVG[league_key], TEAM_SHRINK_MATCHES)
    factor = shrunk / LEAGUE_AVG[league_key]
    return _clamp(factor, low, high), summary["n_matches"] < 3


def team_level_npxg(summary: Optional[dict]) -> tuple[float, bool]:
    if summary is None:
        return LEAGUE_AVG["team_npxg_per_match"], True
    value = _shrink(summary["npxg_per_match"], summary["n_matches"], LEAGUE_AVG["team_npxg_per_match"], TEAM_SHRINK_MATCHES)
    return _clamp(value, 0.65, 2.4), summary["n_matches"] < 3


def build_team_expected_npxg(
    team_summary: Optional[dict],
    opponent_summary: Optional[dict],
    is_home: bool,
) -> tuple[float, float, float, bool, bool]:
    team_base_npxg, attack_fallback = team_level_npxg(team_summary)
    opp_factor, defense_fallback = team_factor(opponent_summary, "xga_per_match", "team_xga_per_match", 0.80, 1.25)
    home_factor = HOME_FACTOR if is_home else (1.0 / HOME_FACTOR)
    return team_base_npxg * opp_factor * home_factor, team_base_npxg / LEAGUE_AVG["team_npxg_per_match"], opp_factor, attack_fallback, defense_fallback


def build_player_rate(recent_summary: dict, long_summary: Optional[dict], position: str) -> float:
    rate = recent_summary["npxg_per_90"]
    if long_summary is not None and long_summary["n_matches"] >= MIN_LONG_MATCHES:
        rate = (RECENT_BLEND * recent_summary["npxg_per_90"]) + ((1.0 - RECENT_BLEND) * long_summary["npxg_per_90"])
    return _shrink(rate, recent_summary["weighted_minutes"], position_prior(position), PLAYER_SHRINK_MINUTES)


def build_player_propensity(
    recent_summary: Optional[dict],
    long_summary: Optional[dict],
    position: str,
    expected_minutes: float,
) -> tuple[float, float, str]:
    if recent_summary is not None and recent_summary["n_matches"] >= MIN_PLAYER_MATCHES:
        base_rate = build_player_rate(recent_summary, long_summary, position)
        method = "model"
    else:
        base_rate = position_prior(position)
        method = "fallback"
    propensity = max(base_rate, 0.0001) * max(expected_minutes, 1.0) / 90.0
    return propensity, base_rate, method


def build_player_raw_share(
    recent_summary: Optional[dict],
    team_summary: Optional[dict],
    expected_minutes: float,
) -> float:
    if recent_summary is None or team_summary is None:
        return 0.0
    team_total = team_summary.get("weighted_npxg_total", 0.0) or 0.0
    if team_total <= 0:
        return 0.0
    player_total = max(recent_summary.get("weighted_npxg", 0.0) or 0.0, 0.0)
    if player_total <= 0:
        return 0.0
    raw_share = player_total / team_total
    return max(0.0, raw_share * (max(expected_minutes, 1.0) / 90.0))


def build_penalty_component(
    player_recent: dict,
    player_long: Optional[dict],
    team_summary: Optional[dict],
    expected_minutes: float,
) -> tuple[float, float]:
    team_pen_rate = LEAGUE_AVG["penalties_per_match"]
    if team_summary is not None:
        team_pen_rate = _shrink(
            team_summary["penalties_per_match"],
            team_summary["n_matches"],
            LEAGUE_AVG["penalties_per_match"],
            TEAM_SHRINK_MATCHES,
        )

    penalty_share = player_recent["penalty_share"]
    share_sample = player_recent["team_pen_weighted"]
    if player_long is not None and player_long["team_pen_weighted"] > 0:
        penalty_share = (RECENT_BLEND * penalty_share) + ((1.0 - RECENT_BLEND) * player_long["penalty_share"])
        share_sample = max(share_sample, player_long["team_pen_weighted"])

    penalty_share = _clamp(_shrink(penalty_share, share_sample, 0.0, 1.5), 0.0, 1.0)
    penalty_lambda = team_pen_rate * penalty_share * LEAGUE_AVG["penalty_conversion"] * (expected_minutes / 90.0)
    return penalty_lambda, penalty_share


def prob_at_least_one(lam: float) -> float:
    return 1.0 - math.exp(-lam)


def log_loss(probabilities: List[float], actuals: List[int]) -> float:
    total = 0.0
    for probability, actual in zip(probabilities, actuals):
        p = _clamp(probability, 0.001, 0.999)
        total += -(actual * math.log(p) + (1 - actual) * math.log(1.0 - p))
    return total / len(probabilities) if probabilities else 0.0


def brier_score(probabilities: List[float], actuals: List[int]) -> float:
    if not probabilities:
        return 0.0
    return sum((probability - actual) ** 2 for probability, actual in zip(probabilities, actuals)) / len(probabilities)


def probability_bins(results: List[dict]) -> List[dict]:
    bins = [
        (0.00, 0.05),
        (0.05, 0.10),
        (0.10, 0.15),
        (0.15, 0.20),
        (0.20, 0.25),
        (0.25, 0.30),
        (0.30, 0.40),
        (0.40, 0.50),
        (0.50, 1.01),
    ]

    rows = []
    model_rows = [row for row in results if row["method"] == "model"]
    for low, high in bins:
        bucket = [row for row in model_rows if low <= row["model_p_atgs"] < high]
        if len(bucket) < 20:
            continue
        predicted = _mean(row["model_p_atgs"] for row in bucket)
        actual = _mean(row["scored"] for row in bucket)
        rows.append(
            {
                "bin": f"{int(low * 100)}-{int((high if high < 1 else 1) * 100)}%",
                "n": len(bucket),
                "predicted": round(predicted, 4),
                "actual": round(actual, 4),
                "gap": round(actual - predicted, 4),
            }
        )
    return rows


def split_summary(results: List[dict], label: str, key_name: str, min_n: int = 30) -> List[dict]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for row in results:
        if row["method"] != "model":
            continue
        groups[str(row[key_name])].append(row)

    summary = []
    for group_name, rows in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(rows) < min_n:
            continue
        predicted = _mean(row["model_p_atgs"] for row in rows)
        actual = _mean(row["scored"] for row in rows)
        summary.append(
            {
                "section": label,
                "group": group_name,
                "n": len(rows),
                "predicted": round(predicted, 4),
                "actual": round(actual, 4),
                "gap": round(actual - predicted, 4),
            }
        )
    return summary


def run_backtest(rows: List[NormalizedRow]) -> tuple[List[dict], dict]:
    player_histories: Dict[str, PlayerHistory] = defaultdict(PlayerHistory)
    team_histories: Dict[str, TeamHistory] = defaultdict(TeamHistory)

    results: List[dict] = []
    stats = {
        "processed_rows": 0,
        "model_rows": 0,
        "fallback_rows": 0,
        "unknown_started_rows": 0,
        "team_attack_fallbacks": 0,
        "opponent_defense_fallbacks": 0,
        "team_matches_with_xg": 0,
        "team_matches_missing_xg": 0,
    }

    for match_date, date_group in groupby(rows, key=lambda row: row.match_date):
        date_rows = list(date_group)
        team_match_summaries: Dict[tuple[str, str, bool], dict] = {}
        grouped_team_rows: Dict[tuple[str, str, bool], List[NormalizedRow]] = defaultdict(list)

        for row in date_rows:
            if row.started is None:
                stats["unknown_started_rows"] += 1

            team_match_key = (row.team_key, row.opponent_key, row.is_home)
            grouped_team_rows[team_match_key].append(row)
            summary = team_match_summaries.setdefault(
                team_match_key,
                {
                    "team_npxg": None,
                    "team_xg": None,
                    "team_xga": None,
                    "team_penalties_attempted": 0,
                },
            )
            summary["team_penalties_attempted"] += row.penalties_attempted
            if row.team_xg is not None and summary["team_xg"] is None:
                summary["team_xg"] = row.team_xg
            if summary["team_xg"] is not None:
                summary["team_npxg"] = max(0.0, summary["team_xg"] - (summary["team_penalties_attempted"] * LEAGUE_AVG["penalty_conversion"]))
            if row.team_xga is not None and summary["team_xga"] is None:
                summary["team_xga"] = row.team_xga

        for (team_key, opponent_key, is_home), team_rows in grouped_team_rows.items():
            team_summary = team_histories[team_key].summary()
            opponent_summary = team_histories[opponent_key].summary()
            team_expected_npxg, attack_factor, opp_factor, attack_fallback, defense_fallback = build_team_expected_npxg(
                team_summary,
                opponent_summary,
                is_home,
            )
            if attack_fallback:
                stats["team_attack_fallbacks"] += len(team_rows)
            if defense_fallback:
                stats["opponent_defense_fallbacks"] += len(team_rows)

            player_predictions: List[dict] = []
            raw_share_total = 0.0
            for row in team_rows:
                player_recent = player_histories[row.player_id].summary(RECENT_WINDOW)
                player_long = player_histories[row.player_id].summary(LONG_WINDOW)
                expected_minutes = expected_minutes_from_summary(player_recent, row.started)
                fallback_propensity, _base_rate, method = build_player_propensity(
                    player_recent,
                    player_long,
                    row.position,
                    expected_minutes,
                )
                raw_share = build_player_raw_share(
                    player_recent,
                    team_summary,
                    expected_minutes,
                )
                penalty_lambda = 0.0
                penalty_share = 0.0
                if method == "model":
                    penalty_lambda, penalty_share = build_penalty_component(
                        player_recent,
                        player_long,
                        team_summary,
                        expected_minutes,
                    )
                player_predictions.append(
                    {
                        "row": row,
                        "expected_minutes": expected_minutes,
                        "raw_share": raw_share,
                        "fallback_propensity": fallback_propensity,
                        "method": method,
                        "penalty_lambda": penalty_lambda,
                        "penalty_share": penalty_share,
                    }
                )
                raw_share_total += raw_share

            if raw_share_total <= 0:
                fallback_total = sum(prediction["fallback_propensity"] for prediction in player_predictions)
                fallback_total = fallback_total if fallback_total > 0 else (float(len(player_predictions)) or 1.0)
                for prediction in player_predictions:
                    prediction["team_share"] = (
                        (prediction["fallback_propensity"] / fallback_total) * (1.0 - UNALLOCATED_SHARE_FLOOR)
                    )
            else:
                for prediction in player_predictions:
                    prediction["team_share"] = (
                        (prediction["raw_share"] / raw_share_total) * (1.0 - UNALLOCATED_SHARE_FLOOR)
                    )

            for prediction in player_predictions:
                row = prediction["row"]
                expected_minutes = prediction["expected_minutes"]
                team_share = prediction["team_share"]
                non_pen_lambda = team_expected_npxg * team_share
                penalty_lambda = prediction["penalty_lambda"]
                penalty_share = prediction["penalty_share"]
                total_lambda = max(0.001, non_pen_lambda + penalty_lambda)
                method = prediction["method"]
                if method == "model":
                    stats["model_rows"] += 1
                else:
                    stats["fallback_rows"] += 1

                position_group = coarse_position(row.position)
                minutes_band = (
                    "<30"
                    if expected_minutes < 30
                    else "30-59"
                    if expected_minutes < 60
                    else "60-79"
                    if expected_minutes < 80
                    else "80+"
                )

                results.append(
                    {
                        "season": row.season,
                        "match_date": row.match_date_str,
                        "player_id": row.player_id,
                        "player_name": row.player_name,
                        "team": row.team,
                        "opponent": row.opponent,
                        "position": row.position,
                        "position_group": position_group or "Unknown",
                        "confirmed_started": "" if row.started is None else int(row.started),
                        "expected_minutes": round(expected_minutes, 1),
                        "minutes_band": minutes_band,
                        "goals": row.goals,
                        "shots": row.shots,
                        "xg": round(row.xg, 4),
                        "npxg": round(row.npxg, 4),
                        "team_expected_npxg": round(team_expected_npxg, 4),
                        "team_share": round(team_share, 4),
                        "model_lambda": round(total_lambda, 4),
                        "model_p_atgs": round(prob_at_least_one(total_lambda), 4),
                        "model_fair_odds_atgs": round(1.0 / prob_at_least_one(total_lambda), 2)
                        if prob_at_least_one(total_lambda) > 0.01
                        else 99.0,
                        "non_pen_lambda": round(non_pen_lambda, 4),
                        "penalty_lambda": round(penalty_lambda, 4),
                        "penalty_share": round(penalty_share, 4),
                        "attack_factor": round(attack_factor, 4),
                        "opp_factor": round(opp_factor, 4),
                        "method": method,
                        "penalty_role": "primary" if penalty_share >= 0.5 else "secondary_or_none",
                        "scored": 1 if row.goals > 0 else 0,
                    }
                )
                stats["processed_rows"] += 1

        for row in date_rows:
            team_match = team_match_summaries[(row.team_key, row.opponent_key, row.is_home)]
            player_histories[row.player_id].add_match(
                {
                    "minutes": row.minutes,
                    "started": row.started,
                    "goals": row.goals,
                    "shots": row.shots,
                    "xg": row.xg,
                    "npxg": row.npxg,
                    "penalties_scored": row.penalties_scored,
                    "penalties_attempted": row.penalties_attempted,
                    "team_penalties_attempted": team_match["team_penalties_attempted"],
                }
            )

        for (team_key, _, _), summary in team_match_summaries.items():
            if summary["team_xg"] is not None:
                stats["team_matches_with_xg"] += 1
            else:
                stats["team_matches_missing_xg"] += 1
            team_histories[team_key].add_match(summary)

    return results, stats


def write_outputs(results: List[dict], stats: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)

    results_path = os.path.join(out_dir, "goalscorer-backtest-results.csv")
    with open(results_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    model_rows = [row for row in results if row["method"] == "model"]
    probabilities = [row["model_p_atgs"] for row in model_rows]
    actuals = [row["scored"] for row in model_rows]

    bins = probability_bins(results)
    bins_path = os.path.join(out_dir, "goalscorer-calibration-bins.csv")
    with open(bins_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["bin", "n", "predicted", "actual", "gap"])
        writer.writeheader()
        writer.writerows(bins)

    split_rows = []
    split_rows.extend(split_summary(results, "Position", "position_group"))
    split_rows.extend(split_summary(results, "Minutes band", "minutes_band"))
    split_rows.extend(split_summary(results, "Penalty role", "penalty_role"))

    report_path = os.path.join(out_dir, "goalscorer-calibration.txt")
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("Goalscorer Model Calibration Report\n")
        handle.write("=================================\n\n")
        handle.write(f"Processed rows:        {stats['processed_rows']:,}\n")
        handle.write(f"Model rows:            {stats['model_rows']:,}\n")
        handle.write(f"Fallback rows:         {stats['fallback_rows']:,}\n")
        handle.write(f"Unknown starters:      {stats['unknown_started_rows']:,}\n")
        handle.write(f"Team attack fallbacks: {stats['team_attack_fallbacks']:,}\n")
        handle.write(f"Opp defence fallbacks: {stats['opponent_defense_fallbacks']:,}\n")
        handle.write(f"Team matches with xG:  {stats['team_matches_with_xg']:,}\n")
        handle.write(f"Team matches missing xG: {stats['team_matches_missing_xg']:,}\n\n")

        if model_rows:
            handle.write(f"Predicted scoring rate: {_mean(probabilities):.4f}\n")
            handle.write(f"Actual scoring rate:    {_mean(actuals):.4f}\n")
            handle.write(f"Brier score:            {brier_score(probabilities, actuals):.5f}\n")
            handle.write(f"Log loss:               {log_loss(probabilities, actuals):.5f}\n\n")

        handle.write("Probability bins\n")
        handle.write("----------------\n")
        if bins:
            for row in bins:
                handle.write(
                    f"{row['bin']:>8}  n={row['n']:>4}  predicted={row['predicted']:.3f}  "
                    f"actual={row['actual']:.3f}  gap={row['gap']:+.3f}\n"
                )
        else:
            handle.write("Not enough model rows for calibration bins.\n")

        handle.write("\nSplit summaries\n")
        handle.write("---------------\n")
        if split_rows:
            current_section = ""
            for row in split_rows:
                if row["section"] != current_section:
                    current_section = row["section"]
                    handle.write(f"\n{current_section}\n")
                handle.write(
                    f"  {row['group']:<20} n={row['n']:>4}  predicted={row['predicted']:.3f}  "
                    f"actual={row['actual']:.3f}  gap={row['gap']:+.3f}\n"
                )
        else:
            handle.write("Not enough rows for split summaries.\n")

    print(f"  Saved: {results_path}")
    print(f"  Saved: {bins_path}")
    print(f"  Saved: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serie A goalscorer calibration model")
    parser.add_argument("--data", nargs="+", required=True, help="CSV files or globs for player match logs")
    parser.add_argument("--out-dir", default="data/goalscorer")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Goalscorer Model")
    print("=" * 64)

    rows = load_match_logs(args.data)
    if not rows:
        print("  No rows loaded.")
        raise SystemExit(1)

    print(f"  Normalized rows: {len(rows):,}")
    results, stats = run_backtest(rows)
    print(f"  Processed rows:  {stats['processed_rows']:,}")
    print(f"  Model rows:      {stats['model_rows']:,}")
    print(f"  Fallback rows:   {stats['fallback_rows']:,}")

    if not results:
        print("  No results produced.")
        raise SystemExit(1)

    write_outputs(results, stats, args.out_dir)
    print("\n  Done.\n")


if __name__ == "__main__":
    main()
