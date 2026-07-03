#!/usr/bin/env python3
"""Grass lane audit: walk-forward edge investigation over backtest-results-*.csv.

Sections:
  1. Funnel + broad-grass baseline sanity check.
  2. Candidate slice grid (pooled 2022-2025 + per-year + bootstrap CI + tournament dependence).
  3. Walk-forward selection (train 22-23 -> validate 24; train 22-24 -> validate 25).
  4. Grass Platt calibration overlay (fit on train years, re-derive bets on validation).
  5. Model-variant comparison on grass (h2h shrunk, fatigue x1.5, tournament form caps).
  6. Component / serve-dominance / CPI splits.

Conventions match scripts/backtest-policy-profiles.py:
  - skip policy_excluded rows, settle only bet_result in {win, loss}
  - bet odds = pinnacle_odds when bet_side == winner else pinnacle_odds_loser
  - flat 1u staking for ROI; value_pct = bet_prob * bet_odds - 1 (verified).

Usage: python scripts/diag-grass-lane-audit.py
Writes: data/backtest/diag-grass-lane-audit.txt
"""

from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BT = ROOT / "data" / "backtest"
OUT = BT / "diag-grass-lane-audit.txt"
YEARS = [2022, 2023, 2024, 2025]
VARIANTS = {
    "baseline": "backtest-results-{y}.csv",
    "h2h_n2_shrunk": "backtest-results-{y}-h2h-n2-shrunk.csv",
    "fatigue_x1.5": "backtest-results-{y}-fatigue-x1.5.csv",
    "form_caps_up": "backtest-results-{y}-tournament-form-caps-up.csv",
}
SPEED_CSV = BT / "tennisabstract-atp-surface-speed.csv"

EARLY_ROUNDS = {"1st Round", "2nd Round"}
LATE_ROUNDS = {"3rd Round", "4th Round", "Quarterfinals", "Semifinals", "The Final"}

random.seed(17)
lines: list[str] = []


def emit(text: str = "") -> None:
    lines.append(text)
    print(text)


def fnum(value: str | None) -> float | None:
    try:
        v = float(value or "")
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def load_grass(variant: str) -> list[dict]:
    rows = []
    for y in YEARS:
        path = BT / VARIANTS[variant].format(y=y)
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("surface") != "Grass":
                    continue
                r["year"] = y
                p1_won = (r.get("actual_winner") or "").strip() == (r.get("player1") or "").strip()
                bet_won = r.get("bet_side") == "winner"
                r["bet_is_p1"] = p1_won == bet_won
                r["p1_won"] = p1_won
                rows.append(r)
    return rows


def enrich(r: dict) -> dict | None:
    """Return a settled-bet record or None if not a usable settled bet."""
    if str(r.get("policy_excluded")).strip().lower() in {"true", "1", "yes"}:
        return None
    if r.get("bet_result") not in {"win", "loss"}:
        return None
    win_odds = fnum(r.get("pinnacle_odds"))
    lose_odds = fnum(r.get("pinnacle_odds_loser"))
    if not win_odds or not lose_odds or win_odds <= 1.0 or lose_odds <= 1.0:
        return None
    bet_odds = win_odds if r["bet_side"] == "winner" else lose_odds
    other_odds = lose_odds if r["bet_side"] == "winner" else win_odds
    our_p1 = fnum(r.get("our_prob"))
    if our_p1 is None:
        return None
    bet_prob = our_p1 if r["bet_is_p1"] else 1.0 - our_p1
    psr = fnum(r.get("p_serve_return"))
    pelo = fnum(r.get("p_elo"))
    bet_psr = psr if r["bet_is_p1"] else (1.0 - psr if psr is not None else None)
    bet_pelo = pelo if r["bet_is_p1"] else (1.0 - pelo if pelo is not None else None)
    won = r["bet_result"] == "win"
    bet_player = r.get("player1") if r["bet_is_p1"] else r.get("player2")
    market_fav_is_bet = bet_odds < other_odds
    model_fav = (r.get("model_favorite") or "").strip()
    market_fav = (bet_player or "").strip() if market_fav_is_bet else (
        (r.get("player2") if r["bet_is_p1"] else r.get("player1")) or ""
    ).strip()
    return {
        "year": r["year"],
        "tournament": r.get("tournament") or "",
        "round": r.get("round") or "",
        "series": r.get("series") or "",
        "confidence": (r.get("confidence") or "").strip().lower(),
        "value_pct": fnum(r.get("value_pct")) or 0.0,
        "bet_odds": bet_odds,
        "bet_prob": bet_prob,
        "bet_psr": bet_psr,
        "bet_pelo": bet_pelo,
        "won": won,
        "pnl": (bet_odds - 1.0) if won else -1.0,
        "bet_on_market_fav": market_fav_is_bet,
        "model_market_fav_agree": bool(model_fav) and model_fav == market_fav,
        "is_slam": (r.get("series") or "") == "Grand Slam",
        "early": (r.get("round") or "") in EARLY_ROUNDS,
    }


def metrics(bets: list[dict]) -> dict:
    n = len(bets)
    if n == 0:
        return {"n": 0}
    pnl = sum(b["pnl"] for b in bets)
    by_year = defaultdict(lambda: [0, 0.0])
    by_tourn = defaultdict(lambda: [0, 0.0])
    for b in bets:
        by_year[b["year"]][0] += 1
        by_year[b["year"]][1] += b["pnl"]
        by_tourn[b["tournament"]][0] += 1
        by_tourn[b["tournament"]][1] += b["pnl"]
    pos_years = sum(1 for _, (yn, yp) in by_year.items() if yn > 0 and yp > 0)
    # bootstrap CI of flat ROI
    pnls = [b["pnl"] for b in bets]
    sims = []
    for _ in range(5000):
        sims.append(sum(random.choice(pnls) for _ in range(n)) / n)
    sims.sort()
    lo, hi = sims[int(0.025 * len(sims))], sims[int(0.975 * len(sims))]
    p_neg = sum(1 for s in sims if s <= 0) / len(sims)
    top_t = max(by_tourn.items(), key=lambda kv: kv[1][1]) if by_tourn else ("", [0, 0.0])
    return {
        "n": n,
        "roi": pnl / n,
        "pnl": pnl,
        "wr": sum(1 for b in bets if b["won"]) / n,
        "by_year": dict(by_year),
        "pos_years": pos_years,
        "yrs_with_bets": sum(1 for _, (yn, _) in by_year.items() if yn > 0),
        "ci": (lo, hi),
        "p_roi_le_0": p_neg,
        "by_tourn": dict(by_tourn),
        "top_tourn": top_t,
    }


def fmt_slice(name: str, m: dict, detail: bool = False) -> None:
    if m["n"] == 0:
        emit(f"  {name:<58} n=0")
        return
    yr = " ".join(
        f"{y}:{v[1]:+.1f}u/{v[0]}" for y, v in sorted(m["by_year"].items())
    )
    emit(
        f"  {name:<58} n={m['n']:<4} ROI={m['roi']*100:+6.1f}%  WR={m['wr']*100:4.1f}%  "
        f"CI=[{m['ci'][0]*100:+.1f}%,{m['ci'][1]*100:+.1f}%]  P(<=0)={m['p_roi_le_0']:.2f}  "
        f"posYrs={m['pos_years']}/{m['yrs_with_bets']}"
    )
    emit(f"  {'':<58} years: {yr}")
    if detail:
        for t, (tn, tp) in sorted(m["by_tourn"].items(), key=lambda kv: -kv[1][1]):
            emit(f"  {'':<58}   {t}: n={tn} P/L={tp:+.1f}u")


# ---------- candidate slice definitions ----------

def s_th(th):
    return lambda b: b["value_pct"] >= th


def s_and(*fs):
    return lambda b: all(f(b) for f in fs)


HM = lambda b: b["confidence"] in {"high", "medium"}
A500 = lambda b: b["series"] == "ATP500"
A250 = lambda b: b["series"] == "ATP250"
SLAM = lambda b: b["is_slam"]
WARMUP = lambda b: not b["is_slam"]
FAV = lambda b: b["bet_on_market_fav"]
DOG = lambda b: not b["bet_on_market_fav"]
AGREE = lambda b: b["model_market_fav_agree"]
EARLY = lambda b: b["early"]
LATE = lambda b: not b["early"]

SLICES: list[tuple[str, object]] = [
    ("broad grass @10", s_th(10)),
    ("broad grass @15", s_th(15)),
    ("broad grass @20", s_th(20)),
    ("broad grass @10 hi+med", s_and(s_th(10), HM)),
    ("ATP500 hi+med @10  [volume_200 slice]", s_and(A500, HM, s_th(10))),
    ("ATP500 hi+med @15", s_and(A500, HM, s_th(15))),
    ("ATP500 hi+med @10 value<25 (overclaim cap)", s_and(A500, HM, s_th(10), lambda b: b["value_pct"] < 25)),
    ("ATP500 hi+med @10 fav only", s_and(A500, HM, s_th(10), FAV)),
    ("ATP500 hi+med @10 dog only", s_and(A500, HM, s_th(10), DOG)),
    ("ATP500 hi+med @10 model=market fav agree", s_and(A500, HM, s_th(10), AGREE)),
    ("ATP500 hi+med @10 agree+fav", s_and(A500, HM, s_th(10), AGREE, FAV)),
    ("ATP500 hi+med @10 early rounds", s_and(A500, HM, s_th(10), EARLY)),
    ("ATP500 hi+med @10 late rounds", s_and(A500, HM, s_th(10), LATE)),
    ("ATP250 hi+med @10", s_and(A250, HM, s_th(10))),
    ("ATP250 hi+med @20", s_and(A250, HM, s_th(20))),
    ("Slam (Wimbledon) hi+med @10", s_and(SLAM, HM, s_th(10))),
    ("Slam hi+med @10 fav only", s_and(SLAM, HM, s_th(10), FAV)),
    ("Slam hi+med @10 early rounds", s_and(SLAM, HM, s_th(10), EARLY)),
    ("Slam hi+med @10 late rounds", s_and(SLAM, HM, s_th(10), LATE)),
    ("warmups (bo3) hi+med @10", s_and(WARMUP, HM, s_th(10))),
    ("warmups hi+med @10 fav only", s_and(WARMUP, HM, s_th(10), FAV)),
    ("warmups hi+med @10 agree", s_and(WARMUP, HM, s_th(10), AGREE)),
    ("broad @10 fav only", s_and(s_th(10), FAV)),
    ("broad @10 dog only", s_and(s_th(10), DOG)),
    ("broad @10 bet odds<1.6", s_and(s_th(10), lambda b: b["bet_odds"] < 1.6)),
    ("broad @10 bet odds 1.6-2.2", s_and(s_th(10), lambda b: 1.6 <= b["bet_odds"] <= 2.2)),
    ("broad @10 bet odds>2.2", s_and(s_th(10), lambda b: b["bet_odds"] > 2.2)),
    ("broad @10 serve-model backs bet (psr>=0.58)", s_and(s_th(10), lambda b: (b["bet_psr"] or 0) >= 0.58)),
    ("broad @10 serve-model against bet (psr<0.42)", s_and(s_th(10), lambda b: (b["bet_psr"] or 1) < 0.42)),
    ("broad @10 serve+elo both back bet", s_and(s_th(10), lambda b: (b["bet_psr"] or 0) > 0.5 and (b["bet_pelo"] or 0) > 0.5)),
    ("ATP500 hi+med @10 serve-model backs bet", s_and(A500, HM, s_th(10), lambda b: (b["bet_psr"] or 0) > 0.5)),
]


def main() -> None:
    emit("=" * 100)
    emit("IL MARGINE - GRASS LANE AUDIT (walk-forward, real Pinnacle settle prices)")
    emit("=" * 100)

    raw = load_grass("baseline")
    bets_all = [e for e in (enrich(r) for r in raw) if e]
    emit(f"\nGrass opportunity rows 2022-2025: {len(raw)}")
    emit(f"Settled, policy-included bets (any value): {len(bets_all)}")

    emit("\n--- SECTION 1: candidate slice grid (pooled 2022-2025) ---")
    emit(f"NOTE: {len(SLICES)} slices tested on the same data; treat best-slice ROI as upper bound (selection bias).")
    for name, f in SLICES:
        sel = [b for b in bets_all if f(b)]
        fmt_slice(name, metrics(sel))

    emit("\n--- SECTION 2: tournament dependence for headline slices ---")
    for name in ("ATP500 hi+med @10  [volume_200 slice]", "warmups (bo3) hi+med @10", "broad @10 fav only"):
        f = dict(SLICES)[name]
        emit(f"  [{name}]")
        fmt_slice(name, metrics([b for b in bets_all if f(b)]), detail=True)

    emit("\n--- SECTION 3: walk-forward selection ---")
    emit("Protocol A: select on 2022-2023 (n>=12, trainROI>0) -> validate 2024")
    emit("Protocol B: select on 2022-2024 (n>=20, trainROI>+5%) -> validate 2025")
    for proto, train_years, val_year, n_min, roi_min in (
        ("A", {2022, 2023}, 2024, 12, 0.0),
        ("B", {2022, 2023, 2024}, 2025, 20, 0.05),
    ):
        emit(f"\n  Protocol {proto} (validate {val_year}):")
        emit(f"  {'slice':<58} {'trainN':>6} {'trainROI':>9} {'valN':>5} {'valROI':>8}")
        survivors = 0
        val_pnl_total, val_n_total = 0.0, 0
        for name, f in SLICES:
            tr = [b for b in bets_all if f(b) and b["year"] in train_years]
            if len(tr) < n_min:
                continue
            tr_roi = sum(b["pnl"] for b in tr) / len(tr)
            if tr_roi <= roi_min:
                continue
            va = [b for b in bets_all if f(b) and b["year"] == val_year]
            va_roi = (sum(b["pnl"] for b in va) / len(va)) if va else float("nan")
            survivors += 1
            val_pnl_total += sum(b["pnl"] for b in va)
            val_n_total += len(va)
            emit(f"  {name:<58} {len(tr):>6} {tr_roi*100:>+8.1f}% {len(va):>5} {va_roi*100:>+7.1f}%")
        if survivors:
            emit(f"  -> {survivors} survivors; pooled validation: n={val_n_total} ROI={val_pnl_total/max(val_n_total,1)*100:+.1f}% (overlapping slices double-counted)")
        else:
            emit("  -> no survivors")

    emit("\n--- SECTION 4: grass Platt calibration overlay (match-level) ---")
    run_calibration(raw)

    emit("\n--- SECTION 5: model variants on grass ---")
    base_ll = match_logloss(raw)
    emit(f"  baseline           : match logloss={base_ll:.4f} (n={len(raw)})")
    f500 = dict(SLICES)["ATP500 hi+med @10  [volume_200 slice]"]
    for var in ("h2h_n2_shrunk", "fatigue_x1.5", "form_caps_up"):
        vraw = load_grass(var)
        if not vraw:
            emit(f"  {var:<19}: no files")
            continue
        vll = match_logloss(vraw)
        vbets = [e for e in (enrich(r) for r in vraw) if e]
        m = metrics([b for b in vbets if f500(b)])
        broad = metrics([b for b in vbets if b["value_pct"] >= 10])
        emit(
            f"  {var:<19}: match logloss={vll:.4f} (d={vll-base_ll:+.4f})  "
            f"ATP500@10: n={m['n']} ROI={m.get('roi',0)*100:+.1f}%  broad@10: n={broad['n']} ROI={broad.get('roi',0)*100:+.1f}%"
        )

    emit("\n--- SECTION 6: tournament CPI (tennisabstract) join, warmups @10 ---")
    run_cpi(bets_all)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nSaved: {OUT.relative_to(ROOT)}")


def match_logloss(raw: list[dict]) -> float:
    tot, n = 0.0, 0
    for r in raw:
        p = fnum(r.get("our_prob_raw")) or fnum(r.get("our_prob"))
        if p is None or not (0 < p < 1):
            continue
        y = 1.0 if r["p1_won"] else 0.0
        tot += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        n += 1
    return tot / max(n, 1)


def fit_platt(raw: list[dict], years: set[int]) -> tuple[float, float]:
    """Fit p_cal = sigmoid(a + b*logit(p_raw)) by Newton steps on grass matches.

    The backtest CSVs are winner-first ordered (player1 == actual winner), so
    each match is added in BOTH orientations to avoid leaking the result;
    symmetry forces a ~= 0 and the fit recovers the shrink factor b.
    """
    xs, ys = [], []
    for r in raw:
        if r["year"] not in years:
            continue
        p = fnum(r.get("our_prob_raw")) or fnum(r.get("our_prob"))
        if p is None or not (0.001 < p < 0.999):
            continue
        x = math.log(p / (1 - p))
        xs.append(x)
        ys.append(1.0)
        xs.append(-x)
        ys.append(0.0)
    a, b = 0.0, 1.0
    for _ in range(60):
        ga = gb = 0.0
        haa = hab = hbb = 1e-9
        for x, y in zip(xs, ys):
            z = max(min(a + b * x, 30), -30)
            p = 1 / (1 + math.exp(-z))
            w = p * (1 - p)
            ga += p - y
            gb += (p - y) * x
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        if abs(det) < 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a -= da
        b -= db
        if abs(da) + abs(db) < 1e-10:
            break
    return a, b


def run_calibration(raw: list[dict]) -> None:
    for train_years, val_year in (({2022, 2023}, 2024), ({2022, 2023, 2024}, 2025)):
        a, b = fit_platt(raw, train_years)
        emit(f"\n  Train {sorted(train_years)} -> validate {val_year}: platt a={a:+.4f} b={b:.4f}")
        for th in (10.0, 15.0):
            base_bets, cal_bets = [], []
            for r in raw:
                if r["year"] != val_year:
                    continue
                e = enrich(r)
                p_raw = fnum(r.get("our_prob_raw")) or fnum(r.get("our_prob"))
                if p_raw is None or not (0.001 < p_raw < 0.999):
                    continue
                if str(r.get("policy_excluded")).strip().lower() in {"true", "1", "yes"}:
                    continue
                win_odds, lose_odds = fnum(r.get("pinnacle_odds")), fnum(r.get("pinnacle_odds_loser"))
                if not win_odds or not lose_odds or win_odds <= 1 or lose_odds <= 1:
                    continue
                p1_odds = win_odds if r["p1_won"] else lose_odds
                p2_odds = lose_odds if r["p1_won"] else win_odds
                z = math.log(p_raw / (1 - p_raw))
                p_cal = 1 / (1 + math.exp(-(a + b * z)))
                for (p_base, p_c, odds, won) in (
                    (p_raw, p_cal, p1_odds, r["p1_won"]),
                    (1 - p_raw, 1 - p_cal, p2_odds, not r["p1_won"]),
                ):
                    if 100 * (p_base * odds - 1) >= th:
                        base_bets.append((odds - 1) if won else -1)
                    if 100 * (p_c * odds - 1) >= th:
                        cal_bets.append((odds - 1) if won else -1)
            for label, arr in (("raw  ", base_bets), ("platt", cal_bets)):
                roi = sum(arr) / len(arr) * 100 if arr else float("nan")
                emit(f"    @{th:.0f}% {label}: n={len(arr):<4} ROI={roi:+.1f}%")


def run_cpi(bets_all: list[dict]) -> None:
    cpi: dict[tuple[int, str], float] = {}
    if SPEED_CSV.exists():
        with SPEED_CSV.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("surface") or "") != "Grass":
                    continue
                v = fnum(r.get("cpi"))
                if v is not None:
                    cpi[(int(r["season_year"]), (r.get("tournament_key") or "").lower())] = v
    if not cpi:
        emit("  no grass CPI rows found")
        return
    keymap = {
        "Halle Open": "halle", "Queen's Club Championships": "queen s club", "Stuttgart Open": "stuttgart",
        "Mercedes Cup": "stuttgart", "Eastbourne International": "eastbourne",
        "Rosmalen Grass Court Championships": "s hertogenbosch", "Mallorca Championships": "mallorca",
        "Hall of Fame Championships": "newport", "Wimbledon": "wimbledon",
    }
    emit(f"  grass CPI rows: {len(cpi)}; sample keys: {sorted(set(k for _, k in cpi))}")
    fast, slow, miss = [], [], 0
    vals = sorted(cpi.values())
    median = vals[len(vals) // 2]
    for bnd in [b for b in bets_all if b["value_pct"] >= 10 and not b["is_slam"]]:
        key = (bnd["year"], keymap.get(bnd["tournament"], ""))
        v = cpi.get(key)
        if v is None:
            miss += 1
            continue
        (fast if v >= median else slow).append(bnd)
    emit(f"  median grass CPI={median:.2f}; unmatched bets={miss}")
    fmt_slice(f"warmup @10 fast courts (CPI>={median:.2f})", metrics(fast))
    fmt_slice(f"warmup @10 slow courts (CPI<{median:.2f})", metrics(slow))


if __name__ == "__main__":
    main()
