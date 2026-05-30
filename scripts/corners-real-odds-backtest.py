#!/usr/bin/env python3
"""Corners v2 real-odds backtest.

This is the only valid corners validation gate. It joins the causal corners
model to captured Pinnacle totals, anchors v2 to the de-vigged market line,
and grades selected bets at real captured odds. Synthetic B365-derived prices
are not used anywhere in this script.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import runpy
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from corners_nb import fit_dispersion, invert_mean_for_over_prob, nb_total_prob_over, nb_total_probs  # noqa: E402

DEFAULT_HISTORICAL = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_PINNACLE = ROOT / "data" / "corners-ou" / "pinnacle-corners-odds.csv"
DEFAULT_OUTPUT = ROOT / "data" / "corners-ou" / "corners-real-odds-backtest-results.csv"
DEFAULT_REPORT = ROOT / "data" / "corners-ou" / "corners-real-odds-backtest-report.txt"

TEAM_ALIASES = {
    "ath bilbao": "athletic bilbao",
    "ath madrid": "atletico madrid",
    "betis": "real betis",
    "borussia monchengladbach": "m gladbach",
    "dortmund": "borussia dortmund",
    "ein frankfurt": "eintracht frankfurt",
    "espanol": "espanyol",
    "hamburg": "hamburger sv",
    "inter": "internazionale",
    "leeds": "leeds united",
    "leverkusen": "bayer leverkusen",
    "man city": "manchester city",
    "man united": "manchester united",
    "milan": "ac milan",
    "newcastle": "newcastle united",
    "nott m forest": "nottingham forest",
    "oviedo": "real oviedo",
    "paris sg": "paris saint germain",
    "sociedad": "real sociedad",
    "st pauli": "st pauli",
    "tottenham": "tottenham hotspur",
    "vallecano": "rayo vallecano",
    "verona": "hellas verona",
    "west ham": "west ham united",
}

OUTPUT_FIELDS = [
    "match_date", "league", "home_team", "away_team", "line", "actual_total", "result_side",
    "kickoff_utc", "published_at_utc", "close_at_utc", "close_is_stale",
    "lambda_poisson", "nb_r", "market_lambda", "lambda_v2", "blend_weight",
    "p_market_over", "p_poisson_over", "p_nb_raw_over", "p_v2_over",
    "pub_over_odds", "pub_under_odds", "close_over_odds", "close_under_odds",
    "ev_over", "ev_under", "selected_side", "selected_odds", "selected_close_odds",
    "selected_ev", "published_to_close_clv", "pnl_units", "bet_result",
    "brier_market", "brier_poisson", "brier_nb_raw", "brier_v2",
]


@dataclass
class Snapshot:
    captured_at: datetime
    kickoff: datetime | None
    over_odds: float
    under_odds: float


def pf(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def fmt_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def norm_team(text: str) -> str:
    raw = (text or "").strip().lower().replace("(corners)", "")
    raw = unicodedata.normalize("NFD", raw)
    raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    raw = re.sub(r"[^a-z0-9]+", " ", raw).strip()
    return TEAM_ALIASES.get(raw, raw)


def is_aggregate_team(text: str) -> bool:
    key = norm_team(text)
    return key.startswith("home teams") or key.startswith("away teams")


def poisson_pmf(k: int, mean: float) -> float:
    if k < 0:
        return 0.0
    mean = max(0.001, mean)
    return math.exp(-mean) * (mean ** k) / math.factorial(k)


def poisson_cdf(k: int, mean: float) -> float:
    if k < 0:
        return 0.0
    return sum(poisson_pmf(i, mean) for i in range(0, min(k, 80) + 1))


def poisson_total_probs(line: float, mean: float) -> tuple[float, float, float]:
    if abs(line - round(line)) < 1e-9:
        exact = int(round(line))
        p_push = poisson_pmf(exact, mean)
        p_under = poisson_cdf(exact - 1, mean)
        return max(0.0, 1.0 - p_under - p_push), p_under, p_push
    threshold = math.floor(line)
    p_under = poisson_cdf(threshold, mean)
    return max(0.0, 1.0 - p_under), p_under, 0.0


def brier(prob: float, actual: bool, push: bool) -> float | None:
    if push:
        return None
    y = 1.0 if actual else 0.0
    return (prob - y) ** 2


def log_loss(prob: float, actual: bool, push: bool) -> float | None:
    if push:
        return None
    p = max(1e-9, min(1.0 - 1e-9, prob))
    return -math.log(p if actual else 1.0 - p)


def load_v1_module() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT_DIR / "corners-ou-model.py"), run_name="corners_ou_model")


def load_predictions(historical_path: Path) -> tuple[list[Any], dict[tuple[str, str, str], dict[str, Any]]]:
    v1 = load_v1_module()
    input_path = v1["resolve_historical_input"](historical_path)
    matches = v1["load_matches"](input_path)
    predictions, _ = v1["run_model"](matches, holdout_start=None)
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in predictions:
        key = (str(row.get("date") or ""), norm_team(row.get("home_team") or ""), norm_team(row.get("away_team") or ""))
        index[key] = row
        # Total-corners market is orientation-invariant; this helps with occasional home/away naming reversals.
        index[(key[0], key[2], key[1])] = row
    return matches, index


def fit_dispersions(matches: list[Any], train_before: date) -> tuple[float, dict[str, float], dict[str, int]]:
    train = [m for m in matches if m.match_date < train_before]
    pooled = fit_dispersion([m.home_corners + m.away_corners for m in train])
    values: dict[str, list[float]] = defaultdict(list)
    for m in train:
        values[m.league].append(m.home_corners + m.away_corners)
    by_league: dict[str, float] = {}
    counts: dict[str, int] = {}
    for league, totals in values.items():
        counts[league] = len(totals)
        by_league[league] = fit_dispersion(totals, fallback=pooled) if len(totals) >= 150 else pooled
    return pooled, by_league, counts


def load_market_snapshots(path: Path) -> dict[tuple[str, str, str, str, str], list[Snapshot]]:
    raw: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            home = row.get("home_team") or ""
            away = row.get("away_team") or ""
            if is_aggregate_team(home) or is_aggregate_team(away):
                continue
            side = str(row.get("side") or "").strip().lower()
            if side not in {"over", "under"}:
                continue
            odds = pf(row.get("odds_decimal"))
            captured = parse_dt(row.get("captured_at"))
            if odds is None or odds <= 1.0 or captured is None:
                continue
            line_val = pf(row.get("line"))
            if line_val is None:
                continue
            line = f"{line_val:.1f}"
            key = (
                str(row.get("match_date") or row.get("kickoff_iso") or "")[:10],
                norm_team(home),
                norm_team(away),
                line,
                fmt_dt(captured),
            )
            item = raw.setdefault(
                key,
                {
                    "league": str(row.get("league") or "").strip().lower(),
                    "home_team": home,
                    "away_team": away,
                    "kickoff": parse_dt(row.get("kickoff_iso")),
                    "captured_at": captured,
                },
            )
            item[f"{side}_odds"] = odds
    grouped: dict[tuple[str, str, str, str, str], list[Snapshot]] = defaultdict(list)
    for key, item in raw.items():
        over = item.get("over_odds")
        under = item.get("under_odds")
        if not over or not under:
            continue
        match_date, home, away, line, _captured = key
        market_key = (match_date, home, away, line, str(item.get("league") or ""))
        grouped[market_key].append(Snapshot(item["captured_at"], item.get("kickoff"), float(over), float(under)))
    for items in grouped.values():
        items.sort(key=lambda snap: snap.captured_at)
    return grouped


def devig_two_way(over_odds: float, under_odds: float) -> tuple[float, float]:
    over_imp = 1.0 / over_odds
    under_imp = 1.0 / under_odds
    total = over_imp + under_imp
    if total <= 0:
        return 0.5, 0.5
    return over_imp / total, under_imp / total


def pre_kickoff_window(items: list[Snapshot]) -> tuple[list[Snapshot], datetime | None]:
    kickoff = next((item.kickoff for item in items if item.kickoff is not None), None)
    if kickoff is None:
        return [], None
    before = [item for item in items if item.captured_at <= kickoff]
    return before, kickoff


def score_markets(
    markets: dict[tuple[str, str, str, str, str], list[Snapshot]],
    predictions: dict[tuple[str, str, str], dict[str, Any]],
    by_league_r: dict[str, float],
    pooled_r: float,
    *,
    blend_weight: float,
    edge_threshold: float,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    misses: Counter[str] = Counter()
    for (match_date, home_key, away_key, line_text, league), items in sorted(markets.items()):
        prediction = predictions.get((match_date, home_key, away_key))
        if prediction is None:
            misses["prediction_not_found"] += 1
            continue
        pre_kickoff, kickoff = pre_kickoff_window(items)
        if kickoff is None:
            misses["missing_kickoff"] += 1
            continue
        if not pre_kickoff:
            misses["no_pre_kickoff_price"] += 1
            continue
        publication = pre_kickoff[0]
        close = pre_kickoff[-1]
        line = float(line_text)
        actual_total = float(prediction.get("actual_total") or 0.0)
        actual_over = actual_total > line
        push = abs(actual_total - line) < 1e-9
        result_side = "push" if push else ("over" if actual_over else "under")
        mean = float(prediction.get("lambda_total") or 0.0)
        r = by_league_r.get(str(prediction.get("league") or league), pooled_r)
        p_market_over, _p_market_under = devig_two_way(publication.over_odds, publication.under_odds)
        market_lambda = invert_mean_for_over_prob(line, p_market_over, r)
        lambda_v2 = blend_weight * mean + (1.0 - blend_weight) * market_lambda
        p_poisson_over, _p_pois_under, _p_pois_push = poisson_total_probs(line, mean)
        p_nb_raw_over, _p_nb_raw_under, _p_nb_raw_push = nb_total_probs(line, mean, r)
        p_v2_over, p_v2_under, p_v2_push = nb_total_probs(line, lambda_v2, r)
        ev_over = p_v2_over * publication.over_odds + p_v2_push - 1.0
        ev_under = p_v2_under * publication.under_odds + p_v2_push - 1.0
        selected_side = ""
        selected_odds = None
        selected_close = None
        selected_ev = None
        if max(ev_over, ev_under) >= edge_threshold:
            if ev_over >= ev_under:
                selected_side = "over"
                selected_odds = publication.over_odds
                selected_close = close.over_odds
                selected_ev = ev_over
            else:
                selected_side = "under"
                selected_odds = publication.under_odds
                selected_close = close.under_odds
                selected_ev = ev_under
        pnl = ""
        bet_result = ""
        clv = ""
        if selected_side:
            if push:
                pnl = 0.0
                bet_result = "push"
            elif selected_side == result_side:
                pnl = selected_odds - 1.0
                bet_result = "won"
            else:
                pnl = -1.0
                bet_result = "lost"
            if selected_close and selected_close > 0:
                clv = (selected_odds / selected_close) - 1.0
        close_gap_hours = (kickoff - close.captured_at).total_seconds() / 3600.0
        row = {
            "match_date": match_date,
            "league": str(prediction.get("league") or league),
            "home_team": prediction.get("home_team") or home_key,
            "away_team": prediction.get("away_team") or away_key,
            "line": line_text,
            "actual_total": int(actual_total),
            "result_side": result_side,
            "kickoff_utc": fmt_dt(publication.kickoff),
            "published_at_utc": fmt_dt(publication.captured_at),
            "close_at_utc": fmt_dt(close.captured_at),
            "close_is_stale": "true" if close_gap_hours is not None and close_gap_hours > 12.0 else "false",
            "lambda_poisson": round(mean, 4),
            "nb_r": round(r, 4),
            "market_lambda": round(market_lambda, 4),
            "lambda_v2": round(lambda_v2, 4),
            "blend_weight": round(blend_weight, 4),
            "p_market_over": round(p_market_over, 6),
            "p_poisson_over": round(p_poisson_over, 6),
            "p_nb_raw_over": round(p_nb_raw_over, 6),
            "p_v2_over": round(p_v2_over, 6),
            "pub_over_odds": round(publication.over_odds, 6),
            "pub_under_odds": round(publication.under_odds, 6),
            "close_over_odds": round(close.over_odds, 6),
            "close_under_odds": round(close.under_odds, 6),
            "ev_over": round(ev_over, 6),
            "ev_under": round(ev_under, 6),
            "selected_side": selected_side,
            "selected_odds": round(selected_odds, 6) if selected_odds else "",
            "selected_close_odds": round(selected_close, 6) if selected_close else "",
            "selected_ev": round(selected_ev, 6) if selected_ev is not None else "",
            "published_to_close_clv": round(clv, 6) if clv != "" else "",
            "pnl_units": round(pnl, 6) if pnl != "" else "",
            "bet_result": bet_result,
            "brier_market": _fmt_metric(brier(p_market_over, actual_over, push)),
            "brier_poisson": _fmt_metric(brier(p_poisson_over, actual_over, push)),
            "brier_nb_raw": _fmt_metric(brier(p_nb_raw_over, actual_over, push)),
            "brier_v2": _fmt_metric(brier(p_v2_over, actual_over, push)),
        }
        rows.append(row)
    keep_best_bet_per_match(rows)
    return rows, misses



def keep_best_bet_per_match(rows: list[dict[str, Any]]) -> None:
    best_by_match: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        if not row.get("selected_side"):
            continue
        key = (str(row.get("match_date") or ""), norm_team(str(row.get("home_team") or "")), norm_team(str(row.get("away_team") or "")))
        current = best_by_match.get(key)
        row_ev = pf(row.get("selected_ev")) or -999.0
        current_ev = pf(current.get("selected_ev")) if current else None
        if current is None or row_ev > (current_ev if current_ev is not None else -999.0):
            best_by_match[key] = row
    keep_ids = {id(row) for row in best_by_match.values()}
    for row in rows:
        if row.get("selected_side") and id(row) not in keep_ids:
            row["selected_side"] = ""
            row["selected_odds"] = ""
            row["selected_close_odds"] = ""
            row["selected_ev"] = ""
            row["published_to_close_clv"] = ""
            row["pnl_units"] = ""
            row["bet_result"] = ""

def _fmt_metric(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"


def avg(values: list[float]) -> float | None:
    vals = [v for v in values if v == v]
    return sum(vals) / len(vals) if vals else None


def pf_row(row: dict[str, Any], key: str) -> float | None:
    return pf(row.get(key))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value:+.2%}"


def render_report(
    rows: list[dict[str, Any]],
    misses: Counter[str],
    *,
    pooled_r: float,
    by_league_r: dict[str, float],
    dispersion_counts: dict[str, int],
    blend_weight: float,
    edge_threshold: float,
) -> str:
    selected = [row for row in rows if row.get("selected_side")]
    settled = [row for row in selected if row.get("bet_result") in {"won", "lost", "push"}]
    non_push = [row for row in rows if row.get("result_side") != "push"]
    pnl = sum(pf_row(row, "pnl_units") or 0.0 for row in settled)
    risked = sum(1 for row in settled if row.get("bet_result") in {"won", "lost"})
    roi = pnl / risked if risked else None
    clv_vals = [pf_row(row, "published_to_close_clv") for row in settled if pf_row(row, "published_to_close_clv") is not None]
    clv_avg = avg([v for v in clv_vals if v is not None])
    clv_pos_share = (sum(1 for v in clv_vals if v is not None and v > 0.0) / len(clv_vals)) if clv_vals else None
    metric_names = ["brier_market", "brier_poisson", "brier_nb_raw", "brier_v2"]
    metric_avgs = {name: avg([pf_row(row, name) for row in non_push if pf_row(row, name) is not None]) for name in metric_names}
    league_clv_gate_count = 0
    league_clv_gate_total = 0
    for league in sorted({str(row.get("league") or "") for row in settled}):
        group = [row for row in settled if row.get("league") == league]
        if len(group) < 40:
            continue
        league_clv_gate_total += 1
        group_clv = avg([pf_row(row, "published_to_close_clv") for row in group if pf_row(row, "published_to_close_clv") is not None])
        if group_clv is not None and group_clv > 0.0:
            league_clv_gate_count += 1
    brier_v2 = metric_avgs.get("brier_v2")
    brier_poisson = metric_avgs.get("brier_poisson")

    lines = [
        "Corners V2 Real-Odds Backtest",
        "",
        "Status: RESEARCH_ONLY - not sellable unless real CLV gates pass.",
        "Validation rule: real captured Pinnacle prices only; synthetic B365 regression is not used.",
        "",
        f"scored_market_lines: {len(rows)}",
        f"selected_bets_at_fixed_edge_one_per_match: {len(selected)}",
        f"settled_selected: {len(settled)}",
        f"edge_threshold: {edge_threshold:.2%}",
        f"blend_weight_model_vs_market: {blend_weight:.2f}",
        f"pooled_nb_r: {pooled_r:.4f}",
        f"join_misses: {dict(misses)}",
        "",
        "Probability calibration on all non-push market lines",
    ]
    for name in metric_names:
        lines.append(f"{name}: {metric_avgs[name]:.6f}" if metric_avgs[name] is not None else f"{name}: -")
    lines.extend([
        "",
        "Selected-bet real-price performance",
        f"pnl_units: {pnl:+.2f}",
        f"risked_bets_no_push: {risked}",
        f"roi_on_risked: {pct(roi)}",
        f"avg_published_to_close_clv: {pct(clv_avg)} (n={len(clv_vals)})",
        f"positive_clv_share: {pct(clv_pos_share)}",
        "",
        "Sell gate (must all pass)",
        f"n>=200: {'PASS' if len(settled) >= 200 else 'FAIL'} ({len(settled)})",
        f"mean_clv>=+1%: {'PASS' if clv_avg is not None and clv_avg >= 0.01 else 'FAIL'} ({pct(clv_avg)})",
        f"positive_clv_share>=55%: {'PASS' if clv_pos_share is not None and clv_pos_share >= 0.55 else 'FAIL'} ({pct(clv_pos_share)})",
        f"v2_brier<=poisson_brier: {'PASS' if brier_v2 is not None and brier_poisson is not None and brier_v2 <= brier_poisson else 'FAIL'} ({brier_v2:.6f} vs {brier_poisson:.6f})" if brier_v2 is not None and brier_poisson is not None else "v2_brier<=poisson_brier: FAIL (-)",
        f"positive_clv_in_3_of_5_leagues_n40: {'PASS' if league_clv_gate_count >= 3 else 'FAIL'} ({league_clv_gate_count}/{league_clv_gate_total})",
        "",
        "League dispersion",
        "league,n_train,nb_r",
    ])
    for league in sorted(by_league_r):
        lines.append(f"{league},{dispersion_counts.get(league, 0)},{by_league_r[league]:.4f}")
    lines.extend(["", "Selected by side"])
    for side in ["over", "under"]:
        group = [row for row in settled if row.get("selected_side") == side]
        group_pnl = sum(pf_row(row, "pnl_units") or 0.0 for row in group)
        group_risk = sum(1 for row in group if row.get("bet_result") in {"won", "lost"})
        lines.append(f"{side}: n={len(group)} pnl={group_pnl:+.2f} roi={pct(group_pnl/group_risk if group_risk else None)}")
    lines.extend(["", "Selected by league"])
    for league in sorted({str(row.get("league") or "") for row in settled}):
        group = [row for row in settled if row.get("league") == league]
        group_pnl = sum(pf_row(row, "pnl_units") or 0.0 for row in group)
        group_risk = sum(1 for row in group if row.get("bet_result") in {"won", "lost"})
        group_clv = avg([pf_row(row, "published_to_close_clv") for row in group if pf_row(row, "published_to_close_clv") is not None])
        lines.append(f"{league}: n={len(group)} pnl={group_pnl:+.2f} roi={pct(group_pnl/group_risk if group_risk else None)} clv={pct(group_clv)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Corners v2 real-odds-only backtest")
    parser.add_argument("--historical", type=Path, default=DEFAULT_HISTORICAL)
    parser.add_argument("--pinnacle", type=Path, default=DEFAULT_PINNACLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--blend-weight", type=float, default=0.30)
    parser.add_argument("--edge-threshold", type=float, default=0.03)
    args = parser.parse_args()

    markets = load_market_snapshots(args.pinnacle)
    if not markets:
        raise SystemExit(f"No valid Pinnacle corner markets loaded from {args.pinnacle}")
    first_market_date = min(date.fromisoformat(key[0]) for key in markets)
    matches, predictions = load_predictions(args.historical)
    pooled_r, by_league_r, dispersion_counts = fit_dispersions(matches, first_market_date)
    rows, misses = score_markets(
        markets,
        predictions,
        by_league_r,
        pooled_r,
        blend_weight=args.blend_weight,
        edge_threshold=args.edge_threshold,
    )
    write_csv(args.output, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        render_report(
            rows,
            misses,
            pooled_r=pooled_r,
            by_league_r=by_league_r,
            dispersion_counts=dispersion_counts,
            blend_weight=args.blend_weight,
            edge_threshold=args.edge_threshold,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {args.output.relative_to(ROOT)}")
    print(f"Wrote {args.report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
