# Tennis Full-Match Total Games O/U — Forensic Audit & Registered Model Design

Date: 2026-07-28 · Repo: `D:\IlMargine\il-margine` · Working tree: `localhost-golden-sync`
(supersedes `golden-with-speed-insights`, which still has the totals code inline in
`scripts/oncourt-compute-fair-odds.py` before the `src/lib/tennis_prob.py` extraction)

Scope: full-match total games Over/Under only. Not aces/DFs, not first-set totals,
not spreads, not a general tennis model review.

---

## 1. Executive verdict

**Do not proceed to a totals betting lane. Fix the display defects, keep the lane as a
calibration diagnostic only.**

Three separable conclusions:

1. **The current displayed O/U prices are materially wrong for best-of-five, and mildly
   miscalibrated for best-of-three.** For Grand Slam matches the published board is
   self-contradictory on its face: the page shows an expected total of ~39 games next to
   an O/U board of 22.5 / 23.5 / 24.5. 426 of 428 captured Slam matches had a Pinnacle
   line above the highest line our board can even emit. This should be hidden immediately.

2. **There is no edge.** Against 7,673 real settled matches priced at real captured
   Pinnacle prices, every candidate model — including a fully corrected structural engine
   fed the *de-vigged Pinnacle moneyline* as its win probability, which is a better ML
   input than our own — scores **worse than a constant 0.5**. Real-price ROI is negative in
   every window, every segment, at every edge threshold. Mean CLV is ~0. Zero of eleven
   league × surface × line-bucket cells with n ≥ 100 has a bootstrap CI excluding zero
   (chance alone would give ~0.6).

3. **The blocker is not sample size — it is that Pinnacle's totals line is at the noise
   floor.** Market Brier at its own line is 0.24982 against a 0.24997 constant-0.5
   baseline. The line is so well-centred that it carries almost no information beyond
   "coin flip", which is exactly what an unbeatable line looks like. Total games has an
   irreducible sd of ~7.2 games; the market's own MAE (5.06) is close to that floor.

Secondary but important: the registered experiment `tennis-serve-derivatives-0.1` lane
`total_games_shape` currently reports `BLOCKED_NO_REGISTERED_REAL_LINE_DATASET` with
"Scored real paired line rows: 0 / 600". That is a **tooling artifact, not reality** —
`scripts/tennis-derivatives-pinnacle-coverage.py` reads a Supabase window starting
`2026-07-12` and ignores 147 daily CSVs and 2,716 history snapshots going back to
2026-03-01. The real figure is 7,673 — the 600-row gate has been passed 12× over since
roughly April. It was passed, scored, and **failed on merit**.

---

## 2. Confirmed defects (file:line)

| # | Hypothesis | Verdict | Materiality |
|---|---|---|---|
| 1 | Tournament shift inconsistency | **CONFIRMED** | Up to 1.5 games |
| 2 | Integer-line push handling | **CONFIRMED (latent)** | 7–12% on Under price |
| 3 | Serving-order propagation | **CONFIRMED but immaterial** | ≤0.06 games |
| 4 | Best-of-five | **CONFIRMED — critical** | 15-game display error |
| 5 | Loss of matchup information | **CONFIRMED — structural** | up to 4.3 games |
| 6 | Ad-hoc line shifts | **CONFIRMED — unfitted constants** | ±2.6 games |

### Defect 1 — tournament residual applied to E[G] but not to the O/U distribution
`scripts/oncourt-compute-fair-odds.py:3656-3658` adds
`clamp(TOURNAMENT_TOTAL_WEIGHT * tour_shift, ±1.5)` to `exp_games`.
`scripts/oncourt-compute-fair-odds.py:3679` prices with
`prob_over_games(p_a_eg, p_b_eg, line + ou_shift)` — no `tour_shift` term.
The displayed `expected_total_games` and the displayed fair O/U prices therefore describe
distributions whose means differ by the capped tournament term, up to **1.50 games**.

### Defect 2 — integer lines: `1 - P(over)` is not `P(under)`
`scripts/oncourt-compute-fair-odds.py:3686-3687`:
```python
fair_over  = round(1.0 / p_over, 3)
fair_under = round(1.0 / (1.0 - p_over), 3)
```
`prob_over_games()` (`src/lib/tennis_prob.py:452-456`) returns `P(total > line)`, so
`1 - P(over) = P(under) + P(push)`.

**Correct derivation.** With win = `total > line`, push = `total == line`, loss =
`total < line`, a unit stake at decimal odds `O` has
`EV = P_o(O-1) + P_p·0 - P_u`. Setting EV = 0:

```
fair_over  = (P_o + P_u) / P_o
fair_under = (P_o + P_u) / P_u
```

Equivalently `1/fair_over = P(over | no push)` and `1/fair_over + 1/fair_under = 1`
exactly. Measured error at `p_a=0.66, p_b=0.62`: line 22.0 → Under should be 2.701,
current code emits 2.364 (**−12.5%**); line 23.0 → 2.212 vs 2.052 (**−7.2%**).

**Materiality nuance (important).** `STANDARD_OU_LINES` (`:115`) is all half-integers and
`ou_shift` is generally fractional, so the *current display path* almost never hits an
integer threshold — the only exception is the bare `"N/A"` surface fallback
(`ou_shift = 2.5`, giving `18.5 + 2.5 = 21.0`). So this defect is **latent today**. It
becomes first-order the moment we price against Pinnacle's real lines: **47.6% of the
7,673 captured lines are integers**, and 6.7% of integer-line bets actually pushed.

### Defect 3 — serving order across sets: real, immaterial
`src/lib/tennis_prob.py:399-449` (`_match_games_pmf`) sets `s3w, s3l = s1w, s1l`, assuming
set 3's first server equals set 1's. The correct rule: service alternates continuously, so
the next set's first server flips **iff the completed set had an odd number of games**
(a tiebreak counts as one game, i.e. 7-6 = 13 = odd → flip, which is self-consistent).
Set totals 6, 8, 10, 12 are even; 7, 9, 13 are odd — so the assumption is wrong roughly
half the time. `expected_total_games_best_of_3` (`:149-157`) inherits the same assumption.

Within-set alternation (`:390`) and tiebreak serving (`:19-21`) are **correct**.

Measured impact of the fix (plus averaging over the unknown first server, which
`expected_match_service_points` at `:339-349` already does but the PMF does not):
E[G] changes by −0.015 to +0.062 games; P(over 21.5) changes by ≤0.0003. **Real bug,
lowest priority.**

### Defect 4 — best-of-five priced from the best-of-three PMF (critical)
`is_best_of_5` is computed correctly at `:2837` and used at `:3645` (ML solve) and `:3651`
(expected total). It is **not** passed to `prob_over_games` at `:3679`, which has no
`best_of` parameter at all (`src/lib/tennis_prob.py:452`) and calls the hardcoded
best-of-three `_match_games_pmf`.

Two distinct failure modes, both real:

- **Display path.** The board picks three lines from `STANDARD_OU_LINES` (18.5–27.5) by
  where the BO3 P(over) crosses 50%. Simulated Slam match (Pinnacle line 38.0):
  page shows `expected_total_games = 39.1` beside a board of **22.5 / 23.5 / 24.5**.
  In the captured data **426 of 428 (99.5%)** BO5 matches had a Pinnacle line above 27.5 —
  entirely off our board.
- **Any market-comparison path.** Scored at Pinnacle's real line, the BO3 PMF has zero
  mass above 39 games, so P(over) collapses and is clamped to 0.01 by `:3680`. **81.2%
  of BO5 rows hit that clamp.** 100% of Model A's 404 sub-0.10 predictions are BO5;
  their actual over rate was **51.5%**. That is a published fair "Under @ 1.02" on a
  coin flip.

### Defect 5 — matchup information discarded (largest structural gap)
`scripts/oncourt-compute-fair-odds.py:3646` calls `_solve_spw_for_match_prob` (`:429-458`),
which binary-searches a **symmetric** pair `p_a = avg + δ, p_b = avg − δ` to reproduce one
number: the final ML probability. The real matchup serve/return estimates
(`hold1_eff`, `ret1_eff`, `hold2_eff`, `ret2_eff`, computed at `:2951-2999`) feed only
`p_serve_return` as one ML blend component and are **discarded for totals**.

Two matches with identical ML probability get identical totals pricing. Measured at
ML = 0.65: a serve-dominant matchup (centre 0.74) gives E[G] = 28.32 and P(over 21.5) =
0.873; a return-dominant matchup (centre 0.55) gives 24.04 and 0.601. That is **4.3 games
and 27 percentage points** collapsed to a single number.

### Defect 6 — the ad-hoc shifts
`scripts/oncourt-compute-fair-odds.py:118-120`:
```python
OU_LINE_SHIFT_BY_SURFACE = {"Hard": 2.6, "Clay": 2.9, "Grass": 1.8, "I.hard": 2.4, "N/A": 2.5}
OU_CHALLENGER_EXTRA_SHIFT = 0.35
OU_ATP_MAIN_TOUR_EXTRA_SHIFT = -0.15
```
No fitting provenance in the repo (comment says only "model has been running high"). No
holdout evidence. Effect is large: at `p_a=0.64, p_b=0.62`, a +2.6 shift moves
P(over 21.5) from 0.676 to 0.521 — a coin flip becomes a heavy Under lean.

**Root cause the shift is papering over.** `SURFACE_LEAGUE_AVG` (`:158`) uses
Hard 0.64 / Clay 0.62 / Grass 0.67. Recomputed from 237,334 OnCourt match-player stat rows
since 2025-01-01, the empirical serve-point-win rate is **Hard 0.5802 / Clay 0.5671 /
Grass 0.6269** — the production constants are ~0.04–0.06 too high across the board, which
inflates hold rates and lengthens matches. That is the +1.8-game raw bias. Correcting the
centre (candidate C2) cuts bias from +1.798 to +0.933 and Brier from 0.27157 to 0.26040 —
a genuine improvement from correctness, and still far short of the market.

No leakage was found in these constants (they are fixed, not fitted per-season), but they
are also not fitted to anything documented. Double counting **is** present in spirit:
`ou_shift`, `tour_shift`, venue SPW and the CPI ratio all adjust the same pace dimension,
with only the CPI/venue pair explicitly blended (`:3632-3637`).

---

## 3. Recomputed data inventory

Built from `data/pinnacle-odds-*.csv` (147 files), `data/pinnacle-history/*.csv`
(2,716 files) and OnCourt `games_*.csv` / `stat_*.csv` / `tours_*.csv` / `players_*.csv`.
Joins are player-ID based via exact name resolution against OnCourt; ambiguous names are
rejected, never fabricated.

**1. Historical score rows for count calibration.** 2,021,007 OnCourt match rows
(1,208,889 ATP + 812,120 WTA) with parsed set scores. Format is clean
(`"6-2 6-1"`, `7-6(4)`, `... ret.`).
*Note:* these files are winner-first (`winner_id, loser_id`), but **total games is
invariant to that ordering**, so unlike match-level fits this dataset carries no
winner-first leak. See memory `backtest-csv-winner-first`.

**2–3. Real Pinnacle total snapshots.** 5,197 complete daily O/U rows
(line + over + under) across 146 days, 2026-03-01 → 2026-07-28; plus **92,159** complete
history snapshot rows over 8,126 distinct match offers.

**4. Opening / close.** 6,159 offers carry a `close` capture; 4,734 carry both a
pre-close and a close snapshot. Capture modes: `close` 82,977, `daily` 8,881,
`weekly` 301. Line moved pub→close in 15.8% of close-covered matches
(±0.5 in 711 cases); price unchanged in 56.9% of same-line pairs.

**5. Settled and joinable.** **7,673 matches** joined to a real total-games result.
Join outcomes from 8,856 offers: joined 7,673 (86.6%), name not found 585 (6.6%),
no result row 225 (2.5%), **retired 224 (2.5%, correctly excluded)**, no date match
149 (1.7%), ambiguous 0.

**6. Tour coverage.** Challenger 5,002 (65.2%), ATP 2,671 (34.8%).
**WTA totals coverage is zero** — the Pinnacle tennis scrape captures no WTA O/U at all.
The "WTA separately" segment cannot be populated.

**7. BO3 / BO5.** BO3 7,245 (94.4%), BO5 428 (5.6%).

**8. Segments.** Surface: Clay 5,132 / Hard 1,706 / Grass 787 / I.hard 48.
Line buckets: <19 323, 19–20.5 1,157, 21–22.5 5,012, 23–24.5 710, 25–29.5 58,
30+ (BO5) 413. Tier: 1 (Challenger) 5,002, 2 928, 3 1,029, 4 714.
**47.6% of lines are integers.**

**9. Hygiene.** Retirements excluded (224). Walkovers produce no score row and drop out.
Slam *qualifying* is BO3 but shares the Pinnacle `league_name` of the main draw
(197 French Open + 89 Wimbledon BO3 rows) — a pre-match BO5 flag from tournament name
alone would misclassify these; round/draw information is required.

**Market properties.** Pinnacle totals hold: mean 4.26% (median 4.28%).
Outcomes vs line: Over 48.9% / Under 47.9% / **Push 3.2%** (6.7% of integer-line bets).
Actual totals: mean 23.92, median 22, sd 7.18 (BO3 mean 23.06, BO5 mean 38.35).

> **Mean-vs-median trap.** `mean(actual − line) = +1.543` looks like market bias but is
> pure right-skew: the market prices the **median**, our `expected_total_games` is the
> **mean**, and the gap is ~1.5 games. Any future comparison must compare like with like.

---

## 4–5. Candidate comparison and walk-forward

All candidates are fed the **de-vigged Pinnacle moneyline** as their match-win
probability. This removes our ML engine as a confound and is the most favourable possible
input for the incumbent.

- **A** — current engine exactly as coded (BO-correct ML solve, BO3-only PMF, `ou_shift`)
- **A0** — A with no `ou_shift`
- **B** — corrected structural engine (right BO, parity-correct serving, push mass,
  first-server averaging), production SPW centre
- **C2** — B recentred on the empirical surface SPW
- **C** — B with strictly past-only matchup serve/return (365-day window, surface blend,
  shrinkage `k = 900` service points), `p_a = spw_A + rpw_B − r̄`
- **D** — market-anchored residual

### Expected-total accuracy (n = 7,673; actual mean 23.92)

| model | MAE | RMSE | bias |
|---|---|---|---|
| Pinnacle line (market median) | **5.063** | 6.322 | −1.543 |
| A current (calibrated E[G]) | 5.118 | **6.280** | −1.125 |
| B corrected, production SPW | 5.603 | 6.426 | +1.798 |
| C2 corrected, empirical SPW | 5.403 | 6.239 | +0.933 |
| C matchup serve/return | 5.544 | 6.468 | +0.962 |

### Probability at the real Pinnacle line (n = 7,427 non-push)

| model | Brier | LogLoss | mean p |
|---|---|---|---|
| **Market (de-vigged Pinnacle)** | **0.24982** | **0.69278** | 0.4996 |
| constant p = base rate (0.5052) | 0.24997 | 0.69309 | — |
| A current | 0.26538 | 0.78255 | 0.4631 |
| A0 current, no shift | 0.27896 | 0.80428 | 0.5846 |
| B corrected, production SPW | 0.27157 | 0.74093 | 0.6395 |
| C2 corrected, empirical SPW | 0.26040 | 0.71526 | 0.5929 |
| C matchup serve/return | 0.27249 | 0.74750 | 0.5868 |

**Every model is worse than a constant.** Adding real matchup data (C) made it *worse*,
not better.

### Calibration

Market is flat (all mass in 0.4–0.6, gaps +0.003 to +0.008). Model B is grossly
overconfident: predicts 0.650 in its largest bin (n=4,791) against 0.508 actual (−0.141);
predicts 0.841 against 0.397 (−0.444). Model A shows the BO5 signature: 404 predictions at
mean 0.015 against **0.515 actual** (+0.500) — all 404 are BO5.

### D — does anything add information beyond the price?

Logistic on `logit(p_market)` + `logit(p_model)`:

| model | w_market | w_model |
|---|---|---|
| A | +0.0370 | **−0.0079** |
| B | +0.0375 | **−0.0377** |
| C2 | +0.0373 | **−0.0327** |
| C | +0.0342 | **−0.0580** |

Every model weight is **negative**. Correlation between model-vs-market E[G]
disagreement and the over outcome: −0.0129 to +0.0004. Zero information, wrong sign.

At 2–5 games of disagreement the structural model says "Over" in **99%+** of cases and the
actual over rate is 0.509 — the disagreement is systematic bias, not signal.

### Real-price ROI at publication odds (pushes returned)

| model | edge ≥0% | ≥5% | ≥10% | ≥20% |
|---|---|---|---|---|
| A current | −4.25% | −6.19% | −7.91% | −9.31% |
| B corrected | −2.99% | −2.94% | −3.40% | −2.58% |
| C2 best structural | −3.26% | −3.84% | −2.46% | −4.05% |
| C matchup | −4.21% | −4.72% | −4.60% | −5.47% |

C2 at edge ≥5%: n = 6,676, ROI **−3.84%**, bootstrap CI95 [−6.12, −1.74], max DD −261u.

### Walk-forward (structural models; no refitting)

| window | n matches | A current (edge ≥5%) | C2 (edge ≥5%) |
|---|---|---|---|
| TRAIN Mar–May | 5,217 | −5.74% (n=1,035) | −3.25% (n=4,536) |
| VALID June | 1,439 | −3.50% (n=339) | −1.46% (n=1,246) |
| **HOLDOUT July** | 1,017 | **−12.81%** (n=207) | **−10.16%** (n=894) |

Negative in every window; worst in the untouched holdout.

### CLV

Mean CLV −0.086%, median exactly 0.000%. Of 8,974 same-line pub→close price pairs,
**56.9% are exactly unchanged**; among those that moved, 38.3% moved in our favour and
61.7% against. The headline "positive CLV share 17%" in the raw run is deflated by the
zero-movement mass — the honest reading is **~0 CLV, slightly negative**, against a
registered gate of +1.0% mean and 55% positive share.

---

## 6. Segments (candidate C2, edge ≥5%, bootstrap CI95)

| segment | n | ROI | CI95 | CLV |
|---|---|---|---|---|
| ATP | 1,901 | −7.36% | [−11.57, −3.03] | −0.02% |
| Challenger | 4,775 | −2.44% | [−5.18, +0.20] | −0.10% |
| BO3 | 6,321 | −4.04% | [−6.44, −1.74] | −0.08% |
| BO5 | 355 | −0.20% | [−9.68, +9.26] | −0.03% |
| Clay | 4,607 | −3.77% | [−6.58, −1.08] | −0.09% |
| Hard | 1,437 | −2.62% | [−7.43, +2.34] | −0.07% |
| Grass | 593 | −8.22% | [−15.62, −0.57] | +0.00% |
| I.hard | 39 | +9.02% | [−21.65, +38.72] | — ⚠ n<100 |
| line <19 | 315 | −11.32% | [−21.75, −1.31] | −0.64% |
| line 19–20.5 | 1,107 | −6.80% | [−12.46, −1.06] | −0.12% |
| line 21–22.5 | 4,569 | −3.08% | [−5.95, −0.33] | −0.05% |
| line 23–24.5 | 315 | −0.21% | [−10.44, +9.77] | +0.15% |
| line 25–30.5 | 39 | +14.26% | [−15.59, +44.81] | ⚠ n<100 |
| line 31+ | 331 | −2.84% | [−13.17, +6.79] | +0.01% |
| OVER | 6,646 | −3.77% | [−6.07, −1.47] | −0.08% |
| UNDER | 30 | −18.86% | [−53.40, +15.78] | ⚠ n<100 |
| fav 0.5–0.6 | 2,322 | −3.20% | [−7.05, +0.70] | −0.02% |
| fav 0.6–0.7 | 2,090 | −1.55% | [−5.97, +2.27] | −0.02% |
| fav 0.7–0.8 | 1,332 | −4.21% | [−9.33, +1.04] | −0.07% |
| fav 0.8–0.9 | 671 | −13.22% | [−19.89, −5.96] | −0.19% |
| fav 0.9–1.0 | 261 | −1.88% | [−12.56, +9.31] | −0.98% |
| integer line | 3,210 | −2.82% | [−6.01, +0.34] | −0.07% |
| half line | 3,466 | −4.78% | [−7.70, −1.47] | −0.08% |
| tier 1 (Challenger) | 4,775 | −2.44% | [−5.23, +0.30] | −0.10% |
| tier 2 | 647 | −6.56% | [−13.74, +0.43] | −0.03% |
| tier 3 | 662 | −13.52% | [−20.51, −6.17] | −0.00% |
| tier 4 | 592 | −1.35% | [−8.88, +6.06] | −0.02% |

The model takes OVER on 6,646 of 6,676 selections — it is a one-sided bias, not a
selective model.

**Multiple-comparisons control.** Across 11 league × surface × line-bucket cells with
n ≥ 100 bets, **0 have a CI95 lower bound above zero**; chance alone predicts ~0.6. Best
cell (Challenger / Hard / 21–23) is +0.76% with CI [−5.20, +6.79] — indistinguishable
from noise. Worst is ATP / Grass / 21–23 at −25.37%.

**Player-sample depth does not rescue candidate C.** Brier by minimum service points of
the two players: <1,500 → 0.34039; 1,500–3,000 → 0.27657; 3,000–6,000 → 0.26876;
6,000–12,000 → 0.26878. Market is 0.2496–0.2502 in every bucket. More data does not close
the gap.

**The most defensible possible lane** (ATP main tour, BO3, both players ≥3,000 service
points, n = 2,021): market Brier 0.24949; A 0.25088; C2 0.25518; C 0.26517; constant
0.25000. ROI: C −3.75% [−8.71, +1.05], C2 −9.01% [−14.09, −4.17]. **No narrow ATP range
survives.**

---

## 7. Recommended policy: **DO NOT PROCEED**

No shadow staking policy is proposed. Forcing one would violate the audit's own rule
("Do not force a policy if the historical calibration fails") and the registered
experiment's `forbidden` list.

The historical calibration has already failed on a sample **12× larger than the
pre-registered gate**, on real prices, with a clean untouched holdout. This is not a
"needs more data" outcome — it is a completed, adequately powered negative result. Running
a prospective shadow window would burn ~3 months to re-derive an answer we already have at
n = 7,427.

Totals are retained as a **diagnostic**, not a lane: the corrected PMF is a legitimate
consistency check on the ML/spread layer, and the empirical-SPW recentring is a real
improvement worth landing regardless.

**The one condition that would reopen this.** Not more of the same data — a genuinely new
information source that the market plausibly lacks or prices slowly: verified pre-match
injury/withdrawal status, confirmed court-speed telemetry, or same-day weather at outdoor
venues. Absent that, totals stay closed.

---

## 8. Implementation plan (ranked)

### P0 — correctness and safety (do these regardless of the lane decision)

1. **Hide the O/U board for best-of-five.**
   `scripts/oncourt-compute-fair-odds.py:3676` — change the guard from
   `if confidence != "none":` to `if confidence != "none" and not is_best_of_5:` so
   `ou_data` stays empty for Slams. Then in `src/app/fair-odds/page.tsx` render "—" when
   `ou_line_*` is absent (the API at `route.ts:3181-3183` already emits `undefined`).
   *Ship this first — it is a visible, self-contradictory public display.*

2. **Add `best_of` to the PMF and fix serving-order propagation.**
   `src/lib/tennis_prob.py` — replace `_match_games_pmf` with a general
   `match_games_pmf(p_a, p_b, best_of=3, average_first_server=True)` that carries
   `(sets_a, sets_b, next_first_server)` state, where the next set's first server flips
   iff the completed set had an odd number of games. Reference implementation:
   `tmp/totals_audit/engine.py`.
   Change `prob_over_games(p_a, p_b, line)` →
   `over_push_under(p_a, p_b, line, best_of)` returning `(P_over, P_push, P_under)`.

3. **Correct push-aware fair prices.**
   `scripts/oncourt-compute-fair-odds.py:3686-3687` →
   `fair_over = (P_o + P_u)/P_o`, `fair_under = (P_o + P_u)/P_u`.
   Assert `abs(1/fair_over + 1/fair_under - 1) < 1e-9`.

4. **Make the tournament shift consistent.**
   Apply the capped `tour_shift` to the same object as `ou_shift` — i.e. fold it into the
   threshold used at `:3679` — so `expected_total_games` and the O/U board describe one
   distribution. Add a regression assert that the board's implied median is within 0.5
   games of the displayed expected total after skew correction.

5. **Recentre SPW on empirical values.**
   `scripts/oncourt-compute-fair-odds.py:158` — `SURFACE_LEAGUE_AVG` →
   Hard 0.580 / Clay 0.567 / Grass 0.627 / I.hard 0.602 / N/A 0.579, and verify the
   Supabase `surface_league_averages` table agrees. Then **re-derive `OU_LINE_SHIFT_*`
   from scratch** — most of the current 2.5–2.9 exists only to cancel the wrong centre.
   Do not tune it on the evaluation sample.

6. **Label the displayed quantity.** The board's median line and
   `expected_total_games` are different statistics (median vs mean, ~1.5 games apart on a
   right-skewed distribution). Either display the model **median** next to the board, or
   label the field "expected (mean)" explicitly.

### P1 — reporting truthfulness

7. **Fix the coverage script.** `scripts/tennis-derivatives-pinnacle-coverage.py:157` —
   `--start-date` defaults to `2026-07-12`, so the evidence ledger reports 0 usable totals
   rows when 7,673 exist. Default it to the earliest capture date and add the local
   `data/pinnacle-odds-*.csv` + `data/pinnacle-history/*.csv` sources alongside the
   Supabase read.

8. **Record the negative result.** Update
   `data/vnext/tennis-derivatives-evidence-report.txt` and
   `data/vnext/experiment-registration-derivatives-0.1.json` to mark
   `total_games_shape` as **`TESTED_AND_REJECTED`** (n = 7,427 settled, ROI −3.84%
   CI95 [−6.12, −1.74], mean CLV −0.086%, market Brier 0.24982 vs best model 0.26040) —
   not `BLOCKED`. Preserve the existing file history; append, do not rewrite.

### P2 — only if the lane is ever reopened

9. Ledgers `data/backtest/strict-signals-totals_shadow-live.csv` +
   `-archive.csv`, matching the `spreadv1` column contract, with
   `bet_type=TOTAL`, `ou_line`, `side ∈ {OVER,UNDER}`, and `settlement_status ∈
   {pending,won,lost,push,void}`.
10. Settlement in `scripts/settle-strict-signals.py` keyed on
    `(match_date, player1_id, player2_id, ou_line, side)`, idempotent, pushes → stake
    returned, retirements → void (matching Pinnacle's rule), walkovers → void.
11. Digest lane in `scripts/tennis-daily-signal-digest.py` `LANES` tuple:
    `Lane("TOTALS SHADOW", BACKTEST / "strict-signals-totals_shadow-live.csv",
    "SHADOW / RESEARCH", 40)`.
12. Monitor page `src/app/model-monitor/tennis/` totals panel.

### Tests (P0 scope)

- `prob_game` / `prob_set` sum to 1; PMF sums to 1 for BO3 and BO5.
- BO5 PMF support extends to 65 games; BO3 PMF caps at 39.
- Serving order: for a set ending 6-4 (even) the next set's first server is unchanged;
  6-3 (odd) and 7-6 (13, odd) flip.
- Integer line: `P_over + P_push + P_under == 1`; `1/fair_over + 1/fair_under == 1`.
- Half line: `P_push == 0` and the corrected prices equal the old formula.
- Symmetry: `pmf(p_a, p_b) == pmf(p_b, p_a)` under first-server averaging.
- Slam guard: `is_best_of_5` ⇒ no `ou_line_*` keys emitted.
- Retirement and walkover settle to `void`, never to a win or loss.
- Duplicate prevention: re-running settlement is a no-op.

---

## 9. Acceptance and promotion gates

**Merge gates for the P0 fixes** (these are correctness fixes, not a promotion):

- All P0 tests pass.
- No Slam match emits `ou_line_*`.
- For BO3, the board's median line stays within ±1.0 game of the Pinnacle line on
  ≥80% of a 500-match replay (current baseline: 83.6%).
- STRICT and VOL200 selections are **byte-identical** before and after
  (`ou_*` fields are not read by any ML/spread path — verify with a diff of
  `strict-signals-*-live.csv` on a dry run).

**Reopening gates for a totals lane** — all must hold on data *not* used in this audit:

- A named new information source, registered before collection.
- ≥1,000 settled selections at real captured publication prices.
- Mean CLV ≥ +1.0% with a bootstrap CI95 lower bound > 0.
- Positive-CLV share ≥ 55% among *moved* prices (current: 38.3%).
- Brier beating the de-vigged market on the same matches, on a locked holdout.
- ROI CI95 lower bound > 0 in a walk-forward holdout not used for any threshold choice.
- ATP and Challenger evidenced separately; WTA impossible until O/U capture exists.

---

## 10. What the user will see daily

**Today, and until the P0 fixes ship:** unchanged. Totals are not a lane, produce no
signals, and appear in no Telegram digest. The 28 July run that priced 90 matches, matched
45 to Pinnacle and produced zero signals **stays at zero** — totals were never going to
rescue it, and loosening ML guards to manufacture bets remains the wrong move.

**After the P0 fixes:**

- On Grand Slam matches, the O/U column shows **"—"** instead of a board 15 games away
  from the market. The expected-total figure remains.
- On ordinary ATP/Challenger matches, the three O/U lines look much as they do now (they
  were already within ±1 game of Pinnacle 83.6% of the time), but the Under price is
  correct on integer lines and the expected total no longer silently disagrees with the
  board.
- The model-monitor evidence page stops claiming "0 / 600 rows, BLOCKED" for
  `total_games_shape` and instead records the honest outcome: tested on 7,427 settled
  real-price selections, rejected.
- **No new bets.** No `TOTALS SHADOW` section in Telegram. Nothing is routed anywhere.

The commercial answer in one line: full-match totals cannot create additional legitimate
daily bets at Pinnacle prices, because Pinnacle's totals line sits at the noise floor of a
distribution with sd 7.2 games, and neither structural correctness nor real matchup serve
data moves us closer to it.

---

## Appendix — commercial questions, answered directly

1. **Can totals create additional legitimate daily bets?** No. Negative ROI in every
   window, segment and edge threshold; ~0 CLV.
2. **Does either side beat the market after vig?** No. The models take OVER on 99.6% of
   selections (a bias, not a selection) and OVER returns −3.77%.
3. **Is there a narrow, defensible ATP range?** No. ATP is the *worst* league segment
   (−7.36%); the best-case ATP/BO3/deep-sample lane is −3.75% to −9.01%.
4. **Are totals useful only as an ML/spread diagnostic?** Partly — the corrected PMF is a
   valid consistency check, but disagreement magnitude tracks match *lopsidedness*
   (mean favourite probability rises 0.651 → 0.741 across disagreement bands), not market
   error. Use it as an internal assertion, not a signal.
5. **Is the current fair-odds display materially wrong?** **Yes for BO5** — catastrophically
   and visibly. For BO3 the lines are sensible; the prices are mildly miscalibrated
   (Brier 0.265 vs market 0.250) and the integer-line Under formula is wrong but latent.
6. **Should the displayed O/U prices be hidden until corrected?** **Yes for best-of-five,
   immediately.** BO3 can stay up through the P0 fixes.
7. **What prospective sample is required before totals can become sellable?** None will
   help without a new information source. Given one, see the reopening gates in §9.

---

## Reproduction

Scripts written for this audit (read-only, no production artifacts touched):

```
tmp/totals_audit/build_cache.py     OnCourt games/tours/players -> pickle
tmp/totals_audit/build_market.py    Pinnacle snapshots -> settled join (7,673 rows)
tmp/totals_audit/build_serve.py     past-only serve/return profiles (1,548,418 rows)
tmp/totals_audit/engine.py          corrected PMF, push-aware fair prices
tmp/totals_audit/defects.py         per-defect numerical quantification
tmp/totals_audit/characterise.py    data inventory
tmp/totals_audit/evaluate.py        candidates A/A0/B + market
tmp/totals_audit/candidates_cd.py   candidates C/C2 + residual test
tmp/totals_audit/roi_clv.py         ROI, CLV, walk-forward, segments
tmp/totals_audit/final_checks.py    sample-depth, best-case lane, tails
```

Safety: STRICT and VOL200 untouched; no synthetic prices used for any ROI figure;
ATP/Challenger/WTA never pooled; no thresholds tuned on the reported sample; no existing
append-only record modified; nothing promoted.
