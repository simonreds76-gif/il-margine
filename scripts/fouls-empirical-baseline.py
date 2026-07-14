#!/usr/bin/env python3
"""Reproduce the registered Team Fouls v1 M1 empirical baseline."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "fouls-empirical-baseline.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "fouls-empirical-baseline.md"
LEAGUE_LABELS = {
    "bundesliga": "Bundesliga",
    "epl": "EPL",
    "la-liga": "La Liga",
    "ligue-1": "Ligue 1",
    "serie-a": "Serie A",
}
MIN_REFEREE_MATCHES = 10
REGISTERED_REFEREE_K = 18
REGISTERED_LINES = (9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5)


def number(value: object) -> float | None:
    try:
        parsed = float(str(value or "").strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0.0 else None


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    return statistics.correlation(left, right)


def leg_structure(rows: Iterable[dict[str, str]]) -> dict[str, dict[str, float | int]]:
    values: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        home = number(row.get("HF"))
        away = number(row.get("AF"))
        league = str(row.get("league") or "").strip().lower()
        if home is None or away is None or league not in LEAGUE_LABELS:
            continue
        values[league].append((home, away))
        values["pooled"].append((home, away))

    result: dict[str, dict[str, float | int]] = {}
    for league in (*LEAGUE_LABELS, "pooled"):
        pairs = values[league]
        home = [pair[0] for pair in pairs]
        away = [pair[1] for pair in pairs]
        totals = [left + right for left, right in pairs]
        home_mean = statistics.fmean(home)
        away_mean = statistics.fmean(away)
        home_vmr = statistics.pvariance(home) / home_mean
        away_vmr = statistics.pvariance(away) / away_mean
        total_vmr = statistics.pvariance(totals) / statistics.fmean(totals)
        covariance = statistics.fmean(
            (left - home_mean) * (right - away_mean) for left, right in pairs
        )
        nu = covariance / (home_mean * away_mean)
        result[league] = {
            "n": len(pairs),
            "home_mean": home_mean,
            "home_vmr": home_vmr,
            "away_mean": away_mean,
            "away_vmr": away_vmr,
            "total_vmr": total_vmr,
            "home_away_correlation": statistics.correlation(home, away),
            "nu_hat_raw_ceiling": nu,
            "alpha_home_after_raw_frailty": ((home_vmr - 1.0) / home_mean) - nu,
            "alpha_away_after_raw_frailty": ((away_vmr - 1.0) / away_mean) - nu,
            "away_gap": away_mean - home_mean,
        }
    return result


def referee_baseline(rows: Iterable[dict[str, str]]) -> dict[str, Any]:
    league_coverage: dict[str, dict[str, int]] = {
        league: {"usable": 0, "with_referee": 0} for league in LEAGUE_LABELS
    }
    epl_referees: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        league = str(row.get("league") or "").strip().lower()
        home = number(row.get("HF"))
        away = number(row.get("AF"))
        if league not in league_coverage or home is None or away is None:
            continue
        league_coverage[league]["usable"] += 1
        referee = str(row.get("Referee") or "").strip()
        if referee:
            league_coverage[league]["with_referee"] += 1
            if league == "epl":
                epl_referees[referee].append(home + away)

    eligible = {name: values for name, values in epl_referees.items() if len(values) >= MIN_REFEREE_MATCHES}
    referee_means = [statistics.fmean(values) for values in eligible.values()]
    referee_population_variances = [statistics.pvariance(values) for values in eligible.values()]
    referee_sample_sizes = [len(values) for values in eligible.values()]
    grand_mean = statistics.fmean(referee_means)
    within_variance = statistics.fmean(referee_population_variances)
    raw_between_variance = statistics.pvariance(referee_means)
    sampling_variance = within_variance / statistics.fmean(referee_sample_sizes)
    true_between_variance = max(0.0, raw_between_variance - sampling_variance)
    empirical_k = within_variance / true_between_variance if true_between_variance > 0.0 else math.inf
    ordered = sorted(
        (
            {"referee": referee, "matches": len(values), "mean_total_fouls": statistics.fmean(values)}
            for referee, values in eligible.items()
        ),
        key=lambda item: item["mean_total_fouls"],
    )
    coverage = {
        league: {
            **counts,
            "coverage": counts["with_referee"] / counts["usable"] if counts["usable"] else 0.0,
        }
        for league, counts in league_coverage.items()
    }
    return {
        "coverage_by_league": coverage,
        "eligible_epl_referees": len(eligible),
        "minimum_referee_matches": MIN_REFEREE_MATCHES,
        "grand_mean_total_fouls_unweighted": grand_mean,
        "within_referee_sd": math.sqrt(within_variance),
        "true_between_referee_sd": math.sqrt(true_between_variance),
        "empirical_k": empirical_k,
        "registered_k": REGISTERED_REFEREE_K,
        "lowest_referee": ordered[0] if ordered else None,
        "highest_referee": ordered[-1] if ordered else None,
    }


def nearest_quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * probability)
    return ordered[index]


def line_grid_and_span(rows: Iterable[dict[str, str]]) -> dict[str, Any]:
    legs: list[float] = []
    seasons: set[str] = set()
    for row in rows:
        home = number(row.get("HF"))
        away = number(row.get("AF"))
        if home is not None and away is not None:
            legs.extend((home, away))
        season = str(row.get("season") or "").strip()
        if season:
            seasons.add(season)
    return {
        "leg_quantiles": {
            "p10": nearest_quantile(legs, 0.10),
            "p25": nearest_quantile(legs, 0.25),
            "p50": nearest_quantile(legs, 0.50),
            "p75": nearest_quantile(legs, 0.75),
            "p90": nearest_quantile(legs, 0.90),
        },
        "registered_line_grid": list(REGISTERED_LINES),
        "first_season": min(seasons),
        "last_season": max(seasons),
        "validation_seasons": ["2024-2025", "2025-2026"],
    }


def cards_and_feature_priors(rows: Iterable[dict[str, str]]) -> dict[str, Any]:
    home_fouls: list[float] = []
    home_cards: list[float] = []
    away_fouls: list[float] = []
    away_cards: list[float] = []
    total_cards: list[float] = []
    total_fouls_for_odds: list[float] = []
    closeness: list[float] = []
    total_fouls_for_shots: list[float] = []
    total_shots: list[float] = []
    for row in rows:
        hf = number(row.get("HF"))
        af = number(row.get("AF"))
        hy = number(row.get("HY"))
        ay = number(row.get("AY"))
        if hf is not None and hy is not None:
            home_fouls.append(hf)
            home_cards.append(hy)
        if af is not None and ay is not None:
            away_fouls.append(af)
            away_cards.append(ay)
        if hy is not None and ay is not None:
            total_cards.append(hy + ay)

        home_odds = number(row.get("B365H"))
        draw_odds = number(row.get("B365D"))
        away_odds = number(row.get("B365A"))
        if None not in (hf, af, home_odds, draw_odds, away_odds):
            home_probability = 1.0 / float(home_odds)
            away_probability = 1.0 / float(away_odds)
            closeness.append(1.0 - abs(home_probability - away_probability))
            total_fouls_for_odds.append(float(hf) + float(af))

        hs = number(row.get("HS"))
        away_shots = number(row.get("AS"))
        if None not in (hf, af, hs, away_shots):
            total_fouls_for_shots.append(float(hf) + float(af))
            total_shots.append(float(hs) + float(away_shots))

    home_card_vmr = statistics.pvariance(home_cards) / statistics.fmean(home_cards)
    away_card_vmr = statistics.pvariance(away_cards) / statistics.fmean(away_cards)
    return {
        "cards": {
            "home_leg_vmr": home_card_vmr,
            "away_leg_vmr": away_card_vmr,
            "match_total_vmr": statistics.pvariance(total_cards) / statistics.fmean(total_cards),
            "verdict": "REJECT_DEDICATED_MODEL",
        },
        "feature_priors": {
            "home_fouls_vs_home_yellows_correlation": correlation(home_fouls, home_cards),
            "away_fouls_vs_away_yellows_correlation": correlation(away_fouls, away_cards),
            "opening_1x2_closeness_vs_total_fouls_correlation": correlation(closeness, total_fouls_for_odds),
            "total_shots_vs_total_fouls_correlation": correlation(total_shots, total_fouls_for_shots),
        },
    }


def build_payload(rows: list[dict[str, str]], source: Path) -> dict[str, Any]:
    structure = leg_structure(rows)
    usable = int(structure["pooled"]["n"])
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": str(source.relative_to(ROOT)).replace("\\", "/") if source.is_relative_to(ROOT) else str(source),
        "source_rows": len(rows),
        "usable_rows": usable,
        "status": "REGISTERED_RESEARCH_BASELINE",
        "market_gate": "BLOCKED_TEAM_FOULS_NOT_OBSERVED",
        "leg_structure": structure,
        "referee": referee_baseline(rows),
        "line_grid_and_span": line_grid_and_span(rows),
        **cards_and_feature_priors(rows),
    }


def fmt(value: object, digits: int = 3) -> str:
    return "-" if value is None else f"{float(value):.{digits}f}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Team Fouls v1: M1 Empirical Registration Baseline",
        "",
        f"Generated: {payload['generated_at']}",
        f"Source: `{payload['source']}` ({payload['usable_rows']:,}/{payload['source_rows']:,} usable rows)",
        "",
        "**Status: research only. M0 market coverage remains blocking; no signals or lock are authorized.**",
        "",
        "## Leg structure and raw frailty ceilings",
        "",
        "| League | n | HF mean | HF VMR | AF mean | AF VMR | Total VMR | corr(HF,AF) | nu ceiling | alpha H | alpha A | Away gap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for league in (*LEAGUE_LABELS, "pooled"):
        row = payload["leg_structure"][league]
        label = LEAGUE_LABELS.get(league, "POOLED")
        lines.append(
            f"| {label} | {row['n']:,} | {fmt(row['home_mean'], 2)} | {fmt(row['home_vmr'])} | "
            f"{fmt(row['away_mean'], 2)} | {fmt(row['away_vmr'])} | {fmt(row['total_vmr'])} | "
            f"{fmt(row['home_away_correlation'])} | {fmt(row['nu_hat_raw_ceiling'], 4)} | "
            f"{fmt(row['alpha_home_after_raw_frailty'], 4)} | {fmt(row['alpha_away_after_raw_frailty'], 4)} | "
            f"{float(row['away_gap']):+.2f} |"
        )

    referee = payload["referee"]
    lines.extend(
        [
            "",
            "## Referee registration",
            "",
            f"- EPL coverage: {referee['coverage_by_league']['epl']['coverage']:.1%}; all other target leagues: 0.0%.",
            f"- Eligible EPL referees: {referee['eligible_epl_referees']} (`n >= {referee['minimum_referee_matches']}`).",
            f"- Unweighted referee grand mean: {referee['grand_mean_total_fouls_unweighted']:.2f} total fouls.",
            f"- Within-referee SD: {referee['within_referee_sd']:.2f}; true between-referee SD: {referee['true_between_referee_sd']:.2f}.",
            f"- Empirical `k={referee['empirical_k']:.1f}`; registered conservative `k={referee['registered_k']}`.",
            "",
            "## Registered F1 inputs",
            "",
            f"- Leg quantiles p10/p25/p50/p75/p90: {' / '.join(str(int(value)) for value in payload['line_grid_and_span']['leg_quantiles'].values())}.",
            f"- Evaluation lines: {', '.join(str(value) for value in payload['line_grid_and_span']['registered_line_grid'])}.",
            f"- Validation folds: {', '.join(payload['line_grid_and_span']['validation_seasons'])}.",
            f"- Home fouls/cards correlation: {payload['feature_priors']['home_fouls_vs_home_yellows_correlation']:+.3f}.",
            f"- Opening-odds closeness/total-fouls correlation: {payload['feature_priors']['opening_1x2_closeness_vs_total_fouls_correlation']:+.3f}.",
            f"- Total-shots/total-fouls correlation: {payload['feature_priors']['total_shots_vs_total_fouls_correlation']:+.3f}.",
            "- Cards verdict: **REJECT dedicated model**; retain cards only as a registered fouls feature.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    rows = load_rows(args.source)
    payload = build_payload(rows, args.source)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report.write_text(render_markdown(payload), encoding="utf-8")
    print(f"Team fouls M1: usable={payload['usable_rows']:,}; report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
