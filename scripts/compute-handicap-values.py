#!/usr/bin/env python3
"""
Compute handicap (spread) value for daily_fair_odds matches using Pinnacle spread lines.

Run after: (1) oncourt-compute-fair-odds.py, (2) pinnacle-scrape-odds.py

If daily_fair_odds is recomputed later (e.g. via Supabase), spread columns get overwritten
with null. Re-run this script or the full pipeline (run-daily-odds.py) to restore handicaps.

Matches daily_fair_odds (with p_a, p_b) to bookmaker_odds_snapshot (with spread_line,
spread_odds1, spread_odds2), computes model edge via handicap_probs.handicap_value,
and PATCHes daily_fair_odds with spread + handicap_edge columns.

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
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean, median

# Add scripts dir for handicap_probs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handicap_probs import prob_p1_covers_plus


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
        help="Path to handicap calibration JSON. Defaults to env HANDICAP_CALIBRATION_FILE or data/backtest/handicap-calibration-params.json.",
    )
    ap.add_argument(
        "--disable-calibration",
        action="store_true",
        help="Disable handicap calibration (raw probabilities only).",
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
        return HandicapCalibration(False, 0.0, 0.0, 1.0, "disabled-by-flag")

    mode = (os.environ.get("HANDICAP_CALIBRATION_MODE") or "auto").strip().lower()
    if mode in {"off", "false", "0", "none"}:
        return HandicapCalibration(False, 0.0, 0.0, 1.0, "disabled-by-env")

    default_path = os.path.join(_root_dir(), "data", "backtest", "handicap-calibration-params.json")
    cal_path = (
        args.calibration_file
        or os.environ.get("HANDICAP_CALIBRATION_FILE")
        or default_path
    )

    if not os.path.exists(cal_path):
        if mode in {"force", "on", "required"}:
            raise FileNotFoundError(f"Calibration file not found: {cal_path}")
        return HandicapCalibration(False, 0.0, 0.0, 1.0, f"missing:{cal_path}")

    with open(cal_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    parsed = _parse_calibration_payload(payload)
    if parsed is None:
        if mode in {"force", "on", "required"}:
            raise ValueError(f"Calibration file missing required params: {cal_path}")
        return HandicapCalibration(False, 0.0, 0.0, 1.0, f"invalid:{cal_path}")

    line_shift, platt_a, platt_b = parsed
    return HandicapCalibration(True, line_shift, platt_a, platt_b, cal_path)


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

    capture_date = args.date or datetime.now(timezone.utc).date().isoformat()
    calibration = load_handicap_calibration(args)
    if calibration.enabled:
        print(
            "Handicap calibration: ON "
            f"(shift={calibration.line_shift:+.3f}, a={calibration.platt_a:+.4f}, b={calibration.platt_b:+.4f}) "
            f"source={calibration.source}"
        )
    else:
        print(f"Handicap calibration: OFF ({calibration.source})")

    # 1) Load daily_fair_odds with p_a, p_b
    r = requests.get(
        f"{url}/rest/v1/daily_fair_odds",
        headers=headers,
        params={"select": "id,tour_id,player1_id,player2_id,p1_win_prob,p_a,p_b"},
        timeout=30,
    )
    r.raise_for_status()
    fair_rows = r.json()
    if not fair_rows:
        print("No rows in daily_fair_odds. Run oncourt-compute-fair-odds.py first.")
        sys.exit(1)

    # Check for p_a, p_b
    sample = fair_rows[0]
    if sample.get("p_a") is None or sample.get("p_b") is None:
        print("daily_fair_odds missing p_a/p_b. Run migration docs/supabase-daily-fair-odds-pa-pb.sql")
        sys.exit(1)

    player_ids = set()
    for row in fair_rows:
        if row.get("player1_id") is not None:
            player_ids.add(row["player1_id"])
        if row.get("player2_id") is not None:
            player_ids.add(row["player2_id"])
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

    # 2) Load Pinnacle snapshot with spread (ATP + Challenger)
    r = requests.get(
        f"{url}/rest/v1/bookmaker_odds_snapshot",
        headers=headers,
        params={
            "select": "player1_name,player2_name,odds1,odds2,spread_line,spread_odds1,spread_odds2,league",
            "bookmaker": "eq.Pinnacle",
            "capture_date": f"eq.{capture_date}",
            "league": "in.(ATP,Challenger)",
            "order": "captured_at.desc",
            "limit": 500,
        },
        timeout=30,
    )
    r.raise_for_status()
    pin_rows = r.json()
    if not pin_rows:
        print(f"No Pinnacle ATP/Challenger snapshot for {capture_date}. Run pinnacle-scrape-odds.py first.")
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
    for m in matched:
        fo, pin, pin_reversed_for_fair = m["fair"], m["pinnacle"], m["pin_reversed_for_fair"]
        p_a = float(fo.get("p_a") or 0)
        p_b = float(fo.get("p_b") or 0)
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
        else:
            line = pin_line
            spread_odds1 = pin_o1
            spread_odds2 = pin_o2

        if spread_odds1 <= 1 or spread_odds2 <= 1:
            continue

        # Signed line from OUR P1 perspective:
        #   +x => P1 +x
        #   -x => P1 -x
        model_p1_raw = prob_p1_covers_plus(p_a, p_b, line)
        model_p1_shifted = prob_p1_covers_plus(p_a, p_b, line + calibration.line_shift)
        model_p1 = _calibrate_prob(model_p1_shifted, calibration)
        model_p2 = _clamp(1.0 - model_p1, 1e-6, 1.0 - 1e-6)

        implied1 = 1.0 / spread_odds1
        raw_edge1 = (model_p1_raw - implied1) / implied1 * 100 if implied1 > 0 else None
        edge1 = (model_p1 - implied1) / implied1 * 100 if implied1 > 0 else None

        # Opposite side (OUR P2 at -line), complementary on .5 spreads.
        implied2 = 1.0 / spread_odds2
        edge2 = (model_p2 - implied2) / implied2 * 100 if implied2 > 0 else None

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
    print("Edge diagnostics (P1 +line):")
    summarize_edges("raw", edge_raw_p1)
    summarize_edges("cal", edge_cal_p1)
    print("Edge diagnostics (P2 -line, calibrated):")
    summarize_edges("cal", edge_cal_p2)
    print("Done.")


if __name__ == "__main__":
    main()
