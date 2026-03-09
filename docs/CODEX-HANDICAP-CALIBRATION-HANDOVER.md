# Handicap Calibration — Handover to Codex

**Task:** Calibrate the handicap (game spread) model so that handicap edges are realistic. Currently almost every match shows +20% to +80% edge on P1+, which is implausible — we cannot have value in every match. Pinnacle is a sharp book; systematic large edges indicate miscalibration.

**Deliverables:** Send us the calibrated files (scripts, constants, any new calibration scripts) and a short summary of what you changed. Put modified/new files in the repo and share the paths; we will review and merge.

---

## 1. What We Have Done (Current State)

### 1.1 Handicap Implementation (Phases 1–3 Complete)

| Component | Location | Status |
|-----------|----------|--------|
| **p_a, p_b persistence** | `daily_fair_odds` table | Done. Migration: `docs/supabase-daily-fair-odds-pa-pb.sql` |
| **Handicap columns** | `daily_fair_odds` | Done. Migration: `docs/supabase-daily-fair-odds-handicap.sql` — adds `spread_line`, `spread_odds1`, `spread_odds2`, `handicap_edge_p1`, `handicap_edge_p2` |
| **Pinnacle spread scrape** | `scripts/pinnacle-scrape-odds.py` | Done. `spread_line`, `spread_odds1`, `spread_odds2` from Pinnacle API (home +line, away −line) |
| **Handicap probability math** | `scripts/handicap_probs.py` | Done. K-M recursion: `game_margin_pmf_bo3`, `prob_p1_covers_plus`, `prob_p2_covers_minus` |
| **Compute handicap values** | `scripts/compute-handicap-values.py` | Done. Matches fair rows to Pinnacle by surname; computes model prob vs implied; PATCHes `daily_fair_odds` |
| **Daily pipeline** | `scripts/run-daily-odds.py` | Done. Runs: Pinnacle scrape → fair odds → compute-handicap-values → strict report |
| **Fair-odds API** | `src/app/api/fair-odds/route.ts` | Returns `spread_line`, `spread_odds1`, `spread_odds2`, `handicap_edge_p1`, `handicap_edge_p2` |
| **Fair-odds UI** | `src/app/fair-odds/page.tsx` | Spread column shows P1 +line / P2 −line with odds and edge % |

### 1.2 Handicap Probability Formulas

- **P1 +line:** P(games_P1 − games_P2 > −line) — covers when margin > −line  
- **P2 −line:** P(games_P1 − games_P2 < −line) — covers when margin < −line  

Both use `prob_p1_covers_plus` and `prob_p2_covers_minus` in `handicap_probs.py`, which build the full game margin PMF from `(p_a, p_b)` via K-M recursion.

### 1.3 Odds Mapping (Pinnacle vs Our Model)

- **Pinnacle:** `player1` = home, `player2` = away. `spread_odds1` = home +line, `spread_odds2` = away −line.  
- **When our P1 = Pinnacle home:** P1+ = odds1, P2− = odds2. Direct mapping.  
- **When our P1 = Pinnacle away:** P1+ = away+ = complement of away−. So `spread_odds1 = pin_odds2 / (pin_odds2 − 1)`. P2− = away− = odds2.  

This mapping was fixed in `compute-handicap-values.py` to avoid comparing wrong sides.

### 1.4 Edge Formula

```python
edge = (model_prob - implied_prob) / implied_prob * 100
implied_prob = 1 / decimal_odds
```

### 1.5 Current Symptom

After the odds-mapping fix, P1+ and P2− edges are now opposite (one positive, one negative), which is correct. But P1+ edges are still very high: typically +20% to +80%. Only a few matches show moderate edges (e.g. Vacherot vs Ruud 11%, Fils vs FAA 9%, Tien vs Davidovich 1%). This suggests the model systematically overestimates P(P1 covers +line).

---

## 2. Reference: How O/U and Match Prob Were Calibrated

The project already calibrates match odds and O/U. Use these as patterns for handicap calibration.

### 2.1 Match Probability Calibration

- **File:** `scripts/oncourt-compute-fair-odds.py`  
- **Constants:** `PROB_CAL_A`, `PROB_CAL_B`, `PROB_CAL_SERIES_BLEND`  
- **Function:** `_calibrate_match_probability(p1_win, series_bucket, surface, confidence)` — Platt transform in favourite-space, blended by tour tier  
- **Backtest:** `scripts/backtest-fair-odds.py` — fits on historical data, outputs calibration metrics  

### 2.2 O/U Calibration

- **File:** `scripts/oncourt-compute-fair-odds.py`  
- **Constants:** `OU_LINE_SHIFT_BY_SURFACE`, `OU_CHALLENGER_EXTRA_SHIFT`, `OU_ATP_MAIN_TOUR_EXTRA_SHIFT`  
- **Logic:** Model tended to run high on totals; shift thresholds up when pricing P(over), equivalent to shifting our distribution left. `exp_games_cal = exp_games - ou_shift`; `p_over = prob_over_games(p_a_eg, p_b_eg, line + ou_shift)`  

### 2.3 Backtest Data

- **Backtest results:** `data/backtest/backtest-results-2022.csv` through `backtest-results-2025.csv`  
- **Columns:** `date`, `tournament`, `surface`, `round`, `series`, `player1`, `player2`, `our_prob`, `pinnacle_odds`, `pinnacle_odds_loser`, `actual_winner`, `score`, `p_a`, `p_b`, …  
- **Backtest script:** `scripts/backtest-fair-odds.py` — outputs `p_a`, `p_b` in CSV  

### 2.4 Handicap Backtest (Partial)

- **File:** `scripts/handicap-backtest.py`  
- **Note:** Designed to run against REAL Pinnacle spread lines. Currently backtest CSVs do **not** include `spread_line`, `spread_odds1`, `spread_odds2`. Those live in `bookmaker_odds_snapshot` (Supabase).  
- **Methodology:** `docs/HANDICAP-BACKTEST-METHODOLOGY.md` — do NOT invert ML odds to synthesise handicap; use real spread data.  

---

## 3. Data Available for Calibration

### 3.1 Live Data

- **Supabase:** `bookmaker_odds_snapshot` has `spread_line`, `spread_odds1`, `spread_odds2` for Pinnacle ATP matches  
- **Supabase:** `daily_fair_odds` has `p_a`, `p_b`, `spread_line`, `spread_odds1`, `spread_odds2`, `handicap_edge_p1`, `handicap_edge_p2`  
- **Pinnacle scrapes:** `data/pinnacle-odds-2026-03-*.csv` — include spread columns  

### 3.2 Historical Backtest

- **Match results:** `data/backtest/backtest-results-2022.csv` … `backtest-results-2025.csv` — have `p_a`, `p_b`, `score`, `player1`, `player2`, `date`, etc.  
- **No historical spread:** Backtest CSVs do not have historical Pinnacle spread. To backtest handicap, you would need to either:  
  - (a) Join backtest to `bookmaker_odds_snapshot` by date + player names (if historical snapshots exist), or  
  - (b) Build a calibration script that uses **settled outcomes** (parse `score` → game margin) and compares model P(cover) to empirical hit rate for different line ranges  

### 3.3 Settling Handicap Bets

- **Score parsing:** `scripts/handicap-backtest.py` has `parse_score(score_str)` → `{games_a, games_b, margin, …}`  
- **P1+ covers:** when `margin > −line` (i.e. margin in P1’s favour by more than −line)  
- **P2− covers:** when `margin < −line`  

---

## 4. What You Need to Do

### 4.1 Calibration Goal

Reduce systematic overestimation of P(P1 covers +line). Edges should be roughly centred around 0, with outliers in ±10–20% range, not +20% to +80% on almost every match.

### 4.2 Possible Approaches

1. **Line shift (like O/U):** Add a `HANDICAP_LINE_SHIFT` (or equivalent) so we compare model probabilities at `line + shift` vs market. If market is sharper, shifting our line up/down could correct bias.  

2. **Probability calibration (like match prob):** Apply a post-hoc transform to `prob_p1_covers_plus` / `prob_p2_covers_minus` before computing edge — e.g. Platt scaling, temperature, or empirical correction from backtest.  

3. **Backtest-driven calibration:**  
   - Build a script that: loads backtest CSVs (with `p_a`, `p_b`, `score`), parses scores to get actual game margin, computes model P(cover) for each line, and compares to empirical hit rate.  
   - Fit calibration parameters (shift, scale, etc.) to minimise bias.  
   - Apply those parameters in `compute-handicap-values.py` or in `handicap_probs.py`.  

4. **Cross-validation:** If you have historical spread data (e.g. from `bookmaker_odds_snapshot` by date), compare model vs actual outcomes over time.  

### 4.3 Where to Apply Calibration

- **Option A:** In `compute-handicap-values.py` — apply shift/transform to `model_p1` and `model_p2` before computing edge.  
- **Option B:** In `handicap_probs.py` — add a `calibrated_prob_p1_covers_plus(p_a, p_b, line, surface?, series?)` that wraps the raw prob with calibration.  
- **Option C:** Add `HANDICAP_*` constants in `oncourt-compute-fair-odds.py` (alongside `OU_LINE_SHIFT_*`) and pass them through to the handicap compute step.  

### 4.4 Constraints

- **Do not change** the core K-M recursion or `prob_p1_covers_plus` / `prob_p2_covers_minus` math — they are correct.  
- **Do not** invert ML odds to synthesise handicap lines — that is explicitly wrong per `HANDICAP-BACKTEST-METHODOLOGY.md`.  
- **Preserve** the odds mapping logic (home/away, complement when P1=away) — that was fixed and is correct.  

---

## 5. Files to Modify / Create

| File | Purpose |
|------|---------|
| `scripts/compute-handicap-values.py` | Apply calibration to model probs before edge calculation |
| `scripts/handicap_probs.py` | Optionally add calibrated wrapper functions |
| `scripts/oncourt-compute-fair-odds.py` | Add `HANDICAP_*` constants if needed |
| `scripts/handicap-calibration.py` | **New:** Script to backtest handicap vs settled outcomes, fit calibration params |
| `docs/CODEX-HANDICAP-CALIBRATION-HANDOVER.md` | This file — update with your findings |

---

## 6. Deliverables

1. **Calibrated code** — scripts and constants that produce realistic handicap edges.  
2. **Calibration script** (if you build one) — e.g. `handicap-calibration.py` that runs on backtest data and outputs recommended parameters.  
3. **Short summary** — what you changed, what parameters you chose, and how you validated (e.g. “before: mean P1+ edge +45%; after: mean +2%”).  
4. **Updated handover** — if you add new constants or change behaviour, document them in this file.  

---

## 7. Quick Commands

```bash
# Run full pipeline (Pinnacle + fair odds + handicap)
python scripts/run-daily-odds.py

# Run only handicap compute (after fair odds + Pinnacle scrape)
python scripts/compute-handicap-values.py
python scripts/compute-handicap-values.py --date 2026-03-09

# Run backtest (match winner; outputs p_a, p_b)
python scripts/backtest-fair-odds.py --files data/backtest/atp-2024.xlsx

# Handicap backtest (expects p_a, p_b in CSV; no real spread in backtest yet)
python scripts/handicap-backtest.py --files data/backtest/backtest-results-2024.csv
```

---

## 8. Environment

- **Supabase:** `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` in `.env.local`  
- **Python:** `scripts/requirements.txt` for dependencies  
- **Branch:** Work on `golden-with-speed-insights`; do not push to `main`  

---

*Handover prepared for Codex. Handicap implementation is complete; calibration is the remaining task.*

---

## 8.1 Handicap Signals and Settlement (NOT YET IMPLEMENTED)

**These were not in the original calibration scope but are required for production use.**

### Handicap signal generation

- Extend the strict policy so it can emit **spread signals** when `handicap_edge_p1` or `handicap_edge_p2` exceeds a threshold (e.g. 10%).
- Add `handicap_value_p1`, `handicap_value_p2` (or equivalent) to the strict policy output.
- Include handicap signals in the daily strict report (`strict-signals.csv` or equivalent) with: match id, side (P1+ or P2−), line, odds, edge %.

### Handicap settlement

- Extend `settle-strict-signals.py` (or equivalent) to settle handicap bets:
  - Parse final score → game margin (use `parse_score` from `handicap-backtest.py`).
  - P1+ covers when `margin > −line`; P2− covers when `margin < −line`.
  - Mark win/loss for each handicap bet in the settlement output.

**Files to modify:** `scripts/strict-policy-report.py`, `scripts/settle-strict-signals.py`, `src/app/api/fair-odds/route.ts` (if policy payload needs handicap fields).

---

## 9. Codex Update (2026-03-09)

Implemented calibration and wired it into production compute flow.

- Updated `scripts/compute-handicap-values.py`:
  - Added calibration loader from `data/backtest/handicap-calibration-params.json` (or `HANDICAP_CALIBRATION_FILE`).
  - Added env/flag gating:
    - `HANDICAP_CALIBRATION_MODE=auto|off|force` (default `auto`)
    - `--disable-calibration`
    - `--dry-run` for diagnostics without DB writes.
  - Applies calibrated model probability:
    - raw at shifted line: `prob_p1_covers_plus(p_a, p_b, line + HANDICAP_LINE_SHIFT)`
    - Platt: `sigmoid(a + b * logit(p_raw_shifted))`
    - P2 side set as complement `1 - p1` for consistency.
  - Added edge diagnostics printout (raw vs calibrated).

- Added/updated `scripts/handicap-calibration.py`:
  - Fits calibration from historical settled results (`backtest-results-2022..2025.csv`).
  - Uses symmetric line grid by default (`-5.5 .. +5.5`).
  - Adds mirrored (swapped player) samples to remove player1 orientation bias.
  - Grid-searches line shift, fits Platt `(a,b)`, and writes JSON output.

Latest fitted params:
- `HANDICAP_LINE_SHIFT = -0.5`
- `HANDICAP_PLATT_A = -0.027807`
- `HANDICAP_PLATT_B = 0.561037`

Quick live dry-run check (12 matched rows):
- raw P1+ mean edge: `+31.66%`
- calibrated P1+ mean edge: `+12.51%`

Commands:
```bash
python scripts/handicap-calibration.py
python scripts/compute-handicap-values.py --dry-run
python scripts/compute-handicap-values.py
```

### How spreads appear on localhost

Spreads are **live** in the sense that the fair-odds page reads from Supabase `daily_fair_odds`. To see calibrated spread data:

1. Run the pipeline: `python scripts/run-daily-odds.py` (or at least: Pinnacle scrape → oncourt-compute-fair-odds → compute-handicap-values).
2. `compute-handicap-values.py` PATCHes `daily_fair_odds` with `spread_line`, `spread_odds1`, `spread_odds2`, `handicap_edge_p1`, `handicap_edge_p2`.
3. The API fetches these columns and the UI displays them in the Spread column.

If you haven't run the pipeline recently, you'll see stale or empty spread data. The calibration only affects the edge values written to the DB — the pipeline must run to write them.

### Real-line calibration update (bookmaker snapshot join)

`scripts/handicap-calibration.py` now supports real historical spread-line fitting by joining
backtest rows to `bookmaker_odds_snapshot`:

- Default mode is now `--line-source snapshot` (real spread lines from Supabase).
- `--line-source auto` tries snapshot first, then falls back to synthetic lines if there are
  no matched snapshot rows.
- Join uses date + normalized player names (with small date window), then optional surname fallback.
- Output JSON now records:
  - `line_source_requested`
  - `line_source_used`
  - `source_details.snapshot` (snapshot rows, matched/unmatched counts, join methods)

Example:
```bash
python scripts/handicap-calibration.py --line-source snapshot
python scripts/handicap-calibration.py --line-source auto
```
