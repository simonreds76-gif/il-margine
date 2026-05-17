# Team-Shots CLV Monitor: `canonical_form_v3_ema20_nb`

Generated: 2026-05-17T13:01:40Z
Picks input: `data/football-form/team-shots-v3-ema20-published-picks.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 60
- Active published picks: 56
- Settled: 48
- Open/pending: 12
- Settled PnL: -0.24u
- Picks with close: 60
- Hard-guard blocked: 4
- Average published-to-close CLV: +0.42%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 22 | 20 | 2 | 9-11-0 | -3.59u | -17.93% | +0.46% (n=20) |
| Under | 34 | 24 | 10 | 13-11-0 | -0.18u | -0.75% | +0.00% (n=24) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 11 | 11 | 0 | 5-6-0 | -2.19u | -19.87% | +0.00% (n=11) |
| epl | 11 | 8 | 3 | 4-4-0 | -0.75u | -9.32% | +0.00% (n=8) |
| la-liga | 13 | 10 | 3 | 6-4-0 | +1.43u | +14.33% | +0.91% (n=10) |
| serie-a | 21 | 15 | 6 | 7-8-0 | -2.27u | -15.12% | +0.00% (n=15) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 6 | 6 | 0 | 4-2-0 | +0.98u | +16.35% | +0.00% (n=6) |
| Over / epl | 3 | 3 | 0 | 1-2-0 | -1.00u | -33.33% | +0.00% (n=3) |
| Over / la-liga | 5 | 3 | 2 | 2-1-0 | +0.80u | +26.67% | +3.04% (n=3) |
| Over / serie-a | 8 | 8 | 0 | 2-6-0 | -4.37u | -54.59% | +0.00% (n=8) |
| Under / bundesliga | 5 | 5 | 0 | 1-4-0 | -3.17u | -63.34% | +0.00% (n=5) |
| Under / epl | 8 | 5 | 3 | 3-2-0 | +0.25u | +5.08% | +0.00% (n=5) |
| Under / la-liga | 8 | 7 | 1 | 4-3-0 | +0.63u | +9.04% | +0.00% (n=7) |
| Under / serie-a | 13 | 7 | 6 | 5-2-0 | +2.10u | +29.99% | +0.00% (n=7) |

## Required Fields

- `current_model_would_have_priced` must be true while canonical-only evidence is blocked.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` tracks the captured bookmaker price versus close.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause `canonical_form_v3_ema20_nb` if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause `canonical_form_v3_ema20_nb` if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.
