#!/usr/bin/env python3
"""Total-corners diagnostic for blocked canonical v0 leagues.

The venue/component diagnostic showed a home/away redistribution bias, but
total-corners O/U only cares about home + away. This script looks at the
match-total expectation directly for Bundesliga and La Liga.
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
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORM = ROOT / "data" / "football-form" / "team-rolling-form.csv"
DEFAULT_CURRENT = ROOT / "data" / "corners-ou" / "corners-ou-predictions.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "corners-total-diagnostic.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "corners-total-diagnostic.md"
DEFAULT_CSV = ROOT / "data" / "football-form" / "corners-total-worst.csv"
FOCUS_LEAGUES = {"bundesliga", "la-liga"}


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


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def rounded(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def win_gap_bucket(gap: float | None) -> str:
    if gap is None:
        return "unknown"
    if gap < 0.10:
        return "0-10pp"
    if gap < 0.25:
        return "10-25pp"
    if gap < 0.40:
        return "25-40pp"
    if gap < 0.55:
        return "40-55pp"
    return "55pp+"


def pace_bucket(ratio: float | None) -> str:
    if ratio is None or ratio <= 0:
        return "unknown"
    if ratio < 0.95:
        return "low"
    if ratio > 1.05:
        return "high"
    return "neutral"


def attack_shape(home_rel: float | None, away_rel: float | None) -> str:
    if home_rel is None or away_rel is None:
        return "unknown"
    home_high = home_rel > 1.05
    away_high = away_rel > 1.05
    home_low = home_rel < 0.95
    away_low = away_rel < 0.95
    if home_high and away_high:
        return "both_high"
    if home_low and away_low:
        return "both_low"
    if (home_high and away_low) or (away_high and home_low):
        return "one_sided"
    return "balanced"


def safe_ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den <= 0:
        return None
    return num / den


def build_records(form_rows: list[dict[str, str]], current_rows: list[dict[str, str]], bt: Any) -> tuple[list[dict[str, Any]], str, str]:
    current_by_key = {bt.row_key(row): row for row in current_rows}
    latest = bt.latest_form_date(form_rows)
    recent_cutoff = latest - timedelta(days=90) if latest else None
    league_shots_avg = bt.league_shots_averages(form_rows)

    rows_by_fixture: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in form_rows:
        rows_by_fixture[bt.row_key(row)].append(row)

    records: list[dict[str, Any]] = []
    for fixture_key, fixture_rows in rows_by_fixture.items():
        current = current_by_key.get(fixture_key)
        if current is None or len(fixture_rows) != 2:
            continue
        home_rows = [row for row in fixture_rows if str(row.get("venue", "")).strip() == "home"]
        away_rows = [row for row in fixture_rows if str(row.get("venue", "")).strip() == "away"]
        if len(home_rows) != 1 or len(away_rows) != 1:
            continue
        home = home_rows[0]
        away = away_rows[0]
        league = str(home.get("league", "")).strip()
        fixture_date = parse_date(home.get("date"))
        if fixture_date is None or recent_cutoff is None or fixture_date < recent_cutoff:
            continue

        canonical_home = bt.canonical_corners_lambda(home, away, league_shots_avg.get(league, 0.0))
        canonical_away = bt.canonical_corners_lambda(away, home, league_shots_avg.get(league, 0.0))
        current_total = pf(current.get("lambda_total"))
        actual_total = pf(current.get("actual_total"))
        if canonical_home is None or canonical_away is None or current_total is None or actual_total is None:
            continue

        canonical_total = canonical_home + canonical_away
        home_prob = pf(home.get("market_team_win_prob"))
        away_prob = pf(away.get("market_team_win_prob"))
        win_gap = abs(home_prob - away_prob) if home_prob is not None and away_prob is not None else None

        league_corner_avg = pf(home.get("league_prior_corners_for_avg"))
        league_total = (league_corner_avg * 2.0) if league_corner_avg is not None else None
        home_attack = bt.blended(home, "corners_for_avg")
        away_attack = bt.blended(away, "corners_for_avg")
        home_concede = bt.blended(home, "corners_against_avg")
        away_concede = bt.blended(away, "corners_against_avg")
        pressure_total = mean(
            [
                value
                for value in (home_attack, away_attack, home_concede, away_concede)
                if value is not None
            ]
        ) * 2.0
        pace_ratio = safe_ratio(pressure_total, league_total)
        home_attack_rel = safe_ratio(home_attack, league_corner_avg)
        away_attack_rel = safe_ratio(away_attack, league_corner_avg)

        current_error = current_total - actual_total
        canonical_error = canonical_total - actual_total
        records.append(
            {
                "date": fixture_date.isoformat(),
                "league": league,
                "home_team": home.get("home_team", ""),
                "away_team": home.get("away_team", ""),
                "current_total_lambda": current_total,
                "canonical_total_lambda": canonical_total,
                "actual_total_corners": actual_total,
                "lambda_gap": canonical_total - current_total,
                "current_error": current_error,
                "canonical_error": canonical_error,
                "canonical_abs_error_minus_current": abs(canonical_error) - abs(current_error),
                "win_prob_gap": win_gap,
                "win_gap_bucket": win_gap_bucket(win_gap),
                "pace_ratio": pace_ratio,
                "pace_bucket": pace_bucket(pace_ratio),
                "home_attack_rel": home_attack_rel,
                "away_attack_rel": away_attack_rel,
                "attack_shape": attack_shape(home_attack_rel, away_attack_rel),
            }
        )
    return records, latest.isoformat() if latest else "", recent_cutoff.isoformat() if recent_cutoff else ""


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "n": 0,
            "current_mae": None,
            "canonical_mae": None,
            "mae_delta": None,
            "current_bias": None,
            "canonical_bias": None,
            "mean_lambda_gap": None,
            "canonical_worse_share": None,
        }
    current_mae = mean(abs(row["current_error"]) for row in records)
    canonical_mae = mean(abs(row["canonical_error"]) for row in records)
    return {
        "n": len(records),
        "current_mae": rounded(current_mae),
        "canonical_mae": rounded(canonical_mae),
        "mae_delta": rounded(canonical_mae - current_mae),
        "current_bias": rounded(mean(row["current_error"] for row in records)),
        "canonical_bias": rounded(mean(row["canonical_error"] for row in records)),
        "mean_lambda_gap": rounded(mean(row["lambda_gap"] for row in records)),
        "canonical_worse_share": rounded(mean(1.0 if row["canonical_abs_error_minus_current"] > 0 else 0.0 for row in records)),
    }


def grouped(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_key[str(row.get(key) or "unknown")].append(row)
    return {name: summarize(rows) for name, rows in sorted(by_key.items())}


def render_table(lines: list[str], title: str, payload: dict[str, dict[str, Any]]) -> None:
    lines.extend(
        [
            f"## {title}",
            "",
            "| Bucket | N | Current MAE | V0 MAE | Delta | Current bias | V0 bias | Lambda gap | Worse share |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for bucket, row in payload.items():
        lines.append(
            "| {bucket} | {n} | {current_mae} | {canonical_mae} | {mae_delta} | {current_bias} | {canonical_bias} | {mean_lambda_gap} | {canonical_worse_share} |".format(
                bucket=bucket,
                **{field: "-" if value is None else value for field, value in row.items()},
            )
        )
    lines.append("")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Corners Total Diagnostic",
        "",
        f"Generated: {payload['generated_at']}",
        f"Latest form date: `{payload['latest_form_date']}`",
        f"Recent cutoff: `{payload['recent_cutoff']}`",
        "",
        "This is diagnostic only. It targets total-corners O/U, not home/away component redistribution.",
        "",
        "## Last-90 League Summary",
        "",
        "| League | N | Current MAE | V0 MAE | Delta | Current bias | V0 bias | Lambda gap | Worse share |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for league, row in payload["by_league"].items():
        lines.append(
            "| {league} | {n} | {current_mae} | {canonical_mae} | {mae_delta} | {current_bias} | {canonical_bias} | {mean_lambda_gap} | {canonical_worse_share} |".format(
                league=league,
                **{field: "-" if value is None else value for field, value in row.items()},
            )
        )
    lines.append("")
    for league in sorted(FOCUS_LEAGUES):
        focus = payload["focus"].get(league, {})
        lines.extend([f"# {league}", ""])
        render_table(lines, "Win-Probability Gap Buckets", focus.get("win_gap_bucket", {}))
        render_table(lines, "Pace Buckets", focus.get("pace_bucket", {}))
        render_table(lines, "Attack-Shape Buckets", focus.get("attack_shape", {}))
    lines.extend(
        [
            "## Read",
            "",
            "- If the blocked leagues have large positive/negative `lambda_gap`, a scalar calibration is the first candidate.",
            "- If the damage clusters in `high` pace or `both_high` attack buckets, the pressure formula is the first candidate.",
            "- If damage clusters by win-probability gap, the corners model needs game-state conditioning rather than home/away redistribution.",
            f"- Worst rows written to `{payload['worst_csv']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_worst(records: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "date",
        "league",
        "home_team",
        "away_team",
        "current_total_lambda",
        "canonical_total_lambda",
        "actual_total_corners",
        "canonical_abs_error_minus_current",
        "lambda_gap",
        "current_error",
        "canonical_error",
        "win_gap_bucket",
        "pace_bucket",
        "attack_shape",
        "win_prob_gap",
        "pace_ratio",
        "home_attack_rel",
        "away_attack_rel",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    worst = sorted(records, key=lambda row: row["canonical_abs_error_minus_current"], reverse=True)[:75]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in worst])


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose corners total-corners v0 errors")
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    ensure_form_input(args.form)
    bt = load_backtest_module()
    records, latest, recent_cutoff = build_records(load_csv(args.form), load_csv(args.current), bt)
    by_league = grouped(records, "league")
    focus_payload: dict[str, Any] = {}
    for league in FOCUS_LEAGUES:
        league_records = [row for row in records if row["league"] == league]
        focus_payload[league] = {
            "win_gap_bucket": grouped(league_records, "win_gap_bucket"),
            "pace_bucket": grouped(league_records, "pace_bucket"),
            "attack_shape": grouped(league_records, "attack_shape"),
        }

    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "latest_form_date": latest,
        "recent_cutoff": recent_cutoff,
        "model": "canonical_form_v0",
        "market": "corners_total",
        "diagnostic": "match_total",
        "by_league": by_league,
        "focus": focus_payload,
        "worst_csv": str(args.csv_out.relative_to(ROOT)).replace("\\", "/"),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_markdown(payload) + "\n", encoding="utf-8")
    write_worst(records, args.csv_out)
    print(f"Wrote {args.json_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")
    print(f"Wrote {args.csv_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
