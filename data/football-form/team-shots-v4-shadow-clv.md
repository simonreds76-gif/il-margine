# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-11-06T15:59:50Z
Picks input: `data/football-form/team-shots-v4-shadow-signals.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 34
- Active published picks: 34
- Settled: 29
- Open/pending: 5
- Settled PnL: -7.18u
- Picks with close: 34
- True-close coverage (<=120m): 12/29 (41.4%)
- Average true-close CLV: +0.01% (n=12)
- Running mean bias (actual - model): +3.896 shots (n=29)
- Active side mix: Over 2 / Under 32
- Registered Over vig allocation: 85.6% (descriptive refits must not alter the lock)
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.53%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 2 | 1 | 1 | 1-0-0 | +0.73u | +72.70% | +0.00% (n=1) |
| Under | 32 | 28 | 4 | 11-17-0 | -7.90u | -28.23% | +0.43% (n=28) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| epl | 6 | 4 | 2 | 1-3-0 | -2.17u | -54.17% | +0.46% (n=4) |
| la-liga | 14 | 14 | 0 | 6-8-0 | -2.96u | -21.17% | +0.25% (n=14) |
| ligue-1 | 3 | 3 | 0 | 1-2-0 | -1.17u | -38.90% | +0.62% (n=3) |
| serie-a | 10 | 7 | 3 | 3-4-0 | -1.71u | -24.47% | +0.68% (n=7) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / serie-a | 2 | 1 | 1 | 1-0-0 | +0.73u | +72.70% | +0.00% (n=1) |
| Under / bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| Under / epl | 6 | 4 | 2 | 1-3-0 | -2.17u | -54.17% | +0.46% (n=4) |
| Under / la-liga | 14 | 14 | 0 | 6-8-0 | -2.96u | -21.17% | +0.25% (n=14) |
| Under / ligue-1 | 3 | 3 | 0 | 1-2-0 | -1.17u | -38.90% | +0.62% (n=3) |
| Under / serie-a | 8 | 6 | 2 | 2-4-0 | -2.44u | -40.67% | +0.79% (n=6) |

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
