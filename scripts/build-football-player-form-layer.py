#!/usr/bin/env python3
"""Build canonical football player rolling-form tables for goalscorer research.

This is an input layer only. It does not change live goalscorer picks.

Outputs:
- data/football-form/player-rolling-form.csv
- data/football-form/player-form-report.md
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict, deque
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_GLOB = "data/goalscorer/*-player-match-logs-*.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "football-form"
WINDOWS = (5, 10, 16, 40)


BASE_FIELDS = [
    "date",
    "league",
    "competition",
    "season",
    "team",
    "opponent",
    "is_home",
    "player_id",
    "player_name",
    "position",
    "current_started",
    "current_minutes",
    "current_goals",
    "current_shots",
    "current_sot",
    "current_xg",
    "current_npxg",
    "current_team_xg",
    "current_team_xga",
]

ROLLING_METRICS = [
    "matches",
    "starts",
    "minutes",
    "avg_minutes",
    "goals_per90",
    "xg_per90",
    "npxg_per90",
    "shots_per90",
    "sot_per90",
    "team_xg_share",
    "avg_team_xg",
    "avg_team_xga",
    "primary_position",
    "last_position",
]


def rolling_fields() -> list[str]:
    fields = list(BASE_FIELDS)
    for window in WINDOWS:
        for metric in ROLLING_METRICS:
            fields.append(f"r{window}_{metric}")
    return fields


def parse_float(value: Any, default: float = 0.0) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    return int(round(parse_float(value, float(default))))


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
    return None


def clean(value: Any) -> str:
    return str(value or "").strip()


def league_from_path(path: Path) -> str:
    name = path.name
    marker = "-player-match-logs-"
    if marker in name:
        return name.split(marker, 1)[0]
    return ""


def value_or_blank(value: float | None, digits: int = 4) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def safe_rate(num: float, minutes: float) -> str:
    if minutes <= 0:
        return ""
    return value_or_blank(num / (minutes / 90.0))


def avg(values: Iterable[float]) -> str:
    vals = list(values)
    if not vals:
        return ""
    return value_or_blank(sum(vals) / len(vals))


def player_key(row: dict[str, Any]) -> str:
    pid = clean(row.get("player_id"))
    if pid:
        return f"id:{pid}"
    return f"name:{clean(row.get('player_name')).lower()}"


def load_player_rows(input_glob: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    files = sorted(ROOT.glob(input_glob))
    rows: list[dict[str, Any]] = []
    stats = {"files": len(files), "raw_rows": 0, "usable_rows": 0, "skipped_no_date": 0}

    for path in files:
        league = league_from_path(path)
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                stats["raw_rows"] += 1
                match_date = parse_date(raw.get("match_date") or raw.get("date"))
                if not match_date:
                    stats["skipped_no_date"] += 1
                    continue
                minutes = parse_float(raw.get("minutes"))
                # Zero-minute rows are not useful for player rates, but keeping
                # them would pollute per-90 denominators and position history.
                if minutes <= 0:
                    continue
                row = {
                    "date": match_date.isoformat(),
                    "league": league,
                    "competition": clean(raw.get("competition")),
                    "season": clean(raw.get("season")),
                    "team": clean(raw.get("team")),
                    "opponent": clean(raw.get("opponent")),
                    "is_home": str(parse_int(raw.get("is_home"))),
                    "player_id": clean(raw.get("player_id")),
                    "player_name": clean(raw.get("player_name")),
                    "position": clean(raw.get("position")),
                    "current_started": str(parse_int(raw.get("started"))),
                    "current_minutes": value_or_blank(minutes),
                    "current_goals": str(parse_int(raw.get("goals"))),
                    "current_shots": str(parse_int(raw.get("shots"))),
                    "current_sot": str(parse_int(raw.get("shots_on_target"))),
                    "current_xg": value_or_blank(parse_float(raw.get("xg"))),
                    "current_npxg": value_or_blank(parse_float(raw.get("npxg"))),
                    "current_team_xg": value_or_blank(parse_float(raw.get("team_xg"))),
                    "current_team_xga": value_or_blank(parse_float(raw.get("team_xga"))),
                }
                rows.append(row)
                stats["usable_rows"] += 1

    rows.sort(key=lambda row: (row["date"], row["league"], row["team"], row["player_name"]))
    return rows, stats


def summarize_window(history: list[dict[str, Any]], window: int) -> dict[str, Any]:
    recent = history[-window:]
    minutes = sum(parse_float(row.get("current_minutes")) for row in recent)
    goals = sum(parse_float(row.get("current_goals")) for row in recent)
    xg = sum(parse_float(row.get("current_xg")) for row in recent)
    npxg = sum(parse_float(row.get("current_npxg")) for row in recent)
    shots = sum(parse_float(row.get("current_shots")) for row in recent)
    sot = sum(parse_float(row.get("current_sot")) for row in recent)
    team_xg_sum = sum(parse_float(row.get("current_team_xg")) for row in recent)
    positions = [clean(row.get("position")) for row in recent if clean(row.get("position"))]
    primary_position = Counter(positions).most_common(1)[0][0] if positions else ""
    last_position = positions[-1] if positions else ""

    return {
        f"r{window}_matches": str(len(recent)),
        f"r{window}_starts": str(sum(parse_int(row.get("current_started")) for row in recent)),
        f"r{window}_minutes": value_or_blank(minutes, digits=1),
        f"r{window}_avg_minutes": value_or_blank(minutes / len(recent), digits=1) if recent else "",
        f"r{window}_goals_per90": safe_rate(goals, minutes),
        f"r{window}_xg_per90": safe_rate(xg, minutes),
        f"r{window}_npxg_per90": safe_rate(npxg, minutes),
        f"r{window}_shots_per90": safe_rate(shots, minutes),
        f"r{window}_sot_per90": safe_rate(sot, minutes),
        f"r{window}_team_xg_share": value_or_blank(xg / team_xg_sum) if team_xg_sum > 0 else "",
        f"r{window}_avg_team_xg": avg(parse_float(row.get("current_team_xg")) for row in recent),
        f"r{window}_avg_team_xga": avg(parse_float(row.get("current_team_xga")) for row in recent),
        f"r{window}_primary_position": primary_position,
        f"r{window}_last_position": last_position,
    }


def build_rolling_rows(player_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    histories: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=max(WINDOWS)))
    rolling_rows: list[dict[str, Any]] = []

    for row in player_rows:
        key = player_key(row)
        history = list(histories[key])
        out = dict(row)
        for window in WINDOWS:
            out.update(summarize_window(history, window))
        rolling_rows.append(out)
        histories[key].append(row)
    return rolling_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_report(player_rows: list[dict[str, Any]], rolling_rows: list[dict[str, Any]], stats: dict[str, int], output_dir: Path) -> str:
    dates = [parse_date(row["date"]) for row in player_rows]
    dates = [item for item in dates if item is not None]
    latest = max(dates).isoformat() if dates else "-"
    earliest = min(dates).isoformat() if dates else "-"
    league_counts: dict[str, int] = defaultdict(int)
    for row in player_rows:
        league_counts[row.get("league") or "unknown"] += 1

    lines = [
        "# Football Player Form Layer Report",
        "",
        f"Generated: {datetime.now(UTC).replace(microsecond=0).isoformat()}",
        "",
        "## Outputs",
        "",
        f"- `{(output_dir / 'player-rolling-form.csv').relative_to(ROOT).as_posix()}`",
        "",
        "## Summary",
        "",
        f"- Source files: {stats['files']}",
        f"- Raw rows: {stats['raw_rows']}",
        f"- Usable player rows: {stats['usable_rows']}",
        f"- Rolling rows: {len(rolling_rows)}",
        f"- Date range: {earliest} to {latest}",
        "",
        "## League Coverage",
        "",
        "| League | Player rows |",
        "| --- | ---: |",
    ]
    for league in sorted(league_counts):
        lines.append(f"| {league} | {league_counts[league]} |")
    lines.extend(
        [
            "",
            "## Source Stats",
            "",
            "```json",
            json.dumps(stats, indent=2, sort_keys=True),
            "```",
            "",
            "## Notes",
            "",
            "- Rolling features are causal: each row uses only prior appearances for that player.",
            "- Windows include 5/10 for shared football form and 16/40 to mirror the current goalscorer model.",
            "- `team_xg_share` is player xG divided by team xG across the same player appearances.",
            "- This table is not wired into live goalscorer selection yet.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build canonical football player rolling-form table.")
    parser.add_argument("--input-glob", default=DEFAULT_INPUT_GLOB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    rows, stats = load_player_rows(args.input_glob)
    rolling_rows = build_rolling_rows(rows)
    write_csv(args.output_dir / "player-rolling-form.csv", rolling_rows, rolling_fields())
    report = render_report(rows, rolling_rows, stats, args.output_dir)
    (args.output_dir / "player-form-report.md").write_text(report, encoding="utf-8")

    print(f"Wrote {(args.output_dir / 'player-rolling-form.csv').relative_to(ROOT).as_posix()}")
    print(f"Wrote {(args.output_dir / 'player-form-report.md').relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
