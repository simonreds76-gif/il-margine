# Assist Value Research Gates

Generated: `2026-09-06T11:41:46Z`
Lane status: **FROZEN_RESEARCH**
Reactivation ready: **NO**

## Walk-Forward Backtest

- Gate: **PASS**
- Train / validation / test: 2023-2024 / 2024-2025 / 2025-2026
- Test rows: 44,739; positives: 2,719
- Raw Brier / ECE: 0.05634 / 1.98%
- Calibrated Brier / ECE: 0.05556 / 0.47%
- Naive Brier: 0.05710
- Platt parameters: a=0.746091, b=-0.763076
- Expected-minutes MAE: mean-8 18.97; median-5 17.87
- Selected minutes estimator: `median_last_5_appearances`

## Settlement Validation

- Overall gate: **FAIL**
- Extractor accuracy: **FAIL**
- Operational coverage: **FAIL**
- Compared player appearances: 0
- Assist agreement: 0.00%
- Positive assist cases: 0; agreement 0.00%
- Assist-complete instrumented fixtures: 100/100 (100.00%)
- Legacy pre-instrumentation fixtures excluded from completeness denominator: 0
- Player matching coverage: 0.00%

## Market Evidence

- Gate: **FAIL**
- Matched participating players: 1,300
- Old matched shadow signals: 0
- Captured calendar span: 8 days (minimum 90)
- Margin-adjustment holdout rows: 598
- Reason blocked: `one_sided_margin_adjustment_needs_90_days_and_prospective_confirmation`
- The fitted one-sided margin adjustment remains research-only and is not treated as CLV.

## Prospective Gate

- Registered v1 signals: 0
- Settled v1 signals: 0/100
- This counter starts only after all upstream gates are implemented and the new model version is locked.
