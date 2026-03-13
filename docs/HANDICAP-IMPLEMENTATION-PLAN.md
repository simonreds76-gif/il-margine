# Handicap Implementation Plan

**Status: Implemented** (Phase 1–3 complete). See "What you need to do" below.

## Do we know how to calculate handicaps?

**Yes.** Claude documented this in `docs/HANDICAP-BACKTEST-METHODOLOGY.md` and the math is implemented in `scripts/handicap_probs.py`.

### The correct approach (from Claude)

1. **Use real Pinnacle spread lines** — not synthesised from moneyline odds. The mapping from match probability → (p_a, p_b) is **not unique**. Many (p_a, p_b) pairs give the same match win probability but completely different margin distributions.

2. **Model handicap probs** — from `handicap_probs.py`:
   - `prob_dog_covers(p_a, p_b, line)` — P(underdog +line covers)
   - `prob_fav_covers(p_a, p_b, line)` — P(favourite -line covers)
   - `handicap_value(p_a, p_b, line, pinnacle_odds, side)` — model prob vs implied prob, edge %

3. **Inputs required:** Real (p_a, p_b) from the matchup model — **not** inverted from match win probability.

---

## Why handicaps are not implemented yet

| Component | Status | Gap |
|-----------|--------|-----|
| **Spread scrape** | ✅ Done | Pinnacle spread_line, spread_odds1, spread_odds2 scraped and stored |
| **Supabase schema** | ✅ Done | spread columns added to bookmaker_odds_snapshot |
| **handicap_probs.py** | ✅ Done | Full K-M extension for game margin, prob_dog_covers, prob_fav_covers, handicap_value |
| **p_a, p_b persistence** | ❌ Missing | Pipeline computes p_a, p_b but does **not** write them to daily_fair_odds |
| **Fair-odds API** | ❌ Missing | Doesn't fetch spread from snapshot; doesn't compute handicap value |
| **Fair-odds UI** | ❌ Missing | No spread columns or handicap value display |
| **Handicap backtest** | ⚠️ Partial | Expects p_a, p_b in CSV; backtest-fair-odds.py doesn't output them → falls back to invert_km_symmetric (wrong per methodology) |

### Root cause

The pipeline was built for **match winner + O/U**. Handicaps were added as data capture (scrape, store) but never wired into the compute flow. The critical missing piece is **p_a, p_b persistence** — without it, we cannot compute handicap probs at API/runtime without re-inverting from match prob, which the methodology explicitly forbids.

---

## Implementation plan

### Phase 1: Persist p_a, p_b (foundation)

1. **Schema:** Add `p_a` and `p_b` columns to `daily_fair_odds`.
2. **Pipeline:** In `oncourt-compute-fair-odds.py`, add `p_a` and `p_b` to the output row (they are already computed; just include them in the upsert).
3. **Backtest:** In `backtest-fair-odds.py`, add `p_a` and `p_b` to the CSV output fields so handicap-backtest can use real model values.

**Deliverables:** Migration SQL, pipeline change, backtest CSV change.

---

### Phase 2: Fair-odds API — fetch spread and compute handicap value

1. **Pinnacle fetch:** Extend the `bookmaker_odds_snapshot` select to include `spread_line`, `spread_odds1`, `spread_odds2`.
2. **Match logic:** When matching Pinnacle rows to fair-odds rows, pass through spread data.
3. **Handicap computation:** For each matched row with spread_line and p_a/p_b:
   - Determine favourite (p1_win_prob > 0.5 → P1 fav)
   - `spread_line` convention: P1 +spread_line, P2 -spread_line (or vice versa — verify Pinnacle mapping)
   - Call `handicap_value(p_a, p_b, line, pinnacle_odds, side="dog"|"fav")` for both sides
   - Add to response: `spread_line`, `spread_odds1`, `spread_odds2`, `handicap_value_p1`, `handicap_value_p2` (or similar)

**Note:** The API is TypeScript; `handicap_probs.py` is Python. Options:
- **A)** Port the core logic (game_margin_pmf_bo3, prob_dog_covers, prob_fav_covers) to TypeScript
- **B)** Call a small Python helper/API at build or runtime (heavy)
- **C)** Pre-compute handicap values in the pipeline and store in daily_fair_odds (simplest: add spread_line, spread_odds1, spread_odds2, handicap_edge_p1, handicap_edge_p2 when Pinnacle match exists)

**Recommended:** **C** — compute handicap value in `oncourt-compute-fair-odds.py` (or a separate script that runs after fair-odds + Pinnacle scrape) and persist. API just reads.

---

### Phase 3: Fair-odds UI — display handicaps

1. Extend `FairOddsMatch` interface with `spread_line`, `spread_odds1`, `spread_odds2`, `handicap_edge_p1`, `handicap_edge_p2` (or equivalent).
2. Add a "Spread" column (or expandable section) showing Pinnacle line and model edge.
3. Optional: highlight rows with handicap value ≥ X% (e.g. 5%) similar to match winner value.

---

### Phase 4: Handicap backtest with real spread data

1. Ensure backtest output includes `p_a`, `p_b` (Phase 1).
2. Extend backtest to join with `bookmaker_odds_snapshot` (or historical spread CSV) for matches with real Pinnacle spread.
3. Run `handicap-backtest.py` against real spread lines; remove or deprecate the invert_km_symmetric fallback.

---

## Summary

| Phase | Effort | Blocks |
|-------|--------|--------|
| 1. Persist p_a, p_b | Low | Schema + 2 script changes |
| 2. API handicap value | Medium | Python in pipeline vs TS port; Pinnacle spread fetch |
| 3. UI display | Low | After Phase 2 |
| 4. Backtest with real spread | Medium | Backtest join + data collection (2–3 weeks) |

**We know how to calculate handicaps.** The methodology is documented and the math exists.

---

## What you need to do

1. **Run Supabase migrations** (SQL Editor):
   - `docs/supabase-daily-fair-odds-pa-pb.sql` — adds p_a, p_b
   - `docs/supabase-daily-fair-odds-handicap.sql` — adds spread_line, spread_odds1, spread_odds2, handicap_edge_p1, handicap_edge_p2

2. **Re-run the pipeline** so daily_fair_odds gets p_a/p_b and handicap values:
   ```bash
   python scripts/run-daily-odds.py
   ```
   Or run steps manually: Pinnacle scrape → oncourt-compute-fair-odds → compute-handicap-values

3. **Refresh localhost/fair-odds** — the Spread column will show ±line and edge % for P1 +line / P2 -line.
