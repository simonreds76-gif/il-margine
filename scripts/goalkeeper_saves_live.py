#!/usr/bin/env python3
"""Shared prospective plumbing for the registered Goalkeeper Saves v1 lane.

The count model is frozen in ``gk-saves-v1-params.json``. This module only
reconstructs its registered live features, prices real Over lines and enforces
the confirmed-starting-goalkeeper gate.
"""

from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from football_counts import total_probs
from football_team_names import football_form_team_key


ROOT = Path(__file__).resolve().parents[1]
WINDOW = 20
DECAY = 0.93
MIN_HISTORY = 6
MIN_EDGE = 0.08


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def parse_day(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def normalize_person(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def person_match_score(left: Any, right: Any) -> int:
    a, b = normalize_person(left), normalize_person(right)
    if not a or not b:
        return 0
    if a == b:
        return 100
    a_parts, b_parts = a.split(), b.split()
    if a_parts[-1] == b_parts[-1] and a_parts[0][0] == b_parts[0][0]:
        return 80
    return 0


def league_key(value: Any) -> str:
    text = str(value or "").casefold()
    if "premier league" in text and "england" in text:
        return "epl"
    if "serie a" in text and "ital" in text:
        return "serie-a"
    if any(token in text for token in ("la liga", "laliga")) and "spain" in text:
        return "la-liga"
    if "bundesliga" in text and "german" in text:
        return "bundesliga"
    if "ligue 1" in text and "france" in text:
        return "ligue-1"
    return ""


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_team_histories(path: Path) -> dict[str, list[dict[str, str]]]:
    histories: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(path):
        key = football_form_team_key(row.get("team") or row.get("team_key"))
        if key and parse_day(row.get("date")):
            histories[key].append(row)
    for rows in histories.values():
        rows.sort(key=lambda item: str(item.get("date") or ""))
    return dict(histories)


def _weighted_rows(rows: Iterable[dict[str, str]]) -> list[tuple[dict[str, str], float]]:
    recent = list(rows)[-WINDOW:]
    return [
        (row, DECAY ** (len(recent) - 1 - index))
        for index, row in enumerate(recent)
    ]


def weighted_average(
    rows: Iterable[dict[str, str]],
    field: str,
    *,
    venue: str | None = None,
) -> float | None:
    values: list[tuple[float, float]] = []
    for row, weight in _weighted_rows(rows):
        if venue and str(row.get("venue") or "") != venue:
            continue
        value = parse_float(row.get(field))
        if value is not None:
            values.append((value, weight))
    denominator = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / denominator if denominator else None


def preferred_average(rows: list[dict[str, str]], field: str, venue: str) -> float | None:
    return weighted_average(rows, field, venue=venue) or weighted_average(rows, field)


def weighted_ratio(rows: list[dict[str, str]], numerator: str, denominator: str) -> float | None:
    top = 0.0
    bottom = 0.0
    seen = False
    for row, weight in _weighted_rows(rows):
        top_value = parse_float(row.get(numerator))
        bottom_value = parse_float(row.get(denominator))
        if top_value is None or bottom_value is None:
            continue
        top += top_value * weight
        bottom += bottom_value * weight
        seen = True
    return (top / bottom) if seen and bottom > 0 else None


def saves_ema(rows: list[dict[str, str]]) -> float | None:
    values: list[tuple[float, float]] = []
    for row, weight in _weighted_rows(rows):
        sot_against = parse_float(row.get("sot_against"))
        goals_against = parse_float(row.get("goals_against"))
        if sot_against is None or goals_against is None:
            continue
        actual = sot_against - goals_against
        if actual >= 0:
            values.append((actual, weight))
    denominator = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / denominator if denominator else None


def as_of_rows(rows: list[dict[str, str]], kickoff_day: date) -> list[dict[str, str]]:
    return [row for row in rows if (day := parse_day(row.get("date"))) is not None and day < kickoff_day]


def _log_positive(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    return math.log(value)


def devig_three_way(home: float, draw: float, away: float) -> tuple[float, float, float] | None:
    if min(home, draw, away) <= 1.0:
        return None
    raw = (1.0 / home, 1.0 / draw, 1.0 / away)
    total = sum(raw)
    return tuple(value / total for value in raw)  # type: ignore[return-value]


def build_features(
    *,
    histories: dict[str, list[dict[str, str]]],
    team: str,
    opponent: str,
    venue: str,
    kickoff_day: date,
    home_price: float,
    draw_price: float,
    away_price: float,
) -> tuple[tuple[float, ...] | None, list[str]]:
    blockers: list[str] = []
    team_rows = as_of_rows(histories.get(football_form_team_key(team), []), kickoff_day)
    opponent_rows = as_of_rows(histories.get(football_form_team_key(opponent), []), kickoff_day)
    if len(team_rows) < MIN_HISTORY or len(opponent_rows) < MIN_HISTORY:
        blockers.append("history_lt_6")

    opponent_venue = "away" if venue == "home" else "home"
    market = devig_three_way(home_price, draw_price, away_price)
    if market is None:
        blockers.append("missing_three_way_market")
        market_gap = None
    else:
        home_prob, _, away_prob = market
        team_prob, opponent_prob = (home_prob, away_prob) if venue == "home" else (away_prob, home_prob)
        market_gap = opponent_prob - team_prob

    raw_values = (
        preferred_average(opponent_rows, "sot_for", opponent_venue),
        preferred_average(team_rows, "sot_against", venue),
        preferred_average(opponent_rows, "shots_for", opponent_venue),
        preferred_average(team_rows, "shots_against", venue),
        market_gap,
        weighted_average(opponent_rows, "xg_for"),
        weighted_average(team_rows, "xg_against"),
        weighted_ratio(opponent_rows, "xg_for", "shots_for"),
        saves_ema(team_rows),
    )
    values = tuple(
        value if index == 4 else _log_positive(value)
        for index, value in enumerate(raw_values)
    )
    missing_indexes = [
        index
        for index, value in enumerate(values)
        if value is None or not math.isfinite(float(value))
    ]
    # Index 4 is the separately reason-coded contemporaneous 1X2 feature.
    # Do not mask that supply issue as a second registered-feature failure.
    if any(index != 4 for index in missing_indexes):
        blockers.append("missing_registered_feature")
    if missing_indexes:
        return None, sorted(set(blockers))
    return tuple(float(value) for value in values), sorted(set(blockers))


def predict_mean(params: dict[str, Any], features: tuple[float, ...], league: str, venue: str) -> float:
    centers = [float(value) for value in params["centers"]]
    scales = [float(value) for value in params["scales"]]
    beta = [float(value) for value in params["beta"]]
    standardized = [
        (value - center) / scale
        for value, center, scale in zip(features, centers, scales)
    ]
    linear = beta[0] + sum(weight * value for weight, value in zip(beta[1:], standardized))
    baseline = float((params.get("league_venue_means") or {}).get(f"{league}|{venue}", params["fallback_mean"]))
    return max(0.1, min(12.0, baseline * math.exp(linear)))


def price_side(side: str, line: float, price: float, mean: float, alpha: float) -> dict[str, float]:
    p_over, p_under, p_push = total_probs(
        line,
        mean,
        distribution="negative_binomial",
        alpha=alpha,
    )
    selected_probability = p_over if side.casefold() == "over" else p_under
    expected_return = (selected_probability * price) + p_push
    fair_odds = (1.0 - p_push) / selected_probability if selected_probability > 0 else float("inf")
    return {
        "model_probability": selected_probability,
        "push_probability": p_push,
        "fair_odds": fair_odds,
        "edge": expected_return - 1.0,
    }


def price_over(line: float, price: float, mean: float, alpha: float) -> dict[str, float]:
    return price_side("over", line, price, mean, alpha)


def load_lineup_index(paths: Iterable[Path]) -> dict[tuple[str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        for fixture in payload.get("fixtures") or []:
            day = str(fixture.get("match_date") or "")[:10]
            home = football_form_team_key(fixture.get("home_team"))
            away = football_form_team_key(fixture.get("away_team"))
            if day and home and away:
                index[(day, home, away)] = fixture
    return index


def resolve_goalkeeper(
    fixture: dict[str, Any] | None,
    player: str,
) -> tuple[str, str, str]:
    if not fixture:
        return "", "missing_lineup", ""
    matches: list[tuple[int, str, str]] = []
    for side in ("home", "away"):
        for starter in fixture.get(f"{side}_starters") or []:
            if str(starter.get("role_group") or "").upper() != "GK":
                continue
            score = person_match_score(player, starter.get("name"))
            if score:
                matches.append((score, side, str(starter.get("name") or "")))
    if not matches:
        return "", "player_not_starting_goalkeeper", ""
    matches.sort(reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        return "", "ambiguous_goalkeeper_identity", ""
    lineup_type = str(fixture.get("lineup_type") or "").strip().lower()
    status = "confirmed_starter" if lineup_type in {"standard", "confirmed"} else "predicted_starter"
    return matches[0][1], status, matches[0][2]
