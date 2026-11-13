# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-11-13T16:31:02Z
Picks input: `data/football-form/team-shots-v4-shadow-signals.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 43
- Active published picks: 43
- Settled: 43
- Open/pending: 0
- Settled PnL: -13.62u
- Picks with close: 43
- True-close coverage (<=120m): 15/43 (34.9%)
- Average true-close CLV: +0.80% (n=15)
- Running mean bias (actual - model): +2.808 shots (n=43)
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
| Over | 8 | 8 | 0 | 2-6-0 | -4.25u | -53.16% | -0.19% (n=8) |
| Under | 35 | 35 | 0 | 14-21-0 | -9.36u | -26.75% | +0.57% (n=35) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 3 | 3 | 0 | 1-2-0 | -1.17u | -38.90% | -1.64% (n=3) |
| epl | 7 | 7 | 0 | 2-5-0 | -3.37u | -48.10% | -0.06% (n=7) |
| la-liga | 18 | 18 | 0 | 6-12-0 | -6.96u | -38.69% | +0.06% (n=18) |
| ligue-1 | 4 | 4 | 0 | 2-2-0 | -0.15u | -3.68% | +0.46% (n=4) |
| serie-a | 11 | 11 | 0 | 5-6-0 | -1.97u | -17.92% | +1.89% (n=11) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 2 | 2 | 0 | 0-2-0 | -2.00u | -100.00% | -2.47% (n=2) |
| Over / epl | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | -2.22% (n=1) |
| Over / la-liga | 2 | 2 | 0 | 0-2-0 | -2.00u | -100.00% | -2.19% (n=2) |
| Over / ligue-1 | 1 | 1 | 0 | 1-0-0 | +1.02u | +102.00% | +0.00% (n=1) |
| Over / serie-a | 2 | 2 | 0 | 1-1-0 | -0.27u | -13.65% | +5.00% (n=2) |
| Under / bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| Under / epl | 6 | 6 | 0 | 2-4-0 | -2.37u | -39.45% | +0.31% (n=6) |
| Under / la-liga | 16 | 16 | 0 | 6-10-0 | -4.96u | -31.03% | +0.34% (n=16) |
| Under / ligue-1 | 3 | 3 | 0 | 1-2-0 | -1.17u | -38.90% | +0.62% (n=3) |
| Under / serie-a | 9 | 9 | 0 | 4-5-0 | -1.70u | -18.87% | +1.20% (n=9) |

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
