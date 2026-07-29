# Most Aces Direct 1X2 Experiment

Registered: 2026-07-29

## Hypothesis

The existing Most Aces lane estimates two ace-count means and converts their
negative-binomial distributions into P1/Draw/P2 probabilities. A3 improved
Most Aces Brier score while failing some individual count-model gates. This
may indicate an objective mismatch: a model trained directly on the three-way
outcome could price the target market better than two separately optimised
count means.

This experiment does not replace the ace-count models. Their causal
projections are retained as inputs and as the A0 control.

## Data and Symmetry

- Source: causal ATP Hard/Clay side rows from the registered A3 matrix.
- One canonical row per match, paired by date, tournament, round and player
  IDs.
- The target is `P1`, `DRAW` or `P2` from realised ace counts.
- Every training row is mirrored with players reversed and the target
  reversed.
- Inference averages the canonical prediction with the reversed prediction
  mapped back into canonical order.
- Actual ace counts and all post-match fields are barred from features.

## Features

- Causal pre-match incumbent ace-count projections and their difference/total.
- Causal player ace rates over L12M, L24M and four years.
- Opponent ace allowance and return-strength adjustments.
- Expected service points and match workload.
- Venue and surface context.
- Current rank, age, height and lagged rank movement.
- All-level inactivity and activity coverage.

Only symmetric totals and signed P1-minus-P2 differences are exposed to the
model.

## Chronology

- Development training: 2023.
- Iteration selection and temperature calibration: 2024.
- Frozen final training: 2023-2024.
- Historical selection test: 2025.
- Diagnostic only: 2026 through 2026-07-29.
- Prospective shadow: 2026-07-30 onward.

The architecture was designed after 2026 had been inspected. Neither 2025 nor
2026 can authorise live routing. A passing retrospective result permits only a
frozen prospective shadow comparison.

## Retrospective Gates

- Selection Brier improves by at least 0.005 versus count-derived A0.
- Selection multiclass log-loss improves by at least 0.005.
- Selection accuracy does not regress by more than 1 percentage point.
- Hard and Clay Brier each regress by no more than 0.010 when `n >= 200`.
- Predicted draw rate is within 3 percentage points of the realised draw rate.
- Mean raw player-order symmetry gap is at most 0.03.
- At least 1,000 selection matches are scored.
- Diagnostic 2026 Brier and log-loss do not regress versus A0.

## Promotion Restriction

Passing all retrospective gates permits prospective shadow tracking only.
Betting or public fair-odds use requires at least 300 prospectively timestamped
priced observations across 100 events, positive CLV of at least 1%, and a
separate pre-registered promotion review.

## Frozen Retrospective Result

Status: **PASS - prospective shadow eligible**

- 2025 Brier: 0.440276 count-derived A0 to 0.433838 direct.
- 2025 log-loss: 0.756163 to 0.750648.
- 2026 diagnostic Brier: 0.464443 to 0.457280.
- 2026 diagnostic log-loss: 0.793194 to 0.789099.
- 2025 predicted draw rate: 9.19%; realised draw rate: 8.50%.
- Mean raw player-order symmetry gap: 0.007756.
- Every registered retrospective gate passed.

## Prospective Shadow Plumbing

Status: **ACTIVE from fixtures dated 2026-07-30 onward**

- `tennis-most-aces-direct-live.py` builds the direct board from the same
  causal rolling state and pairwise feature algebra used by the retrospective
  experiment.
- Current rank and age come from the pre-match OnCourt player snapshot;
  historical ace, return, activity and venue features come from completed
  Sackmann matches strictly before the feature date.
- A fixture is blocked when both players cannot be resolved to the registered
  history. The scorer does not force a partial or fuzzy one-player match.
- Direct and count-derived A0 forecasts are registered before the match in the
  same append-only ledger under distinct model IDs.
- Settlement scores both models from the same realised ace counts and reports
  paired Brier and log-loss deltas on common events.
- The localhost monitor shows both forecasts on one fixture card.

This remains outcome-only prospective evidence. It has no bookmaker price,
value, ROI, CLV, public routing or staking authority.
