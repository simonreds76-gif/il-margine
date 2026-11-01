# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-11-01T09:45:29Z
Picks input: `data/football-form/team-shots-v4-shadow-signals.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 29
- Active published picks: 29
- Settled: 24
- Open/pending: 5
- Settled PnL: -4.01u
- Picks with close: 29
- True-close coverage (<=120m): 12/27 (44.4%)
- Average true-close CLV: +0.01% (n=12)
- Running mean bias (actual - model): +3.874 shots (n=24)
- Active side mix: Over 1 / Under 28
- Registered Over vig allocation: 85.6% (descriptive refits must not alter the lock)
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.41%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 1 | 1 | 0 | 1-0-0 | +0.73u | +72.70% | +0.00% (n=1) |
| Under | 28 | 23 | 5 | 10-13-0 | -4.74u | -20.60% | +0.52% (n=23) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| epl | 4 | 2 | 2 | 1-1-0 | -0.17u | -8.35% | +0.92% (n=2) |
| la-liga | 14 | 12 | 2 | 6-6-0 | -0.96u | -8.03% | +0.29% (n=12) |
| ligue-1 | 3 | 3 | 0 | 1-2-0 | -1.17u | -38.90% | +0.62% (n=3) |
| serie-a | 7 | 6 | 1 | 2-4-0 | -2.55u | -42.43% | +0.79% (n=6) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / serie-a | 1 | 1 | 0 | 1-0-0 | +0.73u | +72.70% | +0.00% (n=1) |
| Under / bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| Under / epl | 4 | 2 | 2 | 1-1-0 | -0.17u | -8.35% | +0.92% (n=2) |
| Under / la-liga | 14 | 12 | 2 | 6-6-0 | -0.96u | -8.03% | +0.29% (n=12) |
| Under / ligue-1 | 3 | 3 | 0 | 1-2-0 | -1.17u | -38.90% | +0.62% (n=3) |
| Under / serie-a | 6 | 5 | 1 | 1-4-0 | -3.27u | -65.46% | +0.95% (n=5) |

## Required Fields

- `current_model_would_have_priced` must be true while canonical-only evidence is blocked.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` tracks the captured bookmaker price versus close.
- `close_lag_minutes` records how far the selected close snapshot was from kickoff; `true_close=true` requires <=120 minutes.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `model_mean` preserves the frozen count expectation so weekly actual-minus-model bias is observable.
- Side mix is diagnostic: strong Over shading can make Under selections dominant by construction.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause `team_shots_v4` if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause `team_shots_v4` if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.
