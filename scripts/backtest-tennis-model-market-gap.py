#!/usr/bin/env python3
"""Replay the extreme tennis model/market gap rule on historical real prices.

ML uses the existing 2022-2026 backtest rows and their recorded Pinnacle prices.
The paired handicap study uses only the real 2026 spread snapshots in the spread-v1
training dataset. Missing historical handicap prices are never reconstructed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILES = [ROOT / "data" / "backtest" / f"backtest-results-{year}.csv" for year in range(2022, 2027)]
DEFAULT_SPREAD = ROOT / "data" / "backtest" / "spread-v1-training-dataset.csv"
DEFAULT_RESULTS = ROOT / "data" / "backtest" / "tennis-model-market-gap-historical.csv"
DEFAULT_PAIRED_RESULTS = ROOT / "data" / "backtest" / "tennis-model-market-gap-historical-spread.csv"
DEFAULT_JSON = ROOT / "data" / "backtest" / "tennis-model-market-gap-historical-report.json"
DEFAULT_TEXT = ROOT / "data" / "backtest" / "tennis-model-market-gap-historical-report.txt"
SIDE_FLIP_BUFFER = 0.03
SHORT_FAVORITE_PROB_MAX = 0.80
THRESHOLD_SWEEP_PP = (5.0, 10.0, 15.0, 20.0)
LOCKED_GUARD_PP = 10.0
REGISTERED_REPLACEMENT_EXPERIMENTS = {
    "strict_gap_10_20_same_side": {
        "profile": "strict",
        "min_gap_pp_exclusive": 10.0,
        "max_gap_pp_inclusive": 20.0,
        "description": "Strict-eligible, same-side selections blocked only by a model/market gap above 10pp and at most 20pp.",
    },
    "volume200_gap_10_15_same_side": {
        "profile": "volume_200",
        "min_gap_pp_exclusive": 10.0,
        "max_gap_pp_inclusive": 15.0,
        "description": "Volume-200-eligible, same-side selections blocked only by a model/market gap above 10pp and at most 15pp.",
    },
}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def normal_name(value: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    return " ".join(sorted(re.findall(r"[a-z0-9]+", ascii_name)))


def match_key(date_value: str, player1: str, player2: str) -> tuple[str, str, str]:
    names = sorted((normal_name(player1), normal_name(player2)))
    return (date_value[:10], names[0], names[1])


def ev_bucket(value: float) -> str:
    if value >= 200:
        return "200%+"
    if value >= 100:
        return "100-200%"
    if value >= 50:
        return "50-100%"
    if value >= 30:
        return "30-50%"
    return "under_30%"


def gap_bucket(value: float) -> str:
    if value >= 25:
        return "25pp+"
    if value >= 15:
        return "15-25pp"
    if value >= 10:
        return "10-15pp"
    return "ev_only"


def diagnosis(row: dict[str, str], model_p1: float, market_p1: float) -> str:
    serve_return = number(row.get("p_serve_return"))
    elo = number(row.get("p_elo"))
    raw = number(row.get("our_prob_raw"))
    if serve_return is not None and elo is not None and abs(serve_return - elo) >= 0.15:
        return "component_disagreement"
    if serve_return is not None and abs(serve_return - market_p1) >= 0.20:
        return "serve_return_market_outlier"
    if elo is not None and abs(elo - market_p1) >= 0.20:
        return "elo_market_outlier"
    if raw is not None and abs(raw - model_p1) >= 0.05:
        return "large_calibration_shift"
    return "unexplained_model_market_gap"


def spread_index(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = match_key(row.get("date_iso") or "", row.get("player1") or "", row.get("player2") or "")
        if all(key):
            grouped[key].append(row)
    return {
        key: sorted(candidates, key=lambda row: row.get("captured_at") or "")[0]
        for key, candidates in grouped.items()
    }


def parsed_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def history_index(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = match_key(
            row.get("match_date") or row.get("capture_date") or "",
            row.get("player1_name") or "",
            row.get("player2_name") or "",
        )
        if all(key):
            grouped[key].append(row)
    return grouped


def history_at_spread_capture(
    spread: dict[str, str],
    candidates: list[dict[str, str]],
) -> dict[str, str] | None:
    target = parsed_datetime(spread.get("captured_at") or "")
    if target is None:
        return None
    eligible = [
        row
        for row in candidates
        if (captured := parsed_datetime(row.get("captured_at") or "")) is not None and captured <= target
    ]
    return max(eligible, key=lambda row: parsed_datetime(row.get("captured_at") or "") or datetime.min.replace(tzinfo=timezone.utc)) if eligible else None


def actual_winner_side(row: dict[str, str]) -> str | None:
    winner = normal_name(row.get("actual_winner") or "")
    if winner == normal_name(row.get("player1") or ""):
        return "P1"
    if winner == normal_name(row.get("player2") or ""):
        return "P2"
    return None


def attach_spread(result: dict[str, Any], spread: dict[str, str] | None) -> None:
    result.update(
        {
            "spread_available": "0",
            "spread_selected_line": "",
            "spread_selected_odds": "",
            "spread_outcome": "",
            "spread_pnl_units": "",
            "spread_market_prob_devig": "",
            "spread_captured_at": "",
        }
    )
    if not spread:
        return
    line_p1 = number(spread.get("spread_line"))
    odds1 = number(spread.get("spread_odds1"))
    odds2 = number(spread.get("spread_odds2"))
    margin_p1 = number(spread.get("margin_p1"))
    if line_p1 is None or odds1 is None or odds2 is None or margin_p1 is None or odds1 <= 1 or odds2 <= 1:
        return

    selected_name = normal_name(str(result["selected_player"]))
    spread_p1 = normal_name(spread.get("player1") or "")
    spread_p2 = normal_name(spread.get("player2") or "")
    if selected_name == spread_p1:
        line, odds, selected_margin = line_p1, odds1, margin_p1
    elif selected_name == spread_p2:
        line, odds, selected_margin = -line_p1, odds2, -margin_p1
    else:
        return
    grade = selected_margin + line
    outcome = "WIN" if grade > 1e-9 else "LOSS" if grade < -1e-9 else "PUSH"
    pnl_units = odds - 1.0 if outcome == "WIN" else -1.0 if outcome == "LOSS" else 0.0
    inv1, inv2 = 1.0 / odds1, 1.0 / odds2
    p1_market = inv1 / (inv1 + inv2)
    selected_market = p1_market if selected_name == spread_p1 else 1.0 - p1_market
    result.update(
        {
            "spread_available": "1",
            "spread_selected_line": round(line, 3),
            "spread_selected_odds": round(odds, 4),
            "spread_outcome": outcome,
            "spread_pnl_units": round(pnl_units, 4),
            "spread_market_prob_devig": round(selected_market, 8),
            "spread_captured_at": spread.get("captured_at") or "",
        }
    )


def replay_rows(
    backtest_rows: list[dict[str, str]],
    spreads: dict[tuple[str, str, str], dict[str, str]],
    min_ev_pct: float = 30.0,
    min_gap_pp: float = 10.0,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    output: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for row in backtest_rows:
        model_p1 = number(row.get("our_prob"))
        odds1 = number(row.get("pinnacle_odds"))
        odds2 = number(row.get("pinnacle_odds_loser"))
        if model_p1 is None or odds1 is None or odds2 is None or not 0 < model_p1 < 1 or odds1 <= 1 or odds2 <= 1:
            reasons["invalid_model_or_ml_price"] += 1
            continue
        inv1, inv2 = 1.0 / odds1, 1.0 / odds2
        market_p1 = number(row.get("pinnacle_prob_novig"), inv1 / (inv1 + inv2))
        if market_p1 is None or not 0 < market_p1 < 1:
            reasons["invalid_market_probability"] += 1
            continue
        model_p2, market_p2 = 1.0 - model_p1, 1.0 - market_p1
        ev1 = (model_p1 * odds1 - 1.0) * 100.0
        ev2 = (model_p2 * odds2 - 1.0) * 100.0
        selected_side = "P1" if ev1 >= ev2 else "P2"
        selected_ev = ev1 if selected_side == "P1" else ev2
        selected_odds = odds1 if selected_side == "P1" else odds2
        model_side = "P1" if model_p1 >= 0.5 else "P2"
        market_side = "P1" if market_p1 >= 0.5 else "P2"
        favourite_gap_pp = abs(max(model_p1, model_p2) - max(market_p1, market_p2)) * 100.0
        side_flip = model_side != market_side and abs(model_p1 - 0.5) >= SIDE_FLIP_BUFFER and abs(market_p1 - 0.5) >= SIDE_FLIP_BUFFER
        if selected_ev < min_ev_pct and favourite_gap_pp < min_gap_pp and not side_flip:
            continue
        winner_side = actual_winner_side(row)
        if winner_side is None:
            reasons["winner_name_mismatch"] += 1
            continue
        ml_outcome = "WIN" if selected_side == winner_side else "LOSS"
        ml_pnl = selected_odds - 1.0 if ml_outcome == "WIN" else -1.0
        selected_player = row.get("player1") if selected_side == "P1" else row.get("player2")
        result: dict[str, Any] = {
            "date": row.get("date") or "",
            "year": (row.get("date") or "")[:4],
            "tournament": row.get("tournament") or "",
            "surface": row.get("surface") or "",
            "series": row.get("series") or "",
            "round": row.get("round") or "",
            "player1": row.get("player1") or "",
            "player2": row.get("player2") or "",
            "player1_id": row.get("player1_id") or "",
            "player2_id": row.get("player2_id") or "",
            "selected_side": selected_side,
            "selected_player": selected_player or "",
            "model_side": model_side,
            "market_side": market_side,
            "side_flip": int(side_flip),
            "model_p1": round(model_p1, 8),
            "market_p1_devig": round(market_p1, 8),
            "selected_ml_odds": round(selected_odds, 4),
            "ml_ev_pct": round(selected_ev, 4),
            "model_market_gap_pp": round(favourite_gap_pp, 4),
            "confidence": (row.get("confidence") or "").strip().lower(),
            "model_favorite_prob": round(max(model_p1, model_p2), 8),
            "market_favorite_prob": round(max(market_p1, market_p2), 8),
            "short_favorite_guard": int(
                max(model_p1, model_p2) > SHORT_FAVORITE_PROB_MAX
                or max(market_p1, market_p2) > SHORT_FAVORITE_PROB_MAX
            ),
            "ev_bucket": ev_bucket(selected_ev),
            "gap_bucket": gap_bucket(favourite_gap_pp),
            "diagnosis_primary": diagnosis(row, model_p1, market_p1),
            "ml_outcome": ml_outcome,
            "ml_pnl_units": round(ml_pnl, 4),
            "score": row.get("score") or "",
        }
        spread = spreads.get(match_key(result["date"], result["player1"], result["player2"]))
        attach_spread(result, spread)
        output.append(result)
    return output, reasons


def replay_paired_spreads(
    spread_rows: list[dict[str, str]],
    histories: dict[tuple[str, str, str], list[dict[str, str]]],
    min_ev_pct: float = 30.0,
    min_gap_pp: float = 10.0,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    output: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for spread in spread_rows:
        date_value = spread.get("date_iso") or ""
        player1, player2 = spread.get("player1") or "", spread.get("player2") or ""
        candidates = histories.get(match_key(date_value, player1, player2), [])
        if not candidates:
            reasons["no_local_ml_history"] += 1
            continue
        history = history_at_spread_capture(spread, candidates)
        if history is None:
            reasons["no_ml_snapshot_before_spread_capture"] += 1
            continue
        model_p1 = number(spread.get("p1_match_prob"))
        history_reversed = normal_name(history.get("player1_name") or "") != normal_name(player1)
        odds1 = number(history.get("odds2" if history_reversed else "odds1"))
        odds2 = number(history.get("odds1" if history_reversed else "odds2"))
        margin_p1 = number(spread.get("margin_p1"))
        if model_p1 is None or odds1 is None or odds2 is None or margin_p1 is None or not 0 < model_p1 < 1 or odds1 <= 1 or odds2 <= 1:
            reasons["invalid_paired_input"] += 1
            continue
        inv1, inv2 = 1.0 / odds1, 1.0 / odds2
        market_p1 = inv1 / (inv1 + inv2)
        model_p2, market_p2 = 1.0 - model_p1, 1.0 - market_p1
        ev1 = (model_p1 * odds1 - 1.0) * 100.0
        ev2 = (model_p2 * odds2 - 1.0) * 100.0
        selected_side = "P1" if ev1 >= ev2 else "P2"
        selected_ev = ev1 if selected_side == "P1" else ev2
        selected_odds = odds1 if selected_side == "P1" else odds2
        model_side = "P1" if model_p1 >= 0.5 else "P2"
        market_side = "P1" if market_p1 >= 0.5 else "P2"
        favourite_gap_pp = abs(max(model_p1, model_p2) - max(market_p1, market_p2)) * 100.0
        side_flip = model_side != market_side and abs(model_p1 - 0.5) >= SIDE_FLIP_BUFFER and abs(market_p1 - 0.5) >= SIDE_FLIP_BUFFER
        if selected_ev < min_ev_pct and favourite_gap_pp < min_gap_pp and not side_flip:
            continue
        if abs(margin_p1) < 1e-9:
            reasons["zero_game_margin"] += 1
            continue
        winner_side = "P1" if margin_p1 > 0 else "P2"
        ml_outcome = "WIN" if selected_side == winner_side else "LOSS"
        selected_player = player1 if selected_side == "P1" else player2
        result: dict[str, Any] = {
            "date": date_value,
            "year": date_value[:4],
            "tournament": history.get("league_name") or "",
            "surface": spread.get("surface") or "",
            "series": spread.get("series") or spread.get("league") or "",
            "round": "",
            "player1": player1,
            "player2": player2,
            "player1_id": "",
            "player2_id": "",
            "selected_side": selected_side,
            "selected_player": selected_player,
            "model_side": model_side,
            "market_side": market_side,
            "side_flip": int(side_flip),
            "model_p1": round(model_p1, 8),
            "market_p1_devig": round(market_p1, 8),
            "selected_ml_odds": round(selected_odds, 4),
            "ml_ev_pct": round(selected_ev, 4),
            "model_market_gap_pp": round(favourite_gap_pp, 4),
            "ev_bucket": ev_bucket(selected_ev),
            "gap_bucket": gap_bucket(favourite_gap_pp),
            "diagnosis_primary": "paired_capture_gap",
            "ml_outcome": ml_outcome,
            "ml_pnl_units": round(selected_odds - 1.0 if ml_outcome == "WIN" else -1.0, 4),
            "score": "",
            "ml_captured_at": history.get("captured_at") or "",
        }
        attach_spread(result, spread)
        if result["spread_available"] != "1":
            reasons["invalid_spread_grade"] += 1
            continue
        output.append(result)
    return output, reasons


def bootstrap_roi_ci(pnl_values: list[float], iterations: int = 2000) -> list[float] | None:
    if len(pnl_values) < 2:
        return None
    rng = random.Random(240713)
    n = len(pnl_values)
    samples = sorted(sum(rng.choice(pnl_values) for _ in range(n)) / n * 100.0 for _ in range(iterations))
    return [round(samples[int(iterations * 0.025)], 2), round(samples[int(iterations * 0.975)], 2)]


def performance(rows: list[dict[str, Any]], prefix: str, include_ci: bool = True) -> dict[str, Any]:
    outcome_key, pnl_key = f"{prefix}_outcome", f"{prefix}_pnl_units"
    decided = [row for row in rows if row.get(outcome_key) in {"WIN", "LOSS", "PUSH"}]
    pnl_values = [float(row[pnl_key]) for row in decided]
    wins = sum(row[outcome_key] == "WIN" for row in decided)
    losses = sum(row[outcome_key] == "LOSS" for row in decided)
    pushes = len(decided) - wins - losses
    pnl_units = sum(pnl_values)
    return {
        "settled": len(decided),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "pnl_units": round(pnl_units, 2),
        "roi_pct": round(pnl_units / len(decided) * 100.0, 2) if decided else None,
        "roi_95ci_pct": bootstrap_roi_ci(pnl_values) if include_ci else None,
    }


def segment_report(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for value in sorted({str(row.get(field) or "unknown") for row in rows}):
        group = [row for row in rows if str(row.get(field) or "unknown") == value]
        output[value] = {
            "anomalies": len(group),
            "ml": performance(group, "ml", include_ci=False),
            "spread": performance([row for row in group if row.get("spread_available") == "1"], "spread", include_ci=False),
        }
    return output


def profile_eligible(row: dict[str, Any], profile: str) -> bool:
    """Apply the registered profile rules without the model/market gap guard."""
    if bool(int(row.get("short_favorite_guard") or 0)):
        return False
    surface = str(row.get("surface") or "")
    series = str(row.get("series") or "")
    confidence = str(row.get("confidence") or "").lower()
    value = float(row.get("ml_ev_pct") or 0.0)
    if profile == "broad_value_10":
        return value >= 10.0
    if profile == "strict":
        return surface == "Hard" and series == "Masters 1000" and confidence == "high" and value >= 10.0
    if profile == "volume_200":
        if confidence not in {"high", "medium"}:
            return False
        rules = (
            ("Hard", "Masters 1000", "high", 15.0),
            ("Hard", "Masters 1000", "medium", 30.0),
            ("Hard", "Grand Slam", confidence, 5.0),
            ("Hard", "ATP500", confidence, 10.0),
            ("Clay", "ATP500", confidence, 10.0),
        )
        return any(
            surface == rule_surface
            and series == rule_series
            and confidence == rule_confidence
            and value >= min_value
            for rule_surface, rule_series, rule_confidence, min_value in rules
        )
    raise ValueError(f"Unknown threshold-audit profile: {profile}")


def threshold_partition(rows: list[dict[str, Any]], threshold_pp: float) -> dict[str, Any]:
    allowed = [
        row
        for row in rows
        if not bool(int(row.get("side_flip") or 0))
        and float(row.get("model_market_gap_pp") or 0.0) <= threshold_pp
    ]
    gap_blocked = [
        row
        for row in rows
        if not bool(int(row.get("side_flip") or 0))
        and float(row.get("model_market_gap_pp") or 0.0) > threshold_pp
    ]
    side_flip_blocked = [row for row in rows if bool(int(row.get("side_flip") or 0))]
    blocked = gap_blocked + side_flip_blocked
    return {
        "threshold_pp": threshold_pp,
        "candidates": len(rows),
        "allowed": performance(allowed, "ml", include_ci=False),
        "blocked": performance(blocked, "ml", include_ci=False),
        "gap_blocked": performance(gap_blocked, "ml", include_ci=False),
        "side_flip_blocked": performance(side_flip_blocked, "ml", include_ci=False),
        "blocked_side_flips": len(side_flip_blocked),
    }


def registered_replacement_rows(universe: list[dict[str, Any]], experiment: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the frozen cohort for a forward guard-replacement experiment."""
    minimum = float(experiment["min_gap_pp_exclusive"])
    maximum = float(experiment["max_gap_pp_inclusive"])
    profile = str(experiment["profile"])
    return [
        row
        for row in universe
        if profile_eligible(row, profile)
        and not bool(int(row.get("side_flip") or 0))
        and minimum < float(row.get("model_market_gap_pp") or 0.0) <= maximum
    ]


def historical_screening(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_year = {
        year: performance(
            [row for row in rows if str(row.get("year") or "unknown") == year],
            "ml",
            include_ci=False,
        )
        for year in sorted({str(row.get("year") or "unknown") for row in rows})
    }
    material_years = [metric for metric in by_year.values() if metric["settled"] >= 20]
    positive_years = sum((metric["roi_pct"] or 0.0) > 0 for metric in material_years)
    overall = performance(rows, "ml")
    checks = {
        "settled_at_least_100": overall["settled"] >= 100,
        "roi_positive": overall["roi_pct"] is not None and overall["roi_pct"] > 0,
        "at_least_two_positive_material_years": len(material_years) >= 2 and positive_years >= 2,
        "no_material_year_below_minus_15pct": all(
            metric["roi_pct"] is not None and metric["roi_pct"] >= -15.0 for metric in material_years
        ),
    }
    return {
        "performance": overall,
        "by_year": by_year,
        "material_years": len(material_years),
        "positive_material_years": positive_years,
        "checks": checks,
        "passes_retrospective_screen": all(checks.values()),
        "decision": "FORWARD_PROOF_REQUIRED",
    }


def build_registered_replacement_experiments(universe: list[dict[str, Any]]) -> dict[str, Any]:
    experiments: dict[str, Any] = {}
    for experiment_id, definition in REGISTERED_REPLACEMENT_EXPERIMENTS.items():
        rows = registered_replacement_rows(universe, definition)
        experiments[experiment_id] = {
            **definition,
            **historical_screening(rows),
            "by_surface": {
                surface: performance(
                    [row for row in rows if str(row.get("surface") or "unknown") == surface],
                    "ml",
                    include_ci=False,
                )
                for surface in sorted({str(row.get("surface") or "unknown") for row in rows})
            },
        }

    broad = [row for row in universe if profile_eligible(row, "broad_value_10")]
    side_flips = [row for row in broad if bool(int(row.get("side_flip") or 0))]
    side_flip_surfaces = {
        surface: historical_screening(
            [row for row in side_flips if str(row.get("surface") or "unknown") == surface]
        )
        for surface in sorted({str(row.get("surface") or "unknown") for row in side_flips})
    }
    return {
        "registered_at": "2026-07-18",
        "status": "SHADOW_ONLY_NO_LIVE_ROUTING_CHANGE",
        "automatic_promotion": False,
        "forward_gate": "n>=150 settled, ROI>0, mean CLV>=+0.5%, positive CLV share>=55%; manual model-risk review required",
        "experiments": experiments,
        "side_flip_surface_diagnostics": side_flip_surfaces,
        "warning": "Retrospective screening can reject a cohort but cannot promote it. Forward frozen prices and CLV are mandatory.",
    }


def build_threshold_audit(universe: list[dict[str, Any]]) -> dict[str, Any]:
    profiles = {
        "broad_value_10": "All otherwise-eligible selections with raw value >=10%.",
        "strict": "Hard | Masters 1000 | high confidence | raw value >=10%.",
        "volume_200": "Current registered volume_200 cells and value floors.",
    }
    profile_reports: dict[str, Any] = {}
    for profile, description in profiles.items():
        candidates = [row for row in universe if profile_eligible(row, profile)]
        profile_reports[profile] = {
            "description": description,
            "candidates": len(candidates),
            "cutoffs": {
                f"{threshold:g}": threshold_partition(candidates, threshold)
                for threshold in THRESHOLD_SWEEP_PP
            },
        }

    broad = [row for row in universe if profile_eligible(row, "broad_value_10")]
    fixed_surface = {
        surface: threshold_partition(
            [row for row in broad if str(row.get("surface") or "unknown") == surface],
            LOCKED_GUARD_PP,
        )
        for surface in sorted({str(row.get("surface") or "unknown") for row in broad})
    }
    fixed_year = {
        year: threshold_partition(
            [row for row in broad if str(row.get("year") or "unknown") == year],
            LOCKED_GUARD_PP,
        )
        for year in sorted({str(row.get("year") or "unknown") for row in broad})
    }
    return {
        "status": "DESCRIPTIVE_ONLY_NO_AUTOMATIC_POLICY_CHANGE",
        "locked_guard_pp": LOCKED_GUARD_PP,
        "thresholds_pp": list(THRESHOLD_SWEEP_PP),
        "short_favorite_guard_preserved": "model or market favourite probability >80%",
        "side_flip_guard_preserved": True,
        "profiles": profile_reports,
        "locked_10pp_by_surface": fixed_surface,
        "locked_10pp_by_year": fixed_year,
        "decision": "KEEP_LOCKED_PENDING_FORWARD_ROI_AND_CLV",
        "warning": "Do not select the best cutoff from this same retrospective sample.",
        "registered_replacement_experiments": build_registered_replacement_experiments(universe),
    }


def build_report(
    rows: list[dict[str, Any]],
    paired: list[dict[str, Any]],
    source_rows: int,
    reasons: Counter[str],
    paired_reasons: Counter[str] | None = None,
    universe: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ml_losses = [row for row in paired if row.get("ml_outcome") == "LOSS"]
    spread_rescues = sum(row.get("spread_outcome") == "WIN" for row in ml_losses)
    spread_perf = performance(paired, "spread")
    if spread_perf["settled"] < 50:
        verdict = "INSUFFICIENT_REAL_SPREAD_SAMPLE"
    elif spread_perf["roi_pct"] is not None and spread_perf["roi_pct"] > 0 and (spread_perf["roi_95ci_pct"] or [-100])[0] > -5:
        verdict = "SUPPORTS_LIVE_COLLECTION_ONLY"
    else:
        verdict = "DOES_NOT_SUPPORT_HANDICAP_HYPOTHESIS"
    long_ev = [row for row in rows if float(row["ml_ev_pct"]) >= 100]
    long_ev_paired = [row for row in paired if float(row["ml_ev_pct"]) >= 100]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "RETROSPECTIVE_DIAGNOSTIC_ONLY",
        "method": "Fixed live thresholds; flat 1u; real recorded ML prices; real captured 2026 spreads only; no synthetic handicap prices.",
        "source_matches": source_rows,
        "anomalies": len(rows),
        "ml": performance(rows, "ml"),
        "paired_real_spread_matches": len(paired),
        "spread": spread_perf,
        "ml_losses_with_spread": len(ml_losses),
        "spread_rescues": spread_rescues,
        "spread_rescue_rate_pct": round(spread_rescues / len(ml_losses) * 100.0, 2) if ml_losses else None,
        "long_ev_100_plus": {
            "anomalies": len(long_ev),
            "ml": performance(long_ev, "ml"),
            "paired_spread_anomalies": len(long_ev_paired),
            "spread": performance(long_ev_paired, "spread"),
        },
        "screening_verdict": verdict,
        "threshold_audit": build_threshold_audit(universe or rows),
        "segments": {
            field: segment_report(rows, field)
            for field in ("year", "surface", "series", "ev_bucket", "gap_bucket", "diagnosis_primary")
        },
        "paired_segments": {
            field: segment_report(paired, field)
            for field in ("surface", "series", "ev_bucket", "gap_bucket")
        },
        "skip_reasons": {"ml_replay": dict(reasons), "paired_spread": dict(paired_reasons or {})},
        "limitations": [
            "Historical probabilities are retrospective model outputs, not frozen live publications.",
            "Real handicap prices are available only for a limited 2026 capture subset.",
            "The historical handicap snapshots are not guaranteed closing prices, so no historical CLV claim is made.",
            "This report can reject or support continued live collection; it cannot promote a live model.",
        ],
    }


def format_perf(metric: dict[str, Any]) -> str:
    roi = "n/a" if metric["roi_pct"] is None else f"{metric['roi_pct']:+.2f}%"
    ci = "n/a" if metric["roi_95ci_pct"] is None else f"[{metric['roi_95ci_pct'][0]:+.2f}%, {metric['roi_95ci_pct'][1]:+.2f}%]"
    return f"n={metric['settled']} {metric['wins']}W/{metric['losses']}L/{metric['pushes']}P P/L={metric['pnl_units']:+.2f}u ROI={roi} 95%CI={ci}"


def report_text(report: dict[str, Any]) -> str:
    long_ev = report["long_ev_100_plus"]
    lines = [
        "TENNIS EXTREME GAP HISTORICAL REPLAY",
        "====================================",
        f"Generated: {report['generated_at']}",
        f"Status: {report['status']}",
        f"Screening verdict: {report['screening_verdict']}",
        "",
        f"Source matches: {report['source_matches']}",
        f"Triggered anomalies: {report['anomalies']}",
        f"ML: {format_perf(report['ml'])}",
        "",
        f"Real paired handicap matches: {report['paired_real_spread_matches']}",
        f"Spread: {format_perf(report['spread'])}",
        f"ML losses rescued by spread: {report['spread_rescues']}/{report['ml_losses_with_spread']} ({report['spread_rescue_rate_pct'] if report['spread_rescue_rate_pct'] is not None else 'n/a'}%)",
        "",
        f"ML EV >=100% anomalies: {long_ev['anomalies']}",
        f"  ML: {format_perf(long_ev['ml'])}",
        f"  Spread: {format_perf(long_ev['spread'])}",
        "",
        "Year cuts",
    ]
    for year, segment in report["segments"]["year"].items():
        lines.append(f"  {year}: ML {format_perf(segment['ml'])} | Spread {format_perf(segment['spread'])}")
    threshold_audit = report["threshold_audit"]
    lines.extend([
        "",
        "Gap guard threshold audit (descriptive only)",
        "  Cutoffs are compared on the same historical sample. The live 10pp rule is not auto-changed.",
    ])
    for profile, payload in threshold_audit["profiles"].items():
        lines.append(f"  [{profile}] {payload['description']}")
        for cutoff, result in payload["cutoffs"].items():
            lines.append(
                f"    {cutoff}pp: allowed {format_perf(result['allowed'])} | "
                f"gap-blocked {format_perf(result['gap_blocked'])} | "
                f"side-flips {format_perf(result['side_flip_blocked'])}"
            )
    lines.append("  Locked 10pp surface cuts (broad value >=10%)")
    for surface, result in threshold_audit["locked_10pp_by_surface"].items():
        lines.append(
            f"    {surface}: allowed {format_perf(result['allowed'])} | "
            f"gap-blocked {format_perf(result['gap_blocked'])} | "
            f"side-flips {format_perf(result['side_flip_blocked'])}"
        )
    registered = threshold_audit["registered_replacement_experiments"]
    lines.extend(
        [
            "",
            "Registered guard-replacement experiments (retrospective screen only)",
            f"  Status: {registered['status']}",
        ]
    )
    for experiment_id, experiment in registered["experiments"].items():
        lines.append(
            f"  {experiment_id}: {format_perf(experiment['performance'])} | "
            f"years +ROI {experiment['positive_material_years']}/{experiment['material_years']} | "
            f"screen={'PASS' if experiment['passes_retrospective_screen'] else 'FAIL'}"
        )
    lines.append("  Side flips remain surface-split shadow evidence; they are not part of either replacement cohort.")
    lines.extend(["", "Limitations"] + [f"- {item}" for item in report["limitations"]])
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", default=[str(path) for path in DEFAULT_FILES])
    parser.add_argument("--spread-dataset", default=str(DEFAULT_SPREAD))
    parser.add_argument("--history-dir", default=str(ROOT / "data" / "pinnacle-history"))
    parser.add_argument("--min-ev-pct", type=float, default=30.0)
    parser.add_argument("--min-gap-pp", type=float, default=10.0)
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--paired-results", default=str(DEFAULT_PAIRED_RESULTS))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    parser.add_argument("--text", default=str(DEFAULT_TEXT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backtest_rows: list[dict[str, str]] = []
    for value in args.files:
        backtest_rows.extend(load_csv(Path(value)))
    spread_rows = load_csv(Path(args.spread_dataset))
    history_rows: list[dict[str, str]] = []
    for path in sorted(Path(args.history_dir).glob("pinnacle-history-*.csv")):
        history_rows.extend(load_csv(path))
    universe, reasons = replay_rows(backtest_rows, {}, -1_000_000_000.0, 1_000_000_000.0)
    rows = [
        row
        for row in universe
        if float(row["ml_ev_pct"]) >= args.min_ev_pct
        or float(row["model_market_gap_pp"]) >= args.min_gap_pp
        or bool(int(row.get("side_flip") or 0))
    ]
    paired_rows, paired_reasons = replay_paired_spreads(
        spread_rows,
        history_index(history_rows),
        args.min_ev_pct,
        args.min_gap_pp,
    )
    report = build_report(rows, paired_rows, len(backtest_rows), reasons, paired_reasons, universe=universe)
    results_path, paired_results_path, json_path, text_path = Path(args.results), Path(args.paired_results), Path(args.json), Path(args.text)
    write_csv(results_path, rows)
    write_csv(paired_results_path, paired_rows)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    text_path.write_text(report_text(report), encoding="utf-8")
    print(f"Historical anomalies: {report['anomalies']} / {report['source_matches']}")
    print(f"ML: {format_perf(report['ml'])}")
    print(f"Real paired spread: {format_perf(report['spread'])}")
    print(f"Verdict: {report['screening_verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
