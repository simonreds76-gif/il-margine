"""
Probability Calibration - calibrate-probs.py
==============================================
The model's probability distribution is too wide (overconfident).
91% of bet opportunities show "positive edge" vs Pinnacle, but ROI
is negative. This means the model sees phantom edges because its
probabilities are too extreme, not because it's finding real value.

Fix: post-hoc calibration that compresses model probabilities toward
their true empirical frequencies.

Three methods (in increasing sophistication):

  1. TEMPERATURE SCALING (1 parameter)
     calibrated = sigmoid(logit(raw) / T)
     T > 1 compresses toward 0.5 (less confident)
     Simplest, often sufficient, no overfitting risk.

  2. PLATT SCALING (2 parameters)
     calibrated = sigmoid(a * logit(raw) + b)
     Handles both confidence and bias simultaneously.

  3. ISOTONIC REGRESSION (non-parametric)
     Monotone step function mapping model probs to observed frequencies.
     Most flexible, but needs more data and can overfit.

Usage:
  # Fit on training data (e.g. 2022-2023)
  python scripts/calibrate-probs.py --train data/backtest/backtest-results-2023.csv --test data/backtest/backtest-results-2024.csv

  # Or fit on all available data (use with caution - in-sample)
  python scripts/calibrate-probs.py --files data/backtest/backtest-results-2024.csv

  # Apply to live pipeline (exports calibration parameters)
  python scripts/calibrate-probs.py --train data/backtest/backtest-results-2023.csv --export calibration-params.json

Integration:
  In oncourt-compute-fair-odds.py, after computing p1_win:
    from calibrate_probs import apply_temperature
    p1_win = apply_temperature(p1_win, T=<fitted value>)

Respects: Iteration 4 policy lock. This is a post-hoc adjustment
layer, not a model change. Backtest comparison still required.
"""

import os
import sys
import csv
import math
import json
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


# ------------------------------------------------------------------------------
# Core calibration functions (importable for live pipeline)
# ------------------------------------------------------------------------------

def logit(p: float) -> float:
    """Log-odds: logit(p) = log(p / (1-p))."""
    p = max(1e-6, min(1 - 1e-6, p))
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    """Inverse logit: sigmoid(x) = 1 / (1 + exp(-x))."""
    x = max(-20, min(20, x))
    return 1.0 / (1.0 + math.exp(-x))


def apply_temperature(p: float, T: float) -> float:
    """
    Temperature scaling: compress (T>1) or sharpen (T<1) probabilities.
    calibrated = sigmoid(logit(p) / T)

    T=1.0: no change
    T=1.5: moderate compression toward 0.5
    T=2.0: strong compression
    T=0.8: sharpening (more confident)
    """
    if T <= 0:
        return p
    return sigmoid(logit(p) / T)


def apply_platt(p: float, a: float, b: float) -> float:
    """
    Platt scaling: calibrated = sigmoid(a * logit(p) + b)
    a controls confidence (a<1 compresses), b controls bias shift.
    """
    return sigmoid(a * logit(p) + b)


# ------------------------------------------------------------------------------
# Fitting
# ------------------------------------------------------------------------------

def extract_prob_outcome(rows):
    """
    Extract (model_prob, actual_outcome, row) from backtest rows.
    Supports backtest format: model_favorite_prob, model_favorite, actual_winner.
    Returns list of (prob, outcome, row) for alignment with simulate_roi.
    """
    result = []
    col_keys = set(rows[0].keys()) if rows else set()

    def find_col(candidates):
        for c in candidates:
            if c in col_keys:
                return c
        return None

    prob_col = find_col(["model_favorite_prob", "our_prob", "p1_win_prob", "model_p1", "prob_p1", "predicted_prob"])
    model_fav_col = find_col(["model_favorite"])
    actual_winner_col = find_col(["actual_winner"])
    won_col = find_col(["p1_won", "p1_win", "result", "bet_result"])
    wid_col = find_col(["winner_id", "actual_winner_id"])
    p1id_col = find_col(["player1_id", "p1_id"])

    for row in rows:
        p = _float(row.get(prob_col)) if prob_col else None
        if p is None:
            continue

        actual = None
        if model_fav_col and actual_winner_col:
            model_fav = str(row.get(model_fav_col) or "").strip()
            actual_winner = str(row.get(actual_winner_col) or "").strip()
            if model_fav and actual_winner:
                actual = 1.0 if model_fav == actual_winner else 0.0
        if actual is None and won_col:
            v = str(row.get(won_col, "")).strip().lower()
            if v in ("1", "true", "yes", "w", "win"):
                actual = 1.0
            elif v in ("0", "false", "no", "l", "loss"):
                actual = 0.0
        if actual is None and wid_col and p1id_col:
            try:
                actual = 1.0 if int(float(row[wid_col])) == int(float(row[p1id_col])) else 0.0
            except (ValueError, TypeError, KeyError):
                continue
        if actual is None:
            continue

        result.append((p, actual, row))

    return result


def fit_temperature(pairs, T_range=None):
    """
    Find optimal temperature T that minimises log-loss on calibration data.
    Uses grid search (safe, no convergence issues).
    pairs: list of (prob, outcome) or (prob, outcome, row)
    """
    if T_range is None:
        T_range = np.arange(0.5, 4.01, 0.01)

    probs = np.array([x[0] for x in pairs])
    outcomes = np.array([x[1] for x in pairs])
    eps = 1e-10

    best_T = 1.0
    best_ll = float("inf")

    for T in T_range:
        cal = np.array([sigmoid(logit(p) / T) for p in probs])
        cal = np.clip(cal, eps, 1 - eps)
        ll = -np.mean(outcomes * np.log(cal) + (1 - outcomes) * np.log(1 - cal))
        if ll < best_ll:
            best_ll = ll
            best_T = T

    return float(best_T), float(best_ll)


def fit_platt(pairs, n_iter=200, lr=0.01):
    """
    Fit Platt scaling parameters (a, b) via gradient descent on log-loss.
    pairs: list of (prob, outcome) or (prob, outcome, row)
    """
    probs = np.array([x[0] for x in pairs])
    outcomes = np.array([x[1] for x in pairs])
    logits = np.array([logit(p) for p in probs])
    eps = 1e-10

    a, b = 1.0, 0.0

    for _ in range(n_iter):
        z = a * logits + b
        cal = 1.0 / (1.0 + np.exp(-np.clip(z, -20, 20)))
        cal = np.clip(cal, eps, 1 - eps)

        err = cal - outcomes
        grad_a = np.mean(err * logits)
        grad_b = np.mean(err)

        a -= lr * grad_a
        b -= lr * grad_b

        a = max(0.1, min(3.0, a))
        b = max(-2.0, min(2.0, b))

    cal = np.array([sigmoid(a * l + b) for l in logits])
    cal = np.clip(cal, eps, 1 - eps)
    ll = -np.mean(outcomes * np.log(cal) + (1 - outcomes) * np.log(1 - cal))

    return float(a), float(b), float(ll)


# ------------------------------------------------------------------------------
# Evaluation
# ------------------------------------------------------------------------------

def evaluate(pairs, label="Raw", transform_fn=None):
    """
    Compute calibration metrics for a set of (prob, outcome) pairs.
    pairs: list of (prob, outcome) or (prob, outcome, row)
    """
    probs = np.array([x[0] for x in pairs])
    outcomes = np.array([x[1] for x in pairs])

    if transform_fn:
        probs = np.array([transform_fn(p) for p in probs])

    eps = 1e-10
    probs_c = np.clip(probs, eps, 1 - eps)

    ll = -np.mean(outcomes * np.log(probs_c) + (1 - outcomes) * np.log(1 - probs_c))
    bs = np.mean((probs - outcomes) ** 2)

    n_bins = 10
    bins = defaultdict(lambda: {"sum_p": 0, "sum_o": 0, "n": 0})
    for p, o in zip(probs, outcomes):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b]["sum_p"] += p
        bins[b]["sum_o"] += o
        bins[b]["n"] += 1

    cal_error = 0.0
    max_cal_error = 0.0
    for b in range(n_bins):
        if bins[b]["n"] > 0:
            pred = bins[b]["sum_p"] / bins[b]["n"]
            obs = bins[b]["sum_o"] / bins[b]["n"]
            err = abs(pred - obs)
            cal_error += bins[b]["n"] * err
            max_cal_error = max(max_cal_error, err)
    ece = cal_error / len(probs) if len(probs) > 0 else 0.0

    p25 = float(np.percentile(probs, 25)) if len(probs) > 0 else 0.5
    p75 = float(np.percentile(probs, 75)) if len(probs) > 0 else 0.5
    spread = p75 - p25

    return {
        "label": label,
        "n": len(probs),
        "logloss": round(ll, 5),
        "brier": round(bs, 5),
        "ece": round(ece, 5),
        "max_cal_error": round(max_cal_error, 4),
        "prob_spread_iqr": round(spread, 4),
        "mean_prob": round(float(np.mean(probs)), 4) if len(probs) > 0 else 0.5,
        "probs": probs,
        "outcomes": outcomes,
    }


def simulate_roi(pairs, transform_fn=None, threshold=10):
    """
    Simulate ROI at given threshold using calibrated probabilities.
    pairs: list of (prob, outcome, row) from extract_prob_outcome.
    Backtest format: pinnacle_odds (winner), pinnacle_odds_loser (loser).
    Fav = min(winner, loser) odds, dog = max.
    """
    bets = []
    for item in pairs:
        if len(item) >= 3:
            prob, outcome, row = item[0], item[1], item[2]
        else:
            continue

        cal_prob = transform_fn(prob) if transform_fn else prob
        pin_winner = _float(row.get("pinnacle_odds"))
        pin_loser = _float(row.get("pinnacle_odds_loser"))
        if not pin_winner or not pin_loser or pin_winner <= 1 or pin_loser <= 1:
            continue

        pin_fav = min(pin_winner, pin_loser)
        pin_dog = max(pin_winner, pin_loser)

        fav_implied = 1.0 / pin_fav
        dog_implied = 1.0 / pin_dog
        model_fav_prob = cal_prob
        model_dog_prob = 1.0 - cal_prob

        edge_fav = (model_fav_prob - fav_implied) / fav_implied * 100
        edge_dog = (model_dog_prob - dog_implied) / dog_implied * 100

        if edge_fav >= threshold:
            pnl = (pin_fav - 1.0) if outcome > 0.5 else -1.0
            bets.append({"edge": edge_fav, "pnl": pnl})
        if edge_dog >= threshold:
            pnl = (pin_dog - 1.0) if outcome < 0.5 else -1.0
            bets.append({"edge": edge_dog, "pnl": pnl})

    if not bets:
        return {"n": 0, "roi": 0, "total_pnl": 0, "avg_edge": 0}

    pnls = [b["pnl"] for b in bets]
    return {
        "n": len(bets),
        "roi": round(float(np.mean(pnls)) * 100, 2),
        "total_pnl": round(sum(pnls), 2),
        "avg_edge": round(float(np.mean([b["edge"] for b in bets])), 1),
    }


# ------------------------------------------------------------------------------
# Charts
# ------------------------------------------------------------------------------

def plot_calibration_comparison(results, out_path):
    if not HAS_MPL:
        return

    fig, ax = plt.subplots(1, 1, figsize=(8, 7))
    apply_dark_style(fig, ax)

    ax.plot([0, 1], [0, 1], "--", color=CS["fg"], alpha=0.4, label="Perfect")

    colors = [CS["accent3"], CS["accent"], CS["accent2"], CS["accent4"]]
    for i, res in enumerate(results):
        probs = res["probs"]
        outcomes = res["outcomes"]
        n_bins = 10
        mids, obs = [], []
        for b in range(n_bins):
            mask = (probs >= b/n_bins) & (probs < (b+1)/n_bins)
            if np.sum(mask) >= 5:
                mids.append(float(np.mean(probs[mask])))
                obs.append(float(np.mean(outcomes[mask])))

        color = colors[i % len(colors)]
        ax.plot(mids, obs, "o-", color=color, markersize=7, linewidth=2,
                label=f"{res['label']} (LL={res['logloss']:.4f})")

    ax.set_xlabel("Predicted P(win)")
    ax.set_ylabel("Observed win rate")
    ax.set_title("Calibration: Raw vs Temperature-Scaled", fontsize=13, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_temperature_sweep(T_range, logloss_values, best_T, out_path):
    if not HAS_MPL:
        return

    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    apply_dark_style(fig, ax)

    ax.plot(T_range, logloss_values, color=CS["accent"], linewidth=2)
    ax.axvline(best_T, color=CS["accent2"], linewidth=2, linestyle="--",
               label=f"Optimal T={best_T:.2f}")
    ax.axvline(1.0, color=CS["accent3"], linewidth=1, linestyle=":", alpha=0.6,
               label="T=1.0 (uncalibrated)")

    ax.set_xlabel("Temperature T")
    ax.set_ylabel("Log-Loss")
    ax.set_title("Temperature Scaling: Log-Loss Optimisation", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_probability_histograms(results, out_path):
    if not HAS_MPL or len(results) < 2:
        return

    fig, axes = plt.subplots(1, len(results), figsize=(5*len(results), 4))
    if len(results) == 1:
        axes = [axes]
    fig.patch.set_facecolor(CS["bg"])

    colors = [CS["accent3"], CS["accent"], CS["accent2"], CS["accent4"]]
    for i, (ax, res) in enumerate(zip(axes, results)):
        apply_dark_style(fig, ax)
        ax.hist(res["probs"], bins=30, color=colors[i%len(colors)], alpha=0.7, edgecolor=CS["bg"])
        ax.axvline(0.5, color=CS["fg"], alpha=0.4, linestyle="--")
        ax.set_title(f"{res['label']}\nIQR={res['prob_spread_iqr']:.3f}", color=CS["fg"], fontsize=10)
        ax.set_xlabel("P(P1 wins)")
        ax.set_xlim(0, 1)

    fig.suptitle("Probability Distribution: Before vs After Calibration", color=CS["fg"],
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Probability Calibration")
    parser.add_argument("--files", nargs="+", help="Backtest CSV files (in-sample fit + eval)")
    parser.add_argument("--train", nargs="+", help="Training set CSV(s) (fit calibration). Multiple files are concatenated.")
    parser.add_argument("--test", help="Test set CSV (evaluate calibration)")
    parser.add_argument("--export", help="Export calibration params to JSON file")
    parser.add_argument("--out-dir", default="data/diagnostics")
    args = parser.parse_args()

    if not args.files and not args.train:
        print("Usage:")
        print("  python scripts/calibrate-probs.py --train backtest-2023.csv --test backtest-2024.csv")
        print("  python scripts/calibrate-probs.py --train backtest-2022.csv backtest-2023.csv --test backtest-2024.csv")
        print("  python scripts/calibrate-probs.py --files backtest-2024.csv")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)

    print("\n" + "="*72)
    print("  IL MARGINE - Probability Calibration")
    print("="*72)

    if args.train:
        print(f"\n-- Loading training data --")
        train_rows = []
        for p in args.train:
            rows = load_csv(p)
            print(f"  {len(rows):,} rows from {os.path.basename(p)}")
            train_rows.extend(rows)
        train_pairs = extract_prob_outcome(train_rows)
        print(f"  Train pairs: {len(train_pairs):,} (from {len(args.train)} file(s))")

        if args.test:
            test_rows = load_csv(args.test)
            print(f"  Test: {len(test_rows):,} rows from {os.path.basename(args.test)}")
            test_pairs = extract_prob_outcome(test_rows)
            print(f"  Test pairs: {len(test_pairs):,}")
        else:
            test_rows = train_rows
            test_pairs = train_pairs
            print(f"  (No test set; evaluating in-sample)")
    else:
        print(f"\n-- Loading data --")
        all_rows = []
        for p in args.files:
            rows = load_csv(p)
            print(f"  {len(rows):,} rows from {os.path.basename(p)}")
            all_rows.extend(rows)
        train_rows = all_rows
        test_rows = all_rows
        train_pairs = extract_prob_outcome(all_rows)
        test_pairs = train_pairs
        print(f"  Pairs: {len(train_pairs):,} (in-sample)")

    if len(train_pairs) < 50:
        print("  Too few pairs. Check data.")
        sys.exit(1)

    print(f"\n-- 1. Baseline (uncalibrated) --")
    raw_eval = evaluate(test_pairs, "Raw (uncalibrated)")
    print(f"  Log-loss:     {raw_eval['logloss']:.5f}")
    print(f"  Brier:        {raw_eval['brier']:.5f}")
    print(f"  ECE:          {raw_eval['ece']:.5f}")
    print(f"  Max cal err:  {raw_eval['max_cal_error']:.4f}")
    print(f"  Prob IQR:     {raw_eval['prob_spread_iqr']:.4f}")

    print(f"\n-- 2. Temperature Scaling --")
    T_range = np.arange(0.50, 4.01, 0.01)
    best_T, best_ll = fit_temperature(train_pairs, T_range)
    print(f"  Optimal T: {best_T:.2f}")
    print(f"  Train log-loss at T={best_T:.2f}: {best_ll:.5f}")

    temp_eval = evaluate(test_pairs, f"Temperature (T={best_T:.2f})",
                         lambda p: apply_temperature(p, best_T))
    print(f"  Test log-loss: {temp_eval['logloss']:.5f} (raw: {raw_eval['logloss']:.5f}, d={temp_eval['logloss']-raw_eval['logloss']:+.5f})")
    print(f"  Test Brier:    {temp_eval['brier']:.5f} (raw: {raw_eval['brier']:.5f}, d={temp_eval['brier']-raw_eval['brier']:+.5f})")
    print(f"  Test ECE:      {temp_eval['ece']:.5f} (raw: {raw_eval['ece']:.5f})")
    print(f"  Prob IQR:      {temp_eval['prob_spread_iqr']:.4f} (raw: {raw_eval['prob_spread_iqr']:.4f})")

    sweep_ll = []
    for T in T_range:
        _, ll = fit_temperature(train_pairs, np.array([T]))
        sweep_ll.append(ll)

    print(f"\n-- 3. Platt Scaling --")
    platt_a, platt_b, platt_ll = fit_platt(train_pairs)
    print(f"  Platt params: a={platt_a:.4f}, b={platt_b:.4f}")
    print(f"  Train log-loss: {platt_ll:.5f}")

    platt_eval = evaluate(test_pairs, f"Platt (a={platt_a:.2f}, b={platt_b:.2f})",
                          lambda p: apply_platt(p, platt_a, platt_b))
    print(f"  Test log-loss: {platt_eval['logloss']:.5f}")
    print(f"  Test Brier:    {platt_eval['brier']:.5f}")
    print(f"  Test ECE:      {platt_eval['ece']:.5f}")

    print(f"\n-- 4. ROI Simulation (calibrated) --")

    for threshold in [5, 7, 10, 15]:
        raw_roi = simulate_roi(test_pairs, None, threshold)
        temp_roi = simulate_roi(test_pairs, lambda p: apply_temperature(p, best_T), threshold)
        platt_roi = simulate_roi(test_pairs, lambda p: apply_platt(p, platt_a, platt_b), threshold)

        print(f"\n  Threshold >={threshold}%:")
        print(f"    {'Method':<24} {'N':>6} {'ROI%':>8} {'AvgEdge':>8} {'PnL':>8}")
        print(f"    {'Raw':<24} {raw_roi['n']:>6} {raw_roi['roi']:>+7.1f}% {raw_roi.get('avg_edge', 0):>+7.1f}% {raw_roi['total_pnl']:>+7.1f}")
        print(f"    {'Temperature T=' + f'{best_T:.2f}':<24} {temp_roi['n']:>6} {temp_roi['roi']:>+7.1f}% {temp_roi.get('avg_edge', 0):>+7.1f}% {temp_roi['total_pnl']:>+7.1f}")
        print(f"    {'Platt a=' + f'{platt_a:.2f}' + ' b=' + f'{platt_b:.2f}':<24} {platt_roi['n']:>6} {platt_roi['roi']:>+7.1f}% {platt_roi.get('avg_edge', 0):>+7.1f}% {platt_roi['total_pnl']:>+7.1f}")

    print(f"\n{'='*72}")
    print(f"  SUMMARY")
    print(f"{'='*72}")
    print(f"\n  Temperature T={best_T:.2f} means the model's raw logits should be")
    print(f"  divided by {best_T:.2f} before converting to probabilities.")
    if best_T > 1.5:
        print(f"\n  T={best_T:.2f} is VERY high - the model is severely overconfident.")
        p_cal = apply_temperature(0.80, best_T)
        print(f"  A player the model gives 80% to actually wins about {p_cal:.0%} of the time.")
    elif best_T > 1.1:
        print(f"\n  T={best_T:.2f} indicates moderate overconfidence.")
    else:
        print(f"\n  T={best_T:.2f} is close to 1 - the model is reasonably calibrated.")

    print(f"\n  How to integrate:")
    print(f"  In oncourt-compute-fair-odds.py, after the final p1_win calculation:")
    print(f"    p1_win = apply_temperature(p1_win, T={best_T:.2f})")
    print(f"    p2_win = 1.0 - p1_win")
    print(f"\n  Where apply_temperature is from calibrate_probs:")
    print(f"    from calibrate_probs import apply_temperature")
    print(f"{'='*72}\n")

    if args.export:
        params = {
            "temperature": best_T,
            "platt_a": platt_a,
            "platt_b": platt_b,
            "fitted_on": args.train or str(args.files),
            "train_n": len(train_pairs),
            "train_logloss_raw": raw_eval["logloss"] if test_pairs is train_pairs else None,
            "train_logloss_temp": best_ll,
        }
        export_path = args.export if os.path.isabs(args.export) else os.path.join(args.out_dir, args.export)
        with open(export_path, "w") as f:
            json.dump(params, f, indent=2)
        print(f"  Exported: {export_path}")

    if HAS_MPL:
        print(f"\n-- Charts --")
        plot_calibration_comparison(
            [raw_eval, temp_eval, platt_eval],
            os.path.join(args.out_dir, "calibration-before-after.png"))
        plot_temperature_sweep(
            T_range, sweep_ll, best_T,
            os.path.join(args.out_dir, "temperature-sweep.png"))
        plot_probability_histograms(
            [raw_eval, temp_eval],
            os.path.join(args.out_dir, "prob-distribution-calibrated.png"))

    print(f"\n  Done.\n")


if __name__ == "__main__":
    main()
