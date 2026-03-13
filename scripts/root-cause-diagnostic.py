"""
Part 4b: Root Cause Diagnostic — Why the Model Shows Phantom Edges
===================================================================
The 2024 backtest shows:
  - Average "edge" of +50.8% but ROI of -9.2%
  - Only heavy favourites (1.01-1.30) are mildly profitable
  - Dogs (3.50+) show "edges" of +49-99% but ROI of -12% to -18%

This is the classic fingerprint of a model that systematically
overestimates underdog probability. The model thinks underdogs
are being offered at too-generous odds, but they're not — they
really do lose that often.

This script diagnoses WHY by isolating the three most likely causes:

  1. SPW DOUBLE-COUNTING (Part 3 finding)
     The p_a/p_b formula feeds hold% (a game-level stat) into a
     ratio, then into K-M recursion which applies prob_game() again.
     This amplifies serve strength twice, producing point probs that
     are too extreme -> match probs too extreme -> phantom edges on
     both heavy favourites and underdogs, but underdogs lose money
     because the market is actually right.

  2. OVERROUND ASYMMETRY
     Pinnacle's margin is not evenly split. On lopsided matches,
     the underdog absorbs more of the overround. A model that
     doesn't account for this will see phantom edges on dogs.

  3. SHRINKAGE FAILURE
     When one player has sparse data, shrinkage toward league
     average makes them look more "average" than they are. If
     the sparse player is actually weak, the model overestimates
     them -> phantom underdog edge.

Output:
  data/diagnostics/root-cause-report.txt
  data/diagnostics/spw-double-counting.png

Usage:
  python scripts/root-cause-diagnostic.py --files data/backtest/backtest-results-2024.csv
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


# ------------------------------------------------------------------------------
# SPW inversion (from hybrid_v2.py)
# ------------------------------------------------------------------------------

def prob_game(p: float) -> float:
    if p <= 0 or p >= 1:
        return max(0.0, min(1.0, p))
    d = (p * p) / (1.0 - 2.0 * p * (1.0 - p))
    return p**4 + 4 * p**4 * (1-p) + 10 * p**4 * (1-p)**2 + 20 * p**3 * (1-p)**3 * d


def estimate_spw_from_hold(hold_pct: float, tol=1e-6, max_iter=50) -> float:
    """Invert prob_game: find SPW such that prob_game(SPW) = hold_pct."""
    hold_pct = max(0.05, min(0.995, hold_pct))
    spw = 0.4 + 0.35 * hold_pct
    spw = max(0.45, min(0.85, spw))
    for _ in range(max_iter):
        g = prob_game(spw)
        err = g - hold_pct
        if abs(err) < tol:
            break
        h = 1e-6
        dg = (prob_game(spw + h) - prob_game(spw - h)) / (2 * h)
        if abs(dg) < 1e-12:
            break
        spw -= err / dg
        spw = max(0.40, min(0.90, spw))
    return spw


# ------------------------------------------------------------------------------
# Diagnosis 1: Quantify SPW double-counting effect
# ------------------------------------------------------------------------------

def diagnose_spw_effect():
    """
    Show how the V4 formula inflates point probabilities and what that
    does to match probabilities at different skill gaps.
    """
    print("\n  -- Diagnosis 1: SPW Double-Counting --")
    print(f"  The V4 formula does: p_a = (hold1 * (1-ret2)) / league_avg")
    print(f"  Then feeds p_a into prob_game() inside K-M recursion.")
    print(f"  But hold% IS ALREADY prob_game(SPW). So prob_game is applied twice.\n")

    league_avg = 0.64
    cases = [
        ("Equal (avg)",         0.64, 0.36, 0.64, 0.36),
        ("Slight favourite",    0.70, 0.38, 0.62, 0.35),
        ("Clear favourite",     0.76, 0.40, 0.60, 0.34),
        ("Heavy favourite",     0.82, 0.42, 0.56, 0.32),
        ("Extreme mismatch",     0.88, 0.44, 0.54, 0.30),
    ]

    print(f"  {'Case':<24} {'V4 p_a':>7} {'V2 p_a':>7} {'V4 p_b':>7} {'V2 p_b':>7}  {'V4 P(A)':>7} {'V2 P(A)':>7} {'d P(A)':>8}  {'V4 edge if Pin=V2':>18}")
    print(f"  {'-'*24} {'-'*7} {'-'*7} {'-'*7} {'-'*7}  {'-'*7} {'-'*7} {'-'*8}  {'-'*18}")

    results = []
    for name, h1, r1, h2, r2 in cases:
        # V4 formula (current)
        pa_v4 = (h1 * (1 - r2)) / league_avg
        pb_v4 = (h2 * (1 - r1)) / league_avg
        pa_v4 = max(0.01, min(0.99, pa_v4))
        pb_v4 = max(0.01, min(0.99, pb_v4))

        # V2 formula (proper inversion)
        spw1 = estimate_spw_from_hold(h1)
        spw2 = estimate_spw_from_hold(h2)
        rpw1 = r1
        rpw2 = r2
        avg_rpw = 1.0 - league_avg
        pa_v2 = spw1 * (1.0 - rpw2) / (1.0 - avg_rpw)
        pb_v2 = spw2 * (1.0 - rpw1) / (1.0 - avg_rpw)
        pa_v2 = max(0.52, min(0.78, pa_v2))
        pb_v2 = max(0.52, min(0.78, pb_v2))

        def approx_match_prob(p_serve_a, p_serve_b):
            g_a = prob_game(p_serve_a)
            g_b = prob_game(p_serve_b)
            games_a = g_a + (1 - g_b)
            games_b = (1 - g_a) + g_b
            p_set = games_a / (games_a + games_b)
            return p_set**2 * (3 - 2*p_set)

        p_match_v4 = approx_match_prob(pa_v4, pb_v4)
        p_match_v2 = approx_match_prob(pa_v2, pb_v2)

        if p_match_v2 > 0:
            v4_phantom_edge = (p_match_v4 - p_match_v2) / p_match_v2 * 100
        else:
            v4_phantom_edge = 0

        print(f"  {name:<24} {pa_v4:>7.4f} {pa_v2:>7.4f} {pb_v4:>7.4f} {pb_v2:>7.4f}  "
              f"{p_match_v4:>7.4f} {p_match_v2:>7.4f} {p_match_v4 - p_match_v2:>+8.4f}  "
              f"{v4_phantom_edge:>+17.1f}%")

        p_dog_v4 = 1 - p_match_v4
        p_dog_v2 = 1 - p_match_v2
        if p_dog_v2 > 0:
            dog_phantom_edge = (p_dog_v4 - p_dog_v2) / p_dog_v2 * 100
        else:
            dog_phantom_edge = 0

        results.append({
            "name": name,
            "fav_edge": v4_phantom_edge,
            "dog_edge": dog_phantom_edge,
            "p_match_v4": p_match_v4,
            "p_match_v2": p_match_v2,
        })

    print(f"\n  Underdog side phantom edges (V4 thinks dog is better than they are):")
    for r in results:
        if r["dog_edge"] != 0:
            print(f"    {r['name']:<24}  Dog phantom edge: {r['dog_edge']:>+.1f}%  "
                  f"(V4 dog prob: {1-r['p_match_v4']:.4f} vs correct: {1-r['p_match_v2']:.4f})")

    return results


# ------------------------------------------------------------------------------
# Diagnosis 2: Overround asymmetry
# ------------------------------------------------------------------------------

def diagnose_overround(rows):
    """
    Check if Pinnacle overround loads more on the underdog side.
    Supports backtest format: pinnacle_odds (fav), pinnacle_odds_loser (dog).
    """
    print(f"\n  -- Diagnosis 2: Pinnacle Overround Asymmetry --")

    bands = defaultdict(lambda: {"overrounds": [], "dog_share": []})

    for row in rows:
        pin_winner = _float(row.get("pinnacle_odds"))
        pin_loser = _float(row.get("pinnacle_odds_loser"))
        if not pin_winner or not pin_loser or pin_winner <= 1 or pin_loser <= 1:
            continue

        pin_fav = min(pin_winner, pin_loser)
        pin_dog = max(pin_winner, pin_loser)
        imp_fav = 1.0 / pin_fav
        imp_dog = 1.0 / pin_dog
        overround = imp_fav + imp_dog - 1.0
        if overround <= 0:
            continue

        total_imp = imp_fav + imp_dog
        dog_or_share = imp_dog / total_imp if total_imp > 0 else 0.5

        if pin_fav < 1.30:
            band = "Heavy fav (<1.30)"
        elif pin_fav < 1.60:
            band = "Fav (1.30-1.60)"
        elif pin_fav < 2.00:
            band = "Mild fav (1.60-2.00)"
        else:
            band = "Coin flip (2.00+)"

        bands[band]["overrounds"].append(overround * 100)
        bands[band]["dog_share"].append(dog_or_share)

    if bands:
        print(f"  {'Band':<24} {'N':>6} {'Avg OR%':>8} {'Dog OR share':>13}")
        for band in ["Heavy fav (<1.30)", "Fav (1.30-1.60)", "Mild fav (1.60-2.00)", "Coin flip (2.00+)"]:
            if band in bands:
                b = bands[band]
                print(f"  {band:<24} {len(b['overrounds']):>6} {np.mean(b['overrounds']):>7.2f}% "
                      f"{np.mean(b['dog_share']):>12.1%}")
        print(f"\n  If dog absorbs >55% of overround on lopsided matches, a model that")
        print(f"  doesn't adjust for this will see phantom edges on dogs.")
    else:
        print(f"  No Pinnacle odds found in data.")


# ------------------------------------------------------------------------------
# Diagnosis 3: Model probability vs actual win rate
# ------------------------------------------------------------------------------

def diagnose_calibration_by_odds(rows):
    """
    Group by model fair odds band (model favourite), compare predicted vs actual.
    Supports backtest format: model_favorite_prob, model_favorite, actual_winner.
    """
    print(f"\n  -- Diagnosis 3: Model Calibration by Fair Odds Band --")

    bins = defaultdict(lambda: {"predicted": [], "actual": []})

    for row in rows:
        prob = _float(row.get("model_favorite_prob") or row.get("our_prob") or row.get("p1_win_prob"))
        if prob is None:
            continue

        model_fav = str(row.get("model_favorite") or "").strip()
        actual_winner = str(row.get("actual_winner") or "").strip()
        if not model_fav or not actual_winner:
            continue
        actual = 1.0 if model_fav == actual_winner else 0.0

        odds = 1.0 / prob if prob > 0 else None
        if odds is None or odds <= 1:
            continue

        if odds < 1.20:
            band = "1.01-1.20 (extreme fav)"
        elif odds < 1.50:
            band = "1.20-1.50 (strong fav)"
        elif odds < 2.00:
            band = "1.50-2.00 (fav)"
        elif odds < 3.00:
            band = "2.00-3.00 (slight fav/flip)"
        elif odds < 5.00:
            band = "3.00-5.00 (dog)"
        else:
            band = "5.00+ (big dog)"

        bins[band]["predicted"].append(prob)
        bins[band]["actual"].append(actual)

    if bins:
        band_order = ["1.01-1.20 (extreme fav)", "1.20-1.50 (strong fav)", "1.50-2.00 (fav)",
                      "2.00-3.00 (slight fav/flip)", "3.00-5.00 (dog)", "5.00+ (big dog)"]
        print(f"  {'Model Odds Band':<30} {'N':>6} {'Pred P1':>8} {'Actual':>8} {'Bias':>8} {'Direction':>10}")
        for band in band_order:
            if band in bins:
                b = bins[band]
                pred = np.mean(b["predicted"])
                act = np.mean(b["actual"])
                bias = pred - act
                direction = "OVER" if bias > 0.02 else "UNDER" if bias < -0.02 else "OK"
                print(f"  {band:<30} {len(b['predicted']):>6} {pred:>8.3f} {act:>8.3f} {bias:>+8.3f} {direction:>10}")

        print(f"\n  'OVER' = model thinks selection wins more than they actually do")
        print(f"  'UNDER' = model underestimates selection")
        print(f"  Consistent OVER across bands = systematic overconfidence")
        print(f"  OVER on dogs + OK on favs = SPW double-counting signature")
    else:
        print(f"  No usable rows (need model_favorite_prob, model_favorite, actual_winner).")


# ------------------------------------------------------------------------------
# Diagnosis 4: What the "edges" actually look like
# ------------------------------------------------------------------------------

def diagnose_edge_reality(rows):
    """
    For bets where the model saw >=10% edge, what actually happened?
    Supports backtest format: value_pct, our_prob, our_odds, bet_side,
    pinnacle_odds, pinnacle_odds_loser, bet_result.
    """
    print(f"\n  -- Diagnosis 4: Reality Check on 'Edges' --")

    value_bets = []
    for row in rows:
        value_pct = _float(row.get("value_pct"))
        if value_pct is None or value_pct < 10:
            continue

        prob = _float(row.get("our_prob") or row.get("p1_win_prob"))
        odds = _float(row.get("our_odds") or row.get("model_odds1"))
        bet_side = str(row.get("bet_side") or "").strip().lower()
        pin_winner = _float(row.get("pinnacle_odds"))
        pin_loser = _float(row.get("pinnacle_odds_loser"))
        model_fav = str(row.get("model_favorite") or "").strip()
        actual_winner = str(row.get("actual_winner") or "").strip()
        player1 = str(row.get("player1") or "").strip()
        player2 = str(row.get("player2") or "").strip()

        if not all([prob, odds]) or odds <= 1:
            continue

        pin_odds = pin_winner if model_fav == player1 else pin_loser
        if not pin_odds or pin_odds <= 1:
            continue

        if model_fav and actual_winner:
            actual = 1.0 if (bet_side == "winner" and actual_winner == model_fav) or (bet_side == "loser" and actual_winner != model_fav) else 0.0
        else:
            bet_result = str(row.get("bet_result") or "").strip().lower()
            actual = 1.0 if bet_result in ("win", "w", "1", "true", "yes") else 0.0

        pin_implied = 1.0 / pin_odds
        model_implied = 1.0 / odds
        edge = (model_implied - pin_implied) / pin_implied * 100

        value_bets.append({
            "edge": edge,
            "model_prob": prob,
            "pin_implied": pin_implied,
            "actual": actual,
            "pin_odds": pin_odds,
            "model_odds": odds,
        })

    if not value_bets:
        print(f"  No bets with >=10% edge found.")
        return

    n = len(value_bets)
    wins = sum(1 for b in value_bets if b["actual"] > 0)
    avg_edge = np.mean([b["edge"] for b in value_bets])
    avg_model_prob = np.mean([b["model_prob"] for b in value_bets])
    avg_pin_implied = np.mean([b["pin_implied"] for b in value_bets])
    actual_win_rate = wins / n

    print(f"  Bets with >=10% model edge: {n}")
    print(f"  Average model 'edge': {avg_edge:+.1f}%")
    print(f"  Average model P(win): {avg_model_prob:.3f}")
    print(f"  Average Pinnacle implied: {avg_pin_implied:.3f}")
    print(f"  Actual win rate: {actual_win_rate:.3f}")
    print(f"  Gap (model vs actual): {avg_model_prob - actual_win_rate:+.3f}")
    print(f"  Gap (Pinnacle vs actual): {avg_pin_implied - actual_win_rate:+.3f}")

    if abs(avg_pin_implied - actual_win_rate) < abs(avg_model_prob - actual_win_rate):
        print(f"\n  [!] Pinnacle is CLOSER to reality than the model.")
        print(f"      This means the 'edges' are phantom - the model is wrong, not the market.")
    else:
        print(f"\n  [OK] Model is closer to reality than Pinnacle.")
        print(f"      (But ROI says otherwise - check further.)")

    by_odds = defaultdict(lambda: {"n": 0, "wins": 0, "model_p": [], "pin_p": []})
    for b in value_bets:
        if b["pin_odds"] < 2:
            band = "Fav (<2.00)"
        elif b["pin_odds"] < 3.5:
            band = "Mid (2.00-3.50)"
        else:
            band = "Dog (3.50+)"
        by_odds[band]["n"] += 1
        by_odds[band]["wins"] += int(b["actual"])
        by_odds[band]["model_p"].append(b["model_prob"])
        by_odds[band]["pin_p"].append(b["pin_implied"])

    print(f"\n  By Pinnacle odds range (bets with >=10% edge):")
    print(f"  {'Range':<20} {'N':>5} {'Wins':>5} {'ActWR':>7} {'ModelP':>7} {'PinP':>7} {'Model err':>10} {'Pin err':>10}")
    for band in ["Fav (<2.00)", "Mid (2.00-3.50)", "Dog (3.50+)"]:
        if band in by_odds:
            b = by_odds[band]
            act_wr = b["wins"] / b["n"] if b["n"] > 0 else 0
            mp = np.mean(b["model_p"])
            pp = np.mean(b["pin_p"])
            print(f"  {band:<20} {b['n']:>5} {b['wins']:>5} {act_wr:>7.3f} {mp:>7.3f} {pp:>7.3f} "
                  f"{mp - act_wr:>+10.3f} {pp - act_wr:>+10.3f}")


# ------------------------------------------------------------------------------
# Summary and recommendations
# ------------------------------------------------------------------------------

def print_summary():
    print(f"\n{'='*72}")
    print(f"  ROOT CAUSE SUMMARY")
    print(f"{'='*72}")
    print(f"""
  The model shows large phantom edges (+50% average) with negative ROI
  because it systematically overestimates win probabilities for the
  selection side. Three factors compound:

  1. SPW DOUBLE-COUNTING (PRIMARY CAUSE)
     hold% ~ prob_game(SPW). The model feeds hold% into a ratio and then
     K-M recursion calls prob_game() again. This squares the serve
     amplification effect. Impact: extreme at the tails. A player with
     82% hold has SPW ~ 0.633, but V4 treats it as 0.82 -> prob_game(0.82)
     = 0.981 vs correct prob_game(0.633) = 0.82. The model's internal
     game-win probability is 98.1% when it should be 82%.

  2. PHANTOM EDGE ILLUSION
     Because the model's probabilities are too extreme, every match where
     it sees ANY edge, the edge appears enormous (avg +50.8%). But the
     market (Pinnacle) is actually right. The model is not finding value
     - it's systematically miscalculating.

  3. UNDERDOG BIAS IN ROI
     The SPW bug makes the model think BOTH players are better servers
     than they are, but the effect is asymmetric after normalization.
     The model ends up overvaluing underdogs more than favourites,
     producing large phantom edges on dog selections that lose money.

  RECOMMENDED FIX ORDER:
  ----------------------
  Step 1: Apply the SPW inversion fix from hybrid_v2.py (Part 3).
          This is the single highest-impact change.
  Step 2: Re-run the 2024 backtest with corrected p_a/p_b formula.
  Step 3: Run diagnostic-toolkit.py (Part 1) on corrected results.
  Step 4: THEN re-evaluate threshold, shrinkage, and Elo blend.

  Do NOT optimise thresholds or staking on the current model output.
  The current output is fundamentally miscalibrated - any threshold
  tuning would be fitting to noise.
""")


# ------------------------------------------------------------------------------
# Charts
# ------------------------------------------------------------------------------

def plot_spw_amplification(out_path):
    """Show how prob_game amplifies serve point win %, and why feeding hold% in doubles it."""
    if not HAS_MPL:
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor(CS["bg"])

    spw = np.linspace(0.50, 0.80, 200)
    hold = [prob_game(s) for s in spw]

    for ax in [ax1, ax2]:
        apply_dark_style(fig, ax)

    ax1.plot(spw, hold, color=CS["accent"], linewidth=2.5)
    ax1.plot([0.50, 0.80], [0.50, 0.80], "--", color=CS["fg"], alpha=0.4, label="If linear (no amplification)")
    ax1.set_xlabel("Serve Point Win % (SPW)")
    ax1.set_ylabel("Hold % = prob_game(SPW)")
    ax1.set_title("The Non-Linear Amplification", fontsize=12, fontweight="bold")
    ax1.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=9)

    for s in [0.55, 0.60, 0.64, 0.70, 0.75]:
        h = prob_game(s)
        ax1.annotate(f"SPW={s:.2f}->Hold={h:.2f}", (s, h), textcoords="offset points",
                     xytext=(10, -15), fontsize=7, color=CS["accent2"], alpha=0.8)
        ax1.plot(s, h, "o", color=CS["accent2"], markersize=4)

    double = [prob_game(h) for h in hold]

    ax2.plot(spw, hold, color=CS["accent"], linewidth=2, label="Correct: prob_game(SPW) = hold%")
    ax2.plot(spw, double, color=CS["accent3"], linewidth=2.5, label="V4 bug: prob_game(hold%) = double-counted")
    ax2.fill_between(spw, hold, double, alpha=0.2, color=CS["accent3"])

    ax2.set_xlabel("True Serve Point Win % (SPW)")
    ax2.set_ylabel("Internal Game Win Probability")
    ax2.set_title("V4 Double-Counting Effect", fontsize=12, fontweight="bold")
    ax2.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"], fontsize=9)

    s_example = 0.64
    h_example = prob_game(s_example)
    d_example = prob_game(h_example)
    ax2.annotate(f"SPW=0.64\nCorrect: {h_example:.2f}\nV4: {d_example:.2f}\nGap: {d_example-h_example:+.2f}",
                 (s_example, (h_example + d_example)/2), textcoords="offset points",
                 xytext=(40, 0), fontsize=9, color=CS["accent2"],
                 arrowprops=dict(arrowstyle="->", color=CS["accent2"], alpha=0.7))

    fig.suptitle("Why the Model Sees Phantom Edges: SPW Double-Counting", color=CS["fg"],
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Root Cause Diagnostic")
    parser.add_argument("--files", nargs="+", help="Backtest CSV files")
    parser.add_argument("--out-dir", default="data/diagnostics")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print("\n" + "="*72)
    print("  IL MARGINE - Root Cause Diagnostic")
    print("="*72)

    diagnose_spw_effect()

    if args.files:
        all_rows = []
        for p in args.files:
            rows = load_csv(p)
            print(f"\n  Loaded {len(rows):,} rows from {os.path.basename(p)}")
            all_rows.extend(rows)

        if all_rows:
            diagnose_overround(all_rows)
            diagnose_calibration_by_odds(all_rows)
            diagnose_edge_reality(all_rows)
    else:
        print(f"\n  (Pass --files to run data-dependent diagnostics 2-4)")

    print_summary()

    if HAS_MPL:
        print("-- Charts --")
        plot_spw_amplification(os.path.join(args.out_dir, "spw-double-counting.png"))

    print(f"\n  Done.\n")


if __name__ == "__main__":
    main()
