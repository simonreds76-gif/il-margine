# Team-Shots CLV Monitor: `canonical_form_v3_ema20_nb`

Generated: 2026-05-01T09:44:39Z
Picks input: `data/football-form/team-shots-v3-ema20-published-picks.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 22
- Settled: 9
- Open/pending: 13
- Settled PnL: +4.13u
- Picks with close: 22
- Hard-guard blocked: 13
- Average published-to-close CLV: +0.41%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Required Fields

- `current_model_would_have_priced` must be true while canonical-only evidence is blocked.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` tracks the captured bookmaker price versus close.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause `canonical_form_v3_ema20_nb` if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause `canonical_form_v3_ema20_nb` if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.
