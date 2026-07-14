#!/usr/bin/env python3
"""Weekly research-lane monitoring report.

This is intentionally boring and strict: it reports what is live, what is
blocked, how much live CLV evidence exists, and whether any pre-agreed pause
rule has fired. It must not fail just because no research picks exist yet.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "football-form"
DEFAULT_JSON = OUT_DIR / "weekly-research-report.json"
DEFAULT_REPORT = OUT_DIR / "weekly-research-report.md"

TEAM_SHOTS_MODEL = "canonical_form_v3_ema20_nb"
CORNERS_MODEL = "canonical_form_v0"
ML_GAP_GUARD_MIN_EDGE_PCT = 10.0
ML_GAP_GUARD_THRESHOLD = 0.10
BACKTEST_YEARS = (2022, 2023, 2024, 2025, 2026)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_env_files() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": f"{display_path(path)} parse failed: {exc}"}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def labelled_value(text: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def labelled_float(text: str, label: str) -> float | None:
    match = re.search(r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", labelled_value(text, label))
    return float(match.group(0)) if match else None


def goalscorer_research_summary() -> dict[str, Any]:
    backtest_dir = ROOT / "data" / "goalscorer" / "backtest"
    parity = load_text(backtest_dir / "parity-report.txt")
    walkforward = load_text(backtest_dir / "walkforward-report.txt")
    clv_rows = load_csv(ROOT / "data" / "goalscorer" / "fair-odds-lab-clv.csv")
    matched = [row for row in clv_rows if str(row.get("close_odds") or "").strip()]
    true_closes = [row for row in clv_rows if row.get("close_status") == "true_close"]
    beta_gate = re.search(
        r"^beta,(\d+),(\d+),([^,]+),([^,]+),([^\n]+)$",
        walkforward,
        flags=re.MULTILINE,
    )
    return {
        "status": "research_only",
        "variant": labelled_value(walkforward, "Model variant") or "v2_minutes_absolute_share_repair",
        "parity_decision": labelled_value(parity, "Decision") or "NOT_RUN",
        "parity_max_delta_pp": (
            labelled_float(parity, "Maximum absolute probability delta") * 100
            if labelled_float(parity, "Maximum absolute probability delta") is not None
            else None
        ),
        "signals": len(clv_rows),
        "matched_closes": len(matched),
        "true_closes": len(true_closes),
        "clv_coverage_pct": (len(matched) / len(clv_rows) * 100) if clv_rows else 0.0,
        "beta_folds": int(beta_gate.group(1)) if beta_gate else 0,
        "beta_fold_wins": int(beta_gate.group(2)) if beta_gate else 0,
        "probability_gate": beta_gate.group(3) if beta_gate else "NOT_RUN",
        "market_roi_gate": beta_gate.group(4) if beta_gate else "UNAVAILABLE",
        "decision": beta_gate.group(5).strip() if beta_gate else "KEEP_RESEARCH",
    }


def pf(value: Any) -> float | None:
    text = str(value or "").strip().replace("%", "")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def finite_float(value: Any) -> float | None:
    parsed = pf(value)
    if parsed is None or not math.isfinite(parsed):
        return None
    return parsed


def number(value: Any, default: float = 0.0) -> float:
    parsed = finite_float(value)
    return parsed if parsed is not None else default


def avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value:+.{digits}f}%"


def league_title(league: str) -> str:
    return {
        "epl": "EPL",
        "serie-a": "Serie A",
        "la-liga": "La Liga",
        "bundesliga": "Bundesliga",
        "ligue-1": "Ligue 1",
    }.get(league, league or "-")


def join_leagues(leagues: list[str]) -> str:
    return ", ".join(league_title(league) for league in leagues) if leagues else "-"


def find_lane(state: dict[str, Any], market: str, model: str) -> dict[str, Any]:
    for lane in state.get("lanes", []) or []:
        if lane.get("market") == market and lane.get("model") == model:
            return lane
    return {}


def clv_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    settled = [row for row in rows if (row.get("result") or "").strip()]
    avg_pub_close = avg([x for x in (pf(row.get("published_to_close_clv")) for row in settled) if x is not None])
    avg_model_close = avg([x for x in (pf(row.get("model_to_close_clv")) for row in settled) if x is not None])
    pnl = sum(x for x in (pf(row.get("pnl_units")) for row in settled) if x is not None)
    positive_clv = [
        row
        for row in settled
        if (pf(row.get("published_to_close_clv")) is not None and (pf(row.get("published_to_close_clv")) or 0) > 0)
    ]
    return {
        "published_picks": len(rows),
        "settled": len(settled),
        "pnl_units": round(pnl, 4),
        "avg_published_to_close_clv": avg_pub_close,
        "avg_model_to_close_clv": avg_model_close,
        "positive_clv_share": len(positive_clv) / len(settled) if settled else None,
        "sample_state": "actionable" if len(settled) >= 50 else "too_early",
        "pause_rule_fired": bool(len(settled) >= 50 and avg_pub_close is not None and avg_pub_close < 0),
    }


def empty_bet_summary() -> dict[str, Any]:
    return {
        "n": 0,
        "wins": 0,
        "losses": 0,
        "pnl_units": 0.0,
        "roi_pct": None,
        "avg_edge_pct": None,
        "avg_gap_pp": None,
    }


def bet_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return empty_bet_summary()
    wins = sum(1 for row in rows if row.get("win"))
    pnl = sum(float(row.get("pnl_units") or 0.0) for row in rows)
    return {
        "n": len(rows),
        "wins": wins,
        "losses": len(rows) - wins,
        "pnl_units": round(pnl, 4),
        "roi_pct": round((pnl / len(rows)) * 100, 2),
        "avg_edge_pct": round(avg([float(row["edge_pct"]) for row in rows]) or 0.0, 2),
        "avg_gap_pp": round((avg([float(row["model_market_gap"]) for row in rows]) or 0.0) * 100, 2),
    }


def format_bet_summary(summary: dict[str, Any]) -> str:
    if not summary.get("n"):
        return "n=0"
    return (
        f"n={summary['n']} "
        f"{summary['wins']}W/{summary['losses']}L "
        f"pnl={summary['pnl_units']:+.2f}u "
        f"ROI={pct(summary['roi_pct'])} "
        f"avg edge={summary['avg_edge_pct']:.1f}% "
        f"avg gap={summary['avg_gap_pp']:.1f}pp"
    )


def load_ml_gap_guard_picks(edge_min_pct: float = ML_GAP_GUARD_MIN_EDGE_PCT) -> list[dict[str, Any]]:
    picks: list[dict[str, Any]] = []
    for year in BACKTEST_YEARS:
        path = ROOT / "data" / "backtest" / f"backtest-results-{year}.csv"
        if not path.exists():
            continue
        for row in load_csv(path):
            p1_prob = finite_float(row.get("our_prob"))
            pin_odds1 = finite_float(row.get("pinnacle_odds"))
            pin_odds2 = finite_float(row.get("pinnacle_odds_loser"))
            if (
                p1_prob is None
                or pin_odds1 is None
                or pin_odds2 is None
                or not 0 < p1_prob < 1
                or pin_odds1 <= 1
                or pin_odds2 <= 1
            ):
                continue
            p2_prob = 1.0 - p1_prob
            pin_p1 = (1.0 / pin_odds1) / ((1.0 / pin_odds1) + (1.0 / pin_odds2))
            model_fav_side = "P1" if p1_prob >= p2_prob else "P2"
            market_fav_side = "P1" if pin_p1 >= 0.5 else "P2"
            model_market_gap = abs(max(p1_prob, p2_prob) - max(pin_p1, 1.0 - pin_p1))
            actual_winner = (row.get("actual_winner") or "").strip()
            sides = [
                ("P1", (row.get("player1") or "").strip(), p1_prob, pin_odds1),
                ("P2", (row.get("player2") or "").strip(), p2_prob, pin_odds2),
            ]
            for side, player, probability, odds in sides:
                if not player:
                    continue
                edge_pct = (odds * probability - 1.0) * 100
                if edge_pct < edge_min_pct:
                    continue
                win = player == actual_winner
                picks.append(
                    {
                        "year": year,
                        "date": row.get("date", ""),
                        "tournament": row.get("tournament", ""),
                        "surface": row.get("surface", ""),
                        "series": row.get("series", ""),
                        "confidence": (row.get("confidence") or "").strip().lower(),
                        "player1": row.get("player1", ""),
                        "player2": row.get("player2", ""),
                        "side": side,
                        "player": player,
                        "edge_pct": edge_pct,
                        "model_market_gap": model_market_gap,
                        "guarded": model_market_gap > ML_GAP_GUARD_THRESHOLD,
                        "market_side_type": "fav" if side == market_fav_side else "dog",
                        "model_side_type": "fav" if side == model_fav_side else "dog",
                        "win": win,
                        "pnl_units": odds - 1.0 if win else -1.0,
                    }
                )
    return picks


def ml_gap_guard_summary() -> dict[str, Any]:
    picks = load_ml_gap_guard_picks()
    guarded = [row for row in picks if row["guarded"]]
    clay_high = [
        row
        for row in guarded
        if row["surface"] == "Clay" and row["confidence"] == "high"
    ]
    clay_high_market_dog = [row for row in clay_high if row["market_side_type"] == "dog"]
    etcheverry_fils_type = [
        row
        for row in clay_high_market_dog
        if row["series"] == "Masters 1000"
    ]
    closest_band = [
        row
        for row in etcheverry_fils_type
        if 0.12 < row["model_market_gap"] <= 0.15 and 30 <= row["edge_pct"] < 50
    ]
    year_breakdown = {
        str(year): bet_summary([row for row in etcheverry_fils_type if row["year"] == year])
        for year in BACKTEST_YEARS
    }
    recent = [
        row
        for row in etcheverry_fils_type
        if row["year"] in {2024, 2025, 2026}
    ]
    return {
        "label": "Tennis ML gap-guard quiet audit",
        "edge_min_pct": ML_GAP_GUARD_MIN_EDGE_PCT,
        "gap_threshold_pp": ML_GAP_GUARD_THRESHOLD * 100,
        "all_guarded": bet_summary(guarded),
        "clay_high_guarded": bet_summary(clay_high),
        "clay_high_market_dog": bet_summary(clay_high_market_dog),
        "etch_type": bet_summary(etcheverry_fils_type),
        "closest_band": bet_summary(closest_band),
        "etch_type_years": year_breakdown,
        "etch_type_recent": bet_summary(recent),
        "read": (
            "keep_guard_active_recent_sample_weak"
            if (bet_summary(recent).get("roi_pct") is None or float(bet_summary(recent).get("roi_pct") or 0) < 0)
            else "interesting_but_keep_shadow_until_live_sample"
        ),
    }


def tennis_props_v3_snapshot() -> dict[str, Any]:
    raw = os.environ.get("TENNIS_PROPS_V3_WEEKLY_JSON", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"_error": f"repository variable JSON is invalid: {exc}"}
    return payload if isinstance(payload, dict) else {"_error": "repository variable is not a JSON object"}


def weighted_last90_delta(promotion: dict[str, Any]) -> dict[str, Any]:
    total_n = 0
    current_sum = 0.0
    canonical_sum = 0.0
    league_rows: list[dict[str, Any]] = []
    for row in promotion.get("league_results", []) or []:
        last90 = row.get("last_90_common") or {}
        n = int(last90.get("n") or 0)
        current = pf(last90.get("current_mae"))
        canonical = pf(last90.get("canonical_mae"))
        improvement = pf(last90.get("improvement_pct"))
        if n and current is not None and canonical is not None:
            total_n += n
            current_sum += current * n
            canonical_sum += canonical * n
        league_rows.append(
            {
                "league": row.get("league", ""),
                "passes": bool(row.get("passes")),
                "n": n,
                "current_mae": current,
                "canonical_mae": canonical,
                "improvement_pct": improvement,
            }
        )
    current_mae = current_sum / total_n if total_n else None
    canonical_mae = canonical_sum / total_n if total_n else None
    improvement = (current_mae - canonical_mae) / current_mae if current_mae else None
    return {
        "n": total_n,
        "current_mae": current_mae,
        "canonical_mae": canonical_mae,
        "improvement_pct": improvement,
        "leagues": league_rows,
    }


def build_payload() -> dict[str, Any]:
    state = load_json(OUT_DIR / "research-lane-state.json")
    team_allowed = load_json(OUT_DIR / "team-shots-v3-ema20-allowed-leagues.json")
    team_promo = load_json(OUT_DIR / "team-shots-v3-ema20-promotion-check.json")
    corners_allowed = load_json(OUT_DIR / "corners-v0-allowed-leagues.json")
    corners_diag = load_json(OUT_DIR / "corners-total-diagnostic.json")
    football_counts_vnext = load_json(OUT_DIR / "football-counts-vnext-gate.json")
    api_football_health = load_json(OUT_DIR / "api-football-counts-health.json")
    api_football_agreement = load_json(OUT_DIR / "api-football-source-agreement.json")
    team_fouls_m1 = load_json(OUT_DIR / "fouls-empirical-baseline.json")
    team_fouls_f1 = load_json(OUT_DIR / "team-fouls-v1-fold-report.json")
    team_fouls_m2 = load_json(OUT_DIR / "team-fouls-definition-agreement.json")

    team_clv_rows = load_csv(OUT_DIR / "team-shots-v3-ema20-clv-monitor.csv")
    corners_clv_rows = load_csv(OUT_DIR / "corners-v0-clv-monitor.csv")
    tennis_gap_guard = ml_gap_guard_summary()
    tennis_props_v3 = tennis_props_v3_snapshot()
    goalscorer_research = goalscorer_research_summary()

    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "team_shots_v3_ema20": {
            "label": "Team Shots V3 EMA20 Research",
            "model": TEAM_SHOTS_MODEL,
            "lane": find_lane(state, "team_shots", TEAM_SHOTS_MODEL),
            "allowed_leagues": team_allowed.get("allowed_leagues", []),
            "blocked_leagues": team_allowed.get("blocked_leagues", []),
            "canonical_only_allowed": bool(team_allowed.get("canonical_only_allowed")),
            "segment_gate": weighted_last90_delta(team_promo),
            "clv": clv_summary(team_clv_rows),
        },
        "corners_v0": {
            "label": "Corners V0 Research Partial",
            "model": CORNERS_MODEL,
            "lane": find_lane(state, "corners_total", CORNERS_MODEL),
            "allowed_leagues": corners_allowed.get("allowed_leagues", []),
            "blocked_leagues": corners_allowed.get("blocked_leagues", []),
            "canonical_only_allowed": bool(corners_allowed.get("canonical_only_allowed")),
            "blocked_diagnostic": {
                league: corners_diag.get("by_league", {}).get(league, {})
                for league in corners_allowed.get("blocked_leagues", [])
            },
            "clv": clv_summary(corners_clv_rows),
        },
        "football_counts_vnext": football_counts_vnext,
        "api_football_counts": {
            "health": api_football_health,
            "agreement": api_football_agreement,
        },
        "team_fouls_v1": {
            "m1": team_fouls_m1,
            "f1": team_fouls_f1,
            "m2": team_fouls_m2,
        },
        "tennis_ml_gap_guard": tennis_gap_guard,
        "tennis_props_v3": tennis_props_v3,
        "goalscorer_v2": goalscorer_research,
    }
    payload["status"] = {
        "pause_required": bool(
            payload["team_shots_v3_ema20"]["clv"]["pause_rule_fired"]
            or payload["corners_v0"]["clv"]["pause_rule_fired"]
        ),
        "read": "observe_live_sample",
    }
    return payload


def render_report(payload: dict[str, Any]) -> str:
    team = payload["team_shots_v3_ema20"]
    corners = payload["corners_v0"]
    vnext = payload.get("football_counts_vnext") or {}
    api_counts = payload.get("api_football_counts") or {}
    api_health = api_counts.get("health") or {}
    api_agreement = api_counts.get("agreement") or {}
    team_fouls = payload.get("team_fouls_v1") or {}
    team_fouls_f1 = team_fouls.get("f1") or {}
    team_fouls_decision = team_fouls_f1.get("decision") or {}
    team_fouls_m2 = team_fouls.get("m2") or {}
    tennis = payload["tennis_ml_gap_guard"]
    tennis_props_v3 = payload.get("tennis_props_v3") or {}
    goalscorer = payload["goalscorer_v2"]
    team_gate = team["segment_gate"]
    team_clv = team["clv"]
    corners_clv = corners["clv"]

    lines = [
        "# Weekly Research Lane Report",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Overall read: {'PAUSE REQUIRED' if payload['status']['pause_required'] else 'observe live sample'}",
        "",
        "## Football Counts vNext",
        "",
        f"- Team Shots v4: count {((vnext.get('team_shots_v4') or {}).get('count_gate') or 'NOT_RUN')}; prospective {((vnext.get('team_shots_v4') or {}).get('prospective_status') or 'BLOCKED')}; market gate remains blocked.",
        f"- Corners v3: count {((vnext.get('corners_v3') or {}).get('count_gate') or 'NOT_RUN')}; prospective {((vnext.get('corners_v3') or {}).get('prospective_status') or 'BLOCKED')}; market gate remains blocked.",
        "- Neither experiment changes live routing or stakes.",
        f"- API-Football count archive: {api_health.get('archive_rows', 0)} fixtures; latest {api_health.get('latest_fixture_date') or '-'}; last run {api_health.get('requests_used', 0)}/{api_health.get('max_requests', 0)} requests.",
        f"- Cross-provider agreement: {api_agreement.get('matched_fixtures', 0)}/{api_agreement.get('api_rows', 0)} API fixtures matched; status {api_agreement.get('status', 'NOT_RUN')}.",
        f"- Team Fouls v1: count {team_fouls_decision.get('status', 'NOT_RUN')}; M2 {team_fouls_m2.get('status', 'NOT_RUN')}; market prices BLOCKED; signals disabled.",
        "- New provider fields remain diagnostic-only until source definitions and coverage are accepted.",
        "",
        "## Team Shots V3 EMA20 Research",
        "",
        f"- Model: `{team['model']}`",
        f"- Allowed leagues: {join_leagues(team['allowed_leagues'])}",
        f"- Blocked leagues: {join_leagues(team['blocked_leagues'])}",
        f"- Canonical-only fixtures: {'allowed' if team['canonical_only_allowed'] else 'blocked'}",
        f"- Last-90 segment gate: {team_gate['n']} rows, current MAE {team_gate['current_mae']:.4f}, V3 MAE {team_gate['canonical_mae']:.4f}, improvement {pct((team_gate['improvement_pct'] or 0) * 100)}" if team_gate["current_mae"] is not None and team_gate["canonical_mae"] is not None else "- Last-90 segment gate: unavailable",
        f"- Live CLV sample: {team_clv['published_picks']} published, {team_clv['settled']} settled",
        f"- Avg published-to-close CLV: {pct((team_clv['avg_published_to_close_clv'] or 0) * 100) if team_clv['avg_published_to_close_clv'] is not None else '-'}",
        f"- P/L sample: {team_clv['pnl_units']:+.2f}u",
        f"- Action: {'pause and investigate' if team_clv['pause_rule_fired'] else 'watch passively; not enough live sample until 50 settled picks' if team_clv['sample_state'] == 'too_early' else 'continue'}",
        "",
        "## Corners V0 Research Partial",
        "",
        f"- Model: `{corners['model']}`",
        f"- Allowed leagues: {join_leagues(corners['allowed_leagues'])}",
        f"- Blocked leagues: {join_leagues(corners['blocked_leagues'])}",
        f"- Canonical-only fixtures: {'allowed' if corners['canonical_only_allowed'] else 'blocked'}",
        f"- Live CLV sample: {corners_clv['published_picks']} published, {corners_clv['settled']} settled",
        f"- Avg published-to-close CLV: {pct((corners_clv['avg_published_to_close_clv'] or 0) * 100) if corners_clv['avg_published_to_close_clv'] is not None else '-'}",
        f"- P/L sample: {corners_clv['pnl_units']:+.2f}u",
        f"- Action: {'pause and investigate' if corners_clv['pause_rule_fired'] else 'keep partial; Bundesliga/La Liga remain blocked'}",
        "",
        "## Blocked Corners Diagnostic",
        "",
    ]
    blocked_diag = corners.get("blocked_diagnostic", {})
    if blocked_diag:
        for league, row in blocked_diag.items():
            delta = pf(row.get("mae_delta"))
            lines.append(
                f"- {league_title(league)}: current MAE {row.get('current_mae', '-')}, V0 MAE {row.get('canonical_mae', '-')}, delta {delta:+.4f}" if delta is not None else f"- {league_title(league)}: diagnostic unavailable"
            )
    else:
        lines.append("- No blocked league diagnostic available.")

    lines.extend(
        [
            "",
            "## Goalscorer V2 Research Gate",
            "",
            "- Public Fair Odds Lab remains on the incumbent model.",
            f"- Live/backtest parity: {goalscorer['parity_decision']} | max drift {pct(goalscorer['parity_max_delta_pp'], 3)}.",
            f"- Beta calibration: {goalscorer['beta_fold_wins']}/{goalscorer['beta_folds']} fold wins | probability gate {goalscorer['probability_gate']} | market gate {goalscorer['market_roi_gate']}.",
            f"- Real-price CLV coverage: {goalscorer['matched_closes']}/{goalscorer['signals']} ({goalscorer['clv_coverage_pct']:.1f}%) | true closes {goalscorer['true_closes']}.",
            f"- Decision: {goalscorer['decision'].replace('_', ' ').lower()} until the fifth fold and real-price evidence exist.",
            "",
            "## Tennis ML Gap-Guard Quiet Audit",
            "",
            "- This is not a live picks lane. Official ML value remains blocked when the model/market favourite gap is too wide.",
            f"- Guard trigger: model/market favourite gap > {tennis['gap_threshold_pp']:.1f}pp and model edge >= {tennis['edge_min_pct']:.1f}%.",
            f"- All guarded ML candidates: {format_bet_summary(tennis['all_guarded'])}",
            f"- Clay high-confidence guarded: {format_bet_summary(tennis['clay_high_guarded'])}",
            f"- Clay high-confidence market dogs: {format_bet_summary(tennis['clay_high_market_dog'])}",
            f"- Etcheverry/Fils-type candidates: {format_bet_summary(tennis['etch_type'])}",
            f"- Closest band to Etcheverry/Fils: {format_bet_summary(tennis['closest_band'])}",
            f"- Recent Etcheverry/Fils-type sample (2024-2026): {format_bet_summary(tennis['etch_type_recent'])}",
            f"- Action: {'keep ML guard active; collect evidence quietly' if tennis['read'] == 'keep_guard_active_recent_sample_weak' else 'interesting, but keep shadow-only until live sample exists'}",
            "",
            "### Etcheverry/Fils-Type Year Split",
            "",
        ]
    )
    for year, summary in tennis.get("etch_type_years", {}).items():
        lines.append(f"- {year}: {format_bet_summary(summary)}")

    if tennis_props_v3 and not tennis_props_v3.get("_error"):
        atp_v3 = tennis_props_v3.get("atp") or {}
        evidence_v3 = tennis_props_v3.get("evidence") or {}
        lines.extend(
            [
                "",
                "## Tennis Props v3 Prospective Evidence",
                "",
                f"- Snapshot: {tennis_props_v3.get('generated_at', '-')}",
                f"- ATP aces gate: {atp_v3.get('status', 'UNKNOWN')} on {', '.join(atp_v3.get('surfaces') or []) or 'no verified surface'}",
                f"- Holdout MAE improvement: {number(atp_v3.get('mae_improvement_pct')):+.2f}%",
                f"- Prospective sample: {int(number(evidence_v3.get('settled')))} settled, {int(number(evidence_v3.get('pending')))} pending, {int(number(evidence_v3.get('distinct_events')))} events",
                f"- P/L: {number(evidence_v3.get('pnl_units')):+.2f}u; ROI {number(evidence_v3.get('roi_pct')):+.2f}%",
                f"- CLV: {number(evidence_v3.get('mean_clv_pct')):+.2f}% across {int(number(evidence_v3.get('clv_coverage')))} rows",
                f"- Sellability: {evidence_v3.get('status', 'BLOCKED')} - {evidence_v3.get('reason', 'no evidence')}",
                "- Scope remains ATP aces on verified Hard/Clay only; shadow-only until every real-price gate passes.",
            ]
        )
    elif tennis_props_v3.get("_error"):
        lines.extend(
            [
                "",
                "## Tennis Props v3 Prospective Evidence",
                "",
                f"- Snapshot unavailable: {tennis_props_v3['_error']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Plain-English Read",
            "",
            "- Team-shots V3 is not proven profitable live yet; it is the first broad research candidate that passed the backtest segment gates.",
            "- Corners V0 is narrower and deliberately blocked in two leagues. That is a discipline feature, not a failure.",
            "- Goalscorer V2 fixes live/backtest mechanics, but it is not a betting edge until captured prices validate it.",
            "- Tennis ML gap-guard remains a safety brake. The backtest is not stable enough to unblock those big market-disagreement ML dogs.",
            "- Tennis props v3 remains prospective shadow evidence; historical accuracy alone does not authorise tips.",
            "- The next real evidence is CLV and settled live sample. Until 50 settled picks, do not overreact to wins/losses.",
            "",
        ]
    )
    return "\n".join(lines)


def telegram_text(payload: dict[str, Any]) -> str:
    team = payload["team_shots_v3_ema20"]
    corners = payload["corners_v0"]
    vnext = payload.get("football_counts_vnext") or {}
    api_counts = payload.get("api_football_counts") or {}
    api_health = api_counts.get("health") or {}
    api_agreement = api_counts.get("agreement") or {}
    team_fouls = payload.get("team_fouls_v1") or {}
    team_fouls_decision = ((team_fouls.get("f1") or {}).get("decision") or {})
    team_fouls_m2 = team_fouls.get("m2") or {}
    tennis = payload["tennis_ml_gap_guard"]
    tennis_props_v3 = payload.get("tennis_props_v3") or {}
    goalscorer = payload["goalscorer_v2"]
    team_clv = team["clv"]
    corners_clv = corners["clv"]
    lines = [
        "Il Margine weekly research report",
        f"Generated: {payload['generated_at']}",
        "",
        f"Team Shots V3 EMA20: {len(team['allowed_leagues'])}/5 leagues, {team_clv['published_picks']} picks, {team_clv['settled']} settled, avg CLV {pct((team_clv['avg_published_to_close_clv'] or 0) * 100) if team_clv['avg_published_to_close_clv'] is not None else '-'}",
        f"Corners V0: {len(corners['allowed_leagues'])}/5 leagues, blocked {join_leagues(corners['blocked_leagues'])}, {corners_clv['published_picks']} picks, {corners_clv['settled']} settled, avg CLV {pct((corners_clv['avg_published_to_close_clv'] or 0) * 100) if corners_clv['avg_published_to_close_clv'] is not None else '-'}",
        f"Football counts vNext: Team Shots {((vnext.get('team_shots_v4') or {}).get('count_gate') or 'NOT_RUN')}, Corners {((vnext.get('corners_v3') or {}).get('count_gate') or 'NOT_RUN')}; both market-gated shadow only",
        f"Count-source health: API-Football {api_health.get('archive_rows', 0)} archived, latest {api_health.get('latest_fixture_date') or '-'}, agreement {api_agreement.get('matched_fixtures', 0)}/{api_agreement.get('api_rows', 0)}",
        f"Team Fouls v1: {team_fouls_decision.get('status', 'NOT_RUN')}; sources {team_fouls_m2.get('status', 'NOT_RUN')}; no signals",
        f"Goalscorer V2: parity {goalscorer['parity_decision']}, Beta {goalscorer['beta_fold_wins']}/{goalscorer['beta_folds']} fold wins, CLV coverage {goalscorer['matched_closes']}/{goalscorer['signals']}; research only",
        f"Tennis ML gap guard: Etch/Fils-type {format_bet_summary(tennis['etch_type'])}; recent 2024-26 {format_bet_summary(tennis['etch_type_recent'])}",
    ]
    if tennis_props_v3 and not tennis_props_v3.get("_error"):
        atp_v3 = tennis_props_v3.get("atp") or {}
        evidence_v3 = tennis_props_v3.get("evidence") or {}
        lines.append(
            "Tennis props v3: "
            f"ATP {atp_v3.get('status', 'UNKNOWN')} {','.join(atp_v3.get('surfaces') or []) or '-'}, "
            f"MAE {number(atp_v3.get('mae_improvement_pct')):+.2f}%, "
            f"{int(number(evidence_v3.get('settled')))} settled, "
            f"ROI {number(evidence_v3.get('roi_pct')):+.2f}%, "
            f"CLV {number(evidence_v3.get('mean_clv_pct')):+.2f}%, "
            f"{evidence_v3.get('status', 'BLOCKED')}"
        )
    elif tennis_props_v3.get("_error"):
        lines.append(f"Tennis props v3: snapshot unavailable ({tennis_props_v3['_error']})")
    lines.extend(
        [
            "",
            "Read: observe live samples. Keep tennis ML gap guard active and aces v3 shadow-only.",
        ]
    )
    return "\n".join(lines)


def post_telegram(message: str) -> bool:
    token = os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("WEEKLY_REPORT_TELEGRAM skipped missing creds")
        return False
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
        print("WEEKLY_REPORT_TELEGRAM sent")
        return True
    except Exception as exc:
        print(f"Warning: telegram post failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and optionally send the weekly research-lane report.")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    load_env_files()
    payload = build_payload()
    report = render_report(payload)

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")

    print(report)
    print(f"Wrote {display_path(args.json)}")
    print(f"Wrote {display_path(args.report)}")

    if not args.no_telegram:
        post_telegram(telegram_text(payload))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
