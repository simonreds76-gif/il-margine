"""
Part 4: Edge Detection & Staking Refinement - edge_analysis.py
===============================================================
Tools for measuring edge quality, optimal thresholds, confidence intervals
on model probabilities, Kelly staking analysis, and CLV tracking.

Five components:

  1. VALUE THRESHOLD SWEEP
     Is 10% optimal? Sweep thresholds with statistical significance tests.
     Output: ROI, Sharpe ratio, win rate, and confidence intervals per threshold.

  2. CONFIDENCE INTERVALS ON FAIR ODDS
     Parametric bootstrap from hold/return sampling variance.
     Tells you when a "10% edge" is real vs within noise.

  3. KELLY CRITERION ANALYSIS
     Full Kelly, fractional Kelly, and comparison to flat stakes.
     Even if flat is the live policy, Kelly tells you where genuine edges are.

  4. CLV (CLOSING LINE VALUE) TRACKER
     Measure model quality faster than waiting for settlement.
     Positive CLV = the market moved toward your price = genuine edge signal.

  5. EDGE DECAY ANALYSIS
     How does edge quality change by time-to-match, round, and odds band?

Usage:
  python scripts/edge-analysis.py --files data/backtest/backtest-results-2024.csv [...]
  python scripts/edge-analysis.py --strict-signals data/backtest/strict-signals.csv
  python scripts/edge-analysis.py --clv-report data/backtest/strict-signals.csv

Respects: Iteration 4 policy lock. Read-only analysis - no model changes.
"""

import os
import sys
import csv
import math
import argparse
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# Add project root for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Chart style (Il Margine)
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


# ══════════════════════════════════════════════════════════════════════════════
# Data loading (shared with diagnostic-toolkit.py)
# ══════════════════════════════════════════════════════════════════════════════

def load_csv(path):
    if not os.path.exists(path):
        print(f"  File not found: {path}")
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


def load_data(paths):
    all_rows = []
    for p in paths:
        rows = load_csv(p)
        print(f"  Loaded {len(rows):,} rows from {os.path.basename(p)}")
        all_rows.extend(rows)
    return all_rows


# ══════════════════════════════════════════════════════════════════════════════
# 1. VALUE THRESHOLD SWEEP (with statistical significance)
# ══════════════════════════════════════════════════════════════════════════════

def threshold_sweep(
    bets: List[Dict],
    thresholds: List[float] = None,
    n_bootstrap: int = 5000,
) -> List[Dict]:
    """
    For each value threshold, compute ROI, Sharpe, win rate, bet volume,
    and bootstrap 95% confidence interval on ROI.

    Each bet dict needs: edge_pct, pnl (from flat 1-unit stake at Pinnacle odds).

    Returns list of dicts sorted by threshold.
    """
    if thresholds is None:
        thresholds = list(range(0, 26))

    results = []
    for thresh in thresholds:
        filtered = [b for b in bets if b["edge_pct"] >= thresh]
        n = len(filtered)
        if n < 5:
            continue

        pnls = np.array([b["pnl"] for b in filtered])
        roi = float(np.mean(pnls)) * 100  # in %
        win_rate = float(np.mean([1 if p > 0 else 0 for p in pnls]))
        std = float(np.std(pnls, ddof=1)) if n > 1 else 0
        sharpe = float(np.mean(pnls) / std) if std > 0 else 0

        # Bootstrap 95% CI on ROI
        boot_rois = []
        for _ in range(n_bootstrap):
            sample = np.random.choice(pnls, size=n, replace=True)
            boot_rois.append(float(np.mean(sample)) * 100)
        ci_lo = float(np.percentile(boot_rois, 2.5))
        ci_hi = float(np.percentile(boot_rois, 97.5))

        # Is ROI significantly > 0? (proportion of bootstrap samples > 0)
        prob_positive = float(np.mean([1 if r > 0 else 0 for r in boot_rois]))

        results.append({
            "threshold": thresh,
            "n_bets": n,
            "roi_pct": round(roi, 2),
            "roi_ci_lo": round(ci_lo, 2),
            "roi_ci_hi": round(ci_hi, 2),
            "prob_positive_roi": round(prob_positive, 3),
            "win_rate": round(win_rate, 4),
            "sharpe": round(sharpe, 4),
            "std_pnl": round(std, 4),
            "total_pnl": round(float(np.sum(pnls)), 2),
        })

    return results


def find_optimal_threshold(sweep_results: List[Dict], min_bets: int = 30) -> Optional[Dict]:
    """
    Find the threshold that maximises the Sharpe ratio (risk-adjusted ROI)
    subject to minimum bet volume.

    Why Sharpe not raw ROI: higher thresholds always have fewer bets and
    more variance. Sharpe penalises that variance, finding the sweet spot
    between edge size and statistical confidence.
    """
    candidates = [r for r in sweep_results if r["n_bets"] >= min_bets and r["prob_positive_roi"] >= 0.80]
    if not candidates:
        candidates = [r for r in sweep_results if r["n_bets"] >= min_bets]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r["sharpe"])


# ══════════════════════════════════════════════════════════════════════════════
# 2. CONFIDENCE INTERVALS ON FAIR ODDS
# ══════════════════════════════════════════════════════════════════════════════

def prob_confidence_interval(
    hold_pct: float,
    return_pct: float,
    service_pts: int,
    return_pts: int,
    opponent_hold: float,
    opponent_return: float,
    opponent_sp: int,
    opponent_rp: int,
    n_bootstrap: int = 2000,
) -> Tuple[float, float, float]:
    """
    Bootstrap confidence interval on match win probability from
    sampling variance in hold%/return%.

    Returns (p_win_median, p_win_5th, p_win_95th).
    """
    try:
        from src.lib.tennis_prob import prob_match_best_of_3 as pmbo3
    except ImportError:
        return hold_pct, hold_pct, hold_pct

    SURFACE_AVG_SPW = 0.64

    p_wins = []
    for _ in range(n_bootstrap):
        if service_pts > 0:
            h1_sim = np.random.binomial(service_pts, hold_pct) / service_pts
        else:
            h1_sim = hold_pct
        if return_pts > 0:
            r1_sim = np.random.binomial(return_pts, return_pct) / return_pts
        else:
            r1_sim = return_pct
        if opponent_sp > 0:
            h2_sim = np.random.binomial(opponent_sp, opponent_hold) / opponent_sp
        else:
            h2_sim = opponent_hold
        if opponent_rp > 0:
            r2_sim = np.random.binomial(opponent_rp, opponent_return) / opponent_rp
        else:
            r2_sim = opponent_return

        p_a = max(0.52, min(0.78, (h1_sim * (1.0 - r2_sim)) / SURFACE_AVG_SPW))
        p_b = max(0.52, min(0.78, (h2_sim * (1.0 - r1_sim)) / SURFACE_AVG_SPW))
        p_wins.append(pmbo3(p_a, p_b))

    p_wins = np.array(p_wins)
    return (
        float(np.median(p_wins)),
        float(np.percentile(p_wins, 5)),
        float(np.percentile(p_wins, 95)),
    )


def edge_significance(
    model_prob: float,
    pinnacle_implied: float,
    service_pts_p1: int,
    return_pts_p1: int,
    service_pts_p2: int,
    return_pts_p2: int,
) -> Dict:
    """
    Compute whether a perceived edge is statistically significant
    given the sampling uncertainty in the model's inputs.

    Returns dict with edge_pct, ci_width, and significance assessment.
    """
    edge_pct = (model_prob - pinnacle_implied) / pinnacle_implied * 100

    total_pts = service_pts_p1 + return_pts_p1 + service_pts_p2 + return_pts_p2
    if total_pts > 0:
        effective_n = math.sqrt(total_pts) * 2
        se = math.sqrt(model_prob * (1 - model_prob) / max(1, effective_n))
        ci_width = 1.96 * se
    else:
        ci_width = 0.20

    ci_width_pct = (ci_width / pinnacle_implied * 100) if pinnacle_implied > 0 else 100

    return {
        "edge_pct": round(edge_pct, 2),
        "model_ci_width": round(ci_width, 4),
        "ci_width_pct": round(ci_width_pct, 2),
        "significant": edge_pct > ci_width_pct,
        "confidence": "high" if edge_pct > 2 * ci_width_pct else "medium" if edge_pct > ci_width_pct else "low",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. KELLY CRITERION ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def kelly_fraction(model_prob: float, decimal_odds: float) -> float:
    """
    Full Kelly fraction: f* = (p * b - q) / b
    where p = win prob, q = 1-p, b = decimal_odds - 1.

    Returns fraction of bankroll to bet (can be negative = no bet).
    """
    if decimal_odds <= 1 or model_prob <= 0 or model_prob >= 1:
        return 0.0
    b = decimal_odds - 1.0
    q = 1.0 - model_prob
    f = (model_prob * b - q) / b
    return f


def kelly_analysis(
    bets: List[Dict],
    kelly_fractions: List[float] = None,
    initial_bankroll: float = 100.0,
) -> Dict:
    """
    Simulate bankroll growth under different staking strategies:
      - Flat 1 unit
      - Full Kelly
      - Fractional Kelly (0.25, 0.33, 0.50)

    Each bet dict needs: model_prob, pinnacle_odds, p1_won (bool).

    Returns dict with final bankrolls, max drawdowns, and growth curves.
    """
    if kelly_fractions is None:
        kelly_fractions = [0.25, 0.33, 0.50, 1.0]

    strategies = {"flat_1u": {"bankroll": initial_bankroll, "history": [initial_bankroll]}}
    for frac in kelly_fractions:
        label = f"kelly_{frac:.0%}" if frac < 1 else "kelly_full"
        strategies[label] = {"bankroll": initial_bankroll, "history": [initial_bankroll]}

    for bet in bets:
        prob = bet["model_prob"]
        odds = bet["pinnacle_odds"]
        won = bet["p1_won"]

        if odds <= 1 or prob <= 0:
            for s in strategies.values():
                s["history"].append(s["bankroll"])
            continue

        # Flat: always bet 1 unit
        flat_pnl = (odds - 1) if won else -1.0
        strategies["flat_1u"]["bankroll"] += flat_pnl
        strategies["flat_1u"]["history"].append(strategies["flat_1u"]["bankroll"])

        # Kelly variants (cap stake at 5% of bankroll to avoid numerical explosion)
        f_full = kelly_fraction(prob, odds)
        max_f = 0.05
        for frac in kelly_fractions:
            label = f"kelly_{frac:.0%}" if frac < 1 else "kelly_full"
            f = max(0, min(f_full * frac, max_f))
            stake = f * strategies[label]["bankroll"]
            stake = min(stake, strategies[label]["bankroll"])
            if stake <= 0:
                strategies[label]["history"].append(strategies[label]["bankroll"])
                continue
            pnl = stake * (odds - 1) if won else -stake
            strategies[label]["bankroll"] += pnl
            strategies[label]["bankroll"] = max(0, strategies[label]["bankroll"])
            # Cap bankroll to prevent overflow (1e6 = 10,000x initial)
            strategies[label]["bankroll"] = min(strategies[label]["bankroll"], initial_bankroll * 1e4)
            strategies[label]["history"].append(strategies[label]["bankroll"])

    # Compute metrics for each strategy
    for label, s in strategies.items():
        hist = np.array(s["history"])
        peak = np.maximum.accumulate(hist)
        drawdown = (peak - hist) / np.maximum(peak, 1e-10)
        s["max_drawdown"] = float(np.max(drawdown))
        s["final_bankroll"] = float(hist[-1])
        s["total_return_pct"] = (float(hist[-1]) - initial_bankroll) / initial_bankroll * 100
        s["n_bets"] = len(bets)

    return strategies


# ══════════════════════════════════════════════════════════════════════════════
# 4. CLV (CLOSING LINE VALUE) TRACKER
# ══════════════════════════════════════════════════════════════════════════════

def compute_clv(
    model_odds: float,
    pinnacle_open: float,
    pinnacle_close: float,
) -> Dict:
    """
    Compute CLV metrics for a single bet.

    CLV = how much Pinnacle closing moved toward our model price
    since our signal was generated.

    Positive CLV = market agrees with us (strong signal of genuine edge).
    """
    if pinnacle_open <= 1 or pinnacle_close <= 1 or model_odds <= 1:
        return {"clv_pct": 0, "beat_closing": False, "market_movement_pct": 0}

    model_implied = 1.0 / model_odds
    pin_open_implied = 1.0 / pinnacle_open
    pin_close_implied = 1.0 / pinnacle_close

    if model_implied > pin_open_implied:
        clv = (pin_close_implied - pin_open_implied) / pin_open_implied * 100
    else:
        clv = (pin_open_implied - pin_close_implied) / pin_open_implied * 100

    beat_closing = model_implied > pin_close_implied
    market_move = (pin_close_implied - pin_open_implied) / pin_open_implied * 100

    return {
        "clv_pct": round(clv, 2),
        "beat_closing": beat_closing,
        "market_movement_pct": round(market_move, 2),
        "model_implied": round(model_implied, 4),
        "pin_open_implied": round(pin_open_implied, 4),
        "pin_close_implied": round(pin_close_implied, 4),
    }


def clv_summary(clv_results: List[Dict]) -> Dict:
    """Aggregate CLV metrics across many bets."""
    if not clv_results:
        return {}

    clvs = [r["clv_pct"] for r in clv_results]
    beat_rate = np.mean([1 if r["beat_closing"] else 0 for r in clv_results])

    return {
        "n_bets": len(clv_results),
        "mean_clv_pct": round(float(np.mean(clvs)), 2),
        "median_clv_pct": round(float(np.median(clvs)), 2),
        "positive_clv_pct": round(float(np.mean([1 if c > 0 else 0 for c in clvs])) * 100, 1),
        "beat_closing_pct": round(float(beat_rate) * 100, 1),
        "clv_std": round(float(np.std(clvs)), 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. EDGE DECAY ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def edge_by_odds_band(bets: List[Dict]) -> List[Dict]:
    """
    Break down ROI by Pinnacle odds band.
    Shows whether edge is concentrated in favourites, underdogs, or balanced.
    """
    bands = [
        ("Heavy fav (1.01-1.30)", 1.01, 1.30),
        ("Fav (1.30-1.60)", 1.30, 1.60),
        ("Mild fav (1.60-2.00)", 1.60, 2.00),
        ("Coin flip (2.00-2.50)", 2.00, 2.50),
        ("Mild dog (2.50-3.50)", 2.50, 3.50),
        ("Dog (3.50-5.00)", 3.50, 5.00),
        ("Big dog (5.00+)", 5.00, 100.0),
    ]
    results = []
    for label, lo, hi in bands:
        filtered = [b for b in bets if lo <= b.get("pinnacle_odds", 0) < hi]
        if len(filtered) < 3:
            continue
        pnls = [b["pnl"] for b in filtered]
        roi = np.mean(pnls) * 100
        results.append({
            "band": label,
            "n_bets": len(filtered),
            "roi_pct": round(roi, 2),
            "win_rate": round(np.mean([1 if p > 0 else 0 for p in pnls]), 3),
            "avg_edge": round(np.mean([b["edge_pct"] for b in filtered]), 2),
        })
    return results


# ══════════════════════════════════════════════════════════════════════════════
# Charts
# ══════════════════════════════════════════════════════════════════════════════

def plot_threshold_sweep(sweep: List[Dict], optimal: Optional[Dict], out_path: str):
    """ROI with bootstrap CI vs threshold, marking the optimal."""
    if not HAS_MPL or not sweep:
        return

    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    apply_dark_style(fig, ax)

    thresholds = [s["threshold"] for s in sweep]
    rois = [s["roi_pct"] for s in sweep]
    ci_lo = [s["roi_ci_lo"] for s in sweep]
    ci_hi = [s["roi_ci_hi"] for s in sweep]
    n_bets = [s["n_bets"] for s in sweep]

    ax.fill_between(thresholds, ci_lo, ci_hi, alpha=0.2, color=CS["accent"], label="95% CI")
    ax.plot(thresholds, rois, "o-", color=CS["accent"], markersize=6, linewidth=2, label="ROI %")
    ax.axhline(0, color=CS["accent3"], alpha=0.5, linestyle="--")
    ax.axvline(10, color=CS["accent2"], alpha=0.7, linestyle="--", label="Current (10%)")
    if optimal:
        ax.axvline(optimal["threshold"], color=CS["accent4"], alpha=0.9, linestyle="-",
                   linewidth=2, label=f"Optimal ({optimal['threshold']}%)")

    ax2 = ax.twinx()
    ax2.bar(thresholds, n_bets, width=0.6, alpha=0.15, color=CS["accent2"])
    ax2.set_ylabel("# Bets", color=CS["accent2"])
    ax2.tick_params(axis="y", labelcolor=CS["accent2"])
    ax2.spines["right"].set_color(CS["grid"])

    ax.set_xlabel("Minimum Value Threshold (%)")
    ax.set_ylabel("ROI (%)")
    ax.set_title("ROI by Value Threshold (with 95% Bootstrap CI)", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=9, loc="upper left")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_kelly_growth(strategies: Dict, out_path: str):
    """Bankroll growth curves for different staking strategies."""
    if not HAS_MPL:
        return

    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    apply_dark_style(fig, ax)

    colors = {
        "flat_1u": CS["fg"],
        "kelly_25%": CS["accent"],
        "kelly_33%": CS["accent2"],
        "kelly_50%": CS["accent4"],
        "kelly_full": CS["accent3"],
    }

    for label, s in strategies.items():
        hist = s["history"]
        color = colors.get(label, CS["fg"])
        lw = 2.5 if "33%" in label or "flat" in label else 1.5
        final = s["final_bankroll"]
        dd = s["max_drawdown"]
        ax.plot(hist, color=color, linewidth=lw, alpha=0.85,
                label=f"{label}: {final:.0f} (DD {dd:.0%})")

    ax.set_xlabel("Bet Number")
    ax.set_ylabel("Bankroll")
    ax.set_title("Bankroll Growth: Flat vs Kelly Variants", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=8, loc="upper left")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_edge_by_odds_band(bands: List[Dict], out_path: str):
    """Horizontal bar chart of ROI by odds band."""
    if not HAS_MPL or not bands:
        return

    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    apply_dark_style(fig, ax)

    labels = [b["band"] for b in bands]
    rois = [b["roi_pct"] for b in bands]
    n_bets = [b["n_bets"] for b in bands]
    colors = [CS["accent"] if r > 0 else CS["accent3"] for r in rois]

    bars = ax.barh(labels, rois, color=colors, alpha=0.8)
    for bar, n in zip(bars, n_bets):
        x = bar.get_width()
        ax.text(x + (1 if x >= 0 else -1), bar.get_y() + bar.get_height()/2,
                f"n={n}", va="center", fontsize=8, color=CS["fg"], alpha=0.7)

    ax.axvline(0, color=CS["fg"], alpha=0.3)
    ax.set_xlabel("ROI (%)")
    ax.set_title("ROI by Pinnacle Odds Band", fontsize=13, fontweight="bold")
    ax.invert_yaxis()

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ══════════════════════════════════════════════════════════════════════════════
# Main: run on backtest data or strict signals
# ══════════════════════════════════════════════════════════════════════════════

def extract_bets(rows: List[Dict]) -> List[Dict]:
    """
    Extract bet-level data from backtest or strict-signals rows.
    Supports two formats:
    A) One row per match with pinnacle_odds1/2, odds1/2 - creates both sides
    B) One row per bet with bet_side, bet_result, value_pct (backtest-results format)
    """
    bets = []
    if not rows:
        return bets
    col_keys = set(rows[0].keys())

    def find_col(candidates):
        for c in candidates:
            if c in col_keys:
                return c
        return None

    # Format B: backtest-results (one bet per row)
    bet_side_col = find_col(["bet_side", "selection", "side"])
    bet_result_col = find_col(["bet_result", "result", "pnl"])
    value_col = find_col(["value_pct", "edge_pct", "value", "edge"])
    model_fav_prob_col = find_col(["model_favorite_prob", "our_prob", "p1_win_prob"])
    pin_odds_col = find_col(["pinnacle_odds", "pin_odds1"])
    pin_loser_col = find_col(["pinnacle_odds_loser", "pin_odds2"])
    pnl_col = find_col(["pnl", "profit_loss", "bet_result"])

    if bet_side_col and value_col and (pin_odds_col or pin_loser_col):
        # Format B: one bet per row
        for row in rows:
            edge = _float(row.get(value_col))
            if edge is None:
                continue
            side = str(row.get(bet_side_col, "")).strip().lower()
            result = str(row.get(bet_result_col, "")).strip().lower()
            model_prob = _float(row.get(model_fav_prob_col))
            pin_odds = _float(row.get(pin_odds_col))
            pin_loser = _float(row.get(pin_loser_col))

            # bet_side: winner = we bet on favourite, loser = we bet on underdog
            if side in ("winner", "fav", "favorite", "1"):
                odds_used = pin_odds
                prob_used = model_prob
            elif side in ("loser", "dog", "underdog", "2"):
                odds_used = pin_loser
                prob_used = 1.0 - model_prob if model_prob is not None else None
            else:
                continue

            if odds_used is None or odds_used <= 1:
                continue
            if prob_used is None:
                prob_used = 1.0 / odds_used  # fallback

            won = result in ("win", "w", "1", "true", "yes")
            pnl = (odds_used - 1.0) if won else -1.0

            bets.append({
                "edge_pct": edge,
                "pnl": pnl,
                "model_prob": prob_used,
                "pinnacle_odds": odds_used,
                "model_odds": 1.0 / prob_used if prob_used > 0 else 0,
                "p1_won": won,
                "side": side,
                "surface": row.get("surface", "Unknown") or "Unknown",
            })
        return bets

    # Format A: both sides per row
    prob_col = find_col(["p1_win_prob", "model_p1", "prob_p1", "our_prob", "predicted_prob"])
    odds1_col = find_col(["odds1", "model_odds1", "fair_odds1", "our_odds"])
    odds2_col = find_col(["odds2", "model_odds2", "fair_odds2"])
    pin1_col = find_col(["pinnacle_odds1", "pin_odds1", "closing_odds1", "pinnacle_p1"])
    pin2_col = find_col(["pinnacle_odds2", "pin_odds2", "closing_odds2", "pinnacle_p2"])
    won_col = find_col(["p1_won", "p1_win", "result"])
    wid_col = find_col(["winner_id", "actual_winner_id"])
    p1id_col = find_col(["player1_id", "p1_id"])
    surface_col = find_col(["surface"])

    for row in rows:
        model_prob = _float(row.get(prob_col)) if prob_col else None
        if model_prob is None:
            continue

        p1_won = None
        if won_col:
            v = str(row.get(won_col, "")).strip().lower()
            if v in ("1", "true", "yes", "w", "win"):
                p1_won = True
            elif v in ("0", "false", "no", "l", "loss"):
                p1_won = False
        if p1_won is None and wid_col and p1id_col:
            try:
                p1_won = int(float(row[wid_col])) == int(float(row[p1id_col]))
            except (ValueError, TypeError, KeyError):
                pass
        if p1_won is None:
            continue

        pin1 = _float(row.get(pin1_col)) if pin1_col else None
        pin2 = _float(row.get(pin2_col)) if pin2_col else None
        odds1 = _float(row.get(odds1_col)) if odds1_col else None
        odds2 = _float(row.get(odds2_col)) if odds2_col else None

        if pin1 and odds1 and pin1 > 1 and odds1 > 1:
            pin_implied1 = 1.0 / pin1
            model_implied1 = 1.0 / odds1
            edge1 = (model_implied1 - pin_implied1) / pin_implied1 * 100
            pnl1 = (pin1 - 1.0) if p1_won else -1.0
            bets.append({
                "edge_pct": edge1,
                "pnl": pnl1,
                "model_prob": model_prob,
                "pinnacle_odds": pin1,
                "model_odds": odds1,
                "p1_won": p1_won,
                "side": "P1",
                "surface": row.get(surface_col, "Unknown") if surface_col else "Unknown",
            })

        if pin2 and odds2 and pin2 > 1 and odds2 > 1:
            pin_implied2 = 1.0 / pin2
            model_implied2 = 1.0 / odds2
            edge2 = (model_implied2 - pin_implied2) / pin_implied2 * 100
            pnl2 = (pin2 - 1.0) if not p1_won else -1.0
            bets.append({
                "edge_pct": edge2,
                "pnl": pnl2,
                "model_prob": 1.0 - model_prob,
                "pinnacle_odds": pin2,
                "model_odds": odds2,
                "p1_won": not p1_won,
                "side": "P2",
                "surface": row.get(surface_col, "Unknown") if surface_col else "Unknown",
            })

    return bets


def main():
    parser = argparse.ArgumentParser(description="Il Margine Edge Analysis (Part 4)")
    parser.add_argument("--files", nargs="+", help="Backtest result CSV files")
    parser.add_argument("--strict-signals", help="Strict signals CSV")
    parser.add_argument("--out-dir", default="data/diagnostics", help="Output directory")
    parser.add_argument("--min-bets", type=int, default=30, help="Min bets for optimal threshold")
    args = parser.parse_args()

    if not args.files and not args.strict_signals:
        print("Usage: python scripts/edge-analysis.py --files data/backtest/backtest-results-2024.csv [...]")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)
    np.random.seed(42)

    # Load
    print("\n-- Loading data --")
    paths = args.files if args.files else [args.strict_signals]
    rows = load_data(paths)
    if not rows:
        print("No data loaded.")
        sys.exit(1)

    # Extract bets
    print("\n-- Extracting bets --")
    bets = extract_bets(rows)
    print(f"  Extracted {len(bets):,} bet opportunities")

    positive_edge = [b for b in bets if b["edge_pct"] > 0]
    print(f"  With positive edge: {len(positive_edge):,}")

    if len(bets) < 10:
        print("  Too few bets for analysis. Check column detection.")
        sys.exit(1)

    # -- 1. Threshold Sweep --
    print("\n-- 1. Value Threshold Sweep --")
    sweep = threshold_sweep(bets)
    optimal = find_optimal_threshold(sweep, min_bets=args.min_bets)

    report_lines = []
    report_lines.append("="*72)
    report_lines.append("  IL MARGINE - Edge Analysis Report (Part 4)")
    report_lines.append("="*72)

    report_lines.append(f"\n  Total bet opportunities: {len(bets):,}")
    report_lines.append(f"  With positive edge: {len(positive_edge):,}\n")

    report_lines.append("  -- Value Threshold Sweep --")
    report_lines.append(f"  {'Thresh':>7} {'N':>6} {'ROI%':>8} {'CI Lo':>8} {'CI Hi':>8} {'P(>0)':>7} {'Sharpe':>8} {'WinR':>7}")
    for s in sweep:
        marker = " <- current" if s["threshold"] == 10 else ""
        if optimal and s["threshold"] == optimal["threshold"]:
            marker += " * optimal"
        report_lines.append(
            f"  {s['threshold']:>6}% {s['n_bets']:>6} {s['roi_pct']:>+7.1f}% "
            f"{s['roi_ci_lo']:>+7.1f}% {s['roi_ci_hi']:>+7.1f}% "
            f"{s['prob_positive_roi']:>6.1%} {s['sharpe']:>8.3f} {s['win_rate']:>6.1%}{marker}"
        )

    if optimal:
        report_lines.append(f"\n  Optimal threshold (max Sharpe, n>={args.min_bets}): {optimal['threshold']}%")
        report_lines.append(f"    ROI: {optimal['roi_pct']:+.1f}%  CI: [{optimal['roi_ci_lo']:+.1f}%, {optimal['roi_ci_hi']:+.1f}%]")
        report_lines.append(f"    Sharpe: {optimal['sharpe']:.3f}  N: {optimal['n_bets']}  P(ROI>0): {optimal['prob_positive_roi']:.1%}")

    # -- 2. Kelly Analysis --
    print("\n-- 2. Kelly Staking Analysis --")
    kelly_bets = [b for b in bets if b["edge_pct"] >= 5]
    if len(kelly_bets) >= 10:
        strategies = kelly_analysis(kelly_bets)

        report_lines.append(f"\n  -- Kelly Staking (bets with >=5% edge, n={len(kelly_bets)}) --")
        report_lines.append(f"  {'Strategy':<16} {'Final':>10} {'Return':>10} {'Max DD':>10}")
        for label, s in strategies.items():
            report_lines.append(
                f"  {label:<16} {s['final_bankroll']:>9.1f} {s['total_return_pct']:>+9.1f}% {s['max_drawdown']:>9.1%}"
            )

        flat_ret = strategies["flat_1u"]["total_return_pct"]
        report_lines.append(f"\n  Kelly insight: if full Kelly shows negative return or >60% drawdown,")
        report_lines.append(f"  the perceived edges are likely noise. Fractional Kelly (25-33%) is")
        report_lines.append(f"  the standard for live trading.")
        if flat_ret < 0 and strategies.get("kelly_25%", {}).get("total_return_pct", 0) > 100:
            report_lines.append(f"  Note: flat ROI is negative; Kelly results are capped and may be misleading.")
    else:
        strategies = None
        report_lines.append(f"\n  Kelly: insufficient bets with >=5% edge ({len(kelly_bets)})")

    # -- 3. Edge by Odds Band --
    print("\n-- 3. Edge by Odds Band --")
    value_bets = [b for b in bets if b["edge_pct"] >= 5]
    bands = edge_by_odds_band(value_bets)

    if bands:
        report_lines.append(f"\n  -- ROI by Odds Band (>=5% edge) --")
        report_lines.append(f"  {'Band':<28} {'N':>6} {'ROI%':>8} {'WinR':>7} {'AvgEdge':>8}")
        for b in bands:
            report_lines.append(
                f"  {b['band']:<28} {b['n_bets']:>6} {b['roi_pct']:>+7.1f}% "
                f"{b['win_rate']:>6.1%} {b['avg_edge']:>+7.1f}%"
            )

    # -- 4. Edge Significance Summary --
    print("\n-- 4. Edge Significance --")
    high_edge = [b for b in bets if b["edge_pct"] >= 10]
    if high_edge:
        avg_edge = np.mean([b["edge_pct"] for b in high_edge])
        avg_odds = np.mean([b["pinnacle_odds"] for b in high_edge])
        typical_sp = 300
        typical_rp = 300
        sig_results = []
        for b in high_edge:
            sig = edge_significance(
                b["model_prob"], 1.0/b["pinnacle_odds"],
                typical_sp, typical_rp, typical_sp, typical_rp)
            sig_results.append(sig)
        pct_significant = np.mean([1 if s["significant"] else 0 for s in sig_results]) * 100
        pct_high_conf = np.mean([1 if s["confidence"] == "high" else 0 for s in sig_results]) * 100

        report_lines.append(f"\n  -- Edge Significance (>=10% edge, n={len(high_edge)}) --")
        report_lines.append(f"  Average edge: {avg_edge:+.1f}%  Average odds: {avg_odds:.2f}")
        report_lines.append(f"  Statistically significant: {pct_significant:.0f}%")
        report_lines.append(f"  High confidence: {pct_high_conf:.0f}%")
        report_lines.append(f"  (Assumes ~300 service points per player per match)")

    # -- Interpretation --
    report_lines.append(f"\n{'='*72}")
    report_lines.append(f"  Interpretation guide:")
    report_lines.append(f"  - Optimal threshold != best threshold. It's the best risk-adjusted point.")
    report_lines.append(f"  - If optimal is far from 10%, consider whether the strict policy needs adjustment.")
    report_lines.append(f"  - P(ROI>0) < 0.80 = insufficient confidence; need more data before trusting.")
    report_lines.append(f"  - Kelly full DD > 50% = edges are uncertain; use 25% Kelly or flat.")
    report_lines.append(f"  - If edge concentrates in one odds band, the model may be miscalibrated there.")
    report_lines.append(f"  - CLV is a faster signal than ROI: positive mean CLV after 50+ bets = real edge.")
    report_lines.append(f"{'='*72}\n")

    # Print and save report
    report_text = "\n".join(report_lines)
    print(report_text)

    report_path = os.path.join(args.out_dir, "edge-analysis-report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  Saved: {report_path}")

    # -- Charts --
    if HAS_MPL:
        print("\n-- Charts --")
        plot_threshold_sweep(sweep, optimal, os.path.join(args.out_dir, "threshold-sweep-ci.png"))
        if strategies:
            plot_kelly_growth(strategies, os.path.join(args.out_dir, "kelly-growth.png"))
        if bands:
            plot_edge_by_odds_band(bands, os.path.join(args.out_dir, "edge-by-odds-band.png"))

    print("\n-- Done --\n")


if __name__ == "__main__":
    main()
