# Team Shots Unified Backfill Validation

Generated: 2026-07-13
Status: **research input only; do not replace the live v3 lane**

## Coverage

- Seasons: 2014-15 through 2025-26
- Leagues: Premier League, Serie A, La Liga, Bundesliga, Ligue 1
- Candidate rows: 21,587
- Historical-spine fixture matches: 21,587 / 21,587 (100%)
- Understat xG matches: 19,770 / 21,587 (91.6%)
- Football-Data-only rows: 1,817
- Reference-only rows excluded for missing usable shot counts: 2

## Count Reconciliation

All 21,587 matched rows have zero deltas against the Football-Data historical
spine for home/away shots, shots on target, and corners. The machine-readable
result is in `source-reconciliation.json`.

## Production Safety Check

Feeding this long artifact into the legacy standalone `team-shots-model.py`
and scoring the 2024-08-01 onward holdout produced:

- Predictions: 6,922
- Mean predicted shots: 13.24
- Mean actual shots: 12.49
- Bias: +0.75 shots
- MAE: 3.85

This confirms that the backfill is suitable for the registered v4 walk-forward
experiment, but it must not silently replace the canonical v3 live mean. V4
must fit its dispersion and calibration causally on rolling folds before any
publication or routing change.
