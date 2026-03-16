"""
Strict policy report for today's signals.

Default behavior (production mode = base):
- Uses strict policy (Hard|Masters 1000, confidence high, value >= 10% public / 5% internal)
- Optionally appends to data/backtest/strict-signals.csv

Overlay behavior (production mode = overlay):
- Applies tournament side-policy overlay from tournament-segment-roi.csv
  after strict policy/value filtering

Side-by-side tracking:
- Use --compare-overlay to evaluate both base and overlay in one run
- Optionally append comparison rows to a separate CSV (default:
  data/backtest/strict-signals-overlay-compare.csv)

Usage:
  python scripts/strict-policy-report.py
  python scripts/strict-policy-report.py --append
  python scripts/strict-policy-report.py --policy-mode overlay --append
  python scripts/strict-policy-report.py --compare-overlay --append
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from injury_overlay import env_bool, load_recent_injury_index


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"
DEFAULT_OUTPUT = DATA_DIR / "strict-signals.csv"
DEFAULT_INTERNAL_OUTPUT = DATA_DIR / "strict-signals-internal-5pct.csv"
DEFAULT_COMPARE_OUTPUT = DATA_DIR / "strict-signals-overlay-compare.csv"
DEFAULT_VOLUME_275_OUTPUT = DATA_DIR / "strict-signals-volume275.csv"
DEFAULT_VOLUME_275_INTERNAL_OUTPUT = DATA_DIR / "strict-signals-volume275-internal.csv"
DEFAULT_VOLUME_200_OUTPUT = DATA_DIR / "strict-signals-volume200.csv"
DEFAULT_VOLUME_200_INTERNAL_OUTPUT = DATA_DIR / "strict-signals-volume200-internal.csv"
DEFAULT_SPREAD_SHADOW_OUTPUT = DATA_DIR / "strict-signals-spreadshadow.csv"
DEFAULT_SPREAD_SHADOW_INTERNAL_OUTPUT = DATA_DIR / "strict-signals-spreadshadow-internal.csv"

STRICT_MIN_VALUE_PCT = 10.0  # Public-facing high-conviction signals
INTERNAL_TRACK_MIN_VALUE_PCT = 5.0  # Internal tracking for 200-bet confirmation
HANDICAP_MIN_EDGE_PCT = 20.0  # Handicap signal: model edge vs Pinnacle spread
SPREAD_SHADOW_MIN_EDGE_PCT = 20.0  # Separate shadow lane for handicaps outside current strict match policy
ALLOWED_SEGMENT = "Hard|Masters 1000"
ALLOWED_CONFIDENCE = {"high"}
SPREAD_SHADOW_CONFIDENCE = {"high", "medium"}
EXCLUDE_ATP500_HARD_SHORT_FAVORITES = True
EXCLUDE_SHORT_FAV_MAX_ODDS = 1.8
EXCLUDE_SHORT_FAV_CONFIDENCE = {"high"}

# Suppress signals when model and Pinnacle disagree on favourite pricing by >10pp.
# Phantom underdog edges (model 1.15 vs Pin 1.02) cause guaranteed losses.
# Skip matches where model favourite odds < 1.25.
# The model cannot price extreme mismatches — both sides are unreliable.
MISPRICE_MODEL_FAV_ODDS_MIN = 1.25

DEFAULT_OVERLAY_POLICY_FILE = DATA_DIR / "tournament-segment-roi.csv"
DEFAULT_OVERLAY_WINDOW = "prior_editions"
DEFAULT_OVERLAY_FAMILY = "seed"
DEFAULT_OVERLAY_MIN_N = 50
DEFAULT_OVERLAY_MIN_ROI_PCT = -5.0
DEFAULT_OVERLAY_MISSING_MODE = "skip"
DEFAULT_INJURY_CSV = ROOT / "data" / "injured-players-tennisexplorer.csv"
DEFAULT_STRICT_INJURY_LOOKBACK_DAYS = 14

STRICT_UNIT_GBP = float(os.environ.get("STRICT_UNIT_GBP", "100"))
MANDATORY_APPEND_FIELDS = ["stake_units", "stake_gbp", "stake_model", "signal_profile"]

# Legacy volume profile kept for comparison.
VOLUME_275_RULES: list[dict[str, Any]] = [
    {"surface": "Hard", "series": "Masters 1000", "confidence": {"high"}, "min_value_pct": 15.0},
    {"surface": "Hard", "series": "Masters 1000", "confidence": {"medium"}, "min_value_pct": 30.0},
    {"surface": "Clay", "series": "Masters 1000", "confidence": {"high"}, "min_value_pct": 20.0},
    {"surface": "Hard", "series": "Grand Slam", "confidence": {"high", "medium"}, "min_value_pct": 5.0},
    {"surface": "Grass", "series": "ATP500", "confidence": {"high", "medium"}, "min_value_pct": 10.0},
    {"surface": "Hard", "series": "ATP250", "confidence": {"high", "medium"}, "min_value_pct": 20.0},
]

# Active trimmed shadow profile: drop the weak Clay Masters slice.
VOLUME_200_RULES: list[dict[str, Any]] = [
    {"surface": "Hard", "series": "Masters 1000", "confidence": {"high"}, "min_value_pct": 15.0},
    {"surface": "Hard", "series": "Masters 1000", "confidence": {"medium"}, "min_value_pct": 30.0},
    {"surface": "Hard", "series": "Grand Slam", "confidence": {"high", "medium"}, "min_value_pct": 5.0},
    {"surface": "Grass", "series": "ATP500", "confidence": {"high", "medium"}, "min_value_pct": 10.0},
    {"surface": "Hard", "series": "ATP250", "confidence": {"high", "medium"}, "min_value_pct": 20.0},
]

SHADOW_PROFILE_RULES: dict[str, list[dict[str, Any]]] = {
    "volume_275": VOLUME_275_RULES,
    "volume_200": VOLUME_200_RULES,
}

SHADOW_PROFILE_OUTPUTS: dict[str, tuple[Path, Path]] = {
    "volume_275": (DEFAULT_VOLUME_275_OUTPUT, DEFAULT_VOLUME_275_INTERNAL_OUTPUT),
    "volume_200": (DEFAULT_VOLUME_200_OUTPUT, DEFAULT_VOLUME_200_INTERNAL_OUTPUT),
    "spread_shadow": (DEFAULT_SPREAD_SHADOW_OUTPUT, DEFAULT_SPREAD_SHADOW_INTERNAL_OUTPUT),
}

SHADOW_PROFILE_LABELS: dict[str, str] = {
    "volume_275": "Volume 275 (legacy shadow; includes Clay Masters)",
    "volume_200": "Volume 200 (trimmed shadow; no Clay Masters)",
    "spread_shadow": "Spread shadow (20%+ handicap edges; Clay + non-policy tournaments)",
}


def _append_key_value(field: str, value: Any) -> str:
    if field == "policy_mode":
        return str(value or "base").strip().lower()
    if field == "bet_type":
        return str(value or "match").strip().lower()
    if field == "signal_profile":
        return str(value or "strict").strip().lower()
    if field == "spread_line":
        txt = str(value or "").strip()
        if not txt:
            return ""
        try:
            return f"{float(txt):g}"
        except ValueError:
            return txt.lower()
    return str(value or "").strip().lower()


def load_env() -> None:
    for name in [".env.local", "env.local"]:
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip().replace("\r", "")
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def series_bucket_from_tour(tour_name: str | None, tour_rank: int | None) -> str:
    u = (tour_name or "").upper()
    if any(x in u for x in ["AUSTRALIAN OPEN", "ROLAND GARROS", "WIMBLEDON", "US OPEN", "GRAND SLAM"]):
        return "Grand Slam"
    if "MASTERS CUP" in u or "ATP FINALS" in u or "TOUR FINALS" in u:
        return "Masters Cup"
    if "MASTERS" in u or "1000" in u:
        return "Masters 1000"
    if "ATP 500" in u or "500" in u:
        return "ATP500"
    if "ATP 250" in u or "250" in u or "CHALLENGER" in u:
        return "ATP250"
    if tour_rank == 1:
        return "Grand Slam"
    if tour_rank == 3:
        return "Masters 1000"
    if tour_rank == 2:
        return "ATP500"
    return "ATP250"


def tour_key(name: str | None) -> str:
    core = (name or "").strip().lower()
    if not core:
        return ""
    core = re.sub(r"\b\d{4}\b", " ", core)
    core = re.sub(r"\b(challenger|qualifiers?|qualifying|qualification|atp|wta)\b", " ", core)
    core = re.sub(r"[^a-z0-9]+", " ", core)
    return " ".join(core.split())


def tour_key_candidates(name: str | None) -> list[str]:
    raw = (name or "").strip().lower()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    cands: list[str] = []
    # Try full name first.
    cands.append(tour_key(raw))
    # Then commonly useful sub-parts for sponsor/city naming variants.
    if parts:
        cands.append(tour_key(parts[0]))
        cands.append(tour_key(parts[-1]))
    # Optional two-part merges for names like "Foo Open - City".
    if len(parts) >= 2:
        cands.append(tour_key(f"{parts[0]} {parts[-1]}"))
    seen = set()
    out: list[str] = []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def norm_name(s: str | None) -> str:
    return (s or "").strip().lower().replace(".", "").replace("-", " ").replace(",", " ")


def tokenize(s: str | None) -> list[str]:
    return [x for x in norm_name(s).split() if len(x) > 1]


def _norm_pinnacle_name(s: str) -> str:
    if not s:
        return ""
    t = (s or "").strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("-", "").replace("'", "")
    return t


def _tokenise_pinnacle_name(name: str) -> list[str]:
    cleaned = (name or "").replace(",", " ").replace("-", " ")
    cleaned = re.sub(r"\s*\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\s*\[[^\]]*\]", " ", cleaned)
    return [
        _norm_pinnacle_name(t)
        for t in cleaned.split()
        if t and not re.match(r"^[a-z]$", _norm_pinnacle_name(t))
    ]


def _surname_keys(name: str) -> list[str]:
    t = _tokenise_pinnacle_name(name)
    if not t:
        return []
    out = set()
    n = len(t)
    out.add(t[n - 1])
    if n >= 2:
        out.add(t[n - 2])
        out.add(f"{t[n - 2]} {t[n - 1]}")
        out.add(f"{t[n - 2]}{t[n - 1]}")
    return list(out)


def _make_pair_keys(a: str, b: str) -> list[str]:
    a_keys = _surname_keys(a)
    b_keys = _surname_keys(b)
    out = set()
    for ka in a_keys:
        for kb in b_keys:
            out.add(f"{ka}|{kb}")
    return list(out)


def _first_word(name: str) -> str:
    t = _tokenise_pinnacle_name(name)
    return t[0] if t else ""


def _full_name(name: str) -> str:
    return " ".join(_tokenise_pinnacle_name(name))


def _is_doubles_name(name: str | None) -> bool:
    return "/" in (name or "") or "&" in (name or "")


def match_pinnacle_rows(
    fair_rows: list[dict[str, Any]],
    pin_rows: list[dict[str, Any]],
) -> dict[int, dict[str, float]]:
    pin_lookup: dict[str, list[tuple[dict[str, Any], bool]]] = {}
    for pin in pin_rows:
        p1 = (pin.get("player1_name") or "").strip()
        p2 = (pin.get("player2_name") or "").strip()
        if _is_doubles_name(p1) or _is_doubles_name(p2):
            continue
        for key in _make_pair_keys(p1, p2):
            pin_lookup.setdefault(key, []).append((pin, False))
        for key in _make_pair_keys(p2, p1):
            pin_lookup.setdefault(key, []).append((pin, True))

    matched: dict[int, dict[str, float]] = {}
    used_pin_keys: set[tuple[str, str]] = set()

    for fo in fair_rows:
        fo_id = fo.get("id")
        if fo_id is None:
            continue
        p1 = (fo.get("p1_name") or "").strip()
        p2 = (fo.get("p2_name") or "").strip()
        if _is_doubles_name(p1) or _is_doubles_name(p2):
            continue

        candidate_map: dict[str, tuple[dict[str, Any], bool, int]] = {}
        for key in _make_pair_keys(p1, p2):
            for pin, reversed_for_fair in pin_lookup.get(key, []):
                ident = f"{pin.get('player1_name','')}|{pin.get('player2_name','')}|{'R' if reversed_for_fair else 'N'}"
                if ident in candidate_map:
                    existing = candidate_map[ident]
                    candidate_map[ident] = (existing[0], existing[1], existing[2] + 1)
                else:
                    candidate_map[ident] = (pin, reversed_for_fair, 1)

        if not candidate_map:
            continue

        fo_p1_first = _first_word(p1)
        fo_p2_first = _first_word(p2)
        fo_p1_full = _full_name(p1)
        fo_p2_full = _full_name(p2)

        for ident, (pin, reversed_for_fair, score) in list(candidate_map.items()):
            pin_p1 = (pin.get("player2_name") if reversed_for_fair else pin.get("player1_name")) or ""
            pin_p2 = (pin.get("player1_name") if reversed_for_fair else pin.get("player2_name")) or ""
            if fo_p1_first and fo_p1_first == _first_word(pin_p1):
                score += 2
            if fo_p2_first and fo_p2_first == _first_word(pin_p2):
                score += 2
            if fo_p1_full and fo_p1_full == _full_name(pin_p1):
                score += 4
            if fo_p2_full and fo_p2_full == _full_name(pin_p2):
                score += 4
            candidate_map[ident] = (pin, reversed_for_fair, score)

        ranked = [
            (pin, reversed_for_fair, score)
            for (pin, reversed_for_fair, score) in sorted(candidate_map.values(), key=lambda x: -x[2])
            if ((pin.get("player1_name") or ""), (pin.get("player2_name") or "")) not in used_pin_keys
        ]
        if not ranked:
            continue
        if len(ranked) > 1 and ranked[0][2] == ranked[1][2]:
            continue

        pin, reversed_for_fair, _ = ranked[0]
        used_pin_keys.add(((pin.get("player1_name") or ""), (pin.get("player2_name") or "")))
        o1 = pin.get("odds1")
        o2 = pin.get("odds2")
        if o1 is None or o2 is None:
            continue
        matched[int(fo_id)] = (
            {"odds1": float(o2), "odds2": float(o1)}
            if reversed_for_fair
            else {"odds1": float(o1), "odds2": float(o2)}
        )

    return matched


def is_excluded_short_favorite(surface: str, series_bucket: str, confidence: str, our_odds1: float, our_odds2: float) -> bool:
    if not EXCLUDE_ATP500_HARD_SHORT_FAVORITES:
        return False
    if surface != "Hard" or series_bucket != "ATP500":
        return False
    if confidence not in EXCLUDE_SHORT_FAV_CONFIDENCE:
        return False
    return min(our_odds1, our_odds2) < EXCLUDE_SHORT_FAV_MAX_ODDS


def strict_min_value_for(surface: str, series_bucket: str, confidence: str) -> float | None:
    segment_key = f"{surface}|{series_bucket}"
    if segment_key != ALLOWED_SEGMENT:
        return None
    if confidence not in ALLOWED_CONFIDENCE:
        return None
    return INTERNAL_TRACK_MIN_VALUE_PCT


def shadow_profile_min_value_for(profile_name: str, surface: str, series_bucket: str, confidence: str) -> float | None:
    vals: list[float] = []
    for rule in SHADOW_PROFILE_RULES.get(profile_name, []):
        if surface != rule["surface"] or series_bucket != rule["series"]:
            continue
        if confidence not in rule["confidence"]:
            continue
        vals.append(float(rule["min_value_pct"]))
    if not vals:
        return None
    return min(vals)


def spread_shadow_reason_for(surface: str, series_bucket: str, confidence: str) -> str | None:
    conf = (confidence or "").strip().lower()
    if conf not in SPREAD_SHADOW_CONFIDENCE:
        return None

    in_strict_match_segment = strict_min_value_for(surface, series_bucket, conf) is not None
    is_clay = surface == "Clay"
    if is_clay and not in_strict_match_segment:
        return "clay_non_policy"
    if is_clay:
        return "clay"
    if not in_strict_match_segment:
        return "non_policy"
    return None


def compute_stake_units(
    *,
    our_odds1: float,
    our_odds2: float,
    pin_odds1: float,
    pin_odds2: float,
    side: str,
    bet_type: str,
    value_pct: float | None = None,
) -> tuple[float, float, str]:
    """
    Compute stake units and GBP amount.
    - Match bets: value_tiered (5–10%→0.5u, 10–15%→1u, 15–20%→1.5u, 20%+→2u).
    - Spread bets: flat 1u.
    """
    if (bet_type or "").strip().lower() == "spread":
        return 1.0, 1.0 * STRICT_UNIT_GBP, "flat_spread"

    if value_pct is not None:
        units = 2.0 if value_pct >= 20 else 1.5 if value_pct >= 15 else 1.0 if value_pct >= 10 else 0.5 if value_pct >= 5 else 0.5
        return units, units * STRICT_UNIT_GBP, "value_tiered"

    return 1.0, 1.0 * STRICT_UNIT_GBP, "flat"


def format_signed_line(v: float | None) -> str:
    if v is None:
        return "—"
    abs_v = abs(v)
    body = str(int(abs_v)) if float(abs_v).is_integer() else f"{abs_v:.1f}"
    return f"{'+' if v >= 0 else '-'}{body}"


def load_overlay_policy(
    policy_path: Path,
    window_type: str,
    segment_family: str,
) -> tuple[dict[tuple[int, str, str], dict[str, float]], dict[tuple[str, str], list[int]]]:
    if not policy_path.exists():
        return {}, {}
    with policy_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}, {}
    req = {"tournament_key", "window_type", "target_season_year", "bet_side", "segment_family", "n", "roi_pct_shrunk"}
    if not req.issubset(set(rows[0].keys())):
        return {}, {}

    agg: dict[tuple[int, str, str], dict[str, float]] = defaultdict(lambda: {"w_roi": 0.0, "w_n": 0.0})
    years_by_key_side: dict[tuple[str, str], set[int]] = defaultdict(set)
    for r in rows:
        if (r.get("window_type") or "") != window_type:
            continue
        if (r.get("segment_family") or "") != segment_family:
            continue
        ts = (r.get("target_season_year") or "").strip()
        tkey = (r.get("tournament_key") or "").strip()
        bside = (r.get("bet_side") or "").strip()
        if not ts or not tkey or bside not in {"fav", "dog"}:
            continue
        try:
            year = int(ts)
            n = float(r.get("n") or 0.0)
            roi = float(r.get("roi_pct_shrunk") or 0.0)
        except ValueError:
            continue
        if n <= 0:
            continue
        k = (year, tkey, bside)
        agg[k]["w_roi"] += roi * n
        agg[k]["w_n"] += n
        years_by_key_side[(tkey, bside)].add(year)

    out: dict[tuple[int, str, str], dict[str, float]] = {}
    for k, v in agg.items():
        if v["w_n"] <= 0:
            continue
        out[k] = {"n": v["w_n"], "roi_pct_shrunk": v["w_roi"] / v["w_n"]}
    years_sorted = {k: sorted(v) for k, v in years_by_key_side.items() if v}
    return out, years_sorted


def resolve_overlay_policy(
    season_year: int,
    tournament_name: str,
    bet_side: str,
    overlay_lookup: dict[tuple[int, str, str], dict[str, float]],
    overlay_years: dict[tuple[str, str], list[int]],
) -> tuple[dict[str, float] | None, str, int | None, str]:
    cands = tour_key_candidates(tournament_name)
    if not cands:
        return None, "", None, "missing"

    # Exact season-year match first.
    for tkey in cands:
        pol = overlay_lookup.get((season_year, tkey, bet_side))
        if pol is not None:
            return pol, tkey, season_year, "exact"

    # Fallback: latest available <= season_year, else latest available.
    for tkey in cands:
        years = overlay_years.get((tkey, bet_side), [])
        if not years:
            continue
        prior = [y for y in years if y <= season_year]
        resolved_year = max(prior) if prior else max(years)
        pol = overlay_lookup.get((resolved_year, tkey, bet_side))
        if pol is not None:
            return pol, tkey, resolved_year, "fallback_year"

    return None, cands[0], None, "missing"


def append_rows_dedup(path: Path, rows: list[dict[str, Any]], key_fields: list[str]) -> int:
    if not path.exists() and not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_by_key: dict[tuple[str, ...], dict[str, str]] = {}
    existing_fields: list[str] = []
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as f:
            rd = csv.DictReader(f)
            existing_fields = list(rd.fieldnames or [])
            for r in rd:
                row = dict(r)
                key = tuple(_append_key_value(k, row.get(k)) for k in key_fields)
                existing_by_key[key] = row

    out_rows = list(existing_by_key.values())
    added = 0
    for r in rows:
        key = tuple(_append_key_value(k, r.get(k)) for k in key_fields)
        if key in existing_by_key:
            continue
        normalized = {k: ("" if v is None else str(v)) for k, v in r.items()}
        existing_by_key[key] = normalized
        out_rows.append(normalized)
        added += 1

    fieldnames = list(existing_fields)
    for r in rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    for r in out_rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    for k in MANDATORY_APPEND_FIELDS:
        if k not in fieldnames:
            fieldnames.append(k)
    if not fieldnames and rows:
        fieldnames = list(rows[0].keys())

    with path.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        wr.writerows(out_rows)
    return added


def main() -> int:
    load_env()

    parser = argparse.ArgumentParser(description="Strict policy signals report with optional tournament-overlay mode.")
    parser.add_argument("--date", default="", help="UTC date YYYY-MM-DD (default: today)")
    parser.add_argument("--append", action="store_true", help="Append production-mode signals to strict-signals.csv")
    parser.add_argument(
        "--signal-profile",
        choices=("strict", "volume_275", "volume_200", "spread_shadow"),
        default=(os.environ.get("STRICT_SIGNAL_PROFILE", "strict") or "strict").strip().lower(),
        help="Signal profile to evaluate/write (strict live policy or one of the shadow volume profiles).",
    )
    parser.add_argument("--output", default="", help="Output CSV path for profile signals (auto by profile if omitted)")
    parser.add_argument("--internal-output", default="", help="Internal-tracking CSV path (auto by profile if omitted)")
    parser.add_argument("--policy-mode", choices=("base", "overlay"), default="base", help="Production mode")
    parser.add_argument("--compare-overlay", action="store_true", help="Compute and print base vs overlay side-by-side")
    parser.add_argument("--compare-output", default=str(DEFAULT_COMPARE_OUTPUT), help="CSV path for side-by-side tracking")

    parser.add_argument("--overlay-policy-file", default=str(DEFAULT_OVERLAY_POLICY_FILE))
    parser.add_argument("--overlay-window", default=DEFAULT_OVERLAY_WINDOW)
    parser.add_argument("--overlay-family", choices=("seed", "entry"), default=DEFAULT_OVERLAY_FAMILY)
    parser.add_argument("--overlay-min-n", type=int, default=DEFAULT_OVERLAY_MIN_N)
    parser.add_argument("--overlay-min-roi-pct", type=float, default=DEFAULT_OVERLAY_MIN_ROI_PCT)
    parser.add_argument("--overlay-missing-mode", choices=("skip", "allow"), default=DEFAULT_OVERLAY_MISSING_MODE)
    parser.add_argument(
        "--injury-overlay-enabled",
        dest="injury_overlay_enabled",
        action="store_true",
        default=env_bool(os.environ.get("STRICT_INJURY_OVERLAY_ENABLED"), False),
        help="Exclude strict candidates when either player has a recent injured-list row",
    )
    parser.add_argument(
        "--no-injury-overlay-enabled",
        dest="injury_overlay_enabled",
        action="store_false",
        help="Disable injury exclusion overlay (default)",
    )
    parser.add_argument(
        "--injury-lookback-days",
        type=int,
        default=int(os.environ.get("STRICT_INJURY_LOOKBACK_DAYS", str(DEFAULT_STRICT_INJURY_LOOKBACK_DAYS))),
    )
    parser.add_argument(
        "--injury-csv",
        default=os.environ.get("INJURED_PLAYERS_CSV", str(DEFAULT_INJURY_CSV)),
    )
    args = parser.parse_args()

    if not args.output:
        args.output = str(DEFAULT_OUTPUT if args.signal_profile == "strict" else SHADOW_PROFILE_OUTPUTS[args.signal_profile][0])
    if not args.internal_output:
        if args.signal_profile == "spread_shadow":
            args.internal_output = ""
        else:
            args.internal_output = str(
                DEFAULT_INTERNAL_OUTPUT if args.signal_profile == "strict" else SHADOW_PROFILE_OUTPUTS[args.signal_profile][1]
            )
    if args.signal_profile != "strict" and args.policy_mode == "overlay":
        print(f"WARNING: overlay mode applies to strict profile only; forcing policy-mode=base for {args.signal_profile}.")
        args.policy_mode = "base"
    if args.signal_profile != "strict" and args.compare_overlay:
        print(f"WARNING: --compare-overlay applies to strict profile only; disabling for {args.signal_profile}.")
        args.compare_overlay = False

    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local", file=sys.stderr)
        return 1

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    base = f"{url}/rest/v1"

    today = datetime.now(timezone.utc).date().isoformat()
    if args.date:
        today = args.date
    try:
        season_year = int(today[:4])
    except ValueError:
        print(f"Invalid date format: {today}", file=sys.stderr)
        return 1
    try:
        report_day = date.fromisoformat(today)
    except ValueError:
        print(f"Invalid date format: {today}", file=sys.stderr)
        return 1

    injury_index = load_recent_injury_index(
        Path(args.injury_csv),
        lookback_days=max(0, int(args.injury_lookback_days)),
        today=report_day,
        include_sources=("injured",),
    )
    injury_flagged_matches = 0
    injury_skipped_matches = 0

    r = requests.get(
        f"{base}/daily_fair_odds",
        headers=headers,
        params={
            "select": "id,tour_id,player1_id,player2_id,surface,odds1,odds2,confidence,spread_line,spread_odds1,spread_odds2,handicap_edge_p1,handicap_edge_p2",
            "limit": 2000,
        },
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json() or []
    if not rows:
        print("No rows in daily_fair_odds. Run oncourt-compute-fair-odds.py first.")
        return 0

    tour_ids = list({r["tour_id"] for r in rows if r.get("tour_id") is not None})
    tours: dict[int, dict[str, Any]] = {}
    if tour_ids:
        for i in range(0, len(tour_ids), 100):
            chunk = tour_ids[i : i + 100]
            tr = requests.get(
                f"{base}/oncourt_tours",
                headers=headers,
                params={"select": "id,name,rank", "id": f"in.({','.join(str(x) for x in chunk)})"},
                timeout=30,
            )
            if tr.status_code == 200 and tr.json():
                for t in tr.json():
                    tid = t.get("id")
                    if tid is not None:
                        tours[int(tid)] = {"name": t.get("name") or "", "rank": t.get("rank")}

    player_ids = list(
        {r["player1_id"] for r in rows if r.get("player1_id") is not None}
        | {r["player2_id"] for r in rows if r.get("player2_id") is not None}
    )
    players: dict[int, str] = {}
    for i in range(0, len(player_ids), 100):
        chunk = player_ids[i : i + 100]
        pr = requests.get(
            f"{base}/oncourt_players",
            headers=headers,
            params={"select": "id,name", "id": f"in.({','.join(str(x) for x in chunk)})"},
            timeout=30,
        )
        if pr.status_code == 200 and pr.json():
            for p in pr.json():
                pid = p.get("id")
                if pid is not None:
                    players[int(pid)] = p.get("name") or ""

    snap = requests.get(
        f"{base}/bookmaker_odds_snapshot",
        headers=headers,
        params={
            "select": "player1_name,player2_name,odds1,odds2",
            "bookmaker": "eq.Pinnacle",
            "capture_date": "eq." + today,
            "league": "in.(ATP,Challenger)",
        },
        timeout=30,
    )
    snap.raise_for_status()
    pin_rows = snap.json() or []

    fair_rows_for_match = [
        {
            "id": r.get("id"),
            "p1_name": players.get(r.get("player1_id") or 0) or "",
            "p2_name": players.get(r.get("player2_id") or 0) or "",
        }
        for r in rows
    ]
    matched_pinnacle = match_pinnacle_rows(fair_rows_for_match, pin_rows)

    candidates: list[dict[str, Any]] = []
    for r in rows:
        surface = (r.get("surface") or "").strip()
        confidence = (r.get("confidence") or "").strip().lower()
        tour_id = r.get("tour_id")
        tour_meta = tours.get(tour_id, {}) if tour_id is not None else {}
        series_bucket = series_bucket_from_tour(tour_meta.get("name"), tour_meta.get("rank"))
        strict_min_value = strict_min_value_for(surface, series_bucket, confidence)
        volume_min_value = (
            shadow_profile_min_value_for(args.signal_profile, surface, series_bucket, confidence)
            if args.signal_profile not in {"strict", "spread_shadow"}
            else None
        )
        spread_shadow_reason = spread_shadow_reason_for(surface, series_bucket, confidence)
        spread_shadow_eligible = args.signal_profile == "spread_shadow" and spread_shadow_reason is not None
        if strict_min_value is None and volume_min_value is None and not spread_shadow_eligible:
            continue

        our_odds1 = r.get("odds1")
        our_odds2 = r.get("odds2")
        if our_odds1 is None or our_odds2 is None:
            continue
        our_odds1 = float(our_odds1)
        our_odds2 = float(our_odds2)
        # ML only: skip matches where model favourite odds < 1.25.
        # Keep spreads eligible; this filter is for dog-moneyline distortions.
        model_fav_odds = min(our_odds1, our_odds2)
        model_ml_excluded = model_fav_odds < MISPRICE_MODEL_FAV_ODDS_MIN
        if is_excluded_short_favorite(surface, series_bucket, confidence, our_odds1, our_odds2):
            continue

        p1_name = players.get(r.get("player1_id") or 0) or ""
        p2_name = players.get(r.get("player2_id") or 0) or ""
        p1_inj, p1_inj_mode = injury_index.match_name(p1_name)
        p2_inj, p2_inj_mode = injury_index.match_name(p2_name)
        inj_any = p1_inj or p2_inj
        if inj_any:
            injury_flagged_matches += 1
        row_id = r.get("id")
        pin = matched_pinnacle.get(int(row_id)) if row_id is not None else None
        if not pin or (pin["odds1"] or 0) <= 0 or (pin["odds2"] or 0) <= 0:
            continue

        # ML only: skip when Pinnacle favourite odds < 1.25. Keep spreads eligible.
        pin_fav_odds = min(float(pin["odds1"] or 0), float(pin["odds2"] or 0))
        pin_ml_excluded = pin_fav_odds > 0 and pin_fav_odds < MISPRICE_MODEL_FAV_ODDS_MIN

        value_p1 = (pin["odds1"] / our_odds1 - 1) * 100 if our_odds1 > 1 else None
        value_p2 = (pin["odds2"] / our_odds2 - 1) * 100 if our_odds2 > 1 else None
        if args.injury_overlay_enabled and inj_any:
            injury_skipped_matches += 1
            continue

        side = "P1" if (value_p1 or 0) >= (value_p2 or 0) else "P2"
        value_pct = value_p1 if side == "P1" else value_p2
        has_internal_ml_value = (
            (value_p1 is not None and value_p1 >= INTERNAL_TRACK_MIN_VALUE_PCT)
            or (value_p2 is not None and value_p2 >= INTERNAL_TRACK_MIN_VALUE_PCT)
        )
        strict_match = (
            strict_min_value is not None
            and not model_ml_excluded
            and not pin_ml_excluded
            and has_internal_ml_value
            and value_pct is not None
            and value_pct >= strict_min_value
        )
        volume_match = (
            volume_min_value is not None
            and not model_ml_excluded
            and not pin_ml_excluded
            and has_internal_ml_value
            and value_pct is not None
            and value_pct >= volume_min_value
        )
        strict_spread_eligible = strict_min_value is not None
        volume_spread_eligible = volume_min_value is not None
        if not strict_match and not volume_match:
            if not strict_spread_eligible and not volume_spread_eligible:
                continue
        fav_side = "P1" if our_odds1 <= our_odds2 else "P2"
        bet_side = "fav" if side == fav_side else "dog"
        tname = tour_meta.get("name") or ""
        tkey = tour_key(tname)
        if args.signal_profile != "spread_shadow" and (strict_match or volume_match):
            stake_units, stake_gbp, stake_model = compute_stake_units(
                our_odds1=our_odds1,
                our_odds2=our_odds2,
                pin_odds1=pin["odds1"],
                pin_odds2=pin["odds2"],
                side=side,
                bet_type="match",
                value_pct=value_pct,
            )

            candidates.append(
                {
                    "date": today,
                    "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "player1": p1_name,
                    "player2": p2_name,
                    "surface": surface,
                    "series": series_bucket,
                    "confidence": confidence,
                    "our_odds1": round(our_odds1, 4),
                    "our_odds2": round(our_odds2, 4),
                    "pin_odds1": round(pin["odds1"], 4),
                    "pin_odds2": round(pin["odds2"], 4),
                    "value_p1": round(value_p1, 2) if value_p1 is not None else None,
                    "value_p2": round(value_p2, 2) if value_p2 is not None else None,
                    "side": side,
                    "value_pct": round(value_pct, 2),
                    "stake_units": round(stake_units, 4),
                    "stake_gbp": round(stake_gbp, 2),
                    "stake_model": stake_model,
                    "bet_type": "match",
                    "policy_mode": "base",
                    "overlay_n": "",
                    "overlay_roi_pct_shrunk": "",
                    "overlay_reason": "",
                    "recent_injured_p1": p1_inj,
                    "recent_injured_p2": p2_inj,
                    "recent_injured_any": inj_any,
                    "recent_injured_p1_mode": p1_inj_mode,
                    "recent_injured_p2_mode": p2_inj_mode,
                    "_bet_side": bet_side,
                    "_tournament_key": tkey,
                    "_tournament_name": tname,
                    "_strict_match": strict_match,
                    "_volume_match": volume_match,
                    "_spread_shadow_match": False,
                    "shadow_reason": "",
                }
            )

        # Handicap signals: when handicap_edge >= 20% on P1+ or P2-
        # Keep them flat 1u and profile-gated the same way as match signals.
        spread_line = r.get("spread_line")
        spread_o1 = r.get("spread_odds1")
        spread_o2 = r.get("spread_odds2")
        he_p1 = r.get("handicap_edge_p1")
        he_p2 = r.get("handicap_edge_p2")
        profile_spread_eligible = strict_spread_eligible or volume_spread_eligible or spread_shadow_eligible
        if profile_spread_eligible and (
            spread_line is not None
            and spread_o1 is not None
            and spread_o2 is not None
            and he_p1 is not None
            and he_p2 is not None
            and not inj_any
        ):
            sl = float(spread_line)
            so1 = float(spread_o1)
            so2 = float(spread_o2)
            he1 = float(he_p1)
            he2 = float(he_p2)
            if he1 >= (SPREAD_SHADOW_MIN_EDGE_PCT if args.signal_profile == "spread_shadow" else HANDICAP_MIN_EDGE_PCT):
                stake_units_h1, stake_gbp_h1, stake_model_h1 = compute_stake_units(
                    our_odds1=our_odds1,
                    our_odds2=our_odds2,
                    pin_odds1=pin["odds1"],
                    pin_odds2=pin["odds2"],
                    side="P1+",
                    bet_type="spread",
                )
                candidates.append(
                    {
                        "date": today,
                        "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                        "player1": p1_name,
                        "player2": p2_name,
                        "surface": surface,
                        "series": series_bucket,
                        "confidence": confidence,
                        "our_odds1": "",
                        "our_odds2": "",
                        "pin_odds1": round(so1, 4),
                        "pin_odds2": round(so2, 4),
                        "value_p1": round(he1, 2),
                        "value_p2": round(he2, 2),
                        "side": "P1+",
                        "value_pct": round(he1, 2),
                        "stake_units": round(stake_units_h1, 4),
                        "stake_gbp": round(stake_gbp_h1, 2),
                        "stake_model": stake_model_h1,
                        "bet_type": "spread",
                        "spread_line": round(sl, 1),
                        "spread_odds": round(so1, 4),
                        "policy_mode": "base",
                        "overlay_n": "",
                        "overlay_roi_pct_shrunk": "",
                        "overlay_reason": "",
                        "recent_injured_p1": p1_inj,
                        "recent_injured_p2": p2_inj,
                        "recent_injured_any": False,
                        "recent_injured_p1_mode": p1_inj_mode,
                        "recent_injured_p2_mode": p2_inj_mode,
                        "_bet_side": "dog" if our_odds1 > our_odds2 else "fav",
                        "_tournament_key": tkey,
                        "_tournament_name": tname,
                        "_strict_match": strict_spread_eligible,
                        "_volume_match": volume_spread_eligible,
                        "_spread_shadow_match": spread_shadow_eligible,
                        "shadow_reason": spread_shadow_reason or "",
                    }
                )
            if he2 >= (SPREAD_SHADOW_MIN_EDGE_PCT if args.signal_profile == "spread_shadow" else HANDICAP_MIN_EDGE_PCT):
                stake_units_h2, stake_gbp_h2, stake_model_h2 = compute_stake_units(
                    our_odds1=our_odds1,
                    our_odds2=our_odds2,
                    pin_odds1=pin["odds1"],
                    pin_odds2=pin["odds2"],
                    side="P2-",
                    bet_type="spread",
                )
                candidates.append(
                    {
                        "date": today,
                        "time_utc": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                        "player1": p1_name,
                        "player2": p2_name,
                        "surface": surface,
                        "series": series_bucket,
                        "confidence": confidence,
                        "our_odds1": "",
                        "our_odds2": "",
                        "pin_odds1": round(so1, 4),
                        "pin_odds2": round(so2, 4),
                        "value_p1": round(he1, 2),
                        "value_p2": round(he2, 2),
                        "side": "P2-",
                        "value_pct": round(he2, 2),
                        "stake_units": round(stake_units_h2, 4),
                        "stake_gbp": round(stake_gbp_h2, 2),
                        "stake_model": stake_model_h2,
                        "bet_type": "spread",
                        "spread_line": round(sl, 1),
                        "spread_odds": round(so2, 4),
                        "policy_mode": "base",
                        "overlay_n": "",
                        "overlay_roi_pct_shrunk": "",
                        "overlay_reason": "",
                        "recent_injured_p1": p1_inj,
                        "recent_injured_p2": p2_inj,
                        "recent_injured_any": False,
                        "recent_injured_p1_mode": p1_inj_mode,
                        "recent_injured_p2_mode": p2_inj_mode,
                        "_bet_side": "dog" if our_odds2 > our_odds1 else "fav",
                        "_tournament_key": tkey,
                        "_tournament_name": tname,
                        "_strict_match": strict_spread_eligible,
                        "_volume_match": volume_spread_eligible,
                        "_spread_shadow_match": spread_shadow_eligible,
                        "shadow_reason": spread_shadow_reason or "",
                    }
                )

    overlay_lookup: dict[tuple[int, str, str], dict[str, float]] = {}
    overlay_years: dict[tuple[str, str], list[int]] = {}
    if args.signal_profile == "strict" and (args.policy_mode == "overlay" or args.compare_overlay):
        overlay_lookup, overlay_years = load_overlay_policy(
            Path(args.overlay_policy_file),
            window_type=args.overlay_window,
            segment_family=args.overlay_family,
        )

    if args.signal_profile == "strict":
        profile_key = "_strict_match"
    elif args.signal_profile == "spread_shadow":
        profile_key = "_spread_shadow_match"
    else:
        profile_key = "_volume_match"
    profile_candidates = [x for x in candidates if x.get(profile_key)]
    base_signals: list[dict[str, Any]] = [dict(x) for x in profile_candidates]
    overlay_signals: list[dict[str, Any]] = []
    overlay_skips = Counter()
    for s in profile_candidates:
        if s.get("bet_type") == "spread":
            row = dict(s)
            row["policy_mode"] = "overlay" if args.policy_mode == "overlay" else "base"
            row["overlay_reason"] = "spread_only"
            overlay_signals.append(row)
            continue
        pol, resolved_tkey, resolved_year, match_mode = resolve_overlay_policy(
            season_year=season_year,
            tournament_name=(s.get("_tournament_name") or ""),
            bet_side=(s.get("_bet_side") or ""),
            overlay_lookup=overlay_lookup,
            overlay_years=overlay_years,
        )
        if pol is None:
            if args.overlay_missing_mode == "skip":
                overlay_skips["missing"] += 1
                continue
            n_val = ""
            roi_val = ""
            reason = "missing_allow"
        else:
            n_val = round(float(pol.get("n", 0.0)), 2)
            roi_val = round(float(pol.get("roi_pct_shrunk", 0.0)), 4)
            if float(pol.get("n", 0.0)) < float(args.overlay_min_n):
                overlay_skips["min_n"] += 1
                continue
            if float(pol.get("roi_pct_shrunk", 0.0)) < float(args.overlay_min_roi_pct):
                overlay_skips["min_roi"] += 1
                continue
            reason = "ok" if match_mode == "exact" else f"ok_{match_mode}_{resolved_year}"

        row = dict(s)
        row["policy_mode"] = "overlay"
        row["overlay_n"] = n_val
        row["overlay_roi_pct_shrunk"] = roi_val
        row["overlay_reason"] = reason
        row["overlay_tournament_key"] = resolved_tkey
        row["overlay_resolved_year"] = "" if resolved_year is None else str(resolved_year)
        overlay_signals.append(row)

    signals = overlay_signals if args.policy_mode == "overlay" else base_signals
    if args.signal_profile == "strict":
        for s in signals:
            s["threshold_tier"] = "public" if (s.get("value_pct") or 0) >= STRICT_MIN_VALUE_PCT else "internal"
            s["signal_profile"] = "strict"
        public_signals = [s for s in signals if (s.get("value_pct") or 0) >= STRICT_MIN_VALUE_PCT]
        internal_signals = signals  # All 5%+ for confirmation tracking
    elif args.signal_profile == "spread_shadow":
        for s in signals:
            s["threshold_tier"] = "profile"
            s["signal_profile"] = "spread_shadow"
        public_signals = signals
        internal_signals = []
    else:
        for s in signals:
            s["threshold_tier"] = "profile"
            s["signal_profile"] = args.signal_profile
        public_signals = signals
        internal_signals = signals

    public_ml_count = sum(1 for s in public_signals if (s.get("bet_type") or "match") != "spread")
    public_spread_count = sum(1 for s in public_signals if (s.get("bet_type") or "") == "spread")

    print(f"Strict policy report - {today} UTC")
    if args.signal_profile == "strict":
        print(
            f"Profile: strict  |  Segment: {ALLOWED_SEGMENT}  |  "
            f"Confidence: {', '.join(sorted(ALLOWED_CONFIDENCE))}  |  "
            f"Public: >={STRICT_MIN_VALUE_PCT}%  |  Internal: >={INTERNAL_TRACK_MIN_VALUE_PCT}%  |  "
            f"Handicap: >={HANDICAP_MIN_EDGE_PCT}%"
        )
    else:
        print(f"Profile: {args.signal_profile}  |  {SHADOW_PROFILE_LABELS.get(args.signal_profile, args.signal_profile)}")
    print(
        "Stake sizing: "
        f"value_tiered (5-10%=0.5u, 10-15%=1u, 15-20%=1.5u, 20%+=2u); "
        f"spread 1u flat; unit_gbp={STRICT_UNIT_GBP:.2f}"
    )
    if EXCLUDE_ATP500_HARD_SHORT_FAVORITES:
        print(
            "Exclusion: ATP500 Hard short favorites skipped "
            f"(confidence {', '.join(sorted(EXCLUDE_SHORT_FAV_CONFIDENCE))}, favorite odds < {EXCLUDE_SHORT_FAV_MAX_ODDS:.2f})"
        )
    print(f"Production mode: {args.policy_mode}  |  signal_profile={args.signal_profile}")
    if args.signal_profile == "strict":
        print(f"Signals (public >={STRICT_MIN_VALUE_PCT}%): {len(public_signals)}  |  Internal (5%+): {len(internal_signals)}")
    else:
        print(f"Signals (profile-qualified): {len(public_signals)}")
    print(f"Breakdown: ML={public_ml_count}  |  Spread={public_spread_count}")
    print(
        "Injury list: "
        f"path={Path(args.injury_csv)} recent_rows={injury_index.rows_recent}/{injury_index.rows_loaded} "
        f"lookback={args.injury_lookback_days}d "
        f"flagged_candidates={injury_flagged_matches} "
        f"overlay={'on' if args.injury_overlay_enabled else 'off'} "
        f"skipped={injury_skipped_matches}"
    )

    if args.signal_profile == "strict" and (args.policy_mode == "overlay" or args.compare_overlay):
        print(
            "Overlay config: "
            f"window={args.overlay_window} family={args.overlay_family} "
            f"min_n={args.overlay_min_n} min_roi_pct={args.overlay_min_roi_pct:+.2f} "
            f"missing={args.overlay_missing_mode} keys={len(overlay_lookup)} key_side={len(overlay_years)}"
        )
        print(f"Overlay pass count: {len(overlay_signals)} / {len(profile_candidates)}  skip_reasons={dict(overlay_skips)}")
    if args.signal_profile == "strict" and args.compare_overlay:
        print(f"Compare mode: base={len(base_signals)} overlay={len(overlay_signals)}")
    print()

    if not public_signals:
        print("No POLICY signals today (public threshold).")
    else:
        for s in public_signals:
            bt = s.get("bet_type") or "match"
            if bt == "spread":
                sl_raw = s.get("spread_line")
                sl_val = float(sl_raw) if sl_raw not in ("", None) else None
                display_line = sl_val if s.get("side") == "P1+" else (-sl_val if sl_val is not None else None)
                so = s.get("spread_odds", "")
                print(
                    f"  {s['player1']} vs {s['player2']}  |  "
                    f"{s['side']} ({format_signed_line(display_line)}) edge {s['value_pct']:+.1f}%  |  odds {so}"
                )
            else:
                print(
                    f"  {s['player1']} vs {s['player2']}  |  {s['side']} value {s['value_pct']:+.1f}%  |  "
                    f"our {s['our_odds1']:.2f}/{s['our_odds2']:.2f}  Pin {s['pin_odds1']:.2f}/{s['pin_odds2']:.2f}"
                )

    # Remove internal keys before CSV writes.
    for row_set in (signals, base_signals, overlay_signals):
        for r in row_set:
            r.pop("_bet_side", None)
            r.pop("_tournament_key", None)
            r.pop("_tournament_name", None)
            r.pop("_strict_match", None)
            r.pop("_volume_match", None)
            r.pop("_spread_shadow_match", None)

    if args.append:
        out_path = Path(args.output)
        added = append_rows_dedup(
            out_path,
            public_signals,
            key_fields=["date", "player1", "player2", "bet_type", "side", "spread_line", "policy_mode", "signal_profile"],
        )
        print(f"\nAppended {added}/{len(public_signals)} public rows to {out_path} (deduped).")

        if internal_signals and args.internal_output:
            internal_path = Path(args.internal_output)
            added_internal = append_rows_dedup(
                internal_path,
                internal_signals,
                key_fields=["date", "player1", "player2", "bet_type", "side", "spread_line", "policy_mode", "signal_profile"],
            )
            if args.signal_profile == "strict":
                print(f"Appended {added_internal}/{len(internal_signals)} internal (5%+) rows to {internal_path} (deduped).")
            else:
                print(f"Appended {added_internal}/{len(internal_signals)} profile rows to {internal_path} (deduped).")

        if args.signal_profile == "strict" and args.compare_overlay:
            compare_rows = base_signals + overlay_signals
            compare_path = Path(args.compare_output)
            added_cmp = append_rows_dedup(
                compare_path,
                compare_rows,
                key_fields=["date", "player1", "player2", "bet_type", "side", "spread_line", "policy_mode", "signal_profile"],
            )
            print(f"Appended {added_cmp}/{len(compare_rows)} comparison rows to {compare_path} (deduped).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
