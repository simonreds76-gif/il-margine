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
DEFAULT_LINES = "8.5,9.5,10.5,11.5"
DEFAULT_EDGE_BANDS = "-1,0,0.03,0.05,0.08,0.12,0.15"
DEFAULT_SWEEP_MIN_EDGES = "0,0.03,0.05,0.08,0.10,0.12,0.15"


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

POLICY_PRESETS: Dict[str, Dict[str, Any]] = {
    "official_v3": {
        "min_edge": matchday_shortlist.DEFAULT_EDGE_THRESHOLD,
        "no_divergence": False,
        "max_bets_per_fixture": 1,
        "flat_stake": None,
        "lines": DEFAULT_LINES,
        "edge_bands": DEFAULT_EDGE_BANDS,
    },
    "research_v31": {
        "min_edge": 0.08,
        "no_divergence": False,
        "max_bets_per_fixture": 1,
        "flat_stake": None,
        "lines": DEFAULT_LINES,
        "edge_bands": DEFAULT_EDGE_BANDS,
    },
    "research_all_bets": {
        "min_edge": 0.08,
        "no_divergence": False,
        "max_bets_per_fixture": 0,
        "flat_stake": None,
        "lines": DEFAULT_LINES,
        "edge_bands": DEFAULT_EDGE_BANDS,
    },
    "diagnostic": {
        "min_edge": 0.0,
        "no_divergence": True,
        "max_bets_per_fixture": 0,
        "flat_stake": 1.0,
        "lines": DEFAULT_LINES,
        "edge_bands": DEFAULT_EDGE_BANDS,
    },
}


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


def _parse_float_list(text: str) -> List[float]:
    values: List[float] = []
    for part in str(text or "").split(","):
        part = part.strip()
        if not part:
            continue
        values.append(float(part))
    return values


def _edge_band_label(edge: float, bands: List[float]) -> str:
    if not bands:
        return "all"
    ordered = sorted(set(bands))
    for idx in range(len(ordered) - 1):
        low = ordered[idx]
        high = ordered[idx + 1]
        if low <= edge < high:
            if low < 0:
                return f"<{high * 100:.0f}%"
            return f"{low * 100:.0f}-{high * 100:.0f}%"
    last = ordered[-1]
    if edge >= last:
        return f"{last * 100:.0f}%+"
    return f"<{ordered[0] * 100:.0f}%"


def _edge_sort_key(label: str) -> Tuple[int, float]:
    if label.endswith("%+"):
        return (2, float(label[:-2]))
    if "-" in label:
        return (1, float(label.split("-", 1)[0]))
    if label.startswith("<"):
        return (0, float(label[1:-1]))
    return (3, 0.0)


def _flat_stake_label(units: float) -> str:
    return f"FLAT_{units:.2f}u"


def _policy_label(no_divergence: bool, max_bets_per_fixture: int, flat_stake: Optional[float]) -> str:
    parts = [matchday_shortlist.POLICY_VERSION]
    if no_divergence:
        parts.append("no_divergence")
    if max_bets_per_fixture == 0:
        parts.append("all_bets")
    elif max_bets_per_fixture > 1:
        parts.append(f"top_{max_bets_per_fixture}")
    if flat_stake is not None:
        parts.append(f"flat_{flat_stake:.2f}u")
    return "+".join(parts)


def _summarize_rows(rows: List[dict]) -> Dict[str, float]:
    settled = len(rows)
    wins = sum(1 for row in rows if str(row.get("won", "")).lower() == "true")
    pnl = sum(_pf(row.get("pnl")) for row in rows)
    staked = sum(_pf(row.get("stake"), 1.0) for row in rows)
    roi = (pnl / staked * 100.0) if staked > 0 else 0.0
    avg_odds = (sum(_pf(row.get("bookie_odds")) for row in rows) / settled) if settled > 0 else 0.0
    avg_edge = (sum(_pf(row.get("edge")) for row in rows) / settled * 100.0) if settled > 0 else 0.0
    return {
        "bets": settled,
        "wins": wins,
        "losses": settled - wins,
        "pnl": pnl,
        "staked": staked,
        "roi": roi,
        "avg_odds": avg_odds,
        "avg_edge": avg_edge,
    }


def _build_rows(
    matches: List[Any],
    holdout_start: date,
    lines: List[float],
    min_edge: float,
    params: Optional[Dict[str, Tuple[float, float]]],
    *,
    no_divergence: bool = False,
    max_bets_per_fixture: int = 1,
    flat_stake: Optional[float] = None,
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

                            if flat_stake is not None:
                                stake = float(flat_stake)
                                stake_label = _flat_stake_label(stake)
                            else:
                                base_stake, stake_label = matchday_shortlist.tier_stake(edge)
                                if base_stake <= 0:
                                    continue
                                if no_divergence:
                                    league_mult = matchday_shortlist.LEAGUE_STAKE_MULTIPLIERS.get(
                                        match.league,
                                        matchday_shortlist.DEFAULT_LEAGUE_MULTIPLIER,
                                    )
                                    stake = round(base_stake * league_mult, 2)
                                    stake = min(stake, 2.0)
                                    if match.league == "ligue-1":
                                        stake = min(stake, matchday_shortlist.LIGUE1_MAX_STAKE)
                                else:
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
                                    "consensus": "aligned" if no_divergence else consensus,
                                    "policy_version": _policy_label(no_divergence, max_bets_per_fixture, flat_stake),
                                    "actual_total": actual_total,
                                    "won": "true" if won else "false",
                                    "pnl": round(pnl, 4),
                                }
                            )
                    if match_candidates:
                        ranked = sorted(
                            match_candidates,
                            key=lambda row: (_pf(row["edge"]), _pf(row["stake"]), _pf(row["model_prob"])),
                            reverse=True,
                        )
                        if max_bets_per_fixture == 0:
                            rows.extend(ranked)
                        elif max_bets_per_fixture == 1:
                            rows.append(ranked[0])
                        else:
                            rows.extend(ranked[:max_bets_per_fixture])

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


def _group_edge_summary(rows: List[dict], edge_bands: List[float]) -> List[Tuple[str, Dict[str, float]]]:
    grouped: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        grouped[_edge_band_label(_pf(row.get("edge")), edge_bands)].append(row)

    summary: List[Tuple[str, Dict[str, float]]] = []
    for label, group_rows in grouped.items():
        summary.append((label, _summarize_rows(group_rows)))
    summary.sort(key=lambda item: _edge_sort_key(item[0]))
    return summary


def _group_fixture_counts(rows: List[dict]) -> List[Tuple[int, int]]:
    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for row in rows:
        counts[(str(row.get("date")), str(row.get("match")))] += 1

    distribution: Dict[int, int] = defaultdict(int)
    for fixture_count in counts.values():
        distribution[fixture_count] += 1
    return sorted(distribution.items())


def _build_report(
    rows: List[dict],
    holdout_start: date,
    min_edge: float,
    counters: Dict[str, float],
    *,
    preset_name: str,
    edge_bands: List[float],
    no_divergence: bool,
    max_bets_per_fixture: int,
    flat_stake: Optional[float],
) -> str:
    summary = _summarize_rows(rows)
    lines: List[str] = [
        "=" * 70,
        "  CORNERS O/U V3 BACKTEST REPORT",
        "=" * 70,
        "",
        f"  Preset              : {preset_name}",
        f"  Policy              : {_policy_label(no_divergence, max_bets_per_fixture, flat_stake)}",
        "  Market              : synthetic B365 1X2 smart-corners baseline",
        f"  Holdout start       : {holdout_start.isoformat()}",
        f"  Min edge            : {min_edge:.1%}",
        f"  Divergence gate     : {'off' if no_divergence else 'on'}",
        f"  Max bets / fixture  : {'all' if max_bets_per_fixture == 0 else max_bets_per_fixture}",
        f"  Flat stake          : {flat_stake:.2f}u" if flat_stake is not None else "  Flat stake          : off",
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

    lines.extend(
        [
            f"  Bets                : {int(summary['bets'])}",
            f"  Record              : {int(summary['wins'])}W / {int(summary['losses'])}L",
            f"  Total staked        : {summary['staked']:.1f}u",
            f"  P&L                 : {summary['pnl']:+.2f}u",
            f"  ROI                 : {summary['roi']:+.1f}%",
            f"  Avg odds            : {summary['avg_odds']:.2f}",
            f"  Avg edge            : {summary['avg_edge']:+.1f}%",
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

    lines.append("")
    lines.append("  By season")
    for season_key, stats in _group_summary(rows, "season"):
        lines.append(
            f"    {season_key:9s} {int(stats['settled']):4d} bets  "
            f"W{int(stats['wins'])}/L{int(stats['losses'])}  "
            f"P&L {stats['pnl']:+.2f}u  ROI {stats['roi']:+.1f}%"
        )

    if edge_bands:
        lines.append("")
        lines.append("  By edge band")
        for label, stats in _group_edge_summary(rows, edge_bands):
            lines.append(
                f"    {label:9s} {int(stats['bets']):4d} bets  "
                f"W{int(stats['wins'])}/L{int(stats['losses'])}  "
                f"P&L {stats['pnl']:+.2f}u  ROI {stats['roi']:+.1f}%"
            )

        lines.append("")
        lines.append("  By season / edge band")
        season_groups: Dict[str, List[dict]] = defaultdict(list)
        for row in rows:
            season_groups[str(row.get("season") or "unknown")].append(row)
        for season_key in sorted(season_groups):
            season_rows = season_groups[season_key]
            season_stats = _summarize_rows(season_rows)
            lines.append(
                f"    {season_key:9s} {int(season_stats['bets']):4d} bets  "
                f"W{int(season_stats['wins'])}/L{int(season_stats['losses'])}  "
                f"P&L {season_stats['pnl']:+.2f}u  ROI {season_stats['roi']:+.1f}%"
            )
            for label, stats in _group_edge_summary(season_rows, edge_bands):
                lines.append(
                    f"      {label:9s} {int(stats['bets']):4d} bets  "
                    f"W{int(stats['wins'])}/L{int(stats['losses'])}  "
                    f"P&L {stats['pnl']:+.2f}u  ROI {stats['roi']:+.1f}%"
                )

    if max_bets_per_fixture == 0:
        lines.append("")
        lines.append("  Qualifying bets per fixture")
        for bets_per_fixture, fixture_count in _group_fixture_counts(rows):
            lines.append(f"    {bets_per_fixture:>2d} bets  {fixture_count:4d} fixtures")

    lines.extend(
        [
            "",
            "=" * 70,
        ]
    )
    return "\n".join(lines)


def _write_rows(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=BACKTEST_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _run_single(
    *,
    matches: List[Any],
    holdout_start: date,
    lines: List[float],
    min_edge: float,
    params: Optional[Dict[str, Tuple[float, float]]],
    results_out: Path,
    report_out: Path,
    preset_name: str,
    edge_bands: List[float],
    no_divergence: bool,
    max_bets_per_fixture: int,
    flat_stake: Optional[float],
) -> Tuple[List[dict], Dict[str, float], str]:
    rows, counters = _build_rows(
        matches,
        holdout_start,
        lines,
        min_edge,
        params,
        no_divergence=no_divergence,
        max_bets_per_fixture=max_bets_per_fixture,
        flat_stake=flat_stake,
    )
    _write_rows(results_out, rows)
    report = _build_report(
        rows,
        holdout_start,
        min_edge,
        counters,
        preset_name=preset_name,
        edge_bands=edge_bands,
        no_divergence=no_divergence,
        max_bets_per_fixture=max_bets_per_fixture,
        flat_stake=flat_stake,
    )
    _write_text(report_out, report)
    return rows, counters, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the live corners V3 policy against a synthetic market")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--results-out", type=Path, default=DEFAULT_RESULTS_OUT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    parser.add_argument("--sweep-summary-out", type=Path, default=ROOT / "data" / "corners-ou" / "corners-ou-backtest-sweep.csv")
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--holdout-start", default=DEFAULT_HOLDOUT_START)
    parser.add_argument("--preset", choices=sorted(POLICY_PRESETS), default="official_v3", help="Named policy preset for official, research, and diagnostic runs")
    parser.add_argument("--min-edge", type=float, default=None)
    parser.add_argument("--sweep-min-edges", default="", help=f"Comma-separated threshold sweep, e.g. {DEFAULT_SWEEP_MIN_EDGES}")
    parser.add_argument("--lines", default=None)
    parser.add_argument("--edge-bands", default=None, help="Comma-separated edge-band lower bounds for report summaries")
    parser.add_argument("--no-divergence", action="store_true", default=None, help="Disable divergence/conflict stake suppression")
    parser.add_argument("--max-bets-per-fixture", type=int, default=None, help="0 = all qualifying bets, 1 = best only (default), N = top N per fixture")
    parser.add_argument("--flat-stake", type=float, default=None, help="Use flat stake instead of tier staking / league multipliers")
    args = parser.parse_args()

    preset = POLICY_PRESETS[args.preset]
    input_path = corners_model.resolve_historical_input(args.input)
    matches = corners_model.load_matches(input_path)
    holdout_start = date.fromisoformat(args.holdout_start)
    params = corners_poisson.load_calibration_params(args.calibration)
    min_edge = float(preset["min_edge"] if args.min_edge is None else args.min_edge)
    lines_text = str(preset["lines"] if args.lines is None else args.lines)
    edge_bands_text = str(preset["edge_bands"] if args.edge_bands is None else args.edge_bands)
    no_divergence = bool(preset["no_divergence"] if args.no_divergence is None else args.no_divergence)
    max_bets_per_fixture = int(
        preset["max_bets_per_fixture"] if args.max_bets_per_fixture is None else args.max_bets_per_fixture
    )
    flat_stake = preset["flat_stake"] if args.flat_stake is None else args.flat_stake
    lines = [float(part.strip()) for part in lines_text.split(",") if part.strip()]
    edge_bands = _parse_float_list(edge_bands_text)
    sweep_thresholds = _parse_float_list(args.sweep_min_edges)

    if sweep_thresholds:
        args.sweep_summary_out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.sweep_summary_out, "w", newline="", encoding="utf-8") as fh:
            fieldnames = [
                "preset",
                "min_edge",
                "bets",
                "wins",
                "losses",
                "staked",
                "pnl",
                "roi",
                "avg_odds",
                "avg_edge",
                "policy_version",
                "results_out",
                "report_out",
            ]
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for threshold in sweep_thresholds:
                suffix = f".edge-{threshold:.2f}".replace("0.", ".")
                results_out = args.results_out.with_name(f"{args.results_out.stem}{suffix}{args.results_out.suffix}")
                report_out = args.report_out.with_name(f"{args.report_out.stem}{suffix}{args.report_out.suffix}")
                rows, _counters, _report = _run_single(
                    matches=matches,
                    holdout_start=holdout_start,
                    lines=lines,
                    min_edge=threshold,
                    params=params,
                    results_out=results_out,
                    report_out=report_out,
                    preset_name=args.preset,
                    edge_bands=edge_bands,
                    no_divergence=no_divergence,
                    max_bets_per_fixture=max_bets_per_fixture,
                    flat_stake=flat_stake,
                )
                summary = _summarize_rows(rows)
                writer.writerow(
                    {
                        "preset": args.preset,
                        "min_edge": round(threshold, 4),
                        "bets": int(summary["bets"]),
                        "wins": int(summary["wins"]),
                        "losses": int(summary["losses"]),
                        "staked": round(summary["staked"], 4),
                        "pnl": round(summary["pnl"], 4),
                        "roi": round(summary["roi"], 4),
                        "avg_odds": round(summary["avg_odds"], 4),
                        "avg_edge": round(summary["avg_edge"], 4),
                        "policy_version": _policy_label(no_divergence, max_bets_per_fixture, flat_stake),
                        "results_out": str(results_out),
                        "report_out": str(report_out),
                    }
                )
        print(f"Matches loaded           : {len(matches)}")
        print(f"Threshold sweep written  : {args.sweep_summary_out}")
        return

    rows, _counters, _report = _run_single(
        matches=matches,
        holdout_start=holdout_start,
        lines=lines,
        min_edge=min_edge,
        params=params,
        results_out=args.results_out,
        report_out=args.report_out,
        preset_name=args.preset,
        edge_bands=edge_bands,
        no_divergence=no_divergence,
        max_bets_per_fixture=max_bets_per_fixture,
        flat_stake=flat_stake,
    )

    print(f"Matches loaded           : {len(matches)}")
    print(f"Backtest bets written    : {len(rows)}")
    print(f"Results CSV written to   : {args.results_out}")
    print(f"Backtest report written  : {args.report_out}")


if __name__ == "__main__":
    main()
