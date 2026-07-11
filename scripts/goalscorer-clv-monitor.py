#!/usr/bin/env python3
"""Measure Fair Odds Lab publication prices against captured ATGS closes.

The five Fair Odds Lab ledgers are append-only inputs. This script never edits
them: it emits one diagnostic row per tracked signal, including explicit
missing-close reasons and capture lag.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from settlement_utils import normalize_team_name, normalize_text_basic, team_name_match_score


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIGNALS_GLOB = "data/goalscorer/fair-odds-lab-*-signals.csv"
DEFAULT_ODDS_HISTORY = "data/goalscorer/goalscorer-odds-history.csv"
DEFAULT_LIVE_HISTORY_GLOB = "data/goalscorer/**/live-history/live-board-*.json"
DEFAULT_OUTPUT = "data/goalscorer/fair-odds-lab-clv.csv"
DEFAULT_REPORT = "data/goalscorer/fair-odds-lab-clv-weekly.txt"
TRUE_CLOSE_MAX_LAG_MINUTES = 45.0
PUBLISH_CAPTURE_TOLERANCE_MINUTES = 10.0

OUTPUT_FIELDS = [
    "signal_id",
    "league",
    "date",
    "kickoff",
    "match",
    "player",
    "player_id",
    "bookmaker",
    "published_at",
    "published_odds",
    "model_p_atgs",
    "tracking_tier",
    "close_status",
    "close_source",
    "close_snapshot_kind",
    "close_captured_at",
    "close_odds",
    "close_lag_minutes",
    "published_to_close_clv",
    "implied_probability_delta",
    "match_method",
    "missing_reason",
]


def parse_float(value: object) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def parse_dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fmt_number(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def expand_paths(pattern: str) -> list[Path]:
    candidate = Path(pattern)
    glob_pattern = str(candidate if candidate.is_absolute() else ROOT / candidate)
    return [Path(path) for path in sorted(glob.glob(glob_pattern, recursive=True))]


def load_env() -> None:
    for name in (".env.local", "env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def league_from_path(path: Path) -> str:
    name = path.name
    return name.removeprefix("fair-odds-lab-").removesuffix("-signals.csv")


def fixture_pair(home: object, away: object) -> tuple[str, str]:
    return normalize_team_name(str(home or "")), normalize_team_name(str(away or ""))


def signal_identity(row: dict[str, str], league: str) -> str:
    return "|".join(
        [
            league,
            str(row.get("date") or "")[:10],
            normalize_text_basic(row.get("player") or row.get("market_player_name") or ""),
            normalize_text_basic(row.get("best_bookmaker") or ""),
            normalize_team_name(row.get("home_team") or ""),
            normalize_team_name(row.get("away_team") or ""),
        ]
    )


def load_signals(pattern: str) -> list[dict]:
    signals: list[dict] = []
    for path in expand_paths(pattern):
        league = league_from_path(path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                published_odds = parse_float(row.get("best_bookmaker_odds"))
                if not row.get("date") or not row.get("player") or not published_odds or published_odds <= 1.0:
                    continue
                signals.append(
                    {
                        **row,
                        "_league": league,
                        "_signal_id": signal_identity(row, league),
                        "_kickoff_dt": parse_dt(row.get("kickoff")),
                        "_published_dt": parse_dt(row.get("compared_at")),
                        "_published_odds": published_odds,
                        "_player_key": normalize_text_basic(row.get("market_player_name") or row.get("player") or ""),
                        "_bookmaker_key": normalize_text_basic(row.get("best_bookmaker") or ""),
                        "_fixture": fixture_pair(row.get("home_team"), row.get("away_team")),
                    }
                )
    return sorted(signals, key=lambda row: (row.get("date", ""), row["_league"], row.get("player", "")))


def capture_row(raw: dict, *, source_file: str, source_kind: str) -> dict | None:
    captured_dt = parse_dt(raw.get("captured_at"))
    odds = parse_float(raw.get("odds_decimal"))
    player_name = str(raw.get("market_player_name") or raw.get("player_name") or "").strip()
    bookmaker = str(raw.get("bookmaker") or "").strip()
    match_date = str(raw.get("match_date") or "")[:10]
    home_team = str(raw.get("home_team") or "").strip()
    away_team = str(raw.get("away_team") or "").strip()
    market = str(raw.get("market") or "ATGS").strip().upper()
    if market and market not in {"ATGS", "ANYTIME GOALSCORER"}:
        return None
    if not captured_dt or not odds or odds <= 1.0 or not player_name or not bookmaker or not match_date:
        return None
    if not home_team or not away_team:
        return None
    return {
        "captured_at": captured_dt.isoformat().replace("+00:00", "Z"),
        "captured_dt": captured_dt,
        "match_date": match_date,
        "event_id": str(raw.get("event_id") or "").strip(),
        "player_id": str(raw.get("player_id") or "").strip(),
        "player_name": player_name,
        "player_key": normalize_text_basic(player_name),
        "bookmaker": bookmaker,
        "bookmaker_key": normalize_text_basic(bookmaker),
        "home_team": home_team,
        "away_team": away_team,
        "fixture": fixture_pair(home_team, away_team),
        "odds": odds,
        "snapshot_kind": str(raw.get("snapshot_kind") or source_kind).strip(),
        "source": str(raw.get("source") or source_kind).strip(),
        "source_file": source_file,
    }


def load_canonical_captures(path_text: str) -> list[dict]:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return []
    captures: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            parsed = capture_row(raw, source_file=path.as_posix(), source_kind="canonical_history")
            if parsed:
                captures.append(parsed)
    return captures


def load_live_history_captures(pattern: str) -> list[dict]:
    captures: list[dict] = []
    for path in expand_paths(pattern):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for raw in payload.get("rows", []):
            parsed = capture_row(raw, source_file=path.as_posix(), source_kind="live_history")
            if parsed:
                captures.append(parsed)
    return captures


def load_supabase_captures(start_date: str, end_date: str) -> list[dict]:
    import requests

    load_env()
    base = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
    if not base or not key:
        raise SystemExit("Supabase CLV load requested but Supabase URL/service-role credentials are missing.")

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    endpoint = f"{base}/rest/v1/goalscorer_odds_history"
    rows: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        response = requests.get(
            endpoint,
            headers=headers,
            params={
                "select": "captured_at,match_date,event_id,kickoff_at,snapshot_kind,bookmaker,competition,market,home_team,away_team,player_name,player_team,odds_decimal,source,notes",
                "match_date": f"gte.{start_date}",
                "and": f"(match_date.lte.{end_date})",
                "order": "captured_at.asc",
                "limit": str(page_size),
                "offset": str(offset),
            },
            timeout=45,
        )
        if not response.ok:
            raise SystemExit(f"Supabase goalscorer odds load failed: {response.status_code} {response.text[:300]}")
        page = response.json()
        if not isinstance(page, list):
            raise SystemExit("Supabase goalscorer odds load returned a non-list payload.")
        for raw in page:
            parsed = capture_row(raw, source_file="supabase:goalscorer_odds_history", source_kind="supabase_history")
            if parsed:
                rows.append(parsed)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def dedupe_captures(captures: Iterable[dict]) -> list[dict]:
    priority = {"supabase_history": 3, "canonical_history": 2, "live_history": 1}
    deduped: dict[tuple, dict] = {}
    for row in captures:
        key = (
            row["match_date"],
            row["fixture"],
            row["player_key"],
            row["bookmaker_key"],
            row["captured_at"],
            row["odds"],
        )
        current = deduped.get(key)
        source_kind = (
            "supabase_history"
            if row["source_file"].startswith("supabase:")
            else "canonical_history"
            if row["source_file"].endswith("goalscorer-odds-history.csv")
            else "live_history"
        )
        current_kind = (
            "supabase_history"
            if current and current["source_file"].startswith("supabase:")
            else "canonical_history"
            if current and current["source_file"].endswith("goalscorer-odds-history.csv")
            else "live_history"
        )
        if current is None or priority[source_kind] > priority[current_kind]:
            deduped[key] = row
    return list(deduped.values())


def fixture_match_score(signal_fixture: tuple[str, str], capture_fixture: tuple[str, str]) -> float:
    sh, sa = signal_fixture
    ch, ca = capture_fixture
    direct = team_name_match_score(sh, ch) + team_name_match_score(sa, ca)
    reversed_score = team_name_match_score(sh, ca) + team_name_match_score(sa, ch)
    return max(direct, reversed_score)


def matching_captures(signal: dict, captures_by_date: dict[str, list[dict]]) -> tuple[list[dict], str]:
    candidates = captures_by_date.get(str(signal.get("date") or "")[:10], [])
    if not candidates:
        return [], "no_capture_on_match_date"

    player_id = str(signal.get("player_id") or "").strip()
    id_matches = [row for row in candidates if player_id and row["player_id"] == player_id]
    name_matches = [
        row
        for row in candidates
        if row["player_key"] == signal["_player_key"]
        and (not player_id or not row["player_id"] or row["player_id"] == player_id)
    ]
    player_candidates = [*id_matches]
    seen = {id(row) for row in player_candidates}
    player_candidates.extend(row for row in name_matches if id(row) not in seen)
    match_method = "player_id_or_exact_name" if id_matches else "player_name"
    if not player_candidates:
        return [], "player_not_found"

    fixture_candidates = [
        row for row in player_candidates if fixture_match_score(signal["_fixture"], row["fixture"]) >= 1.78
    ]
    if not fixture_candidates:
        return [], "fixture_not_found"

    same_book = [row for row in fixture_candidates if row["bookmaker_key"] == signal["_bookmaker_key"]]
    if same_book:
        return same_book, match_method + "+same_book"
    pinnacle = [row for row in fixture_candidates if row["bookmaker_key"] == "pinnacle"]
    if pinnacle:
        return pinnacle, match_method + "+pinnacle_fallback"
    return [], "bookmaker_not_found"


def evaluate_signal(signal: dict, captures_by_date: dict[str, list[dict]]) -> dict[str, str]:
    base = {
        "signal_id": signal["_signal_id"],
        "league": signal["_league"],
        "date": str(signal.get("date") or "")[:10],
        "kickoff": str(signal.get("kickoff") or ""),
        "match": str(signal.get("match") or ""),
        "player": str(signal.get("player") or ""),
        "player_id": str(signal.get("player_id") or ""),
        "bookmaker": str(signal.get("best_bookmaker") or ""),
        "published_at": str(signal.get("compared_at") or ""),
        "published_odds": fmt_number(signal["_published_odds"], 4),
        "model_p_atgs": str(signal.get("model_p_atgs") or ""),
        "tracking_tier": str(signal.get("tracking_tier") or "raw_model_legacy"),
        "close_status": "missing",
        "close_source": "",
        "close_snapshot_kind": "",
        "close_captured_at": "",
        "close_odds": "",
        "close_lag_minutes": "",
        "published_to_close_clv": "",
        "implied_probability_delta": "",
        "match_method": "",
        "missing_reason": "",
    }

    kickoff_dt = signal["_kickoff_dt"]
    published_dt = signal["_published_dt"]
    if not kickoff_dt:
        base["missing_reason"] = "invalid_kickoff"
        return base
    if not published_dt:
        base["missing_reason"] = "invalid_published_at"
        return base

    candidates, match_method = matching_captures(signal, captures_by_date)
    if not candidates:
        base["missing_reason"] = match_method
        return base

    tolerance_seconds = PUBLISH_CAPTURE_TOLERANCE_MINUTES * 60.0
    eligible = [
        row
        for row in candidates
        if row["captured_dt"] <= kickoff_dt
        and (row["captured_dt"] - published_dt).total_seconds() >= -tolerance_seconds
    ]
    if not eligible:
        if any(row["captured_dt"] > kickoff_dt for row in candidates):
            base["missing_reason"] = "only_post_kickoff_capture"
        else:
            base["missing_reason"] = "no_post_publication_capture"
        base["match_method"] = match_method
        return base

    close = max(eligible, key=lambda row: row["captured_dt"])
    lag_minutes = max(0.0, (kickoff_dt - close["captured_dt"]).total_seconds() / 60.0)
    clv = (signal["_published_odds"] / close["odds"]) - 1.0
    implied_delta = (1.0 / close["odds"]) - (1.0 / signal["_published_odds"])
    close_status = "true_close" if lag_minutes <= TRUE_CLOSE_MAX_LAG_MINUTES else "lagged_close"
    if "pinnacle_fallback" in match_method:
        close_status = "pinnacle_reference"

    base.update(
        {
            "close_status": close_status,
            "close_source": close["source"],
            "close_snapshot_kind": close["snapshot_kind"],
            "close_captured_at": close["captured_at"],
            "close_odds": fmt_number(close["odds"], 4),
            "close_lag_minutes": fmt_number(lag_minutes, 1),
            "published_to_close_clv": fmt_number(clv, 6),
            "implied_probability_delta": fmt_number(implied_delta, 6),
            "match_method": match_method,
            "missing_reason": "",
        }
    )
    return base


def write_csv(path_text: str, rows: list[dict[str, str]]) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def price_band(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value < 3.0:
        return "<3.0"
    if value < 4.0:
        return "3.0-3.99"
    if value < 5.0:
        return "4.0-4.99"
    return "5.0+"


def summary_line(label: str, rows: list[dict[str, str]]) -> str:
    values = [parse_float(row.get("published_to_close_clv")) for row in rows]
    clv = [value for value in values if value is not None]
    if not clv:
        return f"{label}: n={len(rows)} close_n=0 avg=- median=- positive=-"
    positive = sum(value > 0 for value in clv) / len(clv)
    return (
        f"{label}: n={len(rows)} close_n={len(clv)} "
        f"avg={statistics.mean(clv):+.2%} median={statistics.median(clv):+.2%} "
        f"positive={positive:.1%}"
    )


def write_report(path_text: str, rows: list[dict[str, str]], captures_loaded: int) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    matched = [row for row in rows if row["close_odds"]]
    true_close = [row for row in rows if row["close_status"] == "true_close"]
    lagged = [row for row in rows if row["close_status"] == "lagged_close"]
    pinnacle = [row for row in rows if row["close_status"] == "pinnacle_reference"]
    missing = [row for row in rows if row["close_status"] == "missing"]
    reasons = Counter(row["missing_reason"] or "unknown" for row in missing)
    coverage = len(matched) / len(rows) if rows else 0.0

    lines = [
        "Fair Odds Lab CLV Monitor",
        "=============================",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}",
        "Status: INTERNAL_DIAGNOSTIC_ONLY",
        "Public page role: live research fair odds; no betting record",
        "",
        "Coverage",
        f"Signals: {len(rows)}",
        f"Captured price rows loaded: {captures_loaded}",
        f"Matched closes/references: {len(matched)} ({coverage:.1%})",
        f"True same-book closes (<= {TRUE_CLOSE_MAX_LAG_MINUTES:.0f}m): {len(true_close)}",
        f"Lagged same-book closes: {len(lagged)}",
        f"Pinnacle references: {len(pinnacle)}",
        f"Missing: {len(missing)}",
        "",
        "Overall",
        summary_line("all", rows),
        summary_line("true_close_only", true_close),
        "",
        "By league",
    ]
    by_league: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_league[row["league"]].append(row)
    lines.extend(summary_line(league, sample) for league, sample in sorted(by_league.items()))
    lines.extend(["", "By publication price"])
    by_price: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_price[price_band(parse_float(row.get("published_odds")))].append(row)
    lines.extend(summary_line(band, sample) for band, sample in sorted(by_price.items()))
    lines.extend(["", "Missing reasons"])
    lines.extend(f"{reason}: {count}" for reason, count in sorted(reasons.items()))
    if not reasons:
        lines.append("none")
    lines.extend(
        [
            "",
            "Methodology",
            "- Positive CLV means the published decimal price was greater than the captured close.",
            "- Same-book captures are primary; Pinnacle is labelled as a cross-book reference.",
            "- ATGS is one-sided here, so these are raw price movements, not no-vig CLV.",
            "- Captures after kickoff and captures materially before publication are rejected.",
            "- Missing closes stay missing and reduce coverage.",
            "- This report does not alter Fair Odds Lab ledgers or the public page.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an internal Fair Odds Lab published-to-close CLV report")
    parser.add_argument("--signals-glob", default=DEFAULT_SIGNALS_GLOB)
    parser.add_argument("--odds-history", default=DEFAULT_ODDS_HISTORY)
    parser.add_argument("--live-history-glob", default=DEFAULT_LIVE_HISTORY_GLOB)
    parser.add_argument("--supabase", action="store_true", help="Load canonical captured odds from Supabase")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    signals = load_signals(args.signals_glob)
    signal_dates = [str(row.get("date") or "")[:10] for row in signals if row.get("date")]
    supabase_captures = (
        load_supabase_captures(min(signal_dates), max(signal_dates))
        if args.supabase and signal_dates
        else []
    )
    captures = dedupe_captures(
        [
            *load_canonical_captures(args.odds_history),
            *load_live_history_captures(args.live_history_glob),
            *supabase_captures,
        ]
    )
    captures_by_date: dict[str, list[dict]] = defaultdict(list)
    for capture in captures:
        captures_by_date[capture["match_date"]].append(capture)
    rows = [evaluate_signal(signal, captures_by_date) for signal in signals]
    output = write_csv(args.output, rows)
    report = write_report(args.report, rows, len(captures))
    print(f"Signals: {len(signals)}")
    print(f"Unique captures: {len(captures)}")
    print(f"Matched closes/references: {sum(bool(row['close_odds']) for row in rows)}")
    print(f"Output: {output}")
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
