# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-11-23T20:20:27Z
Picks input: `data/football-form/team-shots-v4-shadow-signals.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 64
- Active published picks: 64
- Settled: 52
- Open/pending: 12
- Settled PnL: -12.45u
- Picks with close: 64
- True-close coverage (<=120m): 19/64 (29.7%)
- Average true-close CLV: +0.88% (n=19)
- Running mean bias (actual - model): +2.743 shots (n=52)
- Active side mix: Over 19 / Under 45
- Registered Over vig allocation: 85.6% (descriptive refits must not alter the lock)
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.25%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 19 | 12 | 7 | 5-7-0 | -1.75u | -14.61% | -0.52% (n=12) |
| Under | 45 | 40 | 5 | 16-24-0 | -10.70u | -26.74% | +0.40% (n=40) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 5 | 3 | 2 | 1-2-0 | -1.17u | -38.90% | -1.64% (n=3) |
| epl | 12 | 11 | 1 | 5-6-0 | -0.87u | -7.88% | -0.46% (n=11) |
| la-liga | 22 | 20 | 2 | 6-14-0 | -8.96u | -44.82% | -0.15% (n=20) |
| ligue-1 | 8 | 4 | 4 | 2-2-0 | -0.15u | -3.68% | +0.46% (n=4) |
| serie-a | 17 | 14 | 3 | 7-7-0 | -1.31u | -9.32% | +1.49% (n=14) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 3 | 2 | 1 | 0-2-0 | -2.00u | -100.00% | -2.47% (n=2) |
| Over / epl | 5 | 5 | 0 | 3-2-0 | +1.50u | +30.00% | -1.39% (n=5) |
| Over / la-liga | 4 | 2 | 2 | 0-2-0 | -2.00u | -100.00% | -2.19% (n=2) |
| Over / ligue-1 | 4 | 1 | 3 | 1-0-0 | +1.02u | +102.00% | +0.00% (n=1) |
| Over / serie-a | 3 | 2 | 1 | 1-1-0 | -0.27u | -13.65% | +5.00% (n=2) |
| Under / bundesliga | 2 | 1 | 1 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| Under / epl | 7 | 6 | 1 | 2-4-0 | -2.37u | -39.45% | +0.31% (n=6) |
| Under / la-liga | 18 | 18 | 0 | 6-12-0 | -6.96u | -38.69% | +0.08% (n=18) |
| Under / ligue-1 | 4 | 3 | 1 | 1-2-0 | -1.17u | -38.90% | +0.62% (n=3) |
| Under / serie-a | 14 | 12 | 2 | 6-6-0 | -1.03u | -8.60% | +0.90% (n=12) |

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
