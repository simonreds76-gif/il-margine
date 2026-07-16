# Assist Value Research Gates

Generated: `2026-07-16T14:39:01Z`
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

- Overall gate: **PASS**
- Extractor accuracy: **PASS**
- Operational coverage: **PASS**
- Compared player appearances: 2,236
- Assist agreement: 99.91%
- Positive assist cases: 153; agreement 98.69%
- Assist-complete instrumented fixtures: 84/88 (95.45%)
- Legacy pre-instrumentation fixtures excluded from completeness denominator: 77
- Player matching coverage: 90.05%

## Market Evidence

- Gate: **FAIL**
- Matched participating players: 1,300
- Old matched shadow signals: 9
- Captured calendar span: 8 days (minimum 90)
- Margin-adjustment holdout rows: 598
- Reason blocked: `one_sided_margin_adjustment_needs_90_days_and_prospective_confirmation`
- The fitted one-sided margin adjustment remains research-only and is not treated as CLV.

## Prospective Gate

- Registered v1 signals: 0
- Settled v1 signals: 0/100
- This counter starts only after all upstream gates are implemented and the new model version is locked.
