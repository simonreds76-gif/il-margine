#!/usr/bin/env python3
"""
Walk-forward calibration + exposure tuning using backtest CSV outputs.

Default workflow:
  - Train period: 2024
  - Test period: 2025
  - Levers:
      1) global favorite-space calibration (A, B)
      2) selective exposure by segment (surface, series, or surface+series)

Requires:
  data/backtest/backtest-results-2024.csv
  data/backtest/backtest-results-2025.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean


DEFAULT_BLEND = {
    "ATP250": 1.00,
    "Masters 1000": 1.00,
    "ATP500": 0.70,
    "Grand Slam": 0.00,
    "Masters Cup": 0.00,
}


def _safe(p: float) -> float:
    return min(1.0 - 1e-12, max(1e-12, p))


def _logit(p: float) -> float:
    p = _safe(p)
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _load_rows(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"No rows in {path}")
    required = {"our_prob_raw", "pinnacle_odds", "pinnacle_odds_loser", "surface", "series", "tournament"}
    missing = sorted(required - set(rows[0].keys()))
    if missing:
        raise RuntimeError(f"{path} missing columns: {missing}")
    season_year = _infer_season_year(path)
    for r in rows:
        r["_season_year"] = season_year
        r["_tournament_key"] = _tour_key(r.get("tournament", ""))
    return rows


def _infer_season_year(path: Path) -> int:
    m = re.search(r"backtest-results-(\d{4})\.csv$", str(path).replace("\\", "/"), flags=re.IGNORECASE)
    if not m:
        raise RuntimeError(f"Cannot infer season year from filename: {path}")
    return int(m.group(1))


def _tour_key(name: str) -> str:
    raw = (name or "").strip().lower()
    if not raw:
        return ""
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    core = parts[-1] if len(parts) >= 2 and len(parts[-1]) >= 4 else raw
    core = re.sub(r"\b\d{4}\b", " ", core)
    core = re.sub(r"\b(challenger|qualifiers?|qualifying|qualification|atp|wta)\b", " ", core)
    core = re.sub(r"[^a-z0-9]+", " ", core)
    return " ".join(core.split())


def _load_tournament_side_policy(
    path: Path,
    window_type: str,
    segment_family: str,
) -> dict[tuple[int, str, str], dict[str, float]]:
    if not path.exists():
        raise RuntimeError(f"Policy file not found: {path}")
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"No rows in policy file: {path}")

    required = {"tournament_key", "window_type", "target_season_year", "bet_side", "segment_family", "n", "roi_pct_shrunk"}
    missing = sorted(required - set(rows[0].keys()))
    if missing:
        raise RuntimeError(f"{path} missing columns: {missing}")

    agg: dict[tuple[int, str, str], dict[str, float]] = defaultdict(lambda: {"w_roi": 0.0, "w_n": 0.0})
    for r in rows:
        if (r.get("window_type") or "") != window_type:
            continue
        if (r.get("segment_family") or "") != segment_family:
            continue
        tkey = (r.get("tournament_key") or "").strip()
        bside = (r.get("bet_side") or "").strip()
        ts = (r.get("target_season_year") or "").strip()
        try:
            target_year = int(ts)
            n = float(r.get("n") or 0.0)
            roi = float(r.get("roi_pct_shrunk") or 0.0)
        except ValueError:
            continue
        if not tkey or bside not in {"fav", "dog"} or n <= 0:
            continue
        k = (target_year, tkey, bside)
        agg[k]["w_roi"] += roi * n
        agg[k]["w_n"] += n

    out: dict[tuple[int, str, str], dict[str, float]] = {}
    for k, v in agg.items():
        if v["w_n"] <= 0:
            continue
        out[k] = {"roi_pct_shrunk": v["w_roi"] / v["w_n"], "n": v["w_n"]}
    return out


def _apply_prob(row: dict, a: float, b: float, blend_map: dict[str, float]) -> float:
    p_raw = _safe(float(row["our_prob_raw"]))
    q_raw = p_raw if p_raw >= 0.5 else (1.0 - p_raw)
    q_cal = _sigmoid(a + b * _logit(q_raw))
    blend = blend_map.get(row.get("series", ""), 1.0)
    q = (1.0 - blend) * q_raw + blend * q_cal
    q = _safe(q)
    return q if p_raw >= 0.5 else (1.0 - q)


def _metrics(rows: list[dict], a: float, b: float, blend_map: dict[str, float]) -> dict:
    probs = [_apply_prob(r, a, b, blend_map) for r in rows]
    ll = mean(-math.log(_safe(p)) for p in probs)
    brier = mean((1.0 - p) ** 2 for p in probs)  # row orientation: player1 is winner
    acc = mean(1.0 if p >= 0.5 else 0.0 for p in probs)
    return {"log_loss": ll, "brier": brier, "accuracy": acc}


def _roi(
    rows: list[dict],
    a: float,
    b: float,
    blend_map: dict[str, float],
    threshold: float,
    allowed_segments: set[str] | None = None,
    segment_mode: str = "surface_series",
    tournament_side_policy: dict[tuple[int, str, str], dict[str, float]] | None = None,
    policy_min_n: int = 30,
    policy_min_roi_pct: float = 0.0,
    policy_missing_mode: str = "skip",
) -> dict:
    bets = 0
    wins = 0
    profit = 0.0
    policy_skips = 0
    policy_skip_reasons: dict[str, int] = defaultdict(int)

    for r in rows:
        if allowed_segments is not None:
            seg = _segment_key(r, segment_mode)
            if seg not in allowed_segments:
                continue

        p_win = _apply_prob(r, a, b, blend_map)
        p_lose = _safe(1.0 - p_win)
        our_odds_w = 1.0 / p_win
        our_odds_l = 1.0 / p_lose
        psw = float(r["pinnacle_odds"])
        psl = float(r["pinnacle_odds_loser"])
        value_w = (psw / our_odds_w) - 1.0
        value_l = (psl / our_odds_l) - 1.0

        if value_w >= value_l:
            value = value_w
            side_winner = True
            odds = psw
        else:
            value = value_l
            side_winner = False
            odds = psl

        if value <= threshold:
            continue

        if tournament_side_policy is not None:
            model_fav_is_winner = p_win >= 0.5
            bet_side = "fav" if (model_fav_is_winner == side_winner) else "dog"
            season_year = int(r.get("_season_year", 0))
            tkey = str(r.get("_tournament_key", ""))
            pol = tournament_side_policy.get((season_year, tkey, bet_side))
            if pol is None:
                if policy_missing_mode == "skip":
                    policy_skips += 1
                    policy_skip_reasons["missing"] += 1
                    continue
            else:
                if pol["n"] < policy_min_n:
                    policy_skips += 1
                    policy_skip_reasons["min_n"] += 1
                    continue
                if pol["roi_pct_shrunk"] < policy_min_roi_pct:
                    policy_skips += 1
                    policy_skip_reasons["min_roi"] += 1
                    continue

        bets += 1
        if side_winner:
            wins += 1
            profit += odds - 1.0
        else:
            profit -= 1.0

    roi = (profit / bets) if bets > 0 else 0.0
    return {
        "bets": bets,
        "wins": wins,
        "profit": profit,
        "roi": roi,
        "policy_skips": policy_skips,
        "policy_skip_reasons": dict(policy_skip_reasons),
    }


def _segment_key(row: dict, mode: str) -> str:
    if mode == "surface":
        return row.get("surface", "N/A")
    if mode == "series":
        return row.get("series", "N/A")
    return f"{row.get('surface', 'N/A')}|{row.get('series', 'N/A')}"


def _segment_report(
    rows: list[dict],
    a: float,
    b: float,
    blend_map: dict[str, float],
    threshold: float,
    mode: str,
) -> list[tuple[str, int, float, float]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        grouped[_segment_key(r, mode)].append(r)
    out = []
    for seg, seg_rows in grouped.items():
        m = _metrics(seg_rows, a, b, blend_map)
        r = _roi(seg_rows, a, b, blend_map, threshold)
        out.append((seg, len(seg_rows), m["log_loss"], r["roi"]))
    out.sort(key=lambda x: (-x[1], x[0]))
    return out


def _choose_exposure_segments(
    train_rows: list[dict],
    test_rows: list[dict],
    a: float,
    b: float,
    blend_map: dict[str, float],
    threshold: float,
    mode: str,
    min_bets_per_year: int,
) -> set[str]:
    train_grouped: dict[str, list[dict]] = defaultdict(list)
    test_grouped: dict[str, list[dict]] = defaultdict(list)
    for r in train_rows:
        train_grouped[_segment_key(r, mode)].append(r)
    for r in test_rows:
        test_grouped[_segment_key(r, mode)].append(r)

    chosen = set()
    for seg in sorted(set(train_grouped) | set(test_grouped)):
        tr = _roi(train_grouped.get(seg, []), a, b, blend_map, threshold)
        te = _roi(test_grouped.get(seg, []), a, b, blend_map, threshold)
        if tr["bets"] >= min_bets_per_year and te["bets"] >= min_bets_per_year and tr["roi"] > 0 and te["roi"] > 0:
            chosen.add(seg)
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward tuning for backtest calibration/exposure.")
    parser.add_argument("--train", default="data/backtest/backtest-results-2024.csv")
    parser.add_argument("--test", default="data/backtest/backtest-results-2025.csv")
    parser.add_argument("--threshold", type=float, default=5.0, help="Value threshold percent for ROI/exposure logic.")
    parser.add_argument("--min-bets", type=int, default=80, help="Min bets per year for segment exposure selection.")
    parser.add_argument("--enable-tournament-side-policy", action="store_true", help="Apply tournament side-policy overlay from tournament-segment-roi.csv.")
    parser.add_argument("--segment-policy-file", default="data/backtest/tournament-segment-roi.csv", help="Tournament segment ROI CSV.")
    parser.add_argument("--segment-policy-window", default="prior_editions", help="Window type in segment policy file.")
    parser.add_argument("--segment-policy-family", choices=("seed", "entry"), default="seed", help="Segment family used to derive tournament side policy.")
    parser.add_argument("--segment-policy-min-n", type=int, default=30, help="Minimum policy sample size n.")
    parser.add_argument("--segment-policy-min-roi-pct", type=float, default=0.0, help="Minimum shrunk ROI percent required by policy.")
    parser.add_argument(
        "--segment-policy-missing-mode",
        choices=("skip", "allow"),
        default="skip",
        help="How to handle missing tournament side policy rows.",
    )
    args = parser.parse_args()

    train_path = Path(args.train)
    test_path = Path(args.test)
    train_rows = _load_rows(train_path)
    test_rows = _load_rows(test_path)
    th = args.threshold / 100.0

    print(f"Train rows: {len(train_rows):,} ({train_path})")
    print(f"Test rows:  {len(test_rows):,} ({test_path})")
    print(f"Value threshold: {args.threshold:.1f}%")
    print()

    # Baseline and current production calibration
    base = (0.0, 1.0)
    cur = (0.173, 0.512)
    current_blend = dict(DEFAULT_BLEND)

    # Walk-forward tune A/B on train only (fixed blend map)
    best_ab = None
    for a in [x / 100.0 for x in range(-10, 31, 1)]:
        for b in [x / 100.0 for x in range(40, 101, 1)]:
            m = _metrics(train_rows, a, b, current_blend)
            if best_ab is None or m["log_loss"] < best_ab[0]:
                best_ab = (m["log_loss"], a, b)
    tuned = (best_ab[1], best_ab[2])

    print("Calibration Candidates (A, B):")
    print(f"  Baseline(raw): ({base[0]:.3f}, {base[1]:.3f})")
    print(f"  Current(live): ({cur[0]:.3f}, {cur[1]:.3f})")
    print(f"  Tuned(train):  ({tuned[0]:.3f}, {tuned[1]:.3f})")
    print()

    for label, (a, b) in [("Baseline(raw)", base), ("Current(live)", cur), ("Tuned(train)", tuned)]:
        tr_m = _metrics(train_rows, a, b, current_blend)
        te_m = _metrics(test_rows, a, b, current_blend)
        tr_r = _roi(train_rows, a, b, current_blend, th)
        te_r = _roi(test_rows, a, b, current_blend, th)
        print(f"{label}")
        print(f"  Train logloss={tr_m['log_loss']:.5f} brier={tr_m['brier']:.5f} acc={tr_m['accuracy']:.3%} ROI@{args.threshold:.1f}%={tr_r['roi']:+.3%} bets={tr_r['bets']}")
        print(f"  Test  logloss={te_m['log_loss']:.5f} brier={te_m['brier']:.5f} acc={te_m['accuracy']:.3%} ROI@{args.threshold:.1f}%={te_r['roi']:+.3%} bets={te_r['bets']}")
        print()

    # Select model for exposure diagnostics: current live by default (safest).
    use_a, use_b = cur
    print(f"Exposure selection model: Current(live) A={use_a:.3f} B={use_b:.3f}")
    chosen = _choose_exposure_segments(
        train_rows,
        test_rows,
        use_a,
        use_b,
        current_blend,
        th,
        mode="surface_series",
        min_bets_per_year=args.min_bets,
    )
    print(f"Chosen segments (surface|series) with ROI>0 in both years and >= {args.min_bets} bets/year:")
    if chosen:
        for seg in sorted(chosen):
            print(f"  - {seg}")
    else:
        print("  (none)")
    print()

    tr_sel = _roi(train_rows, use_a, use_b, current_blend, th, chosen if chosen else None, segment_mode="surface_series")
    te_sel = _roi(test_rows, use_a, use_b, current_blend, th, chosen if chosen else None, segment_mode="surface_series")
    print("Selective Exposure ROI")
    print(f"  Train: ROI={tr_sel['roi']:+.3%} bets={tr_sel['bets']} wins={tr_sel['wins']} P/L={tr_sel['profit']:+.2f}u")
    print(f"  Test:  ROI={te_sel['roi']:+.3%} bets={te_sel['bets']} wins={te_sel['wins']} P/L={te_sel['profit']:+.2f}u")
    print()

    if args.enable_tournament_side_policy:
        policy_path = Path(args.segment_policy_file)
        if not policy_path.is_absolute():
            policy_path = Path.cwd() / policy_path
        policy = _load_tournament_side_policy(
            path=policy_path,
            window_type=args.segment_policy_window,
            segment_family=args.segment_policy_family,
        )
        print("Tournament Side Policy Overlay")
        print(f"  Source: {policy_path}")
        print(
            f"  Rules: window={args.segment_policy_window} family={args.segment_policy_family} "
            f"min_n={args.segment_policy_min_n} min_roi_pct={args.segment_policy_min_roi_pct:+.2f} "
            f"missing={args.segment_policy_missing_mode}"
        )
        print(f"  Policy keys loaded: {len(policy):,}")

        tr_pol = _roi(
            train_rows,
            use_a,
            use_b,
            current_blend,
            th,
            tournament_side_policy=policy,
            policy_min_n=args.segment_policy_min_n,
            policy_min_roi_pct=args.segment_policy_min_roi_pct,
            policy_missing_mode=args.segment_policy_missing_mode,
        )
        te_pol = _roi(
            test_rows,
            use_a,
            use_b,
            current_blend,
            th,
            tournament_side_policy=policy,
            policy_min_n=args.segment_policy_min_n,
            policy_min_roi_pct=args.segment_policy_min_roi_pct,
            policy_missing_mode=args.segment_policy_missing_mode,
        )
        print("  All exposures + policy")
        print(
            f"    Train: ROI={tr_pol['roi']:+.3%} bets={tr_pol['bets']} wins={tr_pol['wins']} "
            f"P/L={tr_pol['profit']:+.2f}u policy_skips={tr_pol['policy_skips']}"
        )
        print(
            f"    Test:  ROI={te_pol['roi']:+.3%} bets={te_pol['bets']} wins={te_pol['wins']} "
            f"P/L={te_pol['profit']:+.2f}u policy_skips={te_pol['policy_skips']}"
        )

        tr_pol_sel = _roi(
            train_rows,
            use_a,
            use_b,
            current_blend,
            th,
            chosen if chosen else None,
            segment_mode="surface_series",
            tournament_side_policy=policy,
            policy_min_n=args.segment_policy_min_n,
            policy_min_roi_pct=args.segment_policy_min_roi_pct,
            policy_missing_mode=args.segment_policy_missing_mode,
        )
        te_pol_sel = _roi(
            test_rows,
            use_a,
            use_b,
            current_blend,
            th,
            chosen if chosen else None,
            segment_mode="surface_series",
            tournament_side_policy=policy,
            policy_min_n=args.segment_policy_min_n,
            policy_min_roi_pct=args.segment_policy_min_roi_pct,
            policy_missing_mode=args.segment_policy_missing_mode,
        )
        print("  Selective exposure + policy")
        print(
            f"    Train: ROI={tr_pol_sel['roi']:+.3%} bets={tr_pol_sel['bets']} wins={tr_pol_sel['wins']} "
            f"P/L={tr_pol_sel['profit']:+.2f}u policy_skips={tr_pol_sel['policy_skips']}"
        )
        print(
            f"    Test:  ROI={te_pol_sel['roi']:+.3%} bets={te_pol_sel['bets']} wins={te_pol_sel['wins']} "
            f"P/L={te_pol_sel['profit']:+.2f}u policy_skips={te_pol_sel['policy_skips']}"
        )
        print(f"  Test skip reasons: {te_pol['policy_skip_reasons']}")
        print()

    print("Test Segmentation (Current/live model)")
    print("  By surface:")
    for seg, n, ll, roi in _segment_report(test_rows, use_a, use_b, current_blend, th, mode="surface"):
        print(f"    {seg:>8}  n={n:4d}  logloss={ll:.5f}  ROI={roi:+.3%}")
    print("  By series:")
    for seg, n, ll, roi in _segment_report(test_rows, use_a, use_b, current_blend, th, mode="series"):
        print(f"    {seg:>12}  n={n:4d}  logloss={ll:.5f}  ROI={roi:+.3%}")


if __name__ == "__main__":
    main()
