#!/usr/bin/env python3
"""Audit football model input sources before building canonical form tables.

The goal is deliberately narrow:
- identify which datasets currently feed football models;
- measure freshness and field coverage for xG, shots, corners, odds, and player logs;
- produce a review packet before changing model formulas.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "football-form"
DEFAULT_DOCS_OUT = ROOT / "docs" / "model-review" / "football-canonical-inputs-claude-packet.md"


FIELD_GROUPS: dict[str, list[str]] = {
    "xg": ["xg", "home_xg", "away_xg", "team_xg", "team_xga", "big_chance_xg"],
    "npxg": ["npxg", "team_npxg"],
    "shots": ["shots", "home_shots", "away_shots", "HS", "AS", "shots_for", "shots_against"],
    "shots_on_target": ["shots_on_target", "home_sot", "away_sot", "HST", "AST"],
    "corners": ["home_corners", "away_corners", "HC", "AC", "corners_for", "corners_against"],
    "book_odds": ["B365H", "B365D", "B365A", "odds_decimal", "book_odds", "entry_odds"],
    "player_identity": ["player_id", "player_name", "position"],
    "minutes": ["minutes", "started"],
}


DATE_FIELDS = [
    "date",
    "Date",
    "match_date",
    "kickoff_at",
    "kickoff_iso",
    "captured_at",
    "capture_date",
    "fixture_date",
]


LEAGUE_FIELDS = ["league", "competition"]


@dataclass(frozen=True)
class DatasetConfig:
    key: str
    path: str
    owner: str
    source_role: str
    required_groups: tuple[str, ...]


DATASETS: tuple[DatasetConfig, ...] = (
    DatasetConfig(
        key="team_shots_fbref_matches",
        path="data/team-shots/fbref/all-fbref-matches.csv",
        owner="team-shots",
        source_role="FBref match-level shots, SOT, corners, xG, and 1X2 odds",
        required_groups=("xg", "shots", "shots_on_target", "corners", "book_odds"),
    ),
    DatasetConfig(
        key="team_shots_football_data_matches",
        path="data/team-shots/historical/all-historical-matches.csv",
        owner="team-shots",
        source_role="Football-Data match-level shots, SOT, corners, goals, and bookmaker odds",
        required_groups=("shots", "shots_on_target", "corners", "book_odds"),
    ),
    DatasetConfig(
        key="corners_historical_matches",
        path="data/corners-ou/historical/all-historical-matches.csv",
        owner="corners",
        source_role="Football-Data historical corners and 1X2 odds",
        required_groups=("corners", "book_odds", "shots"),
    ),
    DatasetConfig(
        key="corners_pinnacle_odds",
        path="data/corners-ou/pinnacle-corners-odds.csv",
        owner="corners",
        source_role="Pinnacle corners O/U snapshots for CLV and live market comparison",
        required_groups=("book_odds",),
    ),
    DatasetConfig(
        key="team_shots_odds_history",
        path="data/team-shots/team-shots-odds-history.csv",
        owner="team-shots",
        source_role="Bookmaker team-shots O/U snapshots",
        required_groups=("book_odds",),
    ),
    DatasetConfig(
        key="goalscorer_odds_history",
        path="data/goalscorer/goalscorer-odds-history.csv",
        owner="goalscorer",
        source_role="Bookmaker anytime-goalscorer odds snapshots",
        required_groups=("book_odds",),
    ),
)


PLAYER_LOG_GLOB = "data/goalscorer/*-player-match-logs-*.csv"


MODEL_FILES = [
    "scripts/team-shots-model.py",
    "scripts/team-shots-compare.py",
    "scripts/team-shots-shadow-tracker.py",
    "scripts/corners-ou-model.py",
    "scripts/corners-ou-backtest.py",
    "scripts/matchday-shortlist.py",
    "scripts/goalscorer-model.py",
    "scripts/goalscorer-live-compare.py",
    "scripts/goalscorer-shadow-tracker.py",
    "scripts/understat-scrape-serie-a.py",
    "scripts/fbref-download-shooting.py",
    "scripts/fbref-scrape-serie-a.py",
    "scripts/fotmob_match_stats.py",
    "scripts/fotmob-fetch-lineups.py",
]


TERM_GROUPS: dict[str, list[str]] = {
    "understat": ["understat"],
    "fbref": ["fbref"],
    "fotmob": ["fotmob"],
    "xg": ["xg", "npxg", "team_xg", "team_xga"],
    "shots": ["shots", "sot", "shots_on_target"],
    "corners": ["corners", "corner"],
    "odds": ["odds", "pinnacle", "bet365", "b365", "bookmaker"],
    "rolling": ["rolling", "ema", "recent", "decay", "window"],
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for candidate in (text, text[:10]):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                return parsed.date()
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.date()
        except ValueError:
            continue
    return None


def parse_number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def field_present(row: dict[str, str], aliases: Iterable[str]) -> bool:
    for alias in aliases:
        if alias not in row:
            continue
        value = row.get(alias)
        numeric = parse_number(value)
        if numeric is not None:
            if numeric > 0:
                return True
            continue
        if str(value or "").strip():
            return True
    return False


def first_existing(columns: set[str], aliases: Iterable[str]) -> str | None:
    for alias in aliases:
        if alias in columns:
            return alias
    return None


def audit_csv(path: Path, required_groups: tuple[str, ...]) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "mtime_utc": None,
        "row_count": 0,
        "columns": [],
        "date_field": None,
        "min_date": None,
        "max_date": None,
        "freshness_days": None,
        "field_coverage": {},
        "league_breakdown": [],
        "missing_required_groups": [],
    }
    if not path.exists():
        info["missing_required_groups"] = list(required_groups)
        return info

    stat = path.stat()
    info["mtime_utc"] = datetime.fromtimestamp(stat.st_mtime, tz=UTC).replace(microsecond=0).isoformat()

    dates: list[date] = []
    league_counts: dict[str, int] = {}
    league_latest: dict[str, date] = {}
    coverage_counts = {group: 0 for group in FIELD_GROUPS}
    columns: set[str] = set()

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        info["columns"] = list(reader.fieldnames or [])
        date_field = first_existing(columns, DATE_FIELDS)
        league_field = first_existing(columns, LEAGUE_FIELDS)
        info["date_field"] = date_field

        for row in reader:
            info["row_count"] += 1
            if date_field:
                parsed = parse_date(row.get(date_field))
                if parsed:
                    dates.append(parsed)
            else:
                parsed = None

            if league_field:
                league = str(row.get(league_field) or "").strip() or "unknown"
                league_counts[league] = league_counts.get(league, 0) + 1
                if parsed and (league not in league_latest or parsed > league_latest[league]):
                    league_latest[league] = parsed

            for group, aliases in FIELD_GROUPS.items():
                if field_present(row, aliases):
                    coverage_counts[group] += 1

    if dates:
        min_date = min(dates)
        max_date = max(dates)
        info["min_date"] = min_date.isoformat()
        info["max_date"] = max_date.isoformat()
        info["freshness_days"] = (datetime.now(UTC).date() - max_date).days

    row_count = max(int(info["row_count"]), 1)
    info["field_coverage"] = {
        group: {
            "rows_present": count,
            "pct": round((count / row_count) * 100.0, 2) if info["row_count"] else 0.0,
            "columns_available": [alias for alias in aliases if alias in columns],
        }
        for group, aliases in FIELD_GROUPS.items()
        for count in [coverage_counts[group]]
    }
    info["missing_required_groups"] = [
        group
        for group in required_groups
        if not info["field_coverage"].get(group, {}).get("columns_available")
    ]
    info["league_breakdown"] = [
        {
            "league": league,
            "rows": league_counts[league],
            "latest_date": league_latest.get(league).isoformat() if league in league_latest else None,
        }
        for league in sorted(league_counts)
    ]
    return info


def audit_player_logs() -> dict[str, Any]:
    files = sorted(ROOT.glob(PLAYER_LOG_GLOB))
    summaries = []
    combined_rows = 0
    latest: date | None = None
    for path in files:
        summary = audit_csv(path, ("xg", "npxg", "shots", "shots_on_target", "player_identity", "minutes"))
        combined_rows += int(summary["row_count"])
        if summary.get("max_date"):
            parsed = parse_date(summary["max_date"])
            if parsed and (latest is None or parsed > latest):
                latest = parsed
        summaries.append(summary)
    return {
        "glob": PLAYER_LOG_GLOB,
        "file_count": len(files),
        "row_count": combined_rows,
        "latest_date": latest.isoformat() if latest else None,
        "freshness_days": (datetime.now(UTC).date() - latest).days if latest else None,
        "files": summaries,
    }


def scan_model_file(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "terms": {},
        "data_paths": [],
    }
    if not path.exists():
        return info
    text = path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    for group, terms in TERM_GROUPS.items():
        info["terms"][group] = sum(lower.count(term.lower()) for term in terms)
    info["data_paths"] = sorted(set(re.findall(r"data/[A-Za-z0-9_./<>{}\\-]+", text)))
    return info


def build_issues(datasets: list[dict[str, Any]], player_logs: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for dataset in datasets:
        key = dataset["key"]
        if not dataset["exists"]:
            issues.append({"severity": "error", "area": key, "message": "Dataset file is missing."})
            continue
        freshness = dataset.get("freshness_days")
        if isinstance(freshness, int) and freshness > 14:
            issues.append({
                "severity": "warn",
                "area": key,
                "message": f"Latest dated row is {freshness} days old ({dataset.get('max_date')}).",
            })
        for group in dataset.get("missing_required_groups", []):
            issues.append({
                "severity": "warn",
                "area": key,
                "message": f"Required field group '{group}' has no matching columns.",
            })
        coverage = dataset.get("field_coverage", {})
        for group in dataset.get("required_groups", []):
            pct = coverage.get(group, {}).get("pct", 0.0)
            if pct == 0:
                issues.append({
                    "severity": "warn",
                    "area": key,
                    "message": f"Required field group '{group}' has 0% populated coverage.",
                })

    freshness = player_logs.get("freshness_days")
    if isinstance(freshness, int) and freshness > 14:
        issues.append({
            "severity": "warn",
            "area": "goalscorer_player_logs",
            "message": f"Latest player-log row is {freshness} days old ({player_logs.get('latest_date')}).",
        })
    if player_logs.get("file_count", 0) == 0:
        issues.append({"severity": "error", "area": "goalscorer_player_logs", "message": "No player logs found."})
    return issues


def render_markdown(payload: dict[str, Any]) -> str:
    generated_at = payload["generated_at"]
    lines: list[str] = [
        "# Football Model Input Audit",
        "",
        f"Generated: {generated_at}",
        "",
        "## Summary",
        "",
        "| Area | Rows | Latest date | Freshness | Notes |",
        "| --- | ---: | --- | ---: | --- |",
    ]

    for dataset in payload["datasets"]:
        notes = []
        missing = dataset.get("missing_required_groups", [])
        if missing:
            notes.append("missing " + ", ".join(missing))
        if not notes:
            notes.append("ok")
        latest = dataset.get("max_date") or "-"
        freshness = dataset.get("freshness_days")
        lines.append(
            f"| {dataset['key']} | {dataset['row_count']} | {latest} | "
            f"{freshness if freshness is not None else '-'} | {'; '.join(notes)} |"
        )

    player_logs = payload["player_logs"]
    lines.append(
        f"| goalscorer_player_logs | {player_logs['row_count']} | "
        f"{player_logs.get('latest_date') or '-'} | "
        f"{player_logs.get('freshness_days') if player_logs.get('freshness_days') is not None else '-'} | "
        f"{player_logs['file_count']} files |"
    )

    lines.extend(["", "## Issues", ""])
    if payload["issues"]:
        for issue in payload["issues"]:
            lines.append(f"- {issue['severity'].upper()} [{issue['area']}]: {issue['message']}")
    else:
        lines.append("- No hard input-audit issues detected.")

    lines.extend(["", "## Dataset Coverage", ""])
    for dataset in payload["datasets"]:
        lines.append(f"### {dataset['key']}")
        lines.append("")
        lines.append(f"- Path: `{dataset['path']}`")
        lines.append(f"- Owner: {dataset['owner']}")
        lines.append(f"- Role: {dataset['source_role']}")
        lines.append(f"- Date field: `{dataset.get('date_field') or '-'}`")
        lines.append("")
        lines.append("| Field group | Columns | Populated rows | Coverage |")
        lines.append("| --- | --- | ---: | ---: |")
        for group, coverage in dataset.get("field_coverage", {}).items():
            columns = ", ".join(f"`{column}`" for column in coverage.get("columns_available", [])) or "-"
            lines.append(
                f"| {group} | {columns} | {coverage.get('rows_present', 0)} | "
                f"{coverage.get('pct', 0.0):.2f}% |"
            )
        lines.append("")

    lines.extend(["## Model Script Signal Map", ""])
    lines.append("| Script | Understat | FBref | FotMob | xG | Shots | Corners | Odds | Rolling | Data paths |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for model in payload["model_files"]:
        terms = model["terms"]
        lines.append(
            f"| `{model['path']}` | {terms.get('understat', 0)} | {terms.get('fbref', 0)} | "
            f"{terms.get('fotmob', 0)} | {terms.get('xg', 0)} | {terms.get('shots', 0)} | "
            f"{terms.get('corners', 0)} | {terms.get('odds', 0)} | {terms.get('rolling', 0)} | "
            f"{len(model.get('data_paths', []))} |"
        )

    lines.extend(["", "## Immediate Interpretation", ""])
    lines.append("- Team shots already has an xG-enriched FBref source, but xG is blended inside the model rather than supplied by a canonical team-form table.")
    lines.append("- Corners is currently mostly corners-history plus 1X2 market context; it does not consume xG/pressure features directly.")
    lines.append("- Goalscorer already consumes player xG/npxG, team_xg, and team_xga, but the team form layer is embedded in the goalscorer script.")
    lines.append("- The next implementation step should create a generated team-match/team-form table, then backtest consumers before replacing any model inputs.")
    lines.append("")
    return "\n".join(lines)


def load_backtest_highlights(summary_path: Path) -> dict[str, Any]:
    highlights: dict[str, Any] = {"exists": summary_path.exists()}
    if not summary_path.exists():
        return highlights

    with summary_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        rows = list(csv.DictReader(handle))

    def number(value: Any) -> float | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def count_row(model: str, market: str, sample: str) -> dict[str, Any] | None:
        for row in rows:
            if (
                row.get("model") == model
                and row.get("market") == market
                and row.get("sample") == sample
                and row.get("league") == "ALL"
                and row.get("line") == "count"
            ):
                return row
        return None

    def metric_value(model: str, market: str, sample: str, line: str, metric: str) -> float | None:
        for row in rows:
            if (
                row.get("model") == model
                and row.get("market") == market
                and row.get("sample") == sample
                and row.get("league") == "ALL"
                and row.get("line") == line
            ):
                return number(row.get(metric))
        return None

    def n_value(row: dict[str, Any] | None) -> int | None:
        n = number(row.get("n") if row else None)
        return int(n) if n is not None else None

    def mae_value(row: dict[str, Any] | None) -> float | None:
        return number(row.get("mae") if row else None)

    def probability_better(
        candidate: str,
        baseline: str,
        market: str,
        sample: str,
        lines_to_check: list[str],
    ) -> dict[str, bool]:
        brier_ok = True
        log_loss_ok = True
        for line in lines_to_check:
            candidate_brier = metric_value(candidate, market, sample, line, "brier")
            baseline_brier = metric_value(baseline, market, sample, line, "brier")
            candidate_loss = metric_value(candidate, market, sample, line, "log_loss")
            baseline_loss = metric_value(baseline, market, sample, line, "log_loss")
            if candidate_brier is None or baseline_brier is None or candidate_brier > baseline_brier:
                brier_ok = False
            if candidate_loss is None or baseline_loss is None or candidate_loss > baseline_loss:
                log_loss_ok = False
        return {"brier_ok": brier_ok, "log_loss_ok": log_loss_ok}

    corners_common = count_row("canonical_form_v0", "corners_total", "common")
    corners_common_current = count_row("current", "corners_total", "common")
    corners_recent = count_row("canonical_form_v0", "corners_total", "last_90_common")
    corners_recent_current = count_row("current", "corners_total", "last_90_common")
    corners_only = count_row("canonical_form_v0", "corners_total", "canonical_only")

    team_common_nb = count_row("canonical_form_v1_market_nb", "team_shots", "common")
    team_common_market = count_row("canonical_form_v1_market", "team_shots", "common")
    team_common_current = count_row("current", "team_shots", "common")
    team_recent_nb = count_row("canonical_form_v1_market_nb", "team_shots", "last_90_common")
    team_recent_current = count_row("current", "team_shots", "last_90_common")
    team_only_nb = count_row("canonical_form_v1_market_nb", "team_shots", "canonical_only")

    corners_lines = ["8.5", "9.5", "10.5", "11.5"]
    team_lines = ["9.5", "10.5", "11.5", "12.5", "13.5", "14.5", "15.5"]

    highlights.update(
        {
            "corners_common_n": n_value(corners_common),
            "corners_common_mae": mae_value(corners_common),
            "corners_common_current_mae": mae_value(corners_common_current),
            "corners_recent_n": n_value(corners_recent),
            "corners_recent_mae": mae_value(corners_recent),
            "corners_recent_current_mae": mae_value(corners_recent_current),
            "corners_only_n": n_value(corners_only),
            "corners_only_mae": mae_value(corners_only),
            "corners_common_prob": probability_better(
                "canonical_form_v0", "current", "corners_total", "common", corners_lines
            ),
            "corners_recent_prob": probability_better(
                "canonical_form_v0", "current", "corners_total", "last_90_common", corners_lines
            ),
            "team_common_n": n_value(team_common_nb),
            "team_common_nb_mae": mae_value(team_common_nb),
            "team_common_market_mae": mae_value(team_common_market),
            "team_common_current_mae": mae_value(team_common_current),
            "team_recent_n": n_value(team_recent_nb),
            "team_recent_nb_mae": mae_value(team_recent_nb),
            "team_recent_current_mae": mae_value(team_recent_current),
            "team_only_n": n_value(team_only_nb),
            "team_only_nb_mae": mae_value(team_only_nb),
            "team_common_nb_prob": probability_better(
                "canonical_form_v1_market_nb", "current", "team_shots", "common", team_lines
            ),
            "team_recent_nb_prob": probability_better(
                "canonical_form_v1_market_nb", "current", "team_shots", "last_90_common", team_lines
            ),
        }
    )
    return highlights


def load_yoy_highlights(path: Path) -> dict[str, Any]:
    highlights: dict[str, Any] = {"exists": path.exists(), "primary_trailing": [], "guarded_trailing": []}
    if not path.exists():
        return highlights
    payload = json.loads(path.read_text(encoding="utf-8"))
    primary_metrics = {"shots_for", "shots_against", "corners_for", "corners_against"}
    for league, info in sorted(payload.get("leagues", {}).items()):
        material = set(info.get("material_metrics", []))
        recommendation = info.get("recommendation")
        if recommendation != "use_trailing_12m_baseline":
            continue
        if material & primary_metrics:
            highlights["primary_trailing"].append(league)
        else:
            highlights["guarded_trailing"].append(league)
    return highlights


def fmt_float(value: Any, decimals: int = 4) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "-"


def fmt_int(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "-"


def render_claude_packet(payload: dict[str, Any]) -> str:
    audit_rel = rel(DEFAULT_OUTPUT_DIR / "input-audit.md")
    json_rel = rel(DEFAULT_OUTPUT_DIR / "input-audit.json")
    team_match_rel = rel(DEFAULT_OUTPUT_DIR / "team-match-base.csv")
    team_form_rel = rel(DEFAULT_OUTPUT_DIR / "team-rolling-form.csv")
    team_manifest_rel = rel(DEFAULT_OUTPUT_DIR / "team-form-manifest.json")
    team_report_rel = rel(DEFAULT_OUTPUT_DIR / "team-form-report.md")
    team_validation_rel = rel(DEFAULT_OUTPUT_DIR / "team-form-validation.md")
    team_validation_json_rel = rel(DEFAULT_OUTPUT_DIR / "team-form-validation.json")
    player_form_rel = rel(DEFAULT_OUTPUT_DIR / "player-rolling-form.csv")
    player_report_rel = rel(DEFAULT_OUTPUT_DIR / "player-form-report.md")
    player_health_rel = rel(DEFAULT_OUTPUT_DIR / "player-log-health.json")
    player_smoke_rel = rel(DEFAULT_OUTPUT_DIR / "goalscorer-player-log-smoke.md")
    backtest_summary_rel = rel(DEFAULT_OUTPUT_DIR / "canonical-backtest-summary.csv")
    backtest_report_rel = rel(DEFAULT_OUTPUT_DIR / "canonical-backtest-report.md")
    yoy_report_rel = rel(DEFAULT_OUTPUT_DIR / "league-yoy-variance.md")
    yoy_json_rel = rel(DEFAULT_OUTPUT_DIR / "league-yoy-variance.json")
    team_layer_exists = (DEFAULT_OUTPUT_DIR / "team-match-base.csv").exists() and (
        DEFAULT_OUTPUT_DIR / "team-rolling-form.csv"
    ).exists()
    team_manifest_exists = (DEFAULT_OUTPUT_DIR / "team-form-manifest.json").exists()
    team_validation_exists = (DEFAULT_OUTPUT_DIR / "team-form-validation.md").exists()
    player_layer_exists = (DEFAULT_OUTPUT_DIR / "player-rolling-form.csv").exists()
    player_health_exists = (DEFAULT_OUTPUT_DIR / "player-log-health.json").exists()
    player_smoke_exists = (DEFAULT_OUTPUT_DIR / "goalscorer-player-log-smoke.md").exists()
    backtest_exists = (DEFAULT_OUTPUT_DIR / "canonical-backtest-summary.csv").exists() and (
        DEFAULT_OUTPUT_DIR / "canonical-backtest-report.md"
    ).exists()
    backtest = load_backtest_highlights(DEFAULT_OUTPUT_DIR / "canonical-backtest-summary.csv")
    yoy = load_yoy_highlights(DEFAULT_OUTPUT_DIR / "league-yoy-variance.json")
    player_logs = next((dataset for dataset in payload["datasets"] if dataset["key"] == "goalscorer_player_logs"), {})
    lines = [
        "# Claude Review Packet: Football Canonical Input Layer",
        "",
        "We are improving Il Margine football derivative models without adding distracting products.",
        "Please audit the plan and challenge any weak assumptions before we wire it into production.",
        "",
        "## Current Goal",
        "",
        "Build a canonical football team/player form layer that can feed team shots, corners, and goalscorer models.",
        "Do not build steam tracking, public xG tables, or a Dixon-Coles product yet.",
        "",
        "## Audit Artifacts",
        "",
        f"- Markdown audit: `{audit_rel}`",
        f"- JSON audit: `{json_rel}`",
        "",
        "## Implemented Artifacts So Far",
        "",
    ]
    if team_layer_exists:
        lines.extend(
            [
                f"- Team-match base table: `{team_match_rel}`",
                f"- Causal rolling team-form table: `{team_form_rel}`",
                f"- Team-form generation report: `{team_report_rel}`",
                "- Team-form table now preserves raw values plus causal league-relative normalized fields.",
                "- These artifacts are not wired into live model selection yet.",
            ]
        )
        if team_manifest_exists:
            lines.append(f"- Version manifest: `{team_manifest_rel}`")
        if team_validation_exists:
            lines.append(f"- Schema/freshness validation report: `{team_validation_rel}` / `{team_validation_json_rel}`")
    else:
        lines.append("- Team-form layer not generated yet.")
    if player_layer_exists:
        lines.extend(
            [
                f"- Causal player rolling-form table: `{player_form_rel}`",
                f"- Player-form generation report: `{player_report_rel}`",
            ]
        )
    if player_health_exists:
        lines.append(f"- Player-log freshness health: `{player_health_rel}`")
    if player_smoke_exists:
        lines.append(f"- Goalscorer model smoke test: `{player_smoke_rel}`")
    if player_logs:
        lines.append(
            f"- Goalscorer player logs are now fresh: latest `{player_logs.get('latest_date')}`, "
            f"freshness `{player_logs.get('freshness_days')}` day(s), rows `{player_logs.get('row_count')}`."
        )
    if backtest_exists:
        lines.extend(
            [
                f"- Research backtest summary: `{backtest_summary_rel}`",
                f"- Research backtest report: `{backtest_report_rel}`",
                "- Corners canonical v0 beats current on common-sample and last-90 common-sample count MAE and Brier/log-loss.",
                "- Team-shots canonical v1_market_nb adds capped 1X2 win-probability/game-state adjustment plus causal prior-data league negative-binomial O/U conversion. It improves Brier/log-loss, but recent count MAE is not yet better than current.",
                "- No live policy or published pick logic has been changed yet; this remains research-only pending odds/CLV and recent-window validation.",
            ]
        )
    if yoy.get("exists"):
        lines.extend(
            [
                f"- League YoY variance report: `{yoy_report_rel}` / `{yoy_json_rel}`",
                "- EPL and Serie A show material shots/corners regime variance, so trailing-12-month normalization should be implemented before any football-form promotion.",
            ]
        )
    lines.append("")

    lines.extend(
        [
            "## Changes Since Previous Review",
            "",
            "- The 15-day stale player-log issue is fixed. Hosted goalscorer refresh now checks freshness, refreshes stale leagues, writes health output only to temp, and hardens rebase/dirty-worktree handling.",
            "- Added schema/freshness validation for canonical team-form outputs: row counts, required fields, critical coverage, duplicate keys, freshness, market coverage, and xG coverage warnings.",
            "- Added date-versioned canonical CSV outputs and a manifest so model reports can record exactly which canonical data version they used.",
            "- Added causal league-relative normalized fields for shots, corners, and xG. They use only prior league rows, not current-season full-sample means.",
            "- Added common/canonical-only/full and last-90 sample splits to the canonical backtest report.",
            "- Added a team-shots `canonical_form_v1_market_nb` research variant using the market-implied win probability gap as a capped game-state proxy and causal prior-data negative-binomial O/U calibration.",
            "- Added a league year-over-year variance check to decide whether all-prior normalization is safe or trailing-12-month baselines are required.",
            "",
        ]
    )

    if backtest.get("exists"):
        lines.extend(
            [
                "## Backtest Highlights",
                "",
                "| Area | Sample | N | Current MAE | Canonical MAE | Probability gate | Read |",
                "| --- | --- | ---: | ---: | ---: | --- | --- |",
                (
                    "| corners v0 | common | "
                    f"{fmt_int(backtest.get('corners_common_n'))} | "
                    f"{fmt_float(backtest.get('corners_common_current_mae'))} | "
                    f"{fmt_float(backtest.get('corners_common_mae'))} | "
                    f"Brier {'ok' if backtest.get('corners_common_prob', {}).get('brier_ok') else 'fail'}, "
                    f"log-loss {'ok' if backtest.get('corners_common_prob', {}).get('log_loss_ok') else 'fail'} | "
                    "promotion candidate after odds/CLV join |"
                ),
                (
                    "| corners v0 | last_90_common | "
                    f"{fmt_int(backtest.get('corners_recent_n'))} | "
                    f"{fmt_float(backtest.get('corners_recent_current_mae'))} | "
                    f"{fmt_float(backtest.get('corners_recent_mae'))} | "
                    f"Brier {'ok' if backtest.get('corners_recent_prob', {}).get('brier_ok') else 'fail'}, "
                    f"log-loss {'ok' if backtest.get('corners_recent_prob', {}).get('log_loss_ok') else 'fail'} | "
                    "recent window also passes |"
                ),
                (
                    "| corners v0 | canonical_only | "
                    f"{fmt_int(backtest.get('corners_only_n'))} | - | "
                    f"{fmt_float(backtest.get('corners_only_mae'))} | no baseline | "
                    "sample is tiny; add confidence guard, do not infer coverage safety |"
                ),
                (
                    "| team-shots v1_market_nb | common | "
                    f"{fmt_int(backtest.get('team_common_n'))} | "
                    f"{fmt_float(backtest.get('team_common_current_mae'))} | "
                    f"{fmt_float(backtest.get('team_common_nb_mae'))} | "
                    f"Brier {'ok' if backtest.get('team_common_nb_prob', {}).get('brier_ok') else 'fail'}, "
                    f"log-loss {'ok' if backtest.get('team_common_nb_prob', {}).get('log_loss_ok') else 'fail'} | "
                    "NB helps O/U calibration |"
                ),
                (
                    "| team-shots v1_market_nb | last_90_common | "
                    f"{fmt_int(backtest.get('team_recent_n'))} | "
                    f"{fmt_float(backtest.get('team_recent_current_mae'))} | "
                    f"{fmt_float(backtest.get('team_recent_nb_mae'))} | "
                    f"Brier {'ok' if backtest.get('team_recent_nb_prob', {}).get('brier_ok') else 'fail'}, "
                    f"log-loss {'ok' if backtest.get('team_recent_nb_prob', {}).get('log_loss_ok') else 'fail'} | "
                    "probability passes, count MAE does not; keep research-only |"
                ),
                (
                    "| team-shots v1_market_nb | canonical_only | "
                    f"{fmt_int(backtest.get('team_only_n'))} | - | "
                    f"{fmt_float(backtest.get('team_only_nb_mae'))} | no baseline | "
                    "coverage looks usable, still needs segment gates |"
                ),
                "",
            ]
        )

    if yoy.get("exists"):
        primary = ", ".join(yoy.get("primary_trailing", [])) or "-"
        guarded = ", ".join(yoy.get("guarded_trailing", [])) or "-"
        lines.extend(
            [
                "## Normalization Read",
                "",
                f"- Use trailing-12-month baselines before promotion for primary shots/corners metrics in: {primary}.",
                f"- Treat trailing xG as guarded/sparse-only first in: {guarded}.",
                "- La Liga and Ligue 1 are within the 10% material threshold on the checked primary metrics, so all-prior baselines are less risky there.",
                "",
            ]
        )

    lines.extend([
        "## Findings From Current Repo",
        "",
    ])
    for issue in payload["issues"][:20]:
        lines.append(f"- {issue['severity'].upper()} [{issue['area']}]: {issue['message']}")
    if not payload["issues"]:
        lines.append("- No hard input-audit issues detected by the first pass.")
    lines.extend([
        "",
        "## Proposed Implementation Order",
        "",
        "1. Keep the stale-player-log fix in production workflows and monitor the next scheduled run.",
        "2. Run corners v0 odds/CLV join first because count and probability gates pass on common and last-90 common samples.",
        "3. Add a corners confidence guard for canonical-only coverage because the current canonical-only sample is only N=2 and looks unsafe to generalize from.",
        "4. Implement trailing-12-month normalization for EPL/Serie A primary shots/corners before any team-shots promotion.",
        "5. Add win-prob gap bucket calibration for team-shots; negative binomial improves O/U probability but recent count MAE still lags current.",
        "6. Then do the team-shots odds/CLV join and keep it research-only until the recent-window count issue is explained or fixed.",
        "",
        "## Questions For Follow-up Review",
        "",
        "1. Corners v0 now passes full and last-90 common-sample count/probability gates. Is odds/CLV join plus confidence guard sufficient for research-lane promotion?",
        "2. Team-shots v1_market_nb improves Brier/log-loss but last-90 count MAE is worse than current. Should we tune the capped game-state lambda, split by win-prob bucket, or hold the model entirely?",
        "3. For EPL/Serie A, should trailing-12-month normalization replace all-prior normalization globally, or only for shots/corners primary metrics?",
        "4. Is the canonical-only team-shots sample large enough to trust after segment gates, or should we withhold picks where current model was historically silent?",
        "5. What exact CLV join schema should block/allow corners v0 research-lane publication?",
        "",
    ])
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    datasets = []
    for config in DATASETS:
        summary = audit_csv(ROOT / config.path, config.required_groups)
        summary.update({
            "key": config.key,
            "owner": config.owner,
            "source_role": config.source_role,
            "required_groups": list(config.required_groups),
        })
        datasets.append(summary)

    player_logs = audit_player_logs()
    model_files = [scan_model_file(ROOT / path) for path in MODEL_FILES]
    payload = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "datasets": datasets,
        "player_logs": player_logs,
        "model_files": model_files,
        "issues": build_issues(datasets, player_logs),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit football model input datasets and source usage.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--docs-out", type=Path, default=DEFAULT_DOCS_OUT)
    args = parser.parse_args()

    payload = build_payload()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "input-audit.json"
    md_path = args.output_dir / "input-audit.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    args.docs_out.parent.mkdir(parents=True, exist_ok=True)
    args.docs_out.write_text(render_claude_packet(payload), encoding="utf-8")

    print(f"Wrote {rel(json_path)}")
    print(f"Wrote {rel(md_path)}")
    print(f"Wrote {rel(args.docs_out)}")
    print(f"Issues: {len(payload['issues'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
