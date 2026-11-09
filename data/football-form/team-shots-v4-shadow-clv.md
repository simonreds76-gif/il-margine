# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-11-09T18:53:14Z
Picks input: `data/football-form/team-shots-v4-shadow-signals.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 43
- Active published picks: 43
- Settled: 35
- Open/pending: 8
- Settled PnL: -9.47u
- Picks with close: 43
- True-close coverage (<=120m): 15/43 (34.9%)
- Average true-close CLV: +0.80% (n=15)
- Running mean bias (actual - model): +3.691 shots (n=35)
- Active side mix: Over 8 / Under 35
- Registered Over vig allocation: 85.6% (descriptive refits must not alter the lock)
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.43%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 8 | 2 | 6 | 1-1-0 | -0.27u | -13.65% | +0.00% (n=2) |
| Under | 35 | 33 | 2 | 13-20-0 | -9.20u | -27.87% | +0.55% (n=33) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 3 | 1 | 2 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| epl | 7 | 6 | 1 | 2-4-0 | -2.37u | -39.45% | +0.31% (n=6) |
| la-liga | 18 | 16 | 2 | 6-10-0 | -4.96u | -31.03% | +0.22% (n=16) |
| ligue-1 | 4 | 3 | 1 | 1-2-0 | -1.17u | -38.90% | +0.62% (n=3) |
| serie-a | 11 | 9 | 2 | 4-5-0 | -1.80u | -20.04% | +1.20% (n=9) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 2 | 0 | 2 | 0-0-0 | +0.00u | - | - (n=0) |
| Over / epl | 1 | 0 | 1 | 0-0-0 | +0.00u | - | - (n=0) |
| Over / la-liga | 2 | 1 | 1 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Over / ligue-1 | 1 | 0 | 1 | 0-0-0 | +0.00u | - | - (n=0) |
| Over / serie-a | 2 | 1 | 1 | 1-0-0 | +0.73u | +72.70% | +0.00% (n=1) |
| Under / bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| Under / epl | 6 | 6 | 0 | 2-4-0 | -2.37u | -39.45% | +0.31% (n=6) |
| Under / la-liga | 16 | 15 | 1 | 6-9-0 | -3.96u | -26.43% | +0.24% (n=15) |
| Under / ligue-1 | 3 | 3 | 0 | 1-2-0 | -1.17u | -38.90% | +0.62% (n=3) |
| Under / serie-a | 9 | 8 | 1 | 3-5-0 | -2.53u | -31.64% | +1.35% (n=8) |

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
