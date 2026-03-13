"""
Part 1: Diagnostic Toolkit — Baseline Model Measurement
========================================================
Reads backtest results CSVs and produces:
  1. Calibration reliability diagram (predicted prob vs actual win rate, binned)
  2. Brier score decomposition (reliability + resolution + uncertainty) by segment
  3. Log-loss by surface, tier, confidence band
  4. Edge analysis: ROI by value threshold, surface, tier
  5. Overround-adjusted calibration (vs Pinnacle implied)
  6. Summary report (text + PNG charts)

Usage:
  python scripts/diagnostic-toolkit.py --files data/backtest/backtest-results-2024.csv data/backtest/backtest-results-2025.csv
  python scripts/diagnostic-toolkit.py --files data/backtest/backtest-results-2024.csv --surface Hard --tier Masters
  python scripts/diagnostic-toolkit.py --strict-signals data/backtest/strict-signals.csv

Output:
  data/diagnostics/calibration-report.txt        (text summary)
  data/diagnostics/calibration-reliability.png    (reliability diagram)
  data/diagnostics/brier-decomposition.png        (Brier by segment)
  data/diagnostics/logloss-by-segment.png         (log-loss breakdown)
  data/diagnostics/roi-by-threshold.png           (ROI vs value threshold sweep)
  data/diagnostics/edge-distribution.png          (histogram of model edge vs Pinnacle)

Respects: Iteration 4 policy lock. This script is read-only / diagnostic — no model changes.
"""

import os
import sys
import csv
import math
import json
import argparse
from datetime import datetime
from collections import defaultdict

import numpy as np

# Optional: matplotlib for charts (degrades gracefully if missing)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("Warning: matplotlib not installed. Charts will be skipped. Install with: pip install matplotlib")

# Optional: pandas for Excel reading
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _float(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _int(v, default=None):
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


def load_csv(path):
    """Load CSV with auto-detected delimiter."""
    if not os.path.exists(path):
        print(f"  File not found: {path}")
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        reader = csv.DictReader(f, dialect=dialect)
        return [{k: (v if v else None) for k, v in row.items()} for row in reader]


def load_excel(path):
    """Load Excel file via pandas."""
    if not HAS_PANDAS:
        print(f"  Cannot read Excel ({path}): pandas not installed.")
        return []
    df = pd.read_excel(path)
    return df.to_dict("records")


def load_data(paths):
    """Load one or more CSV/Excel files and merge into a single list of dicts."""
    all_rows = []
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext in (".xlsx", ".xls"):
            rows = load_excel(p)
        else:
            rows = load_csv(p)
        print(f"  Loaded {len(rows):,} rows from {os.path.basename(p)}")
        all_rows.extend(rows)
    return all_rows


# ── Column auto-detection ────────────────────────────────────────────────────
# The backtest CSV may use different column names depending on version.
# We try multiple aliases for each concept.

COLUMN_ALIASES = {
    "p1_win_prob": ["p1_win_prob", "model_p1", "prob_p1", "p1_prob", "model_prob_p1", "predicted_prob"],
    "p2_win_prob": ["p2_win_prob", "model_p2", "prob_p2", "p2_prob", "model_prob_p2"],
    "odds1": ["odds1", "model_odds1", "fair_odds1", "model_odds_p1"],
    "odds2": ["odds2", "model_odds2", "fair_odds2", "model_odds_p2"],
    "pinnacle_odds1": ["pinnacle_odds1", "pin_odds1", "closing_odds1", "pinnacle_close_p1", "book_odds1", "pinnacle_p1"],
    "pinnacle_odds2": ["pinnacle_odds2", "pin_odds2", "closing_odds2", "pinnacle_close_p2", "book_odds2", "pinnacle_p2"],
    "winner": ["winner", "actual_winner", "result_winner", "match_winner"],
    "winner_id": ["winner_id", "actual_winner_id"],
    "p1_won": ["p1_won", "p1_win", "result"],
    "surface": ["surface"],
    "tier": ["tier", "series", "tournament_tier", "tour_tier", "category"],
    "confidence": ["confidence", "conf", "signal_confidence"],
    "value_pct": ["value_pct", "value", "edge_pct", "edge", "model_edge"],
    "player1_id": ["player1_id", "p1_id", "p1"],
    "player2_id": ["player2_id", "p2_id", "p2"],
    "tour_id": ["tour_id", "tournament_id"],
    "round_id": ["round_id", "round"],
    "date": ["date", "match_date"],
    "year": ["year"],
    "selection": ["selection", "bet_selection", "side"],
    "stake": ["stake"],
    "pnl": ["pnl", "profit_loss", "profit", "return"],
    "settled": ["settled", "is_settled"],
}


def detect_columns(rows):
    """Auto-detect column mapping from first row's keys."""
    if not rows:
        return {}
    available = set(rows[0].keys())
    mapping = {}
    for concept, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in available:
                mapping[concept] = alias
                break
    return mapping


def get(row, concept, col_map, default=None):
    """Get a value from row using the detected column mapping."""
    col = col_map.get(concept)
    if col is None:
        return default
    return row.get(col, default)


# ── Determine outcome ────────────────────────────────────────────────────────

def determine_p1_won(row, col_map):
    """Return True if P1 won, False if P2 won, None if unknown."""
    # Direct p1_won column
    v = get(row, "p1_won", col_map)
    if v is not None:
        s = str(v).strip().lower()
        if s in ("1", "true", "yes", "w", "win"):
            return True
        if s in ("0", "false", "no", "l", "loss"):
            return False
    # winner_id matches player1_id
    wid = get(row, "winner_id", col_map)
    p1id = get(row, "player1_id", col_map)
    if wid is not None and p1id is not None:
        try:
            return int(float(wid)) == int(float(p1id))
        except (ValueError, TypeError):
            pass
    # winner column: may contain "p1", "player1", or a name
    w = get(row, "winner", col_map)
    if w is not None:
        ws = str(w).strip().lower()
        if ws in ("p1", "player1", "1"):
            return True
        if ws in ("p2", "player2", "2"):
            return False
    return None


# ── Core metrics ─────────────────────────────────────────────────────────────

def brier_score(probs, outcomes):
    """Brier score: mean (forecast - outcome)^2. Lower is better."""
    if not probs:
        return None
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def brier_decomposition(probs, outcomes, n_bins=10):
    """
    Murphy decomposition: BS = REL - RES + UNC
      REL (reliability): lower = better calibrated
      RES (resolution): higher = better discrimination
      UNC (uncertainty): base rate uncertainty (constant for dataset)
    """
    if not probs:
        return None, None, None
    n = len(probs)
    base_rate = sum(outcomes) / n
    unc = base_rate * (1 - base_rate)

    bins = defaultdict(list)
    for p, o in zip(probs, outcomes):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b].append((p, o))

    rel = 0.0
    res = 0.0
    for b, items in bins.items():
        nk = len(items)
        fk = sum(p for p, o in items) / nk  # mean forecast in bin
        ok = sum(o for p, o in items) / nk  # observed frequency in bin
        rel += nk * (fk - ok) ** 2
        res += nk * (ok - base_rate) ** 2
    rel /= n
    res /= n

    return round(rel, 6), round(res, 6), round(unc, 6)


def log_loss(probs, outcomes, eps=1e-15):
    """Mean log-loss. Lower is better."""
    if not probs:
        return None
    total = 0.0
    for p, o in zip(probs, outcomes):
        p_clamped = max(eps, min(1 - eps, p))
        total += o * math.log(p_clamped) + (1 - o) * math.log(1 - p_clamped)
    return -total / len(probs)


def calibration_bins(probs, outcomes, n_bins=10):
    """Return (bin_midpoints, observed_rates, bin_counts) for reliability diagram."""
    bins = defaultdict(lambda: {"sum_p": 0, "sum_o": 0, "n": 0})
    for p, o in zip(probs, outcomes):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b]["sum_p"] += p
        bins[b]["sum_o"] += o
        bins[b]["n"] += 1

    midpoints, observed, counts = [], [], []
    for b in range(n_bins):
        if bins[b]["n"] > 0:
            midpoints.append(bins[b]["sum_p"] / bins[b]["n"])
            observed.append(bins[b]["sum_o"] / bins[b]["n"])
            counts.append(bins[b]["n"])
    return midpoints, observed, counts


def roi_at_threshold(bets, threshold):
    """
    Given list of (model_edge_pct, pnl_if_bet), return ROI and n_bets
    when only betting where model_edge >= threshold.
    """
    filtered = [(e, p) for e, p in bets if e >= threshold]
    if not filtered:
        return None, 0
    total_pnl = sum(p for _, p in filtered)
    n = len(filtered)
    return (total_pnl / n) * 100, n  # ROI in percent


# ── Charting ─────────────────────────────────────────────────────────────────

CHART_STYLE = {
    "bg": "#0d0d0d",
    "fg": "#e0e0e0",
    "accent": "#10b981",  # emerald
    "accent2": "#f59e0b",  # amber
    "accent3": "#ef4444",  # red
    "grid": "#2a2a2a",
}


def apply_dark_style(fig, ax):
    """Apply Il Margine dark trading-terminal aesthetic."""
    fig.patch.set_facecolor(CHART_STYLE["bg"])
    ax.set_facecolor(CHART_STYLE["bg"])
    ax.tick_params(colors=CHART_STYLE["fg"])
    ax.xaxis.label.set_color(CHART_STYLE["fg"])
    ax.yaxis.label.set_color(CHART_STYLE["fg"])
    ax.title.set_color(CHART_STYLE["fg"])
    for spine in ax.spines.values():
        spine.set_color(CHART_STYLE["grid"])
    ax.grid(True, alpha=0.3, color=CHART_STYLE["grid"])


def plot_calibration(midpoints, observed, counts, out_path, title="Calibration Reliability Diagram"):
    """Plot predicted vs observed with perfect calibration line."""
    if not HAS_MPL:
        return
    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    apply_dark_style(fig, ax)

    # Perfect calibration line
    ax.plot([0, 1], [0, 1], "--", color=CHART_STYLE["fg"], alpha=0.5, label="Perfect calibration")

    # Calibration curve
    ax.plot(midpoints, observed, "o-", color=CHART_STYLE["accent"], markersize=8, linewidth=2, label="Model")

    # Show bin counts as text
    for x, y, n in zip(midpoints, observed, counts):
        ax.annotate(f"n={n}", (x, y), textcoords="offset points", xytext=(0, 12),
                    fontsize=7, color=CHART_STYLE["fg"], alpha=0.7, ha="center")

    ax.set_xlabel("Predicted P(win)")
    ax.set_ylabel("Observed win rate")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(facecolor=CHART_STYLE["bg"], edgecolor=CHART_STYLE["grid"],
              labelcolor=CHART_STYLE["fg"], fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CHART_STYLE["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_brier_decomposition(segments, out_path):
    """Bar chart of Brier decomposition by segment."""
    if not HAS_MPL:
        return
    names = [s["name"] for s in segments]
    rel = [s["reliability"] for s in segments]
    res = [s["resolution"] for s in segments]
    unc = [s["uncertainty"] for s in segments]
    bs = [s["brier"] for s in segments]

    x = np.arange(len(names))
    width = 0.2

    fig, ax = plt.subplots(1, 1, figsize=(max(8, len(names) * 1.5), 6))
    apply_dark_style(fig, ax)

    ax.bar(x - 1.5 * width, rel, width, label="Reliability (lower=better)", color=CHART_STYLE["accent3"], alpha=0.85)
    ax.bar(x - 0.5 * width, res, width, label="Resolution (higher=better)", color=CHART_STYLE["accent"], alpha=0.85)
    ax.bar(x + 0.5 * width, unc, width, label="Uncertainty (constant)", color=CHART_STYLE["fg"], alpha=0.4)
    ax.bar(x + 1.5 * width, bs, width, label="Brier Score", color=CHART_STYLE["accent2"], alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Score")
    ax.set_title("Brier Score Decomposition by Segment", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CHART_STYLE["bg"], edgecolor=CHART_STYLE["grid"],
              labelcolor=CHART_STYLE["fg"], fontsize=8, loc="upper right")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CHART_STYLE["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_logloss_by_segment(segments, out_path):
    """Horizontal bar chart of log-loss by segment."""
    if not HAS_MPL:
        return
    names = [s["name"] for s in segments]
    ll = [s["logloss"] for s in segments]
    n_bets = [s["n"] for s in segments]

    fig, ax = plt.subplots(1, 1, figsize=(8, max(4, len(names) * 0.6)))
    apply_dark_style(fig, ax)

    colors = [CHART_STYLE["accent"] if v < 0.65 else CHART_STYLE["accent2"] if v < 0.72 else CHART_STYLE["accent3"] for v in ll]
    bars = ax.barh(names, ll, color=colors, alpha=0.85)

    for bar, n in zip(bars, n_bets):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
                f"n={n}", va="center", fontsize=8, color=CHART_STYLE["fg"], alpha=0.7)

    ax.set_xlabel("Log-Loss (lower = better)")
    ax.set_title("Log-Loss by Segment", fontsize=13, fontweight="bold")
    ax.invert_yaxis()

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CHART_STYLE["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_roi_sweep(thresholds, rois, n_bets_list, out_path):
    """Dual-axis: ROI vs threshold, with bet count overlay."""
    if not HAS_MPL:
        return
    fig, ax1 = plt.subplots(1, 1, figsize=(9, 5))
    apply_dark_style(fig, ax1)

    ax1.plot(thresholds, rois, "o-", color=CHART_STYLE["accent"], markersize=6, linewidth=2, label="ROI %")
    ax1.axhline(0, color=CHART_STYLE["accent3"], alpha=0.5, linestyle="--")
    ax1.set_xlabel("Minimum Value Threshold (%)")
    ax1.set_ylabel("ROI (%)", color=CHART_STYLE["accent"])
    ax1.tick_params(axis="y", labelcolor=CHART_STYLE["accent"])

    ax2 = ax1.twinx()
    ax2.bar(thresholds, n_bets_list, width=0.8, alpha=0.25, color=CHART_STYLE["accent2"], label="# Bets")
    ax2.set_ylabel("Number of Bets", color=CHART_STYLE["accent2"])
    ax2.tick_params(axis="y", labelcolor=CHART_STYLE["accent2"])
    ax2.spines["right"].set_color(CHART_STYLE["grid"])

    ax1.set_title("ROI by Value Threshold (Flat Stakes)", fontsize=13, fontweight="bold")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, facecolor=CHART_STYLE["bg"],
               edgecolor=CHART_STYLE["grid"], labelcolor=CHART_STYLE["fg"], fontsize=9, loc="upper right")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CHART_STYLE["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_edge_distribution(edges, out_path):
    """Histogram of model edge vs Pinnacle (in %)."""
    if not HAS_MPL:
        return
    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    apply_dark_style(fig, ax)

    ax.hist(edges, bins=50, color=CHART_STYLE["accent"], alpha=0.75, edgecolor=CHART_STYLE["bg"])
    ax.axvline(0, color=CHART_STYLE["accent3"], alpha=0.7, linestyle="--", label="Zero edge")
    ax.axvline(10, color=CHART_STYLE["accent2"], alpha=0.7, linestyle="--", label="10% threshold")

    mean_edge = np.mean(edges)
    median_edge = np.median(edges)
    ax.axvline(mean_edge, color=CHART_STYLE["fg"], alpha=0.5, linestyle=":", label=f"Mean: {mean_edge:.1f}%")

    ax.set_xlabel("Model Edge vs Pinnacle (%)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Model Edge vs Pinnacle Closing", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CHART_STYLE["bg"], edgecolor=CHART_STYLE["grid"],
              labelcolor=CHART_STYLE["fg"], fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CHART_STYLE["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ── Main analysis ────────────────────────────────────────────────────────────

def classify_tier(row, col_map):
    """Classify match tier from available columns."""
    tier = get(row, "tier", col_map)
    if tier:
        return str(tier).strip()
    # Fallback: try tour name patterns
    tour = row.get("tour_name") or row.get("tournament") or ""
    tour_u = tour.upper()
    if "GRAND SLAM" in tour_u or any(gs in tour_u for gs in ["AUSTRALIAN OPEN", "ROLAND GARROS", "WIMBLEDON", "US OPEN"]):
        return "Grand Slam"
    if "MASTERS" in tour_u or "1000" in tour_u:
        return "Masters 1000"
    if "500" in tour_u:
        return "ATP 500"
    if "250" in tour_u:
        return "ATP 250"
    if "CHALLENGER" in tour_u:
        return "Challenger"
    return "Unknown"


def analyse(rows, col_map, label="All"):
    """Run full diagnostic analysis on a set of rows. Returns dict of metrics."""
    probs = []
    outcomes = []
    edges = []       # model_edge_pct for ROI sweep
    bet_outcomes = []  # (edge_pct, pnl) for ROI analysis
    by_surface = defaultdict(lambda: {"probs": [], "outcomes": []})
    by_tier = defaultdict(lambda: {"probs": [], "outcomes": []})

    for row in rows:
        p1_prob = _float(get(row, "p1_win_prob", col_map))
        if p1_prob is None:
            continue
        p1_won = determine_p1_won(row, col_map)
        if p1_won is None:
            continue

        outcome = 1.0 if p1_won else 0.0
        probs.append(p1_prob)
        outcomes.append(outcome)

        surface = get(row, "surface", col_map) or "Unknown"
        by_surface[surface]["probs"].append(p1_prob)
        by_surface[surface]["outcomes"].append(outcome)

        tier = classify_tier(row, col_map)
        by_tier[tier]["probs"].append(p1_prob)
        by_tier[tier]["outcomes"].append(outcome)

        # Edge vs Pinnacle
        pin1 = _float(get(row, "pinnacle_odds1", col_map))
        model_odds1 = _float(get(row, "odds1", col_map))
        if pin1 and model_odds1 and pin1 > 1 and model_odds1 > 1:
            pin_implied = 1.0 / pin1
            model_prob = 1.0 / model_odds1
            edge_pct = (model_prob - pin_implied) / pin_implied * 100
            edges.append(edge_pct)
            # PnL if we bet on P1 at Pinnacle odds (flat 1 unit)
            pnl = (pin1 - 1.0) if p1_won else -1.0
            bet_outcomes.append((edge_pct, pnl))

            # Also check P2 side
            pin2 = _float(get(row, "pinnacle_odds2", col_map))
            model_odds2 = _float(get(row, "odds2", col_map))
            if pin2 and model_odds2 and pin2 > 1 and model_odds2 > 1:
                pin_implied2 = 1.0 / pin2
                model_prob2 = 1.0 / model_odds2
                edge_pct2 = (model_prob2 - pin_implied2) / pin_implied2 * 100
                edges.append(edge_pct2)
                pnl2 = (pin2 - 1.0) if not p1_won else -1.0
                bet_outcomes.append((edge_pct2, pnl2))

    if not probs:
        return {"label": label, "n": 0, "error": "No valid rows with prob + outcome"}

    # Core metrics
    bs = brier_score(probs, outcomes)
    rel, res, unc = brier_decomposition(probs, outcomes)
    ll = log_loss(probs, outcomes)
    base_rate = sum(outcomes) / len(outcomes)

    # Calibration bins
    mid, obs, cnt = calibration_bins(probs, outcomes, n_bins=10)

    # Max absolute calibration error
    max_cal_err = max(abs(m - o) for m, o in zip(mid, obs)) if mid else None

    # Per-segment metrics
    surface_metrics = []
    for surf, data in sorted(by_surface.items()):
        if len(data["probs"]) < 10:
            continue
        s_bs = brier_score(data["probs"], data["outcomes"])
        s_rel, s_res, s_unc = brier_decomposition(data["probs"], data["outcomes"])
        s_ll = log_loss(data["probs"], data["outcomes"])
        surface_metrics.append({
            "name": surf, "n": len(data["probs"]),
            "brier": s_bs, "reliability": s_rel, "resolution": s_res, "uncertainty": s_unc,
            "logloss": s_ll,
        })

    tier_metrics = []
    for tier, data in sorted(by_tier.items()):
        if len(data["probs"]) < 10:
            continue
        t_bs = brier_score(data["probs"], data["outcomes"])
        t_rel, t_res, t_unc = brier_decomposition(data["probs"], data["outcomes"])
        t_ll = log_loss(data["probs"], data["outcomes"])
        tier_metrics.append({
            "name": tier, "n": len(data["probs"]),
            "brier": t_bs, "reliability": t_rel, "resolution": t_res, "uncertainty": t_unc,
            "logloss": t_ll,
        })

    # ROI sweep (only if we have edge data)
    roi_sweep = []
    if bet_outcomes:
        for thresh in range(0, 26):
            r, n = roi_at_threshold(bet_outcomes, thresh)
            if n >= 5:
                roi_sweep.append({"threshold": thresh, "roi": r, "n_bets": n})

    return {
        "label": label,
        "n": len(probs),
        "base_rate_p1": round(base_rate, 4),
        "brier": round(bs, 6),
        "reliability": rel,
        "resolution": res,
        "uncertainty": unc,
        "logloss": round(ll, 6),
        "max_calibration_error": round(max_cal_err, 4) if max_cal_err else None,
        "calibration": {"midpoints": mid, "observed": obs, "counts": cnt},
        "surface_metrics": surface_metrics,
        "tier_metrics": tier_metrics,
        "roi_sweep": roi_sweep,
        "edges": edges,
        "bet_outcomes": bet_outcomes,
    }


def print_report(result, f=sys.stdout):
    """Print formatted text report."""
    def w(s):
        f.write(s + "\n")

    w("=" * 72)
    w(f"  IL MARGINE — Diagnostic Report: {result['label']}")
    w(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w("=" * 72)

    if result.get("error"):
        w(f"\n  ERROR: {result['error']}\n")
        return

    w(f"\n  Total matches analysed: {result['n']:,}")
    w(f"  Base rate (P1 wins):    {result['base_rate_p1']:.4f}")

    w(f"\n  ── Overall Metrics ──")
    w(f"  Brier Score:            {result['brier']:.6f}   (lower = better; random = 0.25)")
    w(f"    Reliability:          {result['reliability']:.6f}   (lower = better calibrated)")
    w(f"    Resolution:           {result['resolution']:.6f}   (higher = better discrimination)")
    w(f"    Uncertainty:          {result['uncertainty']:.6f}   (dataset constant)")
    w(f"  Log-Loss:               {result['logloss']:.6f}   (lower = better; random = 0.693)")
    if result["max_calibration_error"] is not None:
        w(f"  Max Calibration Error:  {result['max_calibration_error']:.4f}   (max |predicted - observed| across bins)")

    # Calibration table
    cal = result["calibration"]
    if cal["midpoints"]:
        w(f"\n  ── Calibration Bins ──")
        w(f"  {'Predicted':>10} {'Observed':>10} {'Count':>8} {'Error':>8}")
        w(f"  {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
        for m, o, n in zip(cal["midpoints"], cal["observed"], cal["counts"]):
            err = m - o
            direction = "▲" if err > 0.02 else "▼" if err < -0.02 else " "
            w(f"  {m:>10.3f} {o:>10.3f} {n:>8d} {err:>+7.3f} {direction}")

    # Surface breakdown
    if result["surface_metrics"]:
        w(f"\n  ── By Surface ──")
        w(f"  {'Surface':<12} {'N':>6} {'Brier':>8} {'LogLoss':>8} {'Reliab':>8} {'Resoln':>8}")
        w(f"  {'-'*12} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        for s in result["surface_metrics"]:
            w(f"  {s['name']:<12} {s['n']:>6} {s['brier']:>8.4f} {s['logloss']:>8.4f} {s['reliability']:>8.4f} {s['resolution']:>8.4f}")

    # Tier breakdown
    if result["tier_metrics"]:
        w(f"\n  ── By Tier ──")
        w(f"  {'Tier':<16} {'N':>6} {'Brier':>8} {'LogLoss':>8} {'Reliab':>8} {'Resoln':>8}")
        w(f"  {'-'*16} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        for t in result["tier_metrics"]:
            w(f"  {t['name']:<16} {t['n']:>6} {t['brier']:>8.4f} {t['logloss']:>8.4f} {t['reliability']:>8.4f} {t['resolution']:>8.4f}")

    # ROI sweep
    if result["roi_sweep"]:
        w(f"\n  ── ROI by Value Threshold (flat stakes, both sides) ──")
        w(f"  {'Threshold':>10} {'ROI %':>8} {'# Bets':>8}")
        w(f"  {'-'*10} {'-'*8} {'-'*8}")
        for r in result["roi_sweep"]:
            marker = " ◀" if r["threshold"] == 10 else ""
            w(f"  {r['threshold']:>9}% {r['roi']:>+7.1f}% {r['n_bets']:>8}{marker}")

    # Edge distribution summary
    if result["edges"]:
        edges = result["edges"]
        w(f"\n  ── Edge Distribution (model vs Pinnacle) ──")
        w(f"  Mean edge:              {np.mean(edges):>+.2f}%")
        w(f"  Median edge:            {np.median(edges):>+.2f}%")
        w(f"  Std dev:                {np.std(edges):>.2f}%")
        w(f"  % with positive edge:   {100 * sum(1 for e in edges if e > 0) / len(edges):.1f}%")
        w(f"  % with edge >= 10%:     {100 * sum(1 for e in edges if e >= 10) / len(edges):.1f}%")

    w(f"\n{'=' * 72}")
    w(f"  Interpretation guide:")
    w(f"  - Brier < 0.20 = solid; < 0.18 = strong; Pinnacle implied ~ 0.19-0.20")
    w(f"  - Reliability < 0.005 = well-calibrated; > 0.01 = needs work")
    w(f"  - Resolution > 0.05 = good discrimination between outcomes")
    w(f"  - LogLoss < 0.60 = excellent; 0.60-0.65 = good; > 0.68 = near random")
    w(f"  - ROI > 0% at 10% threshold with 200+ bets = genuine edge signal")
    w(f"{'=' * 72}\n")


def main():
    parser = argparse.ArgumentParser(description="Il Margine Diagnostic Toolkit (Part 1)")
    parser.add_argument("--files", nargs="+", help="Backtest result CSV/Excel files")
    parser.add_argument("--strict-signals", help="Strict signals CSV (settled)")
    parser.add_argument("--surface", help="Filter to surface (e.g. Hard, Clay)")
    parser.add_argument("--tier", help="Filter to tier (e.g. Masters, ATP 500)")
    parser.add_argument("--out-dir", default="data/diagnostics", help="Output directory for charts and report")
    args = parser.parse_args()

    if not args.files and not args.strict_signals:
        print("Usage: python scripts/diagnostic-toolkit.py --files data/backtest/backtest-results-2024.csv [...]")
        print("       python scripts/diagnostic-toolkit.py --strict-signals data/backtest/strict-signals.csv")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)

    # Load data
    print("\n── Loading data ──")
    if args.files:
        rows = load_data(args.files)
    else:
        rows = load_data([args.strict_signals])

    if not rows:
        print("No data loaded. Check file paths.")
        sys.exit(1)

    col_map = detect_columns(rows)
    print(f"\n  Detected columns: {json.dumps(col_map, indent=2)}")

    # Check we have the minimum required columns
    required = ["p1_win_prob"]
    missing = [r for r in required if r not in col_map]
    if missing:
        print(f"\n  MISSING required columns: {missing}")
        print(f"  Available columns: {list(rows[0].keys())}")
        print(f"\n  The backtest CSV needs at minimum a column for P1 win probability")
        print(f"  (any of: {COLUMN_ALIASES['p1_win_prob']}) and an outcome column")
        print(f"  (any of: {COLUMN_ALIASES['p1_won']} or {COLUMN_ALIASES['winner_id']}).")
        sys.exit(1)

    # Apply filters
    label_parts = []
    if args.surface:
        surface_col = col_map.get("surface")
        if surface_col:
            rows = [r for r in rows if (r.get(surface_col) or "").strip().lower() == args.surface.lower()]
            label_parts.append(f"Surface={args.surface}")
    if args.tier:
        rows = [r for r in rows if args.tier.lower() in classify_tier(r, col_map).lower()]
        label_parts.append(f"Tier={args.tier}")

    label = " | ".join(label_parts) if label_parts else "Full Backtest"
    print(f"\n  Rows after filters: {len(rows):,}")

    # Run analysis
    print("\n── Running analysis ──")
    result = analyse(rows, col_map, label=label)

    if result.get("error"):
        print(f"\n  ERROR: {result['error']}")
        sys.exit(1)

    # Print report to stdout
    print_report(result)

    # Save report to file
    report_path = os.path.join(args.out_dir, "calibration-report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        print_report(result, f=f)
    print(f"  Saved: {report_path}")

    # Generate charts
    if HAS_MPL:
        print("\n── Generating charts ──")

        # 1. Calibration reliability diagram
        cal = result["calibration"]
        if cal["midpoints"]:
            plot_calibration(
                cal["midpoints"], cal["observed"], cal["counts"],
                os.path.join(args.out_dir, "calibration-reliability.png"),
                title=f"Calibration: {label} (n={result['n']:,})"
            )

        # 2. Brier decomposition by segment
        all_segments = []
        all_segments.append({
            "name": f"Overall (n={result['n']})",
            "brier": result["brier"], "reliability": result["reliability"],
            "resolution": result["resolution"], "uncertainty": result["uncertainty"],
        })
        for s in result["surface_metrics"]:
            all_segments.append(s)
        for t in result["tier_metrics"]:
            all_segments.append(t)
        if len(all_segments) > 1:
            plot_brier_decomposition(
                all_segments,
                os.path.join(args.out_dir, "brier-decomposition.png")
            )

        # 3. Log-loss by segment
        ll_segments = [
            {"name": s["name"], "logloss": s["logloss"], "n": s["n"]}
            for s in result["surface_metrics"] + result["tier_metrics"]
            if s.get("logloss") is not None
        ]
        if ll_segments:
            plot_logloss_by_segment(
                ll_segments,
                os.path.join(args.out_dir, "logloss-by-segment.png")
            )

        # 4. ROI sweep
        if result["roi_sweep"]:
            thresholds = [r["threshold"] for r in result["roi_sweep"]]
            rois = [r["roi"] for r in result["roi_sweep"]]
            n_bets = [r["n_bets"] for r in result["roi_sweep"]]
            plot_roi_sweep(
                thresholds, rois, n_bets,
                os.path.join(args.out_dir, "roi-by-threshold.png")
            )

        # 5. Edge distribution
        if result["edges"]:
            plot_edge_distribution(
                result["edges"],
                os.path.join(args.out_dir, "edge-distribution.png")
            )

    print("\n── Done ──\n")


if __name__ == "__main__":
    main()
