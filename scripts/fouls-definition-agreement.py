#!/usr/bin/env python3
"""Apply the registered Team Fouls settlement-definition agreement gate."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DEFAULT_AGREEMENT = ROOT / "data" / "football-form" / "api-football-source-agreement.json"
DEFAULT_FOTMOB = ROOT / "data" / "football-form" / "team-fouls-fotmob-agreement.json"
DEFAULT_JSON = ROOT / "data" / "football-form" / "team-fouls-definition-agreement.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "team-fouls-definition-agreement.md"
MIN_TEAM_VALUES = 200
MIN_WITHIN_ONE_PCT = 97.0


def evaluate(api_agreement: dict[str, Any], fotmob_agreement: dict[str, Any] | None = None) -> dict[str, Any]:
    fouls = (api_agreement.get("fields") or {}).get("fouls") or {}
    comparable = int(fouls.get("comparable_team_values") or 0)
    within_one = float(fouls.get("within_one_pct") or 0.0)
    api_pass = comparable >= MIN_TEAM_VALUES and within_one >= MIN_WITHIN_ONE_PCT
    fotmob_summary = (fotmob_agreement or {}).get("summary") or {}
    fotmob_values = int(fotmob_summary.get("comparable_team_values") or 0)
    fotmob_within = float(fotmob_summary.get("within_one_pct") or 0.0)
    fotmob_pass = fotmob_values >= MIN_TEAM_VALUES and fotmob_within >= MIN_WITHIN_ONE_PCT
    if comparable == 0 and fotmob_values == 0:
        status = "NO_OVERLAP"
    elif api_pass and fotmob_pass:
        status = "PASS"
    else:
        status = "WAIT_OR_FAIL"
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": status,
        "settlement_source_authorized": api_pass and fotmob_pass,
        "requirements": {
            "minimum_comparable_team_values": MIN_TEAM_VALUES,
            "minimum_within_one_pct": MIN_WITHIN_ONE_PCT,
            "independent_sources_required": ["api-football", "fotmob"],
        },
        "api_football": {
            "matched_fixtures": int(api_agreement.get("matched_fixtures") or 0),
            "comparable_team_values": comparable,
            "exact_pct": fouls.get("exact_pct"),
            "within_one_pct": within_one,
            "mae": fouls.get("mae"),
            "passed": api_pass,
        },
        "fotmob": {
            "comparable_team_values": fotmob_values,
            "within_one_pct": fotmob_within,
            "mae": fotmob_summary.get("mae"),
            "passed": fotmob_pass,
        },
        "decision": "Settlement definitions remain blocked until both independent sources pass the registered agreement threshold.",
    }


def render(payload: dict[str, Any]) -> str:
    api = payload["api_football"]
    fotmob = payload["fotmob"]
    return "\n".join(
        [
            "# Team Fouls v1: M2 Definition Agreement",
            "",
            f"Generated: {payload['generated_at']}",
            f"Status: **{payload['status'].replace('_', ' ')}**",
            "",
            f"- API-Football comparable team values: {api['comparable_team_values']} (required {MIN_TEAM_VALUES}).",
            f"- API-Football within one foul: {api['within_one_pct']:.1f}% (required {MIN_WITHIN_ONE_PCT:.1f}%).",
            f"- API-Football MAE: {api['mae'] if api['mae'] is not None else '-'}.",
            f"- FotMob comparable team values: {fotmob['comparable_team_values']} (required {MIN_TEAM_VALUES}).",
            f"- FotMob within one foul: {fotmob['within_one_pct']:.1f}% (required {MIN_WITHIN_ONE_PCT:.1f}%).",
            f"- Settlement source authorized: {'yes' if payload['settlement_source_authorized'] else 'no'}.",
            "",
            payload["decision"],
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Team Fouls source-definition agreement.")
    parser.add_argument("--agreement", type=Path, default=DEFAULT_AGREEMENT)
    parser.add_argument("--fotmob", type=Path, default=DEFAULT_FOTMOB)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--allow-empty", action="store_true")
    args = parser.parse_args()
    source = json.loads(args.agreement.read_text(encoding="utf-8")) if args.agreement.exists() else {}
    fotmob = json.loads(args.fotmob.read_text(encoding="utf-8")) if args.fotmob.exists() else {}
    payload = evaluate(source, fotmob)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render(payload), encoding="utf-8")
    print(f"Team Fouls M2: {payload['status']}")
    return 0 if payload["api_football"]["comparable_team_values"] or args.allow_empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
