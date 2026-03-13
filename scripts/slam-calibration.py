"""
Grand Slam Calibration Analysis — slam-calibration.py
======================================================
Analyses historical favourite/dog performance at Grand Slams to find
systematic biases the model can exploit or correct.

Questions answered:
  1. How do favourites perform by round at each slam?
  2. Is there a round/odds band where upsets cluster?
  3. Does the model systematically misprice specific slam rounds?
  4. What's the actual win rate vs model probability by round?
  5. Can a simple slam-round overlay improve ROI?

Uses backtest data (model probs + Pinnacle odds + outcomes).

Usage:
  python scripts/slam-calibration.py --files data/backtest/backtest-results-2022.csv data/backtest/backtest-results-2023.csv data/backtest/backtest-results-2024.csv data/backtest/backtest-results-2025.csv
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
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        return [{k: (v if v else None) for k, v in row.items()} for row in reader]


# ══════════════════════════════════════════════════════════════════════════════
# Column detection and data extraction
# ══════════════════════════════════════════════════════════════════════════════

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
        "won": find(["p1_won", "p1_win", "result"]),
        "wid": find(["winner_id", "actual_winner_id"]),
        "p1id": find(["player1_id", "p1_id"]),
        "surface": find(["surface"]),
        "series": find(["series", "tier", "tournament_tier", "category"]),
        "round": find(["round", "round_id", "round_name"]),
        "tournament": find(["tournament", "tour_name", "event"]),
        "date": find(["date", "match_date"]),
        "year": find(["year"]),
        "actual_winner": find(["actual_winner"]),
        "player1": find(["player1"]),
    }


def get_outcome(row, cm):
    if cm["won"]:
        v = str(row.get(cm["won"], "")).strip().lower()
        if v in ("1", "true", "yes", "w", "win"): return 1.0
        if v in ("0", "false", "no", "l", "loss"): return 0.0
    if cm["wid"] and cm["p1id"]:
        try:
            return 1.0 if int(float(row[cm["wid"]])) == int(float(row[cm["p1id"]])) else 0.0
        except: pass
    # Backtest format: player1 is winner, actual_winner matches player1
    if cm["actual_winner"] and cm["player1"]:
        aw = str(row.get(cm["actual_winner"]) or "").strip()
        p1 = str(row.get(cm["player1"]) or "").strip()
        if aw and p1 and aw.lower() == p1.lower():
            return 1.0
        if aw and p1:
            return 0.0
    return None


def is_grand_slam(row, cm):
    """Detect if a match is a Grand Slam."""
    series = (row.get(cm["series"]) or "").strip() if cm["series"] else ""
    tour = (row.get(cm["tournament"]) or "").strip() if cm["tournament"] else ""
    combined = (series + " " + tour).upper()
    return any(gs in combined for gs in [
        "GRAND SLAM", "AUSTRALIAN OPEN", "ROLAND GARROS", "FRENCH OPEN",
        "WIMBLEDON", "US OPEN",
    ])


def get_slam_name(row, cm):
    """Extract specific slam name."""
    tour = (row.get(cm["tournament"]) or "").strip().upper() if cm["tournament"] else ""
    series = (row.get(cm["series"]) or "").strip().upper() if cm["series"] else ""
    combined = series + " " + tour
    if "AUSTRALIAN" in combined: return "Australian Open"
    if "ROLAND" in combined or "FRENCH" in combined: return "Roland Garros"
    if "WIMBLEDON" in combined: return "Wimbledon"
    if "US OPEN" in combined: return "US Open"
    return "Grand Slam (unknown)"


ROUND_ORDER = {
    "R128": 1, "R64": 2, "R32": 3, "R16": 4,
    "QF": 5, "SF": 6, "F": 7,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "1st Round": 1, "2nd Round": 2, "3rd Round": 3, "4th Round": 4,
    "Quarter-Finals": 5, "Semi-Finals": 6, "Final": 7,
}

ROUND_LABELS = {1: "R128/R64", 2: "R64/R32", 3: "R32", 4: "R16", 5: "QF", 6: "SF", 7: "F"}


def get_round_num(row, cm):
    """Get round as numeric value (1=early, 7=final)."""
    rd = row.get(cm["round"]) if cm["round"] else None
    if rd is None:
        return None
    rd_str = str(rd).strip()
    # Try direct lookup
    if rd_str in ROUND_ORDER:
        return ROUND_ORDER[rd_str]
    # Try numeric
    try:
        v = int(float(rd_str))
        if 1 <= v <= 7:
            return v
    except (ValueError, TypeError):
        pass
    # Try partial match
    rd_upper = rd_str.upper()
    for key, val in ROUND_ORDER.items():
        if key.upper() in rd_upper:
            return val
    return None


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


# ══════════════════════════════════════════════════════════════════════════════
# Analysis
# ══════════════════════════════════════════════════════════════════════════════

def extract_slam_matches(rows, cm):
    """Extract all Grand Slam matches with full data."""
    matches = []
    for row in rows:
        if not is_grand_slam(row, cm):
            continue

        prob = _float(row.get(cm["prob"]))
        pin1 = _float(row.get(cm["pin1"]))
        pin2 = _float(row.get(cm["pin2"]))
        odds1 = _float(row.get(cm["odds1"]))
        outcome = get_outcome(row, cm)
        if prob is None or not pin1 or outcome is None or pin1 <= 1:
            continue

        # Determine favourite side
        # P1 is favourite if model prob > 0.5
        p1_is_fav = prob > 0.5

        # Pin-implied probabilities (remove overround for fair comparison)
        pin_imp1 = 1.0 / pin1
        pin_imp2 = 1.0 / pin2 if pin2 and pin2 > 1 else 1.0 - pin_imp1
        pin_total = pin_imp1 + pin_imp2
        pin_fair1 = pin_imp1 / pin_total if pin_total > 0 else pin_imp1
        pin_fair2 = 1.0 - pin_fair1

        # Favourite's prob and odds (from model and market)
        if p1_is_fav:
            fav_model_prob = prob
            fav_pin_prob = pin_fair1
            fav_pin_odds = pin1
            fav_won = outcome > 0.5
            fav_pnl = (pin1 - 1.0) if fav_won else -1.0
            dog_pin_odds = pin2 if pin2 else 1.0 / (1.0 - pin_imp1)
            dog_pnl = (dog_pin_odds - 1.0) if not fav_won else -1.0
        else:
            fav_model_prob = 1.0 - prob
            fav_pin_prob = pin_fair2
            fav_pin_odds = pin2 if pin2 and pin2 > 1 else 1.0 / (1.0 - pin_imp1)
            fav_won = outcome < 0.5
            fav_pnl = (fav_pin_odds - 1.0) if fav_won else -1.0
            dog_pin_odds = pin1
            dog_pnl = (pin1 - 1.0) if outcome > 0.5 else -1.0

        matches.append({
            "slam": get_slam_name(row, cm),
            "round": get_round_num(row, cm),
            "year": get_year(row, cm),
            "fav_model_prob": fav_model_prob,
            "fav_pin_prob": fav_pin_prob,
            "fav_pin_odds": fav_pin_odds,
            "dog_pin_odds": dog_pin_odds,
            "fav_won": fav_won,
            "fav_pnl": fav_pnl,
            "dog_pnl": dog_pnl,
            "model_edge_fav": (fav_model_prob - fav_pin_prob) / fav_pin_prob * 100 if fav_pin_prob > 0 else 0,
            "prob_raw": prob,
            "outcome": outcome,
        })

    return matches


def analyse_by_round(matches):
    """Favourite performance by round."""
    by_round = defaultdict(list)
    for m in matches:
        if m["round"] is not None:
            by_round[m["round"]].append(m)

    results = []
    for rd in sorted(by_round.keys()):
        group = by_round[rd]
        n = len(group)
        if n < 5:
            continue
        fav_wr = np.mean([1 if m["fav_won"] else 0 for m in group])
        avg_model_prob = np.mean([m["fav_model_prob"] for m in group])
        avg_pin_prob = np.mean([m["fav_pin_prob"] for m in group])
        fav_roi = np.mean([m["fav_pnl"] for m in group]) * 100
        dog_roi = np.mean([m["dog_pnl"] for m in group]) * 100
        model_bias = avg_model_prob - fav_wr  # positive = model overestimates favourite

        results.append({
            "round": rd,
            "round_label": ROUND_LABELS.get(rd, f"R{rd}"),
            "n": n,
            "fav_win_rate": round(fav_wr, 3),
            "model_fav_prob": round(avg_model_prob, 3),
            "pin_fav_prob": round(avg_pin_prob, 3),
            "model_bias": round(model_bias, 3),
            "pin_bias": round(avg_pin_prob - fav_wr, 3),
            "fav_roi": round(fav_roi, 1),
            "dog_roi": round(dog_roi, 1),
        })
    return results


def analyse_by_slam(matches):
    """Performance by individual slam."""
    by_slam = defaultdict(list)
    for m in matches:
        by_slam[m["slam"]].append(m)

    results = []
    for slam in sorted(by_slam.keys()):
        group = by_slam[slam]
        n = len(group)
        if n < 10:
            continue
        fav_wr = np.mean([1 if m["fav_won"] else 0 for m in group])
        avg_model = np.mean([m["fav_model_prob"] for m in group])
        avg_pin = np.mean([m["fav_pin_prob"] for m in group])
        fav_roi = np.mean([m["fav_pnl"] for m in group]) * 100
        dog_roi = np.mean([m["dog_pnl"] for m in group]) * 100

        results.append({
            "slam": slam,
            "n": n,
            "fav_win_rate": round(fav_wr, 3),
            "model_fav_prob": round(avg_model, 3),
            "pin_fav_prob": round(avg_pin, 3),
            "model_bias": round(avg_model - fav_wr, 3),
            "fav_roi": round(fav_roi, 1),
            "dog_roi": round(dog_roi, 1),
        })
    return results


def analyse_by_odds_band(matches):
    """Performance by favourite odds band."""
    bands = [
        ("Fav 1.01-1.15", 1.01, 1.15),
        ("Fav 1.15-1.30", 1.15, 1.30),
        ("Fav 1.30-1.50", 1.30, 1.50),
        ("Fav 1.50-1.80", 1.50, 1.80),
        ("Fav 1.80-2.20", 1.80, 2.20),
        ("Even 2.20+", 2.20, 99.0),
    ]
    results = []
    for label, lo, hi in bands:
        group = [m for m in matches if lo <= m["fav_pin_odds"] < hi]
        if len(group) < 5:
            continue
        fav_wr = np.mean([1 if m["fav_won"] else 0 for m in group])
        avg_model = np.mean([m["fav_model_prob"] for m in group])
        avg_pin = np.mean([m["fav_pin_prob"] for m in group])
        fav_roi = np.mean([m["fav_pnl"] for m in group]) * 100
        dog_roi = np.mean([m["dog_pnl"] for m in group]) * 100

        results.append({
            "band": label,
            "n": len(group),
            "fav_win_rate": round(fav_wr, 3),
            "model_fav_prob": round(avg_model, 3),
            "pin_fav_prob": round(avg_pin, 3),
            "model_bias": round(avg_model - fav_wr, 3),
            "pin_bias": round(avg_pin - fav_wr, 3),
            "fav_roi": round(fav_roi, 1),
            "dog_roi": round(dog_roi, 1),
        })
    return results


def analyse_round_x_slam(matches):
    """Cross: slam x round — where exactly do upsets happen?"""
    cross = defaultdict(list)
    for m in matches:
        if m["round"] is not None:
            cross[(m["slam"], m["round"])].append(m)

    results = []
    for (slam, rd), group in sorted(cross.items()):
        if len(group) < 5:
            continue
        fav_wr = np.mean([1 if m["fav_won"] else 0 for m in group])
        avg_model = np.mean([m["fav_model_prob"] for m in group])
        dog_roi = np.mean([m["dog_pnl"] for m in group]) * 100

        results.append({
            "slam": slam,
            "round": ROUND_LABELS.get(rd, f"R{rd}"),
            "n": len(group),
            "fav_win_rate": round(fav_wr, 3),
            "model_prob": round(avg_model, 3),
            "model_bias": round(avg_model - fav_wr, 3),
            "dog_roi": round(dog_roi, 1),
        })
    return results


def compute_calibration_overlay(matches, by="round"):
    """
    Compute a calibration overlay: for each round (or slam), how much
    should the model adjust its favourite probability?

    overlay = actual_fav_win_rate - model_fav_prob

    Positive overlay -> model underestimates favourites in this segment
    Negative overlay -> model overestimates favourites
    """
    groups = defaultdict(list)
    for m in matches:
        key = m["round"] if by == "round" else m["slam"]
        if key is not None:
            groups[key].append(m)

    overlays = {}
    for key, group in groups.items():
        if len(group) < 15:  # need minimum sample
            continue
        fav_wr = np.mean([1 if m["fav_won"] else 0 for m in group])
        model_prob = np.mean([m["fav_model_prob"] for m in group])
        overlays[key] = {
            "adjustment": round(fav_wr - model_prob, 4),
            "n": len(group),
            "actual_wr": round(fav_wr, 3),
            "model_prob": round(model_prob, 3),
        }
    return overlays


def simulate_overlay_roi(matches, overlay, by="round"):
    """
    Simulate ROI if we applied the calibration overlay.
    Adjusts model prob by the overlay amount, then recalculates edges and ROI.
    """
    adjusted_bets = []
    for m in matches:
        key = m["round"] if by == "round" else m["slam"]
        adj = overlay.get(key, {}).get("adjustment", 0)

        # Adjust model favourite probability
        adj_fav_prob = m["fav_model_prob"] + adj
        adj_fav_prob = max(0.05, min(0.98, adj_fav_prob))

        # Recalculate edge vs Pinnacle
        edge = (adj_fav_prob - m["fav_pin_prob"]) / m["fav_pin_prob"] * 100 if m["fav_pin_prob"] > 0 else 0

        adjusted_bets.append({
            "fav_won": m["fav_won"],
            "fav_pnl": m["fav_pnl"],
            "dog_pnl": m["dog_pnl"],
            "edge_fav": edge,
            "edge_dog": -edge,
            "round": m["round"],
            "slam": m["slam"],
        })

    # ROI when betting the side with >5% edge
    fav_bets = [b for b in adjusted_bets if b["edge_fav"] > 5]
    dog_bets = [b for b in adjusted_bets if b["edge_dog"] > 5]
    all_bets = fav_bets + dog_bets

    fav_roi = np.mean([b["fav_pnl"] for b in fav_bets]) * 100 if fav_bets else 0
    dog_roi = np.mean([b["dog_pnl"] for b in dog_bets]) * 100 if dog_bets else 0
    all_pnl = sum(b["fav_pnl"] for b in fav_bets) + sum(b["dog_pnl"] for b in dog_bets)
    n_total = len(fav_bets) + len(dog_bets)
    all_roi = (all_pnl / n_total * 100) if n_total > 0 else 0

    return {
        "n_fav_bets": len(fav_bets),
        "fav_roi": round(fav_roi, 1),
        "n_dog_bets": len(dog_bets),
        "dog_roi": round(dog_roi, 1),
        "n_total": n_total,
        "all_roi": round(all_roi, 1),
        "total_pnl": round(all_pnl, 1),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Charts
# ══════════════════════════════════════════════════════════════════════════════

def plot_round_calibration(round_results, out_path):
    """Model prob vs actual win rate by round."""
    if not HAS_MPL or not round_results:
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.patch.set_facecolor(CS["bg"])
    for ax in [ax1, ax2]:
        apply_dark_style(fig, ax)

    labels = [r["round_label"] for r in round_results]
    x = np.arange(len(labels))

    # Left: calibration (model vs actual vs Pinnacle)
    ax1.plot(x, [r["fav_win_rate"] for r in round_results], "s-", color=CS["fg"],
             markersize=8, linewidth=2, label="Actual fav win rate")
    ax1.plot(x, [r["model_fav_prob"] for r in round_results], "o-", color=CS["accent"],
             markersize=8, linewidth=2, label="Model fav prob")
    ax1.plot(x, [r["pin_fav_prob"] for r in round_results], "^-", color=CS["accent2"],
             markersize=8, linewidth=2, label="Pinnacle fav prob")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=9)
    ax1.set_ylabel("Probability")
    ax1.set_title("Grand Slam: Model vs Market vs Reality by Round", fontsize=11, fontweight="bold")
    ax1.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=8)

    # Right: ROI (fav vs dog)
    width = 0.35
    ax2.bar(x - width/2, [r["fav_roi"] for r in round_results], width,
            color=CS["accent"], alpha=0.8, label="Fav ROI")
    ax2.bar(x + width/2, [r["dog_roi"] for r in round_results], width,
            color=CS["accent3"], alpha=0.8, label="Dog ROI")
    ax2.axhline(0, color=CS["fg"], alpha=0.4, linestyle="--")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=9)
    ax2.set_ylabel("ROI (%)")
    ax2.set_title("Fav vs Dog ROI by Round", fontsize=11, fontweight="bold")
    ax2.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=8)

    for i, r in enumerate(round_results):
        ax2.text(i, max(r["fav_roi"], r["dog_roi"]) + 2, f"n={r['n']}",
                 ha="center", fontsize=7, color=CS["fg"], alpha=0.6)

    fig.suptitle("Grand Slam Calibration by Round", color=CS["fg"], fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_bias_heatmap(cross_results, out_path):
    """Heatmap: model bias by slam x round."""
    if not HAS_MPL or not cross_results:
        return

    slams = sorted(set(r["slam"] for r in cross_results))
    rounds = sorted(set(r["round"] for r in cross_results))

    if len(slams) < 2 or len(rounds) < 2:
        return

    data = np.full((len(slams), len(rounds)), np.nan)
    for r in cross_results:
        si = slams.index(r["slam"])
        ri = rounds.index(r["round"])
        data[si, ri] = r["model_bias"]

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    apply_dark_style(fig, ax)

    im = ax.imshow(data, cmap="RdYlGn_r", aspect="auto", vmin=-0.15, vmax=0.15)
    ax.set_xticks(range(len(rounds)))
    ax.set_xticklabels(rounds, fontsize=9)
    ax.set_yticks(range(len(slams)))
    ax.set_yticklabels(slams, fontsize=9)

    # Annotate cells
    for i in range(len(slams)):
        for j in range(len(rounds)):
            if not np.isnan(data[i, j]):
                ax.text(j, i, f"{data[i,j]:+.2f}", ha="center", va="center",
                        fontsize=8, color="white" if abs(data[i,j]) > 0.08 else CS["fg"])

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Model Bias (+ = overestimates fav)", color=CS["fg"])
    cbar.ax.yaxis.set_tick_params(color=CS["fg"])
    plt.setp(plt.getp(cbar.ax, "yticklabels"), color=CS["fg"])

    ax.set_title("Model Bias: Slam x Round (green = underestimates fav = upsets underpriced)",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Grand Slam Calibration Analysis")
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--out-dir", default="data/diagnostics")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    np.random.seed(42)

    print("\n" + "="*72)
    print("  IL MARGINE - Grand Slam Calibration Analysis")
    print("="*72)

    # Load
    all_rows = []
    for p in args.files:
        rows = load_csv(p)
        print(f"  {len(rows):,} rows from {os.path.basename(p)}")
        all_rows.extend(rows)

    cm = detect_columns(all_rows)
    matches = extract_slam_matches(all_rows, cm)
    print(f"\n  Grand Slam matches: {len(matches):,}")
    if len(matches) < 20:
        print("  Not enough Grand Slam data.")
        sys.exit(1)

    years = set(m["year"] for m in matches if m["year"])
    slams = set(m["slam"] for m in matches)
    print(f"  Years: {sorted(years)}")
    print(f"  Slams: {sorted(slams)}")

    report = []
    report.append("="*72)
    report.append("  GRAND SLAM CALIBRATION ANALYSIS")
    report.append("="*72)

    # -- 1. By Round --
    print(f"\n-- 1. Performance by Round --")
    round_results = analyse_by_round(matches)
    report.append(f"\n  -- By Round --")
    report.append(f"  {'Round':<12} {'N':>5} {'FavWR':>7} {'Model':>7} {'Pin':>7} {'MBias':>7} {'FavROI':>8} {'DogROI':>8}")
    for r in round_results:
        direction = "+fav" if r["model_bias"] > 0.02 else "-dog" if r["model_bias"] < -0.02 else "  OK"
        report.append(f"  {r['round_label']:<12} {r['n']:>5} {r['fav_win_rate']:>7.1%} {r['model_fav_prob']:>7.1%} "
                      f"{r['pin_fav_prob']:>7.1%} {r['model_bias']:>+6.1%} {r['fav_roi']:>+7.1f}% {r['dog_roi']:>+7.1f}% {direction}")
        print(f"  {r['round_label']}: FavWR={r['fav_win_rate']:.1%} Model={r['model_fav_prob']:.1%} "
              f"Bias={r['model_bias']:+.1%} FavROI={r['fav_roi']:+.1f}% DogROI={r['dog_roi']:+.1f}%")

    # -- 2. By Slam --
    print(f"\n-- 2. Performance by Slam --")
    slam_results = analyse_by_slam(matches)
    report.append(f"\n  -- By Slam --")
    report.append(f"  {'Slam':<20} {'N':>5} {'FavWR':>7} {'Model':>7} {'Bias':>7} {'FavROI':>8} {'DogROI':>8}")
    for s in slam_results:
        report.append(f"  {s['slam']:<20} {s['n']:>5} {s['fav_win_rate']:>7.1%} {s['model_fav_prob']:>7.1%} "
                      f"{s['model_bias']:>+6.1%} {s['fav_roi']:>+7.1f}% {s['dog_roi']:>+7.1f}%")
        print(f"  {s['slam']}: FavWR={s['fav_win_rate']:.1%} Bias={s['model_bias']:+.1%} DogROI={s['dog_roi']:+.1f}%")

    # -- 3. By Odds Band --
    print(f"\n-- 3. Performance by Odds Band --")
    band_results = analyse_by_odds_band(matches)
    report.append(f"\n  -- By Favourite Odds Band --")
    report.append(f"  {'Band':<20} {'N':>5} {'FavWR':>7} {'Model':>7} {'Pin':>7} {'MBias':>7} {'PBias':>7}")
    for b in band_results:
        report.append(f"  {b['band']:<20} {b['n']:>5} {b['fav_win_rate']:>7.1%} {b['model_fav_prob']:>7.1%} "
                      f"{b['pin_fav_prob']:>7.1%} {b['model_bias']:>+6.1%} {b['pin_bias']:>+6.1%}")
        print(f"  {b['band']}: FavWR={b['fav_win_rate']:.1%} ModelBias={b['model_bias']:+.1%} PinBias={b['pin_bias']:+.1%}")

    # -- 4. Cross: Slam x Round --
    print(f"\n-- 4. Slam x Round (upset hotspots) --")
    cross_results = analyse_round_x_slam(matches)
    upsets = [r for r in cross_results if r["model_bias"] < -0.03]
    if upsets:
        report.append(f"\n  -- Upset Hotspots (model underestimates dogs) --")
        for u in sorted(upsets, key=lambda x: x["model_bias"]):
            report.append(f"  {u['slam']:<20} {u['round']:<8} n={u['n']:>3} "
                          f"FavWR={u['fav_win_rate']:.1%} Model={u['model_prob']:.1%} "
                          f"Bias={u['model_bias']:+.1%} DogROI={u['dog_roi']:+.1f}%")

    fav_overpriced = [r for r in cross_results if r["model_bias"] > 0.03]
    if fav_overpriced:
        report.append(f"\n  -- Model Overestimates Favourite --")
        for u in sorted(fav_overpriced, key=lambda x: -x["model_bias"]):
            report.append(f"  {u['slam']:<20} {u['round']:<8} n={u['n']:>3} "
                          f"FavWR={u['fav_win_rate']:.1%} Model={u['model_prob']:.1%} "
                          f"Bias={u['model_bias']:+.1%}")

    # -- 5. Calibration Overlay --
    print(f"\n-- 5. Calibration Overlay --")
    round_overlay = compute_calibration_overlay(matches, by="round")
    slam_overlay = compute_calibration_overlay(matches, by="slam")

    report.append(f"\n  -- Round Calibration Overlay --")
    report.append(f"  Apply these adjustments to the model's favourite probability:")
    for key in sorted(round_overlay.keys()):
        o = round_overlay[key]
        label = ROUND_LABELS.get(key, f"R{key}")
        direction = "boost fav" if o["adjustment"] > 0 else "boost dog" if o["adjustment"] < 0 else "neutral"
        report.append(f"    {label:<12} {o['adjustment']:>+.3f}  (actual={o['actual_wr']:.1%} model={o['model_prob']:.1%} n={o['n']}) -> {direction}")
        print(f"  {label}: adjust {o['adjustment']:+.3f} ({direction})")

    # -- 6. Simulated ROI with overlay --
    print(f"\n-- 6. ROI with Overlay --")
    baseline_sim = simulate_overlay_roi(matches, {}, by="round")
    round_sim = simulate_overlay_roi(matches, round_overlay, by="round")

    report.append(f"\n  -- Simulated ROI (>5% edge, in-sample) --")
    report.append(f"  {'Method':<25} {'N':>5} {'ROI':>8} {'PnL':>8}")
    report.append(f"  {'No overlay':<25} {baseline_sim['n_total']:>5} {baseline_sim['all_roi']:>+7.1f}% {baseline_sim['total_pnl']:>+7.1f}u")
    report.append(f"  {'Round overlay':<25} {round_sim['n_total']:>5} {round_sim['all_roi']:>+7.1f}% {round_sim['total_pnl']:>+7.1f}u")
    print(f"  Baseline: {baseline_sim['all_roi']:+.1f}% (n={baseline_sim['n_total']})")
    print(f"  With round overlay: {round_sim['all_roi']:+.1f}% (n={round_sim['n_total']})")

    report.append(f"\n  [!] Overlay ROI is IN-SAMPLE. To validate, fit on 2022-2023, test on 2024-2025.")

    # Print and save
    report_text = "\n".join(report)
    print(f"\n{report_text}")

    report_path = os.path.join(args.out_dir, "slam-calibration-report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\n  Saved: {report_path}")

    # Charts
    if HAS_MPL:
        print(f"\n-- Charts --")
        plot_round_calibration(round_results, os.path.join(args.out_dir, "slam-round-calibration.png"))
        plot_bias_heatmap(cross_results, os.path.join(args.out_dir, "slam-bias-heatmap.png"))

    print(f"\n  Done.\n")


if __name__ == "__main__":
    main()
