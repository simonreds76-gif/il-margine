#!/usr/bin/env python3
"""
Backtest the live corners V3 policy against a synthetic market.

The live shortlist compares the calibrated model probability against bookmaker
corner O/U prices. Historical corner totals odds are not stored in the repo, so
the backtest uses a synthetic market derived from the smart Bet365 1X2 -> total
corners baseline already embedded in the corners model.

This keeps the backtest aligned with the current V3 decision policy:
  - pooled 20-match EMA primary lambda
  - pooled 6-match EMA recent/confidence lambda
  - Platt-calibrated model probability
  - probability-space edge
  - V3 divergence-based stake adjustment

Outputs:
  data/corners-ou/corners-ou-backtest-results.csv
  data/corners-ou/corners-ou-backtest-report.txt
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_RESULTS_OUT = ROOT / "data" / "corners-ou" / "corners-ou-backtest-results.csv"
DEFAULT_REPORT_OUT = ROOT / "data" / "corners-ou" / "corners-ou-backtest-report.txt"
DEFAULT_CALIBRATION = ROOT / "data" / "corners-ou" / "corners-calibration-params.json"
DEFAULT_HOLDOUT_START = "2022-08-01"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


corners_model = _load_module("corners_ou_model", ROOT / "scripts" / "corners-ou-model.py")
matchday_shortlist = _load_module("matchday_shortlist", ROOT / "scripts" / "matchday-shortlist.py")
corners_poisson = _load_module("corners_poisson", ROOT / "scripts" / "corners_poisson.py")


BACKTEST_FIELDS = [
    "date",
    "league",
    "season",
    "match",
    "line",
    "side",
    "bookmaker",
    "bookie_odds",
    "market_prob",
    "model_prob_raw",
    "model_prob",
    "model_fair",
    "edge",
    "stake",
    "stake_label",
    "lambda_h",
    "lambda_a",
    "lambda_total",
    "lambda_h_recent",
    "lambda_a_recent",
    "divergence",
    "consensus",
    "policy_version",
    "actual_total",
    "won",
    "pnl",
]


def _pf(value: Any, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _line_key(line: float) -> str:
    return f"{line:.1f}"


def _calibrated_prob(line: float, p_raw: float, params: Optional[Dict[str, Tuple[float, float]]]) -> float:
    if not params:
        return p_raw
    pair = params.get(_line_key(line))
    if pair is None:
        return p_raw
    a, b = pair
    return corners_poisson.calibrate_prob(p_raw, a, b)


def _iter_bet_sides(
    line: float,
    p_model_raw: float,
    p_model: float,
    p_market_over: float,
) -> Iterable[Tuple[str, float, float, float, bool]]:
    p_market_under = 1.0 - p_market_over
    yield ("over", p_model_raw, p_model, p_market_over, p_model_raw > 0)
    yield ("under", 1.0 - p_model_raw, 1.0 - p_model, p_market_under, p_model_raw < 1)


def _build_rows(
    matches: List[Any],
    holdout_start: date,
    lines: List[float],
    min_edge: float,
    params: Optional[Dict[str, Tuple[float, float]]],
) -> Tuple[List[dict], Dict[str, float]]:
    team_states: Dict[str, Any] = defaultdict(corners_model.TeamState)
    league_corner_sums: Dict[str, float] = defaultdict(float)
    league_corner_counts: Dict[str, int] = defaultdict(int)
    rows: List[dict] = []
    counters: Dict[str, float] = defaultdict(float)

    def _causal_league_avg(league: str) -> float:
        n = league_corner_counts[league]
        if n < corners_model._MIN_LEAGUE_OBS:
            return corners_model.LEAGUE_DEFAULTS.get(league, corners_model.DEFAULT_AVG_CORNERS)
        return league_corner_sums[league] / n

    for match in matches:
        avg_c = _causal_league_avg(match.league)
        home_key = f"{match.league}:{match.home_team}"
        away_key = f"{match.league}:{match.away_team}"
        h_state = team_states[home_key]
        a_state = team_states[away_key]

        if match.match_date >= holdout_start:
            h_lam = corners_model.predict_team_lambda(h_state, a_state, avg_c, is_home=True)
            a_lam = corners_model.predict_team_lambda(a_state, h_state, avg_c, is_home=False)
            if h_lam is not None and a_lam is not None:
                h_lam_recent = matchday_shortlist.predict_corners_lambda_from_avgs(
                    h_state.avg_won_recent(),
                    a_state.avg_conceded_recent(),
                    avg_c,
                    True,
                )
                a_lam_recent = matchday_shortlist.predict_corners_lambda_from_avgs(
                    a_state.avg_won_recent(),
                    h_state.avg_conceded_recent(),
                    avg_c,
                    False,
                )
                divergence, consensus = matchday_shortlist.consensus_for_lambdas(
                    h_lam,
                    a_lam,
                    h_lam_recent,
                    a_lam_recent,
                )

                market_h = corners_model.smart_corners_lambda("home", match.b365h, match.b365d, match.b365a)
                market_a = corners_model.smart_corners_lambda("away", match.b365h, match.b365d, match.b365a)
                if market_h is not None and market_a is not None:
                    counters["matches_with_market"] += 1
                    actual_total = match.home_corners + match.away_corners
                    match_label = f"{match.home_team} vs {match.away_team}"
                    match_candidates: List[dict] = []
                    for line in lines:
                        p_model_raw = corners_poisson.match_total_prob_over(line, h_lam, a_lam)
                        p_model = _calibrated_prob(line, p_model_raw, params)
                        p_market_over = corners_poisson.match_total_prob_over(line, market_h, market_a)

                        for side, model_prob_raw_side, model_prob, market_prob, valid in _iter_bet_sides(
                            line,
                            p_model_raw,
                            p_model,
                            p_market_over,
                        ):
                            if not valid:
                                continue
                            edge = model_prob - market_prob
                            if edge < min_edge:
                                continue

                            base_stake, stake_label = matchday_shortlist.tier_stake(edge)
                            if base_stake <= 0:
                                continue
                            stake = matchday_shortlist.effective_stake_for_consensus(
                                edge,
                                base_stake,
                                match.league,
                                consensus,
                            )
                            if stake <= 0:
                                continue

                            book_odds = corners_poisson.fair_decimal(market_prob)
                            won = actual_total > line if side == "over" else actual_total < line
                            pnl = stake * (book_odds - 1.0) if won else -stake
                            match_candidates.append(
                                {
                                    "date": match.match_date.isoformat(),
                                    "league": match.league,
                                    "season": match.season,
                                    "match": match_label,
                                    "line": f"{line:.1f}",
                                    "side": side,
                                    "bookmaker": "synthetic_b365_1x2",
                                    "bookie_odds": round(book_odds, 3),
                                    "market_prob": round(market_prob, 4),
                                    "model_prob_raw": round(model_prob_raw_side, 4),
                                    "model_prob": round(model_prob, 4),
                                    "model_fair": corners_poisson.fair_decimal(model_prob),
                                    "edge": round(edge, 4),
                                    "stake": round(stake, 2),
                                    "stake_label": stake_label,
                                    "lambda_h": round(h_lam, 3),
                                    "lambda_a": round(a_lam, 3),
                                    "lambda_total": round(h_lam + a_lam, 3),
                                    "lambda_h_recent": round(h_lam_recent, 3) if h_lam_recent is not None else 0.0,
                                    "lambda_a_recent": round(a_lam_recent, 3) if a_lam_recent is not None else 0.0,
                                    "divergence": round(divergence, 4),
                                    "consensus": consensus,
                                    "policy_version": matchday_shortlist.POLICY_VERSION,
                                    "actual_total": actual_total,
                                    "won": "true" if won else "false",
                                    "pnl": round(pnl, 4),
                                }
                            )
                    if match_candidates:
                        best = max(match_candidates, key=lambda row: (_pf(row["edge"]), _pf(row["stake"])))
                        rows.append(best)

        h_state.add_match(match.home_corners, match.away_corners)
        a_state.add_match(match.away_corners, match.home_corners)
        league_corner_sums[match.league] += match.home_corners + match.away_corners
        league_corner_counts[match.league] += 2
        counters["matches_total"] += 1

    return rows, counters


def _group_summary(rows: List[dict], key: str) -> List[Tuple[str, Dict[str, float]]]:
    grouped: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)

    summary: List[Tuple[str, Dict[str, float]]] = []
    for group_key, group_rows in grouped.items():
        settled = len(group_rows)
        wins = sum(1 for row in group_rows if str(row.get("won", "")).lower() == "true")
        pnl = sum(_pf(row.get("pnl")) for row in group_rows)
        staked = sum(_pf(row.get("stake"), 1.0) for row in group_rows)
        roi = (pnl / staked * 100.0) if staked > 0 else 0.0
        summary.append(
            (
                group_key,
                {
                    "settled": settled,
                    "wins": wins,
                    "losses": settled - wins,
                    "pnl": pnl,
                    "staked": staked,
                    "roi": roi,
                },
            )
        )
    summary.sort(key=lambda item: item[0])
    return summary


def _build_report(
    rows: List[dict],
    holdout_start: date,
    min_edge: float,
    counters: Dict[str, float],
) -> str:
    lines: List[str] = [
        "=" * 70,
        "  CORNERS O/U V3 BACKTEST REPORT",
        "=" * 70,
        "",
        f"  Policy              : {matchday_shortlist.POLICY_VERSION}",
        "  Market              : synthetic B365 1X2 smart-corners baseline",
        f"  Holdout start       : {holdout_start.isoformat()}",
        f"  Min edge            : {min_edge:.1%}",
        f"  Historical matches  : {int(counters.get('matches_total', 0))}",
        f"  Matches w/ market   : {int(counters.get('matches_with_market', 0))}",
        "",
    ]

    if not rows:
        lines.extend(
            [
                "  No backtest bets met the configured policy threshold.",
                "",
                "=" * 70,
            ]
        )
        return "\n".join(lines)

    total_bets = len(rows)
    wins = sum(1 for row in rows if row["won"] == "true")
    pnl = sum(_pf(row["pnl"]) for row in rows)
    staked = sum(_pf(row["stake"], 1.0) for row in rows)
    roi = (pnl / staked * 100.0) if staked > 0 else 0.0
    avg_odds = sum(_pf(row["bookie_odds"]) for row in rows) / total_bets
    avg_edge = sum(_pf(row["edge"]) for row in rows) / total_bets * 100.0
    lines.extend(
        [
            f"  Bets                : {total_bets}",
            f"  Record              : {wins}W / {total_bets - wins}L",
            f"  Total staked        : {staked:.1f}u",
            f"  P&L                 : {pnl:+.2f}u",
            f"  ROI                 : {roi:+.1f}%",
            f"  Avg odds            : {avg_odds:.2f}",
            f"  Avg edge            : {avg_edge:+.1f}%",
            "",
            "  By line",
        ]
    )

    for line_key, stats in _group_summary(rows, "line"):
        lines.append(
            f"    {line_key:>4s}: {int(stats['settled']):4d} bets  "
            f"W{int(stats['wins'])}/L{int(stats['losses'])}  "
            f"P&L {stats['pnl']:+.2f}u  ROI {stats['roi']:+.1f}%"
        )

    lines.append("")
    lines.append("  By league")
    for league_key, stats in _group_summary(rows, "league"):
        lines.append(
            f"    {league_key:12s} {int(stats['settled']):4d} bets  "
            f"W{int(stats['wins'])}/L{int(stats['losses'])}  "
            f"P&L {stats['pnl']:+.2f}u  ROI {stats['roi']:+.1f}%"
        )

    lines.append("")
    lines.append("  By consensus")
    for consensus_key, stats in _group_summary(rows, "consensus"):
        lines.append(
            f"    {consensus_key:9s} {int(stats['settled']):4d} bets  "
            f"W{int(stats['wins'])}/L{int(stats['losses'])}  "
            f"P&L {stats['pnl']:+.2f}u  ROI {stats['roi']:+.1f}%"
        )

    lines.extend(
        [
            "",
            "=" * 70,
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the live corners V3 policy against a synthetic market")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--results-out", type=Path, default=DEFAULT_RESULTS_OUT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--holdout-start", default=DEFAULT_HOLDOUT_START)
    parser.add_argument("--min-edge", type=float, default=matchday_shortlist.DEFAULT_EDGE_THRESHOLD)
    parser.add_argument("--lines", default="8.5,9.5,10.5,11.5")
    args = parser.parse_args()

    input_path = corners_model.resolve_historical_input(args.input)
    matches = corners_model.load_matches(input_path)
    holdout_start = date.fromisoformat(args.holdout_start)
    params = corners_poisson.load_calibration_params(args.calibration)
    lines = [float(part.strip()) for part in args.lines.split(",") if part.strip()]

    rows, counters = _build_rows(matches, holdout_start, lines, args.min_edge, params)

    args.results_out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.results_out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=BACKTEST_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    report = _build_report(rows, holdout_start, args.min_edge, counters)
    with open(args.report_out, "w", encoding="utf-8") as fh:
        fh.write(report)

    print(f"Matches loaded           : {len(matches)}")
    print(f"Backtest bets written    : {len(rows)}")
    print(f"Results CSV written to   : {args.results_out}")
    print(f"Backtest report written  : {args.report_out}")


if __name__ == "__main__":
    main()
