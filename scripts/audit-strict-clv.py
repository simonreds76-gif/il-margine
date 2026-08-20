#!/usr/bin/env python3
"""
Audit live strict-policy scrape odds against tennis-data Pinnacle closing odds.

Purpose:
- Determine whether live strict bets are getting positive CLV relative to close.
- Quantify whether the apparent edge exists at scrape time or evaporates by close.

Default scope:
- data/backtest/strict-signals.csv
- match bets only by default (`--bet-type spread` audits spread rows directly)
- settled rows only
- match closes from captured Pinnacle history only by default
- data/backtest/atp-2026.xlsx is available only behind --allow-stale-fallback
- spread closes from captured Pinnacle history only

Outputs:
- data/backtest/strict-clv-audit-2026.csv
- data/backtest/strict-clv-audit-2026.txt

Positive CLV convention in this script:
- clv_implied_delta = (1 / closing_odds) - (1 / scrape_odds)
- positive = the market moved toward our bet (good)
- negative = the market moved away from our bet (bad)
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

import requests

from signal_storage import STRICT_SIGNAL_PATHS


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"
ONCOURT_DIR = ROOT / "data" / "oncourt"
HTTP_TIMEOUT = 30
HISTORY_SIGNAL_GRACE_SECONDS = 300
DEFAULT_MAX_CLOSE_LAG_MINUTES = 720

DEFAULT_SIGNALS = STRICT_SIGNAL_PATHS.archive
DEFAULT_XLSX = DATA_DIR / "atp-2026.xlsx"
DEFAULT_DETAIL_CSV = DATA_DIR / "strict-clv-audit-2026.csv"
DEFAULT_SUMMARY_TXT = DATA_DIR / "strict-clv-audit-2026.txt"
DEFAULT_UNMATCHED_CSV = DATA_DIR / "strict-clv-audit-2026-unmatched.csv"
DEFAULT_LOCAL_HISTORY_DIR = ROOT / "data" / "pinnacle-history"

KEY_FIELDS = ["date", "player1", "player2", "surface", "series", "confidence", "side"]


@dataclass
class ClosingMatch:
    date_iso: str
    date_ord: int
    surface: str
    series: str
    tournament: str
    location: str
    player1_id: int
    player2_id: int
    close_odds1: float
    close_odds2: float


@dataclass
class HistoryRow:
    capture_date: str
    captured_at: str
    captured_ts: datetime
    kickoff_iso: str
    kickoff_ts: datetime | None
    capture_mode: str
    source: str
    league: str
    player1_name: str
    player2_name: str
    odds1: float
    odds2: float
    spread_line: float | None
    spread_odds1: float | None
    spread_odds2: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit live strict scrape odds vs tennis-data Pinnacle closing odds.")
    parser.add_argument("--signals", default=str(DEFAULT_SIGNALS), help="Strict signal CSV to audit.")
    parser.add_argument("--bet-type", choices=["match", "spread"], default="match", help="Audit match or spread bets.")
    parser.add_argument("--xlsx", default=str(DEFAULT_XLSX), help="Tennis-data ATP XLSX with closing Pinnacle odds.")
    parser.add_argument("--detail-csv", default=str(DEFAULT_DETAIL_CSV), help="Detailed audit CSV output.")
    parser.add_argument("--summary-txt", default=str(DEFAULT_SUMMARY_TXT), help="Summary text output.")
    parser.add_argument("--unmatched-csv", default=str(DEFAULT_UNMATCHED_CSV), help="Unmatched-row diagnostic CSV output.")
    parser.add_argument(
        "--allow-stale-fallback",
        action="store_true",
        help="Allow fallback to the tennis-data XLSX close file after captured-history misses. Default off to avoid stale CLV contamination.",
    )
    parser.add_argument(
        "--require-verified-kickoff",
        action="store_true",
        help="Reject captured closes without kickoff metadata. Required for decision-grade CLV lanes.",
    )
    parser.add_argument(
        "--max-close-lag-minutes",
        type=int,
        default=None,
        help=f"Optional maximum gap between captured close and kickoff. Challenger v2 uses {DEFAULT_MAX_CLOSE_LAG_MINUTES} minutes.",
    )
    parser.add_argument(
        "--local-history-dir",
        default=str(DEFAULT_LOCAL_HISTORY_DIR),
        help="Directory containing local Pinnacle capture CSVs to merge into CLV history coverage.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write outputs; print summary only.")
    return parser.parse_args()


def norm(v: str | None) -> str:
    return (v or "").strip().lower()


def parse_float(v: Any) -> float | None:
    if v is None:
        return None
    txt = str(v).strip()
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def parse_int(v: Any) -> int | None:
    f = parse_float(v)
    if f is None:
        return None
    try:
        return int(f)
    except (TypeError, ValueError):
        return None


def parse_iso_date(v: str | None) -> date | None:
    if v is None:
        return None
    txt = str(v).strip()
    if not txt:
        return None
    try:
        return date.fromisoformat(txt[:10])
    except ValueError:
        return None


def parse_signal_ts(signal_date: str | None, time_utc: str | None) -> datetime | None:
    d = parse_iso_date(signal_date)
    if d is None:
        return None
    txt = (time_utc or "").strip()
    if not txt:
        return datetime.combine(d, time.min, tzinfo=timezone.utc)
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(txt, fmt).time()
            return datetime.combine(d, t, tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def parse_timestamp(v: str | None) -> datetime | None:
    txt = (v or "").strip()
    if not txt:
        return None
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        return None


def pct(v: float) -> str:
    return f"{v:+.3f}%"


def display_path(path: Path | str) -> str:
    if isinstance(path, str):
        return path
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def row_key(row: dict[str, str], include_mode: bool = True) -> tuple[str, ...]:
    event_date = norm(row.get("match_date")) or norm(row.get("date"))
    out = [
        event_date,
        norm(row.get("player1")),
        norm(row.get("player2")),
        norm(row.get("surface")),
        norm(row.get("series")),
        norm(row.get("confidence")),
        norm(row.get("side")),
        norm(row.get("bet_type") or "match"),
        norm(row.get("signal_profile")),
    ]
    if include_mode:
        out.append(norm(row.get("policy_mode") or "base"))
    return tuple(out)


def is_settled(row: dict[str, str]) -> bool:
    return norm(row.get("settlement_status")) == "settled"


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key: dict[tuple[str, ...], dict[str, str]] = {}
    settlement_fields = {
        "settlement_status",
        "result",
        "bet_outcome",
        "won_bet",
        "match_date",
        "player1_id",
        "player2_id",
        "winner_id",
        "loser_id",
        "settled_at",
        "settlement_note",
        "closing_odds1",
        "closing_odds2",
        "closing_source",
    }
    for row in rows:
        k = row_key(row, include_mode=True)
        prev = by_key.get(k)
        if prev is None:
            by_key[k] = row
            continue
        if is_settled(row):
            for field, value in row.items():
                if norm(value) and (field in settlement_fields or not norm(prev.get(field))):
                    prev[field] = value
    return list(by_key.values())


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def load_env() -> None:
    for name in [".env.local", "env.local"]:
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_supabase_rest() -> tuple[str, dict[str, str]]:
    load_env()
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise RuntimeError("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.local")
    return f"{url}/rest/v1", {"apikey": key, "Authorization": f"Bearer {key}"}


def load_backtest_module() -> Any:
    path = ROOT / "scripts" / "backtest-fair-odds.py"
    module_name = "backtest_fair_odds_mod"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_closing_matches(xlsx_path: Path) -> tuple[list[ClosingMatch], dict[str, Any]]:
    mod = load_backtest_module()
    matches, skip, short_names = mod._load_backtest_matches([xlsx_path])
    players_path = ONCOURT_DIR / "players_atp.csv"
    games_path = ONCOURT_DIR / "games_atp.csv"
    tours_path = ONCOURT_DIR / "tours_atp.csv"
    courts_path = ONCOURT_DIR / "courts.csv"
    for p in (players_path, games_path, tours_path, courts_path):
        if not p.exists():
            raise FileNotFoundError(f"Missing required OnCourt file: {p}")

    oncourt_players = mod._load_oncourt_players(players_path)
    players_by_id = {int(r["id"]): r for r in oncourt_players}
    tours = mod._load_tour_info(tours_path, courts_path)
    popularity_by_pid = mod._load_player_popularity(games_path, players_by_id, tours)
    name_map, map_report = mod._build_tennis_data_name_map(short_names, oncourt_players, popularity_by_pid=popularity_by_pid)

    closing_matches: list[ClosingMatch] = []
    skipped = Counter()
    for m in matches:
        wid = name_map.get(m.winner_name_short)
        lid = name_map.get(m.loser_name_short)
        if wid is None:
            skipped["unmapped_winner"] += 1
            continue
        if lid is None:
            skipped["unmapped_loser"] += 1
            continue
        if wid == lid:
            skipped["same_player_after_mapping"] += 1
            continue
        close_odds1 = float(m.psw)
        close_odds2 = float(m.psl)
        closing_matches.append(
            ClosingMatch(
                date_iso=m.date_iso,
                date_ord=m.date_ord,
                surface=m.surface,
                series=m.series,
                tournament=m.tournament,
                location=m.location,
                player1_id=int(wid),
                player2_id=int(lid),
                close_odds1=close_odds1,
                close_odds2=close_odds2,
            )
        )

    meta = {
        "xlsx_matches_loaded": len(matches),
        "xlsx_skip": dict(skip),
        "name_map_report": map_report,
        "closing_matches_mapped": len(closing_matches),
        "closing_matches_skipped": dict(skipped),
    }
    return closing_matches, meta


def _norm_pinnacle_name(s: str) -> str:
    t = (s or "").strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.replace("-", "").replace("'", "")


def _tokenise_pinnacle_name(name: str) -> list[str]:
    cleaned = (name or "").replace(",", " ").replace("-", " ")
    cleaned = re.sub(r"\s*\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\s*\[[^\]]*\]", " ", cleaned)
    return [
        _norm_pinnacle_name(tok)
        for tok in cleaned.split()
        if tok and not re.match(r"^[a-z]$", _norm_pinnacle_name(tok))
    ]


def _surname_keys(name: str) -> list[str]:
    tokens = _tokenise_pinnacle_name(name)
    if not tokens:
        return []
    out = {tokens[-1]}
    if len(tokens) >= 2:
        out.add(tokens[-2])
        out.add(f"{tokens[-2]} {tokens[-1]}")
        out.add(f"{tokens[-2]}{tokens[-1]}")
    return list(out)


def _make_pair_keys(a: str, b: str) -> list[str]:
    out = set()
    for ka in _surname_keys(a):
        for kb in _surname_keys(b):
            out.add(f"{ka}|{kb}")
    return list(out)


def _first_word(name: str) -> str:
    tokens = _tokenise_pinnacle_name(name)
    return tokens[0] if tokens else ""


def _full_name(name: str) -> str:
    return " ".join(_tokenise_pinnacle_name(name))


def _is_doubles_name(name: str | None) -> bool:
    return "/" in (name or "") or "&" in (name or "")


def fetch_supabase_history_rows(start_date: date, end_date: date) -> tuple[list[HistoryRow], dict[str, Any]]:
    try:
        base, headers = get_supabase_rest()
    except Exception as exc:
        return [], {"enabled": False, "error": str(exc)}

    all_rows: list[HistoryRow] = []
    offset = 0
    limit = 1000
    while True:
        query = [
            ("select", "capture_date,captured_at,capture_mode,league,player1_name,player2_name,odds1,odds2,spread_line,spread_odds1,spread_odds2,kickoff_iso"),
            ("bookmaker", "eq.Pinnacle"),
            ("capture_date", f"gte.{start_date.isoformat()}"),
            ("capture_date", f"lte.{end_date.isoformat()}"),
            ("order", "captured_at.desc"),
            ("limit", str(limit)),
            ("offset", str(offset)),
        ]
        try:
            resp = requests.get(f"{base}/bookmaker_odds_history", headers=headers, params=query, timeout=HTTP_TIMEOUT)
            if resp.status_code == 404:
                return [], {"enabled": False, "error": "bookmaker_odds_history table not found"}
            if not resp.ok:
                return [], {"enabled": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            batch = resp.json()
        except requests.RequestException as exc:
            return [], {"enabled": False, "error": str(exc)}

        if not batch:
            break
        for row in batch:
            ts = parse_timestamp(row.get("captured_at"))
            if ts is None:
                continue
            all_rows.append(
                HistoryRow(
                    capture_date=str(row.get("capture_date") or ""),
                    captured_at=str(row.get("captured_at") or ""),
                    captured_ts=ts,
                    kickoff_iso=str(row.get("kickoff_iso") or ""),
                    kickoff_ts=parse_timestamp(row.get("kickoff_iso")),
                    capture_mode=str(row.get("capture_mode") or ""),
                    source="supabase",
                    league=str(row.get("league") or ""),
                    player1_name=str(row.get("player1_name") or ""),
                    player2_name=str(row.get("player2_name") or ""),
                    odds1=float(row.get("odds1") or 0),
                    odds2=float(row.get("odds2") or 0),
                    spread_line=parse_float(row.get("spread_line")),
                    spread_odds1=parse_float(row.get("spread_odds1")),
                    spread_odds2=parse_float(row.get("spread_odds2")),
                )
            )
        if len(batch) < limit:
            break
        offset += limit

    return all_rows, {
        "enabled": True,
        "rows": len(all_rows),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


def load_local_history_rows(history_dir: Path, start_date: date, end_date: date) -> tuple[list[HistoryRow], dict[str, Any]]:
    if not history_dir.exists():
        return [], {"enabled": False, "error": f"missing directory: {history_dir}"}

    rows: list[HistoryRow] = []
    files_scanned = 0
    for path in sorted(history_dir.glob("pinnacle-history-*.csv")):
        files_scanned += 1
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                for raw in csv.DictReader(f):
                    if norm(raw.get("bookmaker")) not in {"", "pinnacle"}:
                        continue
                    capture_date = parse_iso_date(raw.get("capture_date"))
                    if capture_date is None or capture_date < start_date or capture_date > end_date:
                        continue
                    ts = parse_timestamp(raw.get("captured_at"))
                    if ts is None:
                        continue
                    odds1 = parse_float(raw.get("odds1"))
                    odds2 = parse_float(raw.get("odds2"))
                    if odds1 is None or odds2 is None or odds1 <= 1 or odds2 <= 1:
                        continue
                    rows.append(
                        HistoryRow(
                            capture_date=capture_date.isoformat(),
                            captured_at=str(raw.get("captured_at") or ""),
                            captured_ts=ts,
                            kickoff_iso=str(raw.get("kickoff_iso") or ""),
                            kickoff_ts=parse_timestamp(raw.get("kickoff_iso")),
                            capture_mode=str(raw.get("capture_mode") or ""),
                            source="local_csv",
                            league=str(raw.get("league") or ""),
                            player1_name=str(raw.get("player1_name") or ""),
                            player2_name=str(raw.get("player2_name") or ""),
                            odds1=odds1,
                            odds2=odds2,
                            spread_line=parse_float(raw.get("spread_line")),
                            spread_odds1=parse_float(raw.get("spread_odds1")),
                            spread_odds2=parse_float(raw.get("spread_odds2")),
                        )
                    )
        except OSError:
            continue

    return rows, {
        "enabled": True,
        "rows": len(rows),
        "files_scanned": files_scanned,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


def merge_history_rows(primary: list[HistoryRow], secondary: list[HistoryRow]) -> list[HistoryRow]:
    by_key: dict[tuple[Any, ...], HistoryRow] = {}
    source_priority = {"supabase": 2, "local_csv": 1}
    for row in [*primary, *secondary]:
        canonical_ts = row.captured_ts.isoformat()
        key = (
            canonical_ts,
            row.capture_mode,
            row.player1_name,
            row.player2_name,
            row.odds1,
            row.odds2,
            row.league,
            row.spread_line,
            row.spread_odds1,
            row.spread_odds2,
            row.kickoff_iso,
        )
        prev = by_key.get(key)
        if prev is None or source_priority.get(row.source, 0) > source_priority.get(prev.source, 0):
            by_key[key] = row
    return sorted(by_key.values(), key=lambda r: r.captured_ts)


def load_history_rows(history_dir: Path, start_date: date, end_date: date) -> tuple[list[HistoryRow], dict[str, Any]]:
    supabase_rows, supabase_meta = fetch_supabase_history_rows(start_date, end_date)
    local_rows, local_meta = load_local_history_rows(history_dir, start_date, end_date)
    combined = merge_history_rows(supabase_rows, local_rows)
    return combined, {
        "enabled": bool(combined),
        "rows": len(combined),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "supabase_rows": len(supabase_rows),
        "local_rows": len(local_rows),
        "local_files_scanned": local_meta.get("files_scanned", 0),
        "supabase_error": supabase_meta.get("error", ""),
        "local_error": local_meta.get("error", ""),
    }


def lag_bucket(lag_days: int) -> str:
    if lag_days <= 0:
        return "same_day"
    if lag_days == 1:
        return "plus_1_day"
    if lag_days <= 3:
        return "plus_2_3_days"
    return "plus_4plus_days"


def value_bucket(value_pct: float) -> str:
    if value_pct < 10:
        return "5-10%"
    if value_pct < 15:
        return "10-15%"
    if value_pct < 20:
        return "15-20%"
    return "20%+"


def spread_line_bucket(line: float | None) -> str:
    if line is None:
        return "n/a"
    return f"{abs(float(line)):.1f}"


def build_closing_index(matches: list[ClosingMatch]) -> dict[frozenset[int], list[ClosingMatch]]:
    out: dict[frozenset[int], list[ClosingMatch]] = defaultdict(list)
    for m in matches:
        out[frozenset({m.player1_id, m.player2_id})].append(m)
    for pair in out:
        out[pair].sort(key=lambda x: x.date_ord)
    return out


def build_history_lookup(rows: list[HistoryRow]) -> dict[str, list[tuple[HistoryRow, bool]]]:
    out: dict[str, list[tuple[HistoryRow, bool]]] = defaultdict(list)
    for row in rows:
        if _is_doubles_name(row.player1_name) or _is_doubles_name(row.player2_name):
            continue
        for key in _make_pair_keys(row.player1_name, row.player2_name):
            out[key].append((row, False))
        for key in _make_pair_keys(row.player2_name, row.player1_name):
            out[key].append((row, True))
    return out


def match_signal_to_history(
    row: dict[str, str],
    lookup: dict[str, list[tuple[HistoryRow, bool]]],
    signal_line: float | None = None,
    require_verified_kickoff: bool = False,
    max_close_lag_minutes: int | None = None,
) -> tuple[HistoryRow | None, bool, str]:
    signal_ts = parse_signal_ts(row.get("date"), row.get("time_utc"))
    match_dt = parse_iso_date(row.get("match_date"))
    p1 = (row.get("player1") or "").strip()
    p2 = (row.get("player2") or "").strip()
    if signal_ts is None:
        return None, False, "missing_signal_ts"
    if match_dt is None:
        return None, False, "missing_match_date"
    if not p1 or not p2:
        return None, False, "missing_player_names"

    earliest_ts = signal_ts - timedelta(seconds=HISTORY_SIGNAL_GRACE_SECONDS)
    cutoff_ts = datetime.combine(match_dt + timedelta(days=1), time.min, tzinfo=timezone.utc)
    candidate_map: dict[str, tuple[HistoryRow, bool, int]] = {}
    rejected_missing_kickoff = False
    rejected_post_kickoff = False
    rejected_stale_close = False
    for key in _make_pair_keys(p1, p2):
        for hist, reversed_for_signal in lookup.get(key, []):
            if hist.captured_ts < earliest_ts or hist.captured_ts >= cutoff_ts:
                continue
            if hist.kickoff_ts is None:
                if require_verified_kickoff:
                    rejected_missing_kickoff = True
                    continue
            else:
                close_lag_minutes = (hist.kickoff_ts - hist.captured_ts).total_seconds() / 60.0
                if close_lag_minutes < 0:
                    rejected_post_kickoff = True
                    continue
                if max_close_lag_minutes is not None and close_lag_minutes > max_close_lag_minutes:
                    rejected_stale_close = True
                    continue
            ident = (
                f"{hist.captured_ts.isoformat()}|{hist.player1_name}|{hist.player2_name}|"
                f"{'R' if reversed_for_signal else 'N'}|{hist.spread_line}|"
                f"{hist.spread_odds1}|{hist.spread_odds2}"
            )
            if ident in candidate_map:
                prev = candidate_map[ident]
                candidate_map[ident] = (prev[0], prev[1], prev[2] + 1)
            else:
                candidate_map[ident] = (hist, reversed_for_signal, 1)

    if not candidate_map:
        if rejected_post_kickoff:
            return None, False, "history_post_kickoff_only"
        if rejected_stale_close:
            return None, False, "history_close_stale"
        if rejected_missing_kickoff:
            return None, False, "history_kickoff_unverified"
        return None, False, "history_not_found"

    fo_p1_first = _first_word(p1)
    fo_p2_first = _first_word(p2)
    fo_p1_full = _full_name(p1)
    fo_p2_full = _full_name(p2)

    for ident, (hist, reversed_for_signal, score) in list(candidate_map.items()):
        hist_p1 = hist.player2_name if reversed_for_signal else hist.player1_name
        hist_p2 = hist.player1_name if reversed_for_signal else hist.player2_name
        if fo_p1_first and fo_p1_first == _first_word(hist_p1):
            score += 2
        if fo_p2_first and fo_p2_first == _first_word(hist_p2):
            score += 2
        if fo_p1_full and fo_p1_full == _full_name(hist_p1):
            score += 4
        if fo_p2_full and fo_p2_full == _full_name(hist_p2):
            score += 4
        if signal_line is not None:
            hist_line = -hist.spread_line if reversed_for_signal else hist.spread_line
            if hist_line is not None and abs(hist_line - signal_line) <= 0.051:
                score += 12
            elif hist_line is not None:
                score -= 1
        candidate_map[ident] = (hist, reversed_for_signal, score)

    ranked = sorted(candidate_map.values(), key=lambda x: (-x[2], -x[0].captured_ts.timestamp()))
    if len(ranked) > 1 and ranked[0][2] == ranked[1][2] and ranked[0][0].captured_ts == ranked[1][0].captured_ts:
        return None, False, "history_ambiguous"
    hist, reversed_for_signal, _ = ranked[0]
    return hist, reversed_for_signal, "history"


def match_signal_to_close(
    row: dict[str, str],
    index: dict[frozenset[int], list[ClosingMatch]],
) -> tuple[ClosingMatch | None, str]:
    p1 = parse_int(row.get("player1_id"))
    p2 = parse_int(row.get("player2_id"))
    match_dt = parse_iso_date(row.get("match_date"))
    if p1 is None or p2 is None:
        return None, "missing_player_ids"
    if match_dt is None:
        return None, "missing_match_date"
    candidates = index.get(frozenset({p1, p2}), [])
    if not candidates:
        return None, "pair_not_found"

    exact = [m for m in candidates if m.date_ord == match_dt.toordinal()]
    if len(exact) == 1:
        return exact[0], "exact"

    pool = exact if exact else [m for m in candidates if abs(m.date_ord - match_dt.toordinal()) <= 1]
    if not pool:
        return None, "date_not_found"

    series = (row.get("series") or "").strip()
    surface = (row.get("surface") or "").strip()
    if series:
        exact_series = [m for m in pool if m.series == series]
        if len(exact_series) == 1:
            return exact_series[0], "series"
        if exact_series:
            pool = exact_series
    if surface:
        exact_surface = [m for m in pool if m.surface == surface]
        if len(exact_surface) == 1:
            return exact_surface[0], "surface"
        if exact_surface:
            pool = exact_surface
    if len(pool) == 1:
        return pool[0], "date_window"
    return None, "ambiguous"


def summarize_bucket(rows: list[dict[str, Any]], key: str) -> list[str]:
    lines: list[str] = []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "n/a")].append(row)
    for bucket, sample in sorted(groups.items()):
        deltas = [float(r["clv_implied_delta_pct"]) for r in sample]
        pos = sum(1 for x in deltas if x > 0)
        lines.append(
            f"  {bucket:>14} n={len(sample):>3} avg_clv={mean(deltas):+6.3f}% median={median(deltas):+6.3f}% pos={pos}/{len(sample)}"
        )
    return lines


def history_window_for_signal(row: dict[str, str]) -> tuple[datetime, datetime] | None:
    signal_ts = parse_signal_ts(row.get("date"), row.get("time_utc"))
    match_dt = parse_iso_date(row.get("match_date"))
    if signal_ts is None or match_dt is None:
        return None
    earliest_ts = signal_ts - timedelta(seconds=HISTORY_SIGNAL_GRACE_SECONDS)
    cutoff_ts = datetime.combine(match_dt + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return earliest_ts, cutoff_ts


def surname_keys_for_row(row: dict[str, str]) -> str:
    p1 = (row.get("player1") or "").strip()
    p2 = (row.get("player2") or "").strip()
    return ";".join(sorted(_make_pair_keys(p1, p2)))


def nearest_history_candidates(
    row: dict[str, str],
    history_rows: list[HistoryRow],
    signal_line: float | None = None,
    limit: int = 3,
) -> list[str]:
    window = history_window_for_signal(row)
    if window is None:
        return []
    earliest_ts, cutoff_ts = window
    p1 = (row.get("player1") or "").strip()
    p2 = (row.get("player2") or "").strip()
    if not p1 or not p2:
        return []

    signal_keys = set(_make_pair_keys(p1, p2)) | set(_make_pair_keys(p2, p1))
    signal_tokens = set(_tokenise_pinnacle_name(p1)) | set(_tokenise_pinnacle_name(p2))
    scored: list[tuple[int, float, HistoryRow, set[str]]] = []
    for hist in history_rows:
        if _is_doubles_name(hist.player1_name) or _is_doubles_name(hist.player2_name):
            continue
        if hist.captured_ts < earliest_ts or hist.captured_ts >= cutoff_ts:
            continue
        hist_keys = set(_make_pair_keys(hist.player1_name, hist.player2_name)) | set(
            _make_pair_keys(hist.player2_name, hist.player1_name)
        )
        overlap_keys = signal_keys & hist_keys
        hist_tokens = set(_tokenise_pinnacle_name(hist.player1_name)) | set(_tokenise_pinnacle_name(hist.player2_name))
        token_overlap = signal_tokens & hist_tokens
        score = len(overlap_keys) * 10 + len(token_overlap)
        if signal_line is not None and hist.spread_line is not None and abs(abs(hist.spread_line) - abs(signal_line)) <= 0.051:
            score += 4
        if score <= 0:
            continue
        signal_ts = parse_signal_ts(row.get("date"), row.get("time_utc")) or hist.captured_ts
        distance = abs((hist.captured_ts - signal_ts).total_seconds())
        scored.append((score, distance, hist, overlap_keys))

    scored.sort(key=lambda item: (-item[0], item[1], -item[2].captured_ts.timestamp()))
    out: list[str] = []
    for score, _distance, hist, overlap_keys in scored[:limit]:
        keys = ",".join(sorted(overlap_keys)) if overlap_keys else "token-only"
        out.append(
            f"{hist.player1_name} vs {hist.player2_name} | {hist.captured_at} | "
            f"source={hist.source} mode={hist.capture_mode} score={score} keys={keys}"
        )
    return out


def build_unmatched_diagnostic_row(
    row: dict[str, str],
    history_sub_reason: str,
    fallback_reason: str,
    history_rows: list[HistoryRow],
    signal_line: float | None = None,
) -> dict[str, Any]:
    nearest = nearest_history_candidates(row, history_rows, signal_line=signal_line, limit=3)
    return {
        "signal_date": row.get("date") or "",
        "time_utc": row.get("time_utc") or "",
        "match_date": row.get("match_date") or "",
        "bet_type": norm(row.get("bet_type") or "match"),
        "player1": row.get("player1") or "",
        "player2": row.get("player2") or "",
        "player1_id": row.get("player1_id") or "",
        "player2_id": row.get("player2_id") or "",
        "surface": row.get("surface") or "",
        "series": row.get("series") or "",
        "confidence": row.get("confidence") or "",
        "side": row.get("side") or "",
        "spread_line": row.get("spread_line") or "",
        "value_pct": row.get("value_pct") or "",
        "history_sub_reason": history_sub_reason,
        "fallback_reason": fallback_reason,
        "surname_keys_generated": surname_keys_for_row(row),
        "nearest_in_window_capture_1": nearest[0] if len(nearest) > 0 else "",
        "nearest_in_window_capture_2": nearest[1] if len(nearest) > 1 else "",
        "nearest_in_window_capture_3": nearest[2] if len(nearest) > 2 else "",
        "signal_profile": row.get("signal_profile") or "",
        "policy_mode": row.get("policy_mode") or "base",
    }


def write_unmatched_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "signal_date",
        "time_utc",
        "match_date",
        "bet_type",
        "player1",
        "player2",
        "player1_id",
        "player2_id",
        "surface",
        "series",
        "confidence",
        "side",
        "spread_line",
        "value_pct",
        "history_sub_reason",
        "fallback_reason",
        "surname_keys_generated",
        "nearest_in_window_capture_1",
        "nearest_in_window_capture_2",
        "nearest_in_window_capture_3",
        "signal_profile",
        "policy_mode",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def write_detail_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "signal_date",
        "time_utc",
        "match_date",
        "lag_days",
        "lag_bucket",
        "bet_type",
        "player1",
        "player2",
        "player1_id",
        "player2_id",
        "surface",
        "series",
        "confidence",
        "side",
        "spread_line",
        "line_bucket",
        "value_pct",
        "scrape_odds",
        "closing_odds",
        "scrape_implied_pct",
        "closing_implied_pct",
        "clv_implied_delta_pct",
        "odds_move_pct",
        "clv_direction",
        "bet_outcome",
        "won_bet",
        "match_status",
        "match_method",
        "closing_source",
        "history_capture_mode",
        "history_captured_at",
        "history_kickoff_iso",
        "history_close_lag_minutes",
        "history_timing_quality",
        "tournament",
        "location",
        "signal_profile",
        "policy_mode",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def main() -> None:
    args = parse_args()
    signals_path = Path(args.signals) if Path(args.signals).is_absolute() else (ROOT / args.signals)
    xlsx_path = Path(args.xlsx) if Path(args.xlsx).is_absolute() else (ROOT / args.xlsx)
    detail_csv_path = Path(args.detail_csv) if Path(args.detail_csv).is_absolute() else (ROOT / args.detail_csv)
    summary_txt_path = Path(args.summary_txt) if Path(args.summary_txt).is_absolute() else (ROOT / args.summary_txt)
    unmatched_csv_path = Path(args.unmatched_csv) if Path(args.unmatched_csv).is_absolute() else (ROOT / args.unmatched_csv)
    history_dir = Path(args.local_history_dir) if Path(args.local_history_dir).is_absolute() else (ROOT / args.local_history_dir)
    fallback_label = (
        display_path(xlsx_path)
        if args.bet_type == "match" and args.allow_stale_fallback
        else "disabled (captured-history only)" if args.bet_type == "match" else "history-only"
    )
    audited_label = "ML" if args.bet_type == "match" else "spread"
    skipped_label = "spread" if args.bet_type == "match" else "ML"

    if not signals_path.exists():
        summary_text = "\n".join(
            [
                "Strict CLV Audit vs Captured/Closing Pinnacle Odds",
                f"Generated UTC: {date.today().isoformat()}",
                f"Signals file: {display_path(signals_path)}",
                f"Audit bet type: {args.bet_type}",
                f"Fallback closing odds file: {fallback_label}",
                "",
                "Input coverage",
                "  Raw strict rows: 0",
                "  Deduped strict rows: 0",
                "  Settled strict rows: 0",
                f"  Settled {audited_label} rows audited: 0",
                f"  Settled {skipped_label} rows skipped: 0",
                f"  Unique settled {audited_label} match+side keys: 0",
                "  Signal date range: n/a -> n/a",
                "  Settled match-date range: n/a -> n/a",
                "",
                f"No {audited_label} signal file available yet; wrote zero-state audit artifacts.",
            ]
        )
        print(summary_text)
        if not args.dry_run:
            write_detail_csv(detail_csv_path, [])
            write_unmatched_csv(unmatched_csv_path, [])
            summary_txt_path.parent.mkdir(parents=True, exist_ok=True)
            summary_txt_path.write_text(summary_text + "\n", encoding="utf-8")
        return

    raw_rows = load_csv_rows(signals_path)
    if not raw_rows:
        summary_text = "\n".join(
            [
                "Strict CLV Audit vs Captured/Closing Pinnacle Odds",
                f"Generated UTC: {date.today().isoformat()}",
                f"Signals file: {display_path(signals_path)}",
                f"Audit bet type: {args.bet_type}",
                f"Fallback closing odds file: {fallback_label}",
                "",
                "Input coverage",
                "  Raw strict rows: 0",
                "  Deduped strict rows: 0",
                "  Settled strict rows: 0",
                f"  Settled {audited_label} rows audited: 0",
                f"  Settled {skipped_label} rows skipped: 0",
                f"  Unique settled {audited_label} match+side keys: 0",
                "  Signal date range: n/a -> n/a",
                "  Settled match-date range: n/a -> n/a",
                "",
                f"No settled {audited_label} rows to audit yet; wrote zero-state audit artifacts.",
            ]
        )
        print(summary_text)
        if not args.dry_run:
            write_detail_csv(detail_csv_path, [])
            write_unmatched_csv(unmatched_csv_path, [])
            summary_txt_path.parent.mkdir(parents=True, exist_ok=True)
            summary_txt_path.write_text(summary_text + "\n", encoding="utf-8")
        return

    rows = dedupe_rows(raw_rows)
    all_settled = [r for r in rows if is_settled(r)]
    ml_rows = [r for r in all_settled if norm(r.get("bet_type") or "match") != "spread" and norm(r.get("side")) in {"p1", "p2"}]
    spread_rows = [r for r in all_settled if norm(r.get("bet_type")) == "spread" and norm(r.get("side")) in {"p1+", "p2-"}]
    target_rows = ml_rows if args.bet_type == "match" else spread_rows
    skipped_rows = spread_rows if args.bet_type == "match" else ml_rows

    signal_dates = sorted(parse_iso_date(r.get("date")) for r in all_settled if parse_iso_date(r.get("date")))
    match_dates = sorted(parse_iso_date(r.get("match_date")) for r in all_settled if parse_iso_date(r.get("match_date")))

    history_rows: list[HistoryRow] = []
    history_meta: dict[str, Any] = {"enabled": False, "error": "no settled rows"}
    history_lookup: dict[str, list[tuple[HistoryRow, bool]]] = {}
    if signal_dates and match_dates:
        history_rows, history_meta = load_history_rows(history_dir, signal_dates[0], match_dates[-1])
        history_lookup = build_history_lookup(history_rows) if history_rows else {}

    closing_matches: list[ClosingMatch] = []
    meta: dict[str, Any] = {
        "xlsx_matches_loaded": 0,
        "xlsx_skip": {},
        "name_map_report": {},
        "closing_matches_mapped": 0,
        "closing_matches_skipped": {},
    }
    index: dict[frozenset[int], list[ClosingMatch]] = {}
    if args.bet_type == "match" and args.allow_stale_fallback:
        closing_matches, meta = load_closing_matches(xlsx_path)
        index = build_closing_index(closing_matches)

    match_method_counts = Counter()
    unmatched_reasons = Counter()
    source_counts = Counter()
    detailed_rows: list[dict[str, Any]] = []
    unmatched_diagnostics: list[dict[str, Any]] = []

    for row in target_rows:
        p1 = parse_int(row.get("player1_id"))
        p2 = parse_int(row.get("player2_id"))
        if p1 is None or p2 is None:
            unmatched_reasons["missing_player_ids"] += 1
            unmatched_diagnostics.append(
                build_unmatched_diagnostic_row(row, "missing_player_ids", "", history_rows)
            )
            continue
        signal_dt = parse_iso_date(row.get("date"))
        match_dt = parse_iso_date(row.get("match_date"))
        if signal_dt is None or match_dt is None:
            unmatched_reasons["missing_signal_or_match_date"] += 1
            unmatched_diagnostics.append(
                build_unmatched_diagnostic_row(row, "missing_signal_or_match_date", "", history_rows)
            )
            continue

        closing_odds = None
        method = ""
        tournament = ""
        location = ""
        closing_source = ""
        history_capture_mode = ""
        history_captured_at = ""
        history_kickoff_iso = ""
        history_close_lag_minutes: float | None = None
        history_timing_quality = ""
        signal_side = norm(row.get("side"))
        signal_line = parse_float(row.get("spread_line"))

        hist_row, hist_reversed, hist_method = (
            match_signal_to_history(
                row,
                history_lookup,
                signal_line if args.bet_type == "spread" else None,
                require_verified_kickoff=args.require_verified_kickoff,
                max_close_lag_minutes=(
                    max(0, args.max_close_lag_minutes)
                    if args.max_close_lag_minutes is not None
                    else None
                ),
            )
            if history_lookup
            else (None, False, "history_unavailable")
        )
        if args.bet_type == "spread":
            if signal_line is None:
                unmatched_reasons["missing_spread_line"] += 1
                unmatched_diagnostics.append(
                    build_unmatched_diagnostic_row(row, "missing_spread_line", "", history_rows)
                )
                continue
            if hist_row is None:
                unmatched_reasons[hist_method] += 1
                unmatched_diagnostics.append(
                    build_unmatched_diagnostic_row(row, hist_method, "", history_rows, signal_line=signal_line)
                )
                continue
            if (
                hist_row.spread_line is None
                or hist_row.spread_odds1 is None
                or hist_row.spread_odds2 is None
                or hist_row.spread_odds1 <= 1
                or hist_row.spread_odds2 <= 1
            ):
                unmatched_reasons["history_missing_spread"] += 1
                unmatched_diagnostics.append(
                    build_unmatched_diagnostic_row(row, "history_missing_spread", "", history_rows, signal_line=signal_line)
                )
                continue
            method = hist_method
            match_method_counts[method] += 1
            source_counts[hist_row.source] += 1
            closing_source = "bookmaker_odds_history" if hist_row.source == "supabase" else "local_pinnacle_history"
            history_capture_mode = hist_row.capture_mode
            history_captured_at = hist_row.captured_at
            history_kickoff_iso = hist_row.kickoff_iso
            if hist_row.kickoff_ts is not None:
                history_close_lag_minutes = (
                    hist_row.kickoff_ts - hist_row.captured_ts
                ).total_seconds() / 60.0
                history_timing_quality = "verified_prestart"
            else:
                history_timing_quality = "kickoff_unverified"
            close_line = -hist_row.spread_line if hist_reversed else hist_row.spread_line
            close_p1 = hist_row.spread_odds2 if hist_reversed else hist_row.spread_odds1
            close_p2 = hist_row.spread_odds1 if hist_reversed else hist_row.spread_odds2
            if close_line is None or abs(close_line - signal_line) > 0.051:
                unmatched_reasons["spread_line_mismatch"] += 1
                unmatched_diagnostics.append(
                    build_unmatched_diagnostic_row(row, "spread_line_mismatch", "", history_rows, signal_line=signal_line)
                )
                continue
            if signal_side == "p1+":
                closing_odds = close_p1
            elif signal_side == "p2-":
                closing_odds = close_p2
            else:
                unmatched_reasons["bad_spread_side"] += 1
                unmatched_diagnostics.append(
                    build_unmatched_diagnostic_row(row, "bad_spread_side", "", history_rows, signal_line=signal_line)
                )
                continue
            scrape_odds = parse_float(row.get("spread_odds"))
        else:
            if hist_row is not None:
                method = hist_method
                match_method_counts[method] += 1
                source_counts[hist_row.source] += 1
                closing_source = "bookmaker_odds_history" if hist_row.source == "supabase" else "local_pinnacle_history"
                history_capture_mode = hist_row.capture_mode
                history_captured_at = hist_row.captured_at
                history_kickoff_iso = hist_row.kickoff_iso
                if hist_row.kickoff_ts is not None:
                    history_close_lag_minutes = (
                        hist_row.kickoff_ts - hist_row.captured_ts
                    ).total_seconds() / 60.0
                    history_timing_quality = "verified_prestart"
                else:
                    history_timing_quality = "kickoff_unverified"
                close_p1 = hist_row.odds2 if hist_reversed else hist_row.odds1
                close_p2 = hist_row.odds1 if hist_reversed else hist_row.odds2
                closing_odds = close_p1 if signal_side == "p1" else close_p2
            else:
                if not args.allow_stale_fallback:
                    unmatched_reasons[hist_method] += 1
                    unmatched_diagnostics.append(
                        build_unmatched_diagnostic_row(row, hist_method, "stale_fallback_disabled", history_rows)
                    )
                    continue
                matched, method = match_signal_to_close(row, index)
                if matched is None:
                    reason = hist_method if hist_method != "history_unavailable" else method
                    unmatched_reasons[reason] += 1
                    unmatched_diagnostics.append(
                        build_unmatched_diagnostic_row(row, reason, method, history_rows)
                    )
                    continue
                match_method_counts[method] += 1
                source_counts["tennis_data"] += 1
                closing_source = "tennis_data"
                tournament = matched.tournament
                location = matched.location
                if matched.player1_id == p1 and matched.player2_id == p2:
                    close_p1 = matched.close_odds1
                    close_p2 = matched.close_odds2
                elif matched.player1_id == p2 and matched.player2_id == p1:
                    close_p1 = matched.close_odds2
                    close_p2 = matched.close_odds1
                else:
                    unmatched_reasons["orientation_mismatch"] += 1
                    unmatched_diagnostics.append(
                        build_unmatched_diagnostic_row(row, "orientation_mismatch", method, history_rows)
                    )
                    continue
                closing_odds = close_p1 if signal_side == "p1" else close_p2
            scrape_odds = parse_float(row.get("pin_odds1") if signal_side == "p1" else row.get("pin_odds2"))

        if scrape_odds is None or scrape_odds <= 1 or closing_odds <= 1:
            unmatched_reasons["bad_odds"] += 1
            unmatched_diagnostics.append(
                build_unmatched_diagnostic_row(row, "bad_odds", method, history_rows, signal_line=signal_line)
            )
            continue

        scrape_implied = 1.0 / scrape_odds
        closing_implied = 1.0 / closing_odds
        clv_delta = (closing_implied - scrape_implied) * 100.0
        odds_move_pct = (closing_odds / scrape_odds - 1.0) * 100.0
        lag_days = (match_dt - signal_dt).days

        detailed_rows.append(
            {
                "signal_date": signal_dt.isoformat(),
                "time_utc": row.get("time_utc") or "",
                "match_date": match_dt.isoformat(),
                "lag_days": lag_days,
                "lag_bucket": lag_bucket(lag_days),
                "bet_type": args.bet_type,
                "player1": row.get("player1") or "",
                "player2": row.get("player2") or "",
                "player1_id": p1,
                "player2_id": p2,
                "surface": row.get("surface") or "",
                "series": row.get("series") or "",
                "confidence": row.get("confidence") or "",
                "side": row.get("side") or "",
                "spread_line": signal_line,
                "line_bucket": spread_line_bucket(signal_line),
                "value_pct": parse_float(row.get("value_pct")),
                "scrape_odds": scrape_odds,
                "closing_odds": closing_odds,
                "scrape_implied_pct": scrape_implied * 100.0,
                "closing_implied_pct": closing_implied * 100.0,
                "clv_implied_delta_pct": clv_delta,
                "odds_move_pct": odds_move_pct,
                "clv_direction": "positive" if clv_delta > 0 else "negative" if clv_delta < 0 else "flat",
                "bet_outcome": row.get("bet_outcome") or "",
                "won_bet": row.get("won_bet") or "",
                "match_status": "matched",
                "match_method": method,
                "closing_source": closing_source,
                "history_capture_mode": history_capture_mode,
                "history_captured_at": history_captured_at,
                "history_kickoff_iso": history_kickoff_iso,
                "history_close_lag_minutes": history_close_lag_minutes,
                "history_timing_quality": history_timing_quality,
                "tournament": tournament,
                "location": location,
                "signal_profile": row.get("signal_profile") or "",
                "policy_mode": row.get("policy_mode") or "base",
            }
        )

    if args.bet_type == "match":
        unique_match_keys = {
            (row.get("match_date") or "", row.get("player1_id") or "", row.get("player2_id") or "", row.get("side") or "")
            for row in target_rows
        }
    else:
        unique_match_keys = {
            (
                row.get("match_date") or "",
                row.get("player1_id") or "",
                row.get("player2_id") or "",
                row.get("side") or "",
                row.get("spread_line") or "",
            )
            for row in target_rows
        }
    clv_values = [float(r["clv_implied_delta_pct"]) for r in detailed_rows]
    positive_clv = sum(1 for v in clv_values if v > 0)
    match_coverage_rate = len(detailed_rows) / len(target_rows) * 100.0 if target_rows else 0.0
    unmatched_rate = 100.0 - match_coverage_rate if target_rows else 0.0
    closing_dates = sorted(date.fromisoformat(m.date_iso) for m in closing_matches)
    coverage_warning = None
    low_coverage_warning = None
    if target_rows and match_coverage_rate < 70.0:
        low_coverage_warning = (
            f"Only {match_coverage_rate:.2f}% of settled {audited_label} rows have a captured close. "
            "Treat historical CLV as low-coverage until the widened capture era has enough settled rows."
        )
    if args.bet_type == "match" and match_dates and closing_dates and max(closing_dates) < min(match_dates):
        coverage_warning = (
            f"Fallback closing file is stale for this live sample: latest fallback date {max(closing_dates).isoformat()} "
            f"but earliest settled match date is {min(match_dates).isoformat()}."
        )

    history_note_parts = [f"window {history_meta.get('start_date', 'n/a')} -> {history_meta.get('end_date', 'n/a')}"]
    if history_meta.get("supabase_error"):
        history_note_parts.append(f"supabase: {history_meta['supabase_error']}")
    if history_meta.get("local_error"):
        history_note_parts.append(f"local: {history_meta['local_error']}")
    history_note = "; ".join(history_note_parts)
    summary_lines = [
        "Strict CLV Audit vs Captured/Closing Pinnacle Odds",
        f"Generated UTC: {date.today().isoformat()}",
        f"Signals file: {display_path(signals_path)}",
        f"Audit bet type: {args.bet_type}",
        f"Fallback closing odds file: {fallback_label}",
        "",
        "Input coverage",
        f"  Raw strict rows: {len(raw_rows)}",
        f"  Deduped strict rows: {len(rows)}",
        f"  Settled strict rows: {len(all_settled)}",
        f"  Settled {audited_label} rows audited: {len(target_rows)}",
        f"  Settled {skipped_label} rows skipped: {len(skipped_rows)}",
        f"  Unique settled {audited_label} match+side keys: {len(unique_match_keys)}",
        f"  Signal date range: {signal_dates[0].isoformat() if signal_dates else 'n/a'} -> {signal_dates[-1].isoformat() if signal_dates else 'n/a'}",
        f"  Settled match-date range: {match_dates[0].isoformat() if match_dates else 'n/a'} -> {match_dates[-1].isoformat() if match_dates else 'n/a'}",
        "",
        "Captured-history coverage",
        f"  Enabled: {history_meta.get('enabled', False)}",
        f"  History rows loaded: {history_meta.get('rows', 0)}",
        f"  Supabase rows loaded: {history_meta.get('supabase_rows', 0)}",
        f"  Local rows loaded: {history_meta.get('local_rows', 0)}",
        f"  Local files scanned: {history_meta.get('local_files_scanned', 0)}",
        f"  History note: {history_note}",
        "",
        "Closing-file mapping",
        f"  XLSX fallback enabled: {args.bet_type == 'match' and args.allow_stale_fallback}",
        f"  XLSX matches loaded: {meta['xlsx_matches_loaded']}",
        f"  Closing matches mapped to OnCourt IDs: {meta['closing_matches_mapped']}",
        f"  Closing date range: {closing_dates[0].isoformat() if closing_dates else 'n/a'} -> {closing_dates[-1].isoformat() if closing_dates else 'n/a'}",
        f"  XLSX skips: {meta['xlsx_skip']}",
        f"  Name-map report: {meta['name_map_report']}",
        f"  Closing match skips: {meta['closing_matches_skipped']}",
        "",
        "Audit matching",
        f"  Matched {audited_label} rows: {len(detailed_rows)} / {len(target_rows)}",
        f"  Close coverage rate: {match_coverage_rate:.2f}%",
        f"  Unmatched rate: {unmatched_rate:.2f}%",
        f"  Closing sources: {dict(source_counts)}",
        f"  Match methods: {dict(match_method_counts)}",
        f"  Unmatched reasons: {dict(unmatched_reasons)}",
        f"  Unmatched diagnostics rows: {len(unmatched_diagnostics)}",
        f"  Unmatched diagnostics file: {display_path(unmatched_csv_path)}",
    ]
    if coverage_warning or low_coverage_warning:
        summary_lines.extend(["", "Coverage warning"])
        if coverage_warning:
            summary_lines.append(f"  {coverage_warning}")
        if low_coverage_warning:
            summary_lines.append(f"  {low_coverage_warning}")

    if detailed_rows:
        summary_lines.extend(
            [
                "",
                "CLV summary",
                f"  Avg CLV implied delta: {pct(mean(clv_values))}",
                f"  Median CLV implied delta: {pct(median(clv_values))}",
                f"  Positive CLV share: {positive_clv}/{len(clv_values)} ({positive_clv / len(clv_values) * 100:.2f}%)",
                f"  Avg odds move pct: {pct(mean(float(r['odds_move_pct']) for r in detailed_rows))}",
                "",
                "By lag bucket",
                *summarize_bucket(detailed_rows, "lag_bucket"),
                "",
                "By value bucket",
                *summarize_bucket(
                    [{**r, "value_bucket": value_bucket(float(r["value_pct"]))} for r in detailed_rows if r.get("value_pct") is not None],
                    "value_bucket",
                ),
                "",
                "By surface",
                *summarize_bucket(detailed_rows, "surface"),
                "",
                "By side",
                *summarize_bucket(detailed_rows, "side"),
                "",
                "By line bucket",
                *summarize_bucket(detailed_rows, "line_bucket"),
                "",
                "By outcome",
                *summarize_bucket(detailed_rows, "bet_outcome"),
            ]
        )

        best_rows = sorted(detailed_rows, key=lambda r: float(r["clv_implied_delta_pct"]), reverse=True)[:5]
        worst_rows = sorted(detailed_rows, key=lambda r: float(r["clv_implied_delta_pct"]))[:5]
        summary_lines.extend(["", "Best CLV rows"])
        for row in best_rows:
            line_text = f"line={row['spread_line']} " if row.get("spread_line") is not None else ""
            summary_lines.append(
                f"  {row['signal_date']} {row['player1']} vs {row['player2']} {row['side']} "
                f"{line_text}"
                f"scrape={row['scrape_odds']:.3f} close={row['closing_odds']:.3f} clv={pct(float(row['clv_implied_delta_pct']))}"
            )
        summary_lines.extend(["", "Worst CLV rows"])
        for row in worst_rows:
            line_text = f"line={row['spread_line']} " if row.get("spread_line") is not None else ""
            summary_lines.append(
                f"  {row['signal_date']} {row['player1']} vs {row['player2']} {row['side']} "
                f"{line_text}"
                f"scrape={row['scrape_odds']:.3f} close={row['closing_odds']:.3f} clv={pct(float(row['clv_implied_delta_pct']))}"
            )
    else:
        summary_lines.extend(["", f"No matched {audited_label} rows to summarize."])

    summary_text = "\n".join(summary_lines)
    print(summary_text)

    if not args.dry_run:
        write_detail_csv(detail_csv_path, detailed_rows)
        write_unmatched_csv(unmatched_csv_path, unmatched_diagnostics)
        summary_txt_path.parent.mkdir(parents=True, exist_ok=True)
        summary_txt_path.write_text(summary_text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
