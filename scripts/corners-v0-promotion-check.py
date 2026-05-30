#!/usr/bin/env python3
"""Promotion gate report for canonical corners v0.

This reads the canonical football-form backtest summary and checks the exact
research-lane gates we agreed to use before publishing corners v0:

- common-sample count MAE must beat current by league;
- common-sample Brier/log-loss must beat current by league and line;
- last-90 common-sample must pass the same checks;
- canonical-only publication stays hard-blocked until there is evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = ROOT / "data" / "football-form" / "canonical-backtest-summary.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "corners-v0-promotion-check.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "corners-v0-promotion-check.md"
DEFAULT_ALLOWED_CONFIG = ROOT / "data" / "football-form" / "corners-v0-allowed-leagues.json"
DEFAULT_REAL_ODDS_RESULTS = ROOT / "data" / "corners-ou" / "corners-real-odds-backtest-results.csv"

CORNERS_LINES = ["8.5", "9.5", "10.5", "11.5"]
MIN_CANONICAL_ONLY_N = 200
MIN_LAST90_LEAGUE_N = 50
REAL_ODDS_MODEL_VERSION = "nb_market_blend"
REAL_ODDS_MIN_N = 200
REAL_ODDS_MIN_AVG_CLV = 0.01
REAL_ODDS_MIN_POSITIVE_CLV_SHARE = 0.55
REAL_ODDS_MIN_QUALIFIED_LEAGUES = 3
REAL_ODDS_MIN_LEAGUE_N = 40


def pf(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        if path != DEFAULT_SUMMARY:
            raise SystemExit(f"Missing backtest summary: {path}")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "backtest-football-form-layer.py")], check=True)
    if not path.exists():
        raise SystemExit(f"Backtest did not create expected summary: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def find_row(
    rows: list[dict[str, str]],
    *,
    model: str,
    sample: str,
    league: str,
    line: str,
) -> dict[str, str] | None:
    for row in rows:
        if (
            row.get("market") == "corners_total"
            and row.get("model") == model
            and row.get("sample") == sample
            and row.get("league") == league
            and row.get("line") == line
        ):
            return row
    return None


def probability_gate(
    rows: list[dict[str, str]],
    *,
    sample: str,
    league: str,
) -> dict[str, Any]:
    line_results: list[dict[str, Any]] = []
    brier_ok = True
    log_loss_ok = True
    for line in CORNERS_LINES:
        canonical = find_row(rows, model="canonical_form_v0", sample=sample, league=league, line=line)
        current = find_row(rows, model="current", sample=sample, league=league, line=line)
        canonical_brier = pf(canonical.get("brier") if canonical else None)
        current_brier = pf(current.get("brier") if current else None)
        canonical_loss = pf(canonical.get("log_loss") if canonical else None)
        current_loss = pf(current.get("log_loss") if current else None)
        line_brier_ok = canonical_brier is not None and current_brier is not None and canonical_brier <= current_brier
        line_loss_ok = canonical_loss is not None and current_loss is not None and canonical_loss <= current_loss
        brier_ok = brier_ok and line_brier_ok
        log_loss_ok = log_loss_ok and line_loss_ok
        line_results.append(
            {
                "line": line,
                "canonical_brier": canonical_brier,
                "current_brier": current_brier,
                "brier_ok": line_brier_ok,
                "canonical_log_loss": canonical_loss,
                "current_log_loss": current_loss,
                "log_loss_ok": line_loss_ok,
            }
        )
    return {"brier_ok": brier_ok, "log_loss_ok": log_loss_ok, "lines": line_results}


def count_gate(
    rows: list[dict[str, str]],
    *,
    sample: str,
    league: str,
) -> dict[str, Any]:
    canonical = find_row(rows, model="canonical_form_v0", sample=sample, league=league, line="count")
    current = find_row(rows, model="current", sample=sample, league=league, line="count")
    canonical_mae = pf(canonical.get("mae") if canonical else None)
    current_mae = pf(current.get("mae") if current else None)
    n = int(pf(canonical.get("n") if canonical else None) or 0)
    return {
        "n": n,
        "canonical_mae": canonical_mae,
        "current_mae": current_mae,
        "mae_delta": (canonical_mae - current_mae) if canonical_mae is not None and current_mae is not None else None,
        "count_ok": canonical_mae is not None and current_mae is not None and canonical_mae <= current_mae,
    }


def evaluate_league(rows: list[dict[str, str]], league: str) -> dict[str, Any]:
    common_count = count_gate(rows, sample="common", league=league)
    common_prob = probability_gate(rows, sample="common", league=league)
    recent_count = count_gate(rows, sample="last_90_common", league=league)
    recent_prob = probability_gate(rows, sample="last_90_common", league=league)
    recent_n_ok = recent_count["n"] >= MIN_LAST90_LEAGUE_N
    return {
        "league": league,
        "common": {**common_count, **common_prob},
        "last_90_common": {**recent_count, **recent_prob, "n_ok": recent_n_ok},
        "passes": (
            common_count["count_ok"]
            and common_prob["brier_ok"]
            and common_prob["log_loss_ok"]
            and recent_n_ok
            and recent_count["count_ok"]
            and recent_prob["brier_ok"]
            and recent_prob["log_loss_ok"]
        ),
    }



def pb(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def load_real_odds_gate(path: Path) -> dict[str, Any]:
    rows = load_rows(path) if path.exists() else []
    selected = [
        row
        for row in rows
        if row.get("model_version") == REAL_ODDS_MODEL_VERSION
        and pb(row.get("selected"))
        and not pb(row.get("close_is_stale"))
    ]
    n = len(selected)
    pnl = sum(pf(row.get("pnl_units")) or 0.0 for row in selected)
    roi = pnl / n if n else None
    clvs = [x for x in (pf(row.get("published_to_close_clv")) for row in selected) if x is not None]
    avg_clv = avg(clvs)
    positive_clv_n = sum(1 for row in selected if pb(row.get("positive_clv")))
    positive_clv_share = positive_clv_n / n if n else None
    by_league: list[dict[str, Any]] = []
    for league in sorted({str(row.get("league") or "").strip().lower() for row in selected if row.get("league")}):
        sample = [row for row in selected if str(row.get("league") or "").strip().lower() == league]
        league_clvs = [x for x in (pf(row.get("published_to_close_clv")) for row in sample) if x is not None]
        league_avg_clv = avg(league_clvs)
        league_pnl = sum(pf(row.get("pnl_units")) or 0.0 for row in sample)
        by_league.append(
            {
                "league": league,
                "n": len(sample),
                "pnl_units": league_pnl,
                "roi": league_pnl / len(sample) if sample else None,
                "avg_clv": league_avg_clv,
                "positive_clv_share": sum(1 for row in sample if pb(row.get("positive_clv"))) / len(sample) if sample else None,
                "qualified_for_breadth": len(sample) >= REAL_ODDS_MIN_LEAGUE_N,
                "clv_positive": league_avg_clv is not None and league_avg_clv > 0.0,
            }
        )
    qualified_positive_leagues = [row["league"] for row in by_league if row["qualified_for_breadth"] and row["clv_positive"]]
    gates = {
        "n": n >= REAL_ODDS_MIN_N,
        "avg_clv": avg_clv is not None and avg_clv >= REAL_ODDS_MIN_AVG_CLV,
        "positive_clv_share": positive_clv_share is not None and positive_clv_share >= REAL_ODDS_MIN_POSITIVE_CLV_SHARE,
        "roi": roi is not None and roi >= 0.0,
        "league_breadth": len(qualified_positive_leagues) >= REAL_ODDS_MIN_QUALIFIED_LEAGUES,
    }
    return {
        "source": str(path.relative_to(ROOT)).replace("\\", "/"),
        "model_version": REAL_ODDS_MODEL_VERSION,
        "selected_filter": "selected=true and close_is_stale=false",
        "thresholds": {
            "min_n": REAL_ODDS_MIN_N,
            "min_avg_clv": REAL_ODDS_MIN_AVG_CLV,
            "min_positive_clv_share": REAL_ODDS_MIN_POSITIVE_CLV_SHARE,
            "min_qualified_leagues": REAL_ODDS_MIN_QUALIFIED_LEAGUES,
            "min_league_n": REAL_ODDS_MIN_LEAGUE_N,
        },
        "n": n,
        "pnl_units": pnl,
        "roi": roi,
        "avg_clv": avg_clv,
        "positive_clv_share": positive_clv_share,
        "positive_clv_n": positive_clv_n,
        "qualified_positive_leagues": qualified_positive_leagues,
        "by_league": by_league,
        "gates": gates,
        "overall_pass": bool(selected) and all(gates.values()),
        "reason": "pass" if bool(selected) and all(gates.values()) else "real-odds CLV gate failed; corners remains research-only",
    }

def build_payload(rows: list[dict[str, str]], real_odds_results_path: Path = DEFAULT_REAL_ODDS_RESULTS) -> dict[str, Any]:
    leagues = sorted(
        {
            row.get("league", "")
            for row in rows
            if row.get("market") == "corners_total"
            and row.get("sample") == "common"
            and row.get("line") == "count"
            and row.get("league") not in {"", "ALL"}
        }
    )
    league_results = [evaluate_league(rows, league) for league in leagues]
    canonical_only = find_row(rows, model="canonical_form_v0", sample="canonical_only", league="ALL", line="count")
    canonical_only_n = int(pf(canonical_only.get("n") if canonical_only else None) or 0)
    canonical_only_guard = canonical_only_n < MIN_CANONICAL_ONLY_N
    ready_leagues = [item["league"] for item in league_results if item["passes"]]
    blocked_leagues = [item["league"] for item in league_results if not item["passes"]]
    real_odds_gate = load_real_odds_gate(real_odds_results_path)
    real_odds_pass = bool(real_odds_gate.get("overall_pass"))
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": str(DEFAULT_SUMMARY.relative_to(ROOT)).replace("\\", "/"),
        "policy": {
            "model": "canonical_form_v0",
            "market": "corners_total",
            "promotion_lane": "research",
            "min_canonical_only_n": MIN_CANONICAL_ONLY_N,
            "min_last90_league_n": MIN_LAST90_LEAGUE_N,
            "real_odds_gate_required": True,
        },
        "league_results": league_results,
        "canonical_only": {
            "n": canonical_only_n,
            "hard_block": canonical_only_guard,
            "reason": (
                f"canonical-only N={canonical_only_n} < {MIN_CANONICAL_ONLY_N}; do not publish picks where current model was historically silent"
                if canonical_only_guard
                else "canonical-only sample size threshold met; still require segment calibration before allowing publication"
            ),
        },
        "ready_leagues": ready_leagues if real_odds_pass else [],
        "blocked_leagues": sorted(set(blocked_leagues) | (set(ready_leagues) if not real_odds_pass else set())),
        "count_calibration_ready_leagues": ready_leagues,
        "real_odds_gate": real_odds_gate,
        "research_lane_ready_all_leagues": real_odds_pass and all(item["passes"] for item in league_results) and canonical_only_guard,
        "research_lane_ready_partial": real_odds_pass and bool(ready_leagues) and canonical_only_guard,
    }


def build_allowed_config(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": payload["generated_at"],
        "model": "canonical_form_v0",
        "market": "corners_total",
        "lane": "research",
        "allowed_leagues": payload.get("ready_leagues", []),
        "blocked_leagues": payload.get("blocked_leagues", []),
        "canonical_only_allowed": False,
        "canonical_only_min_n": MIN_CANONICAL_ONLY_N,
        "rules": [
            "publish only if league is in allowed_leagues",
            "publish only if current_model_would_have_priced is true",
            "do not publish canonical-only fixtures until canonical-only sample and segment calibration pass",
            "do not publish any corners league unless the real-odds Pinnacle CLV gate passes",
        ],
    }


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Corners V0 Promotion Check",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "This is a research-lane gate only. It does not change live picks.",
        "",
        f"Research lane ready across all leagues with hard canonical-only cutoff: **{'yes' if payload['research_lane_ready_all_leagues'] else 'no'}**",
        f"Research lane ready for passing leagues only: **{'yes' if payload['research_lane_ready_partial'] else 'no'}**",
        f"Passing leagues: `{', '.join(payload['ready_leagues']) or '-'}`",
        f"Blocked leagues: `{', '.join(payload['blocked_leagues']) or '-'}`",
        "",
        "## Real-Odds Gate",
        "",
        f"- Source: `{payload['real_odds_gate']['source']}`",
        f"- Model: `{payload['real_odds_gate']['model_version']}`",
        f"- Selected fresh-close bets: `{payload['real_odds_gate']['n']}` / required `{payload['real_odds_gate']['thresholds']['min_n']}`",
        f"- ROI: `{fmt((payload['real_odds_gate']['roi'] or 0) * 100, 2)}%` / required `>= 0.00%`",
        f"- Mean CLV: `{fmt((payload['real_odds_gate']['avg_clv'] or 0) * 100, 2)}%` / required `>= {fmt(payload['real_odds_gate']['thresholds']['min_avg_clv'] * 100, 2)}%`",
        f"- Positive CLV share: `{fmt((payload['real_odds_gate']['positive_clv_share'] or 0) * 100, 1)}%` / required `>= {fmt(payload['real_odds_gate']['thresholds']['min_positive_clv_share'] * 100, 1)}%`",
        f"- Qualified positive leagues: `{', '.join(payload['real_odds_gate']['qualified_positive_leagues']) or '-'}` / required `{payload['real_odds_gate']['thresholds']['min_qualified_leagues']}`",
        f"- Overall pass: **{'yes' if payload['real_odds_gate']['overall_pass'] else 'no'}**",
        f"- Reason: {payload['real_odds_gate']['reason']}",
        "",
        "## Per-League Count/Calibration Gates",
        "",
        "| League | Common N | Current MAE | V0 MAE | Count | Brier | Log-loss | Last90 N | Last90 Current MAE | Last90 V0 MAE | Last90 Count | Last90 Brier | Last90 Log-loss |",
        "| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for item in payload["league_results"]:
        common = item["common"]
        recent = item["last_90_common"]
        lines.append(
            "| {league} | {common_n} | {common_current} | {common_v0} | {common_count} | {common_brier} | {common_loss} | "
            "{recent_n} | {recent_current} | {recent_v0} | {recent_count} | {recent_brier} | {recent_loss} |".format(
                league=item["league"],
                common_n=common["n"],
                common_current=fmt(common["current_mae"]),
                common_v0=fmt(common["canonical_mae"]),
                common_count=fmt(common["count_ok"]),
                common_brier=fmt(common["brier_ok"]),
                common_loss=fmt(common["log_loss_ok"]),
                recent_n=recent["n"],
                recent_current=fmt(recent["current_mae"]),
                recent_v0=fmt(recent["canonical_mae"]),
                recent_count=fmt(recent["count_ok"]),
                recent_brier=fmt(recent["brier_ok"]),
                recent_loss=fmt(recent["log_loss_ok"]),
            )
        )

    guard = payload["canonical_only"]
    lines.extend(
        [
            "",
            "## Canonical-Only Guard",
            "",
            f"- Canonical-only sample size: `{guard['n']}`",
            f"- Hard block active: `{'yes' if guard['hard_block'] else 'no'}`",
            f"- Reason: {guard['reason']}",
            "",
            "## Publication Rule",
            "",
            "- Allow corners v0 into research lane only for fixtures where the current model would also have priced the fixture.",
            "- Restrict initial research-lane publication to passing leagues only.",
            "- Keep canonical-only fixtures blocked until N >= 200 and segment calibration is stable.",
            "- Keep all corners publication blocked unless the real Pinnacle odds gate passes.",
            "- CLV monitoring must log `current_model_would_have_priced` so live results can keep common vs extended-coverage bets separate.",
            f"- Allowed-league config written to `{DEFAULT_ALLOWED_CONFIG.relative_to(ROOT)}`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check corners v0 promotion gates")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--allowed-config-out", type=Path, default=DEFAULT_ALLOWED_CONFIG)
    parser.add_argument("--real-odds-results", type=Path, default=DEFAULT_REAL_ODDS_RESULTS)
    parser.add_argument("--strict", action="store_true", help="Exit 1 unless all-league research promotion gate passes")
    args = parser.parse_args()

    rows = load_rows(args.summary)
    payload = build_payload(rows, args.real_odds_results)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_markdown(payload), encoding="utf-8")
    args.allowed_config_out.write_text(json.dumps(build_allowed_config(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.json_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")
    print(f"Wrote {args.allowed_config_out.relative_to(ROOT)}")
    if args.strict and not payload["research_lane_ready_all_leagues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
