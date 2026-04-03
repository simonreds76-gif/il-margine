#!/usr/bin/env python3
"""
Settle strict POLICY signals from data/backtest/strict-signals.csv using OnCourt results in Supabase.

What it does:
- Reads strict-signals.csv
- For each non-settled row:
  - Resolves player1/player2 names -> OnCourt player IDs (heuristic name index)
  - Finds finished match in oncourt_games by (date window + player pair)
  - Writes settlement columns in the CSV row
- Runs idempotently every week: rows already settled are skipped unless --resettle
- Closing odds columns are present but left blank by default (can be filled later)

Usage:
  python scripts/settle-strict-signals.py
  python scripts/settle-strict-signals.py --dry-run
  python scripts/settle-strict-signals.py --resettle
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from signal_storage import STRICT_SIGNAL_PATHS


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = STRICT_SIGNAL_PATHS.archive
LOCAL_PLAYERS_CSV = ROOT / "data" / "oncourt" / "players_atp.csv"
LOCAL_GAMES_CSV = ROOT / "data" / "oncourt" / "games_atp.csv"
LOCAL_TODAY_CSV = ROOT / "data" / "oncourt" / "today_atp.csv"

SETTLEMENT_FIELDS = [
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
    "bet_type",
    "spread_line",
    "spread_odds",
    "game_margin",
]

RETRYABLE_STATUSES = {
    "", "unsettled", "pending", "no_match", "ambiguous", "unmatched_name", "invalid_date", "invalid_side", "error"
}

HTTP_TIMEOUT = 45
PAGE_LIMIT = 1000


def load_env() -> None:
    for name in [".env.local", "env.local"]:
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip().replace("\r", "")
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def parse_date(v: str | None) -> date | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def normalize_name(name: str | None) -> str:
    s = (name or "").strip().lower()
    if not s:
        return ""
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_keys(name: str | None) -> dict[str, str]:
    n = normalize_name(name)
    if not n:
        return {"full": "", "first_last": "", "initial_last": "", "last_only": ""}
    t = n.split()
    full = n
    first_last = f"{t[0]} {t[-1]}" if len(t) >= 2 else n
    initial_last = f"{t[0][0]} {t[-1]}" if t and t[0] else ""
    last_only = t[-1] if t else ""
    return {"full": full, "first_last": first_last, "initial_last": initial_last, "last_only": last_only}


@dataclass
class PlayerIndex:
    by_full: dict[str, set[int]]
    by_first_last: dict[str, set[int]]
    by_initial_last: dict[str, set[int]]
    by_last_only: dict[str, set[int]]


def build_player_index(players: list[dict[str, Any]]) -> PlayerIndex:
    by_full: dict[str, set[int]] = defaultdict(set)
    by_first_last: dict[str, set[int]] = defaultdict(set)
    by_initial_last: dict[str, set[int]] = defaultdict(set)
    by_last_only: dict[str, set[int]] = defaultdict(set)
    for p in players:
        pid = p.get("id")
        name = p.get("name")
        if pid is None:
            continue
        try:
            pid_i = int(pid)
        except (TypeError, ValueError):
            continue
        k = name_keys(str(name or ""))
        if k["full"]:
            by_full[k["full"]].add(pid_i)
        if k["first_last"]:
            by_first_last[k["first_last"]].add(pid_i)
        if k["initial_last"]:
            by_initial_last[k["initial_last"]].add(pid_i)
        if k["last_only"]:
            by_last_only[k["last_only"]].add(pid_i)
    return PlayerIndex(by_full=dict(by_full), by_first_last=dict(by_first_last), by_initial_last=dict(by_initial_last), by_last_only=dict(by_last_only))


def resolve_candidate_ids(name: str, idx: PlayerIndex, max_candidates: int = 20) -> set[int]:
    k = name_keys(name)
    if not k["full"]:
        return set()
    score: Counter[int] = Counter()
    for pid in idx.by_full.get(k["full"], set()):
        score[pid] += 8
    for pid in idx.by_first_last.get(k["first_last"], set()):
        score[pid] += 4
    for pid in idx.by_initial_last.get(k["initial_last"], set()):
        score[pid] += 2
    for pid in idx.by_last_only.get(k["last_only"], set()):
        score[pid] += 1
    if not score:
        return set()
    ranked = sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))
    top_score = ranked[0][1]
    chosen = [pid for pid, sc in ranked if sc >= max(1, top_score - 2)]
    return set(chosen[:max_candidates])


def supabase_base_and_headers() -> tuple[str, dict[str, str]]:
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise RuntimeError("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.local")
    return f"{url}/rest/v1", {"apikey": key, "Authorization": f"Bearer {key}"}


def fetch_all_players(base: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        r = requests.get(f"{base}/oncourt_players", headers=headers, params={"select": "id,name", "limit": PAGE_LIMIT, "offset": offset}, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        rows = r.json() or []
        if not rows:
            break
        out.extend(rows)
        offset += len(rows)
        if len(rows) < PAGE_LIMIT:
            break
    return out


def load_local_players(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def fetch_today_completed(base: str, headers: dict[str, str], cache: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Fetch oncourt_today rows with non-empty result (completed matches). Fallback when oncourt_games lacks recent results."""
    key = "_today_completed"
    if key in cache:
        return cache[key]
    rows_all: list[dict[str, Any]] = []
    offset = 0
    while True:
        r = requests.get(
            f"{base}/oncourt_today",
            headers=headers,
            params={"select": "tour_id,player1_id,player2_id,round_id,result", "limit": PAGE_LIMIT, "offset": offset},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        chunk = r.json() or []
        for row in chunk:
            result = (row.get("result") or "").strip()
            if not result:
                continue
            if result.upper() in ("W/O", "WALKOVER"):
                continue
            if re.match(r"^\d+-\d+", result) is None:
                continue
            try:
                p1, p2 = int(row.get("player1_id") or 0), int(row.get("player2_id") or 0)
            except (TypeError, ValueError):
                continue
            if p1 and p2:
                rows_all.append({"winner_id": p1, "loser_id": p2, "date": date.today(), "result": result})
        offset += len(chunk)
        if len(chunk) < PAGE_LIMIT:
            break
    cache[key] = rows_all
    return rows_all


def parse_score_for_margin(score_str: str | None) -> dict[str, int] | None:
    """Parse score string to games_winner, games_loser, margin. Assumes winner's score first per set."""
    if not score_str or not str(score_str).strip():
        return None
    s = str(score_str).strip().upper()
    if "W/O" in s or "WALKOVER" in s:
        return None
    gw, gl = 0, 0
    for part in s.replace("  ", " ").split():
        part = part.strip().rstrip(")").split("(")[0] if "(" in part else part.strip().rstrip(")")
        if "RET" in part:
            continue
        pieces = part.split("-")
        if len(pieces) == 2:
            try:
                a, b = int(pieces[0]), int(pieces[1])
                gw += a
                gl += b
            except ValueError:
                continue
    if gw + gl == 0:
        return None
    return {"games_winner": gw, "games_loser": gl, "margin": gw - gl}


def fetch_games_window(base: str, headers: dict[str, str], start_d: date, end_d: date, cache: dict[tuple[str, str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    key = (start_d.isoformat(), end_d.isoformat())
    if key in cache:
        return cache[key]
    rows_all: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = [
            ("select", "winner_id,loser_id,date,result"),
            ("date", f"gte.{start_d.isoformat()}"),
            ("date", f"lte.{end_d.isoformat()}"),
            ("order", "date.asc"),
            ("limit", str(PAGE_LIMIT)),
            ("offset", str(offset)),
        ]
        r = requests.get(f"{base}/oncourt_games", headers=headers, params=params, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        chunk = r.json() or []
        if not chunk:
            break
        for g in chunk:
            wd = parse_date(g.get("date"))
            if wd is None:
                continue
            try:
                w, l = int(g.get("winner_id")), int(g.get("loser_id"))
            except (TypeError, ValueError):
                continue
            rows_all.append({"winner_id": w, "loser_id": l, "date": wd, "result": g.get("result")})
        offset += len(chunk)
        if len(chunk) < PAGE_LIMIT:
            break
    cache[key] = rows_all
    return rows_all


def load_local_today_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows_all: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            try:
                p1 = int(row.get("player1_id") or 0)
                p2 = int(row.get("player2_id") or 0)
            except (TypeError, ValueError):
                continue
            if not p1 or not p2:
                continue
            rows_all.append(
                {
                    "player1_id": p1,
                    "player2_id": p2,
                    "round_id": row.get("round_id"),
                    "tour_id": row.get("tour_id"),
                    "result": row.get("result") or "",
                }
            )
    return rows_all


def load_local_games_window(path: Path, start_d: date, end_d: date) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows_all: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            wd = parse_date(row.get("date"))
            if wd is None or wd < start_d or wd > end_d:
                continue
            try:
                w = int(row.get("winner_id") or 0)
                l = int(row.get("loser_id") or 0)
            except (TypeError, ValueError):
                continue
            if not w or not l:
                continue
            rows_all.append({"winner_id": w, "loser_id": l, "date": wd, "result": row.get("result")})
    return rows_all


def choose_match_for_signal(signal_date: date, cand1: set[int], cand2: set[int], games: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None, str]:
    matched = [g for g in games if (g["winner_id"] in cand1 and g["loser_id"] in cand2) or (g["winner_id"] in cand2 and g["loser_id"] in cand1)]
    if not matched:
        return "no_match", None, "No oncourt_games row matched this player pair in date window"
    if len(matched) == 1:
        return "ok", matched[0], ""
    matched.sort(key=lambda g: (abs((g["date"] - signal_date).days), g["date"]))
    best_diff = abs((matched[0]["date"] - signal_date).days)
    best = [g for g in matched if abs((g["date"] - signal_date).days) == best_diff]
    if len(best) == 1:
        return "ok", best[0], f"Picked closest date among {len(matched)} candidates"
    return "ambiguous", None, f"{len(best)} matches tied at closest date (from {len(matched)} candidates)"


def has_today_pair(cand1: set[int], cand2: set[int], rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        p1 = row.get("player1_id")
        p2 = row.get("player2_id")
        if (p1 in cand1 and p2 in cand2) or (p1 in cand2 and p2 in cand1):
            return True
    return False


def ensure_fieldnames(rows: list[dict[str, str]], fieldnames: list[str]) -> list[str]:
    out = list(fieldnames)
    for f in SETTLEMENT_FIELDS:
        if f not in out:
            out.append(f)
    for r in rows:
        for f in out:
            r.setdefault(f, "")
    return out


def backup_csv(path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    b = path.with_name(f"{path.stem}.bak-{ts}{path.suffix}")
    shutil.copy2(path, b)
    return b


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def should_process_row(row: dict[str, str], resettle: bool) -> bool:
    if resettle:
        return True
    status = (row.get("settlement_status") or "").strip().lower()
    if status == "settled":
        return False
    # Retry any other status (no_match, ambiguous, unmatched_name, etc.) or unknown
    return True


def _lane_key_value(row: dict[str, str], field: str) -> str:
    raw = row.get(field)
    if field == "policy_mode":
        return (raw or "base").strip().lower()
    if field == "bet_type":
        return (raw or "match").strip().lower()
    if field == "signal_profile":
        return (raw or "strict").strip().lower()
    if field == "spread_line":
        txt = (raw or "").strip()
        if not txt:
            return ""
        try:
            return f"{float(txt):g}"
        except ValueError:
            return txt.lower()
    return (raw or "").strip().lower()


def dedupe_rows_by_lane(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    lane_fields = ["date", "player1", "player2", "bet_type", "spread_line", "policy_mode", "signal_profile"]
    by_lane: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        lane_key = tuple(_lane_key_value(row, f) for f in lane_fields)
        prev = by_lane.get(lane_key)
        if prev is None:
            by_lane[lane_key] = row
            continue
        prev_settled = (prev.get("settlement_status") or "").strip().lower() == "settled"
        curr_settled = (row.get("settlement_status") or "").strip().lower() == "settled"
        # Prefer settled rows; otherwise keep the latest row seen in file order.
        if prev_settled and not curr_settled:
            continue
        by_lane[lane_key] = row
    deduped = list(by_lane.values())
    return deduped, max(0, len(rows) - len(deduped))


def main() -> int:
    parser = argparse.ArgumentParser(description="Settle strict-policy signals from strict-signals.csv using OnCourt results.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to strict-signals.csv")
    parser.add_argument("--before-days", type=int, default=1, help="Match search window before signal date")
    parser.add_argument("--after-days", type=int, default=4, help="Match search window after signal date")
    parser.add_argument("--dry-run", action="store_true", help="Do not write CSV")
    parser.add_argument("--resettle", action="store_true", help="Reprocess rows even if already settled")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup before write")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    load_env()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"strict-signals file not found: {csv_path}")
        return 0

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames:
            print(f"CSV has no header: {csv_path}")
            return 0
        rows = [dict(r) for r in rd]
        fieldnames = list(rd.fieldnames)

    if not rows:
        print(f"CSV is empty: {csv_path}")
        return 0

    rows, deduped_removed = dedupe_rows_by_lane(rows)

    out_fields = ensure_fieldnames(rows, fieldnames)

    pending_dates: list[date] = []
    for row in rows:
        if not should_process_row(row, args.resettle):
            continue
        signal_date = parse_date(row.get("date"))
        if signal_date is not None:
            pending_dates.append(signal_date)

    local_games_rows: list[dict[str, Any]] = []
    local_today_rows: list[dict[str, Any]] = []
    if pending_dates:
        local_start = min(pending_dates) - timedelta(days=max(0, args.before_days))
        local_end = max(pending_dates) + timedelta(days=max(0, args.after_days))
        local_games_rows = load_local_games_window(LOCAL_GAMES_CSV, local_start, local_end)
        local_today_rows = load_local_today_rows(LOCAL_TODAY_CSV)
        print(f"Loaded local games fallback rows: {len(local_games_rows):,}")
        print(f"Loaded local today schedule rows: {len(local_today_rows):,}")

    print("Loading player index...")
    players = load_local_players(LOCAL_PLAYERS_CSV)
    source = "local players_atp.csv"
    if not players:
        base, headers = supabase_base_and_headers()
        players = fetch_all_players(base, headers)
        source = "Supabase oncourt_players"
    print(f"  loaded players: {len(players):,} ({source})")
    p_index = build_player_index(players)

    games_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
    today_cache: dict[str, list[dict[str, Any]]] = {}
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    stats = Counter()
    changed = deduped_removed

    for i, row in enumerate(rows, start=1):
        stats["rows_total"] += 1
        if not should_process_row(row, args.resettle):
            stats["already_settled_skipped"] += 1
            continue

        signal_date = parse_date(row.get("date"))
        if signal_date is None:
            row["settlement_status"] = "invalid_date"
            row["settlement_note"] = "Invalid or missing date"
            stats["invalid_date"] += 1
            changed += 1
            continue

        p1_name = (row.get("player1") or "").strip()
        p2_name = (row.get("player2") or "").strip()
        cand1 = resolve_candidate_ids(p1_name, p_index)
        cand2 = resolve_candidate_ids(p2_name, p_index)

        if not cand1 or not cand2:
            row["settlement_status"] = "unmatched_name"
            row["settlement_note"] = f"Name mapping failed: p1={len(cand1)} candidates, p2={len(cand2)} candidates"
            stats["unmatched_name"] += 1
            changed += 1
            continue

        start_d = signal_date - timedelta(days=max(0, args.before_days))
        end_d = signal_date + timedelta(days=max(0, args.after_days))
        games = local_games_rows
        if not games:
            if "base" not in locals() or "headers" not in locals():
                base, headers = supabase_base_and_headers()
            games = fetch_games_window(base, headers, start_d, end_d, games_cache)

        status, match, note = choose_match_for_signal(signal_date, cand1, cand2, games)
        if status == "no_match" and has_today_pair(cand1, cand2, local_today_rows):
            row["settlement_status"] = "pending"
            row["settlement_note"] = "Match still present in local today_atp schedule; awaiting completed result"
            stats["pending"] += 1
            changed += 1
            continue
        if status == "no_match" and local_games_rows:
            row["settlement_status"] = "no_match"
            row["settlement_note"] = note
            stats["no_match"] += 1
            changed += 1
            continue
        if status == "no_match":
            if "base" not in locals() or "headers" not in locals():
                base, headers = supabase_base_and_headers()
            today_rows = fetch_today_completed(base, headers, today_cache)
            if today_rows:
                status, match, note = choose_match_for_signal(signal_date, cand1, cand2, today_rows)
                if status == "ok" and match:
                    note = (note or "") + " [from oncourt_today fallback]"
        if status == "no_match":
            row["settlement_status"] = "no_match"
            row["settlement_note"] = note
            stats["no_match"] += 1
            changed += 1
            continue
        if status == "ambiguous" or match is None:
            row["settlement_status"] = "ambiguous"
            row["settlement_note"] = note
            stats["ambiguous"] += 1
            changed += 1
            continue

        winner_id = int(match["winner_id"])
        loser_id = int(match["loser_id"])
        match_date = match["date"]

        if winner_id in cand1 and loser_id in cand2:
            p1_id, p2_id, result_side = winner_id, loser_id, "P1"
        elif winner_id in cand2 and loser_id in cand1:
            p1_id, p2_id, result_side = loser_id, winner_id, "P2"
        else:
            row["settlement_status"] = "ambiguous"
            row["settlement_note"] = "Matched game found but side inference failed"
            stats["ambiguous"] += 1
            changed += 1
            continue

        side = (row.get("side") or "").strip().upper()
        bet_type = (row.get("bet_type") or "match").strip().lower()

        if side in ("P1+", "P2-") or bet_type == "spread":
            spread_line_val = row.get("spread_line")
            try:
                spread_line = float(spread_line_val) if spread_line_val else None
            except (TypeError, ValueError):
                spread_line = None
            if spread_line is None:
                row["settlement_status"] = "invalid_side"
                row["settlement_note"] = "Handicap signal missing spread_line"
                stats["invalid_side"] += 1
                changed += 1
                continue
            parsed = parse_score_for_margin(match.get("result"))
            if parsed is None:
                row["settlement_status"] = "no_score"
                row["settlement_note"] = "Match found but no parseable score for handicap"
                stats["no_score"] += 1
                changed += 1
                continue
            margin_raw = parsed["margin"]
            margin_p1_p2 = margin_raw if result_side == "P1" else -margin_raw
            row["game_margin"] = str(margin_p1_p2)
            p1_covers = margin_p1_p2 > -spread_line
            p2_covers = margin_p1_p2 < -spread_line
            is_push = margin_p1_p2 == -spread_line
            if is_push:
                result_side = "PUSH"
                bet_outcome = "VOID"
                won_bet = ""
            else:
                result_side = "P1+" if p1_covers else "P2-"
                bet_outcome = "WIN" if (side == "P1+" and p1_covers) or (side == "P2-" and p2_covers) else "LOSS"
                won_bet = "1" if bet_outcome == "WIN" else "0"
        elif side in ("P1", "P2"):
            bet_outcome = "WIN" if side == result_side else "LOSS"
            won_bet = "1" if bet_outcome == "WIN" else "0"
        else:
            bet_outcome, won_bet = "N/A", ""

        row["player1_id"] = str(p1_id)
        row["player2_id"] = str(p2_id)
        row["winner_id"] = str(winner_id)
        row["loser_id"] = str(loser_id)
        row["match_date"] = match_date.isoformat()
        row["result"] = result_side
        row["bet_outcome"] = bet_outcome
        row["won_bet"] = won_bet
        row["settlement_status"] = "settled"
        row["settled_at"] = now_iso
        row["settlement_note"] = note or ""
        row.setdefault("closing_odds1", "")
        row.setdefault("closing_odds2", "")
        row.setdefault("closing_source", "")

        stats["settled_now"] += 1
        changed += 1
        if args.verbose and i % 50 == 0:
            print(f"  processed {i:,}/{len(rows):,}")

    # Backlog and ROI by bet type (ML vs handicap)
    ml_rows = [r for r in rows if (r.get("bet_type") or "match").strip().lower() != "spread" and (r.get("side") or "").strip().upper() not in ("P1+", "P2-")]
    hc_rows = [r for r in rows if (r.get("bet_type") or "").strip().lower() == "spread" or (r.get("side") or "").strip().upper() in ("P1+", "P2-")]
    ml_settled = [r for r in ml_rows if (r.get("settlement_status") or "").strip().lower() == "settled"]
    hc_settled = [r for r in hc_rows if (r.get("settlement_status") or "").strip().lower() == "settled"]
    ml_backlog = len(ml_rows) - len(ml_settled)
    hc_backlog = len(hc_rows) - len(hc_settled)

    def _roi(settled_list: list) -> tuple[float, float]:
        pnl, n = 0.0, 0
        for r in settled_list:
            outcome = (r.get("bet_outcome") or "").strip().upper()
            if outcome not in ("WIN", "LOSS"):
                continue
            side = (r.get("side") or "").strip().upper()
            if side in ("P1", "P2"):
                odds = float(r.get("pin_odds1") or 0) if side == "P1" else float(r.get("pin_odds2") or 0)
            else:
                odds = float(r.get("spread_odds") or 0)
            if odds <= 1:
                continue
            n += 1
            pnl += (odds - 1.0) if outcome == "WIN" else -1.0
        roi = 100.0 * pnl / n if n else 0.0
        return roi, pnl

    ml_roi, ml_pnl = _roi(ml_settled)
    hc_roi, hc_pnl = _roi(hc_settled)

    print("\nSettlement summary")
    print(f"  Rows total: {stats['rows_total']:,}")
    if deduped_removed:
        print(f"  Duplicate same-lane rows removed before settlement: {deduped_removed:,}")
    print(f"  Already settled skipped: {stats['already_settled_skipped']:,}")
    print(f"  Settled now: {stats['settled_now']:,}")
    print(f"  Pending today schedule: {stats['pending']:,}")
    print(f"  No match (will retry next run): {stats['no_match']:,}")
    print(f"  Ambiguous: {stats['ambiguous']:,}")
    print(f"  Unmatched name: {stats['unmatched_name']:,}")
    print(f"  Invalid date: {stats['invalid_date']:,}")
    if stats.get("invalid_side", 0) or stats.get("no_score", 0):
        print(f"  Invalid side (handicap): {stats.get('invalid_side', 0):,}")
        print(f"  No score (handicap): {stats.get('no_score', 0):,}")
    print("\nBy bet type (ML vs Handicap)")
    print(f"  ML:        settled={len(ml_settled):,} backlog={ml_backlog:,}  ROI={ml_roi:+.2f}%  P/L={ml_pnl:+.2f}u")
    print(f"  Handicap:  settled={len(hc_settled):,} backlog={hc_backlog:,}  ROI={hc_roi:+.2f}%  P/L={hc_pnl:+.2f}u")

    if args.dry_run:
        print("\nDry run: CSV not written.")
        return 0
    if changed == 0:
        print("\nNo row changes detected. CSV unchanged.")
        return 0
    if not args.no_backup:
        b = backup_csv(csv_path)
        print(f"\nBackup created: {b}")
    write_csv(csv_path, rows, out_fields)
    print(f"CSV updated: {csv_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        raise SystemExit(1)
