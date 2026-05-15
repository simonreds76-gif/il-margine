# Team-Shots CLV Monitor: `canonical_form_v3_ema20_nb`

Generated: 2026-05-15T10:39:53Z
Picks input: `data/football-form/team-shots-v3-ema20-published-picks.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 55
- Active published picks: 51
- Settled: 43
- Open/pending: 12
- Settled PnL: +2.96u
- Picks with close: 55
- Hard-guard blocked: 4
- Average published-to-close CLV: +0.45%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 19 | 18 | 1 | 8-10-0 | -3.39u | -18.81% | +0.51% (n=18) |
| Under | 32 | 21 | 11 | 13-8-0 | +2.82u | +13.42% | +0.00% (n=21) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 10 | 7 | 3 | 4-3-0 | +0.01u | +0.20% | +0.00% (n=7) |
| epl | 11 | 7 | 4 | 4-3-0 | +0.25u | +3.63% | +0.00% (n=7) |
| la-liga | 10 | 10 | 0 | 6-4-0 | +1.43u | +14.33% | +0.91% (n=10) |
| serie-a | 20 | 15 | 5 | 7-8-0 | -2.27u | -15.12% | +0.00% (n=15) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 5 | 4 | 1 | 3-1-0 | +1.18u | +29.53% | +0.00% (n=4) |
| Over / epl | 3 | 3 | 0 | 1-2-0 | -1.00u | -33.33% | +0.00% (n=3) |
| Over / la-liga | 3 | 3 | 0 | 2-1-0 | +0.80u | +26.67% | +3.04% (n=3) |
| Over / serie-a | 8 | 8 | 0 | 2-6-0 | -4.37u | -54.59% | +0.00% (n=8) |
| Under / bundesliga | 5 | 3 | 2 | 1-2-0 | -1.17u | -38.90% | +0.00% (n=3) |
| Under / epl | 8 | 4 | 4 | 3-1-0 | +1.25u | +31.35% | +0.00% (n=4) |
| Under / la-liga | 7 | 7 | 0 | 4-3-0 | +0.63u | +9.04% | +0.00% (n=7) |
| Under / serie-a | 12 | 7 | 5 | 5-2-0 | +2.10u | +29.99% | +0.00% (n=7) |

## Required Fields

- `current_model_would_have_priced` must be true while canonical-only evidence is blocked.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` tracks the captured bookmaker price versus close.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause `canonical_form_v3_ema20_nb` if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause `canonical_form_v3_ema20_nb` if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.
