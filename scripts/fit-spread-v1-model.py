#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
sys.path.insert(0, os.path.dirname(_SCRIPT_DIR))

from handicap_probs import prob_p1_covers_plus
from spread_v1_model import FEATURE_NAMES, MODEL_TYPE, clamp_prob, feature_vector, logit, sigmoid
from src.lib.tennis_prob import prob_match_best_of_3


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"
DEFAULT_FILES = [
    "data/backtest/backtest-results-2022.csv",
    "data/backtest/backtest-results-2023.csv",
    "data/backtest/backtest-results-2024.csv",
    "data/backtest/backtest-results-2025.csv",
    "data/backtest/backtest-results-2026.csv",
]
DEFAULT_DATASET_OUT = DATA_DIR / "spread-v1-training-dataset.csv"
DEFAULT_REPORT_OUT = DATA_DIR / "spread-v1-model-report.txt"
DEFAULT_CALIBRATION_FILE = DATA_DIR / "spread-v1-calibration-params.json"
DEFAULT_AUDIT_FILE = DATA_DIR / "handicap-input-audit.csv"
DEFAULT_GAMES_FILE = ROOT / "data" / "oncourt" / "games_atp.csv"

POINT_CLAMP_LO = 0.42
POINT_CLAMP_HI = 0.80
SURFACE_AVG_SPW = {"hard": 0.64, "clay": 0.62, "grass": 0.66, "i.hard": 0.65}
EXCLUDED_SERIES = {"Grand Slam", "Challenger"}
ALLOWED_SURFACES = {"Hard", "Clay"}
RIDGE_GRID = [0.0, 0.1, 0.3, 1.0, 3.0]
COEFFICIENT_NORM_PENALTY = 0.05


@dataclass
class MatchRow:
    year: int
    date_iso: str
    surface: str
    series: str
    player1: str
    player2: str
    margin_p1: float
    pa: float
    pb: float
    p1_match_prob: float


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
    source_file: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit the spread_v1 additive logit correction model.")
    parser.add_argument("--files", nargs="+", default=DEFAULT_FILES)
    parser.add_argument("--dataset-out", default=str(DEFAULT_DATASET_OUT))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT_OUT))
    parser.add_argument("--calibration-file", default=str(DEFAULT_CALIBRATION_FILE))
    parser.add_argument("--snapshot-date-window", type=int, default=1)
    parser.add_argument("--min-total-rows", type=int, default=80)
    parser.add_argument("--min-train-rows", type=int, default=40)
    parser.add_argument("--min-valid-rows", type=int, default=15)
    parser.add_argument("--min-test-rows", type=int, default=15)
    return parser.parse_args()


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


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _parse_float(v: object) -> float | None:
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
        return "Hard"
    if s in {"i.hard", "ihard", "indoor hard", "indoor_hard"}:
        return "I.hard"
    if s.startswith("hard"):
        return "Hard"
    if s.startswith("clay"):
        return "Clay"
    if s.startswith("grass"):
        return "Grass"
    return "Hard"


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


def _parse_date_iso(v: object) -> str | None:
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


def _parse_timestamp(v: object) -> float:
    s = str(v or "").strip()
    if not s:
        return 0.0
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _iso_date_shift(iso_date: str, delta_days: int) -> str:
    d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return (d + timedelta(days=delta_days)).isoformat()


def _solve_spw_for_match_prob(p1_win: float, avg_spw: float) -> tuple[float, float]:
    p1_win = _clamp(p1_win, 0.02, 0.98)
    avg_spw = _clamp(avg_spw, POINT_CLAMP_LO + 0.01, POINT_CLAMP_HI - 0.01)
    max_delta = min(avg_spw - POINT_CLAMP_LO, POINT_CLAMP_HI - avg_spw)
    lo, hi = -max_delta, max_delta
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        pa = _clamp(avg_spw + mid, POINT_CLAMP_LO, POINT_CLAMP_HI)
        pb = _clamp(avg_spw - mid, POINT_CLAMP_LO, POINT_CLAMP_HI)
        implied = prob_match_best_of_3(pa, pb)
        if abs(implied - p1_win) < 5e-4:
            return pa, pb
        if implied < p1_win:
            lo = mid
        else:
            hi = mid
    mid = 0.5 * (lo + hi)
    return (
        _clamp(avg_spw + mid, POINT_CLAMP_LO, POINT_CLAMP_HI),
        _clamp(avg_spw - mid, POINT_CLAMP_LO, POINT_CLAMP_HI),
    )


def parse_score_games(score_str: str) -> tuple[int, int] | None:
    if not score_str:
        return None
    s = str(score_str).strip().upper()
    if not s or any(token in s for token in ["W/O", "WALKOVER", "DEF", "RET"]):
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


def _pick_col(fieldnames: Sequence[str], candidates: Sequence[str]) -> str | None:
    keys = set(fieldnames)
    for candidate in candidates:
        if candidate in keys:
            return candidate
    return None


def load_match_rows(files: Sequence[str]) -> tuple[list[MatchRow], dict[str, int]]:
    rows: list[MatchRow] = []
    skipped = {
        "file_missing": 0,
        "no_prob": 0,
        "no_score": 0,
        "no_winner": 0,
        "bad_date": 0,
        "bad_margin": 0,
        "no_names": 0,
        "filtered_scope": 0,
    }
    for rel_path in files:
        path = Path(rel_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            skipped["file_missing"] += 1
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            cols = reader.fieldnames or []
            if not cols:
                continue

            c_prob = _pick_col(cols, ["our_prob", "p1_win_prob", "model_p1", "prob_p1"])
            c_surface = _pick_col(cols, ["surface"])
            c_series = _pick_col(cols, ["series"])
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

                series = str(row.get(c_series) or "").strip() if c_series else ""
                surface = _normalize_surface(row.get(c_surface))
                if surface not in ALLOWED_SURFACES or series in EXCLUDED_SERIES:
                    skipped["filtered_scope"] += 1
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

                p1_prob = _parse_float(row.get(c_prob)) if c_prob else None
                pa = _parse_float(row.get(c_pa)) if c_pa else None
                pb = _parse_float(row.get(c_pb)) if c_pb else None
                if p1_prob is None and pa is not None and pb is not None:
                    p1_prob = prob_match_best_of_3(pa, pb)
                if p1_prob is None:
                    skipped["no_prob"] += 1
                    continue
                if pa is None or pb is None:
                    avg_spw = SURFACE_AVG_SPW.get(surface.lower(), 0.64)
                    pa, pb = _solve_spw_for_match_prob(p1_prob, avg_spw)

                rows.append(
                    MatchRow(
                        year=year,
                        date_iso=date_iso,
                        surface=surface,
                        series=series,
                        player1=p1_name,
                        player2=p2_name,
                        margin_p1=float(margin_p1),
                        pa=float(pa),
                        pb=float(pb),
                        p1_match_prob=float(p1_prob),
                    )
                )
    return rows, skipped


def _capture_date_from_filename(path: Path) -> str | None:
    name = path.name
    match = re.search(r"pinnacle-odds-(\d{4}-\d{2}-\d{2})\.csv$", name)
    if match:
        return match.group(1)
    match = re.search(r"pinnacle-history-(\d{8})-(\d{6})\.csv$", name)
    if match:
        date_part = match.group(1)
        return f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
    return None


def _captured_at_from_filename(path: Path, capture_date: str | None) -> str:
    name = path.name
    match = re.search(r"pinnacle-history-(\d{8})-(\d{6})\.csv$", name)
    if match:
        date_part = match.group(1)
        time_part = match.group(2)
        return (
            f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}T"
            f"{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}Z"
        )
    if capture_date:
        return f"{capture_date}T23:59:59Z"
    return ""


def load_local_snapshot_rows(start_date: str, end_date: str, leagues: set[str]) -> list[SnapshotSpread]:
    rows: list[SnapshotSpread] = []
    files = [
        *sorted((ROOT / "data" / "pinnacle-history").glob("*.csv")),
        *sorted((ROOT / "data").glob("pinnacle-odds-*.csv")),
    ]
    for path in files:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for raw in reader:
                    capture_date = _parse_date_iso(raw.get("capture_date")) or _capture_date_from_filename(path)
                    if not capture_date or capture_date < start_date or capture_date > end_date:
                        continue
                    league = str(raw.get("league") or "").strip()
                    if leagues and league not in leagues:
                        continue
                    line = _parse_float(raw.get("spread_line"))
                    odds1 = _parse_float(raw.get("spread_odds1"))
                    odds2 = _parse_float(raw.get("spread_odds2"))
                    if line is None or odds1 is None or odds2 is None or odds1 <= 1.0 or odds2 <= 1.0:
                        continue
                    p1 = str(raw.get("player1_name") or "").strip()
                    p2 = str(raw.get("player2_name") or "").strip()
                    if not p1 or not p2:
                        continue
                    captured_at = str(raw.get("captured_at") or "").strip() or _captured_at_from_filename(path, capture_date)
                    n1 = _normalize_name(p1)
                    n2 = _normalize_name(p2)
                    if not n1 or not n2:
                        continue
                    rows.append(
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
                            line=float(line),
                            odds1=float(odds1),
                            odds2=float(odds2),
                            source_file=path.name,
                        )
                    )
        except FileNotFoundError:
            continue
    return rows


def build_snapshot_indices(
    rows: Sequence[SnapshotSpread],
) -> tuple[dict[tuple[str, str, str], list[tuple[SnapshotSpread, bool]]], dict[tuple[str, str, str], list[tuple[SnapshotSpread, bool]]]]:
    exact: dict[tuple[str, str, str], list[tuple[SnapshotSpread, bool]]] = {}
    surname: dict[tuple[str, str, str], list[tuple[SnapshotSpread, bool]]] = {}
    for row in rows:
        exact.setdefault((row.capture_date, row.n1, row.n2), []).append((row, False))
        exact.setdefault((row.capture_date, row.n2, row.n1), []).append((row, True))
        surname.setdefault((row.capture_date, row.s1, row.s2), []).append((row, False))
        surname.setdefault((row.capture_date, row.s2, row.s1), []).append((row, True))
    return exact, surname


def _dedupe_candidates(cands: list[tuple[SnapshotSpread, bool]]) -> list[tuple[SnapshotSpread, bool]]:
    deduped: dict[tuple[str, str, str, float, bool], tuple[SnapshotSpread, bool]] = {}
    for snap, reversed_for_match in cands:
        key = (snap.capture_date, snap.n1, snap.n2, float(snap.line), reversed_for_match)
        prev = deduped.get(key)
        if prev is None or snap.captured_ts > prev[0].captured_ts:
            deduped[key] = (snap, reversed_for_match)
    return list(deduped.values())


def _choose_best_snapshot(cands: list[tuple[SnapshotSpread, bool]]) -> tuple[SnapshotSpread, bool]:
    def priority(item: tuple[SnapshotSpread, bool]) -> tuple[int, float]:
        snap, _ = item
        league_priority = 0 if snap.league == "ATP" else 1
        return (league_priority, -snap.captured_ts)

    return sorted(cands, key=priority)[0]


def find_snapshot_for_match(
    match_row: MatchRow,
    exact_idx: dict[tuple[str, str, str], list[tuple[SnapshotSpread, bool]]],
    surname_idx: dict[tuple[str, str, str], list[tuple[SnapshotSpread, bool]]],
    date_window_days: int,
) -> tuple[SnapshotSpread | None, bool, str | None]:
    n1 = _normalize_name(match_row.player1)
    n2 = _normalize_name(match_row.player2)
    s1 = _surname_key(n1)
    s2 = _surname_key(n2)
    date_candidates = [_iso_date_shift(match_row.date_iso, delta) for delta in range(-date_window_days, date_window_days + 1)]

    for current_date in date_candidates:
        candidates = _dedupe_candidates(exact_idx.get((current_date, n1, n2), []))
        if not candidates:
            continue
        if len(candidates) == 1:
            snap, reversed_for_match = candidates[0]
            method = "exact_same_day" if current_date == match_row.date_iso else "exact_date_window"
            return snap, reversed_for_match, method
        snap, reversed_for_match = _choose_best_snapshot(candidates)
        method = "exact_multi_same_day" if current_date == match_row.date_iso else "exact_multi_window"
        return snap, reversed_for_match, method

    for current_date in date_candidates:
        candidates = _dedupe_candidates(surname_idx.get((current_date, s1, s2), []))
        if not candidates:
            continue
        if len(candidates) == 1:
            snap, reversed_for_match = candidates[0]
            method = "surname_same_day" if current_date == match_row.date_iso else "surname_date_window"
            return snap, reversed_for_match, method
        return None, False, "ambiguous_surname"

    return None, False, None


def load_base_calibration(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"enabled": False, "reason": "missing", "line_shift": 0.0, "platt_a": 0.0, "platt_b": 1.0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": False, "reason": "unreadable", "line_shift": 0.0, "platt_a": 0.0, "platt_b": 1.0}
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    try:
        return {
            "enabled": True,
            "reason": "ok",
            "line_shift": float(usage.get("HANDICAP_LINE_SHIFT", 0.0)),
            "platt_a": float(usage.get("HANDICAP_PLATT_A", 0.0)),
            "platt_b": float(usage.get("HANDICAP_PLATT_B", 1.0)),
            "payload": payload,
        }
    except (TypeError, ValueError):
        return {
            "enabled": False,
            "reason": "missing-usage",
            "line_shift": 0.0,
            "platt_a": 0.0,
            "platt_b": 1.0,
            "payload": payload,
        }


def _calibrate_prob(raw_prob: float, calibration: dict[str, Any]) -> float:
    if not calibration.get("enabled"):
        return clamp_prob(raw_prob)
    return clamp_prob(sigmoid(float(calibration["platt_a"]) + float(calibration["platt_b"]) * logit(raw_prob)))


def build_dataset(
    matches: Sequence[MatchRow],
    snapshots: Sequence[SnapshotSpread],
    date_window_days: int,
    calibration: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    stats = {"snapshot_rows": len(snapshots), "match_rows": len(matches), "matched": 0, "unmatched": 0, "ambiguous": 0, "feature_invalid": 0}
    method_counts: dict[str, int] = {}
    exact_idx, surname_idx = build_snapshot_indices(snapshots)
    for match_row in matches:
        snap, reversed_for_match, method = find_snapshot_for_match(match_row, exact_idx, surname_idx, date_window_days)
        if snap is None:
            stats["unmatched"] += 1
            if method and method.startswith("ambiguous"):
                stats["ambiguous"] += 1
            continue
        stats["matched"] += 1
        method_counts[method or "unknown"] = method_counts.get(method or "unknown", 0) + 1

        line = -float(snap.line) if reversed_for_match else float(snap.line)
        odds1 = float(snap.odds2) if reversed_for_match else float(snap.odds1)
        odds2 = float(snap.odds1) if reversed_for_match else float(snap.odds2)
        base_raw = prob_p1_covers_plus(match_row.pa, match_row.pb, line)
        shifted_raw = prob_p1_covers_plus(match_row.pa, match_row.pb, line + float(calibration.get("line_shift", 0.0)))
        base_prob = _calibrate_prob(shifted_raw, calibration)
        feats = feature_vector(base_prob=base_prob, surface=match_row.surface, line=line, p1_match_prob=match_row.p1_match_prob, odds1=odds1, odds2=odds2)
        if feats is None:
            stats["feature_invalid"] += 1
            continue
        market_prob_p1 = sigmoid(logit(base_prob) + feats["market_logit_delta"])
        cover_result = 1 if match_row.margin_p1 > -line else 0
        rows.append(
            {
                "date_iso": match_row.date_iso,
                "year": match_row.year,
                "surface": match_row.surface,
                "series": match_row.series,
                "league": snap.league,
                "player1": match_row.player1,
                "player2": match_row.player2,
                "spread_line": round(line, 3),
                "spread_odds1": round(odds1, 4),
                "spread_odds2": round(odds2, 4),
                "p1_match_prob": round(match_row.p1_match_prob, 6),
                "p_a": round(match_row.pa, 6),
                "p_b": round(match_row.pb, 6),
                "margin_p1": round(match_row.margin_p1, 3),
                "cover_result": cover_result,
                "base_prob_raw": round(base_raw, 6),
                "base_prob": round(base_prob, 6),
                "market_prob_devig_p1": round(market_prob_p1, 6),
                "market_logit_delta": round(feats["market_logit_delta"], 6),
                "overround": round(feats["overround"], 6),
                "line_bucket": f"{abs(line):.1f}",
                "match_method": method or "",
                "captured_at": snap.captured_at,
                "snapshot_source_file": snap.source_file,
                **{name: round(float(value), 6) for name, value in feats.items()},
            }
        )
    for key, value in method_counts.items():
        stats[f"method_{key}"] = value
    return rows, stats


def _is_grand_slam_name(name: str) -> bool:
    upper = str(name or "").upper()
    return any(token in upper for token in ["AUSTRALIAN OPEN", "ROLAND GARROS", "WIMBLEDON", "US OPEN", "GRAND SLAM"])


def _is_challenger_name(name: str) -> bool:
    return "CHALLENGER" in str(name or "").upper()


def build_games_lookup(start_date: str, end_date: str, tour_ids: set[int]) -> dict[tuple[str, int, int, int], str]:
    lookup: dict[tuple[str, int, int, int], str] = {}
    if not DEFAULT_GAMES_FILE.exists():
        return lookup
    with DEFAULT_GAMES_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            date_iso = _parse_date_iso(row.get("date"))
            if not date_iso or date_iso < start_date or date_iso > end_date:
                continue
            tour_id = int(row.get("tour_id") or 0)
            if tour_ids and tour_id not in tour_ids:
                continue
            winner_id = int(row.get("winner_id") or 0)
            loser_id = int(row.get("loser_id") or 0)
            result = str(row.get("result") or "").strip()
            if not winner_id or not loser_id or not result:
                continue
            lookup[(date_iso, tour_id, winner_id, loser_id)] = result
    return lookup


def build_dataset_from_audit(audit_path: Path, calibration: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not audit_path.exists():
        return [], {"audit_missing": 1}

    raw_rows: list[dict[str, str]] = []
    with audit_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            surface = _normalize_surface(row.get("surface"))
            if surface not in ALLOWED_SURFACES:
                continue
            if _is_grand_slam_name(str(row.get("tournament") or "")):
                continue
            if _is_challenger_name(str(row.get("tournament") or "")):
                continue
            if any(_parse_float(row.get(field)) is None for field in ["used_p_a", "used_p_b", "final_match_prob_p1", "spread_line", "spread_odds1", "spread_odds2"]):
                continue
            raw_rows.append(dict(row))

    if not raw_rows:
        return [], {"audit_rows": 0, "games_lookup": 0, "matched": 0, "unmatched": 0}

    start_date = min(str(row["capture_date"]) for row in raw_rows)
    end_date = max(str(row["capture_date"]) for row in raw_rows)
    tour_ids = {int(row["tour_id"]) for row in raw_rows if str(row.get("tour_id") or "").strip()}
    games_lookup = build_games_lookup(start_date, end_date, tour_ids)

    dataset_rows: list[dict[str, Any]] = []
    unmatched = 0
    for row in raw_rows:
        date_iso = str(row["capture_date"])
        tour_id = int(row["tour_id"])
        p1_id = int(row["player1_id"])
        p2_id = int(row["player2_id"])
        result = games_lookup.get((date_iso, tour_id, p1_id, p2_id))
        if result:
            parsed = parse_score_games(result)
            if parsed is None:
                continue
            margin_p1 = parsed[0] - parsed[1]
        else:
            result = games_lookup.get((date_iso, tour_id, p2_id, p1_id))
            if not result:
                unmatched += 1
                continue
            parsed = parse_score_games(result)
            if parsed is None:
                continue
            margin_p1 = -(parsed[0] - parsed[1])

        line = float(row["spread_line"])
        odds1 = float(row["spread_odds1"])
        odds2 = float(row["spread_odds2"])
        p1_match_prob = clamp_prob(float(row["final_match_prob_p1"]))
        pa = clamp_prob(float(row["used_p_a"]))
        pb = clamp_prob(float(row["used_p_b"]))
        base_raw = prob_p1_covers_plus(pa, pb, line)
        shifted_raw = prob_p1_covers_plus(pa, pb, line + float(calibration.get("line_shift", 0.0)))
        base_prob = _calibrate_prob(shifted_raw, calibration)
        feats = feature_vector(base_prob=base_prob, surface=row["surface"], line=line, p1_match_prob=p1_match_prob, odds1=odds1, odds2=odds2)
        if feats is None:
            continue
        market_prob_p1 = sigmoid(logit(base_prob) + feats["market_logit_delta"])
        cover_result = 1 if margin_p1 > -line else 0
        dataset_rows.append(
            {
                "date_iso": date_iso,
                "year": int(date_iso[:4]),
                "surface": _normalize_surface(row["surface"]),
                "series": "",
                "league": "ATP",
                "player1": row["player1_name"],
                "player2": row["player2_name"],
                "spread_line": round(line, 3),
                "spread_odds1": round(odds1, 4),
                "spread_odds2": round(odds2, 4),
                "p1_match_prob": round(p1_match_prob, 6),
                "p_a": round(pa, 6),
                "p_b": round(pb, 6),
                "margin_p1": round(float(margin_p1), 3),
                "cover_result": cover_result,
                "base_prob_raw": round(base_raw, 6),
                "base_prob": round(base_prob, 6),
                "market_prob_devig_p1": round(market_prob_p1, 6),
                "market_logit_delta": round(feats["market_logit_delta"], 6),
                "overround": round(feats["overround"], 6),
                "line_bucket": f"{abs(line):.1f}",
                "match_method": "audit_local",
                "captured_at": row.get("generated_utc", ""),
                "snapshot_source_file": audit_path.name,
                **{name: round(float(value), 6) for name, value in feats.items()},
            }
        )

    return dataset_rows, {
        "audit_rows": len(raw_rows),
        "games_lookup": len(games_lookup),
        "matched": len(dataset_rows),
        "unmatched": unmatched,
        "source": "handicap-input-audit",
    }


def metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    q = np.clip(p.astype(float), 1e-6, 1.0 - 1e-6)
    yy = y.astype(float)
    ll = -np.mean(yy * np.log(q) + (1.0 - yy) * np.log(1.0 - q))
    br = np.mean((q - yy) ** 2)
    hit = float(np.mean(yy))
    pred = float(np.mean(q))
    return {"n": int(len(yy)), "hit_rate": hit, "mean_pred": pred, "bias": pred - hit, "brier": float(br), "log_loss": float(ll)}


def fit_offset_logistic(X: np.ndarray, offset: np.ndarray, y: np.ndarray, ridge: float) -> tuple[float, np.ndarray]:
    n_features = X.shape[1]
    beta = np.zeros(n_features + 1, dtype=float)
    identity = np.eye(n_features + 1, dtype=float)
    identity[0, 0] = 0.0
    for _ in range(100):
        z = offset + beta[0] + X @ beta[1:]
        p = np.clip(1.0 / (1.0 + np.exp(-z)), 1e-6, 1.0 - 1e-6)
        w = p * (1.0 - p)
        design = np.column_stack([np.ones_like(offset), X])
        grad = design.T @ (p - y) + ridge * (identity @ beta)
        hess = (design.T * w) @ design + ridge * identity
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
        beta_next = beta - step
        if float(np.linalg.norm(step)) < 1e-8:
            beta = beta_next
            break
        beta = beta_next
    return float(beta[0]), beta[1:].copy()


def predict_offset_logistic(X: np.ndarray, offset: np.ndarray, intercept: float, coefs: np.ndarray) -> np.ndarray:
    z = offset + intercept + X @ coefs
    return 1.0 / (1.0 + np.exp(-z))


def build_time_splits(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    dates = sorted({str(row["date_iso"]) for row in rows})
    if len(dates) < 5:
        empty = np.zeros(len(rows), dtype=bool)
        return empty, empty.copy(), empty.copy(), "insufficient-dates"
    train_cut = max(1, int(math.ceil(len(dates) * 0.6)))
    valid_cut = max(train_cut + 1, int(math.ceil(len(dates) * 0.8)))
    train_dates = set(dates[:train_cut])
    valid_dates = set(dates[train_cut:valid_cut])
    test_dates = set(dates[valid_cut:])
    train_mask = np.array([row["date_iso"] in train_dates for row in rows], dtype=bool)
    valid_mask = np.array([row["date_iso"] in valid_dates for row in rows], dtype=bool)
    test_mask = np.array([row["date_iso"] in test_dates for row in rows], dtype=bool)
    return train_mask, valid_mask, test_mask, "date-ordered-60/20/20"


def summarize_surface_metrics(rows: list[dict[str, Any]], mask: np.ndarray, preds: np.ndarray) -> dict[str, Any]:
    out: dict[str, Any] = {}
    masked_rows = [rows[i] for i in np.where(mask)[0]]
    if not masked_rows:
        return out
    masked_preds = preds[mask]
    masked_y = np.array([float(row["cover_result"]) for row in masked_rows], dtype=float)
    for surface in sorted({row["surface"] for row in masked_rows}):
        idx = np.array([i for i, row in enumerate(masked_rows) if row["surface"] == surface], dtype=int)
        if len(idx) == 0:
            continue
        out[surface] = metrics(masked_y[idx], masked_preds[idx])
    return out


def write_dataset_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_invalid_correction(reason: str, generated_at: str, dataset_path: Path, dataset_rows: int, dataset_stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid": False,
        "reason": reason,
        "model_type": MODEL_TYPE,
        "fit_timestamp": generated_at,
        "dataset_file": str(dataset_path.relative_to(ROOT)),
        "dataset_rows": dataset_rows,
        "dataset_stats": dataset_stats,
        "usable_scope": {"leagues": ["ATP"], "best_of": "bo3", "surfaces": sorted(ALLOWED_SURFACES)},
    }


def main() -> None:
    args = parse_args()
    load_env()

    calibration_path = Path(args.calibration_file)
    if not calibration_path.is_absolute():
        calibration_path = ROOT / calibration_path
    dataset_path = Path(args.dataset_out)
    if not dataset_path.is_absolute():
        dataset_path = ROOT / dataset_path
    report_path = Path(args.report_out)
    if not report_path.is_absolute():
        report_path = ROOT / report_path

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    calibration = load_base_calibration(calibration_path)
    skipped_rows: dict[str, Any] = {}

    if DEFAULT_AUDIT_FILE.exists():
        dataset_rows, dataset_stats = build_dataset_from_audit(DEFAULT_AUDIT_FILE, calibration)
        write_dataset_csv(dataset_path, dataset_rows)
        report_dataset_context = [
            f"Dataset source: audit_local ({DEFAULT_AUDIT_FILE.relative_to(ROOT)})",
            f"Dataset rows: {len(dataset_rows)}",
            f"Dataset stats: {dataset_stats}",
            "",
        ]
    else:
        matches, skipped_rows = load_match_rows(args.files)
        if not matches:
            correction = build_invalid_correction("no-match-rows", generated_at, dataset_path, 0, {"skipped_rows": skipped_rows})
            base_payload = {}
            if calibration_path.exists():
                try:
                    base_payload = json.loads(calibration_path.read_text(encoding="utf-8"))
                except Exception:
                    base_payload = {}
            base_payload["correction_valid"] = False
            base_payload["correction_reason"] = correction["reason"]
            base_payload["correction_model"] = correction
            calibration_path.write_text(json.dumps(base_payload, indent=2), encoding="utf-8")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("Spread v1 model fit failed: no usable match rows.\n", encoding="utf-8")
            print("No usable match rows for spread_v1 model fit.")
            return

        min_date = min(row.date_iso for row in matches)
        max_date = max(row.date_iso for row in matches)
        snapshots = load_local_snapshot_rows(min_date, max_date, {"ATP"})
        dataset_rows, dataset_stats = build_dataset(matches, snapshots, args.snapshot_date_window, calibration)
        write_dataset_csv(dataset_path, dataset_rows)
        report_dataset_context = [
            "Dataset source: matched local snapshots",
            f"Match rows: {len(matches)}",
            f"Snapshot rows: {len(snapshots)}",
            f"Dataset rows: {len(dataset_rows)}",
            f"Dataset stats: {dataset_stats}",
            f"Skipped rows: {skipped_rows}",
            "",
        ]

    if not dataset_rows:
        correction = build_invalid_correction("no-dataset-rows", generated_at, dataset_path, 0, {**dataset_stats, "skipped_rows": skipped_rows})
        base_payload = {}
        if calibration_path.exists():
            try:
                base_payload = json.loads(calibration_path.read_text(encoding="utf-8"))
            except Exception:
                base_payload = {}
        base_payload["correction_valid"] = False
        base_payload["correction_reason"] = correction["reason"]
        base_payload["correction_model"] = correction
        calibration_path.write_text(json.dumps(base_payload, indent=2), encoding="utf-8")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("Spread v1 model fit failed: no usable spread_v1 training rows.\n", encoding="utf-8")
        print("No usable spread_v1 training rows.")
        return

    report_lines = [
        "Spread v1 Model Fit",
        f"Generated UTC: {generated_at}",
        f"Calibration file: {calibration_path.relative_to(ROOT)}",
        f"Dataset file: {dataset_path.relative_to(ROOT)}",
        f"Base calibration enabled: {calibration.get('enabled', False)} ({calibration.get('reason', 'n/a')})",
        "",
    ] + report_dataset_context

    if len(dataset_rows) < args.min_total_rows:
        correction_payload = build_invalid_correction(f"insufficient-dataset-rows:{len(dataset_rows)}", generated_at, dataset_path, len(dataset_rows), dataset_stats)
        report_lines.append(f"Correction model invalid: {correction_payload['reason']}")
    else:
        sorted_rows = sorted(dataset_rows, key=lambda row: (row["date_iso"], row.get("captured_at", ""), row["player1"], row["player2"]))
        X = np.array([[float(row[name]) for name in FEATURE_NAMES] for row in sorted_rows], dtype=float)
        y = np.array([float(row["cover_result"]) for row in sorted_rows], dtype=float)
        base_prob = np.array([float(row["base_prob"]) for row in sorted_rows], dtype=float)
        offset = np.array([logit(prob) for prob in base_prob], dtype=float)
        train_mask, valid_mask, test_mask, split_strategy = build_time_splits(sorted_rows)

        if int(train_mask.sum()) < args.min_train_rows or int(valid_mask.sum()) < args.min_valid_rows or int(test_mask.sum()) < args.min_test_rows:
            correction_payload = build_invalid_correction(
                "insufficient-time-split-samples",
                generated_at,
                dataset_path,
                len(dataset_rows),
                {**dataset_stats, "split_strategy": split_strategy, "train_rows": int(train_mask.sum()), "valid_rows": int(valid_mask.sum()), "test_rows": int(test_mask.sum())},
            )
            report_lines.append(f"Correction model invalid: {correction_payload['reason']}")
        else:
            best_fit: dict[str, Any] | None = None
            for ridge in RIDGE_GRID:
                intercept, coefs = fit_offset_logistic(X[train_mask], offset[train_mask], y[train_mask], ridge)
                preds_all = predict_offset_logistic(X, offset, intercept, coefs)
                coefficient_norm = float(np.linalg.norm(coefs))
                candidate = {
                    "ridge": ridge,
                    "intercept": float(intercept),
                    "coefficients": {name: float(value) for name, value in zip(FEATURE_NAMES, coefs.tolist())},
                    "coefficient_norm": coefficient_norm,
                    "train_base": metrics(y[train_mask], base_prob[train_mask]),
                    "valid_base": metrics(y[valid_mask], base_prob[valid_mask]),
                    "test_base": metrics(y[test_mask], base_prob[test_mask]),
                    "train_corrected": metrics(y[train_mask], preds_all[train_mask]),
                    "valid_corrected": metrics(y[valid_mask], preds_all[valid_mask]),
                    "test_corrected": metrics(y[test_mask], preds_all[test_mask]),
                    "surface_eval_test": summarize_surface_metrics(sorted_rows, test_mask, preds_all),
                }
                candidate["objective"] = float(
                    candidate["valid_corrected"]["log_loss"]
                    + 0.25 * abs(candidate["valid_corrected"]["bias"])
                    + COEFFICIENT_NORM_PENALTY * coefficient_norm
                )
                if best_fit is None or candidate["objective"] < best_fit["objective"]:
                    best_fit = candidate

            assert best_fit is not None
            improved = best_fit["valid_corrected"]["log_loss"] <= best_fit["valid_base"]["log_loss"]
            correction_payload = {
                "valid": bool(improved),
                "reason": "ok" if improved else "validation-regressed-vs-baseline",
                "model_type": MODEL_TYPE,
                "fit_timestamp": generated_at,
                "dataset_file": str(dataset_path.relative_to(ROOT)),
                "dataset_rows": len(dataset_rows),
                "dataset_stats": dataset_stats,
                "baseline_source": "calibrated" if calibration.get("enabled") else "raw",
                "devig_method": "normalized_inverse_odds",
                "split_strategy": split_strategy,
                "train_sample_size": int(train_mask.sum()),
                "validation_sample_size": int(valid_mask.sum()),
                "test_sample_size": int(test_mask.sum()),
                "feature_names": FEATURE_NAMES,
                "intercept": round(float(best_fit["intercept"]), 8),
                "coefficients": {k: round(float(v), 8) for k, v in best_fit["coefficients"].items()},
                "coefficient_norm": round(float(best_fit["coefficient_norm"]), 8),
                "ridge": best_fit["ridge"],
                "max_abs_logit_adjustment": 1.25,
                "usable_scope": {"leagues": ["ATP"], "best_of": "bo3", "surfaces": sorted(ALLOWED_SURFACES)},
                "metrics": {
                    "train_base": best_fit["train_base"],
                    "validation_base": best_fit["valid_base"],
                    "test_base": best_fit["test_base"],
                    "train_corrected": best_fit["train_corrected"],
                    "validation_corrected": best_fit["valid_corrected"],
                    "test_corrected": best_fit["test_corrected"],
                },
                "surface_eval_test": best_fit["surface_eval_test"],
            }
            report_lines.extend(
                [
                    f"Split strategy: {split_strategy}",
                    f"Train/valid/test rows: {int(train_mask.sum())}/{int(valid_mask.sum())}/{int(test_mask.sum())}",
                    f"Selected ridge: {best_fit['ridge']}",
                    f"Coefficient norm: {best_fit['coefficient_norm']:.5f}",
                    f"Validation log loss: base {best_fit['valid_base']['log_loss']:.5f} -> corrected {best_fit['valid_corrected']['log_loss']:.5f}",
                    f"Validation bias: base {best_fit['valid_base']['bias']:+.5f} -> corrected {best_fit['valid_corrected']['bias']:+.5f}",
                    f"Test log loss: base {best_fit['test_base']['log_loss']:.5f} -> corrected {best_fit['test_corrected']['log_loss']:.5f}",
                    f"Test brier: base {best_fit['test_base']['brier']:.5f} -> corrected {best_fit['test_corrected']['brier']:.5f}",
                    f"Model status: {correction_payload['reason']}",
                ]
            )

    base_payload: dict[str, Any] = {}
    if calibration_path.exists():
        try:
            base_payload = json.loads(calibration_path.read_text(encoding="utf-8"))
        except Exception:
            base_payload = {}
    base_payload["correction_valid"] = bool(correction_payload["valid"])
    base_payload["correction_reason"] = str(correction_payload["reason"])
    base_payload["correction_fit_timestamp"] = generated_at
    base_payload["correction_model"] = correction_payload
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    calibration_path.write_text(json.dumps(base_payload, indent=2), encoding="utf-8")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print("\n".join(report_lines))
    print(f"Wrote correction model status into {calibration_path}")


if __name__ == "__main__":
    main()
