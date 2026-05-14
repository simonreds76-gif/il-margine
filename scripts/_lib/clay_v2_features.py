"""Offline feature utilities for the clay ML v2 research model.

The historical backtest CSVs are winner-first: ``player1`` is always the
actual winner. A model trained directly on that ordering would have an all-1
label. The v2 builder therefore creates a deterministic pre-match orientation:
for each fixture, player A is assigned to the winner or loser by a stable hash.
All probabilities and odds are then transformed into player-A space.
"""

from __future__ import annotations

import csv
import hashlib
import math
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .clay_v2_cohort_map import tournament_cohort


ROOT = Path(__file__).resolve().parents[2]
BACKTEST_DIR = ROOT / "data" / "backtest"
ONCOURT_DIR = ROOT / "data" / "oncourt"

FEATURE_COLUMNS = [
    "round_ord",
    "series_ord",
    "tournament_cohort",
    "month_of_year",
    "days_into_year",
    "age_a",
    "age_b",
    "age_diff",
    "lefty_a",
    "lefty_b",
    "lefty_vs_righty",
    "atp_rank_a",
    "atp_rank_b",
    "log_rank_a",
    "log_rank_b",
    "log_rank_diff",
    "clay_points_a",
    "clay_points_b",
    "log_clay_points_diff",
    "clay_career_winrate_a",
    "clay_career_matches_a",
    "clay_l52w_winrate_a",
    "clay_l52w_matches_a",
    "clay_l12w_winrate_a",
    "workload_l14_a",
    "workload_l30_a",
    "days_since_last_match_a",
    "clay_career_winrate_b",
    "clay_career_matches_b",
    "clay_l52w_winrate_b",
    "clay_l52w_matches_b",
    "clay_l12w_winrate_b",
    "workload_l14_b",
    "workload_l30_b",
    "days_since_last_match_b",
    "clay_l52w_first_serve_pct_a",
    "clay_l52w_first_serve_won_pct_a",
    "clay_l52w_second_serve_won_pct_a",
    "clay_l52w_return_pts_won_pct_a",
    "clay_l52w_first_serve_pct_b",
    "clay_l52w_first_serve_won_pct_b",
    "clay_l52w_second_serve_won_pct_b",
    "clay_l52w_return_pts_won_pct_b",
    "h2h_clay_total",
    "h2h_clay_a_minus_b",
    "pinnacle_prob_novig",
    "our_prob_raw",
]

KEY_COLUMNS = [
    "source_year",
    "date",
    "tournament",
    "surface",
    "round",
    "series",
    "winner_name",
    "loser_name",
    "winner_id",
    "loser_id",
    "player_a",
    "player_b",
    "player_a_id",
    "player_b_id",
    "a_is_winner",
    "label_player_a_win",
    "pinnacle_odds_a",
    "pinnacle_odds_b",
    "score",
]

OUTPUT_COLUMNS = KEY_COLUMNS + FEATURE_COLUMNS


@dataclass(frozen=True)
class PlayerInfo:
    birthdate: date | None
    atp_rank: float
    clay_points: float
    lefty: bool


@dataclass(frozen=True)
class MatchEvent:
    date_ord: int
    won: bool


@dataclass(frozen=True)
class StatEvent:
    date_ord: int
    fs: float
    fsof: float
    w1s: float
    w1sof: float
    w2s: float
    w2sof: float
    rpw: float
    rpwof: float


@dataclass
class HistoryIndex:
    players: dict[int, PlayerInfo]
    any_matches: dict[int, list[MatchEvent]]
    clay_matches: dict[int, list[MatchEvent]]
    clay_stats: dict[int, list[StatEvent]]
    h2h_clay: dict[tuple[int, int], list[tuple[int, int]]]


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_float(value: Any, default: float = math.nan) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    val = parse_float(value, math.nan)
    if math.isnan(val):
        return default
    return int(val)


def safe_rate(num: float, den: float, prior: float) -> float:
    if den <= 0:
        return prior
    return float(num / den)


def round_ord(round_name: str) -> int:
    text = (round_name or "").strip().lower()
    if "1st" in text or "round of 128" in text or "r128" in text:
        return 1
    if "2nd" in text or "round of 64" in text or "r64" in text:
        return 2
    if "3rd" in text or "round of 32" in text or "r32" in text:
        return 3
    if "4th" in text or "round of 16" in text or "r16" in text:
        return 4
    if "quarter" in text or text == "qf":
        return 5
    if "semi" in text or text == "sf":
        return 6
    if "final" in text:
        return 7
    return 0


def series_ord(series: str) -> int:
    text = (series or "").strip().lower().replace(" ", "")
    if text == "atp250":
        return 1
    if text == "atp500":
        return 2
    if text in {"masters1000", "atp1000"}:
        return 3
    if text == "grandslam":
        return 4
    return 0


def deterministic_a_is_winner(row: dict[str, Any]) -> bool:
    payload = "|".join(
        [
            str(row.get("date", "")),
            str(row.get("tournament", "")),
            str(row.get("player1_id", "")),
            str(row.get("player2_id", "")),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return digest[0] % 2 == 0


def load_lefties(path: Path = ONCOURT_DIR / "left_handed_players.csv") -> set[int]:
    if not path.exists():
        return set()
    ids: set[int] = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            player_id = parse_int(row.get("player_id"), 0)
            if player_id:
                ids.add(player_id)
    return ids


def load_players(path: Path = ONCOURT_DIR / "players_atp.csv") -> dict[int, PlayerInfo]:
    lefties = load_lefties()
    players: dict[int, PlayerInfo] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            player_id = parse_int(row.get("id"), 0)
            if not player_id:
                continue
            players[player_id] = PlayerInfo(
                birthdate=parse_date(row.get("birthdate")),
                atp_rank=parse_float(row.get("atp_rank"), 999.0),
                clay_points=parse_float(row.get("clay_points"), 0.0),
                lefty=player_id in lefties,
            )
    return players


def load_tour_courts(path: Path = ONCOURT_DIR / "tours_atp.csv") -> dict[int, int]:
    tours: dict[int, int] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tour_id = parse_int(row.get("id"), 0)
            if tour_id:
                tours[tour_id] = parse_int(row.get("court_id"), 0)
    return tours


def build_history_index() -> HistoryIndex:
    players = load_players()
    tour_courts = load_tour_courts()
    any_matches: dict[int, list[MatchEvent]] = {}
    clay_matches: dict[int, list[MatchEvent]] = {}
    h2h_clay: dict[tuple[int, int], list[tuple[int, int]]] = {}
    clay_game_lookup: dict[tuple[int, int, int, int], int] = {}

    games_path = ONCOURT_DIR / "games_atp.csv"
    with games_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            match_date = parse_date(row.get("date"))
            if match_date is None:
                continue
            date_ord = match_date.toordinal()
            winner_id = parse_int(row.get("winner_id"), 0)
            loser_id = parse_int(row.get("loser_id"), 0)
            tour_id = parse_int(row.get("tour_id"), 0)
            round_id = parse_int(row.get("round_id"), 0)
            if not winner_id or not loser_id:
                continue
            any_matches.setdefault(winner_id, []).append(MatchEvent(date_ord, True))
            any_matches.setdefault(loser_id, []).append(MatchEvent(date_ord, False))
            if tour_courts.get(tour_id) == 2:
                clay_matches.setdefault(winner_id, []).append(MatchEvent(date_ord, True))
                clay_matches.setdefault(loser_id, []).append(MatchEvent(date_ord, False))
                pair = tuple(sorted((winner_id, loser_id)))
                h2h_clay.setdefault(pair, []).append((date_ord, winner_id))
                clay_game_lookup[(winner_id, loser_id, tour_id, round_id)] = date_ord

    clay_stats: dict[int, list[StatEvent]] = {}
    stats_path = ONCOURT_DIR / "stat_atp.csv"
    with stats_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            winner_id = parse_int(row.get("winner_id"), 0)
            loser_id = parse_int(row.get("loser_id"), 0)
            tour_id = parse_int(row.get("tour_id"), 0)
            round_id = parse_int(row.get("round_id"), 0)
            date_ord = clay_game_lookup.get((winner_id, loser_id, tour_id, round_id))
            if date_ord is None:
                continue
            clay_stats.setdefault(winner_id, []).append(
                StatEvent(
                    date_ord,
                    parse_float(row.get("w_fs"), 0.0),
                    parse_float(row.get("w_fsof"), 0.0),
                    parse_float(row.get("w_w1s"), 0.0),
                    parse_float(row.get("w_w1sof"), 0.0),
                    parse_float(row.get("w_w2s"), 0.0),
                    parse_float(row.get("w_w2sof"), 0.0),
                    parse_float(row.get("w_rpw"), 0.0),
                    parse_float(row.get("w_rpwof"), 0.0),
                )
            )
            clay_stats.setdefault(loser_id, []).append(
                StatEvent(
                    date_ord,
                    parse_float(row.get("l_fs"), 0.0),
                    parse_float(row.get("l_fsof"), 0.0),
                    parse_float(row.get("l_w1s"), 0.0),
                    parse_float(row.get("l_w1sof"), 0.0),
                    parse_float(row.get("l_w2s"), 0.0),
                    parse_float(row.get("l_w2sof"), 0.0),
                    parse_float(row.get("l_rpw"), 0.0),
                    parse_float(row.get("l_rpwof"), 0.0),
                )
            )

    for container in (any_matches, clay_matches, clay_stats):
        for rows in container.values():
            rows.sort(key=lambda item: item.date_ord)
    for rows in h2h_clay.values():
        rows.sort(key=lambda item: item[0])

    return HistoryIndex(
        players=players,
        any_matches=any_matches,
        clay_matches=clay_matches,
        clay_stats=clay_stats,
        h2h_clay=h2h_clay,
    )


def _events_before(events: list[MatchEvent], fixture_ord: int, earliest_ord: int | None = None) -> list[MatchEvent]:
    date_ords = [item.date_ord for item in events]
    end = bisect_left(date_ords, fixture_ord)
    start = 0 if earliest_ord is None else bisect_left(date_ords, earliest_ord)
    selected = events[start:end]
    if selected and selected[-1].date_ord >= fixture_ord:
        raise AssertionError("rolling match feature leaked a future match")
    return selected


def _stats_before(events: list[StatEvent], fixture_ord: int, earliest_ord: int) -> list[StatEvent]:
    date_ords = [item.date_ord for item in events]
    start = bisect_left(date_ords, earliest_ord)
    end = bisect_left(date_ords, fixture_ord)
    selected = events[start:end]
    if selected and selected[-1].date_ord >= fixture_ord:
        raise AssertionError("rolling stat feature leaked a future match")
    return selected


def player_form_features(index: HistoryIndex, player_id: int, fixture_ord: int) -> dict[str, float]:
    clay = index.clay_matches.get(player_id, [])
    any_surface = index.any_matches.get(player_id, [])
    career = _events_before(clay, fixture_ord)
    l52 = _events_before(clay, fixture_ord, fixture_ord - 364)
    l12 = _events_before(clay, fixture_ord, fixture_ord - 84)
    recent_14 = _events_before(any_surface, fixture_ord, fixture_ord - 14)
    recent_30 = _events_before(any_surface, fixture_ord, fixture_ord - 30)
    prior_any = _events_before(any_surface, fixture_ord)
    if prior_any:
        days_since = min(60, fixture_ord - prior_any[-1].date_ord)
    else:
        days_since = 60

    career_n = len(career)
    l52_n = len(l52)
    l12_n = len(l12)
    return {
        "clay_career_winrate": (sum(1 for item in career if item.won) / career_n) if career_n else 0.5,
        "clay_career_matches": float(career_n),
        "clay_l52w_winrate": (sum(1 for item in l52 if item.won) / l52_n) if l52_n >= 5 else 0.5,
        "clay_l52w_matches": float(l52_n),
        "clay_l12w_winrate": (sum(1 for item in l12 if item.won) / l12_n) if l12_n >= 3 else 0.5,
        "workload_l14": float(len(recent_14)),
        "workload_l30": float(len(recent_30)),
        "days_since_last_match": float(days_since),
    }


def player_stat_features(index: HistoryIndex, player_id: int, fixture_ord: int) -> dict[str, float]:
    events = _stats_before(index.clay_stats.get(player_id, []), fixture_ord, fixture_ord - 364)
    fs = sum(item.fs for item in events)
    fsof = sum(item.fsof for item in events)
    w1s = sum(item.w1s for item in events)
    w1sof = sum(item.w1sof for item in events)
    w2s = sum(item.w2s for item in events)
    w2sof = sum(item.w2sof for item in events)
    rpw = sum(item.rpw for item in events)
    rpwof = sum(item.rpwof for item in events)
    return {
        "clay_l52w_first_serve_pct": safe_rate(fs, fsof, 0.60),
        "clay_l52w_first_serve_won_pct": safe_rate(w1s, w1sof, 0.60),
        "clay_l52w_second_serve_won_pct": safe_rate(w2s, w2sof, 0.50),
        "clay_l52w_return_pts_won_pct": safe_rate(rpw, rpwof, 0.40),
    }


def h2h_features(index: HistoryIndex, player_a_id: int, player_b_id: int, fixture_ord: int) -> dict[str, float]:
    pair = tuple(sorted((player_a_id, player_b_id)))
    rows = index.h2h_clay.get(pair, [])
    prior = [item for item in rows if item[0] < fixture_ord]
    if prior and max(item[0] for item in prior) >= fixture_ord:
        raise AssertionError("h2h feature leaked a future match")
    a_wins = sum(1 for _, winner_id in prior if winner_id == player_a_id)
    b_wins = len(prior) - a_wins
    return {
        "h2h_clay_total": float(len(prior)),
        "h2h_clay_a_minus_b": float(a_wins - b_wins),
    }


def age_years(info: PlayerInfo | None, fixture_date: date) -> float:
    if info is None or info.birthdate is None:
        return 27.0
    return max(14.0, min(50.0, (fixture_date - info.birthdate).days / 365.25))


def player_info(index: HistoryIndex, player_id: int) -> PlayerInfo:
    return index.players.get(player_id, PlayerInfo(None, 999.0, 0.0, False))


def build_feature_row(source_row: dict[str, Any], index: HistoryIndex) -> dict[str, Any] | None:
    if (source_row.get("surface") or "").strip().lower() != "clay":
        return None
    fixture_date = parse_date(source_row.get("date"))
    if fixture_date is None:
        return None

    winner_name = str(source_row.get("player1") or "").strip()
    loser_name = str(source_row.get("player2") or "").strip()
    actual_winner = str(source_row.get("actual_winner") or "").strip()
    if actual_winner != winner_name:
        raise ValueError(
            f"Expected winner-first backtest row for {source_row.get('date')} "
            f"{winner_name} vs {loser_name}; actual_winner={actual_winner!r}"
        )
    winner_id = parse_int(source_row.get("player1_id"), 0)
    loser_id = parse_int(source_row.get("player2_id"), 0)
    if not winner_id or not loser_id:
        return None

    a_is_winner = deterministic_a_is_winner(source_row)
    player_a_id = winner_id if a_is_winner else loser_id
    player_b_id = loser_id if a_is_winner else winner_id
    player_a = winner_name if a_is_winner else loser_name
    player_b = loser_name if a_is_winner else winner_name
    label = 1 if a_is_winner else 0

    pin_winner = parse_float(source_row.get("pinnacle_prob_novig"), math.nan)
    raw_winner = parse_float(source_row.get("our_prob_raw"), math.nan)
    if math.isnan(pin_winner) or math.isnan(raw_winner):
        return None
    pin_a = pin_winner if a_is_winner else 1.0 - pin_winner
    raw_a = raw_winner if a_is_winner else 1.0 - raw_winner

    odds_winner = parse_float(source_row.get("pinnacle_odds"), math.nan)
    odds_loser = parse_float(source_row.get("pinnacle_odds_loser"), math.nan)
    if math.isnan(odds_winner) or math.isnan(odds_loser):
        return None
    odds_a = odds_winner if a_is_winner else odds_loser
    odds_b = odds_loser if a_is_winner else odds_winner

    fixture_ord = fixture_date.toordinal()
    info_a = player_info(index, player_a_id)
    info_b = player_info(index, player_b_id)
    age_a = age_years(info_a, fixture_date)
    age_b = age_years(info_b, fixture_date)
    rank_a = info_a.atp_rank if not math.isnan(info_a.atp_rank) and info_a.atp_rank > 0 else 999.0
    rank_b = info_b.atp_rank if not math.isnan(info_b.atp_rank) and info_b.atp_rank > 0 else 999.0
    clay_points_a = info_a.clay_points if not math.isnan(info_a.clay_points) and info_a.clay_points > 0 else 0.0
    clay_points_b = info_b.clay_points if not math.isnan(info_b.clay_points) and info_b.clay_points > 0 else 0.0
    lefty_a = 1.0 if info_a.lefty else 0.0
    lefty_b = 1.0 if info_b.lefty else 0.0

    form_a = player_form_features(index, player_a_id, fixture_ord)
    form_b = player_form_features(index, player_b_id, fixture_ord)
    stat_a = player_stat_features(index, player_a_id, fixture_ord)
    stat_b = player_stat_features(index, player_b_id, fixture_ord)
    h2h = h2h_features(index, player_a_id, player_b_id, fixture_ord)

    row: dict[str, Any] = {
        "source_year": fixture_date.year,
        "date": fixture_date.isoformat(),
        "tournament": source_row.get("tournament", ""),
        "surface": "Clay",
        "round": source_row.get("round", ""),
        "series": source_row.get("series", ""),
        "winner_name": winner_name,
        "loser_name": loser_name,
        "winner_id": winner_id,
        "loser_id": loser_id,
        "player_a": player_a,
        "player_b": player_b,
        "player_a_id": player_a_id,
        "player_b_id": player_b_id,
        "a_is_winner": int(a_is_winner),
        "label_player_a_win": label,
        "pinnacle_odds_a": odds_a,
        "pinnacle_odds_b": odds_b,
        "score": source_row.get("score", ""),
        "round_ord": round_ord(str(source_row.get("round") or "")),
        "series_ord": series_ord(str(source_row.get("series") or "")),
        "tournament_cohort": tournament_cohort(str(source_row.get("tournament") or "")),
        "month_of_year": fixture_date.month,
        "days_into_year": fixture_date.timetuple().tm_yday,
        "age_a": age_a,
        "age_b": age_b,
        "age_diff": age_a - age_b,
        "lefty_a": lefty_a,
        "lefty_b": lefty_b,
        "lefty_vs_righty": 1.0 if bool(lefty_a) ^ bool(lefty_b) else 0.0,
        "atp_rank_a": rank_a,
        "atp_rank_b": rank_b,
        "log_rank_a": math.log1p(rank_a),
        "log_rank_b": math.log1p(rank_b),
        "log_rank_diff": math.log1p(rank_a) - math.log1p(rank_b),
        "clay_points_a": clay_points_a,
        "clay_points_b": clay_points_b,
        "log_clay_points_diff": math.log1p(clay_points_a) - math.log1p(clay_points_b),
        "pinnacle_prob_novig": pin_a,
        "our_prob_raw": raw_a,
    }
    for key, value in form_a.items():
        row[f"{key}_a"] = value
    for key, value in form_b.items():
        row[f"{key}_b"] = value
    for key, value in stat_a.items():
        row[f"{key}_a"] = value
    for key, value in stat_b.items():
        row[f"{key}_b"] = value
    row.update(h2h)

    missing = [col for col in OUTPUT_COLUMNS if col not in row]
    if missing:
        raise AssertionError(f"feature builder missed columns: {missing}")
    return {col: row[col] for col in OUTPUT_COLUMNS}


def load_backtest_rows(years: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year in years:
        path = BACKTEST_DIR / f"backtest-results-{year}.csv"
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows.extend(dict(row) for row in csv.DictReader(f))
    return rows
