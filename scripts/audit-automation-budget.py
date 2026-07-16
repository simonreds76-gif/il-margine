#!/usr/bin/env python3
"""Audit scheduled automation against registered API and database budgets."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "automation-budget.json"
DEFAULT_JSON = ROOT / "data" / "ops" / "automation-budget-report.json"
DEFAULT_REPORT = ROOT / "data" / "ops" / "automation-budget-report.md"
WORKFLOWS = ROOT / ".github" / "workflows"
CRON_RE = re.compile(r"cron:\s*[\"']([^\"']+)[\"']")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cron_values(field: str, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    for item in field.split(","):
        item = item.strip()
        if item == "*":
            values.update(range(minimum, maximum + 1))
            continue
        if item.startswith("*/"):
            step = int(item[2:])
            values.update(range(minimum, maximum + 1, step))
            continue
        if "-" in item:
            start, end = (int(part) for part in item.split("-", 1))
            values.update(range(start, end + 1))
            continue
        values.add(int(item))
    if not values or min(values) < minimum or max(values) > maximum:
        raise ValueError(f"unsupported cron field {field!r} outside {minimum}-{maximum}")
    return values


def expand_week(cron: str) -> list[tuple[int, int, int]]:
    fields = cron.split()
    if len(fields) != 5:
        raise ValueError(f"expected five cron fields: {cron}")
    minute, hour, day_of_month, month, day_of_week = fields
    if day_of_month != "*" or month != "*":
        raise ValueError(f"monthly/date-specific cron is not supported by this budget audit: {cron}")
    minutes = cron_values(minute, 0, 59)
    hours = cron_values(hour, 0, 23)
    days = cron_values(day_of_week, 0, 6) if day_of_week != "*" else set(range(7))
    return [(day, hour_value, minute_value) for day in days for hour_value in hours for minute_value in minutes]


def workflow_crons(path: Path) -> list[str]:
    return CRON_RE.findall(path.read_text(encoding="utf-8"))


def observe_windows_tasks() -> dict[str, dict[str, str]]:
    if sys.platform != "win32":
        return {}
    try:
        completed = subprocess.run(
            ["schtasks", "/Query", "/FO", "CSV", "/V"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    rows = list(csv.DictReader(completed.stdout.splitlines()))
    observed: dict[str, dict[str, str]] = {}
    for row in rows:
        task_name = str(row.get("TaskName") or row.get("Task Name") or "").lstrip("\\")
        if task_name:
            observed[task_name] = {
                "status": str(row.get("Status") or row.get("Scheduled Task State") or "UNKNOWN"),
                "task_to_run": str(row.get("Task To Run") or ""),
            }
    return observed


def build_report(config: dict[str, Any], workflows_dir: Path = WORKFLOWS) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    registered_files = {str(row["file"]): row for row in config["github_workflows"]}
    actual_scheduled: dict[str, list[str]] = {}
    for path in sorted(workflows_dir.glob("*.yml")):
        crons = workflow_crons(path)
        if crons:
            actual_scheduled[path.name] = crons

    missing_registration = sorted(set(actual_scheduled) - set(registered_files))
    stale_registration = sorted(set(registered_files) - set(actual_scheduled))
    if missing_registration:
        errors.append("scheduled workflows missing from budget registry: " + ", ".join(missing_registration))
    if stale_registration:
        errors.append("budget registry entries without an active schedule: " + ", ".join(stale_registration))

    provider_slots: dict[str, dict[tuple[int, int, int], int]] = defaultdict(lambda: defaultdict(int))
    workflow_rows: list[dict[str, Any]] = []
    db_reads_week = 0
    db_writes_week = 0
    for file_name, row in registered_files.items():
        declared_crons = [str(item["cron"]) for item in row["schedules"]]
        found_crons = actual_scheduled.get(file_name, [])
        if sorted(declared_crons) != sorted(found_crons):
            errors.append(f"{file_name}: declared crons {declared_crons} != workflow crons {found_crons}")
        runs_week = 0
        provider_week: dict[str, int] = defaultdict(int)
        for schedule in row["schedules"]:
            try:
                slots = expand_week(str(schedule["cron"]))
            except ValueError as exc:
                errors.append(f"{file_name}: {exc}")
                slots = []
            runs_week += len(slots)
            for provider, cap in (schedule.get("request_caps") or {}).items():
                cap_value = int(cap)
                provider_week[provider] += cap_value * len(slots)
                for slot in slots:
                    provider_slots[provider][slot] += cap_value
        reads = int(row.get("db_reads_max_per_run") or 0) * runs_week
        writes = int(row.get("db_writes_max_per_run") or 0) * runs_week
        db_reads_week += reads
        db_writes_week += writes
        workflow_rows.append(
            {
                "file": file_name,
                "models": row.get("models") or [],
                "season_gate": row.get("season_gate") or "",
                "database_mode": row.get("database_mode") or "unknown",
                "runs_per_week_max": runs_week,
                "provider_requests_per_week_max": dict(provider_week),
                "db_reads_per_week_max": reads,
                "db_writes_per_week_max": writes,
            }
        )

    provider_summary: dict[str, Any] = {}
    for provider, limits in config["provider_limits"].items():
        slots = provider_slots.get(provider, {})
        hourly: dict[tuple[int, int], int] = defaultdict(int)
        daily: dict[int, int] = defaultdict(int)
        for (day, hour, _minute), calls in slots.items():
            hourly[(day, hour)] += calls
            daily[day] += calls
        max_hour = max(hourly.values(), default=0)
        max_day = max(daily.values(), default=0)
        status = "PASS"
        if limits.get("requests_per_hour") is not None and max_hour > int(limits["requests_per_hour"]):
            status = "FAIL"
            errors.append(f"{provider}: hourly ceiling {max_hour} exceeds {limits['requests_per_hour']}")
        if limits.get("requests_per_day") is not None and max_day > int(limits["requests_per_day"]):
            status = "FAIL"
            errors.append(f"{provider}: daily ceiling {max_day} exceeds {limits['requests_per_day']}")
        provider_summary[provider] = {
            **limits,
            "max_requests_in_one_hour": max_hour,
            "max_requests_in_one_day": max_day,
            "max_requests_per_week": sum(slots.values()),
            "status": status,
        }

    observed_tasks = observe_windows_tasks()
    local_rows: list[dict[str, Any]] = []
    for expected in config.get("local_windows_tasks") or []:
        name = str(expected["name"])
        observed = observed_tasks.get(name)
        local_rows.append({**expected, "observed_status": (observed or {}).get("status", "UNOBSERVED")})
        if sys.platform == "win32" and observed is None:
            warnings.append(f"expected Windows task not found: {name}")

    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "workflow_directory": str(workflows_dir),
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "warnings": warnings,
        "providers": provider_summary,
        "github_workflows": workflow_rows,
        "database": {
            "registered_reads_per_week_max": db_reads_week,
            "registered_writes_per_week_max": db_writes_week,
            "note": "Counts are bounded workflow operations, not affected-row counts. Pinnacle history remains append-only.",
        },
        "local_windows_tasks": local_rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Automation Budget Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Status: **{report['status']}**",
        f"- Effective workflow source: `{report['workflow_directory']}`",
        "- Any newly scheduled workflow that is not registered fails this audit.",
        "",
        "## Provider Ceilings",
        "",
        "| Provider | Worst hour | Limit/hour | Worst day | Limit/day | Weekly ceiling | Status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, row in report["providers"].items():
        lines.append(
            f"| {row['label']} | {row['max_requests_in_one_hour']} | {row.get('requests_per_hour', '-')} | "
            f"{row['max_requests_in_one_day']} | {row.get('requests_per_day', '-')} | "
            f"{row['max_requests_per_week']} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## Scheduled GitHub Workflows",
            "",
            "| Workflow | Models | Runs/week max | API request ceilings/week | Database mode |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for row in report["github_workflows"]:
        providers = ", ".join(f"{key}={value}" for key, value in row["provider_requests_per_week_max"].items()) or "none"
        lines.append(
            f"| {row['file']} | {', '.join(row['models'])} | {row['runs_per_week_max']} | {providers} | {row['database_mode']} |"
        )
    lines.extend(
        [
            "",
            "## Database Envelope",
            "",
            f"- Registered read operations/week maximum: {report['database']['registered_reads_per_week_max']}",
            f"- Registered write operations/week maximum: {report['database']['registered_writes_per_week_max']}",
            f"- {report['database']['note']}",
            "",
            "## Local Windows Tasks",
            "",
        ]
    )
    for row in report["local_windows_tasks"]:
        lines.append(f"- {row['name']}: {row['schedule']}; {row['database_mode']}; observed {row['observed_status']}.")
    if report["errors"]:
        lines.extend(["", "## Errors", ""] + [f"- {item}" for item in report["errors"]])
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""] + [f"- {item}" for item in report["warnings"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--workflows-dir",
        type=Path,
        default=WORKFLOWS,
        help="Workflow directory that GitHub actually schedules from (normally the default branch checkout).",
    )
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = build_report(load_json(args.config), args.workflows_dir)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    print(f"Wrote {args.json}")
    print(f"Wrote {args.report}")
    return 1 if args.strict and report["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
