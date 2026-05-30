#!/usr/bin/env python3
"""Real-odds corners backtest for the v2 rebuild.

This script is the first validation gate for corners v2. It joins real captured
Pinnacle corner O/U prices to historical actual corner totals and existing
walk-forward lambda predictions, then scores a Negative Binomial market-blend
model against real publication and close prices.

No synthetic bookmaker prices are used for ROI, CLV, or sellability.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from corners_nb import (  # noqa: E402
    fit_pooled_and_group_dispersion,
    nb_line_probabilities,
    nb_total_prob_over,
    push_adjusted_fair_decimal,
)
from corners_poisson import match_total_prob_over  # noqa: E402

DEFAULT_PINNACLE = ROOT / "data" / "corners-ou" / "pinnacle-corners-odds.csv"
DEFAULT_PREDICTIONS = ROOT / "data" / "corners-ou" / "corners-ou-predictions.csv"
DEFAULT_ACTUALS = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_RESULTS = ROOT / "data" / "corners-ou" / "corners-real-odds-backtest-results.csv"
DEFAULT_REPORT = ROOT / "data" / "corners-ou" / "corners-real-odds-backtest-report.txt"

OUTPUT_FIELDS = [
    "match_id",
    "date",
    "league",
    "home",
    "away",
    "kickoff_utc",
    "line",
    "side",
    "model_version",
    "published_at",
    "close_captured_at",
    "close_is_stale",
    "published_odds",
    "close_odds",
    "market_fair_prob",
    "market_over_prob",
    "lambda_model",
    "lambda_market",
    "lambda_final",
    "dispersion_r",
    "model_prob",
    "model_over_prob",
    "model_push_prob",
    "model_fair_odds",
    "prob_edge",
    "value_pct",
    "selected",
    "actual_total",
    "result",
    "pnl_units",
    "published_to_close_clv",
    "positive_clv",
    "brier_over",
    "logloss_over",
]

STANDARD_LEAGUES = ["epl", "serie-a", "la-liga", "bundesliga", "ligue-1"]


def norm_team(text: Any) -> str:
    raw = str(text or "").strip().lower().replace("(corners)", "")
    raw = unicodedata.normalize("NFD", raw)
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


def parse_dt(text: Any) -> datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def fmt_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def pf(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def pi(value: Any, default: int | None = None) -> int | None:
    val = pf(value)
    if val is None:
        return default
    return int(val)


def parse_date(text: Any) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw[:10]


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def key_for(date_iso: str, league: str, home: Any, away: Any) -> str:
    return "|".join([date_iso, str(league or "").strip().lower(), norm_team(home), norm_team(away)])


def line_label(value: Any) -> str:
    val = pf(value)
    return "" if val is None else f"{val:.1f}"


def is_integer_line(line: float) -> bool:
    return abs(line - round(line)) < 1e-9


def result_for(side: str, line: float, actual_total: int) -> str:
    if is_integer_line(line) and actual_total == int(round(line)):
        return "push"
    if side == "over":
        return "won" if actual_total > line else "lost"
    return "won" if actual_total < line else "lost"


def pnl_for(result: str, odds: float) -> float:
    if result == "won":
        return odds - 1.0
    if result == "lost":
        return -1.0
    return 0.0


def safe_logloss(prob: float, actual: bool) -> float:
    p = min(1.0 - 1e-12, max(1e-12, prob))
    return -math.log(p if actual else 1.0 - p)


def brier(prob: float, actual: bool) -> float:
    y = 1.0 if actual else 0.0
    return (prob - y) ** 2


@dataclass
class Prediction:
    date: str
    league: str
    home: str
    away: str
    lambda_home: float
    lambda_away: float
    lambda_total: float
    actual_total: int


@dataclass
class Actual:
    date: str
    league: str
    home: str
    away: str
    total: int


@dataclass
class SnapshotPair:
    captured_at: datetime
    kickoff: datetime | None
    over_odds: float
    under_odds: float


@dataclass
class MarketPoint:
    date: str
    league: str
    home: str
    away: str
    kickoff: datetime | None
    line: float
    published: SnapshotPair
    close: SnapshotPair


def load_predictions(path: Path) -> dict[str, Prediction]:
    out: dict[str, Prediction] = {}
    for row in load_csv(path):
        date_iso = parse_date(row.get("date"))
        league = str(row.get("league") or "").strip().lower()
        lam_h = pf(row.get("lambda_home"))
        lam_a = pf(row.get("lambda_away"))
        lam_t = pf(row.get("lambda_total"))
        actual = pi(row.get("actual_total"))
        if not (date_iso and league and lam_h is not None and lam_a is not None and lam_t is not None and actual is not None):
            continue
        pred = Prediction(
            date=date_iso,
            league=league,
            home=str(row.get("home_team") or "").strip(),
            away=str(row.get("away_team") or "").strip(),
            lambda_home=lam_h,
            lambda_away=lam_a,
            lambda_total=lam_t,
            actual_total=actual,
        )
        out[key_for(date_iso, league, pred.home, pred.away)] = pred
    return out


def load_actuals(path: Path) -> dict[str, Actual]:
    out: dict[str, Actual] = {}
    for row in load_csv(path):
        date_iso = parse_date(row.get("Date") or row.get("date"))
        league = str(row.get("league") or "").strip().lower()
        home = str(row.get("HomeTeam") or row.get("home_team") or "").strip()
        away = str(row.get("AwayTeam") or row.get("away_team") or "").strip()
        hc = pi(row.get("HC") or row.get("home_corners"))
        ac = pi(row.get("AC") or row.get("away_corners"))
        if not (date_iso and league and home and away and hc is not None and ac is not None):
            continue
        actual = Actual(date_iso, league, home, away, hc + ac)
        out[key_for(date_iso, league, home, away)] = actual
    return out


def load_snapshot_pairs(path: Path) -> tuple[list[MarketPoint], Counter[str]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(dict)
    skips: Counter[str] = Counter()
    for row in load_csv(path):
        date_iso = str(row.get("match_date") or row.get("kickoff_iso") or "").strip()[:10]
        league = str(row.get("league") or "").strip().lower()
        home = str(row.get("home_team") or "").strip()
        away = str(row.get("away_team") or "").strip()
        line = line_label(row.get("line"))
        side = str(row.get("side") or "").strip().lower()
        odds = pf(row.get("odds_decimal"))
        captured = parse_dt(row.get("captured_at"))
        kickoff = parse_dt(row.get("kickoff_iso"))
        if not (date_iso and league and home and away and line and side in {"over", "under"} and odds and captured):
            skips["bad_row"] += 1
            continue
        base_key = "|".join([date_iso, league, norm_team(home), norm_team(away), line, fmt_dt(captured)])
        item = grouped[base_key]
        item.update({"date": date_iso, "league": league, "home": home, "away": away, "line": float(line), "captured_at": captured, "kickoff": kickoff})
        item[f"{side}_odds"] = odds

    by_match_line: dict[str, list[SnapshotPair]] = defaultdict(list)
    meta: dict[str, dict[str, Any]] = {}
    for item in grouped.values():
        over = item.get("over_odds")
        under = item.get("under_odds")
        if not (over and under):
            skips["missing_pair_side"] += 1
            continue
        match_line_key = "|".join([
            item["date"], item["league"], norm_team(item["home"]), norm_team(item["away"]), f"{float(item['line']):.1f}"
        ])
        meta[match_line_key] = item
        by_match_line[match_line_key].append(SnapshotPair(item["captured_at"], item.get("kickoff"), float(over), float(under)))

    points: list[MarketPoint] = []
    for match_line_key, snapshots in by_match_line.items():
        snapshots.sort(key=lambda s: s.captured_at)
        item = meta[match_line_key]
        kickoff = item.get("kickoff")
        if kickoff:
            pre_close = [snap for snap in snapshots if snap.captured_at <= kickoff]
        else:
            pre_close = snapshots
        if not pre_close:
            skips["no_pre_kickoff_snapshot"] += 1
            continue
        points.append(
            MarketPoint(
                date=item["date"],
                league=item["league"],
                home=item["home"],
                away=item["away"],
                kickoff=kickoff,
                line=float(item["line"]),
                published=snapshots[0],
                close=pre_close[-1],
            )
        )
    return points, skips


def devig_pair(over_odds: float, under_odds: float) -> tuple[float, float]:
    inv_over = 1.0 / over_odds
    inv_under = 1.0 / under_odds
    total = inv_over + inv_under
    if total <= 0:
        return 0.5, 0.5
    return inv_over / total, inv_under / total


def solve_market_mu(line: float, target_over: float, r: float) -> float | None:
    target = min(0.999, max(0.001, target_over))
    lo, hi = 0.05, 30.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        p_mid = nb_total_prob_over(line, mid, r)
        if p_mid < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def fmt_num(value: Any, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"{float(value):.{digits}f}"


def model_probabilities(
    version: str,
    point: MarketPoint,
    pred: Prediction,
    market_over_prob: float,
    dispersion_r: float,
    blend_weight: float,
) -> tuple[float, float, float, float | None]:
    if version == "poisson_v1":
        p_over = match_total_prob_over(point.line, pred.lambda_home, pred.lambda_away)
        # Independent Poisson helper includes exact integer mass in under side.
        # For v1 control, expose push as 0 because historical v1 was not push-aware.
        return p_over, 1.0 - p_over, 0.0, pred.lambda_total

    if version == "nb_total":
        p_over, p_under, p_push = nb_line_probabilities(point.line, pred.lambda_total, dispersion_r)
        return p_over, p_under, p_push, pred.lambda_total

    if version == "nb_market_blend":
        market_mu = solve_market_mu(point.line, market_over_prob, dispersion_r)
        final_mu = pred.lambda_total if market_mu is None else blend_weight * pred.lambda_total + (1.0 - blend_weight) * market_mu
        p_over, p_under, p_push = nb_line_probabilities(point.line, final_mu, dispersion_r)
        return p_over, p_under, p_push, final_mu

    raise ValueError(f"unknown model version: {version}")


def build_rows(
    points: list[MarketPoint],
    predictions: dict[str, Prediction],
    actuals: dict[str, Actual],
    group_r: dict[str, float],
    pooled_r: float,
    *,
    blend_weight: float,
    min_value: float,
    stale_hours: float,
    model_versions: list[str],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    skips: Counter[str] = Counter()
    for point in points:
        match_key = key_for(point.date, point.league, point.home, point.away)
        pred = predictions.get(match_key)
        actual = actuals.get(match_key)
        if pred is None:
            skips["missing_prediction"] += 1
            continue
        if actual is None:
            skips["missing_actual"] += 1
            continue
        over_mkt, under_mkt = devig_pair(point.published.over_odds, point.published.under_odds)
        dispersion_r = group_r.get(point.league, pooled_r)
        market_mu = solve_market_mu(point.line, over_mkt, dispersion_r)
        close_gap_hours = None
        if point.kickoff:
            close_gap_hours = (point.kickoff - point.close.captured_at).total_seconds() / 3600.0
        close_is_stale = close_gap_hours is not None and close_gap_hours > stale_hours
        actual_over = actual.total > point.line
        push_actual = is_integer_line(point.line) and actual.total == int(round(point.line))

        for version in model_versions:
            p_over, p_under, p_push, final_mu = model_probabilities(version, point, pred, over_mkt, dispersion_r, blend_weight)
            for side in ("over", "under"):
                published_odds = point.published.over_odds if side == "over" else point.published.under_odds
                close_odds = point.close.over_odds if side == "over" else point.close.under_odds
                market_prob = over_mkt if side == "over" else under_mkt
                model_prob = p_over if side == "over" else p_under
                model_over_prob = p_over
                model_fair = push_adjusted_fair_decimal(model_prob, p_push)
                value_pct = (model_prob * published_odds + p_push - 1.0) * 100.0
                prob_edge = model_prob - market_prob
                selected = version == "nb_market_blend" and value_pct >= (min_value * 100.0)
                result = result_for(side, point.line, actual.total)
                pnl = pnl_for(result, published_odds)
                clv = (published_odds / close_odds) - 1.0 if close_odds else None
                if push_actual:
                    brier_value = ""
                    logloss_value = ""
                else:
                    brier_value = brier(model_over_prob, actual_over)
                    logloss_value = safe_logloss(model_over_prob, actual_over)
                rows.append({
                    "match_id": match_key,
                    "date": point.date,
                    "league": point.league,
                    "home": point.home,
                    "away": point.away,
                    "kickoff_utc": fmt_dt(point.kickoff),
                    "line": f"{point.line:.1f}",
                    "side": side,
                    "model_version": version,
                    "published_at": fmt_dt(point.published.captured_at),
                    "close_captured_at": fmt_dt(point.close.captured_at),
                    "close_is_stale": "true" if close_is_stale else "false",
                    "published_odds": fmt_num(published_odds),
                    "close_odds": fmt_num(close_odds),
                    "market_fair_prob": fmt_num(market_prob),
                    "market_over_prob": fmt_num(over_mkt),
                    "lambda_model": fmt_num(pred.lambda_total, 4),
                    "lambda_market": fmt_num(market_mu, 4),
                    "lambda_final": fmt_num(final_mu, 4),
                    "dispersion_r": fmt_num(dispersion_r, 4),
                    "model_prob": fmt_num(model_prob),
                    "model_over_prob": fmt_num(model_over_prob),
                    "model_push_prob": fmt_num(p_push),
                    "model_fair_odds": fmt_num(model_fair),
                    "prob_edge": fmt_num(prob_edge),
                    "value_pct": fmt_num(value_pct / 100.0),
                    "selected": "true" if selected else "false",
                    "actual_total": str(actual.total),
                    "result": result,
                    "pnl_units": fmt_num(pnl, 4),
                    "published_to_close_clv": fmt_num(clv),
                    "positive_clv": "true" if clv is not None and clv > 0 else "false",
                    "brier_over": fmt_num(brier_value) if brier_value != "" else "",
                    "logloss_over": fmt_num(logloss_value) if logloss_value != "" else "",
                })
    return rows, skips


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def avg(values: Iterable[float]) -> float | None:
    vals = [v for v in values if v is not None and v == v]
    return sum(vals) / len(vals) if vals else None


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value:+.2f}%"


def fnum(value: float | None, digits: int = 3) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def row_float(row: dict[str, Any], key: str) -> float | None:
    return pf(row.get(key))


def selected_nb(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("model_version") == "nb_market_blend" and r.get("selected") == "true"]


def summarize_bets(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    wins = sum(1 for r in rows if r.get("result") == "won")
    losses = sum(1 for r in rows if r.get("result") == "lost")
    pushes = sum(1 for r in rows if r.get("result") == "push")
    pnl = sum(row_float(r, "pnl_units") or 0.0 for r in rows)
    clv_vals = [row_float(r, "published_to_close_clv") for r in rows]
    clv_vals = [v for v in clv_vals if v is not None]
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "pnl": pnl,
        "roi": (pnl / n * 100.0) if n else None,
        "avg_clv": (sum(clv_vals) / len(clv_vals) * 100.0) if clv_vals else None,
        "pos_clv_share": (sum(1 for v in clv_vals if v > 0) / len(clv_vals) * 100.0) if clv_vals else None,
        "clv_n": len(clv_vals),
    }


def summarize_calibration(rows: list[dict[str, Any]], version: str) -> dict[str, Any]:
    subset = [r for r in rows if r.get("model_version") == version and r.get("side") == "over" and r.get("brier_over") != ""]
    briers = [row_float(r, "brier_over") for r in subset]
    logs = [row_float(r, "logloss_over") for r in subset]
    briers = [v for v in briers if v is not None]
    logs = [v for v in logs if v is not None]
    return {"n": len(subset), "brier": avg(briers), "logloss": avg(logs)}


def append_segment(lines: list[str], title: str, groups: list[tuple[str, list[dict[str, Any]]]]) -> None:
    lines.extend([title, "", "label,n,w-l-p,pnl,roi,avg_clv,pos_clv"])
    for label, rows in groups:
        s = summarize_bets(rows)
        if not s["n"]:
            continue
        lines.append(
            f"{label},{s['n']},{s['wins']}-{s['losses']}-{s['pushes']},{s['pnl']:+.2f}u,{pct(s['roi'])},{pct(s['avg_clv'])},{fnum(s['pos_clv_share'], 1)}%"
        )
    lines.append("")


def render_report(
    rows: list[dict[str, Any]],
    *,
    points_n: int,
    initial_skips: Counter[str],
    row_skips: Counter[str],
    pooled_r: float,
    group_r: dict[str, float],
    min_value: float,
    blend_weight: float,
    stale_hours: float,
) -> str:
    selected = selected_nb(rows)
    selected_fresh = [r for r in selected if r.get("close_is_stale") != "true"]
    lines: list[str] = [
        "Corners v2 real-odds backtest",
        "================================",
        "",
        f"Generated UTC: {fmt_dt(datetime.now(UTC))}",
        f"Market points loaded: {points_n}",
        f"Rows written: {len(rows)}",
        f"Model selected for gate: nb_market_blend",
        f"Fixed min value threshold: {min_value * 100:.1f}%",
        f"Market blend weight: {blend_weight:.3f}",
        f"Stale close threshold: {stale_hours:.1f}h",
        f"Pooled NB dispersion r: {pooled_r:.4f}",
        f"League dispersion r: {dict(sorted((k, round(v, 4)) for k, v in group_r.items()))}",
        f"Pairing skips: {dict(initial_skips)}",
        f"Scoring skips: {dict(row_skips)}",
        "",
        "Calibration control (over outcome, pushes skipped)",
        "model,n,brier,logloss",
    ]
    for version in ("poisson_v1", "nb_total", "nb_market_blend"):
        c = summarize_calibration(rows, version)
        if c["n"]:
            lines.append(f"{version},{c['n']},{fnum(c['brier'], 5)},{fnum(c['logloss'], 5)}")
    lines.append("")

    s = summarize_bets(selected)
    sf = summarize_bets(selected_fresh)
    lines.extend([
        "Selected NB market-blend bets",
        "-----------------------------",
        f"All selected: n={s['n']} W-L-P={s['wins']}-{s['losses']}-{s['pushes']} pnl={s['pnl']:+.2f}u roi={pct(s['roi'])} avg_clv={pct(s['avg_clv'])} pos_clv={fnum(s['pos_clv_share'], 1)}%",
        f"Fresh-close selected: n={sf['n']} W-L-P={sf['wins']}-{sf['losses']}-{sf['pushes']} pnl={sf['pnl']:+.2f}u roi={pct(sf['roi'])} avg_clv={pct(sf['avg_clv'])} pos_clv={fnum(sf['pos_clv_share'], 1)}%",
        "",
        "Sellability gate",
        "----------------",
        "Required: n>=200, mean CLV>=+1.0%, positive CLV share>=55%, ROI>=0%, positive in >=3/5 leagues with n>=40.",
    ])
    pass_n = sf["n"] >= 200
    pass_clv = sf["avg_clv"] is not None and sf["avg_clv"] >= 1.0
    pass_pos = sf["pos_clv_share"] is not None and sf["pos_clv_share"] >= 55.0
    pass_roi = sf["roi"] is not None and sf["roi"] >= 0.0

    league_summaries = {
        league: summarize_bets([r for r in selected_fresh if r.get("league") == league])
        for league in STANDARD_LEAGUES
    }
    qualified_leagues = [league for league, summary in league_summaries.items() if summary["n"] >= 40]
    positive_qualified_leagues = [
        league for league in qualified_leagues
        if league_summaries[league]["avg_clv"] is not None and league_summaries[league]["avg_clv"] > 0.0
    ]
    bad_qualified_leagues = [
        league for league in qualified_leagues
        if league_summaries[league]["avg_clv"] is not None and league_summaries[league]["avg_clv"] < -0.5
    ]

    line_summaries = {
        line: summarize_bets([r for r in selected_fresh if r.get("line") == line])
        for line in sorted({r.get("line") or "" for r in selected_fresh}, key=lambda x: float(x or 0))
    }
    bad_qualified_lines = [
        line for line, summary in line_summaries.items()
        if summary["n"] >= 40 and summary["avg_clv"] is not None and summary["avg_clv"] < -0.5
    ]
    pass_league_positive = len(positive_qualified_leagues) >= 3
    pass_bad_league = not bad_qualified_leagues
    pass_bad_line = not bad_qualified_lines
    all_sell_gates = pass_n and pass_clv and pass_pos and pass_roi and pass_league_positive and pass_bad_league and pass_bad_line

    lines.extend([
        f"n gate: {'PASS' if pass_n else 'FAIL'} ({sf['n']}/200)",
        f"mean CLV gate: {'PASS' if pass_clv else 'FAIL'} ({pct(sf['avg_clv'])})",
        f"positive CLV share gate: {'PASS' if pass_pos else 'FAIL'} ({fnum(sf['pos_clv_share'], 1)}%)",
        f"ROI gate: {'PASS' if pass_roi else 'FAIL'} ({pct(sf['roi'])})",
        f"league breadth gate: {'PASS' if pass_league_positive else 'FAIL'} ({len(positive_qualified_leagues)}/3 positive qualified leagues; qualified={qualified_leagues or '-'})",
        f"bad league guard: {'PASS' if pass_bad_league else 'FAIL'} ({bad_qualified_leagues or '-'})",
        f"bad line-band guard: {'PASS' if pass_bad_line else 'FAIL'} ({bad_qualified_lines or '-'})",
        "Overall sellable: YES" if all_sell_gates else "Overall sellable: NO",
        "",
    ])

    leagues = sorted({r.get("league") or "unknown" for r in selected})
    append_segment(lines, "Selected by league", [(lg, [r for r in selected if r.get("league") == lg]) for lg in leagues])
    append_segment(lines, "Selected by side", [(side, [r for r in selected if r.get("side") == side]) for side in ("over", "under")])
    line_labels = sorted({r.get("line") or "" for r in selected}, key=lambda x: float(x or 0))
    append_segment(lines, "Selected by line", [(line, [r for r in selected if r.get("line") == line]) for line in line_labels])

    lines.extend([
        "Important notes",
        "---------------",
        "- This report uses real captured Pinnacle publication and close prices only.",
        "- Synthetic backtest prices are not used for ROI or CLV.",
        "- Close prices are marked stale when the latest captured pair is more than the stale threshold before kickoff.",
        "- This is a research gate. Corners is not sellable unless the real-odds gate passes.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest corners v2 against real captured Pinnacle corner odds")
    parser.add_argument("--pinnacle", type=Path, default=DEFAULT_PINNACLE)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--actuals", type=Path, default=DEFAULT_ACTUALS)
    parser.add_argument("--out", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--min-value", type=float, default=0.08, help="Fixed value threshold for selected NB rows, decimal")
    parser.add_argument("--blend-weight", type=float, default=0.30, help="Weight on model lambda in market blend")
    parser.add_argument("--stale-hours", type=float, default=12.0)
    parser.add_argument("--models", default="poisson_v1,nb_total,nb_market_blend")
    args = parser.parse_args()

    predictions = load_predictions(args.predictions)
    actuals = load_actuals(args.actuals)
    points, initial_skips = load_snapshot_pairs(args.pinnacle)

    dispersion_rows: list[tuple[str, float]] = []
    for actual in actuals.values():
        dispersion_rows.append((actual.league, float(actual.total)))
    pooled_r, group_r = fit_pooled_and_group_dispersion(dispersion_rows)

    models = [part.strip() for part in args.models.split(",") if part.strip()]
    rows, row_skips = build_rows(
        points,
        predictions,
        actuals,
        group_r,
        pooled_r,
        blend_weight=args.blend_weight,
        min_value=args.min_value,
        stale_hours=args.stale_hours,
        model_versions=models,
    )

    write_csv(args.out, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        render_report(
            rows,
            points_n=len(points),
            initial_skips=initial_skips,
            row_skips=row_skips,
            pooled_r=pooled_r,
            group_r=group_r,
            min_value=args.min_value,
            blend_weight=args.blend_weight,
            stale_hours=args.stale_hours,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {args.out.relative_to(ROOT)} ({len(rows)} rows)")
    print(f"Wrote {args.report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
