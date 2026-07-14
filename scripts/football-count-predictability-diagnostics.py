#!/usr/bin/env python3
"""Reproducible causal predictability audit for candidate football count markets."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from settlement_utils import normalize_team_name, parse_isoish_date


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "football-count-predictability.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "football-count-predictability.md"
DECAY = 0.93
WINDOW = 20
MIN_TEAM_MATCHES = 5

METRICS = {
    "shots": ("HS", "AS"),
    "shots_on_target": ("HST", "AST"),
    "corners": ("HC", "AC"),
    "fouls": ("HF", "AF"),
    "cards": ("home_cards", "away_cards"),
}


def number(value: Any) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0.0 else None


def ema(values: list[float], decay: float = DECAY) -> float:
    weights = [decay ** (len(values) - 1 - index) for index in range(len(values))]
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    mean_left = statistics.fmean(left)
    mean_right = statistics.fmean(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    left_ss = sum((a - mean_left) ** 2 for a in left)
    right_ss = sum((b - mean_right) ** 2 for b in right)
    denominator = math.sqrt(left_ss * right_ss)
    return numerator / denominator if denominator > 0.0 else None


def load_matches(path: Path) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            day = parse_isoish_date(str(row.get("Date") or ""))
            league = str(row.get("league") or "").strip().lower()
            home = normalize_team_name(str(row.get("HomeTeam") or ""))
            away = normalize_team_name(str(row.get("AwayTeam") or ""))
            if day is None or not league or not home or not away:
                continue
            home_yellow = number(row.get("HY"))
            away_yellow = number(row.get("AY"))
            home_red = number(row.get("HR")) or 0.0
            away_red = number(row.get("AR")) or 0.0
            enriched = dict(row)
            enriched.update(
                {
                    "day": day,
                    "league_key": league,
                    "home_key": home,
                    "away_key": away,
                    "home_cards": (home_yellow + home_red) if home_yellow is not None else None,
                    "away_cards": (away_yellow + away_red) if away_yellow is not None else None,
                }
            )
            matches.append(enriched)
    return sorted(matches, key=lambda row: (row["day"], row["league_key"], row["home_key"]))


def audit(matches: list[dict[str, Any]]) -> dict[str, Any]:
    team_for: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    team_against: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    league_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    observations: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    all_totals: dict[str, list[float]] = defaultdict(list)

    by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for match in matches:
        by_day[match["day"]].append(match)

    for day in sorted(by_day):
        updates: list[tuple[str, str, str, float, float]] = []
        for match in by_day[day]:
            league = match["league_key"]
            home = match["home_key"]
            away = match["away_key"]
            for metric, (home_field, away_field) in METRICS.items():
                home_actual = number(match.get(home_field))
                away_actual = number(match.get(away_field))
                if home_actual is None or away_actual is None:
                    continue
                all_totals[metric].append(home_actual + away_actual)
                league_history = league_values[(league, metric)]
                for team, opponent, actual in (
                    (home, away, home_actual),
                    (away, home, away_actual),
                ):
                    attack = team_for[(league, team, metric)]
                    defense = team_against[(league, opponent, metric)]
                    if (
                        len(attack) >= MIN_TEAM_MATCHES
                        and len(defense) >= MIN_TEAM_MATCHES
                        and len(league_history) >= 100
                    ):
                        model = (ema(attack[-WINDOW:]) + ema(defense[-WINDOW:])) / 2.0
                        baseline = statistics.fmean(league_history)
                        observations[metric].append((actual, model, baseline))
                updates.append((league, home, metric, home_actual, away_actual))
                updates.append((league, away, metric, away_actual, home_actual))

        # Same-day fixtures cannot leak into one another.
        for league, team, metric, actual_for, actual_against in updates:
            for values, value in (
                (team_for[(league, team, metric)], actual_for),
                (team_against[(league, team, metric)], actual_against),
            ):
                values.append(value)
                if len(values) > WINDOW:
                    del values[0]
            league_values[(league, metric)].append(actual_for)

    result: dict[str, Any] = {}
    for metric in METRICS:
        rows = observations[metric]
        actuals = [row[0] for row in rows]
        models = [row[1] for row in rows]
        baselines = [row[2] for row in rows]
        model_mae = statistics.fmean(abs(actual - model) for actual, model, _ in rows) if rows else None
        baseline_mae = statistics.fmean(abs(actual - baseline) for actual, _, baseline in rows) if rows else None
        improvement = (
            (baseline_mae - model_mae) / baseline_mae
            if model_mae is not None and baseline_mae and baseline_mae > 0.0
            else None
        )
        totals = all_totals[metric]
        total_mean = statistics.fmean(totals) if totals else None
        total_variance = statistics.variance(totals) if len(totals) >= 2 else None
        result[metric] = {
            "observations": len(rows),
            "model_actual_correlation": correlation(models, actuals),
            "model_mae": model_mae,
            "league_baseline_mae": baseline_mae,
            "mae_improvement": improvement,
            "match_total_mean": total_mean,
            "match_total_variance": total_variance,
            "match_total_variance_to_mean": (
                total_variance / total_mean
                if total_variance is not None and total_mean and total_mean > 0.0
                else None
            ),
        }
    return result


def fmt(value: float | None, digits: int = 3) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Football Count Predictability Diagnostics",
        "",
        f"Generated: {payload['generated_at_utc']}",
        f"Source matches: {payload['source_matches']}",
        "",
        "Causal EMA20 attack/opponent-allowance predictions are compared with a prior league mean. Same-day fixtures are scored before any same-day update. This measures count predictability only, not betting edge.",
        "",
        "| Market | N | Corr | Model MAE | League MAE | MAE improvement | Total var/mean |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for metric in METRICS:
        item = payload["metrics"][metric]
        improvement = item["mae_improvement"]
        improvement_text = f"{improvement:.1%}" if improvement is not None else "-"
        lines.append(
            f"| {metric.replace('_', ' ').title()} | {item['observations']} | "
            f"{fmt(item['model_actual_correlation'])} | {fmt(item['model_mae'])} | "
            f"{fmt(item['league_baseline_mae'])} | {improvement_text} | "
            f"{fmt(item['match_total_variance_to_mean'])} |"
        )
    lines.extend(
        [
            "",
            "Interpretation: a positive MAE improvement justifies further modelling research. It does not authorize signals without paired real prices, settlement and CLV.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit causal predictability of football count markets")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    matches = load_matches(args.source)
    try:
        source_label = str(args.source.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        source_label = str(args.source)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": source_label,
        "source_matches": len(matches),
        "method": {
            "window": WINDOW,
            "decay": DECAY,
            "minimum_team_matches": MIN_TEAM_MATCHES,
            "same_day_updates": "blocked",
        },
        "metrics": audit(matches),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(render_report(payload), encoding="utf-8")
    print(f"Football count diagnostics: matches={len(matches)} report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
