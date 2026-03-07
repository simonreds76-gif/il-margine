"""
Strict policy report for today's signals.

Default behavior (production mode = base):
- Uses strict policy (Hard|Masters 1000, confidence high, value >= 10%)
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
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from injury_overlay import env_bool, load_recent_injury_index


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"
DEFAULT_OUTPUT = DATA_DIR / "strict-signals.csv"
DEFAULT_COMPARE_OUTPUT = DATA_DIR / "strict-signals-overlay-compare.csv"

STRICT_MIN_VALUE_PCT = 10.0
ALLOWED_SEGMENT = "Hard|Masters 1000"
ALLOWED_CONFIDENCE = {"high"}
EXCLUDE_ATP500_HARD_SHORT_FAVORITES = True
EXCLUDE_SHORT_FAV_MAX_ODDS = 1.8
EXCLUDE_SHORT_FAV_CONFIDENCE = {"high"}

# Suppress signals when model and Pinnacle disagree on favourite pricing by >10pp.
# Phantom underdog edges (model 1.15 vs Pin 1.02) cause guaranteed losses.
MISPRICE_IMPLIED_GAP_PP = 0.10

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


def match_names(p1_our: str, p2_our: str, pin_list: list[dict[str, Any]]) -> dict[str, float] | None:
    t1 = set(tokenize(p1_our))
    t2 = set(tokenize(p2_our))
    for pin in pin_list:
        a, b = pin.get("player1_name"), pin.get("player2_name")
        pa, pb = set(tokenize(a)), set(tokenize(b))
        if (t1 & pa and t2 & pb) or (t1 & pb and t2 & pa):
            o1 = pin.get("odds1")
            o2 = pin.get("odds2")
            if o1 is None or o2 is None:
                return None
            if (t1 & pa and t2 & pb):
                return {"odds1": float(o1), "odds2": float(o2)}
            return {"odds1": float(o2), "odds2": float(o1)}
    return None


def is_excluded_short_favorite(surface: str, series_bucket: str, confidence: str, our_odds1: float, our_odds2: float) -> bool:
    if not EXCLUDE_ATP500_HARD_SHORT_FAVORITES:
        return False
    if surface != "Hard" or series_bucket != "ATP500":
        return False
    if confidence not in EXCLUDE_SHORT_FAV_CONFIDENCE:
        return False
    return min(our_odds1, our_odds2) < EXCLUDE_SHORT_FAV_MAX_ODDS


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
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows: list[dict[str, str]] = []
    existing_fields: list[str] = []
    existing_keys: set[tuple[str, ...]] = set()
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as f:
            rd = csv.DictReader(f)
            existing_fields = list(rd.fieldnames or [])
            for r in rd:
                existing_rows.append(dict(r))
                key = tuple(str(r.get(k) or "").strip().lower() for k in key_fields)
                existing_keys.add(key)

    out_rows = list(existing_rows)
    added = 0
    for r in rows:
        key = tuple(str(r.get(k) or "").strip().lower() for k in key_fields)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        out_rows.append({k: ("" if v is None else str(v)) for k, v in r.items()})
        added += 1

    fieldnames = list(existing_fields)
    for r in out_rows:
        for k in r.keys():
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
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV path for production-mode signals")
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
        params={"select": "id,tour_id,player1_id,player2_id,surface,odds1,odds2,confidence", "limit": 2000},
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
            "league": "eq.ATP",
        },
        timeout=30,
    )
    snap.raise_for_status()
    pin_rows = snap.json() or []

    candidates: list[dict[str, Any]] = []
    for r in rows:
        surface = (r.get("surface") or "").strip()
        confidence = (r.get("confidence") or "").strip().lower()
        tour_id = r.get("tour_id")
        tour_meta = tours.get(tour_id, {}) if tour_id is not None else {}
        series_bucket = series_bucket_from_tour(tour_meta.get("name"), tour_meta.get("rank"))
        segment_key = f"{surface}|{series_bucket}"
        if segment_key != ALLOWED_SEGMENT or confidence not in ALLOWED_CONFIDENCE:
            continue

        our_odds1 = r.get("odds1")
        our_odds2 = r.get("odds2")
        if our_odds1 is None or our_odds2 is None:
            continue
        our_odds1 = float(our_odds1)
        our_odds2 = float(our_odds2)
        # Skip matches where model favourite odds < 1.25.
        # The model cannot price extreme mismatches — both sides are unreliable.
        model_fav_odds = min(our_odds1, our_odds2)
        if model_fav_odds < MISPRICE_MODEL_FAV_ODDS_MIN:
            continue
        if is_excluded_short_favorite(surface, series_bucket, confidence, our_odds1, our_odds2):
            continue

        p1_name = players.get(r.get("player1_id") or 0) or ""
        p2_name = players.get(r.get("player2_id") or 0) or ""
        p1_inj, p1_inj_mode = injury_index.match_name(p1_name)
        p2_inj, p2_inj_mode = injury_index.match_name(p2_name)
        inj_any = p1_inj or p2_inj
        if inj_any:
            injury_flagged_matches += 1
        pin = match_names(p1_name, p2_name, pin_rows)
        if not pin or (pin["odds1"] or 0) <= 0 or (pin["odds2"] or 0) <= 0:
            continue

        # Suppress when model and Pinnacle disagree on favourite pricing by >10pp.
        # Phantom underdog edges (model 1.15 vs Pin 1.02) cause guaranteed losses.
        pin_fav_implied = max(1.0 / pin["odds1"], 1.0 / pin["odds2"])
        model_fav_implied = max(1.0 / our_odds1, 1.0 / our_odds2)
        if abs(model_fav_implied - pin_fav_implied) > MISPRICE_IMPLIED_GAP_PP:
            continue

        value_p1 = (pin["odds1"] / our_odds1 - 1) * 100 if our_odds1 > 1 else None
        value_p2 = (pin["odds2"] / our_odds2 - 1) * 100 if our_odds2 > 1 else None
        if not ((value_p1 is not None and value_p1 >= STRICT_MIN_VALUE_PCT) or (value_p2 is not None and value_p2 >= STRICT_MIN_VALUE_PCT)):
            continue
        if args.injury_overlay_enabled and inj_any:
            injury_skipped_matches += 1
            continue

        side = "P1" if (value_p1 or 0) >= (value_p2 or 0) else "P2"
        value_pct = value_p1 if side == "P1" else value_p2
        fav_side = "P1" if our_odds1 <= our_odds2 else "P2"
        bet_side = "fav" if side == fav_side else "dog"
        tname = tour_meta.get("name") or ""
        tkey = tour_key(tname)

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
            }
        )

    overlay_lookup: dict[tuple[int, str, str], dict[str, float]] = {}
    overlay_years: dict[tuple[str, str], list[int]] = {}
    if args.policy_mode == "overlay" or args.compare_overlay:
        overlay_lookup, overlay_years = load_overlay_policy(
            Path(args.overlay_policy_file),
            window_type=args.overlay_window,
            segment_family=args.overlay_family,
        )

    base_signals: list[dict[str, Any]] = [dict(x) for x in candidates]
    overlay_signals: list[dict[str, Any]] = []
    overlay_skips = Counter()
    for s in candidates:
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

    print(f"Strict policy report - {today} UTC")
    print(f"Segment: {ALLOWED_SEGMENT}  |  Confidence: {', '.join(sorted(ALLOWED_CONFIDENCE))}  |  Min value: {STRICT_MIN_VALUE_PCT}%")
    if EXCLUDE_ATP500_HARD_SHORT_FAVORITES:
        print(
            "Exclusion: ATP500 Hard short favorites skipped "
            f"(confidence {', '.join(sorted(EXCLUDE_SHORT_FAV_CONFIDENCE))}, favorite odds < {EXCLUDE_SHORT_FAV_MAX_ODDS:.2f})"
        )
    print(f"Production mode: {args.policy_mode}")
    print(f"Signals (production): {len(signals)}")
    print(
        "Injury list: "
        f"path={Path(args.injury_csv)} recent_rows={injury_index.rows_recent}/{injury_index.rows_loaded} "
        f"lookback={args.injury_lookback_days}d "
        f"flagged_candidates={injury_flagged_matches} "
        f"overlay={'on' if args.injury_overlay_enabled else 'off'} "
        f"skipped={injury_skipped_matches}"
    )

    if args.policy_mode == "overlay" or args.compare_overlay:
        print(
            "Overlay config: "
            f"window={args.overlay_window} family={args.overlay_family} "
            f"min_n={args.overlay_min_n} min_roi_pct={args.overlay_min_roi_pct:+.2f} "
            f"missing={args.overlay_missing_mode} keys={len(overlay_lookup)} key_side={len(overlay_years)}"
        )
        print(f"Overlay pass count: {len(overlay_signals)} / {len(candidates)}  skip_reasons={dict(overlay_skips)}")
    if args.compare_overlay:
        print(f"Compare mode: base={len(base_signals)} overlay={len(overlay_signals)}")
    print()

    if not signals:
        print("No POLICY signals today.")
    else:
        for s in signals:
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

    if args.append:
        out_path = Path(args.output)
        added = append_rows_dedup(
            out_path,
            signals,
            key_fields=["date", "player1", "player2", "surface", "series", "confidence", "side", "policy_mode"],
        )
        print(f"\nAppended {added}/{len(signals)} production rows to {out_path} (deduped).")

        if args.compare_overlay:
            compare_rows = base_signals + overlay_signals
            compare_path = Path(args.compare_output)
            added_cmp = append_rows_dedup(
                compare_path,
                compare_rows,
                key_fields=["date", "player1", "player2", "surface", "series", "confidence", "side", "policy_mode"],
            )
            print(f"Appended {added_cmp}/{len(compare_rows)} comparison rows to {compare_path} (deduped).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
