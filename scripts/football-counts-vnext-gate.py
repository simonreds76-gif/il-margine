#!/usr/bin/env python3
"""Build the single weekly gate snapshot for football count-model experiments."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEAM_RESULTS = ROOT / "data" / "team-shots" / "team-shots-v4-fold-results.csv"
DEFAULT_TEAM_REPORT = ROOT / "data" / "team-shots" / "team-shots-v4-fold-report.md"
DEFAULT_CORNERS_RESULTS = ROOT / "data" / "corners-ou" / "corners-v3-fold-results.csv"
DEFAULT_CORNERS_REPORT = ROOT / "data" / "corners-ou" / "corners-v3-fold-report.md"
DEFAULT_JSON = ROOT / "data" / "football-form" / "football-counts-vnext-gate.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "football-counts-vnext-gate.md"


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(row: dict[str, str], field: str) -> float | None:
    try:
        return float(row[field])
    except (KeyError, TypeError, ValueError):
        return None


def team_count_gate(rows: list[dict[str, str]], report: str) -> bool:
    return len(rows) == 2 and "Count-distribution gate: **PASS**" in report and all(
        row.get("status") == "OK"
        and (as_float(row, "hierarchical_mle_brier") or 1.0) < (as_float(row, "fixed_alpha_025_brier") or 0.0)
        and (as_float(row, "hierarchical_mle_log_loss") or 1.0) <= (as_float(row, "fixed_alpha_025_log_loss") or 0.0)
        for row in rows
    )


def corners_count_gate(rows: list[dict[str, str]], report: str) -> bool:
    return len(rows) == 2 and "Count-model gate: **PASS**" in report and all(
        row.get("status") == "OK"
        and (as_float(row, "v3_mae") or 1.0) < (as_float(row, "baseline_mae") or 0.0)
        and (as_float(row, "v3_brier") or 1.0) < (as_float(row, "baseline_brier") or 0.0)
        and (as_float(row, "v3_log_loss") or 1.0) < (as_float(row, "baseline_log_loss") or 0.0)
        for row in rows
    )


def build_payload(
    team_rows: list[dict[str, str]],
    team_report: str,
    corners_rows: list[dict[str, str]],
    corners_report: str,
) -> dict[str, Any]:
    team_pass = team_count_gate(team_rows, team_report)
    corners_pass = corners_count_gate(corners_rows, corners_report)
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "team_shots_v4": {
            "count_gate": "PASS" if team_pass else "FAIL",
            "prospective_status": "AUTHORIZED_SHADOW" if team_pass else "BLOCKED",
            "market_gate": "BLOCKED_PENDING_2026_27_TRUE_CLOSE_SAMPLE",
            "live_routing": False,
        },
        "corners_v3": {
            "count_gate": "PASS" if corners_pass else "FAIL",
            "prospective_status": "AUTHORIZED_SHADOW" if corners_pass else "BLOCKED",
            "market_gate": "BLOCKED_PENDING_2026_27_PINNACLE_SAMPLE",
            "live_routing": False,
        },
    }


def render(payload: dict[str, Any]) -> str:
    team = payload["team_shots_v4"]
    corners = payload["corners_v3"]
    return "\n".join(
        [
            "# Football Counts vNext Gate",
            "",
            f"- Generated: {payload['generated_at']}",
            "- This snapshot cannot promote or route bets.",
            "",
            "## Team Shots v4",
            f"- Count gate: **{team['count_gate']}**",
            f"- Prospective status: **{team['prospective_status']}**",
            f"- Market gate: **{team['market_gate']}**",
            "- Live routing: unchanged / disabled",
            "",
            "## Corners v3",
            f"- Count gate: **{corners['count_gate']}**",
            f"- Prospective status: **{corners['prospective_status']}**",
            f"- Market gate: **{corners['market_gate']}**",
            "- Live routing: unchanged / disabled",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-results", type=Path, default=DEFAULT_TEAM_RESULTS)
    parser.add_argument("--team-report", type=Path, default=DEFAULT_TEAM_REPORT)
    parser.add_argument("--corners-results", type=Path, default=DEFAULT_CORNERS_RESULTS)
    parser.add_argument("--corners-report", type=Path, default=DEFAULT_CORNERS_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    payload = build_payload(
        load_csv(args.team_results),
        args.team_report.read_text(encoding="utf-8") if args.team_report.exists() else "",
        load_csv(args.corners_results),
        args.corners_report.read_text(encoding="utf-8") if args.corners_report.exists() else "",
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(render(payload), encoding="utf-8")
    print(f"Wrote {args.json.relative_to(ROOT)}")
    print(f"Wrote {args.report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
