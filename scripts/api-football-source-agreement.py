#!/usr/bin/env python3
"""Compare API-Football count definitions with the Football-Data archive."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Optional

from settlement_utils import normalize_team_name


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = ROOT / "data" / "football-form" / "api-football-counts.csv"
DEFAULT_REFERENCE = ROOT / "data" / "team-shots" / "historical" / "all-historical-matches.csv"
DEFAULT_HISTORICAL_REFERENCE_DIR = ROOT / "data" / "corners-ou" / "historical"
DEFAULT_JSON = ROOT / "data" / "football-form" / "api-football-source-agreement.json"
DEFAULT_MD = ROOT / "data" / "football-form" / "api-football-source-agreement.md"
FIELD_MAP = {
    "shots": (("home_shots", "HS"), ("away_shots", "AS")),
    "shots_on_target": (("home_sot", "HST"), ("away_sot", "AST")),
    "corners": (("home_corners", "HC"), ("away_corners", "AC")),
    "fouls": (("home_fouls", "HF"), ("away_fouls", "AF")),
    "yellow_cards": (("home_yellow_cards", "HY"), ("away_yellow_cards", "AY")),
    "red_cards": (("home_red_cards", "HR"), ("away_red_cards", "AR")),
}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def load_reference_rows(
    primary: Path = DEFAULT_REFERENCE,
    historical_directory: Path = DEFAULT_HISTORICAL_REFERENCE_DIR,
) -> list[dict[str, str]]:
    rows = load_csv(primary)
    for path in sorted(historical_directory.glob("*-2024-2025.csv")):
        rows.extend(load_csv(path))
    deduplicated: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = fixture_key(row, api=False)
        if key is not None:
            deduplicated[key] = row
    return list(deduplicated.values())


def parse_date(value: str) -> Optional[str]:
    text = str(value or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def fixture_key(row: dict[str, str], *, api: bool) -> Optional[tuple[str, str, str]]:
    day = parse_date(row.get("date" if api else "Date", ""))
    home = normalize_team_name(row.get("home_team" if api else "HomeTeam", ""))
    away = normalize_team_name(row.get("away_team" if api else "AwayTeam", ""))
    if not day or not home or not away:
        return None
    return day, home, away


def numeric(value: object) -> Optional[float]:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def build_agreement(api_rows: list[dict[str, str]], reference_rows: list[dict[str, str]]) -> dict:
    reference = {
        key: row
        for row in reference_rows
        if (key := fixture_key(row, api=False)) is not None
    }
    matched: list[tuple[dict[str, str], dict[str, str]]] = []
    for row in api_rows:
        key = fixture_key(row, api=True)
        if key is not None and key in reference:
            matched.append((row, reference[key]))

    fields = {}
    for label, pairs in FIELD_MAP.items():
        differences: list[float] = []
        for api_row, reference_row in matched:
            for api_field, reference_field in pairs:
                left = numeric(api_row.get(api_field))
                right = numeric(reference_row.get(reference_field))
                if left is not None and right is not None:
                    differences.append(abs(left - right))
        fields[label] = {
            "comparable_team_values": len(differences),
            "possible_team_values": len(matched) * 2,
            "coverage_pct": round((len(differences) / (len(matched) * 2) * 100) if matched else 0.0, 1),
            "exact_pct": round((sum(diff == 0 for diff in differences) / len(differences) * 100) if differences else 0.0, 1),
            "within_one_pct": round((sum(diff <= 1 for diff in differences) / len(differences) * 100) if differences else 0.0, 1),
            "mae": round(mean(differences), 3) if differences else None,
        }

    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "ok" if matched else "no_overlap",
        "api_rows": len(api_rows),
        "latest_api_fixture_date": max((parse_date(row.get("date", "")) or "" for row in api_rows), default="") or None,
        "reference_rows": len(reference_rows),
        "matched_fixtures": len(matched),
        "match_rate_pct": round((len(matched) / len(api_rows) * 100) if api_rows else 0.0, 1),
        "fields": fields,
        "model_use": "diagnostic_only_until_definitions_and_coverage_are_accepted",
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# API-Football Source Agreement",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Status: {payload['status']}",
        f"- Fixture overlap: {payload['matched_fixtures']}/{payload['api_rows']} API rows ({payload['match_rate_pct']:.1f}%)",
        "- Decision: diagnostic only; no new field is wired into a model by this report.",
        "",
        "| Field | Comparable values | Coverage | Exact | Within 1 | MAE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["fields"].items():
        mae = "-" if row["mae"] is None else f"{row['mae']:.3f}"
        lines.append(
            f"| {label.replace('_', ' ').title()} | {row['comparable_team_values']} | "
            f"{row['coverage_pct']:.1f}% | {row['exact_pct']:.1f}% | "
            f"{row['within_one_pct']:.1f}% | {mae} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit API-Football vs Football-Data count agreement.")
    parser.add_argument("--api", type=Path, default=DEFAULT_API)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--historical-reference-dir", type=Path, default=DEFAULT_HISTORICAL_REFERENCE_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--allow-empty", action="store_true")
    args = parser.parse_args()

    payload = build_agreement(
        load_csv(args.api),
        load_reference_rows(args.reference, args.historical_reference_dir),
    )
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_markdown(payload), encoding="utf-8")
    print(
        f"API-Football agreement: {payload['matched_fixtures']}/{payload['api_rows']} fixtures, "
        f"status={payload['status']}"
    )
    return 0 if payload["matched_fixtures"] or args.allow_empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
