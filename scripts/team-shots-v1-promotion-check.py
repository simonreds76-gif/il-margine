#!/usr/bin/env python3
"""Promotion gate report for canonical team-shots research variants.

This is research-only. It checks whether the canonical team-shots model is
safe to publish by league, using the same discipline as the corners v0 gate:

- common-sample count MAE must not regress on the full window;
- last-90 common-sample count MAE must improve by a minimum margin;
- Brier and log-loss must match or beat current on both windows and every line;
- canonical-only publication stays hard-blocked until separately validated.
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
DEFAULT_JSON = ROOT / "data" / "football-form" / "team-shots-v1-promotion-check.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "team-shots-v1-promotion-check.md"
DEFAULT_ALLOWED_CONFIG = ROOT / "data" / "football-form" / "team-shots-v1-allowed-leagues.json"

MODEL = "canonical_form_v1_market_nb"
MARKET = "team_shots"
TEAM_SHOTS_LINES = ["9.5", "10.5", "11.5", "12.5", "13.5", "14.5", "15.5"]
MIN_CANONICAL_ONLY_N = 200
MIN_LAST90_LEAGUE_N = 50
MIN_LAST90_MAE_IMPROVEMENT_PCT = 0.005


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
            row.get("market") == MARKET
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
    for line in TEAM_SHOTS_LINES:
        canonical = find_row(rows, model=MODEL, sample=sample, league=league, line=line)
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
    canonical = find_row(rows, model=MODEL, sample=sample, league=league, line="count")
    current = find_row(rows, model="current", sample=sample, league=league, line="count")
    canonical_mae = pf(canonical.get("mae") if canonical else None)
    current_mae = pf(current.get("mae") if current else None)
    n = int(pf(canonical.get("n") if canonical else None) or 0)
    improvement_pct = None
    if canonical_mae is not None and current_mae is not None and current_mae > 0:
        improvement_pct = (current_mae - canonical_mae) / current_mae
    return {
        "n": n,
        "canonical_mae": canonical_mae,
        "current_mae": current_mae,
        "mae_delta": (canonical_mae - current_mae) if canonical_mae is not None and current_mae is not None else None,
        "improvement_pct": improvement_pct,
        "count_ok": canonical_mae is not None and current_mae is not None and canonical_mae <= current_mae,
    }


def evaluate_league(rows: list[dict[str, str]], league: str) -> dict[str, Any]:
    common_count = count_gate(rows, sample="common", league=league)
    common_prob = probability_gate(rows, sample="common", league=league)
    recent_count = count_gate(rows, sample="last_90_common", league=league)
    recent_prob = probability_gate(rows, sample="last_90_common", league=league)
    recent_n_ok = recent_count["n"] >= MIN_LAST90_LEAGUE_N
    recent_improvement_ok = (
        recent_count["improvement_pct"] is not None
        and recent_count["improvement_pct"] >= MIN_LAST90_MAE_IMPROVEMENT_PCT
    )
    return {
        "league": league,
        "common": {**common_count, **common_prob},
        "last_90_common": {
            **recent_count,
            **recent_prob,
            "n_ok": recent_n_ok,
            "improvement_ok": recent_improvement_ok,
            "min_improvement_pct": MIN_LAST90_MAE_IMPROVEMENT_PCT,
        },
        "passes": (
            common_count["count_ok"]
            and common_prob["brier_ok"]
            and common_prob["log_loss_ok"]
            and recent_n_ok
            and recent_count["count_ok"]
            and recent_improvement_ok
            and recent_prob["brier_ok"]
            and recent_prob["log_loss_ok"]
        ),
    }


def build_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    leagues = sorted(
        {
            row.get("league", "")
            for row in rows
            if row.get("market") == MARKET
            and row.get("sample") == "common"
            and row.get("line") == "count"
            and row.get("league") not in {"", "ALL"}
        }
    )
    league_results = [evaluate_league(rows, league) for league in leagues]
    canonical_only = find_row(rows, model=MODEL, sample="canonical_only", league="ALL", line="count")
    canonical_only_n = int(pf(canonical_only.get("n") if canonical_only else None) or 0)
    ready_leagues = [item["league"] for item in league_results if item["passes"]]
    blocked_leagues = [item["league"] for item in league_results if not item["passes"]]
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": str(DEFAULT_SUMMARY.relative_to(ROOT)).replace("\\", "/"),
        "policy": {
            "model": MODEL,
            "market": MARKET,
            "promotion_lane": "research",
            "min_canonical_only_n": MIN_CANONICAL_ONLY_N,
            "min_last90_league_n": MIN_LAST90_LEAGUE_N,
            "min_last90_mae_improvement_pct": MIN_LAST90_MAE_IMPROVEMENT_PCT,
        },
        "league_results": league_results,
        "canonical_only": {
            "n": canonical_only_n,
            "hard_block": True,
            "reason": (
                "Team-shots canonical-only coverage is large but not segment-validated yet; "
                "publish only where current_model_would_have_priced is true."
            ),
        },
        "ready_leagues": ready_leagues,
        "blocked_leagues": blocked_leagues,
        "research_lane_ready_all_leagues": all(item["passes"] for item in league_results),
        "research_lane_ready_partial": bool(ready_leagues),
    }


def build_allowed_config(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": payload["generated_at"],
        "model": MODEL,
        "market": MARKET,
        "lane": "research",
        "allowed_leagues": payload.get("ready_leagues", []),
        "blocked_leagues": payload.get("blocked_leagues", []),
        "canonical_only_allowed": False,
        "canonical_only_min_n": MIN_CANONICAL_ONLY_N,
        "rules": [
            "publish only if league is in allowed_leagues",
            "publish only if current_model_would_have_priced is true",
            "do not publish canonical-only fixtures until canonical-only segment calibration passes",
            f"last_90 MAE must improve by at least {MIN_LAST90_MAE_IMPROVEMENT_PCT:.1%}",
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
    model = payload["policy"]["model"]
    allowed_config_path = payload.get("allowed_config_path") or str(DEFAULT_ALLOWED_CONFIG.relative_to(ROOT))
    lines = [
        f"# Team-Shots Promotion Check: `{model}`",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "This is a research-lane gate only. It does not change live picks.",
        "",
        f"Research lane ready across all leagues: **{'yes' if payload['research_lane_ready_all_leagues'] else 'no'}**",
        f"Research lane ready for passing leagues only: **{'yes' if payload['research_lane_ready_partial'] else 'no'}**",
        f"Passing leagues: `{', '.join(payload['ready_leagues']) or '-'}`",
        f"Blocked leagues: `{', '.join(payload['blocked_leagues']) or '-'}`",
        "",
        "## Per-League Gates",
        "",
        "| League | Common N | Current MAE | Candidate MAE | Count | Brier | Log-loss | Last90 N | Last90 Current MAE | Last90 Candidate MAE | Last90 Improvement | Last90 Count | Last90 Brier | Last90 Log-loss |",
        "| --- | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for item in payload["league_results"]:
        common = item["common"]
        recent = item["last_90_common"]
        improvement_pct = recent.get("improvement_pct")
        lines.append(
            "| {league} | {common_n} | {common_current} | {common_v1} | {common_count} | {common_brier} | {common_loss} | "
            "{recent_n} | {recent_current} | {recent_v1} | {recent_improvement} | {recent_count} | {recent_brier} | {recent_loss} |".format(
                league=item["league"],
                common_n=common["n"],
                common_current=fmt(common["current_mae"]),
                common_v1=fmt(common["canonical_mae"]),
                common_count=fmt(common["count_ok"]),
                common_brier=fmt(common["brier_ok"]),
                common_loss=fmt(common["log_loss_ok"]),
                recent_n=recent["n"],
                recent_current=fmt(recent["current_mae"]),
                recent_v1=fmt(recent["canonical_mae"]),
                recent_improvement="-" if improvement_pct is None else f"{improvement_pct:.2%}",
                recent_count=fmt(recent["count_ok"] and recent["improvement_ok"]),
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
            f"- Allow `{model}` into research lane only for fixtures where the current model would also have priced the fixture.",
            "- Restrict initial research-lane publication to passing leagues only.",
            "- Keep canonical-only fixtures blocked until segment calibration is stable.",
            f"- Allowed-league config written to `{allowed_config_path}`.",
            "",
        ]
    )
    return "\n".join(lines)


def display_path(path: Path) -> str:
    resolved = path if path.is_absolute() else ROOT / path
    try:
        return str(resolved.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def main() -> None:
    global MODEL
    parser = argparse.ArgumentParser(description="Check team-shots v1 promotion gates")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--allowed-config-out", type=Path, default=DEFAULT_ALLOWED_CONFIG)
    parser.add_argument("--model", default=MODEL, help="Canonical team-shots model id from canonical-backtest-summary.csv")
    parser.add_argument("--strict", action="store_true", help="Exit 1 unless all-league research promotion gate passes")
    args = parser.parse_args()

    MODEL = args.model
    rows = load_rows(args.summary)
    payload = build_payload(rows)
    payload["allowed_config_path"] = display_path(args.allowed_config_out)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_markdown(payload), encoding="utf-8")
    args.allowed_config_out.write_text(json.dumps(build_allowed_config(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {display_path(args.json_out)}")
    print(f"Wrote {display_path(args.report_out)}")
    print(f"Wrote {display_path(args.allowed_config_out)}")
    if args.strict and not payload["research_lane_ready_all_leagues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
