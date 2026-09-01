#!/usr/bin/env python3
"""Publish the locked Team Shots v4 and Corners v3 prospective shadow lanes.

Only paired two-way prices are scored. Matchdays 1-3 fail closed for official
shadow publication, but edge-qualified warm-up observations are retained in a
separate tracking cohort. The strongest row per fixture is appended to a
versioned ledger. These outputs are research signals, not staking instructions.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_counts import prob_over  # noqa: E402
from football_market import blend_logit, proportional_devig, shading_aware_devig  # noqa: E402


TEAM_PARAMS = ROOT / "data" / "team-shots" / "team-shots-v4-params.json"
TEAM_LOCK = ROOT / "data" / "team-shots" / "team-shots-v4-lock.json"
TEAM_OUTPUT = ROOT / "data" / "football-form" / "team-shots-v4-shadow-signals.csv"
CORNERS_PARAMS = ROOT / "data" / "corners-ou" / "corners-v3-params.json"
CORNERS_LOCK = ROOT / "data" / "corners-ou" / "corners-v3-lock.json"
CORNERS_OUTPUT = ROOT / "data" / "football-form" / "corners-v3-shadow-signals.csv"
CANDIDATES_OUTPUT = ROOT / "data" / "football-form" / "football-counts-vnext-candidates.csv"
EVENTS_INPUT = ROOT / "data" / "team-shots" / "understat" / "corner-event-features.csv"

TEAM_MODEL = "team_shots_v4"
CORNERS_MODEL = "corners_v3"
TOP_FIVE = {"epl", "serie-a", "la-liga", "bundesliga", "ligue-1"}
MAX_CAPTURE_SKEW_MINUTES = 15.0

EXTRA_FIELDS = [
    "raw_model_probability",
    "market_fair_probability",
    "model_market_gap",
    "matchday",
    "team_neff",
    "opponent_neff",
    "model_mean",
    "distribution_parameter",
    "signal_status",
]


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PUB = load_module("football_research_publisher_vnext", SCRIPTS / "publish-football-research-picks.py")
FIELDS = [*PUB.PUBLISHED_FIELDS, *EXTRA_FIELDS]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing locked model artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def season_match_count(by_team: dict[tuple[str, str], list[dict[str, str]]], league: str, team: str, day: date) -> int:
    season = PUB.season_label(day)
    return sum(
        1
        for row in by_team.get((league, PUB.team_key(team)), [])
        if row.get("season") == season
        and (played := PUB.parse_date(row.get("date"))) is not None
        and played < day
    )


def paired_rows(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = tuple(str(row.get(field) or "") for field in key_fields)
        grouped[key][str(row.get("side") or "").lower()] = row
    output: list[dict[str, Any]] = []
    for sides in grouped.values():
        over = sides.get("over")
        under = sides.get("under")
        if over is None or under is None:
            continue
        skew = abs((over["captured_at_dt"] - under["captured_at_dt"]).total_seconds()) / 60.0
        if skew > MAX_CAPTURE_SKEW_MINUTES:
            continue
        output.append({"over": over, "under": under, "capture_skew_minutes": skew})
    return output


def candidate_row(
    *,
    model: str,
    source: dict[str, Any],
    team: str,
    side: str,
    probability: float,
    raw_probability: float,
    market_probability: float,
    edge: float,
    matchday: int,
    team_neff: int,
    opponent_neff: int,
    model_mean: float,
    distribution_parameter: float,
    status: str,
    blocked_reason: str = "",
) -> dict[str, Any]:
    kickoff: datetime = source["kickoff"]
    league = source["league_slug"]
    home = source["home_team"]
    away = source["away_team"]
    match_date = kickoff.date().isoformat()
    fx_key = PUB.fixture_key(match_date, league, home, away)
    line = source["line_label"]
    selection = f"{team + ' ' if team else ''}{side} {line}".strip()
    pick_scope = PUB.team_fixture_key(match_date, league, home, away, team) if team else fx_key
    return {
        "pick_id": "|".join([model, pick_scope, line, side]),
        "published_at_utc": PUB.fmt_dt(source["captured_at_dt"]),
        "kickoff_utc": PUB.fmt_dt(kickoff),
        "match_id": fx_key,
        "match_date": match_date,
        "league": league,
        "match": f"{home} vs {away}",
        "home_team": home,
        "away_team": away,
        "team": team,
        "bookmaker": source.get("bookmaker") or "Pinnacle",
        "selection": selection,
        "line": line,
        "side": side,
        "model": model,
        "model_fair_odds": round(PUB.fair_odds(probability), 6),
        "model_implied_prob": round(probability, 6),
        "book_odds": round(float(source["odds"]), 6),
        "edge": round(edge, 6),
        "current_model_would_have_priced": "true" if not blocked_reason else "false",
        "confidence_guard_applied": "true" if blocked_reason else "false",
        "blocked_reason": blocked_reason,
        "result": "",
        "pnl_units": "",
        "raw_model_probability": round(raw_probability, 6),
        "market_fair_probability": round(market_probability, 6),
        "model_market_gap": round(raw_probability - market_probability, 6),
        "matchday": matchday,
        "team_neff": team_neff,
        "opponent_neff": opponent_neff,
        "model_mean": round(model_mean, 6),
        "distribution_parameter": round(distribution_parameter, 8),
        "signal_status": status,
    }


def cap_signals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("match_id") or "")].append(row)
    return sorted(
        [
            max(group, key=lambda row: (float(row.get("edge") or 0.0), float(row.get("book_odds") or 0.0)))
            for group in grouped.values()
        ],
        key=lambda row: (row.get("kickoff_utc", ""), row.get("match", "")),
    )


def warmup_tracking_signals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep rows blocked only by MD1-3 as non-bettable tracking evidence."""
    tracking: list[dict[str, Any]] = []
    for source in rows:
        reasons = {
            reason.strip()
            for reason in str(source.get("blocked_reason") or "").split(";")
            if reason.strip()
        }
        if reasons != {"matchdays_1_to_3"}:
            continue
        row = dict(source)
        row.update(
            {
                "signal_status": "warmup_tracking",
                "current_model_would_have_priced": "true",
                "confidence_guard_applied": "false",
                "blocked_reason": "",
            }
        )
        tracking.append(row)
    return cap_signals(tracking)


def unseen_warmup_signals(
    existing_rows: list[dict[str, Any]], fresh_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Freeze the first recorded warm-up selection for each model fixture."""
    existing_fixtures = {
        (str(row.get("model") or ""), str(row.get("match_id") or ""))
        for row in existing_rows
        if str(row.get("signal_status") or "").strip().lower() == "warmup_tracking"
    }
    return [
        row
        for row in fresh_rows
        if (str(row.get("model") or ""), str(row.get("match_id") or ""))
        not in existing_fixtures
    ]


def is_fixture_team(team: str, home: str, away: str) -> bool:
    team_key = PUB.team_key(team)
    return bool(team_key) and team_key in {PUB.team_key(home), PUB.team_key(away)}


def team_alpha(params: dict[str, Any], league: str, team: str) -> float:
    entry = params.get("team_alpha", {}).get(f"{league}|{PUB.team_key(team)}")
    if isinstance(entry, dict) and entry.get("alpha") is not None:
        return float(entry["alpha"])
    if params.get("league_alpha", {}).get(league) is not None:
        return float(params["league_alpha"][league])
    return float(params["pooled_alpha"])


def score_team_shots(
    *,
    by_team: dict[tuple[str, str], list[dict[str, str]]],
    by_league: dict[str, list[dict[str, str]]],
    odds_rows: list[dict[str, str]],
    params: dict[str, Any],
    lock: dict[str, Any],
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    latest = PUB.latest_team_shots_odds(odds_rows, now)
    pairs = paired_rows(latest, ("league_slug", "home_team", "away_team", "team", "line_label", "bookmaker"))
    accepted: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    min_edge = float(lock["selection_rules"]["minimum_edge"])
    market_weight = float(params["market"]["model_weight"])
    vig_share = float(params["market"]["over_vig_share"])
    market_gap_cap = float(lock["selection_rules"].get("market_gap_cap", 0.12))
    form_cache: dict[tuple[str, str, str, str], tuple[dict[str, Any], dict[str, Any], str, float, float, int, int, int]] = {}
    baseline_cache: dict[tuple[str, date], dict[str, Any]] = {}

    for pair in pairs:
        over, under = pair["over"], pair["under"]
        league = over["league_slug"]
        if league not in TOP_FIVE:
            continue
        kickoff: datetime = over["kickoff"]
        day = kickoff.date()
        home, away = over["home_team"], over["away_team"]
        team = over.get("team", "").strip()
        if not is_fixture_team(team, home, away):
            continue
        is_home = PUB.team_key(team) == PUB.team_key(home)
        opponent = away if is_home else home
        cache_key = (day.isoformat(), league, PUB.team_key(team), PUB.team_key(opponent))
        context = form_cache.get(cache_key)
        if context is None:
            team_form = PUB.live_form_row(
                by_team=by_team, by_league=by_league, league=league, fixture_date=day,
                team=team, opponent=opponent, venue="home" if is_home else "away", home=home, away=away,
                baseline_cache=baseline_cache,
            )
            opponent_form = PUB.live_form_row(
                by_team=by_team, by_league=by_league, league=league, fixture_date=day,
                team=opponent, opponent=team, venue="away" if is_home else "home", home=home, away=away,
                baseline_cache=baseline_cache,
            )
            if team_form is None or opponent_form is None:
                continue
            lam_value = PUB.BACKTEST.canonical_team_shots_ema20_lambda(team_form, opponent_form, use_market=True)
            if lam_value is None:
                continue
            alpha_value = team_alpha(params, league, team)
            matchday_value = min(
                season_match_count(by_team, league, team, day),
                season_match_count(by_team, league, opponent, day),
            ) + 1
            team_neff_value = int(PUB.pf(team_form.get("ema20_matches")) or 0)
            opponent_neff_value = int(PUB.pf(opponent_form.get("ema20_matches")) or 0)
            context = (
                team_form, opponent_form, opponent, float(lam_value), alpha_value,
                matchday_value, team_neff_value, opponent_neff_value,
            )
            form_cache[cache_key] = context
        team_form, opponent_form, opponent, lam, alpha, matchday, team_neff, opponent_neff = context
        line = PUB.pf(over["line_label"])
        if line is None:
            continue
        raw_over = prob_over(line, lam, distribution="negative_binomial", alpha=alpha)
        market_over, market_under, _ = shading_aware_devig(
            float(over["odds"]), float(under["odds"]), over_vig_share=vig_share,
        )
        blended_over = blend_logit(raw_over, market_over, market_weight)

        for side, source, probability, raw_probability, market_probability in (
            ("over", over, blended_over, raw_over, market_over),
            ("under", under, 1.0 - blended_over, 1.0 - raw_over, market_under),
        ):
            edge = (probability * float(source["odds"])) - 1.0
            blocked: list[str] = []
            if matchday <= 3:
                blocked.append("matchdays_1_to_3")
            if 4 <= matchday <= 6 and min(team_neff, opponent_neff) < 6:
                blocked.append("early_neff_below_6")
            if 4 <= matchday <= 6 and abs(raw_probability - market_probability) > market_gap_cap:
                blocked.append("early_market_gap_cap")
            if edge < min_edge:
                blocked.append("edge_below_3pct")
            status = "eligible" if not blocked else "blocked"
            row = candidate_row(
                model=TEAM_MODEL, source=source, team=team, side=side, probability=probability,
                raw_probability=raw_probability, market_probability=market_probability, edge=edge,
                matchday=matchday, team_neff=team_neff, opponent_neff=opponent_neff,
                model_mean=lam, distribution_parameter=alpha, status=status,
                blocked_reason=";".join(blocked),
            )
            candidates.append(row)
            if not blocked:
                accepted.append(row)
    return cap_signals(accepted), candidates


@dataclass
class EventState:
    wide_for: list[float] = field(default_factory=list)
    wide_against: list[float] = field(default_factory=list)
    block_for: list[float] = field(default_factory=list)
    block_against: list[float] = field(default_factory=list)

    def add(self, wide_for: float, wide_against: float, block_for: float, block_against: float, window: int) -> None:
        for values, value in (
            (self.wide_for, wide_for), (self.wide_against, wide_against),
            (self.block_for, block_for), (self.block_against, block_against),
        ):
            values.append(value)
            if len(values) > window:
                del values[0]

    def ema(self, values: list[float], decay: float) -> float:
        weights = [decay ** (len(values) - 1 - index) for index in range(len(values))]
        return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)

    @property
    def matches(self) -> int:
        return len(self.wide_for)


def latest_event_states(rows: list[dict[str, str]], params: dict[str, Any]) -> dict[tuple[str, str], EventState]:
    states: dict[tuple[str, str], EventState] = defaultdict(EventState)
    window = int(params["event_window"])
    for row in sorted(rows, key=lambda item: (item.get("date", ""), item.get("league", ""))):
        league = PUB.league_slug(row.get("league", ""))
        home = PUB.team_key(row.get("home_team", ""))
        away = PUB.team_key(row.get("away_team", ""))
        home_state = states[(league, home)]
        away_state = states[(league, away)]
        home_wide = PUB.pf(row.get("home_wide_share")) or 0.0
        away_wide = PUB.pf(row.get("away_wide_share")) or 0.0
        home_block = PUB.pf(row.get("home_blocked_rate")) or 0.0
        away_block = PUB.pf(row.get("away_blocked_rate")) or 0.0
        home_state.add(home_wide, away_wide, home_block, away_block, window)
        away_state.add(away_wide, home_wide, away_block, home_block, window)
    return states


def preferred(row: dict[str, Any], primary: str, fallback: str) -> float | None:
    return PUB.pf(row.get(primary)) or PUB.pf(row.get(fallback))


def corners_features(
    home: dict[str, Any], away: dict[str, Any], home_state: EventState, away_state: EventState, params: dict[str, Any]
) -> tuple[float, tuple[float, ...]] | None:
    league_corner_values = [
        PUB.pf(home.get("league_prior_corners_for_avg")),
        PUB.pf(away.get("league_prior_corners_for_avg")),
    ]
    valid_corners = [value for value in league_corner_values if value is not None and value > 0]
    league_team_corners = mean(valid_corners) if valid_corners else 4.9
    home_cf = preferred(home, "ema20_corners_for_home_avg", "ema20_corners_for_avg")
    home_ca = preferred(home, "ema20_corners_against_home_avg", "ema20_corners_against_avg")
    away_cf = preferred(away, "ema20_corners_for_away_avg", "ema20_corners_for_avg")
    away_ca = preferred(away, "ema20_corners_against_away_avg", "ema20_corners_against_avg")
    home_shots = PUB.pf(home.get("ema20_shots_for_avg"))
    away_shots = PUB.pf(away.get("ema20_shots_for_avg"))
    league_shots_values = [
        PUB.pf(home.get("league_prior_shots_for_avg")),
        PUB.pf(away.get("league_prior_shots_for_avg")),
    ]
    valid_shots = [value for value in league_shots_values if value is not None and value > 0]
    league_shots = mean(valid_shots) if valid_shots else 12.5
    required = (home_cf, home_ca, away_cf, away_ca, home_shots, away_shots)
    if any(value is None for value in required):
        return None
    decay = float(params["event_decay"])
    wide = mean([
        home_state.ema(home_state.wide_for, decay), home_state.ema(home_state.wide_against, decay),
        away_state.ema(away_state.wide_for, decay), away_state.ema(away_state.wide_against, decay),
    ])
    blocked = mean([
        home_state.ema(home_state.block_for, decay), home_state.ema(home_state.block_against, decay),
        away_state.ema(away_state.block_for, decay), away_state.ema(away_state.block_against, decay),
    ])
    features = (
        math.log(max(0.1, float(home_cf)) / league_team_corners),
        math.log(max(0.1, float(away_ca)) / league_team_corners),
        math.log(max(0.1, float(away_cf)) / league_team_corners),
        math.log(max(0.1, float(home_ca)) / league_team_corners),
        wide,
        blocked,
        math.log(max(0.1, float(home_shots) + float(away_shots)) / (2.0 * league_shots)),
    )
    return 2.0 * league_team_corners, features


def predict_corners_mean(league_mean: float, features: tuple[float, ...], params: dict[str, Any]) -> float:
    selected = [features[index] for index in params["feature_indices"]]
    standardized = [
        (value - float(center)) / float(scale)
        for value, center, scale in zip(selected, params["centers"], params["scales"])
    ]
    beta = [float(value) for value in params["beta"]]
    linear = beta[0] + sum(coef * value for coef, value in zip(beta[1:], standardized))
    return max(2.0, min(22.0, league_mean * math.exp(linear)))


def score_corners(
    *,
    by_team: dict[tuple[str, str], list[dict[str, str]]],
    by_league: dict[str, list[dict[str, str]]],
    odds_rows: list[dict[str, str]],
    event_rows: list[dict[str, str]],
    params: dict[str, Any],
    lock: dict[str, Any],
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    latest = PUB.latest_corners_odds(odds_rows, now)
    pairs = paired_rows(latest, ("league_slug", "home_team", "away_team", "line_label"))
    states = latest_event_states(event_rows, params)
    accepted: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    min_edge = float(lock["selection_rules"]["minimum_edge"])
    min_history = int(params["event_min_history"])
    alpha = float(params["alpha"])
    form_cache: dict[tuple[str, str, str, str], tuple[float, int, int, int]] = {}
    baseline_cache: dict[tuple[str, date], dict[str, Any]] = {}

    for pair in pairs:
        over, under = pair["over"], pair["under"]
        league = over["league_slug"]
        if league not in TOP_FIVE:
            continue
        kickoff: datetime = over["kickoff"]
        day = kickoff.date()
        home, away = over["home_team"], over["away_team"]
        cache_key = (day.isoformat(), league, PUB.team_key(home), PUB.team_key(away))
        context = form_cache.get(cache_key)
        if context is None:
            home_form = PUB.live_form_row(
                by_team=by_team, by_league=by_league, league=league, fixture_date=day,
                team=home, opponent=away, venue="home", home=home, away=away,
                baseline_cache=baseline_cache,
            )
            away_form = PUB.live_form_row(
                by_team=by_team, by_league=by_league, league=league, fixture_date=day,
                team=away, opponent=home, venue="away", home=home, away=away,
                baseline_cache=baseline_cache,
            )
            if home_form is None or away_form is None:
                continue
            home_state = states[(league, PUB.team_key(home))]
            away_state = states[(league, PUB.team_key(away))]
            if min(home_state.matches, away_state.matches) < min_history:
                continue
            feature_row = corners_features(home_form, away_form, home_state, away_state, params)
            if feature_row is None:
                continue
            league_mean, features = feature_row
            predicted_mean_value = predict_corners_mean(league_mean, features, params)
            matchday_value = min(
                season_match_count(by_team, league, home, day),
                season_match_count(by_team, league, away, day),
            ) + 1
            home_neff_value = int(PUB.pf(home_form.get("ema20_matches")) or 0)
            away_neff_value = int(PUB.pf(away_form.get("ema20_matches")) or 0)
            context = (predicted_mean_value, matchday_value, home_neff_value, away_neff_value)
            form_cache[cache_key] = context
        predicted_mean, matchday, home_neff, away_neff = context
        line = PUB.pf(over["line_label"])
        if line is None:
            continue
        raw_over = prob_over(line, predicted_mean, distribution="negative_binomial", alpha=alpha)
        market_over, market_under, _ = proportional_devig(float(over["odds"]), float(under["odds"]))

        for side, source, probability, market_probability in (
            ("over", over, raw_over, market_over),
            ("under", under, 1.0 - raw_over, market_under),
        ):
            edge = (probability * float(source["odds"])) - 1.0
            blocked: list[str] = []
            if matchday <= 3:
                blocked.append("matchdays_1_to_3")
            if edge < min_edge:
                blocked.append("edge_below_3pct")
            status = "eligible" if not blocked else "blocked"
            row = candidate_row(
                model=CORNERS_MODEL, source={**source, "bookmaker": "Pinnacle"}, team="", side=side,
                probability=probability, raw_probability=probability, market_probability=market_probability,
                edge=edge, matchday=matchday, team_neff=home_neff, opponent_neff=away_neff,
                model_mean=predicted_mean, distribution_parameter=alpha, status=status,
                blocked_reason=";".join(blocked),
            )
            candidates.append(row)
            if not blocked:
                accepted.append(row)
    return cap_signals(accepted), candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-base", type=Path, default=PUB.DEFAULT_TEAM_BASE)
    parser.add_argument("--team-odds", type=Path, default=PUB.DEFAULT_TEAM_ODDS)
    parser.add_argument("--corners-odds", type=Path, default=PUB.DEFAULT_CORNERS_PINNACLE)
    parser.add_argument("--events", type=Path, default=EVENTS_INPUT)
    parser.add_argument("--team-params", type=Path, default=TEAM_PARAMS)
    parser.add_argument("--team-lock", type=Path, default=TEAM_LOCK)
    parser.add_argument("--team-output", type=Path, default=TEAM_OUTPUT)
    parser.add_argument("--corners-params", type=Path, default=CORNERS_PARAMS)
    parser.add_argument("--corners-lock", type=Path, default=CORNERS_LOCK)
    parser.add_argument("--corners-output", type=Path, default=CORNERS_OUTPUT)
    parser.add_argument("--candidates-output", type=Path, default=CANDIDATES_OUTPUT)
    parser.add_argument("--now", default="", help="UTC ISO timestamp override")
    args = parser.parse_args()

    now = PUB.parse_dt(args.now) if args.now else datetime.now(UTC)
    if now is None:
        raise SystemExit(f"Invalid --now: {args.now}")
    PUB.ensure_team_base(args.team_base)
    base_rows = PUB.load_csv(args.team_base)
    by_team, by_league = PUB.build_base_indexes(base_rows)
    team_signals, team_candidates = score_team_shots(
        by_team=by_team, by_league=by_league, odds_rows=PUB.load_csv(args.team_odds),
        params=load_json(args.team_params), lock=load_json(args.team_lock), now=now,
    )
    corners_signals, corners_candidates = score_corners(
        by_team=by_team, by_league=by_league, odds_rows=PUB.load_csv(args.corners_odds),
        event_rows=PUB.load_csv(args.events), params=load_json(args.corners_params),
        lock=load_json(args.corners_lock), now=now,
    )

    team_existing = PUB.load_csv(args.team_output)
    corners_existing = PUB.load_csv(args.corners_output)
    team_warmup = unseen_warmup_signals(
        team_existing, warmup_tracking_signals(team_candidates)
    )
    corners_warmup = unseen_warmup_signals(
        corners_existing, warmup_tracking_signals(corners_candidates)
    )
    team_ledger = PUB.merge_published_ledger(
        team_existing, [*team_signals, *team_warmup]
    )
    corners_ledger = PUB.merge_published_ledger(
        corners_existing, [*corners_signals, *corners_warmup]
    )
    write_csv(args.team_output, team_ledger)
    write_csv(args.corners_output, corners_ledger)
    write_csv(args.candidates_output, sorted(
        team_candidates + corners_candidates,
        key=lambda row: (row.get("kickoff_utc", ""), row.get("model", ""), -float(row.get("edge") or 0.0)),
    ))
    print(
        f"Team Shots v4: {len(team_signals)} fresh eligible, "
        f"{len(team_warmup)} warm-up tracking, {len(team_ledger)} ledger rows"
    )
    print(
        f"Corners v3: {len(corners_signals)} fresh eligible, "
        f"{len(corners_warmup)} warm-up tracking, {len(corners_ledger)} ledger rows"
    )
    print(f"Candidates scored: {len(team_candidates) + len(corners_candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
