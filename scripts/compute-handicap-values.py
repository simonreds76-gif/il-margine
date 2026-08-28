#!/usr/bin/env python3
"""
Compute handicap (spread) value for daily_fair_odds matches using Pinnacle spread lines.

Run after: (1) oncourt-compute-fair-odds.py, (2) pinnacle-scrape-odds.py

If daily_fair_odds is recomputed later (e.g. via Supabase), spread columns get overwritten
with null. Re-run this script or the full pipeline (run-daily-odds.py) to restore handicaps.

Matches daily_fair_odds to bookmaker_odds_snapshot, prefers the stored matchup point-probability
pair (`p_a`, `p_b`) when available, but only if those stored values imply a best-of-3 match
win probability close enough to the final blended match win probability (`p1_win_prob`).
If the gap is too large, it falls back to a reverse-solved symmetric pair from the final
blended match win probability so the match-winner and handicap paths stay consistent.
It then computes model spread edges and PATCHes daily_fair_odds with spread + handicap_edge
columns.

Using stored `p_a` / `p_b` preserves the richer serve/return shape when the serve model and
the final blended model broadly agree. Falling back to the solved pair on large divergences
prevents same-match ML/HC contradictions in Elo- or rank-dominated spots.

Usage:
  python scripts/compute-handicap-values.py
  python scripts/compute-handicap-values.py --date 2026-03-09
  python scripts/compute-handicap-values.py --dry-run
"""

import argparse
import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from statistics import mean, median

import requests

# Add scripts dir + project root for local imports
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
sys.path.insert(0, os.path.dirname(_SCRIPT_DIR))
from handicap_probs import cover_probs, match_margin_pmf, match_win_probability
from spread_v1_model import apply_correction


POINT_CLAMP = (0.42, 0.80)
SURFACE_LEAGUE_AVG = {"Hard": 0.64, "Clay": 0.62, "Grass": 0.67, "I.hard": 0.64, "N/A": 0.64}
MIN_VENUE_SPW_MATCHES = 50
# The stored point-probability pair should only drive handicaps when it still
# implies roughly the same match winner view as the final blended match model.
# 12 percentage points was letting obviously contradictory ML/handicap rows
# survive; tighten this so we fall back to the reverse-solved shape sooner.
POINT_PROB_MATCH_PROB_GAP_MAX = 0.08
MODEL_MARKET_FAV_PROB_GAP_MAX = 0.10
MODEL_MARKET_FAV_SIDE_FLIP_BUFFER = 0.03


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _root_dir() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(base)


@dataclass
class HandicapCalibration:
    enabled: bool
    line_shift: float
    platt_a: float
    platt_b: float
    source: str
    payload: dict | None = None


def _chunked(values: list[int], size: int):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _fetch_rest_paged(base_url: str, table: str, headers: dict, params: dict, *, page_size: int = 1000, timeout: int = 30):
    rows = []
    offset = 0
    while True:
        page_params = {**params, "limit": page_size, "offset": offset}
        response = requests.get(
            f"{base_url}/rest/v1/{table}",
            headers=headers,
            params=page_params,
            timeout=timeout,
        )
        response.raise_for_status()
        page = response.json() or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
    return rows


def _solve_spw_for_match_prob(
    p1_win: float,
    avg_spw: float,
    best_of: str = "bo3",
    clamp_lo: float = POINT_CLAMP[0],
    clamp_hi: float = POINT_CLAMP[1],
    tol: float = 5e-4,
    max_iter: int = 60,
):
    """
    Solve symmetric point-win probabilities around avg_spw such that the implied
    match win probability matches the final fair-odds `p1_win`.
    """
    p1_win = _clamp(p1_win, 0.02, 0.98)
    avg_spw = _clamp(avg_spw, clamp_lo + 0.01, clamp_hi - 0.01)
    max_delta = min(avg_spw - clamp_lo, clamp_hi - avg_spw)
    lo, hi = -max_delta, max_delta
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        p_a = _clamp(avg_spw + mid, clamp_lo, clamp_hi)
        p_b = _clamp(avg_spw - mid, clamp_lo, clamp_hi)
        implied = match_win_probability(p_a, p_b, best_of)
        if abs(implied - p1_win) < tol:
            return (p_a, p_b)
        if implied < p1_win:
            lo = mid
        else:
            hi = mid
    mid = (lo + hi) / 2.0
    return (
        _clamp(avg_spw + mid, clamp_lo, clamp_hi),
        _clamp(avg_spw - mid, clamp_lo, clamp_hi),
    )


def _is_grand_slam_event(tour_meta: dict | None) -> bool:
    if not isinstance(tour_meta, dict):
        return False
    tour_name = str(tour_meta.get("name") or "").upper()
    return any(
        token in tour_name
        for token in (
            "AUSTRALIAN OPEN",
            "ROLAND GARROS",
            "WIMBLEDON",
            "US OPEN",
            "GRAND SLAM",
        )
    )


def _is_best_of_five_match(tour_meta: dict | None, round_id: int | None) -> bool:
    """ATP Slam main draws are BO5; qualifying rounds remain BO3."""
    try:
        round_number = int(round_id or 0)
    except (TypeError, ValueError):
        round_number = 0
    return _is_grand_slam_event(tour_meta) and round_number >= 4


def _shape_cover_probabilities(
    p_a: float,
    p_b: float,
    line: float,
    best_of: str,
) -> tuple[float, float, float]:
    """Return push-conditional P1/P2 prices and the explicit push mass."""
    p1_win, p_push, p1_loss = cover_probs(
        match_margin_pmf(p_a, p_b, best_of),
        line,
    )
    non_push = p1_win + p1_loss
    if non_push <= 1e-12:
        return 0.5, 0.5, p_push
    return p1_win / non_push, p1_loss / non_push, p_push


def _parse_point_prob(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    if not (0.0 < v < 1.0):
        return None
    return v


def _court_to_surface(court_name: str | None) -> str:
    if not court_name:
        return "N/A"
    c = court_name.upper()
    if "CLAY" in c or "TERRE" in c:
        return "Clay"
    if "GRASS" in c:
        return "Grass"
    if "INDOOR" in c and "HARD" in c:
        return "I.hard"
    if "HARD" in c or "DECOTURF" in c or "ACRYLIC" in c:
        return "Hard"
    return "N/A"


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _logit(p: float) -> float:
    q = _clamp(p, 1e-6, 1.0 - 1e-6)
    return math.log(q / (1.0 - q))


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _calibrate_prob(raw_prob: float, cfg: HandicapCalibration) -> float:
    if not cfg.enabled:
        return _clamp(raw_prob, 1e-6, 1.0 - 1e-6)
    return _clamp(_sigmoid(cfg.platt_a + cfg.platt_b * _logit(raw_prob)), 1e-6, 1.0 - 1e-6)


def load_env():
    root = _root_dir()
    for name in ["env.local", ".env.local"]:
        path = os.path.join(root, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip().replace("\r", "")
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        os.environ[k.strip()] = v


import unicodedata
import re


def _norm(s: str) -> str:
    """Lowercase, strip accents, hyphens, apostrophes (align with API matchPinnacle)."""
    if not s:
        return ""
    t = (s or "").strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("-", "").replace("'", "")
    return t


def _tokenise_name(name: str) -> list[str]:
    """Split name into tokens, drop initials (align with API)."""
    cleaned = (name or "").replace(",", " ").replace("-", " ")
    cleaned = re.sub(r"\s*\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\s*\[[^\]]*\]", " ", cleaned)
    tokens = [_norm(t) for t in cleaned.split() if t and not re.match(r"^[a-z]$", _norm(t))]
    return tokens


def _surname_keys(name: str) -> list[str]:
    """Multi-key surname set for hyphen/compound variants (align with API normaliseSurnameKeys)."""
    t = _tokenise_name(name)
    if not t:
        return []
    out = set()
    n = len(t)
    out.add(t[-1])
    if n >= 2:
        out.add(t[-2])
        out.add(f"{t[-2]} {t[-1]}")
        out.add(f"{t[-2]}{t[-1]}")
    return list(out)


def _make_pair_keys(a: str, b: str) -> list[str]:
    """Pair keys for lookup (align with API makePairKeys)."""
    a_keys = _surname_keys(a)
    b_keys = _surname_keys(b)
    out = set()
    for ka in a_keys:
        for kb in b_keys:
            out.add(f"{ka}|{kb}")
    return list(out)


def _first_word(name: str) -> str:
    t = _tokenise_name(name)
    return t[0] if t else ""


def _full_name(name: str) -> str:
    return " ".join(_tokenise_name(name))


def _match_fair_to_pinnacle(
    fair_rows: list[dict],
    pin_with_spread: list[dict],
) -> list[dict]:
    """
    Match fair-odds rows to Pinnacle spread rows using same logic as API matchPinnacle.
    Returns list of {"fair": fo, "pinnacle": pin, "pin_reversed_for_fair": bool}.
    pin_reversed_for_fair=True means our player1 maps to Pinnacle player2.
    """
    pin_lookup: dict[str, list[tuple[dict, bool]]] = {}
    for pin in pin_with_spread:
        p1 = (pin.get("player1_name") or "").strip()
        p2 = (pin.get("player2_name") or "").strip()
        for key in _make_pair_keys(p1, p2):
            pin_lookup.setdefault(key, []).append((pin, False))
        for key in _make_pair_keys(p2, p1):
            pin_lookup.setdefault(key, []).append((pin, True))

    matched: list[dict] = []
    used_pin_keys: set[tuple[str, str]] = set()

    for fo in fair_rows:
        p1_our = (fo.get("p1_name") or "").strip()
        p2_our = (fo.get("p2_name") or "").strip()
        pair_keys = _make_pair_keys(p1_our, p2_our)

        candidates: dict[str, tuple[dict, bool, int]] = {}
        for key in pair_keys:
            for pin, rev in pin_lookup.get(key, []):
                pk = (pin.get("player1_name") or "", pin.get("player2_name") or "")
                id_ = f"{pk[0]}|{pk[1]}|{'R' if rev else 'N'}"
                if id_ in candidates:
                    candidates[id_] = (candidates[id_][0], candidates[id_][1], candidates[id_][2] + 1)
                else:
                    candidates[id_] = (pin, rev, 1)

        if not candidates:
            continue

        fo_p1_first = _first_word(p1_our)
        fo_p2_first = _first_word(p2_our)
        fo_p1_full = _full_name(p1_our)
        fo_p2_full = _full_name(p2_our)

        for id_, (pin, rev, score) in list(candidates.items()):
            pin_p1 = (pin.get("player2_name") if rev else pin.get("player1_name")) or ""
            pin_p2 = (pin.get("player1_name") if rev else pin.get("player2_name")) or ""
            if fo_p1_first and fo_p1_first == _first_word(pin_p1):
                score += 2
            if fo_p2_first and fo_p2_first == _first_word(pin_p2):
                score += 2
            if fo_p1_full and fo_p1_full == _full_name(pin_p1):
                score += 4
            if fo_p2_full and fo_p2_full == _full_name(pin_p2):
                score += 4
            candidates[id_] = (pin, rev, score)

        ranked = [
            (pin, rev, score)
            for (pin, rev, score) in sorted(candidates.values(), key=lambda x: -x[2])
            if (pin.get("player1_name"), pin.get("player2_name")) not in used_pin_keys
        ]
        if not ranked:
            continue
        if len(ranked) > 1 and ranked[0][2] == ranked[1][2]:
            continue
        pin, pin_reversed_for_fair, _ = ranked[0]
        used_pin_keys.add((pin.get("player1_name"), pin.get("player2_name")))
        matched.append({"fair": fo, "pinnacle": pin, "pin_reversed_for_fair": pin_reversed_for_fair})

    return matched


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Compute daily handicap values from Pinnacle spread odds.")
    ap.add_argument("--date", default=None, help="Capture date (UTC) as YYYY-MM-DD. Defaults to today.")
    ap.add_argument("--dry-run", action="store_true", help="Compute and print stats without DB updates.")
    ap.add_argument(
        "--calibration-file",
        default=None,
        help="Path to handicap calibration JSON. Defaults to env HANDICAP_CALIBRATION_FILE or data/backtest/spread-v1-calibration-params.json.",
    )
    ap.add_argument(
        "--disable-calibration",
        action="store_true",
        help="Disable handicap calibration (raw probabilities only).",
    )
    ap.add_argument(
        "--bo5-only",
        action="store_true",
        help="Update ATP Grand Slam best-of-five rows only; leave BO3 rows unchanged.",
    )
    ap.add_argument(
        "--allow-bo5",
        action="store_true",
        help="Enable BO5 handicap calculations for the zero-stake evidence lane.",
    )
    return ap.parse_args()


def _parse_calibration_payload(payload: dict) -> tuple[float, float, float] | None:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
    if usage:
        try:
            return (
                float(usage.get("HANDICAP_LINE_SHIFT")),
                float(usage.get("HANDICAP_PLATT_A")),
                float(usage.get("HANDICAP_PLATT_B")),
            )
        except (TypeError, ValueError):
            pass
    best = payload.get("best") if isinstance(payload.get("best"), dict) else None
    if best:
        try:
            return (
                float(best.get("line_shift")),
                float(best.get("platt_a")),
                float(best.get("platt_b")),
            )
        except (TypeError, ValueError):
            pass
    return None


def load_handicap_calibration(args: argparse.Namespace) -> HandicapCalibration:
    if args.disable_calibration:
        return HandicapCalibration(False, 0.0, 0.0, 1.0, "disabled-by-flag", None)

    mode = (os.environ.get("HANDICAP_CALIBRATION_MODE") or "auto").strip().lower()
    if mode in {"off", "false", "0", "none"}:
        return HandicapCalibration(False, 0.0, 0.0, 1.0, "disabled-by-env", None)

    default_path = os.path.join(_root_dir(), "data", "backtest", "spread-v1-calibration-params.json")
    cal_path = (
        args.calibration_file
        or os.environ.get("HANDICAP_CALIBRATION_FILE")
        or default_path
    )

    if not os.path.exists(cal_path):
        if mode in {"force", "on", "required"}:
            raise FileNotFoundError(f"Calibration file not found: {cal_path}")
        return HandicapCalibration(False, 0.0, 0.0, 1.0, f"missing:{cal_path}", None)

    with open(cal_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if mode == "auto" and isinstance(payload, dict) and payload.get("calibration_valid") is False:
        reason = str(payload.get("calibration_reason") or "invalid-calibration")
        if _env_bool("SPREAD_V1_ENABLE_CORRECTION_ONLY", False):
            return HandicapCalibration(False, 0.0, 0.0, 1.0, reason, payload)
        # Correction-only mode created ML/handicap contradictions; keep it opt-in only.
        return HandicapCalibration(False, 0.0, 0.0, 1.0, reason, None)

    parsed = _parse_calibration_payload(payload)
    if parsed is None:
        if mode in {"force", "on", "required"}:
            raise ValueError(f"Calibration file missing required params: {cal_path}")
        return HandicapCalibration(False, 0.0, 0.0, 1.0, f"invalid:{cal_path}", None)

    if mode == "auto":
        line_source = str(payload.get("line_source_used") or "").strip().lower()
        usable_scope = payload.get("usable_scope") if isinstance(payload.get("usable_scope"), dict) else {}
        surfaces = {str(item).strip() for item in usable_scope.get("surfaces") or [] if str(item).strip()}
        leagues = {str(item).strip() for item in usable_scope.get("leagues") or [] if str(item).strip()}
        best_of = str(usable_scope.get("best_of") or "").strip().lower()
        if line_source != "snapshot":
            return HandicapCalibration(False, 0.0, 0.0, 1.0, f"invalid-line-source:{line_source or 'missing'}", payload if _env_bool("SPREAD_V1_ENABLE_CORRECTION_ONLY", False) and isinstance(payload, dict) else None)
        if best_of != "bo3":
            return HandicapCalibration(False, 0.0, 0.0, 1.0, f"invalid-best-of:{best_of or 'missing'}", payload if _env_bool("SPREAD_V1_ENABLE_CORRECTION_ONLY", False) and isinstance(payload, dict) else None)
        if "ATP" not in leagues:
            return HandicapCalibration(False, 0.0, 0.0, 1.0, "invalid-leagues", payload if _env_bool("SPREAD_V1_ENABLE_CORRECTION_ONLY", False) and isinstance(payload, dict) else None)
        if not {"Hard", "Clay"}.issubset(surfaces):
            return HandicapCalibration(False, 0.0, 0.0, 1.0, "invalid-surfaces", payload if _env_bool("SPREAD_V1_ENABLE_CORRECTION_ONLY", False) and isinstance(payload, dict) else None)

    line_shift, platt_a, platt_b = parsed
    return HandicapCalibration(True, line_shift, platt_a, platt_b, cal_path, payload if isinstance(payload, dict) else None)


def summarize_edges(label: str, edges: list[float]) -> None:
    if not edges:
        print(f"  {label}: n=0")
        return
    sorted_edges = sorted(edges)
    p10 = sorted_edges[max(0, int(0.10 * len(sorted_edges)) - 1)]
    p90 = sorted_edges[min(len(sorted_edges) - 1, int(0.90 * len(sorted_edges)))]
    gt10 = sum(1 for e in edges if e >= 10.0)
    gt20 = sum(1 for e in edges if e >= 20.0)
    print(
        f"  {label}: n={len(edges)} mean={mean(edges):+.2f}% median={median(edges):+.2f}% "
        f"p10={p10:+.2f}% p90={p90:+.2f}% >=10%={gt10/len(edges):.1%} >=20%={gt20/len(edges):.1%}"
    )


def resolve_capture_date(base_url: str, headers: dict[str, str], explicit_date: str | None) -> str:
    if explicit_date:
        return explicit_date

    import requests

    fallback = datetime.now(timezone.utc).date().isoformat()
    try:
        resp = requests.get(
            f"{base_url}/rest/v1/bookmaker_odds_snapshot",
            headers=headers,
            params={
                "select": "capture_date,captured_at",
                "bookmaker": "eq.Pinnacle",
                "league": "in.(ATP,Challenger)",
                "order": "captured_at.desc",
                "limit": 1,
            },
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows:
            latest = (rows[0].get("capture_date") or "").strip()
            if latest:
                return latest
    except Exception:
        pass
    return fallback


def main():
    load_env()
    import requests

    args = parse_args()
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local")
        sys.exit(1)
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    capture_date = resolve_capture_date(url, headers, args.date)
    calibration = load_handicap_calibration(args)
    if calibration.enabled:
        print(
            "Handicap calibration: ON "
            f"(legacy shift ignored, a={calibration.platt_a:+.4f}, b={calibration.platt_b:+.4f}) "
            f"source={calibration.source}"
        )
    else:
        correction_valid = bool((calibration.payload or {}).get("correction_valid"))
        correction_reason = str((calibration.payload or {}).get("correction_reason") or "missing")
        if correction_valid:
            print(f"Handicap calibration: OFF ({calibration.source}) | spread_v1 correction-only mode active ({correction_reason})")
        else:
            print(f"Handicap calibration: OFF ({calibration.source})")

    # 1) Load daily_fair_odds with final blended win probability + surface context
    fair_rows = _fetch_rest_paged(
        url,
        "daily_fair_odds",
        headers,
        {"select": "id,tour_id,player1_id,player2_id,p1_win_prob,p_a,p_b,surface"},
        timeout=30,
    )
    if not fair_rows:
        print("No rows in daily_fair_odds. Run oncourt-compute-fair-odds.py first.")
        sys.exit(1)

    try:
        today_rows = _fetch_rest_paged(
            url,
            "oncourt_today",
            headers,
            {
                "select": "tour_id,round_id,player1_id,player2_id,result",
                "order": "tour_id.asc,round_id.asc,draw.asc,player1_id.asc,player2_id.asc",
            },
            timeout=30,
        )
        open_pair_keys: set[tuple[int, int, int]] = set()
        round_by_pair: dict[tuple[int, int, int], int | None] = {}
        for today_row in today_rows:
            if str(today_row.get("result") or "").strip():
                continue
            try:
                tid = int(today_row["tour_id"])
                p1 = int(today_row["player1_id"])
                p2 = int(today_row["player2_id"])
            except (KeyError, TypeError, ValueError):
                continue
            try:
                round_id = int(today_row.get("round_id"))
            except (TypeError, ValueError):
                round_id = None
            open_pair_keys.add((tid, p1, p2))
            open_pair_keys.add((tid, p2, p1))
            round_by_pair[(tid, p1, p2)] = round_id
            round_by_pair[(tid, p2, p1)] = round_id
        if open_pair_keys:
            before = len(fair_rows)
            fair_rows = [
                row
                for row in fair_rows
                if (
                    row.get("tour_id") is not None
                    and row.get("player1_id") is not None
                    and row.get("player2_id") is not None
                    and (
                        int(row["tour_id"]),
                        int(row["player1_id"]),
                        int(row["player2_id"]),
                    )
                    in open_pair_keys
                )
            ]
            for row in fair_rows:
                row["round_id"] = round_by_pair.get(
                    (
                        int(row["tour_id"]),
                        int(row["player1_id"]),
                        int(row["player2_id"]),
                    )
                )
            print(f"Filtered daily_fair_odds to open OnCourt rows: {len(fair_rows)}/{before}")
    except Exception as exc:
        round_by_pair = {}
        print(f"WARNING: oncourt_today open-row filter skipped: {exc}")

    player_ids = set()
    tour_ids = set()
    for row in fair_rows:
        if row.get("player1_id") is not None:
            player_ids.add(row["player1_id"])
        if row.get("player2_id") is not None:
            player_ids.add(row["player2_id"])
        if row.get("tour_id") is not None:
            tour_ids.add(int(row["tour_id"]))
    player_ids = list(player_ids)
    players = {}
    for i in range(0, len(player_ids), 100):
        chunk = player_ids[i : i + 100]
        r2 = requests.get(
            f"{url}/rest/v1/oncourt_players",
            headers=headers,
            params={"id": "in.(" + ",".join(str(x) for x in chunk) + ")", "select": "id,name"},
            timeout=30,
        )
        if r2.status_code == 200:
            for p in r2.json():
                players[p["id"]] = (p.get("name") or "").strip()

    for row in fair_rows:
        row["p1_name"] = players.get(row.get("player1_id"), "")
        row["p2_name"] = players.get(row.get("player2_id"), "")

    league_avg_by_surface = dict(SURFACE_LEAGUE_AVG)
    try:
        r = requests.get(
            f"{url}/rest/v1/surface_league_averages",
            headers=headers,
            params={"select": "surface,serve_point_win_pct", "limit": 20},
            timeout=30,
        )
        r.raise_for_status()
        for row in r.json():
            surf = (row.get("surface") or "N/A").strip() or "N/A"
            pct = row.get("serve_point_win_pct")
            if pct is None:
                continue
            try:
                league_avg_by_surface[surf] = float(pct)
            except (TypeError, ValueError):
                continue
    except Exception:
        pass

    tour_meta: dict[int, dict] = {}
    if tour_ids:
        for chunk in _chunked(sorted(tour_ids), 200):
            r = requests.get(
                f"{url}/rest/v1/oncourt_tours",
                headers=headers,
                params={
                    "id": "in.(" + ",".join(str(x) for x in chunk) + ")",
                    "select": "id,name,rank,court_id",
                    "limit": len(chunk),
                },
                timeout=30,
            )
            r.raise_for_status()
            for row in r.json():
                if row.get("id") is None:
                    continue
                tour_meta[int(row["id"])] = row

    court_ids = sorted(
        {
            int(meta["court_id"])
            for meta in tour_meta.values()
            if meta.get("court_id") is not None
        }
    )
    courts: dict[int, str] = {}
    if court_ids:
        for chunk in _chunked(court_ids, 200):
            r = requests.get(
                f"{url}/rest/v1/oncourt_courts",
                headers=headers,
                params={
                    "id": "in.(" + ",".join(str(x) for x in chunk) + ")",
                    "select": "id,name",
                    "limit": len(chunk),
                },
                timeout=30,
            )
            r.raise_for_status()
            for row in r.json():
                if row.get("id") is None:
                    continue
                courts[int(row["id"])] = (row.get("name") or "").strip()

    venue_serve_lookup: dict[tuple[int, str], float] = {}
    if tour_ids:
        for chunk in _chunked(sorted(tour_ids), 200):
            r = requests.get(
                f"{url}/rest/v1/tournament_serve_profile",
                headers=headers,
                params={
                    "tour_id": "in.(" + ",".join(str(x) for x in chunk) + ")",
                    "select": "tour_id,surface,venue_avg_spw,match_count",
                    "limit": 500,
                },
                timeout=30,
            )
            r.raise_for_status()
            for row in r.json():
                tid = row.get("tour_id")
                surf = (row.get("surface") or "N/A").strip() or "N/A"
                spw = row.get("venue_avg_spw")
                n = int(row.get("match_count") or 0)
                if tid is None or spw is None or n < MIN_VENUE_SPW_MATCHES:
                    continue
                try:
                    venue_serve_lookup[(int(tid), surf)] = float(spw)
                except (TypeError, ValueError):
                    continue

    # 2) Load Pinnacle snapshot with spread (ATP + Challenger)
    def _fetch_pin_rows(d: str):
        r = requests.get(
            f"{url}/rest/v1/bookmaker_odds_snapshot",
            headers=headers,
            params={
                "select": "player1_name,player2_name,odds1,odds2,spread_line,spread_odds1,spread_odds2,league",
                "bookmaker": "eq.Pinnacle",
                "capture_date": f"eq.{d}",
                "league": "in.(ATP,Challenger)",
                "order": "captured_at.desc",
                "limit": 500,
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    pin_rows = _fetch_pin_rows(capture_date)
    if not pin_rows:
        # Fallback: try yesterday (handles 23:55 run crossing midnight or scraper timing)
        try:
            yd = (datetime.strptime(capture_date, "%Y-%m-%d").date() - timedelta(days=1)).strftime("%Y-%m-%d")
            pin_rows = _fetch_pin_rows(yd)
            if pin_rows:
                print(f"No snapshot for {capture_date}; using {yd} (yesterday)")
        except Exception:
            pass
    if not pin_rows:
        print(f"No Pinnacle ATP/Challenger snapshot for {capture_date} (or yesterday). Run pinnacle-scrape-odds.py first.")
        sys.exit(1)

    # Filter for rows with spread
    pin_with_spread = [p for p in pin_rows if p.get("spread_line") is not None and p.get("spread_odds1") and p.get("spread_odds2")]
    if not pin_with_spread:
        print(f"No Pinnacle spread data for {capture_date}. Ensure spread columns exist (docs/supabase-bookmaker-spread-columns.sql)")
        sys.exit(1)

    # 3) Match using same logic as API matchPinnacle (surname keys, first name, full name)
    matched = _match_fair_to_pinnacle(fair_rows, pin_with_spread)
    print(f"Matched {len(matched)} of {len(fair_rows)} fair-odds rows to Pinnacle spread")

    updated = 0
    edge_raw_p1: list[float] = []
    edge_cal_p1: list[float] = []
    edge_cal_p2: list[float] = []
    implied_match_old: list[float] = []
    implied_match_new: list[float] = []
    used_stored_point_probs = 0
    fallback_solved_point_probs = 0
    fallback_divergent_point_probs = 0
    correction_reason_counts: Counter[str] = Counter()
    correction_applied = 0
    correction_sign_flip_guarded = 0
    bo5_suppressed = 0
    push_masses: list[float] = []
    for m in matched:
        fo, pin, pin_reversed_for_fair = m["fair"], m["pinnacle"], m["pin_reversed_for_fair"]
        p1_win_prob = float(fo.get("p1_win_prob") or 0.0)
        surface = (fo.get("surface") or "").strip() or "N/A"
        tid = fo.get("tour_id")
        meta = tour_meta.get(int(tid)) if tid is not None and int(tid) in tour_meta else None
        round_id = fo.get("round_id")
        is_bo5 = _is_best_of_five_match(meta, round_id)
        best_of = "bo5" if is_bo5 else "bo3"
        slam_format_unknown = (
            _is_grand_slam_event(meta)
            and round_id in (None, "")
        )
        if args.bo5_only and not is_bo5:
            continue
        if (
            (is_bo5 or slam_format_unknown)
            and not (args.allow_bo5 or _env_bool("SPREAD_V1_ALLOW_BO5", False))
        ):
            # The BO5 mathematics is now correct, but it has not passed a
            # real-price holdout. Remove stale edges rather than publishing it.
            patch = {
                "spread_line": None,
                "spread_odds1": None,
                "spread_odds2": None,
                "handicap_edge_p1": None,
                "handicap_edge_p2": None,
            }
            if args.dry_run:
                bo5_suppressed += 1
            else:
                resp = requests.patch(
                    f"{url}/rest/v1/daily_fair_odds?id=eq.{fo['id']}",
                    headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json=patch,
                    timeout=10,
                )
                if resp.ok:
                    bo5_suppressed += 1
            continue
        if surface == "N/A" and tid is not None:
            court_name = courts.get(int(meta["court_id"])) if meta and meta.get("court_id") is not None else ""
            surface = _court_to_surface(court_name)
        avg_spw_surface = league_avg_by_surface.get(surface, SURFACE_LEAGUE_AVG.get(surface, SURFACE_LEAGUE_AVG["N/A"]))
        if tid is not None:
            avg_spw_surface = venue_serve_lookup.get((int(tid), surface), avg_spw_surface)
        p_a_old = _parse_point_prob(fo.get("p_a"))
        p_b_old = _parse_point_prob(fo.get("p_b"))
        if p_a_old is not None and p_b_old is not None:
            implied_from_stored = match_win_probability(p_a_old, p_b_old, best_of)
            implied_match_old.append(implied_from_stored)
            if abs(implied_from_stored - p1_win_prob) <= POINT_PROB_MATCH_PROB_GAP_MAX:
                p_a, p_b = p_a_old, p_b_old
                used_stored_point_probs += 1
            else:
                p_a, p_b = _solve_spw_for_match_prob(p1_win_prob, avg_spw_surface, best_of)
                fallback_solved_point_probs += 1
                fallback_divergent_point_probs += 1
        else:
            p_a, p_b = _solve_spw_for_match_prob(p1_win_prob, avg_spw_surface, best_of)
            fallback_solved_point_probs += 1
        implied_match_new.append(match_win_probability(p_a, p_b, best_of))
        pin_line = float(pin.get("spread_line") or 0.0)

        # Snapshot semantics (after scrape normalization):
        #   spread_line: signed handicap for snapshot player1
        #   spread_odds1: odds for snapshot player1 at spread_line
        #   spread_odds2: odds for snapshot player2 at -spread_line
        #
        # Convert into OUR row orientation:
        #   spread_line := signed handicap for OUR player1
        #   spread_odds1 := odds for OUR player1 at spread_line
        #   spread_odds2 := odds for OUR player2 at -spread_line
        pin_o1 = float(pin.get("spread_odds1") or 0)
        pin_o2 = float(pin.get("spread_odds2") or 0)
        if pin_reversed_for_fair:
            line = -pin_line
            spread_odds1 = pin_o2
            spread_odds2 = pin_o1
            pin_ml_odds1 = float(pin.get("odds2") or 0)
            pin_ml_odds2 = float(pin.get("odds1") or 0)
        else:
            line = pin_line
            spread_odds1 = pin_o1
            spread_odds2 = pin_o2
            pin_ml_odds1 = float(pin.get("odds1") or 0)
            pin_ml_odds2 = float(pin.get("odds2") or 0)

        if spread_odds1 <= 1 or spread_odds2 <= 1:
            continue
        if pin_ml_odds1 > 1 and pin_ml_odds2 > 1:
            pin_inv1 = 1.0 / pin_ml_odds1
            pin_inv2 = 1.0 / pin_ml_odds2
            pin_p1_no_vig = pin_inv1 / (pin_inv1 + pin_inv2)
            model_fav_side = "P1" if p1_win_prob >= 0.5 else "P2"
            pin_fav_side = "P1" if pin_p1_no_vig >= 0.5 else "P2"
            model_market_fav_gap = abs(max(p1_win_prob, 1.0 - p1_win_prob) - max(pin_p1_no_vig, 1.0 - pin_p1_no_vig))
            model_market_side_flip = (
                model_fav_side != pin_fav_side
                and abs(pin_p1_no_vig - 0.5) >= MODEL_MARKET_FAV_SIDE_FLIP_BUFFER
                and abs(p1_win_prob - 0.5) >= MODEL_MARKET_FAV_SIDE_FLIP_BUFFER
            )
            if (
                model_market_fav_gap > MODEL_MARKET_FAV_PROB_GAP_MAX or model_market_side_flip
            ) and not args.bo5_only:
                continue

        # Signed line from OUR P1 perspective:
        #   +x => P1 +x
        #   -x => P1 -x
        model_p1_raw, raw_model_p2, push_mass = _shape_cover_probabilities(
            p_a,
            p_b,
            line,
            best_of,
        )
        push_masses.append(push_mass)

        implied1 = 1.0 / spread_odds1
        implied2 = 1.0 / spread_odds2
        raw_edge1 = (model_p1_raw - implied1) / implied1 * 100 if implied1 > 0 else None
        raw_edge2 = (raw_model_p2 - implied2) / implied2 * 100 if implied2 > 0 else None

        # The old universal +0.5 line shift hid the integer-push bug and is no
        # longer part of pricing. Calibrate both non-push sides symmetrically.
        calibrated_p1 = _calibrate_prob(model_p1_raw, calibration)
        calibrated_p2 = _calibrate_prob(raw_model_p2, calibration)
        calibrated_total = calibrated_p1 + calibrated_p2
        model_p1_base = calibrated_p1 / calibrated_total
        model_p1, correction_reason = apply_correction(
            calibration.payload,
            base_prob=model_p1_base,
            surface=surface,
            line=line,
            p1_match_prob=p1_win_prob,
            odds1=spread_odds1,
            odds2=spread_odds2,
            league=str(pin.get("league") or "").strip() or None,
            best_of=best_of,
        )
        model_p2 = _clamp(1.0 - model_p1, 1e-6, 1.0 - 1e-6)
        edge1 = (model_p1 - implied1) / implied1 * 100 if implied1 > 0 else None
        edge2 = (model_p2 - implied2) / implied2 * 100 if implied2 > 0 else None

        sign_flip_guarded = (
            not _env_bool("SPREAD_V1_ALLOW_CORRECTION_SIGN_FLIP", False)
            and (
                (raw_edge1 is not None and edge1 is not None and raw_edge1 <= 0.0 < edge1)
                or (raw_edge2 is not None and edge2 is not None and raw_edge2 <= 0.0 < edge2)
            )
        )
        if sign_flip_guarded:
            # A calibration/correction layer may dampen or resize an existing edge,
            # but it must not invent an opposite-side handicap pick against the raw model.
            model_p1 = model_p1_raw
            model_p2 = raw_model_p2
            edge1 = raw_edge1
            edge2 = raw_edge2
            correction_reason = "sign-flip-guard"
            correction_sign_flip_guarded += 1

        if correction_reason == "ok":
            correction_applied += 1
        else:
            correction_reason_counts[correction_reason] += 1

        if raw_edge1 is not None:
            edge_raw_p1.append(raw_edge1)
        if edge1 is not None:
            edge_cal_p1.append(edge1)
        if edge2 is not None:
            edge_cal_p2.append(edge2)

        patch = {
            "spread_line": line,
            "spread_odds1": spread_odds1,
            "spread_odds2": spread_odds2,
            "handicap_edge_p1": round(edge1, 2) if edge1 is not None else None,
            "handicap_edge_p2": round(edge2, 2) if edge2 is not None else None,
        }
        if args.dry_run:
            updated += 1
        else:
            resp = requests.patch(
                f"{url}/rest/v1/daily_fair_odds?id=eq.{fo['id']}",
                headers={**headers, "Content-Type": "application/json", "Prefer": "return=minimal"},
                json=patch,
                timeout=10,
            )
            if resp.ok:
                updated += 1

    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} {updated} rows with spread + handicap edge")
    if implied_match_new:
        print(
            "Handicap input implied match prob: "
            f"rebuilt mean={mean(implied_match_new):.4f}"
            + (
                f" vs stored reference mean={mean(implied_match_old):.4f}"
                if implied_match_old
                else ""
            )
        )
    print(
        "Point-probability source: "
        f"stored_p_a_p_b={used_stored_point_probs} "
        f"fallback_reverse_solve={fallback_solved_point_probs} "
        f"fallback_divergent_gap={fallback_divergent_point_probs}"
    )
    if bo5_suppressed:
        print(
            "BO5 spread rows suppressed pending real-price validation: "
            f"{bo5_suppressed}"
        )
    if push_masses:
        print(
            "Explicit push mass: "
            f"mean={mean(push_masses):.3%} max={max(push_masses):.3%} "
            f"integer_rows={sum(1 for value in push_masses if value > 1e-12)}"
        )
    print("Edge diagnostics (P1 +line):")
    summarize_edges("raw", edge_raw_p1)
    summarize_edges("cal", edge_cal_p1)
    print("Edge diagnostics (P2 -line, calibrated):")
    summarize_edges("cal", edge_cal_p2)
    if calibration.payload is not None:
        if correction_sign_flip_guarded:
            print(f"Correction sign-flip guard: guarded={correction_sign_flip_guarded}")
        print(
            "Spread v1 correction layer: "
            f"applied={correction_applied} "
            + (
                "fallbacks=" + ", ".join(f"{reason}:{count}" for reason, count in correction_reason_counts.most_common())
                if correction_reason_counts
                else "fallbacks=none"
            )
        )
    print("Done.")


if __name__ == "__main__":
    main()
