#!/usr/bin/env python3
"""Compare current team-shots lambda design against canonical team-shots v1.

The goal is not to tune. It identifies what the current model is doing that
canonical does not, then dumps the last-90 matches where canonical loses most
to current on count error.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_CURRENT = ROOT / "data" / "team-shots" / "team-shots-predictions.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "team-shots-feature-gap-diagnostic.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "team-shots-feature-gap-diagnostic.md"
DEFAULT_CSV = ROOT / "data" / "football-form" / "team-shots-feature-gap-worst.csv"


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
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def ensure_form_input(path: Path) -> None:
    if path.exists():
        return
    if path != DEFAULT_FORM:
        raise SystemExit(f"Missing canonical form input: {path}")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build-football-form-layer.py")], check=True)
    if not path.exists():
        raise SystemExit(f"Canonical form build did not create expected input: {path}")


def pf(value: Any, default: float | None = None) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def mae(errors: list[float]) -> float:
    return mean([abs(error) for error in errors])


def gap_bucket(gap: float | None) -> str:
    if gap is None:
        return "unknown"
    abs_gap = abs(gap)
    if abs_gap < 0.10:
        return "0-10pp"
    if abs_gap < 0.25:
        return "10-25pp"
    if abs_gap < 0.40:
        return "25-40pp"
    if abs_gap < 0.55:
        return "40-55pp"
    return "55pp+"


def round_or_none(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def current_model_inventory() -> list[dict[str, str]]:
    return [
        {
            "area": "formula",
            "current": "multiplicative: league_avg * attack_ratio * opponent_concession_ratio",
            "canonical": "additive: 55% attack input + 45% opponent concession input",
            "diagnostic_read": "Primary suspect if canonical is too conservative in high-volume games.",
        },
        {
            "area": "history weighting",
            "current": "20-match exponential moving average with decay 0.93",
            "canonical": "70% r10 + 30% r5 blend when recent window has at least 3 rows",
            "diagnostic_read": "Current may be smoother; canonical may over/under-react to short windows.",
        },
        {
            "area": "venue",
            "current": "venue-specific team attack; pooled opponent defence; no extra home multiplier on venue lambda",
            "canonical": "venue-specific team attack and venue-specific opponent concession",
            "diagnostic_read": "Canonical may overfit venue concession splits, especially with smaller away/home samples.",
        },
        {
            "area": "league baseline",
            "current": "causal league average with hard baseline until 40 team observations",
            "canonical": "causal prior/t12 fields exist, but promoted lambda uses raw shot inputs plus capped ratios only in diagnostics",
            "diagnostic_read": "Current product formula is league-relative by construction.",
        },
        {
            "area": "xG",
            "current": "25% xG lambda blend when team and opponent xG histories are both usable",
            "canonical": "small capped xG-per-shot quality adjustment",
            "diagnostic_read": "xG is sparse, but current may extract signal in covered rows.",
        },
        {
            "area": "market/game state",
            "current": "not in the count lambda",
            "canonical": "capped 1X2 win-probability adjustment",
            "diagnostic_read": "Already tested: disabling the cap did not fix last-90 aggregate.",
        },
        {
            "area": "probability distribution",
            "current": "Poisson probability surface from venue lambda",
            "canonical": "negative-binomial probability surface from canonical lambda",
            "diagnostic_read": "NB improved probability calibration but does not fix count lambda.",
        },
    ]


def build_records(form_rows: list[dict[str, str]], current_rows: list[dict[str, str]], bt: Any) -> list[dict[str, Any]]:
    current_by_key = {bt.team_key(row): row for row in current_rows}
    rows_by_fixture: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in form_rows:
        rows_by_fixture[bt.row_key(row)].append(row)

    records: list[dict[str, Any]] = []
    for fixture_rows in rows_by_fixture.values():
        if len(fixture_rows) != 2:
            continue
        home_rows = [row for row in fixture_rows if str(row.get("venue", "")).strip() == "home"]
        away_rows = [row for row in fixture_rows if str(row.get("venue", "")).strip() == "away"]
        if len(home_rows) != 1 or len(away_rows) != 1:
            continue
        home = home_rows[0]
        away = away_rows[0]
        for team, opp in ((home, away), (away, home)):
            current = current_by_key.get(bt.team_key(team))
            if current is None:
                continue
            fixture_date = parse_date(team.get("date"))
            actual = pf(team.get("current_shots_for"))
            current_lambda = pf(current.get("lambda_venue"), None) or pf(current.get("lambda_shots"), None)
            canonical_lambda = bt.canonical_team_shots_lambda(team, opp, use_market=True)
            if fixture_date is None or actual is None or current_lambda is None or canonical_lambda is None:
                continue

            team_venue = str(team.get("venue", "")).strip()
            opp_venue = str(opp.get("venue", "")).strip()
            attack = bt.blended_prefer(team, bt.venue_field("shots_for", team_venue), "shots_for_avg")
            defence = bt.blended_prefer(opp, bt.venue_field("shots_against", opp_venue), "shots_against_avg")
            canonical_base = None
            canonical_after_quality = None
            quality_adj = bt.quality_adjustment(team, opp)
            market_adj = bt.market_game_state_adjustment(team)
            if attack is not None and defence is not None:
                canonical_base = (0.55 * attack) + (0.45 * defence)
                canonical_after_quality = canonical_base * quality_adj

            current_base = pf(current.get("lambda_shots"), None)
            current_xg = pf(current.get("xg_lambda"), None)
            current_recent = pf(current.get("lambda_recent"), None)
            current_error = current_lambda - actual
            canonical_error = canonical_lambda - actual
            market_team = pf(team.get("market_team_win_prob"), None)
            market_opp = pf(team.get("market_opp_win_prob"), None)
            market_gap = (market_team - market_opp) if market_team is not None and market_opp is not None else None

            records.append(
                {
                    "date": fixture_date.isoformat(),
                    "league": team.get("league", ""),
                    "season": team.get("season", ""),
                    "team": team.get("team", ""),
                    "opponent": team.get("opponent", ""),
                    "venue": team_venue,
                    "home_team": team.get("home_team", ""),
                    "away_team": team.get("away_team", ""),
                    "actual": actual,
                    "current_lambda": current_lambda,
                    "current_base_lambda": current_base,
                    "current_xg_lambda": current_xg,
                    "current_recent_lambda": current_recent,
                    "current_venue_minus_base": (current_lambda - current_base) if current_base is not None else None,
                    "current_recent_minus_venue": (current_recent - current_lambda) if current_recent is not None else None,
                    "canonical_lambda": canonical_lambda,
                    "canonical_base_lambda": canonical_base,
                    "canonical_after_quality": canonical_after_quality,
                    "canonical_quality_effect": (canonical_after_quality - canonical_base)
                    if canonical_after_quality is not None and canonical_base is not None
                    else None,
                    "canonical_market_effect": (canonical_lambda - canonical_after_quality)
                    if canonical_after_quality is not None
                    else None,
                    "attack_input": attack,
                    "defence_input": defence,
                    "quality_adjustment": quality_adj,
                    "market_adjustment": market_adj,
                    "market_gap": market_gap,
                    "gap_bucket": gap_bucket(market_gap),
                    "r10_matches": int(pf(team.get("r10_matches"), 0) or 0),
                    "opp_r10_matches": int(pf(opp.get("r10_matches"), 0) or 0),
                    "current_error": current_error,
                    "canonical_error": canonical_error,
                    "current_abs_error": abs(current_error),
                    "canonical_abs_error": abs(canonical_error),
                    "canonical_minus_current_lambda": canonical_lambda - current_lambda,
                    "canonical_abs_error_minus_current": abs(canonical_error) - abs(current_error),
                    "canonical_lower_than_current": canonical_lambda < current_lambda,
                }
            )
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    current_errors = [record["current_error"] for record in records]
    canonical_errors = [record["canonical_error"] for record in records]
    lambda_gaps = [record["canonical_minus_current_lambda"] for record in records]
    worse = [record for record in records if record["canonical_abs_error"] > record["current_abs_error"]]
    lower = [record for record in records if record["canonical_lower_than_current"]]
    return {
        "n": len(records),
        "current_mae": round_or_none(mae(current_errors)),
        "canonical_mae": round_or_none(mae(canonical_errors)),
        "mae_delta": round_or_none(mae(canonical_errors) - mae(current_errors)) if records else None,
        "current_bias": round_or_none(mean(current_errors)),
        "canonical_bias": round_or_none(mean(canonical_errors)),
        "mean_lambda_gap": round_or_none(mean(lambda_gaps)),
        "canonical_worse_n": len(worse),
        "canonical_worse_share": round_or_none(len(worse) / len(records), 4) if records else None,
        "canonical_lower_than_current_share": round_or_none(len(lower) / len(records), 4) if records else None,
    }


def grouped_summary(records: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record.get(field) or "unknown")].append(record)
    return [{field: key, **summarize(group)} for key, group in sorted(groups.items())]


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, float):
            cleaned[key] = round_or_none(value, 4)
        else:
            cleaned[key] = value
    return cleaned


def build_payload(form_rows: list[dict[str, str]], current_rows: list[dict[str, str]]) -> dict[str, Any]:
    bt = load_backtest_module()
    records = build_records(form_rows, current_rows, bt)
    latest = max((parse_date(row.get("date")) for row in form_rows if parse_date(row.get("date"))), default=None)
    recent_cutoff = latest - timedelta(days=90) if latest else None
    recent = [
        record
        for record in records
        if recent_cutoff is not None and parse_date(record["date"]) is not None and parse_date(record["date"]) >= recent_cutoff
    ]
    worst = sorted(recent, key=lambda item: item["canonical_abs_error_minus_current"], reverse=True)[:25]
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "latest_form_date": latest.isoformat() if latest else None,
        "recent_cutoff": recent_cutoff.isoformat() if recent_cutoff else None,
        "feature_inventory": current_model_inventory(),
        "summary": {
            "full_common": summarize(records),
            "last_90_common": summarize(recent),
            "last_90_by_league": grouped_summary(recent, "league"),
            "last_90_by_venue": grouped_summary(recent, "venue"),
            "last_90_by_gap_bucket": grouped_summary(recent, "gap_bucket"),
        },
        "worst_canonical_vs_current_last90": [clean_record(record) for record in worst],
    }


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def render_group_table(title: str, rows: list[dict[str, Any]], group_field: str) -> list[str]:
    lines = [
        f"## {title}",
        "",
        f"| {group_field} | N | Current MAE | Canonical MAE | Delta | Current bias | Canonical bias | Mean lambda gap | Canonical worse | Canonical lower |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row[group_field]} | {row['n']} | {fmt(row['current_mae'])} | {fmt(row['canonical_mae'])} | "
            f"{fmt(row['mae_delta'])} | {fmt(row['current_bias'])} | {fmt(row['canonical_bias'])} | "
            f"{fmt(row['mean_lambda_gap'])} | {fmt(row['canonical_worse_share'])} | {fmt(row['canonical_lower_than_current_share'])} |"
        )
    lines.append("")
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    full = payload["summary"]["full_common"]
    recent = payload["summary"]["last_90_common"]
    lines = [
        "# Team-Shots Feature Gap Diagnostic",
        "",
        f"Generated: {payload['generated_at']}",
        f"Latest form date: `{payload['latest_form_date']}`",
        f"Recent cutoff: `{payload['recent_cutoff']}`",
        "",
        "No live policy changed. This report compares current vs canonical lambda design.",
        "",
        "## Headline",
        "",
        "| Sample | N | Current MAE | Canonical MAE | Delta | Current bias | Canonical bias | Mean canonical-current lambda | Canonical worse share | Canonical lower share |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| full_common | {full['n']} | {fmt(full['current_mae'])} | {fmt(full['canonical_mae'])} | {fmt(full['mae_delta'])} | {fmt(full['current_bias'])} | {fmt(full['canonical_bias'])} | {fmt(full['mean_lambda_gap'])} | {fmt(full['canonical_worse_share'])} | {fmt(full['canonical_lower_than_current_share'])} |",
        f"| last_90_common | {recent['n']} | {fmt(recent['current_mae'])} | {fmt(recent['canonical_mae'])} | {fmt(recent['mae_delta'])} | {fmt(recent['current_bias'])} | {fmt(recent['canonical_bias'])} | {fmt(recent['mean_lambda_gap'])} | {fmt(recent['canonical_worse_share'])} | {fmt(recent['canonical_lower_than_current_share'])} |",
        "",
        "## Feature Inventory Diff",
        "",
        "| Area | Current model | Canonical v1 | Diagnostic read |",
        "| --- | --- | --- | --- |",
    ]
    for item in payload["feature_inventory"]:
        lines.append(f"| {item['area']} | {item['current']} | {item['canonical']} | {item['diagnostic_read']} |")

    lines.append("")
    lines.extend(render_group_table("Last-90 By League", payload["summary"]["last_90_by_league"], "league"))
    lines.extend(render_group_table("Last-90 By Venue", payload["summary"]["last_90_by_venue"], "venue"))
    lines.extend(render_group_table("Last-90 By Win-Prob Gap Bucket", payload["summary"]["last_90_by_gap_bucket"], "gap_bucket"))

    lines.extend(
        [
            "## Worst Canonical-vs-Current Last-90 Rows",
            "",
            "| Date | League | Match | Team | Venue | Actual | Current | Canonical | Current err | Canon err | Canon-current lambda | Attack | Defence | Current base | Current xG | Current recent | Canon base | Quality effect | Market effect |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["worst_canonical_vs_current_last90"]:
        lines.append(
            f"| {row['date']} | {row['league']} | {row['home_team']} vs {row['away_team']} | {row['team']} | {row['venue']} | "
            f"{fmt(row['actual'], 1)} | {fmt(row['current_lambda'], 2)} | {fmt(row['canonical_lambda'], 2)} | "
            f"{fmt(row['current_error'], 2)} | {fmt(row['canonical_error'], 2)} | {fmt(row['canonical_minus_current_lambda'], 2)} | "
            f"{fmt(row.get('attack_input'), 2)} | {fmt(row.get('defence_input'), 2)} | {fmt(row.get('current_base_lambda'), 2)} | "
            f"{fmt(row.get('current_xg_lambda'), 2)} | {fmt(row.get('current_recent_lambda'), 2)} | "
            f"{fmt(row.get('canonical_base_lambda'), 2)} | {fmt(row.get('canonical_quality_effect'), 2)} | "
            f"{fmt(row.get('canonical_market_effect'), 2)} |"
        )
    lines.append("")
    lines.extend(
        [
            "## Read",
            "",
            "- If canonical is mostly lower than current in the worst rows, the next test should start with the formula shape: current's multiplicative league-relative lambda vs canonical's additive blend.",
            "- If the gap is mostly venue-specific, test pooled opponent defence vs venue-specific opponent concession before adding new features.",
            "- If both models underpredict extreme actuals, a tail/tempo feature is needed after the formula diff is understood.",
            "",
        ]
    )
    return "\n".join(lines)


def write_worst_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "date",
        "league",
        "season",
        "home_team",
        "away_team",
        "team",
        "opponent",
        "venue",
        "actual",
        "current_lambda",
        "canonical_lambda",
        "current_error",
        "canonical_error",
        "canonical_abs_error_minus_current",
        "canonical_minus_current_lambda",
        "attack_input",
        "defence_input",
        "current_base_lambda",
        "current_xg_lambda",
        "current_recent_lambda",
        "current_venue_minus_base",
        "current_recent_minus_venue",
        "canonical_base_lambda",
        "canonical_quality_effect",
        "canonical_market_effect",
        "quality_adjustment",
        "market_adjustment",
        "market_gap",
        "gap_bucket",
        "r10_matches",
        "opp_r10_matches",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare current and canonical team-shots lambda design")
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    ensure_form_input(args.form)
    form_rows = load_csv(args.form)
    current_rows = load_csv(args.current)
    if not form_rows:
        raise SystemExit(f"Canonical form input is empty: {args.form}")
    if not current_rows:
        raise SystemExit(f"Current team-shots input is empty: {args.current}")

    payload = build_payload(form_rows, current_rows)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_markdown(payload), encoding="utf-8")
    write_worst_csv(args.csv_out, payload["worst_canonical_vs_current_last90"])
    print(f"Wrote {args.json_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")
    print(f"Wrote {args.csv_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
