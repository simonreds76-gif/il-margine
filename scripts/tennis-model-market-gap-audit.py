#!/usr/bin/env python3
"""Capture extreme tennis model/market disagreements as research hypotheses.

This lane never changes public fair-odds routing. It freezes the first observed
ML price and, when available, the same player's Pinnacle handicap so the two
ideas can be settled independently. Registered ML replacement cohorts may be
shown in the private ops digest as provisional selections while their own
forward ROI and CLV evidence accumulates.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_LIVE = ROOT / "data" / "backtest" / "tennis-model-market-gap-live.csv"
DEFAULT_ARCHIVE = ROOT / "data" / "backtest" / "tennis-model-market-gap-archive.csv"
DEFAULT_STATUS = ROOT / "data" / "backtest" / "tennis-model-market-gap-status.json"
DEFAULT_PINNACLE_DIR = ROOT / "data"
DEFAULT_PLAYERS = ROOT / "data" / "oncourt" / "players_atp.csv"
DEFAULT_TOURS = ROOT / "data" / "oncourt" / "tours_atp.csv"

DEFAULT_MIN_EV_PCT = 30.0
DEFAULT_GAP_PP = 10.0
SIDE_FLIP_BUFFER = 0.03
SHORT_FAVORITE_PROB_MAX = 0.80
REGISTERED_REPLACEMENT_AT = "2026-07-18"

SETTLEMENT_FIELDS = [
    "settlement_status",
    "result",
    "bet_outcome",
    "won_bet",
    "match_date",
    "player1_id",
    "player2_id",
    "winner_id",
    "loser_id",
    "settled_at",
    "settlement_note",
    "closing_odds1",
    "closing_odds2",
    "closing_source",
    "game_margin",
]


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip().replace("\r", "")
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def finite_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                fields.append(field)
                seen.add(field)
    if not fields:
        fields = ["anomaly_id", "date", "player1", "player2", "signal_profile"]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def normalize_name(name: Any) -> str:
    text = unicodedata.normalize("NFKD", str(name or "").lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def canonical_name(name: Any) -> str:
    """Full-token identity that tolerates Last/First order without surname matching."""
    return " ".join(sorted(normalize_name(name).split()))


def pair_key(player1: Any, player2: Any) -> tuple[str, str]:
    return tuple(sorted((canonical_name(player1), canonical_name(player2))))


def read_name_map(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for row in load_csv(path):
        identifier = finite_int(row.get("id"))
        name = str(row.get("name") or "").strip()
        if identifier is not None and name and "/" not in name:
            out[identifier] = name
    return out


def read_tour_map(path: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in load_csv(path):
        identifier = finite_int(row.get("id"))
        if identifier is not None:
            out[identifier] = {
                "name": str(row.get("name") or "").strip(),
                "rank": finite_int(row.get("rank")),
            }
    return out


def series_bucket(tour_name: str, tour_rank: int | None) -> str:
    upper = tour_name.upper()
    if any(token in upper for token in ("WIMBLEDON", "ROLAND GARROS", "FRENCH OPEN", "US OPEN", "AUSTRALIAN OPEN")):
        return "Grand Slam"
    if "CHALLENGER" in upper:
        return "Challenger"
    if "MASTERS" in upper or "1000" in upper:
        return "Masters 1000"
    if "500" in upper or tour_rank == 2:
        return "ATP500"
    if tour_rank in {1, 4}:
        return "Grand Slam"
    if tour_rank == 3:
        return "Masters 1000"
    return "ATP250"


def supabase() -> tuple[str, dict[str, str]]:
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise RuntimeError("missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    return f"{url}/rest/v1", {"apikey": key, "Authorization": f"Bearer {key}"}


def fetch_fair_rows() -> list[dict[str, Any]]:
    base, headers = supabase()
    extended = (
        "id,tour_id,player1_id,player2_id,surface,p1_win_prob_raw,p2_win_prob_raw,"
        "p1_win_prob,p2_win_prob,odds1,odds2,p_a,p_b,p_serve_return,p_elo,confidence,"
        "spread_line,spread_odds1,spread_odds2,handicap_edge_p1,handicap_edge_p2,"
        "match_count_12m_p1,match_count_12m_p2,matches_total_p1,matches_total_p2,"
        "recent_challenger_plus_p1,recent_challenger_plus_p2,last_match_days_p1,"
        "last_match_days_p2,data_coverage_tag"
    )
    fallback = (
        "id,tour_id,player1_id,player2_id,surface,p1_win_prob,p2_win_prob,odds1,odds2,"
        "p_a,p_b,confidence,spread_line,spread_odds1,spread_odds2,handicap_edge_p1,handicap_edge_p2"
    )
    response = requests.get(
        f"{base}/daily_fair_odds",
        headers=headers,
        params={"select": extended, "limit": 2500},
        timeout=30,
    )
    if response.status_code >= 400:
        response = requests.get(
            f"{base}/daily_fair_odds",
            headers=headers,
            params={"select": fallback, "limit": 2500},
            timeout=30,
        )
    response.raise_for_status()
    return response.json() or []


def latest_pinnacle_file(capture_day: date, directory: Path) -> Path | None:
    exact = directory / f"pinnacle-odds-{capture_day.isoformat()}.csv"
    if exact.exists():
        return exact
    candidates = sorted(directory.glob("pinnacle-odds-????-??-??.csv"), reverse=True)
    for path in candidates:
        try:
            file_day = date.fromisoformat(path.stem.removeprefix("pinnacle-odds-"))
        except ValueError:
            continue
        if 0 <= (capture_day - file_day).days <= 1:
            return path
    return None


def build_pinnacle_index(rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str], list[dict[str, str]]], int]:
    index: dict[tuple[str, str], list[dict[str, str]]] = {}
    ignored = 0
    for row in rows:
        p1 = row.get("player1_name") or ""
        p2 = row.get("player2_name") or ""
        if not p1 or not p2 or "/" in p1 or "/" in p2:
            ignored += 1
            continue
        index.setdefault(pair_key(p1, p2), []).append(row)
    return index, ignored


def orient_pinnacle(
    fair_p1: str,
    fair_p2: str,
    candidates: list[dict[str, str]],
) -> tuple[dict[str, Any] | None, str]:
    exact: list[tuple[dict[str, str], bool]] = []
    c1 = canonical_name(fair_p1)
    c2 = canonical_name(fair_p2)
    for row in candidates:
        r1 = canonical_name(row.get("player1_name"))
        r2 = canonical_name(row.get("player2_name"))
        if r1 == c1 and r2 == c2:
            exact.append((row, False))
        elif r1 == c2 and r2 == c1:
            exact.append((row, True))
    if not exact:
        return None, "full_name_mismatch"
    unique = {
        (
            item[0].get("player1_name"),
            item[0].get("player2_name"),
            item[0].get("match_date"),
            item[1],
        ): item
        for item in exact
    }
    if len(unique) != 1:
        return None, "ambiguous_exact_pair"
    row, reversed_for_fair = next(iter(unique.values()))
    odds1 = finite_float(row.get("odds2" if reversed_for_fair else "odds1"))
    odds2 = finite_float(row.get("odds1" if reversed_for_fair else "odds2"))
    spread_line = finite_float(row.get("spread_line"))
    if spread_line is not None and reversed_for_fair:
        spread_line = -spread_line
    return {
        **row,
        "odds1_oriented": odds1,
        "odds2_oriented": odds2,
        "spread_line_oriented": spread_line,
        "spread_odds1_oriented": finite_float(row.get("spread_odds2" if reversed_for_fair else "spread_odds1")),
        "spread_odds2_oriented": finite_float(row.get("spread_odds1" if reversed_for_fair else "spread_odds2")),
        "reversed_for_fair": reversed_for_fair,
    }, "matched"


def best_of_match_probability(p_a: float | None, p_b: float | None, best_of: int) -> float | None:
    if p_a is None or p_b is None or not (0 < p_a < 1 and 0 < p_b < 1):
        return None
    from src.lib.tennis_prob import prob_match_best_of_3, prob_match_best_of_5

    return prob_match_best_of_5(p_a, p_b) if best_of == 5 else prob_match_best_of_3(p_a, p_b)


def diagnosis(
    fair: dict[str, Any],
    model_p1: float,
    market_p1: float,
    model_side: str,
    market_side: str,
    point_match_p1: float | None,
) -> tuple[list[str], str, str]:
    tags: list[str] = []
    gap = abs(max(model_p1, 1 - model_p1) - max(market_p1, 1 - market_p1))
    if model_side != market_side:
        tags.append("market_side_flip")
    if gap >= 0.25:
        tags.append("critical_gap_25pp")
    elif gap >= 0.15:
        tags.append("large_gap_15pp")
    else:
        tags.append("guard_gap_10pp")

    coverage = str(fair.get("data_coverage_tag") or "").strip().upper()
    if coverage and coverage not in {"FULL", "HIGH"}:
        tags.append("partial_coverage")
    samples = [finite_int(fair.get("match_count_12m_p1")), finite_int(fair.get("match_count_12m_p2"))]
    known_samples = [value for value in samples if value is not None]
    if known_samples and min(known_samples) < 20:
        tags.append("low_12m_sample")
    inactivity = [finite_float(fair.get("last_match_days_p1")), finite_float(fair.get("last_match_days_p2"))]
    if any(value is not None and value > 45 for value in inactivity):
        tags.append("inactivity_45d")

    serve_return = finite_float(fair.get("p_serve_return"))
    elo = finite_float(fair.get("p_elo"))
    if serve_return is not None and elo is not None:
        if abs(serve_return - elo) >= 0.15:
            tags.append("component_disagreement")
        if abs(serve_return - market_p1) >= 0.20:
            tags.append("serve_return_market_outlier")
        if abs(elo - market_p1) >= 0.20:
            tags.append("elo_market_outlier")

    raw = finite_float(fair.get("p1_win_prob_raw"))
    if raw is not None and abs(raw - model_p1) >= 0.05:
        tags.append("large_calibration_shift")
    if point_match_p1 is not None and abs(point_match_p1 - model_p1) >= 0.08:
        tags.append("point_shape_divergence")

    causal_priority = (
        "partial_coverage",
        "low_12m_sample",
        "component_disagreement",
        "point_shape_divergence",
        "large_calibration_shift",
        "inactivity_45d",
    )
    primary = next((tag for tag in causal_priority if tag in tags), "unexplained_model_market_gap")
    quality = "LOW" if any(tag in tags for tag in ("partial_coverage", "low_12m_sample")) else "MEDIUM"
    if primary == "unexplained_model_market_gap" and gap < 0.15:
        quality = "HIGH"
    return tags, primary, quality


def policy_profile_eligible(
    surface: str,
    series: str,
    confidence: str,
    value_pct: float,
    short_favorite_guard: bool,
    profile: str,
) -> bool:
    if short_favorite_guard:
        return False
    confidence = confidence.lower()
    if profile == "strict":
        return surface == "Hard" and series == "Masters 1000" and confidence == "high" and value_pct >= 10.0
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
            and value_pct >= minimum
            for rule_surface, rule_series, rule_confidence, minimum in rules
        )
    return False


def guard_cohort(side_flip: bool, gap_pp: float) -> str:
    gap_blocked = gap_pp > DEFAULT_GAP_PP
    if side_flip and gap_blocked:
        return "side_flip_and_gap"
    if side_flip:
        return "side_flip_only"
    if gap_blocked:
        return "gap_only"
    return "ev_only_control"


def registered_replacement_cohorts(
    surface: str,
    series: str,
    confidence: str,
    value_pct: float,
    gap_pp: float,
    side_flip: bool,
    short_favorite_guard: bool,
) -> list[str]:
    if side_flip or short_favorite_guard:
        return []
    cohorts: list[str] = []
    if (
        10.0 < gap_pp <= 20.0
        and policy_profile_eligible(surface, series, confidence, value_pct, short_favorite_guard, "strict")
    ):
        cohorts.append("strict_gap_10_20_same_side")
    if (
        10.0 < gap_pp <= 15.0
        and policy_profile_eligible(surface, series, confidence, value_pct, short_favorite_guard, "volume_200")
    ):
        cohorts.append("volume200_gap_10_15_same_side")
    return cohorts


def anomaly_rows(
    fair_rows: list[dict[str, Any]],
    pinnacle_rows: list[dict[str, str]],
    player_names: dict[int, str],
    tours: dict[int, dict[str, Any]],
    captured_at: datetime,
    min_ev_pct: float,
    min_gap_pp: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pin_index, ignored_pin = build_pinnacle_index(pinnacle_rows)
    output: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    matched_pairs = 0
    anomaly_pairs = 0
    unmatched_examples: list[str] = []

    for fair in fair_rows:
        p1_id = finite_int(fair.get("player1_id"))
        p2_id = finite_int(fair.get("player2_id"))
        if p1_id is None or p2_id is None:
            reasons["missing_player_id"] += 1
            continue
        p1_name = player_names.get(p1_id, "")
        p2_name = player_names.get(p2_id, "")
        if not p1_name or not p2_name:
            reasons["missing_player_name"] += 1
            continue
        candidates = pin_index.get(pair_key(p1_name, p2_name), [])
        if not candidates:
            reasons["pair_not_in_snapshot"] += 1
            if len(unmatched_examples) < 10:
                unmatched_examples.append(f"{p1_name} vs {p2_name}")
            continue
        pin, match_reason = orient_pinnacle(p1_name, p2_name, candidates)
        if pin is None:
            reasons[match_reason] += 1
            continue
        model_p1 = finite_float(fair.get("p1_win_prob"))
        model_p2 = finite_float(fair.get("p2_win_prob"))
        odds1 = finite_float(pin.get("odds1_oriented"))
        odds2 = finite_float(pin.get("odds2_oriented"))
        if model_p1 is None or not 0 < model_p1 < 1 or odds1 is None or odds2 is None or odds1 <= 1 or odds2 <= 1:
            reasons["invalid_probability_or_odds"] += 1
            continue
        if model_p2 is None or not 0 < model_p2 < 1:
            model_p2 = 1.0 - model_p1
        inv1, inv2 = 1.0 / odds1, 1.0 / odds2
        market_p1 = inv1 / (inv1 + inv2)
        market_p2 = 1.0 - market_p1
        model_side = "P1" if model_p1 >= model_p2 else "P2"
        market_side = "P1" if market_p1 >= market_p2 else "P2"
        favorite_gap = abs(max(model_p1, model_p2) - max(market_p1, market_p2))
        side_flip = (
            model_side != market_side
            and abs(model_p1 - 0.5) >= SIDE_FLIP_BUFFER
            and abs(market_p1 - 0.5) >= SIDE_FLIP_BUFFER
        )
        ev1 = (model_p1 * odds1 - 1.0) * 100.0
        ev2 = (model_p2 * odds2 - 1.0) * 100.0
        selected_side = "P1" if ev1 >= ev2 else "P2"
        selected_ev = ev1 if selected_side == "P1" else ev2
        if selected_ev < min_ev_pct and favorite_gap * 100.0 < min_gap_pp and not side_flip:
            continue

        matched_pairs += 1
        anomaly_pairs += 1
        tour_id = finite_int(fair.get("tour_id"))
        tour = tours.get(tour_id or -1, {})
        tournament = str(tour.get("name") or pin.get("league_name") or "").strip()
        series = series_bucket(tournament, finite_int(tour.get("rank")))
        best_of = 5 if series == "Grand Slam" and str(pin.get("league") or "") == "ATP" else 3
        point_match_p1 = best_of_match_probability(
            finite_float(fair.get("p_a")), finite_float(fair.get("p_b")), best_of
        )
        tags, primary, quality = diagnosis(
            fair, model_p1, market_p1, model_side, market_side, point_match_p1
        )
        match_date = str(pin.get("match_date") or captured_at.date().isoformat())[:10]
        anomaly_id = f"{match_date}|{tour_id or ''}|{p1_id}|{p2_id}"
        selected_player = p1_name if selected_side == "P1" else p2_name
        selected_model_prob = model_p1 if selected_side == "P1" else model_p2
        selected_market_prob = market_p1 if selected_side == "P1" else market_p2
        selected_odds = odds1 if selected_side == "P1" else odds2
        gap_bucket = "25pp+" if favorite_gap >= 0.25 else "15-25pp" if favorite_gap >= 0.15 else "10-15pp" if favorite_gap >= 0.10 else "ev_only"
        ev_bucket = "100%+" if selected_ev >= 100 else "50-100%" if selected_ev >= 50 else "30-50%" if selected_ev >= 30 else "under_30%"
        model_favorite_prob = max(model_p1, model_p2)
        market_favorite_prob = max(market_p1, market_p2)
        short_favorite_guard = (
            model_favorite_prob > SHORT_FAVORITE_PROB_MAX
            or market_favorite_prob > SHORT_FAVORITE_PROB_MAX
        )
        confidence = str(fair.get("confidence") or "").strip().lower()
        surface = str(fair.get("surface") or "").strip()
        replacement_cohorts = registered_replacement_cohorts(
            surface,
            series,
            confidence,
            selected_ev,
            favorite_gap * 100.0,
            side_flip,
            short_favorite_guard,
        )
        policy_profiles = [
            profile
            for profile in ("strict", "volume_200")
            if policy_profile_eligible(surface, series, confidence, selected_ev, short_favorite_guard, profile)
        ]
        common: dict[str, Any] = {
            "anomaly_id": anomaly_id,
            "date": match_date,
            "time_utc": captured_at.strftime("%H:%M:%S"),
            "captured_at": captured_at.isoformat().replace("+00:00", "Z"),
            "tournament": tournament,
            "tour_id": tour_id or "",
            "surface": fair.get("surface") or "",
            "series": series,
            "confidence": fair.get("confidence") or "",
            "player1": p1_name,
            "player2": p2_name,
            "player1_id": p1_id,
            "player2_id": p2_id,
            "selected_player": selected_player,
            "model_side": model_side,
            "market_side": market_side,
            "selected_side": selected_side,
            "model_p1": round(model_p1, 8),
            "model_p2": round(model_p2, 8),
            "market_p1_devig": round(market_p1, 8),
            "market_p2_devig": round(market_p2, 8),
            "selected_model_prob": round(selected_model_prob, 8),
            "selected_market_prob": round(selected_market_prob, 8),
            "model_market_gap_pp": round(favorite_gap * 100.0, 4),
            "selected_probability_gap_pp": round((selected_model_prob - selected_market_prob) * 100.0, 4),
            "side_flip": "1" if side_flip else "0",
            "model_favorite_prob": round(model_favorite_prob, 8),
            "market_favorite_prob": round(market_favorite_prob, 8),
            "short_favorite_guard": "1" if short_favorite_guard else "0",
            "guard_cohort": guard_cohort(side_flip, favorite_gap * 100.0),
            "policy_profiles": "|".join(policy_profiles),
            "replacement_cohorts": "|".join(replacement_cohorts),
            # Keep the forward sample identical to the registered historical
            # cohort. Quality is reported as a separate diagnostic cut instead
            # of becoming an untested post-registration exclusion.
            "replacement_forward_eligible": "1" if replacement_cohorts else "0",
            "replacement_quality_eligible": "1" if replacement_cohorts and quality != "LOW" else "0",
            "replacement_stake_units": 0.5 if replacement_cohorts else "",
            "replacement_status": "provisional_0_5u" if replacement_cohorts else "",
            "replacement_registered_at": REGISTERED_REPLACEMENT_AT if replacement_cohorts else "",
            "gap_bucket": gap_bucket,
            "ev_bucket": ev_bucket,
            "value_pct": round(selected_ev, 4),
            "pin_odds1": odds1,
            "pin_odds2": odds2,
            "fair_odds1": round(1.0 / model_p1, 4),
            "fair_odds2": round(1.0 / model_p2, 4),
            "p1_win_prob_raw": fair.get("p1_win_prob_raw") or "",
            "p_serve_return": fair.get("p_serve_return") or "",
            "p_elo": fair.get("p_elo") or "",
            "p_a": fair.get("p_a") or "",
            "p_b": fair.get("p_b") or "",
            "point_shape_match_p1": round(point_match_p1, 8) if point_match_p1 is not None else "",
            "match_count_12m_p1": fair.get("match_count_12m_p1") or "",
            "match_count_12m_p2": fair.get("match_count_12m_p2") or "",
            "matches_total_p1": fair.get("matches_total_p1") or "",
            "matches_total_p2": fair.get("matches_total_p2") or "",
            "last_match_days_p1": fair.get("last_match_days_p1") or "",
            "last_match_days_p2": fair.get("last_match_days_p2") or "",
            "data_coverage_tag": fair.get("data_coverage_tag") or "",
            "diagnosis_primary": primary,
            "diagnosis_tags": "|".join(tags),
            "diagnostic_quality": quality,
            "research_only": "1",
            "routing_blocked": "1",
            "policy_mode": "diagnostic",
            "stake_units": 1,
            "stake_model": "shadow_flat_1u",
            "settlement_status": "pending",
            "match_date": match_date,
        }
        for field in SETTLEMENT_FIELDS:
            common.setdefault(field, "")

        output.append(
            {
                **common,
                "hypothesis": "extreme_ml_side",
                "bet_type": "match",
                "side": selected_side,
                "selected_odds": selected_odds,
                "spread_line": "",
                "spread_odds": "",
                "model_spread_edge_pct": "",
                "signal_profile": "model_market_gap_ml_audit",
            }
        )

        spread_line = finite_float(fair.get("spread_line"))
        spread_odds1 = finite_float(fair.get("spread_odds1"))
        spread_odds2 = finite_float(fair.get("spread_odds2"))
        if spread_line is None:
            spread_line = finite_float(pin.get("spread_line_oriented"))
        if spread_odds1 is None:
            spread_odds1 = finite_float(pin.get("spread_odds1_oriented"))
        if spread_odds2 is None:
            spread_odds2 = finite_float(pin.get("spread_odds2_oriented"))
        selected_spread_odds = spread_odds1 if selected_side == "P1" else spread_odds2
        if spread_line is not None and selected_spread_odds is not None and selected_spread_odds > 1:
            output.append(
                {
                    **common,
                    "hypothesis": "same_player_spread",
                    "bet_type": "spread",
                    "side": "P1+" if selected_side == "P1" else "P2-",
                    "selected_odds": selected_spread_odds,
                    "spread_line": round(spread_line, 3),
                    "spread_odds": selected_spread_odds,
                    "model_spread_edge_pct": fair.get("handicap_edge_p1" if selected_side == "P1" else "handicap_edge_p2") or "",
                    "signal_profile": "model_market_gap_spread_audit",
                }
            )
        else:
            reasons["anomaly_missing_spread"] += 1

    return output, {
        "fair_rows": len(fair_rows),
        "pinnacle_rows": len(pinnacle_rows),
        "ignored_pinnacle_rows": ignored_pin,
        "matched_anomaly_pairs": matched_pairs,
        "anomaly_pairs": anomaly_pairs,
        "hypothesis_rows": len(output),
        "reason_counts": dict(reasons),
        "unmatched_examples": unmatched_examples,
    }


def archive_key(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("date") or ""),
        str(row.get("player1_id") or normalize_name(row.get("player1"))),
        str(row.get("player2_id") or normalize_name(row.get("player2"))),
        str(row.get("signal_profile") or ""),
    )


def append_first_observation(path: Path, new_rows: list[dict[str, Any]]) -> int:
    existing: list[dict[str, Any]] = list(load_csv(path))
    keys = {archive_key(row) for row in existing}
    additions = [row for row in new_rows if archive_key(row) not in keys]
    if additions:
        write_csv(path, [*existing, *additions])
    elif not path.exists():
        write_csv(path, [])
    return len(additions)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Capture date (YYYY-MM-DD), defaults to UTC today.")
    parser.add_argument("--pinnacle-file", help="Explicit Pinnacle snapshot CSV.")
    parser.add_argument("--live", default=str(DEFAULT_LIVE))
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--status", default=str(DEFAULT_STATUS))
    parser.add_argument("--min-ev-pct", type=float, default=DEFAULT_MIN_EV_PCT)
    parser.add_argument("--min-gap-pp", type=float, default=DEFAULT_GAP_PP)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env()
    capture_day = date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
    pinnacle_file = Path(args.pinnacle_file) if args.pinnacle_file else latest_pinnacle_file(capture_day, DEFAULT_PINNACLE_DIR)
    if pinnacle_file is None or not pinnacle_file.exists():
        print(f"No fresh Pinnacle snapshot found for {capture_day.isoformat()}.")
        return 0
    captured_at = datetime.fromtimestamp(pinnacle_file.stat().st_mtime, tz=timezone.utc)
    fair_rows = fetch_fair_rows()
    pinnacle_rows = load_csv(pinnacle_file)
    rows, status = anomaly_rows(
        fair_rows,
        pinnacle_rows,
        read_name_map(DEFAULT_PLAYERS),
        read_tour_map(DEFAULT_TOURS),
        captured_at,
        args.min_ev_pct,
        args.min_gap_pp,
    )
    status.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "capture_date": capture_day.isoformat(),
            "pinnacle_file": str(pinnacle_file.relative_to(ROOT)),
            "min_ev_pct": args.min_ev_pct,
            "min_gap_pp": args.min_gap_pp,
            "research_only": True,
        }
    )
    if not args.dry_run:
        write_csv(Path(args.live), rows)
        added = append_first_observation(Path(args.archive), rows)
        status["archive_rows_added"] = added
        status_path = Path(args.status)
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(
        f"Extreme-gap audit: anomalies={status['anomaly_pairs']} hypotheses={len(rows)} "
        f"archive_added={status.get('archive_rows_added', 0)} source={pinnacle_file.name}"
    )
    for row in rows[:8]:
        print(
            f"  {row['player1']} vs {row['player2']} | {row['hypothesis']} {row['side']} "
            f"gap={row['model_market_gap_pp']:.1f}pp ML_EV={row['value_pct']:+.1f}% "
            f"cause={row['diagnosis_primary']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
