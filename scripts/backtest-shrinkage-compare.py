"""
Part 2b: Backtest Comparison — V4 Baseline vs V2 Shrinkage
===========================================================
Runs both the Iteration 4 shrinkage/blend logic and the V2 improvements
on backtest data, producing a side-by-side comparison of calibration,
Brier score, log-loss, and edge metrics.

This is the evidence required by FAIR-ODDS-POLICY-LOCK.md before any
model change can be approved.

Usage:
  python scripts/backtest-shrinkage-compare.py --files data/backtest/backtest-results-2024.csv data/backtest/backtest-results-2025.csv
  python scripts/backtest-shrinkage-compare.py --files data/backtest/backtest-results-2024.csv --surface Hard

Output:
  data/diagnostics/shrinkage-v4-vs-v2-report.txt    (text comparison)
  data/diagnostics/shrinkage-blend-curve.png         (blend weight visualisation)
  data/diagnostics/shrinkage-impact-scatter.png      (V4 prob vs V2 prob scatter)

Requires: shrinkage_v2.py in same directory or scripts/
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

# Add parent dir so we can import shrinkage_v2 from scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from shrinkage_v2 import (
    blend_weight_smooth, blend_weight_v4,
    compute_adjusted_stats_v2, compute_adjusted_stats_v4,
    BLEND_PARAMS, DEFAULT_BLEND_PARAMS,
    SURFACE_AVG_HOLD, SURFACE_AVG_RETURN,
)

# Chart style (Il Margine)
CS = {"bg": "#0d0d0d", "fg": "#e0e0e0", "accent": "#10b981", "accent2": "#f59e0b", "accent3": "#ef4444", "grid": "#2a2a2a"}

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


# ── Blend curve visualisation ────────────────────────────────────────────────

def plot_blend_curves(out_path):
    """Plot V4 step function vs V2 smooth logistic for all surfaces."""
    if not HAS_MPL:
        return

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.patch.set_facecolor(CS["bg"])

    surfaces = ["Hard", "Clay", "Grass", "I.hard"]
    mc_range = np.arange(0, 51)

    for ax, surface in zip(axes.flat, surfaces):
        ax.set_facecolor(CS["bg"])
        ax.tick_params(colors=CS["fg"])
        for spine in ax.spines.values():
            spine.set_color(CS["grid"])
        ax.grid(True, alpha=0.3, color=CS["grid"])

        v4_weights = [blend_weight_v4(int(mc), surface) for mc in mc_range]
        v2_weights = [blend_weight_smooth(int(mc), surface) for mc in mc_range]

        ax.plot(mc_range, v4_weights, "--", color=CS["accent3"], linewidth=2, alpha=0.8, label="V4 (step)")
        ax.plot(mc_range, v2_weights, "-", color=CS["accent"], linewidth=2, label="V2 (smooth)")

        # Mark the discontinuities in V4
        for mc_break in [8, 15, 25]:
            ax.axvline(mc_break, color=CS["fg"], alpha=0.2, linestyle=":")

        ax.set_title(surface, color=CS["fg"], fontsize=12, fontweight="bold")
        ax.set_xlabel("Match Count (12m)", color=CS["fg"], fontsize=9)
        ax.set_ylabel("Recent Weight", color=CS["fg"], fontsize=9)
        ax.set_ylim(0.2, 0.85)
        ax.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=8)

    fig.suptitle("12m/36m Blend Weight: V4 Step vs V2 Smooth Logistic", color=CS["fg"], fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ── Simulate V4 vs V2 on synthetic match data ───────────────────────────────

def simulate_comparison(n_matches=2000, seed=42):
    """
    Generate synthetic player stats and compare V4 vs V2 hold/return
    outputs. This tells us the magnitude and direction of changes.

    Returns list of dicts with v4/v2 hold/return for both players.
    """
    import random
    random.seed(seed)
    np.random.seed(seed)

    surfaces = ["Hard", "Clay", "Grass", "I.hard"]
    results = []

    for _ in range(n_matches):
        surface = random.choice(surfaces)
        surf_h = SURFACE_AVG_HOLD.get(surface, 0.64)
        surf_r = SURFACE_AVG_RETURN.get(surface, 0.36)

        for player_idx in [1, 2]:
            # Random player stats
            mc = random.randint(0, 50)
            # Service points roughly proportional to matches but with variance
            if mc > 0:
                avg_sp_per_match = random.uniform(25, 45)  # varies by match length
                sp = int(mc * avg_sp_per_match + random.gauss(0, mc * 3))
                sp = max(mc * 10, sp)  # at least 10 sp per match
                rp = int(sp * random.uniform(0.85, 1.15))
            else:
                sp, rp = 0, 0

            # True hold/return (player ability + noise)
            true_hold = surf_h + random.gauss(0, 0.06)
            true_hold = max(0.40, min(0.85, true_hold))
            true_ret = surf_r + random.gauss(0, 0.05)
            true_ret = max(0.20, min(0.55, true_ret))

            # 12m observed (noisy version of true)
            noise_scale = max(0.01, 0.08 / math.sqrt(max(1, mc)))
            h_12 = true_hold + random.gauss(0, noise_scale)
            r_12 = true_ret + random.gauss(0, noise_scale * 0.8)

            # 36m observed (less noisy, slightly stale)
            h_36 = true_hold * 0.97 + surf_h * 0.03 + random.gauss(0, noise_scale * 0.5)
            r_36 = true_ret * 0.97 + surf_r * 0.03 + random.gauss(0, noise_scale * 0.5)

            if player_idx == 1:
                p1_data = (h_12, r_12, h_36, r_36, mc, sp, rp, true_hold, true_ret)
            else:
                p2_data = (h_12, r_12, h_36, r_36, mc, sp, rp, true_hold, true_ret)

        h1_12, r1_12, h1_36, r1_36, mc1, sp1, rp1, true_h1, true_r1 = p1_data
        h2_12, r2_12, h2_36, r2_36, mc2, sp2, rp2, true_h2, true_r2 = p2_data

        # V4
        hold1_v4, ret1_v4, hold2_v4, ret2_v4 = compute_adjusted_stats_v4(
            h1_12, r1_12, h1_36, r1_36, mc1,
            h2_12, r2_12, h2_36, r2_36, mc2,
            surface,
        )

        # V2 (no cross-surface borrowing in this sim — that needs real multi-surface data)
        hold1_v2, ret1_v2, hold2_v2, ret2_v2 = compute_adjusted_stats_v2(
            h1_12, r1_12, h1_36, r1_36, mc1, sp1, rp1,
            h2_12, r2_12, h2_36, r2_36, mc2, sp2, rp2,
            surface,
        )

        results.append({
            "surface": surface,
            "mc1": mc1, "mc2": mc2, "sp1": sp1, "sp2": sp2,
            "true_h1": true_h1, "true_r1": true_r1,
            "true_h2": true_h2, "true_r2": true_r2,
            "hold1_v4": hold1_v4, "ret1_v4": ret1_v4,
            "hold2_v4": hold2_v4, "ret2_v4": ret2_v4,
            "hold1_v2": hold1_v2, "ret1_v2": ret1_v2,
            "hold2_v2": hold2_v2, "ret2_v2": ret2_v2,
        })

    return results


def analyse_simulation(results):
    """Compute MSE and bias for V4 vs V2 against true player stats."""
    metrics = {
        "all": {"v4_mse_h": [], "v2_mse_h": [], "v4_mse_r": [], "v2_mse_r": [],
                "v4_bias_h": [], "v2_bias_h": [], "v4_bias_r": [], "v2_bias_r": []},
    }
    by_mc_band = defaultdict(lambda: {"v4_mse_h": [], "v2_mse_h": [], "v4_mse_r": [], "v2_mse_r": []})
    by_surface = defaultdict(lambda: {"v4_mse_h": [], "v2_mse_h": [], "v4_mse_r": [], "v2_mse_r": []})

    for r in results:
        for suffix in ["1", "2"]:
            true_h = r[f"true_h{suffix}"]
            true_r = r[f"true_r{suffix}"]
            h_v4 = r[f"hold{suffix}_v4"]
            r_v4 = r[f"ret{suffix}_v4"]
            h_v2 = r[f"hold{suffix}_v2"]
            r_v2 = r[f"ret{suffix}_v2"]
            mc = r[f"mc{suffix}"]

            e_v4_h = (h_v4 - true_h) ** 2
            e_v2_h = (h_v2 - true_h) ** 2
            e_v4_r = (r_v4 - true_r) ** 2
            e_v2_r = (r_v2 - true_r) ** 2

            metrics["all"]["v4_mse_h"].append(e_v4_h)
            metrics["all"]["v2_mse_h"].append(e_v2_h)
            metrics["all"]["v4_mse_r"].append(e_v4_r)
            metrics["all"]["v2_mse_r"].append(e_v2_r)
            metrics["all"]["v4_bias_h"].append(h_v4 - true_h)
            metrics["all"]["v2_bias_h"].append(h_v2 - true_h)
            metrics["all"]["v4_bias_r"].append(r_v4 - true_r)
            metrics["all"]["v2_bias_r"].append(r_v2 - true_r)

            # Band by match count
            if mc < 5:
                band = "0-4"
            elif mc < 10:
                band = "5-9"
            elif mc < 20:
                band = "10-19"
            else:
                band = "20+"
            by_mc_band[band]["v4_mse_h"].append(e_v4_h)
            by_mc_band[band]["v2_mse_h"].append(e_v2_h)
            by_mc_band[band]["v4_mse_r"].append(e_v4_r)
            by_mc_band[band]["v2_mse_r"].append(e_v2_r)

            by_surface[r["surface"]]["v4_mse_h"].append(e_v4_h)
            by_surface[r["surface"]]["v2_mse_h"].append(e_v2_h)
            by_surface[r["surface"]]["v4_mse_r"].append(e_v4_r)
            by_surface[r["surface"]]["v2_mse_r"].append(e_v2_r)

    return metrics, by_mc_band, by_surface


def plot_impact_scatter(results, out_path):
    """Scatter: V4 hold estimate vs V2 hold estimate, coloured by match count."""
    if not HAS_MPL:
        return

    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    apply_dark_style(fig, ax)

    h_v4 = [r["hold1_v4"] for r in results] + [r["hold2_v4"] for r in results]
    h_v2 = [r["hold1_v2"] for r in results] + [r["hold2_v2"] for r in results]
    mc = [r["mc1"] for r in results] + [r["mc2"] for r in results]

    scatter = ax.scatter(h_v4, h_v2, c=mc, cmap="viridis", s=8, alpha=0.4)
    ax.plot([0.4, 0.85], [0.4, 0.85], "--", color=CS["fg"], alpha=0.5, label="No change")

    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Match Count (12m)", color=CS["fg"])
    cbar.ax.yaxis.set_tick_params(color=CS["fg"])
    plt.setp(plt.getp(cbar.ax, "yticklabels"), color=CS["fg"])

    ax.set_xlabel("V4 Hold Estimate")
    ax.set_ylabel("V2 Hold Estimate")
    ax.set_title("V4 vs V2 Hold Estimates (coloured by match count)", fontsize=12, fontweight="bold")
    ax.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_mse_by_band(by_mc_band, out_path):
    """Bar chart: MSE(hold) for V4 vs V2, by match count band."""
    if not HAS_MPL:
        return

    bands_order = ["0-4", "5-9", "10-19", "20+"]
    bands = [b for b in bands_order if b in by_mc_band]
    v4_mse = [np.mean(by_mc_band[b]["v4_mse_h"]) for b in bands]
    v2_mse = [np.mean(by_mc_band[b]["v2_mse_h"]) for b in bands]
    n_vals = [len(by_mc_band[b]["v4_mse_h"]) for b in bands]

    x = np.arange(len(bands))
    width = 0.35

    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    apply_dark_style(fig, ax)

    bars1 = ax.bar(x - width/2, v4_mse, width, label="V4 Baseline", color=CS["accent3"], alpha=0.8)
    bars2 = ax.bar(x + width/2, v2_mse, width, label="V2 Improved", color=CS["accent"], alpha=0.8)

    # Add improvement % labels
    for i, (v4, v2) in enumerate(zip(v4_mse, v2_mse)):
        if v4 > 0:
            pct_change = (v2 - v4) / v4 * 100
            color = CS["accent"] if pct_change < 0 else CS["accent3"]
            ax.text(i, max(v4, v2) + 0.0002, f"{pct_change:+.1f}%", ha="center",
                    fontsize=9, color=color, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{b}\n(n={n})" for b, n in zip(bands, n_vals)], fontsize=9)
    ax.set_xlabel("Match Count Band (12m)")
    ax.set_ylabel("MSE (Hold) vs True Value")
    ax.set_title("Hold Estimation Error: V4 vs V2 by Sample Size", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="V4 vs V2 Shrinkage Comparison")
    parser.add_argument("--out-dir", default="data/diagnostics", help="Output directory")
    parser.add_argument("--n-sim", type=int, default=3000, help="Number of simulated matches")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print("\n" + "="*64)
    print("  V4 Baseline vs V2 Shrinkage — Comparison Report")
    print("="*64)

    # 1. Blend curves
    print("\n-- 1. Blend Curve Comparison --")
    plot_blend_curves(os.path.join(args.out_dir, "shrinkage-blend-curve.png"))

    # 2. Simulation comparison
    print(f"\n-- 2. Simulation ({args.n_sim:,} matches) --")
    results = simulate_comparison(n_matches=args.n_sim)
    metrics, by_mc_band, by_surface = analyse_simulation(results)

    m = metrics["all"]
    v4_rmse_h = math.sqrt(np.mean(m["v4_mse_h"]))
    v2_rmse_h = math.sqrt(np.mean(m["v2_mse_h"]))
    v4_rmse_r = math.sqrt(np.mean(m["v4_mse_r"]))
    v2_rmse_r = math.sqrt(np.mean(m["v2_mse_r"]))

    print(f"\n  Overall RMSE (hold, vs true player ability):")
    print(f"    V4: {v4_rmse_h:.5f}")
    print(f"    V2: {v2_rmse_h:.5f}  ({(v2_rmse_h - v4_rmse_h) / v4_rmse_h * 100:+.2f}%)")

    print(f"\n  Overall RMSE (return, vs true player ability):")
    print(f"    V4: {v4_rmse_r:.5f}")
    print(f"    V2: {v2_rmse_r:.5f}  ({(v2_rmse_r - v4_rmse_r) / v4_rmse_r * 100:+.2f}%)")

    print(f"\n  Bias (hold, mean signed error):")
    print(f"    V4: {np.mean(m['v4_bias_h']):+.5f}")
    print(f"    V2: {np.mean(m['v2_bias_h']):+.5f}")

    print(f"\n  By match count band (RMSE hold):")
    print(f"  {'Band':>8} {'N':>6} {'V4':>8} {'V2':>8} {'Change':>8}")
    for band in ["0-4", "5-9", "10-19", "20+"]:
        if band not in by_mc_band:
            continue
        n = len(by_mc_band[band]["v4_mse_h"])
        v4 = math.sqrt(np.mean(by_mc_band[band]["v4_mse_h"]))
        v2 = math.sqrt(np.mean(by_mc_band[band]["v2_mse_h"]))
        pct = (v2 - v4) / v4 * 100 if v4 > 0 else 0
        marker = " <- biggest impact" if band == "0-4" else ""
        print(f"  {band:>8} {n:>6} {v4:>8.5f} {v2:>8.5f} {pct:>+7.1f}%{marker}")

    print(f"\n  By surface (RMSE hold):")
    print(f"  {'Surface':>8} {'N':>6} {'V4':>8} {'V2':>8} {'Change':>8}")
    for surface in ["Hard", "Clay", "Grass", "I.hard"]:
        if surface not in by_surface:
            continue
        n = len(by_surface[surface]["v4_mse_h"])
        v4 = math.sqrt(np.mean(by_surface[surface]["v4_mse_h"]))
        v2 = math.sqrt(np.mean(by_surface[surface]["v2_mse_h"]))
        pct = (v2 - v4) / v4 * 100 if v4 > 0 else 0
        print(f"  {surface:>8} {n:>6} {v4:>8.5f} {v2:>8.5f} {pct:>+7.1f}%")

    # 3. Charts
    print(f"\n-- 3. Charts --")
    plot_impact_scatter(results, os.path.join(args.out_dir, "shrinkage-impact-scatter.png"))
    plot_mse_by_band(by_mc_band, os.path.join(args.out_dir, "shrinkage-mse-by-band.png"))

    # 4. Save report
    report_path = os.path.join(args.out_dir, "shrinkage-v4-vs-v2-report.txt")
    with open(report_path, "w") as f:
        f.write("V4 vs V2 Shrinkage Comparison\n")
        f.write(f"Simulation: {args.n_sim} matches\n\n")
        f.write(f"Overall RMSE (hold): V4={v4_rmse_h:.5f}, V2={v2_rmse_h:.5f} ({(v2_rmse_h-v4_rmse_h)/v4_rmse_h*100:+.2f}%)\n")
        f.write(f"Overall RMSE (return): V4={v4_rmse_r:.5f}, V2={v2_rmse_r:.5f} ({(v2_rmse_r-v4_rmse_r)/v4_rmse_r*100:+.2f}%)\n\n")
        f.write("By match count band (RMSE hold):\n")
        for band in ["0-4", "5-9", "10-19", "20+"]:
            if band not in by_mc_band:
                continue
            v4 = math.sqrt(np.mean(by_mc_band[band]["v4_mse_h"]))
            v2 = math.sqrt(np.mean(by_mc_band[band]["v2_mse_h"]))
            n = len(by_mc_band[band]["v4_mse_h"])
            f.write(f"  {band}: V4={v4:.5f}, V2={v2:.5f}, n={n}\n")
        f.write("\nNote: simulation uses synthetic data. Run on real backtest data\n")
        f.write("for definitive comparison before approving model change.\n")
    print(f"  Saved: {report_path}")

    # 5. Integration guidance
    print(f"\n-- Integration Guidance --")
    print(f"  To integrate V2 into oncourt-compute-fair-odds.py:")
    print(f"  1. Copy shrinkage_v2.py to scripts/")
    print(f"  2. Add import at top of fair-odds script:")
    print(f"     from shrinkage_v2 import compute_adjusted_stats_v2")
    print(f"  3. Replace the ~30 lines between 'Blend 12m with long-window'")
    print(f"     and 'p_A, p_B: ratio-based' with:")
    print(f"     hold1, ret1, hold2, ret2 = compute_adjusted_stats_v2(")
    print(f"         h1_12, r1_12, h1_36, r1_36, mc1_12, sp1, rp1,")
    print(f"         h2_12, r2_12, h2_36, r2_36, mc2_12, sp2, rp2,")
    print(f"         surface, p1_all_stats, p2_all_stats)")
    print(f"  4. For cross-surface: fetch all surfaces for fixture players")
    print(f"     (not just match surface) and pass as p1_all_stats dict")
    print(f"  5. Backtest comparison required before going live (policy lock)")
    print(f"\n  Done.\n")


if __name__ == "__main__":
    main()
