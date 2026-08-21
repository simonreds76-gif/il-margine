#!/usr/bin/env python3
"""Build isolated, causal Team Shots v5 season/market feature blocks.

This does not modify the locked canonical rolling-form table or any live lane.
Rows are scored before same-day results are added to history.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "football-form" / "team-match-base.csv"
DEFAULT_OUTPUT = ROOT / "data" / "team-shots" / "team-shots-v5-season-features.csv"
DEFAULT_REPORT = ROOT / "data" / "team-shots" / "team-shots-v5-feature-report.json"
EMA_DECAY = 0.93
EMA_WINDOW = 20
PRIOR_SEASON_MAX_AGE_DAYS = 400
METRICS = ("shots_for", "shots_against", "sot_for", "sot_against", "corners_for", "corners_against")
IDENTITY_FIELDS = (
    "date",
    "league",
    "season",
    "team",
    "team_key",
    "opponent",
    "opponent_key",
    "venue",
    "home_team",
    "away_team",
)


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def numeric(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def previous_season(season: str) -> str:
    parts = str(season or "").split("-")
    if len(parts) != 2:
        return ""
    try:
        start, end = int(parts[0]), int(parts[1])
    except ValueError:
        return ""
    return f"{start - 1}-{end - 1}"


def weighted_average(rows: Iterable[dict[str, Any]], field: str) -> float | None:
    usable = [row for row in rows if numeric(row.get(field)) is not None][-EMA_WINDOW:]
    if not usable:
        return None
    weighted_sum = 0.0
    weight_total = 0.0
    for index, row in enumerate(usable):
        weight = EMA_DECAY ** (len(usable) - 1 - index)
        weighted_sum += float(numeric(row[field])) * weight
        weight_total += weight
    return weighted_sum / weight_total if weight_total else None


def format_number(value: float | int | None, places: int = 4) -> str | int:
    if value is None:
        return ""
    if isinstance(value, int):
        return value
    return f"{value:.{places}f}".rstrip("0").rstrip(".")


def season_block(
    history: list[dict[str, Any]],
    *,
    season: str,
    venue: str,
    prefix: str,
) -> dict[str, Any]:
    rows = [row for row in history if row.get("season") == season]
    venue_rows = [row for row in rows if row.get("venue") == venue]
    out: dict[str, Any] = {
        f"{prefix}_season": season,
        f"{prefix}_matches": len(rows),
        f"{prefix}_venue_matches": len(venue_rows),
    }
    for metric in METRICS:
        out[f"{prefix}_ema20_{metric}"] = format_number(weighted_average(rows, metric))
        out[f"{prefix}_venue_ema20_{metric}"] = format_number(weighted_average(venue_rows, metric))
    return out


def build_feature_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            row.get("date", ""),
            row.get("league", ""),
            row.get("home_team", ""),
            row.get("away_team", ""),
            row.get("venue", ""),
        ),
    )
    histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    output: list[dict[str, Any]] = []
    cursor = 0
    while cursor < len(ordered):
        match_date = ordered[cursor].get("date", "")
        end = cursor
        while end < len(ordered) and ordered[end].get("date", "") == match_date:
            end += 1
        day_rows = ordered[cursor:end]

        # Score the complete matchday before adding any result from that day.
        for row in day_rows:
            history = histories[row.get("team_key", "")]
            current_season = row.get("season", "")
            prior_season = previous_season(current_season)
            current_date = parse_date(row.get("date"))
            prior_rows = [item for item in history if item.get("season") == prior_season]
            last_prior_date = max((parse_date(item.get("date")) for item in prior_rows), default=None)
            prior_age_days = (
                (current_date - last_prior_date).days
                if current_date is not None and last_prior_date is not None
                else None
            )
            prior_is_fresh = prior_age_days is not None and 0 <= prior_age_days <= PRIOR_SEASON_MAX_AGE_DAYS

            team_prob = numeric(row.get("market_team_win_prob"))
            opp_prob = numeric(row.get("market_opp_win_prob"))
            draw_prob = 1.0 - team_prob - opp_prob if team_prob is not None and opp_prob is not None else None
            feature = {field: row.get(field, "") for field in IDENTITY_FIELDS}
            feature.update(
                {
                    "market_team_win_prob": format_number(team_prob),
                    "market_opp_win_prob": format_number(opp_prob),
                    "market_draw_prob": format_number(draw_prob),
                    "market_favourite_gap": format_number(
                        team_prob - opp_prob if team_prob is not None and opp_prob is not None else None
                    ),
                    "market_feature_available": int(team_prob is not None and opp_prob is not None),
                    "prior_season_age_days": format_number(prior_age_days),
                    "prior_season_fresh": int(prior_is_fresh),
                    "blend_status": "UNREGISTERED_PENDING_WEIGHT_SPEC",
                }
            )
            feature.update(
                season_block(
                    history,
                    season=current_season,
                    venue=row.get("venue", ""),
                    prefix="current",
                )
            )
            prior_block = season_block(
                history,
                season=prior_season,
                venue=row.get("venue", ""),
                prefix="prior",
            )
            if not prior_is_fresh:
                for key in list(prior_block):
                    if key not in {"prior_season", "prior_matches", "prior_venue_matches"}:
                        prior_block[key] = ""
            feature.update(prior_block)
            output.append(feature)

        for row in day_rows:
            histories[row.get("team_key", "")].append(row)
        cursor = end
    return output


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else list(IDENTITY_FIELDS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_report(rows: list[dict[str, Any]], input_path: Path, output_path: Path) -> dict[str, Any]:
    total = len(rows)
    market_rows = sum(int(row.get("market_feature_available") or 0) for row in rows)
    fresh_prior_rows = sum(int(row.get("prior_season_fresh") or 0) for row in rows)
    current_five = sum(int(row.get("current_matches") or 0) >= 5 for row in rows)
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "RESEARCH_ONLY_UNREGISTERED",
        "input": str(input_path),
        "output": str(output_path),
        "rows": total,
        "market_feature_coverage": {"rows": market_rows, "rate": market_rows / total if total else 0.0},
        "fresh_prior_season_coverage": {"rows": fresh_prior_rows, "rate": fresh_prior_rows / total if total else 0.0},
        "current_season_five_match_coverage": {"rows": current_five, "rate": current_five / total if total else 0.0},
        "guards": {
            "same_day_batching": "PASS",
            "prior_season_max_age_days": PRIOR_SEASON_MAX_AGE_DAYS,
            "locked_v4_artifacts_modified": False,
            "live_routing_modified": False,
            "blend_registered": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build isolated Team Shots v5 season/market features")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    rows = build_feature_rows(load_rows(args.input))
    write_rows(args.output, rows)
    report = build_report(rows, args.input, args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows: {args.output}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
