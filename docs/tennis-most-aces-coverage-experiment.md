# Most Aces Coverage Experiment

Registered: 2026-07-29

## Problem

The production prop baseline reads main-tour match files only. Qualifying and
Challenger matches are available locally but are omitted from the activity
sample, causing active players to be labelled stale when their recent matches
were outside the main tour.

Activity coverage and performance estimation are separate:

- all-level activity may classify whether a player is active;
- Challenger performance must not enter an ATP projection without a fitted,
  frozen level adjustment.

No arm below may change live betting or shadow-value registration before all
acceptance gates pass.

## Splits

- Development: 2023-01-01 through 2024-12-31.
- Selection: 2025 full year.
- Confirmatory diagnostic: 2026-01-01 through 2026-07-29.
- Untouched prospective holdout: 2026-07-30 forward.

The 2026 confirmatory period has already been inspected and cannot be used for
further tuning.

## Arms

- A0: shipped main-tour-only pipeline.
- A1: A0 plus qualifying/Challenger baseline rows with a level factor fitted
  on development data.
- A2: A1 plus rank-band by thin-sample recalibration.
- A3: A2 plus reproducible lagged activity, age and ranking features.
- A4: A3 plus evidence tiers based on coverage-inclusive all-surface activity.

## Gates

- G1: overall ace MAE improves by at least 1.0% versus A0.
- G2: NB2 log-loss improves by at least 0.002.
- G3: Hard and Clay MAE regression is no worse than 2.0%.
- G4: Hard and Clay log-loss regression is no worse than 0.003.
- G5: low-rank thin-sample predicted/actual ratio lies within 0.95 to 1.05.
- G6: top-200 predicted/actual ratio remains within 0.97 to 1.05.
- G7: at least 900 ATP Hard/Clay holdout sides and 150 low-rank thin sides.
- G8: Most Aces recent-tier Brier does not exceed 0.460561.
- G9: no top-50 player with at least 12 all-surface L12M matches is labelled
  historical.

## Price Gate

No monetary claim is allowed until at least 300 timestamped, settled,
three-way Most Aces observations across at least 100 events are captured,
de-vigged completely, and mean CLV is at least +1.0%.

## Frozen Results

### A1: Level-Adjusted Qualifying and Challenger Coverage

Status: **FAIL — retain A0**

- 2025 selection MAE improved by 0.95%, below the 1.0% gate.
- 2025 selection log-loss worsened by 0.004185.
- 2026 confirmatory MAE improved by 2.28%.
- 2026 confirmatory log-loss improved by 0.000520, below the 0.002 gate.

The 2025 selection failure rejects A1. The stronger 2026 diagnostic result
cannot be used to override that decision because the period has already been
inspected.

### A2: Rank-Band Thin-Sample Recalibration

Status: **FAIL — retain A0**

- 2025 selection MAE improved by 0.43%.
- 2025 selection log-loss worsened by 0.005558.
- 2026 confirmatory MAE improved by 2.16%.
- 2026 confirmatory log-loss improved by 0.000146, below the 0.002 gate.
- Low-rank thin-sample predicted/actual ratio was 0.989, but only 20 sides
  qualified, below the registered sample gate.
- Top-200 predicted/actual ratio was 0.973.

A2 is rejected. No production model, signal routing, staking, ROI or CLV
claim changes.

### A3: Activity, Age and Lagged Ranking Features

Status: **FAIL — retain A0**

- 2025 selection MAE improved by 1.25%.
- 2025 selection log-loss worsened by 0.000665.
- 2026 confirmatory MAE improved by 2.90%.
- 2026 confirmatory log-loss improved by 0.004598.
- 2026 recent-tier Most Aces Brier improved from 0.460561 to 0.451747.
- 2026 recent-tier Most Aces log-loss improved from 0.785260 to 0.773839.
- Hard-court confirmatory log-loss regressed by 0.003014, just outside the
  registered 0.003 ceiling.
- Low-rank thin-sample predicted/actual ratio was 0.931 on only 20 sides.
- Top-200 predicted/actual ratio was 0.969951, just below the registered
  0.970 floor.

A3 contains a useful prospective research signal, especially for Most Aces
outcome calibration, but it failed multiple gates. Thresholds are not changed
after inspection. A3 remains an isolated experiment and cannot alter live
fair odds or signal routing.

## Operational Decision

The coverage-inclusive activity ledger is retained because it fixes false
stale classifications without changing performance projections. Players who
are active mainly in qualifying or Challenger events are labelled
`COVERAGE_GAP`, their fair odds remain research-only, and they cannot register
as automatic value bets.
