# Message for Codex: Backtest script (model vs 2024/2025 Pinnacle CLV)

**Can you implement the backtest so we can test whether our fair-odds model is solid vs historical Pinnacle closing line value?**

---

## What we need

A single script that:

1. **Reads historical matches + Pinnacle closing odds** from the tennis-data.co.uk files we already have:
   - `data/backtest/atp-2024.xlsx`
   - `data/backtest/atp-2025.xlsx`
   - (and optionally `atp-2026.xlsx` for YTD)

   These contain: Date, Tournament, Surface, Round, Winner, Loser, WRank, LRank, Score, and **Pinnacle closing odds** (`PSW` = Pinnacle winner odds, `PSL` = Pinnacle loser odds). Column definitions: http://www.tennis-data.co.uk/notes.txt

2. **For each match (no look-ahead):**
   - Map tennis-data player names (e.g. "Sinner J." / "Djokovic N.") to our OnCourt player IDs (e.g. "Jannik Sinner" / "Novak Djokovic"). Log unmatched and skip those matches.
   - Use only stats/Elo from data **before** the match date. (Option A: use current DB stats and accept small look-ahead bias for speed; Option B: re-compute stats per date for rigor — we can start with A.)
   - Compute our fair odds the same way as `oncourt-compute-fair-odds.py` (reuse or import from that script + `src/lib/tennis_prob.py` for K-M recursion).

3. **Compare to outcome and to Pinnacle:**
   - Did the predicted winner win?
   - Our odds vs Pinnacle closing odds.

4. **Output:**
   - **Console:** Calibration table (prediction buckets vs actual win rate), log loss vs Pinnacle, ROI by Value% threshold (e.g. 2%, 5%, 10%), and a short summary a non-technical person can read.
   - **CSV:** `data/backtest/backtest-results-2024.csv` (and same for 2025) with: date, tournament, surface, round, player1, player2, our_prob, our_odds, pinnacle_odds, actual_winner, value_pct, bet_result.
   - **Log:** Unmatched players, skipped matches, warnings.

---

## How we’ll judge if the model is solid

1. **Calibration**  
   When we say 65% win probability, do players in that bucket win ~65%? Bins (e.g. 50–55%, 55–60%, …, 90–95%). If we’re well-calibrated, the curve is close to the diagonal.

2. **Log loss vs Pinnacle**  
   Our model’s log loss on actual outcomes vs Pinnacle’s implied log loss. If we’re in the same ballpark or better, the model is competitive with the closing line.

3. **Value% and profitability**  
   Value% = (Pinnacle_odds / our_odds) − 1. Simulate flat-stake bets when Value% > threshold (2%, 5%, 10%). Report ROI, number of bets, longest losing streak. If ROI is positive at reasonable thresholds, the model has exploitable edge vs the closing line.

4. **Segmentation**  
   Break results by surface (Hard, Clay, Grass), tournament tier (Grand Slam, Masters, 500, 250), and optionally by data quality (e.g. both players with 20+ matches). This shows where the model is strong or weak.

---

## Reference

Full spec, constraints, and file list: **`docs/CLAUDE-BACKTEST-REQUEST.md`**.

- New script: **`scripts/backtest-fair-odds.py`** (standalone; don’t modify existing scripts).
- Use `openpyxl` for xlsx (`pip install openpyxl`).
- Handle missing data by skipping the match, logging the reason, and continuing.

---

## Summary

Implement `scripts/backtest-fair-odds.py` following `docs/CLAUDE-BACKTEST-REQUEST.md`. Input: `data/backtest/atp-2024.xlsx` and `atp-2025.xlsx` (Pinnacle closing odds + results). Output: calibration, log loss vs Pinnacle, ROI by Value% threshold, plus CSV and logs. That will tell us whether the model is solid going back vs 2024/2025 Pinnacle CLV.
