#!/usr/bin/env python3
"""Measure the evidence required to reactivate the Assist Value lane.

This runner is deliberately research-only. It never publishes picks or mutates
the prospective ledger. The historical model is evaluated causally: every
feature for a player-match is built only from matches on earlier dates.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import runpy
import statistics
from collections import defaultdict, deque
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_GLOB = "data/goalscorer/*-player-match-logs-20*.csv"
DEFAULT_RESULTS_DIR = ROOT / "data" / "goalscorer" / "match-results"
DEFAULT_MARKET = ROOT / "data" / "assist-value" / "assist-value-shadow-signals.csv"
DEFAULT_PROSPECTIVE = ROOT / "data" / "assist-value" / "research" / "assist-value-v1-prospective.csv"
DEFAULT_OUT_DIR = ROOT / "data" / "assist-value" / "research"

TRAIN_SEASON = "2023-2024"
VALIDATION_SEASON = "2024-2025"
TEST_SEASON = "2025-2026"
MIN_HISTORY_MINUTES = 450.0
PLAYER_SHRINK_MINUTES = 900.0
MAX_PLAYER_MATCHES = 40
TEAM_RECENT_MATCHES = 8

FIXTURE_TEAM_ALIASES = {
    "1 fc koln": "cologne",
    "fc cologne": "cologne",
    "koln": "cologne",
    "bayern munchen": "bayern munich",
    "borussia monchengladbach": "gladbach",
    "borussia m gladbach": "gladbach",
    "inter milano": "inter",
    "paris saint germain": "psg",
    "st pauli": "st pauli",
}


def _model_helpers() -> dict:
    return runpy.run_path(str(ROOT / "scripts" / "build-assist-value-model.py"), run_name="assist_value_model")


MODEL_HELPERS = _model_helpers()
norm_text = MODEL_HELPERS["norm_text"]
base_team_key = MODEL_HELPERS["team_key"]
player_prior = MODEL_HELPERS["player_prior"]
LEAGUE_AVG_XG = MODEL_HELPERS["LEAGUE_AVG_XG"]


def canonical_team(value: str) -> str:
    key = base_team_key(value)
    return FIXTURE_TEAM_ALIASES.get(key, key)


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value or "").replace(",", "").strip())
    except ValueError:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _logit(value: float) -> float:
    p = _clamp(value, 1e-6, 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def fit_platt(probabilities: list[float], outcomes: list[int]) -> tuple[float, float]:
    """Fit p_cal = sigmoid(a * logit(p_raw) + b) with mild ridge stability."""
    if len(probabilities) != len(outcomes) or len(probabilities) < 20:
        return 1.0, 0.0
    xs = [_logit(value) for value in probabilities]
    a, b = 1.0, 0.0
    ridge = 1e-3
    for _ in range(60):
        g_a = ridge * (a - 1.0)
        g_b = ridge * b
        h_aa = ridge
        h_ab = 0.0
        h_bb = ridge
        for x, y in zip(xs, outcomes):
            q = _sigmoid(a * x + b)
            error = q - y
            weight = max(q * (1.0 - q), 1e-8)
            g_a += error * x
            g_b += error
            h_aa += weight * x * x
            h_ab += weight * x
            h_bb += weight
        determinant = h_aa * h_bb - h_ab * h_ab
        if abs(determinant) < 1e-12:
            break
        delta_a = (h_bb * g_a - h_ab * g_b) / determinant
        delta_b = (-h_ab * g_a + h_aa * g_b) / determinant
        a -= delta_a
        b -= delta_b
        if max(abs(delta_a), abs(delta_b)) < 1e-8:
            break
    return _clamp(a, 0.05, 5.0), _clamp(b, -6.0, 6.0)


def apply_platt(probability: float, a: float, b: float) -> float:
    return _clamp(_sigmoid(a * _logit(probability) + b), 1e-6, 1.0 - 1e-6)


def probability_metrics(probabilities: list[float], outcomes: list[int]) -> dict[str, float | int]:
    if not probabilities:
        return {"n": 0, "positives": 0, "prevalence": 0.0, "mean_probability": 0.0, "brier": 0.0, "log_loss": 0.0, "ece": 0.0}
    n = len(probabilities)
    positives = sum(outcomes)
    clipped = [_clamp(value, 1e-9, 1.0 - 1e-9) for value in probabilities]
    brier = sum((p - y) ** 2 for p, y in zip(clipped, outcomes)) / n
    log_loss = -sum(y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in zip(clipped, outcomes)) / n
    ranked = sorted(zip(clipped, outcomes), key=lambda item: item[0])
    ece = 0.0
    for start in range(0, n, max(1, math.ceil(n / 10))):
        bucket = ranked[start : start + max(1, math.ceil(n / 10))]
        mean_p = sum(item[0] for item in bucket) / len(bucket)
        mean_y = sum(item[1] for item in bucket) / len(bucket)
        ece += len(bucket) / n * abs(mean_p - mean_y)
    return {
        "n": n,
        "positives": positives,
        "prevalence": positives / n,
        "mean_probability": sum(clipped) / n,
        "brier": brier,
        "log_loss": log_loss,
        "ece": ece,
    }


def _league_from_path(path: Path) -> str:
    return path.name.split("-player-match-logs-", 1)[0]


def load_player_logs(patterns: Iterable[str]) -> list[dict]:
    rows: list[dict] = []
    seen_paths: set[Path] = set()
    for pattern in patterns:
        full_pattern = str(ROOT / pattern) if not Path(pattern).is_absolute() else pattern
        for raw_path in sorted(glob.glob(full_pattern)):
            path = Path(raw_path).resolve()
            if path in seen_paths or "2026-2027" in path.name:
                continue
            seen_paths.add(path)
            league = _league_from_path(path)
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    match_date = str(row.get("match_date") or "")[:10]
                    if not match_date:
                        continue
                    rows.append(
                        {
                            "league": league,
                            "season": str(row.get("season") or ""),
                            "match_date": match_date,
                            "team": canonical_team(str(row.get("team") or "")),
                            "opponent": canonical_team(str(row.get("opponent") or "")),
                            "player_id": str(row.get("player_id") or "").strip(),
                            "player_name": str(row.get("player_name") or "").strip(),
                            "player_key": norm_text(str(row.get("player_name") or "")),
                            "position": str(row.get("position") or "Unknown"),
                            "minutes": _float(row.get("minutes")),
                            "assists": _float(row.get("assists")),
                            "xa": _float(row.get("xa")),
                            "team_xg": _float(row.get("team_xg")),
                            "team_xga": _float(row.get("team_xga")),
                        }
                    )
    return rows


def _player_state_key(row: dict) -> tuple[str, str]:
    identity = row["player_id"] or row["player_key"]
    return row["league"], identity


def _team_context_scale(team_history: dict, league: str, team: str, opponent: str) -> float:
    league_average = LEAGUE_AVG_XG.get(league, 1.35)
    team_recent = list(team_history.get((league, team), []))[-TEAM_RECENT_MATCHES:]
    opponent_recent = list(team_history.get((league, opponent), []))[-TEAM_RECENT_MATCHES:]
    team_xg = sum(item["team_xg"] for item in team_recent) / len(team_recent) if team_recent else league_average
    opponent_xga = sum(item["team_xga"] for item in opponent_recent) / len(opponent_recent) if opponent_recent else league_average
    attack = _clamp(team_xg / league_average, 0.65, 1.45)
    defence = _clamp(opponent_xga / league_average, 0.70, 1.40)
    return math.sqrt(attack * defence)


def build_walk_forward_predictions(log_rows: list[dict]) -> list[dict]:
    by_date: dict[str, list[dict]] = defaultdict(list)
    for row in log_rows:
        by_date[row["match_date"]].append(row)

    player_history: dict[tuple[str, str], deque] = defaultdict(lambda: deque(maxlen=MAX_PLAYER_MATCHES))
    team_history: dict[tuple[str, str], deque] = defaultdict(lambda: deque(maxlen=TEAM_RECENT_MATCHES))
    predictions: list[dict] = []

    for match_date in sorted(by_date):
        daily_rows = by_date[match_date]
        for row in daily_rows:
            if row["minutes"] <= 0:
                continue
            history = list(player_history[_player_state_key(row)])
            history_minutes = sum(item["minutes"] for item in history)
            if len(history) < 3 or history_minutes < MIN_HISTORY_MINUTES:
                continue

            recent_five = [item["minutes"] for item in history[-5:] if item["minutes"] > 0]
            recent_eight = [item["minutes"] for item in history[-8:] if item["minutes"] > 0]
            expected_median_five = statistics.median(recent_five) if recent_five else 68.0
            expected_mean_eight = sum(recent_eight) / len(recent_eight) if recent_eight else 68.0
            expected_median_five = _clamp(expected_median_five, 15.0, 90.0)
            expected_mean_eight = _clamp(expected_mean_eight, 15.0, 90.0)

            position = str(history[-1].get("position") or row["position"] or "Unknown")
            prior = player_prior(position)
            assists = sum(item["assists"] for item in history)
            xa = sum(item["xa"] for item in history)
            raw_assist_rate = assists * 90.0 / history_minutes
            raw_xa_rate = xa * 90.0 / history_minutes
            shrink = history_minutes / (history_minutes + PLAYER_SHRINK_MINUTES)
            assist_rate = shrink * raw_assist_rate + (1.0 - shrink) * prior
            xa_rate = shrink * raw_xa_rate + (1.0 - shrink) * prior
            base_rate = 0.65 * xa_rate + 0.35 * assist_rate
            context_scale = _team_context_scale(team_history, row["league"], row["team"], row["opponent"])

            def probability(expected_minutes: float) -> float:
                lam = _clamp(base_rate * (expected_minutes / 90.0) * context_scale, 0.001, 0.45)
                return _clamp(1.0 - math.exp(-lam), 0.001, 0.45)

            predictions.append(
                {
                    "league": row["league"],
                    "season": row["season"],
                    "match_date": match_date,
                    "position": position.split(",")[0],
                    "actual_minutes": row["minutes"],
                    "expected_minutes_mean8": expected_mean_eight,
                    "expected_minutes_median5": expected_median_five,
                    "probability_mean8": probability(expected_mean_eight),
                    "probability_median5": probability(expected_median_five),
                    "outcome": 1 if row["assists"] > 0 else 0,
                }
            )

        team_updates: dict[tuple[str, str, str], dict] = {}
        for row in daily_rows:
            player_history[_player_state_key(row)].append(row)
            team_updates[(row["league"], row["team"], row["opponent"])] = row
        for (league, team, _opponent), row in team_updates.items():
            team_history[(league, team)].append({"team_xg": row["team_xg"], "team_xga": row["team_xga"]})

    return predictions


def _season_rows(rows: list[dict], season: str) -> list[dict]:
    return [row for row in rows if row["season"] == season]


def evaluate_backtest(predictions: list[dict]) -> tuple[dict, list[dict], tuple[float, float]]:
    train = _season_rows(predictions, TRAIN_SEASON)
    validation = _season_rows(predictions, VALIDATION_SEASON)
    test = _season_rows(predictions, TEST_SEASON)
    train_probs = [row["probability_median5"] for row in train]
    train_y = [row["outcome"] for row in train]
    val_probs = [row["probability_median5"] for row in validation]
    val_y = [row["outcome"] for row in validation]
    test_probs = [row["probability_median5"] for row in test]
    test_y = [row["outcome"] for row in test]

    val_a, val_b = fit_platt(train_probs, train_y)
    final_a, final_b = fit_platt(train_probs + val_probs, train_y + val_y)
    train_prior = sum(train_y + val_y) / max(1, len(train_y) + len(val_y))

    split_payload = {}
    segment_rows: list[dict] = []
    for label, rows, a, b in (
        ("train", train, val_a, val_b),
        ("validation", validation, val_a, val_b),
        ("test", test, final_a, final_b),
    ):
        raw_probs = [row["probability_median5"] for row in rows]
        outcomes = [row["outcome"] for row in rows]
        calibrated = [apply_platt(value, a, b) for value in raw_probs]
        split_payload[label] = {
            "raw": probability_metrics(raw_probs, outcomes),
            "calibrated": probability_metrics(calibrated, outcomes),
            "naive": probability_metrics([train_prior] * len(outcomes), outcomes),
        }
        for league in sorted({row["league"] for row in rows}):
            league_rows = [row for row in rows if row["league"] == league]
            league_probs = [apply_platt(row["probability_median5"], a, b) for row in league_rows]
            league_y = [row["outcome"] for row in league_rows]
            metrics = probability_metrics(league_probs, league_y)
            segment_rows.append({"split": label, "segment_type": "league", "segment": league, **metrics})

    minute_test = validation + test
    mean8_errors = [abs(row["expected_minutes_mean8"] - row["actual_minutes"]) for row in minute_test]
    median5_errors = [abs(row["expected_minutes_median5"] - row["actual_minutes"]) for row in minute_test]
    minute_payload = {
        "n": len(minute_test),
        "mean8_mae": sum(mean8_errors) / max(1, len(mean8_errors)),
        "median5_mae": sum(median5_errors) / max(1, len(median5_errors)),
        "selected": "median_last_5_appearances" if sum(median5_errors) <= sum(mean8_errors) else "mean_last_8_appearances",
    }

    test_cal = split_payload["test"]["calibrated"]
    test_naive = split_payload["test"]["naive"]
    backtest_pass = bool(
        test_cal["n"] >= 10_000
        and test_cal["brier"] < test_naive["brier"]
        and test_cal["ece"] <= 0.025
    )
    return (
        {
            "status": "PASS" if backtest_pass else "FAIL",
            "train_season": TRAIN_SEASON,
            "validation_season": VALIDATION_SEASON,
            "test_season": TEST_SEASON,
            "splits": split_payload,
            "minutes": minute_payload,
            "platt": {"a": final_a, "b": final_b, "fit_seasons": [TRAIN_SEASON, VALIDATION_SEASON]},
            "selection_note": "Outcome evaluation is conditional on the player making an appearance; non-runners are void in the market.",
        },
        segment_rows,
        (final_a, final_b),
    )


def _fixture_similarity(left: tuple[str, str], right: tuple[str, str]) -> float:
    direct = SequenceMatcher(None, left[0], right[0]).ratio() + SequenceMatcher(None, left[1], right[1]).ratio()
    reverse = SequenceMatcher(None, left[0], right[1]).ratio() + SequenceMatcher(None, left[1], right[0]).ratio()
    return max(direct, reverse) / 2.0


def _best_player_match(name: str, candidates: list[dict]) -> dict | None:
    key = norm_text(name)
    exact = next((row for row in candidates if row["player_key"] == key), None)
    if exact:
        return exact
    scored = sorted(
        ((SequenceMatcher(None, key, row["player_key"]).ratio(), row) for row in candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    return scored[0][1] if scored and scored[0][0] >= 0.82 else None


def settlement_validation(log_rows: list[dict], results_dir: Path) -> tuple[dict, list[dict]]:
    by_fixture_team: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    fixtures_by_date: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for row in log_rows:
        by_fixture_team[(row["league"], row["match_date"], row["team"], row["opponent"])].append(row)
        fixtures_by_date[(row["league"], row["match_date"])].add((row["team"], row["opponent"]))

    result_paths = sorted(results_dir.glob("*/fotmob-*.json")) if results_dir.exists() else []
    finished = 0
    instrumented_finished = 0
    complete = 0
    matched_fixtures = 0
    eligible_players = 0
    compared = 0
    agreements = 0
    positive_compared = 0
    positive_agreements = 0
    detail_rows: list[dict] = []

    for path in result_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not payload.get("status_finished"):
            continue
        finished += 1
        if "assist_data_complete" in payload:
            instrumented_finished += 1
        if not payload.get("assist_data_complete"):
            continue
        complete += 1
        league = str(payload.get("league") or path.parent.name)
        match_date = str(payload.get("match_date") or "")[:10]
        fotmob_pair = (canonical_team(str(payload.get("home_team") or "")), canonical_team(str(payload.get("away_team") or "")))
        candidates = list(fixtures_by_date.get((league, match_date), set()))
        fixture = next((pair for pair in candidates if set(pair) == set(fotmob_pair)), None)
        if fixture is None and candidates:
            score, best = max((_fixture_similarity(fotmob_pair, pair), pair) for pair in candidates)
            fixture = best if score >= 0.78 else None
        if fixture is None:
            continue
        matched_fixtures += 1

        for player in payload.get("players") or []:
            if not isinstance(player, dict) or "assists" not in player or int(player.get("minutes_played") or 0) <= 0:
                continue
            eligible_players += 1
            player_team = canonical_team(str(player.get("team") or ""))
            team = fixture[0] if SequenceMatcher(None, player_team, fixture[0]).ratio() >= SequenceMatcher(None, player_team, fixture[1]).ratio() else fixture[1]
            opponent = fixture[1] if team == fixture[0] else fixture[0]
            log_candidates = by_fixture_team.get((league, match_date, team, opponent), [])
            matched = _best_player_match(str(player.get("name") or ""), log_candidates)
            if matched is None:
                continue
            compared += 1
            fotmob_assists = int(player.get("assists") or 0)
            log_assists = int(matched["assists"])
            agree = fotmob_assists == log_assists
            agreements += int(agree)
            positive = fotmob_assists > 0 or log_assists > 0
            positive_compared += int(positive)
            positive_agreements += int(positive and agree)
            detail_rows.append(
                {
                    "league": league,
                    "match_date": match_date,
                    "home_team": payload.get("home_team", ""),
                    "away_team": payload.get("away_team", ""),
                    "fotmob_player": player.get("name", ""),
                    "log_player": matched["player_name"],
                    "fotmob_assists": fotmob_assists,
                    "log_assists": log_assists,
                    "agreement": "true" if agree else "false",
                }
            )

    agreement_rate = agreements / compared if compared else 0.0
    positive_rate = positive_agreements / positive_compared if positive_compared else 0.0
    complete_rate = complete / instrumented_finished if instrumented_finished else 0.0
    player_coverage = compared / eligible_players if eligible_players else 0.0
    fixture_coverage = matched_fixtures / complete if complete else 0.0
    extraction_pass = compared >= 200 and positive_compared >= 50 and agreement_rate >= 0.97 and positive_rate >= 0.95
    # Legacy files captured before completeness metadata existed are not evidence
    # of a failed extractor. Unmatched players remain pending in settlement.
    operational_pass = (
        instrumented_finished >= 50
        and complete_rate >= 0.95
        and fixture_coverage >= 0.95
        and player_coverage >= 0.90
    )
    return (
        {
            "status": "PASS" if extraction_pass and operational_pass else "FAIL",
            "extraction_status": "PASS" if extraction_pass else "FAIL",
            "operational_status": "PASS" if operational_pass else "FAIL",
            "result_files": len(result_paths),
            "finished_matches": finished,
            "instrumented_finished_matches": instrumented_finished,
            "assist_complete_matches": complete,
            "assist_complete_rate": complete_rate,
            "matched_fixtures": matched_fixtures,
            "fixture_match_rate": fixture_coverage,
            "eligible_player_appearances": eligible_players,
            "compared_player_appearances": compared,
            "player_match_rate": player_coverage,
            "agreement_rate": agreement_rate,
            "positive_cases": positive_compared,
            "positive_agreement_rate": positive_rate,
        },
        detail_rows,
    )


def market_evidence(log_rows: list[dict], market_path: Path, platt: tuple[float, float]) -> dict:
    if not market_path.exists():
        return {"status": "FAIL", "n": 0, "reason": "market_file_missing"}
    logs_by_team_player: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in log_rows:
        logs_by_team_player[(row["league"], row["match_date"], row["team"], row["player_key"])].append(row)
    with market_path.open("r", encoding="utf-8-sig", newline="") as handle:
        market_rows = list(csv.DictReader(handle))

    latest: dict[tuple[str, str, str, str, str], dict] = {}
    for row in market_rows:
        odds = _float(row.get("market_odds"))
        if odds <= 1.0:
            continue
        key = (
            str(row.get("league_key") or ""),
            str(row.get("match_date") or "")[:10],
            canonical_team(str(row.get("home_team") or "")),
            canonical_team(str(row.get("away_team") or "")),
            norm_text(str(row.get("player_name") or "")),
        )
        if key not in latest or str(row.get("captured_at") or "") > str(latest[key].get("captured_at") or ""):
            latest[key] = row

    outcomes: list[int] = []
    model_raw: list[float] = []
    model_calibrated: list[float] = []
    market_implied: list[float] = []
    market_dates: list[str] = []
    matched_signals = 0
    a, b = platt
    for row in latest.values():
        league = str(row.get("league_key") or "")
        match_date = str(row.get("match_date") or "")[:10]
        team = canonical_team(str(row.get("player_team") or ""))
        player = norm_text(str(row.get("player_name") or ""))
        matches = logs_by_team_player.get((league, match_date, team, player), [])
        if not matches:
            continue
        actual = 1 if max(item["assists"] for item in matches) > 0 else 0
        raw = _clamp(_float(row.get("model_prob")), 1e-6, 1.0 - 1e-6)
        implied = _clamp(1.0 / _float(row.get("market_odds")), 1e-6, 1.0 - 1e-6)
        outcomes.append(actual)
        model_raw.append(raw)
        model_calibrated.append(apply_platt(raw, a, b))
        market_implied.append(implied)
        market_dates.append(match_date)
        matched_signals += int(str(row.get("signal_status") or "") == "shadow_signal")

    unique_dates = sorted(set(market_dates))
    split_index = max(1, math.ceil(len(unique_dates) * 0.60)) if unique_dates else 0
    fit_dates = set(unique_dates[:split_index])
    holdout_dates = set(unique_dates[split_index:])
    fit_indexes = [index for index, value in enumerate(market_dates) if value in fit_dates]
    holdout_indexes = [index for index, value in enumerate(market_dates) if value in holdout_dates]
    market_a, market_b = fit_platt(
        [market_implied[index] for index in fit_indexes],
        [outcomes[index] for index in fit_indexes],
    )
    holdout_raw = [market_implied[index] for index in holdout_indexes]
    holdout_adjusted = [apply_platt(value, market_a, market_b) for value in holdout_raw]
    holdout_outcomes = [outcomes[index] for index in holdout_indexes]
    calendar_span_days = 0
    if unique_dates:
        first = datetime.strptime(unique_dates[0], "%Y-%m-%d")
        last = datetime.strptime(unique_dates[-1], "%Y-%m-%d")
        calendar_span_days = (last - first).days + 1
    holdout_adjusted_metrics = probability_metrics(holdout_adjusted, holdout_outcomes)
    holdout_raw_metrics = probability_metrics(holdout_raw, holdout_outcomes)
    market_gate = bool(
        calendar_span_days >= 90
        and holdout_adjusted_metrics["n"] >= 500
        and holdout_adjusted_metrics["ece"] <= 0.025
        and holdout_adjusted_metrics["brier"] < holdout_raw_metrics["brier"]
    )

    return {
        "status": "PASS" if market_gate else "FAIL",
        "reason": "one_sided_margin_adjustment_needs_90_days_and_prospective_confirmation" if not market_gate else "registered_date_holdout_passed",
        "unique_market_players": len(latest),
        "matched_participants": len(outcomes),
        "matched_old_shadow_signals": matched_signals,
        "model_raw": probability_metrics(model_raw, outcomes),
        "model_historical_calibration": probability_metrics(model_calibrated, outcomes),
        "market_one_sided_implied": probability_metrics(market_implied, outcomes),
        "one_sided_margin_calibration": {
            "method": "platt_on_raw_implied_probability",
            "a": market_a,
            "b": market_b,
            "fit_dates": sorted(fit_dates),
            "holdout_dates": sorted(holdout_dates),
            "calendar_span_days": calendar_span_days,
            "holdout_raw": holdout_raw_metrics,
            "holdout_adjusted": holdout_adjusted_metrics,
        },
        "note": "The empirical margin adjustment is research-only until it spans at least 90 days and then survives prospective confirmation.",
    }


def prospective_evidence(path: Path) -> dict:
    if not path.exists():
        return {"status": "NOT_STARTED", "registered": 0, "settled": 0, "signals": 0, "target_minimum": 100, "target_preferred": 150}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    valid = [row for row in rows if str(row.get("model_version") or "") == "assist_research_v1"]
    settled = [row for row in valid if str(row.get("settled") or "").strip().lower() in {"1", "true", "yes", "settled"}]
    count = len(settled)
    return {
        "status": "PASS" if count >= 100 else ("COLLECTING" if valid else "NOT_STARTED"),
        "registered": len(valid),
        "settled": count,
        "signals": count,
        "target_minimum": 100,
        "target_preferred": 150,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)


def _pct(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def write_report(path: Path, payload: dict) -> None:
    backtest = payload["backtest"]
    settlement = payload["settlement"]
    market = payload["market"]
    margin_calibration = market.get("one_sided_margin_calibration") or {}
    test_raw = backtest["splits"]["test"]["raw"]
    test_cal = backtest["splits"]["test"]["calibrated"]
    test_naive = backtest["splits"]["test"]["naive"]
    lines = [
        "# Assist Value Research Gates",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"Lane status: **{payload['lane_status']}**",
        f"Reactivation ready: **{'YES' if payload['reactivation_ready'] else 'NO'}**",
        "",
        "## Walk-Forward Backtest",
        "",
        f"- Gate: **{backtest['status']}**",
        f"- Train / validation / test: {backtest['train_season']} / {backtest['validation_season']} / {backtest['test_season']}",
        f"- Test rows: {test_cal['n']:,}; positives: {test_cal['positives']:,}",
        f"- Raw Brier / ECE: {test_raw['brier']:.5f} / {_pct(test_raw['ece'])}",
        f"- Calibrated Brier / ECE: {test_cal['brier']:.5f} / {_pct(test_cal['ece'])}",
        f"- Naive Brier: {test_naive['brier']:.5f}",
        f"- Platt parameters: a={backtest['platt']['a']:.6f}, b={backtest['platt']['b']:.6f}",
        f"- Expected-minutes MAE: mean-8 {backtest['minutes']['mean8_mae']:.2f}; median-5 {backtest['minutes']['median5_mae']:.2f}",
        f"- Selected minutes estimator: `{backtest['minutes']['selected']}`",
        "",
        "## Settlement Validation",
        "",
        f"- Overall gate: **{settlement['status']}**",
        f"- Extractor accuracy: **{settlement['extraction_status']}**",
        f"- Operational coverage: **{settlement['operational_status']}**",
        f"- Compared player appearances: {settlement['compared_player_appearances']:,}",
        f"- Assist agreement: {_pct(settlement['agreement_rate'])}",
        f"- Positive assist cases: {settlement['positive_cases']:,}; agreement {_pct(settlement['positive_agreement_rate'])}",
        f"- Assist-complete instrumented fixtures: {settlement['assist_complete_matches']:,}/{settlement['instrumented_finished_matches']:,} ({_pct(settlement['assist_complete_rate'])})",
        f"- Legacy pre-instrumentation fixtures excluded from completeness denominator: {settlement['finished_matches'] - settlement['instrumented_finished_matches']:,}",
        f"- Player matching coverage: {_pct(settlement['player_match_rate'])}",
        "",
        "## Market Evidence",
        "",
        f"- Gate: **{market['status']}**",
        f"- Matched participating players: {market.get('matched_participants', 0):,}",
        f"- Old matched shadow signals: {market.get('matched_old_shadow_signals', 0):,}",
        f"- Captured calendar span: {margin_calibration.get('calendar_span_days', 0)} days (minimum 90)",
        f"- Margin-adjustment holdout rows: {(margin_calibration.get('holdout_adjusted') or {}).get('n', 0):,}",
        f"- Reason blocked: `{market.get('reason', 'unknown')}`",
        "- The fitted one-sided margin adjustment remains research-only and is not treated as CLV.",
        "",
        "## Prospective Gate",
        "",
        f"- Registered v1 signals: {payload['prospective'].get('registered', 0)}",
        f"- Settled v1 signals: {payload['prospective']['signals']}/{payload['prospective']['target_minimum']}",
        "- This counter starts only after all upstream gates are implemented and the new model version is locked.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Assist Value reactivation evidence")
    parser.add_argument("--player-logs", nargs="+", default=[DEFAULT_LOG_GLOB])
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--market", default=str(DEFAULT_MARKET))
    parser.add_argument("--prospective", default=str(DEFAULT_PROSPECTIVE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    print("Loading historical player-match logs...")
    logs = load_player_logs(args.player_logs)
    print(f"Loaded {len(logs):,} player-match rows")
    predictions = build_walk_forward_predictions(logs)
    print(f"Built {len(predictions):,} causal predictions")
    backtest, segments, platt = evaluate_backtest(predictions)
    settlement, settlement_rows = settlement_validation(logs, Path(args.results_dir))
    market = market_evidence(logs, Path(args.market), platt)
    prospective = prospective_evidence(Path(args.prospective))
    reactivation_ready = bool(
        backtest["status"] == "PASS"
        and settlement["status"] == "PASS"
        and market["status"] == "PASS"
        and prospective["status"] == "PASS"
    )

    payload = {
        "generated_at": generated_at,
        "lane_status": "FROZEN_RESEARCH",
        "reactivation_ready": reactivation_ready,
        "backtest": backtest,
        "settlement": settlement,
        "lineup_minutes": {
            "status": "IMPLEMENTED_NOT_PROSPECTIVE",
            "historical_minutes_model": backtest["minutes"],
            "confirmed_lineup_live_wiring": True,
        },
        "market": market,
        "prospective": prospective,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assist-value-gates.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_csv(out_dir / "assist-value-segments.csv", segments)
    _write_csv(out_dir / "assist-settlement-validation.csv", settlement_rows)
    write_report(out_dir / "assist-value-research-report.md", payload)
    print(f"Backtest gate: {backtest['status']}")
    print(f"Settlement extractor / operations: {settlement['extraction_status']} / {settlement['operational_status']}")
    print(f"Market gate: {market['status']}")
    print(f"Saved research artifacts to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
