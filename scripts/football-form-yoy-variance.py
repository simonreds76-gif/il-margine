#!/usr/bin/env python3
"""Report year-over-year league drift in football form inputs.

Claude's useful objection: causal all-prior league baselines are clean but can
adapt too slowly if league shot/corner environments shift. This report quantifies
that drift before we decide whether to move to trailing-12-month normalization.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "football-form" / "team-match-base.csv"
DEFAULT_JSON_OUT = ROOT / "data" / "football-form" / "league-yoy-variance.json"
DEFAULT_REPORT_OUT = ROOT / "data" / "football-form" / "league-yoy-variance.md"

METRICS = ["shots_for", "shots_against", "corners_for", "corners_against", "xg_for", "xg_against"]


def pf(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def year_from_date(value: Any) -> int | None:
    text = str(value or "").strip()
    if len(text) < 4:
        return None
    try:
        return int(text[:4])
    except ValueError:
        return None


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100.0


def build_report(input_path: Path, *, material_threshold_pct: float) -> dict[str, Any]:
    values: dict[str, dict[int, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with input_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            league = str(row.get("league") or "unknown").strip() or "unknown"
            year = year_from_date(row.get("date"))
            if year is None:
                continue
            for metric in METRICS:
                value = pf(row.get(metric))
                if value is not None:
                    values[league][year][metric].append(value)

    leagues: dict[str, Any] = {}
    for league, years in sorted(values.items()):
        yearly: list[dict[str, Any]] = []
        max_abs_yoy: dict[str, float] = {metric: 0.0 for metric in METRICS}
        previous_means: dict[str, float | None] = {}
        for year in sorted(years):
            item: dict[str, Any] = {"year": year, "rows": max((len(vals) for vals in years[year].values()), default=0)}
            for metric in METRICS:
                avg = mean(years[year].get(metric, []))
                item[f"{metric}_avg"] = round(avg, 4) if avg is not None else None
                change = pct_change(avg, previous_means.get(metric)) if avg is not None and previous_means.get(metric) else None
                item[f"{metric}_yoy_pct"] = round(change, 2) if change is not None else None
                if change is not None:
                    max_abs_yoy[metric] = max(max_abs_yoy[metric], abs(change))
                previous_means[metric] = avg
            yearly.append(item)

        material_metrics = [
            metric for metric, max_change in max_abs_yoy.items() if max_change >= material_threshold_pct
        ]
        leagues[league] = {
            "years": yearly,
            "max_abs_yoy_pct": {metric: round(value, 2) for metric, value in max_abs_yoy.items()},
            "material_metrics": material_metrics,
            "recommendation": (
                "use_trailing_12m_baseline" if material_metrics else "all_prior_baseline_ok"
            ),
        }

    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "input": str(input_path.relative_to(ROOT)),
        "material_threshold_pct": material_threshold_pct,
        "leagues": leagues,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# League Year-Over-Year Variance",
        "",
        f"Generated: {payload['generated_at']}",
        f"Input: `{payload['input']}`",
        f"Material threshold: {payload['material_threshold_pct']:.1f}%",
        "",
        "## Recommendation",
        "",
        "| League | Recommendation | Material metrics | Max shots_for YoY | Max corners_for YoY |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for league, summary in payload["leagues"].items():
        max_yoy = summary["max_abs_yoy_pct"]
        material = ", ".join(summary["material_metrics"]) or "-"
        lines.append(
            f"| {league} | {summary['recommendation']} | {material} | "
            f"{max_yoy.get('shots_for', 0.0):.2f}% | {max_yoy.get('corners_for', 0.0):.2f}% |"
        )

    lines.extend(["", "## Yearly Means", ""])
    for league, summary in payload["leagues"].items():
        lines.extend(
            [
                f"### {league}",
                "",
                "| Year | Rows | Shots for | Shots YoY | Corners for | Corners YoY | xG for | xG YoY |",
                "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for item in summary["years"]:
            lines.append(
                f"| {item['year']} | {item['rows']} | {item.get('shots_for_avg') or '-'} | "
                f"{item.get('shots_for_yoy_pct') if item.get('shots_for_yoy_pct') is not None else '-'} | "
                f"{item.get('corners_for_avg') or '-'} | "
                f"{item.get('corners_for_yoy_pct') if item.get('corners_for_yoy_pct') is not None else '-'} | "
                f"{item.get('xg_for_avg') or '-'} | "
                f"{item.get('xg_for_yoy_pct') if item.get('xg_for_yoy_pct') is not None else '-'} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Read This Properly",
            "",
            "- This is descriptive, not a model promotion decision.",
            "- `use_trailing_12m_baseline` means the all-prior causal baseline adapts too slowly for at least one tracked metric.",
            "- If only sparse xG triggers material variance, prefer trailing shots/corners first and leave xG as a guarded feature.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report league year-over-year variance in canonical football inputs.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    parser.add_argument("--material-threshold-pct", type=float, default=10.0)
    args = parser.parse_args()

    payload = build_report(args.input, material_threshold_pct=args.material_threshold_pct)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(render_markdown(payload), encoding="utf-8")
    print(f"Wrote {args.json_out.relative_to(ROOT)}")
    print(f"Wrote {args.report_out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
