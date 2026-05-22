# Team-Shots CLV Monitor: `canonical_form_v3_ema20_nb`

Generated: 2026-05-22T19:05:11Z
Picks input: `data/football-form/team-shots-v3-ema20-published-picks.csv`
Odds input: `data/team-shots/team-shots-odds-history.csv`

## Summary

- Picks: 72
- Active published picks: 68
- Settled: 60
- Open/pending: 12
- Settled PnL: +6.10u
- Picks with close: 72
- Hard-guard blocked: 4
- Average published-to-close CLV: +0.35%
- Allowed-league config valid: yes
- Allowed leagues: `bundesliga, epl, la-liga, ligue-1, serie-a`
- Config error: `-`

## Active Side Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over | 23 | 22 | 1 | 10-12-0 | -3.59u | -16.30% | +0.41% (n=22) |
| Under | 45 | 34 | 11 | 22-12-0 | +6.16u | +18.11% | +0.00% (n=34) |

## Active League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| bundesliga | 11 | 11 | 0 | 5-6-0 | -2.19u | -19.87% | +0.00% (n=11) |
| epl | 14 | 11 | 3 | 7-4-0 | +1.76u | +16.03% | +0.00% (n=11) |
| la-liga | 17 | 13 | 4 | 8-5-0 | +2.34u | +18.02% | +0.70% (n=13) |
| serie-a | 26 | 21 | 5 | 12-9-0 | +0.65u | +3.10% | +0.00% (n=21) |

## Active Side x League Breakdown

| Segment | Active | Settled | Pending | W-L-P | PnL | ROI | Avg CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| Over / bundesliga | 6 | 6 | 0 | 4-2-0 | +0.98u | +16.35% | +0.00% (n=6) |
| Over / epl | 3 | 3 | 0 | 1-2-0 | -1.00u | -33.33% | +0.00% (n=3) |
| Over / la-liga | 5 | 5 | 0 | 3-2-0 | +0.80u | +16.00% | +1.82% (n=5) |
| Over / serie-a | 9 | 8 | 1 | 2-6-0 | -4.37u | -54.59% | +0.00% (n=8) |
| Under / bundesliga | 5 | 5 | 0 | 1-4-0 | -3.17u | -63.34% | +0.00% (n=5) |
| Under / epl | 11 | 8 | 3 | 6-2-0 | +2.76u | +34.54% | +0.00% (n=8) |
| Under / la-liga | 12 | 8 | 4 | 5-3-0 | +1.54u | +19.28% | +0.00% (n=8) |
| Under / serie-a | 17 | 13 | 4 | 10-3-0 | +5.02u | +38.61% | +0.00% (n=13) |

## Required Fields

- `current_model_would_have_priced` must be true while canonical-only evidence is blocked.
- `time_to_kickoff_hours` records publication timing so CLV can be interpreted by lead time.
- `published_to_close_clv` tracks the captured bookmaker price versus close.
- `model_to_close_clv` tracks the model-implied probability versus close.
- `confidence_guard_applied=true` means the row must not be treated as a published pick.

## De-Promotion Rules

- Pause `canonical_form_v3_ema20_nb` if 30-day rolling CLV is below 0 with at least 50 settled picks.
- Pause `canonical_form_v3_ema20_nb` if rolling 90-day production Brier exceeds 1.05x the pre-promotion backtest Brier.
