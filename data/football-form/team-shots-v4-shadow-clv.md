# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-10-23T13:31:44Z
Picks input: `data/football-form/team-shots-v4-shadow-signals.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 21
- Active published picks: 21
- Settled: 17
- Open/pending: 4
- Settled PnL: -2.68u
- Picks with close: 21
- True-close coverage (<=120m): 9/17 (52.9%)
- Average true-close CLV: -0.40% (n=9)
- Running mean bias (actual - model): +3.518 shots (n=17)
- Active side mix: Over 1 / Under 20
- Registered Over vig allocation: 85.6% (descriptive refits must not alter the lock)
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.07%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 1 | 1 | 0 | 1-0-0 | +0.73u | +72.70% | +0.00% (n=1) |
| Under | 20 | 16 | 4 | 7-9-0 | -3.40u | -21.27% | -0.47% (n=16) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| epl | 2 | 1 | 1 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| la-liga | 12 | 11 | 1 | 5-6-0 | -1.96u | -17.85% | -0.69% (n=11) |
| ligue-1 | 1 | 0 | 1 | 0-0-0 | +0.00u | - | - (n=0) |
| serie-a | 5 | 4 | 1 | 2-2-0 | -0.55u | -13.65% | +0.00% (n=4) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / serie-a | 1 | 1 | 0 | 1-0-0 | +0.73u | +72.70% | +0.00% (n=1) |
| Under / bundesliga | 1 | 1 | 0 | 1-0-0 | +0.83u | +83.30% | +0.00% (n=1) |
| Under / epl | 2 | 1 | 1 | 0-1-0 | -1.00u | -100.00% | +0.00% (n=1) |
| Under / la-liga | 12 | 11 | 1 | 5-6-0 | -1.96u | -17.85% | -0.69% (n=11) |
| Under / ligue-1 | 1 | 0 | 1 | 0-0-0 | +0.00u | - | - (n=0) |
| Under / serie-a | 4 | 3 | 1 | 1-2-0 | -1.27u | -42.43% | +0.00% (n=3) |

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
