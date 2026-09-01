# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-09-01T14:27:12Z
Picks input: `data\football-form\team-shots-v4-shadow-signals.csv`
Odds input: `data\team-shots\team-shots-odds-history.csv`

## Summary

- Picks: 12
- Active published picks: 12
- Settled: 5
- Open/pending: 7
- Settled PnL: +0.44u
- Picks with close: 12
- True-close coverage (<=120m): 6/12 (50.0%)
- Average true-close CLV: -0.60% (n=6)
- Running mean bias (actual - model): -
- Active side mix: Over 1 / Under 11
- Registered Over vig allocation: 85.6% (descriptive refits must not alter the lock)
- Hard-guard blocked: 0
- Average published-to-close CLV: -0.30%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 1 | 0 | 1 | 0-0-0 | +0.00u | - | - (n=0) |
| Under | 11 | 5 | 6 | 3-2-0 | +0.44u | +8.72% | +0.00% (n=5) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| epl | 1 | 0 | 1 | 0-0-0 | +0.00u | - | - (n=0) |
| la-liga | 7 | 4 | 3 | 3-1-0 | +1.44u | +35.90% | +0.00% (n=4) |
| serie-a | 4 | 1 | 3 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / serie-a | 1 | 0 | 1 | 0-0-0 | +0.00u | - | - (n=0) |
| Under / epl | 1 | 0 | 1 | 0-0-0 | +0.00u | - | - (n=0) |
| Under / la-liga | 7 | 4 | 3 | 3-1-0 | +1.44u | +35.90% | +0.00% (n=4) |
| Under / serie-a | 3 | 1 | 2 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |

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
