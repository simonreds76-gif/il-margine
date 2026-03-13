# Path B: Edge Research Roadmap

**Goal:** Build toward a genuine edge over Pinnacle. The current model (hold%/return% + Elo + rank) is commodity — Pinnacle prices it in. A real edge needs information the market doesn't fully absorb.

---

## What You Already Have (Unvalidated)

| Signal | Status | Backtested? | Next Step |
|--------|--------|-------------|-----------|
| **CPI / court speed** | In model, OFF by default | `--enable-cpi-overlay` exists in backtest | Run backtest with CPI on, segment-validate |
| **Injury overlay** | Strict policy filter, OFF by default | No backtest with injury downweight | Add `--injury-downweight` to backtest, validate |
| **Vs leftie** | In model (VS_LEFTIE_WEIGHT ~3%) | Yes, in baseline | Already in; consider if weight is right |
| **Vs big servers** | Chat only, not in model | No | Add to model? Backtest? |
| **H2H, tournament history** | In model | Yes | Already in baseline |

---

## Path B Priorities (by feasibility × potential)

### 1. Validate CPI Overlay — TESTED, NO EDGE

- **Result (2024-03):** Backtest 2022–2024 with `--enable-cpi-overlay`. Log-loss 0.629 vs Pinnacle 0.581. ROI -5.4% to -7.8%. Segment validation: WEAK. CPI does not produce a demonstrable edge.
- **Note:** The CPI run overwrote `backtest-results-2022/2023/2024.csv`. To restore baseline (no CPI), re-run: `python scripts/backtest-fair-odds.py --files data/backtest/atp-2022.xlsx data/backtest/atp-2023.xlsx data/backtest/atp-2024.xlsx` (omit `--enable-cpi-overlay`).

### 2. Validate Injury Overlay (Quick Win)

- **Why:** Recently retired/walkover players may be under-priced by the market in their next match.
- **What:** Add injury downweight to backtest; use historical injured list (or proxy: flag matches where a player retired in prior 14 days from match results). Segment-validate.
- **Effort:** 2–4 hours (wire injury CSV into backtest, add flag).
- **Data:** `data/injured-players-tennisexplorer.csv` — but this is current scrape; for backtest you'd need historical. Option: use Sackmann match outcomes (retired/walkover) as proxy for "recently injured".

### 3. Matchup-Specific Tactical Data (Medium)

- **Idea:** "How does X do against left-handed heavy-spin players on slow hard courts?"
- **What you have:** vs_leftie (overall), court speed (CPI). Missing: "heavy-spin" classification, combined filters.
- **Build:** Define "big server" (SPW > 65th percentile?) and "heavy-spin" (clay specialists? return-style?). Create player_type × opponent_type × surface segments. Backtest.
- **Effort:** 1–2 weeks.
- **Edge hypothesis:** Pinnacle may not fully price niche matchup edges (e.g. baseliner vs leftie serve-and-volleyer on fast grass).

### 4. Injury Before It's Public (Hard)

- **Idea:** Use injury info before it hits TennisExplorer / press.
- **Sources:** Social media, player team announcements, withdrawal patterns. Manual or scraped.
- **Effort:** High; requires new data pipeline and validation.
- **Your edge:** 25 years of odds compiling — you may know which tournaments have late withdrawal patterns, which players telegraph injury.

### 5. In-Play Momentum (Hard)

- **Idea:** Live momentum patterns (e.g. run of breaks) that predict set/match reversal.
- **What:** Would need live data feed (Betfair, Pinnacle live, etc.), different architecture.
- **Effort:** Multi-month project.

---

## Recommended First Steps

1. ~~**Run CPI backtest**~~ — Done. No edge.
2. **Run injury backtest** — Use Sackmann retirements as "recently injured" proxy for historical backtest. Does excluding or downweighting those players improve ROI?
3. **Document soft spots** — From your 25 years: which tournaments, surfaces, or player types have historically had softer lines? That's your research prioritisation.

---

## Validation Rule

Every Path B hypothesis must pass **segment-edge-validation.py** before it counts as an edge. No exceptions.
