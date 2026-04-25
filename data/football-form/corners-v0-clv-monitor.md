# Corners V0 CLV Monitor

Generated: 2026-04-25T14:24:07Z
Picks input: `data\football-form\corners-v0-published-picks.csv`
Pinnacle input: `data\corners-ou\pinnacle-corners-odds.csv`

## Summary

- Picks: 0
- Picks with close: 0
- Hard-guard blocked: 0
- Average published-to-close CLV: -

## Required Fields

- `current_model_would_have_priced` must be true for publication while canonical-only evidence is below threshold.
- `published_to_close_clv` tracks the taken/published Pinnacle price versus close.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause corners v0 if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause corners v0 if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.
