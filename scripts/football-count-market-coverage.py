#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from football_count_markets import classify_market


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = ROOT / "data" / "football-form" / "football-count-market-inventory.csv"
DEFAULT_JSON = ROOT / "data" / "football-form" / "football-count-market-coverage.json"
DEFAULT_REPORT = ROOT / "data" / "football-form" / "football-count-market-coverage.md"
DEFAULT_LEGACY_GLOB = str(ROOT / "data" / "assist-value" / "assist-market-audit-*.csv")
TARGET_CATEGORIES = (
    "team_fouls_total",
    "match_fouls_total",
    "team_cards_total",
    "match_cards_total",
    "player_fouls_committed",
    "player_fouled",
    "player_cards",
)


def read_rows(inventory: Path, legacy_glob: str) -> list[dict]:
    rows: list[dict] = []
    if inventory.exists():
        with inventory.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                rows.append({**row, "source_schema": "paired_inventory"})

    for raw_path in sorted(glob.glob(legacy_glob)):
        path = Path(raw_path)
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                rows.append(
                    {
                        "captured_at": "",
                        "event_id": row.get("event_id", ""),
                        "kickoff_at": row.get("kickoff_at", ""),
                        "bookmaker": row.get("bookmaker", ""),
                        "competition": row.get("league", ""),
                        "home_team": row.get("home_team", ""),
                        "away_team": row.get("away_team", ""),
                        "market_name": row.get("market_name", ""),
                        "market_category": classify_market(row.get("market_name", "")),
                        "odds_count": row.get("odds_count", ""),
                        "line_count": "",
                        "paired_line_count": "",
                        "sample_labels": row.get("sample_labels", ""),
                        "source_schema": "legacy_name_audit",
                    }
                )
    return rows


def _int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def summarize(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        category = str(row.get("market_category") or classify_market(row.get("market_name", "")))
        if category in TARGET_CATEGORIES:
            grouped[category].append(row)

    categories: dict[str, dict] = {}
    for category in TARGET_CATEGORIES:
        category_rows = grouped.get(category, [])
        events = {str(row.get("event_id") or "") for row in category_rows if row.get("event_id")}
        paired_events = {
            str(row.get("event_id") or "")
            for row in category_rows
            if _int(row.get("paired_line_count")) > 0 and row.get("event_id")
        }
        unknown_pairing_events = {
            str(row.get("event_id") or "")
            for row in category_rows
            if row.get("source_schema") == "legacy_name_audit" and row.get("event_id")
        }
        status = "PAIRED_PRICES_OBSERVED" if paired_events else "MARKET_NAME_ONLY" if events else "NOT_OBSERVED"
        categories[category] = {
            "status": status,
            "rows": len(category_rows),
            "events": len(events),
            "paired_price_events": len(paired_events),
            "pairing_unknown_events": len(unknown_pairing_events),
            "competitions": sorted({str(row.get("competition") or "") for row in category_rows if row.get("competition")}),
            "bookmakers": sorted({str(row.get("bookmaker") or "") for row in category_rows if row.get("bookmaker")}),
            "raw_market_names": sorted({str(row.get("market_name") or "") for row in category_rows if row.get("market_name")}),
        }

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "policy": {
            "price_capture_gate": "At least one paired Over/Under line must be observed before a count model can emit shadow signals.",
            "definition_gate": "Bookmaker settlement definitions must be reconciled against the result source before ROI is scored.",
            "live_staking": "BLOCKED",
        },
        "categories": categories,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Football Count Market Coverage",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "This report measures what the configured odds feed actually exposes. A bookmaker offering a market on its website does not prove the aggregator returns it.",
        "",
        "| Category | Status | Events | Paired O/U events | Pairing unknown | Competitions | Raw labels |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for category in TARGET_CATEGORIES:
        item = report["categories"][category]
        labels = ", ".join(item["raw_market_names"]) or "-"
        lines.append(
            f"| {category} | {item['status']} | {item['events']} | {item['paired_price_events']} | "
            f"{item['pairing_unknown_events']} | {len(item['competitions'])} | {labels} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "- `PAIRED_PRICES_OBSERVED`: eligible for definition checks and a preregistered shadow-model experiment.",
            "- `MARKET_NAME_ONLY`: the label was observed, but the legacy audit cannot prove usable paired prices.",
            "- `NOT_OBSERVED`: not returned by the configured feed; do not assume it can be automated.",
            "- Live staking remains blocked until count, settlement, real-price ROI and CLV gates pass.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit real feed coverage for football count markets")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--legacy-glob", default=DEFAULT_LEGACY_GLOB)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    report = summarize(read_rows(args.inventory, args.legacy_glob))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    args.report_out.write_text(render_markdown(report), encoding="utf-8")
    print(f"Coverage JSON: {args.json_out}")
    print(f"Coverage report: {args.report_out}")
    for category in TARGET_CATEGORIES:
        item = report["categories"][category]
        print(f"{category}: {item['status']} ({item['events']} events; {item['paired_price_events']} paired)")


if __name__ == "__main__":
    main()
