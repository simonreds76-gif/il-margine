# Challenger ML rebuild brief

Read-only model-risk review requested. Do not edit files.

## Verified current state

- The current archive `data/backtest/strict-signals-challenger-ml-archive.csv` contains 23 settled rows, all tagged `challenger_ml_nearmiss` / audit-only.
- Outcome record: 8 wins, 15 losses (34.8%).
- Only 15 rows have usable captured Pinnacle entry odds. Flat-stake result on those rows is -2.601u, ROI -17.3%.
- The performance script correctly excludes all 23 from official staking ROI, so the latest official report is a zero-row stub.
- The current Challenger live/archive files stopped updating on 2026-06-02.
- `CHALLENGER_ML_ENABLE` defaults to `0` in both AM and daily runners.
- There is no current Challenger CLV output.

## Data that actually exists

- `data/backtest/challenger-calibration-audit-predictions.csv`: 96,800 player-oriented rows = 48,400 matches, 2022-01-03 through 2026-05-18. Splits: 31,805 matches train 2022-24, 11,400 validation 2025, 5,195 holdout 2026. Surfaces: 23,864 Hard, 23,081 Clay, 1,455 Grass matches. Each row has outcome and `challenger_context_prob`.
- Sackmann `atp_matches_qual_chall_2023.csv` through `2026.csv`: 39,227 total matches, including 34,722 Challenger-level `C` rows. These provide outcomes, ranks and match stats, but no bookmaker prices.
- Refreshed OnCourt ATP files contain full games, tours, players and stats; the current model can derive causal pre-match features if the historical backtester is used correctly.
- Local `data/pinnacle-history/*.csv`: 65,912 Challenger capture rows covering 4,991 unique Challenger matches from 2026-06-02 through 2026-08-21. Capture modes: 59,355 close, 6,357 daily, 200 weekly. Rows contain ML, total and spread prices plus kickoff.
- Existing `backtest-results-challenger-2026.csv` has only 60 matches because the old backtester used a narrow/stale XLSX odds source. That is not the available-data ceiling.
- `daily_fair_odds` is a current-state table: `_sync_daily_fair_odds` removes stale rows. It is not a prediction archive.

## Questions requiring a concrete verdict

1. Can the 48,400-match probability archive support model calibration/model-selection claims, and what exact metrics/splits should be registered?
2. What is the safest way to adapt `scripts/backtest-fair-odds.py` so the 4,991 captured Pinnacle Challenger matches are scored with point-in-time/casual model features, without leaking current OnCourt stats?
3. Should the initial prospective lane preserve the existing HIGH coverage + high confidence + 10-15% edge gate, or should gates be selected only after a registered walk-forward analysis?
4. Specify a clean new prospective schema and lifecycle: append at publication, immutable entry odds, nightly outcome settlement, true pre-kickoff close, ROI/CLV/calibration, weekly report and monitor.
5. Decide what to do with the old 23 audit-only rows. They must never be presented as an authorized betting record.
6. Identify the smallest implementation sequence that starts collecting evidence immediately without prematurely claiming an edge.

## Required answer

Return an evidence-backed implementation specification, ordered by priority. Distinguish clearly between:

- historical probability/calibration evidence;
- historical real-price ROI evidence;
- prospective real-price ROI/CLV evidence;
- anything that remains impossible with current data.

No edits. No generic suggestions. Cite exact repo files/functions and define acceptance gates.
