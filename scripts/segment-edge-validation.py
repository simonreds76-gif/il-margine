#!/usr/bin/env python3
"""
Segment Edge Validation — segment-edge-validation.py
=====================================================
The model loses money across the board (log-loss 0.630 vs Pinnacle 0.580).
But Masters 1000 Hard shows +5.1% ROI in 2024 and +11-13% historically.

This script answers the only question that matters now:
  Is the Masters 1000 edge real, or survivorship bias?

Four tests:

  1. YEAR-BY-YEAR STABILITY
     Does Masters 1000 show positive ROI in EACH year independently?
     If it's +20% in 2022 and -15% in 2023, the average is misleading.

  2. SEGMENT MULTIPLICITY CORRECTION
     You tested many segments (4 surfaces x 5 tiers x 3 confidence levels
     = 60 combinations). Finding 1 profitable segment out of 60 by chance
     at p=0.05 is almost guaranteed. Bonferroni-corrected significance test.

  3. WHY MASTERS 1000 MIGHT BE DIFFERENT
     Hypothesis: the model's Elo and rank signals are most informative for
     top players at big events. At lower tiers, player quality is noisier,
     data is sparser, and upsets are more random. Test this by comparing
     model log-loss vs Pinnacle log-loss BY SEGMENT. If the gap is smaller
     for Masters 1000, the model has relatively more value there.

  4. FORWARD-LOOKING EXPECTED VALUE
     Given the segment's historical ROI, bet volume, and variance,
     what's the probability of profit over the next 6 months?

Usage:
  python scripts/segment-edge-validation.py --files data/backtest/backtest-results-2022.csv data/backtest/backtest-results-2023.csv data/backtest/backtest-results-2024.csv

Output:
  data/diagnostics/segment-validation-report.txt
  data/diagnostics/segment-year-stability.png
  data/diagnostics/segment-logloss-gap.png
"""

import os
import sys
import csv
import math
import argparse
from collections import defaultdict

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

CS = {"bg": "#0d0d0d", "fg": "#e0e0e0", "accent": "#10b981", "accent2": "#f59e0b",
      "accent3": "#ef4444", "grid": "#2a2a2a", "accent4": "#8b5cf6"}

def apply_dark_style(fig, ax):
    fig.patch.set_facecolor(CS["bg"])
    ax.set_facecolor(CS["bg"])
    ax.tick_params(colors=CS["fg"])
    ax.xaxis.label.set_color(CS["fg"])
    ax.yaxis.label.set_color(CS["fg"])
    ax.title.set_color(CS["fg"])
    for spine in ax.spines.values():
        spine.set_color(CS["grid"])
    ax.grid(True, alpha=0.3, color=CS["grid"])


def _float(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        try:
            sample = f.read(2048)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            reader = csv.DictReader(f, dialect=dialect)
        except csv.Error:
            f.seek(0)
            reader = csv.DictReader(f)
        return [{k: (v if v else None) for k, v in row.items()} for row in reader]


def detect_columns(rows):
    """Auto-detect key columns. Supports backtest format and generic format."""
    keys = set(rows[0].keys()) if rows else set()
    def find(candidates):
        for c in candidates:
            if c in keys:
                return c
        return None
    return {
        "prob": find(["p1_win_prob", "model_p1", "prob_p1", "our_prob"]),
        "odds1": find(["odds1", "model_odds1", "fair_odds1", "our_odds"]),
        "odds2": find(["odds2", "model_odds2", "fair_odds2"]),
        "pin1": find(["pinnacle_odds1", "pin_odds1", "closing_odds1", "pinnacle_odds"]),
        "pin2": find(["pinnacle_odds2", "pin_odds2", "closing_odds2", "pinnacle_odds_loser"]),
        "won": find(["p1_won", "p1_win", "result", "bet_result"]),
        "wid": find(["winner_id", "actual_winner_id"]),
        "p1id": find(["player1_id", "p1_id"]),
        "surface": find(["surface"]),
        "tier": find(["tier", "series", "tournament_tier", "tour_tier", "category"]),
        "confidence": find(["confidence", "conf", "signal_confidence"]),
        "date": find(["date", "match_date"]),
        "year": find(["year"]),
        "bet_side": find(["bet_side"]),
        "value_pct": find(["value_pct", "edge_pct"]),
        "pinnacle_prob_novig": find(["pinnacle_prob_novig"]),
    }


def get_outcome(row, cm):
    """Return 1.0 if P1 won, 0.0 if P2, None if unknown."""
    if cm["won"]:
        v = str(row.get(cm["won"], "")).strip().lower()
        if v in ("1", "true", "yes", "w", "win"): return 1.0
        if v in ("0", "false", "no", "l", "loss"): return 0.0
    if cm["wid"] and cm["p1id"]:
        try:
            return 1.0 if int(float(row[cm["wid"]])) == int(float(row[cm["p1id"]])) else 0.0
        except: pass
    return None


def classify_tier(row, cm):
    tier = row.get(cm["tier"]) if cm["tier"] else None
    if tier:
        return str(tier).strip()
    return "Unknown"


def get_year(row, cm):
    if cm["year"]:
        v = row.get(cm["year"])
        if v:
            try: return int(float(v))
            except: pass
    if cm["date"]:
        d = row.get(cm["date"])
        if d and len(str(d)) >= 4:
            try: return int(str(d)[:4])
            except: pass
    return None


def _model_sharpens_favourite(row, cm, min_disagree=0.02):
    """True if model says favourite is MORE of a favourite than Pinnacle (by >= min_disagree)."""
    our_prob = _float(row.get(cm["prob"]))
    pin1 = _float(row.get(cm["pin1"]))
    pin2 = _float(row.get(cm["pin2"]))
    pin_novig = _float(row.get(cm["pinnacle_prob_novig"]))
    if our_prob is None or not pin1 or not pin2 or pin1 <= 1 or pin2 <= 1:
        return False
    if pin_novig is None:
        pin_novig = (1.0 / pin1) / (1.0 / pin1 + 1.0 / pin2) if (pin1 and pin2) else 0.5
    if pin1 < pin2:
        fav_is_p1 = True
        pin_fav = pin_novig
    else:
        fav_is_p1 = False
        pin_fav = 1.0 - pin_novig
    if fav_is_p1:
        model_fav = our_prob
        return model_fav > pin_fav and (model_fav - pin_fav) >= min_disagree
    else:
        model_fav = 1.0 - our_prob
        return model_fav > pin_fav and (model_fav - pin_fav) >= min_disagree


def extract_bets_backtest_format(rows, cm, surface_filter=None, tier_filter=None, threshold=10, sharpen_favourite=False):
    """
    Backtest format: one bet per row (bet_side = winner/loser), value_pct, bet_result.
    player1 = actual winner, our_prob = P(player1 wins).
    If sharpen_favourite: only include rows where model sharpens the favourite (model fav prob > Pinnacle fav prob by >=2pp).
    """
    bets = []
    for row in rows:
        if str(row.get("policy_excluded") or "").strip().lower() in ("true", "1", "yes"):
            continue
        value_pct = _float(row.get(cm["value_pct"]))
        if value_pct is None or value_pct < threshold:
            continue
        if sharpen_favourite and not _model_sharpens_favourite(row, cm):
            continue
        bet_side = str(row.get(cm["bet_side"], "")).strip().lower()
        bet_result = str(row.get(cm["won"], "")).strip().lower()
        pin1 = _float(row.get(cm["pin1"]))
        pin2 = _float(row.get(cm["pin2"]))
        our_prob = _float(row.get(cm["prob"]))
        pin_novig = _float(row.get(cm["pinnacle_prob_novig"]))

        surface = (row.get(cm["surface"]) or "Unknown").strip() if cm["surface"] else "Unknown"
        tier = classify_tier(row, cm)
        year = get_year(row, cm)

        if surface_filter and surface.lower() != surface_filter.lower():
            continue
        if tier_filter and tier_filter.lower() not in tier.lower():
            continue

        if bet_side in ("winner", "fav", "favorite", "1"):
            odds_used = pin1
            prob_used = our_prob
            outcome = 1.0 if bet_result in ("win", "w", "1", "true", "yes") else 0.0
        elif bet_side in ("loser", "dog", "underdog", "2"):
            odds_used = pin2
            prob_used = 1.0 - our_prob if our_prob is not None else 0.5
            outcome = 0.0 if bet_result in ("win", "w", "1", "true", "yes") else 1.0
        else:
            continue

        if odds_used is None or odds_used <= 1:
            continue

        pnl = (odds_used - 1.0) if bet_result in ("win", "w", "1", "true", "yes") else -1.0

        eps = 1e-10
        p_clamped = max(eps, min(1 - eps, prob_used))
        model_ll = -(outcome * math.log(p_clamped) + (1 - outcome) * math.log(1 - p_clamped))
        pin_implied = 1.0 / odds_used
        if pin_novig and bet_side in ("winner", "fav", "favorite", "1"):
            pin_prob = pin_novig
        elif pin_novig and bet_side in ("loser", "dog", "underdog", "2"):
            pin_prob = 1.0 - pin_novig
        else:
            pin_prob = pin_implied / (1.0 / pin1 + 1.0 / pin2) if pin1 and pin2 and pin2 > 1 else pin_implied
        pin_prob = max(eps, min(1 - eps, pin_prob))
        pin_ll = -(outcome * math.log(pin_prob) + (1 - outcome) * math.log(1 - pin_prob))

        bets.append({
            "edge": value_pct, "pnl": pnl, "prob": prob_used, "outcome": outcome,
            "pin_odds": odds_used, "model_odds": 1.0 / prob_used if prob_used and prob_used > 0 else 0,
            "surface": surface, "tier": tier, "year": year,
            "model_ll": model_ll, "pin_ll": pin_ll,
        })
    return bets


def extract_bets(rows, cm, surface_filter=None, tier_filter=None, threshold=10, sharpen_favourite=False):
    """Extract bets. Uses backtest format if bet_side/value_pct present, else generic format."""
    if cm["bet_side"] and cm["value_pct"]:
        return extract_bets_backtest_format(rows, cm, surface_filter, tier_filter, threshold, sharpen_favourite)

    bets = []
    for row in rows:
        prob = _float(row.get(cm["prob"]))
        pin1 = _float(row.get(cm["pin1"]))
        odds1 = _float(row.get(cm["odds1"]))
        outcome = get_outcome(row, cm)
        if not all([prob, pin1, odds1]) or outcome is None or pin1 <= 1 or odds1 <= 1:
            continue

        surface = (row.get(cm["surface"]) or "Unknown").strip() if cm["surface"] else "Unknown"
        tier = classify_tier(row, cm)
        year = get_year(row, cm)

        if surface_filter and surface.lower() != surface_filter.lower():
            continue
        if tier_filter and tier_filter.lower() not in tier.lower():
            continue

        pin_implied = 1.0 / pin1
        model_implied = 1.0 / odds1
        edge = (model_implied - pin_implied) / pin_implied * 100
        pnl = (pin1 - 1.0) if outcome > 0.5 else -1.0

        eps = 1e-10
        p_clamped = max(eps, min(1-eps, prob))
        model_ll = -(outcome * math.log(p_clamped) + (1-outcome) * math.log(1-p_clamped))
        pin_prob = max(eps, min(1-eps, pin_implied))
        pin_ll = -(outcome * math.log(pin_prob) + (1-outcome) * math.log(1-pin_prob))

        bets.append({
            "edge": edge, "pnl": pnl, "prob": prob, "outcome": outcome,
            "pin_odds": pin1, "model_odds": odds1,
            "surface": surface, "tier": tier, "year": year,
            "model_ll": model_ll, "pin_ll": pin_ll,
        })

        pin2 = _float(row.get(cm["pin2"]))
        odds2 = _float(row.get(cm["odds2"]))
        if pin2 and odds2 and pin2 > 1 and odds2 > 1:
            pin_implied2 = 1.0 / pin2
            model_implied2 = 1.0 / odds2
            edge2 = (model_implied2 - pin_implied2) / pin_implied2 * 100
            pnl2 = (pin2 - 1.0) if outcome < 0.5 else -1.0
            p2_prob = 1.0 - prob
            p2_clamped = max(eps, min(1-eps, p2_prob))
            model_ll2 = -(((1-outcome) * math.log(p2_clamped)) + (outcome * math.log(1-p2_clamped)))
            pin_prob2 = max(eps, min(1-eps, pin_implied2))
            pin_ll2 = -(((1-outcome) * math.log(pin_prob2)) + (outcome * math.log(1-pin_prob2)))

            bets.append({
                "edge": edge2, "pnl": pnl2, "prob": p2_prob, "outcome": 1.0 - outcome,
                "pin_odds": pin2, "model_odds": odds2,
                "surface": surface, "tier": tier, "year": year,
                "model_ll": model_ll2, "pin_ll": pin_ll2,
            })

    return bets


# ------------------------------------------------------------------------------
# Test 1: Year-by-Year Stability
# ------------------------------------------------------------------------------

def test_year_stability(bets, threshold=10):
    """ROI for each year independently, at given threshold."""
    by_year = defaultdict(list)
    for b in bets:
        if b["edge"] >= threshold and b["year"] is not None:
            by_year[b["year"]].append(b["pnl"])

    results = []
    for year in sorted(by_year.keys()):
        pnls = np.array(by_year[year])
        n = len(pnls)
        if n < 3:
            continue
        roi = float(np.mean(pnls)) * 100
        std = float(np.std(pnls, ddof=1))
        se = std / math.sqrt(n)
        ci_lo = roi - 1.96 * se * 100
        ci_hi = roi + 1.96 * se * 100
        t_stat = (np.mean(pnls)) / se if se > 0 else 0
        from math import erf
        p_value = 0.5 * (1 - erf(t_stat / math.sqrt(2))) if t_stat > 0 else 1.0

        results.append({
            "year": year, "n": n, "roi": round(roi, 2),
            "ci_lo": round(ci_lo, 2), "ci_hi": round(ci_hi, 2),
            "pnl": round(float(np.sum(pnls)), 2),
            "win_rate": round(float(np.mean([1 if p > 0 else 0 for p in pnls])), 3),
            "t_stat": round(t_stat, 3),
            "p_value": round(p_value, 4),
        })
    return results


# ------------------------------------------------------------------------------
# Test 2: Multiple Comparison Correction
# ------------------------------------------------------------------------------

def test_multiple_comparisons(all_bets, threshold=10, n_bootstrap=5000):
    """
    How likely is it that at least one segment shows positive ROI by chance?
    Uses permutation test: shuffle outcomes, compute best segment ROI, repeat.
    """
    segments = defaultdict(list)
    for b in all_bets:
        if b["edge"] >= threshold:
            key = f"{b['surface']}|{b['tier']}"
            segments[key].append(b)

    seg_rois = {}
    for key, bets in segments.items():
        if len(bets) >= 10:
            seg_rois[key] = float(np.mean([b["pnl"] for b in bets])) * 100

    if not seg_rois:
        return {"n_segments_tested": 0}

    best_segment = max(seg_rois, key=seg_rois.get)
    best_roi = seg_rois[best_segment]

    qualifying_segments = {k: v for k, v in segments.items() if len(v) >= 10}
    all_qualifying = []
    seg_labels = []
    for key, bets in qualifying_segments.items():
        all_qualifying.extend(bets)
        seg_labels.extend([key] * len(bets))
    if len(all_qualifying) < 20:
        return {"n_segments_tested": len(seg_rois), "best_segment": best_segment, "best_roi": best_roi}

    outcomes = np.array([b["outcome"] for b in all_qualifying])
    pin_odds = np.array([b["pin_odds"] for b in all_qualifying])
    seg_labels = np.array(seg_labels)

    count_better = 0
    for _ in range(n_bootstrap):
        shuffled = np.random.permutation(outcomes)
        pnls = np.where(shuffled > 0.5, pin_odds - 1, -1.0)
        best_null = -999
        for key in set(seg_labels):
            mask = seg_labels == key
            if np.sum(mask) >= 10:
                null_roi = float(np.mean(pnls[mask])) * 100
                best_null = max(best_null, null_roi)
        if best_null >= best_roi:
            count_better += 1

    corrected_p = count_better / n_bootstrap

    return {
        "n_segments_tested": len(seg_rois),
        "best_segment": best_segment,
        "best_roi": round(best_roi, 2),
        "corrected_p_value": round(corrected_p, 4),
        "interpretation": "significant" if corrected_p < 0.05 else "not significant (could be chance)",
        "all_segments": dict(sorted(seg_rois.items(), key=lambda x: -x[1])),
    }


# ------------------------------------------------------------------------------
# Test 3: Log-Loss Gap by Segment
# ------------------------------------------------------------------------------

def test_logloss_gap(all_bets):
    """Compare model log-loss vs Pinnacle log-loss by segment."""
    by_segment = defaultdict(lambda: {"model_ll": [], "pin_ll": [], "n": 0})

    for b in all_bets:
        key = f"{b['surface']}|{b['tier']}"
        by_segment[key]["model_ll"].append(b["model_ll"])
        by_segment[key]["pin_ll"].append(b["pin_ll"])
        by_segment[key]["n"] += 1

    results = []
    for key, data in by_segment.items():
        if data["n"] < 20:
            continue
        model_ll = float(np.mean(data["model_ll"]))
        pin_ll = float(np.mean(data["pin_ll"]))
        gap = model_ll - pin_ll
        results.append({
            "segment": key,
            "n": data["n"],
            "model_ll": round(model_ll, 4),
            "pin_ll": round(pin_ll, 4),
            "gap": round(gap, 4),
            "model_relative_pct": round(gap / pin_ll * 100, 1) if pin_ll > 0 else 0,
        })

    return sorted(results, key=lambda x: x["gap"])


# ------------------------------------------------------------------------------
# Test 4: Forward-Looking Expected Value
# ------------------------------------------------------------------------------

def test_forward_ev(segment_bets, threshold=10, months=6, bets_per_month=8):
    """Given historical ROI and variance, what's P(profit) over next N months?"""
    qualifying = [b for b in segment_bets if b["edge"] >= threshold]
    if len(qualifying) < 10:
        return {"error": "insufficient data"}

    pnls = np.array([b["pnl"] for b in qualifying])
    mean_pnl = float(np.mean(pnls))
    std_pnl = float(np.std(pnls, ddof=1))

    n_future = months * bets_per_month
    expected_total = mean_pnl * n_future
    std_total = std_pnl * math.sqrt(n_future)

    if std_total > 0:
        z = expected_total / std_total
        from math import erf
        p_profit = 0.5 * (1 + erf(z / math.sqrt(2)))
    else:
        p_profit = 1.0 if expected_total > 0 else 0.0

    mc_profits = 0
    n_sim = 10000
    for _ in range(n_sim):
        sim_pnls = np.random.choice(pnls, size=n_future, replace=True)
        if np.sum(sim_pnls) > 0:
            mc_profits += 1
    mc_p_profit = mc_profits / n_sim

    return {
        "historical_roi_pct": round(mean_pnl * 100, 2),
        "historical_n": len(qualifying),
        "projected_bets": n_future,
        "projected_months": months,
        "expected_pnl": round(expected_total, 2),
        "std_pnl": round(std_total, 2),
        "p_profit_normal": round(p_profit, 3),
        "p_profit_mc": round(mc_p_profit, 3),
        "bets_per_month_assumed": bets_per_month,
    }


# ------------------------------------------------------------------------------
# Charts
# ------------------------------------------------------------------------------

def plot_year_stability(results, segment_label, out_path):
    if not HAS_MPL or not results:
        return
    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    apply_dark_style(fig, ax)

    years = [r["year"] for r in results]
    rois = [r["roi"] for r in results]
    ci_lo = [r["ci_lo"] for r in results]
    ci_hi = [r["ci_hi"] for r in results]
    n_bets = [r["n"] for r in results]

    x = np.arange(len(years))
    colors = [CS["accent"] if r > 0 else CS["accent3"] for r in rois]
    bars = ax.bar(x, rois, color=colors, alpha=0.8)

    for i, (lo, hi) in enumerate(zip(ci_lo, ci_hi)):
        ax.plot([i, i], [lo, hi], color=CS["fg"], linewidth=2, alpha=0.6)
        ax.plot([i-0.1, i+0.1], [lo, lo], color=CS["fg"], linewidth=2, alpha=0.6)
        ax.plot([i-0.1, i+0.1], [hi, hi], color=CS["fg"], linewidth=2, alpha=0.6)

    for i, (bar, n, p) in enumerate(zip(bars, n_bets, [r["p_value"] for r in results])):
        sig = "*" if p < 0.05 else ""
        ax.text(i, bar.get_height() + 2, f"n={n} {sig}", ha="center",
                fontsize=9, color=CS["fg"])

    ax.axhline(0, color=CS["accent3"], alpha=0.5, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years])
    ax.set_xlabel("Year")
    ax.set_ylabel("ROI (%)")
    ax.set_title(f"Year-by-Year ROI: {segment_label}", fontsize=13, fontweight="bold")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_logloss_gap(ll_results, out_path):
    if not HAS_MPL or not ll_results:
        return
    data = ll_results[:15]

    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    apply_dark_style(fig, ax)

    labels = [d["segment"] for d in data]
    gaps = [d["gap"] for d in data]
    n_vals = [d["n"] for d in data]
    colors = [CS["accent"] if g < 0.05 else CS["accent2"] if g < 0.08 else CS["accent3"] for g in gaps]

    bars = ax.barh(labels, gaps, color=colors, alpha=0.8)
    for bar, n in zip(bars, n_vals):
        ax.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height()/2,
                f"n={n}", va="center", fontsize=8, color=CS["fg"], alpha=0.7)

    ax.axvline(0, color=CS["fg"], alpha=0.3)
    ax.set_xlabel("Log-Loss Gap (Model - Pinnacle) - lower = model closer to Pinnacle")
    ax.set_title("Where the Model Has Most Relative Value", fontsize=13, fontweight="bold")
    ax.invert_yaxis()

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Segment Edge Validation")
    parser.add_argument("--files", nargs="+", required=True, help="Backtest CSV files (multiple years)")
    parser.add_argument("--threshold", type=int, default=10, help="Value threshold %%")
    parser.add_argument("--segment-surface", default=None, help="Surface filter for focal segment")
    parser.add_argument("--segment-tier", default=None, help="Tier filter for focal segment")
    parser.add_argument("--sharpen-favourite", action="store_true",
                        help="Only include bets where model sharpens favourite (model fav prob > Pinnacle by >=2pp)")
    parser.add_argument("--out-dir", default="data/diagnostics")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    np.random.seed(42)

    print("\n" + "="*72)
    print("  IL MARGINE - Segment Edge Validation")
    print("="*72)

    print("\n-- Loading data --")
    all_rows = []
    for p in args.files:
        rows = load_csv(p)
        print(f"  {len(rows):,} rows from {os.path.basename(p)}")
        all_rows.extend(rows)

    if not all_rows:
        print("No data.")
        sys.exit(1)

    cm = detect_columns(all_rows)
    print(f"  Columns detected: {', '.join(k + '=' + str(v) for k, v in cm.items() if v)}")

    all_bets = extract_bets(all_rows, cm, threshold=args.threshold, sharpen_favourite=args.sharpen_favourite)
    print(f"  Total bet opportunities: {len(all_bets):,}")

    focal_surface = args.segment_surface or "Hard"
    focal_tier = args.segment_tier if args.segment_tier and str(args.segment_tier).lower() not in ("", "all") else None
    focal_label = f"{focal_surface}|all" if focal_tier is None else f"{focal_surface}|{focal_tier}"

    def _matches_focal(seg):
        if focal_tier is None:
            return str(seg).startswith(focal_surface + "|")
        return focal_label.lower().replace(" ", "") in str(seg).lower().replace(" ", "")
    focal_bets = extract_bets(all_rows, cm, surface_filter=focal_surface, tier_filter=focal_tier,
                              threshold=args.threshold, sharpen_favourite=args.sharpen_favourite)
    print(f"  Focal segment ({focal_label}): {len(focal_bets):,} bet opportunities")

    report = []
    report.append("="*72)
    report.append(f"  SEGMENT EDGE VALIDATION: {focal_label}")
    report.append(f"  Threshold: >={args.threshold}%")
    if args.sharpen_favourite:
        report.append("  Filter: model sharpens favourite only (>=2pp)")
    report.append("="*72)

    print(f"\n-- Test 1: Year-by-Year Stability ({focal_label}, >={args.threshold}%) --")
    year_results = test_year_stability(focal_bets, threshold=args.threshold)

    report.append(f"\n  -- Test 1: Year-by-Year Stability --")
    report.append(f"  {'Year':>6} {'N':>6} {'ROI%':>8} {'CI Lo':>8} {'CI Hi':>8} {'WinR':>7} {'t':>7} {'p':>7}")
    all_positive = True
    for r in year_results:
        sig = " *" if r["p_value"] < 0.05 else ""
        report.append(f"  {r['year']:>6} {r['n']:>6} {r['roi']:>+7.1f}% {r['ci_lo']:>+7.1f}% "
                      f"{r['ci_hi']:>+7.1f}% {r['win_rate']:>6.1%} {r['t_stat']:>7.3f} {r['p_value']:>6.3f}{sig}")
        if r["roi"] < 0:
            all_positive = False
        print(f"  {r['year']}: ROI={r['roi']:+.1f}%, n={r['n']}, CI=[{r['ci_lo']:+.1f}%, {r['ci_hi']:+.1f}%], p={r['p_value']:.3f}")

    if all_positive and len(year_results) >= 2:
        report.append(f"\n  [PASS] Positive ROI in all years tested - good stability signal.")
    elif not all_positive:
        neg_years = [r["year"] for r in year_results if r["roi"] < 0]
        report.append(f"\n  [WARN] Negative ROI in year(s): {neg_years} - edge may not be stable.")

    print(f"\n-- Test 2: Multiple Comparison Correction --")
    mc_result = test_multiple_comparisons(all_bets, threshold=args.threshold, n_bootstrap=3000)

    report.append(f"\n  -- Test 2: Multiple Comparison Correction --")
    report.append(f"  Segments tested: {mc_result['n_segments_tested']}")
    if "best_segment" in mc_result:
        report.append(f"  Best segment: {mc_result['best_segment']} (ROI: {mc_result['best_roi']:+.1f}%)")
        report.append(f"  Corrected p-value: {mc_result['corrected_p_value']:.4f}")
        report.append(f"  Interpretation: {mc_result['interpretation']}")
        print(f"  Best: {mc_result['best_segment']} ROI={mc_result['best_roi']:+.1f}%, corrected p={mc_result['corrected_p_value']:.4f}")

        if mc_result.get("all_segments"):
            report.append(f"\n  Top segments (ROI at >={args.threshold}% edge):")
            for i, (seg, roi) in enumerate(list(mc_result["all_segments"].items())[:10]):
                marker = " <- focal" if _matches_focal(seg) else ""
                report.append(f"    {seg:<30} {roi:>+7.1f}%{marker}")

    print(f"\n-- Test 3: Log-Loss Gap by Segment --")
    ll_results = test_logloss_gap(all_bets)

    report.append(f"\n  -- Test 3: Log-Loss Gap (Model - Pinnacle, smaller = better) --")
    report.append(f"  {'Segment':<30} {'N':>6} {'Model LL':>9} {'Pin LL':>9} {'Gap':>7} {'Rel%':>7}")
    for i, r in enumerate(ll_results[:15]):
        marker = " <-" if _matches_focal(r["segment"]) else ""
        report.append(f"  {r['segment']:<30} {r['n']:>6} {r['model_ll']:>9.4f} {r['pin_ll']:>9.4f} "
                      f"{r['gap']:>+6.4f} {r['model_relative_pct']:>+6.1f}%{marker}")
        if i < 5:
            print(f"  {r['segment']}: gap={r['gap']:+.4f} (model {r['model_relative_pct']:+.1f}% vs Pinnacle)")

    print(f"\n-- Test 4: Forward-Looking Expected Value --")
    for months, bpm in [(6, 6), (6, 10), (12, 8)]:
        ev = test_forward_ev(focal_bets, threshold=args.threshold, months=months, bets_per_month=bpm)
        if "error" in ev:
            continue
        report.append(f"\n  -- Forward Projection: {months}m, ~{bpm} bets/month --")
        report.append(f"  Historical ROI: {ev['historical_roi_pct']:+.1f}% ({ev['historical_n']} bets)")
        report.append(f"  Projected bets: {ev['projected_bets']}")
        report.append(f"  Expected PnL: {ev['expected_pnl']:+.1f} units")
        report.append(f"  P(profit) normal approx: {ev['p_profit_normal']:.1%}")
        report.append(f"  P(profit) Monte Carlo: {ev['p_profit_mc']:.1%}")
        print(f"  {months}m @ {bpm}/mo: E[PnL]={ev['expected_pnl']:+.1f}, P(profit)={ev['p_profit_mc']:.1%}")

    report.append(f"\n{'='*72}")
    report.append(f"  VERDICT")
    report.append(f"{'='*72}")

    has_stability = all_positive and len(year_results) >= 2
    has_significance = mc_result.get("corrected_p_value", 1) < 0.10
    ll_focal = [r for r in ll_results if _matches_focal(r["segment"])]
    has_ll_advantage = ll_focal and ll_focal[0]["gap"] < 0.06

    if has_stability and has_significance and has_ll_advantage:
        report.append(f"\n  [STRONG] The {focal_label} edge passes all three tests.")
        report.append(f"    Year-stable, survives multiple comparison correction, and model")
        report.append(f"    has relatively low log-loss gap in this segment.")
        report.append(f"    Recommendation: continue live trading this segment with confidence.")
    elif has_stability and (has_significance or has_ll_advantage):
        report.append(f"\n  [MODERATE] The {focal_label} edge passes some tests.")
        report.append(f"    Continue with caution. Collect more data before scaling up.")
    else:
        report.append(f"\n  [WEAK] The {focal_label} edge does not pass validation.")
        report.append(f"    The positive ROI may be due to chance (multiple comparisons)")
        report.append(f"    or a small sample. Do not rely on this for capital allocation.")
        report.append(f"    Continue collecting data; reassess after 200+ settled bets in segment.")

    report.append(f"\n{'='*72}\n")

    report_text = "\n".join(report)
    print(f"\n{report_text}")

    report_path = os.path.join(args.out_dir, "segment-validation-report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  Saved: {report_path}")

    if HAS_MPL:
        print(f"\n-- Charts --")
        plot_year_stability(year_results, focal_label,
                           os.path.join(args.out_dir, "segment-year-stability.png"))
        plot_logloss_gap(ll_results,
                         os.path.join(args.out_dir, "segment-logloss-gap.png"))

    print(f"\n  Done.\n")


if __name__ == "__main__":
    main()
