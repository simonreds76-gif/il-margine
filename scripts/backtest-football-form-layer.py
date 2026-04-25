#!/usr/bin/env python3
"""
Backtest the canonical football-form layer against the current football models.

This is research-only. It does not change live picks or thresholds.

The script compares:
  - current team-shots prediction output vs canonical rolling-form shots lambda
  - current corners prediction output vs canonical rolling-form corners lambda

Metrics:
  - count accuracy: MAE, RMSE, bias
  - price calibration: Brier and log loss for standard O/U lines

Outputs:
  data/football-form/canonical-backtest-summary.csv
  data/football-form/canonical-backtest-report.md
"""

from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent

DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_TEAM_SHOTS_CURRENT = ROOT / "data" / "team-shots" / "team-shots-predictions.csv"
DEFAULT_CORNERS_CURRENT = ROOT / "data" / "corners-ou" / "corners-ou-predictions.csv"
DEFAULT_SUMMARY_OUT = ROOT / "data" / "football-form" / "canonical-backtest-summary.csv"
DEFAULT_REPORT_OUT = ROOT / "data" / "football-form" / "canonical-backtest-report.md"

TEAM_SHOTS_LINES = [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5]
CORNERS_LINES = [8.5, 9.5, 10.5, 11.5]
TEAM_SHOTS_BASELINES = {
    "epl": 12.8,
    "serie-a": 12.5,
    "la-liga": 12.2,
    "bundesliga": 12.9,
    "ligue-1": 12.3,
}
DEFAULT_TEAM_SHOTS_BASELINE = 12.5
XG_WEIGHT = 0.25


def pf(value: Any, default: float | None = 0.0) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def poisson_prob_over(line: float, lam: float) -> float:
    """P(X > line) for half-goal/half-shot lines."""
    if lam <= 0:
        return 0.0
    cutoff = int(math.floor(line))
    cdf = 0.0
    for k in range(cutoff + 1):
        cdf += math.exp((k * math.log(lam)) - lam - math.lgamma(k + 1))
    return clamp(1.0 - cdf, 1e-6, 1.0 - 1e-6)


def negative_binomial_prob_over(line: float, mean_count: float, alpha: float) -> float:
    """P(X > line) for NB2 variance = mean + alpha * mean^2."""
    if mean_count <= 0:
        return 0.0
    if alpha <= 1e-6:
        return poisson_prob_over(line, mean_count)

    cutoff = int(math.floor(line))
    size = 1.0 / alpha
    success_prob = size / (size + mean_count)
    success_prob = clamp(success_prob, 1e-9, 1.0 - 1e-9)

    pmf = math.exp(size * math.log(success_prob))
    cdf = pmf
    fail_prob = 1.0 - success_prob
    for k in range(cutoff):
        pmf *= ((k + size) / (k + 1.0)) * fail_prob
        cdf += pmf
    return clamp(1.0 - cdf, 1e-6, 1.0 - 1e-6)


def brier(prob: float, actual: bool) -> float:
    y = 1.0 if actual else 0.0
    return (prob - y) ** 2


def log_loss(prob: float, actual: bool) -> float:
    p = clamp(prob, 1e-6, 1.0 - 1e-6)
    return -math.log(p if actual else (1.0 - p))


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def row_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("date", "")).strip(),
        str(row.get("league", "")).strip(),
        str(row.get("home_team", "")).strip(),
        str(row.get("away_team", "")).strip(),
    )


def row_date(row: dict[str, Any]) -> date | None:
    text = str(row.get("date") or row.get("match_date") or "").strip()
    if not text:
        return None
    for candidate in (text, text[:10]):
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    return None


def team_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("date", "")).strip(),
        str(row.get("league", "")).strip(),
        str(row.get("team", "")).strip(),
        str(row.get("home_team", "")).strip(),
        str(row.get("away_team", "")).strip(),
    )


def load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def ensure_form_input(path: Path) -> None:
    if path.exists():
        return
    if path != DEFAULT_FORM:
        raise SystemExit(f"Missing canonical form input: {path}")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build-football-form-layer.py")], check=True)
    if not path.exists():
        raise SystemExit(f"Canonical form build did not create expected input: {path}")


def enough_history(row: dict[str, Any], minimum: int = 6) -> bool:
    return int(pf(row.get("r10_matches"), 0) or 0) >= minimum


def blended(row: dict[str, Any], field: str) -> float | None:
    r10 = pf(row.get(f"r10_{field}"), None)
    r5 = pf(row.get(f"r5_{field}"), None)
    r5_matches = int(pf(row.get("r5_matches"), 0) or 0)
    if r10 is None and r5 is None:
        return None
    if r10 is None:
        return r5
    if r5 is None or r5_matches < 3:
        return r10
    return (0.70 * r10) + (0.30 * r5)


def blended_prefer(row: dict[str, Any], preferred: str, fallback: str) -> float | None:
    value = blended(row, preferred)
    if value is not None:
        return value
    return blended(row, fallback)


def venue_field(base: str, venue: str) -> str:
    suffix = "home" if venue == "home" else "away"
    return f"{base}_{suffix}_avg"


def quality_adjustment(team: dict[str, Any], opp: dict[str, Any]) -> float:
    """
    Small xG-per-shot adjustment when both sides have usable xG history.

    This is deliberately capped. We are testing whether xG adds signal, not
    letting sparse xG rows dominate the count forecast.
    """
    team_q = pf(team.get("r10_xg_per_shot_for"), None)
    opp_q = pf(opp.get("r10_xg_per_shot_against"), None)
    if team_q is None or opp_q is None or team_q <= 0 or opp_q <= 0:
        return 1.0
    quality = (team_q + opp_q) / 2.0
    neutral = 0.10
    return clamp(1.0 + ((quality - neutral) * 1.5), 0.88, 1.12)


def market_game_state_adjustment(team: dict[str, Any]) -> float:
    """
    Pre-match market strength proxy for expected game-state asymmetry.

    Heavy favourites tend to take/produce more shots; heavy underdogs often spend
    more time defending. The cap keeps this as a modest contextual nudge rather
    than letting 1X2 odds dominate the shot model.
    """
    team_prob = pf(team.get("market_team_win_prob"), None)
    opp_prob = pf(team.get("market_opp_win_prob"), None)
    if team_prob is None or opp_prob is None:
        return 1.0
    gap = team_prob - opp_prob
    return clamp(1.0 + (gap * 0.22), 0.88, 1.12)


def pressure_adjustment(team: dict[str, Any], opp: dict[str, Any], league_shots_avg: float) -> float:
    team_shots = blended(team, "shots_for_avg")
    opp_conceded = blended(opp, "shots_against_avg")
    if team_shots is None or opp_conceded is None or league_shots_avg <= 0:
        return 1.0
    pressure = ((team_shots / league_shots_avg) + (opp_conceded / league_shots_avg)) / 2.0
    return clamp(1.0 + ((pressure - 1.0) * 0.18), 0.88, 1.12)


def league_level_ratio(
    team: dict[str, Any],
    opp: dict[str, Any],
    *,
    metric_for: str,
    metric_against: str,
) -> float:
    """Causal trailing-12m league-level replay ratio.

    This is a diagnostic normalization replay, not a promoted formula. It asks
    whether recent league shot/corner regimes explain the last-90 regression.
    """
    t12_rows = int(pf(team.get("league_t12_rows"), 0) or 0)
    if t12_rows < 100:
        return 1.0
    prior_values = [
        pf(team.get(f"league_prior_{metric_for}_avg"), None),
        pf(opp.get(f"league_prior_{metric_against}_avg"), None),
    ]
    t12_values = [
        pf(team.get(f"league_t12_{metric_for}_avg"), None),
        pf(opp.get(f"league_t12_{metric_against}_avg"), None),
    ]
    prior = mean([value for value in prior_values if value is not None and value > 0])
    trailing = mean([value for value in t12_values if value is not None and value > 0])
    if prior <= 0 or trailing <= 0:
        return 1.0
    return clamp(trailing / prior, 0.90, 1.10)


def canonical_team_shots_lambda(
    team: dict[str, Any],
    opp: dict[str, Any],
    *,
    use_market: bool = False,
    use_trailing12: bool = False,
) -> float | None:
    team_venue = str(team.get("venue", "")).strip()
    opp_venue = str(opp.get("venue", "")).strip()
    attack = blended_prefer(team, venue_field("shots_for", team_venue), "shots_for_avg")
    opp_defence = blended_prefer(opp, venue_field("shots_against", opp_venue), "shots_against_avg")
    if attack is None or opp_defence is None or not enough_history(team) or not enough_history(opp):
        return None
    lam = (0.55 * attack) + (0.45 * opp_defence)
    lam *= quality_adjustment(team, opp)
    if use_market:
        lam *= market_game_state_adjustment(team)
    if use_trailing12:
        lam *= league_level_ratio(team, opp, metric_for="shots_for", metric_against="shots_against")
    return clamp(lam, 3.0, 30.0)


def canonical_team_shots_pooled_opp_lambda(
    team: dict[str, Any],
    opp: dict[str, Any],
    *,
    use_market: bool = True,
) -> float | None:
    """Team-shots v2 replay: venue attack, pooled opponent concession."""
    team_venue = str(team.get("venue", "")).strip()
    attack = blended_prefer(team, venue_field("shots_for", team_venue), "shots_for_avg")
    opp_defence = blended(opp, "shots_against_avg")
    if attack is None or opp_defence is None or not enough_history(team) or not enough_history(opp):
        return None
    lam = (0.55 * attack) + (0.45 * opp_defence)
    lam *= quality_adjustment(team, opp)
    if use_market:
        lam *= market_game_state_adjustment(team)
    return clamp(lam, 3.0, 30.0)


def league_prior_avg(team: dict[str, Any], opp: dict[str, Any], metric_for: str, metric_against: str, fallback: float) -> float:
    values = [
        pf(team.get(f"league_prior_{metric_for}_avg"), None),
        pf(opp.get(f"league_prior_{metric_against}_avg"), None),
    ]
    valid = [value for value in values if value is not None and value > 0]
    return mean(valid) if valid else fallback


def canonical_team_shots_current_shape_lambda(team: dict[str, Any], opp: dict[str, Any]) -> float | None:
    """Current-model formula shape replay using canonical inputs.

    This diagnostic tests the specific gap found in the feature comparison:
    current uses a league-relative multiplicative lambda with venue-specific
    team attack and pooled opponent defence. Canonical v1 used an additive
    attack/concession blend and venue-specific opponent concession.
    """
    team_venue = str(team.get("venue", "")).strip()
    league = str(team.get("league", "")).strip()
    fallback = TEAM_SHOTS_BASELINES.get(league, DEFAULT_TEAM_SHOTS_BASELINE)
    avg = league_prior_avg(team, opp, "shots_for", "shots_against", fallback)
    if avg <= 0:
        avg = fallback

    attack = blended_prefer(team, venue_field("shots_for", team_venue), "shots_for_avg")
    opp_defence = blended(opp, "shots_against_avg")
    if attack is None or opp_defence is None or not enough_history(team) or not enough_history(opp):
        return None

    lam_shots = avg * (attack / avg) * (opp_defence / avg)
    lam = lam_shots

    team_xg = blended(team, "xg_for_avg")
    opp_xg = blended(opp, "xg_against_avg")
    avg_xg = league_prior_avg(team, opp, "xg_for", "xg_against", 1.35)
    if team_xg is not None and opp_xg is not None and team_xg > 0 and opp_xg > 0 and avg_xg > 0:
        xg_lam = avg * (team_xg / avg_xg) * (opp_xg / avg_xg)
        lam = ((1.0 - XG_WEIGHT) * lam_shots) + (XG_WEIGHT * xg_lam)

    return clamp(lam, 3.0, 30.0)


def canonical_corners_lambda(
    team: dict[str, Any],
    opp: dict[str, Any],
    league_shots_avg: float,
    *,
    use_trailing12: bool = False,
) -> float | None:
    attack = blended(team, "corners_for_avg")
    opp_defence = blended(opp, "corners_against_avg")
    if attack is None or opp_defence is None or not enough_history(team) or not enough_history(opp):
        return None
    lam = (0.58 * attack) + (0.42 * opp_defence)
    lam *= pressure_adjustment(team, opp, league_shots_avg)
    if use_trailing12:
        lam *= league_level_ratio(team, opp, metric_for="corners_for", metric_against="corners_against")
    return clamp(lam, 1.0, 15.0)


@dataclass
class MetricBucket:
    model: str
    market: str
    sample: str
    league: str
    line: str
    n: int = 0
    wins: int = 0
    pred_sum: float = 0.0
    actual_sum: float = 0.0
    abs_err_sum: float = 0.0
    sq_err_sum: float = 0.0
    brier_sum: float = 0.0
    log_loss_sum: float = 0.0

    def add_count(self, pred: float, actual: float) -> None:
        self.n += 1
        self.pred_sum += pred
        self.actual_sum += actual
        self.abs_err_sum += abs(pred - actual)
        self.sq_err_sum += (pred - actual) ** 2

    def add_prob(self, prob: float, actual_over: bool) -> None:
        self.wins += 1 if actual_over else 0
        self.brier_sum += brier(prob, actual_over)
        self.log_loss_sum += log_loss(prob, actual_over)

    def as_row(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "market": self.market,
            "sample": self.sample,
            "league": self.league,
            "line": self.line,
            "n": self.n,
            "mean_pred": round(self.pred_sum / self.n, 4) if self.n else "",
            "mean_actual": round(self.actual_sum / self.n, 4) if self.n else "",
            "bias": round((self.pred_sum - self.actual_sum) / self.n, 4) if self.n else "",
            "mae": round(self.abs_err_sum / self.n, 4) if self.n else "",
            "rmse": round(math.sqrt(self.sq_err_sum / self.n), 4) if self.n else "",
            "actual_over_rate": round(self.wins / self.n, 4) if self.n and self.line != "count" else "",
            "brier": round(self.brier_sum / self.n, 6) if self.n and self.line != "count" else "",
            "log_loss": round(self.log_loss_sum / self.n, 6) if self.n and self.line != "count" else "",
        }


def add_prediction(
    buckets: dict[tuple[str, str, str, str, str], MetricBucket],
    *,
    model: str,
    market: str,
    sample: str,
    league: str,
    pred_count: float,
    actual_count: float,
    lines: list[float],
    probs: dict[float, float] | None = None,
) -> None:
    count_key = (model, market, sample, league, "count")
    buckets.setdefault(count_key, MetricBucket(model, market, sample, league, "count")).add_count(pred_count, actual_count)

    for line in lines:
        line_label = f"{line:.1f}"
        key = (model, market, sample, league, line_label)
        bucket = buckets.setdefault(key, MetricBucket(model, market, sample, league, line_label))
        bucket.add_count(pred_count, actual_count)
        prob = probs.get(line) if probs else poisson_prob_over(line, pred_count)
        bucket.add_prob(prob, actual_count > line)


def league_shots_averages(form_rows: list[dict[str, Any]]) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in form_rows:
        league = str(row.get("league", "")).strip()
        current = pf(row.get("current_shots_for"), None)
        if league and current is not None:
            values[league].append(current)
    return {league: mean(vals) for league, vals in values.items()}


def estimate_alpha(values: list[float]) -> float:
    if len(values) < 100:
        return 0.0
    avg = mean(values)
    if avg <= 0:
        return 0.0
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return clamp((variance - avg) / (avg * avg), 0.0, 2.0)


def estimate_team_shots_alpha_by_date(form_rows: list[dict[str, Any]]) -> dict[tuple[str, date], float]:
    values: dict[str, list[tuple[date, float]]] = defaultdict(list)
    all_values: list[tuple[date, float]] = []
    for row in form_rows:
        league = str(row.get("league", "")).strip()
        parsed = row_date(row)
        actual = pf(row.get("current_shots_for"), None)
        if league and parsed is not None and actual is not None:
            values[league].append((parsed, actual))
            all_values.append((parsed, actual))

    alpha_by_date: dict[tuple[str, date], float] = {}
    for league, dated_values in {**values, "ALL": all_values}.items():
        dated_values = sorted(dated_values, key=lambda item: item[0])
        unique_dates = sorted({value_date for value_date, _ in dated_values})
        index = 0
        prior_values: list[float] = []
        for current_date in unique_dates:
            while index < len(dated_values) and dated_values[index][0] < current_date:
                prior_values.append(dated_values[index][1])
                index += 1
            alpha_by_date[(league, current_date)] = estimate_alpha(prior_values)
    return alpha_by_date


def latest_form_date(form_rows: list[dict[str, Any]]) -> date | None:
    dates = [parsed for row in form_rows if (parsed := row_date(row))]
    return max(dates) if dates else None


def sample_names(*, common: bool, prediction_date: date | None, recent_cutoff: date | None) -> list[str]:
    names = ["full", "common" if common else "canonical_only"]
    if prediction_date is not None and recent_cutoff is not None and prediction_date >= recent_cutoff:
        names.append("last_90_full")
        names.append("last_90_common" if common else "last_90_canonical_only")
    return names


def evaluate_current_team_shots(
    rows: list[dict[str, Any]],
    buckets: dict[tuple[str, str, str, str, str], MetricBucket],
    *,
    recent_cutoff: date | None,
) -> None:
    for row in rows:
        league = str(row.get("league", "")).strip()
        pred = pf(row.get("lambda_venue"), None) or pf(row.get("lambda_shots"), None)
        actual = pf(row.get("actual_shots"), None)
        if not league or pred is None or actual is None:
            continue
        probs = {line: pf(row.get(f"p_over_{line:.1f}"), None) for line in TEAM_SHOTS_LINES}
        probs = {line: prob for line, prob in probs.items() if prob is not None}
        for sample in sample_names(common=True, prediction_date=row_date(row), recent_cutoff=recent_cutoff):
            if sample not in {"common", "last_90_common"}:
                continue
            add_prediction(
                buckets,
                model="current",
                market="team_shots",
                sample=sample,
                league=league,
                pred_count=pred,
                actual_count=actual,
                lines=TEAM_SHOTS_LINES,
                probs=probs,
            )


def evaluate_current_corners(
    rows: list[dict[str, Any]],
    buckets: dict[tuple[str, str, str, str, str], MetricBucket],
    *,
    recent_cutoff: date | None,
) -> None:
    for row in rows:
        league = str(row.get("league", "")).strip()
        pred = pf(row.get("lambda_total"), None)
        actual = pf(row.get("actual_total"), None)
        if not league or pred is None or actual is None:
            continue
        probs = {line: pf(row.get(f"p_over_{line:.1f}"), None) for line in CORNERS_LINES}
        probs = {line: prob for line, prob in probs.items() if prob is not None}
        for sample in sample_names(common=True, prediction_date=row_date(row), recent_cutoff=recent_cutoff):
            if sample not in {"common", "last_90_common"}:
                continue
            add_prediction(
                buckets,
                model="current",
                market="corners_total",
                sample=sample,
                league=league,
                pred_count=pred,
                actual_count=actual,
                lines=CORNERS_LINES,
                probs=probs,
            )


def evaluate_canonical(
    form_rows: list[dict[str, Any]],
    buckets: dict[tuple[str, str, str, str, str], MetricBucket],
    *,
    team_shots_common_keys: set[tuple[str, str, str, str, str]],
    corners_common_keys: set[tuple[str, str, str, str]],
    recent_cutoff: date | None,
) -> None:
    rows_by_fixture: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in form_rows:
        rows_by_fixture[row_key(row)].append(row)

    league_shots_avg = league_shots_averages(form_rows)
    team_shots_alpha_by_date = estimate_team_shots_alpha_by_date(form_rows)

    for fixture_rows in rows_by_fixture.values():
        if len(fixture_rows) != 2:
            continue
        home_rows = [row for row in fixture_rows if str(row.get("venue", "")).strip() == "home"]
        away_rows = [row for row in fixture_rows if str(row.get("venue", "")).strip() == "away"]
        if len(home_rows) != 1 or len(away_rows) != 1:
            continue
        home = home_rows[0]
        away = away_rows[0]
        league = str(home.get("league", "")).strip()
        fixture_date = row_date(home)

        for team, opp in ((home, away), (away, home)):
            actual = pf(team.get("current_shots_for"), None)
            if actual is None:
                continue
            common = team_key(team) in team_shots_common_keys
            samples = sample_names(common=common, prediction_date=fixture_date, recent_cutoff=recent_cutoff)
            for model, use_market, use_nb in (
                ("canonical_form_v0", False, False),
                ("canonical_form_v1_market", True, False),
                ("canonical_form_v1_market_nb", True, True),
                ("canonical_form_v1_market_nb_t12", True, True),
                ("canonical_form_v2_current_shape_nb", False, True),
                ("canonical_form_v2_pooled_opp_nb", True, True),
            ):
                if model == "canonical_form_v2_current_shape_nb":
                    lam = canonical_team_shots_current_shape_lambda(team, opp)
                elif model == "canonical_form_v2_pooled_opp_nb":
                    lam = canonical_team_shots_pooled_opp_lambda(team, opp, use_market=use_market)
                else:
                    lam = canonical_team_shots_lambda(team, opp, use_market=use_market, use_trailing12=model.endswith("_t12"))
                if lam is None:
                    continue
                probs = None
                if use_nb:
                    alpha = 0.0
                    if fixture_date is not None:
                        alpha = team_shots_alpha_by_date.get(
                            (league, fixture_date),
                            team_shots_alpha_by_date.get(("ALL", fixture_date), 0.0),
                        )
                    probs = {line: negative_binomial_prob_over(line, lam, alpha) for line in TEAM_SHOTS_LINES}
                for sample in samples:
                    add_prediction(
                        buckets,
                        model=model,
                        market="team_shots",
                        sample=sample,
                        league=league,
                        pred_count=lam,
                        actual_count=actual,
                        lines=TEAM_SHOTS_LINES,
                        probs=probs,
                    )

        home_corners = canonical_corners_lambda(home, away, league_shots_avg.get(league, 0.0))
        away_corners = canonical_corners_lambda(away, home, league_shots_avg.get(league, 0.0))
        home_corners_t12 = canonical_corners_lambda(home, away, league_shots_avg.get(league, 0.0), use_trailing12=True)
        away_corners_t12 = canonical_corners_lambda(away, home, league_shots_avg.get(league, 0.0), use_trailing12=True)
        actual_home = pf(home.get("current_corners_for"), None)
        actual_away = pf(away.get("current_corners_for"), None)
        if home_corners is not None and away_corners is not None and actual_home is not None and actual_away is not None:
            common = row_key(home) in corners_common_keys
            for model, pred_count in (
                ("canonical_form_v0", home_corners + away_corners),
                (
                    "canonical_form_v0_t12",
                    (home_corners_t12 + away_corners_t12)
                    if home_corners_t12 is not None and away_corners_t12 is not None
                    else None,
                ),
            ):
                if pred_count is None:
                    continue
                for sample in sample_names(common=common, prediction_date=fixture_date, recent_cutoff=recent_cutoff):
                    add_prediction(
                        buckets,
                        model=model,
                        market="corners_total",
                        sample=sample,
                        league=league,
                        pred_count=pred_count,
                        actual_count=actual_home + actual_away,
                        lines=CORNERS_LINES,
                    )


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model",
        "market",
        "sample",
        "league",
        "line",
        "n",
        "mean_pred",
        "mean_actual",
        "bias",
        "mae",
        "rmse",
        "actual_over_rate",
        "brier",
        "log_loss",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_report(rows: list[dict[str, Any]]) -> str:
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    count_rows = [row for row in rows if row["line"] == "count" and row["league"] == "ALL"]
    prob_rows = [row for row in rows if row["line"] != "count" and row["league"] == "ALL"]

    lines = [
        "# Canonical Football Form Backtest",
        "",
        f"Generated: {generated}",
        "",
        "This is research-only. It compares current model outputs with a first canonical rolling-form formula.",
        "No live policy, thresholds, or published picks are changed by this report.",
        "",
        "## Count Accuracy",
        "",
        "| Model | Market | Sample | N | Mean pred | Mean actual | Bias | MAE | RMSE |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    sample_order = {
        "common": 0,
        "canonical_only": 1,
        "full": 2,
        "last_90_common": 3,
        "last_90_canonical_only": 4,
        "last_90_full": 5,
    }

    for row in sorted(
        count_rows,
        key=lambda item: (item["market"], sample_order.get(item["sample"], 99), item["model"]),
    ):
        lines.append(
            "| {model} | {market} | {sample} | {n} | {mean_pred} | {mean_actual} | {bias} | {mae} | {rmse} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Probability Calibration",
            "",
            "| Model | Market | Sample | Line | N | Actual over | Brier | Log loss |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(
        prob_rows,
        key=lambda item: (item["market"], sample_order.get(item["sample"], 99), float(item["line"]), item["model"]),
    ):
        lines.append(
            "| {model} | {market} | {sample} | {line} | {n} | {actual_over_rate} | {brier} | {log_loss} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Read This Properly",
            "",
            "- `common` means both current and canonical produced a prediction for that row.",
            "- `canonical_only` means canonical produced a prediction where current generated output was silent.",
            "- `full` is common + canonical_only for canonical models. Current has no full row because it is the baseline CSV itself.",
            "- `last_90_*` samples use the final 90 days of the canonical form table.",
            "- `canonical_form_v1_market` adds a capped pre-match 1X2 win-probability adjustment for expected game state.",
            "- `canonical_form_v1_market_nb` keeps the same lambda but converts O/U probabilities with a causal prior-data league negative-binomial dispersion estimate.",
            "- `*_t12` rows are diagnostic trailing-12-month league-level normalization replays, not live policy candidates yet.",
            "- `canonical_form_v2_current_shape_nb` is a diagnostic replay of the current model's multiplicative league-relative formula shape using canonical inputs; it is not a promotion candidate unless it beats v1/current on segment gates.",
            "- `canonical_form_v2_pooled_opp_nb` keeps canonical's additive/market/NB shape but pools opponent concession instead of using the opponent venue split.",
            "- Promotion should require full-window and last-90-day Brier/log-loss to match or beat current on the common sample, then odds/CLV checks.",
        ]
    )
    return "\n".join(lines) + "\n"


def aggregate_all(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_rows = list(rows)
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        grouped[(row["model"], row["market"], row["sample"], row["line"])].append(row)

    all_rows: list[dict[str, Any]] = []
    for (model, market, sample, line), group in grouped.items():
        n = sum(int(row["n"]) for row in group)
        if n <= 0:
            continue
        row = {
            "model": model,
            "market": market,
            "sample": sample,
            "league": "ALL",
            "line": line,
            "n": n,
            "mean_pred": round(sum(float(row["mean_pred"]) * int(row["n"]) for row in group if row["mean_pred"] != "") / n, 4),
            "mean_actual": round(sum(float(row["mean_actual"]) * int(row["n"]) for row in group if row["mean_actual"] != "") / n, 4),
            "bias": "",
            "mae": round(sum(float(row["mae"]) * int(row["n"]) for row in group if row["mae"] != "") / n, 4),
            "rmse": round(math.sqrt(sum((float(row["rmse"]) ** 2) * int(row["n"]) for row in group if row["rmse"] != "") / n), 4),
            "actual_over_rate": "",
            "brier": "",
            "log_loss": "",
        }
        row["bias"] = round(float(row["mean_pred"]) - float(row["mean_actual"]), 4)
        if line != "count":
            row["actual_over_rate"] = round(
                sum(float(row["actual_over_rate"]) * int(row["n"]) for row in group if row["actual_over_rate"] != "") / n,
                4,
            )
            row["brier"] = round(sum(float(row["brier"]) * int(row["n"]) for row in group if row["brier"] != "") / n, 6)
            row["log_loss"] = round(
                sum(float(row["log_loss"]) * int(row["n"]) for row in group if row["log_loss"] != "") / n,
                6,
            )
        all_rows.append(row)

    return all_rows + source_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest canonical football-form layer")
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--team-shots-current", type=Path, default=DEFAULT_TEAM_SHOTS_CURRENT)
    parser.add_argument("--corners-current", type=Path, default=DEFAULT_CORNERS_CURRENT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_OUT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    args = parser.parse_args()

    ensure_form_input(args.form)
    form_rows = load_csv(args.form)
    team_shots_rows = load_csv(args.team_shots_current)
    corners_rows = load_csv(args.corners_current)
    if not form_rows:
        raise SystemExit(f"Canonical form input is empty: {args.form}")
    if not team_shots_rows:
        raise SystemExit(f"Current team-shots input is empty: {args.team_shots_current}")
    if not corners_rows:
        raise SystemExit(f"Current corners input is empty: {args.corners_current}")
    latest_date = latest_form_date(form_rows)
    recent_cutoff = latest_date - timedelta(days=90) if latest_date else None

    buckets: dict[tuple[str, str, str, str, str], MetricBucket] = {}
    evaluate_current_team_shots(team_shots_rows, buckets, recent_cutoff=recent_cutoff)
    evaluate_current_corners(corners_rows, buckets, recent_cutoff=recent_cutoff)
    evaluate_canonical(
        form_rows,
        buckets,
        team_shots_common_keys={team_key(row) for row in team_shots_rows},
        corners_common_keys={row_key(row) for row in corners_rows},
        recent_cutoff=recent_cutoff,
    )

    rows = [bucket.as_row() for bucket in buckets.values()]
    rows = aggregate_all(rows)
    rows.sort(key=lambda row: (row["market"], row["sample"], row["model"], row["league"], str(row["line"])))

    write_summary(args.summary_out, rows)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(render_report(rows), encoding="utf-8")

    print(f"Wrote {args.summary_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
