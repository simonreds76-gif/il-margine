#!/usr/bin/env python3
"""Build a private Assist Value shadow board from assist odds + set-piece roles.

This is intentionally not a production model. It only proves the live market
and role-source join, then writes a research-only board under data/assist-value.
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ODDS_INPUT = "data/assist-value/inbox/*.csv"
DEFAULT_ROLES = "data/assist-value/rotowire-setpiece-roles.csv"
DEFAULT_OUT = "data/assist-value/assist-value-shadow-board.csv"
DEFAULT_REPORT = "data/assist-value/assist-value-shadow-report.txt"


OUTPUT_FIELDS = [
    "captured_at",
    "match_date",
    "kickoff_at",
    "competition",
    "home_team",
    "away_team",
    "bookmaker",
    "player_name",
    "odds_decimal",
    "role_team",
    "corner_share_last5_pct",
    "corner_share_total_pct",
    "fk_share_last5_pct",
    "fk_share_total_pct",
    "setpiece_share_last5_pct",
    "total_share_pct",
    "latest_role_week",
    "role_source",
    "join_status",
    "shadow_status",
    "notes",
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def norm_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("'", "").replace("’", "").replace("‘", "")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def norm_team(value: str) -> str:
    text = norm_text(value)
    drop = {
        "afc",
        "bc",
        "cf",
        "fc",
        "sc",
        "sv",
        "the",
        "club",
        "de",
        "la",
    }
    tokens = [token for token in text.split() if token not in drop]
    return " ".join(tokens)


def read_csvs(patterns: Iterable[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for pattern in patterns:
        matched = sorted(glob.glob(str(ROOT / pattern) if not Path(pattern).is_absolute() else pattern))
        for path in matched:
            with open(path, newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    row["_source_file"] = str(Path(path).relative_to(ROOT)) if Path(path).is_absolute() else path
                    rows.append({key: "" if value is None else str(value) for key, value in row.items()})
    return rows


def read_roles(path: str) -> dict[str, list[dict[str, str]]]:
    target = ROOT / path if not Path(path).is_absolute() else Path(path)
    by_player: dict[str, list[dict[str, str]]] = {}
    if not target.exists():
        return by_player
    with open(target, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            player_key = norm_text(str(row.get("player_name") or ""))
            if not player_key:
                continue
            cleaned = {key: "" if value is None else str(value) for key, value in row.items()}
            by_player.setdefault(player_key, []).append(cleaned)
    return by_player


def choose_role(odds_row: dict[str, str], candidates: list[dict[str, str]]) -> tuple[dict[str, str] | None, str]:
    if not candidates:
        return None, "unmatched"
    if len(candidates) == 1:
        return candidates[0], "matched"

    home = norm_team(odds_row.get("home_team", ""))
    away = norm_team(odds_row.get("away_team", ""))
    match_teams = {home, away}
    for candidate in candidates:
        team = norm_team(candidate.get("team", "") or candidate.get("rotowire_team", ""))
        if team in match_teams:
            return candidate, "matched_team_disambiguated"

    return candidates[0], "ambiguous_player_name"


def as_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_rows(odds_rows: list[dict[str, str]], roles_by_player: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for odds in odds_rows:
        player = str(odds.get("player_name") or "").strip()
        if not player:
            continue
        role, join_status = choose_role(odds, roles_by_player.get(norm_text(player), []))
        shadow_status = "role_matched" if role and join_status != "ambiguous_player_name" else join_status
        output.append(
            {
                "captured_at": odds.get("captured_at", ""),
                "match_date": odds.get("match_date", ""),
                "kickoff_at": odds.get("kickoff_at", ""),
                "competition": odds.get("competition", ""),
                "home_team": odds.get("home_team", ""),
                "away_team": odds.get("away_team", ""),
                "bookmaker": odds.get("bookmaker", ""),
                "player_name": player,
                "odds_decimal": odds.get("odds_decimal", ""),
                "role_team": (role or {}).get("team", "") or (role or {}).get("rotowire_team", ""),
                "corner_share_last5_pct": (role or {}).get("corner_share_last5_pct", ""),
                "corner_share_total_pct": (role or {}).get("corner_share_total_pct", ""),
                "fk_share_last5_pct": (role or {}).get("fk_share_last5_pct", ""),
                "fk_share_total_pct": (role or {}).get("fk_share_total_pct", ""),
                "setpiece_share_last5_pct": (role or {}).get("setpiece_share_last5_pct", ""),
                "total_share_pct": (role or {}).get("total_share_pct", ""),
                "latest_role_week": (role or {}).get("latest_week", ""),
                "role_source": (role or {}).get("source", ""),
                "join_status": join_status,
                "shadow_status": shadow_status,
                "notes": "research_only_no_public_signal",
            }
        )
    output.sort(
        key=lambda row: (
            as_float(row.get("setpiece_share_last5_pct", "")),
            as_float(row.get("corner_share_last5_pct", "")),
            as_float(row.get("fk_share_last5_pct", "")),
        ),
        reverse=True,
    )
    return output


def write_csv(path: str, rows: list[dict[str, str]]) -> Path:
    target = ROOT / path if not Path(path).is_absolute() else Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return target


def write_report(path: str, rows: list[dict[str, str]], odds_rows: list[dict[str, str]], role_count: int) -> Path:
    target = ROOT / path if not Path(path).is_absolute() else Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    matched = [row for row in rows if row["shadow_status"] == "role_matched"]
    ambiguous = [row for row in rows if row["join_status"] == "ambiguous_player_name"]
    unmatched = [row for row in rows if row["join_status"] == "unmatched"]
    match_rate = (len(matched) / len(rows) * 100.0) if rows else 0.0

    lines = [
        "Assist Value Shadow Report",
        f"generated_at_utc: {now_utc_iso()}",
        "",
        "Status",
        "shadow_status: ENABLED_RESEARCH_ONLY",
        "public_signal_status: DISABLED",
        "model_status: NOT_FITTED",
        "fair_odds_status: NOT_AUTHORISED",
        "",
        "Inputs",
        f"assist_odds_rows: {len(odds_rows)}",
        f"role_players_loaded: {role_count}",
        "",
        "Join",
        f"shadow_rows: {len(rows)}",
        f"role_matched_rows: {len(matched)}",
        f"role_match_rate_pct: {match_rate:.2f}",
        f"ambiguous_player_rows: {len(ambiguous)}",
        f"unmatched_player_rows: {len(unmatched)}",
        "",
        "Interpretation",
        "This board is an evidence layer only: Bet365 assist market rows enriched with RotoWire set-piece role shares.",
        "It is not a betting model, not a public Fair Odds Lab lane, and not a value signal.",
        "",
        "Top role-matched rows",
    ]
    for row in matched[:20]:
        lines.append(
            " - "
            f"{row['player_name']} | {row['home_team']} vs {row['away_team']} | "
            f"odds {row['odds_decimal']} | setpiece_last5 {row['setpiece_share_last5_pct']} | "
            f"corners_last5 {row['corner_share_last5_pct']} | fk_last5 {row['fk_share_last5_pct']}"
        )
    if not matched:
        lines.append(" - none")
    if unmatched:
        lines.extend(["", "Unmatched sample"])
        for row in unmatched[:20]:
            lines.append(f" - {row['player_name']} | {row['home_team']} vs {row['away_team']}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Build private assist-value shadow board")
    parser.add_argument("--odds-input", nargs="+", default=[DEFAULT_ODDS_INPUT])
    parser.add_argument("--roles", default=DEFAULT_ROLES)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--report-out", default=DEFAULT_REPORT)
    args = parser.parse_args()

    odds_rows = read_csvs(args.odds_input)
    roles_by_player = read_roles(args.roles)
    rows = build_rows(odds_rows, roles_by_player)
    out_path = write_csv(args.out, rows)
    report_path = write_report(args.report_out, rows, odds_rows, sum(len(v) for v in roles_by_player.values()))

    print(f"Assist shadow board rows: {len(rows):,}")
    print(f"Saved: {out_path}")
    print(f"Saved: {report_path}")


if __name__ == "__main__":
    main()
