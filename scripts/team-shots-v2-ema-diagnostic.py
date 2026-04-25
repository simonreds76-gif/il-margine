#!/usr/bin/env python3
"""Diagnostic sweep for adding current-style EMA smoothing on top of team-shots v2.

This is deliberately a diagnostic, not a promotion model. It tests whether
blending the v2 pooled-opponent lambda with the current model's venue-EMA or
short recent-form lambda would rescue blocked leagues before we port EMA fields
into the canonical form layer.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_CURRENT = ROOT / "data" / "team-shots" / "team-shots-predictions.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "team-shots-v2-ema-diagnostic.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "team-shots-v2-ema-diagnostic.md"
WEIGHTS = [round(step / 10, 1) for step in range(11)]


def load_backtest_module() -> Any:
    path = ROOT / "scripts" / "backtest-football-form-layer.py"
    spec = importlib.util.spec_from_file_location("football_form_backtest_mod", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["football_form_backtest_mod"] = module
    spec.loader.exec_module(module)
    return module


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def mae(rows: list[dict[str, Any]], pred_key: str) -> float:
    return sum(abs(row[pred_key] - row["actual"]) for row in rows) / len(rows) if rows else 0.0


def build_records(form_rows: list[dict[str, str]], current_rows: list[dict[str, str]], bt: Any) -> tuple[list[dict[str, Any]], str, str]:
    current_by_key = {bt.team_key(row): row for row in current_rows}
    latest = bt.latest_form_date(form_rows)
    recent_cutoff = latest - timedelta(days=90) if latest else None
    rows_by_fixture: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in form_rows:
        rows_by_fixture[bt.row_key(row)].append(row)

    records: list[dict[str, Any]] = []
    for fixture_rows in rows_by_fixture.values():
        if len(fixture_rows) != 2:
            continue
        home = [row for row in fixture_rows if row.get("venue") == "home"]
        away = [row for row in fixture_rows if row.get("venue") == "away"]
        if len(home) != 1 or len(away) != 1:
            continue
        for team, opp in ((home[0], away[0]), (away[0], home[0])):
            fixture_date = bt.row_date(team)
            if recent_cutoff is None or fixture_date is None or fixture_date < recent_cutoff:
                continue
            current = current_by_key.get(bt.team_key(team))
            if current is None:
                continue
            actual = bt.pf(team.get("current_shots_for"), None)
            v2 = bt.canonical_team_shots_pooled_opp_lambda(team, opp, use_market=True)
            venue_ema = bt.pf(current.get("lambda_venue"), None)
            recent_short = bt.pf(current.get("lambda_recent"), None)
            current_lambda = bt.pf(current.get("lambda_venue"), None) or bt.pf(current.get("lambda_shots"), None)
            if actual is None or v2 is None or venue_ema is None or recent_short is None or current_lambda is None:
                continue
            records.append(
                {
                    "league": str(team.get("league", "")).strip(),
                    "actual": actual,
                    "current": current_lambda,
                    "v2": v2,
                    "venue20": venue_ema,
                    "recent6": recent_short,
                }
            )
    return records, latest.isoformat() if latest else "", recent_cutoff.isoformat() if recent_cutoff else ""


def summarize(records: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for weight in WEIGHTS:
        weighted_rows: list[dict[str, Any]] = []
        for row in records:
            weighted_rows.append(
                {
                    **row,
                    "candidate": ((1.0 - weight) * row["v2"]) + (weight * row[source]),
                }
            )
        by_league: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in weighted_rows:
            by_league[row["league"]].append(row)
        league_metrics = {}
        for league, league_rows in sorted(by_league.items()):
            current_mae = mae(league_rows, "current")
            candidate_mae = mae(league_rows, "candidate")
            improvement = (current_mae - candidate_mae) / current_mae if current_mae > 0 else 0.0
            league_metrics[league] = {
                "n": len(league_rows),
                "current_mae": round(current_mae, 4),
                "candidate_mae": round(candidate_mae, 4),
                "improvement_pct": round(improvement, 4),
                "passes_count_threshold": improvement >= 0.005,
            }
        current_all = mae(weighted_rows, "current")
        candidate_all = mae(weighted_rows, "candidate")
        out.append(
            {
                "source": source,
                "weight": weight,
                "n": len(weighted_rows),
                "current_mae": round(current_all, 4),
                "candidate_mae": round(candidate_all, 4),
                "improvement_pct": round((current_all - candidate_all) / current_all, 4),
                "league_metrics": league_metrics,
            }
        )
    return out


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Team-Shots V2 EMA Diagnostic",
        "",
        f"Generated: {payload['generated_at']}",
        f"Latest form date: `{payload['latest_form_date']}`",
        f"Recent cutoff: `{payload['recent_cutoff']}`",
        "",
        "This is a diagnostic only. It does not promote a v3 model.",
        "",
        "## Best Aggregate Weight By Source",
        "",
        "| Source | Best weight | Current MAE | Candidate MAE | Improvement | Passing leagues at best weight | Blocked leagues at best weight |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for source, best in payload["best_by_source"].items():
        leagues = best["league_metrics"]
        passing = [league for league, item in leagues.items() if item["passes_count_threshold"]]
        blocked = [league for league, item in leagues.items() if not item["passes_count_threshold"]]
        lines.append(
            "| {source} | {weight:.1f} | {current_mae:.4f} | {candidate_mae:.4f} | {improvement_pct:.2%} | `{passing}` | `{blocked}` |".format(
                source=source,
                weight=best["weight"],
                current_mae=best["current_mae"],
                candidate_mae=best["candidate_mae"],
                improvement_pct=best["improvement_pct"],
                passing=", ".join(passing) or "-",
                blocked=", ".join(blocked) or "-",
            )
        )

    lines.extend(
        [
            "",
            "## Read",
            "",
            "- Blending v2 with the current 20-match venue EMA improves aggregate last-90 MAE and helps Serie A, but does not rescue EPL under the configured +0.5% count gate.",
            "- Blending v2 with the short 6-match recent-form lambda is worse than v2, so it should not be promoted.",
            "- Next useful work is not a blind v3 promotion; it is either a clean canonical EMA implementation followed by the same gate, or a separate EPL-specific diagnostic.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep EMA/recent smoothing blends on top of team-shots v2")
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    bt = load_backtest_module()
    records, latest, recent_cutoff = build_records(load_csv(args.form), load_csv(args.current), bt)
    sweeps = {
        "venue20": summarize(records, "venue20"),
        "recent6": summarize(records, "recent6"),
    }
    best_by_source = {
        source: min(rows, key=lambda row: row["candidate_mae"])
        for source, rows in sweeps.items()
    }
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "latest_form_date": latest,
        "recent_cutoff": recent_cutoff,
        "model": "canonical_form_v2_pooled_opp_nb",
        "market": "team_shots",
        "diagnostic": "ema_blend_sweep",
        "sweeps": sweeps,
        "best_by_source": best_by_source,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    print(f"Wrote {args.json_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
