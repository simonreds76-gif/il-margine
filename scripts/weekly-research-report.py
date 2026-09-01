#!/usr/bin/env python3
"""Weekly research-lane monitoring report.

This is intentionally boring and strict: it reports what is live, what is
blocked, how much live CLV evidence exists, and whether any pre-agreed pause
rule has fired. It must not fail just because no research picks exist yet.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "football-form"
DEFAULT_JSON = OUT_DIR / "weekly-research-report.json"
DEFAULT_REPORT = OUT_DIR / "weekly-research-report.md"
TENNIS_PROPS_OBSERVATIONS = ROOT / "data" / "tennis-props" / "shadow" / "market-observations.csv"
TENNIS_PROPS_SHADOW_SIGNALS = ROOT / "data" / "tennis-props" / "shadow" / "aces-dfs-shadow-signals.csv"
TENNIS_PROPS_PIPELINE_HEALTH = ROOT / "data" / "tennis-props" / "pipeline-health.json"
TENNIS_PROPS_DECISION_JSON = ROOT / "data" / "tennis-props" / "shadow" / "aces-dfs-weekly-decision.json"
TENNIS_PROPS_DECISION_REPORT = ROOT / "data" / "tennis-props" / "shadow" / "aces-dfs-weekly-decision.txt"
TENNIS_PROPS_V3_LOCAL_JSON = ROOT / "data" / "tennis-props" / "backtest" / "aces-v3-weekly-report.json"
TENNIS_PROPS_V4_JSON = ROOT / "data" / "tennis-props" / "backtest" / "aces-over-v4-weekly-report.json"
TENNIS_BREAKS_V1_GATE = ROOT / "data" / "tennis-props" / "backtest" / "breaks-stage0-gate.json"
TENNIS_VENUE_ACE_FACTORS = ROOT / "data" / "tennis-props" / "venue-ace-factors.csv"
TENNIS_VENUE_ACE_V1_OBSERVATIONS = ROOT / "data" / "tennis-props" / "shadow" / "venue-ace-factor-v1-observations.csv"
TENNIS_VENUE_ACE_V1_GATE = ROOT / "data" / "tennis-props" / "backtest" / "venue-ace-factor-v1-gate.json"
TENNIS_MOST_ACES_FORECAST_JSON = ROOT / "data" / "tennis-props" / "shadow" / "most-aces-1x2-forecast-report.json"
TENNIS_MOST_ACES_OBSERVATIONS = ROOT / "data" / "tennis-props" / "shadow" / "most-aces-1x2-observations.csv"
TENNIS_MOST_ACES_A0_MODEL = "v3_aces_gaussian_copula_nb2"
TENNIS_MOST_ACES_DIRECT_MODEL = "most_aces_direct_1x2_v1"
TELEGRAM_RELAY_REPOSITORY = "simonreds76-gif/il-margine"
TELEGRAM_RELAY_WORKFLOW = "tennis-daily-signal-digest.yml"
ASSIST_GATES = ROOT / "data" / "assist-value" / "research" / "assist-value-gates.json"
ASSIST_PROSPECTIVE = ROOT / "data" / "assist-value" / "research" / "assist-value-v1-prospective.csv"
AUTOMATION_BUDGET = ROOT / "data" / "ops" / "automation-budget-report.json"
GOALKEEPER_SAVES_EVIDENCE = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-evidence.json"
GOALKEEPER_SAVES_MARKET_PROBE = ROOT / "data" / "goalkeeper-saves" / "gk-saves-market-probe.json"
GOALKEEPER_SAVES_SHADOW_REPORT = ROOT / "data" / "goalkeeper-saves" / "gk-saves-v1-shadow-report.json"
GOALKEEPER_SAVES_CAPTURE_STATUS = ROOT / "data" / "goalkeeper-saves" / "gk-saves-capture-status.json"
CORNERS_V4_G0_DIAGNOSTIC = ROOT / "data" / "corners-ou" / "corners-v4-g0-diagnostic.json"
TENNIS_GAP_REPORT = ROOT / "data" / "backtest" / "tennis-model-market-gap-report.json"
TENNIS_EVIDENCE_SNAPSHOT_LOCAL = ROOT / "data" / "tennis-props" / "tennis-evidence-snapshot.json"
TENNIS_EVIDENCE_SNAPSHOT_KEY = "tennis_evidence_v1"
TENNIS_EVIDENCE_SNAPSHOT_TABLE = "goalscorer_live_snapshot"
TENNIS_LANE_FILES = {
    "strict": ROOT / "data" / "backtest" / "strict-policy-performance-weekly.csv",
    "volume_200": ROOT / "data" / "backtest" / "strict-policy-performance-volume200-weekly.csv",
    "spread_v1": ROOT / "data" / "backtest" / "strict-policy-performance-spreadv1-weekly.csv",
    "grass_bo3": ROOT / "data" / "backtest" / "strict-policy-performance-grass_bo3-weekly.csv",
    "clay_bo3": ROOT / "data" / "backtest" / "strict-policy-performance-clay_bo3-weekly.csv",
    "cpi_speed": ROOT / "data" / "backtest" / "strict-policy-performance-cpi_speed-weekly.csv",
    "challenger": ROOT / "data" / "backtest" / "strict-policy-performance-challenger-ml-v2-weekly.csv",
}
TENNIS_CLV_FILES = {
    "strict": ROOT / "data" / "backtest" / "strict-clv-audit-2026.csv",
    "volume_200": ROOT / "data" / "backtest" / "strict-clv-audit-volume200-2026.csv",
    "spread_v1": ROOT / "data" / "backtest" / "strict-clv-audit-spreadv1-2026.csv",
    "challenger": ROOT / "data" / "backtest" / "strict-clv-audit-challenger-ml-v2-2026.csv",
}

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


def corners_v4_g0_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload or payload.get("_error"):
        return {
            "status": "NOT_RUN",
            "decision": "NOT_RUN",
            "enriched_samples": 0,
            "total_samples": 0,
            "mae_delta": None,
            "market_rows": 0,
            "brier_delta": None,
            "passed_lines": 0,
            "available_lines": 0,
            "failed_lines": [],
        }

    folds = payload.get("folds") or []
    latest_season = max((str(row.get("season") or "") for row in folds), default="")
    latest_rows = [row for row in folds if str(row.get("season") or "") == latest_season]
    control = next((row for row in latest_rows if row.get("variant") == "v3_control"), {})
    candidate = next((row for row in latest_rows if row.get("variant") == "v4_lean_no_wide_block"), {})
    control_mae = control.get("mae")
    candidate_mae = candidate.get("mae")
    mae_delta = (
        float(candidate_mae) - float(control_mae)
        if control_mae is not None and candidate_mae is not None
        else None
    )

    variants = ((payload.get("market_g0") or {}).get("variants") or {})
    market = variants.get("v4_lean_no_wide_block") or {}
    per_line = market.get("per_line") or {}
    available = {line: stats for line, stats in per_line.items() if stats.get("status") != "MISSING"}
    failed = sorted(
        (line for line, stats in per_line.items() if stats.get("gate") != "PASS"),
        key=float,
    )
    return {
        "status": payload.get("status", "RESEARCH_ONLY"),
        "decision": market.get("g0_status", "NOT_RUN"),
        "latest_season": latest_season or None,
        "enriched_samples": int((payload.get("samples") or {}).get("enriched") or 0),
        "total_samples": int((payload.get("samples") or {}).get("v3") or 0),
        "mae_delta": mae_delta,
        "market_rows": int(market.get("market_rows") or 0),
        "brier_delta": market.get("brier_delta"),
        "passed_lines": sum(1 for stats in available.values() if stats.get("gate") == "PASS"),
        "available_lines": len(available),
        "failed_lines": failed,
    }


def tennis_breaks_gate_line(gate: dict[str, Any]) -> str:
    if not gate or gate.get("_error"):
        return "Service Breaks v1: SOURCE_MISSING"
    scopes = gate.get("scopes") or {}
    player = scopes.get("player_breaks") or {}
    match = scopes.get("match_breaks") or {}
    status = "OUTCOME_PASS" if gate.get("status") == "PASS" else "OUTCOME_FAIL"
    return (
        f"Service Breaks v1 [INTERNAL]: {status} | "
        f"player ATP/WTA {'PASS' if player.get('passed') else 'FAIL'} | "
        f"match ATP/WTA {'PASS' if match.get('passed') else 'FAIL'} | "
        "real Bet365 price feed MISSING | 0 prospective | NOT SELLABLE"
    )


def load_tennis_evidence_snapshot() -> dict[str, Any]:
    local = load_json(TENNIS_EVIDENCE_SNAPSHOT_LOCAL)
    if isinstance(local.get("sections"), dict):
        return {**local, "_source": "local_snapshot"}

    if os.environ.get("TENNIS_EVIDENCE_SNAPSHOT_DISABLE", "").strip().lower() in {"1", "true", "yes"}:
        return {"_status": "DISABLED", "_source": "none"}

    base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
    if not base or not key:
        return {"_status": "SOURCE_MISSING", "_source": "none"}

    query = urllib.parse.urlencode(
        {
            "snapshot_key": f"eq.{TENNIS_EVIDENCE_SNAPSHOT_KEY}",
            "select": "updated_at,payload",
            "limit": "1",
        }
    )
    request = urllib.request.Request(
        f"{base}/rest/v1/{TENNIS_EVIDENCE_SNAPSHOT_TABLE}?{query}",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"_status": "FETCH_FAILED", "_source": "supabase", "_error": str(exc)}
    if not isinstance(rows, list) or not rows:
        return {"_status": "SOURCE_MISSING", "_source": "supabase"}
    payload = rows[0].get("payload") if isinstance(rows[0], dict) else None
    if not isinstance(payload, dict) or not isinstance(payload.get("sections"), dict):
        return {"_status": "INVALID", "_source": "supabase"}
    return {**payload, "_source": "supabase"}


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


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "settled"}


def most_aces_review_stage(paired_events: int) -> tuple[str, int | None]:
    if paired_events < 50:
        return "BUILDING", 50
    if paired_events < 100:
        return "EARLY_QA", 100
    if paired_events < 200:
        return "DIRECTIONAL_ONLY", 200
    return "REGISTERED_REVIEW", None


def most_aces_price_summary(
    rows: list[dict[str, str]] | None = None,
) -> dict[str, dict[str, Any]]:
    source = load_csv(TENNIS_MOST_ACES_OBSERVATIONS) if rows is None else rows
    summaries: dict[str, dict[str, Any]] = {}
    for model in sorted({row.get("model", "") for row in source if row.get("model")}):
        model_rows = [row for row in source if row.get("model") == model]
        settled = [
            row for row in model_rows if row.get("settlement_status") == "settled"
        ]
        eligible = [row for row in settled if row.get("bet_eligible") == "yes"]
        pnl = sum(number(row.get("pnl")) for row in eligible)
        clv = [
            number(row.get("clv_pct"))
            for row in model_rows
            if str(row.get("clv_pct") or "").strip()
        ]
        summaries[model] = {
            "registered": len(model_rows),
            "settled": len(settled),
            "eligible_settled": len(eligible),
            "pnl_units": round(pnl, 4),
            "roi_pct": round(100.0 * pnl / len(eligible), 2) if eligible else None,
            "clv_rows": len(clv),
            "mean_clv_pct": round(sum(clv) / len(clv), 3) if clv else None,
        }
    return summaries


def evidence_freshness(value: str, *, stale_after_days: int = 8) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {"generated_at": "", "age_days": None, "status": "MISSING"}
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text[:10]).replace(tzinfo=UTC)
        except ValueError:
            return {"generated_at": text, "age_days": None, "status": "INVALID"}
    age_days = max(0.0, (datetime.now(UTC) - parsed).total_seconds() / 86400.0)
    return {
        "generated_at": text,
        "age_days": round(age_days, 2),
        "status": "STALE" if age_days > stale_after_days else "FRESH",
    }


def settled_ledger_summary(rows: list[dict[str, str]], *, stake_field: str) -> dict[str, Any]:
    settled = [
        row
        for row in rows
        if truthy(row.get("settled")) or str(row.get("bet_outcome") or "").strip().lower() in {"won", "lost", "push", "void"}
    ]
    wins = sum(str(row.get("bet_outcome") or "").strip().lower() == "won" for row in settled)
    losses = sum(str(row.get("bet_outcome") or "").strip().lower() == "lost" for row in settled)
    pushes = sum(str(row.get("bet_outcome") or "").strip().lower() in {"push", "void"} for row in settled)
    pnl = sum(number(row.get("pnl_units")) for row in settled)
    staked = sum(max(0.0, number(row.get(stake_field), 1.0)) for row in settled)
    return {
        "registered": len(rows),
        "settled": len(settled),
        "pending": max(0, len(rows) - len(settled)),
        "wins": wins,
        "losses": losses,
        "pushes_or_voids": pushes,
        "pnl_units": round(pnl, 4),
        "staked_units": round(staked, 4),
        "roi_pct": round(pnl / staked * 100.0, 2) if staked else None,
    }


def report_csv_section(text: str, heading: str) -> list[dict[str, str]]:
    """Parse a small CSV table that follows an exact report heading."""
    lines = text.splitlines()
    try:
        start = lines.index(heading) + 1
    except ValueError:
        return []
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines):
        return []
    table: list[str] = []
    for line in lines[start:]:
        if not line.strip():
            break
        table.append(line)
    if len(table) < 2:
        return []
    try:
        return list(csv.DictReader(table))
    except (csv.Error, TypeError):
        return []


def goalscorer_research_summary() -> dict[str, Any]:
    backtest_dir = ROOT / "data" / "goalscorer" / "backtest"
    parity = load_text(backtest_dir / "parity-report.txt")
    walkforward = load_text(backtest_dir / "walkforward-report.txt")
    clv_rows = load_csv(ROOT / "data" / "goalscorer" / "fair-odds-lab-clv.csv")
    matched = [row for row in clv_rows if str(row.get("close_odds") or "").strip()]
    true_closes = [row for row in clv_rows if row.get("close_status") == "true_close"]
    signal_rows: list[dict[str, str]] = []
    quarantine_rows: list[dict[str, str]] = []
    quarantine_by_league: list[dict[str, Any]] = []
    league_labels = {
        "serie-a": "Serie A",
        "epl": "Premier League",
        "la-liga": "La Liga",
        "bundesliga": "Bundesliga",
        "ligue-1": "Ligue 1",
    }
    for league, label in league_labels.items():
        signal_rows.extend(load_csv(ROOT / "data" / "goalscorer" / f"fair-odds-lab-{league}-signals.csv"))
        league_quarantine = load_csv(ROOT / "data" / "goalscorer" / f"fair-odds-lab-{league}-quarantine.csv")
        quarantine_rows.extend(league_quarantine)
        quarantine_by_league.append(
            {
                "key": league,
                "label": label,
                **settled_ledger_summary(league_quarantine, stake_field="evaluation_stake_units"),
            }
        )
    ledger = settled_ledger_summary(signal_rows, stake_field="recommended_stake_units")
    quarantine_ledger = settled_ledger_summary(quarantine_rows, stake_field="evaluation_stake_units")
    activity_values = [
        str(row.get("settled_at") or row.get("compared_at") or row.get("kickoff") or "").strip()
        for row in signal_rows
    ]
    latest_activity = max((value for value in activity_values if value), default="")
    pooled_rows = {row.get("variant", ""): row for row in report_csv_section(walkforward, "Pooled metrics")}
    gate_rows = {row.get("variant", ""): row for row in report_csv_section(walkforward, "Promotion gate")}
    raw_metrics = pooled_rows.get("raw", {})
    beta_metrics = pooled_rows.get("beta", {})
    beta_gate = gate_rows.get("beta", {})

    def metric(row: dict[str, str], key: str) -> float | None:
        value = str(row.get(key) or "").strip()
        return number(value) if value and value != "-" else None

    raw_brier = metric(raw_metrics, "brier")
    beta_brier = metric(beta_metrics, "brier")
    raw_log_loss = metric(raw_metrics, "log_loss")
    beta_log_loss = metric(beta_metrics, "log_loss")
    raw_ece = metric(raw_metrics, "ece")
    beta_ece = metric(beta_metrics, "ece")
    blockers: list[str] = []
    evaluated_folds = int(number(beta_gate.get("evaluated_folds")))
    probability_gate = beta_gate.get("probability_gate") or "NOT_RUN"
    market_roi_gate = beta_gate.get("market_roi_gate") or "UNAVAILABLE"
    decision = beta_gate.get("decision") or "KEEP_RESEARCH"
    if evaluated_folds < 5:
        blockers.append("fifth fold pending")
    if probability_gate != "PASS":
        blockers.append(f"probability gate {probability_gate.lower()}")
    if market_roi_gate != "PASS":
        blockers.append(f"market ROI gate {market_roi_gate.lower()}")
    if not matched:
        blockers.append("no matched closing prices")
    if not quarantine_ledger["settled"]:
        blockers.append("no settled extreme-gap rows")
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
        "calibration": {
            "n": int(number(beta_metrics.get("n"))),
            "raw_brier": raw_brier,
            "beta_brier": beta_brier,
            "brier_delta": beta_brier - raw_brier if beta_brier is not None and raw_brier is not None else None,
            "raw_log_loss": raw_log_loss,
            "beta_log_loss": beta_log_loss,
            "log_loss_delta": beta_log_loss - raw_log_loss if beta_log_loss is not None and raw_log_loss is not None else None,
            "raw_ece": raw_ece,
            "beta_ece": beta_ece,
            "ece_delta": beta_ece - raw_ece if beta_ece is not None and raw_ece is not None else None,
            "raw_predicted": metric(raw_metrics, "predicted"),
            "beta_predicted": metric(beta_metrics, "predicted"),
            "actual": metric(beta_metrics, "actual"),
        },
        "beta_folds": evaluated_folds,
        "beta_fold_wins": int(number(beta_gate.get("fold_wins"))),
        "probability_gate": probability_gate,
        "market_roi_gate": market_roi_gate,
        "decision": decision,
        "blockers": blockers,
        "ledger": ledger,
        "extreme_gap_quarantine": {
            **quarantine_ledger,
            "by_league": quarantine_by_league,
        },
        "freshness": evidence_freshness(latest_activity),
    }


def assist_value_research_summary() -> dict[str, Any]:
    gates = load_json(ASSIST_GATES)
    prospective_rows = load_csv(ASSIST_PROSPECTIVE)
    prospective = settled_ledger_summary(prospective_rows, stake_field="stake_units")
    backtest = gates.get("backtest") or {}
    settlement = gates.get("settlement") or {}
    market = gates.get("market") or {}
    gate_prospective = gates.get("prospective") or {}
    if gates.get("reactivation_ready"):
        decision = "REVIEW_FOR_REACTIVATION"
    elif market.get("status") != "PASS":
        decision = "KEEP_FROZEN_MARKET_EVIDENCE"
    elif gate_prospective.get("status") != "PASS":
        decision = "KEEP_FROZEN_PROSPECTIVE_SAMPLE"
    else:
        decision = "KEEP_FROZEN_GATE_REVIEW"
    calibration = market.get("one_sided_margin_calibration") or {}
    return {
        "label": "Assist Value V1 Research",
        "lane_status": gates.get("lane_status", "FROZEN_RESEARCH"),
        "reactivation_ready": bool(gates.get("reactivation_ready")),
        "decision": decision,
        "backtest_status": backtest.get("status", "NOT_RUN"),
        "test_rows": int((((backtest.get("splits") or {}).get("test") or {}).get("calibrated") or {}).get("n") or 0),
        "test_brier": (((backtest.get("splits") or {}).get("test") or {}).get("calibrated") or {}).get("brier"),
        "settlement_status": settlement.get("status", "NOT_RUN"),
        "settlement_agreement_pct": number(settlement.get("agreement_rate")) * 100.0,
        "market_status": market.get("status", "NOT_RUN"),
        "market_rows": int(market.get("matched_participants") or 0),
        "market_calendar_span_days": int(calibration.get("calendar_span_days") or 0),
        "prospective_target": int(gate_prospective.get("target_minimum") or 100),
        "prospective": prospective,
        "freshness": evidence_freshness(str(gates.get("generated_at") or "")),
        "automation": {
            "capture_schedule": "Friday-Sunday 07:10 UTC, August-May",
            "captures_per_week": 3,
            "max_paid_api_calls_per_run": 10,
            "max_paid_api_calls_per_week": 30,
            "database_reads_per_capture": 0,
            "database_writes_per_capture": 0,
            "lineup_refresh_reuses_captured_prices": True,
        },
    }


def goalkeeper_saves_research_summary() -> dict[str, Any]:
    evidence = load_json(GOALKEEPER_SAVES_EVIDENCE)
    market = load_json(GOALKEEPER_SAVES_MARKET_PROBE)
    prospective = load_json(GOALKEEPER_SAVES_SHADOW_REPORT)
    capture = load_json(GOALKEEPER_SAVES_CAPTURE_STATUS)
    folds = evidence.get("folds") or []
    count_pass = bool(folds) and all(
        number(((fold.get("models") or {}).get("NB2_FULL") or {}).get("brier"))
        < number(((fold.get("models") or {}).get("INCUMBENT") or {}).get("brier"))
        and number(((fold.get("models") or {}).get("NB2_FULL") or {}).get("log_loss"))
        < number(((fold.get("models") or {}).get("INCUMBENT") or {}).get("log_loss"))
        for fold in folds
    )
    observed = market.get("observed") or {}
    prospective_evidence = prospective.get("evidence") or {}
    current = prospective.get("current") or {}
    return {
        "candidate": "goalkeeper-saves-v1-nb2-confirmed-starter",
        "count_gate": "PASS" if count_pass else "NOT_RUN_OR_FAIL",
        "historical_observations": int(number((evidence.get("target_audit") or {}).get("valid_team_observations"))),
        "model_samples": int(number(evidence.get("model_samples"))),
        "market_status": market.get("status", "NOT_RUN"),
        "over_lines": len(observed.get("over_lines") or []),
        "capture_status": capture.get("status", "NOT_RUN"),
        "capture_events_selected": int(number(capture.get("events_selected"))),
        "capture_events_with_lines": int(number(capture.get("events_with_lines"))),
        "capture_three_way_events": int(number(capture.get("three_way_events"))),
        "capture_rows_observed": int(number(capture.get("rows_observed"))),
        "prospective_status": prospective.get("status", "CAPTURE_NOT_BUILT"),
        "priced_lines": int(number(current.get("priced_lines"))),
        "eligible_lines": int(number(current.get("eligible_lines"))),
        "provisional_lines": int(number(current.get("provisional_lines"))),
        "candidate_board_preserved": bool(current.get("candidate_board_preserved")),
        "blocker_counts": current.get("blocker_counts") if isinstance(current.get("blocker_counts"), dict) else {},
        "signals": int(number(prospective_evidence.get("signals"))),
        "pending": int(number(prospective_evidence.get("pending"))),
        "settled": int(number(prospective_evidence.get("settled"))),
        "roi": finite_float(prospective_evidence.get("roi")),
        "clv": finite_float(prospective_evidence.get("clv")),
        "clv_matched": int(number(prospective_evidence.get("clv_matched"))),
        "true_close_coverage": finite_float(prospective_evidence.get("true_close_coverage")),
        "promotion_gate": "BLOCKED",
        "sellable": False,
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


def fixed(value: float | None, digits: int = 5) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def signed_number(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{number(value):+.{digits}f}"


def ratio_pct(value: float | None, digits: int = 1) -> str:
    return pct(value * 100.0 if value is not None else None, digits)


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


def tennis_lane_performance(path: Path) -> dict[str, Any]:
    rows = load_csv(path)
    if not rows:
        return {"status": "MISSING", "settled": 0, "pnl_units": 0.0, "roi_pct": None}

    latest_generated = max(str(row.get("generated_utc") or "") for row in rows)
    latest_rows = [row for row in rows if str(row.get("generated_utc") or "") == latest_generated]

    def select(period: str) -> dict[str, str] | None:
        candidates = [
            row
            for row in latest_rows
            if row.get("scope") == "all_time"
            and row.get("eval_period") == period
            and row.get("league_scope") == "combined"
            and row.get("policy_mode") == "base"
            and not str(row.get("bet_type") or "").strip()
        ]
        return candidates[0] if candidates else None

    # Current-policy evidence is preferred; older files may only contain overall rows.
    row = select("clean") or select("overall")
    if row is None:
        return {
            "status": "NO_COMBINED_ROW",
            "generated_at": latest_generated,
            "settled": 0,
            "pnl_units": 0.0,
            "roi_pct": None,
        }
    return {
        "status": "OK",
        "generated_at": latest_generated,
        "as_of_date": row.get("as_of_date") or "",
        "evidence_period": row.get("eval_period") or "overall",
        "signals": int(number(row.get("signals"))),
        "settled": int(number(row.get("settled"))),
        "pending": int(number(row.get("unsettled"))),
        "wins": int(number(row.get("wins"))),
        "losses": int(number(row.get("losses"))),
        "staked_units": round(number(row.get("staked_units")), 4),
        "pnl_units": round(number(row.get("pnl_units")), 4),
        "roi_pct": finite_float(row.get("roi_pct")),
    }


def tennis_lane_clv(path: Path) -> dict[str, Any]:
    rows = load_csv(path)
    values = [
        value
        for value in (finite_float(row.get("clv_implied_delta_pct")) for row in rows)
        if value is not None
    ]
    return {
        "rows": len(values),
        "avg_clv_pct": round(avg(values), 4) if values else None,
        "positive_clv_pct": round(100.0 * sum(value > 0 for value in values) / len(values), 2) if values else None,
    }


def tennis_lane_source_summary(lanes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Report whether the three decision-lane summaries were regenerated recently."""
    required = ("strict", "volume_200", "spread_v1")
    per_lane = {
        name: evidence_freshness(str((lanes.get(name) or {}).get("generated_at") or ""), stale_after_days=3)
        for name in required
    }
    statuses = {summary["status"] for summary in per_lane.values()}
    if statuses & {"MISSING", "INVALID"}:
        status = "SOURCE_MISSING"
    elif "STALE" in statuses:
        status = "STALE"
    else:
        status = "FRESH"
    generated = [
        summary["generated_at"]
        for summary in per_lane.values()
        if summary.get("generated_at")
    ]
    return {
        "status": status,
        "oldest_generated_at": min(generated) if generated else "",
        "lanes": per_lane,
    }


def tennis_model_evidence_summary() -> dict[str, Any]:
    lanes = {name: tennis_lane_performance(path) for name, path in TENNIS_LANE_FILES.items()}
    for name, path in TENNIS_CLV_FILES.items():
        lanes.setdefault(name, {})["clv"] = tennis_lane_clv(path)
    gap_report = load_json(TENNIS_GAP_REPORT)
    gap_replacement = gap_report.get("ml_guard_replacement") or {}
    replacements = gap_replacement.get("experiments") or {}
    for key in ("strict_gap_10_20_same_side", "volume200_gap_10_15_same_side"):
        replacements.setdefault(key, {"verdict": "NOT_RUN", "performance": {}})
    return {
        "lanes": lanes,
        "lane_source": tennis_lane_source_summary(lanes),
        "gap_source_status": "OK" if TENNIS_GAP_REPORT.exists() and gap_report else "SOURCE_MISSING",
        "gap_status": gap_replacement.get("status", "SOURCE_MISSING"),
        "gap_replacements": replacements,
        "side_flip_by_surface": gap_replacement.get("side_flip_by_surface") or {},
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


def tennis_props_shadow_decision(
    signals_path: Path = TENNIS_PROPS_SHADOW_SIGNALS,
    health_path: Path = TENNIS_PROPS_PIPELINE_HEALTH,
) -> dict[str, Any]:
    rows = load_csv(signals_path)
    health = load_json(health_path)
    settled = [
        row
        for row in rows
        if (row.get("settlement_status") or "").strip().lower() == "settled"
    ]
    pending = [
        row
        for row in rows
        if (row.get("settlement_status") or "pending").strip().lower() in {"", "pending"}
    ]
    pending_due: list[dict[str, str]] = []
    pending_future: list[dict[str, str]] = []
    pending_unknown: list[dict[str, str]] = []
    now = datetime.now(UTC)
    for row in pending:
        raw_start = str(row.get("match_start_utc") or "").strip()
        if not raw_start:
            pending_unknown.append(row)
            continue
        try:
            match_start = datetime.fromisoformat(raw_start.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pending_unknown.append(row)
            continue
        if match_start + timedelta(hours=6) <= now:
            pending_due.append(row)
        else:
            pending_future.append(row)
    voids = [
        row
        for row in rows
        if (row.get("settlement_status") or "").strip().lower() == "void"
    ]
    wins = sum((row.get("result") or "").strip().lower() == "win" for row in settled)
    losses = sum((row.get("result") or "").strip().lower() == "loss" for row in settled)
    pushes = sum((row.get("result") or "").strip().lower() == "push" for row in settled)
    pnl = sum(number(row.get("pnl")) for row in settled)
    staked = float(len(settled))
    roi_pct = pnl / staked * 100.0 if staked else None

    clv_values = [
        value
        for value in (
            finite_float(row.get("clv_pct"))
            for row in rows
            if (row.get("settlement_status") or "").strip().lower() != "void"
        )
        if value is not None
    ]
    mean_clv_pct = avg(clv_values)
    positive_clv_pct = (
        sum(value > 0 for value in clv_values) / len(clv_values) * 100.0
        if clv_values
        else None
    )
    clv_coverage_pct = len(clv_values) / len(rows) * 100.0 if rows else 0.0

    scored: list[tuple[float, float]] = []
    for row in settled:
        result = (row.get("result") or "").strip().lower()
        fair_odds = finite_float(row.get("fair_odds"))
        if result not in {"win", "loss"} or fair_odds is None or fair_odds <= 1.0:
            continue
        scored.append((1.0 / fair_odds, 1.0 if result == "win" else 0.0))
    predicted_hit_pct = avg([probability for probability, _ in scored])
    actual_hit_pct = avg([outcome for _, outcome in scored])
    brier = avg([(probability - outcome) ** 2 for probability, outcome in scored])
    calibration_gap_pp = (
        abs((actual_hit_pct or 0.0) - (predicted_hit_pct or 0.0)) * 100.0
        if scored
        else None
    )

    slam_aliases = {
        "australian open": "Australian Open",
        "roland garros": "Roland Garros",
        "french open": "Roland Garros",
        "wimbledon": "Wimbledon",
        "us open": "US Open",
        "u s open": "US Open",
    }
    settled_slams: set[str] = set()
    for row in settled:
        tournament = re.sub(r"[^a-z0-9]+", " ", str(row.get("tournament") or "").lower()).strip()
        for alias, canonical in slam_aliases.items():
            if alias in tournament:
                settled_slams.add(canonical)
                break

    market_rows: list[dict[str, Any]] = []
    for market in ("aces", "double_faults"):
        subset = [row for row in rows if (row.get("market") or "").strip().lower() == market]
        subset_settled = [
            row for row in subset if (row.get("settlement_status") or "").strip().lower() == "settled"
        ]
        subset_pnl = sum(number(row.get("pnl")) for row in subset_settled)
        market_rows.append(
            {
                "market": market,
                "registered": len(subset),
                "settled": len(subset_settled),
                "pnl_units": round(subset_pnl, 4),
                "roi_pct": round(subset_pnl / len(subset_settled) * 100.0, 2)
                if subset_settled
                else None,
            }
        )

    structural_ok = bool(health) and not bool(health.get("structural_error"))
    two_way_rows = int(number(health.get("two_way_rows")))
    price_integrity_pass = two_way_rows > 0
    gates = {
        "settled_sample": {"pass": len(settled) >= 300, "observed": len(settled), "target": 300},
        "slam_coverage": {
            "pass": len(settled_slams) >= 2,
            "observed": len(settled_slams),
            "target": 2,
            "events": sorted(settled_slams),
        },
        "roi": {"pass": roi_pct is not None and roi_pct >= 0.0, "observed_pct": roi_pct, "target_pct": 0.0},
        "clv_coverage": {
            "pass": len(clv_values) >= 300,
            "observed": len(clv_values),
            "target": 300,
            "coverage_pct": round(clv_coverage_pct, 2),
        },
        "mean_clv": {
            "pass": mean_clv_pct is not None and mean_clv_pct >= 1.0,
            "observed_pct": mean_clv_pct,
            "target_pct": 1.0,
        },
        "positive_clv": {
            "pass": positive_clv_pct is not None and positive_clv_pct >= 55.0,
            "observed_pct": positive_clv_pct,
            "target_pct": 55.0,
        },
        "calibration_sample": {"pass": len(scored) >= 100, "observed": len(scored), "target": 100},
        "calibration_brier": {
            "pass": brier is not None and brier <= 0.25,
            "observed": brier,
            "maximum": 0.25,
        },
        "calibration_gap": {
            "pass": calibration_gap_pp is not None and calibration_gap_pp <= 5.0,
            "observed_pp": calibration_gap_pp,
            "maximum_pp": 5.0,
        },
        "price_integrity": {
            "pass": price_integrity_pass,
            "observed_two_way_rows": two_way_rows,
            "requirement": "two-way prices or a separately approved one-sided pricing policy",
        },
        "pipeline_health": {
            "pass": structural_ok,
            "state": health.get("state", "MISSING"),
            "structural_error": health.get("structural_error") if health else None,
        },
    }
    failed_gates = [name for name, gate in gates.items() if not gate["pass"]]
    blockers: list[str] = []
    if not rows:
        blockers.append("local shadow ledger is missing or empty")
    if len(settled) < 300:
        blockers.append(f"settled sample {len(settled)}/300")
    if len(settled_slams) < 2:
        blockers.append(f"Slam coverage {len(settled_slams)}/2")
    if len(clv_values) < 300:
        blockers.append(f"CLV sample {len(clv_values)}/300")
    if len(scored) < 100:
        blockers.append(f"calibration sample {len(scored)}/100")
    if not price_integrity_pass:
        blockers.append(f"one-sided price feed ({two_way_rows} two-way rows)")
    if not structural_ok:
        blockers.append(f"pipeline health {health.get('state', 'MISSING')}")

    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "lane": "aces_dfs_canonical_shadow",
        "status": "REVIEW_FOR_PROMOTION" if not failed_gates else "COLLECTING_EVIDENCE",
        "automatic_promotion": False,
        "registered": len(rows),
        "settled": len(settled),
        "pending": len(pending),
        "pending_due": len(pending_due),
        "pending_future": len(pending_future),
        "pending_unknown": len(pending_unknown),
        "void": len(voids),
        "record": {"wins": wins, "losses": losses, "pushes": pushes},
        "staked_units": staked,
        "pnl_units": round(pnl, 4),
        "roi_pct": round(roi_pct, 2) if roi_pct is not None else None,
        "clv": {
            "rows": len(clv_values),
            "coverage_pct": round(clv_coverage_pct, 2),
            "mean_pct": round(mean_clv_pct, 4) if mean_clv_pct is not None else None,
            "positive_pct": round(positive_clv_pct, 2) if positive_clv_pct is not None else None,
        },
        "calibration": {
            "rows": len(scored),
            "brier": round(brier, 6) if brier is not None else None,
            "predicted_hit_pct": round(predicted_hit_pct * 100.0, 2) if predicted_hit_pct is not None else None,
            "actual_hit_pct": round(actual_hit_pct * 100.0, 2) if actual_hit_pct is not None else None,
            "absolute_gap_pp": round(calibration_gap_pp, 2) if calibration_gap_pp is not None else None,
            "pushes_excluded": True,
        },
        "settled_slams": sorted(settled_slams),
        "by_market": market_rows,
        "feed": {
            "state": health.get("state", "MISSING"),
            "line_rows": int(number(health.get("line_rows"))),
            "matched_rows": int(number(health.get("matched_rows"))),
            "match_rate_pct": finite_float(health.get("match_rate_pct")),
            "two_way_rows": two_way_rows,
            "over_only_rows": int(number(health.get("over_only_rows"))),
            "public_bettable_rows": int(number(health.get("public_bettable_rows"))),
            "top_shadow_blocker": health.get("top_shadow_blocker", ""),
        },
        "gates": gates,
        "failed_gates": failed_gates,
        "blockers": blockers,
        "gate_rule": (
            "Human review only after 300 settled lines across at least two Slams, non-negative ROI, "
            "mean CLV >= +1%, positive CLV >= 55%, at least 100 calibrated win/loss rows with "
            "Brier <= 0.25 and absolute calibration gap <= 5pp, plus approved price integrity "
            "and a healthy pipeline."
        ),
    }


def tennis_props_shadow_decision_report(summary: dict[str, Any]) -> str:
    record = summary["record"]
    clv = summary["clv"]
    calibration = summary["calibration"]
    feed = summary["feed"]
    blockers = "; ".join(summary["blockers"]) or "none"
    mean_clv = pct(clv["mean_pct"], 2)
    positive_clv = f"{clv['positive_pct']:.1f}%" if clv["positive_pct"] is not None else "-"
    predicted_hit = (
        f"{calibration['predicted_hit_pct']:.1f}%"
        if calibration["predicted_hit_pct"] is not None
        else "-"
    )
    actual_hit = (
        f"{calibration['actual_hit_pct']:.1f}%"
        if calibration["actual_hit_pct"] is not None
        else "-"
    )
    calibration_gap = (
        f"{calibration['absolute_gap_pp']:.1f}pp"
        if calibration["absolute_gap_pp"] is not None
        else "-"
    )
    market_lines = [
        (
            f"- {row['market']}: {row['settled']}/{row['registered']} settled, "
            f"{row['pnl_units']:+.2f}u, ROI {pct(row['roi_pct'])}"
        )
        for row in summary["by_market"]
    ]
    return "\n".join(
        [
            "Tennis Aces/DF Weekly Decision Report",
            f"Generated UTC: {summary['generated_at']}",
            f"Status: {summary['status']} (never auto-promoted)",
            "",
            (
                f"Sample: {summary['settled']}/{summary['registered']} settled; "
                f"{summary['pending']} pending ({summary.get('pending_due', 0)} due, "
                f"{summary.get('pending_future', 0)} future, {summary.get('pending_unknown', 0)} unknown); "
                f"{summary['void']} void"
            ),
            f"Record: {record['wins']}W/{record['losses']}L/{record['pushes']}P",
            f"P/L: {summary['pnl_units']:+.2f}u | ROI: {pct(summary['roi_pct'])}",
            f"CLV: {mean_clv} mean; {positive_clv} positive; n={clv['rows']}",
            (
                "Calibration: "
                f"Brier {calibration['brier'] if calibration['brier'] is not None else '-'}; "
                f"predicted {predicted_hit}; actual {actual_hit}; gap {calibration_gap}; "
                f"n={calibration['rows']}"
            ),
            (
                "Feed: "
                f"{feed['state']}; matched {feed['matched_rows']}/{feed['line_rows']}; "
                f"two-way {feed['two_way_rows']}; over-only {feed['over_only_rows']}; "
                f"public bettable {feed['public_bettable_rows']}"
            ),
            "",
            "By market:",
            *market_lines,
            "",
            f"Blockers: {blockers}",
            f"Promotion gate: {summary['gate_rule']}",
        ]
    )


def venue_ace_factor_v1_summary() -> dict[str, Any]:
    factors = load_csv(TENNIS_VENUE_ACE_FACTORS)
    observations = load_csv(TENNIS_VENUE_ACE_V1_OBSERVATIONS)
    gate_payload = load_json(TENNIS_VENUE_ACE_V1_GATE)
    scope_factors = [
        row
        for row in factors
        if str(row.get("tour") or "").upper() == "ATP"
        and str(row.get("surface") or "") in {"Hard", "Clay"}
    ]
    eligible = [
        row for row in scope_factors if str(row.get("eligible") or "").lower() == "true"
    ]
    settled = [row for row in observations if str(row.get("settlement_status") or "").lower() == "settled"]
    pending = [row for row in observations if str(row.get("settlement_status") or "").lower() == "pending"]
    pnl_units = sum(number(row.get("pnl")) for row in settled)
    clv_values = [
        number(row.get("clv_pct"))
        for row in observations
        if str(row.get("clv_pct") or "").strip()
    ]
    factor_values = [number(row.get("ace_factor"), 1.0) for row in eligible]
    paired = ((gate_payload.get("paired_scoring") or {}).get("overall") or {}) if gate_payload else {}
    source_missing = not TENNIS_VENUE_ACE_FACTORS.exists() and not TENNIS_VENUE_ACE_V1_OBSERVATIONS.exists()
    return {
        "status": "SOURCE_MISSING" if source_missing else "PROSPECTIVE_SHADOW",
        "automatic_promotion": False,
        "eligible_venues": len(eligible),
        "total_venues": len(scope_factors),
        "factor_min": min(factor_values) if factor_values else None,
        "factor_max": max(factor_values) if factor_values else None,
        "registered": len(observations),
        "settled": len(settled),
        "pending": len(pending),
        "distinct_events": len(
            {
                str(row.get("event_id") or row.get("signal_id") or "")
                for row in observations
                if str(row.get("event_id") or row.get("signal_id") or "")
            }
        ),
        "pnl_units": pnl_units,
        "roi_pct": (pnl_units / len(settled) * 100.0) if settled else None,
        "clv_rows": len(clv_values),
        "mean_clv_pct": (sum(clv_values) / len(clv_values)) if clv_values else None,
        "paired_rows": int(number(paired.get("n"))),
        "control_brier": finite_float(paired.get("control_brier")),
        "candidate_brier": finite_float(paired.get("candidate_brier")),
        "brier_delta": finite_float(paired.get("brier_delta")),
        "passed_gate_count": int(number(gate_payload.get("passed_gate_count"))) if gate_payload else 0,
        "total_gate_count": int(number(gate_payload.get("total_gate_count"))) if gate_payload else 5,
        "promotion_target_rows": 600,
        "promotion_target_events": 150,
        "decision": "SOURCE_MISSING" if source_missing else "NOT_SELLABLE",
    }


def tennis_props_v3_snapshot() -> dict[str, Any]:
    raw = os.environ.get("TENNIS_PROPS_V3_WEEKLY_JSON", "").strip()
    if not raw:
        return load_json(TENNIS_PROPS_V3_LOCAL_JSON)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"_error": f"repository variable JSON is invalid: {exc}"}
    return payload if isinstance(payload, dict) else {"_error": "repository variable is not a JSON object"}


def tennis_props_market_benchmark() -> dict[str, Any]:
    rows = load_csv(TENNIS_PROPS_OBSERVATIONS)
    settled = [row for row in rows if row.get("settlement_status") == "settled"]
    scored = [row for row in settled if row.get("outcome_over") in {"0", "1"}]

    def mean(field: str, sample: list[dict[str, str]]) -> float | None:
        values = [pf(row.get(field)) for row in sample]
        numeric = [value for value in values if value is not None]
        return sum(numeric) / len(numeric) if numeric else None

    model_brier = mean("model_brier", scored)
    market_brier = mean("observed_market_brier", scored)
    return {
        "observations": len(rows),
        "settled": len(settled),
        "scored": len(scored),
        "pending": sum((row.get("settlement_status") or "pending") == "pending" for row in rows),
        "model_count_mae": mean("model_count_abs_error", settled),
        "market_count_mae": mean("observed_market_count_abs_error", settled),
        "model_brier": model_brier,
        "market_brier": market_brier,
        "brier_delta_vs_market": (market_brier - model_brier) if market_brier is not None and model_brier is not None else None,
        "status": (
            "SOURCE_MISSING"
            if not TENNIS_PROPS_OBSERVATIONS.exists()
            else "REVIEW_REQUIRED"
            if len(settled) >= 100
            else "EVIDENCE_BUILDING"
        ),
    }


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
    corners_v4_g0 = corners_v4_g0_summary(load_json(CORNERS_V4_G0_DIAGNOSTIC))
    api_football_health = load_json(OUT_DIR / "api-football-counts-health.json")
    api_football_agreement = load_json(OUT_DIR / "api-football-source-agreement.json")
    team_fouls_m1 = load_json(OUT_DIR / "fouls-empirical-baseline.json")
    team_fouls_f1 = load_json(OUT_DIR / "team-fouls-v1-fold-report.json")
    team_fouls_f2 = load_json(OUT_DIR / "team-fouls-f2-fold-report.json")
    team_fouls_m2 = load_json(OUT_DIR / "team-fouls-definition-agreement.json")

    team_clv_rows = load_csv(OUT_DIR / "team-shots-v3-ema20-clv-monitor.csv")
    corners_clv_rows = load_csv(OUT_DIR / "corners-v0-clv-monitor.csv")
    tennis_gap_guard = ml_gap_guard_summary()
    tennis_model_evidence = tennis_model_evidence_summary()
    tennis_props_v3 = tennis_props_v3_snapshot()
    tennis_props_v4 = load_json(TENNIS_PROPS_V4_JSON)
    tennis_breaks_v1 = load_json(TENNIS_BREAKS_V1_GATE)
    tennis_venue_ace_v1 = venue_ace_factor_v1_summary()
    tennis_most_aces_forecast = load_json(TENNIS_MOST_ACES_FORECAST_JSON)
    tennis_most_aces_prices = most_aces_price_summary()
    tennis_props_benchmark = tennis_props_market_benchmark()
    tennis_props_shadow = tennis_props_shadow_decision()
    goalscorer_research = goalscorer_research_summary()
    assist_value_research = assist_value_research_summary()
    goalkeeper_saves_research = goalkeeper_saves_research_summary()
    automation_budget = load_json(AUTOMATION_BUDGET)
    tennis_snapshot = load_tennis_evidence_snapshot()
    snapshot_sections = tennis_snapshot.get("sections") if isinstance(tennis_snapshot, dict) else None
    snapshot_freshness = evidence_freshness(str(tennis_snapshot.get("generated_at") or ""))
    if isinstance(snapshot_sections, dict) and snapshot_freshness["status"] in {"FRESH", "STALE"}:
        snapshot_model_evidence = snapshot_sections.get("tennis_model_evidence") or {}
        for key in ("lanes", "lane_source", "gap_source_status", "gap_status", "gap_replacements", "side_flip_by_surface"):
            if key in snapshot_model_evidence:
                tennis_model_evidence[key] = snapshot_model_evidence[key]
        tennis_props_v3 = snapshot_sections.get("tennis_props_v3") or tennis_props_v3
        tennis_props_v4 = snapshot_sections.get("tennis_props_v4") or tennis_props_v4
        tennis_venue_ace_v1 = snapshot_sections.get("tennis_venue_ace_factor_v1") or tennis_venue_ace_v1
        tennis_most_aces_forecast = snapshot_sections.get("tennis_most_aces_forecast") or tennis_most_aces_forecast
        tennis_most_aces_prices = snapshot_sections.get("tennis_most_aces_prices") or tennis_most_aces_prices
        tennis_props_benchmark = snapshot_sections.get("tennis_props_market_benchmark") or tennis_props_benchmark
        tennis_props_shadow = snapshot_sections.get("tennis_props_shadow_decision") or tennis_props_shadow

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
        "corners_v4_g0": corners_v4_g0,
        "api_football_counts": {
            "health": api_football_health,
            "agreement": api_football_agreement,
        },
        "team_fouls_v1": {
            "m1": team_fouls_m1,
            "f1": team_fouls_f1,
            "f2": team_fouls_f2,
            "m2": team_fouls_m2,
        },
        "tennis_ml_gap_guard": tennis_gap_guard,
        "tennis_model_evidence": tennis_model_evidence,
        "tennis_props_v3": tennis_props_v3,
        "tennis_props_v4": tennis_props_v4,
        "tennis_breaks_v1": tennis_breaks_v1,
        "tennis_venue_ace_factor_v1": tennis_venue_ace_v1,
        "tennis_most_aces_forecast": tennis_most_aces_forecast,
        "tennis_most_aces_prices": tennis_most_aces_prices,
        "tennis_props_market_benchmark": tennis_props_benchmark,
        "tennis_props_shadow_decision": tennis_props_shadow,
        "tennis_evidence_source": {
            "status": snapshot_freshness["status"] if isinstance(snapshot_sections, dict) else tennis_snapshot.get("_status", "SOURCE_MISSING"),
            "source": tennis_snapshot.get("_source", "none"),
            "generated_at": tennis_snapshot.get("generated_at", ""),
            "age_days": snapshot_freshness.get("age_days"),
            "error": tennis_snapshot.get("_error", ""),
        },
        "goalscorer_v2": goalscorer_research,
        "assist_value_v1": assist_value_research,
        "goalkeeper_saves_v1": goalkeeper_saves_research,
        "automation_budget": automation_budget,
    }


    stale_models = [
        name
        for name, summary in (
            ("goalscorer_v2", goalscorer_research),
            ("assist_value_v1", assist_value_research),
        )
        if (summary.get("freshness") or {}).get("status") in {"MISSING", "INVALID", "STALE"}
    ]
    payload["status"] = {
        "pause_required": bool(
            payload["team_shots_v3_ema20"]["clv"]["pause_rule_fired"]
            or payload["corners_v0"]["clv"]["pause_rule_fired"]
        ),
        "stale_models": stale_models,
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
    team_fouls_f2_decision = ((team_fouls.get("f2") or {}).get("decision") or {})
    team_fouls_m2 = team_fouls.get("m2") or {}
    goalkeeper_saves = payload.get("goalkeeper_saves_v1") or {}
    tennis = payload["tennis_ml_gap_guard"]
    tennis_props_v3 = payload.get("tennis_props_v3") or {}
    tennis_venue_ace_v1 = payload.get("tennis_venue_ace_factor_v1") or {}
    tennis_props_benchmark = payload.get("tennis_props_market_benchmark") or {}
    tennis_props_shadow = payload.get("tennis_props_shadow_decision") or {}
    tennis_breaks_v1 = payload.get("tennis_breaks_v1") or {}
    goalscorer = payload["goalscorer_v2"]
    assist = payload["assist_value_v1"]
    automation = payload.get("automation_budget") or {}
    odds_budget = (automation.get("providers") or {}).get("odds_api_io") or {}
    team_gate = team["segment_gate"]
    team_clv = team["clv"]
    corners_clv = corners["clv"]
    team_v4 = (vnext.get("team_shots_v4") or {})
    corners_v3 = (vnext.get("corners_v3") or {})
    team_v4_live = team_v4.get("prospective") or {}
    corners_v3_live = corners_v3.get("prospective") or {}
    team_v4_warmup = team_v4.get("warmup_tracking") or {}
    corners_v3_warmup = corners_v3.get("warmup_tracking") or {}
    team_v4_scan = team_v4.get("latest_scan") or {}
    corners_v3_scan = corners_v3.get("latest_scan") or {}
    corners_v4_g0 = payload.get("corners_v4_g0") or {}

    lines = [
        "# Weekly Research Lane Report",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Overall read: {'PAUSE REQUIRED' if payload['status']['pause_required'] else 'observe live sample'}",
        "",
        "## Football Counts vNext",
        "",
        f"- Team Shots v4: count {team_v4.get('count_gate', 'NOT_RUN')}; prospective {team_v4.get('prospective_status', 'BLOCKED')}; promotion {team_v4.get('promotion_gate', 'BLOCKED')}.",
        f"- Team Shots v4 evidence: {team_v4_live.get('signals', 0)} signals, {team_v4_live.get('settled', 0)} settled, {number(team_v4_live.get('pnl_units')):+.2f}u, ROI {pct(number(team_v4_live.get('roi')) * 100) if team_v4_live.get('roi') is not None else '-'}, true-close CLV {pct(number(team_v4_live.get('mean_true_close_clv')) * 100) if team_v4_live.get('mean_true_close_clv') is not None else '-'}.",
        f"- Team Shots v4 warm-up tracking (not bets): {team_v4_warmup.get('signals', 0)} signals, {team_v4_warmup.get('settled', 0)} settled / {team_v4_warmup.get('pending', 0)} pending, {number(team_v4_warmup.get('pnl_units')):+.2f}u, ROI {pct(number(team_v4_warmup.get('roi')) * 100) if team_v4_warmup.get('roi') is not None else '-'}.",
        f"- Team Shots v4 latest scan: {team_v4_scan.get('state', 'NOT_RUN')}; {team_v4_scan.get('scored_rows', 0)} rows / {team_v4_scan.get('scored_fixtures', 0)} fixtures scored; {team_v4_scan.get('edge_pass_but_warmup_blocked_fixtures', 0)} fixtures passed edge but were warm-up blocked; blockers {team_v4_scan.get('blocker_rows') or '-'}.",
        f"- Corners v3: count {corners_v3.get('count_gate', 'NOT_RUN')}; prospective {corners_v3.get('prospective_status', 'BLOCKED')}; promotion {corners_v3.get('promotion_gate', 'BLOCKED')}.",
        f"- Corners v3 evidence: {corners_v3_live.get('signals', 0)} signals, {corners_v3_live.get('settled', 0)} settled, {number(corners_v3_live.get('pnl_units')):+.2f}u, ROI {pct(number(corners_v3_live.get('roi')) * 100) if corners_v3_live.get('roi') is not None else '-'}, true-close CLV {pct(number(corners_v3_live.get('mean_true_close_clv')) * 100) if corners_v3_live.get('mean_true_close_clv') is not None else '-'}.",
        f"- Corners v3 warm-up tracking (not bets): {corners_v3_warmup.get('signals', 0)} signals, {corners_v3_warmup.get('settled', 0)} settled / {corners_v3_warmup.get('pending', 0)} pending, {number(corners_v3_warmup.get('pnl_units')):+.2f}u, ROI {pct(number(corners_v3_warmup.get('roi')) * 100) if corners_v3_warmup.get('roi') is not None else '-'}.",
        f"- Corners v3 latest scan: {corners_v3_scan.get('state', 'NOT_RUN')}; {corners_v3_scan.get('scored_rows', 0)} rows / {corners_v3_scan.get('scored_fixtures', 0)} fixtures scored; {corners_v3_scan.get('edge_pass_but_warmup_blocked_fixtures', 0)} fixtures passed edge but were warm-up blocked; blockers {corners_v3_scan.get('blocker_rows') or '-'}.",
        f"- Corners v4 G0 research: {corners_v4_g0.get('decision', 'NOT_RUN')}; {corners_v4_g0.get('enriched_samples', 0)}/{corners_v4_g0.get('total_samples', 0)} enriched; latest holdout MAE delta {signed_number(corners_v4_g0.get('mae_delta'), 4)}; real-market Brier delta {signed_number(corners_v4_g0.get('brier_delta'), 4)} on n={corners_v4_g0.get('market_rows', 0)}; line gates {corners_v4_g0.get('passed_lines', 0)}/{corners_v4_g0.get('available_lines', 0)} passed; failed {', '.join(corners_v4_g0.get('failed_lines') or []) or '-'}.",
        "- Neither experiment changes live routing or stakes.",
        f"- API-Football count archive: {api_health.get('archive_rows', 0)} fixtures; latest {api_health.get('latest_fixture_date') or '-'}; last run {api_health.get('requests_used', 0)}/{api_health.get('max_requests', 0)} requests.",
        f"- Cross-provider agreement: {api_agreement.get('matched_fixtures', 0)}/{api_agreement.get('api_rows', 0)} API fixtures matched; status {api_agreement.get('status', 'NOT_RUN')}.",
        f"- Team Fouls: F1 {team_fouls_decision.get('status', 'NOT_RUN')}; F2 {team_fouls_f2_decision.get('status', 'NOT_RUN')}; M2 {team_fouls_m2.get('status', 'NOT_RUN')}; market prices BLOCKED; signals disabled.",
        f"- Goalkeeper Saves v1: count {goalkeeper_saves.get('count_gate', 'NOT_RUN')} on {goalkeeper_saves.get('historical_observations', 0):,} observations; discovery {goalkeeper_saves.get('market_status', 'NOT_RUN')} ({goalkeeper_saves.get('over_lines', 0)} probe Over lines); latest capture {goalkeeper_saves.get('capture_status', 'NOT_RUN')} ({goalkeeper_saves.get('capture_events_selected', 0)} events selected / {goalkeeper_saves.get('capture_rows_observed', 0)} rows / {goalkeeper_saves.get('capture_three_way_events', 0)} with 1X2); prospective {goalkeeper_saves.get('prospective_status', 'BLOCKED')} with {goalkeeper_saves.get('priced_lines', 0)} priced lines, {goalkeeper_saves.get('eligible_lines', 0)} eligible, {goalkeeper_saves.get('provisional_lines', 0)} predicted-XI research rows, {goalkeeper_saves.get('signals', 0)} signals and {goalkeeper_saves.get('settled', 0)} settled; blockers {goalkeeper_saves.get('blocker_counts', {})}; ROI {ratio_pct(goalkeeper_saves.get('roi'))}, CLV {ratio_pct(goalkeeper_saves.get('clv'))} n={goalkeeper_saves.get('clv_matched', 0)}; promotion BLOCKED.",
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
            (
                f"- Held-out calibration (n={goalscorer['calibration']['n']:,}): "
                f"raw -> beta Brier {fixed(goalscorer['calibration']['raw_brier'])} -> {fixed(goalscorer['calibration']['beta_brier'])} "
                f"(delta {fixed(goalscorer['calibration']['brier_delta'])}); "
                f"log loss {fixed(goalscorer['calibration']['raw_log_loss'])} -> {fixed(goalscorer['calibration']['beta_log_loss'])} "
                f"(delta {fixed(goalscorer['calibration']['log_loss_delta'])}); "
                f"ECE {ratio_pct(goalscorer['calibration']['raw_ece'], 2)} -> {ratio_pct(goalscorer['calibration']['beta_ece'], 2)} "
                f"(delta {ratio_pct(goalscorer['calibration']['ece_delta'], 2)})."
            ),
            (
                f"- Mean probability: raw {ratio_pct(goalscorer['calibration']['raw_predicted'], 2)} | "
                f"beta {ratio_pct(goalscorer['calibration']['beta_predicted'], 2)} | "
                f"actual {ratio_pct(goalscorer['calibration']['actual'], 2)}."
            ),
            f"- Beta calibration: {goalscorer['beta_fold_wins']}/{goalscorer['beta_folds']} fold wins | probability gate {goalscorer['probability_gate']} | market gate {goalscorer['market_roi_gate']}.",
            f"- Real-price CLV coverage: {goalscorer['matched_closes']}/{goalscorer['signals']} ({goalscorer['clv_coverage_pct']:.1f}%) | true closes {goalscorer['true_closes']}.",
            f"- Settled ledger: {goalscorer['ledger']['settled']}/{goalscorer['ledger']['registered']} settled, {goalscorer['ledger']['wins']}W/{goalscorer['ledger']['losses']}L, {goalscorer['ledger']['pnl_units']:+.2f}u, ROI {pct(goalscorer['ledger']['roi_pct'])}.",
            f"- Extreme-gap quarantine: {goalscorer['extreme_gap_quarantine']['settled']}/{goalscorer['extreme_gap_quarantine']['registered']} settled, {goalscorer['extreme_gap_quarantine']['pnl_units']:+.2f}u at 1u evaluation stakes, ROI {pct(goalscorer['extreme_gap_quarantine']['roi_pct'])}.",
            "- Extreme-gap by league: "
            + (
                "; ".join(
                    f"{row['label']} {row['settled']}/{row['registered']} settled, {row['pnl_units']:+.2f}u, ROI {pct(row['roi_pct'])}"
                    for row in goalscorer["extreme_gap_quarantine"]["by_league"]
                    if row["registered"]
                )
                or "no rows registered yet"
            )
            + ".",
            f"- Evidence freshness: {goalscorer['freshness']['status']} ({goalscorer['freshness']['generated_at'] or 'missing'}).",
            f"- Decision: {goalscorer['decision']} | blockers: {', '.join(goalscorer['blockers']) or 'none'}.",
            "",
            "## Assist Value V1 Research Gate",
            "",
            f"- Lane: {assist['lane_status']} | decision {assist['decision']} | reactivation ready {'YES' if assist['reactivation_ready'] else 'NO'}.",
            f"- Historical gate: {assist['backtest_status']} on {assist['test_rows']:,} test rows; calibrated Brier {number(assist['test_brier']):.5f}.",
            f"- Settlement gate: {assist['settlement_status']} | player-assist agreement {assist['settlement_agreement_pct']:.2f}%.",
            f"- Market gate: {assist['market_status']} | {assist['market_rows']} matched player prices across {assist['market_calendar_span_days']} calendar days.",
            f"- Prospective ledger: {assist['prospective']['settled']}/{assist['prospective']['registered']} settled (target {assist['prospective_target']}), {assist['prospective']['pnl_units']:+.2f}u, ROI {pct(assist['prospective']['roi_pct'])}.",
            f"- Evidence freshness: {assist['freshness']['status']} ({assist['freshness']['generated_at'] or 'missing'}).",
            f"- Automation budget: {assist['automation']['capture_schedule']}; <= {assist['automation']['max_paid_api_calls_per_run']} Odds-API calls/run and <= {assist['automation']['max_paid_api_calls_per_week']} calls/week; zero database reads/writes.",
            "- No public output, staking, database writes or automatic promotion are authorised.",
            "",
            "## Automation Budget",
            "",
            f"- Registry status: {automation.get('status', 'NOT_RUN')}; every scheduled GitHub workflow must be registered.",
            f"- Odds-API.io worst registered hour: {odds_budget.get('max_requests_in_one_hour', '-')} / {odds_budget.get('requests_per_hour', '-')} requests.",
            f"- Registered database envelope: {(automation.get('database') or {}).get('registered_reads_per_week_max', '-')} reads/week and {(automation.get('database') or {}).get('registered_writes_per_week_max', '-')} writes/week maximum.",
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
            "## Venue Ace Factor v1",
            "",
            (
                f"- Status: {tennis_venue_ace_v1.get('status', 'NOT_RUN')} / "
                f"{tennis_venue_ace_v1.get('decision', 'NOT_SELLABLE')}"
            ),
            (
                f"- Venue coverage: {tennis_venue_ace_v1.get('eligible_venues', 0)}/"
                f"{tennis_venue_ace_v1.get('total_venues', 0)} eligible."
            ),
            (
                f"- Prospective evidence: {tennis_venue_ace_v1.get('settled', 0)}/"
                f"{tennis_venue_ace_v1.get('promotion_target_rows', 600)} settled across "
                f"{tennis_venue_ace_v1.get('distinct_events', 0)}/"
                f"{tennis_venue_ace_v1.get('promotion_target_events', 150)} events; "
                f"P/L {number(tennis_venue_ace_v1.get('pnl_units')):+.2f}u; "
                f"ROI {pct(tennis_venue_ace_v1.get('roi_pct'))}; "
                f"CLV {pct(tennis_venue_ace_v1.get('mean_clv_pct'), 2)} "
                f"n={tennis_venue_ace_v1.get('clv_rows', 0)}."
            ),
            "- Shadow only. This block never changes routing, stakes or public recommendations.",
        ]
    )

    lines.extend(
        [
            "",
            "## Tennis Aces/DF Prospective Decision",
            "",
            tennis_props_shadow_decision_report(tennis_props_shadow),
            "",
            tennis_breaks_gate_line(tennis_breaks_v1),
            "",
            "## Tennis Props Model vs Bet365",
            "",
            f"- Status: {tennis_props_benchmark.get('status', 'EVIDENCE_BUILDING')}",
            f"- Clean main lines: {tennis_props_benchmark.get('observations', 0)} observed, {tennis_props_benchmark.get('settled', 0)} settled, {tennis_props_benchmark.get('pending', 0)} pending.",
            f"- Count MAE: model {number(tennis_props_benchmark.get('model_count_mae')):.3f}; observed Bet365-implied mean {number(tennis_props_benchmark.get('market_count_mae')):.3f}.",
            f"- Brier: model {number(tennis_props_benchmark.get('model_brier')):.4f}; Bet365 {number(tennis_props_benchmark.get('market_brier')):.4f}; delta {number(tennis_props_benchmark.get('brier_delta_vs_market')):+.4f} (positive favours the model).",
            "- No automatic parameter change; 100 settled clean lines triggers a registered challenger review, not promotion.",
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
            "- Assist V1 passed count calibration and settlement integrity, but remains frozen until 90-day market calibration and 100 prospective settled signals pass.",
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
    team_fouls_f2_decision = ((team_fouls.get("f2") or {}).get("decision") or {})
    team_fouls_m2 = team_fouls.get("m2") or {}
    goalkeeper_saves = payload.get("goalkeeper_saves_v1") or {}
    tennis = payload["tennis_ml_gap_guard"]
    tennis_model_evidence = payload.get("tennis_model_evidence") or {}
    tennis_props_v3 = payload.get("tennis_props_v3") or {}
    tennis_venue_ace_v1 = payload.get("tennis_venue_ace_factor_v1") or {}
    tennis_props_benchmark = payload.get("tennis_props_market_benchmark") or {}
    tennis_props_shadow = payload.get("tennis_props_shadow_decision") or {}
    tennis_breaks_v1 = payload.get("tennis_breaks_v1") or {}
    goalscorer = payload["goalscorer_v2"]
    assist = payload["assist_value_v1"]
    automation = payload.get("automation_budget") or {}
    odds_budget = (automation.get("providers") or {}).get("odds_api_io") or {}
    team_clv = team["clv"]
    corners_clv = corners["clv"]
    team_v4 = (vnext.get("team_shots_v4") or {})
    corners_v3 = (vnext.get("corners_v3") or {})
    team_v4_live = team_v4.get("prospective") or {}
    corners_v3_live = corners_v3.get("prospective") or {}
    team_v4_scan = team_v4.get("latest_scan") or {}
    corners_v3_scan = corners_v3.get("latest_scan") or {}
    corners_v4_g0 = payload.get("corners_v4_g0") or {}
    team_v4_warmup = team_v4.get("warmup_tracking") or {}
    corners_v3_warmup = corners_v3.get("warmup_tracking") or {}
    tennis_lanes = tennis_model_evidence.get("lanes") or {}
    gap_replacements = tennis_model_evidence.get("gap_replacements") or {}
    gap_source_status = tennis_model_evidence.get("gap_source_status", "SOURCE_MISSING")
    side_flip_by_surface = tennis_model_evidence.get("side_flip_by_surface") or {}
    tennis_evidence_source = payload.get("tennis_evidence_source") or {}
    tennis_lane_source = tennis_model_evidence.get("lane_source") or {}

    def action_lines() -> list[str]:
        actions: list[str] = []
        strict_lane = tennis_lanes.get("strict") or {}
        volume_lane = tennis_lanes.get("volume_200") or {}
        hard_flip = side_flip_by_surface.get("Hard") or side_flip_by_surface.get("hard") or {}
        strict_gap = (gap_replacements.get("strict_gap_10_20_same_side") or {}).get("performance") or {}
        volume_gap = (gap_replacements.get("volume200_gap_10_15_same_side") or {}).get("performance") or {}
        if int(number(strict_lane.get("settled"))) >= 100 and number(strict_lane.get("roi_pct")) > 0:
            actions.append(
                f"KEEP: Tennis Strict only as established ML lane ({pct(strict_lane.get('roi_pct'))}, "
                f"n={int(number(strict_lane.get('settled')))})"
            )
        if int(number(volume_lane.get("settled"))) >= 30 and number(volume_lane.get("roi_pct")) < 0:
            actions.append(
                f"PAUSE TIPS: Volume 200 remains shadow ({pct(volume_lane.get('roi_pct'))}, "
                f"n={int(number(volume_lane.get('settled')))})"
            )
        if int(number(hard_flip.get("settled", hard_flip.get("bets")))) >= 100 and number(hard_flip.get("roi_pct")) <= 0:
            actions.append("KEEP BLOCKED: broad Hard side flips are negative; scoped Strict rows only")
        for label, cohort in (("Strict gap", strict_gap), ("Volume gap", volume_gap)):
            settled = int(number(cohort.get("settled")))
            roi_pct = number(cohort.get("roi_pct"))
            clv_pct = number(cohort.get("avg_clv_pct"))
            if settled >= 30 and roi_pct > 0:
                actions.append(
                    f"KEEP COLLECTING: {label} is positive but provisional "
                    f"(ROI {pct(roi_pct)}, CLV {pct(clv_pct, 2)}, n={settled}/150)"
                )
        props_settled = int(number(tennis_props_shadow.get("settled")))
        props_roi = number(tennis_props_shadow.get("roi_pct"))
        if props_settled >= 10 and props_roi > 0:
            actions.append(
                f"WATCH ONLY: Aces/DF is promising but far too small "
                f"(ROI {pct(props_roi)}, n={props_settled}/300)"
            )
        goalscorer_ledger = goalscorer.get("ledger") or {}
        if int(number(goalscorer_ledger.get("settled"))) >= 30 and number(goalscorer_ledger.get("roi_pct")) < 0:
            actions.append(
                f"PUBLIC RISK: Goalscorer is research, not a proven edge "
                f"({pct(goalscorer_ledger.get('roi_pct'))}, n={int(number(goalscorer_ledger.get('settled')))})"
            )
        if int(number(api_health.get("archive_rows"))) == 0:
            actions.append("FIX DATA: API-Football agreement archive is empty")
        if int(number(goalkeeper_saves.get("over_lines"))) > 0 and int(number(goalkeeper_saves.get("capture_rows_observed"))) == 0:
            actions.append("FIX CAPTURE: GK prices were discovered but the live capture retained zero rows")
        return actions

    def tennis_lane_line(label: str, key: str, status: str) -> str:
        lane = tennis_lanes.get(key) or {}
        clv = lane.get("clv") or {}
        return (
            f"{label} [{status}]: {lane.get('settled', 0)} settled | "
            f"{number(lane.get('pnl_units')):+.2f}u | ROI {pct(lane.get('roi_pct'))} | "
            f"CLV {pct(clv.get('avg_clv_pct'), 2)} n={clv.get('rows', 0)}"
        )

    def replacement_line(label: str, key: str) -> str:
        if gap_source_status != "OK":
            return f"{label} [0.5u provisional]: SOURCE_MISSING - local prospective evidence unavailable"
        experiment = gap_replacements.get(key) or {}
        performance = experiment.get("performance") or {}
        return (
            f"{label} [0.5u provisional]: {performance.get('settled', 0)}/150 settled | "
            f"{number(performance.get('pnl_units')):+.2f}u | ROI {pct(performance.get('roi_pct'))} | "
            f"CLV {pct(performance.get('avg_clv_pct'), 2)} n={performance.get('clv_rows', 0)} | "
            f"{experiment.get('verdict', 'FORWARD_SAMPLE_BUILDING')}"
        )

    def hard_side_flip_line() -> str:
        hard = side_flip_by_surface.get("Hard") or side_flip_by_surface.get("hard") or {}
        if gap_source_status != "OK":
            return "Hard side-flip evidence [BROAD DIAGNOSTIC]: SOURCE_MISSING"
        return (
            "Hard side-flip evidence [BROAD DIAGNOSTIC]: "
            f"{hard.get('settled', hard.get('bets', 0))} settled | "
            f"{number(hard.get('pnl_units')):+.2f}u | ROI {pct(hard.get('roi_pct'))} | "
            f"CLV {pct(hard.get('avg_clv_pct'), 2)} n={hard.get('clv_rows', 0)} | "
            "not one sellable lane; only scoped Hard/Masters/HIGH <=10pp rows enter Strict"
        )

    def challenger_line() -> str:
        lane = tennis_lanes.get("challenger") or {}
        clv = lane.get("clv") or {}
        return (
            "Challenger ML v2 [ZERO-STAKE SHADOW]: "
            f"{lane.get('settled', 0)} settled | "
            f"CLV {pct(clv.get('avg_clv_pct'), 2)} n={clv.get('rows', 0)} | "
            "promotion requires n>=300, mean CLV>=+1.0%, and verified calibration"
        )
    lines = [
        "Il Margine weekly model evidence",
        f"Generated: {payload['generated_at']}",
        (
            "Tennis prospective evidence source: "
            f"{tennis_evidence_source.get('status', 'SOURCE_MISSING')} "
            f"({tennis_evidence_source.get('source', 'none')}; "
            f"{tennis_evidence_source.get('generated_at') or 'missing'})"
        ),
        (
            "Tennis lane summaries: "
            f"{tennis_lane_source.get('status', 'SOURCE_MISSING')} "
            f"(oldest core generation {tennis_lane_source.get('oldest_generated_at') or 'missing'})"
        ),
        "",
        "ACTION BOARD",
        *[f"- {action}" for action in action_lines()],
        "",
        "EVIDENCE DETAIL",
        f"Team Shots v4: {team_v4.get('prospective_status', 'BLOCKED')} | {team_v4_live.get('settled', 0)} settled | {number(team_v4_live.get('pnl_units')):+.2f}u | ROI {pct(number(team_v4_live.get('roi')) * 100) if team_v4_live.get('roi') is not None else '-'} | CLV {pct(number(team_v4_live.get('mean_true_close_clv')) * 100) if team_v4_live.get('mean_true_close_clv') is not None else '-'} | promotion {team_v4.get('promotion_gate', 'BLOCKED')}",
        f"Team Shots v4 warm-up [TRACK ONLY]: {team_v4_warmup.get('settled', 0)}/{team_v4_warmup.get('signals', 0)} settled | {number(team_v4_warmup.get('pnl_units')):+.2f}u | ROI {pct(number(team_v4_warmup.get('roi')) * 100) if team_v4_warmup.get('roi') is not None else '-'} | pending {team_v4_warmup.get('pending', 0)}",
        f"Team Shots scan: {team_v4_scan.get('state', 'NOT_RUN')} | scored {team_v4_scan.get('scored_rows', 0)} rows/{team_v4_scan.get('scored_fixtures', 0)} fixtures | edge-pass warmup blocks {team_v4_scan.get('edge_pass_but_warmup_blocked_fixtures', 0)}",
        f"Corners v3: {corners_v3.get('prospective_status', 'BLOCKED')} | {corners_v3_live.get('settled', 0)} settled | {number(corners_v3_live.get('pnl_units')):+.2f}u | ROI {pct(number(corners_v3_live.get('roi')) * 100) if corners_v3_live.get('roi') is not None else '-'} | CLV {pct(number(corners_v3_live.get('mean_true_close_clv')) * 100) if corners_v3_live.get('mean_true_close_clv') is not None else '-'} | promotion {corners_v3.get('promotion_gate', 'BLOCKED')}",
        f"Corners v3 warm-up [TRACK ONLY]: {corners_v3_warmup.get('settled', 0)}/{corners_v3_warmup.get('signals', 0)} settled | {number(corners_v3_warmup.get('pnl_units')):+.2f}u | ROI {pct(number(corners_v3_warmup.get('roi')) * 100) if corners_v3_warmup.get('roi') is not None else '-'} | pending {corners_v3_warmup.get('pending', 0)}",
        f"Corners scan: {corners_v3_scan.get('state', 'NOT_RUN')} | scored {corners_v3_scan.get('scored_rows', 0)} rows/{corners_v3_scan.get('scored_fixtures', 0)} fixtures | edge-pass warmup blocks {corners_v3_scan.get('edge_pass_but_warmup_blocked_fixtures', 0)}",
        f"Corners v4 G0 [RESEARCH]: {corners_v4_g0.get('decision', 'NOT_RUN')} | MAE delta {signed_number(corners_v4_g0.get('mae_delta'), 4)} | market Brier delta {signed_number(corners_v4_g0.get('brier_delta'), 4)} n={corners_v4_g0.get('market_rows', 0)} | line gates {corners_v4_g0.get('passed_lines', 0)}/{corners_v4_g0.get('available_lines', 0)}",
        f"Legacy controls: Team Shots V3 {team_clv['settled']} settled/{team_clv['pnl_units']:+.2f}u; Corners V0 {corners_clv['settled']} settled/{corners_clv['pnl_units']:+.2f}u",
        f"Count-source health: API-Football {api_health.get('archive_rows', 0)} archived, latest {api_health.get('latest_fixture_date') or '-'}, agreement {api_agreement.get('matched_fixtures', 0)}/{api_agreement.get('api_rows', 0)}",
        f"Team Fouls: F1 {team_fouls_decision.get('status', 'NOT_RUN')}; F2 {team_fouls_f2_decision.get('status', 'NOT_RUN')}; sources {team_fouls_m2.get('status', 'NOT_RUN')}; no signals",
        f"GK Saves v1: count {goalkeeper_saves.get('count_gate', 'NOT_RUN')} n={goalkeeper_saves.get('historical_observations', 0)} | discovery {goalkeeper_saves.get('market_status', 'NOT_RUN')} ({goalkeeper_saves.get('over_lines', 0)} probe Over lines) | capture {goalkeeper_saves.get('capture_status', 'NOT_RUN')} events={goalkeeper_saves.get('capture_events_selected', 0)} rows={goalkeeper_saves.get('capture_rows_observed', 0)} 1X2={goalkeeper_saves.get('capture_three_way_events', 0)} | prospective {goalkeeper_saves.get('prospective_status', 'BLOCKED')} priced={goalkeeper_saves.get('priced_lines', 0)} eligible={goalkeeper_saves.get('eligible_lines', 0)} provisional={goalkeeper_saves.get('provisional_lines', 0)} signals={goalkeeper_saves.get('signals', 0)} settled={goalkeeper_saves.get('settled', 0)} blockers={goalkeeper_saves.get('blocker_counts', {})} ROI={ratio_pct(goalkeeper_saves.get('roi'))} CLV={ratio_pct(goalkeeper_saves.get('clv'))} n={goalkeeper_saves.get('clv_matched', 0)} | promotion BLOCKED",
        f"Goalscorer V2: {goalscorer['ledger']['settled']} settled | {goalscorer['ledger']['pnl_units']:+.2f}u | ROI {pct(goalscorer['ledger']['roi_pct'])} | CLV {goalscorer['matched_closes']}/{goalscorer['signals']} | PUBLIC RESEARCH ONLY",
        f"Goalscorer beta vs raw n={goalscorer['calibration']['n']}: Brier {fixed(goalscorer['calibration']['raw_brier'])}->{fixed(goalscorer['calibration']['beta_brier'])} ({fixed(goalscorer['calibration']['brier_delta'])}) | ECE {ratio_pct(goalscorer['calibration']['raw_ece'], 2)}->{ratio_pct(goalscorer['calibration']['beta_ece'], 2)} | folds {goalscorer['beta_fold_wins']}/{goalscorer['beta_folds']}",
        f"Goalscorer gaps [ZERO-STAKE]: {goalscorer['extreme_gap_quarantine']['settled']}/{goalscorer['extreme_gap_quarantine']['registered']} settled | {goalscorer['extreme_gap_quarantine']['pnl_units']:+.2f}u | ROI {pct(goalscorer['extreme_gap_quarantine']['roi_pct'])} | weekly verdict {goalscorer['decision']} | blockers {', '.join(goalscorer['blockers']) or 'none'}",
        f"Assist V1: {assist['lane_status']} | backtest {assist['backtest_status']} | settlement {assist['settlement_status']} | market {assist['market_status']} ({assist['market_calendar_span_days']}/90d) | prospective {assist['prospective']['settled']}/{assist['prospective_target']} | <=30 API calls/week | {assist['decision']}",
        f"Automation: {automation.get('status', 'NOT_RUN')} | Odds-API worst hour {odds_budget.get('max_requests_in_one_hour', '-')}/{odds_budget.get('requests_per_hour', '-')} | DB writes/week max {(automation.get('database') or {}).get('registered_writes_per_week_max', '-')}",
        tennis_lane_line("Tennis Strict", "strict", "CORE"),
        tennis_lane_line("Tennis Volume 200", "volume_200", "SHADOW / DO NOT BET"),
        tennis_lane_line("Tennis Spread v1", "spread_v1", "PAUSED/RESEARCH"),
        replacement_line("Strict gap 10-20pp", "strict_gap_10_20_same_side"),
        replacement_line("Volume gap 10-15pp", "volume200_gap_10_15_same_side"),
        hard_side_flip_line(),
        challenger_line(),
        (
            "Inactive tennis research (not tips): "
            + "; ".join(
                f"{label} n={int(number((tennis_lanes.get(key) or {}).get('settled')))} "
                f"ROI={pct((tennis_lanes.get(key) or {}).get('roi_pct'))}"
                for label, key in (
                    ("Grass", "grass_bo3"),
                    ("Clay", "clay_bo3"),
                    ("CPI", "cpi_speed"),
                )
            )
        ),
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
    lines.append(
        "Venue ace v1 [SHADOW]: "
        + ("SOURCE_MISSING" if tennis_venue_ace_v1.get("status") == "SOURCE_MISSING" else
        f"venues {tennis_venue_ace_v1.get('eligible_venues', 0)}/"
        f"{tennis_venue_ace_v1.get('total_venues', 0)} | "
        f"{tennis_venue_ace_v1.get('settled', 0)}/"
        f"{tennis_venue_ace_v1.get('promotion_target_rows', 600)} settled | "
        f"ROI {pct(tennis_venue_ace_v1.get('roi_pct'))} | "
        f"CLV {pct(tennis_venue_ace_v1.get('mean_clv_pct'), 2)} "
        f"n={tennis_venue_ace_v1.get('clv_rows', 0)} | "
        f"Brier delta {number(tennis_venue_ace_v1.get('brier_delta')):+.4f} "
        f"n={tennis_venue_ace_v1.get('paired_rows', 0)} | NOT SELLABLE")
    )
    lines.append(
        "Tennis props vs Bet365: "
        + ("SOURCE_MISSING" if tennis_props_benchmark.get("status") == "SOURCE_MISSING" else
        f"{tennis_props_benchmark.get('settled', 0)}/{tennis_props_benchmark.get('observations', 0)} settled, "
        f"Brier delta {number(tennis_props_benchmark.get('brier_delta_vs_market')):+.4f}, "
        f"{tennis_props_benchmark.get('status', 'EVIDENCE_BUILDING')}")
    )
    props_clv = tennis_props_shadow.get("clv") or {}
    props_calibration = tennis_props_shadow.get("calibration") or {}
    lines.append(
        "Aces/DF: "
        f"{tennis_props_shadow.get('settled', 0)}/{tennis_props_shadow.get('registered', 0)} | "
        f"P{tennis_props_shadow.get('pending', 0)} "
        f"(D{tennis_props_shadow.get('pending_due', 0)}/"
        f"F{tennis_props_shadow.get('pending_future', 0)}/"
        f"U{tennis_props_shadow.get('pending_unknown', 0)}) | "
        f"{number(tennis_props_shadow.get('pnl_units')):+.2f}u | "
        f"ROI {pct(tennis_props_shadow.get('roi_pct'))} | "
        f"CLV {pct(props_clv.get('mean_pct'), 2)} n={props_clv.get('rows', 0)} | "
        f"Brier {props_calibration.get('brier') if props_calibration.get('brier') is not None else '-'} "
        f"n={props_calibration.get('rows', 0)}"
    )
    lines.append(tennis_breaks_gate_line(tennis_breaks_v1))
    lines.extend(
        [
            "",
            "Read: all promotion gates remain fail-closed. No weekly report changes routing or stakes.",
        ]
    )
    return "\n".join(lines)


def tennis_telegram_text(payload: dict[str, Any]) -> str:
    evidence = payload.get("tennis_model_evidence") or {}
    tennis_breaks_v1 = payload.get("tennis_breaks_v1") or {}
    lanes = evidence.get("lanes") or {}
    replacements = evidence.get("gap_replacements") or {}
    props_v3 = payload.get("tennis_props_v3") or {}
    props_v4 = payload.get("tennis_props_v4") or {}
    venue_ace_v1 = payload.get("tennis_venue_ace_factor_v1") or {}
    most_aces = payload.get("tennis_most_aces_forecast") or {}
    most_aces_prices = payload.get("tennis_most_aces_prices") or {}
    props_benchmark = payload.get("tennis_props_market_benchmark") or {}
    props_shadow = payload.get("tennis_props_shadow_decision") or {}
    source = payload.get("tennis_evidence_source") or {}
    lane_source = evidence.get("lane_source") or {}
    gap_source_status = evidence.get("gap_source_status", "SOURCE_MISSING")
    side_flip_by_surface = evidence.get("side_flip_by_surface") or {}

    def lane_line(label: str, key: str, status: str) -> str:
        lane = lanes.get(key) or {}
        clv = lane.get("clv") or {}
        return (
            f"{label} [{status}]: {lane.get('settled', 0)} settled | "
            f"{number(lane.get('pnl_units')):+.2f}u | ROI {pct(lane.get('roi_pct'))} | "
            f"CLV {pct(clv.get('avg_clv_pct'), 2)} n={clv.get('rows', 0)}"
        )

    def replacement_line(label: str, key: str) -> str:
        if gap_source_status != "OK":
            return f"{label} [0.5u provisional]: SOURCE_MISSING - local prospective evidence unavailable"
        experiment = replacements.get(key) or {}
        performance = experiment.get("performance") or {}
        return (
            f"{label} [0.5u provisional]: {performance.get('settled', 0)}/150 settled | "
            f"{number(performance.get('pnl_units')):+.2f}u | ROI {pct(performance.get('roi_pct'))} | "
            f"CLV {pct(performance.get('avg_clv_pct'), 2)} n={performance.get('clv_rows', 0)} | "
            f"{experiment.get('verdict', 'FORWARD_SAMPLE_BUILDING')}"
        )

    def hard_side_flip_line() -> str:
        hard = side_flip_by_surface.get("Hard") or side_flip_by_surface.get("hard") or {}
        if gap_source_status != "OK":
            return "Hard side-flip evidence [BROAD DIAGNOSTIC]: SOURCE_MISSING"
        return (
            "Hard side-flip evidence [BROAD DIAGNOSTIC]: "
            f"{hard.get('settled', hard.get('bets', 0))} settled | "
            f"{number(hard.get('pnl_units')):+.2f}u | ROI {pct(hard.get('roi_pct'))} | "
            f"CLV {pct(hard.get('avg_clv_pct'), 2)} n={hard.get('clv_rows', 0)} | "
            "only scoped Masters/HIGH <=10pp rows are Strict"
        )

    def challenger_line() -> str:
        lane = lanes.get("challenger") or {}
        clv = lane.get("clv") or {}
        return (
            "Challenger ML v2 [ZERO-STAKE SHADOW]: "
            f"{lane.get('settled', 0)} settled | "
            f"CLV {pct(clv.get('avg_clv_pct'), 2)} n={clv.get('rows', 0)} | "
            "gate n>=300 / CLV>=+1.0% / calibration pass"
        )

    lines = [
        "Il Margine weekly tennis evidence",
        f"Generated: {payload['generated_at']}",
        (
            "Prospective evidence source: "
            f"{source.get('status', 'SOURCE_MISSING')} "
            f"({source.get('source', 'none')}; {source.get('generated_at') or 'missing'})"
        ),
        (
            "Lane summaries: "
            f"{lane_source.get('status', 'SOURCE_MISSING')} "
            f"(oldest core generation {lane_source.get('oldest_generated_at') or 'missing'})"
        ),
        "",
        lane_line("Strict", "strict", "CORE"),
        lane_line("Volume 200", "volume_200", "SHADOW / DO NOT BET"),
        lane_line("Spread v1", "spread_v1", "PAUSED/RESEARCH"),
        replacement_line("Strict gap 10-20pp", "strict_gap_10_20_same_side"),
        replacement_line("Volume gap 10-15pp", "volume200_gap_10_15_same_side"),
        hard_side_flip_line(),
        challenger_line(),
        (
            "Inactive research (not tips): "
            + "; ".join(
                f"{label} n={int(number((lanes.get(key) or {}).get('settled')))} "
                f"ROI={pct((lanes.get(key) or {}).get('roi_pct'))}"
                for label, key in (
                    ("Grass", "grass_bo3"),
                    ("Clay", "clay_bo3"),
                    ("CPI", "cpi_speed"),
                )
            )
        ),
    ]
    if props_v3 and not props_v3.get("_error"):
        atp = props_v3.get("atp") or {}
        proof = props_v3.get("evidence") or {}
        lines.append(
            "Aces/DF v3: "
            f"{proof.get('settled', 0)} settled | ROI {number(proof.get('roi_pct')):+.2f}% | "
            f"CLV {number(proof.get('mean_clv_pct')):+.2f}% | {atp.get('status', 'UNKNOWN')}"
        )
    if props_v4 and not props_v4.get("_error"):
        lines.append(
            "Aces Over v4 [PRE_FIT]: "
            f"{props_v4.get('rows_settled', 0)}/{props_v4.get('minimum_prefit_settled', 200)} settled | "
            f"{props_v4.get('rows_registered', 0)} registered | "
            f"CLV {number(props_v4.get('clv_mean_pct')):+.2f}% "
            f"n={props_v4.get('clv_coverage', 0)} | no tips before gate"
        )
    lines.append(
        "Venue ace v1 [SHADOW]: "
        f"venues {venue_ace_v1.get('eligible_venues', 0)}/"
        f"{venue_ace_v1.get('total_venues', 0)} | "
        f"{venue_ace_v1.get('settled', 0)}/"
        f"{venue_ace_v1.get('promotion_target_rows', 600)} settled | "
        f"events {venue_ace_v1.get('distinct_events', 0)}/"
        f"{venue_ace_v1.get('promotion_target_events', 150)} | "
        f"ROI {pct(venue_ace_v1.get('roi_pct'))} | "
        f"CLV {pct(venue_ace_v1.get('mean_clv_pct'), 2)} | "
        f"Brier delta {number(venue_ace_v1.get('brier_delta')):+.4f} "
        f"n={venue_ace_v1.get('paired_rows', 0)} | NOT SELLABLE"
    )
    if most_aces and not most_aces.get("_error"):
        models = most_aces.get("models") or {}
        paired = most_aces.get("paired_comparison") or {}
        a0_model = paired.get("control_model")
        if not a0_model or a0_model not in models:
            a0_candidates = [
                (name, summary)
                for name, summary in models.items()
                if str(name).startswith("v3_aces_gaussian")
            ]
            a0_model = (
                TENNIS_MOST_ACES_A0_MODEL
                if TENNIS_MOST_ACES_A0_MODEL in models
                else (
                    max(
                        a0_candidates,
                        key=lambda item: int(number(item[1].get("rows_registered"))),
                    )[0]
                    if a0_candidates
                    else ""
                )
            )
        a0 = models.get(a0_model) or {}
        direct = models.get(TENNIS_MOST_ACES_DIRECT_MODEL) or {}
        paired_events = int(number(paired.get("paired_events")))
        fallback_stage, fallback_next_review = most_aces_review_stage(paired_events)
        review_stage = paired.get("review_stage") or fallback_stage
        next_review_at = (
            paired.get("next_review_at")
            if "next_review_at" in paired
            else fallback_next_review
        )

        def model_metric(model: dict[str, Any], key: str) -> str:
            value = model.get(key)
            return "-" if value is None else f"{number(value):.4f}"

        lines.extend(
            [
                (
                    "Most Aces A0 [outcome only]: "
                    f"{a0.get('rows_settled', 0)}/{a0.get('rows_registered', 0)} settled | "
                    f"Brier {model_metric(a0, 'brier')} | logloss {model_metric(a0, 'logloss')}"
                ),
                (
                    "Most Aces Direct [prospective shadow]: "
                    f"{direct.get('rows_settled', 0)}/{direct.get('rows_registered', 0)} settled | "
                    f"Brier {model_metric(direct, 'brier')} | logloss {model_metric(direct, 'logloss')}"
                ),
                (
                    "Direct vs A0 paired: "
                    f"n={paired_events}/200 | "
                    f"Brier delta {model_metric(paired, 'brier_delta_direct_minus_control')} | "
                    f"logloss delta {model_metric(paired, 'logloss_delta_direct_minus_control')} | "
                    f"{review_stage}"
                    + (
                        f" (next {next_review_at})"
                        if next_review_at
                        else " (review due)"
                    )
                ),
                "Paired A0/Direct forecast comparison is outcome-only; price evidence is separate below.",
            ]
        )
        direct_prices = most_aces_prices.get(TENNIS_MOST_ACES_DIRECT_MODEL) or {}
        lines.append(
            "Most Aces Direct vs BetMGM: "
            f"{direct_prices.get('eligible_settled', 0)} eligible settled | "
            f"{number(direct_prices.get('pnl_units')):+.2f}u | "
            f"ROI {pct(direct_prices.get('roi_pct'))} | "
            f"CLV {pct(direct_prices.get('mean_clv_pct'), 2)} "
            f"n={direct_prices.get('clv_rows', 0)} | shadow only"
        )
    shadow_clv = props_shadow.get("clv") or {}
    shadow_calibration = props_shadow.get("calibration") or {}
    lines.extend(
        [
            (
                "Aces/DF canonical shadow: "
                f"{props_shadow.get('settled', 0)}/{props_shadow.get('registered', 0)} settled | "
                f"{number(props_shadow.get('pnl_units')):+.2f}u | "
                f"ROI {pct(props_shadow.get('roi_pct'))} | "
                f"CLV {pct(shadow_clv.get('mean_pct'), 2)} "
                f"({shadow_clv.get('positive_pct') if shadow_clv.get('positive_pct') is not None else '-'}% positive, n={shadow_clv.get('rows', 0)}) | "
                f"{props_shadow.get('status', 'COLLECTING_EVIDENCE')}"
            ),
            (
                "Aces/DF calibration: "
                f"Brier {shadow_calibration.get('brier') if shadow_calibration.get('brier') is not None else '-'} | "
                f"gap {shadow_calibration.get('absolute_gap_pp') if shadow_calibration.get('absolute_gap_pp') is not None else '-'}pp | "
                f"n={shadow_calibration.get('rows', 0)}"
            ),
            "Aces/DF blockers: " + ("; ".join(props_shadow.get("blockers") or []) or "none"),
            (
                "Aces/DF promotion gate: 300 settled across 2 Slams; ROI >= 0; "
                "mean CLV >= +1% and >=55% positive; calibration n>=100, "
                "Brier <=0.25 and gap <=5pp; approved prices + healthy pipeline. Human review only."
            ),
        ]
    )
    lines.extend(
        [
            (
                "Aces/DF vs Bet365: "
                f"{props_benchmark.get('settled', 0)}/{props_benchmark.get('observations', 0)} settled | "
                f"Brier delta {number(props_benchmark.get('brier_delta_vs_market')):+.4f} | "
                f"{props_benchmark.get('status', 'EVIDENCE_BUILDING')}"
            ),
            tennis_breaks_gate_line(tennis_breaks_v1),
            "",
            "No automatic promotion: provisional lanes remain 0.5u until their registered gates pass.",
        ]
    )
    return "\n".join(lines)


def github_token_from_credential_manager() -> str:
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        token = os.environ.get(name, "").strip()
        if token:
            return token

    errors: list[str] = []
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        token = result.stdout.strip()
        if result.returncode == 0 and token:
            return token
        errors.append(f"gh auth token exit {result.returncode}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        errors.append(f"gh auth token: {type(exc).__name__}")

    try:
        result = subprocess.run(
            ["git", "credential-manager", "get"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        fields: dict[str, str] = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                fields[key.strip()] = value.strip()
        token = fields.get("password", "")
        if result.returncode == 0 and token:
            return token
        errors.append(f"credential-manager exit {result.returncode}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        errors.append(f"credential-manager: {type(exc).__name__}")

    raise RuntimeError("GitHub authentication unavailable (" + "; ".join(errors) + ")")


def dispatch_telegram_relay(message: str) -> None:
    encoded = base64.b64encode(
        json.dumps([message], ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    repository = os.environ.get("TENNIS_DIGEST_GITHUB_REPOSITORY", TELEGRAM_RELAY_REPOSITORY)
    ref = os.environ.get("TENNIS_DIGEST_GITHUB_REF", "golden-with-speed-insights")
    payload = json.dumps({"ref": ref, "inputs": {"payload_b64": encoded}}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/actions/workflows/{TELEGRAM_RELAY_WORKFLOW}/dispatches",
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token_from_credential_manager()}",
            "Content-Type": "application/json",
            "User-Agent": "il-margine-weekly-report",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def post_telegram(message: str) -> bool:
    token = os.environ.get("OPS_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("OPS_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        try:
            dispatch_telegram_relay(message)
            print("WEEKLY_REPORT_TELEGRAM relay dispatched")
            return True
        except Exception as exc:
            print(f"Warning: telegram relay dispatch failed: {exc}", file=sys.stderr)
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
    parser.add_argument("--tennis-only-telegram", action="store_true")
    args = parser.parse_args()

    load_env_files()
    payload = build_payload()
    report = render_report(payload)
    tennis_props_decision = payload["tennis_props_shadow_decision"]

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    TENNIS_PROPS_DECISION_JSON.parent.mkdir(parents=True, exist_ok=True)
    TENNIS_PROPS_DECISION_JSON.write_text(
        json.dumps(tennis_props_decision, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    TENNIS_PROPS_DECISION_REPORT.write_text(
        tennis_props_shadow_decision_report(tennis_props_decision) + "\n",
        encoding="utf-8",
    )

    print(report)
    print(f"Wrote {display_path(args.json)}")
    print(f"Wrote {display_path(args.report)}")
    print(f"Wrote {display_path(TENNIS_PROPS_DECISION_JSON)}")
    print(f"Wrote {display_path(TENNIS_PROPS_DECISION_REPORT)}")

    if not args.no_telegram:
        message = tennis_telegram_text(payload) if args.tennis_only_telegram else telegram_text(payload)
        post_telegram(message)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
