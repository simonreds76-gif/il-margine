# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-10-29T15:18:00Z
Picks input: `data/football-form/team-shots-v4-shadow-signals.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 22
- Active published picks: 22
- Settled: 21
- Open/pending: 1
- Settled PnL: -2.84u
- Picks with close: 22
- True-close coverage (<=120m): 10/21 (47.6%)
- Average true-close CLV: -0.18% (n=10)
- Running mean bias (actual - model): +3.781 shots (n=21)
- Active side mix: Over 1 / Under 21
- Registered Over vig allocation: 85.6% (descriptive refits must not alter the lock)
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.46%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 1 | 1 | 0 | 1-0-0 | +0.73u | +72.70% | +0.00% (n=1) |
| Under | 21 | 20 | 1 | 9-11-0 | -3.57u | -17.85% | +0.51% (n=20) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| epl | 2 | 2 | 0 | 1-1-0 | -0.17u | -8.35% | +0.92% (n=2) |
| la-liga | 12 | 12 | 0 | 6-6-0 | -0.96u | -8.03% | +0.29% (n=12) |
| ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| serie-a | 6 | 5 | 1 | 2-3-0 | -1.55u | -30.92% | +0.95% (n=5) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / serie-a | 1 | 1 | 0 | 1-0-0 | +0.73u | +72.70% | +0.00% (n=1) |
| Under / bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| Under / epl | 2 | 2 | 0 | 1-1-0 | -0.17u | -8.35% | +0.92% (n=2) |
| Under / la-liga | 12 | 12 | 0 | 6-6-0 | -0.96u | -8.03% | +0.29% (n=12) |
| Under / ligue-1 | 1 | 1 | 0 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Under / serie-a | 5 | 4 | 1 | 1-3-0 | -2.27u | -56.83% | +1.19% (n=4) |

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
