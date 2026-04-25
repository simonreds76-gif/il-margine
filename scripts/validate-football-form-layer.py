#!/usr/bin/env python3
"""Validate canonical football form outputs for schema drift and freshness.

This is deliberately boring ops plumbing: fail fast when upstream CSV schemas or
coverage change enough that downstream model comparisons are no longer reliable.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "football-form"

TEAM_MATCH_REQUIRED = [
    "date",
    "league",
    "season",
    "team",
    "team_key",
    "opponent",
    "opponent_key",
    "venue",
    "shots_for",
    "shots_against",
    "corners_for",
    "corners_against",
    "market_team_win_prob",
]

ROLLING_REQUIRED = [
    "date",
    "league",
    "season",
    "team",
    "team_key",
    "opponent",
    "opponent_key",
    "venue",
    "current_shots_for",
    "current_shots_against",
    "current_corners_for",
    "current_corners_against",
    "market_team_win_prob",
    "market_opp_win_prob",
    "r10_matches",
    "r10_shots_for_avg",
    "r10_shots_against_avg",
    "r10_corners_for_avg",
    "r10_corners_against_avg",
]

CRITICAL_COVERAGE = [
    "shots_for",
    "shots_against",
    "corners_for",
    "corners_against",
]

ROLLING_CRITICAL_COVERAGE = [
    "current_shots_for",
    "current_shots_against",
    "current_corners_for",
    "current_corners_against",
]


@dataclass
class ValidationIssue:
    level: str
    code: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"level": self.level, "code": self.code, "detail": self.detail}


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text, text[:10]):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    return None


def has_value(value: Any) -> bool:
    return str(value or "").strip() not in {"", "nan", "None"}


def load_csv(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def coverage(rows: list[dict[str, Any]], field: str) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if has_value(row.get(field))) / len(rows)


def duplicate_count(rows: list[dict[str, Any]], fields: list[str]) -> int:
    seen: set[tuple[str, ...]] = set()
    duplicates = 0
    for row in rows:
        key = tuple(str(row.get(field, "")).strip() for field in fields)
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
    return duplicates


def safe_code(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def league_freshness(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest_by_league: dict[str, date] = {}
    today = datetime.now(UTC).date()
    for row in rows:
        league = str(row.get("league") or "unknown").strip() or "unknown"
        parsed = parse_date(row.get("date"))
        if parsed is None:
            continue
        if league not in latest_by_league or parsed > latest_by_league[league]:
            latest_by_league[league] = parsed
    return {
        league: {"latest_date": latest.isoformat(), "age_days": (today - latest).days}
        for league, latest in sorted(latest_by_league.items())
    }


def validate_file(
    *,
    label: str,
    fields: list[str],
    rows: list[dict[str, Any]],
    required: list[str],
    critical_coverage: list[str],
    min_rows: int,
    min_coverage: float,
    max_age_days: int,
) -> tuple[dict[str, Any], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    field_set = set(fields)
    missing = [field for field in required if field not in field_set]
    if missing:
        issues.append(ValidationIssue("error", f"{label}_missing_fields", ", ".join(missing)))

    if len(rows) < min_rows:
        issues.append(ValidationIssue("error", f"{label}_row_count_low", f"{len(rows)} rows < {min_rows}"))

    dates = [parsed for row in rows if (parsed := parse_date(row.get("date")))]
    latest = max(dates) if dates else None
    age_days = (datetime.now(UTC).date() - latest).days if latest else None
    if latest is None:
        issues.append(ValidationIssue("error", f"{label}_no_dates", "No parseable date values"))
    elif age_days is not None and age_days > max_age_days:
        issues.append(
            ValidationIssue(
                "error",
                f"{label}_stale",
                f"latest date {latest.isoformat()} is {age_days}d old; max {max_age_days}d",
            )
        )

    league_dates = league_freshness(rows)
    for league, summary in league_dates.items():
        league_age = summary["age_days"]
        if league_age is not None and league_age > max_age_days:
            issues.append(
                ValidationIssue(
                    "error",
                    f"{label}_{safe_code(league)}_stale",
                    f"{league} latest date {summary['latest_date']} is {league_age}d old; max {max_age_days}d",
                )
            )

    coverage_summary = {field: round(coverage(rows, field), 4) for field in critical_coverage if field in field_set}
    for field, ratio in coverage_summary.items():
        if ratio < min_coverage:
            issues.append(
                ValidationIssue(
                    "error",
                    f"{label}_{field}_coverage_low",
                    f"{field} coverage {ratio:.1%} < {min_coverage:.1%}",
                )
            )

    market_coverage = coverage(rows, "market_team_win_prob") if "market_team_win_prob" in field_set else 0.0
    if market_coverage < 0.50:
        issues.append(
            ValidationIssue(
                "warning",
                f"{label}_market_coverage_low",
                f"market_team_win_prob coverage {market_coverage:.1%}",
            )
        )

    xg_coverage = coverage(rows, "xg_for") if "xg_for" in field_set else coverage(rows, "current_xg_for")
    if xg_coverage and xg_coverage < 0.20:
        issues.append(
            ValidationIssue("warning", f"{label}_xg_coverage_low", f"xG coverage {xg_coverage:.1%}")
        )

    duplicates = duplicate_count(rows, ["date", "league", "team_key", "opponent_key", "venue"])
    if duplicates:
        issues.append(ValidationIssue("warning", f"{label}_duplicates", f"{duplicates} duplicate team rows"))

    return (
        {
            "rows": len(rows),
            "field_count": len(fields),
            "latest_date": latest.isoformat() if latest else None,
            "age_days": age_days,
            "critical_coverage": coverage_summary,
            "league_freshness": league_dates,
            "market_team_win_prob_coverage": round(market_coverage, 4),
            "xg_coverage": round(xg_coverage, 4),
            "duplicates": duplicates,
        },
        issues,
    )


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Football Form Layer Validation",
        "",
        f"Generated: {payload['checked_at']}",
        f"Status: **{payload['status'].upper()}**",
        "",
        "## Files",
        "",
        "| File | Rows | Latest date | Market coverage | xG coverage | Duplicates |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for label, summary in payload["files"].items():
        lines.append(
            f"| {label} | {summary['rows']} | {summary['latest_date'] or '-'} | "
            f"{summary['market_team_win_prob_coverage']:.1%} | {summary['xg_coverage']:.1%} | {summary['duplicates']} |"
        )
    lines.extend(["", "## Issues", ""])
    if payload["issues"]:
        for issue in payload["issues"]:
            lines.append(f"- **{issue['level']}** `{issue['code']}`: {issue['detail']}")
    else:
        lines.append("- No validation issues.")
    lines.extend(["", "## Per-League Freshness", ""])
    for label, summary in payload["files"].items():
        lines.extend(
            [
                f"### {label}",
                "",
                "| League | Latest date | Age days |",
                "| --- | --- | ---: |",
            ]
        )
        for league, item in summary.get("league_freshness", {}).items():
            lines.append(f"| {league} | {item['latest_date']} | {item['age_days']} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate canonical football form layer outputs.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-rows", type=int, default=10_000)
    parser.add_argument("--min-critical-coverage", type=float, default=0.95)
    parser.add_argument("--max-age-days", type=int, default=21)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--report-out", type=Path)
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir
    json_out = args.json_out or output_dir / "team-form-validation.json"
    report_out = args.report_out or output_dir / "team-form-validation.md"

    match_fields, match_rows = load_csv(output_dir / "team-match-base.csv")
    rolling_fields, rolling_rows = load_csv(output_dir / "team-rolling-form.csv")

    files: dict[str, Any] = {}
    issues: list[ValidationIssue] = []
    match_summary, match_issues = validate_file(
        label="team_match_base",
        fields=match_fields,
        rows=match_rows,
        required=TEAM_MATCH_REQUIRED,
        critical_coverage=CRITICAL_COVERAGE,
        min_rows=args.min_rows,
        min_coverage=args.min_critical_coverage,
        max_age_days=args.max_age_days,
    )
    files["team-match-base.csv"] = match_summary
    issues.extend(match_issues)

    rolling_summary, rolling_issues = validate_file(
        label="team_rolling_form",
        fields=rolling_fields,
        rows=rolling_rows,
        required=ROLLING_REQUIRED,
        critical_coverage=ROLLING_CRITICAL_COVERAGE,
        min_rows=args.min_rows,
        min_coverage=args.min_critical_coverage,
        max_age_days=args.max_age_days,
    )
    files["team-rolling-form.csv"] = rolling_summary
    issues.extend(rolling_issues)

    if match_rows and rolling_rows and len(match_rows) != len(rolling_rows):
        issues.append(
            ValidationIssue(
                "error",
                "row_count_mismatch",
                f"team-match-base has {len(match_rows)} rows; team-rolling-form has {len(rolling_rows)}",
            )
        )

    errors = [issue for issue in issues if issue.level == "error"]
    payload = {
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "status": "error" if errors else ("warning" if issues else "ok"),
        "files": files,
        "issues": [issue.as_dict() for issue in issues],
    }

    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_out.write_text(render_markdown(payload), encoding="utf-8")

    print(f"Validation status: {payload['status']}")
    print(f"Wrote {json_out.relative_to(ROOT)}")
    print(f"Wrote {report_out.relative_to(ROOT)}")
    return 1 if args.fail_on_error and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
