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
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
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


def pressure_adjustment(team: dict[str, Any], opp: dict[str, Any], league_shots_avg: float) -> float:
    team_shots = blended(team, "shots_for_avg")
    opp_conceded = blended(opp, "shots_against_avg")
    if team_shots is None or opp_conceded is None or league_shots_avg <= 0:
        return 1.0
    pressure = ((team_shots / league_shots_avg) + (opp_conceded / league_shots_avg)) / 2.0
    return clamp(1.0 + ((pressure - 1.0) * 0.18), 0.88, 1.12)


def canonical_team_shots_lambda(team: dict[str, Any], opp: dict[str, Any]) -> float | None:
    team_venue = str(team.get("venue", "")).strip()
    opp_venue = str(opp.get("venue", "")).strip()
    attack = blended_prefer(team, venue_field("shots_for", team_venue), "shots_for_avg")
    opp_defence = blended_prefer(opp, venue_field("shots_against", opp_venue), "shots_against_avg")
    if attack is None or opp_defence is None or not enough_history(team) or not enough_history(opp):
        return None
    lam = (0.55 * attack) + (0.45 * opp_defence)
    lam *= quality_adjustment(team, opp)
    return clamp(lam, 3.0, 30.0)


def canonical_corners_lambda(
    team: dict[str, Any],
    opp: dict[str, Any],
    league_shots_avg: float,
) -> float | None:
    attack = blended(team, "corners_for_avg")
    opp_defence = blended(opp, "corners_against_avg")
    if attack is None or opp_defence is None or not enough_history(team) or not enough_history(opp):
        return None
    lam = (0.58 * attack) + (0.42 * opp_defence)
    lam *= pressure_adjustment(team, opp, league_shots_avg)
    return clamp(lam, 1.0, 15.0)


@dataclass
class MetricBucket:
    model: str
    market: str
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
    buckets: dict[tuple[str, str, str, str], MetricBucket],
    *,
    model: str,
    market: str,
    league: str,
    pred_count: float,
    actual_count: float,
    lines: list[float],
    probs: dict[float, float] | None = None,
) -> None:
    count_key = (model, market, league, "count")
    buckets.setdefault(count_key, MetricBucket(model, market, league, "count")).add_count(pred_count, actual_count)

    for line in lines:
        line_label = f"{line:.1f}"
        key = (model, market, league, line_label)
        bucket = buckets.setdefault(key, MetricBucket(model, market, league, line_label))
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


def evaluate_current_team_shots(rows: list[dict[str, Any]], buckets: dict[tuple[str, str, str, str], MetricBucket]) -> None:
    for row in rows:
        league = str(row.get("league", "")).strip()
        pred = pf(row.get("lambda_venue"), None) or pf(row.get("lambda_shots"), None)
        actual = pf(row.get("actual_shots"), None)
        if not league or pred is None or actual is None:
            continue
        probs = {line: pf(row.get(f"p_over_{line:.1f}"), None) for line in TEAM_SHOTS_LINES}
        probs = {line: prob for line, prob in probs.items() if prob is not None}
        add_prediction(
            buckets,
            model="current",
            market="team_shots",
            league=league,
            pred_count=pred,
            actual_count=actual,
            lines=TEAM_SHOTS_LINES,
            probs=probs,
        )


def evaluate_current_corners(rows: list[dict[str, Any]], buckets: dict[tuple[str, str, str, str], MetricBucket]) -> None:
    for row in rows:
        league = str(row.get("league", "")).strip()
        pred = pf(row.get("lambda_total"), None)
        actual = pf(row.get("actual_total"), None)
        if not league or pred is None or actual is None:
            continue
        probs = {line: pf(row.get(f"p_over_{line:.1f}"), None) for line in CORNERS_LINES}
        probs = {line: prob for line, prob in probs.items() if prob is not None}
        add_prediction(
            buckets,
            model="current",
            market="corners_total",
            league=league,
            pred_count=pred,
            actual_count=actual,
            lines=CORNERS_LINES,
            probs=probs,
        )


def evaluate_canonical(
    form_rows: list[dict[str, Any]],
    buckets: dict[tuple[str, str, str, str], MetricBucket],
    *,
    team_shots_common_keys: set[tuple[str, str, str, str, str]],
    corners_common_keys: set[tuple[str, str, str, str]],
) -> None:
    rows_by_fixture: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in form_rows:
        rows_by_fixture[row_key(row)].append(row)

    league_shots_avg = league_shots_averages(form_rows)

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

        for team, opp in ((home, away), (away, home)):
            lam = canonical_team_shots_lambda(team, opp)
            actual = pf(team.get("current_shots_for"), None)
            if lam is None or actual is None:
                continue
            common = team_key(team) in team_shots_common_keys
            add_prediction(
                buckets,
                model="canonical_form_v0_full",
                market="team_shots",
                league=league,
                pred_count=lam,
                actual_count=actual,
                lines=TEAM_SHOTS_LINES,
            )
            if common:
                add_prediction(
                    buckets,
                    model="canonical_form_v0_common",
                    market="team_shots",
                    league=league,
                    pred_count=lam,
                    actual_count=actual,
                    lines=TEAM_SHOTS_LINES,
                )

        home_corners = canonical_corners_lambda(home, away, league_shots_avg.get(league, 0.0))
        away_corners = canonical_corners_lambda(away, home, league_shots_avg.get(league, 0.0))
        actual_home = pf(home.get("current_corners_for"), None)
        actual_away = pf(away.get("current_corners_for"), None)
        if home_corners is not None and away_corners is not None and actual_home is not None and actual_away is not None:
            common = row_key(home) in corners_common_keys
            add_prediction(
                buckets,
                model="canonical_form_v0_full",
                market="corners_total",
                league=league,
                pred_count=home_corners + away_corners,
                actual_count=actual_home + actual_away,
                lines=CORNERS_LINES,
            )
            if common:
                add_prediction(
                    buckets,
                    model="canonical_form_v0_common",
                    market="corners_total",
                    league=league,
                    pred_count=home_corners + away_corners,
                    actual_count=actual_home + actual_away,
                    lines=CORNERS_LINES,
                )


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model",
        "market",
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
        "| Model | Market | N | Mean pred | Mean actual | Bias | MAE | RMSE |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for row in sorted(count_rows, key=lambda item: (item["market"], item["model"])):
        lines.append(
            "| {model} | {market} | {n} | {mean_pred} | {mean_actual} | {bias} | {mae} | {rmse} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## Probability Calibration",
            "",
            "| Model | Market | Line | N | Actual over | Brier | Log loss |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(prob_rows, key=lambda item: (item["market"], float(item["line"]), item["model"])):
        lines.append(
            "| {model} | {market} | {line} | {n} | {actual_over_rate} | {brier} | {log_loss} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## Read This Properly",
            "",
            "- `current` is whatever the existing generated prediction CSV currently contains.",
            "- `canonical_form_v0_common` is tested only on rows where the current generated output also exists.",
            "- `canonical_form_v0_full` is the same formula over the full eligible historical canonical table.",
            "- If v0 is worse but close, the canonical layer is still useful as plumbing, not yet as a model replacement.",
            "- If v0 beats current on Brier/log-loss over common lines, then we test it against odds/CLV before promotion.",
        ]
    )
    return "\n".join(lines) + "\n"


def aggregate_all(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_rows = list(rows)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        grouped[(row["model"], row["market"], row["line"])].append(row)

    all_rows: list[dict[str, Any]] = []
    for (model, market, line), group in grouped.items():
        n = sum(int(row["n"]) for row in group)
        if n <= 0:
            continue
        row = {
            "model": model,
            "market": market,
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

    form_rows = load_csv(args.form)
    team_shots_rows = load_csv(args.team_shots_current)
    corners_rows = load_csv(args.corners_current)

    buckets: dict[tuple[str, str, str, str], MetricBucket] = {}
    evaluate_current_team_shots(team_shots_rows, buckets)
    evaluate_current_corners(corners_rows, buckets)
    evaluate_canonical(
        form_rows,
        buckets,
        team_shots_common_keys={team_key(row) for row in team_shots_rows},
        corners_common_keys={row_key(row) for row in corners_rows},
    )

    rows = [bucket.as_row() for bucket in buckets.values()]
    rows = aggregate_all(rows)
    rows.sort(key=lambda row: (row["market"], row["model"], row["league"], str(row["line"])))

    write_summary(args.summary_out, rows)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(render_report(rows), encoding="utf-8")

    print(f"Wrote {args.summary_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
