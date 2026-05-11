#!/usr/bin/env python3
"""
Fit handicap calibration parameters from settled historical results.

Primary mode (recommended):
  - Join backtest rows to real Pinnacle spread lines from Supabase
    `bookmaker_odds_snapshot` (date + player names).
  - Fit:
      1) line shift: p_raw = P(P1 covers +line_shifted)
      2) Platt: p_cal = sigmoid(a + b * logit(p_raw))

Fallback mode:
  - Use synthetic fixed line grid from backtest rows only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import requests

from handicap_probs import prob_p1_covers_plus

try:
    from src.lib.tennis_prob import prob_match_best_of_3
except ImportError:
    from functools import lru_cache

    def prob_game(p: float) -> float:
        if p <= 0 or p >= 1:
            return max(0.0, min(1.0, p))
        d = (p * p) / (1.0 - 2.0 * p * (1.0 - p))
        return p**4 + 4 * p**4 * (1 - p) + 10 * p**4 * (1 - p) ** 2 + 20 * p**3 * (1 - p) ** 3 * d

    @lru_cache(maxsize=4096)
    def _ps(a: int, b: int, pai: int, pbi: int, a_serve: bool) -> float:
        pa, pb = pai / 10000.0, pbi / 10000.0
        if a >= 6 and a - b >= 2:
            return 1.0
        if b >= 6 and b - a >= 2:
            return 0.0
        if a == 6 and b == 6:
            q = 1.0 - pb
            return pa / (pa + q) if (pa + q) > 0 else 0.5
        p_win = prob_game(pa) if a_serve else (1.0 - prob_game(pb))
        return p_win * _ps(a + 1, b, pai, pbi, not a_serve) + (1.0 - p_win) * _ps(a, b + 1, pai, pbi, not a_serve)

    def _set_win_prob(pa: float, pb: float, a_serves_first: bool = True) -> float:
        pai = int(round(max(0.01, min(0.99, pa)) * 10000))
        pbi = int(round(max(0.01, min(0.99, pb)) * 10000))
        return _ps(0, 0, pai, pbi, a_serves_first)

    def prob_match_best_of_3(pa: float, pb: float) -> float:
        s1 = _set_win_prob(pa, pb, True)
        s2 = _set_win_prob(pa, pb, False)
        return s1 * s2 + s1 * (1.0 - s2) * s1 + (1.0 - s1) * s2 * s1


SURFACE_AVG_SPW = {"hard": 0.64, "clay": 0.62, "grass": 0.66, "i.hard": 0.65}
POINT_CLAMP_LO = 0.42
POINT_CLAMP_HI = 0.80
DEFAULT_OUT = "data/backtest/spread-v1-calibration-params.json"
SURFACE_FILTERS = {"all": None, "clay": "clay", "hard": "hard", "grass": "grass"}


@dataclass
class MatchRow:
    year: int
    date_iso: str
    surface: str
    player1: str
    player2: str
    margin_p1: float
    pa: float
    pb: float


@dataclass
class SnapshotSpread:
    capture_date: str
    captured_at: str
    captured_ts: float
    league: str
    player1_name: str
    player2_name: str
    n1: str
    n2: str
    s1: str
    s2: str
    line: float
    odds1: float
    odds2: float


@dataclass
class Sample:
    year: int
    surface: str
    pa: float
    pb: float
    line: float
    y: float


def _root_dir() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(base)


def load_env() -> None:
    root = _root_dir()
    for name in ["env.local", ".env.local"]:
        path = os.path.join(root, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip().replace("\r", "")
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sigmoid(z: np.ndarray | float) -> np.ndarray | float:
    if isinstance(z, np.ndarray):
        out = np.empty_like(z, dtype=float)
        pos = z >= 0
        neg = ~pos
        out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
        ez = np.exp(z[neg])
        out[neg] = ez / (1.0 + ez)
        return out
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _logit(p: np.ndarray | float) -> np.ndarray | float:
    if isinstance(p, np.ndarray):
        q = np.clip(p, 1e-6, 1.0 - 1e-6)
        return np.log(q / (1.0 - q))
    q = _clamp(float(p), 1e-6, 1.0 - 1e-6)
    return math.log(q / (1.0 - q))


def _parse_float(v: object) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _normalize_surface(v: object) -> str:
    s = str(v or "").strip().lower()
    if not s:
        return "hard"
    if s in {"i.hard", "ihard", "indoor hard", "indoor_hard"}:
        return "i.hard"
    if s.startswith("hard"):
        return "hard"
    if s.startswith("clay"):
        return "clay"
    if s.startswith("grass"):
        return "grass"
    return "hard"


def _surface_filter_label(value: str) -> Optional[str]:
    return SURFACE_FILTERS.get(value)


def _surface_scope(value: str) -> List[str]:
    surface = _surface_filter_label(value)
    return [surface.title()] if surface else ["Hard", "Clay"]


def _normalize_name(v: object) -> str:
    s = str(v or "").strip().lower()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _surname_key(name: str) -> str:
    parts = name.split()
    return parts[-1] if parts else ""


def _parse_date_iso(v: object) -> Optional[str]:
    s = str(v or "").strip()
    if not s:
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        base = s[:10]
        try:
            datetime.strptime(base, "%Y-%m-%d")
            return base
        except ValueError:
            return None
    for fmt in ("%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _iso_date_shift(iso_date: str, delta_days: int) -> str:
    d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return (d + timedelta(days=delta_days)).isoformat()


def _parse_timestamp(v: object) -> float:
    s = str(v or "").strip()
    if not s:
        return 0.0
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _league_norm(v: object) -> str:
    return str(v or "").strip().lower()


def _league_priority(league: str) -> int:
    lg = _league_norm(league)
    if lg == "atp":
        return 0
    if lg in {"atp qualifying", "atp quals", "atp qualies"}:
        return 1
    if lg == "atp challenger":
        return 2
    return 9


def _capture_date_from_filename(path: str) -> Optional[str]:
    name = os.path.basename(path)
    m = re.search(r"pinnacle-odds-(\d{4}-\d{2}-\d{2})\.csv$", name)
    if m:
        return m.group(1)
    m = re.search(r"pinnacle-history-(\d{8})-(\d{6})\.csv$", name)
    if m:
        date_part = m.group(1)
        return f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
    return None


def _captured_at_from_filename(path: str, capture_date: Optional[str]) -> str:
    name = os.path.basename(path)
    m = re.search(r"pinnacle-history-(\d{8})-(\d{6})\.csv$", name)
    if m:
        date_part = m.group(1)
        time_part = m.group(2)
        return (
            f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}T"
            f"{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}Z"
        )
    if capture_date:
        return f"{capture_date}T23:59:59Z"
    return ""


def _pick_col(fieldnames: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    keys = set(fieldnames)
    for c in candidates:
        if c in keys:
            return c
    return None


def _solve_spw_for_match_prob(p1_win: float, avg_spw: float) -> Tuple[float, float]:
    p1_win = _clamp(p1_win, 0.02, 0.98)
    avg_spw = _clamp(avg_spw, POINT_CLAMP_LO + 0.01, POINT_CLAMP_HI - 0.01)
    max_delta = min(avg_spw - POINT_CLAMP_LO, POINT_CLAMP_HI - avg_spw)
    lo, hi = -max_delta, max_delta
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        pa = _clamp(avg_spw + mid, POINT_CLAMP_LO, POINT_CLAMP_HI)
        pb = _clamp(avg_spw - mid, POINT_CLAMP_LO, POINT_CLAMP_HI)
        p = prob_match_best_of_3(pa, pb)
        if abs(p - p1_win) < 5e-4:
            return pa, pb
        if p < p1_win:
            lo = mid
        else:
            hi = mid
    mid = 0.5 * (lo + hi)
    return (
        _clamp(avg_spw + mid, POINT_CLAMP_LO, POINT_CLAMP_HI),
        _clamp(avg_spw - mid, POINT_CLAMP_LO, POINT_CLAMP_HI),
    )


def parse_score_games(score_str: str) -> Optional[Tuple[int, int]]:
    if not score_str:
        return None
    s = str(score_str).strip().upper()
    if not s:
        return None
    if "W/O" in s or "WALKOVER" in s or "DEF" in s or "RET" in s:
        return None
    games_winner = 0
    games_loser = 0
    for token in s.replace("  ", " ").split():
        token = token.strip()
        if "(" in token:
            token = token[: token.index("(")]
        parts = token.split("-")
        if len(parts) != 2:
            continue
        try:
            a = int(parts[0])
            b = int(parts[1])
        except ValueError:
            continue
        games_winner += a
        games_loser += b
    if games_winner + games_loser == 0:
        return None
    return games_winner, games_loser


def load_match_rows(files: Sequence[str]) -> Tuple[List[MatchRow], Dict[str, int]]:
    rows: List[MatchRow] = []
    skipped = {
        "file_missing": 0,
        "no_prob": 0,
        "no_score": 0,
        "no_winner": 0,
        "bad_date": 0,
        "bad_margin": 0,
        "no_names": 0,
    }
    for path in files:
        if not os.path.exists(path):
            skipped["file_missing"] += 1
            continue
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames or []
            if not cols:
                continue

            c_prob = _pick_col(cols, ["our_prob", "p1_win_prob", "model_p1", "prob_p1"])
            c_surface = _pick_col(cols, ["surface"])
            c_date = _pick_col(cols, ["date"])
            c_score = _pick_col(cols, ["score", "result", "match_score"])
            c_actual_winner = _pick_col(cols, ["actual_winner"])
            c_player1 = _pick_col(cols, ["player1"])
            c_player2 = _pick_col(cols, ["player2"])
            c_pa = _pick_col(cols, ["p_a", "p_serve_a", "model_p_a"])
            c_pb = _pick_col(cols, ["p_b", "p_serve_b", "model_p_b"])

            for row in reader:
                date_iso = _parse_date_iso(row.get(c_date) if c_date else None)
                if not date_iso:
                    skipped["bad_date"] += 1
                    continue
                year = int(date_iso[:4])

                p1_name = str(row.get(c_player1, "")).strip() if c_player1 else ""
                p2_name = str(row.get(c_player2, "")).strip() if c_player2 else ""
                if not p1_name or not p2_name:
                    skipped["no_names"] += 1
                    continue

                parsed = parse_score_games(str(row.get(c_score, "")).strip() if c_score else "")
                if parsed is None:
                    skipped["no_score"] += 1
                    continue
                games_w, games_l = parsed
                winner = str(row.get(c_actual_winner, "")).strip() if c_actual_winner else ""
                if not winner:
                    skipped["no_winner"] += 1
                    continue
                margin_winner = games_w - games_l
                if margin_winner <= 0:
                    skipped["bad_margin"] += 1
                    continue
                margin_p1 = margin_winner if winner == p1_name else -margin_winner

                pa = _parse_float(row.get(c_pa)) if c_pa else None
                pb = _parse_float(row.get(c_pb)) if c_pb else None
                if pa is None or pb is None:
                    p1_prob = _parse_float(row.get(c_prob)) if c_prob else None
                    if p1_prob is None:
                        skipped["no_prob"] += 1
                        continue
                    surface = _normalize_surface(row.get(c_surface))
                    avg_spw = SURFACE_AVG_SPW.get(surface, 0.64)
                    pa, pb = _solve_spw_for_match_prob(p1_prob, avg_spw)

                rows.append(
                    MatchRow(
                        year=year,
                        date_iso=date_iso,
                        surface=_normalize_surface(row.get(c_surface)),
                        player1=p1_name,
                        player2=p2_name,
                        margin_p1=float(margin_p1),
                        pa=float(pa),
                        pb=float(pb),
                    )
                )
    return rows, skipped


def load_snapshot_spreads_local(
    start_date: str,
    end_date: str,
    leagues: set[str],
) -> List[SnapshotSpread]:
    files = sorted(
        [
            *[str(p) for p in (Path(_root_dir()) / "data" / "pinnacle-history").glob("*.csv")],
            *[str(p) for p in (Path(_root_dir()) / "data").glob("pinnacle-odds-*.csv")],
        ]
    )
    out: List[SnapshotSpread] = []
    for path in files:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                capture_date = _parse_date_iso(row.get("capture_date")) or _capture_date_from_filename(path)
                if not capture_date or capture_date < start_date or capture_date > end_date:
                    continue
                league = str(row.get("league") or "").strip()
                if leagues and _league_norm(league) not in leagues:
                    continue
                line = _parse_float(row.get("spread_line"))
                odds1 = _parse_float(row.get("spread_odds1"))
                odds2 = _parse_float(row.get("spread_odds2"))
                if line is None or odds1 is None or odds2 is None:
                    continue
                line = abs(float(line))
                if line <= 0 or odds1 <= 1.0 or odds2 <= 1.0:
                    continue
                p1 = str(row.get("player1_name") or "").strip()
                p2 = str(row.get("player2_name") or "").strip()
                if not p1 or not p2:
                    continue
                n1 = _normalize_name(p1)
                n2 = _normalize_name(p2)
                if not n1 or not n2:
                    continue
                captured_at = str(row.get("captured_at") or "").strip() or _captured_at_from_filename(path, capture_date)
                out.append(
                    SnapshotSpread(
                        capture_date=capture_date,
                        captured_at=captured_at,
                        captured_ts=_parse_timestamp(captured_at),
                        league=league,
                        player1_name=p1,
                        player2_name=p2,
                        n1=n1,
                        n2=n2,
                        s1=_surname_key(n1),
                        s2=_surname_key(n2),
                            line=line,
                        odds1=float(odds1),
                        odds2=float(odds2),
                    )
                )
    return out


def fetch_snapshot_spreads(
    start_date: str,
    end_date: str,
    leagues: set[str],
    bookmaker: str,
    page_size: int = 1000,
) -> List[SnapshotSpread]:
    local_rows = load_snapshot_spreads_local(start_date, end_date, leagues)
    if local_rows:
        return local_rows

    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        local_rows = load_snapshot_spreads_local(start_date, end_date, leagues)
        if local_rows:
            return local_rows
        raise RuntimeError("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in env/.env.local")

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    endpoint = f"{url}/rest/v1/bookmaker_odds_snapshot"
    select_cols = "capture_date,captured_at,league,player1_name,player2_name,spread_line,spread_odds1,spread_odds2"

    offset = 0
    raw_rows: List[dict] = []
    try:
        while True:
            params = [
                ("select", select_cols),
                ("bookmaker", f"eq.{bookmaker}"),
                ("spread_line", "not.is.null"),
                ("capture_date", f"gte.{start_date}"),
                ("capture_date", f"lte.{end_date}"),
                ("order", "capture_date.asc,captured_at.desc"),
                ("offset", str(offset)),
                ("limit", str(page_size)),
            ]
            resp = requests.get(endpoint, headers=headers, params=params, timeout=60)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            raw_rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
    except Exception:
        local_rows = load_snapshot_spreads_local(start_date, end_date, leagues)
        if local_rows:
            return local_rows
        raise

    out: List[SnapshotSpread] = []
    for row in raw_rows:
        league = str(row.get("league") or "").strip()
        if leagues and _league_norm(league) not in leagues:
            continue
        line = _parse_float(row.get("spread_line"))
        odds1 = _parse_float(row.get("spread_odds1"))
        odds2 = _parse_float(row.get("spread_odds2"))
        if line is None or odds1 is None or odds2 is None:
            continue
        line = abs(float(line))
        if line <= 0 or odds1 <= 1.0 or odds2 <= 1.0:
            continue
        capture_date = _parse_date_iso(row.get("capture_date"))
        if not capture_date:
            continue
        p1 = str(row.get("player1_name") or "").strip()
        p2 = str(row.get("player2_name") or "").strip()
        if not p1 or not p2:
            continue
        n1 = _normalize_name(p1)
        n2 = _normalize_name(p2)
        if not n1 or not n2:
            continue
        out.append(
            SnapshotSpread(
                capture_date=capture_date,
                captured_at=str(row.get("captured_at") or ""),
                captured_ts=_parse_timestamp(row.get("captured_at")),
                league=league,
                player1_name=p1,
                player2_name=p2,
                n1=n1,
                n2=n2,
                s1=_surname_key(n1),
                s2=_surname_key(n2),
                line=line,
                odds1=float(odds1),
                odds2=float(odds2),
            )
        )
    return out


def _choose_best_snapshot(cands: List[SnapshotSpread]) -> SnapshotSpread:
    return sorted(cands, key=lambda c: (_league_priority(c.league), -c.captured_ts))[0]


def build_snapshot_indices(
    rows: Sequence[SnapshotSpread],
) -> Tuple[Dict[Tuple[str, str, str], List[SnapshotSpread]], Dict[Tuple[str, str, str], List[SnapshotSpread]]]:
    exact: Dict[Tuple[str, str, str], List[SnapshotSpread]] = {}
    surn: Dict[Tuple[str, str, str], List[SnapshotSpread]] = {}
    for r in rows:
        exact.setdefault((r.capture_date, r.n1, r.n2), []).append(r)
        surn.setdefault((r.capture_date, r.s1, r.s2), []).append(r)
    return exact, surn


def _dedupe_snapshot_candidates(cands: List[SnapshotSpread]) -> List[SnapshotSpread]:
    uniq: Dict[Tuple[str, str, str, float], SnapshotSpread] = {}
    for c in cands:
        key = (c.capture_date, c.n1, c.n2, c.line)
        prev = uniq.get(key)
        if prev is None or c.captured_ts > prev.captured_ts:
            uniq[key] = c
    return list(uniq.values())


def find_snapshot_for_match(
    m: MatchRow,
    exact_idx: Dict[Tuple[str, str, str], List[SnapshotSpread]],
    surname_idx: Dict[Tuple[str, str, str], List[SnapshotSpread]],
    date_window_days: int,
) -> Tuple[Optional[SnapshotSpread], Optional[str]]:
    n1 = _normalize_name(m.player1)
    n2 = _normalize_name(m.player2)
    s1 = _surname_key(n1)
    s2 = _surname_key(n2)
    date_candidates = [_iso_date_shift(m.date_iso, d) for d in range(-date_window_days, date_window_days + 1)]

    for d in date_candidates:
        fwd = exact_idx.get((d, n1, n2), [])
        rev = exact_idx.get((d, n2, n1), [])
        cands = _dedupe_snapshot_candidates([*fwd, *rev])
        if not cands:
            continue
        if len(cands) == 1:
            method = "exact_same_day" if d == m.date_iso else "exact_date_window"
            return cands[0], method
        return _choose_best_snapshot(cands), ("exact_multi_same_day" if d == m.date_iso else "exact_multi_window")

    for d in date_candidates:
        fwd = surname_idx.get((d, s1, s2), [])
        rev = surname_idx.get((d, s2, s1), [])
        cands = _dedupe_snapshot_candidates([*fwd, *rev])
        if not cands:
            continue
        if len(cands) == 1:
            method = "surname_same_day" if d == m.date_iso else "surname_date_window"
            return cands[0], method
        return None, "ambiguous_surname"

    return None, None


def build_samples_from_snapshot(
    matches: Sequence[MatchRow],
    snapshot_rows: Sequence[SnapshotSpread],
    date_window_days: int,
) -> Tuple[List[Sample], Dict[str, int]]:
    samples: List[Sample] = []
    stats = {
        "snapshot_rows": len(snapshot_rows),
        "match_rows": len(matches),
        "matched": 0,
        "unmatched": 0,
        "ambiguous": 0,
    }
    method_counts: Dict[str, int] = {}

    exact_idx, surname_idx = build_snapshot_indices(snapshot_rows)
    for m in matches:
        snap, method = find_snapshot_for_match(m, exact_idx, surname_idx, date_window_days)
        if snap is None:
            stats["unmatched"] += 1
            if method and method.startswith("ambiguous"):
                stats["ambiguous"] += 1
            continue

        method_counts[method or "unknown"] = method_counts.get(method or "unknown", 0) + 1
        stats["matched"] += 1
        line = snap.line

        # Main orientation
        y = 1.0 if m.margin_p1 > -line else 0.0
        samples.append(Sample(year=m.year, surface=m.surface, pa=m.pa, pb=m.pb, line=line, y=y))

        # Mirrored orientation to prevent player1-label bias.
        y_mirror = 1.0 if m.margin_p1 < line else 0.0
        samples.append(Sample(year=m.year, surface=m.surface, pa=m.pb, pb=m.pa, line=line, y=y_mirror))

    for k, v in method_counts.items():
        stats[f"method_{k}"] = v
    return samples, stats


def build_samples_synthetic(matches: Sequence[MatchRow], lines: Sequence[float]) -> Tuple[List[Sample], Dict[str, int]]:
    samples: List[Sample] = []
    for m in matches:
        for line in lines:
            y = 1.0 if m.margin_p1 > -line else 0.0
            samples.append(Sample(year=m.year, surface=m.surface, pa=m.pa, pb=m.pb, line=line, y=y))
            y_mirror = 1.0 if m.margin_p1 < line else 0.0
            samples.append(Sample(year=m.year, surface=m.surface, pa=m.pb, pb=m.pa, line=line, y=y_mirror))
    return samples, {"synthetic_lines": len(lines), "match_rows": len(matches)}


def fit_platt(logits: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    x = np.column_stack([np.ones_like(logits), logits])
    w = np.array([0.0, 1.0], dtype=float)
    ridge = 1e-6
    eye = np.eye(2, dtype=float)
    for _ in range(80):
        z = x @ w
        p = np.clip(_sigmoid(z), 1e-6, 1.0 - 1e-6)
        w_diag = p * (1.0 - p)
        grad = x.T @ (p - y) + ridge * w
        hess = (x.T * w_diag) @ x + ridge * eye
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
        w_next = w - step
        if float(np.linalg.norm(step)) < 1e-7:
            w = w_next
            break
        w = w_next
    return float(w[0]), float(w[1])


def metrics(y: np.ndarray, p: np.ndarray) -> Dict[str, float]:
    q = np.clip(p, 1e-6, 1.0 - 1e-6)
    ll = -np.mean(y * np.log(q) + (1.0 - y) * np.log(1.0 - q))
    br = np.mean((q - y) ** 2)
    hit = float(np.mean(y))
    pred = float(np.mean(q))
    return {
        "n": int(len(y)),
        "hit_rate": hit,
        "mean_pred": pred,
        "bias": pred - hit,
        "brier": float(br),
        "log_loss": float(ll),
    }


def fit_calibration(samples: Sequence[Sample], shift_min: float, shift_max: float, shift_step: float) -> Dict[str, object]:
    years = np.array([s.year for s in samples], dtype=int)
    y = np.array([s.y for s in samples], dtype=float)
    unique_years = sorted(set(int(v) for v in years.tolist()))
    holdout_year = unique_years[-1] if len(unique_years) >= 2 else None

    if holdout_year is not None:
        train_mask = years < holdout_year
        test_mask = years == holdout_year
        if int(np.sum(train_mask)) < 500:
            train_mask = np.ones_like(years, dtype=bool)
            test_mask = np.zeros_like(years, dtype=bool)
            holdout_year = None
    else:
        train_mask = np.ones_like(years, dtype=bool)
        test_mask = np.zeros_like(years, dtype=bool)

    best: Optional[Dict[str, object]] = None
    shift_grid = np.arange(shift_min, shift_max + 0.5 * shift_step, shift_step)
    for shift in shift_grid:
        p_raw = np.array([prob_p1_covers_plus(s.pa, s.pb, s.line + float(shift)) for s in samples], dtype=float)
        logits = _logit(p_raw)
        a, b = fit_platt(logits[train_mask], y[train_mask])
        p_cal = _sigmoid(a + b * logits)

        m_train_raw = metrics(y[train_mask], p_raw[train_mask])
        m_train_cal = metrics(y[train_mask], p_cal[train_mask])
        if np.any(test_mask):
            m_test_raw = metrics(y[test_mask], p_raw[test_mask])
            m_test_cal = metrics(y[test_mask], p_cal[test_mask])
            objective = m_test_cal["log_loss"] + 0.35 * abs(m_test_cal["bias"])
        else:
            m_test_raw = None
            m_test_cal = None
            objective = m_train_cal["log_loss"] + 0.35 * abs(m_train_cal["bias"])

        candidate = {
            "line_shift": float(round(float(shift), 4)),
            "platt_a": float(round(a, 6)),
            "platt_b": float(round(b, 6)),
            "objective": float(objective),
            "train_raw": m_train_raw,
            "train_cal": m_train_cal,
            "test_raw": m_test_raw,
            "test_cal": m_test_cal,
        }
        if best is None or float(candidate["objective"]) < float(best["objective"]):
            best = candidate

    assert best is not None

    eval_mask = test_mask if np.any(test_mask) else np.ones_like(years, dtype=bool)
    eval_samples = [samples[i] for i in np.where(eval_mask)[0]]
    p_raw_eval = np.array(
        [prob_p1_covers_plus(s.pa, s.pb, s.line + float(best["line_shift"])) for s in eval_samples],
        dtype=float,
    )
    p_cal_eval = _sigmoid(float(best["platt_a"]) + float(best["platt_b"]) * _logit(p_raw_eval))
    y_eval = np.array([s.y for s in eval_samples], dtype=float)

    surface_rows: Dict[str, Dict[str, float]] = {}
    for surf in sorted(set(s.surface for s in eval_samples)):
        idx = np.array([i for i, s in enumerate(eval_samples) if s.surface == surf], dtype=int)
        if len(idx) == 0:
            continue
        surface_rows[surf] = {
            "n": int(len(idx)),
            "raw_bias": float(metrics(y_eval[idx], p_raw_eval[idx])["bias"]),
            "cal_bias": float(metrics(y_eval[idx], p_cal_eval[idx])["bias"]),
            "raw_log_loss": float(metrics(y_eval[idx], p_raw_eval[idx])["log_loss"]),
            "cal_log_loss": float(metrics(y_eval[idx], p_cal_eval[idx])["log_loss"]),
        }

    return {
        "best": best,
        "years": unique_years,
        "holdout_year": holdout_year,
        "surface_eval": surface_rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Fit handicap calibration params (line shift + Platt).")
    ap.add_argument(
        "--files",
        nargs="+",
        default=[
            "data/backtest/backtest-results-2022.csv",
            "data/backtest/backtest-results-2023.csv",
            "data/backtest/backtest-results-2024.csv",
            "data/backtest/backtest-results-2025.csv",
            "data/backtest/backtest-results-2026.csv",
        ],
    )
    ap.add_argument("--line-source", choices=["snapshot", "synthetic", "auto"], default="snapshot")
    ap.add_argument("--lines", default="-5.5,-4.5,-3.5,-2.5,-1.5,-0.5,0.5,1.5,2.5,3.5,4.5,5.5")
    ap.add_argument("--shift-min", type=float, default=-2.0)
    ap.add_argument("--shift-max", type=float, default=2.0)
    ap.add_argument("--shift-step", type=float, default=0.1)
    ap.add_argument("--snapshot-date-window", type=int, default=1)
    ap.add_argument("--snapshot-bookmaker", default="Pinnacle")
    ap.add_argument("--snapshot-leagues", default="ATP")
    ap.add_argument("--snapshot-page-size", type=int, default=1000)
    ap.add_argument("--surface-filter", choices=sorted(SURFACE_FILTERS), default="all")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()
    if args.surface_filter != "all" and args.out == DEFAULT_OUT:
        args.out = f"data/backtest/spread-v1-{args.surface_filter}-calibration-params.json"
    surface_filter = _surface_filter_label(args.surface_filter)
    usable_surfaces = _surface_scope(args.surface_filter)

    def write_invalid_payload(reason: str) -> None:
        fit_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            "schema_version": 1,
            "generated_at_utc": fit_timestamp,
            "fit_timestamp": fit_timestamp,
            "line_source_requested": args.line_source,
            "line_source_used": line_source_used,
            "surface_filter": args.surface_filter,
            "files": list(args.files),
            "lines": lines if line_source_used == "synthetic" else None,
            "sample_count": 0,
            "train_sample_size": 0,
            "test_sample_size": 0,
            "years": sorted({m.year for m in match_rows}),
            "holdout_year": None,
            "skipped_rows": skipped_rows,
            "source_details": source_details,
            "best": None,
            "surface_eval": {},
            "calibration_valid": False,
            "calibration_reason": reason,
            "usable_scope": {
                "leagues": ["ATP"],
                "best_of": "bo3",
                "surfaces": usable_surfaces,
            },
            "usage": {},
            "correction_valid": False,
            "correction_reason": "base-calibration-invalid",
            "correction_model": {
                "valid": False,
                "reason": "base-calibration-invalid",
                "model_type": "spread_v1_additive_logit_offset_v1",
            },
        }
        out_path = args.out
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Wrote invalid calibration status to {out_path}")

    load_env()
    match_rows, skipped_rows = load_match_rows(args.files)
    if surface_filter:
        before_filter = len(match_rows)
        match_rows = [row for row in match_rows if row.surface == surface_filter]
        skipped_rows["surface_filter"] = before_filter - len(match_rows)
    if not match_rows:
        print("No usable match rows. Check --files and required columns (date/player1/player2/score/actual_winner).")
        return

    lines = [float(x.strip()) for x in args.lines.split(",") if x.strip()]
    line_source_used = args.line_source
    source_details: Dict[str, object] = {}

    samples: List[Sample] = []
    if args.line_source in {"snapshot", "auto"}:
        min_date = min(m.date_iso for m in match_rows)
        max_date = max(m.date_iso for m in match_rows)
        leagues = {_league_norm(x) for x in args.snapshot_leagues.split(",") if x.strip()}
        try:
            snapshot_rows = fetch_snapshot_spreads(
                start_date=min_date,
                end_date=max_date,
                leagues=leagues,
                bookmaker=args.snapshot_bookmaker,
                page_size=args.snapshot_page_size,
            )
        except Exception as exc:
            source_details["snapshot_error"] = str(exc)
            if args.line_source == "snapshot":
                print("Snapshot spread fetch failed.")
                print(f"Error: {exc}")
                write_invalid_payload("snapshot-fetch-failed")
                return
            snapshot_rows = []
        snap_samples, snap_stats = build_samples_from_snapshot(match_rows, snapshot_rows, args.snapshot_date_window)
        source_details["snapshot"] = snap_stats
        if snap_samples:
            samples = snap_samples
            line_source_used = "snapshot"
        elif args.line_source == "auto" and surface_filter:
            write_invalid_payload("no-real-market-snapshot-samples")
            print("No real market snapshot samples for surface-specific calibration.")
            print("Synthetic fallback is disabled when --surface-filter is set.")
            return
        elif args.line_source == "auto":
            samples, syn_stats = build_samples_synthetic(match_rows, lines)
            source_details["synthetic"] = syn_stats
            line_source_used = "synthetic"

    if not samples and args.line_source == "synthetic":
        samples, syn_stats = build_samples_synthetic(match_rows, lines)
        source_details["synthetic"] = syn_stats
        line_source_used = "synthetic"

    if not samples:
        write_invalid_payload("no-real-market-snapshot-samples")
        print("No calibration samples produced.")
        if source_details.get("snapshot"):
            print("Snapshot join stats:", source_details["snapshot"])
        print("Hint: snapshot-only spread_v1 remains off until real matched spread captures exist.")
        return

    fit = fit_calibration(samples, args.shift_min, args.shift_max, args.shift_step)
    best = fit["best"]
    years = fit["years"]
    holdout_year = fit["holdout_year"]

    fit_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema_version": 1,
        "generated_at_utc": fit_timestamp,
        "fit_timestamp": fit_timestamp,
        "line_source_requested": args.line_source,
        "line_source_used": line_source_used,
        "surface_filter": args.surface_filter,
        "files": list(args.files),
        "lines": lines if line_source_used == "synthetic" else None,
        "sample_count": len(samples),
        "train_sample_size": int(best["train_cal"]["n"]),
        "test_sample_size": int(best["test_cal"]["n"]) if best.get("test_cal") else 0,
        "calibration_valid": True,
        "calibration_reason": "ok",
        "years": years,
        "holdout_year": holdout_year,
        "skipped_rows": skipped_rows,
        "source_details": source_details,
        "best": best,
        "surface_eval": fit["surface_eval"],
        "usable_scope": {
            "leagues": ["ATP"],
            "best_of": "bo3",
            "surfaces": usable_surfaces,
        },
        "usage": {
            "HANDICAP_LINE_SHIFT": best["line_shift"],
            "HANDICAP_PLATT_A": best["platt_a"],
            "HANDICAP_PLATT_B": best["platt_b"],
        },
        "correction_valid": False,
        "correction_reason": "base-calibration-updated-needs-refit",
        "correction_model": {
            "valid": False,
            "reason": "base-calibration-updated-needs-refit",
            "model_type": "spread_v1_additive_logit_offset_v1",
        },
    }

    out_path = args.out
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    tr_raw = best["train_raw"]
    tr_cal = best["train_cal"]
    te_raw = best["test_raw"]
    te_cal = best["test_cal"]

    print("Handicap calibration fit complete")
    print(f"  line_source={line_source_used} samples={len(samples)} years={years} holdout_year={holdout_year}")
    if source_details.get("snapshot"):
        print(f"  snapshot stats: {source_details['snapshot']}")
    print(
        f"  best shift={best['line_shift']} a={best['platt_a']} b={best['platt_b']} objective={best['objective']:.6f}"
    )
    print(
        f"  train: bias {tr_raw['bias']:+.4f} -> {tr_cal['bias']:+.4f}, "
        f"logloss {tr_raw['log_loss']:.4f} -> {tr_cal['log_loss']:.4f}"
    )
    if te_raw and te_cal:
        print(
            f"  test : bias {te_raw['bias']:+.4f} -> {te_cal['bias']:+.4f}, "
            f"logloss {te_raw['log_loss']:.4f} -> {te_cal['log_loss']:.4f}"
        )
    print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
