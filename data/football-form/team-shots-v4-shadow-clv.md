# Team-Shots CLV Monitor: `team_shots_v4`

Generated: 2026-11-26T18:29:47Z
Picks input: `data/football-form/team-shots-v4-shadow-signals.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 71
- Active published picks: 71
- Settled: 64
- Open/pending: 7
- Settled PnL: -8.56u
- Picks with close: 71
- True-close coverage (<=120m): 19/64 (29.7%)
- Average true-close CLV: +0.88% (n=19)
- Running mean bias (actual - model): +2.288 shots (n=64)
- Active side mix: Over 20 / Under 51
- Registered Over vig allocation: 85.6% (descriptive refits must not alter the lock)
- Hard-guard blocked: 0
- Average published-to-close CLV: +0.22%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 20 | 19 | 1 | 10-9-0 | +1.67u | +8.77% | -0.33% (n=19) |
| Under | 51 | 45 | 6 | 19-26-0 | -10.23u | -22.73% | +0.49% (n=45) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 5 | 5 | 0 | 3-2-0 | +0.64u | +12.84% | +0.23% (n=5) |
| epl | 15 | 12 | 3 | 5-7-0 | -1.87u | -15.56% | -0.42% (n=12) |
| la-liga | 24 | 22 | 2 | 8-14-0 | -6.56u | -29.84% | -0.18% (n=22) |
| ligue-1 | 9 | 8 | 1 | 4-4-0 | -0.27u | -3.38% | +0.23% (n=8) |
| serie-a | 18 | 17 | 1 | 9-8-0 | -0.50u | -2.95% | +1.29% (n=17) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 3 | 3 | 0 | 1-2-0 | -1.10u | -36.67% | -1.64% (n=3) |
| Over / epl | 6 | 5 | 1 | 3-2-0 | +1.50u | +30.00% | -1.39% (n=5) |
| Over / la-liga | 4 | 4 | 0 | 2-2-0 | +0.40u | +10.00% | -1.35% (n=4) |
| Over / ligue-1 | 4 | 4 | 0 | 2-2-0 | +0.17u | +4.25% | +0.00% (n=4) |
| Over / serie-a | 3 | 3 | 0 | 2-1-0 | +0.70u | +23.23% | +3.68% (n=3) |
| Under / bundesliga | 2 | 2 | 0 | 2-0-0 | +1.74u | +87.10% | +3.03% (n=2) |
| Under / epl | 9 | 7 | 2 | 2-5-0 | -3.37u | -48.10% | +0.26% (n=7) |
| Under / la-liga | 20 | 18 | 2 | 6-12-0 | -6.96u | -38.69% | +0.08% (n=18) |
| Under / ligue-1 | 5 | 4 | 1 | 2-2-0 | -0.44u | -11.00% | +0.46% (n=4) |
| Under / serie-a | 15 | 14 | 1 | 7-7-0 | -1.20u | -8.56% | +0.77% (n=14) |

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
