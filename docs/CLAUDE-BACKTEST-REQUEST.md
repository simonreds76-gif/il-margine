# Backtest Request — Fair Odds Model vs Pinnacle Closing Odds

**Priority**: After the calibration fix and O/U changes from `CLAUDE-FAIR-ODDS-CALIBRATION-AND-OU.md` are done.

---

## Goal

Build a backtest script that evaluates how well our fair odds model (`oncourt-compute-fair-odds.py`) performs against historical Pinnacle closing odds and actual match outcomes. This tells us:
1. Is the model well-calibrated? (When we say 70%, does the player win ~70% of the time?)
2. How does our log loss compare to Pinnacle's?
3. Would betting on our Value% signals be profitable?

---

## Data available

### Historical odds (tennis-data.co.uk)
Downloaded to `data/backtest/`:
- `atp-2024.xlsx` — full 2024 ATP season
- `atp-2025.xlsx` — full 2025 ATP season
- `atp-2026.xlsx` — 2026 year-to-date

These contain per-match: Date, Tournament, Surface, Round, Winner, Loser, WRank, LRank, Score, and **Pinnacle closing odds** (columns `PSW` = Pinnacle winner odds, `PSL` = Pinnacle loser odds). Also has Bet365, Betway odds. See http://www.tennis-data.co.uk/notes.txt for column definitions.

### Our model data (already in Supabase/OnCourt)
- `oncourt_games` + `oncourt_stat` — historical match results and serve stats
- `player_surface_stats` — computed hold%/return% by surface
- `player_elo` — Elo ratings by surface
- `oncourt_players` — player name/ID mapping
- `src/lib/tennis_prob.py` — K-M recursion engine

---

## Backtest design

### Script: `scripts/backtest-fair-odds.py`

For each match in the tennis-data file:

1. **Name matching**: Map tennis-data player names to OnCourt player IDs. Handle format differences (tennis-data uses "Sinner J." or "Djokovic N.", OnCourt uses "Jannik Sinner" or "Novak Djokovic"). Build a mapping table, log unmatched.

2. **No look-ahead**: For match on date D, only use stats/Elo computed from data BEFORE date D. This is critical — we can't use 12-month stats that include the match itself.
   - Option A (simpler): Use current stats as-is and accept slight look-ahead bias. Note: for a 12-month rolling window, the bias is small for any single match.
   - Option B (rigorous): Re-compute stats for each date. Much slower but more accurate.
   - **Recommend Option A first**, then Option B if results look suspiciously good.

3. **Compute fair odds**: Same model logic as `oncourt-compute-fair-odds.py` — load player stats + Elo, compute p_A/p_B, run K-M recursion, get P(win) and fair odds.

4. **Compare to actual outcome**: Did the predicted winner actually win?

5. **Compare to Pinnacle**: Our odds vs their closing odds.

### Metrics to compute

**Calibration**:
- Bin predictions into buckets (50-55%, 55-60%, ..., 90-95%)
- For each bucket: average predicted probability vs actual win rate
- Plot calibration curve (or print table)

**Accuracy**:
- Log loss (our model vs Pinnacle)
- Brier score
- Accuracy at various probability thresholds

**Profitability simulation**:
- For each match, compute Value% = (Pinnacle_odds / our_odds - 1) * 100
- Simulate flat-stake betting on all matches where Value% > threshold (try 2%, 5%, 10%)
- Track ROI, number of bets, longest losing streak
- Separate by: surface, tournament tier (Grand Slam / Masters / 500 / 250), round

**Segmentation**:
- Split results by tournament tier (Grand Slams, Masters 1000, ATP 500, ATP 250)
- Split by surface (Hard, Clay, Grass)
- Split by match_count buckets (both players 20+ matches vs thinner data)
- This shows WHERE the model is strong and where it's weak

### Output

1. **Console summary**: Key metrics, calibration table, ROI by threshold
2. **CSV**: `data/backtest/backtest-results-2024.csv` with columns: date, tournament, surface, round, player1, player2, our_prob, our_odds, pinnacle_odds, actual_winner, value_pct, bet_result
3. **Log**: Unmatched players, skipped matches, warnings

---

## Files involved
- `scripts/backtest-fair-odds.py` (new) — the backtest script
- `scripts/oncourt-compute-fair-odds.py` — reference for model logic (reuse functions, don't duplicate)
- `src/lib/tennis_prob.py` — K-M recursion (import directly)
- `data/backtest/atp-2024.xlsx`, `atp-2025.xlsx`, `atp-2026.xlsx` — tennis-data historical odds

## Important constraints
- Use `openpyxl` to read xlsx files (`pip install openpyxl`)
- Don't modify any existing scripts — this is a standalone analysis tool
- Print a clear summary at the end that a non-technical person can understand
- Handle missing data gracefully (skip match, log reason, continue)
