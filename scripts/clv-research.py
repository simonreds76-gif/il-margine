#!/usr/bin/env python3
"""
CLV Research Framework — clv-research.py
==========================================
Research sprint: Market Timing (CLV at open vs close)

Hypothesis: Pinnacle's opening lines for ATP matches are softer than
closing lines. If the model's fair odds anticipate the direction of
line movement, that CLV can be captured by betting early at soft books.

This script works with whatever Pinnacle snapshot data exists:

  Mode A: Multiple snapshots per match in Supabase (bookmaker_odds_snapshot)
          -> measures actual open-to-close movement per match

  Mode B: Backtest data with single Pinnacle closing odds
          -> estimates CLV by comparing model odds to closing odds
          (less powerful but still informative)

  Mode C: Compare daily snapshots across days
          -> if you have snapshots from day N-1 and day N for the same
          match, that's an approximate open vs close pair

Outputs:
  data/diagnostics/clv-research-report.txt
  data/diagnostics/clv-disagreement-dist.png
  data/diagnostics/clv-accuracy-by-disagree.png
  data/diagnostics/clv-segment-accuracy.png

Usage:
  # From backtest data (Mode B)
  python scripts/clv-research.py --backtest data/backtest/backtest-results-2024.csv

  # All three years for maximum sample size
  python scripts/clv-research.py --backtest data/backtest/backtest-results-2022.csv data/backtest/backtest-results-2023.csv data/backtest/backtest-results-2024.csv
"""

import os
import sys
import csv
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
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        return [{k: (v if v else None) for k, v in row.items()} for row in reader]


def detect_columns(rows):
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
        "bet_side": find(["bet_side"]),
        "surface": find(["surface"]),
        "tier": find(["tier", "series", "tournament_tier", "category"]),
        "date": find(["date", "match_date"]),
        "year": find(["year"]),
    }


def get_outcome(row, cm):
    """Return 1.0 if P1 won, 0.0 if P2 won."""
    if cm["bet_side"] and cm["won"]:
        side = str(row.get(cm["bet_side"], "")).strip().lower()
        result = str(row.get(cm["won"], "")).strip().lower()
        won = result in ("win", "w", "1", "true", "yes")
        if side in ("winner", "fav", "favorite", "1"):
            return 1.0 if won else 0.0
        if side in ("loser", "dog", "underdog", "2"):
            return 0.0 if won else 1.0
    if cm["won"]:
        v = str(row.get(cm["won"], "")).strip().lower()
        if v in ("1", "true", "yes", "w", "win"): return 1.0
        if v in ("0", "false", "no", "l", "loss"): return 0.0
    if cm["wid"] and cm["p1id"]:
        try:
            return 1.0 if int(float(row[cm["wid"]])) == int(float(row[cm["p1id"]])) else 0.0
        except: pass
    return None


def analyse_backtest_clv(rows, cm):
    """
    Analyse CLV-related signals from backtest data.
    Backtest format: player1=winner, our_prob=P(player1 wins), pinnacle_odds/pinnacle_odds_loser.
    """
    matches = []

    for row in rows:
        prob = _float(row.get(cm["prob"]))
        pin1 = _float(row.get(cm["pin1"]))
        pin2 = _float(row.get(cm["pin2"]))
        odds1 = _float(row.get(cm["odds1"]))
        outcome = get_outcome(row, cm)

        if not all([prob, pin1]) or outcome is None or pin1 <= 1:
            continue

        pin_implied = 1.0 / pin1
        model_implied = prob

        if pin2 and pin2 > 1:
            pin_implied2 = 1.0 / pin2
            total_imp = pin_implied + pin_implied2
            pin_fair = pin_implied / total_imp if total_imp > 0 else pin_implied
        else:
            pin_fair = pin_implied

        surface = (row.get(cm["surface"]) or "Unknown").strip() if cm["surface"] else "Unknown"
        tier = (row.get(cm["tier"]) or "Unknown").strip() if cm["tier"] else "Unknown"

        disagreement = model_implied - pin_fair
        disagree_pct = disagreement / pin_fair * 100 if pin_fair > 0 else 0

        model_direction_correct = (disagreement > 0 and outcome > 0.5) or (disagreement < 0 and outcome < 0.5)

        if disagreement > 0:
            pnl = (pin1 - 1.0) if outcome > 0.5 else -1.0
            bet_odds = pin1
        else:
            if pin2 and pin2 > 1:
                pnl = (pin2 - 1.0) if outcome < 0.5 else -1.0
                bet_odds = pin2
            else:
                continue

        matches.append({
            "model_prob": model_implied,
            "pin_fair": pin_fair,
            "pin_raw": pin_implied,
            "disagreement": disagreement,
            "disagree_pct": disagree_pct,
            "direction_correct": model_direction_correct,
            "outcome": outcome,
            "pnl": pnl,
            "bet_odds": bet_odds,
            "surface": surface,
            "tier": tier,
        })

    return matches


def compute_directional_accuracy(matches, min_disagree=0.0):
    filtered = [m for m in matches if abs(m["disagreement"]) >= min_disagree]
    if not filtered:
        return {"n": 0, "accuracy": 0, "z_score": 0, "p_value": 1.0, "significant": False}

    correct = sum(1 for m in filtered if m["direction_correct"])
    n = len(filtered)

    from math import sqrt, erf
    se = sqrt(0.25 / n) if n > 0 else 1
    z = ((correct / n) - 0.5) / se if se > 0 else 0
    p_value = 0.5 * (1 - erf(z / sqrt(2))) if z > 0 else 1.0

    return {
        "n": n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n > 0 else 0,
        "z_score": round(z, 3),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
    }


def roi_by_disagreement_band(matches):
    bands = [
        ("0-2% disagree", 0, 0.02),
        ("2-5% disagree", 0.02, 0.05),
        ("5-10% disagree", 0.05, 0.10),
        ("10-20% disagree", 0.10, 0.20),
        ("20%+ disagree", 0.20, 1.0),
    ]
    results = []
    for label, lo, hi in bands:
        filtered = [m for m in matches if lo <= abs(m["disagreement"]) < hi]
        if len(filtered) < 10:
            continue
        pnls = [m["pnl"] for m in filtered]
        accuracy = np.mean([1 if m["direction_correct"] else 0 for m in filtered])
        results.append({
            "band": label,
            "n": len(filtered),
            "roi_pct": round(np.mean(pnls) * 100, 2),
            "direction_accuracy": round(accuracy, 3),
            "avg_disagree": round(np.mean([abs(m["disagreement"]) for m in filtered]), 4),
            "avg_odds": round(np.mean([m["bet_odds"] for m in filtered]), 2),
        })
    return results


def roi_by_direction_and_odds(matches):
    sharpen = [m for m in matches if m["disagreement"] > 0.02 and m["pin_fair"] > 0.5]
    contrarian = [m for m in matches if m["disagreement"] < -0.02 and m["pin_fair"] > 0.5]

    results = {}
    for label, group in [("Model sharpens favourite", sharpen), ("Model backs underdog", contrarian)]:
        if len(group) < 10:
            results[label] = {"n": len(group), "roi_pct": None}
            continue
        pnls = [m["pnl"] for m in group]
        accuracy = np.mean([1 if m["direction_correct"] else 0 for m in group])
        results[label] = {
            "n": len(group),
            "roi_pct": round(np.mean(pnls) * 100, 2),
            "direction_accuracy": round(accuracy, 3),
            "win_rate": round(np.mean([1 if p > 0 else 0 for p in pnls]), 3),
        }
    return results


def clv_by_segment(matches):
    by_seg = defaultdict(list)
    for m in matches:
        key = f"{m['surface']}|{m['tier']}"
        by_seg[key].append(m)

    results = []
    for key, group in by_seg.items():
        if len(group) < 20:
            continue
        correct = sum(1 for m in group if m["direction_correct"])
        pnls = [m["pnl"] for m in group]
        strong_disagree = [m for m in group if abs(m["disagreement"]) > 0.02]
        strong_correct = sum(1 for m in strong_disagree if m["direction_correct"]) if strong_disagree else 0
        results.append({
            "segment": key,
            "n": len(group),
            "direction_accuracy": round(correct / len(group), 3),
            "strong_disagree_n": len(strong_disagree),
            "strong_accuracy": round(strong_correct / len(strong_disagree), 3) if strong_disagree else None,
            "roi_all": round(np.mean(pnls) * 100, 2),
        })
    return sorted(results, key=lambda x: (-(x["strong_accuracy"] or 0), x["strong_disagree_n"]))


def estimate_tradeable_edge(matches):
    thresholds = [0.01, 0.02, 0.03, 0.05, 0.08, 0.10]
    results = []

    for thresh in thresholds:
        da = compute_directional_accuracy(matches, min_disagree=thresh)
        if da["n"] < 20:
            continue

        accuracy = da["accuracy"]
        n = da["n"]
        avg_movement_pct = 3.0
        expected_clv = (2 * accuracy - 1) * avg_movement_pct
        net_edge = expected_clv - 2.5

        results.append({
            "threshold": thresh,
            "n_matches": n,
            "accuracy": round(accuracy, 3),
            "estimated_clv_pct": round(expected_clv, 2),
            "estimated_net_edge_pct": round(net_edge, 2),
            "profitable": net_edge > 0,
        })

    return results


def plot_disagreement_distribution(matches, out_path):
    if not HAS_MPL:
        return
    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    apply_dark_style(fig, ax)

    disagrees = [m["disagreement"] * 100 for m in matches]
    ax.hist(disagrees, bins=60, color=CS["accent"], alpha=0.7, edgecolor=CS["bg"])
    ax.axvline(0, color=CS["accent3"], alpha=0.7, linestyle="--", label="Agreement")
    mean_d = np.mean(disagrees)
    ax.axvline(mean_d, color=CS["accent2"], alpha=0.7, linestyle=":", label=f"Mean: {mean_d:+.1f}pp")
    ax.set_xlabel("Model - Pinnacle (percentage points)")
    ax.set_ylabel("Frequency")
    ax.set_title("Model vs Pinnacle Disagreement Distribution", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_accuracy_by_disagreement(bands, out_path):
    if not HAS_MPL or not bands:
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor(CS["bg"])
    for ax in [ax1, ax2]:
        apply_dark_style(fig, ax)

    labels = [b["band"] for b in bands]
    accuracy = [b["direction_accuracy"] for b in bands]
    roi = [b["roi_pct"] for b in bands]
    n_vals = [b["n"] for b in bands]
    x = np.arange(len(labels))

    colors_acc = [CS["accent"] if a > 0.52 else CS["accent2"] if a > 0.48 else CS["accent3"] for a in accuracy]
    bars1 = ax1.bar(x, [a * 100 for a in accuracy], color=colors_acc, alpha=0.8)
    ax1.axhline(50, color=CS["fg"], alpha=0.5, linestyle="--", label="50% (random)")
    for i, (bar, n) in enumerate(zip(bars1, n_vals)):
        ax1.text(i, bar.get_height() + 0.5, f"n={n}", ha="center", fontsize=8, color=CS["fg"])
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    ax1.set_ylabel("Directional Accuracy (%)")
    ax1.set_title("Accuracy by Disagreement Size", fontsize=11, fontweight="bold")
    ax1.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=8)

    colors_roi = [CS["accent"] if r > 0 else CS["accent3"] for r in roi]
    ax2.bar(x, roi, color=colors_roi, alpha=0.8)
    ax2.axhline(0, color=CS["fg"], alpha=0.5, linestyle="--")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    ax2.set_ylabel("ROI (%)")
    ax2.set_title("ROI by Disagreement Size", fontsize=11, fontweight="bold")

    fig.suptitle("Model Directional Accuracy & ROI vs Disagreement with Pinnacle",
                 color=CS["fg"], fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_segment_accuracy(seg_results, out_path):
    if not HAS_MPL or not seg_results:
        return
    data = [s for s in seg_results if s["strong_accuracy"] is not None][:12]
    if not data:
        return

    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    apply_dark_style(fig, ax)

    labels = [d["segment"] for d in data]
    accuracy = [d["strong_accuracy"] * 100 for d in data]
    n_vals = [d["strong_disagree_n"] for d in data]
    colors = [CS["accent"] if a > 52 else CS["accent2"] if a > 48 else CS["accent3"] for a in accuracy]

    bars = ax.barh(labels, accuracy, color=colors, alpha=0.8)
    ax.axvline(50, color=CS["fg"], alpha=0.5, linestyle="--")
    for bar, n in zip(bars, n_vals):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                f"n={n}", va="center", fontsize=8, color=CS["fg"])
    ax.set_xlabel("Directional Accuracy (%) - where model strongly disagrees with Pinnacle")
    ax.set_title("Which Segments Does the Model Predict Line Direction Best?",
                 fontsize=12, fontweight="bold")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="CLV Research Framework")
    parser.add_argument("--backtest", nargs="+", help="Backtest CSV files (Mode B)")
    parser.add_argument("--out-dir", default="data/diagnostics")
    args = parser.parse_args()

    if not args.backtest:
        print("Usage: python scripts/clv-research.py --backtest data/backtest/backtest-results-2024.csv")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)
    np.random.seed(42)

    print("\n" + "="*72)
    print("  IL MARGINE - CLV Research: Market Timing Edge")
    print("="*72)

    print("\n-- Loading data --")
    all_rows = []
    for p in args.backtest:
        rows = load_csv(p)
        print(f"  {len(rows):,} rows from {os.path.basename(p)}")
        all_rows.extend(rows)

    cm = detect_columns(all_rows)
    matches = analyse_backtest_clv(all_rows, cm)
    print(f"  Analysed {len(matches):,} matches with model + Pinnacle odds")

    report = []
    report.append("="*72)
    report.append("  CLV RESEARCH: Market Timing Edge")
    report.append("="*72)
    report.append(f"\n  Matches analysed: {len(matches):,}")

    print(f"\n-- 1. Model vs Pinnacle Disagreement --")
    disagrees = [m["disagreement"] for m in matches]
    abs_disagrees = [abs(d) for d in disagrees]
    report.append(f"\n  -- Model vs Pinnacle Disagreement --")
    report.append(f"  Mean disagreement: {np.mean(disagrees)*100:+.2f} percentage points")
    report.append(f"  Mean absolute disagreement: {np.mean(abs_disagrees)*100:.2f} pp")
    report.append(f"  Median absolute: {np.median(abs_disagrees)*100:.2f} pp")
    report.append(f"  Model favours P1 more often: {np.mean([1 if d > 0 else 0 for d in disagrees]):.1%}")
    print(f"  Mean |disagreement|: {np.mean(abs_disagrees)*100:.2f}pp")

    print(f"\n-- 2. Directional Accuracy --")
    report.append(f"\n  -- Directional Accuracy --")
    report.append(f"  When model disagrees with Pinnacle, does the outcome go the model's way?")
    report.append(f"  >50% = model adds information; =50% = noise; <50% = anti-informative\n")
    report.append(f"  {'Min disagree':>14} {'N':>6} {'Accuracy':>9} {'z':>7} {'p':>7} {'Sig?':>6}")

    for thresh in [0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15]:
        da = compute_directional_accuracy(matches, min_disagree=thresh)
        if da["n"] < 10:
            continue
        sig = "*" if da.get("significant") else ""
        report.append(f"  {thresh*100:>13.0f}pp {da['n']:>6} {da['accuracy']:>8.1%} "
                      f"{da['z_score']:>7.2f} {da['p_value']:>6.3f}  {sig}")
        if thresh in (0.0, 0.02, 0.05):
            print(f"  >={thresh*100:.0f}pp: {da['accuracy']:.1%} accurate (n={da['n']}, p={da['p_value']:.3f})")

    print(f"\n-- 3. ROI by Disagreement Band --")
    bands = roi_by_disagreement_band(matches)
    report.append(f"\n  -- ROI by Disagreement Band --")
    report.append(f"  Betting the model's side at Pinnacle closing odds:\n")
    report.append(f"  {'Band':<22} {'N':>6} {'ROI%':>8} {'DirAcc':>8} {'AvgOdds':>8}")
    for b in bands:
        report.append(f"  {b['band']:<22} {b['n']:>6} {b['roi_pct']:>+7.1f}% "
                      f"{b['direction_accuracy']:>7.1%} {b['avg_odds']:>8.2f}")
        print(f"  {b['band']}: ROI={b['roi_pct']:+.1f}%, accuracy={b['direction_accuracy']:.1%}, n={b['n']}")

    print(f"\n-- 4. Edge by Direction --")
    dir_results = roi_by_direction_and_odds(matches)
    report.append(f"\n  -- Edge by Direction --")
    for label, data in dir_results.items():
        if data.get("roi_pct") is not None:
            report.append(f"  {label}: n={data['n']}, ROI={data['roi_pct']:+.1f}%, "
                          f"accuracy={data['direction_accuracy']:.1%}")
            print(f"  {label}: ROI={data['roi_pct']:+.1f}%, accuracy={data['direction_accuracy']:.1%}, n={data['n']}")

    print(f"\n-- 5. Segment-Level Directional Accuracy --")
    seg_results = clv_by_segment(matches)
    report.append(f"\n  -- Segment-Level Accuracy (strong disagree >2pp) --")
    report.append(f"  {'Segment':<30} {'N(all)':>7} {'DirAcc':>8} {'N(strong)':>10} {'StrongAcc':>10}")
    for s in seg_results[:15]:
        sa = f"{s['strong_accuracy']:.1%}" if s['strong_accuracy'] is not None else "N/A"
        report.append(f"  {s['segment']:<30} {s['n']:>7} {s['direction_accuracy']:>7.1%} "
                      f"{s['strong_disagree_n']:>10} {sa:>10}")
    if seg_results:
        best = seg_results[0]
        print(f"  Best segment: {best['segment']} - {best.get('strong_accuracy', 0):.1%} "
              f"accuracy on strong disagreements (n={best['strong_disagree_n']})")

    print(f"\n-- 6. Tradeable Edge Estimate --")
    edge_est = estimate_tradeable_edge(matches)
    report.append(f"\n  -- Tradeable Edge Estimate --")
    report.append(f"  Assumes: opening lines ~3% softer than close, soft book margin ~5%\n")
    report.append(f"  {'Threshold':>10} {'N':>6} {'Accuracy':>9} {'Est CLV%':>9} {'Net Edge%':>10} {'Viable?':>8}")
    for e in edge_est:
        viable = "YES" if e["profitable"] else "NO"
        report.append(f"  {e['threshold']*100:>9.0f}pp {e['n_matches']:>6} {e['accuracy']:>8.1%} "
                      f"{e['estimated_clv_pct']:>+8.1f}% {e['estimated_net_edge_pct']:>+9.1f}% {viable:>8}")
        if e["threshold"] in (0.02, 0.05):
            print(f"  >={e['threshold']*100:.0f}pp: accuracy={e['accuracy']:.1%}, est CLV={e['estimated_clv_pct']:+.1f}%, "
                  f"net edge={e['estimated_net_edge_pct']:+.1f}%")

    report.append(f"\n{'='*72}")
    report.append(f"  VERDICT: IS THERE A MARKET TIMING EDGE?")
    report.append(f"{'='*72}")

    any_significant = False
    for thresh in [0.02, 0.03, 0.05]:
        da = compute_directional_accuracy(matches, thresh)
        if da["n"] >= 30 and da.get("significant"):
            any_significant = True
            break

    best_band = max(bands, key=lambda b: b["direction_accuracy"]) if bands else None
    has_good_accuracy = best_band and best_band["direction_accuracy"] > 0.52 and best_band["n"] >= 30

    if any_significant and has_good_accuracy:
        report.append(f"\n  [PROMISING] Model shows significant directional accuracy.")
        report.append(f"    Next step: add dual-scrape (open + close) to measure actual CLV,")
        report.append(f"    then test at soft books where opening lines are exploitable.")
    elif has_good_accuracy:
        report.append(f"\n  [MARGINAL] Some directional accuracy but not statistically significant.")
        report.append(f"    Add dual-scrape and reassess after 500+ matches with open/close pairs.")
    else:
        report.append(f"\n  [NO EVIDENCE] Model does not predict line direction better than chance.")
        report.append(f"    Market timing is not a viable edge source with this model.")

    report.append(f"\n  Regardless of verdict, dual-scrape is worth adding (low effort, high")
    report.append(f"  information value).")
    report.append(f"\n{'='*72}\n")

    report_text = "\n".join(report)
    print(f"\n{report_text}")

    report_path = os.path.join(args.out_dir, "clv-research-report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  Saved: {report_path}")

    if HAS_MPL:
        print(f"\n-- Charts --")
        plot_disagreement_distribution(matches, os.path.join(args.out_dir, "clv-disagreement-dist.png"))
        plot_accuracy_by_disagreement(bands, os.path.join(args.out_dir, "clv-accuracy-by-disagree.png"))
        plot_segment_accuracy(seg_results, os.path.join(args.out_dir, "clv-segment-accuracy.png"))

    print(f"\n  Done.\n")


if __name__ == "__main__":
    main()
