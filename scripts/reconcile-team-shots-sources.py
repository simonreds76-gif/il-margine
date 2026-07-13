#!/usr/bin/env python3
"""Reconcile the unified team-shots artifact against the historical spine."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from settlement_utils import normalize_team_name


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE = ROOT / "data" / "team-shots" / "understat" / "all-understat-matches.csv"
DEFAULT_REFERENCE = ROOT / "data" / "corners-ou" / "historical" / "all-historical-matches.csv"
DEFAULT_REPORT = ROOT / "data" / "team-shots" / "understat" / "source-reconciliation.json"

COUNT_FIELDS = {
    "home_shots": ("home_shots", "HS"),
    "away_shots": ("away_shots", "AS"),
    "home_sot": ("home_sot", "HST"),
    "away_sot": ("away_sot", "AST"),
    "home_corners": ("home_corners", "HC"),
    "away_corners": ("away_corners", "AC"),
}


def parse_date(value: Any) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def season_start(value: Any) -> int | None:
    match = re.search(r"(20\d{2})", str(value or ""))
    return int(match.group(1)) if match else None


def count(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        parse_date(row.get("date") or row.get("Date")),
        str(row.get("league") or "").strip().lower(),
        normalize_team_name(str(row.get("home_team") or row.get("HomeTeam") or "")),
        normalize_team_name(str(row.get("away_team") or row.get("AwayTeam") or "")),
    )


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def reconcile(candidate_path: Path, reference_path: Path) -> dict[str, Any]:
    candidate_rows = load_rows(candidate_path)
    reference_rows = load_rows(reference_path)

    scope = {
        (str(row.get("league") or "").strip().lower(), season_start(row.get("season")))
        for row in candidate_rows
    }
    reference_scoped = [
        row
        for row in reference_rows
        if (str(row.get("league") or "").strip().lower(), season_start(row.get("season"))) in scope
    ]

    candidate_index = {key(row): row for row in candidate_rows if all(key(row))}
    reference_index = {key(row): row for row in reference_scoped if all(key(row))}
    common = sorted(candidate_index.keys() & reference_index.keys())

    mismatches: dict[str, int] = {field: 0 for field in COUNT_FIELDS}
    absolute_delta: dict[str, float] = {field: 0.0 for field in COUNT_FIELDS}
    compared: dict[str, int] = {field: 0 for field in COUNT_FIELDS}
    examples: list[dict[str, Any]] = []

    for match_key in common:
        candidate = candidate_index[match_key]
        reference = reference_index[match_key]
        row_deltas: dict[str, int] = {}
        for field, (candidate_field, reference_field) in COUNT_FIELDS.items():
            candidate_value = count(candidate.get(candidate_field))
            reference_value = count(reference.get(reference_field))
            if candidate_value is None or reference_value is None:
                continue
            compared[field] += 1
            delta = candidate_value - reference_value
            absolute_delta[field] += abs(delta)
            if delta:
                mismatches[field] += 1
                row_deltas[field] = delta
        if row_deltas and len(examples) < 20:
            examples.append({"key": match_key, "deltas": row_deltas})

    candidate_only = candidate_index.keys() - reference_index.keys()
    reference_only = reference_index.keys() - candidate_index.keys()
    coverage = len(common) / len(candidate_index) if candidate_index else 0.0
    source_counts = Counter(str(row.get("source") or "missing") for row in candidate_rows)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate": display_path(candidate_path),
        "reference": display_path(reference_path),
        "candidate_rows": len(candidate_rows),
        "reference_rows_in_scope": len(reference_scoped),
        "matched_rows": len(common),
        "candidate_match_coverage": round(coverage, 6),
        "candidate_only_rows": len(candidate_only),
        "reference_only_rows": len(reference_only),
        "source_counts": dict(sorted(source_counts.items())),
        "field_checks": {
            field: {
                "compared": compared[field],
                "mismatches": mismatches[field],
                "mean_absolute_delta": round(absolute_delta[field] / compared[field], 6)
                if compared[field]
                else None,
            }
            for field in COUNT_FIELDS
        },
        "mismatch_examples": examples,
        "passes": coverage >= 0.95 and not any(mismatches.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile team-shots counts against the historical spine")
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = reconcile(args.candidate, args.reference)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "Team-shots source reconciliation: "
        f"matched={report['matched_rows']}/{report['candidate_rows']} "
        f"coverage={report['candidate_match_coverage']:.1%} passes={report['passes']}"
    )
    print(f"Report: {args.report}")
    return 1 if args.strict and not report["passes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
