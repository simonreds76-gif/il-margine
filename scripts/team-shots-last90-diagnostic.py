#!/usr/bin/env python3
"""Diagnose the team-shots last-90 count MAE regression.

This does not tune the model. It tests the hypotheses from review:

- is the capped market/game-state adjustment hurting recent count accuracy?
- is the regression concentrated in specific leagues or win-probability buckets?
- is the current model simply stronger in the recent regime?
- are the largest recent errors explainable by thin history / fixture position?
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
DEFAULT_JSON = ROOT / "data" / "football-form" / "team-shots-last90-diagnostic.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "team-shots-last90-diagnostic.md"


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


def mae(values: list[float]) -> float:
    return mean([abs(value) for value in values])


def rmse(values: list[float]) -> float:
    return math.sqrt(mean([value * value for value in values])) if values else 0.0


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


def matchday_bucket(matchday: int | None) -> str:
    if matchday is None:
        return "unknown"
    if matchday <= 5:
        return "md_1_5"
    if matchday <= 10:
        return "md_6_10"
    return "md_11_plus"


def history_bucket(matches: int) -> str:
    if matches < 6:
        return "lt_6"
    if matches < 8:
        return "6_7"
    if matches < 10:
        return "8_9"
    return "10_plus"


def summarize_records(records: list[dict[str, Any]], pred_field: str) -> dict[str, Any]:
    errors = [record[pred_field] - record["actual"] for record in records if record.get(pred_field) is not None]
    return {
        "n": len(errors),
        "mean_pred": round(mean([record[pred_field] for record in records if record.get(pred_field) is not None]), 4) if errors else None,
        "mean_actual": round(mean([record["actual"] for record in records if record.get(pred_field) is not None]), 4) if errors else None,
        "bias": round(mean(errors), 4) if errors else None,
        "mae": round(mae(errors), 4) if errors else None,
        "rmse": round(rmse(errors), 4) if errors else None,
    }


def grouped_summary(records: list[dict[str, Any]], group_field: str, pred_fields: list[str]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record.get(group_field) or "unknown")].append(record)
    output: list[dict[str, Any]] = []
    for key in sorted(groups):
        item: dict[str, Any] = {group_field: key}
        for pred_field in pred_fields:
            item[pred_field] = summarize_records(groups[key], pred_field)
        output.append(item)
    return output


def build_matchday_lookup(form_rows: list[dict[str, str]]) -> dict[tuple[str, str, date], int]:
    dates_by_league_season: dict[tuple[str, str], set[date]] = defaultdict(set)
    for row in form_rows:
        parsed = parse_date(row.get("date"))
        if parsed is None:
            continue
        dates_by_league_season[(row.get("league", ""), row.get("season", ""))].add(parsed)
    lookup: dict[tuple[str, str, date], int] = {}
    for key, dates in dates_by_league_season.items():
        for idx, fixture_date in enumerate(sorted(dates), start=1):
            lookup[(key[0], key[1], fixture_date)] = idx
    return lookup


def build_records(form_rows: list[dict[str, str]], current_rows: list[dict[str, str]], bt: Any) -> list[dict[str, Any]]:
    current_by_key = {bt.team_key(row): row for row in current_rows}
    matchday_lookup = build_matchday_lookup(form_rows)
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
            actual = pf(team.get("current_shots_for"))
            current_pred = pf(current.get("lambda_venue"), None) or pf(current.get("lambda_shots"), None)
            canonical_market = bt.canonical_team_shots_lambda(team, opp, use_market=True)
            canonical_no_market = bt.canonical_team_shots_lambda(team, opp, use_market=False)
            canonical_market_t12 = bt.canonical_team_shots_lambda(team, opp, use_market=True, use_trailing12=True)
            team_venue = str(team.get("venue", "")).strip()
            opp_venue = str(opp.get("venue", "")).strip()
            attack_input = bt.blended_prefer(team, bt.venue_field("shots_for", team_venue), "shots_for_avg")
            defence_input = bt.blended_prefer(opp, bt.venue_field("shots_against", opp_venue), "shots_against_avg")
            t12_ratio = bt.league_level_ratio(team, opp, metric_for="shots_for", metric_against="shots_against")
            fixture_date = parse_date(team.get("date"))
            if (
                actual is None
                or current_pred is None
                or canonical_market is None
                or canonical_no_market is None
                or canonical_market_t12 is None
                or fixture_date is None
            ):
                continue
            market_team = pf(team.get("market_team_win_prob"))
            market_opp = pf(team.get("market_opp_win_prob"))
            gap = (market_team - market_opp) if market_team is not None and market_opp is not None else None
            team_history = int(pf(team.get("r10_matches"), 0) or 0)
            opp_history = int(pf(opp.get("r10_matches"), 0) or 0)
            matchday = matchday_lookup.get((team.get("league", ""), team.get("season", ""), fixture_date))
            records.append(
                {
                    "date": fixture_date.isoformat(),
                    "league": team.get("league", ""),
                    "season": team.get("season", ""),
                    "team": team.get("team", ""),
                    "opponent": team.get("opponent", ""),
                    "venue": team.get("venue", ""),
                    "home_team": team.get("home_team", ""),
                    "away_team": team.get("away_team", ""),
                    "actual": actual,
                    "current": current_pred,
                    "canonical_market": canonical_market,
                    "canonical_no_market": canonical_no_market,
                    "canonical_market_t12": canonical_market_t12,
                    "attack_input": attack_input,
                    "defence_input": defence_input,
                    "quality_adjustment": bt.quality_adjustment(team, opp),
                    "market_adjustment": bt.market_game_state_adjustment(team),
                    "t12_ratio": t12_ratio,
                    "league_prior_shots_for_avg": pf(team.get("league_prior_shots_for_avg")),
                    "league_prior_shots_against_avg": pf(opp.get("league_prior_shots_against_avg")),
                    "league_t12_shots_for_avg": pf(team.get("league_t12_shots_for_avg")),
                    "league_t12_shots_against_avg": pf(opp.get("league_t12_shots_against_avg")),
                    "market_gap": round(gap, 4) if gap is not None else None,
                    "gap_bucket": gap_bucket(gap),
                    "matchday": matchday,
                    "matchday_bucket": matchday_bucket(matchday),
                    "team_history": team_history,
                    "opp_history": opp_history,
                    "min_history": min(team_history, opp_history),
                    "history_bucket": history_bucket(min(team_history, opp_history)),
                    "canonical_market_abs_error": abs(canonical_market - actual),
                    "current_abs_error": abs(current_pred - actual),
                }
            )
    return records


def build_payload(form_rows: list[dict[str, str]], current_rows: list[dict[str, str]]) -> dict[str, Any]:
    bt = load_backtest_module()
    records = build_records(form_rows, current_rows, bt)
    latest = max((parse_date(row.get("date")) for row in form_rows if parse_date(row.get("date"))), default=None)
    recent_cutoff = latest - timedelta(days=90) if latest else None
    recent_records = [
        record for record in records if recent_cutoff is not None and parse_date(record["date"]) is not None and parse_date(record["date"]) >= recent_cutoff
    ]
    pred_fields = ["current", "canonical_market", "canonical_no_market", "canonical_market_t12"]
    current_full = summarize_records(records, "current")
    current_recent = summarize_records(recent_records, "current")
    cap_read = {
        "market_cap_hurts_recent": (
            summarize_records(recent_records, "canonical_no_market").get("mae") is not None
            and summarize_records(recent_records, "canonical_market").get("mae") is not None
            and summarize_records(recent_records, "canonical_no_market")["mae"] < summarize_records(recent_records, "canonical_market")["mae"]
        ),
        "current_recent_vs_full_mae_delta": (
            round(current_recent["mae"] - current_full["mae"], 4)
            if current_recent.get("mae") is not None and current_full.get("mae") is not None
            else None
        ),
    }
    largest_errors = sorted(recent_records, key=lambda item: item["canonical_market_abs_error"], reverse=True)[:10]
    for item in largest_errors:
        item["canonical_market_error"] = round(item["canonical_market"] - item["actual"], 4)
        item["current_error"] = round(item["current"] - item["actual"], 4)
        item["canonical_no_market_error"] = round(item["canonical_no_market"] - item["actual"], 4)
        item["canonical_market_t12_error"] = round(item["canonical_market_t12"] - item["actual"], 4)
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "latest_form_date": latest.isoformat() if latest else None,
        "recent_cutoff": recent_cutoff.isoformat() if recent_cutoff else None,
        "summary": {
            "full_common": {field: summarize_records(records, field) for field in pred_fields},
            "last_90_common": {field: summarize_records(recent_records, field) for field in pred_fields},
            "cap_read": cap_read,
        },
        "last_90_by_league": grouped_summary(recent_records, "league", pred_fields),
        "last_90_by_gap_bucket": grouped_summary(recent_records, "gap_bucket", pred_fields),
        "last_90_by_matchday_bucket": grouped_summary(recent_records, "matchday_bucket", pred_fields),
        "last_90_by_history_bucket": grouped_summary(recent_records, "history_bucket", pred_fields),
        "largest_recent_canonical_market_errors": largest_errors,
    }


def render_summary_table(title: str, rows: list[dict[str, Any]], group_field: str) -> list[str]:
    lines = [
        f"## {title}",
        "",
        f"| {group_field} | N | Current MAE | Canonical market MAE | Cap disabled MAE | T12 replay MAE | Read |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        current = row["current"]
        market = row["canonical_market"]
        no_market = row["canonical_no_market"]
        t12 = row["canonical_market_t12"]
        read = "cap helps"
        if no_market.get("mae") is not None and market.get("mae") is not None and no_market["mae"] < market["mae"]:
            read = "cap hurts"
        if t12.get("mae") is not None and market.get("mae") is not None and t12["mae"] < market["mae"]:
            read += "; t12 helps"
        elif t12.get("mae") is not None and market.get("mae") is not None:
            read += "; t12 does not help"
        if market.get("mae") is not None and current.get("mae") is not None and market["mae"] > current["mae"]:
            read += "; canonical lags current"
        lines.append(
            f"| {row[group_field]} | {market.get('n', 0)} | {current.get('mae', '-')} | "
            f"{market.get('mae', '-')} | {no_market.get('mae', '-')} | {t12.get('mae', '-')} | {read} |"
        )
    lines.append("")
    return lines


def fmt_num(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def render_markdown(payload: dict[str, Any]) -> str:
    full = payload["summary"]["full_common"]
    recent = payload["summary"]["last_90_common"]
    cap = payload["summary"]["cap_read"]
    lines = [
        "# Team Shots Last-90 Diagnostic",
        "",
        f"Generated: {payload['generated_at']}",
        f"Latest form date: `{payload['latest_form_date']}`",
        f"Recent cutoff: `{payload['recent_cutoff']}`",
        "",
        "No live policy changed. This report diagnoses the count-lambda regression only.",
        "",
        "## Headline",
        "",
        "| Sample | Model | N | MAE | Bias | RMSE |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for sample_name, sample in (("full_common", full), ("last_90_common", recent)):
        for model_key in ("current", "canonical_market", "canonical_no_market", "canonical_market_t12"):
            item = sample[model_key]
            lines.append(
                f"| {sample_name} | {model_key} | {item.get('n', 0)} | {item.get('mae', '-')} | "
                f"{item.get('bias', '-')} | {item.get('rmse', '-')} |"
            )
    lines.extend(
        [
            "",
            "## Diagnostic Read",
            "",
            f"- Cap-disabled recent MAE beats capped recent MAE: `{'yes' if cap.get('market_cap_hurts_recent') else 'no'}`",
            f"- Current last-90 MAE minus current full-window MAE: `{cap.get('current_recent_vs_full_mae_delta')}`",
            "- If cap-disabled is better, the market-game-state cap is the first suspect. If not, inspect ingestion/history buckets before tuning.",
            "- `canonical_market_t12` is a trailing-12-month league-level normalization replay; it is diagnostic only, not a live policy.",
            "",
        ]
    )
    lines.extend(render_summary_table("Last-90 By League", payload["last_90_by_league"], "league"))
    lines.extend(render_summary_table("Last-90 By Win-Prob Gap Bucket", payload["last_90_by_gap_bucket"], "gap_bucket"))
    lines.extend(render_summary_table("Last-90 By Matchday Bucket", payload["last_90_by_matchday_bucket"], "matchday_bucket"))
    lines.extend(render_summary_table("Last-90 By History Bucket", payload["last_90_by_history_bucket"], "history_bucket"))
    lines.extend(
        [
            "## Largest Recent Canonical Market Errors",
            "",
            "| Date | League | Match | Team | Actual | Current | Canonical | Cap disabled | T12 replay | Gap bucket | Matchday | Min history |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for row in payload["largest_recent_canonical_market_errors"]:
        lines.append(
            f"| {row['date']} | {row['league']} | {row['home_team']} vs {row['away_team']} | {row['team']} | "
            f"{row['actual']:.1f} | {row['current']:.2f} | {row['canonical_market']:.2f} | "
            f"{row['canonical_no_market']:.2f} | {row['canonical_market_t12']:.2f} | {row['gap_bucket']} | "
            f"{row.get('matchday') or '-'} | {row['min_history']} |"
        )
    lines.append("")
    lines.extend(
        [
            "## Largest Error Input Spot Check",
            "",
            "| Date | League | Team | Attack input | Opp def input | Quality adj | Market adj | T12 ratio | Prior shots | T12 shots |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["largest_recent_canonical_market_errors"]:
        prior = row.get("league_prior_shots_for_avg")
        t12 = row.get("league_t12_shots_for_avg")
        lines.append(
            f"| {row['date']} | {row['league']} | {row['team']} | "
            f"{fmt_num(row.get('attack_input'))} | {fmt_num(row.get('defence_input'))} | "
            f"{fmt_num(row.get('quality_adjustment'), 3)} | {fmt_num(row.get('market_adjustment'), 3)} | "
            f"{fmt_num(row.get('t12_ratio'), 3)} | {fmt_num(prior)} | {fmt_num(t12)} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose team-shots recent count regression")
    parser.add_argument("--form", type=Path, default=DEFAULT_FORM)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
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
    print(f"Wrote {args.json_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
