#!/usr/bin/env python3
"""Registered Team Shots v4 distribution experiment.

The canonical v3 EMA20 mean is frozen. This experiment changes only:

1. NB2 dispersion fitted against the frozen, observation-specific means;
2. per-team dispersion partially pooled to its league prior; and
3. a diagnostic market blend fitted on an earlier odds-capture slice.

Nothing in this file writes live predictions or promotion state.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from football_counts import fit_dispersion_alpha_mle, prob_over  # noqa: E402
from football_team_names import football_form_team_key  # noqa: E402
from football_market import (  # noqa: E402
    blend_logit,
    brier,
    fit_blend_weight,
    fit_over_vig_share,
    log_loss,
    shading_aware_devig,
)
from model_experiment_integrity import verify_locked_input  # noqa: E402


DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_ODDS = ROOT / "data" / "team-shots" / "team-shots-odds-history.csv"
DEFAULT_RESULTS = ROOT / "data" / "team-shots" / "team-shots-v4-fold-results.csv"
DEFAULT_REPORT = ROOT / "data" / "team-shots" / "team-shots-v4-fold-report.md"
DEFAULT_LOCK = ROOT / "data" / "team-shots" / "team-shots-v4-lock.json"
VALIDATION_SEASONS = ("2024-2025", "2025-2026")
TEAM_PRIOR_WEIGHT = 60
LINES = (9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5)
TRUE_CLOSE_HOURS = 2.0


@dataclass(frozen=True)
class Prediction:
    match_date: date
    league: str
    season: str
    team: str
    team_key: str
    opponent: str
    actual: int
    lam: float


@dataclass(frozen=True)
class MarketQuote:
    match_date: date
    kickoff_at: datetime
    league: str
    event_id: str
    team: str
    line: float
    over_odds: float
    under_odds: float
    captured_at: datetime
    hours_to_kickoff: float


def parse_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalized_name(value: Any) -> str:
    return football_form_team_key(value)


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing required input: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_canonical_module() -> Any:
    path = SCRIPTS / "backtest-football-form-layer.py"
    spec = importlib.util.spec_from_file_location("football_form_backtest", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import canonical form model from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_predictions(form_rows: list[dict[str, str]]) -> list[Prediction]:
    canonical = load_canonical_module()
    fixtures: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in form_rows:
        key = (
            str(row.get("date", "")),
            str(row.get("league", "")),
            str(row.get("home_team", "")),
            str(row.get("away_team", "")),
        )
        fixtures[key].append(row)

    output: list[Prediction] = []
    for rows in fixtures.values():
        home = [row for row in rows if row.get("venue") == "home"]
        away = [row for row in rows if row.get("venue") == "away"]
        if len(home) != 1 or len(away) != 1:
            continue
        for team, opponent in ((home[0], away[0]), (away[0], home[0])):
            match_date = parse_date(team.get("date"))
            actual = parse_float(team.get("current_shots_for"))
            lam = canonical.canonical_team_shots_ema20_lambda(team, opponent, use_market=True)
            if match_date is None or actual is None or lam is None:
                continue
            output.append(
                Prediction(
                    match_date=match_date,
                    league=str(team.get("league", "")).strip(),
                    season=str(team.get("season", "")).strip(),
                    team=str(team.get("team", "")).strip(),
                    team_key=str(team.get("team_key", "")).strip() or normalized_name(team.get("team")),
                    opponent=str(team.get("opponent", "")).strip(),
                    actual=max(0, int(round(actual))),
                    lam=float(lam),
                )
            )
    return sorted(output, key=lambda row: (row.match_date, row.league, row.team_key))


def fitted_alphas(training: list[Prediction]) -> tuple[dict[str, float], dict[tuple[str, str], float]]:
    by_league: dict[str, list[tuple[float, float]]] = defaultdict(list)
    by_team: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for row in training:
        pair = (float(row.actual), row.lam)
        by_league[row.league].append(pair)
        by_team[(row.league, row.team_key)].append(pair)

    pooled = fit_dispersion_alpha_mle(
        [(actual, lam) for rows in by_league.values() for actual, lam in rows],
        min_sample=30,
    )
    league_alpha = {
        league: fit_dispersion_alpha_mle(rows, fallback=pooled, min_sample=30)
        for league, rows in by_league.items()
    }
    team_alpha: dict[tuple[str, str], float] = {}
    for key, rows in by_team.items():
        league = key[0]
        prior = league_alpha.get(league, pooled)
        raw = fit_dispersion_alpha_mle(rows, fallback=prior, min_sample=10)
        sample = len(rows)
        team_alpha[key] = ((sample * raw) + (TEAM_PRIOR_WEIGHT * prior)) / (sample + TEAM_PRIOR_WEIGHT)
    return league_alpha, team_alpha


def score_fold(
    season: str,
    predictions: list[Prediction],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validation = [row for row in predictions if row.season == season]
    if not validation:
        return [], {"season": season, "status": "NO_VALIDATION_ROWS"}
    first_date = min(row.match_date for row in validation)
    training = [row for row in predictions if row.match_date < first_date]
    league_alpha, team_alpha = fitted_alphas(training)
    pooled_alpha = fit_dispersion_alpha_mle(
        [(row.actual, row.lam) for row in training],
        min_sample=30,
    )

    models = ("poisson", "fixed_alpha_025", "league_mle", "hierarchical_mle")
    totals: dict[str, dict[str, float]] = {
        model: {"brier": 0.0, "log_loss": 0.0, "n": 0.0} for model in models
    }
    league_totals: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {model: {"brier": 0.0, "log_loss": 0.0, "n": 0.0} for model in models}
    )
    for row in validation:
        league_value = league_alpha.get(row.league, pooled_alpha)
        hierarchical_value = team_alpha.get((row.league, row.team_key), league_value)
        alpha_by_model = {
            "poisson": 0.0,
            "fixed_alpha_025": 0.25,
            "league_mle": league_value,
            "hierarchical_mle": hierarchical_value,
        }
        for line in LINES:
            actual_over = row.actual > line
            probabilities: dict[str, float] = {}
            for model, alpha in alpha_by_model.items():
                distribution = "poisson" if model == "poisson" else "negative_binomial"
                probability = prob_over(line, row.lam, distribution=distribution, alpha=alpha)
                probabilities[model] = probability
                totals[model]["brier"] += brier(probability, actual_over)
                totals[model]["log_loss"] += log_loss(probability, actual_over)
                totals[model]["n"] += 1
                league_totals[row.league][model]["brier"] += brier(probability, actual_over)
                league_totals[row.league][model]["log_loss"] += log_loss(probability, actual_over)
                league_totals[row.league][model]["n"] += 1

    mae = mean(abs(row.actual - row.lam) for row in validation)
    bias = mean(row.lam - row.actual for row in validation)
    summary: dict[str, Any] = {
        "season": season,
        "status": "OK",
        "train_teams": len(training),
        "validation_teams": len(validation),
        "first_validation_date": first_date.isoformat(),
        "count_mae": mae,
        "count_bias": bias,
        "pooled_alpha": pooled_alpha,
    }
    for model, values in totals.items():
        count = max(1.0, values["n"])
        summary[f"{model}_brier"] = values["brier"] / count
        summary[f"{model}_log_loss"] = values["log_loss"] / count
    summary["by_league"] = []
    for league, model_values in sorted(league_totals.items()):
        league_summary: dict[str, Any] = {"league": league}
        for model, values in model_values.items():
            count = max(1.0, values["n"])
            league_summary["team_rows"] = int(count / len(LINES))
            league_summary[f"{model}_brier"] = values["brier"] / count
            league_summary[f"{model}_log_loss"] = values["log_loss"] / count
        summary["by_league"].append(league_summary)
    return [], summary


def paired_market_quotes(odds_rows: list[dict[str, str]]) -> list[MarketQuote]:
    snapshots: dict[tuple[str, str, float, datetime], dict[str, Any]] = {}
    for row in odds_rows:
        if str(row.get("market", "")).strip().upper() != "TEAM_SHOTS":
            continue
        captured = parse_datetime(row.get("captured_at"))
        kickoff = parse_datetime(row.get("kickoff_at"))
        match_date = parse_date(row.get("match_date"))
        line = parse_float(row.get("line"))
        odds = parse_float(row.get("odds_decimal"))
        side = str(row.get("side", "")).strip().lower()
        if None in (captured, kickoff, match_date, line, odds) or side not in {"over", "under"}:
            continue
        if odds is None or odds <= 1.0 or captured is None or kickoff is None or captured > kickoff:
            continue
        key = (str(row.get("event_id", "")), normalized_name(row.get("team")), float(line), captured)
        payload = snapshots.setdefault(
            key,
            {
                "match_date": match_date,
                "kickoff": kickoff,
                "league": str(row.get("competition", "")).strip(),
                "event_id": str(row.get("event_id", "")).strip(),
                "team": str(row.get("team", "")).strip(),
                "line": float(line),
                "captured": captured,
            },
        )
        payload[side] = float(odds)

    quotes: list[MarketQuote] = []
    for payload in snapshots.values():
        if "over" not in payload or "under" not in payload:
            continue
        hours = (payload["kickoff"] - payload["captured"]).total_seconds() / 3600.0
        quotes.append(
            MarketQuote(
                match_date=payload["match_date"],
                kickoff_at=payload["kickoff"],
                league=payload["league"],
                event_id=payload["event_id"],
                team=payload["team"],
                line=payload["line"],
                over_odds=payload["over"],
                under_odds=payload["under"],
                captured_at=payload["captured"],
                hours_to_kickoff=hours,
            )
        )
    return sorted(quotes, key=lambda row: (row.match_date, row.event_id, row.team, row.line, row.captured_at))


def market_diagnostic(predictions: list[Prediction], odds_rows: list[dict[str, str]]) -> dict[str, Any]:
    prediction_index = {
        (row.match_date, normalized_name(row.team)): row
        for row in predictions
    }
    by_market: dict[tuple[str, str, float], list[MarketQuote]] = defaultdict(list)
    for quote in paired_market_quotes(odds_rows):
        by_market[(quote.event_id, normalized_name(quote.team), quote.line)].append(quote)

    observations: list[dict[str, Any]] = []
    for quotes in by_market.values():
        ordered = sorted(quotes, key=lambda row: row.captured_at)
        publication = ordered[0]
        close = ordered[-1]
        prediction = prediction_index.get((publication.match_date, normalized_name(publication.team)))
        if prediction is None:
            continue
        observations.append(
            {
                "date": publication.match_date,
                "league": prediction.league,
                "actual_over": prediction.actual > publication.line,
                "line": publication.line,
                "lambda": prediction.lam,
                "over_odds": publication.over_odds,
                "under_odds": publication.under_odds,
                "close_over_odds": close.over_odds,
                "close_under_odds": close.under_odds,
                "close_hours": close.hours_to_kickoff,
            }
        )
    observations.sort(key=lambda row: row["date"])
    if len(observations) < 40:
        return {"status": "INSUFFICIENT_MATCHED_MARKET_ROWS", "matched": len(observations)}

    split = max(20, int(len(observations) * 0.60))
    train = observations[:split]
    validation = observations[split:]
    alpha = fit_dispersion_alpha_mle(
        [(row.actual, row.lam) for row in predictions if row.match_date < validation[0]["date"]],
        min_sample=30,
    )
    vig_share = fit_over_vig_share(
        [(row["over_odds"], row["under_odds"], row["actual_over"]) for row in train],
        min_sample=20,
    )

    def probabilities(row: dict[str, Any]) -> tuple[float, float]:
        model_probability = prob_over(
            row["line"], row["lambda"], distribution="negative_binomial", alpha=alpha
        )
        market_probability, _, _ = shading_aware_devig(
            row["over_odds"], row["under_odds"], over_vig_share=vig_share
        )
        return model_probability, market_probability

    weight = fit_blend_weight(
        [(model, market, row["actual_over"]) for row in train for model, market in [probabilities(row)]]
    )
    scored = []
    for row in validation:
        model_probability, market_probability = probabilities(row)
        blended = blend_logit(model_probability, market_probability, weight)
        scored.append((row, model_probability, market_probability, blended))

    true_close = [item for item in scored if item[0]["close_hours"] <= TRUE_CLOSE_HOURS]
    return {
        "status": "DIAGNOSTIC_ONLY",
        "matched": len(observations),
        "train": len(train),
        "validation": len(validation),
        "split_date": validation[0]["date"].isoformat(),
        "alpha": alpha,
        "over_vig_share": vig_share,
        "model_weight": weight,
        "market_brier": mean(brier(market, row["actual_over"]) for row, _, market, _ in scored),
        "blend_brier": mean(brier(blended, row["actual_over"]) for row, _, _, blended in scored),
        "model_brier": mean(brier(model, row["actual_over"]) for row, model, _, _ in scored),
        "market_log_loss": mean(log_loss(market, row["actual_over"]) for row, _, market, _ in scored),
        "blend_log_loss": mean(log_loss(blended, row["actual_over"]) for row, _, _, blended in scored),
        "true_close": len(true_close),
        "true_close_coverage": len(true_close) / max(1, len(scored)),
    }


def write_results(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["fold", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summary_csv_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "season",
        "status",
        "train_teams",
        "validation_teams",
        "first_validation_date",
        "count_mae",
        "count_bias",
        "pooled_alpha",
        "poisson_brier",
        "fixed_alpha_025_brier",
        "league_mle_brier",
        "hierarchical_mle_brier",
        "poisson_log_loss",
        "fixed_alpha_025_log_loss",
        "league_mle_log_loss",
        "hierarchical_mle_log_loss",
    )
    return [{field: row.get(field, "") for field in fields} for row in summaries]


def metric(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_report(path: Path, summaries: list[dict[str, Any]], market: dict[str, Any]) -> None:
    count_gate = bool(summaries) and all(
        row.get("status") == "OK"
        and row["hierarchical_mle_brier"] < row["fixed_alpha_025_brier"]
        and row["hierarchical_mle_log_loss"] <= row["fixed_alpha_025_log_loss"]
        and all(
            league["hierarchical_mle_brier"] <= league["fixed_alpha_025_brier"]
            for league in row.get("by_league", [])
        )
        for row in summaries
    )
    lines = [
        "# Team Shots v4 registered experiment",
        "",
        "**Status: research only. The live v3 mean and routing are unchanged.**",
        "",
        "v4 freezes the canonical EMA20 v3 mean and tests only NB2 dispersion. "
        "Per-team alpha is partially pooled to league alpha with `k=60`.",
        "",
        f"- Count-distribution gate: **{'PASS' if count_gate else 'FAIL'}**",
        "- Market/sell gate: **BLOCKED** pending the registered 2026-27 true-close sample.",
        "",
        "## Walk-forward count-distribution folds",
        "",
        "| Fold | Train team rows | Validation team rows | MAE | Bias | Poisson Brier | Fixed a=.25 | League MLE | Hierarchical MLE | Hierarchical log loss |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        if row.get("status") != "OK":
            lines.append(f"| {row['season']} | - | - | - | - | - | - | - | - | {row['status']} |")
            continue
        lines.append(
            "| {season} | {train} | {valid} | {mae} | {bias} | {poisson} | {fixed} | {league} | {hierarchical} | {hierarchical_ll} |".format(
                season=row["season"],
                train=row["train_teams"],
                valid=row["validation_teams"],
                mae=metric(row["count_mae"]),
                bias=metric(row["count_bias"]),
                poisson=metric(row["poisson_brier"]),
                fixed=metric(row["fixed_alpha_025_brier"]),
                league=metric(row["league_mle_brier"]),
                hierarchical=metric(row["hierarchical_mle_brier"]),
                hierarchical_ll=metric(row["hierarchical_mle_log_loss"]),
            )
        )
    lines.extend(["", "### Per-league Brier guard", "", "| Fold | League | Team rows | Fixed a=.25 | Hierarchical MLE | Delta |", "|---|---|---:|---:|---:|---:|"])
    for row in summaries:
        for league in row.get("by_league", []):
            delta = league["hierarchical_mle_brier"] - league["fixed_alpha_025_brier"]
            lines.append(
                f"| {row['season']} | {league['league']} | {league['team_rows']} | "
                f"{league['fixed_alpha_025_brier']:.4f} | {league['hierarchical_mle_brier']:.4f} | {delta:+.4f} |"
            )
    lines.extend(
        [
            "",
            "The count MAE/bias columns are identical across distribution variants because the mean is deliberately frozen.",
            "",
            "## Captured-market diagnostic",
            "",
            f"- Status: **{market.get('status', 'UNKNOWN')}**",
            f"- Matched two-way market rows: {market.get('matched', 0)}",
        ]
    )
    if market.get("status") == "DIAGNOSTIC_ONLY":
        lines.extend(
            [
                f"- Earlier/later temporal split: {market['train']} / {market['validation']} at {market['split_date']}",
                f"- Fitted over-vig share: {metric(market['over_vig_share'], 3)}",
                f"- Fitted model logit weight: {metric(market['model_weight'], 3)}",
                f"- Validation Brier, market / model / blend: {metric(market['market_brier'])} / {metric(market['model_brier'])} / {metric(market['blend_brier'])}",
                f"- Validation log loss, market / blend: {metric(market['market_log_loss'])} / {metric(market['blend_log_loss'])}",
                f"- True-close coverage (<=2h): {market['true_close']}/{market['validation']} ({market['true_close_coverage']:.1%})",
                "",
                "This is not a sell gate: the market sample begins in April 2026 and true-close coverage is too low. "
                "It exists to prevent us from mistaking a model-only probability improvement for a takeable betting edge.",
            ]
        )
    lines.extend(
        [
            "",
            "## Locked decision rule",
            "",
            "- Continue to prospective shadow only if hierarchical NB improves both validation folds versus fixed alpha and does not regress log loss.",
            "- Sellability still requires >=150 settled real-price bets, true-close coverage >=70%, and mean true-close CLV >=+0.5%.",
            "- No MD1-MD3 bets and no live wiring from this report.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--odds", type=Path, default=DEFAULT_ODDS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args()

    verify_locked_input(args.lock, "team_rolling_form", args.form)
    predictions = build_predictions(load_csv(args.form))
    summaries: list[dict[str, Any]] = []
    for season in VALIDATION_SEASONS:
        _, summary = score_fold(season, predictions)
        summaries.append(summary)
    market = market_diagnostic(predictions, load_csv(args.odds))
    write_results(args.results, summary_csv_rows(summaries))
    write_report(args.report, summaries, market)
    print(f"Predictions: {len(predictions)}")
    print(f"Wrote {args.results.resolve().relative_to(ROOT)}")
    print(f"Wrote {args.report.resolve().relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
