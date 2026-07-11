#!/usr/bin/env python3
"""Golden-row parity check for historical and live goalscorer pricing paths.

The fixture rows and all histories are real. Only the bookmaker wrapper and
confirmed-lineup payload are synthesized so the live CLI can price a completed
historical fixture without network access.
"""

from __future__ import annotations

import argparse
import csv
import json
import runpy
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEAGUE = "bundesliga"
DATA_GLOB = "bundesliga-player-match-logs-*.csv"
COMPETITION = "Germany - Bundesliga"
MIN_GOLDEN_ROWS = 25
MAX_DELTA = 0.005


def repair_mojibake(value: object) -> str:
    text = str(value or "")
    if not any(marker in text for marker in ("Ã", "Â", "â")):
        return text
    try:
        repaired = text.encode("latin1").decode("utf-8")
        return repaired or text
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_raw_rows(paths: list[Path]) -> tuple[list[str], list[dict]]:
    fieldnames: list[str] = []
    rows: list[dict] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not fieldnames:
                fieldnames = list(reader.fieldnames or [])
            rows.extend(reader)
    return fieldnames, rows


def select_fixture_rows(rows: list[object]) -> tuple[str, list[object]]:
    by_date_fixture: dict[str, dict[tuple[str, str], list[object]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.is_home:
            fixture = (row.team_key, row.opponent_key)
        else:
            fixture = (row.opponent_key, row.team_key)
        by_date_fixture[row.match_date_str][fixture].append(row)

    for match_date in sorted(by_date_fixture, reverse=True):
        selected: list[object] = []
        for fixture_rows in sorted(by_date_fixture[match_date].values(), key=lambda value: value[0].team_key):
            selected.extend(fixture_rows)
            non_goalkeepers = [row for row in selected if not str(row.position).upper().startswith("GK")]
            if len(non_goalkeepers) >= MIN_GOLDEN_ROWS:
                return match_date, selected
    raise AssertionError("Could not find enough rows for the parity fixture set")


def fixture_payload(rows: list[object], match_date: str) -> dict:
    grouped: dict[tuple[str, str], dict[str, list[object]]] = defaultdict(lambda: {"home": [], "away": []})
    for row in rows:
        home = row.team if row.is_home else row.opponent
        away = row.opponent if row.is_home else row.team
        grouped[(home, away)]["home" if row.is_home else "away"].append(row)

    fixtures = []
    for (home, away), sides in grouped.items():
        home_starters = [row for row in sides["home"] if str(row.position).upper() != "SUB"]
        away_starters = [row for row in sides["away"] if str(row.position).upper() != "SUB"]
        fixtures.append(
            {
                "match_date": match_date,
                "home_team": home,
                "away_team": away,
                "lineup_type": "standard",
                "home_players": [row.player_name for row in home_starters],
                "away_players": [row.player_name for row in away_starters],
                "home_subs": [row.player_name for row in sides["home"] if str(row.position).upper() == "SUB"],
                "away_subs": [row.player_name for row in sides["away"] if str(row.position).upper() == "SUB"],
                "home_status": "Confirmed Lineup",
                "away_status": "Confirmed Lineup",
            }
        )
    return {"fixtures": fixtures}


def odds_rows(rows: list[object], match_date: str) -> list[dict]:
    output = []
    for row in rows:
        if str(row.position).upper().startswith("GK"):
            continue
        output.append(
            {
                "captured_at": f"{match_date}T10:00:00Z",
                "match_date": match_date,
                "bookmaker": "ParityBook",
                "competition": COMPETITION,
                "market": "ATGS",
                "home_team": row.team if row.is_home else row.opponent,
                "away_team": row.opponent if row.is_home else row.team,
                "player_name": row.player_name,
                "player_team": row.team,
                "odds_decimal": "3.0000",
                "implied_prob": "0.333333",
                "source": "parity_fixture",
                "notes": "golden-row parity",
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true", help="Write drift report without enforcing the 0.5pp gate")
    parser.add_argument("--out", default=str(ROOT / "data" / "goalscorer" / "backtest" / "parity-report.txt"))
    args = parser.parse_args()

    model = runpy.run_path(str(ROOT / "scripts" / "goalscorer-model.py"), run_name="goalscorer_parity_model")
    model["run_backtest"].__globals__["V2_REPAIR_ENABLED"] = True
    source_paths = sorted((ROOT / "data" / "goalscorer").glob(DATA_GLOB))
    normalized = model["load_match_logs"]([str(path) for path in source_paths])
    match_date, selected_rows = select_fixture_rows(normalized)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        fieldnames, raw_rows = load_raw_rows(source_paths)
        truncated_rows = [row for row in raw_rows if str(row.get("match_date") or "")[:10] <= match_date]
        truncated_path = temp / "history.csv"
        write_csv(truncated_path, fieldnames, truncated_rows)

        truncated_normalized = model["load_match_logs"]([str(truncated_path)])
        observed_penalty_rate = model["infer_league_penalties_per_match"](truncated_normalized)
        model["run_backtest"].__globals__["LEAGUE_AVG"] = model["league_avg_for"](LEAGUE, observed_penalty_rate)
        historical_results, _stats = model["run_backtest"](truncated_normalized)
        historical = {
            (row["match_date"], str(row["player_id"])): row
            for row in historical_results
            if row["match_date"] == match_date
        }

        odds_path = temp / "odds.csv"
        odds = odds_rows(selected_rows, match_date)
        write_csv(odds_path, list(odds[0].keys()), odds)
        lineup_path = temp / "lineups.json"
        lineup_path.write_text(json.dumps(fixture_payload(selected_rows, match_date)), encoding="utf-8")
        empty_path = temp / "empty.json"
        empty_path.write_text("{}\n", encoding="utf-8")
        output_dir = temp / "live"

        command = [
            sys.executable,
            str(ROOT / "scripts" / "goalscorer-live-compare.py"),
            "--data", str(truncated_path),
            "--league", LEAGUE,
            "--odds", str(odds_path),
            "--out-dir", str(output_dir),
            "--bookmaker", "ParityBook",
            "--lineups", str(lineup_path),
            "--penalty-hierarchy", str(empty_path),
            "--penalty-baseline-evidence", str(empty_path),
            "--penalty-baseline-overrides", str(empty_path),
            "--skip-roster-fetch",
            "--v2-repair",
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)

        with (output_dir / "goalscorer-live-comparison.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            live_rows = list(csv.DictReader(handle))

    comparisons = []
    for live in live_rows:
        key = (str(live.get("match_date") or "")[:10], str(live.get("player_id") or ""))
        backtest = historical.get(key)
        if not backtest or backtest.get("method") != "model" or live.get("method") != "model":
            continue
        delta = float(live["model_p_atgs"]) - float(backtest["model_p_atgs"])
        comparisons.append(
            {
                "player": repair_mojibake(live.get("canonical_player_name") or live.get("player_name")),
                "lineup_state": live.get("lineup_state"),
                "backtest_p": float(backtest["model_p_atgs"]),
                "live_p": float(live["model_p_atgs"]),
                "delta": delta,
                "backtest_minutes": float(backtest["expected_minutes"]),
                "live_minutes": float(live["expected_minutes"]),
                "backtest_share": float(backtest["team_share"]),
                "live_share": float(live["team_share"]),
            }
        )
    comparisons.sort(key=lambda row: abs(row["delta"]), reverse=True)
    golden = comparisons[:MIN_GOLDEN_ROWS]
    assert len(golden) >= MIN_GOLDEN_ROWS, f"Only {len(golden)} joined model rows"
    max_delta = max(abs(row["delta"]) for row in golden)
    mean_delta = sum(abs(row["delta"]) for row in golden) / len(golden)

    lines = [
        "Goalscorer Live/Backtest Parity",
        "=================================",
        "",
        f"League: {LEAGUE}",
        f"Fixture date: {match_date}",
        f"Golden rows: {len(golden)}",
        f"Mean absolute probability delta: {mean_delta:.6f}",
        f"Maximum absolute probability delta: {max_delta:.6f}",
        f"Gate: <= {MAX_DELTA:.6f}",
        f"Decision: {'PASS' if max_delta <= MAX_DELTA else 'FAIL'}",
        "",
        "player,lineup,backtest_p,live_p,delta,backtest_minutes,live_minutes,backtest_share,live_share",
    ]
    for row in golden:
        lines.append(
            f"{row['player']},{row['lineup_state']},{row['backtest_p']:.6f},{row['live_p']:.6f},{row['delta']:+.6f},"
            f"{row['backtest_minutes']:.1f},{row['live_minutes']:.1f},{row['backtest_share']:.4f},{row['live_share']:.4f}"
        )
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"GOALSCORER_PARITY rows={len(golden)} mean_delta={mean_delta:.6f} max_delta={max_delta:.6f}")
    print(f"Report: {output_path}")
    if not args.report_only:
        assert max_delta <= MAX_DELTA, f"Parity gate failed: {max_delta:.6f} > {MAX_DELTA:.6f}"


if __name__ == "__main__":
    main()
