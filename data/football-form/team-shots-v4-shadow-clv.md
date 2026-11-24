# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-11-24T19:33:56Z
Picks input: `data/football-form/team-shots-v4-shadow-signals.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 64
- Active published picks: 64
- Settled: 62
- Open/pending: 2
- Settled PnL: -8.76u
- Picks with close: 64
- True-close coverage (<=120m): 19/64 (29.7%)
- Average true-close CLV: +0.88% (n=19)
- Running mean bias (actual - model): +2.265 shots (n=62)
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
| Over | 19 | 18 | 1 | 9-9-0 | +0.47u | +2.59% | -0.75% (n=18) |
| Under | 45 | 44 | 1 | 19-25-0 | -9.23u | -20.97% | +0.50% (n=44) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 5 | 5 | 0 | 3-2-0 | +0.64u | +12.84% | +0.23% (n=5) |
| epl | 12 | 12 | 0 | 5-7-0 | -1.87u | -15.56% | -0.42% (n=12) |
| la-liga | 22 | 21 | 1 | 7-14-0 | -7.76u | -36.97% | -0.54% (n=21) |
| ligue-1 | 8 | 8 | 0 | 4-4-0 | -0.27u | -3.38% | +0.23% (n=8) |
| serie-a | 17 | 16 | 1 | 9-7-0 | +0.50u | +3.11% | +1.37% (n=16) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 3 | 3 | 0 | 1-2-0 | -1.10u | -36.67% | -1.64% (n=3) |
| Over / epl | 5 | 5 | 0 | 3-2-0 | +1.50u | +30.00% | -1.39% (n=5) |
| Over / la-liga | 4 | 3 | 1 | 1-2-0 | -0.80u | -26.67% | -4.24% (n=3) |
| Over / ligue-1 | 4 | 4 | 0 | 2-2-0 | +0.17u | +4.25% | +0.00% (n=4) |
| Over / serie-a | 3 | 3 | 0 | 2-1-0 | +0.70u | +23.23% | +3.68% (n=3) |
| Under / bundesliga | 2 | 2 | 0 | 2-0-0 | +1.74u | +87.10% | +3.03% (n=2) |
| Under / epl | 7 | 7 | 0 | 2-5-0 | -3.37u | -48.10% | +0.26% (n=7) |
| Under / la-liga | 18 | 18 | 0 | 6-12-0 | -6.96u | -38.69% | +0.08% (n=18) |
| Under / ligue-1 | 4 | 4 | 0 | 2-2-0 | -0.44u | -11.00% | +0.46% (n=4) |
| Under / serie-a | 14 | 13 | 1 | 7-6-0 | -0.20u | -1.53% | +0.83% (n=13) |

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
