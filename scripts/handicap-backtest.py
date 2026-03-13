"""
Handicap Backtest - handicap_backtest.py
=========================================

IMPORTANT: Do NOT use ML-odds inversion to synthesise "Pinnacle implied handicap".
The mapping from match probability to (p_a, p_b) is NOT unique. Many pairs produce
the same match win probability but completely different margin distributions.
Sinner (0.70) vs Shapovalov (0.58) has a different margin distribution than
two players at 0.64 +/- 0.03, even though both give the same match win prob.
ROI from comparing model vs inverted-ML handicap is measuring inversion-method
difference, not real market inefficiency.

CORRECT USAGE: Run against REAL Pinnacle spread lines from bookmaker_odds_snapshot
(spread_line, spread_odds1, spread_odds2). The spread scrape is in place; collect
2-3 weeks of data, then backtest model handicap probs vs actual market lines.

Usage (when real spread data available):
  python scripts/handicap_backtest.py --files data/backtest/backtest-results-2024.csv
  python scripts/handicap_backtest.py --files data/backtest/backtest-results-2022.csv data/backtest/backtest-results-2023.csv data/backtest/backtest-results-2024.csv data/backtest/backtest-results-2025.csv

Requirements:
  - handicap_probs.py in scripts/
  - Backtest CSVs with our_prob, pinnacle_odds, pinnacle_odds_loser, score, actual_winner
"""

import os
import sys
import csv
import argparse
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from handicap_probs import (
    prob_dog_covers,
    prob_fav_covers,
)

try:
    from src.lib.tennis_prob import prob_match_best_of_3, prob_game
except ImportError:
    from handicap_probs import prob_game

    def prob_match_best_of_3(p_a, p_b):
        from functools import lru_cache

        @lru_cache(maxsize=4096)
        def _ps(a, b, pai, pbi, s):
            pa, pb = pai / 10000, pbi / 10000
            if a >= 6 and a - b >= 2:
                return 1.0
            if b >= 6 and b - a >= 2:
                return 0.0
            if a == 6 and b == 6:
                return pa / (pa + (1 - pb)) if (pa + (1 - pb)) > 0 else 0.5
            pw = prob_game(pa) if s else 1 - prob_game(pb)
            return pw * _ps(a + 1, b, pai, pbi, not s) + (1 - pw) * _ps(a, b + 1, pai, pbi, not s)

        def ps(pa, pb, af=True):
            return _ps(
                0,
                0,
                int(round(max(0.01, min(0.99, pa)) * 10000)),
                int(round(max(0.01, min(0.99, pb)) * 10000)),
                af,
            )

        s1 = ps(p_a, p_b, True)
        s2 = ps(p_a, p_b, False)
        return s1 * s2 + s1 * (1 - s2) * s1 + (1 - s1) * s2 * s1

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


# Invert K-M: from match probability -> implied p_a, p_b
def invert_km_symmetric(match_prob: float, tol: float = 0.0005, max_iter: int = 50) -> tuple:
    match_prob = max(0.02, min(0.98, match_prob))
    base = 0.62
    lo, hi = -0.15, 0.15
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        p_a = max(0.50, min(0.80, base + mid))
        p_b = max(0.50, min(0.80, base - mid))
        computed = prob_match_best_of_3(p_a, p_b)
        if abs(computed - match_prob) < tol:
            return p_a, p_b
        if computed < match_prob:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2
    return max(0.50, min(0.80, base + k)), max(0.50, min(0.80, base - k))


def invert_km_asymmetric(match_prob: float, model_p_a: float, model_p_b: float,
                         tol: float = 0.001, max_iter: int = 40) -> tuple:
    match_prob = max(0.02, min(0.98, match_prob))
    if model_p_a + model_p_b < 0.01:
        return invert_km_symmetric(match_prob)
    lo, hi = 0.85, 1.15
    for _ in range(max_iter):
        k = (lo + hi) / 2
        p_a = max(0.50, min(0.80, model_p_a * k))
        p_b = max(0.50, min(0.80, model_p_b * k))
        computed = prob_match_best_of_3(p_a, p_b)
        if abs(computed - match_prob) < tol:
            return p_a, p_b
        if computed < match_prob:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    return max(0.50, min(0.80, model_p_a * k)), max(0.50, min(0.80, model_p_b * k))


def parse_score(score_str: str) -> dict | None:
    if not score_str or not str(score_str).strip():
        return None
    score_str = str(score_str).strip().upper()
    if "W/O" in score_str or "WALKOVER" in score_str:
        return None
    games_a, games_b = 0, 0
    sets_a, sets_b = 0, 0
    for part in score_str.replace("  ", " ").split():
        part = part.strip().rstrip(")")
        if "(" in part:
            part = part[: part.index("(")]
        if "RET" in part:
            continue
        pieces = part.split("-")
        if len(pieces) == 2:
            try:
                a, b = int(pieces[0]), int(pieces[1])
                games_a += a
                games_b += b
                if a > b:
                    sets_a += 1
                else:
                    sets_b += 1
            except ValueError:
                continue
    if games_a + games_b == 0:
        return None
    return {
        "games_a": games_a,
        "games_b": games_b,
        "margin": games_a - games_b,
        "sets_a": sets_a,
        "sets_b": sets_b,
        "n_sets": sets_a + sets_b,
        "straight_sets": (sets_a + sets_b) == 2,
    }


def detect_columns(rows):
    keys = set(rows[0].keys()) if rows else set()

    def find(candidates):
        for c in candidates:
            if c in keys:
                return c
        return None

    return {
        "prob": find(["p1_win_prob", "our_prob", "model_p1", "prob_p1"]),
        "odds1": find(["odds1", "model_odds1"]),
        "odds2": find(["odds2", "model_odds2"]),
        "pin1": find(["pinnacle_odds1", "pinnacle_odds", "pin_odds1", "closing_odds1"]),
        "pin2": find(["pinnacle_odds2", "pinnacle_odds_loser", "pin_odds2", "closing_odds2"]),
        "won": find(["p1_won", "p1_win", "bet_result"]),
        "wid": find(["winner_id", "actual_winner_id"]),
        "p1id": find(["player1_id", "p1_id"]),
        "actual_winner": find(["actual_winner"]),
        "player1": find(["player1"]),
        "player2": find(["player2"]),
        "score": find(["score", "result_score", "match_score", "result"]),
        "surface": find(["surface"]),
        "series": find(["series", "tier", "tournament_tier"]),
        "year": find(["year"]),
        "p_a": find(["p_a", "p_serve_a", "model_p_a"]),
        "p_b": find(["p_b", "p_serve_b", "model_p_b"]),
    }


def get_outcome(row, cm):
    if cm["actual_winner"] and cm["player1"]:
        aw = str(row.get(cm["actual_winner"]) or "").strip()
        p1 = str(row.get(cm["player1"]) or "").strip()
        if aw and p1:
            return 1.0 if aw == p1 else 0.0
    if cm["won"]:
        v = str(row.get(cm["won"], "")).strip().lower()
        if v in ("1", "true", "yes", "w", "win"):
            return 1.0
        if v in ("0", "false", "no", "l", "loss"):
            return 0.0
    return None


def run_handicap_backtest(rows, cm, lines=None):
    if lines is None:
        lines = [2.5, 3.5, 4.5, 5.5, 6.5]
    results = {line: {"bets_fav": [], "bets_dog": []} for line in lines}
    skipped = {"no_prob": 0, "no_pinnacle": 0, "no_score": 0, "no_outcome": 0}

    processed = 0
    for row in rows:
        model_prob = _float(row.get(cm["prob"]))
        pin1 = _float(row.get(cm["pin1"]))
        pin2 = _float(row.get(cm["pin2"]))
        outcome = get_outcome(row, cm)

        if model_prob is None:
            skipped["no_prob"] += 1
            continue
        if not pin1 or not pin2 or pin1 <= 1 or pin2 <= 1:
            skipped["no_pinnacle"] += 1
            continue
        if outcome is None:
            skipped["no_outcome"] += 1
            continue

        score_str = row.get(cm["score"]) if cm["score"] else None
        score = parse_score(str(score_str)) if score_str else None
        if score is None:
            skipped["no_score"] += 1
            continue

        p1_is_fav = model_prob > 0.5
        actual_margin = score["margin"] if outcome > 0.5 else -score["margin"]
        if p1_is_fav:
            fav_margin = actual_margin
        else:
            fav_margin = -actual_margin

        model_pa = _float(row.get(cm["p_a"])) if cm["p_a"] else None
        model_pb = _float(row.get(cm["p_b"])) if cm["p_b"] else None

        if model_pa is None or model_pb is None:
            model_pa, model_pb = invert_km_symmetric(model_prob)
            if not p1_is_fav:
                model_pa, model_pb = model_pb, model_pa

        if p1_is_fav:
            fav_pa, dog_pb = model_pa, model_pb
        else:
            fav_pa, dog_pb = model_pb, model_pa

        pin_imp1 = 1.0 / pin1
        pin_imp2 = 1.0 / pin2
        pin_total = pin_imp1 + pin_imp2
        pin_fair1 = pin_imp1 / pin_total if pin_total > 0 else 0.5
        pin_fair_fav = pin_fair1 if p1_is_fav else (1 - pin_fair1)

        pin_pa, pin_pb = invert_km_asymmetric(pin_fair_fav, fav_pa, dog_pb)

        for line in lines:
            model_dog_covers = prob_dog_covers(fav_pa, dog_pb, line)
            model_fav_covers = prob_fav_covers(fav_pa, dog_pb, line)
            pin_dog_covers = prob_dog_covers(pin_pa, pin_pb, line)
            pin_fav_covers = prob_fav_covers(pin_pa, pin_pb, line)

            if pin_dog_covers > 0.01:
                dog_edge = (model_dog_covers - pin_dog_covers) / pin_dog_covers * 100
                pin_dog_odds = 1.0 / pin_dog_covers
                dog_covered = fav_margin < line
                dog_pnl = (pin_dog_odds - 1.0) if dog_covered else -1.0
                results[line]["bets_dog"].append({
                    "edge": dog_edge,
                    "pnl": dog_pnl,
                    "model_prob": model_dog_covers,
                    "pin_prob": pin_dog_covers,
                    "pin_odds": pin_dog_odds,
                    "covered": dog_covered,
                    "actual_margin": fav_margin,
                    "surface": (row.get(cm["surface"]) or "").strip() if cm["surface"] else "",
                    "series": (row.get(cm["series"]) or "").strip() if cm["series"] else "",
                })

            if pin_fav_covers > 0.01:
                fav_edge = (model_fav_covers - pin_fav_covers) / pin_fav_covers * 100
                pin_fav_odds = 1.0 / pin_fav_covers
                fav_covered = fav_margin > line
                fav_pnl = (pin_fav_odds - 1.0) if fav_covered else -1.0
                results[line]["bets_fav"].append({
                    "edge": fav_edge,
                    "pnl": fav_pnl,
                    "model_prob": model_fav_covers,
                    "pin_prob": pin_fav_covers,
                    "pin_odds": pin_fav_odds,
                    "covered": fav_covered,
                    "actual_margin": fav_margin,
                    "surface": (row.get(cm["surface"]) or "").strip() if cm["surface"] else "",
                    "series": (row.get(cm["series"]) or "").strip() if cm["series"] else "",
                })

        processed += 1

    return results, processed, skipped


def analyse_line(bets, label, threshold=5):
    if not bets:
        return None
    qualifying = [b for b in bets if b["edge"] >= threshold]
    if len(qualifying) < 10:
        return {"label": label, "n_total": len(bets), "n_qualifying": len(qualifying), "insufficient": True}
    pnls = np.array([b["pnl"] for b in qualifying])
    roi = float(np.mean(pnls)) * 100
    win_rate = float(np.mean([1 if b["covered"] else 0 for b in qualifying]))
    avg_edge = float(np.mean([b["edge"] for b in qualifying]))
    avg_odds = float(np.mean([b["pin_odds"] for b in qualifying]))
    return {
        "label": label,
        "n_total": len(bets),
        "n_qualifying": len(qualifying),
        "roi": round(roi, 2),
        "win_rate": round(win_rate, 3),
        "avg_edge": round(avg_edge, 1),
        "avg_odds": round(avg_odds, 2),
        "total_pnl": round(float(np.sum(pnls)), 1),
    }


def plot_handicap_roi(line_results, out_path):
    if not HAS_MPL:
        return
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    apply_dark_style(fig, ax)
    lines_plotted = []
    dog_rois = []
    fav_rois = []
    dog_ns = []
    fav_ns = []
    for line, data in sorted(line_results.items()):
        dog = data.get("dog_analysis")
        fav = data.get("fav_analysis")
        if (dog and not dog.get("insufficient")) or (fav and not fav.get("insufficient")):
            lines_plotted.append(line)
            dog_rois.append(dog["roi"] if dog and not dog.get("insufficient") else 0)
            fav_rois.append(fav["roi"] if fav and not fav.get("insufficient") else 0)
            dog_ns.append(dog.get("n_qualifying", 0) if dog else 0)
            fav_ns.append(fav.get("n_qualifying", 0) if fav else 0)
    if not lines_plotted:
        return
    x = np.arange(len(lines_plotted))
    width = 0.35
    ax.bar(x - width / 2, dog_rois, width, color=CS["accent3"], alpha=0.8, label="Dog covers")
    ax.bar(x + width / 2, fav_rois, width, color=CS["accent"], alpha=0.8, label="Fav covers")
    ax.axhline(0, color=CS["fg"], alpha=0.4, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels([f"+/-{l}" for l in lines_plotted])
    ax.set_xlabel("Handicap Line (games)")
    ax.set_ylabel("ROI (%)")
    ax.set_title("Handicap ROI by Line (>=5% model edge)", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CS["bg"], edgecolor=CS["grid"], labelcolor=CS["fg"])
    for i, (dn, fn) in enumerate(zip(dog_ns, fav_ns)):
        ax.text(i - width / 2, max(0, dog_rois[i]) + 1, f"n={dn}", ha="center", fontsize=7, color=CS["fg"])
        ax.text(i + width / 2, max(0, fav_rois[i]) + 1, f"n={fn}", ha="center", fontsize=7, color=CS["fg"])
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=CS["bg"])
    plt.close(fig)
    print(f"  Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Handicap Backtest from ML Odds")
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--threshold", type=float, default=5, help="Min edge %% to bet")
    parser.add_argument("--limit", type=int, default=None, help="Limit matches (for quick test)")
    parser.add_argument("--out-dir", default="data/diagnostics")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    np.random.seed(42)

    print("\n" + "=" * 72)
    print("  IL MARGINE - Handicap Backtest")
    print("=" * 72)
    print()
    print("  WARNING: This script currently uses ML-odds inversion to synthesise")
    print("  'Pinnacle implied handicap' probabilities. That methodology is FLAWED.")
    print("  K-M inversion is not unique; ROI from it measures inversion-method")
    print("  difference, not real market edge. Use real spread_line/spread_odds")
    print("  from bookmaker_odds_snapshot once 2-3 weeks of data are collected.")
    print()

    all_rows = []
    for p in args.files:
        rows = load_csv(p)
        print(f"  {len(rows):,} rows from {os.path.basename(p)}")
        all_rows.extend(rows)

    if args.limit:
        all_rows = all_rows[: args.limit]
        print(f"  Limited to {len(all_rows):,} rows")

    cm = detect_columns(all_rows)
    print(f"  Prob column: {cm['prob']}")
    print(f"  Pinnacle columns: {cm['pin1']}, {cm['pin2']}")
    print(f"  Score column: {cm['score']}")

    lines = [2.5, 3.5, 4.5, 5.5, 6.5]
    print(f"\n  Running handicap backtest on lines: {lines}")
    print(f"  Edge threshold: >={args.threshold}%")

    results, processed, skipped = run_handicap_backtest(all_rows, cm, lines=lines)
    print(f"\n  Processed: {processed:,}")
    print(f"  Skipped: {skipped}")

    report = []
    report.append("=" * 72)
    report.append("  HANDICAP BACKTEST RESULTS")
    report.append(f"  Matches: {processed:,}, Edge threshold: >={args.threshold}%")
    report.append("=" * 72)

    line_results = {}
    report.append(f"\n  {'Line':>6} {'Side':>6} {'N(qual)':>8} {'ROI':>8} {'WinR':>7} {'AvgEdge':>8} {'AvgOdds':>8} {'PnL':>8}")
    report.append(f"  {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*7} {'-'*8} {'-'*8} {'-'*8}")

    for line in lines:
        dog_analysis = analyse_line(results[line]["bets_dog"], f"Dog +{line}", args.threshold)
        fav_analysis = analyse_line(results[line]["bets_fav"], f"Fav -{line}", args.threshold)
        line_results[line] = {"dog_analysis": dog_analysis, "fav_analysis": fav_analysis}

        for side, analysis in [("Dog", dog_analysis), ("Fav", fav_analysis)]:
            if analysis is None:
                continue
            if analysis.get("insufficient"):
                report.append(f"  +/-{line:>4.1f} {side:>6} {analysis['n_qualifying']:>8} - insufficient data (n<10)")
            else:
                marker = " *" if analysis["roi"] > 0 else ""
                report.append(
                    f"  +/-{line:>4.1f} {side:>6} {analysis['n_qualifying']:>8} "
                    f"{analysis['roi']:>+7.1f}% {analysis['win_rate']:>6.1%} "
                    f"{analysis['avg_edge']:>+7.1f}% {analysis['avg_odds']:>8.2f} "
                    f"{analysis['total_pnl']:>+7.1f}u{marker}"
                )
                print(f"  +/-{line}: {side} n={analysis['n_qualifying']} ROI={analysis['roi']:+.1f}% "
                      f"WR={analysis['win_rate']:.1%} PnL={analysis['total_pnl']:+.1f}u{marker}")

    all_analyses = []
    for line, data in line_results.items():
        for side_key, analysis in [("dog", data.get("dog_analysis")), ("fav", data.get("fav_analysis"))]:
            if analysis and not analysis.get("insufficient") and analysis.get("roi") is not None:
                all_analyses.append((line, side_key, analysis))

    if all_analyses:
        best = max(all_analyses, key=lambda x: x[2]["roi"])
        report.append(f"\n  Best line: +/-{best[0]} {best[1]} - ROI {best[2]['roi']:+.1f}% (n={best[2]['n_qualifying']})")

    report.append(f"\n  -- Comparison to Moneyline --")
    report.append(f"  If any handicap line shows positive ROI where moneyline doesn't,")
    report.append(f"  the serve decomposition model adds value for margin of victory.")
    report.append(f"\n{'='*72}\n")

    report_text = "\n".join(report)
    print(f"\n{report_text}")

    report_path = os.path.join(args.out_dir, "handicap-backtest-report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  Saved: {report_path}")

    if HAS_MPL:
        plot_handicap_roi(line_results, os.path.join(args.out_dir, "handicap-roi-by-line.png"))

    print(f"\n  Done.\n")


if __name__ == "__main__":
    main()
